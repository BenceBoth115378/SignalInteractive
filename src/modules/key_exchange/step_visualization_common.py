from __future__ import annotations

from typing import Any, Callable

import flet as ft

import modules.base_step_visualization as base_steps
from modules.base_view import last_n_chars


def format_tooltip_value(value: Any, indent: int = 0) -> str:
    return base_steps.format_tooltip_value(value, indent)


def safe_dimension(value: Any, fallback: int) -> int:
    return base_steps.safe_dimension(value, fallback)


def tooltip_with_full_value(message: str | None, full_value: Any = None) -> str | None:
    return base_steps.tooltip_with_full_value(message, full_value)


def to_text(value: Any) -> str:
    return base_steps.to_text(value)


def with_tooltip(control: ft.Control, message: str | None, full_value: Any = None) -> ft.Control:
    return base_steps.with_tooltip(control, message, full_value)


def page_size(page: ft.Page) -> tuple[int, int]:
    return base_steps.page_size(page)


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


def flow_node(
    label: str,
    value: str | None = None,
    circle: bool = False,
    width: int = 180,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
) -> ft.Control:
    controls = [ft.Text(label, weight="bold", text_align=ft.TextAlign.CENTER)]
    if value:
        controls.append(ft.Text(value, text_align=ft.TextAlign.CENTER))

    node = ft.Container(
        content=ft.Column(
            controls=controls,
            spacing=4,
            tight=True,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=width,
        height=height,
        padding=10,
        border=ft.Border.all(),
        border_radius=45 if circle else 8,
    )
    return with_tooltip(node, tooltip, full_value)


def state_row(
    label: str,
    value: str,
    tooltip: str | None = None,
    full_value: Any = None,
    highlight: bool = False,
) -> ft.Control:
    row = ft.Row(
        controls=[
            ft.Text(f"{label}:", weight="bold"),
            ft.Text(value, weight=ft.FontWeight.W_600 if highlight else None),
        ],
        spacing=8,
        wrap=True,
    )
    if highlight:
        row = ft.Row(
            controls=[
                ft.Container(
                    content=row,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=6,
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                )
            ]
        )
    return with_tooltip(
        ft.Container(content=row, padding=ft.Padding.symmetric(horizontal=4, vertical=2), border_radius=6),
        tooltip,
        full_value,
    )


def state_panel(
    title: str,
    rows: list[tuple[str, str, str | None, Any]],
    highlight_labels: set[str] | None = None,
) -> ft.Control:
    highlighted = highlight_labels or set()
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(title, size=16, weight="bold"),
                *[
                    state_row(label, value, row_tooltip, full_value, highlight=label in highlighted)
                    for label, value, row_tooltip, full_value in rows
                ],
            ],
            spacing=4,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        width=420,
        padding=10,
        border=ft.Border.all(),
        border_radius=8,
    )


