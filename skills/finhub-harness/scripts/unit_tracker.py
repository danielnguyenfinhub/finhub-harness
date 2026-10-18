"""Keep one row per unit of a bulk job in a SQLite file, so a re-run resumes at the row.

Usage, run from the project root:
  unit_tracker.py init DB --table T --key a[,b] --cols c,d --done COL [--seed FILE|-]
  unit_tracker.py upsert DB --table T --row JSON
  unit_tracker.py pending DB --table T [--limit N]
  unit_tracker.py status DB --table T
Exit 0 ok; 3 `pending` found no unit left (the job has converged); 2 usage error or a refused write.

A unit is a row. The done column is NULL until the unit is complete; any value in it means done,
and an upsert that sets it back to null reopens the unit. "What is left" is a fresh query of the
table every time, so the script keeps no memory of its own and `init` run again never resets a
done row. Only tables made by `init` accept writes, only the columns it named, and names that
start with an underscore belong to the script.
Rules U1-U8 are in skills/finhub-harness/references/unit-tracker.md.
The registry of writable tables and columns, the key columns that make a write idempotent, the
refusal of framework-owned and unregistered tables, and the done-predicate column are adapted from
references/hive/core/framework/tools/tracker_tools.py:1-31 and :743-787 and
references/hive/core/framework/agents/queen/nodes/__init__.py:359-365 (Apache-2.0).
That "what is left" is always a fresh query, and that a re-run therefore resumes, is adapted from
references/hive/core/framework/host/playbook/runner.py:1-20 (Apache-2.0).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")  # no leading underscore: those names are ours
REGISTRY = "_unit_registry"


class Refused(Exception):
    """A request the script will not carry out; printed as REFUSED and exit 2."""


def _ident(name: str, what: str) -> str:
    if not IDENT.match(name):
        raise Refused(
            f"{what} {name!r} must be letters, digits and underscores, starting with a letter"
        )
    return '"' + name + '"'


def _names(raw: str, what: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts or len(set(parts)) != len(parts):
        raise Refused(f"{what} needs one or more distinct names, got {raw!r}")
    for p in parts:
        _ident(p, what)
    return parts


def _open(db: str, create: bool) -> sqlite3.Connection:
    if not create and not os.path.isfile(db):
        raise Refused(f"{db} does not exist; run init first")
    con = sqlite3.connect(db)
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {REGISTRY} (table_name TEXT PRIMARY KEY, "
        "key_columns TEXT NOT NULL, write_columns TEXT NOT NULL, done_column TEXT NOT NULL)"
    )
    return con


def _registered(con: sqlite3.Connection, table: str) -> tuple[list[str], list[str], str]:
    _ident(table, "table")
    row = con.execute(
        f"SELECT key_columns, write_columns, done_column FROM {REGISTRY} WHERE table_name = ?",
        (table,),
    ).fetchone()
    if row is None:
        raise Refused(f"table {table!r} was not made by init; nothing may write to it")
    return json.loads(row[0]), json.loads(row[1]), row[2]


def _init(args: argparse.Namespace) -> int:
    key, cols = _names(args.key, "--key"), _names(args.cols, "--cols")
    done = _names(args.done, "--done")
    if len(done) != 1 or done[0] in key or done[0] in cols:
        raise Refused("--done must be one column that is neither a key nor in --cols")
    q = _ident(args.table, "table")
    con = _open(args.db, create=True)
    with con:
        have = con.execute(
            f"SELECT key_columns, write_columns, done_column FROM {REGISTRY} WHERE table_name = ?",
            (args.table,),
        ).fetchone()
        shape = (json.dumps(key), json.dumps(cols), done[0])
        if have is not None and tuple(have) != shape:
            raise Refused(f"table {args.table!r} already exists with a different shape")
        every = [*key, *cols, done[0]]
        con.execute(
            f"CREATE TABLE IF NOT EXISTS {q} ({', '.join(_ident(c, 'column') for c in every)}, "
            f"PRIMARY KEY ({', '.join(_ident(k, 'column') for k in key)}))"
        )
        con.execute(f"INSERT OR IGNORE INTO {REGISTRY} VALUES (?, ?, ?, ?)", (args.table, *shape))
        if args.seed:
            lines = sys.stdin.read() if args.seed == "-" else Path(args.seed).read_text("utf-8")
            for line in lines.splitlines():
                if not line.strip():
                    continue
                vals = line.split("\t")
                if len(vals) != len(key):
                    raise Refused(f"seed line {line!r} has {len(vals)} fields, expected {len(key)}")
                marks = ", ".join("?" * len(key))
                names = ", ".join(_ident(k, "column") for k in key)
                con.execute(f"INSERT OR IGNORE INTO {q} ({names}) VALUES ({marks})", vals)
    return _status(args)


def _upsert(args: argparse.Namespace) -> int:
    con = _open(args.db, create=False)
    key, cols, done = _registered(con, args.table)
    try:
        row = json.loads(args.row)
    except json.JSONDecodeError as exc:
        raise Refused(f"--row is not JSON: {exc}") from exc
    if not isinstance(row, dict) or not row:
        raise Refused("--row must be a non-empty JSON object of column to value")
    allowed = {*key, *cols, done}
    unknown = sorted(c for c in row if c not in allowed)
    if unknown:
        raise Refused(f"columns not allowed: {unknown}; allowed: {sorted(allowed)}")
    missing = [k for k in key if k not in row]
    if missing:
        raise Refused(f"row is missing key columns {missing}")
    names = list(row)
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in row.values()]
    marks = ", ".join("?" * len(names))
    sets = [c for c in names if c not in key]
    tail = (
        "DO UPDATE SET "
        + ", ".join(f'{_ident(c, "column")} = excluded.{_ident(c, "column")}' for c in sets)
        if sets
        else "DO NOTHING"
    )
    with con:
        con.execute(
            f"INSERT INTO {_ident(args.table, 'table')} ({', '.join(_ident(c, 'column') for c in names)}) "
            f"VALUES ({marks}) ON CONFLICT ({', '.join(_ident(k, 'column') for k in key)}) {tail}",
            vals,
        )
    print("OK " + json.dumps({k: row[k] for k in key}, sort_keys=True))
    return 0


def _counts(con: sqlite3.Connection, table: str, done: str) -> tuple[int, int]:
    q, d = _ident(table, "table"), _ident(done, "column")
    total, left = con.execute(f"SELECT COUNT(*), COALESCE(SUM({d} IS NULL), 0) FROM {q}").fetchone()
    return total, left


def _pending(args: argparse.Namespace) -> int:
    con = _open(args.db, create=False)
    _, _, done = _registered(con, args.table)
    con.row_factory = sqlite3.Row
    sql = f"SELECT * FROM {_ident(args.table, 'table')} WHERE {_ident(done, 'column')} IS NULL ORDER BY rowid"
    rows = con.execute(
        sql + (" LIMIT ?" if args.limit else ""), (args.limit,) if args.limit else ()
    ).fetchall()
    for r in rows:
        print(json.dumps(dict(r), sort_keys=True))
    _, left = _counts(con, args.table, done)
    print(f"PENDING: {left}")
    return 0 if left else 3


def _status(args: argparse.Namespace) -> int:
    con = _open(args.db, create=False)
    _, _, done = _registered(con, args.table)
    total, left = _counts(con, args.table, done)
    print(f"TABLE: {args.table}\nTOTAL: {total}\nDONE: {total - left}\nPENDING: {left}")
    print("STATE: " + ("converged" if total and not left else "open"))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="unit_tracker.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "upsert", "pending", "status"):
        p = sub.add_parser(name)
        p.add_argument("db")
        p.add_argument("--table", required=True)
        if name == "init":
            p.add_argument("--key", required=True)
            p.add_argument("--cols", required=True)
            p.add_argument("--done", required=True)
            p.add_argument("--seed")
        if name == "upsert":
            p.add_argument("--row", required=True)
        if name == "pending":
            p.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    try:
        return {"init": _init, "upsert": _upsert, "pending": _pending, "status": _status}[args.cmd](
            args
        )
    except (Refused, sqlite3.Error, OSError) as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    try:
        code = main(sys.argv[1:])
        if sys.stdout is not None:  # closed with >&-: print did nothing, so flush has nothing
            sys.stdout.flush()
    except BrokenPipeError:  # the reader hung up (| head -1): not a fault of ours
        sys.stdout = None  # so the exit-time flush cannot fail again
        code = 141  # 128 + SIGPIPE, the status a shell reports for a writer whose pipe closed
    sys.exit(code)
