# Full-study results

This report is a privacy-safe summary of one completed live-capture study. The sole numerical source is the sanitized aggregate `validation/reporting/full-study-aggregate-input.json` (`full_study_sanitized_aggregate.v1`). Design language comes only from `FULL_STUDY_PROTOCOL.md`, `FULL_STUDY_PROPOSAL.md`, and `EXPERIMENT_CONTRACT.md`. No captured prompts, model replies, retrieved text, or export excerpts are included.

The evidence came from the completed live capture. Each model interaction was captured once against snapshot `gpt-4o-mini-2024-07-18` and replayed identically through published policies P0–P3. Forensic coverage and canary exposure are separate outcomes. They are not combined into one score, and no policy is treated as universally best.

Scripted mixed-descriptive values in the aggregate are empty and are not part of this sample. Implementation validation, mocked validation, and the earlier feasibility replay are not full-study observations.

## Study status

Execution completed successfully.

| Item | Aggregate value |
| --- | --- |
| Evidence role | `authoritative-clean-live-replay` |
| Protocol | `full-study-protocol.v1` |
| Checklist | `full_study_checklist.v1` |
| Model snapshot | `gpt-4o-mini-2024-07-18` |
| Paid capture count | 1 |
| Planned executions | 24 |
| Realized executions | 24 |
| Failed executions | 0 |
| Unattempted executions | 0 |
| Planned exports | 96 |
| Realized exports | 96 |
| Failed runs | 0 |
| Unresolved credited evidence pointers | 0 |
| Replay detector runs | 0 |
| Replay status `ok` | true |
| Capture stop reason | null |
| Requests used | 44 |
| Request cap | 80 |
| Estimated spent (USD) | 0.021606374999999994 |

The 96 exports are four paired policy transforms of the same 24 frozen executions. They are not 96 independent observations.

## Experimental design

This was a capture-once / replay study. The paid model interaction for each of the 24 capture-once executions happened once. The resulting canonical streams were then transformed by four published retention allowlists:

- **P0** — metadata-only baseline: APM metadata and topology; no raw content, raw authorization context, retrieval identifiers, detector events, or security enums.
- **P1** — full-content tracing: P0 metadata plus raw content, raw authorization context, retrieval identifiers, and detector events; no P3 security enums.
- **P2** — content plus simple redaction: P1 fields after shared pattern-library v1 detector/redaction patterns. Surrounding text is preserved; matching tokens are replaced.
- **P3** — security-structured minimized telemetry: P0 metadata plus security enums, opaque or hashed retrieval identifiers, and detector events; no raw content and no raw authorization context.

P0–P3 differences come from those published allowlists, not from different runtime instrumentation. The runtime always produced the full canonical stream. P2 uses the same detector/redaction patterns as the runtime detectors. P3 retains security metadata and detector events while excluding raw content.

The frozen checklist is `full_study_checklist.v1` (FS1–FS16 and OC1). Facts are scored extract-then-evaluate against each export. Applicability is taken from the canonical stream and is identical across policies.

Comparisons are paired in two ways: the same execution through P0–P3, and matched case/control pairs within each family. Primary analysis is descriptive. The study does not claim statistical significance.

Two outcomes stay separate:

1. **Forensic coverage** — correctly reconstructed applicable checklist facts divided by applicable facts for that execution and policy.
2. **Canary exposure** — exact substring matches of registered eligible canaries inside the policy export, divided by eligible canaries for that execution. Zero-canary executions are not applicable to exposure means.

Coverage does not measure privacy risk. Exposure does not measure reconstructability. Neither measures attack prevention, model safety, policy compliance, causal influence, or production incident outcomes.

## Replay integrity and authority

The paid capture was performed once (`paid_capture_count` = 1) and was not repeated.

The authoritative replay came from a clean committed Git state:

- `authoritative_git_commit` = `2d31ab6f71ae4a32111b905ec9f30c9b76150b91`
- `authoritative_git_dirty` = false
- `evidence_role` = `authoritative-clean-live-replay`

Its capture artifacts, source freeze, replay artifacts, permissions, export count, and credited evidence pointers passed integrity checks:

