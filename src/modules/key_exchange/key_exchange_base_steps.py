"""Shared step-visualization helpers for key-exchange protocols.

The functions here assemble the common diagram fragments used by both X3DH
and PQXDH when showing how keys are generated, signed, exchanged, and used to
derive the final shared secret. Protocol-specific visualizers compose these
helpers to keep the step dialogs compact and consistent.
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from modules.base_steps import (
    func_node,
    party_state_panel,
    to_text,
    var_node,
    with_tooltip,
)
from modules.base_view import last_n_chars

state_panel = party_state_panel


def preview(value: Any, limit: int = 28) -> str:
    text = to_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def last_key_chars(value: Any, count: int = 10) -> str:
    text = to_text(value)
    if text in {"", "None", "-"}:
        return text
    return last_n_chars(text, count)


def build_generate_alice_core_steps(
    *,
    before_alice_rows: list[tuple[str, str, str | None, Any]],
    before_server_rows: list[tuple[str, str, str | None, Any]],
    before_alice_panel_title: str,
    before_server_panel_title: str,
    pre_state_text: str,
    ik_public: Any,
    ik_private: Any,
    spk_public: Any,
    spk_private: Any,
    spk_signature: Any,
    opk_count: int,
    opk_keys: list[Any],
    first_opk_pub: Any,
    first_opk_priv: Any,
    first_opk_id: Any,
    sign_output_label: str,
    opk_id_label: str,
    opk_id_value: str,
    tooltips: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    tips = tooltips or {}

    step1 = ft.Column(
        controls=[
            ft.Text(pre_state_text, weight="bold"),
            ft.Row(
                controls=[
                    state_panel(before_alice_panel_title, before_alice_rows),
                    state_panel(before_server_panel_title, before_server_rows),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Generate Identity keys", weight="bold"),
            func_node("GENERATE_DH", width=200, tooltip=tips.get("x3dh_step_node_generate_dh", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    var_node("IK_pub", last_key_chars(ik_public), width=240, full_value=ik_public, tooltip=tips.get("x3dh_step_key_ik_pub", "")),
                    var_node("IK_priv", last_key_chars(ik_private), width=240, full_value=ik_private, tooltip=tips.get("x3dh_step_key_ik_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Generate Signed Prekey (SPK) keys", weight="bold"),
            func_node("GENERATE_DH", width=200, tooltip=tips.get("x3dh_step_node_generate_dh", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    var_node("SPK_pub", last_key_chars(spk_public), width=240, full_value=spk_public, tooltip=tips.get("x3dh_step_key_spk_pub", "")),
                    var_node("SPK_priv", last_key_chars(spk_private), width=240, full_value=spk_private, tooltip=tips.get("x3dh_step_key_spk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Sign SPK_pub using IK_priv", weight="bold"),
            ft.Row(
                controls=[
                    var_node("IK_priv", last_key_chars(ik_private), width=220, full_value=ik_private, tooltip=tips.get("x3dh_step_key_ik_priv", "")),
                    var_node("SPK_pub", last_key_chars(spk_public), width=220, full_value=spk_public, tooltip=tips.get("x3dh_step_key_spk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=18,
            ),
            ft.Text("↓", size=24),
            func_node("SIGN", width=200, tooltip=tips.get("x3dh_step_node_sign", "")),
            ft.Text("↓", size=24),
            var_node(sign_output_label, last_key_chars(spk_signature), width=420, full_value=spk_signature, tooltip=tips.get("x3dh_step_key_spk_sig", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    loop_inner = ft.Stack(
        controls=[
            ft.Container(
                border=ft.Border.all(),
                border_radius=8,
                padding=12,
                content=ft.Column(
                    controls=[
                        func_node("GENERATE_DH", width=200, height=70, tooltip=tips.get("x3dh_step_node_generate_dh", "")),
                        ft.Text("↓", size=22),
                        ft.Row(
                            controls=[
                                var_node("OPK_pub", last_key_chars(first_opk_pub), width=220, height=80, full_value=first_opk_pub, tooltip=tips.get("x3dh_step_key_opk_pub", "")),
                                var_node("OPK_priv", last_key_chars(first_opk_priv), width=220, height=80, full_value=first_opk_priv, tooltip=tips.get("x3dh_step_key_opk_priv", "")),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=18,
                        ),
                        ft.Text("↓", size=22),
                        var_node(opk_id_label, opk_id_value, width=220, height=70, full_value=first_opk_id),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            ft.Container(
                left=8,
                top=8,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border=ft.Border.all(),
                border_radius=4,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Text("loop", size=11, weight="bold"),
            ),
        ]
    )
    loop_inner = with_tooltip(loop_inner, tips.get("x3dh_step_node_loop", ""))

    step5 = ft.Column(
        controls=[
            ft.Text("5) Generate OPK keys", weight="bold"),
            loop_inner,
            var_node("Result", f"OPK set generated: {opk_count} keys", width=360, height=90, full_value=opk_keys),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show current state", "control": step1},
        {"title": "Generate IK", "control": step2},
        {"title": "Generate SPK", "control": step3},
        {"title": "Sign SPK", "control": step4},
        {"title": "Generate OPKs", "control": step5},
    ]


def build_message_state_panel(
    before_state: dict,
    after_state: dict,
    title: str = "Message state",
) -> ft.Control:
    return state_panel(
        title,
        [
            (
                "Initial message (before)",
                str(isinstance(before_state.get("initial_message"), dict)),
                None,
                before_state.get("initial_message"),
            ),
            (
                "Initial message (after)",
                str(isinstance(after_state.get("initial_message"), dict)),
                None,
                after_state.get("initial_message"),
            ),
        ],
        highlight_labels={"Initial message (after)"},
    )


def build_decrypt_step(
    *,
    step_text: str,
    key_label: str,
    key_value: Any,
    ciphertext_value: Any,
    plaintext_label: str,
    plaintext_value: Any,
    key_tooltip: str | None = None,
    ciphertext_tooltip: str | None = None,
    plaintext_tooltip: str | None = None,
    decrypt_tooltip: str | None = None,
    decrypt_node_value: str | None = "Use Bob SK",
) -> ft.Control:
    return ft.Column(
        controls=[
            ft.Text(step_text, weight="bold"),
            ft.Row(
                controls=[
                    var_node(key_label, last_key_chars(key_value), width=260, full_value=key_value, tooltip=key_tooltip),
                    var_node("Ciphertext", last_key_chars(ciphertext_value), width=260, full_value=ciphertext_value, tooltip=ciphertext_tooltip),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            func_node("DECRYPT", decrypt_node_value, width=220, tooltip=decrypt_tooltip),
            ft.Text("↓", size=24),
            var_node(plaintext_label, last_key_chars(plaintext_value), width=520, full_value=plaintext_value, tooltip=plaintext_tooltip),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def build_compare_values_step(
    *,
    step_text: str,
    left_label: str,
    left_value: Any,
    right_label: str,
    right_value: Any,
    result_label: str,
    result_value: Any,
    left_tooltip: str | None = None,
    right_tooltip: str | None = None,
    left_width: int = 260,
    right_width: int = 260,
) -> ft.Control:
    return ft.Column(
        controls=[
            ft.Text(step_text, weight="bold"),
            ft.Row(
                controls=[
                    var_node(left_label, last_key_chars(left_value), width=left_width, full_value=left_value, tooltip=left_tooltip),
                    var_node(right_label, last_key_chars(right_value), width=right_width, full_value=right_value, tooltip=right_tooltip),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            func_node("COMPARE", width=200),
            ft.Text("↓", size=24),
            var_node(result_label, str(bool(result_value)), width=320, full_value=result_value),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def build_bob_summary_step(
    *,
    step_text: str,
    result: dict,
    bob_local: dict,
    result_rows_builder: Callable[[dict], list[tuple[str, str, str | None, Any]]],
    local_rows_builder: Callable[[dict], list[tuple[str, str, str | None, Any]]],
) -> ft.Control:
    return ft.Column(
        controls=[
            ft.Text(step_text, weight="bold"),
            state_panel(
                "Bob result (after)",
                result_rows_builder(result),
                highlight_labels={"AD_matches", "SK_matches", "Decrypt OK"},
            ),
            state_panel("Bob local key state", local_rows_builder(bob_local)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