def show_step_dialog(page: ft.Page, dialog_title: str, steps: list[dict[str, Any]]) -> None:
    resize_event_name = "on_resized" if hasattr(page, "on_resized") else "on_resize"
    previous_resize_handler = getattr(page, resize_event_name, None)

    current_step = {"index": 0}
    progress_text = ft.Text()
    step_container = ft.Container(width=620)

    def apply_responsive_dialog_size() -> None:
        page_width, page_height = page_size(page)
        content_width = max(620, min(980, int(page_width * 0.82)))
        content_height = max(360, min(760, int(page_height * 0.72)))

        dialog_content.width = content_width
        dialog_content.height = content_height
        step_container.width = max(520, content_width - 80)

    def on_page_resized(e) -> None:
        apply_responsive_dialog_size()
        if callable(previous_resize_handler):
            previous_resize_handler(e)
        if dialog.open:
            page.update()

    def close_dialog(e) -> None:
        dialog.open = False
        if getattr(page, resize_event_name, None) == on_page_resized:
            setattr(page, resize_event_name, previous_resize_handler)
        page.update()

    def render_current_step() -> None:
        index = current_step["index"]
        step = steps[index]
        progress_text.value = f"Step {index + 1}/{len(steps)} - {step['title']}"
        step_container.content = step["control"]
        previous_button.disabled = index == 0
        next_button.text = "Finish" if index == len(steps) - 1 else "Next"

    def on_previous(e) -> None:
        if current_step["index"] <= 0:
            return
        current_step["index"] -= 1
        render_current_step()
        page.update()

    def on_next(e) -> None:
        if current_step["index"] >= len(steps) - 1:
            close_dialog(e)
            return
        current_step["index"] += 1
        render_current_step()
        page.update()

    previous_button = ft.TextButton("Previous", on_click=on_previous)
    next_button = ft.TextButton("Next", on_click=on_next)

    dialog_content = ft.Container(
        content=ft.Column(
            controls=[
                progress_text,
                ft.Text("Click Next to continue to the following step."),
                ft.Row(controls=[step_container], alignment=ft.MainAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            spacing=8,
            scroll=ft.ScrollMode.ALWAYS,
        ),
        width=700,
        height=460,
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(dialog_title),
        content=dialog_content,
        actions=[previous_button, next_button, ft.TextButton("Close", on_click=close_dialog)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    apply_responsive_dialog_size()
    setattr(page, resize_event_name, on_page_resized)
    render_current_step()
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


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
            flow_node("GENERATE_DH", circle=True, width=200, tooltip=tips.get("x3dh_step_node_generate_dh", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    flow_node("IK_pub", last_key_chars(ik_public), width=240, full_value=ik_public, tooltip=tips.get("x3dh_step_key_ik_pub", "")),
                    flow_node("IK_priv", last_key_chars(ik_private), width=240, full_value=ik_private, tooltip=tips.get("x3dh_step_key_ik_priv", "")),
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
            flow_node("GENERATE_DH", circle=True, width=200, tooltip=tips.get("x3dh_step_node_generate_dh", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    flow_node("SPK_pub", last_key_chars(spk_public), width=240, full_value=spk_public, tooltip=tips.get("x3dh_step_key_spk_pub", "")),
                    flow_node("SPK_priv", last_key_chars(spk_private), width=240, full_value=spk_private, tooltip=tips.get("x3dh_step_key_spk_priv", "")),
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
                    flow_node("IK_priv", last_key_chars(ik_private), width=220, full_value=ik_private, tooltip=tips.get("x3dh_step_key_ik_priv", "")),
                    flow_node("SPK_pub", last_key_chars(spk_public), width=220, full_value=spk_public, tooltip=tips.get("x3dh_step_key_spk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=18,
            ),
            ft.Text("↓", size=24),
            flow_node("SIGN", circle=True, width=200, tooltip=tips.get("x3dh_step_node_sign", "")),
            ft.Text("↓", size=24),
            flow_node(sign_output_label, last_key_chars(spk_signature), width=420, full_value=spk_signature, tooltip=tips.get("x3dh_step_key_spk_sig", "")),
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
                        flow_node("GENERATE_DH", circle=True, width=200, height=70, tooltip=tips.get("x3dh_step_node_generate_dh", "")),
                        ft.Text("↓", size=22),
                        ft.Row(
                            controls=[
                                flow_node("OPK_pub", last_key_chars(first_opk_pub), width=220, height=80, full_value=first_opk_pub, tooltip=tips.get("x3dh_step_key_opk_pub", "")),
                                flow_node("OPK_priv", last_key_chars(first_opk_priv), width=220, height=80, full_value=first_opk_priv, tooltip=tips.get("x3dh_step_key_opk_priv", "")),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=18,
                        ),
                        ft.Text("↓", size=22),
                        flow_node(opk_id_label, opk_id_value, width=220, height=70, full_value=first_opk_id),
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
            flow_node("Result", f"OPK set generated: {opk_count} keys", width=360, height=90, full_value=opk_keys),
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
                    flow_node(key_label, last_key_chars(key_value), width=260, full_value=key_value, tooltip=key_tooltip),
                    flow_node("Ciphertext", last_key_chars(ciphertext_value), width=260, full_value=ciphertext_value, tooltip=ciphertext_tooltip),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            flow_node("DECRYPT", decrypt_node_value, circle=True, width=220, tooltip=decrypt_tooltip),
            ft.Text("↓", size=24),
            flow_node(plaintext_label, last_key_chars(plaintext_value), width=520, full_value=plaintext_value, tooltip=plaintext_tooltip),
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
                    flow_node(left_label, last_key_chars(left_value), width=left_width, full_value=left_value, tooltip=left_tooltip),
                    flow_node(right_label, last_key_chars(right_value), width=right_width, full_value=right_value, tooltip=right_tooltip),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            flow_node("COMPARE", circle=True, width=200),
            ft.Text("↓", size=24),
            flow_node(result_label, str(bool(result_value)), width=320, full_value=result_value),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def build_bob_summary_step(
    *,
    step_text: str,
    result: dict,
    bob_local: dict,
    tooltips: dict[str, str],
    result_rows_builder: Callable[[dict, dict[str, str]], list[tuple[str, str, str | None, Any]]],
    local_rows_builder: Callable[[dict, dict[str, str]], list[tuple[str, str, str | None, Any]]],
) -> ft.Control:
    return ft.Column(
        controls=[
            ft.Text(step_text, weight="bold"),
            state_panel(
                "Bob result (after)",
                result_rows_builder(result, tooltips),
                highlight_labels={"AD_matches", "SK_matches", "Decrypt OK"},
            ),
            state_panel("Bob local key state", local_rows_builder(bob_local, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
