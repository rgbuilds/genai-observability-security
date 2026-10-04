import pytest

from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import DetectorPass, PolicyId
from genai_observability.serialization import canonical_json_text
from genai_observability.transforms import UnprocessedStreamError, apply_policy
from tests.helpers import CANARY, minimal_span, stream_from_spans


def test_unprocessed_stream_is_rejected_even_with_empty_or_planted_events() -> None:
    empty = stream_from_spans(minimal_span(content={"user": "no match"}))
    planted = stream_from_spans(
        minimal_span(
            content={"user": f"hello {CANARY}"},
            detector_events=[
                {
                    "detector_id": "fixture-supplied",
                    "category": "sensitive_data",
                    "stage": "user_input",
                    "match_class": "schema_sample",
                }
            ],
        )
    )
    assert empty.detector_pass is DetectorPass.NOT_RUN
    assert planted.detector_pass is DetectorPass.NOT_RUN
    for stream in (empty, planted):
        with pytest.raises(UnprocessedStreamError, match="completed runtime detector pass"):
            apply_policy(stream, PolicyId.P1)


def test_p0_omits_detector_events_after_detection() -> None:
    processed = apply_runtime_detectors(
        stream_from_spans(minimal_span(content={"user": f"hello {CANARY}"}))
    )
    export = apply_policy(processed, PolicyId.P0)
    dumped = export.model_dump(mode="json", exclude_none=True)
    text = canonical_json_text(export)
    assert export.spans[0].detector_events is None
    assert "detector_events" not in dumped["spans"][0]
    assert "detector_events" not in text
    assert "detector_pass" not in dumped


def test_p1_p2_p3_retain_empty_list_when_detector_found_nothing() -> None:
    processed = apply_runtime_detectors(
        stream_from_spans(minimal_span(content={"user": "no library match"}))
    )
    assert processed.detector_pass is DetectorPass.COMPLETED
    assert processed.spans[0].detector_events == []
    for policy in (PolicyId.P1, PolicyId.P2, PolicyId.P3):
        export = apply_policy(processed, policy)
        dumped = export.model_dump(mode="json", exclude_none=True)
        assert export.spans[0].detector_events == []
        assert dumped["spans"][0]["detector_events"] == []


def test_p1_p2_p3_retain_populated_list_after_detection() -> None:
    processed = apply_runtime_detectors(
        stream_from_spans(minimal_span(content={"user": f"hello {CANARY}"}))
    )
    assert processed.spans[0].detector_events
    for policy in (PolicyId.P1, PolicyId.P2, PolicyId.P3):
        export = apply_policy(processed, policy)
        dumped = export.model_dump(mode="json", exclude_none=True)
        events = dumped["spans"][0]["detector_events"]
        assert events == [
            {
                "detector_id": "patternlib.v1.canary_grammar",
                "category": "sensitive_data",
                "stage": "user_input",
                "match_class": "canary_grammar",
            }
        ]


def test_transform_does_not_mark_detector_pass_or_rerun_detection() -> None:
    raw = stream_from_spans(minimal_span(content={"user": f"hello {CANARY}"}))
    processed = apply_runtime_detectors(raw)
    before = [event.model_dump(mode="json") for event in processed.spans[0].detector_events or []]
    apply_policy(processed, PolicyId.P1)
    after = [event.model_dump(mode="json") for event in processed.spans[0].detector_events or []]
    assert raw.detector_pass is DetectorPass.NOT_RUN
    assert processed.detector_pass is DetectorPass.COMPLETED
    assert before == after
