import flet as ft
from dataclasses import asdict
from typing import Any

from components.data_classes import (
    DoubleRatchetState,
    Header,
    MessageState,
    PartyStateSnapshot,
    ReceiveStepVisualizationSnapshot,
    SendStepVisualizationSnapshot,
)
from modules.base_module import BaseModule
from modules.double_ratchet.logic import (
    RatchetEncrypt,
    RatchetReceiveKey,
    initialize_session,
)
from modules.double_ratchet import external as ext
from modules.double_ratchet.step_visualization import (
    show_receiving_step_visualization_dialog,
    show_sending_step_visualization_dialog,
)
from modules.double_ratchet.key_history import (
    initialize_key_history,
    track_keys_from_send_snapshot,
    track_keys_from_receive_snapshot,
)
from modules.double_ratchet.attacker_dashboard import build_attacker_dashboard, get_attacker_analysis
from modules.double_ratchet.view import build_visual
from components.data_classes import PartyState


def _encode_bytes(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    return value


def _decode_bytes(value: Any) -> Any:
    if isinstance(value, dict) and len(value) == 1 and isinstance(value.get("__bytes__"), str):
        try:
            return bytes.fromhex(value["__bytes__"])
        except ValueError:
            return b""
    return value


def _serialize_party(state: PartyState) -> dict:
    skipped = [
        {
            "dh": dh,
            "n": n,
            "mk": _encode_bytes(mk),
        }
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
    }


def _deserialize_party(data: dict, default_name: str) -> PartyState:
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
    )


def _serialize_message(message: MessageState) -> dict:
    return {
        "sender": message.sender,
        "receiver": message.receiver,
        "header": {
            "dh": message.header.dh,
            "pn": message.header.pn,
            "n": message.header.n,
        }
        if message.header is not None
        else None,
        "message_key": _encode_bytes(message.message_key),
        "cipher": _encode_bytes(message.cipher),
        "decrypted_by_bob": _encode_bytes(message.decrypted_by_bob),
        "decrypted_by_alice": _encode_bytes(message.decrypted_by_alice),
        "plaintext": _encode_bytes(message.plaintext),
        "seq_id": message.seq_id,
    }


def _deserialize_message(data: dict) -> MessageState:
    header_data = data.get("header")
    header = None
    if isinstance(header_data, dict):
        dh = header_data.get("dh")
        pn = header_data.get("pn")
        n = header_data.get("n")
        if isinstance(dh, str) and isinstance(pn, int) and isinstance(n, int):
            header = Header(dh=dh, pn=pn, n=n)

    plaintext = _decode_bytes(data.get("plaintext", b""))
    if not plaintext:
        plaintext = _decode_bytes(data.get("decrypted_by_alice", b"")) or _decode_bytes(data.get("decrypted_by_bob", b""))

    return MessageState(
        sender=data.get("sender", ""),
        receiver=data.get("receiver", ""),
        message_key=_decode_bytes(data.get("message_key", "")),
        cipher=_decode_bytes(data.get("cipher", "")),
        decrypted_by_bob=_decode_bytes(data.get("decrypted_by_bob", "")),
        decrypted_by_alice=_decode_bytes(data.get("decrypted_by_alice", "")),
        header=header,
        plaintext=plaintext,
        seq_id=data.get("seq_id", 0),
    )


