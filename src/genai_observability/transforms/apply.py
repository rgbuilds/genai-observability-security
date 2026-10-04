import hashlib
from typing import Any

from genai_observability.patterns.library import PatternLibrary, load_pattern_library
from genai_observability.patterns.scan import redact_payload
from genai_observability.schemas.allowlist import PolicyAllowlist, RetentionAction, load_allowlist
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import DetectorPass, PolicyId
from genai_observability.schemas.export import TelemetryExport
from genai_observability.schemas.span import (
    AuthzAttributes,
    CanonicalSpan,
    ContentAttributes,
    DetectorEvent,
    RetrievalAttributes,
    SecurityAttributes,
)


class UnprocessedStreamError(ValueError):
    """Transform refused a stream whose runtime detector pass has not completed."""


def opaque_identifier(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _maybe_redact(value: Any, action: RetentionAction, library: PatternLibrary) -> Any:
    if action is RetentionAction.REDACT:
        return redact_payload(value, library)
    return value


def _transform_content(
    content: ContentAttributes | None,
    allowlist: PolicyAllowlist,
    library: PatternLibrary,
) -> ContentAttributes | None:
    if content is None:
        return None
    mapping = {
        "system": "content.system",
        "user": "content.user",
        "output": "content.output",
        "retrieved": "content.retrieved",
        "tool_args": "content.tool_args",
        "tool_result": "content.tool_result",
    }
    data: dict[str, Any] = {}
    for attr, field_name in mapping.items():
        action = allowlist.fields[field_name]
        value = getattr(content, attr)
        if value is None or action is RetentionAction.DROP:
            continue
        data[attr] = _maybe_redact(value, action, library)
    return ContentAttributes.model_validate(data) if data else None


def _transform_authz(
    authz: AuthzAttributes | None,
    allowlist: PolicyAllowlist,
    library: PatternLibrary,
) -> AuthzAttributes | None:
    if authz is None:
        return None
    mapping = {
        "principal_id": "authz.principal_id",
        "roles": "authz.roles",
        "resource": "authz.resource",
    }
    data: dict[str, Any] = {}
    for attr, field_name in mapping.items():
        action = allowlist.fields[field_name]
        value = getattr(authz, attr)
        if value is None or action is RetentionAction.DROP:
            continue
        data[attr] = _maybe_redact(value, action, library)
    return AuthzAttributes.model_validate(data) if data else None


def _transform_retrieval(
    retrieval: RetrievalAttributes | None,
    allowlist: PolicyAllowlist,
) -> RetrievalAttributes | None:
    if retrieval is None:
        return None
    source_action = allowlist.fields["retrieval.source_id"]
    hash_action = allowlist.fields["retrieval.hash"]
    data: dict[str, Any] = {}

    if retrieval.source_id is not None:
        if source_action is RetentionAction.RETAIN:
            data["source_id"] = retrieval.source_id
        elif source_action is RetentionAction.OPAQUE:
            data["source_id"] = opaque_identifier(retrieval.source_id)

    if retrieval.hash is not None and hash_action in {
        RetentionAction.RETAIN,
        RetentionAction.OPTIONAL,
    }:
        data["hash"] = retrieval.hash
    elif (
        hash_action is RetentionAction.RETAIN
        and "hash" not in data
        and retrieval.source_id is not None
        and source_action is RetentionAction.OPAQUE
    ):
        data["hash"] = opaque_identifier(retrieval.source_id)

    return RetrievalAttributes.model_validate(data) if data else None


def _transform_security(
    security: SecurityAttributes | None,
    allowlist: PolicyAllowlist,
) -> SecurityAttributes | None:
    if security is None:
        return None
    mapping = {
        "trust_class": "security.trust_class",
        "privilege_class": "security.privilege_class",
        "authz_decision": "security.authz_decision",
        "denial_reason": "security.denial_reason",
    }
    data: dict[str, Any] = {}
    for attr, field_name in mapping.items():
        if allowlist.fields[field_name] is RetentionAction.DROP:
            continue
        value = getattr(security, attr)
        if value is not None:
            data[attr] = value
    return SecurityAttributes.model_validate(data) if data else None


def _transform_span(
    span: CanonicalSpan,
    allowlist: PolicyAllowlist,
    library: PatternLibrary,
) -> CanonicalSpan:
    keep_detectors = allowlist.fields["detector_events"] is not RetentionAction.DROP
    if keep_detectors:
        if span.detector_events is None:
            raise UnprocessedStreamError(
                "completed detector pass must set detector_events to a list on every span"
            )
        detector_events: list[DetectorEvent] | None = list(span.detector_events)
    else:
        detector_events = None
    return CanonicalSpan(
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        name=span.name,
        kind=span.kind,
        start_time=span.start_time,
        end_time=span.end_time,
        duration_ms=span.duration_ms,
        status=span.status,
        status_code=span.status_code,
        model=span.model,
        tokens=span.tokens,
        tool=span.tool,
        content=_transform_content(span.content, allowlist, library),
        authz=_transform_authz(span.authz, allowlist, library),
        retrieval=_transform_retrieval(span.retrieval, allowlist),
        security=_transform_security(span.security, allowlist),
        detector_events=detector_events,
    )


def apply_policy(
    stream: CanonicalEventStream,
    policy_id: PolicyId | str,
    *,
    policy_version: str = "1",
    library: PatternLibrary | None = None,
) -> TelemetryExport:
    """Pure allowlist transform. Does not run detectors or mutate `stream`."""
    if stream.detector_pass is not DetectorPass.COMPLETED:
        raise UnprocessedStreamError(
            "apply_policy requires a completed runtime detector pass; "
            "an unprocessed stream must not export a completed-negative detector result"
        )
    policy = PolicyId(policy_id)
    allowlist = load_allowlist(policy, policy_version)
    library = library or load_pattern_library()
    return TelemetryExport(
        policy_id=policy,
        policy_version=allowlist.policy_version,
        request_id=stream.request_id,
        trace_id=stream.trace_id,
        spans=[_transform_span(span, allowlist, library) for span in stream.spans],
    )
