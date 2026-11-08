"""Stdio MCP client: newline-delimited JSON-RPC 2.0 over a child process, stdlib only.

Pattern: reader/stderr threads, id -> queue routing, deadlines and fail-all-waiters on EOF
(deepseek python sdk client.py, adapted); handshake order and reset-in-finally (dify, pattern only,
written fresh); pagination, public names and isError mapping (deepseek mcp-client, idea ported).
Never uses a shell; the child gets ``scrubbed_env`` plus the server's explicit env.

The stdout reader is bounded: it holds at most ``MAX_LINE_CHARS + 1`` *characters* per line (the
stream is text-mode UTF-8, so the raw byte ceiling is a few times larger). Requests the server sends
to us get ``-32601`` (we advertise no capabilities); more than ``MAX_SERVER_REQUESTS`` per session
closes it so a hostile server cannot make the reader thread write forever.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import queue
import re
import shlex
import stat
import subprocess
import threading
import time
from collections import deque
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Self

from master_finhub.runtime.loop import ToolSpec
from master_finhub.sandbox.stream import _kill_group, scrubbed_env
from master_finhub.tools.safety import check_command
from master_finhub.tools.secret_scan import Span, apply_spans, merge_spans, secret_spans

PROTOCOL_VERSION: Final = "2025-06-18"
SUPPORTED_VERSIONS: Final = frozenset({"2025-06-18", "2025-03-26", "2024-11-05"})
CLIENT_NAME: Final = "master-finhub"
CLIENT_VERSION: Final = "0.1.0"  # keep in step with pyproject.toml
DEFAULT_CALL_TIMEOUT_S: Final = 30.0
MAX_TOOL_PAGES: Final = 20
MAX_LINE_CHARS: Final = 4_000_000  # readline(MAX_LINE_CHARS + 1); a longer line closes the session
MAX_SERVER_REQUESTS: Final = 64
MAX_STDERR_LINE: Final = 4096
STDERR_LINES: Final = 200
STDIN_CLOSE_S: Final = 2.0
TERMINATE_WAIT_S: Final = 5.0
NAME_RE: Final = re.compile(r"(?!.*__)[a-z0-9_-]{1,32}")  # no "__": it joins server and tool
MAX_DESCRIPTION_CHARS: Final = 2_000  # per tool; the catalogue is sent to the model on every turn
MAX_SCHEMA_CHARS: Final = 16_000  # serialized inputSchema per tool
MAX_TOOLS: Final = 500
MAX_TOOL_NAME_CHARS: Final = 128  # a longer or non-printable tool name is refused
MAX_CATALOGUE_CHARS: Final = 400_000  # descriptions + serialized schemas of one server, together
SERVER_REPLY_TIMEOUT_S: Final = 5.0  # reply to a server-initiated request; expiry kills the child
SHOWN_NAME_CHARS: Final = 80  # most of a server-supplied name shown in any message
MAX_RPC_ID_CHARS: Final = 128
MAX_CURSOR_CHARS: Final = 4096  # a longer nextCursor is refused
SPEC_TIMEOUT_MARGIN_S: Final = 5.0
TRUNCATED_MARK: Final = "...[truncated]"
PUBLIC_MAX: Final = 64
SECRET_SHAPES: Final = re.compile(
    r"Bearer\s+[A-Za-z0-9._~+/=-]+"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"
    r"|(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"
)


class McpError(RuntimeError):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class McpClosed(McpError):
    """Server exited, stdout closed, or the session was shut down; every waiter gets this."""


class McpToolError(McpError):
    """Tool returned isError: true."""


@dataclass(frozen=True)
class StdioServer:
    name: str
    command: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: str | None = None
    call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S
    allowed_tools: frozenset[str] | None = None
    blocked_tools: frozenset[str] = frozenset()
    max_catalogue_chars: int = MAX_CATALOGUE_CHARS

    def __post_init__(self) -> None:
        if not NAME_RE.fullmatch(self.name):
            raise ValueError("server name must match [a-z0-9_-]{1,32} and not contain '__'")


@dataclass(frozen=True)
class McpToolInfo:
    name: str
    public_name: str
    description: str
    input_schema: dict[str, Any]
    # annotations.readOnlyHint is True; a tool with no hint counts as a write tool, as the MCP spec does
    read_only: bool = False
    # hash of description, inputSchema, title, outputSchema and annotations as sent
    digest: str = ""


@dataclass(frozen=True)
class McpResult:
    text: str
    is_error: bool


def public_tool_name(server: str, tool: str) -> str:
    """Always ends in a digest of (server, tool), so two different pairs never share a name."""
    clean = re.sub(r"[^A-Za-z0-9_-]", "_", f"mcp__{server}__{tool}")
    digest = hashlib.sha256(f"{server}\0{tool}".encode()).hexdigest()[:32]  # 128 bits
    return f"{clean[: PUBLIC_MAX - 33]}_{digest}"


def tool_digest(
    description: str,
    schema: Any,
    *,
    title: Any = None,
    output_schema: Any = None,
    annotations: Any = None,
) -> str:
    """Hash of everything the server says about a tool, over the untruncated values."""
    blob = json.dumps(
        [description, schema, title, output_schema, annotations], sort_keys=True, default=str
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _short(text: str, limit: int = SHOWN_NAME_CHARS) -> str:
    """repr of a server-supplied string, cut to ``limit`` characters with an ellipsis."""
    shown = repr(text)
    return shown if len(shown) <= limit else shown[: limit - 1] + "\u2026"


def redact(text: str, secrets: Iterable[str], *, mcp_shapes: bool = True) -> str:
    """Known values, SECRET_SHAPES and the secret_scan table, all matched on the original text."""
    spans: list[Span] = []
    for secret in sorted({s for s in secrets if len(s) >= 4}, key=len, reverse=True):
        spans += ((m.start(), m.end(), "[REDACTED]") for m in re.finditer(re.escape(secret), text))
    if mcp_shapes:
        spans += ((m.start(), m.end(), "[REDACTED]") for m in SECRET_SHAPES.finditer(text))
    spans += ((s, e, f"[REDACTED:{rule}]") for s, e, rule in secret_spans(text))
    return apply_spans(text, merge_spans(spans))


class McpClient:
    def __init__(self, server: StdioServer) -> None:
        self._server = server
        self._proc: subprocess.Popen[str] | None = None
        self._write_lock = threading.Lock()
        self._state = threading.Lock()  # guards _pending, _next_id, _dead
        self._pending: dict[int, queue.Queue[dict[str, Any] | McpClosed]] = {}
        self._next_id = 0
        self._dead: McpClosed | None = None
        self._initialized = False
        self._stderr: deque[str] = deque(maxlen=STDERR_LINES)
        self._threads: list[threading.Thread] = []
        self._server_requests = 0

    def __enter__(self) -> Self:
        try:
            self.start()
            self.initialize()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(redact(x, self._secrets()) for x in self._stderr)

    def _secrets(self) -> list[str]:
        return list(self._server.env.values())

    def start(self) -> None:
        if not self._server.command:
            raise McpError("empty MCP server command")
        # operator-written launch argv may name credential files (e.g. --kubeconfig ~/.kube/config)
        denial = check_command(shlex.join(self._server.command), sensitive_paths=False)
        if denial is not None:
            raise McpError(f"MCP server '{self._server.name}' launch command denied: {denial}")
        try:
            proc = subprocess.Popen(
                list(self._server.command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=scrubbed_env(self._server.env),
                cwd=self._server.cwd,
                start_new_session=True,  # own process group: close() kills grandchildren too
            )
        except OSError:
            raise McpError(f"could not start MCP server '{self._server.name}'") from None
        self._proc = proc
        for target in (self._read_stdout, self._read_stderr):
            t = threading.Thread(target=target, args=(proc,), daemon=True)
            t.start()
            self._threads.append(t)

    # -- reader side -------------------------------------------------------------------------

    def _fail(self, message: str) -> None:
        """Mark the session dead (first reason wins) and release every waiter."""
        text = redact(message, self._secrets())
        tail = self.stderr_tail[-5:]
        if tail:
            text += " | stderr: " + " / ".join(tail)
        with self._state:
            if self._dead is None:
                self._dead = McpClosed(text)
            dead = self._dead
            waiters = list(self._pending.values())
            self._pending.clear()
        for q in waiters:
            q.put(dead)

    def _read_stdout(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        try:
            while True:
                line = proc.stdout.readline(MAX_LINE_CHARS + 1)
                if line == "":
                    self._join_stderr()
                    self._fail("MCP server closed stdout")
                    return
                if len(line) > MAX_LINE_CHARS and not line.endswith("\n"):
                    self._fail("server line too long")
                    _kill_group(proc)  # it may be blocked writing the rest; do not wait for it
                    return
                if not self._dispatch(line, proc):
                    return
        except Exception as exc:  # noqa: BLE001 - reader crash must never leave waiters hanging
            self._fail(f"MCP reader failed: {type(exc).__name__}")
            _kill_group(proc)  # RecursionError included: nobody reads its stdout any more

    def _dispatch(self, line: str, proc: subprocess.Popen[str]) -> bool:
        try:
            msg = json.loads(line)
        except ValueError:
            return True
        if not isinstance(msg, dict):
            return True
        if "method" in msg:
            if "id" not in msg:
                return True  # notification: ignored
            self._server_requests += 1
            if self._server_requests > MAX_SERVER_REQUESTS:
                self._fail("too many server requests")
                _kill_group(proc)
                return False
            req_id = msg["id"]
            if isinstance(req_id, bool) or not (
                isinstance(req_id, int)
                or (isinstance(req_id, str) and len(req_id) <= MAX_RPC_ID_CHARS)
            ):
                return True  # never echo an id we did not bound
            err = {"code": -32601, "message": "Method not found"}
            try:
                self._send(
                    {"jsonrpc": "2.0", "id": req_id, "error": err},
                    timeout=SERVER_REPLY_TIMEOUT_S,
                )
            except (McpClosed, TimeoutError) as exc:
                self._fail(str(exc))
                return False
            return True
        msg_id = msg.get("id")
        if isinstance(msg_id, int) and not isinstance(msg_id, bool):
            with self._state:
                waiter = self._pending.pop(msg_id, None)
            if waiter is not None:
                waiter.put(msg)
        return True

    def _read_stderr(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stderr is not None
        try:
            while True:
                line = proc.stderr.readline(MAX_STDERR_LINE)
                if line == "":
                    return
                self._stderr.append(line.rstrip("\n"))
        except (OSError, ValueError):
            return

    def _join_stderr(self) -> None:
        if len(self._threads) > 1:
            self._threads[1].join(0.5)

    # -- writer side -------------------------------------------------------------------------

    def _send(self, obj: dict[str, Any], timeout: float | None = None) -> None:
        """Write one message. With ``timeout`` the write runs on a helper thread joined with the
        deadline; a server that stops reading is killed and TimeoutError is raised."""
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise McpClosed("MCP server not running")
        stdin = proc.stdin
        data = json.dumps(obj) + "\n"
        failed: list[BaseException] = []

        def write() -> None:
            try:
                with self._write_lock:
                    stdin.write(data)
                    stdin.flush()
            except (OSError, ValueError) as exc:
                failed.append(exc)

        if timeout is None:
            write()
        else:
            t = threading.Thread(target=write, daemon=True)
            t.start()
            t.join(timeout)
            if t.is_alive():
                self._fail("MCP write timed out")
                _kill_group(proc)  # unblocks the pending write
                raise TimeoutError(f"write to MCP server timed out after {timeout}s")
        if failed:
            raise McpClosed("could not write to MCP server")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg, timeout=self._server.call_timeout_s)

    def request(
        self, method: str, params: dict[str, Any] | None = None, timeout_s: float | None = None
    ) -> dict[str, Any]:
        timeout = self._server.call_timeout_s if timeout_s is None else timeout_s
        waiter: queue.Queue[dict[str, Any] | McpClosed] = queue.Queue(maxsize=1)
        with self._state:
            if self._dead is not None:
                raise self._dead
            self._next_id += 1
            req_id = self._next_id
            self._pending[req_id] = waiter
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        deadline = time.monotonic() + timeout  # one deadline for the write and the wait
        try:
            self._send(msg, timeout=timeout)
            reply = waiter.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            raise TimeoutError(f"MCP request '{method}' timed out after {timeout}s") from None
        except McpClosed:
            self._fail("could not write to MCP server")
            raise self._dead or McpClosed("MCP session closed") from None
        finally:
            with self._state:
                self._pending.pop(req_id, None)
        if isinstance(reply, McpClosed):
            raise reply
        error = reply.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = redact(str(error.get("message", "MCP error")), self._secrets())
            raise McpError(message, code if isinstance(code, int) else None)
        result = reply.get("result")
        return result if isinstance(result, dict) else {}

    # -- protocol ----------------------------------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        result = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        if result.get("protocolVersion") not in SUPPORTED_VERSIONS:
            raise McpError(
                f"unsupported MCP protocol version {_short(str(result.get('protocolVersion')))}"
            )
        self.notify("notifications/initialized")
        self._initialized = True
        return result

    def list_tools(self) -> list[McpToolInfo]:
        self._require_initialized()
        tools: list[McpToolInfo] = []
        names: set[str] = set()
        catalogue = 0
        cursor: str | None = None
        seen: set[bytes] = set()  # hashes: a hostile cursor is not kept
        deadline = time.monotonic() + self._server.call_timeout_s  # one deadline for all pages
        for _ in range(MAX_TOOL_PAGES):
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError(f"tools/list took over {self._server.call_timeout_s}s in total")
            result = self.request(
                "tools/list", {"cursor": cursor} if cursor else {}, timeout_s=left
            )
            page = result.get("tools")
            if page is None:
                page = []
            if not isinstance(page, list):
                raise McpError("tools/list 'tools' is not a list")
            for raw in page:
                if isinstance(raw, dict) and isinstance(raw.get("name"), str):
                    name = raw["name"]
                    if len(tools) >= MAX_TOOLS:
                        raise McpError(f"server lists more than {MAX_TOOLS} tools")
                    if not name or len(name) > MAX_TOOL_NAME_CHARS or not name.isprintable():
                        raise McpError(
                            f"server lists a tool name that is empty, over {MAX_TOOL_NAME_CHARS} "
                            f"characters or not printable: {_short(name)}"
                        )
                    if name in names:
                        raise McpError(f"server lists the tool {_short(name)} more than once")
                    names.add(name)
                    schema = raw.get("inputSchema")
                    hints = raw.get("annotations")
                    desc = str(raw.get("description") or "")
                    digest = tool_digest(
                        desc,
                        schema,
                        title=raw.get("title"),
                        output_schema=raw.get("outputSchema"),
                        annotations=hints,
                    )
                    schema = schema if isinstance(schema, dict) else {"type": "object"}
                    if len(desc) > MAX_DESCRIPTION_CHARS:
                        desc = desc[: MAX_DESCRIPTION_CHARS - len(TRUNCATED_MARK)] + TRUNCATED_MARK
                    size = len(json.dumps(schema, default=str))
                    if size > MAX_SCHEMA_CHARS:  # keep the tool, drop the schema, say so
                        desc += f" [inputSchema of {size} chars omitted; over {MAX_SCHEMA_CHARS}]"
                        schema = {"type": "object", "additionalProperties": True}
                        size = len(json.dumps(schema))
                    catalogue += len(desc) + size
                    if catalogue > self._server.max_catalogue_chars:
                        raise McpError(
                            f"server catalogue is over {self._server.max_catalogue_chars} "
                            "characters of descriptions and schemas"
                        )
                    tools.append(
                        McpToolInfo(
                            name=name,
                            public_name=public_tool_name(self._server.name, name),
                            description=desc,
                            input_schema=schema,
                            read_only=isinstance(hints, dict) and hints.get("readOnlyHint") is True,
                            digest=digest,
                        )
                    )
            nxt = result.get("nextCursor")
            if nxt is None or nxt == "":
                return tools
            if not isinstance(nxt, str):
                raise McpError("tools/list nextCursor is not a string")
            if len(nxt) > MAX_CURSOR_CHARS:
                raise McpError(f"tools/list nextCursor is over {MAX_CURSOR_CHARS} characters")
            mark = hashlib.sha256(nxt.encode("utf-8", "surrogatepass")).digest()
            if mark in seen:
                raise McpError("tools/list repeated a cursor")
            seen.add(mark)
            cursor = nxt
        raise McpError("too many tools/list pages")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> McpResult:
        self._require_initialized()
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        parts: list[str] = []
        content = result.get("content")
        if content is None:
            content = []
        if not isinstance(content, list):
            raise McpError("tools/call 'content' is not a list")
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, dict):
                parts.append(f"[{item.get('type', 'unknown')} content omitted]")
        text = "\n".join(parts)
        is_error = result.get("isError") is True
        text = redact(text, self._secrets(), mcp_shapes=is_error)  # values on every result
        return McpResult(text, is_error)

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise McpError("not initialized")

    # -- shutdown ----------------------------------------------------------------------------

    def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            closer = threading.Thread(target=self._close_stdin, args=(proc,), daemon=True)
            closer.start()
            closer.join(STDIN_CLOSE_S)  # a full pipe must not hang close(); kill unblocks it
            try:
                proc.wait(timeout=STDIN_CLOSE_S)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=TERMINATE_WAIT_S)
                except subprocess.TimeoutExpired:
                    _kill_group(proc)
                    proc.wait(timeout=TERMINATE_WAIT_S)
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            _kill_group(proc)  # even if the child exited: a grandchild may hold the pipes open
            self._proc = None
            self._initialized = False
            self._fail("MCP session closed")
            deadline = time.monotonic() + 1.0
            for t in self._threads:
                t.join(max(0.0, deadline - time.monotonic()))
            if not any(t.is_alive() for t in self._threads):
                for pipe in (proc.stdout, proc.stderr):
                    if pipe is not None:
                        pipe.close()

    @staticmethod
    def _close_stdin(proc: subprocess.Popen[str]) -> None:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except (OSError, ValueError):
            pass


QUARANTINE_NOTICE: Final = (
    "[quarantined: this tool's definition changed or is not yet approved; its text is withheld "
    "and calls are refused until an operator approves it]"
)
_UNSET: Final = object()


class McpTool:
    """Adapts one MCP tool to the runtime ``Tool`` protocol.

    ``approved`` is the digest an operator last approved for this tool (None: none yet). A
    quarantined tool shows the model ``shown`` (its last approved definition) when the caller has
    it, else only a fixed notice; the server's new text never reaches the model.
    """

    def __init__(
        self,
        client: McpClient,
        info: McpToolInfo,
        quarantine: str | None = None,
        approved: Any = _UNSET,
        shown: McpToolInfo | None = None,
    ) -> None:
        self._client = client
        self._info = info
        self._quarantine = quarantine
        self.approved_digest: str | None = (
            (info.digest if quarantine is None else None) if approved is _UNSET else approved
        )
        desc, params = info.description, info.input_schema
        if quarantine is not None:
            desc, params = QUARANTINE_NOTICE, {"type": "object", "additionalProperties": True}
            if shown is not None:
                desc = f"{shown.description} {QUARANTINE_NOTICE}"
                params = shown.input_schema
        self.spec = ToolSpec(
            name=info.public_name,
            description=desc,
            parameters=params,
            idempotent=False,
            timeout_s=client._server.call_timeout_s + SPEC_TIMEOUT_MARGIN_S,
        )

    @property
    def quarantined(self) -> bool:
        return self._quarantine is not None

    @property
    def tool_name(self) -> str:
        """The server's own name for the tool (the public name adds the server and a digest)."""
        return self._info.name

    def run(self, arguments: dict[str, Any]) -> str:
        if self._quarantine is not None:
            raise McpToolError(self._quarantine)
        result = self._client.call_tool(self._info.name, arguments)
        if result.is_error:
            raise McpToolError(result.text)
        return result.text


