# Master FinHub runtime — slice design (revision 2, slices 8-11)

## Changes in revision 2
- Changed: A3 (reworded to the per-agent suffix only), A39 (three new stub modes), A49 (`_both` at :111; events from `snapshot.messages[-1]`).
- Added: A73 (per-run container: reference recreate vs our `mf_<uuid8>` + `--rm`), A74 (bounded stream queue with stop event and reader join, F2), A75 (`MAX_LINE_BYTES` via `readline(limit)`, F1), A76 (`MAX_TOOL_PAGES`, F1), A77 (`-32601` reply to server requests, F1), A78 (eval `tools_factory` receives the per-case `Workspace`, N4).
- Slice-text notes folded in: N1 (`DockerEngine.stream` checks before returning the generator), N2 (container read-only check is a smoke test; argv test proves `--read-only`), N5 (timed-out never passes).
- All other rows are unchanged.

Scope: slices 8-11 only. Slices 1-7 are built and merged and are NOT redesigned here; every slice below plugs into their real interfaces (read this session):

| existing interface | where | used by |
|---|---|---|
| `AgentLoop(llm, tools, max_steps, *, context, guard, checkpoint)`, `Tool` protocol (`spec: ToolSpec`, `run(dict) -> str`), `ToolSpec(name, description, parameters, idempotent)`, `ToolGuard = Callable[[ToolCall], str \| None]`, `CheckpointHook = Callable[[LoopSnapshot], None]` (a raising hook fails closed) | `runtime/loop.py` | 8, 9, 10, 11 |
| `ScriptedLLM` (prompt `echo X` -> calls `echo`, answers with the result) | `runtime/fake_llm.py` | 10, 11 |
| `EchoTool` | `tools/builtins/echo.py` | 10, 11 |
| `check_command(command, policy=DEFAULT_POLICY) -> str \| None` (denylist always wins, even in allowlist mode), `CommandPolicy`, `guard_tool_call`, `make_guard`, `COMMAND_ARG_KEYS` (`command`, `cmd`, `script`, `shell_command`) | `tools/safety.py` | 8, 9, 10, 11 |
| `Workspace(root)`, `.root`, `.read_text`, `.write_text`, `SandboxDenied` | `sandbox/workspace.py` | 8, 11 |
| `_both(parent, extra)` guard combiner: parent first, extra can only add denials | `orchestration/modes/subagent.py:111` | 10 |
| `ContextManager` | `runtime/context.py` | 10, 11 |

Global constraints resolved for all four slices:

- **(a) No new dependency.** `pyproject.toml` `dependencies = []` stays empty. Docker = the `docker` CLI via `subprocess`; MCP = hand-rolled newline-delimited JSON-RPC 2.0 over stdio; SSE = stdlib `http.server.ThreadingHTTPServer`. The `docker` SDK, `mcp` SDK, FastAPI/uvicorn/Flask and pydantic seen in the references are all rejected.
- **Python version.** The pinned toolchain here is Python 3.11 (`requires-python = ">=3.11"`, ruff `target-version = "py311"`, the sandbox runs 3.11.15). All code must be 3.11-compatible (no PEP 695 `type` statements, no 3.12-only stdlib); `enum.StrEnum` (3.11) is fine.
- **(b) dify** is Modified Apache-2.0: rows citing dify are `pattern` only. The builder writes fresh code with no dify identifiers (`stream_topic_events`, `StreamEvent`, `MCPClient`, `invoke_tool`, `ClientSession` must not appear), no dify comments and no dify structure.
- **(c) `references/autogpt/autogpt_platform/**`** (Polyform Shield) is never cited or read. All autogpt rows are under `classic/` (MIT).
- **(d) Net-new honesty.** Slices 8 and 10 have little direct reference code. Every design decision without a reference line is a `NET-NEW` row with a reason and a named test.
- **(e) No host exec of agent-written code.** Verifiers are deterministic string/structure checks; any future code-running verifier must go through slice 8's `DockerEngine` (A57, A64).
- **(f)** Slice 8 container tests skip cleanly without docker (A15). Note: the build sandbox has the `docker` CLI but no daemon (`docker info` fails to connect), so the skip path is what runs here.
- **(g)** Every slice has a one-line proof command.
- **(h) Guards never weaken.** New tools (`sandbox_exec`, `mcp__*`) are ordinary `Tool`s, so the loop's guard (and the slice-7 `_both` scope guard for children) vets every call. Slices 8 and 9 additionally re-run `check_command` at their own boundary with `DEFAULT_POLICY` as floor; slice 10 composes `guard_tool_call` first via `_both`. Server default bind is `127.0.0.1` (A45).

---

## Slice 8 — docker sandbox engine + process output stream

### Goal
Daniel runs `pytest tests/test_stream.py tests/test_docker_engine.py -q` and sees the stream/argv tests pass and the container test either pass (`echo hi` printed from inside a `--network none` container) or report `SKIPPED (docker daemon not available)`.

### Files
| path | new/modified |
|---|---|
| src/master_finhub/sandbox/stream.py | new (0-byte stub today) |
| src/master_finhub/sandbox/docker_engine.py | new (0-byte stub today) |
| tests/test_stream.py | new |
| tests/test_docker_engine.py | new |

### Interfaces
```python
# sandbox/stream.py — host-process I/O primitives (also used by slice 9)
SENSITIVE_ENV: Final = re.compile(r"KEY|PASSWORD|SECRET|TOKEN", re.IGNORECASE)
DEFAULT_MAX_OUTPUT_BYTES: Final = 64_000
ChunkKind = Literal["stdout", "stderr", "exit", "timeout"]

def scrubbed_env(extra: Mapping[str, str] | None = None) -> dict[str, str]: ...
    # os.environ minus SENSITIVE_ENV names, then `extra` merged on top (explicit wins)

@dataclass(frozen=True)
class Chunk:
    seq: int            # 0,1,2,... in delivery order
    kind: ChunkKind
    data: str           # decoded text; for "exit" the return code as text; "" for "timeout"

class TailBuffer:
    def __init__(self, max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None: ...
    def push(self, data: bytes) -> None: ...
    def text(self) -> str: ...            # utf-8, errors="replace"
    @property
    def truncated(self) -> bool: ...

@dataclass(frozen=True)
class ExecResult:
    exit_code: int | None    # None when killed on timeout
    stdout: str              # tail when truncated
    stderr: str
    truncated: bool
    timed_out: bool

def stream_process(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    timeout_s: float,
    on_timeout: Callable[[], None] | None = None,   # e.g. `docker kill <name>`
) -> Iterator[Chunk]: ...

def collect(chunks: Iterable[Chunk], max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> ExecResult: ...

# sandbox/docker_engine.py
DEFAULT_IMAGE: Final = "python:3.12-alpine"
CONTAINER_WORKDIR: Final = "/workspace"

def docker_available(timeout_s: float = 10.0) -> bool: ...
def image_present(image: str, timeout_s: float = 10.0) -> bool: ...

@dataclass(frozen=True)
class SandboxConfig:
    image: str = DEFAULT_IMAGE
    timeout_s: int = 120          # __post_init__: ValueError unless 1 <= timeout_s <= 600
    memory: str = "512m"
    cpus: str = "1"
    pids_limit: int = 128
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES
    env: Mapping[str, str] = field(default_factory=dict)   # the ONLY env the container sees

class CommandBlocked(PermissionError):
    """check_command denied the command; message is the denial text, never the command."""

def docker_argv(config: SandboxConfig, workspace_root: Path, command: str, name: str) -> list[str]: ...

class DockerEngine:
    def __init__(self, workspace: Workspace, config: SandboxConfig = SandboxConfig(),
                 policy: CommandPolicy = DEFAULT_POLICY) -> None: ...
    def stream(self, command: str) -> Iterator[Chunk]: ...
        # plain function, not a generator: runs check_command and raises CommandBlocked
        # immediately, then returns the stream_process(...) generator
    def run(self, command: str) -> ExecResult: ...           # collect(self.stream(command))

class SandboxExecTool:        # satisfies runtime.loop.Tool
    spec = ToolSpec(name="sandbox_exec",
                    description="Run a shell command inside an isolated, network-less container "
                                "whose only writable folder is the workspace.",
                    parameters={"type": "object",
                                "properties": {"command": {"type": "string"}},
                                "required": ["command"]},
                    idempotent=False)
    def __init__(self, engine: DockerEngine) -> None: ...
    def run(self, arguments: dict[str, Any]) -> str: ...
        # "exit=<n>\nSTDOUT:\n...\nSTDERR:\n..." plus "[output truncated]" / "[timed out after Ns]"
```

