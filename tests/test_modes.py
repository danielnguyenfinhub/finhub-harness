"""Slice 7 proof tests, part 2: the task board and team mode (synthetic roles and strings only)."""

from __future__ import annotations

import _thread
import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from modes_support import (
    MARKER,
    FnLLM,
    Gate,
    _quiet_after,  # noqa: F401 - autouse fixture
    answerer_fn,
    asker_fn,
    call,
    say,
    settle,
)

from master_finhub.orchestration.graph_store import GraphError
from master_finhub.orchestration.modes import team as team_mod
from master_finhub.orchestration.modes import workflow
from master_finhub.orchestration.modes.task_board import MAX_TASKS, TaskBoard, TaskError, TaskSpec
from master_finhub.orchestration.modes.team import (
    Persona,
    TeamError,
    TeamEvent,
    TeamLimits,
    TeamResult,
    run_team,
)
from master_finhub.orchestration.modes.team_tools import SendMessageTool
from master_finhub.runtime.loop import LLM, Message, ToolCall, ToolSpec
from master_finhub.tools import safety
from master_finhub.tools.safety import guard_tool_call

ROOT = Path(__file__).resolve().parent.parent
CHILD = Path(__file__).parent / "modes_child.py"


def _team(
    llms: dict[str, Callable[..., Any]],
    tasks: list[TaskSpec],
    *,
    limits: TeamLimits | None = None,
    **kw: Any,
) -> TeamResult:
    personas = [Persona(name, "builder") for name in llms]
    factory: Callable[[Persona], LLM] = lambda p: FnLLM(llms[p.name])
    return run_team(personas, tasks, limits=limits or TeamLimits(), llm_for=factory, **kw)


ROUND_TRIP_TASKS = [TaskSpec("t1", "ask the answerer", assignee="asker-agent")]
ROUND_TRIP = {"asker-agent": asker_fn, "answerer-agent": answerer_fn}


# ----------------------------------------------------------------------------- board
def _race_for_claims() -> list[str]:
    board = TaskBoard([TaskSpec(f"t{i}", "x") for i in range(MAX_TASKS)])
    barrier = threading.Barrier(32)
    claimed: list[str] = []
    lock = threading.Lock()

    def worker(n: int) -> None:
        barrier.wait()
        while (spec := board.claim(f"w{n}-agent")) is not None:
            with lock:
                claimed.append(spec.id)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(32)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return claimed


def test_exactly_once_claim_under_32_threads() -> None:  # T15 (256 = MAX_TASKS, 8 boards)
    for _ in range(8):
        claimed = _race_for_claims()
        assert len(claimed) == MAX_TASKS == len(set(claimed))


def test_owner_only_complete_and_fail() -> None:  # T16
    board = TaskBoard([TaskSpec("t1", "x"), TaskSpec("t2", "y")])
    spec = board.claim("a-agent")
    assert spec is not None and spec.id == "t1"
    for action in (
        lambda: board.complete("b-agent", "t1", "no"),
        lambda: board.fail("b-agent", "t1"),
    ):
        with pytest.raises(TaskError) as exc_info:
            action()
        assert exc_info.value.code == "not_owner"
    board.complete("a-agent", "t1", "fine")
    with pytest.raises(TaskError) as twice:
        board.complete("a-agent", "t1", "again")
    assert twice.value.code == "wrong_status"
    with pytest.raises(TaskError) as unknown:
        board.complete("a-agent", "zz", "x")
    assert unknown.value.code == "unknown_task"
    assert board.results() == {}  # t2 is not done: never a plausible partial
    board.freeze()
    with pytest.raises(TaskError) as closed:
        board.fail("a-agent", "t2")
    assert closed.value.code == "board_closed"


