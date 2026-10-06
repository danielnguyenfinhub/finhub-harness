TOTALS: UPHELD 21 / REJECTED 2 / UNVERIFIED 0 — round 2/3

# Adversarial verdict: C4 adoption (eval regression buckets), revision 1

- Audited file: _workspace/02_strategy-architect_C4.md (revision 1), `## Authority List` A1-A23
- Audited: 2026-10-03
- Prior verdict: _workspace/02_adversarial-risk-judge_C4_r1.md (UPHELD 18 / REJECTED 3)
- Changed claims re-audited this round: A11, A13, A17 (CHANGED r1), A22, A23 (new), proof row P7, the Does not cover additions, the M24 side-effect decision
- Carried forward unchanged: A1-A10, A12, A14-A16, A18-A21. Byte-identity confirmed: the architect's `grep -E '^\| A([1-9]|1[02456]|1[89]|2[01]) \|'` diff against `design_r0.md` is empty (18 rows); A11/A13/A17 do differ.
- Method: the diff and the test file were extracted from the design myself (awk on the ```diff block; lines 349-752 for the test file) and applied to the repo's pre-edit runner in a scratch copy. Hashes: runner `29f63ce9…3ce0b52` (302 lines), test file `069c254b…96e70c3` (404 lines), both match the pins; pre-edit `7098425263ba…b7ce60` matches. Nothing written into the repo except this verdict. Probes ran through the real `python -m master_finhub.evals.runner` subprocess. Mutants: exact-once replacement, fresh copy, fresh pytest process on `tests/test_evals_baseline.py tests/test_evals.py`.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A10 | UPHELD (carried) | crewai result.py / autogpt classic / revfactory | as in r1 | byte-identical to r0 |
| A11 | UPHELD | NET-NEW | — | Every r1 input now fails closed with exit 2 and a `Baseline …` message: 100k-deep arrays at the root, inside an ignored row field, inside an extra top-level field, and 100k-deep objects (`RecursionError`); duplicate keys at the root (`results`, `schema_version`), in a row (`case_id`, `passed`), in a nested ignored object and four levels deep (`ValueError`). Escape spellings: `"case_id"` next to `"case_id"`, and `"results"` next to `"results"`, both exit 2, so the hook sees decoded keys. Also exit 2: UTF-8 BOM (`JSONDecodeError`), a 5000-digit int in an ignored field, a repeated lone-surrogate key, a symlink loop, a symlink to a FIFO, a symlink to a directory, a FIFO, `/dev/zero`, `/dev/null`, a 5000-char path, `""`, a file deleted between `isfile` and `open` (`FileNotFoundError`), and an injected `PermissionError` (as root a real chmod 000 cannot deny; a non-root run cannot read the 0700 scratchpad). Correctly not rejected (no false pass): `NaN`/`Infinity` in ignored fields, a 4000-digit int, a lone-surrogate `case_id` (exit 3, removed + new), `__proto__` (exit 3). Case-variant (`"Results"`, `"Case_id"`) and NFD-variant (`"résults"`) keys exit 0 when they hold the dropped row. That is the declared "extra keys are ignored" lenience, not a duplicate: every JSON parser reads the same `results`, unlike the r1 duplicate key. Size: 8.3 MB took 0.25 s and 59 MB RSS; 83 MB took 3.2 s and 431 MB (plain `json.load` alone takes 1.96 s and 422 MB). Exit 3, correct. Mutants M12, M14, M21-M24 and M39-M41 were killed, plus my own J12, J16, J17, J24, J25, J28 and J34. |
| A12 | UPHELD (carried) | NET-NEW | — | byte-identical to r0 |
| A13 | REJECTED | NET-NEW | — | **A detected regression still exits 1** when the report cannot be written. The verdict is computed and then `print(json.dumps(out, indent=2))` (post-edit runner.py:297, a line C4 rewrites) raises an uncaught `OSError`, and Python exits 1, which is the "known failure, no regression" code. Measured with a `good_gone` baseline and current `c1` (regression = removed). `> /dev/full`, i.e. `> report.json` on a full CI disk, gave **exit 1** (`OSError: [Errno 28]`). `\| true` with a 400-case report (257 KB) gave PIPESTATUS **1** (`BrokenPipeError` at runner.py:297). The same run with stdout intact exits 3. So "2 > 3 > 1 > 0" is false for an ordinary CI pattern, and a consumer that tolerates 1 lets the regression through. Not disclosed in Does not cover. Second contradiction, disclosed but not reflected in the claim text: the claim says "2 (unusable input: a bad benchmark …)", but a benchmark nested 100k deep exits **1** with a traceback, with or without `--baseline` (post-edit runner.py:84 catches only `(OSError, json.JSONDecodeError)`). Fix: (a) wrap the `print` plus an explicit `sys.stdout.flush()` in `try/except OSError` and return a blocking code: 2, or keep 3 when `code == 3`, as the architect chooses. Add a test that swaps `sys.stdout` for a writer that raises `OSError`/`BrokenPipeError`, and a killed mutant. (b) Either add `RecursionError` to `load_benchmark`'s tuple (one token, the A11 fix) or reword A13 to say a crash inside `run_suite` exits 1, as before. What does hold: the catch-all cannot swallow a verdict, because `compare` failing returns 2, which outranks 3. It cannot mask `run_suite`: an injected `RuntimeError`/`RecursionError` in `run_suite` still exits 1 with a traceback, as before, and J11 shows the old `except ValueError` is still the handler. It does not catch `KeyboardInterrupt` (exit 130). `MemoryError`, `RuntimeError` and `TypeError` raised inside the hook exit 2 ("Baseline unusable (…)"). `SystemExit(0)` raised inside the hook would exit 0, but no input can trigger it (only injected code). M7, M30, M47-M49, J6, J22 and J23 were killed. |
| A14-A16 | UPHELD (carried) | NET-NEW | — | byte-identical to r0 |
| A17 | REJECTED | NET-NEW | — | The compare-level half is now real: M50 (= O23), J15 (last two buckets swapped), J20 (`sorted(BUCKETS)`), J14 (`reverse=True`) and M27 (per design) are all killed by the literal-tuple test. But the claim is that buckets are **emitted** in the fixed order, and the writer is unpinned. Own mutant **J19** `print(json.dumps(out, indent=2, sort_keys=True))` **survived all 122 tests**. Under it, the printed `comparison` reads `fixed, new, regressed, removed, still_failing, unchanged`, and `schema_version` is no longer the first key (Decision 4). J31, `schema_version` moved after the report fields, also survived. Fix: in a CLI test that parses stdout with `json.loads` (it keeps order), assert `tuple(out["comparison"]) == order` and `next(iter(out)) == "schema_version"`. Record J19 and J31 as mutants. |
| A18-A21 | UPHELD (carried) | NET-NEW | — | byte-identical to r0. A20: `grep -c "run_suite(args.benchmarks)"` = 1 again |
| A22 | UPHELD | NET-NEW | — | Exit 2 ("given more than once") before the suite runs in every case: two `--baseline` flags with the same value, with different values, with `=` syntax (`--baseline=a --baseline=b`), and with prefix abbreviations mixed in (`--baseline=x --base y`, `--base x --baseline y`). argparse maps a unique prefix (`--b`, `--base`, `--basel=`) to the same `append` dest, so an abbreviation counts as a repeat. A single abbreviated flag works (exit 3 on the gone baseline). Also checked: flag after the positionals (3), `--baseline x -- c1.json` (3), and `-- --baseline x` (2; `--baseline` is read as a benchmark path). M44, M45, M46 and J7 (`>= 1`) killed. J8 (`>= 2`), J9 (`[-1]`) and J27 (`if args.baseline:`) are equivalent under `append` plus the length check. |
| A23 | UPHELD | NET-NEW | — | `isfile` follows symlinks, so a symlink to a regular file is accepted (exit 3 on the gone baseline). `/dev/stdin` redirected from a file is accepted, since it resolves to a regular file. A FIFO, a symlink to a FIFO, a directory, a symlink to a directory, `/dev/zero`, `/dev/null` and a symlink loop all exit 2 without opening. M42, M43, J13 (`isdir`) and J30 (raise removed) are killed, each by the 60 s subprocess timeout (60.5-60.9 s). The FIFO test passed 10/10 under 6 busy loops on 4 cores (0.19-0.42 s). After the timeout-killed mutants no runner process was left (`ps` count 0); `subprocess.run` kills and reaps the child on `TimeoutExpired`. It cannot hang CI past 60 s. The check-then-open race is real (a FIFO swapped in between hangs; `timeout` exit 124) and is disclosed. |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C4 | N/A: boolean outcomes of string-match benchmarks; no returns or P&L | N/A: no positions or leverage | N/A: no fills or prices | N/A for prices. Analogue holds: the baseline is loaded in `main` and passed only to `compare` after `run_suite`; grep = 1; `run_suite`/`run_case` untouched by the diff | N/A for prices. Analogue holds: `removed` is gated (M26, M35 killed). The r1 duplicate-key caveat is closed (M39, M40 killed) | N/A for splits. Analogue holds: `test_agent_never_sees_ground` passes; verifiers unchanged |

## Proof re-run (scratch copies only)

| item | measured |
|---|---|
| hashes | runner `29f63ce9cb6ad7144df6d4bf70174fc7dc9667ad74edd7297aef2a2be3ce0b52`, test `069c254b4cf07c291c15e69595a61b08b78d1ef0de21b9566ad66a71096e70c3`: both match |
| P1 / P2 | 76 passed / 46 passed (122 together) |
| P3 full-tree copy (repo minus references, .git, .venv, _workspace*, dist, caches; references symlinked) | pre-edit **1222 passed, 10 skipped**; post-edit **1298 passed, 10 skipped**. Matches the design |
| P4 / P5 | `Success: no issues found in 38 source files` / `All checks passed!` / `67 files would be left unchanged.` |
| P7 | **6** (docstring :7, :34, :35, :209, :245, :271). The corrected expected value is right |
| P8 / P9 / P10 / P13 | 0,0 / 0,0,0 (result.py, challenge_loader.py, skill-testing-guide.md) / 0,0 / no `import re` |
| architect mutants re-run (27 of 50) | M1 M2 M4 M7 M10 M12 M14 M21 M22 M23 M24 M26 M30 M35 M39 M40 M41 M42 M43 M44 M45 M46 M47 M48 M49 M50: killed. M24 was killed on the second attempt: my first replacement string matched twice (`load_benchmark` has the same line), so I re-ran it with unique context |
| own mutants (35) | Killed (25): J1 swap new/removed, J2 removed branch dead, J3 regressed/unchanged swapped, J4 fixed/still_failing swapped, J5 `or`→`and`, J6 gate only when code 0, J7 `>= 1`, J12 load outside the try, J13 `isdir`, J14 reverse sort, J15 BUCKETS tail swap, J16 no schema default, J17 `version >`, J18 `__main__` drops the code, J20 `sorted(BUCKETS)`, J22 failure returns 3, J23 compare catch narrowed, J24 dup only if disagreeing, J25 `passed in (True, False)`, J26 baseline ids only, J28 `len(rows) <= 1`, J30 regular-file raise removed, J32 drop a baseline row, J33 timed-out cases dropped, J34 empty `case_id` allowed. **Survived, non-equivalent (2): J19 `sort_keys=True` and J31 schema_version not first (A17).** Survived, equivalent (6): J8 `>= 2`, J9 `[-1]`, J21 `len(out) < len(pairs)` (architect's equivalent, confirmed: `dict(pairs)` is never longer), J27 truthiness, J29 `version is True`, J35 `MemoryError` added. Survived, MSG/strictness, not a false pass (2): J10 `OSError` dropped from the tuple (still exit 2 through the catch-all, generic message; no test covers a permission or race `OSError`); J11 `run_suite` handler widened to `Exception` (crash 1→2; untested and outside C4's contract) |

## Adversarial probes (CLI subprocess, edited runner; baseline `good_gone` = c1 + gone, current = c1)

| input | exit | ruling |
|---|---|---|
| deep nesting ×4 shapes, duplicate keys ×7 shapes incl. escape spellings, BOM, 5000-digit int, duplicate surrogate key | 2 | fail closed (A11) |
| NaN/±Infinity ignored, 4000-digit int, surrogate `case_id`, `__proto__`, `schema_version: 1.0` | 3 | correct |
| `Results` / `Case_id` / NFD `results` variants holding `gone` | 0 | declared lenience (extra keys ignored); every parser agrees on `results` |
| path types: loop, →FIFO, FIFO, →dir, /dev/zero, /dev/null, 5000-char, `""`, race→missing, PermissionError | 2 | fail closed (A23, A11) |
| race → FIFO swapped after `isfile` | hangs (timeout 124) | disclosed |
| repeated / `=` / prefix-abbreviated `--baseline` | 2 | A22 |
| injected RuntimeError/TypeError/MemoryError in hook | 2 | catch-all works |
| injected KeyboardInterrupt (load or suite) | 130 | not swallowed; sensible |
| injected SystemExit(0) in hook | 0 | not reachable from any input |
| injected RuntimeError/RecursionError in run_suite; real 100k-deep benchmark | 1 + traceback | pre-existing handler kept; contradicts A13 text (see A13) |
| **regression + stdout `> /dev/full` or closed pipe** | **1** | **A13 REJECTED** |
| `--baseline x … -h` | 0, nothing run | pre-existing argparse behaviour (r1 note); not listed in Does not cover |

## Does not cover (r1 additions)

- Explicit-id benchmark made easier: true, and stated.
- `load_benchmark` deep nesting: reproduced (exit 1 with and without the flag). The cited `runner.py:78` is the pre-edit line (`:84` after the edit). It is disclosed, but it contradicts A13's "a bad benchmark → 2". See the A13 fix (b).
- Check-then-open race: reproduced (a FIFO swapped in hangs). The suggested `os.open(O_NONBLOCK)` + `fstat` fix is sound.
- Missing: the stdout write failure (A13), and `-h` alongside `--baseline` exiting 0 without running.

## M24 side-effect decision

Agreed. Under M24, a `[]` root goes through the CLI to `AttributeError`, then the catch-all, then exit 2 with "Baseline unusable (AttributeError).", so it is no longer a false pass. Calling `load_baseline` directly in `test_unreadable_baseline_exit_2` pins the `ValueError` API contract and kills it. Measured: killed at `test_unreadable_baseline_exit_2[[]]`, with the CLI half passing.

## Stale numbers (grep 66 / 38 / 1288 / 275 / 312)

- Line 3: "38 mutants" in the opening paragraph, which now claims every edit was simulated. Should read 50.
- Line 73: Target table, `tests/test_evals_baseline.py` "new, 66 tests". Should read 76. A builder reads this table, and it contradicts P1.
- Not stale: :31-35 (r0→r1 table), :331 ("38 source files" is the mypy count), :755 (r0 subtotal), :770 ("Revision 0 killed 38/38").

## Notes (not counted)

- The `test_deeply_nested_baseline_exit_2` parametrize ids are 200 KB strings (`-v`, `--durations` and junit output balloon). Add `ids=["root", "row-field"]`, and the same for `test_duplicate_json_keys_exit_2`.
- J10: add a test for an `OSError` after `isfile` (monkeypatched `open` raising `PermissionError`) so the `cannot read (PermissionError)` message is pinned.
