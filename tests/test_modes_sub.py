"""Slice 7 proof tests, part 3: sub-agent mode, the thread budget and engine scope."""

from __future__ import annotations

import contextvars
import logging
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from modes_support import (
    MARKER,
    FnLLM,
    Gate,
    _quiet_after,  # noqa: F401 - autouse fixture
    call,
    say,
    settle,
)

from master_finhub.orchestration.graph import Limits
from master_finhub.orchestration.graph_store import GraphError
from master_finhub.orchestration.modes.subagent import (
    _BUDGET,
    _SCOPE,
    MAX_AGENT_THREADS,
    REFUSED_UNSCOPED,
    DelegateTool,
    SubagentConfig,
    SubagentError,
    SubResult,
    SubTask,
    _scope,
    dispatch,
)
from master_finhub.orchestration.modes.task_board import TaskSpec
from master_finhub.orchestration.modes.team import Persona, TeamError, run_team
from master_finhub.runtime.loop import LLM, Message, Tool, ToolCall, ToolSpec
from master_finhub.tools.safety import DEFAULT_POLICY, make_guard


def _cfg(fn_for: Callable[[SubTask], Any], **kw: Any) -> SubagentConfig:
    return SubagentConfig(llm_for=lambda t: FnLLM(fn_for(t)), **kw)


def _tasks(*ids: str) -> list[SubTask]:
    return [SubTask(i, f"prompt {i}") for i in ids]


def _final(text: str) -> Callable[..., Any]:
    return lambda messages, tools: say(text)


# ----------------------------------------------------------------------------- basics
def test_subagent_concurrency_bound_measured() -> None:  # T25
    lock, now, peak = threading.Lock(), [0], [0]

    def fn_for(task: SubTask) -> Callable[..., Any]:
        def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
            with lock:
                now[0] += 1
                peak[0] = max(peak[0], now[0])
            time.sleep(0.08)
            with lock:
                now[0] -= 1
            return say("out-" + task.id)

        return fn

    config = _cfg(fn_for, limits=Limits(max_nodes=32, deadline_s=30.0, max_parallelism=3))
    result = dispatch(_tasks(*(f"t{i}" for i in range(9))), config=config)
    assert result.status == "done" and peak[0] == 3
    assert result.results["t4"] == SubResult("done", "out-t4")


def test_subagent_failure_isolation() -> None:  # T26
    def fn_for(task: SubTask) -> Callable[..., Any]:
        def boom(messages: list[Message], tools: list[ToolSpec]) -> Any:
            raise ValueError(MARKER)

        return boom if task.id == "b" else _final("out-" + task.id)

    result = dispatch(_tasks("a", "b", "c"), config=_cfg(fn_for))
    assert result.status == "failed" and result.halt_reason is None
    assert result.results["a"] == SubResult("done", "out-a")
    assert result.results["c"] == SubResult("done", "out-c")
    assert result.results["b"] == SubResult("failed", None, "ValueError")
    assert MARKER not in repr(result) and MARKER not in result.message
    assert "b (ValueError)" in result.message


def test_subagent_result_cap() -> None:  # T28
    def fn_for(task: SubTask) -> Callable[..., Any]:
        return _final("x" * (101 if task.id == "big" else 100))

    result = dispatch(_tasks("big", "ok"), config=_cfg(fn_for, max_result_bytes=102))
    assert result.results["big"] == SubResult("failed", None, "SubagentOutputTooLarge")
    assert result.results["ok"].status == "done" and result.status == "failed"
    assert "x" * 50 not in repr(result)


