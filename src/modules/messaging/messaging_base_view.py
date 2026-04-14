from __future__ import annotations


def is_party_visible(perspective: str, party_name: str) -> bool:
    return perspective == "global" or perspective.lower() == party_name.lower()


__all__ = ["is_party_visible"]
FAMILY_ID = "messaging"
