# Local readiness report

Status: **scripted S/T retention validation matched the published forecasts. The mocked capture exercise passed.** A follow-up pass fixed five capture-adapter findings, added regressions, and replayed mocked captures through grading. These results are retention validation and adapter checks only. They are not realistic-capture lessons and not a research go/no-go. Live capture was not enabled. No model API call was made.

Run UTC: 2026-10-04T23:59:06Z. Interpreter: `.venv/bin/python` (CPython 3.12.13). Host: Darwin 25.5.0 arm64 (macOS 26.5). Package 0.1.0; pydantic 2.13.5; pytest 8.4.2.

## Code version

| Item | Value |
| --- | --- |
| `git_commit` | `694dab43b6eb89843b8dfd37518fe22e0ff0de42` |
| `git_describe` | `694dab4-dirty` |
| `git_dirty` | true |
| Source tree SHA-256 (combined) | `6c4be70e511d9bed4959919cc0b8ad0f3d128ea4267a341cc558451bbe434798` |
| Configuration SHA-256 (allowlists + pattern library v1) | `c396134aa1e531d577f98e64f6c7ab87a5ab36a362c9c4b126296328f2348e1f` |
| Research fixture SHA-256 | `0faa35cd81452fa3f292df1284c03fc8e7a17c35a8614ee4bee4b89b583468c6` |
| Research answer SHA-256 | `8a633095864fe9c1fdd0b44cbf02fcde066ce99ae65ad6b0b0895cb618abb1bf` |

The commit is the last committed HEAD. The working tree at provenance collection was dirty. `git status --porcelain` recorded:

- `M .gitignore`
- `M src/genai_observability/paths.py`
- `?? RESEARCH_FEASIBILITY_PLAN.md`
- `?? fixtures/research/`
- `?? references/research/`
- `?? src/genai_observability/research/`
- `?? tests/test_research_capture.py`
- `?? tests/test_research_evaluate.py`
- `?? tests/test_research_extract_isolation.py`
- `?? tests/test_research_forecasts.py`

Per-file hashes, including `run_retention.py` and `exercise_capture.py`, are in the run `provenance.json`. The retention directory itself was created after that snapshot.

## What was executed

1. `.venv/bin/python -m genai_observability.research.run_retention`
2. `.venv/bin/python -m genai_observability.research.exercise_capture`
3. `.venv/bin/python -m pytest` — **122 passed**
4. Independent `git check-ignore -v` on private capture files, and `git status --porcelain --untracked-files=all -- private`

No HTTP client was constructed for a provider. `LIVE_CAPTURE_AUTHORIZED` stayed `false`.

## Earlier runs preserved

`validation/implementation-pilot/` was not rewritten.

| Check | Before | After |
| --- | --- | --- |
| SHA-256 of `validation/implementation-pilot/summary.json` | `7a1077eb0f80748171af920d46a09578167c059cc8c09ebc75a693d4774841cb` | same |
| File count under `validation/implementation-pilot/` | 82 | 82 |

The new run is `validation/research-retention/runs/20261004T235906Z/`. The runner refuses a nonempty destination and allocates a unique directory.

## Retention validation (S/T only)

Label on `summary.json` and every result file: **retention-validation-only**. `research_evidence` is false. `research_go_no_go` is `not_evaluated`. `retention_forecasts_matched` is true.

Pipeline for `res-s1`, `res-s2`, `res-t1`, `res-t2`: fixture load with `detector_pass` forced to `not_run`, `apply_runtime_detectors`, then P0–P3 `apply_policy`, then R extract-then-evaluate. Each result file was written with `fixture_hash`, `processed_hash`, `configuration_hash`, `research_fixture_hash`, and `research_answer_hash` already filled in.

| Artifact | Count | Path |
| --- | --- | --- |
| Exports | 16 | `validation/research-retention/runs/20261004T235906Z/exports/{res-s1,res-s2,res-t1,res-t2}/{P0–P3}.json` |
| Extractions (values + pointers) | 16 | `.../extractions/{execution}/{policy}.json` |
| Results | 16 | `.../results/{execution}/{policy}.json` |
| Provenance | 1 | `.../provenance.json` |
| Roll-up | 1 | `.../summary.json` |

Failed-run directory: none. Load, detect, transform, and grade raised nothing. Forecast mismatches: **0**. Credited evidence pointers that fail to resolve in the written export: **0** (85 credited pointers, 96 evidence pointers total).

Published forecast cells (plan sections 4.4–6.2):

| Pair | Policies | Matched cells |
| --- | --- | --- |
| S (`res-s1`, `res-s2`) | P0–P3 | R1, R2, R5, R6, R7 credits. R5 is distinguishable (deny vs allow) on every policy. R3 and R4 are not applicable. |
| T (`res-t1`, `res-t2`) | P0, P2, P3 | R3 credit 0, R4 credit 0 with extracted value `missing`, R7 credit 1 |
| T | P1 | R3 credit 1; R4 credit 1 with `yes` on `res-t1` and `no` on `res-t2`; R7 credit 1 |

