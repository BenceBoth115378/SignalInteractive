from __future__ import annotations

import hashlib
import itertools
import sys
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from components.data_classes import (   # noqa: E402
    DHKeyPair,
    DoubleRatchetState,
    DRHeader,
    KeyEvent,
    MessageState,
    LimitedSkippedKeys,
)
from modules.messaging.double_ratchet import logic  # noqa: E402
from modules.messaging.double_ratchet.attacker_dashboard.view import (  # noqa: E402
    build_attacker_dashboard,
    collect_attacker_secret_options,
    get_attacker_analysis,
)
from modules.messaging.double_ratchet.key_history import initialize_key_history  # noqa: E402


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

    def fake_header(dh_pair: DHKeyPair, pn: int, n: int) -> DRHeader:
        return DRHeader(dh=dh_pair.public, pn=pn, n=n)

    def fake_concat(ad: bytes, header: DRHeader) -> bytes:
        if ad is None:
            ad = b""
        payload = {"dh": header.dh, "pn": header.pn, "n": header.n}
        return ad + b"|" + str(payload).encode("utf-8")

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


def _bootstrap_session() -> DoubleRatchetState:
    session = DoubleRatchetState()
    shared_secret = hashlib.sha256(b"attacker-test-shared-secret").digest()
    bob_spk_key_pair = logic.ext.GENERATE_DH()
    logic.initialize_session_from_x3dh(session, shared_secret, bob_spk_key_pair)
    initialize_key_history(session)
    return session


def _add_send_history(session: DoubleRatchetState, seq_id: int, header: DRHeader, chain_key: bytes) -> None:
    session.initializer.key_history.add_cks_event(
        KeyEvent(
            key_type="CK",
            key_number=0,
            key_value=chain_key,
            created_at_step=f"send#{seq_id}",
            created_in_context="KDF_CK input on sending chain",
            party=session.initializer.name,
            direction="send",
            public_value=session.initializer.DHs.public if session.initializer.DHs is not None else "",
            start_n=header.n,
            used_for=[f"message #{seq_id}"],
        )
    )


def _add_receive_history(session: DoubleRatchetState, seq_id: int, header: DRHeader, chain_key: bytes, dh_changed: bool) -> None:
    session.responder.key_history.add_ckr_event(
        KeyEvent(
            key_type="CK",
            key_number=0,
            key_value=chain_key,
            created_at_step=f"receive#{seq_id}",
            created_in_context="Receive chain key (KDF_CK input)",
            party=session.responder.name,
            direction="recv",
            remote_public=header.dh,
            start_n=header.n,
            used_for=[f"message #{seq_id}"],
        )
    )
    if dh_changed and session.responder.DHs is not None:
        session.responder.key_history.add_dh_event(
            KeyEvent(
                key_type="DH",
                key_number=0,
                key_value=session.responder.DHs.private,
                public_value=session.responder.DHs.public,
                created_at_step=f"receive#{seq_id}",
                created_in_context="DH ratchet generated a new local key pair during receive",
                party=session.responder.name,
                remote_public=header.dh,
                start_send_n=session.responder.Ns,
                start_recv_n=session.responder.Nr,
                used_for=[f"after receiving message #{seq_id}"],
            )
        )


def _append_message(session: DoubleRatchetState, plaintext: bytes, ad: bytes, seq_id: int) -> None:
    before_dhs_public = session.responder.DHs.public if session.responder.DHs is not None else ""
    before_cks = session.initializer.CKs

    header, ciphertext, mk = logic.RatchetEncrypt(session.initializer, plaintext, ad)
    trace: dict[str, object] = {}
    receive_mk = logic.RatchetReceiveKey(session.responder, header, trace=trace)
    decrypted = logic.ext.DECRYPT(receive_mk, ciphertext, logic.ext.CONCAT(ad, header))

    session.message_log.append(
        MessageState(
            sender=session.initializer.name,
            receiver=session.responder.name,
            message_key=mk,
            cipher=ciphertext,
            plaintext=decrypted,
            header=header,
            seq_id=seq_id,
        )
    )

    if isinstance(before_cks, bytes):
        _add_send_history(session, seq_id, header, before_cks)

    ckr_before_kdf_ck = trace.get("ckr_before_kdf_ck")
    if isinstance(ckr_before_kdf_ck, bytes):
        _add_receive_history(
            session,
            seq_id,
            header,
            ckr_before_kdf_ck,
            session.responder.DHs.public != before_dhs_public,
        )


def _build_session_with_history(message_count: int) -> DoubleRatchetState:
    session = _bootstrap_session()
    ad = b"attacker-dashboard-ad"

    for seq_id in range(1, message_count + 1):
        _append_message(session, f"message-{seq_id}".encode("utf-8"), ad, seq_id)

    return session


def _find_option(options: list[dict[str, object]], **criteria) -> dict[str, object]:
    for option in options:
        if all(option.get(key) == value for key, value in criteria.items()):
            return option
    raise AssertionError(f"No option matched criteria: {criteria}")


