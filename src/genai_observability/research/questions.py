"""Public R-question definitions. No expected answers or captured excerpts."""

from typing import Literal

ResearchQuestionId = Literal["R1", "R2", "R3", "R4", "R5", "R6", "R7"]

RESEARCH_QUESTION_IDS: tuple[ResearchQuestionId, ...] = (
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
)

R2_SELECTORS: tuple[str, ...] = ("authz.resource", "content.tool_args.note_id")
REDACTION_MARKERS: tuple[str, ...] = (
    "[REDACTED:canary_grammar]",
    "[REDACTED:secret_key]",
)
EXCERPT_CHARS = 32