- capture hashed artifacts = 123
- capture artifacts including manifest = 124
- capture-time source files verified = 69
- replay hashed artifacts = 363
- replay artifacts including manifest = 364
- replay permission violations = 0
- realized exports = 96
- unresolved credited evidence pointers = 0
- replay `ok` = true

The earlier dirty-tree replay is retained only as a reproducibility check (`earlier_replay_role` = `reproducibility-check-only`; `earlier_replay_git_dirty` = true). That comparison completed successfully: `exports_identical` = true, `extractions_identical` = true, and `results_identical` = true.

The clean replay is the sole source used for reported findings.

## Applicability denominators

Applicability is an execution-level property of the realized stream. It does not change by policy. A policy that lacks retained evidence scores `missing` for an applicable fact; it does not make the fact not applicable.

Execution-level applicability denominators from `applicability_denominators`:

| Item | Applicable executions |
| --- | --- |
| FS1 | 24 |
| FS2 | 24 |
| FS3 | 24 |
| FS4 | 10 |
| FS5 | 20 |
| FS6 | 20 |
| FS7 | 24 |
| FS8 | 24 |
| FS9 | 20 |
| FS10 | 20 |
| FS11 | 24 |
| FS12 | 20 |
| FS13 | 20 |
| FS14 | 10 |
| FS15 | 24 |
| FS16 | 10 |
| OC1 | 10 |

Protocol applicability, for orientation only: FS1, FS3, FS7, and FS11 apply to every execution; FS2 and FS15 require a model span; FS8 requires a trust-class value on the stream; FS5, FS6, FS9, FS10, FS12, and FS13 require a tool span; FS4 and FS14 require retrieval; FS16 and OC1 require retrieval plus a registered token and a readable destination location. The aggregate does not publish per-execution applicability maps beyond these denominators.

## Forensic coverage by policy

Values are copied exactly from `aggregates.coverage_by_policy`. They are not converted to percentages.

| Policy | Forensic coverage |
| --- | --- |
| P0 | 0.4346046110751993 |
| P1 | 0.8065072182719241 |
| P2 | 0.7672915319974143 |
| P3 | 0.7329778065072183 |

These are descriptive paired means over the same 24 executions. They are not a ranking that practitioners should treat as a universal winner.

What the table shows in this frozen set:

- P0 coverage is 0.4346046110751993. That is the metadata-only baseline: useful for request, model, tool, status, and topology questions, and weak on security enums and content.
- P1 reconstructed the most applicable facts. It is also the only policy with non-zero canary exposure, reported in the separate exposure section.
- P2 sat between P1 and P3. Shared redaction kept more reconstructable content than drop-content policies while removing registered-canary exposure.
- P3 sat between P0 and P2. It was not identical to P0 in this sample, and it was not the highest-coverage policy. It adds security metadata and detector events without retaining raw content.

A later section reports the paired P3−P0 and P1−P0 differences that sit behind these means. No inferential test is attached.

## Coverage by evidence category

Values are copied exactly from `aggregates.coverage_by_category`.

| Category | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| operational | 0.9315068493150684 | 1.0 | 1.0 | 1.0 |
| security | 0.0 | 0.2727272727272727 | 0.2727272727272727 | 1.0 |
| content | 0.0 | 1.0 | 0.8297872340425532 | 0.0 |

Operational facts are FS1–FS7. Security facts are FS8–FS11. Content facts are FS12–FS16 and OC1.

Observed pattern, read against the published allowlists:

- **Operational.** P1, P2, and P3 are 1.0. P0 is 0.9315068493150684. The protocol predicts that P0 drops retrieval identity (FS4) while still retaining request identity, model identity, retrieval-occurred, tool name, status, and parent/child edges. P3 is predicted to restore retrieval identity through an opaque or hashed correlator. The aggregate does not publish per-fact numerators, so the exact operational shortfall on P0 is not itemized here. The category pattern matches that retention split.
- **Security.** P0 is 0.0, which matches dropping both security enums and the detector-event key. P1 and P2 are 0.2727272727272727. The protocol predicts FS8–FS10 missing on P1/P2 (no security enums) and FS11 credited when detector events are retained. P3 is 1.0, matching retention of `security.trust_class`, `security.privilege_class`, `security.authz_decision`, `security.denial_reason`, and detector events. The material P3-versus-P1/P2 security gain is therefore the structured security enums, not additional raw content.
- **Content.** P0 and P3 are 0.0, matching drop of raw content. P1 is 1.0, matching full content retention. P2 is 0.8297872340425532, below P1 and well above P0/P3, matching redaction that removes registered tokens while leaving surrounding content in place. The aggregate does not publish which content facts account for the P1-to-P2 gap.

