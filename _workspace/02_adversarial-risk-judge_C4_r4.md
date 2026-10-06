TOTALS: UPHELD 22 / REJECTED 1 / UNVERIFIED 0 — round 4 (authorised)

# Adversarial verdict: C4 adoption (eval regression buckets), revision 3

- Audited file: _workspace/02_strategy-architect_C4.md (revision 3), `## Authority List` A1-A23
- Audited: 2026-10-04
- Extra round authorised by Daniel: 2026-10-03
- Prior verdicts: _r1.md (UPHELD 18 / REJECTED 3), _r2.md (UPHELD 21 / REJECTED 2), _r3.md (UPHELD 22 / REJECTED 1: A13)
- Changed claims re-audited this round: A13 (CHANGED r3), the 7 new tests, mutants M60-M66, the re-anchored M51/M53/M54/M56, and the r3 figures
- Carried forward unchanged: A1-A12 and A14-A23 (22 rows). I diffed every `| A<n> |` row against my r3 copy of revision 2 (`scratchpad/design_r2.md`). Only A13 differs. The other 22 rows hash identically (`efa140f1…2d86461` both sides).
- Method: I extracted the ```diff block and the test file from the design myself (awk). I applied them with `patch -p1` to a tar copy of the full repo tree (minus references, .git, .venv, _workspace*, dist and caches; references symlinked) in `scratchpad/j4r4/post`, and kept an unpatched copy in `j4r4/pre`. Hashes: runner `452a4140…f58278129` (311 lines) and tests `e6323921…9d196d9ec427` (520 lines) match the pins. The repo's pre-edit runner is `7098425263ba…b7ce60`, which also matches. Probes ran through the real `python -m master_finhub.evals.runner` subprocess. Each mutant got an exact-once replacement, a fresh copy and a fresh pytest process. Nothing was written into the repo except this file.
- **Method correction that changes the findings.** This session's environment exports `PYTHONUNBUFFERED=1`, and so (by every sign) did the architect's r3 table and my own r2/r3 probes. With that unset, which is CPython's default, stdout to a file or pipe is block-buffered. Every real-process row below was therefore run both ways. The buffered results are the ones that matter.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A12 | UPHELD (carried) | as r3 | as r3 | byte-identical to revision 2 |
| A13 | REJECTED | NET-NEW | — | **The r3 fixes work as tested.** Under `PYTHONUNBUFFERED=1`, a regression with `>&-` gives 2. A clean, fixed or still-failing flagged run with `>&-` gives 2. Bad baselines with `"\ud800x"` (UTF-8) and with `"café"` (`PYTHONIOENCODING=ascii`, and uncoerced `LC_ALL=C`) give 2. A normal regression gives 3. Regressions with surrogate or non-ASCII ids under utf-8, ascii, latin-1, C and coerced C give 3. `/dev/full`, `\| true`, `\| head -c1` (450 cases), read-only fd 1, `ulimit -f 1`, a socket with the peer closed, `SHUT_WR`, a closed pty master and SIGPIPE `SIG_DFL` all give 2. A tty gives 3. Closed stderr gives 3. K20 is killed (M62). `KeyboardInterrupt` propagates on write and on flush. No-flag runs are identical to the pre-edit runner in both buffering modes. **Two defects remain, so the claim is still false as written.** **(1) With CPython's default buffered stdout, a lost report exits 120, not 2.** A one-case regression `> /dev/full` gives **120** (`Exception ignored … OSError: [Errno 28]`), and so does `\| true` with one case. A clean flagged run `> /dev/full` also gives **120**. Mechanism: the guard's `flush()` raises and `main` returns 2, but the unwritten bytes stay in the `TextIOWrapper` buffer. Interpreter shutdown flushes `sys.stdout` again, that fails too, and CPython replaces the exit status with 120. Reports larger than the 8 KB buffer (450 cases) give 2, because the write raises inside `print`. The claim says "2 (… with `--baseline` a report that cannot be written)". The r3 real-process table (`regression, > /dev/full \| 2 \| 2`, `clean flagged run, > /dev/full \| 2`) is not reproducible without `PYTHONUNBUFFERED=1`. The unit tests use `BadStdout`, which has no buffer, so they cannot see this. 120 is not 0 or 1, so this is not a false pass under the design's FP definition. It is still a wrong exit-code contract, on the exact proof scenario (one flipped case), under the default configuration. **(2) The disclosed unusable-baseline gap is a false pass under the design's own M49 standard (ruling below).** It is also wider than disclosed. Exit 1 occurs: buffered, whenever the message exceeds the buffer (a 10 MB case id `\| head -c1` gives **1**); and unbuffered (`PYTHONUNBUFFERED=1`, common in container and CI images) for `/dev/full` and `\| true` (**1**, 5/5 runs). In the default buffered mode with a short message it is 120. The claim, Decision 3 and the changes section all say "exits 1", which is consistent across the three texts but not accurate for the default mode. A third variant has the same cause: with a **good** `--baseline` and a bad benchmark file, a broken stdout gives 1 (unbuffered) or 120 (buffered), through the pre-existing `print(str(exc))`. **Minimal fix (simulated in `scratchpad/j4r4/fix`; runner sha256 `5c447a4d…7cb57aa21a`, 323 lines):** add `_stdout_lost()`, which sets `sys.stdout = open(os.devnull, "w", encoding="ascii")  # noqa: SIM115` and returns 2. In `_baseline_failed`, wrap `print(...)` plus `sys.stdout.flush()` in `try/except Exception: return _stdout_lost()`. The report guard returns `_stdout_lost()` instead of `2`. In `main`'s `except ValueError` around `run_suite`, add `if base is not None: return _baseline_failed(exc)`. Result: 137/137 eval tests, mypy --strict, ruff and black all clean. Every flagged broken-stdout case above gives **2** in both buffering modes: regression `/dev/full`, `>&-`, `\| true` and `\| head -c1`; clean flagged `/dev/full`; bad baseline `/dev/full`, `\| true`, `>&-` and 10 MB `\| head -c1`; good baseline plus bad benchmark `/dev/full`. A normal regression still gives 3. **No-flag behaviour is unchanged:** fail `/dev/full` gives 120 buffered and 1 unbuffered, pass `>&-` gives 0, and bad benchmark `/dev/full` gives 120 or 1. All of these equal the pre-edit runner, because every changed line is reached only when `--baseline` was given. **Tests to add (verified: they fail on r3 and pass on the fix):** `test_full_disk_buffered_stdout_exit_2[regression / bad-baseline / bad-benchmark]` (subprocess to `/dev/full` with `PYTHONUNBUFFERED` removed from env; skipif no `/dev/full`; all 3 fail on r3 with 120); and `test_non_oserror_stdout_with_baseline_exit_2` (`BadStdout(ValueError(...), "write")`, which kills K30, see below). |
| A14-A23 | UPHELD (carried) | NET-NEW / as r3 | as r3 | byte-identical to revision 2 |

