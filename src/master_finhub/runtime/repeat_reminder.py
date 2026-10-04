"""Advisory repeat-call reminder: text for the 3rd, 5th and 8th identical call in a row.

Adapted (idea only, own code) from the MIT-licensed deepseek-harness
``references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts``: key-sorted
canonical arguments (:103), a chain of consecutive identical calls (:189-198), reminders at
counts 3/5/8 (:199) and a gentle first tier (:200); and from autogpt classic
``references/autogpt/classic/forge/forge/components/watchdog/watchdog.py:32`` (MIT), which
compares each call with the previous one. Net-new: a fixed text that never quotes the tool
name, arguments or output, a digest key with a size cap, and fail-open error handling.
It never vetoes, skips or reorders a call: the caller appends the returned text to the result.
"""

from __future__ import annotations

import hashlib
import json
from typing import Final

REMIND_AT: Final = (3, 5, 8)  # a count outside this tuple, 9 and above included, stays silent
MAX_KEY_CHARS: Final = 100_000  # ASCII-escaped JSON chars; a longer call is not tracked
GENTLE: Final = (
    "[advisory] The same tool call, with the same arguments, has now been issued 3 times in a "
    "row. Read the earlier results again; if the task is unfinished, change the arguments or "
    "the approach."
)
FIRM: Final = (
    "[advisory] This exact call (same tool, same arguments) has now been issued {count} times "
    "in a row. More repeats are unlikely to help: use a different tool or different arguments, "
    "or give your final answer with what you have."
)


def _call_key(name: str, arguments: object) -> str | None:
    """Digest of the key-sorted JSON form of (name, arguments); None when over the size cap."""
    text = json.dumps([name, arguments], sort_keys=True, separators=(",", ":"))
    if len(text) > MAX_KEY_CHARS:
        return None
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class RepeatReminder:
    """One chain per instance: (digest, run length) of the latest call. Not locked: advisory."""

    def __init__(self) -> None:
        self._last: tuple[str, int] | None = None

    def reset(self) -> None:
        self._last = None

    def observe(self, name: str, arguments: object) -> str:
        """Count one call; return the text to append to its result, or "". No Exception escapes."""
        try:
            key = _call_key(name, arguments)
            if key is None:
                self._last = None
                return ""
            count = self._last[1] + 1 if self._last is not None and self._last[0] == key else 1
            self._last = (key, count)
            if count not in REMIND_AT:
                return ""
            return "\n\n" + (GENTLE if count == REMIND_AT[0] else FIRM.format(count=count))
        except Exception:  # noqa: BLE001 - advisory only: odd arguments must not fail a call
            self._last = None
            return ""
