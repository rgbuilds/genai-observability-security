"""R-extractor: telemetry plus public question definitions only.

Must not import research.references or read answer manifests.
"""

from typing import Any

from genai_observability.grading.evidence import export_dump, span_pointer
from genai_observability.grading.extract import (
    ExtractedFact,
    ForensicExtraction,
    _answered,
    _missing,
)
from genai_observability.research.questions import R2_SELECTORS, RESEARCH_QUESTION_IDS
from genai_observability.schemas.enums import SpanKind
from genai_observability.schemas.export import TelemetryExport
from genai_observability.serialization import canonical_json_text


def _tool_indexes(export: TelemetryExport) -> list[int]:
    return [index for index, span in enumerate(export.spans) if span.kind is SpanKind.TOOL]


def _retrieval_indexes(export: TelemetryExport) -> list[int]:
    return [index for index, span in enumerate(export.spans) if span.kind is SpanKind.RETRIEVAL]


def _model_indexes(export: TelemetryExport) -> list[int]:
    return [index for index, span in enumerate(export.spans) if span.kind is SpanKind.MODEL]


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return canonical_json_text(value) if isinstance(value, dict) else str(value)


def _r2_from_span(span) -> tuple[str | None, str | None]:
    """First existing public selector wins. Paths live in question definitions."""
    for selector in R2_SELECTORS:
        if selector == "authz.resource":
            if span.authz is not None and span.authz.resource:
                return span.authz.resource, "authz.resource"
        elif selector == "content.tool_args.note_id":
            if span.content is not None and isinstance(span.content.tool_args, dict):
                note_id = span.content.tool_args.get("note_id")
                if isinstance(note_id, str):
                    return note_id, "content.tool_args"
    return None, None


def _extract_r1(export: TelemetryExport) -> ExtractedFact:
    indexes = _tool_indexes(export)
    values: list[Any] = []
    pointers: list[str] = []
    for index in indexes:
        span = export.spans[index]
        if span.content is None or span.content.tool_args is None:
            continue
        values.append(span.content.tool_args)
        pointers.append(span_pointer(index, "content", "tool_args"))
    if not values:
        return _missing("R1")
    return _answered("R1", values, *pointers)


def _extract_r2(export: TelemetryExport) -> ExtractedFact:
    indexes = _tool_indexes(export)
    values: list[str] = []
    pointers: list[str] = []
    for index in indexes:
        span = export.spans[index]
        value, selector = _r2_from_span(span)
        if value is None or selector is None:
            continue
        values.append(value)
        if selector == "authz.resource":
            pointers.append(span_pointer(index, "authz", "resource"))
        else:
            pointers.append(span_pointer(index, "content", "tool_args"))
    if not values:
        return _missing("R2")
    return _answered("R2", values[0] if len(values) == 1 else values, *pointers)


def _extract_r3(export: TelemetryExport) -> ExtractedFact:
    for index in _retrieval_indexes(export):
        span = export.spans[index]
        if span.content is not None and span.content.retrieved is not None:
            return _answered("R3", span.content.retrieved, span_pointer(index, "content", "retrieved"))
    return _missing("R3")


def _extract_r4(export: TelemetryExport) -> ExtractedFact:
    loc1 = None
    loc1_ptr = None
    for index in _retrieval_indexes(export):
        span = export.spans[index]
        if span.content is not None and span.content.retrieved is not None:
            loc1 = span.content.retrieved
            loc1_ptr = span_pointer(index, "content", "retrieved")
            break
    loc2 = None
    loc2_ptrs: list[str] = []
    tool_indexes = _tool_indexes(export)
    if tool_indexes:
        parts: list[str] = []
        for index in tool_indexes:
            span = export.spans[index]
            if span.content is None or span.content.tool_args is None:
                continue
            parts.append(_json_text(span.content.tool_args))
            loc2_ptrs.append(span_pointer(index, "content", "tool_args"))
        if parts:
            loc2 = "\n".join(parts)
    else:
        for index in _model_indexes(export):
            span = export.spans[index]
            if span.content is not None and span.content.output is not None:
                loc2 = span.content.output
                loc2_ptrs.append(span_pointer(index, "content", "output"))
                break
    if loc1 is None and loc2 is None:
        return _missing("R4")
    pointers = [ptr for ptr in (loc1_ptr, *loc2_ptrs) if ptr]
    return _answered("R4", {"loc1": loc1, "loc2": loc2}, *pointers)


def _map_tool_outcome(span) -> str | None:
    if span.security is not None and span.security.authz_decision is not None:
        return "allowed" if span.security.authz_decision.value == "allow" else "denied"
    if span.status_code in {401, 403}:
        return "denied"
    if span.status_code == 200:
        return "allowed"
    return None


def _extract_r5(export: TelemetryExport) -> ExtractedFact:
    values: list[str] = []
    pointers: list[str] = []
    for index in _tool_indexes(export):
        span = export.spans[index]
        outcome = _map_tool_outcome(span)
        if outcome is None:
            continue
        values.append(outcome)
        if span.security is not None and span.security.authz_decision is not None:
            pointers.append(span_pointer(index, "security", "authz_decision"))
        else:
            pointers.append(span_pointer(index, "status_code"))
    if not values:
        return _missing("R5")
    return _answered("R5", values[0] if len(values) == 1 else values, *pointers)


def _extract_r6(export: TelemetryExport) -> ExtractedFact:
    for index in _model_indexes(export):
        span = export.spans[index]
        if span.content is not None and span.content.output is not None:
            return _answered("R6", span.content.output, span_pointer(index, "content", "output"))
    return _missing("R6")


def _extract_r7(export: TelemetryExport) -> ExtractedFact:
    edges: list[dict[str, str]] = []
    pointers: list[str] = []
    for index, span in enumerate(export.spans):
        if span.parent_span_id is None:
            continue
        edges.append({"parent": span.parent_span_id, "child": span.span_id})
        pointers.append(span_pointer(index, "parent_span_id"))
    edges.sort(key=lambda edge: (edge["parent"], edge["child"]))
    if not pointers:
        return _answered("R7", [], "/spans")
    return _answered("R7", edges, *pointers)


_EXTRACTORS = {
    "R1": _extract_r1,
    "R2": _extract_r2,
    "R3": _extract_r3,
    "R4": _extract_r4,
    "R5": _extract_r5,
    "R6": _extract_r6,
    "R7": _extract_r7,
}


def extract_research_answers(export: TelemetryExport) -> ForensicExtraction:
    export_dump(export)
    facts = tuple(_EXTRACTORS[question_id](export) for question_id in RESEARCH_QUESTION_IDS)
    return ForensicExtraction(facts=facts)
