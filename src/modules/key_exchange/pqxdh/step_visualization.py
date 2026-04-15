from __future__ import annotations

from typing import Any

import flet as ft

from modules.key_exchange import step_visualization_common as shared_steps
from modules.key_exchange.x3dh import step_visualization as x3dh_steps


def _last_key_chars(value: Any, count: int = 10) -> str:
    return shared_steps.last_key_chars(value, count)


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


def _state_panel(
    title: str,
    rows: list[tuple[str, str, str | None, Any]],
    highlight_labels: set[str] | None = None,
) -> ft.Control:
    return shared_steps.state_panel(title, rows, highlight_labels)


def _alice_local_rows_with_pq(payload: dict | None, tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    base_rows = x3dh_steps._alice_local_rows(payload, tooltips)
    if not isinstance(payload, dict):
        return base_rows

    pq_spk = payload.get("pq_signed_prekey") if isinstance(payload.get("pq_signed_prekey"), dict) else {}
    pq_sig = payload.get("pq_signed_prekey_signature")
    pq_opk_map = payload.get("pq_opk_public_by_id") if isinstance(payload.get("pq_opk_public_by_id"), dict) else {}
    return base_rows + [
        ("PQSPK_pub", _last_key_chars(pq_spk.get("public", "-")), tooltips.get("pqxdh_step_key_pqspk_pub", ""), pq_spk.get("public")),
        ("PQSPK_priv", _last_key_chars(pq_spk.get("private", "-")), tooltips.get("pqxdh_step_key_pqspk_priv", ""), pq_spk.get("private")),
        ("Sig_PQSPK", _last_key_chars(pq_sig if pq_sig else "-"), tooltips.get("pqxdh_step_key_pqspk_sig", ""), pq_sig),
        ("PQOPK_count_local", str(len(pq_opk_map)), tooltips.get("pqxdh_step_state_pqopk_count_local", ""), sorted(pq_opk_map.keys())),
    ]


def _server_alice_rows_with_pq(server: dict | None, tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    base_rows = x3dh_steps._server_alice_rows(server, tooltips)
    if not isinstance(server, dict):
        return base_rows

    bundle = server.get("alice_bundle") if isinstance(server.get("alice_bundle"), dict) else None
    pq_ids = server.get("alice_pq_available_opk_ids", []) if isinstance(server.get("alice_pq_available_opk_ids"), list) else []
    pq_map = server.get("alice_pq_opk_public_by_id", {}) if isinstance(server.get("alice_pq_opk_public_by_id"), dict) else {}

    return base_rows + [
        ("PQSPK_pub(server)", _last_key_chars(bundle.get("pq_signed_prekey_public", "-") if bundle else "-"), tooltips.get("pqxdh_step_key_pqspk_pub", ""), bundle.get("pq_signed_prekey_public") if bundle else None),
        ("Sig_PQSPK(server)", _last_key_chars(bundle.get("pq_signed_prekey_signature", "-") if bundle else "-"), tooltips.get("pqxdh_step_key_pqspk_sig", ""), bundle.get("pq_signed_prekey_signature") if bundle else None),
        ("PQOPK_count_server", str(len(pq_ids)), tooltips.get("pqxdh_step_state_pqopk_count_server", ""), pq_ids),
        ("PQOPK_ids_server", ", ".join(str(item) for item in pq_ids[:8]) or "-", None, pq_map),
    ]


def _server_bob_rows_with_pq(server: dict | None, tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    base_rows = x3dh_steps._server_bob_rows(server, tooltips)
    if not isinstance(server, dict):
        return base_rows

    bundle = server.get("bob_bundle") if isinstance(server.get("bob_bundle"), dict) else None
    pq_ids = server.get("bob_pq_available_opk_ids", []) if isinstance(server.get("bob_pq_available_opk_ids"), list) else []
    pq_map = server.get("bob_pq_opk_public_by_id", {}) if isinstance(server.get("bob_pq_opk_public_by_id"), dict) else {}

    return base_rows + [
        ("PQSPK_pub(server)", _last_key_chars(bundle.get("pq_signed_prekey_public", "-") if bundle else "-"), tooltips.get("pqxdh_step_key_pqspk_pub", ""), bundle.get("pq_signed_prekey_public") if bundle else None),
        ("Sig_PQSPK(server)", _last_key_chars(bundle.get("pq_signed_prekey_signature", "-") if bundle else "-"), tooltips.get("pqxdh_step_key_pqspk_sig", ""), bundle.get("pq_signed_prekey_signature") if bundle else None),
        ("PQOPK_count_server", str(len(pq_ids)), tooltips.get("pqxdh_step_state_pqopk_count_server", ""), pq_ids),
        ("PQOPK_ids_server", ", ".join(str(item) for item in pq_ids[:8]) or "-", None, pq_map),
    ]


def _bundle_for_alice_rows_with_pq(bundle: dict | None, tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    base_rows = x3dh_steps._bundle_for_alice_rows(bundle, tooltips)
    if not isinstance(bundle, dict):
        return base_rows

    return base_rows + [
        ("PQSPK_pub", _last_key_chars(bundle.get("pq_signed_prekey_public", "-")), tooltips.get("pqxdh_step_key_pqspk_pub", ""), bundle.get("pq_signed_prekey_public")),
        ("PQSPK_sig", _last_key_chars(bundle.get("pq_signed_prekey_signature", "-")), tooltips.get("pqxdh_step_key_pqspk_sig", ""), bundle.get("pq_signed_prekey_signature")),
        ("PQPKB_id", str(bundle.get("pq_pkb_id", bundle.get("pq_opk_id", "-"))), tooltips.get("pqxdh_step_key_id_kem", ""), bundle.get("pq_pkb_id", bundle.get("pq_opk_id"))),
        ("PQPKB_pub", _last_key_chars(bundle.get("pq_pkb_public", bundle.get("pq_opk_public", "-"))), tooltips.get("pqxdh_step_key_pqpkb_pub", ""), bundle.get("pq_pkb_public", bundle.get("pq_opk_public"))),
        ("PQPKB_sig", _last_key_chars(bundle.get("pq_pkb_signature", bundle.get("pq_opk_signature", "-"))), tooltips.get("pqxdh_step_key_pqpkb_sig", ""), bundle.get("pq_pkb_signature", bundle.get("pq_opk_signature"))),
        ("PQ_is_last_resort", str(bool(bundle.get("pq_is_last_resort", False))), tooltips.get("pqxdh_step_state_pq_is_last_resort", ""), bundle.get("pq_is_last_resort")),
    ]


def _build_request_bob_bundle_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}
    after_bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}

    opk_id = after_bundle.get("opk_id") if isinstance(after_bundle, dict) else None
    opk_pub = after_bundle.get("opk_public") if isinstance(after_bundle, dict) else None
    pq_opk_id = after_bundle.get("pq_opk_id") if isinstance(after_bundle, dict) else None
    pq_opk_pub = after_bundle.get("pq_opk_public") if isinstance(after_bundle, dict) else None
    pq_pkb_id = after_bundle.get("pq_pkb_id") if isinstance(after_bundle, dict) else None
    pq_pkb_pub = after_bundle.get("pq_pkb_public") if isinstance(after_bundle, dict) else None
    pq_pkb_sig = after_bundle.get("pq_pkb_signature") if isinstance(after_bundle, dict) else None

    input_controls: list[ft.Control] = [
        _flow_node("IK_B_pub", _last_key_chars(after_bundle.get("identity_dh_public", "-")), width=220, full_value=after_bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
        _flow_node("SPK_B_pub", _last_key_chars(after_bundle.get("signed_prekey_public", "-")), width=220, full_value=after_bundle.get("signed_prekey_public"), tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
        _flow_node("SPK_B_sig", _last_key_chars(after_bundle.get("signed_prekey_signature", "-")), width=220, full_value=after_bundle.get("signed_prekey_signature"), tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
        _flow_node("PQSPK_pub", _last_key_chars(after_bundle.get("pq_signed_prekey_public", "-")), width=220, full_value=after_bundle.get("pq_signed_prekey_public"), tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
        _flow_node("PQSPK_sig", _last_key_chars(after_bundle.get("pq_signed_prekey_signature", "-")), width=220, full_value=after_bundle.get("pq_signed_prekey_signature"), tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
    ]
    if opk_pub not in {None, "", "-"}:
        input_controls.append(
            _flow_node("OPK_B_pub", _last_key_chars(opk_pub), width=220, full_value=opk_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", ""))
        )
    if pq_opk_pub not in {None, "", "-"}:
        input_controls.append(
            _flow_node("PQOPK_B_pub", _last_key_chars(pq_opk_pub), width=220, full_value=pq_opk_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", ""))
        )

    step1 = ft.Column(
        controls=[
            ft.Text("1) Server and Alice state before request", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Server Bob state (before)", _server_bob_rows_with_pq(before_server, tooltips)),
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
            ft.Text("2) Fetch Bob bundle, PQSPK, and selected PQPKB", weight="bold"),
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
                    _flow_node("Output: EC OPK id", str(opk_id if opk_id is not None else "-"), width=220, height=90, full_value=opk_id),
                    _flow_node("Output: PQPKB id", str(pq_pkb_id if pq_pkb_id is not None else pq_opk_id if pq_opk_id is not None else "-"), width=220, height=90, full_value=pq_pkb_id if pq_pkb_id is not None else pq_opk_id),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _flow_node("PQPKB_pub", _last_key_chars(pq_pkb_pub), width=260, full_value=pq_pkb_pub),
                    _flow_node("PQPKB_sig", _last_key_chars(pq_pkb_sig), width=260, full_value=pq_pkb_sig),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=14,
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
                    _state_panel("Server Bob state (after)", _server_bob_rows_with_pq(after_server, tooltips), highlight_labels={"Bob_OPK_count_server", "Bob_OPK_ids_server", "PQOPK_count_server", "PQOPK_ids_server"}),
                    _state_panel("Alice bundle cache (after)", _bundle_for_alice_rows_with_pq(after_bundle, tooltips)),
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
        {"title": "Request Bob bundle", "control": step2},
        {"title": "After request summary", "control": step3},
    ]


def _build_verify_signature_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}
    verify_ec = bool(after_state.get("phase2_signature_verified", False))
    pq_pkb_pub = bundle.get("pq_pkb_public", bundle.get("pq_prekey_public", "-"))
    pq_pkb_sig = bundle.get("pq_pkb_signature", bundle.get("pq_prekey_signature", "-"))

    step1 = ft.Column(
        controls=[
            ft.Text("1) Inputs for PQXDH signature verification", weight="bold"),
            _state_panel("Alice bundle cache", _bundle_for_alice_rows_with_pq(bundle, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Verify Bob EC SPK signature", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_B_pub", _last_key_chars(bundle.get("identity_dh_public", "-")), width=220, full_value=bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("SPK_B_pub", _last_key_chars(bundle.get("signed_prekey_public", "-")), width=220, full_value=bundle.get("signed_prekey_public"), tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("SPK_B_sig", _last_key_chars(bundle.get("signed_prekey_signature", "-")), width=220, full_value=bundle.get("signed_prekey_signature"), tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("VERIFY_EC", circle=True, width=180),
            ft.Text("↓", size=24),
            _flow_node("EC valid", str(verify_ec), width=260, full_value=verify_ec),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Verify Bob PQPKB signature", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_B_pub", _last_key_chars(bundle.get("identity_dh_public", "-")), width=220, full_value=bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("PQPKB_pub", _last_key_chars(pq_pkb_pub), width=220, full_value=pq_pkb_pub, tooltip=tooltips.get("pqxdh_step_key_pqpkb_pub", "")),
                    _flow_node("PQPKB_sig", _last_key_chars(pq_pkb_sig), width=220, full_value=pq_pkb_sig, tooltip=tooltips.get("pqxdh_step_key_pqpkb_sig", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("VERIFY_PQ", circle=True, width=180, tooltip=tooltips.get("pqxdh_step_node_verify_pq", "")),
            ft.Text("↓", size=24),
            _flow_node("PQ valid", str(verify_ec), width=260, full_value=verify_ec),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show verify inputs", "control": step1},
        {"title": "Verify EC signature", "control": step2},
        {"title": "Verify PQ signature", "control": step3},

    ]


def _build_generate_ek_and_sk_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}
    derived = after_state.get("alice_derived") if isinstance(after_state.get("alice_derived"), dict) else {}

    ik_priv = (alice.get("identity_dh") or {}).get("private", "-") if isinstance(alice.get("identity_dh"), dict) else "-"
    ik_b_pub = bundle.get("identity_dh_public", "-")
    spk_b_pub = bundle.get("signed_prekey_public", "-")
    opk_b_pub = bundle.get("opk_public", "-")
    pq_pkb_pub = bundle.get("pq_pkb_public", bundle.get("pq_prekey_public", "-"))
    ek_priv = derived.get("ek_private", "-")
    ek_pub = derived.get("ek_public", "-")
    sk = derived.get("shared_secret", "-")
    pq_ct = derived.get("kem_ciphertext", "-")
    pq_ss = derived.get("pq_secret", "-")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Inputs and precondition", weight="bold"),
            _state_panel(
                "Precondition",
                [("Signature verified", str(bool(before_state.get("phase2_signature_verified", False))), None, before_state.get("phase2_signature_verified", False))],
            ),
            _state_panel("Bundle inputs", _bundle_for_alice_rows_with_pq(bundle, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Generate ephemeral curve key EK", weight="bold"),
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

    step3 = ft.Column(
        controls=[
            ft.Text("3) PQKEM-ENC with Bob's selected PQPKB", weight="bold"),
            _flow_node("PQPKB_pub", _last_key_chars(pq_pkb_pub), width=300, full_value=pq_pkb_pub, tooltip=tooltips.get("pqxdh_step_key_pqpkb_pub", "")),
            ft.Text("↓", size=24),
            _flow_node("PQKEM-ENC", circle=True, width=200, tooltip=tooltips.get("pqxdh_step_node_pqkem_enc", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("CT", _last_key_chars(pq_ct), width=260, full_value=pq_ct, tooltip=tooltips.get("pqxdh_step_key_ct", "")),
                    _flow_node("SS", _last_key_chars(pq_ss), width=260, full_value=pq_ss, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dh_controls: list[ft.Control] = [
        _flow_node("DH1", "DH(IKA, SPKB)", width=420, full_value=f"IKA_priv={ik_priv}\nSPKB_pub={spk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH2", "DH(EKA, IKB)", width=420, full_value=f"EKA_priv={ek_priv}\nIKB_pub={ik_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH3", "DH(EKA, SPKB)", width=420, full_value=f"EKA_priv={ek_priv}\nSPKB_pub={spk_b_pub}", tooltip=tooltips.get("x3dh_step_node_dh", "")),
    ]
    if opk_b_pub not in {None, "", "-"}:
        dh_controls.append(_flow_node("DH4", "DH(EKA, OPKB)", width=420, full_value=opk_b_pub, tooltip=tooltips.get("x3dh_step_node_dh", "")))

    dh_controls.append(_flow_node("SS", "PQKEM-SS", width=420, full_value=f"PQSS={pq_ss}", tooltip=tooltips.get("pqxdh_step_key_ss", "")))

    step4 = ft.Column(
        controls=[
            ft.Text("4) Compute DH outputs and derive SK", weight="bold"),
            *dh_controls,
            ft.Text("↓", size=24),
            _flow_node("KDF_SK", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_kdf_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("SK", _last_key_chars(sk), width=380, full_value=sk, tooltip=tooltips.get("x3dh_step_key_sk", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("5) Derived state after operation", weight="bold"),
            _state_panel("Alice derived (after)", x3dh_steps._alice_derived_rows(after_state.get("alice_derived"), tooltips), highlight_labels={"EK_pub", "EK_priv", "SK", "DH_count"}),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Show inputs", "control": step1},
        {"title": "Generate EK", "control": step2},
        {"title": "PQKEM encapsulate", "control": step3},
        {"title": "Derive SK", "control": step4},
        {"title": "After derive summary", "control": step5},
    ]


def _build_calculate_ad_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    bundle = after_state.get("last_bundle_for_alice") if isinstance(after_state.get("last_bundle_for_alice"), dict) else {}
    derived = after_state.get("alice_derived") if isinstance(after_state.get("alice_derived"), dict) else {}

    ik_a_pub = (alice.get("identity_dh") or {}).get("public", "-") if isinstance(alice.get("identity_dh"), dict) else "-"
    ik_b_pub = bundle.get("identity_dh_public", "-")
    ad = derived.get("associated_data", "-")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Calculate AD", weight="bold"),
            ft.Text('Alice calculates associated data with party identity binding:\nAD = EncodeEC(IKA) || EncodeEC(IKB)', text_align=ft.TextAlign.CENTER),
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


def _build_send_initial_message_steps_pqxdh(
    before_state: dict,
    after_state: dict,
    tooltips: dict[str, str],
    action_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    _ = action_context
    derived = after_state.get("alice_derived") if isinstance(after_state.get("alice_derived"), dict) else {}
    message = after_state.get("initial_message") if isinstance(after_state.get("initial_message"), dict) else {}

    sk = derived.get("shared_secret", "-")
    ad = derived.get("associated_data", "-")
    ct = derived.get("kem_ciphertext", message.get("pq_ciphertext", "-"))
    ciphertext = message.get("ciphertext", "-")
    header = message.get("header") if isinstance(message.get("header"), dict) else {}

    ik_a_public = header.get("ik_a_public", message.get("ik_a_public", "-"))
    ek_a_public = header.get("ek_a_public", message.get("ek_a_public", "-"))
    bob_spk_public = header.get("bob_spk_public", message.get("bob_spk_public", "-"))
    bob_opk_id = header.get("bob_opk_id", message.get("bob_opk_id", "-"))
    bob_pq_pkb_id = header.get("bob_pq_prekey_id", message.get("bob_pq_prekey_id", "-"))

    step1 = ft.Column(
        controls=[
            ft.Text("1) Build initial message header", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_A_pub", _last_key_chars(ik_a_public), width=220, full_value=ik_a_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("EK_A_pub", _last_key_chars(ek_a_public), width=220, full_value=ek_a_public, tooltip=tooltips.get("x3dh_step_key_ek_pub", "")),
                    _flow_node("CT", _last_key_chars(ct), width=220, full_value=ct, tooltip=tooltips.get("pqxdh_step_key_ct", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _flow_node("Bob_SPK_pub", _last_key_chars(bob_spk_public), width=220, full_value=bob_spk_public, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("IdEC(OPKB)", str(bob_opk_id), width=220, full_value=bob_opk_id, tooltip=tooltips.get("pqxdh_step_key_id_ec", "")),
                    _flow_node("IdKEM(PQPKB)", str(bob_pq_pkb_id), width=220, full_value=bob_pq_pkb_id, tooltip=tooltips.get("pqxdh_step_key_id_kem", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("BUILD_HEADER", circle=True, width=220, tooltip=tooltips.get("x3dh_step_node_build_header", "")),
            ft.Text("↓", size=24),
            _flow_node("Header", "IKA | EKA | CT | IdEC(OPKB) | IdKEM(PQPKB) ", width=680, height=95, full_value=header, tooltip=tooltips.get("x3dh_step_node_header", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Encrypt initial payload with SK and AD context", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("SK", _last_key_chars(sk), width=260, full_value=sk, tooltip=tooltips.get("x3dh_step_key_sk", "")),
                    _flow_node("AD", _last_key_chars(ad), width=260, full_value=ad, tooltip=tooltips.get("x3dh_step_key_ad", "")),
                ],
                spacing=14,
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
            ft.Text("3) Send initial PQXDH message to Bob", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("Header", "IKA | EKA | CT | IdEC(OPKB) | IdKEM(PQPKB)", width=340, full_value=header, tooltip=tooltips.get("x3dh_step_node_header", "")),
                    _flow_node("Ciphertext", _last_key_chars(ciphertext), width=320, full_value=ciphertext, tooltip=tooltips.get("x3dh_step_key_ciphertext", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("SEND", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_send", "")),
            ft.Text("↓", size=24),
            _flow_node("Transport", "Alice -> Bob", width=320, full_value=message, tooltip=tooltips.get("x3dh_step_node_transport", "")),
            shared_steps.build_message_state_panel(before_state, after_state),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Build header", "control": step1},
        {"title": "Encrypt payload", "control": step2},
        {"title": "Send message", "control": step3},
    ]


def _build_bob_receives_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    bob = after_state.get("bob_local") if isinstance(after_state.get("bob_local"), dict) else {}
    msg = after_state.get("initial_message") if isinstance(after_state.get("initial_message"), dict) else {}
    result = after_state.get("bob_receive_result") if isinstance(after_state.get("bob_receive_result"), dict) else {}
    header = msg.get("header") if isinstance(msg.get("header"), dict) else {}

    ik_a_public = header.get("ik_a_public", msg.get("ik_a_public", "-"))
    ek_a_public = header.get("ek_a_public", msg.get("ek_a_public", "-"))
    bob_spk_public = header.get("bob_spk_public", msg.get("bob_spk_public", "-"))
    bob_opk_id = header.get("bob_opk_id", msg.get("bob_opk_id"))
    pq_ciphertext = header.get("pq_ciphertext", msg.get("pq_ciphertext", "-"))
    ik_b_public = (bob.get("identity_dh") or {}).get("public", "-") if isinstance(bob.get("identity_dh"), dict) else "-"

    step1 = ft.Column(
        controls=[
            ft.Text("1) Bob receives Alice initial message", weight="bold"),
            _flow_node(
                "Header",
                "IKA | EKA | CT | IdEC(OPKB) | IdKEM(PQPKB)",
                width=700,
                height=95,
                full_value=header,
                tooltip=tooltips.get("x3dh_step_node_header", ""),
            ),
            _state_panel("Initial message", x3dh_steps._initial_message_rows(msg, tooltips)),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Decapsulate CT using PQPKB_priv", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("PQPKB_priv", "cached from bundle request", width=300, full_value=result.get("pq_pkb_private"), tooltip=tooltips.get("pqxdh_step_key_pqpkb_priv", "")),
                    _flow_node("CT", _last_key_chars(pq_ciphertext), width=260, full_value=pq_ciphertext, tooltip=tooltips.get("pqxdh_step_key_ct", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=14,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("PQKEM-DEC", width=420, circle=True, tooltip=tooltips.get("pqxdh_step_node_pqkem_dec", "")),
            ft.Text("↓", size=24),
            _flow_node("SS", "PQ shared secret", width=320, full_value=result.get("pq_secret_included"), tooltip=tooltips.get("pqxdh_step_key_ss", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dh_controls: list[ft.Control] = [
        _flow_node("DH1", "DH(SPK_B_priv, IK_A_pub)", width=420, full_value=ik_a_public, tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH2", "DH(IK_B_priv, EK_A_pub)", width=420, full_value=ek_a_public, tooltip=tooltips.get("x3dh_step_node_dh", "")),
        _flow_node("DH3", "DH(SPK_B_priv, EK_A_pub)", width=420, full_value=bob_spk_public, tooltip=tooltips.get("x3dh_step_node_dh", "")),
    ]
    if bob_opk_id is not None:
        dh_controls.append(_flow_node("DH4", "DH(OPK_B_priv, EK_A_pub)", width=420, full_value=bob_opk_id, tooltip=tooltips.get("x3dh_step_node_dh", "")))
    dh_controls.append(_flow_node("SS", "PQKEM-SS", width=420, full_value=result.get("pq_secret_included"), tooltip=tooltips.get("pqxdh_step_key_ss", "")))

    step3 = ft.Column(
        controls=[
            ft.Text("3) Calculate SK", weight="bold"),
            *dh_controls,
            ft.Text("↓", size=24),
            _flow_node("KDF_SK", circle=True, width=180, tooltip=tooltips.get("x3dh_step_node_kdf_sk", "")),
            ft.Text("↓", size=24),
            _flow_node("Bob SK", _last_key_chars(result.get("bob_shared_secret", "-")), width=380, full_value=result.get("bob_shared_secret"), tooltip=tooltips.get("x3dh_step_key_sk", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = shared_steps.build_decrypt_step(
        step_text="4) Decrypt ciphertext using SK -> plaintext AD",
        key_label="SK",
        key_value=result.get("bob_shared_secret"),
        ciphertext_value=msg.get("ciphertext"),
        plaintext_label="Plaintext AD",
        plaintext_value=result.get("decrypted_text"),
        decrypt_node_value=None,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("5) Recompute AD", weight="bold"),
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
            _flow_node("CALC_AD", "AD = EncodeEC(IKA) || EncodeEC(IKB)", width=460, circle=True, tooltip=tooltips.get("x3dh_step_node_calc_ad", "")),
            ft.Text("↓", size=24),
            _flow_node("AD_local", _last_key_chars(result.get("ad_local", "-")), width=460, full_value=result.get("ad_local"), tooltip=tooltips.get("x3dh_step_key_ad", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step6 = shared_steps.build_compare_values_step(
        step_text="6) Compare ADs",
        left_label="AD_local",
        left_value=result.get("ad_local"),
        right_label="Plaintext AD",
        right_value=result.get("decrypted_text"),
        result_label="AD match",
        result_value=result.get("payload_matches_ad", False),
    )

    step7 = shared_steps.build_bob_summary_step(
        step_text="7) Bob verification summary",
        result=result,
        bob_local=bob,
        tooltips=tooltips,
        result_rows_builder=x3dh_steps._bob_receive_result_rows,
        local_rows_builder=x3dh_steps._alice_local_rows,
    )

    return [
        {"title": "Receive message", "control": step1},
        {"title": "Decapsulate CT", "control": step2},
        {"title": "Calculate SK", "control": step3},
        {"title": "Decrypt ciphertext", "control": step4},
        {"title": "Recompute AD", "control": step5},
        {"title": "Compare ADs", "control": step6},
        {"title": "Summary", "control": step7},
    ]


def _build_generate_alice_keys_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    before_alice = before_state.get("alice_local") if isinstance(before_state.get("alice_local"), dict) else None
    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}

    after_identity = after_alice.get("identity_dh", {}) if isinstance(after_alice.get("identity_dh"), dict) else {}
    after_spk = after_alice.get("signed_prekey", {}) if isinstance(after_alice.get("signed_prekey"), dict) else {}
    after_sig = after_alice.get("signed_prekey_signature", "-")

    opk_map = after_alice.get("opk_public_by_id", {}) if isinstance(after_alice.get("opk_public_by_id"), dict) else {}
    opk_priv_map = after_alice.get("opk_private_by_id", {}) if isinstance(after_alice.get("opk_private_by_id"), dict) else {}
    opk_count = len(opk_map)
    opk_keys = sorted(opk_map.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
    first_opk_id = opk_keys[0] if opk_keys else "-"
    first_opk_pub = opk_map.get(first_opk_id, "-")
    first_opk_priv_entry = opk_priv_map.get(first_opk_id, {}) if isinstance(opk_priv_map.get(first_opk_id, {}), dict) else {}
    first_opk_priv = first_opk_priv_entry.get("private", "-")

    pq_spk = after_alice.get("pq_signed_prekey", {}) if isinstance(after_alice.get("pq_signed_prekey"), dict) else {}
    pq_spk_pub = pq_spk.get("public", "-")
    pq_spk_priv = pq_spk.get("private", "-")
    pqspk_signature = after_alice.get("pq_signed_prekey_signature", "-")

    pq_opk_map = after_alice.get("pq_opk_public_by_id", {}) if isinstance(after_alice.get("pq_opk_public_by_id"), dict) else {}
    pq_opk_priv_map = after_alice.get("pq_opk_private_by_id", {}) if isinstance(after_alice.get("pq_opk_private_by_id"), dict) else {}
    pq_opk_count = len(pq_opk_map)
    pq_opk_keys = sorted(pq_opk_map.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
    first_pq_opk_id = pq_opk_keys[0] if pq_opk_keys else "-"
    first_pq_opk_pub = pq_opk_map.get(first_pq_opk_id, "-")
    first_pq_opk_priv_entry = pq_opk_priv_map.get(first_pq_opk_id, {}) if isinstance(pq_opk_priv_map.get(first_pq_opk_id, {}), dict) else {}
    first_pq_opk_priv = first_pq_opk_priv_entry.get("private", "-")

    common_steps = shared_steps.build_generate_alice_core_steps(
        before_alice_rows=_alice_local_rows_with_pq(before_alice, tooltips),
        before_server_rows=_server_alice_rows_with_pq(before_server, tooltips),
        before_alice_panel_title="Alice local state (before)",
        before_server_panel_title="Server state (before)",
        pre_state_text="1) Show server and Alice state before generation",
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
        sign_output_label="Sig_SPK",
        opk_id_label="ID_EC",
        opk_id_value="IdEC(OPK_i)",
        tooltips=tooltips,
    )

    step6 = ft.Column(
        controls=[
            ft.Text("6) Generate Last-Resort PQKEM Prekey (PQSPK)", weight="bold"),
            _flow_node("GENERATE_PQKEM", circle=True, width=220, tooltip=tooltips.get("pqxdh_step_node_generate_pqkem", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("PQSPK_pub", _last_key_chars(pq_spk_pub), width=260, full_value=pq_spk_pub, tooltip=tooltips.get("pqxdh_step_key_pqspk_pub", "")),
                    _flow_node("PQSPK_priv", _last_key_chars(pq_spk_priv), width=260, full_value=pq_spk_priv, tooltip=tooltips.get("pqxdh_step_key_pqspk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step7 = ft.Column(
        controls=[
            ft.Text("7) Sign PQSPK_pub with IK_priv", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_priv", _last_key_chars(after_identity.get("private", "-")), width=240, full_value=after_identity.get("private"), tooltip=tooltips.get("x3dh_step_key_ik_priv", "")),
                    _flow_node("PQSPK_pub", _last_key_chars(pq_spk_pub), width=240, full_value=pq_spk_pub, tooltip=tooltips.get("pqxdh_step_key_pqspk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("SIGN", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_sign", "")),
            ft.Text("↓", size=24),
            _flow_node("Sig_PQSPK", _last_key_chars(pqspk_signature), width=420, full_value=pqspk_signature, tooltip=tooltips.get("pqxdh_step_key_pqspk_sig", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step8_loop = ft.Stack(
        controls=[
            ft.Container(
                border=ft.Border.all(),
                border_radius=8,
                padding=12,
                content=ft.Column(
                    controls=[
                        _flow_node("GENERATE_PQKEM", circle=True, width=220, height=70, tooltip=tooltips.get("pqxdh_step_node_generate_pqkem", "")),
                        ft.Text("↓", size=22),
                        ft.Row(
                            controls=[
                                _flow_node("PQOPK_pub", _last_key_chars(first_pq_opk_pub), width=240, height=80, full_value=first_pq_opk_pub, tooltip=tooltips.get("pqxdh_step_key_pqopk_pub", "")),
                                _flow_node("PQOPK_priv", _last_key_chars(first_pq_opk_priv), width=240, height=80, full_value=first_pq_opk_priv, tooltip=tooltips.get("pqxdh_step_key_pqopk_priv", "")),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=20,
                        ),
                        ft.Text("↓", size=22),
                        _flow_node("ID_KEM", "IdKEM(PQOPK_i)", width=220, height=70, full_value=first_pq_opk_id, tooltip=tooltips.get("pqxdh_step_key_id_kem", "")),
                        ft.Text("↓", size=22),
                        _flow_node(
                            "Sig_PQOPK_i",
                            "Sig(IK_priv, PQOPK_i)",
                            width=480,
                            height=80,
                            full_value="Sig(IK_priv, PQOPK_i)",
                        ),
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

    step8 = ft.Column(
        controls=[
            ft.Text("8) Generate PQOPKs and signatures", weight="bold"),
            step8_loop,
            _flow_node("Result", f"PQOPK set generated: {pq_opk_count} keys", width=380, height=90, full_value=pq_opk_keys),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return common_steps + [
        {"title": "Generate PQSPK", "control": step6},
        {"title": "Sign PQSPK", "control": step7},
        {"title": "Generate PQOPKs", "control": step8},
    ]


def _find_new_shared_opk_id(before_state: dict, after_state: dict) -> str:
    before_alice = before_state.get("alice_local") if isinstance(before_state.get("alice_local"), dict) else {}
    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}

    before_ids = set((before_alice.get("opk_public_by_id") or {}).keys()) if isinstance(before_alice.get("opk_public_by_id"), dict) else set()
    after_ids = set((after_alice.get("opk_public_by_id") or {}).keys()) if isinstance(after_alice.get("opk_public_by_id"), dict) else set()

    new_ids = sorted(after_ids - before_ids, key=lambda x: int(x) if str(x).isdigit() else x)
    return str(new_ids[0]) if new_ids else "-"


def _build_upload_initial_bundle_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}

    step1 = ft.Column(
        controls=[
            ft.Text("1) Show Alice local and server state", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (before)", _alice_local_rows_with_pq(before_state.get("alice_local"), tooltips)),
                    _state_panel("Server (before)", _server_alice_rows_with_pq(before_server, tooltips)),
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
            ft.Text("2) Upload PQXDH prekey bundle to server", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_pub", "identity_dh.public", width=220, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    _flow_node("SPK_pub + Sig", "signed_prekey + signature", width=220, tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
                    _flow_node("PQSPK_pub + Sig", "pq_signed_prekey + signature", width=260, tooltip=tooltips.get("pqxdh_step_key_pqspk_sig", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=14,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD BUNDLE", circle=True, width=220, tooltip=tooltips.get("pqxdh_step_node_upload_bundle", "")),
            ft.Text("↓", size=24),
            _flow_node("Server alice_bundle", "IK + SPK + Sig + PQSPK + Sig", width=480, height=95, tooltip=tooltips.get("pqxdh_step_node_upload_bundle", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Upload OPK and PQOPK maps", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("OPK map", "opk_public_by_id", width=240, tooltip=tooltips.get("x3dh_step_node_upload_opk", "")),
                    _flow_node("PQOPK map", "pq_opk_public_by_id", width=240, tooltip=tooltips.get("pqxdh_step_node_upload_opk_pair", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD OPK SETS", circle=True, width=220, tooltip=tooltips.get("pqxdh_step_node_upload_opk_pair", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("Server EC OPKs", "alice_available_opk_ids + map", width=300, height=95, tooltip=tooltips.get("x3dh_step_node_upload_opk", "")),
                    _flow_node("Server PQ OPKs", "alice_pq_available_opk_ids + map", width=320, height=95, tooltip=tooltips.get("pqxdh_step_node_upload_opk_pair", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Alice and Server after upload", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (after)", _alice_local_rows_with_pq(after_state.get("alice_local"), tooltips)),
                    _state_panel(
                        "Server (after)",
                        _server_alice_rows_with_pq(after_server, tooltips),
                        highlight_labels={"SPK_pub(server)", "SPK_sig(server)", "PQSPK_pub(server)", "Sig_PQSPK(server)", "OPK_count_server", "PQOPK_count_server"},
                    ),
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
        {"title": "Upload prekey bundle", "control": step2},
        {"title": "Upload OPK sets", "control": step3},
        {"title": "After upload summary", "control": step4},
    ]


def _build_upload_new_opk_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}
    new_opk_id = _find_new_shared_opk_id(before_state, after_state)

    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}
    opk_pub_map = after_alice.get("opk_public_by_id", {}) if isinstance(after_alice.get("opk_public_by_id"), dict) else {}
    opk_priv_map = after_alice.get("opk_private_by_id", {}) if isinstance(after_alice.get("opk_private_by_id"), dict) else {}
    pq_opk_pub_map = after_alice.get("pq_opk_public_by_id", {}) if isinstance(after_alice.get("pq_opk_public_by_id"), dict) else {}
    pq_opk_priv_map = after_alice.get("pq_opk_private_by_id", {}) if isinstance(after_alice.get("pq_opk_private_by_id"), dict) else {}

    new_pub = opk_pub_map.get(new_opk_id, "-")
    new_priv = (opk_priv_map.get(new_opk_id, {}) or {}).get("private", "-") if isinstance(opk_priv_map.get(new_opk_id, {}), dict) else "-"
    new_pq_pub = pq_opk_pub_map.get(new_opk_id, "-")
    new_pq_priv = (pq_opk_priv_map.get(new_opk_id, {}) or {}).get("private", "-") if isinstance(pq_opk_priv_map.get(new_opk_id, {}), dict) else "-"

    step1 = ft.Column(
        controls=[
            ft.Text("1) Alice current state (local + server)", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (before)", _alice_local_rows_with_pq(before_state.get("alice_local"), tooltips)),
                    _state_panel("Server (before)", _server_alice_rows_with_pq(before_server, tooltips)),
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
            ft.Text("2) Generate new EC OPK key pair", weight="bold"),
            _flow_node("GENERATE_DH", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_generate_dh", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("OPK_pub", _last_key_chars(new_pub), width=240, full_value=new_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", "")),
                    _flow_node("OPK_priv", _last_key_chars(new_priv), width=240, full_value=new_priv, tooltip=tooltips.get("x3dh_step_key_opk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            _flow_node("Assigned ID", str(new_opk_id), width=220, tooltip=tooltips.get("pqxdh_step_key_id_ec", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Generate new PQOPK key pair", weight="bold"),
            _flow_node("GENERATE_PQKEM", circle=True, width=220, tooltip=tooltips.get("pqxdh_step_node_generate_pqkem", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("PQOPK_pub", _last_key_chars(new_pq_pub), width=240, full_value=new_pq_pub, tooltip=tooltips.get("pqxdh_step_key_pqopk_pub", "")),
                    _flow_node("PQOPK_priv", _last_key_chars(new_pq_priv), width=240, full_value=new_pq_priv, tooltip=tooltips.get("pqxdh_step_key_pqopk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            _flow_node("Shared ID", str(new_opk_id), width=220, tooltip=tooltips.get("pqxdh_step_key_id_kem", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Upload new OPK/PQOPK pair to server", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("EC OPK id", str(new_opk_id), width=220, tooltip=tooltips.get("pqxdh_step_key_id_ec", "")),
                    _flow_node("PQ OPK id", str(new_opk_id), width=220, tooltip=tooltips.get("pqxdh_step_key_id_kem", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD OPK+PQOPK", circle=True, width=240, tooltip=tooltips.get("pqxdh_step_node_upload_opk_pair", "")),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("Server EC OPKs", "alice_available_opk_ids + map", width=300, height=95, tooltip=tooltips.get("x3dh_step_node_upload_opk", "")),
                    _flow_node("Server PQ OPKs", "alice_pq_available_opk_ids + map", width=320, height=95, tooltip=tooltips.get("pqxdh_step_node_upload_opk_pair", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("5) Finish summary", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (after)", _alice_local_rows_with_pq(after_state.get("alice_local"), tooltips), highlight_labels={"OPK_count_local", "PQOPK_count_local"}),
                    _state_panel("Server (after)", _server_alice_rows_with_pq(after_server, tooltips), highlight_labels={"OPK_count_server", "OPK_ids_server", "PQOPK_count_server", "PQOPK_ids_server"}),
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
        {"title": "Generate EC OPK", "control": step2},
        {"title": "Generate PQOPK", "control": step3},
        {"title": "Upload OPK pair", "control": step4},
        {"title": "Finish summary", "control": step5},
    ]


def _build_upload_new_spk_steps_pqxdh(before_state: dict, after_state: dict, tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before_server = before_state.get("server_state") if isinstance(before_state.get("server_state"), dict) else {}
    after_server = after_state.get("server_state") if isinstance(after_state.get("server_state"), dict) else {}
    before_alice = before_state.get("alice_local") if isinstance(before_state.get("alice_local"), dict) else {}
    after_alice = after_state.get("alice_local") if isinstance(after_state.get("alice_local"), dict) else {}

    before_spk = before_alice.get("signed_prekey", {}) if isinstance(before_alice.get("signed_prekey"), dict) else {}
    before_pq_spk = before_alice.get("pq_signed_prekey", {}) if isinstance(before_alice.get("pq_signed_prekey"), dict) else {}

    new_spk = after_alice.get("signed_prekey", {}) if isinstance(after_alice.get("signed_prekey"), dict) else {}
    new_pq_spk = after_alice.get("pq_signed_prekey", {}) if isinstance(after_alice.get("pq_signed_prekey"), dict) else {}
    identity = after_alice.get("identity_dh", {}) if isinstance(after_alice.get("identity_dh"), dict) else {}

    ik_priv = identity.get("private", "-")
    old_spk_pub = before_spk.get("public", "-")
    old_pq_spk_pub = before_pq_spk.get("public", "-")
    new_spk_pub = new_spk.get("public", "-")
    new_spk_priv = new_spk.get("private", "-")
    new_pq_spk_pub = new_pq_spk.get("public", "-")
    new_pq_spk_priv = new_pq_spk.get("private", "-")
    new_sig_spk = after_alice.get("signed_prekey_signature", "-")
    new_sig_pq = after_alice.get("pq_signed_prekey_signature", "-")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Alice current state (local + server)", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (before)", _alice_local_rows_with_pq(before_state.get("alice_local"), tooltips)),
                    _state_panel("Server (before)", _server_alice_rows_with_pq(before_server, tooltips)),
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
            ft.Text("2) Store old SPK/PQSPK and generate new keys", weight="bold"),
            _flow_node(
                "Store old prekeys",
                "Keep old SPK/PQSPK for delayed initial messages",
                width=520,
                height=95,
                full_value=f"old SPK_pub={old_spk_pub}\\nold PQSPK_pub={old_pq_spk_pub}",
                tooltip=tooltips.get("pqxdh_step_node_upload_spk_pqspk", ""),
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("GENERATE_DH", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_generate_dh", "")),
                    _flow_node("GENERATE_PQKEM", circle=True, width=220, tooltip=tooltips.get("pqxdh_step_node_generate_pqkem", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    _flow_node("SPK_pub", _last_key_chars(new_spk_pub), width=230, full_value=new_spk_pub, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                    _flow_node("SPK_priv", _last_key_chars(new_spk_priv), width=230, full_value=new_spk_priv, tooltip=tooltips.get("x3dh_step_key_spk_priv", "")),
                    _flow_node("PQSPK_pub", _last_key_chars(new_pq_spk_pub), width=230, full_value=new_pq_spk_pub, tooltip=tooltips.get("pqxdh_step_key_pqspk_pub", "")),
                    _flow_node("PQSPK_priv", _last_key_chars(new_pq_spk_priv), width=230, full_value=new_pq_spk_priv, tooltip=tooltips.get("pqxdh_step_key_pqspk_priv", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Sign old EC SPK with IK_priv", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_priv", _last_key_chars(ik_priv), width=240, full_value=ik_priv, tooltip=tooltips.get("x3dh_step_key_ik_priv", "")),
                    _flow_node("SPK_pub", _last_key_chars(new_spk_pub), width=240, full_value=new_spk_pub, tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("SIGN", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_sign", "")),
            ft.Text("↓", size=24),
            _flow_node("Sig_SPK", _last_key_chars(new_sig_spk), width=320, full_value=new_sig_spk, tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Sign new PQSPK with IK_priv", weight="bold"),
            ft.Row(
                controls=[
                    _flow_node("IK_priv", _last_key_chars(ik_priv), width=240, full_value=ik_priv, tooltip=tooltips.get("x3dh_step_key_ik_priv", "")),
                    _flow_node("PQSPK_pub", _last_key_chars(new_pq_spk_pub), width=240, full_value=new_pq_spk_pub, tooltip=tooltips.get("pqxdh_step_key_pqspk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            _flow_node("SIGN", circle=True, width=200, tooltip=tooltips.get("x3dh_step_node_sign", "")),
            ft.Text("↓", size=24),
            _flow_node("Sig_PQSPK", _last_key_chars(new_sig_pq), width=320, full_value=new_sig_pq, tooltip=tooltips.get("pqxdh_step_key_pqspk_sig", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("5) Upload new EC+PQ signed prekey bundle", weight="bold"),
            _flow_node("Bundle", "IK_pub + SPK_pub + Sig + PQSPK_pub + Sig", width=520, height=95, tooltip=tooltips.get("pqxdh_step_node_upload_bundle", "")),
            ft.Text("↓", size=24),
            _flow_node("UPLOAD SPK+PQSPK", circle=True, width=260, tooltip=tooltips.get("pqxdh_step_node_upload_spk_pqspk", "")),
            ft.Text("↓", size=24),
            _flow_node("Server alice_bundle", "signed_prekey and pq_signed_prekey fields replaced", width=560, height=95, tooltip=tooltips.get("pqxdh_step_node_upload_bundle", "")),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step6 = ft.Column(
        controls=[
            ft.Text("6) Finish summary", weight="bold"),
            ft.Row(
                controls=[
                    _state_panel("Alice local (after)", _alice_local_rows_with_pq(after_state.get("alice_local"), tooltips), highlight_labels={"SPK_pub", "SPK_sig", "PQSPK_pub", "Sig_PQSPK"}),
                    _state_panel("Server (after)", _server_alice_rows_with_pq(after_server, tooltips), highlight_labels={"SPK_pub(server)", "SPK_sig(server)", "PQSPK_pub(server)", "Sig_PQSPK(server)"}),
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
        {"title": "Generate new SPK/PQSPK", "control": step2},
        {"title": "Sign EC SPK", "control": step3},
        {"title": "Sign PQSPK", "control": step4},
        {"title": "Upload prekey bundle", "control": step5},
        {"title": "Finish summary", "control": step6},
    ]


def _action_title(action_name: str) -> str:
    if action_name == "generate_alice_registration_material":
        return "Generate Alice keys"
    return x3dh_steps._action_title(action_name)


def show_pqxdh_action_step_visualization_dialog(
    page: ft.Page,
    action_name: str,
    before_state: dict,
    after_state: dict,
    action_context: dict[str, Any] | None = None,
) -> None:
    tooltips = {
        **x3dh_steps.get_tooltip_messages("x3dh"),
        **x3dh_steps.get_tooltip_messages("pqxdh"),
    }

    if action_name == "generate_alice_registration_material":
        steps = _build_generate_alice_keys_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "request_bob_bundle_for_alice":
        steps = _build_request_bob_bundle_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "alice_verifies_bundle_signature":
        steps = _build_verify_signature_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "alice_generates_ek_and_derives_sk":
        steps = _build_generate_ek_and_sk_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "alice_calculates_associated_data":
        steps = _build_calculate_ad_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "alice_sends_initial_message":
        steps = _build_send_initial_message_steps_pqxdh(before_state, after_state, tooltips, action_context)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "bob_receives_and_verifies":
        steps = _build_bob_receives_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "upload_alice_initial_bundle":
        steps = _build_upload_initial_bundle_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "alice_uploads_new_opk":
        steps = _build_upload_new_opk_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    if action_name == "alice_rotates_signed_prekey_bundle":
        steps = _build_upload_new_spk_steps_pqxdh(before_state, after_state, tooltips)
        shared_steps.show_step_dialog(page, f"Step-by-step visualization: {_action_title(action_name)}", steps)
        return

    x3dh_steps.show_x3dh_action_step_visualization_dialog(
        page,
        action_name,
        before_state,
        after_state,
        action_context,
    )
