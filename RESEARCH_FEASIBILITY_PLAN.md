# Research-feasibility plan (second stage)

Status: LOCAL IMPLEMENTATION APPROVED for the R-checklist, pairs S/T, extraction boundaries, R4 missing/no rule, and retention rules. **Opt-in live capture is authorized** as of 2026-10-05, bounded by Appendix A. The default process still does not send. A paid run requires `GENAI_LIVE_CAPTURE=1` and `OPENAI_API_KEY`.

Date: 2026-10-04. Revised to record local-implementation approval and to add Appendix A.

This proposal is a small second-stage study. It asks what incident facts an investigator can reconstruct from telemetry, and which of those facts depend on retained application content. It does not retune P0–P3, does not treat implementation-validation scores as research evidence, and does not choose questions so that any policy is guaranteed to win.

## 1. Why a second stage exists

The implementation-validation suite (PILOT_SPEC.md, VALIDATION_REPORT.md) showed that fixtures, detectors, transforms, and graders obey the frozen contract. Many of those scores follow from the field-availability matrix: P3 alone retains `security.*`; P1 alone retains raw canaries; P0 omits both. Matching those tables is pipeline fidelity, not an empirical privacy/forensic finding.

Contract section 7 still asks whether useful reconstruction can be studied without circularity with P3’s enums, and whether family-level differences could support practitioner guidance. Those questions cannot be answered by re-scoring Q1–Q15 on the same ten fixtures.

This stage proposes a **separate R-checklist**, defined from incident-response tasks. P0–P3 stay as published.

Two kinds of outcome must stay distinct:

| Kind | What it can show | What it cannot show |
| --- | --- | --- |
| **Predictable retention effects** | Scripted pairs S and T, using planted tokens and known allowlists. P0/P3 drop `content.*` / `authz.*`; P2 redacts in-grammar canaries; P1 retains them; R5/R7 can succeed on every policy. | That the study is empirically informative beyond the matrix. |
| **Realistic-capture lessons** | Whether a live model calls a tool, copies retrieved text, or answers without tools; which R-questions become N/A; whether model-chosen arguments are recoverable after replay. | A new experimental unit. Each capture is frozen once and replayed through the same P0–P3. |

Scripted S/T results that match the allowlist are **retention forecasts**, analogous to the validation predicted tables. Only capture-once/replay can surprise those forecasts.

## 2. Separation from implementation-validation

| | Implementation-validation (done) | This stage (proposed) |
| --- | --- | --- |
| Purpose | Pipeline fidelity | Whether the study design is empirically informative |
| Questions | Frozen Q1–Q15 | Separate R-checklist below |
| Sample | 5 templates + 5 controls | Same-tool pair S, pair T, predefined capture set U |
| Success | Predicted tables reproduced | Qualitative proceed / redesign / stop (section 11) |
| Evidence | VALIDATION_REPORT.md | A later, separately versioned report |

Do not pool coverage numbers across the two stages. Do not cite Q15 distinguishability, P3 perfect cells, or P2 0/1 exposure as research results. If this stage is run, use a new unique run directory.

## 3. Design constraints

1. **Questions are independent of P3’s field list.** A question is admitted only if a practitioner would ask it even if `security.*` did not exist.
2. **Do not select questions to crown a policy.** Metadata facts may succeed on every policy. That is acceptable.
3. **P0–P3 are unchanged.** No P4, no post-hoc markers on validation fixtures.
4. **Capture once; replay.** Model calls happen only at capture time.
5. **Extractor never reads reference answers.** It receives the export plus public question definitions (including R2 field selectors). Private manifests are evaluation-only.
6. **No LLM judge.** Credit needs a correct evaluated value and a JSON pointer into the serialized export.
7. **Topology is not influence.** R7 reconstructs edges. R4 reconstructs co-occurrence. Neither is scored as causation.

## 4. Extraction versus private references

Public **question definitions** (code or a committed definition file) name which export fields to read. They contain no expected strings.

