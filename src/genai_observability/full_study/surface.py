"""Frozen full-study capture surface: tools, notes, retrieval, and router."""

from __future__ import annotations

from typing import Any

from genai_observability.full_study.protocol import SYSTEM_INSTRUCTIONS
from genai_observability.research.protocol import TOOL_SCHEMAS, ToolArgumentError, validate_tool_arguments

FULL_STUDY_TOOL_SCHEMAS = TOOL_SCHEMAS


def note_catalog(spec: dict[str, Any]) -> dict[str, str]:
    """Return only the notes registered for one execution.

    Case and control executions intentionally reuse note ids. A process-wide
    catalog would let whichever spec was visited last replace the body for the
    execution currently being captured.
    """
    notes: dict[str, str] = {}
    retrieval_id = spec.get("retrieval_id")
    retrieval_body = spec.get("retrieval_body")
    if isinstance(retrieval_id, str) and isinstance(retrieval_body, str):
        notes[retrieval_id] = retrieval_body
    result = spec.get("tool_result") or {}
    resource = spec.get("resource")
    body = result.get("body") if isinstance(result, dict) else None
    if isinstance(resource, str) and isinstance(body, str):
        notes[resource] = body
    return notes


def select_spec_retrieval(spec: dict[str, Any]) -> tuple[str, str] | None:
    retrieval_id = spec.get("retrieval_id")
    retrieval_body = spec.get("retrieval_body")
    if isinstance(retrieval_id, str) and isinstance(retrieval_body, str):
        return retrieval_id, retrieval_body
    return None


def route_full_study_tool(spec: dict[str, Any], name: str) -> tuple[str, int]:
    """Frozen grants. Unexpected tools are denied. Privilege is not read from the name at scoring time."""
    if name == "get_note":
        return "allow", 200
    if name == "delete_account":
        roles = spec.get("roles") or []
        if spec.get("allowed") is True and spec.get("tool_name") == "delete_account":
            return "allow", 200
        if "admin" in roles:
            return "allow", 200
        return "deny", 403
    return "deny", 400


def execute_full_study_tool(spec: dict[str, Any], name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    decision, status = route_full_study_tool(spec, name)
    if name == "get_note":
        note_id = arguments.get("note_id")
        body = note_catalog(spec).get(note_id) if isinstance(note_id, str) else None
        return {
            "ok": decision == "allow" and body is not None,
            "body": body,
            "status_code": status,
        }
    if name == "delete_account":
        return {"ok": decision == "allow", "status_code": status}
    return {"ok": False, "error": "unknown_tool", "status_code": status}


def privilege_for_tool(name: str) -> str:
    return "privileged" if name == "delete_account" else "none"


def system_for_spec(spec: dict[str, Any]) -> str:
    return spec.get("system") or SYSTEM_INSTRUCTIONS


__all__ = [
    "FULL_STUDY_TOOL_SCHEMAS",
    "ToolArgumentError",
    "execute_full_study_tool",
    "note_catalog",
    "privilege_for_tool",
    "route_full_study_tool",
    "select_spec_retrieval",
    "system_for_spec",
    "validate_tool_arguments",
]