## Coverage by scenario family

Values are copied exactly from `aggregates.coverage_by_family`. Families are the intended prompt designs F1–F6.

| Family | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| F1 | 0.5164835164835164 | 0.8131868131868132 | 0.8131868131868132 | 0.8131868131868132 |
| F2 | 0.35294117647058826 | 0.8235294117647058 | 0.7058823529411764 | 0.6470588235294118 |
| F3 | 0.46153846153846156 | 0.7692307692307693 | 0.7692307692307693 | 0.7692307692307693 |
| F4 | 0.46153846153846156 | 0.7692307692307693 | 0.7692307692307693 | 0.7692307692307693 |
| F5 | 0.35294117647058826 | 0.8235294117647058 | 0.7058823529411764 | 0.6470588235294118 |
| F6 | 0.46218487394957986 | 0.8403361344537814 | 0.8403361344537814 | 0.7521008403361344 |

Meaningful differences in this sample:

- F1, F3, and F4 show P1 = P2 = P3, each above P0. On those families, adding raw content or redacted content did not raise coverage above P3.
- F2 and F5 show a spread: P1 highest, then P2, then P3, then P0. Those families are the retrieval-canary designs. Content retention and redaction move the score; P3 remains above P0.
- F6 shows P1 = P2, both above P3, and P3 above P0. Redaction did not reduce family coverage relative to full content; dropping content did.

These family values describe this frozen suite. They are not population rates.

## Canary exposure

Exposure is export-only exact matching of registered canaries. It is not forensic coverage, not a breach-probability estimate, and not a claim about unregistered secrets.

Eligible-denominator facts that appear in the aggregate:

- `zero_canary_executions` = 18. Per the protocol, those executions are not applicable to exposure means.
- The aggregate does not publish a separate eligible-planting count or eligible-execution count for this 24-execution sample. That standalone denominator is unavailable.
- Recorded rates are `aggregates.exposure_by_policy`.
- Recorded execution counts with any exposure are `aggregates.executions_with_any_exposure`.
- Recorded location counts are `aggregates.exposure_by_location`.

| Policy | Exposure rate | Executions with any exposure |
| --- | --- | --- |
| P0 | 0.0 | 0 |
| P1 | 1.0 | 6 |
| P2 | 0.0 | 0 |
| P3 | 0.0 | 0 |

Location counts are empty for P0, P2, and P3. For P1 they are C1 = 2 and C3 = 4. No other C1–C7 location counts appear in the aggregate for this sample.

P1’s exposure rate of 1.0 means every eligible registered canary that the exposure grader scored for those executions appeared as an exact match in the P1 export. P0, P2, and P3 had no registered exact-match canary in the defined export boundary.

Zero exposure does not prove zero real-world privacy risk. It means no registered exact-match canary appeared in the defined export boundary.

## Copying observations

FS16 measures observable copying into tool arguments. OC1 measures observable copying from the first retrieval to the last model output. Both are reconstruction facts. They are not proof that retrieved or untrusted content caused later behavior.

Values are copied exactly from `fs16_tool_argument_copying` and `oc1_retrieval_to_final_output`. Applicability is 10 executions for each item.

### FS16 — retrieval token in tool arguments

| Policy | Applicable | Credit | Copy observed (`yes`) | No copy observed (`no`) | Missing evidence |
| --- | --- | --- | --- | --- | --- |
| P0 | 10 | 0 | 0 | 0 | 10 |
| P1 | 10 | 10 | 0 | 10 | 0 |
| P2 | 10 | 6 | 0 | 6 | 4 |
| P3 | 10 | 0 | 0 | 0 | 10 |

