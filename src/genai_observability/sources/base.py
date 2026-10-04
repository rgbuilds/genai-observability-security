from typing import Protocol, runtime_checkable

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import SourceKind


@runtime_checkable
class CanonicalEventSource(Protocol):
    """Load a validated canonical stream. Fixture and captured adapters share this contract."""

    source_kind: SourceKind

    def load(self, scenario_id: str) -> CanonicalEventStream:
        """Return the canonical stream for an opaque scenario identifier."""
        ...