`docker_argv` output, in this order (pure function, unit-tested without docker):
```
docker run --rm --pull never --name <name> --network none --read-only
  --tmpfs /tmp:rw,nosuid,nodev,size=64m --pids-limit <n> --memory <m> --cpus <c>
  --cap-drop ALL --security-opt no-new-privileges [--user <uid>:<gid>  (POSIX only)]
  --mount type=bind,src=<workspace_root>,dst=/workspace -w /workspace
  [-e K=V for each config.env item, sorted]  <image>  sh -c <command>
```

### Behaviour (claims -> Authority List)
- `docker_available()` runs `docker info --format {{.OSType}}` and returns True only for exit 0 and output `linux`; a missing binary, timeout or any exception returns False (A1, A15).
- The workspace root is bind-mounted read-write at `/workspace` and is the working directory (A2). It is the ONLY writable path besides a size-capped `/tmp` tmpfs; the root filesystem is read-only (A9, A13).
- Each run gets its own container `mf_<uuid4().hex[:8]>` and `--rm`, so runs never share or reuse a container. The reference gives each agent its own name (A3) and recreates its container on every run (A73); this design gets the same per-run isolation with a fresh name plus `--rm` (A73).
- `timeout_s` is bounded 1-600, default 120 (A4). On deadline the engine runs `docker kill <name>` (via `on_timeout`) and then kills the local CLI process group; the result has `timed_out=True`, `exit_code=None` (A12, A8).
- The host-side `docker` CLI process gets `scrubbed_env()`; the container gets only `config.env` via `-e` (A5, A13).
- `stream_process` starts the child with `start_new_session=True`, runs one reader thread per pipe reading `read1(65536)` chunks into a bounded `queue.Queue(maxsize=256)` (back-pressure, not unbounded memory; A74); each reader posts a `None` sentinel at EOF; a reader exception is posted as an item and re-raised by the consumer (A10). Readers never block forever: every `put` uses `timeout=0.1` in a loop that exits when a shared `threading.Event` (`stop`) is set, including the final sentinel put (A74). Chunks are numbered by the consumer in delivery order (A11). After both sentinels it yields `Chunk("exit", str(rc))`. Its `finally` sets `stop`, kills the process group idempotently (process-group first, direct child as fallback) so the pipes reach EOF, closes the pipes and joins both readers (timeout 5 s), so a consumer that stops early, even with a full queue, leaks no process, thread or pipe (A8, A74).
- `collect` keeps a per-stream `TailBuffer` that drops from the head once over `max_bytes`, and reports `truncated` (A6, A7).
- Before spawning, `DockerEngine.stream` calls `check_command(command, policy)`; a denial raises `CommandBlocked` (A14). Because `check_command` always applies the denylist, no `policy` can make it weaker than the slice-3 default.
- Host side never uses `shell=True`; the agent's command string is only ever interpreted by `sh -c` inside the container (A16).
- `docker_argv` rejects (ValueError) a workspace root containing `,`, `=`, newline or NUL, which would let a path inject extra `--mount` fields (A17). Image tag must match `[A-Za-z0-9][A-Za-z0-9._/:@-]{0,127}`; env names must match `[A-Za-z_][A-Za-z0-9_]*` (A17).
- `--pull never`: a run never silently downloads an image; a missing image is a clear error naming `docker pull <image>` (A13).

### Touches existing interfaces
- Imports `Workspace` (uses `.root`, already resolved and existing) and `check_command`, `CommandPolicy`, `DEFAULT_POLICY` from slice 3; `ToolSpec` from slice 1. Modifies none of them.
- `SandboxExecTool` uses the argument key `command`, which is in `COMMAND_ARG_KEYS`, so the loop guard (and any child `_both` guard) vets it before `run` is reached.

### Failure modes
| failure | handling |
|---|---|
| no docker binary / daemon down | `docker_available()` False; container tests skip; `DockerEngine.run` returns non-zero `ExecResult` with the CLI's stderr (no exception) |
| image not present | `--pull never` -> CLI error in stderr, exit 125; tool text says `docker pull python:3.12-alpine` |
| command denied | `CommandBlocked`; through the loop the model sees `Error: tool 'sandbox_exec' failed: CommandBlocked: Blocked by safety policy ...` |
| runaway output | per-stream 64 KB tail; readers block on the bounded queue, so memory stays bounded |
| hang | deadline -> `docker kill` + process-group kill, `timed_out=True` |
| consumer abandons the generator | `finally` kills the process group and calls `on_timeout` (docker kill) once |

### Proof
Tests to write first:
- `tests/test_stream.py::test_scrubbed_env_drops_secret_names` — `API_KEY`, `db_password`, `GITHUB_TOKEN` gone; `PATH` kept; `extra={"API_KEY": "x"}` re-adds it.
- `test_tail_buffer_keeps_tail` — push 3 x 40 bytes into a 100-byte buffer -> last 100 bytes, `truncated` True.
- `test_stream_process_orders_and_exits` — host test helper `[sys.executable, "-c", "print('a'); import sys; print('b', file=sys.stderr)"]` -> chunks contain stdout `a`, stderr `b`, final `exit`/`0`, seq strictly increasing. (Test code, not agent code.)
- `test_stream_process_timeout_kills_group` — child sleeps 30 s, `timeout_s=1` -> last chunk `timeout`, `on_timeout` called once, process gone (`os.killpg(pgid, 0)` raises `ProcessLookupError`).
- `test_docker_argv_unique_names` — two `DockerEngine` runs (argv captured via a monkeypatched `stream_process`) use different `--name mf_<8 hex>` values and both argvs contain `--rm`.
- `test_abandoned_stream_releases_readers` — child prints 10 MB with `maxsize` reached before the consumer reads; consumer takes one chunk then calls `.close()` on the generator; within 5 s both reader threads are no longer alive (`threading.enumerate()`), the process group is gone and both pipes are closed.
- `test_docker_argv_hardening` — argv contains `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit`, `--rm`, `--pull never`, `dst=/workspace`; never contains `--privileged`, `docker.sock` or `host`.
- `test_docker_argv_rejects_comma_root`, `test_config_timeout_bounds` (0 and 601 raise; 1 and 600 accepted).
- `test_engine_blocks_denied_command` — `DockerEngine(...).run("rm -rf /")` raises `CommandBlocked` without invoking docker (monkeypatch `subprocess.Popen` to fail the test if called).
- `test_docker_available_false_without_daemon` — monkeypatch `subprocess.run` to raise `FileNotFoundError` -> False.
- `test_echo_in_container` — `@pytest.mark.skipif(not (docker_available() and image_present(DEFAULT_IMAGE)), reason="docker daemon or image not available")`; `run("echo hi").stdout == "hi\n"`; `run("touch /etc/x").exit_code != 0` (smoke test only: the non-root `--user` would also block it, so `--read-only` itself is proven by `test_docker_argv_hardening`); `run("wget -T 2 http://example.com")` fails (no network).

Proof command: `pytest tests/test_stream.py tests/test_docker_engine.py -q` -> all pass, container test passes or is `SKIPPED (docker daemon or image not available)`.

### Dependencies
None. The `docker` CLI is an external program, not a Python dependency.

### Ported vs net-new
| part | source | port as |
|---|---|---|
| availability probe | autogpt classic code_executor.py (A1) | adapt to CLI |
| workspace mount at /workspace, per-run name, 1-600 s bound | autogpt classic (A2-A4) | adapt |
| env scrub | deepseek subprocess (A5) | adapt |
| tail buffer, collected shape | deepseek (A6, A7) | adapt |
| group kill with fallback | deepseek spawn.ts (A8) | adapt |
| read-only root + writable workspace/tmp | deepseek bwrap profile (A9) | adapt to docker flags |
| thread + queue + sentinel stream, seq frames | crewai (A10, A11) | adapt |
| docker kill on timeout, hardening flags, re-check, argv validation, `--pull never` | — | net-new (A12-A17) |

