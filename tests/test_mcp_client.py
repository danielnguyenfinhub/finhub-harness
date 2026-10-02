"""Slice 9 proof tests: stdio MCP client against tests/mcp_stub_server.py (synthetic data only)."""

import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from master_finhub.runtime.loop import AgentLoop, AssistantMessage, Message, ToolCall, ToolSpec
from master_finhub.tools.mcp import client as mcp_client
from master_finhub.tools.mcp.client import (
    MAX_SERVER_REQUESTS,
    MAX_TOOL_PAGES,
    McpClient,
    McpClosed,
    McpError,
    McpResult,
    McpTool,
    McpToolError,
    McpToolInfo,
    StdioServer,
    mcp_tools,
    public_tool_name,
    redact,
)
from master_finhub.tools.safety import guard_tool_call

STUB = str(Path(__file__).with_name("mcp_stub_server.py"))


def server(
    *flags: str, log: Path | None = None, env: dict[str, str] | None = None, **kw: object
) -> StdioServer:
    full_env = dict(env or {})
    if log is not None:
        full_env["MCP_STUB_LOG"] = str(log)
    return StdioServer(
        name="stub", command=(sys.executable, STUB, *flags), env=full_env, **kw  # type: ignore[arg-type]
    )


def logged(log: Path) -> list[dict[str, object]]:
    if not log.exists():
        return []
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]


