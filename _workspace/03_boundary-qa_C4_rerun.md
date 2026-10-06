RESULT: PASS

# C4 (eval baseline compare) scoped QA re-run

Bar (Daniel's, up front): only a false-pass survivor fails. The 10 known follow-ups (Q20, Q23/Q24, Q27, Q13, Q15, R42, R63, O21, O34) are recorded, not failures. No second fresh mutant batch was run, and no new survivor turned up.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| runner exit codes ↔ tests | 0 clean, 1 failing, 2 unusable baseline/benchmarks/lost stdout, 3 regressed or removed | 112 tests pin each code, including mixed buckets, 2-6 failures, EISDIR/EMFILE devnull, zero paths, invalid UTF-8 inside a string | match |
| src ↔ prior QA | runner.py sha256 c34f998b... | prior report accepted this file as correct | match (unchanged) |

## Scope checks
| command | exit | output |
|---|---|---|
| `sha256sum src/master_finhub/evals/runner.py tests/test_evals_baseline.py` | 0 | `c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6` and `98a447c63f4ca49bd144cf95b1a4f0a0fff43c8760094a110fc0e0f892b23aa3`, both as expected (re-checked at the end) |
| `pytest -q -p no:cacheprovider tests/test_evals_baseline.py` | 0 | `112 passed in 1.03s` |
| `git status --short` (start and end) | 0 | ` M src/master_finhub/evals/runner.py` and `?? tests/test_evals_baseline.py`, nothing else |

## Gate
Each gate ran in both modes. `unset` is `env -u PYTHONUNBUFFERED`; `set` is `PYTHONUNBUFFERED=1`.

| command | mode | exit | output observed |
|---|---|---|---|
| `.venv/bin/python -m pytest -q -p no:cacheprovider` | unset | 0 | `1334 passed, 10 skipped in 98.12s (0:01:38)` |
| same | set | 0 | `1334 passed, 10 skipped in 98.89s (0:01:38)` |
| `python -m mypy --strict src` | unset, set | 0 | `Success: no issues found in 38 source files` |
| `ruff check src tests` | unset, set | 0 | `All checks passed!` |
| `black --check src tests` | unset, set | 0 | `67 files would be left unchanged.` |
| `bash scripts/check-harness-refs.sh` | unset, set | 0 | 0 FAIL lines; last lines `PASS CLAUDE.md says six-agent`, `PASS no Hangul in agents+triage`, `PASS packager exit 0` |
| `bash scripts/package-plugin.sh` | unset, set | 0 | `dist/finhub-harness-skill.zip  85199 bytes`, `dist/finhub-harness-evolve-skill.zip  3516 bytes` |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' src/master_finhub/evals tests/test_evals_baseline.py skills/` | unset, set | 1 (as required) | no lines |
| secrets grep (`AKIA...`, `sk-...`, `ghp_...`, `BEGIN ... PRIVATE KEY`, `xox[bp]-`) over runner.py and the test file | unset, set | 1 | no lines |

## Mutation re-run
Method: a tar copy of src, tests and pyproject.toml in `scratchpad/rr/base` (no rsync). Each mutant got its own copy and a fresh `python -B -m pytest -x -q` process, running `tests/test_evals_baseline.py` and `tests/test_evals.py`. The harness requires the old text to occur exactly once and asserts the mutated file differs from the original, so an unchanged file reports NOOP and a missing anchor reports ANCHOR. Neither happened for any of the mutants counted below. Both modes were run (`default` unsets PYTHONUNBUFFERED, `unbuf` sets it). Scripts and output are in `scratchpad/rr/`: `mutrun.py`, `prior11.py`, `p11_*.out`, `all_*.out`.

| set | modes | result |
|---|---|---|
| 11 prior survivors | default and unbuf | 11/11 KILLED in each mode, survivors [] |
| 75 design mutants M1-M75 | default and unbuf | 75/75 KILLED in each mode, 0 anchor failures |
| judge O1-O34 (re-anchored O17b, O18b, O17c) | default and unbuf | same outcome in both modes (see below) |

Killed:
- Q34, R01, R02, R03, R05, R07: killed by `test_regressed_or_removed_beside_other_buckets_exit_3[...]`.
- Q21: killed by `test_stdout_lost_devnull_is_a_directory_exit_2`.
- Q33: killed by `test_no_benchmark_paths_exit_2[no-flag]`.
- R33a, R33b: killed by `test_several_failures_without_regression_exit_1[3]`.
- Q12, using the anchored `fresh2.py` version: killed by `test_baseline_with_invalid_utf8_inside_string_exit_2`.
- Re-anchored O17b, O18b, O17c: killed by `test_lost_report_with_baseline_exit_2[oserror-write]`.
- Q37, also in `fresh2.py`: killed.

Judge-set survivors, identical in both modes and identical to the prior QA's classification. None of them lets a regression or an unusable baseline exit 0 or 1:
- O11 `len(args.baseline) != 1`: equivalent, because `action="append"` gives None or a list of length 1 or more.
- O22 devnull line-buffered: equivalent, because nothing is written after the swap.
- O30 `code = max(code, 3)`: equivalent, because `code` is 0 or 1 at that point.
- O21 `sys.stdout = sys.stderr`: known follow-up with no CLI exit effect.
- O34 report printed without `indent=2`: known follow-up, format only.
- O17 and O18 as originally written report ANCHOR in the judge's file (the text does not match the 326-line runner). Their re-anchored versions above are killed.

## Defects
None.

observation: the same follow-ups as before stay recorded and open (Q20, Q23/Q24, Q27, Q13, Q15, R42, R63, O21, O34). These are message, format, label or in-process-only effects, and none changes an exit code.

observation: the prior report's 11 false-pass survivors came from test strength. The builder's 15 added tests close them, and the src is byte-identical to what the prior QA accepted.

## Adversarial probes
The mutants above, run in both modes, were the probes. They covered mixed-bucket exit 3, exit 1 with several failures, exit 2 when no benchmark path is given, devnull that is a directory, and invalid UTF-8 inside a case_id string.

## Side effects
`git status --short` before and after is identical. `dist/` was rewritten by package-plugin.sh, as in the prior round, and git ignores it. No file in the repo was edited, except for this report.
