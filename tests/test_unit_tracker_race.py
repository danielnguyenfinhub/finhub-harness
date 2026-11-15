"""A real multi-process race for `upsert --worker` (U11): no write by a worker that does not hold the unit.

Eight processes, four worker names with two processes each (a re-dispatched worker shares its name, so
one process can release the claim the other is about to write under), hammer one unit for two seconds,
all released together by a barrier. Each process claims and writes `<name>:init` under its claim.

The detector is a trigger in the database: on every write of `d` it records a violation when the
holder at that instant is not the worker named in the text. It sits inside the write's own statement,
so nothing can slip in between the write and the check. An earlier version read the row back from
Python afterwards and compared it with the holder; that gave a false alarm when the twin process
released and re-claimed under the same name around another worker's (correctly guarded) write
(seen once in CI, 1 round in 1,246; `test_the_old_read_back_check_was_a_false_alarm` replays it).

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
            with contextlib.suppress(SystemExit):  # a refused write is the guard working
                call("upsert", db, "--table", "sweep", "--row", row, "--worker", name)
        call("release", db, "--table", "sweep", "--worker", name, "--key", KEY)
        ops += 1
    out.put(ops)


def _arm(mod: Any, db: str) -> None:
    """Adds the script-owned claim column (one claim and release), then the detector trigger."""
    for verb in ("claim", "release"):
        with contextlib.redirect_stdout(io.StringIO()):
            assert mod.main([verb, db, "--table", "sweep", "--worker", "w0", "--key", KEY]) == 0
    con = sqlite3.connect(db)
    with con:
        con.execute("CREATE TABLE race_violation (held, d)")
        con.execute(
            "CREATE TRIGGER race_detector AFTER UPDATE OF d ON sweep "
            "WHEN NEW.d IS NOT NULL AND (NEW._claimed_by IS NULL OR NEW.d != NEW._claimed_by || ':init') "
            "BEGIN INSERT INTO race_violation VALUES (NEW._claimed_by, NEW.d); END"
        )
    con.close()


def _violations(db: str) -> list[str]:
    rows = sqlite3.connect(db).execute("SELECT held, d FROM race_violation").fetchall()
    return [f"{d!r} was written while the unit was held by {held!r}" for held, d in rows]


def test_the_old_read_back_check_was_a_false_alarm(tmp_path: Path) -> None:
    """The interleaving CI hit: every step is correct, yet holder w1 sees w2's text. No violation."""
    db = str(tmp_path / "replay.db")
    mod = _load()

    def call(*argv: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                return int(mod.main(list(argv)))
            except SystemExit as stop:
                return int(stop.code or 0)

    def write(name: str) -> int:
        row = json.dumps({"id": "u1", "d": f"{name}:init"})
        return call("upsert", db, "--table", "sweep", "--row", row, "--worker", name)

    def claim(name: str) -> int:
        return call("claim", db, "--table", "sweep", "--worker", name, "--key", KEY)

    def release(name: str) -> int:
        return call("release", db, "--table", "sweep", "--worker", name, "--key", KEY)

    assert (
        call("init", db, "--table", "sweep", "--key", "id", "--cols", "d", "--done", "done_at") == 0
    )
    assert call("upsert", db, "--table", "sweep", "--row", json.dumps({"id": "u1"})) == 0
    _arm(mod, db)
    assert claim("w1") == 0  # process B
    assert release("w1") == 0  # its twin A, at the end of A's loop
    assert claim("w2") == 0
    assert write("w2") == 0
    assert write("w1") != 0, "B no longer holds the unit, so its write must be refused"
    assert release("w2") == 0
    assert claim("w1") == 0  # twin A again
    row = sqlite3.connect(db).execute("SELECT _claimed_by, d FROM sweep").fetchone()
    assert row == ("w1", "w2:init")  # what the old check called a violation
    assert _violations(db) == []


def test_eight_processes_never_write_without_the_claim(tmp_path: Path) -> None:
    db = str(tmp_path / "race.db")
    mod = _load()
    assert mod.main(["init", db, "--table", "sweep", "--key", "id", "--cols", "d",
                     "--done", "done_at"]) == 0  # fmt: skip
    assert mod.main(["upsert", db, "--table", "sweep", "--row", json.dumps({"id": "u1"})]) == 0
    _arm(mod, db)
    ctx = mp.get_context("fork")
    barrier = ctx.Barrier(8)
    out = ctx.Queue()
    procs = [ctx.Process(target=_worker, args=(NAMES[i % 4], db, barrier, out)) for i in range(8)]
    for p in procs:
        p.start()
    results = [out.get(timeout=60) for _ in procs]
    for p in procs:
        p.join(timeout=30)
    ops = sum(results)
    violations = _violations(db)
    assert ops >= 100, f"the race did not run: only {ops} rounds"
    print(f"rounds={ops} violations={len(violations)}")
    assert not violations, violations[:5]
