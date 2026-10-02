"""Credential-path denylist matcher (OH31). A tripwire, not a sandbox (see safety.py).

Patterns are a module constant: no policy, mode or argument can extend or remove them. Every
failure (expand, walk, match) is a denial. The walk uses POSIX ``*at`` calls (``dir_fd``,
``O_PATH``), so the module only imports on Linux-like hosts; on Windows it fails loudly rather
than open. Known false positive: a path through a directory the process may search but not read
is still walked (O_PATH needs search only); permission errors are always denials, never "missing".
"""

from __future__ import annotations

import contextlib
import contextvars
import errno
import fnmatch
import os
import posixpath
import re
import stat
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final

# adapted from references/openharness/src/openharness/permissions/checker.py:18 (MIT)
SENSITIVE_PATH_PATTERNS: Final[tuple[str, ...]] = (
    # adapted from references/openharness/src/openharness/permissions/checker.py:20 (MIT)
    "*/.ssh/*",
    # adapted from references/openharness/src/openharness/permissions/checker.py:22 (MIT)
    # and references/openharness/src/openharness/permissions/checker.py:23 (MIT), widened (A16)
    "*/.aws/*",
    # adapted from references/openharness/src/openharness/permissions/checker.py:25 (MIT)
    "*/.config/gcloud/*",
    # adapted from references/openharness/src/openharness/permissions/checker.py:27 (MIT)
    "*/.azure/*",
    # adapted from references/openharness/src/openharness/permissions/checker.py:29 (MIT)
    "*/.gnupg/*",
    # adapted from references/openharness/src/openharness/permissions/checker.py:31 (MIT), plus root
    "*/.docker/config.json",
    "*/.docker",
    # adapted from references/openharness/src/openharness/permissions/checker.py:33 (MIT), plus root
    "*/.kube/config",
    "*/.kube",
    # net-new: plaintext credential stores and private keys kept outside ~/.ssh
    "*/.netrc",
    "*/_netrc",
    "*/.npmrc",
    "*/.pypirc",
    "*/.git-credentials",
    "*/id_rsa",
    "*/id_dsa",
    "*/id_ecdsa",
    "*/id_ed25519",
)
PATH_MAX_CHARS: Final = 4096  # Linux PATH_MAX
RESOLVE_COMPONENT_BUDGET: Final = 16_384  # components one top-level call may walk
MAX_SYMLINKS: Final = 40  # = Linux MAXSYMLINKS
# adapted from references/openharness/src/openharness/permissions/checker.py:91 (MIT): fnmatch,
# compiled once as a single alternation (same result as a per-pattern fnmatchcase loop)
_PATTERN_RE: Final = re.compile("|".join(fnmatch.translate(p) for p in SENSITIVE_PATH_PATTERNS))
_DIR_FLAGS: Final = getattr(os, "O_PATH", os.O_RDONLY) | os.O_DIRECTORY | os.O_NOFOLLOW
_MISSING: Final = (FileNotFoundError, NotADirectoryError)


class BudgetExceeded(Exception):
    """The walk passed the component budget or the symlink limit."""


@dataclass
class Scan:
    """Per-top-level-call state, reached only through call_scope()/current_scan()."""

    cmd: dict[str, str | None] = field(default_factory=dict)
    path: dict[str, str | None] = field(default_factory=dict)
    components_left: int = field(default_factory=lambda: RESOLVE_COMPONENT_BUDGET)


_SCAN: Final[contextvars.ContextVar[Scan | None]] = contextvars.ContextVar(
    "oh31_scan", default=None
)


def current_scan() -> Scan | None:
    return _SCAN.get()


@contextlib.contextmanager
def call_scope() -> Iterator[Scan]:
    """Reuse the current Scan (not owned), else open a fresh one; only the opener resets it."""
    scan = _SCAN.get()
    if scan is not None:
        yield scan
        return
    scan = Scan()
    token = _SCAN.set(scan)
    try:
        yield scan
    finally:
        _SCAN.reset(token)


def _tokens(path: str) -> list[str | None]:
    """Components of a path; None stands for '/' (restart at the root)."""
    parts: list[str | None] = list(path.split("/"))
    if path.startswith("/"):
        parts[0] = None
    return parts


