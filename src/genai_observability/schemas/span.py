from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from genai_observability.serialization import reject_nonfinite
from genai_observability.schemas.enums import (
    AuthzDecision,
    DenialReason,
    DetectorCategory,
    DetectorStage,
    PrivilegeClass,
    SpanKind,
    SpanStatus,
    TrustClass,
)

RFC3339_UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$"
FORBIDDEN_TELEMETRY_KEYS = frozenset(
    {"incident_type", "variant_class", "expected_q15"}
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def reject_forbidden_mapping_keys(cls, value: Any) -> Any:
        if isinstance(value, dict) and FORBIDDEN_TELEMETRY_KEYS.intersection(value):
            raise ValueError(
                "telemetry must not contain fixture labels or expected conclusions"
            )
        return value

    @model_validator(mode="after")
    def reject_nonfinite_numbers(self) -> "_StrictModel":
        # Check the Python dump before any JSON conversion can turn NaN/Inf into null.
        reject_nonfinite(self.model_dump(mode="python"))
        return self


class ModelAttributes(_StrictModel):
    provider: str | None = None
    name: str | None = None


class TokenCounts(_StrictModel):
    input: int | None = None
    output: int | None = None


class ToolAttributes(_StrictModel):
    name: str | None = None
    type: str | None = None


class ContentAttributes(_StrictModel):
    system: str | None = None
    user: str | None = None
    output: str | None = None
    retrieved: str | None = None
    tool_args: Any = None
    tool_result: Any = None


class AuthzAttributes(_StrictModel):
    principal_id: str | None = None
    roles: list[str] | None = None
    resource: str | None = None


class RetrievalAttributes(_StrictModel):
    source_id: str | None = None
    hash: str | None = None


class SecurityAttributes(_StrictModel):
    trust_class: TrustClass | None = None
    privilege_class: PrivilegeClass | None = None
    authz_decision: AuthzDecision | None = None
    denial_reason: DenialReason | None = None


class DetectorEvent(_StrictModel):
    detector_id: str = Field(min_length=1)
    category: DetectorCategory
    stage: DetectorStage
    match_class: str = Field(min_length=1)


class CanonicalSpan(_StrictModel):
    span_id: str = Field(min_length=1)
    parent_span_id: str | None = None
    name: str = Field(min_length=1)
    kind: SpanKind
    start_time: str = Field(pattern=RFC3339_UTC_PATTERN)
    end_time: str = Field(pattern=RFC3339_UTC_PATTERN)
    duration_ms: int = Field(ge=0)
    status: SpanStatus
    status_code: int | None = None
    model: ModelAttributes | None = None
    tokens: TokenCounts | None = None
    tool: ToolAttributes | None = None
    content: ContentAttributes | None = None
    authz: AuthzAttributes | None = None
    retrieval: RetrievalAttributes | None = None
    security: SecurityAttributes | None = None
    detector_events: list[DetectorEvent] = Field(default_factory=list)
