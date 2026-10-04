from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import SourceKind


class CapturedTraceSource:
    """Reserved adapter for later captured traces.

    The capture method, versioning, and role of realistic LLM/tool traces remain
    unresolved until the full-study freeze. This class exists so later capture
    can implement `CanonicalEventSource` without changing policy or grader
    contracts. It does not capture, store, or replay model traffic.
    """

    source_kind = SourceKind.CAPTURED

    def load(self, scenario_id: str) -> CanonicalEventStream:
        raise NotImplementedError(
            "Captured traces are not implemented. Realistic-trace inclusion "
            "is unresolved until the full-study freeze "
            "(EXPERIMENT_CONTRACT.md section 11). "
            f"Requested scenario_id={scenario_id!r}."
        )
