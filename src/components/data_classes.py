from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

Perspective = Literal["global", "alice", "bob", "attacker"]


@dataclass
class AppState:
    current_module: str = ""
    perspective: Perspective = "global"
    x3dh_to_dr_bootstrap: dict | None = None


@dataclass
class X3DHState:
    alice_local: dict | None = None
    alice_generated: bool = False
    server_state: dict = field(default_factory=dict)
    bob_local: dict | None = None
    last_bundle_for_alice: dict | None = None
    alice_derived: dict | None = None
    initial_message: dict | None = None
    bob_receive_result: dict | None = None
    events: list[str] = field(default_factory=list)
    phase2_signature_verified: bool = False
    phase2_ek_generated: bool = False
    alice_needs_to_upload_opk: bool = False


@dataclass
class PQXDHState:
    alice_local: dict | None = None
    alice_generated: bool = False
    server_state: dict = field(default_factory=dict)
    bob_local: dict | None = None
    last_bundle_for_alice: dict | None = None
    alice_derived: dict | None = None
    initial_message: dict | None = None
    bob_receive_result: dict | None = None
    events: list[str] = field(default_factory=list)
    phase2_signature_verified: bool = False
    phase2_ek_generated: bool = False
    alice_needs_to_upload_opk: bool = False


@dataclass
class DoubleRatchetState:
    initializer: PartyState = field(default_factory=lambda: PartyState("Alice"))
    responder: PartyState = field(default_factory=lambda: PartyState("Bob"))
    message_log: list[MessageState] = field(default_factory=list)


@dataclass
class DHKeyPair:
    private: str
    public: str


@dataclass
class KeyEvent:
    key_type: str
    key_number: int
    key_value: bytes | str
    created_at_step: str
    created_in_context: str
    public_value: str = ""
    party: str = ""
    direction: str = ""
    remote_public: str = ""
    start_send_n: int = 0
    start_recv_n: int = 0
    start_n: int = 0
    used_for: list[str] = field(default_factory=list)


@dataclass
class KeyHistory:
    """Maintains counts and events for each key type."""
    rk_events: list[KeyEvent] = field(default_factory=list)
    cks_events: list[KeyEvent] = field(default_factory=list)
    ckr_events: list[KeyEvent] = field(default_factory=list)
    dh_events: list[KeyEvent] = field(default_factory=list)

    def get_rk_count(self) -> int:
        return len(self.rk_events)

    def get_cks_count(self) -> int:
        return len(self.cks_events)

    def get_ckr_count(self) -> int:
        return len(self.ckr_events)

    def get_ck_count(self) -> int:
        return self.get_cks_count() + self.get_ckr_count()

    def get_dh_count(self) -> int:
        return len(self.dh_events)

    def add_rk_event(self, event: KeyEvent) -> None:
        event.key_number = self.get_rk_count() + 1
        self.rk_events.append(event)

    def add_cks_event(self, event: KeyEvent) -> None:
        event.direction = "send"
        event.key_number = self.get_cks_count() + 1
        self.cks_events.append(event)

    def add_ckr_event(self, event: KeyEvent) -> None:
        event.direction = "recv"
        event.key_number = self.get_ckr_count() + 1
        self.ckr_events.append(event)

    def add_ck_event(self, event: KeyEvent) -> None:
        if event.direction == "recv":
            self.add_ckr_event(event)
            return
        self.add_cks_event(event)

    def add_dh_event(self, event: KeyEvent) -> None:
        event.key_number = self.get_dh_count() + 1
        self.dh_events.append(event)


class LimitedSkippedKeys(dict[tuple[str, int], bytes]):
    def __init__(self, *args, max_items: int = 2000, **kwargs):
        self.max_items = max_items
        super().__init__()
        if args or kwargs:
            self.update(*args, **kwargs)

    def _ensure_capacity_for(self, incoming_count: int) -> None:
        if len(self) + incoming_count > self.max_items:
            raise ValueError(f"MKSKIPPED storage limit exceeded (max={self.max_items})")

    def __setitem__(self, key: tuple[str, int], value: str) -> None:
        if key not in self:
            self._ensure_capacity_for(1)
        super().__setitem__(key, value)

    def update(self, *args, **kwargs) -> None:
        incoming = dict(*args, **kwargs)
        new_keys = [key for key in incoming if key not in self]
        self._ensure_capacity_for(len(new_keys))
        super().update(incoming)


@dataclass
class Header:
    dh: str
    pn: int
    n: int

    def __post_init__(self):
        if self.dh is None:
            raise ValueError("Header DH public key cannot be None")


