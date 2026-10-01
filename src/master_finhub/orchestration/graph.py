"""Deterministic graph executor: a fixed workflow of steps that survives a crash.

Design: _workspace/02_strategy-architect_slice6.md (revision 2). Daniel's agents run a workflow
such as "pull the file -> (check income || check expenses) -> draft the note" as one job; if the
process dies half-way, ``resume_graph`` re-runs only the unfinished steps and the answer equals an
uninterrupted run. Nothing partial ever looks finished: ``GraphResult.outputs`` is empty unless
every step is done.

Rules of this module:
* Node and run ids are role names (``income_check``), never client names: they appear in events
  and logs. Events and logs carry ids, statuses, builtin error names, counts and durations only,
  never a node input, output, prompt, path or exception message.
* A node is ``fn(run_inputs, dep_outputs) -> str``. Everything it needs must come through those two
  read-only mappings; a closure over changing data breaks resume equivalence. An ``AgentLoop`` is
  a node by closure; this module imports nothing from ``runtime/``.
* Nodes run on daemon threads in deterministic batches. Python cannot stop a thread, so there is no
  per-node timeout: a run deadline returns control, and the abandoned node keeps running (and
  keeps its side effects) until it returns or the process exits. Its run cannot be resumed
  until then (see ``graph_store``).
* Observers run on the main thread and must be quick: a slow one uses up the deadline.
* No raise happens inside an ``except`` block (package rule): ``attempt`` captures instead.
"""

from __future__ import annotations

import builtins
import hashlib
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from graphlib import CycleError, TopologicalSorter
from types import MappingProxyType
from typing import Final, Literal

from master_finhub.orchestration._fsio import attempt
from master_finhub.orchestration.dag_engine import MAX_CHECKPOINT_BYTES, _dumps, new_run_id
from master_finhub.orchestration.graph_store import (
    NODE_ID_PATTERN,
    GraphCheckpoint,
    GraphError,
    GraphResumeBlocked,
    GraphStore,
    GraphWriter,
    HaltReason,
    NodeRecord,
    NodeStatus,
    RunStatus,
    SavedStatus,
)

__all__ = [
    "Graph",
    "GraphError",
    "GraphEvent",
    "GraphResult",
    "GraphResumeBlocked",
    "Limits",
    "Node",
    "NodeFn",
    "build_graph",
    "exception_name",
    "parallel",
    "pipeline",
    "resume_graph",
    "run_graph",
    "state_budget",
]

MAX_GRAPH_NODES: Final = 256
POLL_SECONDS: Final = 0.1  # coordinator wait slice: Ctrl-C is only seen between slices
STATE_RESERVE_BYTES: Final = 16_384  # envelope and run-level fields
NODE_RESERVE_BYTES: Final = 512  # per-node keys, id, status, error_type
INPUT_RESERVE_BYTES: Final = 64  # per run-input key
MAX_RUN_INPUTS: Final = 64
NL: Final = chr(10)
JOIN_SECONDS: Final = 5.0
OVER_BUDGET: Final = frozenset({"NodeOutputOverBudget", "NodeOutputTooLarge"})
_PLACEHOLDER_TIME: Final = datetime(1970, 1, 1, tzinfo=UTC)  # the writer overwrites it
log = logging.getLogger("master_finhub.orchestration.graph")

NodeFn = Callable[[Mapping[str, str], Mapping[str, str]], str]
NodeInFlight = Literal["stop", "rerun"]
EventKind = Literal[
    "run_started",
    "run_resumed",
    "node_started",
    "node_finished",
    "node_failed",
    "node_skipped",
    "run_halted",
    "run_finished",
]
Outcome = tuple[str, object, str | None]  # (node id, output, builtin error name)


# ----------------------------------------------------------------------------- model
@dataclass(frozen=True)
class Node:
    id: str
    fn: NodeFn
    deps: tuple[str, ...] = ()
    idempotent: bool = False  # safe to run twice, like ToolSpec.idempotent


@dataclass(frozen=True)
class Graph:
    """Only ``build_graph`` makes one. ``graph_hash`` covers ids and edges, never functions."""

    nodes: Mapping[str, Node]
    graph_hash: str


