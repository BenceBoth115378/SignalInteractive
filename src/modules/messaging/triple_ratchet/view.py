from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import (
    PartyState,
    SpqrRatchetState,
    TripleRatchetMessageState,
    TripleRatchetPartyState,
    TripleRatchetSessionState,
)
from modules.base_view import format_key
from modules.messaging.messaging_base_view import (
    SIDE_PANEL_WIDTH,
    build_key_field,
    get_key_tooltip_text,
    is_party_visible,
    safe_decode_bytes,
)


def _pqxdh_header_preview(pqxdh_header: dict | None) -> str:
    if not isinstance(pqxdh_header, dict):
        return ""
    ik_a = str(pqxdh_header.get("ik_a_public", ""))
    ek_a = str(pqxdh_header.get("ek_a_public", ""))
    bob_spk = str(pqxdh_header.get("bob_spk_public", ""))
    pq_id = pqxdh_header.get("bob_pq_prekey_id")
    return f"ik_a={ik_a[-8:]}, ek_a={ek_a[-8:]}, spk_b={bob_spk[-8:]}, pq_id={pq_id}"


def _build_dr_section(
    page: ft.Page,
    dr: PartyState,
    visible: bool,
) -> list[ft.Control]:
    return [
        ft.Text("Double Ratchet", size=13, weight="bold", color=ft.Colors.PRIMARY),
        build_key_field(page, visible, "RK", format_key(dr.RK), "DR root key"),
        build_key_field(page, visible, "CKs", format_key(dr.CKs) if dr.CKs else "None", "DR sending chain key"),
        build_key_field(page, visible, "CKr", format_key(dr.CKr) if dr.CKr else "None", "DR receiving chain key"),
        build_key_field(page, visible, "DHs", dr.DHs.public[-16:] if dr.DHs else "None", "DR ephemeral DH public key"),
        build_key_field(page, visible, "DHr", dr.DHr[-16:] if dr.DHr else "None", "DR remote DH public key"),
        ft.Text(f"Ns={dr.Ns}, Nr={dr.Nr}, PN={dr.PN}", size=12),
    ]


def _build_spqr_section(
    page: ft.Page,
    spqr: SpqrRatchetState | None,
    visible: bool,
) -> list[ft.Control]:
    if spqr is None:
        return [
            ft.Text("SPQR", size=13, weight="bold", color=ft.Colors.SECONDARY),
            ft.Text("Not initialized", color=ft.Colors.OUTLINE),
        ]
    chains = spqr.kdfchains.get(spqr.epoch)
    send_ck = format_key(chains.send.CK) if chains is not None and chains.send is not None else "None"
    recv_ck = format_key(chains.receive.CK) if chains is not None and chains.receive is not None else "None"
    state_name = type(spqr.scka_state.node).__name__ if spqr.scka_state is not None and spqr.scka_state.node is not None else "None"
    return [
        ft.Text("SPQR", size=13, weight="bold", color=ft.Colors.SECONDARY),
        ft.Text(f"Epoch: {spqr.epoch} | Direction: {spqr.direction} | State: {state_name}", size=12),
        build_key_field(page, visible, "RK", format_key(spqr.RK), "SPQR root key"),
        build_key_field(page, visible, "CK_send", send_ck, "SPQR active sending chain key"),
        build_key_field(page, visible, "CK_recv", recv_ck, "SPQR active receiving chain key"),
    ]


def _build_party_panel(
    page: ft.Page,
    party: TripleRatchetPartyState | None,
    party_name: str,
    perspective: str,
    message_input: ft.TextField | None = None,
    on_send: Callable | None = None,
) -> ft.Control:
    if party is None:
        return ft.Container(
            content=ft.Column(
                [ft.Text(party_name, size=18, weight="bold"), ft.Text("Not initialized yet", color=ft.Colors.OUTLINE)],
                spacing=4, tight=True,
            ),
            width=SIDE_PANEL_WIDTH, padding=10,
        )

    visible = is_party_visible(perspective, party_name)

    controls: list[ft.Control] = [
        ft.Text(party_name, size=18, weight="bold"),
        *_build_dr_section(page, party.dr, visible),
        ft.Divider(height=8),
        *_build_spqr_section(page, party.spqr, visible),
    ]

    if message_input is not None and on_send is not None:
        controls.extend([ft.Divider(height=10), message_input, ft.Button("Send", on_click=on_send)])

    return ft.Container(
        content=ft.Column(controls, spacing=4, tight=True),
        width=SIDE_PANEL_WIDTH, padding=10,
    )


