# Research-feasibility assessment (captured set U)

Status: **proceed toward a full-study proposal.** This is not authorization of the 24–30 scenario study. R1–R7 scores from the offline replay are unchanged. Live capture stays disabled.

Reviewed replay: `private/research-replay/20261005T034345Z` (role `offline-captured-replay`). Source capture: `private/captures/20261005T015238Z`. SHA-256 of each source file matches the replay `summary.json`. No file in either directory was rewritten for this assessment. Exports, answer manifests, and per-question result files stay under `private/`. This report contains only aggregates.

Set U is one capture of the six frozen prompts, replayed through unchanged P0–P3. Pairs S and T are not re-scored here. Their earlier retention-forecast match (`LOCAL_READINESS_REPORT.md`) remains grader validation, not research evidence.

## Decision

Section 11 is met for a proposal, not for a larger run.

The replay is interpretable. Metadata questions R5 and R7 are correct on every policy that can see an edge or a tool status. Content questions R1–R4 and R6 are correct where the field is readable, and `missing` or unmatched where the policy drops or redacts it. The capture kept prompt order, used 11 of 12 requests, spent far under the dollar ceiling, left no prompt unattempted, and was not replaced after grading. Exposure is reported separately from coverage.

The same section does not require a P0–P3 gap on R5 or R7. The P0–P3 tie on this R-list is expected. It is explained below.

What this gate does not do: authorize another paid capture, change R4, or treat the six prompts as a policy ranking.

## Frozen U scores

Applicability is execution-level. `cap-u5` has no retrieval and no tool, so only R6 and R7 apply (2 facts). The other five prompts apply all seven facts. Denominator: **37** applicable facts per policy. Non-applicable cells are excluded.

| Policy | Applicable facts correct | Canaries exposed / eligible |
| --- | ---: | ---: |
| P0 | 11/37 | 0/4 |
| P1 | 37/37 | 4/4 |
| P2 | 27/37 | 0/4 |
| P3 | 11/37 | 0/4 |

Eligible canaries are the four prompts whose retrieval body contains a library-v1 canary (`cap-u1`, `cap-u2`, `cap-u3`, `cap-u6`). `cap-u4` and `cap-u5` have an empty exposure denominator.

Correct facts by prompt:

| Prompt | Applicable | P0 | P1 | P2 | P3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| cap-u1 | 7 | 2 | 7 | 4 | 2 |
| cap-u2 | 7 | 2 | 7 | 4 | 2 |
| cap-u3 | 7 | 2 | 7 | 5 | 2 |
| cap-u4 | 7 | 2 | 7 | 7 | 2 |
| cap-u5 | 2 | 1 | 2 | 2 | 1 |
| cap-u6 | 7 | 2 | 7 | 5 | 2 |

Per-question credit, counting only applicable cells:

| Question | Applicable prompts | P0 | P1 | P2 | P3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1 tool args | 5 | 0 | 5 | 5 | 0 |
| R2 resource id | 5 | 0 | 5 | 5 | 0 |
| R3 retrieval excerpt | 5 | 0 | 5 | 1 | 0 |
| R4 co-occurrence | 5 | 0 | 5 | 1 | 0 |
| R5 allow/deny | 5 | 5 | 5 | 5 | 5 |
| R6 output excerpt | 6 | 0 | 6 | 4 | 0 |
| R7 edges | 6 | 6 | 6 | 6 | 6 |

P2’s single R3 and R4 credits are `cap-u4`, the prompt whose registered token is not a canary. P2’s two R6 misses are `cap-u1` and `cap-u2`.

### R4, left as recorded

Every applicable prompt registered expected answer **`no`**. The registered token is the first library-v1 canary in the retrieval body, or the 32-character retrieval excerpt when no canary is present (`cap-u4`).

| Prompt | P0 | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| cap-u1, cap-u2, cap-u3, cap-u6 | missing | `no` (credit 1) | missing | missing |
| cap-u4 | missing | `no` (credit 1) | `no` (credit 1) | missing |
| cap-u5 | N/A | N/A | N/A | N/A |

On P1, both locations were readable and the token was absent from tool arguments, so the outcome is `no`. On P0 and P3 the content locations are dropped, so the outcome is `missing` and credit is 0. On P2, canary redaction makes a location unreadable for the four canary prompts, so the outcome is `missing`, not `no`. `cap-u4` has no canary, both locations stay readable, and P2 also scores `no`.

