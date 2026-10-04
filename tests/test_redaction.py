from genai_observability.patterns import load_pattern_library, redact_payload
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_json_text
from genai_observability.transforms import apply_policy
from tests.helpers import CANARY, SECRET_CANARY, minimal_span, stream_from_spans


def test_canary_substring_redaction_keeps_surrounding_text() -> None:
    library = load_pattern_library()
    text = f"prefix {CANARY} suffix"
    assert redact_payload(text, library) == "prefix [REDACTED:canary_grammar] suffix"


def test_secret_key_replaces_entire_value_and_wins_over_canary() -> None:
    library = load_pattern_library()
    payload = {
        "note_id": f"see {CANARY}",
        "api_key": SECRET_CANARY,
        "user_password": "visible-secret",
        "api_key_count": 3,
        "tokenized": f"keep {CANARY}",
    }
    redacted = redact_payload(payload, library)
    assert redacted["note_id"] == "see [REDACTED:canary_grammar]"
    assert redacted["api_key"] == "[REDACTED:secret_key]"
    assert redacted["user_password"] == "[REDACTED:secret_key]"
    assert redacted["api_key_count"] == 3
    assert redacted["tokenized"] == "keep [REDACTED:canary_grammar]"


def test_canary_dictionary_key_is_redacted() -> None:
    library = load_pattern_library()
    redacted = redact_payload({CANARY: "nested", "ok": "plain"}, library)
    assert CANARY not in redacted
    assert redacted["[REDACTED:canary_grammar]"] == "nested"
    assert redacted["ok"] == "plain"


def test_lookalikes_are_not_canaries() -> None:
    library = load_pattern_library()
    text = "SYNTHESIS_REPORT and synth-userin-a1b2c3d4 stay"
    assert redact_payload(text, library) == text


def test_p2_redacts_payload_fields_only() -> None:
    stream = stream_from_spans(
        minimal_span(
            name=f"handle {CANARY}",
            tool={"name": f"get_{CANARY}", "type": "read"},
            content={
                "user": f"Ask about {CANARY} please",
                "tool_args": {"note_id": "note-0001", "x-api-key": SECRET_CANARY},
            },
            authz={"principal_id": f"id-{CANARY}", "roles": ["reader"]},
            retrieval={"source_id": CANARY},
        )
    )
    export = apply_policy(stream, PolicyId.P2)
    text = canonical_json_text(export)
    span = export.spans[0]
    assert span.content is not None
    assert span.content.user == "Ask about [REDACTED:canary_grammar] please"
    assert span.content.tool_args == {
        "note_id": "note-0001",
        "x-api-key": "[REDACTED:secret_key]",
    }
    assert span.authz is not None
    assert span.authz.principal_id == "id-[REDACTED:canary_grammar]"
    assert span.name == f"handle {CANARY}"
    assert span.tool is not None
    assert span.tool.name == f"get_{CANARY}"
    assert span.retrieval is not None
    assert span.retrieval.source_id == CANARY
    assert CANARY in text
    assert "Ask about SYNTH-USERIN-A1B2C3D4" not in text


def test_p2_zero_exposure_when_canaries_stay_in_payload_scope() -> None:
    stream = stream_from_spans(
        minimal_span(
            content={"user": f"embedded {CANARY} token", "tool_result": {"ok": True}},
            authz={"resource": f"res-{SECRET_CANARY}"},
        )
    )
    text = canonical_json_text(apply_policy(stream, PolicyId.P2))
    assert CANARY not in text
    assert SECRET_CANARY not in text
