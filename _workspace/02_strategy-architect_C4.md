# C4 adoption design: eval regression buckets against a prior report (revision 4)

Item: C4, scope runtime, from `_workspace/01b_capability-scout_backlog.md:51`. The backlog has no `### C4` detail section (only C1-C3 are detailed), so the row is the whole brief. QA bar from `_workspace/00_input/request.md` Pick 5. PASS means all of: the gates are green; `src` is byte-identical to this design; and no non-equivalent mutant survives that would let a regression pass silently. Every edit below was simulated on a scratch copy. That covered mypy --strict, ruff, black, the full test suite and 75 mutants, each in a fresh process on a fresh copy, and every real-process probe twice: with `PYTHONUNBUFFERED` removed (`env -u PYTHONUNBUFFERED`, CPython's default block-buffered stdout) and with `PYTHONUNBUFFERED=1` (results in § Test plan).

## Changes in revision 4

Judge round 4 (`_workspace/02_adversarial-risk-judge_C4_r4.md`) gave UPHELD 22 / REJECTED 1 (A13). Daniel authorised round 5 on 2026-10-04. The scope is the judge's fix and its tests. Nothing else changes.

Before changing anything, I re-ran the rejection on scratch copies of the pre-edit, r3 and judge-fix runners, every probe in both modes: with `PYTHONUNBUFFERED` removed (CPython's default) and with `PYTHONUNBUFFERED=1`. Every row reproduced, and none is disputed. My r3 `/dev/full` rows were measured in a session that exports `PYTHONUNBUFFERED=1`, so they showed 2 where the default interpreter gives 120. The `BadStdout` unit tests have no buffer, so they could not see it either. The mechanism: the guard's flush raises and `main` returns 2, but the unwritten bytes stay in the `TextIOWrapper` buffer; the interpreter's exit-time flush fails again, and CPython replaces the exit status with 120.

Changed claim: **A13** only (marked `CHANGED r4`). Every other Authority row is byte-identical to revision 3 (the check is in § Authority List).

| finding | fix in `runner.py` (+12 lines, all reached only with `--baseline`) | new test | new mutants (all killed) |
|---|---|---|---|
| A13(1): with buffered stdout, a flagged run whose report is lost exits 120, not 2 (one-flip regression `> /dev/full` or `\| true`; clean flagged run `> /dev/full`) | New `_stdout_lost()`: `sys.stdout = open(os.devnull, "w", encoding="ascii")`, then `return 2`. The report guard returns `_stdout_lost()` instead of `2`, so the exit-time flush goes to devnull and cannot replace the code | `test_full_disk_buffered_stdout_exit_2[regression]` | M67, M69, M70 |
| A13(2): an unusable baseline with an unwritable stdout exits 1 (unbuffered, or a message larger than the buffer) or 120 (buffered). This is a false pass under the M49 standard | `_baseline_failed` puts its `print` and a `sys.stdout.flush()` inside `try/except Exception`, which returns `_stdout_lost()` | `test_full_disk_buffered_stdout_exit_2[bad-baseline]`; the unusable-baseline run in `test_non_oserror_stdout_with_baseline_exit_2` | M68, M71, M75 |
| A13(2), same class: a good `--baseline` with a bad benchmark and an unwritable stdout exits 1 or 120 through the pre-existing `print(str(exc))` | `main`'s `except ValueError` around `run_suite` gains `if base is not None: return _baseline_failed(exc)`. Without the flag, the old `print(str(exc))` / `return 2` is untouched | `test_full_disk_buffered_stdout_exit_2[bad-benchmark]` | M72, M73 |
| judge K30 survived (report guard narrowed to `(OSError, AttributeError)`) | None | `test_non_oserror_stdout_with_baseline_exit_2` (`ValueError` on write: a regression run, then an unusable-baseline run) | M74 = K30 |

Test notes:
- `test_full_disk_buffered_stdout_exit_2` runs the CLI as a subprocess with stdout on `/dev/full`. It builds its environment from a copy of `os.environ` with `PYTHONUNBUFFERED` removed, so it never depends on the session's environment. It is skipped where `/dev/full` does not exist. It also runs the same command without `--baseline` and asserts 120, the pre-edit result. That second assertion kills M73.
- The judge's version of `test_non_oserror_stdout_with_baseline_exit_2` (the regression run only) passes on r3, because r3's report guard already catches `Exception`, so it kills only K30. I added an unusable-baseline run to the same test. The test now also fails on r3 (the `ValueError` escapes from `_baseline_failed`'s bare `print`) and kills M71 and M75.
- All 4 new tests fail on the r3 runner and pass on the r4 runner. I checked this in a pytest process started in each mode: on r3 the 3 subprocess cases give `[120, 120]`, and the non-`OSError` case raises `ValueError` out of `main`.

Re-anchored mutants: M51, M53 and M54, because the guard now ends in `return _stdout_lost()`, and M55, because `sys.stdout.flush()` now appears twice, so its anchor includes the report `print` before it. M61 is reclassified as MSG. With the new message guard, removing the escaping still exits 2 but loses the message, and the two message tests still kill it.

Real-process check (`python -m master_finhub.evals.runner`; buf = `env -u PYTHONUNBUFFERED`, the CPython default; unbuf = `PYTHONUNBUFFERED=1`):

| input | r3 buf | r3 unbuf | r4 buf | r4 unbuf |
|---|---|---|---|---|
| regression, stdout normal | 3 | 3 | 3 | 3 |
| regression (1 case), `> /dev/full` | 120 | 2 | 2 | 2 |
| regression (1 case), `\| true` | 120 | 2 | 2 | 2 |
| regression, `>&-` | 2 | 2 | 2 | 2 |
| regression, 450 cases, `\| true` and `\| head -c1` | 2, 2 | 2, 2 | 2, 2 | 2, 2 |
| clean flagged run, `> /dev/full` | 120 | 2 | 2 | 2 |
| clean flagged run, `>&-` | 2 | 2 | 2 | 2 |
| unusable baseline, case id `"\ud800x"` (UTF-8); `"café"` (`PYTHONIOENCODING=ascii`; `LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0`) | 2 | 2 | 2 | 2 |
| unusable baseline, `> /dev/full` | 120 | 1 | 2 | 2 |
| unusable baseline, `\| true` | 120 | 1 | 2 | 2 |
| unusable baseline, `>&-` | 2 | 2 | 2 | 2 |
| unusable baseline, 10 MB case id, `\| head -c1` | 1 | 1 | 2 | 2 |
| unusable baseline, 10 MB case id, stdout normal | 2 | 2 | 2 | 2 |
| good baseline, bad benchmark, `> /dev/full` | 120 | 1 | 2 | 2 |
| good baseline, bad benchmark, `\| true` | 120 | 1 | 2 | 2 |
| good baseline, bad benchmark, stdout normal | 2 | 2 | 2 | 2 |
| regression with case id `"\ud800x"` or `"café"`, under `PYTHONIOENCODING` utf-8, ascii and latin-1, and under uncoerced `LC_ALL=C` | 3 | 3 | 3 | 3 |
| regression, stderr closed | 3 | 3 | 3 | 3 |

No `--baseline` (pre-edit runner, `7098425263ba…b7ce60`, versus r4):

| input | pre buf | pre unbuf | r4 buf | r4 unbuf |
|---|---|---|---|---|
| failing run; passing run, stdout normal | 1; 0 | 1; 0 | 1; 0 | 1; 0 |
| failing run; passing run, `> /dev/full` | 120; 120 | 1; 1 | 120; 120 | 1; 1 |
| failing run; passing run, `>&-` | 1; 0 | 1; 0 | 1; 0 | 1; 0 |
| failing run, 450 cases, `\| true` | 1 | 1 | 1 | 1 |
| bad benchmark, stdout normal; `> /dev/full` | 2; 120 | 2; 1 | 2; 120 | 2; 1 |

Without `--baseline`, the stdout plus stderr of a failing run, a passing run and a bad benchmark is identical between r3 and r4 in both modes, once the `duration_s` lines are removed. Compared with the pre-edit runner, the only difference is the `"schema_version": 1` line (Decision 4).

**Totals across revisions:**

| item | r0 | r1 | r2 | r3 | r4 |
|---|---|---|---|---|---|
| tests in `tests/test_evals_baseline.py` | 66 | 76 | 84 | 91 | 95 |
| repo suite after the edit (before: 1222 passed, 10 skipped) | 1288 | 1298 | 1306 | 1313 | 1317 passed, 10 skipped |
| mutants, all killed | 38 | 50 | 59 | 66 | 75 |
| `runner.py` lines (pre-edit 210) | 275 | 302 | 310 | 311 | 323 |
| test file lines | 312 | 404 | 460 | 520 | 558 |

## Changes in revision 3

Judge round 3 (`_workspace/02_adversarial-risk-judge_C4_r3.md`) gave UPHELD 22 / REJECTED 1 (A13). Daniel authorised round 4 on 2026-10-03. Before changing anything, I re-ran every input in the rejection on a scratch copy of the r2 files. All of them reproduced, and none is disputed:
- A regression run with stdout closed (`>&-`) exited 1. Python sets `sys.stdout = None`, so `print` does nothing, and `sys.stdout.flush()` raises `AttributeError`, which `except OSError` did not catch.
- An unusable baseline exited 1 when its message could not be encoded: case id `"\ud800x"` in the default UTF-8 locale, and `"café"` under `PYTHONIOENCODING=ascii` or under `LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0`.
- The judge's K20 (`ensure_ascii=False` on the guarded print) survived all 130 tests.

Changed claim: **A13** only (marked `CHANGED r3`). Every other Authority row is byte-identical to revision 2 (the check is in § Authority List). The scope is the judge's two-line fix plus two test notes. Nothing else changes.

| finding | fix in `runner.py` | new test | new mutants (all killed) |
|---|---|---|---|
| A13(a): a closed stdout makes a flagged regression exit 1 | Report guard `except OSError:` becomes `except Exception:  # noqa: BLE001`. `KeyboardInterrupt` and `SystemExit` are not `Exception` subclasses, so they still propagate. | `test_closed_stdout_with_baseline_exit_2`: with `--baseline` the regression gives 2; the same run without the flag gives 1, as before. `test_keyboard_interrupt_during_report_write_propagates` | M60 (narrowed back to `OSError`), M63 (widened to `BaseException`) |
| A13(b): an unencodable message makes an unusable baseline exit 1 | `_baseline_failed` prints `msg.encode("ascii", "backslashreplace").decode("ascii")` | `test_unencodable_case_id_in_bad_baseline_exit_2` (capsys, `"\ud800x"`) and `test_non_ascii_case_id_in_bad_baseline_ascii_stdout_exit_2` (subprocess, `PYTHONIOENCODING=ascii`, `"café"`) | M61 (escaping removed) |
| A13(c): K20 survived | None. The report already uses the `json.dumps` default `ensure_ascii=True`; the new test pins it. | `test_surrogate_case_id_regression_exit_3` | M62 = K20 |
| test note: K18 survived | None | `test_removed_ids_sorted` (3 removed ids, given in reverse order) | M64 = K18 |
| test note: K13 and K14 survived | None. The behaviour is the one stated in Decision 3 (fail closed). | `test_clean_flagged_run_with_lost_report_exit_2` | M65 = K13, M66 = K14 |

`BadStdout.__init__` now takes `exc: BaseException` instead of `OSError`, so that the KeyboardInterrupt test can reuse the class. Only the annotation changes.

Real-process check (`python -m master_finhub.evals.runner`, r2 copy versus r3 copy). Re-measured in revision 4 in both modes, because the r3 figures were taken under `PYTHONUNBUFFERED=1` only (buf = `env -u PYTHONUNBUFFERED`; unbuf = `PYTHONUNBUFFERED=1`):

| input | r2 buf | r2 unbuf | r3 buf | r3 unbuf |
|---|---|---|---|---|
| regression, stdout normal | 3 | 3 | 3 | 3 |
| regression, `>&-` | 1 | 1 | 2 | 2 |
| regression, `> /dev/full` | 120 | 2 | 120 | 2 |
| clean flagged run, `>&-` | 1 | 1 | 2 | 2 |
| clean flagged run, `> /dev/full` | 120 | 2 | 120 | 2 |
| unusable baseline, case id `"\ud800x"`, UTF-8 | 1 | 1 | 2 | 2 |
| unusable baseline, case id `"café"`, `PYTHONIOENCODING=ascii` | 1 | 1 | 2 | 2 |
| unusable baseline, case id `"café"`, `LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0` | 1 | 1 | 2 | 2 |
| unusable baseline, `>&-` | 2 | 2 | 2 | 2 |
| regression with case id `"\ud800x"` or `"café"`, under `PYTHONIOENCODING` utf-8, ascii and latin-1, and under uncoerced `LC_ALL=C` | 3 | 3 | 3 | 3 |
| no `--baseline`: failing run normal, `>&-`, `/dev/full`; passing run `>&-`, `/dev/full` | 1, 1, 120; 0, 120 | 1, 1, 1; 0, 1 | 1, 1, 120; 0, 120 | 1, 1, 1; 0, 1 |

**Found while probing in r3; closed in revision 4.** An unusable baseline with stdout on `/dev/full` exits 1 under `PYTHONUNBUFFERED=1` and 120 in CPython's default mode, in r2 and r3 alike. The `print` inside `_baseline_failed` raises `OSError` itself. The existing bad-benchmark exit-2 path does the same: `print(str(exc))` at pre-edit runner.py:203. Revision 4 guards the message print and routes the flagged bad-benchmark path through it (§ Changes in revision 4).

**Totals across revisions (r0-r3, historical; the current figures are in § Changes in revision 4):**

| item | r0 | r1 | r2 | r3 |
|---|---|---|---|---|
| tests in `tests/test_evals_baseline.py` | 66 | 76 | 84 | 91 |
| repo suite after the edit (before: 1222 passed, 10 skipped) | 1288 | 1298 | 1306 | 1313 passed, 10 skipped |
| mutants, all killed | 38 | 50 | 59 | 66 |
| `runner.py` lines (pre-edit 210) | 275 | 302 | 310 | 311 |
| test file lines | 312 | 404 | 460 | 520 |

## Changes in revision 2

Judge round 2 (`_workspace/02_adversarial-risk-judge_C4_r2.md`) gave UPHELD 21 / REJECTED 2. Both rejections reproduced on the scratch copy, and neither is disputed:
- a regression run with stdout on `/dev/full` exited 1 (`OSError: [Errno 28]` from the report `print`);
- the judge's mutants J19 (`sort_keys=True`) and J31 (`schema_version` placed last) were not covered by any test.

Changed claims: **A13 and A17** (marked `CHANGED r2`). All other Authority rows are byte-identical to revision 1; the check is in § Authority List. No behaviour is added beyond the report-write guard.

| finding | fix | new or changed test | new mutants (all killed) |
|---|---|---|---|
| A13: a detected regression exits 1 when the report write fails (full disk, closed pipe) | With `--baseline` only, `main` puts the report `print` **and** an explicit `sys.stdout.flush()` inside `try/except OSError` and returns 2. `BrokenPipeError` is a subclass of `OSError`. Without `--baseline`, the code path is byte-for-byte the old one: a bare `print` and `return code`. | `test_lost_report_with_baseline_exit_2` and `test_lost_report_without_baseline_unchanged`, 4 cases each: OSError and BrokenPipeError on write and on flush | M51 guard removed, M52 guard widened to all runs, M53 returns `code`, M54 returns 1, M55 flush removed, M56 only `BrokenPipeError` caught |
| A13: a benchmark nested 100k deep exits 1 | No code change (`load_benchmark` is outside C4's diff). A13 now says that a crash inside `run_suite`/`load_benchmark` exits 1 as before, as a documented follow-up. | n/a | n/a |
| A17: printed report order untested | No code change | The proof flip test asserts `next(iter(out)) == "schema_version"` and `tuple(out["comparison"]) == <literal tuple>`; the no-flag test asserts `schema_version` comes first | M57 = J19 on the `--baseline` print, M58 = J19 on the no-flag print, M59 = J31 |
| A17, found while reproducing: M27 (unsorted buckets) **survived** one random-seed run. The old sorted test had only 2 ids per bucket, so an unsorted set came out sorted by chance about 1 time in 4; the earlier kills were luck | No code change | `test_buckets_sorted_and_key_order_fixed` also asserts 20 reverse-ordered ids come out sorted (chance of a lucky pass about 1 in 20!) | M27 now killed under `PYTHONHASHSEED` 0-19 and in the full random-seed run |
| hygiene | Stale figures fixed throughout; `ids=` added to the deep-nesting and duplicate-key parametrize; `-h` added to Does not cover | ids only | n/a |

Real-process check, via `python -m master_finhub.evals.runner` on a pass→fail regression. Re-measured in revision 4 in both modes, on the r1 and r2 copies (buf = `env -u PYTHONUNBUFFERED`; unbuf = `PYTHONUNBUFFERED=1`):

| stdout | r1 buf | r1 unbuf | r2 buf | r2 unbuf |
|---|---|---|---|---|
| `> /dev/full` | 120 | 1 | 120 | 2 |
| normal | 3 | 3 | 3 | 3 |
| 450 cases piped into `\| true` (`PIPESTATUS`) | 1 | 1 | 2 | 2 |
| without `--baseline`, `> /dev/full` (traceback, unchanged from before C4) | 120 | 1 | 120 | 1 |

**Totals across revisions (r0-r2, historical; the current figures are in § Changes in revision 4):**

| item | r0 | r1 | r2 |
|---|---|---|---|
| tests in `tests/test_evals_baseline.py` | 66 | 76 | 84 |
| repo suite after the edit (before: 1222 passed, 10 skipped) | 1288 | 1298 | 1306 passed, 10 skipped |
| mutants, all killed | 38 | 50 | 59 |
| `runner.py` lines (pre-edit 210) | 275 | 302 | 310 |
| test file lines | 312 | 404 | 460 |

## Changes in revision 1

Judge round 1 (`_workspace/02_adversarial-risk-judge_C4_r1.md`) gave UPHELD 18 / REJECTED 3. I re-ran every rejection on the scratch copy before changing anything, and all three reproduced:
- a baseline nested 100,000 deep exited 1 with a traceback;
- a duplicate top-level `results` key exited 0, and the dropped case `gone` was never reported;
- swapping the `BUCKETS` order survived all 112 tests.

None is disputed.

Changed claims: **A11, A13, A17** (marked `CHANGED r1`). New claims: **A22** (a repeated `--baseline` exits 2) and **A23** (a baseline that is not a regular file exits 2). All other Authority rows (A1-A10, A12, A14-A16, A18-A21) are byte-identical to revision 0; the check is in § Authority List.

| finding | fix in `runner.py` | new test | new mutant (killed) |
|---|---|---|---|
| A11(1) deep nesting escapes as `RecursionError` | `RecursionError` added to the `except` tuple in `load_baseline` | `test_deeply_nested_baseline_exit_2` (root, and inside an ignored row field) | M41 |
| A11(2) duplicate JSON keys drop or retarget rows | `json.load(fh, object_pairs_hook=_unique_keys)`, which raises `ValueError` on a repeated key at any depth | `test_duplicate_json_keys_exit_2` (top-level `results`, row `case_id`, a nested ignored object) | M39 (hook removed), M40 (hook never raises) |
| A13 a crash exits 1 | `main` wraps the baseline load and `compare` (not `run_suite`) in `except Exception`, which returns 2 through `_baseline_failed` | `test_unexpected_baseline_exception_exit_2[load_baseline / compare]` (injected `RuntimeError`) | M47, M48 (catch narrowed to `ValueError`), M49 (failure returns 1) |
| A17 order check could not fail | The test asserts against the literal tuple | `test_buckets_sorted_and_key_order_fixed` (edited) | M50 = judge's O23 |
| P7 expected 5 | The expected value is now **6**; the grep is unchanged (docstring line 7 also contains `--baseline`) | n/a | n/a |
| hardening (i): a repeated `--baseline` keeps the last | `action="append"`; more than one value raises before the suite runs, giving exit 2 | `test_repeated_baseline_flag_exit_2` | M44 (check removed), M45 (`> 2`), M46 (`> 0`) |
| hardening (ii): a FIFO baseline hangs | `os.path.isfile(path)` checked before `open` (it follows symlinks) | `test_fifo_baseline_exit_2_without_blocking` (subprocess, 60 s timeout), `test_symlink_to_regular_baseline_is_accepted` | M42 (check removed), M43 (`exists`) |
| side effect: M24 survived once the catch-all existed (a root-not-object crash became exit 2 with a generic message) | none | `test_unreadable_baseline_exit_2` also calls `load_baseline` directly and expects `ValueError` | M24 killed again |

**Changed totals (r0 → r1, historical; the current figures are in § Changes in revision 4):**

| item | revision 0 | revision 1 |
|---|---|---|
| tests in `tests/test_evals_baseline.py` | 66 | 76 |
| repo suite after the edit | 1288 passed | 1298 passed |
| mutants | 38 | 50, all killed |
| `runner.py` | 275 lines | 302 lines |
| test file | 312 lines | 404 lines |

Both hashes changed (§ Exact edit, § Test plan). The equivalent mutant `len(out) < len(pairs)` in `_unique_keys` is not counted: `dict(pairs)` can never be longer than `pairs`.

## Source

Backlog row C4: "compare with a prior report and fail on any pass→fail case". Target `evals/runner.py`, "one compare function plus a `--baseline` flag". Proof: `python -m master_finhub.evals.runner --baseline prev.json cases/`, where one case flips pass→fail, must list that case under `regressed` and exit non-zero. With no flips it must exit 0, and a new case must be listed under `new`.

I re-opened each port-map row myself:

| row | cited line | what the lines actually do |
|---|---|---|
| C24 | `references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:99` | `_compare_with_run` builds a lookup by `identifier` (:102-106) and puts each current result into `new_tests` when the baseline lacks it (:115-116). Otherwise it uses the prior `passed`: `improved` (:121), `regressed` (:123) or `unchanged` (:125-126). Baseline ids missing from the current run go to `missing_tests` (:128-133). |
| C24 context | same file :56-78 | On an unreadable or empty baseline, crewai **warns and saves the current run as the new baseline** (:65-78), so it fails open. It also writes into the baseline file (:88-92). C4 does neither: it fails closed and never writes the baseline. |
| A36 | `references/autogpt/classic/direct_benchmark/direct_benchmark/challenge_loader.py:49` | `is_regression_test` is true when a challenge is marked beaten in `challenges_already_beaten.json`. Line `:66` is only the `explore: bool = False` parameter of `load_all`. The flag filter itself is at :109-118: `maintain` keeps only regression tests (:114) and `improve` keeps the rest (:118). I cite :49 and :114, not :66. |
| A36 context | `references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:64` | A timed-out challenge is never a success (:64-65). The runner turns a timeout into `success=False` (`runner.py:97`, `:103`). Success otherwise means `score >= 0.9` (:67). C4 adopts no score threshold (see Decision 5). |
| R6 | `references/revfactory_harness/skills/harness/references/skill-testing-guide.md:135` (Apache-2.0) | Heading 4-3. Line 137 says an assertion that passes 100% in both configurations does not measure the skill's value. R6 is context only: it supports comparing outcomes per item across two runs, and the idea that "passed in both" is no signal (our `unchanged`). It is not a regression gate. Nothing in C4's behaviour depends on R6. The only R6 text used is the attribution line. |

Licences: autogpt `classic/` MIT, crewai MIT, revfactory Apache-2.0 (`references/LICENSES.md`). Nothing comes from `references/autogpt/autogpt_platform/`. No code is copied: the scan for 8-word runs shared with all three source files found 0 (see Proof P9).

### What the runtime already does (verified in `src/`)

- `src/master_finhub/evals/runner.py:196-206`: `main` takes `benchmarks` (file paths, `nargs="+"`) and prints `json.dumps(asdict(report), indent=2)` **to stdout**. No report file is written. It returns 2 on `ValueError` (bad benchmark JSON, duplicate case id, `:202-204`), 1 when any case failed and 0 otherwise (`:206`).
- `CaseResult` (`:47-56`) has `case_id, name, passed, score, timed_out, error, steps, duration_s, grading`. The report root (`SuiteReport`, `:60-65`) has `results, passed, failed, total, pass_rate`. There is no schema version.
- `case_id` (`:112-116`) is the explicit `"id"` or the first 16 hex characters of a sha256 of the canonical benchmark JSON. `run_suite` already rejects duplicate ids in the current run (`:182-189`).
- `passed` is already false for every error and timeout: `ok = not timed_out and error is None and grading is not None` and then `grading.total > 0 and grading.failed == 0` (`:165-166`). A timeout also sets `error` (`:159`).
- So a passing case always has `score == 1.0`: `pass_rate = passed/total` with `failed == 0` and `total > 0` (`verifiers.py:37-40`).
- The runner has no skipped status. A case that is not run is absent from `results`.
- CLI: only `python -m master_finhub.evals.runner` (`:209-210`). `pyproject.toml` `[project.scripts]` has `master-finhub = "master_finhub.cli:main"`, which has no evals subcommand (grep: no `evals` in `cli.py`).
- Tests: `tests/test_evals.py` (46 tests). They assert only `pass_rate` on stdout, never the exact key set (`:187-192`), so adding a top-level key is safe.

## Target

Runtime module. Exact files:

| file | change |
|---|---|
| `src/master_finhub/evals/runner.py` | edit: 3 docstring lines, 2 constants, 2 new functions (`load_baseline`, `compare`) and 3 helpers (`_unique_keys`, `_stdout_lost`, `_baseline_failed`), `main` gains `--baseline`, `schema_version` and `comparison`. Diff below. |
| `tests/test_evals_baseline.py` | new, 95 tests (full text below) |

Nothing else changes. `tests/test_evals.py`, `verifiers.py`, `benchmarks/`, `tests/fixtures/evals/`, `skills/`, `.claude/` and `scripts/` are all untouched. No new dependencies (stdlib only).

## Design

### Decision 1: the baseline is a prior report, read-only

- **Format.** The baseline is exactly what `main` prints, saved by the caller: `python -m master_finhub.evals.runner a.json b.json > prev.json`. C4 never writes the baseline (unlike crewai :88-92). Refreshing it is an explicit human or CI step.
- **Fields read.** Only `schema_version` (optional), `results[*].case_id` and `results[*].passed`. All other fields (`score`, `timed_out`, `error`, `grading`, `pass_rate` ...) are ignored. Even a `NaN` in `score` is ignored (`json.load` accepts the `NaN` token).
- **Why `passed` alone is enough.** `passed` is already false on error and timeout (runner.py:165-166). And a baseline `passed=true` is never more lenient than `false`: Decision 3 shows that `true` only adds `regressed` (exit 3) where `false` would give `still_failing` (exit 1). So a hand-edited row with `passed: true, error: "x"` can only make the gate stricter, and rejecting such a row would add a rule with no safety value.
- **Versioning.** Every report now carries `"schema_version": 1`.
  - A baseline **without** the key is read as version 1, because every report printed before C4 has exactly that shape.
  - A baseline whose key is present and not equal to 1 is **rejected** (exit 2). That covers `2`, `0`, `"1"`, `null`, `[1]` and `true`; `true` is rejected explicitly because `True == 1` in Python.
  - `1.0` is accepted (`1.0 == 1`). This is a known, harmless lenience.
- **Fail closed.** Each of the following raises `ValueError("Baseline <path>: <why>. Pass a report printed by this runner.")`. `main` then exits 2 **before the suite runs** and prints no report:
  - the path is not a regular file: missing, a directory, `""`, a FIFO or a device. This is checked with `os.path.isfile` before `open`, so a FIFO cannot block the run; a symlink to a regular file is accepted (CHANGED r1);
  - the file is unreadable, is not UTF-8, or is not JSON (including an empty file);
  - the JSON is nested too deep for the parser (`RecursionError`), anywhere, including inside a field C4 ignores (CHANGED r1);
  - any object at any depth repeats a key. `json.load` would otherwise keep the last value, so a repeated `results` or `case_id` key could silently drop or retarget a row. `object_pairs_hook=_unique_keys` raises instead (CHANGED r1);
  - the root is not an object;
  - `schema_version` is wrong;
  - `results` is missing, is not a list, or is **empty**. An empty baseline would turn every case into `new` and silently disable the regression gate, so it is refused.
  - a row is not an object;
  - `case_id` is not a non-empty string;
  - `passed` is not a JSON boolean (`1`, `0`, `"true"` and `null` are rejected);
  - a `case_id` is duplicated, whether the rows agree or not.

  crewai does the opposite: it warns and re-baselines (:65-78).

### Decision 2: buckets (sorted, fixed key order)

`compare(baseline, results)` takes the union of case ids from both runs, iterates it in `sorted()` order, and puts each id into exactly one bucket. The buckets are kept in the fixed order `BUCKETS = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")`, and each bucket list is sorted by `case_id`. So the `comparison` object is deterministic for the same inputs. Report `results` keep their input order, as before.

| baseline | current | bucket | fails the run? |
|---|---|---|---|
| pass | pass | `unchanged` | no |
| pass | fail | `regressed` | **yes, exit 3** |
| pass | error (exception, sandbox denial, step limit) | `regressed` | **yes, exit 3**: an errored case that was passing never passes silently |
| pass | timeout | `regressed` | **yes, exit 3** |
| fail / error / timeout | pass | `fixed` | no |
| fail / error / timeout | fail / error / timeout | `still_failing` | exit 1 (the existing any-failure rule) |
| absent | pass | `new` | no |
| absent | not pass | `new` | exit 1 (the existing rule) |
| pass or not pass | absent | `removed` | **yes, exit 3** |
| (skipped) | | n/a | The runner has no skipped status. A case not run is absent, so it lands in `removed` and exit 3. |

Error and timeout are not separate buckets. Both already mean `passed=false`, and the per-case `timed_out` and `error` fields stay in `results` for diagnosis. Splitting them would add labels with no verdict effect, and so mutants that are equivalent by construction.

`removed` fails the run whatever the baseline status was. Deleting a benchmark file, or passing fewer files, must not be a quiet way out of a regression. The same applies to editing a hash-id benchmark: its `case_id` changes, so it shows as `removed` + `new` (see Does not cover). To retire a case on purpose, refresh the baseline.

### Decision 3: exit codes (the baseline can only raise the code)

| code | meaning | precedence |
|---|---|---|
| 2 | unusable input: a bad benchmark or duplicate id (existing), or an unusable baseline (new) | highest; the suite does not run when the baseline is bad |
| 3 | `--baseline` given and `regressed` or `removed` is non-empty | over 1 |
| 1 | any current case failed, with no regression or removal (existing rule, unchanged) | |
| 0 | every current case passed and, with `--baseline`, nothing regressed or was removed | |

Invariant: with `--baseline`, the exit code is the code without it, or 3, or 2 when the baseline is unusable or the report cannot be written (CHANGED r2). **The baseline never lowers an exit code.** A run with a known-failing case still exits 1. There is no allow-known-failures mode; see Does not cover. The backlog says "with no flips the exit is 0". That holds when every current case passes, which is what the proof test uses.

**Catch-all (CHANGED r1).** Any exception raised while loading the baseline or running `compare` returns 2 through `_baseline_failed`. A `ValueError` prints its own `Baseline <path>: ...` message; anything else prints `Baseline unusable (<ExceptionName>).`. The message is printed ASCII-escaped (`backslashreplace`, CHANGED r3), so a `case_id` or path that stdout cannot encode still exits 2. The message `print` and an explicit `sys.stdout.flush()` sit inside `try/except Exception`, which returns `_stdout_lost()` (2), so an unwritable stdout cannot turn the 2 into 1 or 120 (CHANGED r4). `run_suite` stays under its existing `except ValueError`. With `--baseline`, that branch now returns through `_baseline_failed` (CHANGED r4); without it, the old `print(str(exc))` and `return 2` are untouched. So nothing on the baseline path can produce exit 0 or 1 by crashing. A crash inside `run_suite` or `load_benchmark` is not on the baseline path: it exits 1 as before (for example a benchmark file nested 100,000 deep, because `load_benchmark` catches only `(OSError, json.JSONDecodeError)`). That is a documented follow-up outside C4's diff.

**Report write guard (CHANGED r3).** With `--baseline`, the report `print` and an explicit `sys.stdout.flush()` sit inside `try/except Exception`, and any failure returns `_stdout_lost()`, which is 2. That covers an `OSError` (including `BrokenPipeError`), and the `AttributeError` raised when `sys.stdout` is `None` because fd 1 was closed (`>&-`). `KeyboardInterrupt` and `SystemExit` are not `Exception` subclasses, so they still propagate. Nothing is printed on that path, because stdout is the thing that failed. `_stdout_lost()` (CHANGED r4) first points `sys.stdout` at `os.devnull`. CPython block-buffers stdout to a file or pipe by default. Without that swap, the bytes left in the buffer are flushed again at interpreter exit, that flush fails again, and CPython replaces the returned 2 with exit 120. With `PYTHONUNBUFFERED=1` there is no such buffer, so the swap matters only in the default mode; both modes give 2 (§ Changes in revision 4). For an in-process caller of `main`, `sys.stdout` stays on devnull after a lost write. A full disk, a closed pipe or a closed stdout therefore cannot turn a detected regression (3) into 1. A clean or still-failing flagged run whose report is lost also exits 2. That is fail closed: a gate that printed nothing must not report success. Runs without `--baseline` keep their exact previous code path. **A repeated `--baseline`** (`action="append"`, more than one value) is an error, exit 2 before the suite runs, rather than "last one wins" (A22).

`argparse` usage errors still raise `SystemExit(2)`, as before. `--baseline ""` is treated as a given path, not as absent: the check is `is None`, not falsiness, so an empty path exits 2 and cannot silently disable the gate.

### Decision 4: report fields added

- Always: a top-level `"schema_version": 1`, first key.
- With `--baseline` only: `"comparison": {"regressed": [...], "removed": [...], "fixed": [...], "still_failing": [...], "unchanged": [...], "new": [...]}`. Each list holds case ids.
- `SuiteReport` and `CaseResult` are unchanged. Both fields are added in `main` only, so `run_suite` callers see no change.
- A report printed with `comparison` is itself a valid baseline (`comparison` is ignored on read).

### Decision 5: scores and tolerance: none (by construction)

C4 compares `passed` only. No score threshold is adopted: not autogpt's `score >= 0.9` (evaluator.py:67), and not a delta tolerance. The runner's `passed` already requires every expectation to hold (runner.py:166), so a passing case has `score == 1.0` exactly, and a pass→pass score drop cannot happen. Score changes inside `still_failing` (for example 0.8 → 0.5) are not gated. That means there is no threshold boundary to be off by one. The only numeric boundary is "at least one regressed or removed id". Its off-by-one mutants in both directions (`> 1` and `>= 0`) are M5 and M6, and both are killed. NaN, inf and None in `score` are never read. `passed: null` and `passed: NaN` are not booleans and are rejected.

### Decision 6: call sites

There are exactly two:
1. `main` → `load_baseline(args.baseline[0])`, after the repeated-flag check, inside its own `try/except Exception` (exit 2), **before** `run_suite` (CHANGED r1).
2. `main` → `compare(base, report.results)`, after the suite, inside its own `try/except Exception` (exit 2) (CHANGED r1).

`__main__` (`raise SystemExit(main())`, unchanged) is the CLI entry point, and a subprocess test proves it. `run_suite` and `run_case` receive nothing new: the baseline never reaches the agent (see G6).

### Interface (the contract boundary-qa checks)

```python
# src/master_finhub/evals/runner.py
SCHEMA_VERSION = 1
BUCKETS = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]: ...  # json object_pairs_hook; ValueError on a repeated key
def load_baseline(path: str | os.PathLike[str]) -> dict[str, bool]: ...
def compare(baseline: dict[str, bool], results: Sequence[CaseResult]) -> dict[str, list[str]]: ...
def _stdout_lost() -> int: ...  # points sys.stdout at os.devnull (no exit-time 120), returns 2
def _baseline_failed(exc: Exception) -> int: ...  # prints the reason ASCII-escaped, returns 2
def main(argv: list[str] | None = None) -> int: ...  # gains --baseline (at most once); exit 0/1/2/3
```

### Exact edit to `src/master_finhub/evals/runner.py` [simulated; black, ruff, mypy --strict clean]

Post-edit sha256 of the simulated file: `5c447a4d0c707d7403e48da20fdebd3d051f56e29b81819362058cb7c57aa21a` (323 lines, CHANGED r4). The pre-edit file is `7098425263ba81ec469cb5da6095b3b79591eb42c9ac91ea657dbbd485b7ce60`. If the builder's pre-edit hash differs, it stops and reports.

```diff
--- a/src/master_finhub/evals/runner.py
+++ b/src/master_finhub/evals/runner.py
@@ -4,6 +4,9 @@
 workspace), :88-106 (timeout/exception -> failed result), evaluator.py:36,64 (dispatch on
 eval type; timed-out never passes) and crewai experiment/runner.py:67-72 (stable id, per-case try).
 Only `task` reaches the agent; `ground` (the answer key) never does.
+Baseline buckets (--baseline) adapted (MIT, own code) from crewai experiment/result.py:99-143
+and autogpt classic direct_benchmark challenge_loader.py:49. Comparing with a prior run follows
+revfactory skill-testing-guide.md:135 (Apache-2.0).
 """
 
 from __future__ import annotations
@@ -14,6 +17,7 @@
 import math
 import os
 import shutil
+import sys
 import tempfile
 import time
 from collections.abc import Callable, Sequence
@@ -28,6 +32,9 @@
 from master_finhub.tools.builtins.echo import EchoTool
 from master_finhub.tools.safety import guard_tool_call
 
+SCHEMA_VERSION = 1
+BUCKETS = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
+
 
 class _CutoffReached(Exception):
     pass
@@ -193,17 +200,123 @@
     return SuiteReport(results, passed, total - passed, total, passed / total if total else 0.0)
 
 
+def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
+    out = dict(pairs)
+    if len(out) != len(pairs):
+        raise ValueError("duplicate JSON key")
+    return out
+
+
+def load_baseline(path: str | os.PathLike[str]) -> dict[str, bool]:
+    """Prior report -> {case_id: passed}. Anything unusable raises ValueError (fail closed)."""
+
+    def bad(why: str) -> ValueError:
+        return ValueError(f"Baseline {path}: {why}. Pass a report printed by this runner.")
+
+    if not os.path.isfile(path):  # follows symlinks; a FIFO or device would block on read
+        raise bad("not a regular file")
+    try:
+        with open(path, encoding="utf-8") as fh:
+            data = json.load(fh, object_pairs_hook=_unique_keys)
+    except (OSError, ValueError, RecursionError) as exc:
+        raise bad(f"cannot read ({type(exc).__name__})") from None
+    if not isinstance(data, dict):
+        raise bad("root must be a JSON object")
+    version = data.get("schema_version", SCHEMA_VERSION)
+    if isinstance(version, bool) or version != SCHEMA_VERSION:
+        raise bad(f"schema_version must be {SCHEMA_VERSION}")
+    rows = data.get("results")
+    if not isinstance(rows, list) or not rows:
+        raise bad('"results" must be a non-empty list')
+    out: dict[str, bool] = {}
+    for row in rows:
+        if not isinstance(row, dict):
+            raise bad("each result must be a JSON object")
+        cid, passed = row.get("case_id"), row.get("passed")
+        if not isinstance(cid, str) or not cid:
+            raise bad("each case_id must be a non-empty string")
+        if not isinstance(passed, bool):
+            raise bad(f'case "{cid}": passed must be true or false')
+        if cid in out:
+            raise bad(f'duplicate case id "{cid}"')
+        out[cid] = passed
+    return out
+
+
+def compare(baseline: dict[str, bool], results: Sequence[CaseResult]) -> dict[str, list[str]]:
+    """Bucket every case id seen in either run; each bucket is sorted by case id."""
+    now = {r.case_id: r.passed for r in results}
+    out: dict[str, list[str]] = {b: [] for b in BUCKETS}
+    for cid in sorted(now.keys() | baseline.keys()):
+        if cid not in baseline:
+            key = "new"
+        elif cid not in now:
+            key = "removed"
+        elif baseline[cid]:
+            key = "unchanged" if now[cid] else "regressed"
+        else:
+            key = "fixed" if now[cid] else "still_failing"
+        out[key].append(cid)
+    return out
+
+
+def _stdout_lost() -> int:
+    """Park stdout on devnull so the exit-time flush cannot turn this 2 into 120."""
+    sys.stdout = open(os.devnull, "w", encoding="ascii")  # noqa: SIM115
+    return 2
+
+
+def _baseline_failed(exc: Exception) -> int:
+    msg = str(exc) if isinstance(exc, ValueError) else f"Baseline unusable ({type(exc).__name__})."
+    try:
+        print(msg.encode("ascii", "backslashreplace").decode("ascii"))  # ids may not encode
+        sys.stdout.flush()
+    except Exception:  # noqa: BLE001 - stdout lost; still exit 2, never 1
+        return _stdout_lost()
+    return 2
+
+
 def main(argv: list[str] | None = None) -> int:
     ap = argparse.ArgumentParser(prog="master_finhub.evals.runner")
     ap.add_argument("benchmarks", nargs="+")
+    ap.add_argument(
+        "--baseline", action="append", help="prior report JSON, once; exit 3 on regressed/removed"
+    )
     args = ap.parse_args(argv)
+    base: dict[str, bool] | None = None
+    if args.baseline is not None:
+        try:
+            if len(args.baseline) > 1:
+                raise ValueError("Baseline given more than once. Pass one prior report.")
+            base = load_baseline(args.baseline[0])
+        except Exception as exc:  # noqa: BLE001 - any baseline failure is exit 2, never 0 or 1
+            return _baseline_failed(exc)
     try:
         report = run_suite(args.benchmarks)
     except ValueError as exc:
+        if base is not None:
+            return _baseline_failed(exc)
         print(str(exc))
         return 2
-    print(json.dumps(asdict(report), indent=2))
-    return 0 if report.failed == 0 else 1
+    out: dict[str, Any] = {"schema_version": SCHEMA_VERSION, **asdict(report)}
+    code = 0 if report.failed == 0 else 1
+    if base is not None:
+        try:
+            buckets = compare(base, report.results)
+        except Exception as exc:  # noqa: BLE001 - same fail-closed rule as the load
+            return _baseline_failed(exc)
+        out["comparison"] = buckets
+        if buckets["regressed"] or buckets["removed"]:
+            code = 3
+    if base is None:
+        print(json.dumps(out, indent=2))
+        return code
+    try:  # a lost report must not let a detected regression exit 1
+        print(json.dumps(out, indent=2))
+        sys.stdout.flush()
+    except Exception:  # noqa: BLE001 - OSError, or stdout None (closed fd 1); not KeyboardInterrupt
+        return _stdout_lost()
+    return code
 
 
 if __name__ == "__main__":
```

The `except (OSError, ValueError, RecursionError)` is deliberate:
- `json.JSONDecodeError`, `UnicodeDecodeError` and the duplicate-key error from `_unique_keys` are all `ValueError` subclasses.
- `RecursionError` is what the C JSON scanner raises on deep nesting.
- Narrowing the tuple still exits 2 through the catch-all, but with the generic message. M22, M23 and M41 are killed by the message checks. The attribution is the three added docstring lines, which name all three sources with their licences.

### Quant guardrails (`.claude/skills/adversarial-audit/references/quant-guardrails.md`)

| # | guardrail | ruling | reason |
|---|---|---|---|
| G1 | Transaction fees | N/A | C4 compares boolean outcomes of string-match benchmarks. It computes no returns or P&L, and no trades exist. |
| G2 | Borrow costs | N/A | No positions, shorts or leverage. |
| G3 | Slippage | N/A | No fills or prices. |
| G4 | Look-ahead leakage | N/A for prices. Analogue held: the baseline is read only in `main` and handed only to `compare` after `run_suite` returns, so no agent step can see it. Check: `grep -c "run_suite(args.benchmarks)" src/master_finhub/evals/runner.py` = 1, and `run_suite`/`run_case` signatures are unchanged (the diff touches neither). |
| G5 | Survivorship bias | N/A for prices. Analogue held: a baseline case missing from the current run is not dropped from view. It is listed in `removed` and fails the run (exit 3), so a suite cannot improve its record by losing its failing or regressed cases. Killed mutants: M4, M26, M35, M36. |
| G6 | Train/test leakage | N/A for splits. Analogue held: the answer key (`ground`) and the baseline both stay out of the agent's context. `ground` is protected by the existing `test_agent_never_sees_ground`, which must still pass. The baseline is protected structurally, as in G4. Verifiers are unchanged and deterministic (`verifiers.py:1`). |

## Proof

The builder runs these in the repo after the edit and pastes the output. The expected values were measured on the scratch copy, except the repo-only counts, which are marked.

| # | command | expected |
|---|---|---|
| P1 | `pytest -q tests/test_evals_baseline.py` | `95 passed` (CHANGED r4) |
| P2 | `pytest -q tests/test_evals.py` (unmodified) | `46 passed` |
| P3 | `pytest -q` (whole repo) | before: `1222 passed, 10 skipped` (measured in the repo 2026-10-03). After: `1317 passed, 10 skipped` (CHANGED r4; measured on a full-tree scratch copy with the r4 files: 1317 passed, 10 skipped, in a pytest process started in each mode; before, on the same copy: 1222 passed, 10 skipped, in each mode) |
| P4 | `mypy --strict src` | `Success: no issues found in 38 source files` |
| P5 | `ruff check src tests` and `black --check src tests` | `All checks passed!` / `67 files would be left unchanged` |
| P6 | `bash scripts/check-harness-refs.sh` and `bash scripts/package-plugin.sh` | Exit 0; output identical to the pre-edit run. `git diff --stat -- skills .claude scripts .claude-plugin` is empty. |
| P7 | `grep -c "def load_baseline\|def compare\|--baseline\|SCHEMA_VERSION = 1\|^BUCKETS = " src/master_finhub/evals/runner.py` | `6` (CHANGED r1: I corrected the expected value and kept the grep; the 6 hits are the docstring at line 7, `SCHEMA_VERSION = 1`, `BUCKETS = `, `def load_baseline`, `def compare` and the `"--baseline"` argument) |
| P8 | Hangul count (code points U+AC00-U+D7A3, U+1100-U+11FF, U+3130-U+318F) in `runner.py` and `tests/test_evals_baseline.py` | `0` and `0` |
| P9 | Shared 8-token runs (lower-cased `[A-Za-z0-9_]+`) between the added lines plus the new test file and each of `result.py`, `challenge_loader.py` and `skill-testing-guide.md` | `0`, `0`, `0` (measured) |
| P10 | `grep -c "autogpt_platform" src/master_finhub/evals/runner.py tests/test_evals_baseline.py` | `0`, `0` |
| P11 | `sha256sum src/master_finhub/evals/runner.py` | `5c447a4d…7cb57aa21a` (§ Exact edit, CHANGED r4) |
| P12 | Backlog proof by hand, with synthetic files in a temp dir: run a passing benchmark with `"id": "flip"` and save its stdout as `prev.json`; then `python -m master_finhub.evals.runner --baseline prev.json flip_fail.json` | exit `3`, `comparison.regressed == ["flip"]`. Re-run with the passing file: exit `0`, `unchanged == ["flip"]`. Add a second passing file: exit `0`, `new` lists its id. The backlog's `cases/` directory argument is not supported (the positional is files, `nargs="+"`); pass the files or a shell glob (`cases/*.json`). |
| P13 | Regexes added | none (`import re` is absent from `runner.py`), so no ReDoS sweep is needed |

## Test plan

### New file `tests/test_evals_baseline.py` (95 tests; synthetic data only) [simulated: all pass, ruff and black clean]

Post-edit sha256: `3554b065c729d42a5388edb3fc7a075e6e32f118c08b5bf4bf33ec99ca4250a0` (558 lines, CHANGED r4). The benchmarks are the repo's own synthetic `echo_pass.json` / `echo_fail.json` with an `"id"` added. Error is produced through the existing sandbox denial (`files: ["../../etc/passwd"]`, as `tests/test_evals.py:122-124` already does) and timeout through `cutoff_s: 0`.

```python
"""C4 proof tests: eval baseline compare and regression buckets (synthetic data only)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from master_finhub.evals.runner import (
    BUCKETS,
    SCHEMA_VERSION,
    CaseResult,
    compare,
    load_baseline,
    main,
)

PASS = Path(__file__).parent.parent / "src/master_finhub/evals/benchmarks/echo_pass.json"
FAIL = Path(__file__).parent / "fixtures/evals/echo_fail.json"
SRC = Path(__file__).parent.parent / "src"


def bench(tmp_path: Path, name: str, outcome: str, case_id: str = "c1") -> str:
    """Write a benchmark that ends in `outcome` (pass / fail / error / timeout)."""
    data: dict[str, Any] = json.loads((FAIL if outcome == "fail" else PASS).read_text())
    data["id"] = case_id
    if outcome == "error":
        data["ground"]["files"] = ["../../etc/passwd"]  # SandboxDenied -> error, not passed
    if outcome == "timeout":
        data["cutoff_s"] = 0
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return str(p)


def baseline(tmp_path: Path, rows: Any, **top: Any) -> str:
    p = tmp_path / "prev.json"
    p.write_text(json.dumps({"results": rows, **top}))
    return str(p)


def row(case_id: str, passed: bool) -> dict[str, Any]:
    return {"case_id": case_id, "passed": passed, "timed_out": False, "error": None}


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, Any]:
    code = main(list(argv))
    out = capsys.readouterr().out
    return code, (json.loads(out) if code != 2 else out)


def result(case_id: str, passed: bool) -> CaseResult:
    return CaseResult(case_id, case_id, passed, 1.0 if passed else 0.0, False, None, 1, 0.0, None)


# --- proof (backlog row C4) -------------------------------------------------------------


def test_proof_flip_pass_to_fail_is_regressed_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, first = run(capsys, bench(tmp_path, "a.json", "pass", "flip"))
    assert code == 0
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(first))  # a real report from this runner is a valid baseline
    code, out = run(capsys, "--baseline", str(prev), bench(tmp_path, "b.json", "fail", "flip"))
    assert code == 3
    assert out["comparison"]["regressed"] == ["flip"]
    assert next(iter(out)) == "schema_version"
    order = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
    assert tuple(out["comparison"]) == order


def test_proof_no_flips_exit_0(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    p = bench(tmp_path, "a.json", "pass", "same")
    _, first = run(capsys, p)
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(first))
    code, out = run(capsys, "--baseline", str(prev), p)
    assert code == 0
    assert out["comparison"]["unchanged"] == ["same"] and out["comparison"]["regressed"] == []


def test_proof_new_case_listed_under_new(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("old", True)])
    code, out = run(
        capsys,
        "--baseline",
        prev,
        bench(tmp_path, "a.json", "pass", "old"),
        bench(tmp_path, "b.json", "pass", "fresh"),
    )
    assert code == 0
    assert out["comparison"]["new"] == ["fresh"]


def test_cli_module_entry_point_exit_3(tmp_path: Path) -> None:
    prev = baseline(tmp_path, [row("flip", True)])
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-m", "master_finhub.evals.runner", "--baseline", prev,
         bench(tmp_path, "b.json", "fail", "flip")],
        capture_output=True, text=True, env=env, check=False, timeout=120,
    )  # fmt: skip
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["comparison"]["regressed"] == ["flip"]


# --- every transition -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("was", "now", "bucket"),
    [
        (True, True, "unchanged"),
        (True, False, "regressed"),
        (False, True, "fixed"),
        (False, False, "still_failing"),
        (None, True, "new"),
        (None, False, "new"),
        (True, None, "removed"),
        (False, None, "removed"),
    ],
)
def test_compare_transition(was: bool | None, now: bool | None, bucket: str) -> None:
    base = {} if was is None else {"x": was}
    results = [] if now is None else [result("x", now)]
    got = compare(base, results)
    assert got == {b: (["x"] if b == bucket else []) for b in BUCKETS}


@pytest.mark.parametrize(
    ("was", "now", "code", "bucket"),
    [
        (True, "pass", 0, "unchanged"),
        (True, "fail", 3, "regressed"),
        (True, "error", 3, "regressed"),
        (True, "timeout", 3, "regressed"),
        (False, "pass", 0, "fixed"),
        (False, "fail", 1, "still_failing"),
        (False, "error", 1, "still_failing"),
        (False, "timeout", 1, "still_failing"),
    ],
)
def test_main_transition_exit_code(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    was: bool,
    now: str,
    code: int,
    bucket: str,
) -> None:
    prev = baseline(tmp_path, [row("c1", was)])
    got, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", now))
    assert got == code
    assert out["comparison"][bucket] == ["c1"]


def test_removed_passing_case_fails_run(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    prev = baseline(tmp_path, [row("c1", True), row("gone", True)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "pass"))
    assert code == 3 and out["comparison"]["removed"] == ["gone"]


def test_removed_failing_case_fails_run(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    prev = baseline(tmp_path, [row("c1", True), row("gone", False)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "pass"))
    assert code == 3 and out["comparison"]["removed"] == ["gone"]


def test_new_failing_case_is_new_and_exit_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    code, out = run(
        capsys,
        "--baseline",
        prev,
        bench(tmp_path, "a.json", "pass"),
        bench(tmp_path, "b.json", "fail", "c2"),
    )
    assert code == 1 and out["comparison"]["new"] == ["c2"]
    assert out["comparison"]["regressed"] == [] and out["comparison"]["removed"] == []


def test_exactly_one_regression_among_many_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    ids = ["a", "b", "c", "d"]
    prev = baseline(tmp_path, [row(i, True) for i in ids])
    files = [bench(tmp_path, f"{i}.json", "fail" if i == "c" else "pass", i) for i in ids]
    code, out = run(capsys, "--baseline", prev, *files)
    assert code == 3 and out["comparison"]["regressed"] == ["c"]
    assert out["comparison"]["unchanged"] == ["a", "b", "d"]


def test_regression_outranks_other_failures(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("a", True), row("b", False)])
    files = [bench(tmp_path, "a.json", "fail", "a"), bench(tmp_path, "b.json", "fail", "b")]
    code, _ = run(capsys, "--baseline", prev, *files)
    assert code == 3


def test_baseline_never_lowers_exit_code(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    f = bench(tmp_path, "a.json", "fail")
    assert run(capsys, f)[0] == 1
    for was in (True, False):
        assert run(capsys, "--baseline", baseline(tmp_path, [row("c1", was)]), f)[0] in (1, 3)


def test_buckets_sorted_and_key_order_fixed() -> None:
    base = {"z": True, "b": True, "m": False}
    results = [result("z", False), result("b", False), result("y", True), result("a", True)]
    got = compare(base, results)
    order = ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
    assert BUCKETS == order and tuple(got) == order
    assert got["regressed"] == ["b", "z"] and got["new"] == ["a", "y"]
    assert got["removed"] == ["m"]
    many = [f"c{i:02d}" for i in range(20)]  # 20 ids: a set never iterates sorted by luck
    assert compare({}, [result(c, True) for c in reversed(many)])["new"] == many


def test_report_has_schema_version_and_no_comparison_without_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = run(capsys, str(PASS))
    assert code == 0 and out["schema_version"] == SCHEMA_VERSION == 1
    assert next(iter(out)) == "schema_version"
    assert "comparison" not in out


def test_old_report_without_schema_version_is_accepted(tmp_path: Path) -> None:
    assert load_baseline(baseline(tmp_path, [row("a", True)])) == {"a": True}
    assert load_baseline(baseline(tmp_path, [row("a", False)], schema_version=1)) == {"a": False}


def test_extra_fields_are_ignored(tmp_path: Path) -> None:
    p = tmp_path / "prev.json"
    p.write_text('{"results": [{"case_id": "a", "passed": true, "score": NaN}], "x": 1}')
    assert load_baseline(p) == {"a": True}


# --- unusable baseline fails closed (exit 2, suite never reported) -----------------------

BAD_ROWS: list[Any] = [
    [],
    {},
    None,
    "x",
    ["x"],
    [None],
    [{"passed": True}],
    [{"case_id": "", "passed": True}],
    [{"case_id": 5, "passed": True}],
    [{"case_id": None, "passed": True}],
    [{"case_id": "a"}],
    [{"case_id": "a", "passed": None}],
    [{"case_id": "a", "passed": "true"}],
    [{"case_id": "a", "passed": 1}],
    [{"case_id": "a", "passed": 0}],
    [row("a", True), row("a", True)],
    [row("a", True), row("a", False)],
]


@pytest.mark.parametrize("rows", BAD_ROWS)
def test_bad_rows_exit_2(capsys: pytest.CaptureFixture[str], tmp_path: Path, rows: Any) -> None:
    code, out = run(capsys, "--baseline", baseline(tmp_path, rows), str(PASS))
    assert code == 2 and out.startswith("Baseline ")
    with pytest.raises(ValueError, match="Baseline"):
        load_baseline(tmp_path / "prev.json")


@pytest.mark.parametrize("version", [2, 0, True, "1", None, [1]])
def test_other_schema_version_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, version: Any
) -> None:
    prev = baseline(tmp_path, [row("c1", True)], schema_version=version)
    code, out = run(capsys, "--baseline", prev, str(PASS))
    assert code == 2 and "schema_version" in out


@pytest.mark.parametrize(
    "content", [b"", b"{", b"{}", b"[]", b"null", b'"x"', b"42", b"\xff\xfe\x00", b"NaN"]
)
def test_unreadable_baseline_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, content: bytes
) -> None:
    p = tmp_path / "prev.json"
    p.write_bytes(content)
    code, out = run(capsys, "--baseline", str(p), str(PASS))
    assert code == 2 and out.startswith("Baseline ")
    with pytest.raises(ValueError, match="Baseline"):
        load_baseline(p)


@pytest.mark.parametrize("which", ["missing", "directory", "empty-string"])
def test_missing_baseline_path_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, which: str
) -> None:
    path = {"missing": str(tmp_path / "nope.json"), "directory": str(tmp_path), "empty-string": ""}
    code, out = run(capsys, "--baseline", path[which], str(PASS))
    assert code == 2 and out.startswith("Baseline ")


def test_bad_baseline_checked_before_suite_runs(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr("master_finhub.evals.runner.run_suite", lambda *a, **k: calls.append(a))
    code, _ = run(capsys, "--baseline", str(tmp_path / "nope.json"), str(PASS))
    assert code == 2 and calls == []


DEEP = "[" * 100_000 + "]" * 100_000


@pytest.mark.parametrize(
    "text",
    [
        DEEP,
        '{"results": [{"case_id": "c1", "passed": true, "x": ' + DEEP + "}]}",
    ],
    ids=["root", "ignored-field"],
)
def test_deeply_nested_baseline_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str
) -> None:
    p = tmp_path / "prev.json"
    p.write_text(text)
    code, out = run(capsys, "--baseline", str(p), str(PASS))
    assert code == 2 and "cannot read (RecursionError)" in out


@pytest.mark.parametrize(
    "text",
    [
        (
            '{"results": [{"case_id": "c1", "passed": true}, {"case_id": "gone", "passed": true}],'
            ' "results": [{"case_id": "c1", "passed": true}]}'
        ),
        '{"results": [{"case_id": "gone", "case_id": "c1", "passed": true}]}',
        '{"results": [{"case_id": "c1", "passed": true, "x": {"k": 1, "k": 2}}]}',
    ],
    ids=["results", "case_id", "nested"],
)
def test_duplicate_json_keys_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str
) -> None:
    p = tmp_path / "prev.json"
    p.write_text(text)
    code, out = run(capsys, "--baseline", str(p), bench(tmp_path, "a.json", "pass"))
    assert code == 2 and "cannot read (ValueError)" in out


def test_repeated_baseline_flag_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first.json"
    first.write_text(json.dumps({"results": [row("c1", True), row("gone", True)]}))
    second = baseline(tmp_path, [row("c1", True)])
    code, out = run(
        capsys, "--baseline", str(first), "--baseline", second, bench(tmp_path, "a.json", "pass")
    )
    assert code == 2 and "more than once" in out
    calls: list[Any] = []
    monkeypatch.setattr("master_finhub.evals.runner.run_suite", lambda *a, **k: calls.append(a))
    assert run(capsys, "--baseline", second, "--baseline", second, str(PASS))[0] == 2
    assert calls == []


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs os.mkfifo")
def test_fifo_baseline_exit_2_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "prev.json"
    os.mkfifo(fifo)
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-m", "master_finhub.evals.runner", "--baseline", str(fifo), str(PASS)],
        capture_output=True, text=True, env=env, check=False, timeout=60,
    )  # fmt: skip
    assert proc.returncode == 2 and "not a regular file" in proc.stdout


def test_symlink_to_regular_baseline_is_accepted(tmp_path: Path) -> None:
    link = tmp_path / "link.json"
    link.symlink_to(baseline(tmp_path, [row("a", True)]))
    assert load_baseline(link) == {"a": True}


@pytest.mark.parametrize("target", ["load_baseline", "compare"])
def test_unexpected_baseline_exception_exit_2(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(f"master_finhub.evals.runner.{target}", boom)
    prev = baseline(tmp_path, [row("c1", True)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "pass"))
    assert code == 2 and out.startswith("Baseline unusable (RuntimeError)")


class BadStdout:
    """A stdout whose write or flush raises, like a full disk or a closed pipe."""

    def __init__(self, exc: BaseException, on: str) -> None:
        self.exc, self.on = exc, on

    def write(self, text: str) -> int:
        if self.on == "write":
            raise self.exc
        return len(text)

    def flush(self) -> None:
        if self.on == "flush":
            raise self.exc


STDOUT_FAULTS = [
    (OSError(28, "No space left on device"), "write"),
    (BrokenPipeError(32, "Broken pipe"), "write"),
    (OSError(28, "No space left on device"), "flush"),
    (BrokenPipeError(32, "Broken pipe"), "flush"),
]
FAULT_IDS = ["oserror-write", "brokenpipe-write", "oserror-flush", "brokenpipe-flush"]


@pytest.mark.parametrize(("exc", "on"), STDOUT_FAULTS, ids=FAULT_IDS)
def test_lost_report_with_baseline_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: OSError, on: str
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "fail")  # a detected regression: 3 when stdout works
    monkeypatch.setattr(sys, "stdout", BadStdout(exc, on))
    assert main(["--baseline", prev, f]) == 2


@pytest.mark.parametrize(("exc", "on"), STDOUT_FAULTS, ids=FAULT_IDS)
def test_lost_report_without_baseline_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: OSError, on: str
) -> None:
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(sys, "stdout", BadStdout(exc, on))
    if on == "write":
        with pytest.raises(type(exc)):
            main([f])
    else:
        assert main([f]) == 1  # no flush on this path, as before C4


def test_closed_stdout_with_baseline_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(sys, "stdout", None)  # what Python sets when fd 1 is closed (`>&-`)
    assert main(["--baseline", prev, f]) == 2
    assert main([f]) == 1  # without --baseline: unchanged, print is a no-op


def test_clean_flagged_run_with_lost_report_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "pass")  # nothing regressed: 0 when stdout works
    monkeypatch.setattr(sys, "stdout", BadStdout(OSError(28, "No space left on device"), "write"))
    assert main(["--baseline", prev, f]) == 2  # fail closed


def test_keyboard_interrupt_during_report_write_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    f = bench(tmp_path, "a.json", "fail")
    monkeypatch.setattr(sys, "stdout", BadStdout(KeyboardInterrupt(), "write"))
    with pytest.raises(KeyboardInterrupt):
        main(["--baseline", prev, f])


def test_unencodable_case_id_in_bad_baseline_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [{"case_id": "\ud800x", "passed": 1}])  # lone surrogate
    code, out = run(capsys, "--baseline", prev, str(PASS))
    assert code == 2 and "\\ud800x" in out


def test_non_ascii_case_id_in_bad_baseline_ascii_stdout_exit_2(tmp_path: Path) -> None:
    prev = baseline(tmp_path, [{"case_id": "caf\u00e9", "passed": 1}])
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "ascii"}
    proc = subprocess.run(
        [sys.executable, "-m", "master_finhub.evals.runner", "--baseline", prev, str(PASS)],
        capture_output=True, text=True, env=env, check=False, timeout=120,
    )  # fmt: skip
    assert proc.returncode == 2 and "caf\\xe9" in proc.stdout


def test_surrogate_case_id_regression_exit_3(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    prev = baseline(tmp_path, [row("\ud800x", True)])
    code, out = run(capsys, "--baseline", prev, bench(tmp_path, "a.json", "fail", "\ud800x"))
    assert code == 3 and out["comparison"]["regressed"] == ["\ud800x"]  # pins ensure_ascii


def test_removed_ids_sorted() -> None:
    base = {"r3": True, "r2": False, "r1": True}  # given in reverse order
    assert compare(base, [result("c1", True)])["removed"] == ["r1", "r2", "r3"]


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
@pytest.mark.parametrize("which", ["regression", "bad-baseline", "bad-benchmark"])
def test_full_disk_buffered_stdout_exit_2(tmp_path: Path, which: str) -> None:
    good = baseline(tmp_path, [row("c1", True)])
    bad = str(tmp_path / "bad.json")
    Path(bad).write_text(json.dumps({"results": [{"case_id": "c1", "passed": 1}]}))
    broken = str(tmp_path / "broken.json")
    Path(broken).write_text("{")
    argv = {
        "regression": ["--baseline", good, bench(tmp_path, "a.json", "fail")],
        "bad-baseline": ["--baseline", bad, str(PASS)],
        "bad-benchmark": ["--baseline", good, broken],
    }[which]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}  # CPython default
    env["PYTHONPATH"] = str(SRC)
    codes = []
    for args in (argv, argv[2:]):  # with --baseline, then the same run without it
        with open("/dev/full", "w") as full:
            proc = subprocess.run(
                [sys.executable, "-m", "master_finhub.evals.runner", *args],
                stdout=full, stderr=subprocess.PIPE, env=env, check=False, timeout=120,
            )  # fmt: skip
        codes.append(proc.returncode)
    assert codes == [2, 120]  # no flag: CPython's failed exit-time flush, as before C4


def test_non_oserror_stdout_with_baseline_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prev = baseline(tmp_path, [row("c1", True)])
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"results": [{"case_id": "c1", "passed": 1}]}))
    f = bench(tmp_path, "a.json", "fail")
    for argv in (["--baseline", prev, f], ["--baseline", str(bad), str(PASS)]):
        monkeypatch.setattr(sys, "stdout", BadStdout(ValueError("I/O on closed file"), "write"))
        assert main(argv) == 2  # the report guard, then the unusable-baseline message
```

Count: 4 proof + 8 compare transitions + 8 main transitions + 10 single tests (removed x2, new failing, exactly one, outranks, never lowers, sorted, schema emitted, old report, extra fields) + 17 bad rows + 6 versions + 9 unreadable + 3 paths + 1 call order = 66, plus r1: 2 deep nesting + 3 duplicate keys + 1 repeated flag + 1 FIFO + 1 symlink + 2 injected exceptions = 76, plus r2: 4 lost-report cases with `--baseline` + 4 without = 84, plus r3: 1 closed stdout + 1 clean flagged run with a lost report + 1 KeyboardInterrupt + 2 unencodable ids in a bad baseline + 1 surrogate-id regression + 1 removed ids sorted = 91, plus r4: 3 full-disk subprocess cases with `PYTHONUNBUFFERED` removed + 1 non-`OSError` stdout = **95** (pytest-collected). The new test file is not in the mypy gate (`mypy --strict src` per CI). Run alone, mypy reports only `import-untyped` for the package, which `tests/test_evals.py` also gets.

### Must still pass, unmodified

All 46 tests in `tests/test_evals.py`, in particular:
- `test_main_exit_codes`: exit 0/1/2 with no flag, and `pass_rate` read from stdout;
- `test_main_exit_2_on_duplicate_ids`;
- `test_main_exit_2_on_nan_cutoff`;
- `test_agent_never_sees_ground`;
- `test_suite_continues_after_crash`.

Also the whole suite: 1222 passed, 10 skipped before the edit.

### Mutation targets: one or more per rule, transition, boundary, missing/extra case, NaN/None/empty and call site

How I ran them: for each mutant, a fresh copy of `src` + `tests` in the scratchpad, an exact-once replacement (asserting the old text occurs exactly once and the file changed), then a fresh `pytest -x tests/test_evals_baseline.py tests/test_evals.py` process. **Revision 4: 75/75 killed, 0 survivors**, run against the final r4 source and test file, once with the mutation runner and its pytest processes started under `env -u PYTHONUNBUFFERED` and once under `PYTHONUNBUFFERED=1` (75/75 both times). M42 and M43 are killed by the FIFO test's 60 s subprocess timeout. Revision 0 killed 38/38. The ordering mutants M27, M57, M58, M59 and M64 are each killed 20/20 under `PYTHONHASHSEED` 0-19 against the r4 test file in each mode, and the unmutated files pass 141/141 under the same 20 seeds in each mode. Before r2 the M27 kill depended on the hash seed (see § Changes in revision 2).

Each mutant below has a class:
- FP (false pass): it would let a regression, or an unusable baseline, exit 0 or 1 instead of 3 or 2. Any FP survivor is a FAIL under the Pick 5 bar.
- MSG: it changes only a label, message or order. A survivor of this class is a follow-up.

| id | rule / site | mutation (old → new) | class | killed by |
|---|---|---|---|---|
| M1 | pass→fail transition | `"unchanged" if now[cid] else "regressed"` → `"unchanged"` | FP | proof flip test, transition tests |
| M2 | comparison direction | `elif baseline[cid]:` → `elif not baseline[cid]:` | FP | transitions (regressed↔fixed swap) |
| M3 | gate reads `regressed` | `if buckets["regressed"] or buckets["removed"]:` → `if buckets["removed"]:` | FP | proof flip test |
| M4 | gate reads `removed` | same line → `if buckets["regressed"]:` | FP | `test_removed_*_fails_run` |
| M5 | boundary, too lax (off by one up) | → `len(buckets["regressed"]) > 1 or ...` | FP | proof flip and `exactly_one_regression` |
| M6 | boundary, too strict (off by one down) | → `len(buckets["regressed"]) >= 0 or ...` | strictness | `proof_no_flips_exit_0` |
| M7 | regression exit code | `code = 3` → `code = 1` | FP (merges with known failures) | `== 3` asserts |
| M8 | regression exit code | `code = 3` → `code = 0` | FP | `== 3` asserts |
| M9 | call site 1, `""` path (CHANGED r1) | `if args.baseline is not None:` → `if args.baseline and args.baseline[0]:` | FP (empty path disables the gate) | `missing_baseline_path_exit_2[empty-string]` |
| M10 | call site 1 removed (CHANGED r1) | `base = load_baseline(args.baseline[0])` → `base = None` | FP | proof flip test |
| M11 | call site 2 wrong argument | `compare(base, …)` → `compare({}, …)` | FP | proof flip test |
| M12 | empty `results` | drop `or not rows` | FP (empty baseline disables the gate) | `bad_rows_exit_2[[]]` |
| M13 | schema check removed | `if isinstance(version, bool) or version != SCHEMA_VERSION:` → `if False:` | FP (foreign schema accepted) | `other_schema_version_exit_2` |
| M14 | `true == 1` loophole | drop `isinstance(version, bool) or` | FP | `other_schema_version_exit_2[True]` |
| M15 | missing-version default | `data.get("schema_version", SCHEMA_VERSION)` → `…, 2)` | strictness (rejects old reports) | `old_report_without_schema_version_is_accepted` |
| M16 | non-object row | drop the `isinstance(row, dict)` check | FP (crash instead of exit 2) | `bad_rows_exit_2[["x"]]` |
| M17 | empty `case_id` | drop `or not cid` | FP | `bad_rows_exit_2` |
| M18 | non-string `case_id` | `not isinstance(cid, str) or not cid` → `not cid` | FP | `bad_rows_exit_2` (`5`) |
| M19 | `passed` as int | `isinstance(passed, bool)` → `isinstance(passed, int)` | FP | `bad_rows_exit_2` (`1`, `0`) |
| M20 | `passed` None/missing | bool check → `if False:` | FP (`null` read as not passed hides a regression) | `bad_rows_exit_2` |
| M21 | duplicate ids | `if cid in out:` → `if False:` | FP (last row wins) | `bad_rows_exit_2` (dupes) |
| M22 | non-UTF-8 (CHANGED r1) | `except (OSError, ValueError, RecursionError)` → `(OSError, json.JSONDecodeError, RecursionError)` | MSG (still exit 2 through the catch-all) | `unreadable_baseline_exit_2[\xff…]` |
| M23 | invalid JSON (CHANGED r1) | → `except (OSError, RecursionError)` | MSG (still exit 2 through the catch-all) | `unreadable_baseline_exit_2` |
| M24 | root not object | root check → `if False:` | MSG since r1 (the catch-all gives exit 2) | `unreadable_baseline_exit_2[[]]`: the direct `load_baseline` call gets `AttributeError`, not `ValueError` (CHANGED r1) |
| M25 | NEW bucket | `key = "new"` → `key = "unchanged"` | label | `proof_new_case_listed_under_new` |
| M26 | REMOVED bucket | `key = "removed"` → `key = "still_failing"` | FP (removal no longer fails) | `removed_*` tests |
| M27 | determinism | `sorted(...)` → `list(...)` | MSG (order) | `buckets_sorted_and_key_order_fixed` (20-id check, seeds 0-19; CHANGED r2) |
| M28 | error counted as pass | `r.passed` → `not r.timed_out` | FP (pass→error silent) | `main_transition_exit_code[True-error-…]` |
| M29 | fail counted as pass | `r.passed` → `r.error is None` | FP | `main_transition_exit_code[True-fail-…]` |
| M30 | baseline lowers exit | insert `code = 0` under the second `if base is not None:` (before the `compare` try) | FP | `baseline_never_lowers_exit_code`, still_failing → 1 |
| M31 | call site 2 drops cases | `report.results` → `report.results[:1]` | FP | `exactly_one_regression` |
| M32 | call order (CHANGED r1) | `base = load_baseline(args.baseline[0])` → `base = load_baseline(args.baseline[0]) if run_suite(args.benchmarks) else None` (suite runs before the load) | MSG (wasted run; still exit 2) | `bad_baseline_checked_before_suite_runs` |
| M33 | FIXED bucket | `"fixed" if …` → `"unchanged" if …` | label | transitions |
| M34 | STILL_FAILING bucket | `else "still_failing"` → `else "regressed"` | strictness | transitions (exit 3 vs 1) |
| M35 | removed gated only if it passed | `buckets["removed"]` → `any(base[c] for c in buckets["removed"])` | FP (losing a failing case is quiet) | `removed_failing_case_fails_run` |
| M36 | missing in current run | `elif cid not in now:` → `elif False:` | FP (KeyError crash) | removed tests |
| M37 | `schema_version` emitted | drop it from `out` | MSG | `report_has_schema_version…` |
| M38 | baseline value | `out[cid] = passed` → `out[cid] = True` | strictness (fail→fail reads as regressed) | transitions (exit 1 vs 3) |
| M39 | duplicate-key hook removed (r1) | `json.load(fh, object_pairs_hook=_unique_keys)` → `json.load(fh)` | FP (dropped `gone` exits 0) | `duplicate_json_keys_exit_2` |
| M40 | hook never raises (r1) | `if len(out) != len(pairs):` → `if len(out) > len(pairs):` | FP | `duplicate_json_keys_exit_2` |
| M41 | `RecursionError` out of the tuple (r1) | `(OSError, ValueError, RecursionError)` → `(OSError, ValueError)` | MSG (catch-all still gives 2) | `deeply_nested_baseline_exit_2` (`cannot read (RecursionError)`) |
| M42 | regular-file check removed (r1) | `    if not os.path.isfile(path):` → `    if False:` | hang (FIFO blocks the run) | `fifo_baseline_exit_2_without_blocking` (timeout) |
| M43 | regular-file check weakened (r1) | `os.path.isfile(path)` → `os.path.exists(path)` | hang | `fifo_baseline_exit_2_without_blocking` (timeout) |
| M44 | repeated flag allowed (r1) | `if len(args.baseline) > 1:` → `if False:` | FP (first baseline's `gone` not gated) | `repeated_baseline_flag_exit_2` |
| M45 | repeated flag off by one up (r1) | `> 1` → `> 2` | FP | `repeated_baseline_flag_exit_2` |
| M46 | repeated flag off by one down (r1) | `> 1` → `> 0` | strictness (every `--baseline` exits 2) | proof tests |
| M47 | load catch narrowed (r1) | `except Exception` (load) → `except ValueError` | FP-class (crash exits 1) | `unexpected_baseline_exception_exit_2[load_baseline]` |
| M48 | compare catch narrowed (r1) | `except Exception` (compare) → `except ValueError` | FP-class (crash exits 1) | `unexpected_baseline_exception_exit_2[compare]` |
| M49 | failure code (r1) | `_baseline_failed` returns `1` | FP (unusable baseline reads as "known failure") | every exit-2 baseline test |
| M50 | bucket key order = judge O23 (r1) | `BUCKETS = ("regressed", "removed", …` → `("removed", "regressed", …` | MSG (order) | `buckets_sorted_and_key_order_fixed` (literal tuple) |
| M51 | report guard removed (r2; anchor CHANGED r4) | the `try: print; flush / except Exception: return _stdout_lost()` block → a bare `print` + `return code` | FP (lost report exits 1 with a traceback) | `lost_report_with_baseline_exit_2`, `closed_stdout_with_baseline_exit_2`, `full_disk_buffered_stdout_exit_2[regression]` |
| M52 | guard widened to all runs (r2) | delete the \`if base is None:\` bare-print branch | behaviour change without \`--baseline\` | \`lost_report_without_baseline_unchanged\` |
| M53 | guard returns `code` (r2; anchor CHANGED r4) | `except Exception: return _stdout_lost()` → `return code` | FP (3/1 with no report; 1 is a "known failure") | `lost_report_with_baseline_exit_2` |
| M54 | guard returns 1 (r2; anchor CHANGED r4) | `return _stdout_lost()` (report guard) → `return 1` | FP | `lost_report_with_baseline_exit_2` |
| M55 | flush removed (r2; anchor CHANGED r4) | delete the report guard's `sys.stdout.flush()` (anchor includes the `print` before it, since `_baseline_failed` now has one too) | FP (a buffered failure surfaces at exit as 1 or 120) | `lost_report_with_baseline_exit_2[*-flush]`, `full_disk_buffered_stdout_exit_2[regression]` |
| M56 | guard catches only \`BrokenPipeError\` (r2; anchor CHANGED r3) | \`except Exception:\` → \`except BrokenPipeError:\` | FP (full disk exits 1) | \`lost_report_with_baseline_exit_2[oserror-*]\` |
| M57 | J19 on the \`--baseline\` print (r2) | \`json.dumps(out, indent=2)\` → \`json.dumps(out, indent=2, sort_keys=True)\` in the guarded print | MSG (order) | proof flip test (literal tuple, \`schema_version\` first) |
| M58 | J19 on the no-flag print (r2) | same change in the \`base is None\` print | MSG (order) | \`report_has_schema_version_and_no_comparison_without_flag\` |
| M59 | J31: \`schema_version\` placed last (r2) | \`{"schema_version": SCHEMA_VERSION, **asdict(report)}\` → \`{**asdict(report), "schema_version": SCHEMA_VERSION}\` | MSG (order) | both tests above |
| M60 | guard narrowed back to `OSError` (r3) | `except Exception:` (report guard) → `except OSError:` | FP (closed stdout: a regression exits 1) | `closed_stdout_with_baseline_exit_2` |
| M61 | message escaping removed (r3) | `print(msg.encode("ascii", "backslashreplace").decode("ascii"))` → `print(msg)` | MSG since r4 (the message guard still exits 2, but the reason is lost; in r3 an unusable baseline exited 1) | `unencodable_case_id_in_bad_baseline_exit_2`, `non_ascii_case_id_in_bad_baseline_ascii_stdout_exit_2` |
| M62 | K20 (r3) | guarded `json.dumps(out, indent=2)` → `json.dumps(out, indent=2, ensure_ascii=False)` | code (a surrogate-id regression exits 2 instead of 3; under the r2 guard it exited 1) | `surrogate_case_id_regression_exit_3` |
| M63 | guard widened to `BaseException` (r3) | `except Exception:` (report guard) → `except BaseException:` | swallows Ctrl-C (`KeyboardInterrupt` returns 2) | `keyboard_interrupt_during_report_write_propagates` |
| M64 | K18 (r3) | `for cid in sorted(now.keys() \| baseline.keys()):` → `for cid in sorted(now) + [c for c in baseline if c not in now]:` | MSG (order) | `removed_ids_sorted` (seeds 0-19) |
| M65 | K13 (r3) | `if base is None:` (bare print) → `if base is None or code == 0:` | fail-closed (a clean flagged run with a lost report exits 1, not 2) | `clean_flagged_run_with_lost_report_exit_2` |
| M66 | K14 (r3) | same line → `if code != 3:` | fail-closed (the same, also for a still-failing run) | `clean_flagged_run_with_lost_report_exit_2` |
| M67 | report guard skips `_stdout_lost` (r4) | `return _stdout_lost()` (report guard) → `return 2` | FP-class (buffered: a lost report exits 120) | `full_disk_buffered_stdout_exit_2[regression]` |
| M68 | message guard skips `_stdout_lost` (r4) | `return _stdout_lost()` (in `_baseline_failed`) → `return 2` | FP-class (buffered: an unusable baseline exits 120) | `full_disk_buffered_stdout_exit_2[bad-baseline, bad-benchmark]` |
| M69 | `_stdout_lost` returns 1 (r4) | `return 2` (end of `_stdout_lost`) → `return 1` | FP | `lost_report_with_baseline_exit_2`, `closed_stdout_with_baseline_exit_2`, `full_disk_buffered_stdout_exit_2` (3), `non_oserror_stdout_with_baseline_exit_2` |
| M70 | devnull swap removed (r4) | delete `sys.stdout = open(os.devnull, "w", encoding="ascii")  # noqa: SIM115` | FP-class (buffered: exit 120 is back on every path) | `full_disk_buffered_stdout_exit_2` (3) |
| M71 | message `try` removed (r4) | the `try: print; flush / except Exception: return _stdout_lost()` block in `_baseline_failed` → the bare r3 `print` | FP (an unusable baseline with an unwritable stdout exits 1 or 120) | `full_disk_buffered_stdout_exit_2[bad-baseline, bad-benchmark]`, `non_oserror_stdout_with_baseline_exit_2` |
| M72 | bad benchmark not routed (r4) | delete `if base is not None: return _baseline_failed(exc)` in the `run_suite` `except ValueError` | FP (good baseline + bad benchmark + lost stdout exits 1 or 120) | `full_disk_buffered_stdout_exit_2[bad-benchmark]` |
| M73 | new path applied without `--baseline` (r4) | same line → `if True: return _baseline_failed(exc)` | behaviour change without `--baseline` (no-flag bad benchmark `> /dev/full` exits 2, not 120) | `full_disk_buffered_stdout_exit_2[bad-benchmark]` (the no-flag assertion). The report-side variant is M52 |
| M74 | judge K30 (r4) | `except Exception:` (report guard) → `except (OSError, AttributeError):` | FP-class (a non-`OSError` write failure escapes `main` with exit 1) | `non_oserror_stdout_with_baseline_exit_2` |
| M75 | message guard narrowed to `OSError` (r4) | `except Exception:` (in `_baseline_failed`) → `except OSError:` | FP-class (the same, on the unusable-baseline message) | `non_oserror_stdout_with_baseline_exit_2` |

The mutation script lives in the architect's scratchpad (`mut.py`). QA should re-create it from this table rather than reuse it. Each row is an exact-once string replacement against the § Exact edit text.

## Does not cover

- **Statistical flakiness.** One run is compared with one run. A flaky case that alternates gives `regressed` or `fixed` noise. There are no retries, no k-of-n and no confidence intervals. Add them when a real flaky benchmark exists (today's verifier is deterministic and `ScriptedLLM` is scripted).
- **Renames and edits.** A hash-id benchmark (no `"id"`) gets a new `case_id` when any field changes, so an edit shows as `removed` + `new` and exits 3. A renamed explicit `"id"` behaves the same way. This is intended (fail closed). Give benchmarks an explicit `"id"` to keep identity across edits, and refresh the baseline after an intended change.
- **No allow-known-failures mode.** A `still_failing` or new failing case still exits 1. C4 adds a distinct code (3) for regressions; it does not relax the existing gate. Add a separate flag only if Daniel asks for one, and get its design audited.
- **Seeds and environment.** Model, seed, cutoff and machine are not recorded or compared (crewai keeps `metadata` and `timestamp`, `result.py:33-35`). A timeout regression caused by a slower machine reads as a real regression.
- **Score drift inside failing cases.** It is not gated (Decision 5). Scores of passing cases are always 1.0.
- **History.** One baseline file, no multi-run history and no latest-of-N selection (crewai :80-81). The baseline is never written by the runner. Saving a baseline with `> prev.json` in the same command that reads `prev.json` truncates it first. The runner then sees an empty file and exits 2: fail closed, but the old baseline is lost. Use a separate path.
- **Directory arguments.** `cases/` is not expanded; pass files or a shell glob.
- **Size and DoS.** A huge baseline file is read into memory whole. That is an acceptable trust boundary for a local CI input.
- **The `master-finhub` console script.** It has no evals subcommand; C4 does not add one.
- **Explicit-id benchmark made easier (r1).** If a benchmark keeps its explicit `"id"` but is edited to be easier (for example a weaker `should_contain`), it reads `unchanged` and exits 0. C4 compares outcomes per id, not the benchmark text. A hash-id benchmark is protected because the edit changes its id.
- **`-h` with `--baseline` (r2).** `argparse` prints help and exits 0 without running anything or reading the baseline. A CI line that accidentally contains `-h` passes.
- **`load_benchmark` deep nesting (r1, follow-up outside C4's diff).** `load_benchmark` catches only `(OSError, json.JSONDecodeError)` (runner.py:78 pre-edit, :85 post-edit), so a benchmark file nested 100,000 deep escapes as `RecursionError` and exits 1 with a traceback. This is the same class of bug as A11(1), but in pre-existing code. Fixing it is a one-line follow-up with its own test; it is not folded in here.
- **Check-then-open race (r1).** The `isfile` check and `open` are two calls, so a path swapped to a FIFO between them could still block. This is acceptable for a local CI input; the fix would be `os.open` with `O_NONBLOCK` plus `fstat`.
- **Known lenience.** `schema_version: 1.0` is accepted (it equals 1). Extra keys are ignored. `passed: true` with a non-null `error` is read as passed, which can only make the gate stricter (Decision 1).
- **Control characters in baseline messages (r4, follow-up only).** `backslashreplace` escapes only non-ASCII. ASCII control characters in a bad baseline's `case_id` or path (ESC, BEL, NUL) are printed raw, so a crafted baseline can put terminal escape sequences on screen. The exit code is unaffected (2). The hardening is to print `repr` or `unicode_escape` output; that is a separate follow-up from judge round 4 (not counted).

## Authority List

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | Comparison is keyed by a stable per-case identifier, looked up from the baseline's `results` | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:102 | C4 |
| A2 | A case that passed in the baseline and does not pass now is bucketed as regressed | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:123 | C4 |
| A3 | A case that did not pass in the baseline and passes now gets its own bucket (crewai `improved`; C4 `fixed`) | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:121 | C4 |
| A4 | A current case absent from the baseline is bucketed as new, not compared | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:115 | C4 |
| A5 | A baseline case absent from the current run is reported in its own list (crewai `missing_tests`; C4 `removed`) | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:130 | C4 |
| A6 | The baseline is the prior run's own JSON with a top-level `results` list of per-case records carrying a boolean `passed` | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:36; references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:14 | C4 |
| A7 | The regression set is the set of cases previously marked passed/beaten, read from a JSON file | references/autogpt/classic/direct_benchmark/direct_benchmark/challenge_loader.py:49 | C4 |
| A8 | Regression ("maintain") cases are the ones expected to keep passing, separated from the rest | references/autogpt/classic/direct_benchmark/direct_benchmark/challenge_loader.py:114 | C4 |
| A9 | A timed-out case never counts as a pass, so pass→timeout is a regression | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:64 | C4 |
| A10 | Context only (attribution): outcomes are compared per item across two runs, and an item passing in both carries no new signal (C4 `unchanged`, not gated) | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:137 | C4 |
| A11 | CHANGED r1. An unusable baseline exits 2 before the suite runs and never re-baselines. Unusable means: not a regular file (missing, directory, `""`, FIFO, device); unreadable, non-UTF-8 or not JSON; nested too deep (`RecursionError`); a repeated key in any object at any depth; a wrong root or `schema_version`; empty or missing `results`; a bad row; a non-string or empty `case_id`; a non-boolean `passed`; a duplicate `case_id` | NET-NEW. crewai does the opposite: it warns and saves the current run as the baseline (result.py:65-78), and it skips id-less rows silently (:105). Check: `test_bad_rows_exit_2` (17), `test_unreadable_baseline_exit_2` (9), `test_missing_baseline_path_exit_2` (3), `test_other_schema_version_exit_2` (6), `test_deeply_nested_baseline_exit_2` (2), `test_duplicate_json_keys_exit_2` (3) and `test_bad_baseline_checked_before_suite_runs` fail under M9, M12-M24, M32 and M39-M41. | C4 |
| A12 | `removed` fails the run (exit 3) whatever the baseline status | NET-NEW. crewai's `missing_tests` is informational only (result.py:128-140). C4 makes it gating so that dropping a case is never a quiet way out. Check: `test_removed_passing_case_fails_run` and `test_removed_failing_case_fails_run` fail under M4, M26, M35 and M36. | C4 |
| A13 | CHANGED r4. Exit codes: 2 (unusable input, or with `--baseline` a report or message that cannot be written) > 3 (regressed or removed) > 1 (any failure) > 0. With `--baseline` the code is the no-flag code, 3, or 2; it is never lowered. Any exception raised while loading the baseline or running `compare`, and with `--baseline` a bad benchmark (`ValueError` from `run_suite`), returns 2 through `_baseline_failed`. That function prints its message ASCII-escaped (`backslashreplace`), so a `case_id` or path that stdout cannot encode (a lone surrogate in any locale, or non-ASCII under an ASCII stdout) still exits 2. It wraps that `print` and an explicit flush in `try/except Exception`, so an unwritable stdout (`/dev/full`, a closed pipe, fd 1 closed, or a non-`OSError` write failure) still exits 2. With `--baseline`, any `Exception` from the report write or its explicit flush returns 2: an `OSError` (including `BrokenPipeError`), the `AttributeError` raised when `sys.stdout` is `None` because fd 1 is closed, or any other `Exception` (`ValueError` included). Both guards return through `_stdout_lost()`, which points `sys.stdout` at `os.devnull` before returning 2. CPython's exit-time flush of a block-buffered stdout therefore cannot replace the 2 with 120. So these runs exit 2 both with `PYTHONUNBUFFERED` unset (the CPython default) and with it set. `KeyboardInterrupt` and `SystemExit` still propagate. This applies to every flagged run, so a clean or still-failing flagged run whose report is lost also exits 2 (fail closed). The report keeps the `json.dumps` default `ensure_ascii=True`, so a regression whose case id is a lone surrogate exits 3. A crash inside `run_suite`/`load_benchmark` other than its `ValueError` (for example a benchmark nested 100,000 deep) exits 1 as before: a documented follow-up outside C4's diff. Runs without `--baseline` keep their previous code path and exit codes in both buffering modes | NET-NEW. No reference defines CLI exit codes for a compare. The repo's existing 0/1/2 come from runner.py:202-206. Check: `test_main_transition_exit_code` (8), `test_regression_outranks_other_failures`, `test_baseline_never_lowers_exit_code`, `test_deeply_nested_baseline_exit_2`, `test_unexpected_baseline_exception_exit_2` (2), `test_lost_report_with_baseline_exit_2` (4), `test_lost_report_without_baseline_unchanged` (4), `test_closed_stdout_with_baseline_exit_2`, `test_clean_flagged_run_with_lost_report_exit_2`, `test_keyboard_interrupt_during_report_write_propagates`, `test_unencodable_case_id_in_bad_baseline_exit_2`, `test_non_ascii_case_id_in_bad_baseline_ascii_stdout_exit_2`, `test_surrogate_case_id_regression_exit_3`, `test_full_disk_buffered_stdout_exit_2` (3; subprocess, `PYTHONUNBUFFERED` removed, also asserts the no-flag exit 120) and `test_non_oserror_stdout_with_baseline_exit_2` fail under M7, M8, M30, M34, M38, M47-M49, M51-M56, M60-M63 and M65-M75. | C4 |
| A14 | Error and timeout are not separate statuses: the comparison uses `CaseResult.passed`, which is already false on any error or timeout | NET-NEW (repo fact, runner.py:165-166; A9 supports the timeout half). Check: `test_main_transition_exit_code[True-error-3-regressed]` and `[True-timeout-3-regressed]` fail under M28 and M29. | C4 |
| A15 | A non-empty bucket triggers exit 3 at exactly one id (boundary) | NET-NEW. Check: the proof flip test and `test_exactly_one_regression_among_many_exit_3` fail under M5 (`> 1`); `test_proof_no_flips_exit_0` fails under M6 (`>= 0`). | C4 |
| A16 | `schema_version: 1` is emitted on every report. A missing key in a baseline is read as 1; any other value, including `true`, is rejected | NET-NEW. No reference versions its report (crewai keys on `timestamp`, result.py:61). Check: `test_report_has_schema_version_and_no_comparison_without_flag`, `test_old_report_without_schema_version_is_accepted` and `test_other_schema_version_exit_2` fail under M13, M14, M15 and M37. | C4 |
| A17 | CHANGED r2. Buckets are emitted in the fixed order `("regressed", "removed", "fixed", "still_failing", "unchanged", "new")`, each list sorted by `case_id`, and `schema_version` is the first key of the printed report | NET-NEW. crewai keeps current-run order (result.py:113). Check: `test_buckets_sorted_and_key_order_fixed` asserts the literal tuple for `BUCKETS` and for `compare`'s keys. The proof flip test asserts the literal tuple for the printed `comparison` and `schema_version` first; the no-flag schema test asserts `schema_version` first. They fail under M50 (O23), M27 (unsorted, 20-id check, `PYTHONHASHSEED` 0-19), M57 and M58 (J19 `sort_keys=True` on either print) and M59 (J31). | C4 |
| A18 | Scores are not compared and no tolerance exists, because a passing case always has score 1.0 | NET-NEW. This deliberately does not adopt autogpt's `score >= 0.9` success threshold (evaluator.py:67). Repo fact: runner.py:166 plus verifiers.py:37-40. Check: `tests/test_evals.py::test_pass_benchmark_passes` asserts `score == 1.0` on pass, and M1 and M29 show the verdict depends only on `passed`. | C4 |
| A19 | `--baseline ""` is a given (bad) path, not "no baseline" | NET-NEW. Check: `test_missing_baseline_path_exit_2[empty-string]` fails under M9. | C4 |
| A20 | Quant guardrails G1-G6: all N/A (no prices, trades or splits). The G4/G6 analogue is that the baseline never reaches `run_suite`/`run_case`; the G5 analogue is that `removed` is gated | NET-NEW. Check: `grep -c "run_suite(args.benchmarks)" src/master_finhub/evals/runner.py` = 1, with the `run_suite`/`run_case` signatures unchanged (P11 hash); G5 via A12. | C4 |
| A21 | Attribution: the runner docstring names crewai `result.py:99-143` and autogpt `challenge_loader.py:49` (MIT) and revfactory `skill-testing-guide.md:135` (Apache-2.0); the scan for shared 8-token runs finds 0; Hangul 0 | NET-NEW (licence gate). Check: Proof P8, P9 and P10. | C4 |
| A22 | A `--baseline` given more than once exits 2 before the suite runs, instead of keeping only the last value | NET-NEW (judge r1 hardening (i)). Check: `test_repeated_baseline_flag_exit_2` fails under M44, M45 and M46 (M46 fails the proof tests). | C4 |
| A23 | A baseline path that is not a regular file (FIFO, device, directory) exits 2 without opening it; a symlink to a regular file is accepted | NET-NEW (judge r1 hardening (ii)). Check: `test_fifo_baseline_exit_2_without_blocking` (subprocess, 60 s timeout) fails under M42 and M43, and `test_symlink_to_regular_baseline_is_accepted` pins the symlink case. | C4 |

Byte-identity check for the unchanged rows. Run from the repo root. For r4, `<r3>` is the revision-3 copy saved in the architect scratchpad (`c4r4/design_r3.md`), and the pattern covers every row except A13:

```
diff <(grep -E '^\| A([1-9]|1[0124-9]|2[0-3]) \|' <r3>) \
     <(grep -E '^\| A([1-9]|1[0124-9]|2[0-3]) \|' _workspace/02_strategy-architect_C4.md)
```

The expected output is empty: 22 rows, A1-A12 and A14-A23.
