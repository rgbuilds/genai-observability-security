"""Capture adapter. Tests inject a scripted client. Live HTTP is opt-in."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from genai_observability.paths import PRIVATE_CAPTURE_DIR
from genai_observability.research.clock import Clock, SystemClock
from genai_observability.research.costing import BudgetRejected, CaptureBudget
from genai_observability.research.protocol import (
    CAPTURE_PRINCIPAL,
    MAX_OUTPUT_TOKENS,
    PINNED_MODEL,
    PROMPT_ORDER,
    SYSTEM_INSTRUCTIONS,
    TEMPERATURE,
    TOOL_SCHEMAS,
    USER_PROMPTS,
    ToolArgumentError,
    execute_mock_tool,
    retrieval_context_message,
    route_tool,
    select_retrieval,
    sent_retrieval,
    validate_tool_arguments,
)
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import DetectorPass
from genai_observability.serialization import canonical_json_text

UTC = timezone.utc


class LiveCaptureNotAuthorized(RuntimeError):
    """Live / paid capture is not authorized by this revision."""


class NonemptyCaptureDirectoryError(ValueError):
    """Refused to write into a capture destination that already has files."""


class CompletionsClient(Protocol):
    def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return a chat-completions-shaped dict. Must not perform live HTTP."""


class TransportError(RuntimeError):
    """Mockable transport failure. A retry counts as a new request."""


class LiveOpenAIClient:
    """Chat Completions client. Sends only when constructed with authorized=True and an API key."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        authorized: bool = False,
        sender: Any = None,
    ) -> None:
        self.api_key = api_key
        self.authorized = authorized
        self._sender = sender

    def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.authorized or not self.api_key:
            raise LiveCaptureNotAuthorized(
                "Live capture is opt-in. Run the live command with GENAI_LIVE_CAPTURE=1 and OPENAI_API_KEY."
            )
        if request.get("model") != PINNED_MODEL:
            raise LiveCaptureNotAuthorized(
                f"Refusing model {request.get('model')!r}. The live pin is {PINNED_MODEL}."
            )
        sender = self._sender
        if sender is None:
            from genai_observability.research.live_http import post_chat_completions

            sender = post_chat_completions
        return sender(self.api_key, request)


class ScriptedCompletionsClient:
    """Injectable mock. Each complete() pops the next scripted response."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(request)
        if not self._responses:
            raise AssertionError("scripted client received an unexpected extra request")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class CaptureRecord:
    prompt_id: str
    attempted: bool
    truncated: bool = False
    stop_reason: str | None = None
    requests_used: int = 0
    stream: CanonicalEventStream | None = None
    failures: list[dict[str, Any]] = field(default_factory=list)
    partial: bool = False


@dataclass
class CaptureRun:
    records: list[CaptureRecord] = field(default_factory=list)
    unattempted_prompt_ids: list[str] = field(default_factory=list)
    requests_used: int = 0
    estimated_spent_usd: float = 0.0
    stop_reason: str | None = None
    output_dir: Path | None = None


def prepare_capture_dir(output_dir: Path | None = None) -> Path:
    """Create a unique capture directory, or reject a nonempty explicit destination.

    This only touches the filesystem. It does not send a model request.
    """
    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = PRIVATE_CAPTURE_DIR / stamp
        suffix = 2
        while dest.exists():
            dest = PRIVATE_CAPTURE_DIR / f"{stamp}-{suffix}"
            suffix += 1
        dest.mkdir(parents=True, exist_ok=False)
        return dest
    dest = Path(output_dir)
    if dest.exists() and dest.is_file():
        raise NonemptyCaptureDirectoryError(f"destination is a file: {dest}")
    if dest.exists() and any(dest.iterdir()):
        raise NonemptyCaptureDirectoryError(
            f"destination is not empty: {dest}; pass a new path or omit it for a unique capture directory"
        )
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _build_request(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": PINNED_MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
    }


