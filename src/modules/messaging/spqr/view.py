from __future__ import annotations

import flet as ft

from components.data_classes import SpqrSessionState, SpqrRatchetState
from modules.base_view import format_key
from modules.messaging.messaging_base_view import (
    is_party_visible, build_key_field, get_key_tooltip_text, SIDE_PANEL_WIDTH,
    build_timeline_column, collect_timeline_items, pqxdh_header_preview, find_bob_pqxdh_header,
    build_timeline_entry, build_received_row_controls, build_pending_row_controls,
    resolve_received_body, resolve_pending_body, append_pqxdh_bootstrap_buttons,
)
from modules.tooltip_helpers import get_tooltip_messages

"""SPQR UI view builders.

Provides `build_visual` and timeline builders used by the SPQR messaging UI.
These helpers compose party panels, key-history views and timeline entries
so the application can render the SPQR demo screens.
"""



def _active_chain_values(state: SpqrRatchetState | None) -> tuple[str, str]:
    if state is None:
        return "None", "None"
    chains = state.kdfchains.get(state.epoch)
    if chains is None:
        return "None", "None"
    send_ck = format_key(chains.send.CK) if chains.send is not None else "None"
    recv_ck = format_key(chains.receive.CK) if chains.receive is not None else "None"
    return send_ck, recv_ck


def _build_party_panel(
    page: ft.Page,
    state: SpqrRatchetState | None,
    party_name: str,
    perspective: str,
    message_input: ft.TextField | None = None,
    on_send=None,
) -> ft.Control:
    if state is None:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(party_name, size=18, weight="bold"),
                    ft.Text("Not initialized yet", color=ft.Colors.OUTLINE),
                ],
                spacing=4,
                tight=True,
            ),
            width=SIDE_PANEL_WIDTH,
            padding=10,
        )

    visible = is_party_visible(perspective, party_name)
    send_ck, recv_ck = _active_chain_values(state)
    state_name = type(state.scka_state.node).__name__ if state.scka_state is not None and state.scka_state.node is not None else "None"

    tooltips = get_tooltip_messages("spqr")
    rk_full = format_key(state.RK)

    controls: list[ft.Control] = [
        ft.Text(party_name, size=18, weight="bold"),
        ft.Text(f"Direction: {state.direction}"),
        ft.Text(f"Epoch: {state.epoch}"),
        ft.Text(f"SCKA state: {state_name}"),
        build_key_field(page, visible, "RK", rk_full, tooltips.get("spqr_step_rk", "")),
        build_key_field(page, visible, "CK_send", send_ck, tooltips.get("CK_send", "")),
        build_key_field(page, visible, "CK_recv", recv_ck, tooltips.get("CK_recv", "")),
        ft.Text(f"Skipped MK epochs: {len(state.MKSKIPPED)}"),
    ]

    if message_input is not None and on_send is not None:
        controls.extend([ft.Divider(height=10), message_input, ft.Button("Send", on_click=on_send)])

    return ft.Container(
        content=ft.Column(controls, spacing=4, tight=True),
        width=SIDE_PANEL_WIDTH,
        padding=10,
    )