### Quant guardrails
Not applicable: G1-G6 N/A — slice 8 runs commands; it computes no prices, returns, P&L or data splits.

### Accepted risks
- Membership of the `docker` group is root-equivalent on the host; this slice does not change who may run docker.
- Container escape via kernel bugs is out of scope; the flags reduce, not remove, that surface.
- No opt-in for network access in this slice (YAGNI); add a reviewed `network` field when a real use needs it.

### Out of scope
Long-lived/reused containers, image building, network opt-in, Windows containers, and wiring `sandbox_exec` into the CLI default tool set (the CLI keeps `EchoTool` only until Daniel asks).

---

## Slice 9 — MCP client (stdio, hand-rolled JSON-RPC 2.0)

### Goal
Daniel runs `pytest tests/test_mcp_client.py -q`: a stub MCP server (a Python script in `tests/`) is started over stdio, the client handshakes, lists its tools, calls `echo` and gets `hi` back, and an agent loop calls the tool by its public name `mcp__stub__echo`.

### Files
| path | new/modified |
|---|---|
| src/master_finhub/tools/mcp/client.py | new |
| tests/mcp_stub_server.py | new (test fixture, newline-delimited JSON-RPC server, stdlib only) |
| tests/test_mcp_client.py | new |

### Interfaces
```python
PROTOCOL_VERSION: Final = "2025-06-18"
SUPPORTED_VERSIONS: Final = frozenset({"2025-06-18", "2025-03-26", "2024-11-05"})
DEFAULT_CALL_TIMEOUT_S: Final = 30.0
MAX_TOOL_PAGES: Final = 20
MAX_LINE_BYTES: Final = 4_000_000          # read via readline(MAX_LINE_BYTES + 1); longer -> session closed

@dataclass(frozen=True)
class StdioServer:
    name: str                               # [a-z0-9_-]{1,32}
    command: tuple[str, ...]                # argv, never a shell string
    env: Mapping[str, str] = field(default_factory=dict)   # explicit env, merged over scrubbed_env()
    cwd: str | None = None
    call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S
    allowed_tools: frozenset[str] | None = None            # None = all, unless blocked
    blocked_tools: frozenset[str] = frozenset()            # block wins

class McpError(RuntimeError):
    def __init__(self, message: str, code: int | None = None) -> None: ...
class McpClosed(McpError): ...          # server exited / stdout closed; every waiter gets this
class McpToolError(McpError): ...       # tool returned isError: true

@dataclass(frozen=True)
class McpToolInfo:
    name: str                   # server's raw name, used on the wire
    public_name: str            # model-facing: mcp__<server>__<tool>
    description: str
    input_schema: dict[str, Any]

@dataclass(frozen=True)
class McpResult:
    text: str                   # all text content items joined with "\n"
    is_error: bool

def public_tool_name(server: str, tool: str) -> str: ...
def redact(text: str, secrets: Iterable[str]) -> str: ...

class McpClient:
    def __init__(self, server: StdioServer) -> None: ...
    def __enter__(self) -> McpClient: ...    # start() + initialize()
    def __exit__(self, *exc: object) -> None: ...   # close()
    def start(self) -> None: ...             # check_command(shlex.join(command)) first; McpError on denial
    def initialize(self) -> dict[str, Any]: ...
    def request(self, method: str, params: dict[str, Any] | None = None,
                timeout_s: float | None = None) -> dict[str, Any]: ...
    def notify(self, method: str, params: dict[str, Any] | None = None) -> None: ...
    def list_tools(self) -> list[McpToolInfo]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> McpResult: ...
    def close(self) -> None: ...             # idempotent
    @property
    def stderr_tail(self) -> tuple[str, ...]: ...

class McpTool:                               # satisfies runtime.loop.Tool
    spec: ToolSpec                           # name=public_name, parameters=input_schema, idempotent=False
    def __init__(self, client: McpClient, info: McpToolInfo) -> None: ...
    def run(self, arguments: dict[str, Any]) -> str: ...   # McpToolError on is_error

def mcp_tools(client: McpClient) -> list[McpTool]: ...   # list_tools() filtered by allow/block
```

### Behaviour (claims -> Authority List)
- Spawn: `subprocess.Popen(server.command, stdin/stdout/stderr=PIPE, text=True, encoding="utf-8", bufsize=1, env=scrubbed_env(server.env), cwd=server.cwd)` (A18, A34). Before spawning, `check_command(shlex.join(server.command))` must return None, else `McpError` (A38).
- A daemon reader thread parses one JSON object per stdout line, skipping blank and undecodable lines (A18). It reads with `proc.stdout.readline(MAX_LINE_BYTES + 1)` instead of `for line in proc.stdout`, so at most `MAX_LINE_BYTES + 1` characters are ever held; a line that reaches that length without a newline closes the session and fails every waiter with `McpClosed("server line too long")` (A75). A second daemon thread drains stderr into a `deque(maxlen=200)` so a chatty server cannot block on a full pipe (A19).
- Requests use an integer id counter; each request registers a one-slot `queue.Queue` under its id before writing; responses are routed by id; an `error` object raises `McpError(message, code)`, otherwise the `result` dict is returned (A20). Writes are serialised by a write lock (A23).
- Each request has a deadline (`server.call_timeout_s` default 30 s); on expiry the waiter is removed and `TimeoutError` is raised (A21).
- On stdout EOF or a reader exception, every pending waiter is failed with `McpClosed`, so no caller hangs (A22).
- Handshake: `initialize` with `protocolVersion`, empty `capabilities` and `clientInfo {"name": "master-finhub", "version": <pkg version>}`; a server version outside `SUPPORTED_VERSIONS` raises `McpError`; then the `notifications/initialized` notification is sent (A25, A26). `list_tools`/`call_tool` before a successful handshake raise `McpError("not initialized")` (A36).
- `list_tools` follows `nextCursor` until absent, capped at `MAX_TOOL_PAGES`; a server still returning `nextCursor` after 20 pages raises `McpError("too many tools/list pages")` instead of looping forever (A27, A76).
- `call_tool` sends `tools/call {name, arguments}` with the per-call timeout (A29); `isError: true` is carried on `McpResult` (A31), and `McpTool.run` raises `McpToolError` so the loop returns `Error: tool '<name>' failed: ...` (A30). All `type == "text"` content items are joined; non-text items become `[<type> content omitted]` (A32).
- Public names: `mcp__<server>__<tool>`, characters outside `[A-Za-z0-9_-]` replaced by `_`, and when the name changed or exceeds 64 characters it is cut and suffixed `_<12 hex of sha256(server \0 tool)>` (A28). The 64-char rule also matches the existing provider id check `^[A-Za-z0-9_\-]{1,64}$` in `runtime/anthropic_llm.py:117`.
- Allow/block filter on raw tool names, block wins (A33).
- Error text and stderr tail returned to the model or raised are passed through `redact`, which replaces every `server.env` value of length >= 4 and `Bearer <token>` / GitHub / Slack / JWT shapes with `[REDACTED]` (A35).
- `close()`: close stdin, wait 2 s, `terminate()`, wait 5 s, `kill()`; session state reset in `finally`; idempotent (A24, A37).

### Touches existing interfaces
- Imports `scrubbed_env` from slice 8 `sandbox/stream.py`; `check_command` from slice 3; `ToolSpec` from slice 1.
- `McpTool` is a plain `Tool`; it is registered by passing `mcp_tools(client)` in the `tools` list of `AgentLoop` or a slice-7 `SubagentConfig`. The loop guard and any child `_both` guard still vet every call (a `command`/`cmd` argument to an MCP tool is denylist-checked like any other).
- No change to `loop.py`, `safety.py` or the CLI.

