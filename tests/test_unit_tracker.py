"""Proof for H1: skills/finhub-harness/scripts/unit_tracker.py, one row per unit of a bulk job.

Each assertion message states the rule it guards (U1-U8 in references/unit-tracker.md), so a
mutant that breaks a rule fails with that message. Behaviour adapted from
references/hive/core/framework/tools/tracker_tools.py:1-31 and :743-787 (Apache-2.0)."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/finhub-harness/scripts/unit_tracker.py"


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
        "init", db, "--table", "sweep", "--key", "lender", "--cols", "rate,note",
        "--done", "checked_at", "--seed", "-", stdin="A\nB\nC\n",
    )  # fmt: skip
    assert code == 0, f"init must succeed: {out}"
    return db


def upsert(db: str, **row: object) -> tuple[int, str]:
    return run("upsert", db, "--table", "sweep", "--row", json.dumps(row))


def test_seed_makes_every_unit_pending(job: str) -> None:
    out = run("status", job, "--table", "sweep")[1]
    assert "TOTAL: 3" in out and "PENDING: 3" in out, "U1: a seed key must become one pending row"


def test_rerun_never_resets_a_done_row(job: str, tmp_path: Path) -> None:
    upsert(job, lender="A", rate="6.19", checked_at="2026-10-18")
    seed = tmp_path / "seed.txt"
    seed.write_text("A\nB\nC\nD\n", encoding="utf-8")
    code, out = run(
        "init", job, "--table", "sweep", "--key", "lender", "--cols", "rate,note",
        "--done", "checked_at", "--seed", str(seed),
    )  # fmt: skip
    assert code == 0 and "TOTAL: 4" in out, "U2: init run again must add the new key"
    assert "DONE: 1" in out, "U2: init run again must not reset a done row"
    row = sqlite3.connect(job).execute("SELECT rate FROM sweep WHERE lender='A'").fetchone()
    assert row == ("6.19",), "U2: init run again must keep the data of a done row"


def test_pending_lists_only_undone_and_exits_3_when_converged(job: str) -> None:
    upsert(job, lender="A", checked_at="x")
    code, out = run("pending", job, "--table", "sweep")
    names = [json.loads(ln)["lender"] for ln in out.splitlines() if ln.startswith("{")]
    assert code == 0 and names == ["B", "C"], f"U3: pending must list only undone rows, got {names}"
    for k in ("B", "C"):
        upsert(job, lender=k, checked_at="x")
    code, out = run("pending", job, "--table", "sweep")
    assert code == 3 and "PENDING: 0" in out, "U3: pending must exit 3 when no unit is left"


def test_upsert_is_idempotent_on_the_key(job: str) -> None:
    for rate in ("6.1", "6.2"):
        assert upsert(job, lender="A", rate=rate)[0] == 0, "U4: a repeated upsert must succeed"
    rows = (
        sqlite3.connect(job).execute("SELECT lender, rate FROM sweep WHERE lender='A'").fetchall()
    )
    assert rows == [("A", "6.2")], f"U4: one row per key, last write wins, got {rows}"


def test_setting_done_to_null_reopens_the_unit(job: str) -> None:
    upsert(job, lender="A", checked_at="x")
    upsert(job, lender="A", checked_at=None)
    assert (
        "PENDING: 3" in run("status", job, "--table", "sweep")[1]
    ), "U5: a null done column reopens"


@pytest.mark.parametrize(
    ("row", "needle", "why"),
    [
        ({"lender": "A", "bogus": 1}, "not allowed", "U6: a column outside the set is refused"),
        ({"rate": "6.1"}, "missing key", "U6: a row without its key column is refused"),
    ],
)
def test_bad_rows_are_refused(job: str, row: dict[str, object], needle: str, why: str) -> None:
    code, out = upsert(job, **row)
    assert code == 2 and "REFUSED" in out and needle in out, f"{why}; got {code} {out!r}"


def test_only_tables_made_by_init_accept_writes(job: str) -> None:
    for table in ("other", "_unit_registry", "sweep; DROP TABLE sweep"):
        code, out = run("upsert", job, "--table", table, "--row", '{"lender": "A"}')
        assert code == 2 and "REFUSED" in out, f"U7: table {table!r} must be refused"
    assert "TOTAL: 3" in run("status", job, "--table", "sweep")[1], "U7: nothing may be dropped"


def test_a_missing_database_is_not_created(tmp_path: Path) -> None:
    db = tmp_path / "typo.db"
    code = run("status", str(db), "--table", "sweep")[0]
    assert code == 2 and not db.exists(), "U8: a read command must not create a database"


def test_changed_shape_is_refused(job: str) -> None:
    code, out = run(
        "init", job, "--table", "sweep", "--key", "lender", "--cols", "other",
        "--done", "checked_at",
    )  # fmt: skip
    assert code == 2 and "different shape" in out, "U8: init must not redefine a table"


def test_lists_are_stored_as_json_text(job: str) -> None:
    upsert(job, lender="A", note=["x", "y"])
    got = sqlite3.connect(job).execute("SELECT note FROM sweep WHERE lender='A'").fetchone()
    assert got == ('["x", "y"]',), "U6: a list value must be stored as JSON text"
