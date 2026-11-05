"""Minimal ReAct-style agent loop.

Control flow ported (idea only, not code) from the MIT-licensed deepseek-harness
``references/deepseek_harness/packages/core/agent-loop/src/agent.ts``
(``ReactLoopAgent.step``, lines ~332-420): call the model; if the assistant message has no
tool calls the run is completed, otherwise execute the tool calls, append their results and
loop. Streaming, sessions, hooks and abort handling are intentionally out of scope for slice 1.
The advisory repeat-call reminder (``repeat_reminder.py``) is adapted from the MIT-licensed
deepseek-harness
``references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:189``.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol

from master_finhub.runtime.repeat_reminder import RepeatReminder
from master_finhub.tools.secret_scan import redact_secrets

DEFAULT_MAX_STEPS = 20
UNCERTAIN_RESULT: Final = (
    "Error: interrupted before this call's result was saved; it may or may not have taken "
    "effect. Verify before retrying."
)
LoopStatus = Literal["awaiting_model", "tools_in_flight", "completed"]
InFlightPolicy = Literal["stop", "rerun", "report_unknown"]


FailurePolicy = Literal["ignore", "warn", "raise"]


class AgentLoopError(RuntimeError):
    """Raised when the loop cannot finish (e.g. max_steps exceeded)."""


class ToolFailureError(AgentLoopError):
    """Raised under ``on_tool_failure="raise"`` when a tool reports a failure."""


class ToolFailure(Exception):
    """A tool's own report that it failed: why, an optional code, and whether a retry may help.

    Nothing is guessed from the text of a result. (adapted from
    references/crewai/lib/crewai/src/crewai/tools/tool_failure.py:71 (MIT), idea only)
    """

    def __init__(self, reason: str, *, code: str | None = None, retryable: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class FailureRecord:
    tool: str
    call_id: str
    reason: str
    code: str | None
    retryable: bool


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
    idempotent: bool = False  # running it twice is harmless; never sent to the model
    timeout_s: float | None = None  # deadline for one run; never sent to the model

    def __post_init__(self) -> None:
        if self.timeout_s is not None and not (
            self.timeout_s > 0 and math.isfinite(self.timeout_s)
        ):
            raise ValueError("timeout_s must be a positive finite number of seconds")


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


def _analyse(messages: tuple[Message, ...]) -> tuple[LoopStatus, tuple[ToolCall, ...]]:
    """Derive (status, unanswered calls) from the history; ValueError when it is malformed."""
    if not messages:
        raise ValueError("empty history")
    open_calls: list[ToolCall] = []
    for m in messages:
        if m.role == "tool":
            if not open_calls or open_calls[0].id != m.tool_call_id:
                raise ValueError("tool result out of order")
            open_calls.pop(0)
        elif open_calls:
            raise ValueError("message while tool calls are unanswered")
        elif m.role == "assistant":
            open_calls = list(m.tool_calls)
    if open_calls:
        return "tools_in_flight", tuple(open_calls)
    last = messages[-1]
    return ("completed" if last.role == "assistant" else "awaiting_model"), ()


@dataclass(frozen=True)
class LoopSnapshot:
    """What the loop holds between two side effects. status/pending are derived, never stored."""

    step: int  # model turns completed so far (0 = only the prompt)
    messages: tuple[Message, ...]  # full history, post-compaction

    def __post_init__(self) -> None:
        _analyse(self.messages)

    @property
    def status(self) -> LoopStatus:
        return _analyse(self.messages)[0]

    @property
    def pending_calls(self) -> tuple[ToolCall, ...]:
        return _analyse(self.messages)[1]


# Raising from the hook fails closed: the loop does not catch it and runs nothing further.
CheckpointHook = Callable[[LoopSnapshot], None]


class ResumeBlocked(AgentLoopError):
    """Resume would re-run a tool that may already have run and is not marked idempotent."""

    def __init__(self, tool_name: str, call_id: str, step: int) -> None:
        self.tool_name = tool_name
        self.call_id = call_id
        self.step = step
        what = (
            f'Resume stopped: tool "{tool_name}" (call {call_id}) may already have run at '
            f"step {step} and is not safe to repeat."
        )
        why = "The process stopped before its result was saved."
        fix = (
            'Check whether it happened, then resume with in_flight="rerun" if it did not, '
            'or in_flight="report_unknown" to let the agent check for itself.'
        )
        super().__init__(f"{what}\n{why}\n{fix}")


class LLM(Protocol):
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        """Return the next assistant message for the conversation so far."""
        ...


class Tool(Protocol):
    spec: ToolSpec

    def run(self, arguments: dict[str, Any]) -> str | ToolFailure:
        """Execute the tool and return its textual result, or a ToolFailure it reports."""
        ...


class ContextPolicy(Protocol):
    def fit(self, messages: list[Message]) -> list[Message]:
        """Return a NEW list that fits the budget; never mutate the input."""
        ...


# Tool-call veto: None allows the call; a string is the denial text shown to the model.
ToolGuard = Callable[[ToolCall], str | None]


class AgentLoop:
    def __init__(
        self,
        llm: LLM,
        tools: list[Tool],
        max_steps: int = DEFAULT_MAX_STEPS,
        *,
        context: ContextPolicy | None = None,
        guard: ToolGuard | None = None,
        checkpoint: CheckpointHook | None = None,
        on_tool_failure: FailurePolicy = "warn",
    ) -> None:
        self._on_failure = on_tool_failure
        self.failures: list[FailureRecord] = []  # tool-reported failures, kept under "warn"/"raise"
        self._llm = llm
        self._guard = guard
        self._context = context
        self._checkpoint = checkpoint
        self._tools = {t.spec.name: t for t in tools}
        self._specs = [t.spec for t in tools]
        self._max_steps = max_steps
        self._repeat = RepeatReminder()

    def run(self, prompt: str) -> str:
        self._repeat.reset()  # a new user prompt starts a new chain
        messages = [Message(role="user", content=prompt)]
        self._save(0, messages)
        return self._drive(messages, 0, [])

    def resume(self, snapshot: LoopSnapshot, *, in_flight: InFlightPolicy = "stop") -> str:
        """Continue from a saved snapshot. The first save is a claim: see CheckpointStore."""
        self._repeat.reset()  # the chain is not in the snapshot, so it restarts here
        self._save(snapshot.step, list(snapshot.messages))
        if snapshot.status == "completed":
            return snapshot.messages[-1].content
        messages, pending = list(snapshot.messages), list(snapshot.pending_calls)
        if pending:
            first = pending.pop(0)  # the only call that may already have started
            result = self._uncertain(first, in_flight, snapshot.step)
            messages.append(Message("tool", result, tool_call_id=first.id))
            self._save(snapshot.step, messages)
        return self._drive(messages, snapshot.step, pending)

    def _drive(self, messages: list[Message], step: int, pending: list[ToolCall]) -> str:
        while True:
            for call in pending:
                messages.append(Message("tool", self._execute(call), tool_call_id=call.id))
                self._save(step, messages)
            if step >= self._max_steps:
                raise AgentLoopError(
                    f"max_steps ({self._max_steps}) exceeded without a final answer. "
                    "Raise max_steps or check the model is not looping on tool calls."
                )
            if self._context is not None:
                messages = self._context.fit(messages)
            reply = self._llm.complete(list(messages), self._specs)
            step += 1
            messages.append(Message("assistant", reply.content, tool_calls=tuple(reply.tool_calls)))
            self._save(step, messages)
            if not reply.tool_calls:
                return reply.content
            pending = list(reply.tool_calls)

    def _save(self, step: int, messages: list[Message]) -> None:
        if self._checkpoint is not None:
            self._checkpoint(LoopSnapshot(step, tuple(messages)))

    def _uncertain(self, call: ToolCall, policy: InFlightPolicy, step: int) -> str:
        tool = self._tools.get(call.name)
        # Tool set or guard may differ from the dead process: "it never ran" cannot be known.
        if tool is None or (self._guard is not None and self._guard(call) is not None):
            return UNCERTAIN_RESULT
        if tool.spec.idempotent or policy == "rerun":
            return self._execute(call)
        if policy == "report_unknown":
            return UNCERTAIN_RESULT
        raise ResumeBlocked(call.name, call.id, step)

    def _execute(self, call: ToolCall) -> str:
        """Every tool result, denial and error text passes the secret scan before it is stored.

        The repeat notice is fixed text appended after the scan, inside the same tool message: a
        private-key match runs to the end of the text and would swallow it, and the pair stays
        whole. It is counted before the call runs, so a tool that edits its own arguments in place
        cannot change the key.
        """
        note = self._repeat.observe(call.name, call.arguments)
        return redact_secrets(self._run_tool(call))[0] + note

    def _run_tool(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            known = ", ".join(sorted(self._tools)) or "none"
            return f"Error: Unknown tool '{call.name}'. Available tools: {known}."
        if self._guard is not None:
            denial = self._guard(call)
            if denial is not None:
                return f"Error: {denial}"
        try:
            out = self._call(tool, call)
        except _Deadline:
            return (
                f"Error: TOOL_TIMEOUT: tool '{call.name}' did not finish within "
                f"{tool.spec.timeout_s:g} s; it may or may not have taken effect. "
                "Verify before retrying."
            )
        except ToolFailure as fail:
            out = fail
        except Exception as exc:  # noqa: BLE001 - tool faults go back to the model
            return f"Error: tool '{call.name}' failed: {type(exc).__name__}: {exc}"
        if isinstance(out, ToolFailure):
            return self._failed(call, out)
        return out

    def _call(self, tool: Tool, call: ToolCall) -> str | ToolFailure:
        """Run the tool, under its deadline when it declares one.

        TOOL_TIMEOUT means this loop's own timer fired. A ``TimeoutError`` the tool raises itself
        passes through unchanged and is reported as an ordinary tool failure. (adapted from
        references/deepseek_harness/packages/guard/timeout-policy/src/index.ts:56 (MIT), idea only)
        """
        limit = tool.spec.timeout_s
        if limit is None:
            return tool.run(call.arguments)
        box: dict[str, Any] = {}

        def work() -> None:
            try:
                box["out"] = tool.run(call.arguments)
            except Exception as exc:  # noqa: BLE001 - re-raised in the caller's thread
                box["err"] = exc

        # ponytail: a thread cannot be killed, so a timed-out tool keeps running in the background and
        # its late result is dropped; use a subprocess per call if a runaway tool must be stopped.
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(limit)
        if worker.is_alive():
            raise _Deadline
        if "err" in box:
            raise box["err"]
        out: str | ToolFailure = box["out"]
        return out

    def _failed(self, call: ToolCall, fail: ToolFailure) -> str:
        if self._on_failure != "ignore":
            self.failures.append(
                FailureRecord(call.name, call.id, fail.reason, fail.code, fail.retryable)
            )
        if self._on_failure == "raise":
            raise ToolFailureError(f"tool '{call.name}' reported a failure: {fail.reason}")
        extra = (f" (code {fail.code})" if fail.code else "") + (
            "; retryable" if fail.retryable else ""
        )
        return f"Error: tool '{call.name}' failed: {fail.reason}{extra}"


class _Deadline(Exception):
    """The loop's own deadline timer fired."""
