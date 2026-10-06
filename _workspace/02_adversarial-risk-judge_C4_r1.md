TOTALS: UPHELD 18 / REJECTED 3 / UNVERIFIED 0 — round 1/3

# Adversarial verdict: C4 adoption (eval regression buckets), revision 0

- Audited file: _workspace/02_strategy-architect_C4.md (revision 0), `## Authority List` A1-A21
- Audited: 2026-10-03
- Changed claims re-audited this round: all (first round)
- Method: every cited `references/` line opened at ±5. The design diff and the test file were extracted from the design and applied to scratch copies (never into the repo). Gates were re-run, adversarial inputs were probed through the real `python -m` subprocess, and 16 of the architect's 38 mutants plus 24 of my own were run, each in a fresh copy.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | crewai .../experiment/result.py:102 | `baseline_lookup = {}`, filled by `identifier` at :103-106 | — |
| A2 | UPHELD | result.py:123 | `elif not result.passed and baseline_passed: regressed.append` | — |
| A3 | UPHELD | result.py:121 | `if result.passed and not baseline_passed: improved.append` | — |
| A4 | UPHELD | result.py:115 | `if not test_identifier or test_identifier not in baseline_lookup: new_tests.append` | — |
| A5 | UPHELD | result.py:130 | loop over `baseline_results`, `missing_tests.append` at :133 when absent from current ids | — |
| A6 | UPHELD | result.py:36; result.py:14 | `"results": [r.model_dump(...)]` in `to_json`; `passed: bool` on `ExperimentResult` | — |
| A7 | UPHELD | autogpt classic challenge_loader.py:49 | `is_regression_test` returns `beaten.get(name, False)`, docstring "consistently beaten" | The JSON read is in `_load_beaten_challenges` (:33-45, `json.load` at :41), the helper :51 calls. Same call chain. Licence: `classic/` MIT. |
| A8 | UPHELD | challenge_loader.py:114 | `if maintain and not is_regression: continue` | Backlog's `filter :66` is wrong, as the architect says: :66 is `explore: bool = False,`. |
| A9 | UPHELD | autogpt classic evaluator.py:64 | `if result.timed_out: result.success = False` | — |
| A10 | UPHELD | revfactory skill-testing-guide.md:137 | an assertion that passes 100% in both configurations does not measure the skill's differential value | Context only. The two runs in the guide are with-skill vs without-skill (:11, :85, :92), not before vs after. The claim's wording ("two runs", "passing in both carries no new signal") holds. Apache-2.0. Nothing in behaviour depends on it. |
| A11 | REJECTED | NET-NEW | — | Falsified on substance; two inputs escape the fail-closed contract. **(1) Deep nesting:** a baseline nested 100,000 deep, even inside an ignored field of an otherwise valid row (`{"results":[{"case_id":"c1","passed":true,"x":[[[…]]]}]}`), raises `RecursionError` in `json.load`. That is not `OSError`/`ValueError`, so it escapes `load_baseline` and `main`'s `except ValueError`. Observed through the CLI: exit **1**, traceback, no report. The contract says an unusable baseline gives exit 2, and exit 1 means "known failures, no regression". **(2) Duplicate JSON keys:** `json.load` keeps the last value, so rows are silently dropped. `{"results":[c1 pass, gone pass],"results":[c1 pass]}` with only `c1` run gives exit **0**: a previously passing case is missing from the current run and never reported as `removed`. `{"case_id":"gone","case_id":"c1",...}` silently retargets a row the same way. Fix: add `RecursionError` to the `except` in `load_baseline`, and pass `object_pairs_hook` to `json.load` to raise on a duplicate key (it covers the root and rows alike). Add a test and a killed mutant for each. |
| A12 | UPHELD | NET-NEW | — | Check is real: M26, M35 and M36 re-run, all killed (`test_removed_failing_case_fails_run`, `test_compare_transition[True-None-removed]`). Fail-closed direction confirmed. Renaming a benchmark *file* does not change its `case_id` (the id comes from content or `"id"`, runner.py:112-116), so the rename trap does not exist for file names. Splitting a benchmark, or editing a hash-id benchmark, gives `removed` + `new` and exit 3 until the baseline is refreshed, as stated. Honesty gap for Does not cover (not blocking): an explicit-id benchmark edited to be *easier* keeps its id, reads `unchanged` and exits 0. State this. |
| A13 | REJECTED | NET-NEW | — | The stated invariant "with `--baseline` the code is the no-flag code or 3" and the mapping "2 = unusable input" are falsified by the A11(1) input. Without the flag the suite exits 0; with `--baseline deep.json` it exits **1**, which is neither 0 nor 3, and an unusable input does not get 2. Any crash in the compare path exits 1 through Python's uncaught-exception code, and that collides with "known failure". This matters most for exactly the consumer code 3 exists for, one that tolerates 1 and blocks on 3. Nothing exits 0, and "never lowers" holds: the code only ever goes from 0/1 to 3, and M30 and O4 are killed. Fix: same as A11. Optionally also wrap `main`'s compare path so any unexpected `Exception` returns 2. |
| A14 | UPHELD | NET-NEW (repo fact runner.py:165-166) | `ok = not timed_out and error is None and grading is not None` / `grading.total > 0 and grading.failed == 0` | Through the CLI, pass→fail, pass→error and pass→timeout each gave exit 3 with `regressed == ["c1"]`. M28 killed. |
| A15 | UPHELD | NET-NEW | — | M5 and M6 killed; O13 (single-row off-by-one) and O15 (`and` for `or`) killed. |
| A16 | UPHELD | NET-NEW | — | M14, O7 (`>`), O8 (falsy default) and O22 (emits 2) all killed. A real report printed by the **pre-edit** runner (no `schema_version`) loads as v1 and gates correctly: same set gives 1 (known failing), dropping its failing case gives 3. The only consumer of the report or runner outside the module is `tests/test_evals.py`, which reads `pass_rate` only (:187-192). No script, CI file, doc or other module parses it (grep across the repo, excluding `references/` and `_workspace*`). |
| A17 | REJECTED | NET-NEW | — | Vacuous check for the "fixed `BUCKETS` order" half. `test_buckets_sorted_and_key_order_fixed` asserts `list(got) == list(BUCKETS)` against the *imported* constant, so it cannot fail when the order changes. Own mutant O23, `BUCKETS = ("removed", "regressed", ...)`, **survived all 112 tests**. The sorting half is real (M27 per design; my O10, `reverse=True`, killed). Fix: assert against a literal, e.g. `assert BUCKETS == ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")`, and record O23 as a mutant. |
| A18 | UPHELD | NET-NEW (runner.py:166, verifiers.py:37-40) | `grading.total > 0 and grading.failed == 0`; `pass_rate = passed/total` | `tests/test_evals.py:67-69` `test_pass_benchmark_passes` asserts `r.score == 1.0` on pass. A score cannot drop between two passes. |
| A19 | UPHELD | NET-NEW | — | M9 killed by `test_missing_baseline_path_exit_2[empty-string]`. |
| A20 | UPHELD | NET-NEW | — | `grep -c "run_suite(args.benchmarks)"` = 1 on the edited file. The diff touches neither `run_suite` nor `run_case`. Post-edit sha256 `25250b6f…5358003` reproduced. |
| A21 | UPHELD | NET-NEW (licence gate) | — | Docstring names crewai `result.py:99-143` and autogpt `challenge_loader.py:49` (MIT) and revfactory `skill-testing-guide.md:135` (Apache-2.0); licences match `references/LICENSES.md:8,11,13`. Measured: P8 Hangul 0/0; P9 shared 8-token runs 0/0/0 (result.py, challenge_loader.py, skill-testing-guide.md); P10 `autogpt_platform` 0/0. No citation points into `autogpt_platform/`. |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C4 | N/A: boolean outcomes of string-match benchmarks; no returns or P&L | N/A: no positions or leverage | N/A: no fills or prices | N/A for prices. The analogue holds: the baseline is loaded in `main` and passed only to `compare` after `run_suite`; `run_suite`/`run_case` are unchanged (grep = 1, diff) | N/A for prices. The analogue holds: an absent baseline case is `removed` and gated (M26/M35/M36 killed). See the A11(2) caveat: duplicate keys can hide a row until fixed | N/A for splits. The analogue holds: `ground` stays out of the agent (`test_agent_never_sees_ground` passes) and verifiers are unchanged |

