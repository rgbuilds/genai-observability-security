# Pilot scenario and grading specification

Status: IMPLEMENTATION-VALIDATION — fixtures, graders, and scoring choices recorded. A passing implementation check does not satisfy the contract section 7 research go/no-go.

Date: 2026-10-04. Revised the same day to mark this suite as an implementation-validation pilot, to fix Q12/Q13, exposure denominators, F5 scope, and F3/F4 control confounds, and to record extractor scoring choices including same-span Q15 and JSON-pointer evidence locations.

This specification defines the five-scenario implementation-validation pilot. It does not change frozen policies, pattern library v1, detector access, Q14/Q15 rules, or exposure scanning. It does not plant content markers or out-of-grammar canaries. Expected answers live in separate reference manifests; they are tabulated here for review.

## 1. Role of this suite

This suite is an **implementation-validation pilot**, not the contract section 7 research go/no-go.

**Implementation checks** (this phase, after fixtures and graders exist):

- Canonical fixtures load, validate, and hash stably.
- Runtime detectors run once, replace fixture-supplied events, and omit raw matches.
- P0–P3 remain pure allowlist transforms on the same enriched stream.
- Graders read exports plus question definitions only; tests prove they do not read reference manifests as evidence.
- Predicted scores from the frozen allowlists and this spec are reproduced.

**Research feasibility** (later, separately authorized):

- Whether P0 and P1 show a meaningful exposure/forensic contrast that is not only the allowlist definition.
- Whether P3 occupies a distinct position for reasons other than “P3 alone has these enums.”
- Whether several forensic facts can be recovered without raw content under evidence rules that are not circular with P3’s field set.
- Whether family-level differences support practitioner guidance.

Reproducing the predicted score tables in this document **does not** satisfy those research criteria. Many of those scores are predetermined by field availability (section 5). An implementation that matches them shows the pipeline is faithful, not that the study design is empirically informative.

## 2. Composition and counts

**Proposal:** five security-relevant scenario templates spanning five families, each with one paired benign control. Controls are **additional executions**, not members of the five-scenario total.

| Count | What is counted |
| --- | --- |
| 5 | Scenario templates (security-relevant members only) |
| 5 | Families represented in this suite: F1, F2, F3, F4, F6 |
| 5 | Benign-control executions (additional) |
| 10 | Total executions (paired 1:1) |
| 4 | Security-relevant executions with ≥1 eligible canary (`exec-11`, `exec-21`, `exec-31`, `exec-51`) |
| 6 | Executions with zero eligible canaries (all five controls plus `exec-41`) |
| 4 | Policies applied to each execution (P0–P3) |
| 40 | Export artifacts if this validation run is executed |

Primary sample for implementation checks: the five security-relevant executions, plus their controls for Q15 pairs and leakage scans. Exposure rates use only executions with a positive eligible-canary denominator (four security-relevant executions). Controls are not extra family samples.

### F5 is a scope choice

F5 (untrusted retrieved or tool content influencing a later step) **can** be studied without a `untrusted_propagation` detector. Q14 remains topology only and must not be scored as influence. A later F5 pair could still evaluate:

- Provenance: Q2/Q4 on the untrusted retrieval source (P3 structured fields, or P1/P2 content if a later research condition plants recoverable source identity).
- Topology: the registered retrieval → model → tool edges on every policy.
- Retained content on P1: the same canary substring appearing in `content.retrieved` and a later `content.tool_args` or `content.output`, as reconstruction evidence only.

Deferring F5 from **this** suite keeps the implementation-validation set smaller. It is not required by the reserved propagation detector or by Q14.

## 3. Shared conventions

### Identifiers

Fixture and execution IDs are opaque. Family, variant class, and expected Q15 labels do not appear in filenames, `scenario_id`, span names, or tool names.

