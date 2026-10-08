"""Proof for OR-D2: scripts/mutant_gate.py and the mutation rules M1-M8 (quality-gates.md 3-4).

A mutant counts as caught only when the test written for it fails at its own assertion, between a
passing run before and a passing run after. These tests feed the script hand-made reports for every
state, then real pytest runs for the shapes pytest writes (assertion, DID NOT RAISE, collection
error, import error, NameError, timeout), then pin the prose. The rule is adapted from
references/openrig/packages/test-system/ci/result.mjs:33-34 and :50-65 (Apache-2.0) and
references/openrig/docs/as-built/test-layers.md:214-226 (Apache-2.0).
"""

# adapted from references/openrig/packages/test-system/ci/result.mjs:33-34 (Apache-2.0)
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from xml.sax.saxutils import escape

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills/finhub-harness/scripts/mutant_gate.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutant_gate", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mutant_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


mg = load()
T0 = 1_800_000_000.0  # a fixed start time for the hand-made reports

# ------------------------------------------------------------------ hand-made reports

TEST = "tests/test_g.py::test_depth"
SIG = "assert 6 == 5"


def stamp(t: float) -> str:
    return datetime.fromtimestamp(t, tz=UTC).isoformat()


def report(
    cases: dict[str, str],
    lines: dict[str, list[str]] | None = None,
    t: float | None = T0,
    dur: float = 0.0,
) -> str:
    """JUnit text like pytest's: status is passed, failed, error or skipped.

    A line that starts with "!" is written as it is, without the `E` prefix (native tracebacks).
    """
    lines = lines or {}
    out = []
    for name, status in cases.items():
        body = escape(
            "\n".join(x[1:] if x.startswith("!") else f"E       {x}" for x in lines.get(name, []))
        )
        tag = {"failed": "failure", "error": "error", "skipped": "skipped"}.get(status)
        inner = f'<{tag} message="m">{body}</{tag}>' if tag else ""
        out.append(f'<testcase classname="tests.test_g" name="{name}">{inner}</testcase>')
    ts = f' timestamp="{stamp(t)}"' if t is not None else ""
    return (
        f'<testsuites><testsuite name="pytest"{ts} time="{dur}">{"".join(out)}</testsuite>'
        "</testsuites>"
    )


GREEN = {"test_depth": "passed", "test_other": "passed"}
HIT = {"test_depth": [SIG]}