def approved_digests(tools: Iterable[McpTool]) -> dict[str, str]:
    """The mapping to store and pass as ``previous`` next time: tool name to approved digest.

    A quarantined tool keeps its LAST APPROVED digest (a tool with none is left out, so it stays
    new), never the digest the server sent now. Storing the raw latest listing instead would
    approve a changed tool on the following listing; callers must persist this mapping.
    """
    return {t._info.name: t.approved_digest for t in tools if t.approved_digest is not None}


def _no_str(value: object, what: str) -> None:
    if isinstance(value, str):
        raise TypeError(f"{what} must be a collection of names, not one string")


def mcp_tools(
    client: McpClient,
    *,
    previous: Mapping[str, str] | None = None,
    enabled: Collection[str] | Mapping[str, str] = (),
    trusted_read_only: Collection[str] = (),
    approved_infos: Mapping[str, McpToolInfo] | None = None,
) -> list[McpTool]:
    """Tools of one server.

    ``previous`` is the approved baseline as a mapping of tool name to ``McpToolInfo.digest``; a set
    or list of names is refused with TypeError, because names alone cannot show that a tool changed.
    Build it with ``approved_digests`` of the last call and persist that, not the raw listing.
    A tool that is new since then, or whose digest (description, schema, title, output schema or
    annotations) changed, comes back quarantined: a call is refused with a reason until the operator
    enables it, and the model sees a fixed notice (and the last approved text from
    ``approved_infos``, if given and its digest matches the approved one), never the server's new
    text. ``enabled`` is either a mapping of name to the digest the operator approved (the tool runs
    only while its digest still matches, also on the first listing) or a plain collection of names
    (a new tool with that name runs, but a tool that is in ``previous`` with another digest stays
    quarantined; approve a changed tool by giving its new digest in a mapping). A new tool skips
    quarantine only if the operator names it in ``trusted_read_only``; the server's own readOnlyHint
    is not trusted. The first listing (``previous`` is None, no digest mapping) is the baseline.
    (adapted from references/paperclip/doc/MCP-ACCESS-GOVERNANCE.md:221 (MIT), idea only)
    """
    if previous is not None and not isinstance(previous, Mapping):
        raise TypeError("previous must be a mapping of tool name to digest, not a set or list")
    _no_str(enabled, "enabled")
    _no_str(trusted_read_only, "trusted_read_only")
    cfg = client._server
    tools: list[McpTool] = []
    for info in client.list_tools():
        if (cfg.allowed_tools is not None and info.name not in cfg.allowed_tools) or (
            info.name in cfg.blocked_tools
        ):
            continue
        why = None
        keep: str | None = info.digest  # the digest that stays approved after this listing
        by_digest = isinstance(enabled, Mapping)
        approved = (
            enabled.get(info.name) == info.digest
            if isinstance(enabled, Mapping)
            else info.name in enabled
        )
        if previous is None:
            if isinstance(enabled, Mapping) and info.name in enabled and not approved:
                why = (
                    f"quarantined: tool {_short(info.name)} does not match the digest the "
                    "operator approved; an operator must approve its new digest before it "
                    "can be called"
                )
                keep = enabled[info.name]
        elif info.name not in previous:
            if not approved and info.name not in trusted_read_only:
                why = (
                    f"quarantined: tool {_short(info.name)} is new since the last catalog "
                    "listing and the operator has not trusted it; an operator must enable it "
                    "by name before it can be called"
                )
                keep = None
        elif previous[info.name] != info.digest and not (by_digest and approved):
            why = (
                f"quarantined: tool {_short(info.name)} changed its definition since the "
                "last catalog listing; an operator must approve its new digest before it "
                "can be called"
            )
            keep = previous[info.name]
        shown = None
        if why is not None and approved_infos is not None:
            old = approved_infos.get(info.name)
            if old is not None and old.digest == keep:
                shown = old
        tools.append(McpTool(client, info, why, keep, shown))
    return tools


