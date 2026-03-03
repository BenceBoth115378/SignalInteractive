from typing import Any, Callable

import flet as ft
from common import load_asset_json_cached


def get_tooltip_messages(module_name: str) -> dict:
    tooltip_map = load_asset_json_cached("tooltips.json")
    return tooltip_map.get(module_name, {})


def build_tooltip_text(
    label: str,
    value: str,
    tooltip_message: str,
    full_value: str | None = None,
    on_click: Callable[[Any], None] | None = None,
):
    message_parts = []
    if tooltip_message:
        message_parts.append(tooltip_message)

    if full_value is not None:
        if message_parts:
            message_parts.append("\n────────────\n")
        message_parts.append(f"Key value: {full_value}")

    message = "".join(message_parts)

    return ft.Container(
        content=ft.Text(f"{label}: {value}"),
        tooltip=ft.Tooltip(message=message, prefer_below=False),
        on_click=on_click,
        ink=on_click is not None,
    )