| Pair | Security-relevant execution | Benign control | Family |
| --- | --- | --- | --- |
| A | `exec-11` | `exec-12` | F1 sensitive user input |
| B | `exec-21` | `exec-22` | F2 sensitive retrieved context |
| C | `exec-31` | `exec-32` | F3 unauthorized privileged tool, denied |
| D | `exec-41` | `exec-42` | F4 authorized high-risk tool action |
| E | `exec-51` | `exec-52` | F6 sensitive model output |

Tool names are ordinary: `get_note` (read) and `delete_account` (action). They do not encode privilege. This draft plants **no** explicit content markers such as `trusted`, `untrusted`, `privileged`, `allow`, `deny`, or denial-reason tokens.

### F3/F4 controls compare different operations

The F3 and F4 benign controls use `get_note` rather than `delete_account`. That is **not** an isolated authorization change on the same tool.

| Member | Tool | Privilege | Decision | Status |
| --- | --- | --- | --- | --- |
| `exec-31` | `delete_account` | privileged | deny | 403 |
| `exec-32` | `get_note` | none | allow | 200 |
| `exec-41` | `delete_account` | privileged | allow | 200 |
| `exec-42` | `get_note` | none | allow | 200 |

Confounded factors include tool identity, privilege class, and (for F3) denial versus allow. An authorized `delete_account` cannot be the F3 “benign” control: that execution is F4. A same-operation F3/F4 contrast (denied vs allowed `delete_account`) is a later research pair, not a benign-control pair.

### Topology

Children hang off the request span unless a scenario says otherwise. Q14 credit is the registered `parent_span_id` edge set. Timestamp order is not evidence. Topology is not evidence of content influence.

### Canaries and exposure denominators

Every eligible canary matches `SYNTH-[A-Z0-9]{2,12}-[0-9A-F]{8}` and is planted only in `content.*` or `authz.*`. Eligibility is registered before the run and is policy-independent.

**Zero eligible canaries ⇒ exposure rate N/A for that execution**, whether or not it is a control. Do not report `0/0` as `0`. Still scan those exports for other executions’ tokens (leakage check).

Exposure summaries therefore have **four eligible security executions**, not five. `exec-41` is security-relevant and zero-eligible; it is N/A for exposure.

### Detectors

Runtime detectors run once on the canonical stream before transforms and replace any fixture-supplied events. Transforms do not rerun them. v1 emits only `sensitive_data` with `match_class` `canary_grammar` or `secret_key`.

### Q15

The extractor applies the frozen contract rule to exported operational evidence only. The expected label lives only in the reference manifest. F3 and F4 can both classify as `security_relevant` and must still be distinguished by Q8–Q11.

### Reference manifests

One canary inventory and one answer key per execution:

```
references/canaries/exec-11.json
references/answers/exec-11.json
```

The extractor receives telemetry plus question definitions. It must not read these files. The evaluator compares extractor output to the answer key only after extraction.

Canary-manifest fields: `execution_id`, `eligible_canaries[]` with `canary_id`, `token`, `location` (`C1`–`C7`), `payload_field`, `eligible`.

Answer-manifest fields: `execution_id`, `pair_id`, `q15_expected` (`benign` \| `security_relevant`), `questions[]` with `id`, `applicable`, `answer`, `registered_edges` (Q14 only). Applicability in the manifest is execution-level, not policy-level.

## 4. Question applicability (policy-independent)

Applicability is a property of the execution and the reference manifest. It does not change by policy. A policy that lacks evidence scores `missing` → 0 on an applicable question. It does not make the question N/A.

| Q | Applicable when (execution / reference) |
| --- | --- |
| Q1 | Always |
| Q2 | A relevant input exists |
| Q3 | Always |
| Q4 | Retrieval occurred |
| Q5 | Always |
| Q6 | Always |
| Q7 | A tool was requested |
| Q8 | A tool was requested |
| Q9 | A tool was requested |
| Q10 | A tool was requested |
| Q11 | A tool was requested |
| Q12 | Always |
| Q13 | The reference sensitive-data event occurred (planted detector-firing payload) |
| Q14 | Always |
| Q15 | Registered pair members |

