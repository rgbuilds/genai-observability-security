# Full-study protocol fs.v1

Status: **FROZEN for local and mocked validation only.** Live / paid capture is not authorized. This protocol records every interpretation that `FULL_STUDY_PROPOSAL.md` left open. Code must follow this text. Feasibility scores in `RESEARCH_FEASIBILITY_ASSESSMENT.md` and `private/research-replay/20261005T034345Z` are not modified and are not full-study observations.

Version: `full-study-protocol.v1`

Checklist: `full_study_checklist.v1`

Date: 2026-10-05
Basis: `FULL_STUDY_PROPOSAL.md`, `RESEARCH_FEASIBILITY_ASSESSMENT.md`, `EXPERIMENT_CONTRACT.md`

P0–P3, pattern library v1, Q1–Q15, and R1–R7 stay as published. This checklist has a new version identifier. Do not pool Q, R, and FS percentages.

## 0. Interpretations recorded (nothing silent)

| Open choice in the proposal | Frozen interpretation |
| --- | --- |
| 24 templates + 24 controls? | Yes. Four templates per family F1–F6. Report template count (24) and execution count (48) separately. |
| Half scripted, half captured? | Yes. Two scripted pairs and two capture-once pairs per family (12 + 12 pairs). Capture-once pairs are exercised only with **mocked** API responses in this gate. A later live run, if authorized, uses the same pair ids and prompts. |
| Which facts are essential? | FS1–FS17 below. Ties, reversals, and mixed P0–P3 results are valid. No question was added to force a P3 gap. |
| Is OC1 primary? | Yes. OC1 is a primary content-reconstruction fact in `full_study_checklist.v1`, scored with the same credit rule as other applicable facts. It is not a secondary appendix and it does not replace R4/FS16. |
| What may be committed? | Scripted streams, mocked-capture streams that contain only synthetic library-v1 tokens, public question definitions, canary inventories, and aggregate reports after privacy review. Live captured text, if any later exists, stays under `private/`. |
| Model / budget for live? | Proposed, not authorized: OpenAI snapshot `gpt-4o-mini-2024-07-18`, temperature 0, `max_tokens=512`, input bound 4096 estimated tokens, **80 HTTP requests**, **USD 15.00** conservative ceiling. Official docs must be re-checked immediately before any later send. This gate does not send. |
| Bootstrap or descriptive only? | **Primary analysis is paired descriptive differences only.** The family-stratified 10,000-replicate bootstrap is implemented as a labeled exploratory function and is not a primary result. With two pairs per family/source stratum the intervals are expected to be unstable. |
| Feasibility six streams? | Not reused as full-study observations. |
| Unexpected model behavior? | Keep the stream. Applicability is taken from the canonical stream. Do not relabel family, drop, or recapture to restore a desired shape. The family field is the *intended* template, reported separately from the realized path. |
| P3-distinct pilot rule? | That contract §7 clause was a pilot screen. The full study allows P0–P3 ties. See the contract amendment. |
| FS8–FS10 evidence? | No content-marker vocabulary is frozen. These facts read only `security.*`. P0/P1/P2 are predicted `missing`. That is a retention forecast, not a reason to invent markers. |
| FS4 on P3? | Credit if the export contains the registered `source_id` or the published opaque form `sha256:` + SHA-256(source_id), which P3 already emits. This is a public transform, not a private excerpt. |
| Mixing scripted and captured? | Never average them into one winner. Report each source type, then an unweighted pair of subset means only as a descriptive companion, labeled mixed-descriptive. |
| Zero-canary exposure? | N/A, excluded from exposure means, counted separately. Foreign-token leakage is a separate check. |
| Bootstrap empty exposure stratum? | Exploratory bootstrap **omits** a replicate in which any resampled family/source stratum has zero eligible exposure executions. If more than half of replicates are omitted, report the interval unavailable. |
| Live capture default? | Disabled. `LIVE_CAPTURE_AUTHORIZED` remains false. Full-study code must not send HTTP. |

