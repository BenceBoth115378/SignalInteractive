from typing import Any, Callable

import flet as ft
from components.data_classes import DHKeyPair, ReceiveStepVisualizationSnapshot, SendStepVisualizationSnapshot
from modules import external as ext
from modules.base_step_visualization import (
    format_tooltip_value as _shared_format_tooltip_value,
    page_size as _shared_page_size,
    safe_dimension as _shared_safe_dimension,
    to_text as _shared_to_text,
    tooltip_with_full_value as _shared_tooltip_with_full_value,
    with_tooltip as _shared_with_tooltip,
)
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


def _format_tooltip_value(value: Any, indent: int = 0) -> str:
    return _shared_format_tooltip_value(value, indent)


def _to_text(value: Any) -> str:
    return _shared_to_text(value)


def _last_n_chars(value: Any, count: int = 8) -> str:
    text = _to_text(value)
    if len(text) <= count:
        return text
    return text[-count:]


def _tooltip_with_full_value(message: str | None, full_value: Any = None) -> str | None:
    return _shared_tooltip_with_full_value(message, full_value)


def _safe_dimension(value: Any, fallback: int) -> int:
    return _shared_safe_dimension(value, fallback)


def _page_size(page: ft.Page) -> tuple[int, int]:
    return _shared_page_size(page)


def _with_tooltip(control: ft.Control, message: str | None, full_value: Any = None) -> ft.Control:
    return _shared_with_tooltip(control, message, full_value)


def _flow_node(
    label: str,
    value: str | None = None,
    circle: bool = False,
    width: int = 170,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    controls = [ft.Text(label, weight="bold", text_align=ft.TextAlign.CENTER, color=text_color)]
    if value:
        controls.append(ft.Text(value, text_align=ft.TextAlign.CENTER, color=text_color))

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
        bgcolor=bgcolor,
        border=ft.Border.all(color=border_color) if border_color is not None else ft.Border.all(),
        border_radius=45 if circle else 8,
    )
    return _with_tooltip(node, tooltip, full_value)


def _state_row(
    label: str,
    value: str,
    tooltip: str | None = None,
    full_value: Any = None,
    highlight: bool = False,
    is_synced: bool = False,
) -> ft.Control:
    row = ft.Row(
        controls=[
            ft.Text(
                f"{label}:",
                weight="bold",
                color=ft.Colors.ON_PRIMARY_CONTAINER if highlight else None,
            ),
            ft.Text(
                value,
                weight=ft.FontWeight.W_600 if highlight else None,
                color=ft.Colors.ON_PRIMARY_CONTAINER if highlight else None,
            ),
        ],
        spacing=8,
        wrap=True,
    )
    row_control: ft.Control = row
    if highlight:
        row_control = ft.Container(
            content=row,
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=6,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
        )
    outer_container = ft.Container(
        content=row_control,
        padding=ft.Padding.symmetric(horizontal=4, vertical=2),
        border_radius=6,
        height=32,
        border=ft.Border.all(color=ft.Colors.GREEN_600, width=2) if is_synced else None,
    )
    return _with_tooltip(outer_container, tooltip, full_value)


def _party_state_panel(
    title: str,
    rows: list[tuple[str, str, str | None, Any]],
    tooltip: str | None = None,
    highlight_labels: set[str] | None = None,
    synced_labels: set[str] | None = None,
) -> ft.Control:
    highlighted = highlight_labels or set()
    synced = synced_labels or set()
    panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(title, size=16, weight="bold"),
                *[
                    _state_row(
                        label,
                        value,
                        row_tooltip,
                        full_value,
                        highlight=label in highlighted,
                        is_synced=label in synced,
                    )
                    for label, value, row_tooltip, full_value in rows
                ],
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
    return _with_tooltip(panel, tooltip)


def _show_step_dialog(
    page: ft.Page,
    dialog_title: str,
    steps: list[dict[str, Any]],
    on_close: Callable[[], None] | None = None,
) -> None:
    resize_event_name = "on_resized" if hasattr(page, "on_resized") else "on_resize"
    previous_resize_handler = getattr(page, resize_event_name, None)

    current_step = {"index": 0}
    progress_text = ft.Text()
    step_container = ft.Container(width=620)

    def apply_responsive_dialog_size() -> None:
        page_width, page_height = _page_size(page)
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

    def close_dialog(e) -> None:
        dialog.open = False
        if getattr(page, resize_event_name, None) == on_page_resized:
            setattr(page, resize_event_name, previous_resize_handler)
        page.update()
        if on_close is not None:
            on_close()

    def render_current_step() -> None:
        index = current_step["index"]
        step = steps[index]
        progress_text.value = f"Step {index + 1}/{len(steps)}"
        step_container.content = step["control"]
        previous_button.disabled = index == 0
        next_button.text = "Finish" if index == len(steps) - 1 else "Next"

    def on_previous(e) -> None:
        if current_step["index"] <= 0:
            return
        current_step["index"] -= 1
        render_current_step()
        page.update()

    def on_next(e) -> None:
        if current_step["index"] >= len(steps) - 1:
            close_dialog(e)
            return
        current_step["index"] += 1
        render_current_step()
        page.update()

    previous_button = ft.TextButton("Previous", on_click=on_previous)
    next_button = ft.TextButton("Next", on_click=on_next)

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
            scroll=ft.ScrollMode.ALWAYS,
        ),
        width=700,
        height=460,
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(dialog_title),
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


