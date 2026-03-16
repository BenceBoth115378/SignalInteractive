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

    def _key_field(label: str, full_value: str, copy_value: str | None = None) -> ft.Control:
        display = last_n_chars(full_value, 8) if visible else "Hidden"
        cv = copy_value if copy_value is not None else full_value
        return build_tooltip_text(
            label,
            display,
            tooltips.get(label, ""),
            full_value=full_value if visible else None,
            on_click=make_copy_handler(page, label, cv) if visible else None,
        )

    panel_controls = [
        ft.Text(header, size=18, weight="bold", text_align=ft.TextAlign.LEFT),
        _key_field("DHs", dhs_full, dhs_public_full),
        _key_field("DHr", dhr_full),
        _key_field("RK", rk_full),
        _key_field("CKs", cks_full),
        _key_field("CKr", ckr_full),
        build_tooltip_text("Ns", str(party.Ns), tooltips.get("Ns", "")),
        build_tooltip_text("Nr", str(party.Nr), tooltips.get("Nr", "")),
        build_tooltip_text("PN", str(party.PN), tooltips.get("PN", "")),
        build_tooltip_text("MKSKIPPED", str(len(party.MKSKIPPED)), tooltips.get("MKSKIPPED", "")),
    ]

    if message_input is not None and on_send is not None:
        panel_controls.extend([ft.Divider(height=12), message_input, ft.Button("Send", on_click=on_send)])

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
    on_show_send_visualization=None,
    on_show_receive_visualization=None,
    attacker_analysis: list[dict] | None = None,
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
                    str(n + 1),
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

    def _resolve_message_line(
        perspective_key: str,
        sender: str,
        receiver: str,
        cipher_text: str,
        plaintext_text: str,
        recipient_decrypted: str = "",
    ) -> str:
        sender_view = perspective_key == sender.lower()
        recipient_view = perspective_key == receiver.lower()
        global_view = perspective_key == "global"
        attacker_view = perspective_key == "attacker"
        if attacker_view:
            return f"message: {cipher_text}"
        if sender_view or global_view:
            return f"message: {plaintext_text or recipient_decrypted}"
        if recipient_view:
            return f"message: {recipient_decrypted or plaintext_text}"
        return f"message: {cipher_text}"

    def _build_entry_container(row: ft.Row, dh: str, pn, n, message_line: str, border: ft.Border | None = None, bgcolor: str | None = None) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[row, _build_header_row(dh, pn, n), _build_message_text(message_line)],
                spacing=2,
                tight=True,
            ),
            padding=6,
            border=border,
            bgcolor=bgcolor,
            border_radius=5,
        )

    combined = []
    for msg in session.message_log:
        combined.append((msg.seq_id, "received", msg))
    if pending_messages is not None and perspective_key != "attacker":
        for pending in pending_messages:
            if isinstance(pending.get("id"), int):
                combined.append((pending["id"], "pending", pending))

    attacker_results = {}
    if perspective_key == "attacker" and attacker_analysis:
        for a in attacker_analysis:
            attacker_results[(a["id"], a["state"])] = a

    for seq_id, kind, entry in sorted(combined, key=lambda x: x[0], reverse=True):
        i = seq_id
        border = None
        bgcolor = None
        if kind == "received":
            msg = entry
            sender = msg.sender
            receiver = msg.receiver

            if perspective_key not in {"global", "attacker"} and not _is_actor(perspective_key, sender, receiver):
                continue

            dh, pn, n = _header_parts(getattr(msg, "header", None))
            cipher_text = _to_text(msg.cipher)
            plaintext_text = _to_text(getattr(msg, "plaintext", b""))
            recipient_decrypted = _to_text(msg.decrypted_by_alice if receiver == "Alice" else msg.decrypted_by_bob)

            message_line = _resolve_message_line(
                perspective_key, sender, receiver, cipher_text, plaintext_text, recipient_decrypted
            )

            if perspective_key == "attacker":
                analysis = attacker_results.get((i, "received"))
                if analysis:
                    if analysis["decryptable"]:
                        message_line = f"message (decrypted): {analysis['plaintext']}"
                        border = ft.Border.all(1, ft.Colors.GREEN)
                        bgcolor = ft.Colors.GREEN_ACCENT_100
                    else:
                        border = ft.Border.all(1, ft.Colors.YELLOW)
                        bgcolor = ft.Colors.YELLOW_ACCENT_100
            row_controls = [ft.Text(f"[{i}] {sender} → {receiver} | Received")]
            sender_view = perspective_key == sender.lower()
            receiver_view = perspective_key == receiver.lower()
            global_view = perspective_key == "global"

            show_send_option = (global_view or sender_view) and perspective_key != "attacker"
            show_receive_option = (global_view or receiver_view) and perspective_key != "attacker"

            if show_send_option and on_show_send_visualization is not None:
                row_controls.append(
                    ft.TextButton(
                        "Show sending steps",
                        on_click=lambda e, sid=seq_id: on_show_send_visualization(sid),
                    )
                )
            if show_receive_option and on_show_receive_visualization is not None:
                row_controls.append(
                    ft.TextButton(
                        "Show receiving steps",
                        on_click=lambda e, sid=seq_id: on_show_receive_visualization(sid),
                    )
                )
            row = ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.START)
            col.controls.append(_build_entry_container(row, dh, pn, n, message_line, border, bgcolor))

        else:  # pending
            pending = entry
            pending_id = pending.get("id")
            sender = pending.get("sender", "?")
            receiver = pending.get("receiver", "?")
            dh, pn, n = _header_parts(pending.get("header"))
            cipher_text = _to_text(pending.get("cipher", b""))
            plaintext_text = _to_text(pending.get("plaintext", b""))

            if perspective_key not in {"global", "attacker"} and not _is_actor(perspective_key, str(sender), str(receiver)):
                continue

            can_receive = perspective_key == "global" or perspective_key == str(receiver).lower()
            message_line = _resolve_message_line(
                perspective_key, str(sender), str(receiver), cipher_text, plaintext_text
            )

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

            row = ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.START)
            col.controls.append(_build_entry_container(row, dh, pn, n, message_line, border, bgcolor))

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
    on_show_send_visualization=None,
    on_show_receive_visualization=None,
    attacker_dashboard: ft.Control | None = None,
    attacker_analysis: list[dict] | None = None,
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
        on_show_send_visualization=on_show_send_visualization,
        on_show_receive_visualization=on_show_receive_visualization,
        attacker_analysis=attacker_analysis,
    )

    timeline_container = ft.Container(
        content=timeline,
        expand=True,
        padding=10,
    )

    top_row = ft.Row(
        [
            ft.Container(
                ft.Column([initializer_panel], spacing=10, tight=True),
                expand=True,
                padding=10,
            ),
            ft.VerticalDivider(),
            ft.Container(timeline_container, height=400, expand=True, padding=10),
            ft.VerticalDivider(),
            ft.Container(responder_panel, expand=True, padding=10),
        ],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    if attacker_dashboard is None:
        return top_row

    return ft.Column(
        controls=[
            top_row,
            ft.Divider(height=1),
            attacker_dashboard,
        ],
        expand=True,
        spacing=6,
    )