def test_subagent_deadline_reports_running_not_done() -> None:  # T29 + T38
    gate = Gate()

    def fn_for(task: SubTask) -> Callable[..., Any]:
        return (lambda m, t: gate.hang()) if task.id == "stuck" else _final("out")

    config = _cfg(fn_for, limits=Limits(max_nodes=8, deadline_s=0.3, max_parallelism=2))
    try:
        result = dispatch(_tasks("stuck", "fine"), config=config)
        assert result.status == "halted" and result.halt_reason == "deadline"
        assert (
            result.results["stuck"].status == "running" and result.results["stuck"].output is None
        )
        assert result.results["fine"].status == "done"
        assert "Helper stuck is still running." in result.message
        assert _BUDGET.free() == MAX_AGENT_THREADS - 2  # abandoned threads keep their slots
    finally:
        gate.release.set()
    assert settle() and _BUDGET.free() == MAX_AGENT_THREADS


def test_dispatch_validation_and_mandatory_deadline() -> None:
    llm = _final("x")
    cfg = _cfg(lambda t: llm)
    bad_limits = [
        Limits(deadline_s=None),
        Limits(deadline_s=0.0),
        Limits(deadline_s=float("inf")),
        Limits(deadline_s=float("nan")),
        Limits(deadline_s=14_401.0),
    ]
    for limits in bad_limits:
        with pytest.raises(SubagentError):
            dispatch(_tasks("a"), config=_cfg(lambda t: llm, limits=limits))
    for bad in (
        [],
        [SubTask("A", "x")],
        [SubTask("a", "x"), SubTask("a", "y")],
        [SubTask("a", "\ud800")],
    ):
        with pytest.raises(SubagentError):
            dispatch(bad, config=cfg)
    for kw in ({"max_depth": 0}, {"max_depth": 4}, {"max_steps": 0}, {"max_result_bytes": 0}):
        with pytest.raises(SubagentError):
            dispatch(_tasks("a"), config=_cfg(lambda t: llm, **kw))
    assert _BUDGET.free() == MAX_AGENT_THREADS


def test_subagent_results_identical_across_runs() -> None:  # T33 (dispatch part)
    def fn_for(task: SubTask) -> Callable[..., Any]:
        return _final("out-" + task.id)

    def run() -> object:
        res = dispatch(_tasks("a", "b", "c"), config=_cfg(fn_for))
        return (res.status, res.halt_reason, dict(res.results), res.message)

    first = run()
    assert all(run() == first for _ in range(20))


# ----------------------------------------------------------------------------- depth and scope
class _Direct:
    """A tool that calls dispatch() directly from a depth-2 agent: must be refused."""

    spec = ToolSpec("direct", "Calls dispatch directly.", {"type": "object"})

    def __init__(self, config_ref: list[SubagentConfig], seen: dict[str, str]) -> None:
        self.config_ref, self.seen = config_ref, seen

    def run(self, arguments: dict[str, Any]) -> str:
        try:
            dispatch(_tasks("zz"), config=self.config_ref[0])
        except SubagentError:
            self.seen["direct"] = "refused"
            return "refused"
        self.seen["direct"] = "started"
        return "started"


def _nested(seen: dict[str, Any]) -> tuple[SubagentConfig, list[SubagentConfig]]:
    holder: list[SubagentConfig] = []

    def fn_for(task: SubTask) -> Callable[..., Any]:
        def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
            seen.setdefault("tools_" + task.id, [s.name for s in tools])
            seen["depth_" + task.id] = getattr(_scope(), "depth", None)
            last = messages[-1]
            if last.role == "tool":
                return say(f"{task.id}<-{last.content}")
            if task.id == "c1":
                return call("delegate", tasks=[{"id": "g1", "prompt": "leaf"}])
            if task.id == "g1":
                return call("direct")
            return say("leaf " + task.id)

        return fn

    def tools_for(task: SubTask) -> Sequence[Tool]:
        extra: list[Tool] = [DelegateTool(holder[0])]  # offered at EVERY level
        return [*extra, _Direct(holder, seen)] if task.id == "g1" else extra

    holder.append(_cfg(fn_for, tools_for=tools_for))
    return holder[0], holder


