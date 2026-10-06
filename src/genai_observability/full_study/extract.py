"""FS extractor: telemetry plus public question definitions only.

Must not import full_study.references or read answer manifests.
"""

from typing import Any

from genai_observability.grading.evidence import export_dump, span_pointer
from genai_observability.grading.extract import (
    ExtractedFact,
    ForensicExtraction,
    _ambiguous,
    _answered,
    _missing,
    _unique_or_ambiguous,
)
from genai_observability.full_study.questions import FS13_SELECTORS, FULL_STUDY_QUESTION_IDS
from genai_observability.schemas.enums import DetectorCategory, PrivilegeClass, SpanKind
from genai_observability.schemas.export import TelemetryExport
from genai_observability.serialization import canonical_json_text


def _indexes(export: TelemetryExport, kind: SpanKind) -> list[int]:
    return [index for index, span in enumerate(export.spans) if span.kind is kind]


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return canonical_json_text(value) if isinstance(value, dict) else str(value)


def _extract_fs1(export: TelemetryExport) -> ExtractedFact:
    if not export.request_id:
        return _missing("FS1")
    return _answered("FS1", export.request_id, "/request_id")


def _extract_fs2(export: TelemetryExport) -> ExtractedFact:
    records: list[tuple[dict[str, str], tuple[str, ...]]] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.MODEL:
            continue
        identity: dict[str, str] = {"operation": span.name}
        pointers = [span_pointer(index, "name")]
        if span.model is not None and span.model.name is not None:
            identity["name"] = span.model.name
            pointers.append(span_pointer(index, "model", "name"))
        records.append((identity, tuple(pointers)))
    if not records:
        return _missing("FS2")
    identities = {tuple(sorted(record[0].items())) for record in records}
    pointers = tuple(pointer for record in records for pointer in record[1])
    if len(identities) > 1:
        return _ambiguous("FS2", *pointers)
    return _answered("FS2", records[0][0], *pointers)


def _extract_fs3(export: TelemetryExport) -> ExtractedFact:
    indexes = _indexes(export, SpanKind.RETRIEVAL)
    if indexes:
        return _answered("FS3", "yes", *(span_pointer(index, "kind") for index in indexes))
    return _answered("FS3", "no", "/spans")


def _extract_fs4(export: TelemetryExport) -> ExtractedFact:
    candidates: list[str] = []
    pointers: list[str] = []
    for index, span in enumerate(export.spans):
        if span.retrieval is None:
            continue
        if span.retrieval.source_id is not None:
            candidates.append(span.retrieval.source_id)
            pointers.append(span_pointer(index, "retrieval", "source_id"))
        if span.retrieval.hash is not None:
            candidates.append(span.retrieval.hash)
            pointers.append(span_pointer(index, "retrieval", "hash"))
    if not candidates:
        return _missing("FS4")
    return _answered("FS4", candidates, *pointers)


