"""Slice 7 proof tests, part 1: the message bus (synthetic roles and strings only)."""

from __future__ import annotations

import _thread
import inspect
import logging
import threading
import time
import tracemalloc

import pytest

from master_finhub.orchestration.graph_store import GraphError
from master_finhub.orchestration.message_bus import (
    BusClosed,
    BusError,
    BusLimits,
    Endpoint,
    MessageBus,
)

MARKER = "CLIENT-DOE-MARKER-1234"


DEFAULT = BusLimits()


def _pair(limits: BusLimits = DEFAULT) -> tuple[MessageBus, Endpoint, Endpoint]:
    bus = MessageBus(limits)
    return bus, bus.register("a-agent"), bus.register("b-agent")


def _code(exc_info: pytest.ExceptionInfo[BusError]) -> str:
    return exc_info.value.code


def test_two_agents_exchange_and_reply_round_trips() -> None:  # T1
    _, a, b = _pair()
    first = a.send("b-agent", "question?")
    got = b.receive(1)
    assert got is not None and got.sender == "a-agent" and got.hop == 0 and got.id == first
    reply = b.send("a-agent", "answer.", reply_to=first)
    back = a.receive(1)
    assert back is not None
    assert (back.sender, back.reply_to, back.conversation, back.hop) == (
        "b-agent",
        first,
        first,
        1,
    )
    assert back.content == "answer." and back.id == reply


def test_per_sender_fifo_under_threads() -> None:  # T2
    bus = MessageBus(BusLimits(mailbox_size=1024, max_messages=10_000))
    sink = bus.register("sink-agent")
    senders = [bus.register(f"s{i}-agent") for i in range(8)]

    def send_all(ep: Endpoint) -> None:
        for n in range(500):
            while True:
                try:
                    ep.send("sink-agent", f"{ep.name}:{n}")
                    break
                except BusError as exc:
                    assert exc.code == "mailbox_full"
                    time.sleep(0)

    threads = [threading.Thread(target=send_all, args=(s,)) for s in senders]
    for t in threads:
        t.start()
    seen: dict[str, list[int]] = {}
    ids: list[int] = []
    while len(ids) < 4000:
        msg = sink.receive(5)
        assert msg is not None
        ids.append(msg.id)
        who, n = msg.content.split(":")
        seen.setdefault(who, []).append(int(n))
    for t in threads:
        t.join(5)
    assert all(v == list(range(500)) for v in seen.values()) and len(seen) == 8
    assert ids == sorted(ids) and len(set(ids)) == 4000


def test_full_mailbox_rejects_at_once() -> None:  # T3
    bus, a, _b = _pair(BusLimits(mailbox_size=3))
    for _ in range(3):
        a.send("b-agent", "x")
    start = time.monotonic()
    with pytest.raises(BusError) as exc_info:
        a.send("b-agent", "x")
    assert time.monotonic() - start < 0.05 and _code(exc_info) == "mailbox_full"
    assert bus.pending() == 3 and bus.stats().rejected == {"mailbox_full": 1}


def test_invalid_reserved_duplicate_and_too_many_names_rejected() -> None:  # T4
    bus = MessageBus()
    for bad in ("All", "all", "nul", "-x", "a" * 33, "x", "a_b", "lead"):
        with pytest.raises(BusError) as exc_info:
            bus.register(bad)
        assert _code(exc_info) == "invalid_name"
    bus.register("ok-agent")
    with pytest.raises(BusError) as dup:
        bus.register("ok-agent")
    assert _code(dup) == "duplicate_name"
    for i in range(15):
        bus.register(f"n{i}-agent")
    with pytest.raises(BusError) as many:
        bus.register("extra-agent")
    assert _code(many) == "too_many_agents"


def test_unknown_recipient_lists_registered_names_only() -> None:  # T5
    _, a, _b = _pair()
    with pytest.raises(BusError) as exc_info:
        a.send("ghost-" + MARKER.lower(), "hi")
    text = str(exc_info.value)
    assert _code(exc_info) == "unknown_recipient"
    assert "a-agent" in text and "b-agent" in text and "ghost" not in text and "marker" not in text


