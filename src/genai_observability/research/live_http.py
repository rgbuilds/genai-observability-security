"""HTTP transport for an opted-in Chat Completions call. Mock runs do not import this."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from genai_observability.research.capture import TransportError

API_URL = "https://api.openai.com/v1/chat/completions"


def post_chat_completions(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429 or exc.code >= 500:
            raise TransportError(f"OpenAI HTTP {exc.code}") from exc
        raise RuntimeError(f"OpenAI HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise TransportError(str(exc.reason)) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI response was not a JSON object")
    return parsed
