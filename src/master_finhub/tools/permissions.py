"""Session permission modes: read-only, workspace-write, full-access (CW01).

Ideas adapted (own code, nothing copied) from the MIT CowAgent
``references/cowagent/agent/permission/policy.py:39`` (named modes) and ``:595`` (a protected-file
list that holds even where writes are allowed). A mode guard only adds refusals: ``effective_guard``
puts the base command guard first, so no mode, full-access included, switches it off, and a child
agent (``subagent._both``) can only get stricter than its parent.

Workspace-write protection is advisory: it reads command text and cannot see what the shell
expands or what an interpreter does; only a real sandbox is a boundary. Like the base guard this
is a tripwire on the text of a call, not a sandbox.

How it reads a shell command. One scanner (``_scan``) keeps what ``shlex`` throws away: which
characters were quoted and where the shell would expand them. Read-only mode refuses any word
holding an expansion, glob, brace, backslash, ``$'..'`` or other form the guard cannot evaluate,
then allows only the options each reader command lists in ``OPTION_ALLOWLIST``. Workspace-write
mode compares path parts after folding ``.``, ``..`` and repeated slashes, looks inside
``key=value`` words, treats a word that an expansion or glob could turn into a protected name as a
hit, and fails closed on text it cannot scan. It also refuses writers that act on the working
directory without naming a file once ``cd`` has entered a protected directory, git commands that
rewrite tracked files, hard links to protected files, symlinks made and used in one command, and
function definitions in a command that also changes directory. Known gaps: an interpreter that
builds a path at run time (``python -c``), an archive or patch run at the workspace root that
names a protected file, and ``git diff`` programs chosen by repository attributes. Read-only mode
leaves protected files readable by design.
"""

from __future__ import annotations

import fnmatch
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from master_finhub.runtime.loop import ToolCall, ToolGuard
from master_finhub.sandbox.workspace import SandboxDenied, Workspace
from master_finhub.tools.safety import guard_tool_call
from master_finhub.tools.sensitive_paths import is_sensitive_path

Mode = Literal["read-only", "workspace-write", "full-access"]
ToolClass = Literal["read", "write", "shell"]

DEFAULT_MODE: Final[Mode] = "workspace-write"
_RANK: Final = {"read-only": 0, "workspace-write": 1, "full-access": 2}
DEFAULT_PROTECTED: Final[tuple[str, ...]] = (
    ".git",
    ".env",
    ".envrc",
    ".ssh",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".checkpoints",
)
PATH_ARGS: Final = ("path", "file_path", "filename")
# Write-tool arguments that carry file content or prose, not a place to write.
CONTENT_ARGS: Final = frozenset(
    [
        "content",
        "contents",
        "text",
        "data",
        "body",
        "code",
        "patch",
        "diff",
        "message",
        "description",
        "new_string",
        "old_string",
        "new_str",
        "old_str",
        "input",
    ]
)
ADVISORY: Final = (
    "Workspace-write protection is advisory: it reads command text and cannot see what the "
    "shell expands or what an interpreter does; only a real sandbox is a boundary."
)
READERS: Final = frozenset(
    [
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        "rg",
        "sort",
        "diff",
        "stat",
        "file",
        "pwd",
        "echo",
        "date",
        "find",
        "git",
        "cut",
        "tr",
        "basename",
        "dirname",
    ]
)
# Filters with no option that writes a file or runs a program: any option is fine.
FREE_OPTIONS: Final = frozenset(["echo", "pwd", "cut", "tr", "basename", "dirname"])
GIT_READ: Final = frozenset(["status", "log", "diff", "show", "rev-parse", "ls-files", "blame"])
# Commands that run other code or hide a path inside one argument: every word is substring-scanned.
INTERPRETERS: Final = frozenset(
    [
        "sed",
        "awk",
        "gawk",
        "perl",
        "python",
        "python3",
        "ruby",
        "node",
        "sh",
        "bash",
        "dash",
        "zsh",
        "env",
        "script",
        "xargs",
        "eval",
        "exec",
        "find",
        "nice",
        "nohup",
        "timeout",
        "time",
        "sudo",
        "busybox",
        "php",
        "lua",
        "tclsh",
    ]
)
_WRITER_RE: Final = re.compile(
    r"(?<![\w./-])(dd|tee|cp|mv|install|ln|rm|truncate|sed|rsync|tar|chmod|chown|touch|mkdir|"
    r"unzip|patch|curl|wget|python3?|perl|ruby|node|sh|bash|dash|zsh|eval|awk|env|xargs|unlink|"
    r"shred|gzip|bzip2|xz|zstd|cpio|ed|rmdir|rename|split|zip|vi|vim|nano|emacs)(?![\w-])"
    r"|(?<![\w./-])git\s+(config|reset|clean|stash|branch|update-ref|hook|commit|apply|checkout|"
    r"restore|add|mv|rm|remote|worktree|submodule|gc|notes|replace|filter-branch|reflog|"
    r"symbolic-ref|tag|merge|rebase|pull|fetch|cherry-pick|revert|am|init|update-index)(?![\w-])"
)


def _opts(
    none: str = "", val: str = "", att: str = "", ln: str = "", lv: str = "", lo: str = ""
) -> tuple[dict[str, str], dict[str, str]]:
    short = {**dict.fromkeys(none, "n"), **dict.fromkeys(val, "v"), **dict.fromkeys(att, "a")}
    long = {
        **dict.fromkeys(ln.split(), "n"),
        **dict.fromkeys(lv.split(), "r"),
        **dict.fromkeys(lo.split(), "o"),
    }
    return short, long


