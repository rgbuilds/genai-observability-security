import json
from pathlib import Path

import pytest

from genai_observability.full_study.protocol import LIVE_FULL_STUDY_AUTHORIZED
from genai_observability.full_study.runner import run_full_study
from genai_observability.full_study.write_fixtures import write_full_study_fixtures
from genai_observability.research.capture import LiveCaptureNotAuthorized


def test_live_full_study_flag_stays_off() -> None:
    assert LIVE_FULL_STUDY_AUTHORIZED is False


def test_runner_refuses_live_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GENAI_LIVE_CAPTURE", "1")
    with pytest.raises(LiveCaptureNotAuthorized):
        run_full_study(tmp_path / "run")


def test_write_and_run_mocked_study(tmp_path: Path) -> None:
    counts = write_full_study_fixtures(tmp_path / "materialized")
    assert counts["executions"] == 48
    summary = run_full_study(tmp_path / "run")
    assert summary["planned_exports"] == 192
    assert summary["realized_exports"] == 192
    assert summary["failed_runs"] == []
    assert summary["retention_forecasts_matched"] is True
    assert summary["live_capture"] == "not_authorized"
    provenance = json.loads((tmp_path / "run" / "provenance.json").read_text())
    run_hashes = provenance["run_input_hashes"]
    assert len(run_hashes["files"]) == 144
    assert any(name.startswith("streams/") for name in run_hashes["files"])
    assert any(name.startswith("answers/") for name in run_hashes["files"])
    assert any(name.startswith("canaries/") for name in run_hashes["files"])
    assert summary["provenance"]["run_inputs_combined"] == run_hashes["combined"]
    assert (tmp_path / "run" / "failures").exists() is False or not any(
        (tmp_path / "run" / "failures").iterdir()
    )
