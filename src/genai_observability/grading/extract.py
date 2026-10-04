"""Forensic extractor: telemetry plus question definitions only.

This module must not import reference loaders, canary inventories, or answer
keys, and it must not read the filesystem.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from genai_observability.grading.evidence import export_dump, span_pointer
from genai_observability.grading.questions import QUESTION_IDS, QuestionId
from genai_observability.schemas.enums import DetectorCategory, PrivilegeClass, SpanKind
from genai_observability.schemas.export import TelemetryExport
from genai_observability.schemas.span import CanonicalSpan

# No frozen content-marker vocabulary exists for this suite. Q2/Q8/Q9/Q11
# therefore read only structured security.* fields. Inventing markers would
# change P1/P2 scores.

_Q10_DENIED_CODES = frozenset({401, 403})
_Q10_ALLOWED_CODES = frozenset({200})
_Q15_DENY_CODES = frozenset({401, 403})
_SENSITIVE_CATEGORIES = frozenset(
    {DetectorCategory.SENSITIVE_DATA, DetectorCategory.UNTRUSTED_PROPAGATION}
)


class ExtractionStatus(StrEnum):
    ANSWERED = "answered"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class EvidenceLocation:
    pointer: str


@dataclass(frozen=True)
class ExtractedFact:
    question_id: str
    status: ExtractionStatus
    value: Any = None
    evidence: tuple[EvidenceLocation, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ForensicExtraction:
    facts: tuple[ExtractedFact, ...]

    def fact(self, question_id: str) -> ExtractedFact:
        for item in self.facts:
            if item.question_id == question_id:
                return item
        raise KeyError(question_id)


def _answered(question_id: str, value: Any, *pointers: str) -> ExtractedFact:
    return ExtractedFact(
        question_id=question_id,
        status=ExtractionStatus.ANSWERED,
        value=value,
        evidence=tuple(EvidenceLocation(pointer) for pointer in pointers),
    )


def _missing(question_id: str) -> ExtractedFact:
    return ExtractedFact(question_id=question_id, status=ExtractionStatus.MISSING)


def _ambiguous(question_id: str, *pointers: str) -> ExtractedFact:
    return ExtractedFact(
        question_id=question_id,
        status=ExtractionStatus.AMBIGUOUS,
        evidence=tuple(EvidenceLocation(pointer) for pointer in pointers),
    )


def _span_indexes(export: TelemetryExport, kind: SpanKind) -> list[int]:
    return [index for index, span in enumerate(export.spans) if span.kind is kind]


def _unique_or_ambiguous(
    question_id: str,
    pairs: Sequence[tuple[Any, str]],
) -> ExtractedFact:
    if not pairs:
        return _missing(question_id)
    values = {pair[0] for pair in pairs}
    pointers = tuple(pair[1] for pair in pairs)
    if len(values) > 1:
        return _ambiguous(question_id, *pointers)
    return _answered(question_id, next(iter(values)), *pointers)


def _detector_key_retained(export: TelemetryExport) -> bool:
    return any(span.detector_events is not None for span in export.spans)


def _sensitive_events(export: TelemetryExport) -> list[tuple[int, int, Any]]:
    found: list[tuple[int, int, Any]] = []
    for span_index, span in enumerate(export.spans):
        if span.detector_events is None:
            continue
        for event_index, event in enumerate(span.detector_events):
            if event.category is DetectorCategory.SENSITIVE_DATA:
                found.append((span_index, event_index, event))
    return found


def _extract_q1(export: TelemetryExport) -> ExtractedFact:
    if not export.request_id:
        return _missing("Q1")
    return _answered("Q1", export.request_id, "/request_id")


def _extract_q2(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.security is not None and span.security.trust_class is not None:
            pairs.append((span.security.trust_class.value, span_pointer(index, "security", "trust_class")))
    return _unique_or_ambiguous("Q2", pairs)


def _extract_q3(export: TelemetryExport) -> ExtractedFact:
    # No frozen retrieval-operation-name list; kind == retrieval only.
    indexes = _span_indexes(export, SpanKind.RETRIEVAL)
    if indexes:
        return _answered("Q3", "yes", *(span_pointer(index, "kind") for index in indexes))
    return _answered("Q3", "no", "/spans")


def _extract_q4(export: TelemetryExport) -> ExtractedFact:
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
        return _missing("Q4")
    return _answered("Q4", candidates, *pointers)


def _extract_q5(export: TelemetryExport) -> ExtractedFact:
    records: list[tuple[dict[str, str], tuple[str, ...]]] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.MODEL:
            continue
        identity: dict[str, str] = {"operation": span.name}
        pointers = [span_pointer(index, "name")]
        if span.model is not None and span.model.provider is not None:
            identity["provider"] = span.model.provider
            pointers.append(span_pointer(index, "model", "provider"))
        if span.model is not None and span.model.name is not None:
            identity["name"] = span.model.name
            pointers.append(span_pointer(index, "model", "name"))
        records.append((identity, tuple(pointers)))
    if not records:
        return _missing("Q5")
    identities = {tuple(sorted(record[0].items())) for record in records}
    pointers = tuple(pointer for record in records for pointer in record[1])
    if len(identities) > 1:
        return _ambiguous("Q5", *pointers)
    return _answered("Q5", records[0][0], *pointers)


def _extract_q6(export: TelemetryExport) -> ExtractedFact:
    indexes = _span_indexes(export, SpanKind.TOOL)
    named = [
        index
        for index, span in enumerate(export.spans)
        if span.tool is not None and span.tool.name
    ]
    if indexes or named:
        pointers = [span_pointer(index, "kind") for index in indexes]
        pointers.extend(
            span_pointer(index, "tool", "name") for index in named if index not in indexes
        )
        return _answered("Q6", "yes", *pointers)
    return _answered("Q6", "no", "/spans")


def _tool_name_pairs(export: TelemetryExport) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.tool is not None and span.tool.name:
            pairs.append((span.tool.name, span_pointer(index, "tool", "name")))
    return pairs


def _extract_q7(export: TelemetryExport) -> ExtractedFact:
    return _unique_or_ambiguous("Q7", _tool_name_pairs(export))


def _extract_q8(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.TOOL:
            continue
        if span.security is None or span.security.privilege_class is None:
            continue
        label = "yes" if span.security.privilege_class is PrivilegeClass.PRIVILEGED else "no"
        pairs.append((label, span_pointer(index, "security", "privilege_class")))
    return _unique_or_ambiguous("Q8", pairs)


def _extract_q9(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.TOOL:
            continue
        if span.security is None or span.security.authz_decision is None:
            continue
        pairs.append(
            (span.security.authz_decision.value, span_pointer(index, "security", "authz_decision"))
        )
    return _unique_or_ambiguous("Q9", pairs)


def _map_status_code(code: int) -> str | None:
    if code in _Q10_DENIED_CODES:
        return "denied"
    if code in _Q10_ALLOWED_CODES:
        return "allowed"
    return None


def _extract_q10(export: TelemetryExport) -> ExtractedFact:
    decision_pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.TOOL:
            continue
        if span.security is None or span.security.authz_decision is None:
            continue
        mapped = "allowed" if span.security.authz_decision.value == "allow" else "denied"
        decision_pairs.append((mapped, span_pointer(index, "security", "authz_decision")))
    if decision_pairs:
        return _unique_or_ambiguous("Q10", decision_pairs)

    # Tool-span status_code only. A request-span 200 would mis-score a denied tool.
    code_pairs: list[tuple[str, str]] = []
    unmapped: list[str] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.TOOL or span.status_code is None:
            continue
        mapped = _map_status_code(span.status_code)
        pointer = span_pointer(index, "status_code")
        if mapped is None:
            unmapped.append(pointer)
            continue
        code_pairs.append((mapped, pointer))
    if unmapped and not code_pairs:
        return _missing("Q10")
    return _unique_or_ambiguous("Q10", code_pairs)


def _extract_q11(export: TelemetryExport) -> ExtractedFact:
    pairs: list[tuple[str, str]] = []
    for index, span in enumerate(export.spans):
        if span.kind is not SpanKind.TOOL:
            continue
        if span.security is None or span.security.denial_reason is None:
            continue
        pairs.append(
            (span.security.denial_reason.value, span_pointer(index, "security", "denial_reason"))
        )
    return _unique_or_ambiguous("Q11", pairs)


def _extract_q12(export: TelemetryExport) -> ExtractedFact:
    if not _detector_key_retained(export):
        return _missing("Q12")
    events = _sensitive_events(export)
    if events:
        pointers = [
            span_pointer(span_index, "detector_events", str(event_index), "category")
            for span_index, event_index, _event in events
        ]
        return _answered("Q12", "yes", *pointers)
    retained = [
        span_pointer(index, "detector_events")
        for index, span in enumerate(export.spans)
        if span.detector_events is not None
    ]
    return _answered("Q12", "no", *retained)


def _extract_q13(export: TelemetryExport) -> ExtractedFact:
    if not _detector_key_retained(export):
        return _missing("Q13")
    events = _sensitive_events(export)
    if not events:
        return _missing("Q13")
    pairs = [
        (
            event.stage.value,
            span_pointer(span_index, "detector_events", str(event_index), "stage"),
        )
        for span_index, event_index, event in events
    ]
    return _unique_or_ambiguous("Q13", pairs)


def _extract_q14(export: TelemetryExport) -> ExtractedFact:
    edges: list[dict[str, str]] = []
    pointers: list[str] = []
    for index, span in enumerate(export.spans):
        if span.parent_span_id is None:
            continue
        edges.append({"parent": span.parent_span_id, "child": span.span_id})
        pointers.append(span_pointer(index, "parent_span_id"))
    edges.sort(key=lambda edge: (edge["parent"], edge["child"]))
    if not pointers:
        return _answered("Q14", [], "/spans")
    return _answered("Q14", edges, *pointers)


def _q15_clause_a(export: TelemetryExport) -> list[str]:
    pointers: list[str] = []
    for span_index, span in enumerate(export.spans):
        if span.detector_events is None:
            continue
        for event_index, event in enumerate(span.detector_events):
            if event.category in _SENSITIVE_CATEGORIES:
                pointers.append(
                    span_pointer(span_index, "detector_events", str(event_index), "category")
                )
    return pointers


def _q15_clause_b(export: TelemetryExport) -> list[str]:
    pointers: list[str] = []
    for index, span in enumerate(export.spans):
        if span.security is not None and span.security.authz_decision is not None:
            if span.security.authz_decision.value == "deny":
                pointers.append(span_pointer(index, "security", "authz_decision"))
    return pointers


def _q15_clause_c(span: CanonicalSpan, index: int) -> str | None:
    # Same-span reading of "together with".
    if span.security is None or span.security.privilege_class is not PrivilegeClass.PRIVILEGED:
        return None
    if span.security.authz_decision is not None and span.security.authz_decision.value == "allow":
        return span_pointer(index, "security", "privilege_class")
    if span.status.value == "ok":
        return span_pointer(index, "security", "privilege_class")
    return None


def _q15_clause_d(export: TelemetryExport) -> list[str]:
    pointers: list[str] = []
    for index, span in enumerate(export.spans):
        if span.status_code in _Q15_DENY_CODES:
            pointers.append(span_pointer(index, "status_code"))
    return pointers


def _extract_q15(export: TelemetryExport) -> ExtractedFact:
    pointers = list(_q15_clause_a(export))
    pointers.extend(_q15_clause_b(export))
    for index, span in enumerate(export.spans):
        clause_c = _q15_clause_c(span, index)
        if clause_c is not None:
            pointers.append(clause_c)
    pointers.extend(_q15_clause_d(export))
    if pointers:
        return _answered("Q15", "security_relevant", *pointers)
    return _answered("Q15", "benign", "/spans")


_EXTRACTORS = {
    "Q1": _extract_q1,
    "Q2": _extract_q2,
    "Q3": _extract_q3,
    "Q4": _extract_q4,
    "Q5": _extract_q5,
    "Q6": _extract_q6,
    "Q7": _extract_q7,
    "Q8": _extract_q8,
    "Q9": _extract_q9,
    "Q10": _extract_q10,
    "Q11": _extract_q11,
    "Q12": _extract_q12,
    "Q13": _extract_q13,
    "Q14": _extract_q14,
    "Q15": _extract_q15,
}


def extract_forensic_answers(
    export: TelemetryExport,
    question_ids: Iterable[QuestionId] | None = None,
) -> ForensicExtraction:
    """Infer answers and evidence locations from an export plus question IDs.

    Does not consult applicability, expected answers, or canary inventories.
    """
    export_dump(export)  # reject non-serializable exports early
    requested = tuple(question_ids) if question_ids is not None else QUESTION_IDS
    facts = tuple(_EXTRACTORS[question_id](export) for question_id in requested)
    return ForensicExtraction(facts=facts)
