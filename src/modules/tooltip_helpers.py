import flet as ft
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _load_tooltip_map() -> dict:
    tooltip_file = (
        Path(__file__).resolve().parent.parent / "assets" / "tooltips.json"
    )
    with tooltip_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_tooltip_messages(module_name: str) -> dict:
    tooltip_map = _load_tooltip_map()
    return tooltip_map.get(module_name, {})


def build_tooltip_text(label: str, value: str, tooltip_message: str):
    return ft.Container(
        content=ft.Text(f"{label}: {value}"),
        tooltip=ft.Tooltip(
            message=tooltip_message,
            prefer_below=False,
        ),
    )