def test_board_rejects_forward_or_unknown_deps_and_caps() -> None:  # T17
    bad_sets: list[list[TaskSpec]] = [
        [TaskSpec("t1", "x", deps=("t2",)), TaskSpec("t2", "y")],  # forward
        [TaskSpec("t1", "x", deps=("nope",))],  # unknown
        [TaskSpec(f"t{i}", "x") for i in range(MAX_TASKS + 1)],  # 257
        [TaskSpec("t1", "x" * 9000)],  # oversize description
        [TaskSpec("t1", "x"), TaskSpec("t1", "y")],  # duplicate
        [TaskSpec("T1", "x")],  # bad id
        [],
    ]
    for tasks in bad_sets:
        with pytest.raises(TaskError) as exc_info:
            TaskBoard(tasks)
        assert exc_info.value.code == "invalid_task"
    board = TaskBoard([TaskSpec("t1", "x")], max_result_bytes=10)
    board.claim("a-agent")
    with pytest.raises(TaskError) as big:
        board.complete("a-agent", "t1", "x" * 11)
    assert big.value.code == "too_large"
    with pytest.raises(TaskError) as odd:
        board.complete("a-agent", "t1", "\ud800")
    assert odd.value.code == "not_text"
    board.complete("a-agent", "t1", "x" * 10)
    assert board.results() == {"t1": "x" * 10}


def test_claim_respects_deps_and_assignee() -> None:
    board = TaskBoard([TaskSpec("t1", "x", assignee="a-agent"), TaskSpec("t2", "y", deps=("t1",))])
    assert board.claim("b-agent") is None  # t1 is a-agent's; t2 waits for t1
    assert board.claimable()
    first = board.claim("a-agent")
    assert first is not None and first.id == "t1" and not board.claimable()
    assert board.claim("b-agent") is None
    assert board.release_owner("a-agent") == ("t1",) and board.any_failed()


# ----------------------------------------------------------------------------- team
def test_team_message_round_trip() -> None:  # T18 - the slice proof
    events: list[TeamEvent] = []
    result = _team(ROUND_TRIP, ROUND_TRIP_TASKS, observer=events.append)
    assert result.status == "done" and result.halt_reason is None
    assert result.results == {"t1": "reply=forty-two"}
    assert result.tasks == {"t1": "done"} and result.failed_agents == {}
    assert result.messages == 2 and result.message == "" and result.still_running == ()
    kinds = [e.kind for e in events]
    assert kinds[0] == "team_started" and kinds[-1] == "team_finished"
    assert {"task_claimed", "message_sent", "task_done"} <= set(kinds)
    assert [e.seq for e in events] == list(range(len(events)))
    blob = repr(events) + repr(result)
    assert "forty-two" not in blob and "6x7" not in blob


def test_team_failure_of_one_agent_halts_run() -> None:  # T19
    def boom(messages: list[Message], tools: list[ToolSpec]) -> Any:
        raise ValueError(MARKER)

    result = _team({"asker-agent": asker_fn, "answerer-agent": boom}, ROUND_TRIP_TASKS)
    assert result.status == "failed" and result.results == {}
    assert result.failed_agents == {"answerer-agent": "ValueError"}
    assert MARKER not in repr(result) and MARKER not in result.message


def test_team_stalled_is_halted_not_done() -> None:  # T20
    result = _team({"idle-agent": lambda m, t: say("not doing it")}, [TaskSpec("t1", "x")])
    assert result.status == "halted" and result.halt_reason == "stalled"
    assert result.results == {} and result.tasks == {"t1": "claimed"}
    assert "idle" in result.message


def test_team_turn_limit_and_deadline() -> None:  # T21
    tight = TeamLimits(max_turns=1)
    result = _team(ROUND_TRIP, ROUND_TRIP_TASKS, limits=tight)
    assert result.status == "halted" and result.halt_reason == "turn_limit"
    assert result.results == {} and result.turns == 1
    gate, now = Gate(), [0.0]
    out: list[TeamResult] = []

    def run() -> None:
        out.append(
            _team(
                {"slow-agent": lambda m, t: gate.hang()},
                [TaskSpec("t1", "x")],
                monotonic=lambda: now[0],
            )
        )

    runner = threading.Thread(target=run)
    runner.start()
    try:
        assert gate.started.wait(5)
        now[0] = 10_000.0  # the fake clock jumps past the 1800 s deadline
        runner.join(5)
    finally:
        gate.release.set()
    assert out and out[0].status == "halted" and out[0].halt_reason == "deadline"
    assert out[0].still_running == ("slow-agent",) and out[0].results == {}
    assert "slow-agent" in out[0].message and "cannot stop" in out[0].message


