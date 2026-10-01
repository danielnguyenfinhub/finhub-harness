"""Minimal ReAct-style agent loop.

Control flow ported (idea only, not code) from the MIT-licensed deepseek-harness
``references/deepseek_harness/packages/core/agent-loop/src/agent.ts``
(``ReactLoopAgent.step``, lines ~332-420): call the model; if the assistant message has no
tool calls the run is completed, otherwise execute the tool calls, append their results and
loop. Streaming, sessions, hooks and abort handling are intentionally out of scope for slice 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

DEFAULT_MAX_STEPS = 20


class AgentLoopError(RuntimeError):
    """Raised when the loop cannot finish (e.g. max_steps exceeded)."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class AssistantMessage:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLM(Protocol):
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        """Return the next assistant message for the conversation so far."""
        ...


class Tool(Protocol):
    spec: ToolSpec

    def run(self, arguments: dict[str, Any]) -> str:
        """Execute the tool and return its textual result."""
        ...


class ContextPolicy(Protocol):
    def fit(self, messages: list[Message]) -> list[Message]:
        """Return a NEW list that fits the budget; never mutate the input."""
        ...


class AgentLoop:
    def __init__(
        self,
        llm: LLM,
        tools: list[Tool],
        max_steps: int = DEFAULT_MAX_STEPS,
        *,
        context: ContextPolicy | None = None,
    ) -> None:
        self._llm = llm
        self._context = context
        self._tools = {t.spec.name: t for t in tools}
        self._specs = [t.spec for t in tools]
        self._max_steps = max_steps

    def run(self, prompt: str) -> str:
        messages = [Message(role="user", content=prompt)]
        for _ in range(self._max_steps):
            if self._context is not None:
                messages = self._context.fit(messages)
            reply = self._llm.complete(list(messages), self._specs)
            messages.append(Message("assistant", reply.content, tool_calls=tuple(reply.tool_calls)))
            if not reply.tool_calls:
                return reply.content
            for call in reply.tool_calls:
                messages.append(Message("tool", self._execute(call), tool_call_id=call.id))
        raise AgentLoopError(
            f"max_steps ({self._max_steps}) exceeded without a final answer. "
            "Raise max_steps or check the model is not looping on tool calls."
        )

    def _execute(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            known = ", ".join(sorted(self._tools)) or "none"
            return f"Error: Unknown tool '{call.name}'. Available tools: {known}."
        try:
            return tool.run(call.arguments)
        except Exception as exc:  # noqa: BLE001 - tool faults go back to the model
            return f"Error: tool '{call.name}' failed: {type(exc).__name__}: {exc}"
