"""A tracker file made before key values were stored as text is migrated once, safely."""

from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TRACKER = REPO / "skills/finhub-harness/scripts/unit_tracker.py"


def run(*args: str, stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(TRACKER), *args],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )
    return p.returncode, p.stdout


def old_upsert(db: str, row: dict[str, object]) -> None:
    """Fixture writer: the old code stored the JSON value as it came (an integer stayed an integer)."""
    con = sqlite3.connect(db)
    names = list(row)
    sets = ", ".join(f'"{c}" = excluded."{c}"' for c in names if c != "id")
    with con:
        con.execute(
            f"INSERT INTO sweep ({', '.join(names)}) VALUES ({', '.join('?' * len(names))}) "
            f"ON CONFLICT (id) DO UPDATE SET {sets}",
            list(row.values()),
        )


@pytest.fixture
def old(tmp_path: Path) -> str:
    db = str(tmp_path / "old.db")
    code = run("init", db, "--table", "sweep", "--key", "id", "--cols", "d", "--done", "done_at")[0]
    assert code == 0
    return db


def rows(db: str) -> list[tuple[object, ...]]:
    q = "SELECT id, typeof(id), d, done_at FROM sweep ORDER BY rowid"
    return sqlite3.connect(db).execute(q).fetchall()


def test_integer_keys_become_text_and_are_reported(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "a"})
    old_upsert(old, {"id": 2, "d": "b", "done_at": "2026-01-01"})
    code, out = run("status", old, "--table", "sweep")
    assert code == 0
    assert "MIGRATED: 2 rows, 0 merged" in out
    assert rows(old) == [("1", "text", "a", None), ("2", "text", "b", "2026-01-01")]
    # the new code now reaches the old row by either spelling
    claim = run("claim", old, "--table", "sweep", "--worker", "w", "--key", '{"id": 1}')[1]
    assert claim.startswith("CLAIM: ok")


def test_migration_is_idempotent(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "a"})
    run("status", old, "--table", "sweep")
    before = rows(old)
    code, out = run("status", old, "--table", "sweep")
    assert "MIGRATED" not in out and rows(old) == before and code == 0


def test_a_clean_file_is_not_touched(old: str) -> None:
    assert run("upsert", old, "--table", "sweep", "--row", '{"id": 1, "d": "x"}')[0] == 0
    assert "MIGRATED" not in run("pending", old, "--table", "sweep")[1]


def test_collision_keeps_the_done_row(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "int-open"})
    old_upsert(old, {"id": "1", "d": "text-done", "done_at": "2026-01-01"})
    out = run("status", old, "--table", "sweep")[1]
    assert "MIGRATED: 1 rows, 1 merged" in out
    assert rows(old) == [("1", "text", "text-done", "2026-01-01")]


def test_collision_keeps_the_done_row_when_the_integer_one_is_done(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "int-done", "done_at": "2026-01-01"})
    old_upsert(old, {"id": "1", "d": "text-open"})
    assert "1 merged" in run("status", old, "--table", "sweep")[1]
    assert rows(old) == [("1", "text", "int-done", "2026-01-01")]


def mark_dead(db: str, where: str) -> None:
    """Old files already had the dead-letter column; set it by hand on the rows picked by `where`."""
    con = sqlite3.connect(db)
    if "_failed" not in {r[1] for r in con.execute("PRAGMA table_info(sweep)")}:
        con.execute("ALTER TABLE sweep ADD COLUMN _failed TEXT")
    con.execute(f"UPDATE sweep SET _failed = 'gave up' WHERE {where}")
    con.commit()


def test_collision_never_loses_a_dead_lettered_row(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "int-dead"})
    old_upsert(old, {"id": "1", "d": "text-done", "done_at": "2026-01-01"})
    mark_dead(old, "typeof(id) = 'integer'")
    out = run("status", old, "--table", "sweep")[1]
    assert "1 merged" in out and "FAILED: 1" in out and "STATE: stopped-with-failures" in out
    rows_ = sqlite3.connect(old).execute("SELECT d, _failed FROM sweep").fetchall()
    assert rows_ == [("int-dead", "gave up")]


