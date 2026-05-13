"""Triple Ratchet messaging controller.

This module adapts the hybrid PQXDH-backed Triple Ratchet session to the
interactive messaging UI. It handles state import/export, lazy Bob bootstrap,
message send and receive flows, key-history tracking, and the optional step
visualization dialogs shown after each action.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from typing import Any

import flet as ft

from components.data_classes import (
    AuthenticatorState,
    BraidProtocolState,
    DecoderState,
    DHKeyPair,
    EncoderState,
    EpochKdfChains,
    KdfChainState,
    KeyEvent,
    KeyHistory,
    PartyState,
    PartyStateSnapshot,
    ReceiveStepVisualizationSnapshot,
    SckaOutputKey,
    SckaReceiveResult,
    SckaSendResult,
    SpqrHeader,
    SpqrMessageType,
    SpqrRatchetState,
    SpqrSckaMessage,
    TripleRatchetHeader,
    TripleRatchetMessageState,
    TripleRatchetPartyState,
    TripleRatchetPartyStateSnapshot,
    TripleRatchetReceiveSnapshot,
    TripleRatchetSendSnapshot,
    TripleRatchetSessionState,
)
from modules.messaging.messaging_base_module import MessagingBaseModule, decode_nested, encode_nested
from modules.messaging.messaging_base_view import (
    build_module_layout,
    build_perspective_selector,
    show_initial_bootstrap_warning,
    show_warning_dialog,
    tail_hex,
)
from modules.messaging.spqr.logic import (
    Ct1Acknowledged,
    Ct1Received,
    Ct1Sampled,
    Ct2Sampled,
    EkReceivedCt1Sampled,
    EkSentCt1Received,
    HeaderReceived,
    HeaderSent,
    KeysSampled,
    KeysUnsampled,
    NoHeaderReceived,
    RatchetInitBobSCKA,
)
from modules.messaging.triple_ratchet.key_history import (
    initialize_key_history,
    track_keys_from_receive_step,
    track_keys_from_send_step,
)
from modules.messaging.triple_ratchet.logic import (
    TripleRatchetDecrypt,
    TripleRatchetEncrypt,
    initialize_session_from_pqxdh,
    KDF_TR_SPLIT,
    RatchetInitBobTripleRatchet,
)
from modules.messaging.triple_ratchet.step_visualization import (
    show_alice_pqxdh_bootstrap_visualization_dialog,
    show_bob_pqxdh_bootstrap_visualization_dialog,
    show_triple_ratchet_receive_step_dialog,
    show_triple_ratchet_send_step_dialog,
)
from modules.messaging.triple_ratchet.view import build_visual
from modules.key_exchange.key_exchange_base_logic import alice_calculates_associated_data
from modules.key_exchange.pqxdh.logic import (
    alice_generates_ek_and_derives_sk,
    alice_sends_initial_message,
    alice_verifies_bundle_signature,
    generate_alice_registration_material,
    new_state as new_pqxdh_state,
    request_bob_bundle_for_alice,
    upload_alice_initial_bundle,
)


def _class_map() -> dict[str, type]:
    """Return the dataclass/class map used when decoding nested module state."""

    return {
        "SpqrMessageType": SpqrMessageType,
        "SpqrSckaMessage": SpqrSckaMessage,
        "SckaOutputKey": SckaOutputKey,
        "KeyEvent": KeyEvent,
        "AuthenticatorState": AuthenticatorState,
        "EncoderState": EncoderState,
        "DecoderState": DecoderState,
        "BraidProtocolState": BraidProtocolState,
        "KdfChainState": KdfChainState,
        "EpochKdfChains": EpochKdfChains,
        "SpqrHeader": SpqrHeader,
        "SpqrRatchetState": SpqrRatchetState,
        "SckaSendResult": SckaSendResult,
        "SckaReceiveResult": SckaReceiveResult,
        "KeyHistory": KeyHistory,
        "KeysUnsampled": KeysUnsampled,
        "KeysSampled": KeysSampled,
        "HeaderSent": HeaderSent,
        "Ct1Received": Ct1Received,
        "EkSentCt1Received": EkSentCt1Received,
        "NoHeaderReceived": NoHeaderReceived,
        "HeaderReceived": HeaderReceived,
        "Ct1Sampled": Ct1Sampled,
        "EkReceivedCt1Sampled": EkReceivedCt1Sampled,
        "Ct1Acknowledged": Ct1Acknowledged,
        "Ct2Sampled": Ct2Sampled,
    }


def _snapshot_dr(state: PartyState) -> PartyStateSnapshot:
    """Capture a lightweight snapshot of the embedded Double Ratchet state."""

    return PartyStateSnapshot(
        DHs_public=state.DHs.public if state.DHs else "",
        DHs_private=state.DHs.private if state.DHs else "",
        DHr=state.DHr or "",
        RK=state.RK,
        CKs=state.CKs,
        CKr=state.CKr,
        Ns=state.Ns,
        Nr=state.Nr,
        PN=state.PN,
    )


def _node_snapshot(node: object | None) -> dict[str, Any]:
    """Recursively snapshot a dataclass node for visualization and persistence."""

    if not is_dataclass(node):
        return {}

    snapshot: dict[str, Any] = {"node": type(node).__name__}
    for field in fields(node):
        value = getattr(node, field.name)
        if is_dataclass(value):
            snapshot[field.name] = _node_snapshot(value)
        elif isinstance(value, list):
            snapshot[field.name] = [
                _node_snapshot(item) if is_dataclass(item) else item
                for item in value
            ]
        else:
            snapshot[field.name] = value
    return snapshot


def _snapshot_spqr(spqr: SpqrRatchetState | None) -> dict[str, Any]:
    """Capture the current SPQR state in a serializable snapshot form."""

    if spqr is None:
        return {"state": "Uninitialized", "epoch": 0, "direction": "", "rk_tail": "", "send_ck_tail": "", "recv_ck_tail": ""}
    chains = spqr.kdfchains.get(spqr.epoch)
    send_ck = chains.send.CK if chains is not None and chains.send is not None else None
    recv_ck = chains.receive.CK if chains is not None and chains.receive is not None else None
    node = spqr.scka_state.node if spqr.scka_state is not None else None
    return {
        "state": type(node).__name__ if node is not None else "Unknown",
        "epoch": spqr.epoch,
        "direction": spqr.direction,
        "rk": spqr.RK,
        "rk_tail": tail_hex(spqr.RK),
        "send_ck": send_ck,
        "send_ck_tail": tail_hex(send_ck),
        "recv_ck": recv_ck,
        "recv_ck_tail": tail_hex(recv_ck),
        "scka_node": _node_snapshot(node),
    }


def _snapshot_party(party: TripleRatchetPartyState) -> TripleRatchetPartyStateSnapshot:
    """Combine the DR and SPQR snapshots for a Triple Ratchet party."""

    dr = _snapshot_dr(party.dr)
    spqr_snap = _snapshot_spqr(party.spqr)
    return TripleRatchetPartyStateSnapshot(
        dr_dhs_public=dr.DHs_public,
        dr_dhs_private=dr.DHs_private,
        dr_dhr=dr.DHr,
        dr_rk=dr.RK,
        dr_cks=dr.CKs,
        dr_ckr=dr.CKr,
        dr_ns=dr.Ns,
        dr_nr=dr.Nr,
        dr_pn=dr.PN,
        spqr_rk=spqr_snap.get("rk"),
        spqr_epoch=spqr_snap.get("epoch", 0),
        spqr_direction=spqr_snap.get("direction", ""),
        spqr_state_name=spqr_snap.get("state", ""),
        spqr_send_ck=spqr_snap.get("send_ck"),
        spqr_recv_ck=spqr_snap.get("recv_ck"),
        spqr_scka_node=spqr_snap.get("scka_node", {}),
        spqr_snapshot=spqr_snap,
    )


def _encode_bytes(value: Any) -> Any:
    """Encode bytes as a tagged hex payload for JSON-compatible storage."""

    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    return value


def _decode_bytes(value: Any) -> Any:
    """Decode a tagged hex payload back into bytes when possible."""

    if isinstance(value, dict) and len(value) == 1 and isinstance(value.get("__bytes__"), str):
        try:
            return bytes.fromhex(value["__bytes__"])
        except ValueError:
            return b""
    return value


def _serialize_dr_party(state: PartyState) -> dict:
    """Serialize a Double Ratchet party state for persistence."""

    skipped = [
        {"dh": dh, "n": n, "mk": _encode_bytes(mk)}
        for (dh, n), mk in state.MKSKIPPED.items()
    ]
    return {
        "name": state.name,
        "DHs": asdict(state.DHs) if state.DHs is not None else None,
        "DHr": state.DHr,
        "RK": _encode_bytes(state.RK),
        "CKs": _encode_bytes(state.CKs),
        "CKr": _encode_bytes(state.CKr),
        "Ns": state.Ns,
        "Nr": state.Nr,
        "PN": state.PN,
        "MKSKIPPED": skipped,
        "key_history": encode_nested(asdict(state.key_history)),
    }


def _deserialize_key_event(data: Any) -> KeyEvent | None:
    """Rebuild a KeyEvent instance from serialized nested state."""

    if not isinstance(data, dict):
        return None
    used_for_raw = data.get("used_for", [])
    used_for = [i for i in used_for_raw if isinstance(i, str)] if isinstance(used_for_raw, list) else []
    return KeyEvent(
        key_type=data.get("key_type", "") if isinstance(data.get("key_type"), str) else "",
        key_number=data.get("key_number", 0) if isinstance(data.get("key_number"), int) else 0,
        key_value=decode_nested(data.get("key_value"), {}),
        created_at_step=data.get("created_at_step", "") if isinstance(data.get("created_at_step"), str) else "",
        created_in_context=data.get("created_in_context", "") if isinstance(data.get("created_in_context"), str) else "",
        public_value=data.get("public_value", "") if isinstance(data.get("public_value"), str) else "",
        party=data.get("party", "") if isinstance(data.get("party"), str) else "",
        direction=data.get("direction", "") if isinstance(data.get("direction"), str) else "",
        remote_public=data.get("remote_public", "") if isinstance(data.get("remote_public"), str) else "",
        start_send_n=data.get("start_send_n", 0) if isinstance(data.get("start_send_n"), int) else 0,
        start_recv_n=data.get("start_recv_n", 0) if isinstance(data.get("start_recv_n"), int) else 0,
        start_n=data.get("start_n", 0) if isinstance(data.get("start_n"), int) else 0,
        used_for=used_for,
    )


def _deserialize_key_history(data: Any) -> KeyHistory:
    """Rebuild a KeyHistory object from serialized nested state."""

    history = KeyHistory()
    if not isinstance(data, dict):
        return history

    def _events(name: str) -> list[KeyEvent]:
        raw = data.get(name, [])
        if not isinstance(raw, list):
            return []
        return [e for e in (_deserialize_key_event(r) for r in raw) if e is not None]

    history.rk_events = _events("rk_events")
    history.cks_events = _events("cks_events")
    history.ckr_events = _events("ckr_events")
    history.dh_events = _events("dh_events")
    return history


def _deserialize_dr_party(data: dict, default_name: str) -> PartyState:
    """Rebuild a Double Ratchet party state from serialized module data."""

    skipped = {}
    for entry in data.get("MKSKIPPED", []):
        if not isinstance(entry, dict):
            continue
        dh = entry.get("dh")
        n = entry.get("n")
        if not isinstance(dh, str) or not isinstance(n, int):
            continue
        skipped[(dh, n)] = _decode_bytes(entry.get("mk"))

    return PartyState(
        name=data.get("name", default_name),
        DHs=data.get("DHs"),
        DHr=data.get("DHr", ""),
        RK=_decode_bytes(data.get("RK", b"RK0")),
        CKs=_decode_bytes(data.get("CKs")),
        CKr=_decode_bytes(data.get("CKr")),
        Ns=data.get("Ns", 0),
        Nr=data.get("Nr", 0),
        PN=data.get("PN", 0),
        MKSKIPPED=skipped,
        key_history=_deserialize_key_history(decode_nested(data.get("key_history", {}), {})),
    )


def _serialize_message(msg: TripleRatchetMessageState) -> dict:
    """Serialize a Triple Ratchet message for persistence."""

    header_dict = None
    if msg.header is not None:
        header_dict = {
            "dr": {"dh": msg.header.dr.dh, "pn": msg.header.dr.pn, "n": msg.header.dr.n},
            "spqr": {"msg": msg.header.spqr.msg.to_dict(), "n": msg.header.spqr.n},
        }
    return {
        "sender": msg.sender,
        "receiver": msg.receiver,
        "header": header_dict,
        "cipher": _encode_bytes(msg.cipher),
        "plaintext": _encode_bytes(msg.plaintext),
        "decrypted_by_receiver": _encode_bytes(msg.decrypted_by_receiver),
        "seq_id": msg.seq_id,
        "pqxdh_header": msg.pqxdh_header,
        "ec_mk": _encode_bytes(msg.ec_mk),
        "pq_mk": _encode_bytes(msg.pq_mk),
        "mk": _encode_bytes(msg.mk),
    }


def _deserialize_message(data: dict) -> TripleRatchetMessageState | None:
    """Rebuild a Triple Ratchet message from serialized module data."""

    from components.data_classes import DRHeader, SpqrSckaMessage, SpqrHeader, TripleRatchetHeader
    header = None
    raw_header = data.get("header")
    if isinstance(raw_header, dict):
        dr_raw = raw_header.get("dr")
        spqr_raw = raw_header.get("spqr")
        if isinstance(dr_raw, dict) and isinstance(spqr_raw, dict):
            dh = dr_raw.get("dh")
            pn = dr_raw.get("pn")
            n_dr = dr_raw.get("n")
            msg_raw = spqr_raw.get("msg")
            n_spqr = spqr_raw.get("n")
            if isinstance(dh, str) and isinstance(pn, int) and isinstance(n_dr, int) and isinstance(msg_raw, dict) and isinstance(n_spqr, int):
                dr_header = DRHeader(dh=dh, pn=pn, n=n_dr)
                spqr_msg = SpqrSckaMessage.from_dict(msg_raw)
                spqr_header = SpqrHeader(msg=spqr_msg, n=n_spqr)
                header = TripleRatchetHeader(dr=dr_header, spqr=spqr_header)

    plaintext = _decode_bytes(data.get("plaintext", b""))
    if not plaintext:
        plaintext = _decode_bytes(data.get("decrypted_by_receiver", b"")) or b""

    return TripleRatchetMessageState(
        sender=data.get("sender", ""),
        receiver=data.get("receiver", ""),
        header=header,
        cipher=_decode_bytes(data.get("cipher", b"")),
        plaintext=plaintext,
        decrypted_by_receiver=_decode_bytes(data.get("decrypted_by_receiver", b"")),
        seq_id=data.get("seq_id", 0),
        pqxdh_header=data.get("pqxdh_header") if isinstance(data.get("pqxdh_header"), dict) else None,
        ec_mk=_decode_bytes(data.get("ec_mk", b"")),
        pq_mk=_decode_bytes(data.get("pq_mk", b"")),
        mk=_decode_bytes(data.get("mk", b"")),
    )


class TripleRatchetModule(MessagingBaseModule):
    """Controller for the Triple Ratchet messaging demo.

    The module keeps the embedded PQXDH bootstrap, Double Ratchet, and SPQR
    state in sync with the messaging UI, supports persistence, and exposes the
    send/receive actions used by the interactive workspace.
    """

    def __init__(self) -> None:
        """Create a fresh Triple Ratchet controller with empty session state."""

        self.session = TripleRatchetSessionState()
        self.pending_messages: list[dict[str, Any]] = []
        self._next_pending_id = 1
        self._session_ad: bytes = b""
        self._pqxdh_bootstrap_payload: dict[str, Any] | None = None
        self._pqxdh_initial_header: dict[str, Any] | None = None
        self._pqxdh_shared_secret: bytes | None = None
        self._pqxdh_bob_spk_pair: DHKeyPair | None = None
        self._pqxdh_state_data: dict[str, Any] | None = None
        self._pqxdh_bob_initialized: bool = False
        self._pqxdh_alice_received_bob_reply: bool = False
        self._pending_show_alice_pqxdh_bootstrap: bool = True
        self._last_bob_bootstrap_info: dict[str, Any] | None = None
        self._initial_warning_shown: bool = False
        self._send_steps: dict[int, TripleRatchetSendSnapshot] = {}
        self._receive_steps: dict[int, TripleRatchetReceiveSnapshot] = {}
        self._reset_session()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _reset_session(self) -> None:
        """Clear all runtime state and return to a pristine session."""

        self.session = TripleRatchetSessionState(alice=None, bob=None, message_log=[])
        self._session_ad = b""
        self._pqxdh_bootstrap_payload = None
        self._pqxdh_initial_header = None
        self._pqxdh_shared_secret = None
        self._pqxdh_bob_spk_pair = None
        self._pqxdh_state_data = None
        self._pqxdh_bob_initialized = False
        self._pqxdh_alice_received_bob_reply = False
        self._pending_show_alice_pqxdh_bootstrap = True
        self._last_bob_bootstrap_info = None
        self.pending_messages = []
        self._next_pending_id = 1
        self._send_steps.clear()
        self._receive_steps.clear()

    def _apply_pqxdh_bootstrap_payload(self, payload: dict[str, Any]) -> bool:
        """Apply PQXDH bootstrap data when the embedding application provides it."""

        if not isinstance(payload, dict):
            return False

        # Accept both naming conventions from the two PQXDH bootstrap paths.
        sk_hex = payload.get("sk_hex") or payload.get("shared_secret_hex")
        ad_hex = payload.get("ad_hex") or payload.get("associated_data_hex")
        bob_spk_public = payload.get("bob_spk_public")
        bob_spk_private = payload.get("bob_spk_private")
        initial_header = payload.get("initial_header") if isinstance(payload.get("initial_header"), dict) else None

        if not all(isinstance(v, str) and v for v in [sk_hex, ad_hex, bob_spk_public, bob_spk_private]):
            return False

        sk = bytes.fromhex(sk_hex)
        ad = bytes.fromhex(ad_hex)
        bob_spk = DHKeyPair(private=bob_spk_private, public=bob_spk_public)

        self.session = initialize_session_from_pqxdh(sk, bob_spk)
        self._session_ad = ad
        self._pqxdh_bootstrap_payload = payload
        self._pqxdh_initial_header = initial_header
        self._pqxdh_shared_secret = sk
        self._pqxdh_bob_spk_pair = bob_spk
        self._pqxdh_bob_initialized = False
        self._pqxdh_alice_received_bob_reply = False
        self._pending_show_alice_pqxdh_bootstrap = True
        self._last_bob_bootstrap_info = None
        initialize_key_history(self.session)
        return True

    def _complete_bob_pqxdh_bootstrap(self) -> None:
        """Initialize Bob's embedded ratchets when his first message arrives."""

        if self.session.bob is not None or self.session.alice is None:
            return

        if self._pqxdh_shared_secret is None or self._pqxdh_bob_spk_pair is None:
            raise ValueError("Bob cannot complete PQXDH bootstrap because required state is missing.")

        # Split the shared secret the same way Alice did
        sk_dr, sk_spqr = KDF_TR_SPLIT(self._pqxdh_shared_secret)

        # Create and initialize Bob's states
        bob_dr = PartyState("Bob")
        bob_spqr = RatchetInitBobSCKA(sk_spqr)

        # Initialize Bob's DR state
        RatchetInitBobTripleRatchet(bob_dr, sk_dr, self._pqxdh_bob_spk_pair)

        # Create Bob's complete party state
        self.session.bob = TripleRatchetPartyState("Bob", bob_dr, bob_spqr)
        self._pqxdh_bob_initialized = True
        initialize_key_history(self.session)

    def _sync_bootstrap_from_app_state(self, app_state: Any) -> None:
        """Pull PQXDH bootstrap data from the hosting app or initialize locally."""

        if self.session.alice is not None:
            return

        # Prefer the DR-style bootstrap dict (set by PQXDH module) because it contains
        # the SPK pair needed to seed the embedded Double Ratchet.
        payload = getattr(app_state, "x3dh_to_dr_bootstrap", None)
        if isinstance(payload, dict) and payload.get("source") == "pqxdh":
            if self._apply_pqxdh_bootstrap_payload(payload):
                return

        # Fallback: generate fresh PQXDH keying material internally.
        self._reset_session_with_initializer()

    def _reset_session_with_initializer(self) -> None:
        """Build a self-contained PQXDH bootstrap when no external data is present."""

        pqxdh_state = new_pqxdh_state()
        generate_alice_registration_material(pqxdh_state)
        upload_alice_initial_bundle(pqxdh_state)
        request_bob_bundle_for_alice(pqxdh_state)
        alice_verifies_bundle_signature(pqxdh_state)
        alice_generates_ek_and_derives_sk(pqxdh_state)
        alice_calculates_associated_data(pqxdh_state)
        alice_sends_initial_message(pqxdh_state, "")

        derived = pqxdh_state.alice_derived if isinstance(pqxdh_state.alice_derived, dict) else None
        initial_message = pqxdh_state.initial_message if isinstance(pqxdh_state.initial_message, dict) else None
        initial_header = initial_message.get("header") if isinstance(initial_message, dict) and isinstance(initial_message.get("header"), dict) else None
        bob_local = pqxdh_state.bob_local if isinstance(pqxdh_state.bob_local, dict) else None
        bob_spk = bob_local.get("signed_prekey") if isinstance(bob_local, dict) and isinstance(bob_local.get("signed_prekey"), dict) else None

        if not isinstance(derived, dict) or not isinstance(bob_spk, dict):
            raise ValueError("Could not initialize Triple Ratchet because PQXDH bootstrap is incomplete.")

        shared_secret_hex = derived.get("shared_secret")
        associated_data_hex = derived.get("associated_data")
        bob_spk_public = bob_spk.get("public")
        bob_spk_private = bob_spk.get("private")
        if not all(isinstance(v, str) and v for v in [shared_secret_hex, associated_data_hex, bob_spk_public, bob_spk_private]):
            raise ValueError("Could not initialize Triple Ratchet because PQXDH output values are invalid.")

        payload = {
            "source": "pqxdh",
            "sk_hex": shared_secret_hex,
            "ad_hex": associated_data_hex,
            "bob_spk_public": bob_spk_public,
            "bob_spk_private": bob_spk_private,
            "initial_header": initial_header,
            "initial_message_json": json.dumps(initial_message, sort_keys=True) if isinstance(initial_message, dict) else "",
        }
        self._apply_pqxdh_bootstrap_payload(payload)
        self._pqxdh_state_data = asdict(pqxdh_state)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_party(self, name: str) -> TripleRatchetPartyState:
        """Return the requested party state or raise if it has not been initialized."""

        key = name.lower()
        if key == "alice":
            if self.session.alice is None:
                raise ValueError("Alice state is not initialized")
            return self.session.alice
        if key == "bob":
            if self.session.bob is None:
                raise ValueError("Bob state is not initialized")
            return self.session.bob
        raise ValueError(f"Unknown party: {name}")

    def _build_hint_message(self, sender: str) -> str:
        """Return a simple UI hint for the next message from the selected sender."""

        key = sender.lower()
        if key == "alice":
            return f"Alice message #{self._next_pending_id} to Bob"
        if key == "bob":
            return f"Bob message #{self._next_pending_id} to Alice"
        return ""

    # ------------------------------------------------------------------
    # Send / receive
    # ------------------------------------------------------------------

    def send_message(self, sender: str, plaintext: str, fallback_plaintext: str = "") -> dict[str, Any]:
        """Encrypt and queue a new Triple Ratchet message from the chosen sender."""

        sender_name = sender.capitalize()
        receiver_name = "Bob" if sender_name == "Alice" else "Alice"

        message_text = (plaintext or "").strip() or (fallback_plaintext or "").strip()
        if not message_text:
            raise ValueError("Message cannot be empty")

        party = self._get_party(sender_name)
        before = _snapshot_party(party)

        triple_header, cipher, ec_mk, pq_mk, mk, dr_trace, spqr_trace = TripleRatchetEncrypt(
            party.dr,
            party.spqr,
            message_text.encode("utf-8"),
            self._session_ad,
        )

        after = _snapshot_party(party)
        
        pending_id = self._next_pending_id
        pqxdh_header = self._pqxdh_initial_header if sender_name == "Alice" and not self._pqxdh_alice_received_bob_reply else None

        pending: dict[str, Any] = {
            "id": pending_id,
            "sender": sender_name,
            "receiver": receiver_name,
            "header": triple_header,
            "cipher": cipher,
            "plaintext": message_text.encode("utf-8"),
            "pqxdh_header": pqxdh_header,
        }
        self.pending_messages.append(pending)
        self._next_pending_id += 1

        snapshot = TripleRatchetSendSnapshot(
            sender=sender_name,
            receiver=receiver_name,
            plaintext=message_text.encode("utf-8"),
            header=triple_header,
            cipher=cipher,
            ec_mk=ec_mk,
            pq_mk=pq_mk,
            mk=mk,
            AD=self._session_ad,
            pending_id=pending_id,
            before=before,
            after=after,
            dr_trace=dr_trace,
            spqr_trace=spqr_trace,
            pqxdh_header=pqxdh_header,
        )
        self._send_steps[pending_id] = snapshot

        track_keys_from_send_step(party, sender_name, pending_id)

        return pending

    def receive_message(self, recipient: str, pending_id: int) -> TripleRatchetMessageState | None:
        """Decrypt a queued Triple Ratchet message for the chosen recipient."""

        target = recipient.capitalize()
        pending = next((item for item in self.pending_messages if item.get("id") == pending_id), None)
        if pending is None:
            return None
        if pending.get("receiver") != target:
            raise ValueError("Pending message receiver mismatch")

        pqxdh_header = pending.get("pqxdh_header") if isinstance(pending.get("pqxdh_header"), dict) else None
        was_pqxdh_bootstrapped = False

        # Initialize Bob on first message if recipient is Bob
        if target == "Bob" and self.session.bob is None:
            self._complete_bob_pqxdh_bootstrap()
            was_pqxdh_bootstrapped = True

        party = self._get_party(target)
        before = _snapshot_party(party)

        dr_header = pending["header"].dr
        plaintext, ec_mk, pq_mk, mk, dr_trace, spqr_trace = TripleRatchetDecrypt(
            party.dr,
            party.spqr,
            pending["header"],
            pending["cipher"],
            self._session_ad,
        )
        after = _snapshot_party(party)

        message = TripleRatchetMessageState(
            sender=str(pending["sender"]),
            receiver=str(pending["receiver"]),
            header=pending["header"],
            cipher=pending["cipher"],
            plaintext=pending.get("plaintext", b""),
            decrypted_by_receiver=plaintext,
            seq_id=pending_id,
            pqxdh_header=pqxdh_header,
            ec_mk=ec_mk,
            pq_mk=pq_mk,
            mk=mk,
        )
        self.session.message_log.append(message)
        self.pending_messages = [item for item in self.pending_messages if item.get("id") != pending_id]

        if pending["sender"] == "Bob" and target == "Alice":
            self._pqxdh_alice_received_bob_reply = True

        # Compute skip-ahead logic for DR visualization
        dh_ratchet_needed = dr_header.dh != before.dr_dhr
        if dh_ratchet_needed:
            ff_count = max(0, dr_header.n)
            ff_from_nr = 0
            ff_to_nr = dr_header.n
        else:
            ff_count = max(0, dr_header.n - before.dr_nr)
            ff_from_nr = before.dr_nr
            ff_to_nr = before.dr_nr + ff_count
        
        # Construct DR ReceiveStepVisualizationSnapshot
        dr_before_snap = PartyStateSnapshot(
            DHs_public=before.dr_dhs_public,
            DHs_private=before.dr_dhs_private,
            DHr=before.dr_dhr,
            RK=before.dr_rk,
            CKs=before.dr_cks,
            CKr=before.dr_ckr,
            Ns=before.dr_ns,
            Nr=before.dr_nr,
            PN=before.dr_pn,
        )
        dr_after_snap = PartyStateSnapshot(
            DHs_public=after.dr_dhs_public,
            DHs_private=after.dr_dhs_private,
            DHr=after.dr_dhr,
            RK=after.dr_rk,
            CKs=after.dr_cks,
            CKr=after.dr_ckr,
            Ns=after.dr_ns,
            Nr=after.dr_nr,
            PN=after.dr_pn,
        )
        dr_snapshot = ReceiveStepVisualizationSnapshot(
            sender=str(pending["sender"]),
            receiver=target,
            pending_id=pending_id,
            header=dr_header,
            cipher=pending["cipher"],
            mk=ec_mk,
            decrypted=plaintext,
            plaintext=pending.get("plaintext", b""),
            skipped_key_hit=False,
            dh_ratchet_needed=dh_ratchet_needed,
            fast_forward_count=ff_count,
            fast_forward_from_nr=ff_from_nr,
            fast_forward_to_nr=ff_to_nr,
            ckr_after_double_ratchet=dr_trace.get("ckr_after_double_ratchet"),
            ckr_before_kdf_ck=dr_trace.get("ckr_before_kdf_ck"),
            before=dr_before_snap,
            after=dr_after_snap,
            pqxdh_header=pqxdh_header,
            was_pqxdh_bootstrapped=was_pqxdh_bootstrapped,
        )

        snapshot = TripleRatchetReceiveSnapshot(
            sender=str(pending["sender"]),
            receiver=target,
            pending_id=pending_id,
            header=pending["header"],
            cipher=pending["cipher"],
            ec_mk=ec_mk,
            pq_mk=pq_mk,
            mk=mk,
            AD=self._session_ad,
            decrypted=plaintext,
            plaintext=pending.get("plaintext", b""),
            before=before,
            after=after,
            dr_trace=dr_trace,
            spqr_trace=spqr_trace,
            pqxdh_header=pqxdh_header,
            was_pqxdh_bootstrapped=was_pqxdh_bootstrapped,
            dr_snapshot=dr_snapshot,
        )
        self._receive_steps[pending_id] = snapshot

        track_keys_from_receive_step(party, target, pending_id)

        return message

    def _auto_receive_all_pending(self) -> tuple[list[int], list[str]]:
        """Process all pending messages when auto-receive is enabled."""

        processed: list[int] = []
        errors: list[str] = []
        for pending in list(self.pending_messages):
            pending_id = pending.get("id")
            recipient = pending.get("receiver")
            if not isinstance(pending_id, int) or not isinstance(recipient, str):
                continue
            try:
                result = self.receive_message(recipient, pending_id)
                if result is not None:
                    processed.append(pending_id)
            except ValueError as exc:
                errors.append(f"#{pending_id} {recipient}: {exc}")
        return processed, errors

    # ------------------------------------------------------------------
    # State export / import
    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        """Export the current Triple Ratchet session for persistence."""

        alice = self.session.alice
        bob = self.session.bob

        def _serialize_party(p: TripleRatchetPartyState | None) -> dict | None:
            if p is None:
                return None
            return {
                "name": p.name,
                "dr": _serialize_dr_party(p.dr),
                "spqr": encode_nested(p.spqr),
            }

        def _serialize_pending(item: dict) -> dict:
            header = item.get("header")
            header_dict = None
            if isinstance(header, TripleRatchetHeader):
                header_dict = {
                    "dr": {"dh": header.dr.dh, "pn": header.dr.pn, "n": header.dr.n},
                    "spqr": {"msg": header.spqr.msg.to_dict(), "n": header.spqr.n},
                }
            return {
                "id": item.get("id"),
                "sender": item.get("sender"),
                "receiver": item.get("receiver"),
                "header": header_dict,
                "cipher": _encode_bytes(item.get("cipher", b"")),
                "plaintext": _encode_bytes(item.get("plaintext", b"")),
                "pqxdh_header": item.get("pqxdh_header"),
            }

        return {
            "alice": _serialize_party(alice),
            "bob": _serialize_party(bob),
            "message_log": [_serialize_message(m) for m in self.session.message_log],
            "pending_messages": [_serialize_pending(p) for p in self.pending_messages],
            "next_pending_id": self._next_pending_id,
            "session_ad": _encode_bytes(self._session_ad),
            "pqxdh_bootstrap_payload": self._pqxdh_bootstrap_payload,
            "pqxdh_initial_header": self._pqxdh_initial_header,
            "pqxdh_shared_secret": _encode_bytes(self._pqxdh_shared_secret),
            "pqxdh_bob_spk_pair": asdict(self._pqxdh_bob_spk_pair) if self._pqxdh_bob_spk_pair else None,
            "pqxdh_state_data": self._pqxdh_state_data,
            "pqxdh_bob_initialized": self._pqxdh_bob_initialized,
            "pqxdh_alice_received_bob_reply": self._pqxdh_alice_received_bob_reply,
            "pending_show_alice_pqxdh_bootstrap": self._pending_show_alice_pqxdh_bootstrap,
            "last_bob_bootstrap_info": self._last_bob_bootstrap_info,
        }

    def import_state(self, data: dict) -> None:
        """Restore a Triple Ratchet session from persisted module data."""

        if not isinstance(data, dict):
            return

        cmap = _class_map()

        def _load_party(raw: Any, default_name: str) -> TripleRatchetPartyState | None:
            if not isinstance(raw, dict):
                return None
            dr_raw = raw.get("dr")
            spqr_raw = raw.get("spqr")
            if not isinstance(dr_raw, dict):
                return None
            dr = _deserialize_dr_party(dr_raw, default_name)
            spqr = decode_nested(spqr_raw, cmap) if spqr_raw is not None else None
            if not isinstance(spqr, SpqrRatchetState):
                spqr = None
            name = raw.get("name", default_name)
            return TripleRatchetPartyState(name=name, dr=dr, spqr=spqr)

        alice = _load_party(data.get("alice"), "Alice")
        bob = _load_party(data.get("bob"), "Bob")

        message_log: list[TripleRatchetMessageState] = []
        for raw_msg in data.get("message_log", []):
            if not isinstance(raw_msg, dict):
                continue
            msg = _deserialize_message(raw_msg)
            if msg is not None:
                message_log.append(msg)

        self.session = TripleRatchetSessionState(alice=alice, bob=bob, message_log=message_log)

        # Pending messages
        pending: list[dict[str, Any]] = []
        for raw_p in data.get("pending_messages", []):
            if not isinstance(raw_p, dict):
                continue
            msg = _deserialize_message(raw_p)
            if msg is None:
                continue
            raw_header = raw_p.get("header")
            if isinstance(raw_header, dict):
                msg_obj = _deserialize_message(raw_p)
                if msg_obj is not None:
                    pending.append({
                        "id": raw_p.get("id"),
                        "sender": raw_p.get("sender"),
                        "receiver": raw_p.get("receiver"),
                        "header": msg_obj.header,
                        "cipher": msg_obj.cipher,
                        "plaintext": msg_obj.plaintext,
                        "pqxdh_header": raw_p.get("pqxdh_header"),
                    })
        self.pending_messages = pending

        next_id = data.get("next_pending_id", 1)
        self._next_pending_id = next_id if isinstance(next_id, int) and next_id > 0 else 1

        self._session_ad = _decode_bytes(data.get("session_ad")) or b""
        self._pqxdh_bootstrap_payload = data.get("pqxdh_bootstrap_payload") if isinstance(data.get("pqxdh_bootstrap_payload"), dict) else None
        self._pqxdh_initial_header = data.get("pqxdh_initial_header") if isinstance(data.get("pqxdh_initial_header"), dict) else None
        self._pqxdh_shared_secret = _decode_bytes(data.get("pqxdh_shared_secret")) or None
        spk_raw = data.get("pqxdh_bob_spk_pair")
        if isinstance(spk_raw, dict):
            p = spk_raw.get("private")
            pub = spk_raw.get("public")
            if isinstance(p, str) and isinstance(pub, str) and p and pub:
                self._pqxdh_bob_spk_pair = DHKeyPair(private=p, public=pub)
            else:
                self._pqxdh_bob_spk_pair = None
        else:
            self._pqxdh_bob_spk_pair = None
        self._pqxdh_state_data = data.get("pqxdh_state_data") if isinstance(data.get("pqxdh_state_data"), dict) else None
        self._pqxdh_bob_initialized = bool(data.get("pqxdh_bob_initialized", False))
        self._pqxdh_alice_received_bob_reply = bool(data.get("pqxdh_alice_received_bob_reply", False))
        self._pending_show_alice_pqxdh_bootstrap = bool(data.get("pending_show_alice_pqxdh_bootstrap", True))
        self._last_bob_bootstrap_info = data.get("last_bob_bootstrap_info") if isinstance(data.get("last_bob_bootstrap_info"), dict) else None
        self._send_steps.clear()
        self._receive_steps.clear()
        self._initial_warning_shown = True

        if self.session.alice is None and self._pqxdh_bootstrap_payload is not None:
            self._apply_pqxdh_bootstrap_payload(self._pqxdh_bootstrap_payload)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def build(self, page: ft.Page, app_state: Any, perspective_selector: ft.Control | None = None) -> ft.Control:
        """Build the interactive Triple Ratchet module view."""

        self._sync_bootstrap_from_app_state(app_state)

        message_count = ft.Text(f"Messages exchanged: {len(self.session.message_log)}")
        send_step_visualization_checkbox = ft.Checkbox(label="Show sending steps visualisation", value=False)
        receive_step_visualization_checkbox = ft.Checkbox(label="Show receiving steps visualisation", value=False)
        auto_receive_checkbox = ft.Checkbox(label="Auto receive", value=False)
        alice_input = ft.TextField(dense=True, expand=True)
        bob_input = ft.TextField(dense=True, expand=True)
        visual_container = ft.Container(expand=True)

        auto_receive_enabled = bool(auto_receive_checkbox.value)

        def _show_send_step(pending_id: int, on_close=None) -> None:
            step = self._send_steps.get(pending_id)
            if step is not None:
                show_triple_ratchet_send_step_dialog(page, step, on_close=on_close)

        def _show_receive_step(pending_id: int) -> None:
            step = self._receive_steps.get(pending_id)
            if step is not None:
                show_triple_ratchet_receive_step_dialog(
                    page,
                    step,
                    on_show_bootstrap=lambda: show_bob_pqxdh_bootstrap_visualization(step.pqxdh_header),
                )

        def _on_perspective_change(e: Any) -> None:
            app_state.perspective = e.control.value
            refresh_view()
            page.update()

        if perspective_selector is None:
            perspective_selector = build_perspective_selector(
                app_state,
                _on_perspective_change,
                [("global", "Global"), ("alice", "Alice"), ("bob", "Bob")],
            )

        def _auto_receive_if_enabled() -> tuple[list[int], list[str]]:
            if not auto_receive_enabled:
                return [], []
            return self._auto_receive_all_pending()

        def refresh_view() -> None:
            message_count.value = f"Messages exchanged: {len(self.session.message_log)}"
            alice_input.hint_text = self._build_hint_message("alice")
            bob_input.hint_text = self._build_hint_message("bob")
            visual_container.content = build_visual(
                self.session,
                app_state.perspective,
                page,
                alice_input=alice_input,
                bob_input=bob_input,
                on_send_alice=on_send_alice,
                on_send_bob=on_send_bob,
                pending_messages=self.pending_messages,
                on_receive_pending=on_receive_pending,
                on_show_send_visualization=lambda sid: _show_send_step(sid),
                on_show_receive_visualization=lambda sid: _show_receive_step(sid),
                on_show_alice_pqxdh_bootstrap=show_alice_pqxdh_bootstrap_visualization,
                on_show_bob_pqxdh_bootstrap=lambda header: show_bob_pqxdh_bootstrap_visualization(header),
            )

        def _handle_post_send(pending_id: int) -> None:
            processed_ids, errors = _auto_receive_if_enabled()
            refresh_view()
            page.update()

            if errors:
                show_warning_dialog(page, "Auto receive failed for: " + "; ".join(errors))

            if send_step_visualization_checkbox.value:
                if receive_step_visualization_checkbox.value and pending_id in processed_ids:
                    _show_send_step(pending_id, on_close=lambda: _show_receive_step(pending_id))
                else:
                    _show_send_step(pending_id)
            elif receive_step_visualization_checkbox.value and pending_id in processed_ids:
                _show_receive_step(pending_id)

        def on_send_alice(e: Any) -> None:
            try:
                pending = self.send_message("alice", alice_input.value, alice_input.hint_text or "")
            except ValueError as exc:
                show_warning_dialog(page, str(exc))
                return
            alice_input.value = ""
            _handle_post_send(int(pending["id"]))

        def on_send_bob(e: Any) -> None:
            try:
                pending = self.send_message("bob", bob_input.value, bob_input.hint_text or "")
            except ValueError as exc:
                show_warning_dialog(page, str(exc))
                return
            bob_input.value = ""
            _handle_post_send(int(pending["id"]))

        def on_receive_pending(recipient: str, pending_id: int) -> None:
            try:
                self.receive_message(recipient, pending_id)
            except ValueError as exc:
                show_warning_dialog(page, str(exc))
                return
            refresh_view()
            page.update()
            if receive_step_visualization_checkbox.value:
                _show_receive_step(pending_id)

        def on_auto_receive_changed(e: Any) -> None:
            nonlocal auto_receive_enabled
            auto_receive_enabled = bool(auto_receive_checkbox.value)
            processed_ids, errors = _auto_receive_if_enabled()
            refresh_view()
            page.update()
            if errors:
                show_warning_dialog(page, "Auto receive failed for: " + "; ".join(errors))
            if receive_step_visualization_checkbox.value:
                for pid in processed_ids:
                    _show_receive_step(pid)

        def on_reset_module(e: Any) -> None:
            self._reset_session()
            self._sync_bootstrap_from_app_state(app_state)
            refresh_view()
            page.update()
            show_initial_bootstrap_warning(
                page,
                "Triple Ratchet session reset with a fresh PQXDH bootstrap.",
                "Show Alice PQXDH steps after closing",
                "Info",
                _on_bootstrap_viz,
            )

        def _on_bootstrap_viz() -> None:
            show_alice_pqxdh_bootstrap_visualization()

        def show_alice_pqxdh_bootstrap_visualization() -> None:
            alice = self.session.alice
            if alice is None:
                return
            spqr = alice.spqr
            if spqr is None:
                return
            chains = spqr.kdfchains.get(spqr.epoch)
            cks = chains.send.CK if chains is not None and chains.send is not None else None
            show_alice_pqxdh_bootstrap_visualization_dialog(
                page,
                pqxdh_state_data=self._pqxdh_state_data,
                spqr_rk_after_init=spqr.RK,
                spqr_cks_after_init=cks,
                alice_scka_state=spqr.scka_state,
                dr_rk_after_init=alice.dr.RK,
                dr_cks_after_init=alice.dr.CKs,
                session_ad=self._session_ad,
                alice_dhs_pub=alice.dr.DHs.public if alice.dr.DHs else "",
                alice_dhs_priv=alice.dr.DHs.private if alice.dr.DHs else "",
                sk=self._pqxdh_shared_secret,
            )

        def show_bob_pqxdh_bootstrap_visualization(pqxdh_header: dict[str, Any] | None) -> None:
            bob = self.session.bob
            if bob is None or self._pqxdh_shared_secret is None:
                return

            bob_ik_pub = ""
            bob_ik_priv = ""
            if isinstance(self._pqxdh_state_data, dict):
                bob_local = self._pqxdh_state_data.get("bob_local", {})
                if isinstance(bob_local, dict):
                    bob_ik = bob_local.get("identity_dh", {})
                    if isinstance(bob_ik, dict):
                        bob_ik_pub = bob_ik.get("public", "")
                        bob_ik_priv = bob_ik.get("private", "")

            show_bob_pqxdh_bootstrap_visualization_dialog(
                page,
                pqxdh_state_data=self._pqxdh_state_data,
                pqxdh_header=pqxdh_header,
                bob=bob,
                session_ad=self._session_ad,
                bob_spk_public=bob.dr.DHs.public if bob.dr and bob.dr.DHs else "",
                bob_spk_priv=bob.dr.DHs.private if bob.dr and bob.dr.DHs else "",
                bob_ik_pub=bob_ik_pub,
                bob_ik_priv=bob_ik_priv,
                shared_secret=self._pqxdh_shared_secret,
            )

        auto_receive_checkbox.on_change = on_auto_receive_changed

        if not self._initial_warning_shown:
            self._initial_warning_shown = True
            if self._pending_show_alice_pqxdh_bootstrap:
                show_initial_bootstrap_warning(
                    page,
                    "Triple Ratchet session initialized with PQXDH for DR and SPQR ratchets.",
                    "Show Alice PQXDH bootstrap steps",
                    "Info",
                    _on_bootstrap_viz,
                )

        refresh_view()

        return build_module_layout(
            title_text="Triple Ratchet Simulation",
            send_step_visualization_checkbox=send_step_visualization_checkbox,
            receive_step_visualization_checkbox=receive_step_visualization_checkbox,
            auto_receive_checkbox=auto_receive_checkbox,
            message_count=message_count,
            perspective_selector=perspective_selector,
            on_reset_module=on_reset_module,
            visual_container=visual_container,
        )
