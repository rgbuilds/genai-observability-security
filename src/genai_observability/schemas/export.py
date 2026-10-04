from typing import Literal

from pydantic import Field

from genai_observability.schemas.enums import PolicyId
from genai_observability.schemas.span import CanonicalSpan, _StrictModel

EXPORT_SCHEMA_VERSION = "telemetry_export.v1"


class TelemetryExport(_StrictModel):
    """Versioned local JSON export after a policy transform.

    Span fields are optional so a transform can omit dropped groups.
    """

    schema_version: Literal["telemetry_export.v1"] = EXPORT_SCHEMA_VERSION
    policy_id: PolicyId
    policy_version: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    spans: list[CanonicalSpan] = Field(min_length=1)
