"""Team mode: named role agents that message each other and work a shared task list until it is done.

Design: _workspace/02_strategy-architect_slice7.md (revision 3), Decision 3. Every persona is an
``AgentLoop`` on its own daemon thread; the main thread is the coordinator and checks the stop
rules every 0.1 s, so Ctrl-C is always seen. Team runs are NOT resumable and NOT deterministic:
if the process dies the run is lost and tools that already acted may act again. Results are empty
unless every task is done. Events, logs and errors carry names, ids, sizes and counts only.
"""

from __future__ import annotations

import logging
import math
import queue
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Literal, cast

from master_finhub.orchestration._fsio import Failure, attempt
from master_finhub.orchestration.graph import POLL_SECONDS
from master_finhub.orchestration.graph_store import GraphError
from master_finhub.orchestration.message_bus import (
    AGENT_NAME_PATTERN,
    DEFAULT_BUS_LIMITS,
    MAX_AGENTS,
    RESERVED_NAMES,
    BusError,
    BusLimits,
    BusMessage,
    Endpoint,
    MessageBus,
)
from master_finhub.orchestration.modes.subagent import (
    _BUDGET,
    MAX_AGENT_THREADS,
    _Scope,
    _set_scope,
    _strip_delegate,
    error_label,
    release_quietly,
)
from master_finhub.orchestration.modes.task_board import TaskBoard, TaskSpec, TaskStatus
from master_finhub.orchestration.modes.team_tools import (
    CompleteTaskTool,
    FailTaskTool,
    SendMessageTool,
)
from master_finhub.runtime.context import ContextManager
from master_finhub.runtime.loop import (
    LLM,
    AgentLoop,
    LoopSnapshot,
    Message,
    Tool,
    ToolGuard,
)
from master_finhub.runtime.router import Router
from master_finhub.tools.safety import guard_tool_call

__all__ = [
    "MAX_TEAM_DEADLINE_S",
    "PERSONA_NAME_SUFFIX",
    "Persona",
    "TeamError",
    "TeamEvent",
    "TeamLimits",
    "TeamResult",
    "run_team",
]

PERSONA_NAME_SUFFIX: Final = "-agent"
MAX_TEAM_DEADLINE_S: Final = 14_400.0
JOIN_SECONDS: Final = 1.0
NL: Final = chr(10)
log = logging.getLogger("master_finhub.orchestration.modes.team")
_TEAM_LOCK: Final = threading.Lock()  # one team at a time, held until its last thread exits

TeamStatus = Literal["done", "failed", "halted"]
TeamHalt = Literal["turn_limit", "deadline", "message_limit", "stalled", "interrupted"]
TeamEventKind = Literal[
    "team_started",
    "turn_started",
    "turn_finished",
    "turn_failed",
    "task_claimed",
    "task_done",
    "task_failed",
    "message_sent",
    "message_rejected",
    "team_halted",
    "team_finished",
]


class TeamError(GraphError):
    """Bad personas, tasks or limits, another team running, or no agent capacity."""


@dataclass(frozen=True)
class Persona:
    name: str  # bus name; a role, never a person or client ("income-agent")
    profile: str  # Router profile -> tier
    system: str = field(default="", repr=False)  # reaches the model only
    tools: tuple[Tool, ...] = ()
    max_steps: int = 40  # model calls over the WHOLE team run (step count is cumulative)


@dataclass(frozen=True)
class TeamLimits:
    max_turns: int = 64  # turns started over all agents (one turn = one input handled)
    deadline_s: float = 1800.0  # MANDATORY and finite: 0 < d <= MAX_TEAM_DEADLINE_S
    bus: BusLimits = DEFAULT_BUS_LIMITS
    max_depth: int = 2  # personas run at depth 1, their sub-agents at depth 2; 1..3


@dataclass(frozen=True)
class TeamEvent:
    """Ids, names, sizes, counts and fixed error names. Never content."""

    kind: TeamEventKind
    seq: int
    agent: str | None = None
    task_id: str | None = None
    message_id: int | None = None
    size: int | None = None
    error_type: str | None = None
    halt_reason: TeamHalt | None = None
    counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TeamResult:
    status: TeamStatus
    halt_reason: TeamHalt | None
    tasks: Mapping[str, TaskStatus]
    results: Mapping[str, str] = field(repr=False)  # EMPTY unless status == "done"
    failed_agents: Mapping[str, str]  # name -> error name
    turns: int
    messages: int
    dead_letters: int
    still_running: tuple[str, ...]  # agents abandoned mid-turn at the stop
    observer_errors: int
    message: str = ""  # three lines for Daniel when not done


