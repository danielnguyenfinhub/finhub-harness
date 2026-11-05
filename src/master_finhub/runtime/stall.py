"""Stall detection as pure functions: reply similarity over a window, and a silence clock.

Adapted (idea only, own code) from the Apache-2.0 hive
``references/hive/core/framework/agent_loop/internals/stall_detector.py:11`` (``ngram_similarity``)
and ``:33`` (``is_stalled``): a stall needs every consecutive pair of recent replies to be similar,
so one different reply resets it, and "attempt 1" against "attempt 2" is not a stall. It complements
``repeat_reminder.py``, which only sees identical tool calls. Nothing here reads a clock, calls a
model or changes a run: the caller passes ``now`` and decides what to do with the answer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

SILENCE_AT: Final = (30.0, 120.0, 300.0)  # seconds without activity for levels 1, 2 and 3


def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


def bigram_similarity(a: str, b: str) -> float:
    """Jaccard similarity of the character bigrams of two texts, ignoring case: 0.0 to 1.0."""
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    first, second = _bigrams(a), _bigrams(b)
    if not first or not second:  # a one-character text can only equal the other
        return 0.0
    return len(first & second) / len(first | second)


def is_stalled(replies: Sequence[str], window: int = 3, threshold: float = 0.85) -> bool:
    """True when each consecutive pair among the last ``window`` replies scores at least ``threshold``."""
    if window < 2:
        raise ValueError("window must be at least 2")
    if len(replies) < window:
        return False
    recent = replies[-window:]
    if not recent[0]:
        return False
    return all(
        bigram_similarity(recent[i], recent[i - 1]) >= threshold for i in range(1, len(recent))
    )


def silence_level(last_activity: float, now: float) -> int:
    """How many of ``SILENCE_AT`` have passed since ``last_activity`` (0 to 3); a clock that went back is 0."""
    idle = now - last_activity
    return sum(idle >= limit for limit in SILENCE_AT)
