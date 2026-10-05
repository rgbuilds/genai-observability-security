# Full-study proposal: GenAI telemetry privacy and forensic utility

Status: **proposal for researcher review**. No full-suite scenarios, graders, captures, or runs are authorized by this document. Proposed on 2026-10-04 from `RESEARCH_FEASIBILITY_ASSESSMENT.md` and the earlier contract. The six captured streams remain a feasibility sample and are not full-study observations.

## 1. Decision this proposal supports

The feasibility gate says **proceed toward a full-study proposal**, not that the larger study should run. In six captured streams, the frozen R1–R7 checklist gave P0 and P3 the same 11/37 coverage, P2 27/37, and P1 37/37. P1 exposed four of four eligible canaries; P0, P2, and P3 exposed none. These are descriptive observations for one model, principal, note collection, and prompt set. R4 measured retrieval-to-tool-argument co-occurrence and missed copying into final replies; prospective OC1 addresses that different question.

The full study should answer: **which incident facts can be reconstructed under each unchanged telemetry policy, and what sensitive content does that policy retain?** A P0–P3 tie is a valid result. The original `EXPERIMENT_CONTRACT.md` section 7 criterion requiring P3 to occupy a distinct position was a pilot screening rule, not a requirement to manufacture a policy gap. Before the full-study freeze, amend the contract to record the feasibility decision and explicitly allow ties, reversals, and mixed results.

## 2. Design and unit of analysis

Keep P0–P3, pattern library v1, the canonical-event schema, and the capture-once/replay comparison unchanged unless a separately approved, versioned amendment is made **before** the full run. Do not add P4 or retune P3 using the feasibility scores.

Proposed suite: **24 scenario templates**, four in each F1–F6 family, with one matched control per template: **48 registered executions**. The policy transform runs on each canonical stream once for each of four policies, yielding at most **192 paired policy exports**. Scenario/template and control counts must remain separate in every report. The family of a captured execution records the *intended* prompt design; report what actually happened separately. Do not relabel, drop, or recapture an inconvenient model response to preserve a desired family balance.

Proposed composition within each family: two scripted pairs and two capture-once pairs. This gives 24 scripted and 24 captured executions. This mix is a **design proposal**, not permission to call a model. A captured pair can differ from its intended path; both executions stay in the denominator where their questions apply. If captured paths prove too inconsistent for the study question, review the design before expanding or replacing any stream.

The paired comparison unit is the **execution**: one canonical stream through all four policies. A matched case/control pair is a cluster for scenario design and uncertainty analysis. Facts, spans, and repeated transforms are not independent samples. Mock tools have no external effects. No production data or observability SaaS is used.

## 3. Scenario matrix to register before implementation

| Family | Four case templates should cover | Matched control principle |
| --- | --- | --- |
| F1 sensitive user input | Different legitimate tasks and user-input shapes, including a value not needed to name the operation | Same task and tool path without the sensitive value |
| F2 sensitive retrieved context | Distinct retrieval sources and document-body placements | Same source/path with a benign body |
| F3 unauthorized tool attempt | Same privileged tool with denied requests under different principal contexts | Same tool and target class under an authorized grant; do not switch to a read tool |
| F4 authorized high-risk action | Valid grant and completed privileged action, including a case with no canary | Same privileged tool under a denied or lower-privilege context; interpret authorization and execution separately |
| F5 untrusted content and later action | Retrieval/tool-result content followed by a model output or tool request; include copy and no-copy variants | Same topology and tools with the registered token absent or not repeated. Score observation, never causal influence |
| F6 sensitive model output | Output-only and output-after-retrieval paths | Same task/path with a benign output |

The exact 24 templates, paired prompts, ground truth, canaries, and applicable questions are **not specified yet**. Register them in a separate scenario manifest and have the researcher approve them before fixture creation or live capture. Allocate planted canaries across all C1–C7 origin locations at least once, publish the count at each location, and preserve origin attribution when a canary propagates. Do not claim that one token per location makes the location-level rates generalizable. Use unique library-v1 synthetic canaries inside eligible payload fields; do not plant them in fields retained only to force a policy failure. Include benign lookalikes only if their role and P2 false-positive rule are registered prospectively.

Capture prompts, order, system instructions, tool schemas, note bodies, principal grants, router decisions, request ceiling, token bound, dollar ceiling, and failure/exclusion rules must be frozen in a new full-study capture protocol. Do not reuse the six feasibility streams as new observations. One model snapshot and one provider should be chosen before the first request. No model shopping or reruns by policy. A no-tool or unexpected response is retained, with applicability determined from its canonical stream.

## 4. Investigator questions and scoring freeze

Define the final question list **before** completing the scenario suite and without choosing questions to make P3 win. Use practitioner incident tasks as the organizing principle. The list should include:

- **Operational sequence:** initiating request, model/tool identity, retrieval provenance, authorization outcome, and parent/child relationships.
- **Security boundary:** input trust, privileged action, authorization basis or denial reason, and whether an observed detector fired. The answer must come from operational evidence, not scenario labels or a planted `incident_type` field.
- **Content needed for containment:** exact tool arguments, affected resource, retrieved excerpt, model output, and where a registered value appeared.
- **Prospective OC1:** whether the registered retrieval token appears in the **last model output**. Source is first `content.retrieved`; destination is the last model span with `content.output`. This is separate from frozen R4, which checks tool arguments when a tool ran.

