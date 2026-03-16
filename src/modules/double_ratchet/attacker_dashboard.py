from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import DoubleRatchetState, Header
from modules.double_ratchet import external as ext


def _message_entries_for_attacker(
    session: DoubleRatchetState,
    pending_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for msg in session.message_log:
        if msg.header is None:
            continue
        entries.append(
            {
                "id": msg.seq_id,
                "state": "received",
                "sender": msg.sender,
                "receiver": msg.receiver,
                "header": msg.header,
                "cipher": msg.cipher,
                "plaintext": msg.plaintext,
                "message_key": msg.message_key,
            }
        )

    for pending in pending_messages:
        header = pending.get("header")
        if header is None:
            continue
        entries.append(
            {
                "id": pending.get("id", 0),
                "state": "pending",
                "sender": pending.get("sender", "?"),
                "receiver": pending.get("receiver", "?"),
                "header": header,
                "cipher": pending.get("cipher", b""),
                "plaintext": pending.get("plaintext", b""),
                "message_key": b"",
            }
        )

    return sorted(entries, key=lambda x: int(x.get("id", 0)))


def collect_attacker_secret_options(session: DoubleRatchetState) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []

    def add_option(key_id: str, label: str, kind: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, bytes) and not value:
            return
        if isinstance(value, str) and not value:
            return
        options.append(
            {
                "id": key_id,
                "label": label,
                "kind": kind,
                "value": value,
            }
        )

    for party in (session.initializer, session.responder):
        prefix = f"party:{party.name}"
        if party.DHs is not None and party.DHs.private:
            add_option(
                f"{prefix}:dhs_private",
                f"{party.name} DHs private",
                "dh_private",
                party.DHs.private,
            )
            options[-1].update(
                {
                    "party": party.name,
                    "public": party.DHs.public,
                    "remote_public": party.DHr,
                    "start_send_n": party.Ns,
                    "start_recv_n": party.Nr,
                    "secret_type": "party_secret",
                }
            )
        add_option(f"{prefix}:rk", f"{party.name} RK", "rk", party.RK)
        if options and options[-1]["id"] == f"{prefix}:rk":
            options[-1].update(
                {
                    "party": party.name,
                    "public": party.DHs.public if party.DHs is not None else "",
                    "remote_public": party.DHr,
                    "start_send_n": party.Ns,
                    "start_recv_n": party.Nr,
                    "secret_type": "party_secret",
                }
            )
        add_option(f"{prefix}:cks", f"{party.name} CKs", "ck", party.CKs)
        if options and options[-1]["id"] == f"{prefix}:cks":
            options[-1].update(
                {
                    "party": party.name,
                    "direction": "send",
                    "public": party.DHs.public if party.DHs is not None else "",
                    "start_n": party.Ns,
                    "secret_type": "party_secret",
                }
            )
        add_option(f"{prefix}:ckr", f"{party.name} CKr", "ck", party.CKr)
        if options and options[-1]["id"] == f"{prefix}:ckr":
            options[-1].update(
                {
                    "party": party.name,
                    "direction": "recv",
                    "remote_public": party.DHr,
                    "start_n": party.Nr,
                    "secret_type": "party_secret",
                }
            )

        for (dh_key, n_idx), mk in party.MKSKIPPED.items():
            add_option(
                f"{prefix}:mkskipped:{dh_key}:{n_idx}",
                f"{party.name} MKSKIPPED(dh={dh_key[-8:]}, n={n_idx + 1})",
                "mk",
                mk,
            )
            options[-1].update(
                {
                    "party": party.name,
                    "dh": dh_key,
                    "n": n_idx,
                    "secret_type": "skipped_mk",
                }
            )

    for message in session.message_log:
        add_option(
            f"msg:{message.seq_id}:mk",
            f"MK for message #{message.seq_id}",
            "mk",
            message.message_key,
        )
        options[-1].update(
            {
                "seq_id": message.seq_id,
                "secret_type": "message_mk",
            }
        )

    return options


def _decode_plaintext(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return ""


def _try_decrypt_with_message_key(entry: dict[str, Any], mk: bytes) -> str:
    header = entry.get("header")
    cipher = entry.get("cipher")
    if not isinstance(header, Header) or not isinstance(cipher, bytes):
        return ""
    if not isinstance(mk, bytes) or not mk:
        return ""

    try:
        plaintext = ext.DECRYPT(mk, cipher, ext.CONCAT(b"", header))
    except ValueError:
        return ""
    return _decode_plaintext(plaintext)


def decrypt_with_attacker_selection(
    session: DoubleRatchetState,
    pending_messages: list[dict[str, Any]],
    compromised_secrets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    messages = _message_entries_for_attacker(session, pending_messages)
    results: list[dict[str, Any]] = [
        {
            "id": entry["id"],
            "state": entry["state"],
            "sender": entry["sender"],
            "receiver": entry["receiver"],
            "decryptable": False,
            "plaintext": "",
            "source": "",
            "header": entry["header"],
        }
        for entry in messages
    ]

    result_lookup = {
        (result["id"], result["state"]): result
        for result in results
    }

    def mark_decryptable(entry: dict[str, Any], plaintext: str, source: str) -> None:
        if not plaintext:
            return
        result = result_lookup.get((entry["id"], entry["state"]))
        if result is None or result["decryptable"]:
            return
        result["decryptable"] = True
        result["plaintext"] = plaintext
        result["source"] = source

    for secret in compromised_secrets.values():
        if secret.get("kind") != "mk":
            continue
        for entry in messages:
            plaintext = _try_decrypt_with_message_key(entry, secret.get("value"))
            if plaintext:
                mark_decryptable(entry, plaintext, str(secret.get("label", "MK")))

    return sorted(results, key=lambda item: int(item.get("id", 0)), reverse=True)


def get_attacker_analysis(
    session: DoubleRatchetState,
    pending_messages: list[dict[str, Any]],
    compromised_secrets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return decrypt_with_attacker_selection(session, pending_messages, compromised_secrets)


def build_attacker_dashboard(
    page: ft.Page,
    session: DoubleRatchetState,
    pending_messages: list[dict[str, Any]],
    compromised_secrets: dict[str, dict[str, Any]],
    set_compromised_secrets: Callable[[dict[str, dict[str, Any]]], None],
    refresh_callback: Callable[[], None],
) -> ft.Control:
    del pending_messages

    options = collect_attacker_secret_options(session)
    option_ids = {item["id"] for item in options}
    active_selected = {key_id for key_id in compromised_secrets if key_id in option_ids}
    options_by_id = {item["id"]: item for item in options}

    party_names = {session.initializer.name, session.responder.name}

    def _option_owner(label: str) -> str:
        first_token = label.split(" ", 1)[0] if label else "Other"
        return first_token if first_token in party_names else "Other"

    def _option_grid_label(item: dict[str, Any]) -> str:
        label = item.get("label", "")
        owner = _option_owner(label)
        if owner != "Other" and label.startswith(f"{owner} "):
            return label[len(owner) + 1:]
        return label

    def update_selection(key_id: str, checked: bool) -> None:
        updated = dict(compromised_secrets)
        if checked:
            option = options_by_id.get(key_id)
            if option is None:
                return
            updated[key_id] = dict(option)
        else:
            updated.pop(key_id, None)
        set_compromised_secrets(updated)
        refresh_callback()
        page.update()

    def select_all(e) -> None:
        set_compromised_secrets({item["id"]: dict(item) for item in options})
        refresh_callback()
        page.update()

    def clear_all(e) -> None:
        set_compromised_secrets({})
        refresh_callback()
        page.update()

    key_selector_controls: list[ft.Control] = [
        ft.Row(
            controls=[
                ft.Text("Compromised secrets", weight="bold"),
                ft.Row(
                    controls=[
                        ft.TextButton("Select all", on_click=select_all),
                        ft.TextButton("Clear", on_click=clear_all),
                    ],
                    spacing=6,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    ]

    if not options:
        key_selector_controls.append(ft.Text("No selectable secrets are available yet."))
    else:
        grouped: dict[str, list[dict[str, Any]]] = {session.initializer.name: [], session.responder.name: [], "Other": []}
        for item in options:
            grouped.setdefault(_option_owner(item["label"]), []).append(item)

        column_count = 4

        for owner in (session.initializer.name, session.responder.name, "Other"):
            owner_items = grouped.get(owner, [])
            if not owner_items:
                continue

            key_selector_controls.append(ft.Divider(height=8))
            key_selector_controls.append(ft.Text(owner, weight="bold", size=12))

            for start in range(0, len(owner_items), column_count):
                chunk = owner_items[start: start + column_count]
                cells: list[ft.Control] = []

                for item in chunk:
                    cells.append(
                        ft.Container(
                            content=ft.Checkbox(
                                label=_option_grid_label(item),
                                value=item["id"] in active_selected,
                                on_change=lambda e, kid=item["id"]: update_selection(kid, bool(e.control.value)),
                            ),
                            width=220,
                            padding=ft.Padding.only(right=6),
                        )
                    )

                while len(cells) < column_count:
                    cells.append(ft.Container(width=220))

                key_selector_controls.append(
                    ft.Row(
                        controls=cells,
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                )

    return ft.Container(
        content=ft.Column(
            controls=key_selector_controls,
            scroll=ft.ScrollMode.AUTO,
            spacing=4,
        ),
        expand=True,
        padding=10,
        border=ft.Border.all(color=ft.Colors.OUTLINE),
        border_radius=8,
        height=330,
    )
