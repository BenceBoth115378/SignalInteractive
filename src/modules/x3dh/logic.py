from __future__ import annotations

from components.data_classes import X3DHState
from modules import external as ext


def _generate_dh_key_pair() -> dict[str, str]:
    pair = ext.GENERATE_DH()
    return {
        "private": pair.private,
        "public": pair.public,
    }


def _ensure_server_state(state: X3DHState) -> dict:
    if not isinstance(state.server_state, dict):
        state.server_state = {}

    defaults = {
        "alice_bundle": None,
        "alice_available_opk_ids": [],
        "alice_opk_public_by_id": {},
        "bob_bundle": None,
        "bob_available_opk_ids": [],
        "bob_opk_public_by_id": {},
    }
    for key, value in defaults.items():
        if key not in state.server_state:
            state.server_state[key] = value.copy() if isinstance(value, list | dict) else value

    return state.server_state


def add_event(state: X3DHState, message: str) -> None:
    state.events.append(message)


def ensure_alice_local(state: X3DHState) -> dict:
    alice = state.alice_local
    if not isinstance(alice, dict):
        raise ValueError("Alice must generate keys first.")
    return alice


def ensure_bob_local(state: X3DHState) -> dict:
    bob = state.bob_local
    if not isinstance(bob, dict):
        raise ValueError("Bob local state is missing.")
    return bob


def bootstrap_bob_to_server(state: X3DHState) -> None:
    server_state = _ensure_server_state(state)

    bob_identity = _generate_dh_key_pair()
    bob_signed_prekey = _generate_dh_key_pair()
    identity_signing_public = ext.IDENTITY_SIGNING_PUBLIC_FROM_DH_PRIVATE(bob_identity["private"])
    signature = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(bob_identity["private"], bytes.fromhex(bob_signed_prekey["public"]))

    opk_private_by_id: dict[str, dict[str, str]] = {}
    opk_public_by_id: dict[str, str] = {}
    for idx in range(1, 6):
        kp = _generate_dh_key_pair()
        opk_private_by_id[str(idx)] = kp
        opk_public_by_id[str(idx)] = kp["public"]

    state.bob_local = {
        "name": "Bob",
        "identity_dh": bob_identity,
        "identity_signing_public": identity_signing_public,
        "signed_prekey": bob_signed_prekey,
        "signed_prekey_signature": signature,
        "opk_private_by_id": opk_private_by_id,
        "opk_public_by_id": opk_public_by_id,
        "next_opk_id": 6,
    }

    server_state["bob_bundle"] = {
        "identity_dh_public": bob_identity["public"],
        "identity_signing_public": identity_signing_public,
        "signed_prekey_public": bob_signed_prekey["public"],
        "signed_prekey_signature": signature,
    }
    server_state["bob_available_opk_ids"] = [1, 2, 3, 4, 5]
    server_state["bob_opk_public_by_id"] = opk_public_by_id.copy()
    state.events.append("Server bootstrapped with Bob prekey bundle and OPKs.")


def new_state() -> X3DHState:
    state = X3DHState(
        server_state={
            "alice_bundle": None,
            "alice_available_opk_ids": [],
            "alice_opk_public_by_id": {},
            "bob_bundle": None,
            "bob_available_opk_ids": [],
            "bob_opk_public_by_id": {},
        }
    )
    bootstrap_bob_to_server(state)
    state.events.append(
        "Flow: registration (Alice/Server) -> request Bob bundle -> derive SK/AD -> send initial message -> Bob verifies AD and derives SK."
    )
    return state


