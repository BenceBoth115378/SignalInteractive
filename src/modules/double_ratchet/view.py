import flet as ft
from components.data_classes import DoubleRatchetState
from components.data_classes import PartyState
from modules.base_view import format_key, last_n_chars, make_copy_handler
from modules.tooltip_helpers import build_tooltip_text, get_tooltip_messages


def _build_party_panel(
    page: ft.Page,
    party: PartyState,
    perspective: str,
    role_title: str | None = None,
    message_input: ft.TextField | None = None,
    on_send=None,
):
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

    panel_controls = [
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
    ]

    if message_input is not None and on_send is not None:
        panel_controls.extend(
            [
                ft.Divider(height=12),
                message_input,
                ft.Button("Send", on_click=on_send),
            ]
        )

    return ft.Column(
        panel_controls,
        spacing=2,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )


def build_timeline(
    session: DoubleRatchetState,
    perspective: str,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
):
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

    if pending_messages is not None:
        for i, pending in enumerate(pending_messages, start=len(session.message_log)):
            pending_id = pending.get("id")
            sender = pending.get("sender", "?")
            receiver = pending.get("receiver", "?")

            if not isinstance(pending_id, int):
                continue

            label = f"[{i}] {sender} → {receiver} | PENDING"
            can_receive = perspective == "global" or perspective.lower() == str(receiver).lower()

            if can_receive and on_receive_pending is not None:
                col.controls.append(
                    ft.TextButton(
                        label,
                        on_click=lambda e, pid=pending_id, recipient=receiver: on_receive_pending(recipient, pid),
                    )
                )
            else:
                col.controls.append(ft.Text(label))

    return col


def build_visual(
    session: DoubleRatchetState,
    perspective: str,
    page: ft.Page,
    alice_input: ft.TextField | None = None,
    bob_input: ft.TextField | None = None,
    on_send_alice=None,
    on_send_bob=None,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
):
    initializer_party = session.initializer
    responder_party = session.responder

    initializer_input = alice_input if initializer_party.name == "Alice" else bob_input
    responder_input = alice_input if responder_party.name == "Alice" else bob_input
    initializer_send = on_send_alice if initializer_party.name == "Alice" else on_send_bob
    responder_send = on_send_alice if responder_party.name == "Alice" else on_send_bob

    initializer_panel = _build_party_panel(
        page,
        initializer_party,
        perspective,
        role_title="Initializer",
        message_input=initializer_input,
        on_send=initializer_send,
    )
    responder_panel = _build_party_panel(
        page,
        responder_party,
        perspective,
        role_title="Responder",
        message_input=responder_input,
        on_send=responder_send,
    )
    timeline = build_timeline(
        session,
        perspective,
        pending_messages=pending_messages,
        on_receive_pending=on_receive_pending,
    )

    timeline_container = ft.Container(
        content=timeline,
        expand=True,
        padding=10,
    )

    return ft.Row(
        [
            ft.Container(initializer_panel, expand=True, padding=10),
            ft.VerticalDivider(),
            ft.Container(timeline_container, height=400, expand=True, padding=10),
            ft.VerticalDivider(),
            ft.Container(responder_panel, expand=True, padding=10),
        ],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
