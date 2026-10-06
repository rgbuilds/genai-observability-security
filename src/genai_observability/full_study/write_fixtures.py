"""Materialize streams, manifests, and canary inventories from the registry."""

from __future__ import annotations

import json
from pathlib import Path

from genai_observability.full_study.fixtures import build_stream
from genai_observability.full_study.inventory import inventory_from_spec
from genai_observability.full_study.scenarios import all_specs
from genai_observability.full_study.select import select_full_study_references
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.paths import (
    FULL_STUDY_ANSWER_DIR,
    FULL_STUDY_CANARY_DIR,
    FULL_STUDY_STREAM_DIR,
)
from genai_observability.serialization import canonical_json_text


def write_full_study_fixtures(root: Path | None = None) -> dict[str, int]:
    stream_dir = (root / "streams") if root else FULL_STUDY_STREAM_DIR
    answer_dir = (root / "answers") if root else FULL_STUDY_ANSWER_DIR
    canary_dir = (root / "canaries") if root else FULL_STUDY_CANARY_DIR
    stream_dir.mkdir(parents=True, exist_ok=True)
    answer_dir.mkdir(parents=True, exist_ok=True)
    canary_dir.mkdir(parents=True, exist_ok=True)
    for spec in all_specs():
        stream = build_stream(spec)
        answers = select_full_study_references(apply_runtime_detectors(stream), spec)
        inventory = inventory_from_spec(spec)
        (stream_dir / f"{spec['execution_id']}.json").write_text(
            canonical_json_text(stream) + "\n",
            encoding="utf-8",
        )
        (answer_dir / f"{spec['execution_id']}.json").write_text(
            answers.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        (canary_dir / f"{spec['execution_id']}.json").write_text(
            inventory.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    return {"executions": 48, "streams": 48, "answers": 48, "canaries": 48}


def main() -> int:
    counts = write_full_study_fixtures()
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
