"""Slice 10: loopback HTTP server + SSE run stream (synthetic data only)."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import AssistantMessage, Message, ToolCall, ToolSpec
from master_finhub.server.app import SESSION_HEADER, RunServer, make_server
from master_finhub.tools.builtins.echo import EchoTool

FAST = {"ping_interval_s": 0.05, "poll_s": 0.01}


@contextmanager
def running(**kw: Any) -> Iterator[RunServer]:
    kw.setdefault("llm_factory", ScriptedLLM)
    kw.setdefault("tools_factory", lambda: [EchoTool()])
    srv = make_server(**kw)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(5)


def conn(srv: RunServer) -> http.client.HTTPConnection:
    return http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)


def call(
    srv: RunServer, method: str, path: str, body: bytes | None = None, **headers: str
) -> tuple[int, bytes]:
    c = conn(srv)
    try:
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


def auth(srv: RunServer) -> dict[str, str]:
    return {SESSION_HEADER: srv.session_key}


def start_run(srv: RunServer, prompt: str = "echo hi") -> str:
    status, body = call(srv, "POST", "/runs", json.dumps({"prompt": prompt}).encode(), **auth(srv))
    assert status == 202
    return str(json.loads(body)["run_id"])


def parse_stream(raw: bytes) -> list[tuple[str, str]]:
    frames = []
    for block in raw.decode().split("\n\n"):
        if not block.strip():
            continue
        name, data = "message", []
        for line in block.split("\n"):
            field, _, value = line.partition(": ")
            if field == "event":
                name = value
            elif field == "data":
                data.append(value)
        frames.append((name, "\n".join(data)))
    return frames


def test_health_needs_no_key() -> None:
    with running() as srv:
        assert call(srv, "GET", "/health") == (200, b'{"status": "ok"}')


def test_run_streams_ping_then_events() -> None:
    with running() as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        r = c.getresponse()
        assert r.status == 200
        assert r.getheader("Content-Type") == "text/event-stream"
        assert r.getheader("Cache-Control") == "no-cache"
        frames = parse_stream(r.read())
        c.close()
    assert frames[0][0] == "ping"
    names = [n for n, _ in frames]
    assert names.count("message") >= 3  # user, assistant(tool call), tool, assistant
    assert frames[-1] == ("done", '"hi"')
    first_msg = json.loads(frames[1][1])
    assert first_msg == {"role": "user", "content": "echo hi", "tool_calls": []}


def test_missing_or_wrong_key_401() -> None:
    with running() as srv:
        assert call(srv, "POST", "/runs", b"{}")[0] == 401
        assert call(srv, "POST", "/runs", b"{}", **{SESSION_HEADER: "wrong"})[0] == 401
        assert (
            call(srv, "GET", "/runs/x/events", **{SESSION_HEADER: srv.session_key + "x"})[0] == 401
        )


def test_key_compare_is_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    import hmac

    from master_finhub.server import app

    seen: list[tuple[Any, Any]] = []
    real = hmac.compare_digest

    def spy(a: Any, b: Any) -> bool:
        seen.append((a, b))
        return real(a, b)

    monkeypatch.setattr(app.hmac, "compare_digest", spy)
    with running() as srv:
        call(srv, "POST", "/runs", b"{}", **{SESSION_HEADER: "wrong"})
    assert seen, "the session key must be compared with hmac.compare_digest"


def test_bad_host_header_421() -> None:
    with running() as srv:
        for host in ("evil.example.com", "evil.example.com:80", "192.168.1.5:80"):
            status, _ = call(srv, "POST", "/runs", b"{}", Host=host, **auth(srv))
            assert status == 421, host
        assert call(srv, "GET", "/health", Host="evil.example.com")[0] == 200


def test_loopback_host_names_accepted() -> None:
    with running() as srv:
        for host in ("localhost:1", "127.0.0.1", "[::1]:9"):
            body = json.dumps({"prompt": "echo a"}).encode()
            assert call(srv, "POST", "/runs", body, Host=host, **auth(srv))[0] == 202


def test_unknown_run_404_and_unknown_route_404() -> None:
    with running() as srv:
        assert call(srv, "GET", "/runs/nope/events", **auth(srv))[0] == 404
        assert call(srv, "GET", "/nothing", **auth(srv))[0] == 404


def test_bad_bodies_400_and_413() -> None:
    with running() as srv:
        h = auth(srv)
        assert call(srv, "POST", "/runs", b"not json", **h)[0] == 400
        assert call(srv, "POST", "/runs", b'{"prompt": 3}', **h)[0] == 400
        status, body = call(srv, "POST", "/runs", b"x" * (64 * 1024 + 1), **h)
        assert status == 413
        assert b"xxxx" not in body


def test_second_subscriber_409() -> None:
    gate = threading.Event()

    class Slow:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            gate.wait(5)
            return AssistantMessage("late")

    with running(llm_factory=Slow, **FAST) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        first = c.getresponse()  # keep it referenced: dropping it closes the socket
        assert first.status == 200
        assert call(srv, "GET", f"/runs/{rid}/events", **auth(srv))[0] == 409
        gate.set()
        c.close()


def test_refuses_lan_bind() -> None:
    with pytest.raises(ValueError):
        make_server(ScriptedLLM, lambda: [EchoTool()], host="0.0.0.0")


def test_allow_remote_permits_non_loopback_host() -> None:
    srv = make_server(ScriptedLLM, lambda: [EchoTool()], host="0.0.0.0", allow_remote=True)
    srv.server_close()


def test_default_bind_is_loopback() -> None:
    srv = make_server(ScriptedLLM, lambda: [EchoTool()])
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def _lan_ipv4() -> str | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent for UDP connect
        ip = str(s.getsockname()[0])
    except OSError:
        return None
    finally:
        s.close()
    return None if ip.startswith("127.") else ip


def test_loopback_only() -> None:
    lan = _lan_ipv4()
    if lan is None:
        pytest.skip("host has no non-loopback IPv4")
    with running() as srv:
        port = srv.server_address[1]
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        with pytest.raises(OSError):
            socket.create_connection((lan, port), timeout=2).close()


class _RmTool:
    spec = ToolSpec("sh", "run", {"type": "object"})
    ran = False

    def run(self, arguments: dict[str, Any]) -> str:
        _RmTool.ran = True
        return "ran"


class _CallsRm:
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        if messages[-1].role == "tool":
            return AssistantMessage(messages[-1].content)
        return AssistantMessage("", [ToolCall("c", "sh", {"command": "rm -rf /"})])


def test_extra_guard_cannot_weaken() -> None:
    _RmTool.ran = False
    with running(
        llm_factory=_CallsRm, tools_factory=lambda: [_RmTool()], extra_guard=lambda c: None
    ) as srv:
        rid = start_run(srv, "go")
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        frames = parse_stream(c.getresponse().read())
        c.close()
    assert not _RmTool.ran
    assert frames[-1][0] == "done"
    assert frames[-1][1].startswith('"Error:')


def test_extra_guard_can_add_denial() -> None:
    with running(extra_guard=lambda c: "blocked by extra") as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        frames = parse_stream(c.getresponse().read())
        c.close()
    assert frames[-1] == ("done", '"Error: blocked by extra"')


def test_agent_error_event_has_class_name_only() -> None:
    def boom() -> Any:
        raise RuntimeError("secret detail")

    with running(llm_factory=boom) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        raw = c.getresponse().read()
        c.close()
    assert parse_stream(raw)[-1] == ("error", '"RuntimeError"')
    assert b"secret" not in raw


def test_compaction_does_not_drop_or_repeat_events() -> None:
    """A49/N3: events come from messages[-1] per hook call, even if fit() shrinks history."""

    class Shrink:
        def fit(self, messages: list[Message]) -> list[Message]:
            return [Message("user", "summary")] if len(messages) > 1 else messages

    with running(context_factory=Shrink) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        frames = parse_stream(c.getresponse().read())
        c.close()
    msgs = [json.loads(d) for n, d in frames if n == "message"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "assistant"]
    assert msgs[-1]["content"].startswith("ScriptedLLM only understands")
    assert frames[-1][0] == "done"


def test_too_many_running_429() -> None:
    gate = threading.Event()

    class Slow:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            gate.wait(5)
            return AssistantMessage("x")

    with running(llm_factory=Slow) as srv:
        try:
            for _ in range(4):
                start_run(srv)
            body = json.dumps({"prompt": "p"}).encode()
            assert call(srv, "POST", "/runs", body, **auth(srv))[0] == 429
        finally:
            gate.set()


def _wait(pred: Any, secs: float = 5.0) -> bool:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def _handler_threads() -> int:
    return sum(1 for t in threading.enumerate() if "process_request_thread" in t.name)


def test_disconnect_releases_thread_and_subscriber() -> None:
    gate = threading.Event()

    class Slow:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            gate.wait(5)
            return AssistantMessage("x")

    with running(llm_factory=Slow, **FAST) as srv:
        base = _handler_threads()
        rid = start_run(srv)
        raw = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=5)
        req = f"GET /runs/{rid}/events HTTP/1.0\r\nHost: localhost\r\n{SESSION_HEADER}: "
        raw.sendall(f"{req}{srv.session_key}\r\n\r\n".encode())
        assert b"200" in raw.recv(4096)
        assert _handler_threads() > base
        raw.close()  # client vanishes mid-stream
        assert _wait(lambda: _handler_threads() == base), "handler thread leaked"
        assert _wait(lambda: rid not in srv.runs), "subscriber/run entry leaked"
        gate.set()


def test_idle_stream_times_out_and_releases() -> None:
    gate = threading.Event()

    class Slow:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            gate.wait(5)
            return AssistantMessage("x")

    with running(llm_factory=Slow, idle_timeout_s=0.2, **FAST) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        raw = c.getresponse().read()  # server ends the stream itself
        c.close()
        gate.set()
    names = [n for n, _ in parse_stream(raw)]
    assert names[-1] == "ping" and not {"done", "error"} & set(names)


def test_shutdown_does_not_hang_with_open_stream() -> None:
    gate = threading.Event()

    class Slow:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            gate.wait(5)
            return AssistantMessage("x")

    started = time.monotonic()
    with running(llm_factory=Slow, **FAST) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        resp = c.getresponse()
        assert resp.status == 200
    gate.set()
    c.close()
    assert time.monotonic() - started < 4
