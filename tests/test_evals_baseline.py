"""C4 proof tests: eval baseline compare and regression buckets (synthetic data only)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from master_finhub.evals.runner import (
    BUCKETS,
    SCHEMA_VERSION,
    CaseResult,
    compare,
    load_baseline,
    main,
)

PASS = Path(__file__).parent.parent / "src/master_finhub/evals/benchmarks/echo_pass.json"
FAIL = Path(__file__).parent / "fixtures/evals/echo_fail.json"
SRC = Path(__file__).parent.parent / "src"


def bench(tmp_path: Path, name: str, outcome: str, case_id: str = "c1") -> str:
    """Write a benchmark that ends in `outcome` (pass / fail / error / timeout)."""
    data: dict[str, Any] = json.loads((FAIL if outcome == "fail" else PASS).read_text())
    data["id"] = case_id
    if outcome == "error":
        data["ground"]["files"] = ["../../etc/passwd"]  # SandboxDenied -> error, not passed
    if outcome == "timeout":
        data["cutoff_s"] = 0
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return str(p)


def baseline(tmp_path: Path, rows: Any, **top: Any) -> str:
    p = tmp_path / "prev.json"
    p.write_text(json.dumps({"results": rows, **top}))
    return str(p)


def row(case_id: str, passed: bool) -> dict[str, Any]:
    return {"case_id": case_id, "passed": passed, "timed_out": False, "error": None}


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, Any]:
    code = main(list(argv))
    out = capsys.readouterr().out
    return code, (json.loads(out) if code != 2 else out)


def result(case_id: str, passed: bool) -> CaseResult:
    return CaseResult(case_id, case_id, passed, 1.0 if passed else 0.0, False, None, 1, 0.0, None)


# --- proof (backlog row C4) -------------------------------------------------------------


def test_proof_flip_pass_to_fail_is_regressed_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, first = run(capsys, bench(tmp_path, "a.json", "pass", "flip"))
    assert code == 0
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(first))  # a real report from this runner is a valid baseline
    code, out = run(capsys, "--baseline", str(prev), bench(tmp_path, "b.json", "fail", "flip"))
    assert code == 3
    assert out["comparison"]["regressed"] == ["flip"]
    assert next(iter(out)) == "schema_version"
    order = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
    assert tuple(out["comparison"]) == order


def test_proof_no_flips_exit_0(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    p = bench(tmp_path, "a.json", "pass", "same")
    _, first = run(capsys, p)
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(first))
    code, out = run(capsys, "--baseline", str(prev), p)
    assert code == 0
    assert out["comparison"]["unchanged"] == ["same"] and out["comparison"]["regressed"] == []


def test_proof_new_case_listed_under_new(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("old", True)])
    code, out = run(
        capsys,
        "--baseline",
        prev,
        bench(tmp_path, "a.json", "pass", "old"),
        bench(tmp_path, "b.json", "pass", "fresh"),
    )
    assert code == 0
    assert out["comparison"]["new"] == ["fresh"]


def test_cli_module_entry_point_exit_3(tmp_path: Path) -> None:
    prev = baseline(tmp_path, [row("flip", True)])
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-m", "master_finhub.evals.runner", "--baseline", prev,
         bench(tmp_path, "b.json", "fail", "flip")],
        capture_output=True, text=True, env=env, check=False, timeout=120,
    )  # fmt: skip
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["comparison"]["regressed"] == ["flip"]


# --- every transition -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("was", "now", "bucket"),
    [
        (True, True, "unchanged"),
        (True, False, "regressed"),
        (False, True, "fixed"),
        (False, False, "still_failing"),
        (None, True, "new"),
        (None, False, "new"),
        (True, None, "removed"),
        (False, None, "removed"),
    ],
)
def test_compare_transition(was: bool | None, now: bool | None, bucket: str) -> None:
    base = {} if was is None else {"x": was}
    results = [] if now is None else [result("x", now)]
    got = compare(base, results)
    assert got == {b: (["x"] if b == bucket else []) for b in BUCKETS}


@pytest.mark.parametrize(
    ("was", "now", "code", "bucket"),
    [
        (True, "pass", 0, "unchanged"),
        (True, "fail", 3, "regressed"),
        (True, "error", 3, "regressed"),
        (True, "timeout", 3, "regressed"),
        (False, "pass", 0, "fixed"),
        (False, "fail", 1, "still_failing"),
        (False, "error", 1, "still_failing"),
        (False, "timeout", 1, "still_failing"),
    ],
)
def test_main_transition_exit_code(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    was: bool,
    now: str,
    code: int,
    bucket: str,
) -> None:
    prev = baseline(tmp_path, [row("c1", was)])
    got, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", now))
    assert got == code
    assert out["comparison"][bucket] == ["c1"]


def test_removed_passing_case_fails_run(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    prev = baseline(tmp_path, [row("c1", True), row("gone", True)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "pass"))
    assert code == 3 and out["comparison"]["removed"] == ["gone"]


def test_removed_failing_case_fails_run(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    prev = baseline(tmp_path, [row("c1", True), row("gone", False)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "pass"))
    assert code == 3 and out["comparison"]["removed"] == ["gone"]


def test_new_failing_case_is_new_and_exit_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    code, out = run(
        capsys,
        "--baseline",
        prev,
        bench(tmp_path, "a.json", "pass"),
        bench(tmp_path, "b.json", "fail", "c2"),
    )
    assert code == 1 and out["comparison"]["new"] == ["c2"]
    assert out["comparison"]["regressed"] == [] and out["comparison"]["removed"] == []


def test_exactly_one_regression_among_many_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    ids = ["a", "b", "c", "d"]
    prev = baseline(tmp_path, [row(i, True) for i in ids])
    files = [bench(tmp_path, f"{i}.json", "fail" if i == "c" else "pass", i) for i in ids]
    code, out = run(capsys, "--baseline", prev, *files)
    assert code == 3 and out["comparison"]["regressed"] == ["c"]
    assert out["comparison"]["unchanged"] == ["a", "b", "d"]


def test_regression_outranks_other_failures(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("a", True), row("b", False)])
    files = [bench(tmp_path, "a.json", "fail", "a"), bench(tmp_path, "b.json", "fail", "b")]
    code, _ = run(capsys, "--baseline", prev, *files)
    assert code == 3


def test_baseline_never_lowers_exit_code(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    f = bench(tmp_path, "a.json", "fail")
    assert run(capsys, f)[0] == 1
    for was in (True, False):
        assert run(capsys, "--baseline", baseline(tmp_path, [row("c1", was)]), f)[0] in (1, 3)


def test_buckets_sorted_and_key_order_fixed() -> None:
    base = {"z": True, "b": True, "m": False}
    results = [result("z", False), result("b", False), result("y", True), result("a", True)]
    got = compare(base, results)
    order = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
    assert BUCKETS == order and tuple(got) == order
    assert got["regressed"] == ["b", "z"] and got["new"] == ["a", "y"]
    assert got["removed"] == ["m"]
    many = [f"c{i:02d}" for i in range(20)]  # 20 ids: a set never iterates sorted by luck
    assert compare({}, [result(c, True) for c in reversed(many)])["new"] == many


def test_report_has_schema_version_and_no_comparison_without_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = run(capsys, str(PASS))
    assert code == 0 and out["schema_version"] == SCHEMA_VERSION == 1
    assert next(iter(out)) == "schema_version"
    assert "comparison" not in out


def test_old_report_without_schema_version_is_accepted(tmp_path: Path) -> None:
    assert load_baseline(baseline(tmp_path, [row("a", True)])) == {"a": True}
    assert load_baseline(baseline(tmp_path, [row("a", False)], schema_version=1)) == {"a": False}


def test_extra_fields_are_ignored(tmp_path: Path) -> None:
    p = tmp_path / "prev.json"
    p.write_text('{"results": [{"case_id": "a", "passed": true, "score": NaN}], "x": 1}')
    assert load_baseline(p) == {"a": True}


# --- unusable baseline fails closed (exit 2, suite never reported) -----------------------

BAD_ROWS: list[Any] = [
    [],
    {},
    None,
    "x",
    ["x"],
    [None],
    [{"passed": True}],
    [{"case_id": "", "passed": True}],
    [{"case_id": 5, "passed": True}],
    [{"case_id": None, "passed": True}],
    [{"case_id": "a"}],
    [{"case_id": "a", "passed": None}],
    [{"case_id": "a", "passed": "true"}],
    [{"case_id": "a", "passed": 1}],
    [{"case_id": "a", "passed": 0}],
    [row("a", True), row("a", True)],
    [row("a", True), row("a", False)],
]


@pytest.mark.parametrize("rows", BAD_ROWS)
def test_bad_rows_exit_2(capsys: pytest.CaptureFixture[str], tmp_path: Path, rows: Any) -> None:
    code, out = run(capsys, "--baseline", baseline(tmp_path, rows), str(PASS))
    assert code == 2 and out.startswith("Baseline ")
    with pytest.raises(ValueError, match="Baseline"):
        load_baseline(tmp_path / "prev.json")


@pytest.mark.parametrize("version", [2, 0, True, "1", None, [1]])
def test_other_schema_version_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, version: Any
) -> None:
    prev = baseline(tmp_path, [row("c1", True)], schema_version=version)
    code, out = run(capsys, "--baseline", prev, str(PASS))
    assert code == 2 and "schema_version" in out


@pytest.mark.parametrize(
    "content", [b"", b"{", b"{}", b"[]", b"null", b'"x"', b"42", b"\xff\xfe\x00", b"NaN"]
)
def test_unreadable_baseline_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, content: bytes
) -> None:
    p = tmp_path / "prev.json"
    p.write_bytes(content)
    code, out = run(capsys, "--baseline", str(p), str(PASS))
    assert code == 2 and out.startswith("Baseline ")
    with pytest.raises(ValueError, match="Baseline"):
        load_baseline(p)


@pytest.mark.parametrize("which", ["missing", "directory", "empty-string"])
def test_missing_baseline_path_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, which: str
) -> None:
    path = {"missing": str(tmp_path / "nope.json"), "directory": str(tmp_path), "empty-string": ""}
    code, out = run(capsys, "--baseline", path[which], str(PASS))
    assert code == 2 and out.startswith("Baseline ")


def test_bad_baseline_checked_before_suite_runs(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr("master_finhub.evals.runner.run_suite", lambda *a, **k: calls.append(a))
    code, _ = run(capsys, "--baseline", str(tmp_path / "nope.json"), str(PASS))
    assert code == 2 and calls == []


DEEP = "[" * 100_000 + "]" * 100_000


@pytest.mark.parametrize(
    "text",
    [
        DEEP,
        '{"results": [{"case_id": "c1", "passed": true, "x": ' + DEEP + "}]}",
    ],
    ids=["root", "ignored-field"],
)
def test_deeply_nested_baseline_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str
) -> None:
    p = tmp_path / "prev.json"
    p.write_text(text)
    code, out = run(capsys, "--baseline", str(p), str(PASS))
    assert code == 2 and "cannot read (RecursionError)" in out


@pytest.mark.parametrize(
    "text",
    [
        (
            '{"results": [{"case_id": "c1", "passed": true}, {"case_id": "gone", "passed": true}],'
            ' "results": [{"case_id": "c1", "passed": true}]}'
        ),
        '{"results": [{"case_id": "gone", "case_id": "c1", "passed": true}]}',
        '{"results": [{"case_id": "c1", "passed": true, "x": {"k": 1, "k": 2}}]}',
    ],
    ids=["results", "case_id", "nested"],
)
def test_duplicate_json_keys_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str
) -> None:
    p = tmp_path / "prev.json"
    p.write_text(text)
    code, out = run(capsys, "--baseline", str(p), bench(tmp_path, "a.json", "pass"))
    assert code == 2 and "cannot read (ValueError)" in out


def test_repeated_baseline_flag_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first.json"
    first.write_text(json.dumps({"results": [row("c1", True), row("gone", True)]}))
    second = baseline(tmp_path, [row("c1", True)])
    code, out = run(
        capsys, "--baseline", str(first), "--baseline", second, bench(tmp_path, "a.json", "pass")
    )
    assert code == 2 and "more than once" in out
    calls: list[Any] = []
    monkeypatch.setattr("master_finhub.evals.runner.run_suite", lambda *a, **k: calls.append(a))
    assert run(capsys, "--baseline", second, "--baseline", second, str(PASS))[0] == 2
    assert calls == []


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs os.mkfifo")
def test_fifo_baseline_exit_2_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "prev.json"
    os.mkfifo(fifo)
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-m", "master_finhub.evals.runner", "--baseline", str(fifo), str(PASS)],
        capture_output=True, text=True, env=env, check=False, timeout=60,
    )  # fmt: skip
    assert proc.returncode == 2 and "not a regular file" in proc.stdout


def test_symlink_to_regular_baseline_is_accepted(tmp_path: Path) -> None:
    link = tmp_path / "link.json"
    link.symlink_to(baseline(tmp_path, [row("a", True)]))
    assert load_baseline(link) == {"a": True}


@pytest.mark.parametrize("target", ["load_baseline", "compare"])
def test_unexpected_baseline_exception_exit_2(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(f"master_finhub.evals.runner.{target}", boom)
    prev = baseline(tmp_path, [row("c1", True)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "pass"))
    assert code == 2 and out.startswith("Baseline unusable (RuntimeError)")


class BadStdout:
    """A stdout whose write or flush raises, like a full disk or a closed pipe."""

    def __init__(self, exc: BaseException, on: str) -> None:
        self.exc, self.on = exc, on

    def write(self, text: str) -> int:
        if self.on == "write":
            raise self.exc
        return len(text)

    def flush(self) -> None:
        if self.on == "flush":
            raise self.exc


STDOUT_FAULTS = [
    (OSError(28, "No space left on device"), "write"),
    (BrokenPipeError(32, "Broken pipe"), "write"),
    (OSError(28, "No space left on device"), "flush"),
    (BrokenPipeError(32, "Broken pipe"), "flush"),
]
FAULT_IDS = ["oserror-write", "brokenpipe-write", "oserror-flush", "brokenpipe-flush"]


@pytest.mark.parametrize(("exc", "on"), STDOUT_FAULTS, ids=FAULT_IDS)
def test_lost_report_with_baseline_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: OSError, on: str
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "fail")  # a detected regression: 3 when stdout works
    monkeypatch.setattr(sys, "stdout", BadStdout(exc, on))
    assert main(["--baseline", prev, f]) == 2


@pytest.mark.parametrize(("exc", "on"), STDOUT_FAULTS, ids=FAULT_IDS)
def test_lost_report_without_baseline_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: OSError, on: str
) -> None:
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(sys, "stdout", BadStdout(exc, on))
    if on == "write":
        with pytest.raises(type(exc)):
            main([f])
    else:
        assert main([f]) == 1  # no flush on this path, as before C4


def test_closed_stdout_with_baseline_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(sys, "stdout", None)  # what Python sets when fd 1 is closed (`>&-`)
    assert main(["--baseline", prev, f]) == 2
    assert main([f]) == 1  # without --baseline: unchanged, print is a no-op


def test_clean_flagged_run_with_lost_report_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "pass")  # nothing regressed: 0 when stdout works
    monkeypatch.setattr(sys, "stdout", BadStdout(OSError(28, "No space left on device"), "write"))
    assert main(["--baseline", prev, f]) == 2  # fail closed


def test_keyboard_interrupt_during_report_write_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(sys, "stdout", BadStdout(KeyboardInterrupt(), "write"))
    with pytest.raises(KeyboardInterrupt):
        main(["--baseline", prev, f])


def test_unencodable_case_id_in_bad_baseline_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [{"case_id": "\ud800x", "passed": 1}])  # lone surrogate
    code, out = run(capsys, "--baseline", prev, str(PASS))
    assert code == 2 and "\\ud800x" in out


def test_non_ascii_case_id_in_bad_baseline_ascii_stdout_exit_2(tmp_path: Path) -> None:
    prev = baseline(tmp_path, [{"case_id": "caf\u00e9", "passed": 1}])
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "ascii"}
    proc = subprocess.run(
        [sys.executable, "-m", "master_finhub.evals.runner", "--baseline", prev, str(PASS)],
        capture_output=True, text=True, env=env, check=False, timeout=120,
    )  # fmt: skip
    assert proc.returncode == 2 and "caf\\xe9" in proc.stdout


def test_surrogate_case_id_regression_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("\ud800x", True)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "fail", "\ud800x"))
    assert code == 3 and out["comparison"]["regressed"] == ["\ud800x"]  # pins ensure_ascii


def test_removed_ids_sorted() -> None:
    base = {"r3": True, "r2": False, "r1": True}  # given in reverse order
    assert compare(base, [result("c1", True)])["removed"] == ["r1", "r2", "r3"]


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
@pytest.mark.parametrize("which", ["regression", "bad-baseline", "bad-benchmark"])
def test_full_disk_buffered_stdout_exit_2(tmp_path: Path, which: str) -> None:
    good = baseline(tmp_path, [row("c1", True)])
    bad = str(tmp_path / "bad.json")
    Path(bad).write_text(json.dumps({"results": [{"case_id": "c1", "passed": 1}]}))
    broken = str(tmp_path / "broken.json")
    Path(broken).write_text("{")
    argv = {
        "regression": ["--baseline", good, bench(tmp_path, "a.json", "fail")],
        "bad-baseline": ["--baseline", bad, str(PASS)],
        "bad-benchmark": ["--baseline", good, broken],
    }[which]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}  # CPython default
    env["PYTHONPATH"] = str(SRC)
    codes = []
    for args in (argv, argv[2:]):  # with --baseline, then the same run without it
        with open("/dev/full", "w") as full:
            proc = subprocess.run(
                [sys.executable, "-m", "master_finhub.evals.runner", *args],
                stdout=full, stderr=subprocess.PIPE, env=env, check=False, timeout=120,
            )  # fmt: skip
        codes.append(proc.returncode)
    assert codes == [2, 120]  # no flag: CPython's failed exit-time flush, as before C4


def test_non_oserror_stdout_with_baseline_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"results": [{"case_id": "c1", "passed": 1}]}))
    f = bench(tmp_path, "a.json", "fail")
    for argv in (["--baseline", prev, f], ["--baseline", str(bad), str(PASS)]):
        monkeypatch.setattr(sys, "stdout", BadStdout(ValueError("I/O on closed file"), "write"))
        assert main(argv) == 2  # the report guard, then the unusable-baseline message


def test_stdout_lost_without_devnull_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"results": [{"case_id": "c1", "passed": 1}]}))
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(os, "devnull", str(tmp_path / "missing" / "null"))  # bare chroot
    for argv in (["--baseline", prev, f], ["--baseline", str(bad), str(PASS)]):
        monkeypatch.setattr(sys, "stdout", None)  # fd 1 closed
        assert main(argv) == 2


def test_keyboard_interrupt_during_baseline_message_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"results": [{"case_id": "c1", "passed": 1}]}))
    monkeypatch.setattr(sys, "stdout", BadStdout(KeyboardInterrupt(), "write"))
    with pytest.raises(KeyboardInterrupt):  # not swallowed into exit 2
        main(["--baseline", str(bad), str(PASS)])


# --- QA pins: the exit-3 gate with mixed buckets, devnull faults, argv and encoding ------------

MIXED = {  # id: (baseline {case: passed}, run {case: passed}, expected buckets that matter)
    "removed+still_failing": (
        {"gone": True, "s": False}, {"s": False},
        {"removed": ["gone"], "still_failing": ["s"]},
    ),
    "removed+new": ({"old": True}, {"n": True}, {"removed": ["old"], "new": ["n"]}),
    "removed+fixed": (
        {"gone": True, "f": False}, {"f": True}, {"removed": ["gone"], "fixed": ["f"]},
    ),
    "regressed+fixed": (
        {"r": True, "f": False}, {"r": False, "f": True}, {"regressed": ["r"], "fixed": ["f"]},
    ),
    "regressed+new": (
        {"r": True}, {"r": False, "n": True}, {"regressed": ["r"], "new": ["n"]},
    ),
    "regressed+still_failing": (
        {"r": True, "s": False}, {"r": False, "s": False},
        {"regressed": ["r"], "still_failing": ["s"]},
    ),
    "all-buckets": (
        {"r": True, "g": True, "f": False, "s": False, "u": True},
        {"r": False, "f": True, "s": False, "u": True, "n": True},
        {"regressed": ["r"], "removed": ["g"], "fixed": ["f"], "still_failing": ["s"],
         "unchanged": ["u"], "new": ["n"]},
    ),
}  # fmt: skip


@pytest.mark.parametrize("key", list(MIXED))
def test_regressed_or_removed_beside_other_buckets_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, key: str
) -> None:
    was, now, want = MIXED[key]
    prev = baseline(tmp_path, [row(c, p) for c, p in was.items()])
    files = [bench(tmp_path, f"{c}.json", "pass" if p else "fail", c) for c, p in now.items()]
    code, out = run(capsys, "--baseline", prev, *files)
    assert code == 3
    for bucket, ids in want.items():
        assert out["comparison"][bucket] == ids


def _regression_args(tmp_path: Path) -> list[str]:
    prev = baseline(tmp_path, [row("c1", True)])
    return ["--baseline", prev, bench(tmp_path, "a.json", "fail")]  # 3 when stdout works


def test_stdout_lost_devnull_is_a_directory_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv = _regression_args(tmp_path)
    monkeypatch.setattr(os, "devnull", str(tmp_path))  # open(..., "w") -> IsADirectoryError
    monkeypatch.setattr(sys, "stdout", None)
    assert main(argv) == 2


def test_stdout_lost_devnull_open_fails_emfile_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    argv = _regression_args(tmp_path)
    nd = str(tmp_path / "nd")
    real_open = builtins.open

    def fake_open(file: Any, *a: Any, **k: Any) -> Any:
        if file == nd:
            raise OSError(24, "Too many open files", nd)
        return real_open(file, *a, **k)

    monkeypatch.setattr(os, "devnull", nd)
    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(sys, "stdout", None)
    assert main(argv) == 2


@pytest.mark.parametrize("flag", [False, True], ids=["no-flag", "baseline"])
def test_no_benchmark_paths_exit_2(tmp_path: Path, flag: bool) -> None:
    argv = ["--baseline", baseline(tmp_path, [row("c1", True)])] if flag else []
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2  # argparse usage error, as before C4


@pytest.mark.parametrize("n", [3, 4, 6])
def test_several_failures_without_regression_exit_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, n: int
) -> None:
    files = [bench(tmp_path, f"f{i}.json", "fail", f"f{i}") for i in range(n)]
    code, out = run(capsys, *files)
    assert code == 1 and out["failed"] == n  # not the count, not count % 3, not 3


def test_baseline_with_invalid_utf8_inside_string_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    p = tmp_path / "prev.json"
    p.write_bytes(b'{"results": [{"case_id": "\xe9", "passed": true}]}')  # latin-1 e-acute
    code, out = run(capsys, "--baseline", str(p), str(PASS))
    assert code == 2 and "cannot read (UnicodeDecodeError)" in out
