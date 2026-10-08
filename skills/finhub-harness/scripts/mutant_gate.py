"""Decide whether a planted-fault run (a mutant) was CAUGHT, from three pytest JUnit files.

Usage: mutant_gate.py classify SPEC.json --before B.xml --mutant M.xml --after A.xml
Exit 0 only for STATE: CAUGHT; 3 for every other state (SURVIVED, INVALID, BASELINE-RED, ORDER);
2 for a bad call, an unreadable spec or the same file named twice.
Rules M1-M8 are in skills/finhub-harness/references/quality-gates.md section 3-4.

A mutant is CAUGHT only when the one test it was written to break fails on an assertion whose text
contains the signature the spec named before the run, and the run before and the run after the
mutant both pass that same test. A collection error, an import error, a syntax error, a crash, a
timeout or a failure somewhere else is never a catch. The rule (a catch counts only at the intended
assertion; a healthy run, a faulted run, then a healthy run again) is adapted from
references/openrig/packages/test-system/ci/result.mjs:33-34 and :50-65 and
references/openrig/docs/as-built/test-layers.md:214-226 (Apache-2.0). Rewritten for pytest, not
copied; stdlib only, no network, and it runs nothing itself.

Not covered: it cannot show that the QA agent applied the change the spec describes, that the
three files came from three real runs of one command, or that the spec was written before the
mutant was chosen (the spec's file time against the first run is the only check). It judges
pytest JUnit output and nothing else.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

FIELDS = ("id", "test", "sig", "file", "old", "new")
# ponytail: a length floor, not a proof that the signature is distinctive; the QA agent picks it
MIN_SIG = 6
BARE_SIG = ("assert", "AssertionError")  # matches every assertion failure, so it names nothing
# the first error line of the intended test must be an assertion of the test's own, not a crash
ASSERTION_STARTS = ("assert", "AssertionError", "Failed: DID NOT RAISE")
ERROR_LINE = re.compile(r"^E\s+(\S.*)$")
CAUGHT = "CAUGHT"


@dataclass
class Case:
    status: str  # passed | failed | error | skipped
    error_lines: list[str] = field(default_factory=list)


@dataclass
class Leg:
    cases: dict[tuple[str, str], Case]
    start: float | None
    end: float | None = None  # start plus the suite time pytest wrote; None when there is no start

    @property
    def tests(self) -> int:
        return len(self.cases)

    def count(self, status: str) -> int:
        return sum(1 for c in self.cases.values() if c.status == status)


def read_leg(path: Path) -> Leg | None:
    """None when the file is missing, is not XML or holds no test case (a run that was killed)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    cases: dict[tuple[str, str], Case] = {}
    for tc in root.iter("testcase"):
        status, lines = "passed", []
        for child in tc:
            if child.tag in ("failure", "error", "skipped"):
                status = "failed" if child.tag == "failure" else child.tag
                for raw in (child.text or "").splitlines():
                    m = ERROR_LINE.match(raw)
                    if m:
                        lines.append(m.group(1).strip())
        cases[(tc.get("classname", ""), tc.get("name", ""))] = Case(status, lines)
    if not cases:
        return None
    stamps: list[float] = []
    lasted = 0.0
    for suite in root.iter("testsuite"):
        try:
            stamps.append(datetime.fromisoformat(suite.get("timestamp", "")).timestamp())
        except ValueError:
            pass
        try:
            lasted += float(suite.get("time", "0"))
        except ValueError:
            pass
    start = min(stamps) if stamps else None
    return Leg(cases, start, None if start is None else start + lasted)


def junit_key(test: str) -> tuple[str, str]:
    """tests/test_x.py::Cls::test_y[a] -> ('tests.test_x.Cls', 'test_y[a]') as pytest writes it."""
    path, _, tail = test.partition("::")
    path = path.replace("\\", "/")  # a Windows separator in the spec; the param ids stay as typed
    *classes, name = tail.split("::")
    return ".".join([path.removesuffix(".py").replace("/", "."), *classes]), name


def same_module(file: str, test: str) -> bool:
    """True when `file` is the module the test id names (a mutant that edits its own test).

    Compared after strip, backslash to slash, normpath and case folding; an absolute `file` also
    matches when it ends with the test's relative path (the script does not know the repo root).
    """

    def norm(p: str) -> str:
        return os.path.normpath(p.strip().replace("\\", "/")).casefold()

    f, t = norm(file), norm(test.partition("::")[0])
    absolute = f.startswith("/") or re.match(r"[a-z]:/", f) is not None
    return f == t or (absolute and f.endswith("/" + t.lstrip("/")))


def is_conftest(file: str) -> bool:
    return file.strip().replace("\\", "/").rsplit("/", 1)[-1].casefold() == "conftest.py"


