from enum import StrEnum


class PolicyId(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class SourceKind(StrEnum):
    FIXTURE = "fixture"
    CAPTURED = "captured"


class SpanKind(StrEnum):
    REQUEST = "request"
    MODEL = "model"
    RETRIEVAL = "retrieval"
    TOOL = "tool"


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class TrustClass(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    MIXED = "mixed"


class PrivilegeClass(StrEnum):
    """Minimal vocabulary frozen by Q15. A richer taxonomy was not specified."""

    NONE = "none"
    PRIVILEGED = "privileged"


class AuthzDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class DenialReason(StrEnum):
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    TOOL_ERROR = "tool_error"
    MODEL_ERROR = "model_error"
    NONE = "none"


class DetectorCategory(StrEnum):
    SENSITIVE_DATA = "sensitive_data"
    UNTRUSTED_PROPAGATION = "untrusted_propagation"


class DetectorStage(StrEnum):
    USER_INPUT = "user_input"
    INSTRUCTIONS = "instructions"
    RETRIEVAL = "retrieval"
    TOOL_ARGS = "tool_args"
    TOOL_RESULT = "tool_result"
    MODEL_OUTPUT = "model_output"
    AUTHORIZATION = "authorization"
