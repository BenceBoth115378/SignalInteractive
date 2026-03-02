import flet as ft
from dataclasses import asdict
from modules.base_module import BaseModule
from components.state import DoubleRatchetState
from modules.message_state import MessageState
from modules.party_state import PartyState
from modules.tooltip_helpers import (
    build_tooltip_text,
    get_tooltip_messages,
)


def fake_kdf(*inputs):
    return "KDF(" + "+".join(inputs) + ")"


def fake_dh(priv, pub):
    return f"DH({priv[:3]}x{pub[:3]})"


def derive_message_key(chain_key):
    mk = f"MK({chain_key})"
    next_ck = f"CK({chain_key})"
    return mk, next_ck


class DoubleRatchetModule(BaseModule):

    def __init__(self):
        self.session = DoubleRatchetState()
        self._initialize_session()


    def _initialize_session(self):
        alice = self.session.alice
        bob = self.session.bob

        alice.dh_private = "A0_priv"
        alice.dh_public = "A0_pub"

        bob.dh_private = "B0_priv"
        bob.dh_public = "B0_pub"

        alice.root_key = "RK0"
        bob.root_key = "RK0"

        alice.sending_chain = "CK_A0"
        alice.receiving_chain = "CK_A0"

        bob.sending_chain = "CK_A0"
        bob.receiving_chain = "CK_A0"

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

        step = app_state.current_step
        perspective = app_state.perspective

        content = ft.Column(
            controls=[
                ft.Text("Double Ratchet Simulation", size=22, weight="bold"),
                self._build_visual(perspective),
                ft.Divider(),
                self._build_explanation(step)
            ],
            expand=True
        )

        return content


    def next_step(self, app_state):
        step = app_state.current_step

        if step == 0:
            self._alice_sends()

        elif step == 1:
            self._bob_receives()

        elif step == 2:
            self._bob_sends_with_dh_ratchet()

        elif step == 3:
            self._alice_receives_dh()

        app_state.current_step += 1

    def prev_step(self, app_state):
        # For simplicity: no rollback yet
        if app_state.current_step > 0:
            app_state.current_step -= 1

    # --------------------------------
    # Protocol Actions
    # --------------------------------

    def _alice_sends(self):
        alice = self.session.alice

        mk, next_ck = derive_message_key(alice.sending_chain)

        self.session.message_log.append(
            MessageState(
                sender="Alice",
                receiver="Bob",
                message_key=mk,
                cipher=f"ENC({mk})",
            )
        )

        alice.sending_chain = next_ck

    def _bob_receives(self):
        bob = self.session.bob
        msg = self.session.message_log[-1]

        mk, next_ck = derive_message_key(bob.receiving_chain)

        msg.decrypted_by_bob = mk

        bob.receiving_chain = next_ck

    def _bob_sends_with_dh_ratchet(self):
        alice = self.session.alice
        bob = self.session.bob

        # Bob generates new DH key
        bob.dh_private = "B1_priv"
        bob.dh_public = "B1_pub"

        # DH ratchet
        dh_result = fake_dh(bob.dh_private, alice.dh_public)

        new_root = fake_kdf(bob.root_key, dh_result)

        bob.root_key = new_root
        alice.root_key = new_root

        bob.sending_chain = "CK_B1"
        alice.receiving_chain = "CK_B1"

        # Send message
        mk, next_ck = derive_message_key(bob.sending_chain)

        self.session.message_log.append(
            MessageState(
                sender="Bob",
                receiver="Alice",
                message_key=mk,
                cipher=f"ENC({mk})",
            )
        )

        bob.sending_chain = next_ck

    def _alice_receives_dh(self):
        alice = self.session.alice
        msg = self.session.message_log[-1]

        mk, next_ck = derive_message_key(alice.receiving_chain)

        msg.decrypted_by_alice = mk

        alice.receiving_chain = next_ck

    def _build_visual(self, perspective):
        sender_party, receiver_party = self._get_sender_receiver_parties()

        sender_panel = self._build_party_panel(
            sender_party,
            perspective,
            role_title="Sender"
        )
        receiver_panel = self._build_party_panel(
            receiver_party,
            perspective,
            role_title="Receiver"
        )
        timeline = self._build_timeline(perspective)

        return ft.Row(
            [
                ft.Container(sender_panel, expand=1, padding=10),
                ft.VerticalDivider(),
                ft.Container(timeline, expand=1, padding=10),
                ft.VerticalDivider(),
                ft.Container(receiver_panel, expand=1, padding=10),
            ],
            expand=True
        )

    def _get_sender_receiver_parties(self):
        if self.session.message_log:
            latest = self.session.message_log[-1]
            sender_name = latest.sender
            receiver_name = latest.receiver
        else:
            sender_name = "Alice"
            receiver_name = "Bob"

        sender_party = (
            self.session.alice
            if sender_name == "Alice"
            else self.session.bob
        )
        receiver_party = (
            self.session.alice
            if receiver_name == "Alice"
            else self.session.bob
        )

        return sender_party, receiver_party

    def _build_party_panel(
        self,
        party: PartyState,
        perspective,
        role_title=None
    ):

        visible = (
            perspective == "global"
            or perspective.lower() == party.name.lower()
        )

        header = (
            party.name
            if role_title is None
            else f"{role_title}: {party.name}"
        )
        is_receiver_role = role_title == "Receiver"
        tooltips = get_tooltip_messages("double_ratchet")

        return ft.Column(
            [
                ft.Text(
                    header,
                    size=18,
                    weight="bold",
                    text_align=(
                        ft.TextAlign.RIGHT
                        if is_receiver_role
                        else ft.TextAlign.LEFT
                    ),
                ),
                build_tooltip_text(
                    label="DH Public",
                    value=party.dh_public,
                    tooltip_message=tooltips.get("dh_public", ""),
                ),
                build_tooltip_text(
                    label="DH Private",
                    value=party.dh_private if visible else "Hidden",
                    tooltip_message=tooltips.get("dh_private", ""),
                ),
                build_tooltip_text(
                    label="Root Key",
                    value=party.root_key if visible else "Hidden",
                    tooltip_message=tooltips.get("root_key", ""),
                ),
                build_tooltip_text(
                    label="Sending Chain",
                    value=party.sending_chain if visible else "Hidden",
                    tooltip_message=tooltips.get("sending_chain", ""),
                ),
                build_tooltip_text(
                    label="Receiving Chain",
                    value=party.receiving_chain if visible else "Hidden",
                    tooltip_message=tooltips.get("receiving_chain", ""),
                ),
            ],
            horizontal_alignment=(
                ft.CrossAxisAlignment.END
                if is_receiver_role
                else ft.CrossAxisAlignment.START
            ),
        )

    def _build_timeline(self, perspective):

        col = ft.Column([ft.Text("Message Timeline", weight="bold")])

        for i, msg in enumerate(self.session.message_log):

            if perspective == "attacker":
                display = f"{msg.sender} → {msg.receiver} | {msg.cipher}"
            elif perspective == "alice":
                if msg.receiver == "Alice":
                    display = f"{msg.sender} → Alice | Decrypted"
                elif msg.sender == "Alice":
                    display = f"Alice → {msg.receiver} | Sent"
                else:
                    continue
            elif perspective == "bob":
                if msg.receiver == "Bob":
                    display = f"{msg.sender} → Bob | Decrypted"
                elif msg.sender == "Bob":
                    display = f"Bob → {msg.receiver} | Sent"
                else:
                    continue
            else:
                display = (
                    f"{msg.sender} → {msg.receiver} "
                    f"| MK={msg.message_key}"
                )

            col.controls.append(ft.Text(f"[{i}] {display}"))

        return col

    def _build_explanation(self, step):

        explanations = {
            0: "Initial state: Both share RK0 and initial chains.",
            1: "Alice sends first message using symmetric ratchet.",
            2: "Bob decrypts using receiving chain.",
            3: "Bob generates new DH key and performs DH ratchet.",
            4: "Alice receives and updates receiving chain.",
        }

        return ft.Text(explanations.get(step, "More steps soon..."))
