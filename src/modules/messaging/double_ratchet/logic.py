from __future__ import annotations

from typing import Any

from components.data_classes import DHKeyPair, DRHeader, LimitedSkippedKeys, PartyState, DoubleRatchetState
from modules import external as ext

"""Double Ratchet core logic.

This module implements a simplified educational Double Ratchet algorithm used
by the messaging demos. It provides routines to initialize sessions (including
from an X3DH-derived shared secret), perform DH ratchets, derive message
encryption keys, encrypt/decrypt messages, and manage skipped message keys.

The functions aim to mirror the steps in the Double Ratchet specification but
are intentionally simplified for clarity and visualization in the app.
"""


def _require_dh_pair(state: PartyState) -> DHKeyPair:
    """Return the party's ephemeral DH key pair or raise ValueError.

    Many operations assume the local ephemeral DH key pair (`DHs`) is
    initialized. This helper centralizes the check and error message.
    """
    if state.DHs is None:
        raise ValueError("DHs key pair is not initialized")
    return state.DHs


def initialize_session(session: DoubleRatchetState) -> None:
    """Initialize a demo session for both parties.

    For the educational demo we initialize both Alice and Bob locally. In a
    real-world protocol Alice would send her DH public key to Bob and Bob
    would initialize on receipt.
    """
    # For simplicity, we directly initialize both parties here.
    # In a real scenario, Alice would initialize and send her DH public key to Bob,
    # and Bob would initialize upon receiving it.
    bob_dh_key_pair = ext.GENERATE_DH()
    shared_secret = ext.DH(ext.GENERATE_DH(), ext.GENERATE_DH().public)
    RatchetInitAlice(session.initializer, shared_secret, bob_dh_key_pair.public)
    RatchetInitBob(session.responder, shared_secret, bob_dh_key_pair)


def initialize_session_from_x3dh(
    session: DoubleRatchetState,
    shared_secret: bytes,
    bob_spk_key_pair: DHKeyPair,
) -> None:
    """Initialize Double Ratchet state using X3DH-derived values.

    This function is used after X3DH bootstrapping: `shared_secret` is the
    symmetric key derived by the X3DH exchange and `bob_spk_key_pair` is Bob's
    signed prekey pair produced during X3DH. It sets up both Alice and Bob
    for the subsequent Double Ratchet operations used in the demo.
    """

    RatchetInitAlice(session.initializer, shared_secret, bob_spk_key_pair.public)
    RatchetInitBob(session.responder, shared_secret, bob_spk_key_pair)


def RatchetInitAlice(state: PartyState, SK: bytes, bob_dh_public_key: str) -> None:
    """Initialize the state for the party that starts (Alice).

    SK is the shared secret input to the root KDF; `bob_dh_public_key` is the
    public value of Bob's DH used in the initial DH ratchet step. The function
    generates Alice's ephemeral DH pair, derives root and chain keys, and
    resets ratchet counters and skipped-key storage.
    """
    state.DHs = ext.GENERATE_DH()
    state.DHr = bob_dh_public_key
    state.RK, state.CKs = ext.KDF_RK(SK, ext.DH(_require_dh_pair(state), state.DHr))
    state.CKr = None
    state.Ns = 0
    state.Nr = 0
    state.PN = 0
    state.MKSKIPPED = LimitedSkippedKeys()


def RatchetInitBob(state: PartyState, SK: bytes, bob_dh_key_pair: DHKeyPair) -> None:
    """Initialize the state for the responder (Bob).

    Bob starts with his ephemeral DH pair already chosen (`bob_dh_key_pair`) and
    the X3DH-derived root key `SK`. This sets up Bob to receive Alice's first
    message and continue the ratchet.
    """
    state.DHs = bob_dh_key_pair
    state.DHr = None
    state.RK = SK
    state.CKs = None
    state.CKr = None
    state.Ns = 0
    state.Nr = 0
    state.PN = 0
    state.MKSKIPPED = LimitedSkippedKeys()


def RatchetSendKey(state: PartyState) -> tuple[int, bytes]:
    """Advance the sending chain and return the next message number and key.

    Returns the message sequence number (`Ns`) and the derived message key
    (`mk`) to be used for encrypting a single message.
    """
    state.CKs, mk = ext.KDF_CK(state.CKs)
    Ns = state.Ns
    state.Ns += 1
    return Ns, mk


