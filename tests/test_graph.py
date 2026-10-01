"""Slice 6 proof tests, part 1: model, validation and execution without a store (synthetic data)."""

from __future__ import annotations

import ast
import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from master_finhub.orchestration import graph as graph_mod
from master_finhub.orchestration.graph import (
    GraphError,
    GraphEvent,
    Limits,
    Node,
    build_graph,
    exception_name,
    parallel,
    pipeline,
    run_graph,
)
from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import AgentLoop
from master_finhub.tools.builtins.echo import EchoTool

ROOT = Path(__file__).resolve().parent.parent
MARKER = "MARKER-client_a-acct_001"
LOGGER = "master_finhub.orchestration.graph"


def _out(text: str) -> Any:
    def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        return text + "(" + ",".join(f"{k}={deps[k]}" for k in sorted(deps)) + ")"

    return fn


def _fail(exc: BaseException) -> Any:
    def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        raise exc

    return fn


def _diamond(order: list[str] | None = None) -> Any:
    def mk(name: str) -> Any:
        base = _out(name.upper())

        def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
            if order is not None:
                order.append(name)
            return str(base(run, deps))

        return fn

    return build_graph(
        [
            Node("a", mk("a")),
            Node("b", mk("b"), ("a",)),
            Node("c", mk("c"), ("a",)),
            Node("d", mk("d"), ("b", "c")),
        ]
    )


# --------------------------------------------------------------------------------- T1
@pytest.mark.parametrize("width", [1, 2])
def test_diamond_order(width: int) -> None:
    order: list[str] = []
    res = run_graph(_diamond(order), limits=Limits(max_parallelism=width))
    assert order[0] == "a" and order[-1] == "d" and sorted(order[1:3]) == ["b", "c"]
    assert res.status == "done" and res.outputs["d"] == "D(b=B(a=A()),c=C(a=A()))"


# --------------------------------------------------------------------------------- T2
def test_concurrency_bound_honoured() -> None:
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    active = 0
    peak = 0

    def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait()
        with lock:
            active -= 1
        return "ok"

    g = build_graph([Node(f"n{i}", fn) for i in range(4)])
    res = run_graph(g, limits=Limits(max_parallelism=2))
    assert res.status == "done" and peak == 2


