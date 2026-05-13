from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
import json
from typing import Any

import flet as ft

from components.data_classes import (
    AuthenticatorState,
    BraidProtocolState,
    DecoderState,
    EncoderState,
    EpochKdfChains,
    KdfChainState,
    KeyEvent,
    SckaOutputKey,
    SckaReceiveResult,
    SckaSendResult,
    SpqrHeader,
    SpqrMessageState,
    SpqrMessageType,
    SpqrRatchetState,
    SpqrSckaMessage,
    SpqrSessionState,
)
from modules.messaging.messaging_base_module import MessagingBaseModule, encode_nested, decode_nested
from modules.messaging.messaging_base_view import (
    tail_hex,
    safe_decode_bytes,
    show_warning_dialog,
    show_initial_bootstrap_warning,
    build_perspective_selector,
    build_module_layout,
)
from modules.messaging.spqr.key_history import (
    initialize_key_history,
    track_keys_from_send_step,
    track_keys_from_receive_step,
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
    initialize_session_from_pqxdh,
    SCKARatchetDecrypt,
    SCKARatchetEncrypt,
)
from modules.messaging.spqr.step_visualization import (
    show_alice_pqxdh_bootstrap_visualization_dialog,
    show_bob_pqxdh_bootstrap_visualization_dialog,
    show_spqr_step_visualization_dialog,
)
from modules.messaging.spqr.view import build_visual
from modules.key_exchange.key_exchange_base_logic import alice_calculates_associated_data
from modules.key_exchange.pqxdh.logic import (
    new_state as new_pqxdh_state,
    generate_alice_registration_material,
    upload_alice_initial_bundle,
    request_bob_bundle_for_alice,
    alice_verifies_bundle_signature,
    alice_generates_ek_and_derives_sk,
    alice_sends_initial_message,
)
"""SPQR messaging module integration.

This module provides `SPQRModule`, a `MessagingBaseModule` implementation that
hooks the SPQR ratchet logic into the application's UI, state export/import,
and visualization helpers. It manages PQXDH bootstrapping, pending message
queues, and instrumentation used by the SPQR visualizations.
"""