_D = "0123456789"
# Per-command ALLOWLIST of option shapes: short letter -> n (none) / v (value, glued or next) /
# a (glued value only); long name -> n / r (value after = or next word) / o (value after = only).
# Anything starting with "-" that is not listed is refused, abbreviations included.
OPTION_ALLOWLIST: Final[dict[str, tuple[dict[str, str], dict[str, str]]]] = {
    "cat": _opts(
        "AbeEnstTuv",
        ln="show-all number-nonblank show-ends number squeeze-blank show-tabs show-nonprinting",
    ),
    "ls": _opts(
        "aAbBcCdfFgGhHiklLmnopqrRsStuUvxX1",
        ln="all almost-all human-readable classify recursive reverse size directory long",
        lo="color colour",
    ),
    "head": _opts(_D + "qvz", "nc", ln="quiet silent verbose zero-terminated", lv="lines bytes"),
    "tail": _opts(
        _D + "qvzfF",
        "ncs",
        ln="quiet silent verbose zero-terminated follow retry",
        lv="lines bytes pid sleep-interval",
    ),
    "wc": _opts("lwcmL", ln="lines words bytes chars max-line-length"),
    "grep": _opts(
        _D + "EFGPiyvwxcLlosqbHhnTZazUIrR",
        "efmdDABC",
        ln="ignore-case invert-match word-regexp line-regexp count files-with-matches "
        "files-without-match only-matching quiet silent no-messages byte-offset with-filename "
        "no-filename line-number initial-tab null text recursive dereference-recursive "
        "extended-regexp fixed-strings basic-regexp perl-regexp null-data no-ignore-case "
        "line-buffered",
        lv="include exclude exclude-dir max-count after-context before-context context regexp "
        "file binary-files devices directories label",
        lo="color colour",
    ),
    "rg": _opts(
        _D + "FSiIvwxlcoqsuNnHhLUaAB.",
        "efgtTmjrCAB",
        ln="files files-with-matches files-without-match count count-matches line-number "
        "no-line-number with-filename no-filename ignore-case case-sensitive smart-case "
        "word-regexp line-regexp fixed-strings invert-match only-matching quiet hidden "
        "no-ignore pretty json type-list heading no-heading column follow stats multiline "
        "multiline-dotall null text trim unrestricted no-messages vimgrep no-config "
        "no-ignore-vcs sort-files",
        lv="glob iglob type type-not max-count max-depth context after-context before-context "
        "regexp file colors sort sortr threads max-filesize replace maxdepth",
        lo="color",
    ),
    "sort": _opts(
        "urnfbcCdghiMRsVzm",
        "kt",
        "S",
        ln="unique reverse numeric-sort ignore-case ignore-leading-blanks dictionary-order "
        "general-numeric-sort human-numeric-sort month-sort version-sort random-sort stable "
        "zero-terminated ignore-nonprinting merge",
        lv="key field-separator",
        lo="check",
    ),
    "date": _opts(
        "uR",
        "dr",
        "I",
        ln="utc universal rfc-email rfc-2822",
        lv="date reference rfc-3339",
        lo="iso-8601",
    ),
    "file": _opts("biLhknNr", ln="brief mime mime-type mime-encoding dereference keep-going"),
    "stat": _opts("Lft", "c", ln="dereference file-system terse", lv="format printf"),
    "diff": _opts(
        "uqrNiwBsyaEZbc",
        "UCx",
        ln="brief recursive new-file ignore-case ignore-all-space ignore-space-change "
        "side-by-side report-identical-files text ignore-blank-lines",
        lo="unified context color",
    ),
    "git": _opts(
        _D + "bpsnuzlMCwe",
        "nSGL",
        "U",
        ln="oneline stat shortstat numstat name-only name-status short branch patch graph "
        "decorate all no-color abbrev-commit no-merges merges first-parent reverse cached "
        "staged porcelain ignored quiet exit-code follow relative find-renames show-toplevel "
        "abbrev-ref verify no-ext-diff no-textconv no-patch summary full-history "
        "ignore-all-space ignore-space-change cc raw",
        lv="max-count since until author grep committer skip diff-filter",
        lo="color abbrev pretty format untracked-files stat date",
    ),
}
FIND_VALUE: Final = frozenset(
    [
        "-name",
        "-iname",
        "-path",
        "-ipath",
        "-wholename",
        "-iwholename",
        "-regex",
        "-iregex",
        "-type",
        "-maxdepth",
        "-mindepth",
        "-size",
        "-mtime",
        "-atime",
        "-ctime",
        "-mmin",
        "-amin",
        "-cmin",
        "-newer",
        "-user",
        "-group",
        "-perm",
        "-lname",
        "-ilname",
        "-samefile",
        "-links",
        "-inum",
        "-uid",
        "-gid",
        "-regextype",
    ]
)
FIND_PLAIN: Final = frozenset(
    [
        "-print",
        "-print0",
        "-prune",
        "-o",
        "-a",
        "-not",
        "-and",
        "-or",
        "-empty",
        "-depth",
        "-follow",
        "-L",
        "-P",
        "-H",
        "-xdev",
        "-mount",
        "-readable",
        "-writable",
        "-executable",
        "-true",
        "-false",
        "-nouser",
        "-nogroup",
        "-quit",
        "-d",
    ]
)
FIND_WRITE: Final = ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fls")
_ESCAPES: Final = frozenset('$`"\\\n')


class ModeWidening(ValueError):
    """A child asked for a wider mode than its parent has."""


def inherit_mode(parent: Mode, requested: Mode | None = None) -> Mode:
    if requested is None:
        return parent
    if _RANK[requested] > _RANK[parent]:
        raise ModeWidening(
            f"cannot widen {parent} to {requested}; ask the operator to change mode."
        )
    return requested


def _refuse(call: ToolCall, mode: Mode, why: str) -> str:
    note = f" {ADVISORY}" if mode == "workspace-write" else ""
    return (
        f"Tool '{call.name}' refused in {mode} mode: {why}. Do not retry it; "
        f"ask the operator to switch to a wider mode if the work needs it.{note}"
    )


# --- shell scanner ------------------------------------------------------------------------

Piece = tuple[str, str]  # (kind, text): L literal, G glob character, X expansion we cannot evaluate


@dataclass
class _Word:
    pieces: list[Piece] = field(default_factory=list)
    risky: bool = False  # holds something the guard cannot evaluate

    @property
    def text(self) -> str:
        return "".join(t for _, t in self.pieces)

    @property
    def literal(self) -> bool:
        return all(k == "L" for k, _ in self.pieces)


Item = tuple[str, "_Word | str"]
_SEP: Final = " \t\n;&|<>()"


def _close(cmd: str, i: int, opener: str, closer: str) -> int:
    """Index just past the closer matching an opener that sits just before ``i``; -1 if none."""
    depth = 1
    while i < len(cmd):
        if cmd[i] == opener:
            depth += 1
        elif cmd[i] == closer:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _dollar(cmd: str, i: int) -> int:
    """After a ``$`` that is not a plain end-of-word one: the index past the expansion, or -1."""
    if i >= len(cmd):
        return i
    c = cmd[i]
    if c == "(":
        return _close(cmd, i + 1, "(", ")")
    if c == "{":
        return _close(cmd, i + 1, "{", "}")
    if c == "'":
        j = i + 1
        while j < len(cmd) and cmd[j] != "'":
            j += 2 if cmd[j] == "\\" else 1
        return j + 1 if j < len(cmd) else -1
    if c == '"':
        return i  # $"..." is locale quoting: the quote is read normally afterwards
    if c.isalnum() or c == "_":
        while i < len(cmd) and (cmd[i].isalnum() or cmd[i] == "_"):
            i += 1
        return i
    return i + 1  # $@ $? $$ $! $- $# $*


