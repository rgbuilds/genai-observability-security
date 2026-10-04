"""Exposure grader: scan an export artifact against a canary inventory."""

from dataclasses import dataclass

from genai_observability.grading.references import CanaryInventory
from genai_observability.schemas.export import TelemetryExport
from genai_observability.serialization import canonical_json_text


@dataclass(frozen=True)
class ExposureResult:
    execution_id: str
    eligible_count: int
    exposed_ids: tuple[str, ...]
    applicable: bool
    exposed_count: int | None
    leaked_foreign_tokens: tuple[str, ...] = ()

    @property
    def rate_label(self) -> str:
        if not self.applicable:
            return "N/A"
        return f"{self.exposed_count}/{self.eligible_count}"


def export_scan_text(export: TelemetryExport) -> str:
    return canonical_json_text(export)


def tokens_found_in_text(text: str, tokens: list[str]) -> tuple[str, ...]:
    return tuple(token for token in tokens if token in text)


def grade_exposure(
    export: TelemetryExport,
    inventory: CanaryInventory,
    *,
    foreign_tokens: list[str] | None = None,
) -> ExposureResult:
    """Exact substring scan of the export artifact only.

    Zero eligible canaries are N/A, not 0/0. Foreign tokens are a leakage
    check and do not enter the exposure rate.
    """
    text = export_scan_text(export)
    eligible = [canary for canary in inventory.eligible_canaries if canary.eligible]
    exposed_ids = tuple(
        canary.canary_id for canary in eligible if canary.token in text
    )
    leaked = tokens_found_in_text(text, foreign_tokens or [])
    if not eligible:
        return ExposureResult(
            execution_id=inventory.execution_id,
            eligible_count=0,
            exposed_ids=(),
            applicable=False,
            exposed_count=None,
            leaked_foreign_tokens=leaked,
        )
    return ExposureResult(
        execution_id=inventory.execution_id,
        eligible_count=len(eligible),
        exposed_ids=exposed_ids,
        applicable=True,
        exposed_count=len(exposed_ids),
        leaked_foreign_tokens=leaked,
    )
