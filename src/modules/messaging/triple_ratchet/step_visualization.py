from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import (
    PartyStateSnapshot,
    SendStepVisualizationSnapshot,
    TripleRatchetPartyState,
    TripleRatchetPartyStateSnapshot,
    TripleRatchetReceiveSnapshot,
    TripleRatchetSendSnapshot,
)
from modules.base_steps import (
    func_node,
    normalize_step_titles,
    show_step_dialog,
    var_node,
)
from modules.messaging.messaging_base_steps import (
    build_before_after_panels,
    build_bootstrap_init_step,
    dr_header_preview,
    last_n_chars,
    pqxdh_header_preview,
    spqr_header_preview,
)
from modules.messaging.messaging_base_view import (
    safe_decode_bytes,
    tail_hex,
)


def _snap_dr_rows(snap: TripleRatchetPartyStateSnapshot) -> list[tuple[str, str, str | None, Any]]:
    return [
        ("DHs", last_n_chars(snap.dr_dhs_public), None, snap.dr_dhs_public),
        ("DHr", last_n_chars(snap.dr_dhr) if snap.dr_dhr else "None", None, snap.dr_dhr),
        ("RK", tail_hex(snap.dr_rk), None, snap.dr_rk),
        ("CKs", tail_hex(snap.dr_cks) if snap.dr_cks else "None", None, snap.dr_cks),
        ("CKr", tail_hex(snap.dr_ckr) if snap.dr_ckr else "None", None, snap.dr_ckr),
        ("Ns", str(snap.dr_ns), None, snap.dr_ns),
        ("Nr", str(snap.dr_nr), None, snap.dr_nr),
        ("PN", str(snap.dr_pn), None, snap.dr_pn),
    ]


def _snap_spqr_rows(snap: TripleRatchetPartyStateSnapshot) -> list[tuple[str, str, str | None, Any]]:
    return [
        ("State", snap.spqr_state_name or "Unknown", None, snap.spqr_state_name),
        ("Epoch", str(snap.spqr_epoch), None, snap.spqr_epoch),
        ("Direction", snap.spqr_direction or "-", None, snap.spqr_direction),
        ("RK", tail_hex(snap.spqr_rk) if snap.spqr_rk else "None", None, snap.spqr_rk),
    ]


def _build_spqr_step_snapshot(snap: TripleRatchetPartyStateSnapshot) -> dict[str, Any]:
    if isinstance(snap.spqr_snapshot, dict) and snap.spqr_snapshot:
        return snap.spqr_snapshot
    state_name = snap.spqr_state_name or "Unknown"
    return {
        "state": state_name,
        "node": state_name,
        "epoch": snap.spqr_epoch,
        "direction": snap.spqr_direction,
        "rk_tail": tail_hex(snap.spqr_rk),
        "send_ck_tail": tail_hex(snap.spqr_send_ck),
        "recv_ck_tail": tail_hex(snap.spqr_recv_ck),
        "scka_node": snap.spqr_scka_node or {},
    }


def _changed_labels(before_rows: list, after_rows: list) -> set[str]:
    bv = {label: val for label, val, *_ in before_rows}
    av = {label: val for label, val, *_ in after_rows}
    return {label for label, value in bv.items() if value != av.get(label)}


