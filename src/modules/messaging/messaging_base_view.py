from __future__ import annotations

import flet as ft
from typing import Any, Callable

from components.data_classes import KeyEvent
from modules.base_view import last_n_chars, make_copy_handler
from modules.tooltip_helpers import build_tooltip_text


def is_party_visible(perspective: str, party_name: str) -> bool:
    return perspective == "global" or perspective.lower() == party_name.lower()


def build_key_field(
    page: ft.Page,
    visible: bool,
    label: str,
    full_value: str,
    tooltip_message: str = "",
    copy_value: str | None = None,
) -> ft.Control:
    """Build a formatted key field with tooltip, matching double_ratchet style."""
    display = last_n_chars(full_value, 8) if visible else "Hidden"
    cv = copy_value if copy_value is not None else full_value
    return build_tooltip_text(
        label,
        display,
        tooltip_message,
        full_value=full_value if visible else None,
        on_click=make_copy_handler(page, label, cv) if visible else None,
    )

def keys_differ(key1: Any, key2: Any) -> bool:
    """Return True when key values changed."""
    if key1 is None and key2 is None:
        return False
    if key1 is None or key2 is None:
        return True
    return key1 != key2


def get_key_display_label(key_type: str, key_number: int) -> str:
    """Format key label (e.g., 'RK#0')."""
    return f"{key_type}#{key_number}"


def tail_hex(value: bytes | None, size: int = 12) -> str:
    """Return the trailing hex text for a byte value."""
    if value is None:
        return "None"
    text = value.hex()
    if len(text) <= size:
        return text
    return text[-size:]


def get_key_tooltip_text(event: KeyEvent) -> str:
    """Build tooltip text for key history entries."""
    lines = []

    lines.append(f"Type: {event.key_type} (#{event.key_number})")
    lines.append(f"Generated: {event.created_at_step}")
    lines.append(f"Context: {event.created_in_context}")

    key_hex = (
        event.key_value.hex()
        if isinstance(event.key_value, bytes)
        else str(event.key_value)
    )
    lines.append(f"Value (last 16 chars): ...{key_hex[-16:]}")

    if event.used_for:
        lines.append(f"Used in: {', '.join(event.used_for[:3])}")
        if len(event.used_for) > 3:
            lines.append(f"  ... and {len(event.used_for) - 3} more")
    else:
        lines.append("Not yet used")

    return "\n".join(lines)

VarNodeFactory = Callable[[str, Any, str], ft.Control]
FlowNodeFactory = Callable[..., ft.Control]
FunctionNodeFactory = Callable[[str, str, Any | None, Any | None], ft.Control]
TooltipResolver = Callable[[str], str]


