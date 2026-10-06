RESULT: FAIL
Survivor split: equivalent 13 / false-pass 11 (all are missing test pins; src is correct on every real-process probe) / follow-up 10

# Boundary QA: C4 (eval regression buckets, `--baseline`)

- Tree: /home/user/finhub-harness, branch claude/tender-brown-8us2kt at origin/main 6bc9e51, uncommitted. Python 3.11.15 (the only interpreter here; 3.10/3.12/3.13 not run).
- Bar (fixed up front): gates green; src byte-identical to the accepted design; zero non-equivalent survivors that let a regression pass silently or make a regression or unusable baseline exit 0 or 1 across the design's mutants, my own batch and one fresh batch. Message/format/label/order-only survivors are follow-ups.
- Why FAIL: 11 non-equivalent mutants survive the 97-test file and make a regression, a removed case or an unusable baseline exit 0 or 1 (table "False-pass survivors"). A false-pass survivor was found, so I ran a second fresh batch (R01-R82); it found 5 more of the same family. The code itself passed every real-process probe; the defect is test strength, and the fix is test-only (pins below).
- Everything ran in scratch copies under /tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/qa/. Repo untouched except as disclosed under "Side effect".

## Boundary table

| boundary | side A shape | side B shape | match |
|---|---|---|---|
| CLI flag -> `main` | `--baseline` `action="append"`, `args.baseline` is None or a list of length >= 1 | `main` reads `args.baseline[0]` after a `len > 1` check inside the same `try` | yes (repeat and `--base`/`--basel` abbreviations exit 2 / 3 as designed) |
| baseline file -> `load_baseline` | `{schema_version?, results:[{case_id:str, passed:bool,...}]}` as printed by the runner | returns `{case_id: bool}`; unusable raises ValueError, `main` maps any Exception to 2 | yes (18 unusable shapes, all 2 with every stdout state) |
| `load_baseline` -> `compare` | `dict[str,bool]` | `compare(baseline, results)` keyed on `CaseResult.case_id`/`.passed` | yes |
| `compare` -> exit code / printed report | six buckets, literal order, sorted ids | `buckets["regressed"] or buckets["removed"]` -> 3; `schema_version` first key; `comparison` last | yes; exit logic correct but its mixed-bucket cases are unpinned (see defects) |
| `main` -> `_baseline_failed` / `_stdout_lost` | print + flush guarded, `Exception` caught, KeyboardInterrupt/SystemExit not | returns 2; stdout swapped to devnull, or None when devnull cannot be opened | yes in every probe (both buffering modes, 10 configs) |
| runner report -> next run's baseline (round trip) | report from this runner, or from the pre-edit runner (no `schema_version`) | missing `schema_version` counts as 1 | yes |
| design test file -> built test file | design r4 file, 558 lines, sha256 3554b065..ca4250a0 | tests/test_evals_baseline.py, 581 lines = the 558 lines byte-identical + 2 appended tests | yes |
| built runner -> judge's fix2 runner | sha256 c34f998b..e06166e6, 326 lines | repo file | byte-identical |

## Gate

