import flet as ft
from dataclasses import asdict

from components.state import DoubleRatchetState
from modules.base_module import BaseModule
from modules.double_ratchet_logic import (
    alice_receives_dh,
    alice_sends,
    bob_receives,
    bob_sends_with_dh_ratchet,
    initialize_session,
)
from modules.double_ratchet_view import build_visual
from modules.message_state import MessageState
from modules.party_state import PartyState


class DoubleRatchetModule(BaseModule):
    def __init__(self):
        self.session = DoubleRatchetState()
        initialize_session(self.session)

    def export_state(self) -> dict:
        return asdict(self.session)

    def import_state(self, data: dict) -> None:
        alice_data = data.get("alice", {})
        bob_data = data.get("bob", {})
        log_data = data.get("message_log", [])

        self.session = DoubleRatchetState(
            initializer=PartyState(
                name=alice_data.get("name", "Alice"),
                dh_private=alice_data.get("dh_private", ""),
                dh_public=alice_data.get("dh_public", ""),
                root_key=alice_data.get("root_key", "RK0"),
                sending_chain=alice_data.get("sending_chain", ""),
                receiving_chain=alice_data.get("receiving_chain", ""),
            ),
            responder=PartyState(
                name=bob_data.get("name", "Bob"),
                dh_private=bob_data.get("dh_private", ""),
                dh_public=bob_data.get("dh_public", ""),
                root_key=bob_data.get("root_key", "RK0"),
                sending_chain=bob_data.get("sending_chain", ""),
                receiving_chain=bob_data.get("receiving_chain", ""),
            ),
            message_log=[
                MessageState(
                    sender=msg.get("sender", ""),
                    receiver=msg.get("receiver", ""),
                    message_key=msg.get("message_key", ""),
                    cipher=msg.get("cipher", ""),
                    decrypted_by_bob=msg.get("decrypted_by_bob", ""),
                    decrypted_by_alice=msg.get("decrypted_by_alice", ""),
                )
                for msg in log_data
            ],
        )

    def send_message(self, app_state, sender: str) -> None:
        if sender == "alice":
            alice_sends(self.session)
            bob_receives(self.session)
        elif sender == "bob":
            # Keep your existing DH-ratchet behavior for Bob messages
            bob_sends_with_dh_ratchet(self.session)
            alice_receives_dh(self.session)

        app_state.current_step = len(self.session.message_log)

    def build(self, page, app_state):
        return ft.Column(
            controls=[
                ft.Text("Double Ratchet Simulation", size=22, weight="bold"),
                ft.Text(f"Messages exchanged: {len(self.session.message_log)}"),
                build_visual(self.session, app_state.perspective),
            ],
            expand=True,
        )

    # Keep compatibility with existing base/navigation calls if any remain
    def next_step(self, app_state):
        self.send_message(app_state, sender="alice")

    def prev_step(self, app_state):
        # Not reversible without full state history.
        pass
