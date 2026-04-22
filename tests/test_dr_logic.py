from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from components.data_classes import DHKeyPair, DoubleRatchetState, Header, PartyState  # noqa: E402
from modules.messaging.double_ratchet import logic  # noqa: E402


@pytest.fixture(autouse=True)
def deterministic_crypto(monkeypatch: pytest.MonkeyPatch):
    pair_ids = itertools.count(1)
    private_by_public: dict[str, str] = {}

    def fake_generate_dh() -> DHKeyPair:
        index = next(pair_ids)
        private_hex = f"{index:064x}"
        public_hex = f"{index + 1000:064x}"
        private_by_public[public_hex] = private_hex
        return DHKeyPair(private=private_hex, public=public_hex)

    def fake_dh(dh_pair, dh_pub: str) -> bytes:
        if isinstance(dh_pair, dict):
            private_hex = dh_pair["private"]
        else:
            private_hex = dh_pair.private

        peer_private_hex = private_by_public.get(dh_pub, dh_pub)
        shared_parts = sorted([private_hex, peer_private_hex])
        return hashlib.sha256("|".join(shared_parts).encode("utf-8")).digest()

    def fake_kdf_rk(rk: bytes, dh_out: bytes) -> tuple[bytes, bytes]:
        material = rk + b"|" + dh_out
        return (
            hashlib.sha256(material + b"|root").digest(),
            hashlib.sha256(material + b"|chain").digest(),
        )

    def fake_kdf_ck(ck: bytes) -> tuple[bytes, bytes]:
        next_ck = hashlib.sha256(ck + b"|next").digest()
        mk = hashlib.sha256(ck + b"|msg").digest()
        return next_ck, mk

    def fake_header(dh_pair: DHKeyPair, pn: int, n: int) -> Header:
        return Header(dh=dh_pair.public, pn=pn, n=n)

    def fake_concat(ad: bytes, header: Header) -> bytes:
        if ad is None:
            ad = b""
        payload = {"dh": header.dh, "pn": header.pn, "n": header.n}
        return ad + b"|" + json.dumps(payload, sort_keys=True).encode("utf-8")

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

    monkeypatch.setattr(logic.ext, "GENERATE_DH", fake_generate_dh)
    monkeypatch.setattr(logic.ext, "DH", fake_dh)
    monkeypatch.setattr(logic.ext, "KDF_RK", fake_kdf_rk)
    monkeypatch.setattr(logic.ext, "KDF_CK", fake_kdf_ck)
    monkeypatch.setattr(logic.ext, "HEADER", fake_header)
    monkeypatch.setattr(logic.ext, "CONCAT", fake_concat)
    monkeypatch.setattr(logic.ext, "ENCRYPT", fake_encrypt)
    monkeypatch.setattr(logic.ext, "DECRYPT", fake_decrypt)


def _bootstrap_session() -> tuple[DoubleRatchetState, PartyState, PartyState, bytes]:
    session = DoubleRatchetState()
    shared_secret = hashlib.sha256(b"fixed-shared-secret").digest()
    bob_spk_key_pair = logic.ext.GENERATE_DH()
    logic.initialize_session_from_x3dh(session, shared_secret, bob_spk_key_pair)
    return session, session.initializer, session.responder, shared_secret


def _decrypt_with_key(mk: bytes, header: Header, ciphertext: bytes, ad: bytes) -> bytes:
    return logic.ext.DECRYPT(mk, ciphertext, logic.ext.CONCAT(ad, header))


def test_initialize_session_from_x3dh_sets_expected_initial_fields():
    _, alice, bob, shared_secret = _bootstrap_session()

    assert alice.DHs is not None
    assert bob.DHs is not None
    assert alice.DHr == bob.DHs.public
    assert bob.DHr is None
    assert alice.CKs is not None
    assert alice.CKr is None
    assert bob.CKs is None
    assert bob.CKr is None
    assert bob.RK == shared_secret


def test_initialize_session_allows_end_to_end_send_receive():
    session = DoubleRatchetState()
    logic.initialize_session(session)
    alice = session.initializer
    bob = session.responder

    ad = b"session-ad"
    plaintext = b"hello from initialize_session"
    header, ciphertext, _ = logic.RatchetEncrypt(alice, plaintext, ad)
    decrypted = logic.RatchetDecrypt(bob, header, ciphertext, ad)

    assert decrypted == plaintext
    assert alice.Ns == 1
    assert bob.Nr == 1