def run(
    tmp: Path,
    before: str | None,
    mutant: str | None,
    after: str | None,
    spec: dict[str, str] | None = None,
    spec_at: float = T0 - 100,
) -> tuple[int, str, str]:
    """Run the CLI on three reports; returns (exit code, STATE value, whole output)."""
    base = {"id": "M1", "file": "src/g.py", "old": "<= 5", "new": "<= 6", "test": TEST, "sig": SIG}
    spec_file = tmp / "spec.json"
    spec_file.write_text(json.dumps({**base, **(spec or {})}), encoding="utf-8")
    os.utime(spec_file, (spec_at, spec_at))
    names = {"before": before, "mutant": mutant, "after": after}
    args = ["classify", str(spec_file)]
    for which, text in names.items():
        f = tmp / f"{which}.xml"
        f.unlink(missing_ok=True)
        if text is not None:
            f.write_text(text, encoding="utf-8")
        args += [f"--{which}", str(f)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mg.main(args)
    out = buf.getvalue()
    m = re.search(r"^STATE: (\S+)", out, re.MULTILINE)
    return code, (m.group(1) if m else "-"), out


def legs(
    mutant: str | None,
    before: str | None = None,
    after: str | None = None,
    times: tuple[float, float, float] = (T0, T0 + 1, T0 + 2),
) -> tuple[str | None, str | None, str | None]:
    b = before if before is not None else report(GREEN, t=times[0])
    a = after if after is not None else report(GREEN, t=times[2])
    return b, mutant, a


def caught_mutant(extra: dict[str, str] | None = None) -> str:
    return report({**GREEN, "test_depth": "failed", **(extra or {})}, HIT, T0 + 1)


def test_caught(tmp_path: Path) -> None:
    code, state, out = run(tmp_path, *legs(caught_mutant()))
    assert (code, state) == (0, "CAUGHT"), out
    digest = hashlib.sha256((tmp_path / "spec.json").read_bytes()).hexdigest()
    assert f"SPEC-SHA256: {digest}" in out


def test_caught_when_another_test_also_fails(tmp_path: Path) -> None:
    mut = caught_mutant({"test_other": "failed"})
    assert run(tmp_path, *legs(mut))[:2] == (0, "CAUGHT")


def test_caught_with_message_before_the_introspection(tmp_path: Path) -> None:
    mut = report(
        {**GREEN, "test_depth": "failed"}, {"test_depth": ["AssertionError: depth 6", SIG]}, T0 + 1
    )
    assert run(tmp_path, *legs(mut))[:2] == (0, "CAUGHT")


def test_caught_by_did_not_raise(tmp_path: Path) -> None:
    mut = report(
        {**GREEN, "test_depth": "failed"},
        {"test_depth": ["Failed: DID NOT RAISE <class 'ValueError'>"]},
        T0 + 1,
    )
    got = run(tmp_path, *legs(mut), spec={"sig": "DID NOT RAISE"})
    assert got[:2] == (0, "CAUGHT")


def test_survived(tmp_path: Path) -> None:
    code, state, _ = run(tmp_path, *legs(report(GREEN, t=T0 + 1)))
    assert (code, state) == (3, "SURVIVED")


MUTANT_CASES: list[tuple[str, str, str]] = [
    (
        "collection error",
        report({"test_g": "error"}, {"test_g": ["ModuleNotFoundError: x"]}, T0 + 1),
        "error elements",
    ),
    (
        "error in an unrelated test",
        report({"test_depth": "failed", "test_other": "error"}, HIT, T0 + 1),
        "error elements",
    ),
    (
        "signature absent",
        report({**GREEN, "test_depth": "failed"}, {"test_depth": ["assert 7 == 5"]}, T0 + 1),
        "lacks the signature",
    ),
    (
        "import error first, signature later in the traceback",
        report(
            {**GREEN, "test_depth": "failed"},
            {"test_depth": ["ModuleNotFoundError: No module named 'x'", SIG]},
            T0 + 1,
        ),
        "not an assertion",
    ),
    (
        "name error",
        report({**GREEN, "test_depth": "failed"}, {"test_depth": ["NameError: name 'q'"]}, T0 + 1),
        "not an assertion",
    ),
    (
        "pytest-timeout failure inside the intended test",
        report(
            {**GREEN, "test_depth": "failed"},
            {"test_depth": ["Failed: Timeout >5.0s", SIG]},
            T0 + 1,
        ),
        "not an assertion",
    ),
    (
        "failure with no error line",
        report({**GREEN, "test_depth": "failed"}, {}, T0 + 1),
        "not an assertion",
    ),
    (
        "failure only in another test",
        report({**GREEN, "test_other": "failed"}, {"test_other": [SIG]}, T0 + 1),
        "others failed",
    ),
    (
        "intended test skipped",
        report({**GREEN, "test_depth": "skipped"}, t=T0 + 1),
        "missing or skipped",
    ),
    (
        "intended test renamed",
        report({"test_depth_renamed": "failed", "test_other": "passed"}, HIT, T0 + 1),
        "ids that differ",
    ),
    (
        "equal count, different selection",
        report({"test_depth": "failed", "test_new": "passed"}, HIT, T0 + 1),
        "ids that differ",
    ),
    (
        "native traceback without the E prefix",
        report(
            {**GREEN, "test_depth": "failed"}, {"test_depth": ["!AssertionError: " + SIG]}, T0 + 1
        ),
        "not an assertion",
    ),
    (
        "traceback line that starts with E but has no space after it",
        report(
            {**GREEN, "test_depth": "failed"}, {"test_depth": ["!EAssertionError: " + SIG]}, T0 + 1
        ),
        "not an assertion",
    ),
    (
        "fewer tests ran",
        report({"test_depth": "failed"}, HIT, T0 + 1),
        "tests ran",
    ),
    (
        "more tests ran",
        report({**GREEN, "test_new": "passed", "test_depth": "failed"}, HIT, T0 + 1),
        "tests ran",
    ),
    ("report is not XML", "this is not xml", "no readable report"),
    ("report has no test case", "<testsuites/>", "no readable report"),
]


@pytest.mark.parametrize("name,mut,why", MUTANT_CASES, ids=[c[0] for c in MUTANT_CASES])
def test_mutant_leg_is_invalid(tmp_path: Path, name: str, mut: str, why: str) -> None:
    code, state, out = run(tmp_path, *legs(mut))
    assert (code, state) == (3, "INVALID"), name
    assert why in out, out


def test_missing_mutant_report_is_invalid(tmp_path: Path) -> None:
    code, state, out = run(tmp_path, *legs(None))
    assert (code, state) == (3, "INVALID")
    assert "no readable report" in out


BASELINE_CASES: list[tuple[str, dict[str, str], str]] = [
    (
        "before red",
        {"before": report({**GREEN, "test_other": "failed"}, t=T0)},
        "before the mutant",
    ),
    (
        "before lacks the test",
        {"before": report({"test_other": "passed"}, t=T0)},
        "not in the report",
    ),
    (
        "before skips the test",
        {"before": report({**GREEN, "test_depth": "skipped"}, t=T0)},
        "skipped",
    ),
    (
        "after red",
        {"after": report({**GREEN, "test_depth": "failed"}, HIT, T0 + 2)},
        "after restoring",
    ),
    (
        "after has another count",
        {"after": report({"test_depth": "passed"}, t=T0 + 2)},
        "tests, 2 before",
    ),
    (
        "after has the same count but other tests",
        {"after": report({"test_depth": "passed", "test_new": "passed"}, t=T0 + 2)},
        "ids that differ",
    ),
    (
        "after errors",
        {"after": report({**GREEN, "test_other": "error"}, t=T0 + 2)},
        "after restoring",
    ),
]


@pytest.mark.parametrize("name,over,why", BASELINE_CASES, ids=[c[0] for c in BASELINE_CASES])
@pytest.mark.parametrize("mut_kind", ["caught", "survived"])
def test_baseline_leg_red(
    tmp_path: Path, name: str, over: dict[str, str], why: str, mut_kind: str
) -> None:
    mut = caught_mutant() if mut_kind == "caught" else report(GREEN, t=T0 + 1)
    b, m, a = legs(mut)
    code, state, out = run(tmp_path, over.get("before", b), m, over.get("after", a))
    assert (code, state) == (3, "BASELINE-RED"), out
    assert why in out, out


def test_missing_baseline_reports_are_baseline_red(tmp_path: Path) -> None:
    b, m, a = legs(caught_mutant())
    assert run(tmp_path, None, m, a)[:2] == (3, "BASELINE-RED")
    assert run(tmp_path, b, m, None)[:2] == (3, "BASELINE-RED")


def test_red_before_voids_a_run_that_looks_caught(tmp_path: Path) -> None:
    before = report({"test_depth": "failed", "test_other": "passed"}, HIT, T0)
    assert run(tmp_path, *legs(caught_mutant(), before=before))[:2] == (3, "BASELINE-RED")


def test_invalid_mutant_is_reported_before_a_red_after_leg(tmp_path: Path) -> None:
    mut = report({"test_g": "error"}, t=T0 + 1)
    after = report({**GREEN, "test_other": "failed"}, t=T0 + 2)
    assert run(tmp_path, *legs(mut, after=after))[:2] == (3, "INVALID")


ORDER_CASES: list[tuple[str, tuple[float, float, float], float]] = [
    ("same start time", (T0, T0, T0), T0 - 100),
    ("mutant before baseline", (T0 + 1, T0, T0 + 2), T0 - 100),
    ("after before mutant", (T0, T0 + 2, T0 + 1), T0 - 100),
    ("spec written after the before run", (T0, T0 + 1, T0 + 2), T0 + 0.5),
]


@pytest.mark.parametrize("name,times,spec_at", ORDER_CASES, ids=[c[0] for c in ORDER_CASES])
def test_order(
    tmp_path: Path, name: str, times: tuple[float, float, float], spec_at: float
) -> None:
    mut = report({**GREEN, "test_depth": "failed"}, HIT, times[1])
    b = report(GREEN, t=times[0])
    a = report(GREEN, t=times[2])
    code, state, _ = run(tmp_path, b, mut, a, spec_at=spec_at)
    assert (code, state) == (3, "ORDER"), name


def test_before_leg_that_ends_after_the_mutant_starts_is_order(tmp_path: Path) -> None:
    b = report(GREEN, t=T0, dur=2)  # ends at T0 + 2, the mutant leg starts at T0 + 1
    code, state, _ = run(tmp_path, b, caught_mutant(), report(GREEN, t=T0 + 2))
    assert (code, state) == (3, "ORDER")


def test_mutant_leg_that_ends_after_the_after_leg_starts_is_order(tmp_path: Path) -> None:
    mut = report({**GREEN, "test_depth": "failed"}, HIT, T0 + 1, dur=5)  # ends at T0 + 6
    code, state, _ = run(tmp_path, report(GREEN, t=T0), mut, report(GREEN, t=T0 + 2))
    assert (code, state) == (3, "ORDER")


def test_a_leg_that_ends_when_the_next_one_starts_is_in_order(tmp_path: Path) -> None:
    ok = report(GREEN, t=T0, dur=1)  # ends exactly when the mutant leg starts
    code, state, _ = run(tmp_path, ok, caught_mutant(), report(GREEN, t=T0 + 2))
    assert (code, state) == (0, "CAUGHT")


def test_a_mutant_leg_that_ends_when_the_after_leg_starts_is_in_order(tmp_path: Path) -> None:
    mut = report({**GREEN, "test_depth": "failed"}, HIT, T0 + 1, dur=1)  # ends at T0 + 2
    code, state, _ = run(tmp_path, report(GREEN, t=T0), mut, report(GREEN, t=T0 + 2))
    assert (code, state) == (0, "CAUGHT")


def test_whitespace_in_the_signature_and_in_the_failure_text_is_squashed(tmp_path: Path) -> None:
    mut = report({**GREEN, "test_depth": "failed"}, {"test_depth": ["assert 6   ==\t5"]}, T0 + 1)
    got = run(tmp_path, *legs(mut), spec={"sig": "assert \t 6  ==   5"})
    assert got[:2] == (0, "CAUGHT"), got[2]


def test_an_indented_source_line_starting_with_e_is_not_an_error_line(tmp_path: Path) -> None:
    mut = report(
        {**GREEN, "test_depth": "failed"}, {"test_depth": ["!    E = compute()", SIG]}, T0 + 1
    )
    got = run(tmp_path, *legs(mut))
    assert got[:2] == (0, "CAUGHT"), got[2]


def test_the_differing_ids_are_named_up_to_three(tmp_path: Path) -> None:
    extra = {f"test_x{i}": "passed" for i in range(1, 5)}  # four ids only the mutant leg ran
    mut = report({**GREEN, **extra, "test_depth": "failed"}, HIT, T0 + 1)
    out = run(tmp_path, *legs(mut))[2]
    reason = next(x for x in out.splitlines() if x.startswith("REASON:"))
    for i in (1, 2, 3):
        assert f"tests.test_g::test_x{i}" in reason, reason
    assert "test_x4" not in reason, reason


def test_missing_timestamp_is_order(tmp_path: Path) -> None:
    mut = report({**GREEN, "test_depth": "failed"}, HIT, None)
    assert run(tmp_path, *legs(mut))[:2] == (3, "ORDER")


def test_spec_written_exactly_at_the_before_run_is_in_order(tmp_path: Path) -> None:
    assert run(tmp_path, *legs(caught_mutant()), spec_at=T0)[:2] == (0, "CAUGHT")


def test_junit_key_shapes() -> None:
    assert mg.junit_key("tests/test_g.py::test_depth") == ("tests.test_g", "test_depth")
    assert mg.junit_key("tests/test_g.py::TestG::test_d[a-1]") == (
        "tests.test_g.TestG",
        "test_d[a-1]",
    )


def test_windows_separator_in_the_test_id_is_read_as_a_slash() -> None:
    assert mg.junit_key("tests\\test_g.py::test_depth") == ("tests.test_g", "test_depth")
    assert mg.junit_key("tests/test_g.py::test_d[a\\b]") == ("tests.test_g", "test_d[a\\b]")


def test_class_based_test_id_reaches_the_report(tmp_path: Path) -> None:
    def rep(status: str, t: float) -> str:
        tag = "failure" if status == "failed" else None
        inner = f"<{tag}>E       {SIG}</{tag}>" if tag else ""
        return (
            f'<testsuite timestamp="{stamp(t)}"><testcase classname="tests.test_g.TestG" '
            f'name="test_d[a-1]">{inner}</testcase></testsuite>'
        )

    spec = {"test": "tests/test_g.py::TestG::test_d[a-1]"}
    got = run(tmp_path, rep("passed", T0), rep("failed", T0 + 1), rep("passed", T0 + 2), spec)
    assert got[:2] == (0, "CAUGHT"), got[2]


BAD_SPECS: list[tuple[str, dict[str, object]]] = [
    ("bare assert", {"sig": "assert"}),
    ("bare AssertionError", {"sig": "AssertionError"}),
    ("short signature", {"sig": "a == b"[:5]}),
    ("five characters", {"sig": "abcde"}),
    ("padded bare assert", {"sig": "  assert  "}),
    ("padded bare AssertionError", {"sig": "AssertionError "}),
    ("file is the module of the test", {"file": "tests/test_g.py"}),
    (
        "file is the module of the test, written ./ and with a backslash",
        {"file": ".\\tests\\test_g.py"},
    ),
    ("file is conftest.py", {"file": "tests/conftest.py"}),
    ("file is conftest.py in capitals", {"file": "tests/Conftest.PY"}),
    ("file is conftest.py with a backslash", {"file": "tests\\conftest.py"}),
    ("file is conftest.py with a trailing space", {"file": "tests/conftest.py "}),
    ("file is the absolute path of the module", {"file": "/work/repo/tests/test_g.py"}),
    ("file is the absolute Windows path of the module", {"file": "C:\\repo\\tests\\test_g.py"}),
    ("file is the module in other letter case", {"file": "tests/Test_G.py"}),
    ("file is the module with a trailing space", {"file": "tests/test_g.py "}),
    ("file is the module with a double slash", {"file": "tests//test_g.py"}),
    ("file is the module behind a dot-dot detour", {"file": "./tests/../tests/test_g.py"}),
    ("file is the module reached through src/..", {"file": "src/../tests/test_g.py"}),
    ("blank signature", {"sig": "      "}),
    ("old equals new", {"new": "a"}),
    ("no id", {"id": ""}),
    ("no file", {"file": ""}),
    ("test without a function", {"test": "tests/test_g.py"}),
    ("test that is not python", {"test": "tests/g.txt::test_x"}),
    ("field is not a string", {"old": 5}),
]


@pytest.mark.parametrize("name,over", BAD_SPECS, ids=[c[0] for c in BAD_SPECS])
def test_bad_spec_is_exit_2(tmp_path: Path, name: str, over: dict[str, object]) -> None:
    base: dict[str, object] = {
        "id": "M1",
        "file": "f.py",
        "old": "a",
        "new": "b",
        "test": TEST,
        "sig": SIG,
    }
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({**base, **over}), encoding="utf-8")
    for w in ("before", "mutant", "after"):
        (tmp_path / f"{w}.xml").write_text(report(GREEN), encoding="utf-8")
    args = ["classify", str(spec)] + [
        x for w in ("before", "mutant", "after") for x in (f"--{w}", str(tmp_path / f"{w}.xml"))
    ]
    assert mg.main(args) == 2, name


