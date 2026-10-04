import re
from functools import lru_cache
from typing import Literal

from pydantic import Field

from genai_observability.paths import PATTERN_LIBRARY_DIR
from genai_observability.schemas.enums import DetectorCategory
from genai_observability.schemas.span import _StrictModel


class CanaryGrammarRule(_StrictModel):
    pattern: str = Field(min_length=1)
    match: Literal["substring"]
    case_sensitive: bool
    match_class: Literal["canary_grammar"]
    detector_id: str
    category: DetectorCategory
    replacement: str


class SecretKeyRule(_StrictModel):
    names: list[str] = Field(min_length=1)
    normalize: list[Literal["lowercase", "hyphen_to_underscore"]]
    match: Literal["exact_or_underscore_suffix"]
    match_class: Literal["secret_key"]
    detector_id: str
    category: DetectorCategory
    replacement: str


class PatternLibrary(_StrictModel):
    schema_version: Literal["pattern_library.v1"]
    library_id: str
    library_version: str
    payload_fields: list[str]
    canary_grammar: CanaryGrammarRule
    secret_keys: SecretKeyRule
    precedence: list[str]
    pii_rules: list[str]
    propagation_detector: Literal["reserved"]

    def canary_regex(self) -> re.Pattern[str]:
        flags = 0 if self.canary_grammar.case_sensitive else re.IGNORECASE
        return re.compile(self.canary_grammar.pattern, flags)

    def normalize_key(self, key: str) -> str:
        text = key
        if "lowercase" in self.secret_keys.normalize:
            text = text.lower()
        if "hyphen_to_underscore" in self.secret_keys.normalize:
            text = text.replace("-", "_")
        return text

    def is_secret_key(self, key: str) -> bool:
        normalized = self.normalize_key(key)
        names = set(self.secret_keys.names)
        if normalized in names:
            return True
        return any(normalized.endswith(f"_{name}") for name in names)


@lru_cache(maxsize=8)
def load_pattern_library(library_version: str = "1") -> PatternLibrary:
    path = PATTERN_LIBRARY_DIR / f"pattern_library.v{library_version}.json"
    return PatternLibrary.model_validate_json(path.read_text(encoding="utf-8"))
