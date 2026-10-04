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


def _redacted_key_name(key: str, library: PatternLibrary, used: dict[str, int]) -> str:
    if library.canary_regex().search(key) is None:
        return key
    base = library.canary_grammar.replacement
    used[base] = used.get(base, 0) + 1
    if used[base] == 1:
        return base
    return f"{base}_{used[base]}"


def redact_payload(value: Any, library: PatternLibrary) -> Any:
    if isinstance(value, str):
        return redact_string(value, library)
    if isinstance(value, list):
        return [redact_payload(item, library) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        used_keys: dict[str, int] = {}
        for key, item in value.items():
            new_key = _redacted_key_name(str(key), library, used_keys)
            if library.is_secret_key(str(key)):
                redacted[new_key] = library.secret_keys.replacement
            else:
                redacted[new_key] = redact_payload(item, library)
        return redacted
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
