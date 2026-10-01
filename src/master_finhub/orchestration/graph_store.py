"""Graph checkpoint files (schema 2) for the deterministic graph executor.

Design: _workspace/02_strategy-architect_slice6.md (revision 2). Same run-folder layout, owner
lock, fence, temp+fsync+no-clobber publish, 8 MiB cap and strict loader as slice 5, reused from
``dag_engine``/``_fsio``; the file series is ``graph-NNNNNN.json`` so slice 5's step files (schema
1) and their loader are untouched. Every message is three lines built from fixed phrases, run ids,
node ids and integers: never a node input or output. Every raise is ``from None``.

The owner lock outlives the run while an abandoned node thread is still alive: ``node_started`` /
``node_ended`` keep a process-wide set of live nodes, and the lock descriptor is released exactly
once, under one lock, by whichever of ``close`` and the last ``node_ended`` comes second.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import TracebackType
from typing import Final, Literal, Self

from master_finhub.orchestration._fsio import _quiet_unlink, _unlock, attempt, publish, stage
from master_finhub.orchestration.dag_engine import (
    CHECKPOINT_DIRNAME,
    MAX_CHECKPOINT_BYTES,
    MAX_SEQ,
    STEP_FILE_PATTERN,
    CheckpointStore,
    Clock,
    _bad_listing,
    _checksum,
    _dumps,
    _publish_error,
    _ranges,
    _reject_constant,
    _walk,
    validate_run_id,
)

GRAPH_SCHEMA_VERSION: Final = 2
GRAPH_FILE_PATTERN: Final = re.compile(r"graph-([0-9]{6})\.json")  # fullmatch only; ASCII digits
NODE_ID_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,31}")  # fullmatch only
HASH_PATTERN: Final = re.compile(r"sha256:[0-9a-f]{64}")
NodeStatus = Literal["pending", "running", "done", "failed", "skipped"]
RunStatus = Literal["done", "failed", "halted"]
HaltReason = Literal["step_limit", "deadline", "interrupted"]
SavedStatus = Literal["running", "done", "failed", "halted"]
_NODE_STATUSES: Final = ("pending", "running", "done", "failed", "skipped")
_SAVED_STATUSES: Final = ("running", "done", "failed", "halted")
_HALT_REASONS: Final = ("step_limit", "deadline", "interrupted")
_STATE_KEYS: Final = frozenset(
    {"graph_hash", "halt_reason", "inputs", "nodes", "run_id", "saved_at", "seq", "status"}
)
_NODE_KEYS: Final = frozenset({"error_type", "output", "status"})

# Process-wide live node registry: run folder (memory only, never logged) -> node ids running.
_LIVE_LOCK = threading.Lock()
_LIVE: dict[str, set[str]] = {}


class GraphError(RuntimeError):
    """Three lines: what failed / why / exact fix. Contains run and node ids and counts only."""

    def __init__(self, what: str, why: str, fix: str, *, node_ids: tuple[str, ...] = ()) -> None:
        super().__init__(f"{what}\n{why}\n{fix}")
        self.node_ids = node_ids


class GraphResumeBlocked(GraphError):
    """A resume was refused before any write."""


@dataclass(frozen=True)
class NodeRecord:
    status: NodeStatus
    output: str | None = None  # non-None iff status == "done"
    error_type: str | None = None  # non-None iff status == "failed"


@dataclass(frozen=True)
class GraphCheckpoint:
    run_id: str
    seq: int
    saved_at: datetime  # aware
    graph_hash: str
    status: SavedStatus
    halt_reason: HaltReason | None
    inputs: Mapping[str, str]
    nodes: Mapping[str, NodeRecord]


# ----------------------------------------------------------------------------- encode
def _state(cp: GraphCheckpoint) -> dict[str, object]:
    rid, seq = cp.run_id, cp.seq
    nodes = {
        k: {"error_type": v.error_type, "output": v.output, "status": v.status}
        for k, v in cp.nodes.items()
    }
    _walk([dict(cp.inputs), nodes], 1, "the graph state", rid, seq)
    return {
        "graph_hash": cp.graph_hash,
        "halt_reason": cp.halt_reason,
        "inputs": dict(cp.inputs),
        "nodes": nodes,
        "run_id": rid,
        "saved_at": cp.saved_at.isoformat(timespec="seconds"),
        "seq": seq,
        "status": cp.status,
    }


def encode_graph_checkpoint(cp: GraphCheckpoint) -> bytes:
    """The exact bytes of the graph file; refuses over MAX_CHECKPOINT_BYTES (a backstop)."""
    state = _state(cp)
    checksum = _checksum(state, GRAPH_SCHEMA_VERSION)
    envelope = {"checksum": checksum, "schema_version": GRAPH_SCHEMA_VERSION, "state": state}
    data = None if checksum is None else _dumps(envelope, pretty=True)
    if data is None or len(data) > MAX_CHECKPOINT_BYTES:
        raise GraphError(
            f'Run "{cp.run_id}" step file {cp.seq} cannot be saved (too large or not plain text).',
            "A run keeps every step's output in one checkpoint file of at most 8 MiB.",
            "Make the steps return less (for example a summary), then start a new run.",
        ) from None
    return data


# ----------------------------------------------------------------------------- decode
def _bad(rid: str, seq: int, problem: str, why: str) -> GraphError:
    return GraphError(
        f'Graph file {seq} of run "{rid}" {problem}.',
        why,
        "Restore the file, or start a new run.",
    )


def _malformed(rid: str, seq: int, what: str) -> GraphError:
    return _bad(rid, seq, f"is malformed ({what})", "Its contents do not match the layout.")


def _parse_node(raw: object, rid: str, seq: int) -> NodeRecord:
    if not isinstance(raw, dict) or set(raw) != _NODE_KEYS:
        raise _malformed(rid, seq, "nodes") from None
    status, output, error = raw["status"], raw["output"], raw["error_type"]
    ok = isinstance(status, str) and status in _NODE_STATUSES
    ok = ok and (output is None or isinstance(output, str))
    ok = ok and (error is None or isinstance(error, str))
    ok = ok and (output is not None) == (status == "done")
    ok = ok and (error is not None) == (status == "failed")
    if not ok:
        raise _malformed(rid, seq, "nodes") from None
    assert isinstance(status, str)
    return NodeRecord(status, output, error)  # type: ignore[arg-type]


def _parse_state(state: object, rid: str, seq: int) -> GraphCheckpoint:
    if not isinstance(state, dict) or set(state) != _STATE_KEYS:
        raise _malformed(rid, seq, "state") from None
    if state["run_id"] != rid:
        raise _bad(
            rid, seq, "belongs to a different run", "A file was copied between runs."
        ) from None
    if type(state["seq"]) is not int or state["seq"] != seq:
        raise _bad(rid, seq, "is out of place", "It was renamed.") from None
    inputs, nodes, status, reason = (state[k] for k in ("inputs", "nodes", "status", "halt_reason"))
    ok = isinstance(inputs, dict) and isinstance(nodes, dict)
    ok = (
        ok
        and isinstance(state["graph_hash"], str)
        and bool(HASH_PATTERN.fullmatch(state["graph_hash"]))
    )
    ok = ok and isinstance(status, str) and status in _SAVED_STATUSES
    ok = ok and (reason is None or (isinstance(reason, str) and reason in _HALT_REASONS))
    ok = ok and (reason is not None) == (status == "halted")
    if not ok:
        raise _malformed(rid, seq, "state") from None
    assert isinstance(inputs, dict) and isinstance(nodes, dict)
    clean_inputs = {k: v for k, v in inputs.items() if isinstance(v, str) and _id_ok(k)}
    if len(clean_inputs) != len(inputs):
        raise _malformed(rid, seq, "inputs") from None
    records = {k: _parse_node(v, rid, seq) for k, v in nodes.items() if _id_ok(k)}
    if len(records) != len(nodes) or not records:
        raise _malformed(rid, seq, "nodes") from None
    when, bad = attempt(lambda: datetime.fromisoformat(str(state["saved_at"])), (ValueError,))
    if bad is not None or when is None or when.utcoffset() is None:
        raise _malformed(rid, seq, "saved_at") from None
    return GraphCheckpoint(
        rid, seq, when, state["graph_hash"], status, reason, clean_inputs, records
    )


def _id_ok(value: object) -> bool:
    return isinstance(value, str) and NODE_ID_PATTERN.fullmatch(value) is not None


# ----------------------------------------------------------------------------- writer
class GraphWriter:
    """Publishes the next graph file (no-clobber) and holds the run's owner lock."""

    def __init__(self, store: GraphStore, run_id: str, next_seq: int, lock_fd: int, key: str):
        self._store = store
        self._run_id = run_id
        self._next = next_seq
        self._key = key
        self._fd: int | None = lock_fd
        self._closed = False

    @property
    def run_id(self) -> str:
        return self._run_id

    def __call__(self, cp: GraphCheckpoint) -> None:
        """Save cp under the next seq and the store clock's time (both overwritten here)."""
        if self._next > MAX_SEQ:
            raise GraphError(
                f'Run "{self._run_id}" has reached the limit of {MAX_SEQ + 1} saved files.',
                "Graph files are numbered with six digits.",
                "Start a new run.",
            ) from None
        self._store.write(replace(cp, seq=self._next, saved_at=self._store.clock()))
        self._next += 1

    def node_started(self, node_id: str) -> None:
        with _LIVE_LOCK:
            _LIVE.setdefault(self._key, set()).add(node_id)

    def node_ended(self, node_id: str) -> None:
        """Idempotent. Frees the lock if the run already closed and this was the last live node."""
        with _LIVE_LOCK:
            live = _LIVE.get(self._key)
            if live is not None:
                live.discard(node_id)
                if not live:
                    del _LIVE[self._key]
            fd = self._take_fd()
        _release(fd)

    def close(self) -> None:
        """Idempotent. The lock stays held while an abandoned node thread is alive."""
        with _LIVE_LOCK:
            self._closed = True
            fd = self._take_fd()
        _release(fd)

    def _take_fd(self) -> int | None:  # call with _LIVE_LOCK held: this is the exactly-once gate
        if self._closed and self._fd is not None and self._key not in _LIVE:
            fd, self._fd = self._fd, None
            return fd
        return None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def _release(fd: int | None) -> None:
    if fd is not None:
        attempt(lambda: _unlock(fd), (OSError,))  # a failed close cannot be retried safely


