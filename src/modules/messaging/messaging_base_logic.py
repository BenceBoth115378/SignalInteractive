"""Shared logic base for the messaging protocol family.

The messaging modules use this class as a common logic-layer anchor so DR,
SPQR, and Triple Ratchet can share the same module family identity without
duplicating protocol-agnostic behavior.
"""

from __future__ import annotations

from modules.base_logic import BaseLogic


class MessagingBaseLogic(BaseLogic):
    """Shared logic-layer base for messaging protocols (DR, SPQR, ...)."""


__all__ = ["MessagingBaseLogic"]
FAMILY_ID = "messaging"