def test_sender_is_stamped_by_bus() -> None:  # T6
    _, a, b = _pair()
    assert "sender" not in inspect.signature(Endpoint.send).parameters
    a.send("b-agent", "hi")
    msg = b.receive(1)
    assert msg is not None and msg.sender == a.name == "a-agent"


def test_self_send_rejected() -> None:  # T7
    _, a, _b = _pair()
    with pytest.raises(BusError) as exc_info:
        a.send("a-agent", "me")
    assert _code(exc_info) == "self_send"


def test_message_size_cap_and_text_rules() -> None:  # T8
    bus, a, b = _pair(BusLimits(max_message_bytes=100))
    a.send("b-agent", "x" * 100)  # exactly the cap
    for too_big in ("x" * 101, "é" * 51):  # 51 code points but 102 UTF-8 bytes
        with pytest.raises(BusError) as big:
            a.send("b-agent", too_big)
        assert _code(big) == "too_large"

    class Sub(str):
        pass

    for odd in (Sub("hi"), b"bytes", "\ud800", 5):
        with pytest.raises(BusError) as odd_info:
            a.send("b-agent", odd)  # type: ignore[arg-type]
        assert _code(odd_info) == "not_text"
    assert bus.pending() == 1 and b.receive(0) is not None


def test_reply_rules_and_hop_cap() -> None:  # T9
    _, a, b = _pair()
    first = a.send("b-agent", "start")
    with pytest.raises(BusError) as not_mine:  # a was the sender, not the recipient
        a.send("b-agent", "x", reply_to=first)
    assert _code(not_mine) == "bad_reply"
    with pytest.raises(BusError) as unknown:
        b.send("a-agent", "x", reply_to=999)
    assert _code(unknown) == "bad_reply"
    last, turn = first, b
    other = {"a-agent": b, "b-agent": a}
    for hop in range(1, 9):  # replies 1..8 are fine
        to = "a-agent" if turn is b else "b-agent"
        last = turn.send(to, f"hop {hop}", reply_to=last)
        turn = other[turn.name]
    to = "a-agent" if turn is b else "b-agent"
    with pytest.raises(BusError) as deep:
        turn.send(to, "9th reply", reply_to=last)
    assert _code(deep) == "too_many_hops"


def test_message_limit_halts_ping_pong() -> None:  # T10
    bus, a, b = _pair()
    for _ in range(256):
        a.send("b-agent", "ping")
        assert b.receive(0) is not None
    with pytest.raises(BusError) as exc_info:
        a.send("b-agent", "ping")
    assert _code(exc_info) == "message_limit"
    stats = bus.stats()
    assert stats.limit_hit and stats.sent == 256


def test_broadcast_all_or_nothing() -> None:  # T11
    bus = MessageBus(BusLimits(mailbox_size=1))
    a, b, c = (bus.register(f"{n}-agent") for n in "abc")
    assert a.broadcast("hello") == 2
    assert a.receive(0) is None
    assert b.receive(0) is not None and c.receive(0) is not None
    c.send("b-agent", "fill")  # b's mailbox (size 1) is now full
    with pytest.raises(BusError) as exc_info:
        a.broadcast("again")
    assert _code(exc_info) == "mailbox_full"
    assert c.receive(0) is None  # nothing was delivered to c either


def test_close_unblocks_all_waiters_no_thread_leak() -> None:  # T12
    bus = MessageBus()
    eps = [bus.register(f"w{i}-agent") for i in range(16)]
    baseline = threading.active_count()
    woke: list[str] = []

    def wait(ep: Endpoint) -> None:
        try:
            ep.receive(None)
        except BusClosed:
            woke.append(ep.name)

    threads = [threading.Thread(target=wait, args=(e,)) for e in eps]
    for t in threads:
        t.start()
    time.sleep(0.2)
    start = time.monotonic()
    bus.close()
    for t in threads:
        t.join(2)
    assert time.monotonic() - start < 0.5 and len(woke) == 16
    assert threading.active_count() == baseline and not any(t.is_alive() for t in threads)
    with pytest.raises(BusClosed):
        eps[0].send("w1-agent", "late")
    with pytest.raises(BusClosed):
        bus.register("late-agent")


