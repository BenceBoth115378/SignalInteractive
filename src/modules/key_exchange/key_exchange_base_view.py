from __future__ import annotations


def phase_ready(current_phase_done: bool) -> bool:
    return bool(current_phase_done)


__all__ = ["phase_ready"]
FAMILY_ID = "key_exchange"