Q13 therefore applies to **every policy** on `exec-11`, `exec-21`, `exec-31`, and `exec-51`. P0 scores `missing` / 0, not N/A. Q13 is not applicable on executions where no reference event occurred (`exec-12`, `exec-22`, `exec-32`, `exec-41`, `exec-42`, `exec-52`), including P1–P3.

Expected evidence, when the question is applicable:

| Q | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| Q1 | envelope `request_id` | same | same | same |
| Q2 | missing | missing (no planted marker) | missing | `security.trust_class` |
| Q3 | span `kind` | same | same | same |
| Q4 | missing | `retrieval.source_id` | `retrieval.source_id` | opaque id / hash |
| Q5 | model metadata | same | same | same |
| Q6–Q7 | tool span / `tool.name` | same | same | same |
| Q8 | missing | missing (no planted marker) | missing | `security.privilege_class` |
| Q9 | missing | missing (no planted marker) | missing | `security.authz_decision` |
| Q10 | `status_code` map | `status_code` map | `status_code` map | decision or `status_code` |
| Q11 | missing | missing (no planted marker) | missing | `security.denial_reason` |
| Q12–Q13 | key omitted → missing/0 | retained `[]` or list | retained `[]` or list | retained `[]` or list |
| Q14 | `parent_span_id` edges | same | same | same |
| Q15 | frozen operational rule | same | same | same |

### 4.1 Q12 absence: adopted detector-drop representation

Q12 must distinguish “detector ran and found nothing” from “policy dropped detector evidence.”

**Adopted and implemented:**

| Export shape | Meaning | Q12 extraction |
| --- | --- | --- |
| `detector_events` key **absent** | Policy dropped detector evidence | `missing` (score 0 if Q12 applicable) |
| `detector_events: []` | Detector ran; no `sensitive_data` event | `no` |
| `detector_events` contains `category=sensitive_data` | Detector ran and fired | `yes` |

Canonical streams carry `detector_pass` (`not_run` \| `completed`). That field is runtime processing state, not a forensic answer, and is not copied into the export. `apply_runtime_detectors` is the only step that sets `completed` and writes per-span lists (empty or populated). `apply_policy` rejects `not_run` streams so an unprocessed fixture cannot export `[]` as a completed negative. Transforms do not rerun detectors.

P0 omits the `detector_events` key. P1–P3 retain the list produced by the detector pass. No `detector_evidence=dropped` enum is added to P0.

### 4.2 Recorded scoring choices

These choices freeze extractor/evaluator behavior for this suite. They do not change the contract predicates. They were recorded because the contract left the comparison details unspecified.

| Topic | Recorded choice | Why |
| --- | --- | --- |
| Q10 `status_code` | Prefer tool-span `security.authz_decision` when present. Otherwise map the **tool** span `status_code` (`401\|403 → denied`, `200 → allowed`). Do not use the request-span code. Unmapped codes are `missing`. | A request span is `200` on `exec-31` while the tool is `403`. Using the request code would score Q10 as `allowed`. |
| Q2 / Q8 / Q9 / Q11 markers | Read only structured `security.*` fields. This suite plants no content-marker vocabulary and does not invent one. | Invented phrases would give P1/P2 credit the tables forecast as missing/0. |
| Q15 clause (c) | Same-span: `security.privilege_class = privileged` together with `security.authz_decision = allow` **or** `status = ok` on **that span**. A privileged tool plus an `ok` request span is not enough. | “Together with” is evaluated on one span. |
| Q15 otherwise | If no clause matches, classify `benign`. The expected label is never read from the export, fixture id, or filename. | Frozen contract rule. |
| Q3 | `kind == retrieval` only. No frozen retrieval-operation-name list. | Avoid scoring from span names. |
| Q5 | Structured answer `{provider, name, operation}` compared field-wise to the reference. | The spec lists three tokens without a concatenation rule. |
| Q4 | Extractor emits exported `retrieval.source_id` and `retrieval.hash`. Evaluator accepts an exact registered identifier or `opaque_identifier(registered)`. | Extractor must not read the answer key; P3 retains an opaque id. |
| Q14 | Credit if the registered edge set is a **subset** of extracted `parent_span_id` edges. Timestamp order is not evidence. | Contract: retained links “contain the registered edge set.” |
| Q13 multiple stages | One distinct stage → that stage; more than one → `ambiguous`. | Not exercised by this suite. |
| Evidence locations | JSON pointers into the **serialized export artifact** (canonical JSON: UTF-8, sorted keys, compact separators, `ensure_ascii=false`, `exclude_none`). Credit requires at least one pointer that resolves in that document. | The artifact of record is the written export, not an in-memory model dump. |

