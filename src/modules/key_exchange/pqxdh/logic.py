from __future__ import annotations

from components.data_classes import PQXDHState
from modules import external as ext


def _generate_dh_key_pair() -> dict[str, str]:
    pair = ext.GENERATE_DH()
    return {
        "private": pair.private,
        "public": pair.public,
    }


def _generate_pq_key_pair() -> dict[str, str]:
    return ext.GENERATE_PQKEM_KEYPAIR()


def _ensure_server_state(state: PQXDHState) -> dict:
    if not isinstance(state.server_state, dict):
        state.server_state = {}

    defaults = {
        "alice_bundle": None,
        "alice_available_opk_ids": [],
        "alice_opk_public_by_id": {},
        "alice_pq_available_opk_ids": [],
        "alice_pq_opk_public_by_id": {},
        "alice_pq_opk_signature_by_id": {},
        "bob_bundle": None,
        "bob_available_opk_ids": [],
        "bob_opk_public_by_id": {},
        "bob_pq_available_opk_ids": [],
        "bob_pq_opk_public_by_id": {},
        "bob_pq_opk_signature_by_id": {},
    }
    for key, value in defaults.items():
        if key not in state.server_state:
            state.server_state[key] = value.copy() if isinstance(value, list | dict) else value

    return state.server_state


def add_event(state: PQXDHState, message: str) -> None:
    state.events.append(message)


def _update_alice_upload_opk_flag(state: PQXDHState, server_state: dict) -> None:
    remaining_min = min(
        len(server_state.get("alice_available_opk_ids", [])),
        len(server_state.get("alice_pq_available_opk_ids", [])),
    )
    state.alice_needs_to_upload_opk = remaining_min < 3


def ensure_alice_local(state: PQXDHState) -> dict:
    alice = state.alice_local
    if not isinstance(alice, dict):
        raise ValueError("Alice must generate keys first.")
    return alice


def ensure_bob_local(state: PQXDHState) -> dict:
    bob = state.bob_local
    if not isinstance(bob, dict):
        raise ValueError("Bob local state is missing.")
    return bob


def bootstrap_bob_to_server(state: PQXDHState) -> None:
    server_state = _ensure_server_state(state)

    bob_identity = _generate_dh_key_pair()
    bob_signed_prekey = _generate_dh_key_pair()
    bob_pq_signed_prekey = _generate_pq_key_pair()

    signature_ec = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(
        bob_identity["private"],
        bytes.fromhex(bob_signed_prekey["public"]),
    )
    signature_pq = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(
        bob_identity["private"],
        bytes.fromhex(bob_pq_signed_prekey["public"]),
    )

    opk_private_by_id: dict[str, dict[str, str]] = {}
    opk_public_by_id: dict[str, str] = {}
    pq_opk_private_by_id: dict[str, dict[str, str]] = {}
    pq_opk_public_by_id: dict[str, str] = {}
    pq_opk_signature_by_id: dict[str, str] = {}

    for idx in range(1, 6):
        ec_kp = _generate_dh_key_pair()
        pq_kp = _generate_pq_key_pair()
        opk_private_by_id[str(idx)] = ec_kp
        opk_public_by_id[str(idx)] = ec_kp["public"]
        pq_opk_private_by_id[str(idx)] = pq_kp
        pq_opk_public_by_id[str(idx)] = pq_kp["public"]
        pq_opk_signature_by_id[str(idx)] = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(
            bob_identity["private"],
            bytes.fromhex(pq_kp["public"]),
        )

    state.bob_local = {
        "name": "Bob",
        "identity_dh": bob_identity,
        "signed_prekey": bob_signed_prekey,
        "signed_prekey_signature": signature_ec,
        "pq_signed_prekey": bob_pq_signed_prekey,
        "pq_signed_prekey_signature": signature_pq,
        "opk_private_by_id": opk_private_by_id,
        "opk_public_by_id": opk_public_by_id,
        "pq_opk_private_by_id": pq_opk_private_by_id,
        "pq_opk_public_by_id": pq_opk_public_by_id,
        "pq_opk_signature_by_id": pq_opk_signature_by_id,
        "next_opk_id": 6,
    }

    server_state["bob_bundle"] = {
        "identity_dh_public": bob_identity["public"],
        "signed_prekey_public": bob_signed_prekey["public"],
        "signed_prekey_signature": signature_ec,
        "pq_signed_prekey_public": bob_pq_signed_prekey["public"],
        "pq_signed_prekey_signature": signature_pq,
    }
    server_state["bob_available_opk_ids"] = [1, 2, 3, 4, 5]
    server_state["bob_opk_public_by_id"] = opk_public_by_id.copy()
    server_state["bob_pq_available_opk_ids"] = [1, 2, 3, 4, 5]
    server_state["bob_pq_opk_public_by_id"] = pq_opk_public_by_id.copy()
    server_state["bob_pq_opk_signature_by_id"] = pq_opk_signature_by_id.copy()
    state.events.append("Server bootstrapped with Bob PQXDH prekey bundle, EC OPKs, and PQOPKs.")


