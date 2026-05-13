"""Interactive controller for the X3DH protocol demonstration.

This module wires the X3DH state machine into the generic key-exchange module
base, exposes user-triggered actions for each protocol step, and coordinates
the main view with the step-by-step visualization dialog shown after each
action. It is the UI-facing entry point for the non-post-quantum key-exchange
flow.
"""

from __future__ import annotations

import flet as ft

from components.data_classes import X3DHState
from modules.key_exchange.key_exchange_base_logic import (
    alice_calculates_associated_data,
    is_phase1_done,
    is_phase2_done,
)
from modules.key_exchange.key_exchange_base_module import KeyExchangeBaseModule
from modules.key_exchange.x3dh.logic import (
    alice_generates_ek_and_derives_sk,
    alice_rotates_signed_prekey_bundle,
    alice_sends_initial_message,
    alice_uploads_new_opk,
    alice_verifies_bundle_signature,
    bob_receives_and_verifies,
    generate_alice_registration_material,
    new_state,
    request_bob_bundle_for_alice,
    server_sends_alice_opk_to_requester,
    server_sends_bob_opk_to_requester,
    upload_alice_initial_bundle,
)
from modules.key_exchange.x3dh.step_visualization import show_x3dh_action_step_visualization_dialog
from modules.key_exchange.x3dh.view import build_visual