### Failure modes
| failure | handling |
|---|---|
| server binary missing | `McpError("could not start MCP server '<name>'")`, no traceback with env |
| server exits mid-call | waiter gets `McpClosed`; `stderr_tail` (redacted) attached to the message |
| server never answers | `TimeoutError` after `call_timeout_s` |
| junk on stdout | non-JSON lines skipped; a line over `MAX_LINE_BYTES` closes the session (`McpClosed`) |
| server sends a request to the client (sampling, roots) | the reader answers `{"jsonrpc":"2.0","id":<same id>,"error":{"code":-32601,"message":"Method not found"}}` (we advertise no capabilities); pending client requests are unaffected (A77) |
| secret in env echoed in an error | redacted before it reaches the model |

### Proof
Tests to write first (all use `[sys.executable, "tests/mcp_stub_server.py"]`):
- `test_handshake_and_list` — `with McpClient(...) as c:` -> `[t.name for t in c.list_tools()] == ["echo", "fail"]`; stub records it received `notifications/initialized` after `initialize`.
- `test_call_echo_round_trip` — `c.call_tool("echo", {"text": "hi"}) == McpResult("hi", False)`.
- `test_is_error_maps_to_tool_error` — `fail` -> `McpResult(..., True)`; via `McpTool.run` raises `McpToolError`.
- `test_pagination` — stub mode `--paged` returns 2 pages; both tools listed.
- `test_server_death_fails_waiter` — stub mode `--die-on-call`; `call_tool` raises `McpClosed` within 5 s (no hang).
- `test_timeout` — stub mode `--never-answer`, `call_timeout_s=0.5` -> `TimeoutError`.
- `test_unsupported_version_rejected` — stub mode `--version 1999-01-01` -> `McpError`.
- `test_oversize_line_closes_session` — stub mode `--huge-line` writes 5 MB without a newline in reply to `tools/list`; `list_tools` raises `McpClosed` within 5 s and the reader never holds more than `MAX_LINE_BYTES + 1` characters (assert via a monkeypatched smaller `MAX_LINE_BYTES=1000`).
- `test_endless_pages_capped` — stub mode `--endless-pages` always returns a `nextCursor`; `list_tools` raises `McpError` after exactly `MAX_TOOL_PAGES` requests (stub counts them).
- `test_server_request_gets_method_not_found` — stub mode `--ask-client` sends a `sampling/createMessage` request before answering `tools/call`; the stub records the client's reply with `error.code == -32601` and the same id, and `call_tool` still returns `hi`.
- `test_public_name_rules` — `public_tool_name("stub", "echo") == "mcp__stub__echo"`; a 100-char tool gives a 64-char name ending in 12 hex; `"a.b"` vs `"a_b"` differ.
- `test_filter_block_wins`, `test_redact_env_value_and_bearer`, `test_denied_launch_command` (`command=("rm", "-rf", "/")` -> `McpError` before spawn).
- `test_loop_calls_mcp_tool` — a 6-line scripted LLM in the test calls `mcp__stub__echo(text="hi")` then answers with the result; `AgentLoop(llm, mcp_tools(c), guard=guard_tool_call).run("go") == "hi"`.

Proof command: `pytest tests/test_mcp_client.py -q` -> all pass.

### Dependencies
None. The `mcp` PyPI SDK (used by crewai and deepseek) is rejected: new dependency, licence not checked.

### Ported vs net-new
| part | source | port as |
|---|---|---|
| Popen + reader/stderr threads, id->queue routing, deadline, fail-all-waiters, write lock, close sequence | deepseek python sdk client.py (A18-A24) | adapt |
| handshake order, version check, context-manager shape, reset-in-finally | dify (A25, A26, A36, A37) | pattern only, written fresh |
| pagination, public name, tools/call, isError -> error | deepseek mcp-client (A27-A30) | adapt idea (TS -> Python) |
| result carrier, filter, terminate/wait/kill | crewai (A31, A33, A24) | adapt |
| redaction | openhands (A35) | adapt |
| launch-command check, stub server | — | net-new (A38, A39) |

### Quant guardrails
Not applicable: G1-G6 N/A — protocol plumbing; no prices, returns or splits.

### Out of scope
HTTP/SSE MCP transports, OAuth, reconnect supervisor, tool-list caching, resources/prompts, image content, config file loading of MCP servers.

---

## Slice 10 — HTTP server + SSE event stream

### Goal
Daniel runs `pytest tests/test_server.py -q`: a test client POSTs `{"prompt": "echo hi"}` to a server on `127.0.0.1:<random port>`, opens the run's event stream and receives `ping` first, then `message` events, then `done` with data `"hi"`.

### Files
| path | new/modified |
|---|---|
| src/master_finhub/server/sse.py | new (0-byte stub today) |
| src/master_finhub/server/app.py | new (0-byte stub today) |
| tests/test_sse.py | new |
| tests/test_server.py | new |

### Interfaces
```python
# server/sse.py
class EventName(StrEnum):
    PING = "ping"; MESSAGE = "message"; DONE = "done"; ERROR = "error"

TERMINAL: Final = frozenset({EventName.DONE, EventName.ERROR})
IDLE_TIMEOUT_S: Final = 300.0
PING_INTERVAL_S: Final = 10.0
POLL_S: Final = 1.0

@dataclass(frozen=True)
class SseEvent:
    name: EventName
    data: str              # JSON text, single line

def encode(event: SseEvent, event_id: int | None = None) -> bytes: ...
    # b"id: N\nevent: <name>\ndata: <line>\n" per data line + b"\n"

def event_stream(
    source: queue.Queue[SseEvent],
    *,
    idle_timeout_s: float = IDLE_TIMEOUT_S,
    ping_interval_s: float = PING_INTERVAL_S,
    poll_s: float = POLL_S,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[SseEvent]: ...

# server/app.py
SESSION_HEADER: Final = "X-Session-API-Key"
MAX_BODY_BYTES: Final = 64 * 1024
MAX_RUNNING: Final = 4
MAX_RETAINED: Final = 32
LOOPBACK: Final = frozenset({"127.0.0.1", "::1", "localhost"})

LLMFactory = Callable[[], LLM]

class RunServer(ThreadingHTTPServer):
    session_key: str        # secrets.token_urlsafe(32), generated per server

def make_server(
    llm_factory: LLMFactory,
    tools_factory: Callable[[], list[Tool]],
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    allow_remote: bool = False,
    extra_guard: ToolGuard | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> RunServer: ...        # ValueError if host not in LOOPBACK and not allow_remote

def main(argv: list[str] | None = None) -> int: ...
    # python -m master_finhub.server.app [--port N]; prints URL and session key to stderr;
    # uses ScriptedLLM + EchoTool unless --profile is given (then runtime.router.Router)
```

Routes:
| method + path | auth | response |
|---|---|---|
| `GET /health` | none | `200 {"status":"ok"}` |
| `POST /runs` body `{"prompt": str}` | session header | `202 {"run_id": "<uuid4 hex>"}`; `400` bad JSON/prompt; `413` body > 64 KB; `429` when `MAX_RUNNING` loops are running |
| `GET /runs/<run_id>/events` | session header | `200 text/event-stream`; `404` unknown; `409` stream already attached |
| anything else | — | `404` |
All non-health routes: `401` when the header is missing or wrong (constant-time compare), `421` when the `Host` header's hostname is not loopback while `allow_remote` is False.