Applicability stays on the execution’s answer manifest and is identical across P0–P3.

## 5. Predetermined implementation-check results

These outcomes follow from frozen allowlists and this spec. Matching them validates implementation. It is not research evidence.

- **P2 exposure is 0/1** on each of the four eligible security executions. Canaries are in-grammar and payload-scoped. That is valid. Do not plant out-of-grammar tokens or retain-only leaks to force a miss.
- **P0 and P3 exposure are 0/1** on those four executions (payload fields dropped).
- **P1 exposure is 1/1** on those four executions.
- **Six executions are N/A** for exposure (denominator 0): `exec-12`, `exec-22`, `exec-32`, `exec-41`, `exec-42`, `exec-52`.
- **Q1, Q3, Q5, Q6, Q7, Q14** are recoverable on all policies when applicable.
- **Q2, Q8, Q9, Q11** are recoverable on P3 and missing/0 on P0/P1/P2 because no content markers are planted.
- **Q10** is recoverable from `status_code` on tool-bearing executions for all policies.
- **Q12/Q13** are missing/0 on P0 for every applicable execution because the `detector_events` key is omitted.
- **Q15 F3:** all policies can distinguish the pair via `403` vs `200`, but the control also changes the tool.
- **Q15 F4:** only P3 distinguishes the pair (privileged+allow). P0/P1/P2 classify `exec-41` as `benign`.
- **Q15 F1/F2/F6:** P1/P2/P3 distinguish via detectors; P0 does not.

## 6. Later research-feasibility stage (not this suite)

To test **what evidence a fact needs** without treating P3’s field list as the only structured answer, register separate research conditions after this validation suite. Do not retune P0–P3 to manufacture contrast.

Candidates, each approved and versioned before use:

1. **Content-marker condition.** Same canonical streams, plus prospectively planted frozen operational phrases in P1/P2 content (`trust_class=untrusted`, `privilege: privileged`, and the like). Measures whether Q2/Q8/Q9/Q11 need P3 enums or can be recovered from content. This suite plants none of those phrases.
2. **Enum-ablation condition.** Same streams, additional export profiles that retain detectors and status codes but not `security.*` enums, or the reverse. Measures which Q15/Q8–Q11 facts depend on enums versus detectors versus `status_code`.
3. **Same-operation authorization pair.** `delete_account` denied vs `delete_account` allowed. Isolates authorization. Neither member is a benign `get_note` control.
4. **F5 reconstruction pair.** Canary in retrieved content copied into a later tool argument. Score Q4, Q14 topology, and P1 dual-location content. Do not score Q14 as influence. No propagation detector required.

Those conditions are out of scope here.

## 7. Scenario specifications

Shared model identity when a model span exists: `name=chat.completion`, `model.provider=mock`, `model.name=fixture-model`.

Policy columns below are **score forecasts** (`yes` = correct reconstruction, `missing/0` = applicable but no evidence, `incorrect` = extractor would emit the wrong label). Applicability does not change across columns.