def live_nodes(key: str) -> tuple[str, ...]:
    with _LIVE_LOCK:
        return tuple(sorted(_LIVE.get(key, ())))


# ----------------------------------------------------------------------------- store
class GraphStore:
    """Reads and writes graph checkpoints under ``<workspace>/.checkpoints/<run_id>/``."""

    def __init__(self, checkpoints: CheckpointStore) -> None:
        self._cs = checkpoints

    @property
    def clock(self) -> Clock:
        return self._cs.clock

    def create(self, run_id: str) -> GraphWriter:
        cs, rid = self._cs, validate_run_id(run_id)
        base = cs._path(CHECKPOINT_DIRNAME, "write", rid)
        cs._ensure_dir(base, exist_ok=True, rid=rid)
        cs._write_gitignore(base)
        run_dir = cs._path(cs._run_rel(rid), "write", rid)
        cs._ensure_dir(run_dir, exist_ok=False, rid=rid)
        return GraphWriter(self, rid, 0, cs._lock(rid), os.fspath(run_dir))

    def resume(self, run_id: str) -> tuple[GraphCheckpoint, GraphWriter]:
        cs, rid = self._cs, validate_run_id(run_id)
        run_dir = cs._path(cs._run_rel(rid), "write", rid)
        if not run_dir.is_dir():
            raise _not_found(rid) from None
        key = os.fspath(run_dir)
        running = live_nodes(key)
        if running:
            raise GraphResumeBlocked(
                f'Step {running[0]} of run "{rid}" is still running in this process.',
                "It was left running when the run stopped, and Python cannot stop it.",
                "Wait for it to finish, or restart the program, then resume.",
                node_ids=running,
            ) from None
        fd = cs._lock(rid)
        handed_over = False
        try:
            cp = self.load(rid)
            handed_over = True
        finally:
            if not handed_over:
                _release(fd)
        return cp, GraphWriter(self, rid, cp.seq + 1, fd, key)

    def list_seqs(self, run_id: str) -> list[int]:
        cs, rid = self._cs, validate_run_id(run_id)
        folder = cs._path(cs._run_rel(rid), "read", rid)
        names, failed = attempt(lambda: [e.name for e in os.scandir(folder)], (OSError,))
        if failed is not None or names is None:
            missing = failed is not None and issubclass(
                failed[0], (FileNotFoundError, NotADirectoryError)
            )
            raise (_not_found(rid) if missing else _bad_listing(rid)) from None
        seqs = _graph_seqs(names, rid)
        for i, n in enumerate(seqs):
            if n != i:
                raise GraphError(
                    f'Run "{rid}" is missing graph file {i} (found {_ranges(seqs)}).',
                    "A file was deleted or moved.",
                    "Restore the file, or start a new run.",
                ) from None
        return seqs

    def load(self, run_id: str, seq: int | None = None) -> GraphCheckpoint:
        """Latest checkpoint, or any seq (read-only). No fallback, ever."""
        cs, rid = self._cs, validate_run_id(run_id)
        seqs = self.list_seqs(rid)
        n = seqs[-1] if seq is None else seq
        if n not in seqs:
            raise GraphError(
                f'Run "{rid}" has no graph file {n} (found {_ranges(seqs)}).',
                "That file was never saved.",
                f"Pick a number between 0 and {seqs[-1]}.",
            ) from None
        path = cs._path(f"{cs._run_rel(rid)}/graph-{n:06d}.json", "read", rid)
        stat, failed = attempt(path.stat, (OSError,))
        if failed is not None or stat is None:
            raise _bad(rid, n, "is unreadable", "The file is missing or locked.") from None
        if stat.st_size > MAX_CHECKPOINT_BYTES:
            raise _bad(rid, n, "is too large to load", "It is bigger than any file written.")

        def read() -> object:
            return json.loads(path.read_bytes().decode("utf-8"), parse_constant=_reject_constant)

        obj, failed = attempt(read, (OSError, ValueError, RecursionError))
        if failed is not None:
            raise _bad(rid, n, "is unreadable", "The file is damaged or was cut short.") from None
        return self._open(obj, rid, n)

    def _open(self, obj: object, rid: str, n: int) -> GraphCheckpoint:
        if not isinstance(obj, dict) or set(obj) != {"checksum", "schema_version", "state"}:
            raise _malformed(rid, n, "unexpected layout") from None
        version = obj["schema_version"]
        if type(version) is not int or version != GRAPH_SCHEMA_VERSION:
            shown = version if type(version) is int else "unknown"
            raise _bad(
                rid,
                n,
                f"was written by a different version (schema {shown}; this build reads "
                f"{GRAPH_SCHEMA_VERSION})",
                "The file layout changed between versions.",
            ) from None
        expected = _checksum(obj["state"], version)
        if expected is None or obj["checksum"] != expected:
            raise _bad(
                rid, n, "failed its integrity check", "The content changed after it was saved."
            ) from None
        return _parse_state(obj["state"], rid, n)

    def write(self, cp: GraphCheckpoint) -> None:
        """Publish one graph file: temp file, fsync, durable no-clobber publish, cleanup."""
        cs, rid, seq = self._cs, cp.run_id, cp.seq
        data = encode_graph_checkpoint(cp)
        run_dir = cs._path(cs._run_rel(rid), "write", rid)
        final = cs._path(f"{cs._run_rel(rid)}/graph-{seq:06d}.json", "write", rid)
        tmp, failed = attempt(lambda: stage(run_dir, data), (OSError,))
        if failed is not None or tmp is None:
            raise GraphError(
                f'Run "{rid}" graph file {seq} could not be saved.',
                f"The disk refused the write (error {failed[1] if failed else 0}).",
                "Check free space and folder permissions in the workspace, then resume the run.",
            ) from None
        refused = publish(os.fspath(tmp), os.fspath(final))
        if refused is not None:
            _quiet_unlink(tmp)
            raise _publish_error(refused, rid, seq) from None


