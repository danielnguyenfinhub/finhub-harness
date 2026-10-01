"""Slice 5 proof tests: checkpoint and resume (synthetic data only, no network)."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from checkpoint_child import PROMPT, CountingLLM, MarkerTool

from master_finhub.cli import main
from master_finhub.orchestration import _fsio, dag_engine
from master_finhub.orchestration.dag_engine import (
    MAX_CHECKPOINT_BYTES,
    Checkpoint,
    CheckpointError,
    CheckpointStore,
    encode_checkpoint,
    snapshot_to_state,
    state_to_checkpoint,
    validate_run_id,
)
from master_finhub.runtime.context import CLIP_BUDGET_TOKENS, ContextManager, clip_text
from master_finhub.runtime.loop import (
    AgentLoop,
    AgentLoopError,
    AssistantMessage,
    LoopSnapshot,
    Message,
    ResumeBlocked,
    ToolCall,
    ToolSpec,
)
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.builtins.echo import EchoTool

ROOT = Path(__file__).resolve().parent.parent
FIXED = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone(timedelta(hours=10)))
SENTINEL = "client_a ACCT-001 SECRET"
IS_WIN = sys.platform == "win32"


def _clock() -> datetime:
    return FIXED


def _store(root: Path, **kw: Any) -> CheckpointStore:
    root.mkdir(parents=True, exist_ok=True)
    return CheckpointStore(Workspace(root), clock=_clock, **kw)


def _prompt(text: str = "echo hi") -> LoopSnapshot:
    return LoopSnapshot(0, (Message("user", text),))


def _turns(n: int, text: str = "go") -> LoopSnapshot:
    msgs: list[Message] = [Message("user", text)]
    for i in range(1, n + 1):
        call = ToolCall(f"c{i}", "echo", {"text": f"t{i}"})
        msgs.append(Message("assistant", "", (call,)))
        msgs.append(Message("tool", f"t{i}", tool_call_id=f"c{i}"))
    return LoopSnapshot(n, tuple(msgs))


def _in_flight(tool: str = "write_file", second: bool = True) -> LoopSnapshot:
    calls = [ToolCall("call-7", tool, {"path": SENTINEL})]
    if second:
        calls.append(ToolCall("call-8", "echo", {"text": "after"}))
    return LoopSnapshot(4, (Message("user", "go"), Message("assistant", "", tuple(calls))))


def _step_file(root: Path, run: str, seq: int) -> Path:
    return root / ".checkpoints" / run / f"step-{seq:06d}.json"


def _checksum_rewrite(path: Path, edit: Any) -> None:
    env = json.loads(path.read_text(encoding="utf-8"))
    edit(env)
    body = {"schema_version": env["schema_version"], "state": env["state"]}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    env["checksum"] = "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()
    path.write_text(json.dumps(env, indent=2, sort_keys=True, ensure_ascii=False), "utf-8")


def _save_n(store: CheckpointStore, run: str, n: int, snap: LoopSnapshot | None = None) -> None:
    writer = store.create_run(run)
    for _ in range(n):
        writer(snap or _prompt())
    writer.close()


def _assert_clean(exc: CheckpointError) -> None:
    text = str(exc) + repr(exc)
    assert SENTINEL not in text and "ACCT-001" not in text
    assert exc.__cause__ is None and exc.__suppress_context__ is True
    assert len(str(exc).split("\n")) == 3, "three-part message expected"


class QueueLLM:
    def __init__(self, replies: list[AssistantMessage]) -> None:
        self.replies = list(replies)
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.seen.append(list(messages))
        return self.replies.pop(0)


class FakeTool:
    def __init__(self, name: str, idempotent: bool) -> None:
        self.spec = ToolSpec(name, "d", {}, idempotent=idempotent)
        self.ran: list[dict[str, Any]] = []

    def run(self, arguments: dict[str, Any]) -> str:
        self.ran.append(arguments)
        return "ran"


# ----------------------------------------------------------------- T1, T15, T16, T20, T21, T22
def test_round_trip_equal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    writer = store.create_run("r1", meta={"profile": "scripted"})
    snap = _turns(1)
    writer(snap)
    cp = store.load("r1")
    assert cp == Checkpoint("r1", 0, FIXED, snap, None, {"profile": "scripted"})
    assert isinstance(cp.snapshot.messages[1].tool_calls, tuple)
    assert state_to_checkpoint(snapshot_to_state(cp), run_id="r1", seq=0) == cp


def test_deterministic_bytes(tmp_path: Path) -> None:
    for name in ("a", "b"):
        _save_n(_store(tmp_path / name), "r1", 1, _turns(2))
    a = _step_file(tmp_path / "a", "r1", 0).read_bytes()
    assert a == _step_file(tmp_path / "b", "r1", 0).read_bytes()
    assert b"2026-10-01T09:00:00+10:00" in a


def test_naive_clock_rejected(tmp_path: Path) -> None:
    root = tmp_path
    naive = datetime(2026, 10, 1, 9, 0, 0)  # noqa: DTZ001
    store = CheckpointStore(Workspace(root), clock=lambda: naive)
    with pytest.raises(CheckpointError) as ei:
        store.create_run("r1")(_prompt())
    _assert_clean(ei.value)


def test_loop_without_hook_unchanged() -> None:
    llm = QueueLLM([AssistantMessage("", [ToolCall("c1", "echo", {"text": "hi"})])])
    llm.replies.append(AssistantMessage("hi"))
    assert AgentLoop(llm, [EchoTool()]).run("go") == "hi"
    assert [len(m) for m in llm.seen] == [1, 3]


def test_resume_completed_returns_answer() -> None:
    llm = QueueLLM([])
    done = LoopSnapshot(1, (Message("user", "q"), Message("assistant", "the answer")))
    assert AgentLoop(llm, [EchoTool()]).resume(done) == "the answer"
    assert llm.seen == []


def test_resume_keeps_step_budget() -> None:
    llm = QueueLLM([AssistantMessage("", [ToolCall("cx", "echo", {"text": "x"})])] * 3)
    with pytest.raises(AgentLoopError):
        AgentLoop(llm, [EchoTool()], max_steps=4).resume(_turns(3))
    assert len(llm.seen) == 1


# ----------------------------------------------------------------- T2 proof, T26
def _child_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def test_kill_after_step_2_resumes_at_3(tmp_path: Path) -> None:
    child = Path(__file__).parent / "checkpoint_child.py"
    done = subprocess.run(
        [sys.executable, str(child), "kill", str(tmp_path), "kill-run"],
        env=_child_env(),
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 9, done.stderr
    store = CheckpointStore(Workspace(tmp_path), clock=_clock)
    cp, writer = store.resume_run("kill-run")  # also proves the dead process's lock is gone
    assert store.list_seqs("kill-run") == [0, 1, 2, 3, 4]
    assert (cp.seq, cp.snapshot.step, cp.snapshot.status) == (4, 2, "awaiting_model")
    llm = CountingLLM()
    answer = AgentLoop(llm, [EchoTool()], checkpoint=writer).resume(cp.snapshot)
    writer.close()
    assert answer == AgentLoop(CountingLLM(), [EchoTool()]).run(PROMPT) == "final:part1+part2+part3"
    assert llm.calls == 2, "resumed at step 3, did not start over"
    claim, reply = store.load("kill-run", 5), store.load("kill-run", 6)
    assert (claim.snapshot, reply.snapshot.step) == (cp.snapshot, 3)
    assert store.load("kill-run").snapshot.status == "completed"


class _Stop(Exception):
    pass


class BigTool:
    spec = ToolSpec("big", "d", {}, idempotent=True)

    def run(self, arguments: dict[str, Any]) -> str:
        return "x" * 3_000_000


def test_tool_result_clipped_on_save_and_resume_equivalent(tmp_path: Path) -> None:
    def llm() -> QueueLLM:
        return QueueLLM([AssistantMessage("", [ToolCall("b1", "big", {})]), AssistantMessage("ok")])

    plain = llm()
    AgentLoop(plain, [BigTool()], context=ContextManager()).run("go")
    store = _store(tmp_path)
    writer = store.create_run("r1")

    def hook(snap: LoopSnapshot) -> None:
        writer(snap)
        if snap.step == 1 and snap.status == "awaiting_model":
            raise _Stop

    with pytest.raises(_Stop):
        AgentLoop(llm(), [BigTool()], context=ContextManager(), checkpoint=hook).run("go")
    writer.close()
    cp, writer2 = store.resume_run("r1")
    assert cp.snapshot.messages[-1].content == clip_text("x" * 3_000_000, CLIP_BUDGET_TOKENS)
    resumed = QueueLLM([AssistantMessage("ok")])
    AgentLoop(resumed, [BigTool()], context=ContextManager(), checkpoint=writer2).resume(
        cp.snapshot
    )
    writer2.close()
    assert resumed.seen[0] == plain.seen[1]


# ----------------------------------------------------------------- T3-T7, T12
def test_torn_write_never_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    writer = store.create_run("r1")
    with monkeypatch.context() as m:

        def boom(fd: int) -> None:
            raise OSError(5, "disk")

        m.setattr(os, "fsync", boom)
        with pytest.raises(CheckpointError) as ei:
            writer(_prompt())
    _assert_clean(ei.value)
    left = [p.name for p in (tmp_path / ".checkpoints" / "r1").iterdir()]
    assert not [n for n in left if n.startswith(("step-", ".tmp-"))]
    writer(_prompt())
    (tmp_path / ".checkpoints" / "r1" / ".tmp-stray.json").write_text("junk")
    assert store.list_seqs("r1") == [0]


def test_truncated_file_fails_loudly(tmp_path: Path) -> None:
    _save_n(_store(tmp_path), "r1", 3)
    path = _step_file(tmp_path, "r1", 2)
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
    with pytest.raises(CheckpointError, match="unreadable") as ei:
        _store(tmp_path).load("r1")
    _assert_clean(ei.value)


def test_checksum_tamper_detected(tmp_path: Path) -> None:
    _save_n(_store(tmp_path), "r1", 1, _prompt(SENTINEL))
    path = _step_file(tmp_path, "r1", 0)
    path.write_text(path.read_text("utf-8").replace("client_a", "client_b"), "utf-8")
    with pytest.raises(CheckpointError, match="integrity check") as ei:
        _store(tmp_path).load("r1")
    _assert_clean(ei.value)


def test_gap_detected(tmp_path: Path) -> None:
    _save_n(_store(tmp_path), "r1", 5)
    _step_file(tmp_path, "r1", 2).unlink()
    with pytest.raises(CheckpointError, match="missing step file 2") as ei:
        _store(tmp_path).load("r1")
    assert "0-1, 3-4" in str(ei.value)
    _assert_clean(ei.value)


@pytest.mark.parametrize("version", [2, 0])
def test_unknown_schema_version(tmp_path: Path, version: int) -> None:
    _save_n(_store(tmp_path), "r1", 1)
    _checksum_rewrite(_step_file(tmp_path, "r1", 0), lambda e: e.update(schema_version=version))
    with pytest.raises(CheckpointError, match="different version") as ei:
        _store(tmp_path).load("r1")
    _assert_clean(ei.value)


def test_run_id_mismatch_and_seq_mismatch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save_n(store, "run-a", 1)
    _save_n(store, "run-b", 3)
    (tmp_path / ".checkpoints" / "run-c").mkdir()
    (tmp_path / ".checkpoints" / "run-c" / "step-000000.json").write_bytes(
        _step_file(tmp_path, "run-a", 0).read_bytes()
    )
    with pytest.raises(CheckpointError, match="different run") as ei:
        store.load("run-c")
    _assert_clean(ei.value)
    _step_file(tmp_path, "run-b", 1).write_bytes(_step_file(tmp_path, "run-b", 2).read_bytes())
    with pytest.raises(CheckpointError, match="out of place") as ei2:
        store.load("run-b", seq=1)
    _assert_clean(ei2.value)


def test_malformed_state_and_status_mismatch(tmp_path: Path) -> None:
    _save_n(_store(tmp_path), "r1", 1)
    path = _step_file(tmp_path, "r1", 0)
    _checksum_rewrite(path, lambda e: e["state"].update(status="completed"))
    with pytest.raises(CheckpointError, match=r"malformed \(status\)") as ei:
        _store(tmp_path).load("r1")
    _assert_clean(ei.value)
    _checksum_rewrite(path, lambda e: e["state"].update(status="awaiting_model", saved_at="x"))
    with pytest.raises(CheckpointError, match=r"malformed \(saved_at\)"):
        _store(tmp_path).load("r1")
    _checksum_rewrite(path, lambda e: e["state"].update(saved_at="2026-10-01T09:00:00"))
    with pytest.raises(CheckpointError, match=r"malformed \(saved_at\)"):
        _store(tmp_path).load("r1")
    _checksum_rewrite(path, lambda e: e["state"]["messages"][0].update(role="tool"))
    with pytest.raises(CheckpointError, match="malformed"):
        _store(tmp_path).load("r1")
    _checksum_rewrite(path, lambda e: e.update(extra=1))
    with pytest.raises(CheckpointError, match="unexpected layout"):
        _store(tmp_path).load("r1")


# ----------------------------------------------------------------- T8
HOSTILE = ["../x", "a/b", "a\\b", "CON", "con", "COM1", "x:y", "", "a" * 200, "a\x00b"]
HOSTILE += ["abc\n", "run.1", "１２", " a", "-a", "a" * 65]


@pytest.mark.parametrize("bad", HOSTILE)
def test_hostile_run_ids_rejected_before_any_fs_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    store = _store(tmp_path)

    def fail(*a: Any, **k: Any) -> None:
        raise AssertionError("filesystem touched before the run id was validated")

    monkeypatch.setattr(Path, "mkdir", fail)
    monkeypatch.setattr(os, "open", fail)
    for call in (store.create_run, store.resume_run, store.load, store.list_seqs):
        with pytest.raises(CheckpointError) as ei:
            call(bad)
        if len(bad) > 3 and len(bad) < 100:
            assert bad not in str(ei.value)
        _assert_clean(ei.value)


def test_run_id_case_insensitive(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with store.create_run("Run1") as writer:
        writer(_prompt())
    assert validate_run_id("RUN1") == "run1"
    assert (tmp_path / ".checkpoints" / "run1").is_dir()
    assert store.load("Run1").run_id == "run1"
    cp, writer2 = store.resume_run("RUN1")
    writer2.close()
    assert cp.run_id == "run1"


def test_create_existing_run_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run("r1").close()
    with pytest.raises(CheckpointError, match="already exists") as ei:
        store.create_run("r1")
    _assert_clean(ei.value)


def test_checkpoints_folder_ignores_itself(tmp_path: Path) -> None:
    _store(tmp_path).create_run("r1").close()
    assert (tmp_path / ".checkpoints" / ".gitignore").read_text() == "*\n"
    assert ".checkpoints/" in (ROOT / ".gitignore").read_text().splitlines()


# ----------------------------------------------------------------- T9, T32
def _blocked_loop(tool: FakeTool, llm: QueueLLM | None = None) -> AgentLoop:
    return AgentLoop(llm or QueueLLM([AssistantMessage("fin")]), [tool, EchoTool()])


def test_in_flight_non_idempotent_stops() -> None:
    tool = FakeTool("write_file", idempotent=False)
    with pytest.raises(ResumeBlocked) as ei:
        _blocked_loop(tool).resume(_in_flight())
    assert (ei.value.tool_name, ei.value.call_id, ei.value.step) == ("write_file", "call-7", 4)
    assert "write_file" in str(ei.value) and SENTINEL not in str(ei.value)
    assert tool.ran == [] and len(str(ei.value).split("\n")) == 3


def test_in_flight_rerun_and_report_unknown_and_idempotent() -> None:
    tool = FakeTool("write_file", idempotent=False)
    assert _blocked_loop(tool).resume(_in_flight(), in_flight="rerun") == "fin"
    assert len(tool.ran) == 1
    tool2, llm = FakeTool("write_file", idempotent=False), QueueLLM([AssistantMessage("fin")])
    _blocked_loop(tool2, llm).resume(_in_flight(), in_flight="report_unknown")
    assert tool2.ran == []
    tool_msgs = [m for m in llm.seen[0] if m.role == "tool"]
    assert [m.tool_call_id for m in tool_msgs] == ["call-7", "call-8"]
    assert "may or may not have taken effect" in tool_msgs[0].content
    assert tool_msgs[1].content == "after", "calls after the first pending one run normally"
    safe = FakeTool("write_file", idempotent=True)
    _blocked_loop(safe).resume(_in_flight())
    assert len(safe.ran) == 1


def test_uncertain_call_unknown_or_denied_at_resume() -> None:
    llm = QueueLLM([AssistantMessage("fin")])
    AgentLoop(llm, [EchoTool()]).resume(_in_flight("gone_tool", second=False))
    first = next(m for m in llm.seen[0] if m.role == "tool").content
    assert "may or may not have taken effect" in first and "Unknown tool" not in first
    llm2 = QueueLLM([AssistantMessage("fin")])
    tool = FakeTool("write_file", idempotent=True)
    AgentLoop(llm2, [tool], guard=lambda c: "denied by policy").resume(_in_flight(second=False))
    first2 = next(m for m in llm2.seen[0] if m.role == "tool").content
    assert "may or may not have taken effect" in first2 and "denied by policy" not in first2
    assert tool.ran == []


# ----------------------------------------------------------------- T10, T11, T34
def test_no_content_in_exceptions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    call = ToolCall("c1", "echo", {"text": SENTINEL})
    snap = LoopSnapshot(
        1,
        (
            Message("user", SENTINEL),
            Message("assistant", "", (call,)),
            Message("tool", SENTINEL, tool_call_id="c1"),
        ),
    )
    store = _store(tmp_path)
    _save_n(store, "r1", 2, snap)
    caught: list[CheckpointError] = []

    def grab(fn: Any) -> None:
        with pytest.raises(CheckpointError) as ei:
            fn()
        caught.append(ei.value)

    p1 = _step_file(tmp_path, "r1", 1)
    original = p1.read_bytes()
    p1.write_bytes(original[: len(original) // 2])
    grab(lambda: store.load("r1"))
    p1.write_bytes(original.replace(b"client_a", b"client_b"))
    grab(lambda: store.load("r1"))
    p1.write_bytes(original)
    _step_file(tmp_path, "r1", 0).unlink()
    grab(lambda: store.load("r1"))
    bad_call = ToolCall("c1", "echo", {"text": {SENTINEL}})
    w = _store(tmp_path / "other").create_run("r2")
    grab(lambda: w(LoopSnapshot(1, (Message("user", "x"), Message("assistant", "", (bad_call,))))))
    grab(lambda: w(LoopSnapshot(0, (Message("user", SENTINEL + "\ud800"),))))
    w.close()
    for exc in caught:
        _assert_clean(exc)
    assert not (tmp_path / ".checkpoints" / "r1" / "step-000000.json").exists()


@pytest.mark.parametrize(
    "value",
    [{1, 2}, b"x", (1, 2), {1: "a"}, float("nan"), float("inf"), object(), "\ud800"],
)
def test_non_json_tool_arguments_rejected(tmp_path: Path, value: Any) -> None:
    writer = _store(tmp_path).create_run("r1")
    call = ToolCall("c1", "echo", {"text": value})
    snap = LoopSnapshot(1, (Message("user", "x"), Message("assistant", "", (call,))))
    with pytest.raises(CheckpointError) as ei:
        writer(snap)
    _assert_clean(ei.value)
    assert not list((tmp_path / ".checkpoints" / "r1").glob("step-*"))


def test_depth_and_bigint_rejected(tmp_path: Path) -> None:
    writer = _store(tmp_path).create_run("r1")
    deep: Any = "x"
    for _ in range(65):
        deep = [deep]
    for args in ({"a": deep}, {"a": 10**5000}):
        call = ToolCall("c1", "echo", args)
        with pytest.raises(CheckpointError) as ei:
            writer(LoopSnapshot(1, (Message("user", "x"), Message("assistant", "", (call,)))))
        _assert_clean(ei.value)
    ok: Any = "x"
    for _ in range(60):
        ok = [ok]
    writer(
        LoopSnapshot(
            1, (Message("user", "x"), Message("assistant", "", (ToolCall("c", "e", {"a": ok}),)))
        )
    )


def test_hostile_files_are_unreadable_not_crashes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save_n(store, "r1", 1, _prompt(SENTINEL))
    path = _step_file(tmp_path, "r1", 0)
    for blob in (
        b"[" * 100_000,
        b'{"checksum":"x","schema_version":1,"state":{"a":' + b"9" * 5000 + b"}}",
        b'{"checksum":"x","schema_version":1,"state":{"a":NaN}}',
        b"\xff\xfe" + SENTINEL.encode(),
    ):
        path.write_bytes(blob)
        with pytest.raises(CheckpointError, match="unreadable") as ei:
            store.load("r1")
        _assert_clean(ei.value)


# ----------------------------------------------------------------- T13, T13b, T25, T31, T33
def _no_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dag_engine, "_try_lock", lambda fd: None)


def test_publish_never_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_lock(monkeypatch)
    store = _store(tmp_path)
    w1 = store.create_run("r1")
    w1(_prompt())
    _, w2 = store.resume_run("r1")
    w1(_prompt("first"))
    before = _step_file(tmp_path, "r1", 1).read_bytes()
    with pytest.raises(CheckpointError, match="Another process") as ei:
        w2(_prompt("second"))
    _assert_clean(ei.value)
    assert _step_file(tmp_path, "r1", 1).read_bytes() == before


def test_same_process_second_writer_refused_by_lock(tmp_path: Path) -> None:
    store = _store(tmp_path)
    w1 = store.create_run("r1")
    w1(_prompt())
    with pytest.raises(CheckpointError, match="still running") as ei:
        store.resume_run("r1")
    _assert_clean(ei.value)
    w1.close()
    store.resume_run("r1")[1].close()


def test_concurrent_resume_rerun_runs_tool_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    call = ToolCall("c1", "write_marker", {})
    _save_n(
        store, "r1", 1, LoopSnapshot(1, (Message("user", "go"), Message("assistant", "", (call,))))
    )
    marker = tmp_path / "marker.txt"
    child = Path(__file__).parent / "checkpoint_child.py"
    start = time.time() + 3
    args = [sys.executable, str(child), "race", str(tmp_path), "r1", str(marker), str(start)]
    procs = [subprocess.Popen(args, env=_child_env(), stderr=subprocess.PIPE) for _ in range(2)]
    codes = sorted(p.wait(timeout=60) for p in procs)
    for p in procs:
        assert p.stderr is not None
        p.stderr.close()
    assert marker.read_text().splitlines() == ["ran"], "side effect exactly once"
    assert codes == [0, 3], "one winner, one loser that ran nothing"


def test_marker_tool_is_not_idempotent() -> None:
    assert MarkerTool("x").spec.idempotent is False


def test_owner_lock_released_when_holder_exits(tmp_path: Path) -> None:
    child = Path(__file__).parent / "checkpoint_child.py"
    proc = subprocess.Popen(
        [sys.executable, str(child), "hold", str(tmp_path), "r1"],
        env=_child_env(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None
    assert proc.stdout.readline().strip() == "ready"
    store = CheckpointStore(Workspace(tmp_path), clock=_clock)
    with pytest.raises(CheckpointError, match="still running"):
        store.resume_run("r1")
    proc.stdin.write("\n")
    proc.stdin.flush()
    proc.wait(timeout=30)
    proc.stdin.close()
    proc.stdout.close()
    store.resume_run("r1")[1].close()


def test_temp_cleanup_failure_stays_in_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_lock(monkeypatch)
    store = _store(tmp_path)
    w1 = store.create_run("r1")
    w1(_prompt())
    _, w2 = store.resume_run("r1")
    w1(_prompt())
    leak = tmp_path / "leaky-abs-path"

    def deny(path: Any, *a: Any, **k: Any) -> None:
        raise PermissionError(32, "in use", str(leak))

    with monkeypatch.context() as m:
        m.setattr(os, "unlink", deny)
        with pytest.raises(CheckpointError, match="Another process") as ei:
            w2(_prompt())
        _, w3 = store.resume_run("r1")
        w3(_prompt())
    assert "leaky" not in str(ei.value) and str(tmp_path) not in str(ei.value)
    _assert_clean(ei.value)


# ----------------------------------------------------------------- T14 time travel, T17, T18, T19
def test_fork_records_parent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    writer = store.create_run("run")
    writer(_turns(0))
    writer(_turns(1))
    writer(_turns(2))
    writer.close()
    before = [_step_file(tmp_path, "run", i).read_bytes() for i in range(3)]
    parent = store.load("run", seq=2)
    fork = store.create_run("fork", parent=parent)
    fork(parent.snapshot)
    fork.close()
    assert store.load("fork", 0).parent == "run@2"
    assert [_step_file(tmp_path, "run", i).read_bytes() for i in range(3)] == before


def test_fenced_read_symlink_outside(tmp_path: Path) -> None:
    ws_root, outside = tmp_path / "ws", tmp_path / "outside"
    outside.mkdir()
    store = _store(ws_root)
    _save_n(store, "r1", 2)
    (outside / "x.json").write_text("{}")
    link = _step_file(ws_root, "r1", 1)
    link.unlink()
    try:
        os.symlink(outside / "x.json", link)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here (needs Developer Mode or admin on Windows)")
    with pytest.raises(CheckpointError, match="outside the workspace") as ei:
        store.load("r1")
    _assert_clean(ei.value)


def test_step_names_ascii_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save_n(store, "r1", 2)
    run = tmp_path / ".checkpoints" / "r1"
    for ignored in (".tmp-x.json", "desktop.ini"):
        (run / ignored).write_text("x")
    assert store.list_seqs("r1") == [0, 1]
    for odd in ("step-００００09.json", "step-9.json"):
        (run / odd).write_text("x")
        with pytest.raises(CheckpointError, match="unexpected file") as ei:
            store.list_seqs("r1")
        _assert_clean(ei.value)
        (run / odd).unlink()


def test_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*a: Any, **k: Any) -> None:
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    store = _store(tmp_path)
    store.create_run("r1")(_turns(1))
    assert store.load("r1").snapshot.step == 1


def test_stdlib_only() -> None:
    tree = ast.parse((ROOT / "src/master_finhub/orchestration/dag_engine.py").read_text("utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"master_finhub"}, mods


# ----------------------------------------------------------------- T27 size cap (+ R3-1)
def _padded(store: CheckpointStore, run: str, seq: int, target: int) -> Checkpoint:
    base = Checkpoint(run, seq, FIXED, _prompt(""))
    pad = target - len(encode_checkpoint(base))
    assert pad > 0
    return Checkpoint(run, seq, FIXED, _prompt("a" * pad))


def test_size_cap_save_and_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    exact = _padded(store, "r1", 0, MAX_CHECKPOINT_BYTES)
    assert len(encode_checkpoint(exact)) == MAX_CHECKPOINT_BYTES
    store.create_run("r1")(exact.snapshot)  # (a) saves ...
    path = _step_file(tmp_path, "r1", 0)
    assert path.stat().st_size == MAX_CHECKPOINT_BYTES
    assert store.load("r1") == exact  # ... and loads
    over = Checkpoint("r2", 0, FIXED, _prompt("a" * (len(exact.snapshot.messages[0].content) + 1)))
    w2 = store.create_run("r2")
    with monkeypatch.context() as m:
        m.setattr(
            "tempfile.mkstemp", lambda *a, **k: (_ for _ in ()).throw(AssertionError("mkstemp"))
        )
        with pytest.raises(CheckpointError, match="too large to save") as ei:  # (b)
            w2(over.snapshot)
    _assert_clean(ei.value)
    assert not [
        p for p in (tmp_path / ".checkpoints" / "r2").iterdir() if p.name[:4] in ("step", ".tmp")
    ]
    hand = _step_file(tmp_path, "r1", 0)
    hand.write_bytes(b"x" * (MAX_CHECKPOINT_BYTES + 1))  # (c)
    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(AssertionError("read")))
        with pytest.raises(CheckpointError, match="too large to load") as ei2:
            store.load("r1")
    _assert_clean(ei2.value)


def test_judge_case_compact_at_cap_is_refused_on_save(tmp_path: Path) -> None:
    store = _store(tmp_path)
    cp = _padded(store, "r1", 0, MAX_CHECKPOINT_BYTES)
    body = {"schema_version": 1, "state": snapshot_to_state(cp)}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    pad_more = MAX_CHECKPOINT_BYTES - len(canon.encode("utf-8"))
    content = cp.snapshot.messages[0].content + "a" * pad_more
    judge = Checkpoint("r1", 0, FIXED, _prompt(content))
    with pytest.raises(CheckpointError, match="too large to save"):
        store.create_run("r1")(judge.snapshot)
    assert not list((tmp_path / ".checkpoints" / "r1").glob("step-*"))


def test_claim_save_refused_loudly_when_seq_gains_a_digit(tmp_path: Path) -> None:
    store = _store(tmp_path)
    writer = store.create_run("r1")
    for _ in range(9):
        writer(_prompt())
    big = _padded(store, "r1", 9, MAX_CHECKPOINT_BYTES)
    writer(big.snapshot)  # seq 9 file is exactly at the cap
    writer.close()
    with pytest.raises(CheckpointError, match="too large"):  # seq 10 is one byte longer
        encode_checkpoint(Checkpoint("r1", 10, FIXED, big.snapshot))
    cp, writer2 = store.resume_run("r1")
    llm = QueueLLM([AssistantMessage("never")])
    with pytest.raises(CheckpointError, match="too large to save") as ei:
        AgentLoop(llm, [EchoTool()], checkpoint=writer2).resume(cp.snapshot)
    writer2.close()
    assert llm.seen == [] and "stopped" in str(ei.value)
    _assert_clean(ei.value)


# ----------------------------------------------------------------- T30 (win32) and POSIX (skipped here)
@pytest.mark.skipif(not IS_WIN, reason="MoveFileExW publish is the win32 branch")
def test_win32_publish_uses_write_through_no_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    writer = store.create_run("r1")
    real = _fsio._move_file_ex
    seen: list[tuple[Any, Any, int]] = []

    def spy(src: Any, dst: Any, flags: int) -> int:
        seen.append((src, dst, flags))
        return real(src, dst, flags)

    monkeypatch.setattr(_fsio, "_move_file_ex", spy)
    writer(_prompt())
    assert len(seen) == 1 and all(isinstance(x, str) for x in seen[0][:2])
    assert seen[0][2] == 0x8 and not seen[0][2] & 0x1
    final = _step_file(tmp_path, "r1", 1)
    final.write_bytes(b"keep")  # a stranger already owns the next name
    with pytest.raises(CheckpointError, match="Another process"):
        writer(_prompt())
    assert final.read_bytes() == b"keep"


@pytest.mark.skipif(not IS_WIN, reason="MoveFileExW publish is the win32 branch")
def test_win32_busy_codes_retried_then_antivirus_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _store(tmp_path).create_run("r1")
    calls: list[int] = []

    def busy(src: str, dst: str, flags: int) -> int:
        calls.append(flags)
        return 32

    monkeypatch.setattr(_fsio, "_move_file_ex", busy)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    with pytest.raises(CheckpointError, match="antivirus") as ei:
        writer(_prompt())
    assert len(calls) == 4, "first try plus 3 retries"
    _assert_clean(ei.value)


@pytest.mark.skipif(not IS_WIN, reason="MoveFileExW publish is the win32 branch")
def test_win32_wrapper_unavailable_fails_loudly_no_link_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _store(tmp_path).create_run("r1")

    def gone(src: str, dst: str, flags: int) -> int:
        raise OSError("MoveFileExW unavailable")

    def no_link(*a: Any, **k: Any) -> None:
        raise AssertionError("os.link fallback used")

    monkeypatch.setattr(_fsio, "_move_file_ex", gone)
    monkeypatch.setattr(os, "link", no_link)
    for _ in range(2):  # every save, not just the first
        with pytest.raises(CheckpointError, match="cannot store checkpoints safely") as ei:
            writer(_prompt())
        _assert_clean(ei.value)


@pytest.mark.skipif(not IS_WIN, reason="win32 error-code mapping")
def test_win32_other_error_code_names_the_drive_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _store(tmp_path).create_run("r1")
    monkeypatch.setattr(_fsio, "_move_file_ex", lambda s, d, f: 1)
    with pytest.raises(
        CheckpointError, match=r"cannot store checkpoints safely \(Windows error 1\)"
    ):
        writer(_prompt())


@pytest.mark.skipif(
    IS_WIN, reason="POSIX os.link + directory fsync need a POSIX interpreter (unverified here)"
)
def test_posix_publish_no_clobber(tmp_path: Path) -> None:
    writer = _store(tmp_path).create_run("r1")
    writer(_prompt())
    (tmp_path / ".checkpoints" / "r1" / "step-000001.json").write_bytes(b"keep")
    with pytest.raises(CheckpointError, match="Another process"):
        writer(_prompt())
    assert not list((tmp_path / ".checkpoints" / "r1").glob(".tmp-*"))


@pytest.mark.skipif(
    IS_WIN, reason="fcntl.flock owner lock needs a POSIX interpreter (unverified here)"
)
def test_posix_flock_owner_lock(tmp_path: Path) -> None:
    store = _store(tmp_path)
    w1 = store.create_run("r1")
    w1(_prompt())
    with pytest.raises(CheckpointError, match="still running"):
        store.resume_run("r1")
    w1.close()


def test_unreadable_owner_file_is_not_reported_as_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    _save_n(store, "r1", 1)
    real_open = os.open

    def deny(path: Any, flags: int, *a: Any) -> int:
        if str(path).endswith(".owner"):
            raise PermissionError(13, "read-only")
        return real_open(path, flags, *a)

    monkeypatch.setattr(os, "open", deny)
    with pytest.raises(CheckpointError, match="Cannot open the lock file") as ei:
        store.resume_run("r1")
    assert "still running" not in str(ei.value)
    _assert_clean(ei.value)


# ----------------------------------------------------------------- T24 CLI
def test_cli_run_id_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MASTER_FINHUB_WORKSPACE", str(tmp_path))
    assert main(["--run-id", "r1", "echo hi"]) == 0
    assert capsys.readouterr().out.strip() == "hi"
    assert len(list((tmp_path / ".checkpoints" / "r1").glob("step-*.json"))) == 4
    assert main(["--resume", "r1"]) == 0
    assert capsys.readouterr().out.strip() == "hi"
    assert main(["--resume", "r1", "echo again"]) == 2
    assert main(["--run-id", "r1", "echo hi"]) == 1  # already exists
    assert "already exists" in capsys.readouterr().err
    assert main(["--resume", "r1", "--profile", "judge"]) == 2
    assert "started with" in capsys.readouterr().err
    assert main(["--resume", "nope1"]) == 1
    with pytest.raises(SystemExit) as ei:  # a new run needs a prompt
        main(["--run-id", "r2"])
    assert ei.value.code == 2


def test_cli_missing_workspace_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MASTER_FINHUB_WORKSPACE", str(tmp_path / "nope"))
    assert main(["--run-id", "r1", "echo hi"]) == 2
    assert "MASTER_FINHUB_WORKSPACE" in capsys.readouterr().err


def test_cli_without_flags_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MASTER_FINHUB_WORKSPACE", str(tmp_path))
    assert main(["echo hi"]) == 0
    assert not (tmp_path / ".checkpoints").exists()


def test_idempotent_flag_defaults_and_stays_off_the_wire() -> None:
    assert ToolSpec("n", "d", {}).idempotent is False
    assert EchoTool.spec.idempotent is True


# ----------------------------------------------------------------- D1: no exception chain, no leaks
MARKER = "CLIENT-DOE-MARKER-1234"


def _chain(exc: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    todo: list[BaseException | None] = [exc]
    while todo:
        cur = todo.pop()
        if cur is None or any(cur is s for s in seen):
            continue
        seen.append(cur)
        todo += [cur.__cause__, cur.__context__]
    return seen


def _spellings(root: Path) -> set[str]:
    forms = {str(root), str(root.resolve()), os.fspath(root)}
    if IS_WIN:
        import ctypes

        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(str(root), buf, 1024):  # type: ignore[attr-defined]
            forms.add(buf.value)
    out = set()
    for form in forms:
        for v in (form, form.replace("\\", "\\\\"), form.replace("\\", "/")):
            out.add(v.lower())
    return out


def _marker_run(root: Path, n: int = 2) -> CheckpointStore:
    store = _store(root)
    _save_n(store, "r1", n, _prompt(MARKER))
    return store


def _s_create_existing(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _store(root)
    store.create_run("run1").close()
    store.create_run("run1")


def _s_corrupt(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    _step_file(root, "r1", 1).write_text('{"a": "' + MARKER + '" ', encoding="utf-8")
    store.load("r1")


def _s_truncated(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    p = _step_file(root, "r1", 1)
    p.write_bytes(p.read_bytes()[: p.stat().st_size // 2])
    store.load("r1")


def _s_bad_utf8(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    _step_file(root, "r1", 1).write_bytes(b"\xff\xfe" + MARKER.encode())
    store.load("r1")


def _s_schema(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    _checksum_rewrite(_step_file(root, "r1", 1), lambda e: e.update(schema_version=2))
    store.load("r1")


def _s_gap(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root, 3)
    _step_file(root, "r1", 1).unlink()
    store.load("r1")


def _s_checksum(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    p = _step_file(root, "r1", 1)
    p.write_text(p.read_text("utf-8").replace("MARKER", "MARKED"), "utf-8")
    store.load("r1")


def _s_malformed(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    _checksum_rewrite(_step_file(root, "r1", 1), lambda e: e["state"].update(saved_at="nope"))
    store.load("r1")


def _s_over_cap_save(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _store(root)
    store.create_run("r1")(_prompt(MARKER + "a" * MAX_CHECKPOINT_BYTES))


def _s_over_cap_load(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    _step_file(root, "r1", 1).write_bytes(MARKER.encode() * (MAX_CHECKPOINT_BYTES // 8))
    store.load("r1")


def _s_fence(root: Path, mp: pytest.MonkeyPatch) -> None:
    from master_finhub.sandbox.workspace import SandboxDenied

    store = _marker_run(root)

    def deny(self: Workspace, path: Any) -> Path:
        raise SandboxDenied(str(root), f"{root} {MARKER}", "read")

    mp.setattr(Workspace, "check_read", deny)
    store.load("r1")


def _s_bad_id(root: Path, mp: pytest.MonkeyPatch) -> None:
    _store(root).create_run("../" + MARKER)


def _s_lock_held(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    writer = store.create_run("r2")
    writer(_prompt(MARKER))
    store.resume_run("r2")


def _s_publish_exists(root: Path, mp: pytest.MonkeyPatch) -> None:
    writer = _store(root).create_run("r1")
    writer(_prompt(MARKER))
    _step_file(root, "r1", 1).write_bytes(b"x")
    writer(_prompt(MARKER))


def _s_disk_error(root: Path, mp: pytest.MonkeyPatch) -> None:
    writer = _store(root).create_run("r1")

    def boom(fd: int) -> None:
        raise OSError(5, MARKER, str(root))

    mp.setattr(os, "fsync", boom)
    writer(_prompt(MARKER))


def _s_owner_open(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    real = os.open

    def deny(path: Any, flags: int, *a: Any) -> int:
        if str(path).endswith(".owner"):
            raise PermissionError(13, MARKER, str(path))
        return real(path, flags, *a)

    mp.setattr(os, "open", deny)
    store.resume_run("r1")


def _s_not_found(root: Path, mp: pytest.MonkeyPatch) -> None:
    _store(root).load("nope1")


def _s_unexpected_file(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    (root / ".checkpoints" / "r1" / "step-9.json").write_text(MARKER)
    store.list_seqs("r1")


def _s_non_json(root: Path, mp: pytest.MonkeyPatch) -> None:
    call = ToolCall("c1", "echo", {"text": {MARKER}})
    snap = LoopSnapshot(1, (Message("user", MARKER), Message("assistant", "", (call,))))
    _store(root).create_run("r1")(snap)


def _s_bigint(root: Path, mp: pytest.MonkeyPatch) -> None:
    call = ToolCall("c1", "echo", {"n": 10**5000, "t": MARKER})
    snap = LoopSnapshot(1, (Message("user", MARKER), Message("assistant", "", (call,))))
    _store(root).create_run("r1")(snap)


def _s_bigint_on_disk(root: Path, mp: pytest.MonkeyPatch) -> None:
    store = _marker_run(root)
    body = b'{"checksum":"x","schema_version":1,"state":{"a":' + b"9" * 5000 + b"}}"
    _step_file(root, "r1", 1).write_bytes(body)
    store.load("r1")


SCENARIOS = [
    _s_create_existing, _s_corrupt, _s_truncated, _s_bad_utf8, _s_schema, _s_gap, _s_checksum,
    _s_malformed, _s_over_cap_save, _s_over_cap_load, _s_fence, _s_bad_id, _s_lock_held,
    _s_publish_exists, _s_disk_error, _s_owner_open, _s_not_found, _s_unexpected_file,
    _s_non_json, _s_bigint, _s_bigint_on_disk,
]  # fmt: skip


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda f: f.__name__[3:])
def test_no_exception_chain_no_marker_no_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    scenario: Any,
) -> None:
    import logging

    root = tmp_path / "ws"
    root.mkdir()
    caplog.set_level(logging.DEBUG)
    with pytest.raises(CheckpointError) as ei, monkeypatch.context() as m:
        scenario(root, m)
    chain = _chain(ei.value)
    assert len(chain) == 1, [type(e).__name__ for e in chain]
    pool = "".join(f"{e}{e!r}{e.args!r}" for e in chain).lower()
    assert MARKER.lower() not in pool
    for spelling in _spellings(root):
        assert spelling not in pool
    out = capsys.readouterr()
    everything = (caplog.text + out.out + out.err).lower()
    assert MARKER.lower() not in everything
    for spelling in _spellings(root):
        assert spelling not in everything
