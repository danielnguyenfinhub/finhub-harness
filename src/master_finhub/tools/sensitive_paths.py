"""Credential-path denylist matcher (OH31). A tripwire, not a sandbox (see safety.py).

Patterns are a module constant: no policy, mode or argument can extend or remove them. Every
failure (expand, walk, match) is a denial. The walk uses POSIX ``*at`` calls (``dir_fd``,
``O_PATH``), so the module only imports on Linux-like hosts; on Windows it fails loudly rather
than open. Known false positive: a path through a directory the process may search but not read
is still walked (O_PATH needs search only); permission errors are always denials, never "missing".

Not covered (a path the guard cannot see in the command text): paths read from a pipe, from stdin,
from a file named by an option, or built by an interpreter; hard links are matched by inode only
for the credential files found under the home directory (best effort, bounded stat of the list).
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
    # audit lead 5: more token stores, project env files and process environments
    "*/.config/gh/hosts.yml",
    "*/.cargo/credentials",
    "*/.cargo/credentials.toml",
    "*/.config/anthropic",
    "*/.config/anthropic/*",
    "*/.env",
    "*/.env.*",
    "/proc/*/environ",
    # re-audit 2 (RA2-13): more credential stores and shell histories
    "*/.bash_history",
    "*/.zsh_history",
    "*/.pgpass",
    "*/.vault-token",
    "*/.claude/.credentials.json",
    "*/.config/rclone/rclone.conf",
    "*/.terraform.d/credentials.tfrc.json",
    "*/.gem/credentials",
    "*/.composer/auth.json",
    "*/.config/git/credentials",
    "*/.oci/*",
    "*/.oci",
    "/etc/shadow*",
    "/etc/gshadow*",
    "/etc/ssh/ssh_host_*_key",
)
# audit lead 4: credential locations as path components, for words with shell wildcards
_CRED_COMPONENTS: Final[tuple[tuple[str, ...], ...]] = (
    (".ssh",),
    (".aws",),
    (".azure",),
    (".gnupg",),
    (".docker",),
    (".kube",),
    (".netrc",),
    ("_netrc",),
    (".npmrc",),
    (".pypirc",),
    (".git-credentials",),
    (".env",),
    ("id_rsa",),
    ("id_dsa",),
    ("id_ecdsa",),
    ("id_ed25519",),
    (".config", "gcloud"),
    (".config", "anthropic"),
    (".config", "gh", "hosts.yml"),
    (".cargo", "credentials"),
    (".cargo", "credentials.toml"),
    (".bash_history",),
    (".zsh_history",),
    (".pgpass",),
    (".vault-token",),
    (".oci",),
    (".claude", ".credentials.json"),
    (".config", "rclone", "rclone.conf"),
    (".terraform.d", "credentials.tfrc.json"),
    (".gem", "credentials"),
    (".composer", "auth.json"),
    (".config", "git", "credentials"),
)
_GLOB_RE: Final = re.compile(r"[*?\[]")
_GLOB_PART_RE: Final = re.compile(r"\[[^\]]*\]|[*?]")
_SINGLE_CLASS_RE: Final = re.compile(r"\[([^\]\[!^])\]")  # `[s]` is the literal `s`
_POSIX_CLASSES: Final = (
    ("[:alpha:]", "a-zA-Z"),
    ("[:digit:]", "0-9"),
    ("[:alnum:]", "a-zA-Z0-9"),
    ("[:lower:]", "a-z"),
    ("[:upper:]", "A-Z"),
    ("[:xdigit:]", "0-9a-fA-F"),
    ("[:space:]", " \t"),
)
GLOB_ENTRIES_PER_WORD: Final = 4096  # directory entries listed for one glob word
GLOB_ENTRIES_PER_CALL: Final = 65_536  # ... for one top-level call (then path-budget)
GLOB_MATCHES: Final = 256  # matches one glob word keeps per path component
CRED_STAT_BUDGET: Final = 512  # entries looked at when listing the credential files under HOME
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
    entries_left: int = field(default_factory=lambda: GLOB_ENTRIES_PER_CALL)
    inodes: frozenset[tuple[int, int]] | None = None  # (dev, ino) of credential files, lazily


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


def _posix(part: str) -> str:
    for cls, rng in _POSIX_CLASSES:
        part = part.replace(cls, rng)
    return part


def _fn(name: str, part: str) -> bool:
    """fnmatch of `name` against a shell pattern. Bash reads `[^x]` as `[!x]` and fnmatch reads
    the `^` as a member (RA2-02), so a pattern with `[^` is tried both ways and matches if either
    does."""
    part = _posix(part)
    if fnmatch.fnmatchcase(name, part):
        return True
    return "[^" in part and fnmatch.fnmatchcase(name, part.replace("[^", "[!"))


def _shell_match(part: str, name: str) -> bool:
    """Could shell pattern `part` expand to `name`? A wildcard never matches a leading dot."""
    part = part.casefold()
    if name.startswith(".") and not part.startswith("."):
        return False
    return _fn(name.casefold(), part)


def _part_matches(part: str, name: str) -> bool:
    """Could shell pattern `part` expand to `name`? A dotfile needs a literal leading dot, and a
    pattern with nothing literal beyond that (`*`, `.*`, `??`, a bare `[a-z]*`) is too wide to
    call a match here; glob_hit_wide judges those against the home directory instead."""
    part = part.casefold()
    if not _GLOB_RE.search(part):
        return part == name
    dot = name[0] == "."
    if dot and not part.startswith("."):
        return False
    rest = part[1:] if dot else part
    lit = _GLOB_PART_RE.sub("", _SINGLE_CLASS_RE.sub(r"\1", rest))
    exempt = "[" in rest if dot else _SINGLE_CLASS_RE.search(rest) is not None
    if len(lit) < (1 if dot else 2) and not exempt:
        return False
    return _fn(name, part)


def glob_hit(path: str) -> bool:
    """True if a word with shell wildcards in a directory or file name could name a credential."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    for entry in _CRED_COMPONENTS:
        for i in range(len(parts) - len(entry) + 1):
            if all(_part_matches(parts[i + j], n) for j, n in enumerate(entry)):
                return True
    return False


