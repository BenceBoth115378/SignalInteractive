from __future__ import annotations

from typing import Any, Callable

import flet as ft

from components.data_classes import DHKeyPair, DoubleRatchetState, Header
from modules.base_view import last_n_chars
from modules.double_ratchet import external as ext
from modules.double_ratchet.key_history import get_key_display_label, get_key_tooltip_text


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
        prefix = f"kh:{party.name}"

        for event in party.key_history.rk_events:
            add_option(
                f"{prefix}:rk:{event.key_number}",
                f"{party.name} {get_key_display_label('RK', event.key_number)}",
                "rk",
                event.key_value,
            )
            options[-1].update(
                {
                    "party": event.party,
                    "remote_public": event.remote_public,
                    "start_send_n": event.start_send_n,
                    "start_recv_n": event.start_recv_n,
                    "secret_type": "history_key",
                    "context": get_key_tooltip_text(event),
                }
            )

        for event in party.key_history.cks_events:
            add_option(
                f"{prefix}:cks:{event.key_number}",
                f"{party.name} {get_key_display_label('CKs', event.key_number)}",
                "cks",
                event.key_value,
            )
            options[-1].update(
                {
                    "party": event.party,
                    "direction": "send",
                    "public": event.public_value,
                    "remote_public": "",
                    "start_n": event.start_n,
                    "secret_type": "history_key",
                    "context": get_key_tooltip_text(event),
                }
            )

        for event in party.key_history.ckr_events:
            add_option(
                f"{prefix}:ckr:{event.key_number}",
                f"{party.name} {get_key_display_label('CKr', event.key_number)}",
                "ckr",
                event.key_value,
            )
            options[-1].update(
                {
                    "party": event.party,
                    "direction": "recv",
                    "public": "",
                    "remote_public": event.remote_public,
                    "start_n": event.start_n,
                    "secret_type": "history_key",
                    "context": get_key_tooltip_text(event),
                }
            )

        for event in party.key_history.dh_events:
            add_option(
                f"{prefix}:dh:{event.key_number}",
                f"{party.name} {get_key_display_label('DH', event.key_number)}",
                "dh_private",
                event.key_value,
            )
            options[-1].update(
                {
                    "party": event.party,
                    "public": event.public_value,
                    "remote_public": event.remote_public,
                    "start_send_n": event.start_send_n,
                    "start_recv_n": event.start_recv_n,
                    "secret_type": "history_key",
                    "context": get_key_tooltip_text(event),
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


def _format_source_value(value: Any) -> str:
    tail_len = 8
    if isinstance(value, bytes):
        return last_n_chars(value.hex(), tail_len)
    return last_n_chars(str(value), tail_len)


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


def _derive_chain_message_key(chain_key: bytes, step_count: int) -> bytes | None:
    if not isinstance(chain_key, bytes) or not chain_key or step_count < 1:
        return None

    current_ck = chain_key
    mk = None
    for _ in range(step_count):
        current_ck, mk = ext.KDF_CK(current_ck)
    return mk


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

    rk_by_party: dict[str, list[dict[str, Any]]] = {}
    for candidate_secret in compromised_secrets.values():
        if candidate_secret.get("kind") != "rk":
            continue
        party_name = candidate_secret.get("party")
        if not isinstance(party_name, str):
            continue
        rk_by_party.setdefault(party_name, []).append(candidate_secret)

    dh_by_party = {
        party_name: [
            secret
            for secret in compromised_secrets.values()
            if secret.get("kind") == "dh_private" and secret.get("party") == party_name
        ]
        for party_name in rk_by_party.keys()
    }

    chain_cache: dict[tuple[str, int], bytes | None] = {}
    dh_chain_cache: dict[str, bytes | None] = {}

    def _process_mk_secret(secret: dict[str, Any]) -> None:
        for entry in messages:
            plaintext = _try_decrypt_with_message_key(entry, secret.get("value"))
            if plaintext:
                mark_decryptable(entry, plaintext, str(secret.get("label", "MK")))

    def _process_ck_secret(secret: dict[str, Any], party: str) -> None:
        kind = secret.get("kind")
        direction = secret.get("direction")
        if direction not in {"send", "recv"}:
            if kind == "cks":
                direction = "send"
            elif kind == "ckr":
                direction = "recv"
        public_key = secret.get("public") if direction == "send" else secret.get("remote_public")
        start_n = secret.get("start_n")
        if direction not in {"send", "recv"}:
            return
        if not isinstance(public_key, str) or not public_key:
            return
        if not isinstance(start_n, int):
            return

        for entry in messages:
            header = entry.get("header")
            if not isinstance(header, Header):
                continue
            if direction == "send" and entry.get("sender") != party:
                continue
            if direction == "recv" and entry.get("receiver") != party:
                continue
            if header.dh != public_key or header.n < start_n:
                continue

            step_count = header.n - start_n + 1
            cache_key = (str(secret.get("id", "")), step_count)
            if cache_key not in chain_cache:
                chain_cache[cache_key] = _derive_chain_message_key(secret.get("value"), step_count)
            mk = chain_cache[cache_key]
            if mk is None:
                continue
            plaintext = _try_decrypt_with_message_key(entry, mk)
            if plaintext:
                mark_decryptable(entry, plaintext, f"{secret.get('label', 'CK')} -> KDF_CK step {step_count}")
                continue

    def _build_dh_sequence(party: str) -> list[dict[str, Any]]:
        sequence = [
            secret
            for secret in dh_by_party.get(party, [])
            if isinstance(secret.get("public"), str)
            if bool(secret.get("public"))
            if isinstance(secret.get("start_send_n"), int)
            if isinstance(secret.get("start_recv_n"), int)
            if isinstance(secret.get("value"), str)
            if bool(secret.get("value"))
        ]
        sequence.sort(
            key=lambda s: (
                int(s.get("start_send_n", 0)),
                int(s.get("start_recv_n", 0)),
                str(s.get("id", "")),
            )
        )
        return sequence

    def _derive_dh_contexts_for_party(
        party: str,
        rk_candidates: list[dict[str, Any]],
        dh_sequence: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        recv_contexts: list[dict[str, Any]] = []
        send_contexts: list[dict[str, Any]] = []

        for rk_secret in rk_candidates:
            rk_value = rk_secret.get("value")
            if not isinstance(rk_value, bytes) or not rk_value:
                continue

            current_rk = rk_value
            rk_id = str(rk_secret.get("id", ""))

            for idx, dh_secret in enumerate(dh_sequence):
                local_priv = str(dh_secret.get("value", ""))
                local_pub = str(dh_secret.get("public", ""))
                peer_pub = str(dh_secret.get("remote_public", ""))
                # DH-derived receive chains start at header.n == 0 for the corresponding peer DH key.
                # `start_recv_n` in state history can be post-receive and off by one for derivation steps.
                recv_start_n = 0
                dh_id = str(dh_secret.get("id", ""))

                recv_contexts.append(
                    {
                        "party": party,
                        "direction": "recv",
                        "rk_id": rk_id,
                        "rk_value": current_rk,
                        "dh_id": dh_id,
                        "dh_private": local_priv,
                        "local_public": local_pub,
                        "chain": b"",
                        "start_n": recv_start_n,
                    }
                )

                if idx + 1 >= len(dh_sequence):
                    continue

                next_dh = dh_sequence[idx + 1]
                next_priv = str(next_dh.get("value", ""))
                next_pub = str(next_dh.get("public", ""))
                send_start_n = int(next_dh.get("start_send_n", 0))
                next_dh_id = str(next_dh.get("id", ""))

                send_chain: bytes = b""
                rk_after_send: bytes | None = None
                send_chain_cache_key = (
                    f"iter:{party}:rk:{rk_id}:from:{dh_id}:to:{next_dh_id}:send_chain:{peer_pub}"
                )
                if peer_pub:
                    if send_chain_cache_key not in dh_chain_cache:
                        try:
                            local_pair = DHKeyPair(private=local_priv, public=local_pub)
                            dh_out_recv = ext.DH(local_pair, peer_pub)
                            rk_after_recv, _ = ext.KDF_RK(current_rk, dh_out_recv)

                            next_pair = DHKeyPair(private=next_priv, public=next_pub)
                            dh_out_send = ext.DH(next_pair, peer_pub)
                            rk_after_send, send_chain = ext.KDF_RK(rk_after_recv, dh_out_send)
                            dh_chain_cache[send_chain_cache_key] = send_chain
                            dh_chain_cache[f"{send_chain_cache_key}:rk_after"] = rk_after_send
                        except ValueError:
                            dh_chain_cache[send_chain_cache_key] = None
                            dh_chain_cache[f"{send_chain_cache_key}:rk_after"] = None

                    cached_chain = dh_chain_cache.get(send_chain_cache_key)
                    cached_rk_after = dh_chain_cache.get(f"{send_chain_cache_key}:rk_after")
                    if isinstance(cached_chain, bytes):
                        send_chain = cached_chain
                    if isinstance(cached_rk_after, bytes):
                        rk_after_send = cached_rk_after

                send_contexts.append(
                    {
                        "party": party,
                        "direction": "send",
                        "rk_id": rk_id,
                        "rk_value": current_rk,
                        "dh_id": next_dh_id,
                        "prev_dh_id": dh_id,
                        "public": next_pub,
                        "peer_public": peer_pub,
                        "prev_dh_private": local_priv,
                        "prev_dh_public": local_pub,
                        "next_dh_private": next_priv,
                        "next_dh_public": next_pub,
                        "chain": send_chain,
                        "start_n": send_start_n,
                    }
                )
                if isinstance(rk_after_send, bytes):
                    current_rk = rk_after_send

        return recv_contexts, send_contexts

    def _iter_matching_dh_contexts(
        contexts: list[dict[str, Any]],
        direction: str,
        header: Header,
    ) -> list[dict[str, Any]]:
        if direction == "recv":
            matching = [
                ctx
                for ctx in contexts
                if isinstance(ctx.get("start_n"), int)
                if header.n >= int(ctx.get("start_n"))
            ]
            matching.sort(key=lambda ctx: int(ctx.get("start_n", -1)), reverse=True)
            return matching

        key_name = "public"
        matching = [
            ctx
            for ctx in contexts
            if ctx.get(key_name) == header.dh
            if isinstance(ctx.get("start_n"), int)
            if header.n >= int(ctx.get("start_n"))
        ]
        matching.sort(key=lambda ctx: int(ctx.get("start_n", -1)), reverse=True)
        return matching

    def _try_decrypt_with_dh_context(
        entry: dict[str, Any],
        ctx: dict[str, Any],
        direction: str,
        peer_public_override: str | None = None,
    ) -> bool:
        header = entry.get("header")
        if not isinstance(header, Header):
            return False

        start_n = ctx.get("start_n")
        if not isinstance(start_n, int):
            return False
        step_count = header.n - start_n + 1
        if step_count < 1:
            return False

        base_cache_key = f"iter:{ctx.get('party')}:rk:{ctx.get('rk_id')}:dh:{ctx.get('dh_id')}:{direction}:{header.dh}"
        cache_key = (base_cache_key, step_count)
        send_chain_cache_key = ""

        def _latest_rk_after_for_send_context() -> bytes | None:
            prefix = (
                f"iter:{ctx.get('party')}:rk:{ctx.get('rk_id')}:dh:{ctx.get('dh_id')}:"
                "send_chain_for_peer:"
            )
            for key in reversed(list(dh_chain_cache.keys())):
                if not isinstance(key, str):
                    continue
                if not key.startswith(prefix) or not key.endswith(":rk_after"):
                    continue
                value = dh_chain_cache.get(key)
                if isinstance(value, bytes) and value:
                    return value
            return None

        def _latest_rk_after_for_recv_context(prev_dh_id: str, peer_public: str) -> bytes | None:
            prefix = (
                f"iter:{ctx.get('party')}:rk:{ctx.get('rk_id')}:dh:{prev_dh_id}:"
            )
            suffix = f":recv_chain_for_header:{peer_public}:rk_after"
            for key in reversed(list(dh_chain_cache.keys())):
                if not isinstance(key, str):
                    continue
                if not key.startswith(prefix) or not key.endswith(suffix):
                    continue
                value = dh_chain_cache.get(key)
                if isinstance(value, bytes) and value:
                    return value
            return None

        if direction == "recv":
            dh_private = str(ctx.get("dh_private", ""))
            local_public = str(ctx.get("local_public", ""))
            rk_value = _latest_rk_after_for_send_context()
            if not isinstance(rk_value, bytes) or not rk_value:
                rk_value = ctx.get("rk_value")

            rk_tag = ""
            if isinstance(rk_value, bytes) and rk_value:
                rk_tag = _format_source_value(rk_value)

            recv_chain_cache_key = (
                f"iter:{ctx.get('party')}:rk:{ctx.get('rk_id')}:dh:{ctx.get('dh_id')}:"
                f"rk_tag:{rk_tag}:recv_chain_for_header:{header.dh}"
            )
            cache_key = (f"{base_cache_key}:rk_tag:{rk_tag}", step_count)

            if recv_chain_cache_key not in dh_chain_cache:
                if not dh_private or not local_public or not isinstance(rk_value, bytes) or not rk_value:
                    dh_chain_cache[recv_chain_cache_key] = None
                else:
                    try:
                        local_pair = DHKeyPair(private=dh_private, public=local_public)
                        dh_out_recv = ext.DH(local_pair, header.dh)
                        rk_after_recv, recv_chain_for_header = ext.KDF_RK(rk_value, dh_out_recv)
                        dh_chain_cache[recv_chain_cache_key] = recv_chain_for_header
                        dh_chain_cache[f"{recv_chain_cache_key}:rk_after"] = rk_after_recv
                    except ValueError:
                        dh_chain_cache[recv_chain_cache_key] = None
                        dh_chain_cache[f"{recv_chain_cache_key}:rk_after"] = None

            recv_chain_for_header = dh_chain_cache[recv_chain_cache_key]
            if not isinstance(recv_chain_for_header, bytes):
                return False
            if cache_key not in chain_cache:
                chain_cache[cache_key] = _derive_chain_message_key(recv_chain_for_header, step_count)
        else:
            send_chain = ctx.get("chain")
            peer_public_for_send = peer_public_override if isinstance(peer_public_override, str) and peer_public_override else str(ctx.get("peer_public", ""))
            send_chain_cache_key = (
                f"iter:{ctx.get('party')}:rk:{ctx.get('rk_id')}:dh:{ctx.get('dh_id')}:"
                f"send_chain_for_peer:{peer_public_for_send}"
            )
            cache_key = (f"{base_cache_key}:peer:{peer_public_for_send}", step_count)

            if peer_public_for_send and send_chain_cache_key not in dh_chain_cache:
                prev_dh_private = str(ctx.get("prev_dh_private", ""))
                prev_dh_public = str(ctx.get("prev_dh_public", ""))
                next_dh_private = str(ctx.get("next_dh_private", ""))
                next_dh_public = str(ctx.get("next_dh_public", ""))
                prev_dh_id = str(ctx.get("prev_dh_id", ""))
                rk_value = ctx.get("rk_value")
                rk_after_recv_seed = _latest_rk_after_for_recv_context(prev_dh_id, peer_public_for_send)

                if not all([prev_dh_private, prev_dh_public, next_dh_private, next_dh_public]) or not isinstance(rk_value, bytes) or not rk_value:
                    dh_chain_cache[send_chain_cache_key] = None
                else:
                    try:
                        prev_pair = DHKeyPair(private=prev_dh_private, public=prev_dh_public)
                        next_pair = DHKeyPair(private=next_dh_private, public=next_dh_public)

                        rk_after_recv = rk_after_recv_seed
                        if not isinstance(rk_after_recv, bytes) or not rk_after_recv:
                            dh_out_recv = ext.DH(prev_pair, peer_public_for_send)
                            rk_after_recv, _ = ext.KDF_RK(rk_value, dh_out_recv)

                        dh_out_send = ext.DH(next_pair, peer_public_for_send)
                        rk_after_send, send_chain_for_peer = ext.KDF_RK(rk_after_recv, dh_out_send)
                        dh_chain_cache[send_chain_cache_key] = send_chain_for_peer
                        dh_chain_cache[f"{send_chain_cache_key}:rk_after"] = rk_after_send
                    except ValueError:
                        dh_chain_cache[send_chain_cache_key] = None
                        dh_chain_cache[f"{send_chain_cache_key}:rk_after"] = None

            if peer_public_for_send and send_chain_cache_key in dh_chain_cache:
                cached_send_chain = dh_chain_cache[send_chain_cache_key]
                if isinstance(cached_send_chain, bytes):
                    send_chain = cached_send_chain

            if cache_key not in chain_cache:
                chain_cache[cache_key] = _derive_chain_message_key(send_chain, step_count)
        mk = chain_cache[cache_key]
        if not isinstance(mk, bytes):
            return False

        plaintext = _try_decrypt_with_message_key(entry, mk)
        if not plaintext:
            return False

        chain_source = ctx.get("chain")
        if direction == "recv":
            rk_value = _latest_rk_after_for_send_context()
            if not isinstance(rk_value, bytes) or not rk_value:
                rk_value = ctx.get("rk_value")
            rk_tag = _format_source_value(rk_value) if isinstance(rk_value, bytes) and rk_value else ""
            recv_chain_cache_key = (
                f"iter:{ctx.get('party')}:rk:{ctx.get('rk_id')}:dh:{ctx.get('dh_id')}:"
                f"rk_tag:{rk_tag}:recv_chain_for_header:{header.dh}"
            )
            chain_source = dh_chain_cache.get(recv_chain_cache_key)
        elif send_chain_cache_key:
            chain_source = dh_chain_cache.get(send_chain_cache_key, chain_source)
        chain_value = _format_source_value(chain_source)
        rk_value = _format_source_value(ctx.get("rk_value"))
        peer_value = _format_source_value(header.dh)
        chain_label = "CKs" if direction == "send" else "CKr"
        source = (
            f"iterative DH compromise: RK({rk_value}) -> {chain_label} on dh_pub={peer_value} "
            f"(chain={chain_value}) + step({step_count})"
        )
        mark_decryptable(entry, plaintext, source)
        return True

    def _process_dh_secrets_iterative() -> None:
        for party, rk_candidates in rk_by_party.items():
            if not rk_candidates:
                continue

            dh_sequence = _build_dh_sequence(party)
            if not dh_sequence:
                continue

            recv_contexts, send_contexts = _derive_dh_contexts_for_party(party, rk_candidates, dh_sequence)
            if not recv_contexts and not send_contexts:
                continue

            observed_peer_headers: list[str] = []

            for entry in messages:
                result = result_lookup.get((entry["id"], entry["state"]))
                if result is None or result.get("decryptable"):
                    continue

                header = entry.get("header")
                if not isinstance(header, Header):
                    continue

                if entry.get("receiver") == party:
                    if header.dh and header.dh not in observed_peer_headers:
                        observed_peer_headers.append(header.dh)

                if entry.get("receiver") == party:
                    recv_matches = _iter_matching_dh_contexts(recv_contexts, direction="recv", header=header)
                    for ctx in recv_matches:
                        if _try_decrypt_with_dh_context(entry, ctx, "recv"):
                            break

                result = result_lookup.get((entry["id"], entry["state"]))
                if result is None or result.get("decryptable"):
                    continue

                if entry.get("sender") == party:
                    send_matches = _iter_matching_dh_contexts(send_contexts, direction="send", header=header)
                    for ctx in send_matches:
                        # Prefer peer DH publics seen in actual receive headers over stale compromise snapshots.
                        peer_candidates = list(reversed(observed_peer_headers))
                        fallback_peer = str(ctx.get("peer_public", ""))
                        if fallback_peer and fallback_peer not in peer_candidates:
                            peer_candidates.append(fallback_peer)

                        decrypted = False
                        for peer_public in peer_candidates:
                            if _try_decrypt_with_dh_context(entry, ctx, "send", peer_public_override=peer_public):
                                decrypted = True
                                break
                        if decrypted:
                            break

    for secret in compromised_secrets.values():
        kind = secret.get("kind")
        party = secret.get("party")

        if kind == "mk":
            _process_mk_secret(secret)
            continue

        if kind in {"ck", "cks", "ckr"}:
            if isinstance(party, str):
                _process_ck_secret(secret, party)
            continue

    _process_dh_secrets_iterative()

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
    options = collect_attacker_secret_options(session)
    option_ids = {item["id"] for item in options}
    active_selected = {key_id for key_id in compromised_secrets if key_id in option_ids}
    options_by_id = {item["id"]: item for item in options}

    party_names = {session.initializer.name, session.responder.name}
    opposite_party_by_name = {
        session.initializer.name: session.responder.name,
        session.responder.name: session.initializer.name,
    }
    messages_by_id = {msg.seq_id: msg for msg in session.message_log}

    def _option_owner(label: str) -> str:
        first_token = label.split(" ", 1)[0] if label else "Other"
        return first_token if first_token in party_names else "Other"

    def _extract_key_number(item: dict[str, Any]) -> int:
        key_id = str(item.get("id", ""))
        try:
            return int(key_id.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            return 0

    def _layout_label(item: dict[str, Any]) -> str:
        kind = item.get("kind")
        number = _extract_key_number(item)
        if kind == "dh_private":
            return f"DH#{number}"
        if kind == "rk":
            return f"RK#{number}"
        if kind == "cks":
            return f"CKs#{number}"
        if kind == "ckr":
            return f"CKr#{number}"
        if kind == "ck":
            direction = item.get("direction")
            if direction == "send":
                return f"CKs#{number}"
            if direction == "recv":
                return f"CKr#{number}"
            return f"CK#{number}"
        return str(item.get("label", ""))

    def _key_sort(item: dict[str, Any]) -> tuple[int, int]:
        kind_rank = {
            "dh_private": 0,
            "rk": 1,
            "cks": 2,
            "ckr": 3,
            "ck": 4,
            "mk": 3,
        }.get(str(item.get("kind", "")), 99)
        return (kind_rank, _extract_key_number(item))

    def _is_send_ck(item: dict[str, Any]) -> bool:
        kind = item.get("kind")
        return kind == "cks" or (kind == "ck" and item.get("direction") == "send")

    def _is_recv_ck(item: dict[str, Any]) -> bool:
        kind = item.get("kind")
        return kind == "ckr" or (kind == "ck" and item.get("direction") == "recv")

    def _find_matching_ids(
        *,
        party: str,
        kind_filter: Callable[[dict[str, Any]], bool],
        public_key: str,
        start_n: int,
        allow_earlier_start: bool = False,
    ) -> set[str]:
        matches: set[str] = set()
        for candidate in options:
            if candidate.get("party") != party:
                continue
            if not kind_filter(candidate):
                continue
            candidate_public = candidate.get("public") if _is_send_ck(candidate) else candidate.get("remote_public")
            if candidate_public != public_key:
                continue
            candidate_start_n = candidate.get("start_n")
            if not isinstance(candidate_start_n, int):
                continue
            if allow_earlier_start:
                if candidate_start_n > start_n:
                    continue
            elif candidate_start_n != start_n:
                continue
            matches.add(str(candidate.get("id", "")))
        return {cid for cid in matches if cid}

    def _find_best_matching_id(
        *,
        party: str,
        kind_filter: Callable[[dict[str, Any]], bool],
        public_key: str,
        step_n: int,
    ) -> str | None:
        best_id: str | None = None
        best_start_n = -1
        for candidate in options:
            if candidate.get("party") != party:
                continue
            if not kind_filter(candidate):
                continue
            candidate_public = candidate.get("public") if _is_send_ck(candidate) else candidate.get("remote_public")
            if candidate_public != public_key:
                continue
            candidate_start_n = candidate.get("start_n")
            if not isinstance(candidate_start_n, int):
                continue
            if candidate_start_n > step_n:
                continue
            if candidate_start_n >= best_start_n:
                best_start_n = candidate_start_n
                best_id = str(candidate.get("id", ""))
        return best_id if best_id else None

    def _infer_ck_ids_from_decryptable_messages(known_ids: set[str]) -> set[str]:
        compromised_subset = {
            key_id: dict(options_by_id[key_id])
            for key_id in known_ids
            if key_id in options_by_id
        }
        analysis = decrypt_with_attacker_selection(session, pending_messages, compromised_subset)

        implied_ck_ids: set[str] = set()
        for result in analysis:
            if not result.get("decryptable"):
                continue

            header = result.get("header")
            if not isinstance(header, Header):
                continue

            receiver = result.get("receiver")
            if not isinstance(receiver, str):
                continue

            # Decryption proves receiver-side chain knowledge for this message context.
            best_receiver_ck = _find_best_matching_id(
                party=receiver,
                kind_filter=_is_recv_ck,
                public_key=header.dh,
                step_n=header.n,
            )
            if best_receiver_ck is not None:
                implied_ck_ids.add(best_receiver_ck)

        return implied_ck_ids

    def _compute_implied_known_ids(selected_ids: set[str]) -> set[str]:
        known_ids = {key_id for key_id in selected_ids if key_id in options_by_id}

        changed = True
        while changed:
            changed = False
            snapshot_ids = list(known_ids)
            rk_parties = {
                str(options_by_id[key_id].get("party", ""))
                for key_id in snapshot_ids
                if options_by_id[key_id].get("kind") == "rk"
            }

            for key_id in snapshot_ids:
                secret = options_by_id.get(key_id)
                if secret is None:
                    continue
                party = str(secret.get("party", ""))
                if not party:
                    continue

                if _is_send_ck(secret):
                    counterparty = opposite_party_by_name.get(party, "")
                    public_key = str(secret.get("public", ""))
                    start_n = secret.get("start_n")
                    if counterparty and public_key and isinstance(start_n, int):
                        matches = _find_matching_ids(
                            party=counterparty,
                            kind_filter=_is_recv_ck,
                            public_key=public_key,
                            start_n=start_n,
                        )
                        new_ids = matches - known_ids
                        if new_ids:
                            known_ids.update(new_ids)
                            changed = True

                if secret.get("kind") == "dh_private" and party in rk_parties:
                    remote_public = str(secret.get("remote_public", ""))
                    start_recv_n = secret.get("start_recv_n")
                    if remote_public and isinstance(start_recv_n, int):
                        matches = _find_matching_ids(
                            party=party,
                            kind_filter=_is_recv_ck,
                            public_key=remote_public,
                            start_n=start_recv_n,
                        )
                        new_ids = matches - known_ids
                        if new_ids:
                            known_ids.update(new_ids)
                            changed = True

            implied_from_decryption = _infer_ck_ids_from_decryptable_messages(known_ids)
            new_ids = implied_from_decryption - known_ids
            if new_ids:
                known_ids.update(new_ids)
                changed = True

            # Any known CK implies all message keys reachable on that chain.
            for candidate in options:
                if candidate.get("kind") != "mk":
                    continue
                candidate_id = str(candidate.get("id", ""))
                if not candidate_id or candidate_id in known_ids:
                    continue

                seq_id = candidate.get("seq_id")
                if not isinstance(seq_id, int):
                    continue
                message = messages_by_id.get(seq_id)
                if message is None or message.header is None:
                    continue

                for known_id in snapshot_ids:
                    secret = options_by_id.get(known_id)
                    if secret is None:
                        continue
                    if secret.get("kind") not in {"ck", "cks", "ckr"}:
                        continue

                    direction = secret.get("direction")
                    if direction not in {"send", "recv"}:
                        if secret.get("kind") == "cks":
                            direction = "send"
                        elif secret.get("kind") == "ckr":
                            direction = "recv"
                    if direction not in {"send", "recv"}:
                        continue

                    party = str(secret.get("party", ""))
                    start_n = secret.get("start_n")
                    if not party or not isinstance(start_n, int):
                        continue

                    chain_public = str(secret.get("public", "")) if direction == "send" else str(secret.get("remote_public", ""))
                    if not chain_public:
                        continue

                    if direction == "send" and message.sender != party:
                        continue
                    if direction == "recv" and message.receiver != party:
                        continue
                    if message.header.dh != chain_public:
                        continue
                    if message.header.n < start_n:
                        continue

                    known_ids.add(candidate_id)
                    changed = True
                    break

        return known_ids - selected_ids

    implied_known_ids = _compute_implied_known_ids(active_selected)

    def _checkbox_cell(item: dict[str, Any]) -> ft.Control:
        is_selected = item["id"] in active_selected
        is_implied = item["id"] in implied_known_ids and not is_selected
        cell_bg = ft.Colors.AMBER_50 if is_implied else None
        cell_border_color = ft.Colors.AMBER_500 if is_implied else ft.Colors.TRANSPARENT
        tooltip_text = str(item.get("context", ""))
        if is_implied:
            implied_note = "Implied by selected secrets"
            tooltip_text = f"{implied_note}\n\n{tooltip_text}" if tooltip_text else implied_note

        return ft.Container(
            content=ft.Checkbox(
                label=_layout_label(item),
                value=is_selected,
                on_change=lambda e, kid=item["id"]: update_selection(kid, bool(e.control.value)),
            ),
            tooltip=tooltip_text,
            width=140,
            padding=ft.Padding.only(right=6),
            bgcolor=cell_bg,
            border=ft.Border.all(color=cell_border_color),
            border_radius=6,
        )

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
                        ft.Text("Amber highlight = implied known key", size=11, color=ft.Colors.AMBER_800),
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

        for owner in (session.initializer.name, session.responder.name, "Other"):
            owner_items = grouped.get(owner, [])
            if not owner_items:
                continue

            key_selector_controls.append(ft.Divider(height=8))
            key_selector_controls.append(ft.Text(owner, weight="bold", size=12))

            if owner in {session.initializer.name, session.responder.name}:
                dh_and_rk = sorted(
                    [item for item in owner_items if item.get("kind") in {"dh_private", "rk"}],
                    key=_key_sort,
                )
                ck_send = sorted(
                    [
                        item
                        for item in owner_items
                        if item.get("kind") == "cks" or (item.get("kind") == "ck" and item.get("direction") == "send")
                    ],
                    key=_key_sort,
                )
                ck_recv = sorted(
                    [
                        item
                        for item in owner_items
                        if item.get("kind") == "ckr" or (item.get("kind") == "ck" and item.get("direction") == "recv")
                    ],
                    key=_key_sort,
                )

                for row_items in (dh_and_rk, ck_send, ck_recv):
                    if not row_items:
                        continue
                    key_selector_controls.append(
                        ft.Row(
                            controls=[_checkbox_cell(item) for item in row_items],
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                    )
            else:
                other_items = sorted(owner_items, key=_key_sort)
                key_selector_controls.append(
                    ft.Row(
                        controls=[_checkbox_cell(item) for item in other_items],
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
    )
