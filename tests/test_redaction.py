from genai_observability.patterns import load_pattern_library, redact_payload
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_hash, canonical_json_text
from genai_observability.transforms import apply_policy
from tests.helpers import CANARY, CANARY_B, SECRET_CANARY, minimal_span, stream_from_spans


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


def test_canary_dictionary_key_preserves_surrounding_text() -> None:
    library = load_pattern_library()
    redacted = redact_payload({f"pre_{CANARY}_post": "nested", "ok": "plain"}, library)
    assert CANARY not in redacted
    assert f"pre_{CANARY}_post" not in redacted
    assert redacted["pre_[REDACTED:canary_grammar]_post"] == "nested"
    assert redacted["ok"] == "plain"


def test_multiple_canary_keys_do_not_overwrite_each_other() -> None:
    library = load_pattern_library()
    redacted = redact_payload({CANARY: "first", CANARY_B: "second"}, library)
    assert set(redacted) == {"[REDACTED:canary_grammar]", "[REDACTED:canary_grammar]_2"}
    assert set(redacted.values()) == {"first", "second"}
    # Lexicographic original keys: CANARY_B (TOOLARG) before CANARY (USERIN).
    assert redacted["[REDACTED:canary_grammar]"] == "second"
    assert redacted["[REDACTED:canary_grammar]_2"] == "first"


def test_redacted_key_does_not_overwrite_existing_key() -> None:
    library = load_pattern_library()
    reserved = "[REDACTED:canary_grammar]"
    redacted = redact_payload({reserved: "kept", CANARY: "moved"}, library)
    assert redacted[reserved] == "kept"
    assert redacted["[REDACTED:canary_grammar]_2"] == "moved"
    assert len(redacted) == 2


def test_key_redaction_is_independent_of_insertion_order() -> None:
    library = load_pattern_library()
    left = {CANARY: "a", CANARY_B: "b", "plain": 1, f"pre_{CANARY}": "c"}
    right = {f"pre_{CANARY}": "c", "plain": 1, CANARY_B: "b", CANARY: "a"}
    left_redacted = redact_payload(left, library)
    right_redacted = redact_payload(right, library)
    assert left_redacted == right_redacted
    assert list(left_redacted) == list(right_redacted)
    assert canonical_hash({"payload": left_redacted}) == canonical_hash({"payload": right_redacted})


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
    export = apply_policy(apply_runtime_detectors(stream), PolicyId.P2)
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
    text = canonical_json_text(apply_policy(apply_runtime_detectors(stream), PolicyId.P2))
    assert CANARY not in text
    assert SECRET_CANARY not in text
