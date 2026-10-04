from copy import deepcopy

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_hash, canonical_json_text
from genai_observability.transforms import apply_policy
from tests.helpers import stream_from_spans, minimal_span


def _dumped_spans(stream: CanonicalEventStream, policy: PolicyId) -> list[dict]:
    export = apply_policy(stream, policy)
    return export.model_dump(mode="json", exclude_none=True)["spans"]


def test_parent_linkage_preserved_for_every_policy(sample_stream: CanonicalEventStream) -> None:
    expected = [(span.span_id, span.parent_span_id) for span in sample_stream.spans]
    for policy in PolicyId:
        exported = [(span["span_id"], span.get("parent_span_id")) for span in _dumped_spans(sample_stream, policy)]
        assert exported == expected


def test_transform_does_not_mutate_source(sample_stream: CanonicalEventStream) -> None:
    before = sample_stream.model_copy(deep=True)
    for policy in PolicyId:
        apply_policy(sample_stream, policy)
    assert sample_stream == before


def test_transform_output_is_deterministic(sample_stream: CanonicalEventStream) -> None:
    for policy in PolicyId:
        first = apply_policy(sample_stream, policy)
        second = apply_policy(sample_stream, policy)
        assert canonical_hash(first) == canonical_hash(second)


def test_p0_keeps_metadata_and_drops_forbidden_groups(sample_stream: CanonicalEventStream) -> None:
    spans = _dumped_spans(sample_stream, PolicyId.P0)
    assert {span["span_id"] for span in spans} == {span.span_id for span in sample_stream.spans}
    for span in spans:
        assert "content" not in span
        assert "authz" not in span
        assert "retrieval" not in span
        assert "security" not in span
        assert span.get("detector_events", []) == []
        assert "name" in span
        assert "kind" in span
        assert "status" in span


def test_p1_retains_content_and_drops_security(sample_stream: CanonicalEventStream) -> None:
    spans = _dumped_spans(sample_stream, PolicyId.P1)
    request = next(span for span in spans if span["span_id"] == "span-0001")
    retrieval = next(span for span in spans if span["span_id"] == "span-0002")
    assert request["content"]["user"] == "Summarize the cited note."
    assert request["authz"]["principal_id"] == "principal-0001"
    assert "security" not in request
    assert retrieval["retrieval"]["source_id"] == "doc-0001"
    assert retrieval["retrieval"]["hash"].startswith("sha256:")


def test_p3_retains_security_and_opaques_retrieval(sample_stream: CanonicalEventStream) -> None:
    spans = _dumped_spans(sample_stream, PolicyId.P3)
    request = next(span for span in spans if span["span_id"] == "span-0001")
    retrieval = next(span for span in spans if span["span_id"] == "span-0002")
    export_text = canonical_json_text(apply_policy(sample_stream, PolicyId.P3))
    assert "security" in request
    assert request["security"]["trust_class"] == "untrusted"
    assert "content" not in request
    assert "authz" not in request
    assert "doc-0001" not in export_text
    assert retrieval["retrieval"]["source_id"].startswith("sha256:")
    assert retrieval["retrieval"]["hash"].startswith("sha256:")


def test_p1_optional_hash_omitted_when_absent() -> None:
    stream = stream_from_spans(
        minimal_span(
            kind="retrieval",
            name="retrieve_notes",
            retrieval={"source_id": "doc-0001"},
        )
    )
    [span] = _dumped_spans(stream, PolicyId.P1)
    assert span["retrieval"] == {"source_id": "doc-0001"}


def test_request_id_stays_on_export_envelope(sample_stream: CanonicalEventStream) -> None:
    for policy in PolicyId:
        export = apply_policy(sample_stream, policy)
        dumped = export.model_dump(mode="json", exclude_none=True)
        assert dumped["request_id"] == sample_stream.request_id
        for span in dumped["spans"]:
            assert "request_id" not in span


def test_transform_does_not_rerun_detectors() -> None:
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
            content={"user": "plain text with no library match"},
            detector_events=planted,
        )
    )
    original_events = deepcopy(stream.spans[0].detector_events)
    p1 = apply_policy(stream, PolicyId.P1)
    p0 = apply_policy(stream, PolicyId.P0)
    assert p1.spans[0].detector_events == original_events
    assert p0.spans[0].detector_events == []
    assert stream.spans[0].detector_events == original_events
