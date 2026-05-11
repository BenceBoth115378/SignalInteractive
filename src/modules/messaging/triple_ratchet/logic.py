from __future__ import annotations

import hashlib
import hmac as _hmac
from typing import Any

from components.data_classes import (
    DHKeyPair,
    PartyState,
    SpqrHeader,
    SpqrRatchetState,
    TripleRatchetHeader,
    TripleRatchetPartyState,
    TripleRatchetSessionState,
)
from modules import external as ext
from modules.messaging.double_ratchet.logic import (
    RatchetInitAlice,
    RatchetInitBob,
    RatchetReceiveKey,
    RatchetSendKey,
)
from modules.messaging.spqr.logic import (
    RatchetInitAliceSCKA,
    SCKARatchetReceiveKey,
    SCKARatchetSendKey,
)

_PROTOCOL_INFO = b"TripleRatchet:HMAC-SHA256"


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return _hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes) -> bytes:
    return _hmac.new(prk, info + b"\x01", hashlib.sha256).digest()


def KDF_TR_SPLIT(sk: bytes) -> tuple[bytes, bytes]:
    """Derive separate 32-byte seeds for DR and SPQR from the PQXDH shared secret."""
    prk = _hkdf_extract(b"\x00" * 32, sk)
    sk_dr = _hkdf_expand(prk, _PROTOCOL_INFO + b":DR")
    sk_spqr = _hkdf_expand(prk, _PROTOCOL_INFO + b":SPQR")
    return sk_dr, sk_spqr


def KDF_HYBRID(ec_mk: bytes, pq_mk: bytes) -> bytes:
    """Combine the DR and SPQR per-message keys into a single encryption key."""
    prk = _hkdf_extract(b"\x00" * 32, ec_mk + pq_mk)
    return _hkdf_expand(prk, _PROTOCOL_INFO + b":MK")


def initialize_session_from_pqxdh(
    sk: bytes,
    bob_spk_pair: DHKeyPair,
) -> TripleRatchetSessionState:
    """Bootstrap a Triple Ratchet session from PQXDH output.

    The 32-byte PQXDH shared secret is split into two independent seeds:
    one to seed the classical DR ratchet and one to seed the SPQR ratchet.
    
    Alice is initialized immediately, but Bob is initialized only after
    receiving Alice's first message (deferred bootstrap pattern).
    """
    sk_dr, sk_spqr = KDF_TR_SPLIT(sk)

    alice_dr = PartyState("Alice")
    RatchetInitAlice(alice_dr, sk_dr, bob_spk_pair.public)

    alice_spqr = RatchetInitAliceSCKA(sk_spqr)

    # Bob is not initialized yet; will be initialized when he receives the first message
    return TripleRatchetSessionState(
        alice=TripleRatchetPartyState("Alice", alice_dr, alice_spqr),
        bob=None,  # Initialized after first message received
        message_log=[],
    )


def RatchetInitBobTripleRatchet(
    dr_state: PartyState,
    sk_dr: bytes,
    bob_spk_pair: DHKeyPair,
) -> None:
    """Initialize Bob's DR state.

    Called when Bob receives his first message from Alice.
    """
    RatchetInitBob(dr_state, sk_dr, bob_spk_pair)


def TripleRatchetEncrypt(
    dr_state: PartyState,
    spqr_state: SpqrRatchetState,
    plaintext: bytes,
    AD: bytes,
) -> tuple[TripleRatchetHeader, bytes, bytes, bytes, bytes, dict[str, Any], dict[str, Any]]:
    """Encrypt one message using both DR and SPQR in parallel.

    Returns (header, ciphertext, ec_mk, pq_mk, mk, dr_trace, spqr_trace).
    """
    # DR ratchet step
    dr_ns, ec_mk = RatchetSendKey(dr_state)
    dr_header = ext.HEADER(dr_state.DHs, dr_state.PN, dr_ns)
    dr_trace: dict[str, Any] = {
        "Ns": dr_ns,
        "mk": ec_mk,
        "dhs_public": dr_state.DHs.public if dr_state.DHs else "",
        "rk": dr_state.RK,
        "cks": dr_state.CKs,
    }

    # SPQR ratchet step
    spqr_msg, spqr_n, pq_mk, spqr_trace = SCKARatchetSendKey(spqr_state)
    spqr_header = SpqrHeader(msg=spqr_msg, n=spqr_n)

    # Combine both message keys
    mk = KDF_HYBRID(ec_mk, pq_mk)

    triple_header = TripleRatchetHeader(dr=dr_header, spqr=spqr_header)
    associated = ext.CONCAT(AD, dr_header)
    ciphertext = ext.ENCRYPT(mk, plaintext, associated)

    return triple_header, ciphertext, ec_mk, pq_mk, mk, dr_trace, spqr_trace


def TripleRatchetDecrypt(
    dr_state: PartyState,
    spqr_state: SpqrRatchetState,
    triple_header: TripleRatchetHeader,
    ciphertext: bytes,
    AD: bytes,
) -> tuple[bytes, bytes, bytes, bytes, dict[str, Any], dict[str, Any]]:
    """Decrypt one message using both DR and SPQR in parallel.

    Returns (plaintext, ec_mk, pq_mk, mk, dr_trace, spqr_trace).
    """
    dr_trace: dict[str, Any] = {}
    ec_mk = RatchetReceiveKey(dr_state, triple_header.dr, dr_trace)
    dr_trace["rk"] = dr_state.RK
    dr_trace["ckr"] = dr_state.CKr

    pq_mk, spqr_trace = SCKARatchetReceiveKey(spqr_state, triple_header.spqr)

    mk = KDF_HYBRID(ec_mk, pq_mk)

    associated = ext.CONCAT(AD, triple_header.dr)
    plaintext = ext.DECRYPT(mk, ciphertext, associated)

    return plaintext, ec_mk, pq_mk, mk, dr_trace, spqr_trace
