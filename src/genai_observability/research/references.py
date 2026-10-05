"""Private research answer manifests. Extraction must not import this module."""

from typing import Any, Literal

from pydantic import Field, model_validator

from genai_observability.grading.references import RegisteredEdge
from genai_observability.paths import RESEARCH_ANSWER_DIR
from genai_observability.schemas.span import _StrictModel

RESEARCH_ANSWER_MANIFEST_VERSION = "research_answer_manifest.v1"

RESEARCH_EXECUTION_IDS: tuple[str, ...] = ("res-s1", "res-s2", "res-t1", "res-t2")
RESEARCH_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("S", "res-s1", "res-s2"),
    ("T", "res-t1", "res-t2"),
)


class ResearchQuestionReference(_StrictModel):
    id: str = Field(min_length=1)
    applicable: bool
    answer: Any = None
    token: str | None = None
    registered_edges: list[RegisteredEdge] | None = None

    @model_validator(mode="after")
    def applicable_questions_need_an_answer(self) -> "ResearchQuestionReference":
        if not self.applicable:
            return self
        if self.id == "R7":
            if not self.registered_edges:
                raise ValueError("applicable R7 requires registered_edges")
            return self
        if self.id == "R4":
            if self.answer not in {"yes", "no"}:
                raise ValueError("applicable R4 requires answer yes or no")
            if not self.token:
                raise ValueError("applicable R4 requires a private token")
            return self
        if self.answer is None:
            raise ValueError(f"applicable {self.id} requires an answer")
        return self


class ResearchAnswerManifest(_StrictModel):
    schema_version: Literal["research_answer_manifest.v1"] = RESEARCH_ANSWER_MANIFEST_VERSION
    execution_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    questions: list[ResearchQuestionReference] = Field(min_length=1)

    @model_validator(mode="after")
    def question_ids_are_unique(self) -> "ResearchAnswerManifest":
        seen: set[str] = set()
        for item in self.questions:
            if item.id in seen:
                raise ValueError(f"duplicate question id: {item.id}")
            seen.add(item.id)
        return self

    def question(self, question_id: str) -> ResearchQuestionReference:
        for item in self.questions:
            if item.id == question_id:
                return item
        raise KeyError(question_id)


def load_research_answers(execution_id: str) -> ResearchAnswerManifest:
    path = RESEARCH_ANSWER_DIR / f"{execution_id}.json"
    manifest = ResearchAnswerManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.execution_id != execution_id:
        raise ValueError(
            f"research answer manifest {path} has execution_id={manifest.execution_id!r}"
        )
    return manifest
