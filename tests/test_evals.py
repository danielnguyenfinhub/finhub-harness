"""Slice 11 proof tests: evals runner and string-match verifier (synthetic data only)."""

import json
from pathlib import Path
from typing import Any

import pytest

from master_finhub.evals.runner import (
    Benchmark,
    SuiteReport,
    load_benchmark,
    main,
    run_case,
    run_suite,
)
from master_finhub.evals.verifiers import VERIFIERS, contains
from master_finhub.runtime.loop import AssistantMessage, Message, ToolCall, ToolSpec
from master_finhub.sandbox.workspace import Workspace

PASS = Path(__file__).parent.parent / "src/master_finhub/evals/benchmarks/echo_pass.json"
FAIL = Path(__file__).parent / "fixtures/evals/echo_fail.json"


def make_bench(tmp_path: Path, **over: Any) -> Benchmark:
    ground = {
        "files": [],
        "should_contain": ["42"],
        "should_not_contain": ["Error:"],
        "eval": {"type": "contains"},
    }
    data: dict[str, Any] = {"name": "t", "task": "echo 42", "max_steps": 4, "cutoff_s": 30}
    data["ground"] = {**ground, **over.pop("ground", {})}
    data.update(over)
    p = tmp_path / "b.json"
    p.write_text(json.dumps(data))
    return load_benchmark(p)


def test_contains_all_present() -> None:
    g = contains("the answer is 42", {"should_contain": ["answer", "42"], "should_not_contain": []})
    assert (g.passed, g.failed, g.total, g.pass_rate) == (2, 0, 2, 1.0)


def test_contains_forbidden_present() -> None:
    g = contains("42 Error: boom", {"should_contain": ["42"], "should_not_contain": ["Error:"]})
    assert (g.passed, g.failed, g.total, g.pass_rate) == (1, 1, 2, 0.5)
    bad = [e for e in g.expectations if not e.passed]
    assert len(bad) == 1 and "Error:" in bad[0].text


def test_contains_case_insensitive() -> None:
    ground = {"should_contain": ["HELLO"], "should_not_contain": [], "case_sensitive": False}
    assert contains("hello", ground).pass_rate == 1.0
    assert contains("hello", {**ground, "case_sensitive": True}).pass_rate == 0.0


def test_contains_empty_ground_scores_zero() -> None:
    assert contains("x", {}).pass_rate == 0.0


def test_evidence_is_bounded() -> None:
    g = contains("a" * 5000, {"should_contain": ["zzz"]})
    assert len(g.expectations[0].evidence) <= 200


def test_pass_benchmark_passes() -> None:
    r = run_case(load_benchmark(PASS))
    assert r.passed is True and r.score == 1.0 and r.error is None and not r.timed_out


def test_fail_benchmark_fails() -> None:
    r = run_case(load_benchmark(FAIL))
    assert r.passed is False and r.score < 1.0 and r.grading is not None
    bad = [e for e in r.grading.expectations if not e.passed]
    assert bad[0].text == 'output contains "42"'
    assert "41" in bad[0].evidence


class Boom:
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        raise RuntimeError("model down")


def test_crash_becomes_failed_result(tmp_path: Path) -> None:
    r = run_case(make_bench(tmp_path), llm_factory=Boom)
    assert r.passed is False and r.score == 0.0
    assert r.error is not None and r.error.startswith("RuntimeError")


class Looper:
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        return AssistantMessage("", [ToolCall("c", "echo", {"text": "42"})])


def test_step_limit_is_failure(tmp_path: Path) -> None:
    r = run_case(make_bench(tmp_path), llm_factory=Looper)
    assert r.passed is False and r.error is not None and "AgentLoopError" in r.error


def test_cutoff_marks_timed_out(tmp_path: Path) -> None:
    r = run_case(make_bench(tmp_path, cutoff_s=0))
    assert r.timed_out is True and r.passed is False


def test_unknown_eval_type_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="eval"):
        make_bench(tmp_path, ground={"eval": {"type": "llm"}})
    assert set(VERIFIERS) == {"contains"}


@pytest.mark.parametrize("field", ["name", "task", "max_steps", "cutoff_s", "ground"])
def test_missing_field_rejected(tmp_path: Path, field: str) -> None:
    data = json.loads(PASS.read_text())
    del data[field]
    p = tmp_path / "b.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=field):
        load_benchmark(p)


def test_file_entry_outside_workspace_fails(tmp_path: Path) -> None:
    r = run_case(make_bench(tmp_path, ground={"files": ["../../etc/passwd"]}))
    assert r.passed is False and r.error is not None and "SandboxDenied" in r.error


class WriteTool:
    spec = ToolSpec("write_out", "write out.txt", {"type": "object", "properties": {}})

    def __init__(self, ws: Workspace) -> None:
        self.ws = ws

    def run(self, arguments: dict[str, Any]) -> str:
        self.ws.write_text("out.txt", "hello file")
        return "written"


