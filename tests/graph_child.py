"""Helper run as a subprocess by tests/test_graph.py (not collected: no test_ prefix).

Modes (argv[1]): ``kill`` (diamond, os._exit(9) inside node c), ``resume`` (resume that diamond and
print the outcome), ``sigint`` (one blocked node, Ctrl-C at 0.3 s), ``cycle`` (print a cycle
message). Synthetic data only.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

from master_finhub.orchestration.dag_engine import CheckpointStore
from master_finhub.orchestration.graph import (
    Graph,
    GraphError,
    Limits,
    Node,
    build_graph,
    resume_graph,
    run_graph,
)
from master_finhub.orchestration.graph_store import GraphStore
from master_finhub.sandbox.workspace import Workspace

FIXED = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone(timedelta(hours=10)))


def make_store(ws: str | Path) -> GraphStore:
    return GraphStore(CheckpointStore(Workspace(ws), clock=lambda: FIXED))


def diamond(side: str, *, kill: bool, c_idempotent: bool) -> Graph:
    """a -> (b, c) -> d. Each node appends its id to the side-effect file when it runs."""

    def log(name: str) -> None:
        with open(side, "a", encoding="utf-8") as fh:
            fh.write(name + "\n")

    def a(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("a")
        return "A:" + run["client"]

    def b(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("b")
        return "B(" + deps["a"] + ")"

    def c(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("c")
        if kill:
            os._exit(9)
        return "C(" + deps["a"] + ")"

    def d(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("d")
        return "D(" + deps["b"] + "+" + deps["c"] + ")"

    return build_graph(
        [
            Node("a", a),
            Node("b", b, ("a",), idempotent=True),
            Node("c", c, ("a",), idempotent=c_idempotent),
            Node("d", d, ("b", "c"), idempotent=True),
        ]
    )


INPUTS = {"client": "client_a"}


def _sigint(ws: str) -> None:
    release = threading.Event()

    def blocker(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        release.wait(60)
        return "never"

    graph = build_graph([Node("slow", blocker)])
    threading.Timer(0.3, lambda: signal.raise_signal(signal.SIGINT)).start()
    start = time.monotonic()
    try:
        run_graph(graph, store=make_store(ws), run_id="sig-run", limits=Limits(deadline_s=None))
    except KeyboardInterrupt as exc:
        print(
            f"elapsed={time.monotonic() - start:.3f} context_none={exc.__context__ is None}",
            flush=True,
        )
        os._exit(0)
    print("no interrupt")
    os._exit(1)


def _cycle() -> None:
    try:
        build_graph([Node("a", _noop, ("c",)), Node("b", _noop, ("a",)), Node("c", _noop, ("b",))])
    except GraphError as exc:
        print(str(exc).replace("\n", " | "))


def _noop(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
    return ""


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "kill":
        ws, run_id, side = sys.argv[2], sys.argv[3], sys.argv[4]
        run_graph(
            diamond(side, kill=True, c_idempotent=sys.argv[5] == "idem"),
            INPUTS,
            limits=Limits(max_parallelism=1),
            store=make_store(ws),
            run_id=run_id,
        )
    elif mode == "resume":
        ws, run_id, side = sys.argv[2], sys.argv[3], sys.argv[4]
        try:
            res = resume_graph(diamond(side, kill=False, c_idempotent=True), make_store(ws), run_id)
            print("status=" + res.status)
        except (GraphError, RuntimeError) as exc:
            print(str(exc).split("\n")[0])
    elif mode == "sigint":
        _sigint(sys.argv[2])
    elif mode == "cycle":
        _cycle()
    else:
        raise SystemExit(f"unknown mode {Path(mode).name}")
