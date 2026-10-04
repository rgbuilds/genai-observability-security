# Experiment contract: GenAI observability privacy and forensic utility

Status: DRAFT — scaffolding-blocking decisions resolved 2026-10-04; remaining decisions and overall contract approval still pending.

Draft date: 2026-10-04.

Source: [RSAC Experiment Plan — GenAI Observability: Privacy vs Forensic Utility](https://docs.google.com/document/d/1LLWyr7YPC73cy9Ctu1YoKHwk8pqzNozYz1akzZ8Rumk/edit), read 2026-10-04.

Repository: https://github.com/rgbuilds/genai-observability-security (private during design and pilot).

This document translates the source plan into a proposed experimental contract. It records no results. Policy definitions, metrics, and change rules become binding for a phase only after the decisions that phase depends on are recorded as resolved. This phase produces the contract only; implementation and execution follow review. Resolved section 11 items are binding for scaffolding and grader design. Remaining section 11 items are not approved.

## 1. Research question and contribution

How much incident-reconstruction value can an LLM application retain in telemetry without copying sensitive application content into the observability system?

The contribution is a reproducible synthetic incident suite, a paired comparison of telemetry policies, and evidence about which incident facts depend on raw content. Sensitive telemetry, redaction, and privacy/observability tradeoffs are not claimed as novel.

The study measures two separate outcomes: sensitive-content exposure and forensic reconstruction coverage. It must not assume that structured minimization wins, that full-content telemetry reconstructs everything, or that simple redaction fails. Null, unfavorable, and mixed results are valid outcomes.

## 2. Experimental unit and controlled comparison

Each scenario execution produces one canonical internal event stream. Every telemetry policy transforms that same stream. Model calls must not be rerun independently for each policy. Scenario-level comparisons are paired; spans, facts, and repeated replays are not independent experimental samples.

The pipeline is: controlled execution or fixture, canonical events, policy transform, exported telemetry, deterministic grading, analysis.

The synthetic application includes instructions, user input, optional retrieval, a mock tool router, authorization context, tool arguments/results, model output, and trace relationships. Include read-like and action-like tools. Mock tools have no external side effects, and no production service is targeted.

The pilot uses deterministic scripted fixtures as the canonical-event source. The publication study should include realistic LLM/tool traces; the capture method and their role remain open until the full-study freeze. Any captured interaction is replayed identically across policies. Scaffold interfaces must accept canonical events from fixtures now and from a later capture adapter without changing policy or grader contracts.

## 3. Telemetry policies

All transforms must be deterministic, versioned, and auditable. A policy must not consult scenario answers or grading results. The runtime always computes the full canonical stream. Policies differ only by published retain/redact allowlists, not by accidentally withholding instrumentation.

Telemetry must not contain fixture labels or expected conclusions, including `incident_type`, `variant_class`, `expected_q15`, family codes used as answers, or scenario identifiers that encode a security outcome.

### Field-availability matrix

Runtime source fields and policy retention:

| Field | Runtime source | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- |
| `trace_id`, `span_id`, `parent_span_id` | span context | retain | retain | retain | retain |
| `request_id` | root request identifier | retain | retain | retain | retain |
| timestamps, `duration_ms`, operation name, span kind | span metadata | retain | retain | retain | retain |
| `model.provider`, `model.name`, token counts | model span | retain | retain | retain | retain |
| `tool.name`, `tool.type` | tool span | retain | retain | retain | retain |
| `status` (`ok` \| `error`), `status_code` | span status | retain | retain | retain | retain |
| `content.system`, `content.user`, `content.output`, `content.retrieved`, `content.tool_args`, `content.tool_result` | raw payloads | drop | retain | redact | drop |
| `authz.principal_id`, `authz.roles`, `authz.resource` | raw authorization context | drop | retain | redact | drop |
| `retrieval.source_id` | retrieval identity | drop | retain | retain | opaque/hashed only |
| `retrieval.hash` | retrieval correlator | drop | optional | optional | retain |
| `security.trust_class` | runtime trust primitive | drop | drop | drop | retain |
| `security.privilege_class` | runtime privilege primitive | drop | drop | drop | retain |
| `security.authz_decision` | runtime authorization decision | drop | drop | drop | retain |
| `security.denial_reason` | runtime denial primitive | drop | drop | drop | retain |
| detector events (`detector_id`, category, stage, `match_class`; no raw match) | runtime detector | drop | retain | retain | retain |

`parent_span_id` is ordinary trace topology, not a P3 enrichment. Tool names must be ordinary operation names and must not encode privilege or incident class. Privilege, trust, authorization decision, and denial reason exist only as the structured fields above, except where P1/P2 content happens to contain an explicit operational phrase that a frozen extractor rule may read.

### P0 — Metadata-only baseline

Retain the APM metadata and topology columns marked retain in the matrix, including parent linkage, `request_id`, `status`, and `status_code`. Exclude raw content, raw authorization context, retrieval identifiers, detector events, and P3 security enums. Do not silently enrich this baseline with P3 fields.

### P1 — Full-content tracing

Retain P0 metadata plus raw content fields, raw authorization context, retrieval source identifiers, and detector events. Do not retain P3 security enums. Raw text alone never earns automatic forensic credit.

### P2 — Content plus simple redaction

Apply a plausible deterministic redaction layer to P1 using pattern library v1, shared with runtime detectors. Preserve surrounding content. Do not build a perfect domain-aware DLP system or modify rules after inspecting held-out results.

Library v1 is frozen as follows:

- Canary grammar, case-sensitive substring: `SYNTH-[A-Z0-9]{2,12}-[0-9A-F]{8}`. Embedded tokens are redacted.
- Secret-like keys: `token`, `password`, `secret`, `api_key` after lowercasing and treating `-` as `_`. A key matches only if it equals a name or ends with `_<name>`. `api_key_count` and `tokenized` do not match.
- No PII rules in v1.
- Replacement text: `[REDACTED:canary_grammar]` for grammar matches; `[REDACTED:secret_key]` for a secret-key value.
- Traverse strings, lists, and dicts only in `content.*` and `authz.*`. Do not scan retain-only metadata such as `tool.name` or `retrieval.source_id`.
- Precedence: a secret-key match replaces the entire value and wins over substring redaction inside that value. Then apply canary substring replacement left-to-right, non-overlapping, including on dictionary keys that match the grammar. Key replacement preserves surrounding key text. If two original keys would share a redacted name, or a redacted name would overwrite an unredacted key, append `_N` for the smallest integer `N >= 2` that is free. Assignment among canary keys is in lexicographic order of the original keys and does not depend on dictionary insertion order.
- `untrusted_propagation` is a reserved category; v1 does not implement a propagation detector.

All eligible pilot canaries must use this grammar and must be planted only in `content.*` or `authz.*`. Under those constraints P2 is expected to expose zero canaries. That outcome is valid. Do not plant out-of-grammar tokens or copy canaries into retain-only fields in order to manufacture a P2 miss.

### P3 — Security-structured minimized telemetry

Retain P0 metadata plus `security.trust_class`, `security.privilege_class`, `security.authz_decision`, `security.denial_reason`, opaque or hashed retrieval identifiers, and detector events. Exclude raw content and raw authorization context.

Any detector event must come from an implemented deterministic runtime detector. A security-event category must describe an observed primitive, not a fixture label. Neither incident answers nor scenario-specific conclusions may be copied into telemetry.

Hashes and opaque identifiers support correlation; they are not by themselves proof of privacy.

### Detector meaning and access

A sensitive-data event is a frozen runtime detector firing on a concrete payload location. Pilot v1 detector classes are canary-grammar matches and secret-like key names from pattern library v1. Detectors must not consult the canary inventory, answer key, fixture identifier, or family label.

Runtime payload detectors run once on the full canonical stream before any policy transform. They replace any fixture-supplied `detector_events` and set stream-level `detector_pass=completed`. `detector_pass` is runtime processing state, not a forensic answer, and is not exported. Policy transforms must not rerun detectors and must reject streams whose detector pass has not completed, so an unprocessed stream cannot export `detector_events: []` as a completed negative. All policies then receive that same enriched stream.

Exported detector evidence uses this representation:

- omitted `detector_events` key: detector evidence is unavailable (P0 drop).
- `detector_events: []`: the runtime detector pass completed with no matches on that span.
- a populated list: observed detector events.

Detector events retain `detector_id`, category, stage, and `match_class`. They omit the raw matched value. Evidence location is `stage` (and the hosting span), not a JSON path. Locations and event fields must not contain raw canary strings or sensitive dictionary keys. P1, P2, and P3 retain these events; P0 omits the key. Report the limitation that detectors cover only predeclared pattern classes.

Approved detector categories are `sensitive_data` and `untrusted_propagation`. v1 emits only `sensitive_data` with `match_class` `canary_grammar` or `secret_key`. Stage values are `user_input`, `instructions`, `retrieval`, `tool_args`, `tool_result`, `model_output`, and `authorization`. Matches in `authz.*` use stage `authorization` (C7).

### Optional P4

Structured telemetry plus narrowly selected content is outside the initial pilot. Consider it only if pilot evidence identifies a principled missing content field. Approve and register it before the full study; do not add it retrospectively to rescue a result.

## 4. Scenarios and canaries

The pilot contains five scenarios spanning at least four distinct families. The full study targets approximately 24–30 scenarios, balanced across six families with four or five scenarios per family:

- F1: sensitive user input.
- F2: sensitive retrieved context.
- F3: unauthorized privileged tool attempt, denied by the router.
- F4: authorized high-risk tool action.
- F5: untrusted retrieved/tool content influencing a subsequent step.
- F6: sensitive model output.

Include benign controls exercising comparable paths. Exact pilot selection and whether controls count within these totals require review. F5 evaluates reconstruction evidence; it does not claim discovery of a new attack. Reconstructing parent/child topology is not proof that untrusted content influenced a later step.

Plant unique, deterministic synthetic canaries by scenario and source location: C1 user input, C2 system/developer instructions, C3 retrieved content, C4 tool arguments, C5 tool results, C6 model output, and C7 authorization/context content. Each canary must match library v1 grammar `SYNTH-[A-Z0-9]{2,12}-[0-9A-F]{8}` and must remain inside `content.*` or `authz.*`. Use that synthetic format rather than real-looking credentials. Preserve original placement attribution when a value propagates to later stages.

Before execution, register scenario version/family, canary inventory and eligibility, applicable forensic facts, expected answers, and evidence requirements. Fixture names, identifiers, and filenames must not reveal expected security outcomes and must not be inputs to the forensic extractor or to the Q15 classification rule.

## 5. Grading boundaries and primary metrics

No LLM judge is permitted. Grading must depend on exported telemetry as evidence, with frozen reference manifests used only for evaluation. Canonical events are not available to graders at grading time.

The exposure grader needs a canary reference inventory to perform exact matching. The forensic system needs applicable questions and expected answers to evaluate correctness. Those references must not act as evidence: the reconstruction stage receives telemetry and question definitions, returns inferred answers and evidence locations, and only then does evaluation compare them with the frozen answer key. Tests must demonstrate this boundary.

### Exposure

canary_exposure_rate = distinct eligible planted canaries found in exported telemetry / distinct planted canaries eligible for exposure in the scenario.

Eligible canaries are planted tokens registered in the scenario manifest before the run. Eligibility does not depend on policy. The denominator is fixed across policies for a given scenario. Count each canary once in the primary rate even if it appears repeatedly.

Scan only the policy export artifact as UTF-8 text for an exact, case-sensitive substring match of each eligible canary. The scan covers serialized values, attribute keys, event names, and envelopes in that file. Do not scan grader sidecars, reference manifests, canonical events, or other non-export paths. A hash or opaque identifier that does not contain the plaintext canary is not an exposure. Pilot matching is exact only; any decoding or canonical transformations must be enumerated before the full run.

Zero-canary controls are not applicable for the exposure rate. Do not report `0/0` as `0`. Still scan those exports as a leakage check for other scenarios' canaries, and report that check separately.

Also report exposure by C1–C7, scenarios with any exposed canary, retained raw-content fields, and P2 false negatives and false positives where defined. Exposed sensitive characters may be a secondary metric with an explicit counting rule.

### Forensic reconstruction

forensic_coverage = correctly reconstructable applicable facts / total applicable facts.

Each applicable fact receives 1 or 0 under a predeclared deterministic evidence rule. Do not award credit merely because a field exists. Missing, ambiguous, contradictory, or incorrect evidence cannot be treated as a correct reconstruction. Nonapplicable facts are excluded rather than credited.

The extractor receives exported telemetry and question definitions only. It returns an inferred answer plus evidence locations, or `missing` / `ambiguous`. The evaluator then compares the extracted answer with the frozen answer key. Credit requires both a correct value and at least one evidence location inside the export.

The candidate question set and frozen evidence predicates are:

1. Q1: Which request initiated the trace? Answer is `request_id` from the export envelope. Do not duplicate `request_id` onto spans.
2. Q2: Was the relevant input trusted or untrusted? Answer vocabulary: `trusted` \| `untrusted` \| `mixed`. Evidence is `security.trust_class` or an explicit frozen trust marker in retained fields. Do not infer trust from source names, URLs, or fixture identity.
3. Q3: Did retrieval occur? Evidence is a retrieval span kind or retrieval operation name.
4. Q4: Which retrieval source/document was involved? Evidence is `retrieval.source_id` or `retrieval.hash` matching the registered identifier. "A document was retrieved" without which one is not credit.
5. Q5: Which model operation occurred? Evidence is retained model operation and identity.
6. Q6: Was a tool requested? Evidence is a tool span or `tool.name`.
7. Q7: Which tool was requested? Evidence is `tool.name`.
8. Q8: Was the tool privileged? Evidence is `security.privilege_class`. P1/P2 receive credit only if retained content contains an explicit frozen privilege marker, not because the tool name looks privileged.
9. Q9: Was the principal authorized? Evidence is `security.authz_decision` or an explicit frozen allow/deny marker in retained content.
10. Q10: Was the action allowed or denied? Prefer `security.authz_decision` when present. Otherwise map `status_code` with the frozen table `401|403 → denied`, `200 → allowed`. Technical `status=error` alone is not authorization evidence.
11. Q11: Which broad denial/failure reason applied? Answer vocabulary: `authorization` \| `validation` \| `not_found` \| `tool_error` \| `model_error` \| `none`. Evidence is `security.denial_reason` or an explicit frozen reason marker in retained content. A status code alone is not sufficient.
12. Q12: Did a sensitive-data event occur? Evidence is a retained detector event with category `sensitive_data`. The extractor must not use the canary inventory.
13. Q13: At which stage did it occur? Evidence is the detector event `stage`.
14. Q14: Can the parent/child causal sequence be reconstructed? Credit if retained `parent_span_id` links contain the registered edge set or declared subsequence. Timestamp order is not credit. Topology reconstruction is not proof of content influence and must not be scored as such.
15. Q15: Can a benign execution be distinguished from its security-relevant variant? The extractor applies the frozen classification rule below to exported operational evidence only. It must never read an exported expected label and must never obtain the label from fixture identifiers, filenames, or family codes.

Frozen Q15 classification rule, recorded before execution:

- Classify `security_relevant` if the export contains at least one of: (a) a detector event whose category is `sensitive_data` or `untrusted_propagation`; (b) `security.authz_decision = deny`; (c) `security.privilege_class = privileged` together with `security.authz_decision = allow` or `status = ok`; (d) `status_code` in `{401, 403}`.
- Otherwise classify `benign`.

The expected Q15 label lives only in the reference manifest. Policies must not export that label. Q15 is applicable only to registered benign/security-relevant pairs and is scored per execution. Report paired distinguishability separately: both members correct and different under the same rule.

Category mapping: provenance Q1–Q5; tool/action Q6, Q7, Q8, Q10; authorization Q9, Q11; sensitive-data events Q12–Q13; causal sequence Q14–Q15.

## 6. Secondary metrics and analysis

Secondary metrics include exported bytes, retained attributes/events, transformation time, storage ratio relative to P1, redaction counts, and correlation completeness. Define serialization and timing procedures before measurement; timing must not dominate the privacy/forensic question.

Report scenario-level paired values, policy means and medians, family-level forensic coverage, and location-level exposure. Keep exposure and forensic coverage as separate axes; do not create a weighted composite winner.

Planned figures are an exposure-versus-coverage scatter, coverage by family and policy, and exposure by location and policy. Payload size versus coverage is optional. Preserve source data and regeneration instructions for all figures.

For the full study, consider scenario-level paired bootstrap intervals for differences if sample size supports them. Freeze resampling unit, weighting, seed, and interval method before final analysis. A small purposive synthetic suite does not justify population-wide inference or forced significance tests.

## 7. Pilot go/no-go review

Run only the five-scenario pilot after scenarios, checklists, policy definitions, and metric rules have been reviewed. The decision is qualitative and structural; there is no invented numerical success threshold.

Proceed to a full-study proposal only if:

- P0 and P1 show a meaningful exposure/forensic contrast.
- P3 occupies a meaningfully distinct position from P0 and P1.
- Several forensic facts can be recovered without raw content.
- Both graders are deterministic and auditable.
- Family-level differences support useful practitioner guidance.

Stop or redesign if policies are nearly indistinguishable, P3 embeds answers, nearly all useful evidence requires raw content, redaction adds no insight, policy/checklist definitions predetermine the result, or the study becomes a vendor benchmark.

Record a go, redesign, or stop decision with evidence and limitations. Passing the pilot does not automatically authorize expansion. The researcher approves the full suite and its freeze separately.

## 8. Execution and reproducibility

Develop and execute in this dedicated repository on the linked Mac Mini. Keep raw traces local; do not send them to an observability SaaS. The pilot does not use an OTLP collector or backend. External access is limited to repository hosting, dependencies, and model APIs if realistic capture is later approved.

Pilot execution format: deterministic JSON fixtures, policy transforms over those fixtures, and a versioned local JSON export as the artifact of record. No live model calls in the pilot. Hash identity uses SHA-256 over canonical JSON: UTF-8, sorted keys, compact separators, `ensure_ascii=false`. Pretty-printed copies may exist for inspection; hashes are computed on the canonical form.

Record macOS, architecture, Python, package versions, relevant OpenTelemetry SDK/instrumentation versions if introduced later, Docker if used, model/provider identity if used, UTC run time, Git commit, and configuration hashes.

For each scenario/policy pair preserve scenario and policy versions, canonical-event hash, export hash and bytes, canary inventory/locations, fact applicability and outcomes, evidence references, exposure counts, correlation completeness, P2 redaction events, and P3 fields used.

Before the full run, freeze and commit scenarios, policies, detectors, grading rules, configs, and analysis definitions. Execute from a clean commit. Preserve failed/invalid run records with their exclusion reasons; do not silently replace unfavorable observations.

## 9. Change control and researcher review

Pilot-driven changes are allowed, but record the prior definition, proposed change, evidence motivating it, expected effect, date, and approval before the next comparison. Keep results from different versions distinguishable.

After full-study freeze, a bug or protocol deviation requires a recorded amendment and affected-run disposition. Do not silently tune policies, checklists, redaction, or detectors against final results. Exploratory analyses must be labeled separately.

Researcher review covers the research question, policies, scenario definitions, forensic checklists, metrics, full-study freeze, interpretation, and externally visible prose. Record approval against a specific contract/scenario/config version; this draft does not assert overall approval.

Scaffolding-blocking decisions and pattern library v1 are resolved. Policy transforms follow this freeze. Graders, draft pilot scenarios, pilot execution, and go/no-go review follow in stages. Pilot composition remains open until scenario approval.

## 10. Interpretation and publication boundary

A 600–800-word RSAC article is the intended first publication, with a reproducible repository carrying details. Submission requirements and cited external guidance must be checked before publication; this contract does not independently verify the source plan's external references.

Claims must follow results. Do not claim universal optimality of P3, that OpenTelemetry is insecure, that full-content tracing should never be used, that synthetic exposure is a breach, that the suite covers every AI application, that a vendor is unsafe, that redaction generally fails, or that this experiment estimates breach probability. Do not treat Q14 topology credit as evidence that untrusted content influenced a later step.

The eventual evidence pack should include setup, counts, policy definitions, metrics, defensible findings, limitations, artifact paths, reproducibility commit, and unsupported claims. No findings or publication conclusions are asserted now.

## 11. Decisions for contract review

### Resolved 2026-10-04 — required before scaffolding or grader implementation

- **Policy fairness and instrumentation:** Runtime computes the full canonical stream. Retention follows the section 3 matrix. P0 keeps APM metadata, parent linkage, `request_id`, and status fields only. P1/P2 keep that plus raw content, raw authorization context, retrieval source IDs, and detector events, and drop P3 security enums. P3 keeps metadata plus trust, privilege, authorization decision, denial reason, opaque identifiers, and detector events, and drops raw content. Differences come from published allowlists.
- **Detector meaning and access:** A sensitive-data event is a frozen runtime detector firing on a payload location. Detectors use the shared pattern library and never the answer key. Events omit raw matched values. P1/P2/P3 retain detector events; P0 drops them.
- **Exposure boundary:** Eligible canaries are registered before the run; the denominator is fixed across policies. Scan only the policy export file as UTF-8 for exact canary substrings. Do not scan graders, manifests, or canonical events. Hashes without plaintext do not count. Zero-canary controls are not applicable for the rate, not `0/0`. Pilot matching is exact only.
- **Forensic evidence rules:** Extractor then evaluator, with credit requiring an extracted answer plus evidence location. Predicates and category mapping are in section 5. Q14 is parent/child topology only and is not proof of content influence. Q15 derives `benign` / `security_relevant` from the frozen operational rule in section 5; the expected label is never exported and is never obtained from fixture identifiers.
- **Pilot execution format:** Deterministic JSON fixtures and policy transforms; no live model calls and no OTLP collector in the pilot. The artifact of record is a versioned local JSON export. Hash with SHA-256 over canonical JSON. Interfaces must allow captured traces to be added later as another canonical-event source.
- **Pattern library v1 and detector pipeline (before transforms):** Library v1 grammar, secret-key rule, replacements, payload-only traversal, and secret-key-then-substring precedence are frozen in section 3. All eligible pilot canaries stay in that grammar and in `content.*` / `authz.*`; expected P2 zero exposure is valid. Payload detectors run once before transforms, replace fixture-supplied events, and do not emit raw matches or sensitive keys. Stage `authorization` covers `authz.*` / C7. `untrusted_propagation` remains reserved and is not implemented in v1. Transforms do not rerun detectors.
- **Detector-drop representation:** Omitted `detector_events` means evidence is unavailable. `[]` means the runtime pass completed with no matches. A populated list contains observed events. Canonical `detector_pass` records whether that pass ran and is not exported. Transforms reject unprocessed streams.

### Still unresolved — not required to implement transforms

- **Pilot composition and controls (before scenario approval):** Select five scenarios across at least four families, and decide how controls count. Proposed approach: distinguish scenario templates from execution variants and report both counts explicitly, keeping related variants paired in analysis.
- **Realistic trace inclusion (before full-study freeze):** Define what realistic LLM/tool traces must contribute and how stochastic capture is versioned. Do not substitute model variability for policy comparison.
- **Aggregation and uncertainty (before full-study freeze):** Resolve treatment of control variants, missing/invalid runs, family weighting, bootstrap grouping and parameters, and remaining zero-denominator cases beyond the exposure-rate rule above. Proposed primary aggregation: equal weight per registered scenario, with grouped variants handled explicitly and denominators reported.
- **Artifact retention and publication (before full-study freeze):** Decide which synthetic traces and reference manifests may be committed or released, local retention rules, and the eventual public reproducibility package. Repository visibility remains private during design and pilot.

Review record: scaffolding-blocking decisions approved 2026-10-04 with the Q14/Q15 constraints above. Pattern library v1 and the pre-transform detector pipeline approved 2026-10-04; propagation detector deferred. Detector-drop representation (omit vs `[]` vs populated list; reject unprocessed streams) adopted 2026-10-04. Overall contract approval, remaining decisions, pilot authorization, and full-study authorization have not been recorded.
