from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import DRHeader, SpqrHeader
from modules.base_view import format_key, last_n_chars


def format_tooltip_value(value: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    if value is None:
        return f"{prefix}None"

    if isinstance(value, DRHeader):
        value = {"dh": value.dh, "pn": value.pn, "n": value.n}
    elif isinstance(value, SpqrHeader):
        msg_val = value.msg.to_dict() if hasattr(value.msg, "to_dict") else str(value.msg)
        value = {"msg": msg_val, "n": value.n}

    if isinstance(value, dict):
        if not value:
            return f"{prefix}(empty)"
        lines: list[str] = []
        for key, nested in value.items():
            if isinstance(nested, (dict, list, tuple, set)):
                lines.append(f"{prefix}{key}:")
                lines.append(format_tooltip_value(nested, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {format_key(nested)}")
        return "\n".join(lines)

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if isinstance(value, set):
            items = sorted(items, key=lambda item: format_key(item))
        if not items:
            return f"{prefix}(empty)"
        lines = []
        for item in items:
            if isinstance(item, (dict, list, tuple, set)):
                lines.append(f"{prefix}-")
                lines.append(format_tooltip_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- {format_key(item)}")
        return "\n".join(lines)

    return f"{prefix}{format_key(value)}"


def to_text(value: Any) -> str:
    return format_tooltip_value(value)


def tooltip_with_full_value(message: str | None, full_value: Any = None) -> str | None:
    parts: list[str] = []
    if message:
        parts.append(message)
    if full_value is not None:
        if parts:
            parts.append("\n────────────\n")
        parts.append(f"Full value:\n{to_text(full_value)}")
    if not parts:
        return None
    return "".join(parts)


def safe_dimension(value: Any, fallback: int) -> int:
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return fallback


def page_size(page: ft.Page) -> tuple[int, int]:
    width = getattr(page, "width", None)
    height = getattr(page, "height", None)
    window = getattr(page, "window", None)

    if width is None and window is not None:
        width = getattr(window, "width", None)
    if height is None and window is not None:
        height = getattr(window, "height", None)

    return safe_dimension(width, 1100), safe_dimension(height, 760)


def with_tooltip(control: ft.Control, message: str | None, full_value: Any = None) -> ft.Control:
    tooltip_message = tooltip_with_full_value(message, full_value)
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
    width: int = 260,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    controls = [ft.Text(label, weight="bold", text_align=ft.TextAlign.CENTER, color=text_color)]
    if value is not None:
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
    return with_tooltip(node, tooltip, full_value)


def var_node(
    label: str,
    value: str | None = None,
    width: int = 220,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    derived_value = value
    if derived_value is None and full_value is not None:
        derived_value = last_n_chars(format_tooltip_value(full_value), 8)
        if derived_value == "":
            derived_value = "(empty)"

    return flow_node(
        label=label,
        value=derived_value,
        circle=False,
        width=width,
        height=height,
        tooltip=tooltip,
        full_value=full_value,
        bgcolor=bgcolor,
        text_color=text_color,
        border_color=border_color,
    )


def func_node(
    label: str,
    value: str | None = None,
    tooltip: str | None = None,
    full_value: Any = None,
    width: int = 220,
    height: int = 70,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    return flow_node(
        label=label,
        value=value,
        circle=True,
        width=width,
        height=height,
        tooltip=tooltip,
        full_value=full_value,
        bgcolor=bgcolor,
        text_color=text_color,
        border_color=border_color,
    )


def state_row(
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
    return with_tooltip(outer_container, tooltip, full_value)


def party_state_panel(
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
                    state_row(
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
    return with_tooltip(panel, tooltip)


def normalize_step_titles(steps: list[dict[str, Any]]) -> None:
    for index, step in enumerate(steps):
        numbered_title = f"{index + 1}) {step['title']}"
        step["title"] = numbered_title
        control = step.get("control")
        if isinstance(control, ft.Column) and control.controls and isinstance(control.controls[0], ft.Text):
            control.controls[0].value = numbered_title


def show_step_dialog(
    page: ft.Page,
    dialog_title: str,
    steps: list[dict[str, Any]],
    on_close: Callable[[], None] | None = None,
    show_step_title: bool = True,
) -> None:
    resize_event_name = "on_resized" if hasattr(page, "on_resized") else "on_resize"
    previous_resize_handler = getattr(page, resize_event_name, None)

    current_step = {"index": 0}
    progress_text = ft.Text()
    step_container = ft.Container(width=620)

    def apply_responsive_dialog_size() -> None:
        page_width, page_height = page_size(page)
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
        if show_step_title:
            progress_text.value = f"Step {index + 1}/{len(steps)} - {step['title']}"
        else:
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
            alignment=ft.MainAxisAlignment.START,
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