def RatchetEncrypt(state: PartyState, plaintext: bytes, AD: bytes) -> tuple[DRHeader, bytes, bytes]:
    """Encrypt `plaintext` under the sending party's current chain.

    Returns a tuple of (header, ciphertext, mk) where `header` contains the
    sender's DH public value and message counters, `ciphertext` is the
    authenticated-encrypted payload and `mk` is the message key used (used for
    visualization/tracing in the demo).
    """
    Ns, mk = RatchetSendKey(state)
    header = ext.HEADER(_require_dh_pair(state), state.PN, Ns)
    return header, ext.ENCRYPT(mk, plaintext, ext.CONCAT(AD, header)), mk


def RatchetReceiveKey(state: PartyState, header: DRHeader, trace: dict[str, Any] | None = None) -> bytes:
    """Obtain the message key for a received message described by `header`.

    The function first checks any skipped-message cache, performs a DH
    ratchet if the header contains a new remote DH, advances receive chain
    keys, and returns the derived message key for decryption. An optional
    `trace` dict may be provided to collect internal state for visualization.
    """
    mk = TrySkippedMessageKeys(state, header)
    if mk is not None:
        if trace is not None:
            trace["used_skipped_mk"] = True
            trace["ckr_before_kdf_ck"] = None
            trace["ckr_after_double_ratchet"] = None
        return mk
    if trace is not None:
        trace["used_skipped_mk"] = False
    if header.dh != state.DHr:
        SkipMessageKeys(state, header.pn)
        DHRatchet(state, header)
        if trace is not None:
            trace["ckr_after_double_ratchet"] = state.CKr
    elif trace is not None:
        trace["ckr_after_double_ratchet"] = None
    SkipMessageKeys(state, header.n)
    if trace is not None:
        trace["ckr_before_kdf_ck"] = state.CKr
    state.CKr, mk = ext.KDF_CK(state.CKr)
    state.Nr += 1
    return mk


def RatchetDecrypt(state: PartyState, header: DRHeader, ciphertext: bytes, AD: bytes) -> bytes:
    """Decrypt a received `ciphertext` using the key derived from `header`.

    This is a convenience wrapper that derives the correct message key and
    then calls the external AEAD `DECRYPT` primitive with the associated
    data (AD concatenated with the header).
    """
    mk = RatchetReceiveKey(state, header)
    return ext.DECRYPT(mk, ciphertext, ext.CONCAT(AD, header))


def TrySkippedMessageKeys(state: PartyState, header: DRHeader) -> bytes | None:
    """Return and remove a previously saved skipped message key, if present.

    Skipped message keys are stored when messages are missed and derived
    later when processing future headers. If present, the key is returned and
    removed from the skipped-key store.
    """
    if (header.dh, header.n) in state.MKSKIPPED:
        mk = state.MKSKIPPED[header.dh, header.n]
        del state.MKSKIPPED[header.dh, header.n]
        return mk
    else:
        return None


def SkipMessageKeys(state: PartyState, until: int) -> None:
    """Derive and store message keys for skipped incoming messages.

    Advances the receiver chain key up to `until` and stores each derived
    message key in `state.MKSKIPPED`. Protects against unbounded skipping by
    enforcing `ext.MAX_SKIP`.
    """
    if state.Nr + ext.MAX_SKIP < until:
        raise ValueError("Too many skipped messages")
    if state.CKr is not None:
        while state.Nr < until:
            state.CKr, mk = ext.KDF_CK(state.CKr)
            state.MKSKIPPED[state.DHr, state.Nr] = mk
            state.Nr += 1


def DHRatchet(state: PartyState, header: DRHeader) -> None:
    """Perform a DH ratchet when a new remote DH public key is observed.

    Updates the previous message number (`PN`), resets counters, performs a
    root-key KDF with the new DH shared secret to derive the new receive
    chain (`CKr`) and then generates a fresh local ephemeral DH pair to
    derive the new send chain (`CKs`).
    """
    state.PN = state.Ns
    state.Ns = 0
    state.Nr = 0
    state.DHr = header.dh
    state.RK, state.CKr = ext.KDF_RK(state.RK, ext.DH(_require_dh_pair(state), state.DHr))
    state.DHs = ext.GENERATE_DH()
    state.RK, state.CKs = ext.KDF_RK(state.RK, ext.DH(_require_dh_pair(state), state.DHr))
