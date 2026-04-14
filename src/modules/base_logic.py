from __future__ import annotations


class BaseLogic:
    """Logic-layer base class used by all protocol families."""

    def reset(self) -> None:
        return None


__all__ = ["BaseLogic"]
