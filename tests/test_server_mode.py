"""The server runs every run's tool calls under a permission mode."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar

import pytest

from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import AssistantMessage, Message, ToolCall, ToolSpec
from master_finhub.sandbox.workspace import WORKSPACE_ENV_VAR
from master_finhub.server import app
from master_finhub.server.app import SESSION_HEADER, RunServer, make_server
from master_finhub.tools import guard_factory
from master_finhub.tools.builtins.echo import EchoTool


class _WriteTool:
    spec = ToolSpec("wr", "write a file", {"type": "object"})
    ran: ClassVar[list[dict[str, Any]]] = []

    def run(self, arguments: dict[str, Any]) -> str:
        _WriteTool.ran.append(arguments)
        return "wrote"


class _CallsWrite:
    path = "notes.txt"

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        if messages[-1].role == "tool":
            return AssistantMessage(messages[-1].content)
        return AssistantMessage("", [ToolCall("c", "wr", {"path": self.path, "content": "x"})])


class _CallsEnv(_CallsWrite):
    path = ".claude/settings.json"


@contextmanager
def running(**kw: Any) -> Iterator[RunServer]:
    kw.setdefault("llm_factory", ScriptedLLM)
    kw.setdefault("tools_factory", lambda: [EchoTool()])
    srv = make_server(**kw)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(5)


def final_data(srv: RunServer, prompt: str = "go") -> str:
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
    c.request(
        "POST",
        "/runs",
        body=json.dumps({"prompt": prompt}).encode(),
        headers={SESSION_HEADER: srv.session_key},
    )
    rid = json.loads(c.getresponse().read())["run_id"]
    c.close()
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
    c.request("GET", f"/runs/{rid}/events", headers={SESSION_HEADER: srv.session_key})
    raw = c.getresponse().read().decode()
    c.close()
    frames = [b for b in raw.split("\n\n") if "event: done" in b]
    return frames[-1].split("data: ", 1)[1].split("\n", 1)[0]


@pytest.fixture()
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, str(tmp_path))
    return tmp_path


def test_default_mode_is_workspace_write_with_the_default_tool_classes(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, dict[str, str]]] = []
    real = guard_factory.effective_guard

    def spy(mode, workspace, *, tool_classes=None, **kw):  # type: ignore[no-untyped-def]
        seen.append((mode, dict(tool_classes or {})))
        return real(mode, workspace, tool_classes=tool_classes, **kw)

    monkeypatch.setattr(guard_factory, "effective_guard", spy)
    with running() as srv:
        assert final_data(srv, "echo hi") == '"hi"'
    assert seen == [("workspace-write", {"echo": "read"})]


@pytest.mark.parametrize("mode", ["read-only", "workspace-write", "full-access"])
def test_echo_runs_in_every_mode(mode: str, ws: Path) -> None:
    with running(mode=mode) as srv:
        assert final_data(srv, "echo hi") == '"hi"'


def test_read_only_refuses_a_write_tool(ws: Path) -> None:
    _WriteTool.ran = []
    with running(
        llm_factory=_CallsWrite,
        tools_factory=lambda: [_WriteTool()],
        mode="read-only",
        tool_classes={"wr": "write"},
    ) as srv:
        data = final_data(srv)
    assert data.startswith('"Error:') and "read-only" in data
    assert _WriteTool.ran == []


def test_workspace_write_allows_a_write_inside_the_workspace(ws: Path) -> None:
    _WriteTool.ran = []
    with running(
        llm_factory=_CallsWrite,
        tools_factory=lambda: [_WriteTool()],
        mode="workspace-write",
        tool_classes={"wr": "write"},
    ) as srv:
        assert final_data(srv) == '"wrote"'
    assert len(_WriteTool.ran) == 1


def test_workspace_write_refuses_a_protected_path(ws: Path) -> None:
    _WriteTool.ran = []
    with running(
        llm_factory=_CallsEnv, tools_factory=lambda: [_WriteTool()], tool_classes={"wr": "write"}
    ) as srv:
        data = final_data(srv)
    assert data.startswith('"Error:') and "protected" in data
    assert _WriteTool.ran == []


def test_an_unlisted_tool_is_refused_in_read_only(ws: Path) -> None:
    _WriteTool.ran = []
    with running(
        llm_factory=_CallsWrite, tools_factory=lambda: [_WriteTool()], mode="read-only"
    ) as srv:
        data = final_data(srv)
    assert data.startswith('"Error:') and "unknown tool" in data
    assert _WriteTool.ran == []


def test_without_a_workspace_folder_only_read_tools_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "/nonexistent-folder-for-test")
    _WriteTool.ran = []
    with running() as srv:  # echo is classed read
        assert final_data(srv, "echo hi") == '"hi"'
    with running(
        llm_factory=_CallsWrite, tools_factory=lambda: [_WriteTool()], tool_classes={"wr": "write"}
    ) as srv:
        data = final_data(srv)
    assert data.startswith('"Error:') and "workspace" in data
    assert _WriteTool.ran == []


def test_extra_guard_still_only_adds_denials_under_a_mode(ws: Path) -> None:
    with running(mode="full-access", extra_guard=lambda c: "blocked by extra") as srv:
        assert final_data(srv, "echo hi") == '"Error: blocked by extra"'


def test_base_command_guard_still_runs_in_full_access(ws: Path) -> None:
    class _Sh:
        spec = ToolSpec("sh", "run", {"type": "object"})
        ran = False

        def run(self, arguments: dict[str, Any]) -> str:
            _Sh.ran = True
            return "ran"

    class _CallsRm:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            if messages[-1].role == "tool":
                return AssistantMessage(messages[-1].content)
            return AssistantMessage("", [ToolCall("c", "sh", {"command": "rm -rf /"})])

    with running(
        llm_factory=_CallsRm,
        tools_factory=lambda: [_Sh()],
        mode="full-access",
        tool_classes={"sh": "shell"},
    ) as srv:
        assert final_data(srv).startswith('"Error:')
    assert not _Sh.ran


def test_main_passes_the_mode_and_the_tool_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[dict[str, Any]] = []
    real = app.make_server

    def spy(llm_factory: Any, tools_factory: Any, **kw: Any) -> RunServer:
        made.append(kw)
        return real(llm_factory, tools_factory, **kw)

    monkeypatch.setattr(app, "make_server", spy)
    monkeypatch.setattr(app.RunServer, "serve_forever", lambda self, *a, **k: None)
    assert app.main(["--mode", "read-only"]) == 0
    assert app.main([]) == 0
    assert made[0]["mode"] == "read-only" and made[0]["tool_classes"] == {"echo": "read"}
    assert made[1]["mode"] == "workspace-write"


def test_main_rejects_an_unknown_mode(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        app.main(["--mode", "root"])
    assert stop.value.code == 2
    assert "read-only" in capsys.readouterr().err
