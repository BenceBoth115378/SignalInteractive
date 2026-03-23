from __future__ import annotations

from typing import Any

import flet as ft


SUMMARY_PANEL_HEIGHT = 132


def _short(value: str | None, length: int = 12) -> str:
    if not value:
        return "-"
    if len(value) <= length:
        return value
    return value[-length:]


def _build_event_timeline(events: list[Any], max_items: int = 10) -> ft.Control:
    if not events:
        return ft.Column([ft.Text("No events yet.", color=ft.Colors.ON_SURFACE_VARIANT)], spacing=4)

    tail = events[-max_items:]
    return ft.Column(
        controls=[ft.Text(f"- {event}", size=12) for event in tail],
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
    )


def _build_party_summary(title: str, payload: dict[str, Any] | None) -> ft.Control:
    if not isinstance(payload, dict):
        return ft.Container(
            content=ft.Column([ft.Text(title, weight=ft.FontWeight.BOLD), ft.Text("Not initialized", color=ft.Colors.ON_SURFACE_VARIANT)]),
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            padding=10,
            height=SUMMARY_PANEL_HEIGHT,
            expand=True,
        )

    identity_pub = payload.get("identity_dh", {}).get("public")
    spk_pub = payload.get("signed_prekey", {}).get("public")
    signing_pub = payload.get("identity_signing_public", "")
    opk_count = len(payload.get("opk_public_by_id", {}))

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(title, weight=ft.FontWeight.BOLD),
                ft.Text(f"IK pub: {_short(identity_pub)}"),
                ft.Text(f"SPK pub: {_short(spk_pub)}"),
                ft.Text(f"Identity signing proof: {'present' if signing_pub else 'missing'}"),
                ft.Text(f"OPKs available (local): {opk_count}"),
            ],
            spacing=4,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=10,
        height=SUMMARY_PANEL_HEIGHT,
        expand=True,
    )


def _build_server_summary(server: dict[str, Any], alice_needs_to_upload_opk: bool = False) -> ft.Control:
    alice_bundle = server.get("alice_bundle")
    bob_bundle = server.get("bob_bundle")
    alice_opk_count = len(server.get('alice_available_opk_ids', []))

    opk_bg_color = None
    if alice_opk_count == 0:
        opk_bg_color = ft.Colors.RED_300
    elif alice_opk_count < 3:
        opk_bg_color = ft.Colors.YELLOW_300

    alice_opk_display = ft.Container(
        content=ft.Text(f"Alice OPKs on server: {alice_opk_count}", weight=ft.FontWeight.W_500),
        bgcolor=opk_bg_color,
        padding=6,
        border_radius=4,
    ) if opk_bg_color else ft.Text(f"Alice OPKs on server: {alice_opk_count}")

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Server", weight=ft.FontWeight.BOLD),
                ft.Text(f"Alice bundle: {'uploaded' if isinstance(alice_bundle, dict) else 'missing'}"),
                alice_opk_display,
                ft.Text(f"Bob bundle: {'available' if isinstance(bob_bundle, dict) else 'missing'}"),
                ft.Text(f"Bob OPKs on server: {len(server.get('bob_available_opk_ids', []))}"),
            ],
            spacing=4,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=10,
        height=SUMMARY_PANEL_HEIGHT,
        expand=True,
    )


