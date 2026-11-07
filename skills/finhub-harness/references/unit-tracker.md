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
| `status DB --table T` | Prints `TOTAL`, `DONE`, `PENDING` (and `FAILED` when a unit was dead-lettered) and `STATE: open`, `converged` (every unit done) or `stopped-with-failures` (nothing open, some unit given up on). |
| `claim DB --table T --worker W [--key JSON]` | Takes the next unit nobody holds, or the unit named by `--key` (a JSON object with exactly the key columns). Prints `CLAIM: ok <row>` or a typed outcome. A dead-lettered unit is never claimable (`CLAIM: dead-lettered` for `--key`). |
| `release DB --table T --worker W --key JSON` | Gives a unit back; only its holder can. Prints `RELEASE: ok` or `RELEASE: not-held`. |
| `deadletter DB --table T --reason TEXT` | Records every unit still open as failed, with the reason, once. Prints each as `DEAD: <row>` and `DEAD-LETTERED: n`; exit 3 when there was nothing to record. `pending` and `status` then leave those units out, and `status` prints `FAILED: n`. A dead unit is final: it is not claimable and not writable (`upsert` answers `UPSERT: dead-lettered`, exit 4). |

`upsert` also takes `--worker W`: the write is refused unless W holds the claim on that unit. An upsert on a dead-lettered unit is refused whoever sends it, so a unit is never both done and failed.

Exit 0 ok; 3 nothing pending, or `claim` found nothing unclaimed; 4 a claim or release was not granted, or an upsert named a dead-lettered unit; 2 usage error or a refused write (`REFUSED: ...` on stdout).

Example, with synthetic names: `init DB --table sweep --key lender --cols rate,note --done checked_at --seed lenders.txt`, then each worker runs `upsert DB --table sweep --row '{"lender":"LenderA","rate":"6.19","checked_at":"2026-10-18"}'`, and the orchestrator loops on `pending` until it exits 3. The script does not read dates; the caller writes them.

## 3. Rules

| Id | Rule |
|----|------|
| U1 | A seed key becomes exactly one pending row. A done column that is NULL means pending; any value means done. |
| U2 | `init` run again never resets a done row and never overwrites data. It adds keys that are new. |
| U3 | `pending` lists only undone rows, and exits 3 when none is left. The answer is a fresh query each time. |
| U4 | `upsert` is idempotent on the key columns: the same key written twice is one row and the last write wins. A re-dispatched worker cannot create a duplicate. |
| U5 | Setting the done column to null reopens the unit. This is how a row that failed a check is cleared and sent back. |
| U6 | A write may carry only the registered key, `--cols` and done columns, and must carry every key column. Lists and objects are stored as JSON text. Key values are always stored and matched as text, so the number 1 and the string "1" name one unit. |
| U7 | Only tables made by `init` accept writes. Names must be letters, digits and underscores starting with a letter, so the script's own table (`_unit_registry`) and any name with SQL in it are refused. |
| U8 | A table cannot be redefined by a later `init` with a different key, columns or done column, and a read command on a missing file does not create one. |
| U9 | A claim is one guarded UPDATE: the unit is taken only if it is undone and nobody else holds it. Two workers never get the same unit, and a worker that loses the race gets the next one or `none-left` (exit 3). Never read a unit and write it as two steps. |
| U10 | A claim answers with a typed outcome: `ok`, `none-left`, `not-found`, `already-done`, `dead-lettered` or `owned-by-other`. A dead-lettered unit (C3) is never handed out by `claim`: with only such units left, `claim` is `none-left`, and `claim --key` on one is `dead-lettered` (exit 4). A dead-lettered unit is not writable either: `upsert` on it prints `UPSERT: dead-lettered` (exit 4), even for its holder, and setting its done column to null does not reopen it; the only way back is a new key (C5). Claiming a unit you already hold is `ok`. Only the holder releases a unit. A released unit can be claimed again. |
| U11 | `upsert --worker W` is refused unless W holds the claim, so a worker whose claim was released or never made cannot write. Without `--worker` an upsert behaves as before. The claim is kept in the script-owned column `_claimed_by`, added by the first `claim`. |

## 3a. The convergence loop (rules C1-C5)

For a phase that must keep going until every unit is done or given up on, the orchestrator runs rounds. The script runs no workers and keeps no round count; the orchestrator holds the counters. (adapted from references/hive/core/framework/host/playbook/runner.py:57 and :305 (Apache-2.0), ideas only)

| Id | Rule |
|----|------|
| C1 | Each round starts with a fresh `pending` and gives each open unit to one worker, which takes it with `claim` first (U9). Nothing is remembered from the last round. |
| C2 | The loop stops when `pending` exits 3, when the round limit the orchestrator wrote into its plan is reached, or when the failure-fraction breaker trips: in one round, the share of workers that ended `STATUS: blocked` or failed is above the limit the plan names. State both limits in the plan before the first round; the script has no default for either. |
| C3 | After the loop stops with units still open, run `deadletter` once with a reason that names why (round limit, breaker, or the first blocker). The units are recorded as failed, and the report lists every one with its reason. |
| C4 | `deadletter` records a unit once. Calling it again lists nothing and exits 3, so a leftover unit is never reported twice for the same stop. |
| C5 | A re-run is a resume: the next run starts at `pending`, which leaves done and failed units out. A failed unit comes back only if a person decides to retry it; no command reopens one, and neither a claim nor an upsert (null done column included) reaches it, so the orchestrator asks, and then writes the unit as a new key; a new key is the only way back. |

## 4. How it fits with the rest

Phase level: `state_ledger.py` says where the run resumes. Row level: this script says which items inside that phase are left. An orchestrator that uses both keeps the tracker file under `_workspace/` and names it in the Handoff files table of its plan.

Does not cover:

- Workers writing at the same moment: SQLite serialises them and a busy file waits at most five seconds, then the write is refused. Two workers cannot take the same unit if both use `claim` (U9); a worker that skips it can still write any row. A claim never expires: a worker that dies holding a unit leaves it claimed until someone runs `release` with that worker's name, and no sweep reclaims it (hive's idle-claim sweep, HV16, is not adopted).
- Retry, backoff and running the rounds or measuring the failure fraction: a script does not run workers, so the orchestrator does (section 3a). The list of rows that never finish is covered by `deadletter`.
- Checking that a done row is true: the tracker records that an item was marked done, not that the result is right. A verification gate is candidate H4.
- Edits to the SQLite file made outside the script.