Private **answer manifests** hold expected values. For captured executions they may contain model or retrieved excerpts and follow the same private-retention rule as raw traces (section 9).

| R | Extractor (export + public definitions only) | Evaluator (private reference afterward) |
| --- | --- | --- |
| R1 | Emit retained `content.tool_args` as canonical JSON, or `missing`. | Exact object equality with the registered args. |
| R2 | Read the **public field selector** for that execution class (section 4.2). Emit the string or `missing`. | Exact match to the private resource id. |
| R3 | Emit retained `content.retrieved` text, or `missing`. Do not receive the excerpt. | `yes` if the private excerpt is an exact substring of the extracted text. |
| R4 | Emit observed text at the two public locations, or `missing` per location. Do not receive the token. | Section 4.4 (yes / no / missing). |
| R5 | Emit allow/deny from tool `security.authz_decision` or tool `status_code` map. | Equality with the registered outcome. |
| R6 | Emit retained `content.output` text, or `missing`. Do not receive the excerpt. | `yes` if the private excerpt is an exact substring of the extracted text. |
| R7 | Emit the `parent_span_id` edge set. | Registered edges ⊆ extracted edges. |

Captured excerpts used as R3/R4/R6 answers are **private**. Do not commit them. Commit hashes of those manifests, not the excerpt text. Scripted synthetic answers that contain only in-grammar canaries already in committed fixtures may remain in-repo; captured wording may not.

## 4.1 Applicability (execution-level, policy-independent)

A policy that lacks evidence scores `missing` → 0 on an applicable question. It does not make the question N/A.

| R | Applicable when (from the canonical stream / reference definition, not from a policy export) |
| --- | --- |
| R1 | A tool was requested |
| R2 | A tool was requested |
| R3 | Retrieval occurred |
| R4 | Retrieval occurred **and** a later location exists in the stream (tool span or model output, per the public rule below) **and** a token/excerpt is registered for that execution |
| R5 | A tool was requested |
| R6 | A model span with output exists |
| R7 | Always |

**No-tool responses are valid kept outcomes.** If the model never requests a tool, R1, R2, and R5 are N/A, not 0, and the stream is not excluded. If there is no retrieval, R3 and R4 are N/A.

## 4.2 R2 public field selectors

The extractor does not learn the resource id from the answer key. It uses a public selector:

| Execution class | Public selector (first existing wins) |
| --- | --- |
| Scripted pair S and any `delete_account` / `get_note` tool span | `authz.resource` on the tool span; else `content.tool_args.note_id` |
| Captured streams | Same default. An execution may register a different public selector in the **question-definition** sidecar (field path only, no expected value) before transforms. |

The private manifest stores only the expected id string.

## 4.3 R1, R3, R6 scoring notes

R1: `tool.name` alone is not credit. Partial or redacted objects score 0.

R3/R6: source id, hash, model name, and token counts are not credit. If the extracted field is omitted, status is `missing` (0 if applicable). The extractor must not test for a reference substring; it only exports the retained field.

## 4.4 R4 — yes, no, and missing

R4 asks whether a privately registered token occurs in **both** public locations.

**Public locations (frozen):**

1. `content.retrieved` on a retrieval span.
2. `content.tool_args` if a tool span exists; otherwise `content.output`.

**Evaluator outcomes** (after extraction, using the private token):

| Export observability | Token in loc 1 | Token in loc 2 | R4 answer | Score if applicable |
| --- | --- | --- | --- | --- |
| Both locations present and readable | yes | yes | `yes` | 1 if expected `yes` |
| Both locations present and readable | yes | no | `no` | 1 if expected `no` |
| Both locations present and readable | no | any | `no` (no copy of the registered token) | 1 if expected `no` |
| Either location **dropped** (P0/P3 content drop) | — | — | `missing` / unknown | 0 |
| Either location **redacted** so the registered token cannot be observed (P2 canary replacement) | — | — | `missing` / unknown | 0 |
| Extractor reported `missing` for either location | — | — | `missing` / unknown | 0 |

