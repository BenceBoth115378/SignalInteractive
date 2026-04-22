from __future__ import annotations

import hashlib
import itertools
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from components.data_classes import DHKeyPair  # noqa: E402
from modules.key_exchange.x3dh import logic  # noqa: E402


@pytest.fixture(autouse=True)
def deterministic_crypto(monkeypatch: pytest.MonkeyPatch):
    pair_ids = itertools.count(1)
    private_by_public: dict[str, str] = {}

    def fake_generate_dh() -> DHKeyPair:
        index = next(pair_ids)
        private_hex = f"{index:064x}"
        public_hex = f"{index + 1000:064x}"
        private_by_public[public_hex] = private_hex
        return DHKeyPair(private=private_hex, public=public_hex)

    def fake_sign(identity_private_hex: str, message: bytes) -> str:
        return f"sig:{identity_private_hex}:{message.hex()}"

    def fake_verify(identity_signing_public: str, message: bytes, signature_hex: str) -> bool:
        prefix = "signpub:"
        if not identity_signing_public.startswith(prefix):
            return False
        identity_private_hex = identity_signing_public[len(prefix):]
        expected_signature = f"sig:{identity_private_hex}:{message.hex()}"
        return signature_hex == expected_signature

    def fake_identity_signing_public_from_dh_private(identity_private_hex: str) -> str:
        return f"signpub:{identity_private_hex}"

    def fake_dh(dh_pair, dh_pub: str) -> bytes:
        if isinstance(dh_pair, dict):
            private_hex = dh_pair["private"]
        else:
            private_hex = dh_pair.private

        peer_private_hex = private_by_public.get(dh_pub, dh_pub)
        shared_parts = sorted([private_hex, peer_private_hex])
        return hashlib.sha256("|".join(shared_parts).encode("utf-8")).digest()

    def fake_kdf_sk(dh_values: list[bytes]) -> bytes:
        return hashlib.sha256(b"|".join(dh_values)).digest()

    def fake_calc_ad(*, initiator_identity_public: str, responder_identity_public: str) -> str:
        payload = f"{initiator_identity_public}|{responder_identity_public}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def fake_encrypt(message_key: bytes, plaintext: bytes, associated_data: bytes) -> bytes:
        _ = message_key
        _ = associated_data
        return b"ct:" + plaintext

    def fake_decrypt(message_key: bytes, ciphertext: bytes, associated_data: bytes) -> bytes:
        _ = message_key
        _ = associated_data
        prefix = b"ct:"
        if not ciphertext.startswith(prefix):
            raise ValueError("Unexpected ciphertext format")
        return ciphertext[len(prefix):]

    monkeypatch.setattr(logic.ext, "GENERATE_DH", fake_generate_dh)
    monkeypatch.setattr(logic.ext, "SIGN_WITH_IDENTITY_DH_PRIVATE", fake_sign)
    monkeypatch.setattr(logic.ext, "VERIFY_WITH_IDENTITY_SIGNING_PUBLIC", fake_verify)
    monkeypatch.setattr(logic.ext, "IDENTITY_SIGNING_PUBLIC_FROM_DH_PRIVATE", fake_identity_signing_public_from_dh_private)
    monkeypatch.setattr(logic.ext, "DH", fake_dh)
    monkeypatch.setattr(logic.ext, "KDF_SK", fake_kdf_sk)
    monkeypatch.setattr(logic.ext, "CALC_AD", fake_calc_ad)
    monkeypatch.setattr(logic.ext, "ENCRYPT", fake_encrypt)
    monkeypatch.setattr(logic.ext, "DECRYPT", fake_decrypt)


def _prepare_alice(state):
    logic.generate_alice_registration_material(state)
    logic.upload_alice_initial_bundle(state)


def test_new_state_bootstraps_bob_bundle_and_events():
    state = logic.new_state()

    assert isinstance(state.bob_local, dict)
    assert isinstance(state.server_state.get("bob_bundle"), dict)
    assert state.server_state["bob_available_opk_ids"] == [1, 2, 3, 4, 5]
    assert state.events[0] == "Server bootstrapped with Bob prekey bundle and OPKs."
    assert "Flow: registration" in state.events[1]


