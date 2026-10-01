"""Command tripwire for tool calls that carry a shell command line.

THIS IS A SPEED-BUMP TRIPWIRE, NOT A SANDBOX. It blocks common literal forms of destructive
commands (``rm -rf /``, disk wipes, fork bombs, download-and-run, force-push to main, Windows
drive wipes) before a tool runs. A determined or obfuscating caller can still get past it
(interpreter one-liners, multi-step indirection across calls, unusual encodings). Execution
containment is slice 8's container, not this module.

Design: deny before allow and match over the whole command line (pattern from autogpt classic
permissions.py, MIT; matcher is net-new). Every pass is linear in the command length, which is
capped at MAX_COMMAND_CHARS and never truncated. Any internal error fails closed. Denial text
never echoes the command.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from master_finhub.runtime.loop import ToolCall, ToolGuard

MAX_COMMAND_CHARS: Final = 10_000
MAX_GUARD_DEPTH: Final = 16
MAX_DEPTH: Final = 3
MAX_FUNC_NAMES: Final = 64
COMMAND_ARG_KEYS: Final = frozenset({"command", "cmd", "script", "shell_command"})
PUNCT: Final = "();<>|&`"
OPS: Final = ("&&", "||", "|&", ">>", "&>", ">&", "<(", ";", "&", "|", "(", ")", "`", ">", "<")
REDIRECTS: Final = frozenset({">", ">>", "&>", ">&"})
SYSTEM_DIRS: Final = frozenset(
    [
        "bin",
        "boot",
        "dev",
        "etc",
        "home",
        "lib",
        "lib32",
        "lib64",
        "opt",
        "proc",
        "root",
        "sbin",
        "srv",
        "sys",
        "usr",
        "var",
    ]
)
DEVICE_RE: Final = re.compile(
    r"/dev/(?:sd[a-z]|hd[a-z]|vd[a-z]|xvd[a-z]|nvme\d|mmcblk\d|disk\d|rdisk\d|mapper/|md\d|dm-\d)"
)
DRIVE_ROOT_RE: Final = re.compile(
    r"(?:[a-z]:|%systemdrive%|\$env:systemdrive)[\\/]?\*?(?:\.\*)?", re.IGNORECASE
)
WIN_SYS_RE: Final = re.compile(
    r"(?:[a-z]:|%systemdrive%|\$env:systemdrive)[\\/]"
    r"(?:windows|program files(?: \(x86\))?|users|programdata)[\\/]?\*?",
    re.IGNORECASE,
)
WIN_ENV_SYS_RE: Final = re.compile(
    r"(?:%systemroot%|%windir%|\$env:systemroot|\$env:windir)[\\/]?\*?", re.IGNORECASE
)
ASSIGN_RE: Final = re.compile(r"[A-Za-z_]\w{0,63}=.*", re.DOTALL)
CONTROL_RE: Final = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # all but \t \n \r
PY_RE: Final = re.compile(r"python[\d.]*")
FUNC_RE: Final = re.compile(r"([A-Za-z_:][\w:-]{0,63})\(\)\{|function([A-Za-z_][\w-]{0,63})\{")
WRAPPERS: Final = frozenset(
    [
        "sudo",
        "doas",
        "env",
        "nice",
        "nohup",
        "time",
        "command",
        "exec",
        "xargs",
        "busybox",
        "stdbuf",
        "timeout",
    ]
)
# NF3: wrapper flags that consume the next word (so it is not mistaken for the command).
WRAPPER_VALUE_FLAGS: Final[Mapping[str, frozenset[str]]] = {
    "sudo": frozenset({"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U"}),
    "doas": frozenset({"-u", "-C"}),
    "env": frozenset({"-u", "-C", "-S"}),
    "nice": frozenset({"-n"}),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
    "timeout": frozenset({"-s", "-k"}),
    "xargs": frozenset({"-I", "-n", "-P", "-d", "-E", "-L", "-s", "-a"}),
    "exec": frozenset({"-a"}),
    "time": frozenset({"-f", "-o"}),
}
SHELLS: Final = frozenset(["sh", "bash", "dash", "ksh", "zsh", "fish"])
POWERSHELLS: Final = frozenset({"pwsh", "powershell"})
INTERPRETERS: Final = (
    SHELLS | frozenset(["perl", "ruby", "node", "iex", "invoke-expression"]) | POWERSHELLS
)
SHELL_HOSTS: Final = SHELLS | POWERSHELLS | {"cmd"}
DOWNLOADERS: Final = frozenset(
    ["curl", "wget", "iwr", "irm", "invoke-webrequest", "invoke-restmethod", "fetch"]
)
DECODERS: Final = frozenset(["base64", "xxd", "openssl", "uudecode", "gunzip", "zcat"])
DELETERS: Final = frozenset(["rm", "remove-item", "ri", "del", "erase", "rd", "rmdir"])
PERMS: Final = frozenset(["chmod", "chown", "chgrp"])
FORMATTERS: Final = frozenset(
    [
        "mke2fs",
        "wipefs",
        "blkdiscard",
        "format-volume",
        "clear-disk",
        "initialize-disk",
        "remove-partition",
    ]
)
PROTECTED_BRANCHES: Final = frozenset({"main", "master"})

RULE_REASONS: Final[Mapping[str, str]] = {
    "recursive-delete-root": "recursive delete of a filesystem root, home folder, system folder "
    "or drive",
    "rm-no-preserve-root": "explicitly disables rm's own root protection",
    "recursive-perms-root": "recursive permission or ownership change on a root, home or system "
    "folder",
    "find-delete-root": "find-and-delete starting at a root, home or system folder",
    "format-disk": "formats or wipes a disk or partition",
    "windows-format": "formats a Windows drive",
    "raw-device-write": "writes directly to a disk device or system file",
    "redirect-raw-disk": "redirects output onto a disk device",
    "git-force-push-protected": "force-push or delete on main/master, or a force-push without "
    "naming the branch",
    "pipe-to-interpreter": "pipes downloaded or decoded content straight into an interpreter",
    "interpreter-on-download": "runs downloaded content via process substitution or eval",
    "run-downloaded-script": "runs a script downloaded earlier in the same command",
    "computed-command-name": "the command name is computed at run time; write it literally",
    "fork-bomb": "defines a self-replicating function (fork bomb)",
    "too-long": "command is longer than 10,000 characters and was not inspected",
    "unparseable": "command quoting could not be parsed",
    "nesting-too-deep": "shell-within-shell nesting is deeper than 3 levels",
    "uninspectable-command": "the command is encoded so it cannot be inspected",
    "check-failed": "the command could not be checked",
    "not-allowlisted": "(allowlist mode) the command is not in the allowed list",
}


@dataclass(frozen=True)
class CommandPolicy:
    mode: Literal["denylist", "allowlist"] = "denylist"
    allowed_commands: frozenset[str] = frozenset()


DEFAULT_POLICY: Final = CommandPolicy()


@dataclass
class _State:
    depth: int
    cwd_root: bool = False
    downloaded: set[str] = field(default_factory=set)


def cmd_name(tok: str) -> str:
    base = re.split(r"[\\/]", tok)[-1].lower()
    for ext in (".exe", ".com"):
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


def is_interpreter(name: str) -> bool:
    return name in INTERPRETERS or PY_RE.fullmatch(name) is not None


def dangerous_target(arg: str, cwd_root: bool) -> bool:
    a = arg.strip()
    if not a:
        return False
    if a[0] in "$%":
        if WIN_ENV_SYS_RE.fullmatch(a) or DRIVE_ROOT_RE.fullmatch(a):
            return True
        return a[0] == "$"  # unexpanded variable as a target: fail closed
    if DRIVE_ROOT_RE.fullmatch(a) or WIN_SYS_RE.fullmatch(a):
        return True
    if cwd_root and a in ("*", ".", "./", "./*"):
        return True
    if a[0] == "~":
        return a[1:].lstrip("/") in ("", "*", ".")
    if a[0] == "/":
        p = re.sub(r"/+", "/", a).rstrip("*") or "/"
        p = posixpath.normpath(p)
        if p == "/":
            return True
        parts = p.strip("/").split("/")
        return len(parts) == 1 and parts[0] in SYSTEM_DIRS
    return False


def recursive_flag(name: str, args: list[str]) -> bool:
    for a in args:
        al = a.lower()
        if al in ("--recursive", "/s"):
            return True
        if name in DELETERS and al.startswith("-r") and "-recurse".startswith(al):
            return True
        if a.startswith("-") and not a.startswith("--") and "r" in al[1:]:
            return True
    return False


def strip_wrappers(words: list[str]) -> list[str]:
    """Peel VAR=x assignments and wrappers (with their flag values) to expose the real command."""
    i = 0
    while i < len(words):
        if ASSIGN_RE.fullmatch(words[i]):
            i += 1
            continue
        wrapper = cmd_name(words[i])
        if wrapper not in WRAPPERS:
            break
        i += 1
        valued = WRAPPER_VALUE_FLAGS.get(wrapper, frozenset())
        while i < len(words) and words[i].startswith("-"):
            flag = words[i]
            i += 1
            if flag in valued and i < len(words):
                i += 1
        if wrapper == "timeout" and i < len(words):
            i += 1  # the duration
    return words[i:]


def git_rule(args: list[str]) -> str | None:
    if "push" not in args:
        return None
    force = delete = False
    positional: list[str] = []
    for a in args[args.index("push") + 1 :]:
        if a in ("--force", "--mirror") or a.startswith(
            ("--force-with-lease", "--force-if-includes")
        ):
            force = True
        elif a == "--delete":
            delete = True
        elif a.startswith("-") and not a.startswith("--"):
            force = force or "f" in a[1:]
            delete = delete or "d" in a[1:]
        elif not a.startswith("-"):
            positional.append(a)
    refs = positional[1:]
    force = force or any(r.startswith("+") for r in refs)
    delete = delete or any(r.startswith(":") for r in refs)
    if not (force or delete):
        return None
    if not refs:
        return "git-force-push-protected"
    for r in refs:
        dst = r.lstrip("+").split(":")[-1].removeprefix("refs/heads/")
        if dst.lower() in PROTECTED_BRANCHES:
            return "git-force-push-protected"
    return None


def _inline_kind(host: str, arg: str) -> Literal["cmd", "enc"] | None:
    """Classify an argument of a shell host: carries inline command text, or an encoded one."""
    al = arg.lower()
    if host in SHELLS:
        letters = arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""
        return "cmd" if "c" in letters else None
    if host == "cmd":
        return "cmd" if al in ("/c", "/k") else None
    if len(al) >= 2 and al[0] == "-":  # PowerShell accepts any unambiguous prefix (NF2)
        if "-command".startswith(al):
            return "cmd"
        if "-encodedcommand".startswith(al) or al == "-ec":
            return "enc"
    return None


def _inline_rule(name: str, args: list[str], depth: int) -> str | None:
    if name == "eval":
        return _check(" ".join(args), depth + 1)
    if name not in SHELL_HOSTS:
        return None
    for i, a in enumerate(args):
        kind = _inline_kind(name, a)
        if kind == "enc":
            return "uninspectable-command"
        if kind == "cmd" and i + 1 < len(args):
            return _check(" ".join(args[i + 1 :]), depth + 1)
    return None


def segment_rule(words: list[str], state: _State) -> str | None:
    core = strip_wrappers(words)
    if not core:
        return None
    if core[0].startswith(("$", "`")):
        return "computed-command-name"
    name, args = cmd_name(core[0]), core[1:]
    positional = [a for a in args if not a.startswith("-") and a.lower() not in ("/s", "/q")]
    if name == "cd":
        state.cwd_root = bool(args) and dangerous_target(args[0], False)
        return None
    if name in DELETERS:
        if "--no-preserve-root" in args:
            return "rm-no-preserve-root"
        if recursive_flag(name, args) and any(
            dangerous_target(a, state.cwd_root) for a in positional
        ):
            return "recursive-delete-root"
    if (
        name in PERMS
        and recursive_flag(name, args)
        and any(dangerous_target(a, state.cwd_root) for a in positional)
    ):
        return "recursive-perms-root"
    deletes = "-delete" in args or (
        "-exec" in args and any(cmd_name(a) in ("rm", "shred") for a in args)
    )
    find_start_bad = (
        not args or args[0].startswith("-") or dangerous_target(args[0], state.cwd_root)
    )
    if name == "find" and deletes and find_start_bad:
        return "find-delete-root"
    if name.startswith("mkfs") or name in FORMATTERS:
        return "format-disk"
    if name == "format" and args and re.fullmatch(r"[a-z]:", args[0], re.IGNORECASE):
        return "windows-format"
    if name == "dd" and any(a.startswith("of=") and DEVICE_RE.match(a[3:]) for a in args):
        return "raw-device-write"
    if name in ("shred", "truncate", "tee"):
        for a in positional:
            if DEVICE_RE.match(a) or (
                a.startswith("/") and a.strip("/").split("/")[0] in SYSTEM_DIRS
            ):
                return "raw-device-write"
    if (
        name in ("cp", "mv", "install")
        and positional
        and (DEVICE_RE.match(positional[-1]) or dangerous_target(positional[-1], False))
    ):
        return "raw-device-write"
    for i, a in enumerate(core):
        if a in REDIRECTS and i + 1 < len(core):
            target = core[i + 1]
            if DEVICE_RE.match(target):
                return "redirect-raw-disk"
            if name in DOWNLOADERS:
                state.downloaded.add(target.removeprefix("./"))
    if name == "git":
        rule = git_rule(args)
        if rule:
            return rule
    if name in DOWNLOADERS:
        for i, a in enumerate(args):
            if a.lower() in ("-o", "--output", "-outfile") and i + 1 < len(args):
                state.downloaded.add(args[i + 1].removeprefix("./"))
    if is_interpreter(name) and any(a.removeprefix("./") in state.downloaded for a in args):
        return "run-downloaded-script"
    return _inline_rule(name, args, state.depth)


def split_ops(tok: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(tok):
        op = next(o for o in OPS if tok.startswith(o, i))
        out.append(op)
        i += len(op)
    return out


def lex(command: str, posix: bool) -> list[str]:
    lexer = shlex.shlex(command.replace("\n", ";"), posix=posix, punctuation_chars=PUNCT)
    lexer.whitespace_split = True
    tokens = list(lexer)
    return tokens if posix else [t.strip("\"'") if t[:1] in "\"'" else t for t in tokens]


def token_streams(command: str) -> list[list[str]]:
    """POSIX and non-POSIX lexes. A trailing backslash only breaks the POSIX lex, so retry it
    without that backslash: otherwise only the weaker stream is checked (NF1)."""
    streams: list[list[str]] = []
    for posix in (True, False):
        try:
            streams.append(lex(command, posix))
        except ValueError:
            if posix and command.endswith("\\"):
                try:
                    streams.append(lex(command[:-1], True))
                except ValueError:
                    pass
    return streams


def segments(tokens: list[str]) -> list[tuple[str, list[str]]]:
    """Split a token stream into (separator_before, words). Redirect operators stay as words."""
    out: list[tuple[str, list[str]]] = []
    sep, words = "", []
    for tok in tokens:
        if tok and all(c in PUNCT for c in tok):
            for op in split_ops(tok):
                if op in REDIRECTS or op == "<":
                    words.append(op)
                    continue
                if op == "(" and words and words[-1] == "$":
                    words.pop()
                    op = "$("
                out.append((sep, words))
                sep, words = op, []
        else:
            words.append(tok)
    out.append((sep, words))
    return out


def fork_bomb(command: str) -> bool:
    flat = re.sub(r"\s+", "", command)
    names: set[str] = set()
    for m in FUNC_RE.finditer(flat):
        names.add(m.group(1) or m.group(2))
        if len(names) > MAX_FUNC_NAMES:
            return True
    return any(f"{n}|{n}&" in flat for n in names)


def _check_tokens(tokens: list[str], depth: int) -> str | None:
    state = _State(depth=depth)
    segs = segments(tokens)
    prev_name, pipe_source = "", False
    for idx, (sep, words) in enumerate(segs):
        core = strip_wrappers(words)
        name = cmd_name(core[0]) if core else ""
        if sep in ("$(", "`") and idx > 0 and not strip_wrappers(segs[idx - 1][1]):
            return "computed-command-name"
        if (
            sep in ("$(", "<(", "`")
            and name in DOWNLOADERS
            and (is_interpreter(prev_name) or prev_name in ("eval", "source", "."))
        ):
            return "interpreter-on-download"
        if sep in ("|", "|&"):
            json_tool = PY_RE.fullmatch(name) is not None and core[1:3] == ["-m", "json.tool"]
            if is_interpreter(name) and pipe_source and not json_tool:
                return "pipe-to-interpreter"
        elif sep not in ("", "$(", "<(", "`", "("):
            pipe_source = False
        if name in DOWNLOADERS or name in DECODERS:
            pipe_source = True
        rule = segment_rule(words, state)
        if rule:
            return rule
        if core:
            prev_name = name
    return None


def _normalise(command: str) -> str:
    # Bash deletes backslash-newline outright, so `r\<nl>m` is `rm` (NF1).
    return command.replace("\\\r\n", "").replace("\\\n", "")


def _check(command: str, depth: int = 0) -> str | None:
    if depth > MAX_DEPTH:
        return "nesting-too-deep"
    if len(command) > MAX_COMMAND_CHARS:
        return "too-long"
    if CONTROL_RE.search(command):
        return "unparseable"  # NUL/control bytes: the shell would see something else (fail closed)
    command = _normalise(command)
    if fork_bomb(command):
        return "fork-bomb"
    streams = token_streams(command)
    if not streams:
        return "unparseable"
    for tokens in streams:
        rule = _check_tokens(tokens, depth)
        if rule:
            return rule
    return None


def check_rule(command: str) -> str | None:
    """Return the matched rule name, or None. Any internal error fails closed."""
    try:
        return _check(command)
    except Exception:  # noqa: BLE001 - fail closed
        return "check-failed"


def command_names(command: str) -> list[str]:
    """Normalised command name of every segment; computed names keep their leading $ or backtick."""
    streams = token_streams(_normalise(command))
    if not streams:
        return []
    names: list[str] = []
    for _sep, words in segments(streams[0]):
        core = strip_wrappers(words)
        if core:
            names.append(core[0] if core[0].startswith(("$", "`")) else cmd_name(core[0]))
    return names


def _denial(rule: str) -> str:
    return (
        f"Blocked by safety policy (rule {rule}): {RULE_REASONS[rule]}. "
        "Use a path inside the workspace, or ask Daniel to run it manually."
    )


def check_command(command: str, policy: CommandPolicy = DEFAULT_POLICY) -> str | None:
    """Return denial text for the model, or None to allow. Denylist always wins."""
    rule = check_rule(command)
    if rule:
        return _denial(rule)
    if policy.mode != "allowlist":
        return None
    try:
        names = command_names(command)
    except Exception:  # noqa: BLE001 - fail closed
        return _denial("check-failed")
    for name in names:
        if name not in policy.allowed_commands:
            shown = name if re.fullmatch(r"[a-z0-9._-]{1,32}", name) else "[command]"
            return (
                f"Blocked by safety policy (rule not-allowlisted): '{shown}' is not in the "
                "allowed command list."
            )
    return None


def _check_value(value: Any, policy: CommandPolicy) -> str | None:
    if isinstance(value, str):
        return check_command(value, policy)
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return check_command(shlex.join(value), policy)
    return _denial("check-failed")


def _guard(call: ToolCall, policy: CommandPolicy) -> str | None:
    try:
        stack: list[tuple[Any, int]] = [(call.arguments, 0)]
        while stack:
            node, depth = stack.pop()
            if depth > MAX_GUARD_DEPTH:
                return _denial("check-failed")
            if isinstance(node, dict):
                for key, val in node.items():
                    if str(key).casefold() in COMMAND_ARG_KEYS:
                        denial = _check_value(val, policy)
                        if denial is not None:
                            return denial
                    else:
                        stack.append((val, depth + 1))
            elif isinstance(node, (list, tuple)):
                stack.extend((v, depth + 1) for v in node)
        return None
    except Exception:  # noqa: BLE001 - fail closed
        return _denial("check-failed")


def guard_tool_call(call: ToolCall) -> str | None:
    return _guard(call, DEFAULT_POLICY)


def make_guard(policy: CommandPolicy) -> ToolGuard:
    return lambda call: _guard(call, policy)