**`no` means “no copy observed” only when both locations are observable.** Dropped or redacted evidence is not a negative. v1 does not treat `[REDACTED:canary_grammar]` as proof the token was or was not present.

R4 is co-occurrence reconstruction. It is not “the retrieved text caused the tool call.”

### Pair T forecasts (retention effects, not capture lessons)

| Execution | Canonical fact | P0 | P1 | P2 (in-grammar token) | P3 |
| --- | --- | --- | --- | --- | --- |
| `res-t1` (copy present) | token in retrieval and tool args | missing | `yes` | missing | missing |
| `res-t2` (no copy) | token in retrieval only | missing | `no` | missing | missing |

## 4.5 R5 and R7

**R5.** Same-tool allow vs deny. Prefer tool-span `security.authz_decision`; else map tool `status_code` `401|403 → denied`, `200 → allowed`. Pair distinguishability is both members correct and different. P0 can succeed from status codes on **every** policy. That is useful metadata reconstruction, not a failed contrast.

**R7.** Registered `parent_span_id` edges. Timestamp order is not credit. Success on P0–P3 is the expected retention effect (topology is retained everywhere). Do not require a policy gap.

**R5 is not** Q8, Q11, or Q15.

## 4.6 Questions considered and rejected

| Candidate | Why rejected here |
| --- | --- |
| Re-score Q2/Q8/Q9/Q11 | P3-enum answers unless a later content-marker condition is approved. |
| “Did retrieved text cause the tool call?” | Needs an intervention design. R4 and R7 are not that design. |
| Q15 as a research outcome | Repeats validation circularity. |
| Enum-ablation profiles | Optional later diagnostic; must not replace P0–P3. |

## 5. Observable events versus content influence

| Claim | May support | Does **not** support |
| --- | --- | --- |
| An event happened | Tool name, status, edges (R5, R7) | — |
| A value was present | Extracted content later matched to a private excerpt (R1–R3, R6) | Hashes, tool names, topology |
| A value appeared in two observable places | R4 `yes` | R7; R4 `missing` |
| No copy in two observable places | R4 `no` | Dropped/redacted fields |
| Untrusted content influenced a later step | **Not scored** | R4, R7, Q14, a future propagation detector |

Pair T is in scope for R3, R4, and R7 only. Do not implement `untrusted_propagation`.

## 6. Composition

### 6.1 Scripted pair S — same-tool authorization (kept)

| Execution | Tool | Decision | Status | Role |
| --- | --- | --- | --- | --- |
| `res-s1` | `delete_account` | deny | 403 | unauthorized attempt |
| `res-s2` | `delete_account` | allow | 200 | authorized completion |

Same tool, different router decision. Score R1, R2, R5, R7. Neither member is a `get_note` control.

**Predictable retention:** R5 and R7 can be correct on P0–P3. R1/R2 missing on P0/P3; P1 exact; P2 exact iff the resource/args are not in-grammar canaries (pair S should use non-canary ids so R1/R2 test content retention, not redaction).

### 6.2 Scripted pair T — dual-location reconstruction (kept)

| Execution | Shape | R4 expected when both locations observable |
| --- | --- | --- |
| `res-t1` | Token in retrieval and later tool args | `yes` |
| `res-t2` | Same topology; token in retrieval only | `no` |

Score R3, R4, R7. Do not score influence. R4 on P0/P2/P3 is `missing`, not `no` (section 4.4).

### 6.3 Captured set U — predefined protocol

Six prompts, **this order**, one capture attempt sequence. Capture once; persist valid canonical streams; replay through unchanged P0–P3.

| Order | ID | Prompt (frozen) | Likely shape (not a success requirement) |
| --- | --- | --- | --- |
| 1 | `cap-u1` | `Summarize the cited note.` | Retrieval and/or `get_note` |
| 2 | `cap-u2` | `What does the cited note say?` | Retrieval and/or model-only |
| 3 | `cap-u3` | `Please remove the cited note.` | May request `delete_account` |
| 4 | `cap-u4` | `Read note note-u4 and return only its title.` | May request `get_note` |
| 5 | `cap-u5` | `Do not use tools. Reply with exactly: acknowledged.` | Likely no tool — **valid** |
| 6 | `cap-u6` | `If you retrieve a note, call get_note with note_id equal to the first word of the retrieved body.` | May copy text into args — score R4 only |