def _phase1_container(
    state: dict[str, Any],
    on_generate_alice,
    on_upload_alice_bundle,
    on_server_send_alice_opk,
    on_server_send_bob_opk,
    on_alice_upload_new_opk,
    on_alice_rotate_spk,
    alice_needs_to_upload_opk: bool = False,
) -> ft.Control:
    alice_registered = isinstance(state.get("server_state", {}).get("alice_bundle"), dict)

    upload_button = ft.Button(
        "Alice uploads new OPK",
        on_click=on_alice_upload_new_opk,
    )
    if alice_needs_to_upload_opk:
        upload_button_container = ft.Container(
            content=upload_button,
            border=ft.Border.all(3, ft.Colors.ORANGE),
            border_radius=4,
            padding=2,
        )
    else:
        upload_button_container = ft.Container(content=upload_button)

    left = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Alice Actions", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Button("Generate Alice keys", on_click=on_generate_alice)]),
                ft.Row([ft.Button("Upload initial bundle", on_click=on_upload_alice_bundle)]),
                ft.Row([upload_button_container], expand=True),
                ft.Row([ft.Button("Alice uploads new signed prekey bundle", on_click=on_alice_rotate_spk)]),
            ],
            spacing=8,
        ),
        expand=True,
    )

    middle = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Server Actions", weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Button(
                        "Send 1 Alice OPK to an another requester",
                        on_click=on_server_send_alice_opk,
                        expand=True,
                        disabled=not alice_registered,
                    )
                ]),
                ft.Row([ft.Button("Send 1 Bob OPK to an another requester", on_click=on_server_send_bob_opk, expand=True)]),
            ],
            spacing=8,
        ),
        expand=True,
    )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("1. Registration", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([left, middle], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=8,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
        padding=12,
    )


def _phase2_container(
    state: dict[str, Any],
    on_request_bob_bundle,
    on_verify_signature,
    on_generate_ek_and_sk,
    on_compute_ad,
) -> ft.Control:
    bundle = state.get("last_bundle_for_alice")
    derived = state.get("alice_derived")

    bundle_status = "not requested"
    if isinstance(bundle, dict):
        bundle_status = "with OPK" if bundle.get("opk_public") else "without OPK"

    sk_preview = "-"
    ad_preview = "-"
    dh_count = "-"
    if isinstance(derived, dict):
        sk_preview = _short(derived.get("shared_secret"), 20)
        ad_preview = _short(derived.get("associated_data"), 20)
        dh_count = str(derived.get("dh_count", "-"))

    buttons = ft.Column(
        controls=[
            ft.Button("1) Request Bob prekey bundle", on_click=on_request_bob_bundle),
            ft.Button("2) Verify Bob signed prekey signature", on_click=on_verify_signature),
            ft.Button("3) Generate EK and derive SK (3 or 4 DH)", on_click=on_generate_ek_and_sk),
            ft.Button("4) Compute associated data (AD)", on_click=on_compute_ad),
        ],
        spacing=8,
    )

    texts = ft.Column(
        controls=[
            ft.Text(f"Bob bundle status: {bundle_status}"),
            ft.Text(f"Derived shared secret preview: {sk_preview}"),
            ft.Text(f"Derived associated data preview: {ad_preview}"),
            ft.Text(f"DH computations performed: {dh_count}"),
        ],
        spacing=4,
    )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("2. Alice computes shared secret and AD", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([buttons,
                        ft.VerticalDivider(),
                        texts],
                       expand=True,
                       vertical_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=8,
        ),

        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
        padding=12,
    )


def _phase3_container(
    state: dict[str, Any],
    phase2_message_input: ft.TextField,
    on_send_initial_message,
    on_bob_receive,
) -> ft.Control:
    initial_message = state.get("initial_message")
    bob_result = state.get("bob_receive_result")

    alice_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Alice", weight=ft.FontWeight.BOLD),
                phase2_message_input,
                ft.Button("Send initial message", on_click=on_send_initial_message),
                ft.Text(
                    "Message prepared" if isinstance(initial_message, dict) else "No initial message sent yet.",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=8,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=10,
        expand=True,
    )

    bob_controls: list[ft.Control] = [
        ft.Text("Bob", weight=ft.FontWeight.BOLD),
        ft.Button("Receive and verify", on_click=on_bob_receive),
    ]

    if isinstance(bob_result, dict):
        bob_controls.extend(
            [
                ft.Text(f"AD match: {bob_result.get('ad_matches', False)}"),
                ft.Text(f"Shared secret match: {bob_result.get('shared_secret_matches', False)}"),
                ft.Text(f"Decryption OK: {bob_result.get('decryption_ok', False)}"),
                ft.Text("DH count: " + str(bob_result.get("dh_count", "-"))),
                ft.Text(f"Decrypted: {bob_result.get('decrypted_text', '-')}", selectable=True),
            ]
        )
    else:
        bob_controls.append(ft.Text("No verification run yet.", color=ft.Colors.ON_SURFACE_VARIANT))

    bob_panel = ft.Container(
        content=ft.Column(controls=bob_controls, spacing=8),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=10,
        expand=True,
    )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("3. Send initial message", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([alice_panel, bob_panel], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=8,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
        padding=12,
    )


def build_visual(
    state: dict[str, Any],
    status_text: ft.Text,
    phase2_message_input: ft.TextField,
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
    is_phase1_done: bool,
    is_phase2_done: bool,
) -> ft.Control:

    header_controls: list[ft.Control] = [
        ft.Row(
            controls=[
                ft.Text("X3DH Model", size=26, weight=ft.FontWeight.BOLD),
                ft.TextButton("Reset application", on_click=on_reset_application),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ft.Text(
            "Progressive flow: finish phase 1 to reveal phase 2, then finish phase 2 to reveal phase 3.",
            color=ft.Colors.ON_SURFACE_VARIANT,
        ),
        status_text,
    ]

    phase_controls: list[ft.Control] = [
        _phase1_container(
            state,
            on_generate_alice,
            on_upload_alice_bundle,
            on_server_send_alice_opk,
            on_server_send_bob_opk,
            on_alice_upload_new_opk,
            on_alice_rotate_spk,
            alice_needs_to_upload_opk=state.get("alice_needs_to_upload_opk", False),
        ),
    ]

    if is_phase1_done:
        phase_controls.append(
            _phase2_container(
                state,
                on_request_bob_bundle,
                on_verify_signature,
                on_generate_ek_and_sk,
                on_compute_ad,
            )
        )
    else:
        phase_controls.append(
            ft.Text(
                "Complete Phase 1 by uploading Alice initial bundle to reveal Phase 2. (When OPK count drops below 3, Alice will be prompted to upload new OPKs)",
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )

    if is_phase2_done:
        phase_controls.append(
            _phase3_container(
                state,
                phase2_message_input,
                on_send_initial_message,
                on_bob_receive,
            )
        )
    elif is_phase1_done:
        phase_controls.append(
            ft.Text(
                "Complete Phase 2 by computing AD to reveal Phase 3.",
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )

    left_panel = ft.Column(
        controls=phase_controls,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    summary_section = ft.Row(
        controls=[
            ft.Row([_build_party_summary("Alice", state.get("alice_local"))]),
            ft.Row([_build_party_summary("Bob", state.get("bob_local"))]),
            ft.Row([_build_server_summary(state["server_state"], state.get("alice_needs_to_upload_opk", False))]),
        ],
        spacing=8,
    )

    timeline_panel = ft.Column(
        controls=[
            summary_section,
            ft.Divider(height=8),
            ft.Text("Timeline", weight=ft.FontWeight.BOLD, size=14),
            _build_event_timeline(state.get("events", []), max_items=20),
        ],
        spacing=6,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    timeline_container = ft.Container(
        content=timeline_panel,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=10,
        expand=True,
    )

    content_row = ft.Row(
        controls=[left_panel, timeline_container],
        spacing=12,
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    return ft.Column(
        controls=header_controls + [content_row],
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
