"""C8 proof: advisory repeat-call reminder (synthetic data only, no network).

Every fake credential is assembled at runtime so no complete token shape is committed.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from master_finhub.runtime.context import CLIP_MARKER, ContextManager, balanced_cuts
from master_finhub.runtime.loop import (
    UNCERTAIN_RESULT,
    AgentLoop,
    AgentLoopError,
    AssistantMessage,
    LoopSnapshot,
    Message,
    ToolCall,
    ToolSpec,
)
from master_finhub.runtime.repeat_reminder import (
    FIRM,
    GENTLE,
    MAX_KEY_CHARS,
    REMIND_AT,
    RepeatReminder,
    _call_key,
)
from master_finhub.tools.secret_scan import redact_secrets

PLAIN = "plain-result"
SUMMARY = "<compacted-summary>"
AWS = "AKIA" + "FAKE" * 3 + "0000"
K: dict[str, Any] = {"x": 1}


def _notice(count: int) -> str:
    """What the design says the result of the count-th identical call must end with."""
    if count == 3:
        return "\n\n" + GENTLE
    return "\n\n" + FIRM.format(count=count) if count in (5, 8) else ""


class _Tool:
    def __init__(self, name: str = "echo", out: str = PLAIN, boom: bool = False) -> None:
        self.spec = ToolSpec(name=name, description="test tool", parameters={})
        self.out, self.boom, self.runs = out, boom, 0

    def run(self, arguments: dict[str, Any]) -> str:
        self.runs += 1
        time.sleep(0)  # let another thread run, for the sharing tests
        if self.boom:
            raise ValueError("boom")
        return self.out


class _Seq:
    """One assistant turn per entry: a list of ToolCall, or a str for a final answer."""

    def __init__(self, turns: list[list[ToolCall] | str]) -> None:
        self.turns = list(turns)
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.seen.append(list(messages))
        turn = self.turns.pop(0) if self.turns else "done"
        return AssistantMessage(turn) if isinstance(turn, str) else AssistantMessage("", turn)


def _calls(*args_list: dict[str, Any], name: str = "echo") -> list[list[ToolCall]]:
    return [[ToolCall(f"c{i}", name, a)] for i, a in enumerate(args_list, start=1)]


def _tool_texts(snaps: list[LoopSnapshot]) -> list[str]:
    return [m.content for m in snaps[-1].messages if m.role == "tool"]


def _run(turns: list[list[ToolCall] | str], tools: list[Any] | None = None, **kw: Any) -> list[str]:
    """Run to the end; return every tool message in order."""
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_Seq(turns), tools or [_Tool()], 99, checkpoint=snaps.append, **kw)
    assert loop.run("go") == "done"
    return _tool_texts(snaps)


def test_third_identical_call_ends_with_the_reminder() -> None:
    tool = _Tool()
    out = _run([*_calls(K, K, K), "done"], [tool])
    assert out == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]
    assert tool.runs == 3  # the calls still ran


def test_reminder_pattern_over_twenty_identical_calls() -> None:
    out = _run([*_calls(*[K] * 20), "done"])
    assert out == [PLAIN + _notice(n) for n in range(1, 21)]
    assert REMIND_AT == (3, 5, 8)  # 4, 6, 7 and 9 and above stay silent


def test_reminder_texts_are_pinned() -> None:
    out = _run([*_calls(*[K] * 8), "done"])
    assert out[2] == PLAIN + (
        "\n\n[advisory] The same tool call, with the same arguments, has now been issued 3 times "
        "in a row. Read the earlier results again; if the task is unfinished, change the "
        "arguments or the approach."
    )
    for n in (5, 8):
        assert out[n - 1] == PLAIN + (
            "\n\n[advisory] This exact call (same tool, same arguments) has now been issued "
            f"{n} times in a row. More repeats are unlikely to help: use a different tool or "
            "different arguments, or give your final answer with what you have."
        )


def test_reminder_never_quotes_arguments_output_or_tool_name() -> None:
    args = {"x": "SENTINEL-ARG-77", "tail": {"k": "SENTINEL-NEST-66"}}
    out = _run(
        [*_calls(*[args] * 8, name="sentinel_tool"), "done"],
        [_Tool("sentinel_tool", out="SENTINEL-OUT-88")],
    )
    for n, text in enumerate(out, start=1):
        notice = text[len("SENTINEL-OUT-88") :]
        assert text.startswith("SENTINEL-OUT-88") and notice == _notice(n)
        for secret in ("SENTINEL", "sentinel_tool"):
            assert secret not in notice


def test_key_order_does_not_matter() -> None:
    ab, ba = {"b": 1, "a": 2}, {"a": 2, "b": 1}
    assert _run([*_calls(ba, ab, ba), "done"])[2].endswith(GENTLE)
    nested1 = {"o": {"d": 1, "c": [{"z": 1, "y": 2}]}, "l": [3, 4]}
    nested2 = {"l": [3, 4], "o": {"c": [{"y": 2, "z": 1}], "d": 1}}
    assert _run([*_calls(nested1, nested2, nested1), "done"])[2].endswith(GENTLE)


DIFFERENT: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = [
    ("echo", {"x": 1}, "other", {"x": 1}),  # the tool name is part of the key
    ("echo", {"x": 1}, "echo", {"x": 2}),
    ("echo", {"x": 1}, "echo", {"y": 1}),
    ("echo", {"x": 1}, "echo", {"x": "1"}),
    ("echo", {"x": 1}, "echo", {"x": True}),
    ("echo", {"x": 1}, "echo", {"x": 1.0}),
    ("echo", {"x": [1, 2]}, "echo", {"x": [2, 1]}),  # list order is data
    ("echo", {}, "echo", {"x": None}),
    ("echo", {"x": {"a": 1}}, "echo", {"x": {"a": 2}}),
    ("echo", {"x": 1}, "echo", {"x": 1, "y": 1}),
]


@pytest.mark.parametrize(("n1", "a1", "n2", "a2"), DIFFERENT)
def test_different_calls_are_never_merged(
    n1: str, a1: dict[str, Any], n2: str, a2: dict[str, Any]
) -> None:
    turns: list[list[ToolCall] | str] = [
        [ToolCall("c1", n1, a1)],
        [ToolCall("c2", n2, a2)],
        [ToolCall("c3", n2, a2)],
        "done",
    ]
    assert _run(turns, [_Tool("echo"), _Tool("other")]) == [PLAIN] * 3  # B, B is only two in a row


def test_only_consecutive_calls_count_and_a_different_call_resets() -> None:
    other = {"x": 2}
    assert _run([*_calls(K, K, other, K, K, K), "done"]) == [PLAIN] * 5 + [PLAIN + "\n\n" + GENTLE]
    assert _run([*_calls(K, K, other, K), "done"]) == [PLAIN] * 4  # not a total of three
    assert _run([*_calls(K, other, K, other, K, other), "done"]) == [PLAIN] * 6  # ping-pong


def test_a_new_prompt_resets_the_count() -> None:
    llm = _Seq([*_calls(K, K), "done", *_calls(K), "done"])
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    assert _tool_texts(snaps) == [PLAIN, PLAIN]
    loop.run("second")  # same instance: a 3rd identical call overall, but a new chain
    assert _tool_texts(snaps) == [PLAIN]


def test_a_run_that_raised_does_not_leak_its_count_into_the_next_run() -> None:
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_Seq([*_calls(K, K, K), "done"]), [_Tool()], 2, checkpoint=snaps.append)
    with pytest.raises(AgentLoopError, match="max_steps"):
        loop.run("first")  # two identical calls, then the step limit
    loop.run("second")  # one more identical call: a new chain, so no reminder
    assert _tool_texts(snaps) == [PLAIN]


def test_the_key_ignores_the_tool_output() -> None:
    class _Counting(_Tool):
        def run(self, arguments: dict[str, Any]) -> str:
            super().run(arguments)
            return f"call number {self.runs}"

    out = _run([*_calls(K, K, K), "done"], [_Counting()])
    assert out == ["call number 1", "call number 2", "call number 3\n\n" + GENTLE]


def _pending_snapshot(*calls: ToolCall) -> LoopSnapshot:
    return LoopSnapshot(1, (Message("user", "go"), Message("assistant", "", calls)))


def test_resume_restarts_the_count_and_the_rerun_path_counts() -> None:
    a, b, c = (ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3))
    snaps: list[LoopSnapshot] = []
    # run() leaves a chain of two on this instance; resume() must not continue it.
    loop = AgentLoop(_Seq([*_calls(K, K), "done", "done"]), [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    loop.resume(_pending_snapshot(a), in_flight="rerun")
    assert _tool_texts(snaps) == [PLAIN]
    # rerun (via _uncertain) counts as call 1, the next pending call as 2, the model's as 3.
    snaps.clear()
    fresh = AgentLoop(_Seq([[c], "done"]), [_Tool()], 99, checkpoint=snaps.append)
    fresh.resume(_pending_snapshot(a, b), in_flight="rerun")
    assert _tool_texts(snaps) == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_uncertain_results_are_neither_counted_nor_given_a_reminder() -> None:
    a, b, c = (ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3))
    snaps: list[LoopSnapshot] = []
    llm = _Seq(["done"])
    AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append).resume(
        _pending_snapshot(a, b, c), in_flight="report_unknown"
    )
    assert _tool_texts(snaps) == [UNCERTAIN_RESULT, PLAIN, PLAIN]  # c1 not counted: c3 is no 3rd


def test_uncertain_results_from_a_missing_tool_or_a_guard_are_not_counted() -> None:
    a, b, c = (ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3))
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(
        _Seq(["done"]), [_Tool()], 99, guard=lambda call: "nope", checkpoint=snaps.append
    )
    loop.resume(_pending_snapshot(a, b, c), in_flight="rerun")
    assert _tool_texts(snaps) == [UNCERTAIN_RESULT, "Error: nope", "Error: nope"]


def test_it_never_vetoes_skips_or_changes_a_call() -> None:
    tool, seen = _Tool(), []

    def guard(call: ToolCall) -> str | None:
        seen.append(call)
        return None

    out = _run([*_calls(*[K] * 10), "done"], [tool], guard=guard)
    assert tool.runs == 10 and len(seen) == 10 and len(out) == 10
    assert all(t.startswith(PLAIN) for t in out)


def test_the_tool_and_the_guard_receive_exactly_what_the_model_sent() -> None:
    args: dict[str, Any] = {"b": 2, "a": [1, {"z": 1, "y": "é"}]}
    got: list[Any] = []
    tool, seen = _Tool(), []

    def run(arguments: dict[str, Any]) -> str:
        got.append(arguments)
        return PLAIN

    tool.run = run  # type: ignore[method-assign]

    def guard(call: ToolCall) -> str | None:
        seen.append((call.id, call.name, call.arguments))
        return None

    _run([*_calls(*[args] * 10), "done"], [tool], guard=guard)
    assert got == [args] * 10 and [list(g) for g in got] == [["b", "a"]] * 10
    assert [list(g["a"][1]) for g in got] == [["z", "y"]] * 10
    assert seen == [(f"c{i}", "echo", args) for i in range(1, 11)]
    assert [list(a) for _, _, a in seen] == [["b", "a"]] * 10


def test_a_guard_denial_is_counted_and_gets_the_reminder() -> None:
    tool, seen = _Tool(), []

    def guard(call: ToolCall) -> str | None:
        seen.append(call)
        return "nope"

    out = _run([*_calls(K, K, K), "done"], [tool], guard=guard)
    assert out == ["Error: nope", "Error: nope", "Error: nope\n\n" + GENTLE]
    assert tool.runs == 0 and len(seen) == 3  # still denied, guard asked once per call


def test_tool_errors_and_unknown_tools_are_counted_too() -> None:
    boom = "Error: tool 'echo' failed: ValueError: boom"
    out = _run([*_calls(K, K, K), "done"], [_Tool(boom=True)])
    assert out == [boom, boom, boom + "\n\n" + GENTLE]
    miss = "Error: Unknown tool 'nope'. Available tools: echo."
    out = _run([*_calls(K, K, K, name="nope"), "done"])
    assert out == [miss, miss, miss + "\n\n" + GENTLE]


def test_the_reminder_survives_redaction_and_is_not_altered_by_it() -> None:
    for n in (3, 5, 8):
        text = (GENTLE if n == 3 else FIRM.format(count=n)).strip()
        assert redact_secrets(text) == (text, ())
    out = _run([*_calls(K, K, K), "done"], [_Tool(out=f"key {AWS}")])
    assert out == ["key [REDACTED:aws-access-key]"] * 2 + [
        "key [REDACTED:aws-access-key]\n\n" + GENTLE
    ]
    # an unterminated private-key block is redacted to the end of the text: the notice is outside
    unclosed = "-----BEGIN " + "PRIVATE KEY-----\nTUFERVVQ"
    out = _run([*_calls(K, K, K), "done"], [_Tool(out=unclosed)])
    assert out[2] == "[REDACTED:private-key]\n\n" + GENTLE


def test_max_steps_still_raises_and_the_last_result_is_saved_with_its_reminder() -> None:
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_Seq(_calls(K, K, K, K)), [_Tool()], 3, checkpoint=snaps.append)
    with pytest.raises(AgentLoopError, match=r"max_steps \(3\) exceeded"):
        loop.run("go")
    assert _tool_texts(snaps) == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_the_call_and_result_pair_is_never_split_or_lost() -> None:
    snaps: list[LoopSnapshot] = []  # LoopSnapshot validates pairing on every save
    three = [ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3)]
    llm = _Seq([three, "done"])
    AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append).run("go")
    roles = [m.role for m in snaps[-1].messages]
    assert roles == ["user", "assistant", "tool", "tool", "tool", "assistant"]
    tools = [m for m in snaps[-1].messages if m.role == "tool"]
    assert [m.tool_call_id for m in tools] == ["c1", "c2", "c3"]
    assert [m.content for m in tools] == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_compaction_neither_resets_the_count_nor_splits_a_pair() -> None:
    big = "y" * 1700  # ~425 estimated tokens each: a summary replaces old turns, no clip
    llm = _Seq([*_calls(*[K] * 9), "done"])
    ctx = ContextManager(context_window_tokens=3000, clip_budget_tokens=500)
    assert _run_with(llm, _Tool(out=big), ctx) == "done"
    summarised = [i for i, s in enumerate(llm.seen) if any(SUMMARY in m.content for m in s)]
    assert summarised and summarised[0] < 8  # compaction ran before the 8th call's reminder
    for seen in llm.seen:
        assert balanced_cuts(seen)[-1]  # no orphan result, no call left without its result
    latest = [s[-1].content for s in llm.seen[1:10]]  # the result each model turn just received
    assert latest == [big + _notice(n) for n in range(1, 10)]


def _run_with(llm: _Seq, tool: _Tool, ctx: ContextManager) -> str:
    return AgentLoop(llm, [tool], 99, context=ctx).run("go")


def test_a_clipped_long_result_keeps_its_reminder_in_the_tail() -> None:
    llm = _Seq([*_calls(K, K, K), "done"])
    _run_with(llm, _Tool(out="z" * 50_000), ContextManager())
    last = llm.seen[3][-1].content  # what the model saw after the third call
    assert CLIP_MARKER in last and last.endswith("\n\n" + GENTLE)


class _Boom(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise RuntimeError("boom")


def _circular() -> dict[str, Any]:
    d: dict[str, Any] = {}
    d["self"] = d
    return d


def _deep() -> dict[str, Any]:
    leaf: Any = 0
    for _ in range(100_000):  # past the json.dumps recursion limit on 3.10 to 3.13
        leaf = [leaf]
    return {"x": leaf}


UNKEYABLE: list[dict[Any, Any]] = [
    {"x": object()},
    {"x": {1, 2}},
    {"x": b"bytes"},
    {1: "a", "b": 2},  # keys that cannot be sorted together
    _circular(),
    _deep(),
    _Boom(x=1),
    {"x": "a" * (MAX_KEY_CHARS + 1)},  # over the size cap
]


@pytest.mark.parametrize("args", UNKEYABLE, ids=range(len(UNKEYABLE)))
def test_unkeyable_arguments_fail_open_with_no_reminder_and_no_exception(
    args: dict[Any, Any],
) -> None:
    tool = _Tool()
    out = _run([*_calls(*[args] * 5), "done"], [tool])
    assert out == [PLAIN] * 5 and tool.runs == 5


def test_an_unkeyable_call_resets_the_chain() -> None:
    over = {"x": "a" * (MAX_KEY_CHARS + 1)}  # no exception, but no key either
    for bad in ({"x": object()}, over):
        assert _run([*_calls(K, K, bad, K), "done"]) == [PLAIN] * 4
        assert _run([*_calls(K, K, bad, K, K, K), "done"])[5].endswith(GENTLE)


def test_size_cap_boundary() -> None:
    assert MAX_KEY_CHARS == 100_000
    base = len(json.dumps(["echo", {"x": ""}], separators=(",", ":")))
    at_cap = {"x": "a" * (MAX_KEY_CHARS - base)}
    over = {"x": "a" * (MAX_KEY_CHARS - base + 1)}
    assert _call_key("echo", at_cap) is not None
    assert _call_key("echo", over) is None
    assert _run([*_calls(*[at_cap] * 3), "done"])[2].endswith(GENTLE)
    assert _run([*_calls(*[over] * 3), "done"])[2] == PLAIN


def test_state_is_one_digest_and_one_count_whatever_the_arguments() -> None:
    r = RepeatReminder()
    for i in range(2000):
        r.observe("echo", {"x": f"{i}" * 40})
    assert len(repr(vars(r))) < 200
    r.observe("echo", {"x": "q" * 90_000})
    assert len(repr(vars(r))) < 200


def test_two_loop_instances_share_no_state() -> None:
    inner_tool = _Tool()
    inner_snaps: list[LoopSnapshot] = []
    inner = AgentLoop(_Seq([*_calls(K), "done"]), [inner_tool], 99, checkpoint=inner_snaps.append)

    class _Nest(_Tool):
        def run(self, arguments: dict[str, Any]) -> str:
            if self.runs == 1:  # during the outer loop's 2nd call another loop runs to the end
                inner.run("inner")
            return super().run(arguments)

    out = _run([*_calls(K, K, K), "done"], [_Nest()])
    assert out == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]
    assert _tool_texts(inner_snaps) == [PLAIN]


def test_threads_with_their_own_loops_each_see_their_own_pattern() -> None:
    results: list[list[str]] = []

    def work() -> None:
        results.append(_run([*_calls(*[K] * 12), "done"]))

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 8
    assert all(r == [PLAIN + _notice(n) for n in range(1, 13)] for r in results)


CHILD = """
import json
from master_finhub.runtime.repeat_reminder import RepeatReminder
r = RepeatReminder()
a = {"b": 1, "a": [{"d": 1, "c": 2}]}
b = {"a": [{"c": 2, "d": 1}], "b": 1}
print(json.dumps([r.observe("echo", a if i % 2 else b) for i in range(12)]))
"""


def test_output_does_not_depend_on_the_hash_seed() -> None:
    root = Path(__file__).resolve().parent.parent
    outs = set()
    for seed in ("0", "1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(root / "src")}
        done = subprocess.run(
            [sys.executable, "-B", "-c", CHILD],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        outs.add(done.stdout)
    assert len(outs) == 1
    assert json.loads(outs.pop()) == [_notice(n) for n in range(1, 13)]


class _Interrupt(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise KeyboardInterrupt


def test_a_keyboard_interrupt_is_not_swallowed() -> None:
    with pytest.raises(KeyboardInterrupt):
        RepeatReminder().observe("echo", _Interrupt(x=1))


# --- revision 2: classes the round-1 audit found unpinned (B1-B5) and two one-line follow-ups ---


class _Mem(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise MemoryError


class _Ovf(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise OverflowError


@pytest.mark.parametrize("cls", [_Mem, _Ovf])
def test_other_exceptions_fail_open(cls: type[dict[str, Any]]) -> None:
    r = RepeatReminder()
    assert r.observe("echo", cls(x=1)) == ""
    assert _run([*_calls(*[cls(x=1)] * 3), "done"]) == [PLAIN] * 3  # the call itself is unharmed


def test_names_are_exact() -> None:
    r = RepeatReminder()
    assert [r.observe(n, K) for n in ("echo", "Echo", "echo", "echo ", "echo")] == [""] * 5


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ({"x": "A"}, {"x": "a"}),
        ({"x": "a b"}, {"x": "ab"}),
        ({"x": None}, {"x": ""}),
        ({"x": "null"}, {"x": ""}),
        ({"x": " a"}, {"x": "a"}),
    ],
)
def test_values_are_exact(a: dict[str, Any], b: dict[str, Any]) -> None:
    r = RepeatReminder()
    assert [r.observe("echo", v) for v in (a, b, a)] == [""] * 3  # a, b, a is never a run


def test_digest_is_full_and_distinct() -> None:
    keys = {_call_key("echo", {"x": i}) for i in range(500)}
    assert len(keys) == 500 and all(k is not None and len(k) == 64 for k in keys)


def test_unicode_arguments_are_tracked() -> None:
    u = {"x": "xin chào, tiếng Việt éạ"}
    assert _run([*_calls(u, u, u), "done"])[2].endswith(GENTLE)


def test_nan_arguments_are_tracked() -> None:
    n = {"x": float("nan")}
    assert _run([*_calls(n, n, n), "done"])[2].endswith(GENTLE)


def test_empty_result_gets_the_reminder() -> None:
    assert _run([*_calls(K, K, K), "done"], [_Tool(out="")])[2] == "\n\n" + GENTLE


def test_huge_result_gets_the_reminder() -> None:
    out = _run([*_calls(K, K, K), "done"], [_Tool(out="q" * 200_000)])
    assert out[2].endswith(GENTLE) and len(out[2]) > 200_000


def test_chain_crosses_turns_into_a_batch() -> None:
    def c(i: int) -> ToolCall:
        return ToolCall(f"c{i}", "echo", K)

    out = _run([[c(1)], [c(2), c(3)], "done"])
    assert out == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_resume_with_a_new_user_message_resets() -> None:
    snaps: list[LoopSnapshot] = []
    llm = _Seq([*_calls(K, K), "done", *_calls(K), "done"])
    loop = AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    prior = snaps[-1]
    snaps.clear()
    # the team.py path: history plus a new user message, no call pending
    loop.resume(LoopSnapshot(prior.step, (*prior.messages, Message("user", "again"))))
    assert _tool_texts(snaps) == [PLAIN] * 3  # two earlier results; the new call is a first


def test_a_tool_that_edits_its_own_arguments_cannot_merge_calls() -> None:
    class _Pop(_Tool):
        def run(self, arguments: dict[str, Any]) -> str:
            arguments.pop("t", None)
            return super().run(arguments)

    a1, b, a2 = {"x": 1, "t": 0}, {"x": 1}, {"x": 1, "t": 0}  # A, B, A: no two alike in a row
    assert _run([*_calls(a1, b, a2), "done"], [_Pop()]) == [PLAIN] * 3
    c1, c2, c3 = {"x": 1, "t": 0}, {"x": 1, "t": 0}, {"x": 1, "t": 0}  # three real repeats
    assert _run([*_calls(c1, c2, c3), "done"], [_Pop()])[2].endswith(GENTLE)
