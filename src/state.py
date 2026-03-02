from dataclasses import dataclass, field
from typing import Literal
from modules.party_state import PartyState
from modules.message_state import MessageState


Perspective = Literal["global", "alice", "bob", "attacker"]


@dataclass
class AppState:
    current_module: str = "double_ratchet"
    current_step: int = 0
    perspective: Perspective = "global"


@dataclass
class DoubleRatchetState:
    alice: PartyState = field(default_factory=lambda: PartyState("Alice"))
    bob: PartyState = field(default_factory=lambda: PartyState("Bob"))
    message_log: list[MessageState] = field(default_factory=list)
