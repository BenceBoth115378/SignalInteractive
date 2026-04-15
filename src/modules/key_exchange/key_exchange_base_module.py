from __future__ import annotations

from modules.base_module import BaseModule


class KeyExchangeBaseModule(BaseModule):
    """Shared module-layer base for key-exchange protocol controllers."""


__all__ = ["KeyExchangeBaseModule"]
FAMILY_ID = "key_exchange"
