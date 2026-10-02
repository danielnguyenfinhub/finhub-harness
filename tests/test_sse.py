"""Slice 10: SSE framing and the event_stream generator (synthetic data only)."""

import itertools
import queue

from master_finhub.server.sse import EventName, SseEvent, encode, event_stream


def parse_frame(raw: bytes) -> tuple[str | None, str, str]:
    """Reference client parser: (id, event, data) with multi-line data joined by newline."""
    fid, name, data = None, "message", []
    for line in raw.decode().split("\n"):
        field, _, value = line.partition(": ")
        if field == "id":
            fid = value
        elif field == "event":
            name = value
        elif field == "data":
            data.append(value)
    return fid, name, "\n".join(data)


def test_encode_frame() -> None:
    frame = encode(SseEvent(EventName.MESSAGE, '"x"'), 3)
    assert frame == b'id: 3\nevent: message\ndata: "x"\n\n'
    assert parse_frame(frame.rstrip(b"\n")) == ("3", "message", '"x"')
    multi = encode(SseEvent(EventName.MESSAGE, "a\nb"))
    assert multi == b"event: message\ndata: a\ndata: b\n\n"
    assert parse_frame(multi.rstrip(b"\n"))[2] == "a\nb"


def test_ping_first_then_event_then_stop() -> None:
    q: queue.Queue[SseEvent] = queue.Queue()
    q.put(SseEvent(EventName.MESSAGE, "1"))
    q.put(SseEvent(EventName.DONE, "2"))
    q.put(SseEvent(EventName.MESSAGE, "never"))
    names = [e.name for e in event_stream(q, poll_s=0.01)]
    assert names == [EventName.PING, EventName.MESSAGE, EventName.DONE]


def test_error_is_terminal() -> None:
    q: queue.Queue[SseEvent] = queue.Queue()
    q.put(SseEvent(EventName.ERROR, '"X"'))
    assert [e.name for e in event_stream(q, poll_s=0.01, idle_timeout_s=0.3)] == [
        EventName.PING,
        EventName.ERROR,
    ]


class _ClockQueue(queue.Queue[SseEvent]):
    """Empty queue whose every poll advances a fake clock by the poll interval."""

    def __init__(self, tick: float) -> None:
        super().__init__()
        self.now = 0.0
        self.tick = tick

    def get(self, block: bool = True, timeout: float | None = None) -> SseEvent:
        self.now += self.tick
        raise queue.Empty


def test_idle_pings_then_timeout() -> None:
    q = _ClockQueue(1.0)
    gen = event_stream(q, idle_timeout_s=5, ping_interval_s=2, poll_s=1.0, clock=lambda: q.now)
    names = [
        e.name for e in itertools.islice(gen, 50)
    ]  # cap: a missing timeout must fail, not hang
    assert names == [EventName.PING] * 3


def test_real_event_resets_idle_timer() -> None:
    q = _ClockQueue(1.0)
    seen: list[EventName] = []
    gen = event_stream(q, idle_timeout_s=3, ping_interval_s=100, poll_s=1.0, clock=lambda: q.now)
    seen.append(next(gen).name)  # initial ping

    def late_event(block: bool = True, timeout: float | None = None) -> SseEvent:
        q.now = 2.5  # almost idle when a real event finally arrives
        return SseEvent(EventName.MESSAGE, "m")

    q.get = late_event  # type: ignore[method-assign,assignment]
    seen.append(next(gen).name)
    del q.get
    # polls at 3.5, 4.5, 5.5: only 3s idle since 2.5 -> stops at 5.5, not at 3.5
    seen.extend(itertools.islice((e.name for e in gen), 50))
    assert seen == [EventName.PING, EventName.MESSAGE]
    assert q.now == 5.5


def test_dropping_error_from_terminal_set_is_caught_fast() -> None:
    """If ERROR stops being terminal the stream keeps pinging until idle; fail in 0.3 s, not 300."""
    q: queue.Queue[SseEvent] = queue.Queue()
    q.put(SseEvent(EventName.ERROR, '"X"'))
    names = [e.name for e in event_stream(q, idle_timeout_s=0.3, ping_interval_s=0.05, poll_s=0.01)]
    assert names == [EventName.PING, EventName.ERROR]