## 1. Unit of analysis

The paired unit is one **execution**: one canonical stream transformed once per policy (four exports). A matched case/control pair is a design cluster, not four independent samples. Facts and spans are not samples.

Families F1–F6 name the intended prompt design. Realized tool use, retrieval, and copy/no-copy are read from the stream after it exists.

## 2. Scenario matrix (24 templates, 48 executions)

Ids do not encode security outcomes.

| Pair | Family | Source | Case | Control | Intended case shape |
| --- | --- | --- | --- | --- | --- |
| F1A | F1 | scripted | `fs-f1a-case` | `fs-f1a-ctrl` | Canary in user text; `get_note`; value not required as `note_id` |
| F1B | F1 | scripted | `fs-f1b-case` | `fs-f1b-ctrl` | Canary in system text; `get_note` |
| F1C | F1 | mocked-capture | `fs-f1c-case` | `fs-f1c-ctrl` | Different user-input shape; `get_note` |
| F1D | F1 | mocked-capture | `fs-f1d-case` | `fs-f1d-ctrl` | No tool; canary in user text |
| F2A | F2 | scripted | `fs-f2a-case` | `fs-f2a-ctrl` | Canary in retrieval body; `get_note` |
| F2B | F2 | scripted | `fs-f2b-case` | `fs-f2b-ctrl` | Canary originates in tool result |
| F2C | F2 | mocked-capture | `fs-f2c-case` | `fs-f2c-ctrl` | Different source id; retrieval canary |
| F2D | F2 | mocked-capture | `fs-f2d-case` | `fs-f2d-ctrl` | Canary at end of retrieval body |
| F3A | F3 | scripted | `fs-f3a-case` | `fs-f3a-ctrl` | `delete_account` denied; C7 in `authz.principal_id` |
| F3B | F3 | scripted | `fs-f3b-case` | `fs-f3b-ctrl` | Same tool, other denied principal |
| F3C | F3 | mocked-capture | `fs-f3c-case` | `fs-f3c-ctrl` | Denied `delete_account` |
| F3D | F3 | mocked-capture | `fs-f3d-case` | `fs-f3d-ctrl` | Denied `delete_account`, other resource |
| F4A | F4 | scripted | `fs-f4a-case` | `fs-f4a-ctrl` | Allowed `delete_account`; C4 memo in tool args |
| F4B | F4 | scripted | `fs-f4b-case` | `fs-f4b-ctrl` | Allowed `delete_account`; **no canary** |
| F4C | F4 | mocked-capture | `fs-f4c-case` | `fs-f4c-ctrl` | Allowed `delete_account`; no pre-model canary |
| F4D | F4 | mocked-capture | `fs-f4d-case` | `fs-f4d-ctrl` | Allowed `delete_account`; no canary |
| F5A | F5 | scripted | `fs-f5a-case` | `fs-f5a-ctrl` | Retrieval canary copied into tool-arg field (FS16 `yes`) |
| F5B | F5 | scripted | `fs-f5b-case` | `fs-f5b-ctrl` | Retrieval canary not copied (FS16 `no`, OC1 `no`) |
| F5C | F5 | mocked-capture | `fs-f5c-case` | `fs-f5c-ctrl` | Retrieval canary copied into last model output (OC1 `yes`) |
| F5D | F5 | mocked-capture | `fs-f5d-case` | `fs-f5d-ctrl` | Retrieval canary not repeated later |
| F6A | F6 | scripted | `fs-f6a-case` | `fs-f6a-ctrl` | Output-only; canary in model output |
| F6B | F6 | scripted | `fs-f6b-case` | `fs-f6b-ctrl` | Retrieval then canary in output |
| F6C | F6 | mocked-capture | `fs-f6c-case` | `fs-f6c-ctrl` | Output-only response; no pre-model canary |
| F6D | F6 | mocked-capture | `fs-f6d-case` | `fs-f6d-ctrl` | Retrieval then model output; no planted output token |