DEFAULT_TEAM_LIMITS: Final = TeamLimits()


def _bad(what: str, why: str, fix: str) -> TeamError:
    return TeamError(what, why, fix)


def _check_limits(limits: TeamLimits) -> None:
    d = limits.deadline_s
    deadline_ok = isinstance(d, (int, float)) and not isinstance(d, bool)
    deadline_ok = deadline_ok and math.isfinite(d) and 0 < d <= MAX_TEAM_DEADLINE_S
    if not deadline_ok:
        raise _bad(
            "The team time limit is not usable.",
            f"A deadline is required: more than 0 and at most {int(MAX_TEAM_DEADLINE_S)} s.",
            "Set TeamLimits(deadline_s=...) to a finite number of seconds.",
        ) from None
    if not (limits.max_turns >= 1 and 1 <= limits.max_depth <= 3):
        raise _bad(
            "The team limits are not usable.",
            "Turns must be at least 1 and depth 1 to 3.",
            "Change TeamLimits(...) to values in those ranges.",
        ) from None


def _check_personas(personas: Sequence[Persona], tasks: Sequence[TaskSpec]) -> None:
    fix = "Give each agent a role name ending in -agent, such as income-agent."
    if not personas or len(personas) > MAX_AGENTS:
        raise _bad(
            "The team size is not usable.", f"A team has 1 to {MAX_AGENTS} agents.", fix
        ) from None
    names: set[str] = set()
    for position, persona in enumerate(personas, 1):
        name = persona.name if isinstance(persona, Persona) else None
        ok = isinstance(name, str) and AGENT_NAME_PATTERN.fullmatch(name) is not None
        ok = ok and name not in RESERVED_NAMES and name not in names
        ok = ok and name is not None and name.endswith(PERSONA_NAME_SUFFIX)
        ok = ok and persona.max_steps >= 1 and isinstance(persona.profile, str)
        if not ok or name is None:
            raise _bad(
                f"Agent {position} is not usable.", "Names are unique role names.", fix
            ) from None
        names.add(name)
    for task in tasks:
        if task.assignee is not None and task.assignee not in names:
            raise _bad(
                f'Task "{task.id}" is assigned to an agent that is not on the team.',
                "Only team agents can claim tasks.",
                "Fix the assignee or add the agent.",
            ) from None


