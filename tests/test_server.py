"""Slice 10: loopback HTTP server + SSE run stream (synthetic data only)."""

from __future__ import annotations

import http.client
import json
import socket
import struct
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

    with running(llm_factory=boom, idle_timeout_s=1.0, **FAST) as srv:
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


# --------------------------------------------------------------- fix round (QA advisories)
def _raw(srv: RunServer, request: bytes, *, read: bool = True) -> bytes:
    s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=5)
    try:
        s.sendall(request)
        if not read:
            return b""
        out = b""
        while chunk := s.recv(4096):
            out += chunk
        return out
    finally:
        s.close()


def _host_status(srv: RunServer, host: bytes) -> int:
    key = f"{SESSION_HEADER}: {srv.session_key}".encode()
    req = (
        b"GET /nothing HTTP/1.1\r\nHost: " + host + b"\r\n" + key + b"\r\nConnection: close\r\n\r\n"
    )
    return int(_raw(srv, req).split(b" ", 2)[1])


@pytest.mark.parametrize(
    "host",
    [
        b"evil.com@localhost",
        b"evil.com\\@localhost",
        b"localhost@evil.com",
        b"localhost:80@evil.com",
        b"user:pw@localhost",
        b"local host",
        b"localhost\x01",
        b"local\thost",
        b"localhost:",
        b"localhost:abc",
        b"localhost:99999",
        b"localhost:1:2",
        b"localhost:-1",
        b":80",
        b"::1",
        b"[::1]x",
        b"[::1]x80",
        b"[::1",
        b"[::1]:",
        b"[::1]:abc",
        b"[]",
        b"localhost.",
        b"127.1",
        b"0.0.0.0",
        b"[::ffff:127.0.0.1]",
        b"evil.com#@localhost",
    ],
)
def test_strict_host_parse_refuses_421(host: bytes) -> None:
    with running() as srv:
        assert _host_status(srv, host) == 421, host


@pytest.mark.parametrize(
    "host", [b"localhost", b"LOCALHOST", b"LocalHost:80", b"127.0.0.1:8080", b"[::1]", b"[::1]:9"]
)
def test_strict_host_parse_keeps_loopback_names(host: bytes) -> None:
    with running() as srv:
        assert _host_status(srv, host) == 404, host  # past the Host check, unknown route


def test_duplicate_or_missing_or_empty_host_421() -> None:
    with running() as srv:
        key = f"{SESSION_HEADER}: {srv.session_key}\r\n".encode()
        for hosts in (b"Host: localhost\r\nHost: evil.com\r\n", b"Host: \r\n", b""):
            raw = _raw(
                srv, b"GET /nothing HTTP/1.1\r\n" + hosts + key + b"Connection: close\r\n\r\n"
            )
            assert raw.split(b" ", 2)[1] == b"421", hosts


def test_slow_body_handler_is_released_by_read_timeout() -> None:
    with running(read_timeout_s=0.3) as srv:
        base = _handler_threads()
        s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=5)
        head = f"POST /runs HTTP/1.1\r\nHost: localhost\r\n{SESSION_HEADER}: {srv.session_key}\r\n"
        s.sendall(f"{head}Content-Length: 100\r\n\r\nabc".encode())
        assert _wait(lambda: _handler_threads() > base), "handler never parked"
        assert _wait(lambda: _handler_threads() == base, 3), "short body parked a thread forever"
        s.close()


def test_idle_preauth_connection_is_released_by_read_timeout() -> None:
    with running(read_timeout_s=0.3) as srv:
        base = _handler_threads()
        s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=5)
        assert _wait(lambda: _handler_threads() > base), "handler never parked"
        assert _wait(lambda: _handler_threads() == base, 3), "idle connection parked a thread"
        assert s.recv(1) == b""  # server closed its side
        s.close()


def test_read_timeout_does_not_cut_an_idle_sse_stream() -> None:
    gate = threading.Event()

    class Slow:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            gate.wait(5)
            return AssistantMessage("late")

    # no pings inside the window: the stream is silent for 3x the read timeout
    with running(
        llm_factory=Slow, read_timeout_s=0.2, idle_timeout_s=5.0, ping_interval_s=5.0, poll_s=0.01
    ) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        resp = c.getresponse()
        assert resp.status == 200
        time.sleep(0.6)
        gate.set()
        frames = parse_stream(resp.read())
        c.close()
    assert frames[-1] == ("done", '"late"')


