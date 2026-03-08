from typing import Any

import flet as ft
from modules.tooltip_helpers import get_tooltip_messages


def _preview_value(value: Any, limit: int = 28) -> str:
    if isinstance(value, bytes):
        text = value.hex()
    elif value is None:
        text = "None"
    else:
        text = str(value)

    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _to_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.hex()
    if value is None:
        return "None"
    return str(value)


def _last_n_chars(value: Any, count: int = 8) -> str:
    text = _to_text(value)
    if len(text) <= count:
        return text
    return text[-count:]


def _tooltip_with_full_value(message: str | None, full_value: Any = None) -> str | None:
    parts: list[str] = []
    if message:
        parts.append(message)
    if full_value is not None:
        if parts:
            parts.append("\n────────────\n")
        parts.append(f"Key value:\n{_to_text(full_value)}")
    if not parts:
        return None
    return "".join(parts)


def show_step_visualization_dialog(page: ft.Page, step_data: dict[str, Any]) -> None:
    tooltips = get_tooltip_messages("double_ratchet")

    resize_event_name = "on_resized" if hasattr(page, "on_resized") else "on_resize"
    previous_resize_handler = getattr(page, resize_event_name, None)

    def _safe_dimension(value: Any, fallback: int) -> int:
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
        return fallback

    def _page_size() -> tuple[int, int]:
        width = getattr(page, "width", None)
        height = getattr(page, "height", None)
        window = getattr(page, "window", None)

        if width is None and window is not None:
            width = getattr(window, "width", None)
        if height is None and window is not None:
            height = getattr(window, "height", None)

        return _safe_dimension(width, 1100), _safe_dimension(height, 760)

    def apply_responsive_dialog_size() -> None:
        page_width, page_height = _page_size()
        content_width = max(620, min(980, int(page_width * 0.82)))
        content_height = max(360, min(760, int(page_height * 0.72)))

        dialog_content.width = content_width
        dialog_content.height = content_height
        step_container.width = max(520, content_width - 80)

    def on_page_resized(e) -> None:
        apply_responsive_dialog_size()
        if callable(previous_resize_handler):
            previous_resize_handler(e)
        if dialog.open:
            page.update()

    def close_dialog(e):
        dialog.open = False
        if getattr(page, resize_event_name, None) == on_page_resized:
            setattr(page, resize_event_name, previous_resize_handler)
        page.update()

    def on_previous(e):
        if current_step["index"] <= 0:
            return
        current_step["index"] -= 1
        render_current_step()
        page.update()

    def on_next(e):
        if current_step["index"] >= len(steps) - 1:
            close_dialog(e)
            return
        current_step["index"] += 1
        render_current_step()
        page.update()

    def with_tooltip(control: ft.Control, message: str | None, full_value: Any = None) -> ft.Control:
        tooltip_message = _tooltip_with_full_value(message, full_value)
        if tooltip_message:
            return ft.Container(
                content=control,
                tooltip=ft.Tooltip(message=tooltip_message, prefer_below=False),
                padding=0,
            )
        return control

    def flow_node(
        label: str,
        value: str | None = None,
        circle: bool = False,
        width: int = 170,
        height: int = 90,
        tooltip: str | None = None,
        full_value: Any = None,
    ) -> ft.Control:
        controls = [ft.Text(label, weight="bold", text_align=ft.TextAlign.CENTER)]
        if value:
            controls.append(ft.Text(value, text_align=ft.TextAlign.CENTER))

        node = ft.Container(
            content=ft.Column(
                controls=controls,
                spacing=4,
                tight=True,
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=width,
            height=height,
            padding=10,
            border=ft.Border.all(),
            border_radius=45 if circle else 8,
        )
        return with_tooltip(node, tooltip, full_value)

    def state_row(label: str, value: str, tooltip: str | None = None, full_value: Any = None) -> ft.Control:
        row = ft.Row(
            controls=[
                ft.Text(f"{label}:", weight="bold"),
                ft.Text(value),
            ],
            spacing=8,
            wrap=True,
        )
        return with_tooltip(row, tooltip, full_value)

    def party_state_panel(
        title: str,
        rows: list[tuple[str, str, str | None, Any]],
        tooltip: str | None = None,
    ) -> ft.Control:
        panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(title, size=16, weight="bold"),
                    *[state_row(label, value, row_tooltip, full_value) for label, value, row_tooltip, full_value in rows],
                ],
                spacing=4,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            width=420,
            padding=10,
            border=ft.Border.all(),
            border_radius=8,
        )
        return with_tooltip(panel, tooltip)

    sender = step_data.get("sender", "?")
    receiver = step_data.get("receiver", "?")
    plaintext_raw = step_data.get("plaintext", b"")
    if isinstance(plaintext_raw, bytes):
        try:
            plaintext_string = plaintext_raw.decode("utf-8")
        except UnicodeDecodeError:
            plaintext_string = plaintext_raw.hex()
    else:
        plaintext_string = str(plaintext_raw)

    plaintext = _preview_value(plaintext_string, limit=40)
    cipher_full = step_data.get("cipher", b"")
    mk_full = step_data.get("mk", b"")
    before_cks_full = step_data.get("before_cks")
    after_cks_full = step_data.get("after_cks")
    before_dh_full = step_data.get("before_dh", "")
    header_dh_full = step_data.get("header_dh", "")

    cipher = _last_n_chars(cipher_full, 8)
    mk = _last_n_chars(mk_full, 8)
    before_cks = _last_n_chars(before_cks_full, 8)
    after_cks = _last_n_chars(after_cks_full, 8)
    after_ns = step_data.get("after_ns", "?")
    before_ns = step_data.get("before_ns", "?")
    before_pn = step_data.get("before_pn", "?")
    before_dh = _last_n_chars(before_dh_full, 8)
    header_preview = (
        f"dh={_last_n_chars(header_dh_full, 8)}, "
        f"pn={step_data.get('header_pn', '?')}, n={step_data.get('header_n', '?')}"
    )

    step1_data_flow = ft.Column(
        controls=[
            ft.Text("1) Data and party state", weight="bold"),
            ft.Row(
                controls=[
                    flow_node(
                        "Plaintext (string)",
                        plaintext,
                        width=260,
                        tooltip=tooltips.get("step_viz_plaintext", ""),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            party_state_panel(
                "Sender party state (before send)",
                [
                    ("DHs", before_dh, tooltips.get("step_viz_sender_before_dhs", ""), before_dh_full),
                    ("PN", str(before_pn), tooltips.get("step_viz_sender_before_pn", ""), None),
                    ("Ns", str(before_ns), tooltips.get("step_viz_sender_before_ns", ""), None),
                    ("CKs", before_cks, tooltips.get("step_viz_sender_before_cks", ""), before_cks_full),
                ],
                tooltip=tooltips.get("step_viz_sender_before_panel", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2_data_flow = ft.Column(
        controls=[
            ft.Text("2) Send chain step", weight="bold"),
            flow_node("CKs", before_cks, tooltip=tooltips.get("step_viz_send_chain_cks", ""), full_value=before_cks_full),
            ft.Text("↓", size=24),
            flow_node("KDF_CK", circle=True, tooltip=tooltips.get("step_viz_kdf_ck", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    flow_node("new CKs", after_cks, tooltip=tooltips.get("step_viz_new_cks", ""), full_value=after_cks_full),
                    flow_node("message key", mk, tooltip=tooltips.get("step_viz_message_key", ""), full_value=mk_full),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=24,
            ),
            ft.Container(height=8),
            ft.Divider(height=1),
            ft.Container(height=8),
            flow_node(
                "Party state update",
                f"CKs replaced with new CKs\nNs: {before_ns} -> {after_ns}",
                width=260,
                height=105,
                tooltip=tooltips.get("step_viz_state_update", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3_data_flow = ft.Column(
        controls=[
            ft.Text("3) Encrypt plaintext", weight="bold"),
            ft.Row(
                controls=[
                    flow_node("mk", mk, tooltip=tooltips.get("step_viz_encrypt_mk", ""), full_value=mk_full),
                    flow_node("Plaintext", plaintext, tooltip=tooltips.get("step_viz_encrypt_plaintext", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=24,
            ),
            flow_node(
                "AD||header",
                width=220,
                tooltip=tooltips.get("step_viz_ad_header", ""),
            ),
            ft.Text("↓", size=24),
            flow_node("ENCRYPT", circle=True, tooltip=tooltips.get("step_viz_encrypt_fn", "")),
            ft.Text("↓", size=24),
            flow_node("Ciphertext", cipher, tooltip=tooltips.get("step_viz_ciphertext", ""), full_value=cipher_full),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4_data_flow = ft.Column(
        controls=[
            ft.Text("4) Create header and update state", weight="bold"),
            ft.Row(
                controls=[
                    flow_node("DHs", before_dh, tooltip=tooltips.get("step_viz_header_dhs", ""), full_value=before_dh_full),
                    flow_node("PN", str(before_pn), tooltip=tooltips.get("step_viz_header_pn", "")),
                    flow_node("N", str(before_ns), tooltip=tooltips.get("step_viz_header_n", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node("HEADER", circle=True, tooltip=tooltips.get("step_viz_header_fn", "")),
            ft.Text("↓", size=24),
            flow_node("Header", header_preview, width=360, tooltip=tooltips.get("step_viz_header_output", ""), full_value=f"dh={_to_text(header_dh_full)}, pn={step_data.get('header_pn', '?')}, n={step_data.get('header_n', '?')}"),
            ft.Container(height=8),
            ft.Divider(height=1),
            ft.Container(height=8),
            party_state_panel(
                "Party state after send",
                [
                    ("CKs", after_cks, tooltips.get("step_viz_sender_after_cks", ""), after_cks_full),
                    ("Ns", str(after_ns), tooltips.get("step_viz_sender_after_ns", ""), None),
                ],
                tooltip=tooltips.get("step_viz_sender_after_panel", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5_data_flow = ft.Column(
        controls=[
            ft.Text("5) Sent", weight="bold"),
            party_state_panel(
                "Party state before send",
                [
                    ("DHs", before_dh, tooltips.get("step_viz_sent_before_dhs", ""), before_dh_full),
                    ("PN", str(before_pn), tooltips.get("step_viz_sent_before_pn", ""), None),
                    ("Ns", str(before_ns), tooltips.get("step_viz_sent_before_ns", ""), None),
                    ("CKs", before_cks, tooltips.get("step_viz_sent_before_cks", ""), before_cks_full),
                ],
            ),
            flow_node(
                "Pending queue",
                f"ID: {step_data.get('pending_id', '?')}\n{sender} -> {receiver}",
                width=280,
                tooltip=tooltips.get("step_viz_pending_queue", ""),
            ),
            party_state_panel(
                "Party state after send",
                [
                    ("DHs", before_dh, tooltips.get("step_viz_sent_after_dhs", ""), before_dh_full),
                    ("PN", str(before_pn), tooltips.get("step_viz_sent_after_pn", ""), None),
                    ("Ns", str(after_ns), tooltips.get("step_viz_sent_after_ns", ""), None),
                    ("CKs", after_cks, tooltips.get("step_viz_sent_after_cks", ""), after_cks_full),
                ],
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    steps = [
        {
            "title": "1) Data and party state",
            "control": step1_data_flow,
        },
        {
            "title": "2) Send chain step",
            "control": step2_data_flow,
        },
        {
            "title": "3) Create header and update state",
            "control": step4_data_flow,
        },
        {
            "title": "4) Encrypt plaintext",
            "control": step3_data_flow,
        },
        {
            "title": "5) Sent",
            "control": step5_data_flow,
        },
    ]

    current_step = {"index": 0}
    progress_text = ft.Text()
    step_container = ft.Container(width=620)
    previous_button = ft.TextButton("Previous", on_click=on_previous)
    next_button = ft.TextButton("Next", on_click=on_next)

    def render_current_step() -> None:
        index = current_step["index"]
        step = steps[index]
        progress_text.value = f"Step {index + 1}/{len(steps)}"
        step_container.content = step["control"]
        previous_button.disabled = index == 0
        next_button.text = "Finish" if index == len(steps) - 1 else "Next"

    dialog_content = ft.Container(
        content=ft.Column(
            controls=[
                progress_text,
                ft.Text("Click Next to continue to the following step."),
                ft.Row(controls=[step_container], alignment=ft.MainAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=700,
        height=460,
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Step-by-step vizualization"),
        content=dialog_content,
        actions=[previous_button, next_button, ft.TextButton("Close", on_click=close_dialog)],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    apply_responsive_dialog_size()
    setattr(page, resize_event_name, on_page_resized)
    render_current_step()
    page.overlay.append(dialog)
    dialog.open = True
    page.update()