Shared capture context (frozen): mock notes only; tools `get_note` and `delete_account`; no production backend; synthetic note bodies may include library-v1 canaries. Principal and router rules for `cap-u3` are fixed before the first API request (propose: `cap-u3` denied / 403 if `delete_account` is requested).

**Applicability** follows section 4.1 after the stream exists. Do not drop `cap-u5` because it has no tool.

**Exclude from rates (predefined). Do not replace the prompt or spend a new capture to fill the slot:**

- Canonical schema validation failure, forbidden telemetry keys, or non-finite numbers (no usable stream).
- Capture-adapter crash before a stream is written.
- Transform or grade failure on an already-written stream: keep the stream; record the failed policy export; **do not** issue a replacement capture.

**Do not exclude:**

- No tool call.
- Unexpected wording.
- Model ignores `cap-u5` or `cap-u6` instructions.
- Retrieval or tool missing relative to the “likely shape” column.

Invalid schema streams consume their API requests and are failed-run records. Remaining prompts still run in order until the request cap.

## 7. Necessary contract amendments

None are in force until recorded against a contract version.

| Contract locus | Amendment |
| --- | --- |
| §7 | This stage is a research-feasibility gate, not the 24–30 scenario full study and not a Q1–Q15 re-run. Validation passing does not authorize it. |
| §4 / §5 | Add R1–R7 as a **separate** checklist. Extractor sees question definitions only. Private captured excerpts stay out of extraction and out of the committed repo. |
| §4 | Admit pair S and pair T (F5 reconstruction, no influence scoring). |
| §11 Realistic traces | Capture-once, hash, replay. Load with `detector_pass=not_run`. Predefined prompts and exclusions (section 6.3). |
| §11 Aggregation | Equal weight per **kept** execution; report S, T, and U separately; do not average with validation coverage. |
| §11 Artifacts | **Private retention** for captured raw traces **and** for answer-manifest excerpts derived from those traces (retrieved text, model output, tool args). Commit hashes, public question definitions, applicability flags, and the later report. Scripted synthetic fixtures/answers may remain committed. |
| §3 Policies / detectors | No change to P0–P3 or library v1. No propagation detector. |
| §8 | Bounded model API for capture only (section 8). Unique run directories; hashes written before result files. Every API request counts toward the cap. |
| §10 | R4/R7 must not be published as influence. Predictable retention on S/T is not a capture lesson. |

## 8. Provider, model, tokens, and dollar ceiling

Proposed bound. Review may substitute a same-cost-class model **before** the first request, not after seeing outputs.

| Item | Bound |
| --- | --- |
| Provider | OpenAI |
| Model | Pinned snapshot `gpt-4o-mini-2024-07-18` (do not use the floating `gpt-4o-mini` alias in a live run) |
| API | Chat Completions `v1/chat/completions` with the two mock tools. Official model page (checked 2026-10-04): function calling supported; `max_tokens` legal up to 16,384 output; context 128k. Re-verify immediately before any live run. |
| Temperature | `0` |
| Per-request completion cap | `max_tokens=512` |
| Per-request **input** bound | **4,096 estimated input tokens** (conservative char/3 count of messages + tool schemas + pad). Refuse the request if the estimate exceeds this; do not send. |
| Dollar ceiling | **USD 5.00**. Enforce with a **conservative pre-request check** (Appendix A.5) that includes history, tool schemas, assumed full 512 output tokens, continuations, and retries. |
| Request cap | **12 HTTP requests to the model API, total** |
| What counts as one request | Every chat-completions call: initial turns, **tool-result continuations**, HTTP retries, and provider-required repeats. A 3-hop tool loop is up to 4 requests. |
| Successful streams kept | At most the 6 predefined prompts, if budget remains |
| Model shopping | Forbidden after the first request |
| Tools | Mock `get_note`, `delete_account` only |
| Secrets | No production user data. Library v1 canaries only if planted in mock notes |

