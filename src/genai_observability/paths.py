from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
# src/genai_observability -> src -> repository root
REPO_ROOT = PACKAGE_ROOT.parents[1]
POLICY_ALLOWLIST_DIR = REPO_ROOT / "policies" / "allowlists"
PATTERN_LIBRARY_DIR = REPO_ROOT / "policies" / "pattern_libraries"
FIXTURE_DIR = REPO_ROOT / "fixtures" / "canonical"
REFERENCE_CANARY_DIR = REPO_ROOT / "references" / "canaries"
REFERENCE_ANSWER_DIR = REPO_ROOT / "references" / "answers"
VALIDATION_DIR = REPO_ROOT / "validation" / "implementation-pilot"
VALIDATION_RUNS_DIR = VALIDATION_DIR / "runs"
