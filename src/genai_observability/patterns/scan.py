from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from genai_observability.patterns.library import PatternLibrary
from genai_observability.schemas.enums import DetectorStage

PAYLOAD_FIELD_STAGES: dict[str, DetectorStage] = {
    "content.system": DetectorStage.INSTRUCTIONS,
    "content.user": DetectorStage.USER_INPUT,
    "content.output": DetectorStage.MODEL_OUTPUT,
    "content.retrieved": DetectorStage.RETRIEVAL,
    "content.tool_args": DetectorStage.TOOL_ARGS,
    "content.tool_result": DetectorStage.TOOL_RESULT,
    "authz.principal_id": DetectorStage.AUTHORIZATION,
    "authz.roles": DetectorStage.AUTHORIZATION,
    "authz.resource": DetectorStage.AUTHORIZATION,
}


@dataclass(frozen=True)
class PayloadHit:
    stage: DetectorStage
    match_class: str


def redact_string(value: str, library: PatternLibrary) -> str:
    return library.canary_regex().sub(library.canary_grammar.replacement, value)


def _next_free_key(candidate: str, taken: set[str]) -> str:
    if candidate not in taken:
        return candidate
    index = 2
    while f"{candidate}_{index}" in taken:
        index += 1
    return f"{candidate}_{index}"


def assign_redacted_keys(keys: list[str], library: PatternLibrary) -> dict[str, str]:
    """Map original keys to unique redacted names.

    Collision rule:
    1. Keys with no canary substring keep their original names and are reserved first.
    2. Keys containing canary substrings receive the same in-place substring
       replacement used for string values, so surrounding key text is preserved.
    3. Those canary keys are then assigned in lexicographic order of the original
       key, independent of dictionary insertion order.
    4. If a candidate name is already reserved by an unredacted key or an earlier
       assigned redacted key, append ``_N`` for the smallest integer ``N >= 2``
       that is free. Values are never silently overwritten.
    """
    regex = library.canary_regex()
    assigned: dict[str, str] = {}
    taken: set[str] = set()
    for key in keys:
        if regex.search(key) is None:
            assigned[key] = key
            taken.add(key)
    for key in sorted(key for key in keys if regex.search(key) is not None):
        candidate = redact_string(key, library)
        name = _next_free_key(candidate, taken)
        assigned[key] = name
        taken.add(name)
    return assigned


def redact_payload(value: Any, library: PatternLibrary) -> Any:
    if isinstance(value, str):
        return redact_string(value, library)
    if isinstance(value, list):
        return [redact_payload(item, library) for item in value]
    if isinstance(value, dict):
        original_keys = [str(key) for key in value]
        key_map = assign_redacted_keys(original_keys, library)
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            new_key = key_map[str(key)]
            if library.is_secret_key(str(key)):
                redacted[new_key] = library.secret_keys.replacement
            else:
                redacted[new_key] = redact_payload(item, library)
        return dict(sorted(redacted.items(), key=lambda item: item[0]))
    return value


def _scan_node(value: Any, library: PatternLibrary) -> Iterator[str]:
    if isinstance(value, str):
        if library.canary_regex().search(value):
            yield "canary_grammar"
        return
    if isinstance(value, list):
        for item in value:
            yield from _scan_node(item, library)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if library.is_secret_key(key_text):
                yield "secret_key"
            if library.canary_regex().search(key_text):
                yield "canary_grammar"
            yield from _scan_node(item, library)
        return


def scan_payload(value: Any, stage: DetectorStage, library: PatternLibrary) -> list[PayloadHit]:
    classes = set(_scan_node(value, library))
    return [PayloadHit(stage=stage, match_class=match_class) for match_class in sorted(classes)]
