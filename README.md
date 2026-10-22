# GenAI telemetry privacy and forensic utility

This repository contains the protocol, implementation, tests, and sanitized
research artifacts for an experiment comparing the forensic utility and
plaintext exposure of four GenAI telemetry-retention policies.

Raw captures and other text-bearing research artifacts remain in the
gitignored `private/` tree and are not published.

## Repository guide

- [EXPERIMENT_CONTRACT.md](EXPERIMENT_CONTRACT.md) defines the research and
  scoring boundaries.
- [FULL_STUDY_PROTOCOL.md](FULL_STUDY_PROTOCOL.md) records the scenario matrix,
  policy comparison, capture rules, and analysis plan.
- [FULL_STUDY_PROPOSAL.md](FULL_STUDY_PROPOSAL.md) describes the study design
  and the decision it was intended to support.
- [FULL_STUDY_RESULTS.md](FULL_STUDY_RESULTS.md) contains the privacy-safe
  aggregate results, integrity checks, and limitations.
- [ARCHITECTURE.md](ARCHITECTURE.md) explains the schemas, detectors,
  transforms, grading, capture, replay, and trust boundaries.
- [validation/reporting/full-study-aggregate-input.json](validation/reporting/full-study-aggregate-input.json)
  is the sanitized numerical source for the aggregate report.
- `policies/` contains the versioned allowlists and detector pattern library.
- `src/genai_observability/` contains the Python implementation.
- `fixtures/` and `references/` contain deterministic validation inputs and
  manifests.
- `tests/` contains the automated validation suite.

The project requires Python 3.12 or newer. Run the local test suite with:

```bash
.venv/bin/python -m pytest
```