def _flatten_controls(control):
    yield control
    content = getattr(control, "content", None)
    if content is not None:
        yield from _flatten_controls(content)
    for child in getattr(control, "controls", []) or []:
        yield from _flatten_controls(child)


def test_collect_attacker_secret_options_one_message():
    session = _bootstrap_session()

    ad = b"ad"
    header, ciphertext, mk = logic.RatchetEncrypt(session.initializer, b"hello", ad)
    receive_mk = logic.RatchetReceiveKey(session.responder, header)
    plaintext = logic.ext.DECRYPT(receive_mk, ciphertext, logic.ext.CONCAT(ad, header))

    session.message_log.append(
        type("M", (), {"seq_id": 1, "header": header, "cipher": ciphertext, "plaintext": plaintext, "message_key": mk, "sender": "Alice", "receiver": "Bob"})()
    )

    options = collect_attacker_secret_options(session)

    assert any(o for o in options if o["kind"] == "mk" and o.get("seq_id") == 1)
    assert any(o for o in options if o["kind"] in {"cks", "ckr"})
    assert any(o for o in options if o["kind"] == "rk")


def test_attacker_analysis_decrypts_when_message_mk_compromised():
    session = _bootstrap_session()

    ad = b"ad"
    # create two messages
    for i in (1, 2):
        header, ciphertext, mk = logic.RatchetEncrypt(session.initializer, f"m{i}".encode("utf-8"), ad)
        recv_mk = logic.RatchetReceiveKey(session.responder, header)
        plaintext = logic.ext.DECRYPT(recv_mk, ciphertext, logic.ext.CONCAT(ad, header))
        session.message_log.append(
            type("M", (), {"seq_id": i, "header": header, "cipher": ciphertext, "plaintext": plaintext, "message_key": mk, "sender": "Alice", "receiver": "Bob"})()
        )

    options = collect_attacker_secret_options(session)
    mk_option = next(o for o in options if o["kind"] == "mk" and o.get("seq_id") == 2)
    compromised = {str(mk_option["id"]): dict(mk_option)}

    analysis = get_attacker_analysis(session, [], compromised, ad)

    decryptables = [r for r in analysis if r["decryptable"]]
    assert any(int(r["id"]) == 2 for r in decryptables)
    found = next(r for r in decryptables if int(r["id"]) == 2)
    assert found["plaintext"] == "m2"


# --- Edge-case tests ---

def test_limited_skipped_keys_capacity():
    ls = LimitedSkippedKeys(max_items=3)
    ls[("a", 1)] = b"k1"
    ls[("b", 2)] = b"k2"
    ls.update({("c", 3): b"k3"})

    with pytest.raises(ValueError):
        ls[("d", 4)] = b"k4"


def test_decrypt_ignores_empty_mk_and_invalid_ck_entries():
    session = _bootstrap_session()
    ad = b"ad"

    # Produce a single message
    header, ciphertext, mk = logic.RatchetEncrypt(session.initializer, b"hello", ad)
    recv_mk = logic.RatchetReceiveKey(session.responder, header)
    plaintext = logic.ext.DECRYPT(recv_mk, ciphertext, logic.ext.CONCAT(ad, header))

    session.message_log.append(
        type("M", (), {"seq_id": 1, "header": header, "cipher": ciphertext, "plaintext": plaintext, "message_key": mk, "sender": "Alice", "receiver": "Bob"})()
    )

    options = collect_attacker_secret_options(session)

    # mk empty should be ignored
    mk_option = next(o for o in options if o["kind"] == "mk")
    empty_mk = dict(mk_option)
    empty_mk["value"] = b""

    # ck with missing public/start_n should be ignored
    ck_option = next(o for o in options if o.get("kind") in {"cks", "ckr"})
    bad_ck = dict(ck_option)
    bad_ck["public"] = ""
    bad_ck.pop("start_n", None)

    compromised = {"empty_mk": empty_mk, "bad_ck": bad_ck}
    analysis = get_attacker_analysis(session, [], compromised, ad)

    assert all(not r["decryptable"] for r in analysis)


def test_pending_message_with_invalid_header_ignored():
    session = _bootstrap_session()

    pending = [{"id": 1, "header": None, "cipher": b"", "plaintext": b"", "sender": "Alice", "receiver": "Bob"}]
    analysis = get_attacker_analysis(session, pending, {}, b"")

    assert all(not r["decryptable"] for r in analysis)


def test_ck_wrong_direction_does_not_decrypt():
    session = _bootstrap_session()
    ad = b"ad"

    # create two messages so start_n alignment is clear
    for i in (1, 2):
        header, ciphertext, mk = logic.RatchetEncrypt(session.initializer, f"m{i}".encode("utf-8"), ad)
        recv_mk = logic.RatchetReceiveKey(session.responder, header)
        plaintext = logic.ext.DECRYPT(recv_mk, ciphertext, logic.ext.CONCAT(ad, header))
        session.message_log.append(
            type("M", (), {"seq_id": i, "header": header, "cipher": ciphertext, "plaintext": plaintext, "message_key": mk, "sender": "Alice", "receiver": "Bob"})()
        )

    options = collect_attacker_secret_options(session)
    # pick a sending CK (CKs) for Alice but mark it as recv direction incorrectly
    cks = next(o for o in options if o.get("kind") in {"cks", "ck"} and o.get("party") == session.initializer.name)
    bad_ck = dict(cks)
    bad_ck["direction"] = "recv"
    compromised = {str(bad_ck["id"]): bad_ck}

    analysis = get_attacker_analysis(session, [], compromised, ad)
    assert all(not r["decryptable"] for r in analysis)

