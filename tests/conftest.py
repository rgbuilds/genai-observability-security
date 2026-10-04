from pathlib import Path

import pytest

from genai_observability.schemas.canonical import CanonicalEventStream

TEST_DATA = Path(__file__).parent / "data" / "canonical"
SAMPLE_SCENARIO_ID = "scenario-0001"


@pytest.fixture
def sample_stream() -> CanonicalEventStream:
    path = TEST_DATA / f"{SAMPLE_SCENARIO_ID}.json"
    return CanonicalEventStream.model_validate_json(path.read_text(encoding="utf-8"))