@dataclass(frozen=True)
class Limits:
    """Per invocation of run_graph / resume_graph."""

    max_nodes: int = 64  # node executions started ("step limit"), >= 1
    deadline_s: float | None = 1800.0  # wall-clock budget on the injected clock; None = none
    max_parallelism: int = 4  # 1..32 nodes in one batch
    max_output_bytes: int = 262_144  # JSON-encoded bytes per node output


@dataclass(frozen=True)
class GraphEvent:
    kind: EventKind
    seq: int
    run_id: str | None
    node_id: str | None = None
    status: str | None = None
    halt_reason: HaltReason | None = None
    error_type: str | None = None
    duration_ms: int | None = None
    counts: Mapping[str, int] = field(default_factory=dict)


Observer = Callable[[GraphEvent], None]


@dataclass(frozen=True)
class GraphResult:
    run_id: str | None
    status: RunStatus
    halt_reason: HaltReason | None
    nodes: Mapping[str, NodeStatus]
    errors: Mapping[str, str]  # node id -> error name, failed nodes only
    outputs: Mapping[str, str]  # EMPTY unless status == "done"
    observer_errors: int
    message: str = ""  # three lines for Daniel when the run is not done


DEFAULT_LIMITS: Final = Limits()


def _builtin_table() -> dict[int, tuple[type[BaseException], str]]:
    table: dict[int, tuple[type[BaseException], str]] = {}
    for obj in vars(builtins).values():
        if isinstance(obj, type) and issubclass(obj, BaseException):
            table[id(obj)] = (obj, obj.__name__)
    return table


_BUILTIN_EXC: Final = _builtin_table()


def exception_name(cls: type[BaseException]) -> str:
    """Builtin exception name by identity, else "Exception". Runs no user code."""
    entry = _BUILTIN_EXC.get(id(cls))
    return entry[1] if entry is not None and entry[0] is cls else "Exception"


def _bad(what: str, why: str, fix: str, ids: tuple[str, ...] = ()) -> GraphError:
    return GraphError(what, why, fix, node_ids=ids)


# ----------------------------------------------------------------------------- build
def _find_cycle(deps: Mapping[str, tuple[str, ...]]) -> list[str] | None:
    ts: TopologicalSorter[str] = TopologicalSorter()
    for node_id in sorted(deps):  # sorted ids and deps: the same text whatever PYTHONHASHSEED is
        ts.add(node_id, *sorted(deps[node_id]))
    try:
        ts.prepare()
    except CycleError as exc:
        return [str(x) for x in exc.args[1]]  # already-validated id strings
    return None


def _shown(dep: object) -> str:
    ok = isinstance(dep, str) and NODE_ID_PATTERN.fullmatch(dep) is not None
    return str(dep) if ok else "a malformed id"


def _check_nodes(items: Sequence[object]) -> dict[str, Node]:
    fix_ids = "Give every step a different lower-case role name such as income_check."
    if not items:
        raise _bad("The graph has no steps.", "A graph needs at least one step.", fix_ids) from None
    if len(items) > MAX_GRAPH_NODES:
        raise _bad(
            f"The graph has {len(items)} steps.",
            f"A graph may have at most {MAX_GRAPH_NODES} steps.",
            "Split the workflow into smaller graphs.",
        ) from None
    table: dict[str, Node] = {}
    for position, node in enumerate(items, 1):
        if not isinstance(node, Node) or not isinstance(node.id, str):
            raise _bad(
                f"Step {position} is not a step.", "Steps are made with Node(...).", "Use Node."
            ) from None
        if NODE_ID_PATTERN.fullmatch(node.id) is None:
            raise _bad(
                f"Node {position} has an id that is not allowed.",
                "Ids are a lower-case letter then up to 31 lower-case letters, digits or _.",
                fix_ids,
            ) from None
        if node.id in table:
            raise _bad(
                f'Step "{node.id}" appears twice.', "Ids must be unique.", fix_ids, (node.id,)
            ) from None
        table[node.id] = node
    return table