| # | command | exit | output observed |
|---|---|---|---|
| G1 | `git status --short` | 0 | ` M src/master_finhub/evals/runner.py` / `?? tests/test_evals_baseline.py`; `git diff --stat -- references` empty; `git submodule status \| grep -c '^[+-U]'` = 0 |
| G2 | `sha256sum src/master_finhub/evals/runner.py; wc -l` | 0 | `c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6`, 326 lines |
| G3 | `cmp src/master_finhub/evals/runner.py <judge>/r5/fix2/src/master_finhub/evals/runner.py` | 0 | no output; I echoed IDENTICAL_fix2 |
| G4 | extract design diff (156 lines), `patch -p1` onto `git show HEAD:...runner.py` (sha 70984252..85b7ce60), then `diff` against the repo runner | 1 | patched runner is 323 lines, sha 5c447a4d..7cb57aa21a; the only difference is `265c265,268`: the `try:` / `except OSError:` / `sys.stdout = None` fallback around the devnull `open` (the 3-line fallback, plus re-indent) |
| G5 | test file: lines 529-1086 of the design (558 lines), `head -558 tests/test_evals_baseline.py \| cmp - design_tests.py` | 0 | PREFIX_IDENTICAL; design file sha256 begins 3554b065c729d42a; repo file `e6a70140a017e15b572783049ee6cef274d37c05220ab24b7f6f9127c8537529` (581 lines). Lines 559-581 are exactly `test_stdout_lost_without_devnull_exit_2` and `test_keyboard_interrupt_during_baseline_message_propagates`; no existing test edited |
| G6 | `env -u PYTHONUNBUFFERED .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_evals_baseline.py` x5 | 0 | `97 passed in 1.04s`, `0.98s`, `0.97s`, `0.94s`, `1.02s` |
| G7 | same x5 with `PYTHONUNBUFFERED=1` | 0 | `97 passed` x5 (1.00s, 1.05s, 1.60s, 0.94s, 0.94s) |
| G8 | tests/test_evals_baseline.py + tests/test_evals.py, both modes | 0 | `143 passed in 1.06s` (unset), `143 passed in 1.00s` (set) |
| G9 | full `pytest -q -p no:cacheprovider`, `env -u PYTHONUNBUFFERED` | 0 | `1319 passed, 10 skipped in 101.76s (0:01:41)` |
| G10 | full `pytest -q`, `PYTHONUNBUFFERED=1` | 0 | `1319 passed, 10 skipped in 99.88s (0:01:39)` (1319 = 1222 + 97) |
| G11 | `.venv/bin/mypy --strict src` | 0 | `Success: no issues found in 38 source files` |
| G12 | `.venv/bin/ruff check src tests` | 0 | `All checks passed!` |
| G13 | `.venv/bin/black --check src tests` | 0 | `67 files would be left unchanged.` |
| G14 | `bash scripts/check-harness-refs.sh` (scratch tree copy, references symlinked; also run on the repo: 0 FAIL lines) | 0 | last lines `PASS six agent files`, `PASS CLAUDE.md says six-agent`, `PASS no Hangul in agents+triage`, `PASS packager exit 0` |
| G15 | `bash scripts/package-plugin.sh` in the scratch tree copy | 0 | `lint_harness: 0 error(s), 0 warning(s)`; `dist/finhub-harness.plugin  97930 bytes`, `...-skill.zip 85199`, `...-evolve-skill.zip 3516` |
| G16 | `LC_ALL=C.UTF-8 grep -nP '\p{Hangul}' src/master_finhub/evals/runner.py tests/test_evals_baseline.py` | 1 | no lines |
| G17 | 8-word token-run scan (my `ngram.py`) of runner.py and the test file against `references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py`, `references/autogpt/classic/direct_benchmark/direct_benchmark/challenge_loader.py`, `references/revfactory_harness/skills/harness/references/skill-testing-guide.md` (all three exist in this checkout) | 0 | 0 hits for all 6 pairs |
| G18 | attribution: `sed -n 1,12p src/master_finhub/evals/runner.py` | 0 | docstring lines 3-9 name crewai `result.py:99-143` and autogpt `challenge_loader.py:49` (MIT, own code) and revfactory `skill-testing-guide.md:135` (Apache-2.0) |
| G19 | three subprocess `test_full_disk_buffered_stdout_exit_2[...]` plus `cli_module`, `fifo`, `non_ascii_case_id_in_bad` (6 tests) run 10 times, `env -u PYTHONUNBUFFERED` | 0 | `6 passed` x10 (0.65-0.78s each) |
| G20 | same 6 tests x3 with 8 busy-loop python processes running | 0 | `6 passed in 1.67s`, `1.53s`, `1.49s`; `ps -eo pid,args \| grep -E "evals.runner\|while True"` afterwards: empty (no leftover process) |
| G21 | subprocess tests build their own env | n/a | test source (lines 536-538): `env = {k: v for ... if k != "PYTHONUNBUFFERED"}`; with the parent running `PYTHONUNBUFFERED=1`, `-k full_disk` still gives `3 passed` |
| G22 | `/dev/full` missing, simulated with `-p plug` (`os.path.exists("/dev/full")` -> False) | 0 | `94 passed, 3 skipped`; `SKIPPED [3] tests/test_evals_baseline.py:523: needs /dev/full` (visible skip, not a silent pass) |

