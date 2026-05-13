from __future__ import annotations

from typing import Any

from components.data_classes import DHKeyPair, DoubleRatchetState, DRHeader
from modules.base_view import last_n_chars
from modules import external as ext
from modules.messaging.messaging_base_view import get_key_display_label, get_key_tooltip_text

"""Attacker analysis helpers for Double Ratchet visualization.

This module provides utilities used by the attacker dashboard UI to enumerate
potential secrets (RKs, CKs, DHs, MKs), attempt decryption using selected
compromised secrets, and compute implied secrets discovered from successful
decryptions. The functions are written for use by the educational UI and
prioritize clarity over performance.
"""


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
    """Collect a list of candidate secrets the attacker can choose to compromise.

    Returns a list of option dicts with metadata suitable for rendering in the
    attacker UI (labels, kinds, associated party and context information).
    """
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
            f"MK#{message.seq_id}",
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


def _try_decrypt_with_message_key(entry: dict[str, Any], mk: bytes, session_ad: bytes) -> str:
    header = entry.get("header")
    cipher = entry.get("cipher")
    if not isinstance(header, DRHeader) or not isinstance(cipher, bytes):
        return ""
    if not isinstance(mk, bytes) or not mk:
        return ""

    try:
        plaintext = ext.DECRYPT(mk, cipher, ext.CONCAT(session_ad, header))
    except ValueError:
        return ""
    return _decode_plaintext(plaintext)


def _derive_chain_message_key(chain_key: bytes, step_count: int) -> bytes | None:
    """Derive the message key after advancing `step_count` times from `chain_key`.

    Returns the derived message key (`mk`) or `None` if inputs are invalid.
    """
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
    session_ad: bytes = b"",
) -> list[dict[str, Any]]:
    """Attempt to decrypt all messages using the provided `compromised_secrets`.

    Returns a list of analysis results indicating which messages are
    decryptable, the discovered plaintexts, and metadata describing how the
    plaintext was recovered.
    """
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
            "usage": [],
        }
        for entry in messages
    ]

    result_lookup = {
        (result["id"], result["state"]): result
        for result in results
    }

    def mark_decryptable(
        entry: dict[str, Any],
        plaintext: str,
        source: str,
        usage: dict[str, Any] | None = None,
    ) -> None:
        if not plaintext:
            return
        result = result_lookup.get((entry["id"], entry["state"]))
        if result is None or result["decryptable"]:
            return
        result["decryptable"] = True
        result["plaintext"] = plaintext
        result["source"] = source
        if usage is not None:
            result["usage"] = [dict(usage)]

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
            plaintext = _try_decrypt_with_message_key(entry, secret.get("value"), session_ad)
            if plaintext:
                mark_decryptable(
                    entry,
                    plaintext,
                    str(secret.get("label", "MK")),
                    usage={
                        "kind": "mk",
                        "id": str(secret.get("id", "")),
                        "message_id": int(entry.get("id", 0)),
                    },
                )

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
            if not isinstance(header, DRHeader):
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
            plaintext = _try_decrypt_with_message_key(entry, mk, session_ad)
            if plaintext:
                mark_decryptable(
                    entry,
                    plaintext,
                    f"{secret.get('label', 'CK')} -> KDF_CK step {step_count}",
                    usage={
                        "kind": "ck",
                        "id": str(secret.get("id", "")),
                        "party": party,
                        "direction": direction,
                        "public_key": public_key,
                        "step_n": int(header.n),
                        "message_id": int(entry.get("id", 0)),
                    },
                )
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

        def _key_number(key_id: str) -> int:
            try:
                return int(key_id.rsplit(":", 1)[1])
            except (ValueError, IndexError):
                return 0

        for rk_secret in rk_candidates:
            rk_value = rk_secret.get("value")
            if not isinstance(rk_value, bytes) or not rk_value:
                continue

            current_rk = rk_value
            rk_id = str(rk_secret.get("id", ""))
            rk_key_number = _key_number(rk_id)

            # Only use DH keys that were created at or after this RK.
            # Earlier DH keys predate this RK and would corrupt current_rk.
            effective_dh_sequence = [
                s for s in dh_sequence
                if _key_number(str(s.get("id", ""))) >= rk_key_number
            ]

            for idx, dh_secret in enumerate(effective_dh_sequence):
                local_priv = str(dh_secret.get("value", ""))
                local_pub = str(dh_secret.get("public", ""))
                peer_pub = str(dh_secret.get("remote_public", ""))
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

                if idx + 1 >= len(effective_dh_sequence):
                    continue

                next_dh = effective_dh_sequence[idx + 1]
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
        header: DRHeader,
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
        if not isinstance(header, DRHeader):
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

        plaintext = _try_decrypt_with_message_key(entry, mk, session_ad)
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
        mark_decryptable(
            entry,
            plaintext,
            source,
            usage={
                "kind": "derived_ck",
                "party": str(ctx.get("party", "")),
                "direction": direction,
                "public_key": str(header.dh),
                "step_n": int(header.n),
                "message_id": int(entry.get("id", 0)),
            },
        )
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
                if not isinstance(header, DRHeader):
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
    session_ad: bytes = b"",
) -> list[dict[str, Any]]:
    """Compatibility wrapper used by the UI to run attacker analysis.

    Delegates to `decrypt_with_attacker_selection` and returns the same
    analysis structure expected by the attacker dashboard view.
    """
    return decrypt_with_attacker_selection(session, pending_messages, compromised_secrets, session_ad)


