"""Verification gates as data: a declared list of command gates, run as argv; a shell only when
the gate declares it and the caller allows it.

Policy adapted (MIT, own code) from references/openharness/src/openharness/autopilot/service.py:155
(string or mapping entry, argv unless the entry opts in, a policy error is never executed), the
metacharacter set at :136 and the spawn and status mapping at :2094. Own code: a strict JSON
schema, every gate checked before anything is spawned, the workspace fence for cwd, the command
guard, a scrubbed env, per-gate and total time bounds, and redacted output tails.

What is and is not controlled. This module starts /bin/sh itself only for a gate that declares
``"shell": true`` AND is run with ``--allow-shell``; the string form never turns into a shell by
itself. In a non-shell gate a shell as the executable (sh, bash, dash, ...), or a symlink to one
reached by an absolute path, a cwd-relative path or PATH (resolved from the gate's folder), su,
watch, or a wrapper handed a shell (env sh, xargs sh, find -exec sh, ...) is refused; so is any
executable under /proc or /dev, which the runner and the child resolve differently. That is a
speed bump that catches common accidents, NOT a sandbox: each audit round found another
path-resolution mismatch of the same class, and others may exist. NOT detected: wrappers not on
the list, wrapper chains, interpreters (``python -c``, ``perl -e``, ``awk``, ``node -e``), make,
scripts, a copy or hard link of a shell, a link made by an earlier gate, programs that start a
shell without naming one (flock -c, script -c, runuser -c, parallel, sudo -s, env -S), an
executable earlier on PATH that exec skips (no shebang, a missing interpreter) before a same-name
shell link, and shells outside the 14 listed names (ksh93, elvish, nu, xonsh, versioned names).

Exit codes of ``python -m master_finhub.evals.gates``: 0 every gate passed; 1 a gate failed, timed
out, could not start or was not run; 2 the gate file is unusable or a gate broke the policy
(nothing was spawned); 143 (SIGTERM), 129 (SIGHUP) or a SIGINT death: interrupted, no report, the
running gate's process group killed (SIGKILL of the runner itself cannot be handled). Gates are
trusted operator data: this fences accidents, it is not a sandbox.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import signal
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal

from master_finhub.evals.runner import _stdout_lost
from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.stream import collect, scrubbed_env, stream_process
from master_finhub.sandbox.workspace import SandboxDenied, Workspace
from master_finhub.tools.safety import guard_tool_call
from master_finhub.tools.secret_scan import redact_secrets

SCHEMA_VERSION: Final = 1
MAX_GATES: Final = 50
MAX_FILE_BYTES: Final = 262_144
MAX_TEXT_CHARS: Final = 4096  # one command string, or one argv item
MAX_ARGV_ITEMS: Final = 256
DEFAULT_TIMEOUT_S: Final = 300.0
MAX_TIMEOUT_S: Final = 1800.0
MAX_TOTAL_S: Final = 3600.0
TAIL_CHARS: Final = 4000  # per stream in the report (stream.collect keeps 64,000 before this)
SHELL_METACHARS: Final = frozenset(";&|`$<>\n\r")
SHELL_PATH: Final = "/bin/sh"
OPAQUE_ROOTS: Final = ("/proc", "/dev")
HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)
# Shell names (lower case, ".exe" stripped) refused as the executable of a non-shell gate.
SHELL_NAMES: Final = frozenset(
    {
        "sh",
        "bash",
        "dash",
        "ash",
        "ksh",
        "mksh",
        "pdksh",
        "posh",
        "yash",
        "zsh",
        "fish",
        "csh",
        "tcsh",
        "rbash",
    }
)
# One-hop wrappers refused when ANY later argument names a shell; and programs that run a shell
# by design, refused outright. Not exhaustive: a wrapper chain cannot be closed by a tripwire.
WRAPPERS: Final = frozenset(
    {"env", "xargs", "busybox", "toybox", "nohup", "exec", "command", "builtin", "sudo", "doas", "timeout",
     "nice", "ionice", "setsid", "stdbuf", "chroot", "find", "flock", "unshare", "strace", "time", "chrt",
     "taskset", "script", "runuser", "setpriv", "nsenter", "ssh", "parallel"}
)  # fmt: skip
SHELL_RUNNERS: Final = frozenset({"su", "watch"})
ROOT_KEYS: Final = frozenset({"schema_version", "gates"})
GATE_KEYS: Final = frozenset({"id", "command", "argv", "shell", "timeout_s", "cwd"})
Status = Literal["pass", "fail", "timeout", "error", "policy-error", "not-run"]


class GateFileError(ValueError):
    """The gate file is unusable. The message never echoes the file's contents."""