@pytest.mark.parametrize("message_count", [100, 1000, 1200])
def test_collect_attacker_secret_options_scales_with_large_sessions(message_count: int):
    session = _build_session_with_history(message_count)

    options = collect_attacker_secret_options(session)

    assert len([item for item in options if item["kind"] == "mk"]) == message_count
    assert len([item for item in options if item["kind"] == "cks"]) == message_count + 1
    assert len([item for item in options if item["kind"] == "ckr"]) == message_count
    assert len([item for item in options if item["kind"] == "rk"]) == 2
    assert len([item for item in options if item["kind"] == "dh_private"]) == 3
    assert len(options) == (message_count * 3) + 6
    assert any(item["id"] == f"msg:{message_count}:mk" for item in options)


@pytest.mark.parametrize(
    ("selection_kind", "selection_filter", "expected_ids", "expected_source_fragment"),
    [
        (
            "mk",
            {"kind": "mk", "seq_id": 2},
            [2],
            "MK#2",
        ),
        (
            "cks",
            {"kind": "cks", "direction": "send", "start_n": 1},
            [4, 3, 2],
            "CKs#",
        ),
        (
            "rk_dh",
            {"kind": "rk", "party": "Bob"},
            [],
            "iterative DH compromise",
        ),
    ],
)
def test_get_attacker_analysis_decrypts_with_mk_ck_and_rk_dh_compromises(
    selection_kind: str,
    selection_filter: dict[str, object],
    expected_ids: list[int],
    expected_source_fragment: str,
):
    session = _build_session_with_history(4)
    options = collect_attacker_secret_options(session)

    compromised_secrets: dict[str, dict[str, object]] = {}

    if selection_kind == "mk":
        selected = _find_option(options, **selection_filter)
        compromised_secrets[str(selected["id"])] = dict(selected)
    elif selection_kind == "cks":
        selected = _find_option(options, **selection_filter)
        compromised_secrets[str(selected["id"])] = dict(selected)
    else:
        rk_secret = _find_option(options, kind="rk", party="Bob")
        dh_secret = _find_option(options, kind="dh_private", party="Bob", start_recv_n=1)
        compromised_secrets[str(rk_secret["id"])] = dict(rk_secret)
        compromised_secrets[str(dh_secret["id"])] = dict(dh_secret)

    analysis = get_attacker_analysis(session, [], compromised_secrets, b"attacker-dashboard-ad")

    decryptable_ids = [item["id"] for item in analysis if item["decryptable"]]
    assert decryptable_ids == expected_ids

    if expected_ids:
        if selection_kind != "rk_dh":
            assert all(item["source"] for item in analysis if item["decryptable"])
            assert expected_source_fragment in next(item["source"] for item in analysis if item["decryptable"])
        else:
            assert all(not item["decryptable"] for item in analysis)

    if selection_kind == "mk":
        result = next(item for item in analysis if item["id"] == 2)
        assert result["usage"][0]["kind"] == "mk"
        assert result["plaintext"] == "message-2"
    elif selection_kind == "cks":
        result = next(item for item in analysis if item["id"] == 4)
        assert result["usage"][0]["kind"] == "ck"
        assert result["usage"][0]["direction"] == "send"
    elif selection_kind == "rk_dh" and expected_ids:
        result = next(item for item in analysis if item["id"] == 4)
        assert result["usage"][0]["kind"] == "derived_ck"
        assert result["usage"][0]["party"] == "Bob"


def test_build_attacker_dashboard_marks_implied_mirror_chain_key_and_message_key():
    session = _build_session_with_history(3)
    options = collect_attacker_secret_options(session)
    selected = _find_option(options, kind="cks", direction="send", start_n=1)
    compromised_secrets = {str(selected["id"]): dict(selected)}

    page = SimpleNamespace(update=lambda: None)
    dashboard = build_attacker_dashboard(
        page,
        session,
        [],
        compromised_secrets,
        lambda _value: None,
        lambda: None,
        b"attacker-dashboard-ad",
    )

    controls = list(_flatten_controls(dashboard))
    labeled_containers = [
        control
        for control in controls
        if isinstance(control, ft.Container)
        and isinstance(getattr(control, "content", None), ft.Checkbox)
    ]

    bob_ckr = next(container for container in labeled_containers if container.content.label == "CKr#2")
    message_mk = next(container for container in labeled_containers if container.content.label == "MK#2")

    assert bob_ckr.content.value is False
    assert message_mk.content.value is False
    assert bob_ckr.bgcolor == ft.Colors.AMBER_50
    assert message_mk.bgcolor == ft.Colors.AMBER_50