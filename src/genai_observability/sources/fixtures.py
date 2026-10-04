from pathlib import Path

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import DetectorPass, SourceKind


class FixtureSource:
    """Deterministic JSON fixtures. Files are `{scenario_id}.json` under `root`.

    Loading always yields `detector_pass=not_run`. A fixture file cannot mark
    the stream completed and thereby skip `apply_runtime_detectors`.
    """

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
        return stream.model_copy(update={"detector_pass": DetectorPass.NOT_RUN})
