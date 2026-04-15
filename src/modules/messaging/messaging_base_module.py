from __future__ import annotations

from modules.base_module import BaseModule


class MessagingBaseModule(BaseModule):
    """Shared module-layer base for messaging protocol controllers."""


__all__ = ["MessagingBaseModule"]
FAMILY_ID = "messaging"
