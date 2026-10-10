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
RESEARCH_FIXTURE_DIR = REPO_ROOT / "fixtures" / "research"
RESEARCH_ANSWER_DIR = REPO_ROOT / "references" / "research" / "answers"
RESEARCH_RETENTION_RUNS_DIR = REPO_ROOT / "validation" / "research-retention" / "runs"
CAPTURE_REPLAY_RUNS_DIR = REPO_ROOT / "validation" / "capture-replay" / "runs"
PRIVATE_DIR = REPO_ROOT / "private"
PRIVATE_CAPTURE_DIR = PRIVATE_DIR / "captures"
PRIVATE_LOCAL_READINESS_DIR = PRIVATE_DIR / "local-readiness"
PRIVATE_FULL_STUDY_CAPTURE_DIR = PRIVATE_DIR / "full-study-captures"
FULL_STUDY_FIXTURE_DIR = REPO_ROOT / "fixtures" / "full-study"
FULL_STUDY_STREAM_DIR = FULL_STUDY_FIXTURE_DIR / "streams"
FULL_STUDY_ANSWER_DIR = REPO_ROOT / "references" / "full-study" / "answers"
FULL_STUDY_CANARY_DIR = REPO_ROOT / "references" / "full-study" / "canaries"
FULL_STUDY_LIVE_SOURCE_FREEZE_PATH = REPO_ROOT / "references" / "full-study" / "live_source_freeze.json"
FULL_STUDY_RUNS_DIR = REPO_ROOT / "validation" / "full-study" / "runs"
