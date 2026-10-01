"""Sub-agent mode: a quick fan-out of isolated helpers whose answers come back to the caller only.

Design: _workspace/02_strategy-architect_slice7.md (revision 3), Decision 4. ``dispatch`` is a thin
adapter over ``run_graph`` (concurrency bound, deadline, Ctrl-C handling come from slice 6). The
engine, not the caller, carries depth, the depth cap and the guard in a private per-thread scope, so
a child's guard is always ``parent guard AND config guard`` and delegation can only get stricter.
Every agent thread needs a slot from one process-wide budget.
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from master_finhub.orchestration._fsio import attempt
from master_finhub.orchestration.graph import (
    GraphResult,
    Limits,
    Node,
    _check_limits,
    _text_problem,
    build_graph,
    exception_name,
    json_len,
    run_graph,
)
from master_finhub.orchestration.graph_store import NODE_ID_PATTERN, GraphError, HaltReason
from master_finhub.runtime.anthropic_llm import ProviderError
from master_finhub.runtime.context import ContextManager, ContextOverflowError
from master_finhub.runtime.loop import (
    LLM,
    AgentLoop,
    AgentLoopError,
    Tool,
    ToolCall,
    ToolGuard,
    ToolSpec,
)
from master_finhub.runtime.router import Router
from master_finhub.tools.safety import guard_tool_call

__all__ = [
    "MAX_AGENT_THREADS",
    "MAX_DISPATCH_DEADLINE_S",
    "DelegateTool",
    "DispatchResult",
    "SubResult",
    "SubStatus",
    "SubTask",
    "SubagentConfig",
    "SubagentError",
    "dispatch",
]

SubStatus = Literal["done", "failed", "running", "not_run"]
MAX_AGENT_THREADS: Final = 32  # process-wide budget of live agent threads (personas + children)
MAX_DISPATCH_DEADLINE_S: Final = 14_400.0
NL: Final = chr(10)
log = logging.getLogger("master_finhub.orchestration.modes.subagent")

REFUSED_UNSCOPED: Final = NL.join(
    (
        "Error: Delegation refused: this helper tool ran outside an agent.",
        "It only works inside a team agent or a helper started by the engine.",
        "Call dispatch() from your own code instead, or run the tool through an agent.",
    )
)


class SubagentError(GraphError):
    """Bad config, bad ids, delegation too deep, or no capacity. Three lines, no content."""


def error_label(cls: type[BaseException]) -> str:
    """Fixed name for our own failure classes (by identity), else a builtin name or Exception."""
    if cls is AgentLoopError:
        return "AgentStepLimit"
    if cls is ProviderError:
        return "ModelCallFailed"
    if cls is ContextOverflowError:
        return "ContextOverflow"
    return exception_name(cls)


# ----------------------------------------------------------------------------- engine scope
@dataclass(frozen=True)
class _Scope:
    """Set by the engine in each persona / child thread, never by callers."""

    depth: int  # 1 = persona or first-level child, ...
    max_depth: int  # the cap fixed by the root; a nested config can only lower it
    guard: ToolGuard  # the effective guard of the agent running on this thread


_SCOPE: Final = threading.local()


def _scope() -> _Scope | None:
    value = getattr(_SCOPE, "value", None)
    return value if isinstance(value, _Scope) else None


def _set_scope(scope: _Scope) -> None:
    _SCOPE.value = scope


def _both(first: ToolGuard, extra: ToolGuard) -> ToolGuard:
    """Parent first; the extra guard can only add denials. A denial is anything but None."""

    def guard(call: ToolCall) -> str | None:  # NEVER `or`: "" is a denial
        denial = first(call)
        return denial if denial is not None else extra(call)

    return guard


# ----------------------------------------------------------------------------- thread budget
class _AgentBudget:
    """Process-wide slots for live agent threads. Reserve before start, release exactly once."""

    def __init__(self, total: int) -> None:
        self._lock = threading.Lock()
        self._total = total
        self._free = total

    def reserve(self, n: int) -> bool:
        with self._lock:
            if n > self._free:
                return False
            self._free -= n
            return True

    def release(self, n: int) -> None:
        with self._lock:
            self._free = min(self._total, self._free + n)

    def free(self) -> int:
        with self._lock:
            return self._free


_BUDGET: Final = _AgentBudget(MAX_AGENT_THREADS)


def release_quietly(slots: int) -> None:
    attempt(lambda: _BUDGET.release(slots), (Exception,))


class _Reservation:
    """Slots for one dispatch, released once: after run_graph returned AND every outstanding
    node (one still ``running`` at return) has left its function. See design Decision 4 (N2)."""

    def __init__(self, slots: int) -> None:
        self._slots = slots
        self._lock = threading.Lock()
        self._entered: set[str] = set()
        self._exited: set[str] = set()
        self._outstanding: set[str] = set()
        self._returned = False
        self._released = False

    def acquire(self) -> bool:
        return _BUDGET.reserve(self._slots)

    def enter(self, node_id: str) -> None:
        with self._lock:
            self._entered.add(node_id)

    def leave(self, node_id: str) -> None:
        with self._lock:
            self._exited.add(node_id)
            ready = self._ready()
        if ready:
            release_quietly(self._slots)

    def returned(self, outstanding: set[str] | None) -> None:
        """run_graph is over. ``outstanding`` None (it raised): nodes entered and not yet left."""
        with self._lock:
            self._outstanding = (
                set(outstanding) if outstanding is not None else self._entered - self._exited
            )
            self._returned = True
            ready = self._ready()
        if ready:
            release_quietly(self._slots)

    def _ready(self) -> bool:  # call under the lock
        if self._released or not self._returned or not self._outstanding <= self._exited:
            return False
        self._released = True
        return True


# ----------------------------------------------------------------------------- model
@dataclass(frozen=True)
class SubTask:
    id: str  # NODE_ID_PATTERN
    prompt: str = field(repr=False)
    profile: str = "builder"
    system: str = field(default="", repr=False)


@dataclass(frozen=True)
class SubResult:
    status: SubStatus
    output: str | None = field(default=None, repr=False)  # non-None iff status == "done"
    error_type: str | None = None


@dataclass(frozen=True)
class DispatchResult:
    status: Literal["done", "failed", "halted"]
    halt_reason: HaltReason | None
    results: Mapping[str, SubResult] = field(repr=False)
    message: str = ""


DEFAULT_SUB_LIMITS: Final = Limits(max_nodes=32, deadline_s=600.0, max_parallelism=4)


def _no_tools(task: SubTask) -> Sequence[Tool]:
    return ()


@dataclass(frozen=True)
class SubagentConfig:
    llm_for: Callable[[SubTask], LLM] | None = None  # default: Router().build_llm(...)
    tools_for: Callable[[SubTask], Sequence[Tool]] = _no_tools
    guard: ToolGuard = guard_tool_call  # at the root this IS the guard; under a scope it is ADDED
    max_steps: int = 20
    max_depth: int = 2  # 1..3; under a scope the effective cap is min(scope.max_depth, max_depth)
    max_result_bytes: int = 65_536  # JSON-encoded bytes per child output
    limits: Limits = DEFAULT_SUB_LIMITS


DEFAULT_CONFIG: Final = SubagentConfig()


def _refuse(what: str, why: str, fix: str) -> SubagentError:
    return SubagentError(what, why, fix)


def _check_deadline(deadline: object) -> bool:
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
        return False
    return math.isfinite(deadline) and 0 < deadline <= MAX_DISPATCH_DEADLINE_S


def _check_config(config: SubagentConfig, tasks: Sequence[SubTask]) -> None:
    if not tasks:
        raise _refuse(
            "There is nothing to dispatch.", "A dispatch needs at least one task.", "Add a task."
        ) from None
    ok = 1 <= config.max_depth <= 3 and config.max_steps >= 1 and config.max_result_bytes >= 1
    if not ok:
        raise _refuse(
            "The helper settings are not usable.",
            "Depth is 1 to 3, steps at least 1 and the result limit at least 1 byte.",
            "Change SubagentConfig(...) to values in those ranges.",
        ) from None
    if not _check_deadline(config.limits.deadline_s):
        raise _refuse(
            "The helper time limit is not usable.",
            f"A deadline is required: more than 0 and at most {int(MAX_DISPATCH_DEADLINE_S)} s.",
            "Set Limits(deadline_s=...) to a finite number of seconds.",
        ) from None
    seen: set[str] = set()
    for position, task in enumerate(tasks, 1):
        good = isinstance(task, SubTask) and isinstance(task.id, str)
        good = good and NODE_ID_PATTERN.fullmatch(task.id) is not None and task.id not in seen
        good = good and type(task.prompt) is str and _text_problem(task.prompt) is None
        if not good:
            raise _refuse(
                f"Helper task {position} is not usable.",
                "Ids are unique lower-case role names and the prompt is plain text.",
                "Fix the task, for example SubTask(id='income_check', prompt='...').",
            ) from None
        seen.add(task.id)


def _strip_delegate(tools: Sequence[Tool], depth: int, cap: int) -> list[Tool]:
    """An agent at the last level is not offered delegation at all."""
    return [t for t in tools if not (depth >= cap and isinstance(t, DelegateTool))]


class _Table:
    """Dispatcher-owned results, written by child threads under a lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, SubResult] = {}

    def put(self, task_id: str, result: SubResult) -> None:
        with self._lock:
            self._items[task_id] = result

    def get(self, task_id: str) -> SubResult | None:
        with self._lock:
            return self._items.get(task_id)


