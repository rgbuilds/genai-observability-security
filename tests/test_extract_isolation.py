import ast
from pathlib import Path

from genai_observability.grading.extract import extract_forensic_answers
from genai_observability.grading.questions import QUESTION_IDS
from tests.helpers import export_from_spans, minimal_span

EXTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "genai_observability"
    / "grading"
    / "extract.py"
)


def test_extract_module_does_not_import_references_or_paths() -> None:
    tree = ast.parse(EXTRACT_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert all("references" not in name for name in imported)
    assert all("evaluate" not in name for name in imported)
    assert all("exposure" not in name for name in imported)
    assert all(name != "pathlib" and not name.startswith("pathlib.") for name in imported)
    assert all("paths" not in name.split(".") for name in imported)


def test_extractor_does_not_read_the_filesystem(monkeypatch) -> None:
    def reject(*_args, **_kwargs):
        raise AssertionError("extractor read the filesystem")

    monkeypatch.setattr(Path, "read_text", reject)
    monkeypatch.setattr(Path, "read_bytes", reject)
    export = export_from_spans(minimal_span())
    extraction = extract_forensic_answers(export, QUESTION_IDS)
    assert [fact.question_id for fact in extraction.facts] == list(QUESTION_IDS)


def test_extractor_signature_does_not_accept_manifests() -> None:
    names = extract_forensic_answers.__code__.co_varnames[: extract_forensic_answers.__code__.co_argcount]
    assert names == ("export", "question_ids")
