from genai_observability.full_study.evaluate import co_occurrence_outcome, extract_then_evaluate_full_study
from genai_observability.full_study.extract import extract_full_study_answers
from genai_observability.full_study.fixtures import build_stream
from genai_observability.full_study.inventory import inventory_from_spec
from genai_observability.full_study.mock_capture import (
    MockCaptureResponseError,
    capture_mocked,
    scripted_responses_for,
)
from genai_observability.full_study.protocol import LIVE_FULL_STUDY_AUTHORIZED
from genai_observability.full_study.scenarios import FULL_STUDY_EXECUTION_IDS, all_specs, spec_by_id
from genai_observability.full_study.select import select_full_study_references
from genai_observability.grading.extract import ExtractedFact, ExtractionStatus
from genai_observability.research.capture import LiveCaptureNotAuthorized, LiveOpenAIClient, ScriptedCompletionsClient
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import PolicyId, TrustClass
from genai_observability.transforms import apply_policy


def test_registry_counts_and_canary_origins() -> None:
    specs = all_specs()
    assert len(specs) == 48
    assert len(FULL_STUDY_EXECUTION_IDS) == 48
    assert len({item["pair_id"] for item in specs}) == 24
    assert sum(1 for item in specs if item["source"] == "scripted") == 24
    assert sum(1 for item in specs if item["source"] == "mocked-capture") == 24
    origins = {plant["location"] for spec in specs for plant in spec["canaries"]}
    assert origins == {"C1", "C2", "C3", "C4", "C5", "C6", "C7"}
    tokens = [plant["token"] for spec in specs for plant in spec["canaries"]]
    assert len(tokens) == len(set(tokens)) == 16


def test_oc1_uses_last_model_output_not_tool_args() -> None:
    spec = spec_by_id()["fs-f5c-case"]
    stream = build_stream(spec)
    answers = select_full_study_references(apply_runtime_detectors(stream), spec)
    assert answers.question("FS16").answer == "no"
    assert answers.question("OC1").answer == "yes"
    export = apply_policy(apply_runtime_detectors(stream), PolicyId.P1)
    extraction = extract_full_study_answers(export)
    oc1 = extraction.fact("OC1")
    assert isinstance(oc1.value, dict)
    assert spec["canaries"][0]["token"] in (oc1.value["loc2"] or "")
    assert spec["canaries"][0]["token"] not in str(
        next(span.content.tool_args for span in export.spans if span.content and span.content.tool_args)
    )


def test_co_occurrence_drop_and_redaction_are_missing() -> None:
    fact = ExtractedFact(
        question_id="OC1",
        status=ExtractionStatus.ANSWERED,
        value={"loc1": "alpha SYNTH-F5C3C-B44B000E", "loc2": None},
    )
    assert co_occurrence_outcome(fact, "SYNTH-F5C3C-B44B000E") == "missing"
    redacted = ExtractedFact(
        question_id="OC1",
        status=ExtractionStatus.ANSWERED,
        value={
            "loc1": "alpha [REDACTED:canary_grammar]",
            "loc2": "alpha [REDACTED:canary_grammar]",
        },
    )
    assert co_occurrence_outcome(redacted, "SYNTH-F5C3C-B44B000E") == "missing"


def test_mocked_capture_consumes_scripted_responses() -> None:
    spec = spec_by_id()["fs-f1d-case"]
    client = ScriptedCompletionsClient(scripted_responses_for(spec))
    stream = capture_mocked(spec, client)
    assert stream.scenario_id == "fs-f1d-case"
    assert client.calls
    assert not client._responses


def test_mocked_capture_uses_changed_response_content() -> None:
    spec = spec_by_id()["fs-f1d-case"]
    client = ScriptedCompletionsClient(
        [{"choices": [{"finish_reason": "stop", "message": {"content": "changed"}}]}]
    )
    stream = capture_mocked(spec, client)
    outputs = [span.content.output for span in stream.spans if span.content and span.content.output]
    assert outputs == ["changed"]


def test_mocked_capture_rejects_malformed_tool_arguments() -> None:
    spec = spec_by_id()["fs-f1c-case"]
    client = ScriptedCompletionsClient(
        [
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {"function": {"name": "get_note", "arguments": "{"}}
                            ]
                        },
                    }
                ]
            }
        ]
    )
    try:
        capture_mocked(spec, client)
    except MockCaptureResponseError:
        return
    raise AssertionError("malformed tool arguments were accepted")


def test_mock_capture_refuses_live_client() -> None:
    assert LIVE_FULL_STUDY_AUTHORIZED is False
    spec = spec_by_id()["fs-f1d-ctrl"]
    try:
        capture_mocked(spec, LiveOpenAIClient())
    except LiveCaptureNotAuthorized:
        return
    raise AssertionError("live client was accepted")


def test_select_rejects_policy_export() -> None:
    spec = spec_by_id()["fs-f1a-case"]
    stream = build_stream(spec)
    export = apply_policy(apply_runtime_detectors(stream), PolicyId.P1)
    try:
        select_full_study_references(export, spec)  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("select accepted a policy export")


def test_reference_selection_uses_realized_stream_fields() -> None:
    spec = spec_by_id()["fs-f2c-case"]
    stream = build_stream(spec)
    request = next(span for span in stream.spans if span.kind.value == "request")
    retrieval = next(span for span in stream.spans if span.kind.value == "retrieval")
    assert request.security is not None
    assert retrieval.retrieval is not None
    request.security.trust_class = TrustClass.TRUSTED
    retrieval.retrieval.source_id = "realized-source"
    assert retrieval.content is not None
    retrieval.content.retrieved = "benign realized body"
    tool = next(span for span in stream.spans if span.kind.value == "tool")
    assert tool.content is not None
    tool.content.tool_result = {"ok": True, "body": "benign realized body"}
    answers = select_full_study_references(apply_runtime_detectors(stream), spec)
    assert answers.question("FS4").answer == "realized-source"
    assert answers.question("FS8").answer == "trusted"
    assert answers.question("FS11").answer == "no"


def test_zero_canary_inventory_is_empty() -> None:
    spec = spec_by_id()["fs-f4b-case"]
    inventory = inventory_from_spec(spec)
    assert inventory.eligible_canaries == []


def test_p1_grades_f5c_oc1_yes() -> None:
    spec = spec_by_id()["fs-f5c-case"]
    stream = build_stream(spec)
    answers = select_full_study_references(apply_runtime_detectors(stream), spec)
    export = apply_policy(apply_runtime_detectors(stream), PolicyId.P1)
    _, evaluation = extract_then_evaluate_full_study(export, answers)
    assert evaluation.score("OC1").credit == 1
    assert evaluation.score("OC1").extracted_value == "yes"
    assert evaluation.score("FS16").extracted_value == "no"