### Pair A — F1 sensitive user input

#### `exec-11` (security-relevant)

| Span | Kind | Parent | Status | Notes |
| --- | --- | --- | --- | --- |
| `sp-11-req` | request | none | ok / 200 | `content.user` contains C1; `content.system` has no canary; `authz` present, no C7 |
| `sp-11-mdl` | model | `sp-11-req` | ok | Ordinary completion; output has no canary |
| `sp-11-tol` | tool | `sp-11-req` | ok / 200 | `get_note`; `privilege_class=none`; `authz_decision=allow`; `denial_reason=none` |

Registered Q14 edges: `sp-11-req→sp-11-mdl`, `sp-11-req→sp-11-tol`. `trust_class=untrusted` on the request span.

| ID | Token | Location | Payload field |
| --- | --- | --- | --- |
| C1 | `SYNTH-USERIN-A11F0001` | C1 | `content.user` |

No C2–C7. Runtime detector: `sensitive_data` / `canary_grammar` at `user_input` on `sp-11-req`. Eligible canaries: **1**. Exposure denominator: 1.

| Q | Applicable | Answer | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | yes | `req-11` | yes | yes | yes | yes |
| Q2 | yes | `untrusted` | missing/0 | missing/0 | missing/0 | yes |
| Q3 | yes | `no` | yes | yes | yes | yes |
| Q4 | no | — | — | — | — | — |
| Q5 | yes | `mock` / `fixture-model` / `chat.completion` | yes | yes | yes | yes |
| Q6 | yes | `yes` | yes | yes | yes | yes |
| Q7 | yes | `get_note` | yes | yes | yes | yes |
| Q8 | yes | `no` (`none`) | missing/0 | missing/0 | missing/0 | yes |
| Q9 | yes | `allow` | missing/0 | missing/0 | missing/0 | yes |
| Q10 | yes | `allowed` | yes (`200`) | yes | yes | yes |
| Q11 | yes | `none` | missing/0 | missing/0 | missing/0 | yes |
| Q12 | yes | `yes` | missing/0 | yes | yes | yes |
| Q13 | yes | `user_input` | missing/0 | yes | yes | yes |
| Q14 | yes | registered edges | yes | yes | yes | yes |
| Q15 | yes | `security_relevant` | incorrect (`benign`) | yes | yes | yes |

P2 redacts C1 and keeps the detector event. Expected exposure 0/1. P1 expected 1/1.

#### `exec-12` (benign control)

Same topology, `get_note`, allow, `200`, no canary, no detector after the runtime pass. Eligible canaries: **0**. Exposure: **N/A**. Leakage scan still runs.

Q1 answer `req-12`. Q12 applicable, answer `no` on P1/P2/P3; missing/0 on P0. **Q13 not applicable** (no reference event) for any policy. Q15 `benign` on all policies.

**Q15 pair:** distinguishable on P1/P2/P3, not on P0.

### Pair B — F2 sensitive retrieved context

#### `exec-21` (security-relevant)

| Span | Kind | Parent | Status | Notes |
| --- | --- | --- | --- | --- |
| `sp-21-req` | request | none | ok / 200 | User asks for a summary; no C1 |
| `sp-21-ret` | retrieval | `sp-21-req` | ok | `retrieval.source_id=doc-2100`; hash set; `content.retrieved` contains C3; `trust_class=untrusted` |
| `sp-21-mdl` | model | `sp-21-req` | ok | Output has no canary |
| `sp-21-tol` | tool | `sp-21-req` | ok / 200 | `get_note`; privilege none; allow |

Registered Q14 edges: `sp-21-req→sp-21-ret`, `sp-21-req→sp-21-mdl`, `sp-21-req→sp-21-tol`.

| ID | Token | Location | Payload field |
| --- | --- | --- | --- |
| C3 | `SYNTH-RETRVL-B22E0002` | C3 | `content.retrieved` |

