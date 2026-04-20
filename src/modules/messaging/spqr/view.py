from __future__ import annotations

import flet as ft

from components.data_classes import SpqrSessionState, SpqrRatchetState
from modules.base_view import format_key, last_n_chars, make_copy_handler
from modules.messaging.messaging_base_view import is_party_visible

SIDE_PANEL_WIDTH = 360


def _safe_decode(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.hex()


def _active_chain_values(state: SpqrRatchetState) -> tuple[str, str]:
    chains = state.kdfchains.get(state.epoch)
    if chains is None:
        return "None", "None"
    send_ck = format_key(chains.send.CK) if chains.send is not None else "None"
    recv_ck = format_key(chains.receive.CK) if chains.receive is not None else "None"
    return send_ck, recv_ck


def _build_party_panel(
    page: ft.Page,
    state: SpqrRatchetState,
    party_name: str,
    perspective: str,
    message_input: ft.TextField | None = None,
    on_send=None,
) -> ft.Control:
    visible = is_party_visible(perspective, party_name)
    send_ck, recv_ck = _active_chain_values(state)
    state_name = type(state.scka_state.node).__name__ if state.scka_state is not None and state.scka_state.node is not None else "None"

    def _field(label: str, value: str, copy_value: str | None = None) -> ft.Control:
        display = last_n_chars(value, 8) if visible and value not in {"None", ""} else (value if visible else "Hidden")
        return ft.Row(
            [
                ft.Text(f"{label}: ", weight=ft.FontWeight.W_600),
                ft.TextButton(
                    display,
                    on_click=make_copy_handler(page, f"{party_name} {label}", copy_value or value),
                    disabled=not visible or not value or value == "None",
                ),
            ],
            spacing=2,
        )

    controls: list[ft.Control] = [
        ft.Text(party_name, size=18, weight="bold"),
        ft.Text(f"Direction: {state.direction}"),
        ft.Text(f"Epoch: {state.epoch}"),
        ft.Text(f"SCKA state: {state_name}"),
        _field("RK", format_key(state.RK)),
        _field("CK_send", send_ck),
        _field("CK_recv", recv_ck),
        ft.Text(f"Skipped MK epochs: {len(state.MKSKIPPED)}"),
    ]

    if message_input is not None and on_send is not None:
        controls.extend([ft.Divider(height=10), message_input, ft.Button("Send", on_click=on_send)])

    return ft.Container(
        content=ft.Column(controls, spacing=4, tight=True),
        width=SIDE_PANEL_WIDTH,
        padding=10,
    )


def build_timeline(
    session: SpqrSessionState,
    perspective: str,
    page: ft.Page,
    pending_messages: list[dict] | None = None,
    on_receive_pending=None,
    on_show_send_visualization=None,
    on_show_receive_visualization=None,
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
            col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(row_controls),
                            ft.Text(f"header: {header_text}"),
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

        body = _safe_decode(plaintext if perspective_key in {"global", sender.lower()} else cipher)
        col.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(row_controls),
                        ft.Text(f"header: {header_text}"),
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
) -> ft.Control:
    if session.alice is None or session.bob is None:
        return ft.Container(content=ft.Text("SPQR session is not initialized."), padding=12)

    page_height = getattr(page, "height", None)
    if page_height is None and getattr(page, "window", None) is not None:
        page_height = getattr(page.window, "height", None)
    if not isinstance(page_height, (int, float)) or page_height <= 0:
        page_height = 900

    timeline_height = max(280, int(page_height * 0.86))

    alice_panel = _build_party_panel(page, session.alice, "Alice", perspective, alice_input, on_send_alice)
    bob_panel = _build_party_panel(page, session.bob, "Bob", perspective, bob_input, on_send_bob)
    timeline = build_timeline(
        session,
        perspective,
        page,
        pending_messages=pending_messages,
        on_receive_pending=on_receive_pending,
        on_show_send_visualization=on_show_send_visualization,
        on_show_receive_visualization=on_show_receive_visualization,
    )

    return ft.Row(
        [
            ft.Container(ft.Column([alice_panel], expand=True), expand=True, height=timeline_height, padding=10),
            ft.Container(ft.Container(content=timeline, height=timeline_height, padding=10), expand=True, padding=10),
            ft.Container(ft.Column([bob_panel], expand=True), expand=True, height=timeline_height, padding=10),
        ],
        expand=True,
        height=timeline_height,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