Control principle: same task, tools, and topology without the planted token (F1, F2, F5, F6) or the opposite authorization grant on the **same** privileged tool (F3, F4). F3/F4 never switch the control to `get_note`.

Authorization and execution are scored separately (FS6 vs tool `status`). A 403 is a denial. A 200 is an allow. Privilege is not inferred from the tool name.

## 3. Canary inventory

Grammar remains library v1: `SYNTH-[A-Z0-9]{2,12}-[0-9A-F]{8}`. Plant only in `content.*` or `authz.*`. Unique token per planting. Origin location is preserved when a token later appears in another field.

| Origin | Tokens (cases only) | Count |
| --- | --- | --- |
| C1 user | `SYNTH-F1C1A-A11A0001`, `SYNTH-F1C1C-D00D000A`, `SYNTH-F1C1D-A12A0011` | 3 |
| C2 system | `SYNTH-F1C2B-B22B0002` | 1 |
| C3 retrieval | `SYNTH-F2C3A-C33C0003`, `SYNTH-F2C3C-E11E000B`, `SYNTH-F2C3D-B13B0012`, `SYNTH-F5C3A-A77A0007`, `SYNTH-F5C3B-B88B0008`, `SYNTH-F5C3C-B44B000E`, `SYNTH-F5C3D-C14C0013` | 7 |
| C4 tool args | `SYNTH-F4C4A-F66F0006` | 1 |
| C5 tool result | `SYNTH-F2C5B-D44D0004` | 1 |
| C6 model output | `SYNTH-F6C6A-C99C0009`, `SYNTH-F6C6B-D15D0014` | 2 |
| C7 authz | `SYNTH-F3C7A-E55E0005` | 1 |

Eligible plantings: **16**. Zero-canary executions: the 24 controls plus eight cases with no plant (`fs-f3b-case`, `fs-f3c-case`, `fs-f3d-case`, `fs-f4b-case`, `fs-f4c-case`, `fs-f4d-case`, `fs-f6c-case`, `fs-f6d-case`) (**32**). Those 32 are N/A for exposure means.

Capture-once canaries must be introduced in frozen pre-model inputs such as the user text or retrieval body. A random token authored only in an expected tool call or expected model output is not an eligible live-capture planting because the model could not know it. F4C, F6C, and F6D therefore have no canary. Their realized tool arguments and outputs remain scored as forensic facts. Scripted fixtures retain C4 and C6 coverage, so all C1–C7 origins remain represented in the local validation suite.

No benign lookalikes are registered. P2 false positives are therefore not in scope. One token per location does not make location-level rates generalizable.

## 4. Checklist `full_study_checklist.v1`

Practitioner rationale is an incident task, not a P3 field name. Mapping to Q/R is historical only.

