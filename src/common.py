from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

DEFAULT_MODULE = "double_ratchet"
PERSPECTIVE_OPTIONS = ("global", "alice", "bob", "attacker")
PERSPECTIVE_SET = set(PERSPECTIVE_OPTIONS)
PERSPECTIVE_LABELS = {
    "global": "Global",
    "alice": "Alice",
    "bob": "Bob",
    "attacker": "Attacker",
}


def asset_path(*parts: str) -> Path:
    return ASSETS_DIR.joinpath(*parts)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON from {path}: {e}")
        return default


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


@lru_cache(maxsize=8)
def load_asset_json_cached(filename: str) -> dict:
    path = asset_path(filename)
    data = load_json(path, default={})
    return data if isinstance(data, dict) else {}
