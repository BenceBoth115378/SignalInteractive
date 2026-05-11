"""Key history tracking for the Triple Ratchet module (DR + SPQR combined)."""

from components.data_classes import (
    KeyEvent,
    TripleRatchetPartyState,
    TripleRatchetSessionState,
)


def initialize_key_history(session: TripleRatchetSessionState) -> None:
    """Seed initial key history entries after Triple Ratchet session initialization."""
    for party in (session.alice, session.bob):
        if party is None:
            continue

        dr = party.dr
        spqr = party.spqr

        # DR root key
        if dr.RK and not dr.key_history.rk_events:
            dr.key_history.add_rk_event(
                KeyEvent(
                    key_type="RK",
                    key_number=0,
                    key_value=dr.RK,
                    created_at_step="init",
                    created_in_context="DR initial root key (from PQXDH SK split)",
                    party=party.name,
                    start_send_n=0,
                    start_recv_n=0,
                    used_for=["session bootstrap (DR)"],
                )
            )

        # DR initial chain keys
        if dr.CKs and not dr.key_history.cks_events:
            dr.key_history.add_cks_event(
                KeyEvent(
                    key_type="CK",
                    key_number=0,
                    key_value=dr.CKs,
                    created_at_step="init",
                    created_in_context="DR initial sending chain key",
                    party=party.name,
                    direction="send",
                    start_n=0,
                    used_for=["outgoing DR chain"],
                )
            )

        if spqr is None:
            continue

        # SPQR root key (tracked on the SPQR ratchet state's key_history)
        if spqr.RK and not spqr.key_history.rk_events:
            spqr.key_history.add_rk_event(
                KeyEvent(
                    key_type="RK",
                    key_number=0,
                    key_value=spqr.RK,
                    created_at_step="init",
                    created_in_context="SPQR initial root key (from PQXDH SK split)",
                    party=party.name,
                    start_send_n=0,
                    start_recv_n=0,
                    used_for=["session bootstrap (SPQR)"],
                )
            )

        chains_0 = spqr.kdfchains.get(0)
        if chains_0 is not None:
            if chains_0.send is not None and not spqr.key_history.cks_events:
                spqr.key_history.add_cks_event(
                    KeyEvent(
                        key_type="CK",
                        key_number=0,
                        key_value=chains_0.send.CK,
                        created_at_step="init",
                        created_in_context="SPQR initial sending chain key (epoch 0)",
                        party=party.name,
                        direction="send",
                        start_n=0,
                        used_for=["outgoing SPQR chain"],
                    )
                )
            if chains_0.receive is not None and not spqr.key_history.ckr_events:
                spqr.key_history.add_ckr_event(
                    KeyEvent(
                        key_type="CK",
                        key_number=0,
                        key_value=chains_0.receive.CK,
                        created_at_step="init",
                        created_in_context="SPQR initial receiving chain key (epoch 0)",
                        party=party.name,
                        direction="recv",
                        start_n=0,
                        used_for=["incoming SPQR chain"],
                    )
                )


def track_keys_from_send_step(
    party: TripleRatchetPartyState,
    party_name: str,
    message_id: int,
) -> None:
    """Record key events that occurred during a send step."""
    dr = party.dr
    spqr = party.spqr

    # DR: track CKs advancement
    if dr.CKs:
        dr.key_history.add_cks_event(
            KeyEvent(
                key_type="CK",
                key_number=0,
                key_value=dr.CKs,
                created_at_step=f"send#{message_id}",
                created_in_context=f"DR sending chain key advanced (msg #{message_id})",
                party=party_name,
                direction="send",
                start_n=dr.Ns,
                used_for=[f"message #{message_id} (DR)"],
            )
        )

    # DR: track RK if a DH ratchet step occurred (Ns == 1 at each DH step)
    if dr.RK and dr.Ns == 1:
        dr.key_history.add_rk_event(
            KeyEvent(
                key_type="RK",
                key_number=0,
                key_value=dr.RK,
                created_at_step=f"send#{message_id}:dh_ratchet",
                created_in_context=f"DR root key after DH ratchet (send msg #{message_id})",
                party=party_name,
                start_send_n=dr.Ns,
                start_recv_n=dr.Nr,
                used_for=[f"message #{message_id} (DR)"],
            )
        )

    if spqr is None:
        return

    # SPQR: track RK transitions
    if spqr.RK:
        chains = spqr.kdfchains.get(spqr.epoch)
        if chains is not None and chains.send is not None:
            spqr.key_history.add_cks_event(
                KeyEvent(
                    key_type="CK",
                    key_number=0,
                    key_value=chains.send.CK,
                    created_at_step=f"send#{message_id}",
                    created_in_context=f"SPQR sending chain key advanced (msg #{message_id}, epoch {spqr.epoch})",
                    party=party_name,
                    direction="send",
                    start_n=message_id,
                    used_for=[f"message #{message_id} (SPQR)"],
                )
            )


def track_keys_from_receive_step(
    party: TripleRatchetPartyState,
    party_name: str,
    message_id: int,
) -> None:
    """Record key events that occurred during a receive step."""
    dr = party.dr
    spqr = party.spqr

    # DR: track CKr advancement
    if dr.CKr:
        dr.key_history.add_ckr_event(
            KeyEvent(
                key_type="CK",
                key_number=0,
                key_value=dr.CKr,
                created_at_step=f"receive#{message_id}",
                created_in_context=f"DR receiving chain key advanced (msg #{message_id})",
                party=party_name,
                direction="recv",
                start_n=dr.Nr,
                used_for=[f"message #{message_id} (DR)"],
            )
        )

    if spqr is None:
        return

    # SPQR: track receive chain advancement
    chains = spqr.kdfchains.get(spqr.epoch)
    if chains is not None and chains.receive is not None:
        spqr.key_history.add_ckr_event(
            KeyEvent(
                key_type="CK",
                key_number=0,
                key_value=chains.receive.CK,
                created_at_step=f"receive#{message_id}",
                created_in_context=f"SPQR receiving chain key advanced (msg #{message_id}, epoch {spqr.epoch})",
                party=party_name,
                direction="recv",
                start_n=message_id,
                used_for=[f"message #{message_id} (SPQR)"],
            )
        )
