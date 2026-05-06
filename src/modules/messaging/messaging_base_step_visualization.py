from typing import Any, Callable

import flet as ft

from modules.base_step_visualization import (
    page_size,
    with_tooltip,
    to_text
)

def flow_node(
    label: str,
    value: str | None = None,
    circle: bool = False,
    width: int = 260,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    """Build a card-style UI container for data flow visualization."""
    controls = [ft.Text(label, weight="bold", text_align=ft.TextAlign.CENTER, color=text_color)]
    if value:
        controls.append(ft.Text(value, text_align=ft.TextAlign.CENTER, color=text_color))

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
        bgcolor=bgcolor,
        border=ft.Border.all(color=border_color) if border_color is not None else ft.Border.all(),
        border_radius=45 if circle else 8,
    )
    return with_tooltip(node, tooltip, full_value)


def var_node(
    label: str,
    value: str | None = None,
    width: int = 220,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    """Build a variable/data node using shared visual style."""
    value = value or last_n_chars(full_value) if full_value is not None else None
    return flow_node(
        label=label,
        value=value,
        circle=False,
        width=width,
        height=height,
        tooltip=tooltip,
        full_value=full_value,
        bgcolor=bgcolor,
        text_color=text_color,
        border_color=border_color,
    )


def func_node(
    label: str,
    value: str | None = None,
    tooltip: str | None = None,
    full_value: Any = None,
    width: int = 220,
    height: int = 70,
    bgcolor: str | None = None,
    text_color: str | None = None,
    border_color: str | None = None,
) -> ft.Control:
    """Build a function/operator node (circular) using shared visual style."""
    return flow_node(
        label=label,
        value=value,
        circle=True,
        width=width,
        height=height,
        tooltip=tooltip,
        full_value=full_value,
        bgcolor=bgcolor,
        text_color=text_color,
        border_color=border_color,
    )


def state_row(
    label: str,
    value: str,
    tooltip: str | None = None,
    full_value: Any = None,
    highlight: bool = False,
    is_synced: bool = False,
) -> ft.Control:
    """Build a label-value row pair for party state display."""
    row = ft.Row(
        controls=[
            ft.Text(
                f"{label}:",
                weight="bold",
                color=ft.Colors.ON_PRIMARY_CONTAINER if highlight else None,
            ),
            ft.Text(
                value,
                weight=ft.FontWeight.W_600 if highlight else None,
                color=ft.Colors.ON_PRIMARY_CONTAINER if highlight else None,
            ),
        ],
        spacing=8,
        wrap=True,
    )
    row_control: ft.Control = row
    if highlight:
        row_control = ft.Container(
            content=row,
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=6,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
        )
    outer_container = ft.Container(
        content=row_control,
        padding=ft.Padding.symmetric(horizontal=4, vertical=2),
        border_radius=6,
        height=32,
        border=ft.Border.all(color=ft.Colors.GREEN_600, width=2) if is_synced else None,
    )
    return with_tooltip(outer_container, tooltip, full_value)


def party_state_panel(
    title: str,
    rows: list[tuple[str, str, str | None, Any]],
    tooltip: str | None = None,
    highlight_labels: set[str] | None = None,
    synced_labels: set[str] | None = None,
) -> ft.Control:
    """Build a state panel container for party state display.
    
    Args:
        title: Panel title
        rows: List of (label, value, tooltip, full_value) tuples
        tooltip: Optional tooltip for the panel
        highlight_labels: Labels to highlight with primary container background
        synced_labels: Labels to highlight with green sync border (optional, DR-specific)
    """
    highlighted = highlight_labels or set()
    synced = synced_labels or set()
    panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(title, size=16, weight="bold"),
                *[
                    state_row(
                        label,
                        value,
                        row_tooltip,
                        full_value,
                        highlight=label in highlighted,
                        is_synced=label in synced,
                    )
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
    return with_tooltip(panel, tooltip)


def show_step_dialog(
    page: ft.Page,
    dialog_title: str,
    steps: list[dict[str, Any]],
    on_close: Callable[[], None] | None = None,
) -> None:
    """Display a multi-step dialog navigator with pagination.
    
    Args:
        page: Flet page object
        dialog_title: Title for the dialog
        steps: List of step dicts with 'title' and 'control' keys
        on_close: Optional callback when dialog closes
    """
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
        if on_close is not None:
            on_close()

    def render_current_step() -> None:
        index = current_step["index"]
        step = steps[index]
        progress_text.value = f"Step {index + 1}/{len(steps)}"
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
