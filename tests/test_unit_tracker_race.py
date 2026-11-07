"""A real multi-process race for `upsert --worker` (U11): no write by a worker that does not hold the unit.

Eight processes, four worker names with two processes each (a re-dispatched worker shares its name, so
one process can release the claim the other is about to write under), hammer one unit for two seconds,
all released together by a barrier. Each process claims, writes `<name>:init` under its claim, reads the
row back in one statement and, if it still holds the claim but the row carries someone else's text,
reports a violation: a write got through without the claim.

`UT_RACE_MODULE` points the test at another copy of the script (used to run it against the logic that
read the holder in a separate statement, see CLAUDE.md); by default it runs the real script.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import multiprocessing as mp
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
TRACKER = Path(
    os.environ.get("UT_RACE_MODULE", REPO / "skills/finhub-harness/scripts/unit_tracker.py")
)
KEY = json.dumps({"id": "u1"})
NAMES = ["w1", "w2", "w3", "w4"]
SECONDS = 2.0


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("ut_race_worker", TRACKER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _worker(name: str, db: str, barrier: Any, out: Any) -> None:
    mod = _load()
    watch = sqlite3.connect(db, timeout=10)
    bad: list[str] = []
    ops = 0

    def call(*argv: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main(list(argv))
        return buf.getvalue()

    barrier.wait()
    end = time.monotonic() + SECONDS
    while time.monotonic() < end:
        if call("claim", db, "--table", "sweep", "--worker", name, "--key", KEY).startswith(
            "CLAIM: ok"
        ):
            row = json.dumps({"id": "u1", "d": f"{name}:init"})
            call("upsert", db, "--table", "sweep", "--row", row, "--worker", name)
            held, d = watch.execute("SELECT _claimed_by, d FROM sweep").fetchone()
            if held == name and d is not None and d != f"{name}:init":
                bad.append(f"{name} holds the unit but the row says {d!r}")
        call("release", db, "--table", "sweep", "--worker", name, "--key", KEY)
        ops += 1
    out.put((ops, bad))


def test_eight_processes_never_write_without_the_claim(tmp_path: Path) -> None:
    db = str(tmp_path / "race.db")
    mod = _load()
    assert mod.main(["init", db, "--table", "sweep", "--key", "id", "--cols", "d",
                     "--done", "done_at"]) == 0  # fmt: skip
    assert mod.main(["upsert", db, "--table", "sweep", "--row", json.dumps({"id": "u1"})]) == 0
    ctx = mp.get_context("fork")
    barrier = ctx.Barrier(8)
    out = ctx.Queue()
    procs = [ctx.Process(target=_worker, args=(NAMES[i % 4], db, barrier, out)) for i in range(8)]
    for p in procs:
        p.start()
    results = [out.get(timeout=60) for _ in procs]
    for p in procs:
        p.join(timeout=30)
    ops = sum(r[0] for r in results)
    violations = [v for r in results for v in r[1]]
    assert ops >= 100, f"the race did not run: only {ops} rounds"
    print(f"rounds={ops} violations={len(violations)}")
    assert not violations, violations[:5]