def _scan(cmd: str) -> list[Item] | None:
    """Split a command into words (with quoting kept) and operators; None if it cannot be read."""
    items: list[Item] = []
    word: _Word | None = None
    n = len(cmd)
    i = 0

    def flush() -> None:
        nonlocal word
        if word is not None:
            items.append(("word", word))
            word = None

    def cur() -> _Word:
        nonlocal word
        if word is None:
            word = _Word()
        return word

    def add(kind: str, text: str, risky: bool = False) -> None:
        w = cur()
        w.risky = w.risky or risky
        if kind == "L" and w.pieces and w.pieces[-1][0] == "L":
            w.pieces[-1] = ("L", w.pieces[-1][1] + text)
        else:
            w.pieces.append((kind, text))

    while i < n:
        c = cmd[i]
        if c in " \t":
            flush()
            i += 1
        elif c in "\n;":
            flush()
            items.append(("op", ";"))
            i += 1
        elif c == "\\":
            if i + 1 < n and cmd[i + 1] == "\n":
                cur().risky = True
            else:
                add("L", cmd[i + 1] if i + 1 < n else "\\", risky=True)
            i += 2
        elif c == "'":
            j = cmd.find("'", i + 1)
            if j < 0:
                return None
            add("L", cmd[i + 1 : j])
            i = j + 1
        elif c == '"':
            i += 1
            add("L", "")
            while True:
                if i >= n:
                    return None
                d = cmd[i]
                if d == '"':
                    i += 1
                    break
                if d == "\\" and i + 1 < n and cmd[i + 1] in _ESCAPES:
                    if cmd[i + 1] != "\n":
                        add("L", cmd[i + 1], risky=True)
                    cur().risky = True
                    i += 2
                elif d == "`":
                    j = cmd.find("`", i + 1)
                    if j < 0:
                        return None
                    add("X", cmd[i : j + 1], risky=True)
                    i = j + 1
                elif d == "$" and i + 1 < n and cmd[i + 1] != '"':
                    j = _dollar(cmd, i + 1)
                    if j < 0:
                        return None
                    add("X", cmd[i:j], risky=True)
                    i = j
                else:
                    add("L", d, risky=(d == "\\"))
                    i += 1
        elif c == "`":
            j = cmd.find("`", i + 1)
            if j < 0:
                return None
            add("X", cmd[i : j + 1], risky=True)
            i = j + 1
        elif c == "$":
            if i + 1 >= n or cmd[i + 1] in _SEP:
                add("L", "$")  # a lone "$" at the end of a word is plain text
                i += 1
            else:
                j = _dollar(cmd, i + 1)
                if j < 0:
                    return None
                add("X", cmd[i:j], risky=True)
                i = j
        elif c == "{":
            j = _close(cmd, i + 1, "{", "}")
            if j < 0:
                add("L", "{", risky=True)
                i += 1
            else:
                add("X", cmd[i:j], risky=True)
                i = j
        elif c == "}":
            add("L", "}", risky=True)
            i += 1
        elif c in "*?":
            add("G", c, risky=True)
            i += 1
        elif c == "[":
            j = cmd.find("]", i + 2)
            if j < 0 or any(ch in cmd[i:j] for ch in " \t\n"):
                add("L", "[", risky=True)
                i += 1
            else:
                add("G", "[", risky=True)
                i = j + 1
        elif c == "~":
            at_start = word is None or not word.pieces
            plain = at_start and (i + 1 >= n or cmd[i + 1] in "/ \t\n;&|)")
            prev = cmd[i - 1] if i else " "
            add("L", "~", risky=not plain and (at_start or prev in "=:"))
            i += 1
        elif c == "#" and word is None:
            j = cmd.find("\n", i)
            items.append(("comment", "#"))
            i = n if j < 0 else j
        elif c == "&":
            flush()
            if cmd.startswith("&&", i):
                items.append(("op", "&&"))
                i += 2
            elif cmd.startswith("&>", i):
                j = i + 2
                while j < n and cmd[j] in "<>&|":
                    j += 1
                items.append(("redir", cmd[i:j]))
                i = j
            else:
                items.append(("bad", "&"))
                i += 1
        elif c == "|":
            flush()
            if cmd.startswith("||", i):
                items.append(("op", "||"))
                i += 2
            elif cmd.startswith("|&", i):
                items.append(("bad", "|&"))
                i += 2
            else:
                items.append(("op", "|"))
                i += 1
        elif c in "<>":
            flush()
            j = i + 1
            while j < n and cmd[j] in "<>&|":
                j += 1
            items.append(("redir", cmd[i:j]))
            i = j
        elif c in "()":
            flush()
            items.append(("bad", c))
            i += 1
        else:
            add("L", c)
            i += 1
    flush()
    return items


# --- read-only mode -----------------------------------------------------------------------


def _check_options(
    cmd: str,
    args: Sequence[str],
    spec: tuple[dict[str, str], dict[str, str]],
    operands: list[str] | None = None,
) -> str | None:
    """None if every option is on the allowlist; the non-option words go to ``operands``."""
    short, long = spec
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            if operands is not None:
                operands.extend(args[i:])
            return None
        if a == "-" or not a.startswith("-"):
            if operands is not None:
                operands.append(a)
            continue
        if a.startswith("--"):
            name, eq, _ = a[2:].partition("=")
            kind = long.get(name)
            if kind is None:
                return f"option {a} is not on the read-only list for {cmd}"
            if kind == "r" and not eq:
                i += 1
            continue
        j = 1
        while j < len(a):
            kind = short.get(a[j])
            if kind is None:
                return f"option -{a[j]} is not on the read-only list for {cmd}"
            j += 1
            if kind == "v" and j >= len(a):
                i += 1
            if kind in "va":
                break
    return None


def _find_denial(args: Sequence[str]) -> str | None:
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if not a.startswith("-") or a == "-":
            continue
        if a in FIND_VALUE:
            i += 1
        elif a not in FIND_PLAIN:
            return f"find option {a} is not on the read-only list"
    return None


def _date_sets_clock(args: Sequence[str]) -> bool:
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a.startswith("--") and a != "--":
            if a[2:] in ("date", "reference", "rfc-3339"):
                i += 1  # the value is the next word
        elif a.startswith("-") and a != "-":
            for j, c in enumerate(a[1:], 1):
                if c in "dr":  # -d/-r take the rest of the cluster, or the next word
                    i += j == len(a) - 1
                    break
                if c == "I":
                    break
        elif not a.startswith("+"):
            return True  # a bare operand such as 010112002026 sets the clock
    return False


def _start_dirs(cmd: str, args: Sequence[str]) -> list[str] | None:
    """The words a recursive reader walks below (``.`` when it names none), None if it is not
    recursive. rg and find always are; grep, diff and ls only with -r / -R."""
    shorts = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))
    longs = {a[2:].split("=", 1)[0] for a in args if a.startswith("--") and a != "--"}
    if cmd == "find":
        ops: list[str] = []
        for a in args:
            if a.startswith("-") and a != "-":
                break
            ops.append(a)
        return ops or ["."]
    rec = {
        "rg": True,
        "grep": bool(set(shorts) & set("rR"))
        or bool({"recursive", "dereference-recursive"} & longs),
        "diff": "r" in shorts or "recursive" in longs,
        "ls": "R" in shorts or "recursive" in longs,
    }
    if not rec.get(cmd):
        return None
    ops = []
    _check_options(cmd, args, OPTION_ALLOWLIST[cmd], ops)
    if cmd in ("grep", "rg") and not (
        set(shorts) & set("ef") or {"regexp", "file", "files"} & longs
    ):
        ops = ops[1:]  # the first word is the pattern
    return ops or ["."]


def _path_denial(cmd: str, args: Sequence[str], root: Path) -> str | None:
    """Credential paths named by a reader, and recursive readers that would start at the home
    directory or above the workspace. A start inside the workspace is allowed, so protected
    files there stay readable in read-only mode."""
    for a in args:
        if not a.startswith("-") and is_sensitive_path(a):
            return "it names a credential path"
    starts = _start_dirs(cmd, args)
    if starts is None:
        return None
    rr, home = root.resolve(), Path.home().resolve()
    for raw in starts:
        try:
            real = rr.joinpath(os.path.expanduser(raw)).resolve()
        except (OSError, RuntimeError):
            return "a recursive reader's start directory cannot be resolved"
        if real == home or real in home.parents or real in rr.parents:
            return "a recursive reader would start at the home directory or above the workspace"
    return None


def _segment_denial(seg: Sequence[str], root: Path | None = None) -> str | None:
    """Why one command of a chain is not a plain read, or None. With a ``root``, credential
    paths and recursive readers aimed at the home directory or above the workspace are refused."""
    why = _syntax_denial(seg)
    if why or root is None:
        return why
    return _path_denial(seg[0], seg[1:], root)


def _syntax_denial(seg: Sequence[str]) -> str | None:
    """Why one command of a chain is not a plain read, or None."""
    if not seg:
        return "empty command in a chain"
    cmd, args = seg[0], seg[1:]
    if cmd not in READERS:
        return f"'{cmd}' is not on the read-only list"
    if cmd == "git":
        if not args or args[0] not in GIT_READ:
            return "only read-only git subcommands are allowed"
        return _check_options(cmd, args[1:], OPTION_ALLOWLIST["git"])
    if cmd == "find":
        return _find_denial(args)
    if cmd in OPTION_ALLOWLIST:
        why = _check_options(cmd, args, OPTION_ALLOWLIST[cmd])
        if why:
            return why
    if cmd == "date" and _date_sets_clock(args):
        return "a bare date operand sets the clock"
    return None


