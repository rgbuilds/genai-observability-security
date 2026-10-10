import json
import stat
from datetime import date
from pathlib import Path

import pytest

from genai_observability.full_study.inventory import inventory_from_realized_stream
from genai_observability.full_study.live_adapter import (
    FullStudyCaptureAdapter,
    artifact_hashes,
    capture_configuration_hashes,
    capture_input_hashes,
    frozen_source_hashes,
    full_study_budget,
    load_expected_source_hash,
    validate_official_doc_check,
    verify_source_hashes,
)
from genai_observability.full_study.live_capture import main
from genai_observability.paths import FULL_STUDY_LIVE_SOURCE_FREEZE_PATH, PACKAGE_ROOT, REPO_ROOT
from genai_observability.full_study.protocol import (
    CHECKLIST_VERSION,
    LIVE_ENV_FLAG,
    LIVE_FULL_STUDY_AUTHORIZED,
    OFFICIAL_DOC_CHECK,
    PROPOSED_DOLLAR_CEILING_USD,
    PROPOSED_PINNED_MODEL,
    PROPOSED_REQUEST_CAP,
)
from genai_observability.full_study.scenarios import (
    CAPTURE_ONCE_EXECUTION_IDS,
    FULL_STUDY_EXECUTION_IDS,
    capture_once_specs,
    spec_by_id,
)
from genai_observability.full_study.select import select_full_study_references
from genai_observability.full_study.surface import execute_full_study_tool
from genai_observability.research.capture import (
    CaptureRun,
    LiveCaptureNotAuthorized,
    LiveOpenAIClient,
    ScriptedCompletionsClient,
    TransportError,
)
from genai_observability.research.clock import DeterministicClock
from genai_observability.research.costing import CaptureBudget
from genai_observability.runtime import apply_runtime_detectors
from genai_observability.schemas.enums import SpanKind


def _stop(text: str) -> dict:
    return {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 5},
    }


def _tools(*calls: tuple[str, object], finish: str = "tool_calls") -> dict:
    tool_calls = []
    for index, (name, arguments) in enumerate(calls, start=1):
        raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
        tool_calls.append(
            {
                "id": f"call_{index}",
                "type": "function",
                "function": {"name": name, "arguments": raw},
            }
        )
    return {
        "choices": [
            {
                "finish_reason": finish,
                "message": {"role": "assistant", "content": None, "tool_calls": tool_calls},
            }
        ],
        "usage": {"prompt_tokens": 24, "completion_tokens": 8},
    }