def _build_key_history_panel(
    page: ft.Page,
    party: TripleRatchetPartyState | None,
    party_name: str,
    perspective: str,
) -> ft.Control:
    visible = is_party_visible(perspective, party_name)

    panel: list[ft.Control] = [
        ft.Text("Key history", weight="bold", size=14),
    ]

    if party is None:
        panel.append(ft.Text("Not initialized", color=ft.Colors.OUTLINE))
    elif not visible:
        panel.append(ft.Text("Hidden", color=ft.Colors.OUTLINE))
    else:
        # DR key history
        panel.append(ft.Text("DR", weight="bold", size=12, color=ft.Colors.PRIMARY))
        for section_label, events in [("RK", party.dr.key_history.rk_events), ("CKs", party.dr.key_history.cks_events), ("CKr", party.dr.key_history.ckr_events)]:
            panel.append(ft.Text(section_label, weight="bold", size=11))
            for event in reversed(events):
                key_text = event.key_value.hex() if isinstance(event.key_value, bytes) else str(event.key_value)
                label = f"{event.key_type}#{event.key_number} ({event.created_at_step})"
                panel.append(build_key_field(page, visible, label, key_text, get_key_tooltip_text(event)))

        # SPQR key history
        if party.spqr is not None:
            panel.append(ft.Divider(height=6))
            panel.append(ft.Text("SPQR", weight="bold", size=12, color=ft.Colors.SECONDARY))
            for section_label, events in [("RK", party.spqr.key_history.rk_events), ("CKs", party.spqr.key_history.cks_events), ("CKr", party.spqr.key_history.ckr_events)]:
                panel.append(ft.Text(section_label, weight="bold", size=11))
                for event in reversed(events):
                    key_text = event.key_value.hex() if isinstance(event.key_value, bytes) else str(event.key_value)
                    label = f"{event.key_type}#{event.key_number} ({event.created_at_step})"
                    panel.append(build_key_field(page, visible, label, key_text, get_key_tooltip_text(event)))

    return ft.Container(
        content=ft.Column(panel, spacing=2, tight=False, horizontal_alignment=ft.CrossAxisAlignment.START, scroll=ft.ScrollMode.AUTO),
        width=SIDE_PANEL_WIDTH, expand=True, padding=8, border_radius=8,
    )


def _header_text(msg: TripleRatchetMessageState) -> str:
    if msg.header is None:
        return "No header"
    dr = msg.header.dr
    spqr = msg.header.spqr
    return f"DR: dh={dr.dh[-8:]}, pn={dr.pn}, n={dr.n} | SPQR: epoch={spqr.msg.epoch}, type={spqr.msg.msg_type.value}, n={spqr.n}"


def _pending_header_text(header: Any) -> str:
    if header is None:
        return ""
    try:
        dr = header.dr
        spqr = header.spqr
        return f"DR: dh={dr.dh[-8:]}, pn={dr.pn}, n={dr.n} | SPQR: epoch={spqr.msg.epoch}, type={spqr.msg.msg_type.value}, n={spqr.n}"
    except AttributeError:
        return str(header)


def build_timeline(
    session: TripleRatchetSessionState,
    perspective: str,
    page: ft.Page,
    pending_messages: list[dict] | None = None,
    on_receive_pending: Callable | None = None,
    on_show_send_visualization: Callable | None = None,
    on_show_receive_visualization: Callable | None = None,
    on_show_alice_pqxdh_bootstrap: Callable | None = None,
    on_show_bob_pqxdh_bootstrap: Callable | None = None,
) -> ft.Control:
    perspective_key = perspective.lower()

    col = ft.Column(
        [ft.Row([ft.Text("Message Timeline", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)],
        scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=6,
    )

    items: list[tuple[int, str, Any]] = []
    for msg in session.message_log:
        items.append((msg.seq_id, "received", msg))
    if pending_messages:
        for p in pending_messages:
            if isinstance(p.get("id"), int):
                items.append((p["id"], "pending", p))

    bob_initialized = session.bob is not None
    bob_pqxdh_header: dict | None = None
    for msg in session.message_log:
        h = getattr(msg, "pqxdh_header", None)
        if isinstance(h, dict) and str(getattr(msg, "receiver", "")).lower() == "bob":
            bob_pqxdh_header = h
            break

    for seq_id, kind, entry in sorted(items, key=lambda x: x[0], reverse=True):
        if kind == "received":
            msg: TripleRatchetMessageState = entry
            sender = msg.sender
            receiver = msg.receiver
            sender_view = perspective_key in {"global", sender.lower()}
            body = safe_decode_bytes(msg.plaintext if sender_view else msg.decrypted_by_receiver) or safe_decode_bytes(msg.cipher)

            row_controls: list[ft.Control] = [ft.Text(f"[{seq_id}] {sender} → {receiver} | ")]
            if on_show_send_visualization:
                row_controls.append(ft.TextButton("Send steps", on_click=lambda e, sid=seq_id: on_show_send_visualization(sid)))
            if on_show_receive_visualization:
                row_controls.append(ft.TextButton("Receive steps", on_click=lambda e, sid=seq_id: on_show_receive_visualization(sid)))

            pqxdh_text = _pqxdh_header_preview(getattr(msg, "pqxdh_header", None))
            col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(row_controls),
                            ft.Text(f"header: {_header_text(msg)}", size=11),
                            *([ ft.Text(f"pqxdh: {pqxdh_text}", size=11)] if pqxdh_text else []),
                            ft.Text(f"message: {body}"),
                        ],
                        spacing=2, tight=True,
                    ),
                    padding=6, border_radius=5,
                )
            )

        else:
            pending = entry
            sender = str(pending.get("sender", ""))
            receiver = str(pending.get("receiver", ""))
            header = pending.get("header")
            cipher = pending.get("cipher", b"")
            plaintext = pending.get("plaintext", b"")
            can_receive = perspective_key in {"global", receiver.lower()}

            row_controls = [ft.Text(f"[{seq_id}] {sender} → {receiver} | ")]
            if can_receive and on_receive_pending:
                row_controls.append(ft.TextButton("Receive", on_click=lambda e, pid=seq_id, who=receiver: on_receive_pending(who, pid)))
            else:
                row_controls.append(ft.Text("Pending"))
            if on_show_send_visualization:
                row_controls.append(ft.TextButton("Send steps", on_click=lambda e, sid=seq_id: on_show_send_visualization(sid)))

            pqxdh_text = _pqxdh_header_preview(pending.get("pqxdh_header"))
            body = safe_decode_bytes(plaintext if perspective_key in {"global", sender.lower()} else cipher)
            col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(row_controls),
                            ft.Text(f"header: {_pending_header_text(header)}", size=11),
                            *([ ft.Text(f"pqxdh: {pqxdh_text}", size=11)] if pqxdh_text else []),
                            ft.Text(f"message: {body}"),
                        ],
                        spacing=2, tight=True,
                    ),
                    padding=6, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=5,
                )
            )

    bottom: list[ft.Control] = []
    if on_show_alice_pqxdh_bootstrap and session.alice is not None and perspective_key in {"global", "alice"}:
        bottom.append(ft.TextButton("Show Alice PQXDH initialization", on_click=lambda e: on_show_alice_pqxdh_bootstrap()))
    if on_show_bob_pqxdh_bootstrap and bob_initialized and bob_pqxdh_header is not None and perspective_key in {"global", "bob"}:
        bottom.append(ft.TextButton("Show Bob PQXDH initialization", on_click=lambda e, h=bob_pqxdh_header: on_show_bob_pqxdh_bootstrap(h)))
    if bottom:
        col.controls.append(ft.Divider(height=8))
        col.controls.extend(bottom)

    return col


