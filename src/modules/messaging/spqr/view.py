from __future__ import annotations

import flet as ft

from components.data_classes import SpqrSessionState, SpqrRatchetState
from modules.base_view import format_key
from modules.messaging.messaging_base_view import is_party_visible, build_key_field, get_key_tooltip_text
from modules.tooltip_helpers import get_tooltip_messages

SIDE_PANEL_WIDTH = 430


def _safe_decode(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.hex()


def _pqxdh_header_preview(pqxdh_header: dict | None) -> str:
    if not isinstance(pqxdh_header, dict):
        return ""

    ik_a = str(pqxdh_header.get("ik_a_public", ""))
    ek_a = str(pqxdh_header.get("ek_a_public", ""))
    bob_spk = str(pqxdh_header.get("bob_spk_public", ""))
    pq_prekey_id = pqxdh_header.get("bob_pq_prekey_id")
    return f"ik_a={ik_a[-8:]}, ek_a={ek_a[-8:]}, spk_b={bob_spk[-8:]}, pq_id={pq_prekey_id}"


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
        build_key_field(page, visible, "RK", rk_full, tooltips.get("RK", "")),
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
    col = ft.Column(
        [
            ft.Row([ft.Text("Message Timeline", weight="bold")], alignment=ft.MainAxisAlignment.CENTER),
        ],
        scroll=ft.ScrollMode.ALWAYS,
        expand=True,
        spacing=6,
    )

    items: list[tuple[int, str, object]] = []
    for message in session.message_log:
        items.append((message.seq_id, "received", message))
    if pending_messages is not None:
        for pending in pending_messages:
            if isinstance(pending.get("id"), int):
                items.append((pending["id"], "pending", pending))

    bob_initialized = session.bob is not None
    bob_pqxdh_header: dict | None = None
    for message in session.message_log:
        header_candidate = getattr(message, "pqxdh_header", None)
        receiver_name = getattr(message, "receiver", "")
        if isinstance(header_candidate, dict) and str(receiver_name).lower() == "bob":
            bob_pqxdh_header = header_candidate
            break

    for seq_id, kind, entry in sorted(items, key=lambda item: item[0], reverse=True):
        if kind == "received":
            sender = entry.sender
            receiver = entry.receiver
            header = entry.header
            sender_view = perspective_key in {"global", sender.lower()}
            receiver_view = perspective_key == receiver.lower()
            body = _safe_decode(entry.plaintext if sender_view else entry.decrypted_by_receiver)
            if not body and receiver_view:
                body = _safe_decode(entry.decrypted_by_receiver)
            if not body:
                body = _safe_decode(entry.cipher)

            row_controls: list[ft.Control] = [ft.Text(f"[{seq_id}] {sender} -> {receiver} | ")]
            if on_show_send_visualization is not None:
                row_controls.append(
                    ft.TextButton("Send steps", on_click=lambda e, sid=seq_id: on_show_send_visualization(sid))
                )
            if on_show_receive_visualization is not None:
                row_controls.append(
                    ft.TextButton("Receive steps", on_click=lambda e, sid=seq_id: on_show_receive_visualization(sid))
                )

            header_text = ""
            if header is not None:
                header_text = f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}"
            pqxdh_text = _pqxdh_header_preview(getattr(entry, "pqxdh_header", None))
            pqxdh_line = ft.Text(f"pqxdh: {pqxdh_text}") if pqxdh_text else None
            col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(row_controls),
                            ft.Text(f"header: {header_text}"),
                            *( [pqxdh_line] if pqxdh_line else [] ),
                            ft.Text(f"message: {body}"),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                    padding=6,
                    border_radius=5,
                )
            )
            continue

        pending = entry
        sender = str(pending.get("sender", ""))
        receiver = str(pending.get("receiver", ""))
        header = pending.get("header")
        cipher = pending.get("cipher", b"")
        plaintext = pending.get("plaintext", b"")
        can_receive = perspective_key in {"global", receiver.lower()}
        row_controls: list[ft.Control] = [ft.Text(f"[{seq_id}] {sender} -> {receiver} | ")]
        if can_receive and on_receive_pending is not None:
            row_controls.append(
                ft.TextButton("Receive", on_click=lambda e, pid=seq_id, who=receiver: on_receive_pending(who, pid))
            )
        else:
            row_controls.append(ft.Text("Pending"))

        if on_show_send_visualization is not None:
            row_controls.append(
                ft.TextButton("Send steps", on_click=lambda e, sid=seq_id: on_show_send_visualization(sid))
            )

        header_text = ""
        if header is not None:
            header_text = f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}"

        pqxdh_header = pending.get("pqxdh_header") if isinstance(pending.get("pqxdh_header"), dict) else None
        pqxdh_text = _pqxdh_header_preview(pqxdh_header)

        body = _safe_decode(plaintext if perspective_key in {"global", sender.lower()} else cipher)
        pqxdh_line = ft.Text(f"pqxdh: {pqxdh_text}") if pqxdh_text else None
        col.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(row_controls),
                        ft.Text(f"header: {header_text}"),
                        *( [pqxdh_line] if pqxdh_line else [] ),
                        ft.Text(f"message: {body}"),
                    ],
                    spacing=2,
                    tight=True,
                ),
                padding=6,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=5,
            )
        )

    bottom_actions: list[ft.Control] = []
    if on_show_alice_pqxdh_bootstrap is not None and session.alice is not None and perspective_key in {"global", "alice"}:
        bottom_actions.append(
            ft.TextButton("Show Alice PQXDH initialization", on_click=lambda e: on_show_alice_pqxdh_bootstrap())
        )
    if on_show_bob_pqxdh_bootstrap is not None and bob_initialized and bob_pqxdh_header is not None and perspective_key in {"global", "bob"}:
        bottom_actions.append(
            ft.TextButton(
                "Show Bob PQXDH initialization",
                on_click=lambda e, header=bob_pqxdh_header: on_show_bob_pqxdh_bootstrap(header),
            )
        )
    if bottom_actions:
        col.controls.append(ft.Divider(height=8))
        col.controls.extend(bottom_actions)

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
                ft.Column(alice_controls, spacing=10, tight=False),
                width=SIDE_PANEL_WIDTH,
                height=timeline_height,
                padding=10,
            ),
            ft.Container(timeline_container, expand=True, padding=10),
            ft.Container(
                ft.Column(bob_controls, spacing=10, tight=False),
                width=SIDE_PANEL_WIDTH,
                height=timeline_height,
                padding=10,
            ),
        ],
        expand=True,
        height=timeline_height,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
