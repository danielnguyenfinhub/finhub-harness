"""Shared fakes for the slice 7 tests (not collected: no test_ prefix). Synthetic data only."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from master_finhub.orchestration.modes import team as team_mod
from master_finhub.orchestration.modes.subagent import _BUDGET, MAX_AGENT_THREADS
from master_finhub.runtime.loop import AssistantMessage, Message, ToolCall, ToolSpec

MARKER = "CLIENT-DOE-MARKER-1234"
Fn = Callable[[list[Message], list[ToolSpec]], AssistantMessage]


class FnLLM:
    """An LLM whose behaviour is one function of (messages, tools)."""

    def __init__(self, fn: Fn) -> None:
        self.fn = fn
        self.calls = 0

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.calls += 1
        return self.fn(messages, tools)


def call(name: str, **args: Any) -> AssistantMessage:
    return AssistantMessage("", [ToolCall(f"c-{name}", name, dict(args))])


def say(text: str) -> AssistantMessage:
    return AssistantMessage(text)


def asker_fn(messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
    last = messages[-1]
    if last.role == "tool":
        return say("ok")
    if last.content.startswith("You have claimed task"):
        return call("send_message", to="answerer-agent", message="what is 6x7?")
    if last.content.startswith("Message "):
        return call(
            "complete_task", task_id="t1", result="reply=" + last.content.split(":\n", 1)[1]
        )
    return say("?")


def answerer_fn(messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
    last = messages[-1]
    if last.role == "tool":
        return say("ok")
    found = re.match(r"Message (\d+) from", last.content)
    if found is not None:
        return call("send_message", to="asker-agent", message="forty-two", reply_to=int(found[1]))
    return say("?")


class Gate:
    """A blocking point for hung-turn tests; always released in a finally."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def hang(self) -> AssistantMessage:
        self.started.set()
        self.release.wait(30)
        return say("late")


def settle(timeout: float = 8.0) -> bool:
    """Wait until no abandoned agent thread holds a budget slot or the one-team lock."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if _BUDGET.free() == MAX_AGENT_THREADS and not team_mod._TEAM_LOCK.locked():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(autouse=True)
def _quiet_after() -> Iterator[None]:
    yield
    assert settle(), "an agent thread was left holding a budget slot or the team lock"
