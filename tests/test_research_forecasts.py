from genai_observability.paths import RESEARCH_FIXTURE_DIR
from genai_observability.research.evaluate import extract_then_evaluate_research
from genai_observability.research.references import load_research_answers
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import PolicyId
from genai_observability.sources.fixtures import FixtureSource
from genai_observability.transforms import apply_policy

# Retention forecasts from RESEARCH_FEASIBILITY_PLAN.md sections 4.4–6.2.
# Matching these cells validates the R-graders. It is not research evidence.

_S_FORECAST = {
    PolicyId.P0: {"R1": 0, "R2": 0, "R5": 1, "R6": 0, "R7": 1},
    PolicyId.P1: {"R1": 1, "R2": 1, "R5": 1, "R6": 1, "R7": 1},
    PolicyId.P2: {"R1": 1, "R2": 1, "R5": 1, "R6": 1, "R7": 1},
    PolicyId.P3: {"R1": 0, "R2": 0, "R5": 1, "R6": 0, "R7": 1},
}

_T_FORECAST = {
    "res-t1": {
        PolicyId.P0: {"R3": 0, "R4": 0, "R7": 1},
        PolicyId.P1: {"R3": 1, "R4": 1, "R7": 1},
        PolicyId.P2: {"R3": 0, "R4": 0, "R7": 1},
        PolicyId.P3: {"R3": 0, "R4": 0, "R7": 1},
    },
    "res-t2": {
        PolicyId.P0: {"R3": 0, "R4": 0, "R7": 1},
        PolicyId.P1: {"R3": 1, "R4": 1, "R7": 1},
        PolicyId.P2: {"R3": 0, "R4": 0, "R7": 1},
        PolicyId.P3: {"R3": 0, "R4": 0, "R7": 1},
    },
}


def _evaluate(execution_id: str, policy: PolicyId):
    stream = apply_runtime_detectors(FixtureSource(RESEARCH_FIXTURE_DIR).load(execution_id))
    export = apply_policy(stream, policy)
    return extract_then_evaluate_research(export, load_research_answers(execution_id))[1]


def test_pair_s_retention_forecasts() -> None:
    for execution_id in ("res-s1", "res-s2"):
        for policy, expected in _S_FORECAST.items():
            evaluation = _evaluate(execution_id, policy)
            for question_id, credit in expected.items():
                score = evaluation.score(question_id)
                assert score.applicable is True
                assert score.credit == credit, (execution_id, policy, question_id, score)


def test_pair_t_r4_is_missing_on_drop_or_redaction() -> None:
    for execution_id, policies in _T_FORECAST.items():
        for policy, expected in policies.items():
            evaluation = _evaluate(execution_id, policy)
            for question_id, credit in expected.items():
                score = evaluation.score(question_id)
                assert score.applicable is True
                assert score.credit == credit, (execution_id, policy, question_id, score)
            if policy is not PolicyId.P1:
                assert evaluation.score("R4").extracted_status == "missing"
                assert evaluation.score("R4").extracted_value == "missing"


def test_pair_s_r5_differs_when_both_members_are_correct() -> None:
    deny = _evaluate("res-s1", PolicyId.P0)
    allow = _evaluate("res-s2", PolicyId.P0)
    assert deny.score("R5").credit == 1
    assert allow.score("R5").credit == 1
    assert deny.score("R5").extracted_value != allow.score("R5").extracted_value