That is the frozen rule in section 4.4. Drop and redaction were not scored as “no copy.”

R4’s second location, when any tool span exists, is the tool-argument JSON. All five tool prompts had a tool span. The registered token does not appear in those arguments on any of the six streams. R4 therefore cannot see note text that the model repeated in a final reply. `cap-u1`, `cap-u2`, and `cap-u4` do repeat the retrieval body in that reply. `cap-u3` and `cap-u6` do not. Those reply facts were not given an R4 yes/no. They are not a reason to edit the stored R4 column.

`cap-u6` asked the model to place the first word of the retrieval body into `get_note`. R4’s token is the canary, not that word. The argument does not contain the canary, so R4 stays `no` on P1. That score is co-occurrence of the registered token. It is not a finding that the instruction failed, and it is not an influence score.

R6 does not fill this gap. Its excerpt is taken from the model output itself (first canary in that output, otherwise 32 characters). On P1, credit means the output field survived. It does not mean a retrieval token was compared with the reply. On P2, `cap-u1` and `cap-u2` keep an output field but lose credit because redaction removes the canary excerpt. That is a retention effect on the reply, recorded as credit 0 with status `answered`, which is a different rule from R4’s `missing`.

## What the six captures show about P0–P3

One model snapshot, one principal, six prompts. Five prompts called exactly one tool. One (`cap-u5`) called none and had no retrieval. None were truncated. Each tool prompt used two HTTP requests; the no-tool prompt used one.

**P1** retains the fields R1–R4 and R6 read. Tool arguments and resource ids match on all five tool prompts, including the model-chosen argument on `cap-u6`. Retrieval excerpts match. R4 can be answered, and the answer is `no` for every applicable prompt. Output excerpts match, so coverage is 37/37. The same policy exposes 4/4 eligible canaries. Coverage and exposure are not combined into a winner.

**P2** keeps non-canary tool arguments, so R1 and R2 match on all five tool prompts. It redacts in-grammar canaries. Where the registered excerpt is a canary, R3 is extracted but does not match (credit 0, status `answered`) and R4 is `missing`. That is four prompts. The two replies that contain the canary lose R6 the same way. The prompt with no canary (`cap-u4`) matches P1 on all seven facts. No secret-key redaction appeared in model JSON beyond the canary grammar. Exposure is 0/4.

**P0 and P3** match each other on every prompt and every R-question: 11/37, exposure 0/4. Both answer R5 and R7. Both miss R1–R4 and R6.

**Applicability.** One of six prompts makes R1, R2, and R5 N/A, and R3 and R4 N/A, because the model followed the no-tool prompt. The stream was kept. Empty applicability is not what happened. Section 10’s capture lessons that this run can support are: tool use was common; model-chosen arguments were complete enough for R1 and R2 after P1 and P2; a canary was not copied into tool arguments (R4 `no` on P1); P2 redacted canaries and did not need a secret-key hit to change R3, R4, and R6.

## Why P0 and P3 tied

P3’s export is not the same document as P0’s. On these streams P3 adds `detector_events` on spans, retrieval metadata without the retrieved text, and tool `security.authz_decision`, `denial_reason`, and `privilege_class`. P0 has none of those.

R1–R7 do not read them, except R5, which prefers `security.authz_decision` when it is present and otherwise maps tool `status_code` (`401|403` → denied, `200` → allowed). On this replay:

- P0, P1, and P2 credit R5 from `status_code`.
- P3 credits R5 from `security.authz_decision`.
- The allow/deny value is the same, so the credit is the same. The one denial (`cap-u3`, 403) is recovered by both routes.

R7 credits `parent_span_id` edges, which both policies keep. R1, R2, R3, R4, and R6 read content or `authz.resource`. Both policies omit those, so those questions are `missing` together.

The tie is the section 4 rule that an R-question must be one a practitioner would ask even if `security.*` did not exist. P3’s extra security fields have no R-question of their own. Equal scores are not a claim that the exports are identical, and they are not a failed contrast.

## Proposed question for a future run (not scored)

Name: **OC1**. It is not R1–R7. It is not applied to `20261005T034345Z`. Scoring it on these exports would be a retrospective change. Register it in a later protocol revision before any new capture, then score only that later capture.

**Question.** Does the privately registered retrieval token occur in the model’s final reply?