def test_dead_letters_counted_on_close_and_retire() -> None:  # T13
    bus, a, b = _pair()
    c = bus.register("c-agent")
    a.send("c-agent", "1")
    a.send("c-agent", "2")
    assert bus.retire("c-agent") == 2
    with pytest.raises(BusError) as gone:
        a.send("c-agent", "3")
    assert _code(gone) == "recipient_gone"
    with pytest.raises(BusError) as left:
        c.receive(0)
    assert _code(left) == "recipient_gone"
    a.send("b-agent", "x")
    a.send("b-agent", "y")
    stats = bus.close()
    assert stats.dead_letters == 4 and stats.closed and bus.close().dead_letters == 4
    assert b is not None


def test_receive_ctrl_c_latency() -> None:  # T14
    _, a, _b = _pair()
    fired: list[float] = []

    def interrupt() -> None:
        fired.append(time.monotonic())
        _thread.interrupt_main()

    timer = threading.Timer(0.3, interrupt)
    timer.start()
    caught = None
    try:
        a.receive(None)
    except KeyboardInterrupt:
        caught = time.monotonic()
    timer.join()
    assert caught is not None and caught - fired[0] < 0.25


def test_receive_timeout_returns_none() -> None:
    _, a, _b = _pair()
    start = time.monotonic()
    assert a.receive(0.15) is None
    assert 0.1 <= time.monotonic() - start < 0.5


def test_marker_never_in_errors_logs_or_reprs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    bus, a, b = _pair(BusLimits(max_message_bytes=64, mailbox_size=1))
    seen: list[BaseException] = []
    a.send("b-agent", MARKER)
    msg = b.receive(0)
    assert msg is not None and MARKER not in repr(msg) and MARKER not in str(msg)
    attempts = [
        lambda: a.send("ghost-agent", MARKER),
        lambda: a.send("a-agent", MARKER),
        lambda: a.send("b-agent", MARKER * 10),
        lambda: a.send("b-agent", MARKER, reply_to=77),
        lambda: bus.register(MARKER),
    ]
    a.send("b-agent", "fill")
    attempts.append(lambda: a.send("b-agent", MARKER))  # mailbox_full
    for call in attempts:
        with pytest.raises(BusError) as exc_info:
            call()
        seen.append(exc_info.value)
    for err in seen:
        blob = f"{err!s}|{err!r}|{err.args}"
        assert MARKER not in blob and MARKER.lower() not in blob.lower()
        assert err.__context__ is None and err.__cause__ is None
        assert isinstance(err, GraphError)
    assert MARKER not in caplog.text and MARKER not in repr(bus.stats())


def test_low_fixes_bus() -> None:  # T40 (bus part)
    _, a, b = _pair()
    for attr in ("name", "_name", "sender"):
        try:
            setattr(a, attr, "b-agent")
        except AttributeError:
            pass
    a.send("b-agent", "hi")
    msg = b.receive(0)
    assert msg is not None and msg.sender == "a-agent"
    big = "é" * 10_000_000  # 20 MB if encoded
    tracemalloc.start()
    with pytest.raises(BusError) as exc_info:
        a.send("b-agent", big)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert _code(exc_info) == "too_large" and peak < 1_000_000


def test_bus_ids_and_order_repeat_across_runs() -> None:  # T33 (bus part)
    def run() -> list[tuple[int, str, str]]:
        _bus, a, b = _pair()
        out = []
        for i in range(10):
            a.send("b-agent", f"m{i}")
            b.send("a-agent", f"r{i}")
        while (m := b.receive(0)) is not None:
            out.append((m.id, m.sender, m.content))
        while (m := a.receive(0)) is not None:
            out.append((m.id, m.sender, m.content))
        return out

    first = run()
    assert all(run() == first for _ in range(20))
