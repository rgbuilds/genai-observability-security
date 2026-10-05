import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from genai_observability.research.capture import (
    CaptureAdapter,
    NonemptyCaptureDirectoryError,
    ScriptedCompletionsClient,
    TransportError,
)
from genai_observability.research.replay_capture import run_mock_replay
from genai_observability.research.clock import DeterministicClock, SystemClock
from genai_observability.research.protocol import MOCK_NOTES, sent_retrieval
from genai_observability.schemas.enums import SpanKind

UTC = timezone.utc


def _stop(text: str) -> dict:
    return {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
    }


def _tool_raw(raw: str, *, finish_reason: str) -> dict:
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_note", "arguments": raw},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8},
    }


def test_retrieved_note_is_sent_and_recorded_verbatim() -> None:
    client = ScriptedCompletionsClient([_stop("Summary complete.")])
    record = CaptureAdapter(client, clock=DeterministicClock()).capture_prompt("cap-u1")
    context = next(
        message["content"]
        for message in client.calls[0]["messages"]
        if isinstance(message.get("content"), str) and message["content"].startswith("Retrieved note_id=")
    )
    note_id, sent_body = sent_retrieval(context)
    assert record.stream is not None
    retrieval = next(span for span in record.stream.spans if span.kind is SpanKind.RETRIEVAL)
    assert retrieval.content is not None
    assert retrieval.retrieval is not None
    assert retrieval.content.retrieved == sent_body == MOCK_NOTES["note-cited"]
    assert retrieval.retrieval.source_id == note_id == "note-cited"


def test_malformed_and_schema_invalid_arguments_are_preserved(monkeypatch) -> None:
    def reject_execution(*_args, **_kwargs):
        raise AssertionError("invalid arguments were executed")

    monkeypatch.setattr(
        "genai_observability.research.capture.execute_mock_tool",
        reject_execution,
    )
    truncated = '{"note_id": "note-ci'
    truncated_client = ScriptedCompletionsClient([_tool_raw(truncated, finish_reason="length")])
    truncated_record = CaptureAdapter(truncated_client, clock=DeterministicClock()).capture_prompt("cap-u1")
    assert truncated_record.stream is not None
    truncated_tool = next(span for span in truncated_record.stream.spans if span.kind is SpanKind.TOOL)
    assert truncated_tool.content is not None
    assert truncated_tool.content.tool_args == truncated
    assert truncated_tool.content.tool_args != {}
    assert truncated_tool.content.tool_result["executed"] is False
    assert truncated_tool.content.tool_result["argument_text"] == truncated
    assert truncated_tool.content.tool_result["error"] == "truncated_arguments"
    assert len(truncated_client.calls) == 1

    invalid = '{"note_id": 1}'
    invalid_client = ScriptedCompletionsClient([_tool_raw(invalid, finish_reason="tool_calls")])
    invalid_record = CaptureAdapter(invalid_client, clock=DeterministicClock()).capture_prompt("cap-u4")
    assert invalid_record.stream is not None
    invalid_tool = next(span for span in invalid_record.stream.spans if span.kind is SpanKind.TOOL)
    assert invalid_tool.content is not None
    assert invalid_tool.content.tool_args == {"note_id": 1}
    assert invalid_tool.content.tool_result["executed"] is False
    assert invalid_tool.content.tool_result["argument_text"] == invalid
    assert invalid_tool.content.tool_result["error"] == "schema_mismatch"
    assert len(invalid_client.calls) == 1


def test_capture_metadata_is_written_before_the_next_request_and_on_partial(tmp_path: Path) -> None:
    class Probe:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def complete(self, request: dict) -> dict:
            self.calls.append(request)
            if len(self.calls) == 2:
                meta = json.loads((tmp_path / "cap-u1.meta.json").read_text(encoding="utf-8"))
                stream = json.loads((tmp_path / "cap-u1.json").read_text(encoding="utf-8"))
                models = [span for span in stream["spans"] if span["kind"] == "model"]
                assert len(models) == 1
                assert meta["requests_used"] == 1
                assert meta["partial"] is True
                assert "truncated" in meta
                assert "stop_reason" in meta
                assert "failures" in meta
                return _stop("done")
            return _tool_raw('{"note_id": "note-cited"}', finish_reason="tool_calls")

    probe = Probe()
    run = CaptureAdapter(probe, clock=DeterministicClock()).run(("cap-u1",), output_dir=tmp_path)
    assert run.records[0].requests_used == 2
    final_meta = json.loads((tmp_path / "cap-u1.meta.json").read_text(encoding="utf-8"))
    assert final_meta["requests_used"] == 2
    assert final_meta["truncated"] is False

    partial_dir = tmp_path / "partial"
    partial = CaptureAdapter(
        ScriptedCompletionsClient([TransportError("boom"), TransportError("boom")]),
        clock=DeterministicClock(),
    ).run(("cap-u3",), output_dir=partial_dir)
    meta = json.loads((partial_dir / "cap-u3.meta.json").read_text(encoding="utf-8"))
    stream = json.loads((partial_dir / "cap-u3.json").read_text(encoding="utf-8"))
    assert partial.records[0].partial is True
    assert meta["stop_reason"] == "transport_exhausted"
    assert meta["requests_used"] == 2
    assert meta["truncated"] is False
    assert meta["partial"] is True
    assert meta["failures"] == [{"kind": "transport_exhausted"}]
    assert all(span["kind"] != "model" for span in stream["spans"])