The 12-request cap is binding and will often prevent all six prompts from completing a tool loop. Continue in the frozen order; do not skip `cap-u5` to “save” requests for a tool-heavy prompt; do not add a seventh prompt if a no-tool capture “wastes” a slot.

Stop at the first of: 12 requests, $5.00, or all six prompts finished.

The adapter (not written now) emits `canonical_event_stream.v1` without expected labels, family codes, or `detector_pass=completed`.

## 9. Ground-truth and scoring workflow

1. **Scripted S/T:** write fixtures and private synthetic answer keys; public selectors as in section 4.2.
2. **Capture U:** run prompts in order under section 8. From each **kept** stream’s capture transcript, write a **private** answer manifest (excerpts, resource ids, registered R4 token if any). Write a public question-definition record (selectors and applicability only).
3. Detectors once; unchanged P0–P3 replay. A transform failure does not trigger a new capture.
4. Extract R1–R7 from each export using public definitions only.
5. Evaluate against private manifests. Coverage = correct applicable R-facts / applicable R-facts.
6. Exposure: existing canary scan; N/A when the eligible denominator is 0.
7. Report S, T, and U as three blocks. Label S/T cells that match section 4.4–4.5 as **retention forecasts**. Label U as **capture observations**.

## 10. Predictable retention versus capture lessons

**Forecast on S/T (allowlist, not research):**

- R7: yes on P0–P3.
- R5: yes on P0–P3 for pair S (status_code or `authz_decision`).
- R1/R2 (non-canary ids): missing P0/P3; yes P1; yes P2 if no canary/secret-key redaction.
- R3/R4/R6 with in-grammar canaries: missing P0/P2/P3; P1 yes or no per section 4.4.

Matching those cells validates the new R-graders. It does **not** satisfy contract section 7.

**What U can teach (if anything):**

- How often R1–R5 are N/A because the model used no tool.
- Whether model-chosen `tool_args` are complete enough for R1 after P1/P2.
- Whether a copy into tool args occurs without being scripted (R4 `yes` on P1 only if both fields retained).
- Whether P2 redacts anything that is not a planted canary (secret-like keys in model JSON).
- Whether replay hashes are stable on messy, non-hand-authored streams.

Empty or no-tool U results are informative about applicability, not a reason to recapture.

## 11. Proceed, redesign, or stop

Qualitative. Judge **new** R-results only. Do not require a policy gap on R5 or R7.

**Proceed toward a full-study proposal** if all of the following hold:

- **Useful metadata reconstruction:** R5 (on pair S) and R7 (on S/T, and on U when edges exist) are correctly scored and investigator-usable. Success on **all** policies is acceptable and expected for R7 and is acceptable for R5.
- **Informative content-dependent measurements:** R1–R4 and R6 can be interpreted—including predicted `missing` on policies that drop or redact the field, and `yes`/`no` only where content is observable. A forced “some policy must miss metadata” is **not** required.
- Pair S isolates same-tool allow vs deny without a `get_note` confound.
- Pair T assigns R4 `yes` / `no` / `missing` per section 4.4 without influence language.
- Capture obeyed the prompt order, request cap, dollar ceiling, and no-replacement rule; replay hashes are stable on kept streams.
- Exposure and coverage stay separate; no composite winner.

**Redesign** if:

- R-graders leak private excerpts into extraction, or R4 treats drop/redaction as `no`.
- Pair S is still confounded (different tools, or status codes that do not match the router).
- Capture protocol was violated (replacement after transform failure, prompt reordering to chase tools, uncounted continuations).
- Reviewers would reasonably read R4/R7 as influence.
- U cannot be interpreted even as applicability data (for example, answers were written from exports instead of capture transcripts).

**Stop** if:

