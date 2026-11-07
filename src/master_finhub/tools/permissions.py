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
hit, and fails closed on text it cannot scan. Known gaps: an interpreter that builds a path at run
time (``python -c``), a symlink created in the same command, and ``git diff`` programs chosen by
repository attributes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from master_finhub.runtime.loop import ToolCall, ToolGuard
from master_finhub.sandbox.workspace import SandboxDenied, Workspace
from master_finhub.tools.safety import guard_tool_call

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
    r"unzip|patch|curl|wget|python3?|perl|ruby|node|sh|bash|dash|zsh|eval|awk|env|xargs)(?![\w-])"
    r"|(?<![\w./-])git\s+(config|reset|clean|stash|branch|update-ref|hook|commit|apply|checkout|"
    r"restore|add|mv|rm)(?![\w-])"
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
            plain = at_start and (i + 1 >= n or cmd[i + 1] == "/")
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
    cmd: str, args: Sequence[str], spec: tuple[dict[str, str], dict[str, str]]
) -> str | None:
    short, long = spec
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            return None
        if a == "-" or not a.startswith("-"):
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
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a in ("-d", "-r", "--date", "--reference", "--rfc-3339"):
            skip = True
        elif not a.startswith(("-", "+")):
            return True  # a bare operand such as 010112002026 sets the clock
    return False


def _segment_denial(seg: Sequence[str]) -> str | None:
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


def _reader_denial(command: str) -> str | None:
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
        why = _segment_denial(seg)
        if why:
            return why
    return None


# --- workspace-write: protected paths -----------------------------------------------------


def _split_parts(pieces: Sequence[Piece]) -> list[list[Piece]]:
    """Path parts of a word: split on literal "/", drop "" and ".", fold ".." textually."""
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
    out: list[list[Piece]] = []
    for p in parts:
        lit = "".join(t for _, t in p) if all(k == "L" for k, _ in p) else None
        if not p or lit == ".":
            continue
        if lit == "..":
            if out:
                out.pop()
            continue
        out.append(p)
    return out


def _part_matches(part: Sequence[Piece], want: str) -> bool:
    if all(k == "L" for k, _ in part):
        return "".join(t for _, t in part).casefold() == want
    rx = ""
    for kind, text in part:
        if kind == "L":
            rx += re.escape(text.casefold())
        elif kind == "X" or text == "*":
            rx += ".*"
        else:
            rx += "."
    # a real glob never matches a leading dot; an expansion can produce one
    if part[0][0] == "G" and want.startswith(".") and all(k != "X" for k, _ in part):
        return False
    return re.fullmatch(rx, want, re.DOTALL) is not None


def _parts_hit(parts: Sequence[Sequence[Piece]], protected: Sequence[str]) -> bool:
    for entry in protected:
        want = [p.casefold() for p in PurePosixPath(entry).parts]
        n = len(want)
        for i in range(len(parts) - n + 1):
            if all(_part_matches(parts[i + j], want[j]) for j in range(n)):
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


def _word_hits(word: _Word, protected: Sequence[str], root: Path, *, split: bool = True) -> bool:
    if any(_parts_hit(_split_parts(c), protected) for c in _candidates(word.pieces)):
        return True
    if not word.literal:
        return False
    text = word.text
    if split:  # a path hidden in one quoted argument: "tee .env", "w .env"
        for bit in re.split(r"[\s;<>|&\"'()=,:]+", text):
            if bit and bit != text and _parts_hit(_split_parts([("L", bit)]), protected):
                return True
    if text and len(text) < 1024 and "\x00" not in text and "\n" not in text:
        try:  # a symlink inside the workspace that points at a protected file
            real = (root / text).resolve().relative_to(root.resolve())
        except (OSError, ValueError, RuntimeError):
            return False
        return _is_protected(real.parts, protected)
    return False


def _substring_hit(text: str, protected: Sequence[str]) -> bool:
    low = text.casefold()
    return any(e.casefold() in low for e in protected)


def _is_recursive(texts: Sequence[str]) -> bool:
    return any(
        t == "--recursive" or (t.startswith("-") and not t.startswith("--") and set(t) & set("rR"))
        for t in texts
    )


def _reaches_root(word: _Word) -> bool:
    return not word.literal or not _split_parts(word.pieces) or word.text.startswith("..")