def test_team_ctrl_c_latency() -> None:  # T22
    gate = Gate()
    events: list[TeamEvent] = []
    fired: list[float] = []

    def interrupt() -> None:
        gate.started.wait(5)
        time.sleep(0.3)
        fired.append(time.monotonic())
        _thread.interrupt_main()

    timer = threading.Thread(target=interrupt)
    timer.start()
    caught = None
    try:
        _team(
            {"slow-agent": lambda m, t: gate.hang()}, [TaskSpec("t1", "x")], observer=events.append
        )
    except KeyboardInterrupt as exc:
        caught = time.monotonic()
        assert exc.__context__ is None and exc.__cause__ is None
    finally:
        gate.release.set()
    timer.join()
    assert caught is not None and caught - fired[0] < 0.25
    assert events[-1].kind == "team_halted" and events[-1].halt_reason == "interrupted"


def test_one_team_at_a_time() -> None:  # T23
    gate = Gate()
    out: list[TeamResult] = []
    first = threading.Thread(
        target=lambda: out.append(
            _team(
                {"slow-agent": lambda m, t: gate.hang()},
                [TaskSpec("t1", "x")],
                limits=TeamLimits(deadline_s=0.4),
            )
        )
    )
    first.start()
    try:
        assert gate.started.wait(5)
        with pytest.raises(TeamError) as exc_info:
            _team(ROUND_TRIP, ROUND_TRIP_TASKS)
        assert "Another team" in str(exc_info.value)
        first.join(5)  # the deadline ends the first run, but its hung agent still holds the lock
        assert out and out[0].halt_reason == "deadline"
        with pytest.raises(TeamError):
            _team(ROUND_TRIP, ROUND_TRIP_TASKS)
    finally:
        gate.release.set()
    assert settle()
    assert _team(ROUND_TRIP, ROUND_TRIP_TASKS).status == "done"


class _Shell:
    spec = ToolSpec("shell", "Run a command.", {"type": "object"})

    def __init__(self) -> None:
        self.ran = 0

    def run(self, arguments: dict[str, Any]) -> str:
        self.ran += 1
        return "ran"


def test_guard_is_always_applied() -> None:  # T24
    shell, seen = _Shell(), []

    def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("shell", command="rm -rf /")
        if last.role == "tool" and last.tool_call_id == "c-shell":
            seen.append(last.content)
            return call("complete_task", task_id="t1", result="denied")
        return say("ok")

    personas = [Persona("ops-agent", "builder", tools=(shell,))]
    result = run_team(personas, [TaskSpec("t1", "x")], llm_for=lambda p: FnLLM(fn))
    assert result.status == "done" and shell.ran == 0
    assert seen and seen[0].startswith("Error: Blocked by safety policy")


def test_team_validation_and_low_fixes() -> None:  # T39 validation + T40 team part
    def llm(p: Persona) -> LLM:
        return FnLLM(lambda m, t: say("x"))

    tasks = [TaskSpec("t1", "x")]
    for deadline in (None, 0, -1, float("inf"), float("nan"), 14_401.0):
        with pytest.raises(TeamError):
            run_team(
                [Persona("a-agent", "b")],
                tasks,
                limits=TeamLimits(deadline_s=deadline),  # type: ignore[arg-type]
                llm_for=llm,
            )
    with pytest.raises(TeamError):
        run_team([Persona("a-agent", "b")], [], llm_for=llm)
    for name in ("income", "lead-agent2", "All-agent", "nul"):
        with pytest.raises(TeamError):
            run_team([Persona(name, "b")], tasks, llm_for=llm)
    with pytest.raises(TeamError):
        run_team([Persona("a-agent", "b"), Persona("a-agent", "b")], tasks, llm_for=llm)
    with pytest.raises(TeamError):
        run_team(
            [Persona("a-agent", "b")], [TaskSpec("t1", "x", assignee="ghost-agent")], llm_for=llm
        )
    assert team_mod._TEAM_LOCK.locked() is False


def test_hung_turn_halts_at_deadline() -> None:  # T39
    gate = Gate()
    start = time.monotonic()
    try:
        result = _team(
            {"answerer-agent": lambda m, t: gate.hang()},
            [TaskSpec("t1", "x")],
            limits=TeamLimits(deadline_s=0.3),
        )
    finally:
        gate.release.set()
    assert time.monotonic() - start < 3
    assert result.status == "halted" and result.halt_reason == "deadline"
    assert result.still_running == ("answerer-agent",)
    assert "Agent answerer-agent is still running." in result.message


