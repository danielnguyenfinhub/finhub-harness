"""Shared task list for team mode: claimed exactly once, finished only by the owner.

Design: _workspace/02_strategy-architect_slice7.md (revision 3), Decision 2. The board is seeded
once by the caller and never grows; agents can claim, complete and fail tasks. A task may depend
only on tasks listed earlier, so the dependency graph is acyclic by construction. Errors name task
ids and counts only, never a description or a result.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Literal

from master_finhub.orchestration._fsio import attempt
from master_finhub.orchestration.graph_store import NODE_ID_PATTERN, GraphError

__all__ = [
    "MAX_DESCRIPTION_BYTES",
    "MAX_TASKS",
    "TaskBoard",
    "TaskError",
    "TaskSpec",
    "TaskStatus",
    "TaskView",
]

MAX_TASKS: Final = 256
MAX_DESCRIPTION_BYTES: Final = 8_192
TaskStatus = Literal["pending", "claimed", "done", "failed"]
TaskErrorCode = Literal[
    "invalid_task",
    "unknown_task",
    "not_owner",
    "wrong_status",
    "too_large",
    "not_text",
    "board_closed",
]


class TaskError(GraphError):
    """Three lines: what / why / fix. Task ids and counts only."""

    def __init__(self, code: TaskErrorCode, what: str, why: str, fix: str) -> None:
        super().__init__(what, why, fix)
        self.code: TaskErrorCode = code


@dataclass(frozen=True)
class TaskSpec:
    id: str  # NODE_ID_PATTERN, e.g. "t1", "income_check"
    description: str = field(repr=False)
    deps: tuple[str, ...] = ()  # ids of tasks listed EARLIER in the same board
    assignee: str | None = None  # only this agent may claim it; None = anyone


@dataclass(frozen=True)
class TaskView:
    id: str
    status: TaskStatus
    owner: str | None
    deps: tuple[str, ...]


def _invalid(why: str, fix: str) -> TaskError:
    return TaskError("invalid_task", "The task list is not usable.", why, fix)


def _text_size(value: object, cap: int) -> tuple[TaskErrorCode | None, int]:
    """(problem, utf-8 size) for task text. Length is tested before encoding."""
    if type(value) is not str:
        return "not_text", 0
    assert isinstance(value, str)
    if len(value) > cap:
        return "too_large", 0
    encoded, bad = attempt(lambda: value.encode("utf-8"), (UnicodeError,))
    if bad is not None or encoded is None:
        return "not_text", 0
    return ("too_large" if len(encoded) > cap else None), len(encoded)


def _validate(tasks: Sequence[TaskSpec]) -> None:
    if not tasks:
        raise _invalid("A board needs at least one task.", "Add the tasks to do.") from None
    if len(tasks) > MAX_TASKS:
        raise _invalid(f"At most {MAX_TASKS} tasks fit on a board.", "Split the work.") from None
    seen: set[str] = set()
    for position, task in enumerate(tasks, 1):
        ok = isinstance(task, TaskSpec) and isinstance(task.id, str)
        ok = ok and NODE_ID_PATTERN.fullmatch(task.id) is not None
        if not ok:
            raise _invalid(
                f"Task {position} has no usable id.",
                "Ids are a lower-case letter then up to 31 lower-case letters, digits or _.",
            ) from None
        if task.id in seen:
            raise _invalid(f'Task "{task.id}" appears twice.', "Ids must be unique.") from None
        problem, _ = _text_size(task.description, MAX_DESCRIPTION_BYTES)
        if problem is not None:
            raise _invalid(
                f'Task "{task.id}" has a description that is not usable.',
                f"A description is plain text of at most {MAX_DESCRIPTION_BYTES} bytes.",
            ) from None
        if not (task.assignee is None or type(task.assignee) is str):
            raise _invalid(f'Task "{task.id}" has a bad assignee.', "Use an agent name.") from None
        for dep in task.deps:
            if not (isinstance(dep, str) and dep in seen):
                raise _invalid(
                    f'Task "{task.id}" depends on a task that is not listed before it.',
                    "A task may only wait for tasks listed earlier.",
                ) from None
        seen.add(task.id)


class TaskBoard:
    def __init__(self, tasks: Sequence[TaskSpec], *, max_result_bytes: int = 32_768) -> None:
        _validate(tasks)
        self._lock = threading.Lock()
        self._specs = {t.id: t for t in tasks}
        self._order = sorted(self._specs)  # claim order: lowest id first
        self._status: dict[str, TaskStatus] = {t.id: "pending" for t in tasks}
        self._owner: dict[str, str | None] = {t.id: None for t in tasks}
        self._results: dict[str, str] = {}
        self._max_result = max_result_bytes
        self._frozen = False

    def _closed(self) -> TaskError | None:
        if self._frozen:
            return TaskError(
                "board_closed",
                "The task list is closed.",
                "The run is over.",
                "End your turn.",
            )
        return None

    def _ready(self, task_id: str) -> bool:
        return all(self._status[d] == "done" for d in self._specs[task_id].deps)

    def claim(self, agent: str) -> TaskSpec | None:
        """Lowest id that is pending, has all deps done and fits the assignee; else None."""
        with self._lock:
            if self._frozen:
                return None
            for task_id in self._order:
                spec = self._specs[task_id]
                fits = spec.assignee is None or spec.assignee == agent
                if self._status[task_id] == "pending" and fits and self._ready(task_id):
                    self._status[task_id] = "claimed"
                    self._owner[task_id] = agent
                    return spec
        return None

    def _own(self, agent: str, task_id: str) -> TaskError | None:
        if self._frozen:
            return self._closed()
        if task_id not in self._specs:
            return TaskError(
                "unknown_task",
                "No such task.",
                "Task ids are the ones in the task you were given.",
                "Use the id from your claimed task.",
            )
        if self._owner[task_id] != agent:
            return TaskError(
                "not_owner",
                f'You do not own task "{task_id}".',
                "Only the agent that claimed a task can finish or fail it.",
                "Finish only your own task.",
            )
        if self._status[task_id] != "claimed":
            return TaskError(
                "wrong_status",
                f'Task "{task_id}" is not open.',
                "It is already finished.",
                "Move on to your next input.",
            )
        return None

    def complete(self, agent: str, task_id: str, result: str) -> None:
        problem, _ = _text_size(result, self._max_result)
        error: TaskError | None = None
        with self._lock:
            error = self._own(agent, task_id)
            if error is None and problem is not None:
                error = TaskError(
                    problem,
                    "The result is not usable.",
                    f"A result is plain text of at most {self._max_result} bytes.",
                    "Summarise it, then call complete_task again.",
                )
            if error is None:
                self._status[task_id] = "done"
                self._results[task_id] = result
        if error is not None:
            raise error from None

    def fail(self, agent: str, task_id: str) -> None:
        error: TaskError | None = None
        with self._lock:
            error = self._own(agent, task_id)
            if error is None:
                self._status[task_id] = "failed"
        if error is not None:
            raise error from None

    def release_owner(self, agent: str) -> tuple[str, ...]:
        """Agent died: its claimed tasks become failed (never handed to someone else)."""
        with self._lock:
            lost = tuple(
                i for i in self._order if self._owner[i] == agent and self._status[i] == "claimed"
            )
            for task_id in lost:
                self._status[task_id] = "failed"
        return lost

    def claimable(self) -> bool:
        """Some task is pending with every dependency done."""
        with self._lock:
            return not self._frozen and any(
                self._status[i] == "pending" and self._ready(i) for i in self._order
            )

    def all_done(self) -> bool:
        with self._lock:
            return all(s == "done" for s in self._status.values())

    def any_failed(self) -> bool:
        with self._lock:
            return any(s == "failed" for s in self._status.values())

    def snapshot(self) -> Mapping[str, TaskView]:
        with self._lock:
            return MappingProxyType(
                {
                    i: TaskView(i, self._status[i], self._owner[i], self._specs[i].deps)
                    for i in self._order
                }
            )

    def results(self) -> Mapping[str, str]:
        """EMPTY unless every task is done: never a plausible partial."""
        with self._lock:
            done = all(s == "done" for s in self._status.values())
            return MappingProxyType({i: self._results[i] for i in self._order} if done else {})

    def freeze(self) -> None:
        """After a stop: every mutation is refused with "board_closed"."""
        with self._lock:
            self._frozen = True
