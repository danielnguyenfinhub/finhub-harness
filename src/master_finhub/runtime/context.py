"""Context management: token estimate, tool-output clip, threshold compaction (slice 2).

Ideas ported (own code, not copied) from the MIT-licensed deepseek-harness under
``references/deepseek_harness/packages/``:
- token estimate ceil(len/4) plus block/role overheads: llm/token-meter/src/estimate.ts:13,32,35,57
- head/marker/tail tool-result clip and its invariants:
  compaction/compaction-tool-result-pruner/src/index.ts:85,107,118,153 and config.ts:7,12,58
- threshold ratios, retain < threshold, tail-anchored range walk, tool-pairing back-off:
  compaction/compaction-basic/src/config.ts:20,144,148, index.ts:304,328, region.ts:114-132,
  compaction/compaction/src/tool-pairing.ts:29,64,67
- summary frame tags: compaction/compaction-basic/src/summarizer.ts:21,191
Rationale for never splitting a call from its result (providers reject an unanswered call):
autogpt classic forge action_history.py:265 (MIT; idea only, nothing from autogpt_platform).
Net-new here: deterministic model-free summariser, unconditional clip, pinned task message.
All token figures are chars/4 estimates, not real tokenizer counts (accepted risk until slice 4).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from master_finhub.runtime.loop import Message

CHARS_PER_TOKEN: Final = 4
BLOCK_OVERHEAD: Final = 4
ROLE_OVERHEAD: Final = 4
CLIP_BUDGET_TOKENS: Final = 2000
CLIP_MARKER: Final = "\n\n[... middle of tool output clipped to fit the token budget ...]\n\n"
DEFAULT_CONTEXT_WINDOW_TOKENS: Final = 128_000
THRESHOLD_RATIO: Final = 0.8
RETAIN_RATIO: Final = 0.16
SUMMARY_BUDGET_TOKENS: Final = 1000
SUMMARY_LINE_CHARS: Final = 200
FRAME_OVERHEAD_TOKENS: Final = 256  # preamble + tags + role/block overheads, rounded up
CHECKPOINT_PREAMBLE: Final = (
    "Earlier conversation was compacted without a model call. The lines below are "
    "truncated excerpts in original order; re-run a tool if you need its full output."
)
SUMMARY_OPEN_TAG: Final = "<compacted-summary>"
SUMMARY_CLOSE_TAG: Final = "</compacted-summary>"


class ContextOverflowError(RuntimeError):
    """Raised when the conversation cannot be brought under the token threshold."""


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_message(message: Message) -> int:
    total = estimate_tokens(message.content) + BLOCK_OVERHEAD + ROLE_OVERHEAD
    for call in message.tool_calls:
        args = json.dumps(call.arguments, sort_keys=True)
        total += estimate_tokens(call.name) + estimate_tokens(args) + BLOCK_OVERHEAD
    return total


def clip_text(text: str, budget_tokens: int = CLIP_BUDGET_TOKENS) -> str:
    """Keep a 4:1 head/tail around CLIP_MARKER so the result is <= budget estimated tokens."""
    max_chars = budget_tokens * CHARS_PER_TOKEN
    if max_chars <= len(CLIP_MARKER):
        raise ValueError(
            f"clip budget of {budget_tokens} tokens is not larger than the clip marker; "
            "use a budget of at least "
            f"{len(CLIP_MARKER) // CHARS_PER_TOKEN + 1} tokens."
        )
    if estimate_tokens(text) <= budget_tokens:
        return text
    avail = max_chars - len(CLIP_MARKER)
    head = avail * 4 // 5
    tail = avail - head  # >= 1 whenever avail >= 1, so text[-tail:] is never text[-0:]
    out = text[:head] + CLIP_MARKER + text[-tail:]
    if len(out) > max_chars or len(out) >= len(text):
        raise RuntimeError("clip invariant violated")
    return out


def balanced_cuts(messages: Sequence[Message]) -> list[bool]:
    """cuts[i] is True when messages[:i] leaves no tool call without its result."""
    cuts = [True]
    open_calls = 0
    for i, m in enumerate(messages):
        if m.role == "assistant":
            open_calls += len(m.tool_calls)
        elif m.role == "tool":
            open_calls -= 1
            if open_calls < 0:
                raise ValueError(f"orphan tool result at index {i}")
        cuts.append(open_calls == 0)
    return cuts


def select_compactable_range(
    messages: Sequence[Message], retain_tokens: int, pinned: int
) -> int | None:
    """Return keep_from (start of the verbatim tail), or None when nothing can be compacted."""
    keep_from = 0
    running = 0
    for i in range(len(messages) - 1, -1, -1):
        running += estimate_message(messages[i])
        if running >= retain_tokens:
            keep_from = i
            break
    if keep_from <= pinned:
        return None
    cuts = balanced_cuts(messages)
    while keep_from > pinned and not cuts[keep_from]:
        keep_from -= 1
    return keep_from if keep_from > pinned else None


def _excerpt(text: str) -> str:
    return " ".join(text.split())[:SUMMARY_LINE_CHARS]


def summarise(messages: Sequence[Message]) -> Message:
    """Deterministic, model-free checkpoint of ``messages`` (output depends only on input)."""
    lines: list[str] = []
    for n, m in enumerate(messages, start=1):
        label = f"tool({m.tool_call_id})" if m.role == "tool" else m.role
        line = f"{n}. {label}: {_excerpt(m.content)}"
        if m.tool_calls:
            line += f" [called: {', '.join(c.name for c in m.tool_calls)}]"
        lines.append(line)
    body = clip_text("\n".join(lines), SUMMARY_BUDGET_TOKENS)
    content = f"{CHECKPOINT_PREAMBLE}\n\n{SUMMARY_OPEN_TAG}\n{body}\n{SUMMARY_CLOSE_TAG}"
    return Message(role="user", content=content)


@dataclass(frozen=True)
class ContextManager:
    context_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    clip_budget_tokens: int = CLIP_BUDGET_TOKENS
    threshold_ratio: float = THRESHOLD_RATIO
    retain_ratio: float = RETAIN_RATIO

    def __post_init__(self) -> None:
        if self.context_window_tokens <= 0:
            raise ValueError("context_window_tokens must be a positive integer.")
        if self.retain_tokens >= self.threshold_tokens:
            raise ValueError(
                f"retain ({self.retain_tokens}) must be below threshold "
                f"({self.threshold_tokens}); lower retain_ratio or raise threshold_ratio."
            )
        if self.clip_budget_tokens * CHARS_PER_TOKEN <= len(CLIP_MARKER):
            raise ValueError("clip_budget_tokens is too small to hold the clip marker.")
        room = self.threshold_tokens - self.retain_tokens
        needed = self.clip_budget_tokens + SUMMARY_BUDGET_TOKENS + FRAME_OVERHEAD_TOKENS
        if needed >= room:
            minimum = math.ceil((needed + 1) / (self.threshold_ratio - self.retain_ratio))
            raise ValueError(
                "context_window_tokens too small for the clip and summary budgets; "
                f"minimum is about {minimum}."
            )

    @property
    def threshold_tokens(self) -> int:
        return math.floor(self.context_window_tokens * self.threshold_ratio)

    @property
    def retain_tokens(self) -> int:
        return math.floor(self.context_window_tokens * self.retain_ratio)

    def fit(self, messages: list[Message]) -> list[Message]:
        clipped = [
            (
                replace(m, content=clip_text(m.content, self.clip_budget_tokens))
                if m.role == "tool" and estimate_tokens(m.content) > self.clip_budget_tokens
                else m
            )
            for m in messages
        ]
        total = sum(estimate_message(m) for m in clipped)
        if total < self.threshold_tokens:
            return clipped
        pinned = 1 if clipped and clipped[0].role == "user" else 0
        keep_from = select_compactable_range(clipped, self.retain_tokens, pinned)
        if keep_from is None:
            raise self._overflow(clipped, total)
        result = [*clipped[:pinned], summarise(clipped[pinned:keep_from]), *clipped[keep_from:]]
        total = sum(estimate_message(m) for m in result)
        if total >= self.threshold_tokens:
            raise self._overflow(result, total)
        return result

    def _overflow(self, messages: Sequence[Message], total: int) -> ContextOverflowError:
        sizes = [estimate_message(m) for m in messages]
        i = max(range(len(sizes)), key=sizes.__getitem__)
        hint = ", or lower clip_budget_tokens" if messages[i].role == "tool" else ""
        return ContextOverflowError(
            f"Conversation is {total} estimated tokens, above the {self.threshold_tokens} "
            "threshold, and nothing older can be compacted without splitting a tool call "
            f"from its result. Largest message: #{i} ({messages[i].role}, {sizes[i]} tokens). "
            f"Raise context_window_tokens{hint}."
        )
