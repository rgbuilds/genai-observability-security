import json
from pathlib import Path

import pytest

from genai_observability.research.capture import (
    CaptureAdapter,
    LiveCaptureNotAuthorized,
    LiveOpenAIClient,
    ScriptedCompletionsClient,
    TransportError,
)
from genai_observability.research.costing import BudgetRejected, CaptureBudget, estimated_input_tokens
from genai_observability.research.protocol import (
    LIVE_CAPTURE_AUTHORIZED,
    OFFICIAL_DOC_CHECK,
    PINNED_MODEL,
    USER_PROMPTS,
)
from genai_observability.schemas.enums import DetectorPass, SpanKind


def _stop(text: str) -> dict:
    return {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 5},
    }


def _tools(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 24, "completion_tokens": 8},
    }


def _length(text: str) -> dict:
    return {
        "choices": [{"finish_reason": "length", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 512},
    }


def test_live_client_and_authorization_flag_refuse_paid_capture() -> None:
    assert LIVE_CAPTURE_AUTHORIZED is False
    with pytest.raises(LiveCaptureNotAuthorized):
        CaptureAdapter(LiveOpenAIClient())
    with pytest.raises(LiveCaptureNotAuthorized):
        LiveOpenAIClient().complete({"model": PINNED_MODEL})


def test_official_doc_snapshot_is_pinned_and_requires_recheck() -> None:
    assert OFFICIAL_DOC_CHECK["snapshot"] == "gpt-4o-mini-2024-07-18"
    assert OFFICIAL_DOC_CHECK["function_calling"] is True
    assert OFFICIAL_DOC_CHECK["max_output_tokens"] >= 512
    assert OFFICIAL_DOC_CHECK["input_usd_per_million"] == 0.15
    assert OFFICIAL_DOC_CHECK["output_usd_per_million"] == 0.60
    assert OFFICIAL_DOC_CHECK["live_recheck_required"] is True


def test_no_tool_capture_is_kept() -> None:
    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    record = CaptureAdapter(client).capture_prompt("cap-u5")
    assert record.attempted is True
    assert record.truncated is False
    assert record.stream is not None
    assert record.stream.detector_pass is DetectorPass.NOT_RUN
    kinds = [span.kind for span in record.stream.spans]
    assert SpanKind.TOOL not in kinds
    assert SpanKind.RETRIEVAL not in kinds
    assert SpanKind.MODEL in kinds


def test_tool_continuation_uses_a_second_scripted_response() -> None:
    client = ScriptedCompletionsClient(
        [
            _tools("get_note", {"note_id": "note-cited"}),
            _stop("The cited note is brief."),
        ]
    )
    record = CaptureAdapter(client).capture_prompt("cap-u1")
    assert record.stream is not None
    kinds = [span.kind for span in record.stream.spans]
    assert kinds.count(SpanKind.MODEL) == 2
    assert SpanKind.RETRIEVAL in kinds
    assert SpanKind.TOOL in kinds
    tool = next(span for span in record.stream.spans if span.kind is SpanKind.TOOL)
    assert tool.content is not None
    assert tool.content.tool_args == {"note_id": "note-cited"}
    assert tool.content.tool_result is not None
    assert "SYNTH-RETRVL-C00C0003" in tool.content.tool_result["body"]
    assert len(client.calls) == 2
    assert all(call["model"] == PINNED_MODEL for call in client.calls)
    assert all(call["max_tokens"] == 512 for call in client.calls)


def test_truncated_response_is_preserved_without_a_prose_retry() -> None:
    client = ScriptedCompletionsClient([_length("partial ")])
    record = CaptureAdapter(client).capture_prompt("cap-u5")
    assert record.truncated is True
    assert record.stream is not None
    output = next(span.content.output for span in record.stream.spans if span.kind is SpanKind.MODEL)
    assert output == "partial "
    assert len(client.calls) == 1


def test_request_cap_preserves_partial_run_and_lists_unattempted(tmp_path: Path) -> None:
    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    budget = CaptureBudget(requests_used=11)
    run = CaptureAdapter(client, budget).run(("cap-u5", "cap-u1", "cap-u2"), output_dir=tmp_path)
    assert [record.prompt_id for record in run.records] == ["cap-u5"]
    assert run.records[0].stream is not None
    assert run.unattempted_prompt_ids == ["cap-u1", "cap-u2"]
    assert (tmp_path / "cap-u5.json").is_file()
    unattempted = json.loads((tmp_path / "unattempted_prompts.json").read_text(encoding="utf-8"))
    assert unattempted["unattempted_prompt_ids"] == ["cap-u1", "cap-u2"]


def test_dollar_ceiling_refuses_before_send() -> None:
    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    budget = CaptureBudget(spent_usd=5.00)
    run = CaptureAdapter(client, budget).run(("cap-u5",))
    assert run.records == []
    assert run.unattempted_prompt_ids == ["cap-u5"]
    assert client.calls == []


def test_input_token_bound_refuses_oversized_history() -> None:
    request = {
        "messages": [{"role": "user", "content": "x" * 20000}],
        "tools": [{"schema": "y" * 2000}],
    }
    assert estimated_input_tokens(request) > 4096
    with pytest.raises(BudgetRejected, match="input_bound"):
        CaptureBudget().check(request)


def test_transport_retries_count_as_requests_then_keep_partial() -> None:
    client = ScriptedCompletionsClient([TransportError("boom"), TransportError("boom")])
    record = CaptureAdapter(client).capture_prompt("cap-u5")
    assert record.attempted is True
    assert record.stop_reason == "transport_exhausted"
    assert record.stream is not None
    assert record.requests_used == 2
    assert all(span.kind is not SpanKind.MODEL for span in record.stream.spans)


def test_frozen_prompts_are_the_six_named_ids() -> None:
    assert list(USER_PROMPTS) == ["cap-u1", "cap-u2", "cap-u3", "cap-u4", "cap-u5", "cap-u6"]
