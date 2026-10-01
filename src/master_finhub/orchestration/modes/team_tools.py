"""The three tools a team agent gets: send_message, complete_task, fail_task.

Design: _workspace/02_strategy-architect_slice7.md (revision 3), Decision 3. Each tool is bound to
one agent's own endpoint or name, so an agent cannot act as another. Results are short fixed text;
errors are the bus's or board's three-line text (names and counts only, never message content).
"""

from __future__ import annotations

from typing import Any, Protocol

from master_finhub.orchestration.message_bus import BROADCAST, BusError, Endpoint
from master_finhub.orchestration.modes.task_board import TaskBoard, TaskError
from master_finhub.runtime.loop import ToolSpec

__all__ = ["CompleteTaskTool", "FailTaskTool", "SendMessageTool"]

NL = chr(10)


class Report(Protocol):
    """Team-side hook for events. Carries ids, sizes and fixed codes, never text."""

    def __call__(
        self,
        kind: str,
        *,
        task_id: str | None = None,
        message_id: int | None = None,
        size: int | None = None,
        error_type: str | None = None,
    ) -> None: ...


def _flat(exc: BusError | TaskError) -> str:
    return "Error: " + str(exc).replace(NL, " ")


def _size(text: object) -> int | None:
    return len(text.encode("utf-8", "replace")) if isinstance(text, str) else None


class SendMessageTool:
    spec = ToolSpec(
        name="send_message",
        description=(
            "Send a message to a teammate by name, or to everyone with to='all'. Use to ask a "
            "question or share a finding. Takes to, message and an optional reply_to message id. "
            "Returns that it was delivered; the answer arrives as your next input."
        ),
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "message": {"type": "string"},
                "reply_to": {"type": "integer"},
            },
            "required": ["to", "message"],
        },
    )

    def __init__(self, endpoint: Endpoint, *, report: Report | None = None) -> None:
        self._endpoint = endpoint
        self._report = report

    def run(self, arguments: dict[str, Any]) -> str:
        to, message, reply_to = (
            arguments.get("to"),
            arguments.get("message"),
            arguments.get("reply_to"),
        )
        bad_reply = reply_to is not None and type(reply_to) is not int
        if not isinstance(to, str) or not isinstance(message, str) or bad_reply:
            return "Error: send_message needs text for to and message, and a whole number reply_to."
        sent: int | None = None
        try:
            if to == BROADCAST:
                copies = self._endpoint.broadcast(message)
                text = f"Delivered to {copies} agents."
            else:
                sent = self._endpoint.send(to, message, reply_to=reply_to)
                text = f"Delivered as message {sent}."
        except BusError as exc:
            if self._report is not None:
                self._report("message_rejected", error_type=exc.code)
            return _flat(exc)
        if self._report is not None:
            self._report("message_sent", message_id=sent, size=_size(message))
        return text


class CompleteTaskTool:
    spec = ToolSpec(
        name="complete_task",
        description=(
            "Mark the task you claimed as done and store its result. Use when the work is "
            "finished. Takes task_id and result (plain text summary). Returns confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "result": {"type": "string"}},
            "required": ["task_id", "result"],
        },
    )

    def __init__(self, board: TaskBoard, agent: str, *, report: Report | None = None) -> None:
        self._board = board
        self._agent = agent
        self._report = report

    def run(self, arguments: dict[str, Any]) -> str:
        task_id, result = arguments.get("task_id"), arguments.get("result")
        if not isinstance(task_id, str) or not isinstance(result, str):
            return "Error: complete_task needs text for task_id and result."
        try:
            self._board.complete(self._agent, task_id, result)
        except TaskError as exc:
            return _flat(exc)
        if self._report is not None:
            self._report("task_done", task_id=task_id, size=_size(result))
        return f"Task {task_id} completed."


class FailTaskTool:
    spec = ToolSpec(
        name="fail_task",
        description=(
            "Mark the task you claimed as failed because you cannot do it. Use only when the "
            "work cannot be completed. Takes task_id. Returns confirmation; the team run stops."
        ),
        parameters={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    )

    def __init__(self, board: TaskBoard, agent: str, *, report: Report | None = None) -> None:
        self._board = board
        self._agent = agent
        self._report = report

    def run(self, arguments: dict[str, Any]) -> str:
        task_id = arguments.get("task_id")
        if not isinstance(task_id, str):
            return "Error: fail_task needs text for task_id."
        try:
            self._board.fail(self._agent, task_id)
        except TaskError as exc:
            return _flat(exc)
        if self._report is not None:
            self._report("task_failed", task_id=task_id)
        return f"Task {task_id} marked failed."
