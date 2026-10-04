import pytest
from pydantic import ValidationError

from genai_observability.grading.evaluate import (
    DuplicateQuestionIdError,
    evaluate_forensic,
    extract_then_evaluate,
    pair_distinguishable,
)
from genai_observability.grading.references import AnswerManifest
from genai_observability.grading.extract import (
    EvidenceLocation,
    ExtractedFact,
    ExtractionStatus,
    ForensicExtraction,
    extract_forensic_answers,
)
from genai_observability.grading.references import load_answer_manifest
from genai_observability.schemas.enums import PolicyId, SpanKind
from genai_observability.transforms.apply import opaque_identifier
from tests.helpers import export_from_spans, minimal_span


def test_q13_applicability_comes_from_the_execution_reference() -> None:
    applicable = load_answer_manifest("exec-11")
    not_applicable = load_answer_manifest("exec-41")
    missing_detector = export_from_spans(minimal_span(), policy_id=PolicyId.P0, request_id="req-11")
    retained_empty = export_from_spans(
        minimal_span(detector_events=[]),
        policy_id=PolicyId.P1,
        request_id="req-41",
    )

    missing_eval = extract_then_evaluate(missing_detector, applicable)[1]
    empty_eval = extract_then_evaluate(retained_empty, not_applicable)[1]

    assert missing_eval.score("Q13").applicable is True
    assert missing_eval.score("Q13").credit == 0
    assert empty_eval.score("Q13").applicable is False
    assert empty_eval.score("Q13").credit is None


def test_q13_extracted_stage_is_ignored_when_reference_says_not_applicable() -> None:
    answers = load_answer_manifest("exec-41")
    export = export_from_spans(minimal_span(detector_events=[]), request_id="req-41")
    planted = ForensicExtraction(
        facts=(
            ExtractedFact(
                question_id="Q13",
                status=ExtractionStatus.ANSWERED,
                value="user_input",
                evidence=(EvidenceLocation(pointer="/spans/0/detector_events"),),
            ),
        )
    )
    evaluation = evaluate_forensic(planted, answers, export)
    assert evaluation.score("Q13").applicable is False
    assert evaluation.score("Q13").credit is None


def test_applicability_is_identical_across_policies() -> None:
    answers = load_answer_manifest("exec-11")
    p0 = export_from_spans(minimal_span(), policy_id=PolicyId.P0, request_id="req-11")
    p1 = export_from_spans(
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
        policy_id=PolicyId.P1,
        request_id="req-11",
    )
    flags_p0 = [score.applicable for score in extract_then_evaluate(p0, answers)[1].scores]
    flags_p1 = [score.applicable for score in extract_then_evaluate(p1, answers)[1].scores]
    assert flags_p0 == flags_p1
    assert answers.question("Q13").applicable is True


def test_q4_accepts_opaque_source_id_matching_the_registered_identifier() -> None:
    answers = load_answer_manifest("exec-21")
    export = export_from_spans(
        minimal_span(
            kind=SpanKind.RETRIEVAL,
            name="retrieve_notes",
            retrieval={"source_id": opaque_identifier("doc-2100")},
        ),
        request_id="req-21",
    )
    extraction = extract_forensic_answers(export)
    evaluation = evaluate_forensic(extraction, answers, export)
    assert extraction.fact("Q4").value == [opaque_identifier("doc-2100")]
    assert evaluation.score("Q4").credit == 1


def test_q14_credits_registered_edges_as_a_subset() -> None:
    answers = load_answer_manifest("exec-51")
    extra = export_from_spans(
        minimal_span(span_id="sp-51-req", parent_span_id=None),
        minimal_span(
            span_id="sp-51-mdl",
            parent_span_id="sp-51-req",
            kind=SpanKind.MODEL,
            name="chat.completion",
            model={"provider": "mock", "name": "fixture-model"},
        ),
        minimal_span(span_id="sp-51-extra", parent_span_id="sp-51-req"),
        request_id="req-51",
    )
    missing = export_from_spans(
        minimal_span(span_id="sp-51-req", parent_span_id=None),
        request_id="req-51",
    )
    extra_eval = extract_then_evaluate(extra, answers)[1]
    missing_eval = extract_then_evaluate(missing, answers)[1]
    assert extra_eval.score("Q14").credit == 1
    assert missing_eval.score("Q14").credit == 0


def test_credit_requires_evidence_location_inside_the_export() -> None:
    answers = load_answer_manifest("exec-12")
    export = export_from_spans(minimal_span(), request_id="req-12")
    extraction = ForensicExtraction(
        facts=(
            ExtractedFact(
                question_id="Q1",
                status=ExtractionStatus.ANSWERED,
                value="req-12",
                evidence=(EvidenceLocation(pointer="/not_a_real_field"),),
            ),
        )
    )
    evaluation = evaluate_forensic(extraction, answers, export)
    assert evaluation.score("Q1").credit == 0


def test_coverage_uses_reference_questions_not_extracted_subset() -> None:
    answers = load_answer_manifest("exec-11")
    export = export_from_spans(minimal_span(), request_id="req-11")
    extraction = ForensicExtraction(
        facts=(
            ExtractedFact(
                question_id="Q1",
                status=ExtractionStatus.ANSWERED,
                value="req-11",
                evidence=(EvidenceLocation(pointer="/request_id"),),
            ),
        )
    )
    evaluation = evaluate_forensic(extraction, answers, export)
    applicable = [score for score in evaluation.scores if score.applicable]
    assert len(evaluation.scores) == len(answers.questions)
    assert len(applicable) == 14
    assert evaluation.score("Q1").credit == 1
    assert evaluation.score("Q3").credit == 0
    assert evaluation.score("Q3").extracted_status == "missing"
    assert evaluation.coverage() == 1 / 14


def test_duplicate_extracted_question_ids_are_rejected() -> None:
    answers = load_answer_manifest("exec-12")
    export = export_from_spans(minimal_span(), request_id="req-12")
    fact = ExtractedFact(
        question_id="Q1",
        status=ExtractionStatus.ANSWERED,
        value="req-12",
        evidence=(EvidenceLocation(pointer="/request_id"),),
    )
    with pytest.raises(DuplicateQuestionIdError, match="Q1"):
        evaluate_forensic(ForensicExtraction(facts=(fact, fact)), answers, export)


def test_answer_manifest_rejects_duplicate_question_ids() -> None:
    payload = load_answer_manifest("exec-12").model_dump(mode="json")
    payload["questions"] = payload["questions"] + [payload["questions"][0]]
    with pytest.raises(ValidationError, match="duplicate question id"):
        AnswerManifest.model_validate(payload)


def test_pair_distinguishable_requires_both_correct_and_different() -> None:
    security_answers = load_answer_manifest("exec-11")
    control_answers = load_answer_manifest("exec-12")
    security_export = export_from_spans(
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
    control_export = export_from_spans(minimal_span(detector_events=[]), request_id="req-12")
    same_export = export_from_spans(minimal_span(detector_events=[]), request_id="req-11")

    security_eval = extract_then_evaluate(security_export, security_answers)[1]
    control_eval = extract_then_evaluate(control_export, control_answers)[1]
    same_eval = extract_then_evaluate(same_export, security_answers)[1]

    assert pair_distinguishable(security_eval, control_eval) is True
    assert pair_distinguishable(same_eval, control_eval) is False