def _drop_before_reply(srv: RunServer, request: bytes) -> None:
    s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=5)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))  # close sends RST
    s.sendall(request)
    s.close()


def test_client_drop_before_reply_is_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    from master_finhub.server import app

    real = app._Handler._allowed

    def slow_allowed(self: Any) -> bool:
        time.sleep(0.3)  # let the RST land before the 401 / 413 is written
        return bool(real(self))

    monkeypatch.setattr(app._Handler, "_allowed", slow_allowed)
    with running() as srv:
        errors: list[object] = []
        srv.handle_error = lambda *a: errors.append(a)  # type: ignore[method-assign]
        base = _handler_threads()
        _drop_before_reply(
            srv, b"POST /runs HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}"
        )
        big = b"x" * (64 * 1024 + 1)
        head = f"POST /runs HTTP/1.1\r\nHost: localhost\r\n{SESSION_HEADER}: {srv.session_key}\r\n"
        _drop_before_reply(srv, f"{head}Content-Length: {len(big)}\r\n\r\n".encode() + big)
        assert _wait(lambda: _handler_threads() == base, 5)
        time.sleep(0.2)
        assert errors == [], "a dropped client must not surface a traceback"


def test_run_thread_always_queues_a_terminal_event_on_baseexception() -> None:
    class Fatal(BaseException):
        pass

    def boom() -> Any:
        raise Fatal("secret detail")

    # idle timeout is short so a missing terminal event fails in about a second, not 300 s
    with running(llm_factory=boom, idle_timeout_s=1.0, **FAST) as srv:
        rid = start_run(srv)
        c = conn(srv)
        c.request("GET", f"/runs/{rid}/events", headers=auth(srv))
        raw = c.getresponse().read()
        c.close()
        assert _wait(lambda: srv._running == 0), "running count leaked"
    assert parse_stream(raw)[-1] == ("error", '"Fatal"')
    assert b"secret" not in raw


# ----------------------------------------------------------------------- main()
def _patched_main(monkeypatch: pytest.MonkeyPatch, serve: Any) -> list[dict[str, Any]]:
    from master_finhub.server import app

    made: list[dict[str, Any]] = []
    real = app.make_server

    def spy(llm_factory: Any, tools_factory: Any, **kw: Any) -> RunServer:
        srv = real(llm_factory, tools_factory, **kw)
        made.append({"factory": llm_factory, "srv": srv, **kw})
        return srv

    monkeypatch.setattr(app, "make_server", spy)
    monkeypatch.setattr(app.RunServer, "serve_forever", serve)
    return made


def test_main_default_uses_scripted_llm_and_prints_key_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from master_finhub.server import app

    made = _patched_main(monkeypatch, lambda self, *a, **k: None)
    assert app.main([]) == 0
    srv = made[0]["srv"]
    assert made[0]["factory"] is ScriptedLLM and "host" not in made[0]
    err = capsys.readouterr().err
    assert err.count(srv.session_key) == 1 and "http://127.0.0.1:" in err
    assert srv.socket.fileno() == -1, "main must close the server socket"


def test_main_profile_branch_builds_llm_through_router(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from master_finhub.runtime import router
    from master_finhub.server import app

    built: list[str] = []
    monkeypatch.setattr(router.Router, "build_llm", lambda self, profile: built.append(profile))
    made = _patched_main(monkeypatch, lambda self, *a, **k: None)
    assert app.main(["--profile", "fast"]) == 0
    assert built == [], "the model is built per run, never at startup"
    made[0]["factory"]()
    assert built == ["fast"]
    capsys.readouterr()


def test_main_ctrl_c_exits_zero_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    from master_finhub.server import app

    def interrupted(self: Any, *a: Any, **k: Any) -> None:
        raise KeyboardInterrupt

    made = _patched_main(monkeypatch, interrupted)
    assert app.main(["--port", "0"]) == 0
    assert made[0]["srv"].socket.fileno() == -1


def test_main_bad_arguments_exit_2() -> None:
    from master_finhub.server import app

    with pytest.raises(SystemExit) as e:
        app.main(["--port", "not-a-number"])
    assert e.value.code == 2
