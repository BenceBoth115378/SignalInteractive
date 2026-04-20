from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

import flet as ft

from components.data_classes import (
    AuthenticatorState,
    BraidProtocolState,
    DecoderState,
    EncoderState,
    EpochKdfChains,
    KdfChainState,
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
from modules.messaging.messaging_base_module import MessagingBaseModule
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
    RatchetInitAliceSCKA,
    RatchetInitBobSCKA,
    SCKARatchetDecrypt,
    SCKARatchetEncrypt,
)
from modules.messaging.spqr.step_visualization import show_spqr_step_visualization_dialog
from modules.messaging.spqr.view import build_visual


def _encode_nested(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, Enum):
        return {"__enum__": value.__class__.__name__, "value": value.value}
    if is_dataclass(value):
        return {
            "__class__": value.__class__.__name__,
            "fields": {field.name: _encode_nested(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, dict):
        return {key: _encode_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_nested(item) for item in value]
    return value


def _decode_nested(value: Any, class_map: dict[str, type]) -> Any:
    if isinstance(value, dict):
        if "__bytes__" in value and isinstance(value["__bytes__"], str):
            try:
                return bytes.fromhex(value["__bytes__"])
            except ValueError:
                return b""
        if "__enum__" in value and isinstance(value["__enum__"], str):
            enum_cls = class_map.get(value["__enum__"])
            if enum_cls is not None and issubclass(enum_cls, Enum):
                try:
                    return enum_cls(value.get("value"))
                except Exception:
                    return value.get("value")
        if "__class__" in value and isinstance(value["__class__"], str):
            class_name = value["__class__"]
            cls = class_map.get(class_name)
            raw_fields = value.get("fields", {})
            if cls is not None and isinstance(raw_fields, dict):
                kwargs = {key: _decode_nested(item, class_map) for key, item in raw_fields.items()}
                return cls(**kwargs)
        return {key: _decode_nested(item, class_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_nested(item, class_map) for item in value]
    return value


def _tail(value: bytes | None, size: int = 12) -> str:
    if value is None:
        return "None"
    text = value.hex()
    if len(text) <= size:
        return text
    return text[-size:]


class SPQRModule(MessagingBaseModule):
    def __init__(self) -> None:
        self.session = SpqrSessionState()
        self.pending_messages: list[dict[str, Any]] = []
        self._next_pending_id = 1
        self._session_ad = b"SPQR_AD"
        self._send_steps: dict[int, dict[str, Any]] = {}
        self._receive_steps: dict[int, dict[str, Any]] = {}
        self._reset_session()

    def _class_map(self) -> dict[str, type]:
        return {
            "SpqrMessageType": SpqrMessageType,
            "SpqrSckaMessage": SpqrSckaMessage,
            "SckaOutputKey": SckaOutputKey,
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
        shared_secret = b"\x51" * 32
        self.session = SpqrSessionState(
            alice=RatchetInitAliceSCKA(shared_secret),
            bob=RatchetInitBobSCKA(shared_secret),
            message_log=[],
        )
        self.pending_messages = []
        self._next_pending_id = 1
        self._send_steps.clear()
        self._receive_steps.clear()

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

    def _state_snapshot(self, state: SpqrRatchetState) -> dict[str, Any]:
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
            "rk_tail": _tail(state.RK),
            "send_ck_tail": _tail(send_ck),
            "recv_ck_tail": _tail(recv_ck),
            "scka_node": self._node_snapshot(node),
        }

    def _header_desc(self, header: SpqrHeader | None) -> str:
        if header is None:
            return ""
        return f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}"

    def _safe_text(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.hex()

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
            "message_desc": f"plaintext={self._safe_text(plaintext)} | cipher_tail={_tail(cipher, 16)}",
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
            "message_desc": f"cipher_tail={_tail(cipher, 16)} | decrypted={self._safe_text(decrypted)}",
        }

    def _get_party_state(self, party: str) -> SpqrRatchetState:
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

        sender_state = self._get_party_state(sender_name)
        before = self._state_snapshot(sender_state)
        header, cipher, encrypt_trace = SCKARatchetEncrypt(
            sender_state,
            message_text.encode("utf-8"),
            self._session_ad,
        )
        after = self._state_snapshot(sender_state)

        pending_id = self._next_pending_id
        pending = {
            "id": pending_id,
            "sender": sender_name,
            "receiver": receiver_name,
            "header": header,
            "cipher": cipher,
            "plaintext": message_text.encode("utf-8"),
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
        return pending

    def receive_message(self, recipient: str, pending_id: int) -> SpqrMessageState | None:
        target = recipient.capitalize()
        pending = next((item for item in self.pending_messages if item.get("id") == pending_id), None)
        if pending is None:
            return None
        if pending.get("receiver") != target:
            raise ValueError("Pending message receiver mismatch")

        recipient_state = self._get_party_state(target)
        before = self._state_snapshot(recipient_state)
        plaintext, receive_trace = SCKARatchetDecrypt(
            recipient_state,
            pending["header"],
            pending["cipher"],
            self._session_ad,
        )
        after = self._state_snapshot(recipient_state)

        message = SpqrMessageState(
            sender=str(pending["sender"]),
            receiver=str(pending["receiver"]),
            header=pending["header"],
            cipher=pending["cipher"],
            plaintext=pending.get("plaintext", b""),
            decrypted_by_receiver=plaintext,
            seq_id=pending_id,
        )
        self.session.message_log.append(message)
        self.pending_messages = [item for item in self.pending_messages if item.get("id") != pending_id]

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
            "session": _encode_nested(self.session),
            "pending_messages": _encode_nested(self.pending_messages),
            "next_pending_id": self._next_pending_id,
        }

    def import_state(self, data: dict) -> None:
        class_map = self._class_map()
        session_raw = data.get("session")
        pending_raw = data.get("pending_messages", [])
        next_id = data.get("next_pending_id", 1)

        decoded_session = _decode_nested(session_raw, class_map)
        if isinstance(decoded_session, SpqrSessionState):
            self.session = decoded_session
        else:
            self._reset_session()
            return

        decoded_pending = _decode_nested(pending_raw, class_map)
        self.pending_messages = decoded_pending if isinstance(decoded_pending, list) else []
        self._next_pending_id = next_id if isinstance(next_id, int) and next_id > 0 else 1
        self._send_steps.clear()
        self._receive_steps.clear()

    def build(self, page, app_state, perspective_selector: ft.Control | None = None):
        message_count = ft.Text(f"Messages exchanged: {len(self.session.message_log)}")
        send_step_visualization_checkbox = ft.Checkbox(label="Show sending steps visualisation", value=False)
        receive_step_visualization_checkbox = ft.Checkbox(label="Show receiving steps visualisation", value=False)
        auto_receive_checkbox = ft.Checkbox(label="Auto receive", value=False)
        alice_input = ft.TextField(dense=True, expand=True)
        bob_input = ft.TextField(dense=True, expand=True)
        visual_container = ft.Container(expand=True)

        auto_receive_enabled = bool(auto_receive_checkbox.value)

        def show_warning(message: str) -> None:
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Warning"),
                content=ft.Text(message),
                actions=[ft.TextButton("OK", on_click=lambda e: _close_dialog(dialog))],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def _close_dialog(dialog: ft.AlertDialog) -> None:
            dialog.open = False
            page.update()

        def _show_send_step(pending_id: int, on_close=None) -> None:
            step = self._send_steps.get(pending_id)
            if step is not None:
                show_spqr_step_visualization_dialog(page, step, on_close=on_close)

        def _show_receive_step(pending_id: int) -> None:
            step = self._receive_steps.get(pending_id)
            if step is not None:
                show_spqr_step_visualization_dialog(page, step)

        if perspective_selector is None:
            perspective_selector = ft.RadioGroup(
                value=app_state.perspective,
                content=ft.Row(
                    controls=[
                        ft.Radio(value="global", label="Global"),
                        ft.Radio(value="alice", label="Alice"),
                        ft.Radio(value="bob", label="Bob"),
                    ],
                    spacing=10,
                ),
                on_change=lambda e: _on_perspective_change(e),
            )

        def _on_perspective_change(e) -> None:
            app_state.perspective = e.control.value
            refresh_view()
            page.update()

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
            )

        def _handle_post_send(pending_id: int) -> None:
            processed_ids, errors = _auto_receive_if_enabled()
            refresh_view()
            page.update()

            if errors:
                show_warning("Auto receive failed for: " + "; ".join(errors))

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
                show_warning(str(exc))
                return
            alice_input.value = ""
            _handle_post_send(int(pending["id"]))

        def on_send_bob(e) -> None:
            try:
                pending = self.send_message("bob", bob_input.value, bob_input.hint_text or "")
            except ValueError as exc:
                show_warning(str(exc))
                return
            bob_input.value = ""
            _handle_post_send(int(pending["id"]))

        def on_receive_pending(recipient: str, pending_id: int) -> None:
            try:
                self.receive_message(recipient, pending_id)
            except ValueError as exc:
                show_warning(str(exc))
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
                show_warning("Auto receive failed for: " + "; ".join(errors))
            if receive_step_visualization_checkbox.value:
                for pending_id in processed_ids:
                    _show_receive_step(pending_id)

        def on_reset_module(e) -> None:
            self._reset_session()
            refresh_view()
            page.update()

        auto_receive_checkbox.on_change = on_auto_receive_changed
        refresh_view()

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("SPQR Simulation", size=22, weight="bold"),
                        ft.Row(
                            controls=[
                                send_step_visualization_checkbox,
                                receive_step_visualization_checkbox,
                                auto_receive_checkbox,
                            ],
                            spacing=16,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        message_count,
                        perspective_selector,
                        ft.TextButton("Reset application", on_click=on_reset_module),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                visual_container,
            ],
            expand=True,
        )


SpqrModule = SPQRModule
