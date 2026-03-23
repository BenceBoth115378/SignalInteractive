from __future__ import annotations

from dataclasses import asdict

import flet as ft

from components.data_classes import X3DHState
from modules.base_module import BaseModule
from modules.x3dh.logic import (
    alice_calculates_associated_data,
    alice_generates_ek_and_derives_sk,
    alice_rotates_signed_prekey_bundle,
    alice_sends_initial_message,
    alice_uploads_new_opk,
    alice_verifies_bundle_signature,
    bob_receives_and_verifies,
    generate_alice_registration_material,
    is_phase1_done,
    is_phase2_done,
    new_state,
    request_bob_bundle_for_alice,
    server_sends_alice_opk_to_requester,
    server_sends_bob_opk_to_requester,
    upload_alice_initial_bundle,
)
from modules.x3dh.view import build_visual


def _serialize_x3dh_state(state: X3DHState) -> dict:
    return asdict(state)


def _deserialize_x3dh_state(data: dict) -> X3DHState:
    return X3DHState(
        alice_local=data.get("alice_local"),
        alice_generated=bool(data.get("alice_generated", False)),
        server_state=data.get("server_state", {}),
        bob_local=data.get("bob_local"),
        last_bundle_for_alice=data.get("last_bundle_for_alice"),
        alice_derived=data.get("alice_derived"),
        initial_message=data.get("initial_message"),
        bob_receive_result=data.get("bob_receive_result"),
        events=data.get("events", []),
        phase2_signature_verified=bool(data.get("phase2_signature_verified", False)),
        phase2_ek_generated=bool(data.get("phase2_ek_generated", False)),
        alice_needs_to_upload_opk=bool(data.get("alice_needs_to_upload_opk", False)),
    )


class X3DHModule(BaseModule):
    def __init__(self):
        self.state = self._new_state()

    def _new_state(self) -> X3DHState:
        return new_state()

    def _state_data(self) -> dict:
        return _serialize_x3dh_state(self.state)

    def _reset_application(self) -> None:
        self.state = self._new_state()

    def export_state(self) -> dict:
        return self._state_data()

    def import_state(self, data: dict) -> None:
        if isinstance(data, dict) and data:
            if not data.get("events"):
                data["events"] = []
            self.state = _deserialize_x3dh_state(data)
        else:
            self.state = self._new_state()

    def _generate_alice_registration_material(self) -> None:
        generate_alice_registration_material(self.state)

    def _upload_alice_initial_bundle(self) -> None:
        upload_alice_initial_bundle(self.state)

    def _server_sends_alice_opk_to_requester(self) -> None:
        server_sends_alice_opk_to_requester(self.state)

    def _server_sends_bob_opk_to_requester(self) -> None:
        server_sends_bob_opk_to_requester(self.state)

    def _alice_uploads_new_opk(self) -> None:
        alice_uploads_new_opk(self.state)

    def _alice_rotates_signed_prekey_bundle(self) -> None:
        alice_rotates_signed_prekey_bundle(self.state)

    def _request_bob_bundle_for_alice(self) -> None:
        request_bob_bundle_for_alice(self.state)

    def _alice_verifies_bundle_signature(self) -> None:
        alice_verifies_bundle_signature(self.state)

    def _alice_generates_ek_and_derives_sk(self) -> None:
        alice_generates_ek_and_derives_sk(self.state)

    def _alice_calculates_associated_data(self) -> None:
        alice_calculates_associated_data(self.state)

    def _alice_sends_initial_message(self, plaintext: str) -> None:
        alice_sends_initial_message(self.state, plaintext)

    def _bob_receives_and_verifies(self) -> None:
        bob_receives_and_verifies(self.state)

    def _is_phase1_done(self) -> bool:
        return is_phase1_done(self.state)

    def _is_phase2_done(self) -> bool:
        return is_phase2_done(self.state)

    def build(self, page, app_state, perspective_selector: ft.Control | None = None):
        status_text = ft.Text("", size=13, color=ft.Colors.BLUE)
        phase2_message_input = ft.TextField(label="Initial plaintext", value="Hello Bob from Alice using X3DH", dense=True)
        visual_container = ft.Container(expand=True)

        _ = app_state
        _ = perspective_selector

        def _set_status(message: str, is_error: bool = False) -> None:
            status_text.value = message
            status_text.color = ft.Colors.RED if is_error else ft.Colors.BLUE

        def _run(action: callable, success: str):
            try:
                action()
                _set_status(success, is_error=False)
            except Exception as exc:
                _set_status(str(exc), is_error=True)
            refresh()
            page.update()

        def on_generate_alice(e):
            _run(self._generate_alice_registration_material, "Alice registration material generated.")

        def on_upload_alice_bundle(e):
            _run(self._upload_alice_initial_bundle, "Alice initial bundle uploaded to server.")

        def on_server_send_alice_opk(e):
            _run(self._server_sends_alice_opk_to_requester, "Server sent one Alice OPK to requester.")

        def on_server_send_bob_opk(e):
            _run(self._server_sends_bob_opk_to_requester, "Server sent one Bob OPK to requester.")

        def on_alice_upload_new_opk(e):
            _run(self._alice_uploads_new_opk, "Alice uploaded a new OPK.")

        def on_alice_rotate_spk(e):
            _run(self._alice_rotates_signed_prekey_bundle, "Alice uploaded a new signed prekey bundle.")

        def on_request_bob_bundle(e):
            _run(self._request_bob_bundle_for_alice, "Alice requested Bob prekey bundle from server.")

        def on_verify_signature(e):
            _run(self._alice_verifies_bundle_signature, "Alice verified Bob signed prekey signature.")

        def on_generate_ek_and_sk(e):
            _run(self._alice_generates_ek_and_derives_sk, "Alice generated EK and derived SK.")

        def on_compute_ad(e):
            _run(self._alice_calculates_associated_data, "Alice computed AD.")

        def on_send_initial_message(e):
            _run(lambda: self._alice_sends_initial_message(phase2_message_input.value), "Alice sent initial X3DH message.")

        def on_bob_receive(e):
            _run(self._bob_receives_and_verifies, "Bob processed initial message and checked AD/SK.")

        def on_reset_application(e):
            phase2_message_input.value = "Hello Bob from Alice using X3DH"
            _run(self._reset_application, "X3DH application reset.")

        def refresh() -> None:
            state_data = self._state_data()
            visual_container.content = build_visual(
                state_data,
                page,
                status_text,
                phase2_message_input,
                on_generate_alice,
                on_upload_alice_bundle,
                on_server_send_alice_opk,
                on_server_send_bob_opk,
                on_alice_upload_new_opk,
                on_alice_rotate_spk,
                on_request_bob_bundle,
                on_verify_signature,
                on_generate_ek_and_sk,
                on_compute_ad,
                on_send_initial_message,
                on_bob_receive,
                on_reset_application,
                self._is_phase1_done(),
                self._is_phase2_done(),
            )

        refresh()
        return visual_container