def _check_edges(table: Mapping[str, Node]) -> None:
    for node_id in sorted(table):
        deps = table[node_id].deps
        for dep in deps:
            if dep not in table:
                raise _bad(
                    f'Step "{node_id}" depends on "{_shown(dep)}", which is not a step.',
                    "Every dependency must be the id of a step in the graph.",
                    "Fix the dependency name or add the missing step.",
                    (node_id,),
                ) from None
        if len(set(deps)) != len(deps):
            raise _bad(
                f'Step "{node_id}" lists the same dependency twice.',
                "A repeated dependency would change the graph's identity.",
                "List each dependency once.",
                (node_id,),
            ) from None
        if node_id in deps:
            raise _bad(
                f'Step "{node_id}" depends on itself.',
                "A step cannot wait for its own result.",
                "Remove the self-dependency.",
                (node_id,),
            ) from None


def build_graph(nodes: Iterable[Node]) -> Graph:
    """Validate and freeze a graph. Errors name step ids only, never functions or data."""
    table = _check_nodes(list(nodes))
    _check_edges(table)
    path = _find_cycle({i: n.deps for i, n in table.items()})
    if path is not None:
        raise _bad(
            f"The steps form a loop: {' -> '.join(path)}.",
            "A step cannot depend, directly or indirectly, on itself.",
            "Remove one dependency in the loop.",
            tuple(sorted(set(path))),
        ) from None
    shape = [[i, sorted(table[i].deps)] for i in sorted(table)]
    canonical = _dumps(shape, pretty=False) or b""
    digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
    frozen = {i: replace(table[i], deps=tuple(table[i].deps)) for i in sorted(table)}
    return Graph(MappingProxyType(frozen), digest)


def pipeline(*nodes: Node) -> tuple[Node, ...]:
    """Build-time sugar: each step also depends on the one before it."""
    out: list[Node] = []
    for i, node in enumerate(nodes):
        extra = (nodes[i - 1].id,) if i else ()
        out.append(replace(node, deps=(*node.deps, *(d for d in extra if d not in node.deps))))
    return tuple(out)


def parallel(*nodes: Node, after: Sequence[str] = ()) -> tuple[Node, ...]:
    """Build-time sugar: every step also depends on the ``after`` ids."""
    return tuple(replace(n, deps=(*n.deps, *(d for d in after if d not in n.deps))) for n in nodes)


# ----------------------------------------------------------------------------- limits and text
def state_budget(node_count: int) -> int:
    """Bytes of run inputs and outputs a checkpoint may hold so its file stays under 8 MiB."""
    return MAX_CHECKPOINT_BYTES - STATE_RESERVE_BYTES - NODE_RESERVE_BYTES * node_count


def json_len(text: str) -> int:
    """JSON-encoded size in bytes (escaping can make text up to 6x larger)."""
    return len(_dumps(text, pretty=False) or b"")


def _text_problem(value: object) -> str | None:
    if type(value) is not str:
        return "NodeOutputNotText"
    assert isinstance(value, str)
    _, bad = attempt(lambda: str.encode(value, "utf-8"), (UnicodeEncodeError,))
    return "NodeOutputNotStorable" if bad is not None else None


def _check_limits(limits: Limits, graph: Graph) -> None:
    budget = state_budget(len(graph.nodes))
    ok = limits.max_nodes >= 1 and 1 <= limits.max_parallelism <= 32
    ok = ok and (limits.deadline_s is None or limits.deadline_s > 0)
    ok = ok and 1 <= limits.max_output_bytes <= budget
    if not ok:
        raise _bad(
            "The run limits are not usable.",
            f"Steps must be at least 1, parallelism 1 to 32, the deadline above 0 and the "
            f"output limit at most {budget} bytes for this graph.",
            "Change Limits(...) to values in those ranges.",
        ) from None


