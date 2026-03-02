from dataclasses import dataclass


@dataclass
class MessageState:
    sender: str
    receiver: str
    message_key: str
    cipher: str
    decrypted_by_bob: str = ""
    decrypted_by_alice: str = ""
