from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import SpqrHeader, SpqrRatchetState
from modules.base_steps import (
    func_node,
    normalize_step_titles,
    party_state_panel,
    show_step_dialog,
    to_text as _shared_to_text,
    var_node,
)
from modules.messaging.messaging_base_steps import (
    format_plaintext,
    last_n_chars,
    pqxdh_header_preview,
    build_header_split_step,
    build_bootstrap_init_step,
)
from modules.messaging.messaging_base_view import (
    build_chunk_send_steps,
    build_message_step,
    build_none_send_steps,
    build_send_result_step,
)


from modules.tooltip_helpers import get_tooltip_messages



def _tt(key: str) -> str:
    tooltips = get_tooltip_messages("spqr")
    message = tooltips.get(key, "")
    return message if message else "Tooltip missing in src/assets/tooltips.json"


def _header_preview(header: SpqrHeader | None) -> str:
    if header is None:
        return "No header"
    return f"epoch={header.msg.epoch}, type={header.msg.msg_type.value}, n={header.n}"


def _before_after_rows(snapshot: dict[str, Any], tooltips: dict[str, str]) -> list[tuple[str, str, str | None, Any]]:
    return [
        (
            "State",
            str(snapshot.get("state", snapshot.get("node", "Unknown"))),
            tooltips.get("spqr_step_state", tooltips.get("spqr_step_node", "")),
            snapshot.get("state", snapshot.get("node", "Unknown")),
        ),
        ("Epoch", str(snapshot.get("epoch", "-")), tooltips.get("spqr_step_epoch", ""), snapshot.get("epoch", "-")),
        ("Direction", str(snapshot.get("direction", "-")), tooltips.get("spqr_step_direction", ""), snapshot.get("direction", "-")),
        ("RK", str(snapshot.get("rk_tail", "None")), tooltips.get("spqr_step_rk", ""), snapshot.get("rk_tail", "None")),
        (
            "CKs",
            str(snapshot.get("send_ck_tail", "None")),
            tooltips.get("spqr_step_send_ck", ""),
            snapshot.get("send_ck_tail", "None"),
        ),
        (
            "CKr",
            str(snapshot.get("recv_ck_tail", "None")),
            tooltips.get("spqr_step_recv_ck", ""),
            snapshot.get("recv_ck_tail", "None"),
        ),
    ]


