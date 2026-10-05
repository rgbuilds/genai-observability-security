"""Opt-in paid capture. Does nothing unless GENAI_LIVE_CAPTURE=1 and OPENAI_API_KEY are set."""

from __future__ import annotations

import os
import sys

from genai_observability.research.capture import CaptureAdapter, LiveOpenAIClient
from genai_observability.research.clock import SystemClock
from genai_observability.research.protocol import (
    DOLLAR_CEILING_USD,
    INPUT_TOKEN_BOUND,
    INPUT_USD_PER_MILLION,
    MAX_OUTPUT_TOKENS,
    OFFICIAL_DOC_CHECK,
    OUTPUT_USD_PER_MILLION,
    PINNED_MODEL,
    REQUEST_CAP,
)


def _docs_match_protocol() -> None:
    required = {
        "snapshot": PINNED_MODEL,
        "function_calling": True,
        "input_usd_per_million": INPUT_USD_PER_MILLION,
        "output_usd_per_million": OUTPUT_USD_PER_MILLION,
        "max_tokens_512_supported": True,
    }
    for key, expected in required.items():
        if OFFICIAL_DOC_CHECK.get(key) != expected:
            raise SystemExit(f"Official doc record {key}={OFFICIAL_DOC_CHECK.get(key)!r} does not match the protocol.")
    if OFFICIAL_DOC_CHECK.get("max_output_tokens", 0) < MAX_OUTPUT_TOKENS:
        raise SystemExit("Recorded max output is below max_tokens=512.")


def main() -> int:
    if os.environ.get("GENAI_LIVE_CAPTURE") != "1":
        raise SystemExit(
            "Live capture is off. Re-run with GENAI_LIVE_CAPTURE=1 after checking the OpenAI model page. "
            "This process will send up to "
            f"{REQUEST_CAP} requests, max_tokens={MAX_OUTPUT_TOKENS}, input bound {INPUT_TOKEN_BOUND}, "
            f"and stop at ${DOLLAR_CEILING_USD:.2f}."
        )
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing. No request was sent.")
    _docs_match_protocol()
    print(
        f"Doc check {OFFICIAL_DOC_CHECK['checked_on']}: {PINNED_MODEL}, "
        f"input ${INPUT_USD_PER_MILLION}/1M, output ${OUTPUT_USD_PER_MILLION}/1M. "
        f"Cap {REQUEST_CAP} requests, ${DOLLAR_CEILING_USD:.2f}.",
        file=sys.stderr,
    )
    adapter = CaptureAdapter(LiveOpenAIClient(api_key, authorized=True), clock=SystemClock())
    run = adapter.run()
    print(
        {
            "output_dir": str(run.output_dir),
            "prompts": [record.prompt_id for record in run.records],
            "unattempted": run.unattempted_prompt_ids,
            "requests_used": run.requests_used,
            "estimated_spent_usd": round(run.estimated_spent_usd, 6),
            "stop_reason": run.stop_reason,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
