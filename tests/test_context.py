"""Slice 2 proof tests for runtime/context.py (synthetic data only)."""

import json
import math
from typing import Any

import pytest

from master_finhub.runtime.context import (
    CLIP_MARKER,
    ContextManager,
    ContextOverflowError,
    balanced_cuts,
    clip_text,
    estimate_message,
    estimate_tokens,
    summarise,
)
from master_finhub.runtime.loop import (
    AgentLoop,
    AssistantMessage,
    Message,
    ToolCall,
    ToolSpec,
)

WINDOW = 6000  # threshold 4800, retain 960


def _mgr() -> ContextManager:
    return ContextManager(context_window_tokens=WINDOW)


def _filler(n: int, chars: int = 1000) -> list[Message]:
    return [Message("assistant", f"filler {i} " + "x" * chars) for i in range(n)]


def test_estimate_tokens_uses_ceil() -> None:
    assert estimate_tokens("x" * 12000) == 3000
    assert estimate_tokens("x" * 12001) == 3001
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("") == 0


def test_estimate_message_adds_block_role_and_call_overhead() -> None:
    args = {"b": 2, "a": "hello"}
    call = ToolCall("c1", "write_file", args)
    msg = Message("assistant", "x" * 10, tool_calls=(call,))
    arg_len = len(json.dumps(args, sort_keys=True))
    expected = (
        math.ceil(10 / 4) + 4 + math.ceil(len("write_file") / 4) + math.ceil(arg_len / 4) + 4 + 4
    )
    assert estimate_message(msg) == expected


def test_clip_3000_token_result_to_budget() -> None:
    text = "HEADSENTINEL" + "a" * 11976 + "TAILSENTINEL"
    assert len(text) == 12000 and estimate_tokens(text) == 3000
    out = clip_text(text)
    assert estimate_tokens(out) <= 2000
    assert len(out) <= 8000
    assert CLIP_MARKER in out
    assert out.startswith("HEADSENTINEL")
    assert out.endswith("TAILSENTINEL")


def test_clip_under_budget_returns_input_unchanged() -> None:
    text = "y" * 8000
    assert clip_text(text) == text


def test_clip_boundary_8001_chars_is_clipped() -> None:
    out = clip_text("z" * 8001)
    assert len(out) <= 8000
    assert CLIP_MARKER in out


def test_clip_rejects_budget_not_larger_than_marker() -> None:
    with pytest.raises(ValueError):
        clip_text("q" * 100, budget_tokens=1)


def test_clip_is_idempotent() -> None:
    text = "h" * 5000 + "m" * 5000 + "t" * 5000
    assert clip_text(clip_text(text)) == clip_text(text)


def test_fit_clips_tool_message_and_keeps_call_id() -> None:
    history = [
        Message("user", "task"),
        Message("assistant", "", tool_calls=(ToolCall("c1", "echo", {}),)),
        Message("tool", "L" * 12000, tool_call_id="c1"),
    ]
    snapshot = list(history)
    out = _mgr().fit(history)
    assert history == snapshot
    assert out[2].role == "tool" and out[2].tool_call_id == "c1"
    assert estimate_tokens(out[2].content) <= 2000
    assert CLIP_MARKER in out[2].content


def test_fit_under_threshold_returns_equal_new_list() -> None:
    history = [Message("user", "hi"), Message("assistant", "hello")]
    out = _mgr().fit(history)
    assert out == history and out is not history


def test_compaction_keeps_recent_tail_verbatim() -> None:
    history = [Message("user", "TASK-ALPHA")] + _filler(25) + [Message("assistant", "last one")]
    out = _mgr().fit(history)
    assert "<compacted-summary>" in out[1].content
    assert out[-1] == history[-1]
    assert len(out) < len(history)


def test_compaction_pins_first_user_message() -> None:
    history = [Message("user", "TASK-ALPHA")] + _filler(25)
    out = _mgr().fit(history)
    assert out[0] is history[0]
    assert "TASK-ALPHA" not in out[1].content


def _pair_history() -> list[Message]:
    calls = (ToolCall("c1", "echo", {"t": 1}), ToolCall("c2", "echo", {"t": 2}))
    return (
        [Message("user", "task")]
        + _filler(25)
        + [
            Message("assistant", "", tool_calls=calls),
            Message("tool", "r1", tool_call_id="c1"),
            Message("tool", "R" * 4000, tool_call_id="c2"),
            Message("assistant", "done"),
        ]
    )


def test_compaction_never_splits_call_result_pair() -> None:
    history = _pair_history()
    out = _mgr().fit(history)
    assert out[-4:] == history[-4:]  # tail starts at the assistant with the two calls
    open_calls: set[str] = set()
    for m in out:
        if m.role == "assistant":
            open_calls |= {c.id for c in m.tool_calls}
        elif m.role == "tool":
            assert m.tool_call_id in open_calls


def test_orphan_tool_result_raises() -> None:
    with pytest.raises(ValueError, match="orphan tool result at index 1"):
        balanced_cuts([Message("user", "t"), Message("tool", "r", tool_call_id="x")])
    history = [Message("user", "t")] + _filler(25) + [Message("tool", "r", tool_call_id="x")]
    with pytest.raises(ValueError, match="orphan tool result"):
        _mgr().fit(history)


def test_compaction_raises_when_nothing_compactable() -> None:
    history = [Message("user", "task"), Message("user", "SECRETSENTINEL" + "x" * 20000)]
    with pytest.raises(ContextOverflowError) as info:
        _mgr().fit(history)
    assert "#1 (user" in str(info.value)
    assert "SECRETSENTINEL" not in str(info.value)


def test_summary_is_deterministic() -> None:
    history = _pair_history()[1:10]
    assert summarise(history) == summarise(history)
    assert summarise(history).role == "user"


def test_retain_must_be_below_threshold() -> None:
    with pytest.raises(ValueError):
        ContextManager(threshold_ratio=0.1, retain_ratio=0.2)


def test_minimum_window_validated() -> None:
    with pytest.raises(ValueError, match="minimum is about"):
        ContextManager(context_window_tokens=4000)
    smallest = next(w for w in range(4000, 8000) if _constructs(w))
    assert not _constructs(smallest - 1)


def _constructs(window: int) -> bool:
    try:
        ContextManager(context_window_tokens=window)
    except ValueError:
        return False
    return True


class _BigTool:
    spec = ToolSpec("big", "returns a long log", {"type": "object", "properties": {}})

    def run(self, arguments: dict[str, Any]) -> str:
        return "G" * 12000


class _Recorder:
    def __init__(self) -> None:
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.seen.append(list(messages))
        if len(self.seen) == 1:
            return AssistantMessage("", [ToolCall("c1", "big", {})])
        return AssistantMessage("ok")


def test_agent_loop_clips_tool_result_before_model_sees_it() -> None:
    llm = _Recorder()
    AgentLoop(llm, [_BigTool()], context=ContextManager()).run("go")
    tool_msg = llm.seen[1][-1]
    assert tool_msg.role == "tool"
    assert estimate_tokens(tool_msg.content) <= 2000