- After S/T behave as pure retention forecasts, U adds no applicability or reconstruction information and cannot be run under the budget without protocol violations.
- The work becomes a model-quality or vendor benchmark.
- Required amendments (section 7) are declined and no coherent subset remains.

A proceed decision does not authorize the 24–30 scenario full study.

## 12. Authorization boundary

**Authorized now (local only):** R graders; scripted S/T fixtures and synthetic answers; a capture adapter exercised with **mocked** API responses; unit tests; Appendix A recorded as the intended live protocol.

**Authorized on request (2026-10-05):** one opt-in paid capture command, `python -m genai_observability.research.live_capture`, only when `GENAI_LIVE_CAPTURE=1` and `OPENAI_API_KEY` are set. It uses pinned snapshot `gpt-4o-mini-2024-07-18`, the Appendix A budget, and writes under `private/captures/`. Docs were re-checked the same day; prices and the snapshot still match Appendix A.5.

**Not authorized:** treating S/T retention-forecast matches as research evidence; changing P0–P3, library v1, or Q1–Q15; content-marker planting on validation fixtures; `untrusted_propagation`; P4. A live run is not research go/no-go evidence by itself.

Captured streams, captured answer excerpts, captured policy exports, and captured extraction/result files stay under `private/` (gitignored). They can reproduce raw text.

## 13. Review checklist

**Approved for local implementation** (this revision):

1. R1–R7 as a separate checklist; extract-then-evaluate with public selectors (especially R2) and private excerpts (R3/R4/R6).
2. R4 `no` only when both locations are observable; otherwise `missing`.
3. Proceed rule: metadata may succeed on all policies; do not require an R5/R7 gap.
4. Pair S kept; pair T kept; influence not scored.
5. Predefined U prompts, order, applicability, exclusions; no-tool kept; no replacement capture after transform failure.
6. Pinned snapshot `gpt-4o-mini-2024-07-18`, `max_tokens=512`, input bound 4,096 estimated tokens, **12 requests including continuations and retries**, **USD 5.00** ceiling with a conservative pre-request check. Official docs must be re-checked immediately before any later live run.
7. Private retention for captured traces, captured answer excerpts, **captured policy exports**, and **captured extraction/result files**.
8. S/T retention forecasts vs U capture lessons.
9. VALIDATION_REPORT.md remains implementation evidence only.

Opt-in live capture is approved under Appendix A. The command does not send unless `GENAI_LIVE_CAPTURE=1` is set in that process.

## Appendix A — Capture protocol (frozen before any live run)

User prompts alone are not a protocol. This appendix freezes the application surface, reference selection, truncation/cap handling, and cost controls. Live capture still requires a separate authorization and an immediate re-check of official OpenAI documentation.

### A.1 System instructions (frozen)

```
You are a note assistant for a mock application. Use only the provided tools
and retrieved notes. Do not invent note ids. Do not call external services.
If you cannot complete a request with the available tools, say so briefly.
```

### A.2 Tool schemas (frozen)

`get_note` (type `read`): required object `{ "note_id": string }`.

`delete_account` (type `action`): required object `{ "note_id": string }`. Ordinary names; they do not encode privilege.

### A.3 Mock notes and retrieval (frozen)

| Note id | Body |
| --- | --- |
| `note-cited` | `Alpha SYNTH-RETRVL-C00C0003 body for the cited note.` |
| `note-u4` | `TitleOnly note without a planted canary.` |

Retrieval (deterministic, before the model call for that user turn):

1. If the user text contains `note-u4`, retrieve `note-u4`.
2. Else if the prompt id is `cap-u1`, `cap-u2`, `cap-u3`, or `cap-u6`, or the user text contains `cited note`, retrieve `note-cited`.
3. Else no retrieval span.

`get_note` returns the matching mock body in `content.tool_result` only (not as `content.retrieved`). R3 reads retrieval, not tool results.

### A.4 Router permissions (frozen)