def _reader_denial(command: str, root: Path | None = None) -> str | None:
    items = _scan(command.strip())
    if not items:
        return "command is empty or cannot be judged read-only"
    segs: list[list[str]] = [[]]
    for kind, val in items:
        if kind == "op":
            segs.append([])
        elif kind == "word":
            assert isinstance(val, _Word)
            if val.risky:
                return (
                    "a word uses an expansion, glob, brace, backslash or quoting form "
                    "the guard cannot evaluate"
                )
            segs[-1].append(val.text)
        else:
            return "redirect, background, subshell or comment cannot be judged read-only"
    for seg in segs:
        why = _segment_denial(seg, root)
        if why:
            return why
    return None


# --- workspace-write: protected paths -----------------------------------------------------

MAX_PIECES: Final = 128  # a word with more expansion/glob pieces is refused, not matched
MAX_DEPTH: Final = 3  # nested `sh -c '...'` bodies that are followed
PROTECTED_WHY: Final = "it touches a protected file"
COMPLEX_WHY: Final = "a word has too many expansion or glob pieces to check"
UNKNOWN_CWD_WHY: Final = (
    "the working directory is unknown after a cd the guard cannot follow, so it cannot tell "
    "whether a relative name is a protected file"
)
_ASSIGN_RE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# Commands that run another command (or keywords that start one): the guard looks through them.
# The value is the short-option letters that take a value.
_WRAPPERS: Final[dict[str, str]] = {
    "command": "",
    "builtin": "",
    "env": "uCS",
    "nice": "n",
    "ionice": "cnp",
    "stdbuf": "ioe",
    "setsid": "",
    "sudo": "ughCDRTUrtp",
    "doas": "uC",
    "exec": "a",
    "time": "",
    "nohup": "",
    "timeout": "sk",
    "xargs": "IJnPdLsEa",
    "busybox": "",
    **dict.fromkeys(["{", "!", "if", "then", "do", "else", "elif", "while", "until"], ""),
}
_WRAP_LONG: Final = frozenset(
    ["user", "group", "chdir", "unset", "host", "prompt", "signal", "kill-after", "priority"]
)
# Wrappers the guard cannot see through: refused rather than guessed.
_UNKNOWN_WRAPPERS: Final = frozenset(
    ["chroot", "setpriv", "unshare", "nsenter", "runuser", "su", "strace", "ltrace", "fakeroot",
     "watch", "parallel", "ssh", "sg", "pkexec", "systemd-run", "bwrap", "firejail", "taskset",
     "chrt", "flock", "proot", "cpulimit", "script"]
)  # fmt: skip
_SHELLS: Final = frozenset(["sh", "bash", "dash", "zsh", "ksh"])
GIT_REWRITE: Final = frozenset(
    ["config", "hook", "update-ref", "clean", "notes", "replace", "filter-branch", "filter-repo",
     "gc", "prune", "repack", "worktree", "submodule", "update-index", "symbolic-ref",
     "maintenance"]
)  # fmt: skip
FUNCTION_RE: Final = re.compile(
    r"(?<![\w$./-])function\s+\S|(?<![\w$.:-])[A-Za-z_][\w.:-]*\s*\(\s*\)"
)
CD_RE: Final = re.compile(r"(?<![\w./-])(cd|pushd|popd|chdir)(?![\w-])")
FUNCTION_WHY: Final = (
    "it defines a shell function in a command that also changes directory, so the guard "
    "cannot tell where a later call of the function leaves the shell"
)
CWD_WRITER_WHY: Final = (
    "it writes into the current directory, which is or holds a protected file, without naming "
    "the file it writes"
)
DECOMPRESS_NAMES: Final = frozenset(["gunzip", "bunzip2", "unxz", "unzstd", "uncompress", "unlzma"])
COMPRESS_NAMES: Final = frozenset(["gzip", "bzip2", "xz", "zstd", "lzma"])
GIT_WORKTREE_SUBS: Final = frozenset(
    ["checkout", "restore", "switch", "reset", "stash", "apply", "checkout-index"]
)
INTO_DIR_WHY: Final = (
    "it puts a file into a directory that holds a protected entry, under the name the source "
    "has, and that name may be the protected one"
)
GIT_REMOTE_WRITE: Final = frozenset(
    ["add", "set-url", "rename", "remove", "rm", "set-head", "prune", "update", "set-branches"]
)
GIT_BRANCH_LONG: Final = (
    "delete", "move", "copy", "force", "edit-description", "set-upstream-to", "unset-upstream",
)  # fmt: skip


def _split_parts(pieces: Sequence[Piece], base: Sequence[str] = ()) -> list[list[Piece]]:
    """Path parts of a word: split on literal "/", drop "" and ".", fold ".." textually.

    ``base`` is the tracked working directory a relative word starts from. A ".." with nothing to
    pop is kept: it leaves the workspace and must not vanish."""
    parts: list[list[Piece]] = [[]]
    for kind, text in pieces:
        if kind != "L":
            parts[-1].append((kind, text))
            continue
        for k, seg in enumerate(text.split("/")):
            if k:
                parts.append([])
            if seg:
                parts[-1].append(("L", seg))
    absolute = bool(pieces) and pieces[0][0] == "L" and pieces[0][1].startswith("/")
    out: list[list[Piece]] = [] if absolute else [[("L", b)] for b in base]
    for p in parts:
        lit = "".join(t for _, t in p) if all(k == "L" for k, _ in p) else None
        if not p or lit == ".":
            continue
        if lit == "..":
            if out and out[-1] != [("L", "..")]:
                out.pop()
            else:
                out.append(p)
            continue
        out.append(p)
    return out


_BRACE_FLAT: Final = re.compile(r"[\w.@+-]*")


def _brace_alternatives(text: str) -> list[str] | None:
    """What a brace expansion ``{a,b}`` can be: its alternatives. ``{x}`` and ``{}`` are not
    expanded by the shell and stay as typed. None when it cannot be listed (nested, a sequence
    ``{1..3}``, a quote or a variable inside): it then stands for anything."""
    if not (text.startswith("{") and text.endswith("}")):
        return None
    inner = text[1:-1]
    if not _BRACE_FLAT.fullmatch(inner.replace(",", "")):
        return None
    if "," in inner:
        return inner.split(",")
    return None if ".." in inner else [text]


def _part_matches(part: Sequence[Piece], want: str) -> bool:
    """Can this path part, with its globs and expansions, be the name ``want``? Linear time."""
    if all(k == "L" for k, _ in part):
        return "".join(t for _, t in part).casefold() == want
    # a real glob never matches a leading dot; an expansion can produce one
    if part[0][0] == "G" and want.startswith(".") and all(k != "X" for k, _ in part):
        return False
    n = len(want)
    at = {0}  # positions in ``want`` reachable after the pieces so far
    for kind, text in part:
        if kind == "L":
            low = text.casefold()
            at = {p + len(low) for p in at if want.startswith(low, p)}
        elif kind == "X" and (alts := _brace_alternatives(text)) is not None:
            lows = [alt.casefold() for alt in alts]
            at = {p + len(low) for p in at for low in lows if want.startswith(low, p)}
        elif kind == "X" or text == "*":
            at = set(range(min(at), n + 1)) if at else set()
        else:
            at = {p + 1 for p in at if p < n}
        if not at:
            return False
    return n in at


def _parts_hit(parts: Sequence[Sequence[Piece]], protected: Sequence[str]) -> bool:
    for entry in protected:
        want = [p.casefold() for p in PurePosixPath(entry).parts]
        n = len(want)
        for i in range(len(parts) - n + 1):
            if all(_part_matches(parts[i + j], want[j]) for j in range(n)):
                return True
    return False


