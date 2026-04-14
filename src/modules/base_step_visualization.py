from __future__ import annotations

from typing import Any

import flet as ft

from modules.base_view import format_key


def format_tooltip_value(value: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    if value is None:
        return f"{prefix}None"

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
