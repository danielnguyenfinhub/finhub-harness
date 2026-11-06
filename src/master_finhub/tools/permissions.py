"""Session permission modes: read-only, workspace-write, full-access (CW01).

Ideas adapted (own code, nothing copied) from the MIT CowAgent
``references/cowagent/agent/permission/policy.py:39`` (named modes) and ``:595`` (a protected-file
list that holds even where writes are allowed). A mode guard only adds refusals: ``effective_guard``
puts the base command guard first, so no mode, full-access included, switches it off, and a child
agent (``subagent._both``) can only get stricter than its parent.

Like the base guard this is a tripwire on the text of a call, not a sandbox.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
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
GIT_READ: Final = frozenset(["status", "log", "diff", "show", "rev-parse", "ls-files", "blame"])
OPERATORS: Final = frozenset({";", "&&", "||", "|"})
PUNCT: Final = frozenset(";<>|&()")
# (flag, match as prefix): a prefix flag also catches -fprintf, --pre=cmd and -ofile
BAD_FLAGS: Final[dict[str, tuple[tuple[str, bool], ...]]] = {
    "find": (
        ("-exec", True),
        ("-ok", True),
        ("-delete", False),
        ("-fprint", True),
        ("-fls", False),
    ),
    "sort": (("-o", True),),  # --output* is refused for every command above
    "date": (("-s", False), ("--set", True)),
    "rg": (("--pre", True),),
    "file": (("-C", False),),
}
# Grouped short-flag letters and long options (abbreviations count) that write or run code.
# When unsure the guard denies: "-ro", "-uo", "--o", "--out" all match sort's output flag.
SHORT_BAD: Final[dict[str, str]] = {"sort": "o", "date": "s", "file": "C"}
LONG_BAD: Final[dict[str, tuple[str, ...]]] = {
    "*": ("output",),
    "sort": ("compress-program",),
    "date": ("set",),
    "file": ("compile",),
    "rg": ("pre",),
}


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
    return (
        f"Tool '{call.name}' refused in {mode} mode: {why}. Do not retry it; "
        "ask the operator to switch to a wider mode if the work needs it."
    )


def _tokens(command: str) -> list[str] | None:
    if "\n" in command or "`" in command or "$(" in command or "${" in command:
        return None
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return None


def _is_punct(token: str) -> bool:
    return bool(token) and set(token) <= PUNCT


def _segments(tokens: Sequence[str]) -> list[list[str]] | None:
    out: list[list[str]] = [[]]
    for t in tokens:
        if t in OPERATORS:
            out.append([])
        elif _is_punct(t):
            return None  # redirect, background or subshell
        else:
            out[-1].append(t)
    return out


def _flag_hit(args: Sequence[str], flag: str, prefix: bool) -> bool:
    return any(a == flag or (prefix and a.startswith(flag)) for a in args)


def _bad_option(cmd: str, arg: str) -> bool:
    if arg.startswith("--"):
        name = arg[2:].split("=", 1)[0]
        return bool(name) and any(
            long.startswith(name) for long in LONG_BAD["*"] + LONG_BAD.get(cmd, ())
        )
    letters = SHORT_BAD.get(cmd, "")
    return arg.startswith("-") and any(c in letters for c in arg[1:])


def _segment_denial(seg: Sequence[str]) -> str | None:
    """Why one command of a chain is not a plain read, or None."""
    if not seg:
        return "empty command in a chain"
    cmd, args = seg[0], seg[1:]
    if cmd not in READERS:
        return f"'{cmd}' is not on the read-only list"
    if any(_bad_option(cmd, a) for a in args):
        return "an option can write a file or run code"
    if cmd == "git" and (not args or args[0] not in GIT_READ):
        return "only read-only git subcommands are allowed"
    for flag, prefix in BAD_FLAGS.get(cmd, ()):
        if _flag_hit(args, flag, prefix):
            return f"flag {flag} can write or run code"
    return None


def _reader_denial(command: str) -> str | None:
    tokens = _tokens(command)
    segments = _segments(tokens) if tokens else None
    if segments is None:
        return "command is empty or cannot be judged read-only"
    for seg in segments:
        why = _segment_denial(seg)
        if why:
            return why
    return None


def _is_protected(parts: Sequence[str], protected: Sequence[str]) -> bool:
    for entry in protected:
        want = tuple(p.casefold() for p in PurePosixPath(entry).parts)
        n = len(want)
        folded = tuple(p.casefold() for p in parts)
        if any(folded[i : i + n] == want for i in range(len(folded) - n + 1)):
            return True
    return False


def _shell_protected(command: str, protected: Sequence[str]) -> bool:
    tokens = _tokens(command)
    if tokens is None:
        # Cannot be tokenized (newline, backtick, $(, ${, bad quoting): a protected name could sit
        # behind a redirect we cannot see, so fail closed on a casefolded substring scan. This
        # over-refuses (".git" matches ".github") by design; it only applies to untokenizable input.
        low = command.casefold()
        return any(entry.casefold() in low for entry in protected)
    folded = [e.casefold() for e in protected]
    segs: list[list[str]] = [[]]
    redirect = False
    for t in tokens:
        if t in OPERATORS:
            segs.append([])
        elif _is_punct(t):
            redirect = t.startswith(">")
        else:
            if redirect and _is_protected(PurePosixPath(t).parts, protected):
                return True
            redirect = False
            segs[-1].append(t)
    for seg in segs:
        if not seg:
            continue
        cmd, args = seg[0], seg[1:]
        # A reader is exempt only when the whole command is a plain read: a write flag, a git
        # subcommand that writes, etc. count, so a protected name anywhere in it is refused.
        if cmd in READERS and _segment_denial(seg) is None:
            continue
        for a in args:
            if _is_protected(PurePosixPath(a).parts, protected):
                return True
            if cmd in READERS and any(e in a.casefold() for e in folded):
                return True  # e.g. "-o.env" glued to a write flag
    return False


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
            if _shell_protected(command, protected):
                return _refuse(call, mode, "it touches a protected file")
            return None
        if mode == "read-only":
            return _refuse(call, mode, "writes are not allowed")
        raws = [call.arguments[k] for k in PATH_ARGS if k in call.arguments]
        if not raws or not all(isinstance(r, str) for r in raws):
            return _refuse(call, mode, "a write needs a path to check")
        for raw in raws:  # every path key present is checked, not only the first
            try:
                resolved = workspace.check_write(str(raw))
            except SandboxDenied as exc:
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
