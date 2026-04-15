from __future__ import annotations


class BaseModule:
    """Coordinator layer that binds protocol logic and protocol view."""

    def build(self, page, app_state, perspective_selector=None):
        raise NotImplementedError

    def export_state(self) -> dict:
        return {}

    def import_state(self, data: dict) -> None:
        _ = data


__all__ = ["BaseModule"]
