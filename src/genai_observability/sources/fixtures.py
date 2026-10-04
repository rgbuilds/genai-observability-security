from pathlib import Path

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import SourceKind


class FixtureSource:
    """Deterministic JSON fixtures. Files are `{scenario_id}.json` under `root`."""

    source_kind = SourceKind.FIXTURE

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def load(self, scenario_id: str) -> CanonicalEventStream:
        path = self.root / f"{scenario_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"canonical fixture not found: {path}")
        stream = CanonicalEventStream.model_validate_json(path.read_text(encoding="utf-8"))
        if stream.scenario_id != scenario_id:
            raise ValueError(
                f"fixture {path} has scenario_id={stream.scenario_id!r}, expected {scenario_id!r}"
            )
        return stream
