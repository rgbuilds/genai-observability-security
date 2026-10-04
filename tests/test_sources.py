from pathlib import Path

import pytest

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import SourceKind
from genai_observability.sources import CapturedTraceSource, FixtureSource
from genai_observability.sources.base import CanonicalEventSource

TEST_DATA = Path(__file__).parent / "data" / "canonical"


def test_fixture_source_satisfies_protocol_and_loads_sample() -> None:
    source = FixtureSource(TEST_DATA)
    assert isinstance(source, CanonicalEventSource)
    assert source.source_kind is SourceKind.FIXTURE
    stream = source.load("scenario-0001")
    assert isinstance(stream, CanonicalEventStream)
    assert stream.request_id == "req-0001"


def test_fixture_source_rejects_missing_and_mismatched_ids(
    tmp_path: Path, sample_stream: CanonicalEventStream
) -> None:
    source = FixtureSource(tmp_path)
    with pytest.raises(FileNotFoundError):
        source.load("scenario-0001")

    path = tmp_path / "other-id.json"
    path.write_text(sample_stream.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="scenario_id"):
        FixtureSource(tmp_path).load("other-id")


def test_captured_source_is_reserved_and_unimplemented() -> None:
    source = CapturedTraceSource()
    assert isinstance(source, CanonicalEventSource)
    assert source.source_kind is SourceKind.CAPTURED
    with pytest.raises(NotImplementedError, match="unresolved"):
        source.load("scenario-0001")
