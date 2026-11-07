"""`stopped-with-failures` is not success: the tracker docs and the script's own text say so."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = (REPO / "skills/finhub-harness/references/unit-tracker.md").read_text("utf-8")
SCRIPT = (REPO / "skills/finhub-harness/scripts/unit_tracker.py").read_text("utf-8")


def c_rule(n: int) -> str:
    m = re.search(rf"^\| C{n} \|.*$", DOC, re.MULTILINE)
    assert m, f"C{n} missing"
    return m.group(0)


def test_only_converged_is_success() -> None:
    assert "Only `STATE: converged` is success" in DOC
    assert "`STATE: stopped-with-failures` is not" in DOC


def test_the_failed_stop_report_lists_units_and_never_marks_the_phase_done() -> None:
    para = DOC[DOC.index("Only `STATE: converged` is success") :]
    para = para.split("\n\n")[0]
    assert "lists every failed unit with its reason" in para
    assert "never marks the phase done" in para


def test_exit_3_is_not_read_as_success() -> None:
    assert "always read `status` before reporting" in DOC
    assert "says nothing yet about success" in c_rule(2)


def test_the_status_row_marks_converged_as_the_only_success() -> None:
    row = next(ln for ln in DOC.splitlines() if ln.startswith("| `status DB"))
    assert "the only success" in row and "not success" in row


def test_the_script_text_no_longer_says_exit_3_means_converged() -> None:
    assert "(the job has converged)" not in SCRIPT
    assert "only `STATE: converged` means every unit is done" in SCRIPT
    assert "converged means every unit is done, none given up on" not in SCRIPT