def build_visual(
    session: TripleRatchetSessionState,
    perspective: str,
    page: ft.Page,
    alice_input: ft.TextField | None = None,
    bob_input: ft.TextField | None = None,
    on_send_alice: Callable | None = None,
    on_send_bob: Callable | None = None,
    pending_messages: list[dict] | None = None,
    on_receive_pending: Callable | None = None,
    on_show_send_visualization: Callable | None = None,
    on_show_receive_visualization: Callable | None = None,
    on_show_alice_pqxdh_bootstrap: Callable | None = None,
    on_show_bob_pqxdh_bootstrap: Callable | None = None,
) -> ft.Control:
    if session.alice is None:
        return ft.Container(
            content=ft.Text("Triple Ratchet session is not initialized from PQXDH yet."), padding=12
        )

    page_height = getattr(page, "height", None)
    if page_height is None and getattr(page, "window", None) is not None:
        page_height = getattr(page.window, "height", None)
    if not isinstance(page_height, (int, float)) or page_height <= 0:
        page_height = 900

    timeline_height = max(280, int(page_height * 0.86))

    alice_panel = _build_party_panel(page, session.alice, "Alice", perspective, alice_input, on_send_alice)
    bob_panel = _build_party_panel(page, session.bob, "Bob", perspective, bob_input, on_send_bob)

    show_key_history = perspective.lower() != "attacker"
    alice_history = _build_key_history_panel(page, session.alice, "Alice", perspective) if show_key_history else None
    bob_history = _build_key_history_panel(page, session.bob, "Bob", perspective) if show_key_history else None

    timeline = build_timeline(
        session, perspective, page,
        pending_messages=pending_messages,
        on_receive_pending=on_receive_pending,
        on_show_send_visualization=on_show_send_visualization,
        on_show_receive_visualization=on_show_receive_visualization,
        on_show_alice_pqxdh_bootstrap=on_show_alice_pqxdh_bootstrap,
        on_show_bob_pqxdh_bootstrap=on_show_bob_pqxdh_bootstrap,
    )

    timeline_container = ft.Container(content=timeline, height=timeline_height, padding=10, clip_behavior=ft.ClipBehavior.HARD_EDGE)

    alice_controls: list[ft.Control] = [alice_panel]
    bob_controls: list[ft.Control] = [bob_panel]
    if show_key_history and alice_history and bob_history:
        alice_controls.extend([ft.Divider(height=10), alice_history])
        bob_controls.extend([ft.Divider(height=10), bob_history])

    return ft.Row(
        controls=[
            ft.Column(alice_controls, scroll=ft.ScrollMode.AUTO, expand=False),
            ft.VerticalDivider(width=1),
            ft.Column([timeline_container], expand=True),
            ft.VerticalDivider(width=1),
            ft.Column(bob_controls, scroll=ft.ScrollMode.AUTO, expand=False),
        ],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
