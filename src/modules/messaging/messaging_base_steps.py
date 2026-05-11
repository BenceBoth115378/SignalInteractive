from typing import Any, Callable

import flet as ft

from modules.base_steps import (
    func_node,
    party_state_panel,
    to_text,
    var_node,
)

def last_n_chars(value: Any, count: int = 8) -> str:
    """Get last N characters of a hex/string value."""
    text = to_text(value)
    if len(text) <= count:
        return text
    return text[-count:]


def preview_value(value: Any, limit: int = 28) -> str:
    """Get limited preview of bytes/string value (truncated with ...)."""
    if isinstance(value, bytes):
        text = value.hex()
    elif value is None:
        text = "None"
    else:
        text = str(value)

    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def preview_text(value: Any, limit: int = 48) -> str:
    """Get limited preview of any value as text (with higher default limit)."""
    text = to_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def format_plaintext(value: Any) -> str | Any:
    """Convert plaintext bytes to a readable string for visualization."""
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, int) and 0 <= item <= 255 for item in value):
        value = bytes(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode('utf-8', errors='replace')
        except Exception:
            return value
    return value


def bytes_to_display_str(value: Any) -> str:
    """Decode bytes to a displayable UTF-8 string, falling back to hex on decode failure."""
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            return value.hex()
    return str(value) if value is not None else "None"

def format_x3dh_header_preview(
    x3dh_header: dict[str, Any] | None,
    last_n_chars_fn: Callable[[Any, int], str],
) -> str:
    """Format X3DH header fields for preview display.
    
    Args:
        x3dh_header: X3DH header dict with ik_a_public, ek_a_public, bob_spk_public, bob_opk_id
        last_n_chars_fn: Callback to format value to last N characters (e.g., tail_hex)
    
    Returns:
        Human-readable preview string
    """
    if not isinstance(x3dh_header, dict):
        return "None"
    ik_a = last_n_chars_fn(x3dh_header.get("ik_a_public"), 8)
    ek_a = last_n_chars_fn(x3dh_header.get("ek_a_public"), 8)
    spk_b = last_n_chars_fn(x3dh_header.get("bob_spk_public"), 8)
    opk_id = x3dh_header.get("bob_opk_id")
    opk_text = str(opk_id) if opk_id is not None else "None"
    return f"ik_a={ik_a}, ek_a={ek_a}, spk_b={spk_b}, opk_id={opk_text}"


def format_pqxdh_header_preview(
    pqxdh_header: dict[str, Any] | None,
    last_n_chars_fn: Callable[[Any, int], str],
) -> str:
    """Format PQXDH header fields for preview display.
    
    Args:
        pqxdh_header: PQXDH header dict with ik_a_public, ek_a_public, bob_spk_public, bob_pq_prekey_id
        last_n_chars_fn: Callback to format value to last N characters (e.g., tail_hex)
    
    Returns:
        Human-readable preview string
    """
    if not isinstance(pqxdh_header, dict):
        return "None"
    ik_a = last_n_chars_fn(pqxdh_header.get("ik_a_public"), 8)
    ek_a = last_n_chars_fn(pqxdh_header.get("ek_a_public"), 8)
    bob_spk = last_n_chars_fn(pqxdh_header.get("bob_spk_public"), 8)
    pq_prekey_id = pqxdh_header.get("bob_pq_prekey_id")
    pq_prekey_text = str(pq_prekey_id) if pq_prekey_id is not None else "None"
    return f"ik_a={ik_a}, ek_a={ek_a}, spk_b={bob_spk}, pq_id={pq_prekey_text}"


def format_combined_header_preview(
    header_dh: Any,
    header_pn: int,
    header_n_one_based: int,
    protocol_header: dict[str, Any] | None,
    protocol_preview_fn: Callable[[dict[str, Any] | None], str],
    last_n_chars_fn: Callable[[Any, int], str],
) -> str:
    """Format a combined header (Double Ratchet + protocol-specific) for preview.
    
    Args:
        header_dh: DH key for the base header
        header_pn: PN count in the base header
        header_n_one_based: Message index (1-based) in the base header
        protocol_header: Protocol-specific header dict (X3DH or PQXDH)
        protocol_preview_fn: Callback to format the protocol header
        last_n_chars_fn: Callback to format value to last N characters
    
    Returns:
        Human-readable combined header preview string
    """
    base_part = f"dh={last_n_chars_fn(header_dh, 8)}, pn={header_pn}, n={header_n_one_based}"
    if not isinstance(protocol_header, dict):
        return f"header: {base_part}"
    protocol_preview = protocol_preview_fn(protocol_header)
    return f"header: {base_part} | protocol: {protocol_preview}"


def format_protocol_header_preview(
    header_main: dict[str, Any] | None,
    header_aux: dict[str, Any] | None,
    format_main: Callable[[dict[str, Any]], str],
    format_aux: Callable[[dict[str, Any]], str] | None = None,
) -> str:
    """Build combined header preview from main (X3DH/PQXDH) and auxiliary parts.
    
    Args:
        header_main: Primary header dict (X3DH or PQXDH header)
        header_aux: Optional secondary header dict
        format_main: Callback to format main header
        format_aux: Optional callback to format auxiliary header
    
    Returns:
        Human-readable header preview string
    """
    if header_main is None:
        return "No header"
    
    main_preview = format_main(header_main)
    if header_aux is None or format_aux is None:
        return main_preview
    
    aux_preview = format_aux(header_aux)
    return f"{main_preview} | {aux_preview}"


def build_bootstrap_dialog_steps(
    protocol_name: str,
    party_role: str,
    step_builders: list[Callable[[], dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Assemble bootstrap dialog steps from builder callbacks.

    Args:
        protocol_name: Protocol name (e.g., "X3DH", "PQXDH")
        party_role: Party role (e.g., "Alice", "Bob")
        step_builders: List of callables that each return {"title": str, "control": ft.Control}

    Returns:
        Flat list of step dicts ready for show_step_dialog
    """
    return [builder() for builder in step_builders]


def x3dh_header_preview(x3dh_header: dict[str, Any] | None) -> str:
    return format_x3dh_header_preview(x3dh_header, last_n_chars)


def pqxdh_header_preview(pqxdh_header: dict[str, Any] | None) -> str:
    return format_pqxdh_header_preview(pqxdh_header, last_n_chars)


def dr_header_preview(header_dh: Any, header_pn: int, header_n_one_based: int) -> str:
    return f"dh={last_n_chars(header_dh, 8)}, pn={header_pn}, n={header_n_one_based}"


def spqr_header_preview(spqr_header: Any) -> str:
    if spqr_header is None:
        return "None"
    msg = getattr(spqr_header, "msg", None)
    epoch = getattr(msg, "epoch", "?")
    msg_type = getattr(getattr(msg, "msg_type", None), "value", "?")
    n = getattr(spqr_header, "n", "?")
    return f"epoch={epoch}, type={msg_type}, n={n}"


def combined_dr_header_preview(
    header_dh: Any,
    header_pn: int,
    header_n_one_based: int,
    x3dh_hdr: dict[str, Any] | None,
) -> str:
    return format_combined_header_preview(
        header_dh, header_pn, header_n_one_based, x3dh_hdr,
        x3dh_header_preview, last_n_chars,
    )


def compute_changed_labels(
    before_rows: list[tuple[str, str, Any, Any]],
    after_rows: list[tuple[str, str, Any, Any]],
) -> set[str]:
    before_values = {label: value for label, value, _, _ in before_rows}
    after_values = {label: value for label, value, _, _ in after_rows}
    return {
        label
        for label, value in before_values.items()
        if value != after_values.get(label)
    }


def build_header_split_step(
    protocol_label: str,
    combined_preview: str,
    combined_full: Any,
    message_header_preview: str,
    message_header_full: Any,
    protocol_header_preview: str,
    protocol_header_full: Any,
    combined_tooltip: str = "",
    split_tooltip: str = "",
    message_header_tooltip: str = "",
    protocol_header_tooltip: str = "",
    combined_width: int = 460,
    message_header_width: int = 240,
) -> dict[str, Any]:
    title = f"Header split ({protocol_label} metadata extraction)"
    return {
        "title": title,
        "control": ft.Column(
            controls=[
                ft.Text(title, weight="bold"),
                var_node(
                    "Complete header",
                    value=combined_preview,
                    width=combined_width,
                    full_value=combined_full,
                    tooltip=combined_tooltip,
                ),
                ft.Text("↓", size=24),
                func_node("SPLIT", width=200, height=70, tooltip=split_tooltip),
                ft.Text("↓", size=24),
                ft.Row(
                    controls=[
                        var_node(
                            "Message header",
                            value=message_header_preview,
                            width=message_header_width,
                            full_value=message_header_full,
                            tooltip=message_header_tooltip,
                        ),
                        var_node(
                            f"{protocol_label} header",
                            value=protocol_header_preview,
                            width=420,
                            full_value=protocol_header_full,
                            tooltip=protocol_header_tooltip,
                            bgcolor=ft.Colors.SECONDARY_CONTAINER,
                            text_color=ft.Colors.ON_SECONDARY_CONTAINER,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                    wrap=True,
                ),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def build_bootstrap_init_step(
    title: str,
    was_bootstrapped: bool,
    protocol_header_label: str,
    protocol_header_preview: str,
    protocol_header_full: Any,
    on_show_bootstrap: Callable[[], None] | None,
    button_label: str,
    bootstrap_fn_label: str,
    bootstrap_fn_value: str,
    result_text: str = "Party was initialized during this receive",
    party_initialized_text: str = "Party initialized",
    party_not_initialized_text: str = "Party not yet initialized",
    party_tooltip: str = "",
    protocol_header_tooltip: str = "",
    bootstrap_fn_tooltip: str = "",
    party_width: int = 280,
    protocol_header_width: int = 320,
    bootstrap_fn_width: int = 340,
    bootstrap_fn_height: int = 80,
) -> dict[str, Any]:
    already_initialized = not was_bootstrapped
    controls: list[ft.Control] = [
        ft.Text(title, weight="bold"),
        var_node(
            "Party status",
            value=party_initialized_text if already_initialized else party_not_initialized_text,
            width=party_width,
            tooltip=party_tooltip,
            bgcolor=ft.Colors.SECONDARY_CONTAINER if already_initialized else ft.Colors.ERROR_CONTAINER,
            text_color=ft.Colors.ON_SECONDARY_CONTAINER if already_initialized else ft.Colors.ON_ERROR_CONTAINER,
        ),
        ft.Divider(height=1),
    ]
    if not already_initialized:
        controls.extend([
            var_node(
                protocol_header_label,
                value=protocol_header_preview,
                width=protocol_header_width,
                full_value=protocol_header_full,
                tooltip=protocol_header_tooltip,
            ),
            ft.Text("↓", size=24),
            func_node(
                bootstrap_fn_label,
                value=bootstrap_fn_value,
                width=bootstrap_fn_width,
                height=bootstrap_fn_height,
                tooltip=bootstrap_fn_tooltip,
            ),
        ])
        if on_show_bootstrap is not None:
            controls.append(
                ft.Column(
                    controls=[
                        ft.Text("Click button to view detailed bootstrap steps:", size=12),
                        ft.Button(button_label, on_click=lambda _: on_show_bootstrap()),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                )
            )
        controls.extend([
            ft.Text("↓", size=24),
            var_node("Result", value=result_text, width=360),
        ])
    return {
        "title": title,
        "control": ft.Column(
            controls=controls,
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    }


def build_before_after_panels(
    before_title: str,
    before_rows: list[tuple[str, str, str | None, Any]],
    after_title: str,
    after_rows: list[tuple[str, str, str | None, Any]],
    highlight_labels: set[str] | None = None,
    before_highlight_labels: set[str] | None = None,
    after_highlight_labels: set[str] | None = None,
) -> ft.Row:
    """Build a side-by-side before/after state comparison row.

    highlight_labels applies to both panels unless overridden per-panel.
    """
    hl_before = before_highlight_labels if before_highlight_labels is not None else highlight_labels
    hl_after = after_highlight_labels if after_highlight_labels is not None else highlight_labels
    return ft.Row(
        controls=[
            party_state_panel(before_title, before_rows, highlight_labels=hl_before),
            party_state_panel(after_title, after_rows, highlight_labels=hl_after),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=20,
        wrap=True,
    )
