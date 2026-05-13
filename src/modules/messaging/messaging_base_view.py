from __future__ import annotations

import flet as ft
from typing import Any, Callable

from components.data_classes import KeyEvent
from modules.base_view import last_n_chars, make_copy_handler
from modules.tooltip_helpers import build_tooltip_text


SIDE_PANEL_WIDTH = 430


def safe_decode_bytes(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.hex()


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


def show_warning_dialog(page: ft.Page, message: str, title: str = "Warning") -> None:
    def close_dialog(e):
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text(message),
        actions=[ft.TextButton("OK", on_click=close_dialog)],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def show_initial_bootstrap_warning(
    page: ft.Page,
    message: str,
    checkbox_label: str,
    dialog_title: str,
    on_bootstrap_viz: Callable[[], None] | None = None,
) -> None:
    show_bootstrap_checkbox = ft.Checkbox(label=checkbox_label, value=True)

    def close_dialog(e):
        dialog.open = False
        page.update()
        if show_bootstrap_checkbox.value and on_bootstrap_viz is not None:
            on_bootstrap_viz()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(dialog_title),
        content=ft.Column(
            controls=[ft.Text(message), show_bootstrap_checkbox],
            tight=True,
            spacing=8,
        ),
        actions=[ft.TextButton("OK", on_click=close_dialog)],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def build_perspective_selector(
    app_state: Any,
    on_change: Callable,
    perspectives: list[tuple[str, str]] | None = None,
) -> ft.RadioGroup:
    if perspectives is None:
        perspectives = [("global", "Global"), ("alice", "Alice"), ("bob", "Bob")]
    return ft.RadioGroup(
        value=app_state.perspective,
        content=ft.Row(
            controls=[ft.Radio(value=v, label=label) for v, label in perspectives],
            spacing=10,
        ),
        on_change=on_change,
    )


def build_timeline_column() -> ft.Column:
    return ft.Column(
        [ft.Row([ft.Text("Message Timeline", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)],
        scroll=ft.ScrollMode.ALWAYS,
        expand=True,
        spacing=6,
    )


def collect_timeline_items(
    message_log: list[Any],
    pending_messages: list[dict] | None,
) -> list[tuple[int, str, Any]]:
    items: list[tuple[int, str, Any]] = [(msg.seq_id, "received", msg) for msg in message_log]
    if pending_messages:
        for p in pending_messages:
            if isinstance(p.get("id"), int):
                items.append((p["id"], "pending", p))
    return items


def pqxdh_header_preview(pqxdh_header: dict | None) -> str:
    if not isinstance(pqxdh_header, dict):
        return ""
    ik_a = str(pqxdh_header.get("ik_a_public", ""))
    ek_a = str(pqxdh_header.get("ek_a_public", ""))
    bob_spk = str(pqxdh_header.get("bob_spk_public", ""))
    pq_id = pqxdh_header.get("bob_pq_prekey_id")
    return f"ik_a={ik_a[-8:]}, ek_a={ek_a[-8:]}, spk_b={bob_spk[-8:]}, pq_id={pq_id}"


def find_bob_pqxdh_header(message_log: list[Any]) -> dict | None:
    for msg in message_log:
        h = getattr(msg, "pqxdh_header", None)
        if isinstance(h, dict) and str(getattr(msg, "receiver", "")).lower() == "bob":
            return h
    return None


def build_timeline_entry(
    row_controls: list[ft.Control],
    header_text: str,
    body: str,
    pqxdh_text: str = "",
    border: ft.Border | None = None,
    text_size: int = 11,
) -> ft.Container:
    content: list[ft.Control] = [
        ft.Row(row_controls),
        ft.Text(f"header: {header_text}", size=text_size),
    ]
    if pqxdh_text:
        content.append(ft.Text(f"pqxdh: {pqxdh_text}", size=text_size))
    content.append(ft.Text(f"message: {body}"))
    return ft.Container(
        content=ft.Column(content, spacing=2, tight=True),
        padding=6,
        border=border,
        border_radius=5,
    )


def build_received_row_controls(
    seq_id: int,
    sender: str,
    receiver: str,
    on_show_send_visualization: Callable | None,
    on_show_receive_visualization: Callable | None,
) -> list[ft.Control]:
    controls: list[ft.Control] = [ft.Text(f"[{seq_id}] {sender} → {receiver} | ")]
    if on_show_send_visualization is not None:
        controls.append(ft.TextButton("Send steps", on_click=lambda _, sid=seq_id: on_show_send_visualization(sid)))
    if on_show_receive_visualization is not None:
        controls.append(ft.TextButton("Receive steps", on_click=lambda _, sid=seq_id: on_show_receive_visualization(sid)))
    return controls


def build_pending_row_controls(
    seq_id: int,
    sender: str,
    receiver: str,
    perspective_key: str,
    on_receive_pending: Callable | None,
    on_show_send_visualization: Callable | None,
) -> list[ft.Control]:
    can_receive = perspective_key in {"global", receiver.lower()}
    controls: list[ft.Control] = [ft.Text(f"[{seq_id}] {sender} → {receiver} | ")]
    if can_receive and on_receive_pending is not None:
        controls.append(ft.TextButton("Receive", on_click=lambda _, pid=seq_id, who=receiver: on_receive_pending(who, pid)))
    else:
        controls.append(ft.Text("Pending"))
    if on_show_send_visualization is not None:
        controls.append(ft.TextButton("Send steps", on_click=lambda _, sid=seq_id: on_show_send_visualization(sid)))
    return controls


def resolve_received_body(
    perspective_key: str,
    sender: str,
    plaintext: bytes,
    decrypted_by_receiver: bytes,
    cipher: bytes,
) -> str:
    sender_view = perspective_key in {"global", sender.lower()}
    return safe_decode_bytes(plaintext if sender_view else decrypted_by_receiver) or safe_decode_bytes(cipher)


def resolve_pending_body(
    perspective_key: str,
    sender: str,
    plaintext: bytes,
    cipher: bytes,
) -> str:
    return safe_decode_bytes(plaintext if perspective_key in {"global", sender.lower()} else cipher)


def append_pqxdh_bootstrap_buttons(
    col: ft.Column,
    session_alice: Any,
    bob_initialized: bool,
    bob_pqxdh_header: dict | None,
    perspective_key: str,
    on_show_alice_bootstrap: Callable | None,
    on_show_bob_bootstrap: Callable | None,
    alice_label: str = "Show Alice PQXDH initialization",
    bob_label: str = "Show Bob PQXDH initialization",
) -> None:
    buttons: list[ft.Control] = []
    if on_show_alice_bootstrap and session_alice is not None and perspective_key in {"global", "alice"}:
        buttons.append(ft.TextButton(alice_label, on_click=lambda _: on_show_alice_bootstrap()))
    if on_show_bob_bootstrap and bob_initialized and bob_pqxdh_header is not None and perspective_key in {"global", "bob"}:
        buttons.append(ft.TextButton(bob_label, on_click=lambda _, h=bob_pqxdh_header: on_show_bob_bootstrap(h)))
    if buttons:
        col.controls.append(ft.Divider(height=8))
        col.controls.extend(buttons)


def build_module_layout(
    title_text: str,
    send_step_visualization_checkbox: ft.Control,
    receive_step_visualization_checkbox: ft.Control,
    auto_receive_checkbox: ft.Control,
    message_count: ft.Control,
    perspective_selector: ft.Control,
    on_reset_module: Callable,
    visual_container: ft.Control,
) -> ft.Column:
    return ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.Text(title_text, size=22, weight="bold"),
                    ft.Row(
                        controls=[
                            send_step_visualization_checkbox,
                            receive_step_visualization_checkbox,
                            auto_receive_checkbox,
                        ],
                        spacing=16,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                controls=[
                    message_count,
                    perspective_selector,
                    ft.TextButton("Reset application", on_click=on_reset_module),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            visual_container,
        ],
        expand=True,
    )
