"""In-process message bus for team mode: one bounded mailbox per named agent.

Design: _workspace/02_strategy-architect_slice7.md (revision 3), Decision 1. Threads, not
asyncio: every agent already runs on a thread, and one lock plus a ``Condition`` per mailbox can
be closed and woken honestly. The bus carries text between role agents ("income-agent"); it never
logs, prints or puts message content in an error. Errors name registered agents and counts only.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Literal, NamedTuple

from master_finhub.orchestration._fsio import attempt
from master_finhub.orchestration.graph import POLL_SECONDS
from master_finhub.orchestration.graph_store import GraphError
from master_finhub.sandbox.workspace import RESERVED

__all__ = [
    "AGENT_NAME_PATTERN",
    "BROADCAST",
    "MAX_AGENTS",
    "RESERVED_NAMES",
    "BusClosed",
    "BusError",
    "BusLimits",
    "BusMessage",
    "BusStats",
    "Endpoint",
    "MessageBus",
]

AGENT_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9-]{0,30}[a-z0-9]")  # fullmatch only
BROADCAST: Final = "all"
RESERVED_NAMES: Final = (
    frozenset({"all", "lead", "bus", "system", "user", "self", "none", "everyone"}) | RESERVED
)
MAX_AGENTS: Final = 16
log = logging.getLogger("master_finhub.orchestration.message_bus")

BusErrorCode = Literal[
    "invalid_name",
    "duplicate_name",
    "too_many_agents",
    "unknown_recipient",
    "self_send",
    "recipient_gone",
    "mailbox_full",
    "not_text",
    "too_large",
    "bad_reply",
    "too_many_hops",
    "message_limit",
    "closed",
]


class BusError(GraphError):
    """Three lines: what / why / fix. Names and counts only, never message content."""

    def __init__(self, code: BusErrorCode, what: str, why: str, fix: str) -> None:
        super().__init__(what, why, fix)
        self.code: BusErrorCode = code


class BusClosed(BusError):
    """The bus is closed (or this agent has left it); code is always "closed"."""


@dataclass(frozen=True)
class BusLimits:
    mailbox_size: int = 64  # unread messages per agent, 1..1024
    max_message_bytes: int = 32_768  # UTF-8 bytes of one message, 1..262_144
    max_messages: int = 256  # accepted sends over the bus lifetime (a broadcast counts per copy)
    max_hops: int = 8  # replies in one conversation, 1..64

    def __post_init__(self) -> None:
        ok = 1 <= self.mailbox_size <= 1024 and 1 <= self.max_message_bytes <= 262_144
        ok = ok and 1 <= self.max_messages <= 10_000 and 1 <= self.max_hops <= 64
        if not ok:
            raise GraphError(
                "The bus limits are not usable.",
                "Mailbox 1..1024, message bytes 1..262144, messages 1..10000, hops 1..64.",
                "Change BusLimits(...) to values in those ranges.",
            ) from None


@dataclass(frozen=True)
class BusMessage:
    id: int  # bus-assigned, strictly increasing over the whole bus
    sender: str  # set by the bus from the sending Endpoint; never a caller argument
    recipient: str
    conversation: int  # id of the conversation's first message
    hop: int  # 0 for a new conversation; a reply is parent.hop + 1
    reply_to: int | None
    content: str = field(repr=False)  # never in repr, events, logs or errors


@dataclass(frozen=True)
class BusStats:
    sent: int
    rejected: Mapping[str, int]  # code -> count
    dead_letters: int  # unread when dropped (close / retire); count only, content discarded
    limit_hit: bool  # max_messages reached
    closed: bool


class _Meta(NamedTuple):
    recipient: str
    conversation: int
    hop: int


class _Reject(NamedTuple):
    code: BusErrorCode
    names: tuple[str, ...] = ()
    number: int = 0


class _Box:
    def __init__(self, lock: threading.Lock) -> None:
        self.q: deque[BusMessage] = deque()
        self.cond = threading.Condition(lock)
        self.retired = False


_TEXT: Final[dict[str, tuple[str, str, str]]] = {
    "invalid_name": (
        "That agent name is not allowed.",
        "Names are 2-32 lower-case letters, digits or inner hyphens, and not a reserved word.",
        "Use a role name such as income-agent.",
    ),
    "duplicate_name": (
        "That agent name is already registered.",
        "Every agent on the bus needs its own name.",
        "Pick a different role name.",
    ),
    "too_many_agents": (
        "Too many agents on the bus.",
        "A bus holds at most {n} agents.",
        "Use fewer agents.",
    ),
    "unknown_recipient": (
        "Unknown recipient.",
        "Registered agents: {names}.",
        'Send to one of those names, or "all".',
    ),
    "self_send": (
        "An agent cannot message itself.",
        "Messages go to other agents.",
        "Pick another recipient.",
    ),
    "recipient_gone": (
        "That agent has left the bus.",
        "It failed or was retired, so it will not read mail.",
        "Message another agent, or finish the work yourself.",
    ),
    "mailbox_full": (
        "That agent's mailbox is full.",
        "It already holds {n} unread messages.",
        "Finish your turn so it can read them, then try again.",
    ),
    "not_text": (
        "The message is not plain text.",
        "Messages must be text that can be stored as UTF-8.",
        "Send plain text.",
    ),
    "too_large": (
        "The message is too large.",
        "A message may hold at most {n} bytes.",
        "Send a short summary instead.",
    ),
    "bad_reply": (
        "That reply does not match a message you received.",
        "reply_to must be the id of a message sent to you.",
        "Use the id shown in the message you are answering.",
    ),
    "too_many_hops": (
        "This conversation has gone back and forth too many times.",
        "A conversation allows at most {n} replies.",
        "Finish the task, or start a new topic if it is needed.",
    ),
    "message_limit": (
        "The bus has reached its message limit.",
        "At most {n} messages are accepted in one run.",
        "Stop messaging and finish your task.",
    ),
    "closed": (
        "The message bus is closed to you.",
        "The run is over or this agent has left it.",
        "End your turn.",
    ),
}


def _build(reject: _Reject) -> BusError:
    what, why, fix = _TEXT[reject.code]
    why = why.format(names=", ".join(reject.names) or "none", n=reject.number)
    cls = BusClosed if reject.code == "closed" else BusError
    return cls(reject.code, what, why, fix)


def _content_problem(content: object, max_bytes: int) -> tuple[BusErrorCode | None, int]:
    """(code, utf-8 size). Cheap length test first: a code point is at least one byte."""
    if type(content) is not str:
        return "not_text", 0
    assert isinstance(content, str)
    if len(content) > max_bytes:
        return "too_large", 0
    encoded, bad = attempt(lambda: content.encode("utf-8"), (UnicodeError,))
    if bad is not None or encoded is None:
        return "not_text", 0
    return ("too_large" if len(encoded) > max_bytes else None), len(encoded)


class Endpoint:
    """One agent's handle. Holds no name: the bus stamps the sender from its own table."""

    __slots__ = ("_bus",)

    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus

    @property
    def name(self) -> str:
        return self._bus._name_of(self)

    def send(self, to: str, content: str, *, reply_to: int | None = None) -> int:
        """Put one message in ``to``'s mailbox and return its id (delivered, not acknowledged)."""
        return self._bus._send(self, to, content, reply_to)

    def broadcast(self, content: str) -> int:
        """One copy to every other live agent, all or nothing. Returns the number of copies."""
        return self._bus._broadcast(self, content)

    def receive(self, timeout: float | None = None) -> BusMessage | None:
        """Oldest unread message, or None on timeout. Raises BusClosed once the bus is closed."""
        return self._bus._receive(self, timeout)


