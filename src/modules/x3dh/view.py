from __future__ import annotations

from typing import Any

import flet as ft

from modules.base_view import format_key, last_n_chars, make_copy_handler
from modules.tooltip_helpers import build_tooltip_text, get_tooltip_messages


SUMMARY_PANEL_HEIGHT = 150


def _short(value: str | None, length: int = 12) -> str:
    if not value:
        return "-"
    if len(value) <= length:
        return value
    return value[-length:]



def _build_tooltip_value(
    page: ft.Page | None,
    tooltips: dict[str, str],
    label: str,
    full_value: Any,
    display_length: int = 12,
) -> ft.Control:
    normalized = format_key(full_value)
    display = last_n_chars(normalized, display_length) if normalized not in {"", "None"} else normalized
    copy_handler = make_copy_handler(page, label, normalized) if page is not None and normalized not in {"", "None"} else None
    return build_tooltip_text(
        label,
        display,
        tooltips.get(label, ""),
        full_value=normalized if normalized not in {"", "None"} else None,
        on_click=copy_handler,
    )


def _build_event_timeline(events: list[Any], tooltips: dict[str, str], max_items: int = 10) -> ft.Control:
    if not events:
        return ft.Column([ft.Text("No events yet.", color=ft.Colors.ON_SURFACE_VARIANT)], spacing=4)

    tail = events[-max_items:]
    return ft.Column(
        controls=[
            build_tooltip_text(
                "event",
                f"- {event}",
                tooltips.get("event", ""),
                full_value=str(event),
            )
            for event in tail
        ],
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
    )


def _build_party_summary(
    title: str,
    payload: dict[str, Any] | None,
    page: ft.Page | None,
    tooltips: dict[str, str],
) -> ft.Control:
    if not isinstance(payload, dict):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, weight=ft.FontWeight.BOLD),
                    build_tooltip_text("party_not_initialized", "Not initialized", tooltips.get("party_not_initialized", "")),
                ]
            ),
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
                _build_tooltip_value(page, tooltips, "IK_pub", identity_pub),
                _build_tooltip_value(page, tooltips, "SPK_pub", spk_pub),
                build_tooltip_text(
                    "identity_signing_proof",
                    "present" if signing_pub else "missing",
                    tooltips.get("identity_signing_proof", ""),
                    full_value=signing_pub or None,
                    on_click=make_copy_handler(page, "identity_signing_proof", signing_pub) if page is not None and signing_pub else None,
                ),
                build_tooltip_text(
                    "local_opk_count",
                    str(opk_count),
                    tooltips.get("local_opk_count", ""),
                ),
            ],
            spacing=4,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=10,
        height=SUMMARY_PANEL_HEIGHT,
        expand=True,
    )


