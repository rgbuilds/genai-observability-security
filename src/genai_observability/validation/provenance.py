"""Run identity: git metadata plus hashes of configuration and source trees."""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from genai_observability import __version__
from genai_observability.paths import (
    FIXTURE_DIR,
    PACKAGE_ROOT,
    PATTERN_LIBRARY_DIR,
    POLICY_ALLOWLIST_DIR,
    REFERENCE_ANSWER_DIR,
    REFERENCE_CANARY_DIR,
    REPO_ROOT,
)
from genai_observability.serialization import sha256_hex

UTC = timezone.utc


def _git(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *command],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def hash_paths(paths: list[Path]) -> dict[str, Any]:
    files: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        files[path.relative_to(REPO_ROOT).as_posix()] = sha256_hex(path.read_bytes())
    combined = sha256_hex(
        "\n".join(f"{name}={digest}" for name, digest in files.items()).encode("utf-8")
    )
    return {"files": files, "combined": combined}


def collect_tree_hashes() -> dict[str, Any]:
    configuration = hash_paths(
        [*POLICY_ALLOWLIST_DIR.glob("*.json"), *PATTERN_LIBRARY_DIR.glob("*.json")]
    )
    references = hash_paths(
        [
            *sorted(FIXTURE_DIR.glob("*.json")),
            *sorted(REFERENCE_CANARY_DIR.glob("*.json")),
            *sorted(REFERENCE_ANSWER_DIR.glob("*.json")),
        ]
    )
    sources = hash_paths(sorted(PACKAGE_ROOT.rglob("*.py")))
    return {
        "configuration_hashes": configuration,
        "reference_hashes": references,
        "source_hashes": sources,
    }


def collect_provenance() -> dict[str, Any]:
    packages = {}
    for name in ("pydantic", "pytest"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    status = _git(["status", "--porcelain"])
    return {
        "utc_time": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "mac_ver": platform.mac_ver()[0],
        },
        "package_version": __version__,
        "dependencies": packages,
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_describe": _git(["describe", "--always", "--dirty"]),
        "git_status": status,
        "git_dirty": bool(status),
        "canonical_schema": "canonical_event_stream.v1",
        "export_schema": "telemetry_export.v1",
        "policy_version": "1",
        "pattern_library": "pattern_library.v1",
        "fixture_root": str(FIXTURE_DIR),
        **collect_tree_hashes(),
    }
