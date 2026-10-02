"""Slice 8 proof tests: process output stream (synthetic child processes only)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time

import pytest

from master_finhub.sandbox import stream as stream_mod
from master_finhub.sandbox.stream import (
    Chunk,
    TailBuffer,
    collect,
    scrubbed_env,
    stream_process,
)

PY = sys.executable


def _gone(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def _reader_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith("mf-stream-reader")]


def test_scrubbed_env_drops_secret_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "a")
    monkeypatch.setenv("db_password", "b")
    monkeypatch.setenv("GITHUB_TOKEN", "c")
    monkeypatch.setenv("MY_SECRET", "d")
    env = scrubbed_env()
    for name in ("API_KEY", "db_password", "GITHUB_TOKEN", "MY_SECRET"):
        assert name not in env
    assert "PATH" in env
    assert scrubbed_env({"API_KEY": "x"})["API_KEY"] == "x"


def test_tail_buffer_keeps_tail() -> None:
    buf = TailBuffer(100)
    for ch in (b"a", b"b", b"c"):
        buf.push(ch * 40)
    assert buf.text() == ("a" * 40 + "b" * 40 + "c" * 40)[-100:]
    assert buf.truncated is True
    small = TailBuffer(100)
    small.push(b"hi")
    assert small.text() == "hi" and small.truncated is False


def test_stream_process_orders_and_exits() -> None:
    code = "print('a'); import sys; print('b', file=sys.stderr)"
    chunks = list(stream_process([PY, "-c", code], env=scrubbed_env(), timeout_s=20))
    assert [c.seq for c in chunks] == list(range(len(chunks)))
    assert any(c.kind == "stdout" and "a" in c.data for c in chunks)
    assert any(c.kind == "stderr" and "b" in c.data for c in chunks)
    assert chunks[-1] == Chunk(len(chunks) - 1, "exit", "0")
    res = collect(chunks)
    assert res.stdout == "a\n" and res.stderr == "b\n" and res.exit_code == 0


def test_stream_process_timeout_kills_group() -> None:
    calls: list[int] = []
    pids: list[int] = []
    real_popen = subprocess.Popen

    def spy(*a: object, **k: object) -> subprocess.Popen[bytes]:
        p = real_popen(*a, **k)  # type: ignore[call-overload]
        pids.append(p.pid)
        return p  # type: ignore[no-any-return]

    mp = pytest.MonkeyPatch()
    mp.setattr(stream_mod.subprocess, "Popen", spy)
    try:
        chunks = list(
            stream_process(
                [PY, "-c", "import time; time.sleep(30)"],
                env=scrubbed_env(),
                timeout_s=1,
                on_timeout=lambda: calls.append(1),
            )
        )
    finally:
        mp.undo()
    assert chunks[-1].kind == "timeout"
    assert calls == [1]
    res = collect(chunks)
    assert res.timed_out and res.exit_code is None
    time.sleep(0.2)
    assert _gone(pids[0])


def test_abandoned_stream_releases_readers() -> None:
    # 600 x 64 KiB >> QUEUE_MAX (256): the queue really fills and readers block in put().
    assert stream_mod.QUEUE_MAX < 600
    code = (
        "import sys\nfor _ in range(600):\n"
        "    sys.stdout.write('x'*65536)\n    sys.stdout.flush()\n"
    )
    procs: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    def spy(*a: object, **k: object) -> subprocess.Popen[bytes]:
        p = real_popen(*a, **k)  # type: ignore[call-overload]
        procs.append(p)
        return p  # type: ignore[no-any-return]

    mp = pytest.MonkeyPatch()
    mp.setattr(stream_mod.subprocess, "Popen", spy)
    calls: list[int] = []
    try:
        gen = stream_process(
            [PY, "-c", code], env=scrubbed_env(), timeout_s=30, on_timeout=lambda: calls.append(1)
        )
        next(gen)
        time.sleep(1.0)  # let the child fill the bounded queue so a reader blocks on put
        gen.close()
    finally:
        mp.undo()
    deadline = time.monotonic() + 5
    while _reader_threads() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _reader_threads() == []
    assert _gone(procs[0].pid)
    assert calls == [1]
    assert procs[0].stdout is not None and procs[0].stdout.closed
    assert procs[0].stderr is not None and procs[0].stderr.closed


def test_abandoned_stream_with_escaped_child_does_not_hang() -> None:
    # A grandchild leaves the process group (setsid) and keeps the pipe open for 60 s.
    # Closing the pipes before the join (N7 regression) would block until it exits.
    code = (
        "import subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],"
        " start_new_session=True)\n"
        "print(g.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    gen = stream_process([PY, "-c", code], env=scrubbed_env(), timeout_s=120)
    first = next(gen)
    assert first.kind == "stdout"
    grandchild = int(first.data.strip())
    try:
        t0 = time.monotonic()
        gen.close()
        assert time.monotonic() - t0 < 10  # 5 s proc/join bound; never waits for the grandchild
        for t in _reader_threads():
            assert t.daemon
    finally:
        try:
            os.kill(grandchild, signal.SIGKILL)
        except ProcessLookupError:
            pass
