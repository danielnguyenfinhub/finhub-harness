"""Deterministic stand-in LLM for slice 1 (no real model exists yet)."""

from __future__ import annotations

from master_finhub.runtime.loop import AssistantMessage, Message, ToolCall, ToolSpec

ECHO_PREFIX = "echo "


class ScriptedLLM:
    """For a prompt 'echo X': call the echo tool with X, then answer with the tool result."""

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        last = messages[-1]
        if last.role == "tool":
            return AssistantMessage(content=last.content)
        if last.role == "user" and last.content.startswith(ECHO_PREFIX):
            text = last.content[len(ECHO_PREFIX) :]
            return AssistantMessage(
                content="", tool_calls=[ToolCall("call-1", "echo", {"text": text})]
            )
        return AssistantMessage(content="ScriptedLLM only understands prompts starting 'echo '.")
