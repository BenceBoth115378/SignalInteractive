import json
from pathlib import Path


STATE_FILE = Path(__file__).resolve().parent / "assets" / "app_state.json"


def has_saved_state() -> bool:
    return STATE_FILE.exists()


def save_state(payload: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return None


def clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
