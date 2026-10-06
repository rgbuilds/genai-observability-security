"""Descriptive aggregation. Exploratory bootstrap is labeled and not primary."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from genai_observability.full_study.protocol import BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED
from genai_observability.full_study.questions import QUESTION_CATEGORY
from genai_observability.schemas.enums import PolicyId


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_policy: dict[str, list[float]] = defaultdict(list)
    by_source: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_family: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_category: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    exposure: dict[str, list[float]] = defaultdict(list)
    zero_canary = 0
    any_exposed = {policy.value: 0 for policy in PolicyId}
    location_exposed: dict[str, dict[str, int]] = {
        policy.value: defaultdict(int) for policy in PolicyId
    }
    for row in records:
        policy = row["policy_id"]
        coverage = row["forensic_coverage"]
        if coverage is not None:
            by_policy[policy].append(coverage)
            by_source[row["source"]][policy].append(coverage)
            by_family[row["family"]][policy].append(coverage)
            for question in row["questions"]:
                if not question["applicable"]:
                    continue
                category = QUESTION_CATEGORY[question["id"]]
                by_category[category][policy].append(float(question["credit"] or 0))
        if row["exposure_applicable"]:
            rate = row["exposed_canaries"] / row["eligible_canaries"]
            exposure[policy].append(rate)
            if row["exposed_canaries"]:
                any_exposed[policy] += 1
            for location in row.get("exposed_locations") or []:
                location_exposed[policy][location] += 1
        else:
            if policy == "P0":
                zero_canary += 1
    return {
        "coverage_by_policy": {key: _mean(values) for key, values in by_policy.items()},
        "coverage_by_source": {
            source: {policy: _mean(values) for policy, values in policies.items()}
            for source, policies in by_source.items()
        },
        "coverage_by_family": {
            family: {policy: _mean(values) for policy, values in policies.items()}
            for family, policies in by_family.items()
        },
        "coverage_by_category": {
            category: {policy: _mean(values) for policy, values in policies.items()}
            for category, policies in by_category.items()
        },
        "exposure_by_policy": {key: _mean(values) for key, values in exposure.items()},
        "executions_with_any_exposure": any_exposed,
        "exposure_by_location": {policy: dict(counts) for policy, counts in location_exposed.items()},
        "zero_canary_executions": zero_canary,
        "mixed_descriptive": {
            "label": "unweighted subset means; not a winner score",
            "scripted": {k: _mean(v) for k, v in by_source.get("scripted", {}).items()},
            "mocked-capture": {k: _mean(v) for k, v in by_source.get("mocked-capture", {}).items()},
        },
    }


def paired_differences(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in records:
        grouped[(row["execution_id"], row["source"])][row["policy_id"]] = row
    diffs = []
    for (execution_id, source), policies in grouped.items():
        if set(policies) != {"P0", "P1", "P2", "P3"}:
            continue
        coverage = {policy: policies[policy]["forensic_coverage"] for policy in policies}
        diffs.append(
            {
                "execution_id": execution_id,
                "source": source,
                "coverage": coverage,
                "p3_minus_p0": (coverage["P3"] or 0) - (coverage["P0"] or 0),
                "p1_minus_p0": (coverage["P1"] or 0) - (coverage["P0"] or 0),
            }
        )
    return diffs


def exploratory_bootstrap(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Labeled exploratory only. Omit a replicate if any stratum lacks exposure."""
    pairs: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_exec: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_exec[row["execution_id"]].append(row)
    seen_pairs: set[tuple[str, str, str]] = set()
    for row in records:
        key = (row["family"], row["source"], row["pair_id"])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        pairs[(row["family"], row["source"])].append(row["pair_id"])
    rng = random.Random(BOOTSTRAP_SEED)
    kept = 0
    omitted = 0
    p3_minus_p0: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        chosen_pairs: list[tuple[str, str, str]] = []
        exposure_ok = True
        for family in ("F1", "F2", "F3", "F4", "F5", "F6"):
            for source in ("scripted", "mocked-capture"):
                available = pairs.get((family, source), [])
                if len(available) < 2:
                    exposure_ok = False
                    break
                chosen_pairs.extend(
                    (family, source, pair_id) for pair_id in rng.choices(available, k=2)
                )
            if not exposure_ok:
                break
        if not exposure_ok:
            omitted += 1
            continue
        sampled_rows: list[dict[str, Any]] = []
        for family, source, pair_id in chosen_pairs:
            matching_execs = [
                execution_id
                for execution_id, rows in by_exec.items()
                if rows[0]["family"] == family
                and rows[0]["source"] == source
                and rows[0]["pair_id"] == pair_id
            ]
            for execution_id in matching_execs:
                sampled_rows.extend(by_exec[execution_id])
        for family in ("F1", "F2", "F3", "F4", "F5", "F6"):
            for source in ("scripted", "mocked-capture"):
                stratum = [
                    row
                    for row in sampled_rows
                    if row["family"] == family and row["source"] == source
                ]
                if not any(row["exposure_applicable"] for row in stratum):
                    exposure_ok = False
                    break
            if not exposure_ok:
                break
        if not exposure_ok:
            omitted += 1
            continue
        coverages = [row for row in sampled_rows if row["forensic_coverage"] is not None]
        p0 = _mean([row["forensic_coverage"] for row in coverages if row["policy_id"] == "P0"])
        p3 = _mean([row["forensic_coverage"] for row in coverages if row["policy_id"] == "P3"])
        if p0 is None or p3 is None:
            omitted += 1
            continue
        kept += 1
        p3_minus_p0.append(p3 - p0)
    if omitted > BOOTSTRAP_REPLICATES / 2 or not p3_minus_p0:
        return {
            "role": "exploratory",
            "interval": "unavailable",
            "replicates_kept": kept,
            "replicates_omitted": omitted,
            "seed": BOOTSTRAP_SEED,
        }
    ordered = sorted(p3_minus_p0)
    lo = ordered[int(0.025 * (len(ordered) - 1))]
    hi = ordered[int(0.975 * (len(ordered) - 1))]
    return {
        "role": "exploratory",
        "metric": "mean_coverage_P3_minus_P0",
        "replicates_kept": kept,
        "replicates_omitted": omitted,
        "seed": BOOTSTRAP_SEED,
        "interval_025_975": [lo, hi],
        "mean": _mean(p3_minus_p0),
    }