DEFAULT_BUS_LIMITS: Final = BusLimits()


class MessageBus:
    def __init__(self, limits: BusLimits = DEFAULT_BUS_LIMITS) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._boxes: dict[str, _Box] = {}
        self._endpoints: dict[str, Endpoint] = {}  # keeps endpoints alive so id() stays unique
        self._names: dict[int, str] = {}  # id(endpoint) -> name: the only source of "sender"
        self._meta: dict[int, _Meta] = {}  # bounded by max_messages; never holds content
        self._next_id = 1
        self._sent = 0
        self._rejected: dict[str, int] = {}
        self._dead = 0
        self._limit_hit = False
        self._closed = False

    # -- registry
    def register(self, name: str) -> Endpoint:
        reject: _Reject | None = None
        ok = type(name) is str and AGENT_NAME_PATTERN.fullmatch(name) is not None
        ok = ok and name not in RESERVED_NAMES
        endpoint = Endpoint(self)
        with self._lock:
            if self._closed:
                reject = _Reject("closed")
            elif not ok:
                reject = _Reject("invalid_name")
            elif name in self._boxes:
                reject = _Reject("duplicate_name")
            elif len(self._boxes) >= MAX_AGENTS:
                reject = _Reject("too_many_agents", number=MAX_AGENTS)
            else:
                self._boxes[name] = _Box(self._lock)
                self._endpoints[name] = endpoint
                self._names[id(endpoint)] = name
            if reject is not None:
                self._count(reject.code)
        if reject is not None:
            raise _build(reject) from None
        log.debug("bus register name=%s", name)
        return endpoint

    def retire(self, name: str) -> int:
        """Agent gone: unread mail becomes dead letters (returned); later sends are refused."""
        reject: _Reject | None = None
        dropped = 0
        with self._lock:
            box = self._boxes.get(name) if type(name) is str else None
            if box is None:
                reject = _Reject("unknown_recipient", tuple(sorted(self._live())))
            elif not box.retired:
                box.retired = True
                dropped = len(box.q)
                box.q.clear()
                self._dead += dropped
                box.cond.notify_all()
        if reject is not None:
            raise _build(reject) from None
        log.debug("bus retire name=%s dead_letters=%d", name, dropped)
        return dropped

    def _name_of(self, endpoint: Endpoint) -> str:
        with self._lock:
            return self._names[id(endpoint)]

    def _live(self) -> list[str]:
        return [n for n, b in self._boxes.items() if not b.retired]

    def _count(self, code: str) -> None:
        self._rejected[code] = self._rejected.get(code, 0) + 1

    # -- sending
    def _check(
        self, sender: str, to: object, reply_to: object, problem: BusErrorCode | None
    ) -> tuple[_Reject | None, _Meta | None]:
        """Validate one send under the lock. Returns (rejection, reply parent or None)."""
        mine = self._boxes[sender]
        if self._closed or mine.retired:
            return _Reject("closed"), None
        if problem is not None:
            return _Reject(problem, number=self._limits.max_message_bytes), None
        box = self._boxes.get(to) if type(to) is str else None
        if box is None:
            return _Reject("unknown_recipient", tuple(sorted(self._live()))), None
        if box.retired:
            return _Reject("recipient_gone"), None
        if to == sender:
            return _Reject("self_send"), None
        parent: _Meta | None = None
        if reply_to is not None:
            found = self._meta.get(reply_to) if type(reply_to) is int else None
            if found is None or found.recipient != sender:
                return _Reject("bad_reply"), None
            if found.hop + 1 > self._limits.max_hops:
                return _Reject("too_many_hops", number=self._limits.max_hops), None
            parent = found
        if self._sent >= self._limits.max_messages:
            self._limit_hit = True
            return _Reject("message_limit", number=self._limits.max_messages), None
        if len(box.q) >= self._limits.mailbox_size:
            return _Reject("mailbox_full", number=self._limits.mailbox_size), None
        return None, parent

    def _enqueue(
        self, sender: str, to: str, content: str, reply_to: int | None, parent: _Meta | None
    ) -> int:
        mid = self._next_id
        self._next_id += 1
        conversation = mid if parent is None else parent.conversation
        hop = 0 if parent is None else parent.hop + 1
        box = self._boxes[to]
        box.q.append(BusMessage(mid, sender, to, conversation, hop, reply_to, content))
        box.cond.notify()
        self._meta[mid] = _Meta(to, conversation, hop)
        self._sent += 1
        return mid

    def _send(self, endpoint: Endpoint, to: str, content: str, reply_to: int | None) -> int:
        problem, size = _content_problem(content, self._limits.max_message_bytes)
        reject: _Reject | None = None
        mid = 0
        with self._lock:
            sender = self._names[id(endpoint)]
            reject, parent = self._check(sender, to, reply_to, problem)
            if reject is None:
                mid = self._enqueue(sender, to, content, reply_to, parent)
            else:
                self._count(reject.code)
        if reject is not None:
            log.debug("bus reject code=%s from=%s", reject.code, sender)
            raise _build(reject) from None
        log.debug("bus send id=%d from=%s to=%s bytes=%d", mid, sender, to, size)
        return mid

    def _broadcast(self, endpoint: Endpoint, content: str) -> int:
        problem, size = _content_problem(content, self._limits.max_message_bytes)
        reject: _Reject | None = None
        count = 0
        with self._lock:
            sender = self._names[id(endpoint)]
            targets = sorted(n for n in self._live() if n != sender)
            if self._closed or self._boxes[sender].retired:
                reject = _Reject("closed")
            elif problem is not None:
                reject = _Reject(problem, number=self._limits.max_message_bytes)
            elif self._sent + len(targets) > self._limits.max_messages:
                self._limit_hit = True
                reject = _Reject("message_limit", number=self._limits.max_messages)
            elif any(len(self._boxes[t].q) >= self._limits.mailbox_size for t in targets):
                reject = _Reject("mailbox_full", number=self._limits.mailbox_size)
            else:
                for target in targets:
                    self._enqueue(sender, target, content, None, None)
                count = len(targets)
            if reject is not None:
                self._count(reject.code)
        if reject is not None:
            raise _build(reject) from None
        log.debug("bus broadcast from=%s copies=%d bytes=%d", sender, count, size)
        return count

    # -- receiving
    def _receive(self, endpoint: Endpoint, timeout: float | None) -> BusMessage | None:
        msg: BusMessage | None = None
        code: BusErrorCode | None = None
        end = None if timeout is None else time.monotonic() + max(timeout, 0.0)
        with self._lock:
            box = self._boxes[self._names[id(endpoint)]]
            while True:
                if box.q:
                    msg = box.q.popleft()
                    break
                if self._closed:
                    code = "closed"
                    break
                if box.retired:
                    code = "recipient_gone"
                    break
                wait = POLL_SECONDS if end is None else min(POLL_SECONDS, end - time.monotonic())
                if wait <= 0:
                    break  # timeout (also timeout=0)
                box.cond.wait(wait)  # slices keep Ctrl-C on the main thread responsive
        if code is not None:
            raise _build(_Reject(code)) from None
        return msg

    # -- inspection and shutdown
    def pending(self) -> int:
        with self._lock:
            return sum(len(b.q) for b in self._boxes.values())

    def stats(self) -> BusStats:
        with self._lock:
            return self._stats()

    def _stats(self) -> BusStats:
        return BusStats(
            self._sent,
            MappingProxyType(dict(self._rejected)),
            self._dead,
            self._limit_hit,
            self._closed,
        )

    def close(self) -> BusStats:
        """Idempotent. Counts and drops unread mail, then wakes every waiter."""
        with self._lock:
            if not self._closed:
                self._closed = True
                for box in self._boxes.values():
                    self._dead += len(box.q)
                    box.q.clear()
                    box.cond.notify_all()
            stats = self._stats()
        log.debug("bus close sent=%d dead_letters=%d", stats.sent, stats.dead_letters)
        return stats
