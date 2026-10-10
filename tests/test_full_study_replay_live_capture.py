import json
from pathlib import Path

import pytest

from genai_observability.full_study.fixtures import build_stream
from genai_observability.full_study.inventory import inventory_from_realized_stream
from genai_observability.full_study.live_adapter import artifact_hashes
from genai_observability.full_study.protocol import LIVE_ENV_FLAG
from genai_observability.full_study.replay_live_capture import (
    REPLAY_ANALYSIS_SOURCE_FREEZE_PATH,
    ReplayExecutionError,
    ReplayIntegrityError,
    main,
    public_summary,
    refuse_live_flags,
    run_replay,
    verify_capture_artifact_hashes,
)
from genai_observability.full_study.scenarios import CAPTURE_ONCE_EXECUTION_IDS, capture_once_specs
from genai_observability.full_study.select import select_full_study_references
from genai_observability.research.capture import LiveCaptureNotAuthorized, LiveOpenAIClient
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.serialization import canonical_json_text


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _tree_hashes(root: Path) -> dict[str, str]:
    from genai_observability.serialization import sha256_hex

    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = sha256_hex(path.read_bytes())
    return files


@pytest.fixture
def replay_root(tmp_path: Path, monkeypatch) -> Path:
    from genai_observability.full_study import replay_live_capture

    root = tmp_path / "private" / "full-study-replay" / "runs"
    monkeypatch.setattr(replay_live_capture, "PRIVATE_REPLAY_RUNS_DIR", root)
    return root


def write_synthetic_capture(root: Path) -> Path:
    """Copy scripted fixtures into a capture-shaped directory. Never touches live captures."""
    capture = root / "capture"
    for spec in capture_once_specs():
        execution_id = spec["execution_id"]
        raw = build_stream(spec)
        processed = apply_runtime_detectors(raw)
        answers = select_full_study_references(processed, spec)
        inventory = inventory_from_realized_stream(spec, processed)
        _write(capture / "captures" / f"{execution_id}.json", json.loads(canonical_json_text(raw)))
        _write(
            capture / "captures" / f"{execution_id}.meta.json",
            {
                "prompt_id": execution_id,
                "attempted": True,
                "partial": False,
                "stop_reason": None,
                "truncated": False,
                "requests_used": 1,
                "failures": [],
            },
        )
        _write(
            capture / "realized" / "processed" / f"{execution_id}.json",
            json.loads(canonical_json_text(processed)),
        )
        _write(
            capture / "realized" / "answers" / f"{execution_id}.json",
            json.loads(answers.model_dump_json()),
        )
        _write(
            capture / "realized" / "canaries" / f"{execution_id}.json",
            json.loads(inventory.model_dump_json()),
        )
    _write(
        capture / "captures" / "unattempted_prompts.json",
        {"unattempted_prompt_ids": [], "stop_reason": None, "requests_used": 24},
    )
    source_freeze = json.loads(REPLAY_ANALYSIS_SOURCE_FREEZE_PATH.read_text(encoding="utf-8"))
    _write(
        capture / "provenance.json",
        {
            "protocol_version": "full-study-protocol.v1",
            "expected_source_hash": source_freeze["capture_source_combined"],
            "observed_source_hashes": {
                "combined": source_freeze["capture_source_combined"],
                "files": source_freeze["files"],
            },
            "role": "full-study-live-capture",
        },
    )
    _write(
        capture / "run.json",
        {
            "attempted": list(CAPTURE_ONCE_EXECUTION_IDS),
            "failed": [],
            "unattempted": [],
            "stop_reason": None,
            "failure": None,
        },
    )
    _write(capture / "artifact_hashes.json", artifact_hashes(capture))
    return capture


