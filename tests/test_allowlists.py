from genai_observability.schemas.allowlist import (
    MATRIX_FIELDS,
    RetentionAction,
    load_all_allowlists,
    load_allowlist,
)
from genai_observability.schemas.enums import PolicyId


def test_all_versioned_allowlists_load_and_cover_the_matrix() -> None:
    loaded = load_all_allowlists("1")
    assert set(loaded) == set(PolicyId)
    for allowlist in loaded.values():
        assert tuple(allowlist.fields)  # non-empty
        assert set(allowlist.fields) == set(MATRIX_FIELDS)
        assert allowlist.schema_version == "policy_allowlist.v1"
        assert allowlist.policy_version == "1"


def test_allowlist_actions_match_section_3_matrix() -> None:
    p0, p1, p2, p3 = (load_allowlist(policy, "1") for policy in PolicyId)

    assert p0.fields["parent_span_id"] is RetentionAction.RETAIN
    assert p0.fields["content.user"] is RetentionAction.DROP
    assert p0.fields["security.trust_class"] is RetentionAction.DROP
    assert p0.fields["detector_events"] is RetentionAction.DROP
    assert p0.fields["retrieval.source_id"] is RetentionAction.DROP

    assert p1.fields["content.user"] is RetentionAction.RETAIN
    assert p1.fields["authz.principal_id"] is RetentionAction.RETAIN
    assert p1.fields["retrieval.source_id"] is RetentionAction.RETAIN
    assert p1.fields["retrieval.hash"] is RetentionAction.OPTIONAL
    assert p1.fields["security.authz_decision"] is RetentionAction.DROP
    assert p1.fields["detector_events"] is RetentionAction.RETAIN

    assert p2.fields["content.user"] is RetentionAction.REDACT
    assert p2.fields["authz.roles"] is RetentionAction.REDACT
    assert p2.fields["retrieval.source_id"] is RetentionAction.RETAIN
    assert p2.fields["security.privilege_class"] is RetentionAction.DROP
    assert p2.fields["detector_events"] is RetentionAction.RETAIN

    assert p3.fields["content.output"] is RetentionAction.DROP
    assert p3.fields["authz.resource"] is RetentionAction.DROP
    assert p3.fields["retrieval.source_id"] is RetentionAction.OPAQUE
    assert p3.fields["retrieval.hash"] is RetentionAction.RETAIN
    assert p3.fields["security.trust_class"] is RetentionAction.RETAIN
    assert p3.fields["detector_events"] is RetentionAction.RETAIN