def wait_for(pred: object, seconds: float = 5.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if pred():  # type: ignore[operator]
            return True
        time.sleep(0.02)
    return False


def test_handshake_and_list(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    with McpClient(server(log=log)) as c:
        assert [t.name for t in c.list_tools()] == ["echo", "fail"]
    methods = [m.get("method") for m in logged(log)]
    assert methods[:3] == ["initialize", "notifications/initialized", "tools/list"]


def test_call_echo_round_trip() -> None:
    with McpClient(server()) as c:
        assert c.call_tool("echo", {"text": "hi"}) == McpResult("hi", False)


def test_is_error_maps_to_tool_error_and_redacts_env_secret() -> None:
    secret = "s3cr3t-value-123"
    with McpClient(server(env={"MCP_STUB_SECRET": secret})) as c:
        res = c.call_tool("fail", {})
        assert res.is_error is True
        assert secret not in res.text and "[REDACTED]" in res.text
        tool = McpTool(c, McpToolInfo("fail", "mcp__stub__fail", "", {"type": "object"}))
        with pytest.raises(McpToolError) as ei:
            tool.run({})
        assert secret not in str(ei.value)


def test_pagination() -> None:
    with McpClient(server("--paged")) as c:
        assert [t.name for t in c.list_tools()] == ["echo", "fail"]


def test_server_death_fails_waiter() -> None:
    start = time.monotonic()
    with McpClient(server("--die-on-call")) as c, pytest.raises(McpClosed):
        c.call_tool("echo", {"text": "x"})
    assert time.monotonic() - start < 5


def test_timeout() -> None:
    with McpClient(server("--never-answer", call_timeout_s=0.5)) as c, pytest.raises(TimeoutError):
        c.call_tool("echo", {"text": "x"})


def test_unsupported_version_rejected() -> None:
    with pytest.raises(McpError), McpClient(server("--version", "1999-01-01")):
        pass


def test_oversize_line_closes_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_client, "MAX_LINE_CHARS", 100_000)
    start = time.monotonic()
    with McpClient(server("--huge-line")) as c:
        with pytest.raises(McpClosed, match="too long"):
            c.list_tools()
        with pytest.raises(McpClosed):  # session stays closed
            c.call_tool("echo", {"text": "x"})
    assert time.monotonic() - start < 5


def test_endless_pages_capped(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    with (
        McpClient(server("--endless-pages", log=log)) as c,
        pytest.raises(McpError, match="too many"),
    ):
        c.list_tools()
    assert [m.get("method") for m in logged(log)].count("tools/list") == MAX_TOOL_PAGES == 20


def test_server_request_gets_method_not_found(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    with McpClient(server("--ask-client", "1", log=log)) as c:
        assert c.call_tool("echo", {"text": "hi"}).text == "hi"
        assert wait_for(lambda: any(m.get("id") == "s0" for m in logged(log)))
    reply = next(m for m in logged(log) if m.get("id") == "s0")
    assert reply["error"]["code"] == -32601  # type: ignore[index]


def test_server_request_flood_closes_session() -> None:
    n = MAX_SERVER_REQUESTS + 40
    start = time.monotonic()
    with McpClient(server("--ask-client", str(n))) as c, pytest.raises(McpClosed, match="too many"):
        c.call_tool("echo", {"text": "hi"})
    assert time.monotonic() - start < 5  # and close() did not hang


def test_public_name_rules() -> None:
    assert public_tool_name("stub", "echo") == "mcp__stub__echo"
    long = public_tool_name("stub", "t" * 100)
    assert len(long) == 64 and long[-13] == "_" and int(long[-12:], 16) >= 0
    assert public_tool_name("stub", "a.b") != public_tool_name("stub", "a_b")
    assert public_tool_name("stub", "a.b").startswith("mcp__stub__a_b_")


def test_filter_block_wins() -> None:
    with McpClient(
        server(allowed_tools=frozenset({"echo", "fail"}), blocked_tools=frozenset({"fail"}))
    ) as c:
        assert [t.spec.name for t in mcp_tools(c)] == ["mcp__stub__echo"]
    with McpClient(server(allowed_tools=frozenset({"fail"}))) as c:
        assert [t.spec.name for t in mcp_tools(c)] == ["mcp__stub__fail"]


def test_redact_env_value_and_bearer() -> None:
    out = redact(
        "key=abcd1234 short=ab Authorization: Bearer tok.en-123 ghp_" + "a" * 30,
        ["abcd1234", "ab"],
    )
    assert "abcd1234" not in out and "tok.en-123" not in out and "ghp_" not in out
    assert "short=ab" in out  # values under 4 chars are not redacted


def test_denied_launch_command_never_spawns() -> None:
    c = McpClient(StdioServer(name="bad", command=("rm", "-rf", "/")))
    with pytest.raises(McpError):
        c.start()
    assert c._proc is None


def test_missing_binary_is_mcp_error() -> None:
    with pytest.raises(McpError, match="could not start"):
        McpClient(StdioServer(name="gone", command=("/nonexistent/mcp-server-xyz",))).start()


def test_not_initialized_and_close_idempotent_kills_child() -> None:
    c = McpClient(server())
    c.start()
    proc = c._proc
    assert proc is not None
    with pytest.raises(McpError, match="not initialized"):
        c.list_tools()
    c.close()
    c.close()
    assert proc.poll() is not None


def started_stuck(*flags: str) -> McpClient:
    c = McpClient(server("--ignore-eof", *flags))
    c.start()
    c.initialize()
    return c


def test_close_terminates_child_that_ignores_stdin_eof() -> None:
    c = started_stuck()
    proc = c._proc
    assert proc is not None
    start = time.monotonic()
    c.close()
    assert time.monotonic() - start < 10
    assert proc.returncode == -signal.SIGTERM  # terminate branch, not kill


def test_close_kills_child_that_ignores_eof_and_sigterm() -> None:
    c = started_stuck("--ignore-term")
    proc = c._proc
    assert proc is not None
    start = time.monotonic()
    c.close()
    assert time.monotonic() - start < 12
    assert proc.returncode == -signal.SIGKILL
    with pytest.raises(ProcessLookupError):
        os.kill(proc.pid, 0)  # really gone


def test_close_final_kill_runs_even_if_wait_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    c = started_stuck("--ignore-term")
    proc = c._proc
    assert proc is not None
    monkeypatch.setattr(proc, "wait", lambda timeout=None: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(RuntimeError):
        c.close()
    monkeypatch.undo()
    assert proc.wait(timeout=5) == -signal.SIGKILL


def test_child_env_is_scrubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_API_KEY", "parent-secret-value")
    monkeypatch.setenv("MCP_PLAIN_VAR", "visible")
    with McpClient(server(env={"MCP_STUB_SECRET": "explicit-secret-1"})) as c:
        keys = c.initialize()["serverInfo"]["envKeys"]
    assert "FAKE_API_KEY" not in keys  # scrubbed from the parent env
    assert "MCP_PLAIN_VAR" in keys and "MCP_STUB_SECRET" in keys  # plain + explicit pass


class QueueLLM:
    def __init__(self, replies: list[AssistantMessage]) -> None:
        self._replies = list(replies)

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        return self._replies.pop(0)


def test_loop_calls_mcp_tool() -> None:
    call = ToolCall(id="c1", name="mcp__stub__echo", arguments={"text": "hi"})

    class AnswerWithToolResult(QueueLLM):
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            if messages[-1].role == "tool":
                return AssistantMessage(content=messages[-1].content)
            return AssistantMessage(content="", tool_calls=[call])

    with McpClient(server()) as c:
        loop = AgentLoop(AnswerWithToolResult([]), list(mcp_tools(c)), guard=guard_tool_call)  # type: ignore[arg-type]
        assert loop.run("go") == "hi"
