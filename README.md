# GenAI telemetry privacy and forensic utility

This repository contains a paired study of what security investigators can
reconstruct from GenAI application telemetry under four retention policies,
and whether those exports retain registered synthetic canaries as plaintext.
The study treats forensic coverage and plaintext exposure as separate
outcomes: answering more incident questions does not erase an exposure, and
zero registered-canary exposure does not prove that telemetry is generally
private.

## Research question

GenAI applications can emit prompts, retrieved context, model output, tool
arguments, authorization decisions, detector events, status, and trace
topology. Retaining all of it may help an investigation while also creating a
new store of sensitive content. Retaining too little may prevent responders
from reconstructing what happened.

The experiment asks:

> Which operational, security, and content facts remain reconstructable under
> different telemetry-retention policies, and which registered canaries remain
> visible in the resulting exports?

It does not measure attack prevention, model safety, policy compliance, causal
influence, or production incident outcomes.

## Study design

The reported live study used a deterministic local note application around a
pinned GPT-4o Mini snapshot (`gpt-4o-mini-2024-07-18`). The application could
retrieve mock notes, expose `get_note` and privileged `delete_account` tools,
apply local authorization decisions, and record a canonical event stream.
The tools had no external side effects.

The live capture produced 24 executions arranged as 12 matched case/control
pairs. Each pair used the same basic task, available tools, and intended trace
structure. A case contained the condition under study, such as a registered
canary in user or retrieved content or a particular authorization outcome. Its
control removed the canary or applied the opposite grant to the same privileged
tool. Pairing limited unrelated differences; it was not used to infer that the
condition caused the model's response.

Each captured execution was replayed through all four policies, producing 96
paired exports. The model was not called again for each policy, so differences
between P0-P3 reflect their published field allowlists rather than four
different model responses.

The frozen checklist contains 17 facts: FS1-FS16 and OC1. A fact received
credit only when the extracted answer was correct and its evidence pointer
resolved inside the serialized export. A separate export-only scan searched
for exact plaintext matches of registered canaries.

## Retention policies

- **P0 — metadata-only baseline.** Keeps request identity, timing, status, and
  topology while dropping raw content, detector events, and structured
  security fields.
- **P1 — full-content tracing.** Adds raw content, raw authorization context,
  retrieval identifiers, and detector events.
- **P2 — redacted-content tracing.** Applies the shared detector and redaction
  patterns to P1-like content while retaining detector events and surrounding
  text.
- **P3 — security-structured telemetry.** Drops raw content and raw
  authorization context while keeping trust, privilege, authorization, denial,
  detector fields, and opaque or hashed retrieval identifiers.

The runtime first computes one full canonical stream. Policies differ only in
what their versioned allowlists retain.

## Results

Mean forensic coverage over the same 24 live executions was:

- **P0:** 43.5%
- **P1:** 80.7%
- **P2:** 76.7%
- **P3:** 73.3%

Canary exposure is reported separately. Six executions carried a registered
canary in an eligible input or retrieval location; the other 18 were not
applicable to this measure. P1 exposed registered canaries in all six eligible
executions. P0, P2, and P3 exposed none of the registered canaries in their
exports.

The category results show why one aggregate number is insufficient:

- P0 reconstructed most operational sequence but no scored security or
  content facts.
- P1 reconstructed all scored operational and content facts, but it was also
  the only policy with registered-canary exposure.
- P2 preserved all scored operational facts and 83% of content facts with no
  registered-canary exposure, while reconstructing 27.3% of security facts.
- P3 reconstructed all scored operational and security facts with no raw
  content reconstruction and no registered-canary exposure.

The live capture also made content movement observable. For the ten P1
executions where both the first retrieval and last model output were retained
as plaintext, retrieved text appeared in the final output in nine. This is an
observable copy result, not evidence that the retrieval caused or influenced
the response.

See [FULL_STUDY_RESULTS.md](FULL_STUDY_RESULTS.md) for the privacy-safe
aggregate, denominators, paired results, integrity checks, and limitations.
The machine-readable numerical source is
[validation/reporting/full-study-aggregate-input.json](validation/reporting/full-study-aggregate-input.json).

## Repository guide

- [EXPERIMENT_CONTRACT.md](EXPERIMENT_CONTRACT.md) defines the research and
  scoring boundaries.
- [FULL_STUDY_PROTOCOL.md](FULL_STUDY_PROTOCOL.md) freezes the scenario matrix,
  case/control design, checklist, capture rules, and analysis plan.
- [FULL_STUDY_PROPOSAL.md](FULL_STUDY_PROPOSAL.md) explains the decision the
  full study was designed to support.
- [FULL_STUDY_RESULTS.md](FULL_STUDY_RESULTS.md) reports the completed live
  study using sanitized aggregate data.
- [ARCHITECTURE.md](ARCHITECTURE.md) describes schemas, detectors, transforms,
  grading, capture, replay, and trust boundaries.
- `policies/` contains versioned allowlists and the detector/redaction pattern
  library.
- `src/genai_observability/` contains the Python implementation.
- `fixtures/` and `references/` contain deterministic validation streams,
  answer manifests, and canary inventories.
- `tests/` covers schemas, canonical serialization, transforms, grading,
  capture safeguards, immutable replay, privacy boundaries, and aggregation.

## Local setup and validation

Python 3.12 or newer is required.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

The mocked full-study runner exercises all 48 registered scripted and mocked
case/control executions and compares 192 policy exports with their retention
forecasts:

```bash
.venv/bin/python -m genai_observability.full_study.runner
```

That command performs local implementation validation. It does not call a
model API and its output is not live-model research evidence.

## Privacy and reproducibility boundary

Raw live captures, retrieved text, model replies, tool arguments, private
answer excerpts, and per-export research artifacts are stored under the
gitignored `private/` tree and are not published. They can reproduce sensitive
text, so this repository publishes the protocol, implementation, deterministic
fixtures, sanitized aggregate, integrity summaries, and source hashes instead.

Consequently, a public reader can inspect the design, run the complete test
suite and mocked validation, and verify the reported numbers against the
sanitized aggregate. The public repository does not contain the raw capture
needed to independently regenerate the live aggregate from its first step.

Live capture is guarded separately and is not required for local validation.
Do not treat the local mocked runner or retention forecasts as additional live
observations.

## Limitations

- The live evidence uses one pinned model snapshot and one designed scenario
  suite rather than a random sample.
- The application router and tools are deterministic local simulations.
- Exposure is exact matching of registered canaries; it does not cover every
  secret, encoding, transformation, or privacy risk.
- Textual co-occurrence and parent/child topology do not establish causal
  influence.
- Results depend on the frozen P0-P3 allowlists and pattern library.
- The study evaluates local telemetry exports rather than a production OTLP
  collector or observability backend.
- The descriptive results do not establish statistical significance or a
  universally best policy.