def build_message_step(
    build_title: str,
    chunk: Any,
    msg_epoch: Any,
    msg_type_label: str,
    msg_type_full: str,
    var_node: VarNodeFactory,
    flow_node: FlowNodeFactory,
    tt: TooltipResolver,
) -> list[dict[str, Any]]:
    return [
        {
            "title": build_title,
            "control": ft.Column(
                controls=[
                    ft.Text(build_title, weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("chunk", chunk, "spqr_step_chunk_in_msg"),
                            var_node("epoch", msg_epoch, "spqr_step_epoch_in_msg"),
                            flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=tt("spqr_step_msg_type_in_msg"),
                                full_value=msg_type_full,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    flow_node(
                        "Build SpqrMessage",
                        circle=True,
                        width=220,
                        height=70,
                        tooltip=tt("spqr_step_build_message"),
                        full_value={
                            "epoch": msg_epoch,
                            "msg_type": msg_type_label,
                            "data": chunk,
                        },
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("epoch", msg_epoch, "spqr_step_msg_epoch"),
                            flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=tt("spqr_step_msg_type"),
                                full_value=msg_type_full,
                            ),
                            var_node("msg.data", chunk, "spqr_step_msg_data"),
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


def build_send_result_step(
    sending_epoch: Any,
    output_key_label: str,
    output_key: Any,
    next_state: str,
    var_node: VarNodeFactory,
    flow_node: FlowNodeFactory,
    tt: TooltipResolver,
) -> dict[str, Any]:
    return {
        "title": "Send result",
        "control": ft.Column(
            controls=[
                ft.Text("Send result", weight="bold"),
                ft.Row(
                    controls=[
                        var_node("sending_epoch", sending_epoch, "spqr_step_sending_epoch"),
                        flow_node(
                            "output_key",
                            output_key_label,
                            width=220,
                            tooltip=tt("spqr_step_output_key"),
                            full_value=output_key,
                        ),
                        flow_node(
                            "next_state",
                            next_state,
                            width=220,
                            tooltip=tt("spqr_step_next_state"),
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


def build_chunk_send_steps(
    chunk: Any,
    msg_epoch: Any,
    sending_epoch: Any,
    generate_title: str,
    build_title: str,
    chunk_expr: str,
    msg_type_label: str,
    msg_type_full: str,
    next_state: str,
    var_node: VarNodeFactory,
    flow_node: FlowNodeFactory,
    function_node: FunctionNodeFactory,
    tt: TooltipResolver,
) -> list[dict[str, Any]]:
    return [
        {
            "title": generate_title,
            "control": ft.Column(
                controls=[
                    ft.Text(generate_title, weight="bold"),
                    function_node(
                        "Encoder.next_chunk",
                        "spqr_step_next_chunk",
                        chunk_expr,
                        None,
                    ),
                    ft.Text("↓", size=24),
                    var_node("chunk", chunk, "spqr_step_chunk"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        *build_message_step(
            build_title=build_title,
            chunk=chunk,
            msg_epoch=msg_epoch,
            msg_type_label=msg_type_label,
            msg_type_full=msg_type_full,
            var_node=var_node,
            flow_node=flow_node,
            tt=tt,
        ),
        build_send_result_step(
            sending_epoch=sending_epoch,
            output_key_label="None",
            output_key=None,
            next_state=next_state,
            var_node=var_node,
            flow_node=flow_node,
            tt=tt,
        ),
    ]


def build_none_send_steps(
    msg_epoch: Any,
    sending_epoch: Any,
    msg_type_label: str,
    msg_type_full: str,
    next_state: str,
    var_node: VarNodeFactory,
    flow_node: FlowNodeFactory,
    tt: TooltipResolver,
) -> list[dict[str, Any]]:
    return [
        {
            "title": "Build message with no data to send",
            "control": ft.Column(
                controls=[
                    ft.Text("Build message with no data to send", weight="bold"),
                    ft.Row(
                        controls=[
                            flow_node("data", "None", width=220, tooltip=tt("spqr_step_chunk_in_msg"), full_value=None),
                            var_node("epoch", msg_epoch, "spqr_step_epoch_in_msg"),
                            flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=tt("spqr_step_msg_type_in_msg"),
                                full_value=msg_type_full,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    flow_node(
                        "Build SpqrMessage",
                        circle=True,
                        width=220,
                        height=70,
                        tooltip=tt("spqr_step_build_message"),
                        full_value={
                            "epoch": msg_epoch,
                            "msg_type": msg_type_label,
                            "data": None,
                        },
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("epoch", msg_epoch, "spqr_step_msg_epoch"),
                            flow_node(
                                "msg.type",
                                msg_type_label,
                                width=220,
                                tooltip=tt("spqr_step_msg_type"),
                                full_value=msg_type_full,
                            ),
                            flow_node("msg.data", "None", width=220, tooltip=tt("spqr_step_msg_data"), full_value=None),
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
        build_send_result_step(
            sending_epoch=sending_epoch,
            output_key_label="None",
            output_key=None,
            next_state=next_state,
            var_node=var_node,
            flow_node=flow_node,
            tt=tt,
        ),
    ]


def build_party_panel_from_rows(
    page: ft.Page,
    party_name: str,
    rows: list[tuple[str, str, str | None]],
    message_input: ft.TextField | None = None,
    on_send=None,
    width: int = 430,
) -> ft.Control:
    """Build a generic party state panel from rows.
    
    Args:
        page: Flet page object
        party_name: Name of the party
        rows: List of (label, value, tooltip) tuples
        message_input: Optional message input field
        on_send: Optional send button callback
        width: Panel width
    """
    controls: list[ft.Control] = [
        ft.Text(party_name, size=18, weight="bold", text_align=ft.TextAlign.LEFT),
    ]
    
    for label, value, tooltip_text in rows:
        controls.append(
            build_tooltip_text(label, value, tooltip_text or "")
        )
    
    if message_input is not None and on_send is not None:
        controls.extend([
            ft.Divider(height=12),
            message_input,
            ft.Button("Send", on_click=on_send),
        ])
    
    return ft.Container(
        content=ft.Column(
            controls,
            spacing=2,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        width=width,
    )


def build_key_history_panel(
    page: ft.Page,
    visible: bool,
    key_history_sections: list[tuple[str, list[Any]]],
    width: int = 430,
) -> ft.Control:
    """Build a generic key history panel.
    
    Args:
        page: Flet page object
        visible: Whether to show full key values
        key_history_sections: List of (section_label, events) tuples
        width: Panel width
    """
    panel_controls: list[ft.Control] = [
        build_tooltip_text("Used keys history", "", "Key history for this party"),
    ]
    
    if not visible:
        panel_controls.append(ft.Text("Hidden", color=ft.Colors.OUTLINE))
    else:
        for section_label, events in key_history_sections:
            panel_controls.append(ft.Text(section_label, weight="bold", size=12))
            ordered_events = list(reversed(events))
            if not ordered_events:
                panel_controls.append(ft.Text("-", color=ft.Colors.OUTLINE))
                continue
            
            for event in ordered_events:
                key_text = event.key_value.hex() if isinstance(event.key_value, bytes) else str(event.key_value)
                label = f"{event.key_type}#{event.key_number} ({event.created_at_step})"
                panel_controls.append(
                    build_key_field(
                        page,
                        visible,
                        label,
                        key_text,
                        get_key_tooltip_text(event),
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
        width=width,
        expand=True,
        padding=8,
        border_radius=8,
    )
