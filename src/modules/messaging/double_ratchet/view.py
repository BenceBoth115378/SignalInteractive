import flet as ft
from components.data_classes import DoubleRatchetState
from components.data_classes import PartyState
from modules.messaging.double_ratchet.key_history import get_key_tooltip_text
from modules.messaging.messaging_base_view import is_party_visible
from modules.base_view import format_key, last_n_chars, make_copy_handler
from modules.tooltip_helpers import build_tooltip_text, get_tooltip_messages


SIDE_PANEL_WIDTH = 360


def _build_party_panel(
    page: ft.Page,
    party: PartyState,
    perspective: str,
    role_title: str | None = None,
    message_input: ft.TextField | None = None,
    on_send=None,
):
    visible = is_party_visible(perspective, party.name)
    header = party.name if role_title is None else f"{role_title}: {party.name}"
    tooltips = get_tooltip_messages("double_ratchet")

    dhs_public_full = party.DHs.public if party.DHs is not None else "None"
    dhs_private_full = party.DHs.private if party.DHs is not None else "None"
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
        _key_field("DHs_pub", dhs_public_full),
        _key_field("DHs_priv", dhs_private_full),
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

    return ft.Container(
        content=ft.Column(
            panel_controls,
            spacing=2,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        width=SIDE_PANEL_WIDTH,
    )


def _build_used_keys_history_panel(page: ft.Page, party: PartyState, perspective: str) -> ft.Control:
    visible = is_party_visible(perspective, party.name)
    tooltips = get_tooltip_messages("double_ratchet")

    panel_controls: list[ft.Control] = [
        build_tooltip_text(
            "Used keys history",
            "",
            tooltips.get("used_keys_history_notice", ""),
        ),
    ]

    if not visible:
        panel_controls.append(ft.Text("Hidden", color=ft.Colors.OUTLINE))
    else:
        sections: list[tuple[str, list]] = [
            ("DH", party.key_history.dh_events),
            ("RK", party.key_history.rk_events),
            ("CKs", party.key_history.cks_events),
            ("CKr", party.key_history.ckr_events),
        ]

        for section_label, events in sections:
            panel_controls.append(ft.Text(section_label, weight="bold", size=12))
            ordered_events = list(reversed(events))
            if not ordered_events:
                panel_controls.append(ft.Text("-", color=ft.Colors.OUTLINE))
                continue
            for event in ordered_events:
                if section_label == "DH":
                    public_text = str(event.public_value or "")
                    private_text = event.key_value.hex() if isinstance(event.key_value, bytes) else str(event.key_value)
                    pub_label = f"DHs_pub#{event.key_number} ({event.created_at_step})"
                    priv_label = f"DHs_priv#{event.key_number} ({event.created_at_step})"
                    panel_controls.append(
                        build_tooltip_text(
                            pub_label,
                            last_n_chars(public_text, 10),
                            get_key_tooltip_text(event),
                            full_value=public_text,
                            on_click=make_copy_handler(page, f"{party.name} {pub_label}", public_text),
                        )
                    )
                    panel_controls.append(
                        build_tooltip_text(
                            priv_label,
                            last_n_chars(private_text, 10),
                            get_key_tooltip_text(event),
                            full_value=private_text,
                            on_click=make_copy_handler(page, f"{party.name} {priv_label}", private_text),
                        )
                    )
                else:
                    key_text = event.key_value.hex() if isinstance(event.key_value, bytes) else str(event.key_value)
                    label = f"{event.key_type}#{event.key_number} ({event.created_at_step})"
                    panel_controls.append(
                        build_tooltip_text(
                            label,
                            last_n_chars(key_text, 10),
                            get_key_tooltip_text(event),
                            full_value=key_text,
                            on_click=make_copy_handler(page, f"{party.name} {label}", key_text),
                        )
                    )

    return ft.Container(
        content=ft.Column(
            panel_controls,
            spacing=2,
            tight=False,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=SIDE_PANEL_WIDTH,
        expand=True,
        padding=8,
        border_radius=8,
    )


def build_timeline(
    session: DoubleRatchetState,
    perspective: str,
    page: ft.Page | None = None,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
    on_show_send_visualization=None,
    on_show_receive_visualization=None,
    on_show_alice_x3dh_bootstrap=None,
    on_show_bob_x3dh_bootstrap=None,
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

    def _build_message_text(message_line: str, tooltip_message: str = "") -> ft.Control:
        can_copy = page is not None and message_line.strip() != "message:"

        if not tooltip_message:
            return ft.Container(
                content=ft.Text(message_line),
                on_click=make_copy_handler(page, "Message", message_line) if can_copy else None,
                ink=can_copy,
            )

        decryption_explanation = f"The message was successfully decrypted using:\n{tooltip_message}"

        return build_tooltip_text(
            "message",
            message_line,
            decryption_explanation,
            full_value=None,
            on_click=make_copy_handler(page, "Message", message_line) if can_copy else None,
        )

    def _is_actor(target: str, sender: str, receiver: str) -> bool:
        lowered = target.lower()
        return lowered == sender.lower() or lowered == receiver.lower()

    controls = [
        ft.Row(
            controls=[ft.Text("Message Timeline", weight="bold")],
            alignment=ft.MainAxisAlignment.CENTER,
        )
    ]

    if on_show_alice_x3dh_bootstrap is not None and perspective_key in {"global", "alice"}:
        controls.append(
            ft.TextButton(
                "Show Alice X3DH initialization",
                on_click=lambda e: on_show_alice_x3dh_bootstrap(),
            )
        )
    col = ft.Column(
        controls,
        scroll=ft.ScrollMode.ALWAYS,
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

    def _build_entry_container(
        row: ft.Row,
        dh: str,
        pn,
        n,
        message_line: str,
        border: ft.Border | None = None,
        bgcolor: str | None = None,
        message_tooltip: str = "",
    ) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[row, _build_header_row(dh, pn, n), _build_message_text(message_line, message_tooltip)],
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

    bob_bootstrap_inserted = False
    for seq_id, kind, entry in sorted(combined, key=lambda x: x[0], reverse=True):
        i = seq_id
        border = None
        bgcolor = None
        message_tooltip = ""
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
                        message_tooltip = str(analysis.get("source", ""))
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

            if (not bob_bootstrap_inserted and on_show_bob_x3dh_bootstrap is not None and receiver.lower() == "bob"
                and perspective_key in {"global", "bob"}):
                col.controls.append(
                    ft.TextButton(
                        "Show Bob X3DH initialization",
                        on_click=lambda e, msg=msg: on_show_bob_x3dh_bootstrap(msg),
                    )
                )
                bob_bootstrap_inserted = True
            row = ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.START)
            col.controls.append(_build_entry_container(row, dh, pn, n, message_line, border, bgcolor, message_tooltip))

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
    on_show_alice_x3dh_bootstrap=None,
    on_show_bob_x3dh_bootstrap=None,
    attacker_dashboard: ft.Control | None = None,
    attacker_analysis: list[dict] | None = None,
):
    page_height = getattr(page, "height", None)
    if page_height is None and getattr(page, "window", None) is not None:
        page_height = getattr(page.window, "height", None)
    if not isinstance(page_height, (int, float)) or page_height <= 0:
        page_height = 900

    attacker_view = perspective.lower() == "attacker"
    timeline_height = max(280, int(page_height * (0.42 if attacker_view else 0.86)))

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
    show_key_history = perspective.lower() != "attacker"
    initializer_history = _build_used_keys_history_panel(page, initializer_party, perspective)
    responder_history = _build_used_keys_history_panel(page, responder_party, perspective)
    timeline = build_timeline(
        session,
        perspective,
        page,
        pending_messages=pending_messages,
        on_receive_pending=on_receive_pending,
        on_show_send_visualization=on_show_send_visualization,
        on_show_receive_visualization=on_show_receive_visualization,
        on_show_alice_x3dh_bootstrap=on_show_alice_x3dh_bootstrap,
        on_show_bob_x3dh_bootstrap=on_show_bob_x3dh_bootstrap,
        attacker_analysis=attacker_analysis,
    )

    timeline_container = ft.Container(
        content=timeline,
        height=timeline_height,
        padding=10,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    initializer_controls: list[ft.Control] = [initializer_panel]
    responder_controls: list[ft.Control] = [responder_panel]
    if show_key_history:
        initializer_controls.extend([ft.Divider(height=10), initializer_history])
        responder_controls.extend([ft.Divider(height=10), responder_history])

    top_row = ft.Row(
        [
            ft.Container(
                ft.Column(initializer_controls, spacing=10, tight=False, expand=True),
                expand=True,
                height=timeline_height,
                padding=10,
            ),
            ft.Container(timeline_container, expand=True, padding=10),
            ft.Container(
                ft.Column(responder_controls, spacing=10, tight=False, expand=True),
                expand=True,
                height=timeline_height,
                padding=10,
            ),
        ],
        expand=True,
        height=timeline_height,
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
