"""Conservative pre-request cost and token checks. No network I/O."""

import json
import math
from dataclasses import dataclass, field
from typing import Any

from genai_observability.research.protocol import (
    COST_PAD,
    DOLLAR_CEILING_USD,
    INPUT_PAD_TOKENS,
    INPUT_TOKEN_BOUND,
    INPUT_USD_PER_MILLION,
    MAX_OUTPUT_TOKENS,
    OUTPUT_USD_PER_MILLION,
    REQUEST_CAP,
)


class BudgetRejected(ValueError):
    """The request was not sent because a bound would be exceeded."""


def estimated_input_tokens(request: dict[str, Any]) -> int:
    payload = json.dumps(
        {
            "messages": request.get("messages", []),
            "tools": request.get("tools", []),
            "system": request.get("system"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return math.ceil(len(payload.encode("utf-8")) / 3) + INPUT_PAD_TOKENS


def conservative_request_usd(input_tokens: int) -> float:
    raw = (
        input_tokens / 1_000_000 * INPUT_USD_PER_MILLION
        + MAX_OUTPUT_TOKENS / 1_000_000 * OUTPUT_USD_PER_MILLION
    )
    return raw * COST_PAD


@dataclass
class CaptureBudget:
    requests_used: int = 0
    spent_usd: float = 0.0
    rejections: list[str] = field(default_factory=list)
    request_cap: int = REQUEST_CAP
    dollar_ceiling_usd: float = DOLLAR_CEILING_USD
    input_token_bound: int = INPUT_TOKEN_BOUND

    def check(self, request: dict[str, Any]) -> float:
        """Return conservative USD for this request, or raise BudgetRejected."""
        tokens = estimated_input_tokens(request)
        if tokens > self.input_token_bound:
            reason = "input_bound"
            self.rejections.append(reason)
            raise BudgetRejected(reason)
        if self.requests_used + 1 > self.request_cap:
            reason = "request_cap"
            self.rejections.append(reason)
            raise BudgetRejected(reason)
        cost = conservative_request_usd(tokens)
        if self.spent_usd + cost > self.dollar_ceiling_usd:
            reason = "dollar_ceiling"
            self.rejections.append(reason)
            raise BudgetRejected(reason)
        return cost

    def consume(self, request: dict[str, Any]) -> float:
        cost = self.check(request)
        self.requests_used += 1
        self.spent_usd += cost
        return cost