@dataclass
class PartyState:
    name: str
    DHs: DHKeyPair | None = None
    DHr: str = ""
    RK: bytes | None = "RK0"
    CKs: bytes | None = ""
    CKr: bytes | None = ""
    Ns: int = 0
    Nr: int = 0
    PN: int = 0
    MKSKIPPED: LimitedSkippedKeys = field(default_factory=LimitedSkippedKeys)
    key_history: KeyHistory = field(default_factory=KeyHistory)

    def __post_init__(self):
        if isinstance(self.DHs, dict):
            self.DHs = DHKeyPair(
                private=self.DHs.get("private", ""),
                public=self.DHs.get("public", ""),
            )

        if not isinstance(self.MKSKIPPED, LimitedSkippedKeys):
            self.MKSKIPPED = LimitedSkippedKeys(self.MKSKIPPED)


@dataclass
class MessageState:
    sender: str
    receiver: str
    message_key: bytes
    cipher: bytes
    decrypted_by_bob: bytes = b""
    decrypted_by_alice: bytes = b""
    header: Header | None = None
    plaintext: bytes = b""
    seq_id: int = 0


@dataclass
class PartyStateSnapshot:
    DHs_public: str = ""
    DHs_private: str = ""
    DHr: str | None = ""
    RK: bytes | None = None
    CKs: bytes | None = None
    CKr: bytes | None = None
    Ns: int = 0
    Nr: int = 0
    PN: int = 0


@dataclass
class SendStepVisualizationSnapshot:
    sender: str
    receiver: str
    plaintext: bytes
    header: Header
    cipher: bytes
    mk: bytes
    pending_id: int
    before: PartyStateSnapshot
    after: PartyStateSnapshot
    initializer_switch_warning: str | None = None


@dataclass
class ReceiveStepVisualizationSnapshot:
    sender: str
    receiver: str
    pending_id: int
    header: Header
    cipher: bytes
    mk: bytes
    decrypted: bytes
    plaintext: bytes
    skipped_key_hit: bool
    dh_ratchet_needed: bool
    fast_forward_count: int
    fast_forward_from_nr: int
    fast_forward_to_nr: int
    ckr_after_double_ratchet: bytes | None
    ckr_before_kdf_ck: bytes | None
    before: PartyStateSnapshot
    after: PartyStateSnapshot


def _spqr_encode_bytes(value: bytes | None) -> str | None:
    if value is None:
        return None
    return value.hex()


def _spqr_decode_bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        return None


class SpqrMessageType(str, Enum):
    NONE = "None"
    HDR = "Hdr"
    EK = "Ek"
    EK_CT1_ACK = "EkCt1Ack"
    CT1_ACK = "Ct1Ack"
    CT1 = "Ct1"
    CT2 = "Ct2"