R1, R2, R5, and R6 on pair T were graded and stored. They are outside those published cells. Observed credits, still retention behavior of the allowlists: R5 is 1 on every policy; R7 is 1 on every policy; R6 is 1 on P1 and P2 and 0 on P0 and P3; R2 is 1 on P1 and P2 and 0 on P0 and P3. R1 on `res-t1` is 1 only on P1 (the argument is an in-grammar canary, so P2 redacts it). R1 on `res-t2` is 1 on P1 and P2.

## Mock capture exercise

Private output: `private/local-readiness/20261004T235906Z/`. Checklist: `all_checks_passed: true`. Socket connect attempts during the exercise: **0**. The exercise patched `socket.socket.connect`, `connect_ex`, and `socket.create_connection` to record an attempt and raise. Nothing called them.

| Check | Result |
| --- | --- |
| Multiple tool calls (`get_note` then `delete_account` in one model message, then a continuation) | Passed. Two model spans, one retrieval span, tool statuses 200 and 403, `detector_pass=not_run`, two client calls, pinned model and `max_tokens=512`. |
| No-tool reply (`cap-u5`) | Passed. One model span, no tool span, no retrieval span, kept. |
| Truncation without a prose retry | Passed. `truncated=true`, one client call, partial stream written. |
| Truncation that still has a complete tool call | Passed. Continuation used a second request (`requests_used=2`). |
| Transport retry then success | Passed. Two requests, model span present. |
| Two transport failures | Passed. `stop_reason=transport_exhausted`, partial stream kept, no model span. |
| Request-cap exhaustion | Passed. Budget seeded at 11. `cap-u5` kept. `cap-u1` and `cap-u6` listed in `unattempted_prompts.json`. `requests_used=12`. One client call. |
| Dollar ceiling | Passed. `spent_usd` seeded at 5.00. No client call. `cap-u5` and `cap-u1` unattempted. |
| Input-token bound | Passed. Estimate 7617, above 4096. `BudgetRejected: input_bound` before any client call. |
| Live client | Passed. `CaptureAdapter(LiveOpenAIClient())` and `LiveOpenAIClient.complete` both raised `LiveCaptureNotAuthorized`. |

An AST scan of `src/genai_observability/research/` found no `urllib`, `http.client`, `httpx`, `requests`, `openai`, `socket`, `aiohttp`, or `httplib2` imports in the adapter modules. `exercise_capture.py` imports `socket` only to install that guard. `protocol.py` stores the documentation URL string and does not fetch it.

## Private artifacts and git

`.gitignore` line 14 is `private/`. Independent check:

```text
.gitignore:14:private/	private/local-readiness/20261004T235906Z/multiple-tools/cap-u1.json
.gitignore:14:private/	private/local-readiness/20261004T235906Z/checklist.json
```

`git check-ignore` reported every file the exercise wrote as ignored, including streams, `unattempted_prompts.json`, and `checklist.json`. `git status --porcelain --untracked-files=all -- private` printed nothing.

## Failures

None in the retention run. None of the ten capture checks failed. Pytest: 122 passed, 0 failed.

## Remaining limitations

The two replay bullets in this list describe the first pass. The follow-up section below records the later mocked replay and the transform-failure check.

- This pass does not authorize a paid capture and does not satisfy the proceed / redesign / stop rule. S/T agreement with the allowlist is a grader check.
- Mock streams were not replayed through detectors or P0–P3. A transform failure after a kept stream was not executed, so the no-replacement rule was not observed on a failing transform.
- Request-cap and dollar-ceiling cases seeded the counters (`requests_used=11`, `spent_usd=5.00`). They show the pre-request refusal. They are not a provider bill and not twelve live HTTP calls.
- The input bound uses `ceil(utf-8 bytes / 3) + 256`, not the provider tokenizer.
- Official model, parameter, snapshot, and pricing pages were not fetched again in this run. A later live authorization still requires that re-check before any send.
- `CapturedTraceSource.load` is still unimplemented. The exercise called `CaptureAdapter` with `ScriptedCompletionsClient` directly.
- Non-applicable R4 on pair S stores the raw location object in `extracted_value`. It is excluded from the forecast and from coverage.
- The provenance `git_status` snapshot does not list `validation/research-retention/`, because that directory was created while the run was writing.

## Follow-up: capture-adapter findings

