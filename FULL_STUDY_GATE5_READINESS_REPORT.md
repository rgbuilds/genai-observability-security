# Full-study Gate 5 readiness report

Status: **Gate 5 command prepared. Paid send is not authorized.** Protocol `full-study-protocol.v1` is unchanged in its scientific freeze (P0–P3, library v1, Q1–Q15, R1–R7, FS1–FS16, OC1, 48 executions). Amendment §13 records the live command, budget, and realized-derivation rule. Official OpenAI docs were rechecked on **2026-10-09**; every frozen model and price fact still matches, so `live_recheck_required` is now false. The snapshot and standard rates were not changed. `LIVE_FULL_STUDY_AUTHORIZED` is false. No model API call was made.

This report does not change `RESEARCH_FEASIBILITY_ASSESSMENT.md`, `private/research-replay/20261005T034345Z`, or the mocked-run scores in `FULL_STUDY_READINESS_REPORT.md`.

## What Gate 5 prepared

- Command: `python -m genai_observability.full_study.live_capture`
- Default: refuse. Explicit process flag: `GENAI_FULL_STUDY_LIVE=1`. Feasibility `GENAI_LIVE_CAPTURE=1` does not enable this command. The mocked runner refuses both flags.
- Order: the 24 `source=="mocked-capture"` executions in registry order:

  `fs-f1c-case`, `fs-f1c-ctrl`, `fs-f1d-case`, `fs-f1d-ctrl`, `fs-f2c-case`, `fs-f2c-ctrl`, `fs-f2d-case`, `fs-f2d-ctrl`, `fs-f3c-case`, `fs-f3c-ctrl`, `fs-f3d-case`, `fs-f3d-ctrl`, `fs-f4c-case`, `fs-f4c-ctrl`, `fs-f4d-case`, `fs-f4d-ctrl`, `fs-f5c-case`, `fs-f5c-ctrl`, `fs-f5d-case`, `fs-f5d-ctrl`, `fs-f6c-case`, `fs-f6c-ctrl`, `fs-f6d-case`, `fs-f6d-ctrl`

- Frozen surface: registered prompts, `SYSTEM_INSTRUCTIONS`, tools `get_note` / `delete_account`, full-study router grants, snapshot `gpt-4o-mini-2024-07-18`, temperature 0, `max_tokens=512`.
- Scripted 24 executions remain `build_stream` fixtures. They are not submitted.

## Review fixes (this revision)

1. **Mandatory official recheck.** `full_study.live_capture` refuses before constructing or invoking `LiveOpenAIClient` when `OFFICIAL_DOC_CHECK["live_recheck_required"]` is true. It also refuses a missing/invalid `checked_on`, a snapshot mismatch, an input or output price mismatch, `function_calling` that is not true, `max_output_tokens` below 512, a future date, or a completed check more than one UTC calendar day old. Tests still prove that a pending-recheck record plus `GENAI_FULL_STUDY_LIVE=1` and an API key makes zero client constructions and zero `complete()` / `run()` calls. The recorded 2026-10-09 check is completed (`live_recheck_required=false`) because the official pages still match.

2. **Independent source freeze and provenance.** Capture hashes are compared to `references/full-study/live_source_freeze.json`, which is outside the hashed set. The frozen set includes every `.py` file under `src/genai_observability/`, all four allowlists, and pattern library v1. A missing expected hash, a changed expected combined hash, or a changed frozen file refuses before any request and before a destination directory is created. Provenance records protocol and checklist versions, expected and observed freeze hashes, separate configuration and capture-input hashes, Git commit/description/status/dirty state, model, and budget.

3. **Malformed responses.** After a successful transport, the adapter requires exactly one usable choice, a recognized and consistent finish reason, and a valid assistant message with text or tool calls. No choices, multiple choices, a missing or non-object message, neither text nor tool calls, filtered or unknown finish reasons, and inconsistent `stop` / `tool_calls` combinations become a partial failed capture with `stop_reason=malformed_response`. No model span is written for that hop. A `length` response is partial; any tool-call arguments are retained as failure evidence and never executed. Failure details are structural labels only.