Where the export made both locations readable, no copy was observed (P1: 10; P2: 6). P0 and P3 had missing evidence for all 10 applicable executions. P2 had missing evidence for 4. No policy recorded `yes`.

### OC1 — retrieval token in the last model output

| Policy | Applicable | Credit | Copy observed (`yes`) | No copy observed (`no`) | Missing evidence |
| --- | --- | --- | --- | --- | --- |
| P0 | 10 | 0 | 0 | 0 | 10 |
| P1 | 10 | 10 | 9 | 1 | 0 |
| P2 | 10 | 6 | 5 | 1 | 4 |
| P3 | 10 | 0 | 0 | 0 | 10 |

Where the export made both locations readable, copy was observed on P1 for 9 executions and not observed for 1; on P2, copy was observed for 5 and not observed for 1, with missing evidence for 4. P0 and P3 had missing evidence for all 10 applicable executions.

These counts describe what the exports made observable. They do not say that retrieval caused the later output or the later tool request.

## Paired case/control observations

`paired_case_control_differences` records case coverage minus control coverage for each pair and policy. The 96 exports remain paired, not independent.

On P0, P1, and P3, every recorded pair has `case_minus_control` = 0.0.

On P2, these pairs also have `case_minus_control` = 0.0: F1C, F1D, F3C, F3D, F4C, F4D, F6C, and F6D.

The only non-zero case/control coverage differences in the aggregate are these P2 pairs:

| Pair | Policy | Case coverage | Control coverage | Case minus control |
| --- | --- | --- | --- | --- |
| F2C | P2 | 0.5882352941176471 | 0.8235294117647058 | -0.23529411764705876 |
| F2D | P2 | 0.5882352941176471 | 0.8235294117647058 | -0.23529411764705876 |
| F5C | P2 | 0.5882352941176471 | 0.8235294117647058 | -0.23529411764705876 |
| F5D | P2 | 0.5882352941176471 | 0.8235294117647058 | -0.23529411764705876 |

F2 and F5 are the retrieval-canary families. The observed P2 case scores are lower than their matched controls by -0.23529411764705876. That pattern is consistent with shared redaction removing registered tokens from case content fields while leaving the no-plant controls readable. It is a paired descriptive observation, not a significance result and not a claim that the retrieved token caused later model behavior.

Paired policy differences (`paired_policy_differences`) are within the same execution. Every recorded execution has a positive `p3_minus_p0`. The recorded values are 0.3076923076923077, 0.2857142857142857, or 0.29411764705882354. Recorded `p1_minus_p0` values are 0.3076923076923077, 0.2857142857142857, or 0.4705882352941176. The larger P1−P0 gaps (0.4705882352941176) appear on F2C, F2D, F5C, F5D, and F6D. This report does not convert those paired differences into a winner score.

## Operational interpretation

The following points are interpretation. Each is tied to an observed aggregate pattern. None is a recommendation that one policy must be chosen.

**Metadata-only telemetry can reconstruct most operational sequence, and none of the security or content checklist.** P0 operational coverage is 0.9315068493150684, while P0 security and content coverage are both 0.0. Overall P0 coverage is 0.4346046110751993. Practitioners who keep only request, model, tool, status, and topology fields should expect to answer “what ran, in what order, and with what status,” not “what text moved” or “what trust/privilege enum was set.”

**Content retention adds complete content-fact reconstruction in this sample, and it is the only policy that exposed registered canaries.** P1 content coverage is 1.0, P1 overall coverage is 0.8065072182719241, P1 exposure is 1.0, and P1 executions with any exposure are 6 (C1 = 2, C3 = 4). If the operational need is exact tool arguments, retrieved excerpts, model-output excerpts, or copy observations, P1 supplied them here. The privacy cost in this sample is exact-match leakage of every eligible registered canary.

**Shared redaction preserved substantial content reconstruction and removed registered-canary exposure.** P2 content coverage is 0.8297872340425532 versus P1 1.0 and P0/P3 0.0. P2 exposure is 0.0. P2 overall coverage is 0.7672915319974143. Redaction did not make P2 identical to either drop-content policy or full-content policy. The only case/control coverage gaps in the study are the P2 F2C, F2D, F5C, and F5D pairs at -0.23529411764705876, which is the place this suite shows redaction changing reconstructability between a planted case and its control.