def _covers(parts: Sequence[Sequence[Piece]], protected: Sequence[str], *, root_too: bool) -> bool:
    """Is this path a protected entry's ancestor (or the entry itself)? Deleting, renaming or
    replacing such a directory removes the protected entry. ``root_too``: the workspace root
    (no parts), and a path made only of ``..``, count as ancestors of everything."""
    if parts and all(
        all(k == "L" for k, _ in p) and "".join(t for _, t in p) == ".." for p in parts
    ):
        return True
    if not parts:
        return root_too
    for entry in protected:
        want = [p.casefold() for p in PurePosixPath(entry).parts]
        if len(parts) <= len(want) and all(
            _part_matches(parts[i], want[i]) for i in range(len(parts))
        ):
            return True
    return False


def _is_protected(parts: Sequence[str], protected: Sequence[str]) -> bool:
    return _parts_hit([[("L", p)] for p in parts], protected)


def _candidates(pieces: Sequence[Piece]) -> list[Sequence[Piece]]:
    """The word itself and the value after each literal "=" (``of=.env``, ``--opt=.git``)."""
    out: list[Sequence[Piece]] = [pieces]
    for k, (kind, text) in enumerate(pieces):
        if kind != "L":
            continue
        pos = text.find("=")
        while pos >= 0:
            out.append([("L", text[pos + 1 :]), *pieces[k + 1 :]])
            pos = text.find("=", pos + 1)
    return out


Cwd = tuple[str, ...] | None  # tracked working directory below the workspace root; None unknown


def _real_parts(text: str, cwd: Cwd, root: Path) -> tuple[str, ...] | None:
    """The word's real location below the workspace root (symlinks followed), or None."""
    if not text or len(text) >= 1024 or "\x00" in text or "\n" in text:
        return None
    try:
        rr = root.resolve()
        return rr.joinpath(*(cwd or ()), text).resolve().relative_to(rr).parts
    except (OSError, ValueError, RuntimeError):
        return None


def _forms(word: _Word, cwd: Cwd, root: Path) -> list[list[list[Piece]]]:
    """Every reading of a word as path parts below the workspace root."""
    out: list[list[list[Piece]]] = []
    for cand in _candidates(word.pieces):
        out.append(_split_parts(cand, cwd or ()))
        if all(k == "L" for k, _ in cand):
            real = _real_parts("".join(t for _, t in cand), cwd, root)
            if real is not None:
                out.append([[("L", p)] for p in real])
    return out


def _word_hits(word: _Word, protected: Sequence[str], root: Path, cwd: Cwd, *, split: bool) -> bool:
    if any(_parts_hit(f, protected) for f in _forms(word, cwd, root)):
        return True
    if split and word.literal:  # a path hidden in one quoted argument: "tee .env", "w .env"
        text = word.text
        for bit in re.split(r"[\s;<>|&\"'()=,:]+", text):
            if bit and bit != text and _parts_hit(_split_parts([("L", bit)], cwd or ()), protected):
                return True
    return False


def _word_covers(
    word: _Word, protected: Sequence[str], root: Path, cwd: Cwd, *, root_too: bool
) -> bool:
    return any(_covers(f, protected, root_too=root_too) for f in _forms(word, cwd, root))


def _substring_hit(text: str, protected: Sequence[str]) -> bool:
    low = text.casefold()
    return any(e.casefold() in low for e in protected)


def _short_letters(texts: Sequence[str]) -> set[str]:
    return {c for t in texts if t.startswith("-") and not t.startswith("--") for c in t[1:]}


def _long_prefix(t: str, full: str) -> bool:
    """Is ``t`` (a ``--x`` argument) an abbreviation of the long option ``--full``?"""
    name = t[2:].split("=", 1)[0] if t.startswith("--") else ""
    return bool(name) and full.startswith(name)


def _is_recursive(texts: Sequence[str]) -> bool:
    return bool(_short_letters(texts) & set("rR")) or any(
        _long_prefix(t, "recursive") for t in texts
    )


def _unwrap(seg: Sequence[_Word]) -> tuple[list[_Word], str, list[_Word], list[str]]:
    """Split a command into (assignments and wrapper words, effective name, its arguments,
    wrapper chain). The name is the basename of the first word that is not a wrapper; it is ""
    when that word is not literal (then every remaining word is in the arguments)."""
    prefix: list[_Word] = []
    chain: list[str] = []
    i, n = 0, len(seg)
    while i < n and seg[i].literal:
        w = seg[i]
        if _ASSIGN_RE.match(w.text):
            prefix.append(w)
            i += 1
            continue
        base = PurePosixPath(w.text).name
        if base not in _WRAPPERS:
            break
        chain.append(base)
        prefix.append(w)
        i += 1
        vals = _WRAPPERS[base]
        while i < n and seg[i].literal and seg[i].text.startswith("-") and seg[i].text != "-":
            t = seg[i].text
            prefix.append(seg[i])
            i += 1
            if t == "--":
                break
            if t.startswith("--"):
                takes = "=" not in t and t[2:] in _WRAP_LONG
            else:
                hit = [k for k, c in enumerate(t[1:]) if c in vals]
                takes = bool(hit) and hit[0] == len(t) - 2
            if takes and i < n:
                prefix.append(seg[i])
                i += 1
        if base == "timeout" and i < n:
            prefix.append(seg[i])  # the duration
            i += 1
    if i >= n:
        return prefix, "", [], chain
    head = seg[i]
    if not head.literal:
        return prefix, "", list(seg[i:]), chain
    return prefix, PurePosixPath(head.text).name, list(seg[i + 1 :]), chain


def _bare(word: _Word) -> bool:
    """A word that names a path relative to the (unknown) working directory."""
    return not word.literal or not word.text.startswith(("/", "~", "-"))


def _legacy_scan(command: str, protected: Sequence[str]) -> bool:
    """Fail closed on text the scanner cannot follow (``$(``, ``${``, backticks, bad quoting)."""
    if _substring_hit(command, protected):
        return True
    trio = "`" in command or "$(" in command or "${" in command
    return trio and (">" in command or _WRITER_RE.search(command) is not None)


def _sensitive_dir(cwd: Cwd, protected: Sequence[str]) -> bool:
    """Is this directory (below the root) a protected entry, inside one, or the parent of one?"""
    if not cwd:
        return False
    parts: list[list[Piece]] = [[("L", p)] for p in cwd]
    return _parts_hit(parts, protected) or _covers(parts, protected, root_too=False)