def glob_hit_wide(path: str) -> bool:
    """A wildcard that can match a credential name even with nothing literal in it (`~/.*`,
    `~/.??*`, `~/.config/*`, `~/.*/gcloud/x`): refused only when the literal directory in front
    of the first wildcard is the home directory or a credential parent, so `ls .*` or
    `cat ./[0-9]*.md` in a project directory stay allowed. Needs an absolute path (a relative
    word is joined to a known directory by the caller first)."""
    p = path.replace("\\", "/")
    if not p.startswith("/"):
        return False
    comps = [c for c in p.split("/") if c not in ("", ".")]
    n = next((i for i, c in enumerate(comps) if _GLOB_RE.search(c)), None)
    if n is None:
        return False
    rest = comps[n:]
    if (
        len(comps) > 2
        and comps[0].casefold() == "proc"
        and _shell_match(comps[2], "environ")
        and 0 < n <= 2
    ):
        return True  # /proc/<pid or self>/environ spelled with a wildcard in the last name
    d = posixpath.normpath("/" + "/".join(comps[:n])).casefold()
    homes = {os.path.expanduser("~")}
    with contextlib.suppress(OSError):
        homes.add(os.path.realpath(os.path.expanduser("~")))
    for home in homes:
        for entry in _CRED_COMPONENTS:
            for s in range(len(entry)):
                if s == 0 and not entry[0].startswith("."):
                    continue  # `~/*` could name ~/id_rsa; only a wildcard with literals does
                if d != posixpath.join(home, *entry[:s]).casefold():
                    continue
                need = len(entry) - s
                if len(rest) >= need and all(
                    _shell_match(r, e) for r, e in zip(rest, entry[s:], strict=False)
                ):
                    return True
    return False


def _cred_inodes(scan: Scan) -> frozenset[tuple[int, int]]:
    """(device, inode) of the credential files under the home directory. Best effort: the list
    is _CRED_COMPONENTS, a directory is listed two levels deep, and at most CRED_STAT_BUDGET
    entries are looked at."""
    if scan.inodes is not None:
        return scan.inodes
    out: set[tuple[int, int]] = set()
    left = CRED_STAT_BUDGET
    home = os.path.expanduser("~")
    todo: deque[tuple[str, int]] = deque((posixpath.join(home, *e), 0) for e in _CRED_COMPONENTS)
    while todo and left > 0:
        path, depth = todo.popleft()
        left -= 1
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if stat.S_ISREG(st.st_mode):
            out.add((st.st_dev, st.st_ino))
        elif stat.S_ISDIR(st.st_mode) and depth < 2:
            try:
                with os.scandir(path) as it:
                    todo.extend((e.path, depth + 1) for e in it)
            except OSError:
                continue
    scan.inodes = frozenset(out)
    return scan.inodes