def realpath_bounded(path: str, scan: Scan) -> str:
    """os.path.realpath(path) (strict=False) with one directory fd and a charge per component.

    Every popped component costs 1 (symlink-target and cwd components included); more than
    MAX_SYMLINKS links or an exhausted budget raises BudgetExceeded. A missing component, or a
    non-directory, switches to lexical appending until '..' climbs back above it.
    """
    pending: deque[str | None] = deque(
        _tokens(path) if path.startswith("/") else [*_tokens(os.getcwd()), *path.split("/")]
    )
    parts: list[str] = []
    lexical = 0  # trailing names in `parts` that fd does not contain
    links = 0
    fd = os.open("/", _DIR_FLAGS)
    try:
        while pending:
            scan.components_left -= 1
            if scan.components_left < 0:
                raise BudgetExceeded
            name = pending.popleft()
            if name is None:
                os.close(fd)
                fd = os.open("/", _DIR_FLAGS)
                parts, lexical = [], 0
            elif name in ("", "."):
                continue
            elif name == "..":
                if lexical:
                    parts.pop()
                    lexical -= 1
                elif parts:
                    up = os.open("..", _DIR_FLAGS, dir_fd=fd)
                    os.close(fd)
                    fd = up
                    parts.pop()
            elif lexical:
                parts.append(name)
                lexical += 1
            else:
                try:
                    mode = os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode
                except _MISSING:
                    mode = 0
                except OSError as exc:
                    if exc.errno != errno.ENAMETOOLONG:
                        raise
                    mode = 0
                if stat.S_ISLNK(mode):
                    links += 1
                    if links > MAX_SYMLINKS:
                        raise BudgetExceeded
                    pending.extendleft(reversed(_tokens(os.readlink(name, dir_fd=fd))))
                elif stat.S_ISDIR(mode):
                    down = os.open(name, _DIR_FLAGS, dir_fd=fd)
                    os.close(fd)
                    fd = down
                    parts.append(name)
                else:
                    parts.append(name)
                    lexical = 1
    finally:
        os.close(fd)
    return "/" + "/".join(parts)


def _lexical(s: str) -> str:
    """Backslashes to '/', drive split (A39), per-segment ':stream' and trailing dot/space strip."""
    parts = s.replace("\\", "/").split("/")
    if len(parts[0]) > 2 and parts[0][1] == ":" and parts[0][0].isalpha():
        parts[0:1] = [parts[0][:2], parts[0][2:]]
    out = []
    for i, seg in enumerate(parts):
        if seg in (".", "..") or (i == 0 and len(seg) == 2 and seg[1] == ":" and seg[0].isalpha()):
            out.append(seg)
        else:
            out.append(seg.split(":", 1)[0].rstrip(". "))
    return posixpath.normpath("/".join(out))


def _forms(path: str) -> tuple[str, str]:
    # adapted from references/openharness/src/openharness/permissions/checker.py:169 (MIT):
    # match with and without a trailing '/', so a directory root matches '*/dir/*'
    f = path.casefold()
    f = (f if f.startswith("/") else "/" + f).rstrip("/")
    return f, f + "/"


def _hit(path: str) -> bool:
    return any(_PATTERN_RE.match(f) for f in _forms(path))


def match_forms(expanded: str, *, resolve: bool = True) -> tuple[str, ...]:
    """Casefolded '/'-rooted forms (with and without a trailing '/') of the lexical form and,
    if resolve, of the bounded-walk form. May raise."""
    forms: tuple[str, ...] = _forms(_lexical(expanded))
    if resolve:
        forms += _forms(realpath_bounded(expanded, current_scan() or Scan()))
    return forms


def sensitive_rule(
    raw: str, *, resolve: bool = True, max_chars: int = PATH_MAX_CHARS
) -> str | None:
    """'path-too-long', 'path-budget', 'sensitive-path' or None. Lexical forms are matched before
    any walk. Does not touch Scan.cmd / Scan.path (callers memoise). Any other error denies."""
    try:
        if len(raw) > max_chars:
            return "path-too-long"
        # adapted from references/openharness/src/openharness/engine/query.py:1032 (MIT):
        # expand ~ and match the resolved path
        s = os.path.expandvars(os.path.expanduser(raw))
        if len(s) > max_chars:
            return "path-too-long"
        if _hit(_lexical(s)):
            return "sensitive-path"
        if resolve and len(s) <= PATH_MAX_CHARS:
            try:
                resolved = realpath_bounded(s, current_scan() or Scan())
            except BudgetExceeded:
                return "path-budget"
            if _hit(resolved):
                return "sensitive-path"
        return None
    except Exception:  # noqa: BLE001 - fail closed
        return "sensitive-path"


def is_sensitive_path(raw: str, *, resolve: bool = True) -> bool:
    return sensitive_rule(raw, resolve=resolve) is not None