### Behaviour (claims -> Authority List)
- `event_stream` yields a `ping` immediately, before reading the queue, so the client sees bytes at once (A40).
- It polls `source.get(timeout=poll_s)`; while idle it emits `ping` every `ping_interval_s` and ends the stream after `idle_timeout_s` without events; any real event resets both timers (A41). Defaults 300 s idle, 10 s ping (A43). The clock is injectable so tests are deterministic.
- After yielding an event whose name is in `TERMINAL` the stream ends (A42).
- The events response uses `Content-Type: text/event-stream` and `Cache-Control: no-cache`, plus `Connection: close`; the handler speaks HTTP/1.0 semantics (no Content-Length, connection closed at stream end) (A44, A48).
- Default bind is `127.0.0.1`; `make_server` refuses a non-loopback host unless `allow_remote=True` (A45). The `Host` header check blocks DNS-rebinding requests from a browser page (A50).
- Every non-health request must carry `X-Session-API-Key` equal to the per-server key, compared with `hmac.compare_digest` (A47). A custom header also forces a CORS preflight, which the server never answers, so a web page cannot start runs cross-origin.
- `POST /runs` starts a daemon thread running `AgentLoop(llm_factory(), tools_factory(), max_steps, context=ContextManager(), guard=g, checkpoint=hook)`, where `g = guard_tool_call` or `_both(guard_tool_call, extra_guard)` — the server can only add denials, never replace the default guard (A49).
- `hook` emits exactly `snapshot.messages[-1]` per call (the loop calls the hook once per appended message, so this is exact even when `ContextManager.fit` shrinks history; no length-diff) as `SseEvent(MESSAGE, json.dumps({"role", "content", "tool_calls": [names]}))`; it never raises (queue is unbounded per run, size bounded by `max_steps`). On return the thread queues `DONE` with `json.dumps(final_text)`; on any exception it queues `ERROR` with `json.dumps(type(exc).__name__)` only — no message text, no traceback (A49).
- One subscriber per run; events queued before the client attaches are delivered after the initial ping. A finished run is retained (oldest evicted beyond `MAX_RETAINED`) and removed when its stream ends (A48).

### Touches existing interfaces
- Uses `AgentLoop`, `CheckpointHook`, `LoopSnapshot`, `LLM`, `Tool`, `ToolGuard`, `DEFAULT_MAX_STEPS` (slice 1), `ContextManager` (slice 2), `guard_tool_call` (slice 3), `Router.build_llm` for `--profile` (slice 4), `_both` from `orchestration/modes/subagent.py` (slice 7) — imported, not copied, so the "parent first, extra only adds denials" rule has one definition. `ScriptedLLM`/`EchoTool` for the default/test configuration. No existing file changes.

### Failure modes
| failure | handling |
|---|---|
| client disconnects mid-stream | `BrokenPipeError`/`ConnectionResetError` caught in the handler; run keeps going; run removed when finished |
| agent raises | `ERROR` event with the exception class name only |
| flood of runs | `429` beyond `MAX_RUNNING` |
| oversized/invalid body | `413` / `400` with a three-part message (what/why/fix), never echoing the body |
| LAN exposure attempt | `ValueError` at `make_server` unless `allow_remote=True`; `421` on non-loopback Host |

### Proof
Tests to write first:
- `tests/test_sse.py::test_encode_frame` — `encode(SseEvent(MESSAGE, '"x"'), 3) == b'id: 3\nevent: message\ndata: "x"\n\n'`; a data value containing `\n` becomes two `data:` lines.
- `test_ping_first_then_event_then_stop` — queue pre-loaded with `MESSAGE`, `DONE` -> names `[ping, message, done]`, generator exhausted.
- `test_idle_pings_then_timeout` — fake clock advanced by `poll_s` per empty poll, `ping_interval_s=2`, `idle_timeout_s=5` -> `[ping, ping, ping]` then stop.
- `tests/test_server.py::test_run_streams_ping_then_events` — `make_server(ScriptedLLM, lambda: [EchoTool()])` on port 0 in a thread; `http.client` POST `/runs` with the key -> 202; GET events -> parsed frames: first `ping`, at least one `message`, last `done` with data `"hi"`.
- `test_missing_key_401`, `test_bad_host_header_421`, `test_unknown_run_404`, `test_second_subscriber_409`, `test_body_too_large_413`.
- `test_refuses_lan_bind` — `make_server(..., host="0.0.0.0")` raises `ValueError`.
- `test_loopback_only` — server on `127.0.0.1`: connect to `127.0.0.1` succeeds; connect to the first non-loopback IPv4 of the host fails (skip if the host has none).
- `test_extra_guard_cannot_weaken` — `extra_guard=lambda c: None` with a scripted LLM that calls a tool with `{"command": "rm -rf /"}` -> the tool's `run` is never invoked.

Proof command: `pytest tests/test_sse.py tests/test_server.py -q` -> all pass.

### Dependencies
None (`http.server`, `socketserver`, `queue`, `threading`, `hmac`, `secrets`, `json`).

### Ported vs net-new
| part | source | port as |
|---|---|---|
| ping-first, idle timeout, ping-while-idle, terminal set, defaults, mimetype + no-cache | dify (A40-A44) | pattern only, written fresh |
| loopback default, LAN opt-in, loopback test | openhands (A45, A46) | adapt |
| session header | openhands (A47) | adapt (header name only) |
| stdlib server, routes, run lifecycle, checkpoint-to-event, Host check | — | net-new (A48-A50) |

### Quant guardrails
Not applicable: G1-G6 N/A — transport only; no prices, returns or splits.

### Out of scope
TLS, multi-user auth, WebSockets, event replay/`Last-Event-ID`, run cancellation, persistence across restarts, CORS.

---

## Slice 11 — evals runner + verifiers + one pass and one fail benchmark

### Goal
Daniel runs `python -m master_finhub.evals.runner src/master_finhub/evals/benchmarks/echo_pass.json` and sees a JSON report with `"pass_rate": 1.0` and exit 0; the same command on `tests/fixtures/evals/echo_fail.json` prints `"pass_rate": 0.0` with the failing expectation's evidence and exits 1.

### Files
| path | new/modified |
|---|---|
| src/master_finhub/evals/__init__.py | new |
| src/master_finhub/evals/runner.py | new |
| src/master_finhub/evals/verifiers.py | new |
| src/master_finhub/evals/benchmarks/echo_pass.json | new (shipped benchmark; must pass) |
| tests/fixtures/evals/echo_fail.json | new (discriminating negative case; must fail) |
| tests/test_evals.py | new |

Placement: the phase table names `evals/runner.py` and `verifiers/`; the template restricts code to `src/master_finhub/**` and `tests/**`, so the package lives at `src/master_finhub/evals/` and `verifiers` is one module (one verifier does not justify a package). The 0-byte stubs at the repo root (`evals/runner.py`, `evals/benchmarks/.gitkeep`, `evals/verifiers/.gitkeep`) are left untouched (see Open question 1). The fail benchmark lives under `tests/` so the shipped suite is green by default.

Benchmark JSON (synthetic):
```json
{
  "name": "echo_pass",
  "task": "echo 42",
  "max_steps": 4,
  "cutoff_s": 30,
  "ground": {
    "files": [],
    "should_contain": ["42"],
    "should_not_contain": ["Error:"],
    "case_sensitive": true,
    "eval": {"type": "contains"}
  }
}
```
`echo_fail.json` is identical except `"name": "echo_fail"`, `"task": "echo 41"`.

### Interfaces
```python
# evals/verifiers.py
@dataclass(frozen=True)
class Expectation:
    text: str          # e.g. 'output contains "42"'
    passed: bool
    evidence: str      # what was actually found, <= 200 chars, never the whole output

@dataclass(frozen=True)
class Grading:
    expectations: tuple[Expectation, ...]
    passed: int
    failed: int
    total: int
    pass_rate: float   # passed / total; 0.0 when total == 0

Verifier = Callable[[str, Mapping[str, Any]], Grading]   # (content, ground) -> Grading

def contains(content: str, ground: Mapping[str, Any]) -> Grading: ...
VERIFIERS: Final[Mapping[str, Verifier]] = {"contains": contains}

# evals/runner.py
@dataclass(frozen=True)
class Benchmark:
    name: str
    task: str
    max_steps: int
    cutoff_s: float
    ground: Mapping[str, Any]
    case_id: str        # explicit "id" or sha256 of the canonical JSON, first 16 hex

@dataclass(frozen=True)
class CaseResult:
    case_id: str
    name: str
    passed: bool
    score: float        # grading.pass_rate
    timed_out: bool
    error: str | None   # exception class + message, no traceback
    steps: int
    duration_s: float
    grading: Grading | None

@dataclass(frozen=True)
class SuiteReport:
    results: tuple[CaseResult, ...]
    passed: int
    failed: int
    total: int
    pass_rate: float

def load_benchmark(path: str | os.PathLike[str]) -> Benchmark: ...   # ValueError naming the bad field
def run_case(bench: Benchmark, llm_factory: Callable[[], LLM] = ScriptedLLM,
             tools_factory: Callable[[Workspace], list[Tool]] = lambda ws: [EchoTool()]) -> CaseResult: ...
    # the per-case Workspace is passed in, so file-writing tools write where ground.files reads (A78)
def run_suite(paths: Sequence[str | os.PathLike[str]], **kw: Any) -> SuiteReport: ...
def main(argv: list[str] | None = None) -> int: ...   # 0 all pass, 1 any fail, 2 load/usage error
```

