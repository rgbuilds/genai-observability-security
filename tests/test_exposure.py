from genai_observability.grading.exposure import grade_exposure
from genai_observability.grading.references import load_canary_inventory
from genai_observability.schemas.enums import PolicyId
from tests.helpers import export_from_spans, minimal_span

FOREIGN = "SYNTH-USERIN-A11F0001"


def test_zero_eligible_canaries_are_not_applicable() -> None:
    inventory = load_canary_inventory("exec-41")
    export = export_from_spans(minimal_span(content={"user": "no planted token"}))
    result = grade_exposure(export, inventory, foreign_tokens=[FOREIGN])
    assert result.applicable is False
    assert result.exposed_count is None
    assert result.eligible_count == 0
    assert result.rate_label == "N/A"
    assert result.leaked_foreign_tokens == ()


def test_zero_canary_export_still_reports_foreign_token_leakage() -> None:
    inventory = load_canary_inventory("exec-41")
    export = export_from_spans(minimal_span(content={"user": f"leaked {FOREIGN}"}))
    result = grade_exposure(export, inventory, foreign_tokens=[FOREIGN])
    assert result.applicable is False
    assert result.exposed_count is None
    assert result.leaked_foreign_tokens == (FOREIGN,)


def test_eligible_exposure_counts_distinct_tokens_in_export_text_only() -> None:
    inventory = load_canary_inventory("exec-11")
    exposed = export_from_spans(
        minimal_span(content={"user": "Read note SYNTH-USERIN-A11F0001 and summarize it."})
    )
    redacted = export_from_spans(
        minimal_span(content={"user": "Read note [REDACTED:canary_grammar] and summarize it."}),
        policy_id=PolicyId.P2,
    )
    found = grade_exposure(exposed, inventory)
    missed = grade_exposure(redacted, inventory)
    assert found.applicable is True
    assert found.rate_label == "1/1"
    assert found.exposed_ids == ("C1",)
    assert missed.applicable is True
    assert missed.rate_label == "0/1"
    assert missed.exposed_ids == ()


def test_exposure_does_not_treat_inventory_membership_as_evidence() -> None:
    inventory = load_canary_inventory("exec-11")
    export = export_from_spans(minimal_span(content={"user": "no token in the artifact"}))
    result = grade_exposure(export, inventory)
    assert result.exposed_count == 0
    assert "SYNTH-USERIN-A11F0001" == inventory.eligible_canaries[0].token
