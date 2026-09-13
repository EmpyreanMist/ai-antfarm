"""Validation and immutable representation of JSON-compatible values."""

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | tuple[JsonValue, ...] | JsonObject
type JsonObject = Mapping[str, JsonValue]


def freeze_json(value: object) -> JsonValue:
    """Validate a JSON value and recursively remove mutable containers."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            frozen[key] = freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(freeze_json(item) for item in value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def freeze_object(value: Mapping[str, object]) -> JsonObject:
    frozen = freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise TypeError("expected a JSON object")
    return frozen


def thaw_json(value: JsonValue) -> object:
    """Return ordinary dict/list containers suitable for json.dumps."""

    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value
