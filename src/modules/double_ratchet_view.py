import flet as ft
from components.state import DoubleRatchetState
from modules.party_state import PartyState
from modules.tooltip_helpers import build_tooltip_text, get_tooltip_messages


def _get_sender_receiver_parties(session: DoubleRatchetState) -> tuple[PartyState, PartyState]:
    if session.message_log:
        latest = session.message_log[-1]
        sender_name, receiver_name = latest.sender, latest.receiver
    else:
        sender_name, receiver_name = "Alice", "Bob"

    sender_party = session.initializer if sender_name == "Alice" else session.responder
    receiver_party = session.initializer if receiver_name == "Alice" else session.responder
    return sender_party, receiver_party


def _build_party_panel(party: PartyState, perspective: str, role_title: str | None = None):
    visible = perspective == "global" or perspective.lower() == party.name.lower()
    header = party.name if role_title is None else f"{role_title}: {party.name}"
    is_receiver_role = role_title == "Receiver"
    tooltips = get_tooltip_messages("double_ratchet")

    return ft.Column(
        [
            ft.Text(
                header,
                size=18,
                weight="bold",
                text_align=ft.TextAlign.RIGHT if is_receiver_role else ft.TextAlign.LEFT,
            ),
            build_tooltip_text("DH Public", party.dh_public, tooltips.get("dh_public", "")),
            build_tooltip_text("DH Private", party.dh_private if visible else "Hidden", tooltips.get("dh_private", "")),
            build_tooltip_text("Root Key", party.root_key if visible else "Hidden", tooltips.get("root_key", "")),
            build_tooltip_text("Sending Chain", party.sending_chain if visible else "Hidden", tooltips.get("sending_chain", "")),
            build_tooltip_text("Receiving Chain", party.receiving_chain if visible else "Hidden", tooltips.get("receiving_chain", "")),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.END if is_receiver_role else ft.CrossAxisAlignment.START,
    )


def build_timeline(session: DoubleRatchetState, perspective: str):
    col = ft.Column([ft.Text("Message Timeline", weight="bold")])

    for i, msg in enumerate(session.message_log):
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
            display = f"{msg.sender} → {msg.receiver} | MK={msg.message_key}"

        col.controls.append(ft.Text(f"[{i}] {display}"))

    return col


def build_visual(session: DoubleRatchetState, perspective: str):
    sender_party, receiver_party = _get_sender_receiver_parties(session)

    sender_panel = _build_party_panel(sender_party, perspective, role_title="Sender")
    receiver_panel = _build_party_panel(receiver_party, perspective, role_title="Receiver")
    timeline = build_timeline(session, perspective)

    return ft.Row(
        [
            ft.Container(sender_panel, expand=1, padding=10),
            ft.VerticalDivider(),
            ft.Container(timeline, expand=1, padding=10),
            ft.VerticalDivider(),
            ft.Container(receiver_panel, expand=1, padding=10),
        ],
        expand=True,
    )


def build_explanation(step: int):
    explanations = {
        0: "Initial state: Both share RK0 and initial chains.",
        1: "Alice sends first message using symmetric ratchet.",
        2: "Bob decrypts using receiving chain.",
        3: "Bob generates new DH key and performs DH ratchet.",
        4: "Alice receives and updates receiving chain.",
    }
    return ft.Text(explanations.get(step, "More steps soon..."))
