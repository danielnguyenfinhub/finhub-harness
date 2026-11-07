"""Host-process I/O primitives: scrubbed env, bounded output tail, and a leak-free output stream.

Pattern: thread + queue + sentinel streaming (crewai streaming.py, MIT, re-implemented with a
bounded queue and a stop event), env scrub and tail buffer (deepseek subprocess, adapted),
process-group kill with direct-child fallback (deepseek spawn.ts, adapted). Never uses a shell.
"""

from __future__ import annotations

import codecs
import os
import queue
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import IO, Any, Final, Literal

SENSITIVE_ENV: Final = re.compile(
    r"KEY|PASSWORD|PASSWD|PASSPHRASE|PGPASS|SECRET|TOKEN|AUTH|CREDENTIAL|COOKIE|BEARER|SESSION"
    r"|WEBHOOK|DB_CONN|CONNECTION_?STR|(^|_)(PASS|JWT)($|_)|_(PAT|DSN|URI)$"
    r"|^(SSH_AUTH_SOCK|DATABASE_URL|REDIS_URL|GOOGLE_APPLICATION_CREDENTIALS|KUBECONFIG)$",
    re.IGNORECASE,
)
# a value that carries a password or token, whatever the variable is called
SENSITIVE_VALUE: Final = re.compile(
    r"://[^/\s@:]*:[^/\s@]+@|\bBearer\s+\S{8,}|\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}"
    r"|\bxox[abprs]-[\w-]{10,}|\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}|\bauthorization\s*:",
    re.IGNORECASE,
)
# git takes identity by env name; it is not a secret, so allow before deny
ALLOWED_ENV: Final = re.compile(r"GIT_(AUTHOR|COMMITTER)_(NAME|EMAIL|DATE)")
# config-by-env pairs are kept only when the key is not an auth setting and the value is clean
GIT_PAIR: Final = re.compile(r"GIT_CONFIG_(COUNT|KEY_[0-9]{1,4}|VALUE_[0-9]{1,4})")
GIT_AUTH_KEY: Final = re.compile(
    r"extraheader|^credential|insteadof|password|passwd|token|secret|askpass|sshcommand|proxy",
    re.IGNORECASE,
)
DEFAULT_MAX_OUTPUT_BYTES: Final = 64_000
QUEUE_MAX: Final = 256
READ_SIZE: Final = 65_536
JOIN_TIMEOUT_S: Final = 5.0
ChunkKind = Literal["stdout", "stderr", "exit", "timeout"]


def _git_config_pairs(environ: Mapping[str, str]) -> dict[str, str]:
    """Benign GIT_CONFIG_KEY_n/VALUE_n pairs, renumbered from 0 with a matching COUNT."""
    keep: list[tuple[str, str]] = []
    for name in sorted(environ, key=lambda n: (len(n), n)):
        if name.startswith("GIT_CONFIG_KEY_") and GIT_PAIR.fullmatch(name):
            value = environ.get("GIT_CONFIG_VALUE_" + name.rsplit("_", 1)[1])
            key = environ[name]
            if (
                value is not None
                and not GIT_AUTH_KEY.search(key)
                and not SENSITIVE_VALUE.search(value)
            ):
                keep.append((key, value))
    out = {"GIT_CONFIG_COUNT": str(len(keep))} if keep else {}
    for i, (key, value) in enumerate(keep):
        out[f"GIT_CONFIG_KEY_{i}"] = key
        out[f"GIT_CONFIG_VALUE_{i}"] = value
    return out


def scrubbed_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """os.environ minus secret-looking names and values; explicit ``extra`` wins."""
    env = {
        k: v
        for k, v in os.environ.items()
        if ALLOWED_ENV.fullmatch(k)
        or not (GIT_PAIR.fullmatch(k) or SENSITIVE_ENV.search(k) or SENSITIVE_VALUE.search(v))
    }
    env.update(_git_config_pairs(os.environ))
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True)
class Chunk:
    seq: int
    kind: ChunkKind
    data: str  # "exit": return code as text; "timeout": ""


