from __future__ import annotations

from modules.base_logic import BaseLogic


class MessagingBaseLogic(BaseLogic):
    """Shared logic-layer base for messaging protocols (DR, SPQR, ...)."""


__all__ = ["MessagingBaseLogic"]
FAMILY_ID = "messaging"