4. **Failure durability and execution isolation.** Each case or control resolves notes only from its own registered retrieval and tool-result data, so reused note ids cannot cross-contaminate paired executions. Non-retryable client errors are persisted without response text. Realization and orchestration failures stop the run, preserve structural failure metadata, list remaining prompts as unattempted, and still write final run metadata.

5. **Actual send boundary and aggregate status.** The adapter checks the live flag, authorized client, official-check freshness and facts, source/configuration freeze, private persisted provenance, Git commit, and clean working tree immediately before every `complete()` call. Calling `capture_spec()` directly cannot send around the CLI. `run.json` lists failed execution ids, `completed_with_failures` marks a run that reaches the end with failures, and the CLI exits nonzero for failures, unattempted prompts, or any run stop reason.

6. **Frozen budget, served-model identity, and artifact hashes.** Immediately before every live request, the adapter requires the exact `CaptureBudget` type, the 80-request / USD 15 / 4096-token limits, and nonnegative in-bounds counters. A live response must report `gpt-4o-mini-2024-07-18`; missing or different model identity becomes a partial malformed-response failure before a model span is written. `artifact_hashes.json` records SHA-256 for every other persisted JSON file, including raw capture streams and sidecars, processed streams, answers, canary inventories, provenance, unattempted ids, and `run.json`.

7. **Owner-only private artifacts.** Capture directories are created as `0700`, and every JSON stream, sidecar, manifest, provenance file, and run record is created as `0600`. The secure writer is shared by feasibility and full-study capture persistence and does not create a readable file before tightening permissions.

## Budget and persistence

| Bound | Value |
| --- | --- |
| HTTP request cap | 80 |
| Conservative dollar ceiling | USD 15.00 |
| Estimated input token bound | 4096 |
| Cost check | pre-request; refuse before send if the next conservative cost would exceed the remaining ceiling |
| Transport retries | two attempts per hop; each attempt counts as a request |
| Feasibility defaults | unchanged: 12 requests / $5.00 |

Every attempted, partial, failed, and unattempted capture is written under a unique gitignored `private/full-study-captures/<stamp>/` (`captures/`, `realized/`, `unattempted_prompts.json`, `provenance.json`, `run.json`). A nonempty destination is refused. No live directory was created in this gate.

## Realized derivation

After a usable stream exists, detectors run once. Answer manifests, applicability, and canary eligibility come from that realized stream. A planted token is eligible only when it is present in its registered origin field. Expected completions are not plants. Output-only tokens are not invented.

## Official model-page record (2026-10-09 HTTP recheck)

Rechecked official OpenAI sources only. No Chat Completions or other model API call was made.

