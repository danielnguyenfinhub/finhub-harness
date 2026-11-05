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


def _reader_denial(command: str) -> str | None:
    tokens = _tokens(command)
    segments = _segments(tokens) if tokens else None
    if segments is None:
        return "command is empty or cannot be judged read-only"
    for seg in segments:
        if not seg:
            return "empty command in a chain"
        cmd, args = seg[0], seg[1:]
        if cmd not in READERS:
            return f"'{cmd}' is not on the read-only list"
        if any(a.startswith("--output") for a in args):
            return "an output flag writes a file"
        if cmd == "git" and (not args or args[0] not in GIT_READ):
            return "only read-only git subcommands are allowed"
        for flag, prefix in BAD_FLAGS.get(cmd, ()):
            if _flag_hit(args, flag, prefix):
                return f"flag {flag} can write or run code"
    return None


def _is_protected(parts: Sequence[str], protected: Sequence[str]) -> bool:
    for entry in protected:
        want = PurePosixPath(entry).parts
        n = len(want)
        if any(tuple(parts[i : i + n]) == want for i in range(len(parts) - n + 1)):
            return True
    return False


def _shell_protected(command: str, protected: Sequence[str]) -> bool:
    tokens = _tokens(command)
    if tokens is None:
        return False
    redirect = False
    start = True
    cmd = ""
    for t in tokens:
        if t in OPERATORS:
            start = True
        elif _is_punct(t):
            redirect = t.startswith(">")
        elif start:
            cmd, start = t, False
        else:
            if _is_protected(PurePosixPath(t).parts, protected) and (
                redirect or cmd not in READERS
            ):
                return True
            redirect = False
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
        raw = next((call.arguments[k] for k in PATH_ARGS if k in call.arguments), None)
        if not isinstance(raw, str):
            return _refuse(call, mode, "a write needs a path to check")
        try:
            resolved = workspace.check_write(raw)
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
