from __future__ import annotations

from typing import Any

from components.data_classes import DHKeyPair, Header, LimitedSkippedKeys, PartyState, DoubleRatchetState
from modules import external as ext


def _require_dh_pair(state: PartyState) -> DHKeyPair:
    if state.DHs is None:
        raise ValueError("DHs key pair is not initialized")
    return state.DHs


def initialize_session(session: DoubleRatchetState) -> None:
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

    RatchetInitAlice(session.initializer, shared_secret, bob_spk_key_pair.public)
    RatchetInitBob(session.responder, shared_secret, bob_spk_key_pair)


def RatchetInitAlice(state: PartyState, SK: bytes, bob_dh_public_key: str) -> None:
    state.DHs = ext.GENERATE_DH()
    state.DHr = bob_dh_public_key
    state.RK, state.CKs = ext.KDF_RK(SK, ext.DH(_require_dh_pair(state), state.DHr))
    state.CKr = None
    state.Ns = 0
    state.Nr = 0
    state.PN = 0
    state.MKSKIPPED = LimitedSkippedKeys()


def RatchetInitBob(state: PartyState, SK: bytes, bob_dh_key_pair: DHKeyPair) -> None:
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
    state.CKs, mk = ext.KDF_CK(state.CKs)
    Ns = state.Ns
    state.Ns += 1
    return Ns, mk


def RatchetEncrypt(state: PartyState, plaintext: bytes, AD: bytes) -> tuple[Header, bytes, bytes]:
    Ns, mk = RatchetSendKey(state)
    header = ext.HEADER(_require_dh_pair(state), state.PN, Ns)
    return header, ext.ENCRYPT(mk, plaintext, ext.CONCAT(AD, header)), mk


def RatchetReceiveKey(state: PartyState, header: Header, trace: dict[str, Any] | None = None) -> bytes:
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


def RatchetDecrypt(state: PartyState, header: Header, ciphertext: bytes, AD: bytes) -> bytes:
    mk = RatchetReceiveKey(state, header)
    return ext.DECRYPT(mk, ciphertext, ext.CONCAT(AD, header))


def TrySkippedMessageKeys(state: PartyState, header: Header) -> bytes | None:
    if (header.dh, header.n) in state.MKSKIPPED:
        mk = state.MKSKIPPED[header.dh, header.n]
        del state.MKSKIPPED[header.dh, header.n]
        return mk
    else:
        return None


def SkipMessageKeys(state: PartyState, until: int) -> None:
    if state.Nr + ext.MAX_SKIP < until:
        raise ValueError("Too many skipped messages")
    if state.CKr is not None:
        while state.Nr < until:
            state.CKr, mk = ext.KDF_CK(state.CKr)
            state.MKSKIPPED[state.DHr, state.Nr] = mk
            state.Nr += 1


def DHRatchet(state: PartyState, header: Header) -> None:
    state.PN = state.Ns
    state.Ns = 0
    state.Nr = 0
    state.DHr = header.dh
    state.RK, state.CKr = ext.KDF_RK(state.RK, ext.DH(_require_dh_pair(state), state.DHr))
    state.DHs = ext.GENERATE_DH()
    state.RK, state.CKs = ext.KDF_RK(state.RK, ext.DH(_require_dh_pair(state), state.DHr))