def show_sending_step_visualization_dialog(
    page: ft.Page,
    step_data: SendStepVisualizationSnapshot,
    on_close: Callable[[], None] | None = None,
) -> None:
    tooltips = get_tooltip_messages("double_ratchet")

    flow_node = _flow_node
    party_state_panel = _party_state_panel

    sender = step_data.sender
    receiver = step_data.receiver
    plaintext_raw = step_data.plaintext
    if isinstance(plaintext_raw, bytes):
        try:
            plaintext_string = plaintext_raw.decode("utf-8")
        except UnicodeDecodeError:
            plaintext_string = plaintext_raw.hex()
    else:
        plaintext_string = str(plaintext_raw)

    plaintext = _preview_value(plaintext_string, limit=40)
    cipher_full = step_data.cipher
    mk_full = step_data.mk
    before_cks_full = step_data.before.CKs
    after_cks_full = step_data.after.CKs
    before_dhs_pub_full = step_data.before.DHs_public
    before_dhs_priv_full = step_data.before.DHs_private
    after_dhs_pub_full = step_data.after.DHs_public
    after_dhs_priv_full = step_data.after.DHs_private
    header_dh_full = step_data.header.dh

    cipher = _last_n_chars(cipher_full, 8)
    mk = _last_n_chars(mk_full, 8)
    before_cks = _last_n_chars(before_cks_full, 8)
    after_cks = _last_n_chars(after_cks_full, 8)
    after_ns = step_data.after.Ns
    before_ns = step_data.before.Ns
    before_pn = step_data.before.PN
    before_dhs_pub = _last_n_chars(before_dhs_pub_full, 8)
    before_dhs_priv = _last_n_chars(before_dhs_priv_full, 8)
    after_dhs_pub = _last_n_chars(after_dhs_pub_full, 8)
    after_dhs_priv = _last_n_chars(after_dhs_priv_full, 8)
    header_preview = (
        f"dh={_last_n_chars(header_dh_full, 8)}, "
        f"pn={step_data.header.pn}, n={step_data.header.n + 1}"
    )
    step2_cks_transition_full = (
        f"old CKs: {_to_text(before_cks_full)}\n"
        f"new CKs: {_to_text(after_cks_full)}"
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
            ft.Divider(height=1),
            party_state_panel(
                "Sender state (before send)",
                [
                    ("DHs_pub", before_dhs_pub, tooltips.get("DHs_pub", ""), before_dhs_pub_full),
                    ("DHs_priv", before_dhs_priv, tooltips.get("DHs_priv", ""), before_dhs_priv_full),
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
                full_value=step2_cks_transition_full,
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
                    flow_node("AD||header", tooltip=tooltips.get("step_viz_ad_header", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=24,
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
                    flow_node("DHs_pub", before_dhs_pub, tooltip=tooltips.get("step_viz_header_dhs", ""), full_value=before_dhs_pub_full),
                    flow_node("PN", str(before_pn), tooltip=tooltips.get("step_viz_header_pn", "")),
                    flow_node("N", str(before_ns + 1), tooltip=tooltips.get("step_viz_header_n", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node("HEADER", circle=True, tooltip=tooltips.get("step_viz_header_fn", "")),
            ft.Text("↓", size=24),
            flow_node("Header", header_preview, width=360, tooltip=tooltips.get("step_viz_header_output", ""), full_value=f"dh={_to_text(header_dh_full)}, pn={step_data.header.pn}, n={step_data.header.n + 1}"),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5_before_rows = [
        ("DHs_pub", before_dhs_pub, tooltips.get("DHs_pub", ""), before_dhs_pub_full),
        ("DHs_priv", before_dhs_priv, tooltips.get("DHs_priv", ""), before_dhs_priv_full),
        ("PN", str(before_pn), tooltips.get("step_viz_sent_before_pn", ""), None),
        ("Ns", str(before_ns), tooltips.get("step_viz_sent_before_ns", ""), None),
        ("CKs", before_cks, tooltips.get("step_viz_sent_before_cks", ""), before_cks_full),
    ]
    step5_after_rows = [
        ("DHs_pub", after_dhs_pub, tooltips.get("DHs_pub", ""), after_dhs_pub_full),
        ("DHs_priv", after_dhs_priv, tooltips.get("DHs_priv", ""), after_dhs_priv_full),
        ("PN", str(before_pn), tooltips.get("step_viz_sent_after_pn", ""), None),
        ("Ns", str(after_ns), tooltips.get("step_viz_sent_after_ns", ""), None),
        ("CKs", after_cks, tooltips.get("step_viz_sent_after_cks", ""), after_cks_full),
    ]
    step5_before_values = {label: value for label, value, _, _ in step5_before_rows}
    step5_after_values = {label: value for label, value, _, _ in step5_after_rows}
    changed_step5_labels = {
        label
        for label, value in step5_before_values.items()
        if value != step5_after_values.get(label)
    }

    step5_data_flow = ft.Column(
        controls=[
            ft.Text("5) Sent", weight="bold"),
            ft.Row(
                controls=[
                    flow_node(
                        "Pending queue",
                        f"ID: {step_data.pending_id}\n{sender} -> {receiver}",
                        width=280,
                        tooltip=tooltips.get("step_viz_pending_queue", ""),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Divider(height=1),
            ft.Row(
                controls=[
                    party_state_panel(
                        "Party state before send",
                        step5_before_rows,
                        highlight_labels=changed_step5_labels,
                    ),
                    party_state_panel(
                        "Party state after send",
                        step5_after_rows,
                        highlight_labels=changed_step5_labels,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=20,
                wrap=True,
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

    _show_step_dialog(page, "Step-by-step visualization of sending steps", steps, on_close=on_close)


def show_receiving_step_visualization_dialog(page: ft.Page, step_data: ReceiveStepVisualizationSnapshot) -> None:
    tooltips = get_tooltip_messages("double_ratchet")

    flow_node = _flow_node
    party_state_panel = _party_state_panel

    sender = step_data.sender
    receiver = step_data.receiver
    decrypted_full = step_data.decrypted
    cipher_full = step_data.cipher
    header_dh_full = step_data.header.dh

    if isinstance(decrypted_full, bytes):
        try:
            decrypted_string = decrypted_full.decode("utf-8")
        except UnicodeDecodeError:
            decrypted_string = decrypted_full.hex()
    else:
        decrypted_string = str(decrypted_full)

    plaintext = _preview_value(decrypted_string, limit=40)
    cipher = _last_n_chars(cipher_full, 8)
    header_preview = (
        f"dh={_last_n_chars(header_dh_full, 8)}, "
        f"pn={step_data.header.pn}, n={step_data.header.n + 1}"
    )
    mk_full = step_data.mk
    mk = _last_n_chars(mk_full, 8)

    before_ckr_full = step_data.before.CKr
    after_ckr_full = step_data.after.CKr
    before_rk_full = step_data.before.RK
    after_rk_full = step_data.after.RK
    before_dhr_full = step_data.before.DHr or ""
    after_dhr_full = step_data.after.DHr or ""
    before_dhs_pub_full = step_data.before.DHs_public
    after_dhs_pub_full = step_data.after.DHs_public
    before_dhs_priv_full = step_data.before.DHs_private
    after_dhs_priv_full = step_data.after.DHs_private
    after_cks_full = step_data.after.CKs
    ckr_after_double_ratchet_full = step_data.ckr_after_double_ratchet
    ckr_before_kdf_ck_full = step_data.ckr_before_kdf_ck
    before_nr = step_data.before.Nr
    after_nr = step_data.after.Nr
    skipped_key_hit = step_data.skipped_key_hit
    dh_ratchet_needed = step_data.dh_ratchet_needed
    fast_forward_count = step_data.fast_forward_count
    fast_forward_from_nr = step_data.fast_forward_from_nr
    fast_forward_to_nr = step_data.fast_forward_to_nr
    header_n = step_data.header.n
    header_pn = step_data.header.pn
    before_nr_int = int(before_nr)
    pn_fast_forward_count = max(0, header_pn - before_nr_int) if dh_ratchet_needed else 0
    pn_fast_forward_from_nr = before_nr_int
    pn_fast_forward_to_nr = before_nr_int + pn_fast_forward_count

    before_ckr = _last_n_chars(before_ckr_full, 8)
    after_ckr = _last_n_chars(after_ckr_full, 8)
    before_rk = _last_n_chars(before_rk_full, 8)
    after_rk = _last_n_chars(after_rk_full, 8)
    before_dhr = _last_n_chars(before_dhr_full, 8)
    after_dhr = _last_n_chars(after_dhr_full, 8)
    before_dhs_pub = _last_n_chars(before_dhs_pub_full, 8)
    after_dhs_pub = _last_n_chars(after_dhs_pub_full, 8)
    before_dhs_priv = _last_n_chars(before_dhs_priv_full, 8)
    after_dhs_priv = _last_n_chars(after_dhs_priv_full, 8)
    after_cks = _last_n_chars(after_cks_full, 8)
    ckr_after_double_ratchet = _last_n_chars(ckr_after_double_ratchet_full, 8)
    ckr_before_kdf_ck = _last_n_chars(ckr_before_kdf_ck_full, 8)

    rk_after_kdf_rk1_full: bytes | None = None
    ss_kdf_rk1_full: bytes | None = None
    ss_kdf_rk2_full: bytes | None = None

    if all(
        [
            dh_ratchet_needed,
            isinstance(before_dhs_priv_full, str),
            isinstance(before_dhs_pub_full, str),
            isinstance(header_dh_full, str),
            isinstance(before_rk_full, bytes),
        ]
    ):
        try:
            ss_kdf_rk1_full = ext.DH(
                DHKeyPair(private=before_dhs_priv_full, public=before_dhs_pub_full),
                header_dh_full,
            )
            rk_after_kdf_rk1_full, kdf1_ckr_full = ext.KDF_RK(before_rk_full, ss_kdf_rk1_full)
            if ckr_after_double_ratchet_full is None:
                ckr_after_double_ratchet_full = kdf1_ckr_full
                ckr_after_double_ratchet = _last_n_chars(ckr_after_double_ratchet_full, 8)
        except ValueError:
            rk_after_kdf_rk1_full = None
            ss_kdf_rk1_full = None

    if all(
        [
            dh_ratchet_needed,
            isinstance(after_dhs_priv_full, str),
            isinstance(after_dhs_pub_full, str),
            isinstance(header_dh_full, str),
            isinstance(rk_after_kdf_rk1_full, bytes),
        ]
    ):
        try:
            ss_kdf_rk2_full = ext.DH(
                DHKeyPair(private=after_dhs_priv_full, public=after_dhs_pub_full),
                header_dh_full,
            )
        except ValueError:
            ss_kdf_rk2_full = None

    rk_after_kdf_rk1 = _last_n_chars(rk_after_kdf_rk1_full, 8)
    ss_kdf_rk1 = _last_n_chars(ss_kdf_rk1_full, 8)
    ss_kdf_rk2 = _last_n_chars(ss_kdf_rk2_full, 8)

    step1_data_flow = ft.Column(
        controls=[
            ft.Text("Incoming message and receiver state", weight="bold"),
            ft.Row(
                controls=[
                    flow_node(
                        "Header",
                        header_preview,
                        width=360,
                        tooltip=tooltips.get("step_viz_receive_header", ""),
                        full_value=f"dh={_to_text(header_dh_full)}, pn={step_data.header.pn}, n={step_data.header.n + 1}",
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            flow_node(
                "Ciphertext",
                cipher,
                width=260,
                tooltip=tooltips.get("step_viz_receive_ciphertext", ""),
                full_value=cipher_full,
            ),
            ft.Divider(height=1),
            party_state_panel(
                "Receiver state before receive",
                [
                    ("DHs_pub", before_dhs_pub, tooltips.get("DHs_pub", ""), before_dhs_pub_full),
                    ("DHs_priv", before_dhs_priv, tooltips.get("DHs_priv", ""), before_dhs_priv_full),
                    ("DHr", before_dhr, tooltips.get("step_viz_receive_before_dhr", ""), before_dhr_full),
                    ("RK", before_rk, tooltips.get("step_viz_receive_before_rk", ""), before_rk_full),
                    ("CKr", before_ckr, tooltips.get("step_viz_receive_before_ckr", ""), before_ckr_full),
                    ("Nr", str(before_nr), tooltips.get("step_viz_receive_before_nr", ""), None),
                ],
                tooltip=tooltips.get("step_viz_receive_before_panel", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    skipped_check_controls: list[ft.Control] = [
        ft.Text("Skipped-message key check", weight="bold"),
        flow_node(
            "Lookup key",
            f"(dh, n)=({_last_n_chars(header_dh_full, 8)}, {step_data.header.n + 1})",
            width=300,
            tooltip=tooltips.get("step_viz_receive_skipped_lookup", ""),
            full_value=f"dh={_to_text(header_dh_full)}, n={step_data.header.n + 1}",
        ),
        ft.Text("↓", size=24),
        flow_node(
            "MKSKIPPED check",
            "FOUND" if skipped_key_hit else "NOT FOUND",
            width=220,
            tooltip=tooltips.get("step_viz_receive_skipped_check", ""),
        ),
        ft.Text("↓", size=24),
        flow_node(
            "Return value",
            f"return MK: {mk}" if skipped_key_hit else "no MK returned -> continue",
            width=340,
            tooltip=tooltips.get("step_viz_receive_skipped_path", ""),
            full_value=mk_full if skipped_key_hit else None,
        ),
    ]

    skipped_check_data_flow = ft.Column(
        controls=skipped_check_controls,
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    header_processing_data_flow = ft.Column(
        controls=[
            ft.Text("Header processing", weight="bold"),
            flow_node("Header.dh", _last_n_chars(header_dh_full, 8), tooltip=tooltips.get("step_viz_receive_header_dh", ""), full_value=header_dh_full),
            ft.Text("↓", size=24),
            flow_node("Compare with DHr", f"DHr: {before_dhr}", circle=True, tooltip=tooltips.get("step_viz_receive_compare_dh", ""), full_value=before_dhr_full),
            ft.Text("↓", size=24),
            flow_node(
                "Ratchet decision",
                "DH ratchet needed" if dh_ratchet_needed else "No DH ratchet needed",
                width=250,
                tooltip=tooltips.get("step_viz_receive_ratchet_decision", ""),
                bgcolor=ft.Colors.SECONDARY_CONTAINER if dh_ratchet_needed else ft.Colors.TERTIARY_CONTAINER,
                text_color=ft.Colors.ON_SECONDARY_CONTAINER if dh_ratchet_needed else ft.Colors.ON_TERTIARY_CONTAINER,
                border_color=ft.Colors.OUTLINE,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    controls = [
        ft.Text("Sync Nr to header.n", weight="bold"),
        flow_node(
            "Check correlation",
            f"Nr: {fast_forward_from_nr}  n: {header_n + 1}",
            width=300,
            tooltip=tooltips.get("step_viz_receive_fast_forward", ""),
        ),
    ]
    if fast_forward_count > 0:
        controls.extend([
            ft.Text("↓", size=24),
            flow_node(
                "SkipMessageKeys(state, n)",
                f"save MKSKIPPED: {fast_forward_count}\nNr: {fast_forward_from_nr} -> {fast_forward_to_nr}\nCKr: {ckr_before_kdf_ck}",
                width=340,
                height=150,
                tooltip=tooltips.get("step_viz_receive_fast_forward", ""),
                full_value=(
                    f"Roll receive chain to n={header_n + 1}.\n"
                    f"Each skipped index derives MK and stores it into MKSKIPPED.")
            ),
        ])
    else:
        controls.append(ft.Text("No fast forward needed", weight="bold"))
    skip_to_n_data_flow = ft.Column(
        controls=controls,
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    receive_chain_step_data_flow = ft.Column(
        controls=[
            ft.Text("Generate MK and advance CKr", weight="bold"),
            flow_node(
                "CKr",
                ckr_before_kdf_ck,
                tooltip=tooltips.get("step_viz_receive_ckr", ""),
                full_value=ckr_before_kdf_ck_full,
            ),
            ft.Text("↓", size=24),
            flow_node("KDF_CK", circle=True, tooltip=tooltips.get("step_viz_receive_kdf_ck", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    flow_node("new CKr", after_ckr, tooltip=tooltips.get("step_viz_receive_new_ckr", ""), full_value=after_ckr_full),
                    flow_node(
                        "message key",
                        mk,
                        tooltip=tooltips.get("step_viz_receive_message_key", ""),
                        full_value=mk_full,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=24,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step_dh_ratchet_data_flow_1 = ft.Column(
        controls=[
            ft.Text("DH ratchet update (part 1)", weight="bold"),
            ft.Row(
                controls=[
                    flow_node("Header.dh", _last_n_chars(header_dh_full, 8), tooltip=tooltips.get("step_viz_receive_header_dh", ""), full_value=header_dh_full),
                    flow_node("Current DHr", before_dhr, tooltip=tooltips.get("step_viz_receive_compare_dh", ""), full_value=before_dhr_full),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node(
                "Complete old receiving chain",
                (
                    f"header.pn={header_pn}, Nr={pn_fast_forward_from_nr}\n"
                    f"In-transit msgs: {pn_fast_forward_count}\n"
                    f"Saving MKs: Nr {pn_fast_forward_from_nr} -> {pn_fast_forward_to_nr}"
                    if pn_fast_forward_count > 0
                    else f"header.pn={header_pn}, Nr={pn_fast_forward_from_nr}\nAll msgs received, nothing to skip"
                ),
                width=340,
                height=120,
                circle=True,
                tooltip=tooltips.get("step_viz_receive_complete_old_chain", ""),
                full_value=(
                    f"header.pn={header_pn}, Nr={pn_fast_forward_from_nr}\n"
                    f"In-transit messages: {pn_fast_forward_count}\n"
                    f"Saving MKs: Nr {pn_fast_forward_from_nr} -> {pn_fast_forward_to_nr}"
                    if pn_fast_forward_count > 0
                    else
                    f"header.pn={header_pn}, Nr={pn_fast_forward_from_nr}\n"
                    f"All messages from the previous chain were received — nothing to skip."
                ),
            ),
            ft.Text("", size=24),
            flow_node(
                "Set DHr",
                f"Header.dh -> DHr\n{before_dhr} -> {_last_n_chars(header_dh_full, 8)}",
                width=320,
                height=110,
                circle=True,
                tooltip=tooltips.get("step_viz_receive_set_dhr", ""),
                full_value=f"old DHr: {_to_text(before_dhr_full)}\nnew DHr: {_to_text(header_dh_full)}",
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step_dh_ratchet_data_flow_2 = ft.Column(
        controls=[
            ft.Text("DH ratchet update (part 2)", weight="bold"),
            ft.Row(
                controls=[
                    flow_node("DHr", after_dhr, tooltip=tooltips.get("step_viz_receive_after_dhr", ""), full_value=header_dh_full, width=170, height=90),
                    flow_node("DHs_pub", before_dhs_pub, tooltip=tooltips.get("DHs_pub", ""), full_value=before_dhs_pub_full, width=170, height=90),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node(
                "DH",
                "Inputs: DHr, DHs_pub",
                width=200,
                height=70,
                circle=True,
                tooltip=tooltips.get("step_viz_dh_computation", ""),
            ),
            ft.Text("↓", size=24),
            flow_node("Shared secret (SS)", ss_kdf_rk1, width=200, height=70, tooltip=tooltips.get("step_viz_shared_secret", ""), full_value=ss_kdf_rk1_full),
            ft.Text("", size=24),
            ft.Row(
                controls=[
                    flow_node("RK", before_rk, tooltip=tooltips.get("step_viz_receive_before_rk", ""), full_value=before_rk_full, width=170, height=90),
                    flow_node("SS", ss_kdf_rk1, tooltip=tooltips.get("step_viz_shared_secret", ""), full_value=ss_kdf_rk1_full, width=170, height=90),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node(
                "KDF_RK #1",
                width=200,
                height=70,
                circle=True,
                tooltip=tooltips.get("step_viz_receive_kdf_rk_1", ""),
                full_value=(
                    f"RK before: {_to_text(before_rk_full)}\n"
                    f"SS: {_to_text(ss_kdf_rk1_full)}\n"
                    f"RK after: {_to_text(rk_after_kdf_rk1_full)}\n"
                    f"CKr after: {_to_text(ckr_after_double_ratchet_full)}"
                ),
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    flow_node("RK", rk_after_kdf_rk1, tooltip=tooltips.get("step_viz_receive_after_rk", ""), full_value=rk_after_kdf_rk1_full),
                    flow_node("CKr", ckr_after_double_ratchet, tooltip=tooltips.get("step_viz_receive_after_ckr", ""), full_value=ckr_after_double_ratchet_full),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("", size=24),
            flow_node(
                "Set Nr",
                "Nr <- 0",
                width=220,
                circle=True,
                tooltip=tooltips.get("step_viz_receive_set_nr_zero", ""),
            ),
            ft.Divider(height=1),
            ft.Row(
                controls=[
                    party_state_panel(
                        "Receiver state before",
                        [
                            ("DHr", before_dhr, tooltips.get("step_viz_receive_before_dhr", ""), before_dhr_full),
                            ("DHs_pub", before_dhs_pub, tooltips.get("DHs_pub", ""), before_dhs_pub_full),
                            ("RK", before_rk, tooltips.get("step_viz_receive_before_rk", ""), before_rk_full),
                            ("CKr", before_ckr, tooltips.get("step_viz_receive_before_ckr", ""), before_ckr_full),
                            ("Nr", str(before_nr), tooltips.get("step_viz_receive_before_nr", ""), None),
                        ],
                    ),
                    party_state_panel(
                        "Receiver state until this point",
                        [
                            ("DHr", _last_n_chars(header_dh_full, 8), tooltips.get("step_viz_receive_after_dhr", ""), header_dh_full),
                            ("DHs_pub", before_dhs_pub, tooltips.get("DHs_pub", ""), before_dhs_pub_full),
                            ("RK", rk_after_kdf_rk1, tooltips.get("step_viz_receive_after_rk", ""), rk_after_kdf_rk1_full),
                            ("CKr", ckr_after_double_ratchet, tooltips.get("step_viz_receive_after_ckr", ""), ckr_after_double_ratchet_full),
                            ("Nr", "0", tooltips.get("step_viz_receive_set_nr_zero", ""), 0),
                        ],
                        highlight_labels={"DHr", "RK", "CKr", "Nr"},
                        synced_labels={"DHr", "RK", "CKr"},
                    ),
                    party_state_panel(
                        "Sender state",
                        [
                            ("DHr", before_dhs_pub, tooltips.get("step_viz_receive_compare_dh", ""), before_dhs_pub_full),
                            ("DHs_pub", _last_n_chars(header_dh_full, 8), tooltips.get("DHs_pub", ""), header_dh_full),
                            ("RK", rk_after_kdf_rk1, tooltips.get("step_viz_receive_kdf_rk_1", ""), rk_after_kdf_rk1_full),
                            ("CKs", ckr_after_double_ratchet, tooltips.get("step_viz_receive_kdf_rk_1", ""), ckr_after_double_ratchet_full),
                        ],
                        synced_labels={"DHs_pub", "RK", "CKs"},
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step_dh_ratchet_data_flow_3 = ft.Column(
        controls=[
            ft.Text("DH ratchet update (part 3)", weight="bold"),
            ft.Row(
                controls=[
                    flow_node("DHr", after_dhr, tooltip=tooltips.get("step_viz_receive_after_dhr", ""), full_value=after_dhr_full, width=170, height=90),
                    flow_node("DHs_pub", after_dhs_pub, tooltip=tooltips.get("DHs_pub", ""), full_value=after_dhs_pub_full, width=170, height=90),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node(
                "DH",
                "Inputs: DHr, DHs_pub",
                width=200,
                height=70,
                circle=True,
                tooltip=tooltips.get("step_viz_dh_computation", ""),
            ),
            ft.Text("↓", size=24),
            flow_node("Shared secret (SS)", ss_kdf_rk2, width=200, height=70, tooltip=tooltips.get("step_viz_shared_secret", ""), full_value=ss_kdf_rk2_full),
            ft.Text("", size=24),
            ft.Row(
                controls=[
                    flow_node("RK", rk_after_kdf_rk1, tooltip=tooltips.get("step_viz_receive_after_rk", ""), full_value=rk_after_kdf_rk1_full, width=170, height=90),
                    flow_node("SS", ss_kdf_rk2, tooltip=tooltips.get("step_viz_shared_secret", ""), full_value=ss_kdf_rk2_full, width=170, height=90),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            flow_node(
                "KDF_RK #2",
                width=200,
                height=70,
                circle=True,
                tooltip=tooltips.get("step_viz_receive_kdf_rk_2", ""),
                full_value=(
                    f"RK before: {_to_text(rk_after_kdf_rk1_full)}\n"
                    f"SS: {_to_text(ss_kdf_rk2_full)}\n"
                    f"RK after: {_to_text(after_rk_full)}\n"
                    f"CKs after: {_to_text(after_cks_full)}"
                ),
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    flow_node("RK", after_rk, tooltip=tooltips.get("step_viz_receive_after_rk", ""), full_value=after_rk_full),
                    flow_node("CKs", after_cks, tooltip=tooltips.get("step_viz_receive_dh_ratchet_after_cks", ""), full_value=after_cks_full),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Divider(height=1),
            ft.Row(
                controls=[
                    party_state_panel(
                        "Receiver state before part 3",
                        [
                            ("DHr", after_dhr, tooltips.get("step_viz_receive_after_dhr", ""), after_dhr_full),
                            ("DHs_pub", after_dhs_pub, tooltips.get("DHs_pub", ""), after_dhs_pub_full),
                            ("RK", rk_after_kdf_rk1, tooltips.get("step_viz_receive_after_rk", ""), rk_after_kdf_rk1_full),
                            ("CKr", ckr_after_double_ratchet, tooltips.get("step_viz_receive_after_ckr", ""), ckr_after_double_ratchet_full),
                            ("Nr", "0", tooltips.get("step_viz_receive_set_nr_zero", ""), None),
                        ],
                    ),
                    party_state_panel(
                        "Receiver state after part 3",
                        [
                            ("DHr", after_dhr, tooltips.get("step_viz_receive_after_dhr", ""), after_dhr_full),
                            ("DHs_pub", after_dhs_pub, tooltips.get("DHs_pub", ""), after_dhs_pub_full),
                            ("RK", after_rk, tooltips.get("step_viz_receive_after_rk", ""), after_rk_full),
                            ("CKs", after_cks, tooltips.get("step_viz_receive_dh_ratchet_after_cks", ""), after_cks_full),
                            ("Ns", "0", tooltips.get("step_viz_receive_dh_ratchet_after_ns", ""), None),
                        ],
                        highlight_labels={"RK", "CKs", "Ns"},
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    decrypt_data_flow = ft.Column(
        controls=[
            ft.Text("Decrypt ciphertext", weight="bold"),
            ft.Row(
                controls=[
                    flow_node(
                        "MK",
                        mk,
                        tooltip=tooltips.get("step_viz_receive_message_key", ""),
                        full_value=mk_full,
                    ),
                    flow_node("Ciphertext", cipher, tooltip=tooltips.get("step_viz_receive_decrypt_cipher", ""), full_value=cipher_full),
                    flow_node("AD||header", tooltip=tooltips.get("step_viz_receive_decrypt_ad", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=24,
            ),
            ft.Text("↓", size=24),
            flow_node("DECRYPT", circle=True, tooltip=tooltips.get("step_viz_receive_decrypt_fn", "")),
            ft.Text("↓", size=24),
            flow_node("Plaintext", plaintext, width=280, tooltip=tooltips.get("step_viz_receive_plaintext", ""), full_value=decrypted_string),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    before_rows = [
        ("DHs_pub", before_dhs_pub, tooltips.get("DHs_pub", ""), before_dhs_pub_full),
        ("DHs_priv", before_dhs_priv, tooltips.get("DHs_priv", ""), before_dhs_priv_full),
        ("DHr", before_dhr, tooltips.get("step_viz_receive_before_dhr", ""), before_dhr_full),
        ("RK", before_rk, tooltips.get("step_viz_receive_before_rk", ""), before_rk_full),
        ("CKr", before_ckr, tooltips.get("step_viz_receive_before_ckr", ""), before_ckr_full),
        ("Nr", str(before_nr), tooltips.get("step_viz_receive_before_nr", ""), None),
    ]
    after_rows = [
        ("DHs_pub", after_dhs_pub, tooltips.get("DHs_pub", ""), after_dhs_pub_full),
        ("DHs_priv", after_dhs_priv, tooltips.get("DHs_priv", ""), after_dhs_priv_full),
        ("DHr", after_dhr, tooltips.get("step_viz_receive_after_dhr", ""), after_dhr_full),
        ("RK", after_rk, tooltips.get("step_viz_receive_after_rk", ""), after_rk_full),
        ("CKr", after_ckr, tooltips.get("step_viz_receive_after_ckr", ""), after_ckr_full),
        ("Nr", str(after_nr), tooltips.get("step_viz_receive_after_nr", ""), None),
    ]
    before_values = {label: value for label, value, _, _ in before_rows}
    after_values = {label: value for label, value, _, _ in after_rows}
    changed_labels = {
        label
        for label, value in before_values.items()
        if value != after_values.get(label)
    }

    received_summary_data_flow = ft.Column(
        controls=[
            ft.Text("Received", weight="bold"),
            ft.Row(
                controls=[
                    flow_node(
                        "Delivered message",
                        f"{sender} -> {receiver}",
                        width=260,
                        tooltip=tooltips.get("step_viz_receive_delivered", ""),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Divider(height=1),
            ft.Row(
                controls=[
                    party_state_panel(
                        "Receiver state before",
                        before_rows,
                        highlight_labels=changed_labels,
                    ),
                    party_state_panel(
                        "Receiver state after",
                        after_rows,
                        highlight_labels=changed_labels,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    steps = [
        {
            "title": "Incoming message and receiver state",
            "control": step1_data_flow,
        },
        {
            "title": "Skipped-message key check",
            "control": skipped_check_data_flow,
        },
    ]

    if not skipped_key_hit:
        steps.append(
            {
                "title": "Header DH decision",
                "control": header_processing_data_flow,
            }
        )
        if dh_ratchet_needed:
            steps.append(
                {
                    "title": "DH ratchet update (part 1)",
                    "control": step_dh_ratchet_data_flow_1,
                }
            )
            steps.append(
                {
                    "title": "DH ratchet update (part 2)",
                    "control": step_dh_ratchet_data_flow_2,
                }
            )
            steps.append(
                {
                    "title": "DH ratchet update (part 3)",
                    "control": step_dh_ratchet_data_flow_3,
                }
            )
        steps.extend(
            [
                {
                    "title": "Sync Nr to header.n",
                    "control": skip_to_n_data_flow,
                },
                {
                    "title": "Generate MK and advance CKr",
                    "control": receive_chain_step_data_flow,
                },
            ]
        )

    steps.extend(
        [
            {
                "title": "Decrypt ciphertext",
                "control": decrypt_data_flow,
            },
            {
                "title": "Received",
                "control": received_summary_data_flow,
            },
        ]
    )

    for i, step in enumerate(steps):
        numbered_title = f"{i + 1}) {step['title']}"
        step["title"] = numbered_title
        if isinstance(step["control"], ft.Column) and len(step["control"].controls) > 0:
            step["control"].controls[0].value = numbered_title

    _show_step_dialog(page, "Step-by-step visualization of receiving steps", steps)


def show_alice_x3dh_bootstrap_visualization_dialog(
    page: ft.Page,
    x3dh_state_data: dict[str, Any] | None,
    rk_after_init: bytes | None,
    cks_after_init: bytes | None,
    alice_dhs_pub: str,
    alice_dhs_priv: str,
    bob_spk_pub: str,
    session_ad: bytes,
    on_close: Callable[[], None] | None = None,
) -> None:
    tooltips = get_tooltip_messages("x3dh")

    derived = {}
    bundle = {}
    initial_header = {}
    alice_local = {}
    if isinstance(x3dh_state_data, dict):
        if isinstance(x3dh_state_data.get("alice_derived"), dict):
            derived = x3dh_state_data.get("alice_derived", {})
        if isinstance(x3dh_state_data.get("last_bundle_for_alice"), dict):
            bundle = x3dh_state_data.get("last_bundle_for_alice", {})
        if isinstance(x3dh_state_data.get("alice_local"), dict):
            alice_local = x3dh_state_data.get("alice_local", {})
        initial_message = x3dh_state_data.get("initial_message")
        if isinstance(initial_message, dict) and isinstance(initial_message.get("header"), dict):
            initial_header = initial_message.get("header", {})

    sk = derived.get("shared_secret") if isinstance(derived.get("shared_secret"), str) else ""
    ad = derived.get("associated_data") if isinstance(derived.get("associated_data"), str) else session_ad.hex()
    ek_pub = derived.get("ek_public") if isinstance(derived.get("ek_public"), str) else ""
    ek_priv = derived.get("ek_private") if isinstance(derived.get("ek_private"), str) else ""
    identity = alice_local.get("identity_dh") if isinstance(alice_local.get("identity_dh"), dict) else {}
    ik_priv = identity.get("private") if isinstance(identity.get("private"), str) else ""
    ik_b_pub = bundle.get("identity_dh_public") if isinstance(bundle.get("identity_dh_public"), str) else ""
    ik_a_pub = initial_header.get("ik_a_public") if isinstance(initial_header.get("ik_a_public"), str) else ""
    spk_b_pub = bundle.get("signed_prekey_public") if isinstance(bundle.get("signed_prekey_public"), str) else bob_spk_pub
    opk_b_pub = bundle.get("opk_public") if isinstance(bundle.get("opk_public"), str) else ""
    spk_b_signature = bundle.get("signed_prekey_signature") if isinstance(bundle.get("signed_prekey_signature"), str) else ""
    header_preview = (
        f"ik_a={ik_a_pub}, "
        f"ek_a={ek_pub}, "
        f"spk_b={spk_b_pub}"
        if initial_header
        else "Header fields captured for Bob"
    )
    ss: bytes | None = None
    if alice_dhs_priv and ik_b_pub:
        try:
            ss = ext.DH(DHKeyPair(private=alice_dhs_priv, public=alice_dhs_pub), ik_b_pub)
        except ValueError:
            ss = None

    step1 = ft.Column(
        controls=[
            ft.Text("1) Receive Pre key Bundle from server", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("Bundle", "IK_B, SPK_B, SPK_B_signature, optional OPK_B", width=420, tooltip=tooltips.get("x3dh_step_node_request_bundle", ""), full_value=(
                        f"IK_B={_last_n_chars(ik_b_pub, 8)}\nSPK_B={_last_n_chars(spk_b_pub, 8)}\nSPK_B_signature={_last_n_chars(spk_b_signature, 8)}\nOPK_B={_last_n_chars(opk_b_pub, 8)}"
                    )),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Verify SPK_B signature with IK_B", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_B", _last_n_chars(bundle.get("identity_dh_public", ""), 8), width=220, full_value=bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("SPK_B_signature", _last_n_chars(spk_b_signature, 8), width=220, full_value=spk_b_signature, tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            _flow_node("VERIFY", circle=True, width=210, height=70, tooltip=tooltips.get("x3dh_step_node_verify", "")),
            ft.Text("↓", size=24),
            _flow_node("Verification result", "VALID signature", width=240, tooltip=tooltips.get("x3dh_step_state_signature_verified", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dh_controls: list[ft.Control] = [
        _flow_node("DH1", "DH(IK_A_priv, SPK_B_pub)", width=420, full_value=f"IK_A_priv={ik_priv}\nSPK_B_pub={spk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH2", "DH(EK_A_priv, IK_B_pub)", width=420, full_value=f"EK_A_priv={ek_priv}\nIK_B_pub={ik_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH3", "DH(EK_A_priv, SPK_B_pub)", width=420, full_value=f"EK_A_priv={ek_priv}\nSPK_B_pub={spk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
    ]
    if bundle.get("opk_public"):
        dh_controls.append(_flow_node("DH4", "DH(EK_A_priv, OPK_B_pub)", width=420, full_value=f"EK_A_priv={ek_priv}\nOPK_B_pub={opk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")))

    step3 = ft.Column(
        controls=[
            ft.Text("3) Derive SK from DH outputs", weight="bold"),
            ft.Row(
                controls=dh_controls,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("KDF_SK", circle=True, width=200, height=70, tooltip=tooltips.get("x3dh_step_node_kdf_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("SK", _last_n_chars(sk, 8), width=220, full_value=sk, tooltip=tooltips.get("x3dh_step_key_sk", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    _flow_node("IK_A_pub", _last_n_chars(ik_a_pub, 8), width=220, full_value=ik_a_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("IK_B_pub", _last_n_chars(ik_b_pub, 8), width=220, full_value=ik_b_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("CALC_AD", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_calc_ad", "")),
            ft.Text("↓", size=24),
            _flow_node("AD", _last_n_chars(ad, 8), width=460, full_value=ad, tooltip=tooltips.get("x3dh_step_key_ad", "")),
            ft.Divider(height=1),
            _flow_node("X3DH header prefix", "IK_A_pub | EK_A_pub | Bob_SPK_pub | Bob_OPK_id", width=620, height=95,
                       full_value=header_preview, tooltip=tooltips.get("x3dh_step_node_header", ""),
                       ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("5) Initialize Double Ratchet and calculate SS", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("Generate DH keypair", circle=True, width=210, height=70, tooltip=tooltips.get("x3dh_step_node_generate_dh", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("DHs_pub", _last_n_chars(alice_dhs_pub, 8), width=220, full_value=alice_dhs_pub, tooltip=tooltips.get("dr_bootstrap_dhs_pub", "")),
                    _flow_node("DHs_priv", _last_n_chars(alice_dhs_priv, 8), width=220, full_value=alice_dhs_priv, tooltip=tooltips.get("dr_bootstrap_dhs_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("", size=24),
            ft.Row(
                controls=[
                    _flow_node("DHs_priv", _last_n_chars(alice_dhs_priv, 8), width=220, full_value=alice_dhs_priv, tooltip=tooltips.get("dr_bootstrap_dhs_priv", "")),
                    _flow_node("IK_B_pub", _last_n_chars(ik_b_pub, 8), width=220, full_value=ik_b_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("DH", "DHs_priv, IK_B_pub -> SS", circle=True, width=260, height=70, tooltip=tooltips.get("x3dh_step_node_dh", "")),
            ft.Text("↓", size=24),
            _flow_node("SS", _last_n_chars(ss, 8), width=260, full_value=ss, tooltip=tooltips.get("dr_bootstrap_ss", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step6 = ft.Column(
        controls=[
            ft.Text("6) Derive RK and CKs", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("SS", _last_n_chars(ss, 8), width=220, full_value=ss, tooltip=tooltips.get("dr_bootstrap_ss", "")),
                    _flow_node("SK", _last_n_chars(sk, 8), width=220, full_value=sk, tooltip=tooltips.get("x3dh_step_key_sk", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("KDF_RK", "SS, SK -> RK, CKs", circle=True, width=240, height=70, tooltip=tooltips.get("dr_bootstrap_kdf_rk", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("RK", _last_n_chars(rk_after_init, 8), width=220, full_value=rk_after_init, tooltip=tooltips.get("dr_bootstrap_rk", "")),
                    _flow_node("CKs", _last_n_chars(cks_after_init, 8), width=220, full_value=cks_after_init, tooltip=tooltips.get("dr_bootstrap_cks", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    steps = [
        {"title": "1) Receive Pre key Bundle from server", "control": step1},
        {"title": "2) Verify SPK_B signature with IK_B", "control": step2},
        {"title": "3) Derive SK from DH outputs", "control": step3},
        {"title": "4) Calculate AD", "control": step4},
        {"title": "5) Initialize Double Ratchet and calculate SS", "control": step5},
        {"title": "6) Derive RK and CKs", "control": step6},
    ]
    _show_step_dialog(page, "Alice X3DH -> Double Ratchet bootstrap", steps, on_close=on_close)


def show_bob_x3dh_bootstrap_visualization_dialog(
    page: ft.Page,
    x3dh_header: dict[str, Any],
    shared_secret: bytes | None,
    session_ad: bytes,
    bob_spk_public: str,
    bob_spk_priv: str,
    bob_ik_pub: str,
    bob_ik_priv: str,
    on_close: Callable[[], None] | None = None,
) -> None:
    tooltips = get_tooltip_messages("x3dh")

    ik_a_pub = x3dh_header.get("ik_a_public") if isinstance(x3dh_header.get("ik_a_public"), str) else ""
    ek_a_pub = x3dh_header.get("ek_a_public") if isinstance(x3dh_header.get("ek_a_public"), str) else ""
    spk_b_pub = x3dh_header.get("bob_spk_public") if isinstance(x3dh_header.get("bob_spk_public"), str) else bob_spk_public
    opk_b_id = x3dh_header.get("bob_opk_id")

    step1 = ft.Column(
        controls=[
            ft.Text("1) X3DH header extraction", weight="bold"),
            _flow_node(
                "X3DH header",
                f"ik_a={_last_n_chars(ik_a_pub, 8)}, ek_a={_last_n_chars(ek_a_pub, 8)}, spk_b={_last_n_chars(spk_b_pub, 8)}",
                width=560,
                full_value=x3dh_header,
                tooltip=tooltips.get("x3dh_step_node_header", ""),
            ),
            ft.Text("↓", size=24),
            _flow_node("EXTRACT", circle=True, width=200, height=70, tooltip=tooltips.get("dr_bootstrap_extract", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Derive SK from DH outputs (same pattern as A)", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("DH1", "DH(SPK_B_priv, IK_A_pub)", width=320, full_value=f"SPK_B_priv=local\nIK_A_pub={ik_a_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                    _flow_node("DH2", "DH(IK_B_priv, EK_A_pub)", width=320, full_value=f"IK_B_priv=local\nEK_A_pub={ek_a_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _flow_node("DH3", "DH(SPK_B_priv, EK_A_pub)", width=320, full_value=f"SPK_B_priv=local\nEK_A_pub={ek_a_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                    _flow_node("DH4", "DH(OPK_B_priv, EK_A_pub)", width=320, full_value=f"OPK_B_priv=local (if used)\nOPK_B_id={opk_b_id}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("KDF_SK", circle=True, width=200, height=70, tooltip=tooltips.get("x3dh_step_node_kdf_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("SK", _last_n_chars(shared_secret, 8), width=220, full_value=shared_secret, tooltip=tooltips.get("x3dh_step_key_sk", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Calculate AD", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_A_pub", _last_n_chars(ik_a_pub, 8), width=220, full_value=ik_a_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("IK_B_pub", _last_n_chars(bob_spk_public, 8), width=220, full_value=bob_spk_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("CALC_AD", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_calc_ad", "")),
            ft.Text("↓", size=24),
            _flow_node("AD", _last_n_chars(session_ad, 8), width=280, full_value=session_ad, tooltip=tooltips.get("x3dh_step_key_ad", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("4) Set DHs and RK (Bob init state)", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("SPK_B_pub", _last_n_chars(bob_spk_public, 8), width=220, full_value=bob_spk_public, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("SPK_B_priv", _last_n_chars(bob_spk_priv, 8), width=220, full_value=bob_spk_priv, tooltip=tooltips.get("x3dh_step_key_spk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("SET_DHS", "DHs <- SPK_B keypair", circle=True, width=260, height=70, tooltip=tooltips.get("dr_bootstrap_set_dhs", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("DHs_pub", _last_n_chars(bob_spk_public, 8), width=220, full_value=bob_spk_public, tooltip=tooltips.get("dr_bootstrap_dhs_pub", "")),
                    _flow_node("DHs_priv", _last_n_chars(bob_spk_priv, 8), width=220, full_value=bob_spk_priv, tooltip=tooltips.get("dr_bootstrap_dhs_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("", size=24),
            _flow_node("SK", _last_n_chars(shared_secret, 8), width=220, full_value=shared_secret, tooltip=tooltips.get("x3dh_step_key_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("SET_RK", "RK <- SK", circle=True, width=220, height=70, tooltip=tooltips.get("dr_bootstrap_set_rk", "")),
            ft.Text("↓", size=24),
            _flow_node("RK", _last_n_chars(shared_secret, 8), width=220, full_value=shared_secret, tooltip=tooltips.get("dr_bootstrap_rk", "")),
            ft.Text("↓", size=24),
            _flow_node("Bob ready", "for Double Ratchet receive chain", width=320, tooltip=tooltips.get("dr_bootstrap_ready", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step6 = ft.Column(
        controls=[
            ft.Text("5) Summary of set values", weight="bold"),
            _party_state_panel(
                "Bob bootstrap state",
                [
                    ("DHs_pub", _last_n_chars(bob_spk_public, 8), tooltips.get("dr_bootstrap_dhs_pub", ""), bob_spk_public),
                    ("DHs_priv", _last_n_chars(bob_spk_priv, 8), tooltips.get("dr_bootstrap_dhs_priv", ""), bob_spk_priv),
                    ("AD", _last_n_chars(session_ad, 8), tooltips.get("x3dh_step_key_ad", ""), session_ad),
                    ("RK", _last_n_chars(shared_secret, 8), tooltips.get("dr_bootstrap_rk", ""), shared_secret),
                ],
                tooltip=tooltips.get("dr_bootstrap_summary", ""),
                highlight_labels={"AD", "RK", "DHs_pub", "DHs_priv"},
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    steps = [
        {"title": "1) X3DH header extraction", "control": step1},
        {"title": "2) Derive SK from DH outputs (same pattern as A)", "control": step2},
        {"title": "3) Calculate AD", "control": step3},
        {"title": "4) Set DHs and RK (Bob init state)", "control": step5},
        {"title": "5) Summary of set values", "control": step6},
    ]
    _show_step_dialog(page, "Bob X3DH -> Double Ratchet bootstrap", steps, on_close=on_close)