def _check_inputs(inputs: Mapping[str, str], graph: Graph) -> dict[str, str]:
    fix = "Pass at most 64 inputs with lower-case names and plain-text values."
    used = 0
    if len(inputs) > MAX_RUN_INPUTS:
        raise _bad("Too many run inputs.", f"A run takes at most {MAX_RUN_INPUTS}.", fix) from None
    for key, value in inputs.items():
        keyed = isinstance(key, str) and NODE_ID_PATTERN.fullmatch(key) is not None
        if not keyed or _text_problem(value) is not None:
            raise _bad(
                "A run input is not allowed.", "Names and values must be text.", fix
            ) from None
        used += json_len(value) + INPUT_RESERVE_BYTES
    if used > state_budget(len(graph.nodes)):
        raise _bad(
            "The run inputs are too large.",
            "A run keeps all inputs and step outputs in one checkpoint file of at most 8 MiB.",
            "Pass less data, for example a summary.",
        ) from None
    return dict(inputs)


# ----------------------------------------------------------------------------- worker
def _work(
    node_id: str,
    fn: NodeFn,
    run: Mapping[str, str],
    deps: Mapping[str, str],
    q: queue.Queue[Outcome],
    writer: GraphWriter | None,
) -> None:
    """Thread target. Posts exactly one outcome FIRST, then cleans up; never reads the instance.

    Every BaseException is handled here (a thread cannot hand SystemExit or Ctrl-C to the main
    thread). Only the class is kept, mapped to a builtin name by identity.
    """
    outcome: Outcome = (node_id, None, "Exception")  # pessimistic default
    try:
        outcome = (node_id, fn(run, deps), None)
    except BaseException as exc:  # noqa: BLE001 - thread boundary
        outcome = (node_id, None, exception_name(type(exc)))
    finally:
        q.put(outcome)  # the result is posted before any cleanup can fail
        if writer is not None:
            attempt(lambda: writer.node_ended(node_id), (Exception,))