def test_done_run_with_failed_persona_names_it() -> None:  # T40
    def finisher(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("send_message", to="flaky-agent", message="hello")
        if last.role == "tool" and last.tool_call_id == "c-send_message":
            return call("complete_task", task_id="t1", result="all good")
        return say("ok")

    def flaky(messages: list[Message], tools: list[ToolSpec]) -> Any:
        raise ValueError("boom")

    slowed = [False]

    def slow_first_event(event: TeamEvent) -> None:
        if not slowed[0]:  # the coordinator is busy here while the agents finish and fail
            slowed[0] = True
            time.sleep(0.8)

    result = _team(
        {"finisher-agent": finisher, "flaky-agent": flaky},
        [TaskSpec("t1", "x", assignee="finisher-agent")],
        observer=slow_first_event,
    )
    assert result.status == "done" and result.results == {"t1": "all good"}
    assert "flaky-agent failed (ValueError)" in result.message
    assert "all good" not in repr(result)


def test_planted_marker_never_in_events_logs_errors(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:  # T31 (team part)
    caplog.set_level(logging.DEBUG)
    events: list[TeamEvent] = []

    def asker(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("send_message", to="answerer-agent", message="q " + MARKER)
        if last.content.startswith("Message "):
            return call("complete_task", task_id="t1", result="r " + MARKER)
        return say("ok " + MARKER)

    def answerer(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.role == "tool":
            return say("ok")
        if last.content.startswith("Message "):
            mid = int(last.content.split()[1])
            return call("send_message", to="asker-agent", message="a " + MARKER, reply_to=mid)
        return say("?")

    personas = [Persona(n, "builder", system="sys " + MARKER) for n in ROUND_TRIP]
    result = run_team(
        personas,
        [TaskSpec("t1", "desc " + MARKER, assignee="asker-agent")],
        llm_for=lambda p: FnLLM({"asker-agent": asker, "answerer-agent": answerer}[p.name]),
        observer=events.append,
    )
    assert result.status == "done" and result.results == {"t1": "r " + MARKER}
    visible = repr(events) + repr(result) + result.message + caplog.text
    assert MARKER not in visible and MARKER.lower() not in visible.lower()
    out = capsys.readouterr()
    assert MARKER not in out.out + out.err
    errors: list[BaseException] = []
    for bad in (
        lambda: run_team([], [TaskSpec("t1", MARKER)]),
        lambda: run_team([Persona(MARKER, "x")], [TaskSpec("t1", MARKER)]),
        lambda: run_team([Persona("a-agent", "x")], [TaskSpec("t1", "x", ("t0",))]),
    ):
        with pytest.raises(GraphError) as exc_info:
            bad()
        errors.append(exc_info.value)
    for err in errors:
        blob = f"{err!s}|{err!r}|{err.args}"
        assert MARKER not in blob and MARKER.lower() not in blob.lower()
        assert err.__context__ is None and err.__cause__ is None


class _Hostile(Exception):
    def __str__(self) -> str:
        raise RuntimeError(MARKER)

    def __repr__(self) -> str:
        raise RuntimeError(MARKER)

    @property
    def errno(self) -> int:
        raise RuntimeError(MARKER)

    @property  # type: ignore[misc]
    def __class__(self) -> type:  # type: ignore[override]
        raise RuntimeError(MARKER)


def test_hostile_callables_contained(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:  # T32 (team part)
    caplog.set_level(logging.DEBUG)

    def hostile_llm(messages: list[Message], tools: list[ToolSpec]) -> Any:
        raise _Hostile()

    def asker(messages: list[Message], tools: list[ToolSpec]) -> Any:
        return call("explode") if messages[-1].role == "user" else say("ok")

    class Explode:
        spec = ToolSpec("explode", "Raises a hostile error.", {"type": "object"})

        def run(self, arguments: dict[str, Any]) -> str:
            raise _Hostile()

    def bad_observer(event: TeamEvent) -> None:
        raise _Hostile()

    # hostile model, hostile tool, hostile observer, hostile llm_for
    r1 = _team({"a-agent": hostile_llm}, [TaskSpec("t1", "x")], observer=bad_observer)
    r2 = run_team(
        [Persona("a-agent", "b", tools=(Explode(),))],
        [TaskSpec("t1", "x")],
        llm_for=lambda p: FnLLM(asker),
    )

    def bad_factory(p: Persona) -> LLM:
        raise _Hostile()

    r3 = run_team([Persona("a-agent", "b")], [TaskSpec("t1", "x")], llm_for=bad_factory)
    for res in (r1, r2, r3):
        assert res.status == "failed" and res.results == {}
        assert set(res.failed_agents) == {"a-agent"}
        assert res.failed_agents["a-agent"] in {"Exception", "RuntimeError"}
    assert r1.observer_errors > 0
    seen = capsys.readouterr()
    assert seen.out == "" and seen.err == ""
    assert MARKER not in caplog.text + repr(r1) + repr(r2) + repr(r3)


def test_send_message_tool_rejects_odd_arguments() -> None:
    from master_finhub.orchestration.message_bus import MessageBus

    bus = MessageBus()
    tool = SendMessageTool(bus.register("a-agent"))
    bus.register("b-agent")
    for args in ({}, {"to": 5, "message": "x"}, {"to": "b-agent", "message": "x", "reply_to": "1"}):
        assert tool.run(args).startswith("Error: send_message needs text")
    assert tool.run({"to": "ghost-agent", "message": MARKER}).startswith("Error: Unknown recipient")
    assert MARKER not in tool.run({"to": "ghost-agent", "message": MARKER})
    assert tool.run({"to": "all", "message": "hi"}) == "Delivered to 1 agents."


# ----------------------------------------------------------------------------- workflow, guard
def test_workflow_reexports_are_slice6_objects() -> None:  # T30
    from master_finhub.orchestration import graph

    for name in workflow.__all__:
        assert getattr(workflow, name) is getattr(graph, name)


def _child(*args: str) -> subprocess.CompletedProcess[bytes]:
    import os

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, str(CHILD), *args], env=env, capture_output=True, timeout=90, check=False
    )


def test_workflow_resume_after_real_kill_reruns_only_unfinished(tmp_path: Path) -> None:
    ws, side = tmp_path / "ws", tmp_path / "side.txt"
    ws.mkdir()
    killed = _child("kill", str(ws), "wf-run", str(side))
    assert killed.returncode == 9, killed.stderr
    assert side.read_text(encoding="utf-8").split() == ["fetch", "check"]
    resumed = _child("resume", str(ws), "wf-run", str(side))
    assert resumed.returncode == 0, resumed.stderr
    assert resumed.stdout.decode().split() == ["status=done", "note=NOTE(CHECKED(synthetic-topic))"]
    # fetch (an agent node, finished before the kill) is NOT run again; check and note are
    assert side.read_text(encoding="utf-8").split() == ["fetch", "check", "check", "note"]


def test_empty_string_denial_blocks(monkeypatch: pytest.MonkeyPatch) -> None:  # T41
    from master_finhub.orchestration.modes.subagent import _both
    from master_finhub.runtime.loop import AgentLoop

    class FalsyStr(str):
        def __bool__(self) -> bool:
            return False

    ran = [0]

    class Probe:
        spec = ToolSpec("probe", "Counts runs.", {"type": "object"})

        def run(self, arguments: dict[str, Any]) -> str:
            ran[0] += 1
            return "ran"

    def script(messages: list[Message], tools: list[ToolSpec]) -> Any:
        return call("probe") if messages[-1].role == "user" else say("done")

    for denial in ("", FalsyStr("")):
        ran[0] = 0
        parent: Callable[[ToolCall], str | None] = lambda c, d=denial: d
        child: Callable[[ToolCall], str | None] = lambda c: None
        combined = _both(parent, child)
        assert combined(ToolCall("c1", "probe", {})) is denial
        AgentLoop(FnLLM(script), [Probe()], guard=combined).run("go")
        assert ran[0] == 0
        AgentLoop(FnLLM(script), [Probe()], guard=parent).run("go")
        assert ran[0] == 0
    monkeypatch.setattr(safety, "check_command", lambda value, policy=None: "")
    assert guard_tool_call(ToolCall("c1", "shell", {"command": "ls"})) == ""
