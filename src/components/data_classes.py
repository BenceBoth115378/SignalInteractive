from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

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