def find_best_ck_id(
    options: list[dict[str, Any]],
    party: str,
    direction: str,
    public_key: str,
    step_n: int,
) -> str | None:
    best_id: str | None = None
    best_start_n = -1

    def _resolve_direction(item: dict[str, Any]) -> str:
        item_direction = item.get("direction")
        if item_direction in {"send", "recv"}:
            return str(item_direction)
        if item.get("kind") == "cks":
            return "send"
        if item.get("kind") == "ckr":
            return "recv"
        return ""

    for candidate in options:
        if candidate.get("party") != party:
            continue
        if _resolve_direction(candidate) != direction:
            continue

        candidate_public = candidate.get("public") if direction == "send" else candidate.get("remote_public")
        if candidate_public != public_key:
            continue

        candidate_start_n = candidate.get("start_n")
        if not isinstance(candidate_start_n, int) or candidate_start_n > step_n:
            continue

        if candidate_start_n >= best_start_n:
            best_start_n = candidate_start_n
            best_id = str(candidate.get("id", ""))
    return best_id if best_id else None


def imply_mirror_ck_id(
    options: list[dict[str, Any]],
    options_by_id: dict[str, dict[str, Any]],
    opposite_party_by_name: dict[str, str],
    ck_id: str,
) -> str | None:
    secret = options_by_id.get(ck_id)
    if secret is None:
        return None

    kind = str(secret.get("kind", ""))
    if kind not in {"ck", "cks", "ckr"}:
        return None

    party = str(secret.get("party", ""))
    if not party:
        return None

    mirror_party = opposite_party_by_name.get(party, "")
    if not mirror_party:
        return None

    direction = secret.get("direction")
    if direction not in {"send", "recv"}:
        if kind == "cks":
            direction = "send"
        elif kind == "ckr":
            direction = "recv"
    if direction not in {"send", "recv"}:
        return None

    mirror_direction = "recv" if direction == "send" else "send"
    public_key = str(secret.get("public", "")) if direction == "send" else str(secret.get("remote_public", ""))
    if not public_key:
        return None

    start_n = secret.get("start_n")
    if not isinstance(start_n, int):
        return None

    return find_best_ck_id(
        options=options,
        party=mirror_party,
        direction=mirror_direction,
        public_key=public_key,
        step_n=start_n,
    )


def find_message_mk_id(options: list[dict[str, Any]], message_id: int) -> str | None:
    for candidate in options:
        if candidate.get("kind") != "mk":
            continue
        if candidate.get("seq_id") != message_id:
            continue
        candidate_id = str(candidate.get("id", ""))
        if candidate_id:
            return candidate_id
    return None


def implied_ids_from_usage(
    options: list[dict[str, Any]],
    options_by_id: dict[str, dict[str, Any]],
    opposite_party_by_name: dict[str, str],
    session: DoubleRatchetState,
    pending_messages: list[dict[str, Any]],
    session_ad: bytes,
    known_ids: set[str],
) -> set[str]:
    compromised_subset = {
        key_id: dict(options_by_id[key_id])
        for key_id in known_ids
        if key_id in options_by_id
    }
    analysis = decrypt_with_attacker_selection(session, pending_messages, compromised_subset, session_ad)

    implied: set[str] = set()
    for result in analysis:
        if not result.get("decryptable"):
            continue

        usage_items = result.get("usage")
        if not isinstance(usage_items, list):
            continue

        for usage in usage_items:
            if not isinstance(usage, dict):
                continue

            direct_id = str(usage.get("id", ""))
            if direct_id and direct_id in options_by_id:
                implied.add(direct_id)
                mirrored_id = imply_mirror_ck_id(options, options_by_id, opposite_party_by_name, direct_id)
                if mirrored_id is not None:
                    implied.add(mirrored_id)

            usage_kind = str(usage.get("kind", ""))
            if usage_kind == "derived_ck":
                party = str(usage.get("party", ""))
                direction = str(usage.get("direction", ""))
                public_key = str(usage.get("public_key", ""))
                step_n = usage.get("step_n")
                if party and direction in {"send", "recv"} and public_key and isinstance(step_n, int):
                    matched_ck_id = find_best_ck_id(
                        options=options,
                        party=party,
                        direction=direction,
                        public_key=public_key,
                        step_n=step_n,
                    )
                    if matched_ck_id is not None:
                        implied.add(matched_ck_id)
                        mirrored_id = imply_mirror_ck_id(options, options_by_id, opposite_party_by_name, matched_ck_id)
                        if mirrored_id is not None:
                            implied.add(mirrored_id)

            message_id = usage.get("message_id")
            if isinstance(message_id, int):
                message_mk_id = find_message_mk_id(options, message_id)
                if message_mk_id is not None:
                    implied.add(message_mk_id)

    return implied


def compute_implied_known_ids(
    options: list[dict[str, Any]],
    options_by_id: dict[str, dict[str, Any]],
    opposite_party_by_name: dict[str, str],
    session: DoubleRatchetState,
    pending_messages: list[dict[str, Any]],
    session_ad: bytes,
    selected_ids: set[str],
) -> set[str]:
    """Compute secrets that are implied by a set of already selected secrets.

    When an attacker compromises certain keys, other keys may become
    recoverable (implied) — this function iteratively discovers such keys by
    running the decryption analysis on the currently-known subset.
    """
    known_ids = {key_id for key_id in selected_ids if key_id in options_by_id}

    changed = True
    while changed:
        changed = False
        new_implied = implied_ids_from_usage(
            options, options_by_id, opposite_party_by_name, session, pending_messages, session_ad, known_ids
        )
        new_ids = new_implied - known_ids
        if new_ids:
            known_ids.update(new_ids)
            changed = True

    return known_ids - selected_ids