def test_six_characters_is_the_shortest_signature(tmp_path: Path) -> None:
    mut = report({**GREEN, "test_depth": "failed"}, {"test_depth": ["assert abcdef"]}, T0 + 1)
    assert run(tmp_path, *legs(mut), spec={"sig": "abcdef"})[:2] == (0, "CAUGHT")


def test_an_absolute_directory_that_merely_ends_in_tests_is_accepted(tmp_path: Path) -> None:
    got = run(tmp_path, *legs(caught_mutant()), spec={"file": "/a/xtests/test_g.py"})
    assert got[:2] == (0, "CAUGHT")


def test_a_file_that_only_ends_in_conftest_py_is_accepted(tmp_path: Path) -> None:
    got = run(tmp_path, *legs(caught_mutant()), spec={"file": "tests/myconftest.py"})
    assert got[:2] == (0, "CAUGHT")


def test_an_absolute_path_that_does_not_end_in_the_module_is_accepted(tmp_path: Path) -> None:
    got = run(tmp_path, *legs(caught_mutant()), spec={"file": "/work/repo/src/test_g.py"})
    assert got[:2] == (0, "CAUGHT")


def test_a_relative_path_below_another_directory_is_accepted(tmp_path: Path) -> None:
    got = run(tmp_path, *legs(caught_mutant()), spec={"file": "pkg/tests/test_g.py"})
    assert got[:2] == (0, "CAUGHT")


