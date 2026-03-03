"""
Mock implementations of the Double Ratchet external functions
as defined in Signal's specification (Section 3.1).

These are NOT cryptographically secure.
They are deterministic, symbolic, and suitable only for
educational / visualization purposes.
"""


import hashlib
import json
import os
from components.data_classes import DHKeyPair, Header

MAX_SKIP = 50


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
    Returns a new mock Diffie-Hellman key pair.
    """
    # Generate random 16 bytes and hex-encode
    priv = os.urandom(16).hex()
    pub = _hash_to_32_bytes(priv.encode()).hex()
    return DHKeyPair(private=priv, public=pub)


def DH(dh_pair: DHKeyPair, dh_pub: str) -> bytes:
    """
    Returns a mock Diffie-Hellman shared secret.
    Deterministically hashes private + public.
    """
    if dh_pub is None:
        raise ValueError("Invalid DH public key")

    combined = dh_pair.private.encode() + dh_pub.encode()
    return _hash_to_32_bytes(combined)


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
    Mock AEAD encryption.
    Produces: HASH(mk || ad || plaintext) || plaintext
    """
    if mk is None:
        raise ValueError("Message key cannot be None")

    tag = _hash_to_32_bytes(mk + associated_data + plaintext)
    return tag + plaintext


def DECRYPT(mk: bytes, ciphertext: bytes, associated_data: bytes) -> bytes:
    """
    Mock AEAD decryption.
    Verifies tag and returns plaintext.
    Raises exception on authentication failure.
    """
    if mk is None:
        raise ValueError("Message key cannot be None")

    tag = ciphertext[:32]
    plaintext = ciphertext[32:]

    expected_tag = _hash_to_32_bytes(mk + associated_data + plaintext)

    if tag != expected_tag:
        raise ValueError("Authentication failed")

    return plaintext


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