## Proof re-run (scratch copies only; nothing written into the repo)

| item | result |
|---|---|
| pre-edit sha256 runner.py | `7098425263ba…b7ce60`, matches the design |
| post-edit sha256 runner.py / test file | `25250b6f…5358003` / `4110b8a5…2313377`, both match |
| new tests + test_evals.py | 112 passed (66 + 46) |
| full suite, full-tree copy (all of the repo except references, .git, .venv, _workspace*, dist; references symlinked) | pre-edit **1222 passed, 10 skipped**; post-edit **1288 passed, 10 skipped** |
| narrow copy (src + tests only) | 1283 passed, 5 failed (test_checkpoint ×1, test_lint_harness ×4). The same 5 fail on an unedited narrow copy (90 passed, 4 skipped, 5 failed in those two files), so the claim is confirmed: they depend on the tree, not on the edit |
| mypy --strict src / ruff / black | Success, 38 files / All checks passed / 67 files unchanged |
| P7 | **6, not 5**: the docstring line 7 `Baseline buckets (--baseline) adapted…` also matches `--baseline`. The proof row's expected value is wrong; a builder would see a mismatch. Fix the expected value. |
| P8 / P9 / P10 / P13 | 0,0 / 0,0,0 / 0,0 / no `import re` |
| architect mutants spot-checked (16 of 38) | M1 M3 M5 M6 M9 M12 M14 M19 M21 M26 M28 M30 M32 M35 M36 M38: all killed |
| own mutants (24) | O1 first-branch direction, O2 second-branch direction, O3 removed→new, O4 precedence (3 only when otherwise 0), O5 load outside try, O6 `passed in (True, False)`, O7 schema `>`, O8 falsy schema default, O9 dup only if disagreeing, O10 reverse sort, O11 benchmark as baseline, O12 `__main__` drops exit code (subprocess test kills it), O13 single-row off-by-one, O14 `new` gates, O15 `and` for `or`, O16 fixed reads baseline, O17 case_id None-only, O18 compare drops first case, O19 code 3→2, O20 root check removed, O21 except JSONDecodeError only, O22 schema emitted as 2, O24 baseline value negated: **killed**. O23 BUCKETS order swapped: **SURVIVED** (A17) |

