"""Mocked full-study runner. Live HTTP is refused. Failures are preserved."""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genai_observability.full_study.aggregate import exploratory_bootstrap, paired_differences, summarize
from genai_observability.full_study.evaluate import extract_then_evaluate_full_study
from genai_observability.full_study.fixtures import build_stream
from genai_observability.full_study.forecasts import predict_credit
from genai_observability.full_study.inventory import all_tokens, inventory_from_spec
from genai_observability.full_study.mock_capture import capture_mocked, scripted_responses_for
from genai_observability.full_study.protocol import (
    CHECKLIST_VERSION,
    LIVE_ENV_FLAG,
    LIVE_FULL_STUDY_AUTHORIZED,
    PROTOCOL_VERSION,
)
from genai_observability.full_study.scenarios import all_specs
from genai_observability.full_study.select import select_full_study_references
from genai_observability.grading.evidence import pointer_exists_in_artifact
from genai_observability.grading.exposure import grade_exposure
from genai_observability.grading.references import CanaryInventory
from genai_observability.paths import (
    FULL_STUDY_ANSWER_DIR,
    FULL_STUDY_CANARY_DIR,
    FULL_STUDY_RUNS_DIR,
    FULL_STUDY_STREAM_DIR,
    PATTERN_LIBRARY_DIR,
    POLICY_ALLOWLIST_DIR,
)
from genai_observability.research.capture import LiveCaptureNotAuthorized, ScriptedCompletionsClient
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_hash, canonical_json_text, sha256_hex
from genai_observability.transforms import apply_policy
from genai_observability.validation.provenance import collect_provenance, hash_paths
from genai_observability.validation.run_pilot import NonemptyDestinationError

UTC = timezone.utc
ROLE = "full-study-mocked-validation"
LABEL = (
    "Full-study mocked validation. Retention-forecast cells are allowlist checks. "
    "They are not live-capture observations."
)