def test_a_file_that_only_looks_like_the_test_module_is_accepted(tmp_path: Path) -> None:
    got = run(tmp_path, *legs(caught_mutant()), spec={"file": "src/test_g.py"})
    assert got[:2] == (0, "CAUGHT")


def test_spec_not_json_or_missing_is_exit_2(tmp_path: Path) -> None:
    for w in ("before", "mutant", "after"):
        (tmp_path / f"{w}.xml").write_text(report(GREEN), encoding="utf-8")
    tail = [
        x for w in ("before", "mutant", "after") for x in (f"--{w}", str(tmp_path / f"{w}.xml"))
    ]
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert mg.main(["classify", str(bad), *tail]) == 2
    assert mg.main(["classify", str(tmp_path / "absent.json"), *tail]) == 2


def test_one_file_named_twice_is_exit_2(tmp_path: Path) -> None:
    same = tmp_path / "same.xml"
    same.write_text(report(GREEN), encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps({"id": "M", "file": "f", "old": "a", "new": "b", "test": TEST, "sig": SIG}),
        encoding="utf-8",
    )
    assert (
        mg.main(
            [
                "classify",
                str(spec),
                "--before",
                str(same),
                "--mutant",
                str(same),
                "--after",
                str(same),
            ]
        )
        == 2
    )


