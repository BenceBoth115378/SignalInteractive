"""
Shared cryptographic helpers used by protocol modules.

This module centralizes the external cryptographic primitives used by:
- Double Ratchet
- X3DH
- PQXDH
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from Crypto.Cipher import ChaCha20_Poly1305
from Crypto.Protocol.DH import key_agreement
from Crypto.PublicKey import ECC
from Crypto.Random import get_random_bytes
from Crypto.Signature import eddsa
from pqcrypto.kem import ml_kem_1024

from components.data_classes import DHKeyPair, Header

MAX_SKIP = 50

_AEAD_NONCE_LEN = 12
_AEAD_TAG_LEN = 16


_SPQR_HEADER_SIZE = 64
_SPQR_EK_SIZE = 1536
_SPQR_CT1_SIZE = 1408
_SPQR_CT2_SIZE = 160

_spqr_private_to_public: dict[bytes, bytes] = {}
_spqr_ciphertext_to_shared: dict[bytes, bytes] = {}


def _hash_to_32_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _expand_to_length(seed: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def _encode_header(header: Header) -> bytes:
    header_dict = {
        "dh": header.dh,
        "pn": header.pn,
        "n": header.n,
    }
    return json.dumps(header_dict).encode("utf-8")


def _normalize_dh_pair(dh_pair: DHKeyPair | dict[str, str]) -> tuple[str, str]:
    if isinstance(dh_pair, DHKeyPair):
        return dh_pair.private, dh_pair.public
    if isinstance(dh_pair, dict):
        private = dh_pair.get("private")
        public = dh_pair.get("public")
        if isinstance(private, str) and isinstance(public, str):
            return private, public
    raise ValueError("Invalid DH key pair")


def _identity_signing_private_key_from_dh_private(identity_dh_private_hex: str):
    if not isinstance(identity_dh_private_hex, str):
        raise ValueError("Invalid identity private key")
    try:
        seed = bytes.fromhex(identity_dh_private_hex)
        return ECC.construct(curve="Ed25519", seed=seed)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid identity private key") from exc


def GENERATE_DH() -> DHKeyPair:
    private_seed = get_random_bytes(32)
    private_key = ECC.construct(curve="Curve25519", seed=private_seed)
    pub = private_key.public_key().export_key(format="raw").hex()
    priv = private_seed.hex()
    return DHKeyPair(private=priv, public=pub)


def DH(dh_pair: DHKeyPair | dict[str, str], dh_pub: str) -> bytes:
    if dh_pair is None or dh_pub is None:
        raise ValueError("Invalid DH public key")

    try:
        private_hex, _ = _normalize_dh_pair(dh_pair)
        private_seed = bytes.fromhex(private_hex)
        peer_public_raw = bytes.fromhex(dh_pub)
        private_key = ECC.construct(curve="Curve25519", seed=private_seed)
        peer_public_key = ECC.construct(
            curve="Curve25519",
            point_x=int.from_bytes(peer_public_raw, "little"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid DH key encoding") from exc

    shared_secret = key_agreement(
        static_priv=private_key,
        static_pub=peer_public_key,
        kdf=lambda z: z,
    )
    return _hash_to_32_bytes(shared_secret)


def KDF_RK(rk: bytes, dh_out: bytes) -> tuple[bytes, bytes]:
    if rk is None or dh_out is None:
        raise ValueError("KDF_RK inputs cannot be None")

    material = rk + dh_out
    new_root = _hash_to_32_bytes(material + b"root")
    new_chain = _hash_to_32_bytes(material + b"chain")
    return new_root, new_chain


def KDF_CK(ck: bytes) -> tuple[bytes, bytes]:
    if ck is None:
        raise ValueError("Chain key is None")

    next_ck = _hash_to_32_bytes(ck + b"next")
    mk = _hash_to_32_bytes(ck + b"msg")
    return next_ck, mk


def ENCRYPT(mk: bytes, plaintext: bytes, associated_data: bytes) -> bytes:
    if mk is None:
        raise ValueError("Message key cannot be None")
    if associated_data is None:
        associated_data = b""

    cipher = ChaCha20_Poly1305.new(key=mk)
    cipher.update(associated_data)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return cipher.nonce + tag + ciphertext


def DECRYPT(mk: bytes, ciphertext: bytes, associated_data: bytes) -> bytes:
    if mk is None:
        raise ValueError("Message key cannot be None")
    if associated_data is None:
        associated_data = b""
    if ciphertext is None or len(ciphertext) < (_AEAD_NONCE_LEN + _AEAD_TAG_LEN):
        raise ValueError("Ciphertext too short")

    nonce = ciphertext[:_AEAD_NONCE_LEN]
    tag = ciphertext[_AEAD_NONCE_LEN:_AEAD_NONCE_LEN + _AEAD_TAG_LEN]
    encrypted = ciphertext[_AEAD_NONCE_LEN + _AEAD_TAG_LEN:]

    try:
        cipher = ChaCha20_Poly1305.new(key=mk, nonce=nonce)
        cipher.update(associated_data)
        return cipher.decrypt_and_verify(encrypted, tag)
    except ValueError as e:
        raise ValueError("Authentication failed") from e


def HEADER(dh_pair: DHKeyPair, pn: int, n: int) -> Header:
    if dh_pair is None or dh_pair.public is None:
        raise ValueError("Invalid DH key pair")
    return Header(dh=dh_pair.public, pn=pn, n=n)


def CONCAT(ad: bytes, header: Header) -> bytes:
    if ad is None:
        ad = b""

    header_bytes = _encode_header(header)
    ad_length = len(ad).to_bytes(4, "big")
    return ad_length + ad + header_bytes


def IDENTITY_SIGNING_PUBLIC_FROM_DH_PRIVATE(identity_dh_private_hex: str) -> str:
    private_key = _identity_signing_private_key_from_dh_private(identity_dh_private_hex)
    public_pem = private_key.public_key().export_key(format="PEM")
    return public_pem.encode("utf-8").hex()


def SIGN_WITH_IDENTITY_DH_PRIVATE(identity_dh_private_hex: str, message: bytes) -> str:
    private_key = _identity_signing_private_key_from_dh_private(identity_dh_private_hex)
    signer = eddsa.new(private_key, "rfc8032")
    return signer.sign(message).hex()


def VERIFY_WITH_IDENTITY_SIGNING_PUBLIC(identity_signing_public: str, message: bytes, signature_hex: str) -> bool:
    try:
        public_pem = bytes.fromhex(identity_signing_public).decode("utf-8")
        public_key = ECC.import_key(public_pem)
        verifier = eddsa.new(public_key, "rfc8032")
        verifier.verify(message, bytes.fromhex(signature_hex))
        return True
    except Exception:
        return False


def SIGN(private_pem: str, message: bytes) -> str:
    private_key = ECC.import_key(private_pem)
    signer = eddsa.new(private_key, "rfc8032")
    return signer.sign(message).hex()


def VERIFY(public_pem: str, message: bytes, signature_hex: str) -> bool:
    try:
        public_key = ECC.import_key(public_pem)
        verifier = eddsa.new(public_key, "rfc8032")
        verifier.verify(message, bytes.fromhex(signature_hex))
        return True
    except Exception:
        return False


def GENERATE_PQKEM_KEYPAIR() -> dict[str, str]:
    public_bytes, private_bytes = ml_kem_1024.generate_keypair()
    return {
        "private": private_bytes.hex(),
        "public": public_bytes.hex(),
    }


def PQKEM_ENCAPSULATE(pq_public_hex: str) -> tuple[str, bytes]:
    if not isinstance(pq_public_hex, str):
        raise ValueError("Invalid PQ public key")

    try:
        public_bytes = bytes.fromhex(pq_public_hex)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid PQ public key encoding") from exc

    kem_ciphertext, shared_secret = ml_kem_1024.encrypt(public_bytes)
    return kem_ciphertext.hex(), shared_secret


def PQKEM_DECAPSULATE(pq_private_hex: str, kem_ciphertext_hex: str) -> bytes:
    if not isinstance(pq_private_hex, str):
        raise ValueError("Invalid PQ private key")
    if not isinstance(kem_ciphertext_hex, str):
        raise ValueError("Invalid KEM ciphertext")

    try:
        private_bytes = bytes.fromhex(pq_private_hex)
        kem_ciphertext = bytes.fromhex(kem_ciphertext_hex)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid PQ key or ciphertext encoding") from exc

    return ml_kem_1024.decrypt(private_bytes, kem_ciphertext)


def KDF_SK(dh_values: list[bytes]) -> bytes:
    joined = b"X3DH|" + b"|".join(dh_values)
    return _hash_to_32_bytes(joined + b"|SK")


def KDF_SK_PQXDH(secret_values: list[bytes]) -> bytes:
    joined = b"PQXDH|" + b"|".join(secret_values)
    return _hash_to_32_bytes(joined + b"|SK")


def CALC_AD(
    initiator_identity_public: str,
    responder_identity_public: str,
) -> str:

    payload: dict[str, Any] = {
        "ik_a": initiator_identity_public,
        "ik_b": responder_identity_public,
    }
    serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def SPQR_INCREMENTAL_KEM_KEYGEN() -> tuple[bytes, bytes, bytes]:
    """Return (dk, ek_header, ek_vector) for the SPQR incremental KEM interface."""
    keypair = GENERATE_PQKEM_KEYPAIR()
    dk = bytes.fromhex(keypair["private"])
    ek = bytes.fromhex(keypair["public"])
    if len(ek) != _SPQR_EK_SIZE + 32:
        raise ValueError("Unexpected ML-KEM-1024 public key size")

    ek_vector = ek[:_SPQR_EK_SIZE]
    ek_seed = ek[_SPQR_EK_SIZE:]
    hek = hashlib.sha3_256(ek_seed + ek_vector).digest()
    ek_header = ek_seed + hek
    if len(ek_header) != _SPQR_HEADER_SIZE:
        raise ValueError("Unexpected SPQR header size")

    _spqr_private_to_public[dk] = ek
    return dk, ek_header, ek_vector


def SPQR_INCREMENTAL_KEM_ENCAPS1(ek_header: bytes) -> tuple[bytes, bytes, bytes]:
    """Return (encaps_secret, ct1, shared_secret) using only ek_header."""
    if len(ek_header) != _SPQR_HEADER_SIZE:
        raise ValueError("Invalid SPQR encapsulation header size")

    randomness = get_random_bytes(32)
    ct1 = _expand_to_length(hashlib.sha3_256(b"SPQR:ct1" + ek_header + randomness).digest(), _SPQR_CT1_SIZE)
    shared_secret = hashlib.sha3_256(b"SPQR:ss" + ek_header + ct1 + randomness).digest()
    encaps_secret = randomness
    return encaps_secret, ct1, shared_secret


def SPQR_INCREMENTAL_KEM_ENCAPS2(encaps_secret: bytes, ek_header: bytes, ek_vector: bytes) -> bytes:
    """Return ct2 and register complete ciphertext for simulated decapsulation."""
    if len(encaps_secret) != 32:
        raise ValueError("Invalid encapsulation secret size")
    if len(ek_header) != _SPQR_HEADER_SIZE:
        raise ValueError("Invalid SPQR encapsulation header size")
    if len(ek_vector) != _SPQR_EK_SIZE:
        raise ValueError("Invalid SPQR encapsulation vector size")

    ek_seed = ek_header[:32]
    hek = ek_header[32:]
    if hashlib.sha3_256(ek_seed + ek_vector).digest() != hek:
        raise ValueError("EK integrity check failed")

    ct1 = _expand_to_length(hashlib.sha3_256(b"SPQR:ct1" + ek_header + encaps_secret).digest(), _SPQR_CT1_SIZE)
    ct2 = _expand_to_length(
        hashlib.sha3_256(b"SPQR:ct2" + ek_header + ek_vector + encaps_secret).digest(),
        _SPQR_CT2_SIZE,
    )
    shared_secret = hashlib.sha3_256(b"SPQR:ss" + ek_header + ct1 + encaps_secret).digest()
    _spqr_ciphertext_to_shared[ct1 + ct2] = shared_secret
    return ct2


def SPQR_INCREMENTAL_KEM_DECAPS(dk: bytes, ct1: bytes, ct2: bytes) -> bytes:
    """Decapsulate shared secret for the simulated incremental interface."""
    if len(ct1) != _SPQR_CT1_SIZE:
        raise ValueError("Invalid SPQR ct1 size")
    if len(ct2) != _SPQR_CT2_SIZE:
        raise ValueError("Invalid SPQR ct2 size")

    if dk not in _spqr_private_to_public:
        raise ValueError("Unknown SPQR decapsulation key")

    key = ct1 + ct2
    shared_secret = _spqr_ciphertext_to_shared.get(key)
    if shared_secret is None:
        raise ValueError("Unknown SPQR ciphertext for simulated decapsulation")
    return shared_secret