@dataclass(frozen=True)
class Gate:
    id: str
    command: str | None
    argv: tuple[str, ...] | None
    shell: bool
    timeout_s: float
    cwd: str


@dataclass(frozen=True)
class GateResult:
    id: str
    status: Status
    exit_code: int | None
    duration_s: float
    stdout_tail: str
    stderr_tail: str
    truncated: bool
    message: str


@dataclass(frozen=True)
class GateReport:
    gates: tuple[GateResult, ...]
    passed: int
    failed: int
    total: int
    ok: bool


@dataclass(frozen=True)
class Plan:
    argv: tuple[str, ...]
    cwd: Path


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = dict(pairs)
    if len(out) != len(pairs):
        raise ValueError("duplicate JSON key")
    return out


def _bad(why: str) -> GateFileError:
    return GateFileError(f"Gate file: {why}. Fix the gate file and retry.")


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 64
        and value.isascii()
        and value[0].isalnum()
        and all(c.isalnum() or c in "._-" for c in value)
    )


def _timeout(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        seconds = float(value)
    except OverflowError:
        return None
    return seconds if 0 < seconds <= MAX_TIMEOUT_S else None  # False for NaN, inf, 0 and below


def _parse_gate(n: int, entry: Any) -> Gate:
    if not isinstance(entry, dict):
        raise _bad(f"gate {n} must be an object")
    if not set(entry) <= GATE_KEYS:
        raise _bad(f"gate {n} has an unknown key")
    if not _valid_id(entry.get("id")):
        raise _bad(f"gate {n}: id must be 1-64 ASCII letters, digits, '.', '_' or '-'")
    command, argv = entry.get("command"), entry.get("argv")
    if (command is None) == (argv is None):
        raise _bad(f"gate {n} needs exactly one of command and argv")
    if command is not None and not isinstance(command, str):
        raise _bad(f"gate {n}: command must be a string")
    if argv is not None and not (isinstance(argv, list) and all(isinstance(a, str) for a in argv)):
        raise _bad(f"gate {n}: argv must be a list of strings")
    shell = entry.get("shell", False)
    if not isinstance(shell, bool):
        raise _bad(f"gate {n}: shell must be true or false")
    if shell and command is None:
        raise _bad(f"gate {n}: shell needs command, not argv")
    timeout = _timeout(entry["timeout_s"]) if "timeout_s" in entry else DEFAULT_TIMEOUT_S
    if timeout is None:
        raise _bad(f"gate {n}: timeout_s must be a number above 0 and at most {MAX_TIMEOUT_S:g}")
    cwd = entry.get("cwd", ".")
    if not isinstance(cwd, str):
        raise _bad(f"gate {n}: cwd must be a string")
    return Gate(entry["id"], command, None if argv is None else tuple(argv), shell, timeout, cwd)


def load_gate_file(path: str | os.PathLike[str]) -> tuple[Gate, ...]:
    """Strict load: anything unusable raises GateFileError (fail closed, never an empty list)."""
    if not os.path.isfile(path):  # follows symlinks; a FIFO or device would block on read
        raise _bad("not a regular file")
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_FILE_BYTES + 1)
    except OSError:
        raise _bad("cannot be read") from None
    if len(raw) > MAX_FILE_BYTES:
        raise _bad(f"larger than {MAX_FILE_BYTES} bytes")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError):  # includes bad UTF-8 and duplicate keys
        raise _bad("not UTF-8 JSON (duplicate keys and very deep nesting are refused)") from None
    if not isinstance(data, dict) or not set(data) <= ROOT_KEYS:
        raise _bad("the root must be an object with only schema_version and gates")
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:  # not a bool, not 1.0
        raise _bad(f"schema_version must be {SCHEMA_VERSION}")
    rows = data.get("gates")
    if not isinstance(rows, list) or not rows:
        raise _bad('"gates" must be a non-empty list')
    if len(rows) > MAX_GATES:
        raise _bad(f"more than {MAX_GATES} gates")
    gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))
    if len({g.id for g in gates}) != len(gates):
        raise _bad("duplicate gate id")
    return gates


