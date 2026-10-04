import json

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.serialization import canonical_json_bytes, canonical_json_text


def test_canonical_json_is_compact_sorted_utf8(sample_stream: CanonicalEventStream) -> None:
    text = canonical_json_text(sample_stream)
    raw = canonical_json_bytes(sample_stream)

    assert raw == text.encode("utf-8")
    assert "\n" not in text
    parsed = json.loads(text)
    assert json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == text
    assert "café" in text
    assert "\\u00e9" not in text


def test_key_order_and_whitespace_do_not_affect_canonical_bytes(
    sample_stream: CanonicalEventStream,
) -> None:
    pretty = json.dumps(sample_stream.model_dump(mode="json", exclude_none=True), indent=2)
    reordered = json.dumps(
        sample_stream.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        separators=(", ", ": "),
    )
    from_pretty = CanonicalEventStream.model_validate_json(pretty)
    from_reordered = CanonicalEventStream.model_validate_json(reordered)

    assert canonical_json_bytes(from_pretty) == canonical_json_bytes(sample_stream)
    assert canonical_json_bytes(from_reordered) == canonical_json_bytes(sample_stream)


def test_omitted_optional_groups_are_not_serialized_as_null(
    sample_stream: CanonicalEventStream,
) -> None:
    text = canonical_json_text(sample_stream)
    request_span = json.loads(text)["spans"][0]
    assert "model" not in request_span
    assert "tool" not in request_span
    assert "retrieval" not in request_span