def _build_dual_state_step(
    title: str,
    before: TripleRatchetPartyStateSnapshot,
    after: TripleRatchetPartyStateSnapshot,
    actor: str,
) -> dict[str, Any]:
    """Build a before/after step panel showing both DR and SPQR state."""
    dr_before = _snap_dr_rows(before)
    dr_after = _snap_dr_rows(after)
    spqr_before = _snap_spqr_rows(before)
    spqr_after = _snap_spqr_rows(after)
    dr_hl = _changed_labels(dr_before, dr_after)
    spqr_hl = _changed_labels(spqr_before, spqr_after)
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                ft.Text("Double Ratchet state", size=13, italic=True),
                build_before_after_panels(
                    f"{actor} (DR) — before",
                    dr_before,
                    f"{actor} (DR) — after",
                    dr_after,
                    highlight_labels=dr_hl,
                ),
                ft.Divider(),
                ft.Text("SPQR state", size=13, italic=True),
                build_before_after_panels(
                    f"{actor} (SPQR) — before",
                    spqr_before,
                    f"{actor} (SPQR) — after",
                    spqr_after,
                    highlight_labels=spqr_hl,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_key_combination_step(
    ec_mk: bytes,
    pq_mk: bytes,
    mk: bytes,
) -> dict[str, Any]:
    title = "Message key combination: KDF_HYBRID(ec_mk, pq_mk)"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                ft.Row(
                    controls=[
                        var_node("ec_mk", value=tail_hex(ec_mk), full_value=ec_mk.hex(), width=220),
                        var_node("pq_mk (SPQR)", value=tail_hex(pq_mk), full_value=pq_mk.hex(), width=220),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Text("↓", size=24),
                func_node("KDF_HYBRID", width=260, height=70),
                ft.Text("↓", size=24),
                var_node("mk", value=tail_hex(mk), full_value=mk.hex(), width=260),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_dr_receiving_step(snapshot: TripleRatchetReceiveSnapshot, page: ft.Page, on_close: Callable[[], None] | None = None) -> dict[str, Any]:
    from modules.messaging.double_ratchet.step_visualization import build_dr_receive_phase2_steps
    from modules.tooltip_helpers import get_tooltip_messages

    dr = snapshot.header.dr
    dr_preview = f"dh={last_n_chars(dr.dh)}, pn={dr.pn}, n={dr.n}"

    def show_dr_visualization() -> None:
        if snapshot.dr_snapshot is None:
            return
        tooltips = get_tooltip_messages("double_ratchet")
        steps = build_dr_receive_phase2_steps(snapshot.dr_snapshot, tooltips)
        normalize_step_titles(steps)
        show_step_dialog(page, "DR receiving steps", steps, on_close=None)

    title = "DR receiving steps"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                var_node("DR header", value=dr_preview, full_value=dr, width=280),
                ft.Text("↓", size=16),
                func_node("Double Ratchet receive steps", width=220, height=70),
                ft.Text("↓", size=16),
                var_node("ec_mk", value=tail_hex(snapshot.ec_mk), full_value=snapshot.ec_mk.hex(), width=220),
                ft.Button(
                    "Show DR steps",
                    on_click=lambda e: show_dr_visualization(),
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_dr_sending_step(snapshot: TripleRatchetSendSnapshot, page: ft.Page, on_close: Callable[[], None] | None = None) -> dict[str, Any]:
    from modules.messaging.double_ratchet.step_visualization import build_dr_send_phase2_steps
    from modules.tooltip_helpers import get_tooltip_messages

    dr = snapshot.header.dr
    dr_preview = f"dh={last_n_chars(dr.dh)}, pn={dr.pn}, n={dr.n}"

    def show_dr_visualization() -> None:
        dr_before = PartyStateSnapshot(
            DHs_public=snapshot.before.dr_dhs_public,
            DHs_private=snapshot.before.dr_dhs_private,
            DHr=snapshot.before.dr_dhr,
            RK=snapshot.before.dr_rk,
            CKs=snapshot.before.dr_cks,
            CKr=snapshot.before.dr_ckr,
            Ns=snapshot.before.dr_ns,
            Nr=snapshot.before.dr_nr,
            PN=snapshot.before.dr_pn,
        )
        dr_after = PartyStateSnapshot(
            DHs_public=snapshot.after.dr_dhs_public,
            DHs_private=snapshot.after.dr_dhs_private,
            DHr=snapshot.after.dr_dhr,
            RK=snapshot.after.dr_rk,
            CKs=snapshot.after.dr_cks,
            CKr=snapshot.after.dr_ckr,
            Ns=snapshot.after.dr_ns,
            Nr=snapshot.after.dr_nr,
            PN=snapshot.after.dr_pn,
        )
        dr_snapshot_inner = SendStepVisualizationSnapshot(
            sender=snapshot.sender,
            receiver=snapshot.receiver,
            plaintext=snapshot.plaintext,
            header=dr,
            cipher=snapshot.cipher,
            mk=snapshot.ec_mk,
            pending_id=snapshot.pending_id,
            before=dr_before,
            after=dr_after,
        )
        tooltips = get_tooltip_messages("double_ratchet")
        steps = build_dr_send_phase2_steps(dr_snapshot_inner, tooltips)
        normalize_step_titles(steps)
        show_step_dialog(page, "DR sending steps", steps, on_close=None)

    title = "DR sending steps"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                var_node("DR header", value=dr_preview, full_value=dr, width=280),
                ft.Text("↓", size=16),
                func_node("Double Ratchet send steps", width=220, height=70),
                ft.Text("↓", size=16),
                var_node("ec_mk", value=tail_hex(snapshot.ec_mk), full_value=snapshot.ec_mk.hex(), width=220),
                ft.Button(
                    "Show DR steps",
                    on_click=lambda e: show_dr_visualization(),
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_spqr_sending_step(snapshot: TripleRatchetSendSnapshot, page: ft.Page, on_close: Callable[[], None] | None = None) -> dict[str, Any]:
    from modules.messaging.spqr.step_visualization import build_spqr_send_phase2_steps
    from modules.tooltip_helpers import get_tooltip_messages

    spqr = snapshot.header.spqr
    spqr_preview = f"epoch={spqr.msg.epoch}, type={spqr.msg.msg_type.value}, n={spqr.n}"

    def show_spqr_visualization() -> None:
        spqr_step_data = {
            "action": "send",
            "before": _build_spqr_step_snapshot(snapshot.before),
            "after": _build_spqr_step_snapshot(snapshot.after),
            "header": spqr,
            "encrypt_trace": snapshot.spqr_trace,
            "pqxdh_header": snapshot.pqxdh_header,
        }
        tooltips = {**get_tooltip_messages("spqr"), **get_tooltip_messages("pqxdh")}
        steps = build_spqr_send_phase2_steps(spqr_step_data, tooltips)
        normalize_step_titles(steps)
        show_step_dialog(page, "SPQR sending steps", steps, on_close=None)

    title = "SPQR sending steps"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                var_node("SPQR header", value=spqr_preview, full_value=spqr, width=280),
                ft.Text("↓", size=16),
                func_node("SPQR send steps", width=220, height=70),
                ft.Text("↓", size=16),
                var_node("pq_mk", value=tail_hex(snapshot.pq_mk), full_value=snapshot.pq_mk.hex(), width=220),
                ft.Button(
                    "Show SPQR steps",
                    on_click=lambda e: show_spqr_visualization(),
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_send_header_step(snapshot: TripleRatchetSendSnapshot) -> dict[str, Any]:
    dr = snapshot.header.dr
    spqr = snapshot.header.spqr
    pqxdh = getattr(snapshot, "pqxdh_header", None)

    dr_preview = f"dh={last_n_chars(dr.dh)}, pn={dr.pn}, n={dr.n}"
    spqr_preview = f"epoch={spqr.msg.epoch}, type={spqr.msg.msg_type.value}, n={spqr.n}"
    pqxdh_preview = pqxdh_header_preview(pqxdh) if pqxdh is not None else None

    title = "Header combination"

    inputs = [
        var_node("DR header", value=dr_preview, full_value=dr, width=280),
        var_node("SPQR header", value=spqr_preview, full_value=spqr, width=280),
    ]
    if pqxdh_preview is not None:
        inputs.append(var_node("PQXDH header", value=pqxdh_preview, full_value=pqxdh, width=420))

    combined_value = f"dr: {dr_preview} | spqr: {spqr_preview}"
    if pqxdh_preview is not None:
        combined_value += f" | pqxdh: {pqxdh_preview}"

    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                ft.Row(
                    controls=inputs,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    wrap=True,
                ),
                ft.Text("↓", size=24),
                func_node("COMBINE", width=260, height=70),
                ft.Text("↓", size=24),
                var_node("TripleRatchetHeader", value=combined_value, full_value=snapshot.header, width=620),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_spqr_receiving_step(snapshot: TripleRatchetReceiveSnapshot, page: ft.Page, on_close: Callable[[], None] | None = None) -> dict[str, Any]:
    from modules.messaging.spqr.step_visualization import build_spqr_receive_phase2_steps
    from modules.tooltip_helpers import get_tooltip_messages

    spqr = snapshot.header.spqr
    spqr_preview = f"epoch={spqr.msg.epoch}, type={spqr.msg.msg_type.value}, n={spqr.n}"

    def show_spqr_visualization() -> None:
        spqr_step_data = {
            "action": "receive",
            "before": _build_spqr_step_snapshot(snapshot.before),
            "after": _build_spqr_step_snapshot(snapshot.after),
            "header": spqr,
            "receive_trace": snapshot.spqr_trace,
            "pqxdh_header": snapshot.pqxdh_header,
        }
        tooltips = {**get_tooltip_messages("spqr"), **get_tooltip_messages("pqxdh")}
        steps = build_spqr_receive_phase2_steps(spqr_step_data, tooltips)
        normalize_step_titles(steps)
        show_step_dialog(page, "SPQR receiving steps", steps, on_close=None)

    title = "SPQR receiving steps"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                var_node("SPQR header", value=spqr_preview, full_value=spqr, width=280),
                ft.Text("↓", size=16),
                func_node("SPQR receive steps", width=220, height=70),
                ft.Text("↓", size=16),
                var_node("pq_mk", value=tail_hex(snapshot.pq_mk), full_value=snapshot.pq_mk.hex(), width=220),
                ft.Button(
                    "Show SPQR steps",
                    on_click=lambda e: show_spqr_visualization(),
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def _build_bob_initialization_step(
    snapshot: TripleRatchetReceiveSnapshot,
    on_show_bootstrap: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    if not snapshot.was_pqxdh_bootstrapped or not snapshot.pqxdh_header:
        return None
    return build_bootstrap_init_step(
        title="PQXDH initialization (Bob bootstrap)",
        was_bootstrapped=snapshot.was_pqxdh_bootstrapped,
        protocol_header_label="PQXDH header",
        protocol_header_preview=pqxdh_header_preview(snapshot.pqxdh_header),
        protocol_header_full=snapshot.pqxdh_header,
        on_show_bootstrap=on_show_bootstrap,
        button_label="Show Bob PQXDH bootstrap",
        bootstrap_fn_label="PQXDH Bootstrap",
        bootstrap_fn_value="Initialize Triple Ratchet DR and SPQR states from PQXDH",
        result_text="Bob DR and SPQR states initialized during this receive",
        party_initialized_text="Bob already initialized",
        party_not_initialized_text="Bob not initialized yet",
        party_width=320,
        protocol_header_width=420,
        bootstrap_fn_width=360,
        bootstrap_fn_height=90,
    )


def _build_receive_header_step(snapshot: TripleRatchetReceiveSnapshot) -> dict[str, Any]:
    dr = snapshot.header.dr
    spqr = snapshot.header.spqr
    pqxdh = snapshot.pqxdh_header
    dr_preview = dr_header_preview(dr.dh, dr.pn, dr.n)
    spqr_preview = spqr_header_preview(spqr)

    split_outputs = [
        var_node("DR header", value=dr_preview, full_value=dr, width=280),
        var_node("SPQR header", value=spqr_preview, full_value=spqr, width=300),
    ]
    if pqxdh is not None:
        split_outputs.append(
            var_node("PQXDH header", value=pqxdh_header_preview(pqxdh), full_value=pqxdh, width=420)
        )

    title = "Triple Ratchet header extraction"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                var_node(
                    "Triple Ratchet header",
                    value=f"dr: {dr_preview} | spqr: {spqr_preview}",
                    full_value=snapshot.header,
                    width=620,
                ),
                ft.Text("↓", size=24),
                func_node("SPLIT", width=220, height=70),
                ft.Text("↓", size=24),
                ft.Row(
                    controls=split_outputs,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    wrap=True,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def show_triple_ratchet_send_step_dialog(
    page: ft.Page,
    snapshot: TripleRatchetSendSnapshot,
    on_close: Callable[[], None] | None = None,
) -> None:
    plaintext_str = safe_decode_bytes(snapshot.plaintext)
    cipher_preview = tail_hex(snapshot.cipher, 16)
    combined_preview = tail_hex(snapshot.mk)

    steps: list[dict[str, Any]] = []

    # 1. State before send
    steps.append(_build_dual_state_step(
        f"State before send (sender: {snapshot.sender})",
        snapshot.before,
        snapshot.before,
        snapshot.sender,
    ))

    # 2. DR sending steps
    steps.append(_build_dr_sending_step(snapshot, page, on_close))

    # 3. SPQR sending steps
    steps.append(_build_spqr_sending_step(snapshot, page, on_close))

    # 4. Header combination
    steps.append(_build_send_header_step(snapshot))

    # 5. Key combination
    steps.append(_build_key_combination_step(snapshot.ec_mk, snapshot.pq_mk, snapshot.mk))

    # 6. Encryption result
    steps.append({
        "title": "Encryption",
        "control": ft.Column(
            controls=[
                ft.Text("Encryption", weight="bold"),
                ft.Row(
                    controls=[
                        var_node("plaintext", value=plaintext_str, full_value=plaintext_str),
                        var_node("mk", value=combined_preview, full_value=snapshot.mk.hex()),
                        var_node("AD || header"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    wrap=True,
                ),
                ft.Text("↓", size=24),
                func_node("ENCRYPT", width=320, height=70),
                ft.Text("↓", size=24),
                var_node("ciphertext", value=cipher_preview, full_value=snapshot.cipher.hex(), width=320),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    })

    # 7. State after send
    steps.append(_build_dual_state_step(
        f"State after send (sender: {snapshot.sender})",
        snapshot.before,
        snapshot.after,
        snapshot.sender,
    ))

    normalize_step_titles(steps)
    show_step_dialog(
        page,
        dialog_title=f"Triple Ratchet — Send step #{snapshot.pending_id} ({snapshot.sender} → {snapshot.receiver})",
        steps=steps,
        on_close=on_close,
    )


def show_triple_ratchet_receive_step_dialog(
    page: ft.Page,
    snapshot: TripleRatchetReceiveSnapshot,
    on_show_bootstrap: Callable[[], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    decrypted_str = safe_decode_bytes(snapshot.decrypted)
    cipher_preview = tail_hex(snapshot.cipher, 16)
    combined_preview = tail_hex(snapshot.mk)

    steps: list[dict[str, Any]] = []

    # 1. State before receive
    steps.append(_build_dual_state_step(
        f"State before receive (receiver: {snapshot.receiver})",
        snapshot.before,
        snapshot.before,
        snapshot.receiver,
    ))

    # 2. Header extraction (split into DR, SPQR, PQXDH if present)
    steps.append(_build_receive_header_step(snapshot))

    # 3. Bob initialization (if not initialized)
    bob_init_step = _build_bob_initialization_step(snapshot, on_show_bootstrap=on_show_bootstrap)
    if bob_init_step:
        steps.append(bob_init_step)

    # 4. DR receiving step (phase 2)
    steps.append(_build_dr_receiving_step(snapshot, page, on_close))

    # 5. SPQR receiving step (phase 2)
    steps.append(_build_spqr_receiving_step(snapshot, page, on_close))

    # 6. Triple Ratchet message key combination
    steps.append(_build_key_combination_step(snapshot.ec_mk, snapshot.pq_mk, snapshot.mk))

    # 7. Decryption result
    steps.append({
        "title": "Decryption result",
        "control": ft.Column(
            controls=[
                ft.Text("Decryption result", weight="bold"),
                ft.Row(
                    controls=[
                        var_node("ciphertext", value=cipher_preview, full_value=snapshot.cipher.hex()),
                        var_node("mk", value=combined_preview, full_value=snapshot.mk.hex()),
                        var_node("AD|| header")
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Text("↓", size=24),
                func_node("DECRYPT", width=320, height=70),
                ft.Text("↓", size=24),
                var_node("plaintext", value=decrypted_str, full_value=decrypted_str, width=340),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    })

    # 8. State after receive
    steps.append(_build_dual_state_step(
        f"State after receive (receiver: {snapshot.receiver})",
        snapshot.before,
        snapshot.after,
        snapshot.receiver,
    ))

    normalize_step_titles(steps)
    show_step_dialog(
        page,
        dialog_title="Triple Ratchet — Receive step",
        steps=steps,
        on_close=on_close,
    )


def _build_sk_split_step(sk: bytes, sk_dr: bytes, sk_spqr: bytes) -> dict[str, Any]:
    """Build KDF_TR_SPLIT step showing SK being split into sk_dr and sk_spqr."""
    return {
        "title": "PQXDH SK split (KDF_TR_SPLIT)",
        "control": ft.Column(
            controls=[
                ft.Text("PQXDH SK split (KDF_TR_SPLIT)", weight="bold"),
                var_node("SK (PQXDH)", value=tail_hex(sk), full_value=sk.hex(), width=260),
                ft.Text("↓", size=24),
                func_node("Split", width=220, height=70),
                ft.Text("↓", size=24),
                ft.Row(
                    controls=[
                        var_node("sk_dr", value=tail_hex(sk_dr), full_value=sk_dr.hex(), width=200),
                        var_node("sk_spqr", value=tail_hex(sk_spqr), full_value=sk_spqr.hex(), width=200),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def show_alice_pqxdh_bootstrap_visualization_dialog(
    page: ft.Page,
    pqxdh_state_data: dict[str, Any] | None,
    spqr_rk_after_init: bytes | None,
    spqr_cks_after_init: bytes | None,
    alice_scka_state: Any,
    dr_rk_after_init: bytes | None,
    dr_cks_after_init: bytes | None,
    session_ad: bytes,
    alice_dhs_pub: str = "",
    alice_dhs_priv: str = "",
    sk: bytes | None = None,
) -> None:
    from modules.messaging.spqr.step_visualization import build_alice_pqxdh_phase1_steps, build_alice_pqxdh_phase2_steps
    from modules.messaging.double_ratchet.step_visualization import build_alice_x3dh_phase2_steps
    from modules.messaging.triple_ratchet.logic import KDF_TR_SPLIT
    from modules.tooltip_helpers import get_tooltip_messages

    steps: list[dict[str, Any]] = []

    # Phase 1: SPQR Phase 1 (PQXDH headers → SK, AD)
    tooltips_spqr = get_tooltip_messages("spqr")
    steps.extend(build_alice_pqxdh_phase1_steps(pqxdh_state_data, tooltips_spqr))

    # Phase 1.5: SK split
    sk_dr: bytes | None = None
    sk_spqr: bytes | None = None
    if sk is not None:
        sk_dr, sk_spqr = KDF_TR_SPLIT(sk)
        steps.append(_build_sk_split_step(sk, sk_dr, sk_spqr))

    # Phase 2: DR Phase 2 (sk_dr → DR state)
    if sk_dr is not None:
        bob_ik_pub = ""
        if isinstance(pqxdh_state_data, dict):
            last_bundle = pqxdh_state_data.get("last_bundle_for_alice", {})
            if isinstance(last_bundle, dict):
                bob_ik_pub = last_bundle.get("identity_dh_public", "")

        tooltips_dr = get_tooltip_messages("x3dh")
        steps.extend(build_alice_x3dh_phase2_steps(
            sk_dr.hex(), dr_rk_after_init, dr_cks_after_init,
            alice_dhs_pub, alice_dhs_priv, bob_ik_pub,
            tooltips_dr
        ))

    # Phase 2: SPQR Phase 2 (sk_spqr → SPQR state)
    if sk_spqr is not None:
        steps.extend(build_alice_pqxdh_phase2_steps(
            sk_spqr, spqr_rk_after_init, spqr_cks_after_init,
            alice_scka_state, tooltips_spqr
        ))

    normalize_step_titles(steps)
    show_step_dialog(page, "Triple Ratchet Alice PQXDH bootstrap", steps)




def show_bob_pqxdh_bootstrap_visualization_dialog(
    page: ft.Page,
    pqxdh_state_data: dict[str, Any] | None,
    pqxdh_header: dict[str, Any] | None,
    bob: TripleRatchetPartyState,
    session_ad: bytes,
    bob_spk_public: str = "",
    bob_spk_priv: str = "",
    bob_ik_pub: str = "",
    bob_ik_priv: str = "",
    shared_secret: bytes | None = None,
) -> None:
    from modules.messaging.spqr.step_visualization import build_bob_pqxdh_phase1_steps, build_bob_pqxdh_phase2_steps
    from modules.messaging.double_ratchet.step_visualization import build_bob_x3dh_phase2_steps
    from modules.messaging.triple_ratchet.logic import KDF_TR_SPLIT
    from modules.tooltip_helpers import get_tooltip_messages

    bob_spqr = bob.spqr

    bob_ik_public = None
    pq_shared_secret = None
    bob_pq_prekey_public = None
    if isinstance(pqxdh_state_data, dict):
        last_bundle = pqxdh_state_data.get("last_bundle_for_alice")
        if isinstance(last_bundle, dict):
            bob_ik_public = last_bundle.get("identity_dh_public")
        alice_derived = pqxdh_state_data.get("alice_derived")
        if isinstance(alice_derived, dict):
            pq_secret_hex = alice_derived.get("pq_secret")
            if isinstance(pq_secret_hex, str):
                try:
                    pq_shared_secret = bytes.fromhex(pq_secret_hex)
                except ValueError:
                    pass
            pq_prekey_type = alice_derived.get("pq_prekey_type", "")
            if pq_prekey_type == "PQSPK":
                bob_pq_prekey_public = pqxdh_state_data.get("bob_local", {}).get("pqspk", {}).get("public_key")
            else:
                opks = pqxdh_state_data.get("bob_local", {}).get("pqopks", [])
                if opks:
                    bob_pq_prekey_public = opks[0].get("public_key")

    steps: list[dict[str, Any]] = []

    # Phase 1: SPQR Phase 1 (PQXDH headers → SK, AD)
    tooltips_spqr = get_tooltip_messages("spqr")
    steps.extend(build_bob_pqxdh_phase1_steps(
        pqxdh_header, shared_secret, session_ad,
        pq_shared_secret, bob_pq_prekey_public, bob_ik_public,
        tooltips_spqr
    ))

    # Phase 1.5: SK split
    sk_dr: bytes | None = None
    sk_spqr: bytes | None = None
    if shared_secret is not None:
        sk_dr, sk_spqr = KDF_TR_SPLIT(shared_secret)
        steps.append(_build_sk_split_step(shared_secret, sk_dr, sk_spqr))

    # Phase 2: DR Phase 2 (sk_dr → DR state)
    if sk_dr is not None:
        tooltips_dr = get_tooltip_messages("x3dh")
        steps.extend(build_bob_x3dh_phase2_steps(
            sk_dr, session_ad,
            bob_spk_public, bob_spk_priv,
            bob_ik_pub, bob_ik_priv,
            tooltips_dr
        ))

    # Phase 2: SPQR Phase 2 (sk_spqr → SPQR state)
    if sk_spqr is not None:
        steps.extend(build_bob_pqxdh_phase2_steps(
            sk_spqr, session_ad, bob_spqr, tooltips_spqr
        ))

    normalize_step_titles(steps)
    show_step_dialog(page, "Triple Ratchet Bob PQXDH bootstrap", steps)