def _extract_fs5(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.tool is not None and span.tool.name:
            pairs.append((span.tool.name, span_pointer(index, "tool", "name")))
    return _unique_or_ambiguous("FS5", pairs)


def _map_tool_outcome(span) -> tuple[str, str] | None:
    if span.security is not None and span.security.authz_decision is not None:
        value = "allowed" if span.security.authz_decision.value == "allow" else "denied"
        return value, "security.authz_decision"
    if span.status_code in {401, 403}:
        return "denied", "status_code"
    if span.status_code == 200:
        return "allowed", "status_code"
    return None


def _extract_fs6(export: TelemetryExport) -> ExtractedFact:
    values: list[str] = []
    pointers: list[str] = []
    for index in _indexes(export, SpanKind.TOOL):
        span = export.spans[index]
        mapped = _map_tool_outcome(span)
        if mapped is None:
            continue
        value, selector = mapped
        values.append(value)
        if selector == "security.authz_decision":
            pointers.append(span_pointer(index, "security", "authz_decision"))
        else:
            pointers.append(span_pointer(index, "status_code"))
    if not values:
        return _missing("FS6")
    return _answered("FS6", values[0] if len(values) == 1 else values, *pointers)


def _extract_fs7(export: TelemetryExport) -> ExtractedFact:
    edges: list[dict[str, str]] = []
    pointers: list[str] = []
    for index, span in enumerate(export.spans):
        if span.parent_span_id is None:
            continue
        edges.append({"parent": span.parent_span_id, "child": span.span_id})
        pointers.append(span_pointer(index, "parent_span_id"))
    edges.sort(key=lambda edge: (edge["parent"], edge["child"]))
    if not pointers:
        return _answered("FS7", [], "/spans")
    return _answered("FS7", edges, *pointers)


def _extract_fs8(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.security is not None and span.security.trust_class is not None:
            pairs.append((span.security.trust_class.value, span_pointer(index, "security", "trust_class")))
    return _unique_or_ambiguous("FS8", pairs)


def _extract_fs9(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index in _indexes(export, SpanKind.TOOL):
        span = export.spans[index]
        if span.security is None or span.security.privilege_class is None:
            continue
        label = "yes" if span.security.privilege_class is PrivilegeClass.PRIVILEGED else "no"
        pairs.append((label, span_pointer(index, "security", "privilege_class")))
    return _unique_or_ambiguous("FS9", pairs)


def _extract_fs10(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index in _indexes(export, SpanKind.TOOL):
        span = export.spans[index]
        if span.security is None or span.security.denial_reason is None:
            continue
        pairs.append(
            (span.security.denial_reason.value, span_pointer(index, "security", "denial_reason"))
        )
    return _unique_or_ambiguous("FS10", pairs)


def _extract_fs11(export: TelemetryExport) -> ExtractedFact:
    retained = any(span.detector_events is not None for span in export.spans)
    if not retained:
        return _missing("FS11")
    pointers: list[str] = []
    found = False
    for index, span in enumerate(export.spans):
        if span.detector_events is None:
            continue
        pointers.append(span_pointer(index, "detector_events"))
        for event in span.detector_events:
            if event.category is DetectorCategory.SENSITIVE_DATA:
                found = True
    if not pointers:
        return _missing("FS11")
    return _answered("FS11", "yes" if found else "no", *pointers)


def _extract_fs12(export: TelemetryExport) -> ExtractedFact:
    values: list[Any] = []
    pointers: list[str] = []
    for index in _indexes(export, SpanKind.TOOL):
        span = export.spans[index]
        if span.content is None or span.content.tool_args is None:
            continue
        values.append(span.content.tool_args)
        pointers.append(span_pointer(index, "content", "tool_args"))
    if not values:
        return _missing("FS12")
    return _answered("FS12", values, *pointers)


def _fs13_from_span(span) -> tuple[str | None, str | None]:
    for selector in FS13_SELECTORS:
        if selector == "authz.resource":
            if span.authz is not None and span.authz.resource:
                return span.authz.resource, "authz.resource"
        elif selector == "content.tool_args.note_id":
            if span.content is not None and isinstance(span.content.tool_args, dict):
                note_id = span.content.tool_args.get("note_id")
                if isinstance(note_id, str):
                    return note_id, "content.tool_args"
    return None, None


def _extract_fs13(export: TelemetryExport) -> ExtractedFact:
    values: list[str] = []
    pointers: list[str] = []
    for index in _indexes(export, SpanKind.TOOL):
        value, selector = _fs13_from_span(export.spans[index])
        if value is None or selector is None:
            continue
        values.append(value)
        if selector == "authz.resource":
            pointers.append(span_pointer(index, "authz", "resource"))
        else:
            pointers.append(span_pointer(index, "content", "tool_args"))
    if not values:
        return _missing("FS13")
    return _answered("FS13", values[0] if len(values) == 1 else values, *pointers)


def _extract_fs14(export: TelemetryExport) -> ExtractedFact:
    for index in _indexes(export, SpanKind.RETRIEVAL):
        span = export.spans[index]
        if span.content is not None and span.content.retrieved is not None:
            return _answered("FS14", span.content.retrieved, span_pointer(index, "content", "retrieved"))
    return _missing("FS14")


def _extract_fs15(export: TelemetryExport) -> ExtractedFact:
    for index in _indexes(export, SpanKind.MODEL):
        span = export.spans[index]
        if span.content is not None and span.content.output is not None:
            return _answered("FS15", span.content.output, span_pointer(index, "content", "output"))
    return _missing("FS15")


def _first_retrieved(export: TelemetryExport) -> tuple[str | None, str | None]:
    for index in _indexes(export, SpanKind.RETRIEVAL):
        span = export.spans[index]
        if span.content is not None and span.content.retrieved is not None:
            return span.content.retrieved, span_pointer(index, "content", "retrieved")
    return None, None


def _extract_fs16(export: TelemetryExport) -> ExtractedFact:
    loc1, loc1_ptr = _first_retrieved(export)
    loc2 = None
    loc2_ptrs: list[str] = []
    tools = _indexes(export, SpanKind.TOOL)
    if tools:
        parts: list[str] = []
        for index in tools:
            span = export.spans[index]
            if span.content is None or span.content.tool_args is None:
                continue
            parts.append(_json_text(span.content.tool_args))
            loc2_ptrs.append(span_pointer(index, "content", "tool_args"))
        if parts:
            loc2 = "\n".join(parts)
    else:
        for index in _indexes(export, SpanKind.MODEL):
            span = export.spans[index]
            if span.content is not None and span.content.output is not None:
                loc2 = span.content.output
                loc2_ptrs.append(span_pointer(index, "content", "output"))
                break
    if loc1 is None and loc2 is None:
        return _missing("FS16")
    pointers = [ptr for ptr in (loc1_ptr, *loc2_ptrs) if ptr]
    return _answered("FS16", {"loc1": loc1, "loc2": loc2}, *pointers)


def _extract_oc1(export: TelemetryExport) -> ExtractedFact:
    loc1, loc1_ptr = _first_retrieved(export)
    loc2 = None
    loc2_ptr = None
    for index in _indexes(export, SpanKind.MODEL):
        span = export.spans[index]
        if span.content is not None and span.content.output is not None:
            loc2 = span.content.output
            loc2_ptr = span_pointer(index, "content", "output")
    if loc1 is None and loc2 is None:
        return _missing("OC1")
    pointers = [ptr for ptr in (loc1_ptr, loc2_ptr) if ptr]
    return _answered("OC1", {"loc1": loc1, "loc2": loc2}, *pointers)


_EXTRACTORS = {
    "FS1": _extract_fs1,
    "FS2": _extract_fs2,
    "FS3": _extract_fs3,
    "FS4": _extract_fs4,
    "FS5": _extract_fs5,
    "FS6": _extract_fs6,
    "FS7": _extract_fs7,
    "FS8": _extract_fs8,
    "FS9": _extract_fs9,
    "FS10": _extract_fs10,
    "FS11": _extract_fs11,
    "FS12": _extract_fs12,
    "FS13": _extract_fs13,
    "FS14": _extract_fs14,
    "FS15": _extract_fs15,
    "FS16": _extract_fs16,
    "OC1": _extract_oc1,
}


def extract_full_study_answers(export: TelemetryExport) -> ForensicExtraction:
    export_dump(export)
    facts = tuple(_EXTRACTORS[question_id](export) for question_id in FULL_STUDY_QUESTION_IDS)
    return ForensicExtraction(facts=facts)