def _length(text: str) -> dict:
    return {
        "choices": [{"finish_reason": "length", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 512},
    }


def _adapter(responses: list, budget: CaptureBudget | None = None) -> FullStudyCaptureAdapter:
    return FullStudyCaptureAdapter(
        ScriptedCompletionsClient(responses),
        budget=budget or full_study_budget(),
        clock=DeterministicClock(),
    )


def test_live_flag_and_command_refuse_by_default(monkeypatch) -> None:
    assert LIVE_FULL_STUDY_AUTHORIZED is False
    assert len(CAPTURE_ONCE_EXECUTION_IDS) == 24
    assert len(FULL_STUDY_EXECUTION_IDS) == 48
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    with pytest.raises(SystemExit, match="Full-study live capture is off"):
        main()
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENAI_API_KEY is missing"):
        main()
    with pytest.raises(LiveCaptureNotAuthorized):
        FullStudyCaptureAdapter(LiveOpenAIClient())


def test_official_doc_record_does_not_change_the_pin() -> None:
    assert OFFICIAL_DOC_CHECK["snapshot"] == PROPOSED_PINNED_MODEL
    assert OFFICIAL_DOC_CHECK["input_usd_per_million"] == 0.15
    assert OFFICIAL_DOC_CHECK["output_usd_per_million"] == 0.60
    assert OFFICIAL_DOC_CHECK["live_recheck_required"] is True
    assert OFFICIAL_DOC_CHECK["gate5_prep_http"] is False
    assert PROPOSED_REQUEST_CAP == 80
    assert PROPOSED_DOLLAR_CEILING_USD == 15.00
    feasibility = CaptureBudget()
    assert feasibility.request_cap == 12
    assert feasibility.dollar_ceiling_usd == 5.00
    live = full_study_budget()
    assert live.request_cap == 80
    assert live.dollar_ceiling_usd == 15.00
    assert live.input_token_bound == 4096


def test_completed_official_check_must_be_recent() -> None:
    completed = {**OFFICIAL_DOC_CHECK, "live_recheck_required": False}
    with pytest.raises(LiveCaptureNotAuthorized, match="stale"):
        validate_official_doc_check(completed, today=date(2026, 10, 9))
    fresh = {**completed, "checked_on": "2026-10-08"}
    assert validate_official_doc_check(fresh, today=date(2026, 10, 9)) == date(2026, 10, 8)
    future = {**completed, "checked_on": "2026-10-10"}
    with pytest.raises(LiveCaptureNotAuthorized, match="stale"):
        validate_official_doc_check(future, today=date(2026, 10, 9))


def test_direct_live_adapter_send_cannot_bypass_official_gate(monkeypatch) -> None:
    sent: list[dict] = []
    client = LiveOpenAIClient(
        "sk-test",
        authorized=True,
        sender=lambda _key, request: sent.append(request) or _stop("unexpected"),
    )
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    with pytest.raises(LiveCaptureNotAuthorized, match="recheck is still required"):
        adapter.capture_spec(spec_by_id()["fs-f6c-ctrl"])
    assert sent == []
    assert adapter.budget.requests_used == 0


def test_direct_live_adapter_send_requires_freeze_and_persistence(monkeypatch) -> None:
    from genai_observability.full_study import live_adapter

    sent: list[dict] = []
    verified = {"source": 0}
    client = LiveOpenAIClient(
        "sk-test",
        authorized=True,
        sender=lambda _key, request: sent.append(request) or _stop("unexpected"),
    )
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.setattr(live_adapter, "validate_official_doc_check", lambda: date(2026, 10, 9))

    def verified_source() -> None:
        verified["source"] += 1

    monkeypatch.setattr(live_adapter, "verify_source_hashes", verified_source)
    with pytest.raises(LiveCaptureNotAuthorized, match="must use run"):
        adapter.capture_spec(spec_by_id()["fs-f6c-ctrl"])
    assert verified["source"] == 1
    assert sent == []
    assert adapter.budget.requests_used == 0


def test_live_send_rejects_mutated_or_custom_budget_before_client(monkeypatch) -> None:
    sent: list[dict] = []
    client = LiveOpenAIClient(
        "sk-test",
        authorized=True,
        sender=lambda _key, request: sent.append(request) or _stop("unexpected"),
    )
    budget = full_study_budget()
    budget.request_cap = PROPOSED_REQUEST_CAP + 1
    adapter = FullStudyCaptureAdapter(client, budget=budget, clock=DeterministicClock())
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    with pytest.raises(LiveCaptureNotAuthorized, match="frozen 80-request"):
        adapter.capture_spec(spec_by_id()["fs-f6c-ctrl"])
    assert sent == []
    assert adapter.budget.requests_used == 0

    counter_budget = full_study_budget()
    counter_adapter = FullStudyCaptureAdapter(
        client,
        budget=counter_budget,
        clock=DeterministicClock(),
    )
    counter_budget.requests_used = 1
    with pytest.raises(LiveCaptureNotAuthorized, match="counters changed"):
        counter_adapter.capture_spec(spec_by_id()["fs-f6c-ctrl"])
    assert sent == []


def test_live_response_model_must_match_pinned_snapshot(monkeypatch) -> None:
    mismatch = {
        **_stop("response"),
        "model": "gpt-4o-mini-future-snapshot",
    }
    client = LiveOpenAIClient(
        "sk-test",
        authorized=True,
        sender=lambda _key, _request: mismatch,
    )
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    monkeypatch.setattr(adapter, "_refuse_unless_live_send_ready", lambda: None)
    record = adapter.capture_spec(spec_by_id()["fs-f6c-ctrl"])
    assert record.stop_reason == "malformed_response"
    assert record.failures == [
        {"kind": "malformed_response", "detail": "reported_model_mismatch"}
    ]
    assert all(span.kind is not SpanKind.MODEL for span in record.stream.spans)


def test_no_tool_realized_applicability() -> None:
    spec = spec_by_id()["fs-f2c-case"]
    adapter = _adapter([_stop("acknowledged.")])
    record = adapter.capture_spec(spec)
    assert record.attempted is True
    assert record.stream is not None
    assert all(span.kind is not SpanKind.TOOL for span in record.stream.spans)
    processed = apply_runtime_detectors(record.stream)
    answers = select_full_study_references(processed, spec)
    assert answers.question("FS12").applicable is False
    assert answers.question("FS5").applicable is False
    assert answers.question("OC1").applicable is True
    assert answers.question("OC1").answer == "no"
    inventory = inventory_from_realized_stream(spec, processed)
    assert inventory.eligible_canaries
    assert inventory.eligible_canaries[0].token == spec["canaries"][0]["token"]
    assert inventory.eligible_canaries[0].location == "C3"


def test_case_and_control_note_bodies_are_execution_scoped() -> None:
    case = spec_by_id()["fs-f2c-case"]
    control = spec_by_id()["fs-f2c-ctrl"]
    case_result = execute_full_study_tool(case, "get_note", {"note_id": "note-f2c"})
    control_result = execute_full_study_tool(control, "get_note", {"note_id": "note-f2c"})
    token = case["canaries"][0]["token"]
    assert token in case_result["body"]
    assert token not in control_result["body"]
    assert case_result["body"] == case["tool_result"]["body"]
    assert control_result["body"] == control["tool_result"]["body"]
    c5_case = spec_by_id()["fs-f2b-case"]
    c5_result = execute_full_study_tool(c5_case, "get_note", {"note_id": "note-f2b"})
    assert c5_case["canaries"][0]["token"] in c5_result["body"]


def test_unexpected_tool_is_recorded_and_not_replaced() -> None:
    spec = spec_by_id()["fs-f1d-ctrl"]
    adapter = _adapter([_tools(("search_web", {"query": "x"}))])
    record = adapter.capture_spec(spec)
    assert record.stream is not None
    tool = next(span for span in record.stream.spans if span.kind is SpanKind.TOOL)
    assert tool.tool is not None
    assert tool.tool.name == "search_web"
    assert tool.content is not None
    assert tool.content.tool_result["executed"] is False
    assert tool.content.tool_result["error"] == "unknown_tool"
    assert record.failures[0]["kind"] == "unknown_tool"


def test_malformed_arguments_are_preserved() -> None:
    spec = spec_by_id()["fs-f1c-ctrl"]
    adapter = _adapter([_tools(("get_note", "{note_id"))])
    record = adapter.capture_spec(spec)
    assert record.stream is not None
    tool = next(span for span in record.stream.spans if span.kind is SpanKind.TOOL)
    assert tool.content is not None
    assert tool.content.tool_args == "{note_id"
    assert tool.content.tool_result["executed"] is False
    assert record.stop_reason == "malformed_arguments"


def test_multiple_tool_calls_in_one_message() -> None:
    spec = spec_by_id()["fs-f2c-case"]
    adapter = _adapter(
        [
            _tools(("get_note", {"note_id": "note-f2c"}), ("get_note", {"note_id": "note-f2d"})),
            _stop("both notes read"),
        ]
    )
    record = adapter.capture_spec(spec)
    assert record.stream is not None
    tools = [span for span in record.stream.spans if span.kind is SpanKind.TOOL]
    assert len(tools) == 2
    assert [span.content.tool_args["note_id"] for span in tools] == ["note-f2c", "note-f2d"]
    processed = apply_runtime_detectors(record.stream)
    answers = select_full_study_references(processed, spec)
    assert answers.question("FS12").applicable is True
    assert len(answers.question("FS12").answer) == 2


def test_truncation_keeps_partial_without_prose_followup() -> None:
    spec = spec_by_id()["fs-f6c-case"]
    client = ScriptedCompletionsClient([_length("Status par")])
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    record = adapter.capture_spec(spec)
    assert record.truncated is True
    assert record.stream is not None
    output = next(span.content.output for span in record.stream.spans if span.kind is SpanKind.MODEL)
    assert output == "Status par"
    assert len(client.calls) == 1
    inventory = inventory_from_realized_stream(spec, apply_runtime_detectors(record.stream))
    assert inventory.eligible_canaries == []


def test_truncated_tool_call_is_preserved_but_never_executed() -> None:
    spec = spec_by_id()["fs-f2c-case"]
    adapter = _adapter([_tools(("get_note", {"note_id": "note-f2c"}), finish="length")])
    record = adapter.capture_spec(spec)
    assert record.partial is True
    assert record.truncated is True
    assert record.stop_reason == "truncated"
    assert record.failures == [{"kind": "truncated_tool_calls", "preserved": True}]
    tool = next(span for span in record.stream.spans if span.kind is SpanKind.TOOL)
    assert tool.content.tool_args == json.dumps({"note_id": "note-f2c"})
    assert tool.content.tool_result["executed"] is False
    assert tool.content.tool_result["error"] == "truncated_arguments"


def test_transport_retries_count_then_keep_partial() -> None:
    spec = spec_by_id()["fs-f6c-ctrl"]
    adapter = _adapter([TransportError("boom"), TransportError("boom")])
    record = adapter.capture_spec(spec)
    assert record.attempted is True
    assert record.stop_reason == "transport_exhausted"
    assert record.requests_used == 2
    assert record.stream is not None
    assert all(span.kind is not SpanKind.MODEL for span in record.stream.spans)


def test_request_exhaustion_lists_unattempted(tmp_path: Path) -> None:
    first, second, *rest = capture_once_specs()
    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    budget = CaptureBudget(request_cap=1, dollar_ceiling_usd=15.0, input_token_bound=4096)
    adapter = FullStudyCaptureAdapter(client, budget=budget, clock=DeterministicClock())
    # Patch order by running two ids through a custom remaining loop is hard;
    # use run() which walks all 24, with cap 1.
    run = adapter.run(tmp_path)
    assert len(run.records) == 1
    assert run.records[0].attempted is True
    assert run.unattempted_prompt_ids
    assert first["execution_id"] == run.records[0].prompt_id
    assert second["execution_id"] in run.unattempted_prompt_ids
    assert (tmp_path / "captures" / f"{first['execution_id']}.json").is_file()
    unattempted = json.loads((tmp_path / "captures" / "unattempted_prompts.json").read_text())
    assert second["execution_id"] in unattempted["unattempted_prompt_ids"]
    hashes = json.loads((tmp_path / "artifact_hashes.json").read_text(encoding="utf-8"))
    assert hashes == artifact_hashes(tmp_path)
    required = {
        "provenance.json",
        "run.json",
        "captures/unattempted_prompts.json",
        f"captures/{first['execution_id']}.json",
        f"captures/{first['execution_id']}.meta.json",
        f"realized/processed/{first['execution_id']}.json",
        f"realized/answers/{first['execution_id']}.json",
        f"realized/canaries/{first['execution_id']}.json",
    }
    assert required <= set(hashes["files"])
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    for directory in (path for path in tmp_path.rglob("*") if path.is_dir()):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    for artifact in (path for path in tmp_path.rglob("*") if path.is_file()):
        assert stat.S_IMODE(artifact.stat().st_mode) == 0o600
    assert rest


def test_dollar_ceiling_refuses_before_send(tmp_path: Path) -> None:
    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    budget = CaptureBudget(request_cap=80, dollar_ceiling_usd=15.0, spent_usd=15.0)
    adapter = FullStudyCaptureAdapter(client, budget=budget, clock=DeterministicClock())
    run = adapter.run(tmp_path)
    assert run.records == []
    assert run.unattempted_prompt_ids == list(CAPTURE_ONCE_EXECUTION_IDS)
    assert client.calls == []
    assert (tmp_path / "captures" / "unattempted_prompts.json").is_file()
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    expected = load_expected_source_hash()
    observed = frozen_source_hashes()
    assert provenance["expected_source_hash"] == expected["combined"]
    assert provenance["observed_source_hashes"]["combined"] == observed["combined"]
    assert provenance["protocol_version"] == "full-study-protocol.v1"
    assert provenance["checklist_version"] == CHECKLIST_VERSION
    assert provenance["configuration_hashes"] == capture_configuration_hashes()
    assert provenance["capture_input_hashes"] == capture_input_hashes()
    assert isinstance(provenance["git_dirty"], bool)
    assert "git_commit" in provenance
    assert "git_status" in provenance
    assert FULL_STUDY_LIVE_SOURCE_FREEZE_PATH.as_posix() not in observed["files"]


def test_persistence_and_realized_derivation(tmp_path: Path) -> None:
    spec = spec_by_id()["fs-f5c-case"]
    adapter = _adapter(
        [
            _tools(("get_note", {"note_id": "note-f5c"})),
            _stop(f"The cited note says Retrieved {spec['canaries'][0]['token']}"),
        ]
    )
    adapter.output_dir = tmp_path
    record = adapter.capture_spec(spec)
    adapter.realize_record(spec, record)
    meta = json.loads((tmp_path / "captures" / f"{spec['execution_id']}.meta.json").read_text())
    assert meta["attempted"] is True
    answers = json.loads((tmp_path / "realized" / "answers" / f"{spec['execution_id']}.json").read_text())
    oc1 = next(item for item in answers["questions"] if item["id"] == "OC1")
    fs16 = next(item for item in answers["questions"] if item["id"] == "FS16")
    assert oc1["applicable"] is True
    assert oc1["answer"] == "yes"
    assert fs16["answer"] == "no"
    canaries = json.loads((tmp_path / "realized" / "canaries" / f"{spec['execution_id']}.json").read_text())
    assert canaries["eligible_canaries"][0]["location"] == "C3"


def test_live_adapter_does_not_import_http() -> None:
    import sys

    sys.modules.pop("genai_observability.research.live_http", None)
    import genai_observability.full_study.live_adapter  # noqa: F401

    assert "genai_observability.research.live_http" not in sys.modules


def test_pending_recheck_makes_zero_client_calls(monkeypatch) -> None:
    from genai_observability.full_study import live_capture

    calls = {"client": 0, "adapter": 0, "complete": 0, "run": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            calls["client"] += 1

        def complete(self, request: dict) -> dict:
            calls["complete"] += 1
            raise AssertionError("complete must not be called")

    class FakeAdapter:
        def __init__(self, *args, **kwargs) -> None:
            calls["adapter"] += 1

        def run(self, *args, **kwargs):
            calls["run"] += 1
            raise AssertionError("run must not be called")

    assert OFFICIAL_DOC_CHECK["live_recheck_required"] is True
    assert OFFICIAL_DOC_CHECK["snapshot"] == PROPOSED_PINNED_MODEL
    assert OFFICIAL_DOC_CHECK["input_usd_per_million"] == 0.15
    assert OFFICIAL_DOC_CHECK["output_usd_per_million"] == 0.60
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(live_capture, "LiveOpenAIClient", FakeClient)
    monkeypatch.setattr(live_capture, "FullStudyCaptureAdapter", FakeAdapter)
    with pytest.raises(SystemExit, match="recheck is still required"):
        live_capture.main()
    assert calls == {"client": 0, "adapter": 0, "complete": 0, "run": 0}


def test_missing_or_invalid_check_date_refuses(monkeypatch) -> None:
    from genai_observability.full_study import live_capture

    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(live_capture, "LiveOpenAIClient", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        live_capture,
        "OFFICIAL_DOC_CHECK",
        {**OFFICIAL_DOC_CHECK, "checked_on": None, "live_recheck_required": False},
    )
    with pytest.raises(SystemExit, match="check date is missing or invalid"):
        live_capture.main()
    monkeypatch.setattr(
        live_capture,
        "OFFICIAL_DOC_CHECK",
        {**OFFICIAL_DOC_CHECK, "checked_on": "2026-13-40", "live_recheck_required": False},
    )
    with pytest.raises(SystemExit, match="check date is missing or invalid"):
        live_capture.main()


def test_pricing_function_calling_and_output_limit_refuse(monkeypatch) -> None:
    from genai_observability.full_study import live_capture

    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(live_capture, "LiveOpenAIClient", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    cases = [
        ({"input_usd_per_million": 1.5}, "input_usd_per_million"),
        ({"output_usd_per_million": 6.0}, "output_usd_per_million"),
        ({"function_calling": False}, "function_calling"),
        ({"max_output_tokens": 64, "max_tokens_512_supported": True}, "max output"),
        ({"max_tokens_512_supported": False}, "max_tokens_512_supported"),
    ]
    for patch, match in cases:
        monkeypatch.setattr(
            live_capture,
            "OFFICIAL_DOC_CHECK",
            {**OFFICIAL_DOC_CHECK, "live_recheck_required": False, **patch},
        )
        with pytest.raises(SystemExit, match=match):
            live_capture.main()


def test_source_hash_verification_uses_independent_expected() -> None:
    expected = load_expected_source_hash()
    observed = frozen_source_hashes()
    assert expected["combined"] == observed["combined"]
    assert "live_source_freeze.json" not in observed["files"]
    package_sources = {
        path.relative_to(REPO_ROOT).as_posix() for path in PACKAGE_ROOT.rglob("*.py")
    }
    assert package_sources <= set(observed["files"])
    for required in (
        "policies/allowlists/p0.v1.json",
        "policies/allowlists/p3.v1.json",
        "policies/pattern_libraries/pattern_library.v1.json",
        "src/genai_observability/full_study/inventory.py",
        "src/genai_observability/full_study/questions.py",
        "src/genai_observability/full_study/select.py",
        "src/genai_observability/research/capture.py",
        "src/genai_observability/research/costing.py",
        "src/genai_observability/research/live_http.py",
        "src/genai_observability/research/protocol.py",
    ):
        assert required in observed["files"]
    verify_source_hashes()
    with pytest.raises(RuntimeError, match="source hashes"):
        verify_source_hashes({"combined": "0" * 64})
    with pytest.raises(RuntimeError, match="source hashes"):
        verify_source_hashes(expected, {"combined": "1" * 64, "files": {}})


def test_run_refuses_before_request_when_expected_hash_changes(tmp_path: Path, monkeypatch) -> None:
    from genai_observability.full_study import live_adapter

    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    monkeypatch.setattr(live_adapter, "load_expected_source_hash", lambda: {"combined": "0" * 64})
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    with pytest.raises(RuntimeError, match="source hashes"):
        adapter.run(tmp_path)
    assert client.calls == []
    assert not (tmp_path / "captures").exists()


def test_run_refuses_before_request_when_source_hash_changes(tmp_path: Path, monkeypatch) -> None:
    from genai_observability.full_study import live_adapter

    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    monkeypatch.setattr(
        live_adapter,
        "frozen_source_hashes",
        lambda: {"combined": "1" * 64, "files": {"src/genai_observability/full_study/live_adapter.py": "1" * 64}},
    )
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    with pytest.raises(RuntimeError, match="source hashes"):
        adapter.run(tmp_path)
    assert client.calls == []


def test_run_refuses_when_expected_hash_is_missing(tmp_path: Path, monkeypatch) -> None:
    from genai_observability.full_study import live_adapter

    client = ScriptedCompletionsClient([_stop("acknowledged.")])
    monkeypatch.setattr(live_adapter, "FULL_STUDY_LIVE_SOURCE_FREEZE_PATH", tmp_path / "missing.json")
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    with pytest.raises(RuntimeError, match="expected live-capture source hash is missing"):
        adapter.run(tmp_path)
    assert client.calls == []


def test_pin_mismatch_refuses_before_send(monkeypatch) -> None:
    from genai_observability.full_study import live_capture

    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(live_capture, "LiveOpenAIClient", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        live_capture,
        "OFFICIAL_DOC_CHECK",
        {**OFFICIAL_DOC_CHECK, "snapshot": "gpt-4o-mini"},
    )
    with pytest.raises(SystemExit, match="does not match"):
        live_capture.main()


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({}, "choices_missing"),
        ({"choices": []}, "choices_empty"),
        (
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "a"}},
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "b"}},
                ]
            },
            "multiple_choices",
        ),
        ({"choices": [{"finish_reason": "stop"}]}, "message_missing"),
        ({"choices": [{"finish_reason": "stop", "message": "ok"}]}, "message_not_object"),
        ({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": None}}]}, "neither_text_nor_tool_calls"),
    ],
)
def test_malformed_response_is_partial_failure(payload: dict, detail: str) -> None:
    spec = spec_by_id()["fs-f6c-ctrl"]
    client = ScriptedCompletionsClient([{**payload, "usage": {"prompt_tokens": 8, "completion_tokens": 0}}])
    adapter = FullStudyCaptureAdapter(client, clock=DeterministicClock())
    record = adapter.capture_spec(spec)
    assert record.attempted is True
    assert record.partial is True
    assert record.stop_reason == "malformed_response"
    assert record.failures[0]["kind"] == "malformed_response"
    assert record.failures[0]["detail"] == detail
    dumped = json.dumps(record.failures)
    assert "sk-" not in dumped
    assert "OPENAI_API_KEY" not in dumped
    assert all(span.kind is not SpanKind.MODEL for span in (record.stream.spans if record.stream else []))
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    ("finish_reason", "message", "detail"),
    [
        (None, {"role": "assistant", "content": "text"}, "finish_reason_missing"),
        (7, {"role": "assistant", "content": "text"}, "finish_reason_not_string"),
        ("content_filter", {"role": "assistant", "content": "partial"}, "finish_reason_content_filter"),
        ("future_reason", {"role": "assistant", "content": "text"}, "finish_reason_unknown"),
        (
            "stop",
            {
                "role": "assistant",
                "content": "text",
                "tool_calls": [{"function": {"name": "get_note", "arguments": "{}"}}],
            },
            "stop_with_tool_calls",
        ),
        ("tool_calls", {"role": "assistant", "content": "text"}, "tool_calls_without_calls"),
    ],
)
def test_finish_reason_is_validated_before_recording_or_execution(
    finish_reason: object,
    message: dict,
    detail: str,
) -> None:
    spec = spec_by_id()["fs-f2c-case"]
    payload = {
        "choices": [{"finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 2},
    }
    record = _adapter([payload]).capture_spec(spec)
    assert record.partial is True
    assert record.stop_reason == "malformed_response"
    assert record.failures == [{"kind": "malformed_response", "detail": detail}]
    assert all(span.kind not in {SpanKind.MODEL, SpanKind.TOOL} for span in record.stream.spans)


def test_nonretryable_client_error_is_persisted_without_message(tmp_path: Path) -> None:
    spec = spec_by_id()["fs-f6c-ctrl"]
    adapter = _adapter([RuntimeError("secret response body")])
    adapter.output_dir = tmp_path
    record = adapter.capture_spec(spec)
    assert record.attempted is True
    assert record.stop_reason == "capture_error"
    assert record.failures == [{"kind": "capture_error", "error_type": "RuntimeError"}]
    metadata = json.loads(
        (tmp_path / "captures" / f"{spec['execution_id']}.meta.json").read_text(encoding="utf-8")
    )
    assert metadata["failures"] == record.failures
    assert "secret response body" not in json.dumps(metadata)


def test_realization_failure_writes_final_metadata_and_unattempted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from genai_observability.full_study import live_adapter

    adapter = _adapter([_stop("acknowledged.")])
    monkeypatch.setattr(adapter, "realize_record", lambda *args: (_ for _ in ()).throw(ValueError("private")))
    monkeypatch.setattr(live_adapter, "verify_source_hashes", lambda *args: None)
    run = adapter.run(tmp_path)
    assert run.stop_reason == "realization_error"
    assert len(run.records) == 1
    assert run.records[0].failures[-1] == {
        "kind": "realization_error",
        "error_type": "ValueError",
    }
    assert len(run.unattempted_prompt_ids) == len(CAPTURE_ONCE_EXECUTION_IDS) - 1
    final = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert final["stop_reason"] == "realization_error"
    assert final["unattempted"] == run.unattempted_prompt_ids
    assert final["failure"] is None
    metadata = json.loads(
        (tmp_path / "captures" / f"{run.records[0].prompt_id}.meta.json").read_text(
            encoding="utf-8"
        )
    )
    assert "private" not in json.dumps(metadata["failures"])


def test_all_failed_captures_set_aggregate_failure_status(tmp_path: Path, monkeypatch) -> None:
    from genai_observability.full_study import live_adapter

    failures = [RuntimeError("private transport detail") for _ in CAPTURE_ONCE_EXECUTION_IDS]
    adapter = _adapter(failures)
    monkeypatch.setattr(live_adapter, "verify_source_hashes", lambda *args: None)
    run = adapter.run(tmp_path)
    assert len(run.records) == len(CAPTURE_ONCE_EXECUTION_IDS)
    assert run.failed_prompt_ids == list(CAPTURE_ONCE_EXECUTION_IDS)
    assert run.stop_reason == "completed_with_failures"
    final = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert final["failed"] == list(CAPTURE_ONCE_EXECUTION_IDS)
    assert final["stop_reason"] == "completed_with_failures"
    assert "private transport detail" not in json.dumps(final)


def test_live_cli_returns_nonzero_for_failed_run(monkeypatch) -> None:
    from genai_observability.full_study import live_capture

    failed = CaptureRun(
        failed_prompt_ids=["fs-f1c-case"],
        stop_reason="completed_with_failures",
    )
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(live_capture, "refuse_unless_official_docs_ready", lambda: None)
    monkeypatch.setattr(live_capture, "verify_source_hashes", lambda: None)
    monkeypatch.setattr(live_capture, "LiveOpenAIClient", lambda *args, **kwargs: object())

    class FakeAdapter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self) -> CaptureRun:
            return failed

    monkeypatch.setattr(live_capture, "FullStudyCaptureAdapter", FakeAdapter)
    assert live_capture.main() == 1


def test_scripted_executions_are_not_in_live_order() -> None:
    live_ids = set(CAPTURE_ONCE_EXECUTION_IDS)
    scripted = [item for item in FULL_STUDY_EXECUTION_IDS if item not in live_ids]
    assert len(scripted) == 24
    assert all(item.endswith("case") or item.endswith("ctrl") for item in scripted)
    assert "fs-f1a-case" in scripted
    assert "fs-f1c-case" in live_ids
