from genai_observability.grading.extract import ExtractionStatus, extract_forensic_answers
from genai_observability.schemas.enums import PolicyId, SpanKind
from tests.helpers import export_from_spans, minimal_span


def test_q12_and_q13_distinguish_omitted_empty_and_populated_detector_events() -> None:
    omitted = export_from_spans(minimal_span(), policy_id=PolicyId.P0)
    empty = export_from_spans(minimal_span(detector_events=[]))
    populated = export_from_spans(
        minimal_span(
            detector_events=[
                {
                    "detector_id": "patternlib.v1.canary_grammar",
                    "category": "sensitive_data",
                    "stage": "user_input",
                    "match_class": "canary_grammar",
                }
            ]
        )
    )

    omitted_x = extract_forensic_answers(omitted)
    empty_x = extract_forensic_answers(empty)
    populated_x = extract_forensic_answers(populated)

    assert omitted_x.fact("Q12").status is ExtractionStatus.MISSING
    assert omitted_x.fact("Q13").status is ExtractionStatus.MISSING
    assert empty_x.fact("Q12").status is ExtractionStatus.ANSWERED
    assert empty_x.fact("Q12").value == "no"
    assert empty_x.fact("Q13").status is ExtractionStatus.MISSING
    assert populated_x.fact("Q12").value == "yes"
    assert populated_x.fact("Q13").value == "user_input"


def test_q14_extracts_parent_child_edges_not_timestamp_order() -> None:
    export = export_from_spans(
        minimal_span(span_id="child-b", parent_span_id="root", start_time="2026-10-04T22:00:00.200Z"),
        minimal_span(
            span_id="child-a",
            parent_span_id="root",
            start_time="2026-10-04T22:00:00.010Z",
            kind=SpanKind.MODEL,
            name="chat.completion",
        ),
        minimal_span(span_id="root", parent_span_id=None, kind=SpanKind.REQUEST),
    )
    fact = extract_forensic_answers(export).fact("Q14")
    assert fact.status is ExtractionStatus.ANSWERED
    assert fact.value == [
        {"parent": "root", "child": "child-a"},
        {"parent": "root", "child": "child-b"},
    ]


def test_q15_uses_frozen_operational_rule_not_identifiers() -> None:
    detector = export_from_spans(
        minimal_span(
            detector_events=[
                {
                    "detector_id": "patternlib.v1.canary_grammar",
                    "category": "sensitive_data",
                    "stage": "user_input",
                    "match_class": "canary_grammar",
                }
            ]
        ),
        request_id="req-11",
    )
    denied = export_from_spans(
        minimal_span(
            kind=SpanKind.TOOL,
            name="get_note",
            status="error",
            status_code=403,
            tool={"name": "get_note"},
            security={"authz_decision": "deny"},
        ),
        request_id="req-31",
    )
    privileged = export_from_spans(
        minimal_span(
            kind=SpanKind.TOOL,
            name="delete_account",
            tool={"name": "delete_account"},
            security={"privilege_class": "privileged", "authz_decision": "allow"},
        ),
        request_id="req-41",
    )
    benign = export_from_spans(
        minimal_span(detector_events=[], status_code=200),
        request_id="req-12",
    )

    assert extract_forensic_answers(detector).fact("Q15").value == "security_relevant"
    assert extract_forensic_answers(denied).fact("Q15").value == "security_relevant"
    assert extract_forensic_answers(privileged).fact("Q15").value == "security_relevant"
    assert extract_forensic_answers(benign).fact("Q15").value == "benign"


def test_q15_clause_c_is_same_span() -> None:
    export = export_from_spans(
        minimal_span(span_id="req", status="ok", status_code=200),
        minimal_span(
            span_id="tol",
            kind=SpanKind.TOOL,
            name="delete_account",
            status="error",
            status_code=500,
            tool={"name": "delete_account"},
            security={"privilege_class": "privileged"},
        ),
    )
    assert extract_forensic_answers(export).fact("Q15").value == "benign"


def test_q10_uses_tool_status_code_not_request_ok() -> None:
    export = export_from_spans(
        minimal_span(span_id="req", status="ok", status_code=200),
        minimal_span(
            span_id="tol",
            kind=SpanKind.TOOL,
            name="delete_account",
            status="error",
            status_code=403,
            tool={"name": "delete_account"},
        ),
    )
    assert extract_forensic_answers(export).fact("Q10").value == "denied"


def test_q4_extracts_exported_identifiers_only() -> None:
    export = export_from_spans(
        minimal_span(
            kind=SpanKind.RETRIEVAL,
            name="retrieve_notes",
            retrieval={"source_id": "sha256:opaque", "hash": "sha256:" + ("c" * 64)},
        )
    )
    fact = extract_forensic_answers(export).fact("Q4")
    assert fact.value == ["sha256:opaque", "sha256:" + ("c" * 64)]


def test_q2_q8_q9_q11_do_not_infer_from_content_or_tool_name() -> None:
    export = export_from_spans(
        minimal_span(
            kind=SpanKind.TOOL,
            name="delete_account",
            tool={"name": "delete_account"},
            content={"tool_args": {"note_id": "note-41"}},
            detector_events=[],
        )
    )
    extraction = extract_forensic_answers(export)
    assert extraction.fact("Q2").status is ExtractionStatus.MISSING
    assert extraction.fact("Q8").status is ExtractionStatus.MISSING
    assert extraction.fact("Q9").status is ExtractionStatus.MISSING
    assert extraction.fact("Q11").status is ExtractionStatus.MISSING
    assert extraction.fact("Q7").value == "delete_account"