@dataclass
class _Run:
    """One pass over a command: the tracked directory, the directory stack and the context."""

    protected: Sequence[str]
    root: Path
    cwd: Cwd
    depth: int
    dirs: list[Cwd] = field(default_factory=list)
    links: list[tuple[str, ...]] = field(default_factory=list)  # symlinks made in this command
    inodes: set[tuple[int, int]] | None = None

    def hit(self, w: _Word, *, split: bool = True) -> bool:
        return (
            _word_hits(w, self.protected, self.root, self.cwd, split=split)
            or self.on_link(w)
            or self.hard_link(w)
        )

    def cov(self, w: _Word, *, root_too: bool = True) -> bool:
        return _word_covers(w, self.protected, self.root, self.cwd, root_too=root_too)

    def on_link(self, w: _Word) -> bool:
        """Does the word name, or sit below, a symlink this command made to a directory that
        holds a protected entry? The link does not exist yet, so its real target cannot be read."""
        if not self.links:
            return False
        for form in _forms(w, self.cwd, self.root):
            for link in self.links:
                if len(form) >= len(link) and all(
                    _part_matches(form[i], link[i]) for i in range(len(link))
                ):
                    return True
        return False

    def hard_link(self, w: _Word) -> bool:
        """Is the word an existing hard link to a protected file (same inode)? Checked only for
        words of a command that is not a plain read; a linked name is a protected file."""
        if self.cwd is None:
            return False
        for cand in _candidates(w.pieces):
            if not all(k == "L" for k, _ in cand):
                continue
            text = "".join(t for _, t in cand)
            if not text or len(text) >= 1024 or "\x00" in text or text.startswith("-"):
                continue
            path = os.path.join(str(self.root), *self.cwd, os.path.expanduser(text))
            try:
                st = os.stat(path)
            except (OSError, ValueError):
                continue
            if stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
                if self.inodes is None:
                    self.inodes = _protected_inodes(self.root, self.protected)
                if (st.st_dev, st.st_ino) in self.inodes:
                    return True
        return False

    def sensitive_cwd(self) -> bool:
        """Is the tracked working directory (below the root) a protected directory, inside one,
        or the parent of a protected entry? A command that writes into it without naming a file
        can then overwrite a protected file."""
        return _sensitive_dir(self.cwd, self.protected)

    def reaches_root(self, w: _Word) -> bool:
        return not w.literal or self.cov(w)

    def hidden(self, w: _Word, interp: bool) -> bool:
        """A protected name hidden inside one quoted argument of an interpreter or a flag."""
        return (
            w.literal
            and (interp or w.text.startswith("-"))
            and _substring_hit(w.text, self.protected)
        )

    def chdir(self, text: str) -> Cwd:
        return self.chdir_from(self.cwd, text)

    def chdir_from(self, cwd: Cwd, text: str) -> Cwd:
        if cwd is None and not text.startswith(("/", "~")):
            return None
        joined = os.path.join(str(self.root), *(cwd or ()), os.path.expanduser(text))
        rel = os.path.relpath(os.path.realpath(joined), os.path.realpath(self.root))
        return tuple(p for p in PurePosixPath(rel).parts if p != ".")

    def segment(self, seg: list[_Word], redirs: list[_Word]) -> str | None:
        for w in redirs:
            if len(w.pieces) > MAX_PIECES:
                return COMPLEX_WHY
            if self.hit(w, split=False):
                return PROTECTED_WHY
            if self.cwd is None and _bare(w):
                return UNKNOWN_CWD_WHY
        if not seg:
            return None
        if any(len(w.pieces) > MAX_PIECES for w in seg):
            return COMPLEX_WHY
        prefix, name, args, chain = _unwrap(seg)
        if name in _UNKNOWN_WRAPPERS:
            return f"'{name}' runs other commands and the guard cannot see through it"
        interp = any(c in INTERPRETERS for c in (*chain, name))
        for w in prefix:  # NAME=value assignments and wrapper options
            if self.hit(w) or self.hidden(w, interp):
                return PROTECTED_WHY
        texts = [w.text for w in args]
        if name in READERS and _segment_denial([name, *texts]) is None:
            return None  # a plain read, may name a protected file
        why = self.structural(name, args)
        if why:
            return why
        cd = name in ("cd", "pushd", "popd")
        if self.cwd is None and not cd and any(_bare(w) for w in args):
            return UNKNOWN_CWD_WHY
        split = not (name in FREE_OPTIONS or name == "printf")
        for w in args:
            if self.hit(w, split=split) or self.hidden(w, interp):
                return PROTECTED_WHY
        if self.sensitive_cwd():
            why = self.cwd_writer(name, texts)
            if why:
                return why
        if name in ("cp", "mv", "ln", "install", "rsync"):
            why = self.into_protected_dir(name, args)
            if why:
                return why
        if name in _SHELLS or name == "eval":
            bodies = [w.text for w in args if w.literal and not w.text.startswith("-")]
            if name == "eval":
                bodies = [" ".join(bodies)]
            for body in bodies:
                why = _shell_denial(body, self.protected, self.root, self.cwd, self.depth + 1)
                if why:
                    return why
        if cd:
            self.change_dir(name, args)
        self.note_links(name, args)
        return None

    def change_dir(self, name: str, args: list[_Word]) -> None:
        if name == "popd":
            self.cwd = self.dirs.pop() if self.dirs else None
            return
        ops = [w for w in args if not (w.literal and w.text.startswith("-") and w.text != "-")]
        new: Cwd = None
        if len(ops) == 1 and ops[0].literal and ops[0].text not in ("", "-"):
            new = self.chdir(ops[0].text)
        if name == "pushd":
            self.dirs.append(self.cwd)
        self.cwd = new

    def structural(self, name: str, args: list[_Word]) -> str | None:
        """Commands that reach or change protected files without naming them."""
        texts = [w.text for w in args]
        paths = [w for w in args if not w.text.startswith("-")]
        if name in ("rm", "rmdir", "unlink", "shred"):
            if name == "rm" and _is_recursive(texts) and any(self.reaches_root(w) for w in paths):
                return (
                    "a recursive delete of a glob, an expansion, the workspace root or a "
                    "directory that holds a protected file"
                )
            if any(self.cov(w) for w in paths):
                return "it deletes the workspace root or a directory that holds a protected file"
        elif name == "mv":
            with_t = any(t == "-t" or _long_prefix(t, "target-directory") for t in texts)
            if any(self.cov(w) for w in (paths if with_t else paths[:-1])):
                return "it moves the workspace root or a directory that holds a protected file"
        elif name == "find" and any(t.startswith(FIND_WRITE) for t in texts):
            starts: list[_Word] = []
            for w in args:
                if w.text.startswith("-"):
                    break
                starts.append(w)
            if not starts or any(self.reaches_root(w) for w in starts):
                return (
                    "find with -delete, -exec or another write action must not start at the "
                    "workspace root, a directory that holds protected files, a glob or an "
                    "expansion; start from a subdirectory such as src"
                )
        elif name == "tar":
            if any(t.startswith("--rem") for t in texts) or any(
                self.cov(w, root_too=False) for w in paths
            ):
                return (
                    "tar --remove-files, or extracting into a directory that holds a protected file"
                )
        elif name == "rsync":
            gone = any(t.startswith(("--del", "--remove")) for t in texts)
            if any(self.cov(w, root_too=gone) for w in paths):
                return "rsync into a directory that holds a protected file, or with --delete"
        elif name in ("cp", "install"):
            merging = any(w.text == "." or w.text.endswith("/.") for w in paths[:-1])
            if merging and any(self.cov(w) for w in paths[-1:]):
                return "a merging copy over a directory that holds a protected file"
        elif name == "unzip" and any(self.cov(w, root_too=False) for w in paths):
            return "unzip into a directory that holds a protected file"
        elif name in ("gzip", "zstd") and _is_recursive(texts) and any(self.cov(w) for w in paths):
            return f"{name} -r over a directory that holds a protected file"
        elif name == "git":
            return self.git_denial(args)
        return None

    def cwd_writer(self, name: str, texts: list[str]) -> str | None:
        """In a protected directory (or a parent of a protected entry): a command that writes
        files whose names it takes from an archive, a patch or its own arguments."""
        short = _short_letters(texts)
        if name == "tar":
            bundle = set(texts[0]) if texts and not texts[0].startswith("-") else set()
            if "x" in (short | bundle) or any(
                _long_prefix(t, "extract") or _long_prefix(t, "get") for t in texts
            ):
                return CWD_WRITER_WHY
        elif name == "cpio":
            if short & set("ip") or any(
                _long_prefix(t, "extract") or _long_prefix(t, "pass-through") for t in texts
            ):
                return CWD_WRITER_WHY
        elif name == "unzip":
            if not short & set("ltpvzZcd"):
                return CWD_WRITER_WHY
        elif name == "patch":
            if not any(_long_prefix(t, "dry-run") for t in texts):
                return CWD_WRITER_WHY
        elif name in DECOMPRESS_NAMES or (
            name in COMPRESS_NAMES
            and (short & {"d"} or any(_long_prefix(t, "decompress") for t in texts))
        ):
            quiet = any(_long_prefix(t, "stdout") or _long_prefix(t, "test") for t in texts) or any(
                _long_prefix(t, "list") for t in texts
            )
            if not (short & set("ctl") or quiet or "--to-stdout" in texts):
                return CWD_WRITER_WHY
        return None

    def copy_parts(self, name: str, args: list[_Word]) -> tuple[list[_Word], _Word] | None:
        """(sources, destination) of cp, mv, ln, install or rsync, or None if unclear. A lone
        ``ln`` source is linked into the working directory under its own name."""
        pos: list[_Word] = []
        tdir: _Word | None = None
        i = 0
        while i < len(args):
            w = args[i]
            t = w.text
            if w.literal and t == "--":
                pos += args[i + 1 :]
                break
            if w.literal and t.startswith("-") and t != "-":
                if name == "rsync":
                    pass
                elif t.startswith("--") and _long_prefix(t, "target-directory"):
                    if "=" in t:
                        tdir = _Word(pieces=list(_candidates(w.pieces)[1]))
                    elif i + 1 < len(args):
                        tdir = args[i + 1]
                        i += 1
                elif not t.startswith("--") and t.endswith("t") and i + 1 < len(args):
                    tdir = args[i + 1]
                    i += 1
            else:
                pos.append(w)
            i += 1
        if tdir is not None:
            return pos, tdir
        if len(pos) >= 2:
            return pos[:-1], pos[-1]
        if len(pos) == 1 and name == "ln":
            return pos, _Word(pieces=[("L", ".")])
        return None

    def into_protected_dir(self, name: str, args: list[_Word]) -> str | None:
        """A file copied, moved or linked into a directory that holds a protected entry, where
        the file keeps the name it has at the source: ``cp x/settings.json .claude/``."""
        parts = self.copy_parts(name, args)
        if parts is None:
            return None
        sources, dest = parts
        if not self.cov(dest, root_too=False):
            return None
        for src in sources:
            base = PurePosixPath(src.text).name if src.literal else ""
            if not src.literal or base in ("", ".", ".."):
                return INTO_DIR_WHY
            if self.hit(_Word(pieces=[*dest.pieces, ("L", "/" + base)]), split=False):
                return INTO_DIR_WHY
        return None

    def note_links(self, name: str, args: list[_Word]) -> None:
        """Remember a symlink this command makes to a directory that holds a protected entry,
        so a later word of the same command that goes through it is refused."""
        texts = [w.text for w in args]
        short = _short_letters(texts)
        symbolic = "s" in short or any(
            _long_prefix(t, "symbolic" if name == "ln" else "symbolic-link") for t in texts
        )
        if name not in ("ln", "cp") or not symbolic or self.cwd is None:
            return
        parts = self.copy_parts(name, args)
        if parts is None:
            return
        sources, dest = parts
        if not dest.literal:
            return
        dparts = _split_parts(dest.pieces, self.cwd)
        names = tuple("".join(t for _, t in p).casefold() for p in dparts)
        if ".." in names:
            return
        inside = (self.root / Path(*names)).is_dir() if names else True
        bases: list[Cwd] = [names[:-1], names] if names else [()]
        if not any(
            _word_covers(src, self.protected, self.root, base, root_too=False)
            for src in sources
            for base in bases
        ):
            return
        if inside:
            for src in sources:
                base_name = PurePosixPath(src.text).name.casefold() if src.literal else ""
                self.links.append((*names, base_name) if base_name else names)
        else:
            self.links.append(names)

    def git_worktree_denial(self, sub: str, args: list[_Word], gcwd: Cwd) -> str | None:
        """git commands that rewrite tracked files of the working tree: they can overwrite or
        delete a protected file that git tracks (``.claude/settings.json``, a committed ``.env``).
        """
        texts = [w.text for w in args]
        short = _short_letters(texts)
        if gcwd is None:
            return "git -C names a directory the guard cannot follow, so it cannot check the paths"
        if sub == "checkout-index":
            return "git checkout-index can overwrite tracked protected files"
        if sub == "reset":
            if any(_long_prefix(t, "hard") for t in texts):
                return "git reset with the hard option overwrites tracked protected files"
            return None
        if sub == "stash":
            first = next((t for t in texts if not t.startswith("-")), "")
            if first in ("pop", "apply", "branch"):
                return f"git stash {first} writes the stashed versions over tracked protected files"
            return None
        if sub == "apply":
            if _sensitive_dir(gcwd, self.protected) and not any(
                _long_prefix(t, x) for t in texts for x in ("check", "stat", "numstat", "summary")
            ):
                return CWD_WRITER_WHY
            return None
        if sub in ("checkout", "switch") and (
            "f" in short
            or any(_long_prefix(t, "force") or _long_prefix(t, "discard-changes") for t in texts)
        ):
            return f"git {sub} with force discards local changes, protected files among them"
        if sub == "switch":
            return None
        worktree = "W" in short or any(_long_prefix(t, "worktree") for t in texts)
        staged = "S" in short or any(_long_prefix(t, "staged") for t in texts)
        if sub == "restore" and staged and not worktree:
            return None  # only the index
        if any(_long_prefix(t, "pathspec-from-file") for t in texts):
            return f"git {sub} with a pathspec file lists paths the guard cannot read"
        after = texts.index("--") + 1 if "--" in texts else 0
        for w in args[after:]:
            if w.text.startswith("-") and not after:
                continue
            if w.literal and self.pathspec_magic(w.text, gcwd):
                return f"git {sub} with a pathspec the guard cannot rule out as a protected file"
            if _word_covers(w, self.protected, self.root, gcwd, root_too=True):
                return (
                    f"git {sub} on the workspace root or a directory that holds a protected "
                    "file overwrites tracked files"
                )
        return None

    def pathspec_magic(self, text: str, gcwd: Cwd) -> bool:
        """A pathspec git reads as a pattern, or with ``:`` magic, that may reach a protected
        entry."""
        if text.startswith(":"):
            return True
        if not any(c in text for c in "*?[\\"):
            return False
        names: list[str] = []
        for entry in self.protected:
            ps = PurePosixPath(entry).parts
            names += ["/".join((*(gcwd or ()), *ps[: i + 1])) for i in range(len(ps))]
            names += ["/".join(ps[: i + 1]) for i in range(len(ps))]
        return any(fnmatch.fnmatchcase(n.casefold(), text.casefold()) for n in names)

    def git_denial(self, args: list[_Word]) -> str | None:
        texts = [w.text for w in args]
        k = 0
        gcwd = self.cwd  # the directory git works in, after any -C
        while k < len(texts) and texts[k].startswith("-"):
            if texts[k] == "-c" or texts[k].startswith(
                ("--config-env", "--exec-path", "--git-dir", "--work-tree")
            ):
                return "a git option can set configuration or point inside the protected tree"
            if texts[k] == "-C":
                ok = k + 1 < len(args) and args[k + 1].literal
                gcwd = self.chdir_from(gcwd, texts[k + 1]) if ok else None
                k += 2
            else:
                k += 1
        sub = texts[k] if k < len(texts) else ""
        rest = texts[k + 1 :]
        short = _short_letters(rest)
        if sub in GIT_WORKTREE_SUBS:
            why = self.git_worktree_denial(sub, args[k + 1 :], gcwd)
            if why:
                return why
        if sub in GIT_REWRITE:
            return f"git {sub} can change configuration, hooks or the contents of .git"
        if sub == "stash" and (
            short & set("ua")
            or any(_long_prefix(t, "include-untracked") or _long_prefix(t, "all") for t in rest)
        ):
            return "git stash of untracked or ignored files can delete a protected file"
        if sub == "remote" and GIT_REMOTE_WRITE & set(rest):
            return "git remote add, set-url and similar rewrite .git/config"
        if sub == "reflog" and {"expire", "delete"} & set(rest):
            return "git reflog expire or delete rewrites .git"
        if sub == "tag" and (
            short & set("df")
            or any(_long_prefix(t, "delete") or _long_prefix(t, "force") for t in rest)
        ):
            return "git tag -d or -f rewrites .git"
        if sub == "branch" and (
            short & set("mMdDuCcf")
            or any(_long_prefix(t, long) for t in rest for long in GIT_BRANCH_LONG)
        ):
            return "git branch with an option that renames, deletes or edits rewrites .git"
        if sub == "init" and any(t.startswith("--separate-git-dir") for t in rest):
            return "git init --separate-git-dir moves .git"
        if sub in ("rm", "mv") and any(
            self.cov(w) for w in args[k + 1 :] if not w.text.startswith("-")
        ):
            return "it removes or moves a directory that holds a protected file"
        return None


