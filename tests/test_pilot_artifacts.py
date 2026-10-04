import json
from pathlib import Path

import pytest

from genai_observability.grading.questions import QUESTION_IDS
from genai_observability.grading.references import (
    PILOT_EXECUTION_IDS,
    load_answer_manifest,
    load_canary_inventory,
)
from genai_observability.paths import FIXTURE_DIR
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import DetectorPass, PolicyId
from genai_observability.serialization import canonical_hash
from genai_observability.sources import FixtureSource
from genai_observability.transforms import UnprocessedStreamError, apply_policy
from tests.helpers import CANARY


def _payload_contains(stream, payload_field: str, token: str) -> bool:
    group_name, attr = payload_field.split(".", 1)
    for span in stream.spans:
        group = getattr(span, group_name)
        if group is None:
            continue
        value = getattr(group, attr)
        if value is not None and token in json.dumps(value, ensure_ascii=False):
            return True
    return False


def test_ten_execution_fixtures_load_and_hash_stably() -> None:
    source = FixtureSource(FIXTURE_DIR)
    assert len(PILOT_EXECUTION_IDS) == 10
    for execution_id in PILOT_EXECUTION_IDS:
        first = source.load(execution_id)
        second = source.load(execution_id)
        assert first.scenario_id == execution_id
        assert first.detector_pass is DetectorPass.NOT_RUN
        assert canonical_hash(first) == canonical_hash(second)


def test_canary_and_answer_manifests_are_separate_and_complete() -> None:
    for execution_id in PILOT_EXECUTION_IDS:
        inventory = load_canary_inventory(execution_id)
        answers = load_answer_manifest(execution_id)
        assert inventory.execution_id == execution_id
        assert answers.execution_id == execution_id
        assert [question.id for question in answers.questions] == list(QUESTION_IDS)
        assert answers.question("Q15").answer == answers.q15_expected


def test_planted_canaries_match_registered_payload_fields() -> None:
    source = FixtureSource(FIXTURE_DIR)
    for execution_id in PILOT_EXECUTION_IDS:
        stream = source.load(execution_id)
        inventory = load_canary_inventory(execution_id)
        for canary in inventory.eligible_canaries:
            assert canary.eligible is True
            assert _payload_contains(stream, canary.payload_field, canary.token)


def test_loading_fixture_cannot_bypass_detectors_with_completed_pass(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "canonical_event_stream.v1",
        "scenario_id": "exec-bypass",
        "request_id": "req-bypass",
        "trace_id": "trace-bypass",
        "detector_pass": "completed",
        "spans": [
            {
                "span_id": "span-0001",
                "name": "handle_request",
                "kind": "request",
                "start_time": "2026-10-04T22:00:00.000Z",
                "end_time": "2026-10-04T22:00:00.120Z",
                "duration_ms": 120,
                "status": "ok",
                "status_code": 200,
                "content": {"user": f"hello {CANARY}"},
                "detector_events": [],
            }
        ],
    }
    path = tmp_path / "exec-bypass.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    stream = FixtureSource(tmp_path).load("exec-bypass")

    assert stream.detector_pass is DetectorPass.NOT_RUN
    assert stream.spans[0].detector_events == []
    with pytest.raises(UnprocessedStreamError):
        apply_policy(stream, PolicyId.P1)

    processed = apply_runtime_detectors(stream)
    export = apply_policy(processed, PolicyId.P1)
    assert processed.detector_pass is DetectorPass.COMPLETED
    assert export.spans[0].detector_events
    assert export.spans[0].detector_events[0].match_class == "canary_grammar"


def test_fixtures_do_not_embed_expected_labels() -> None:
    source = FixtureSource(FIXTURE_DIR)
    forbidden = ("incident_type", "variant_class", "expected_q15", "security_relevant")
    for execution_id in PILOT_EXECUTION_IDS:
        text = json.dumps(source.load(execution_id).model_dump(mode="json"), ensure_ascii=False)
        for token in forbidden:
            assert token not in text
        assert "F1" not in execution_id