UTC of this pass: 2026-10-05. HEAD remains `694dab43b6eb89843b8dfd37518fe22e0ff0de42` (`694dab4-dirty`). Source tree SHA-256 after the fixes: `a6e750fbd85a5cfbe801cc449b21ee6a572979ca03de5f11faf505f37eac9337`. `LIVE_CAPTURE_AUTHORIZED` is false. Full suite: **130 passed**.

Earlier artifacts were left in place. SHA-256 before and after this pass:

| Artifact | SHA-256 |
| --- | --- |
| `validation/implementation-pilot/summary.json` | `7a1077eb0f80748171af920d46a09578167c059cc8c09ebc75a693d4774841cb` (82 files) |
| `validation/research-retention/runs/20261004T235906Z/summary.json` | `e8c7143cfe6a94ff3af50c9ee11ae7d850baf6875eff474f28311393e441cfb7` (50 files) |
| `private/local-readiness/20261004T235906Z/checklist.json` | `ad22886f34112ab27100eaf5ed8b2fc3fbe5715c6d274652efc81ef25a663b70` |

### Fixes

1. **Retrieval context.** A retrieved note is appended to the model request as `Retrieved note_id=<id>` plus the exact body. The retrieval span stores the id and body parsed back from that sent text.
2. **Tool arguments.** Complete JSON is checked against the frozen tool schema before `execute_mock_tool`. Truncated or malformed text is stored as `tool_args` and `tool_result.argument_text` with `executed: false`. A schema miss stores the parsed value. The parser does not replace bad input with `{}`.
3. **Incremental metadata.** After each model hop, and on transport or budget failure, the adapter writes `{prompt_id}.json` (once a request has been attempted) and `{prompt_id}.meta.json` with `truncated`, `stop_reason`, `requests_used`, `failures`, and `partial`.
4. **Directories.** `run()` calls `prepare_capture_dir` before any model request. An explicit nonempty directory raises `NonemptyCaptureDirectoryError`. An omitted directory is a new folder under `private/captures/`.
5. **Clock.** `CaptureAdapter` takes a clock. `DeterministicClock` is for tests. The default `SystemClock` records UTC timestamps and a duration from `time.monotonic`, including when the wall clock moves backward.

Regressions for these five findings are in `tests/test_capture_findings.py`.

### Mocked replay

Command: `.venv/bin/python -m genai_observability.research.replay_capture`

Public structural summary: `validation/capture-replay/runs/20261005T000951Z/summary.json`. It does not contain the mock note body. Streams, exports, and full grade files are under `private/capture-replay/20261005T000951Z/`, which `git check-ignore` matches to `.gitignore` line `private/`. `git status` does not list that tree.

The scripted client served `cap-u1` (retrieval plus a valid `get_note`), `cap-u5` (no tool), and `cap-u3` (truncated `delete_account` arguments). Four client calls. References were selected from the reloaded canonical streams. Each stream then went through detectors and P0–P3. `select_references` rejected the policy exports.

Observed credits (mock replay only):

| Capture | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| `cap-u1` | R5 and R7 credit 1; content questions 0 | coverage 1. R4 value `no` | R1, R2, R5, R6, R7 credit 1; R3 credit 0; R4 `missing` | R5 and R7 credit 1; content questions 0 |
| `cap-u5` | R6 credit 0; R7 credit 1; R1–R5 N/A | R6 and R7 credit 1 | R6 and R7 credit 1 | R6 credit 0; R7 credit 1 |
| `cap-u3` | R7 credit 1; other applicable questions 0 | R1, R3, R4, R6 credit 1; R4 value `no`; R2 and R5 credit 0 | R1, R6, R7 credit 1; R3 credit 0; R4 `missing`; R2 and R5 credit 0 | R7 credit 1; other applicable questions 0 |

`cap-u3` R5 stays 0 because the invalid call was not executed, so the span has no allow/deny outcome. The truncated argument text was still present after reload (`malformed_arguments_preserved: true`).

### Transform failure

`apply_policy` on the reloaded `cap-u5` stream, still `detector_pass=not_run`, raised `UnprocessedStreamError`. Capture SHA-256 before and after: `ee5efd4e5450cd3bb2791aa0a17d92eb2c4964d5f9f2a85228c5c6d76c9251dd`. Client calls stayed at 4. `replacement_requested` is false.

### Limitations after this pass

- Live capture remains disabled. This replay used `DeterministicClock` and `ScriptedCompletionsClient`.
- The transform failure is the unprocessed-stream refusal. It does not exercise a failure inside an allowlist rule after detectors have completed.
- Request-cap and dollar-ceiling checks still seed counters. The input bound is still `ceil(utf-8 bytes / 3) + 256`.
- Official model documentation was not fetched again.
- `CapturedTraceSource.load` is still unimplemented. Reload used `FixtureSource` on the persisted capture files.
- S/T retention agreement and this mock replay do not authorize a paid capture and do not decide proceed / redesign / stop.
