"""Evidence-location helpers shared by extraction and evaluation.

Locations are JSON pointers into the serialized export artifact (canonical
JSON). Credit requires that a pointer resolve in that document, not merely
in an in-memory model dump.
"""

import json
from typing import Any

from genai_observability.schemas.export import TelemetryExport
from genai_observability.serialization import canonical_json_text


def serialized_export_text(export: TelemetryExport) -> str:
    return canonical_json_text(export)


def export_dump(export: TelemetryExport) -> dict[str, Any]:
    """Parse the canonical serialized artifact. This is the credit surface."""
    return json.loads(serialized_export_text(export))


def parse_artifact_text(text: str) -> dict[str, Any]:
    document = json.loads(text)
    if not isinstance(document, dict):
        raise TypeError("export artifact root must be an object")
    return document


def decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer!r}")
    node = document
    for raw in pointer[1:].split("/"):
        token = decode_pointer_token(raw)
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict):
            if token not in node:
                raise KeyError(token)
            node = node[token]
        else:
            raise KeyError(token)
    return node


def pointer_exists(document: Any, pointer: str) -> bool:
    try:
        resolve_pointer(document, pointer)
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return True


def pointer_exists_in_artifact(text: str, pointer: str) -> bool:
    return pointer_exists(parse_artifact_text(text), pointer)


def span_pointer(index: int, *parts: str) -> str:
    path = f"/spans/{index}"
    for part in parts:
        path += "/" + part.replace("~", "~0").replace("/", "~1")
    return path
