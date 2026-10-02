"""Server-sent-event framing and the idle/ping policy for one run's event queue."""

from __future__ import annotations

import queue
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class EventName(StrEnum):
    PING = "ping"
    MESSAGE = "message"
    DONE = "done"
    ERROR = "error"


TERMINAL: Final = frozenset({EventName.DONE, EventName.ERROR})
IDLE_TIMEOUT_S: Final = 300.0
PING_INTERVAL_S: Final = 10.0
POLL_S: Final = 1.0


@dataclass(frozen=True)
class SseEvent:
    name: EventName
    data: str  # JSON text; a newline inside becomes several data: lines


def encode(event: SseEvent, event_id: int | None = None) -> bytes:
    lines = [] if event_id is None else [f"id: {event_id}"]
    lines.append(f"event: {event.name.value}")
    lines.extend(f"data: {part}" for part in event.data.split("\n"))
    return ("\n".join(lines) + "\n\n").encode()


def event_stream(
    source: queue.Queue[SseEvent],
    *,
    idle_timeout_s: float = IDLE_TIMEOUT_S,
    ping_interval_s: float = PING_INTERVAL_S,
    poll_s: float = POLL_S,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[SseEvent]:
    """Ping at once, then queue events; ping while idle; stop on a terminal event or idle."""
    yield SseEvent(EventName.PING, "{}")
    last_event = last_ping = clock()
    while True:
        try:
            event = source.get(timeout=poll_s)
        except queue.Empty:
            now = clock()
            if now - last_event >= idle_timeout_s:
                return
            if now - last_ping >= ping_interval_s:
                last_ping = now
                yield SseEvent(EventName.PING, "{}")
            continue
        yield event
        last_event = last_ping = clock()
        if event.name in TERMINAL:
            return
