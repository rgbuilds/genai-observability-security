"""Select FS answers from a canonical stream only. Never from a policy export."""

from typing import Any

from genai_observability.full_study.protocol import EXCERPT_CHARS
from genai_observability.full_study.questions import FULL_STUDY_QUESTION_IDS
from genai_observability.full_study.references import FullStudyAnswerManifest, FullStudyQuestionReference
from genai_observability.grading.references import RegisteredEdge
from genai_observability.patterns.library import load_pattern_library
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import (
    AuthzDecision,
    DetectorCategory,
    DetectorPass,
    PrivilegeClass,
    SpanKind,
)
from genai_observability.serialization import canonical_json_text


def _tool_spans(stream: CanonicalEventStream):
    return [span for span in stream.spans if span.kind is SpanKind.TOOL]


def _retrieval_spans(stream: CanonicalEventStream):
    return [span for span in stream.spans if span.kind is SpanKind.RETRIEVAL]


def _model_spans(stream: CanonicalEventStream):
    return [span for span in stream.spans if span.kind is SpanKind.MODEL]


def first_canary_or_excerpt(text: str) -> str:
    match = load_pattern_library().canary_regex().search(text)
    if match:
        return match.group(0)
    return text[:EXCERPT_CHARS]


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return canonical_json_text(value)
    return str(value)


def _maybe_single(values: list[Any]) -> Any:
    if len(values) == 1:
        return values[0]
    return values


def _fs13_value(span) -> str | None:
    if span.authz is not None and span.authz.resource:
        return span.authz.resource
    if span.content is not None and isinstance(span.content.tool_args, dict):
        note_id = span.content.tool_args.get("note_id")
        if isinstance(note_id, str):
            return note_id
    return None


def _fs6_value(span) -> str | None:
    if span.security is not None and span.security.authz_decision is not None:
        return "allowed" if span.security.authz_decision is AuthzDecision.ALLOW else "denied"
    if span.status_code in {401, 403}:
        return "denied"
    if span.status_code == 200:
        return "allowed"
    return None


def _first_retrieved(stream: CanonicalEventStream) -> str | None:
    for span in _retrieval_spans(stream):
        if span.content is not None and span.content.retrieved is not None:
            return span.content.retrieved
    return None


def _fs16_loc2(stream: CanonicalEventStream) -> str | None:
    tools = _tool_spans(stream)
    if tools:
        parts = [
            _json_text(span.content.tool_args)
            for span in tools
            if span.content is not None and span.content.tool_args is not None
        ]
        return "\n".join(parts) if parts else None
    for span in _model_spans(stream):
        if span.content is not None and span.content.output is not None:
            return span.content.output
    return None


def _last_output(stream: CanonicalEventStream) -> str | None:
    last = None
    for span in _model_spans(stream):
        if span.content is not None and span.content.output is not None:
            last = span.content.output
    return last


def _first_output(stream: CanonicalEventStream) -> str | None:
    for span in _model_spans(stream):
        if span.content is not None and span.content.output is not None:
            return span.content.output
    return None


def applicability_from_stream(stream: CanonicalEventStream) -> dict[str, bool]:
    tools = _tool_spans(stream)
    retrievals = _retrieval_spans(stream)
    loc1 = _first_retrieved(stream)
    loc2 = _fs16_loc2(stream)
    last_output = _last_output(stream)
    has_model = any(span.kind is SpanKind.MODEL for span in stream.spans)
    has_trust = any(span.security is not None and span.security.trust_class is not None for span in stream.spans)
    has_privilege = any(
        span.kind is SpanKind.TOOL
        and span.security is not None
        and span.security.privilege_class is not None
        for span in stream.spans
    )
    has_denial = any(
        span.kind is SpanKind.TOOL
        and span.security is not None
        and span.security.denial_reason is not None
        for span in stream.spans
    )
    return {
        "FS1": True,
        "FS2": has_model,
        "FS3": True,
        "FS4": bool(retrievals),
        "FS5": bool(tools),
        "FS6": bool(tools),
        "FS7": True,
        "FS8": has_trust,
        "FS9": has_privilege,
        "FS10": has_denial,
        "FS11": True,
        "FS12": bool(tools),
        "FS13": bool(tools),
        "FS14": loc1 is not None,
        "FS15": _first_output(stream) is not None,
        "FS16": loc1 is not None and loc2 is not None,
        "OC1": loc1 is not None and last_output is not None,
    }


