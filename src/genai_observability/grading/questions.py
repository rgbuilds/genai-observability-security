"""Frozen question definitions. No answers, applicability, or reference I/O."""

from typing import Literal

QuestionId = Literal[
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "Q5",
    "Q6",
    "Q7",
    "Q8",
    "Q9",
    "Q10",
    "Q11",
    "Q12",
    "Q13",
    "Q14",
    "Q15",
]

QUESTION_IDS: tuple[QuestionId, ...] = (
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "Q5",
    "Q6",
    "Q7",
    "Q8",
    "Q9",
    "Q10",
    "Q11",
    "Q12",
    "Q13",
    "Q14",
    "Q15",
)

QUESTION_PROMPTS: dict[QuestionId, str] = {
    "Q1": "Which request initiated the trace?",
    "Q2": "Was the relevant input trusted or untrusted?",
    "Q3": "Did retrieval occur?",
    "Q4": "Which retrieval source/document was involved?",
    "Q5": "Which model operation occurred?",
    "Q6": "Was a tool requested?",
    "Q7": "Which tool was requested?",
    "Q8": "Was the tool privileged?",
    "Q9": "Was the principal authorized?",
    "Q10": "Was the action allowed or denied?",
    "Q11": "Which broad denial/failure reason applied?",
    "Q12": "Did a sensitive-data event occur?",
    "Q13": "At which stage did it occur?",
    "Q14": "Can the parent/child causal sequence be reconstructed?",
    "Q15": "Can a benign execution be distinguished from its security-relevant variant?",
}