def test_subagent_depth_limit() -> None:  # T27
    seen: dict[str, Any] = {}
    config, _ = _nested(seen)
    result = dispatch(_tasks("c1"), config=config)
    assert result.status == "done"
    assert seen["depth_c1"] == 1 and seen["depth_g1"] == 2
    assert "delegate" in seen["tools_c1"]  # level 1 may delegate
    assert "delegate" not in seen["tools_g1"]  # the last level is never offered it
    assert seen["direct"] == "refused"  # a direct dispatch from a depth-2 tool starts nothing
    assert result.results["c1"].output is not None and "g1<-refused" in result.results["c1"].output
    assert _BUDGET.free() == MAX_AGENT_THREADS


def test_hostile_callable_cannot_reset_depth_or_cap() -> None:  # T36
    seen: dict[str, Any] = {}
    holder: list[SubagentConfig] = []
    tried: list[str] = []

    def fn_for(task: SubTask) -> Callable[..., Any]:
        def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
            if messages[-1].role == "tool":
                return say("done")
            seen[task.id] = _scope().depth  # type: ignore[union-attr]
            if task.id == "g1":  # an llm_for-time callable tries dispatch() itself
                try:
                    dispatch(_tasks("zz"), config=holder[0])
                except SubagentError:
                    tried.append("refused")
            return (
                call("delegate", tasks=[{"id": "g1", "prompt": "x"}])
                if task.id == "c1"
                else say("leaf")
            )

        return fn

    inner = SubagentConfig(max_depth=3)  # tries to raise the cap
    holder.append(
        _cfg(
            fn_for,
            tools_for=lambda t: [
                DelegateTool(
                    SubagentConfig(
                        llm_for=holder[0].llm_for, max_depth=3, tools_for=holder[0].tools_for
                    )
                )
            ],
        )
    )
    assert inner.max_depth == 3
    result = dispatch(_tasks("c1"), config=holder[0])
    assert result.status == "done"
    assert seen == {"c1": 1, "g1": 2} and tried == ["refused"]


class _Shell:
    spec = ToolSpec("shell", "Run a command.", {"type": "object"})

    def __init__(self) -> None:
        self.ran = 0

    def run(self, arguments: dict[str, Any]) -> str:
        self.ran += 1
        return "ran"


def _deleg_then_shell(shell: _Shell, outputs: list[str]) -> Callable[[SubTask], Callable[..., Any]]:
    def fn_for(task: SubTask) -> Callable[..., Any]:
        def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
            last = messages[-1]
            if last.role == "tool":
                outputs.append(last.content)
                return say("finished")
            if task.id == "g1":
                return call("shell", command="rm -rf /")
            return call("delegate", tasks=[{"id": "g1", "prompt": "do it"}])

        return fn

    return fn_for


def test_child_guard_never_weaker_than_parent() -> None:  # T35
    shell, outputs = _Shell(), []
    allow_all = SubagentConfig(guard=lambda call: None)
    fn_for = _deleg_then_shell(shell, outputs)
    inner = SubagentConfig(
        llm_for=lambda t: FnLLM(fn_for(t)), tools_for=lambda t: [shell], guard=allow_all.guard
    )
    deleg = DelegateTool(inner)

    # team: the persona's delegate gets an allow-all config, but the team guard still applies
    def persona_fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("delegate", tasks=[{"id": "g1", "prompt": "do it"}])
        if last.role == "tool" and last.tool_call_id == "c-delegate":
            return call("complete_task", task_id="t1", result="x")
        return say("ok")

    result = run_team(
        [Persona("ops-agent", "b", tools=(deleg,))],
        [TaskSpec("t1", "x")],
        llm_for=lambda p: FnLLM(persona_fn),
    )
    assert result.status == "done" and shell.ran == 0
    assert any("Blocked by safety policy" in o for o in outputs)

    # root dispatch: strict root guard, the child delegates with an allow-all config
    shell2, outputs2 = _Shell(), []
    fn2 = _deleg_then_shell(shell2, outputs2)
    holder: list[SubagentConfig] = []
    holder.append(
        SubagentConfig(
            llm_for=lambda t: FnLLM(fn2(t)),
            tools_for=lambda t: (
                [
                    DelegateTool(
                        SubagentConfig(
                            llm_for=holder[0].llm_for,
                            tools_for=lambda x: [shell2],
                            guard=lambda c: None,
                        )
                    )
                ]
                if t.id == "c1"
                else [shell2]
            ),
        )
    )
    res = dispatch(_tasks("c1"), config=holder[0])
    assert res.status == "done" and shell2.ran == 0
    assert any("Blocked by safety policy" in o for o in outputs2)
    # a stricter child config can add denials
    strict = make_guard(DEFAULT_POLICY)
    assert strict(ToolCall("c", "shell", {"command": "rm -rf /"})) is not None