## Real-process probe matrix (built runner, `matrix.py`)

136 rows x 10 configurations = {`env -u PYTHONUNBUFFERED`, `PYTHONUNBUFFERED=1`} x {plain, `-u`, `-X dev`, `PYTHONIOENCODING=ascii`, `LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0`}. Output of `.venv/bin/python -B matrix.py /home/user/finhub-harness/src mx_post.json`: `rows 136 bad 1`; the one "BAD" is my expectation, not the runner (row 6 below).

| row group | expected | observed (all 10 configs) |
|---|---|---|
| regression, normal stdout | 3 | 3 |
| regression on `/dev/full`, `\| true`, `>&-` | 2 | 2 |
| regression `\| head -c1`, small report | 3 or 2 | 2 and 3 (pipe write may succeed before head exits; the same race exists in the pre-edit runner) |
| regression 450 cases on normal / `\| true` / `\| head -c1` / `/dev/full` / `>&-` | 3 / 2 / 2 / 2 / 2 | as expected |
| clean flagged: normal / `/dev/full` / `\| true` / `>&-` | 0 / 2 / 2 / 2 | as expected (`\| head -c1`: 0 or 2) |
| fixed flagged: same | 0 / 2 / 2 / 2 | as expected (`head`: 0 or 2) |
| still-failing flagged: same | 1 / 2 / 2 / 2 | as expected (`head`: 1 or 2) |
| lone-surrogate-id regression (normal / `/dev/full` / `\| true` / `>&-`) | 3 / 2 / 2 / 2 | as expected |
| unusable baseline (missing, directory, FIFO, non-UTF-8, 200000-deep nesting, duplicate key at root, in a row, nested, escape-spelled (`passed`), schema_version 2, schema_version true, `passed:"yes"`, `passed:1`, empty results, duplicate ids, non-ASCII id under ascii, 10 MB case id, `{`) x (normal, `/dev/full`, `\| true`, `>&-`) | 2 | 2 in all 18 x 4 rows. A baseline whose only fault is a lone-surrogate id with a valid `passed` is usable and gives 3 (removed), which is why my row "unusable-surrogate_id/normal" read BAD; its three broken-stdout variants gave 2 |
| good baseline + bad benchmark x 5 stdout states | 2 | 2 |
| repeated `--baseline`; `--base` and `--basel` abbreviations; `--baseline ''` | 2; 3; 2 | 2; 3 (both abbreviations); 2 |
| no-flag runs (fail / pass / bad benchmark / two failing) x 5 stdout states | equal to the pre-edit runner | exit codes identical in 10 configs for normal, `/dev/full` (1 or 120), `\| true`, `>&-`. `\| head -c1` rows differ run to run in BOTH trees (0 or 1 under load); 20 quiet repeats of each tree: all 0 |
| no-flag stdout vs pre-edit stdout (duration masked) | only the new key | `1a2 >   "schema_version": 1,` for fail and pass runs, nothing else |
| KeyboardInterrupt and SystemExit(7) raised from `write` and from `flush`, on the report path and the unusable-baseline message path (in-process `main`) | propagate | all 8 combinations `raised` the original exception |

No-/dev/null reproduction (`r5/nodevnull.py`; `os.devnull` set to `/nonexistent/null`, then to `/tmp` (a directory, EISDIR), then the real devnull), rows regression, clean, still-failing, bad baseline, bad benchmark, stdout normal / `/dev/full` / `\| true` / `>&-`, both modes: normal gives 3 / 0 / 1 / 2 / 2; every broken-stdout cell gives 2. 30 of 30 rows x 4 stdouts as expected.

EMFILE (`emfile.py`, `ulimit -n 64`; stdout whose `write` first exhausts all file descriptors, then raises OSError so the next `open(os.devnull)` fails with `[Errno 24] Too many open files`): regression and unusable-baseline runs both return 2 (`main returned 2 held 61`).

