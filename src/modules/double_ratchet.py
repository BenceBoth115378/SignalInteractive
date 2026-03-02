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
from modules.double_ratchet_view import build_explanation, build_visual
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
            alice=PartyState(
                name=alice_data.get("name", "Alice"),
                dh_private=alice_data.get("dh_private", ""),
                dh_public=alice_data.get("dh_public", ""),
                root_key=alice_data.get("root_key", "RK0"),
                sending_chain=alice_data.get("sending_chain", ""),
                receiving_chain=alice_data.get("receiving_chain", ""),
            ),
            bob=PartyState(
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

    def build(self, page, app_state):
        return ft.Column(
            controls=[
                ft.Text("Double Ratchet Simulation", size=22, weight="bold"),
                build_visual(self.session, app_state.perspective),
                ft.Divider(),
                build_explanation(app_state.current_step),
            ],
            expand=True,
        )

    def next_step(self, app_state):
        actions = {
            0: alice_sends,
            1: bob_receives,
            2: bob_sends_with_dh_ratchet,
            3: alice_receives_dh,
        }
        action = actions.get(app_state.current_step)
        if action:
            action(self.session)

        app_state.current_step += 1

    def prev_step(self, app_state):
        if app_state.current_step > 0:
            app_state.current_step -= 1