| Tool | Principal | Decision | Status |
| --- | --- | --- | --- |
| `get_note` | `principal-capture` | allow | 200 |
| `delete_account` | `principal-capture` | deny | 403 |

Pair S remains scripted (`res-s1` / `res-s2`) and does not use this capture principal.

### A.5 Cost and token bounds (pre-request)

Checked against https://developers.openai.com/api/docs/models/gpt-4o-mini on 2026-10-04:

- Snapshot to pin: `gpt-4o-mini-2024-07-18`
- Input **$0.15** / 1M tokens; output **$0.60** / 1M tokens (standard, not batch)
- `max_tokens=512` is within the 16,384 max-output limit
- Function calling is listed as supported
- Re-verify availability, parameters, snapshot list, and the pricing page immediately before any live call. If they differ, stop; do not send.

Conservative estimate for **each** prospective HTTP request:

1. Serialize the full message history, system text, and tool schemas as UTF-8 JSON.
2. `estimated_input_tokens = ceil(byte_length / 3) + 256`.
3. If `estimated_input_tokens > 4096`, refuse the request (input bound).
4. `estimated_output_tokens = 512` (always assume the completion cap is used).
5. `raw_usd = estimated_input_tokens / 1e6 * 0.15 + estimated_output_tokens / 1e6 * 0.60`.
6. `conservative_usd = raw_usd * 1.25`.
7. If `spent_usd + conservative_usd > 5.00` or `requests_used + 1 > 12`, do not send.

Retries and tool-result continuations each run this check and increment `requests_used`.

### A.6 Deterministic reference selection (canonical stream only)

Select answers from the **canonical stream or capture transcript**, never from a policy export.

Span order is the stream’s `spans` list order.

| Item | Rule |
| --- | --- |
| Tool sequence | Every `kind=tool` span, in order. Multiple tool calls are first-class. |
| R1 expected | List of each tool span’s `content.tool_args` in that order. |
| R2 expected | For each tool span, `authz.resource` if set, else `content.tool_args.note_id`. Registered value is that list (or the single string if length 1). Public selector paths stay in question definitions. |
| R3 excerpt | On the first retrieval span: first library-v1 canary substring if present, else the first 32 characters of `content.retrieved`. |
| R4 token | First library-v1 canary in the first retrieval body, else the R3 excerpt. Not registered if R4 is N/A. |
| R4 locations | Loc1 = first retrieval `content.retrieved`. Loc2 = concatenated canonical JSON of **all** tool_args in order if any tool span exists, else the first model `content.output`. |
| R5 expected | For each tool span: `denied` if `authz_decision=deny` or `status_code` in {401,403}; `allowed` if allow or 200. Length-1 lists may be stored as a string. |
| R6 excerpt | First model output: first canary if present, else first 32 characters. |
| R7 edges | Every `(parent_span_id, span_id)` where parent is non-null. |
| Applicability | Section 4.1 on this stream. |

### A.7 Truncation, partial captures, and cap exhaustion

- `finish_reason=length`: keep the partial stream, mark `truncated=true`. Do not send a follow-up solely to finish truncated prose. If the truncated message still contains complete `tool_calls`, a tool-result continuation may proceed only after a successful cost/cap check.
- Transport errors: a retry counts as a new request and needs a new cost check. After two failed transports on the same hop, keep any partial stream and move on (no replacement prompt).
- **Request-cap or dollar-ceiling exhaustion:** stop. Persist every partial or complete capture already written. Write `unattempted_prompts.json` listing remaining predefined ids (`cap-uN`) that were never started. Do not start a new prompt. Do not reorder.
- A prompt that received at least one HTTP request is **attempted**, even if truncated or tool-less.

### A.8 Private artifacts

Do not commit:

- `private/captures/` raw canonical streams from live or mock-to-disk capture
- `private/captured-answers/` manifests containing captured excerpts
- `private/captured-exports/` P0–P3 exports of captured streams
- `private/captured-results/` extraction/evaluation of those exports

Exports and grade files can reconstruct raw text. Scripted S/T fixtures and their synthetic answers may remain in git.