def _not_found(rid: str) -> GraphError:
    return GraphError(
        f'Run "{rid}" not found.',
        "There are no saved files under the checkpoint folder.",
        "Check the name, or start a new run.",
    )


def _graph_seqs(names: list[str], rid: str) -> list[int]:
    seqs: list[int] = []
    has_steps = False
    for name in names:
        match = GRAPH_FILE_PATTERN.fullmatch(name)
        if match:
            seqs.append(int(match.group(1)))
        elif name.startswith("graph-"):
            raise GraphError(
                f'Run "{rid}" has an unexpected file in its folder.',
                "Something other than this program put it there.",
                "Move that file out of the run folder.",
            ) from None
        elif STEP_FILE_PATTERN.fullmatch(name) or name.startswith("step-"):
            has_steps = True
    if has_steps and seqs:
        raise GraphError(
            f'Run "{rid}" holds both agent and graph checkpoints.',
            "Agent and graph checkpoints must not share a run folder.",
            "Move the stray files out of the run folder.",
        ) from None
    if has_steps:
        raise GraphError(
            f'Run "{rid}" is a single agent run, not a graph run.',
            "It was saved by the agent loop.",
            f"Resume it with --resume {rid}, or start a new graph run.",
        ) from None
    if not seqs:
        raise GraphError(
            f'Run "{rid}" has no saved graph files.',
            "It was created but nothing was saved.",
            "Start a new run; this folder can be deleted by hand.",
        ) from None
    seqs.sort()
    return seqs
