"""Offline replay of an immutable full-study live capture. No model or HTTP calls."""

from __future__ import annotations

import argparse
import json
import os
import stat
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genai_observability.full_study.aggregate import paired_differences, summarize
from genai_observability.full_study.evaluate import extract_then_evaluate_full_study
from genai_observability.full_study.inventory import all_tokens, inventory_from_realized_stream
from genai_observability.full_study.live_adapter import artifact_hashes
from genai_observability.full_study.protocol import (
    CHECKLIST_VERSION,
    LIVE_ENV_FLAG,
    LIVE_FULL_STUDY_AUTHORIZED,
    PROTOCOL_VERSION,
)
from genai_observability.full_study.questions import FULL_STUDY_QUESTION_IDS
from genai_observability.full_study.references import FullStudyAnswerManifest, FullStudyCanaryInventory
from genai_observability.full_study.scenarios import CAPTURE_ONCE_EXECUTION_IDS, spec_by_id
from genai_observability.full_study.select import select_full_study_references
from genai_observability.grading.evidence import pointer_exists_in_artifact
from genai_observability.grading.exposure import grade_exposure
from genai_observability.grading.references import CanaryInventory
from genai_observability.paths import PRIVATE_DIR, REPO_ROOT
from genai_observability.research.capture import (
    LiveCaptureNotAuthorized,
    secure_capture_directory,
    secure_capture_write_text,
)
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import DetectorPass, PolicyId
from genai_observability.serialization import canonical_json_text, sha256_hex
from genai_observability.transforms import apply_policy
from genai_observability.validation.provenance import collect_provenance

UTC = timezone.utc
ROLE = "full-study-live-replay"
LABEL = (
    "Live-capture research evidence. Offline replay of an immutable capture. "
    "Not a retention-forecast validation."
)
PRIVATE_REPLAY_RUNS_DIR = PRIVATE_DIR / "full-study-replay" / "runs"
REPLAY_ANALYSIS_SOURCE_FREEZE_PATH = (
    REPO_ROOT / "references" / "full-study" / "replay_analysis_source_freeze.json"
)
_SAFE_VALUES = frozenset({"yes", "no", "missing", "allowed", "denied", "none"})


class ReplayIntegrityError(RuntimeError):
    """The capture package or replay protocol is not internally consistent."""


class ReplayExecutionError(RuntimeError):
    """An unexpected replay failure was persisted without exposing its details."""


@dataclass
class ReplayContext:
    output_dir: Path | None = None


@dataclass(frozen=True)
class VerifiedCaptureSnapshot:
    root: Path
    files: dict[str, bytes]

    def has(self, relative_name: str) -> bool:
        return relative_name in self.files

    def read_text(self, relative_name: str) -> str:
        try:
            return self.files[relative_name].decode("utf-8")
        except KeyError as exc:
            raise ReplayIntegrityError(f"verified capture artifact is missing: {relative_name}") from exc
        except UnicodeDecodeError as exc:
            raise ReplayIntegrityError(f"verified capture artifact is not UTF-8: {relative_name}") from exc

    def load_json(self, relative_name: str) -> Any:
        try:
            return json.loads(self.read_text(relative_name))
        except json.JSONDecodeError as exc:
            raise ReplayIntegrityError(
                f"verified capture artifact is invalid JSON: {relative_name}"
            ) from exc


def refuse_live_flags() -> None:
    if LIVE_FULL_STUDY_AUTHORIZED:
        raise LiveCaptureNotAuthorized("full-study live capture is not authorized")
    if os.environ.get("GENAI_LIVE_CAPTURE") == "1":
        raise LiveCaptureNotAuthorized("full-study replay refuses GENAI_LIVE_CAPTURE=1")
    if os.environ.get(LIVE_ENV_FLAG) == "1":
        raise LiveCaptureNotAuthorized("full-study replay refuses GENAI_FULL_STUDY_LIVE=1")


