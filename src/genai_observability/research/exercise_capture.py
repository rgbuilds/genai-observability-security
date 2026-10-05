"""End-to-end capture-adapter exercise with scripted responses only.

Writes raw streams under private/ (gitignored). The checklist omits raw text.
Does not enable live capture and does not open a network connection.
"""

from __future__ import annotations

import ast
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genai_observability.paths import PACKAGE_ROOT, PRIVATE_LOCAL_READINESS_DIR, REPO_ROOT
from genai_observability.research.capture import (
    CaptureAdapter,
    LiveCaptureNotAuthorized,
    LiveOpenAIClient,
    ScriptedCompletionsClient,
    TransportError,
)
from genai_observability.research.costing import BudgetRejected, CaptureBudget, estimated_input_tokens
from genai_observability.research.protocol import LIVE_CAPTURE_AUTHORIZED, PINNED_MODEL
from genai_observability.schemas.enums import DetectorPass, SpanKind
from genai_observability.serialization import sha256_hex

UTC = timezone.utc

_NETWORK_MODULES = (
    "urllib",
    "http.client",
    "httpx",
    "requests",
    "openai",
    "socket",
    "aiohttp",
    "httplib2",
)


def _stop(text: str) -> dict[str, Any]:
    return {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 4},
    }


def _tools(calls: list[tuple[str, dict[str, str]]]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{index}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                        for index, (name, arguments) in enumerate(calls, start=1)
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 12},
    }


