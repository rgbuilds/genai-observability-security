import pytest
from pydantic import ValidationError

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import PolicyId
from genai_observability.schemas.export import TelemetryExport
from genai_observability.schemas.span import CanonicalSpan


def _span_payload() -> dict:
    return {
        "span_id": "span-0001",
        "name": "handle_request",
        "kind": "request",
        "start_time": "2026-10-04T22:00:00Z",
        "end_time": "2026-10-04T22:00:00.120Z",
        "duration_ms": 120,
        "status": "ok",
    }


def test_valid_canonical_stream_parses(sample_stream: CanonicalEventStream) -> None:
    assert sample_stream.schema_version == "canonical_event_stream.v1"
    assert sample_stream.scenario_id == "scenario-0001"
    assert len(sample_stream.spans) == 4
    assert sample_stream.spans[0].security is not None
    assert sample_stream.spans[2].detector_events[0].category.value == "sensitive_data"


def test_valid_export_envelope_parses(sample_stream: CanonicalEventStream) -> None:
    export = TelemetryExport(
        policy_id=PolicyId.P0,
        policy_version="1",
        request_id=sample_stream.request_id,
        trace_id=sample_stream.trace_id,
        spans=[
            CanonicalSpan(
                span_id=sample_stream.spans[0].span_id,
                parent_span_id=sample_stream.spans[0].parent_span_id,
                name=sample_stream.spans[0].name,
                kind=sample_stream.spans[0].kind,
                start_time=sample_stream.spans[0].start_time,
                end_time=sample_stream.spans[0].end_time,
                duration_ms=sample_stream.spans[0].duration_ms,
                status=sample_stream.spans[0].status,
                status_code=sample_stream.spans[0].status_code,
            )
        ],
    )
    assert export.schema_version == "telemetry_export.v1"
    assert export.spans[0].content is None
    assert export.spans[0].security is None
    assert export.spans[0].detector_events == []


def test_missing_required_field_is_rejected() -> None:
    payload = {
        "schema_version": "canonical_event_stream.v1",
        "scenario_id": "scenario-0001",
        "trace_id": "trace-0001",
        "spans": [_span_payload()],
    }
    with pytest.raises(ValidationError):
        CanonicalEventStream.model_validate(payload)


def test_invalid_enum_is_rejected() -> None:
    payload = _span_payload() | {"kind": "detector"}
    with pytest.raises(ValidationError):
        CanonicalSpan.model_validate(payload)


def test_invalid_timestamp_is_rejected() -> None:
    payload = _span_payload() | {"start_time": "2026-10-04 22:00:00"}
    with pytest.raises(ValidationError):
        CanonicalSpan.model_validate(payload)


def test_forbidden_expected_labels_are_rejected() -> None:
    for key in ("incident_type", "variant_class", "expected_q15"):
        payload = {
            "schema_version": "canonical_event_stream.v1",
            "scenario_id": "scenario-0001",
            "request_id": "req-0001",
            "trace_id": "trace-0001",
            "spans": [_span_payload()],
            key: "security_relevant",
        }
        with pytest.raises(ValidationError):
            CanonicalEventStream.model_validate(payload)


def test_forbidden_label_inside_tool_args_is_rejected() -> None:
    payload = _span_payload()
    payload["content"] = {"tool_args": {"incident_type": "prompt_injection"}}
    with pytest.raises(ValidationError):
        CanonicalSpan.model_validate(payload)
