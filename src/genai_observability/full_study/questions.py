"""Public FS question definitions. No expected answers or captured excerpts."""

from typing import Literal

FullStudyQuestionId = Literal[
    "FS1",
    "FS2",
    "FS3",
    "FS4",
    "FS5",
    "FS6",
    "FS7",
    "FS8",
    "FS9",
    "FS10",
    "FS11",
    "FS12",
    "FS13",
    "FS14",
    "FS15",
    "FS16",
    "OC1",
]

FULL_STUDY_QUESTION_IDS: tuple[FullStudyQuestionId, ...] = (
    "FS1",
    "FS2",
    "FS3",
    "FS4",
    "FS5",
    "FS6",
    "FS7",
    "FS8",
    "FS9",
    "FS10",
    "FS11",
    "FS12",
    "FS13",
    "FS14",
    "FS15",
    "FS16",
    "OC1",
)

QUESTION_CATEGORY: dict[str, str] = {
    "FS1": "operational",
    "FS2": "operational",
    "FS3": "operational",
    "FS4": "operational",
    "FS5": "operational",
    "FS6": "operational",
    "FS7": "operational",
    "FS8": "security",
    "FS9": "security",
    "FS10": "security",
    "FS11": "security",
    "FS12": "content",
    "FS13": "content",
    "FS14": "content",
    "FS15": "content",
    "FS16": "content",
    "OC1": "content",
}

PRIOR_MAPPING: dict[str, str] = {
    "FS1": "Q1",
    "FS2": "Q5",
    "FS3": "Q3",
    "FS4": "Q4",
    "FS5": "Q7",
    "FS6": "R5/Q10",
    "FS7": "R7/Q14",
    "FS8": "Q2",
    "FS9": "Q8",
    "FS10": "Q11",
    "FS11": "Q12",
    "FS12": "R1",
    "FS13": "R2",
    "FS14": "R3",
    "FS15": "R6",
    "FS16": "R4",
    "OC1": "new",
}

FS13_SELECTORS: tuple[str, ...] = ("authz.resource", "content.tool_args.note_id")
CO_OCCURRENCE_IDS = frozenset({"FS16", "OC1"})
