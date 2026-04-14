from __future__ import annotations

from modules.base_logic import BaseLogic


class KeyExchangeBaseLogic(BaseLogic):
    """Shared logic-layer base for key-exchange protocols (X3DH, PQXDH, ...)."""


__all__ = ["KeyExchangeBaseLogic"]
FAMILY_ID = "key_exchange"
