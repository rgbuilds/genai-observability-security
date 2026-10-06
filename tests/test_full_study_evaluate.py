from genai_observability.full_study.evaluate import extract_then_evaluate_full_study
from genai_observability.full_study.extract import extract_full_study_answers
from genai_observability.full_study.questions import FULL_STUDY_QUESTION_IDS
from genai_observability.full_study.references import FullStudyAnswerManifest, FullStudyQuestionReference
from genai_observability.grading.extract import ExtractionStatus
from tests.helpers import export_from_spans, minimal_span


def _answers(*questions: FullStudyQuestionReference) -> FullStudyAnswerManifest:
    present = {item.id for item in questions}
    filled = list(questions)
    for question_id in FULL_STUDY_QUESTION_IDS:
        if question_id not in present:
            filled.append(FullStudyQuestionReference(id=question_id, applicable=False))
    return FullStudyAnswerManifest(
        execution_id="fs-test",
        pair_id="T1",
        family="F1",
        role="case",
        source="scripted",
        intended_family="F1",
        questions=filled,
    )


def test_ambiguous_tool_names() -> None:
    export = export_from_spans(
        minimal_span(),
        minimal_span(
            span_id="tol-a",
            kind="tool",
            name="get_note",
            parent_span_id="span-0001",
            tool={"name": "get_note", "type": "read"},
        ),
        minimal_span(
            span_id="tol-b",
            kind="tool",
            name="delete_account",
            parent_span_id="span-0001",
            start_time="2026-10-04T22:00:00.200Z",
            end_time="2026-10-04T22:00:00.220Z",
            tool={"name": "delete_account", "type": "action"},
        ),
    )
    fact = extract_full_study_answers(export).fact("FS5")
    assert fact.status is ExtractionStatus.AMBIGUOUS
    answers = _answers(FullStudyQuestionReference(id="FS5", applicable=True, answer="get_note"))
    _, evaluation = extract_then_evaluate_full_study(export, answers)
    assert evaluation.score("FS5").credit == 0


def test_contradictory_allow_deny_is_not_auto_credit() -> None:
    export = export_from_spans(
        minimal_span(),
        minimal_span(
            span_id="tol-a",
            kind="tool",
            name="delete_account",
            parent_span_id="span-0001",
            status_code=200,
            tool={"name": "delete_account", "type": "action"},
            security={"authz_decision": "allow"},
            content={"tool_args": {"note_id": "n1"}},
        ),
        minimal_span(
            span_id="tol-b",
            kind="tool",
            name="delete_account",
            parent_span_id="span-0001",
            start_time="2026-10-04T22:00:00.200Z",
            end_time="2026-10-04T22:00:00.220Z",
            status_code=403,
            tool={"name": "delete_account", "type": "action"},
            security={"authz_decision": "deny"},
            content={"tool_args": {"note_id": "n1"}},
        ),
    )
    fact = extract_full_study_answers(export).fact("FS6")
    assert fact.value == ["allowed", "denied"]
    answers = _answers(FullStudyQuestionReference(id="FS6", applicable=True, answer="allowed"))
    _, evaluation = extract_then_evaluate_full_study(export, answers)
    assert evaluation.score("FS6").credit == 0
