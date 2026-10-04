from typing import Any, Literal

from pydantic import Field, model_validator

from genai_observability.paths import REFERENCE_ANSWER_DIR, REFERENCE_CANARY_DIR
from genai_observability.schemas.span import _StrictModel

CANARY_INVENTORY_VERSION = "canary_inventory.v1"
ANSWER_MANIFEST_VERSION = "answer_manifest.v1"

CanaryLocation = Literal["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
Q15Label = Literal["benign", "security_relevant"]

PILOT_EXECUTION_IDS: tuple[str, ...] = (
    "exec-11",
    "exec-12",
    "exec-21",
    "exec-22",
    "exec-31",
    "exec-32",
    "exec-41",
    "exec-42",
    "exec-51",
    "exec-52",
)

PILOT_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("A", "exec-11", "exec-12"),
    ("B", "exec-21", "exec-22"),
    ("C", "exec-31", "exec-32"),
    ("D", "exec-41", "exec-42"),
    ("E", "exec-51", "exec-52"),
)


class EligibleCanary(_StrictModel):
    canary_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    location: CanaryLocation
    payload_field: str = Field(min_length=1)
    eligible: bool


class CanaryInventory(_StrictModel):
    schema_version: Literal["canary_inventory.v1"] = CANARY_INVENTORY_VERSION
    execution_id: str = Field(min_length=1)
    eligible_canaries: list[EligibleCanary] = Field(default_factory=list)


class RegisteredEdge(_StrictModel):
    parent: str = Field(min_length=1)
    child: str = Field(min_length=1)


class QuestionReference(_StrictModel):
    id: str = Field(min_length=1)
    applicable: bool
    answer: Any = None
    registered_edges: list[RegisteredEdge] | None = None

    @model_validator(mode="after")
    def applicable_questions_need_an_answer(self) -> "QuestionReference":
        if self.applicable and self.id == "Q14":
            if not self.registered_edges:
                raise ValueError("applicable Q14 requires registered_edges")
            return self
        if self.applicable and self.answer is None:
            raise ValueError(f"applicable {self.id} requires an answer")
        return self


class AnswerManifest(_StrictModel):
    schema_version: Literal["answer_manifest.v1"] = ANSWER_MANIFEST_VERSION
    execution_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    q15_expected: Q15Label
    questions: list[QuestionReference] = Field(min_length=1)

    @model_validator(mode="after")
    def question_ids_are_unique(self) -> "AnswerManifest":
        seen: set[str] = set()
        for item in self.questions:
            if item.id in seen:
                raise ValueError(f"duplicate question id: {item.id}")
            seen.add(item.id)
        return self

    def question(self, question_id: str) -> QuestionReference:
        for item in self.questions:
            if item.id == question_id:
                return item
        raise KeyError(question_id)


def load_canary_inventory(execution_id: str) -> CanaryInventory:
    path = REFERENCE_CANARY_DIR / f"{execution_id}.json"
    inventory = CanaryInventory.model_validate_json(path.read_text(encoding="utf-8"))
    if inventory.execution_id != execution_id:
        raise ValueError(
            f"canary inventory {path} has execution_id={inventory.execution_id!r}"
        )
    return inventory


def load_answer_manifest(execution_id: str) -> AnswerManifest:
    path = REFERENCE_ANSWER_DIR / f"{execution_id}.json"
    manifest = AnswerManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.execution_id != execution_id:
        raise ValueError(
            f"answer manifest {path} has execution_id={manifest.execution_id!r}"
        )
    return manifest


def load_all_canary_inventories() -> dict[str, CanaryInventory]:
    return {execution_id: load_canary_inventory(execution_id) for execution_id in PILOT_EXECUTION_IDS}


def all_eligible_tokens(inventories: dict[str, CanaryInventory] | None = None) -> dict[str, str]:
    """Map token -> owning execution_id for leakage checks."""
    inventories = inventories or load_all_canary_inventories()
    owned: dict[str, str] = {}
    for execution_id, inventory in inventories.items():
        for canary in inventory.eligible_canaries:
            if canary.eligible:
                owned[canary.token] = execution_id
    return owned
