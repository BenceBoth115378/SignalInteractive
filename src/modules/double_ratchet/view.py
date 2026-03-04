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
    dhs_public_full = party.DHs.public if party.DHs is not None else "None"
    dhr_full = format_key(party.DHr)
    rk_full = format_key(party.RK)
    cks_full = format_key(party.CKs)
    ckr_full = format_key(party.CKr)

    dhs_value = last_n_chars(dhs_public_full, 8) if visible else "Hidden"
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
            on_click=make_copy_handler(page, "DHs", dhs_public_full) if visible else None,
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
    page: ft.Page | None = None,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
):
    perspective_key = perspective.lower()
    tooltips = get_tooltip_messages("double_ratchet")

    def _to_text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            if not value:
                return ""
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.hex()
        return str(value)

    def _header_parts(header) -> tuple[str, int | str, int | str]:
        if header is None:
            return "", "?", "?"
        return str(getattr(header, "dh", "")), getattr(header, "pn", "?"), getattr(header, "n", "?")

    def _build_header_row(dh: str, pn: int | str, n: int | str) -> ft.Row:
        dh_display = last_n_chars(dh, 12) if dh else ""
        return ft.Row(
            controls=[
                ft.Text("header:"),
                build_tooltip_text(
                    "dh",
                    dh_display,
                    tooltips.get("header_dh", ""),
                    full_value=dh or None,
                    on_click=make_copy_handler(page, "Header DH", dh) if page is not None and dh else None,
                ),
                ft.Text("|"),
                build_tooltip_text(
                    "pn",
                    str(pn),
                    tooltips.get("header_pn", ""),
                ),
                ft.Text("|"),
                build_tooltip_text(
                    "n",
                    str(n),
                    tooltips.get("header_n", ""),
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
            wrap=True,
        )

    def _build_message_text(message_line: str) -> ft.Container:
        can_copy = page is not None and message_line.strip() != "message:"
        return ft.Container(
            content=ft.Text(message_line),
            on_click=make_copy_handler(page, "Message", message_line) if can_copy else None,
            ink=can_copy,
        )

    def _is_actor(target: str, sender: str, receiver: str) -> bool:
        lowered = target.lower()
        return lowered == sender.lower() or lowered == receiver.lower()

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
        sender = msg.sender
        receiver = msg.receiver

        if perspective_key not in {"global", "attacker"} and not _is_actor(perspective_key, sender, receiver):
            continue

        sender_view = perspective_key == sender.lower()
        recipient_view = perspective_key == receiver.lower()
        attacker_view = perspective_key == "attacker"
        global_view = perspective_key == "global"

        dh, pn, n = _header_parts(getattr(msg, "header", None))
        cipher_text = _to_text(msg.cipher)
        plaintext_text = _to_text(getattr(msg, "plaintext", b""))
        recipient_decrypted = _to_text(msg.decrypted_by_alice if receiver == "Alice" else msg.decrypted_by_bob)

        if sender_view or global_view:
            message_line = f"message: {plaintext_text or recipient_decrypted}"
        elif recipient_view:
            message_line = f"message: {recipient_decrypted or plaintext_text}"
        else:
            message_line = f"message: {cipher_text}"

        row = ft.Row(
            controls=[ft.Text(f"[{i}] {sender} → {receiver} | Received")],
            alignment=ft.MainAxisAlignment.START,
        )
        header_row = _build_header_row(dh, pn, n)

        col.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        row,
                        header_row,
                        _build_message_text(message_line),
                    ],
                    spacing=2,
                    tight=True,
                ),
                padding=6,
            )
        )

    if pending_messages is not None:
        for i, pending in enumerate(pending_messages, start=len(session.message_log)):
            pending_id = pending.get("id")
            sender = pending.get("sender", "?")
            receiver = pending.get("receiver", "?")
            header = pending.get("header")
            dh, pn, n = _header_parts(header)
            cipher_text = _to_text(pending.get("cipher", b""))
            plaintext_text = _to_text(pending.get("plaintext", b""))

            if not isinstance(pending_id, int):
                continue

            if perspective_key not in {"global", "attacker"} and not _is_actor(perspective_key, str(sender), str(receiver)):
                continue

            sender_view = perspective_key == str(sender).lower()
            attacker_view = perspective_key == "attacker"
            can_receive = perspective_key == "global" or perspective_key == str(receiver).lower()

            if attacker_view:
                message_line = f"message: {cipher_text}"
            elif sender_view or perspective_key == "global":
                message_line = f"message: {plaintext_text}"
            else:
                message_line = f"message: {cipher_text}"

            row_controls = [ft.Text(f"[{i}] {sender} → {receiver} | ")]
            if can_receive and on_receive_pending is not None:
                row_controls.append(
                    ft.TextButton(
                        "Receive",
                        on_click=lambda e, pid=pending_id, recipient=receiver: on_receive_pending(recipient, pid),
                    )
                )
            else:
                row_controls.append(ft.Text("Pending"))

            col.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.START),
                            _build_header_row(dh, pn, n),
                            _build_message_text(message_line),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                    padding=6,
                )
            )

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
        page,
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
