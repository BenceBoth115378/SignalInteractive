import flet as ft
from dataclasses import asdict
from typing import Any

from components.data_classes import (
    DHKeyPair,
    DoubleRatchetState,
    Header,
    MessageState,
    PartyStateSnapshot,
    ReceiveStepVisualizationSnapshot,
    SendStepVisualizationSnapshot,
)
from modules.base_module import BaseModule
from modules.double_ratchet.logic import (
    RatchetInitBob,
    RatchetEncrypt,
    RatchetReceiveKey,
    initialize_session_from_x3dh,
)
from modules import external as ext
from modules.x3dh.logic import (
    alice_calculates_associated_data,
    alice_generates_ek_and_derives_sk,
    alice_sends_initial_message,
    alice_verifies_bundle_signature,
    generate_alice_registration_material,
    new_state as new_x3dh_state,
    request_bob_bundle_for_alice,
    upload_alice_initial_bundle,
)
from modules.double_ratchet.step_visualization import (
    show_alice_x3dh_bootstrap_visualization_dialog,
    show_bob_x3dh_bootstrap_visualization_dialog,
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
        self._session_ad: bytes = b""
        self._x3dh_initial_header: dict[str, Any] | None = None
        self._x3dh_bob_spk_pair: DHKeyPair | None = None
        self._x3dh_shared_secret: bytes | None = None
        self._x3dh_state_data: dict[str, Any] | None = None
        self._x3dh_bob_initialized: bool = False
        self._pending_show_alice_x3dh_bootstrap: bool = True
        self._last_bob_bootstrap_info: dict[str, Any] | None = None
        self._reset_session_with_initializer("alice")

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
                    "x3dh_header": pending.get("x3dh_header"),
                }
                for pending in self.pending_messages
            ],
            "session_ad": _encode_bytes(self._session_ad),
            "x3dh_initial_header": self._x3dh_initial_header,
            "x3dh_bob_spk_pair": asdict(self._x3dh_bob_spk_pair) if self._x3dh_bob_spk_pair is not None else None,
            "x3dh_shared_secret": _encode_bytes(self._x3dh_shared_secret),
            "x3dh_state_data": self._x3dh_state_data,
            "x3dh_bob_initialized": self._x3dh_bob_initialized,
            "pending_show_alice_x3dh_bootstrap": self._pending_show_alice_x3dh_bootstrap,
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
                    "x3dh_header": pending.get("x3dh_header") if isinstance(pending.get("x3dh_header"), dict) else None,
                }
            )

        self._session_ad = _decode_bytes(data.get("session_ad", b"")) or b""
        self._x3dh_initial_header = data.get("x3dh_initial_header") if isinstance(data.get("x3dh_initial_header"), dict) else None
        bob_spk_pair_data = data.get("x3dh_bob_spk_pair")
        if isinstance(bob_spk_pair_data, dict):
            private = bob_spk_pair_data.get("private")
            public = bob_spk_pair_data.get("public")
            if isinstance(private, str) and isinstance(public, str) and private and public:
                self._x3dh_bob_spk_pair = DHKeyPair(private=private, public=public)
            else:
                self._x3dh_bob_spk_pair = None
        else:
            self._x3dh_bob_spk_pair = None
        self._x3dh_shared_secret = _decode_bytes(data.get("x3dh_shared_secret"))
        if self._x3dh_shared_secret == b"":
            self._x3dh_shared_secret = None
        self._x3dh_state_data = data.get("x3dh_state_data") if isinstance(data.get("x3dh_state_data"), dict) else None
        self._x3dh_bob_initialized = bool(data.get("x3dh_bob_initialized", False))
        self._pending_show_alice_x3dh_bootstrap = bool(data.get("pending_show_alice_x3dh_bootstrap", True))
        self._last_bob_bootstrap_info = None

        max_log_seq_id = max((msg.seq_id for msg in self.session.message_log), default=0)
        max_pending_seq_id = max((item["id"] for item in self.pending_messages), default=0)
        self._next_pending_id = max(max_log_seq_id, max_pending_seq_id) + 1

        if self._x3dh_shared_secret is None or self._x3dh_bob_spk_pair is None:
            self._reset_session_with_initializer("alice")

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
        _ = initializer_name
        initializer = PartyState("Alice")
        responder = PartyState("Bob")

        x3dh_state = new_x3dh_state()
        generate_alice_registration_material(x3dh_state)
        upload_alice_initial_bundle(x3dh_state)
        request_bob_bundle_for_alice(x3dh_state)
        alice_verifies_bundle_signature(x3dh_state)
        alice_generates_ek_and_derives_sk(x3dh_state)
        alice_calculates_associated_data(x3dh_state)
        alice_sends_initial_message(x3dh_state, "")

        derived = x3dh_state.alice_derived if isinstance(x3dh_state.alice_derived, dict) else None
        initial_message = x3dh_state.initial_message if isinstance(x3dh_state.initial_message, dict) else None
        x3dh_header = initial_message.get("header") if isinstance(initial_message, dict) and isinstance(initial_message.get("header"), dict) else None
        bob_local = x3dh_state.bob_local if isinstance(x3dh_state.bob_local, dict) else None
        bob_spk = bob_local.get("signed_prekey") if isinstance(bob_local, dict) and isinstance(bob_local.get("signed_prekey"), dict) else None

        if not isinstance(derived, dict) or not isinstance(x3dh_header, dict) or not isinstance(bob_spk, dict):
            raise ValueError("Could not initialize Double Ratchet because X3DH bootstrap is incomplete.")

        shared_secret_hex = derived.get("shared_secret")
        associated_data_hex = derived.get("associated_data")
        bob_spk_public = bob_spk.get("public")
        bob_spk_private = bob_spk.get("private")
        if not all(
            isinstance(value, str) and value
            for value in [shared_secret_hex, associated_data_hex, bob_spk_public, bob_spk_private]
        ):
            raise ValueError("Could not initialize Double Ratchet because X3DH output values are invalid.")

        shared_secret = bytes.fromhex(shared_secret_hex)
        associated_data = bytes.fromhex(associated_data_hex)
        bob_spk_pair = DHKeyPair(private=bob_spk_private, public=bob_spk_public)

        self.session = DoubleRatchetState(
            initializer=initializer,
            responder=responder,
            message_log=[],
        )
        self.pending_messages = []
        self._next_pending_id = 1
        self._send_snapshots = {}
        self._receive_snapshots = {}
        initialize_session_from_x3dh(self.session, shared_secret, bob_spk_pair)

        bob_state = self._get_party("bob")
        bob_state.DHs = None
        bob_state.DHr = None
        bob_state.RK = b""
        bob_state.CKs = None
        bob_state.CKr = None
        bob_state.Ns = 0
        bob_state.Nr = 0
        bob_state.PN = 0
        bob_state.MKSKIPPED = {}

        self._session_ad = associated_data
        self._x3dh_initial_header = x3dh_header
        self._x3dh_bob_spk_pair = bob_spk_pair
        self._x3dh_shared_secret = shared_secret
        self._x3dh_state_data = asdict(x3dh_state)
        self._x3dh_bob_initialized = False
        self._pending_show_alice_x3dh_bootstrap = True
        self._last_bob_bootstrap_info = None
        initialize_key_history(self.session)

    def _complete_bob_x3dh_bootstrap_from_header(self, x3dh_header: dict[str, Any]) -> None:
        if self._x3dh_bob_initialized:
            return

        if self._x3dh_bob_spk_pair is None or self._x3dh_shared_secret is None:
            raise ValueError("Bob cannot complete X3DH bootstrap because required state is missing.")

        expected_spk_public = self._x3dh_bob_spk_pair.public
        header_spk_public = x3dh_header.get("bob_spk_public")
        if not isinstance(header_spk_public, str) or header_spk_public != expected_spk_public:
            raise ValueError("X3DH header does not match Bob signed prekey.")

        bob_state = self._get_party("bob")
        RatchetInitBob(bob_state, self._x3dh_shared_secret, self._x3dh_bob_spk_pair)
        self._x3dh_bob_initialized = True
        self._last_bob_bootstrap_info = {"x3dh_header": x3dh_header}

    def _build_initializer_switch_warning(self, old_initializer: str, new_initializer: str) -> str:
        template = f"Session initializer switched from {old_initializer} to {new_initializer}.\n" if old_initializer and new_initializer else ""
        assumption = "Double Ratchet now always starts from a fresh X3DH run; Bob completes X3DH bootstrap on first receive."
        return template + assumption

    def _initializer_sent_count(self) -> int:
        return len(self.session.message_log) + len(self.pending_messages)

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

        if recipient_name == "Bob" and not self._x3dh_bob_initialized:
            x3dh_header = pending.get("x3dh_header")
            if not isinstance(x3dh_header, dict):
                raise ValueError("Bob cannot receive the first message because X3DH header is missing.")
            self._complete_bob_x3dh_bootstrap_from_header(x3dh_header)

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
        associated_data = self._session_ad
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

        if sender_key == "bob" and not self._x3dh_bob_initialized:
            raise ValueError("Bob can send only after receiving Alice's first X3DH initialized message.")

        sender_state = self._get_party(sender_key)
        sender_name = "Alice" if sender_key == "alice" else "Bob"
        receiver_name = "Bob" if sender_key == "alice" else "Alice"

        if sender_state.CKs is None:
            raise ValueError("Cannot send yet. Receive at least one pending message first.")

        associated_data = self._session_ad
        plaintext_bytes = text_to_send.encode("utf-8")
        is_first_alice_message = sender_key == "alice" and not self.session.message_log and not self.pending_messages
        include_x3dh_header = sender_key == "alice" and not self._x3dh_bob_initialized and isinstance(self._x3dh_initial_header, dict)
        if is_first_alice_message:
            ad_prefix = b"X3DH_AD:" + self._session_ad.hex().encode("utf-8") + b"\n\n"
            plaintext_bytes = ad_prefix + plaintext_bytes

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
                "x3dh_header": self._x3dh_initial_header if include_x3dh_header else None,
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
            initializer_switch_warning=None,
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

        def show_initial_warning_with_bootstrap_option(message: str) -> None:
            show_bootstrap_checkbox = ft.Checkbox(
                label="Show Alice X3DH bootstrap steps after closing",
                value=True,
            )

            def close_dialog(e):
                dialog.open = False
                page.update()
                if show_bootstrap_checkbox.value and self._pending_show_alice_x3dh_bootstrap:
                    self._pending_show_alice_x3dh_bootstrap = False
                    show_alice_x3dh_bootstrap_visualization()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Warning"),
                content=ft.Column(
                    controls=[
                        ft.Text(message),
                        show_bootstrap_checkbox,
                    ],
                    tight=True,
                    spacing=8,
                ),
                actions=[
                    ft.TextButton("OK", on_click=close_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        if perspective_selector is None:
            def _on_perspective_change_local(e):
                app_state.perspective = e.control.value
                refresh_view()
                page.update()

            perspective_selector = ft.RadioGroup(
                value=app_state.perspective,
                content=ft.Row(
                    controls=[
                        ft.Radio(value="global", label="Global"),
                        ft.Radio(value="alice", label="Alice"),
                        ft.Radio(value="bob", label="Bob"),
                        ft.Radio(value="attacker", label="Attacker"),
                    ],
                    spacing=10,
                ),
                on_change=_on_perspective_change_local,
            )

        def show_step_visualization(
            step_data: SendStepVisualizationSnapshot,
            on_close=None,
        ) -> None:
            show_sending_step_visualization_dialog(page, step_data, on_close=on_close)

        def show_receive_step_visualization(step_data: ReceiveStepVisualizationSnapshot) -> None:
            show_receiving_step_visualization_dialog(page, step_data)

        def show_alice_x3dh_bootstrap_visualization() -> None:
            alice_state = self._get_party("alice")
            show_alice_x3dh_bootstrap_visualization_dialog(
                page,
                x3dh_state_data=self._x3dh_state_data,
                rk_after_init=alice_state.RK,
                cks_after_init=alice_state.CKs,
                alice_dhs_pub=alice_state.DHs.public if alice_state.DHs is not None else "",
                alice_dhs_priv=alice_state.DHs.private if alice_state.DHs is not None else "",
                bob_spk_pub=alice_state.DHr if isinstance(alice_state.DHr, str) else "",
                session_ad=self._session_ad,
            )

        def show_bob_x3dh_bootstrap_visualization(
            x3dh_header: dict[str, Any],
            on_close=None,
        ) -> None:
            bob_spk_public = self._x3dh_bob_spk_pair.public if self._x3dh_bob_spk_pair is not None else ""
            bob_spk_private = self._x3dh_bob_spk_pair.private if self._x3dh_bob_spk_pair is not None else ""
            bob_ik_pub = ""
            bob_ik_priv = ""
            if isinstance(self._x3dh_state_data, dict):
                bob_local = self._x3dh_state_data.get("bob_local")
                if isinstance(bob_local, dict):
                    bob_identity = bob_local.get("identity_dh")
                    if isinstance(bob_identity, dict):
                        bob_ik_pub = bob_identity.get("public") if isinstance(bob_identity.get("public"), str) else ""
                        bob_ik_priv = bob_identity.get("private") if isinstance(bob_identity.get("private"), str) else ""
            show_bob_x3dh_bootstrap_visualization_dialog(
                page,
                x3dh_header=x3dh_header,
                shared_secret=self._x3dh_shared_secret,
                session_ad=self._session_ad,
                bob_spk_public=bob_spk_public,
                bob_spk_priv=bob_spk_private,
                bob_ik_pub=bob_ik_pub,
                bob_ik_priv=bob_ik_priv,
                on_close=on_close,
            )

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
            bob_bootstrap = self._last_bob_bootstrap_info
            if receive_step_visualization_checkbox.value and isinstance(bob_bootstrap, dict) and receive_snapshot.receiver == "Bob" and isinstance(bob_bootstrap.get("x3dh_header"), dict):
                show_bob_x3dh_bootstrap_visualization(
                    bob_bootstrap["x3dh_header"],
                    on_close=lambda: show_receive_step_visualization(receive_snapshot),
                )
                self._last_bob_bootstrap_info = None
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
                on_show_alice_x3dh_bootstrap=show_alice_x3dh_bootstrap_visualization,
                on_show_bob_x3dh_bootstrap=lambda msg: show_bob_x3dh_bootstrap_visualization(
                    msg.header._asdict() if hasattr(msg, "header") and hasattr(msg.header, "_asdict") else {},
                ),
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
            pending = next((item for item in self.pending_messages if item.get("id") == pending_id), None)
            will_show_bob_bootstrap = receive_step_visualization_checkbox.value and recipient.lower() == "bob" and not self._x3dh_bob_initialized and isinstance(pending, dict) and isinstance(pending.get("x3dh_header"), dict)
            x3dh_header_for_bob = pending.get("x3dh_header") if isinstance(pending, dict) else None

            step_data = self.receive_message(recipient, pending_id)
            refresh_view()
            page.update()
            if will_show_bob_bootstrap and isinstance(x3dh_header_for_bob, dict):
                if receive_step_visualization_checkbox.value and step_data is not None:
                    show_bob_x3dh_bootstrap_visualization(
                        x3dh_header_for_bob,
                        on_close=lambda: show_receive_step_visualization(step_data),
                    )
                else:
                    show_bob_x3dh_bootstrap_visualization(x3dh_header_for_bob)
                self._last_bob_bootstrap_info = None
                return
            if receive_step_visualization_checkbox.value and step_data is not None:
                show_receive_step_visualization(step_data)

        def on_reset_module(e) -> None:
            self._reset_session_with_initializer("alice")
            self._attacker_compromised_secrets.clear()
            refresh_view()
            page.update()
            show_initial_warning_with_bootstrap_option("Double Ratchet reset completed with a fresh X3DH bootstrap.")

        def on_auto_receive_changed(e) -> None:
            nonlocal auto_receive_user_enabled
            if not _is_attacker_perspective():
                auto_receive_user_enabled = bool(auto_receive_checkbox.value)
            refresh_view()
            page.update()

        auto_receive_checkbox.on_change = on_auto_receive_changed

        refresh_view()
        if not self._initial_warning_shown:
            show_initial_warning_with_bootstrap_option(self._build_initializer_switch_warning("", ""))
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
