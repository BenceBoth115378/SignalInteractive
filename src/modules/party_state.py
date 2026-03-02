from dataclasses import dataclass


@dataclass
class PartyState:
    name: str
    dh_private: str = ""
    dh_public: str = ""
    root_key: str = "RK0"
    sending_chain: str = ""
    receiving_chain: str = ""