| ID | Category | Question | Applicable when (canonical stream) | Extractor (export + public definitions) | Evaluator |
| --- | --- | --- | --- | --- | --- |
| FS1 | operational | Which request initiated the trace? | Always | `request_id` | Exact match |
| FS2 | operational | Which model ran? | A model span exists | `model.name` + operation; ambiguous if several identities | Exact dict match on registered keys |
| FS3 | operational | Did retrieval occur? | Always | Retrieval span kind → `yes`/`no` | Equality |
| FS4 | operational | Which retrieval source? | Retrieval occurred | `retrieval.source_id` and/or `retrieval.hash` | Any candidate equals registered source_id or its published opaque form |
| FS5 | operational | Which tool was requested? | A tool span exists | `tool.name`; ambiguous if several names | Equality |
| FS6 | operational | Was the action allowed or denied? | A tool span exists | Prefer `security.authz_decision`; else tool `status_code` `401\|403→denied`, `200→allowed` | Equality |
| FS7 | operational | Parent/child edges? | Always | `parent_span_id` edge set | Registered ⊆ extracted |
| FS8 | security | Was input trusted or untrusted? | `security.trust_class` is set on the stream | `security.trust_class` only | Equality |
| FS9 | security | Was the tool privileged? | A tool span has `privilege_class` | `privileged`→`yes`, else `no` | Equality |
| FS10 | security | Which denial/failure reason? | A tool span has `denial_reason` | `security.denial_reason` | Equality |
| FS11 | security | Did a sensitive-data detector fire? | Always | `yes` if any retained `sensitive_data` event; `no` if `detector_events` key is present and empty; `missing` if the key is omitted | Equality |
| FS12 | content | Exact tool arguments? | A tool was requested | `content.tool_args` list | Canonical object equality |
| FS13 | content | Affected resource? | A tool was requested | `authz.resource` else `content.tool_args.note_id` | Equality |
| FS14 | content | Retrieved excerpt present? | Retrieval text exists | `content.retrieved` | Private excerpt is a substring |
| FS15 | content | Model-output excerpt present? | A model span has output | First model `content.output` | Private excerpt is a substring |
| FS16 | content | Retrieval token also in tool args (or first output if no tool)? | Retrieval occurred, loc2 exists, token registered | loc1 = first `content.retrieved`; loc2 = all tool_args JSON, else first model output | Section 4.4 yes/no/missing (same as R4) |
| OC1 | content | Retrieval token also in the **last** model output? | Retrieval occurred, a model output exists, token registered | loc1 = first `content.retrieved`; loc2 = **last** model `content.output` | Same yes/no/missing discipline |

OC1 source and destination are frozen: first retrieval `content.retrieved` → last model span that has `content.output`. A tool call does not change the destination and does not make OC1 N/A. OC1 is not influence.

`no` on FS16 or OC1 requires both locations present and readable. Drop or `[REDACTED:…]` → `missing` → 0 if applicable.

A policy that lacks evidence scores `missing` → 0. It does not make the question N/A.

No-tool and no-retrieval streams are kept. FS12, FS13, FS5, FS6, FS9, FS10 become N/A without a tool. FS4, FS14, FS16, OC1 become N/A without retrieval (OC1 also needs model output).

Credit needs a correct value and a JSON pointer that resolves in the serialized export. No LLM judge. Extractor never reads manifests, canary inventories, or the filesystem.

### Rejected for this checklist

| Candidate | Why |
| --- | --- |
| Re-score Q15 as a primary FS fact | Repeats validation circularity; family labels are not evidence |
| “Did retrieved text cause the later step?” | Needs an intervention; FS16, OC1, and FS7 are not that design |
| Content-marker answers for FS8–FS10 | No frozen marker vocabulary |
| `untrusted_propagation` | Still reserved, not implemented |

## 5. Predicted retention (allowlist, not capture lessons)

These cells apply to **known streams** (scripted and mocked-capture fixtures). They validate graders. They are not live-model findings.

| Fact | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| FS1, FS2, FS3, FS5, FS7 | 1 | 1 | 1 | 1 |
| FS6 | 1 from `status_code` | 1 | 1 | 1 from `authz_decision` or code |
| FS4 when retrieval exists | 0 | 1 | 1 | 1 via hash/opaque |
| FS8, FS9, FS10 | 0 | 0 | 0 | 1 |
| FS11 when a canary is planted | 0 (key omitted) | 1 | 1 | 1 |
| FS11 when no canary | 0 | 1 (`no`) | 1 (`no`) | 1 (`no`) |
| FS12/FS13 non-canary ids | 0 | 1 | 1 | 0 |
| FS12 when C4 memo is planted | 0 | 1 | 0 (redacted object) | 0 |
| FS14/FS15/FS16/OC1 with in-grammar token | 0 | 1 (yes/no as registered) | 0 (`missing` or unmatched excerpt) | 0 |
| FS14/FS15 with non-canary excerpt | 0 | 1 | 1 | 0 |
| FS16/OC1 when the registered token is not a canary but either location still contains a different canary | 0 | 1 | 0 (`missing` after P2 redacts that location) | 0 |