# ------------------------------------------------------------------ real pytest runs

MOD = """def depth_ok(d):
    return d <= 5


def clamp(x):
    return min(x, 10)


def must_be_positive(v):
    if v <= 0:
        raise ValueError("not positive")
    return v
"""
TESTS = """import pytest
import mod


def test_depth():
    assert mod.depth_ok(5) is True
    assert mod.depth_ok(6) is False


def test_clamp():
    assert mod.clamp(99) == 10


def test_positive():
    with pytest.raises(ValueError):
        mod.must_be_positive(0)
"""


def pytest_leg(proj: Path, xml: Path, timeout: float = 60) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "PYTHONPATH"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    xml.unlink(missing_ok=True)
    cmd = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    cmd += [f"--junitxml={xml}", "test_g.py"]
    try:
        subprocess.run(cmd, cwd=proj, env=env, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        pass  # the killed run leaves no report, which is the case under test


def sandwich(
    tmp: Path,
    old: str,
    new: str,
    test: str,
    sig: str,
    *,
    restore: bool = True,
    pre_mutated: bool = False,
    mutant_timeout: float = 60,
    swap: bool = False,
) -> tuple[int, str, str]:
    proj = tmp / "proj"
    proj.mkdir()
    (proj / "mod.py").write_text(MOD, encoding="utf-8")
    (proj / "test_g.py").write_text(TESTS, encoding="utf-8")
    (proj / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    spec = {
        "id": "M",
        "file": "mod.py",
        "old": old,
        "new": new,
        "test": f"test_g.py::{test}",
        "sig": sig,
    }
    (tmp / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    assert old in MOD and old != new
    if pre_mutated:
        (proj / "mod.py").write_text(MOD.replace(old, new), encoding="utf-8")
    pytest_leg(proj, tmp / "before.xml")
    (proj / "mod.py").write_text(MOD.replace(old, new), encoding="utf-8")
    pytest_leg(proj, tmp / "mutant.xml", mutant_timeout)
    if restore:
        (proj / "mod.py").write_text(MOD, encoding="utf-8")
    pytest_leg(proj, tmp / "after.xml")
    first, last = ("after", "before") if swap else ("before", "after")
    args = ["classify", str(tmp / "spec.json"), "--before", str(tmp / f"{first}.xml")]
    args += ["--mutant", str(tmp / "mutant.xml"), "--after", str(tmp / f"{last}.xml")]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mg.main(args)
    m = re.search(r"^STATE: (\S+)", buf.getvalue(), re.MULTILINE)
    return code, (m.group(1) if m else "-"), buf.getvalue()


REAL: list[tuple[str, dict[str, object], str, str]] = [
    (
        "assertion mutant",
        {"old": "d <= 5", "new": "d <= 6", "test": "test_depth", "sig": "assert True is False"},
        "CAUGHT",
        "intended test failed at",
    ),
    (
        "did not raise",
        {"old": "if v <= 0:", "new": "if v < 0:", "test": "test_positive", "sig": "DID NOT RAISE"},
        "CAUGHT",
        "DID NOT RAISE",
    ),
    (
        "equivalent change",
        {"old": "min(x, 10)", "new": "min(10, x)", "test": "test_clamp", "sig": "assert 99 == 10"},
        "SURVIVED",
        "every test passed",
    ),
    (
        "syntax error",
        {
            "old": "return d <= 5",
            "new": "return d <=",
            "test": "test_depth",
            "sig": "assert True is False",
        },
        "INVALID",
        "error elements",
    ),
    (
        "import error",
        {
            "old": "def depth_ok",
            "new": "import no_such_module_q\n\ndef depth_ok",
            "test": "test_depth",
            "sig": "assert True is False",
        },
        "INVALID",
        "error elements",
    ),
    (
        "name error inside the code under test",
        {"old": "d <= 5", "new": "d <= undefined_q", "test": "test_depth", "sig": "undefined_q"},
        "INVALID",
        "not an assertion",
    ),
    (
        "intended test passes, another fails",
        {"old": "min(x, 10)", "new": "min(x, 11)", "test": "test_depth", "sig": "assert 99 == 10"},
        "INVALID",
        "others failed",
    ),
]


@pytest.mark.parametrize("name,kw,state,why", REAL, ids=[c[0] for c in REAL])
def test_real_pytest_run(
    tmp_path: Path, name: str, kw: dict[str, object], state: str, why: str
) -> None:
    code, got, out = sandwich(tmp_path, **kw)  # type: ignore[arg-type]
    assert got == state, out
    assert (code == 0) == (state == "CAUGHT")
    assert why in out, out


def test_real_timeout_leaves_no_report(tmp_path: Path) -> None:
    code, got, out = sandwich(
        tmp_path,
        "return min(x, 10)",
        "import time\n    time.sleep(120)\n    return min(x, 10)",
        "test_clamp",
        "assert 99 == 10",
        mutant_timeout=3,
    )
    assert (code, got) == (3, "INVALID"), out
    assert "no readable report" in out


def test_real_forgotten_restore_is_baseline_red(tmp_path: Path) -> None:
    kw = {"old": "d <= 5", "new": "d <= 6", "test": "test_depth", "sig": "assert True is False"}
    code, got, out = sandwich(tmp_path, restore=False, **kw)  # type: ignore[arg-type]
    assert (code, got) == (3, "BASELINE-RED")
    assert "after restoring" in out, out


def test_real_mutated_tree_before_the_first_leg_is_baseline_red(tmp_path: Path) -> None:
    kw = {"old": "d <= 5", "new": "d <= 6", "test": "test_depth", "sig": "assert True is False"}
    code, got, out = sandwich(tmp_path, pre_mutated=True, **kw)  # type: ignore[arg-type]
    assert (code, got) == (3, "BASELINE-RED")
    assert "before the mutant" in out, out


def test_real_legs_given_in_the_wrong_order_are_order(tmp_path: Path) -> None:
    kw = {"old": "d <= 5", "new": "d <= 6", "test": "test_depth", "sig": "assert True is False"}
    code, got, out = sandwich(tmp_path, swap=True, **kw)  # type: ignore[arg-type]
    assert (code, got) == (3, "ORDER"), out


# ------------------------------------------------------------------ the prose

PROSE = {
    "qg": "skills/finhub-harness/references/quality-gates.md",
    "qag": "skills/finhub-harness/references/qa-agent-guide.md",
    "skill": "skills/finhub-harness/SKILL.md",
    "tmpl": "skills/finhub-harness/references/orchestrator-template.md",
    "bqa": ".claude/agents/boundary-qa.md",
    "bqas": ".claude/skills/boundary-qa/SKILL.md",
    "rsd": ".claude/skills/runtime-slice-design/SKILL.md",
}

PINS: list[tuple[str, str, str]] = [
    ("qg-purpose", "qg", "fails, at the assertion written for it"),
    ("qg-tar", "qg", "with `tar`, so `.gitignore`, `skills/` and `.claude/` come along"),
    ("qg-exclude", "qg", "Leave `.venv`, `.git`, `dist` and `__pycache__` out of the copy"),
    ("qg-refs-link", "qg", "a read-only link to the pinned `references/` instead of a second copy"),
    (
        "qg-outside",
        "qg",
        "Everything you write (`spec.json`, the three reports) goes into a work directory outside the tree too",
    ),
    ("qg-never-edit", "qg", "Never edit or delete anything in the repo under review."),
    ("qg-vars", "qg", 'COPY=$(mktemp -d)                                        # outside "$REPO"'),
    (
        "qg-repo-script",
        "qg",
        "Run `classify` from the unmutated script in `$REPO`, never from the copy.",
    ),
    ("qg-file-rule", "qg", "never the module named in `test`, and never `conftest.py`"),
    (
        "qg-M1-file",
        "qg",
        "It exits 2 for a spec whose `file` is the module named in `test` or is `conftest.py`",
    ),
    ("qg-M2-ids", "qg", "the same set of test ids, not only the same number"),
    (
        "qg-M5-end",
        "qg",
        "a leg must end (its start plus the suite time pytest wrote) no later than the next leg starts",
    ),
    ("qg-M5-guard", "qg", "the file time is the only mechanical guard on your own `sig`"),
    ("qg-prereg", "qg", "copy `test` and `sig` from the design's row byte for byte"),
    ("qg-not-prereg", "qg", 'is labelled "not pre-registered" in the report'),
    ("qg-dnc-versions", "qg", "pytest 6.2.5 to 9.1.1 on Python 3.11"),
    (
        "qg-dnc-tb",
        "qg",
        "`--tb=native` (the failure text has no `E` lines, so the run is `INVALID`)",
    ),
    (
        "qg-dnc-warns",
        "qg",
        "a failing `pytest.warns` (`Failed: DID NOT WARN` is not in the allow-list",
    ),
    ("qg-dnc-colons", "qg", "A test id whose parameter ids contain `::` cannot be matched"),
    ("qg-dnc-win", "qg", "A `\\` in the `test` path is read as `/`"),
    ("qg-dnc-tz", "qg", "`classify` reads it in its own time zone"),
    ("qg-new-copy", "qg", "make a new copy for each mutant"),
    ("qg-spec-first", "qg", "Before the first run of a mutant, write its spec and save it"),
    (
        "qg-sig-floor",
        "qg",
        "at least 6 characters, and not the bare word `assert` or `AssertionError`",
    ),
    (
        "qg-choose-after",
        "qg",
        "Choosing the mutant after seeing which test fails is not a mutation check.",
    ),
    ("qg-three-legs", "qg", "Run three legs, in this order"),
    ("qg-no-x", "qg", "(no `-x`: a stopped run reports fewer tests and is void)"),
    ("qg-command", "qg", "python -B -m pytest -p no:cacheprovider --junitxml="),
    ("qg-M1", "qg", "| M1 | The spec is written and hashed before the first leg."),
    ("qg-M2", "qg", "| M2 | One mutant is three legs: before, mutant, after."),
    ("qg-M3", "qg", "| M3 | CAUGHT needs all of:"),
    ("qg-M3-list", "qg", "a collection, import or syntax error, a crash or a timeout"),
    ("qg-M4", "qg", "A red `before` voids the mutant run"),
    (
        "qg-M5",
        "qg",
        "| M5 | The reports must be in time order: spec file, `before`, `mutant`, `after`, and a leg",
    ),
    ("qg-M6", "qg", "| M6 | `SURVIVED`"),
    ("qg-M7", "qg", "A behaviour whose mutants are all void is unproven, and the report is FAIL."),
    (
        "qg-M7-probe",
        "qg",
        "Only a `mutant:` row that ends in `CAUGHT` or `SURVIVED` counts as the adversarial probe",
    ),
    (
        "qg-M8",
        "qg",
        "a state taken from an earlier candidate goes on the `CARRIED:` line and never licenses a PASS",
    ),
    ("qg-nonpytest", "qg", "Anything that is not pytest."),
    ("qg-prose", "qg", "the pin test is the intended assertion"),
    ("qg-equivalent", "qg", "Equivalent mutants. They still need a written argument"),
    ("qg-flaky", "qg", "Flaky tests."),
    ("qg-wrong-thing", "qg", "A test that asserts the wrong thing."),
    ("qg-fraud", "qg", "The script is there to catch accidents, not to detect fraud."),
    ("qg-old-kills", "qg", "were recorded under the earlier wording"),
    (
        "qg-checklist",
        "qg",
        "A mutant is killed only when `mutant_gate.py classify` prints `STATE: CAUGHT` for it",
    ),
    ("qg-checklist-probe", "qg", "the latter only with a"),
    ("qag-probe", "qag", "ends in `STATE: CAUGHT` or `STATE: SURVIVED`"),
    ("qag-excuse", "qag", "The mutant made the tests fail, so it is killed"),
    ("qag-section", "qag", "### 7-9. Mutant rows"),
    ("qag-exit0", "qag", "Exit 0 is the only kill."),
    ("qag-void", "qag", "Never edit a report to turn a void row into a kill."),
    ("qag-prereg", "qag", "copy `test` and `sig` from the design's row byte for byte"),
    ("qag-not-prereg", "qag", 'a mutant you add yourself is labelled "not pre-registered"'),
    (
        "qag-filetime",
        "qag",
        "The file time of the spec is the only mechanical guard on a `sig` you chose yourself.",
    ),
    (
        "skill-clause",
        "skill",
        "count a mutant as killed only when `scripts/mutant_gate.py` prints `STATE: CAUGHT` for it",
    ),
    ("skill-checklist", "skill", "Each mutant it ran ends in `STATE: CAUGHT` or is redone."),
    (
        "skill-ref",
        "skill",
        "A mutant counts as caught only when the test written for it fails at the assertion written for it",
    ),
    ("tmpl-brief", "tmpl", "only `STATE: CAUGHT` counts as a kill"),
    (
        "tmpl-candidate",
        "tmpl",
        "The copy for the mutants is taken from the tree on the `Candidate:` line.",
    ),
    (
        "bqa-bullet",
        "bqa",
        "A mutant counts as killed only when `python3 skills/finhub-harness/scripts/mutant_gate.py classify` prints `STATE: CAUGHT` for it",
    ),
    ("bqa-void", "bqa", "is `INVALID`: redo the mutant, never record it as killed."),
    ("bqa-adoption", "bqa", "a catching pytest test is judged by `mutant_gate.py classify`"),
    ("bqas-row", "bqas", "a `mutant:` row ends in `STATE: CAUGHT` or `STATE: SURVIVED`"),
    ("rsd-plan", "rsd", "each with the one test id it should break"),
    ("rsd-required", "rsd", "required in an adoption's plan, optional in a runtime slice's"),
]


def texts() -> dict[str, str]:
    return {k: (REPO / v).read_text(encoding="utf-8") for k, v in PROSE.items()}


@pytest.mark.parametrize("tag,key,phrase", PINS, ids=[p[0] for p in PINS])
def test_pin(tag: str, key: str, phrase: str) -> None:
    assert phrase in texts()[key], f"pin {tag}: sentence missing from {PROSE[key]}"


def test_old_killed_wording_is_gone() -> None:
    assert "A mutant is KILLED if a named test fails" not in texts()["qg"]


def test_every_changed_file_carries_an_openrig_attribution() -> None:
    pat = re.compile(r"adapted from references/openrig/[\w./-]+:\d+(?:-\d+)? \(Apache-2\.0\)")
    for key, rel in PROSE.items():
        assert pat.search(texts()[key]), rel
    for path in (SCRIPT, Path(__file__)):
        assert pat.search(path.read_text(encoding="utf-8")), path


def test_no_hangul() -> None:
    blobs = list(texts().values()) + [
        SCRIPT.read_text(encoding="utf-8"),
        Path(__file__).read_text(encoding="utf-8"),
    ]
    for blob in blobs:
        assert not any(unicodedata.name(c, "").startswith("HANGUL") for c in blob)


def cited() -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    blob = "\n".join(texts().values()) + SCRIPT.read_text() + Path(__file__).read_text()
    for m in re.finditer(r"references/openrig/([\w./-]+?):(\d+)(?:-(\d+))?", blob):
        out.add((m[1], int(m[2])))
        if m[3]:
            out.add((m[1], int(m[3])))
    return out


def test_cited_openrig_lines_exist() -> None:
    root = REPO / "references/openrig"
    if not (root / "LICENSE").exists():
        pytest.skip("references/openrig is not checked out")
    got = cited()
    assert ("packages/test-system/ci/result.mjs", 33) in got
    for path, ln in sorted(got):
        f = root / path
        assert f.is_file(), path
        assert 1 <= ln <= len(f.read_text(encoding="utf-8").splitlines()), (path, ln)


def test_no_eight_word_run_from_openrig() -> None:
    root = REPO / "references/openrig"
    if not (root / "LICENSE").exists():
        pytest.skip("references/openrig is not checked out")

    def words(s: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", s.lower())

    grams: set[tuple[str, ...]] = set()
    for path in {p for p, _ in cited()}:
        w = words((root / path).read_text(encoding="utf-8"))
        grams.update(tuple(w[i : i + 8]) for i in range(len(w) - 7))
    ours = [SCRIPT.read_text(encoding="utf-8")]
    for key in ("qg", "qag", "tmpl", "bqa", "bqas", "rsd", "skill"):
        ours.append(texts()[key])
    for blob in ours:
        w = words(blob)
        for i in range(len(w) - 7):
            assert tuple(w[i : i + 8]) not in grams, " ".join(w[i : i + 8])


def test_script_runs_as_a_program(tmp_path: Path) -> None:
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "classify",
            str(tmp_path / "none.json"),
            "--before",
            "a",
            "--mutant",
            "b",
            "--after",
            "c",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2
    assert "error" in done.stdout


def test_script_imports_nothing_that_runs_a_process_or_a_network() -> None:
    import ast

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    banned = {"subprocess", "socket", "urllib", "http", "requests", "ctypes", "multiprocessing"}
    assert not names & banned, sorted(names & banned)


def test_script_has_no_bytecode_residue_and_docstring() -> None:
    assert SCRIPT.read_text(encoding="utf-8").startswith('"""Decide whether a planted-fault run')
    assert not list(SCRIPT.parent.glob("mutant_gate*.pyc"))