class _Run:
    """One team run. Lock order is always team lock -> bus lock / board lock."""

    def __init__(
        self,
        personas: Sequence[Persona],
        board: TaskBoard,
        bus: MessageBus,
        endpoints: Mapping[str, Endpoint],
        limits: TeamLimits,
        llm_for: Callable[[Persona], LLM] | None,
        guard: ToolGuard,
        observer: Callable[[TeamEvent], None] | None,
        monotonic: Callable[[], float],
    ) -> None:
        self.personas, self.board, self.bus, self.endpoints = personas, board, bus, endpoints
        self.limits, self.llm_for, self.guard = limits, llm_for, guard
        self.observer, self.mono = observer, monotonic
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.busy: set[str] = set()
        self.failed: dict[str, str] = {}
        self.turns = 0
        self.events: queue.Queue[TeamEvent] = queue.Queue()
        self.seq = 0
        self.observer_errors = 0
        self.live = 1  # the coordinator; each persona thread adds one
        self.live_lock = threading.Lock()
        self.threads: list[tuple[str, threading.Thread]] = []
        self.t0 = monotonic()

    # -- events (any thread puts; only the coordinator numbers and delivers)
    def emit(
        self,
        kind: TeamEventKind,
        *,
        agent: str | None = None,
        task_id: str | None = None,
        message_id: int | None = None,
        size: int | None = None,
        error_type: str | None = None,
        halt_reason: TeamHalt | None = None,
        counts: Mapping[str, int] | None = None,
    ) -> None:
        counts = {} if counts is None else counts
        self.events.put(
            TeamEvent(kind, 0, agent, task_id, message_id, size, error_type, halt_reason, counts)
        )

    def drain(self) -> None:
        while True:
            try:
                raw = self.events.get_nowait()
            except queue.Empty:
                return
            ev = TeamEvent(
                raw.kind,
                self.seq,
                raw.agent,
                raw.task_id,
                raw.message_id,
                raw.size,
                raw.error_type,
                raw.halt_reason,
                raw.counts,
            )
            self.seq += 1
            log.debug(
                "event kind=%s seq=%d agent=%s task=%s msg=%s size=%s error=%s halt=%s",
                ev.kind,
                ev.seq,
                ev.agent,
                ev.task_id,
                ev.message_id,
                ev.size,
                ev.error_type,
                ev.halt_reason,
            )
            if self.observer is not None:
                bad = _notify(self.observer, ev)
                if bad is not None:
                    self.observer_errors += 1
                    log.warning("observer raised %s", error_label(bad[0]))

    def reporter(self, agent: str) -> Callable[..., None]:
        def report(
            kind: str,
            *,
            task_id: str | None = None,
            message_id: int | None = None,
            size: int | None = None,
            error_type: str | None = None,
        ) -> None:
            self.emit(
                cast(TeamEventKind, kind),
                agent=agent,
                task_id=task_id,
                message_id=message_id,
                size=size,
                error_type=error_type,
            )

        return report

    # -- thread side
    def thread_done(self) -> None:
        with self.live_lock:
            self.live -= 1
            last = self.live == 0
        if last:
            _TEAM_LOCK.release()

    def start_thread(self, persona: Persona) -> bool:
        with self.live_lock:
            self.live += 1
        thread = threading.Thread(target=self.thread_main, args=(persona,), daemon=True)
        _, failed = attempt(thread.start, (Exception,))
        if failed is not None:
            release_quietly(1)  # the slot is held only from before start() until the thread ends
            self.thread_done()
            return False
        self.threads.append((persona.name, thread))
        return True

    def thread_main(self, persona: Persona) -> None:
        try:
            _, failed = attempt(lambda: self.persona_body(persona), (BaseException,))
            if failed is not None:  # class only: never the instance, never its text
                self.fail_persona(persona.name, error_label(failed[0]))
        finally:
            release_quietly(1)
            self.thread_done()

    def persona_body(self, persona: Persona) -> None:
        name = persona.name
        endpoint = self.endpoints[name]
        _set_scope(_Scope(1, self.limits.max_depth, self.guard))
        llm = (
            self.llm_for(persona)
            if self.llm_for is not None
            else Router().build_llm(persona.profile, system=persona.system)
        )
        report = self.reporter(name)
        own: list[Tool] = [
            *persona.tools,
            SendMessageTool(endpoint, report=report),
            CompleteTaskTool(self.board, name, report=report),
            FailTaskTool(self.board, name, report=report),
        ]
        tools = _strip_delegate(own, 1, self.limits.max_depth)
        last: list[LoopSnapshot] = []

        def keep(snapshot: LoopSnapshot) -> None:
            last[:] = [snapshot]

        loop = AgentLoop(
            llm,
            tools,
            persona.max_steps,
            context=ContextManager(),
            guard=self.guard,
            checkpoint=keep,
        )
        while not self.stop.is_set():
            prompt = self.take(name, endpoint)
            if prompt is None:
                self.stop.wait(POLL_SECONDS)
                continue
            if last:
                prior = last[0]
                loop.resume(LoopSnapshot(prior.step, (*prior.messages, Message("user", prompt))))
            else:
                loop.run(prompt)
            with self.lock:
                self.busy.discard(name)
                self.emit("turn_finished", agent=name)

    def take(self, name: str, endpoint: Endpoint) -> str | None:
        """Mail first (coworkers' questions), else a task. Marks the agent busy in the same step."""
        with self.lock:
            if self.stop.is_set() or self.turns >= self.limits.max_turns or name in self.failed:
                return None
            msg, bad = attempt(lambda: endpoint.receive(0), (BusError,))
            prompt: str | None = None
            if bad is None and msg is not None:
                prompt = _mail_prompt(msg)
            else:
                spec = self.board.claim(name)
                if spec is not None:
                    self.emit("task_claimed", agent=name, task_id=spec.id)
                    prompt = _task_prompt(spec)
            if prompt is None:
                return None
            self.busy.add(name)
            self.turns += 1
            self.emit("turn_started", agent=name)
            return prompt

    def fail_persona(self, name: str, label: str) -> None:
        with self.lock:
            if name in self.failed:
                return
            self.failed[name] = label
            self.busy.discard(name)
            self.emit("turn_failed", agent=name, error_type=label)
            for task_id in self.board.release_owner(name):
                self.emit("task_failed", agent=name, task_id=task_id)

    # -- coordinator side
    def decide(self) -> tuple[TeamStatus, TeamHalt | None] | None:
        with self.lock:
            if self.board.all_done():
                return "done", None
            if self.failed or self.board.any_failed():
                return "failed", None
            if self.bus.stats().limit_hit:
                return "halted", "message_limit"
            if self.mono() - self.t0 >= self.limits.deadline_s:
                return "halted", "deadline"
            idle = not self.busy
            if idle and self.turns >= self.limits.max_turns:
                return "halted", "turn_limit"
            if idle and self.bus.pending() == 0 and not self.board.claimable():
                return "halted", "stalled"
        return None

    def halt_now(self) -> tuple[str, ...]:
        """Stop the team: agents see BusClosed / board_closed on their next call."""
        with self.lock:
            running = tuple(sorted(self.busy))
            self.stop.set()
        self.board.freeze()
        self.bus.close()
        return running

    def coordinate(self) -> TeamResult:
        decision: tuple[TeamStatus, TeamHalt | None] | None = None
        interrupted = False
        try:
            while decision is None:
                self.drain()
                decision = self.decide()
                if decision is None:
                    time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            interrupted = True  # handled below, outside the except (package rule)
        running = self.halt_now()
        if interrupted:
            self.emit("team_halted", halt_reason="interrupted")
            self.drain()
            raise KeyboardInterrupt  # a fresh instance with no chain
        assert decision is not None
        result = self.build_result(decision[0], decision[1], running)
        for name, thread in self.threads:
            if name not in running:
                thread.join(JOIN_SECONDS)
        kind: TeamEventKind = "team_halted" if decision[0] == "halted" else "team_finished"
        self.emit(kind, halt_reason=decision[1], counts=_counts(result))
        self.drain()
        return result

    def build_result(
        self, status: TeamStatus, halt: TeamHalt | None, running: tuple[str, ...]
    ) -> TeamResult:
        views = self.board.snapshot()
        stats = self.bus.stats()
        failed = dict(self.failed)
        tasks = {i: v.status for i, v in views.items()}
        results = self.board.results() if status == "done" else {}
        return TeamResult(
            status,
            halt,
            tasks,
            MappingProxyType(dict(results)),
            failed,
            self.turns,
            stats.sent,
            stats.dead_letters,
            running,
            self.observer_errors,
            _message(status, halt, tasks, failed, running),
        )


