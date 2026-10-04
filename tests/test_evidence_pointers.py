import json

from genai_observability.grading.evidence import (
    export_dump,
    pointer_exists_in_artifact,
    serialized_export_text,
)
from genai_observability.grading.extract import extract_forensic_answers
from genai_observability.serialization import canonical_json_text
from tests.helpers import export_from_spans, minimal_span


def test_export_dump_is_the_parsed_canonical_artifact() -> None:
    export = export_from_spans(
        minimal_span(
            content={"user": "hello"},
            detector_events=[],
        )
    )
    text = serialized_export_text(export)
    assert text == canonical_json_text(export)
    assert export_dump(export) == json.loads(text)


def test_extracted_pointers_resolve_in_the_serialized_artifact() -> None:
    export = export_from_spans(
        minimal_span(
            detector_events=[
                {
                    "detector_id": "patternlib.v1.canary_grammar",
                    "category": "sensitive_data",
                    "stage": "user_input",
                    "match_class": "canary_grammar",
                }
            ]
        )
    )
    text = serialized_export_text(export)
    extraction = extract_forensic_answers(export)
    credited = [extraction.fact(qid) for qid in ("Q1", "Q12", "Q13")]
    assert all(fact.evidence for fact in credited)
    for fact in credited:
        assert any(pointer_exists_in_artifact(text, location.pointer) for location in fact.evidence)


def test_missing_pointer_does_not_resolve_in_artifact() -> None:
    export = export_from_spans(minimal_span())
    text = serialized_export_text(export)
    assert pointer_exists_in_artifact(text, "/request_id") is True
    assert pointer_exists_in_artifact(text, "/spans/0/detector_events") is False
