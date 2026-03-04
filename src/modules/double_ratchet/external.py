"""
Implementations of the Double Ratchet external functions
as defined in Signal's specification (Section 3.1).

This module uses real cryptographic primitives for:
- Diffie-Hellman (X25519)
- AEAD (ChaCha20-Poly1305)

Note:
Most functions in this module were initially generated with GAI tools,
then reviewed and adapted for this project.
"""


import hashlib
import json
from Crypto.Cipher import ChaCha20_Poly1305
from Crypto.Protocol.DH import key_agreement
from Crypto.PublicKey import ECC
from Crypto.Random import get_random_bytes
from components.data_classes import DHKeyPair, Header

MAX_SKIP = 50

_AEAD_NONCE_LEN = 12
_AEAD_TAG_LEN = 16


def _hash_to_32_bytes(data: bytes) -> bytes:
    """
    Deterministic 32-byte output using SHA-256.
    Used to simulate KDF outputs.
    """
    return hashlib.sha256(data).digest()


def _encode_header(header: Header) -> bytes:
    """
    Encode header into a parseable JSON byte sequence.
    """
    header_dict = {
        "dh": header.dh,
        "pn": header.pn,
        "n": header.n,
    }
    return json.dumps(header_dict).encode("utf-8")


def GENERATE_DH() -> DHKeyPair:
    """
    Returns a new Curve25519 Diffie-Hellman key pair.
    Both private and public keys are hex-encoded strings.
    """
    private_seed = get_random_bytes(32)
    private_key = ECC.construct(curve="Curve25519", seed=private_seed)
    pub = private_key.public_key().export_key(format="raw").hex()
    priv = private_seed.hex()
    return DHKeyPair(private=priv, public=pub)


def DH(dh_pair: DHKeyPair, dh_pub: str) -> bytes:
    """
    Returns a Diffie-Hellman shared secret (32-byte key material).
    """
    if dh_pair is None or dh_pair.private is None or dh_pub is None:
        raise ValueError("Invalid DH public key")

    try:
        private_seed = bytes.fromhex(dh_pair.private)
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
    """
    Derives (new_root_key, new_chain_key)
    from current root key and DH output.
    """
    if rk is None or dh_out is None:
        raise ValueError("KDF_RK inputs cannot be None")

    material = rk + dh_out
    new_root = _hash_to_32_bytes(material + b"root")
    new_chain = _hash_to_32_bytes(material + b"chain")
    return new_root, new_chain


def KDF_CK(ck: bytes) -> tuple[bytes, bytes]:
    """
    Derives (next_chain_key, message_key)
    from current chain key.
    """
    if ck is None:
        raise ValueError("Chain key is None")

    next_ck = _hash_to_32_bytes(ck + b"next")
    mk = _hash_to_32_bytes(ck + b"msg")
    return next_ck, mk


def ENCRYPT(mk: bytes, plaintext: bytes, associated_data: bytes) -> bytes:
    """
    AEAD encryption using ChaCha20-Poly1305.
    Produces: nonce || tag || ciphertext
    """
    if mk is None:
        raise ValueError("Message key cannot be None")
    if associated_data is None:
        associated_data = b""

    cipher = ChaCha20_Poly1305.new(key=mk)
    cipher.update(associated_data)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return cipher.nonce + tag + ciphertext


def DECRYPT(mk: bytes, ciphertext: bytes, associated_data: bytes) -> bytes:
    """
    AEAD decryption using ChaCha20-Poly1305.
    Verifies tag and returns plaintext.
    """
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
    """
    Creates a message header containing:
    - dh: public ratchet key
    - pn: previous chain length
    - n: message number
    """
    if dh_pair is None or dh_pair.public is None:
        raise ValueError("Invalid DH key pair")

    return Header(dh=dh_pair.public, pn=pn, n=n)


def CONCAT(ad: bytes, header: Header) -> bytes:
    """
    Encodes associated data + header into parseable bytes.
    Format:
        len(ad) || ad || header_json
    """
    if ad is None:
        ad = b""

    header_bytes = _encode_header(header)
    ad_length = len(ad).to_bytes(4, "big")
    return ad_length + ad + header_bytes