# --------------------------------------------------------------------------------- T3 / T4
def _noop(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
    return MARKER


@pytest.mark.parametrize(
    "nodes, must_have, must_not",
    [
        ([Node("a", _noop, ("b",)), Node("b", _noop, ("a",))], ("a", "b"), ()),
        ([Node("a", _noop, ("a",))], ("a",), ()),
        ([Node("a", _noop, ("ghost",))], ("ghost",), ()),
        ([Node("b", _noop), Node("b", _noop)], ("b",), ()),
        ([Node("a", _noop), Node("B!", _noop)], ("Node 2",), ("B!",)),
        ([], (), ()),
        ([Node(f"n{i}", _noop) for i in range(257)], ("257",), ()),
        ([Node("a", _noop), Node("b", _noop, ("a", "a"))], ("b",), ()),
    ],
    ids=["cycle", "self", "unknown", "duplicate", "bad-id", "empty", "too-many", "dup-dep"],
)
def test_build_errors_name_ids_only(
    nodes: list[Node], must_have: tuple[str, ...], must_not: tuple[str, ...]
) -> None:
    with pytest.raises(GraphError) as info:
        build_graph(nodes)
    err = info.value
    assert len(str(err).split("\n")) == 3
    assert all(s in str(err) for s in must_have) and not any(s in str(err) for s in must_not)
    assert err.__cause__ is None and err.__suppress_context__ is True
    assert MARKER not in str(err) + repr(err) + repr(err.args)


def test_unknown_dep_not_invented() -> None:
    ran: list[str] = []

    def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        ran.append("x")
        return "x"

    with pytest.raises(GraphError):
        run_graph(build_graph([Node("a", fn, ("ghost",))]))
    assert ran == []


# --------------------------------------------------------------------------------- T6
class _Tick:
    def __init__(self, step: float) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def test_deadline_with_injected_clock() -> None:
    g = build_graph(list(pipeline(*[Node(f"n{i}", _noop) for i in range(4)])))
    events: list[GraphEvent] = []
    res = run_graph(g, limits=Limits(deadline_s=25), monotonic=_Tick(10.0), observer=events.append)
    assert res.status == "halted" and res.halt_reason == "deadline"
    assert "done" in res.nodes.values() and "done" != res.nodes["n3"]
    assert res.outputs == {} and events[-1].kind == "run_halted"
    assert events[-1].halt_reason == "deadline"


# --------------------------------------------------------------------------------- T7
def test_node_exception_wrapped(caplog: pytest.LogCaptureFixture) -> None:
    cause = RuntimeError(MARKER)
    bad = ValueError(MARKER)
    bad.__cause__ = cause
    named = type("MARKERclientA", (Exception,), {})
    odd = type("bad name!", (Exception,), {})
    g = build_graph(
        [
            Node("b", _fail(bad)),
            Node("c", _fail(named(MARKER))),
            Node("d", _fail(odd(MARKER))),
            Node("e", _fail(TimeoutError(MARKER))),
        ]
    )
    events: list[GraphEvent] = []
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        res = run_graph(g, observer=events.append)
    assert res.status == "failed"
    assert dict(res.errors) == {
        "b": "ValueError",
        "c": "Exception",
        "d": "Exception",
        "e": "TimeoutError",
    }
    blob = repr(res) + repr(events) + caplog.text
    assert MARKER not in blob and "MARKERclientA" not in blob


# --------------------------------------------------------------------------------- T8
def test_downstream_skipped_independent_continues() -> None:
    g = build_graph(
        [
            Node("a", _noop),
            Node("b", _fail(ValueError("x")), ("a",)),
            Node("c", _noop, ("a",)),
            Node("d", _noop, ("b",)),
        ]
    )
    events: list[GraphEvent] = []
    res = run_graph(g, observer=events.append)
    assert res.status == "failed" and res.outputs == {}
    assert dict(res.nodes) == {"a": "done", "b": "failed", "c": "done", "d": "skipped"}
    tail = [(e.kind, e.node_id) for e in events[-4:]]  # b and c ran in one batch, id order
    assert tail == [
        ("node_failed", "b"),
        ("node_finished", "c"),
        ("node_skipped", "d"),
        ("run_finished", None),
    ]


# --------------------------------------------------------------------------------- T13
def test_deterministic_events() -> None:
    def once() -> list[tuple[Any, ...]]:
        evs: list[GraphEvent] = []
        run_graph(_diamond(), limits=Limits(max_parallelism=3), observer=evs.append)
        return [(e.kind, e.seq, e.node_id, e.status, dict(e.counts)) for e in evs]

    assert once() == once()


# --------------------------------------------------------------------------------- T15
def test_engine_does_not_import_loop() -> None:
    tree = ast.parse(Path(graph_mod.__file__).read_text(encoding="utf-8"))
    mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    ]
    assert not any(m.startswith("master_finhub.runtime") for m in mods)
    agent = lambda run, deps: AgentLoop(ScriptedLLM(), [EchoTool()]).run("echo hi")
    assert run_graph(build_graph([Node("agent", agent)])).outputs == {"agent": "hi"}


# --------------------------------------------------------------------------------- T16
def test_output_rules() -> None:
    class Sub(str):
        def encode(self, *a: Any, **k: Any) -> bytes:  # type: ignore[override]
            raise AssertionError("encode must never run")

    def returning(value: Any) -> Any:
        return lambda run, deps: value

    g = build_graph(
        [
            Node("a", returning(3)),
            Node("b", returning("\ud800")),
            Node("c", returning("x" * 1001)),
            Node("d", returning("a" * 998)),
            Node("e", returning("\x00" * 166)),
            Node("f", returning("\x00" * 167)),
            Node("g", returning(Sub("x"))),
        ]
    )
    res = run_graph(g, limits=Limits(max_output_bytes=1000, max_parallelism=7))
    assert dict(res.errors) == {
        "a": "NodeOutputNotText",
        "b": "NodeOutputNotStorable",
        "c": "NodeOutputTooLarge",
        "f": "NodeOutputTooLarge",
        "g": "NodeOutputNotText",
    }
    assert res.nodes["d"] == "done" and res.nodes["e"] == "done"


# --------------------------------------------------------------------------------- T17
def test_observer_errors_contained(caplog: pytest.LogCaptureFixture) -> None:
    def bad(ev: GraphEvent) -> None:
        raise RuntimeError(MARKER)

    seen: list[GraphEvent] = []

    def both(ev: GraphEvent) -> None:
        seen.append(ev)
        bad(ev)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        res = run_graph(_diamond(), observer=both)
    assert res.status == "done" and res.observer_errors == len(seen)
    warned = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warned) == len(seen) and all("RuntimeError" in r.getMessage() for r in warned)
    assert MARKER not in caplog.text


def test_observer_keyboard_interrupt_not_swallowed() -> None:
    def obs(ev: GraphEvent) -> None:
        if ev.kind == "node_started":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_graph(_diamond(), observer=obs)


