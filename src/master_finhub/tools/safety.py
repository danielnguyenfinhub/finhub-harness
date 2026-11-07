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

Not covered: a path the command text does not contain. Paths that arrive through a pipe, stdin,
a file named by an option (`xargs -a`, `curl -d @file`), `git show :.env` or an interpreter's
own code string are invisible here; xargs of a reader, `find -exec sh -c` and a reader fed by a
substitution that names a credential are refused instead (rule unscannable-path), but a
substitution that does not name one (`cat d/$(ls d)`) is only judged as the command it is.
Wildcards are expanded against the real directory in part (4,096 entries per word, 65,536 per
call), hard links by inode only for the credential files under the home directory.
"""

from __future__ import annotations

import itertools
import os
import posixpath
import re
import shlex
from collections.abc import Iterable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from master_finhub.runtime.loop import ToolCall, ToolGuard
from master_finhub.tools import (
    sensitive_paths as _sp,
)  # the bool `sensitive_paths` shadows the module

MAX_COMMAND_CHARS: Final = 10_000
MAX_GUARD_DEPTH: Final = 16
MAX_DEPTH: Final = 3
MAX_FUNC_NAMES: Final = 64
MAX_BRACE_FORMS: Final = 64
MAX_TRACKED_VARS: Final = 64
UNDER_DIRS: Final = frozenset({"home", "usr", "var", "etc"})  # rm of a child of these is refused
COMMAND_ARG_KEYS: Final = frozenset({"command", "cmd", "script", "shell_command"})
# adapted from references/openharness/src/openharness/engine/query.py:1026 (MIT): file_path, path, root
PATH_ARG_KEYS: Final = frozenset(
    {
        "file_path",
        "path",
        "root",
        "paths",
        "filepath",
        "filename",
        "file",
        "dir",
        "directory",
        "cwd",
        "source",
        "destination",
        "src",
        "dst",
        "target",
        "uri",
    }
)
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
VAR_RE: Final = re.compile(r"\$(\w+)|\$\{(\w+)\}")
REF_RE: Final = re.compile(r"\$(\w+)|\$\{(\w+)(?:(:?[-+=?])([^{}]*))?\}")  # plus ${X:-w} forms
MAX_VAR_PRODUCT: Final = 64  # readings of one word; past it only the first and last readings
MAX_SUBST_BODIES: Final = 16
MAX_DYN_DIRS: Final = 64  # directories tried for a relative word after a non-literal `cd`
DIR_CMDS: Final = frozenset({"env", "tar", "git", "make"})
SUBST_READERS: Final = frozenset({"cat", "head", "tail", "less", "more", "cp", "mv", "tar"})
CRED_WORDS: Final = (".ssh", ".aws", ".env", "gnupg", "kube", "docker", "npmrc", "netrc", "pypirc")
CRED_WORDS_ANY: Final = (*CRED_WORDS, "id_", "rsa")
XARGS_READERS: Final = SUBST_READERS | frozenset(
    [
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "sed",
        "awk",
        "sort",
        "uniq",
        "wc",
        "od",
        "xxd",
        "strings",
        "base64",
        "nl",
        "tac",
        "rev",
        "bat",
        "jq",
        "diff",
        "cmp",
        "file",
        "md5sum",
        "sha1sum",
        "sha256sum",
        "shasum",
        "scp",
        "rsync",
        "openssl",
        "source",
    ]
)
GLOB_CHARS_RE: Final = re.compile(r"[*?\[]")
BRACE_RE: Final = re.compile(r"\{([^{}]*,[^{}]*)\}")
ANSI_C_RE: Final = re.compile(r"\$'((?:[^'\\]|\\.)*)'", re.DOTALL)
ANSI_ESC_RE: Final = re.compile(
    r"\\(x[0-9A-Fa-f]{1,2}|[0-7]{1,3}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}|c.|.)", re.DOTALL
)
ANSI_SIMPLE: Final[Mapping[str, str]] = {
    "a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f",
    "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?",
}  # fmt: skip
ASSIGN_PREFIXES: Final = frozenset({"export", "declare", "local", "readonly", "typeset"})
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
    "env": frozenset({"-u", "-C", "-S", "--chdir"}),
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
    "sensitive-path": "touches a credential or key location (SSH, cloud, registry or token "
    "files); ask Daniel to handle credentials manually",
    "path-too-long": "a path or command word is longer than its limit after expanding ~ and "
    "$VARS (4,096 for path arguments, 10,000 in commands) and was not inspected",
    "path-budget": "the call names more path components than can be inspected at once "
    "(16,384) or expands more wildcard entries than can be listed (65,536); split it into "
    "smaller calls",
    "unscannable-path": "the files it reads come from xargs, a find -exec shell or a command "
    "substitution that names a credential location, so they cannot be checked; write the path "
    "out literally",
}


@dataclass(frozen=True)
class CommandPolicy:
    mode: Literal["denylist", "allowlist"] = "denylist"
    allowed_commands: frozenset[str] = frozenset()


DEFAULT_POLICY: Final = CommandPolicy()


@dataclass
class _State:
    depth: int
    sensitive: bool = True
    cwd_root: bool = False
    cwd: str | None = None  # literal directory after `cd`; None until a literal `cd`
    vars: dict[str, str] = field(default_factory=dict)  # NAME=literal set earlier in the command
    downloaded: set[str] = field(default_factory=set)
    stack: list[tuple[str | None, str | None]] = field(default_factory=list)  # pushd/popd
    dyn_base: str | None = None  # last known directory before a non-literal `cd`
    extra: list[str] = field(default_factory=list)  # `env -C`, `tar -C`, `git -C`: this segment
    extra_dyn: str | None = None  # a non-literal such target (this segment)
    dyn_cache: dict[str, list[str]] = field(default_factory=dict)
    var_overflow: bool = False  # more than MAX_TRACKED_VARS names: later `$` words are refused


def cmd_name(tok: str) -> str:
    base = re.split(r"[\\/]", tok)[-1].lower()
    for ext in (".exe", ".com"):
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


def is_interpreter(name: str) -> bool:
    return name in INTERPRETERS or PY_RE.fullmatch(name) is not None


def dangerous_target(arg: str, cwd_root: bool, under: bool = False) -> bool:
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
        if len(parts) == 1 and parts[0] in SYSTEM_DIRS:
            return True
        # under: a child of /home, /usr, /var or /etc, or the user's home itself
        return under and (
            (len(parts) == 2 and parts[0] in UNDER_DIRS) or p == posixpath.normpath(_home())
        )
    return False


def _home() -> str:
    return os.path.expanduser("~")


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


def _inline_rule(name: str, args: list[str], depth: int, sensitive: bool) -> str | None:
    if name == "eval":
        return _check(" ".join(args), depth + 1, sensitive)
    if name not in SHELL_HOSTS:
        return None
    for i, a in enumerate(args):
        kind = _inline_kind(name, a)
        if kind == "enc":
            return "uninspectable-command"
        if kind == "cmd" and i + 1 < len(args):
            return _check(" ".join(args[i + 1 :]), depth + 1, sensitive)
    return None


def _pathish(word: str) -> bool:
    return "/" in word or "\\" in word or word.startswith(("~", ".", "$"))


def _subst(word: str, names: Mapping[str, str]) -> str:
    """Replace $NAME and ${NAME} that were set to a literal earlier in the same command."""
    if not names or "$" not in word:
        return word
    return VAR_RE.sub(lambda m: names.get(m.group(1) or m.group(2), m.group(0)), word)


class _TooManyForms(Exception):
    pass


def _var_forms(word: str, names: Mapping[str, str]) -> list[str]:
    """Every reading of one word's variables. The first is `_subst`'s. A name the guard cannot
    resolve reads as itself and as empty; `${X:-w}`, `${X-w}` and `${X:=w}` also as `w`, and
    `${X:+w}` and `${X+w}` also as `w` or empty (a set variable). With more than
    MAX_VAR_PRODUCT combinations only the first and last reading of every reference are kept."""
    if "$" not in word:
        return [word]
    refs = list(REF_RE.finditer(word))
    if not refs:
        return [word]
    alts: list[list[str]] = []
    for m in refs:
        name, op, w = m.group(1) or m.group(2), m.group(3), _subst(m.group(4) or "", names)
        known = names.get(name)
        if op is None:
            a = [known] if known is not None else [m.group(0), ""]
        else:
            a = [m.group(0), *([known] if known is not None else []), w, ""]
        alts.append(list(dict.fromkeys(a)))
    size = 1
    for a in alts:
        size *= len(a)
        if size > MAX_VAR_PRODUCT:
            break
    combos: Iterable[tuple[str, ...]]
    if size <= MAX_VAR_PRODUCT:
        combos = itertools.product(*alts)
    else:
        combos = [tuple(a[0] for a in alts), tuple(a[-1] for a in alts)]
    out: list[str] = []
    for combo in combos:
        pieces: list[str] = []
        last = 0
        for m, rep in zip(refs, combo, strict=True):
            pieces += [word[last : m.start()], rep]
            last = m.end()
        out.append("".join(pieces) + word[last:])
    return list(dict.fromkeys(out))


def _literal_dir(arg: str, names: Mapping[str, str], cwd: str | None) -> str | None:
    """The directory a literal `cd`-like target names, or None if it is not literal."""
    t = os.path.expanduser(_subst(arg, names)) if arg else _home()
    if any(c in t for c in "$`*?[{") or not t:
        return None
    new = posixpath.normpath(t if t.startswith("/") or cwd is None else posixpath.join(cwd, t))
    return new if len(new) <= _sp.PATH_MAX_CHARS else None


def _dyn_dirs(base: str, state: _State) -> list[str]:
    """`base` and the directories under it down to two levels (MAX_DYN_DIRS, and the entries
    read count against the call's glob-entry budget): where a non-literal `cd` may have gone."""
    if base in state.dyn_cache:
        return state.dyn_cache[base]
    scan = _sp.current_scan() or _sp.Scan()
    out, todo = [base], [(base, 0)]
    while todo and len(out) < MAX_DYN_DIRS:
        d, depth = todo.pop(0)
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                scan.entries_left -= 1
                if scan.entries_left < 0 or len(out) >= MAX_DYN_DIRS:
                    break
                try:
                    if e.is_dir():
                        out.append(e.path)
                        if depth < 1:
                            todo.append((e.path, depth + 1))
                except OSError:
                    continue
    state.dyn_cache[base] = out
    return out


def _seg_dirs(words: list[str], joined: str, state: _State) -> tuple[list[str], str | None]:
    """Directories this one command runs in or reads relative to: `env -C D`, `env --chdir D`,
    `--chdir=D`, `tar -C D`, `--directory=D`, `git -C D`, `make -C D`. The second value is the
    last known directory when a target is not literal."""
    if "-C" not in joined and "--chdir" not in joined and "--directory" not in joined:
        return [], None
    if not DIR_CMDS & {cmd_name(w) for w in words}:
        return [], None
    base = state.cwd if state.cwd is not None else os.getcwd()
    dirs: list[str] = []
    dyn: str | None = None
    for i, w in enumerate(words):
        if w in ("-C", "--chdir", "--directory"):
            target = words[i + 1] if i + 1 < len(words) else ""
        elif w.startswith(("--chdir=", "--directory=")):
            target = w.partition("=")[2]
        elif w.startswith("-C") and not w.startswith("-C=") and len(w) > 2:
            target = w[2:]
        else:
            continue
        lit = _literal_dir(target, state.vars, base) if target else None
        if lit is None:
            dyn = base
        else:
            dirs.append(lit)
    return dirs[:MAX_DYN_DIRS], dyn


def _braces(word: str) -> list[str]:
    """Comma brace expansion of one word, innermost first, at most MAX_BRACE_FORMS results."""
    forms = [word]
    for _ in range(MAX_BRACE_FORMS):
        out: list[str] = []
        changed = False
        for f in forms:
            m = BRACE_RE.search(f)
            if m is None:
                out.append(f)
                continue
            changed = True
            out.extend(f[: m.start()] + alt + f[m.end() :] for alt in m.group(1).split(","))
            if len(out) > MAX_BRACE_FORMS:
                raise _TooManyForms
        forms = out
        if not changed:
            break
    return forms


def _exists(path: str) -> bool:
    try:
        os.lstat(path)
    except (OSError, ValueError):
        return False
    return True


def _word_forms(word: str, state: _State) -> list[str]:
    """What the shell may turn one raw word into: known variables replaced, braces expanded, and
    (after a literal `cd`) the same relative word under the new directory."""
    if state.var_overflow and "$" in word:
        raise _TooManyForms
    if (
        "$" not in word
        and "{" not in word
        and state.cwd is None
        and not state.extra
        and state.dyn_base is None
        and state.extra_dyn is None
    ):
        return [word]  # the common word: nothing to read two ways
    forms: list[str] = []
    for w in _var_forms(word, state.vars):
        forms += _braces(w) if "{" in w and "," in w else [w]
    forms = list(dict.fromkeys(forms))
    rel = [f for f in forms if not f.startswith(("/", "~", "$"))]
    bases = ([state.cwd] if state.cwd is not None else []) + state.extra
    for b in (state.dyn_base, state.extra_dyn):
        if b is not None:  # a non-literal `cd`: the word may be relative to any directory below
            bases += _dyn_dirs(b, state)
            rel = [f for f in rel if not f.startswith("-")]
    forms += [posixpath.join(b, f) for b in dict.fromkeys(bases) for f in rel]
    return forms


def _form_rule(f: str) -> str | None:
    rule = _sp.sensitive_rule(f, resolve=_pathish(f) or _exists(f), max_chars=MAX_COMMAND_CHARS)
    if rule is None and GLOB_CHARS_RE.search(f):
        rule = _sp.glob_rule(f, _sp.current_scan() or _sp.Scan())
    return rule


def _sensitive_word_rule(words: list[str], state: _State) -> str | None:
    """OH31: every raw word, before strip_wrappers, so VAR=~/.x and wrapper flag values count.
    A bare word is walked too when a file of that name exists (a symlink alias), and a word with
    wildcards is expanded against the real directory and each match that needs it is walked."""
    scan = _sp.current_scan() or _sp.Scan()
    for w in words:
        try:
            forms = _word_forms(w, state)
        except _TooManyForms:
            return "check-failed"
        for f in forms:
            if f not in scan.cmd:
                scan.cmd[f] = _form_rule(f)
            if scan.cmd[f] is not None:
                return scan.cmd[f]
    return None


def _track(words: list[str], core: list[str], state: _State) -> None:
    """Remember NAME=literal assignments and literal `cd` targets for the words that follow."""
    for w in words:
        if ASSIGN_RE.fullmatch(w):
            key, _, val = w.partition("=")
            val = _subst(val, state.vars)
            if key not in state.vars and len(state.vars) >= MAX_TRACKED_VARS:
                state.var_overflow = True  # a name the guard stopped tracking could hide a path
            if (
                "$" in val
                or "`" in val
                or (key not in state.vars and len(state.vars) >= MAX_TRACKED_VARS)
            ):
                state.vars.pop(key, None)
            else:
                state.vars[key] = val
        elif w not in ASSIGN_PREFIXES and not w.startswith("-"):
            break
    name = cmd_name(core[0]) if core else ""
    if name == "popd":
        if state.stack:
            state.cwd, state.dyn_base = state.stack.pop()
        return
    if name in ("cd", "pushd"):
        args = [_subst(a, state.vars) for a in core[1:]]
        target = [a for a in args if not a.startswith("-")]
        if args and not target:
            return  # `cd -` and the like: keep the last known directory
        if name == "pushd" and any(a.startswith("+") for a in args):
            return  # a rotation of the stack: not followed
        if name == "pushd" and len(state.stack) < MAX_TRACKED_VARS:
            state.stack.append((state.cwd, state.dyn_base))
        new = _literal_dir(target[0] if target else "", state.vars, state.cwd)
        if new is None:
            # not literal: words are checked as written, under the last known directory and
            # under the directories below it that the guard can list
            if state.dyn_base is None:
                state.dyn_base = state.cwd if state.cwd is not None else os.getcwd()
            return
        state.cwd = new
        if new.startswith("/"):
            state.dyn_base = None


def _bodies(word: str) -> list[str]:
    """Texts of the `$(...)` and backtick substitutions inside one lexed word (quotes already
    removed, so these are substitutions bash runs inside double quotes). At most MAX_SUBST_BODIES
    are read; one more makes the caller refuse."""
    out: list[str] = []
    i, n = 0, len(word)
    while i < n and len(out) <= MAX_SUBST_BODIES:
        if word.startswith("$(", i):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += (word[j] == "(") - (word[j] == ")")
                j += 1
            out.append(word[i + 2 : j - 1 if depth == 0 else j])
            i = j
        elif word[i] == "`":
            j = word.find("`", i + 1)
            j = n if j < 0 else j
            out.append(word[i + 1 : j])
            i = j + 1
        else:
            i += 1
    return out


def _quoted_subst_rule(words: list[str], joined: str, state: _State) -> str | None:
    """A substitution inside double quotes is one lexed word; judge its text as a command (the
    old R5 gap), under the variables and directory known so far."""
    if "$(" not in joined and "`" not in joined:
        return None
    for w in words:
        if "$(" not in w and "`" not in w:
            continue
        bodies = _bodies(w)
        if len(bodies) > MAX_SUBST_BODIES:
            return "check-failed"
        for body in bodies:
            text = _subst(body, state.vars)
            if state.cwd is not None:
                text = f"cd {shlex.quote(state.cwd)}; {text}"
            rule = _check(text, state.depth + 1, state.sensitive)
            if rule:
                return rule
    return None


def _unscannable(words: list[str], core: list[str], name: str, args: list[str]) -> bool:
    """xargs, find -exec of a shell: the paths are not in the text. (A substitution naming a
    credential location is judged in _check_tokens.)"""
    if (name in XARGS_READERS or is_interpreter(name) or name in DOWNLOADERS) and any(
        cmd_name(w) == "xargs" for w in words[: len(words) - len(core)]
    ):
        return True  # a program that reads or runs the files xargs hands it
    if name == "find":
        for i, a in enumerate(args):
            if a in ("-exec", "-execdir", "-ok", "-okdir") and any(
                cmd_name(b) in SHELL_HOSTS for b in args[i + 1 :]
            ):
                return True
    return False


def segment_rule(words: list[str], state: _State) -> str | None:
    if state.sensitive:
        joined = " ".join(words)
        state.extra, state.extra_dyn = _seg_dirs(words, joined, state)
        try:
            hit = _sensitive_word_rule(words, state)
        finally:
            state.extra, state.extra_dyn = [], None
        if hit:
            return hit
        hit = _quoted_subst_rule(words, joined, state)
        if hit:
            return hit
    core = strip_wrappers(words)
    _track(words, core, state)
    if not core:
        return None
    if core[0].startswith(("$", "`")):
        return "computed-command-name"
    name, args = cmd_name(core[0]), core[1:]
    positional = [a for a in args if not a.startswith("-") and a.lower() not in ("/s", "/q")]
    if name == "cd":
        state.cwd_root = bool(args) and dangerous_target(args[0], False, True)
        return None
    if name in DELETERS:
        if "--no-preserve-root" in args:
            return "rm-no-preserve-root"
        if recursive_flag(name, args) and any(
            dangerous_target(a, state.cwd_root, True) for a in positional
        ):
            return "recursive-delete-root"
    if (
        name in PERMS
        and recursive_flag(name, args)
        and any(dangerous_target(a, state.cwd_root, True) for a in positional)
    ):
        return "recursive-perms-root"
    deletes = "-delete" in args or (
        "-exec" in args and any(cmd_name(a) in ("rm", "shred") for a in args)
    )
    find_start_bad = (
        not args or args[0].startswith("-") or dangerous_target(args[0], state.cwd_root, True)
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
    rule = _inline_rule(name, args, state.depth, state.sensitive)
    if rule is None and state.sensitive and _unscannable(words, core, name, args):
        return "unscannable-path"
    return rule


def split_ops(tok: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(tok):
        op = next(o for o in OPS if tok.startswith(o, i))
        out.append(op)
        i += len(op)
    return out


_WORD_BREAK: Final = " \t\n" + PUNCT  # a `#` right after one of these starts a comment


def _scan(command: str, newline: str) -> str:
    """The text bash would run: backslash-newline deleted (NF1); a `#` that starts a word, outside
    quotes, opens a comment that ends at the newline (a backslash does not extend it); a `#` inside
    a word is an ordinary character. Each unquoted newline becomes `newline`. A word-start `#`
    inside backticks, `${`, or a `$(` that sits inside double quotes (the quote count is then
    unreliable), or right after `)` or a backtick, may or may not be a comment in bash, so it
    raises ValueError (the caller fails closed). A plain `(` or `$(` is not ambiguous: its
    comment also ends at the newline. `start` is false inside quotes, so a quoted `#` never opens
    a comment."""
    if "#" not in command and "\n" not in command:
        return command  # nothing to strip, join or convert: the scan would give the same text
    out: list[str] = []
    quote, start, tick, prev, i = "", True, False, "", 0
    stack: list[str] = []  # open `(`, `$(`, `${`; "" for a plain paren, else an ambiguous one
    while i < len(command):
        c = command[i]
        if c == "\\" and command.startswith(("\n", "\r\n"), i + 1):
            i += 2 if command[i + 1] == "\n" else 3
            continue
        if c == "\\" and quote != "'":
            out.append(command[i : i + 2])
            i, start, prev = i + 2, False, command[i + 1 : i + 2]
            continue
        if quote != "'":
            if c == "`":
                tick = not tick
            elif c == ")":
                if stack and stack[-1] != "}":
                    stack.pop()
            elif c == "}":
                if stack and stack[-1] == "}":
                    stack.pop()
            elif c == "(" and (not quote or prev == "$"):
                stack.append(")" if quote else "")
            elif c == "{" and prev == "$":
                stack.append("}")
        if c == "#" and start:
            if tick or any(stack) or prev in (")", "`"):
                raise ValueError("a comment in a nested or ambiguous place")
            end = command.find("\n", i)
            i = len(command) if end < 0 else end
            continue
        if quote:
            quote = "" if c == quote else quote
            out.append(c)
        elif c in "'\"":
            quote = c
            out.append(c)
            start = False
        elif c == "\n":
            out.append(newline)
            start = True
        else:
            out.append(c)
            start = c in _WORD_BREAK
        prev = c
        i += 1
    return "".join(out)


# True while the guard re-runs HEAD's original comment and newline handling (see _check)
_LEGACY: Final[ContextVar[bool]] = ContextVar("guard_legacy", default=False)


def lex(command: str, posix: bool) -> list[str]:
    """Lex text that _lexable already prepared; it does not scan or strip anything itself."""
    lexer = shlex.shlex(command, posix=posix, punctuation_chars=PUNCT)
    if not _LEGACY.get():
        lexer.commenters = ""  # _scan took the real comments out; shlex would cut at any `#`
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


def _opens_subst(segs: list[tuple[str, list[str]]], idx: int) -> bool:
    """Segment idx is the body of a command substitution (`$(`, a backtick, or `X$` then `(`)."""
    sep = segs[idx][0]
    prev = segs[idx - 1][1] if idx > 0 else []
    return sep in ("$(", "`") or (sep == "(" and bool(prev) and prev[-1].endswith("$"))


def _subst_credential(segs: list[tuple[str, list[str]]], idx: int) -> bool:
    """Segment idx opens a command substitution whose outer command is a reader (cat, cp, tar,
    ...) and whose words contain a credential-adjacent token: the file it names is not in the
    text, so refuse rather than guess."""
    sep, prev = segs[idx][0], (segs[idx - 1][1] if idx > 0 else [])
    if not _opens_subst(segs, idx):
        return False
    outer = strip_wrappers(prev)
    if not outer or cmd_name(outer[0]) not in SUBST_READERS:
        return False
    depth = 0
    for j in range(idx, len(segs)):
        s, words = segs[j]
        if j > idx:
            if s == ")" and depth == 0 or (s == "`" and sep == "`"):
                break
            depth += (s in ("$(", "(", "<(")) - (s == ")")
        if any(c in w.casefold() for w in words for c in CRED_WORDS_ANY):
            return True
    return False


def _check_tokens(tokens: list[str], depth: int, sensitive: bool) -> str | None:
    state = _State(depth=depth, sensitive=sensitive)
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
        if (
            sensitive
            and name in ("cd", "pushd")
            and idx + 1 < len(segs)
            and _opens_subst(segs, idx + 1)
        ):
            words = [*words, "$("]  # `cd $(...)`: the target is not literal
        rule = segment_rule(words, state)
        if rule:
            return rule
        if sensitive and _subst_credential(segs, idx):
            return "unscannable-path"
        if core:
            prev_name = name
    return None


def _normalise(command: str) -> str:
    # Bash deletes backslash-newline outright, so `r\<nl>m` is `rm` (NF1), and drops comments.
    if _LEGACY.get():  # HEAD's text: comments stay, shlex cuts the line at the first `#`
        return command.replace("\\\r\n", "").replace("\\\n", "")
    return _scan(command, "\n")


def _lexable(command: str) -> str:
    """The text token_streams lexes: newlines are `;` outside quotes, in one pass from `command`."""
    if _LEGACY.get():
        return _normalise(command).replace("\n", ";")
    return _scan(command, ";")


def _check(command: str, depth: int = 0, sensitive: bool = True) -> str | None:
    if depth == 0:  # one Scan (memo + component budget) per top-level call
        with _sp.call_scope():
            rule = _check_inner(command, depth, sensitive)
            if rule is not None or ("#" not in command and "\n" not in command):
                return rule  # with no `#` and no newline both paths read the same text
            # Union with HEAD's own handling, so nothing HEAD denied can be allowed now.
            token = _LEGACY.set(True)
            try:
                return _check_inner(command, depth, sensitive)
            finally:
                _LEGACY.reset(token)
    return _check_inner(command, depth, sensitive)


def _ansi_char(m: re.Match[str]) -> str:
    e = m.group(1)
    c = e[0]
    try:
        if c in "xuU" and len(e) > 1:
            return chr(int(e[1:], 16))
        if c in "01234567":
            return chr(int(e, 8) & 0xFF)
    except ValueError:
        return "\x00"  # out of range: a control byte makes the checker refuse the command
    if c == "c" and len(e) == 2:
        return chr(ord(e[1]) & 0x1F)
    return ANSI_SIMPLE.get(c, "\\" + e)


def _ansi_c(command: str) -> str:
    """Replace each $'...' string with the single-quoted text bash would produce from it."""
    return ANSI_C_RE.sub(
        lambda m: "'" + ANSI_ESC_RE.sub(_ansi_char, m.group(1)).replace("'", "'\\''") + "'",
        command,
    )


def _check_inner(command: str, depth: int, sensitive: bool) -> str | None:
    rule = _check_text(command, depth, sensitive)
    if rule is None and "$'" in command and len(command) <= MAX_COMMAND_CHARS:
        decoded = _ansi_c(command)  # union: the text as written, and with $'..' decoded
        if decoded != command:
            return _check_text(decoded, depth, sensitive)
    return rule


def _check_text(command: str, depth: int, sensitive: bool) -> str | None:
    if depth > MAX_DEPTH:
        return "nesting-too-deep"
    if len(command) > MAX_COMMAND_CHARS:
        return "too-long"
    if CONTROL_RE.search(command):
        return "unparseable"  # NUL/control bytes: the shell would see something else (fail closed)
    try:
        flat, text = _normalise(command), _lexable(command)
    except ValueError:
        return "unparseable"  # a `#` bash may read as a comment or as text: do not guess
    if fork_bomb(flat):
        return "fork-bomb"
    streams = token_streams(text)
    if not streams:
        return "unparseable"
    for tokens in streams:
        rule = _check_tokens(tokens, depth, sensitive)
        if rule:
            return rule
    return None


def check_rule(command: str, *, sensitive_paths: bool = True) -> str | None:
    """Return the matched rule name, or None. Any internal error fails closed."""
    try:
        return _check(command, 0, sensitive_paths)
    except Exception:  # noqa: BLE001 - fail closed
        return "check-failed"


def command_names(command: str) -> list[str]:
    """Normalised command name of every segment; computed names keep their leading $ or backtick.

    Raises ValueError for a `#` that _scan cannot place; check_command reaches it only after
    check_rule allowed the command, and wraps it in try/except (fail closed)."""
    names = _names(command)
    token = _LEGACY.set(True)  # plus the names HEAD's handling sees, so none can be missed
    try:
        names += [n for n in _names(command) if n not in names]
    finally:
        _LEGACY.reset(token)
    return names


def _names(command: str) -> list[str]:
    streams = token_streams(_lexable(command))
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


def check_command(
    command: str, policy: CommandPolicy = DEFAULT_POLICY, *, sensitive_paths: bool = True
) -> str | None:
    """Return denial text for the model, or None to allow. Denylist always wins."""
    rule = check_rule(command, sensitive_paths=sensitive_paths)
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


def _path_rule(value: Any, scan: _sp.Scan) -> str | None:
    """Rule for a path-key value: a str, or each str of a list/tuple. Memoised per call."""
    for v in (
        [value] if isinstance(value, str) else value if isinstance(value, (list, tuple)) else []
    ):
        if isinstance(v, str):
            if v not in scan.path:
                scan.path[v] = _sp.sensitive_rule(v, resolve=True, max_chars=_sp.PATH_MAX_CHARS)
            if scan.path[v] is not None:
                return scan.path[v]
    return None


def _guard(call: ToolCall, policy: CommandPolicy) -> str | None:
    try:
        with _sp.call_scope() as scan:
            stack: list[tuple[Any, int]] = [(call.arguments, 0)]
            while stack:
                node, depth = stack.pop()
                if depth > MAX_GUARD_DEPTH:
                    return _denial("check-failed")
                if isinstance(node, dict):
                    for key, val in node.items():
                        name = str(key).casefold()
                        if name in COMMAND_ARG_KEYS:
                            denial = _check_value(val, policy)
                            if denial is not None:
                                return denial
                            continue
                        if name in PATH_ARG_KEYS:
                            rule = _path_rule(val, scan)
                            if rule is not None:
                                return _denial(rule)
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
