"""Spec section 5/7/9 score forecasts for implementation comparison only.

Graders do not import this module.
"""

from genai_observability.grading.questions import QUESTION_IDS
from genai_observability.schemas.enums import PolicyId

YES = "yes"
MISSING = "missing/0"
INCORRECT = "incorrect"

ELIGIBLE_SECURITY_EXECUTIONS = ("exec-11", "exec-21", "exec-31", "exec-51")
ZERO_CANARY_EXECUTIONS = (
    "exec-12",
    "exec-22",
    "exec-32",
    "exec-41",
    "exec-42",
    "exec-52",
)

PREDICTED_EXPOSURE = {
    "exec-11": {PolicyId.P0: "0/1", PolicyId.P1: "1/1", PolicyId.P2: "0/1", PolicyId.P3: "0/1"},
    "exec-21": {PolicyId.P0: "0/1", PolicyId.P1: "1/1", PolicyId.P2: "0/1", PolicyId.P3: "0/1"},
    "exec-31": {PolicyId.P0: "0/1", PolicyId.P1: "1/1", PolicyId.P2: "0/1", PolicyId.P3: "0/1"},
    "exec-51": {PolicyId.P0: "0/1", PolicyId.P1: "1/1", PolicyId.P2: "0/1", PolicyId.P3: "0/1"},
}

PREDICTED_Q15_DISTINGUISHABLE = {
    "A": {PolicyId.P0: False, PolicyId.P1: True, PolicyId.P2: True, PolicyId.P3: True},
    "B": {PolicyId.P0: False, PolicyId.P1: True, PolicyId.P2: True, PolicyId.P3: True},
    "C": {PolicyId.P0: True, PolicyId.P1: True, PolicyId.P2: True, PolicyId.P3: True},
    "D": {PolicyId.P0: False, PolicyId.P1: False, PolicyId.P2: False, PolicyId.P3: True},
    "E": {PolicyId.P0: False, PolicyId.P1: True, PolicyId.P2: True, PolicyId.P3: True},
}

_ALL_YES = {policy: YES for policy in PolicyId}
_P3_ONLY = {PolicyId.P0: MISSING, PolicyId.P1: MISSING, PolicyId.P2: MISSING, PolicyId.P3: YES}
_DETECTOR_RETAINED = {PolicyId.P0: MISSING, PolicyId.P1: YES, PolicyId.P2: YES, PolicyId.P3: YES}
_Q4 = {PolicyId.P0: MISSING, PolicyId.P1: YES, PolicyId.P2: YES, PolicyId.P3: YES}
_Q15_F1 = {PolicyId.P0: INCORRECT, PolicyId.P1: YES, PolicyId.P2: YES, PolicyId.P3: YES}
_Q15_F3 = _ALL_YES
_Q15_F4 = {PolicyId.P0: INCORRECT, PolicyId.P1: INCORRECT, PolicyId.P2: INCORRECT, PolicyId.P3: YES}


def _tool_questions(*, q15: dict[PolicyId, str], q12: dict[PolicyId, str], q13: dict[PolicyId, str] | None) -> dict[str, dict[PolicyId, str] | None]:
    return {
        "Q1": _ALL_YES,
        "Q2": _P3_ONLY,
        "Q3": _ALL_YES,
        "Q4": None,
        "Q5": _ALL_YES,
        "Q6": _ALL_YES,
        "Q7": _ALL_YES,
        "Q8": _P3_ONLY,
        "Q9": _P3_ONLY,
        "Q10": _ALL_YES,
        "Q11": _P3_ONLY,
        "Q12": q12,
        "Q13": q13,
        "Q14": _ALL_YES,
        "Q15": q15,
    }


FORECASTS: dict[str, dict[str, dict[PolicyId, str] | None]] = {
    "exec-11": _tool_questions(q15=_Q15_F1, q12=_DETECTOR_RETAINED, q13=_DETECTOR_RETAINED),
    "exec-12": _tool_questions(q15=_ALL_YES, q12=_DETECTOR_RETAINED, q13=None),
    "exec-21": {
        **_tool_questions(q15=_Q15_F1, q12=_DETECTOR_RETAINED, q13=_DETECTOR_RETAINED),
        "Q3": _ALL_YES,
        "Q4": _Q4,
        "Q13": {PolicyId.P0: MISSING, PolicyId.P1: YES, PolicyId.P2: YES, PolicyId.P3: YES},
    },
    "exec-22": {
        **_tool_questions(q15=_ALL_YES, q12=_DETECTOR_RETAINED, q13=None),
        "Q3": _ALL_YES,
        "Q4": _Q4,
    },
    "exec-31": _tool_questions(q15=_Q15_F3, q12=_DETECTOR_RETAINED, q13=_DETECTOR_RETAINED),
    "exec-32": _tool_questions(q15=_ALL_YES, q12=_DETECTOR_RETAINED, q13=None),
    "exec-41": _tool_questions(q15=_Q15_F4, q12=_DETECTOR_RETAINED, q13=None),
    "exec-42": _tool_questions(q15=_ALL_YES, q12=_DETECTOR_RETAINED, q13=None),
    "exec-51": {
        "Q1": _ALL_YES,
        "Q2": _P3_ONLY,
        "Q3": _ALL_YES,
        "Q4": None,
        "Q5": _ALL_YES,
        "Q6": _ALL_YES,
        "Q7": None,
        "Q8": None,
        "Q9": None,
        "Q10": None,
        "Q11": None,
        "Q12": _DETECTOR_RETAINED,
        "Q13": _DETECTOR_RETAINED,
        "Q14": _ALL_YES,
        "Q15": _Q15_F1,
    },
    "exec-52": {
        "Q1": _ALL_YES,
        "Q2": _P3_ONLY,
        "Q3": _ALL_YES,
        "Q4": None,
        "Q5": _ALL_YES,
        "Q6": _ALL_YES,
        "Q7": None,
        "Q8": None,
        "Q9": None,
        "Q10": None,
        "Q11": None,
        "Q12": _DETECTOR_RETAINED,
        "Q13": None,
        "Q14": _ALL_YES,
        "Q15": _ALL_YES,
    },
}


def predicted_forecast(execution_id: str, policy_id: PolicyId, question_id: str) -> str | None:
    row = FORECASTS[execution_id][question_id]
    if row is None:
        return None
    return row[policy_id]


def predicted_applicable(execution_id: str, question_id: str) -> bool:
    return FORECASTS[execution_id][question_id] is not None


def applicable_denominator(execution_id: str) -> int:
    return sum(1 for question_id in QUESTION_IDS if predicted_applicable(execution_id, question_id))
