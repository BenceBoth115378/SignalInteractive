"""Key history tracking utilities for the Double Ratchet module."""

from typing import Any

from components.data_classes import (
    DoubleRatchetState,
    KeyEvent,
    PartyState,
    ReceiveStepVisualizationSnapshot,
    SendStepVisualizationSnapshot,
)


def _keys_differ(key1: Any, key2: Any) -> bool:
    """Return True when key values changed."""
    if key1 is None and key2 is None:
        return False
    if key1 is None or key2 is None:
        return True
    return key1 != key2


def _snapshot_to_string(step_number: int, step_type: str) -> str:
    return f"{step_type}#{step_number}"


def initialize_key_history(session: DoubleRatchetState) -> None:
    """Seed initial key history entries after session initialization."""
    for party in (session.initializer, session.responder):
        history = party.key_history
        if party.RK and not history.rk_events:
            history.add_rk_event(
                KeyEvent(
                    key_type="RK",
                    key_number=0,
                    key_value=party.RK,
                    created_at_step="init",
                    created_in_context="Initial root key",
                    party=party.name,
                    remote_public=party.DHr,
                    start_send_n=party.Ns,
                    start_recv_n=party.Nr,
                    used_for=["session bootstrap"],
                )
            )
        if party.CKs and not history.cks_events:
            history.add_cks_event(
                KeyEvent(
                    key_type="CK",
                    key_number=0,
                    key_value=party.CKs,
                    created_at_step="init",
                    created_in_context="Initial sending chain key",
                    party=party.name,
                    direction="send",
                    public_value=party.DHs.public if party.DHs is not None else "",
                    start_n=party.Ns,
                    used_for=["outgoing chain"],
                )
            )
        if party.DHs is not None and party.DHs.public and not history.dh_events:
            history.add_dh_event(
                KeyEvent(
                    key_type="DH",
                    key_number=0,
                    key_value=party.DHs.private,
                    public_value=party.DHs.public,
                    created_at_step="init",
                    created_in_context="Initial local DH key pair",
                    party=party.name,
                    remote_public=party.DHr,
                    start_send_n=party.Ns,
                    start_recv_n=party.Nr,
                    used_for=["header.dh for outgoing messages"],
                )
            )


def track_keys_from_send_snapshot(
    party: PartyState,
    step_number: int,
    snapshot: SendStepVisualizationSnapshot,
    pending_id: int,
) -> None:
    """Track newly derived keys after a send step."""
    before = snapshot.before
    after = snapshot.after

    if _keys_differ(before.RK, after.RK) and after.RK is not None:
        party.key_history.add_rk_event(
            KeyEvent(
                key_type="RK",
                key_number=0,
                key_value=after.RK,
                created_at_step=_snapshot_to_string(step_number, "send"),
                created_in_context="Root key derivation during send",
                party=party.name,
                remote_public=after.DHr,
                start_send_n=after.Ns,
                start_recv_n=after.Nr,
                used_for=[f"after message #{pending_id}"],
            )
        )

    if _keys_differ(before.CKs, after.CKs) and after.CKs is not None:
        party.key_history.add_cks_event(
            KeyEvent(
                key_type="CK",
                key_number=0,
                key_value=after.CKs,
                created_at_step=_snapshot_to_string(step_number, "send"),
                created_in_context="KDF_CK on sending chain",
                party=party.name,
                direction="send",
                public_value=after.DHs_public,
                start_n=after.Ns,
                used_for=[f"future sends after message #{pending_id}"],
            )
        )

    if before.DHs_public != after.DHs_public and after.DHs_public:
        party.key_history.add_dh_event(
            KeyEvent(
                key_type="DH",
                key_number=0,
                key_value=party.DHs.private if party.DHs is not None else "",
                public_value=after.DHs_public,
                created_at_step=_snapshot_to_string(step_number, "send"),
                created_in_context="DH ratchet generated a new local key pair",
                party=party.name,
                remote_public=after.DHr,
                start_send_n=after.Ns,
                start_recv_n=after.Nr,
                used_for=["header.dh for subsequent outgoing messages"],
            )
        )


def track_keys_from_receive_snapshot(
    party: PartyState,
    step_number: int,
    snapshot: ReceiveStepVisualizationSnapshot,
    pending_id: int,
) -> None:
    """Track newly derived keys after a receive step."""
    before = snapshot.before
    after = snapshot.after

    if _keys_differ(before.RK, after.RK) and after.RK is not None:
        context = "Root key derivation during receive"
        if snapshot.dh_ratchet_needed:
            context += " (DH ratchet triggered)"
        party.key_history.add_rk_event(
            KeyEvent(
                key_type="RK",
                key_number=0,
                key_value=after.RK,
                created_at_step=_snapshot_to_string(step_number, "receive"),
                created_in_context=context,
                party=party.name,
                remote_public=after.DHr,
                start_send_n=after.Ns,
                start_recv_n=after.Nr,
                used_for=[f"after receiving message #{pending_id}"],
            )
        )

    if _keys_differ(before.CKr, after.CKr) and after.CKr is not None:
        context = "Receive chain key"
        if snapshot.dh_ratchet_needed:
            context += " (new from DH ratchet)"
        else:
            context += " (ratchet via KDF_CK)"
        if snapshot.fast_forward_count > 0:
            context += f", fast-forwarded {snapshot.fast_forward_count} steps"
        party.key_history.add_ckr_event(
            KeyEvent(
                key_type="CK",
                key_number=0,
                key_value=after.CKr,
                created_at_step=_snapshot_to_string(step_number, "receive"),
                created_in_context=context,
                party=party.name,
                direction="recv",
                remote_public=after.DHr,
                start_n=after.Nr,
                used_for=[f"future receives after message #{pending_id}"],
            )
        )

    if before.DHs_public != after.DHs_public and after.DHs_public:
        party.key_history.add_dh_event(
            KeyEvent(
                key_type="DH",
                key_number=0,
                key_value=party.DHs.private if party.DHs is not None else "",
                public_value=after.DHs_public,
                created_at_step=_snapshot_to_string(step_number, "receive"),
                created_in_context="DH ratchet generated a new local key pair during receive",
                party=party.name,
                remote_public=after.DHr,
                start_send_n=after.Ns,
                start_recv_n=after.Nr,
                used_for=[f"after receiving message #{pending_id}"],
            )
        )


def get_key_display_label(key_type: str, key_number: int) -> str:
    return f"{key_type}#{key_number}"


def get_key_tooltip_text(event: KeyEvent) -> str:
    """Build tooltip text for key history entries."""
    lines = []

    lines.append(f"Type: {event.key_type} (#{event.key_number})")
    lines.append(f"Generated: {event.created_at_step}")
    lines.append(f"Context: {event.created_in_context}")

    key_hex = (
        event.key_value.hex()
        if isinstance(event.key_value, bytes)
        else str(event.key_value)
    )
    lines.append(f"Value (last 16 chars): ...{key_hex[-16:]}")

    if event.used_for:
        lines.append(f"Used in: {', '.join(event.used_for[:3])}")
        if len(event.used_for) > 3:
            lines.append(f"  ... and {len(event.used_for) - 3} more")
    else:
        lines.append("Not yet used")

    return "\n".join(lines)