def test_dead_beats_done_on_a_collision(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "int-done", "done_at": "2026-01-01"})
    old_upsert(old, {"id": "1", "d": "text-dead"})
    mark_dead(old, "typeof(id) = 'text'")
    run("status", old, "--table", "sweep")
    rows_ = sqlite3.connect(old).execute("SELECT d, _failed FROM sweep").fetchall()
    assert rows_ == [("text-dead", "gave up")]


def test_migration_keeps_a_dead_state_without_collision(old: str) -> None:
    old_upsert(old, {"id": 7, "d": "x"})
    mark_dead(old, "1")
    out = run("status", old, "--table", "sweep")[1]
    assert "MIGRATED: 1 rows, 0 merged" in out and "FAILED: 1" in out
    code, claim = run("claim", old, "--table", "sweep", "--worker", "w", "--key", '{"id": 7}')
    assert code == 4 and "dead-lettered" in claim


def test_composite_keys_migrate_every_column(tmp_path: Path) -> None:
    db = str(tmp_path / "c.db")
    run("init", db, "--table", "sweep", "--key", "a,b", "--cols", "d", "--done", "done_at")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO sweep (a, b, d) VALUES ('x', 1, 'v')")
    con.execute("INSERT INTO sweep (a, b, d) VALUES ('y', 2.5, 'w')")
    con.commit()
    assert "MIGRATED: 2 rows, 0 merged" in run("status", db, "--table", "sweep")[1]
    assert con.execute("SELECT a, b, typeof(b) FROM sweep ORDER BY rowid").fetchall() == [
        ("x", "1", "text"),
        ("y", "2.5", "text"),
    ]


def test_migration_is_one_transaction(old: str) -> None:
    """A failure half way leaves the file as it was, not half converted."""
    old_upsert(old, {"id": 1, "d": "a"})
    old_upsert(old, {"id": 2, "d": "b"})
    con = sqlite3.connect(old)
    con.execute(  # a trigger that makes the second row's rewrite fail
        "CREATE TRIGGER boom BEFORE UPDATE ON sweep WHEN OLD.id = 2 "
        "BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    con.commit()
    code, out = run("status", old, "--table", "sweep")
    assert code == 2 and "boom" in out
    assert [r[1] for r in rows(old)] == ["integer", "integer"]


def test_a_second_migrator_that_finds_nothing_left_prints_nothing(
    old: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The recheck under the lock: another process converted the rows between our look and our BEGIN."""
    old_upsert(old, {"id": 1, "d": "a"})
    spec = importlib.util.spec_from_file_location("ut_race_mod", TRACKER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    other = sqlite3.connect(old)

    def rival(sql: str) -> None:
        if sql == "BEGIN IMMEDIATE" and not other.in_transaction:
            other.execute("UPDATE sweep SET id = '1'")
            other.commit()

    con = sqlite3.connect(old)
    con.set_trace_callback(rival)
    mod._migrate_keys(con, "sweep", ["id"], "done_at")
    assert "MIGRATED" not in capsys.readouterr().out
    assert rows(old) == [("1", "text", "a", None)]


def test_two_open_rows_keep_the_one_already_stored_as_text(old: str) -> None:
    old_upsert(old, {"id": 1, "d": "int-open"})
    old_upsert(old, {"id": "1", "d": "text-open"})
    assert "1 merged" in run("status", old, "--table", "sweep")[1]
    assert rows(old) == [("1", "text", "text-open", None)]


def test_doc_has_the_migration_rule() -> None:
    doc = (REPO / "skills/finhub-harness/references/unit-tracker.md").read_text("utf-8")
    assert "| U12 |" in doc and "MIGRATED: n rows, m merged" in doc
