import json

import pytest

from genai_observability.grading.references import load_all_canary_inventories
from genai_observability.paths import FIXTURE_DIR, POLICY_ALLOWLIST_DIR, REPO_ROOT
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_hash, sha256_hex
from genai_observability.sources import FixtureSource
from genai_observability.validation.provenance import collect_provenance, hash_paths
from genai_observability.validation.run_pilot import (
    NonemptyDestinationError,
    _run_one,
    prepare_output_dir,
)


def test_prepare_output_dir_refuses_nonempty_destination(tmp_path) -> None:
    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "already.json").write_text("{}", encoding="utf-8")
    with pytest.raises(NonemptyDestinationError, match="not empty"):
        prepare_output_dir(dest)


def test_prepare_output_dir_accepts_empty_explicit_destination(tmp_path) -> None:
    dest = tmp_path / "empty"
    dest.mkdir()
    assert prepare_output_dir(dest) == dest


def test_default_run_directories_are_unique(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "genai_observability.validation.run_pilot.VALIDATION_RUNS_DIR",
        tmp_path / "runs",
    )
    first = prepare_output_dir()
    second = prepare_output_dir()
    assert first != second
    assert first.is_dir() and second.is_dir()
    assert not any(first.iterdir())
    assert not any(second.iterdir())


def test_provenance_includes_configuration_and_source_hashes() -> None:
    provenance = collect_provenance()
    allowlist = next(POLICY_ALLOWLIST_DIR.glob("*.json"))
    rel = allowlist.relative_to(REPO_ROOT).as_posix()
    assert isinstance(provenance["git_dirty"], bool)
    assert provenance["git_commit"]
    assert provenance["configuration_hashes"]["files"][rel] == sha256_hex(allowlist.read_bytes())
    assert provenance["source_hashes"]["files"]
    assert provenance["reference_hashes"]["files"]
    assert hash_paths([allowlist])["combined"]


def test_written_result_includes_fixture_and_processed_hashes(tmp_path) -> None:
    source = FixtureSource(FIXTURE_DIR)
    raw = source.load("exec-12")
    processed = apply_runtime_detectors(raw)
    fixture_hash = canonical_hash(raw)
    processed_hash = canonical_hash(processed)
    record = _run_one(
        execution_id="exec-12",
        policy_id=PolicyId.P0,
        processed=processed,
        output_dir=tmp_path,
        inventories=load_all_canary_inventories(),
        fixture_hash=fixture_hash,
        processed_hash=processed_hash,
    )
    saved = json.loads((tmp_path / "results" / "exec-12" / "P0.json").read_text(encoding="utf-8"))
    assert saved["fixture_hash"] == fixture_hash
    assert saved["processed_hash"] == processed_hash
    assert saved["canonical_hash"] == processed_hash
    assert record["fixture_hash"] == fixture_hash
    assert fixture_hash != processed_hash