@dataclass
class SpqrSckaMessage:
    epoch: int
    msg_type: SpqrMessageType
    data: bytes = b""

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "msg_type": self.msg_type.value,
            "data": self.data.hex(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SpqrSckaMessage":
        raw_type = str(payload.get("msg_type", SpqrMessageType.NONE.value))
        msg_type = SpqrMessageType(raw_type) if raw_type in SpqrMessageType._value2member_map_ else SpqrMessageType.NONE
        raw_data = payload.get("data", "")
        data = bytes.fromhex(raw_data) if isinstance(raw_data, str) else b""
        epoch = int(payload.get("epoch", 0)) if isinstance(payload.get("epoch"), int) else 0
        return cls(epoch=epoch, msg_type=msg_type, data=data)


@dataclass
class SckaOutputKey:
    epoch: int
    key: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "key": self.key.hex(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SckaOutputKey | None":
        if not isinstance(payload, dict):
            return None
        epoch = payload.get("epoch")
        key_hex = payload.get("key")
        if not isinstance(epoch, int) or not isinstance(key_hex, str):
            return None
        try:
            key = bytes.fromhex(key_hex)
        except ValueError:
            return None
        return cls(epoch=epoch, key=key)


@dataclass
class AuthenticatorState:
    root_key: bytes = b"\x00" * 32
    mac_key: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_key": self.root_key.hex(),
            "mac_key": _spqr_encode_bytes(self.mac_key),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuthenticatorState":
        root_key = _spqr_decode_bytes(payload.get("root_key")) or (b"\x00" * 32)
        mac_key = _spqr_decode_bytes(payload.get("mac_key"))
        return cls(root_key=root_key, mac_key=mac_key)


@dataclass
class EncoderState:
    message: bytes
    chunk_size: int = 256
    next_index: int = 0

    def next_chunk(self) -> bytes:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        total_chunks = max(1, (len(self.message) + self.chunk_size - 1) // self.chunk_size)
        index = self.next_index % total_chunks
        start = index * self.chunk_size
        end = min(len(self.message), start + self.chunk_size)
        payload = self.message[start:end]
        self.next_index += 1
        return index.to_bytes(4, "big") + total_chunks.to_bytes(4, "big") + payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message.hex(),
            "chunk_size": self.chunk_size,
            "next_index": self.next_index,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EncoderState":
        raw_message = payload.get("message", "")
        message = bytes.fromhex(raw_message) if isinstance(raw_message, str) else b""
        chunk_size = int(payload.get("chunk_size", 256)) if isinstance(payload.get("chunk_size"), int) else 256
        next_index = int(payload.get("next_index", 0)) if isinstance(payload.get("next_index"), int) else 0
        return cls(message=message, chunk_size=chunk_size, next_index=next_index)


@dataclass
class DecoderState:
    message_size: int
    chunks: dict[int, bytes] = field(default_factory=dict)
    total_chunks: int | None = None

    def add_chunk(self, chunk: bytes) -> None:
        if len(chunk) < 8:
            return
        index = int.from_bytes(chunk[:4], "big")
        total = int.from_bytes(chunk[4:8], "big")
        payload = chunk[8:]
        if total <= 0:
            return
        self.total_chunks = total
        if index < 0 or index >= total:
            return
        if index in self.chunks:
            return
        self.chunks[index] = payload

    def has_message(self) -> bool:
        if self.total_chunks is None:
            return False
        return len(self.chunks) >= self.total_chunks

    def message(self) -> bytes | None:
        if not self.has_message() or self.total_chunks is None:
            return None
        rebuilt = b"".join(self.chunks.get(i, b"") for i in range(self.total_chunks))
        return rebuilt[: self.message_size]

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_size": self.message_size,
            "chunks": [{"index": idx, "payload": value.hex()} for idx, value in self.chunks.items()],
            "total_chunks": self.total_chunks,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecoderState":
        message_size = int(payload.get("message_size", 0)) if isinstance(payload.get("message_size"), int) else 0
        decoder = cls(message_size=message_size)
        total_chunks = payload.get("total_chunks")
        if isinstance(total_chunks, int):
            decoder.total_chunks = total_chunks
        raw_chunks = payload.get("chunks", [])
        if isinstance(raw_chunks, list):
            for entry in raw_chunks:
                if not isinstance(entry, dict):
                    continue
                idx = entry.get("index")
                payload_hex = entry.get("payload")
                if not isinstance(idx, int) or not isinstance(payload_hex, str):
                    continue
                try:
                    decoder.chunks[idx] = bytes.fromhex(payload_hex)
                except ValueError:
                    continue
        return decoder


@dataclass
class BraidProtocolState:
    node: Any


@dataclass
class KdfChainState:
    CK: bytes
    N: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "CK": self.CK.hex(),
            "N": self.N,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KdfChainState":
        ck = _spqr_decode_bytes(payload.get("CK")) or b""
        n = int(payload.get("N", 0)) if isinstance(payload.get("N"), int) else 0
        return cls(CK=ck, N=n)


@dataclass
class EpochKdfChains:
    send: KdfChainState | None
    receive: KdfChainState | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "send": None if self.send is None else self.send.to_dict(),
            "receive": None if self.receive is None else self.receive.to_dict(),
        }


@dataclass
class SpqrHeader:
    msg: SpqrSckaMessage
    n: int


Direction = Literal["A2B", "B2A"]


@dataclass
class SpqrRatchetState:
    RK: bytes
    epoch: int
    kdfchains: dict[int, EpochKdfChains]
    MKSKIPPED: dict[int, dict[int, bytes]] = field(default_factory=dict)
    direction: Direction = "A2B"
    scka_state: BraidProtocolState | None = None


@dataclass
class SckaSendResult:
    msg: SpqrSckaMessage
    sending_epoch: int
    output_key: SckaOutputKey | None
    raw_ss: bytes | None = None


@dataclass
class SckaReceiveResult:
    receiving_epoch: int
    output_key: SckaOutputKey | None


@dataclass
class SpqrMessageState:
    sender: str
    receiver: str
    header: SpqrHeader | None = None
    cipher: bytes = b""
    plaintext: bytes = b""
    decrypted_by_receiver: bytes = b""
    seq_id: int = 0


@dataclass
class SpqrSessionState:
    alice: SpqrRatchetState | None = None
    bob: SpqrRatchetState | None = None
    message_log: list[SpqrMessageState] = field(default_factory=list)