class WriterLLM:
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        if messages[-1].role == "tool":
            return AssistantMessage("done")
        return AssistantMessage("", [ToolCall("w", "write_out", {})])


def test_tools_get_case_workspace(tmp_path: Path) -> None:
    seen: list[Workspace] = []

    def tools(ws: Workspace) -> list[Any]:
        seen.append(ws)
        return [WriteTool(ws)]

    b = make_bench(tmp_path, ground={"files": ["out.txt"], "should_contain": ["hello file"]})
    r = run_case(b, llm_factory=WriterLLM, tools_factory=tools)
    assert r.passed is True
    assert len(seen) == 1 and not seen[0].root.exists()  # fresh temp dir, cleaned up


def test_agent_never_sees_ground(tmp_path: Path) -> None:
    secret = "ZX-SECRET-991"
    seen: list[str] = []

    class Spy:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            seen.extend(m.content for m in messages)
            seen.extend(f"{t.name}{t.description}{t.parameters}" for t in tools)
            seen.extend(repr(m) for m in messages)
            return AssistantMessage("hi")

    b = make_bench(tmp_path, task="say hi", ground={"should_contain": [secret]})
    run_case(b, llm_factory=Spy)
    assert seen and not any(secret in s for s in seen)


def test_case_id_stable_and_explicit(tmp_path: Path) -> None:
    a, b = make_bench(tmp_path), make_bench(tmp_path)
    assert a.case_id == b.case_id and len(a.case_id) == 16
    assert make_bench(tmp_path, task="echo 43").case_id != a.case_id
    assert make_bench(tmp_path, id="my-id").case_id == "my-id"


def test_suite_continues_after_crash(tmp_path: Path) -> None:
    rep = run_suite([PASS, FAIL])
    assert isinstance(rep, SuiteReport)
    assert (rep.passed, rep.failed, rep.total, rep.pass_rate) == (1, 1, 2, 0.5)


def test_main_exit_codes(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main([str(PASS)]) == 0
    assert json.loads(capsys.readouterr().out)["pass_rate"] == 1.0
    assert main([str(FAIL)]) == 1
    assert json.loads(capsys.readouterr().out)["pass_rate"] == 0.0
    assert main([str(tmp_path / "missing.json")]) == 2


@pytest.mark.parametrize("phrase", ["", "   "])
@pytest.mark.parametrize("key", ["should_contain", "should_not_contain"])
def test_empty_phrase_rejected(tmp_path: Path, key: str, phrase: str) -> None:
    with pytest.raises(ValueError, match=key):
        make_bench(tmp_path, ground={key: [phrase]})


@pytest.mark.parametrize("bad", [["x"], {"a": 1}, 5, None])
def test_non_string_eval_type_is_valueerror(tmp_path: Path, bad: Any) -> None:
    with pytest.raises(ValueError, match=r"ground\.eval\.type"):
        make_bench(tmp_path, ground={"eval": {"type": bad}})


def test_main_exit_2_on_bad_eval_type(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    make_bench(tmp_path)  # writes b.json; overwrite with a bad type
    data = json.loads((tmp_path / "b.json").read_text())
    data["ground"]["eval"]["type"] = ["x"]
    (tmp_path / "b.json").write_text(json.dumps(data))
    assert main([str(tmp_path / "b.json")]) == 2


def test_case_sensitive_must_be_bool(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="case_sensitive"):
        make_bench(tmp_path, ground={"case_sensitive": "false"})


def test_empty_ground_cannot_pass(tmp_path: Path) -> None:
    b = make_bench(tmp_path, ground={"should_contain": [], "should_not_contain": []})
    r = run_case(b)
    assert r.passed is False and r.error is None and r.grading is not None
    assert r.grading.total == 0


def _capture() -> tuple[list[Workspace], Any]:
    seen: list[Workspace] = []

    def tools(ws: Workspace) -> list[Any]:
        seen.append(ws)
        return []

    return seen, tools


def test_workspace_cleaned_after_crash(tmp_path: Path) -> None:
    seen, tools = _capture()
    r = run_case(make_bench(tmp_path), llm_factory=Boom, tools_factory=tools)
    assert r.error is not None and len(seen) == 1 and not seen[0].root.exists()


def test_workspace_cleaned_after_timeout(tmp_path: Path) -> None:
    seen, tools = _capture()
    r = run_case(make_bench(tmp_path, cutoff_s=0), tools_factory=tools)
    assert r.timed_out and len(seen) == 1 and not seen[0].root.exists()


def test_mkdtemp_failure_is_failed_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(**kw: Any) -> str:
        raise OSError("disk full")

    monkeypatch.setattr("master_finhub.evals.runner.tempfile.mkdtemp", fail)
    r = run_case(make_bench(tmp_path))
    assert r.passed is False and r.error is not None and r.error.startswith("OSError")
