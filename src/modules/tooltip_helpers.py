import flet as ft
from common import load_asset_json_cached


def get_tooltip_messages(module_name: str) -> dict:
    tooltip_map = load_asset_json_cached("tooltips.json")
    return tooltip_map.get(module_name, {})


def build_tooltip_text(label: str, value: str, tooltip_message: str):
    return ft.Container(
        content=ft.Text(f"{label}: {value}"),
        tooltip=ft.Tooltip(message=tooltip_message, prefer_below=False),
    )