**Source.** `content.retrieved` on the first retrieval span. Same field as R4 location 1.

**Destination.** `content.output` on the last model span that has output text. Not `content.tool_args`. Not “tool arguments if a tool ran, otherwise output,” which is R4’s rule. On these six streams the tool-call model span stored no output text, so the only output span is the final reply. The destination rule still names the last output so a later model that writes prose before a tool call is not graded on that earlier text.

**Ground truth.** Selected from the canonical stream only, never from a policy export. Token rule matches R4: the first library-v1 canary in the source text, otherwise the first 32 characters of the source. Expected `yes` when that token is a substring of both the source and the destination on the canonical stream. Expected `no` when both fields exist on the canonical stream and the token is absent from the destination. No token is registered when OC1 is N/A.

If that rule is ever applied to a new capture with the same shapes as these six, the canonical labels would be `yes` for `cap-u1`, `cap-u2`, and `cap-u4`, and `no` for `cap-u3` and `cap-u6`. That sentence is a specification check against streams already stored. It is not an OC1 score.

**Applicability.** Retrieval occurred, a model span with `content.output` exists, and a token is registered. A tool call does not change the destination and does not make OC1 N/A. No retrieval, or no model output, means N/A rather than 0. A policy that drops the field does not make the question N/A.

**Yes / no / missing.** Same discipline as section 4.4.

| Export observability | Token in source | Token in destination | OC1 answer | Score if applicable |
| --- | --- | --- | --- | --- |
| Both locations present and readable | yes | yes | `yes` | 1 if expected `yes` |
| Both locations present and readable | yes | no | `no` | 1 if expected `no` |
| Both locations present and readable | no | any | `no` | 1 if expected `no` |
| Either location dropped | — | — | `missing` | 0 |
| Either location redacted so the token cannot be read | — | — | `missing` | 0 |
| Extractor reports `missing` for either location | — | — | `missing` | 0 |

`no` means the token was not observed in the destination only when both locations are readable. A redaction marker is not proof the token was absent. OC1 is co-occurrence of a retrieval token and a final reply. It is not a claim that the retrieval caused the reply. It does not replace R4, and R4’s tool-argument results stay as published.

## Section 11 checklist

| Criterion | This record |
| --- | --- |
| R5 and R7 usable, including when every policy succeeds | Held on U. R5 is 5/5 and R7 is 6/6 on P0–P3. Pair S and pair T were forecast checks earlier, not evidence. |
| R1–R4 and R6 interpretable, including `missing` on drop or redaction | Held. P1 answers them. P0/P3 miss the content questions. P2 redacts canaries and still answers non-canary args. R4 `no` is used only on readable pairs of locations. |
| Pair S isolates allow vs deny | Not re-opened. Earlier forecast match stands as grader validation. |
| Pair T uses section 4.4 without influence language | Not re-opened. This U report does not call R4 or R7 influence. |
| Capture order, cap, ceiling, no replacement; stable replay hashes | Held. Six prompts in order, 11 requests, no unattempted prompts, no truncation, source hashes unchanged. |
| Exposure separate from coverage | Held. P1 is 37/37 and 4/4 exposed. Those are two columns. |
| Redesign triggers (excerpt leak into extraction, R4 drop scored as `no`, protocol breach, uninterpretable U) | Not observed in this replay. |
| Stop triggers (U adds nothing, or the work is a model benchmark) | Not met. U distinguishes no-tool applicability, recoverable arguments, canary-free tool arguments, and canary redaction. |

## Limitations

- Six prompts, one pinned snapshot, one router principal. Rates are descriptions of this capture, not population estimates.
- R1–R7 cannot rank P0 against P3. A later study that needs that contrast has to pre-register a question a practitioner would ask without `security.*`, or accept the tie.
- Reply repetition of retrieval text is outside R4 whenever a tool ran, which was five of these six prompts. OC1 is the pre-registered place for that fact. It is not a correction to this replay.
- R6 on P1 is largely a retention check of text taken from the output. High R6 credit is not evidence of copy-from-retrieval.
- P2 credit 0 on R3 and on some R6 cells means the private canary excerpt is no longer a substring after redaction. It is not a second, independent measurement of model behavior.
- S/T forecast matches are still not research results. This U block is one capture observation.
- No further experiment was run. The live-capture command remains opt-in and default-off. The API key that was printed in a terminal during capture must stay revoked and is not used here.
