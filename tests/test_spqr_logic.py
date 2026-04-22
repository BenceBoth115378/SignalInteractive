from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from components.data_classes import SckaOutputKey, SckaReceiveResult, SckaSendResult, SpqrHeader, SpqrMessageType, SpqrSckaMessage  # noqa: E402
from modules.messaging.spqr import logic  # noqa: E402


@pytest.fixture(autouse=True)
def deterministic_aead(monkeypatch: pytest.MonkeyPatch):
    def fake_encrypt(mk: bytes, plaintext: bytes, associated_data: bytes) -> bytes:
        tag = hashlib.sha256(mk + associated_data).digest()[:8]
        return b"ct:" + tag + plaintext

    def fake_decrypt(mk: bytes, ciphertext: bytes, associated_data: bytes) -> bytes:
        prefix = b"ct:"
        if not ciphertext.startswith(prefix):
            raise ValueError("Unexpected ciphertext format")
        body = ciphertext[len(prefix):]
        if len(body) < 8:
            raise ValueError("Ciphertext too short")
        expected_tag = hashlib.sha256(mk + associated_data).digest()[:8]
        actual_tag = body[:8]
        if actual_tag != expected_tag:
            raise ValueError("Authentication failed")
        return body[8:]

    monkeypatch.setattr(logic.ext, "ENCRYPT", fake_encrypt)
    monkeypatch.setattr(logic.ext, "DECRYPT", fake_decrypt)


def _msg(epoch: int, msg_type: SpqrMessageType = SpqrMessageType.NONE, data: bytes = b"") -> SpqrSckaMessage:
    return SpqrSckaMessage(epoch=epoch, msg_type=msg_type, data=data)


def _bootstrap_states(shared_secret: bytes = b"spqr-shared-secret"):
    alice = logic.RatchetInitAliceSCKA(shared_secret)
    bob = logic.RatchetInitBobSCKA(shared_secret)
    return alice, bob


def test_ratchet_init_sets_complementary_chain_directions():
    alice, bob = _bootstrap_states()

    assert alice.direction == "A2B"
    assert bob.direction == "B2A"
    assert alice.epoch == 0
    assert bob.epoch == 0
    assert 0 in alice.kdfchains
    assert 0 in bob.kdfchains

    alice_send = alice.kdfchains[0].send
    alice_recv = alice.kdfchains[0].receive
    bob_send = bob.kdfchains[0].send
    bob_recv = bob.kdfchains[0].receive

    assert alice_send is not None and alice_recv is not None
    assert bob_send is not None and bob_recv is not None
    assert alice_send.CK == bob_recv.CK
    assert alice_recv.CK == bob_send.CK


def test_try_skipped_message_keys_returns_and_deletes_key():
    state, _ = _bootstrap_states()
    state.MKSKIPPED = {2: {7: b"mk-2-7"}}

    mk = logic.TrySkippedMessageKeys(state, 2, 7)

    assert mk == b"mk-2-7"
    assert 2 not in state.MKSKIPPED


def test_clear_old_epochs_removes_epoch_minus_two_data():
    state, _ = _bootstrap_states()
    state.kdfchains[1] = state.kdfchains[0]
    state.kdfchains[2] = state.kdfchains[0]
    state.MKSKIPPED[1] = {1: b"old-mk"}

    logic.ClearOldEpochs(state, sending_epoch=3)

    assert 1 not in state.kdfchains
    assert 1 not in state.MKSKIPPED


def test_skip_message_keys_derives_and_stores_missing_keys():
    state, _ = _bootstrap_states()

    logic.SkipMessageKeys(state, epoch=0, until=3)

    chains = state.kdfchains[0]
    assert chains.receive is not None
    assert chains.receive.N == 3
    assert 0 in state.MKSKIPPED
    assert set(state.MKSKIPPED[0].keys()) == {1, 2, 3}


def test_skip_message_keys_enforces_max_skip_window():
    state, _ = _bootstrap_states()

    with pytest.raises(ValueError, match="Too many skipped SPQR message keys"):
        logic.SkipMessageKeys(state, epoch=0, until=6, max_skip=5)


def test_scka_ratchet_encrypt_decrypt_roundtrip(monkeypatch: pytest.MonkeyPatch):
    alice, bob = _bootstrap_states()

    def fake_send(_state):
        return SckaSendResult(msg=_msg(epoch=1), sending_epoch=0, output_key=None)

    def fake_receive(_state, _msg_obj):
        return SckaReceiveResult(receiving_epoch=0, output_key=None)

    monkeypatch.setattr(logic, "SCKASend", fake_send)
    monkeypatch.setattr(logic, "SCKAReceive", fake_receive)

    header, ciphertext, send_trace = logic.SCKARatchetEncrypt(alice, b"hello-spqr", b"ad")
    plaintext, recv_trace = logic.SCKARatchetDecrypt(bob, header, ciphertext, b"ad")

    assert plaintext == b"hello-spqr"
    assert send_trace["counter"] == 1
    assert recv_trace["counter"] == 1
    assert recv_trace["used_skipped_key"] is False


