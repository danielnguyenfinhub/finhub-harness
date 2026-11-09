"""The CLI can load MCP servers from a config file; the mode guard judges their tools."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from master_finhub import cli
from master_finhub.runtime.loop import AgentLoop, ToolCall
from master_finhub.sandbox.workspace import WORKSPACE_ENV_VAR
from master_finhub.tools.mcp.loader import McpConfigError, open_mcp, read_config

STUB = str(Path(__file__).with_name("mcp_stub_server.py"))


@pytest.fixture()
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, str(tmp_path))
    return tmp_path


def write_config(tmp_path: Path, **server: Any) -> Path:
    entry: dict[str, Any] = {
        "name": "stub",
        "command": [sys.executable, STUB],
        "trusted_read_only": ["echo"],
    }
    entry.update(server)
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"servers": [entry]}), encoding="utf-8")
    return path


def capture_loop(monkeypatch: pytest.MonkeyPatch) -> list[AgentLoop]:
    made: list[AgentLoop] = []
    real = AgentLoop.__init__

    def spy(self: AgentLoop, *a: Any, **kw: Any) -> None:
        real(self, *a, **kw)
        made.append(self)

    monkeypatch.setattr(AgentLoop, "__init__", spy)
    return made


def mcp_names(loop: AgentLoop) -> dict[str, str]:
    """server's own tool name -> public tool name, for the MCP tools of a loop."""
    return {t.tool_name: n for n, t in loop._tools.items() if hasattr(t, "tool_name")}  # type: ignore[attr-defined]


# ----------------------------------------------------------------------------- config
@pytest.mark.parametrize(
    "bad",
    [
        {"servers": "x"},
        {"servers": [{"name": "s"}]},
        {"servers": [{"name": "s", "command": []}]},
        {"servers": [{"name": "s", "command": ["x"], "typo": 1}]},
        {"servers": [{"name": "s", "command": ["x"], "env": {"A": 1}}]},
        {"servers": [{"name": "s", "command": ["x"], "trusted_read_only": "echo"}]},
        {"servers": [{"name": "s", "command": ["x"]}, {"name": "s", "command": ["y"]}]},
        {"extra": 1, "servers": []},
        [],
    ],
)
def test_bad_config_is_refused(tmp_path: Path, bad: Any) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(McpConfigError):
        read_config(path)


def test_missing_and_unparseable_config_are_refused(tmp_path: Path) -> None:
    with pytest.raises(McpConfigError):
        read_config(tmp_path / "nope.json")
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(McpConfigError):
        read_config(tmp_path / "bad.json")


# ----------------------------------------------------------------------------- loader
def test_open_mcp_classes_trusted_names_read_and_leaves_the_rest_unknown(tmp_path: Path) -> None:
    cfg = write_config(tmp_path)
    with open_mcp(cfg) as bundle:
        by_raw = {t.tool_name: t.spec.name for t in bundle.tools}
        assert set(by_raw) == {"echo", "fail"}
        assert bundle.tool_classes == {by_raw["echo"]: "read"}
        assert bundle.quarantined == []


def test_open_mcp_uses_the_operators_tool_classes(tmp_path: Path) -> None:
    cfg = write_config(tmp_path, tool_classes={"fail": "write"})
    with open_mcp(cfg) as bundle:
        by_raw = {t.tool_name: t.spec.name for t in bundle.tools}
        assert bundle.tool_classes == {by_raw["echo"]: "read", by_raw["fail"]: "write"}


@pytest.mark.parametrize(
    "extra",
    [
        {"tool_classes": {"fail": "root"}},
        {"tool_classes": ["fail"]},
        {"tool_classes": {"echo": "write"}},  # echo is also in trusted_read_only
    ],
)
def test_bad_tool_classes_are_refused(tmp_path: Path, extra: dict[str, Any]) -> None:
    with pytest.raises(McpConfigError):
        read_config(write_config(tmp_path, **extra))


def test_approvals_are_kept_in_a_private_directory_next_to_the_config(tmp_path: Path) -> None:
    cfg = write_config(tmp_path)
    with open_mcp(cfg):
        pass
    store = tmp_path / "mcp.json.approvals" / "stub.json"
    assert store.is_file()
    if os.name == "posix":
        assert stat.S_IMODE(store.stat().st_mode) == 0o600
        assert stat.S_IMODE(store.parent.stat().st_mode) == 0o700