def generate_alice_registration_material(state: X3DHState) -> None:
    identity = _generate_dh_key_pair()
    signed_prekey = _generate_dh_key_pair()
    identity_signing_public = ext.IDENTITY_SIGNING_PUBLIC_FROM_DH_PRIVATE(identity["private"])
    signature = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(identity["private"], bytes.fromhex(signed_prekey["public"]))

    opk_private_by_id: dict[str, dict[str, str]] = {}
    opk_public_by_id: dict[str, str] = {}
    for idx in range(1, 6):
        kp = _generate_dh_key_pair()
        opk_private_by_id[str(idx)] = kp
        opk_public_by_id[str(idx)] = kp["public"]

    state.alice_local = {
        "name": "Alice",
        "identity_dh": identity,
        "identity_signing_public": identity_signing_public,
        "signed_prekey": signed_prekey,
        "signed_prekey_signature": signature,
        "opk_private_by_id": opk_private_by_id,
        "opk_public_by_id": opk_public_by_id,
        "next_opk_id": 6,
        "ephemeral_key": None,
    }
    state.alice_generated = True
    state.phase2_signature_verified = False
    state.phase2_ek_generated = False
    state.last_bundle_for_alice = None
    state.alice_derived = None
    state.initial_message = None
    state.bob_receive_result = None
    add_event(state, "Alice generated IK, SPK(sign), and OPKs.")


def upload_alice_initial_bundle(state: X3DHState) -> None:
    alice = ensure_alice_local(state)
    server_state = _ensure_server_state(state)
    server_state["alice_bundle"] = {
        "identity_dh_public": alice["identity_dh"]["public"],
        "identity_signing_public": alice["identity_signing_public"],
        "signed_prekey_public": alice["signed_prekey"]["public"],
        "signed_prekey_signature": alice["signed_prekey_signature"],
    }

    opk_map = {k: v for k, v in alice["opk_public_by_id"].items()}
    server_state["alice_opk_public_by_id"] = opk_map
    server_state["alice_available_opk_ids"] = sorted(int(k) for k in opk_map.keys())
    add_event(state, "Alice uploaded initial prekey bundle and OPKs to Server.")


def server_sends_alice_opk_to_requester(state: X3DHState) -> None:
    server_state = _ensure_server_state(state)
    available = server_state.get("alice_available_opk_ids", [])
    if not available:
        add_event(state, "Server could not send Alice OPK to requester because none are available.")
        raise ValueError("No Alice's OPK is currently available on server.")

    opk_id = available.pop(0)
    server_state["alice_opk_public_by_id"].pop(str(opk_id), None)
    add_event(state, f"Server sent Alice OPK id={opk_id} to a requester.")

    remaining_opks = len(server_state.get("alice_available_opk_ids", []))
    if remaining_opks < 3:
        state.alice_needs_to_upload_opk = True


def server_sends_bob_opk_to_requester(state: X3DHState) -> None:
    server_state = _ensure_server_state(state)
    available = server_state.get("bob_available_opk_ids", [])
    if not available:
        add_event(state, "Server could not send Bob OPK to requester because none are available.")
        raise ValueError("No Bob's OPK is currently available on server.")

    opk_id = available.pop(0)
    server_state["bob_opk_public_by_id"].pop(str(opk_id), None)
    add_event(state, f"Server sent Bob OPK id={opk_id} to a requester.")


def alice_uploads_new_opk(state: X3DHState) -> None:
    alice = ensure_alice_local(state)
    server_state = _ensure_server_state(state)

    new_id = int(alice["next_opk_id"])
    new_opk = _generate_dh_key_pair()
    alice["next_opk_id"] = new_id + 1
    alice["opk_private_by_id"][str(new_id)] = new_opk
    alice["opk_public_by_id"][str(new_id)] = new_opk["public"]

    server_state["alice_opk_public_by_id"][str(new_id)] = new_opk["public"]
    server_state.setdefault("alice_available_opk_ids", []).append(new_id)
    server_state["alice_available_opk_ids"] = sorted(server_state["alice_available_opk_ids"])
    add_event(state, f"Alice uploaded fresh OPK id={new_id}.")

    current_count = len(server_state.get("alice_available_opk_ids", []))
    if current_count >= 3:
        state.alice_needs_to_upload_opk = False


def alice_rotates_signed_prekey_bundle(state: X3DHState) -> None:
    alice = ensure_alice_local(state)
    server_state = _ensure_server_state(state)

    new_spk = _generate_dh_key_pair()
    new_signature = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(alice["identity_dh"]["private"], bytes.fromhex(new_spk["public"]))
    alice["signed_prekey"] = new_spk
    alice["signed_prekey_signature"] = new_signature

    if not isinstance(server_state.get("alice_bundle"), dict):
        raise ValueError("Upload Alice initial bundle first.")

    server_state["alice_bundle"] = {
        "identity_dh_public": alice["identity_dh"]["public"],
        "identity_signing_public": alice["identity_signing_public"],
        "signed_prekey_public": new_spk["public"],
        "signed_prekey_signature": new_signature,
    }
    add_event(state, "Alice uploaded a new signed prekey bundle.")