def test_registration_upload_and_alice_opk_replenishment_flow():
    state = logic.new_state()

    _prepare_alice(state)

    assert state.alice_generated is True
    assert isinstance(state.alice_local, dict)
    assert isinstance(state.server_state.get("alice_bundle"), dict)
    assert state.server_state["alice_available_opk_ids"] == [1, 2, 3, 4, 5]

    logic.server_sends_alice_opk_to_requester(state)
    logic.server_sends_alice_opk_to_requester(state)
    logic.server_sends_alice_opk_to_requester(state)

    assert state.alice_needs_to_upload_opk is True
    assert state.server_state["alice_available_opk_ids"] == [4, 5]
    assert "id=3" in state.events[-1]

    logic.alice_uploads_new_opk(state)

    assert state.alice_needs_to_upload_opk is False
    assert state.server_state["alice_available_opk_ids"] == [4, 5, 6]
    assert state.alice_local["next_opk_id"] == 7
    assert state.events[-1] == "Alice uploaded fresh OPK id=6."


def test_full_x3dh_flow_with_opk_matches_shared_secret_and_ad():
    state = logic.new_state()
    _prepare_alice(state)

    logic.request_bob_bundle_for_alice(state)
    logic.alice_verifies_bundle_signature(state)
    logic.alice_generates_ek_and_derives_sk(state)
    logic.alice_calculates_associated_data(state)
    logic.alice_sends_initial_message(state, "ignored payload")
    logic.bob_receives_and_verifies(state)

    derived = state.alice_derived
    bob_result = state.bob_receive_result
    message = state.initial_message

    assert state.phase2_signature_verified is True
    assert state.phase2_ek_generated is True
    assert isinstance(derived, dict)
    assert derived["dh_count"] == 4
    assert isinstance(message, dict)
    assert message["header"]["bob_opk_id"] == 1
    assert isinstance(bob_result, dict)
    assert bob_result["used_opk_id"] == 1
    assert bob_result["dh_count"] == 4
    assert bob_result["decryption_ok"] is True
    assert bob_result["ad_matches"] is True
    assert bob_result["shared_secret_matches"] is True
    assert bob_result["decrypted_text"] == bob_result["ad_local"]
    assert state.events[-1] == "Bob verified AD and derived the same shared secret."


def test_full_x3dh_flow_without_opk_uses_three_dh_operations():
    state = logic.new_state()
    state.server_state["bob_available_opk_ids"] = []
    state.server_state["bob_opk_public_by_id"] = {}

    _prepare_alice(state)

    logic.request_bob_bundle_for_alice(state)
    logic.alice_verifies_bundle_signature(state)
    logic.alice_generates_ek_and_derives_sk(state)
    logic.alice_calculates_associated_data(state)
    logic.alice_sends_initial_message(state, "ignored payload")
    logic.bob_receives_and_verifies(state)

    derived = state.alice_derived
    bob_result = state.bob_receive_result

    assert isinstance(derived, dict)
    assert derived["dh_count"] == 3
    assert isinstance(bob_result, dict)
    assert bob_result["used_opk_id"] is None
    assert bob_result["dh_count"] == 3
    assert bob_result["shared_secret_matches"] is True
    assert bob_result["ad_matches"] is True


def test_signature_mismatch_blocks_bundle_verification():
    state = logic.new_state()
    _prepare_alice(state)

    state.server_state["bob_bundle"]["signed_prekey_signature"] = "broken-signature"
    logic.request_bob_bundle_for_alice(state)

    with pytest.raises(ValueError, match="signature verification failed"):
        logic.alice_verifies_bundle_signature(state)


def test_requesting_bob_bundle_without_server_bundle_fails():
    state = logic.new_state()
    state.server_state["bob_bundle"] = None

    with pytest.raises(ValueError, match="Server has no Bob bundle"):
        logic.request_bob_bundle_for_alice(state)
