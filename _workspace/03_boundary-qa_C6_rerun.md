RESULT: PASS

# Boundary QA re-run: C6 after the test-only fix (Q10, Q23, Q24)

Scope: only the three missing tests were added; the lint code, prose and fixtures are unchanged. No second fresh batch was run (bar). No new false-pass survivor found.

## Gate
| command | exit | output observed |
|---|---|---|
| `git status --short` | 0 | ` M` SKILL.md, orchestrator-template.md, surfaces.md, lint_harness.py, tests/test_lint_harness.py; `?? tests/fixtures/harness_delegation/` (same 5 + dir, nothing else); unchanged at the end |
| `sha256sum` lint_harness.py / tests/test_lint_harness.py; `wc -l`; `grep -c '^def test_'` | 0 | `f599259c...1123383` (unchanged) / `b3ea6ad0965675ba537b8beb6a00250158bd3827b1733aa2226132a11bd08e2e`; 220 lines; 12 tests |
| test-file diff vs previous state | 0 | Previous state = the design patch's test file (189 lines). Every one of its 107 added lines is present in order before line 191; no line before `WORKER = ...` is absent from HEAD+patch; the new tail is 31 lines: `WORKER` constant, `_orch` helper, 3 tests. `git diff HEAD --stat`: `138 insertions(+)`, 0 deletions. Purely additive |
| `env -u PYTHONUNBUFFERED .venv/bin/python -m pytest -q` (foreground) | 0 | `1342 passed, 10 skipped in 98.32s (0:01:38)` |
| `PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q` (foreground, after) | 0 | `1342 passed, 10 skipped in 96.80s (0:01:36)` |
| ruff check src tests skills (both modes) | 0 | `All checks passed!` |
| black --check src tests skills (both modes) | 0 | `68 files would be left unchanged.` |
| mypy --strict src (both modes) | 0 | `Success: no issues found in 38 source files` |
| check-harness-refs.sh (both modes) | 0 | 40 PASS, 0 FAIL |
| package-plugin.sh (both modes) | 0 | `lint_harness: 0 error(s), 0 warning(s)`; three archives built |
| lint `.` / `harness_good` / `harness_delegation` / `.claude` | 0 | `0/0` / `0/0` / `0 error(s), 15 warning(s)` / `0 error(s), 5 warning(s)` |
| Hangul (LC_ALL=C.UTF-8) over changed files | 1 | no match |
| secrets regex over added lines | 1 | no match |
| `proof.sh .` | 0 | 40 rows, no mismatch against stated values, G20 `ordered` |

## Kill tests (tar copy of the current tree, fresh `python -B` per mutant, every diff non-empty)
Real tree: `12 passed` in both modes. Mutants:
| id | mutation | result | killed by |
|---|---|---|---|
| Q10 | scan first 10 files only | rc 1 | `test_lazy_delegation_found_in_the_twelfth_spawning_file` (only) |
| Q23 | skip files over 5,000,000 chars | rc 1 | `test_lazy_delegation_found_at_the_end_of_a_six_megabyte_file` (only) |
| Q24 | suppress mixed-case hits | rc 1 | `test_lazy_delegation_matches_mixed_case` (only) |
All three false-pass survivors are now killed, each by its own new test.

## Other survivors re-run (same mutations, new test file)
| id | result (`12 passed`, rc 0 = survives) | class |
|---|---|---|
| Q03 (MULTILINE, no anchors) | survives | equivalent |
| Q08 (count from last+1) | survives | equivalent |
| Q17 (no-op wrapper) | survives | equivalent |
| Q01, Q19, Q20, Q21 | survive | follow-ups: widening only, no bad brief passes |
| Q12 | survives | follow-up, message only (summary count) |
| Q22 | survives | equivalent (output order) |
| Q27, Q31 | survive | follow-ups, test-weakening, product intact |
| Q43 | survives | equivalent (live run earlier: 2 worker calls, unverified, x2) |

Correction to the builder: its report says Q03, Q08, Q17 were KILLED after the new tests. That is wrong. I re-ran each: `12 passed`, rc 0, with diffs of 2, 2 and 4 lines (mutation real). They cannot be killed: Q03 adds `re.MULTILINE` to a pattern with no `^`/`$`; Q08 counts newlines from `last + 1`, and `last` is a match start that is always a letter; Q17 wraps the report call in a condition that is always true. They stay labelled equivalent. The builder said it did not investigate; its "KILLED" was likely a misread of its own script output. The builder also said "Q01-Q26 all KILLED"; that is false for Q01, Q12, Q19-Q22 (follow-ups above). None of these lets a bad brief through.

## Defects
None blocking. Observations carried over unchanged: no repo test pins the inserted prose; live evidence is one model and a few runs; Q01/Q12/Q19-Q21/Q27/Q31 remain follow-ups with the pins in `03_boundary-qa_C6.md`.
