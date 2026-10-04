from typing import Literal

from pydantic import Field

from genai_observability.schemas.enums import DetectorPass
from genai_observability.schemas.span import CanonicalSpan, _StrictModel

CANONICAL_SCHEMA_VERSION = "canonical_event_stream.v1"


class CanonicalEventStream(_StrictModel):
    """Full runtime stream. Policies filter this object; they do not re-run the source."""

    schema_version: Literal["canonical_event_stream.v1"] = CANONICAL_SCHEMA_VERSION
    scenario_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    detector_pass: DetectorPass = DetectorPass.NOT_RUN
    spans: list[CanonicalSpan] = Field(min_length=1)