class X3DHModule(KeyExchangeBaseModule):
    """Controller for the standard X3DH demo flow.

    The class adapts protocol-specific state and action handlers to the shared
    key-exchange module contract so the rest of the application can load,
    export, render, and reset the X3DH scenario without special-casing it.
    """

    _PROTOCOL_SOURCE_ID = "x3dh"

    def _new_state(self) -> X3DHState:
        """Create a fresh X3DH demo state."""

        return new_state()

    def _deserialize_state(self, data: dict) -> X3DHState:
        """Rebuild X3DH state from persisted module data."""

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

    def _generate_alice_registration_material(self) -> None:
        """Generate Alice's X3DH identity, signed prekey, and OPKs."""

        generate_alice_registration_material(self.state)

    def _upload_alice_initial_bundle(self) -> None:
        """Upload Alice's initial prekey bundle to the simulated server."""

        upload_alice_initial_bundle(self.state)

    def _server_sends_alice_opk_to_requester(self) -> None:
        """Consume and return one Alice OPK from the server."""

        server_sends_alice_opk_to_requester(self.state)

    def _server_sends_bob_opk_to_requester(self) -> None:
        """Consume and return one Bob OPK from the server."""

        server_sends_bob_opk_to_requester(self.state)

    def _alice_uploads_new_opk(self) -> None:
        """Generate and publish a fresh Alice OPK."""

        alice_uploads_new_opk(self.state)

    def _alice_rotates_signed_prekey_bundle(self) -> None:
        """Rotate Alice's signed prekey bundle on the server."""

        alice_rotates_signed_prekey_bundle(self.state)

    def _request_bob_bundle_for_alice(self) -> None:
        """Request Bob's bundle for Alice's X3DH handshake."""

        request_bob_bundle_for_alice(self.state)

    def _alice_verifies_bundle_signature(self) -> None:
        """Verify Bob's signed prekey bundle before derivation."""

        alice_verifies_bundle_signature(self.state)

    def _alice_generates_ek_and_derives_sk(self) -> None:
        """Generate Alice's ephemeral key and derive the shared secret."""

        alice_generates_ek_and_derives_sk(self.state)

    def _alice_calculates_associated_data(self) -> None:
        """Derive the associated data used by the initial message."""

        alice_calculates_associated_data(self.state)

    def _alice_sends_initial_message(self, plaintext: str) -> None:
        """Build and store Alice's initial X3DH message payload."""

        alice_sends_initial_message(self.state, plaintext)

    def _bob_receives_and_verifies(self) -> None:
        """Let Bob consume the message and verify the derived secrets."""

        bob_receives_and_verifies(self.state)

    def _is_phase1_done(self) -> bool:
        """Report whether the registration phase is complete."""

        return is_phase1_done(self.state)

    def _is_phase2_done(self) -> bool:
        """Report whether Alice has finished the derivation phase."""

        return is_phase2_done(self.state)

    def build(self, page, app_state, perspective_selector: ft.Control | None = None):
        """Build the interactive X3DH module view."""

        status_text = ft.Text("", size=13, color=ft.Colors.BLUE)
        show_step_visualization_checkbox = ft.Checkbox(label="Show step-by-step visualization", value=True)
        phase2_message_input = ft.TextField(label="Payload", value="", dense=True)
        visual_container = ft.Container(expand=True)

        _ = app_state
        _ = perspective_selector

        def _set_status(message: str, is_error: bool = False) -> None:
            status_text.value = message
            status_text.color = ft.Colors.RED if is_error else ft.Colors.BLUE

        def _run(
            action: callable,
            success: str,
            action_name: str,
            action_context: dict | None = None,
            show_step_visualization: bool = True,
        ):
            before_state = self._state_data()
            try:
                action()
                _set_status(success, is_error=False)
            except Exception as exc:
                _set_status(str(exc), is_error=True)
                refresh()
                page.update()
                return

            after_state = self._state_data()
            refresh()
            page.update()

            if show_step_visualization and show_step_visualization_checkbox.value:
                show_x3dh_action_step_visualization_dialog(
                    page,
                    action_name=action_name,
                    before_state=before_state,
                    after_state=after_state,
                    action_context=action_context or {},
                )

        def on_generate_alice(e):
            _run(
                self._generate_alice_registration_material,
                "Alice registration material generated.",
                "generate_alice_registration_material",
            )

        def on_upload_alice_bundle(e):
            _run(
                self._upload_alice_initial_bundle,
                "Alice initial bundle uploaded to server.",
                "upload_alice_initial_bundle",
            )

        def on_server_send_alice_opk(e):
            _run(
                self._server_sends_alice_opk_to_requester,
                "Server sent one Alice OPK to requester.",
                "server_sends_alice_opk_to_requester",
            )

        def on_server_send_bob_opk(e):
            _run(
                self._server_sends_bob_opk_to_requester,
                "Server sent one Bob OPK to requester.",
                "server_sends_bob_opk_to_requester",
            )

        def on_alice_upload_new_opk(e):
            _run(self._alice_uploads_new_opk, "Alice uploaded a new OPK.", "alice_uploads_new_opk")

        def on_alice_rotate_spk(e):
            _run(
                self._alice_rotates_signed_prekey_bundle,
                "Alice uploaded a new signed prekey bundle.",
                "alice_rotates_signed_prekey_bundle",
            )

        def on_request_bob_bundle(e):
            _run(
                self._request_bob_bundle_for_alice,
                "Alice requested Bob prekey bundle from server.",
                "request_bob_bundle_for_alice",
            )

        def on_verify_signature(e):
            _run(
                self._alice_verifies_bundle_signature,
                "Alice verified Bob signed prekey signature.",
                "alice_verifies_bundle_signature",
            )

        def on_generate_ek_and_sk(e):
            _run(
                self._alice_generates_ek_and_derives_sk,
                "Alice generated EK and derived SK.",
                "alice_generates_ek_and_derives_sk",
            )

        def on_compute_ad(e):
            _run(self._alice_calculates_associated_data, "Alice computed AD.", "alice_calculates_associated_data")

        def on_send_initial_message(e):
            _run(
                lambda: self._alice_sends_initial_message(phase2_message_input.value),
                "Alice sent initial X3DH message.",
                "alice_sends_initial_message",
            )

        def on_bob_receive(e):
            _run(
                self._bob_receives_and_verifies,
                "Bob processed initial message and checked AD/SK.",
                "bob_receives_and_verifies",
            )

        def on_reset_application(e):
            phase2_message_input.value = ""
            _run(
                self._reset_application,
                "X3DH application reset.",
                "reset_application",
                show_step_visualization=False,
            )

        def refresh() -> None:
            state_data = self._state_data()
            app_state.x3dh_to_dr_bootstrap = self._build_dr_bootstrap_payload()
            visual_container.content = build_visual(
                state_data,
                page,
                status_text,
                show_step_visualization_checkbox,
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

