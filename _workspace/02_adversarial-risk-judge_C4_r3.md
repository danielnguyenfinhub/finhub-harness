TOTALS: UPHELD 22 / REJECTED 1 / UNVERIFIED 0 — round 3/3

# Adversarial verdict: C4 adoption (eval regression buckets), revision 2

- Audited file: _workspace/02_strategy-architect_C4.md (revision 2), `## Authority List` A1-A23
- Audited: 2026-10-04
- Prior verdicts: _workspace/02_adversarial-risk-judge_C4_r1.md (UPHELD 18 / REJECTED 3), _workspace/02_adversarial-risk-judge_C4_r2.md (UPHELD 21 / REJECTED 2: A13, A17)
- Changed claims re-audited this round: A13, A17 (CHANGED r2), the A13 rewording about `run_suite`/`load_benchmark`, the M27 seed-flakiness fix, the housekeeping changes
- Carried forward unchanged: A1-A12, A14-A16, A18-A23 (21 rows). Byte-identity confirmed: the design's own `grep -E '^\| A([1-9]|1[0124-6]|1[89]|2[0-3]) \|'` diff against the revision-1 copy (`scratchpad/design_r1.md`, header "revision 1") is empty, 21 rows. A13 and A17 differ.
- Extra round authorised by Daniel: none in the launch prompt. Round 3 ends with REJECTED > 0, so this goes to escalation (see the end of this file).
- Method: I extracted the ```diff block and the test file from the design myself (awk), applied them with `patch -p1` to a tar copy of the full repo tree (minus references, .git, .venv, _workspace*, dist and caches; references symlinked) in `scratchpad/j3/`, and kept an unpatched copy as `pre/`. Hashes: runner `c5e597931ac6664f6f54435fadaa25bc2fde48670e71f8c29b6317e5b64f478b` (310 lines) and test file `e624c3ba0bf1b3a334c7e3755e39dbd572041bd372cc379ce7426fe5c267e458` (460 lines). Both match the pins, and the repo's pre-edit runner `7098425263ba…b7ce60` matches too. Probes ran through the real `python -m master_finhub.evals.runner` subprocess. Each mutant got an exact-once replacement, a fresh copy and a fresh pytest process (`-x`, the two eval test files). Nothing was written into the repo except this file.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A12 | UPHELD (carried) | as r2 | as r2 | byte-identical to r1. A11: see the note under A13. The A13 message defect (b) also gives exit 1 for an unusable baseline, and the same one-line fix closes it |
| A13 | REJECTED | NET-NEW | — | **A detected regression with `--baseline` still exits 1 when stdout is closed.** Regression run (baseline `c1` passed, current `c1` fails) with `>&-` exits **1** with `AttributeError: 'NoneType' object has no attribute 'flush'`. With fd 1 closed, Python sets `sys.stdout = None`. `print` is then a silent no-op, and `sys.stdout.flush()` (post-edit runner.py:349) raises `AttributeError`, which `except OSError` (:350) does not catch. The same happens in any host where `sys.stdout is None`. A "fixed" run under `>&-` also exits 1 instead of 2. **(b) An unusable baseline exits 1 when its message cannot be encoded.** `_baseline_failed` (:308) prints `str(exc)`, which embeds the raw `case_id` or path. Two cases: a baseline row `{"case_id": "\ud800x", "passed": 1}` exits **1** (`UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' … surrogates not allowed`) in the default UTF-8 locale; `{"case_id": "café", "passed": 1}` exits **1** under `PYTHONIOENCODING=ascii` or `LC_ALL=C` with `PYTHONCOERCECLOCALE=0 PYTHONUTF8=0`. The claim says "2 (unusable input …) > …" and "Any exception raised while loading the baseline … returns 2". Both are false for these inputs. The claim's own check list does not cover them, and the design classes exit 1 for an unusable baseline as FP (M49). **(c) Supporting survivor K20:** `ensure_ascii=False` on the guarded `print` survives all 130 tests. Under it, a benchmark with `"id": "\ud800x"` that regresses exits **1** (`UnicodeEncodeError`). The report path is safe today only because of the unpinned `json.dumps` default. **Minimal fix (simulated: 130 passed; mypy --strict, ruff and black clean; all probes below then exit 2):** (1) guard `except Exception:  # noqa: BLE001` (still lets `KeyboardInterrupt`/`SystemExit` through) in place of `except OSError:`; (2) in `_baseline_failed`, `print(msg.encode("ascii", "backslashreplace").decode("ascii"))`. Tests to add: `monkeypatch.setattr(sys, "stdout", None)` on a regression gives 2; a bad-row baseline with case id `"\ud800x"` gives 2 under `capsys`; and a K20-style mutant to kill. **What holds:** `/dev/full` gives 2; `\| true` (small and 450 cases) gives 2; `\| head -c1` with 450 cases gives 2, and with a 1-case report gives 3 (the write completed into the pipe buffer, which is correct). Stdout as a read-only fd gives 2. `ulimit -f 1` (partial write of 1024 bytes, then EFBIG) gives 2. A slow consumer (3 s sleep, 450 cases) gives 3. With `SIGPIPE` reset to `SIG_DFL` by the parent the result is 2, because Python re-ignores SIGPIPE at startup. Regressions with non-ASCII or lone-surrogate case ids under utf-8, ascii, latin-1 and `LC_ALL=C` (coerced and uncoerced) all give 3, since `ensure_ascii` escapes them. An injected `KeyboardInterrupt` or `SystemExit` during the write propagates (exit 130, or the injected code); this is input-unreachable. A clean run with a failed write gives 2, which is fail closed and stated in Decision 3. The rewording holds: a 100k-deep benchmark exits 1 with and without `--baseline` (`RecursionError`), the same as pre-edit. "Runs without `--baseline` keep their previous code path" holds: pre and post copies give the same exits (`/dev/full` 1, `\| true` 1, `>&-` 1 or 0), `test_lost_report_without_baseline_unchanged[*-flush]` proves flush is never called, and M52 is killed. Stdout opened on a directory dies in interpreter startup (`init_sys_streams`, exit 1) before any code runs, pre and post alike. That is outside C4. |
| A14-A16 | UPHELD (carried) | NET-NEW | — | byte-identical to r1 |
| A17 | UPHELD | NET-NEW | — | The printed order is now pinned. M57 (J19 on the `--baseline` print), M58 (J19 on the no-flag print) and M59 (J31) are each killed **40/40 under `PYTHONHASHSEED` 0-39**. So are my own K23 (`dict(sorted(buckets.items()))`) and K24 (empty buckets dropped). M27 is killed 40/40, always by `test_buckets_sorted_and_key_order_fixed` (the 20 reverse-ordered ids), so the M27 flakiness fix is confirmed. Under M27, the secondary `test_exactly_one_regression_among_many_exit_3` (3-id `unchanged`) fails only 31/40 seeds. It passes by luck, but it is not the killing test. Note (MSG, not counted): K18 survives 40/40. K18 iterates `sorted(now) + [c for c in baseline if c not in now]`, so the `removed` list is unsorted when there are two or more removed ids. No test has more than one removed id. Add 2+ removed ids in reverse order to `test_buckets_sorted_and_key_order_fixed`. The real code sorts the whole union once (runner.py:294), so the claim is true of the code. |
| A18-A23 | UPHELD (carried) | NET-NEW | — | byte-identical to r1 |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C4 | N/A: boolean outcomes of string-match benchmarks; no returns or P&L | N/A: no positions or leverage | N/A: no fills or prices | N/A for prices. Analogue holds (carried from r2; `run_suite`/`run_case` untouched by the r2 diff) | N/A for prices. Analogue holds: M26 and M35 are killed again | N/A for splits. Analogue holds: `test_agent_never_sees_ground` passes in the full run |