def _build_used_keys_history_panel(page: ft.Page, state: SpqrRatchetState | None, party_name: str, perspective: str) -> ft.Control:
    visible = is_party_visible(perspective, party_name)

    panel_controls: list[ft.Control] = [
        ft.Row(
            [
                ft.Text("Used keys history", weight="bold", size=14),
            ],
            spacing=2,
        ),
    ]

    if state is None:
        panel_controls.append(ft.Text("Not initialized", color=ft.Colors.OUTLINE))
    elif not visible:
        panel_controls.append(ft.Text("Hidden", color=ft.Colors.OUTLINE))
    else:
        sections: list[tuple[str, list]] = [
            ("RK", state.key_history.rk_events),
            ("CK_s", state.key_history.cks_events),
            ("CK_r", state.key_history.ckr_events),
        ]

        for section_label, events in sections:
            panel_controls.append(ft.Text(section_label, weight="bold", size=12))
            ordered_events = list(reversed(events))
            if not ordered_events:
                panel_controls.append(ft.Text("-", color=ft.Colors.OUTLINE))
                continue
            for event in ordered_events:
                key_text = event.key_value.hex() if isinstance(event.key_value, bytes) else str(event.key_value)
                label = f"{event.key_type}#{event.key_number} ({event.created_at_step})"
                panel_controls.append(
                    build_key_field(
                        page,
                        visible,
                        label,
                        key_text,
                        get_key_tooltip_text(event),
                    )
                )

    return ft.Container(
        content=ft.Column(
            panel_controls,
            spacing=2,
            tight=False,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=SIDE_PANEL_WIDTH,
        expand=True,
        padding=8,
        border_radius=8,
    )


def build_timeline(
    session: SpqrSessionState,
    perspective: str,
    page: ft.Page,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
    on_show_send_visualization=None,
    on_show_receive_visualization=None,
    on_show_alice_pqxdh_bootstrap=None,
    on_show_bob_pqxdh_bootstrap=None,
) -> ft.Control:
    perspective_key = perspective.lower()
    col = build_timeline_column()
    bob_pqxdh_header = find_bob_pqxdh_header(session.message_log)

    for seq_id, kind, entry in sorted(
        collect_timeline_items(session.message_log, pending_messages),
        key=lambda item: item[0], reverse=True,
    ):
        if kind == "received":
            sender = entry.sender
            receiver = entry.receiver
            header = entry.header
            header_text = f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}" if header is not None else ""
            body = resolve_received_body(perspective_key, sender, entry.plaintext, entry.decrypted_by_receiver, entry.cipher)
            row_controls = build_received_row_controls(seq_id, sender, receiver, on_show_send_visualization, on_show_receive_visualization)
            col.controls.append(build_timeline_entry(row_controls, header_text, body, pqxdh_header_preview(getattr(entry, "pqxdh_header", None))))
        else:
            sender = str(entry.get("sender", ""))
            receiver = str(entry.get("receiver", ""))
            header = entry.get("header")
            header_text = f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}" if header is not None else ""
            body = resolve_pending_body(perspective_key, sender, entry.get("plaintext", b""), entry.get("cipher", b""))
            row_controls = build_pending_row_controls(seq_id, sender, receiver, perspective_key, on_receive_pending, on_show_send_visualization)
            col.controls.append(build_timeline_entry(row_controls, header_text, body, pqxdh_header_preview(entry.get("pqxdh_header")), ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)))

    append_pqxdh_bootstrap_buttons(col, session.alice, session.bob is not None, bob_pqxdh_header, perspective_key, on_show_alice_pqxdh_bootstrap, on_show_bob_pqxdh_bootstrap)
    return col


def build_visual(
    session: SpqrSessionState,
    perspective: str,
    page: ft.Page,
    alice_input: ft.TextField | None = None,
    bob_input: ft.TextField | None = None,
    on_send_alice=None,
    on_send_bob=None,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
    on_show_send_visualization=None,
    on_show_receive_visualization=None,
    on_show_alice_pqxdh_bootstrap=None,
    on_show_bob_pqxdh_bootstrap=None,
) -> ft.Control:
    if session.alice is None:
        return ft.Container(content=ft.Text("SPQR session is not initialized from PQXDH yet."), padding=12)

    page_height = getattr(page, "height", None)
    if page_height is None and getattr(page, "window", None) is not None:
        page_height = getattr(page.window, "height", None)
    if not isinstance(page_height, (int, float)) or page_height <= 0:
        page_height = 900

    timeline_height = max(280, int(page_height * 0.86))

    alice_panel = _build_party_panel(page, session.alice, "Alice", perspective, alice_input, on_send_alice)
    bob_panel = _build_party_panel(page, session.bob, "Bob", perspective, bob_input, on_send_bob)
    
    show_key_history = perspective.lower() != "attacker"
    alice_history = _build_used_keys_history_panel(page, session.alice, "Alice", perspective) if show_key_history else None
    bob_history = _build_used_keys_history_panel(page, session.bob, "Bob", perspective) if show_key_history else None
    
    timeline = build_timeline(
        session,
        perspective,
        page,
        pending_messages=pending_messages,
        on_receive_pending=on_receive_pending,
        on_show_send_visualization=on_show_send_visualization,
        on_show_receive_visualization=on_show_receive_visualization,
        on_show_alice_pqxdh_bootstrap=on_show_alice_pqxdh_bootstrap,
        on_show_bob_pqxdh_bootstrap=on_show_bob_pqxdh_bootstrap,
    )

    timeline_container = ft.Container(
        content=timeline,
        height=timeline_height,
        padding=10,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    alice_controls: list[ft.Control] = [alice_panel]
    bob_controls: list[ft.Control] = [bob_panel]
    if show_key_history and alice_history is not None and bob_history is not None:
        alice_controls.extend([ft.Divider(height=10), alice_history])
        bob_controls.extend([ft.Divider(height=10), bob_history])

    return ft.Row(
        [
            ft.Container(
                ft.Column(alice_controls, spacing=10, tight=False, expand=True),
                width=SIDE_PANEL_WIDTH,
                height=timeline_height,
                padding=10,
            ),
            ft.Container(timeline_container, expand=True, padding=10),
            ft.Container(
                ft.Column(bob_controls, spacing=10, tight=False, expand=True),
                width=SIDE_PANEL_WIDTH,
                height=timeline_height,
                padding=10,
            ),
        ],
        expand=True,
        height=timeline_height,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