def _run_child(
    task: SubTask, config: SubagentConfig, depth: int, cap: int, guard: ToolGuard
) -> str:
    tools = _strip_delegate(list(config.tools_for(task)), depth, cap)
    llm = (
        config.llm_for(task)
        if config.llm_for is not None
        else Router().build_llm(task.profile, system=task.system)
    )
    loop = AgentLoop(llm, tools, config.max_steps, context=ContextManager(), guard=guard)
    return loop.run(task.prompt)


def _judge(out: object, failed: tuple[type[BaseException], int] | None, cap: int) -> SubResult:
    if failed is not None:
        return SubResult("failed", error_type=error_label(failed[0]))
    if _text_problem(out) is not None:
        return SubResult("failed", error_type="SubagentOutputNotText")
    assert isinstance(out, str)
    if json_len(out) > cap:
        return SubResult("failed", error_type="SubagentOutputTooLarge")
    return SubResult("done", output=out)


def _node(
    task: SubTask,
    config: SubagentConfig,
    scope: _Scope,
    table: _Table,
    reservation: _Reservation,
) -> Node:
    def fn(run: Mapping[str, str], deps: Mapping[str, str]) -> str:
        reservation.enter(task.id)
        try:
            _set_scope(scope)  # before any caller code runs on this thread
            args = (task, config, scope.depth, scope.max_depth, scope.guard)
            out, failed = attempt(lambda: _run_child(*args), (Exception,))
            table.put(task.id, _judge(out, failed, config.max_result_bytes))
        finally:
            reservation.leave(task.id)
        return ""  # a child's failure never fails or skips its siblings

    return Node(task.id, fn)