def test_replay_refuses_live_env_flags(monkeypatch) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    refuse_live_flags()
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    with pytest.raises(LiveCaptureNotAuthorized, match="GENAI_FULL_STUDY_LIVE"):
        refuse_live_flags()
    monkeypatch.delenv(LIVE_ENV_FLAG)
    monkeypatch.setenv("GENAI_LIVE_CAPTURE", "1")
    with pytest.raises(LiveCaptureNotAuthorized, match="GENAI_LIVE_CAPTURE"):
        refuse_live_flags()
    with pytest.raises(LiveCaptureNotAuthorized, match="GENAI_LIVE_CAPTURE"):
        main(["--capture-dir", "unused"])


def test_replay_constructs_no_client_and_imports_no_http(monkeypatch) -> None:
    import sys

    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    sys.modules.pop("genai_observability.research.live_http", None)
    from genai_observability.full_study import replay_live_capture

    assert "genai_observability.research.live_http" not in sys.modules
    constructed = {"count": 0}

    class Boom(LiveOpenAIClient):
        def __init__(self, *args, **kwargs) -> None:
            constructed["count"] += 1
            raise AssertionError("live client must not be constructed")

    monkeypatch.setattr("genai_observability.research.capture.LiveOpenAIClient", Boom)
    monkeypatch.setattr(replay_live_capture, "LiveOpenAIClient", Boom, raising=False)
    assert constructed["count"] == 0