class DoubleRatchetModule(BaseModule):
    def __init__(self):
        self.session = DoubleRatchetState()
        self.pending_messages: list[dict[str, Any]] = []
        self._next_pending_id = 1
        self._send_snapshots: dict[int, SendStepVisualizationSnapshot] = {}
        self._receive_snapshots: dict[int, ReceiveStepVisualizationSnapshot] = {}
        self._attacker_compromised_secrets: dict[str, dict[str, Any]] = {}
        self._initial_warning_shown = False
        initialize_session(self.session)
        initialize_key_history(self.session)

    def export_state(self) -> dict:
        return {
            "initializer": _serialize_party(self.session.initializer),
            "responder": _serialize_party(self.session.responder),
            "message_log": [
                _serialize_message(message)
                for message in self.session.message_log
            ],
            "pending_messages": [
                {
                    "id": pending["id"],
                    "sender": pending["sender"],
                    "receiver": pending["receiver"],
                    "header": {
                        "dh": pending["header"].dh,
                        "pn": pending["header"].pn,
                        "n": pending["header"].n,
                    },
                    "cipher": _encode_bytes(pending["cipher"]),
                    "plaintext": _encode_bytes(pending.get("plaintext", b"")),
                }
                for pending in self.pending_messages
            ],
        }

    def import_state(self, data: dict) -> None:
        alice_data = data.get("initializer", {})
        bob_data = data.get("responder", {})
        log_data = data.get("message_log", [])
        pending_data = data.get("pending_messages", [])

        self.session = DoubleRatchetState(
            initializer=_deserialize_party(alice_data, "Alice"),
            responder=_deserialize_party(bob_data, "Bob"),
            message_log=[
                _deserialize_message(msg)
                for msg in log_data
                if isinstance(msg, dict)
            ],
        )

        self.pending_messages = []
        for pending in pending_data:
            if not isinstance(pending, dict):
                continue

            header_data = pending.get("header")
            if not isinstance(header_data, dict):
                continue

            sender = pending.get("sender")
            receiver = pending.get("receiver")
            pending_id = pending.get("id")
            header_dh = header_data.get("dh")
            header_pn = header_data.get("pn")
            header_n = header_data.get("n")

            if not isinstance(sender, str) or not isinstance(receiver, str):
                continue
            if not isinstance(pending_id, int):
                continue
            if not isinstance(header_dh, str) or not isinstance(header_pn, int) or not isinstance(header_n, int):
                continue

            self.pending_messages.append(
                {
                    "id": pending_id,
                    "sender": sender,
                    "receiver": receiver,
                    "header": Header(dh=header_dh, pn=header_pn, n=header_n),
                    "cipher": _decode_bytes(pending.get("cipher")),
                    "plaintext": _decode_bytes(pending.get("plaintext", b"")),
                }
            )

        max_log_seq_id = max((msg.seq_id for msg in self.session.message_log), default=0)
        max_pending_seq_id = max((item["id"] for item in self.pending_messages), default=0)
        self._next_pending_id = max(max_log_seq_id, max_pending_seq_id) + 1

    def _build_hint_message(self, sender: str) -> str:
        sender_key = sender.lower()
        if sender_key == "alice":
            next_index = self._get_party("alice").Ns + 1
            return f"Alice message #{next_index} to Bob"
        if sender_key == "bob":
            next_index = self._get_party("bob").Ns + 1
            return f"Bob message #{next_index} to Alice"
        return ""

    def _get_party(self, name: str) -> PartyState:
        normalized = name.lower()
        if self.session.initializer.name.lower() == normalized:
            return self.session.initializer
        if self.session.responder.name.lower() == normalized:
            return self.session.responder
        raise ValueError(f"Unknown party: {name}")

    def _reset_session_with_initializer(self, initializer_name: str) -> None:
        if initializer_name.lower() == "bob":
            initializer = PartyState("Bob")
            responder = PartyState("Alice")
        else:
            initializer = PartyState("Alice")
            responder = PartyState("Bob")

        self.session = DoubleRatchetState(
            initializer=initializer,
            responder=responder,
            message_log=[],
        )
        self.pending_messages = []
        self._next_pending_id = 1
        self._send_snapshots = {}
        self._receive_snapshots = {}
        initialize_session(self.session)
        initialize_key_history(self.session)

    def _build_initializer_switch_warning(self, old_initializer: str, new_initializer: str) -> str:
        template = f"Session initializer switched from {old_initializer} to {new_initializer}.\n" if old_initializer and new_initializer else ""
        assumption = "This simulation now assumes both parties (at least the sender) already know each other's public DH key and share an initial secret."
        return template + assumption

    def _initializer_sent_count(self) -> int:
        initializer_name = self.session.initializer.name
        delivered_count = sum(
            1
            for message in self.session.message_log
            if message.sender == initializer_name
        )
        pending_count = sum(
            1
            for pending in self.pending_messages
            if pending.get("sender") == initializer_name
        )
        return delivered_count + pending_count

    def _snapshot_party_state(self, state: PartyState) -> PartyStateSnapshot:
        return PartyStateSnapshot(
            DHs_public=state.DHs.public if state.DHs is not None else "",
            DHs_private=state.DHs.private if state.DHs is not None else "",
            DHr=state.DHr,
            RK=state.RK,
            CKs=state.CKs,
            CKr=state.CKr,
            Ns=state.Ns,
            Nr=state.Nr,
            PN=state.PN,
        )

    def receive_message(self, recipient: str, pending_id: int) -> ReceiveStepVisualizationSnapshot | None:
        recipient_name = "Alice" if recipient.lower() == "alice" else "Bob"

        pending = next(
            (
                item
                for item in self.pending_messages
                if item["id"] == pending_id and item["receiver"] == recipient_name
            ),
            None,
        )
        if pending is None:
            return None

        receiver_state = self._get_party(recipient_name)
        before_snapshot = self._snapshot_party_state(receiver_state)
        header = pending["header"]
        cipher = pending["cipher"]
        skipped_key_hit = (header.dh, header.n) in receiver_state.MKSKIPPED
        dh_ratchet_needed = (not skipped_key_hit) and (header.dh != before_snapshot.DHr)
        if skipped_key_hit:
            fast_forward_count = 0
            fast_forward_from_nr = before_snapshot.Nr
            fast_forward_to_nr = before_snapshot.Nr
        elif dh_ratchet_needed:
            fast_forward_count = max(0, header.n)
            fast_forward_from_nr = 0
            fast_forward_to_nr = header.n
        else:
            fast_forward_count = max(0, header.n - before_snapshot.Nr)
            fast_forward_from_nr = before_snapshot.Nr
            fast_forward_to_nr = before_snapshot.Nr + fast_forward_count
        associated_data = b""
        receive_trace: dict[str, Any] = {}
        mk = RatchetReceiveKey(receiver_state, header, trace=receive_trace)
        decrypted = ext.DECRYPT(mk, cipher, ext.CONCAT(associated_data, header))

        self.session.message_log.append(
            MessageState(
                sender=pending["sender"],
                receiver=pending["receiver"],
                message_key=mk,
                cipher=cipher,
                decrypted_by_bob=decrypted if recipient_name == "Bob" else b"",
                decrypted_by_alice=decrypted if recipient_name == "Alice" else b"",
                header=header,
                plaintext=pending.get("plaintext", b"") or decrypted,
                seq_id=pending_id,
            )
        )
        self.pending_messages = [item for item in self.pending_messages if item["id"] != pending_id]

        after_snapshot = self._snapshot_party_state(receiver_state)

        snapshot = ReceiveStepVisualizationSnapshot(
            sender=pending["sender"],
            receiver=pending["receiver"],
            pending_id=pending_id,
            header=header,
            cipher=cipher,
            mk=mk,
            decrypted=decrypted,
            plaintext=pending.get("plaintext", b"") or decrypted,
            skipped_key_hit=skipped_key_hit,
            dh_ratchet_needed=dh_ratchet_needed,
            fast_forward_count=fast_forward_count,
            fast_forward_from_nr=fast_forward_from_nr,
            fast_forward_to_nr=fast_forward_to_nr,
            ckr_after_double_ratchet=receive_trace.get("ckr_after_double_ratchet"),
            ckr_before_kdf_ck=receive_trace.get("ckr_before_kdf_ck"),
            before=before_snapshot,
            after=after_snapshot,
        )

        # Track key generation from this receive step.
        step_number = len(self._receive_snapshots) + 1
        track_keys_from_receive_snapshot(receiver_state, step_number, snapshot, pending_id)

        self._receive_snapshots[pending_id] = snapshot
        return snapshot

    def send_message(
        self,
        app_state=None,
        sender: str = "alice",
        plaintext: str | None = None,
        fallback_plaintext: str | None = None,
    ) -> SendStepVisualizationSnapshot | None:
        sender_key = sender.lower()
        if sender_key not in {"alice", "bob"}:
            return None

        text_to_send = (plaintext or "").strip()
        if not text_to_send:
            text_to_send = (fallback_plaintext or "").strip()
        if not text_to_send:
            return None

        initializer_before = self.session.initializer.name
        initializer_switch_warning: str | None = None

        if not self.session.message_log and not self.pending_messages and sender_key == "bob":
            self._reset_session_with_initializer("bob")
            initializer_after = self.session.initializer.name
            if initializer_after != initializer_before:
                initializer_switch_warning = self._build_initializer_switch_warning(initializer_before, initializer_after)

        sender_state = self._get_party(sender_key)
        sender_name = "Alice" if sender_key == "alice" else "Bob"
        receiver_name = "Bob" if sender_key == "alice" else "Alice"

        if sender_state.CKs is None:
            if self._initializer_sent_count() > 0:
                raise ValueError("Cannot send yet. Receive at least one pending message first.")

            initializer_before = self.session.initializer.name
            self._reset_session_with_initializer(sender_key)
            initializer_after = self.session.initializer.name
            if initializer_after != initializer_before:
                initializer_switch_warning = self._build_initializer_switch_warning(initializer_before, initializer_after)
            sender_state = self._get_party(sender_key)
            sender_name = "Alice" if sender_key == "alice" else "Bob"
            receiver_name = "Bob" if sender_key == "alice" else "Alice"

        associated_data = b""
        plaintext_bytes = text_to_send.encode("utf-8")

        before_snapshot = self._snapshot_party_state(sender_state)

        header, cipher, mk = RatchetEncrypt(sender_state, plaintext_bytes, associated_data)
        pending_id = self._next_pending_id
        self.pending_messages.append(
            {
                "id": pending_id,
                "sender": sender_name,
                "receiver": receiver_name,
                "header": header,
                "cipher": cipher,
                "plaintext": plaintext_bytes,
            }
        )
        self._next_pending_id += 1

        after_snapshot = self._snapshot_party_state(sender_state)

        snapshot = SendStepVisualizationSnapshot(
            sender=sender_name,
            receiver=receiver_name,
            plaintext=plaintext_bytes,
            header=header,
            cipher=cipher,
            mk=mk,
            pending_id=pending_id,
            before=before_snapshot,
            after=after_snapshot,
            initializer_switch_warning=initializer_switch_warning,
        )

        # Track key generation from this send step.
        step_number = len(self._send_snapshots) + 1
        track_keys_from_send_snapshot(sender_state, step_number, snapshot, pending_id)

        return snapshot

    def _auto_receive_all_pending(self) -> None:
        for pending in self.pending_messages:
            pending_id = pending.get("id")
            recipient = pending.get("receiver")
            if not isinstance(pending_id, int) or not isinstance(recipient, str):
                continue
            self.receive_message(recipient, pending_id)

    def build(self, page, app_state, perspective_selector: ft.Control | None = None):
        message_count = ft.Text(f"Messages exchanged: {len(self.session.message_log)}")
        send_step_visualization_checkbox = ft.Checkbox(label="Show sending steps visualisation", value=False)
        receive_step_visualization_checkbox = ft.Checkbox(label="Show receiving steps visualisation", value=False)
        auto_receive_checkbox = ft.Checkbox(label="Auto receive", value=False)
        auto_receive_user_enabled = bool(auto_receive_checkbox.value)
        alice_input = ft.TextField(dense=True, expand=True)
        bob_input = ft.TextField(dense=True, expand=True)
        visual_container = ft.Container(expand=True)

        def show_warning(message: str):
            def close_dialog(e):
                dialog.open = False
                page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Warning"),
                content=ft.Text(message),
                actions=[
                    ft.TextButton("OK", on_click=close_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def show_step_visualization(
            step_data: SendStepVisualizationSnapshot,
            on_close=None,
        ) -> None:
            show_sending_step_visualization_dialog(page, step_data, on_close=on_close)

        def show_receive_step_visualization(step_data: ReceiveStepVisualizationSnapshot) -> None:
            show_receiving_step_visualization_dialog(page, step_data)

        def _auto_show_receive_visualization_after_send(step_data: SendStepVisualizationSnapshot | None) -> None:
            if step_data is None:
                return
            if not receive_step_visualization_checkbox.value:
                return
            if not _effective_auto_receive_enabled():
                return
            if not _is_global_or_recipient_perspective(step_data):
                return
            receive_snapshot = self._receive_snapshots.get(step_data.pending_id)
            if receive_snapshot is None:
                return
            show_receive_step_visualization(receive_snapshot)

        def _is_attacker_perspective() -> bool:
            return app_state.perspective == "attacker"

        def _is_global_or_recipient_perspective(step_data: SendStepVisualizationSnapshot) -> bool:
            recipient_key = step_data.receiver.lower()
            return app_state.perspective in {"global", recipient_key}

        def _effective_auto_receive_enabled() -> bool:
            return _is_attacker_perspective() or auto_receive_user_enabled

        def _sync_auto_receive_checkbox_state() -> None:
            if _is_attacker_perspective():
                auto_receive_checkbox.value = True
                auto_receive_checkbox.disabled = True
                return
            auto_receive_checkbox.value = auto_receive_user_enabled
            auto_receive_checkbox.disabled = False

        def _auto_receive_if_enabled(step_data: SendStepVisualizationSnapshot | None = None) -> None:
            if not _effective_auto_receive_enabled():
                return
            if step_data is not None:
                self.receive_message(step_data.receiver, step_data.pending_id)
                return
            if self.pending_messages:
                self._auto_receive_all_pending()

        def refresh_view() -> None:
            _sync_auto_receive_checkbox_state()
            _auto_receive_if_enabled()
            message_count.value = f"Messages exchanged: {len(self.session.message_log)}"
            alice_input.hint_text = self._build_hint_message("alice")
            bob_input.hint_text = self._build_hint_message("bob")
            attacker_dashboard = None
            attacker_analysis = None
            if app_state.perspective == "attacker":
                attacker_dashboard = build_attacker_dashboard(
                    page,
                    self.session,
                    self.pending_messages,
                    self._attacker_compromised_secrets,
                    lambda value: setattr(self, "_attacker_compromised_secrets", value),
                    refresh_view,
                )
                attacker_analysis = get_attacker_analysis(
                    self.session,
                    self.pending_messages,
                    self._attacker_compromised_secrets,
                )
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
                on_show_send_visualization=lambda sid: show_step_visualization(
                    self._send_snapshots[sid]
                ) if sid in self._send_snapshots else None,
                on_show_receive_visualization=lambda sid: show_receive_step_visualization(
                    self._receive_snapshots[sid]
                ) if sid in self._receive_snapshots else None,
                attacker_dashboard=attacker_dashboard,
                attacker_analysis=attacker_analysis,
            )

        def on_send_alice(e) -> None:
            try:
                step_data = self.send_message(
                    sender="alice",
                    plaintext=alice_input.value,
                    fallback_plaintext=alice_input.hint_text,
                )
            except ValueError as exc:
                show_warning(str(exc))
                return
            alice_input.value = ""
            _auto_receive_if_enabled(step_data)
            refresh_view()
            page.update()
            warning_message = step_data.initializer_switch_warning if step_data is not None else None
            if warning_message:
                show_warning(warning_message)
            if step_data is not None:
                self._send_snapshots[step_data.pending_id] = step_data
            if send_step_visualization_checkbox.value and step_data is not None and not warning_message:
                show_step_visualization(
                    step_data,
                    on_close=lambda: _auto_show_receive_visualization_after_send(step_data),
                )
            elif not warning_message:
                _auto_show_receive_visualization_after_send(step_data)

        def on_send_bob(e) -> None:
            try:
                step_data = self.send_message(
                    sender="bob",
                    plaintext=bob_input.value,
                    fallback_plaintext=bob_input.hint_text,
                )
            except ValueError as exc:
                show_warning(str(exc))
                return
            bob_input.value = ""
            _auto_receive_if_enabled(step_data)
            refresh_view()
            page.update()
            warning_message = step_data.initializer_switch_warning if step_data is not None else None
            if warning_message:
                show_warning(warning_message)
            if step_data is not None:
                self._send_snapshots[step_data.pending_id] = step_data
            if send_step_visualization_checkbox.value and step_data is not None and not warning_message:
                show_step_visualization(
                    step_data,
                    on_close=lambda: _auto_show_receive_visualization_after_send(step_data),
                )
            elif not warning_message:
                _auto_show_receive_visualization_after_send(step_data)

        def on_receive_pending(recipient: str, pending_id: int) -> None:
            step_data = self.receive_message(recipient, pending_id)
            refresh_view()
            page.update()
            if receive_step_visualization_checkbox.value and step_data is not None:
                show_receive_step_visualization(step_data)

        def on_reset_module(e) -> None:
            self._reset_session_with_initializer("alice")
            self._attacker_compromised_secrets.clear()
            refresh_view()
            page.update()
            show_warning(self._build_initializer_switch_warning("", ""))

        def on_auto_receive_changed(e) -> None:
            nonlocal auto_receive_user_enabled
            if not _is_attacker_perspective():
                auto_receive_user_enabled = bool(auto_receive_checkbox.value)
            refresh_view()
            page.update()

        auto_receive_checkbox.on_change = on_auto_receive_changed

        refresh_view()
        if not self._initial_warning_shown:
            show_warning(self._build_initializer_switch_warning("", ""))
            self._initial_warning_shown = True

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Double Ratchet Simulation", size=22, weight="bold"),
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
                        perspective_selector if perspective_selector is not None else ft.Container(expand=True),
                        ft.TextButton("Reset application", on_click=on_reset_module),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                visual_container,
            ],
            expand=True,
        )
