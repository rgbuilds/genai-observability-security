"""Span clocks. Tests inject a deterministic clock. Actual capture uses UTC plus monotonic duration."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

UTC = timezone.utc


def format_utc(value: datetime) -> str:
    moment = value.astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Clock(Protocol):
    def start(self) -> object:
        """Mark the beginning of a span."""

    def finish(self, token: object) -> tuple[str, str, int]:
        """Return start RFC3339, end RFC3339, and elapsed milliseconds."""


class DeterministicClock:
    """Fixed timestamps and durations. Ignores wall and monotonic time."""

    def __init__(self, *, duration_ms: int = 15) -> None:
        self._index = 0
        self._duration_ms = duration_ms

    def start(self) -> int:
        token = self._index
        self._index += 1
        return token

    def finish(self, token: object) -> tuple[str, str, int]:
        if not isinstance(token, int):
            raise TypeError("deterministic clock token must be an int")
        start = datetime(2026, 10, 4, 23, 0, tzinfo=UTC) + timedelta(seconds=token)
        end = start + timedelta(milliseconds=self._duration_ms)
        return format_utc(start), format_utc(end), self._duration_ms


class SystemClock:
    """Real UTC timestamps. Duration is monotonic elapsed time, not wall-clock delta."""

    def __init__(
        self,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic

    def start(self) -> tuple[str, float]:
        return format_utc(self._now()), self._monotonic()

    def finish(self, token: object) -> tuple[str, str, int]:
        if not isinstance(token, tuple) or len(token) != 2:
            raise TypeError("system clock token must be (start, monotonic)")
        start, mono_start = token
        if not isinstance(start, str) or not isinstance(mono_start, (int, float)):
            raise TypeError("system clock token must be (start, monotonic)")
        end = format_utc(self._now())
        duration_ms = round((self._monotonic() - float(mono_start)) * 1000)
        if duration_ms < 0:
            duration_ms = 0
        return start, end, duration_ms