# ----------------------------------------------------------------------------- executor
class _Exec:
    """One invocation. Only the main thread touches the sorter, records, store and observer."""

    def __init__(
        self,
        graph: Graph,
        inputs: Mapping[str, str],
        records: dict[str, NodeRecord],
        writer: GraphWriter | None,
        run_id: str | None,
        limits: Limits,
        observer: Observer | None,
        monotonic: Callable[[], float],
        resumed: bool,
    ) -> None:
        self.graph, self.rec, self.writer, self.run_id = graph, records, writer, run_id
        self.inputs = MappingProxyType(dict(inputs))
        self.limits, self.observer, self.mono, self.resumed = limits, observer, monotonic, resumed
        self.seq = self.started = self.observer_errors = 0
        self.q: queue.Queue[Outcome] = queue.Queue()
        self.batch: dict[str, threading.Thread] = {}
        self.budget = state_budget(len(graph.nodes))
        self.used = sum(json_len(v) + INPUT_RESERVE_BYTES for v in inputs.values())
        self.used += sum(json_len(r.output) for r in records.values() if r.output is not None)
        self.t0 = monotonic()
        self.last = 0.0
        self.drained: list[str] = []

    # -- events and saves
    def _emit(
        self,
        kind: EventKind,
        node_id: str | None = None,
        status: str | None = None,
        halt_reason: HaltReason | None = None,
        error_type: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        counts: dict[str, int] = {}
        if kind.startswith("run_"):
            counts = {s: 0 for s in ("pending", "running", "done", "failed", "skipped")}
            for r in self.rec.values():
                counts[r.status] += 1
        ev = GraphEvent(
            kind,
            self.seq,
            self.run_id,
            node_id,
            status,
            halt_reason,
            error_type,
            duration_ms,
            counts,
        )
        self.seq += 1
        log.debug(
            "event kind=%s seq=%d run=%s node=%s status=%s halt=%s error=%s ms=%s",
            ev.kind,
            ev.seq,
            ev.run_id,
            ev.node_id,
            ev.status,
            ev.halt_reason,
            ev.error_type,
            ev.duration_ms,
        )
        if self.observer is not None:
            observer = self.observer
            _, bad = attempt(lambda: observer(ev), (Exception,))
            if bad is not None:
                self.observer_errors += 1
                log.warning("observer raised %s", exception_name(bad[0]))

    def _save(self, status: SavedStatus = "running", reason: HaltReason | None = None) -> None:
        if self.writer is None or self.run_id is None:
            return
        self.writer(
            GraphCheckpoint(
                self.run_id,
                0,
                _PLACEHOLDER_TIME,
                self.graph.graph_hash,
                status,
                reason,
                dict(self.inputs),
                dict(self.rec),
            )
        )

    # -- the run
    def run(self) -> GraphResult:
        try:
            return self._run()
        finally:
            self._release()

    def _release(self) -> None:
        if self.writer is None:
            return
        for node_id, thread in self.batch.items():
            if thread.ident is None:  # never started: no worker will ever clear its entry
                self.writer.node_ended(node_id)
        self.writer.close()

    def _run(self) -> GraphResult:
        self._save()
        self._emit("run_resumed" if self.resumed else "run_started", status="running")
        reason: HaltReason | None = None
        interrupted = False
        try:
            reason = self._loop()
        except KeyboardInterrupt:
            interrupted = True  # handled below, outside the except (package rule)
        if interrupted:
            self._drain()
            self._halt("interrupted")
            raise KeyboardInterrupt  # a fresh instance with no chain
        if reason is not None:
            self._halt(reason)
            return self._result("halted", reason)
        return self._finish()

    def replay_done(self) -> GraphResult:
        """A run saved as done: return its stored outputs, run and write nothing."""
        try:
            self._emit("run_resumed", status="done")
            self._emit("run_finished", status="done")
            return self._result("done", None)
        finally:
            self._release()

    def _sorter(self) -> TopologicalSorter[str]:
        ts: TopologicalSorter[str] = TopologicalSorter()
        todo = [i for i in sorted(self.graph.nodes) if self.rec[i].status != "done"]
        for i in todo:
            ts.add(i, *sorted(d for d in self.graph.nodes[i].deps if self.rec[d].status != "done"))
        ts.prepare()
        return ts

    def _loop(self) -> HaltReason | None:
        ts = self._sorter()
        ready: list[str] = []
        while True:
            ready = sorted([*ready, *ts.get_ready()])  # each id is handed out once: keep them
            if not ready:
                return None
            if self.started >= self.limits.max_nodes:
                return "step_limit"
            if self._elapsed() >= self._deadline():
                return "deadline"
            size = min(self.limits.max_parallelism, self.limits.max_nodes - self.started)
            take, ready = ready[:size], ready[size:]
            if self._batch(take, ts):
                return "deadline"

    def _deadline(self) -> float:
        d = self.limits.deadline_s
        return float("inf") if d is None else d

    def _elapsed(self) -> float:
        self.last = self.mono() - self.t0
        return self.last

    def _batch(self, take: list[str], ts: TopologicalSorter[str]) -> bool:
        """Run one batch. True when the deadline cut it short."""
        for node_id in take:
            self.rec[node_id] = NodeRecord("running")
        self.started += len(take)
        self._save()
        for node_id in take:
            self._emit("node_started", node_id=node_id, status="running")
        begun = self.last
        self._launch(take)
        got, timed_out = self._collect(len(take))
        self._join(got)
        done = self._apply(got, ts)
        self._save()
        ms = int(max(self.last - begun, 0.0) * 1000)
        for node_id in sorted(done):
            r = self.rec[node_id]
            kind: EventKind = "node_finished" if r.status == "done" else "node_failed"
            self._emit(
                kind, node_id=node_id, status=r.status, error_type=r.error_type, duration_ms=ms
            )
        self.batch.clear()
        return timed_out

    def _launch(self, take: list[str]) -> None:
        for node_id in take:
            node = self.graph.nodes[node_id]
            deps = MappingProxyType({d: self.rec[d].output or "" for d in sorted(node.deps)})
            args = (node_id, node.fn, self.inputs, deps, self.q, self.writer)
            thread = threading.Thread(target=_work, args=args, daemon=True)
            self.batch[node_id] = thread
            if self.writer is not None:
                self.writer.node_started(node_id)
            _, failed = attempt(thread.start, (Exception,))
            if failed is not None:  # "can't start new thread": the step never ran
                self.q.put((node_id, None, exception_name(failed[0])))
                self._ended(node_id)

    def _poll(self, wait: float) -> Outcome | None:
        try:
            return self.q.get(timeout=wait) if wait > 0 else self.q.get_nowait()
        except queue.Empty:
            return None

    def _collect(self, count: int) -> tuple[list[Outcome], bool]:
        got: list[Outcome] = []
        while len(got) < count:
            item = self._poll(0)
            if item is None:
                remaining = self._deadline() - self._elapsed()
                if remaining <= 0:  # also guards queue.get(timeout=negative)
                    return got, True
                item = self._poll(min(POLL_SECONDS, remaining))
            if item is not None:
                got.append(item)
        return got, False

    def _join(self, got: list[Outcome]) -> None:
        """Wait for the finished workers so none is still 'live' when the batch is applied."""
        for node_id, *_ in got:
            thread = self.batch[node_id]
            if thread.ident is not None:  # a thread that failed to start has nothing to join
                thread.join(JOIN_SECONDS)
            self._ended(node_id)  # belt and braces: idempotent, the worker already did it

    def _ended(self, node_id: str) -> None:
        if self.writer is not None:
            writer = self.writer
            attempt(lambda: writer.node_ended(node_id), (Exception,))

    def _apply(self, got: list[Outcome], ts: TopologicalSorter[str] | None) -> list[str]:
        for node_id, output, error in sorted(got, key=lambda o: o[0]):
            self.rec[node_id] = self._judge(output, error)
            if ts is not None and self.rec[node_id].status == "done":
                ts.done(node_id)
        return [o[0] for o in got]

    def _judge(self, output: object, error: str | None) -> NodeRecord:
        if error is None:
            error = _text_problem(output)
        if error is not None:
            return NodeRecord("failed", error_type=error)
        assert isinstance(output, str)
        size = json_len(output)
        if size > self.limits.max_output_bytes:
            return NodeRecord("failed", error_type="NodeOutputTooLarge")
        if self.used + size > self.budget:
            return NodeRecord("failed", error_type="NodeOutputOverBudget")
        self.used += size
        return NodeRecord("done", output=output)

    def _drain(self) -> None:
        got: list[Outcome] = []
        while (item := self._poll(0)) is not None:
            got.append(item)
        self.drained = self._apply(got, None)

    # -- endings
    def _halt(self, reason: HaltReason) -> None:
        self._save("halted", reason)
        for node_id in sorted(self.drained):
            r = self.rec[node_id]
            kind: EventKind = "node_finished" if r.status == "done" else "node_failed"
            self._emit(kind, node_id=node_id, status=r.status, error_type=r.error_type)
        self._emit("run_halted", status="halted", halt_reason=reason)

    def _finish(self) -> GraphResult:
        failed = any(r.status == "failed" for r in self.rec.values())
        skipped = sorted(i for i, r in self.rec.items() if r.status == "pending")
        for node_id in skipped:
            self.rec[node_id] = NodeRecord("skipped")
        status: RunStatus = "failed" if failed or skipped else "done"
        self._save(status)
        for node_id in skipped:
            self._emit("node_skipped", node_id=node_id, status="skipped")
        self._emit("run_finished", status=status)
        return self._result(status, None)

    def _result(self, status: RunStatus, reason: HaltReason | None) -> GraphResult:
        nodes: dict[str, NodeStatus] = {i: self.rec[i].status for i in sorted(self.rec)}
        errors = {i: r.error_type for i, r in sorted(self.rec.items()) if r.error_type}
        outputs = (
            {i: r.output or "" for i, r in sorted(self.rec.items())} if status == "done" else {}
        )
        return GraphResult(
            self.run_id,
            status,
            reason,
            nodes,
            errors,
            outputs,
            self.observer_errors,
            self._message(status, reason),
        )

    def _message(self, status: RunStatus, reason: HaltReason | None) -> str:
        if status == "done":
            return ""
        if status == "failed":
            return self._failure_message()
        running = sorted(i for i, r in self.rec.items() if r.status == "running")
        if reason == "deadline":
            first = f"Step {running[0]} is still running." if running else "The run hit its limit."
            return NL.join(
                (
                    first,
                    "It passed the run's time limit and Python cannot stop it.",
                    "Wait for it to finish (or restart the program), then resume.",
                )
            )
        todo = sum(1 for r in self.rec.values() if r.status in ("pending", "running"))
        return NL.join(
            (
                f"The run stopped at its step limit ({self.limits.max_nodes} steps).",
                f"{todo} steps are still to do.",
                "Resume it with the same limits to continue.",
            )
        )

    def _failure_message(self) -> str:
        failed = {i: r.error_type for i, r in sorted(self.rec.items()) if r.status == "failed"}
        big = [i for i, t in failed.items() if t in OVER_BUDGET]
        if big:
            return (
                f"Step {big[0]} produced more than the run can store.\n"
                "A run keeps every step's output in one checkpoint file of at most 8 MiB.\n"
                "Make the step return less (for example a summary), then start a new run."
            )
        names = ", ".join(f"{i} ({t})" for i, t in failed.items())
        skipped = ", ".join(i for i, r in sorted(self.rec.items()) if r.status == "skipped")
        return (
            f"Failed: {names}.\n"
            f"Steps that depend on them were skipped: {skipped or 'none'}.\n"
            'Fix the cause, then resume with in_flight="rerun".'
        )


# ----------------------------------------------------------------------------- entry points
def run_graph(
    graph: Graph,
    inputs: Mapping[str, str] | None = None,
    *,
    limits: Limits = DEFAULT_LIMITS,
    store: GraphStore | None = None,
    run_id: str | None = None,
    observer: Observer | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> GraphResult:
    """Run a graph. With a store every batch is checkpointed first; without one nothing is written."""
    _check_limits(limits, graph)
    clean = _check_inputs(inputs or {}, graph)
    writer: GraphWriter | None = None
    rid = run_id
    if store is not None:
        writer = store.create(run_id or new_run_id(store.clock))
        rid = writer.run_id
    records = {i: NodeRecord("pending") for i in graph.nodes}
    return _Exec(graph, clean, records, writer, rid, limits, observer, monotonic, False).run()


def _plan_resume(
    graph: Graph, cp: GraphCheckpoint, in_flight: NodeInFlight
) -> dict[str, NodeRecord]:
    if cp.graph_hash != graph.graph_hash:
        then, now = set(cp.nodes), set(graph.nodes)
        moved = f"; added: {', '.join(sorted(now - then)[:5])}" if now - then else ""
        moved += f"; removed: {', '.join(sorted(then - now)[:5])}" if then - now else ""
        raise _bad(
            f'Run "{cp.run_id}" was saved for a different graph '
            f"({len(then)} steps then, {len(now)} now{moved or '; connections changed'}).",
            "Resuming would mix results from two different workflows.",
            "Resume with the same graph, or start a new run.",
        ) from None
    records: dict[str, NodeRecord] = {}
    unsafe: list[str] = []
    for node_id in sorted(cp.nodes):
        rec = cp.nodes[node_id]
        if rec.status == "done":
            records[node_id] = rec
            continue
        if rec.status in ("running", "failed") and not (
            graph.nodes[node_id].idempotent or in_flight == "rerun"
        ):
            unsafe.append(node_id)
        records[node_id] = NodeRecord("pending")
    if unsafe:
        plural = len(unsafe) > 1
        raise GraphResumeBlocked(
            f"Resume stopped: {'steps' if plural else 'step'} {', '.join(unsafe)} "
            f"may already have run and {'are' if plural else 'is'} not safe to repeat.",
            "The process stopped before the result was saved.",
            'Check whether it happened, then resume with in_flight="rerun".',
            node_ids=tuple(unsafe),
        ) from None
    return records


def resume_graph(
    graph: Graph,
    store: GraphStore,
    run_id: str,
    *,
    limits: Limits = DEFAULT_LIMITS,
    in_flight: NodeInFlight = "stop",
    observer: Observer | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> GraphResult:
    """Continue a saved run: done steps are kept, the rest run. Takes no inputs: the run's own."""
    _check_limits(limits, graph)
    cp, writer = store.resume(run_id)
    planned = False
    try:
        records = _plan_resume(graph, cp, in_flight)
        planned = True
    finally:
        if not planned:
            writer.close()
    run = _Exec(graph, cp.inputs, records, writer, cp.run_id, limits, observer, monotonic, True)
    return run.replay_done() if cp.status == "done" else run.run()