Detector: `sensitive_data` / `canary_grammar` at `retrieval`. Eligible canaries: **1**. Exposure denominator: 1.

| Q | Applicable | Answer | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | yes | `req-21` | yes | yes | yes | yes |
| Q2 | yes | `untrusted` | missing/0 | missing/0 | missing/0 | yes |
| Q3 | yes | `yes` | yes | yes | yes | yes |
| Q4 | yes | `doc-2100` or opaque hash | missing/0 | yes | yes | yes |
| Q5 | yes | model identity | yes | yes | yes | yes |
| Q6 | yes | `yes` | yes | yes | yes | yes |
| Q7 | yes | `get_note` | yes | yes | yes | yes |
| Q8 | yes | `no` | missing/0 | missing/0 | missing/0 | yes |
| Q9 | yes | `allow` | missing/0 | missing/0 | missing/0 | yes |
| Q10 | yes | `allowed` | yes | yes | yes | yes |
| Q11 | yes | `none` | missing/0 | missing/0 | missing/0 | yes |
| Q12 | yes | `yes` | missing/0 | yes | yes | yes |
| Q13 | yes | `retrieval` | missing/0 | yes | yes | yes |
| Q14 | yes | registered edges | yes | yes | yes | yes |
| Q15 | yes | `security_relevant` | incorrect (`benign`) | yes | yes | yes |

P2 redacts C3; `retrieval.source_id` is not a canary. Expected exposure 0/1.

#### `exec-22` (benign control)

Same four-span topology and `doc-2100`. No canary, no detector. Eligible canaries: **0**. Exposure: **N/A**. Q4 still applicable. Q12=`no` on P1/P2/P3; missing/0 on P0. Q13 not applicable. Q15=`benign`.

**Q15 pair:** distinguishable on P1/P2/P3, not on P0.

### Pair C — F3 unauthorized privileged tool, denied

Must remain distinguishable from Pair D even when both security members are Q15 `security_relevant`.

#### `exec-31` (security-relevant)

| Span | Kind | Parent | Status | Notes |
| --- | --- | --- | --- | --- |
| `sp-31-req` | request | none | ok / 200 | User asks to remove a note; no C1 |
| `sp-31-mdl` | model | `sp-31-req` | ok | Requests `delete_account`; output has no canary |
| `sp-31-tol` | tool | `sp-31-req` | error / **403** | `delete_account`; privileged; deny; `denial_reason=authorization`; `authz.resource` contains C7 |

Registered Q14 edges: `sp-31-req→sp-31-mdl`, `sp-31-req→sp-31-tol`.

| ID | Token | Location | Payload field |
| --- | --- | --- | --- |
| C7 | `SYNTH-RESID-C33D0003` | C7 | `authz.resource` on `sp-31-tol` |

Detector: `sensitive_data` / `canary_grammar` at `authorization`. Eligible canaries: **1**. Exposure denominator: 1. C7 placement is unchanged.

| Q | Applicable | Answer | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | yes | `req-31` | yes | yes | yes | yes |
| Q2 | yes | `untrusted` | missing/0 | missing/0 | missing/0 | yes |
| Q3 | yes | `no` | yes | yes | yes | yes |
| Q4 | no | — | — | — | — | — |
| Q5 | yes | model identity | yes | yes | yes | yes |
| Q6 | yes | `yes` | yes | yes | yes | yes |
| Q7 | yes | `delete_account` | yes | yes | yes | yes |
| Q8 | yes | `yes` (`privileged`) | missing/0 | missing/0 | missing/0 | yes |
| Q9 | yes | `deny` | missing/0 | missing/0 | missing/0 | yes |
| Q10 | yes | `denied` | yes (`403`) | yes | yes | yes |
| Q11 | yes | `authorization` | missing/0 | missing/0 | missing/0 | yes |
| Q12 | yes | `yes` | missing/0 | yes | yes | yes |
| Q13 | yes | `authorization` | missing/0 | yes | yes | yes |
| Q14 | yes | registered edges | yes | yes | yes | yes |
| Q15 | yes | `security_relevant` | yes (`403`) | yes | yes | yes |

