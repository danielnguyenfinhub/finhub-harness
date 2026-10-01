"""Checkpoint store for one AgentLoop run: one immutable JSON file per save, resume on demand.

Design: _workspace/02_strategy-architect_slice5.md (revision 3). Ideas adapted (MIT, own code)
from deepseek-harness: storage-json atomic.ts:25-37 (same-folder temp, fsync, publish),
session-persistence-jsonl index.ts:544-549 (no-clobber publish) and win32.ts:4-9
(MoveFileExW write-through), session-checkpoint-policy index.ts:52-58 (checkpoint before the
tool body, fail closed).

Every message is three lines (what failed / why / fix) built only from fixed phrases, a
validated run id, integers, a tool name or a Python type name: never checkpoint content.
Every raise is ``from None`` so no traceback can carry a document or an absolute path.

Clip note: tool results are saved through the same ``clip_text`` and budget that
``ContextManager.fit`` applies before each model call. A resumed run therefore sends the model
exactly what an uninterrupted run would, PROVIDED the loop's ContextManager uses the same
``clip_budget_tokens``. A loop with no context policy would see clipped output after a resume
where the uninterrupted run saw raw output; that is the caller's choice.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Final, Literal, Self

from master_finhub.orchestration._fsio import (
    PublishFailure,
    _quiet_unlink,
    _try_lock,
    _unlock,
    attempt,
    publish,
    stage,
)
from master_finhub.runtime.context import CLIP_BUDGET_TOKENS, clip_text
from master_finhub.runtime.loop import LoopSnapshot, Message, ToolCall
from master_finhub.sandbox.workspace import RESERVED, SandboxDenied, Workspace

SCHEMA_VERSION: Final = 1
CHECKPOINT_DIRNAME: Final = ".checkpoints"
RUN_ID_PATTERN: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")  # fullmatch only
STEP_FILE_PATTERN: Final = re.compile(r"step-([0-9]{6})\.json")  # fullmatch only; ASCII digits
PARENT_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}@[0-9]{1,6}")
SURROGATE: Final = re.compile("[\ud800-\udfff]")
MAX_SEQ: Final = 999_999
MAX_JSON_DEPTH: Final = 64
MAX_CHECKPOINT_BYTES: Final = 8 * 1024 * 1024  # exact FILE bytes: save checks len, load st_size
MAX_META_KEYS: Final = 16
MAX_META_CHARS: Final = 200
OWNER_LOCK_NAME: Final = ".owner"
_STATE_KEYS: Final = frozenset(
    {"messages", "meta", "parent", "run_id", "saved_at", "seq", "status", "step"}
)
_MESSAGE_KEYS: Final = frozenset({"role", "content", "tool_calls", "tool_call_id"})
_CALL_KEYS: Final = frozenset({"id", "name", "arguments"})
_ROLES: Final[dict[str, Literal["user", "assistant", "tool"]]] = {
    "user": "user",
    "assistant": "assistant",
    "tool": "tool",
}

Clock = Callable[[], datetime]  # must return an aware datetime


class CheckpointError(RuntimeError):
    """Three-line message: what failed / why / exact fix. Never contains checkpoint content."""

    def __init__(
        self,
        what: str,
        why: str,
        fix: str,
        *,
        run_id: str | None = None,
        seq: int | None = None,
    ) -> None:
        super().__init__(f"{what}\n{why}\n{fix}")
        self.run_id = run_id
        self.seq = seq


@dataclass(frozen=True)
class Checkpoint:
    run_id: str
    seq: int  # file sequence number (0, 1, 2, ... contiguous)
    saved_at: datetime  # aware
    snapshot: LoopSnapshot
    parent: str | None = None  # "run_id@seq" when forked from another run (time travel)
    meta: Mapping[str, str] = field(default_factory=dict)


def local_now() -> datetime:
    return datetime.now().astimezone()


def new_run_id(clock: Clock = local_now) -> str:
    return f"run-{clock():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def validate_run_id(run_id: str) -> str:
    """Return the id lower-cased, or raise without echoing it. Runs before any path join."""
    if (
        not isinstance(run_id, str)
        or RUN_ID_PATTERN.fullmatch(run_id) is None
        or run_id.casefold() in RESERVED
    ):
        raise CheckpointError(
            "The run name you gave is not allowed.",
            "Run names use letters, digits, - and _ only, up to 64 characters.",
            "Pick a different name, for example loan-review-01.",
        ) from None
    return run_id.lower()


# ----------------------------------------------------------------------------- error builders
def _label(run_id: str, seq: int) -> str:
    return f'Step file {seq} of run "{run_id}"'


def _restore_fix(seq: int) -> str:
    if seq > 0:
        return f"Restore the file, or time-travel from step {seq - 1} into a new run."
    return "Restore the file, or start a new run."


def _file_error(run_id: str, seq: int, problem: str, why: str) -> CheckpointError:
    return CheckpointError(
        f"{_label(run_id, seq)} {problem}.", why, _restore_fix(seq), run_id=run_id, seq=seq
    )


def _unreadable(run_id: str, seq: int) -> CheckpointError:
    return _file_error(
        run_id, seq, "is unreadable (not valid JSON)", "The file is damaged or was cut short."
    )


def _malformed(run_id: str, seq: int, what: str) -> CheckpointError:
    return _file_error(
        run_id, seq, f"is malformed ({what})", "Its contents do not match the checkpoint layout."
    )


def _bad_value(run_id: str, seq: int, where: str, kind: str) -> CheckpointError:
    return CheckpointError(
        f'Run "{run_id}" step {seq} cannot be saved: {where} holds {kind}.',
        "Checkpoints store plain JSON only, and nothing is changed or guessed.",
        "Make the value plain text, numbers, lists and objects, then run again.",
        run_id=run_id,
        seq=seq,
    )


# ----------------------------------------------------------------------------- serialiser
def _walk(value: object, depth: int, where: str, run_id: str, seq: int) -> None:
    """Strict JSON check: raise on anything json would silently coerce or fail on."""
    if depth > MAX_JSON_DEPTH:
        raise _bad_value(run_id, seq, where, "nesting deeper than 64") from None
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind is int:
        _, too_long = attempt(lambda: str(value), (ValueError,))
        if too_long is not None:
            raise _bad_value(run_id, seq, where, "a number with too many digits") from None
    elif kind is float:
        assert isinstance(value, float)
        if not math.isfinite(value):
            raise _bad_value(run_id, seq, where, "a number that is not finite") from None
    elif kind is str:
        assert isinstance(value, str)
        if SURROGATE.search(value):
            raise _bad_value(run_id, seq, where, "text with an unpaired surrogate") from None
    elif kind is list:
        assert isinstance(value, list)
        for item in value:
            _walk(item, depth + 1, where, run_id, seq)
    elif kind is dict:
        assert isinstance(value, dict)
        for key, item in value.items():
            if type(key) is not str:
                raise _bad_value(
                    run_id, seq, where, f"a key of type {type(key).__name__}"
                ) from None
            _walk(key, depth + 1, where, run_id, seq)
            _walk(item, depth + 1, where, run_id, seq)
    else:
        raise _bad_value(run_id, seq, where, f"a value of type {kind.__name__}") from None


def snapshot_to_state(cp: Checkpoint) -> dict[str, object]:
    """Strict: raises CheckpointError on anything that is not plain JSON."""
    rid, seq = cp.run_id, cp.seq
    if cp.saved_at.utcoffset() is None:
        raise CheckpointError(
            f'Run "{rid}" step {seq} cannot be saved: the clock gave a time without an offset.',
            "Checkpoint times must say AEST or AEDT explicitly (for example +10:00).",
            "Pass a clock that returns an aware datetime.",
            run_id=rid,
            seq=seq,
        ) from None
    messages: list[dict[str, object]] = []
    for i, m in enumerate(cp.snapshot.messages):
        calls: list[dict[str, object]] = []
        _walk(m.content, 1, f"message {i}", rid, seq)
        for j, c in enumerate(m.tool_calls):
            where = f"message {i}, call {j}"
            _walk([c.id, c.name, c.arguments], 1, where, rid, seq)
            calls.append({"id": c.id, "name": c.name, "arguments": c.arguments})
        _walk(m.tool_call_id, 1, f"message {i}", rid, seq)
        messages.append(
            {
                "role": m.role,
                "content": m.content,
                "tool_calls": calls,
                "tool_call_id": m.tool_call_id,
            }
        )
    meta_ok = all(type(k) is str and type(v) is str for k, v in cp.meta.items())
    if (
        not meta_ok
        or len(cp.meta) > MAX_META_KEYS
        or any(len(k) > MAX_META_CHARS or len(v) > MAX_META_CHARS for k, v in cp.meta.items())
    ):
        raise _bad_value(rid, seq, "the run labels", "more than 16 labels or labels over 200 chars")
    _walk(cp.parent, 1, "the parent", rid, seq)
    return {
        "messages": messages,
        "meta": dict(cp.meta),
        "parent": cp.parent,
        "run_id": rid,
        "saved_at": cp.saved_at.isoformat(timespec="seconds"),
        "seq": seq,
        "status": cp.snapshot.status,
        "step": cp.snapshot.step,
    }


def _dumps(obj: object, *, pretty: bool) -> bytes | None:
    """UTF-8 JSON bytes, or None when json cannot store the value (no exception escapes)."""

    def go() -> bytes:
        if pretty:
            text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        else:
            text = json.dumps(
                obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            )
        return text.encode("utf-8")

    return attempt(go, (ValueError, RecursionError))[0]


def _checksum(state: object, version: object) -> str | None:
    canonical = _dumps({"schema_version": version, "state": state}, pretty=False)
    return None if canonical is None else "sha256:" + hashlib.sha256(canonical).hexdigest()


def encode_checkpoint(cp: Checkpoint) -> bytes:
    """The exact bytes of the step file; refuses over MAX_CHECKPOINT_BYTES (measured here)."""
    state = snapshot_to_state(cp)
    checksum = _checksum(state, SCHEMA_VERSION)
    envelope = {"checksum": checksum, "schema_version": SCHEMA_VERSION, "state": state}
    data = None if checksum is None else _dumps(envelope, pretty=True)
    if data is None:
        raise _bad_value(cp.run_id, cp.seq, "the state", "a value JSON cannot store") from None
    if len(data) > MAX_CHECKPOINT_BYTES:
        raise CheckpointError(
            f'Run "{cp.run_id}" step {cp.seq} is too large to save (over 8 MiB).',
            "The conversation grew past the checkpoint limit.",
            "Lower max_steps or use a context policy; the run has stopped.",
            run_id=cp.run_id,
            seq=cp.seq,
        ) from None
    return data


# ----------------------------------------------------------------------------- loader helpers
def _need(ok: bool, run_id: str, seq: int, what: str) -> None:
    if not ok:
        raise _malformed(run_id, seq, what) from None


def _parse_call(raw: object, run_id: str, seq: int) -> ToolCall:
    _need(isinstance(raw, dict) and set(raw) == _CALL_KEYS, run_id, seq, "tool_calls")
    assert isinstance(raw, dict)
    ok = isinstance(raw["id"], str) and isinstance(raw["name"], str)
    _need(ok and isinstance(raw["arguments"], dict), run_id, seq, "tool_calls")
    return ToolCall(raw["id"], raw["name"], raw["arguments"])


def _parse_message(raw: object, run_id: str, seq: int) -> Message:
    _need(isinstance(raw, dict) and set(raw) == _MESSAGE_KEYS, run_id, seq, "messages")
    assert isinstance(raw, dict)
    role = _ROLES.get(raw["role"]) if isinstance(raw["role"], str) else None
    _need(role is not None and isinstance(raw["content"], str), run_id, seq, "messages")
    _need(isinstance(raw["tool_calls"], list), run_id, seq, "tool_calls")
    tcid = raw["tool_call_id"]
    _need(tcid is None or isinstance(tcid, str), run_id, seq, "tool_call_id")
    assert role is not None
    calls = tuple(_parse_call(c, run_id, seq) for c in raw["tool_calls"])
    return Message(role, raw["content"], calls, tcid)


def _parse_saved_at(raw: object, run_id: str, seq: int) -> datetime:
    _need(isinstance(raw, str), run_id, seq, "saved_at")
    assert isinstance(raw, str)
    when, bad = attempt(lambda: datetime.fromisoformat(raw), (ValueError,))
    if bad is not None or when is None:
        raise _malformed(run_id, seq, "saved_at") from None
    _need(when.utcoffset() is not None, run_id, seq, "saved_at")
    return when


def _parse_meta(raw: object, run_id: str, seq: int) -> dict[str, str]:
    ok = isinstance(raw, dict) and len(raw) <= MAX_META_KEYS
    _need(ok, run_id, seq, "meta")
    assert isinstance(raw, dict)
    for k, v in raw.items():
        _need(isinstance(k, str) and isinstance(v, str), run_id, seq, "meta")
        _need(len(k) <= MAX_META_CHARS and len(v) <= MAX_META_CHARS, run_id, seq, "meta")
    return dict(raw)


def state_to_checkpoint(state: object, *, run_id: str, seq: int) -> Checkpoint:
    """Strict shape check; run_id and seq come from the folder and file name."""
    _need(isinstance(state, dict) and set(state) == _STATE_KEYS, run_id, seq, "state")
    assert isinstance(state, dict)
    if state["run_id"] != run_id:
        raise _file_error(
            run_id, seq, "belongs to a different run", "A file was copied between runs."
        ) from None
    if type(state["seq"]) is not int or state["seq"] != seq:
        found = state["seq"] if type(state["seq"]) is int else "?"
        raise _file_error(
            run_id, seq, f"is out of place (says step {found}, file is {seq})", "It was renamed."
        ) from None
    _need(type(state["step"]) is int and state["step"] >= 0, run_id, seq, "step")
    _need(isinstance(state["messages"], list), run_id, seq, "messages")
    parent = state["parent"]
    ok = parent is None or (isinstance(parent, str) and PARENT_PATTERN.fullmatch(parent))
    _need(bool(ok), run_id, seq, "parent")
    messages = tuple(_parse_message(m, run_id, seq) for m in state["messages"])
    snapshot, bad = attempt(lambda: LoopSnapshot(state["step"], messages), (ValueError,))
    if bad is not None or snapshot is None:
        raise _malformed(run_id, seq, "messages") from None
    _need(state["status"] == snapshot.status, run_id, seq, "status")
    return Checkpoint(
        run_id,
        seq,
        _parse_saved_at(state["saved_at"], run_id, seq),
        snapshot,
        parent,
        _parse_meta(state["meta"], run_id, seq),
    )


def _reject_constant(name: str) -> Any:
    raise ValueError("NaN or Infinity literal")


def _ranges(seqs: list[int]) -> str:
    parts: list[str] = []
    start = prev = seqs[0]
    for n in [*seqs[1:], None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        if n is not None:
            start = prev = n
    return ", ".join(parts)


# ----------------------------------------------------------------------------- the store
class RunWriter:
    """Satisfies CheckpointHook: publishes the next seq (no-clobber). Holds the owner lock."""

    def __init__(
        self,
        store: CheckpointStore,
        run_id: str,
        next_seq: int,
        parent: str | None,
        meta: Mapping[str, str],
        lock_fd: int,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._next = next_seq
        self._parent = parent
        self._meta = dict(meta)
        self._fd: int | None = lock_fd

    def __call__(self, snapshot: LoopSnapshot) -> None:
        seq = self._next
        if seq > MAX_SEQ:
            raise CheckpointError(
                f'Run "{self._run_id}" has reached the limit of {MAX_SEQ + 1} saved steps.',
                "Step files are numbered with six digits.",
                "Start a new run, or fork this one with a new --run-id.",
                run_id=self._run_id,
                seq=seq,
            ) from None
        budget = self._store.clip_budget_tokens
        clipped = tuple(
            replace(m, content=clip_text(m.content, budget)) if m.role == "tool" else m
            for m in snapshot.messages
        )
        cp = Checkpoint(
            self._run_id,
            seq,
            self._store.clock(),
            LoopSnapshot(snapshot.step, clipped),
            self._parent,
            self._meta,
        )
        self._store.write(cp)
        self._next += 1

    def close(self) -> None:
        if self._fd is not None:
            _unlock(self._fd)
            self._fd = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class CheckpointStore:
    """Reads and writes checkpoints under ``<workspace>/.checkpoints/<run_id>/``.

    See the module docstring for the clip-budget caveat.
    """

    def __init__(
        self,
        workspace: Workspace,
        *,
        clock: Clock = local_now,
        clip_budget_tokens: int = CLIP_BUDGET_TOKENS,
    ) -> None:
        self._ws = workspace
        self.clock = clock
        self.clip_budget_tokens = clip_budget_tokens

    # -- fenced paths
    def _path(self, rel: str, mode: Literal["read", "write"], run_id: str | None) -> Path:
        check = self._ws.check_write if mode == "write" else self._ws.check_read
        path, denied = attempt(lambda: check(rel), (SandboxDenied,))
        if denied is not None or path is None:
            raise CheckpointError(
                "A checkpoint path is outside the workspace.",
                "Checkpoints may only live inside the workspace folder.",
                "Check MASTER_FINHUB_WORKSPACE and remove any link that points elsewhere.",
                run_id=run_id,
            ) from None
        return path

    def _run_rel(self, run_id: str) -> str:
        return f"{CHECKPOINT_DIRNAME}/{run_id}"

    # -- public API
    def create_run(
        self,
        run_id: str,
        *,
        parent: Checkpoint | None = None,
        meta: Mapping[str, str] | None = None,
    ) -> RunWriter:
        rid = validate_run_id(run_id)
        base = self._path(CHECKPOINT_DIRNAME, "write", rid)
        self._ensure_dir(base, exist_ok=True, rid=rid)
        self._write_gitignore(base)
        self._ensure_dir(self._path(self._run_rel(rid), "write", rid), exist_ok=False, rid=rid)
        fd = self._lock(rid)
        label = None if parent is None else f"{parent.run_id}@{parent.seq}"
        return RunWriter(self, rid, 0, label, meta or {}, fd)

    def resume_run(self, run_id: str) -> tuple[Checkpoint, RunWriter]:
        rid = validate_run_id(run_id)
        if not self._path(self._run_rel(rid), "write", rid).is_dir():
            raise self._not_found(rid) from None
        fd = self._lock(rid)
        handed_over = False
        try:
            cp = self.load(rid)
            handed_over = True
        finally:
            if not handed_over:
                _unlock(fd)
        return cp, RunWriter(self, rid, cp.seq + 1, cp.parent, cp.meta, fd)

    def list_seqs(self, run_id: str) -> list[int]:
        rid = validate_run_id(run_id)
        folder = self._path(self._run_rel(rid), "read", rid)
        names, failed = attempt(lambda: [e.name for e in os.scandir(folder)], (OSError,))
        if failed is not None or names is None:
            missing = failed is not None and issubclass(
                failed[0], (FileNotFoundError, NotADirectoryError)
            )
            raise (self._not_found(rid) if missing else _bad_listing(rid)) from None
        seqs: list[int] = []
        for name in names:
            match = STEP_FILE_PATTERN.fullmatch(name)
            if match:
                seqs.append(int(match.group(1)))
            elif name.startswith("step-"):
                raise CheckpointError(
                    f'Run "{rid}" has an unexpected file in its folder.',
                    "Something other than this program put it there.",
                    "Move that file out of the run folder.",
                    run_id=rid,
                ) from None
        seqs.sort()
        if not seqs:
            raise CheckpointError(
                f'Run "{rid}" has no saved steps.',
                "It was created but nothing was saved.",
                "Start a new run; this folder can be deleted by hand.",
                run_id=rid,
            ) from None
        for i, n in enumerate(seqs):
            if n != i:
                raise CheckpointError(
                    f'Run "{rid}" is missing step file {i} (found {_ranges(seqs)}).',
                    "A file was deleted or moved.",
                    f"Restore the file, or time-travel from step {max(i - 1, 0)} into a new run.",
                    run_id=rid,
                    seq=i,
                ) from None
        return seqs

    def load(self, run_id: str, seq: int | None = None) -> Checkpoint:
        """Latest checkpoint, or any seq (read-only time travel). No fallback, ever."""
        rid = validate_run_id(run_id)
        seqs = self.list_seqs(rid)
        n = seqs[-1] if seq is None else seq
        if n not in seqs:
            raise CheckpointError(
                f'Run "{rid}" has no step file {n} (found {_ranges(seqs)}).',
                "That step was never saved.",
                f"Pick a step between 0 and {seqs[-1]}.",
                run_id=rid,
            ) from None
        path = self._path(f"{self._run_rel(rid)}/step-{n:06d}.json", "read", rid)
        stat, failed = attempt(path.stat, (OSError,))
        if failed is not None or stat is None:
            raise _unreadable(rid, n) from None
        if stat.st_size > MAX_CHECKPOINT_BYTES:
            raise _file_error(
                rid, n, "is too large to load", "It is bigger than any file this program writes."
            ) from None

        def read() -> object:
            data = path.read_bytes()
            return json.loads(data.decode("utf-8"), parse_constant=_reject_constant)

        # UnicodeDecodeError and JSONDecodeError are ValueErrors; both carry the document.
        obj, failed = attempt(read, (OSError, ValueError, RecursionError))
        if failed is not None:
            raise _unreadable(rid, n) from None
        return self._open_envelope(obj, rid, n)

    # -- internals
    def _open_envelope(self, obj: object, rid: str, n: int) -> Checkpoint:
        if not isinstance(obj, dict) or set(obj) != {"checksum", "schema_version", "state"}:
            raise _malformed(rid, n, "unexpected layout") from None
        version = obj["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            shown = version if type(version) is int else "unknown"
            raise _file_error(
                rid,
                n,
                f"was written by a different version (schema {shown}; this build reads "
                f"{SCHEMA_VERSION})",
                "The file layout changed between versions.",
            ) from None
        expected = _checksum(obj["state"], version)
        if expected is None:
            raise _unreadable(rid, n) from None
        if obj["checksum"] != expected:
            raise _file_error(
                rid, n, "failed its integrity check", "The content changed after it was saved."
            ) from None
        return state_to_checkpoint(obj["state"], run_id=rid, seq=n)

    def write(self, cp: Checkpoint) -> None:
        """Publish one checkpoint: temp file, fsync, durable no-clobber publish, cleanup."""
        rid, seq = cp.run_id, cp.seq
        data = encode_checkpoint(cp)
        run_dir = self._path(self._run_rel(rid), "write", rid)
        final = self._path(f"{self._run_rel(rid)}/step-{seq:06d}.json", "write", rid)
        tmp, failed = attempt(lambda: stage(run_dir, data), (OSError,))
        if failed is not None or tmp is None:
            raise CheckpointError(
                f'Run "{rid}" step {seq} could not be saved.',
                f"The disk refused the write (error {failed[1] if failed else 0}).",
                f"Check free space and folder permissions in the workspace, then --resume {rid}.",
                run_id=rid,
                seq=seq,
            ) from None
        refused = publish(os.fspath(tmp), os.fspath(final))
        if refused is not None:
            _quiet_unlink(tmp)
            raise _publish_error(refused, rid, seq) from None

    def _ensure_dir(self, path: Path, *, exist_ok: bool, rid: str) -> None:
        _, failed = attempt(lambda: path.mkdir(mode=0o700, exist_ok=exist_ok), (OSError,))
        if failed is None:
            return
        if issubclass(failed[0], FileExistsError):
            raise CheckpointError(
                f'Run "{rid}" already exists.',
                "A run with that name was saved before.",
                f"Use --resume {rid}, or pick a new name.",
                run_id=rid,
            ) from None
        raise _bad_listing(rid) from None

    def _write_gitignore(self, base: Path) -> None:
        def create() -> None:
            with open(base / ".gitignore", "x", encoding="utf-8") as fh:
                fh.write("*\n")

        _, failed = attempt(create, (OSError,))
        if failed is not None and not issubclass(failed[0], FileExistsError):
            raise _bad_listing(None) from None

    def _lock(self, rid: str) -> int:
        owner = self._path(f"{self._run_rel(rid)}/{OWNER_LOCK_NAME}", "write", rid)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        fd, failed = attempt(lambda: os.open(owner, flags, 0o600), (OSError,))
        if failed is not None or fd is None:
            raise CheckpointError(
                f'Cannot open the lock file of run "{rid}".',
                "The file is read-only or access was denied.",
                f"Clear the read-only flag on {rid}/{OWNER_LOCK_NAME}, then --resume {rid}.",
                run_id=rid,
            ) from None
        _, taken = attempt(lambda: _try_lock(fd), (OSError,))
        if taken is not None:
            os.close(fd)
            raise CheckpointError(
                f'Run "{rid}" is still running in another process.',
                "Only one process may write a run at a time.",
                f"Wait for it to finish or stop it, then --resume {rid}.",
                run_id=rid,
            ) from None
        return fd

    def _not_found(self, rid: str) -> CheckpointError:
        return CheckpointError(
            f'Run "{rid}" not found.',
            "There are no saved steps under the checkpoint folder.",
            "Check the name, or start a new run with --run-id.",
            run_id=rid,
        )


def _bad_listing(rid: str | None) -> CheckpointError:
    return CheckpointError(
        "The checkpoint folder could not be used.",
        "The disk or folder permissions refused the request.",
        "Check that MASTER_FINHUB_WORKSPACE is writable, then try again.",
        run_id=rid,
    )


def _publish_error(exc: PublishFailure, rid: str, seq: int) -> CheckpointError:
    if exc.kind == "exists":
        return CheckpointError(
            f'Another process is writing run "{rid}" (step file {seq} already exists).',
            "Two writers tried to save the same step; the first one keeps it.",
            f"Stop the other process, then --resume {rid}.",
            run_id=rid,
            seq=seq,
        )
    if exc.kind == "busy":
        return CheckpointError(
            "Another program (possibly antivirus) is holding a checkpoint file.",
            f"Windows refused the save (error {exc.code}).",
            f"Close that program or exclude the workspace folder from scanning, "
            f"then --resume {rid}.",
            run_id=rid,
            seq=seq,
        )
    if sys.platform == "win32" and exc.code == 0:
        return CheckpointError(
            "This machine cannot store checkpoints safely (the Windows safe-save call failed).",
            "Saving needs MoveFileExW with write-through, and it could not be used.",
            "Use a standard Windows Python install, then --resume " + rid + ".",
            run_id=rid,
            seq=seq,
        )
    code = f" (Windows error {exc.code})" if exc.code and sys.platform == "win32" else ""
    return CheckpointError(
        f"This drive cannot store checkpoints safely{code}.",
        "The checkpoint folder is on a drive that does not support safe saves.",
        "Move MASTER_FINHUB_WORKSPACE to a local NTFS drive.",
        run_id=rid,
        seq=seq,
    )