**Security enums and detector events add the security category that content policies do not fully supply.** P3 security coverage is 1.0 versus 0.2727272727272727 on P1/P2 and 0.0 on P0. P3 content coverage remains 0.0 and P3 exposure remains 0.0. P3 overall coverage is 0.7329778065072183, above P0 and below P1/P2. In this sample, P3 is the policy that answers trust, privilege, denial reason, and detector-fired questions without retaining raw content. It does not reconstruct FS16 or OC1 (missing evidence on all 10 applicable executions).

**Status codes can stand in for an authorization conclusion when security enums are dropped.** P0 retains `status` and `status_code` and drops `security.authz_decision`. P0 operational coverage is still 0.9315068493150684, and the protocol’s FS6 rule may use status codes `401`/`403` → denied and `200` → allowed when the security decision field is absent. P0 security coverage is nevertheless 0.0, because FS8–FS11 require security enums or detector events. Practitioners should not treat a high operational score as proof that authorization basis was retained. A status code can duplicate the allow/deny conclusion and still leave privilege class, trust class, and denial reason missing.

**Privacy exposure and forensic utility should be evaluated on separate axes.** P1 has the highest coverage and the only non-zero exposure. P0, P2, and P3 all have exposure 0.0 and three different coverage values: 0.4346046110751993, 0.7672915319974143, and 0.7329778065072183. Combining those into one score would hide that P2 and P3 reached different reconstructability with the same recorded exposure rate. Zero registered-canary exposure is not a claim of zero real-world privacy risk.

Copy observations reinforce the same split. Full content made FS16 and OC1 decidable (P1 credit = 10 for both). Drop-content policies made them missing. Redaction recorded credit = 6 and missing = 4. FS16 showed no copy observed wherever it was decidable. OC1 showed copy observed (`yes` = 9) and no copy observed (`no` = 1) on P1, and copy observed (`yes` = 5) and no copy observed (`no` = 1) on P2, with missing = 4. Those are export-visible reconstruction facts, not influence findings.

## Limitations

- One pinned model snapshot: `gpt-4o-mini-2024-07-18`.
- Twenty-four frozen executions, replayed through four policies, producing 96 paired exports. This is a designed suite, not a random sample.
- The application router and tool environment are deterministic local simulations with no external side effects.
- Exposure uses exact-match registered canaries only. Unregistered secrets, transformed encodings, and out-of-grammar values are outside the metric.
- FS16 and OC1 record observable copying. They do not measure causal influence of retrieved or untrusted content on later behavior.
- The study evaluates local observability exports. It does not use a production OTLP collector or an observability SaaS backend.
- Analysis is descriptive. No statistical significance, confidence interval, or population inference is claimed. The protocol’s exploratory bootstrap is not reported in this aggregate.
- Retained-field behavior depends on the frozen P0–P3 allowlists and pattern-library v1. A different redaction library or security-enum set would be a different study.
- The study evaluates observability exports under those policies. It does not measure overall system security, attack prevention, model safety, policy compliance, or production incident outcomes.
- Applicability and realized tool/retrieval paths are those of this live capture. They are not the scripted validation suite and not the earlier feasibility sample.
- Zero exposure means no registered exact-match canary appeared in the defined export boundary. It does not prove zero real-world privacy risk.
- The aggregate does not publish per-fact numerators, a standalone eligible-canary count, or scripted-subset coverage. Those comparisons are unavailable here rather than inferred.

## RSAC article direction

### 1. Proposed article thesis

A single live capture, replayed through four published retention allowlists, shows that forensic reconstructability and registered-canary exposure move independently. Full-content telemetry reconstructed every applicable content fact in this sample and was the only policy that leaked registered canaries; metadata-only, redacted, and security-structured exports had zero registered-canary exposure and recovered different operational, security, and content subsets.

### 2. Three possible titles