def request_bob_bundle_for_alice(state: X3DHState) -> None:
    server = _ensure_server_state(state)
    bob_bundle = server.get("bob_bundle")
    if not isinstance(bob_bundle, dict):
        raise ValueError("Server has no Bob bundle.")

    opk_id: int | None = None
    opk_public: str | None = None

    available = server.get("bob_available_opk_ids", [])
    if available:
        opk_id = int(available.pop(0))
        opk_public = server.get("bob_opk_public_by_id", {}).pop(str(opk_id), None)

    state.last_bundle_for_alice = {
        "identity_dh_public": bob_bundle["identity_dh_public"],
        "identity_signing_public": bob_bundle["identity_signing_public"],
        "signed_prekey_public": bob_bundle["signed_prekey_public"],
        "signed_prekey_signature": bob_bundle["signed_prekey_signature"],
        "opk_id": opk_id,
        "opk_public": opk_public,
    }

    suffix = "with OPK" if opk_public else "without OPK"
    state.phase2_signature_verified = False
    state.phase2_ek_generated = False
    state.alice_derived = None
    state.initial_message = None
    state.bob_receive_result = None
    add_event(state, f"Alice requested Bob bundle ({suffix}).")


def alice_verifies_bundle_signature(state: X3DHState) -> None:
    bundle = state.last_bundle_for_alice
    if not isinstance(bundle, dict):
        raise ValueError("Alice must request Bob prekey bundle first.")

    ok = ext.VERIFY_WITH_IDENTITY_SIGNING_PUBLIC(
        bundle["identity_signing_public"],
        bytes.fromhex(bundle["signed_prekey_public"]),
        bundle["signed_prekey_signature"],
    )
    if not ok:
        raise ValueError("Bob signed prekey signature verification failed.")

    state.phase2_signature_verified = True
    add_event(state, "Alice verified Bob signed-prekey signature.")


def alice_generates_ek_and_derives_sk(state: X3DHState) -> None:
    if not state.phase2_signature_verified:
        raise ValueError("Verify bundle signature before deriving SK.")

    alice = ensure_alice_local(state)
    bundle = state.last_bundle_for_alice
    if not isinstance(bundle, dict):
        raise ValueError("Alice must request Bob prekey bundle first.")

    ek = _generate_dh_key_pair()
    alice["ephemeral_key"] = ek

    dh_outputs = [
        ext.DH(alice["identity_dh"], bundle["signed_prekey_public"]),
        ext.DH(ek, bundle["identity_dh_public"]),
        ext.DH(ek, bundle["signed_prekey_public"]),
    ]

    if bundle.get("opk_public"):
        dh_outputs.append(ext.DH(ek, bundle["opk_public"]))

    sk = ext.KDF_SK(dh_outputs)

    state.alice_derived = {
        "shared_secret": sk.hex(),
        "dh_count": len(dh_outputs),
        "associated_data": None,
        "ek_public": ek["public"],
        "ek_private": ek["private"],
    }
    state.phase2_ek_generated = True
    add_event(state, f"Alice derived SK with {len(dh_outputs)} DH operation(s).")


def alice_calculates_associated_data(state: X3DHState) -> None:
    alice = ensure_alice_local(state)
    derived = state.alice_derived
    bundle = state.last_bundle_for_alice
    if not isinstance(derived, dict) or not isinstance(bundle, dict):
        raise ValueError("Derive SK first.")

    associated_data = ext.CALC_AD(
        initiator_identity_public=alice["identity_dh"]["public"],
        responder_identity_public=bundle["identity_dh_public"],
        responder_signed_prekey_public=bundle["signed_prekey_public"],
        initiator_ephemeral_public=derived["ek_public"],
        responder_opk_id=bundle.get("opk_id"),
    )

    derived["associated_data"] = associated_data
    add_event(state, "Alice calculated Associated Data (AD).")


