# Full-study local readiness report

Status: **mocked validation passed.** Protocol `full-study-protocol.v1` and checklist `full_study_checklist.v1` are frozen for local review. Live / paid capture is **not** authorized. `LIVE_CAPTURE_AUTHORIZED` and `LIVE_FULL_STUDY_AUTHORIZED` are both false. No model API call was made.

This report does not change `RESEARCH_FEASIBILITY_ASSESSMENT.md` or `private/research-replay/20261005T034345Z`. Those R1–R7 scores stay 11/37, 37/37, 27/37, 11/37.

## What was frozen

Every open choice in `FULL_STUDY_PROPOSAL.md` is recorded in `FULL_STUDY_PROTOCOL.md`, including:

- 24 templates + 24 controls (48 executions); four templates per family
- two scripted pairs and two capture-once pairs per family
- OC1 as a primary fact: first `content.retrieved` → last model `content.output`
- FS16 kept as the tool-argument (or first-output-if-no-tool) co-occurrence fact
- descriptive paired differences as the primary analysis; bootstrap exploratory only
- ties allowed; P3-distinct was a pilot screen only (`EXPERIMENT_CONTRACT.md` §12)
- proposed live bound 80 requests / $15, not enabled

## What was executed

1. Unit tests for extractor isolation, registry counts, OC1 vs FS16, drop/redaction as `missing`, live-client refusal, ambiguous/contradictory tools.
2. Materialize 48 streams, 48 answer manifests, 48 canary inventories.
3. Mocked runner: scripted streams plus scripted-completions capture for the 24 capture-once executions; detectors once; P0–P3; FS/OC1 grading; forecast comparison.

Command: `.venv/bin/python -m genai_observability.full_study.runner`

Run directory: `validation/full-study/runs/20261006T031752Z` (gitignored via `runs/`)

Full pytest: **153 passed**.

| Planned | Realized |
| --- | ---: |
| Templates | 24 |
| Controls | 24 |
| Executions | 48 |
| Policy exports | 192 / 192 |
| Failed attempts | 0 |
| Forecast mismatches | 0 |

## Source hashes

| Tree | SHA-256 combined | Files |
| --- | --- | ---: |
| `src/genai_observability/full_study/*.py` | `e04d286741ed699836055bbd29405fc85fce3bf6080ae74d6ea5d77ab9ec9665` | 15 |
| `fixtures/full-study/streams/` | `2d4b54689fe2b1f43cfec7fa3788b05b335f57d4da5d41188a27652a5edeb6e8` | 48 |
| `references/full-study/answers/` | `e58cd259cef413b86e668166adb2796c9e3ffd213bb5ca296c630c5c31b47b00` | 48 |
| `references/full-study/canaries/` | `82cace56c24a00c31e994170949d26c7735e83f16f5f1faf342e5106dbe470de` | 48 |
| Allowlists + pattern library v1 | `c396134aa1e531d577f98e64f6c7ab87a5ab36a362c9c4b126296328f2348e1f` | unchanged |

Git at the mocked run: `ae4a8e1-dirty` (working tree included this scaffold). Package 0.1.0.

## Predicted retention results (allowlist checks)

These cells are grader/forecast validation on **known** streams. They are not live-model findings.

Coverage = correct applicable FS facts / applicable FS facts. Denominator is **644** per policy (execution-level applicability, identical across P0–P3).

| Policy | Coverage | Exposure (eligible plantings) | Executions with any exposure |
| --- | ---: | ---: | ---: |
| P0 | 268/644 | 0/16 | 0 |
| P1 | 520/644 | 16/16 | 16 |
| P2 | 492/644 | 0/16 | 0 |
| P3 | 460/644 | 0/16 | 0 |

Zero-canary executions: **32** (N/A for exposure means). Eligible plantings: **16**, at least one at each C1–C7 origin. P1 exposed every eligible token. P0/P2/P3 exposed none. Foreign-token leaks: none in this run. Three capture-once tokens that existed only in authored tool arguments or outputs were removed because a live model could not know them before generation.

P0 and P3 do **not** tie on this checklist. P3 adds FS4 (retrieval hash/opaque) and FS8–FS11. Both still miss content facts FS12–FS15, FS16, and OC1. That gap is a predicted retention effect from admitting security-boundary questions that read `security.*` / detector events, recorded in the protocol. It is not a requirement that P3 win.

Category means (descriptive):

| Category | P0 | P1 | P2 | P3 |
| --- | ---: | ---: | ---: | ---: |
| Operational | 0.931 | 1.000 | 1.000 | 1.000 |
| Security | 0.000 | 0.279 | 0.279 | 1.000 |
| Content | 0.000 | 1.000 | 0.848 | 0.000 |

Scripted vs mocked-capture coverage means differ by at most 0.021 across policies. They are reported separately. No winner score.

One forecast rule was recorded during implementation: if the registered FS16/OC1 token is not a canary but the other location still contains a different canary, P2 redacts that location and the outcome is `missing`, not `no`. That matches `fs-f6b-case`.

Exploratory bootstrap (seed 20261005, 10_000 replicates) is labeled exploratory and is not a primary result. Its interval is unavailable because one or more frozen family/source strata contain no eligible exposure execution, so every replicate is omitted under the preregistered rule.

## Outcomes that require a later live capture

Do not read the mocked-capture numbers as these:

- Whether a live model calls a tool or follows a no-tool prompt
- Whether a live model copies a retrieval token into tool arguments (FS16) or into the last output (OC1)
- Live applicability rates
- Unexpected wording, truncation, or budget exhaustion
- Billed cost

The 24 capture-once executions used scripted completions. Their content was authored in the registry.

## Privacy and live-capture posture

- Synthetic streams and in-grammar canaries are committed under `fixtures/full-study/` and `references/full-study/`.
- Run exports and detailed grades are under `validation/full-study/runs/` (gitignored).
- Live captured text, if any later exists, stays under `private/`.
- The full-study runner raises if `GENAI_LIVE_CAPTURE=1` is set. It does not import a live sender.
- Feasibility live command remains opt-in and default-off. It was not run.

## Remaining gate

Implementation review (proposal gate 3) can use this report. Gate 4 is a clean-commit freeze after researcher review. Gate 5 (authorize live capture) is a separate written decision and is not requested here.