def select_full_study_references(
    stream: CanonicalEventStream,
    spec: dict[str, Any],
) -> FullStudyAnswerManifest:
    if not isinstance(stream, CanonicalEventStream):
        raise TypeError("select_full_study_references accepts CanonicalEventStream only")
    if stream.detector_pass is not DetectorPass.COMPLETED:
        raise ValueError("reference selection requires a detector-completed canonical stream")
    applicable = applicability_from_stream(stream)
    tools = _tool_spans(stream)
    loc1 = _first_retrieved(stream)
    loc2 = _fs16_loc2(stream)
    last_output = _last_output(stream)
    first_output = _first_output(stream)
    r14 = first_canary_or_excerpt(loc1) if loc1 else None
    r15 = first_canary_or_excerpt(first_output) if first_output else None
    token = None
    if loc1:
        match = load_pattern_library().canary_regex().search(loc1)
        token = match.group(0) if match else r14
    fs16_answer = None
    if applicable["FS16"] and token and loc1 and loc2:
        fs16_answer = "yes" if token in loc1 and token in loc2 else "no"
    oc1_answer = None
    oc1_token = token
    if applicable["OC1"] and loc1 and last_output:
        if oc1_token is None:
            oc1_token = first_canary_or_excerpt(loc1)
        oc1_answer = "yes" if oc1_token in loc1 and oc1_token in last_output else "no"
    detector_expected = "yes" if any(
        event.category is DetectorCategory.SENSITIVE_DATA
        for span in stream.spans
        for event in (span.detector_events or [])
    ) else "no"
    model_span = next((span for span in _model_spans(stream)), None)
    fs2 = None
    if model_span is not None:
        fs2 = {"operation": model_span.name}
        if model_span.model is not None and model_span.model.name:
            fs2["name"] = model_span.model.name
    fs9 = None
    if tools and tools[0].security is not None and tools[0].security.privilege_class is not None:
        fs9 = "yes" if tools[0].security.privilege_class is PrivilegeClass.PRIVILEGED else "no"
    fs10 = None
    if tools and tools[0].security is not None and tools[0].security.denial_reason is not None:
        fs10 = tools[0].security.denial_reason.value
    retrieval_ids = [
        span.retrieval.source_id
        for span in _retrieval_spans(stream)
        if span.retrieval is not None and span.retrieval.source_id is not None
    ]
    trust_values = [
        span.security.trust_class.value
        for span in stream.spans
        if span.security is not None and span.security.trust_class is not None
    ]
    answers: dict[str, Any] = {
        "FS1": stream.request_id,
        "FS2": fs2,
        "FS3": "yes" if _retrieval_spans(stream) else "no",
        "FS4": _maybe_single(retrieval_ids) if retrieval_ids else None,
        "FS5": tools[0].tool.name if tools and tools[0].tool is not None else None,
        "FS6": _maybe_single([value for value in (_fs6_value(span) for span in tools) if value]),
        "FS7": None,
        "FS8": _maybe_single(trust_values) if trust_values else None,
        "FS9": fs9,
        "FS10": fs10,
        "FS11": detector_expected,
        "FS12": [
            span.content.tool_args
            for span in tools
            if span.content is not None and span.content.tool_args is not None
        ],
        "FS13": _maybe_single([value for value in (_fs13_value(span) for span in tools) if value]),
        "FS14": r14,
        "FS15": r15,
        "FS16": fs16_answer,
        "OC1": oc1_answer,
    }
    edges = [
        RegisteredEdge(parent=span.parent_span_id, child=span.span_id)
        for span in stream.spans
        if span.parent_span_id is not None
    ]
    questions = []
    for question_id in FULL_STUDY_QUESTION_IDS:
        token_for = None
        if question_id == "FS16" and applicable["FS16"]:
            token_for = token
        if question_id == "OC1" and applicable["OC1"]:
            token_for = oc1_token
        questions.append(
            FullStudyQuestionReference(
                id=question_id,
                applicable=applicable[question_id],
                answer=answers[question_id] if applicable[question_id] else None,
                token=token_for,
                registered_edges=edges if question_id == "FS7" else None,
            )
        )
    return FullStudyAnswerManifest(
        execution_id=stream.scenario_id,
        pair_id=spec["pair_id"],
        family=spec["family"],
        role=spec["role"],
        source=spec["source"],
        intended_family=spec["intended_family"],
        questions=questions,
    )
