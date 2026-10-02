"""Loopback-only HTTP server: start an agent run, stream its events over SSE.

Stdlib only. Routes: GET /health, POST /runs, GET /runs/<id>/events.
"""

from __future__ import annotations

import argparse
import hmac
import json
import queue
import secrets
import sys
import threading
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Final

from master_finhub.orchestration.modes.subagent import _both
from master_finhub.runtime.context import ContextManager
from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import (
    DEFAULT_MAX_STEPS,
    LLM,
    AgentLoop,
    ContextPolicy,
    LoopSnapshot,
    Tool,
    ToolGuard,
)
from master_finhub.server.sse import (
    IDLE_TIMEOUT_S,
    PING_INTERVAL_S,
    POLL_S,
    EventName,
    SseEvent,
    encode,
    event_stream,
)
from master_finhub.tools.builtins.echo import EchoTool
from master_finhub.tools.safety import guard_tool_call

SESSION_HEADER: Final = "X-Session-API-Key"
MAX_BODY_BYTES: Final = 64 * 1024
MAX_RUNNING: Final = 4
MAX_RETAINED: Final = 32
LOOPBACK: Final = frozenset({"127.0.0.1", "::1", "localhost"})
READ_TIMEOUT_S: Final = 30.0  # per-connection socket timeout; SSE only writes, so it is unaffected

LLMFactory = Callable[[], LLM]


class _Run:
    def __init__(self) -> None:
        self.events: queue.Queue[SseEvent] = queue.Queue()  # bounded by max_steps in practice
        self.attached = False
        self.finished = False


class RunServer(ThreadingHTTPServer):
    daemon_threads = True  # a stuck client must never block shutdown

    def __init__(
        self,
        address: tuple[str, int],
        *,
        llm_factory: LLMFactory,
        tools_factory: Callable[[], list[Tool]],
        context_factory: Callable[[], ContextPolicy],
        allow_remote: bool,
        guard: ToolGuard,
        max_steps: int,
        timing: tuple[float, float, float],
        read_timeout_s: float,
    ) -> None:
        super().__init__(address, _Handler)
        self.session_key = secrets.token_urlsafe(32)
        self.runs: dict[str, _Run] = {}
        self.closing = threading.Event()
        self.llm_factory = llm_factory
        self.tools_factory = tools_factory
        self.context_factory = context_factory
        self.allow_remote = allow_remote
        self.guard = guard
        self.max_steps = max_steps
        self.timing = timing
        self.read_timeout_s = read_timeout_s
        self._lock = threading.Lock()
        self._running = 0

    def shutdown(self) -> None:
        self.closing.set()  # open streams end at their next frame
        super().shutdown()

    # ------------------------------------------------------------------ run table
    def start_run(self, prompt: str) -> str | None:
        """Register and start a run; None when MAX_RUNNING loops are already live."""
        with self._lock:
            if self._running >= MAX_RUNNING:
                return None
            self._running += 1
            run_id = uuid.uuid4().hex
            run = self.runs[run_id] = _Run()
            for old in [k for k, r in self.runs.items() if r.finished]:
                if len(self.runs) <= MAX_RETAINED:
                    break
                del self.runs[old]
        threading.Thread(target=self._work, args=(run, prompt), daemon=True).start()
        return run_id

    def claim(self, run_id: str) -> _Run | int:
        """Attach the single subscriber: the run, or 404 / 409."""
        with self._lock:
            run = self.runs.get(run_id)
            if run is None:
                return 404
            if run.attached:
                return 409
            run.attached = True
            return run

    def release(self, run_id: str) -> None:
        with self._lock:
            self.runs.pop(run_id, None)

    def _work(self, run: _Run, prompt: str) -> None:
        def hook(snapshot: LoopSnapshot) -> None:
            m = snapshot.messages[-1]  # one call per appended message; never a length diff
            payload = {
                "role": m.role,
                "content": m.content,
                "tool_calls": [c.name for c in m.tool_calls],
            }
            run.events.put(SseEvent(EventName.MESSAGE, json.dumps(payload)))

        try:
            loop = AgentLoop(
                self.llm_factory(),
                self.tools_factory(),
                self.max_steps,
                context=self.context_factory(),
                guard=self.guard,
                checkpoint=hook,
            )
            run.events.put(SseEvent(EventName.DONE, json.dumps(loop.run(prompt))))
        except BaseException as exc:  # noqa: BLE001 - always end the stream; class name only
            # Not re-raised: nothing above a worker thread can use it, and the default thread
            # hook would print the exception text (which may hold a secret) to stderr.
            run.events.put(SseEvent(EventName.ERROR, json.dumps(type(exc).__name__)))
        finally:
            with self._lock:
                self._running -= 1
                run.finished = True


def _hostname(host_header: str | None) -> str | None:
    """Strict `host[:port]` or `[v6][:port]`; None for anything else (userinfo, junk, bad port)."""
    if not host_header or any(not 0x21 <= ord(c) <= 0x7E or c in "\\@" for c in host_header):
        return None
    if host_header.startswith("["):
        name, close, rest = host_header[1:].partition("]")
        if not close or (rest and not rest.startswith(":")):
            return None
        port = rest[1:] if rest else None
    else:
        name, colon, tail = host_header.partition(":")
        port = tail if colon else None
    if not name or (port is not None and not (port.isdigit() and int(port) <= 65535)):
        return None
    return name.lower()


