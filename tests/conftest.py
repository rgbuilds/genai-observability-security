from pathlib import Path

import pytest

from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.canonical import CanonicalEventStream

TEST_DATA = Path(__file__).parent / "data" / "canonical"
SAMPLE_SCENARIO_ID = "scenario-0001"


@pytest.fixture
def sample_stream() -> CanonicalEventStream:
    path = TEST_DATA / f"{SAMPLE_SCENARIO_ID}.json"
    return CanonicalEventStream.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture
def processed_sample_stream(sample_stream: CanonicalEventStream) -> CanonicalEventStream:
    return apply_runtime_detectors(sample_stream)
