"""Shared view helpers for the key-exchange protocol family.

This module provides the layout primitives that render the registration phase,
the shared-secret phase, and the initial message phase in a consistent way
across X3DH and PQXDH. Protocol-specific views plug their own state summaries
and tooltip data into these building blocks.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from modules.base_view import format_key, last_n_chars, make_copy_handler
from modules.tooltip_helpers import build_tooltip_text


def phase_ready(current_phase_done: bool) -> bool:
    return bool(current_phase_done)


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


def build_message_phase_container(
    state: dict[str, Any],
    page: ft.Page | None,
    tooltips: dict[str, str],
    phase2_message_input: ft.TextField,
    on_send_initial_message,
    on_bob_receive,
    enabled: bool,
    extra_bob_result_controls: list[ft.Control] | None = None,
) -> ft.Control:
    initial_message = state.get("initial_message")
    bob_result = state.get("bob_receive_result")
    message_sent = isinstance(initial_message, dict)
    verified = isinstance(bob_result, dict)

    highlight_send = enabled and not message_sent
    highlight_receive = enabled and message_sent and not verified

    send_button = ft.Button(
        "Send initial message",
        on_click=on_send_initial_message,
        disabled=not enabled,
        style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_300) if highlight_send else None,
    )

    alice_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Alice", weight=ft.FontWeight.BOLD),
                send_button,
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
        ft.Button(
            "Receive and verify",
            on_click=on_bob_receive,
            disabled=not enabled,
            style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_300) if highlight_receive else None,
        ),
    ]

    if isinstance(bob_result, dict):
        bob_controls.extend([
            build_tooltip_text("ad_match", str(bob_result.get("ad_matches", False)), tooltips.get("ad_match", "")),
            build_tooltip_text(
                "shared_secret_match",
                str(bob_result.get("shared_secret_matches", False)),
                tooltips.get("shared_secret_match", ""),
            ),
            build_tooltip_text("decryption_ok", str(bob_result.get("decryption_ok", False)), tooltips.get("decryption_ok", "")),
            build_tooltip_text("dh_count", str(bob_result.get("dh_count", "-")), tooltips.get("dh_count", "")),
            *(extra_bob_result_controls or []),
            build_tooltip_text(
                "decrypted_text",
                _short(str(bob_result.get("decrypted_text", "-")), 24),
                tooltips.get("decrypted_text", ""),
                full_value=str(bob_result.get("decrypted_text", "-")),
                on_click=make_copy_handler(page, "decrypted_text", str(bob_result.get("decrypted_text", "-"))) if page is not None else None,
            ),
        ])

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
                ft.Text(
                    "Disabled until Phase 2 is complete." if not enabled else "",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Row([alice_panel, bob_panel], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=8,
        ),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
        padding=12,
    )


def build_key_exchange_layout(
    header_controls: list[ft.Control],
    phase_controls: list[ft.Control],
    summary_section: ft.Control,
    events: list[Any],
    tooltips: dict[str, str],
) -> ft.Control:
    left_panel = ft.Column(
        controls=phase_controls,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    timeline_panel = ft.Column(
        controls=[
            summary_section,
            ft.Divider(height=8),
            build_tooltip_text("timeline", "Timeline", tooltips.get("timeline", "")),
            _build_event_timeline(events, tooltips, max_items=20),
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


__all__ = [
    "phase_ready",
    "_short",
    "_build_tooltip_value",
    "_build_event_timeline",
    "build_message_phase_container",
    "build_key_exchange_layout",
]
FAMILY_ID = "key_exchange"
