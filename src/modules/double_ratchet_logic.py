from components.state import DoubleRatchetState
from modules.message_state import MessageState


def fake_kdf(*inputs: str) -> str:
    return "KDF(" + "+".join(inputs) + ")"


def fake_dh(priv: str, pub: str) -> str:
    return f"DH({priv[:3]}x{pub[:3]})"


def derive_message_key(chain_key: str) -> tuple[str, str]:
    mk = f"MK({chain_key})"
    next_ck = f"CK({chain_key})"
    return mk, next_ck


def initialize_session(session: DoubleRatchetState) -> None:
    alice = session.initializer
    bob = session.responder

    alice.dh_private = "A0_priv"
    alice.dh_public = "A0_pub"
    bob.dh_private = "B0_priv"
    bob.dh_public = "B0_pub"

    alice.root_key = "RK0"
    bob.root_key = "RK0"

    alice.sending_chain = "CK_A0"
    alice.receiving_chain = "CK_A0"
    bob.sending_chain = "CK_A0"
    bob.receiving_chain = "CK_A0"


def alice_sends(session: DoubleRatchetState) -> None:
    alice = session.initializer
    mk, next_ck = derive_message_key(alice.sending_chain)

    session.message_log.append(
        MessageState(
            sender="Alice",
            receiver="Bob",
            message_key=mk,
            cipher=f"ENC({mk})",
        )
    )
    alice.sending_chain = next_ck


def bob_receives(session: DoubleRatchetState) -> None:
    if not session.message_log:
        return

    bob = session.responder
    msg = session.message_log[-1]
    mk, next_ck = derive_message_key(bob.receiving_chain)

    msg.decrypted_by_bob = mk
    bob.receiving_chain = next_ck


def bob_sends_with_dh_ratchet(session: DoubleRatchetState) -> None:
    alice = session.initializer
    bob = session.responder

    bob.dh_private = "B1_priv"
    bob.dh_public = "B1_pub"

    dh_result = fake_dh(bob.dh_private, alice.dh_public)
    new_root = fake_kdf(bob.root_key, dh_result)

    bob.root_key = new_root
    alice.root_key = new_root

    bob.sending_chain = "CK_B1"
    alice.receiving_chain = "CK_B1"

    mk, next_ck = derive_message_key(bob.sending_chain)
    session.message_log.append(
        MessageState(
            sender="Bob",
            receiver="Alice",
            message_key=mk,
            cipher=f"ENC({mk})",
        )
    )
    bob.sending_chain = next_ck


def alice_receives_dh(session: DoubleRatchetState) -> None:
    if not session.message_log:
        return

    alice = session.initializer
    msg = session.message_log[-1]
    mk, next_ck = derive_message_key(alice.receiving_chain)

    msg.decrypted_by_alice = mk
    alice.receiving_chain = next_ck