Spot-check of "Does not cover": easier-edited explicit-id benchmark reads `unchanged`, exit 0 (accurate); `load_benchmark` 100000-deep file exits 1 with `RecursionError`, also with a good `--baseline` (accurate); `-h --baseline nope.json` exits 0 (accurate); isfile/open race: not run (timing-dependent, accepted by the design).

## Safety property end to end (`e2e.py`, real CLI, `env -u PYTHONUNBUFFERED`)

| check | observed |
|---|---|
| pass->pass | rc 0, bucket `unchanged` |
| pass->fail / pass->error / pass->timeout | rc 3, `regressed` (3 of 3) |
| fail->pass | rc 0, `fixed` |
| fail->fail / fail->error / fail->timeout | rc 1, `still_failing` (3 of 3) |
| removed, baseline passed / baseline failed, suite otherwise passing | rc 3 both |
| new passing / new failing | rc 0 / rc 1 |
| regressed + removed + still_failing | 3 |
| removed (baseline failed) + still_failing | 3 |
| regression + bad benchmark; bad baseline + failing suite | 2; 2 (2 > 3 > 1 > 0) |
| same suites with and without the flag (clean, failing, mixed) | flagged >= unflagged in all 3 (a baseline never lowers the code) |
| `> prev.json` round trip | save rc 1; rerun with `--baseline prev.json`: `unchanged:[a]`, `still_failing:[b]`, rc 1; keys start `schema_version, results, passed`; bucket order `regressed, removed, fixed, still_failing, unchanged, new`; every bucket sorted |
| report produced by the pre-edit runner (first key `results`, no `schema_version`) as baseline | accepted as version 1: rc 1 with the same buckets; with a removed `b` and a new `a2` rc 3 |

## Mutation results (tar copy of the real tree at qa/mtree, fresh copy and fresh pytest process per mutant, each mutation asserted to match the source exactly once, `-x` on tests/test_evals_baseline.py + tests/test_evals.py)

