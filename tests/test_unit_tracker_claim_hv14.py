"""Proof for HV14: the atomic claim of skills/finhub-harness/scripts/unit_tracker.py.

Rules U9-U11 of references/unit-tracker.md. Each assertion message names the rule it guards.
adapted from references/hive/core/framework/skills/_default_skills/colony-progress-tracker/SKILL.md:16
and :32 and references/hive/core/framework/tasks/store.py:806 (Apache-2.0), ideas only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/finhub-harness/scripts/unit_tracker.py"


def cmd(*args: str) -> list[str]:
    return [sys.executable, "-B", str(SCRIPT), *args]


def run(*args: str, stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd(*args), capture_output=True, text=True, input=stdin, check=False)
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


def claim(db: str, worker: str, key: str | None = None) -> tuple[int, str]:
    extra = ["--key", json.dumps({"lender": key})] if key else []
    return run("claim", db, "--table", "sweep", "--worker", worker, *extra)


def test_claim_takes_the_next_unclaimed_unit_in_order(job: str) -> None:
    code, out = claim(job, "w1")
    assert code == 0 and out.startswith("CLAIM: ok") and '"lender": "A"' in out, "U9: first claim"
    code, out = claim(job, "w2")
    assert (
        code == 0 and '"lender": "B"' in out
    ), "U9: a claimed unit is not given to a second worker"


def test_claims_run_out_with_exit_3(job: str) -> None:
    for w in ("w1", "w2", "w3"):
        assert claim(job, w)[0] == 0
    code, out = claim(job, "w4")
    assert code == 3 and out.strip() == "CLAIM: none-left", "U9: nothing unclaimed is exit 3"


def test_claiming_a_named_unit_owned_by_another_is_refused(job: str) -> None:
    assert claim(job, "w1", "B")[0] == 0
    code, out = claim(job, "w2", "B")
    assert code == 4 and out.strip() == "CLAIM: owned-by-other", "U10: typed owned-by-other"


def test_claiming_my_own_unit_again_is_ok(job: str) -> None:
    assert claim(job, "w1", "B")[0] == 0
    assert claim(job, "w1", "B")[0] == 0, "U10: re-claim by the owner is idempotent"


def test_unknown_unit_is_not_found(job: str) -> None:
    code, out = claim(job, "w1", "Z")
    assert code == 4 and out.strip() == "CLAIM: not-found", "U10: typed not-found"


def test_a_done_unit_cannot_be_claimed(job: str) -> None:
    row = json.dumps({"lender": "A", "checked_at": "2026-11-07"})
    assert run("upsert", job, "--table", "sweep", "--row", row)[0] == 0
    code, out = claim(job, "w1", "A")
    assert code == 4 and out.strip() == "CLAIM: already-done", "U10: typed already-done"


def test_release_returns_the_unit_and_only_for_its_owner(job: str) -> None:
    assert claim(job, "w1", "A")[0] == 0
    key = json.dumps({"lender": "A"})
    code, out = run("release", job, "--table", "sweep", "--worker", "w2", "--key", key)
    assert code == 4 and out.strip() == "RELEASE: not-held", "U10: a non-owner cannot release"
    code, out = run("release", job, "--table", "sweep", "--worker", "w1", "--key", key)
    assert code == 0 and out.strip() == "RELEASE: ok", "U10: the owner releases"
    assert claim(job, "w2", "A")[0] == 0, "U10: a released unit can be claimed again"


def test_a_write_with_worker_needs_the_claim(job: str) -> None:
    row = json.dumps({"lender": "A", "rate": "6.1"})
    code, out = run("upsert", job, "--table", "sweep", "--row", row, "--worker", "w1")
    assert code == 2 and "claim" in out, "U11: no claim, no write"
    assert claim(job, "w1", "A")[0] == 0
    assert (
        run("upsert", job, "--table", "sweep", "--row", row, "--worker", "w2")[0] == 2
    ), "U11: a claim held by another worker blocks the write"
    assert (
        run("upsert", job, "--table", "sweep", "--row", row, "--worker", "w1")[0] == 0
    ), "U11: the holder writes"


def test_a_write_without_worker_is_unchanged(job: str) -> None:
    row = json.dumps({"lender": "A", "rate": "6.1"})
    assert run("upsert", job, "--table", "sweep", "--row", row)[0] == 0, "U11: --worker is optional"


def test_parallel_claimers_never_get_the_same_unit(tmp_path: Path) -> None:
    db = str(tmp_path / "p.db")
    seed = "".join(f"U{i}\n" for i in range(6))
    code, out = run(
        "init", db, "--table", "sweep", "--key", "lender", "--cols", "rate",
        "--done", "checked_at", "--seed", "-", stdin=seed,
    )  # fmt: skip
    assert code == 0, out
    procs = [
        subprocess.Popen(
            cmd("claim", db, "--table", "sweep", "--worker", f"w{i}"),
            stdout=subprocess.PIPE,
            text=True,
        )
        for i in range(12)
    ]
    outs = [p.communicate()[0] for p in procs]
    got = [json.loads(o.split(" ", 2)[2])["lender"] for o in outs if o.startswith("CLAIM: ok")]
    assert len(got) == 6 and len(set(got)) == 6, f"U9: each unit claimed exactly once, got {got}"
    assert sum(o.startswith("CLAIM: none-left") for o in outs) == 6, "U9: the rest find none left"


DOC = Path(__file__).resolve().parents[1] / "skills/finhub-harness/references/unit-tracker.md"


def test_reference_documents_the_claim_rules_and_commands() -> None:
    text = DOC.read_text(encoding="utf-8")
    for needle in (
        "| U9 |",
        "| U10 |",
        "| U11 |",
        "`claim DB --table T --worker W [--key JSON]`",
        "`release DB --table T --worker W --key JSON`",
        "4 a claim or release was not granted",
        "no sweep reclaims it",
    ):
        assert needle in text, f"the reference must carry {needle!r}"


def _module():  # type: ignore[no-untyped-def]
    import importlib.util

    spec = importlib.util.spec_from_file_location("unit_tracker_mod", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_adding_the_claim_column_twice_is_not_an_error() -> None:
    import sqlite3

    mod = _module()
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE "t" (k TEXT)')
    mod._add_column(con, '"t"', "_claimed_by")
    mod._add_column(con, '"t"', "_claimed_by")  # a second worker lost the race to add it
    assert "_claimed_by" in {
        r[1] for r in con.execute('PRAGMA table_info("t")')
    }, "U9: first claims racing to add the column must not fail"


def test_other_sql_errors_in_add_column_still_surface() -> None:
    import sqlite3

    mod = _module()
    con = sqlite3.connect(":memory:")
    with pytest.raises(sqlite3.OperationalError):
        mod._add_column(con, '"missing"', "_claimed_by")