def _notify(observer: Callable[[TeamEvent], None], ev: TeamEvent) -> Failure | None:
    """Run the observer; a failure comes back as (class, errno), never raised."""
    return attempt(lambda: observer(ev), (Exception,))[1]


def _counts(result: TeamResult) -> dict[str, int]:
    done = sum(1 for s in result.tasks.values() if s == "done")
    return {"tasks": len(result.tasks), "done": done, "turns": result.turns}


def _mail_prompt(msg: BusMessage) -> str:
    return f"Message {msg.id} from {msg.sender} (reply with reply_to={msg.id}):{NL}{msg.content}"


def _task_prompt(spec: TaskSpec) -> str:
    return (
        f"You have claimed task {spec.id}:{NL}{spec.description}{NL}"
        "Call complete_task when done, or fail_task if you cannot do it."
    )


def _message(
    status: TeamStatus,
    halt: TeamHalt | None,
    tasks: Mapping[str, TaskStatus],
    failed: Mapping[str, str],
    running: tuple[str, ...],
) -> str:
    extra = [f"{n} failed ({t})" for n, t in sorted(failed.items())]
    extra += [f"{n} was still mid-turn and may still be acting" for n in running]
    if status == "done":
        if not extra:
            return ""
        return NL.join(
            (
                f"All {len(tasks)} tasks are done.",
                "; ".join(extra) + ".",
                "Check the results before relying on any later side effects.",
            )
        )
    todo = sorted(i for i, s in tasks.items() if s != "done")
    if status == "failed":
        bad = ", ".join(sorted(i for i, s in tasks.items() if s == "failed")) or "none"
        who = ", ".join(sorted(failed)) or "none"
        return NL.join(
            (
                f"The team run failed. Failed tasks: {bad}. Failed agents: {who}.",
                "A failed task or agent stops the run so nothing half-finished looks finished.",
                "Fix the cause, then start a new run.",
            )
        )
    first = {
        "stalled": f"Task {todo[0] if todo else '?'} is still waiting.",
        "deadline": (
            f"Agent {running[0]} is still running."
            if running
            else "The team passed its time limit."
        ),
        "turn_limit": "The team used all its turns.",
        "message_limit": "The agents sent too many messages.",
    }.get(halt or "", "The team stopped.")
    second = {
        "stalled": "Every agent was idle with no unread messages, so nothing could move it.",
        "deadline": "It passed the team's time limit and Python cannot stop it.",
        "turn_limit": f"{len(todo)} tasks are still to do.",
        "message_limit": "A reply loop between agents was stopped.",
    }.get(halt or "", "")
    third = {
        "stalled": "Add the missing step or assign it, then start a new run.",
        "deadline": "It may keep running until its call returns; restart the program if it never does.",
        "turn_limit": "Raise TeamLimits.max_turns or simplify the tasks, then start a new run.",
        "message_limit": "Check the agents' instructions, then start a new run.",
    }.get(halt or "", "Start a new run.")
    return NL.join((first, second, third))