### Behaviour (claims -> Authority List)
- Benchmark files follow the autogpt classic challenge shape: `name`, `task` and `ground` with `files`, `should_contain`, `should_not_contain`, `eval.type`; `max_steps` and `cutoff_s` are our own fields (A51). Loading is strict: missing/mistyped fields raise `ValueError` naming the field; `eval.type` not in `VERIFIERS` is rejected at load time, so an unreviewed verifier type can never run (A64).
- Each case runs in a fresh `tempfile.mkdtemp(prefix="mf_eval_")` wrapped as `Workspace(root)`, deleted afterwards (A52).
- `run_case` builds `AgentLoop(llm_factory(), tools_factory(workspace), bench.max_steps, context=ContextManager(), guard=guard_tool_call, checkpoint=hook)`. `hook` records the max `snapshot.step` and raises a private `_CutoffReached` when `time.monotonic()` passes `start + cutoff_s` (the loop fails closed on a raising hook), giving `timed_out=True`. Ceiling: one blocking model/tool call can overrun the cutoff; acceptable with fake LLMs.
- Any exception (including `AgentLoopError` on `max_steps`, `_CutoffReached`, verifier errors) becomes a failed `CaseResult` with `score 0.0`; `run_case` never raises, so one crash cannot stop a suite (A53, A61).
- Content to verify = the final answer, followed by each `ground.files` entry read through `Workspace.read_text` (fenced: a `../` file entry is a `SandboxDenied` -> failed case) (A53).
- Dispatch on `ground.eval.type` via `VERIFIERS` (A54). `contains` produces one `Expectation` per `should_contain` (present) and per `should_not_contain` (absent), honouring `case_sensitive` (default True) (A56); result shape is `expectations[text, passed, evidence]` plus `passed/failed/total/pass_rate` (A58).
- `passed = (not timed_out) and error is None and grading.failed == 0`; a timed-out case never passes (A55).
- Verifiers are deterministic string/structure checks only (A59, A63). No verifier executes agent-written code on the host; a future code-running verifier must call slice 8 `DockerEngine.run` and get its own design row (A57).
- The suite needs at least one case that must fail, to prove the verifier discriminates (A60); `echo_fail` is that case.
- `case_id` is the benchmark's explicit `id` or a sha256 of its canonical JSON (A62).
- Duration is captured with `time.monotonic()` at completion (no token metering: the fake LLM has no tokens).

### Touches existing interfaces
- `AgentLoop`, `CheckpointHook`, `LoopSnapshot`, `AgentLoopError`, `LLM`, `Tool` (slice 1); `ContextManager` (slice 2); `guard_tool_call`, `Workspace`, `SandboxDenied` (slice 3); `ScriptedLLM`, `EchoTool`. No existing file changes.
- Does not use slice 8 at runtime (no code-running verifier yet), slice 9 or slice 10.

### Failure modes
| failure | handling |
|---|---|
| malformed benchmark JSON | `load_benchmark` ValueError -> `main` exit 2 with what/why/fix |
| unknown `eval.type` | rejected at load (exit 2), never "falls back" to another verifier |
| agent loops forever | `max_steps` -> `AgentLoopError` -> failed case; wall-clock `cutoff_s` via hook -> `timed_out` |
| file entry escapes workspace | `SandboxDenied` -> failed case, message without the path |
| verifier bug | caught -> failed case with `error` set |

### Proof
Tests to write first:
- `tests/test_evals.py::test_contains_all_present` / `test_contains_forbidden_present` / `test_contains_case_insensitive` — Grading counts and evidence.
- `test_pass_benchmark_passes` — `run_case(load_benchmark(".../echo_pass.json")).passed is True`, `score == 1.0`.
- `test_fail_benchmark_fails` — `echo_fail.json` -> `passed is False`, the failing expectation's text is `output contains "42"` and evidence shows `41`.
- `test_crash_becomes_failed_result` — `llm_factory` whose `complete` raises -> `passed False`, `error` starts with the class name, no exception escapes.
- `test_step_limit_is_failure` — LLM that always calls `echo` -> failed with `AgentLoopError` in `error`.
- `test_cutoff_marks_timed_out` — fake clock / `cutoff_s=0` -> `timed_out True`, `passed False`.
- `test_unknown_eval_type_rejected`, `test_file_entry_outside_workspace_fails`.
- `test_tools_get_case_workspace` — `tools_factory` returns a test tool that writes `out.txt` via the given `Workspace`; a benchmark with `ground.files: ["out.txt"]` passes.
- `test_main_exit_codes` — pass file -> 0, fail file -> 1, missing file -> 2.

Proof command: `python -m master_finhub.evals.runner src/master_finhub/evals/benchmarks/echo_pass.json` -> exit 0, `"pass_rate": 1.0`; `python -m master_finhub.evals.runner tests/fixtures/evals/echo_fail.json` -> exit 1, `"pass_rate": 0.0`; and `pytest tests/test_evals.py -q` -> all pass.

### Dependencies
None (`json`, `hashlib`, `tempfile`, `shutil`, `time`, `argparse`, `dataclasses`). pydantic (autogpt) and rich (crewai) are rejected.

### Ported vs net-new
| part | source | port as |
|---|---|---|
| challenge JSON shape, temp workspace per run, never-raise results, eval-type dispatch, timed-out-never-passes, contains check | autogpt classic direct_benchmark (A51-A56) | adapt (dataclasses, not pydantic) |
| grading schema, objective assertions, need a discriminating fail case, scripted checks | revfactory_harness (A58-A60, A63) | adapt |
| per-case try/except, stable case id | crewai (A61, A62) | adapt (sha256, not md5) |
| reject host exec, fail-closed unknown type, cutoff via checkpoint hook, file placement | — | net-new (A57 consequence, A64, A71) |

### Quant guardrails
Slice 11 scores agent text output against string expectations. It computes no prices, returns, P&L, fills or data splits. Each guardrail is ruled here and has an Authority List row (A65-A70):
- G1 transaction fees — N/A: no trades or returns are computed; the benchmark schema has no price/trade fields.
- G2 borrow costs — N/A: no positions, shorts or leverage exist in this slice.
- G3 slippage — N/A: no fills or signal prices.
- G4 look-ahead leakage — N/A: no time series or features; benchmarks are independent single prompts.
- G5 survivorship bias — N/A: no security universe.
- G6 train/test leakage — N/A: nothing is fitted or tuned on benchmark results; no split exists (the revfactory 60/40 split idea is deferred).
- Forward rule (enforced by A64): because unknown `eval.type` values are rejected at load, a backtest/return-scoring verifier cannot be added by data alone; it requires a code change in `VERIFIERS` plus a new design slice that states G1-G6 with PASS mechanisms and tests (fee default > 0, slippage default > 0, `t-1` signals, point-in-time universe, time-ordered split).

### Out of scope
LLM-judge scoring, parallel/matrix runs, resume state, baseline comparison, report directories per iteration, trigger evals, code-running verifiers (until a slice-8-backed one is designed), real-provider benchmark runs.

---

## Slice 12 — factory (deferred)

Out of scope for this design (YAGNI, phase table row 12). `src/master_finhub/factory/*.py` remain 0-byte stubs; no slice 8-11 code may import them (A72).

---

## Open questions for Daniel

1. **Root-level `evals/` stubs.** `evals/runner.py`, `evals/benchmarks/.gitkeep`, `evals/verifiers/.gitkeep` exist at the repo root, outside the package. This design puts the code in `src/master_finhub/evals/` and leaves the root stubs alone. Delete them, or keep them for something else? Default if no answer: leave them.
2. **Docker on the build machine.** The `docker` CLI is installed but there is no daemon, so the slice 8 container test will be SKIPPED here and only the argv/stream tests prove the slice. If you want the in-container proof to run, start a daemon and `docker pull python:3.12-alpine` once (the engine uses `--pull never`).