The final checklist may reuse Q and R questions, but must have a new version identifier and an explicit mapping to earlier definitions. Do not pool Q1–Q15, R1–R7, and new checklist percentages. For each fact, record practitioner rationale, applicability, accepted evidence paths under any policy, answer vocabulary, ambiguity handling, and a deterministic extractor/evaluator rule. Allow raw content or structured fields to answer the **same** fact when both are valid evidence. Do not infer privilege merely from a tool name or mark a detector event as a breach. OC1 and R4 `no` require both registered locations readable; a dropped or redacted location yields `missing`. Neither co-occurrence nor topology proves influence.

The researcher reviews the question list and scenario manifests before code or capture. Freeze graders before any full-study policy results are inspected. Extractors receive only exports and public question definitions; private answer keys and canary inventories enter at evaluation. Credit requires a correct answer and evidence pointer into the serialized export. Tests must cover partial, ambiguous, contradictory, and multiple-tool traces.

## 5. Outcomes and analysis

Primary axes stay separate:

1. **Canary exposure rate:** distinct eligible planted canaries found by exact substring scan of the policy export / eligible canaries registered for that execution. Zero-canary executions are N/A, excluded from exposure-rate means and counted separately. Report C1–C7 exposure and the number of scenarios with any exposed canary. This metric measures the synthetic grammar, not breach probability.
2. **Forensic coverage:** correctly reconstructed applicable facts / applicable facts for each execution and policy. Report scenario-level values, family and fact-category coverage, and raw numerators/denominators. Applicability is execution-level, identical across policies.

Report paired policy differences within the same execution, with scripted and captured subsets shown separately and a combined descriptive view only if their mixing rule was frozen beforehand. The main figure is exposure versus coverage, with one point per policy and separate subset labels. Further figures show coverage by family and exposure by C1–C7 location. Keep payload bytes, correlation completeness, redaction counts, and processing time secondary. Do not create a weighted winner score.

Proposed uncertainty method: cluster bootstrap **matched pairs** within each family and source type, resampling two scripted and two captured pairs per family with replacement for each replicate, using a fixed recorded seed and 10,000 replicates. Compute intervals for paired differences in execution-level coverage and exposure, reporting the number of eligible exposure executions in each draw. A family with no eligible exposure execution cannot contribute an exposure mean in that draw; predefine whether to omit that draw or report the interval unavailable before freezing. These intervals describe sensitivity to this designed suite, not a population estimate or proof of statistical significance. With only two pairs in each family/source stratum, intervals may be unstable; report paired differences without inferential claims if so.

Pre-register missing/invalid run handling: a capture that fails before a usable canonical stream is a failed attempt, not a replaced observation; a transform or grader error after capture is a policy-run failure, not a reason to recapture. Report planned and realized counts, all exclusions, and reasons. Do not silently replace unfavorable cases.

## 6. Provenance, privacy, and reproducibility

Freeze and commit the scenario definitions, public questions, policy allowlists, pattern library, extractor/evaluator code, analysis plan, and configuration before running from a clean commit. Record the commit and SHA-256 hashes of each config, fixture, capture, manifest, and export; capture time, macOS/Python/package versions, model snapshot, request counts, and estimated and actual billed cost if available. Use a unique run directory and preserve failed-run records.

Keep captured canonical streams, captured answer manifests, exported content, and detailed extraction/result files under gitignored `private/`. Public repository artifacts may include synthetic scripted fixtures and an aggregate report after privacy review. Do not put captured excerpts or credentials in committed manifests, logs, charts, or prose. The exposed API key from the feasibility capture must be revoked; a future approved capture uses a new key supplied through a secret channel and never printed.

The full study needs a separate capture budget and authorization. The earlier six-prompt, 12-request, $5 ceiling applied only to feasibility capture and does not carry forward. Verify the chosen model's current availability, parameters, and pricing against official documentation immediately before any live full-study run.

## 7. Gates and approvals

1. **Design review:** approve this proposal's scope, case/control accounting, scripted/captured mix, and treatment of unexpected model behavior.
2. **Question and scenario review:** approve the final checklist, evidence rules (including OC1), 24 template/control pairs, canary inventory, capture protocol, analysis rule, privacy plan, and budget. Record an amendment to `EXPERIMENT_CONTRACT.md` reconciling its P3-distinct pilot criterion with the observed P0–P3 tie and the new full-study decision rule.
3. **Implementation review:** build and test the full-suite fixtures, graders, runner, and mock capture path. Verify that private results stay private and that code cannot read answer keys during extraction. No live calls at this gate.
4. **Freeze review:** commit the approved materials; record hashes and clean Git status. Inspect the exact prepared prompt list and cost ceiling. Authorize live capture separately if desired.
5. **Execution and analysis:** capture each approved stream once, replay P0–P3, produce audit tables and figures, then review interpretations and any RSAC claims against the evidence pack.

This proposal stops at gate 1. It does **not** approve the 24–30 scenario suite, a new model budget, another API request, or a publication claim.

## 8. Decisions for researcher review

- Is 24 templates plus 24 matched controls the right size, with four templates per family?
- Should half the pairs be scripted and half captured? If not, what fixed mix should be registered before capture?
- Which investigator facts are essential and which are secondary? The final list must allow P0–P3 ties.
- Should OC1 be a primary content-reconstruction fact in the new checklist or a separate secondary analysis?
- Which synthetic artifacts may be committed, and what aggregate captured results may be released?
- What full-study model/provider, request/token/dollar cap, and capture window should be approved at the later freeze gate?
- Should the proposed family-stratified bootstrap be used, or should the study report paired descriptive differences only?

Record decisions and a versioned contract amendment before creating the full-suite scenarios or making another model call.