- Coverage and Exposure Are Different Questions: Four GenAI Telemetry Policies After One Live Capture
- What Metadata, Redaction, and Security Enums Each Reconstruct in LLM Incident Telemetry
- Do Not Pick a Winner: Paired Evidence on GenAI Observability Retention

### 3. Five key practitioner takeaways

1. Score reconstructability and export exposure separately. In this sample P1 had both the highest coverage (0.8065072182719241) and the only non-zero exposure (1.0).
2. Metadata-only telemetry still answered most operational questions (P0 operational coverage 0.9315068493150684) and answered no security or content questions (both 0.0).
3. Shared redaction removed registered-canary exposure (P2 = 0.0) while keeping content coverage at 0.8297872340425532, not 0.0 and not 1.0.
4. Security enums plus detector events raised security coverage to 1.0 on P3 without restoring content facts (content 0.0) and without registered-canary exposure (0.0).
5. Observable copying is policy-visible only when both locations are retained. FS16 showed no copy observed on every decidable export; OC1 showed copy observed (`yes` = 9) on P1. Neither result is a causal-influence finding.

### 4. Claims that are supported

- The live capture completed: 24 realized executions, 96 realized exports, 0 failed runs, 0 unresolved credited evidence pointers.
- The paid capture was performed once on `gpt-4o-mini-2024-07-18` and replayed from a clean commit; dirty and clean replays were identical on exports, extractions, and results.
- Forensic coverage in this sample was 0.4346046110751993 (P0), 0.8065072182719241 (P1), 0.7672915319974143 (P2), and 0.7329778065072183 (P3).
- Category coverage followed the published allowlists: P0 high operational / zero security / zero content; P1 complete operational and content / partial security; P2 complete operational / partial security / partial content; P3 complete operational and security / zero content.
- Registered-canary exposure was 0.0 on P0, P2, and P3, and 1.0 on P1, with 6 P1 executions showing any exposure at C1 = 2 and C3 = 4. Eighteen executions were zero-canary.
- FS16 recorded no copy observed wherever evidence was present; OC1 recorded copy observed on 9 P1 executions and 5 P2 executions.
- Case/control coverage differed only under P2 for pairs F2C, F2D, F5C, and F5D, each by -0.23529411764705876.
- Every recorded execution had P3 coverage above P0. P3 was not identical to P0 and was not the highest-coverage policy.

### 5. Claims that must not be made

- That any policy is universally best, safest, or required.
- That P3 must differ from P0 in every future suite, or that a P0–P3 tie would have been a failed study.
- That zero registered-canary exposure equals zero real-world privacy risk.
- That retrieved or untrusted content caused, influenced, or made the model take a later step.
- That the study measured attack prevention, model safety, policy compliance, or production incident outcomes.
- That the 96 exports are 96 independent observations, or that any difference is statistically significant.
- That scripted validation, mocked validation, or the earlier feasibility replay is part of this full-study sample.
- That status codes fully replace security enums for authorization forensics.
- That exact-match canary results generalize to arbitrary secrets, encodings, or other models.

### 6. Recommended chart list

Use only aggregate fields. Keep coverage and exposure on separate visual encodings; do not plot a combined winner score.

1. Forensic coverage by policy — `aggregates.coverage_by_policy` (P0–P3).
2. Canary exposure by policy — `aggregates.exposure_by_policy`, with a paired annotation of `aggregates.executions_with_any_exposure`.
3. Coverage-versus-exposure scatter — one point per policy using those two fields only, with no third composite axis.
4. Coverage by evidence category — `aggregates.coverage_by_category` grouped by operational, security, and content.
5. Coverage by scenario family — `aggregates.coverage_by_family` for F1–F6.
6. P1 exposure by origin location — `aggregates.exposure_by_location` C1 = 2 and C3 = 4; show the empty P0, P2, and P3 location maps as empty rather than inferred counts for other locations.
7. FS16 yes / no / missing by policy — `fs16_tool_argument_copying.by_policy`.
8. OC1 yes / no / missing by policy — `oc1_retrieval_to_final_output.by_policy`.
9. Case minus control by pair and policy — `paired_case_control_differences`, highlighting the non-zero P2 cells.

Do not chart scripted-subset means. That object is empty in this aggregate.
