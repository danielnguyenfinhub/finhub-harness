# Unit tracker: resuming a bulk job at the row

> The registry of writable columns, the key columns that make a write idempotent, the refusal of unregistered and reserved tables, and the done-predicate column are adapted from references/hive/core/framework/tools/tracker_tools.py:1-31 and :743-787 and references/hive/core/framework/agents/queen/nodes/__init__.py:359-365 (Apache-2.0). "What is left is always a fresh query, so a re-run resumes" is adapted from references/hive/core/framework/host/playbook/runner.py:1-20 (Apache-2.0).

`state-ledger.md` resumes a run at the phase. A bulk job, where one phase does the same work for N items (check 40 lenders, review 200 clients), needs a finer record: which item is done. `scripts/unit_tracker.py` keeps that record in one SQLite file, one row per item, and answers "what is left" by asking the table, never by remembering.

## 1. When to use it

Use it when a harness has one phase that repeats the same work over many items and the items can be named by a stable key. Do not use it for a single deliverable or for work with no item list. Chat and Cowork have no shell, so there the orchestrator keeps the same table as a list in its reply and says the script was not run: unverified.

## 2. Commands

Run from the project root. `DB` is a file path such as `_workspace/units.db`.

| Command | What it does |
|---------|--------------|
| `init DB --table T --key a[,b] --cols c,d --done COL [--seed FILE\|-]` | Makes the table and registers it. `--seed` adds one pending row per line (tab-separated for a multi-column key). Safe to run again. |
| `upsert DB --table T --row JSON` | Writes one row by key. Setting the done column marks the unit done; setting it to null reopens it. |
| `pending DB --table T [--limit N]` | Prints each undone row as a JSON line, then `PENDING: n`. Exit 3 when none is left. |
| `status DB --table T` | Prints `TOTAL`, `DONE`, `PENDING` and `STATE: open` or `converged`. |

Exit 0 ok; 3 nothing pending; 2 usage error or a refused write (`REFUSED: ...` on stdout).

Example, with synthetic names: `init DB --table sweep --key lender --cols rate,note --done checked_at --seed lenders.txt`, then each worker runs `upsert DB --table sweep --row '{"lender":"LenderA","rate":"6.19","checked_at":"2026-10-18"}'`, and the orchestrator loops on `pending` until it exits 3. The script does not read dates; the caller writes them.

## 3. Rules

| Id | Rule |
|----|------|
| U1 | A seed key becomes exactly one pending row. A done column that is NULL means pending; any value means done. |
| U2 | `init` run again never resets a done row and never overwrites data. It adds keys that are new. |
| U3 | `pending` lists only undone rows, and exits 3 when none is left. The answer is a fresh query each time. |
| U4 | `upsert` is idempotent on the key columns: the same key written twice is one row and the last write wins. A re-dispatched worker cannot create a duplicate. |
| U5 | Setting the done column to null reopens the unit. This is how a row that failed a check is cleared and sent back. |
| U6 | A write may carry only the registered key, `--cols` and done columns, and must carry every key column. Lists and objects are stored as JSON text. |
| U7 | Only tables made by `init` accept writes. Names must be letters, digits and underscores starting with a letter, so the script's own table (`_unit_registry`) and any name with SQL in it are refused. |
| U8 | A table cannot be redefined by a later `init` with a different key, columns or done column, and a read command on a missing file does not create one. |

## 4. How it fits with the rest

Phase level: `state_ledger.py` says where the run resumes. Row level: this script says which items inside that phase are left. An orchestrator that uses both keeps the tracker file under `_workspace/` and names it in the Handoff files table of its plan.

Does not cover:

- Workers writing at the same moment: SQLite serialises them and a busy file waits at most five seconds, then the write is refused. There is no worker identity, budget or claim, so two workers can take the same row. Give each worker a different slice, or run them one at a time.
- Retry, backoff, a failure-rate stop and a list of rows that never finish: a script does not run workers. They belong to the runtime (candidate H3 in `docs/hive-adoption-proposal.md`).
- Checking that a done row is true: the tracker records that an item was marked done, not that the result is right. A verification gate is candidate H4.
- Edits to the SQLite file made outside the script.