ONE_TOOL_SERVER = """
import json, os, sys
for line in sys.stdin:
    m = json.loads(line)
    i = m.get("id")
    if i is None:
        continue
    if m["method"] == "initialize":
        r = {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "s", "version": "0"}}
    elif m["method"] == "tools/list":
        r = {"tools": [{"name": "echo", "description": os.environ.get("DESC", "d"),
                        "inputSchema": {"type": "object"}}]}
    else:
        r = {}
    print(json.dumps({"jsonrpc": "2.0", "id": i, "result": r}), flush=True)
"""


def test_a_changed_tool_stays_quarantined_after_a_restart(tmp_path: Path) -> None:
    script = tmp_path / "one_tool.py"
    script.write_text(ONE_TOOL_SERVER, encoding="utf-8")
    command = [sys.executable, str(script)]
    cfg = write_config(tmp_path, command=command, trusted_read_only=[], env={"DESC": "v1"})
    with open_mcp(cfg) as first:
        assert first.quarantined == []  # first listing is the baseline
    cfg = write_config(tmp_path, command=command, trusted_read_only=[], env={"DESC": "v2"})
    with open_mcp(cfg) as second:
        assert len(second.quarantined) == 1  # definition changed: refused until enabled
    with open_mcp(cfg) as third:
        assert len(third.quarantined) == 1  # and it stays refused on the next start


def test_approvals_dir_can_be_chosen(tmp_path: Path) -> None:
    cfg = write_config(tmp_path)
    where = tmp_path / "elsewhere"
    with open_mcp(cfg, where):
        pass
    assert (where / "stub.json").is_file()
    assert not (tmp_path / "mcp.json.approvals").exists()


# ----------------------------------------------------------------------------- cli
def test_cli_registers_the_mcp_tools_and_echo_still_runs(
    ws: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    made = capture_loop(monkeypatch)
    cfg = write_config(ws)
    assert cli.main(["--mcp-config", str(cfg), "echo hi"]) == 0
    assert capsys.readouterr().out.strip() == "hi"
    assert "echo" in made[0]._tools and len(made[0]._tools) == 3  # type: ignore[attr-defined]


def test_cli_without_a_config_registers_only_echo(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = capture_loop(monkeypatch)
    assert cli.main(["echo hi"]) == 0
    assert list(made[0]._tools) == ["echo"]  # type: ignore[attr-defined]


def _guard_verdicts(
    mode: str, ws: Path, monkeypatch: pytest.MonkeyPatch, **server: Any
) -> dict[str, str | None]:
    made = capture_loop(monkeypatch)
    cfg = write_config(ws, **server)
    assert cli.main(["--mode", mode, "--mcp-config", str(cfg), "echo hi"]) == 0
    loop = made[0]
    return {
        raw: loop._guard(ToolCall("1", public, {"text": "x"}))  # type: ignore[attr-defined]
        for raw, public in mcp_names(loop).items()
    }


def test_read_only_mode_passes_only_the_trusted_read_tool(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verdicts = _guard_verdicts("read-only", ws, monkeypatch)
    assert verdicts["echo"] is None
    assert verdicts["fail"] is not None and "unknown tool" in verdicts["fail"]
    classed = _guard_verdicts("read-only", ws, monkeypatch, tool_classes={"fail": "write"})
    assert classed["fail"] is not None and "read-only" in classed["fail"]


def test_workspace_write_mode_judges_an_operator_classed_write_tool(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _guard_verdicts("workspace-write", ws, monkeypatch) == {"echo": None, "fail": None}
    classed = _guard_verdicts("workspace-write", ws, monkeypatch, tool_classes={"fail": "write"})
    assert classed["echo"] is None
    assert classed["fail"] is not None and "needs a path" in classed["fail"]


def test_a_bad_config_exits_2_and_a_dead_server_exits_1(
    ws: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (ws / "bad.json").write_text("{", encoding="utf-8")
    assert cli.main(["--mcp-config", str(ws / "bad.json"), "echo hi"]) == 2
    assert "MCP" in capsys.readouterr().err
    dead = write_config(ws, command=["/nonexistent-binary-for-test"])
    assert cli.main(["--mcp-config", str(dead), "echo hi"]) == 1
    assert "MCP" in capsys.readouterr().err
