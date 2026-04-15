from __future__ import annotations

from typing import Any

import flet as ft

from modules.key_exchange import step_visualization_common as shared_steps
from modules.tooltip_helpers import get_tooltip_messages


def _format_tooltip_value(value: Any, indent: int = 0) -> str:
    return shared_steps.format_tooltip_value(value, indent)


def _to_text(value: Any) -> str:
    return shared_steps.to_text(value)


def _preview(value: Any, limit: int = 28) -> str:
    return shared_steps.preview(value, limit)


def _last_key_chars(value: Any, count: int = 10) -> str:
    return shared_steps.last_key_chars(value, count)


def _tooltip_with_full_value(message: str | None, full_value: Any = None) -> str | None:
    return shared_steps.tooltip_with_full_value(message, full_value)


def _safe_dimension(value: Any, fallback: int) -> int:
    return shared_steps.safe_dimension(value, fallback)


def _page_size(page: ft.Page) -> tuple[int, int]:
    return shared_steps.page_size(page)


def _with_tooltip(control: ft.Control, message: str | None, full_value: Any = None) -> ft.Control:
    return shared_steps.with_tooltip(control, message, full_value)


def _flow_node(
    label: str,
    value: str | None = None,
    circle: bool = False,
    width: int = 180,
    height: int = 90,
    tooltip: str | None = None,
    full_value: Any = None,
) -> ft.Control:
    return shared_steps.flow_node(label, value, circle, width, height, tooltip, full_value)


def _state_row(
    label: str,
    value: str,
    tooltip: str | None = None,
    full_value: Any = None,
    highlight: bool = False,
) -> ft.Control:
    return shared_steps.state_row(label, value, tooltip, full_value, highlight)


def _state_panel(
    title: str,
    rows: list[tuple[str, str, str | None, Any]],
    highlight_labels: set[str] | None = None,
) -> ft.Control:
    return shared_steps.state_panel(title, rows, highlight_labels)


def _show_step_dialog(page: ft.Page, dialog_title: str, steps: list[dict[str, Any]]) -> None:
    shared_steps.show_step_dialog(page, dialog_title, steps)


def _opk_count(server_state: dict, key: str) -> int:
    value = server_state.get(key, [])
    return len(value) if isinstance(value, list) else 0


