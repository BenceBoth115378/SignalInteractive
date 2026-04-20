from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import SpqrHeader
from modules.base_step_visualization import (
    page_size as _shared_page_size,
    to_text as _shared_to_text,
    with_tooltip as _shared_with_tooltip,
)
from modules.tooltip_helpers import get_tooltip_messages


def _to_text(value: Any) -> str:
    return _shared_to_text(value)


def _page_size(page: ft.Page) -> tuple[int, int]:
    return _shared_page_size(page)


def _with_tooltip(control: ft.Control, message: str | None, full_value: Any = None) -> ft.Control:
    return _shared_with_tooltip(control, message, full_value)


def _preview_text(value: Any, limit: int = 48) -> str:
    text = _to_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _last_n_chars(value: Any, count: int = 8) -> str:
    text = _to_text(value)
    if len(text) <= count:
        return text
    return text[-count:]


def _format_plaintext(value: Any) -> str | Any:
    """Convert plaintext bytes to a readable string for visualization."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode('utf-8', errors='replace')
        except Exception:
            return value
    return value


def _var_node(label: str, value: Any, tip_key: str) -> ft.Control:
    return _flow_node(
        label,
        value,
        width=220,
        tooltip=_tt(tip_key),
        full_value=value,
    )


def _tt(key: str) -> str:
    tooltips = get_tooltip_messages("spqr")
    message = tooltips.get(key, "")
    return message if message else "Tooltip missing in src/assets/tooltips.json"


def _function_node(label: str, tip_key: str, full_value: Any = None, value: Any = None) -> ft.Control:
    return _flow_node(
        label,
        circle=True,
        width=220,
        height=70,
        tooltip=_tt(tip_key),
        full_value=full_value,
    )


def _flow_node(
    label: str,
    value: str | None = None,
    circle: bool = False,
    width: int = 260,
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


def _flow_row(items: list[tuple[str, str | None]], tooltip: str | None = None) -> ft.Control:
    return ft.Row(
        controls=[
            _flow_node(label, value, width=220, tooltip=tooltip)
            for label, value in items
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=16,
        wrap=True,
    )


def _state_row(
    label: str,
    value: str,
    tooltip: str | None = None,
    full_value: Any = None,
    highlight: bool = False,
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
    return _with_tooltip(
        ft.Container(
            content=row_control,
            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
            border_radius=6,
            height=32,
        ),
        tooltip,
        full_value,
    )


def _party_state_panel(
    title: str,
    rows: list[tuple[str, str, str | None, Any]],
    tooltip: str | None = None,
    highlight_labels: set[str] | None = None,
) -> ft.Control:
    highlighted = highlight_labels or set()
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


def _header_preview(header: SpqrHeader | None) -> str:
    if header is None:
        return "No header"
    return f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}"


def _before_after_rows(snapshot: dict[str, Any], tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    return [
        (
            "State",
            str(snapshot.get("state", snapshot.get("node", "Unknown"))),
            tooltips.get("spqr_step_state", tooltips.get("spqr_step_node", "")),
            snapshot.get("state", snapshot.get("node", "Unknown")),
        ),
        ("Epoch", str(snapshot.get("epoch", "-")), tooltips.get("spqr_step_epoch", ""), snapshot.get("epoch", "-")),
        ("Direction", str(snapshot.get("direction", "-")), tooltips.get("spqr_step_direction", ""), snapshot.get("direction", "-")),
        ("RK", str(snapshot.get("rk_tail", "None")), tooltips.get("spqr_step_rk", ""), snapshot.get("rk_tail", "None")),
        (
            "CKs",
            str(snapshot.get("send_ck_tail", "None")),
            tooltips.get("spqr_step_send_ck", ""),
            snapshot.get("send_ck_tail", "None"),
        ),
        (
            "CKr",
            str(snapshot.get("recv_ck_tail", "None")),
            tooltips.get("spqr_step_recv_ck", ""),
            snapshot.get("recv_ck_tail", "None"),
        ),
    ]


def _send_keys_unsampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:

    header: SpqrHeader | None = step_data.get("header")
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}

    dk = after_node.get("dk")
    ek_header = after_node.get("ek_header")
    ek_vector = after_node.get("ek_vector")
    header_encoder = after_node.get("header_encoder") if isinstance(after_node.get("header_encoder"), dict) else {}

    ek_header_bytes = bytes(ek_header) if isinstance(ek_header, (bytes, bytearray)) else None
    header_encoder_message = header_encoder.get("message") if isinstance(header_encoder.get("message"), (bytes, bytearray)) else None
    header_bytes = bytes(header_encoder_message[:64]) if isinstance(header_encoder_message, (bytes, bytearray)) and len(header_encoder_message) >= 64 else None
    if header_bytes is None:
        header_bytes = ek_header_bytes
    mac = bytes(header_encoder_message[64:]) if isinstance(header_encoder_message, (bytes, bytearray)) and len(header_encoder_message) > 64 else None
    header_with_mac = bytes(header_encoder_message) if isinstance(header_encoder_message, (bytes, bytearray)) else None
    if header_with_mac is None and isinstance(header_bytes, bytes) and isinstance(mac, bytes):
        header_with_mac = header_bytes + mac

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else after.get("epoch")
    sending_epoch = msg_epoch - 1 if isinstance(msg_epoch, int) else "self.epoch - 1"

    return [
        {
            "title": "Generate key material",
            "control": ft.Column(
                controls=[
                    ft.Text("Generate key material", weight="bold"),
                    _function_node(
                        "IncrementalKEM.KeyGen",
                        "spqr_step_keygen_fn",
                        full_value="Outputs: dk, ek_header, ek_vector",
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("dk", dk, "spqr_step_dk"),
                            _var_node("ek_header", ek_header, "spqr_step_ek_header"),
                            _var_node("ek_vector", ek_vector, "spqr_step_ek_vector"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Authenticate header",
            "control": ft.Column(
                controls=[
                    ft.Text("Authenticate header", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("auth", after_node.get("auth"), "spqr_step_auth"),
                            _var_node("epoch", msg_epoch, "spqr_step_epoch"),
                            _var_node("header", header_bytes, "spqr_step_header_in_mac"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Authenticator.MacHdr",
                        "spqr_step_machdr_fn",
                        full_value="mac = MacHdr(auth, epoch, header)",
                    ),
                    ft.Text("↓", size=24),
                    _var_node("mac", mac, "spqr_step_mac"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Start header stream",
            "control": ft.Column(
                controls=[
                    ft.Text("Start header stream", weight="bold"),
                    _var_node("header||mac", header_with_mac, "spqr_step_header_with_mac", value="Initialized with header||mac"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "new Encoder",
                        "spqr_step_encode_fn",
                        full_value="header_encoder = Encode(header || mac)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "header_encoder",
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_header_encoder"),
                        full_value=header_encoder,
                    ),
                    ft.Divider(height=1),
                    _function_node(
                        "Encoder.next_chunk",
                        "spqr_step_next_chunk",
                        full_value="chunk = header_encoder.next_chunk()",
                    ),
                    ft.Text("↓", size=24),
                    _var_node("Header chunk", chunk, "spqr_step_chunk"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Build message with header chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Build message with header chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("Header chunk", chunk, "spqr_step_chunk_in_msg"),
                            _var_node("epoch", msg_epoch, "spqr_step_epoch_in_msg"),
                            _flow_node(
                                "msg.type",
                                "Hdr",
                                width=220,
                                tooltip=_tt("spqr_step_msg_type_in_msg"),
                                full_value="SpqrMessageType.HDR",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Build SpqrMessage",
                        circle=True,
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_build_message"),
                        full_value={
                            "epoch": msg_epoch,
                            "msg_type": "Hdr",
                            "data": chunk,
                        },
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("epoch", msg_epoch, "spqr_step_msg_epoch"),
                            _flow_node(
                                "msg.type",
                                "Hdr",
                                width=220,
                                tooltip=_tt("spqr_step_msg_type"),
                                full_value="SpqrMessageType.HDR",
                            ),
                            _var_node("msg.data", chunk, "spqr_step_msg_data"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Send result",
            "control": ft.Column(
                controls=[
                    ft.Text("Send result", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node(
                                "sending_epoch",
                                sending_epoch,
                                "spqr_step_sending_epoch",
                            ),
                            _flow_node(
                                "output_key",
                                "None",
                                width=220,
                                tooltip=_tt("spqr_step_output_key"),
                                full_value=None,
                            ),
                            _flow_node(
                                "next_state",
                                "KeysSampled",
                                width=220,
                                tooltip=_tt("spqr_step_next_state"),
                                full_value="KeysSampled",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _send_keys_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:

    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next header chunk",
        build_title="Build message with header chunk",
        chunk_expr="chunk = header_encoder.next_chunk()",
        msg_type_label="Hdr",
        msg_type_full="SpqrMessageType.HDR",
        next_state="KeysSampled",
    )


def _send_header_sent(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ek_vector chunk",
        build_title="Build message with ek_vector chunk",
        chunk_expr="chunk = ek_encoder.next_chunk()",
        msg_type_label="Ek",
        msg_type_full="SpqrMessageType.EK",
        next_state="HeaderSent",
    )


def _send_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ek_vector chunk",
        build_title="Build message with ek_vector chunk and acknowledgment",
        chunk_expr="chunk = ek_encoder.next_chunk()",
        msg_type_label="EkCt1Ack",
        msg_type_full="SpqrMessageType.EK_CT1_ACK",
        next_state="Ct1Received",
    )


def _send_ek_sent_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_none_send_steps(
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        msg_type_label="None",
        msg_type_full="SpqrMessageType.NONE",
        next_state="EkSentCt1Received",
    )


def _send_no_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_none_send_steps(
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        msg_type_label="None",
        msg_type_full="SpqrMessageType.NONE",
        next_state="NoHeaderReceived",
    )


def _send_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}
    auth = after_node.get("auth")
    ek_header = after_node.get("ek_header")
    encaps_secret = after_node.get("encaps_secret")
    ct1 = after_node.get("ct1")
    ct1_encoder = after_node.get("ct1_encoder") if isinstance(after_node.get("ct1_encoder"), dict) else {}
    output_key = {
        "epoch": ctx["msg_epoch"],
        "key": "derived by KDF_OK",
    }

    return [
        {
            "title": "Generate shared secret and ct1 using incremental KEM interface",
            "control": ft.Column(
                controls=[
                    ft.Text("Generate shared secret and ct1 using incremental KEM interface", weight="bold"),
                    _var_node("ek_header", ek_header, "spqr_step_ek_header"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "IncrementalKEM.Encaps1",
                        "spqr_step_keygen_fn",
                        full_value="encaps_secret, ct1, ss = Encaps1(ek_header)",
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("encaps_secret", encaps_secret, "spqr_step_ek_vector"),
                            _var_node("ct1", ct1, "spqr_step_chunk"),
                            _flow_node(
                                "ss",
                                "derived",
                                width=220,
                                tooltip=_tt("spqr_step_key_evolution"),
                                full_value="shared secret",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {

            "title": "Derive output",
            "control": ft.Column(
                controls=[
                    ft.Text("Derive output key", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("ss", "ss_from_encaps1_value", "spqr_step_ss"),
                            _var_node("epoch", ctx["msg_epoch"], "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "KDF_OK",
                        "spqr_step_kdf_ok",
                        full_value="KDF_OK(ss, epoch)",
                    ),
                    ft.Text("↓", size=24),
                    _var_node(
                        "SS (output_key)",
                        output_key,
                        "spqr_step_output_key",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Update authenticator",
            "control": ft.Column(
                controls=[
                    ft.Text("Update authenticator", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("auth", auth, "spqr_step_auth"),
                            _var_node("epoch", ctx["msg_epoch"], "spqr_step_epoch"),
                            _var_node("ss", "ss_from_kdf_ok_value", "spqr_step_ss_after_kdf"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Authenticator.Update",
                        "spqr_step_machdr_fn",
                        full_value="Authenticator.Update(auth, epoch, ss)",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Start ct1 stream",
            "control": ft.Column(
                controls=[
                    ft.Text("Start ct1 stream", weight="bold"),
                    _var_node("ct1", ct1, "spqr_step_chunk"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Encode",
                        "spqr_step_encode_fn",
                        full_value="ct1_encoder = Encode(ct1)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "ct1_encoder",
                        _last_n_chars(ct1_encoder.get("chunk_size"), 8),
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_header_encoder"),
                        full_value=ct1_encoder,
                    ),
                    ft.Divider(height=1),
                    _function_node(
                        "Encoder.next_chunk",
                        "spqr_step_next_chunk",
                        full_value="chunk = ct1_encoder.next_chunk()",
                    ),
                    ft.Text("↓", size=24),
                    _var_node("chunk", ctx["chunk"], "spqr_step_chunk"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        *_build_message_step(
            build_title="Build message with ct1 chunk",
            chunk=ctx["chunk"],
            msg_epoch=ctx["msg_epoch"],
            msg_type_label="Ct1",
            msg_type_full="SpqrMessageType.CT1",
        ),
        _build_send_result_step(
            sending_epoch=ctx["sending_epoch"],
            output_key_label="OutputKey",
            output_key=output_key,
            next_state="Ct1Sampled",
        ),
    ]


def _send_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ct1 chunk",
        build_title="Build message with ct1 chunk",
        chunk_expr="chunk = ct1_encoder.next_chunk()",
        msg_type_label="Ct1",
        msg_type_full="SpqrMessageType.CT1",
        next_state="Ct1Sampled",
    )


def _send_ek_received_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ct1 chunk",
        build_title="Build message with ct1 chunk",
        chunk_expr="chunk = ct1_encoder.next_chunk()",
        msg_type_label="Ct1",
        msg_type_full="SpqrMessageType.CT1",
        next_state="EkReceivedCt1Sampled",
    )


def _send_ct1_acknowledged(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_none_send_steps(
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        msg_type_label="None",
        msg_type_full="SpqrMessageType.NONE",
        next_state="Ct1Acknowledged",
    )


def _send_ct2_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ct2 chunk",
        build_title="Build message with ct2 chunk",
        chunk_expr="chunk = ct2_encoder.next_chunk()",
        msg_type_label="Ct2",
        msg_type_full="SpqrMessageType.CT2",
        next_state="Ct2Sampled",
    )


def _build_message_step(
    build_title: str,
    chunk: Any,
    msg_epoch: Any,
    msg_type_label: str,
    msg_type_full: str,
) -> list[dict[str, Any]]:
    return [
        {
            "title": build_title,
            "control": ft.Column(
                controls=[
                    ft.Text(build_title, weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("chunk", chunk, "spqr_step_chunk_in_msg"),
                            _var_node("epoch", msg_epoch, "spqr_step_epoch_in_msg"),
                            _flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=_tt("spqr_step_msg_type_in_msg"),
                                full_value=msg_type_full,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Build SpqrMessage",
                        circle=True,
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_build_message"),
                        full_value={
                            "epoch": msg_epoch,
                            "msg_type": msg_type_label,
                            "data": chunk,
                        },
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("epoch", msg_epoch, "spqr_step_msg_epoch"),
                            _flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=_tt("spqr_step_msg_type"),
                                full_value=msg_type_full,
                            ),
                            _var_node("msg.data", chunk, "spqr_step_msg_data"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        }
    ]


def _build_send_result_step(
    sending_epoch: Any,
    output_key_label: str,
    output_key: Any,
    next_state: str,
) -> dict[str, Any]:
    return {
        "title": "Send result",
        "control": ft.Column(
            controls=[
                ft.Text("Send result", weight="bold"),
                ft.Row(
                    controls=[
                        _var_node(
                            "sending_epoch",
                            sending_epoch,
                            "spqr_step_sending_epoch",
                        ),
                        _flow_node(
                            "output_key",
                            output_key_label,
                            width=220,
                            tooltip=_tt("spqr_step_output_key"),
                            full_value=output_key,
                        ),
                        _flow_node(
                            "next_state",
                            next_state,
                            width=220,
                            tooltip=_tt("spqr_step_next_state"),
                            full_value=next_state,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                    wrap=True,
                ),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_chunk_send_steps(
    chunk: Any,
    msg_epoch: Any,
    sending_epoch: Any,
    generate_title: str,
    build_title: str,
    chunk_expr: str,
    msg_type_label: str,
    msg_type_full: str,
    next_state: str,
) -> list[dict[str, Any]]:
    return [
        {
            "title": generate_title,
            "control": ft.Column(
                controls=[
                    ft.Text(generate_title, weight="bold"),
                    _function_node(
                        "Encoder.next_chunk",
                        "spqr_step_next_chunk",
                        full_value=chunk_expr,
                    ),
                    ft.Text("↓", size=24),
                    _var_node("chunk", chunk, "spqr_step_chunk"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        *_build_message_step(
            build_title=build_title,
            chunk=chunk,
            msg_epoch=msg_epoch,
            msg_type_label=msg_type_label,
            msg_type_full=msg_type_full,
        ),
        _build_send_result_step(
            sending_epoch=sending_epoch,
            output_key_label="None",
            output_key=None,
            next_state=next_state,
        ),
    ]


def _build_none_send_steps(
    msg_epoch: Any,
    sending_epoch: Any,
    msg_type_label: str,
    msg_type_full: str,
    next_state: str,
) -> list[dict[str, Any]]:
    return [
        {
            "title": "Build message with no data to send",
            "control": ft.Column(
                controls=[
                    ft.Text("Build message with no data to send", weight="bold"),
                    ft.Row(
                        controls=[
                            _flow_node("data", "None", width=220, tooltip=_tt("spqr_step_chunk_in_msg"), full_value=None),
                            _var_node("epoch", msg_epoch, "spqr_step_epoch_in_msg"),
                            _flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=_tt("spqr_step_msg_type_in_msg"),
                                full_value=msg_type_full,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Build SpqrMessage",
                        circle=True,
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_build_message"),
                        full_value={
                            "epoch": msg_epoch,
                            "msg_type": msg_type_label,
                            "data": None,
                        },
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("epoch", msg_epoch, "spqr_step_msg_epoch"),
                            _flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=_tt("spqr_step_msg_type"),
                                full_value=msg_type_full,
                            ),
                            _flow_node("msg.data", "None", width=220, tooltip=_tt("spqr_step_msg_data"), full_value=None),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        _build_send_result_step(
            sending_epoch=sending_epoch,
            output_key_label="None",
            output_key=None,
            next_state=next_state,
        ),
    ]


def _send_context(step_data: dict[str, Any]) -> dict[str, Any]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}
    active_node = after_node if after_node else before_node

    msg_epoch = (
        header.msg.epoch
        if header is not None
        else active_node.get("epoch", after.get("epoch", before.get("epoch")))
    )
    sending_epoch = msg_epoch - 1 if isinstance(msg_epoch, int) else "self.epoch - 1"
    chunk = header.msg.data if header is not None else None

    return {
        "header": header,
        "before": before,
        "after": after,
        "before_node": before_node,
        "after_node": after_node,
        "msg_epoch": msg_epoch,
        "sending_epoch": sending_epoch,
        "chunk": chunk,
    }


def _output_key_expected(action: str, state_name: str) -> bool:
    if action == "send" and state_name == "HeaderReceived":
        return True
    if action == "receive" and state_name == "EkSentCt1Received":
        return True
    return False


def _build_intro_step(before: dict[str, Any], tooltips: dict[str, str]) -> dict[str, Any]:
    intro_control = ft.Column(
        controls=[
            _party_state_panel(
                "Before snapshot",
                _before_after_rows(before, tooltips),
                tooltip=tooltips.get("spqr_step_before_panel", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "title": "State before",
        "control": intro_control,
    }


def _build_output_key_step(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    header: SpqrHeader | None,
    tooltips: dict[str, str],
) -> dict[str, Any]:
    rk_changed = before.get("rk_tail") != after.get("rk_tail")
    output_key_produced = _output_key_expected(action, state_name)
    output_label = "output_key produced" if output_key_produced else "output_key = None"
    rk_label = "RK derivation needed" if rk_changed else "No new RK derived"

    output_control = ft.Column(
        controls=[
            ft.Text("Output key and root-key decision", weight="bold"),
            _flow_node(
                "SCKA output",
                output_label,
                width=320,
                tooltip=tooltips.get("spqr_step_key_evolution", ""),
            ),
            ft.Text("↓", size=24),
            _flow_node(
                "Root key derivation",
                rk_label,
                width=320,
                tooltip=tooltips.get("spqr_step_rk_change", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "title": "Output key decision",
        "control": output_control,
    }


def _build_rk_derivation_step(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    step_data: dict[str, Any],
) -> dict[str, Any] | None:
    if before.get("rk_tail") == after.get("rk_tail"):
        return None

    derivation_trace = step_data.get("encrypt_trace") if isinstance(step_data.get("encrypt_trace"), dict) else {}
    scka_output_key = derivation_trace.get("scka_output_key")
    if scka_output_key is None:
        scka_output_key = "from SCKA output"

    rk_before = derivation_trace.get("rk_before", before.get("rk_tail"))
    rk_after = derivation_trace.get("rk_after", after.get("rk_tail"))
    new_cks = derivation_trace.get("new_cks", after.get("send_ck_tail"))
    new_ckr = derivation_trace.get("new_ckr", after.get("recv_ck_tail"))

    return {
        "title": "RK derivation",
        "control": ft.Column(
            controls=[
                ft.Text("RK derivation", weight="bold"),
                ft.Row(
                    controls=[
                        _var_node("RK", rk_before, "spqr_step_rk"),
                        _var_node("SCKA_output_key", scka_output_key, "spqr_step_output_key"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                    wrap=True,
                ),
                ft.Text("↓", size=24),
                _function_node(
                    "KDF_SCKA_RK",
                    "spqr_step_key_evolution",
                    full_value="new_RK, new_CKs, new_CKr = KDF_SCKA_RK(RK, SCKA_output_key)",
                ),
                ft.Text("↓", size=24),
                ft.Row(
                    controls=[
                        _var_node("new RK", rk_after, "spqr_step_rk"),
                        _var_node("new CKs", new_cks, "spqr_step_send_ck"),
                        _var_node("new CKr", new_ckr, "spqr_step_recv_ck"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                    wrap=True,
                ),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_send_steps(state_name: str, step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    builders: dict[str, Callable[[dict[str, Any], dict[str, str]], list[dict[str, Any]]]] = {
        "KeysUnsampled": _send_keys_unsampled,
        "KeysSampled": _send_keys_sampled,
        "HeaderSent": _send_header_sent,
        "Ct1Received": _send_ct1_received,
        "EkSentCt1Received": _send_ek_sent_ct1_received,
        "NoHeaderReceived": _send_no_header_received,
        "HeaderReceived": _send_header_received,
        "Ct1Sampled": _send_ct1_sampled,
        "EkReceivedCt1Sampled": _send_ek_received_ct1_sampled,
        "Ct1Acknowledged": _send_ct1_acknowledged,
        "Ct2Sampled": _send_ct2_sampled,
    }
    builder = builders.get(state_name)
    if builder is None:
        return []
    return builder(step_data, tooltips)


def _receive_keys_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    condition_met = msg_epoch == self_epoch and msg_type == "Ct1"

    ct1_decoder = after_node.get("ct1_decoder") if isinstance(after_node.get("ct1_decoder"), dict) else None
    ek_vector = before_node.get("ek_vector", after_node.get("ek_vector"))
    ek_encoder = after_node.get("ek_encoder") if isinstance(after_node.get("ek_encoder"), dict) else None

    return [
        {
            "title": "Initialize Decoder",
            "control": ft.Column(
                controls=[
                    ft.Text("Initialize Decoder", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                            _flow_node("msg.type", str(msg_type), width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type),
                            _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Condition",
                        "msg.epoch == self.epoch and msg.type == Ct1",
                        width=420,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=condition_met,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "new Decoder()",
                        "spqr_step_state_op",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "ct1_decoder",
                        width=260,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=ct1_decoder,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "chunk -> Decoder add chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("chunk -> Decoder add chunk", weight="bold"),
                    _var_node("msg.data - Chunk", chunk, "spqr_step_chunk"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Decoder.add_chunk",
                        "spqr_step_state_op",
                        full_value="ct1_decoder.add_chunk(chunk)",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "ek_vector -> Initialize EkEncoder -> EkEncoder",
            "control": ft.Column(
                controls=[
                    ft.Text("ek_vector -> Initialize EkEncoder -> EkEncoder", weight="bold"),
                    _var_node("ek_vector", ek_vector, "spqr_step_ek_vector"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "new Encoder()",
                        "spqr_step_encode_fn",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "EkEncoder",
                        "initialized with ek_vector" if ek_encoder is not None else "not initialized",
                        width=260,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=ek_encoder,
                    ),
                    ft.Divider(height=10),
                    _flow_node(
                        "Next state",
                        "HeaderSent",
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_header_sent(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    ct1_decoder = before_node.get("ct1_decoder") if isinstance(before_node.get("ct1_decoder"), dict) else None
    has_message = str(after.get("state", before.get("state", ""))) == "Ct1Received"

    return [
        {
            "title": "chunk -> Decoder add chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("chunk -> Decoder add chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("chunk", chunk, "spqr_step_chunk"),
                            _flow_node(
                                "Decoder",
                                "ct1_decoder",
                                width=220,
                                tooltip=_tt("spqr_step_state_op"),
                                full_value=ct1_decoder,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Decoder.add_chunk",
                        "spqr_step_state_op",
                        full_value="ct1_decoder.add_chunk(chunk)",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decoder has message()",
            "control": ft.Column(
                controls=[
                    ft.Text("Decoder has message()", weight="bold"),
                    _function_node(
                        "Decoder.has_message",
                        "spqr_step_state_op",
                        full_value="ct1_decoder.has_message()",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "has_message",
                        "yes" if has_message else "no",
                        width=220,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=has_message,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state transition" if has_message else "remain in current state",
                        "Ct1Received" if has_message else "HeaderSent",
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_no_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    condition_met = msg_epoch == self_epoch and msg_type == "Hdr"
    next_state = after.get("state", before.get("state"))
    completed = next_state == "HeaderReceived"
    header_with_mac = after_node.get("ek_header") if isinstance(after_node.get("ek_header"), (bytes, bytearray)) else None

    return [
        {
            "title": "Initialize header decoder",
            "control": ft.Column(
                controls=[
                    ft.Text("Initialize header decoder", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                            _flow_node("msg.type", str(msg_type), width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type),
                            _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Condition",
                        "msg.epoch == self.epoch and msg.type == Hdr",
                        width=420,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=condition_met,
                    ),
                    ft.Text("↓", size=24),
                    _var_node("chunk", chunk, "spqr_step_chunk"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Decoder.add_chunk",
                        "spqr_step_state_op",
                        full_value="header_decoder.add_chunk(chunk)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "header_with_mac",
                        header_with_mac,
                        width=320,
                        tooltip=_tt("spqr_step_header_with_mac"),
                        full_value=header_with_mac,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decoder.has_message()",
            "control": ft.Column(
                controls=[
                    ft.Text("Decoder.has_message()", weight="bold"),
                    _flow_node(
                        "has_message",
                        "yes" if completed else "no",
                        width=220,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=completed,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state transition" if completed else "remain in current state",
                        "HeaderReceived" if completed else "NoHeaderReceived",
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=next_state,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}

    return [
        {
            "title": "No action taken",
            "control": ft.Column(
                controls=[
                    ft.Text("No action taken", weight="bold"),
                    _flow_node(
                        "HeaderReceived.receive",
                        "noop",
                        width=260,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value="No action taken",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_state = str(after.get("state", before.get("state", "")))

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    msg_type_label = str(msg_type)
    is_ek_branch = msg_epoch == self_epoch and msg_type_label == "Ek"
    is_ek_ack_branch = msg_epoch == self_epoch and msg_type_label == "EkCt1Ack"

    if is_ek_branch:
        completed = after_state == "EkReceivedCt1Sampled"
        return [
            {
                "title": "EK branch guard",
                "control": ft.Column(
                    controls=[
                        ft.Text("EK branch guard", weight="bold"),
                        ft.Row(
                            controls=[
                                _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                                _flow_node("msg.type", msg_type_label, width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type_label),
                                _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=16,
                            wrap=True,
                        ),
                        ft.Text("↓", size=24),
                        _flow_node(
                            "Condition",
                            "msg.epoch == self.epoch and msg.type == Ek",
                            width=420,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=is_ek_branch,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Add EK chunk",
                "control": ft.Column(
                    controls=[
                        ft.Text("Add EK chunk", weight="bold"),
                        _var_node("chunk", chunk, "spqr_step_chunk"),
                        ft.Text("↓", size=24),
                        _function_node(
                            "ek_decoder.add_chunk",
                            "spqr_step_state_op",
                            full_value="ek_decoder.add_chunk(chunk)",
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Check EK completeness",
                "control": ft.Column(
                    controls=[
                        ft.Text("Check EK completeness", weight="bold"),
                        _flow_node(
                            "ek_decoder.has_message",
                            "yes" if completed else "no",
                            width=260,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=completed,
                        ),
                        ft.Text("↓", size=24),
                        _flow_node(
                            "state transition",
                            "EkReceivedCt1Sampled" if completed else "Ct1Sampled",
                            width=260,
                            circle=True,
                            tooltip=_tt("spqr_step_next_state"),
                            full_value=after_state,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
        ]

    if is_ek_ack_branch:
        completed = after_state == "Ct2Sampled"
        return [
            {
                "title": "EK_CT1_ACK branch guard",
                "control": ft.Column(
                    controls=[
                        ft.Text("EK_CT1_ACK branch guard", weight="bold"),
                        ft.Row(
                            controls=[
                                _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                                _flow_node("msg.type", msg_type_label, width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type_label),
                                _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=16,
                            wrap=True,
                        ),
                        ft.Text("↓", size=24),
                        _flow_node(
                            "Condition",
                            "msg.epoch == self.epoch and msg.type == EkCt1Ack",
                            width=420,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=is_ek_ack_branch,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Add EK_CT1_ACK chunk",
                "control": ft.Column(
                    controls=[
                        ft.Text("Add EK_CT1_ACK chunk", weight="bold"),
                        _var_node("chunk", chunk, "spqr_step_chunk"),
                        ft.Text("↓", size=24),
                        _function_node(
                            "ek_decoder.add_chunk",
                            "spqr_step_state_op",
                            full_value="ek_decoder.add_chunk(chunk)",
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Check EK completeness",
                "control": ft.Column(
                    controls=[
                        ft.Text("Check EK completeness", weight="bold"),
                        _flow_node(
                            "ek_decoder.has_message",
                            "yes" if completed else "no",
                            width=260,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=completed,
                        ),
                        ft.Text("↓", size=24),
                        _flow_node(
                            "state transition",
                            "Ct2Sampled" if completed else "Ct1Acknowledged",
                            width=300,
                            circle=True,
                            tooltip=_tt("spqr_step_next_state"),
                            full_value=after_state,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
        ]

    return [
        {
            "title": "No matching branch",
            "control": ft.Column(
                controls=[
                    ft.Text("No matching branch", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                            _flow_node("msg.type", msg_type_label, width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type_label),
                            _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state transition",
                        "Ct1Sampled (no-op)",
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after_state,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        }
    ]


def _receive_ek_received_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}

    return [
        {
            "title": "Complete encapsulation",
            "control": ft.Column(
                controls=[
                    ft.Text("Complete encapsulation", weight="bold"),
                    _flow_node(
                        "EK_CT1_ACK",
                        str(step_data.get("header").msg.msg_type.value if isinstance(step_data.get("header"), SpqrHeader) else ""),
                        width=240,
                        tooltip=_tt("spqr_step_msg_type"),
                        full_value=step_data.get("header").msg.to_dict() if isinstance(step_data.get("header"), SpqrHeader) else None,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Encaps2 + MacCt",
                        "spqr_step_state_op",
                        full_value="ct2 = Encaps2(...); mac = MacCt(...)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct1_acknowledged(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    completed = after.get("state", before.get("state")) == "Ct2Sampled"

    return [
        {
            "title": "Add EK_CT1_ACK chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Add EK_CT1_ACK chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                            _flow_node("msg.type", str(msg_type), width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type),
                            _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _var_node("chunk", chunk, "spqr_step_chunk"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "ek_decoder.add_chunk",
                        "spqr_step_state_op",
                        full_value="ek_decoder.add_chunk(chunk)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "has_message",
                        "yes" if completed else "no",
                        width=220,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=completed,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state transition",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct2_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    next_epoch = msg_epoch + 1 if isinstance(msg_epoch, int) else None

    return [
        {
            "title": "Check next epoch",
            "control": ft.Column(
                controls=[
                    ft.Text("Check next epoch", weight="bold"),
                    _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Condition",
                        "msg.epoch == self.epoch + 1",
                        width=320,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=bool(next_epoch),
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Next state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")

    return [
        {
            "title": "Initialize ct2 decoder",
            "control": ft.Column(
                controls=[
                    ft.Text("Initialize ct2 decoder", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                            _flow_node("msg.type", str(msg_type), width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type),
                            _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Condition",
                        "msg.epoch == self.epoch and msg.type == Ct2",
                        width=420,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=msg_type == "Ct2",
                    ),
                    ft.Text("↓", size=24),
                    _var_node("chunk", chunk, "spqr_step_chunk"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "ct2_decoder = Decoder_new(CT2_SIZE + MAC_SIZE)",
                        "spqr_step_state_op",
                        full_value="ct2_decoder = Decoder_new(CT2_SIZE + MAC_SIZE)",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Add CT2 chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Add CT2 chunk", weight="bold"),
                    _function_node(
                        "ct2_decoder.add_chunk",
                        "spqr_step_state_op",
                        full_value="ct2_decoder.add_chunk(chunk)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state transition",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ek_sent_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    completed = after.get("state", before.get("state")) == "NoHeaderReceived"
    output_key = step_data.get("receive_trace", {}).get("scka_output_key") if isinstance(step_data.get("receive_trace"), dict) else None

    return [
        {
            "title": "Add CT2 chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Add CT2 chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("msg.epoch", msg_epoch, "spqr_step_epoch"),
                            _flow_node("msg.type", str(msg_type), width=220, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type),
                            _var_node("self.epoch", self_epoch, "spqr_step_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _var_node("chunk", chunk, "spqr_step_chunk"),
                    ft.Text("↓", size=24),
                    _function_node(
                        "ct2_decoder.add_chunk",
                        "spqr_step_state_op",
                        full_value="ct2_decoder.add_chunk(chunk)",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decoder.has_message()",
            "control": ft.Column(
                controls=[
                    ft.Text("Decoder.has_message()", weight="bold"),
                    _flow_node(
                        "has_message",
                        "yes" if completed else "no",
                        width=220,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=completed,
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "state transition" if completed else "remain in current state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        circle=True,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Output key",
            "control": ft.Column(
                controls=[
                    ft.Text("Output key", weight="bold"),
                    _var_node("output_key", output_key, "spqr_step_output_key"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _build_receive_chain_steps(state_name: str, step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    builders: dict[str, Callable[[dict[str, Any], dict[str, str]], list[dict[str, Any]]]] = {
        # "KeysUnsampled": _receive_keys_unsampled,
        "KeysSampled": _receive_keys_sampled,
        "HeaderSent": _receive_header_sent,
        "Ct1Received": _receive_ct1_received,
        "EkSentCt1Received": _receive_ek_sent_ct1_received,
        "NoHeaderReceived": _receive_no_header_received,
        "HeaderReceived": _receive_header_received,
        "Ct1Sampled": _receive_ct1_sampled,
        "EkReceivedCt1Sampled": _receive_ek_received_ct1_sampled,
        "Ct1Acknowledged": _receive_ct1_acknowledged,
        "Ct2Sampled": _receive_ct2_sampled,
    }
    builder = builders.get(state_name)
    if builder is None:
        return []
    return builder(step_data, tooltips)


def _build_send_message_pipeline_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    plaintext = step_data.get("plaintext")
    ciphertext = step_data.get("cipher")
    encrypt_trace = step_data.get("encrypt_trace") if isinstance(step_data.get("encrypt_trace"), dict) else {}

    sending_epoch = encrypt_trace.get("sending_epoch", header.msg.epoch - 1 if header is not None else "-")
    counter = encrypt_trace.get("counter", header.n if header is not None else "-")
    chain_key_before = encrypt_trace.get("chain_key_before")
    chain_key_after = encrypt_trace.get("chain_key_after")
    mk = encrypt_trace.get("mk")
    ad_header = encrypt_trace.get("ad_header")

    header_msg = header.msg if header is not None else None
    header_payload = {
        "msg": header_msg.to_dict() if header_msg is not None else None,
        "n": header.n if header is not None else None,
    }

    return [
        {
            "title": "Message key derivation",
            "control": ft.Column(
                controls=[
                    ft.Text("Message key derivation", weight="bold"),
                    _var_node("sending_epoch", sending_epoch, "spqr_step_sending_epoch"),
                    ft.Text("↓", size=24),
                    _function_node("Get sending chain", f"epoch {sending_epoch}"),
                    ft.Text("↓", size=24),
                    _var_node("CKs", chain_key_before, "spqr_step_send_ck"),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            _var_node("counter", counter, "spqr_step_msg_epoch"),
                            _var_node("CKs", chain_key_before, "spqr_step_send_ck"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node("KDF_SCKA_CK", "spqr_step_kdf_scka_ck"),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("new CKs", chain_key_after, "spqr_step_send_ck"),
                            _var_node("mk", mk, "spqr_step_output_key"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Build SPQR header",
            "control": ft.Column(
                controls=[
                    ft.Text("Build SPQR header", weight="bold"),
                    ft.Row(
                        controls=[
                            _flow_node("msg", _header_preview(header) if header is not None else "None", width=260, tooltip=_tt("spqr_step_header"), full_value=header_msg.to_dict() if header_msg is not None else None),
                            _var_node("n", header.n if header is not None else None, "spqr_step_msg_epoch"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Build SpqrHeader",
                        "spqr_step_build_message",
                        full_value="header = SpqrHeader(msg=msg, n=n)",
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "header",
                        _header_preview(header),
                        width=420,
                        tooltip=_tt("spqr_step_header"),
                        full_value=header_payload,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Encrypt message",
            "control": ft.Column(
                controls=[
                    ft.Text("Encrypt message", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("mk", mk, "spqr_step_output_key"),
                            _var_node("plaintext", _format_plaintext(plaintext), "spqr_step_chunk"),
                            _var_node("AD||header", ad_header, "spqr_step_header_with_mac"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Encrypt",
                        "spqr_step_build_message",
                        full_value="ciphertext = ENCRYPT(mk, plaintext, AD || header)",
                    ),
                    ft.Text("↓", size=24),
                    _var_node("ciphertext", ciphertext, "spqr_step_msg_data"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _build_receive_message_pipeline_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    ciphertext = step_data.get("cipher")
    decrypted = step_data.get("decrypted")
    receive_trace = step_data.get("receive_trace") if isinstance(step_data.get("receive_trace"), dict) else {}

    receiving_epoch = receive_trace.get("receiving_epoch", header.msg.epoch - 1 if header is not None else "-")
    counter = receive_trace.get("counter", header.n if header is not None else "-")
    chain_key_before = receive_trace.get("chain_key_before")
    chain_key_after = receive_trace.get("chain_key_after")
    mk = receive_trace.get("mk")
    used_skipped_key = bool(receive_trace.get("used_skipped_key", False))
    ad_header = receive_trace.get("ad_header")

    if used_skipped_key:
        derivation_note = "MK restored from skipped-key store"
    else:
        derivation_note = "MK derived from receive chain"

    return [
        {
            "title": "Message key derivation",
            "control": ft.Column(
                controls=[
                    ft.Text("Message key derivation", weight="bold"),
                    _var_node("receiving_epoch", receiving_epoch, "spqr_step_epoch"),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "Get receiving chain",
                        f"epoch {receiving_epoch}",
                        circle=True,
                        width=260,
                        tooltip=_tt("spqr_step_recv_ck"),
                        full_value={"epoch": receiving_epoch},
                    ),
                    ft.Text("↓", size=24),
                    _flow_node(
                        "MK",
                        derivation_note,
                        width=320,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value={"used_skipped_key": used_skipped_key},
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            _var_node("counter", counter, "spqr_step_msg_epoch"),
                            _var_node("CKr", chain_key_before, "spqr_step_recv_ck"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node("KDF_SCKA_CK", "spqr_step_kdf_scka_ck"),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            _var_node("new CKr", chain_key_after, "spqr_step_recv_ck"),
                            _var_node("mk", mk, "spqr_step_output_key"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decrypt message",
            "control": ft.Column(
                controls=[
                    ft.Text("Decrypt message", weight="bold"),
                    ft.Row(
                        controls=[
                            _var_node("mk", mk, "spqr_step_output_key"),
                            _var_node("ciphertext", ciphertext, "spqr_step_msg_data"),
                            _var_node("AD||header", ad_header, "spqr_step_header_with_mac"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    _function_node(
                        "Decrypt",
                        "spqr_step_build_message",
                        full_value="plaintext = DECRYPT(mk, ciphertext, AD || header)",
                    ),
                    ft.Text("↓", size=24),
                    _var_node("plaintext", _format_plaintext(decrypted), "spqr_step_chunk"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _build_after_step(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    tooltips: dict[str, str],
) -> dict[str, Any]:
    before_rows = _before_after_rows(before, tooltips)
    after_rows = _before_after_rows(after, tooltips)

    before_state = before.get("state", before.get("node"))
    after_state = after.get("state", after.get("node"))

    changed_labels: set[str] = set()
    if before_state != after_state:
        changed_labels.add("State")
    if before.get("epoch") != after.get("epoch"):
        changed_labels.add("Epoch")
    if before.get("direction") != after.get("direction"):
        changed_labels.add("Direction")
    if before.get("rk_tail") != after.get("rk_tail"):
        changed_labels.add("RK")
    if before.get("send_ck_tail") != after.get("send_ck_tail"):
        changed_labels.add("CKs")
    if before.get("recv_ck_tail") != after.get("recv_ck_tail"):
        changed_labels.add("CKr")

    state_comparison = ft.Row(
        controls=[
            _party_state_panel(
                "Before",
                before_rows,
                tooltip=tooltips.get("spqr_step_before_panel", ""),
                highlight_labels=changed_labels,
            ),
            _party_state_panel(
                "After",
                after_rows,
                tooltip=tooltips.get("spqr_step_after_panel", ""),
                highlight_labels=changed_labels,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=20,
        wrap=True,
    )

    after_control = ft.Column(
        controls=[
            ft.Text("State before and after", weight="bold"),
            state_comparison,
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "title": "State comparison",
        "control": after_control,
    }


def _normalize_step_titles(steps: list[dict[str, Any]]) -> None:
    for index, step in enumerate(steps):
        numbered_title = f"{index + 1}) {step['title']}"
        step["title"] = numbered_title
        control = step.get("control")
        if isinstance(control, ft.Column) and control.controls and isinstance(control.controls[0], ft.Text):
            control.controls[0].value = numbered_title


def show_spqr_step_visualization_dialog(
    page: ft.Page,
    step_data: dict[str, Any],
    on_close: Callable[[], None] | None = None,
) -> None:
    tooltips = get_tooltip_messages("spqr")
    action = str(step_data.get("action", "send")).strip().lower()
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    state_name = str(before.get("state", before.get("node", "Unknown")))

    steps: list[dict[str, Any]] = [
        _build_intro_step(before, tooltips)
    ]

    chain_steps = (
        _build_send_steps(state_name, step_data, tooltips)
        if action == "send"
        else _build_receive_chain_steps(state_name, step_data, tooltips)
    )
    steps.extend(chain_steps)

    steps.append(_build_output_key_step(action, state_name, before, after, header, tooltips))
    rk_derivation_step = _build_rk_derivation_step(action, state_name, before, after, step_data)
    if rk_derivation_step is not None:
        steps.append(rk_derivation_step)
    if action == "send":
        steps.extend(_build_send_message_pipeline_steps(step_data, tooltips))
    if action == "receive":
        steps.extend(_build_receive_message_pipeline_steps(step_data, tooltips))
    steps.append(_build_after_step(action, str(after.get("state", after.get("node", state_name))), before, after, tooltips))

    _normalize_step_titles(steps)
    dialog_title = f"SPQR {action.capitalize()} visualization:"
    _show_step_dialog(page, dialog_title, steps, on_close=on_close)
