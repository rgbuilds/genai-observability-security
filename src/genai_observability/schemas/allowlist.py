from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from genai_observability.paths import POLICY_ALLOWLIST_DIR
from genai_observability.schemas.enums import PolicyId
from genai_observability.schemas.span import _StrictModel

ALLOWLIST_SCHEMA_VERSION = "policy_allowlist.v1"

MATRIX_FIELDS: tuple[str, ...] = (
    "trace_id",
    "span_id",
    "parent_span_id",
    "request_id",
    "start_time",
    "end_time",
    "duration_ms",
    "name",
    "kind",
    "model.provider",
    "model.name",
    "tokens.input",
    "tokens.output",
    "tool.name",
    "tool.type",
    "status",
    "status_code",
    "content.system",
    "content.user",
    "content.output",
    "content.retrieved",
    "content.tool_args",
    "content.tool_result",
    "authz.principal_id",
    "authz.roles",
    "authz.resource",
    "retrieval.source_id",
    "retrieval.hash",
    "security.trust_class",
    "security.privilege_class",
    "security.authz_decision",
    "security.denial_reason",
    "detector_events",
    "detector_events.detector_id",
    "detector_events.category",
    "detector_events.stage",
    "detector_events.match_class",
)


class RetentionAction(StrEnum):
    RETAIN = "retain"
    DROP = "drop"
    REDACT = "redact"
    OPAQUE = "opaque"
    OPTIONAL = "optional"


class PolicyAllowlist(_StrictModel):
    """Published retain/redact/drop map. Loading this is not a transform."""

    schema_version: Literal["policy_allowlist.v1"] = ALLOWLIST_SCHEMA_VERSION
    policy_id: PolicyId
    policy_version: str = Field(min_length=1)
    fields: dict[str, RetentionAction]

    @model_validator(mode="after")
    def require_complete_matrix(self) -> "PolicyAllowlist":
        missing = [name for name in MATRIX_FIELDS if name not in self.fields]
        extra = sorted(set(self.fields) - set(MATRIX_FIELDS))
        if missing or extra:
            raise ValueError(
                f"allowlist {self.policy_id} v{self.policy_version} must list "
                f"exactly the section 3 matrix fields; missing={missing} extra={extra}"
            )
        return self


def allowlist_path(policy_id: PolicyId | str, policy_version: str = "1") -> Path:
    policy = PolicyId(policy_id)
    return POLICY_ALLOWLIST_DIR / f"{policy.value.lower()}.v{policy_version}.json"


def load_allowlist(policy_id: PolicyId | str, policy_version: str = "1") -> PolicyAllowlist:
    path = allowlist_path(policy_id, policy_version)
    return PolicyAllowlist.model_validate_json(path.read_text(encoding="utf-8"))


def load_all_allowlists(policy_version: str = "1") -> dict[PolicyId, PolicyAllowlist]:
    return {policy: load_allowlist(policy, policy_version) for policy in PolicyId}
