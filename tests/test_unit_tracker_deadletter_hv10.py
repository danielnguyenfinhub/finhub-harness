"""Proof for HV10: the dead-letter step and convergence loop rules (C1-C5) of unit_tracker.py.

adapted from references/hive/core/framework/host/playbook/runner.py:57 and :305 (Apache-2.0), ideas only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/finhub-harness/scripts/unit_tracker.py"
DOC = ROOT / "skills/finhub-harness/references/unit-tracker.md"


def run(*args: str, stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )
    return p.returncode, p.stdout


@pytest.fixture
def job(tmp_path: Path) -> str:
    db = str(tmp_path / "t.db")
    code, out = run(
        "init", db, "--table", "sweep", "--key", "lender", "--cols", "rate",
        "--done", "checked_at", "--seed", "-", stdin="A\nB\nC\n",
    )  # fmt: skip
    assert code == 0, out
    return db


def done(db: str, lender: str) -> None:
    row = json.dumps({"lender": lender, "checked_at": "2026-11-07"})
    assert run("upsert", db, "--table", "sweep", "--row", row)[0] == 0


def dead(db: str, reason: str = "gave up after 3 rounds") -> tuple[int, str]:
    return run("deadletter", db, "--table", "sweep", "--reason", reason)


def test_deadletter_records_every_open_unit_and_only_those(job: str) -> None:
    done(job, "A")
    code, out = dead(job)
    assert code == 0 and "DEAD-LETTERED: 2" in out, "C3: the two open units are recorded"
    assert (
        '"lender": "B"' in out and '"lender": "C"' in out and '"lender": "A"' not in out
    ), "C3: a done unit is never dead-lettered"


def test_a_second_deadletter_records_nothing_and_exits_3(job: str) -> None:
    assert dead(job)[0] == 0
    code, out = dead(job)
    assert (
        code == 3 and "DEAD-LETTERED: 0" in out and "DEAD:" not in out
    ), "C4: leftover units are recorded once, not once per call"


def test_dead_units_leave_pending_and_the_loop_converges(job: str) -> None:
    done(job, "A")
    assert dead(job)[0] == 0
    code, out = run("pending", job, "--table", "sweep")
    assert (
        code == 3 and "PENDING: 0" in out and '"lender"' not in out
    ), "C5: a dead unit is not pending, so a re-run of the loop does not pick it up"


def test_status_reports_failed_separately_from_done(job: str) -> None:
    done(job, "A")
    dead(job)
    out = run("status", job, "--table", "sweep")[1]
    assert (
        "DONE: 1" in out and "FAILED: 2" in out and "PENDING: 0" in out
    ), "C3: FAILED is counted on its own and not as done"
    assert "STATE: stopped-with-failures" in out, "C5: nothing open but some given up on"


def test_status_without_failures_has_no_failed_line(job: str) -> None:
    assert "FAILED" not in run("status", job, "--table", "sweep")[1], "existing output unchanged"


def test_the_reason_is_stored_with_the_unit(job: str) -> None:
    dead(job, "lender site down")
    import sqlite3

    rows = sqlite3.connect(job).execute('SELECT "_failed" FROM sweep').fetchall()
    assert {r[0] for r in rows} == {"lender site down"}, "C3: the reason travels with the row"


def test_a_blank_reason_is_refused(job: str) -> None:
    code, out = dead(job, "  ")
    assert code == 2 and "REFUSED" in out, "C3: say why the units were given up on"
    assert "PENDING: 3" in run("status", job, "--table", "sweep")[1], "nothing recorded on refusal"


def test_reference_carries_the_loop_rules() -> None:
    text = DOC.read_text(encoding="utf-8")
    for needle in (
        "| C1 |",
        "| C2 |",
        "| C3 |",
        "| C4 |",
        "| C5 |",
        "`deadletter DB --table T --reason TEXT`",
        "failure-fraction",
    ):
        assert needle in text, f"the reference must carry {needle!r}"
