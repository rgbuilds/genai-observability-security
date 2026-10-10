"""Capture-once adapter for the 24 full-study executions. Live HTTP is opt-in."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from genai_observability.full_study.inventory import inventory_from_realized_stream
from genai_observability.full_study.protocol import (
    CHECKLIST_VERSION,
    LIVE_FULL_STUDY_AUTHORIZED,
    LIVE_ENV_FLAG,
    OFFICIAL_DOC_CHECK,
    OFFICIAL_DOC_MAX_AGE_DAYS,
    PROPOSED_DOLLAR_CEILING_USD,
    PROPOSED_INPUT_TOKEN_BOUND,
    PROPOSED_MAX_OUTPUT_TOKENS,
    PROPOSED_PINNED_MODEL,
    PROPOSED_REQUEST_CAP,
    PROPOSED_TEMPERATURE,
    PROTOCOL_VERSION,
)
from genai_observability.full_study.scenarios import capture_once_specs
from genai_observability.full_study.select import select_full_study_references
from genai_observability.full_study.surface import (
    FULL_STUDY_TOOL_SCHEMAS,
    execute_full_study_tool,
    privilege_for_tool,
    route_full_study_tool,
    select_spec_retrieval,
    system_for_spec,
    validate_tool_arguments,
)
from genai_observability.paths import (
    FULL_STUDY_LIVE_SOURCE_FREEZE_PATH,
    PACKAGE_ROOT,
    PRIVATE_FULL_STUDY_CAPTURE_DIR,
    REPO_ROOT,
)
from genai_observability.research.capture import (
    CaptureRecord,
    CaptureRun,
    CompletionsClient,
    LiveCaptureNotAuthorized,
    LiveOpenAIClient,
    NonemptyCaptureDirectoryError,
    TransportError,
    persist_record,
    persist_unattempted,
    secure_capture_directory,
    secure_capture_write_text,
)
from genai_observability.research.clock import Clock, SystemClock
from genai_observability.research.costing import BudgetRejected, CaptureBudget
from genai_observability.research.protocol import ToolArgumentError, retrieval_context_message, sent_retrieval
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import DetectorPass
from genai_observability.serialization import canonical_json_text, sha256_hex
from genai_observability.transforms.apply import opaque_identifier
from genai_observability.validation.provenance import collect_provenance, hash_paths

UTC = timezone.utc
_CHECK_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CAPTURE_CONFIGURATION_RELATIVE_PATHS: tuple[str, ...] = (
    "policies/allowlists/p0.v1.json",
    "policies/allowlists/p1.v1.json",
    "policies/allowlists/p2.v1.json",
    "policies/allowlists/p3.v1.json",
    "policies/pattern_libraries/pattern_library.v1.json",
)

CAPTURE_INPUT_RELATIVE_PATHS: tuple[str, ...] = (
    "src/genai_observability/full_study/protocol.py",
    "src/genai_observability/full_study/questions.py",
    "src/genai_observability/full_study/references.py",
    "src/genai_observability/full_study/scenarios.py",
    "src/genai_observability/full_study/surface.py",
)

CAPTURE_SOURCE_RELATIVE_PATHS: tuple[str, ...] = tuple(
    sorted(path.relative_to(REPO_ROOT).as_posix() for path in PACKAGE_ROOT.rglob("*.py"))
) + CAPTURE_CONFIGURATION_RELATIVE_PATHS


class MalformedCompletionError(ValueError):
    """A transport success was not a usable chat-completions response."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def full_study_budget() -> CaptureBudget:
    return CaptureBudget(
        request_cap=PROPOSED_REQUEST_CAP,
        dollar_ceiling_usd=PROPOSED_DOLLAR_CEILING_USD,
        input_token_bound=PROPOSED_INPUT_TOKEN_BOUND,
    )


