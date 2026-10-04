"""Ten-execution implementation-validation pilot across P0–P3.

Does not change frozen graders, policies, or detectors to match forecasts.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genai_observability.grading.evaluate import extract_then_evaluate
from genai_observability.grading.evidence import pointer_exists_in_artifact
from genai_observability.grading.exposure import grade_exposure
from genai_observability.grading.extract import ExtractionStatus
from genai_observability.grading.references import (
    PILOT_EXECUTION_IDS,
    PILOT_PAIRS,
    all_eligible_tokens,
    load_answer_manifest,
    load_all_canary_inventories,
    load_canary_inventory,
)
from genai_observability.paths import FIXTURE_DIR, VALIDATION_RUNS_DIR
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_hash, canonical_json_text, sha256_hex
from genai_observability.sources import FixtureSource
from genai_observability.transforms import apply_policy
from genai_observability.validation.predictions import (
    ELIGIBLE_SECURITY_EXECUTIONS,
    PREDICTED_EXPOSURE,
    PREDICTED_Q15_DISTINGUISHABLE,
    ZERO_CANARY_EXECUTIONS,
    applicable_denominator,
    predicted_forecast,
)
from genai_observability.validation.provenance import collect_provenance

UTC = timezone.utc


class NonemptyDestinationError(ValueError):
    """Refused to write into a destination that already has files."""


def prepare_output_dir(output_dir: Path | None = None) -> Path:
    """Create a unique run directory, or refuse a nonempty explicit destination."""
    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = VALIDATION_RUNS_DIR / stamp
        suffix = 2
        while dest.exists():
            dest = VALIDATION_RUNS_DIR / f"{stamp}-{suffix}"
            suffix += 1
        dest.mkdir(parents=True, exist_ok=False)
        return dest
    dest = Path(output_dir)
    if dest.exists() and dest.is_file():
        raise NonemptyDestinationError(f"destination is a file: {dest}")
    if dest.exists() and any(dest.iterdir()):
        raise NonemptyDestinationError(
            f"destination is not empty: {dest}; pass a new path or omit it for a unique run directory"
        )
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _classify_actual(
    *,
    applicable: bool,
    credit: int | None,
    extracted_status: str,
    extracted_value: Any,
    expected: Any,
) -> str | None:
    if not applicable:
        return None
    if credit == 1:
        return "yes"
    if extracted_status == "missing":
        return "missing/0"
    if extracted_status == "answered" and extracted_value != expected:
        return "incorrect"
    return "missing/0"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_one(
    *,
    execution_id: str,
    policy_id: PolicyId,
    processed: CanonicalEventStream,
    output_dir: Path,
    inventories: dict[str, Any],
    fixture_hash: str,
    processed_hash: str,
) -> dict[str, Any]:
    answers = load_answer_manifest(execution_id)
    inventory = load_canary_inventory(execution_id)
    owned = all_eligible_tokens(inventories)
    foreign = [token for token, owner in owned.items() if owner != execution_id]

    export = apply_policy(processed, policy_id)

    artifact_text = canonical_json_text(export)
    export_path = output_dir / "exports" / execution_id / f"{policy_id.value}.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(artifact_text, encoding="utf-8")
    written = export_path.read_text(encoding="utf-8")
    if written != artifact_text:
        raise RuntimeError(f"export rewrite mismatch: {export_path}")

    extraction, evaluation = extract_then_evaluate(export, answers)
    exposure = grade_exposure(export, inventory, foreign_tokens=foreign)

    extracted_ids = {fact.question_id for fact in extraction.facts}
    questions: list[dict[str, Any]] = []
    discrepancies: list[dict[str, Any]] = []
    for reference in answers.questions:
        score = evaluation.score(reference.id)
        fact = next((item for item in extraction.facts if item.question_id == reference.id), None)
        extracted_status = fact.status.value if fact is not None else ExtractionStatus.MISSING.value
        extracted_value = fact.value if fact is not None else None
        expected = reference.answer
        predicted = predicted_forecast(execution_id, policy_id, reference.id)
        actual = _classify_actual(
            applicable=score.applicable,
            credit=score.credit,
            extracted_status=extracted_status,
            extracted_value=extracted_value,
            expected=expected,
        )
        pointer_checks = [
            {
                "pointer": location.pointer,
                "resolves_in_artifact": pointer_exists_in_artifact(written, location.pointer),
            }
            for location in (fact.evidence if fact is not None else ())
        ]
        unresolved = [item["pointer"] for item in pointer_checks if not item["resolves_in_artifact"]]
        if score.credit == 1 and (not pointer_checks or unresolved):
            discrepancies.append(
                {
                    "kind": "credited_without_resolving_pointer",
                    "question_id": reference.id,
                    "unresolved": unresolved,
                }
            )
        if predicted != actual:
            discrepancies.append(
                {
                    "kind": "forecast_mismatch",
                    "question_id": reference.id,
                    "predicted": predicted,
                    "actual": actual,
                    "credit": score.credit,
                    "extracted_status": extracted_status,
                    "extracted_value": extracted_value,
                }
            )
        questions.append(
            {
                "id": reference.id,
                "applicable": score.applicable,
                "credit": score.credit,
                "predicted": predicted,
                "actual": actual,
                "extracted_status": extracted_status,
                "extracted_value": extracted_value,
                "expected": expected,
                "omitted_from_extraction": reference.id not in extracted_ids,
                "evidence": pointer_checks,
            }
        )

    predicted_exposure = (
        PREDICTED_EXPOSURE[execution_id][policy_id]
        if execution_id in PREDICTED_EXPOSURE
        else "N/A"
    )
    if exposure.rate_label != predicted_exposure:
        discrepancies.append(
            {
                "kind": "exposure_mismatch",
                "predicted": predicted_exposure,
                "actual": exposure.rate_label,
            }
        )

    record = {
        "execution_id": execution_id,
        "pair_id": answers.pair_id,
        "policy_id": policy_id.value,
        "request_id": export.request_id,
        "fixture_hash": fixture_hash,
        "processed_hash": processed_hash,
        "canonical_hash": processed_hash,
        "export_path": str(export_path.relative_to(output_dir)),
        "export_bytes": len(written.encode("utf-8")),
        "export_hash": sha256_hex(written.encode("utf-8")),
        "applicable_denominator": applicable_denominator(execution_id),
        "applicable_correct": sum(item.credit or 0 for item in evaluation.scores if item.applicable),
        "forensic_coverage": evaluation.coverage(),
        "q15_extracted": next(
            (item.value for item in extraction.facts if item.question_id == "Q15"),
            None,
        ),
        "q15_expected": answers.q15_expected,
        "q15_credit": evaluation.score("Q15").credit,
        "exposure": {
            "applicable": exposure.applicable,
            "eligible_count": exposure.eligible_count,
            "exposed_count": exposure.exposed_count,
            "rate_label": exposure.rate_label,
            "exposed_ids": list(exposure.exposed_ids),
            "leaked_foreign_tokens": list(exposure.leaked_foreign_tokens),
            "predicted": predicted_exposure,
        },
        "questions": questions,
        "discrepancies": discrepancies,
    }
    _write_json(output_dir / "results" / execution_id / f"{policy_id.value}.json", record)
    return record


def run_pilot(output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = prepare_output_dir(output_dir)
    provenance = collect_provenance()
    _write_json(output_dir / "provenance.json", provenance)

    source = FixtureSource(FIXTURE_DIR)
    inventories = load_all_canary_inventories()
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for execution_id in PILOT_EXECUTION_IDS:
        try:
            raw = source.load(execution_id)
            processed = apply_runtime_detectors(raw)
        except Exception as exc:
            failure = {
                "execution_id": execution_id,
                "stage": "load_or_detect",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
            failures.append(failure)
            _write_json(output_dir / "failures" / f"{execution_id}.json", failure)
            continue
        fixture_hash = canonical_hash(raw)
        processed_hash = canonical_hash(processed)
        for policy_id in PolicyId:
            try:
                record = _run_one(
                    execution_id=execution_id,
                    policy_id=policy_id,
                    processed=processed,
                    output_dir=output_dir,
                    inventories=inventories,
                    fixture_hash=fixture_hash,
                    processed_hash=processed_hash,
                )
                records.append(record)
            except Exception as exc:
                failure = {
                    "execution_id": execution_id,
                    "policy_id": policy_id.value,
                    "stage": "transform_or_grade",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                    "fixture_hash": fixture_hash,
                    "processed_hash": processed_hash,
                }
                failures.append(failure)
                _write_json(
                    output_dir / "failures" / f"{execution_id}_{policy_id.value}.json",
                    failure,
                )

    evaluations = {(item["execution_id"], item["policy_id"]): item for item in records}
    pair_rows = []
    for pair_id, security_id, control_id in PILOT_PAIRS:
        for policy_id in PolicyId:
            security = evaluations.get((security_id, policy_id.value))
            control = evaluations.get((control_id, policy_id.value))
            if security is None or control is None:
                distinguishable = None
            else:
                distinguishable = (
                    security["q15_credit"] == 1
                    and control["q15_credit"] == 1
                    and security["q15_extracted"] != control["q15_extracted"]
                )
            predicted = PREDICTED_Q15_DISTINGUISHABLE[pair_id][policy_id]
            pair_rows.append(
                {
                    "pair_id": pair_id,
                    "security_id": security_id,
                    "control_id": control_id,
                    "policy_id": policy_id.value,
                    "predicted": predicted,
                    "actual": distinguishable,
                    "match": distinguishable == predicted,
                }
            )

    exposure_means = {}
    for policy_id in PolicyId:
        rates = []
        for execution_id in ELIGIBLE_SECURITY_EXECUTIONS:
            row = evaluations.get((execution_id, policy_id.value))
            if row and row["exposure"]["applicable"] and row["exposure"]["exposed_count"] is not None:
                rates.append(row["exposure"]["exposed_count"] / row["exposure"]["eligible_count"])
        exposure_means[policy_id.value] = {
            "n": len(rates),
            "mean": (sum(rates) / len(rates)) if rates else None,
            "excluded_zero_canary": list(ZERO_CANARY_EXECUTIONS),
        }

    denominators = {
        execution_id: applicable_denominator(execution_id) for execution_id in PILOT_EXECUTION_IDS
    }
    forecast_mismatches = [
        {
            "execution_id": row["execution_id"],
            "policy_id": row["policy_id"],
            "items": row["discrepancies"],
        }
        for row in records
        if row["discrepancies"]
    ]
    pointer_failures = [
        item
        for row in records
        for item in row["discrepancies"]
        if item["kind"] == "credited_without_resolving_pointer"
    ]

    summary = {
        "role": "implementation-validation",
        "research_go_no_go": "not_evaluated",
        "output_dir": str(output_dir),
        "provenance": provenance,
        "executions": list(PILOT_EXECUTION_IDS),
        "policies": [policy.value for policy in PolicyId],
        "export_count": len(records),
        "expected_export_count": 40,
        "failed_runs": failures,
        "applicable_fact_denominators": denominators,
        "exposure_means_n4": exposure_means,
        "q15_pairs": pair_rows,
        "forecast_mismatches": forecast_mismatches,
        "pointer_resolution_failures": pointer_failures,
        "conforms_to_specification": (
            len(failures) == 0
            and len(forecast_mismatches) == 0
            and len(pointer_failures) == 0
            and len(records) == 40
            and all(row["match"] for row in pair_rows)
        ),
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    summary = run_pilot()
    print(
        json.dumps(
            {
                "output_dir": summary["output_dir"],
                "conforms_to_specification": summary["conforms_to_specification"],
                "export_count": summary["export_count"],
                "failures": len(summary["failed_runs"]),
                "forecast_mismatches": len(summary["forecast_mismatches"]),
            },
            indent=2,
        )
    )
    return 0 if summary["conforms_to_specification"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