def hard_link_hit(path: str, scan: Scan) -> bool:
    """A regular file with more than one link that is the same inode as a credential file."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    return (
        stat.S_ISREG(st.st_mode)
        and st.st_nlink > 1
        and (st.st_dev, st.st_ino) in _cred_inodes(scan)
    )


def _multi_link(path: str) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and st.st_nlink > 1


_CRED_NAMES: Final = frozenset(n for e in _CRED_COMPONENTS for n in e)


def _could_name_credential(part: str) -> bool:
    """Could the wildcard name `part` expand to the name of a credential file or directory?"""
    return any(_shell_match(part, n) for n in _CRED_NAMES)


def glob_rule(raw: str, scan: Scan) -> str | None:
    """Expand a word with wildcards against the real directories (component by component, no
    recursion past the word's own components, GLOB_ENTRIES_PER_WORD entries per word) and judge
    every match by name; a match that is a link, sits behind a link or has other links is walked
    too. 'sensitive-path' when any match names a credential, and 'path-budget' when the expansion
    cannot be completed: the call's entry budget or the word's entry limit runs out, or more than
    GLOB_MATCHES directories would have to be opened (RA2-01). Best effort otherwise."""
    try:
        s = os.path.expandvars(os.path.expanduser(raw))
        parts = [c for c in s.split("/") if c not in ("", ".")]
        bases: list[tuple[str, bool]] = [("/" if s.startswith("/") else os.getcwd(), False)]
        word_left = GLOB_ENTRIES_PER_WORD
        for n, part in enumerate(parts):
            nxt: list[tuple[str, bool]] = []
            for base, walk in bases:
                if not _GLOB_RE.search(part):
                    child = posixpath.join(base, part)
                    nxt.append((child, walk))
                    continue
                try:
                    it = os.scandir(base)
                except OSError:
                    continue  # unreadable or missing: nothing to name
                with it:
                    for e in it:
                        word_left -= 1
                        scan.entries_left -= 1
                        if scan.entries_left < 0:
                            return "path-budget"
                        if word_left < 0:  # the listing is cut: refuse only a pattern that could
                            if _could_name_credential(part):  # name a credential in the rest
                                return "path-budget"
                            break
                        if _shell_match(part, e.name):
                            nxt.append((e.path, walk or e.is_symlink()))
            for path, _ in nxt:
                if _hit(path):  # a plain match is judged by name, whatever the pattern looks like
                    return "sensitive-path"
            if (
                len(nxt) > GLOB_MATCHES
                and n + 1 < len(parts)
                and any(_could_name_credential(q) for q in parts[n + 1 :])
            ):
                return "path-budget"  # too many directories to open for the next component
            bases = nxt
            if not bases:
                return None
        for path, walk in bases:
            # an alias (a link, a path behind one, a hard link) needs the walk
            if (walk or _multi_link(path)) and sensitive_rule(path, max_chars=len(path) + 1):
                return "sensitive-path"
        return None
    except Exception:  # noqa: BLE001 - fail closed
        return "sensitive-path"


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
        if _hit(_lexical(s)) or (_GLOB_RE.search(s) and (glob_hit(s) or glob_hit_wide(s))):
            return "sensitive-path"
        if resolve and len(s) <= PATH_MAX_CHARS:
            try:
                resolved = realpath_bounded(s, current_scan() or Scan())
            except BudgetExceeded:
                return "path-budget"
            if _hit(resolved) or hard_link_hit(resolved, current_scan() or Scan()):
                return "sensitive-path"
        return None
    except Exception:  # noqa: BLE001 - fail closed
        return "sensitive-path"


def is_sensitive_path(raw: str, *, resolve: bool = True) -> bool:
    return sensitive_rule(raw, resolve=resolve) is not None