def _state_snapshot_rows(state: dict, tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    server = state.get("server_state", {}) if isinstance(state.get("server_state"), dict) else {}
    derived = state.get("alice_derived") if isinstance(state.get("alice_derived"), dict) else None

    return [
        ("Alice Generated", str(bool(state.get("alice_generated", False))), tooltips.get("x3dh_step_state_alice_generated", ""), state.get("alice_generated", False)),
        ("Alice Bundle Uploaded", str(isinstance(server.get("alice_bundle"), dict)), tooltips.get("x3dh_step_state_alice_bundle", ""), server.get("alice_bundle")),
        ("Alice OPK on Server", str(_opk_count(server, "alice_available_opk_ids")), tooltips.get("x3dh_step_state_alice_opk", ""), server.get("alice_available_opk_ids")),
        ("Bob OPK on Server", str(_opk_count(server, "bob_available_opk_ids")), tooltips.get("x3dh_step_state_bob_opk", ""), server.get("bob_available_opk_ids")),
        ("Bundle For Alice", str(isinstance(state.get("last_bundle_for_alice"), dict)), tooltips.get("x3dh_step_state_bundle_for_alice", ""), state.get("last_bundle_for_alice")),
        ("Signature Verified", str(bool(state.get("phase2_signature_verified", False))), tooltips.get("x3dh_step_state_signature_verified", ""), state.get("phase2_signature_verified", False)),
        ("EK/SK Derived", str(bool(state.get("phase2_ek_generated", False))), tooltips.get("x3dh_step_state_ek_sk", ""), state.get("phase2_ek_generated", False)),
        ("AD Computed", str(isinstance(derived, dict) and isinstance(derived.get("associated_data"), str)), tooltips.get("x3dh_step_state_ad", ""), derived.get("associated_data") if derived else None),
        ("Initial Message", str(isinstance(state.get("initial_message"), dict)), tooltips.get("x3dh_step_state_initial_message", ""), state.get("initial_message")),
        ("Bob Verification", str(isinstance(state.get("bob_receive_result"), dict)), tooltips.get("x3dh_step_state_bob_verification", ""), state.get("bob_receive_result")),
        ("Events", str(len(state.get("events", []))), tooltips.get("x3dh_step_state_events", ""), state.get("events", [])),
    ]


def _changed_labels(before_rows: list[tuple[str, str, str | None, Any]], after_rows: list[tuple[str, str, str | None, Any]]) -> set[str]:
    before_map = {label: value for label, value, _, _ in before_rows}
    after_map = {label: value for label, value, _, _ in after_rows}
    return {label for label, value in before_map.items() if value != after_map.get(label)}


def _new_events(before_state: dict, after_state: dict) -> list[str]:
    before_events = before_state.get("events", []) if isinstance(before_state.get("events"), list) else []
    after_events = after_state.get("events", []) if isinstance(after_state.get("events"), list) else []
    if len(after_events) <= len(before_events):
        return []
    return [str(event) for event in after_events[len(before_events):]]


def _action_title(action_name: str) -> str:
    titles = {
        "generate_alice_registration_material": "Generate Alice keys",
        "upload_alice_initial_bundle": "Upload Alice initial bundle",
        "server_sends_alice_opk_to_requester": "Server sends Alice OPK",
        "server_sends_bob_opk_to_requester": "Server sends Bob OPK",
        "alice_uploads_new_opk": "Alice uploads new OPK",
        "alice_rotates_signed_prekey_bundle": "Alice rotates signed prekey bundle",
        "request_bob_bundle_for_alice": "Alice requests Bob bundle",
        "alice_verifies_bundle_signature": "Alice verifies Bob signature",
        "alice_generates_ek_and_derives_sk": "Alice derives SK",
        "alice_calculates_associated_data": "Alice computes AD",
        "alice_sends_initial_message": "Alice sends initial message",
        "bob_receives_and_verifies": "Bob receives and verifies",
        "reset_application": "Reset application",
    }
    return titles.get(action_name, action_name)


def _alice_local_rows(payload: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(payload, dict):
        return [("Alice local", "Not initialized", None, None)]

    identity = payload.get("identity_dh", {}) if isinstance(payload.get("identity_dh"), dict) else {}
    spk = payload.get("signed_prekey", {}) if isinstance(payload.get("signed_prekey"), dict) else {}
    opk_map = payload.get("opk_public_by_id", {}) if isinstance(payload.get("opk_public_by_id"), dict) else {}

    return [
        ("IK_pub", _last_key_chars(identity.get("public", "-")), tips.get("x3dh_step_key_ik_pub", ""), identity.get("public")),
        ("IK_priv", _last_key_chars(identity.get("private", "-")), tips.get("x3dh_step_key_ik_priv", ""), identity.get("private")),
        ("SPK_pub", _last_key_chars(spk.get("public", "-")), tips.get("x3dh_step_key_spk_pub", ""), spk.get("public")),
        ("SPK_priv", _last_key_chars(spk.get("private", "-")), tips.get("x3dh_step_key_spk_priv", ""), spk.get("private")),
        ("SPK_sig", _last_key_chars(payload.get("signed_prekey_signature", "-")), tips.get("x3dh_step_key_spk_sig", ""), payload.get("signed_prekey_signature")),
        ("OPK_count_local", str(len(opk_map)), None, sorted(opk_map.keys())),
    ]


def _server_alice_rows(server: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(server, dict):
        return [("Server", "Unavailable", None, None)]

    bundle = server.get("alice_bundle") if isinstance(server.get("alice_bundle"), dict) else None
    opk_ids = server.get("alice_available_opk_ids", []) if isinstance(server.get("alice_available_opk_ids"), list) else []
    opk_map = server.get("alice_opk_public_by_id", {}) if isinstance(server.get("alice_opk_public_by_id"), dict) else {}

    return [
        ("Alice bundle", "uploaded" if isinstance(bundle, dict) else "missing", None, bundle),
        ("IK_pub(server)", _last_key_chars(bundle.get("identity_dh_public", "-") if bundle else "-"), tips.get("x3dh_step_key_ik_pub", ""), bundle.get("identity_dh_public") if bundle else None),
        ("SPK_pub(server)", _last_key_chars(bundle.get("signed_prekey_public", "-") if bundle else "-"), tips.get("x3dh_step_key_spk_pub", ""), bundle.get("signed_prekey_public") if bundle else None),
        ("SPK_sig(server)", _last_key_chars(bundle.get("signed_prekey_signature", "-") if bundle else "-"), tips.get("x3dh_step_key_spk_sig", ""), bundle.get("signed_prekey_signature") if bundle else None),
        ("OPK_count_server", str(len(opk_ids)), None, opk_ids),
        ("OPK_ids_server", ", ".join(str(item) for item in opk_ids[:8]) or "-", None, opk_map),
    ]


def _server_bob_rows(server: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(server, dict):
        return [("Server", "Unavailable", None, None)]

    bundle = server.get("bob_bundle") if isinstance(server.get("bob_bundle"), dict) else None
    opk_ids = server.get("bob_available_opk_ids", []) if isinstance(server.get("bob_available_opk_ids"), list) else []
    opk_map = server.get("bob_opk_public_by_id", {}) if isinstance(server.get("bob_opk_public_by_id"), dict) else {}

    return [
        ("Bob bundle", "available" if isinstance(bundle, dict) else "missing", None, bundle),
        ("IK_B_pub(server)", _last_key_chars(bundle.get("identity_dh_public", "-") if bundle else "-"), tips.get("x3dh_step_key_ik_pub", ""), bundle.get("identity_dh_public") if bundle else None),
        ("SPK_B_pub(server)", _last_key_chars(bundle.get("signed_prekey_public", "-") if bundle else "-"), tips.get("x3dh_step_key_spk_pub", ""), bundle.get("signed_prekey_public") if bundle else None),
        ("SPK_B_sig(server)", _last_key_chars(bundle.get("signed_prekey_signature", "-") if bundle else "-"), tips.get("x3dh_step_key_spk_sig", ""), bundle.get("signed_prekey_signature") if bundle else None),
        ("Bob_OPK_count_server", str(len(opk_ids)), None, opk_ids),
        ("Bob_OPK_ids_server", ", ".join(str(item) for item in opk_ids[:8]) or "-", None, opk_map),
    ]


def _bundle_for_alice_rows(bundle: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(bundle, dict):
        return [("Bundle for Alice", "Not requested", None, None)]

    return [
        ("IK_B_pub", _last_key_chars(bundle.get("identity_dh_public", "-")), tips.get("x3dh_step_key_ik_pub", ""), bundle.get("identity_dh_public")),
        ("SPK_B_pub", _last_key_chars(bundle.get("signed_prekey_public", "-")), tips.get("x3dh_step_key_spk_pub", ""), bundle.get("signed_prekey_public")),
        ("SPK_B_sig", _last_key_chars(bundle.get("signed_prekey_signature", "-")), tips.get("x3dh_step_key_spk_sig", ""), bundle.get("signed_prekey_signature")),
        ("OPK_B_id", str(bundle.get("opk_id", "-")), None, bundle.get("opk_id")),
        ("OPK_B_pub", _last_key_chars(bundle.get("opk_public", "-")), tips.get("x3dh_step_key_opk_pub", ""), bundle.get("opk_public")),
    ]


def _alice_derived_rows(derived: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(derived, dict):
        return [("Alice derived", "Not available", None, None)]

    return [
        ("EK_pub", _last_key_chars(derived.get("ek_public", "-")), tips.get("x3dh_step_key_ek_pub", ""), derived.get("ek_public")),
        ("EK_priv", _last_key_chars(derived.get("ek_private", "-")), tips.get("x3dh_step_key_ek_priv", ""), derived.get("ek_private")),
        ("SK", _last_key_chars(derived.get("shared_secret", "-")), tips.get("x3dh_step_key_sk", ""), derived.get("shared_secret")),
        ("AD", _last_key_chars(derived.get("associated_data", "-")), tips.get("x3dh_step_key_ad", ""), derived.get("associated_data")),
        ("DH_count", str(derived.get("dh_count", "-")), None, derived.get("dh_count")),
    ]


def _initial_message_rows(message: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(message, dict):
        return [("Initial message", "Not sent", None, None)]

    header = message.get("header") if isinstance(message.get("header"), dict) else {}

    ik_a_public = header.get("ik_a_public", message.get("ik_a_public"))
    ek_a_public = header.get("ek_a_public", message.get("ek_a_public"))
    bob_spk_public = header.get("bob_spk_public", message.get("bob_spk_public"))
    bob_opk_id = header.get("bob_opk_id", message.get("bob_opk_id"))

    return [
        ("IK_A_pub", _last_key_chars(ik_a_public), tips.get("x3dh_step_key_ik_pub", ""), ik_a_public),
        ("EK_A_pub", _last_key_chars(ek_a_public), tips.get("x3dh_step_key_ek_pub", ""), ek_a_public),
        ("Bob SPK_pub", _last_key_chars(bob_spk_public), tips.get("x3dh_step_key_spk_pub", ""), bob_spk_public),
        ("Bob OPK id", str(bob_opk_id if bob_opk_id is not None else "-"), None, bob_opk_id),
        ("Ciphertext", _last_key_chars(message.get("ciphertext", "-")), None, message.get("ciphertext")),
    ]


def _bob_receive_result_rows(result: dict | None, tooltips: dict[str, str] | None = None) -> list[tuple[str, str, str | None, Any]]:
    tips = tooltips or {}
    if not isinstance(result, dict):
        return [("Bob result", "Not available", None, None)]

    return [
        ("Used OPK id", str(result.get("used_opk_id", "-")), None, result.get("used_opk_id")),
        ("AD_local", _last_key_chars(result.get("ad_local", "-")), tips.get("x3dh_step_key_ad", ""), result.get("ad_local")),
        ("AD_matches", str(bool(result.get("ad_matches", False))), None, result.get("ad_matches")),
        ("Payload_matches_AD", str(bool(result.get("payload_matches_ad", False))), None, result.get("payload_matches_ad")),
        ("Bob SK", _last_key_chars(result.get("bob_shared_secret", "-")), tips.get("x3dh_step_key_sk", ""), result.get("bob_shared_secret")),
        ("SK_matches", str(bool(result.get("shared_secret_matches", False))), None, result.get("shared_secret_matches")),
        ("Decrypt OK", str(bool(result.get("decryption_ok", False))), None, result.get("decryption_ok")),
        ("Decrypted_payload", _preview(result.get("decrypted_text", "-"), 64), None, result.get("decrypted_text")),
        ("DH_count", str(result.get("dh_count", "-")), None, result.get("dh_count")),
    ]


def _find_new_opk_id(before_state: dict, after_state: dict) -> str:
    before_alice = before_state.get("alice_local") if isinstance(before_state.get("alice_local"), dict) else {}
    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}

    before_ids = set((before_alice.get("opk_public_by_id") or {}).keys()) if isinstance(before_alice.get("opk_public_by_id"), dict) else set()
    after_ids = set((after_alice.get("opk_public_by_id") or {}).keys()) if isinstance(after_alice.get("opk_public_by_id"), dict) else set()

    new_ids = sorted(after_ids - before_ids, key=lambda x: int(x) if str(x).isdigit() else x)
    return str(new_ids[0]) if new_ids else "-"


def _build_request_bob_bundle_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}
    after_bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}

    opk_id = after_bundle.get("opk_id") if isinstance(after_bundle, dict) else None
    opk_pub = after_bundle.get("opk_public") if isinstance(after_bundle, dict) else None

    input_controls: list[ft.Control] = [
        _flow_node("IK_B_pub", _last_key_chars(after_bundle.get("identity_dh_public", "-")), width=220, full_value=after_bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
        _flow_node("SPK_B_pub", _last_key_chars(after_bundle.get("signed_prekey_public", "-")), width=220, full_value=after_bundle.get("signed_prekey_public"), tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
        _flow_node("SPK_B_sig", _last_key_chars(after_bundle.get("signed_prekey_signature", "-")), width=220, full_value=after_bundle.get("signed_prekey_signature"), tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
    ]
    if opk_pub not in {None, "", "-"}:
        input_controls.append(
            _flow_node("OPK_B_pub", _last_key_chars(opk_pub), width=220, full_value=opk_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", ""))
        )

    step1 = ft.Column(
        controls=[
            ft.Text("1) Server and Alice state before request", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Server Bob state (before)", _server_bob_rows(before_server, tooltips)),
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
            ft.Text("2) Fetch Bob bundle and optional OPK", weight="bold"),
            ft.Row(
                controls=input_controls,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=14,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("REQUEST_BUNDLE", circle=True, width=220, tooltip=tooltips.get("x3dh_step_node_request_bundle", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("Output: Bob bundle", "cached in last_bundle_for_alice", width=280, height=90, full_value=after_bundle),
                    _flow_node("Output: Consumed OPK id", str(opk_id if opk_id is not None else "-"), width=280, height=90, full_value=opk_id),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) State after request", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Server Bob state (after)", _server_bob_rows(after_server, tooltips), highlight_labels={"Bob_OPK_count_server", "Bob_OPK_ids_server"}),
                    _state_panel("Alice bundle cache (after)", _bundle_for_alice_rows(after_bundle, tooltips)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show pre-request state", "control": step1},
        {"title": "Request bundle", "control": step2},
        {"title": "After request summary", "control": step3},
    ]


def _build_verify_signature_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}

    ik_pub = bundle.get("identity_dh_public", "-")
    spk_pub = bundle.get("signed_prekey_public", "-")
    spk_sig = bundle.get("signed_prekey_signature", "-")
    verify_result = bool(after_state.get("phase2_signature_verified", False))

    step1 = ft.Column(
        controls=[
            ft.Text("1) Inputs for signature verification", weight="bold"),
            _state_panel("Bundle for Alice", _bundle_for_alice_rows(bundle, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) VERIFY(IK_pub, SPK_pub, SPK_signature)", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_B_pub", _last_key_chars(ik_pub), width=240, full_value=ik_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("SPK_B_pub", _last_key_chars(spk_pub), width=240, full_value=spk_pub, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("SPK_B_sig", _last_key_chars(spk_sig), width=240, full_value=spk_sig, tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("VERIFY", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_verify", "")),
            ft.Text("↓", size=24),
            _flow_node("is_valid", str(verify_result), width=260, full_value=verify_result),
            ft.Text(
                "(Internally, verify public material is derived on demand from Bob IK_priv and is not stored.)",
                size=12,
                italic=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Gate update", weight="bold"),
            _state_panel(
                "Phase flags",
                [
                    ("Signature verified (before)", str(bool(before_state.get("phase2_signature_verified", False))), None, before_state.get("phase2_signature_verified", False)),
                    ("Signature verified (after)", str(bool(after_state.get("phase2_signature_verified", False))), None, after_state.get("phase2_signature_verified", False)),
                ],
                highlight_labels={"Signature verified (after)"},
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show verify inputs", "control": step1},
        {"title": "Verify signature", "control": step2},
        {"title": "Update gate", "control": step3},
    ]


def _build_generate_ek_and_sk_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}
    derived = after_state.get("alice_derived") if isinstance(after_state.get("alice_derived"), dict) else {}

    ik_priv = (alice.get("identity_dh") or {}).get("private", "-") if isinstance(alice.get("identity_dh"), dict) else "-"
    ik_b_pub = bundle.get("identity_dh_public", "-")
    spk_b_pub = bundle.get("signed_prekey_public", "-")
    opk_b_pub = bundle.get("opk_public", "-")
    ek_priv = derived.get("ek_private", "-")
    ek_pub = derived.get("ek_public", "-")
    sk = derived.get("shared_secret", "-")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Inputs and precondition", weight="bold"),
            _state_panel(
                "Precondition",
                [("Signature verified", str(bool(before_state.get("phase2_signature_verified", False))), None, before_state.get("phase2_signature_verified", False))],
            ),
            _state_panel("Bundle inputs", _bundle_for_alice_rows(bundle, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Generate ephemeral key EK", weight="bold"),
            _flow_node("GENERATE_DH", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_generate_dh", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("EK_pub", _last_key_chars(ek_pub), width=240, full_value=ek_pub, tooltip=tooltips.get("x3dh_step_key_ek_pub", "")),
                    _flow_node("EK_priv", _last_key_chars(ek_priv), width=240, full_value=ek_priv, tooltip=tooltips.get("x3dh_step_key_ek_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dh_controls: list[ft.Control] = [
        _flow_node("DH1", "DH(IK_A_priv, SPK_B_pub)", width=420, full_value=f"IK_A_priv={ik_priv}\nSPK_B_pub={spk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH2", "DH(EK_A_priv, IK_B_pub)", width=420, full_value=f"EK_A_priv={ek_priv}\nIK_B_pub={ik_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH3", "DH(EK_A_priv, SPK_B_pub)", width=420, full_value=f"EK_A_priv={ek_priv}\nSPK_B_pub={spk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
    ]
    if opk_b_pub not in {None, "", "-"}:
        dh_controls.append(_flow_node("DH4", "DH(EK_A_priv, OPK_B_pub)", width=420, full_value=opk_b_pub, tooltip=tooltips.get("x3dh_step_node_dh", "")))

    step3 = ft.Column(
        controls=[
            ft.Text("3) Compute DH outputs then KDF_SK", weight="bold"),
            *dh_controls,
            ft.Text("↓", size=24),
            _flow_node("KDF_SK", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_kdf_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("SK", _last_key_chars(sk), width=380, full_value=sk, tooltip=tooltips.get("x3dh_step_key_sk", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Derived state after operation", weight="bold"),
            _state_panel("Alice derived (after)", _alice_derived_rows(after_state.get("alice_derived"), tooltips), highlight_labels={"EK_pub", "EK_priv", "SK", "DH_count"}),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show inputs", "control": step1},
        {"title": "Generate EK", "control": step2},
        {"title": "Derive SK", "control": step3},
        {"title": "After derive summary", "control": step4},
    ]


def _build_calculate_ad_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}
    derived = after_state.get("alice_derived") if isinstance(after_state.get("alice_derived"), dict) else {}

    ik_a_pub = (alice.get("identity_dh") or {}).get("public", "-") if isinstance(alice.get("identity_dh"), dict) else "-"
    ik_b_pub = bundle.get("identity_dh_public", "-")
    ad = derived.get("associated_data", "-")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Calculate AD", weight="bold"),
            ft.Text('Alice then calculates associated data AD with party identity binding:\nAD = Encode(IK_A_pub) || Encode(IK_B_pub)', text_align=ft.TextAlign.CENTER),
            ft.Row(
                controls=[
                    _flow_node("IK_A_pub", _last_key_chars(ik_a_pub), width=220, full_value=ik_a_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("IK_B_pub", _last_key_chars(ik_b_pub), width=220, full_value=ik_b_pub, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("CALC_AD", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_calc_ad", "")),
            ft.Text("↓", size=24),
            _flow_node("AD", _last_key_chars(ad), width=460, full_value=ad, tooltip=tooltips.get("x3dh_step_key_ad", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Compute AD", "control": step1},
    ]


def _build_send_initial_message_steps(before_state: dict, after_state: dict, tooltips: dict[str, str], action_context: dict[str, Any]) -> list[dict[str, Any]]:
    _ = action_context
    derived = after_state.get("alice_derived") if isinstance(after_state.get("alice_derived"), dict) else {}
    message = after_state.get("initial_message") if isinstance(after_state.get("initial_message"), dict) else {}

    sk = derived.get("shared_secret", "-")
    ad = derived.get("associated_data", "-")
    ciphertext = message.get("ciphertext", "-")
    header = message.get("header") if isinstance(message.get("header"), dict) else {}
    ik_a_public = header.get("ik_a_public", message.get("ik_a_public", "-"))
    ek_a_public = header.get("ek_a_public", message.get("ek_a_public", "-"))
    bob_spk_public = header.get("bob_spk_public", message.get("bob_spk_public", "-"))
    bob_opk_id = header.get("bob_opk_id", message.get("bob_opk_id", "-"))

    step1 = ft.Column(
        controls=[
            ft.Text("1) Build header", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_A_pub", _last_key_chars(ik_a_public), width=220, full_value=ik_a_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("EK_A_pub", _last_key_chars(ek_a_public), width=220, full_value=ek_a_public, tooltip=tooltips.get("x3dh_step_key_ek_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _flow_node("Bob_SPK_pub", _last_key_chars(bob_spk_public), width=220, full_value=bob_spk_public, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("Bob_OPK_id", str(bob_opk_id), width=220, full_value=bob_opk_id, tooltip=tooltips.get("x3dh_step_key_bob_opk_id", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("BUILD_HEADER", circle=True, width=220, tooltip=tooltips.get("x3dh_step_node_build_header", "")),
            ft.Text("↓", size=24),
            _flow_node(
                "Header",
                "IK_A_pub | EK_A_pub | Bob_SPK_pub | Bob_OPK_id",
                width=620,
                height=95,
                full_value=header,
                tooltip=tooltips.get("x3dh_step_node_header", ""),
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Encrypt AD", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("SK", _last_key_chars(sk), width=260, full_value=sk, tooltip=tooltips.get("x3dh_step_key_sk", "")),
                    _flow_node("AD", _last_key_chars(ad), width=260, full_value=ad, tooltip=tooltips.get("x3dh_step_key_ad", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("ENCRYPT", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_encrypt", "")),
            ft.Text("↓", size=24),
            _flow_node("Ciphertext", _last_key_chars(ciphertext), width=560, full_value=ciphertext, tooltip=tooltips.get("x3dh_step_key_ciphertext", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Send initial message", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("Header", "IK_A_pub | EK_A_pub | Bob_SPK_pub | Bob_OPK_id",
                               width=300, full_value=header, tooltip=tooltips.get("x3dh_step_node_header", "")),
                    _flow_node("Ciphertext", _last_key_chars(ciphertext), width=300, full_value=ciphertext, tooltip=tooltips.get("x3dh_step_key_ciphertext", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("SEND", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_send", "")),
            ft.Text("↓", size=24),
            _flow_node("Transport", "Alice -> Bob", width=320, full_value=message, tooltip=tooltips.get("x3dh_step_node_transport", "")),
            ft.Divider(height=1),
            shared_steps.build_message_state_panel(before_state, after_state),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Build header", "control": step1},
        {"title": "Encrypt AD", "control": step2},
        {"title": "Send message", "control": step3},
    ]


def _build_bob_receives_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    bob = after_state.get("bob_local") if isinstance(after_state.get("bob_local"), dict) else {}
    msg = after_state.get("initial_message") if isinstance(after_state.get("initial_message"), dict) else {}
    result = after_state.get("bob_receive_result") if isinstance(after_state.get("bob_receive_result"), dict) else {}
    header = msg.get("header") if isinstance(msg.get("header"), dict) else {}
    ik_a_public = header.get("ik_a_public", msg.get("ik_a_public", "-"))
    ik_b_public = (bob.get("identity_dh") or {}).get("public", "-") if isinstance(bob.get("identity_dh"), dict) else "-"
    opk_used = result.get("used_opk_id") if isinstance(result, dict) else None

    step1 = ft.Column(
        controls=[
            ft.Text("1) Bob receives Alice initial message", weight="bold"),
            _flow_node(
                "Header",
                "IK_A_pub | EK_A_pub | Bob_SPK_pub | Bob_OPK_id",
                width=620,
                height=95,
                full_value=header,
                tooltip=tooltips.get("x3dh_step_node_header", ""),
            ),
            _state_panel("Initial message", _initial_message_rows(msg, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dh_controls: list[ft.Control] = [
        _flow_node("DH1", "DH(SPK_B_priv, IK_A_pub)", width=420, tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH2", "DH(IK_B_priv, EK_A_pub)", width=420, tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH3", "DH(SPK_B_priv, EK_A_pub)", width=420, tooltip=tooltips.get("x3dh_step_node_dh", "")),
    ]
    if opk_used is not None:
        dh_controls.append(_flow_node("DH4", "DH(OPK_B_priv, EK_A_pub)", width=420, tooltip=tooltips.get("x3dh_step_node_dh", "")))

    step2 = ft.Column(
        controls=[
            ft.Text("2) Bob derives SK from DH outputs", weight="bold"),
            *dh_controls,
            ft.Text("↓", size=24),
            _flow_node("KDF_SK", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_kdf_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("Bob SK", _last_key_chars(result.get("bob_shared_secret", "-")), width=380, full_value=result.get("bob_shared_secret"), tooltip=tooltips.get("x3dh_step_key_sk", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = shared_steps.build_decrypt_step(
        step_text="3) Decrypt ciphertext",
        key_label="Bob SK",
        key_value=result.get("bob_shared_secret"),
        ciphertext_value=msg.get("ciphertext"),
        plaintext_label="Plaintext (AD)",
        plaintext_value=result.get("decrypted_text"),
        key_tooltip=tooltips.get("x3dh_step_key_sk", ""),
        ciphertext_tooltip=tooltips.get("x3dh_step_key_ciphertext", ""),
        plaintext_tooltip=tooltips.get("x3dh_step_key_ad", ""),
        decrypt_tooltip=tooltips.get("x3dh_step_node_decrypt", ""),
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Recompute AD", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_A_pub", _last_key_chars(ik_a_public), width=220, full_value=ik_a_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("IK_B_pub", _last_key_chars(ik_b_public), width=220, full_value=ik_b_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("CALC_AD", "Compute AD from header identities", width=420, circle=True, tooltip=tooltips.get("x3dh_step_node_calc_ad", "")),
            ft.Text("↓", size=24),
            _flow_node("AD_local", _last_key_chars(result.get("ad_local", "-")), width=460, full_value=result.get("ad_local"), tooltip=tooltips.get("x3dh_step_key_ad", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = shared_steps.build_compare_values_step(
        step_text="5) Compare AD with decrypted payload",
        left_label="AD_local",
        left_value=result.get("ad_local"),
        right_label="Decrypted payload",
        right_value=result.get("decrypted_text"),
        result_label="AD == plaintext",
        result_value=result.get("payload_matches_ad", False),
        left_tooltip=tooltips.get("x3dh_step_key_ad", ""),
    )

    step6 = shared_steps.build_bob_summary_step(
        step_text="6) Bob verification result",
        result=result,
        bob_local=bob,
        tooltips=tooltips,
        result_rows_builder=_bob_receive_result_rows,
        local_rows_builder=_alice_local_rows,
    )

    return [
        {"title": "Receive message", "control": step1},
        {"title": "Derive Bob SK", "control": step2},
        {"title": "Decrypt", "control": step3},
        {"title": "Calculate AD", "control": step4},
        {"title": "Compare", "control": step5},
        {"title": "Summary", "control": step6},
    ]


def _build_generate_alice_keys_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_alice = before_state.get("alice_local") if isinstance(before_state.get("alice_local"), dict) else None
    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else None

    after_identity = (after_alice or {}).get("identity_dh", {}) if isinstance((after_alice or {}).get("identity_dh"), dict) else {}
    after_spk = (after_alice or {}).get("signed_prekey", {}) if isinstance((after_alice or {}).get("signed_prekey"), dict) else {}
    after_sig = (after_alice or {}).get("signed_prekey_signature", "-")
    after_opk_map = (after_alice or {}).get("opk_public_by_id", {}) if isinstance((after_alice or {}).get("opk_public_by_id"), dict) else {}

    opk_count = len(after_opk_map)
    opk_keys = sorted(after_opk_map.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
    first_opk_id = opk_keys[0] if opk_keys else "-"
    first_opk_pub = after_opk_map.get(first_opk_id) if first_opk_id != "-" else "-"
    after_opk_priv_map = (after_alice or {}).get("opk_private_by_id", {}) if isinstance((after_alice or {}).get("opk_private_by_id"), dict) else {}
    first_opk_priv_entry = after_opk_priv_map.get(first_opk_id, {}) if first_opk_id != "-" else {}
    first_opk_priv = first_opk_priv_entry.get("private", "-") if isinstance(first_opk_priv_entry, dict) else "-"
    return shared_steps.build_generate_alice_core_steps(
        before_alice_rows=_alice_local_rows(before_alice, tooltips),
        before_server_rows=_server_alice_rows(before_state.get("server_state"), tooltips),
        before_alice_panel_title="Alice local state (before)",
        before_server_panel_title="Server view (before)",
        pre_state_text="1) Show Alice current state",
        ik_public=after_identity.get("public", "-"),
        ik_private=after_identity.get("private", "-"),
        spk_public=after_spk.get("public", "-"),
        spk_private=after_spk.get("private", "-"),
        spk_signature=after_sig,
        opk_count=opk_count,
        opk_keys=opk_keys,
        first_opk_pub=first_opk_pub,
        first_opk_priv=first_opk_priv,
        first_opk_id=first_opk_id,
        sign_output_label="SPK signature",
        opk_id_label="ID",
        opk_id_value="id = i",
        tooltips=tooltips,
    )


def _build_upload_initial_bundle_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}

    step1 = ft.Column(
        controls=[
            ft.Text("1) Show Alice local and server state", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (before)", _alice_local_rows(before_state.get("alice_local"), tooltips)),
                    _state_panel("Server (before)", _server_alice_rows(before_server, tooltips)),
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
            ft.Text("2) Alice uploads initial bundle to server", weight="bold"),
            _flow_node("Alice local state", "IK + SPK + signature + OPKs", width=300, height=95),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_upload", "")),
            ft.Text("↓", size=24),
            _flow_node("Server state", "alice_bundle + OPK map saved", width=320, height=95),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Alice and Server after upload", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (after)", _alice_local_rows(after_state.get("alice_local"), tooltips)),
                    _state_panel("Server (after)", _server_alice_rows(after_server, tooltips)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show pre-upload state", "control": step1},
        {"title": "Upload initial bundle", "control": step2},
        {"title": "After upload summary", "control": step3},
    ]


def _build_upload_new_opk_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}
    new_opk_id = _find_new_opk_id(before_state, after_state)

    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    opk_pub_map = after_alice.get("opk_public_by_id", {}) if isinstance(after_alice.get("opk_public_by_id"), dict) else {}
    opk_priv_map = after_alice.get("opk_private_by_id", {}) if isinstance(after_alice.get("opk_private_by_id"), dict) else {}
    new_pub = opk_pub_map.get(new_opk_id, "-")
    new_priv = (opk_priv_map.get(new_opk_id, {}) or {}).get("private", "-") if isinstance(opk_priv_map.get(new_opk_id, {}), dict) else "-"

    step1 = ft.Column(
        controls=[
            ft.Text("1) Alice current state (local + server)", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (before)", _alice_local_rows(before_state.get("alice_local"), tooltips)),
                    _state_panel("Server (before)", _server_alice_rows(before_server, tooltips)),
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
            ft.Text("2) Generate new OPK key pair", weight="bold"),
            _flow_node(
                "GENERATE_DH",
                circle=True,
                width=200,
                tooltip=tooltips.get("x3dh_step_node_generate_dh", ""),
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("OPK_pub", _last_key_chars(new_pub), width=240, full_value=new_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", "")),
                    _flow_node("OPK_priv", _last_key_chars(new_priv), width=240, full_value=new_priv, tooltip=tooltips.get("x3dh_step_key_opk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            _flow_node("Assigned ID", str(new_opk_id), width=220),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Alice uploads OPK to server", weight="bold"),
            _flow_node("Alice OPK id", str(new_opk_id), width=240),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD OPK", circle=True, width=220, tooltip=tooltips.get("x3dh_step_node_upload_opk", "")),
            ft.Text("↓", size=24),
            _flow_node("Server OPK set", "alice_available_opk_ids + alice_opk_public_by_id", width=360, height=95),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Finish summary", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (after)", _alice_local_rows(after_state.get("alice_local"), tooltips), highlight_labels={"OPK_count_local"}),
                    _state_panel("Server (after)", _server_alice_rows(after_server, tooltips), highlight_labels={"OPK_count_server", "OPK_ids_server"}),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show current state", "control": step1},
        {"title": "Generate OPK", "control": step2},
        {"title": "Upload OPK", "control": step3},
        {"title": "Finish summary", "control": step4},
    ]


def _build_upload_new_spk_steps(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}
    before_alice = before_state.get("alice_local") if isinstance(before_state.get("alice_local"), dict) else {}

    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    before_spk = before_alice.get("signed_prekey", {}) if isinstance(before_alice.get("signed_prekey"), dict) else {}
    spk = after_alice.get("signed_prekey", {}) if isinstance(after_alice.get("signed_prekey"), dict) else {}
    identity = after_alice.get("identity_dh", {}) if isinstance(after_alice.get("identity_dh"), dict) else {}
    old_spk_pub = before_spk.get("public", "-")
    old_spk_priv = before_spk.get("private", "-")
    spk_pub = spk.get("public", "-")
    spk_priv = spk.get("private", "-")
    ik_priv = identity.get("private", "-")
    new_signature = after_alice.get("signed_prekey_signature", "-")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Alice current state (local + server)", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (before)", _alice_local_rows(before_state.get("alice_local"), tooltips)),
                    _state_panel("Server (before)", _server_alice_rows(before_server, tooltips)),
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
            ft.Text("2) Store old SPK and generate new SPK", weight="bold"),
            _flow_node(
                "Store old SPK",
                "Keep for delayed initial messages\n(e.g., week/month window)",
                width=420,
                height=95,
                full_value=f"old SPK_pub={old_spk_pub}\nold SPK_priv={old_spk_priv}",
            ),
            ft.Text("↓", size=24),
            _flow_node(
                "GENERATE_DH",
                circle=True,
                width=200,
                tooltip=tooltips.get("x3dh_step_node_generate_dh", ""),
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("SPK_pub", _last_key_chars(spk_pub), width=240, full_value=spk_pub, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("SPK_priv", _last_key_chars(spk_priv), width=240, full_value=spk_priv, tooltip=tooltips.get("x3dh_step_key_spk_priv", "")),
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
            ft.Text("3) Sign new SPK_pub using IK_priv", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("SPK_pub", _last_key_chars(spk_pub), width=240, full_value=spk_pub, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("IK_priv", _last_key_chars(ik_priv), width=240, full_value=ik_priv, tooltip=tooltips.get("x3dh_step_key_ik_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            ft.Text("↓", size=24),
            _flow_node("SIGN", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_sign", "")),
            ft.Text("↓", size=24),
            _flow_node(
                "new SPK signature",
                _last_key_chars(new_signature),
                width=380,
                full_value=new_signature,
                tooltip=tooltips.get("x3dh_step_key_spk_sig", ""),
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Upload new SPK bundle", weight="bold"),
            _flow_node("Local SPK", _last_key_chars(spk_pub), width=240, full_value=spk_pub, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD SPK", circle=True, width=220, tooltip=tooltips.get("x3dh_step_node_upload_spk", "")),
            ft.Text("↓", size=24),
            _flow_node("Server bundle", "signed_prekey_public + signature replaced", width=380, height=95),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("5) Finish summary", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (after)", _alice_local_rows(after_state.get("alice_local"), tooltips), highlight_labels={"SPK_pub", "SPK_priv", "SPK_sig"}),
                    _state_panel("Server (after)", _server_alice_rows(after_server, tooltips), highlight_labels={"SPK_pub(server)", "SPK_sig(server)"}),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show current state", "control": step1},
        {"title": "Store old + generate new SPK", "control": step2},
        {"title": "Sign new SPK", "control": step3},
        {"title": "Upload SPK", "control": step4},
        {"title": "Finish summary", "control": step5},
    ]


def _build_custom_steps(
    action_name: str,
    before_state: dict,
    after_state: dict,
    tooltips: dict[str, str],
    action_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | None:
    if action_name == "generate_alice_registration_material":
        return _build_generate_alice_keys_steps(before_state, after_state, tooltips)
    if action_name == "upload_alice_initial_bundle":
        return _build_upload_initial_bundle_steps(before_state, after_state, tooltips)
    if action_name == "alice_uploads_new_opk":
        return _build_upload_new_opk_steps(before_state, after_state, tooltips)
    if action_name == "alice_rotates_signed_prekey_bundle":
        return _build_upload_new_spk_steps(before_state, after_state, tooltips)
    if action_name == "request_bob_bundle_for_alice":
        return _build_request_bob_bundle_steps(before_state, after_state, tooltips)
    if action_name == "alice_verifies_bundle_signature":
        return _build_verify_signature_steps(before_state, after_state, tooltips)
    if action_name == "alice_generates_ek_and_derives_sk":
        return _build_generate_ek_and_sk_steps(before_state, after_state, tooltips)
    if action_name == "alice_calculates_associated_data":
        return _build_calculate_ad_steps(before_state, after_state, tooltips)
    if action_name == "alice_sends_initial_message":
        return _build_send_initial_message_steps(before_state, after_state, tooltips, action_context or {})
    if action_name == "bob_receives_and_verifies":
        return _build_bob_receives_steps(before_state, after_state, tooltips)
    return None


def show_x3dh_action_step_visualization_dialog(
    page: ft.Page,
    action_name: str,
    before_state: dict,
    after_state: dict,
    action_context: dict[str, Any] | None = None,
) -> None:
    tooltips = get_tooltip_messages("x3dh")

    custom_steps = _build_custom_steps(action_name, before_state, after_state, tooltips, action_context)
    if custom_steps is None:
        return

    _show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", custom_steps)