P0 and P3 are **not** predicted to tie on this checklist: P3 is predicted to add FS4 (when retrieval exists), FS8–FS11, while still missing content facts. A realized tie remains a valid result.

## 6. Outcomes that require a later live capture

Do not treat mocked-capture scores as these:

- Whether a live model calls a tool, skips a tool, or ignores the prompt
- Whether a live model copies a retrieval token into arguments (FS16) or into the last output (OC1)
- Applicability rates under a real model
- Unexpected wording that changes excerpts
- Any cost, latency, or vendor-quality claim

The mocked-capture path exists to prove the adapter, persistence, selection, and graders. Its content is authored in the registry.

## 7. Aggregation

1. Coverage = correct applicable FS facts / applicable FS facts, per execution and policy. Applicability is identical across policies.
2. Exposure = distinct eligible planted canaries found by exact substring scan of the export / eligible canaries for that execution. Zero-canary → N/A.
3. Report execution-level tables, family coverage, fact-category coverage, C1–C7 exposure counts, and the number of executions with any exposed canary.
4. Scripted and mocked-capture subsets are separate. A mixed-descriptive companion may show two subset means side by side. No weighted winner.
5. Paired policy differences are within the same execution.
6. Primary uncertainty: describe the designed suite. No inferential claim. Exploratory bootstrap (seed `20261005`, 10_000 replicates, resample two scripted and two mocked pairs per family with replacement) is labeled exploratory and is omitted as in section 0.

## 8. Exclusions, failures, stop rules

**Failed attempt (not an observation, not replaced):** capture crash or schema-invalid stream before a usable canonical file is written.

**Policy-run failure (stream kept, that policy excluded from rates, not recaptured):** transform or grader exception after a stream exists.

**Do not exclude:** no tool, unexpected wording, ignored instructions, missing retrieval relative to the intended shape, truncated prose, or an OC1/FS16 `no`.

Stop the runner if live HTTP is requested, if `GENAI_LIVE_CAPTURE` would be required to proceed, or if the destination directory is nonempty. Do not reorder prompts to chase tools. Do not replace a stream after a transform failure.

Planned counts: 24 templates, 24 controls, 48 executions, 192 policy exports if every transform succeeds. Report planned vs realized.

## 9. Capture protocol for this gate

Mocked capture only. System instructions, tools `get_note` and `delete_account`, and the conservative cost function are the feasibility surface unless a later live amendment replaces them. Full-study notes, principals, and grants are those in the scenario registry.

Mocked adapter: inject a scripted completions client; persist each stream; select references from the canonical stream only; refuse `LiveOpenAIClient` unless a future written authorization sets a new flag. This revision does not add that flag.

Proposed live bound (not authorized): 24 capture-once executions, up to 80 requests, USD 15.00, same pinned snapshot. Feasibility’s 12-request / $5 ceiling does not carry forward.

## 10. Provenance and privacy

Record protocol version, checklist version, git commit, SHA-256 of allowlists, pattern library, full-study sources, generated streams, manifests, inventories, and each export. Unique run directory. Preserve `failures/`.

Do not commit live captured text. Do not print API keys. The key exposed during feasibility capture must remain revoked.

## 11. Gates

This revision implements proposal gates 2–3 for **local mocked validation**. Gate 4 (clean-commit freeze before live) and gate 5 (live execution) are not authorized here.

## 12. Stop / redesign / proceed for the mocked gate

- **Pass local readiness** if 48 streams exist, 192 mocked exports grade, retention forecasts match section 5, extractors do not import answers, live send is refused, and private paths stay gitignored.
- **Redesign** if FS16/OC1 treat drop/redaction as `no`, or if answers were selected from policy exports.
- **Do not proceed to live capture** from this document alone.
