"""Shared logic helpers for the key-exchange protocol family.

The functions in this module capture the protocol-independent parts of the
registration and prekey flow that X3DH and PQXDH both rely on. Concrete
protocol modules build on these helpers to generate keys, track phase
progress, derive associated data, and emit user-facing events.
"""

from __future__ import annotations

from components.data_classes import PQXDHState, X3DHState
from modules import external as ext
from modules.base_logic import BaseLogic

KeyExchangeState = X3DHState | PQXDHState


class KeyExchangeBaseLogic(BaseLogic):
    """Shared logic-layer base for key-exchange protocols (X3DH, PQXDH, ...)."""


def _generate_dh_key_pair() -> dict[str, str]:
    """Return a normalized DH key pair with public and private hex strings."""

    pair = ext.GENERATE_DH()
    return {
        "private": pair.private,
        "public": pair.public,
    }


def add_event(state: KeyExchangeState, message: str) -> None:
    """Append a human-readable event to the protocol event log."""

    state.events.append(message)


def ensure_alice_local(state: KeyExchangeState) -> dict:
    """Return Alice's local state or raise if it has not been initialized."""

    alice = state.alice_local
    if not isinstance(alice, dict):
        raise ValueError("Alice must generate keys first.")
    return alice


def ensure_bob_local(state: KeyExchangeState) -> dict:
    """Return Bob's local state or raise if it has not been initialized."""

    bob = state.bob_local
    if not isinstance(bob, dict):
        raise ValueError("Bob local state is missing.")
    return bob


def is_phase1_done(state: KeyExchangeState) -> bool:
    """Report whether the registration phase has completed."""

    return isinstance(state.server_state.get("alice_bundle"), dict)


def is_phase2_done(state: KeyExchangeState) -> bool:
    """Report whether Alice has derived associated data for phase 2."""

    derived = state.alice_derived
    return isinstance(derived, dict) and isinstance(derived.get("associated_data"), str)


def alice_calculates_associated_data(state: KeyExchangeState) -> None:
    """Compute and store X3DH associated data from Alice and Bob identity keys."""

    alice = ensure_alice_local(state)
    derived = state.alice_derived
    bundle = state.last_bundle_for_alice
    if not isinstance(derived, dict) or not isinstance(bundle, dict):
        raise ValueError("Derive SK first.")

    associated_data = ext.CALC_AD(
        initiator_identity_public=alice["identity_dh"]["public"],
        responder_identity_public=bundle["identity_dh_public"],
    )

    derived["associated_data"] = associated_data
    add_event(state, "Alice calculated Associated Data (AD).")


__all__ = [
    "KeyExchangeBaseLogic",
    "KeyExchangeState",
    "_generate_dh_key_pair",
    "add_event",
    "alice_calculates_associated_data",
    "ensure_alice_local",
    "ensure_bob_local",
    "is_phase1_done",
    "is_phase2_done",
]
FAMILY_ID = "key_exchange"