def _argv_from_string(raw: str) -> tuple[str, ...] | str:
    """A command string -> argv, or the reason it is refused. Metacharacters are scanned on the
    raw text, quotes included, before shlex sees it (conservative, like the reference)."""
    text = raw.strip()
    if len(text) > MAX_TEXT_CHARS:
        return "command is too long"
    if any(ch in SHELL_METACHARS for ch in text):
        return "shell metacharacters; use argv, or declare shell: true and pass --allow-shell"
    try:
        return tuple(shlex.split(text))
    except ValueError:
        return "could not tokenize the command (unbalanced quote or trailing backslash)"


def _argv_refusal(argv: Sequence[str]) -> str | None:
    if not argv:
        return "empty command"
    if len(argv) > MAX_ARGV_ITEMS or any(len(a) > MAX_TEXT_CHARS for a in argv):
        return "argv is too long"
    if any("\x00" in a for a in argv):
        return "argument contains a NUL byte"
    try:
        for a in argv:
            a.encode("utf-8")
    except UnicodeEncodeError:
        return "argument is not valid text"
    if not argv[0]:
        return "empty executable"
    if argv[0].startswith("-"):
        return "the executable starts with '-'"
    if "=" in argv[0]:
        return "the executable contains '=' (environment prefixes need shell: true)"
    return None


def _base(word: str) -> str:
    name = word.rsplit("/", 1)[-1].lower()
    return name.removesuffix(".exe")


class _Opaque(Exception):
    """The executable's path goes through /proc or /dev, where the runner and the child see
    different things (/proc/self/cwd, /proc/self/fd/N, /dev/fd/N, /dev/stdin): refused outright."""


def _opaque(path: str) -> bool:
    p = "/" + os.path.normpath(path).lstrip("/")  # normpath keeps a leading "//"
    return any(p == root or p.startswith(root + "/") for root in OPAQUE_ROOTS)


def _link_into_opaque(path: str, hops: int = 0) -> bool:
    """True when a symlink met on the way (any component, text read with readlink, not followed
    through /proc) leads into /proc or /dev. Fails closed on a loop or more than 40 hops."""
    if hops > 40:
        return True
    p = os.path.normpath(path)
    parts, cur = p.split("/"), "/"
    for i, part in enumerate(parts):
        if not part:
            continue
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            target = os.path.join(os.path.dirname(cur), os.readlink(cur))
            rest = "/".join(parts[i + 1 :])
            nxt = os.path.join(target, rest) if rest else target
            return _opaque(nxt) or _link_into_opaque(nxt, hops + 1)
    return False


def _checked_real(path: str) -> str:
    """realpath of ``path`` after the /proc and /dev checks, run BEFORE the resolution: realpath
    inside the runner would expand /proc/self to the runner's own folders."""
    if _opaque(path) or _link_into_opaque(path):
        raise _Opaque
    real = os.path.realpath(path)
    if _opaque(real):
        raise _Opaque
    return real


def _resolve(word: str, cwd: Path) -> str | None:
    """Where the child's exec will find ``word``. The child starts in ``cwd`` (the gate's folder,
    not the runner's), so a path with a "/" is joined onto it, and a bare name is searched along
    PATH the way Popen does: first entry holding an executable file, an empty or relative entry
    meaning ``cwd``. A path, a link on the way or a PATH entry under /proc or /dev raises _Opaque.
    Not looked at: a file created or swapped after this check (an earlier gate), and an earlier
    PATH file that exec skips for another reason (no shebang, a missing interpreter)."""
    if "/" in word:
        return _checked_real(os.path.join(cwd, word))
    for entry in os.get_exec_path():
        base = os.path.join(cwd, entry)
        if _opaque(base) or _link_into_opaque(base):
            raise _Opaque
        candidate = os.path.join(base, word)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return _checked_real(candidate)
    return None