_STORE_VERSION: Final = 1
_INFO_FIELDS: Final = ("name", "public_name", "description", "input_schema", "read_only", "digest")


def _info_from_json(raw: Any) -> McpToolInfo:
    """Rebuild one stored definition; any wrong shape or type raises ValueError (fail closed)."""
    ok = (
        isinstance(raw, dict)
        and set(raw) == set(_INFO_FIELDS)
        and all(isinstance(raw[k], str) for k in ("name", "public_name", "description", "digest"))
        and isinstance(raw["input_schema"], dict)
        and isinstance(raw["read_only"], bool)
    )
    if not ok:
        raise ValueError("stored tool definition has the wrong shape")
    return McpToolInfo(**raw)


class ApprovalStore:
    """Keeps the caller's half of the MCP contract: persist ``approved_digests`` and the approved
    definitions between listings, so a changed tool stays quarantined after a restart and a caller
    cannot forget to store them. One JSON file at a caller-supplied path, replaced atomically and
    kept at mode 0600 (POSIX).

    No file means a first listing (the baseline: ``previous`` is None). A file that cannot be read,
    is not a regular file, can be written by group or others, or is not exactly the expected JSON
    is not trusted: ``load`` answers an empty mapping, so every tool counts as new and comes back
    quarantined until the operator enables it. The save that follows rewrites the file as a valid,
    empty one, so the closed state persists. A tool the server stops listing is dropped from the
    file and is quarantined as new if it comes back. Not wired into any entrypoint.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = os.fspath(path)

    def load(self) -> tuple[dict[str, str] | None, dict[str, McpToolInfo]]:
        """(previous, approved_infos) to pass to ``mcp_tools``."""
        try:
            st = os.lstat(self._path)
        except FileNotFoundError:
            return None, {}
        except OSError:
            return {}, {}
        try:
            if not stat.S_ISREG(st.st_mode) or (os.name == "posix" and st.st_mode & 0o022):
                raise ValueError("not a regular file, or writable by group or others")
            with open(self._path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict) or data.get("version") != _STORE_VERSION:
                raise ValueError("unknown layout")
            digests, raw_infos = data["digests"], data["infos"]
            if not isinstance(digests, dict) or not isinstance(raw_infos, dict):
                raise TypeError("digests and infos must be objects")
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in digests.items()):
                raise ValueError("digests must map names to strings")
            infos = {k: _info_from_json(v) for k, v in raw_infos.items()}
            return dict(digests), infos
        except (OSError, ValueError, KeyError, TypeError):  # JSONDecodeError is a ValueError
            return {}, {}

    def save(self, tools: Iterable[McpTool]) -> None:
        """Write ``approved_digests(tools)`` and the approved definition of each such tool."""
        tools = list(tools)
        _, old = self.load()
        digests = approved_digests(tools)
        infos: dict[str, dict[str, Any]] = {}
        for t in tools:
            name = t._info.name
            if name not in digests:
                continue
            info = t._info if not t.quarantined else old.get(name)
            if info is not None and info.digest == digests[name]:
                infos[name] = {k: getattr(info, k) for k in _INFO_FIELDS}
        blob = json.dumps({"version": _STORE_VERSION, "digests": digests, "infos": infos})
        tmp = f"{self._path}.{os.getpid()}.{time.monotonic_ns()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(blob)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def mcp_tools(
        self,
        client: McpClient,
        *,
        enabled: Collection[str] | Mapping[str, str] = (),
        trusted_read_only: Collection[str] = (),
    ) -> list[McpTool]:
        """``mcp_tools`` with the stored baseline, then save the new one."""
        previous, infos = self.load()
        tools = mcp_tools(
            client,
            previous=previous,
            enabled=enabled,
            trusted_read_only=trusted_read_only,
            approved_infos=infos,
        )
        self.save(tools)
        return tools
