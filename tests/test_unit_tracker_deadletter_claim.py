"""Lead 12: a dead-lettered unit is retired from the claim queue as well as from pending."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/finhub-harness/scripts/unit_tracker.py"


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )
    return p.returncode, p.stdout


def make(tmp_path: Path, ids: str = "a\nb\n") -> str:
    db = str(tmp_path / "t.db")
    seed = tmp_path / "seed.tsv"
    seed.write_text(ids)
    rc, out = run("init", db, "--table", "T", "--key", "id", "--cols", "x", "--done", "d",
                  "--seed", str(seed))  # fmt: skip
    assert rc == 0, out
    return db


def test_claim_skips_dead_lettered_and_reaches_none_left(tmp_path: Path) -> None:
    db = make(tmp_path)
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    rc, out = run("claim", db, "--table", "T", "--worker", "w1")
    assert (rc, out.strip()) == (3, "CLAIM: none-left")


def test_dead_lettered_released_unit_is_not_handed_out_again(tmp_path: Path) -> None:
    db = make(tmp_path, "a\n")
    assert run("claim", db, "--table", "T", "--worker", "w1")[0] == 0
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    assert run("release", db, "--table", "T", "--worker", "w1", "--key", '{"id":"a"}')[0] == 0
    assert run("claim", db, "--table", "T", "--worker", "w1")[0] == 3


def test_claim_picks_live_unit_before_and_after_dead_one(tmp_path: Path) -> None:
    db = make(tmp_path, "a\n")
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    assert run("upsert", db, "--table", "T", "--row", '{"id":"b"}')[0] == 0
    rc, out = run("claim", db, "--table", "T", "--worker", "w1")
    assert rc == 0 and '"id": "b"' in out


def test_claim_key_on_dead_lettered_unit_is_typed_refusal(tmp_path: Path) -> None:
    db = make(tmp_path)
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    rc, out = run("claim", db, "--table", "T", "--worker", "w1", "--key", '{"id":"a"}')
    assert (rc, out.strip()) == (4, "CLAIM: dead-lettered")


def test_claim_key_outcomes_unchanged(tmp_path: Path) -> None:
    db = make(tmp_path)
    assert run("claim", db, "--table", "T", "--worker", "w1", "--key", '{"id":"a"}')[0] == 0
    out = run("claim", db, "--table", "T", "--worker", "w2", "--key", '{"id":"a"}')
    assert out == (4, "CLAIM: owned-by-other\n")
    out = run("claim", db, "--table", "T", "--worker", "w2", "--key", '{"id":"zz"}')
    assert out == (4, "CLAIM: not-found\n")


# ---- re-audit: the first deadletter of a table must not race a claim ----


def load() -> Any:
    spec = importlib.util.spec_from_file_location("unit_tracker_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_claim_builds_guard_after_failed_column_exists_even_if_deadletter_lands_between(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Deadletter runs right after the claim built its guard (the first-ever deadletter)."""
    db = make(tmp_path, "a\nb\n")
    ut = load()
    real, fired = ut._open_where, []

    def hooked(con: sqlite3.Connection, table: str, done: str) -> str:
        guard = real(con, table, done)
        if not fired:
            fired.append(1)
            ut._deadletter(argparse.Namespace(db=db, table="T", reason="poison"))
        return guard

    monkeypatch.setattr(ut, "_open_where", hooked)
    rc = ut._claim(argparse.Namespace(db=db, table="T", worker="w1", key=None))
    out = capsys.readouterr().out
    assert fired and rc == 3 and "none-left" in out, out
    rows = sqlite3.connect(db).execute('SELECT "_failed", "_claimed_by" FROM T').fetchall()
    assert all(f is not None and c is None for f, c in rows), rows


def _racer(db: str, role: str, gate: Any, q: Any) -> None:
    import contextlib
    import io

    ut = load()
    gate.wait()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if role == "dead":
            ut.main(["deadletter", db, "--table", "T", "--reason", "poison"])
        else:
            ut.main(["claim", db, "--table", "T", "--worker", role])
    q.put((role, buf.getvalue()))


def test_six_claimers_racing_the_first_deadletter_never_claim_a_dead_unit(tmp_path: Path) -> None:
    ctx = mp.get_context("fork")
    for trial in range(25):
        (tmp_path / f"t{trial}").mkdir()
        db = make(tmp_path / f"t{trial}", "\n".join("abcdefgh") + "\n")
        gate, q = ctx.Barrier(7), ctx.Queue()
        roles = [f"w{i}" for i in range(6)] + ["dead"]
        procs = [ctx.Process(target=_racer, args=(db, r, gate, q)) for r in roles]
        for p in procs:
            p.start()
        outs = dict(q.get(timeout=60) for _ in procs)
        for p in procs:
            p.join(60)
        shown = {}
        for line in outs["dead"].splitlines():
            if line.startswith("DEAD: {"):
                row = json.loads(line[6:])
                shown[row["id"]] = row.get("_claimed_by")
        final = dict(
            sqlite3.connect(db).execute(
                'SELECT id, "_claimed_by" FROM T WHERE "_failed" IS NOT NULL'
            )
        )
        for uid, who in shown.items():
            assert final[uid] == who, (trial, uid, who, final[uid])  # claimed only before dead


# ---- re-audit: a dead unit is not writable either ----


def test_upsert_worker_on_dead_unit_is_refused_and_status_stays_consistent(tmp_path: Path) -> None:
    db = make(tmp_path, "a\nb\nc\n")
    assert run("claim", db, "--table", "T", "--worker", "w1", "--key", '{"id":"a"}')[0] == 0
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    rc, out = run("upsert", db, "--table", "T", "--row", '{"id":"a","d":"x"}', "--worker", "w1")
    assert (rc, out.strip()) == (4, "UPSERT: dead-lettered")
    rc, out = run("status", db, "--table", "T")
    assert "DONE: 0\n" in out and "PENDING: 0\n" in out and "FAILED: 3\n" in out, out
    got = sqlite3.connect(db).execute("SELECT d FROM T WHERE id = 'a'").fetchone()
    assert got == (None,)


def test_plain_upsert_on_dead_unit_is_refused_but_live_units_still_write(tmp_path: Path) -> None:
    db = make(tmp_path, "a\n")
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    assert run("upsert", db, "--table", "T", "--row", '{"id":"a","d":"x"}') == (
        4,
        "UPSERT: dead-lettered\n",
    )
    assert run("upsert", db, "--table", "T", "--row", '{"id":"b","d":"x"}')[0] == 0
    assert run("upsert", db, "--table", "T", "--row", '{"id":"b","x":"y"}')[0] == 0


def test_dead_unit_cannot_be_reopened_by_null_done(tmp_path: Path) -> None:
    db = make(tmp_path, "a\n")
    assert run("deadletter", db, "--table", "T", "--reason", "poison")[0] == 0
    assert run("upsert", db, "--table", "T", "--row", '{"id":"a","d":null}')[0] == 4
    assert run("claim", db, "--table", "T", "--worker", "w1")[0] == 3