def _shell_denial(
    command: str,
    protected: Sequence[str],
    root: Path,
    cwd: Cwd = (),
    depth: int = 0,
) -> str | None:
    """Why a workspace-write shell command is refused, or None. Follows ``cd``, ``pushd``,
    subshells and ``sh -c`` bodies, and looks through wrappers such as ``env`` and ``sudo``."""
    if depth > MAX_DEPTH:
        return "shell commands are nested too deep to check"
    if FUNCTION_RE.search(command) and CD_RE.search(command):
        return FUNCTION_WHY
    items = _scan(command)
    if items is None or "`" in command or "$(" in command or "${" in command:
        return PROTECTED_WHY if _legacy_scan(command, protected) else None
    run = _Run(protected, root, cwd, depth)
    seg: list[_Word] = []
    redirs: list[_Word] = []
    redirect = False
    for kind, val in items:
        if kind in ("op", "bad"):
            why = run.segment(seg, redirs)
            if why:
                return why
            seg, redirs, redirect = [], [], False
            if val == "(":
                run.dirs.append(run.cwd)
            elif val == ")" and run.dirs:
                run.cwd = run.dirs.pop()
        elif kind == "redir":
            assert isinstance(val, str)
            redirect = ">" in val
        elif kind == "word":
            assert isinstance(val, _Word)
            if redirect:
                redirs.append(val)
                redirect = False
            else:
                seg.append(val)
    return run.segment(seg, redirs)