def test_delegate_tool_fails_closed_without_scope() -> None:  # T44
    ran = [0]

    def fn_for(task: SubTask) -> Callable[..., Any]:
        ran[0] += 1
        return _final("x")

    tool = DelegateTool(_cfg(fn_for))
    args = {"tasks": [{"id": "a", "prompt": "p"}]}
    outcomes: list[str] = []
    with ThreadPoolExecutor(1) as pool:
        outcomes.append(pool.submit(tool.run, args).result(5))
    raw = threading.Thread(target=lambda: outcomes.append(tool.run(args)))
    raw.start()
    raw.join(5)
    ctx = contextvars.copy_context()
    ctxed = threading.Thread(target=lambda: outcomes.append(ctx.run(tool.run, args)))
    ctxed.start()
    ctxed.join(5)
    assert outcomes == [REFUSED_UNSCOPED] * 3 and ran[0] == 0
    assert MARKER not in REFUSED_UNSCOPED and "Daniel" not in REFUSED_UNSCOPED
    assert getattr(_SCOPE, "value", None) is None

    # a scoped thread (a persona) dispatches
    def persona_fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("delegate", **args)
        if last.role == "tool" and last.tool_call_id == "c-delegate":
            return call("complete_task", task_id="t1", result=last.content)
        return say("ok")

    result = run_team(
        [Persona("ops-agent", "b", tools=(tool,))],
        [TaskSpec("t1", "x")],
        llm_for=lambda p: FnLLM(persona_fn),
    )
    assert result.status == "done" and result.results["t1"] == "[a] done:\nx" and ran[0] == 1


def test_delegate_tool_rejects_odd_arguments() -> None:
    seen: list[str] = []

    def persona_fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("delegate", tasks="nope")
        if last.role == "tool":
            seen.append(last.content)
            return call("complete_task", task_id="t1", result="x") if len(seen) == 1 else say("ok")
        return say("ok")

    tool = DelegateTool(SubagentConfig())
    result = run_team(
        [Persona("ops-agent", "b", tools=(tool,))],
        [TaskSpec("t1", "x")],
        llm_for=lambda p: FnLLM(persona_fn),
    )
    assert result.status == "done" and seen[0].startswith("Error: tasks must be a list")


