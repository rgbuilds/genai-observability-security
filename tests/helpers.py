from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.span import CanonicalSpan

CANARY = "SYNTH-USERIN-A1B2C3D4"
CANARY_B = "SYNTH-TOOLARG-DEADBEEF"
SECRET_CANARY = "SYNTH-SECRET-DEADBEEF"


def minimal_span(**updates) -> CanonicalSpan:
    payload = {
        "span_id": "span-0001",
        "parent_span_id": None,
        "name": "handle_request",
        "kind": "request",
        "start_time": "2026-10-04T22:00:00.000Z",
        "end_time": "2026-10-04T22:00:00.120Z",
        "duration_ms": 120,
        "status": "ok",
        "status_code": 200,
    }
    payload.update(updates)
    return CanonicalSpan.model_validate(payload)


def stream_from_spans(*spans: CanonicalSpan) -> CanonicalEventStream:
    return CanonicalEventStream(
        scenario_id="scenario-0001",
        request_id="req-0001",
        trace_id="trace-0001",
        spans=list(spans),
    )
