from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Perspective = Literal["global", "alice", "bob", "attacker"]


@dataclass
class AppState:
    current_module: str = "double_ratchet"
    perspective: Perspective = "global"


@dataclass
class DoubleRatchetState:
    initializer: PartyState = field(default_factory=lambda: PartyState("Alice"))
    responder: PartyState = field(default_factory=lambda: PartyState("Bob"))
    message_log: list[MessageState] = field(default_factory=list)


@dataclass
class DHKeyPair:
    private: str
    public: str


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