# ----------------------------------------------------------------------------- thread budget
def test_thread_budget_caps_nested_fanout() -> None:  # T37
    base = threading.active_count()
    peak, stop = [0], threading.Event()

    def sample() -> None:
        while not stop.is_set():
            peak[0] = max(peak[0], threading.active_count() - base)
            time.sleep(0.002)

    refused = [0]
    holder: list[SubagentConfig] = []

    def child_fn_for(task: SubTask) -> Callable[..., Any]:
        def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
            time.sleep(0.4)
            return say("leaf")

        return fn

    holder.append(
        _cfg(child_fn_for, limits=Limits(max_nodes=8, deadline_s=30.0, max_parallelism=4))
    )
    deleg = DelegateTool(holder[0])

    def persona_fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
        last = messages[-1]
        if last.content.startswith("You have claimed"):
            return call("delegate", tasks=[{"id": f"h{i}", "prompt": "p"} for i in range(4)])
        if last.role == "tool" and last.tool_call_id == "c-delegate":
            refused[0] += "Not enough agent capacity" in last.content
            return call("complete_task", task_id=_task_id(messages), result="x")
        return say("ok")

    def _task_id(messages: list[Message]) -> str:
        return messages[0].content.split()[4].rstrip(":")

    personas = [Persona(f"p{i}-agent", "b", tools=(deleg,)) for i in range(16)]
    tasks = [TaskSpec(f"t{i}", "x", assignee=f"p{i}-agent") for i in range(16)]
    sampler = threading.Thread(target=sample)
    sampler.start()
    try:
        result = run_team(personas, tasks, llm_for=lambda p: FnLLM(persona_fn))
    finally:
        stop.set()
        sampler.join()
    assert result.status == "done"
    assert peak[0] <= MAX_AGENT_THREADS + 1  # +1 for the sampler thread itself
    assert refused[0] > 0  # the budget refused some dispatches with the capacity text
    assert settle() and _BUDGET.free() == MAX_AGENT_THREADS


def test_dispatch_refused_when_budget_exhausted() -> None:
    assert _BUDGET.reserve(MAX_AGENT_THREADS - 1)
    try:
        with pytest.raises(SubagentError) as exc_info:
            dispatch(_tasks("a", "b"), config=_cfg(lambda t: _final("x")))
        assert "Not enough agent capacity: 2 helpers asked for, 1 slots free." in str(
            exc_info.value
        )
        with pytest.raises(TeamError):
            run_team(
                [Persona("a-agent", "b"), Persona("b-agent", "b")],
                [TaskSpec("t1", "x")],
                llm_for=lambda p: FnLLM(_final("x")),
            )
    finally:
        _BUDGET.release(MAX_AGENT_THREADS - 1)
    assert _BUDGET.free() == MAX_AGENT_THREADS


def test_budget_slot_returned_when_thread_start_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # T42
    real_start = threading.Thread.start

    def patched(self: threading.Thread) -> None:
        args = getattr(self, "_args", ())
        if args and (args[0] == "b" or getattr(args[0], "name", None) == "b-agent"):
            raise RuntimeError("can't start new thread")
        real_start(self)

    monkeypatch.setattr(threading.Thread, "start", patched)
    result = dispatch(_tasks("a", "b", "c"), config=_cfg(lambda t: _final("out-" + t.id)))
    assert result.status == "failed" and result.results["b"].status == "failed"
    assert result.results["a"].status == "done" and result.results["c"].status == "done"
    assert settle() and _BUDGET.free() == MAX_AGENT_THREADS
    personas = [Persona("a-agent", "x"), Persona("b-agent", "x")]
    with pytest.raises(TeamError):
        run_team(personas, [TaskSpec("t1", "x")], llm_for=lambda p: FnLLM(_final("x")))
    assert settle() and _BUDGET.free() == MAX_AGENT_THREADS


def test_budget_never_exceeded_by_late_starting_threads() -> None:  # T43
    running, violations, lock = [0], [0], threading.Lock()
    base = threading.active_count()
    peak = [0]

    def fn_for(task: SubTask) -> Callable[..., Any]:
        def fn(messages: list[Message], tools: list[ToolSpec]) -> Any:
            time.sleep(0.002)
            with lock:
                running[0] += 1
                held = MAX_AGENT_THREADS - _BUDGET.free()
                violations[0] += running[0] > held  # a body is running without a slot
                peak[0] = max(peak[0], threading.active_count() - base)
            time.sleep(0.002)
            with lock:
                running[0] -= 1
            return say("x")

        return fn

    config = _cfg(fn_for, limits=Limits(max_nodes=4, deadline_s=0.001, max_parallelism=1))
    for _ in range(300):
        try:
            dispatch(_tasks("a"), config=config)
        except SubagentError:
            pass  # capacity refusal is fine; running outside the budget is not
    assert settle()
    assert violations[0] == 0 and peak[0] <= MAX_AGENT_THREADS


