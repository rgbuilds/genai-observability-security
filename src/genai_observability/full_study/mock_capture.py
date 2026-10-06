"""Mocked full-study capture. Refuses live clients. No HTTP."""

from __future__ import annotations

import copy
import json
from typing import Any

from genai_observability.full_study.fixtures import build_stream
from genai_observability.full_study.protocol import LIVE_FULL_STUDY_AUTHORIZED
from genai_observability.research.capture import LiveCaptureNotAuthorized, LiveOpenAIClient, ScriptedCompletionsClient
from genai_observability.schemas.canonical import CanonicalEventStream


class MockCaptureResponseError(ValueError):
    """A scripted completion was not a usable chat-completions response."""


def _message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise MockCaptureResponseError("mock response must contain exactly one choice")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise MockCaptureResponseError("mock response choice must contain a message object")
    return message


def _tool_call(message: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    calls = message.get("tool_calls")
    if calls is None:
        return None
    if not isinstance(calls, list) or len(calls) != 1:
        raise MockCaptureResponseError("mock response must contain exactly one tool call")
    function = calls[0].get("function") if isinstance(calls[0], dict) else None
    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
        raise MockCaptureResponseError("mock tool call must contain a function name")
    raw_arguments = function.get("arguments")
    if not isinstance(raw_arguments, str):
        raise MockCaptureResponseError("mock tool arguments must be a JSON string")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise MockCaptureResponseError("mock tool arguments are not valid JSON") from exc
    if not isinstance(arguments, dict):
        raise MockCaptureResponseError("mock tool arguments must decode to an object")
    return function["name"], arguments


def _assistant_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, str):
        raise MockCaptureResponseError("final mock response must contain assistant text")
    return content


def _apply_realized_tool(spec: dict[str, Any], name: str, arguments: dict[str, Any]) -> None:
    if name not in {"get_note", "delete_account"}:
        raise MockCaptureResponseError(f"unsupported mock tool {name!r}")
    note_id = arguments.get("note_id")
    if not isinstance(note_id, str) or not note_id:
        raise MockCaptureResponseError("mock tool arguments require a nonempty note_id")
    spec["tool_name"] = name
    spec["tool_args"] = arguments
    spec["resource"] = note_id
    if name == "get_note":
        spec["allowed"] = True
        spec["privilege"] = "none"
        spec["denial_reason"] = "none"
        body = spec.get("retrieval_body") or f"Title of {note_id}"
        spec["tool_result"] = {"ok": True, "body": body, "status_code": 200}
        return
    allowed = "admin" in spec.get("roles", [])
    spec["allowed"] = allowed
    spec["privilege"] = "privileged"
    spec["denial_reason"] = "none" if allowed else "authorization"
    spec["tool_result"] = {"ok": allowed, "status_code": 200 if allowed else 403}


def scripted_responses_for(spec: dict[str, Any]) -> list[dict[str, Any]]:
    if spec.get("tool_name"):
        return [
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": f"call-{spec['execution_id']}",
                                    "type": "function",
                                    "function": {
                                        "name": spec["tool_name"],
                                        "arguments": __import__("json").dumps(spec["tool_args"]),
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": spec["output"]},
                    }
                ]
            },
        ]
    return [
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": spec["output"]},
                }
            ]
        }
    ]


def capture_mocked(spec: dict[str, Any], client: ScriptedCompletionsClient) -> CanonicalEventStream:
    """Build the canonical stream from the responses actually returned by the mock client."""
    if LIVE_FULL_STUDY_AUTHORIZED:
        raise LiveCaptureNotAuthorized("full-study live capture is not authorized")
    if isinstance(client, LiveOpenAIClient):
        raise LiveCaptureNotAuthorized("full-study mock capture refuses LiveOpenAIClient")
    request = {"model": "mock", "messages": [{"role": "user", "content": spec["user"]}]}
    first = _message(client.complete(request))
    call = _tool_call(first)
    realized = copy.deepcopy(spec)
    if call is None:
        realized["tool_name"] = None
        realized["tool_args"] = None
        realized["tool_result"] = None
        realized["allowed"] = None
        realized["privilege"] = None
        realized["denial_reason"] = None
        realized["output"] = _assistant_text(first)
        return build_stream(realized)

    _apply_realized_tool(realized, *call)
    second = _message(client.complete(request))
    if _tool_call(second) is not None:
        raise MockCaptureResponseError("final mock response must not request another tool")
    realized["output"] = _assistant_text(second)
    return build_stream(realized)


def capture_all_mocked(specs: list[dict[str, Any]]) -> dict[str, CanonicalEventStream]:
    streams: dict[str, CanonicalEventStream] = {}
    for spec in specs:
        if spec["source"] != "mocked-capture":
            continue
        client = ScriptedCompletionsClient(scripted_responses_for(spec))
        streams[spec["execution_id"]] = capture_mocked(spec, client)
        if client._responses:
            raise RuntimeError(f"unused scripted responses for {spec['execution_id']}")
    return streams
