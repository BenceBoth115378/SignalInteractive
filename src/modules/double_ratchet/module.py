import flet as ft
from dataclasses import asdict
from typing import Any

from components.data_classes import DoubleRatchetState, MessageState
from modules.base_module import BaseModule
from modules.double_ratchet.logic import (
    RatchetDecrypt,
    RatchetEncrypt,
    initialize_session,
)
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
        "message_key": _encode_bytes(message.message_key),
        "cipher": _encode_bytes(message.cipher),
        "decrypted_by_bob": _encode_bytes(message.decrypted_by_bob),
        "decrypted_by_alice": _encode_bytes(message.decrypted_by_alice),
    }


def _deserialize_message(data: dict) -> MessageState:
    return MessageState(
        sender=data.get("sender", ""),
        receiver=data.get("receiver", ""),
        message_key=_decode_bytes(data.get("message_key", "")),
        cipher=_decode_bytes(data.get("cipher", "")),
        decrypted_by_bob=_decode_bytes(data.get("decrypted_by_bob", "")),
        decrypted_by_alice=_decode_bytes(data.get("decrypted_by_alice", "")),
    )


class DoubleRatchetModule(BaseModule):
    def __init__(self):
        self.session = DoubleRatchetState()
        initialize_session(self.session)

    def export_state(self) -> dict:
        return {
            "initializer": _serialize_party(self.session.initializer),
            "responder": _serialize_party(self.session.responder),
            "message_log": [
                _serialize_message(message)
                for message in self.session.message_log
            ],
        }

    def import_state(self, data: dict) -> None:
        alice_data = data.get("initializer", {})
        bob_data = data.get("responder", {})
        log_data = data.get("message_log", [])

        self.session = DoubleRatchetState(
            initializer=_deserialize_party(alice_data, "Alice"),
            responder=_deserialize_party(bob_data, "Bob"),
            message_log=[
                _deserialize_message(msg)
                for msg in log_data
                if isinstance(msg, dict)
            ],
        )

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
        initialize_session(self.session)

    def send_message(
        self,
        app_state=None,
        sender: str = "alice",
        plaintext: str | None = None,
        fallback_plaintext: str | None = None,
    ) -> None:
        sender_key = sender.lower()
        if sender_key not in {"alice", "bob"}:
            return

        if not self.session.message_log and sender_key == "bob":
            self._reset_session_with_initializer("bob")

        sender_state = self._get_party(sender_key)
        receiver_state = self._get_party("bob" if sender_key == "alice" else "alice")
        sender_name = "Alice" if sender_key == "alice" else "Bob"
        receiver_name = "Bob" if sender_key == "alice" else "Alice"

        text_to_send = (plaintext or "").strip()
        if not text_to_send:
            text_to_send = (fallback_plaintext or "").strip()
        if not text_to_send:
            return

        associated_data = b""
        plaintext_bytes = text_to_send.encode("utf-8")

        header, cipher = RatchetEncrypt(sender_state, plaintext_bytes, associated_data)
        decrypted = RatchetDecrypt(receiver_state, header, cipher, associated_data)

        self.session.message_log.append(
            MessageState(
                sender=sender_name,
                receiver=receiver_name,
                message_key=b"",
                cipher=cipher,
                decrypted_by_bob=decrypted if receiver_name == "Bob" else b"",
                decrypted_by_alice=decrypted if receiver_name == "Alice" else b"",
            )
        )

    def build(self, page, app_state):
        message_count = ft.Text(f"Messages exchanged: {len(self.session.message_log)}")
        alice_input = ft.TextField(dense=True, expand=True)
        bob_input = ft.TextField(dense=True, expand=True)
        visual_container = ft.Container(expand=True)

        def refresh_view() -> None:
            message_count.value = f"Messages exchanged: {len(self.session.message_log)}"
            alice_input.hint_text = self._build_hint_message("alice")
            bob_input.hint_text = self._build_hint_message("bob")
            visual_container.content = build_visual(
                self.session,
                app_state.perspective,
                page,
                alice_input,
                bob_input,
                on_send_alice,
                on_send_bob,
            )

        def on_send_alice(e) -> None:
            self.send_message(
                sender="alice",
                plaintext=alice_input.value,
                fallback_plaintext=alice_input.hint_text,
            )
            alice_input.value = ""
            refresh_view()
            page.update()

        def on_send_bob(e) -> None:
            self.send_message(
                sender="bob",
                plaintext=bob_input.value,
                fallback_plaintext=bob_input.hint_text,
            )
            bob_input.value = ""
            refresh_view()
            page.update()

        refresh_view()

        return ft.Column(
            controls=[
                ft.Text("Double Ratchet Simulation", size=22, weight="bold"),
                message_count,
                visual_container,
            ],
            expand=True,
        )
