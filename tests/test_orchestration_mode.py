"""Sub-agent and team modes can run their tool calls under a permission mode (opt-in)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from modes_support import FnLLM, _quiet_after, call, say  # noqa: F401 - autouse fixture

from master_finhub.orchestration.modes.subagent import (
    ENGINE_TOOL_CLASSES,
    SubagentConfig,
    SubTask,
    dispatch,
)
from master_finhub.orchestration.modes.task_board import TaskSpec
from master_finhub.orchestration.modes.team import Persona, run_team
from master_finhub.runtime.loop import Message, ToolSpec
from master_finhub.sandbox.workspace import WORKSPACE_ENV_VAR
from master_finhub.tools import guard_factory


class _Write:
    spec = ToolSpec("wr", "write a file", {"type": "object"})
    ran: ClassVar[int] = 0

    def run(self, arguments: dict[str, Any]) -> str:
        _Write.ran += 1
        return "wrote"


def _fn(path: str) -> Any:
    def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.role == "tool":
            return say(last.content)
        return call("wr", path=path, content="x")

    return fn


@pytest.fixture()
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, str(tmp_path))
    _Write.ran = 0
    return tmp_path


def _dispatch(mode: str | None, path: str = "notes.txt") -> str:
    cfg = SubagentConfig(
        llm_for=lambda t: FnLLM(_fn(path)),
        tools_for=lambda t: [_Write()],
        mode=mode,  # type: ignore[arg-type]
        tool_classes={"wr": "write"},
    )
    result = dispatch([SubTask("w1", "go")], config=cfg)
    return result.results["w1"].output or ""


def test_subagent_read_only_refuses_a_write_tool(ws: Path) -> None:
    out = _dispatch("read-only")
    assert out.startswith("Error:") and "read-only" in out
    assert _Write.ran == 0


def test_subagent_workspace_write_allows_a_write_inside_the_workspace(ws: Path) -> None:
    assert _dispatch("workspace-write") == "wrote"
    assert _Write.ran == 1


def test_subagent_workspace_write_refuses_a_protected_path(ws: Path) -> None:
    out = _dispatch("workspace-write", ".claude/settings.json")
    assert out.startswith("Error:") and "protected" in out
    assert _Write.ran == 0


def test_subagent_without_a_mode_is_unchanged(ws: Path) -> None:
    assert _dispatch(None) == "wrote"
    assert _Write.ran == 1


def test_subagent_mode_goes_through_the_shared_guard_factory(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, dict[str, str]]] = []
    real = guard_factory.build_guard

    def spy(mode: Any, tool_classes: Any = None) -> Any:
        seen.append((mode, dict(tool_classes or {})))
        return real(mode, tool_classes)

    monkeypatch.setattr("master_finhub.orchestration.modes.subagent.build_guard", spy)
    _dispatch("read-only")
    assert seen == [("read-only", {**ENGINE_TOOL_CLASSES, "wr": "write"})]


def test_subagent_base_command_guard_still_runs_in_full_access(ws: Path) -> None:
    class _Sh:
        spec = ToolSpec("sh", "run", {"type": "object"})
        ran = False

        def run(self, arguments: dict[str, Any]) -> str:
            _Sh.ran = True
            return "ran"

    def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        if messages[-1].role == "tool":
            return say(messages[-1].content)
        return call("sh", command="rm -rf /")

    cfg = SubagentConfig(
        llm_for=lambda t: FnLLM(fn),
        tools_for=lambda t: [_Sh()],
        mode="full-access",
        tool_classes={"sh": "shell"},
    )
    out = dispatch([SubTask("w1", "go")], config=cfg).results["w1"].output or ""
    assert out.startswith("Error:") and not _Sh.ran


def _team(mode: str | None, path: str = "notes.txt", **kw: Any) -> str:
    seen: list[str] = []

    def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("wr", path=path, content="x")
        if last.role == "tool" and last.tool_call_id == "c-wr":
            seen.append(last.content)
            return call("complete_task", task_id="t1", result="done")
        return say("ok")

    result = run_team(
        [Persona("ops-agent", "builder", tools=(_Write(),))],
        [TaskSpec("t1", "x")],
        llm_for=lambda p: FnLLM(fn),
        mode=mode,  # type: ignore[arg-type]
        tool_classes={"wr": "write"},
        **kw,
    )
    assert result.status == "done"
    return seen[0]


def test_team_read_only_refuses_a_write_tool(ws: Path) -> None:
    out = _team("read-only")
    assert out.startswith("Error:") and "read-only" in out and _Write.ran == 0


def test_team_workspace_write_allows_a_write_inside_the_workspace(ws: Path) -> None:
    assert _team("workspace-write") == "wrote" and _Write.ran == 1


def test_team_without_a_mode_is_unchanged(ws: Path) -> None:
    assert _team(None) == "wrote" and _Write.ran == 1


def test_team_explicit_guard_still_adds_denials_beside_the_mode(ws: Path) -> None:
    out = _team("workspace-write", guard=lambda c: "blocked by extra" if c.name == "wr" else None)
    assert out == "Error: blocked by extra" and _Write.ran == 0