def _shell_refusal(argv: Sequence[str], cwd: Path) -> str | None:
    """Non-shell gates only. Refuse a shell as the executable (by its name, and by what a path or a
    PATH lookup resolves to FROM THE GATE'S cwd, so a symlink called anything that points at a
    shell is caught), a shell-running program, and a one-hop wrapper handed a shell name."""
    first = _base(argv[0])
    names = {first}
    try:
        found = _resolve(argv[0], cwd)
        if found:
            names.add(_base(found))
    except _Opaque:
        return "the executable is under /proc or /dev, which the runner and the child resolve differently"
    except (OSError, ValueError):
        pass
    if names & SHELL_NAMES or first in SHELL_RUNNERS:
        return "the executable is a shell; declare shell: true and pass --allow-shell"
    if first in WRAPPERS and any(_base(a) in SHELL_NAMES for a in argv[1:]):
        return "a wrapper is given a shell; declare shell: true and pass --allow-shell"
    return None


def plan_gate(gate: Gate, ws: Workspace, allow_shell: bool) -> Plan | str:
    """The spawn plan, or the policy-error reason. Nothing here spawns."""
    try:
        if gate.shell:
            raw = gate.command or ""
            if not raw.strip():
                return "empty command"
            if len(raw) > MAX_TEXT_CHARS:
                return "command is too long"
            if not allow_shell:
                return "shell gate refused: pass --allow-shell"
            if os.name != "posix":
                return "shell gates need a POSIX shell"
            argv: tuple[str, ...] = (SHELL_PATH, "-c", raw)
            line = raw
        else:
            parsed = _argv_from_string(gate.command) if gate.command is not None else gate.argv
            if isinstance(parsed, str):
                return parsed
            argv = parsed or ()
            line = shlex.join(argv)
        refusal = _argv_refusal(argv)
        if refusal is not None:
            return refusal
        try:
            cwd = ws.check_read(gate.cwd)
        except SandboxDenied as exc:
            return f"cwd refused ({exc.reason})"
        if not cwd.is_dir():
            return "cwd is not a folder"
        if not gate.shell:  # needs the gate's cwd: the child resolves argv[0] from there
            refusal = _shell_refusal(argv, cwd)
            if refusal is not None:
                return refusal
        # the same guard the agent loop uses: command rules plus the sensitive-path rule on cwd
        denial = guard_tool_call(ToolCall("gate", "gate", {"command": line, "cwd": str(cwd)}))
        if denial is not None:
            return denial
        return Plan(argv, cwd)
    except Exception:  # noqa: BLE001 - fail closed: an unexpected error is a refusal
        return "policy check failed"


def _tail(text: str) -> tuple[str, bool]:
    cleaned = redact_secrets(text)[0]
    return cleaned[-TAIL_CHARS:], len(cleaned) > TAIL_CHARS


def _run_one(gate: Gate, plan: Plan, timeout_s: float) -> GateResult:
    start = time.monotonic()

    def done(
        status: Status,
        code: int | None,
        message: str,
        out: str = "",
        err: str = "",
        truncated: bool = False,
    ) -> GateResult:
        elapsed = round(time.monotonic() - start, 3)
        return GateResult(gate.id, status, code, elapsed, out, err, truncated, message)

    try:
        res = collect(
            stream_process(plan.argv, env=scrubbed_env(), timeout_s=timeout_s, cwd=str(plan.cwd))
        )
    except FileNotFoundError:
        return done("error", None, "executable or folder not found")
    except PermissionError:
        return done("error", None, "not executable or not permitted")
    except Exception as exc:  # noqa: BLE001 - a spawn failure is an error, never a pass
        return done("error", None, f"could not start ({type(exc).__name__})")
    out, cut_out = _tail(res.stdout)
    err, cut_err = _tail(res.stderr)
    cut = res.truncated or cut_out or cut_err
    if res.timed_out:
        return done("timeout", None, f"timed out after {timeout_s:g}s", out, err, cut)
    if res.exit_code is None:
        return done("error", None, "no exit status", out, err, cut)
    if res.exit_code == 0:
        return done("pass", 0, "", out, err, cut)
    why = (
        f"killed by signal {-res.exit_code}" if res.exit_code < 0 else f"exit code {res.exit_code}"
    )
    return done("fail", res.exit_code, why, out, err, cut)