def test_ctrl_c_during_dispatch_returns_slots_after_children_end() -> None:  # N7
    import _thread

    gate = Gate()
    fired: list[float] = []

    def fn_for(task: SubTask) -> Callable[..., Any]:
        return lambda m, t: gate.hang()

    def interrupt() -> None:
        gate.started.wait(5)
        fired.append(time.monotonic())
        _thread.interrupt_main()

    timer = threading.Thread(target=interrupt)
    timer.start()
    caught = None
    try:
        dispatch(_tasks("a", "b"), config=_cfg(fn_for))
    except KeyboardInterrupt:
        caught = time.monotonic()
        held = MAX_AGENT_THREADS - _BUDGET.free()
    finally:
        timer.join()
    try:
        assert caught is not None and caught - fired[0] < 0.25
        assert held == 2  # the running children are still budgeted while they run
    finally:
        gate.release.set()
    assert settle() and _BUDGET.free() == MAX_AGENT_THREADS


# ----------------------------------------------------------------------------- compliance
def test_planted_marker_never_in_dispatch_outputs_logs_errors(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:  # T31 (dispatch part)
    caplog.set_level(logging.DEBUG)

    def fn_for(task: SubTask) -> Callable[..., Any]:
        def boom(messages: list[Message], tools: list[ToolSpec]) -> Any:
            raise ValueError(MARKER)

        return boom if task.id == "b" else _final("a " + MARKER)

    tasks = [SubTask("a", "q " + MARKER, system="s " + MARKER), SubTask("b", MARKER)]
    result = dispatch(tasks, config=_cfg(fn_for))
    assert result.results["a"].output == "a " + MARKER  # in the result for the caller only
    visible = repr(result) + result.message + caplog.text
    assert MARKER not in visible and MARKER.lower() not in visible.lower()
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    errors: list[BaseException] = []
    for bad in (
        lambda: dispatch([], config=_cfg(fn_for)),
        lambda: dispatch([SubTask(MARKER, "x")], config=_cfg(fn_for)),
        lambda: dispatch(tasks, config=_cfg(fn_for, limits=Limits(deadline_s=None))),
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

    @property
    def errno(self) -> int:
        raise RuntimeError(MARKER)


def test_hostile_callables_contained_in_dispatch(capsys: pytest.CaptureFixture[str]) -> None:
    class Explode:
        spec = ToolSpec("explode", "Raises.", {"type": "object"})

        def run(self, arguments: dict[str, Any]) -> str:
            raise _Hostile()

    def hostile_llm(messages: list[Message], tools: list[ToolSpec]) -> Any:
        raise _Hostile()

    def fn_for(task: SubTask) -> Callable[..., Any]:
        if task.id == "m":
            return hostile_llm
        if task.id == "t":
            return lambda m, t: call("explode") if m[-1].role == "user" else say("ok")
        return _final("fine")

    def tools_for(task: SubTask) -> Sequence[Tool]:
        if task.id == "tf":
            raise _Hostile()
        return [Explode()] if task.id == "t" else []

    def llm_for(task: SubTask) -> LLM:
        if task.id == "lf":
            raise _Hostile()
        return FnLLM(fn_for(task))

    result = dispatch(
        _tasks("m", "t", "tf", "lf", "ok"),
        config=SubagentConfig(llm_for=llm_for, tools_for=tools_for),
    )
    assert result.results["ok"].status == "done"
    for tid in ("m", "tf", "lf"):
        assert result.results[tid].status == "failed"
        assert result.results[tid].error_type == "Exception"
    assert result.results["t"].status == "failed"  # the loop's own str(exc) raised: class only
    seen = capsys.readouterr()
    assert seen.out == "" and seen.err == ""
    assert MARKER not in repr(result) and settle()