class TailBuffer:
    """Keeps the last ``max_bytes`` bytes pushed."""

    def __init__(self, max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None:
        self._max = max_bytes
        self._buf = bytearray()
        self._truncated = False

    def push(self, data: bytes) -> None:
        self._buf += data
        if len(self._buf) > self._max:
            del self._buf[: len(self._buf) - self._max]
            self._truncated = True

    def text(self) -> str:
        return bytes(self._buf).decode("utf-8", errors="replace")

    @property
    def truncated(self) -> bool:
        return self._truncated


@dataclass(frozen=True)
class ExecResult:
    exit_code: int | None  # None when killed on timeout
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool


def _kill_group(proc: subprocess.Popen[Any]) -> None:
    """Kill the child's process group; fall back to the direct child. Idempotent."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:  # pragma: no cover - non-POSIX
            proc.kill()
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except (ProcessLookupError, PermissionError):
            pass


def _reader(
    kind: ChunkKind,
    pipe: IO[bytes],
    out: queue.Queue[tuple[ChunkKind, bytes | BaseException | None]],
    stop: threading.Event,
) -> None:
    def put(item: tuple[ChunkKind, bytes | BaseException | None]) -> bool:
        while not stop.is_set():
            try:
                out.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    try:
        while not stop.is_set():
            data = pipe.read1(READ_SIZE)  # type: ignore[attr-defined]
            if not data:
                break
            if not put((kind, data)):
                return
    except BaseException as exc:  # noqa: BLE001 - re-raised by the consumer
        put((kind, exc))
        return
    put((kind, None))


def stream_process(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    timeout_s: float,
    on_timeout: Callable[[], None] | None = None,
    cwd: str | None = None,
) -> Iterator[Chunk]:
    """Run ``argv`` (no shell) and yield output chunks, then ``exit`` or ``timeout``.

    ``cwd`` goes to Popen unchanged: the caller fences it (see ``evals/gates.py``).

    Closing the generator early kills the process group, calls ``on_timeout`` and releases both
    reader threads (daemon threads; pipes closed only once their reader has finished).
    """
    deadline = time.monotonic() + timeout_s
    proc = subprocess.Popen(
        list(argv),
        env=dict(env),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert proc.stdout is not None and proc.stderr is not None
    pipes = {"stdout": proc.stdout, "stderr": proc.stderr}
    stop = threading.Event()
    q: queue.Queue[tuple[ChunkKind, bytes | BaseException | None]] = queue.Queue(QUEUE_MAX)
    readers = [
        threading.Thread(
            target=_reader, args=(k, p, q, stop), name=f"mf-stream-reader-{k}", daemon=True
        )
        for k, p in pipes.items()
    ]
    for t in readers:
        t.start()
    decoders = {k: codecs.getincrementaldecoder("utf-8")(errors="replace") for k in pipes}
    seq = 0
    timeout_called = False
    finished = False
    try:
        open_streams = 2
        while open_streams:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                kind, item = q.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue
            if isinstance(item, BaseException):
                raise item
            if item is None:
                open_streams -= 1
                continue
            text = decoders[kind].decode(item)
            if text:
                yield Chunk(seq, kind, text)
                seq += 1
        else:
            while proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            rc = proc.poll()
            if rc is not None:
                finished = True
                yield Chunk(seq, "exit", str(rc))
                return
        # deadline passed
        timeout_called = True
        if on_timeout is not None:
            on_timeout()
        _kill_group(proc)
        finished = True
        yield Chunk(seq, "timeout", "")
    finally:
        stop.set()
        _kill_group(proc)
        if on_timeout is not None and not finished and not timeout_called:
            try:
                on_timeout()
            except Exception:  # noqa: BLE001, S110 - cleanup must continue
                pass
        try:
            proc.wait(timeout=JOIN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            pass
        join_by = time.monotonic() + JOIN_TIMEOUT_S
        for t in readers:
            t.join(timeout=max(0.0, join_by - time.monotonic()))
        # close() blocks while a reader is inside read1(): only close pipes whose reader is done
        for t, p in zip(readers, pipes.values(), strict=True):
            if not t.is_alive():
                p.close()


def collect(chunks: Iterable[Chunk], max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> ExecResult:
    out, err = TailBuffer(max_bytes), TailBuffer(max_bytes)
    code: int | None = None
    timed_out = False
    for c in chunks:
        if c.kind == "stdout":
            out.push(c.data.encode())
        elif c.kind == "stderr":
            err.push(c.data.encode())
        elif c.kind == "exit":
            code = int(c.data)
        else:
            timed_out = True
    return ExecResult(code, out.text(), err.text(), out.truncated or err.truncated, timed_out)