def test_scka_out_of_order_messages_use_skipped_keys(monkeypatch: pytest.MonkeyPatch):
    alice, bob = _bootstrap_states()

    def fake_send(_state):
        return SckaSendResult(msg=_msg(epoch=1), sending_epoch=0, output_key=None)

    def fake_receive(_state, _msg_obj):
        return SckaReceiveResult(receiving_epoch=0, output_key=None)

    monkeypatch.setattr(logic, "SCKASend", fake_send)
    monkeypatch.setattr(logic, "SCKAReceive", fake_receive)

    m1 = logic.SCKARatchetEncrypt(alice, b"m1", b"ad")
    m2 = logic.SCKARatchetEncrypt(alice, b"m2", b"ad")
    m3 = logic.SCKARatchetEncrypt(alice, b"m3", b"ad")

    header3, cipher3, _ = m3
    plain3, trace3 = logic.SCKARatchetDecrypt(bob, header3, cipher3, b"ad")
    assert plain3 == b"m3"
    assert trace3["used_skipped_key"] is False
    assert 0 in bob.MKSKIPPED
    assert set(bob.MKSKIPPED[0].keys()) == {1, 2}

    header1, cipher1, _ = m1
    plain1, trace1 = logic.SCKARatchetDecrypt(bob, header1, cipher1, b"ad")
    assert plain1 == b"m1"
    assert trace1["used_skipped_key"] is True

    header2, cipher2, _ = m2
    plain2, trace2 = logic.SCKARatchetDecrypt(bob, header2, cipher2, b"ad")
    assert plain2 == b"m2"
    assert trace2["used_skipped_key"] is True
    assert 0 not in bob.MKSKIPPED


def test_scka_ratchet_send_key_updates_epoch_on_output_key(monkeypatch: pytest.MonkeyPatch):
    state, _ = _bootstrap_states()

    def fake_send(_state):
        return SckaSendResult(
            msg=_msg(epoch=2),
            sending_epoch=1,
            output_key=SckaOutputKey(epoch=1, key=b"ok-epoch-1"),
            raw_ss=b"raw-ss",
        )

    monkeypatch.setattr(logic, "SCKASend", fake_send)

    _msg_out, counter, mk, trace = logic.SCKARatchetSendKey(state)

    assert counter == 1
    assert isinstance(mk, bytes)
    assert state.epoch == 1
    assert 1 in state.kdfchains
    assert state.kdfchains[0].send is None
    assert trace["new_cks"] is not None
    assert trace["new_ckr"] is not None
    assert trace["scka_output_key"] == b"ok-epoch-1"
    assert trace["raw_ss"] == b"raw-ss"


def test_scka_ratchet_send_key_rejects_unexpected_output_epoch(monkeypatch: pytest.MonkeyPatch):
    state, _ = _bootstrap_states()

    def fake_send(_state):
        return SckaSendResult(
            msg=_msg(epoch=2),
            sending_epoch=1,
            output_key=SckaOutputKey(epoch=3, key=b"bad"),
        )

    monkeypatch.setattr(logic, "SCKASend", fake_send)

    with pytest.raises(ValueError, match="Unexpected SPQR key epoch during send"):
        logic.SCKARatchetSendKey(state)


def test_scka_ratchet_receive_key_uses_precomputed_skipped_key(monkeypatch: pytest.MonkeyPatch):
    state, _ = _bootstrap_states()
    state.MKSKIPPED = {0: {5: b"mk-from-cache"}}

    def fake_receive(_state, _msg_obj):
        return SckaReceiveResult(receiving_epoch=0, output_key=None)

    monkeypatch.setattr(logic, "SCKAReceive", fake_receive)

    header = SpqrHeader(msg=_msg(epoch=1), n=5)
    mk, trace = logic.SCKARatchetReceiveKey(state, header)

    assert mk == b"mk-from-cache"
    assert trace["used_skipped_key"] is True
    assert 0 not in state.MKSKIPPED


def test_scka_ratchet_receive_key_updates_epoch_when_output_key_present(monkeypatch: pytest.MonkeyPatch):
    state, _ = _bootstrap_states()

    def fake_receive(_state, _msg_obj):
        return SckaReceiveResult(
            receiving_epoch=0,
            output_key=SckaOutputKey(epoch=1, key=b"recv-ok-epoch-1"),
        )

    monkeypatch.setattr(logic, "SCKAReceive", fake_receive)

    header = SpqrHeader(msg=_msg(epoch=1), n=1)
    mk, trace = logic.SCKARatchetReceiveKey(state, header)

    assert isinstance(mk, bytes)
    assert state.epoch == 1
    assert 1 in state.kdfchains
    assert trace["used_skipped_key"] is False
    assert trace["new_cks"] is not None
    assert trace["new_ckr"] is not None


def test_authenticator_detects_tampered_header_mac():
    auth = logic.Authenticator.Init(epoch=1, key=b"auth-key")
    hdr = b"H" * logic.HEADER_SIZE
    mac = logic.Authenticator.MacHdr(auth, 1, hdr)

    with pytest.raises(ValueError, match="SPQR header MAC verification failed"):
        logic.Authenticator.VfyHdr(auth, 1, hdr + b"x", mac)


def test_ratchet_send_and_receive_require_scka_state():
    state, _ = _bootstrap_states()
    state.scka_state = None

    with pytest.raises(ValueError, match="SPQR state has no SCKA state"):
        logic.SCKARatchetSendKey(state)

    header = SpqrHeader(msg=_msg(epoch=1), n=1)
    with pytest.raises(ValueError, match="SPQR state has no SCKA state"):
        logic.SCKARatchetReceiveKey(state, header)
