from common import asset_path, load_json, save_json

STATE_FILE = asset_path("app_state.json")


def has_saved_state() -> bool:
    return STATE_FILE.exists()


def save_state(payload: dict) -> None:
    save_json(STATE_FILE, payload)


def load_state() -> dict | None:
    data = load_json(STATE_FILE, default=None)
    return data if isinstance(data, dict) else None


def clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