def _structural_denial(cmd: str, args: list[_Word]) -> str | None:
    """Commands that reach or change protected files without naming them."""
    texts = [w.text for w in args]
    rm_reaches = cmd == "rm" and _is_recursive(texts)
    if rm_reaches and any(not w.text.startswith("-") and _reaches_root(w) for w in args):
        return "a recursive delete of a glob, an expansion or the workspace root"
    if cmd == "find" and any(t.startswith(FIND_WRITE) for t in texts):
        starts: list[_Word] = []
        for w in args:
            if w.text.startswith("-"):
                break
            starts.append(w)
        if not starts or any(_reaches_root(w) for w in starts):
            return "a find write or exec action over the workspace root, a glob or an expansion"
    if cmd == "git":
        k = 0
        while k < len(texts) and texts[k].startswith("-"):
            if texts[k] == "-c" or texts[k].startswith(
                ("--config-env", "--exec-path", "--git-dir", "--work-tree")
            ):
                return "a git option can set configuration or point inside the protected tree"
            k += 2 if texts[k] == "-C" else 1
        sub = texts[k] if k < len(texts) else ""
        if sub in ("config", "hook", "update-ref", "clean"):
            return f"git {sub} can change configuration or hooks or delete ignored files"
        if sub == "stash" and any(
            t in ("--include-untracked", "--all")
            or (t.startswith("-") and not t.startswith("--") and set(t) & set("ua"))
            for t in texts[k + 1 :]
        ):
            return "git stash of untracked or ignored files can delete a protected file"
    return None


def _legacy_scan(command: str, protected: Sequence[str]) -> bool:
    """Fail closed on text the scanner cannot follow (``$(``, ``${``, backticks, bad quoting)."""
    if _substring_hit(command, protected):
        return True
    trio = "`" in command or "$(" in command or "${" in command
    return trio and (">" in command or _WRITER_RE.search(command) is not None)


def _shell_protected(command: str, protected: Sequence[str], root: Path) -> bool:
    items = _scan(command)
    if items is None or "`" in command or "$(" in command or "${" in command:
        return _legacy_scan(command, protected)
    segs: list[list[_Word]] = [[]]
    redirect = False
    for kind, val in items:
        if kind in ("op", "bad"):
            segs.append([])
            redirect = False
        elif kind == "redir":
            assert isinstance(val, str)
            redirect = ">" in val
        elif kind == "word":
            assert isinstance(val, _Word)
            if redirect:
                if _word_hits(val, protected, root, split=False):
                    return True
                redirect = False
            else:
                segs[-1].append(val)
    for seg in segs:
        if not seg:
            continue
        head, args = seg[0], seg[1:]
        name = head.text if head.literal else ""
        # A reader is exempt only when the whole command is a plain read.
        if name in READERS and _segment_denial([w.text for w in seg]) is None:
            continue
        if _structural_denial(name, args):
            return True
        split = not (name in FREE_OPTIONS or name == "printf")
        for w in args if head.literal else [head, *args]:
            if _word_hits(w, protected, root, split=split):
                return True
            hidden = w.literal and (name in INTERPRETERS or w.text.startswith("-"))
            if hidden and _substring_hit(w.text, protected):
                return True
    return False


def _checked_strings(arguments: Mapping[str, object]) -> list[str]:
    """Every string argument of a write tool that could name a place, content keys skipped."""
    out: list[str] = []
    for key, value in arguments.items():
        if key in CONTENT_ARGS and key not in PATH_ARGS:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for v in values:
            if isinstance(v, str) and (key in PATH_ARGS or ("\n" not in v and len(v) <= 4096)):
                out.append(v)
    return out


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
                why = _reader_denial(command)
                return _refuse(call, mode, why) if why else None
            if _shell_protected(command, protected, workspace.root):
                return _refuse(call, mode, "it touches a protected file")
            return None
        if mode == "read-only":
            return _refuse(call, mode, "writes are not allowed")
        if any(k in call.arguments and not isinstance(call.arguments[k], str) for k in PATH_ARGS):
            return _refuse(call, mode, "a write needs a path to check")
        raws = _checked_strings(call.arguments)
        if not raws:
            return _refuse(call, mode, "a write needs a path to check")
        for raw in raws:  # every string argument is checked, whatever its key is called
            try:
                resolved = workspace.check_write(raw)
            except (SandboxDenied, ValueError, OSError) as exc:
                return _refuse(call, mode, str(exc))
            if _is_protected(resolved.relative_to(workspace.root).parts, protected):
                return _refuse(call, mode, "the path is protected")
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