## Proof re-run (scratch copies only)

| item | measured |
|---|---|
| hashes | runner `c5e59793…5b64f478b` (310 lines), test file `e624c3ba…fe5c267e458` (460 lines), pre-edit `70984252…85b7ce60`: all match |
| P1 + P2 | `tests/test_evals_baseline.py tests/test_evals.py`: **130 passed** (84 + 46) |
| P3 full tree | pre-edit **1222 passed, 10 skipped**; post-edit **1306 passed, 10 skipped**. Matches the design. My full-tree copy had no 5 extra failures, unlike the architect's (line 382 note) |
| P4 / P5 | `Success: no issues found in 38 source files` / `All checks passed!` / `67 files would be left unchanged.` |
| hash-seed flakiness | 40 runs of both files under random `PYTHONHASHSEED` values, 8 in parallel: **40/40 runs had 130 passed**. pytest-randomly is not installed, so `-p no:randomly` does not apply. Test-file scan: no assertion depends on set or dict iteration order or on sorted tmp paths. Parametrize `ids=` are literals. The only luck-dependent assertion is the 3-id `unchanged` under M27 (see A17) |
| design mutants re-run (25 of 59) | M1 M2 M3 M4 M5 M6 M7 M9 M11 M13 M20 M26 M27 M30 M35 M38 M51 M52 M53 M54 M55 M56 M57 M58 M59: **all killed**. M27, M57, M58 and M59 were also killed under seeds 0-39 |
| own mutants (30, across the compare/main path) | Killed (23): K1 unchanged/regressed swapped, K2 fixed/still_failing swapped, K3 `len(r)+len(rm) > 1`, K4 list root allowed, K5 `version is not True and …`, K6 hook raises `TypeError`, K7 `object_hook=dict`, K8 read error returns `{}`, K9 `action="store"`, K10 symlinks rejected, K11 compare crash returns `code`, K12 guard returns 3, K15 `report.passed` as the code test, K16 `SCHEMA_VERSION = 2`, K17 `get(...) or SCHEMA_VERSION`, K19 timed-out cases dropped, K21 non-ValueError returns 1, K22 `len(set(...)) > 1`, K23 comparison re-sorted, K24 empty buckets dropped, K25 load catch narrowed to `(ValueError, OSError)`, K28 flush added to the no-flag path, K29 guard routes through `_baseline_failed`. **Survived, non-equivalent FP-class (1): K20 `ensure_ascii=False` on the guarded print** (surrogate-id regression exits 1; see A13 (c)). Survived, not a false pass (4): K13 `if base is None or code == 0` (a clean flagged run with a lost report exits 1 instead of 2, so no regression is hidden); K14 `if code != 3` (the same for clean and still-failing runs; regressions stay guarded); K18 `removed` unsorted (MSG, A17 note); K30 flush moved before print (real `/dev/full` regression still exits 2). Equivalent (2): K26 `max(code, 3) if code else 3` (always 3); K27 `MemoryError` added to the read tuple (only the message changes) |

