"""Lead 12: a dead-lettered unit is retired from the claim queue as well as from pending."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
