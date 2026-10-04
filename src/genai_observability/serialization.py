import hashlib
import json
import math
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel

# Frozen identity rule from EXPERIMENT_CONTRACT.md section 8.
# exclude_none is part of that identity rule: omitted optional groups must not
# appear as JSON nulls, or hashes would change without a semantic change.
#
# Non-finite floats are rejected before any JSON conversion. Pydantic's
# mode="json" dump and json.dumps(allow_nan=True) can turn NaN/Inf into null
# or emit invalid JSON; neither is allowed.


class NonFiniteNumberError(ValueError):
    """NaN or infinity is not representable in canonical JSON."""


def reject_nonfinite(value: Any, path: str = "$") -> None:
    """Raise if value contains NaN, +Inf, or -Inf. Walks nested dicts and lists."""
    if isinstance(value, float) and not math.isfinite(value):
        raise NonFiniteNumberError(f"non-finite number at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            reject_nonfinite(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{path}[{index}]")
        return
    if isinstance(value, BaseModel):
        reject_nonfinite(value.model_dump(mode="python"), path)


def _to_jsonable(value: Any) -> Any:
    reject_nonfinite(value)
    if isinstance(value, BaseModel):
        return _to_jsonable(value.model_dump(mode="python", exclude_none=True))
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def to_plain(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        data = value.model_dump(mode="python", exclude_none=True)
    else:
        data = dict(value)
    reject_nonfinite(data)
    converted = _to_jsonable(data)
    if not isinstance(converted, dict):
        raise TypeError("canonical JSON root must be an object")
    return converted


def canonical_json_bytes(value: BaseModel | Mapping[str, Any]) -> bytes:
    """UTF-8 JSON with sorted keys, compact separators, and ensure_ascii=false."""
    text = json.dumps(
        to_plain(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def canonical_json_text(value: BaseModel | Mapping[str, Any]) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: BaseModel | Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(value))
