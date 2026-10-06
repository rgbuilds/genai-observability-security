import ast
from pathlib import Path

from genai_observability.full_study.extract import extract_full_study_answers
from genai_observability.full_study.questions import FULL_STUDY_QUESTION_IDS
from tests.helpers import export_from_spans, minimal_span

EXTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "genai_observability"
    / "full_study"
    / "extract.py"
)


def test_full_study_extract_does_not_import_references_or_paths() -> None:
    tree = ast.parse(EXTRACT_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert all("references" not in name for name in imported)
    assert all("evaluate" not in name for name in imported)
    assert all("select" not in name for name in imported)
    assert all("scenarios" not in name for name in imported)
    assert all(name != "pathlib" and not name.startswith("pathlib.") for name in imported)
    assert all("paths" not in name.split(".") for name in imported)


def test_full_study_extractor_does_not_read_the_filesystem(monkeypatch) -> None:
    def reject(*_args, **_kwargs):
        raise AssertionError("full-study extractor read the filesystem")

    monkeypatch.setattr(Path, "read_text", reject)
    monkeypatch.setattr(Path, "read_bytes", reject)
    export = export_from_spans(minimal_span())
    extraction = extract_full_study_answers(export)
    assert [fact.question_id for fact in extraction.facts] == list(FULL_STUDY_QUESTION_IDS)


def test_full_study_extractor_signature_does_not_accept_manifests() -> None:
    names = extract_full_study_answers.__code__.co_varnames[: extract_full_study_answers.__code__.co_argcount]
    assert names == ("export",)
