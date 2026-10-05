"""Scripted S/T retention validation across P0–P3.

These artifacts check that R graders reproduce allowlist forecasts.
They are not realistic-capture lessons and not a research go/no-go.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genai_observability.grading.evidence import pointer_exists_in_artifact
from genai_observability.grading.extract import ExtractionStatus
from genai_observability.paths import (
    PATTERN_LIBRARY_DIR,
    POLICY_ALLOWLIST_DIR,
    RESEARCH_ANSWER_DIR,
    RESEARCH_FIXTURE_DIR,
    RESEARCH_RETENTION_RUNS_DIR,
)
from genai_observability.research.evaluate import extract_then_evaluate_research
from genai_observability.research.references import RESEARCH_EXECUTION_IDS, RESEARCH_PAIRS, load_research_answers
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_hash, canonical_json_text, sha256_hex
from genai_observability.sources import FixtureSource
from genai_observability.transforms import apply_policy
from genai_observability.validation.provenance import collect_provenance, hash_paths
from genai_observability.validation.run_pilot import NonemptyDestinationError

UTC = timezone.utc

ROLE = "retention-validation-only"
LABEL = (
    "Retention validation only. Scripted S/T scores that match the allowlist "
    "are retention forecasts, not realistic-capture lessons and not a research go/no-go."
)

# Published forecast cells from RESEARCH_FEASIBILITY_PLAN.md sections 4.4–6.2.
_S_CREDITS = {
    PolicyId.P0: {"R1": 0, "R2": 0, "R5": 1, "R6": 0, "R7": 1},
    PolicyId.P1: {"R1": 1, "R2": 1, "R5": 1, "R6": 1, "R7": 1},
    PolicyId.P2: {"R1": 1, "R2": 1, "R5": 1, "R6": 1, "R7": 1},
    PolicyId.P3: {"R1": 0, "R2": 0, "R5": 1, "R6": 0, "R7": 1},
}
_T_CREDITS = {
    PolicyId.P0: {"R3": 0, "R4": 0, "R7": 1},
    PolicyId.P1: {"R3": 1, "R4": 1, "R7": 1},
    PolicyId.P2: {"R3": 0, "R4": 0, "R7": 1},
    PolicyId.P3: {"R3": 0, "R4": 0, "R7": 1},
}


def _forecast(execution_id: str, policy_id: PolicyId) -> dict[str, int]:
    if execution_id in {"res-s1", "res-s2"}:
        return dict(_S_CREDITS[policy_id])
    return dict(_T_CREDITS[policy_id])


def _expected_r4_value(execution_id: str, policy_id: PolicyId) -> str | None:
    if execution_id not in {"res-t1", "res-t2"}:
        return None
    if policy_id is not PolicyId.P1:
        return "missing"
    return "yes" if execution_id == "res-t1" else "no"


def prepare_retention_dir(output_dir: Path | None = None) -> Path:
    """Create a unique retention-run directory, or refuse a nonempty destination."""
    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = RESEARCH_RETENTION_RUNS_DIR / stamp
        suffix = 2
        while dest.exists():
            dest = RESEARCH_RETENTION_RUNS_DIR / f"{stamp}-{suffix}"
            suffix += 1
        dest.mkdir(parents=True, exist_ok=False)
        return dest
    dest = Path(output_dir)
    if dest.exists() and dest.is_file():
        raise NonemptyDestinationError(f"destination is a file: {dest}")
    if dest.exists() and any(dest.iterdir()):
        raise NonemptyDestinationError(
            f"destination is not empty: {dest}; omit the path for a unique run directory"
        )
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _research_provenance() -> dict[str, Any]:
    provenance = collect_provenance()
    provenance["role"] = ROLE
    provenance["label"] = LABEL
    provenance["research_fixture_hashes"] = hash_paths(sorted(RESEARCH_FIXTURE_DIR.glob("*.json")))
    provenance["research_answer_hashes"] = hash_paths(sorted(RESEARCH_ANSWER_DIR.glob("*.json")))
    provenance["configuration_hashes"] = hash_paths(
        [*POLICY_ALLOWLIST_DIR.glob("*.json"), *PATTERN_LIBRARY_DIR.glob("*.json")]
    )
    return provenance


def _run_one(
    *,
    execution_id: str,
    policy_id: PolicyId,
    processed: CanonicalEventStream,
    output_dir: Path,
    fixture_hash: str,
    processed_hash: str,
    configuration_combined: str,
    research_fixture_combined: str,
    research_answer_combined: str,
) -> dict[str, Any]:
    answers = load_research_answers(execution_id)
    export = apply_policy(processed, policy_id)
    artifact_text = canonical_json_text(export)
    export_path = output_dir / "exports" / execution_id / f"{policy_id.value}.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(artifact_text, encoding="utf-8")
    written = export_path.read_text(encoding="utf-8")
    if written != artifact_text:
        raise RuntimeError(f"export rewrite mismatch: {export_path}")

    extraction, evaluation = extract_then_evaluate_research(export, answers)
    extracted_ids = {fact.question_id for fact in extraction.facts}
    forecast = _forecast(execution_id, policy_id)
    expected_r4 = _expected_r4_value(execution_id, policy_id)
    questions: list[dict[str, Any]] = []
    discrepancies: list[dict[str, Any]] = []
    extraction_facts: list[dict[str, Any]] = []

    for fact in extraction.facts:
        pointer_checks = [
            {
                "pointer": location.pointer,
                "resolves_in_artifact": pointer_exists_in_artifact(written, location.pointer),
            }
            for location in fact.evidence
        ]
        extraction_facts.append(
            {
                "question_id": fact.question_id,
                "status": fact.status.value,
                "value": fact.value,
                "evidence": pointer_checks,
            }
        )

    for reference in answers.questions:
        score = evaluation.score(reference.id)
        fact = next((item for item in extraction.facts if item.question_id == reference.id), None)
        extracted_status = fact.status.value if fact is not None else ExtractionStatus.MISSING.value
        scored_value = score.extracted_value
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
        predicted = forecast.get(reference.id)
        if predicted is not None and score.credit != predicted:
            discrepancies.append(
                {
                    "kind": "forecast_mismatch",
                    "question_id": reference.id,
                    "predicted_credit": predicted,
                    "actual_credit": score.credit,
                    "extracted_status": extracted_status,
                }
            )
        if reference.id == "R4" and expected_r4 is not None and scored_value != expected_r4:
            discrepancies.append(
                {
                    "kind": "r4_value_mismatch",
                    "predicted": expected_r4,
                    "actual": scored_value,
                }
            )
        questions.append(
            {
                "id": reference.id,
                "applicable": score.applicable,
                "credit": score.credit,
                "predicted_credit": predicted,
                "extracted_status": extracted_status,
                "extracted_value": scored_value,
                "omitted_from_extraction": reference.id not in extracted_ids,
                "evidence": pointer_checks,
            }
        )

    record = {
        "role": ROLE,
        "label": LABEL,
        "execution_id": execution_id,
        "pair_id": answers.pair_id,
        "policy_id": policy_id.value,
        "request_id": export.request_id,
        "fixture_hash": fixture_hash,
        "processed_hash": processed_hash,
        "configuration_hash": configuration_combined,
        "research_fixture_hash": research_fixture_combined,
        "research_answer_hash": research_answer_combined,
        "export_path": str(export_path.relative_to(output_dir)),
        "export_bytes": len(written.encode("utf-8")),
        "export_hash": sha256_hex(written.encode("utf-8")),
        "applicable_correct": sum(item.credit or 0 for item in evaluation.scores if item.applicable),
        "forensic_coverage": evaluation.coverage(),
        "questions": questions,
        "discrepancies": discrepancies,
    }
    _write_json(output_dir / "extractions" / execution_id / f"{policy_id.value}.json", {
        "role": ROLE,
        "execution_id": execution_id,
        "policy_id": policy_id.value,
        "fixture_hash": fixture_hash,
        "processed_hash": processed_hash,
        "export_hash": record["export_hash"],
        "facts": extraction_facts,
    })
    _write_json(output_dir / "results" / execution_id / f"{policy_id.value}.json", record)
    return record


def run_retention(output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = prepare_retention_dir(output_dir)
    provenance = _research_provenance()
    _write_json(output_dir / "provenance.json", provenance)
    configuration_combined = provenance["configuration_hashes"]["combined"]
    research_fixture_combined = provenance["research_fixture_hashes"]["combined"]
    research_answer_combined = provenance["research_answer_hashes"]["combined"]

    source = FixtureSource(RESEARCH_FIXTURE_DIR)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for execution_id in RESEARCH_EXECUTION_IDS:
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
                records.append(
                    _run_one(
                        execution_id=execution_id,
                        policy_id=policy_id,
                        processed=processed,
                        output_dir=output_dir,
                        fixture_hash=fixture_hash,
                        processed_hash=processed_hash,
                        configuration_combined=configuration_combined,
                        research_fixture_combined=research_fixture_combined,
                        research_answer_combined=research_answer_combined,
                    )
                )
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
    for pair_id, left_id, right_id in RESEARCH_PAIRS:
        if pair_id != "S":
            continue
        for policy_id in PolicyId:
            left = evaluations.get((left_id, policy_id.value))
            right = evaluations.get((right_id, policy_id.value))
            if left is None or right is None:
                distinguishable = None
            else:
                left_r5 = next(item for item in left["questions"] if item["id"] == "R5")
                right_r5 = next(item for item in right["questions"] if item["id"] == "R5")
                distinguishable = (
                    left_r5["credit"] == 1
                    and right_r5["credit"] == 1
                    and left_r5["extracted_value"] != right_r5["extracted_value"]
                )
            pair_rows.append(
                {
                    "pair_id": pair_id,
                    "left_id": left_id,
                    "right_id": right_id,
                    "policy_id": policy_id.value,
                    "question_id": "R5",
                    "actual_distinguishable": distinguishable,
                    "match": distinguishable is True,
                }
            )

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
        "role": ROLE,
        "label": LABEL,
        "research_evidence": False,
        "research_go_no_go": "not_evaluated",
        "live_capture": "not_authorized",
        "output_dir": str(output_dir),
        "provenance": provenance,
        "executions": list(RESEARCH_EXECUTION_IDS),
        "policies": [policy.value for policy in PolicyId],
        "export_count": len(records),
        "expected_export_count": 16,
        "failed_runs": failures,
        "r5_pair_s": pair_rows,
        "forecast_mismatches": forecast_mismatches,
        "pointer_resolution_failures": pointer_failures,
        "retention_forecasts_matched": (
            len(failures) == 0
            and len(forecast_mismatches) == 0
            and len(pointer_failures) == 0
            and len(records) == 16
            and all(row["match"] for row in pair_rows)
        ),
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    summary = run_retention()
    print(
        json.dumps(
            {
                "output_dir": summary["output_dir"],
                "role": summary["role"],
                "retention_forecasts_matched": summary["retention_forecasts_matched"],
                "export_count": summary["export_count"],
                "failures": len(summary["failed_runs"]),
                "forecast_mismatches": len(summary["forecast_mismatches"]),
                "git_commit": summary["provenance"]["git_commit"],
                "git_describe": summary["provenance"]["git_describe"],
                "git_dirty": summary["provenance"]["git_dirty"],
            },
            indent=2,
        )
    )
    return 0 if summary["retention_forecasts_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