PATH_KEYS: Final = frozenset(
    [
        "path", "file", "filename", "dest", "destination", "target", "src", "source", "cwd",
        "dir", "directory", "output", "to", "from", "paths", "files", "dirs", "directories",
        "sources", "targets", "outputs", "destinations",
    ]
)  # fmt: skip
_FILENAME_KEY: Final = re.compile(r"[\w.~/@+-]+")


def _is_path_key(key: str) -> bool:
    k = key.casefold()
    return k in PATH_KEYS or k.endswith(("_path", "_file", "_dir"))


MAX_ARG_DEPTH: Final = 6  # deeper or larger write calls are refused, not half-checked
MAX_ARG_STRINGS: Final = 256


def _checked_strings(arguments: Mapping[str, object]) -> list[str]:
    """Strings of a write tool call that could name a place: values under path-like keys and
    values that start like a path (``/`` ``./`` ``../`` ``~``), at any depth, and dict keys that
    look like file names. Content and prose arguments are skipped."""
    out: list[str] = []

    def add(text: str) -> None:
        if len(out) >= MAX_ARG_STRINGS:
            raise ValueError(f"a write call holds more than {MAX_ARG_STRINGS} paths to check")
        out.append(text)

    def walk(key: str, value: object, depth: int) -> None:
        if key in CONTENT_ARGS and key not in PATH_ARGS:
            return
        if depth > MAX_ARG_DEPTH:
            raise ValueError(f"a write call is nested deeper than {MAX_ARG_DEPTH} levels to check")
        if isinstance(value, str):
            plain = "\n" not in value and len(value) <= 4096
            starts = value.startswith(("/", "./", "../", "~"))
            if key in PATH_ARGS or (plain and (_is_path_key(key) or starts)):
                add(value)
        elif isinstance(value, Mapping):
            for k, v in value.items():
                if isinstance(k, str):
                    if _FILENAME_KEY.fullmatch(k) and ("." in k or "/" in k):
                        add(k)
                    walk(k, v, depth + 1)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(key, v, depth + 1)

    for key, value in arguments.items():
        walk(key, value, 0)
    return out


def _protected_inodes(root: Path, protected: Sequence[str]) -> set[tuple[int, int]]:
    """(device, inode) of the protected files under the root; a protected directory is walked
    (at most 2000 entries)."""
    out: set[tuple[int, int]] = set()
    left = 2000
    for entry in protected:
        top = root / entry
        walk = os.walk(top) if top.is_dir() else [(str(top.parent), [], [top.name])]
        for base, dirs, files in walk:
            for name in [*dirs, *files]:
                left -= 1
                try:
                    st = os.lstat(os.path.join(base, name))
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):
                    out.add((st.st_dev, st.st_ino))
            if left <= 0:
                return out
    return out


def _hard_link_to_protected(resolved: Path, root: Path, protected: Sequence[str]) -> bool:
    try:
        st = os.stat(resolved)
    except OSError:
        return False
    return (
        stat.S_ISREG(st.st_mode)
        and st.st_nlink > 1
        and (st.st_dev, st.st_ino) in _protected_inodes(root, protected)
    )


def make_mode_guard(
    mode: Mode,
    workspace: Workspace,
    *,
    tool_classes: Mapping[str, ToolClass] | None = None,
    protected: Sequence[str] = DEFAULT_PROTECTED,
) -> ToolGuard:
    classes = dict(tool_classes or {})

    def guard(call: ToolCall) -> str | None:
        if mode == "full-access":
            return None
        kind = classes.get(call.name)
        if kind is None:
            return _refuse(call, mode, "unknown tool") if mode == "read-only" else None
        if kind == "read":
            return None
        if kind == "shell":
            command = str(call.arguments.get("command") or "")
            if mode == "read-only":
                why = _reader_denial(command, workspace.root)
            else:
                why = _shell_denial(command, protected, workspace.root)
            return _refuse(call, mode, why) if why else None
        if mode == "read-only":
            return _refuse(call, mode, "writes are not allowed")
        if any(k in call.arguments and not isinstance(call.arguments[k], str) for k in PATH_ARGS):
            return _refuse(call, mode, "a write needs a path to check")
        try:
            raws = _checked_strings(call.arguments)
        except ValueError as exc:
            return _refuse(call, mode, str(exc))
        if not raws:
            return _refuse(call, mode, "a write needs a path to check")
        for raw in raws:  # every path-like string is checked, nested ones included
            try:
                resolved = workspace.check_write(raw)
            except (SandboxDenied, ValueError, OSError) as exc:
                return _refuse(call, mode, str(exc))
            if _is_protected(resolved.relative_to(workspace.root).parts, protected):
                return _refuse(call, mode, "the path is protected")
            if _hard_link_to_protected(resolved, workspace.root, protected):
                return _refuse(call, mode, "the path is a hard link to a protected file")
        return None

    return guard


def effective_guard(
    mode: Mode,
    workspace: Workspace,
    *,
    tool_classes: Mapping[str, ToolClass] | None = None,
    protected: Sequence[str] = DEFAULT_PROTECTED,
) -> ToolGuard:
    """Base command guard first, then the mode guard; full-access never drops the base."""
    mode_guard = make_mode_guard(mode, workspace, tool_classes=tool_classes, protected=protected)

    def guard(call: ToolCall) -> str | None:
        denial = guard_tool_call(call)
        return denial if denial is not None else mode_guard(call)

    return guard
