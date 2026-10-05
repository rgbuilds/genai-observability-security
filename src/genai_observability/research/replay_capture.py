"""Reload mocked captures and grade them. A transform failure does not recapture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genai_observability.paths import CAPTURE_REPLAY_RUNS_DIR, PRIVATE_DIR, REPO_ROOT
from genai_observability.research.capture import CaptureAdapter, ScriptedCompletionsClient
from genai_observability.research.clock import DeterministicClock
from genai_observability.research.evaluate import extract_then_evaluate_research
from genai_observability.research.select import select_references
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import PolicyId
from genai_observability.serialization import canonical_json_text, sha256_hex
from genai_observability.sources.fixtures import FixtureSource
from genai_observability.transforms.apply import UnprocessedStreamError, apply_policy

TRUNCATED_ARGUMENTS = '{"note_id": "note-ci'
_SAFE_R4 = frozenset({"yes", "no", "missing"})
_SAFE_OUTCOMES = frozenset({"allowed", "denied", "yes", "no", "missing"})


def _stop(text: str) -> dict[str, Any]:
    return {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 4},
    }


def _tools(name: str, arguments: dict[str, str]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 24, "completion_tokens": 8},
    }


def _truncated_tool(raw: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": "partial",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "delete_account", "arguments": raw},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 512},
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _public_value(question_id: str, value: Any) -> Any:
    if question_id == "R7" and isinstance(value, list):
        return value
    if isinstance(value, list) and all(isinstance(item, str) and item in _SAFE_OUTCOMES for item in value):
        return value
    if isinstance(value, str) and (value in _SAFE_R4 or value in _SAFE_OUTCOMES):
        return value
    return None


def run_mock_replay(capture_dir: Path, grade_dir: Path) -> dict[str, Any]:
    """Capture with a scripted client, reload, select references, detect, grade.

    `capture_dir` and `grade_dir` must be empty or absent. The scripted client is
    not called again after a transform failure.
    """
    client = ScriptedCompletionsClient(
        [
            _tools("get_note", {"note_id": "note-cited"}),
            _stop("Summary complete."),
            _stop("acknowledged"),
            _truncated_tool(TRUNCATED_ARGUMENTS),
        ]
    )
    adapter = CaptureAdapter(client, clock=DeterministicClock())
    run = adapter.run(("cap-u1", "cap-u5", "cap-u3"), output_dir=capture_dir)
    calls_after_capture = len(client.calls)

    source = FixtureSource(capture_dir)
    graded: list[dict[str, Any]] = []
    for record in run.records:
        reloaded = source.load(record.prompt_id)
        in_memory = record.stream
        if in_memory is None:
            raise RuntimeError(f"missing in-memory stream for {record.prompt_id}")
        selected = select_references(reloaded, "U")
        if selected.model_dump() != select_references(in_memory, "U").model_dump():
            raise RuntimeError(f"reload changed reference selection for {record.prompt_id}")
        processed = apply_runtime_detectors(reloaded)
        for policy_id in PolicyId:
            export = apply_policy(processed, policy_id)
            try:
                select_references(export, "U")  # type: ignore[arg-type]
            except TypeError:
                pass
            else:
                raise RuntimeError("select_references accepted a policy export")
            extraction, evaluation = extract_then_evaluate_research(export, selected)
            export_path = grade_dir / "exports" / record.prompt_id / f"{policy_id.value}.json"
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(canonical_json_text(export), encoding="utf-8")
            questions = []
            for score in evaluation.scores:
                public = _public_value(score.question_id, score.extracted_value)
                questions.append(
                    {
                        "id": score.question_id,
                        "applicable": score.applicable,
                        "credit": score.credit,
                        "extracted_status": score.extracted_status,
                        "public_value": public,
                        "value_withheld": public is None and score.extracted_value is not None,
                    }
                )
            result = {
                "role": "mock-capture-replay",
                "research_evidence": False,
                "live_capture": "not_authorized",
                "execution_id": record.prompt_id,
                "policy_id": policy_id.value,
                "questions": questions,
                "forensic_coverage": evaluation.coverage(),
            }
            _write_json(grade_dir / "results" / record.prompt_id / f"{policy_id.value}.json", result)
            _ = extraction
            graded.append(
                {
                    "execution_id": record.prompt_id,
                    "policy_id": policy_id.value,
                    "coverage": evaluation.coverage(),
                    "questions": questions,
                }
            )

    failure_target = capture_dir / "cap-u5.json"
    before = failure_target.read_bytes()
    calls_before_failure = len(client.calls)
    unprocessed = CanonicalEventStream.model_validate_json(before)
    transform_error: str | None = None
    try:
        apply_policy(unprocessed, PolicyId.P1)
    except UnprocessedStreamError as exc:
        transform_error = type(exc).__name__
    after = failure_target.read_bytes()
    calls_after_failure = len(client.calls)
    malformed = source.load("cap-u3")
    preserved_args = next(
        span.content.tool_args
        for span in malformed.spans
        if span.kind.value == "tool" and span.content is not None
    )

    summary = {
        "role": "mock-capture-replay",
        "research_evidence": False,
        "research_go_no_go": "not_evaluated",
        "live_capture": "not_authorized",
        "capture_dir": str(capture_dir),
        "grade_dir": str(grade_dir),
        "prompt_ids": [record.prompt_id for record in run.records],
        "client_calls_after_capture": calls_after_capture,
        "graded": graded,
        "malformed_arguments_preserved": preserved_args == TRUNCATED_ARGUMENTS,
        "transform_failure": {
            "error": transform_error,
            "capture_sha256_before": sha256_hex(before),
            "capture_sha256_after": sha256_hex(after),
            "capture_bytes_unchanged": before == after,
            "client_calls_before": calls_before_failure,
            "client_calls_after": calls_after_failure,
            "replacement_requested": calls_after_failure != calls_before_failure,
        },
    }
    summary["passed"] = (
        transform_error == "UnprocessedStreamError"
        and before == after
        and calls_after_failure == calls_before_failure
        and preserved_args == TRUNCATED_ARGUMENTS
        and summary["prompt_ids"] == ["cap-u1", "cap-u5", "cap-u3"]
        and len(graded) == 12
    )
    _write_json(grade_dir / "summary.json", summary)
    return summary


def main() -> int:
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    private_root = PRIVATE_DIR / "capture-replay" / stamp
    public_root = CAPTURE_REPLAY_RUNS_DIR / stamp
    if private_root.exists() or public_root.exists():
        raise SystemExit(f"replay destination already exists: {stamp}")
    summary = run_mock_replay(private_root / "captures", private_root / "grades")
    summary["capture_dir"] = str((private_root / "captures").relative_to(REPO_ROOT))
    summary["grade_dir"] = str((private_root / "grades").relative_to(REPO_ROOT))
    summary["utc_stamp"] = stamp
    public_root.mkdir(parents=True, exist_ok=False)
    _write_json(public_root / "summary.json", summary)
    print(
        json.dumps(
            {
                "public_summary": str((public_root / "summary.json").relative_to(REPO_ROOT)),
                "passed": summary["passed"],
                "transform_failure": summary["transform_failure"],
                "malformed_arguments_preserved": summary["malformed_arguments_preserved"],
                "prompt_ids": summary["prompt_ids"],
            },
            indent=2,
        )
    )
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