P2 redacts C7. Expected exposure 0/1.

#### `exec-32` (benign control)

Same request→model→tool **shape**, but the tool is `get_note`, not a denied `delete_account`. Privilege `none`, allow, `200`, no C7, no detector. Eligible canaries: **0**. Exposure: **N/A**.

This control changes operation, privilege, decision, and status together (section 3). Q7=`get_note`. Q8=`no`. Q9=`allow`. Q10=`allowed`. Q11=`none`. Q12=`no` on P1/P2/P3. Q13 not applicable. Q15=`benign`.

**Q15 pair:** expected distinguishable on all policies via `403` vs `200`, with the operation confound noted above.

### Pair D — F4 authorized high-risk tool action

Legitimate privileged action. Q15 `security_relevant` via clause (c), not an authorization failure.

#### `exec-41` (security-relevant)

| Span | Kind | Parent | Status | Notes |
| --- | --- | --- | --- | --- |
| `sp-41-req` | request | none | ok / 200 | Authorized deletion request; no canary |
| `sp-41-mdl` | model | `sp-41-req` | ok | Requests `delete_account` |
| `sp-41-tol` | tool | `sp-41-req` | ok / **200** | `delete_account`; privileged; allow; `denial_reason=none` |

Registered Q14 edges: `sp-41-req→sp-41-mdl`, `sp-41-req→sp-41-tol`.

Eligible canaries: **0**. Exposure: **N/A**. Leakage scan still runs. No detector events.

| Q | Applicable | Answer | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | yes | `req-41` | yes | yes | yes | yes |
| Q2 | yes | `untrusted` | missing/0 | missing/0 | missing/0 | yes |
| Q3 | yes | `no` | yes | yes | yes | yes |
| Q4 | no | — | — | — | — | — |
| Q5 | yes | model identity | yes | yes | yes | yes |
| Q6 | yes | `yes` | yes | yes | yes | yes |
| Q7 | yes | `delete_account` | yes | yes | yes | yes |
| Q8 | yes | `yes` (`privileged`) | missing/0 | missing/0 | missing/0 | yes |
| Q9 | yes | `allow` | missing/0 | missing/0 | missing/0 | yes |
| Q10 | yes | `allowed` | yes (`200`) | yes | yes | yes |
| Q11 | yes | `none` | missing/0 | missing/0 | missing/0 | yes |
| Q12 | yes | `no` | missing/0 | yes (`[]` retained) | yes | yes |
| Q13 | no | — | — | — | — | — |
| Q14 | yes | registered edges | yes | yes | yes | yes |
| Q15 | yes | `security_relevant` | incorrect (`benign`) | incorrect (`benign`) | incorrect (`benign`) | yes |

P1 seeing `delete_account` is not Q8 credit. Q13 is not applicable because no reference sensitive-data event occurred.

#### `exec-42` (benign control)

`get_note`, privilege `none`, allow, `200`, no canary. Different operation from `exec-41` (section 3). Eligible canaries: **0**. Exposure: **N/A**. Q15=`benign` on all policies.

**Q15 pair:** distinguishable only on P3.

### Pair E — F6 sensitive model output

#### `exec-51` (security-relevant)

| Span | Kind | Parent | Status | Notes |
| --- | --- | --- | --- | --- |
| `sp-51-req` | request | none | ok / 200 | User question; no C1 |
| `sp-51-mdl` | model | `sp-51-req` | ok | `content.output` contains C6 |

No tool span. Registered Q14 edges: `sp-51-req→sp-51-mdl`.

| ID | Token | Location | Payload field |
| --- | --- | --- | --- |
| C6 | `SYNTH-MODELO-E55B0005` | C6 | `content.output` |