def test_nonempty_destination_is_rejected_before_any_request(tmp_path: Path) -> None:
    (tmp_path / "already.txt").write_text("keep", encoding="utf-8")

    class Boom:
        def complete(self, request: dict) -> dict:
            raise AssertionError("request sent to a nonempty destination")

    with pytest.raises(NonemptyCaptureDirectoryError, match="not empty"):
        CaptureAdapter(Boom(), clock=DeterministicClock()).run(("cap-u5",), output_dir=tmp_path)
    assert (tmp_path / "already.txt").read_text(encoding="utf-8") == "keep"


def test_default_capture_directories_are_unique(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("genai_observability.research.capture.PRIVATE_CAPTURE_DIR", tmp_path / "captures")
    first = CaptureAdapter(
        ScriptedCompletionsClient([_stop("acknowledged")]),
        clock=DeterministicClock(),
    ).run(("cap-u5",))
    second = CaptureAdapter(
        ScriptedCompletionsClient([_stop("acknowledged")]),
        clock=DeterministicClock(),
    ).run(("cap-u5",))
    assert first.output_dir is not None and second.output_dir is not None
    assert first.output_dir != second.output_dir
    assert (first.output_dir / "cap-u5.json").is_file()
    assert (second.output_dir / "cap-u5.json").is_file()


def test_deterministic_clock_does_not_read_wall_or_monotonic_time(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("capture read the real clock")

    monkeypatch.setattr(time, "monotonic", explode)
    monkeypatch.setattr("genai_observability.research.clock.time.monotonic", explode)
    record = CaptureAdapter(
        ScriptedCompletionsClient([_stop("acknowledged")]),
        clock=DeterministicClock(),
    ).capture_prompt("cap-u5")
    assert record.stream is not None
    assert record.stream.spans[0].start_time == "2026-10-04T23:00:00.000Z"
    assert record.stream.spans[0].duration_ms == 15
    assert record.stream.spans[1].start_time == "2026-10-04T23:00:01.000Z"
    assert record.stream.spans[1].duration_ms == 15


def test_system_clock_uses_utc_timestamps_and_monotonic_duration() -> None:
    walls = iter(
        [
            datetime(2026, 10, 5, 1, 0, tzinfo=UTC),
            datetime(2026, 10, 5, 1, 0, tzinfo=UTC),
            datetime(2026, 10, 5, 2, 0, tzinfo=UTC),
            datetime(2026, 10, 4, 1, 0, tzinfo=UTC),
        ]
    )
    monos = iter([10.0, 10.0, 50.0, 50.25])
    clock = SystemClock(now=lambda: next(walls), monotonic=lambda: next(monos))
    record = CaptureAdapter(
        ScriptedCompletionsClient([_stop("acknowledged")]),
        clock=clock,
    ).capture_prompt("cap-u5")
    assert record.stream is not None
    model = next(span for span in record.stream.spans if span.kind is SpanKind.MODEL)
    assert model.start_time == "2026-10-05T02:00:00.000Z"
    assert model.end_time == "2026-10-04T01:00:00.000Z"
    assert model.duration_ms == 250


def test_mock_replay_grades_reloaded_captures_and_does_not_replace_on_transform_failure(
    tmp_path: Path,
) -> None:
    summary = run_mock_replay(tmp_path / "captures", tmp_path / "grades")
    assert summary["passed"] is True
    failure = summary["transform_failure"]
    assert failure["error"] == "UnprocessedStreamError"
    assert failure["capture_bytes_unchanged"] is True
    assert failure["replacement_requested"] is False
    assert failure["client_calls_before"] == failure["client_calls_after"]
    assert summary["malformed_arguments_preserved"] is True
    assert (tmp_path / "grades" / "exports" / "cap-u1" / "P0.json").is_file()
    assert (tmp_path / "grades" / "results" / "cap-u3" / "P2.json").is_file()
