"""Shared messaging module base and nested-state serialization helpers.

This file provides the base controller class used by the messaging protocols
and the generic nested encode/decode functions that preserve dataclasses,
enums, and byte payloads during persistence.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from modules.base_module import BaseModule


class MessagingBaseModule(BaseModule):
    """Shared module-layer base for messaging protocol controllers."""


def encode_nested(value: Any) -> Any:
    """Recursively encode dataclasses, enums, and bytes for JSON storage."""

    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, Enum):
        return {"__enum__": value.__class__.__name__, "value": value.value}
    if is_dataclass(value):
        return {
            "__class__": value.__class__.__name__,
            "fields": {field.name: encode_nested(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, dict):
        return {key: encode_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode_nested(item) for item in value]
    return value


def decode_nested(value: Any, class_map: dict[str, type]) -> Any:
    """Recursively decode JSON storage back into bytes, enums, and dataclasses."""

    if isinstance(value, dict):
        if "__bytes__" in value and isinstance(value["__bytes__"], str):
            try:
                return bytes.fromhex(value["__bytes__"])
            except ValueError:
                return b""
        if "__enum__" in value and isinstance(value["__enum__"], str):
            enum_cls = class_map.get(value["__enum__"])
            if enum_cls is not None and issubclass(enum_cls, Enum):
                try:
                    return enum_cls(value.get("value"))
                except Exception:
                    return value.get("value")
        if "__class__" in value and isinstance(value["__class__"], str):
            class_name = value["__class__"]
            cls = class_map.get(class_name)
            raw_fields = value.get("fields", {})
            if cls is not None and isinstance(raw_fields, dict):
                kwargs = {key: decode_nested(item, class_map) for key, item in raw_fields.items()}
                return cls(**kwargs)

        def _decode_key(key: Any) -> Any:
            if isinstance(key, str) and key.isdigit():
                try:
                    return int(key)
                except ValueError:
                    return key
            return key

        return {_decode_key(key): decode_nested(item, class_map) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_nested(item, class_map) for item in value]
    return value


__all__ = ["MessagingBaseModule", "encode_nested", "decode_nested"]
FAMILY_ID = "messaging"