def _build_server_summary(
    server: dict[str, Any],
    page: ft.Page | None,
    tooltips: dict[str, str],
    alice_needs_to_upload_opk: bool = False,
) -> ft.Control:
    alice_bundle = server.get("alice_bundle")
    bob_bundle = server.get("bob_bundle")
    alice_opk_count = len(server.get('alice_available_opk_ids', []))

    opk_bg_color = None
    if alice_opk_count == 0:
        opk_bg_color = ft.Colors.RED_300
    elif alice_opk_count < 3:
        opk_bg_color = ft.Colors.YELLOW_300

    alice_opk_display = ft.Container(
        content=build_tooltip_text(
            "alice_server_opk_count",
            str(alice_opk_count),
            tooltips.get("alice_server_opk_count", ""),
        ),
        bgcolor=opk_bg_color,
        padding=6,
        border_radius=4,
    ) if opk_bg_color else build_tooltip_text(
        "alice_server_opk_count",
        str(alice_opk_count),
        tooltips.get("alice_server_opk_count", ""),
    )

    _ = page
    _ = alice_needs_to_upload_opk

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Server", weight=ft.FontWeight.BOLD),
                build_tooltip_text(
                    "alice_bundle_status",
                    "uploaded" if isinstance(alice_bundle, dict) else "missing",
                    tooltips.get("alice_bundle_status", ""),
                ),
                alice_opk_display,
                build_tooltip_text(
                    "bob_bundle_status",
                    "available" if isinstance(bob_bundle, dict) else "missing",
                    tooltips.get("bob_bundle_status", ""),
                ),
                build_tooltip_text(
                    "bob_server_opk_count",
                    str(len(server.get("bob_available_opk_ids", []))),
                    tooltips.get("bob_server_opk_count", ""),
                ),
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
    tooltips: dict[str, str],
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
            build_tooltip_text("phase2_bob_bundle_status", bundle_status, tooltips.get("phase2_bob_bundle_status", "")),
            build_tooltip_text(
                "phase2_shared_secret_preview",
                sk_preview,
                tooltips.get("phase2_shared_secret_preview", ""),
                full_value=derived.get("shared_secret") if isinstance(derived, dict) else None,
            ),
            build_tooltip_text(
                "phase2_ad_preview",
                ad_preview,
                tooltips.get("phase2_ad_preview", ""),
                full_value=derived.get("associated_data") if isinstance(derived, dict) else None,
            ),
            build_tooltip_text("phase2_dh_count", dh_count, tooltips.get("phase2_dh_count", "")),
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
    page: ft.Page | None,
    tooltips: dict[str, str],
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
                build_tooltip_text(
                    "phase3_message_status",
                    "Message prepared" if isinstance(initial_message, dict) else "No initial message sent yet.",
                    tooltips.get("phase3_message_status", ""),
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
                build_tooltip_text("phase3_ad_match", str(bob_result.get("ad_matches", False)), tooltips.get("phase3_ad_match", "")),
                build_tooltip_text(
                    "phase3_shared_secret_match",
                    str(bob_result.get("shared_secret_matches", False)),
                    tooltips.get("phase3_shared_secret_match", ""),
                ),
                build_tooltip_text("phase3_decryption_ok", str(bob_result.get("decryption_ok", False)), tooltips.get("phase3_decryption_ok", "")),
                build_tooltip_text("phase3_dh_count", str(bob_result.get("dh_count", "-")), tooltips.get("phase3_dh_count", "")),
                build_tooltip_text(
                    "phase3_decrypted_text",
                    _short(str(bob_result.get("decrypted_text", "-")), 24),
                    tooltips.get("phase3_decrypted_text", ""),
                    full_value=str(bob_result.get("decrypted_text", "-")),
                    on_click=make_copy_handler(page, "phase3_decrypted_text", str(bob_result.get("decrypted_text", "-"))) if page is not None else None,
                ),
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
    page: ft.Page,
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
    tooltips = get_tooltip_messages("x3dh")

    header_controls: list[ft.Control] = [
        ft.Row(
            controls=[
                ft.Text("X3DH Model", size=26, weight=ft.FontWeight.BOLD),
                ft.TextButton("Reset application", on_click=on_reset_application),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        build_tooltip_text(
            "progressive_flow",
            "Progressive flow: finish phase 1 to reveal phase 2, then finish phase 2 to reveal phase 3.",
            tooltips.get("progressive_flow", ""),
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
                tooltips,
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
                page,
                tooltips,
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
            ft.Row([_build_party_summary("Alice", state.get("alice_local"), page, tooltips)]),
            ft.Row([_build_party_summary("Bob", state.get("bob_local"), page, tooltips)]),
            ft.Row([
                _build_server_summary(
                    state["server_state"],
                    page,
                    tooltips,
                    state.get("alice_needs_to_upload_opk", False),
                )
            ]),
        ],
        spacing=8,
    )

    timeline_panel = ft.Column(
        controls=[
            summary_section,
            ft.Divider(height=8),
            build_tooltip_text("timeline", "Timeline", tooltips.get("timeline", "")),
            _build_event_timeline(state.get("events", []), tooltips, max_items=20),
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
