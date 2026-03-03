import flet as ft
from components.data_classes import DoubleRatchetState
from components.data_classes import PartyState
from modules.base_view import format_key, last_n_chars, make_copy_handler
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


def _build_party_panel(page: ft.Page, party: PartyState, perspective: str, role_title: str | None = None):
    visible = perspective == "global" or perspective.lower() == party.name.lower()
    header = party.name if role_title is None else f"{role_title}: {party.name}"
    tooltips = get_tooltip_messages("double_ratchet")

    dhs_full = format_key(party.DHs)
    dhr_full = format_key(party.DHr)
    rk_full = format_key(party.RK)
    cks_full = format_key(party.CKs)
    ckr_full = format_key(party.CKr)

    dhs_value = last_n_chars(dhs_full, 8) if visible else "Hidden"
    dhr_value = last_n_chars(dhr_full, 8) if visible else "Hidden"
    rk_value = last_n_chars(rk_full, 8) if visible else "Hidden"
    cks_value = last_n_chars(cks_full, 8) if visible else "Hidden"
    ckr_value = last_n_chars(ckr_full, 8) if visible else "Hidden"

    return ft.Column(
        [
            ft.Text(
                header,
                size=18,
                weight="bold",
                text_align=ft.TextAlign.LEFT
            ),
            build_tooltip_text(
                "DHs",
                dhs_value,
                tooltips.get("DHs", ""),
                full_value=dhs_full if visible else None,
                on_click=make_copy_handler(page, "DHs", dhs_full) if visible else None,
            ),
            build_tooltip_text(
                "DHr",
                dhr_value,
                tooltips.get("DHr", ""),
                full_value=dhr_full if visible else None,
                on_click=make_copy_handler(page, "DHr", dhr_full) if visible else None,
            ),
            build_tooltip_text(
                "RK",
                rk_value,
                tooltips.get("RK", ""),
                full_value=rk_full if visible else None,
                on_click=make_copy_handler(page, "RK", rk_full) if visible else None,
            ),
            build_tooltip_text(
                "CKs",
                cks_value,
                tooltips.get("CKs", ""),
                full_value=cks_full if visible else None,
                on_click=make_copy_handler(page, "CKs", cks_full) if visible else None,
            ),
            build_tooltip_text(
                "CKr",
                ckr_value,
                tooltips.get("CKr", ""),
                full_value=ckr_full if visible else None,
                on_click=make_copy_handler(page, "CKr", ckr_full) if visible else None,
            ),
            build_tooltip_text("Ns", str(party.Ns), tooltips.get("Ns", "")),
            build_tooltip_text("Nr", str(party.Nr), tooltips.get("Nr", "")),
            build_tooltip_text("PN", str(party.PN), tooltips.get("PN", "")),
            build_tooltip_text("MKSKIPPED", str(len(party.MKSKIPPED)), tooltips.get("MKSKIPPED", "")),
        ],
        spacing=2,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )


def build_timeline(session: DoubleRatchetState, perspective: str):
    col = ft.Column(
        [
            ft.Row(
                controls=[ft.Text("Message Timeline", weight="bold")],
                alignment=ft.MainAxisAlignment.CENTER,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=6,
    )

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


def build_visual(session: DoubleRatchetState, perspective: str, page: ft.Page):
    sender_party, receiver_party = _get_sender_receiver_parties(session)

    sender_panel = _build_party_panel(page, sender_party, perspective, role_title="Sender")
    receiver_panel = _build_party_panel(page, receiver_party, perspective, role_title="Receiver")
    timeline = build_timeline(session, perspective)

    timeline_container = ft.Container(
        content=timeline,
        expand=True,
        padding=10,
    )

    return ft.Row(
        [
            ft.Container(sender_panel, width=170, padding=10),
            ft.VerticalDivider(),
            ft.Container(timeline_container, expand=True, padding=10),
            ft.VerticalDivider(),
            ft.Container(receiver_panel, width=170, padding=10),
        ],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