class _Handler(BaseHTTPRequestHandler):
    server: RunServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(self.server.read_timeout_s)  # bounds every read; SSE only writes

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client left before a reply or mid-read; nothing to log (no key, no prompt)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # request lines can carry run ids; keep stderr quiet

    # ------------------------------------------------------------------ helpers
    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _fail(self, status: int, what: str, why: str, fix: str) -> None:
        self._send(status, {"error": f"{what} {why} {fix}"})

    def _allowed(self) -> bool:
        hosts = self.headers.get_all("Host") or []
        one = hosts[0] if len(hosts) == 1 else None  # duplicate Host headers are ambiguous: refuse
        if not self.server.allow_remote and _hostname(one) not in LOOPBACK:
            self._fail(
                421,
                "Request refused: the Host header is not a loopback name.",
                "This server only answers requests addressed to localhost.",
                "Connect through 127.0.0.1 or localhost.",
            )
            return False
        supplied = self.headers.get(SESSION_HEADER, "")
        if not hmac.compare_digest(supplied.encode(), self.server.session_key.encode()):
            self._fail(
                401,
                "Request refused: the session key is missing or wrong.",
                "Every route except /health needs it.",
                f"Send the key printed at startup in the {SESSION_HEADER} header.",
            )
            return False
        return True

    # ------------------------------------------------------------------ routes
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
            return
        parts = self.path.split("/")
        is_events = len(parts) == 4 and parts[:2] == ["", "runs"] and parts[3] == "events"
        if not self._allowed():
            return
        if not is_events:
            self._send(404, {"error": "Not found."})
            return
        claimed = self.server.claim(parts[2])
        if isinstance(claimed, int):
            msg = "Unknown run." if claimed == 404 else "A stream is already attached."
            self._send(claimed, {"error": msg})
            return
        self._stream(parts[2], claimed)

    def do_POST(self) -> None:
        if self.path != "/runs" or not self._allowed():
            if self.path != "/runs":
                self._send(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 0:
            self._fail(
                400,
                "Bad request: no valid Content-Length.",
                "The body size is unknown.",
                "Send a JSON body with Content-Length.",
            )
            return
        if length > MAX_BODY_BYTES:
            self.rfile.read(min(length, 2 * MAX_BODY_BYTES))  # bounded drain so the reply lands
            self._fail(
                413,
                f"Body too large: over {MAX_BODY_BYTES} bytes.",
                "Prompts are capped.",
                "Send a shorter prompt.",
            )
            return
        try:
            prompt = json.loads(self.rfile.read(length))["prompt"]
        except (ValueError, KeyError, TypeError):
            prompt = None
        if not isinstance(prompt, str) or not prompt:
            self._fail(
                400,
                "Bad request: body must be JSON with a non-empty string prompt.",
                "It could not be read that way.",
                'Send {"prompt": "echo hi"}.',
            )
            return
        run_id = self.server.start_run(prompt)
        if run_id is None:
            self._fail(
                429,
                "Too many runs: the limit of running agents is reached.",
                "Each run holds a thread.",
                "Wait for a run to finish, then retry.",
            )
            return
        self._send(202, {"run_id": run_id})

    def _stream(self, run_id: str, run: _Run) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for n, event in enumerate(
                event_stream(
                    run.events,
                    idle_timeout_s=self.server.timing[0],
                    ping_interval_s=self.server.timing[1],
                    poll_s=self.server.timing[2],
                )
            ):
                self.wfile.write(encode(event, n))
                self.wfile.flush()
                if self.server.closing.is_set():
                    break
        except OSError:  # client went away: BrokenPipe / ConnectionReset
            pass
        finally:
            self.server.release(run_id)  # frees the subscriber slot and the queue
        self.close_connection = True


def make_server(
    llm_factory: LLMFactory,
    tools_factory: Callable[[], list[Tool]],
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    allow_remote: bool = False,
    extra_guard: ToolGuard | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    context_factory: Callable[[], ContextPolicy] = ContextManager,
    idle_timeout_s: float = IDLE_TIMEOUT_S,
    ping_interval_s: float = PING_INTERVAL_S,
    poll_s: float = POLL_S,
    read_timeout_s: float = READ_TIMEOUT_S,
) -> RunServer:
    if host not in LOOPBACK and not allow_remote:
        raise ValueError(
            f'Refusing to bind "{host}": it would expose the agent to the network. '
            "Runs execute tools on this machine. "
            "Bind 127.0.0.1, or pass allow_remote=True if you mean it."
        )
    guard = guard_tool_call if extra_guard is None else _both(guard_tool_call, extra_guard)
    timing = (idle_timeout_s, ping_interval_s, poll_s)
    return RunServer(
        (host, port),
        llm_factory=llm_factory,
        tools_factory=tools_factory,
        context_factory=context_factory,
        allow_remote=allow_remote,
        guard=guard,
        max_steps=max_steps,
        timing=timing,
        read_timeout_s=read_timeout_s,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="master_finhub.server.app")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--profile", default=None, help="Model profile; omit for the scripted LLM.")
    args = parser.parse_args(argv)
    factory: LLMFactory = ScriptedLLM
    if args.profile is not None:
        from master_finhub.runtime.router import Router

        profile = str(args.profile)
        factory = lambda: Router().build_llm(profile)
    server = make_server(factory, lambda: [EchoTool()], port=args.port)
    print(f"serving on http://127.0.0.1:{server.server_address[1]}", file=sys.stderr)
    print(f"{SESSION_HEADER}: {server.session_key}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