### Ruling on the disclosed gap (item 2): REJECT

1. **The design's own standard decides it.** The design classes M49 (`_baseline_failed` returns 1) as FP: "an unusable baseline reads as 'known failure'". For this input, the real code produces exactly M49's observable outcome. Disclosure documents a false pass; it does not reclassify it. The QA bar is behavioural ("no non-equivalent mutant survives that would let a regression pass silently"), and a consumer that tolerates 1 (the reason exit 3 exists) accepts a run in which no comparison happened.
2. **The same standard has already been applied.** The r2 rejection was the same two-condition case (regression plus a broken stdout gives 1), and the architect fixed it. An unusable baseline plus a broken stdout cannot be held to a weaker rule than a detected regression plus a broken stdout.
3. **The design is internally inconsistent.** A clean flagged run that only lost its report is declared fail-closed 2. A run that never read its baseline at all, which is strictly worse, gives 1.
4. **The precedent argument does not carry over.** Before C4, codes 1 and 2 were both plain failure, and no caller had a reason to tolerate 1. C4 introduces the 1-vs-3 split that makes 1 tolerable. So C4 creates the hazard on the pre-existing bad-benchmark print too, when `--baseline` is given.
5. **Cost.** The fix is 12 lines, scoped to `--baseline`, simulated green, and leaves no-flag behaviour byte-for-byte as before.

The claim, Decision 3 and the changes section state the exception consistently with each other ("exits 1"). That is true only unbuffered or for messages over the buffer size. In the default buffered mode the gap shows as 120. This needs no separate fix: with the fix above, the exception disappears and the sentence should be deleted.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C4 | N/A: boolean outcomes of string-match benchmarks; no returns or P&L | N/A: no positions | N/A: no fills | N/A for prices. Analogue holds (diff does not touch `run_suite`/`run_case`) | N/A for prices. Analogue holds: M26 and M35 killed again | N/A for splits. Analogue holds: `test_agent_never_sees_ground` passes in the full run |

