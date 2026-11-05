"""Spill an oversized tool result to a file; the model keeps a short preview and the path.

Adapted (idea only, own code) from the MIT deepseek-harness
``references/deepseek_harness/packages/spill/spill-policy/src/index.ts``: the whole result is saved
(:190), the replacement never exceeds the cap because the notice's own size is reserved inside it
(:171), and a storage failure keeps the result inline instead of turning a success into an error
(:154); and from the Apache-2.0 hive
``references/hive/core/framework/agent_loop/internals/tool_result_handler.py:580``: after a restart
the next file number is found by scanning the numbered files already there, so nothing is overwritten.
The notice is plain prose: the same hive file records a model copying a bracketed trailer.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final

from master_finhub.runtime.context import CHARS_PER_TOKEN, estimate_tokens

NAME_RE: Final = re.compile(r"spill_(\d+)\.txt")
SEPARATOR: Final = "\n...\n"
MIN_PREVIEW_CHARS: Final = 40  # below this a preview says nothing, so the result stays inline
MAX_TRIES: Final = 5


class SpillStore:
    """Numbered private files in one directory. Created on the first spill, never before."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def _next_number(self) -> int:
        try:
            names = [NAME_RE.fullmatch(p.name) for p in self._dir.iterdir()]
        except OSError:
            return 1
        return max((int(m.group(1)) for m in names if m), default=0) + 1

    def spill(self, text: str, cap_tokens: int) -> str | None:
        """Replacement text for ``text``, or None when the caller keeps the result inline.

        None means: the result already fits, the notice and a useful preview do not fit in the cap,
        or the file could not be written. A replacement is never above ``cap_tokens`` estimated tokens.
        """
        if estimate_tokens(text) <= cap_tokens:
            return None
        cap_chars = cap_tokens * CHARS_PER_TOKEN
        number = self._next_number()
        for _ in range(MAX_TRIES):
            path = self._dir / f"spill_{number:04d}.txt"
            notice = (
                f"The full result ({len(text)} characters) was saved to {path}. "
                "The start and the end of it follow.\n"
            )
            room = cap_chars - len(notice) - len(SEPARATOR)
            if room < MIN_PREVIEW_CHARS:
                return None
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
                os.chmod(self._dir, 0o700)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                number += 1  # another writer took this number
                continue
            except OSError:
                return None
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(text)
            except (OSError, ValueError):
                return None
            head = room // 2
            return notice + text[:head] + SEPARATOR + text[-(room - head) :]
        return None
