from genai_observability.grading.evaluate import DuplicateQuestionIdError
from genai_observability.grading.extract import ExtractedFact, ExtractionStatus, ForensicExtraction
from genai_observability.paths import RESEARCH_FIXTURE_DIR
from genai_observability.research.evaluate import evaluate_research, extract_then_evaluate_research, r4_outcome
from genai_observability.research.extract import extract_research_answers
from genai_observability.research.references import load_research_answers
from genai_observability.research.select import select_references
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import PolicyId
from genai_observability.sources.fixtures import FixtureSource
from genai_observability.transforms import apply_policy
from tests.helpers import export_from_spans, minimal_span, stream_from_spans


def _p1_export(execution_id: str):
    stream = apply_runtime_detectors(FixtureSource(RESEARCH_FIXTURE_DIR).load(execution_id))
    return apply_policy(stream, PolicyId.P1)


def test_select_references_matches_committed_s_and_t_manifests() -> None:
    source = FixtureSource(RESEARCH_FIXTURE_DIR)
    for execution_id, pair_id in (("res-s1", "S"), ("res-s2", "S"), ("res-t1", "T"), ("res-t2", "T")):
        selected = select_references(source.load(execution_id), pair_id)
        committed = load_research_answers(execution_id)
        assert selected.model_dump(exclude_none=True) == committed.model_dump(exclude_none=True)


def test_select_references_rejects_policy_exports() -> None:
    export = _p1_export("res-s1")
    try:
        select_references(export, "S")  # type: ignore[arg-type]
    except TypeError as exc:
        assert "CanonicalEventStream" in str(exc)
    else:
        raise AssertionError("select_references accepted a policy export")


def test_select_and_extract_handle_multiple_tool_calls() -> None:
    stream = stream_from_spans(
        minimal_span(span_id="sp-req", kind="request", name="handle_request"),
        minimal_span(
            span_id="sp-tol-1",
            parent_span_id="sp-req",
            name="get_note",
            kind="tool",
            tool={"name": "get_note", "type": "read"},
            content={"tool_args": {"note_id": "note-a"}},
            authz={"resource": "note-a"},
            security={"authz_decision": "allow"},
        ),
        minimal_span(
            span_id="sp-tol-2",
            parent_span_id="sp-req",
            name="get_note",
            kind="tool",
            tool={"name": "get_note", "type": "read"},
            content={"tool_args": {"note_id": "note-b"}},
            authz={"resource": "note-b"},
            security={"authz_decision": "deny"},
        ),
    )
    selected = select_references(stream, "U")
    assert selected.question("R1").answer == [{"note_id": "note-a"}, {"note_id": "note-b"}]
    assert selected.question("R2").answer == ["note-a", "note-b"]
    assert selected.question("R5").answer == ["allowed", "denied"]
    export = export_from_spans(*stream.spans)
    fact = extract_research_answers(export).fact("R1")
    assert fact.value == [{"note_id": "note-a"}, {"note_id": "note-b"}]


def test_r4_missing_when_dropped_or_redacted_not_no() -> None:
    token = "SYNTH-RETRVL-A11A0001"
    dropped = ExtractedFact(
        question_id="R4",
        status=ExtractionStatus.MISSING,
        value=None,
    )
    assert r4_outcome(dropped, token) == "missing"
    redacted = ExtractedFact(
        question_id="R4",
        status=ExtractionStatus.ANSWERED,
        value={
            "loc1": "Retrieved [REDACTED:canary_grammar] for copy.",
            "loc2": '{"note_id":"[REDACTED:canary_grammar]"}',
        },
    )
    assert r4_outcome(redacted, token) == "missing"
    one_sided = ExtractedFact(
        question_id="R4",
        status=ExtractionStatus.ANSWERED,
        value={"loc1": f"Retrieved {token} only here.", "loc2": '{"note_id":"note-t2"}'},
    )
    assert r4_outcome(one_sided, token) == "no"
    copied = ExtractedFact(
        question_id="R4",
        status=ExtractionStatus.ANSWERED,
        value={"loc1": f"Retrieved {token} for copy.", "loc2": f'{{"note_id":"{token}"}}'},
    )
    assert r4_outcome(copied, token) == "yes"


def test_r4_pair_t_on_p1_is_yes_versus_no() -> None:
    t1 = extract_then_evaluate_research(_p1_export("res-t1"), load_research_answers("res-t1"))[1]
    t2 = extract_then_evaluate_research(_p1_export("res-t2"), load_research_answers("res-t2"))[1]
    assert t1.score("R4").credit == 1
    assert t1.score("R4").extracted_value == "yes"
    assert t2.score("R4").credit == 1
    assert t2.score("R4").extracted_value == "no"


def test_duplicate_research_question_ids_are_rejected() -> None:
    export = _p1_export("res-s1")
    extraction = ForensicExtraction(
        facts=(
            ExtractedFact(question_id="R5", status=ExtractionStatus.ANSWERED, value="denied"),
            ExtractedFact(question_id="R5", status=ExtractionStatus.ANSWERED, value="denied"),
        )
    )
    try:
        evaluate_research(extraction, load_research_answers("res-s1"), export)
    except DuplicateQuestionIdError:
        return
    raise AssertionError("duplicate R ids should be rejected")


def test_omitted_applicable_research_question_scores_zero() -> None:
    export = _p1_export("res-s1")
    extraction = ForensicExtraction(
        facts=(ExtractedFact(question_id="R7", status=ExtractionStatus.MISSING),)
    )
    evaluation = evaluate_research(extraction, load_research_answers("res-s1"), export)
    assert evaluation.score("R1").applicable is True
    assert evaluation.score("R1").credit == 0
