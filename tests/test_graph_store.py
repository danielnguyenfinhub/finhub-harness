"""Slice 6 proof tests, part 2: checkpoints, kill/resume, Ctrl-C, abandoned nodes (synthetic data)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from graph_child import INPUTS, diamond, make_store

from master_finhub.orchestration import graph as graph_mod
from master_finhub.orchestration import graph_store
from master_finhub.orchestration.dag_engine import (
    MAX_CHECKPOINT_BYTES,
    CheckpointError,
    CheckpointStore,
)
from master_finhub.orchestration.graph import (
    GraphError,
    GraphEvent,
    GraphResumeBlocked,
    Limits,
    Node,
    build_graph,
    pipeline,
    resume_graph,
    run_graph,
    state_budget,
)
from master_finhub.orchestration.graph_store import (
    GraphCheckpoint,
    GraphStore,
    GraphWriter,
    NodeRecord,
    encode_graph_checkpoint,
)
from master_finhub.runtime.loop import LoopSnapshot, Message
from master_finhub.sandbox.workspace import Workspace

ROOT = Path(__file__).resolve().parent.parent
CHILD = Path(__file__).parent / "graph_child.py"
FIXED = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone(timedelta(hours=10)))
MARKER = "MARKER-client_a-acct_001"
LOGGER = "master_finhub.orchestration.graph"


def _store(root: Path) -> GraphStore:
    root.mkdir(parents=True, exist_ok=True)
    return make_store(root)


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def _child(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(CHILD), *args],
        env=_env(),
        capture_output=True,
        timeout=60,
        check=False,
    )


def _files(root: Path, run_id: str) -> list[str]:
    return sorted(p.name for p in (root / ".checkpoints" / run_id).glob("graph-*.json"))


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").split()


def _noop(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
    return "ok"


# --------------------------------------------------------------------------------- T5
def test_step_limit_halts_resumable(tmp_path: Path) -> None:
    side = tmp_path / "side.txt"

    def mk(name: str) -> Any:
        def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
            with open(side, "a", encoding="utf-8") as fh:
                fh.write(name + "\n")
            return name + "".join(deps.values())

        return fn

    g = build_graph(list(pipeline(*[Node(n, mk(n)) for n in "wxyz"])))
    store = _store(tmp_path / "ws")
    events: list[GraphEvent] = []
    first = run_graph(
        g, store=store, run_id="chain", limits=Limits(max_nodes=2), observer=events.append
    )
    assert (first.status, first.halt_reason, dict(first.outputs)) == ("halted", "step_limit", {})
    assert list(first.nodes.values()) == ["done", "done", "pending", "pending"]
    assert events[-1].kind == "run_halted"
    final = resume_graph(g, store, "chain", limits=Limits(max_nodes=1))
    assert final.status == "halted" and final.halt_reason == "step_limit"
    final = resume_graph(g, store, "chain", limits=Limits(max_nodes=8))
    assert final.status == "done" and final.outputs["z"] == "zyxw"
    assert _lines(side) == ["w", "x", "y", "z"], "each node ran exactly once"


# --------------------------------------------------------------------------------- T9
def test_kill_mid_graph_resume_equals_uninterrupted(tmp_path: Path) -> None:
    side, ws = tmp_path / "side.txt", tmp_path / "ws"
    ws.mkdir()
    done = _child("kill", str(ws), "kill-run", str(side), "idem")
    assert done.returncode == 9, done.stderr
    store = make_store(ws)
    latest = store.load("kill-run")
    assert latest.status == "running"
    assert {k: v.status for k, v in latest.nodes.items()} == {
        "a": "done",
        "b": "done",
        "c": "running",
        "d": "pending",
    }
    res = resume_graph(diamond(str(side), kill=False, c_idempotent=True), store, "kill-run")
    assert res.status == "done"
    assert _lines(side) == ["a", "b", "c", "c", "d"], "a and b were not run again"
    fresh_side = tmp_path / "fresh.txt"
    fresh = run_graph(
        diamond(str(fresh_side), kill=False, c_idempotent=True),
        INPUTS,
        limits=Limits(max_parallelism=1),
        store=_store(tmp_path / "ws2"),
        run_id="fresh",
    )
    assert dict(res.outputs) == dict(fresh.outputs) and res.outputs["d"].startswith("D(")


# --------------------------------------------------------------------------------- T10
def test_resume_running_not_idempotent_blocked(tmp_path: Path) -> None:
    side, ws = tmp_path / "side.txt", tmp_path / "ws"
    ws.mkdir()
    assert _child("kill", str(ws), "kr", str(side), "not").returncode == 9
    store = make_store(ws)
    before = _files(ws, "kr")
    g = diamond(str(side), kill=False, c_idempotent=False)
    with pytest.raises(GraphResumeBlocked) as info:
        resume_graph(g, store, "kr")
    assert info.value.node_ids == ("c",) and len(str(info.value).split("\n")) == 3
    assert _files(ws, "kr") == before, "nothing written by a refused resume"
    assert resume_graph(g, store, "kr", in_flight="rerun").status == "done"


def test_resume_reports_all_possibly_started(tmp_path: Path) -> None:
    release = threading.Event()
    store = _store(tmp_path)

    def slow(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        release.wait(30)
        return "x"

    g = build_graph([Node("b", slow), Node("c", slow)])
    res = run_graph(g, store=store, run_id="two", limits=Limits(max_parallelism=2, deadline_s=0.3))
    assert res.halt_reason == "deadline"
    release.set()
    _wait_resumable(g, store, "two")
    # both b and c finished in their threads but their results were discarded (still `running`)
    with pytest.raises(GraphResumeBlocked) as info:
        resume_graph(g, store, "two")
    assert info.value.node_ids == ("b", "c")


def _wait_resumable(g: Any, store: GraphStore, run_id: str) -> None:
    end = time.monotonic() + 10
    while time.monotonic() < end:
        try:
            resume_graph(g, store, run_id, limits=Limits(max_nodes=1), in_flight="stop")
        except GraphResumeBlocked as exc:
            if "still running in this process" not in str(exc):
                return
        except CheckpointError:
            pass
        except GraphError:
            return
        time.sleep(0.02)
    raise AssertionError("abandoned nodes never ended")


# --------------------------------------------------------------------------------- T11
def test_resume_changed_graph_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    g = build_graph(list(pipeline(Node("a", _noop), Node("b", _noop))))
    run_graph(g, store=store, run_id="chg", limits=Limits(max_nodes=1))
    before = _files(tmp_path, "chg")
    added = build_graph(list(pipeline(Node("a", _noop), Node("b", _noop), Node("e", _noop))))
    rewired = build_graph([Node("a", _noop), Node("b", _noop)])
    for other in (added, rewired):
        with pytest.raises(GraphError, match="different graph"):
            resume_graph(other, store, "chg")
    assert _files(tmp_path, "chg") == before
    new_fn = build_graph(list(pipeline(Node("a", lambda r, d: "z"), Node("b", _noop))))
    assert resume_graph(new_fn, store, "chg").status == "done"


# --------------------------------------------------------------------------------- T12 (file)
def test_marker_is_in_graph_file_only(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    g = build_graph([Node("a", lambda r, d: MARKER + r["k"])])
    store = _store(tmp_path)
    events: list[GraphEvent] = []
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        run_graph(g, {"k": MARKER}, store=store, run_id="m", observer=events.append)
    text = (tmp_path / ".checkpoints" / "m" / _files(tmp_path, "m")[-1]).read_text("utf-8")
    assert MARKER in text, "the test is looking in the right place"
    assert MARKER not in repr(events) + caplog.text  # the done result holds outputs by design


# --------------------------------------------------------------------------------- T13 (files)
def test_deterministic_files(tmp_path: Path) -> None:
    def once(name: str) -> list[dict[str, Any]]:
        g = build_graph(
            [
                Node("a", _noop),
                Node("b", _noop, ("a",)),
                Node("c", _noop, ("a",)),
                Node("d", _noop, ("b", "c")),
            ]
        )
        run_graph(g, store=_store(tmp_path / name), run_id="r", limits=Limits(max_parallelism=3))
        out = []
        for f in _files(tmp_path / name, "r"):
            doc = json.loads((tmp_path / name / ".checkpoints" / "r" / f).read_text("utf-8"))
            doc["state"]["saved_at"] = ""
            out.append(doc["state"])
        return out

    assert once("one") == once("two")


# --------------------------------------------------------------------------------- T14
def _agent_run(tmp_path: Path, run_id: str) -> CheckpointStore:
    cs = CheckpointStore(Workspace(tmp_path), clock=lambda: FIXED)
    with cs.create_run(run_id) as writer:
        writer(LoopSnapshot(0, (Message("user", "hi"),)))
    return cs


def test_slice5_files_compat(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    cs = _agent_run(tmp_path, "r1")
    store = GraphStore(cs)
    with pytest.raises(GraphError, match="single agent run"):
        store.resume("r1")
    g = build_graph([Node("a", _noop)])
    run_graph(g, store=store, run_id="gr")
    with pytest.raises(CheckpointError, match="graph run"):
        cs.resume_run("gr")
    # (c) a graph file renamed to a step file
    run = tmp_path / ".checkpoints" / "swapped"
    run.mkdir()
    (run / "step-000000.json").write_text(
        (tmp_path / ".checkpoints" / "gr" / "graph-000000.json").read_text("utf-8"), "utf-8"
    )
    with pytest.raises(CheckpointError, match=r"schema 2; this build reads 1"):
        cs.load("swapped")
    # (d) wrong schema numbers in a graph file
    for version in (1, 3):
        doc = json.loads(
            (tmp_path / ".checkpoints" / "gr" / "graph-000000.json").read_text("utf-8")
        )
        doc["schema_version"] = version
        bad = tmp_path / ".checkpoints" / f"v{version}"
        bad.mkdir()
        (bad / "graph-000000.json").write_text(json.dumps(doc), "utf-8")
        with pytest.raises(GraphError, match="different version") as info:
            store.load(f"v{version}")
        assert len(str(info.value).split("\n")) == 3
    # (e) both series in one folder
    mixed = tmp_path / ".checkpoints" / "mixed"
    mixed.mkdir()
    (mixed / "step-000000.json").write_text(
        (tmp_path / ".checkpoints" / "r1" / "step-000000.json").read_text("utf-8"), "utf-8"
    )
    (mixed / "graph-000000.json").write_text(
        (tmp_path / ".checkpoints" / "gr" / "graph-000000.json").read_text("utf-8"), "utf-8"
    )
    before = sorted(p.name for p in mixed.iterdir() if p.name != ".owner")
    with pytest.raises(CheckpointError, match="must not share a run folder"):
        cs.resume_run("mixed")
    with pytest.raises(GraphError, match="must not share a run folder"):
        store.resume("mixed")
    assert sorted(p.name for p in mixed.iterdir() if p.name != ".owner") == before


# --------------------------------------------------------------------------------- T20
def test_resume_done_run_returns_stored(tmp_path: Path) -> None:
    side = tmp_path / "side.txt"
    g = diamond(str(side), kill=False, c_idempotent=True)
    store = _store(tmp_path / "ws")
    first = run_graph(g, INPUTS, store=store, run_id="dn")
    log_before = _lines(side)
    again = resume_graph(g, store, "dn")
    assert again.status == "done" and dict(again.outputs) == dict(first.outputs)
    assert _lines(side) == log_before


# --------------------------------------------------------------------------------- T24
def test_ctrl_c_interrupts_wait(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    done = _child("sigint", str(ws))
    assert done.returncode == 0, done.stderr
    out = done.stdout.decode()
    elapsed = float(out.split("elapsed=")[1].split()[0])
    assert elapsed < 1.0 and "context_none=True" in out
    cp = make_store(ws).load("sig-run")
    assert (cp.status, cp.halt_reason, cp.nodes["slow"].status) == (
        "halted",
        "interrupted",
        "running",
    )
    g = build_graph([Node("slow", _noop)])
    with pytest.raises(GraphResumeBlocked):
        resume_graph(g, make_store(ws), "sig-run")


# --------------------------------------------------------------------------------- T25
def test_output_budget_never_poisons(tmp_path: Path) -> None:
    def big(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        return "\x00" * 300_000

    g = build_graph(list(pipeline(*[Node(f"n{i}", big) for i in range(8)])))
    store = _store(tmp_path)
    limits = Limits(max_output_bytes=2 * 1024 * 1024)
    res = run_graph(g, store=store, run_id="big", limits=limits)
    assert res.status == "failed" and res.outputs == {}
    assert [s for s in res.nodes.values()] == ["done"] * 4 + ["failed"] + ["skipped"] * 3
    assert dict(res.errors) == {"n4": "NodeOutputOverBudget"}
    for f in _files(tmp_path, "big"):
        assert (tmp_path / ".checkpoints" / "big" / f).stat().st_size <= MAX_CHECKPOINT_BYTES
    assert store.load("big").status == "failed"
    again = resume_graph(g, store, "big", limits=limits, in_flight="rerun")
    assert again.status == "failed" and dict(again.errors) == {"n4": "NodeOutputOverBudget"}


# --------------------------------------------------------------------------------- T26
def test_budget_bound_worst_case() -> None:
    names = [f"{'n' * 29}{i:03d}" for i in range(256)]
    assert all(len(n) == 32 for n in names)
    budget = state_budget(len(names))
    inputs = {f"{'i' * 29}{i:03d}": "" for i in range(64)}
    spent = sum(graph_mod.json_len(v) + graph_mod.INPUT_RESERVE_BYTES for v in inputs.values())
    per_node = (budget - spent) // len(names)
    for char, width in (("\x00", 6), ('"', 2), ("\\", 2), ("\U0001f600", 4), (" ", 3)):
        out = char * ((per_node - 2) // width)
        assert graph_mod.json_len(out) <= per_node
        nodes = {n: NodeRecord("done", output=out) for n in names}
        cp = GraphCheckpoint(
            "r" * 64, 999_999, FIXED, "sha256:" + "0" * 64, "running", None, inputs, nodes
        )
        assert len(encode_graph_checkpoint(cp)) <= MAX_CHECKPOINT_BYTES


# --------------------------------------------------------------------------------- T27
def test_abandoned_node_blocks_second_copy(tmp_path: Path) -> None:
    release = threading.Event()
    lock = threading.Lock()
    live = 0
    peak = 0

    def slow(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        release.wait(30)
        with lock:
            live -= 1
        return "late"

    g = build_graph([Node("w", slow)])
    store = _store(tmp_path)
    res = run_graph(g, store=store, run_id="ab", limits=Limits(deadline_s=0.3))
    assert (res.status, res.halt_reason) == ("halted", "deadline")
    assert "still running" in res.message
    before = _files(tmp_path, "ab")
    with pytest.raises(GraphResumeBlocked, match="still running in this process"):
        resume_graph(g, store, "ab", in_flight="rerun")
    assert _files(tmp_path, "ab") == before
    other = _child("resume", str(tmp_path), "ab", str(tmp_path / "unused.txt"))
    assert b"still running in another process" in other.stdout
    release.set()
    end = time.monotonic() + 10
    final = None
    while time.monotonic() < end and final is None:
        try:
            final = resume_graph(g, store, "ab", in_flight="rerun")
        except GraphError:
            time.sleep(0.02)
    assert final is not None and final.status == "done"
    assert peak <= 1


# --------------------------------------------------------------------------------- A70
def test_cleanup_failure_does_not_lose_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    real = GraphWriter.node_ended
    hooked: list[Any] = []
    monkeypatch.setattr(threading, "excepthook", lambda args: hooked.append(args))

    def boom(self: GraphWriter, node_id: str) -> None:
        real(self, node_id)
        raise OSError("MARKERclientA")

    monkeypatch.setattr(GraphWriter, "node_ended", boom)

    def bad(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        raise ValueError("x")

    g = build_graph([Node("a", _noop), Node("b", bad, ("a",)), Node("c", _noop, ("a",))])
    start = time.monotonic()
    res = run_graph(g, store=_store(tmp_path), run_id="cl", limits=Limits(max_parallelism=2))
    assert time.monotonic() - start < 5
    assert dict(res.nodes) == {"a": "done", "b": "failed", "c": "done"}
    assert dict(res.errors) == {"b": "ValueError"}
    assert hooked == [] and capfd.readouterr().err == ""


# --------------------------------------------------------------------------------- F-R2-1
def _count_unlocks(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    real = graph_store._unlock

    def counting(fd: int) -> None:
        calls.append(fd)
        real(fd)

    monkeypatch.setattr(graph_store, "_unlock", counting)
    return calls


def test_lock_release_is_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count_unlocks(monkeypatch)
    store = _store(tmp_path)
    writer = store.create("once")
    writer.close()
    writer.close()
    writer.node_ended("ghost")
    assert len(calls) == 1
    held = store.create("held")
    held.node_started("n")
    held.close()
    assert len(calls) == 1, "a live node keeps the lock"
    held.node_ended("n")
    held.node_ended("n")
    held.close()
    assert len(calls) == 2


def test_close_racing_node_end_releases_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _count_unlocks(monkeypatch)
    store = _store(tmp_path)
    for i in range(200):
        calls.clear()
        writer = store.create(f"race{i}")
        writer.node_started("n")
        gate = threading.Barrier(2)

        def end(g: threading.Barrier = gate, w: GraphWriter = writer) -> None:
            g.wait()
            w.node_ended("n")

        t = threading.Thread(target=end)
        t.start()
        gate.wait()
        writer.close()
        t.join()
        assert len(calls) == 1, f"iteration {i}"


# --------------------------------------------------------------------------------- F-R2-2
def test_thread_start_failure_leaves_no_stale_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    g = build_graph([Node("a", _noop)])
    store = _store(tmp_path)
    real_start = threading.Thread.start

    def failing(self: threading.Thread) -> None:
        if getattr(self, "_target", None) is graph_mod._work:
            raise RuntimeError("can't start new thread")
        real_start(self)

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", failing)
        res = run_graph(g, store=store, run_id="nostart")
    assert res.status == "failed" and dict(res.errors) == {"a": "RuntimeError"}
    final = resume_graph(g, store, "nostart", in_flight="rerun")  # lock free, nothing "live"
    assert final.status == "done"
