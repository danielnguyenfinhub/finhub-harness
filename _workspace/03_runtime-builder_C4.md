# Runtime builder report: C4 (eval regression buckets). Status: PASS

## Files
- src/master_finhub/evals/runner.py (modified): sha256 c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6, 326 lines. Byte-identical to the judge's fix2 runner (r5 verdict).
- tests/test_evals_baseline.py (created): sha256 e6a70140a017e15b572783049ee6cef274d37c05220ab24b7f6f9127c8537529, 581 lines, 97 tests. = design r4 file (3554b065..., 558 lines, 95 tests) + judge's test_stdout_lost_without_devnull_exit_2 + new test_keyboard_interrupt_during_baseline_message_propagates.
- Attribution lines (crewai MIT, AutoGPT classic MIT, revfactory Apache-2.0) are in the runner docstring (lines 3-9) as in the design.

## Claims implemented
A1-A23 per the design (A13 as fixed by the judge's 3-line OSError fallback, accepted by Daniel without a round 6). A13's "KeyboardInterrupt propagates" is now pinned on the unusable-baseline message path by the new test.

## Gate (venv .venv/bin)
- new test file x3, env -u PYTHONUNBUFFERED: `97 passed` x3 (95+1+1 as expected).
- test_evals_baseline.py + test_evals.py: `143 passed`.
- full pytest -q, env -u PYTHONUNBUFFERED: `1319 passed, 10 skipped`; PYTHONUNBUFFERED=1: `1319 passed, 10 skipped`. Before: 1222 passed / 10 skipped (1319 - 97 = 1222; I did not re-run a separate pre-edit full suite on this tree, the delta is exact).
- mypy --strict src: Success: no issues found in 38 source files. ruff check src tests: All checks passed! black --check src tests: 67 files would be left unchanged.
- bash scripts/check-harness-refs.sh: exit 0 (last lines PASS ... PASS packager exit 0). bash scripts/package-plugin.sh: exit 0.
- Hangul (LC_ALL=C.UTF-8 grep -P) on both files: rc 1, no lines.
- 8-word-run check (token-normalised) of runner.py vs crewai experiment/result.py, autogpt classic challenge_loader.py, and skill-testing-guide.md (three copies found under /root/.claude; references/revfactory does not exist in this checkout): 0 hits each.
- Real-process probe (c4r4/probe.sh, tree = repo), buf (env -u) and unbuf (=1): regression normal 3; regression /dev/full, "| true", ">&-", 450-case "| true"/"| head -c1": 2; clean flagged /dev/full, >&-: 2; bad baseline (surrogate, cafe ascii, cafe uncoerced C, /dev/full, | true, >&-, 10MB id | head -c1, normal): 2; good baseline + bad benchmark (/dev/full, | true, normal): 2; surrogate-id regression 3; stderr closed 3. All identical in both modes.
- No-flag rows, exit codes: identical to pre-edit runner in both modes (normal 1/0, bad bench 2; /dev/full 120 buf / 1 unbuf; >&- 1/0). The probe's stdout sha rows differ pre vs post only by the by-design `"schema_version": 1` first key (Decision 4); after masking duration_s the single diff line is that key. The raw sha rows are noisy anyway (duration_s varies run to run).
- No-/dev/null reproduction (r5/nodevnull.py, os.devnull set to a missing path; /dev/full, >&-, and bad-baseline "| true"): 2 in both modes on the built runner. (The pre-edit runner has no --baseline, so its 2 there is an argparse error, not comparable.)
- Mutants: all 75 design mutants (M1-M75) plus J1 (BaseException widening of the message guard) and J2 (OSError fallback removed), on a tar copy (scratchpad b4/tree2), fresh process per mutant, each asserted to change the file exactly once, default (PYTHONUNBUFFERED unset) mode: 77/77 KILLED, survivors []. J1 killed by test_keyboard_interrupt_during_baseline_message_propagates; J2 killed by test_stdout_lost_without_devnull_exit_2. Output: scratchpad b4/mut_b4.out.

## AMBER actions
None. No dependency added; pyproject.toml untouched.

## Deviations from design
None beyond the accepted judge fix and the one added test.

Not run: mutants in PYTHONUNBUFFERED=1 mode (the judge did both; I ran the default mode only, as asked); `-W error` runs (the judge noted 7 expected ResourceWarning errors from the swapped devnull, not a gate); a mount-namespace reproduction of a missing /dev (simulated via os.devnull, as the judge did). One scratch-dir cleanup command was refused by the command hook, so I used fresh scratch directory names; nothing was deleted anywhere.

## Fix after QA (test-only; runner.py unchanged)
- runner.py still sha256 c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6 (326 lines). No src change.
- tests/test_evals_baseline.py: 112 tests (97 + 15), 684 lines, sha256 98a447c63f4ca49bd144cf95b1a4f0a0fff43c8760094a110fc0e0f892b23aa3.
- Added: 7 mixed-bucket exit-3 cases (removed+still_failing, removed+new, removed+fixed, regressed+fixed, regressed+new, regressed+still_failing, all six buckets; each also asserts bucket contents); devnull-is-a-directory (EISDIR) and devnull open raising EMFILE (builtins.open patched for the devnull path) with stdout None and a regression: exit 2; no benchmark paths with and without --baseline: SystemExit 2; 3, 4 and 6 failing cases with no baseline: exit 1 and failed == n; baseline with invalid UTF-8 byte inside a case_id string: exit 2 ("cannot read (UnicodeDecodeError)").
- Gates: new file x3 in each mode: `112 passed` x6. Full pytest -q: `1334 passed, 10 skipped` with `env -u PYTHONUNBUFFERED` and with `PYTHONUNBUFFERED=1` (1319 + 15). mypy --strict src clean (38 files); ruff check src tests clean; black --check src tests: 67 files unchanged; check-harness-refs.sh exit 0; package-plugin.sh exit 0; Hangul rc 1; secret-pattern grep rc 1.
- Mutants (tar copy, fresh process each, change verified, default mode): 75 design + J1 + J2 + Q34, R01, R02, R03, R05, R07, Q21, Q33, R33a, R33b, Q12 = 88 run, 88 KILLED, survivors []. QA's definitions taken from scratchpad qa/fresh.py, fresh3.py and Q12 from fresh2.py (the fresh.py Q12 pattern matches two lines; the anchored fresh2 version targets the baseline loader). Output: scratchpad b4/mut_b5.out.
- Not run in this round: mutants in PYTHONUNBUFFERED=1 mode; QA's other follow-up items (not added, per instruction).