def _assemble(
    tasks: Sequence[SubTask], table: _Table, graph_result: GraphResult
) -> dict[str, SubResult]:
    out: dict[str, SubResult] = {}
    for task in sorted(tasks, key=lambda t: t.id):
        mine = table.get(task.id)
        if mine is not None:
            out[task.id] = mine
            continue
        state = graph_result.nodes.get(task.id)
        if state == "running":
            out[task.id] = SubResult("running")
        elif state == "failed":
            out[task.id] = SubResult("failed", error_type=graph_result.errors.get(task.id))
        else:
            out[task.id] = SubResult("not_run")
    return out


def _message(results: Mapping[str, SubResult], halted: HaltReason | None) -> str:
    bad = {i: r for i, r in results.items() if r.status != "done"}
    if not bad:
        return ""
    names = ", ".join(f"{i} ({r.error_type or r.status})" for i, r in bad.items())
    running = sorted(i for i, r in bad.items() if r.status == "running")
    if halted == "deadline" and running:
        second = "It passed the time limit and Python cannot stop it; it may keep running."
        third = "Check any side effects before relying on the others."
        return NL.join((f"Helper {running[0]} is still running.", second, third))
    return NL.join(
        (
            f"Not every helper finished: {names}.",
            "Only helpers marked done have an answer; the rest have none.",
            "Fix the cause and dispatch the missing ones again.",
        )
    )