## Adversarial input probes (CLI subprocess, edited runner)

| input | exit | ruling |
|---|---|---|
| pass→fail / error / timeout | 3 / 3 / 3 | correct |
| baseline ids `C1`, `c1 `, NFD `ć` vs current `c1` | 3 | fail closed (removed + new) |
| baseline from another benchmark set | 3 | fail closed |
| duplicate id in the current run | 2 | existing run_suite check |
| missing benchmark file in the current run | 2 | not silently skipped |
| BOM, trailing garbage, two concatenated reports, latin-1, UTF-16 (PowerShell `>`) | 2 | fail closed |
| `passed: NaN`, `schema_version` Infinity / 1e400 / 5000-digit int | 2 | fail closed |
| `"results"` an object | 2 | fail closed |
| directory; NUL in path (API) | 2 | fail closed |
| `schema_version: 1.0` | 0 | documented lenience |
| 100 MB baseline | 0 | works (documented trust boundary) |
| symlink to a good baseline | 0 | correct |
| **100k-deep nesting (root or inside an ignored row field)** | **1, traceback** | **A11 / A13 REJECTED** |
| **duplicate top-level `results` key / duplicate `case_id` key in a row** | **0** with a previously passing case unreported | **A11 REJECTED** |
| FIFO as baseline | hangs (killed by timeout) | not a false pass; add to Does not cover |
| `--baseline` given twice | last wins silently; the first baseline's `gone` case was not gated (exit 0) | not blocking; state it or reject a repeated flag (`action` that errors on a second value) |
| `-h` with `--baseline` | 0 | existing argparse behaviour, runs nothing |
| KeyboardInterrupt / whole-suite kill | non-zero by signal, no report | not a false pass |

Not in C4's diff, but the same class: `load_benchmark` (runner.py:75-79) also lets `RecursionError` escape as exit 1. If the architect widens the fix to `main`, it covers both.

## Notes for revision (not counted)

- Does not cover should add: an explicit-id benchmark edited to be easier reads `unchanged`; a FIFO or device path blocks; a repeated `--baseline` keeps only the last.
- P7 expected value is 6.