Detector: `sensitive_data` / `canary_grammar` at `model_output`. Eligible canaries: **1**. Exposure denominator: 1.

| Q | Applicable | Answer | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | yes | `req-51` | yes | yes | yes | yes |
| Q2 | yes | `untrusted` | missing/0 | missing/0 | missing/0 | yes |
| Q3 | yes | `no` | yes | yes | yes | yes |
| Q4 | no | — | — | — | — | — |
| Q5 | yes | model identity | yes | yes | yes | yes |
| Q6 | yes | `no` | yes | yes | yes | yes |
| Q7 | no | — | — | — | — | — |
| Q8 | no | — | — | — | — | — |
| Q9 | no | — | — | — | — | — |
| Q10 | no | — | — | — | — | — |
| Q11 | no | — | — | — | — | — |
| Q12 | yes | `yes` | missing/0 | yes | yes | yes |
| Q13 | yes | `model_output` | missing/0 | yes | yes | yes |
| Q14 | yes | registered edges | yes | yes | yes | yes |
| Q15 | yes | `security_relevant` | incorrect (`benign`) | yes | yes | yes |

P2 redacts C6. Expected exposure 0/1.

#### `exec-52` (benign control)

Same two-span topology. No canary, no detector. Eligible canaries: **0**. Exposure: **N/A**. Q6=`no`. Q12=`no` on P1/P2/P3. Q13 not applicable. Q15=`benign`.

**Q15 pair:** distinguishable on P1/P2/P3, not on P0.

## 8. Exposure summary (denominators explicit)

Eligible security executions: **4** (`exec-11`, `exec-21`, `exec-31`, `exec-51`). Each denominator is 1.

| Execution | Eligible | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- |
| `exec-11` | 1 | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-21` | 1 | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-31` | 1 | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-51` | 1 | 0/1 | 1/1 | 0/1 | 0/1 |
| `exec-41` | 0 | N/A | N/A | N/A | N/A |
| `exec-12`, `exec-22`, `exec-32`, `exec-42`, `exec-52` | 0 | N/A | N/A | N/A | N/A |

If a mean exposure is reported for implementation checks, state **n = 4** eligible security executions (not 5). P2 mean 0/1 on those four is the predicted validation target, not a research claim that redaction “works.”

## 9. Predicted Q15 distinguishability (implementation check)

| Pair | P0 | P1 | P2 | P3 | Notes |
| --- | --- | --- | --- | --- | --- |
| A F1 | no | yes | yes | yes | Detector vs none |
| B F2 | no | yes | yes | yes | Detector vs none |
| C F3 | yes | yes | yes | yes | `403` vs `200`, plus different tools |
| D F4 | no | no | no | yes | Privileged+allow only on P3; tools also differ |
| E F6 | no | yes | yes | yes | Detector vs none |

Matching this table validates the Q15 extractor against the frozen rule. It does not show that P3 is a generally better forensic policy.

## 10. Decisions still requiring review

Resolved unless you object: implementation-validation framing; Q13 applicability follows the reference event, not the policy; zero eligible canaries ⇒ N/A on every execution; exposure n = 4; F5 deferral is scope; F3/F4 controls are different-operation comparisons; C7 on `exec-31` kept; no content markers; detector-drop representation (section 4.1) adopted; scoring choices in section 4.2 adopted.

Adopted for this implementation-validation suite: 5 templates + 5 additional controls (10 executions); F1/F2 carry `get_note` so Q6–Q11 apply; manifests at `references/canaries/` and `references/answers/`.

Still open:

1. **When to authorize a research-feasibility stage** (section 6), including any F5 pair or same-operation authorization pair. A passing implementation-validation run does not authorize that stage.

## 11. Out of scope for this phase

Do not expand the suite, plant content markers, or begin realistic-model capture. Do not treat a matching implementation-validation report as the contract section 7 research go/no-go.
