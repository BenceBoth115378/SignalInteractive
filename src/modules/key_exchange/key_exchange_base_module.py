"""Shared module-layer controller helpers for key-exchange protocols.

The base class in this file standardizes state creation, state import/export,
and the bootstrap data needed by downstream messaging modules. X3DH and PQXDH
extend it so the UI can treat both protocols through the same persistence and
action-dispatch surface.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from modules.base_module import BaseModule


def serialize_state(state) -> dict:
    """Serialize a dataclass-backed module state to a plain dictionary."""

    return asdict(state)


class KeyExchangeBaseModule(BaseModule):
    """Shared module-layer base for key-exchange protocol controllers."""

    _PROTOCOL_SOURCE_ID: str = ""

    def __init__(self):
        """Create the initial module state for the protocol controller."""

        self.state = self._new_state()

    def _new_state(self):
        """Create a fresh protocol state instance."""

        raise NotImplementedError

    def _state_data(self) -> dict:
        """Return the current state as a serializable dictionary."""

        return serialize_state(self.state)

    def _reset_application(self) -> None:
        """Reset the protocol controller back to a fresh state."""

        self.state = self._new_state()

    def export_state(self) -> dict:
        """Export the current protocol state for persistence."""

        return self._state_data()

    def import_state(self, data: dict) -> None:
        """Restore protocol state from persisted data or reset if empty."""

        if isinstance(data, dict) and data:
            if not data.get("events"):
                data["events"] = []
            self.state = self._deserialize_state(data)
        else:
            self.state = self._new_state()

    def _deserialize_state(self, data: dict):
        """Convert persisted data into the concrete protocol state type."""

        raise NotImplementedError

    def _build_dr_bootstrap_payload(self) -> dict | None:
        """Build the double-ratchet bootstrap payload when phase 2 is ready."""

        derived = self.state.alice_derived if isinstance(self.state.alice_derived, dict) else None
        bob_local = self.state.bob_local if isinstance(self.state.bob_local, dict) else None
        bob_spk = (bob_local or {}).get("signed_prekey") if isinstance((bob_local or {}).get("signed_prekey"), dict) else None

        if not isinstance(derived, dict) or not isinstance(bob_spk, dict):
            return None

        sk_hex = derived.get("shared_secret")
        ad_hex = derived.get("associated_data")
        bob_spk_public = bob_spk.get("public")
        bob_spk_private = bob_spk.get("private")

        if not all(isinstance(value, str) and value for value in [sk_hex, ad_hex, bob_spk_public, bob_spk_private]):
            return None

        initial_message = self.state.initial_message if isinstance(self.state.initial_message, dict) else None
        initial_message_json = json.dumps(initial_message, sort_keys=True) if isinstance(initial_message, dict) else ""

        return {
            "source": self._PROTOCOL_SOURCE_ID,
            "sk_hex": sk_hex,
            "ad_hex": ad_hex,
            "bob_spk_public": bob_spk_public,
            "bob_spk_private": bob_spk_private,
            "initial_message_json": initial_message_json,
        }


__all__ = ["KeyExchangeBaseModule", "serialize_state"]
FAMILY_ID = "key_exchange"