def _write_json(path: Path, payload: Any, *, root: Path) -> None:
    secure_capture_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        root=root,
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_payload(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        return canonical_json_text(payload)
    return canonical_json_text(payload)


def _same_payload(left: Any, right: Any) -> bool:
    return _canonical_payload(left) == _canonical_payload(right)


def verify_capture_artifact_hashes(capture_dir: Path) -> VerifiedCaptureSnapshot:
    capture_dir = capture_dir.resolve()
    if not capture_dir.is_dir():
        raise ReplayIntegrityError("capture directory is missing")
    captured_bytes: dict[str, bytes] = {}
    for path in sorted(capture_dir.rglob("*"), key=lambda item: item.as_posix()):
        mode = path.lstat().st_mode
        relative = path.relative_to(capture_dir).as_posix()
        if stat.S_ISLNK(mode):
            raise ReplayIntegrityError(f"capture package contains a symlink: {relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ReplayIntegrityError(f"capture package contains a non-regular file: {relative}")
        captured_bytes[relative] = path.read_bytes()

    if "artifact_hashes.json" not in captured_bytes:
        raise ReplayIntegrityError("artifact_hashes.json is missing")
    try:
        recorded = json.loads(captured_bytes["artifact_hashes.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayIntegrityError("artifact_hashes.json is invalid") from exc
    expected_files = recorded.get("files") if isinstance(recorded, dict) else None
    if not isinstance(expected_files, dict):
        raise ReplayIntegrityError("artifact_hashes.json is invalid")
    expected_names = set(expected_files)
    observed_names = set(captured_bytes) - {"artifact_hashes.json"}
    missing = sorted(expected_names - observed_names)
    extra_expected = missing
    extra_on_disk = sorted(observed_names - expected_names)
    mismatches = sorted(
        name
        for name in expected_names & observed_names
        if expected_files[name] != sha256_hex(captured_bytes[name])
    )
    if extra_expected:
        raise ReplayIntegrityError(f"missing file: extra expected artifact {extra_expected[0]}")
    if extra_on_disk:
        raise ReplayIntegrityError(f"missing file: {extra_on_disk[0]} is not in artifact_hashes.json")
    if mismatches:
        raise ReplayIntegrityError(f"hash mismatch: {mismatches[0]}")
    return VerifiedCaptureSnapshot(root=capture_dir, files=captured_bytes)


def verify_recorded_source_hash(provenance: dict[str, Any]) -> str:
    expected = provenance.get("expected_source_hash")
    observed = (provenance.get("observed_source_hashes") or {}).get("combined")
    if not isinstance(expected, str) or not isinstance(observed, str):
        raise ReplayIntegrityError("capture provenance source hash is missing")
    if expected != observed:
        raise ReplayIntegrityError("capture provenance source hash does not match the recorded freeze")
    return expected


def verify_current_analysis_sources(provenance: dict[str, Any]) -> int:
    """Match every capture-time source/config file against the current tree."""
    try:
        required = _load_json(REPLAY_ANALYSIS_SOURCE_FREEZE_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayIntegrityError("independent replay analysis source freeze is missing or invalid") from exc
    required_files = required.get("files") if isinstance(required, dict) else None
    required_combined = required.get("capture_source_combined") if isinstance(required, dict) else None
    if not isinstance(required_files, dict) or not required_files:
        raise ReplayIntegrityError("independent replay analysis source freeze has no files")
    if not isinstance(required_combined, str) or len(required_combined) != 64:
        raise ReplayIntegrityError("independent replay analysis source freeze hash is invalid")

    observed = provenance.get("observed_source_hashes")
    recorded_files = observed.get("files") if isinstance(observed, dict) else None
    if not isinstance(recorded_files, dict) or not recorded_files:
        raise ReplayIntegrityError("capture provenance per-file source hashes are missing")
    recorded_combined = observed.get("combined") if isinstance(observed, dict) else None
    if recorded_combined != required_combined or provenance.get("expected_source_hash") != required_combined:
        raise ReplayIntegrityError("capture provenance source hash differs from the analysis freeze")
    recorded_names = set(recorded_files)
    required_names = set(required_files)
    if recorded_names != required_names:
        missing = sorted(required_names - recorded_names)
        extra = sorted(recorded_names - required_names)
        detail = missing[0] if missing else extra[0]
        raise ReplayIntegrityError(f"capture provenance analysis source set differs: {detail}")
    if recorded_files != required_files:
        raise ReplayIntegrityError("capture provenance per-file hashes differ from the analysis freeze")

    for relative_name, expected_hash in sorted(required_files.items()):
        if not isinstance(relative_name, str) or not isinstance(expected_hash, str):
            raise ReplayIntegrityError("independent replay analysis source hashes are invalid")
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ReplayIntegrityError("analysis source path is invalid")
        source_path = REPO_ROOT
        for part in relative.parts:
            source_path = source_path / part
            if source_path.is_symlink():
                raise ReplayIntegrityError(
                    f"capture-time analysis source uses a symlink: {relative_name}"
                )
        source = source_path.resolve()
        if not source.is_relative_to(REPO_ROOT.resolve()) or not source.is_file():
            raise ReplayIntegrityError(f"capture-time analysis source is missing: {relative_name}")
        if sha256_hex(source.read_bytes()) != expected_hash:
            raise ReplayIntegrityError(f"capture-time analysis source changed: {relative_name}")
    return len(required_files)


def verify_capture_completion(snapshot: VerifiedCaptureSnapshot) -> None:
    """Refuse partial, failed, stopped, or otherwise incomplete capture packages."""
    run = snapshot.load_json("run.json")
    if not isinstance(run, dict):
        raise ReplayIntegrityError("capture run.json is invalid")
    required_run_fields = {"attempted", "failed", "unattempted", "stop_reason", "failure"}
    if not required_run_fields.issubset(run):
        raise ReplayIntegrityError("capture run status fields are missing")
    expected_ids = list(CAPTURE_ONCE_EXECUTION_IDS)
    if run.get("attempted") != expected_ids:
        raise ReplayIntegrityError("capture run attempted ids are incomplete or out of order")
    if run["failed"] != []:
        raise ReplayIntegrityError("capture run records failed executions")
    if run["unattempted"] != []:
        raise ReplayIntegrityError("capture run records unattempted executions")
    if run["stop_reason"] is not None or run["failure"] is not None:
        raise ReplayIntegrityError("capture run did not complete cleanly")

    unattempted = snapshot.load_json("captures/unattempted_prompts.json")
    if not isinstance(unattempted, dict):
        raise ReplayIntegrityError("capture unattempted-prompts record is invalid")
    if unattempted.get("unattempted_prompt_ids") != []:
        raise ReplayIntegrityError("capture package has unattempted prompts")
    if unattempted.get("stop_reason") is not None:
        raise ReplayIntegrityError("capture package stopped before completion")

    for execution_id in expected_ids:
        meta = snapshot.load_json(f"captures/{execution_id}.meta.json")
        if not isinstance(meta, dict) or meta.get("prompt_id") != execution_id:
            raise ReplayIntegrityError(f"capture metadata is invalid: {execution_id}")
        if meta.get("attempted") is not True:
            raise ReplayIntegrityError(f"capture was not attempted: {execution_id}")
        if meta.get("partial") is not False:
            raise ReplayIntegrityError(f"capture is partial: {execution_id}")
        if meta.get("truncated") is not False:
            raise ReplayIntegrityError(f"capture is truncated: {execution_id}")
        if meta.get("stop_reason") is not None:
            raise ReplayIntegrityError(f"capture stopped with a reason: {execution_id}")
        if meta.get("failures") != []:
            raise ReplayIntegrityError(f"capture records failures: {execution_id}")


def _validate_destination_separation(capture_dir: Path, destination: Path) -> None:
    capture = capture_dir.resolve()
    dest = destination.resolve()
    if dest == capture or dest.is_relative_to(capture) or capture.is_relative_to(dest):
        raise ReplayIntegrityError("replay destination must be separate from the capture directory")


def prepare_replay_dir(capture_dir: Path, output_dir: Path | None = None) -> Path:
    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = PRIVATE_REPLAY_RUNS_DIR / stamp
        suffix = 2
        while dest.exists():
            dest = PRIVATE_REPLAY_RUNS_DIR / f"{stamp}-{suffix}"
            suffix += 1
        _validate_destination_separation(capture_dir, dest)
        secure_capture_directory(dest, root=dest, exist_ok=False)
        return dest
    dest = Path(output_dir).resolve()
    _validate_destination_separation(capture_dir, dest)
    replay_root = PRIVATE_REPLAY_RUNS_DIR.resolve()
    if not dest.is_relative_to(replay_root):
        raise ReplayIntegrityError("replay destination must be under private/full-study-replay/runs")
    if dest.exists() and dest.is_file():
        raise ReplayIntegrityError(f"destination is a file: {dest}")
    if dest.exists() and any(dest.iterdir()):
        raise ReplayIntegrityError(f"destination is not empty: {dest}")
    secure_capture_directory(dest, root=dest, exist_ok=True)
    return dest


def capture_stream_ids(snapshot: VerifiedCaptureSnapshot) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    prefix = "captures/"
    for relative_name in sorted(snapshot.files):
        if not relative_name.startswith(prefix):
            continue
        name = relative_name.removeprefix(prefix)
        if "/" in name or not name.endswith(".json"):
            continue
        if name == "unattempted_prompts.json" or name.endswith(".meta.json"):
            continue
        execution_id = Path(name).stem
        if execution_id in seen:
            raise ReplayIntegrityError(f"duplicate execution id: {execution_id}")
        seen.add(execution_id)
        ids.append(execution_id)
    return ids


def validate_execution_ids(found: list[str]) -> None:
    expected = list(CAPTURE_ONCE_EXECUTION_IDS)
    found_set = set(found)
    expected_set = set(expected)
    unexpected = sorted(found_set - expected_set)
    missing = [item for item in expected if item not in found_set]
    if unexpected:
        raise ReplayIntegrityError(f"unexpected execution id: {unexpected[0]}")
    if missing:
        raise ReplayIntegrityError(f"missing execution id: {missing[0]}")
    if len(found) != len(found_set):
        raise ReplayIntegrityError("duplicate execution id")


def _load_raw_stream(snapshot: VerifiedCaptureSnapshot, execution_id: str) -> CanonicalEventStream:
    stream = CanonicalEventStream.model_validate_json(
        snapshot.read_text(f"captures/{execution_id}.json")
    )
    if stream.scenario_id != execution_id:
        raise ReplayIntegrityError(f"unexpected execution id: {stream.scenario_id}")
    if stream.detector_pass is not DetectorPass.NOT_RUN:
        raise ReplayIntegrityError(f"{execution_id} raw capture detector_pass is not not_run")
    return stream


def _load_realized_model(snapshot: VerifiedCaptureSnapshot, relative_name: str, model: type):
    return model.model_validate_json(snapshot.read_text(relative_name))


def processed_stream(
    snapshot: VerifiedCaptureSnapshot,
    execution_id: str,
    raw: CanonicalEventStream,
) -> tuple[CanonicalEventStream, str]:
    realized_name = f"realized/processed/{execution_id}.json"
    if snapshot.has(realized_name):
        processed = CanonicalEventStream.model_validate_json(
            snapshot.read_text(realized_name)
        )
        if processed.detector_pass is not DetectorPass.COMPLETED:
            raise ReplayIntegrityError(f"{execution_id} realized processed stream is not completed")
        if processed.scenario_id != execution_id:
            raise ReplayIntegrityError(f"unexpected execution id: {processed.scenario_id}")
        return processed, "realized"
    processed = apply_runtime_detectors(raw)
    return processed, "detected"


def _verify_realized(
    snapshot: VerifiedCaptureSnapshot,
    execution_id: str,
    processed: CanonicalEventStream,
    answers: FullStudyAnswerManifest,
    inventory: FullStudyCanaryInventory,
) -> None:
    realized_processed = _load_realized_model(
        snapshot,
        f"realized/processed/{execution_id}.json",
        CanonicalEventStream,
    )
    realized_answers = _load_realized_model(
        snapshot,
        f"realized/answers/{execution_id}.json",
        FullStudyAnswerManifest,
    )
    realized_canaries = _load_realized_model(
        snapshot,
        f"realized/canaries/{execution_id}.json",
        FullStudyCanaryInventory,
    )
    if not _same_payload(processed, realized_processed):
        raise ReplayIntegrityError(f"{execution_id} processed stream does not match realized artifact")
    if not _same_payload(answers, realized_answers):
        raise ReplayIntegrityError(f"{execution_id} answer manifest does not match realized artifact")
    if not _same_payload(inventory, realized_canaries):
        raise ReplayIntegrityError(f"{execution_id} canary inventory does not match realized artifact")


def _copy_question_rates(records: list[dict[str, Any]], question_id: str) -> dict[str, Any]:
    applicable = 0
    by_policy: dict[str, dict[str, int]] = {
        policy.value: {"applicable": 0, "credit": 0, "yes": 0, "no": 0, "missing": 0}
        for policy in PolicyId
    }
    seen: set[str] = set()
    for row in records:
        item = next((question for question in row["questions"] if question["id"] == question_id), None)
        if item is None or not item["applicable"]:
            continue
        if row["execution_id"] not in seen:
            seen.add(row["execution_id"])
            applicable += 1
        bucket = by_policy[row["policy_id"]]
        bucket["applicable"] += 1
        bucket["credit"] += int(item["credit"] or 0)
        extracted = item.get("extracted_status_public")
        if extracted in {"yes", "no", "missing"}:
            bucket[extracted] += 1
    return {"executions_applicable": applicable, "by_policy": by_policy}


def _case_control_differences(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in records:
        key = (row["pair_id"], row["policy_id"])
        grouped.setdefault(key, {})[row["role_in_pair"]] = row
    diffs = []
    for (pair_id, policy_id), roles in sorted(grouped.items()):
        if "case" not in roles or "control" not in roles:
            continue
        case_cov = roles["case"]["forensic_coverage"]
        control_cov = roles["control"]["forensic_coverage"]
        diffs.append(
            {
                "pair_id": pair_id,
                "policy_id": policy_id,
                "case_coverage": case_cov,
                "control_coverage": control_cov,
                "case_minus_control": (case_cov or 0) - (control_cov or 0),
            }
        )
    return diffs


def _applicability_denominators(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {question_id: 0 for question_id in FULL_STUDY_QUESTION_IDS}
    seen: set[tuple[str, str]] = set()
    for row in records:
        for question in row["questions"]:
            key = (row["execution_id"], question["id"])
            if key in seen or not question["applicable"]:
                continue
            seen.add(key)
            counts[question["id"]] += 1
    return counts


def public_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Count and status fields only. No captured text."""
    return {
        "role": ROLE,
        "label": LABEL,
        "research_evidence": True,
        "retention_validation": False,
        "protocol_version": summary.get("protocol_version"),
        "checklist_version": summary.get("checklist_version"),
        "capture_dir": summary.get("capture_dir"),
        "output_dir": summary.get("output_dir"),
        "planned_executions": summary.get("planned_executions"),
        "realized_executions": summary.get("realized_executions"),
        "planned_exports": summary.get("planned_exports"),
        "realized_exports": summary.get("realized_exports"),
        "failed_runs": len(summary.get("failed_runs") or []),
        "unresolved_credited_pointers": summary.get("unresolved_credited_pointers"),
        "ok": summary.get("ok"),
    }


def _run_replay_impl(
    capture_dir: Path,
    output_dir: Path | None,
    context: ReplayContext,
) -> dict[str, Any]:
    refuse_live_flags()
    capture_dir = Path(capture_dir)
    if not capture_dir.is_absolute():
        capture_dir = (REPO_ROOT / capture_dir).resolve()
    else:
        capture_dir = capture_dir.resolve()
    snapshot = verify_capture_artifact_hashes(capture_dir)
    provenance_in = snapshot.load_json("provenance.json")
    recorded_hash = verify_recorded_source_hash(provenance_in)
    verified_source_files = verify_current_analysis_sources(provenance_in)
    found_ids = capture_stream_ids(snapshot)
    validate_execution_ids(found_ids)
    verify_capture_completion(snapshot)
    dest = prepare_replay_dir(capture_dir, output_dir)
    context.output_dir = dest
    specs = spec_by_id()
    inventories = []
    processed_by_id: dict[str, CanonicalEventStream] = {}
    answers_by_id: dict[str, FullStudyAnswerManifest] = {}
    failures: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    unresolved = 0
    detector_runs = 0

    for execution_id in CAPTURE_ONCE_EXECUTION_IDS:
        spec = specs[execution_id]
        try:
            raw = _load_raw_stream(snapshot, execution_id)
            processed, processed_source = processed_stream(snapshot, execution_id, raw)
            if processed_source == "detected":
                detector_runs += 1
            answers = select_full_study_references(processed, spec)
            inventory = inventory_from_realized_stream(spec, processed)
            _verify_realized(snapshot, execution_id, processed, answers, inventory)
        except Exception as exc:
            failure = {
                "execution_id": execution_id,
                "stage": "load_or_verify",
                "error": f"{type(exc).__name__}",
                "reason": str(exc),
            }
            if not isinstance(exc, ReplayIntegrityError):
                failure["traceback"] = traceback.format_exc()
            failures.append(failure)
            _write_json(dest / "failures" / f"{execution_id}.json", failure, root=dest)
            continue
        inventories.append(inventory)
        processed_by_id[execution_id] = processed
        answers_by_id[execution_id] = answers
        _write_json(
            dest / "processed" / f"{execution_id}.json",
            json.loads(canonical_json_text(processed)),
            root=dest,
        )
        _write_json(
            dest / "answers" / f"{execution_id}.json",
            json.loads(answers.model_dump_json()),
            root=dest,
        )
        _write_json(
            dest / "canaries" / f"{execution_id}.json",
            json.loads(inventory.model_dump_json()),
            root=dest,
        )

    owned = all_tokens(inventories)
    for execution_id in CAPTURE_ONCE_EXECUTION_IDS:
        if execution_id not in processed_by_id:
            continue
        spec = specs[execution_id]
        processed = processed_by_id[execution_id]
        answers = answers_by_id[execution_id]
        inventory = next(item for item in inventories if item.execution_id == execution_id)
        foreign = [token for token, owner in owned.items() if owner != execution_id]
        for policy_id in PolicyId:
            try:
                export = apply_policy(processed, policy_id)
                artifact = canonical_json_text(export)
                export_path = dest / "exports" / execution_id / f"{policy_id.value}.json"
                secure_capture_write_text(export_path, artifact + "\n", root=dest)
                extraction, evaluation = extract_then_evaluate_full_study(export, answers)
                exposure = grade_exposure(
                    export,
                    CanaryInventory(
                        execution_id=inventory.execution_id,
                        eligible_canaries=inventory.eligible_canaries,
                    ),
                    foreign_tokens=foreign,
                )
                _write_json(
                    dest / "extractions" / execution_id / f"{policy_id.value}.json",
                    {
                        "facts": [
                            {
                                "question_id": fact.question_id,
                                "status": fact.status.value,
                                "value": fact.value,
                                "evidence": [
                                    {"pointer": location.pointer} for location in fact.evidence
                                ],
                            }
                            for fact in extraction.facts
                        ]
                    },
                    root=dest,
                )
                questions = []
                for reference in answers.questions:
                    score = evaluation.score(reference.id)
                    fact = next(
                        (item for item in extraction.facts if item.question_id == reference.id),
                        None,
                    )
                    pointer_checks = []
                    if fact is not None:
                        pointer_checks = [
                            {
                                "pointer": location.pointer,
                                "resolves_in_artifact": pointer_exists_in_artifact(
                                    artifact, location.pointer
                                ),
                            }
                            for location in fact.evidence
                        ]
                    if score.credit == 1 and any(
                        not item["resolves_in_artifact"] for item in pointer_checks
                    ):
                        unresolved += 1
                        raise ReplayIntegrityError(
                            f"{execution_id} {policy_id.value} {reference.id} credited pointer does not resolve"
                        )
                    extracted_public = None
                    if isinstance(score.extracted_value, str) and score.extracted_value in _SAFE_VALUES:
                        extracted_public = score.extracted_value
                    questions.append(
                        {
                            "id": reference.id,
                            "applicable": score.applicable,
                            "credit": score.credit,
                            "extracted_status": score.extracted_status,
                            "extracted_status_public": extracted_public,
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
                    "research_evidence": True,
                    "retention_validation": False,
                    "execution_id": execution_id,
                    "pair_id": spec["pair_id"],
                    "family": spec["family"],
                    "intended_family": spec["intended_family"],
                    "role_in_pair": spec["role"],
                    "source": spec["source"],
                    "policy_id": policy_id.value,
                    "processed_hash": sha256_hex(canonical_json_text(processed).encode("utf-8")),
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
                }
                _write_json(
                    dest / "results" / execution_id / f"{policy_id.value}.json",
                    record,
                    root=dest,
                )
                records.append(record)
            except Exception as exc:
                failure = {
                    "execution_id": execution_id,
                    "policy_id": policy_id.value,
                    "stage": "transform_or_grade",
                    "error": f"{type(exc).__name__}",
                    "reason": str(exc),
                }
                if not isinstance(exc, ReplayIntegrityError):
                    failure["traceback"] = traceback.format_exc()
                failures.append(failure)
                _write_json(
                    dest / "failures" / f"{execution_id}_{policy_id.value}.json",
                    failure,
                    root=dest,
                )

    realized_executions = len(processed_by_id)
    planned_exports = len(CAPTURE_ONCE_EXECUTION_IDS) * len(PolicyId)
    ok = (
        realized_executions == len(CAPTURE_ONCE_EXECUTION_IDS)
        and len(records) == planned_exports
        and not failures
        and unresolved == 0
    )
    provenance = collect_provenance()
    provenance.update(
        {
            "role": ROLE,
            "label": LABEL,
            "research_evidence": True,
            "retention_validation": False,
            "protocol_version": PROTOCOL_VERSION,
            "checklist_version": CHECKLIST_VERSION,
            "live_full_study_authorized": LIVE_FULL_STUDY_AUTHORIZED,
            "capture_dir": str(capture_dir),
            "recorded_source_hash": recorded_hash,
            "verified_capture_time_source_files": verified_source_files,
            "detector_runs": detector_runs,
        }
    )
    _write_json(dest / "provenance.json", provenance, root=dest)
    summary = {
        "role": ROLE,
        "label": LABEL,
        "research_evidence": True,
        "retention_validation": False,
        "forecast_comparison": "not_applicable",
        "protocol_version": PROTOCOL_VERSION,
        "checklist_version": CHECKLIST_VERSION,
        "capture_dir": str(capture_dir),
        "output_dir": str(dest),
        "planned_executions": len(CAPTURE_ONCE_EXECUTION_IDS),
        "realized_executions": realized_executions,
        "planned_exports": planned_exports,
        "realized_exports": len(records),
        "detector_runs": detector_runs,
        "failed_runs": [
            {key: item[key] for key in item if key != "traceback"}
            for item in failures
        ],
        "unresolved_credited_pointers": unresolved,
        "aggregates": summarize(records),
        "paired_policy_differences": paired_differences(records),
        "paired_case_control_differences": _case_control_differences(records),
        "fs16_tool_argument_copying": _copy_question_rates(records, "FS16"),
        "oc1_retrieval_to_final_output": _copy_question_rates(records, "OC1"),
        "applicability_denominators": _applicability_denominators(records),
        "ok": ok,
    }
    _write_json(dest / "summary.json", summary, root=dest)
    _write_json(dest / "summary.public.json", public_summary(summary), root=dest)
    _write_json(dest / "artifact_hashes.json", artifact_hashes(dest), root=dest)
    return summary


def _persist_unexpected_failure(output_dir: Path, exc: Exception) -> None:
    payload = {
        "role": ROLE,
        "stage": "unexpected_replay_failure",
        "error": type(exc).__name__,
        "ok": False,
    }
    try:
        _write_json(output_dir / "failures" / "unexpected.json", payload, root=output_dir)
        _write_json(output_dir / "run.failure.json", payload, root=output_dir)
        _write_json(
            output_dir / "artifact_hashes.json",
            artifact_hashes(output_dir),
            root=output_dir,
        )
    except Exception:
        # The CLI still emits only a structural error. Never print the original exception.
        pass


def run_replay(capture_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    context = ReplayContext()
    try:
        return _run_replay_impl(capture_dir, output_dir, context)
    except (ReplayIntegrityError, LiveCaptureNotAuthorized):
        raise
    except Exception as exc:
        if context.output_dir is not None:
            _persist_unexpected_failure(context.output_dir, exc)
        raise ReplayExecutionError("offline replay failed") from exc


def main(argv: list[str] | None = None) -> int:
    refuse_live_flags()
    parser = argparse.ArgumentParser(description="Replay an immutable full-study live capture offline.")
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        summary = run_replay(args.capture_dir, args.output_dir)
    except Exception as exc:
        print(json.dumps({"role": ROLE, "research_evidence": True, "ok": False, "error": type(exc).__name__}))
        return 1
    print(json.dumps(public_summary(summary), indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