def load_spec(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_bytes()
    spec = json.loads(raw.decode("utf-8"))
    if not isinstance(spec, dict) or any(not isinstance(spec.get(k), str) for k in FIELDS):
        raise ValueError(f"spec needs string fields {', '.join(FIELDS)}")
    if not spec["id"] or not spec["file"] or spec["old"] == spec["new"]:
        raise ValueError("spec needs an id, a file and an old text different from the new text")
    if not spec["test"].partition("::")[0].endswith(".py") or "::" not in spec["test"]:
        raise ValueError("spec test must look like tests/test_x.py::test_name")
    if same_module(spec["file"], spec["test"]) or is_conftest(spec["file"]):
        raise ValueError(
            "spec file must be the code under test, not the test's own module or conftest.py"
        )
    if len(spec["sig"].strip()) < MIN_SIG or spec["sig"].strip() in BARE_SIG:
        raise ValueError(
            f"spec sig must be {MIN_SIG}+ characters of the failing assertion, not a bare keyword"
        )
    return spec, hashlib.sha256(raw).hexdigest()


def not_green(leg: Leg | None, key: tuple[str, str]) -> str | None:
    """Why a baseline leg is not a healthy run of the intended test, or None."""
    if leg is None:
        return "no readable report"
    if leg.count("failed") or leg.count("error"):
        return f"{leg.count('failed')} failed, {leg.count('error')} errors"
    case = leg.cases.get(key)
    if case is None:
        return "intended test not in the report"
    return None if case.status == "passed" else f"intended test {case.status}"


def differ(a: Leg, b: Leg) -> str:
    """Name up to three test ids that only one of two legs ran, so a swapped selection shows."""
    only = sorted(a.cases.keys() ^ b.cases.keys())[:3]
    return "; ids that differ: " + ", ".join(f"{c}::{n}" for c, n in only)


def squash(s: str) -> str:
    return " ".join(s.split())


# adapted from references/openrig/packages/test-system/ci/result.mjs:50-65 (Apache-2.0)
def judge_mutant(spec: dict[str, str], before: Leg, mutant: Leg | None) -> tuple[str, str]:
    """(CAUGHT | SURVIVED | INVALID, reason) for the mutant leg alone."""
    if mutant is None:
        return "INVALID", "no readable report (timeout, crash or kill: pytest writes it at the end)"
    if mutant.count("error"):
        return "INVALID", f"{mutant.count('error')} error elements (collection, import, setup)"
    # compare the test ids, not their number: two selections of equal size can differ
    if mutant.cases.keys() != before.cases.keys():
        why = f"{mutant.tests} tests ran, {before.tests} ran before{differ(before, mutant)}"
        return "INVALID", why
    case = mutant.cases.get(junit_key(spec["test"]))
    if case is None or case.status == "skipped":
        return "INVALID", "intended test missing or skipped"
    if case.status == "passed":
        if mutant.count("failed"):
            return "INVALID", f"intended test passed, {mutant.count('failed')} others failed"
        return "SURVIVED", "every test passed with the mutant in place"
    first = case.error_lines[0] if case.error_lines else ""
    if not first.startswith(ASSERTION_STARTS):
        return "INVALID", f"first error line is not an assertion: {first[:80]!r}"
    if squash(spec["sig"]) not in squash(" ".join(case.error_lines)):
        return "INVALID", f"assertion text lacks the signature {spec['sig']!r}"
    return CAUGHT, f"intended test failed at: {first[:80]}"


def classify(
    spec: dict[str, str],
    spec_time: float,
    before: Leg | None,
    mutant: Leg | None,
    after: Leg | None,
) -> tuple[str, str]:
    """The state of one mutant. Order of checks: baseline before, mutant, baseline after, order."""
    key = junit_key(spec["test"])
    why = not_green(before, key)
    if why or before is None:
        return "BASELINE-RED", f"before the mutant: {why}"
    state, reason = judge_mutant(spec, before, mutant)
    if state == "INVALID":
        return state, reason
    why = not_green(after, key)
    if why or after is None:
        return "BASELINE-RED", f"after restoring: {why}"
    if after.cases.keys() != before.cases.keys():
        why = f"{after.tests} tests, {before.tests} before{differ(before, after)}"
        return "BASELINE-RED", f"after restoring: {why}"
    assert mutant is not None
    b, m, a = before.start, mutant.start, after.start
    if b is None or m is None or a is None or before.end is None or mutant.end is None:
        return "ORDER", "a report has no timestamp"
    if not spec_time <= b < m < a or before.end > m or mutant.end > a:
        return "ORDER", "spec file time, before, mutant and after runs are not in that order"
    return state, reason


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mutant_gate.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    cl = sub.add_parser("classify", help="state of one mutant from its spec and three reports")
    cl.add_argument("spec", type=Path)
    for which in ("before", "mutant", "after"):
        cl.add_argument(f"--{which}", type=Path, required=True)
    args = ap.parse_args(argv)
    paths = [args.before, args.mutant, args.after]
    if len({os.path.realpath(p) for p in paths}) != 3:
        print("error: --before, --mutant and --after must be three different files")
        return 2
    try:
        spec, digest = load_spec(args.spec)
        spec_time = args.spec.stat().st_mtime
    except (OSError, ValueError) as e:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        print(f"error: {e}")
        return 2
    before, mutant, after = (read_leg(p) for p in paths)
    state, reason = classify(spec, spec_time, before, mutant, after)
    print(f"MUTANT: {spec['id']}  file={spec['file']}")
    print(f"SPEC-SHA256: {digest}")
    print(f"EXPECT: {spec['test']}  SIG: {spec['sig']}")
    for name, leg in (("BEFORE", before), ("MUTANT-RUN", mutant), ("AFTER", after)):
        print(
            f"{name}: "
            + (
                "no readable report"
                if leg is None
                else f"{leg.tests} tests, "
                f"{leg.count('failed')} failed, {leg.count('error')} errors"
            )
        )
    print(f"STATE: {state}")
    print(f"REASON: {reason}")
    return 0 if state == CAUGHT else 3


if __name__ == "__main__":
    sys.exit(main())