def _length(text: str, calls: list[tuple[str, dict[str, str]]] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if calls:
        message["tool_calls"] = [
            {
                "id": f"call_{index}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for index, (name, arguments) in enumerate(calls, start=1)
        ]
    return {
        "choices": [{"finish_reason": "length", "message": message}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 512},
    }


def _structural(record) -> dict[str, Any]:
    stream = record.stream
    kinds: dict[str, int] = {}
    tool_names: list[str] = []
    tool_status: list[int | None] = []
    detector_pass = None
    if stream is not None:
        detector_pass = stream.detector_pass.value
        for span in stream.spans:
            kinds[span.kind.value] = kinds.get(span.kind.value, 0) + 1
            if span.kind is SpanKind.TOOL:
                tool_names.append(span.name)
                tool_status.append(span.status_code)
    return {
        "prompt_id": record.prompt_id,
        "attempted": record.attempted,
        "truncated": record.truncated,
        "stop_reason": record.stop_reason,
        "requests_used": record.requests_used,
        "detector_pass": detector_pass,
        "span_kind_counts": kinds,
        "tool_names": tool_names,
        "tool_status_codes": tool_status,
        "has_stream": stream is not None,
    }


def _imports_in_research_package() -> list[str]:
    found: list[str] = []
    for path in sorted((PACKAGE_ROOT / "research").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for name in modules:
                if any(name == item or name.startswith(f"{item}.") for item in _NETWORK_MODULES):
                    found.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {name}")
    return found


def _git_check_ignore(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        result = subprocess.run(
            ["git", "check-ignore", "-v", "--", str(path)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        rows.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "ignored": result.returncode == 0,
                "check_ignore": result.stdout.strip(),
            }
        )
    return rows


def _private_in_status() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "private"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


class _ConnectGuard:
    def __init__(self) -> None:
        self.attempts: list[Any] = []
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex
        self._create = socket.create_connection

    def install(self) -> None:
        attempts = self.attempts

        def connect(sock, address):  # type: ignore[no-untyped-def]
            attempts.append(("connect", address))
            raise RuntimeError("live network connect attempted")

        def connect_ex(sock, address):  # type: ignore[no-untyped-def]
            attempts.append(("connect_ex", address))
            raise RuntimeError("live network connect_ex attempted")

        def create_connection(*args, **kwargs):  # type: ignore[no-untyped-def]
            attempts.append(("create_connection", args[:1]))
            raise RuntimeError("live network create_connection attempted")

        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
        socket.create_connection = create_connection  # type: ignore[assignment]

    def restore(self) -> None:
        socket.socket.connect = self._connect  # type: ignore[method-assign]
        socket.socket.connect_ex = self._connect_ex  # type: ignore[method-assign]
        socket.create_connection = self._create  # type: ignore[assignment]


def exercise_capture(private_dir: Path | None = None) -> dict[str, Any]:
    """Run mocked capture cases. Returns a checklist with no raw model text."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path(private_dir) if private_dir is not None else PRIVATE_LOCAL_READINESS_DIR / stamp
    root.mkdir(parents=True, exist_ok=False)
    guard = _ConnectGuard()
    guard.install()
    checks: list[dict[str, Any]] = []
    try:
        checks.append(_check_multiple_tools(root))
        checks.append(_check_no_tool(root))
        checks.append(_check_truncation(root))
        checks.append(_check_truncated_tool_continuation(root))
        checks.append(_check_retry_then_success(root))
        checks.append(_check_retry_exhausted(root))
        checks.append(_check_request_cap(root))
        checks.append(_check_dollar_ceiling(root))
        checks.append(_check_input_bound())
        checks.append(_check_live_refused())
    finally:
        guard.restore()

    network_imports = _imports_in_research_package()
    adapter_imports = [
        item
        for item in network_imports
        if not item.startswith("src/genai_observability/research/exercise_capture.py")
    ]
    checklist_path = root / "checklist.json"
    checklist_path.write_text("{}\n", encoding="utf-8")
    written = sorted(path for path in root.rglob("*") if path.is_file())
    ignore_rows = _git_check_ignore(written)
    status_lines = _private_in_status()
    payload = {
        "role": "mock-capture-exercise",
        "live_capture": "not_authorized",
        "live_capture_authorized_flag": LIVE_CAPTURE_AUTHORIZED,
        "private_dir": str(root.relative_to(REPO_ROOT)),
        "socket_connect_attempts": len(guard.attempts),
        "research_package_network_imports_excluding_guard": adapter_imports,
        "checks": checks,
        "private_files_gitignored": bool(ignore_rows) and all(row["ignored"] for row in ignore_rows),
        "git_check_ignore": ignore_rows,
        "private_paths_in_git_status": status_lines,
        "all_checks_passed": False,
    }
    payload["all_checks_passed"] = (
        all(item["passed"] for item in checks)
        and payload["socket_connect_attempts"] == 0
        and not adapter_imports
        and payload["private_files_gitignored"]
        and not status_lines
        and LIVE_CAPTURE_AUTHORIZED is False
    )
    checklist_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["checklist_sha256"] = sha256_hex(checklist_path.read_bytes())
    return payload


def _passed(name: str, ok: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": ok, **detail}


def _check_multiple_tools(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient(
        [
            _tools([("get_note", {"note_id": "note-cited"}), ("delete_account", {"note_id": "note-cited"})]),
            _stop("done"),
        ]
    )
    run = CaptureAdapter(client).run(("cap-u1",), output_dir=root / "multiple-tools")
    record = run.records[0]
    structural = _structural(record)
    ok = (
        len(run.records) == 1
        and structural["tool_names"] == ["get_note", "delete_account"]
        and structural["tool_status_codes"] == [200, 403]
        and structural["span_kind_counts"].get("model") == 2
        and structural["span_kind_counts"].get("retrieval") == 1
        and structural["detector_pass"] == DetectorPass.NOT_RUN.value
        and len(client.calls) == 2
        and all(call["model"] == PINNED_MODEL and call["max_tokens"] == 512 for call in client.calls)
        and run.unattempted_prompt_ids == []
    )
    return _passed("multiple_tool_calls", ok, {"structural": structural, "client_calls": len(client.calls)})


def _check_no_tool(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient([_stop("acknowledged")])
    run = CaptureAdapter(client).run(("cap-u5",), output_dir=root / "no-tool")
    structural = _structural(run.records[0])
    ok = (
        structural["attempted"]
        and structural["span_kind_counts"].get("tool", 0) == 0
        and structural["span_kind_counts"].get("retrieval", 0) == 0
        and structural["span_kind_counts"].get("model") == 1
        and structural["truncated"] is False
        and structural["detector_pass"] == DetectorPass.NOT_RUN.value
    )
    return _passed("no_tool_reply", ok, {"structural": structural})


def _check_truncation(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient([_length("partial")])
    run = CaptureAdapter(client).run(("cap-u5",), output_dir=root / "truncated")
    structural = _structural(run.records[0])
    ok = (
        structural["truncated"] is True
        and structural["has_stream"]
        and structural["span_kind_counts"].get("model") == 1
        and len(client.calls) == 1
        and (root / "truncated" / "cap-u5.json").is_file()
    )
    return _passed("truncation_preserved", ok, {"structural": structural, "client_calls": len(client.calls)})


def _check_truncated_tool_continuation(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient(
        [
            _length("partial", [("get_note", {"note_id": "note-u4"})]),
            _stop("title"),
        ]
    )
    record = CaptureAdapter(client).capture_prompt("cap-u4")
    structural = _structural(record)
    if record.stream is not None:
        path = root / "truncated-tool" / "cap-u4.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        from genai_observability.serialization import canonical_json_text

        path.write_text(canonical_json_text(record.stream), encoding="utf-8")
    ok = (
        structural["truncated"] is True
        and structural["tool_names"] == ["get_note"]
        and structural["tool_status_codes"] == [200]
        and structural["span_kind_counts"].get("model") == 2
        and record.requests_used == 2
    )
    return _passed(
        "truncated_complete_tool_call_continues",
        ok,
        {"structural": structural, "requests_used": record.requests_used},
    )


def _check_retry_then_success(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient([TransportError("boom"), _stop("acknowledged")])
    record = CaptureAdapter(client).capture_prompt("cap-u5")
    structural = _structural(record)
    if record.stream is not None:
        path = root / "retry-success" / "cap-u5.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        from genai_observability.serialization import canonical_json_text

        path.write_text(canonical_json_text(record.stream), encoding="utf-8")
    ok = record.attempted and record.requests_used == 2 and structural["span_kind_counts"].get("model") == 1
    return _passed("retry_then_success", ok, {"structural": structural})


def _check_retry_exhausted(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient([TransportError("boom"), TransportError("boom")])
    record = CaptureAdapter(client).capture_prompt("cap-u3")
    structural = _structural(record)
    if record.stream is not None:
        path = root / "retry-exhausted" / "cap-u3.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        from genai_observability.serialization import canonical_json_text

        path.write_text(canonical_json_text(record.stream), encoding="utf-8")
    ok = (
        record.attempted
        and record.stop_reason == "transport_exhausted"
        and record.requests_used == 2
        and structural["has_stream"]
        and structural["span_kind_counts"].get("model", 0) == 0
    )
    return _passed("retry_exhausted_keeps_partial", ok, {"structural": structural})


def _check_request_cap(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient([_stop("acknowledged")])
    budget = CaptureBudget(requests_used=11)
    run = CaptureAdapter(client, budget).run(("cap-u5", "cap-u1", "cap-u6"), output_dir=root / "request-cap")
    ok = (
        [item.prompt_id for item in run.records] == ["cap-u5"]
        and run.unattempted_prompt_ids == ["cap-u1", "cap-u6"]
        and (root / "request-cap" / "cap-u5.json").is_file()
        and not (root / "request-cap" / "cap-u1.json").exists()
        and run.requests_used == 12
        and len(client.calls) == 1
    )
    unattempted = json.loads((root / "request-cap" / "unattempted_prompts.json").read_text(encoding="utf-8"))
    return _passed(
        "request_cap_exhaustion",
        ok and unattempted["unattempted_prompt_ids"] == ["cap-u1", "cap-u6"],
        {
            "attempted": [item.prompt_id for item in run.records],
            "unattempted": run.unattempted_prompt_ids,
            "requests_used": run.requests_used,
            "stop_reason": run.stop_reason,
        },
    )


def _check_dollar_ceiling(root: Path) -> dict[str, Any]:
    client = ScriptedCompletionsClient([_stop("acknowledged")])
    budget = CaptureBudget(spent_usd=5.00)
    run = CaptureAdapter(client, budget).run(("cap-u5", "cap-u1"), output_dir=root / "dollar-ceiling")
    ok = (
        run.records == []
        and run.unattempted_prompt_ids == ["cap-u5", "cap-u1"]
        and client.calls == []
        and not (root / "dollar-ceiling" / "cap-u5.json").exists()
        and (root / "dollar-ceiling" / "unattempted_prompts.json").is_file()
    )
    return _passed(
        "dollar_ceiling_before_send",
        ok,
        {"unattempted": run.unattempted_prompt_ids, "client_calls": len(client.calls), "stop_reason": run.stop_reason},
    )


def _check_input_bound() -> dict[str, Any]:
    client = ScriptedCompletionsClient([_stop("acknowledged")])
    request = {"messages": [{"role": "user", "content": "x" * 20000}], "tools": [{"schema": "y" * 2000}]}
    tokens = estimated_input_tokens(request)
    rejected = False
    try:
        CaptureAdapter(client).budget.check(request)
    except BudgetRejected as exc:
        rejected = str(exc) == "input_bound"
    ok = tokens > 4096 and rejected and client.calls == []
    return _passed("input_token_bound", ok, {"estimated_input_tokens": tokens, "client_calls": len(client.calls)})


def _check_live_refused() -> dict[str, Any]:
    refused_construct = False
    refused_complete = False
    try:
        CaptureAdapter(LiveOpenAIClient())
    except LiveCaptureNotAuthorized:
        refused_construct = True
    try:
        LiveOpenAIClient().complete({"model": PINNED_MODEL, "messages": []})
    except LiveCaptureNotAuthorized:
        refused_complete = True
    return _passed(
        "live_client_refused",
        refused_construct and refused_complete and LIVE_CAPTURE_AUTHORIZED is False,
        {
            "construct_refused": refused_construct,
            "complete_refused": refused_complete,
            "live_capture_authorized": LIVE_CAPTURE_AUTHORIZED,
        },
    )


def main() -> int:
    payload = exercise_capture()
    print(
        json.dumps(
            {
                "private_dir": payload["private_dir"],
                "all_checks_passed": payload["all_checks_passed"],
                "checks": [{"name": item["name"], "passed": item["passed"]} for item in payload["checks"]],
                "socket_connect_attempts": payload["socket_connect_attempts"],
                "private_files_gitignored": payload["private_files_gitignored"],
                "private_paths_in_git_status": payload["private_paths_in_git_status"],
                "network_imports": payload["research_package_network_imports_excluding_guard"],
            },
            indent=2,
        )
    )
    return 0 if payload["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