def test_in_order_messages_decrypt_successfully():
    _, alice, bob, _ = _bootstrap_session()
    ad = b"chat-ad"

    payloads = [b"m0", b"m1", b"m2"]
    envelopes = [logic.RatchetEncrypt(alice, payload, ad) for payload in payloads]

    decrypted = [logic.RatchetDecrypt(bob, header, ciphertext, ad) for header, ciphertext, _ in envelopes]

    assert decrypted == payloads
    assert alice.Ns == 3
    assert bob.Nr == 3
    assert len(bob.MKSKIPPED) == 0


def test_out_of_order_messages_use_and_consume_skipped_keys():
    _, alice, bob, _ = _bootstrap_session()
    ad = b"chat-ad"

    m0 = logic.RatchetEncrypt(alice, b"message-0", ad)
    m1 = logic.RatchetEncrypt(alice, b"message-1", ad)
    m2 = logic.RatchetEncrypt(alice, b"message-2", ad)

    header2, cipher2, _ = m2
    header0, cipher0, _ = m0
    header1, cipher1, _ = m1

    assert logic.RatchetDecrypt(bob, header2, cipher2, ad) == b"message-2"
    assert len(bob.MKSKIPPED) == 2

    trace0: dict[str, object] = {}
    mk0 = logic.RatchetReceiveKey(bob, header0, trace=trace0)
    assert _decrypt_with_key(mk0, header0, cipher0, ad) == b"message-0"
    assert trace0["used_skipped_mk"] is True
    assert trace0["ckr_before_kdf_ck"] is None
    assert trace0["ckr_after_double_ratchet"] is None
    assert len(bob.MKSKIPPED) == 1

    trace1: dict[str, object] = {}
    mk1 = logic.RatchetReceiveKey(bob, header1, trace=trace1)
    assert _decrypt_with_key(mk1, header1, cipher1, ad) == b"message-1"
    assert trace1["used_skipped_mk"] is True
    assert len(bob.MKSKIPPED) == 0


def test_receive_trace_reports_double_ratchet_and_chain_key_inputs():
    _, alice, bob, _ = _bootstrap_session()
    ad = b"chat-ad"

    header, ciphertext, _ = logic.RatchetEncrypt(alice, b"first", ad)
    trace: dict[str, object] = {}
    mk = logic.RatchetReceiveKey(bob, header, trace=trace)

    assert _decrypt_with_key(mk, header, ciphertext, ad) == b"first"
    assert trace["used_skipped_mk"] is False
    assert isinstance(trace["ckr_after_double_ratchet"], bytes)
    assert trace["ckr_before_kdf_ck"] == trace["ckr_after_double_ratchet"]


def test_dh_ratchet_is_triggered_when_remote_dh_changes():
    _, alice, bob, _ = _bootstrap_session()
    ad = b"chat-ad"

    first_header, first_cipher, _ = logic.RatchetEncrypt(alice, b"alice->bob #0", ad)
    assert logic.RatchetDecrypt(bob, first_header, first_cipher, ad) == b"alice->bob #0"

    alice_old_dhs_public = alice.DHs.public if alice.DHs is not None else ""
    alice_ns_before_receive = alice.Ns
    bob_reply_header, bob_reply_cipher, _ = logic.RatchetEncrypt(bob, b"bob->alice #0", ad)

    assert logic.RatchetDecrypt(alice, bob_reply_header, bob_reply_cipher, ad) == b"bob->alice #0"
    assert alice.PN == alice_ns_before_receive
    assert alice.Ns == 0
    assert alice.Nr == 1
    assert alice.DHr == bob_reply_header.dh
    assert alice.DHs is not None
    assert alice.DHs.public != alice_old_dhs_public


def test_skip_message_keys_raises_when_skip_window_exceeded():
    state = PartyState(name="Bob")
    state.DHr = "peer-public"
    state.CKr = hashlib.sha256(b"seed-ckr").digest()
    state.Nr = 0

    with pytest.raises(ValueError, match="Too many skipped messages"):
        logic.SkipMessageKeys(state, logic.ext.MAX_SKIP + 1)


def test_try_skipped_message_keys_returns_and_deletes_stored_key():
    state = PartyState(name="Bob")
    header = Header(dh="alice-dh", pn=0, n=7)
    state.MKSKIPPED[(header.dh, header.n)] = b"stored-message-key"

    mk = logic.TrySkippedMessageKeys(state, header)

    assert mk == b"stored-message-key"
    assert (header.dh, header.n) not in state.MKSKIPPED


def test_ratchet_encrypt_requires_initialized_dhs_keypair():
    state = PartyState(name="Alice")
    state.DHs = None
    state.CKs = hashlib.sha256(b"cks").digest()

    with pytest.raises(ValueError, match="DHs key pair is not initialized"):
        logic.RatchetEncrypt(state, b"payload", b"ad")