def validate_official_doc_check(
    record: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> date:
    """Validate the recorded official facts and require a recent completed check."""
    facts = record if record is not None else OFFICIAL_DOC_CHECK
    checked = facts.get("checked_on")
    if not isinstance(checked, str) or not _CHECK_DATE.fullmatch(checked):
        raise LiveCaptureNotAuthorized("Official doc check date is missing or invalid.")
    try:
        checked_date = date.fromisoformat(checked)
    except ValueError as exc:
        raise LiveCaptureNotAuthorized("Official doc check date is missing or invalid.") from exc
    required = {
        "snapshot": PROPOSED_PINNED_MODEL,
        "function_calling": True,
        "input_usd_per_million": 0.15,
        "output_usd_per_million": 0.60,
        "max_tokens_512_supported": True,
    }
    for key, expected in required.items():
        if facts.get(key) != expected:
            raise LiveCaptureNotAuthorized(
                f"Official doc record {key}={facts.get(key)!r} does not match "
                "full-study-protocol.v1. Record an amendment; do not change the pin silently."
            )
    max_output = facts.get("max_output_tokens")
    if not isinstance(max_output, int) or max_output < PROPOSED_MAX_OUTPUT_TOKENS:
        raise LiveCaptureNotAuthorized("Recorded max output is below max_tokens=512.")
    if facts.get("live_recheck_required") is True:
        raise LiveCaptureNotAuthorized("Official model-page recheck is still required.")
    if facts.get("live_recheck_required") is not False:
        raise LiveCaptureNotAuthorized(
            "Official doc live_recheck_required is not a completed check."
        )
    current = today or datetime.now(UTC).date()
    age_days = (current - checked_date).days
    if age_days < 0 or age_days > OFFICIAL_DOC_MAX_AGE_DAYS:
        raise LiveCaptureNotAuthorized(
            f"Official doc check is stale; it must be no more than "
            f"{OFFICIAL_DOC_MAX_AGE_DAYS} day old."
        )
    return checked_date


def prepare_full_study_capture_dir(output_dir: Path | None = None) -> Path:
    if output_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = PRIVATE_FULL_STUDY_CAPTURE_DIR / stamp
        suffix = 2
        while dest.exists():
            dest = PRIVATE_FULL_STUDY_CAPTURE_DIR / f"{stamp}-{suffix}"
            suffix += 1
        secure_capture_directory(dest, exist_ok=False)
        return dest
    dest = Path(output_dir)
    if dest.exists() and dest.is_file():
        raise NonemptyCaptureDirectoryError(f"destination is a file: {dest}")
    if dest.exists() and any(dest.iterdir()):
        raise NonemptyCaptureDirectoryError(f"destination is not empty: {dest}")
    secure_capture_directory(dest)
    return dest


def frozen_source_hashes() -> dict[str, Any]:
    return hash_paths(sorted(REPO_ROOT / relative for relative in CAPTURE_SOURCE_RELATIVE_PATHS))


def capture_configuration_hashes() -> dict[str, Any]:
    return hash_paths(
        sorted(REPO_ROOT / relative for relative in CAPTURE_CONFIGURATION_RELATIVE_PATHS)
    )


def capture_input_hashes() -> dict[str, Any]:
    return hash_paths(sorted(REPO_ROOT / relative for relative in CAPTURE_INPUT_RELATIVE_PATHS))


def artifact_hashes(output_dir: Path) -> dict[str, Any]:
    """Hash every persisted JSON artifact except the hash manifest itself."""
    files: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*.json"), key=lambda item: item.as_posix()):
        relative = path.relative_to(output_dir).as_posix()
        if relative == "artifact_hashes.json":
            continue
        files[relative] = sha256_hex(path.read_bytes())
    combined = sha256_hex(
        "\n".join(f"{name}={digest}" for name, digest in files.items()).encode("utf-8")
    )
    return {
        "schema_version": "full_study_artifact_hashes.v1",
        "algorithm": "sha256",
        "files": files,
        "combined": combined,
    }


def load_expected_source_hash(path: Path | None = None) -> dict[str, Any]:
    dest = path if path is not None else FULL_STUDY_LIVE_SOURCE_FREEZE_PATH
    if not dest.is_file():
        raise RuntimeError("expected live-capture source hash is missing")
    try:
        payload = json.loads(dest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("expected live-capture source hash is invalid") from exc
    combined = payload.get("combined") if isinstance(payload, dict) else None
    if not isinstance(combined, str) or len(combined) != 64:
        raise RuntimeError("expected live-capture source hash is invalid")
    if any(char not in "0123456789abcdef" for char in combined):
        raise RuntimeError("expected live-capture source hash is invalid")
    return payload


def verify_source_hashes(
    expected: dict[str, Any] | None = None,
    observed: dict[str, Any] | None = None,
) -> None:
    recorded = expected if expected is not None else load_expected_source_hash()
    actual = observed if observed is not None else frozen_source_hashes()
    if actual.get("combined") != recorded.get("combined"):
        raise RuntimeError("full-study capture source hashes do not match the recorded freeze")


def _write_json(path: Path, payload: Any, *, root: Path) -> None:
    secure_capture_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        root=root,
    )


def _build_request(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": PROPOSED_PINNED_MODEL,
        "temperature": PROPOSED_TEMPERATURE,
        "max_tokens": PROPOSED_MAX_OUTPUT_TOKENS,
        "messages": messages,
        "tools": FULL_STUDY_TOOL_SCHEMAS,
    }


def completion_shape_error(response: Any) -> str | None:
    """Return a structural label, or None when the response has one usable assistant turn."""
    if not isinstance(response, dict):
        return "response_not_object"
    if "choices" not in response:
        return "choices_missing"
    choices = response["choices"]
    if not isinstance(choices, list):
        return "choices_not_list"
    if len(choices) == 0:
        return "choices_empty"
    if len(choices) > 1:
        return "multiple_choices"
    choice = choices[0]
    if not isinstance(choice, dict):
        return "choice_not_object"
    finish = choice.get("finish_reason")
    if finish is None:
        return "finish_reason_missing"
    if not isinstance(finish, str):
        return "finish_reason_not_string"
    if finish == "content_filter":
        return "finish_reason_content_filter"
    if finish not in {"stop", "tool_calls", "length"}:
        return "finish_reason_unknown"
    if "message" not in choice:
        return "message_missing"
    message = choice["message"]
    if not isinstance(message, dict):
        return "message_not_object"
    content = message.get("content")
    has_text = isinstance(content, str) and bool(content)
    calls = message.get("tool_calls")
    has_calls = isinstance(calls, list) and len(calls) > 0
    if not has_text and not has_calls:
        return "neither_text_nor_tool_calls"
    if finish == "stop" and has_calls:
        return "stop_with_tool_calls"
    if finish == "tool_calls" and not has_calls:
        return "tool_calls_without_calls"
    return None


def _assistant_text(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    content = (choices[0].get("message") or {}).get("content")
    return content if isinstance(content, str) else None


def _tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    choices = response.get("choices") or []
    if not choices:
        return []
    calls = (choices[0].get("message") or {}).get("tool_calls") or []
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


def _stream_or_none(execution_id: str, spans: list[dict[str, Any]]) -> CanonicalEventStream | None:
    if not spans:
        return None
    return CanonicalEventStream.model_validate(
        {
            "scenario_id": execution_id,
            "request_id": f"req-{execution_id}",
            "trace_id": f"trace-{execution_id}",
            "detector_pass": DetectorPass.NOT_RUN,
            "spans": spans,
        }
    )


def _failure_tool_span(
    execution_id: str,
    parent: str,
    hop: int,
    call_index: int,
    name: str,
    start: str,
    end: str,
    duration: int,
    exc: ToolArgumentError,
) -> dict[str, Any]:
    tool_result: dict[str, Any] = {"ok": False, "executed": False, "error": exc.kind}
    if isinstance(exc.raw, str):
        tool_result["argument_text"] = exc.raw
    return _span(
        f"sp-{execution_id}-tol{hop}-{call_index}",
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


class FullStudyCaptureAdapter:
    """Run the 24 capture-once specs against an injected client."""

    def __init__(
        self,
        client: CompletionsClient,
        budget: CaptureBudget | None = None,
        clock: Clock | None = None,
    ) -> None:
        if LIVE_FULL_STUDY_AUTHORIZED:
            raise LiveCaptureNotAuthorized("LIVE_FULL_STUDY_AUTHORIZED must remain false")
        if isinstance(client, LiveOpenAIClient) and not client.authorized:
            raise LiveCaptureNotAuthorized(
                "Full-study live capture is opt-in. Pass an authorized client or a scripted client."
            )
        self.client = client
        self.budget = budget or full_study_budget()
        self._accounted_requests = self.budget.requests_used
        self._accounted_spend = self.budget.spent_usd
        self.clock = clock or SystemClock()
        self.output_dir: Path | None = None

    def _times(self) -> tuple[str, str, int]:
        token = self.clock.start()
        return self.clock.finish(token)

    def _refuse_unless_live_send_ready(self) -> None:
        """Enforce live gates at the last boundary before client.complete()."""
        if not isinstance(self.client, LiveOpenAIClient):
            return
        if os.environ.get(LIVE_ENV_FLAG) != "1":
            raise LiveCaptureNotAuthorized(f"{LIVE_ENV_FLAG}=1 is required for a live send.")
        if not self.client.authorized:
            raise LiveCaptureNotAuthorized("The live client is not authorized.")
        if type(self.budget) is not CaptureBudget:
            raise LiveCaptureNotAuthorized("Live capture requires the frozen CaptureBudget type.")
        if (
            self.budget.request_cap != PROPOSED_REQUEST_CAP
            or self.budget.dollar_ceiling_usd != PROPOSED_DOLLAR_CEILING_USD
            or self.budget.input_token_bound != PROPOSED_INPUT_TOKEN_BOUND
        ):
            raise LiveCaptureNotAuthorized(
                "Live capture requires the frozen 80-request, USD 15, and 4096-token limits."
            )
        if (
            self.budget.requests_used < 0
            or self.budget.requests_used > PROPOSED_REQUEST_CAP
            or self.budget.spent_usd < 0
            or self.budget.spent_usd > PROPOSED_DOLLAR_CEILING_USD
        ):
            raise LiveCaptureNotAuthorized("Live capture budget accounting is outside its bounds.")
        if (
            self.budget.requests_used != self._accounted_requests
            or self.budget.spent_usd != self._accounted_spend
        ):
            raise LiveCaptureNotAuthorized(
                "Live capture budget counters changed outside the adapter."
            )
        validate_official_doc_check()
        verify_source_hashes()
        if self.output_dir is None:
            raise LiveCaptureNotAuthorized(
                "Live capture must use run() so a unique private destination exists."
            )
        try:
            self.output_dir.resolve().relative_to(PRIVATE_FULL_STUDY_CAPTURE_DIR.resolve())
        except ValueError as exc:
            raise LiveCaptureNotAuthorized(
                "Live capture output must be under private/full-study-captures."
            ) from exc
        if not (self.output_dir / "provenance.json").is_file():
            raise LiveCaptureNotAuthorized(
                "Live capture provenance must be persisted before the first send."
            )
        provenance = collect_provenance()
        if not isinstance(provenance.get("git_commit"), str):
            raise LiveCaptureNotAuthorized("Live capture requires a Git commit.")
        if provenance.get("git_dirty") is not False:
            raise LiveCaptureNotAuthorized("Live capture requires a clean Git working tree.")

    def _write_artifact_hashes(self) -> None:
        if self.output_dir is None:
            return
        _write_json(
            self.output_dir / "artifact_hashes.json",
            artifact_hashes(self.output_dir),
            root=self.output_dir,
        )

    def _send(self, request: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for _attempt in range(2):
            self._refuse_unless_live_send_ready()
            self.budget.consume(request)
            self._accounted_requests = self.budget.requests_used
            self._accounted_spend = self.budget.spent_usd
            try:
                return self.client.complete(request)
            except TransportError as exc:
                last_error = exc
                continue
        raise TransportError("two transport failures on the same hop") from last_error

    def _persist_root(self) -> Path | None:
        if self.output_dir is None:
            return None
        captures = self.output_dir / "captures"
        secure_capture_directory(captures, root=self.output_dir)
        return captures

    def _checkpoint(
        self,
        execution_id: str,
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
            prompt_id=execution_id,
            attempted=attempted,
            truncated=truncated,
            stop_reason=stop_reason,
            requests_used=self.budget.requests_used - requests_before,
            stream=_stream_or_none(execution_id, spans) if attempted else None,
            failures=list(failures),
            partial=partial,
        )
        persist_record(self._persist_root(), record)
        self._write_artifact_hashes()
        return record

    def capture_spec(self, spec: dict[str, Any]) -> CaptureRecord:
        execution_id = spec["execution_id"]
        system = system_for_spec(spec)
        user_text = spec["user"]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]
        spans: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        start, end, duration = self._times()
        request_span_id = f"sp-{execution_id}-req"
        authz = {
            "principal_id": spec["principal"],
            "roles": spec["roles"],
        }
        if spec.get("resource"):
            authz["resource"] = spec["resource"]
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
                content={"system": system, "user": user_text},
                authz=authz,
                security={"trust_class": "untrusted"},
            )
        )
        retrieval = select_spec_retrieval(spec)
        if retrieval is not None:
            note_id, body = retrieval
            message = retrieval_context_message(note_id, body)
            messages.append(message)
            recorded_id, recorded_body = sent_retrieval(message["content"])
            start, end, duration = self._times()
            spans.append(
                _span(
                    f"sp-{execution_id}-ret",
                    request_span_id,
                    "retrieve_notes",
                    "retrieval",
                    start,
                    end,
                    duration,
                    retrieval={
                        "source_id": recorded_id,
                        "hash": opaque_identifier(recorded_id),
                    },
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
                shape_error = completion_shape_error(response)
                if shape_error is not None:
                    raise MalformedCompletionError(shape_error)
                finish = _finish_reason(response)
                text = _assistant_text(response)
                calls = _tool_calls(response)
                reported_model = response.get("model")
                if isinstance(self.client, LiveOpenAIClient):
                    if not isinstance(reported_model, str) or not reported_model:
                        raise MalformedCompletionError("reported_model_missing")
                    if reported_model != PROPOSED_PINNED_MODEL:
                        raise MalformedCompletionError("reported_model_mismatch")
                model_name = (
                    reported_model
                    if isinstance(reported_model, str) and reported_model
                    else PROPOSED_PINNED_MODEL
                )
                usage = response.get("usage") or {}
                model_extra: dict[str, Any] = {
                    "model": {"provider": "openai", "name": model_name},
                    "tokens": {
                        "input": usage.get("prompt_tokens"),
                        "output": usage.get("completion_tokens"),
                    },
                }
                if text is not None:
                    model_extra["content"] = {"output": text}
                spans.append(
                    _span(
                        f"sp-{execution_id}-mdl{hop}",
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
                    if calls:
                        failures.append({"kind": "truncated_tool_calls", "preserved": True})
                        for call_index, call in enumerate(calls, start=1):
                            function = call.get("function") if isinstance(call, dict) else None
                            function = function if isinstance(function, dict) else {}
                            name = function.get("name") if isinstance(function.get("name"), str) else "unknown"
                            raw_arguments = function.get("arguments")
                            exc = ToolArgumentError(
                                "truncated_arguments",
                                raw_arguments,
                                raw_arguments if isinstance(raw_arguments, str) else None,
                            )
                            tool_start, tool_end, tool_duration = self._times()
                            spans.append(
                                _failure_tool_span(
                                    execution_id,
                                    request_span_id,
                                    hop,
                                    call_index,
                                    name,
                                    tool_start,
                                    tool_end,
                                    tool_duration,
                                    exc,
                                )
                            )
                    self._checkpoint(
                        execution_id,
                        spans,
                        requests_before=requests_before,
                        truncated=True,
                        stop_reason="truncated",
                        failures=failures,
                        partial=True,
                    )
                    break
                if not calls:
                    self._checkpoint(
                        execution_id,
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
                        failures.append({"kind": exc.kind, "tool": name, "preserved": True})
                        start, end, duration = self._times()
                        spans.append(
                            _failure_tool_span(
                                execution_id,
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
                    result = execute_full_study_tool(spec, name, arguments)
                    decision, status_code = route_full_study_tool(spec, name)
                    start, end, duration = self.clock.finish(tool_token)
                    note_id = arguments.get("note_id")
                    tool_authz: dict[str, Any] = {
                        "principal_id": spec["principal"],
                        "roles": spec["roles"],
                    }
                    if isinstance(note_id, str):
                        tool_authz["resource"] = note_id
                    spans.append(
                        _span(
                            f"sp-{execution_id}-tol{hop}-{call_index}",
                            request_span_id,
                            name,
                            "tool",
                            start,
                            end,
                            duration,
                            status="ok" if status_code == 200 else "error",
                            status_code=status_code,
                            tool={
                                "name": name,
                                "type": "read" if name == "get_note" else "action",
                            },
                            content={"tool_args": arguments, "tool_result": result},
                            authz=tool_authz,
                            security={
                                "privilege_class": privilege_for_tool(name),
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
                    execution_id,
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
                execution_id,
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
                execution_id,
                spans,
                requests_before=requests_before,
                truncated=truncated,
                stop_reason="transport_exhausted",
                failures=failures,
                partial=True,
            )
        except MalformedCompletionError as exc:
            failures.append({"kind": "malformed_response", "detail": exc.detail})
            return self._checkpoint(
                execution_id,
                spans,
                requests_before=requests_before,
                truncated=truncated,
                stop_reason="malformed_response",
                failures=failures,
                partial=True,
            )
        except LiveCaptureNotAuthorized:
            raise
        except Exception as exc:
            failures.append({"kind": "capture_error", "error_type": type(exc).__name__})
            return self._checkpoint(
                execution_id,
                spans,
                requests_before=requests_before,
                truncated=truncated,
                stop_reason="capture_error",
                failures=failures,
                partial=True,
            )
        stop_reason = argument_failure or ("truncated" if truncated else None)
        return self._checkpoint(
            execution_id,
            spans,
            requests_before=requests_before,
            truncated=truncated,
            stop_reason=stop_reason,
            failures=failures,
            partial=stop_reason is not None,
        )

    def realize_record(self, spec: dict[str, Any], record: CaptureRecord) -> None:
        if self.output_dir is None or record.stream is None:
            return
        processed = apply_runtime_detectors(record.stream)
        answers = select_full_study_references(processed, spec)
        inventory = inventory_from_realized_stream(spec, processed)
        _write_json(
            self.output_dir / "realized" / "answers" / f"{spec['execution_id']}.json",
            json.loads(answers.model_dump_json()),
            root=self.output_dir,
        )
        _write_json(
            self.output_dir / "realized" / "canaries" / f"{spec['execution_id']}.json",
            json.loads(inventory.model_dump_json()),
            root=self.output_dir,
        )
        _write_json(
            self.output_dir / "realized" / "processed" / f"{spec['execution_id']}.json",
            json.loads(canonical_json_text(processed)),
            root=self.output_dir,
        )
        self._write_artifact_hashes()

    def run(self, output_dir: Path | None = None) -> CaptureRun:
        observed = frozen_source_hashes()
        expected = load_expected_source_hash()
        verify_source_hashes(expected, observed)
        dest = prepare_full_study_capture_dir(output_dir)
        self.output_dir = dest
        repository = collect_provenance()
        _write_json(
            dest / "provenance.json",
            {
                "protocol_version": PROTOCOL_VERSION,
                "checklist_version": CHECKLIST_VERSION,
                "role": "full-study-live-capture",
                "live_full_study_authorized": LIVE_FULL_STUDY_AUTHORIZED,
                "expected_source_hash": expected["combined"],
                "observed_source_hashes": observed,
                "configuration_hashes": capture_configuration_hashes(),
                "capture_input_hashes": capture_input_hashes(),
                "git_commit": repository.get("git_commit"),
                "git_describe": repository.get("git_describe"),
                "git_dirty": repository.get("git_dirty"),
                "git_status": repository.get("git_status"),
                "request_cap": self.budget.request_cap,
                "dollar_ceiling_usd": self.budget.dollar_ceiling_usd,
                "pinned_model": PROPOSED_PINNED_MODEL,
            },
            root=dest,
        )
        self._write_artifact_hashes()
        ordered = capture_once_specs()
        run = CaptureRun(output_dir=dest)
        remaining = list(ordered)
        persist_root = dest / "captures"
        secure_capture_directory(persist_root, root=dest)
        run_failure: dict[str, str] | None = None
        try:
            while remaining:
                spec = remaining[0]
                requests_before_spec = self.budget.requests_used
                try:
                    record = self.capture_spec(spec)
                except Exception as exc:
                    attempted = self.budget.requests_used > requests_before_spec
                    record = CaptureRecord(
                        prompt_id=spec["execution_id"],
                        attempted=attempted,
                        requests_used=self.budget.requests_used - requests_before_spec,
                        failures=[
                            {"kind": "orchestration_error", "error_type": type(exc).__name__}
                        ],
                        stop_reason="orchestration_error",
                        partial=attempted,
                    )
                    persist_record(persist_root, record)
                    run.stop_reason = "orchestration_error"
                    run_failure = record.failures[0]
                    if attempted:
                        run.records.append(record)
                        run.failed_prompt_ids.append(record.prompt_id)
                        remaining.pop(0)
                    run.unattempted_prompt_ids.extend(
                        item["execution_id"] for item in remaining
                    )
                    break
                remaining.pop(0)
                run.requests_used = self.budget.requests_used
                run.estimated_spent_usd = self.budget.spent_usd
                if not record.attempted:
                    run.stop_reason = record.stop_reason
                    run.unattempted_prompt_ids.append(spec["execution_id"])
                    run.unattempted_prompt_ids.extend(item["execution_id"] for item in remaining)
                    break
                run.records.append(record)
                if record.partial or record.failures or record.stop_reason is not None:
                    run.failed_prompt_ids.append(record.prompt_id)
                try:
                    self.realize_record(spec, record)
                except Exception as exc:
                    record.failures.append(
                        {"kind": "realization_error", "error_type": type(exc).__name__}
                    )
                    record.stop_reason = "realization_error"
                    record.partial = True
                    persist_record(persist_root, record)
                    if record.prompt_id not in run.failed_prompt_ids:
                        run.failed_prompt_ids.append(record.prompt_id)
                    run.stop_reason = "realization_error"
                    run.unattempted_prompt_ids.extend(item["execution_id"] for item in remaining)
                    break
                if record.stop_reason in {"request_cap", "dollar_ceiling", "input_bound"}:
                    run.stop_reason = record.stop_reason
                    run.unattempted_prompt_ids.extend(item["execution_id"] for item in remaining)
                    break
        except Exception as exc:
            run.stop_reason = "orchestration_error"
            run_failure = {"kind": "orchestration_error", "error_type": type(exc).__name__}
            run.unattempted_prompt_ids.extend(item["execution_id"] for item in remaining)
        finally:
            run.requests_used = self.budget.requests_used
            run.estimated_spent_usd = self.budget.spent_usd
            if run.failed_prompt_ids and run.stop_reason is None:
                run.stop_reason = "completed_with_failures"
            persist_unattempted(persist_root, run)
            _write_json(
                dest / "run.json",
                {
                    "output_dir": str(dest),
                    "attempted": [record.prompt_id for record in run.records],
                    "failed": run.failed_prompt_ids,
                    "unattempted": run.unattempted_prompt_ids,
                    "requests_used": run.requests_used,
                    "estimated_spent_usd": run.estimated_spent_usd,
                    "stop_reason": run.stop_reason,
                    "failure": run_failure,
                    "expected_source_hash": expected["combined"],
                    "observed_source_hash": observed["combined"],
                },
                root=dest,
            )
            self._write_artifact_hashes()
        return run