| Recorded fact | Official evidence | Match |
| --- | --- | --- |
| Snapshot `gpt-4o-mini-2024-07-18` listed and default | [GPT-4o Mini](https://developers.openai.com/api/docs/models/gpt-4o-mini) (also [platform](https://platform.openai.com/docs/models/gpt-4o-mini)) | yes |
| Chat Completions | `v1/chat/completions` Supported | yes |
| Function calling | listed under Supported features | yes |
| Context window | 128,000 | yes |
| Max output tokens | 16,384 (`max_tokens=512` supported) | yes |
| Standard input | $0.15 / 1M | yes |
| Standard cached input | $0.075 / 1M | yes |
| Standard output | $0.6 / 1M (= $0.60) | yes |

Pricing confirmation: [Pricing](https://developers.openai.com/api/docs/pricing) Standard table lists `gpt-4o-mini` at $0.15 / $0.075 / $0.60. Function-calling guide: `https://developers.openai.com/api/docs/guides/function-calling`. Fine-tuning and Batch tables were not used as standard inference prices. Floating alias `gpt-4o-mini` remains forbidden for sends.

`checked_on=2026-10-09`, `live_recheck_required=false`. A completed check is valid for at most one UTC calendar day. If a later official page differs, stop; record a further amendment; do not change the pin in place and do not send.

## Mocked tests

Command: `.venv/bin/python -m pytest`

Full pytest: **198 passed**. No network. The Gate 5 suite covers:

- default-off CLI and unauthorized `LiveOpenAIClient`
- missing `OPENAI_API_KEY` after opt-in
- pending official recheck (patched record) with env flag and API key: zero client calls
- recorded 2026-10-09 check completed; pin and prices unchanged
- completed official check freshness and future-date rejection
- direct adapter sends blocked at the actual send boundary before budget consumption
- mutated or custom live budgets rejected before client invocation
- API-reported model mismatch rejected before model-span creation
- missing/invalid check date, pin mismatch, price mismatch, function-calling mismatch, insufficient output limit
- recorded pin / prices unchanged
- no-tool realized applicability (FS12/FS5 N/A; OC1 from retrieval + output)
- unexpected tool preserved (`search_web`, not substituted)
- malformed arguments preserved (no `{}` substitute)
- multiple tool calls in one message
- truncation without a prose follow-up; no invented output canary
- truncated tool calls retained as failure evidence and never executed
- filtered, unknown, missing, and inconsistent finish reasons rejected before tool execution
- two transport retries counted, then partial keep
- non-retryable client errors persisted without response text
- request-cap exhaustion lists remaining ids as unattempted
- dollar-ceiling refusal before any send
- case/control note catalogs isolated despite reused note ids
- realization failures preserve the attempted record, remaining prompt list, and final run metadata
- aggregate failed-id tracking, `completed_with_failures`, and nonzero CLI status
- checklist, Git state, configuration hashes, and capture-input hashes in provenance
- SHA-256 manifest coverage for captures, sidecars, realized artifacts, provenance, and run metadata
- owner-only `0700` directories and `0600` artifact files
- complete-package freeze coverage, including detector scanning, grading references, and transitive schemas
- persistence of streams, answer manifests, and realized canaries
- independent expected-hash verify; altered expected hash; simulated changed source hash; missing expected file
- malformed response shapes: no choices, empty choices, multiple choices, missing message, non-object message, neither text nor tool calls
- live adapter does not import `live_http`
- scripted execution ids stay out of the live order
- mocked runner refuses `GENAI_FULL_STUDY_LIVE=1`

## Source hashes

| Tree | SHA-256 combined | Files |
| --- | --- | ---: |
| Complete package source plus policy configuration | `7cfc719220c03674c7cbeb40ddff2ff41c78e3ecd1a92e27ae3f4d09b20bb6b7` | 69 |
| Independent expected hash (`references/full-study/live_source_freeze.json`, not hashed) | `7cfc719220c03674c7cbeb40ddff2ff41c78e3ecd1a92e27ae3f4d09b20bb6b7` | 1 |
| `src/genai_observability/**/*.py` | `c65644e17a7e3e29cee6f1e0dd0f50e92e51addb5bdb017852b19931aa725275` | 64 |
| Capture inputs (protocol, checklist, references, scenarios, tool surface) | `f71890c44896a6a2f93b152f17c8eb98f265eda933e625db60f3c2b59d5d25a4` | 5 |
| `src/genai_observability/full_study/*.py` | `815194bc4548c656e16945ba294dd0a7a5d870aa2deb9c849a2c1cdf77a26047` | 18 |
| Allowlists + pattern library v1 | `c396134aa1e531d577f98e64f6c7ab87a5ab36a362c9c4b126296328f2348e1f` | 5 |

Git HEAD before this official-recheck amendment: `52a2fdd` (the working tree includes the recheck record and regenerated freeze). Package 0.1.0.

## Still required before a paid send

1. Gate 4 clean-commit freeze after researcher review of the exact 24-id list and the 80 / $15.00 ceiling.
2. If this 2026-10-09 official check is more than one UTC calendar day old at send time, recheck official pages again before sending. If anything differs, amend; do not silently retarget.
3. A new unprinted API key. The key exposed during feasibility capture must stay revoked.
4. Written authorization that is not this report and not protocol §13. Then, and only then, `GENAI_FULL_STUDY_LIVE=1`.

Gate 5 is ready as a **command and test surface**. It is not a live execution.