---

## Authority List

Every cited line below was opened during this design session. dify rows are pattern only. No row cites `references/autogpt/autogpt_platform/`.

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | Docker availability = daemon info reports OSType `linux`; any exception means unavailable | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:48; :49 | 8 |
| A2 | The workspace is bind-mounted read-write at `/workspace` and `/workspace` is the container working directory | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:489; :493 | 8 |
| A3 | Container name gets a random suffix once per executor instance, so different agents never share a container | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:94 | 8 |
| A4 | Execution timeout is bounded 1-600 seconds with default 120 | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:132 | 8 |
| A5 | Child env = parent env minus names matching `KEY\|PASSWORD\|SECRET\|TOKEN` case-insensitively; explicit env is merged after the scrub | references/deepseek_harness/packages/subprocess/subprocess/src/index.ts:44; :63 | 8 |
| A6 | Captured output keeps the tail: after each push, bytes are dropped from the head while retained > max | references/deepseek_harness/packages/e2b/subprocess-e2b/src/output.ts:103 | 8 |
| A7 | Collected output is reported as text (the tail when truncated) plus a `truncated` flag | references/deepseek_harness/packages/subprocess/subprocess/src/types.ts:22 | 8 |
| A8 | Teardown signals the negative process group and falls back to the direct child, swallowing errors so teardown is idempotent | references/deepseek_harness/packages/subprocess/subprocess-local/src/spawn.ts:304; :309 | 8 |
| A9 | Sandbox profile: read-only root, PID namespace isolation, and only `/tmp` (tmpfs) plus the workspace root writable | references/deepseek_harness/packages/sandbox/sandbox-local/src/profiles.ts:17; :19 | 8 |
| A10 | Producer runs in a worker thread feeding a queue; consumer stops on a `None` sentinel and re-raises an Exception item | references/crewai/lib/crewai/src/crewai/utilities/streaming.py:279; :281 | 8 |
| A11 | Stream frames carry an execution-local order number `seq`, a `type` and `data` | references/crewai/lib/crewai/src/crewai/types/streaming.py:35 | 8 |
| A12 | Kill the container (`docker kill <name>`) when the deadline passes | NET-NEW — the reference docker path runs `exec_run` with no timeout at all (autogpt code_executor.py:512), so it gives no kill-on-timeout behaviour to port; proven by `test_stream_process_timeout_kills_group` | 8 |
| A13 | Hardened `docker run` flags: `--rm`, `--pull never`, `--network none`, `--read-only`, size-capped `/tmp` tmpfs, `--pids-limit`, `--memory`, `--cpus`, `--cap-drop ALL`, `--security-opt no-new-privileges`, non-root `--user` on POSIX; container env only from explicit `-e`; never `--privileged` or the docker socket | NET-NEW — no reference builds docker CLI flags (openhands, crewai, deepseek and dify port maps all record this gap); spec requirement for an execution sandbox; proven by `test_docker_argv_hardening` | 8 |
| A14 | The engine re-runs `check_command(command, policy)` before spawning and raises `CommandBlocked` on denial; the denylist cannot be weakened by any policy | NET-NEW — defence in depth on top of the slice-3 guard (existing code `tools/safety.py` `check_command` applies the denylist before the allowlist); proven by `test_engine_blocks_denied_command` | 8 |
| A15 | Container tests skip cleanly when the docker daemon or image is unavailable | NET-NEW — orchestrator constraint (f); proven by `test_docker_available_false_without_daemon` and the `skipif` on `test_echo_in_container` | 8 |
| A16 | Host side never uses `shell=True`; the command is interpreted only by `sh -c` inside the container | NET-NEW — keeps host-shell injection impossible; proven by argv test asserting the command is the final single element after `sh -c` | 8 |
| A17 | `docker_argv` rejects workspace roots containing `,` `=` newline or NUL, invalid image tags and invalid env names | NET-NEW — `--mount` is comma/equals-delimited, so an unvalidated path could inject mount options; proven by `test_docker_argv_rejects_comma_root` | 8 |
| A18 | Server child is spawned with stdin/stdout/stderr pipes, utf-8 text, line buffering; a daemon reader thread parses one JSON object per line and skips blank or undecodable lines | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:73; :323 | 9 |
| A19 | Child stderr is drained on its own thread into a bounded deque | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:340; :52 | 9 |
| A20 | Responses are routed by id to a per-request one-slot queue; an `error` object becomes a raised JSON-RPC error, otherwise `result` is delivered | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:357; :239 | 9 |
| A21 | Each request has a deadline; on expiry the waiter is removed and `TimeoutError` is raised | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:269 | 9 |
| A22 | On stdout EOF or a reader exception every pending waiter is failed so no caller hangs | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:332; :334 | 9 |
| A23 | Message writes are serialised by a dedicated write lock | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:304 | 9 |
| A24 | Close sequence: close stdin, terminate if still running, wait with a timeout, then kill | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:97; :108 | 9 |
| A25 | Handshake (pattern): send `initialize` with protocol version, capabilities and client info; reject an unsupported server protocol version; then send `notifications/initialized` | references/dify/api/core/mcp/session/client_session.py:143; :147 | 9 |
| A26 | Current MCP protocol version string is `2025-06-18` (protocol constant, pattern) | references/dify/api/core/mcp/types.py:26 | 9 |
| A27 | `tools/list` is paginated: repeat with `cursor` while the response has `nextCursor` | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:173; :74 | 9 |
| A28 | Public tool name is `mcp__<server>__<tool>`; invalid chars become `_`; if changed or over 64 chars it is cut and suffixed with 12 hex chars of SHA-256 of the identity | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:112; :115 | 9 |
| A29 | Tool invocation is a `tools/call` request with `{name, arguments}` and a per-call timeout | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:88; :92 | 9 |
| A30 | An MCP result with `isError: true` is turned into a thrown error so the runtime gives the model an error result | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:344 | 9 |
| A31 | Tool result carrier pairs the text content with the `is_error` flag | references/crewai/lib/crewai/src/crewai/mcp/client.py:45 | 9 |
| A32 | crewai reads only the first content item; this design deliberately joins all text items instead | references/crewai/lib/crewai/src/crewai/mcp/client.py:625 | 9 |
| A33 | Tool filter: a blocked name is excluded even if allowed (block wins) | references/crewai/lib/crewai/src/crewai/mcp/filters.py:82 | 9 |
| A34 | Stdio MCP child env = scrubbed parent env plus the server's explicit env | references/deepseek_harness/packages/mcp/mcp-client/src/transport.ts:22 | 9 |
| A35 | Error text is scrubbed of each configured secret value (values shorter than 4 chars are ignored), then of `Bearer <token>` and generic token shapes | references/openhands/src/utils/redact-mcp-secrets.ts:119; :35 | 9 |
| A36 | (pattern) Listing or calling tools before the session is initialized raises | references/dify/api/core/mcp/mcp_client.py:115 | 9 |
| A37 | (pattern) Cleanup resets session state in `finally` even if closing fails | references/dify/api/core/mcp/mcp_client.py:134 | 9 |
| A38 | The server launch argv is checked with `check_command(shlex.join(command))` before `Popen`; denial refuses to start | NET-NEW — launching an MCP server is a command execution and must meet the same slice-3 floor; proven by `test_denied_launch_command` | 9 |
| A39 | A stdlib stub MCP server in `tests/` (modes: normal, paged, die-on-call, never-answer, bad version, huge-line, endless-pages, ask-client) is the proof fixture | NET-NEW — no reference ships a stdio MCP server; phase-table proof "stub stdio server round-trip" | 9 |
| A40 | (pattern) The event stream emits a ping immediately, before waiting for any message | references/dify/api/core/app/apps/streaming_utils.py:25 | 10 |
| A41 | (pattern) Poll with a 1 s receive timeout; while idle end the stream after `idle_timeout` and emit ping every `ping_interval`; a message resets both timers | references/dify/api/core/app/apps/streaming_utils.py:42; :49 | 10 |
| A42 | (pattern) The stream ends after yielding an event whose type is in the terminal set | references/dify/api/core/app/apps/streaming_utils.py:57 | 10 |
| A43 | (pattern) Defaults: idle timeout 300 s, ping interval 10 s | references/dify/api/core/app/apps/message_generator.py:27; :28 | 10 |
| A44 | (pattern) SSE response uses mimetype `text/event-stream` with `Cache-Control: no-cache` | references/dify/api/controllers/service_api/app/workflow_events.py:174; :176 | 10 |
| A45 | Default bind is `127.0.0.1`; exposing on 0.0.0.0/LAN requires an explicit opt-in flag | references/openhands/scripts/static-server.mjs:244 | 10 |
| A46 | Bind-policy test: loopback connect succeeds and connect via the host's LAN IPv4 is refused | references/openhands/tests/e2e/bind-policy/loopback-bind.spec.ts:144; :150 | 10 |
| A47 | Runtime requests authenticate with an `X-Session-API-Key` header | references/openhands/src/api/bash-service/bash-service.api.ts:36 | 10 |
| A48 | Stdlib `ThreadingHTTPServer` with routes `/health`, `POST /runs` (202 + run id), `GET /runs/<id>/events`; HTTP/1.0 close-delimited stream; one subscriber per run; caps 64 KB body, 4 running, 32 retained | NET-NEW — dify serves SSE via Flask and autogpt classic via FastAPI, both rejected as new dependencies; proven by `test_run_streams_ping_then_events` and the 409/413/429 tests | 10 |
| A49 | Runs execute `AgentLoop` with guard `guard_tool_call` composed first via slice-7 `_both` (`orchestration/modes/subagent.py:111`; extra guard can only add denials); a non-raising `CheckpointHook` emits `snapshot.messages[-1]` as one `message` event per call (compaction-proof, no length-diff); completion queues `done`, exceptions queue `error` with the class name only | NET-NEW — reuses existing slice 1/3/7 interfaces; constraint (h); proven by `test_extra_guard_cannot_weaken` | 10 |
| A50 | Non-loopback `Host` header is refused with 421 unless `allow_remote`, and the session key is compared with `hmac.compare_digest` | NET-NEW — loopback bind alone does not stop DNS-rebinding/cross-origin browser requests to a local agent runner; proven by `test_bad_host_header_421`, `test_missing_key_401` | 10 |
| A51 | Benchmark file shape: `name`, `task`, and `ground` with `eval.type`, `files`, `should_contain`, `should_not_contain` | references/autogpt/classic/direct_benchmark/challenges/verticals/code/0_execute_python/data.json:14; :26 | 11 |
| A52 | Each challenge run gets its own fresh temp workspace via `mkdtemp` | references/autogpt/classic/direct_benchmark/direct_benchmark/runner.py:58 | 11 |
| A53 | Timeout and any exception produce a failed result (success False, score 0.0, timed_out or error message) instead of raising | references/autogpt/classic/direct_benchmark/direct_benchmark/runner.py:88; :106 | 11 |
| A54 | Evaluation dispatches on `ground.eval.type` | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:36 | 11 |
| A55 | A timed-out run never passes even though its score is still recorded | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:64 | 11 |
| A56 | String-match verifier: every `should_contain` phrase present, no `should_not_contain` phrase present, optional case-insensitivity | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:103; :109 | 11 |
| A57 | The reference python verifier executes agent-written files on the host with `sys.executable`; this design forbids that and routes any future code-running verifier through slice 8 `DockerEngine` | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:145 | 11 |
| A58 | Grading schema: `expectations[]` of `text`, `passed`, `evidence` plus `summary` `passed`, `failed`, `total`, `pass_rate` | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:143; :155 | 11 |
| A59 | Good assertions are objectively true/false; assertions that always pass or need subjective judgement are bad | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:123; :128 | 11 |
| A60 | An assertion that passes in both configurations is non-discriminating and must be removed or hardened (hence a must-fail case) | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:137 | 11 |
| A61 | Each case runs inside its own try block so one failing case does not abort the run | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:72 | 11 |
| A62 | Case identifier is the explicit `identifier` or a hash of the case (this design uses sha256 instead of md5) | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:67; :69 | 11 |
| A63 | Assertions that can be checked by code are written as reusable scripts | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:133 | 11 |
| A64 | Unknown `eval.type` is rejected at load time (fail closed); no fallback to another verifier | NET-NEW — deliberate departure from autogpt, which silently falls back to string match for unknown/`llm` types (evaluator.py:50-55); also the gate for quant verifiers; proven by `test_unknown_eval_type_rejected` | 11 |
| A65 | G1 transaction fees: N/A — slice 11 computes no trades or returns; benchmark schema has no price fields | NET-NEW — quant guardrail row (quant-guardrails.md G1); forward rule via A64 | 11 |
| A66 | G2 borrow costs: N/A — no positions, shorts or leverage | NET-NEW — quant guardrail row G2 | 11 |
| A67 | G3 slippage: N/A — no fills or signal prices | NET-NEW — quant guardrail row G3 | 11 |
| A68 | G4 look-ahead: N/A — no time series or features; cases are independent prompts | NET-NEW — quant guardrail row G4 | 11 |
| A69 | G5 survivorship: N/A — no security universe | NET-NEW — quant guardrail row G5 | 11 |
| A70 | G6 train/test leakage: N/A — nothing is fitted or tuned on results; no split built (revfactory 60/40 split deferred) | NET-NEW — quant guardrail row G6 | 11 |
| A71 | Evals live at `src/master_finhub/evals/` (runner.py, verifiers.py, benchmarks/echo_pass.json); the must-fail fixture lives at `tests/fixtures/evals/echo_fail.json`; wall-clock cutoff enforced by a raising checkpoint hook | NET-NEW — slice template restricts files to `src/master_finhub/**` and `tests/**`; keeps the shipped suite green; reuses the existing fail-closed hook contract in `runtime/loop.py` | 11 |
| A72 | Slice 12 (factory) is deferred; no slice 8-11 code imports `factory/*` | NET-NEW — phase table row 12 marks it deferred (YAGNI) | 12 |
| A73 | The reference force-removes and recreates its container on every run; this design adapts that per-run isolation as a fresh `mf_<uuid4 hex[:8]>` name per run plus `--rm` | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:451; :457 | 8 |
| A74 | Stream readers feed a bounded `queue.Queue(maxsize=256)`; every `put` (including the end sentinel) retries with `timeout=0.1` until a shared stop event is set; the generator's `finally` sets stop, kills the process group, closes the pipes and joins the readers | NET-NEW — the crewai queue is unbounded (crewai utilities/streaming.py:213); a bound keeps memory fixed for runaway output, and the stop event prevents readers blocking forever when the consumer abandons a full queue; proven by `test_abandoned_stream_releases_readers` | 8 |
| A75 | The MCP reader uses `readline(MAX_LINE_BYTES + 1)` (4 MB) instead of iterating lines, and a line reaching the limit closes the session with `McpClosed` | NET-NEW — the reference reader (`for line in proc.stdout`, deepseek client.py:323) has no per-line bound; proven by `test_oversize_line_closes_session` | 9 |
| A76 | `tools/list` pagination stops with `McpError` after `MAX_TOOL_PAGES` (20) pages | NET-NEW — the reference loops while `nextCursor` is set with no cap (deepseek tools.ts:173-174); a cap stops a broken server looping forever; proven by `test_endless_pages_capped` | 9 |
| A77 | Server-to-client requests are answered with JSON-RPC error `-32601` and the same id; pending client requests are unaffected | NET-NEW — the client advertises no capabilities, so any server request is unsupported; the reference queues them for an application handler (deepseek client.py:348-351) that this design does not have; proven by `test_server_request_gets_method_not_found` | 9 |
| A78 | Eval `tools_factory` is `Callable[[Workspace], list[Tool]]` and receives the per-case `Workspace`, so file-writing tools and `ground.files` use the same folder | NET-NEW — the reference creates a per-run workspace but its agent wiring is not portable (runner.py:58, :66); proven by `test_file_entry_outside_workspace_fails` plus a test tool that writes `out.txt` read back via `ground.files` (`test_tools_get_case_workspace`) | 11 |
