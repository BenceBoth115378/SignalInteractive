import flet as ft
from dataclasses import asdict
from typing import Any

from components.data_classes import DoubleRatchetState, MessageState
from modules.base_module import BaseModule
from modules.double_ratchet.logic import (
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

    def build(self, page, app_state):
        return ft.Column(
            controls=[
                ft.Text("Double Ratchet Simulation", size=22, weight="bold"),
                ft.Text(f"Messages exchanged: {len(self.session.message_log)}"),
                build_visual(self.session, app_state.perspective, page),
            ],
            expand=True,
        )
