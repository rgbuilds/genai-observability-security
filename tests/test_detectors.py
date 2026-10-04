from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import DetectorStage, PolicyId
from genai_observability.serialization import canonical_json_text
from genai_observability.transforms import apply_policy
from tests.helpers import CANARY, SECRET_CANARY, minimal_span, stream_from_spans


def test_runtime_detectors_replace_fixture_events_and_do_not_mutate_source() -> None:
    planted = [
        {
            "detector_id": "fixture-supplied",
            "category": "sensitive_data",
            "stage": "user_input",
            "match_class": "schema_sample",
        }
    ]
    stream = stream_from_spans(
        minimal_span(
            content={"user": f"hello {CANARY}"},
            detector_events=planted,
        )
    )
    enriched = apply_runtime_detectors(stream)
    assert stream.spans[0].detector_events is not None
    assert stream.spans[0].detector_events[0].match_class == "schema_sample"
    assert enriched.spans[0].detector_events is not None
    assert [event.match_class for event in enriched.spans[0].detector_events] == ["canary_grammar"]
    assert enriched.spans[0].detector_events[0].stage is DetectorStage.USER_INPUT
    assert enriched.spans[0].detector_events[0].detector_id == "patternlib.v1.canary_grammar"


def test_authorization_stage_for_authz_payload() -> None:
    stream = stream_from_spans(
        minimal_span(authz={"principal_id": CANARY, "roles": ["reader"]})
    )
    enriched = apply_runtime_detectors(stream)
    events = enriched.spans[0].detector_events
    assert events is not None
    assert len(events) == 1
    assert events[0].stage is DetectorStage.AUTHORIZATION
    assert events[0].match_class == "canary_grammar"


def test_secret_key_and_canary_hits_are_deduped_by_stage_and_class() -> None:
    stream = stream_from_spans(
        minimal_span(
            content={
                "tool_args": {
                    "api_key": SECRET_CANARY,
                    "note_id": f"see {CANARY}",
                }
            }
        )
    )
    detected = apply_runtime_detectors(stream).spans[0].detector_events
    assert detected is not None
    events = detected
    classes = sorted(event.match_class for event in events)
    assert classes == ["canary_grammar", "secret_key"]
    assert all(event.stage is DetectorStage.TOOL_ARGS for event in events)
    assert all(event.category.value == "sensitive_data" for event in events)


def test_detector_events_omit_raw_canaries_and_sensitive_keys() -> None:
    stream = stream_from_spans(
        minimal_span(
            content={"tool_args": {"user_password": SECRET_CANARY, CANARY: "x"}},
            authz={"resource": CANARY},
        )
    )
    enriched = apply_runtime_detectors(stream)
    assert enriched.spans[0].detector_events is not None
    all_events = canonical_json_text(
        {"events": [event.model_dump(mode="json") for event in enriched.spans[0].detector_events]}
    )
    assert CANARY not in all_events
    assert SECRET_CANARY not in all_events
    assert "user_password" not in all_events
    for event in enriched.spans[0].detector_events:
        dumped = canonical_json_text(event)
        assert CANARY not in dumped
        assert SECRET_CANARY not in dumped
        assert "user_password" not in dumped


def test_detectors_do_not_scan_retain_only_fields() -> None:
    stream = stream_from_spans(
        minimal_span(
            name=CANARY,
            tool={"name": CANARY, "type": "read"},
            retrieval={"source_id": CANARY},
            content={"user": "no token here"},
        )
    )
    enriched = apply_runtime_detectors(stream)
    assert enriched.spans[0].detector_events == []


def test_policies_share_enriched_stream_and_transforms_do_not_rerun_detectors() -> None:
    stream = stream_from_spans(
        minimal_span(
            content={"user": f"hello {CANARY}"},
            detector_events=[],
        )
    )
    enriched = apply_runtime_detectors(stream)
    p0 = apply_policy(enriched, PolicyId.P0)
    p1 = apply_policy(enriched, PolicyId.P1)
    p2 = apply_policy(enriched, PolicyId.P2)
    p3 = apply_policy(enriched, PolicyId.P3)
    expected = enriched.spans[0].detector_events
    assert p0.spans[0].detector_events is None
    assert p1.spans[0].detector_events == expected
    assert p2.spans[0].detector_events == expected
    assert p3.spans[0].detector_events == expected
    assert p2.spans[0].content is not None
    assert p2.spans[0].content.user == "hello [REDACTED:canary_grammar]"


def test_propagation_detector_is_not_emitted() -> None:
    stream = stream_from_spans(
        minimal_span(content={"retrieved": CANARY}),
        minimal_span(
            span_id="span-0002",
            parent_span_id="span-0001",
            name="chat.completion",
            kind="model",
            content={"output": f"repeat {CANARY}"},
        ),
    )
    enriched = apply_runtime_detectors(stream)
    categories = {
        event.category.value
        for span in enriched.spans
        for event in span.detector_events or []
    }
    assert categories == {"sensitive_data"}