# --------------------------------------------------------------------------------- T18
def test_pipeline_parallel_helpers() -> None:
    a, b, c = (Node(i, _noop) for i in "abc")
    chain = pipeline(a, b, c)
    assert [n.deps for n in chain] == [(), ("a",), ("b",)] and a.deps == ()
    fan = parallel(b, c, after=("a",))
    assert [n.deps for n in fan] == [("a",), ("a",)]


# --------------------------------------------------------------------------------- T19
def test_limits_validated() -> None:
    g = build_graph([Node("a", _noop)])
    for bad in (
        Limits(max_nodes=0),
        Limits(max_parallelism=0),
        Limits(max_parallelism=33),
        Limits(deadline_s=0),
        Limits(max_output_bytes=10**9),
    ):
        with pytest.raises(GraphError):
            run_graph(g, limits=bad)
    too_many = {f"k{i}": "v" for i in range(65)}
    for inputs in (too_many, {"Bad Key": "v"}, {"k": 3}, {"k": "x" * 9_000_000}, {"k": "\ud800"}):
        with pytest.raises(GraphError):
            run_graph(g, inputs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------------- T21
def test_ready_nodes_carry_over() -> None:
    g = build_graph([Node(f"n{i}", _noop) for i in range(1, 7)])
    events: list[GraphEvent] = []
    res = run_graph(g, limits=Limits(max_parallelism=2), observer=events.append)
    assert res.status == "done"
    started = [e.node_id for e in events if e.kind == "node_started"]
    assert started == ["n1", "n2", "n3", "n4", "n5", "n6"]


# --------------------------------------------------------------------------------- T22
class _ErrnoBomb(OSError):
    @property  # type: ignore[override]
    def errno(self) -> int:
        raise RuntimeError("MARKERclientA")

    def __str__(self) -> str:
        raise RuntimeError("MARKERclientA")

    def __repr__(self) -> str:
        raise RuntimeError("MARKERclientA")


class _NameMeta(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        raise RuntimeError("MARKERclientA")


class _MetaBomb(Exception, metaclass=_NameMeta):
    pass


class _ClassBomb(Exception):
    @property  # type: ignore[override]
    def __class__(self) -> type:  # type: ignore[override]
        raise RuntimeError("MARKERclientA")


def test_hostile_exception_in_worker(
    capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    hooked: list[Any] = []
    monkeypatch.setattr(threading, "excepthook", lambda args: hooked.append(args))
    g = build_graph(
        [
            Node("n1", _fail(_ErrnoBomb(5, "x"))),
            Node("n2", _fail(_MetaBomb())),
            Node("n3", _fail(_ClassBomb())),
            Node("n4", _fail(SystemExit(3))),
            Node("n5", _fail(KeyboardInterrupt())),
        ]
    )
    start = time.monotonic()
    events: list[GraphEvent] = []
    res = run_graph(g, limits=Limits(deadline_s=None, max_parallelism=5), observer=events.append)
    assert time.monotonic() - start < 5
    assert dict(res.errors) == {
        "n1": "Exception",
        "n2": "Exception",
        "n3": "Exception",
        "n4": "SystemExit",
        "n5": "KeyboardInterrupt",
    }
    captured = capfd.readouterr()
    assert captured.err == "" and hooked == []
    assert "MARKERclientA" not in captured.out + repr(res) + repr(events)


def test_exception_name_by_identity() -> None:
    assert exception_name(ValueError) == "ValueError"
    assert exception_name(type("ValueError", (Exception,), {})) == "Exception"
    assert exception_name(ExceptionGroup) == "ExceptionGroup"


# --------------------------------------------------------------------------------- T12
def test_no_content_in_events_logs_errors(caplog: pytest.LogCaptureFixture) -> None:
    bad_cls = type("MARKERclientA", (Exception,), {})
    g = build_graph(
        [
            Node("a", lambda run, deps: MARKER + run["k"]),
            Node("b", _fail(bad_cls(MARKER)), ("a",)),
            Node("c", _fail(ValueError(MARKER)), ("a",)),
        ]
    )
    events: list[GraphEvent] = []
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        res = run_graph(g, {"k": MARKER}, observer=events.append)
    blob = repr(events) + caplog.text + repr(res) + repr(dict(res.errors)) + res.message
    assert MARKER not in blob and "MARKERclientA" not in blob
    assert res.status == "failed" and res.errors["b"] == "Exception"


# --------------------------------------------------------------------------------- T28
def test_stable_cycle_text_across_hash_seeds() -> None:
    child = Path(__file__).parent / "graph_child.py"
    texts = set()
    for seed in range(8):
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": str(seed)}
        done = subprocess.run(
            [sys.executable, str(child), "cycle"],
            env=env,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        texts.add(done.stdout)
    assert len(texts) == 1 and b"a" in next(iter(texts))
