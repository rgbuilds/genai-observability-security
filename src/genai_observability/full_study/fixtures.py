"""Build canonical streams from registered specs. No policy exports."""

from __future__ import annotations

from typing import Any

from genai_observability.full_study.protocol import SYSTEM_INSTRUCTIONS
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.transforms.apply import opaque_identifier


def _stamp(execution_id: str, offset: int) -> tuple[str, str, int]:
    second = offset
    start = f"2026-10-05T12:00:{second:02d}.000Z"
    end = f"2026-10-05T12:00:{second:02d}.015Z"
    return start, end, 15


def _span(
    execution_id: str,
    suffix: str,
    *,
    name: str,
    kind: str,
    parent: str | None,
    offset: int,
    status: str = "ok",
    status_code: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    start, end, duration = _stamp(execution_id, offset)
    payload: dict[str, Any] = {
        "span_id": f"sp-{execution_id}-{suffix}",
        "parent_span_id": parent,
        "name": name,
        "kind": kind,
        "start_time": start,
        "end_time": end,
        "duration_ms": duration,
        "status": status,
    }
    if status_code is not None:
        payload["status_code"] = status_code
    payload.update(fields)
    return payload


def build_stream(spec: dict[str, Any]) -> CanonicalEventStream:
    execution_id = spec["execution_id"]
    req = f"sp-{execution_id}-req"
    system = spec.get("system") or SYSTEM_INSTRUCTIONS
    spans: list[dict[str, Any]] = [
        _span(
            execution_id,
            "req",
            name="handle_request",
            kind="request",
            parent=None,
            offset=0,
            status_code=200,
            content={"system": system, "user": spec["user"]},
            security={"trust_class": "untrusted"},
            authz={
                "principal_id": spec["principal"],
                "roles": spec["roles"],
                "resource": spec.get("resource"),
            },
        )
    ]
    offset = 1
    if spec.get("retrieval_id"):
        spans.append(
            _span(
                execution_id,
                "ret",
                name="retrieve_notes",
                kind="retrieval",
                parent=req,
                offset=offset,
                content={"retrieved": spec["retrieval_body"]},
                retrieval={
                    "source_id": spec["retrieval_id"],
                    "hash": opaque_identifier(spec["retrieval_id"]),
                },
            )
        )
        offset += 1
    tool_name = spec.get("tool_name")
    model_name = (
        "gpt-4o-mini-2024-07-18" if spec["source"] == "mocked-capture" else "fixture-model"
    )
    if tool_name:
        spans.append(
            _span(
                execution_id,
                "mdl1",
                name="chat.completion",
                kind="model",
                parent=req,
                offset=offset,
                model={"provider": "mock", "name": model_name},
                tokens={"input": 20, "output": 8},
            )
        )
        offset += 1
        allowed = spec["allowed"] is True
        spans.append(
            _span(
                execution_id,
                "tol1",
                name=tool_name,
                kind="tool",
                parent=req,
                offset=offset,
                status="ok" if allowed else "error",
                status_code=200 if allowed else 403,
                tool={"name": tool_name, "type": "read" if tool_name == "get_note" else "action"},
                content={
                    "tool_args": spec["tool_args"],
                    "tool_result": spec.get("tool_result") or {"ok": allowed},
                },
                authz={
                    "principal_id": spec["principal"],
                    "roles": spec["roles"],
                    "resource": spec.get("resource"),
                },
                security={
                    "privilege_class": spec["privilege"],
                    "authz_decision": "allow" if allowed else "deny",
                    "denial_reason": spec["denial_reason"],
                },
            )
        )
        offset += 1
        spans.append(
            _span(
                execution_id,
                "mdl2",
                name="chat.completion",
                kind="model",
                parent=req,
                offset=offset,
                model={"provider": "mock", "name": model_name},
                tokens={"input": 24, "output": 12},
                content={"output": spec["output"]},
            )
        )
    else:
        spans.append(
            _span(
                execution_id,
                "mdl1",
                name="chat.completion",
                kind="model",
                parent=req,
                offset=offset,
                model={"provider": "mock", "name": model_name},
                tokens={"input": 16, "output": 6},
                content={"output": spec["output"]},
            )
        )
    return CanonicalEventStream.model_validate(
        {
            "scenario_id": execution_id,
            "request_id": f"req-{execution_id}",
            "trace_id": f"trace-{execution_id}",
            "spans": spans,
        }
    )
