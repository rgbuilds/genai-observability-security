from genai_observability.full_study import aggregate


def _records(*, empty_exposure_stratum: tuple[str, str] | None = None):
    rows = []
    for family_index, family in enumerate(("F1", "F2", "F3", "F4", "F5", "F6")):
        for source in ("scripted", "mocked-capture"):
            for pair_index in range(2):
                pair_id = f"{family}-{source}-{pair_index}"
                for role in ("case", "control"):
                    execution_id = f"{pair_id}-{role}"
                    for policy in ("P0", "P1", "P2", "P3"):
                        rows.append(
                            {
                                "execution_id": execution_id,
                                "pair_id": pair_id,
                                "family": family,
                                "source": source,
                                "policy_id": policy,
                                "forensic_coverage": (
                                    1.0
                                    if policy == "P3"
                                    and family_index == 0
                                    and source == "scripted"
                                    and pair_index == 0
                                    else 0.0
                                ),
                                "exposure_applicable": (family, source)
                                != empty_exposure_stratum,
                            }
                        )
    return rows


def test_bootstrap_omits_draw_when_one_stratum_has_no_exposure(monkeypatch) -> None:
    monkeypatch.setattr(aggregate, "BOOTSTRAP_REPLICATES", 4)
    result = aggregate.exploratory_bootstrap(
        _records(empty_exposure_stratum=("F6", "mocked-capture"))
    )
    assert result["interval"] == "unavailable"
    assert result["replicates_kept"] == 0
    assert result["replicates_omitted"] == 4


def test_bootstrap_preserves_replacement_multiplicity(monkeypatch) -> None:
    class FixedRandom:
        calls = 0

        def __init__(self, seed: int) -> None:
            assert seed == aggregate.BOOTSTRAP_SEED

        def choices(self, available, k):
            assert k == 2
            self.calls += 1
            if self.calls == 1:
                return [available[0], available[0]]
            return [available[0], available[1]]

    monkeypatch.setattr(aggregate, "BOOTSTRAP_REPLICATES", 1)
    monkeypatch.setattr(aggregate.random, "Random", FixedRandom)
    result = aggregate.exploratory_bootstrap(_records())
    assert result["replicates_kept"] == 1
    assert result["mean"] == 1 / 12
