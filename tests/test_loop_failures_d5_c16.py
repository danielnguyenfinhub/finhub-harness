"""Proof for the tool deadline (D5) and the typed tool failure (C16) in runtime/loop.py.

adapted from references/deepseek_harness/packages/guard/timeout-policy/src/index.ts:56 (MIT) and
references/crewai/lib/crewai/src/crewai/tools/tool_failure.py:71 (MIT), idea only
"""

import threading
import time
from typing import Any

import pytest

from master_finhub.runtime.loop import (
    AgentLoop,
    AssistantMessage,
    Message,
    ToolCall,
    ToolFailure,
    ToolFailureError,
    ToolSpec,
)


class QueueLLM:
    def __init__(self, replies: list[AssistantMessage]) -> None:
        self._replies = list(replies)
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.seen.append(list(messages))
        return self._replies.pop(0)


class FnTool:
    def __init__(self, name: str, fn: Any, timeout_s: float | None = None) -> None:
        self.spec = ToolSpec(name, "", {"type": "object"}, timeout_s=timeout_s)
        self._fn = fn

    def run(self, arguments: dict[str, Any]) -> Any:
        return self._fn(arguments)


def run_once(tool: FnTool, **kw: Any) -> tuple[str, str]:
    """Run one call to ``tool``; returns (final answer, the tool message the model saw)."""
    call = ToolCall("c1", tool.spec.name, {})
    llm = QueueLLM([AssistantMessage("", [call]), AssistantMessage("done")])
    answer = AgentLoop(llm, [tool], **kw).run("go")
    return answer, llm.seen[1][-1].content


def test_tool_past_its_deadline_reports_tool_timeout() -> None:
    gate = threading.Event()
    tool = FnTool("slow", lambda a: gate.wait(5) and "late", timeout_s=0.05)
    start = time.monotonic()
    answer, seen = run_once(tool)
    gate.set()
    assert answer == "done"
    assert seen.startswith("Error: TOOL_TIMEOUT")
    assert "slow" in seen and "may or may not have taken effect" in seen
    assert time.monotonic() - start < 2


def test_tools_own_timeout_error_is_not_tool_timeout() -> None:
    def inner(_: dict[str, Any]) -> str:
        raise TimeoutError("upstream api timed out")

    _, seen = run_once(FnTool("api", inner, timeout_s=5))
    assert "TOOL_TIMEOUT" not in seen
    assert "TimeoutError" in seen and "upstream api timed out" in seen


def test_tool_inside_its_deadline_returns_normally() -> None:
    _, seen = run_once(FnTool("fast", lambda a: "ok", timeout_s=5))
    assert seen == "ok"


def test_no_deadline_declared_runs_inline() -> None:
    _, seen = run_once(FnTool("plain", lambda a: threading.current_thread().name))
    assert seen == threading.current_thread().name


def test_deadline_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ToolSpec("x", "", {}, timeout_s=0)


def failing(a: dict[str, Any]) -> ToolFailure:
    return ToolFailure("ok was false", code="slack_error", retryable=True)


def test_returned_failure_is_not_logged_as_success() -> None:
    call = ToolCall("c1", "post", {})
    llm = QueueLLM([AssistantMessage("", [call]), AssistantMessage("done")])
    loop = AgentLoop(llm, [FnTool("post", failing)])
    loop.run("go")
    seen = llm.seen[1][-1].content
    assert seen.startswith("Error: tool 'post' failed: ok was false")
    assert "slack_error" in seen and "retryable" in seen
    assert [(f.tool, f.code, f.retryable) for f in loop.failures] == [("post", "slack_error", True)]


def test_raised_failure_is_handled_like_a_returned_one() -> None:
    def boom(a: dict[str, Any]) -> str:
        raise ToolFailure("denied", code="403")

    _, seen = run_once(FnTool("post", boom))
    assert "denied" in seen and "403" in seen and seen.startswith("Error:")


def test_policy_raise_stops_the_run() -> None:
    call = ToolCall("c1", "post", {})
    llm = QueueLLM([AssistantMessage("", [call]), AssistantMessage("never reached")])
    with pytest.raises(ToolFailureError) as err:
        AgentLoop(llm, [FnTool("post", failing)], on_tool_failure="raise").run("go")
    assert "ok was false" in str(err.value)


def test_policy_ignore_records_nothing_and_run_continues() -> None:
    call = ToolCall("c1", "post", {})
    llm = QueueLLM([AssistantMessage("", [call]), AssistantMessage("done")])
    loop = AgentLoop(llm, [FnTool("post", failing)], on_tool_failure="ignore")
    assert loop.run("go") == "done"
    assert loop.failures == []


def test_plain_string_result_is_still_a_success() -> None:
    call = ToolCall("c1", "post", {})
    llm = QueueLLM([AssistantMessage("", [call]), AssistantMessage("done")])
    loop = AgentLoop(llm, [FnTool("post", lambda a: "sent")])
    loop.run("go")
    assert llm.seen[1][-1].content == "sent" and loop.failures == []
