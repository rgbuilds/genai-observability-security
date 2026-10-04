"""Compare extracted answers to a frozen answer key.

Applicability is read from the execution's reference definition and does not
vary by policy. Callers must extract first, then pass the extraction here.
"""

from dataclasses import dataclass
from typing import Any

from genai_observability.grading.evidence import export_dump, pointer_exists
from genai_observability.grading.extract import (
    ExtractedFact,
    ExtractionStatus,
    ForensicExtraction,
    extract_forensic_answers,
)
from genai_observability.grading.references import AnswerManifest, QuestionReference
from genai_observability.schemas.export import TelemetryExport
from genai_observability.transforms.apply import opaque_identifier


class DuplicateQuestionIdError(ValueError):
    """An extraction or answer key repeated a question id."""


@dataclass(frozen=True)
class FactScore:
    question_id: str
    applicable: bool
    credit: int | None
    extracted_status: str
    extracted_value: Any = None


@dataclass(frozen=True)
class ForensicEvaluation:
    execution_id: str
    scores: tuple[FactScore, ...]

    def score(self, question_id: str) -> FactScore:
        for item in self.scores:
            if item.question_id == question_id:
                return item
        raise KeyError(question_id)

    def coverage(self) -> float | None:
        applicable = [item for item in self.scores if item.applicable]
        if not applicable:
            return None
        return sum(item.credit or 0 for item in applicable) / len(applicable)


def _edges(value: Any) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    if not value:
        return result
    for item in value:
        if isinstance(item, dict):
            result.add((item["parent"], item["child"]))
        else:
            result.add((item[0], item[1]))
    return result


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _q4_matches(extracted: Any, expected: Any) -> bool:
    expected_ids = [item for item in _as_list(expected) if item is not None]
    candidates = [item for item in _as_list(extracted) if item is not None]
    accepted = set(expected_ids)
    for item in expected_ids:
        if isinstance(item, str):
            accepted.add(opaque_identifier(item))
    return any(candidate in accepted for candidate in candidates)


def _q5_matches(extracted: Any, expected: Any) -> bool:
    if not isinstance(extracted, dict) or not isinstance(expected, dict):
        return extracted == expected
    return all(extracted.get(key) == value for key, value in expected.items())


def _q14_matches(extracted: Any, reference: QuestionReference) -> bool:
    registered = reference.registered_edges or []
    registered_edges = {(edge.parent, edge.child) for edge in registered}
    if reference.answer is not None:
        registered_edges |= _edges(reference.answer)
    return registered_edges.issubset(_edges(extracted))


def _values_match(fact: ExtractedFact, reference: QuestionReference) -> bool:
    if fact.question_id == "Q4":
        return _q4_matches(fact.value, reference.answer)
    if fact.question_id == "Q5":
        return _q5_matches(fact.value, reference.answer)
    if fact.question_id == "Q14":
        return _q14_matches(fact.value, reference)
    return fact.value == reference.answer


def _evidence_in_export(export: TelemetryExport, fact: ExtractedFact) -> bool:
    if not fact.evidence:
        return False
    dump = export_dump(export)
    return any(pointer_exists(dump, location.pointer) for location in fact.evidence)


def _facts_by_id(extraction: ForensicExtraction) -> dict[str, ExtractedFact]:
    facts: dict[str, ExtractedFact] = {}
    for fact in extraction.facts:
        if fact.question_id in facts:
            raise DuplicateQuestionIdError(
                f"extraction repeated question id {fact.question_id!r}"
            )
        facts[fact.question_id] = fact
    return facts


def evaluate_forensic(
    extraction: ForensicExtraction,
    answers: AnswerManifest,
    export: TelemetryExport,
) -> ForensicEvaluation:
    """Score an already-computed extraction against the execution answer key.

    The denominator is the reference question list. An omitted applicable
    question is missing → 0. Duplicate extracted IDs are rejected.
    """
    facts = _facts_by_id(extraction)
    scores: list[FactScore] = []
    for reference in answers.questions:
        fact = facts.get(reference.id) or ExtractedFact(
            question_id=reference.id,
            status=ExtractionStatus.MISSING,
        )
        if not reference.applicable:
            scores.append(
                FactScore(
                    question_id=reference.id,
                    applicable=False,
                    credit=None,
                    extracted_status=fact.status.value,
                    extracted_value=fact.value,
                )
            )
            continue
        credit = 0
        if (
            fact.status is ExtractionStatus.ANSWERED
            and _values_match(fact, reference)
            and _evidence_in_export(export, fact)
        ):
            credit = 1
        scores.append(
            FactScore(
                question_id=reference.id,
                applicable=True,
                credit=credit,
                extracted_status=fact.status.value,
                extracted_value=fact.value,
            )
        )
    return ForensicEvaluation(execution_id=answers.execution_id, scores=tuple(scores))


def extract_then_evaluate(
    export: TelemetryExport,
    answers: AnswerManifest,
) -> tuple[ForensicExtraction, ForensicEvaluation]:
    extraction = extract_forensic_answers(export)
    return extraction, evaluate_forensic(extraction, answers, export)


def pair_distinguishable(
    security_eval: ForensicEvaluation,
    control_eval: ForensicEvaluation,
) -> bool:
    """Both members correct and different under the same Q15 extraction rule."""
    security = security_eval.score("Q15")
    control = control_eval.score("Q15")
    if not security.applicable or not control.applicable:
        return False
    if security.credit != 1 or control.credit != 1:
        return False
    return security.extracted_value != control.extracted_value
