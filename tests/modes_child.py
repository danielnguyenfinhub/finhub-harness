"""Helper run as a subprocess by tests/test_modes.py (not collected: no test_ prefix).

Workflow mode through ``modes.workflow``: ``kill`` runs fetch (an AgentLoop node) -> check -> note
and dies with ``os._exit(9)`` inside ``check``; ``resume`` finishes the run. Synthetic data only.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

from graph_child import make_store

from master_finhub.orchestration.modes.workflow import (
    Graph,
    Node,
    build_graph,
    pipeline,
    resume_graph,
    run_graph,
)
from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import AgentLoop
from master_finhub.tools.builtins.echo import EchoTool


def workflow(side: str, *, kill: bool) -> Graph:
    def log(name: str) -> None:
        with open(side, "a", encoding="utf-8") as fh:
            fh.write(name + "\n")

    def fetch(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("fetch")
        return AgentLoop(ScriptedLLM(), [EchoTool()]).run("echo " + run["topic"])

    def check(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("check")
        if kill:
            os._exit(9)
        return "CHECKED(" + deps["fetch"] + ")"

    def note(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        log("note")
        return "NOTE(" + deps["check"] + ")"

    return build_graph(
        pipeline(
            Node("fetch", fetch),
            Node("check", check, idempotent=not kill),
            Node("note", note, idempotent=True),
        )
    )


if __name__ == "__main__":
    mode, ws, run_id, side = sys.argv[1:5]
    if mode == "kill":
        run_graph(
            workflow(side, kill=True),
            {"topic": "synthetic-topic"},
            store=make_store(ws),
            run_id=run_id,
        )
    else:
        res = resume_graph(workflow(side, kill=False), make_store(ws), run_id)
        print("status=" + res.status)
        print("note=" + res.outputs["note"])