def test_replay_keeps_capture_immutable_and_writes_96_exports(
    tmp_path: Path, replay_root: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    capture = write_synthetic_capture(tmp_path)
    before = _tree_hashes(capture)
    detector_calls = {"count": 0}
    original = apply_runtime_detectors

    def counted(stream):
        detector_calls["count"] += 1
        return original(stream)

    monkeypatch.setattr(
        "genai_observability.full_study.replay_live_capture.apply_runtime_detectors",
        counted,
    )
    dest = replay_root / "replay"
    summary = run_replay(capture, dest)
    assert before == _tree_hashes(capture)
    assert detector_calls["count"] == 0
    assert summary["planned_exports"] == 96
    assert summary["realized_exports"] == 96
    assert summary["research_evidence"] is True
    assert summary["retention_validation"] is False
    assert summary["forecast_comparison"] == "not_applicable"
    assert summary["ok"] is True
    export_files = list((dest / "exports").rglob("P*.json"))
    assert len(export_files) == 96
    assert (dest / "artifact_hashes.json").is_file()
    assert oct(dest.stat().st_mode)[-3:] == "700"
    assert oct((dest / "summary.json").stat().st_mode)[-3:] == "600"
    printed = json.dumps(public_summary(summary))
    assert "SYNTH-" not in printed
    assert "note-f" not in printed
    assert "tool_args" not in printed
    assert "sk-" not in printed
    status = main(
        ["--capture-dir", str(capture), "--output-dir", str(replay_root / "replay-cli")]
    )
    output = capsys.readouterr().out
    assert status == 0
    assert "SYNTH-" not in output
    assert "note-f" not in output


def test_hash_refusal_and_nonzero_status(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    capture = write_synthetic_capture(tmp_path)
    missing = write_synthetic_capture(tmp_path / "missing")
    (missing / "captures" / "fs-f1c-case.json").unlink()
    with pytest.raises(ReplayIntegrityError, match="extra expected artifact"):
        verify_capture_artifact_hashes(missing)
    changed = write_synthetic_capture(tmp_path / "changed")
    target = changed / "captures" / "fs-f1c-ctrl.meta.json"
    payload = json.loads(target.read_text())
    payload["requests_used"] = 99
    target.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ReplayIntegrityError, match="hash mismatch"):
        verify_capture_artifact_hashes(changed)
    extra = write_synthetic_capture(tmp_path / "extra")
    manifest = json.loads((extra / "artifact_hashes.json").read_text())
    manifest["files"]["captures/not-a-real-id.json"] = "b" * 64
    (extra / "artifact_hashes.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with pytest.raises(ReplayIntegrityError, match="extra expected artifact"):
        verify_capture_artifact_hashes(extra)
    (capture / "artifact_hashes.json").unlink()
    assert main(["--capture-dir", str(capture)]) == 1
    assert "SYNTH-" not in capsys.readouterr().out


def test_execution_id_validation(tmp_path: Path, replay_root: Path, monkeypatch) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    missing = write_synthetic_capture(tmp_path / "missing-id")
    (missing / "captures" / "fs-f6d-ctrl.json").unlink()
    manifest = artifact_hashes(missing)
    (missing / "artifact_hashes.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with pytest.raises(ReplayIntegrityError, match="missing execution id"):
        run_replay(missing, replay_root / "out-missing")
    unexpected = write_synthetic_capture(tmp_path / "unexpected")
    extra = json.loads((unexpected / "captures" / "fs-f1c-case.json").read_text())
    extra["scenario_id"] = "fs-f1a-case"
    _write(unexpected / "captures" / "fs-f1a-case.json", extra)
    (unexpected / "artifact_hashes.json").write_text(
        json.dumps(artifact_hashes(unexpected), indent=2) + "\n"
    )
    with pytest.raises(ReplayIntegrityError, match="unexpected execution id"):
        run_replay(unexpected, replay_root / "out-unexpected")


def test_replay_refuses_capture_failures_and_partial_metadata(
    tmp_path: Path, replay_root: Path, monkeypatch
) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)

    failed = write_synthetic_capture(tmp_path / "failed")
    run_path = failed / "run.json"
    run_payload = json.loads(run_path.read_text())
    run_payload["failed"] = ["fs-f1c-case"]
    _write(run_path, run_payload)
    _write(failed / "artifact_hashes.json", artifact_hashes(failed))
    failed_dest = replay_root / "failed-replay"
    with pytest.raises(ReplayIntegrityError, match="failed executions"):
        run_replay(failed, failed_dest)
    assert not failed_dest.exists()

    partial = write_synthetic_capture(tmp_path / "partial")
    meta_path = partial / "captures" / "fs-f1c-case.meta.json"
    meta_payload = json.loads(meta_path.read_text())
    meta_payload["partial"] = True
    meta_payload["failures"] = ["transport_error"]
    _write(meta_path, meta_payload)
    _write(partial / "artifact_hashes.json", artifact_hashes(partial))
    partial_dest = replay_root / "partial-replay"
    with pytest.raises(ReplayIntegrityError, match="partial"):
        run_replay(partial, partial_dest)
    assert not partial_dest.exists()


def test_replay_refuses_changed_capture_time_analysis_source(
    tmp_path: Path, replay_root: Path, monkeypatch
) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    capture = write_synthetic_capture(tmp_path)
    provenance_path = capture / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    source_name = next(iter(provenance["observed_source_hashes"]["files"]))
    provenance["observed_source_hashes"]["files"][source_name] = "0" * 64
    _write(provenance_path, provenance)
    _write(capture / "artifact_hashes.json", artifact_hashes(capture))
    dest = replay_root / "replay"
    with pytest.raises(ReplayIntegrityError, match="per-file hashes differ"):
        run_replay(capture, dest)
    assert not dest.exists()

    missing = write_synthetic_capture(tmp_path / "missing-source")
    provenance_path = missing / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["observed_source_hashes"]["files"].pop(
        next(iter(provenance["observed_source_hashes"]["files"]))
    )
    _write(provenance_path, provenance)
    _write(missing / "artifact_hashes.json", artifact_hashes(missing))
    with pytest.raises(ReplayIntegrityError, match="source set differs"):
        run_replay(missing, replay_root / "missing-source-replay")


def test_replay_refuses_destination_overlap(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    capture = write_synthetic_capture(tmp_path)
    before = _tree_hashes(capture)
    nested = capture / "replay-output"
    with pytest.raises(ReplayIntegrityError, match="separate from the capture"):
        run_replay(capture, nested)
    assert not nested.exists()
    assert _tree_hashes(capture) == before

    with pytest.raises(ReplayIntegrityError, match="separate from the capture"):
        run_replay(capture, capture.parent)
    assert _tree_hashes(capture) == before

    with pytest.raises(ReplayIntegrityError, match="under private/full-study-replay/runs"):
        run_replay(capture, tmp_path / "public-output")
    assert not (tmp_path / "public-output").exists()


def test_replay_rejects_symlinks_and_consumes_verified_snapshot(
    tmp_path: Path, replay_root: Path, monkeypatch
) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    linked = write_synthetic_capture(tmp_path / "linked")
    linked_file = linked / "captures" / "fs-f1c-case.json"
    external = tmp_path / "external.json"
    external.write_bytes(linked_file.read_bytes())
    linked_file.unlink()
    linked_file.symlink_to(external)
    with pytest.raises(ReplayIntegrityError, match="symlink"):
        run_replay(linked, replay_root / "linked-replay")

    captured_once = write_synthetic_capture(tmp_path / "snapshot")
    target = captured_once / "captures" / "fs-f1c-case.json"
    from genai_observability.full_study import replay_live_capture

    original_verify = replay_live_capture.verify_current_analysis_sources

    def mutate_after_snapshot(provenance):
        result = original_verify(provenance)
        target.write_text("{}\n", encoding="utf-8")
        return result

    monkeypatch.setattr(
        replay_live_capture,
        "verify_current_analysis_sources",
        mutate_after_snapshot,
    )
    summary = run_replay(captured_once, replay_root / "snapshot-replay")
    assert summary["ok"] is True
    assert target.read_text(encoding="utf-8") == "{}\n"


def test_unexpected_failure_is_sanitized_and_persisted(
    tmp_path: Path, replay_root: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    capture = write_synthetic_capture(tmp_path)
    from genai_observability.full_study import replay_live_capture

    def fail_with_sensitive_text():
        raise RuntimeError("SYNTH-SECRET-DEADBEEF sk-private note-body tool_args")

    monkeypatch.setattr(replay_live_capture, "spec_by_id", fail_with_sensitive_text)
    destination = replay_root / "failed-replay"
    with pytest.raises(ReplayExecutionError, match="offline replay failed"):
        run_replay(capture, destination)
    failure = json.loads((destination / "run.failure.json").read_text())
    assert failure["error"] == "RuntimeError"
    assert "reason" not in failure
    assert (destination / "failures" / "unexpected.json").is_file()
    assert (destination / "artifact_hashes.json").is_file()
    assert oct(destination.stat().st_mode)[-3:] == "700"
    assert oct((destination / "run.failure.json").stat().st_mode)[-3:] == "600"

    cli_destination = replay_root / "failed-replay-cli"
    assert main(
        ["--capture-dir", str(capture), "--output-dir", str(cli_destination)]
    ) == 1
    output = capsys.readouterr().out
    assert "SYNTH-" not in output
    assert "sk-private" not in output
    assert "note-body" not in output
    assert "tool_args" not in output
    assert "Traceback" not in output


def test_credited_pointer_failure_is_nonzero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    monkeypatch.delenv("GENAI_LIVE_CAPTURE", raising=False)
    capture = write_synthetic_capture(tmp_path)
    monkeypatch.setattr(
        "genai_observability.full_study.replay_live_capture.pointer_exists_in_artifact",
        lambda *_args, **_kwargs: False,
    )
    from genai_observability.full_study import replay_live_capture

    replay_root = tmp_path / "private" / "full-study-replay" / "runs"
    monkeypatch.setattr(replay_live_capture, "PRIVATE_REPLAY_RUNS_DIR", replay_root)
    destination = replay_root / "replay"
    summary = run_replay(capture, destination)
    assert summary["ok"] is False
    assert summary["failed_runs"]
    assert (destination / "failures").exists()
    assert _tree_hashes(capture) == _tree_hashes(capture)