def alice_sends_initial_message(state: X3DHState, plaintext: str) -> None:
    alice = ensure_alice_local(state)
    derived = state.alice_derived
    bundle = state.last_bundle_for_alice
    if not isinstance(derived, dict) or not isinstance(bundle, dict):
        raise ValueError("Complete phase 2 before sending the initial message.")

    shared_secret = derived.get("shared_secret")
    associated_data = derived.get("associated_data")
    if not isinstance(shared_secret, str) or not isinstance(associated_data, str):
        raise ValueError("SK and AD must be available before sending.")

    text = plaintext.strip() or "Hello Bob from Alice using X3DH"
    ciphertext = ext.ENCRYPT(
        bytes.fromhex(shared_secret),
        text.encode("utf-8"),
        bytes.fromhex(associated_data),
    ).hex()

    state.initial_message = {
        "from": "Alice",
        "to": "Bob",
        "ik_a_public": alice["identity_dh"]["public"],
        "ek_a_public": derived["ek_public"],
        "bob_spk_public": bundle["signed_prekey_public"],
        "bob_opk_id": bundle.get("opk_id"),
        "associated_data": associated_data,
        "ciphertext": ciphertext,
        "plaintext_preview": text,
    }

    state.bob_receive_result = None
    add_event(state, "Alice sent initial X3DH message to Bob.")


def bob_receives_and_verifies(state: X3DHState) -> None:
    bob = ensure_bob_local(state)
    msg = state.initial_message
    if not isinstance(msg, dict):
        raise ValueError("No initial message to process.")

    dh_values = [
        ext.DH(bob["signed_prekey"], msg["ik_a_public"]),
        ext.DH(bob["identity_dh"], msg["ek_a_public"]),
        ext.DH(bob["signed_prekey"], msg["ek_a_public"]),
    ]

    opk_id = msg.get("bob_opk_id")
    if opk_id is not None:
        opk_private_entry = bob.get("opk_private_by_id", {}).pop(str(opk_id), None)
        if not isinstance(opk_private_entry, dict):
            raise ValueError("Expected Bob OPK was already consumed or missing.")
        dh_values.append(ext.DH(opk_private_entry, msg["ek_a_public"]))

    bob_sk = ext.KDF_SK(dh_values)
    bob_associated_data = ext.CALC_AD(
        initiator_identity_public=msg["ik_a_public"],
        responder_identity_public=bob["identity_dh"]["public"],
        responder_signed_prekey_public=bob["signed_prekey"]["public"],
        initiator_ephemeral_public=msg["ek_a_public"],
        responder_opk_id=opk_id,
    )

    received_associated_data = msg.get("associated_data")
    ad_matches = bob_associated_data == received_associated_data

    decrypted_text = ""
    decrypt_ok = False
    if ad_matches:
        try:
            decrypted_text = ext.DECRYPT(
                bob_sk,
                bytes.fromhex(msg["ciphertext"]),
                bytes.fromhex(bob_associated_data),
            ).decode("utf-8", errors="replace")
            decrypt_ok = True
        except Exception as exc:
            decrypted_text = f"Decryption failed: {exc}"

    alice_derived = state.alice_derived
    shared_secret_match = False
    if isinstance(alice_derived, dict):
        shared_secret_match = alice_derived.get("shared_secret") == bob_sk.hex()

    state.bob_receive_result = {
        "ad_local": bob_associated_data,
        "ad_received": received_associated_data,
        "ad_matches": ad_matches,
        "bob_shared_secret": bob_sk.hex(),
        "shared_secret_matches": shared_secret_match,
        "decryption_ok": decrypt_ok,
        "decrypted_text": decrypted_text,
        "dh_count": len(dh_values),
    }

    if ad_matches and shared_secret_match:
        add_event(state, "Bob verified AD and derived the same shared secret.")
    else:
        add_event(state, "Bob processed message but AD or shared secret mismatch occurred.")


def is_phase1_done(state: X3DHState) -> bool:
    return isinstance(state.server_state.get("alice_bundle"), dict)


def is_phase2_done(state: X3DHState) -> bool:
    derived = state.alice_derived
    return isinstance(derived, dict) and isinstance(derived.get("associated_data"), str)