def run_team(
    personas: Sequence[Persona],
    tasks: Sequence[TaskSpec],
    *,
    limits: TeamLimits = DEFAULT_TEAM_LIMITS,
    llm_for: Callable[[Persona], LLM] | None = None,
    guard: ToolGuard = guard_tool_call,
    observer: Callable[[TeamEvent], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> TeamResult:
    """Run the team until every task is done, something fails, or a limit stops it.

    Not resumable: if the process dies the run is lost, and tools that already acted may act again.
    """
    _check_limits(limits)
    if not tasks:
        raise _bad(
            "The team has no tasks.",
            "A team with nothing to do has no finished state.",
            "Add the tasks to do.",
        ) from None
    board = TaskBoard(tasks)
    _check_personas(personas, tasks)
    bus = MessageBus(limits.bus)
    endpoints = {p.name: bus.register(p.name) for p in personas}
    if not _TEAM_LOCK.acquire(blocking=False):
        raise _bad(
            "Another team is still running in this program.",
            "Only one team runs at a time, and an abandoned agent keeps the lock until it ends.",
            "Wait for it to finish, or restart the program.",
        ) from None
    run = _Run(personas, board, bus, endpoints, limits, llm_for, guard, observer, monotonic)
    try:
        return _execute(run)
    finally:
        run.thread_done()  # the coordinator's own count: the lock frees with the last thread


def _execute(run: _Run) -> TeamResult:
    if not _BUDGET.reserve(len(run.personas)):
        raise _bad(
            f"Not enough agent capacity: {len(run.personas)} agents asked for, "
            f"{_BUDGET.free()} slots free.",
            f"Every running agent and helper uses one of {MAX_AGENT_THREADS} slots, including "
            "ones still finishing after a time limit.",
            "Use fewer agents, or wait for running work to end.",
        ) from None
    run.emit(
        "team_started", counts={"agents": len(run.personas), "tasks": len(run.board.snapshot())}
    )
    unstarted = list(run.personas)
    start_failed = False
    while unstarted and not start_failed:
        start_failed = not run.start_thread(unstarted.pop(0))
    if start_failed:
        release_quietly(len(unstarted))  # their slots were never used
        run.halt_now()
        for _, thread in run.threads:
            thread.join(JOIN_SECONDS)
        raise _bad(
            "The team could not start all its agents.",
            "The computer refused to start another thread.",
            "Close other work or use fewer agents, then start a new run.",
        ) from None
    return run.coordinate()
