"""Slice 1 proof tests for AgentLoop (synthetic data only)."""

import pytest

from master_finhub.runtime.loop import (
    AgentLoop,
    AgentLoopError,
    AssistantMessage,
    Message,
    ToolCall,
    ToolSpec,
)
from master_finhub.tools.builtins.echo import EchoTool


class QueueLLM:
    """Returns pre-baked assistant messages and records what it was shown."""

    def __init__(self, replies: list[AssistantMessage]) -> None:
        self._replies = list(replies)
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.seen.append(list(messages))
        return self._replies.pop(0)


def test_terminates_without_tool_calls() -> None:
    llm = QueueLLM([AssistantMessage(content="done")])
    assert AgentLoop(llm, [EchoTool()]).run("hello") == "done"
    assert len(llm.seen) == 1


def test_executes_tool_call_then_finishes() -> None:
    call = ToolCall(id="c1", name="echo", arguments={"text": "hi"})
    llm = QueueLLM([AssistantMessage(content="", tool_calls=[call]), AssistantMessage("ok")])
    assert AgentLoop(llm, [EchoTool()]).run("go") == "ok"
    tool_msg = llm.seen[1][-1]
    assert (tool_msg.role, tool_msg.content, tool_msg.tool_call_id) == ("tool", "hi", "c1")


def test_unknown_tool_returns_error_message_not_crash() -> None:
    call = ToolCall(id="c1", name="nope", arguments={})
    llm = QueueLLM([AssistantMessage(content="", tool_calls=[call]), AssistantMessage("ok")])
    assert AgentLoop(llm, [EchoTool()]).run("go") == "ok"
    tool_msg = llm.seen[1][-1]
    assert tool_msg.role == "tool"
    assert "Unknown tool 'nope'" in tool_msg.content
    assert "echo" in tool_msg.content


def test_tool_exception_becomes_error_result() -> None:
    call = ToolCall(id="c1", name="echo", arguments={})  # missing 'text'
    llm = QueueLLM([AssistantMessage(content="", tool_calls=[call]), AssistantMessage("ok")])
    assert AgentLoop(llm, [EchoTool()]).run("go") == "ok"
    assert "failed" in llm.seen[1][-1].content


def test_max_steps_exceeded_raises() -> None:
    call = ToolCall(id="c", name="echo", arguments={"text": "x"})
    llm = QueueLLM([AssistantMessage(content="", tool_calls=[call]) for _ in range(5)])
    with pytest.raises(AgentLoopError, match="max_steps"):
        AgentLoop(llm, [EchoTool()], max_steps=3).run("go")