def new_state() -> PQXDHState:
    state = PQXDHState(
        server_state={
            "alice_bundle": None,
            "alice_available_opk_ids": [],
            "alice_opk_public_by_id": {},
            "alice_pq_available_opk_ids": [],
            "alice_pq_opk_public_by_id": {},
            "bob_bundle": None,
            "bob_available_opk_ids": [],
            "bob_opk_public_by_id": {},
            "bob_pq_available_opk_ids": [],
            "bob_pq_opk_public_by_id": {},
            "bob_pq_opk_signature_by_id": {},
        }
    )
    bootstrap_bob_to_server(state)
    state.events.append(
        "Flow: registration (Alice/Server) -> request Bob bundle -> verify signatures -> derive SK/AD (DH + PQKEM) -> send initial message -> Bob verifies AD and derives SK."
    )
    return state


def generate_alice_registration_material(state: PQXDHState) -> None:
    identity = _generate_dh_key_pair()
    signed_prekey = _generate_dh_key_pair()
    pq_signed_prekey = _generate_pq_key_pair()

    signature_ec = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(identity["private"], bytes.fromhex(signed_prekey["public"]))
    signature_pq = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(identity["private"], bytes.fromhex(pq_signed_prekey["public"]))

    opk_private_by_id: dict[str, dict[str, str]] = {}
    opk_public_by_id: dict[str, str] = {}
    pq_opk_private_by_id: dict[str, dict[str, str]] = {}
    pq_opk_public_by_id: dict[str, str] = {}
    pq_opk_signature_by_id: dict[str, str] = {}

    for idx in range(1, 6):
        ec_kp = _generate_dh_key_pair()
        pq_kp = _generate_pq_key_pair()
        opk_private_by_id[str(idx)] = ec_kp
        opk_public_by_id[str(idx)] = ec_kp["public"]
        pq_opk_private_by_id[str(idx)] = pq_kp
        pq_opk_public_by_id[str(idx)] = pq_kp["public"]
        pq_opk_signature_by_id[str(idx)] = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(
            identity["private"],
            bytes.fromhex(pq_kp["public"]),
        )

    state.alice_local = {
        "name": "Alice",
        "identity_dh": identity,
        "signed_prekey": signed_prekey,
        "signed_prekey_signature": signature_ec,
        "pq_signed_prekey": pq_signed_prekey,
        "pq_signed_prekey_signature": signature_pq,
        "opk_private_by_id": opk_private_by_id,
        "opk_public_by_id": opk_public_by_id,
        "pq_opk_private_by_id": pq_opk_private_by_id,
        "pq_opk_public_by_id": pq_opk_public_by_id,
        "pq_opk_signature_by_id": pq_opk_signature_by_id,
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
    add_event(state, "Alice generated IK, SPK(sign), PQSPK(sign), OPKs, and PQOPKs.")


def upload_alice_initial_bundle(state: PQXDHState) -> None:
    alice = ensure_alice_local(state)
    server_state = _ensure_server_state(state)

    server_state["alice_bundle"] = {
        "identity_dh_public": alice["identity_dh"]["public"],
        "signed_prekey_public": alice["signed_prekey"]["public"],
        "signed_prekey_signature": alice["signed_prekey_signature"],
        "pq_signed_prekey_public": alice["pq_signed_prekey"]["public"],
        "pq_signed_prekey_signature": alice["pq_signed_prekey_signature"],
    }

    ec_opk_map = {k: v for k, v in alice["opk_public_by_id"].items()}
    pq_opk_map = {k: v for k, v in alice["pq_opk_public_by_id"].items()}
    pq_opk_signature_map = {k: v for k, v in alice.get("pq_opk_signature_by_id", {}).items()} if isinstance(alice.get("pq_opk_signature_by_id"), dict) else {}

    server_state["alice_opk_public_by_id"] = ec_opk_map
    server_state["alice_available_opk_ids"] = sorted(int(k) for k in ec_opk_map.keys())
    server_state["alice_pq_opk_public_by_id"] = pq_opk_map
    server_state["alice_pq_available_opk_ids"] = sorted(int(k) for k in pq_opk_map.keys())
    server_state["alice_pq_opk_signature_by_id"] = pq_opk_signature_map

    add_event(state, "Alice uploaded initial PQXDH prekey bundle, OPKs, and PQOPKs to Server.")


def server_sends_alice_ec_opk_to_requester(state: PQXDHState) -> None:
    server_state = _ensure_server_state(state)
    ec_available = server_state.get("alice_available_opk_ids", [])

    if not ec_available:
        add_event(state, "Server could not send Alice EC OPK to requester because none are available.")
        raise ValueError("No Alice EC OPK is currently available on server.")

    ec_id = ec_available.pop(0)
    server_state["alice_opk_public_by_id"].pop(str(ec_id), None)
    add_event(state, f"Server sent Alice EC OPK id={ec_id} to a requester.")

    _update_alice_upload_opk_flag(state, server_state)


def server_sends_alice_pqopk_to_requester(state: PQXDHState) -> None:
    server_state = _ensure_server_state(state)
    pq_available = server_state.get("alice_pq_available_opk_ids", [])

    if not pq_available:
        add_event(state, "Server could not send Alice PQOPK to requester because none are available.")
        raise ValueError("No Alice PQOPK is currently available on server.")

    pq_id = pq_available.pop(0)
    server_state["alice_pq_opk_public_by_id"].pop(str(pq_id), None)
    add_event(state, f"Server sent Alice PQOPK id={pq_id} to a requester.")

    _update_alice_upload_opk_flag(state, server_state)


def server_sends_bob_ec_opk_to_requester(state: PQXDHState) -> None:
    server_state = _ensure_server_state(state)
    ec_available = server_state.get("bob_available_opk_ids", [])

    if not ec_available:
        add_event(state, "Server could not send Bob EC OPK to requester because none are available.")
        raise ValueError("No Bob EC OPK is currently available on server.")

    ec_id = ec_available.pop(0)
    server_state["bob_opk_public_by_id"].pop(str(ec_id), None)
    add_event(state, f"Server sent Bob EC OPK id={ec_id} to a requester.")


def server_sends_bob_pqopk_to_requester(state: PQXDHState) -> None:
    server_state = _ensure_server_state(state)
    pq_available = server_state.get("bob_pq_available_opk_ids", [])

    if not pq_available:
        add_event(state, "Server could not send Bob PQOPK to requester because none are available.")
        raise ValueError("No Bob PQOPK is currently available on server.")

    pq_id = pq_available.pop(0)
    server_state["bob_pq_opk_public_by_id"].pop(str(pq_id), None)
    add_event(state, f"Server sent Bob PQOPK id={pq_id} to a requester.")


def alice_uploads_new_opk(state: PQXDHState) -> None:
    alice = ensure_alice_local(state)
    server_state = _ensure_server_state(state)

    new_id = int(alice["next_opk_id"])
    ec_opk = _generate_dh_key_pair()
    pq_opk = _generate_pq_key_pair()
    pq_opk_signature = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(
        alice["identity_dh"]["private"],
        bytes.fromhex(pq_opk["public"]),
    )

    alice["next_opk_id"] = new_id + 1
    alice["opk_private_by_id"][str(new_id)] = ec_opk
    alice["opk_public_by_id"][str(new_id)] = ec_opk["public"]
    alice["pq_opk_private_by_id"][str(new_id)] = pq_opk
    alice["pq_opk_public_by_id"][str(new_id)] = pq_opk["public"]
    alice.setdefault("pq_opk_signature_by_id", {})[str(new_id)] = pq_opk_signature

    server_state["alice_opk_public_by_id"][str(new_id)] = ec_opk["public"]
    server_state.setdefault("alice_available_opk_ids", []).append(new_id)
    server_state["alice_available_opk_ids"] = sorted(server_state["alice_available_opk_ids"])

    server_state["alice_pq_opk_public_by_id"][str(new_id)] = pq_opk["public"]
    server_state.setdefault("alice_pq_available_opk_ids", []).append(new_id)
    server_state["alice_pq_available_opk_ids"] = sorted(server_state["alice_pq_available_opk_ids"])
    server_state.setdefault("alice_pq_opk_signature_by_id", {})[str(new_id)] = pq_opk_signature

    add_event(state, f"Alice uploaded fresh EC OPK and PQOPK id={new_id}.")

    current_min = min(
        len(server_state.get("alice_available_opk_ids", [])),
        len(server_state.get("alice_pq_available_opk_ids", [])),
    )
    if current_min >= 3:
        state.alice_needs_to_upload_opk = False


def alice_rotates_signed_prekey_bundle(state: PQXDHState) -> None:
    alice = ensure_alice_local(state)
    server_state = _ensure_server_state(state)

    new_spk = _generate_dh_key_pair()
    new_pq_spk = _generate_pq_key_pair()

    new_signature_ec = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(alice["identity_dh"]["private"], bytes.fromhex(new_spk["public"]))
    new_signature_pq = ext.SIGN_WITH_IDENTITY_DH_PRIVATE(alice["identity_dh"]["private"], bytes.fromhex(new_pq_spk["public"]))

    alice["signed_prekey"] = new_spk
    alice["signed_prekey_signature"] = new_signature_ec
    alice["pq_signed_prekey"] = new_pq_spk
    alice["pq_signed_prekey_signature"] = new_signature_pq

    if not isinstance(server_state.get("alice_bundle"), dict):
        raise ValueError("Upload Alice initial bundle first.")

    server_state["alice_bundle"] = {
        "identity_dh_public": alice["identity_dh"]["public"],
        "signed_prekey_public": new_spk["public"],
        "signed_prekey_signature": new_signature_ec,
        "pq_signed_prekey_public": new_pq_spk["public"],
        "pq_signed_prekey_signature": new_signature_pq,
    }

    add_event(state, "Alice uploaded a new EC+PQ signed prekey bundle.")


def request_bob_bundle_for_alice(state: PQXDHState) -> None:
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

    pq_opk_id: int | None = None
    pq_opk_public: str | None = None
    pq_opk_signature: str | None = None

    pq_available = server.get("bob_pq_available_opk_ids", [])
    if pq_available:
        pq_opk_id = int(pq_available.pop(0))
        pq_opk_public = server.get("bob_pq_opk_public_by_id", {}).pop(str(pq_opk_id), None)
        pq_opk_signature = server.get("bob_pq_opk_signature_by_id", {}).pop(str(pq_opk_id), None)

    selected_pq_public = pq_opk_public or bob_bundle.get("pq_signed_prekey_public")
    selected_pq_signature = pq_opk_signature or bob_bundle.get("pq_signed_prekey_signature")
    pq_prekey_source = "pqopk" if pq_opk_public is not None else "pqspk"

    state.last_bundle_for_alice = {
        "identity_dh_public": bob_bundle["identity_dh_public"],
        "signed_prekey_public": bob_bundle["signed_prekey_public"],
        "signed_prekey_signature": bob_bundle["signed_prekey_signature"],
        "opk_id": opk_id,
        "opk_public": opk_public,
        "pq_signed_prekey_public": bob_bundle["pq_signed_prekey_public"],
        "pq_signed_prekey_signature": bob_bundle["pq_signed_prekey_signature"],
        "pq_opk_id": pq_opk_id,
        "pq_opk_public": pq_opk_public,
        "pq_opk_signature": pq_opk_signature,
        "pq_pkb_id": pq_opk_id if pq_opk_id is not None else "last-resort",
        "pq_pkb_public": selected_pq_public,
        "pq_pkb_signature": selected_pq_signature,
        "pq_prekey_id": pq_opk_id,
        "pq_prekey_public": selected_pq_public,
        "pq_prekey_signature": selected_pq_signature,
        "pq_is_last_resort": pq_opk_public is None,
        "pq_prekey_source": pq_prekey_source,
    }

    suffix_parts = ["with EC OPK" if opk_public else "without EC OPK"]
    suffix_parts.append("with PQOPK" if pq_opk_public else "with PQ signed last-resort prekey")

    state.phase2_signature_verified = False
    state.phase2_ek_generated = False
    state.alice_derived = None
    state.initial_message = None
    state.bob_receive_result = None
    add_event(state, f"Alice requested Bob PQXDH bundle ({', '.join(suffix_parts)}).")


def alice_verifies_bundle_signature(state: PQXDHState) -> None:
    bundle = state.last_bundle_for_alice
    if not isinstance(bundle, dict):
        raise ValueError("Alice must request Bob prekey bundle first.")

    bob = ensure_bob_local(state)
    bob_identity = bob.get("identity_dh") if isinstance(bob.get("identity_dh"), dict) else None
    if not isinstance(bob_identity, dict):
        raise ValueError("Bob local identity key is missing.")

    verify_public = ext.IDENTITY_SIGNING_PUBLIC_FROM_DH_PRIVATE(bob_identity["private"])

    if bundle.get("identity_dh_public") != bob_identity.get("public"):
        raise ValueError("Bundle IK_pub does not match Bob identity key.")

    ok_ec = ext.VERIFY_WITH_IDENTITY_SIGNING_PUBLIC(
        verify_public,
        bytes.fromhex(bundle["signed_prekey_public"]),
        bundle["signed_prekey_signature"],
    )
    if not ok_ec:
        raise ValueError("Bob EC signed prekey signature verification failed.")

    pq_public = bundle.get("pq_pkb_public", bundle.get("pq_prekey_public", bundle.get("pq_signed_prekey_public")))
    pq_signature = bundle.get("pq_pkb_signature", bundle.get("pq_prekey_signature", bundle.get("pq_signed_prekey_signature")))
    if not isinstance(pq_public, str) or not isinstance(pq_signature, str):
        raise ValueError("Bundle PQ prekey information is missing.")

    ok_pq = ext.VERIFY_WITH_IDENTITY_SIGNING_PUBLIC(
        verify_public,
        bytes.fromhex(pq_public),
        pq_signature,
    )
    if not ok_pq:
        raise ValueError("Bob PQ prekey signature verification failed.")

    state.phase2_signature_verified = True
    add_event(state, "Alice verified Bob EC and PQPKB signatures.")


def alice_generates_ek_and_derives_sk(state: PQXDHState) -> None:
    if not state.phase2_signature_verified:
        raise ValueError("Verify bundle signatures before deriving SK.")

    alice = ensure_alice_local(state)
    bundle = state.last_bundle_for_alice
    if not isinstance(bundle, dict):
        raise ValueError("Alice must request Bob prekey bundle first.")

    pq_prekey_public = bundle.get("pq_pkb_public") or bundle.get("pq_opk_public") or bundle.get("pq_prekey_public")
    if not isinstance(pq_prekey_public, str) or not pq_prekey_public:
        raise ValueError("PQ prekey public value is missing.")

    pq_key_type = "PQSPK" if bool(bundle.get("pq_is_last_resort", False)) else "PQOPK"

    ek = _generate_dh_key_pair()
    alice["ephemeral_key"] = ek

    dh_outputs = [
        ext.DH(alice["identity_dh"], bundle["signed_prekey_public"]),
        ext.DH(ek, bundle["identity_dh_public"]),
        ext.DH(ek, bundle["signed_prekey_public"]),
    ]

    if bundle.get("opk_public"):
        dh_outputs.append(ext.DH(ek, bundle["opk_public"]))

    kem_ciphertext, pq_secret = ext.PQKEM_ENCAPSULATE(pq_prekey_public)

    secret_values = [*dh_outputs, pq_secret]
    sk = ext.KDF_SK_PQXDH(secret_values)

    state.alice_derived = {
        "shared_secret": sk.hex(),
        "dh_count": len(dh_outputs),
        "associated_data": None,
        "ek_public": ek["public"],
        "ek_private": ek["private"],
        "kem_ciphertext": kem_ciphertext,
        "pq_secret": pq_secret.hex(),
        "pq_prekey_type": pq_key_type,
    }

    state.phase2_ek_generated = True
    add_event(state, f"Alice derived PQXDH SK using {pq_key_type} with {len(dh_outputs)} DH operation(s) and 1 PQKEM secret.")


def alice_calculates_associated_data(state: PQXDHState) -> None:
    alice = ensure_alice_local(state)
    derived = state.alice_derived
    bundle = state.last_bundle_for_alice
    if not isinstance(derived, dict) or not isinstance(bundle, dict):
        raise ValueError("Derive SK first.")

    associated_data = ext.CALC_AD(
        initiator_identity_public=alice["identity_dh"]["public"],
        responder_identity_public=bundle["identity_dh_public"],
    )

    derived["associated_data"] = associated_data
    add_event(state, "Alice calculated Associated Data (AD).")


def alice_sends_initial_message(state: PQXDHState, plaintext: str) -> None:
    alice = ensure_alice_local(state)
    derived = state.alice_derived
    bundle = state.last_bundle_for_alice
    if not isinstance(derived, dict) or not isinstance(bundle, dict):
        raise ValueError("Complete phase 2 before sending the initial message.")

    shared_secret = derived.get("shared_secret")
    associated_data = derived.get("associated_data")
    kem_ciphertext = derived.get("kem_ciphertext")

    if not isinstance(shared_secret, str) or not isinstance(associated_data, str) or not isinstance(kem_ciphertext, str):
        raise ValueError("SK, AD, and PQ ciphertext must be available before sending.")

    _ = plaintext

    payload = bytes.fromhex(associated_data)
    ciphertext = ext.ENCRYPT(
        bytes.fromhex(shared_secret),
        payload,
        b"",
    ).hex()

    header = {
        "ik_a_public": alice["identity_dh"]["public"],
        "ek_a_public": derived["ek_public"],
        "bob_spk_public": bundle["signed_prekey_public"],
        "bob_opk_id": bundle.get("opk_id"),
        "bob_pq_prekey_id": bundle.get("pq_opk_id", bundle.get("pq_prekey_id")),
        "bob_pq_prekey_source": bundle.get("pq_prekey_source", "pqspk"),
        "pq_ciphertext": kem_ciphertext,
        "pq_is_last_resort": bool(bundle.get("pq_is_last_resort", False)),
    }

    state.initial_message = {
        "from": "Alice",
        "to": "Bob",
        "header": header,
        "ik_a_public": header["ik_a_public"],
        "ek_a_public": header["ek_a_public"],
        "bob_spk_public": header["bob_spk_public"],
        "bob_opk_id": header["bob_opk_id"],
        "bob_pq_prekey_id": header["bob_pq_prekey_id"],
        "bob_pq_prekey_source": header["bob_pq_prekey_source"],
        "pq_ciphertext": header["pq_ciphertext"],
        "pq_is_last_resort": header["pq_is_last_resort"],
        "ciphertext": ciphertext,
    }

    state.bob_receive_result = None
    add_event(state, "Alice sent initial PQXDH message to Bob (encrypted AD payload).")


def bob_receives_and_verifies(state: PQXDHState) -> None:
    bob = ensure_bob_local(state)
    msg = state.initial_message
    if not isinstance(msg, dict):
        raise ValueError("No initial message to process.")

    header = msg.get("header") if isinstance(msg.get("header"), dict) else {}
    ik_a_public = header.get("ik_a_public", msg.get("ik_a_public"))
    ek_a_public = header.get("ek_a_public", msg.get("ek_a_public"))
    bob_spk_public = header.get("bob_spk_public", msg.get("bob_spk_public"))
    pq_ciphertext = header.get("pq_ciphertext", msg.get("pq_ciphertext"))

    if not all(isinstance(value, str) and value for value in [ik_a_public, ek_a_public, bob_spk_public, pq_ciphertext]):
        raise ValueError("Initial message header is incomplete.")

    if bob.get("signed_prekey", {}).get("public") != bob_spk_public:
        raise ValueError("Message header SPK does not match Bob's current SPK.")

    dh_values = [
        ext.DH(bob["signed_prekey"], ik_a_public),
        ext.DH(bob["identity_dh"], ek_a_public),
        ext.DH(bob["signed_prekey"], ek_a_public),
    ]

    opk_id = header.get("bob_opk_id", msg.get("bob_opk_id"))
    if opk_id is not None:
        opk_private_entry = bob.get("opk_private_by_id", {}).pop(str(opk_id), None)
        if not isinstance(opk_private_entry, dict):
            raise ValueError("Expected Bob OPK was already consumed or missing.")
        dh_values.append(ext.DH(opk_private_entry, ek_a_public))

    pq_key_id = header.get("bob_pq_prekey_id", msg.get("bob_pq_prekey_id"))
    pq_is_last_resort = bool(header.get("pq_is_last_resort", msg.get("pq_is_last_resort", False)))
    used_pq_prekey_type = "PQSPK" if pq_is_last_resort else "PQOPK"
    pq_private_entry = None
    if pq_key_id is not None:
        pq_private_entry = bob.get("pq_opk_private_by_id", {}).pop(str(pq_key_id), None)
    if not isinstance(pq_private_entry, dict):
        pq_private_entry = bob.get("pq_signed_prekey")

    if not isinstance(pq_private_entry, dict) or not isinstance(pq_private_entry.get("private"), str):
        raise ValueError("Bob PQ private key material is missing.")

    pq_secret = ext.PQKEM_DECAPSULATE(pq_private_entry["private"], pq_ciphertext)

    bob_sk = ext.KDF_SK_PQXDH([*dh_values, pq_secret])
    bob_associated_data = ext.CALC_AD(
        initiator_identity_public=ik_a_public,
        responder_identity_public=bob["identity_dh"]["public"],
    )

    decrypted_text = ""
    decrypt_ok = False
    payload_matches_ad = False
    try:
        decrypted_bytes = ext.DECRYPT(
            bob_sk,
            bytes.fromhex(msg["ciphertext"]),
            b"",
        )
        decrypted_text = decrypted_bytes.hex()
        decrypt_ok = True
        payload_matches_ad = decrypted_text == bob_associated_data
    except Exception as exc:
        decrypted_text = f"Decryption failed: {exc}"

    ad_matches = payload_matches_ad

    alice_derived = state.alice_derived
    shared_secret_match = False
    if isinstance(alice_derived, dict):
        shared_secret_match = alice_derived.get("shared_secret") == bob_sk.hex()

    state.bob_receive_result = {
        "used_opk_id": opk_id,
        "used_pq_prekey_id": pq_key_id,
        "used_pq_prekey_type": used_pq_prekey_type,
        "ad_local": bob_associated_data,
        "ad_matches": ad_matches,
        "payload_matches_ad": payload_matches_ad,
        "bob_shared_secret": bob_sk.hex(),
        "shared_secret_matches": shared_secret_match,
        "decryption_ok": decrypt_ok,
        "decrypted_text": decrypted_text,
        "dh_count": len(dh_values),
        "pq_secret_included": True,
    }

    if ad_matches and shared_secret_match:
        add_event(state, "Bob verified AD and derived the same PQXDH shared secret.")
    else:
        add_event(state, "Bob processed message but AD or shared secret mismatch occurred.")


def is_phase1_done(state: PQXDHState) -> bool:
    return isinstance(state.server_state.get("alice_bundle"), dict)


def is_phase2_done(state: PQXDHState) -> bool:
    derived = state.alice_derived
    return isinstance(derived, dict) and isinstance(derived.get("associated_data"), str)