| set | run | result |
|---|---|---|
| design M1-M75 (architect's mut_r4.py, anchors unchanged against the 326-line runner) | `env -u PYTHONUNBUFFERED` and `PYTHONUNBUFFERED=1` | 75/75 killed in both modes, 0 survivors, 0 anchor failures. Includes K30 (= M74), the BaseException widening (M63) and the message-guard widening, killed by the new KeyboardInterrupt test (J1 = judge O25, killed) |
| J2 (OSError fallback removed) = my Q22 | both modes | killed by `test_stdout_lost_without_devnull_exit_2` |
| judge's 34 own (O1-O34, from r5/mut.py) | both modes | 27 killed, 5 survive: O11, O22, O30 (equivalent), O21, O34 (no exit effect). O17 and O18 did not anchor against the 326-line runner; I re-anchored them as O17b, O18b, O17c (return 3 / return 0 after the swap): all 3 killed |
| my batch 1, Q01-Q46 (+ Q12, Q37 re-anchored) | both modes | 33 killed, 13 survive (classified below); no mode differences |
| my batch 2, R01-R82 (33 mutants; run because batch 1 found a false-pass survivor) | both modes | 18 killed, 15 survive; no mode differences |

### False-pass survivors (non-equivalent, wrong exit 0 or 1 where the design says 3 or 2)

Each is reproduced through the real CLI on a mutated tree (`mt/<id>/src`), except where marked.

| mutant | change | real runner | mutant | why no test catches it | one-line pin |
|---|---|---|---|---|---|
| Q34 | gate `... or (removed and not report.failed)` | removed + still-failing case: 3 | 1 | A12's tests use a passing suite | `main` with baseline `[gone:true, s:false]`, run `[s fails]` -> 3 |
| R01 | removed masked by `still_failing` | 3 | 1 | same | same case as Q34, assert `removed==["gone"]` and code 3 |
| R02 | removed masked by `new` | removed + new (rename, passing suite): 3 | 0 | no removed+new test, although the design's hash-id-edit story is exactly this | baseline `[old:true]`, run a passing case with a different id -> 3 |
| R03 | removed masked by `fixed` | 3 | 0 | no removed+fixed test | baseline `[gone:true, f:false]`, run `[f passes]` -> 3 |
| R05 | regressed masked by `fixed` | regressed + fixed: 3 | 1 | regression tests never carry a fixed case | baseline `[r:true, f:false]`, run `[r fails, f passes]` -> 3 |
| R07 | regressed masked by `new` | regressed + new: 3 | 1 | same | baseline `[r:true]`, run `[r fails, n passes]` -> 3 |
| Q21 | devnull fallback `except FileNotFoundError` | open fails with EISDIR / EMFILE: 2 | 1 (traceback `OSError: [Errno 24] Too many open files: '/dev/null'`) | the new test only uses a missing path | `os.devnull = str(tmp_path)` (a directory) with `sys.stdout=None`: regression run -> 2 |
| Q33 | `nargs="*"` for the benchmark paths | `main []` / no path: 2 (argparse) | 0 with no flag (an empty suite passes); 3 with a flag | no test runs with zero paths | `with pytest.raises(SystemExit) as e: main([])`; `e.value.code == 2` |
| R33a | exit code = number of failures | 3 failing, no regression: 1 | 3 (indistinguishable from a regression; 2 failures give 2) | no test has two failing cases without a regression | baseline all-false, run 3 failing cases -> 1, with and without the flag |
| R33b | exit code = `failed % 3` | 1 | 0 (3 failing cases pass silently) | same | same test |
| Q12 | baseline opened as latin-1 | invalid UTF-8 inside a string: 2 | accepted (rc from the compare) | the only non-UTF-8 test input is `\xff\xfe\x00`, which fails as JSON under latin-1 too | `b'{"results":[{"case_id":"a\xff","passed":true}]}'` -> 2 |

All of R01-R07 and Q34 close with one parametrized test over mixed bucket combinations: for every pair drawn from {regressed, removed} x {unchanged, fixed, still_failing, new, regressed, removed} the code is 3, and for {fixed, still_failing, new, unchanged} alone it is 0 or 1.

### Equivalent survivors (13)

| mutant | change | evidence |
|---|---|---|
| O11 `len(args.baseline) != 1` | judge: `action="append"` gives None or a list of length >= 1 | reasoning |
| O22 devnull line-buffered | nothing is written after the swap | reasoning |
| O30 `code = max(code, 3)` | `code` is 0 or 1 at that point | reasoning |
| Q02 `now[cid] and cid` | case ids are non-empty strings (baseline validated, benchmark id `explicit or hash`) | 120000-input fuzz, 0 differences |
| Q16 `if base:` instead of `is not None` | `base` is None or a non-empty dict (empty results rejected) | fuzz 0 differences; reasoning |
| Q44 `args.baseline[-1]` | length > 1 is rejected earlier in the same try | fuzz (includes repeated-flag argv) 0 differences |
| Q45 `if args.baseline:` | None or non-empty list | fuzz 0 differences |
| R10 `regressed and report.failed > 0` | a regressed case is a failed case | fuzz 0 differences |
| R11 `regressed and len(removed) < 2 or removed` | boolean identity | fuzz 0 differences |
| R71 devnull opened without `encoding="ascii"` | nothing is written to it | reasoning |
| R73 `except Exception` around the devnull open | superset of OSError; `open` raises only OSError (or ValueError/TypeError for a bad name) | reasoning; strictly more protective |
| R74 `except (OSError, ValueError)` | same | same |
| R82 skip the swap when `sys.stdout is None` | stdout is already None, exit 2 either way | reasoning; Q20 below is the relevant contrast |

Fuzz: `fuzz.py`, 120000 trials of random baseline (300 files, 1-6 ids) x random current run, in-process `main` of the real and each mutated module, comparing return code and stdout.

### Follow-ups (message/format/label/ordering, or wrong non-zero exit that is neither 0 nor 1) (10)

| mutant | what changes | one-line pin |
|---|---|---|
| Q20 `except OSError: pass` (no `sys.stdout = None`) | with devnull unusable AND stdout broken, a regression exits 120 (buffered; 2 when unbuffered). Neither 0 nor 1, so not counted as a false pass, but it breaks "exit 2 in both modes" | subprocess regression, `os.devnull` missing, stdout `/dev/full`, `env -u PYTHONUNBUFFERED` -> 2 |
| Q23 / Q24 guards narrowed to `(OSError, ValueError, AttributeError)` | an exception of another type (for example a reentrant-call RuntimeError) would escape as exit 1; no real process raises it | stdout whose write raises `RuntimeError`, both guards -> 2 |
| Q27 still-failing flagged run with a lost report returns 1 | contract says every flagged lost report exits 2; no regression is hidden (code 1 means none) | still-failing flagged run, stdout None -> 2 |
| Q13 baseline id `" "` rejected | fail-closed 2 on a usable baseline | baseline `[" ": true]` is accepted |
| Q15 `run_suite` catch widened to Exception | a crash that exits 1 today would exit 2 | monkeypatched `run_suite` raising TypeError propagates, with and without the flag |
| R42 OSError given the full message | message text only | none needed beyond a message assertion |
| R63 non-list `results` | same exit 2, different message | assert the message for `"results": 5` |
| O21 `sys.stdout = sys.stderr` | in-process callers see later stdout on stderr; CLI exit identical | assert `sys.stdout` is not `sys.stderr` after `_stdout_lost()` |
| O34 report printed without `indent=2` | format only | assert the printed report starts with `{\n  "schema_version"` |

## Defects

1. tests/test_evals_baseline.py (whole file): no test combines `regressed` or `removed` with another bucket, so the exit-3 gate in runner.py:310-313 can be weakened without a failure. Expected: any report containing a regressed or removed case exits 3. Mutants R01, R02, R03, R05, R07, Q34 survive; each exits 1 or 0 in the real CLI (table above). Fix: one parametrized mixed-bucket test.
2. tests/test_evals_baseline.py:561-570 (`test_stdout_lost_without_devnull_exit_2`): only `os.devnull` missing (ENOENT) is pinned. Expected: any OSError from the devnull open falls back to None. Mutant Q21 survives and exits 1 under EISDIR or EMFILE (both reproduced).
3. tests/test_evals_baseline.py: no test with zero benchmark paths (Q33), none with two or more failing cases and no regression (R33a, R33b), none with raw invalid UTF-8 inside a JSON string (Q12). Each mutant gives a wrong exit 0 or 1 (or 3).
4. `_workspace/02_strategy-architect_C4.md` A12 and A13 "fail under" lists are accurate for the mutants they name; they do not claim the mixed-bucket cases, so no claim is false, only incomplete.

No defect in src/master_finhub/evals/runner.py was found: every row of the probe matrix, the no-devnull and EMFILE reproductions, the transition table and the round trips behaved as designed.

## Side effect and not run

- `bash scripts/check-harness-refs.sh` (run on the repo, as the task asks) calls the packager, which rewrote the gitignored `dist/` in the repo (3 files, same sizes as the scratch run: 97930 / 85199 / 3516 bytes). `git status` is unaffected (`dist` is ignored). I deleted nothing.
- Not run: CPython 3.10/3.12/3.13 (only 3.11.15 here); `pytest -W error` (the design notes 7 expected ResourceWarning errors); a mount-namespace reproduction of a missing /dev (simulated through `os.devnull`, as the judge did); the isfile/open check-then-open race; a pty probe. No second fresh batch beyond R01-R82.
- Reproduction files (scratchpad, not repo): `qa/matrix.py`, `qa/e2e.py`, `qa/mutrun.py`, `qa/fresh.py` (Q batch), `qa/fresh2.py`, `qa/fresh3.py` (R batch), `qa/fuzz.py`, `qa/mut_all_unset.out`, `qa/mut_all_set.out`, `qa/fresh_unset.out`, `qa/fresh3_unset.out`.

## Next step

Add the pins in the False-pass table (one mixed-bucket parametrized test, an EISDIR devnull variant, a zero-paths test, a two-or-three-failures exit-1 test, an invalid-UTF-8-in-string baseline test) to tests/test_evals_baseline.py, then re-run only mutants Q34, R01, R02, R03, R05, R07, Q21, Q33, R33a, R33b and Q12 plus the 75 design mutants; src stays as it is.