def _send_keys_unsampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:

    header: SpqrHeader | None = step_data.get("header")
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}

    dk = after_node.get("dk")
    ek_header = after_node.get("ek_header")
    ek_vector = after_node.get("ek_vector")
    header_encoder = after_node.get("header_encoder") if isinstance(after_node.get("header_encoder"), dict) else {}

    ek_header_bytes = bytes(ek_header) if isinstance(ek_header, (bytes, bytearray)) else None
    header_encoder_message = header_encoder.get("message") if isinstance(header_encoder.get("message"), (bytes, bytearray)) else None
    header_bytes = bytes(header_encoder_message[:64]) if isinstance(header_encoder_message, (bytes, bytearray)) and len(header_encoder_message) >= 64 else None
    if header_bytes is None:
        header_bytes = ek_header_bytes
    mac = bytes(header_encoder_message[64:]) if isinstance(header_encoder_message, (bytes, bytearray)) and len(header_encoder_message) > 64 else None
    header_with_mac = bytes(header_encoder_message) if isinstance(header_encoder_message, (bytes, bytearray)) else None
    if header_with_mac is None and isinstance(header_bytes, bytes) and isinstance(mac, bytes):
        header_with_mac = header_bytes + mac

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else after.get("epoch")
    sending_epoch = msg_epoch - 1 if isinstance(msg_epoch, int) else "self.epoch - 1"

    return [
        {
            "title": "Generate key material",
            "control": ft.Column(
                controls=[
                    ft.Text("Generate key material", weight="bold"),
                    func_node(
                        "IncrementalKEM.KeyGen",
                        "spqr_step_keygen_fn",
                        full_value="Outputs: dk, ek_header, ek_vector",
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("dk", tooltip=_tt("spqr_step_dk"), full_value=dk),
                            var_node("ek_header", tooltip=_tt("spqr_step_ek_header"), full_value=ek_header),
                            var_node("ek_vector", tooltip=_tt("spqr_step_ek_vector"), full_value=ek_vector),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Authenticate header",
            "control": ft.Column(
                controls=[
                    ft.Text("Authenticate header", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("auth", tooltip=_tt("spqr_step_auth"), full_value=after_node.get("auth")),
                            var_node("epoch", tooltip=_tt("spqr_step_epoch"), full_value=msg_epoch),
                            var_node("header", tooltip=_tt("spqr_step_header_in_mac"), full_value=header_bytes),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Authenticator.MacHdr",
                        "spqr_step_machdr_fn",
                        full_value="mac = MacHdr(auth, epoch, header)",
                    ),
                    ft.Text("↓", size=24),
                    var_node("mac", tooltip=_tt("spqr_step_mac"), full_value=mac),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Start header stream",
            "control": ft.Column(
                controls=[
                    ft.Text("Start header stream", weight="bold"),
                    var_node("header||mac", tooltip=_tt("spqr_step_header_with_mac"), full_value=header_with_mac),
                    ft.Text("↓", size=24),
                    func_node(
                        "new Encoder",
                        "spqr_step_encode_fn",
                        full_value="header_encoder = Encode(header || mac)",
                    ),
                    ft.Text("↓", size=24),
                    var_node(
                        label="header_encoder",
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_header_encoder"),
                        full_value=header_encoder,
                    ),
                    ft.Divider(height=1),
                    func_node(
                        "Encoder.next_chunk",
                        "spqr_step_next_chunk",
                        full_value="chunk = header_encoder.next_chunk()",
                    ),
                    ft.Text("↓", size=24),
                    var_node("Header chunk", tooltip=_tt("spqr_step_chunk"), full_value=chunk),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Build message with header chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Build message with header chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("Header chunk", tooltip=_tt("spqr_step_chunk_in_msg"), full_value=chunk),
                            var_node("epoch", tooltip=_tt("spqr_step_epoch_in_msg"), full_value=msg_epoch),
                            var_node(
                                label="msg.type",
                                value="Hdr",
                                width=220,
                                tooltip=_tt("spqr_step_msg_type_in_msg"),
                                full_value="SpqrMessageType.HDR",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Build SpqrMessage",
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_build_message"),
                        full_value={
                            "epoch": msg_epoch,
                            "msg_type": "Hdr",
                            "data": chunk,
                        },
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("epoch", tooltip=_tt("spqr_step_msg_epoch"), full_value=msg_epoch),
                            var_node(
                                label="msg.type",
                                value="Hdr",
                                width=220,
                                tooltip=_tt("spqr_step_msg_type"),
                                full_value="SpqrMessageType.HDR",
                            ),
                            var_node("msg.data", tooltip=_tt("spqr_step_msg_data"), full_value=chunk),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Send result",
            "control": ft.Column(
                controls=[
                    ft.Text("Send result", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node(
                                "sending_epoch",
                                tooltip=_tt("spqr_step_sending_epoch"),
                                full_value=sending_epoch,
                            ),
                            var_node(
                                label="output_key",
                                value="None",
                                width=220,
                                tooltip=_tt("spqr_step_output_key"),
                                full_value=None,
                            ),
                            var_node(
                                label="next_state",
                                value="KeysSampled",
                                width=220,
                                tooltip=_tt("spqr_step_next_state"),
                                full_value="KeysSampled",
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
        },
    ]


def _send_keys_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:

    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next header chunk",
        build_title="Build message with header chunk",
        chunk_expr="chunk = header_encoder.next_chunk()",
        msg_type_label="Hdr",
        msg_type_full="SpqrMessageType.HDR",
        next_state="KeysSampled",
    )


def _send_header_sent(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ek_vector chunk",
        build_title="Build message with ek_vector chunk",
        chunk_expr="chunk = ek_encoder.next_chunk()",
        msg_type_label="Ek",
        msg_type_full="SpqrMessageType.EK",
        next_state="HeaderSent",
    )


def _send_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ek_vector chunk",
        build_title="Build message with ek_vector chunk and acknowledgment",
        chunk_expr="chunk = ek_encoder.next_chunk()",
        msg_type_label="EkCt1Ack",
        msg_type_full="SpqrMessageType.EK_CT1_ACK",
        next_state="Ct1Received",
    )


def _send_ek_sent_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_none_send_steps(
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        msg_type_label="None",
        msg_type_full="SpqrMessageType.NONE",
        next_state="EkSentCt1Received",
    )


def _send_no_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_none_send_steps(
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        msg_type_label="None",
        msg_type_full="SpqrMessageType.NONE",
        next_state="NoHeaderReceived",
    )


def _send_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}
    encrypt_trace = step_data.get("encrypt_trace") if isinstance(step_data.get("encrypt_trace"), dict) else {}
    auth = after_node.get("auth")
    ek_header = after_node.get("ek_header")
    encaps_secret = after_node.get("encaps_secret")
    ct1 = after_node.get("ct1")
    ct1_encoder = after_node.get("ct1_encoder") if isinstance(after_node.get("ct1_encoder"), dict) else {}
    output_key = encrypt_trace.get("scka_output_key")

    return [
        {
            "title": "Generate shared secret and ct1 using incremental KEM interface",
            "control": ft.Column(
                controls=[
                    ft.Text("Generate shared secret and ct1 using incremental KEM interface", weight="bold"),
                    var_node("ek_header", full_value=ek_header, tooltip=_tt("spqr_step_ek_header")),
                    ft.Text("↓", size=24),
                    func_node(
                        "IncrementalKEM.Encaps1",
                        "spqr_step_keygen_fn",
                        full_value="encaps_secret, ct1, ss = Encaps1(ek_header)",
                    ),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("encaps_secret", full_value=encaps_secret, tooltip=_tt("spqr_step_ek_vector")),
                            var_node("ct1", full_value=ct1, tooltip=_tt("spqr_step_chunk")),
                            var_node("ss", tooltip=_tt("spqr_step_key_evolution"),full_value=encrypt_trace.get("raw_ss")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {

            "title": "Derive output",
            "control": ft.Column(
                controls=[
                    ft.Text("Derive output key", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("ss", tooltip=_tt("spqr_step_ss"), full_value="ss_from_encaps1_value"),
                            var_node("epoch", tooltip=_tt("spqr_step_epoch"), full_value=ctx["msg_epoch"]),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "KDF_OK",
                        "spqr_step_kdf_ok",
                        full_value="KDF_OK(ss, epoch)",
                    ),
                    ft.Text("↓", size=24),
                    var_node("SS (output_key)",
                        full_value=_shared_to_text(output_key),
                        tooltip=_tt("spqr_step_output_key"),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Update authenticator",
            "control": ft.Column(
                controls=[
                    ft.Text("Update authenticator", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("auth", full_value=auth, tooltip=_tt("spqr_step_auth")),
                            var_node("epoch", full_value=ctx["msg_epoch"], tooltip=_tt("spqr_step_epoch")),
                            var_node("ss", full_value="ss_from_kdf_ok_value", tooltip=_tt("spqr_step_ss_after_kdf")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Authenticator.Update",
                        "spqr_step_machdr_fn",
                        full_value="Authenticator.Update(auth, epoch, ss)",
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Start ct1 stream",
            "control": ft.Column(
                controls=[
                    ft.Text("Start ct1 stream", weight="bold"),
                    var_node("ct1", full_value=ct1, tooltip=_tt("spqr_step_chunk")),
                    ft.Text("↓", size=24),
                    func_node(
                        "Encode",
                        "spqr_step_encode_fn",
                        full_value="ct1_encoder = Encode(ct1)",
                    ),
                    ft.Text("↓", size=24),
                    var_node(
                        "ct1_encoder",
                        last_n_chars(ct1_encoder.get("chunk_size"), 8),
                        width=220,
                        height=70,
                        tooltip=_tt("spqr_step_header_encoder"),
                        full_value=ct1_encoder,
                    ),
                    ft.Divider(height=1),
                    func_node(
                        "Encoder.next_chunk",
                        "spqr_step_next_chunk",
                        full_value="chunk = ct1_encoder.next_chunk()",
                    ),
                    ft.Text("↓", size=24),
                    var_node("chunk", full_value=ctx["chunk"], tooltip=_tt("spqr_step_chunk")),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        *_build_message_step(
            build_title="Build message with ct1 chunk",
            chunk=ctx["chunk"],
            msg_epoch=ctx["msg_epoch"],
            msg_type_label="Ct1",
            msg_type_full="SpqrMessageType.CT1",
        ),
        _build_send_result_step(
            sending_epoch=ctx["sending_epoch"],
            output_key_label="OutputKey",
            output_key=output_key,
            next_state="Ct1Sampled",
        ),
    ]


def _send_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ct1 chunk",
        build_title="Build message with ct1 chunk",
        chunk_expr="chunk = ct1_encoder.next_chunk()",
        msg_type_label="Ct1",
        msg_type_full="SpqrMessageType.CT1",
        next_state="Ct1Sampled",
    )


def _send_ek_received_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ct1 chunk",
        build_title="Build message with ct1 chunk",
        chunk_expr="chunk = ct1_encoder.next_chunk()",
        msg_type_label="Ct1",
        msg_type_full="SpqrMessageType.CT1",
        next_state="EkReceivedCt1Sampled",
    )


def _send_ct1_acknowledged(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_none_send_steps(
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        msg_type_label="None",
        msg_type_full="SpqrMessageType.NONE",
        next_state="Ct1Acknowledged",
    )


def _send_ct2_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ctx = _send_context(step_data)
    return _build_chunk_send_steps(
        chunk=ctx["chunk"],
        msg_epoch=ctx["msg_epoch"],
        sending_epoch=ctx["sending_epoch"],
        generate_title="Generate next ct2 chunk",
        build_title="Build message with ct2 chunk",
        chunk_expr="chunk = ct2_encoder.next_chunk()",
        msg_type_label="Ct2",
        msg_type_full="SpqrMessageType.CT2",
        next_state="Ct2Sampled",
    )


def _build_message_step(
    build_title: str,
    chunk: Any,
    msg_epoch: Any,
    msg_type_label: str,
    msg_type_full: str,
) -> list[dict[str, Any]]:
    return build_message_step(
        build_title=build_title,
        chunk=chunk,
        msg_epoch=msg_epoch,
        msg_type_label=msg_type_label,
        msg_type_full=msg_type_full,
        var_node=var_node,
        flow_node=var_node,
        tt=_tt,
    )


def _build_send_result_step(
    sending_epoch: Any,
    output_key_label: str,
    output_key: Any,
    next_state: str,
) -> dict[str, Any]:
    return build_send_result_step(
        sending_epoch=sending_epoch,
        output_key_label=output_key_label,
        output_key=output_key,
        next_state=next_state,
        var_node=var_node,
        flow_node=var_node,
        tt=_tt,
    )


def _build_chunk_send_steps(
    chunk: Any,
    msg_epoch: Any,
    sending_epoch: Any,
    generate_title: str,
    build_title: str,
    chunk_expr: str,
    msg_type_label: str,
    msg_type_full: str,
    next_state: str,
) -> list[dict[str, Any]]:
    return build_chunk_send_steps(
        chunk=chunk,
        msg_epoch=msg_epoch,
        sending_epoch=sending_epoch,
        generate_title=generate_title,
        build_title=build_title,
        chunk_expr=chunk_expr,
        msg_type_label=msg_type_label,
        msg_type_full=msg_type_full,
        next_state=next_state,
        var_node=var_node,
        flow_node=var_node,
        function_node=func_node,
        tt=_tt,
    )


def _build_none_send_steps(
    msg_epoch: Any,
    sending_epoch: Any,
    msg_type_label: str,
    msg_type_full: str,
    next_state: str,
) -> list[dict[str, Any]]:
    return build_none_send_steps(
        msg_epoch=msg_epoch,
        sending_epoch=sending_epoch,
        msg_type_label=msg_type_label,
        msg_type_full=msg_type_full,
        next_state=next_state,
        var_node=var_node,
        flow_node=var_node,
        tt=_tt,
    )


def _send_context(step_data: dict[str, Any]) -> dict[str, Any]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}
    active_node = after_node if after_node else before_node

    msg_epoch = (
        header.msg.epoch
        if header is not None
        else active_node.get("epoch", after.get("epoch", before.get("epoch")))
    )
    sending_epoch = msg_epoch - 1 if isinstance(msg_epoch, int) else "self.epoch - 1"
    chunk = header.msg.data if header is not None else None

    return {
        "header": header,
        "before": before,
        "after": after,
        "before_node": before_node,
        "after_node": after_node,
        "msg_epoch": msg_epoch,
        "sending_epoch": sending_epoch,
        "chunk": chunk,
    }


def _output_key_expected(action: str, state_name: str) -> bool:
    if action == "send" and state_name == "HeaderReceived":
        return True
    if action == "receive" and state_name == "EkSentCt1Received":
        return True
    return False


def _build_intro_step(before: dict[str, Any], tooltips: dict[str, str]) -> dict[str, Any]:
    intro_control = ft.Column(
        controls=[
            party_state_panel(
                "Before snapshot",
                _before_after_rows(before, tooltips),
                tooltip=tooltips.get("spqr_step_before_panel", ""),
                synced_labels=None,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "title": "State before",
        "control": intro_control,
    }


def _build_output_key_step(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    header: SpqrHeader | None,
    tooltips: dict[str, str],
) -> dict[str, Any]:
    rk_changed = before.get("rk_tail") != after.get("rk_tail")
    output_key_produced = _output_key_expected(action, state_name)
    output_label = "output_key produced" if output_key_produced else "output_key = None"
    rk_label = "RK derivation needed" if rk_changed else "No new RK derived"

    output_control = ft.Column(
        controls=[
            ft.Text("Output key and root-key decision", weight="bold"),
            var_node(
                label="SCKA output",
                value=output_label,
                width=320,
                tooltip=tooltips.get("spqr_step_key_evolution", ""),
            ),
            ft.Text("↓", size=24),
            var_node(
                label="Root key derivation",
                value=rk_label,
                width=320,
                tooltip=tooltips.get("spqr_step_rk_change", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "title": "Output key decision",
        "control": output_control,
    }


def _build_rk_derivation_step(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    step_data: dict[str, Any],
) -> dict[str, Any] | None:
    if before.get("rk_tail") == after.get("rk_tail"):
        return None

    derivation_trace = step_data.get("encrypt_trace") if isinstance(step_data.get("encrypt_trace"), dict) else {}
    scka_output_key = derivation_trace.get("scka_output_key")
    if scka_output_key is None:
        scka_output_key = "from SCKA output"

    rk_before = derivation_trace.get("rk_before", before.get("rk_tail"))
    rk_after = derivation_trace.get("rk_after", after.get("rk_tail"))
    new_cks = derivation_trace.get("new_cks", after.get("send_ck_tail"))
    new_ckr = derivation_trace.get("new_ckr", after.get("recv_ck_tail"))

    return {
        "title": "RK derivation",
        "control": ft.Column(
            controls=[
                ft.Text("RK derivation", weight="bold"),
                ft.Row(
                    controls=[
                        var_node("RK", full_value=rk_before, tooltip=_tt("spqr_step_rk")),
                        var_node("SCKA_output_key", full_value=scka_output_key, tooltip=_tt("spqr_step_output_key")),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                    wrap=True,
                ),
                ft.Text("↓", size=24),
                func_node(
                    "KDF_SCKA_RK",
                    "spqr_step_key_evolution",
                    full_value="new_RK, new_CKs, new_CKr = KDF_SCKA_RK(RK, SCKA_output_key)",
                ),
                ft.Text("↓", size=24),
                ft.Row(
                    controls=[
                        var_node("new RK", full_value=rk_after, tooltip=_tt("spqr_step_rk")),
                        var_node("new CKs", full_value=new_cks, tooltip=_tt("spqr_step_send_ck")),
                        var_node("new CKr", full_value=new_ckr, tooltip=_tt("spqr_step_recv_ck")),
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


def _build_send_steps(state_name: str, step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    builders: dict[str, Callable[[dict[str, Any], dict[str, str]], list[dict[str, Any]]]] = {
        "KeysUnsampled": _send_keys_unsampled,
        "KeysSampled": _send_keys_sampled,
        "HeaderSent": _send_header_sent,
        "Ct1Received": _send_ct1_received,
        "EkSentCt1Received": _send_ek_sent_ct1_received,
        "NoHeaderReceived": _send_no_header_received,
        "HeaderReceived": _send_header_received,
        "Ct1Sampled": _send_ct1_sampled,
        "EkReceivedCt1Sampled": _send_ek_received_ct1_sampled,
        "Ct1Acknowledged": _send_ct1_acknowledged,
        "Ct2Sampled": _send_ct2_sampled,
    }
    builder = builders.get(state_name)
    if builder is None:
        return []
    return builder(step_data, tooltips)


def _receive_keys_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    condition_met = msg_epoch == self_epoch and msg_type == "Ct1"

    ct1_decoder = after_node.get("ct1_decoder") if isinstance(after_node.get("ct1_decoder"), dict) else None
    ek_vector = before_node.get("ek_vector", after_node.get("ek_vector"))
    ek_encoder = after_node.get("ek_encoder") if isinstance(after_node.get("ek_encoder"), dict) else None

    return [
        {
            "title": "Initialize Decoder",
            "control": ft.Column(
                controls=[
                    ft.Text("Initialize Decoder", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                            var_node("msg.type", full_value=str(msg_type), tooltip=_tt("spqr_step_msg_type")),
                            var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    var_node(label="Condition", value="msg.epoch == self.epoch and msg.type == Ct1", width=420, tooltip=_tt("spqr_step_state_op"), full_value=condition_met),
                    ft.Text("↓", size=24),
                    func_node("new Decoder()",),
                    ft.Text("↓", size=24),
                    var_node(
                        label="ct1_decoder",
                        width=260,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=ct1_decoder,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "chunk -> Decoder add chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("chunk -> Decoder add chunk", weight="bold"),
                    var_node("msg.data - Chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                    ft.Text("↓", size=24),
                    func_node("Decoder.add_chunk", full_value="ct1_decoder.add_chunk(chunk)"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "ek_vector -> Initialize EkEncoder -> EkEncoder",
            "control": ft.Column(
                controls=[
                    ft.Text("ek_vector -> Initialize EkEncoder -> EkEncoder", weight="bold"),
                    var_node("ek_vector", full_value=ek_vector, tooltip=_tt("spqr_step_ek_vector")),
                    ft.Text("↓", size=24),
                    func_node(
                        "new Encoder()",
                        "spqr_step_encode_fn",
                    ),
                    ft.Text("↓", size=24),
                        var_node(
                        "EkEncoder",
                        "initialized with ek_vector" if ek_encoder is not None else "not initialized",
                        width=260,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=ek_encoder,
                    ),
                    ft.Divider(height=10),
                        var_node(
                        "Next state",
                        "HeaderSent",
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_header_sent(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    ct1_decoder = before_node.get("ct1_decoder") if isinstance(before_node.get("ct1_decoder"), dict) else None
    has_message = str(after.get("state", before.get("state", ""))) == "Ct1Received"

    return [
        {
            "title": "chunk -> Decoder add chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("chunk -> Decoder add chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                            var_node(label="Decoder", value="ct1_decoder", width=220, tooltip=_tt("spqr_step_state_op"), full_value=ct1_decoder),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node("Decoder.add_chunk", full_value="ct1_decoder.add_chunk(chunk)"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decoder has message()",
            "control": ft.Column(
                controls=[
                    ft.Text("Decoder has message()", weight="bold"),
                    func_node("Decoder.has_message", full_value="ct1_decoder.has_message()"),
                    ft.Text("↓", size=24),
                    var_node(label="has_message", value=("yes" if has_message else "no"), width=220, tooltip=_tt("spqr_step_state_op"), full_value=has_message),
                    ft.Text("↓", size=24),
                    func_node(
                        "state transition" if has_message else "remain in current state",
                        "Ct1Received" if has_message else "HeaderSent",
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_no_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_node = after.get("scka_node") if isinstance(after.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    condition_met = msg_epoch == self_epoch and msg_type == "Hdr"
    next_state = after.get("state", before.get("state"))
    completed = next_state == "HeaderReceived"
    header_with_mac = after_node.get("ek_header") if isinstance(after_node.get("ek_header"), (bytes, bytearray)) else None

    return [
        {
            "title": "Initialize header decoder",
            "control": ft.Column(
                controls=[
                    ft.Text("Initialize header decoder", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                            var_node("msg.type", full_value=str(msg_type), width=220, tooltip=_tt("spqr_step_msg_type")),
                            var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    var_node(label="Condition", value="msg.epoch == self.epoch and msg.type == Hdr", width=420, tooltip=_tt("spqr_step_state_op"), full_value=condition_met),
                    ft.Text("↓", size=24),
                    var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                    ft.Text("↓", size=24),
                    func_node("Decoder.add_chunk", full_value="header_decoder.add_chunk(chunk)"),
                    ft.Text("↓", size=24),
                    var_node("header with MAC", full_value=header_with_mac, tooltip=_tt("spqr_step_header_with_mac")),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decoder.has_message()",
            "control": ft.Column(
                controls=[
                    ft.Text("Decoder.has_message()", weight="bold"),
                    var_node(
                        "has_message",
                        value="yes" if completed else "no",
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=completed,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "state transition" if completed else "remain in current state",
                        value="HeaderReceived" if completed else "NoHeaderReceived",
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=next_state,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_header_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}

    return [
        {
            "title": "No action taken",
            "control": ft.Column(
                controls=[
                    ft.Text("No action taken", weight="bold"),
                    var_node(
                        label="HeaderReceived.receive",
                        value="noop",
                        width=260,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value="No action taken",
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}
    after_state = str(after.get("state", before.get("state", "")))

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    msg_type_label = str(msg_type)
    is_ek_branch = msg_epoch == self_epoch and msg_type_label == "Ek"
    is_ek_ack_branch = msg_epoch == self_epoch and msg_type_label == "EkCt1Ack"

    if is_ek_branch:
        completed = after_state == "EkReceivedCt1Sampled"
        return [
            {
                "title": "EK branch guard",
                "control": ft.Column(
                    controls=[
                        ft.Text("EK branch guard", weight="bold"),
                        ft.Row(
                            controls=[
                                var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                                var_node("msg.type", full_value=msg_type_label, tooltip=_tt("spqr_step_msg_type")),
                                var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=16,
                            wrap=True,
                        ),
                        ft.Text("↓", size=24),
                        var_node(
                            "Condition",
                            "msg.epoch == self.epoch and msg.type == Ek",
                            width=420,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=is_ek_branch,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Add EK chunk",
                "control": ft.Column(
                    controls=[
                        ft.Text("Add EK chunk", weight="bold"),
                        var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                        ft.Text("↓", size=24),
                        func_node("ek_decoder.add_chunk", full_value="ek_decoder.add_chunk(chunk)"),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Check EK completeness",
                "control": ft.Column(
                    controls=[
                        ft.Text("Check EK completeness", weight="bold"),
                        var_node(
                            "ek_decoder.has_message",
                            value="yes" if completed else "no",
                            width=260,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=completed,
                        ),
                        ft.Text("↓", size=24),
                        func_node(
                            "state transition",
                            value="EkReceivedCt1Sampled" if completed else "Ct1Sampled",
                            width=260,
                            tooltip=_tt("spqr_step_next_state"),
                            full_value=after_state,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
        ]

    if is_ek_ack_branch:
        completed = after_state == "Ct2Sampled"
        return [
            {
                "title": "EK_CT1_ACK branch guard",
                "control": ft.Column(
                    controls=[
                        ft.Text("EK_CT1_ACK branch guard", weight="bold"),
                        ft.Row(
                            controls=[
                                var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                                var_node("msg.type", value=msg_type_label, tooltip=_tt("spqr_step_msg_type"), full_value=msg_type_label),
                                var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=16,
                            wrap=True,
                        ),
                        ft.Text("↓", size=24),
                        var_node(
                            "Condition",
                            "msg.epoch == self.epoch and msg.type == EkCt1Ack",
                            width=420,
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=is_ek_ack_branch,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Add EK_CT1_ACK chunk",
                "control": ft.Column(
                    controls=[
                        ft.Text("Add EK_CT1_ACK chunk", weight="bold"),
                        var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                        ft.Text("↓", size=24),
                        func_node(
                            "ek_decoder.add_chunk",
                       
                            full_value="ek_decoder.add_chunk(chunk)",
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
            {
                "title": "Check EK completeness",
                "control": ft.Column(
                    controls=[
                        ft.Text("Check EK completeness", weight="bold"),
                        var_node(
                            "ek_decoder.has_message",
                            value="yes" if completed else "no",
                            tooltip=_tt("spqr_step_state_op"),
                            full_value=completed,
                        ),
                        ft.Text("↓", size=24),
                        func_node(
                            "state transition",
                            value="Ct2Sampled" if completed else "Ct1Acknowledged",
                            width=300,
                            tooltip=_tt("spqr_step_next_state"),
                            full_value=after_state,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            },
        ]

    return [
        {
            "title": "No matching branch",
            "control": ft.Column(
                controls=[
                    ft.Text("No matching branch", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                            var_node(label="msg.type", tooltip=_tt("spqr_step_msg_type"), full_value=msg_type_label),
                            var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "state transition",
                        "Ct1Sampled (no-op)",
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after_state,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        }
    ]


def _receive_ek_received_ct1_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}

    return [
        {
            "title": "Complete encapsulation",
            "control": ft.Column(
                controls=[
                    ft.Text("Complete encapsulation", weight="bold"),
                    var_node(
                        label="EK_CT1_ACK",
                        value=str(step_data.get("header").msg.msg_type.value if isinstance(step_data.get("header"), SpqrHeader) else ""),
                        width=240,
                        tooltip=_tt("spqr_step_msg_type"),
                        full_value=step_data.get("header").msg.to_dict() if isinstance(step_data.get("header"), SpqrHeader) else None,
                    ),
                    ft.Text("↓", size=24),
                    func_node("Encaps2 + MacCt", full_value="ct2 = Encaps2(...); mac = MacCt(...)"),
                    ft.Text("↓", size=24),
                    func_node(
                        "state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct1_acknowledged(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    completed = after.get("state", before.get("state")) == "Ct2Sampled"

    return [
        {
            "title": "Add EK_CT1_ACK chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Add EK_CT1_ACK chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                            var_node("msg.type", full_value=str(msg_type), tooltip=_tt("spqr_step_msg_type")),
                            var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                    ft.Text("↓", size=24),
                    func_node("ek_decoder.add_chunk", full_value="ek_decoder.add_chunk(chunk)"),
                    ft.Text("↓", size=24),
                    var_node(
                        label="has_message",
                        value="yes" if completed else "no",
                        width=220,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=completed,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "state transition",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct2_sampled(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    next_epoch = msg_epoch + 1 if isinstance(msg_epoch, int) else None

    return [
        {
            "title": "Check next epoch",
            "control": ft.Column(
                controls=[
                    ft.Text("Check next epoch", weight="bold"),
                    var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                    ft.Text("↓", size=24),
                    var_node(
                        label="Condition",
                        value="msg.epoch == self.epoch + 1",
                        width=320,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=bool(next_epoch),
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Next state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")

    return [
        {
            "title": "Initialize ct2 decoder",
            "control": ft.Column(
                controls=[
                    ft.Text("Initialize ct2 decoder", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                            var_node("msg.type", full_value=str(msg_type), tooltip=_tt("spqr_step_msg_type")),
                            var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Condition",
                        "msg.epoch == self.epoch and msg.type == Ct2",
                        width=420,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=msg_type == "Ct2",
                    ),
                    ft.Text("↓", size=24),
                    var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                    ft.Text("↓", size=24),
                    func_node("ct2_decoder = Decoder_new(CT2_SIZE + MAC_SIZE)", full_value="ct2_decoder = Decoder_new(CT2_SIZE + MAC_SIZE)"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Add CT2 chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Add CT2 chunk", weight="bold"),
                    func_node("ct2_decoder.add_chunk", full_value="ct2_decoder.add_chunk(chunk)"),
                    ft.Text("↓", size=24),
                    func_node(
                        "state transition",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _receive_ek_sent_ct1_received(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    before_node = before.get("scka_node") if isinstance(before.get("scka_node"), dict) else {}

    chunk = header.msg.data if header is not None else None
    msg_epoch = header.msg.epoch if header is not None else before_node.get("epoch")
    msg_type = header.msg.msg_type.value if header is not None else None
    self_epoch = before_node.get("epoch")
    completed = after.get("state", before.get("state")) == "NoHeaderReceived"
    output_key = step_data.get("receive_trace", {}).get("scka_output_key") if isinstance(step_data.get("receive_trace"), dict) else None

    return [
        {
            "title": "Add CT2 chunk",
            "control": ft.Column(
                controls=[
                    ft.Text("Add CT2 chunk", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg.epoch", full_value=msg_epoch, tooltip=_tt("spqr_step_epoch")),
                            var_node("msg.type", full_value=str(msg_type), tooltip=_tt("spqr_step_msg_type")),
                            var_node("self.epoch", full_value=self_epoch, tooltip=_tt("spqr_step_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    var_node("chunk", full_value=chunk, tooltip=_tt("spqr_step_chunk")),
                    ft.Text("↓", size=24),
                    func_node("ct2_decoder.add_chunk", full_value="ct2_decoder.add_chunk(chunk)"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Decoder.has_message()",
            "control": ft.Column(
                controls=[
                    ft.Text("Decoder.has_message()", weight="bold"),
                    var_node(
                        label="has_message",
                        value="yes" if completed else "no",
                        width=220,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value=completed,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "state transition" if completed else "remain in current state",
                        str(after.get("state", before.get("state"))),
                        width=260,
                        tooltip=_tt("spqr_step_next_state"),
                        full_value=after.get("state", before.get("state")),
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
        {
            "title": "Output key",
            "control": ft.Column(
                controls=[
                    ft.Text("Output key", weight="bold"),
                    var_node("output_key", full_value=output_key, tooltip=_tt("spqr_step_output_key")),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _build_receive_chain_steps(state_name: str, step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    builders: dict[str, Callable[[dict[str, Any], dict[str, str]], list[dict[str, Any]]]] = {
        # "KeysUnsampled": _receive_keys_unsampled,
        "KeysSampled": _receive_keys_sampled,
        "HeaderSent": _receive_header_sent,
        "Ct1Received": _receive_ct1_received,
        "EkSentCt1Received": _receive_ek_sent_ct1_received,
        "NoHeaderReceived": _receive_no_header_received,
        "HeaderReceived": _receive_header_received,
        "Ct1Sampled": _receive_ct1_sampled,
        "EkReceivedCt1Sampled": _receive_ek_received_ct1_sampled,
        "Ct1Acknowledged": _receive_ct1_acknowledged,
        "Ct2Sampled": _receive_ct2_sampled,
    }
    builder = builders.get(state_name)
    if builder is None:
        return []
    return builder(step_data, tooltips)


def _build_send_message_pipeline_phase2_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    encrypt_trace = step_data.get("encrypt_trace") if isinstance(step_data.get("encrypt_trace"), dict) else {}

    sending_epoch = encrypt_trace.get("sending_epoch", header.msg.epoch - 1 if header is not None else "-")
    counter = encrypt_trace.get("counter", header.n if header is not None else "-")
    chain_key_before = encrypt_trace.get("chain_key_before")
    chain_key_after = encrypt_trace.get("chain_key_after")
    mk = encrypt_trace.get("mk")

    header_msg = header.msg if header is not None else None
    header_payload = {
        "msg": header_msg.to_dict() if header_msg is not None else None,
        "n": header.n if header is not None else None,
    }

    steps: list[dict[str, Any]] = []

    steps.append(
        {
            "title": "Message key derivation",
            "control": ft.Column(
                controls=[
                    ft.Text("Message key derivation", weight="bold"),
                    var_node("sending_epoch", full_value=sending_epoch, tooltip=_tt("spqr_step_sending_epoch")),
                    ft.Text("↓", size=24),
                    func_node("Get sending chain", f"epoch {sending_epoch}"),
                    ft.Text("↓", size=24),
                    var_node("CKs", full_value=chain_key_before, tooltip=_tt("spqr_step_send_ck")),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            var_node("counter", full_value=counter, tooltip=_tt("spqr_step_msg_epoch")),
                            var_node("CKs", full_value=chain_key_before, tooltip=_tt("spqr_step_send_ck")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node("KDF_SCKA_CK", "spqr_step_kdf_scka_ck"),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("new CKs", full_value=chain_key_after, tooltip=_tt("spqr_step_send_ck")),
                            var_node("mk", full_value=mk, tooltip=_tt("spqr_step_output_key")),
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
    )

    steps.append(
        {
            "title": "Build SPQR header",
            "control": ft.Column(
                controls=[
                    ft.Text("Build SPQR header", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("msg", full_value=_header_preview(header) if header is not None else "None", tooltip=_tt("spqr_step_header")),
                            var_node("n", full_value=header.n if header is not None else None, tooltip=_tt("spqr_step_msg_epoch")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Build SpqrHeader",
                        "spqr_step_build_message",
                        full_value="header = SpqrHeader(msg=msg, n=n)",
                    ),
                    ft.Text("↓", size=24),
                    var_node(
                        "header",
                        value=_header_preview(header),
                        width=420,
                        tooltip=_tt("spqr_step_header"),
                        full_value=header_payload,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        }
    )

    return steps


def _build_send_phase2_5_pqxdh_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    pqxdh_header = step_data.get("pqxdh_header") if isinstance(step_data.get("pqxdh_header"), dict) else None
    header = step_data.get("header") if isinstance(step_data.get("header"), type(step_data.get("header"))) else None
    if not isinstance(pqxdh_header, dict):
        return []

    pqxdh_preview = pqxdh_header_preview(pqxdh_header)
    combined_header_full = {
        "header": {"msg": header.msg.to_dict() if header is not None else None, "n": header.n if header is not None else None},
        "pqxdh_header": pqxdh_header,
    }
    combined_header_preview = f"{_header_preview(header)} | pqxdh: {pqxdh_preview}"
    return [
        {
            "title": "Add PQXDH header data",
            "control": ft.Column(
                controls=[
                    ft.Text("Add PQXDH header data", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node(label="PQXDH header", value=pqxdh_preview, width=420, full_value=pqxdh_header, tooltip=_tt("pqxdh_step_node_verify_pq")),
                            var_node(label="Header", value=_header_preview(header), width=320, full_value={"msg": header.msg.to_dict() if header is not None else None, "n": header.n if header is not None else None}, tooltip=_tt("spqr_step_header")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node("CONCAT"),
                    ft.Text("↓", size=24),
                    var_node(label="Header including PQXDH data", value=combined_header_preview, width=620, height=110, full_value=combined_header_full, tooltip=_tt("pqxdh_step_node_verify_pq")),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        }
    ]



def _build_send_message_pipeline_phase3_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    plaintext = step_data.get("plaintext")
    ciphertext = step_data.get("cipher")
    encrypt_trace = step_data.get("encrypt_trace") if isinstance(step_data.get("encrypt_trace"), dict) else {}
    mk = encrypt_trace.get("mk")
    ad_header = encrypt_trace.get("ad_header")

    return [
        {
            "title": "Encrypt message",
            "control": ft.Column(
                controls=[
                    ft.Text("Encrypt message", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("mk", full_value=mk, tooltip=_tt("spqr_step_output_key")),
                            var_node("plaintext", full_value=format_plaintext(plaintext), tooltip=_tt("spqr_step_chunk")),
                            var_node("AD||header", full_value=ad_header, tooltip=_tt("spqr_step_header_with_mac")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Encrypt",
                        "spqr_step_build_message",
                        full_value="ciphertext = ENCRYPT(mk, plaintext, AD || header)",
                    ),
                    ft.Text("↓", size=24),
                    var_node("ciphertext", full_value=ciphertext, tooltip=_tt("spqr_step_msg_data")),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        }
    ]


def _build_send_message_pipeline_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    return [
        *_build_send_message_pipeline_phase2_steps(step_data, tooltips),
        *_build_send_phase2_5_pqxdh_steps(step_data, tooltips),
        *_build_send_message_pipeline_phase3_steps(step_data, tooltips),
    ]


def _build_receive_message_pipeline_phase2_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    receive_trace = step_data.get("receive_trace") if isinstance(step_data.get("receive_trace"), dict) else {}

    receiving_epoch = receive_trace.get("receiving_epoch", header.msg.epoch - 1 if header is not None else "-")
    counter = receive_trace.get("counter", header.n if header is not None else "-")
    chain_key_before = receive_trace.get("chain_key_before")
    chain_key_after = receive_trace.get("chain_key_after")
    mk = receive_trace.get("mk")
    used_skipped_key = bool(receive_trace.get("used_skipped_key", False))

    derivation_note = "MK restored from skipped-key store" if used_skipped_key else "MK derived from receive chain"

    return [
        {
            "title": "Message key derivation",
            "control": ft.Column(
                controls=[
                    ft.Text("Message key derivation", weight="bold"),
                    var_node("receiving_epoch", full_value=receiving_epoch, tooltip=_tt("spqr_step_epoch")),
                    ft.Text("↓", size=24),
                    func_node(
                        "Get receiving chain",
                        f"epoch {receiving_epoch}",
                        width=260,
                        tooltip=_tt("spqr_step_recv_ck"),
                        full_value={"epoch": receiving_epoch},
                    ),
                    ft.Text("↓", size=24),
                    var_node(
                        label="MK",
                        value=derivation_note,
                        width=320,
                        tooltip=_tt("spqr_step_state_op"),
                        full_value={"used_skipped_key": used_skipped_key},
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            var_node("counter", full_value=counter, tooltip=_tt("spqr_step_msg_epoch")),
                            var_node("CKr", full_value=chain_key_before, tooltip=_tt("spqr_step_recv_ck")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node("KDF_SCKA_CK", "spqr_step_kdf_scka_ck"),
                    ft.Text("↓", size=24),
                    ft.Row(
                        controls=[
                            var_node("new CKr", full_value=chain_key_after, tooltip=_tt("spqr_step_recv_ck")),
                            var_node("mk", full_value=mk, tooltip=_tt("spqr_step_output_key")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _build_receive_message_pipeline_phase3_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    ciphertext = step_data.get("cipher")
    decrypted = step_data.get("decrypted")
    receive_trace = step_data.get("receive_trace") if isinstance(step_data.get("receive_trace"), dict) else {}
    mk = receive_trace.get("mk")
    ad_header = receive_trace.get("ad_header")

    return [
        {
            "title": "Decrypt message",
            "control": ft.Column(
                controls=[
                    ft.Text("Decrypt message", weight="bold"),
                    ft.Row(
                        controls=[
                            var_node("mk", full_value=mk, tooltip=_tt("spqr_step_output_key")),
                            var_node("ciphertext", full_value=ciphertext, tooltip=_tt("spqr_step_msg_data")),
                            var_node("AD||header", full_value=ad_header, tooltip=_tt("spqr_step_header_with_mac")),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    ft.Text("↓", size=24),
                    func_node(
                        "Decrypt",
                        "spqr_step_build_message",
                        full_value="plaintext = DECRYPT(mk, ciphertext, AD || header)",
                    ),
                    ft.Text("↓", size=24),
                    var_node("plaintext", full_value=format_plaintext(decrypted), tooltip=_tt("spqr_step_chunk")),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        },
    ]


def _build_receive_message_pipeline_steps(step_data: dict[str, Any], tooltips: dict[str, str]) -> list[dict[str, Any]]:
    return [
        *_build_receive_message_pipeline_phase2_steps(step_data, tooltips),
        *_build_receive_message_pipeline_phase3_steps(step_data, tooltips),
    ]


def _build_after_step(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    tooltips: dict[str, str],
) -> dict[str, Any]:
    before_rows = _before_after_rows(before, tooltips)
    after_rows = _before_after_rows(after, tooltips)

    before_state = before.get("state", before.get("node"))
    after_state = after.get("state", after.get("node"))

    changed_labels: set[str] = set()
    if before_state != after_state:
        changed_labels.add("State")
    if before.get("epoch") != after.get("epoch"):
        changed_labels.add("Epoch")
    if before.get("direction") != after.get("direction"):
        changed_labels.add("Direction")
    if before.get("rk_tail") != after.get("rk_tail"):
        changed_labels.add("RK")
    if before.get("send_ck_tail") != after.get("send_ck_tail"):
        changed_labels.add("CKs")
    if before.get("recv_ck_tail") != after.get("recv_ck_tail"):
        changed_labels.add("CKr")

    state_comparison = ft.Row(
        controls=[
            party_state_panel(
                "Before",
                before_rows,
                tooltip=tooltips.get("spqr_step_before_panel", ""),
                highlight_labels=changed_labels,
                synced_labels=None,
            ),
            party_state_panel(
                "After",
                after_rows,
                tooltip=tooltips.get("spqr_step_after_panel", ""),
                highlight_labels=changed_labels,
                synced_labels=None,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=20,
        wrap=True,
    )

    after_control = ft.Column(
        controls=[
            ft.Text("State before and after", weight="bold"),
            state_comparison,
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "title": "State comparison",
        "control": after_control,
    }


def build_alice_pqxdh_phase1_steps(
    pqxdh_state_data: dict[str, Any] | None,
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    derived = {}
    last_bundle = {}
    real_pqxdh_header = {}
    if isinstance(pqxdh_state_data, dict):
        initial_message = pqxdh_state_data.get("initial_message", {})
        if isinstance(initial_message, dict) and isinstance(initial_message.get("header"), dict):
            real_pqxdh_header = initial_message["header"]
        else:
            real_pqxdh_header = pqxdh_state_data.get("initial_header") if isinstance(pqxdh_state_data.get("initial_header"), dict) else {}
        derived = pqxdh_state_data.get("alice_derived") if isinstance(pqxdh_state_data.get("alice_derived"), dict) else {}
        last_bundle = pqxdh_state_data.get("last_bundle_for_alice") if isinstance(pqxdh_state_data.get("last_bundle_for_alice"), dict) else {}
        if not derived:
            derived = pqxdh_state_data

    shared_secret = derived.get("shared_secret_hex") if isinstance(derived.get("shared_secret_hex"), str) else derived.get("shared_secret")
    associated_data = derived.get("associated_data_hex") if isinstance(derived.get("associated_data_hex"), str) else derived.get("associated_data")
    header_preview = pqxdh_header_preview(real_pqxdh_header)
    alice_identity_public = None
    if isinstance(pqxdh_state_data, dict):
        alice_local = pqxdh_state_data.get("alice_local", {})
        alice_identity = alice_local.get("identity_dh", {})
        alice_identity_public = alice_identity.get("public", None)

    opk_pub = last_bundle.get("opk_public") if last_bundle.get("opk_public") not in {None, "", "-"} else None
    pq_opk_pub = last_bundle.get("pq_opk_public") if last_bundle.get("pq_opk_public") not in {None, "", "-"} else None
    pq_prekey_source = last_bundle.get("pq_prekey_source", "pqspk")

    bundle_controls = [
        ft.Text("Bundle from server:", size=12, weight="bold"),
        ft.Row(
            controls=[
                var_node(label="IK_B", value=last_n_chars(last_bundle.get("identity_dh_public"), 8), width=180, full_value=last_bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                var_node(label="SPK_B", value=last_n_chars(last_bundle.get("signed_prekey_public"), 8), width=180, full_value=last_bundle.get("signed_prekey_public"), tooltip=tooltips.get("x3dh_step_key_spk_pub", "")),
                var_node(label="SPK_B_sig", value=last_n_chars(last_bundle.get("signed_prekey_signature"), 8), width=180, full_value=last_bundle.get("signed_prekey_signature"), tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            wrap=True,
        ),
    ]

    if opk_pub is not None:
        bundle_controls.append(
            ft.Row(
                controls=[
                    var_node(label="OPK_B", value=last_n_chars(opk_pub), width=180, full_value=opk_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            )
        )

    bundle_controls.extend([
        ft.Row(
            controls=[
                var_node(label="PQSPK_B", value=last_n_chars(last_bundle.get("pq_signed_prekey_public"), 8), width=180, full_value=last_bundle.get("pq_signed_prekey_public"), tooltip=tooltips.get("x3dh_step_key_pqspk_pub", "")),
                var_node(label="PQSPK_B_sig", value=last_n_chars(last_bundle.get("pq_signed_prekey_signature"), 8), width=180, full_value=last_bundle.get("pq_signed_prekey_signature"), tooltip=tooltips.get("x3dh_step_key_spk_sig", "")),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            wrap=True,
        ),
    ])

    if pq_opk_pub is not None:
        bundle_controls.append(
            ft.Row(
                controls=[
                    var_node(label=f"PQ{pq_prekey_source.upper()}_B", value=last_n_chars(pq_opk_pub), width=180, full_value=pq_opk_pub, tooltip=tooltips.get("x3dh_step_key_opk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            )
        )

    step1 = ft.Column(
        controls=[
            ft.Text("1) Alice requests Bob's bundle", weight="bold"),
            *bundle_controls,
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2a) Alice verifies EC signature (SPK_B_sig)", weight="bold"),
            ft.Row(
                controls=[
                    var_node("IK_B", full_value=last_bundle.get("identity_dh_public"), tooltip=_tt("x3dh_step_key_ik_pub")),
                    var_node("SPK_B", full_value=last_bundle.get("signed_prekey_public"), tooltip=_tt("x3dh_step_key_spk_pub")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=20),
            func_node("VERIFY_EC", "spqr_step_state_op", full_value="Verify EC signature"),
            ft.Text("↓", size=20),
            var_node(label="Verification result", value="Valid signature", width=200, tooltip=_tt("spqr_step_state_op"), full_value="Valid signature"),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("2b) Alice verifies PQ signature (PQSPK_B_sig)", weight="bold"),
            ft.Row(
                controls=[
                    var_node("IK_B", full_value=last_bundle.get("identity_dh_public"), tooltip=_tt("x3dh_step_key_ik_pub")),
                    var_node("PQSPK_B", full_value=last_bundle.get("pq_signed_prekey_public"), tooltip=_tt("x3dh_step_key_pqspk_pub")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=20),
            func_node("VERIFY_PQ", "spqr_step_state_op", full_value="Verify PQ signature"),
            ft.Text("↓", size=20),
            var_node(label="Verification result", value="Valid signature", width=200, tooltip=_tt("spqr_step_state_op"), full_value="Valid signature"),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    pqpkb_pub = pq_opk_pub if pq_opk_pub else last_bundle.get("pq_signed_prekey_public")
    pq_shared_secret = derived.get("pq_secret") if isinstance(derived.get("pq_secret"), str) else derived.get("pq_shared_secret")
    step4 = ft.Column(
        controls=[
            ft.Text("3) Alice encapsulates PQ prekey material", weight="bold"),
            var_node("PQPKB", full_value=pqpkb_pub, tooltip=_tt("x3dh_step_key_pqspk_pub")),
            ft.Text("↓", size=20),
            func_node("PQKEM.Encaps", "spqr_step_state_op", full_value="PQPKB -> encaps -> CT, SS"),
            ft.Text("↓", size=20),
            ft.Row(
                controls=[
                    var_node(label="CT", value=last_n_chars(derived.get("kem_ciphertext"), 8), width=200, full_value=derived.get("kem_ciphertext"), tooltip=tooltips.get("pqxdh_step_key_ct", "")),
                    var_node(label="SS (from PQKEM)", value=last_n_chars(pq_shared_secret), width=220, full_value=pq_shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step5 = ft.Column(
        controls=[
            ft.Text("4) Alice derives shared secret SK", weight="bold"),
            ft.Row(
                controls=[
                    func_node("DH1", "spqr_step_state_op", full_value="DH(IKA_priv, SPK_B)"),
                    func_node("DH2", "spqr_step_state_op", full_value="DH(EKA_priv, IK_B)"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    func_node("DH3", "spqr_step_state_op", full_value="DH(EKA_priv, SPK_B)"),
                    func_node("DH4", "spqr_step_state_op", full_value="DH(EKA_priv, OPK_B)"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            var_node("SS (from PQKEM)", full_value=pq_shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
            ft.Text("↓", size=20),
            func_node("KDF_SK", "spqr_step_state_op", full_value="KDF_SK(DH1 || DH2 || DH3 || DH4 || SS)"),
            ft.Text("↓", size=20),
            var_node("SK", full_value=shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step6 = ft.Column(
        controls=[
            ft.Text("5) Alice computes associated data and builds PQXDH header prefix", weight="bold"),
            ft.Row(
                controls=[
                    var_node(label="IK_A", value=last_n_chars(alice_identity_public), width=220, full_value=alice_identity_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    var_node(label="IK_B", value=last_n_chars(last_bundle.get("identity_dh_public")), width=220, full_value=last_bundle.get("identity_dh_public"), tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=20),
            func_node("CALC_AD", "spqr_step_state_op", full_value="IK_A, IK_B -> CALC_AD"),
            ft.Text("↓", size=20),
            var_node("AD", full_value=associated_data, tooltip=tooltips.get("pqxdh_step_key_ad", "")),
            ft.Divider(height=1),
            var_node(label="PQXDH header prefix", value=header_preview, width=580, full_value=real_pqxdh_header, tooltip=tooltips.get("pqxdh_step_node_verify_pq", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Alice requests Bob bundle", "control": step1},
        {"title": "Alice verifies EC signature", "control": step2},
        {"title": "Alice verifies PQ signature", "control": step3},
        {"title": "Alice encapsulates ephemeral KEM", "control": step4},
        {"title": "Alice derives shared secret SK", "control": step5},
        {"title": "Alice computes AD and header prefix", "control": step6},
    ]


def build_alice_pqxdh_phase2_steps(
    shared_secret: Any,
    rk_after_init: bytes | None,
    cks_after_init: bytes | None,
    alice_scka_state: Any,
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    ckr_value = None
    if alice_scka_state is not None and hasattr(alice_scka_state, "kdfchains"):
        try:
            chains = alice_scka_state.kdfchains.get(alice_scka_state.epoch)
            if chains and hasattr(chains, "receive"):
                ckr_value = chains.receive.CK
        except Exception:
            pass

    step7 = ft.Column(
        controls=[
            ft.Text("6) Initialize Alice SPQR session state", weight="bold"),
            var_node("SK", full_value=shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
            ft.Text("↓", size=20),
            func_node("RatchetInitAliceSCKA(SK)", "spqr_step_state_op", full_value="Initialize ratchet state"),
            ft.Text("↓", size=20),
            ft.Row(
                controls=[
                    var_node("RK", full_value=rk_after_init, tooltip=tooltips.get("spqr_step_rk", "")),
                    var_node("CKs", full_value=cks_after_init, tooltip=tooltips.get("spqr_step_send_ck", "")),
                    var_node("CKr", full_value=ckr_value, tooltip=tooltips.get("spqr_step_recv_ck", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Divider(height=1),
            var_node("Direction", full_value="A2B", tooltip=tooltips.get("spqr_step_direction", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Alice initializes SPQR state", "control": step7},
    ]


def show_alice_pqxdh_bootstrap_visualization_dialog(
    page: ft.Page,
    pqxdh_state_data: dict[str, Any] | None,
    rk_after_init: bytes | None,
    cks_after_init: bytes | None,
    alice_scka_state: Any = None,
    session_ad: bytes | None = None,
    on_close: Callable[[], None] | None = None,
    extra_steps: list[dict] | None = None,
    dialog_title: str | None = None,
) -> None:
    tooltips = {
        **get_tooltip_messages("pqxdh"),
        **get_tooltip_messages("spqr"),
    }

    derived = {}
    if isinstance(pqxdh_state_data, dict):
        derived = pqxdh_state_data.get("alice_derived") if isinstance(pqxdh_state_data.get("alice_derived"), dict) else {}
        if not derived:
            derived = pqxdh_state_data

    shared_secret = derived.get("shared_secret_hex") if isinstance(derived.get("shared_secret_hex"), str) else derived.get("shared_secret")

    steps = [
        *build_alice_pqxdh_phase1_steps(pqxdh_state_data, tooltips),
        *build_alice_pqxdh_phase2_steps(shared_secret, rk_after_init, cks_after_init, alice_scka_state, tooltips),
    ]
    if extra_steps:
        steps.extend(extra_steps)
    normalize_step_titles(steps)
    show_step_dialog(page, dialog_title or "SPQR Alice bootstrap", steps, on_close=on_close)


def build_bob_pqxdh_phase1_steps(
    pqxdh_header: dict[str, Any] | None,
    shared_secret: Any,
    session_ad: bytes | None,
    pq_shared_secret: bytes | None,
    bob_pq_prekey_public: str | None,
    bob_ik_public: str | None,
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    header_preview = pqxdh_header_preview(pqxdh_header)
    ik_a_public = pqxdh_header.get("ik_a_public") if isinstance(pqxdh_header, dict) else None
    kem_ciphertext = pqxdh_header.get("pq_ciphertext") if isinstance(pqxdh_header, dict) else None
    if kem_ciphertext is None and isinstance(pqxdh_header, dict):
        kem_ciphertext = pqxdh_header.get("kem_ciphertext")

    step1 = ft.Column(
        controls=[
            ft.Text("1) Extract PQXDH header", weight="bold"),
            var_node(
                "Received PQXDH header",
                value=header_preview,
                width=560,
                full_value=pqxdh_header,
                tooltip=tooltips.get("pqxdh_step_node_verify_pq", ""),
            ),
            ft.Text("↓", size=24),
            func_node("Extract components", full_value="Extract ik_a, ek_a, bob_spk, pq_id, CT"),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2 = ft.Column(
        controls=[
            ft.Text("2) Decapsulate KEM ciphertext", weight="bold"),
            ft.Row(
                controls=[
                    var_node("CT", full_value=kem_ciphertext, tooltip=tooltips.get("pqxdh_step_key_ct", "")),
                    var_node("PQPKB", full_value=bob_pq_prekey_public, tooltip=tooltips.get("x3dh_step_key_pqspk_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            func_node( "PQKEM.Decaps",full_value="CT + Bob_pq_privkey -> SS"),
            ft.Text("↓", size=24),
            var_node("SS (PQ shared secret)", full_value=pq_shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step3 = ft.Column(
        controls=[
            ft.Text("3) Calculate shared secret SK", weight="bold"),
            ft.Row(
                controls=[
                    var_node("DH1", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                    var_node("DH2", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    var_node("DH3", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                    var_node("DH4", tooltip=tooltips.get("x3dh_step_node_dh", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            var_node("SS (from PQKEM)", full_value=pq_shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
            ft.Text("↓", size=24),
            func_node("KDF_SK", full_value="KDF_SK(DH1 || DH2 || DH3 || DH4 || SS)"),
            ft.Text("↓", size=24),
            var_node("SK", full_value=shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step4 = ft.Column(
        controls=[
            ft.Text("4) Calculate associated data AD", weight="bold"),
            ft.Row(
                controls=[
                    var_node("IK_A", full_value=ik_a_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                    var_node("IK_B", full_value=bob_ik_public, tooltip=tooltips.get("x3dh_step_key_ik_pub", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Text("↓", size=24),
            func_node("CALC_AD", "spqr_step_state_op", full_value="IK_A, IK_B -> CALC_AD"),
            ft.Text("↓", size=24),
            var_node("AD", full_value=session_ad, tooltip=tooltips.get("pqxdh_step_key_ad", "")),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Extract PQXDH header", "control": step1},
        {"title": "Decapsulate KEM ciphertext", "control": step2},
        {"title": "Calculate shared secret SK", "control": step3},
        {"title": "Calculate associated data AD", "control": step4},
    ]


def build_bob_pqxdh_phase2_steps(
    shared_secret: Any,
    session_ad: bytes | None,
    bob_state: SpqrRatchetState | None,
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    rk_value = bob_state.RK if bob_state is not None else None
    chains = bob_state.kdfchains.get(bob_state.epoch) if bob_state is not None else None
    ckr_value = chains.receive.CK if chains is not None and chains.receive is not None else None
    cks_value = chains.send.CK if chains is not None and chains.send is not None else None
    rk_after_init = rk_value
    cks_after_init = cks_value

    step5 = ft.Column(
        controls=[
            ft.Text("5) Initialize Bob SCKA state", weight="bold"),
            var_node("SK", full_value=shared_secret, tooltip=tooltips.get("pqxdh_step_key_ss", "")),
            ft.Text("↓", size=20),
            func_node("RatchetInitBobSCKA",full_value="RatchetInitBobSCKA(SK, AD)"),
            ft.Text("↓", size=24),
            ft.Row(
                controls=[
                    var_node("RK", full_value=rk_after_init, tooltip=tooltips.get("spqr_step_rk", "")),
                    var_node("CKs", full_value=cks_after_init, tooltip=tooltips.get("spqr_step_send_ck", "")),
                    var_node("CKr", full_value=ckr_value, tooltip=tooltips.get("spqr_step_recv_ck", "")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                wrap=True,
            ),
            ft.Divider(height=1),
            var_node(
                "Direction",
                value="B2A",
                full_value="B2A (Bob receives, Alice sends)",
                tooltip=tooltips.get("spqr_step_direction", ""),
            ),
        ],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return [
        {"title": "Initialize Bob SCKA state", "control": step5},
    ]


def show_bob_pqxdh_bootstrap_visualization_dialog(
    page: ft.Page,
    pqxdh_header: dict[str, Any] | None,
    shared_secret: bytes | None,
    session_ad: bytes | None,
    bob_state: SpqrRatchetState | None,
    bob_ik_public: str | None = None,
    pq_shared_secret: bytes | None = None,
    bob_pq_prekey_public: str | None = None,
    on_close: Callable[[], None] | None = None,
    extra_steps: list[dict] | None = None,
    dialog_title: str | None = None,
) -> None:
    tooltips = {
        **get_tooltip_messages("pqxdh"),
        **get_tooltip_messages("spqr"),
    }

    steps = [
        *build_bob_pqxdh_phase1_steps(pqxdh_header, shared_secret, session_ad, pq_shared_secret, bob_pq_prekey_public, bob_ik_public, tooltips),
        *build_bob_pqxdh_phase2_steps(shared_secret, session_ad, bob_state, tooltips),
    ]
    if extra_steps:
        steps.extend(extra_steps)
    normalize_step_titles(steps)
    show_step_dialog(page, dialog_title or "SPQR Bob PQXDH bootstrap", steps, on_close=on_close)


def build_spqr_phase1_intro_steps(
    before: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    return [_build_intro_step(before, tooltips)]


def build_spqr_phase2_pqxdh_receive_steps(
    step_data: dict[str, Any],
    header: SpqrHeader | None,
    tooltips: dict[str, str],
    on_show_pqxdh_bootstrap: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    pqxdh_header = step_data.get("pqxdh_header") if isinstance(step_data.get("pqxdh_header"), dict) else None
    if not isinstance(pqxdh_header, dict):
        return []
    header_msg = header.msg if header is not None else None
    header_payload = {
        "msg": header_msg.to_dict() if header_msg is not None else None,
        "n": header.n if header is not None else None,
    }
    combined_header_full = {"header": header_payload, "pqxdh_header": pqxdh_header}
    combined_header_preview = f"{_header_preview(header)} | pqxdh: {pqxdh_header_preview(pqxdh_header)}"
    return [
        build_header_split_step(
            protocol_label="PQXDH",
            combined_preview=combined_header_preview,
            combined_full=combined_header_full,
            message_header_preview=_header_preview(header),
            message_header_full=header_payload,
            protocol_header_preview=pqxdh_header_preview(pqxdh_header),
            protocol_header_full=pqxdh_header,
            combined_tooltip=tooltips.get("pqxdh_step_node_verify_pq", ""),
            split_tooltip=tooltips.get("spqr_step_state_op", ""),
            message_header_tooltip=tooltips.get("spqr_step_header", ""),
            protocol_header_tooltip=tooltips.get("pqxdh_step_node_verify_pq", ""),
            combined_width=620,
            message_header_width=280,
        ),
        build_bootstrap_init_step(
            title="PQXDH initialization (party bootstrap)",
            was_bootstrapped=bool(step_data.get("was_pqxdh_bootstrapped", False)),
            protocol_header_label="PQXDH header",
            protocol_header_preview=pqxdh_header_preview(pqxdh_header),
            protocol_header_full=pqxdh_header,
            on_show_bootstrap=on_show_pqxdh_bootstrap,
            button_label="Show Bob SPQR PQXDH bootstrap",
            bootstrap_fn_label="PQXDH Bootstrap",
            bootstrap_fn_value="Initialize SPQR state from PQXDH",
            result_text="Bob was initialized during this receive",
            party_initialized_text="Bob already initialized",
            party_not_initialized_text="Bob not initialized yet",
            party_tooltip=tooltips.get("spqr_step_state_op", ""),
            protocol_header_tooltip=tooltips.get("pqxdh_step_node_verify_pq", ""),
            bootstrap_fn_tooltip=tooltips.get("spqr_step_state_op", ""),
            party_width=320,
            protocol_header_width=420,
            bootstrap_fn_width=360,
            bootstrap_fn_height=90,
        ),
    ]


def build_spqr_phase3_chain_steps(
    action: str,
    state_name: str,
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    if action == "send":
        return _build_send_steps(state_name, step_data, tooltips)
    return _build_receive_chain_steps(state_name, step_data, tooltips)


def build_spqr_phase4_key_steps(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    header: SpqrHeader | None,
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        _build_output_key_step(action, state_name, before, after, header, tooltips),
    ]
    rk_step = _build_rk_derivation_step(action, state_name, before, after, step_data)
    if rk_step is not None:
        steps.append(rk_step)
    return steps


def build_spqr_phase5_pipeline_steps(
    action: str,
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    if action == "send":
        return _build_send_message_pipeline_steps(step_data, tooltips)
    return _build_receive_message_pipeline_steps(step_data, tooltips)


def build_spqr_phase6_after_steps(
    action: str,
    state_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    after_state = str(after.get("state", after.get("node", state_name)))
    return [_build_after_step(action, after_state, before, after, tooltips)]


def build_spqr_send_phase1_steps(
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    return [_build_intro_step(before, tooltips)]


def build_spqr_send_phase2_steps(
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    state_name = str(before.get("state", before.get("node", "Unknown")))
    steps = _build_send_steps(state_name, step_data, tooltips)
    steps.append(_build_output_key_step("send", state_name, before, after, header, tooltips))
    rk_step = _build_rk_derivation_step("send", state_name, before, after, step_data)
    if rk_step is not None:
        steps.append(rk_step)
    steps.extend(_build_send_message_pipeline_phase2_steps(step_data, tooltips))
    return steps


def build_spqr_send_phase3_steps(
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    state_name = str(before.get("state", before.get("node", "Unknown")))
    after_state = str(after.get("state", after.get("node", state_name)))
    return [
        *_build_send_message_pipeline_phase3_steps(step_data, tooltips),
        _build_after_step("send", after_state, before, after, tooltips),
    ]


def build_spqr_receive_phase1_steps(
    step_data: dict[str, Any],
    tooltips: dict[str, str],
    on_show_pqxdh_bootstrap: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    return [
        _build_intro_step(before, tooltips),
        *build_spqr_phase2_pqxdh_receive_steps(step_data, header, tooltips, on_show_pqxdh_bootstrap),
    ]


def build_spqr_receive_phase2_steps(
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    state_name = str(before.get("state", before.get("node", "Unknown")))
    steps = _build_receive_chain_steps(state_name, step_data, tooltips)
    steps.append(_build_output_key_step("receive", state_name, before, after, header, tooltips))
    rk_step = _build_rk_derivation_step("receive", state_name, before, after, step_data)
    if rk_step is not None:
        steps.append(rk_step)
    steps.extend(_build_receive_message_pipeline_phase2_steps(step_data, tooltips))
    return steps


def build_spqr_receive_phase3_steps(
    step_data: dict[str, Any],
    tooltips: dict[str, str],
) -> list[dict[str, Any]]:
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    state_name = str(before.get("state", before.get("node", "Unknown")))
    after_state = str(after.get("state", after.get("node", state_name)))
    return [
        *_build_receive_message_pipeline_phase3_steps(step_data, tooltips),
        _build_after_step("receive", after_state, before, after, tooltips),
    ]


def show_spqr_step_visualization_dialog(
    page: ft.Page,
    step_data: dict[str, Any],
    on_close: Callable[[], None] | None = None,
    on_show_pqxdh_bootstrap: Callable[[], None] | None = None,
) -> None:
    tooltips = {**get_tooltip_messages("spqr"), **get_tooltip_messages("pqxdh")}
    action = str(step_data.get("action", "send")).strip().lower()
    before = step_data.get("before") if isinstance(step_data.get("before"), dict) else {}
    after = step_data.get("after") if isinstance(step_data.get("after"), dict) else {}
    header: SpqrHeader | None = step_data.get("header") if isinstance(step_data.get("header"), SpqrHeader) else None
    state_name = str(before.get("state", before.get("node", "Unknown")))

    steps: list[dict[str, Any]] = [
        *build_spqr_phase1_intro_steps(before, tooltips),
        *(build_spqr_phase2_pqxdh_receive_steps(step_data, header, tooltips, on_show_pqxdh_bootstrap) if action == "receive" else []),
        *build_spqr_phase3_chain_steps(action, state_name, step_data, tooltips),
        *build_spqr_phase4_key_steps(action, state_name, before, after, header, step_data, tooltips),
        *build_spqr_phase5_pipeline_steps(action, step_data, tooltips),
        *build_spqr_phase6_after_steps(action, state_name, before, after, tooltips),
    ]
    normalize_step_titles(steps)
    show_step_dialog(page, f"SPQR {action.capitalize()} visualization:", steps, on_close=on_close)
