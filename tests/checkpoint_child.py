"""Helper run as a subprocess by tests/test_checkpoint.py (not collected: no test_ prefix).

Modes (argv[1]): ``kill`` (4-turn run, os._exit(9) after step 2), ``hold`` (own a run until
told to exit), ``race`` (resume a prepared run and re-run its pending tool). Synthetic data only.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from master_finhub.orchestration import dag_engine
from master_finhub.orchestration.dag_engine import CheckpointError, CheckpointStore
from master_finhub.runtime.loop import (
    AgentLoop,
    AssistantMessage,
    LoopSnapshot,
    Message,
    ToolCall,
    ToolSpec,
)
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.builtins.echo import EchoTool

PROMPT = "walk three steps"
RACE_EXIT_LOST = 3


class CountingLLM:
    """3 echo calls then a final answer. Each reply depends only on the messages so far."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.calls += 1
        done = [m.content for m in messages if m.role == "tool"]
        if len(done) < 3:
            call = ToolCall(f"call-{len(done) + 1}", "echo", {"text": f"part{len(done) + 1}"})
            return AssistantMessage("", [call])
        return AssistantMessage("final:" + "+".join(done))


class MarkerTool:
    """NOT idempotent: appends one line to a side-effect file every time it runs."""

    spec = ToolSpec("write_marker", "Append a line.", {"type": "object"})

    def __init__(self, path: str) -> None:
        self._path = path

    def run(self, arguments: dict[str, Any]) -> str:
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write("ran\n")
        return "marked"


class FinalLLM:
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        return AssistantMessage("finished")


def _kill(ws: str, run_id: str) -> None:
    store = CheckpointStore(Workspace(ws))
    writer = store.create_run(run_id)

    def hook(snap: LoopSnapshot) -> None:
        writer(snap)
        if snap.step == 2 and snap.status == "awaiting_model":
            os._exit(9)

    AgentLoop(CountingLLM(), [EchoTool()], checkpoint=hook).run(PROMPT)


def _hold(ws: str, run_id: str) -> None:
    writer = CheckpointStore(Workspace(ws)).create_run(run_id)
    writer(LoopSnapshot(0, (Message("user", PROMPT),)))
    print("ready", flush=True)
    sys.stdin.readline()
    os._exit(0)


def _race(ws: str, run_id: str, marker: str, start_at: float) -> None:
    dag_engine._try_lock = lambda fd: None  # test: claim layer alone
    store = CheckpointStore(Workspace(ws))
    cp, writer = store.resume_run(run_id)
    while time.time() < start_at:
        time.sleep(0.001)
    loop = AgentLoop(FinalLLM(), [MarkerTool(marker)], checkpoint=writer)
    try:
        loop.resume(cp.snapshot, in_flight="rerun")
    except CheckpointError:
        os._exit(RACE_EXIT_LOST)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "kill":
        _kill(sys.argv[2], sys.argv[3])
    elif mode == "hold":
        _hold(sys.argv[2], sys.argv[3])
    elif mode == "race":
        _race(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]))
    else:
        raise SystemExit(f"unknown mode {Path(mode).name}")