def dispatch(
    tasks: Sequence[SubTask], *, config: SubagentConfig = DEFAULT_CONFIG
) -> DispatchResult:
    """Run helpers in parallel and return each one's own status. Depth, cap and guard come from
    the calling thread's engine scope; Daniel's own code has none and is a root."""
    scope = _scope()
    depth = 0 if scope is None else scope.depth
    cap = config.max_depth if scope is None else min(scope.max_depth, config.max_depth)
    guard = config.guard if scope is None else _both(scope.guard, config.guard)
    _check_config(config, tasks)
    if depth >= cap:
        raise _refuse(
            f"Delegation is too deep: this agent is already at level {depth} of {cap}.",
            "Helpers may not start further helpers beyond the depth limit.",
            "Do this part of the work yourself.",
        ) from None
    reservation = _Reservation(min(config.limits.max_parallelism, len(tasks)))
    table = _Table()
    child = _Scope(depth + 1, cap, guard)
    graph = build_graph([_node(t, config, child, table, reservation) for t in tasks])
    _check_limits(config.limits, graph)
    if not reservation.acquire():
        raise _refuse(
            f"Not enough agent capacity: {len(tasks)} helpers asked for, "
            f"{_BUDGET.free()} slots free.",
            f"Every running agent and helper uses one of {MAX_AGENT_THREADS} slots, including "
            "ones still finishing after a time limit.",
            "Ask for fewer helpers, or wait for running work to end.",
        ) from None
    raised: BaseException | None = None
    result = None
    try:
        result = run_graph(graph, limits=config.limits)
    except BaseException as exc:  # noqa: BLE001 - released below, re-raised outside the except
        raised = exc
    if result is not None:
        reservation.returned({i for i, s in result.nodes.items() if s == "running"})
    else:
        reservation.returned(None)
    if raised is not None:
        raise raised
    assert result is not None
    results = _assemble(tasks, table, result)
    all_done = all(r.status == "done" for r in results.values())
    status: Literal["done", "failed", "halted"] = (
        "done" if all_done else "halted" if result.status == "halted" else "failed"
    )
    log.debug("dispatch status=%s tasks=%d depth=%d", status, len(tasks), depth)
    return DispatchResult(
        status, result.halt_reason, results, _message(results, result.halt_reason)
    )


# ----------------------------------------------------------------------------- delegate tool
class DelegateTool:
    """crewAI DelegateWorkTool pattern: runs isolated helpers and returns their answers as text.
    It reads its depth and guard from the engine scope and refuses on a thread without one."""

    spec = ToolSpec(
        name="delegate",
        description=(
            "Hand independent sub-tasks to isolated helpers that run in parallel and return "
            "their answers to you only. Use for self-contained checks. Takes tasks: a list of "
            "{id, prompt}. Returns one section per task with its own status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}, "prompt": {"type": "string"}},
                        "required": ["id", "prompt"],
                    },
                }
            },
            "required": ["tasks"],
        },
    )

    def __init__(self, config: SubagentConfig) -> None:
        self._config = config

    def run(self, arguments: dict[str, Any]) -> str:
        if _scope() is None:  # fail closed: a thread without a scope would drop the parent guard
            return REFUSED_UNSCOPED
        items = arguments.get("tasks")
        tasks: list[SubTask] = []
        if isinstance(items, list):
            for item in items:
                prompt = item.get("prompt") if isinstance(item, dict) else None
                if isinstance(item, dict) and type(item.get("id")) is str and type(prompt) is str:
                    tasks.append(SubTask(item["id"], prompt))
        if not tasks or not isinstance(items, list) or len(tasks) != len(items):
            return "Error: tasks must be a list of {id, prompt} objects with text values."
        return self._dispatch_text(tasks)

    def _dispatch_text(self, tasks: list[SubTask]) -> str:
        try:
            result = dispatch(tasks, config=self._config)
        except GraphError as exc:
            return "Error: " + str(exc).replace(NL, " ")  # fixed three-part text, ids and counts
        sections = []
        for task_id, sub in result.results.items():
            head = f"[{task_id}] {sub.status}"
            if sub.status == "done":
                sections.append(f"{head}:{NL}{sub.output}")
            else:
                sections.append(head + (f" ({sub.error_type})" if sub.error_type else ""))
        if result.message:
            sections.append(result.message)
        return (NL + NL).join(sections)