## Probes (CLI subprocess, edited runner)

| input | exit | ruling |
|---|---|---|
| regression, stdout normal | 3 | correct |
| regression `> /dev/full`; `\| true` (1 and 450 cases); `\| head -c1` (450); read-only fd 1; `ulimit -f 1` partial write; SIGPIPE `SIG_DFL` inherited | 2 | A13 r2 fix works |
| regression `\| head -c1` (1 case, 2 KB fits the pipe buffer) | 3 | correct: the write succeeded |
| regression, slow consumer (450 cases) | 3 | correct |
| **regression, stdout closed `>&-`** | **1** | **A13 REJECTED (a)** |
| fixed run with `--baseline`, stdout closed | 1 | same cause |
| regression, non-ASCII / lone-surrogate id, encodings utf-8 / ascii / latin-1 / C | 3 | `ensure_ascii` saves it (unpinned: K20) |
| **unusable baseline, case id `"\ud800x"` (utf-8), or `"café"` with ascii stdout** | **1** | **A13 REJECTED (b)** |
| clean flagged run `> /dev/full` | 2 | fail closed, stated |
| no flag: `/dev/full`, `\| true`, `>&-` | 1, 1, 1 (fail) / 0 (pass) | identical to pre-edit |
| 100k-deep benchmark, with and without `--baseline` | 1 | the reworded A13 text is accurate |
| stdout fd on a directory | 1 (interpreter startup fatal) | before any code; same pre-edit; outside C4 |
| after the simulated fix: `>&-` regression, surrogate and `café` bad baselines, `/dev/full` | 2, 2, 2, 2 | fix confirmed |

## Housekeeping

- Stale figures: 66, 76, 1288, 1298, 275, 302, 312, 404 and 50 appear only in the r0/r1/r2 totals tables (:34-38, :66-70) and the test-count breakdown (:863). They are historical by label. "38" is the mypy source count (:383) and the r0 kill count (:878). "66" at :84 is a citation (`:66`). No stale current figure remains. 59, 84, 1306, 310 and 460 agree throughout (:3, :34-38, :108, :210, :380, :382, :396, :398, :863, :878).
- The revision-2 table's real-process rows reproduce (`/dev/full` 2, normal 3, `\| true` 2, no-flag `/dev/full` 1).
- `ids=` is present on both large parametrizes (:733 `root`/`ignored-field`, :754 `results`/`case_id`/`nested`).
- Does not cover now lists `-h` (:960) and `load_benchmark` nesting with the post-edit line (:961).

## Escalation (round 3/3, REJECTED > 0, no authorisation line)

| id | judge position | architect position (design text) |
|---|---|---|
| A13 | With `--baseline`, a regression exits 1 when `sys.stdout is None` (`>&-`): `flush()` raises `AttributeError`, which `except OSError` misses. An unusable baseline exits 1 when its message holds a non-encodable `case_id` (lone surrogate in any locale; non-ASCII with ascii stdout), because `_baseline_failed`'s `print` raises `UnicodeEncodeError`. Two-token fix: `except Exception` in the guard, plus an ASCII-escaped message in `_baseline_failed`. Simulated green; add 2 tests and kill K20. | "With `--baseline`, an `OSError` (including `BrokenPipeError`) from the report write or its explicit flush returns 2 … the code is the no-flag code, 3, or 2; it is never lowered. Any exception raised while loading the baseline or running `compare` returns 2." The design scopes the guard to `OSError` and does not discuss a missing stdout or encoding errors. |
