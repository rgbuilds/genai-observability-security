# Implementation-validation report

Status: **implementation conforms to PILOT_SPEC.md**. This is not a contract section 7 research go/no-go decision. The suite was not expanded. Realistic-model capture was not started.

Run UTC: 2026-10-04T23:23:02Z. Interpreter: `.venv/bin/python` (CPython 3.12.13). Host: Darwin 25.5.0 arm64 (macOS 26.5). Package 0.1.0; pydantic 2.13.5; pytest 8.4.2. Policy allowlists v1; pattern library v1. Git describe at run time: `aaa9285-dirty` (working tree included the uncommitted fixtures, graders, and this validation pass).

## What was executed

1. Full unit suite via `.venv/bin/python -m pytest` — passed.
2. Ten-execution implementation-validation pilot across P0–P3 (40 exports) via `.venv/bin/python -m genai_observability.validation.run_pilot`.

Artifacts (artifact of record is canonical JSON):

| Kind | Path |
| --- | --- |
| 40 exports | `validation/implementation-pilot/exports/{exec}/{P0–P3}.json` |
| Per-question answers, evidence pointers, exposure | `validation/implementation-pilot/results/{exec}/{policy}.json` |
| Configuration / version provenance | `validation/implementation-pilot/provenance.json` |
| Roll-up | `validation/implementation-pilot/summary.json` |

Failed-run directory: none created. The runner writes `validation/implementation-pilot/failures/` only when a load, transform, or grade step raises. No step failed; no records were discarded.

## Scoring choices used

Recorded in PILOT_SPEC.md section 4.2. The ones that affect this run:

- Q15 clause (c) is **same-span**.
- Evidence locations are **JSON pointers** into the **serialized** export (canonical JSON: UTF-8, sorted keys, compact, `ensure_ascii=false`, `exclude_none`).
- Q10 maps the **tool** span `status_code` (or tool `security.authz_decision` on P3), not the request span.
- Q2/Q8/Q9/Q11 read only `security.*`; no content-marker vocabulary was invented.

Every credited pointer in the 40 results has `resolves_in_artifact: true` against the written export file. Pointer-resolution failures: **0**.

## Applicable-fact denominators

Applicability is execution-level and identical across policies. Non-applicable questions are excluded from coverage.

| Execution | Applicable facts | Notes |
| --- | --- | --- |
| `exec-11` | 14 | Q4 N/A |
| `exec-12` | 13 | Q4, Q13 N/A |
| `exec-21` | 15 | |
| `exec-22` | 14 | Q13 N/A |
| `exec-31` | 14 | Q4 N/A |
| `exec-32` | 13 | Q4, Q13 N/A |
| `exec-41` | 13 | Q4, Q13 N/A |
| `exec-42` | 13 | Q4, Q13 N/A |
| `exec-51` | 9 | Q4, Q7–Q11 N/A |
| `exec-52` | 8 | Q4, Q7–Q11, Q13 N/A |

## Forensic coverage (correct / applicable)

| Execution | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| `exec-11` | 7/14 | 10/14 | 10/14 | 14/14 |
| `exec-12` | 8/13 | 9/13 | 9/13 | 13/13 |
| `exec-21` | 7/15 | 11/15 | 11/15 | 15/15 |
| `exec-22` | 8/14 | 10/14 | 10/14 | 14/14 |
| `exec-31` | 8/14 | 10/14 | 10/14 | 14/14 |
| `exec-32` | 8/13 | 9/13 | 9/13 | 13/13 |
| `exec-41` | 7/13 | 8/13 | 8/13 | 13/13 |
| `exec-42` | 8/13 | 9/13 | 9/13 | 13/13 |
| `exec-51` | 5/9 | 8/9 | 8/9 | 9/9 |
| `exec-52` | 6/8 | 7/8 | 7/8 | 8/8 |

P0 misses detectors and `security.*`. P1/P2 recover detectors and metadata but not Q2/Q8/Q9/Q11 (no planted content markers). P3 recovers the structured fields. Q15 on P0 is incorrect for F1/F2/F6 and for F4; F3 is correct via `403`. These cells match the specification forecasts (`yes` / `missing/0` / `incorrect`). Forecast mismatches: **0**.

## Exposure

Zero-canary executions are **N/A**, not `0/0`, and are excluded from means: `exec-12`, `exec-22`, `exec-32`, `exec-41`, `exec-42`, `exec-52`.

Eligible security executions **n = 4**: `exec-11`, `exec-21`, `exec-31`, `exec-51` (denominator 1 each).

| Execution | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| `exec-11` | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-21` | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-31` | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-51` | 0/1 | 1/1 | 0/1 | 0/1 |
| six zero-canary | N/A | N/A | N/A | N/A |

Policy means on those four: P0 **0**, P1 **1**, P2 **0**, P3 **0**. P2 zero exposure is the predicted validation target for in-grammar, payload-scoped canaries. It is not a research claim that redaction works.

Leakage scan of other executions’ tokens: **none** on any of the 40 exports.

## Paired Q15 distinguishability

| Pair | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| A F1 | no | yes | yes | yes |
| B F2 | no | yes | yes | yes |
| C F3 | yes | yes | yes | yes |
| D F4 | no | no | no | yes |
| E F6 | no | yes | yes | yes |

Matches PILOT_SPEC.md section 9. Pair C still confounds authorization with a different tool (`delete_account` vs `get_note`). Pair D is distinguishable only on P3 (same-span privileged+allow).

## Discrepancy investigation

None. Actual cells matched the specification tables, so frozen policies, detectors, and graders were not changed.

## What this does not decide

Reproducing the predicted tables shows the pipeline is faithful to the frozen allowlists and this spec. It does **not** show that P0 and P1 have a meaningful empirical contrast, that P3 occupies a distinct research position, or that family-level guidance is warranted. Those remain contract section 7 questions for a later, separately authorized research-feasibility stage.