def prepare_run_dir(output_dir: Path | None = None) -> Path:
    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = FULL_STUDY_RUNS_DIR / stamp
        suffix = 2
        while dest.exists():
            dest = FULL_STUDY_RUNS_DIR / f"{stamp}-{suffix}"
            suffix += 1
        dest.mkdir(parents=True, exist_ok=False)
        return dest
    dest = Path(output_dir)
    if dest.exists() and dest.is_file():
        raise NonemptyDestinationError(f"destination is a file: {dest}")
    if dest.exists() and any(dest.iterdir()):
        raise NonemptyDestinationError(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _hash_run_inputs(output_dir: Path) -> dict[str, Any]:
    files: dict[str, str] = {}
    for directory in ("streams", "answers", "canaries"):
        for path in sorted((output_dir / directory).glob("*.json")):
            files[path.relative_to(output_dir).as_posix()] = sha256_hex(path.read_bytes())
    combined = sha256_hex(
        "\n".join(f"{name}={digest}" for name, digest in files.items()).encode("utf-8")
    )
    return {"files": files, "combined": combined}


def _refuse_live() -> None:
    if LIVE_FULL_STUDY_AUTHORIZED:
        raise LiveCaptureNotAuthorized("full-study live capture is not authorized")
    if os.environ.get("GENAI_LIVE_CAPTURE") == "1":
        raise LiveCaptureNotAuthorized("full-study runner refuses GENAI_LIVE_CAPTURE=1")
    if os.environ.get(LIVE_ENV_FLAG) == "1":
        raise LiveCaptureNotAuthorized("full-study runner refuses GENAI_FULL_STUDY_LIVE=1")


def _stream_for(spec: dict[str, Any]):
    if spec["source"] == "mocked-capture":
        client = ScriptedCompletionsClient(scripted_responses_for(spec))
        return capture_mocked(spec, client)
    return build_stream(spec)


def run_full_study(output_dir: Path | None = None) -> dict[str, Any]:
    _refuse_live()
    output_dir = prepare_run_dir(output_dir)
    specs = all_specs()
    inventories = [inventory_from_spec(spec) for spec in specs]
    owned = all_tokens(inventories)
    provenance = collect_provenance()
    provenance["role"] = ROLE
    provenance["protocol_version"] = PROTOCOL_VERSION
    provenance["checklist_version"] = CHECKLIST_VERSION
    provenance["live_full_study_authorized"] = LIVE_FULL_STUDY_AUTHORIZED
    provenance["configuration_hashes"] = hash_paths(
        [*POLICY_ALLOWLIST_DIR.glob("*.json"), *PATTERN_LIBRARY_DIR.glob("*.json")]
    )
    provenance["registered_full_study_hashes"] = hash_paths(
        [
            *FULL_STUDY_STREAM_DIR.glob("*.json"),
            *FULL_STUDY_ANSWER_DIR.glob("*.json"),
            *FULL_STUDY_CANARY_DIR.glob("*.json"),
        ]
    )

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    forecast_mismatches: list[dict[str, Any]] = []

    for spec in specs:
        execution_id = spec["execution_id"]
        try:
            raw = _stream_for(spec)
            processed = apply_runtime_detectors(raw)
            answers = select_full_study_references(processed, spec)
            inventory = inventory_from_spec(spec)
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
        _write_json(output_dir / "streams" / f"{execution_id}.json", json.loads(canonical_json_text(raw)))
        _write_json(output_dir / "answers" / f"{execution_id}.json", json.loads(answers.model_dump_json()))
        _write_json(
            output_dir / "canaries" / f"{execution_id}.json",
            json.loads(inventory.model_dump_json()),
        )
        foreign = [token for token, owner in owned.items() if owner != execution_id]
        for policy_id in PolicyId:
            try:
                export = apply_policy(processed, policy_id)
                artifact = canonical_json_text(export)
                export_path = output_dir / "exports" / execution_id / f"{policy_id.value}.json"
                export_path.parent.mkdir(parents=True, exist_ok=True)
                export_path.write_text(artifact, encoding="utf-8")
                extraction, evaluation = extract_then_evaluate_full_study(export, answers)
                exposure = grade_exposure(
                    export,
                    CanaryInventory(
                        execution_id=inventory.execution_id,
                        eligible_canaries=inventory.eligible_canaries,
                    ),
                    foreign_tokens=foreign,
                )
                questions = []
                mismatches = []
                for reference in answers.questions:
                    score = evaluation.score(reference.id)
                    predicted = predict_credit(reference.id, policy_id, raw, answers)
                    if predicted is not None and score.credit != predicted:
                        mismatches.append(
                            {
                                "question_id": reference.id,
                                "predicted_credit": predicted,
                                "actual_credit": score.credit,
                            }
                        )
                    pointer_checks = [
                        {
                            "pointer": location.pointer,
                            "resolves_in_artifact": pointer_exists_in_artifact(artifact, location.pointer),
                        }
                        for location in next(
                            (fact.evidence for fact in extraction.facts if fact.question_id == reference.id),
                            (),
                        )
                    ]
                    questions.append(
                        {
                            "id": reference.id,
                            "applicable": score.applicable,
                            "credit": score.credit,
                            "predicted_credit": predicted,
                            "extracted_status": score.extracted_status,
                            "extracted_value": score.extracted_value,
                            "evidence": pointer_checks,
                        }
                    )
                exposed_locations = sorted(
                    {
                        canary.location
                        for canary in inventory.eligible_canaries
                        if canary.canary_id in exposure.exposed_ids
                    }
                )
                record = {
                    "role": ROLE,
                    "execution_id": execution_id,
                    "pair_id": spec["pair_id"],
                    "family": spec["family"],
                    "intended_family": spec["intended_family"],
                    "role_in_pair": spec["role"],
                    "source": spec["source"],
                    "policy_id": policy_id.value,
                    "fixture_hash": fixture_hash,
                    "processed_hash": processed_hash,
                    "export_hash": sha256_hex(artifact.encode("utf-8")),
                    "applicable": sum(1 for item in evaluation.scores if item.applicable),
                    "correct": sum(item.credit or 0 for item in evaluation.scores if item.applicable),
                    "forensic_coverage": evaluation.coverage(),
                    "eligible_canaries": exposure.eligible_count,
                    "exposed_canaries": exposure.exposed_count or 0,
                    "exposure_applicable": exposure.applicable,
                    "exposed_locations": exposed_locations,
                    "leaked_foreign_tokens": list(exposure.leaked_foreign_tokens),
                    "questions": questions,
                    "forecast_mismatches": mismatches,
                }
                _write_json(output_dir / "results" / execution_id / f"{policy_id.value}.json", record)
                records.append(record)
                if mismatches:
                    forecast_mismatches.append(
                        {
                            "execution_id": execution_id,
                            "policy_id": policy_id.value,
                            "items": mismatches,
                        }
                    )
            except Exception as exc:
                failure = {
                    "execution_id": execution_id,
                    "policy_id": policy_id.value,
                    "stage": "transform_or_grade",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
                failures.append(failure)
                _write_json(
                    output_dir / "failures" / f"{execution_id}_{policy_id.value}.json",
                    failure,
                )

    aggregates = summarize(records)
    provenance["run_input_hashes"] = _hash_run_inputs(output_dir)
    _write_json(output_dir / "provenance.json", provenance)
    summary = {
        "role": ROLE,
        "label": LABEL,
        "protocol_version": PROTOCOL_VERSION,
        "checklist_version": CHECKLIST_VERSION,
        "research_evidence": False,
        "live_capture": "not_authorized",
        "output_dir": str(output_dir),
        "planned_templates": 24,
        "planned_controls": 24,
        "planned_executions": 48,
        "planned_exports": 192,
        "realized_exports": len(records),
        "failed_runs": failures,
        "forecast_mismatches": forecast_mismatches,
        "retention_forecasts_matched": len(failures) == 0
        and len(forecast_mismatches) == 0
        and len(records) == 192,
        "aggregates": aggregates,
        "paired_differences": paired_differences(records),
        "exploratory_bootstrap": exploratory_bootstrap(records),
        "provenance": {
            "git_commit": provenance.get("git_commit"),
            "git_describe": provenance.get("git_describe"),
            "git_dirty": provenance.get("git_dirty"),
            "configuration_combined": provenance["configuration_hashes"]["combined"],
            "source_combined": provenance["source_hashes"]["combined"],
            "registered_full_study_combined": provenance["registered_full_study_hashes"][
                "combined"
            ],
            "run_inputs_combined": provenance["run_input_hashes"]["combined"],
        },
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    summary = run_full_study()
    print(
        json.dumps(
            {
                "output_dir": summary["output_dir"],
                "retention_forecasts_matched": summary["retention_forecasts_matched"],
                "realized_exports": summary["realized_exports"],
                "failures": len(summary["failed_runs"]),
                "forecast_mismatches": len(summary["forecast_mismatches"]),
            },
            indent=2,
        )
    )
    return 0 if summary["retention_forecasts_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
