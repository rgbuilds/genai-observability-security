"""Full-study answer manifests and canary inventories. Extraction must not import this."""

from typing import Any, Literal

from pydantic import Field, model_validator

from genai_observability.grading.references import EligibleCanary, RegisteredEdge
from genai_observability.paths import FULL_STUDY_ANSWER_DIR, FULL_STUDY_CANARY_DIR
from genai_observability.schemas.span import _StrictModel

FULL_STUDY_ANSWER_VERSION = "full_study_answer_manifest.v1"
FULL_STUDY_CANARY_VERSION = "canary_inventory.v1"


class FullStudyQuestionReference(_StrictModel):
    id: str = Field(min_length=1)
    applicable: bool
    answer: Any = None
    token: str | None = None
    registered_edges: list[RegisteredEdge] | None = None

    @model_validator(mode="after")
    def applicable_questions_need_an_answer(self) -> "FullStudyQuestionReference":
        if not self.applicable:
            return self
        if self.id == "FS7":
            if self.registered_edges is None:
                raise ValueError("applicable FS7 requires registered_edges")
            return self
        if self.id in {"FS16", "OC1"}:
            if self.answer not in {"yes", "no"}:
                raise ValueError(f"applicable {self.id} requires answer yes or no")
            if not self.token:
                raise ValueError(f"applicable {self.id} requires a private token")
            return self
        if self.answer is None:
            raise ValueError(f"applicable {self.id} requires an answer")
        return self


class FullStudyAnswerManifest(_StrictModel):
    schema_version: Literal["full_study_answer_manifest.v1"] = FULL_STUDY_ANSWER_VERSION
    execution_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    role: Literal["case", "control"]
    source: Literal["scripted", "mocked-capture"]
    intended_family: str = Field(min_length=1)
    questions: list[FullStudyQuestionReference] = Field(min_length=1)

    @model_validator(mode="after")
    def question_ids_are_unique(self) -> "FullStudyAnswerManifest":
        seen: set[str] = set()
        for item in self.questions:
            if item.id in seen:
                raise ValueError(f"duplicate question id: {item.id}")
            seen.add(item.id)
        return self

    def question(self, question_id: str) -> FullStudyQuestionReference:
        for item in self.questions:
            if item.id == question_id:
                return item
        raise KeyError(question_id)


class FullStudyCanaryInventory(_StrictModel):
    schema_version: Literal["canary_inventory.v1"] = FULL_STUDY_CANARY_VERSION
    execution_id: str = Field(min_length=1)
    eligible_canaries: list[EligibleCanary] = Field(default_factory=list)


def load_full_study_answers(execution_id: str) -> FullStudyAnswerManifest:
    path = FULL_STUDY_ANSWER_DIR / f"{execution_id}.json"
    manifest = FullStudyAnswerManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.execution_id != execution_id:
        raise ValueError(f"full-study answer {path} has execution_id={manifest.execution_id!r}")
    return manifest


def load_full_study_canaries(execution_id: str) -> FullStudyCanaryInventory:
    path = FULL_STUDY_CANARY_DIR / f"{execution_id}.json"
    inventory = FullStudyCanaryInventory.model_validate_json(path.read_text(encoding="utf-8"))
    if inventory.execution_id != execution_id:
        raise ValueError(f"full-study canaries {path} has execution_id={inventory.execution_id!r}")
    return inventory