## Proof re-run (scratch copies only)

| item | measured |
|---|---|
| hashes | runner `452a4140…f58278129` (311), tests `e6323921…9d196d9ec427` (520), pre-edit `70984252…85b7ce60`: all match |
| P1 / P1+P2 | `tests/test_evals_baseline.py`: **91 passed**. With `tests/test_evals.py`: **137 passed** |
| P3 full tree | pre-edit **1222 passed, 10 skipped**; post-edit **1313 passed, 10 skipped**. Matches the design |
| P4 / P5 | `Success: no issues found in 38 source files` / `All checks passed!` / `67 files would be left unchanged.` |
| hash seeds 0-39 | unmutated: **137 passed, 40/40**. M27, M57, M58, M59 and M64 are each **killed 40/40**. M64 is always killed by `test_removed_ids_sorted`. M27 is killed by `exactly_one_regression` (31 seeds) or `buckets_sorted…` (9 seeds), first failure under `-x` |
| design mutants spot-checked (31 of 66) | M1 M3 M4 M7 M9 M13 M20 M26 M27 M35 M39 M44 M47 M48 M49 M51 M52 M53 M54 M55 M56 M57 M58 M59 M60 M61 M62 M63 M64 M65 M66: **all killed**, each by the test the table names. The re-anchored M51, M53, M54 and M56 hit exactly once against the `except Exception` guard. Cosmetic: the M51-M59 rows escape backticks (`\``), so they render literally |
| own mutants (33, whole compare/main path) | **Killed (28):** K1 unchanged/regressed swapped; K2 fixed/still_failing swapped; K3 gate `len(r)+len(rm) > 1`; K4 string-only root check; K5 `version is not True and …`; K6 hook raises `TypeError`; K7 `object_hook=dict`; K8 read error returns `{}`; K9 `len(set(...)) > 1`; K10 symlinks rejected; K11 compare crash returns `code`; K12 guard returns 3; K13 load catch `(ValueError, OSError)`; K14 `"replace"` escaping; K15 utf-8 `backslashreplace` (killed by the ascii subprocess test); K16 `code = code or 3`; K17 new case only when passing; K18 timed-out counted as pass; K19 `get(...) or SCHEMA_VERSION`; K20 `passed is None` check; K23 generic message for every exception; K24 load failure returns bare 2 (no message); K25 timed-out cases dropped from `compare`; K28 missing file returns `{}`; K29 guard returns 2 only for `stdout is None`; K31 duplicate-id check removed; K32 `RecursionError` out of the tuple. **Survived, equivalent (3), with proof:** K22 `if not base:` (`load_baseline` returns either a non-empty dict or raises: `rows` is non-empty and each row adds a key or raises); K26 `len(...) != 1` and K27 `if args.baseline:` (`action="append"` yields `None` or a list of length ≥ 1, and `[""]` is truthy). **Survived, strictness (1):** K21 `not cid.strip()` (rejects whitespace-only ids, exit 2; never lowers). **Survived, non-equivalent (1): K30 guard `except (OSError, AttributeError)`.** A stdout whose write raises a non-`OSError` (closed `io.StringIO` gives `ValueError`, also `MemoryError` or `RuntimeError`) then escapes, and a flagged regression crashes (exit 1). This is unreachable from the CLI (CPython gives `OSError` or `None`), but reachable for in-process callers of `main`. The real code returns 2 for all of these (probed). Since A13 now promises "any `Exception`", pin it: `test_non_oserror_stdout_with_baseline_exit_2` kills K30 (verified) |

## Probes (CLI subprocess; buf = CPython default, unbuf = `PYTHONUNBUFFERED=1`)

