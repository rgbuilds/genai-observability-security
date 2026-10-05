"""Deterministic reference selection from a canonical stream only.

Must not accept a policy export. Choose excerpts and span pairs without
viewing transformed telemetry.
"""

from typing import Any

from genai_observability.grading.references import RegisteredEdge
from genai_observability.patterns.library import load_pattern_library
from genai_observability.research.questions import EXCERPT_CHARS, RESEARCH_QUESTION_IDS
from genai_observability.research.references import ResearchAnswerManifest, ResearchQuestionReference
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import AuthzDecision, SpanKind
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


def _r2_value(span) -> str | None:
    if span.authz is not None and span.authz.resource:
        return span.authz.resource
    if span.content is not None and isinstance(span.content.tool_args, dict):
        note_id = span.content.tool_args.get("note_id")
        if isinstance(note_id, str):
            return note_id
    return None


def _r5_value(span) -> str | None:
    if span.security is not None and span.security.authz_decision is not None:
        return "allowed" if span.security.authz_decision is AuthzDecision.ALLOW else "denied"
    if span.status_code in {401, 403}:
        return "denied"
    if span.status_code == 200:
        return "allowed"
    return None


def _maybe_single(values: list[Any]) -> Any:
    if len(values) == 1:
        return values[0]
    return values


def _r4_locations(stream: CanonicalEventStream) -> tuple[str | None, str | None]:
    loc1 = None
    for span in _retrieval_spans(stream):
        if span.content is not None and span.content.retrieved is not None:
            loc1 = span.content.retrieved
            break
    loc2 = None
    tools = _tool_spans(stream)
    if tools:
        parts = [
            _json_text(span.content.tool_args)
            for span in tools
            if span.content is not None and span.content.tool_args is not None
        ]
        if parts:
            loc2 = "\n".join(parts)
    else:
        for span in _model_spans(stream):
            if span.content is not None and span.content.output is not None:
                loc2 = span.content.output
                break
    return loc1, loc2


def applicability_from_stream(stream: CanonicalEventStream) -> dict[str, bool]:
    tools = _tool_spans(stream)
    retrievals = _retrieval_spans(stream)
    loc1, loc2 = _r4_locations(stream)
    has_model_output = any(
        span.content is not None and span.content.output is not None for span in _model_spans(stream)
    )
    has_r4_token = bool(loc1)
    return {
        "R1": bool(tools),
        "R2": bool(tools),
        "R3": bool(retrievals),
        "R4": bool(retrievals) and loc2 is not None and has_r4_token,
        "R5": bool(tools),
        "R6": has_model_output,
        "R7": True,
    }


def select_references(stream: CanonicalEventStream, pair_id: str) -> ResearchAnswerManifest:
    """Build the private answer key from the canonical stream (never an export)."""
    if not isinstance(stream, CanonicalEventStream):
        raise TypeError("select_references accepts CanonicalEventStream only, not a policy export")
    applicable = applicability_from_stream(stream)
    tools = _tool_spans(stream)
    models = _model_spans(stream)
    loc1, loc2 = _r4_locations(stream)

    r1_args = [
        span.content.tool_args
        for span in tools
        if span.content is not None and span.content.tool_args is not None
    ]
    r2_values = [value for value in (_r2_value(span) for span in tools) if value is not None]
    r5_values = [value for value in (_r5_value(span) for span in tools) if value is not None]
    r3_excerpt = first_canary_or_excerpt(loc1) if loc1 else None
    r4_token = None
    r4_answer = None
    if applicable["R4"] and loc1 and loc2:
        match = load_pattern_library().canary_regex().search(loc1)
        r4_token = match.group(0) if match else r3_excerpt
        r4_answer = "yes" if r4_token and r4_token in loc1 and r4_token in loc2 else "no"
    r6_text = None
    for span in models:
        if span.content is not None and span.content.output is not None:
            r6_text = span.content.output
            break
    r6_excerpt = first_canary_or_excerpt(r6_text) if r6_text else None
    edges = [
        RegisteredEdge(parent=span.parent_span_id, child=span.span_id)
        for span in stream.spans
        if span.parent_span_id is not None
    ]

    answers: dict[str, Any] = {
        "R1": r1_args,
        "R2": _maybe_single(r2_values),
        "R3": r3_excerpt,
        "R4": r4_answer,
        "R5": _maybe_single(r5_values),
        "R6": r6_excerpt,
        "R7": None,
    }
    questions = []
    for question_id in RESEARCH_QUESTION_IDS:
        questions.append(
            ResearchQuestionReference(
                id=question_id,
                applicable=applicable[question_id],
                answer=answers[question_id] if applicable[question_id] else None,
                token=r4_token if question_id == "R4" and applicable["R4"] else None,
                registered_edges=edges if question_id == "R7" else None,
            )
        )
    return ResearchAnswerManifest(
        execution_id=stream.scenario_id,
        pair_id=pair_id,
        questions=questions,
    )