class SPQRModule(MessagingBaseModule):
    """UI-facing module for demonstrating SPQR ratchet behavior.

    The class maintains the active `SpqrSessionState`, pending messages and
    visualization snapshots. Methods such as `send_message` and
    `receive_message` perform ratchet operations and record traces used by the
    step visualization components.
    """
    def __init__(self) -> None:
        self.session = SpqrSessionState()
        self.pending_messages: list[dict[str, Any]] = []
        self._next_pending_id = 1
        self._session_ad = b""
        self._pqxdh_bootstrap_payload: dict[str, Any] | None = None
        self._pqxdh_initial_header: dict[str, Any] | None = None
        self._pqxdh_shared_secret: bytes | None = None
        self._pqxdh_state_data: dict[str, Any] | None = None
        self._pqxdh_bob_initialized: bool = False
        self._pqxdh_alice_received_bob_reply: bool = False
        self._pending_show_alice_pqxdh_bootstrap: bool = True
        self._last_bob_bootstrap_info: dict[str, Any] | None = None
        self._initial_warning_shown: bool = False
        self._send_steps: dict[int, dict[str, Any]] = {}
        self._receive_steps: dict[int, dict[str, Any]] = {}
        self._reset_session()

    def _class_map(self) -> dict[str, type]:
        from components.data_classes import KeyHistory
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
            "SpqrMessageState": SpqrMessageState,
            "SpqrSessionState": SpqrSessionState,
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

    def _reset_session(self) -> None:
        self.session = SpqrSessionState(alice=None, bob=None, message_log=[])
        self._session_ad = b""
        self._pqxdh_bootstrap_payload = None
        self._pqxdh_initial_header = None
        self._pqxdh_shared_secret = None
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
        if not isinstance(payload, dict):
            return False

        shared_secret_hex = payload.get("shared_secret_hex")
        associated_data_hex = payload.get("associated_data_hex")
        initial_header = payload.get("initial_header") if isinstance(payload.get("initial_header"), dict) else None
        if not all(isinstance(value, str) and value for value in [shared_secret_hex, associated_data_hex]) or not isinstance(initial_header, dict):
            return False

        self.session = initialize_session_from_pqxdh(bytes.fromhex(shared_secret_hex))
        self._session_ad = bytes.fromhex(associated_data_hex)
        self._pqxdh_bootstrap_payload = payload
        self._pqxdh_initial_header = initial_header
        self._pqxdh_shared_secret = bytes.fromhex(shared_secret_hex)
        self._pqxdh_state_data = payload
        self._pqxdh_bob_initialized = False
        self._pqxdh_alice_received_bob_reply = False
        self._pending_show_alice_pqxdh_bootstrap = True
        self._last_bob_bootstrap_info = None
        initialize_key_history(self.session)
        return True

    def _sync_bootstrap_from_app_state(self, app_state) -> None:
        if self.session.alice is not None:
            return

        payload = getattr(app_state, "pqxdh_to_spqr_bootstrap", None)
        if not isinstance(payload, dict):
            payload = self._pqxdh_bootstrap_payload
        if isinstance(payload, dict):
            self._apply_pqxdh_bootstrap_payload(payload)
        else:
            # No bootstrap payload from PQXDH, generate one internally (fallback)
            self._reset_session_with_initializer()

    def _reset_session_with_initializer(self) -> None:
        """Initialize SPQR session by generating fresh PQXDH keying material internally."""
        # Generate fresh PQXDH state
        pqxdh_state = new_pqxdh_state()
        
        # Run through complete PQXDH initialization
        generate_alice_registration_material(pqxdh_state)
        upload_alice_initial_bundle(pqxdh_state)
        request_bob_bundle_for_alice(pqxdh_state)
        alice_verifies_bundle_signature(pqxdh_state)
        alice_generates_ek_and_derives_sk(pqxdh_state)
        alice_calculates_associated_data(pqxdh_state)
        alice_sends_initial_message(pqxdh_state, "")

        # Extract the bootstrap payload
        derived = pqxdh_state.alice_derived if isinstance(pqxdh_state.alice_derived, dict) else None
        initial_message = pqxdh_state.initial_message if isinstance(pqxdh_state.initial_message, dict) else None
        initial_header = initial_message.get("header") if isinstance(initial_message, dict) and isinstance(initial_message.get("header"), dict) else None

        if not isinstance(derived, dict) or not isinstance(initial_header, dict):
            raise ValueError("Could not initialize SPQR because PQXDH bootstrap is incomplete.")

        shared_secret_hex = derived.get("shared_secret")
        associated_data_hex = derived.get("associated_data")
        if not all(isinstance(value, str) and value for value in [shared_secret_hex, associated_data_hex]):
            raise ValueError("Could not initialize SPQR because PQXDH output values are invalid.")

        # Build and apply the bootstrap payload
        payload = {
            "source": "pqxdh",
            "shared_secret_hex": shared_secret_hex,
            "associated_data_hex": associated_data_hex,
            "initial_header": initial_header,
            "initial_message_json": json.dumps(initial_message, sort_keys=True) if isinstance(initial_message, dict) else "",
        }
        self._apply_pqxdh_bootstrap_payload(payload)
        self._pqxdh_state_data = asdict(pqxdh_state)

    def _complete_bob_pqxdh_bootstrap_from_header(self, pqxdh_header: dict[str, Any]) -> None:
        if self._pqxdh_bob_initialized:
            return

        if self._pqxdh_shared_secret is None or self._pqxdh_initial_header is None:
            raise ValueError("Bob cannot complete PQXDH bootstrap because required state is missing.")

        if not isinstance(pqxdh_header, dict) or pqxdh_header != self._pqxdh_initial_header:
            raise ValueError("PQXDH header does not match the stored bootstrap header.")

        self.session.bob = RatchetInitBobSCKA(self._pqxdh_shared_secret)
        self._pqxdh_bob_initialized = True
        self._last_bob_bootstrap_info = {"pqxdh_header": pqxdh_header}
        initialize_key_history(self.session)

    def _node_snapshot(self, node: object | None) -> dict[str, Any]:
        if not is_dataclass(node):
            return {}

        snapshot: dict[str, Any] = {"node": type(node).__name__}
        for field in fields(node):
            value = getattr(node, field.name)
            if is_dataclass(value):
                snapshot[field.name] = self._node_snapshot(value)
            elif isinstance(value, list):
                snapshot[field.name] = [self._node_snapshot(item) if is_dataclass(item) else item for item in value]
            else:
                snapshot[field.name] = value
        return snapshot

    def _snapshot_party_state(self, state: SpqrRatchetState) -> dict[str, Any]:
        chains = state.kdfchains.get(state.epoch)
        send_ck = chains.send.CK if chains is not None and chains.send is not None else None
        recv_ck = chains.receive.CK if chains is not None and chains.receive is not None else None
        node = state.scka_state.node if state.scka_state is not None else None
        state_name = type(node).__name__ if node is not None else "Unknown"
        return {
            "state": state_name,
            "node": state_name,
            "epoch": state.epoch,
            "direction": state.direction,
            "rk_tail": tail_hex(state.RK),
            "send_ck_tail": tail_hex(send_ck),
            "recv_ck_tail": tail_hex(recv_ck),
            "scka_node": self._node_snapshot(node),
        }

    def _header_desc(self, header: SpqrHeader | None) -> str:
        if header is None:
            return ""
        return f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}"


    def _record_send_step(
        self,
        pending_id: int,
        sender: str,
        receiver: str,
        before: dict[str, Any],
        after: dict[str, Any],
        header: SpqrHeader,
        plaintext: bytes,
        cipher: bytes,
        encrypt_trace: dict[str, Any],
    ) -> None:
        self._send_steps[pending_id] = {
            "action": "send",
            "actor": sender,
            "peer": receiver,
            "before": before,
            "after": after,
            "header": header,
            "plaintext": plaintext,
            "cipher": cipher,
            "encrypt_trace": encrypt_trace,
            "header_desc": self._header_desc(header),
            "message_type": header.msg.msg_type.value,
            "message_desc": f"plaintext={safe_decode_bytes(plaintext)} | cipher_tail={tail_hex(cipher, 16)}",
        }

    def _record_receive_step(
        self,
        pending_id: int,
        sender: str,
        receiver: str,
        before: dict[str, Any],
        after: dict[str, Any],
        header: SpqrHeader,
        cipher: bytes,
        decrypted: bytes,
        receive_trace: dict[str, Any],
    ) -> None:
        self._receive_steps[pending_id] = {
            "action": "receive",
            "actor": receiver,
            "peer": sender,
            "before": before,
            "after": after,
            "header": header,
            "cipher": cipher,
            "decrypted": decrypted,
            "receive_trace": receive_trace,
            "header_desc": self._header_desc(header),
            "message_type": header.msg.msg_type.value,
            "message_desc": f"cipher_tail={tail_hex(cipher, 16)} | decrypted={safe_decode_bytes(decrypted)}",
        }

    def _get_party(self, party: str) -> SpqrRatchetState:
        key = party.lower()
        if key == "alice":
            if self.session.alice is None:
                raise ValueError("Alice state is not initialized")
            return self.session.alice
        if key == "bob":
            if self.session.bob is None:
                raise ValueError("Bob state is not initialized")
            return self.session.bob
        raise ValueError(f"Unknown party: {party}")

    def _build_hint_message(self, sender: str) -> str:
        key = sender.lower()
        if key == "alice":
            return f"Alice message #{self._next_pending_id} to Bob"
        if key == "bob":
            return f"Bob message #{self._next_pending_id} to Alice"
        return ""

    def send_message(self, sender: str, plaintext: str, fallback_plaintext: str = "") -> dict[str, Any]:
        sender_name = sender.capitalize()
        receiver_name = "Bob" if sender_name == "Alice" else "Alice"

        message_text = (plaintext or "").strip()
        if not message_text:
            message_text = (fallback_plaintext or "").strip()
        if not message_text:
            raise ValueError("Message cannot be empty")

        sender_state = self._get_party(sender_name)
        before = self._snapshot_party_state(sender_state)
        header, cipher, encrypt_trace = SCKARatchetEncrypt(
            sender_state,
            message_text.encode("utf-8"),
            self._session_ad,
        )
        after = self._snapshot_party_state(sender_state)

        pending_id = self._next_pending_id
        pending = {
            "id": pending_id,
            "sender": sender_name,
            "receiver": receiver_name,
            "header": header,
            "cipher": cipher,
            "plaintext": message_text.encode("utf-8"),
            "pqxdh_header": self._pqxdh_initial_header if sender_name == "Alice" and not self._pqxdh_alice_received_bob_reply else None,
        }
        self.pending_messages.append(pending)
        self._next_pending_id += 1

        self._record_send_step(
            pending_id,
            sender_name,
            receiver_name,
            before,
            after,
            header,
            pending["plaintext"],
            cipher,
            encrypt_trace,
        )

        # Expose pqxdh header on the recorded send-step so visualizations can show it
        self._send_steps[pending_id]["pqxdh_header"] = pending.get("pqxdh_header")

        # Track key generation from this send step
        track_keys_from_send_step(sender_state, sender_name, pending_id, before, after)

        return pending

    def receive_message(self, recipient: str, pending_id: int) -> SpqrMessageState | None:
        target = recipient.capitalize()
        pending = next((item for item in self.pending_messages if item.get("id") == pending_id), None)
        if pending is None:
            return None
        if pending.get("receiver") != target:
            raise ValueError("Pending message receiver mismatch")

        pqxdh_header = pending.get("pqxdh_header") if isinstance(pending.get("pqxdh_header"), dict) else None
        was_pqxdh_bootstrapped = False
        if target == "Bob" and not self._pqxdh_bob_initialized:
            if pqxdh_header is None:
                raise ValueError("Bob cannot receive the first message because PQXDH header is missing.")
            self._complete_bob_pqxdh_bootstrap_from_header(pqxdh_header)
            was_pqxdh_bootstrapped = True

        recipient_state = self._get_party(target)
        before = self._snapshot_party_state(recipient_state)
        plaintext, receive_trace = SCKARatchetDecrypt(
            recipient_state,
            pending["header"],
            pending["cipher"],
            self._session_ad,
        )
        after = self._snapshot_party_state(recipient_state)

        message = SpqrMessageState(
            sender=str(pending["sender"]),
            receiver=str(pending["receiver"]),
            header=pending["header"],
            cipher=pending["cipher"],
            plaintext=pending.get("plaintext", b""),
            decrypted_by_receiver=plaintext,
            seq_id=pending_id,
            pqxdh_header=pqxdh_header,
        )
        self.session.message_log.append(message)
        self.pending_messages = [item for item in self.pending_messages if item.get("id") != pending_id]

        if pending["sender"] == "Bob" and target == "Alice":
            self._pqxdh_alice_received_bob_reply = True

        self._record_receive_step(
            pending_id,
            message.sender,
            message.receiver,
            before,
            after,
            message.header,
            message.cipher,
            plaintext,
            receive_trace,
        )

        self._receive_steps[pending_id]["pqxdh_header"] = pqxdh_header
        self._receive_steps[pending_id]["was_pqxdh_bootstrapped"] = was_pqxdh_bootstrapped

        # Track key generation from this receive step
        track_keys_from_receive_step(recipient_state, target, pending_id, before, after)

        return message

    def _auto_receive_all_pending(self) -> tuple[list[int], list[str]]:
        processed_ids: list[int] = []
        errors: list[str] = []
        for pending in list(self.pending_messages):
            pending_id = pending.get("id")
            recipient = pending.get("receiver")
            if not isinstance(pending_id, int) or not isinstance(recipient, str):
                continue
            try:
                result = self.receive_message(recipient, pending_id)
                if result is not None:
                    processed_ids.append(pending_id)
            except ValueError as exc:
                errors.append(f"#{pending_id} {recipient}: {exc}")
        return processed_ids, errors

    def export_state(self) -> dict:
        return {
            "session": encode_nested(self.session),
            "pending_messages": encode_nested(self.pending_messages),
            "next_pending_id": self._next_pending_id,
            "session_ad": encode_nested(self._session_ad),
            "pqxdh_bootstrap_payload": encode_nested(self._pqxdh_bootstrap_payload),
            "pqxdh_initial_header": encode_nested(self._pqxdh_initial_header),
            "pqxdh_shared_secret": encode_nested(self._pqxdh_shared_secret),
            "pqxdh_state_data": encode_nested(self._pqxdh_state_data),
            "pqxdh_bob_initialized": self._pqxdh_bob_initialized,
            "pqxdh_alice_received_bob_reply": self._pqxdh_alice_received_bob_reply,
            "pending_show_alice_pqxdh_bootstrap": self._pending_show_alice_pqxdh_bootstrap,
            "last_bob_bootstrap_info": encode_nested(self._last_bob_bootstrap_info),
            "send_steps": encode_nested(self._send_steps),
            "receive_steps": encode_nested(self._receive_steps),
        }

    def import_state(self, data: dict) -> None:
        class_map = self._class_map()
        session_raw = data.get("session")
        pending_raw = data.get("pending_messages", [])
        next_id = data.get("next_pending_id", 1)

        decoded_session = decode_nested(session_raw, class_map)
        if isinstance(decoded_session, SpqrSessionState):
            self.session = decoded_session
        else:
            self._reset_session()
            return

        decoded_pending = decode_nested(pending_raw, class_map)
        self.pending_messages = decoded_pending if isinstance(decoded_pending, list) else []
        self._next_pending_id = next_id if isinstance(next_id, int) and next_id > 0 else 1
        self._session_ad = decode_nested(data.get("session_ad"), class_map) if data.get("session_ad") is not None else b""
        if not isinstance(self._session_ad, bytes):
            self._session_ad = b""
        decoded_bootstrap = decode_nested(data.get("pqxdh_bootstrap_payload"), class_map)
        self._pqxdh_bootstrap_payload = decoded_bootstrap if isinstance(decoded_bootstrap, dict) else None
        decoded_header = decode_nested(data.get("pqxdh_initial_header"), class_map)
        self._pqxdh_initial_header = decoded_header if isinstance(decoded_header, dict) else None
        decoded_shared_secret = decode_nested(data.get("pqxdh_shared_secret"), class_map)
        self._pqxdh_shared_secret = decoded_shared_secret if isinstance(decoded_shared_secret, bytes) else None
        decoded_state_data = decode_nested(data.get("pqxdh_state_data"), class_map)
        self._pqxdh_state_data = decoded_state_data if isinstance(decoded_state_data, dict) else None
        self._pqxdh_bob_initialized = bool(data.get("pqxdh_bob_initialized", False))
        self._pqxdh_alice_received_bob_reply = bool(data.get("pqxdh_alice_received_bob_reply", False))
        self._pending_show_alice_pqxdh_bootstrap = bool(data.get("pending_show_alice_pqxdh_bootstrap", True))
        decoded_last_bootstrap = decode_nested(data.get("last_bob_bootstrap_info"), class_map)
        self._last_bob_bootstrap_info = decoded_last_bootstrap if isinstance(decoded_last_bootstrap, dict) else None
        raw_send_steps = decode_nested(data.get("send_steps", {}), class_map)
        self._send_steps = raw_send_steps if isinstance(raw_send_steps, dict) else {}
        raw_receive_steps = decode_nested(data.get("receive_steps", {}), class_map)
        self._receive_steps = raw_receive_steps if isinstance(raw_receive_steps, dict) else {}
        self._initial_warning_shown = True

        if self.session.alice is None and self._pqxdh_bootstrap_payload is not None:
            self._apply_pqxdh_bootstrap_payload(self._pqxdh_bootstrap_payload)

    def build(self, page, app_state, perspective_selector: ft.Control | None = None):
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
                show_spqr_step_visualization_dialog(page, step, on_close=on_close)

        def _show_receive_step(pending_id: int) -> None:
            step = self._receive_steps.get(pending_id)
            if step is not None:
                pqxdh_header = step.get("pqxdh_header") if isinstance(step.get("pqxdh_header"), dict) else None

                def _show_bound_bob_pqxdh_bootstrap() -> None:
                    if pqxdh_header is not None:
                        show_bob_pqxdh_bootstrap_visualization(pqxdh_header)

                show_spqr_step_visualization_dialog(
                    page,
                    step,
                    on_show_pqxdh_bootstrap=_show_bound_bob_pqxdh_bootstrap,
                )

        def _on_perspective_change(e) -> None:
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

        def on_send_alice(e) -> None:
            try:
                pending = self.send_message("alice", alice_input.value, alice_input.hint_text or "")
            except ValueError as exc:
                show_warning_dialog(page, str(exc))
                return
            alice_input.value = ""
            _handle_post_send(int(pending["id"]))

        def on_send_bob(e) -> None:
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

        def on_auto_receive_changed(e) -> None:
            nonlocal auto_receive_enabled
            auto_receive_enabled = bool(auto_receive_checkbox.value)
            processed_ids, errors = _auto_receive_if_enabled()
            refresh_view()
            page.update()
            if errors:
                show_warning_dialog(page, "Auto receive failed for: " + "; ".join(errors))
            if receive_step_visualization_checkbox.value:
                for pending_id in processed_ids:
                    _show_receive_step(pending_id)

        def on_reset_module(e) -> None:
            self._reset_session()
            self._sync_bootstrap_from_app_state(app_state)
            refresh_view()
            page.update()
            show_initial_bootstrap_warning(page, "SPQR session reset with a fresh PQXDH bootstrap.", "Show Alice PQXDH steps after closing", "Info", _on_bootstrap_viz)

        def show_alice_pqxdh_bootstrap_visualization() -> None:
            alice_state = self.session.alice
            if alice_state is None:
                return
            show_alice_pqxdh_bootstrap_visualization_dialog(
                page,
                pqxdh_state_data=self._pqxdh_state_data,
                rk_after_init=alice_state.RK,
                cks_after_init=alice_state.kdfchains.get(alice_state.epoch).send.CK if alice_state.kdfchains.get(alice_state.epoch) and alice_state.kdfchains.get(alice_state.epoch).send is not None else None,
                alice_scka_state=alice_state.scka_state,
                session_ad=self._session_ad,
            )

        def show_bob_pqxdh_bootstrap_visualization(pqxdh_header: dict[str, Any] | None) -> None:
            bob_state = self.session.bob
            if bob_state is None or self._pqxdh_shared_secret is None:
                return
            bob_ik_public = None
            pq_shared_secret = None
            bob_pq_prekey_public = None
            if isinstance(self._pqxdh_state_data, dict):
                last_bundle = self._pqxdh_state_data.get("last_bundle_for_alice")
                if isinstance(last_bundle, dict) and isinstance(last_bundle.get("identity_dh_public"), str):
                    bob_ik_public = last_bundle.get("identity_dh_public")

                alice_derived = self._pqxdh_state_data.get("alice_derived")
                if isinstance(alice_derived, dict):
                    pq_secret_hex = alice_derived.get("pq_secret")
                    if isinstance(pq_secret_hex, str):
                        pq_shared_secret = bytes.fromhex(pq_secret_hex)

                    bob_pq_prekey_public = alice_derived.get("bob_pq_prekey_public")
                if bob_pq_prekey_public is None and isinstance(last_bundle, dict):
                    bob_pq_prekey_public = last_bundle.get("pq_opk_public")
                    if bob_pq_prekey_public is None:
                        bob_pq_prekey_public = last_bundle.get("pq_signed_prekey_public")
            show_bob_pqxdh_bootstrap_visualization_dialog(
                page,
                pqxdh_header=pqxdh_header,
                shared_secret=self._pqxdh_shared_secret,
                session_ad=self._session_ad,
                bob_state=bob_state,
                bob_ik_public=bob_ik_public,
                pq_shared_secret=pq_shared_secret,
                bob_pq_prekey_public=bob_pq_prekey_public,
                on_close=None,
            )

        def _on_bootstrap_viz() -> None:
            if self._pending_show_alice_pqxdh_bootstrap:
                self._pending_show_alice_pqxdh_bootstrap = False
                show_alice_pqxdh_bootstrap_visualization()

        auto_receive_checkbox.on_change = on_auto_receive_changed
        refresh_view()
        if not self._initial_warning_shown:
            show_initial_bootstrap_warning(
                page,
                "SPQR starts from a fresh PQXDH run. Alice already completed her steps; "
                "Bob completes PQXDH bootstrap on his first receive.",
                "Show Alice PQXDH steps after closing",
                "Info",
                _on_bootstrap_viz,
            )
            self._initial_warning_shown = True

        return build_module_layout(
            title_text="SPQR Simulation",
            send_step_visualization_checkbox=send_step_visualization_checkbox,
            receive_step_visualization_checkbox=receive_step_visualization_checkbox,
            auto_receive_checkbox=auto_receive_checkbox,
            message_count=message_count,
            perspective_selector=perspective_selector,
            on_reset_module=on_reset_module,
            visual_container=visual_container,
        )


SpqrModule = SPQRModule
