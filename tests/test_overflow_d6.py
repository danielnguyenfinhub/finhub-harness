"""Proof for compact-and-retry on a context-window error (D6).

adapted from references/deepseek_harness/packages/compaction/compaction-basic/src/index.ts:179 (MIT)
"""

import pytest

from master_finhub.runtime.context import ContextManager, ContextOverflowError
from master_finhub.runtime.loop import AgentLoop, AssistantMessage, Message, ToolSpec


class Overflow(RuntimeError):
    """Looks like ProviderError("CONTEXT_WINDOW", ...): the loop reads only ``code``."""

    code = "CONTEXT_WINDOW"


class Other(RuntimeError):
    code = "REFUSAL"


class ScriptedLLM:
    """Each entry is a reply, or an exception to raise for that call."""

    def __init__(self, script: list[AssistantMessage | Exception]) -> None:
        self.script = list(script)
        self.calls = 0

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Policy:
    """fit() is the normal pre-call step; compact() is the forced one."""

    def __init__(self) -> None:
        self.compactions = 0

    def fit(self, messages: list[Message]) -> list[Message]:
        return messages

    def compact(self, messages: list[Message]) -> list[Message]:
        self.compactions += 1
        return messages[-1:]


def test_overflow_once_compacts_once_and_retries() -> None:
    llm = ScriptedLLM([Overflow("full"), AssistantMessage("done")])
    policy = Policy()
    assert AgentLoop(llm, [], context=policy).run("go") == "done"
    assert (policy.compactions, llm.calls) == (1, 2)


def test_overflow_twice_raises_context_overflow_error() -> None:
    llm = ScriptedLLM([Overflow("full"), Overflow("still full")])
    policy = Policy()
    with pytest.raises(ContextOverflowError):
        AgentLoop(llm, [], context=policy).run("go")
    assert (policy.compactions, llm.calls) == (1, 2)


def test_retry_count_is_configurable() -> None:
    llm = ScriptedLLM([Overflow("a"), Overflow("b"), AssistantMessage("done")])
    policy = Policy()
    loop = AgentLoop(llm, [], context=policy, max_overflow_retries=2)
    assert loop.run("go") == "done"
    assert policy.compactions == 2


def test_zero_retries_re_raises_the_original_error() -> None:
    llm = ScriptedLLM([Overflow("full")])
    with pytest.raises(Overflow):
        AgentLoop(llm, [], context=Policy(), max_overflow_retries=0).run("go")


def test_other_errors_are_not_retried() -> None:
    llm = ScriptedLLM([Other("refused")])
    policy = Policy()
    with pytest.raises(Other):
        AgentLoop(llm, [], context=policy).run("go")
    assert policy.compactions == 0


def test_no_context_policy_means_the_original_error() -> None:
    with pytest.raises(Overflow):
        AgentLoop(ScriptedLLM([Overflow("full")]), []).run("go")


def test_policy_without_compact_means_the_original_error() -> None:
    class FitOnly:
        def fit(self, messages: list[Message]) -> list[Message]:
            return messages

    with pytest.raises(Overflow):
        AgentLoop(ScriptedLLM([Overflow("full")]), [], context=FitOnly()).run("go")


def test_counter_resets_after_a_successful_call() -> None:
    call = AssistantMessage(
        "", [__import__("master_finhub.runtime.loop", fromlist=["x"]).ToolCall("c1", "t", {})]
    )
    llm = ScriptedLLM([Overflow("a"), call, Overflow("b"), AssistantMessage("done")])
    policy = Policy()
    assert AgentLoop(llm, [], context=policy).run("go") == "done"
    assert policy.compactions == 2


def many_turns(n: int) -> list[Message]:
    out = [Message("user", "task")]
    for i in range(n):
        out.append(Message("assistant", f"step {i} " + "x" * 200))
    return out


def test_manager_compact_shrinks_below_threshold_conversations() -> None:
    cm = ContextManager()
    msgs = many_turns(30)
    assert cm.fit(list(msgs)) == msgs  # well under the threshold: fit leaves it alone
    out = cm.compact(list(msgs))
    assert len(out) < len(msgs)
    assert out[0] == msgs[0]
    assert "<compacted-summary>" in out[1].content


def test_manager_compact_with_nothing_older_raises() -> None:
    with pytest.raises(ContextOverflowError):
        ContextManager().compact([Message("user", "only one")])


def test_negative_retry_count_is_refused() -> None:
    with pytest.raises(ValueError):
        AgentLoop(ScriptedLLM([]), [], max_overflow_retries=-1)
