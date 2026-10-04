import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

# Frozen identity rule from EXPERIMENT_CONTRACT.md section 8.
# exclude_none is part of that identity rule: omitted optional groups must not
# appear as JSON nulls, or hashes would change without a semantic change.


def to_plain(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return json.loads(json.dumps(value, ensure_ascii=False))


def canonical_json_bytes(value: BaseModel | Mapping[str, Any]) -> bytes:
    """UTF-8 JSON with sorted keys, compact separators, and ensure_ascii=false."""
    text = json.dumps(
        to_plain(value),
        ensure_ascii=False,
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