def _assistant_text(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else None


def _tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    choices = response.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    calls = message.get("tool_calls") or []
    return list(calls) if isinstance(calls, list) else []


def _finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    return choices[0].get("finish_reason")


def _span(
    span_id: str,
    parent: str | None,
    name: str,
    kind: str,
    start: str,
    end: str,
    duration_ms: int,
    status: str = "ok",
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "span_id": span_id,
        "parent_span_id": parent,
        "name": name,
        "kind": kind,
        "start_time": start,
        "end_time": end,
        "duration_ms": duration_ms,
        "status": status,
    }
    payload.update(extra)
    return payload


def _stream_or_none(prompt_id: str, spans: list[dict[str, Any]]) -> CanonicalEventStream | None:
    if not spans:
        return None
    return CanonicalEventStream.model_validate(
        {
            "scenario_id": prompt_id,
            "request_id": f"req-{prompt_id}",
            "trace_id": f"trace-{prompt_id}",
            "detector_pass": DetectorPass.NOT_RUN,
            "spans": spans,
        }
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def persist_record(output_dir: Path | None, record: CaptureRecord) -> None:
    """Write one capture's stream and metadata. Unattempted prompts are not given a stream."""
    if output_dir is None or not record.attempted:
        return
    if record.stream is not None:
        stream_path = output_dir / f"{record.prompt_id}.json"
        stream_path.write_text(canonical_json_text(record.stream), encoding="utf-8")
    _write_json(
        output_dir / f"{record.prompt_id}.meta.json",
        {
            "prompt_id": record.prompt_id,
            "attempted": record.attempted,
            "truncated": record.truncated,
            "stop_reason": record.stop_reason,
            "requests_used": record.requests_used,
            "failures": record.failures,
            "partial": record.partial,
        },
    )


def persist_unattempted(output_dir: Path, run: CaptureRun) -> None:
    _write_json(
        output_dir / "unattempted_prompts.json",
        {
            "unattempted_prompt_ids": run.unattempted_prompt_ids,
            "stop_reason": run.stop_reason,
            "requests_used": run.requests_used,
        },
    )


class CaptureAdapter:
    """Run the frozen prompt protocol against an injected client."""

    def __init__(
        self,
        client: CompletionsClient,
        budget: CaptureBudget | None = None,
        clock: Clock | None = None,
    ) -> None:
        if isinstance(client, LiveOpenAIClient) and not client.authorized:
            raise LiveCaptureNotAuthorized(
                "Live capture is opt-in. Pass an authorized LiveOpenAIClient or a scripted client."
            )
        self.client = client
        self.budget = budget or CaptureBudget()
        self.clock = clock or SystemClock()
        self.output_dir: Path | None = None

    def _times(self) -> tuple[str, str, int]:
        token = self.clock.start()
        return self.clock.finish(token)

    def _send(self, request: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for _attempt in range(2):
            self.budget.consume(request)
            try:
                return self.client.complete(request)
            except TransportError as exc:
                last_error = exc
                continue
        raise TransportError("two transport failures on the same hop") from last_error

    def _checkpoint(
        self,
        prompt_id: str,
        spans: list[dict[str, Any]],
        *,
        requests_before: int,
        truncated: bool,
        stop_reason: str | None,
        failures: list[dict[str, Any]],
        partial: bool,
    ) -> CaptureRecord:
        attempted = self.budget.requests_used > requests_before
        record = CaptureRecord(
            prompt_id=prompt_id,
            attempted=attempted,
            truncated=truncated,
            stop_reason=stop_reason,
            requests_used=self.budget.requests_used - requests_before,
            stream=_stream_or_none(prompt_id, spans) if attempted else None,
            failures=list(failures),
            partial=partial,
        )
        persist_record(self.output_dir, record)
        return record

    def capture_prompt(self, prompt_id: str) -> CaptureRecord:
        user_text = USER_PROMPTS[prompt_id]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_text},
        ]
        spans: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        start, end, duration = self._times()
        request_span_id = f"sp-{prompt_id}-req"
        spans.append(
            _span(
                request_span_id,
                None,
                "handle_request",
                "request",
                start,
                end,
                duration,
                status_code=200,
                content={"system": SYSTEM_INSTRUCTIONS, "user": user_text},
                authz={"principal_id": CAPTURE_PRINCIPAL, "roles": ["member"]},
            )
        )
        retrieval = select_retrieval(prompt_id, user_text)
        if retrieval is not None:
            note_id, body = retrieval
            message = retrieval_context_message(note_id, body)
            messages.append(message)
            recorded_id, recorded_body = sent_retrieval(message["content"])
            start, end, duration = self._times()
            spans.append(
                _span(
                    f"sp-{prompt_id}-ret",
                    request_span_id,
                    "retrieve_notes",
                    "retrieval",
                    start,
                    end,
                    duration,
                    retrieval={"source_id": recorded_id},
                    content={"retrieved": recorded_body},
                )
            )
        truncated = False
        requests_before = self.budget.requests_used
        hop = 0
        argument_failure: str | None = None
        try:
            while True:
                request = _build_request(messages)
                model_token = self.clock.start()
                response = self._send(request)
                start, end, duration = self.clock.finish(model_token)
                hop += 1
                finish = _finish_reason(response)
                text = _assistant_text(response)
                calls = _tool_calls(response)
                usage = response.get("usage") or {}
                model_extra: dict[str, Any] = {
                    "model": {"provider": "openai", "name": PINNED_MODEL},
                    "tokens": {
                        "input": usage.get("prompt_tokens"),
                        "output": usage.get("completion_tokens"),
                    },
                }
                if text is not None:
                    model_extra["content"] = {"output": text}
                spans.append(
                    _span(
                        f"sp-{prompt_id}-mdl{hop}",
                        request_span_id,
                        "chat.completion",
                        "model",
                        start,
                        end,
                        duration,
                        **model_extra,
                    )
                )
                if finish == "length":
                    truncated = True
                if not calls:
                    self._checkpoint(
                        prompt_id,
                        spans,
                        requests_before=requests_before,
                        truncated=truncated,
                        stop_reason="truncated" if truncated else None,
                        failures=failures,
                        partial=True,
                    )
                    break
                assistant_message = (response.get("choices") or [{}])[0].get("message") or {}
                messages.append(assistant_message)
                for call_index, call in enumerate(calls, start=1):
                    function = call.get("function") or {}
                    name = function.get("name") if isinstance(function.get("name"), str) else "unknown"
                    raw_arguments = function.get("arguments")
                    try:
                        arguments = validate_tool_arguments(
                            name,
                            raw_arguments,
                            truncated=finish == "length",
                        )
                    except ToolArgumentError as exc:
                        argument_failure = exc.kind
                        failures.append(
                            {
                                "kind": exc.kind,
                                "tool": name,
                                "preserved": True,
                            }
                        )
                        start, end, duration = self._times()
                        spans.append(
                            _failure_tool_span(
                                prompt_id,
                                request_span_id,
                                hop,
                                call_index,
                                name,
                                start,
                                end,
                                duration,
                                exc,
                            )
                        )
                        continue
                    tool_token = self.clock.start()
                    result = execute_mock_tool(name, arguments)
                    decision, status_code = route_tool(name)
                    start, end, duration = self.clock.finish(tool_token)
                    tool_status = "ok" if status_code == 200 else "error"
                    note_id = arguments.get("note_id")
                    authz: dict[str, Any] = {
                        "principal_id": CAPTURE_PRINCIPAL,
                        "roles": ["member"],
                    }
                    if isinstance(note_id, str):
                        authz["resource"] = note_id
                    spans.append(
                        _span(
                            f"sp-{prompt_id}-tol{hop}-{call_index}",
                            request_span_id,
                            name,
                            "tool",
                            start,
                            end,
                            duration,
                            status=tool_status,
                            status_code=status_code,
                            tool={
                                "name": name,
                                "type": "read" if name == "get_note" else "action",
                            },
                            content={"tool_args": arguments, "tool_result": result},
                            authz=authz,
                            security={
                                "privilege_class": "privileged" if name == "delete_account" else "none",
                                "authz_decision": decision,
                                "denial_reason": "authorization" if decision == "deny" else "none",
                            },
                        )
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id") or f"call-{call_index}",
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                self._checkpoint(
                    prompt_id,
                    spans,
                    requests_before=requests_before,
                    truncated=truncated,
                    stop_reason=argument_failure,
                    failures=failures,
                    partial=True,
                )
                if argument_failure is not None:
                    break
        except BudgetRejected as exc:
            failures.append({"kind": str(exc)})
            return self._checkpoint(
                prompt_id,
                spans,
                requests_before=requests_before,
                truncated=truncated,
                stop_reason=str(exc),
                failures=failures,
                partial=True,
            )
        except TransportError:
            failures.append({"kind": "transport_exhausted"})
            return self._checkpoint(
                prompt_id,
                spans,
                requests_before=requests_before,
                truncated=truncated,
                stop_reason="transport_exhausted",
                failures=failures,
                partial=True,
            )
        stop_reason = argument_failure or ("truncated" if truncated else None)
        return self._checkpoint(
            prompt_id,
            spans,
            requests_before=requests_before,
            truncated=truncated,
            stop_reason=stop_reason,
            failures=failures,
            partial=stop_reason is not None,
        )

    def run(
        self,
        prompt_ids: tuple[str, ...] | list[str] | None = None,
        output_dir: Path | None = None,
    ) -> CaptureRun:
        dest = prepare_capture_dir(output_dir)
        self.output_dir = dest
        ordered = list(prompt_ids or PROMPT_ORDER)
        run = CaptureRun(output_dir=dest)
        remaining = list(ordered)
        while remaining:
            prompt_id = remaining[0]
            try:
                record = self.capture_prompt(prompt_id)
            except BudgetRejected as exc:
                run.stop_reason = str(exc)
                run.requests_used = self.budget.requests_used
                run.estimated_spent_usd = self.budget.spent_usd
                run.unattempted_prompt_ids.extend(remaining)
                persist_unattempted(dest, run)
                break
            remaining.pop(0)
            run.requests_used = self.budget.requests_used
            run.estimated_spent_usd = self.budget.spent_usd
            if not record.attempted:
                run.stop_reason = record.stop_reason
                run.unattempted_prompt_ids.append(prompt_id)
                run.unattempted_prompt_ids.extend(remaining)
                persist_unattempted(dest, run)
                break
            run.records.append(record)
            if record.stop_reason in {"request_cap", "dollar_ceiling", "input_bound"}:
                run.stop_reason = record.stop_reason
                run.unattempted_prompt_ids.extend(remaining)
                persist_unattempted(dest, run)
                break
        else:
            persist_unattempted(dest, run)
        run.requests_used = self.budget.requests_used
        run.estimated_spent_usd = self.budget.spent_usd
        return run


def _failure_tool_span(
    prompt_id: str,
    parent: str,
    hop: int,
    call_index: int,
    name: str,
    start: str,
    end: str,
    duration: int,
    exc: ToolArgumentError,
) -> dict[str, Any]:
    tool_result: dict[str, Any] = {
        "ok": False,
        "executed": False,
        "error": exc.kind,
    }
    if isinstance(exc.raw, str):
        tool_result["argument_text"] = exc.raw
    return _span(
        f"sp-{prompt_id}-tol{hop}-{call_index}",
        parent,
        name,
        "tool",
        start,
        end,
        duration,
        status="error",
        tool={"name": name, "type": "read" if name == "get_note" else "action"},
        content={"tool_args": exc.evidence, "tool_result": tool_result},
        security={"denial_reason": "validation"},
    )