def _skipped(gate_id: str, status: Status, message: str) -> GateResult:
    return GateResult(gate_id, status, None, 0.0, "", "", False, message)


def _report(results: Sequence[GateResult]) -> GateReport:
    passed = sum(r.status == "pass" for r in results)
    total = len(results)
    return GateReport(tuple(results), passed, total - passed, total, total > 0 and passed == total)


def run_gates(
    gates: Sequence[Gate],
    ws: Workspace,
    *,
    allow_shell: bool = False,
    total_s: float = MAX_TOTAL_S,
) -> GateReport:
    """Check every gate first; spawn nothing if any is refused. Then run all, in order."""
    if not gates:
        raise ValueError("no gates to run")
    plans = [plan_gate(g, ws, allow_shell) for g in gates]
    ready = [p for p in plans if isinstance(p, Plan)]
    if len(ready) != len(plans):  # nothing is spawned when any gate is refused
        return _report(
            [
                (
                    _skipped(g.id, "policy-error", p)
                    if isinstance(p, str)
                    else _skipped(g.id, "not-run", "another gate was refused")
                )
                for g, p in zip(gates, plans, strict=True)
            ]
        )
    deadline = time.monotonic() + total_s
    results: list[GateResult] = []
    for g, p in zip(gates, ready, strict=True):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append(_skipped(g.id, "not-run", "time budget used up"))
        else:
            results.append(_run_one(g, p, min(g.timeout_s, remaining)))
    return _report(results)


def exit_code(report: GateReport) -> int:
    if report.ok:
        return 0
    return 2 if any(r.status == "policy-error" for r in report.gates) else 1


def _emit(text: str) -> bool:
    try:
        print(text)
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 - stdout lost: the caller still exits 2, never 0 or 1
        return False
    return True


def _raise_exit(signum: int, _frame: object) -> None:
    raise SystemExit(128 + signum)


@contextlib.contextmanager
def _signals_raise() -> Iterator[None]:
    """SIGTERM (a CI cancel) and SIGHUP (a closed terminal) unwind like Ctrl-C, so stream_process
    kills the gate's process group instead of leaving it running. SIGKILL cannot be handled: that
    one still orphans a gate."""
    saved: list[tuple[int, Any]] = []
    try:
        for sig in HANDLED_SIGNALS:
            saved.append((sig, signal.signal(sig, _raise_exit)))
    except ValueError:  # not the main thread: leave the handlers alone
        pass
    try:
        yield
    finally:
        for old_sig, previous in saved:  # None = installed from C: SIG_DFL is the closest restore
            signal.signal(old_sig, signal.SIG_DFL if previous is None else previous)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="master_finhub.evals.gates")
    ap.add_argument("gate_file")
    ap.add_argument("--root", default=None, help="workspace fence for gate cwd (default: cwd)")
    ap.add_argument(
        "--allow-shell",
        action="store_true",
        help="honour shell: true gates (a convention for the string form; the shell refusal is a speed bump with known gaps, not a sandbox: see the module docstring)",
    )
    args = ap.parse_args(argv)
    try:
        with _signals_raise():
            gates = load_gate_file(args.gate_file)
            ws = Workspace(args.root if args.root is not None else os.getcwd())
            report = run_gates(gates, ws, allow_shell=args.allow_shell)
    except (GateFileError, FileNotFoundError, NotADirectoryError) as exc:
        return 2 if _emit(str(exc)) else _stdout_lost()
    except Exception as exc:  # noqa: BLE001 - any other failure is exit 2, never 0 or 1
        return 2 if _emit(f"Gates could not run ({type(exc).__name__}).") else _stdout_lost()
    out = {"schema_version": SCHEMA_VERSION, "kind": "gates", **asdict(report)}
    code = exit_code(report)
    return code if _emit(json.dumps(out, indent=2)) else _stdout_lost()


if __name__ == "__main__":
    raise SystemExit(main())
