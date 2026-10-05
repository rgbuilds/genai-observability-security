"""Compare extracted R-answers to a private research answer key.

Callers must extract first. This module may read manifests; extract must not.
"""

from typing import Any

from genai_observability.grading.evaluate import DuplicateQuestionIdError, FactScore, ForensicEvaluation
from genai_observability.grading.evidence import export_dump, pointer_exists
from genai_observability.grading.extract import ExtractedFact, ExtractionStatus, ForensicExtraction
from genai_observability.research.extract import extract_research_answers
from genai_observability.research.questions import REDACTION_MARKERS
from genai_observability.research.references import ResearchAnswerManifest, ResearchQuestionReference
from genai_observability.schemas.export import TelemetryExport
from genai_observability.serialization import canonical_json_text


def _readable(text: Any) -> bool:
    if not isinstance(text, str) or text == "":
        return False
    return not any(marker in text for marker in REDACTION_MARKERS)


def r4_outcome(fact: ExtractedFact, token: str | None) -> str:
    """yes / no / missing. `no` requires both locations readable."""
    if token is None or fact.status is not ExtractionStatus.ANSWERED:
        return "missing"
    if not isinstance(fact.value, dict):
        return "missing"
    loc1 = fact.value.get("loc1")
    loc2 = fact.value.get("loc2")
    if not _readable(loc1) or not _readable(loc2):
        return "missing"
    in_loc1 = token in loc1
    in_loc2 = token in loc2
    return "yes" if in_loc1 and in_loc2 else "no"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _canonical_item(value: Any) -> str:
    if isinstance(value, dict):
        return canonical_json_text(value)
    return canonical_json_text({"_": value})


def _r1_matches(extracted: Any, expected: Any) -> bool:
    left = [_canonical_item(item) for item in _as_list(extracted)]
    right = [_canonical_item(item) for item in _as_list(expected)]
    return left == right


def _scalar_list_matches(extracted: Any, expected: Any) -> bool:
    return _as_list(extracted) == _as_list(expected)


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


def _r7_matches(extracted: Any, reference: ResearchQuestionReference) -> bool:
    registered = {(edge.parent, edge.child) for edge in (reference.registered_edges or [])}
    return registered.issubset(_edges(extracted))


def _values_match(fact: ExtractedFact, reference: ResearchQuestionReference) -> bool:
    if reference.id == "R1":
        return _r1_matches(fact.value, reference.answer)
    if reference.id in {"R2", "R5"}:
        return _scalar_list_matches(fact.value, reference.answer)
    if reference.id in {"R3", "R6"}:
        return (
            isinstance(fact.value, str)
            and isinstance(reference.answer, str)
            and reference.answer in fact.value
        )
    if reference.id == "R4":
        return r4_outcome(fact, reference.token) == reference.answer
    if reference.id == "R7":
        return _r7_matches(fact.value, reference)
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


def evaluate_research(
    extraction: ForensicExtraction,
    answers: ResearchAnswerManifest,
    export: TelemetryExport,
) -> ForensicEvaluation:
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
        if reference.id == "R4":
            observed = r4_outcome(fact, reference.token)
            credit = (
                1
                if observed == reference.answer
                and observed != "missing"
                and _evidence_in_export(export, fact)
                else 0
            )
            scores.append(
                FactScore(
                    question_id="R4",
                    applicable=True,
                    credit=credit,
                    extracted_status="missing" if observed == "missing" else fact.status.value,
                    extracted_value=observed,
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


def extract_then_evaluate_research(
    export: TelemetryExport,
    answers: ResearchAnswerManifest,
) -> tuple[ForensicExtraction, ForensicEvaluation]:
    extraction = extract_research_answers(export)
    return extraction, evaluate_research(extraction, answers, export)