| input | r3 buf | r3 unbuf | fix (both) | ruling |
|---|---|---|---|---|
| regression, stdout normal | 3 | 3 | 3 | correct |
| regression `> /dev/full` (1 case) | **120** | 2 | 2 | A13 (1) |
| regression `\| true` (1 case) | **120** | 2 | 2 | A13 (1) |
| regression `\| true` / `\| head -c1` (450 cases) | 2 | 2 | 2 | correct |
| regression `>&-`; clean/fixed flagged `>&-` | 2 | 2 | 2 | r3 fix (a) confirmed |
| clean flagged `> /dev/full` | **120** | 2 | 2 | A13 (1) |
| bad baseline `"\ud800x"` utf-8; `"café"` ascii / uncoerced C | 2 | 2 | 2 | r3 fix (b) confirmed |
| regression, surrogate / non-ASCII id, utf-8 / ascii / latin-1 / C | 3 | 3 | 3 | correct; K20 = M62 killed |
| **bad baseline `> /dev/full`** | **120** | **1** | 2 | disclosed gap (REJECT, item 2) |
| **bad baseline `\| true`** | **120** | **1** (5/5) | 2 | gap, wider than disclosed |
| **bad baseline, 10 MB case id, `\| head -c1`** | **1** | **1** | 2 | gap, exit 1 in default mode |
| bad baseline `>&-` | 2 | 2 | 2 | correct |
| **good baseline + bad benchmark `> /dev/full`** | **120** | **1** | 2 | same class, via the pre-existing print |
| bad baseline, case id with NUL/ESC/BEL | 2 | 2 | 2 | exit correct. Note (not counted): `backslashreplace` leaves ASCII control characters raw, so a baseline can put terminal escapes on screen. Hardening follow-up: `.encode("unicode_escape")` or `repr` |
| bad baseline, 10 MB id / 3M lone surrogates, stdout normal | 2 / 2 | 2 / 2 | 2 | correct |
| stderr closed (regression) | 3 | 3 | 3 | correct |
| tty (pty) / pty master closed | 3 / 2 | — | — | correct |
| socket peer closed / `SHUT_WR`; SIGPIPE `SIG_DFL` | 2 / 2; 2 | 2 / 2; 2 | — | correct |
| `ulimit -f 1` (450 cases) | 2 | 2 | — | correct |
| in-process: write raises `ValueError` / `UnicodeEncodeError` / `MemoryError`; flush raises `RuntimeError` | 2 | — | 2 | correct (K30 unpinned) |
| in-process: `KeyboardInterrupt` on write / on flush | propagates | — | propagates | correct |
| in-process: injected `SystemExit(0)` on write | propagates, exits 0 | — | same | not reachable from a real stream; same as no-flag; not counted |
| no flag: fail / pass normal; fail / pass `/dev/full`; fail / pass `>&-`; fail `\| true` (450); bad bench `/dev/full` | pre = post: 1/0; 120/120; 1/0; 1; 120 | pre = post: 1/0; 1/1; 1/0; 1; 1 | unchanged | "no-flag path unchanged" holds |

## Housekeeping

- Stale figures: the grep for 84, 460, 310, 59, 1306 and 130 hits only the labelled r0-r3 history tables (:46-50, :81-85), the r3 changes line about K20 surviving "all 130 tests" (:10; historically accurate), and the cumulative count (:971). No stale current figure. The current figures agree throughout: 91 (:46, :155, :428, :444, :971), 1313 (:47, :430), 66 (:3, :48, :986), 311 (:49, :257), 520 (:50, :446).
- The r3 real-process table (:31-43) was measured with `PYTHONUNBUFFERED=1`. Its `/dev/full` rows are wrong for the default interpreter (120). After the fix, re-measure with the variable unset.
- The § Mutation targets note says seeds 0-19. I ran 0-39: all kills held.

## Escalation

Round 4 (authorised) ends with REJECTED 1 (A13). Further rounds need Daniel's authorisation.

| id | judge position | architect position (design text) |
|---|---|---|
| A13 | (1) In CPython's default buffered mode, a flagged run whose report cannot be written exits 120, not 2, for any report under 8 KB. That includes the one-flip proof scenario on a full disk, because the exit-time flush fails again after `main` returns 2. (2) The disclosed "unusable baseline plus unwritable stdout" gap is a false pass by the design's own M49 definition. It reaches exit 1 in the default mode (message over the buffer size) and under `PYTHONUNBUFFERED=1`. Good baseline plus bad benchmark is the same. Fix: `_stdout_lost()` (park stdout on devnull, return 2), used by the report guard and by a guarded `_baseline_failed`, and route the `run_suite` `ValueError` through `_baseline_failed` when `--baseline` is given. 12 lines, flagged path only, simulated green. Add 4 tests (verified to fail on r3). | "With `--baseline`, any `Exception` from the report write or its explicit flush returns 2 … One exception: when stdout itself cannot be written (`/dev/full`), that message `print` raises `OSError` and the run exits 1, the same as the existing bad-benchmark path." Real-process table: regression `> /dev/full` gives 2. |
