"""Opt-in full-study live capture. Does nothing unless GENAI_FULL_STUDY_LIVE=1."""

from __future__ import annotations

import os
import sys

from genai_observability.full_study.live_adapter import (
    FullStudyCaptureAdapter,
    validate_official_doc_check,
    verify_source_hashes,
)
from genai_observability.full_study.protocol import (
    LIVE_ENV_FLAG,
    LIVE_FULL_STUDY_AUTHORIZED,
    OFFICIAL_DOC_CHECK,
    PROPOSED_DOLLAR_CEILING_USD,
    PROPOSED_INPUT_TOKEN_BOUND,
    PROPOSED_MAX_OUTPUT_TOKENS,
    PROPOSED_PINNED_MODEL,
    PROPOSED_REQUEST_CAP,
)
from genai_observability.full_study.scenarios import CAPTURE_ONCE_EXECUTION_IDS
from genai_observability.research.capture import LiveCaptureNotAuthorized, LiveOpenAIClient
from genai_observability.research.clock import SystemClock


def refuse_unless_official_docs_ready() -> None:
    """Refuse before a live client exists. Does not fetch official pages."""
    try:
        validate_official_doc_check(OFFICIAL_DOC_CHECK)
    except LiveCaptureNotAuthorized as exc:
        raise SystemExit(f"{exc} No client was constructed and no request was sent.") from exc


def main() -> int:
    if os.environ.get(LIVE_ENV_FLAG) != "1":
        raise SystemExit(
            "Full-study live capture is off. Re-run with GENAI_FULL_STUDY_LIVE=1 after an official "
            "model-page recheck. This process would send up to "
            f"{PROPOSED_REQUEST_CAP} requests for {len(CAPTURE_ONCE_EXECUTION_IDS)} capture-once "
            f"executions, max_tokens={PROPOSED_MAX_OUTPUT_TOKENS}, input bound "
            f"{PROPOSED_INPUT_TOKEN_BOUND}, and stop at ${PROPOSED_DOLLAR_CEILING_USD:.2f}."
        )
    if LIVE_FULL_STUDY_AUTHORIZED:
        raise SystemExit("LIVE_FULL_STUDY_AUTHORIZED must remain false. Use the env flag only.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing. No request was sent.")
    refuse_unless_official_docs_ready()
    try:
        verify_source_hashes()
    except RuntimeError as exc:
        raise SystemExit(f"{exc} No client was constructed.") from exc
    print(
        f"Doc check {OFFICIAL_DOC_CHECK['checked_on']}: {PROPOSED_PINNED_MODEL}, "
        f"input $0.15/1M, output $0.60/1M. Cap {PROPOSED_REQUEST_CAP} requests, "
        f"${PROPOSED_DOLLAR_CEILING_USD:.2f}. HTTP recheck required before a paid send: "
        f"{OFFICIAL_DOC_CHECK['live_recheck_required']}.",
        file=sys.stderr,
    )
    adapter = FullStudyCaptureAdapter(
        LiveOpenAIClient(api_key, authorized=True),
        clock=SystemClock(),
    )
    run = adapter.run()
    print(
        {
            "output_dir": str(run.output_dir),
            "attempted": [record.prompt_id for record in run.records],
            "failed": run.failed_prompt_ids,
            "unattempted": run.unattempted_prompt_ids,
            "requests_used": run.requests_used,
            "estimated_spent_usd": round(run.estimated_spent_usd, 6),
            "stop_reason": run.stop_reason,
        }
    )
    return 1 if run.failed_prompt_ids or run.unattempted_prompt_ids or run.stop_reason else 0


if __name__ == "__main__":
    raise SystemExit(main())
