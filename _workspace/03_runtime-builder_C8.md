# C8 build report (runtime-builder)

Status: PASS. No deviations. Nothing committed or pushed.

## Preconditions
- Branch claude/tender-brown-8us2kt, HEAD 0474fc5 = origin/main (after git fetch), `git status` clean, `git diff origin/main HEAD` empty.
- Patch sha256 e958910679608d6d0f8e990b68b73f26e3776f3a4f05e6d8e09c796aa78ca5ef (verified). `git apply --check` clean, then `git apply`.

## Files (only these three changed; dist/ is gitignored)
| path | state | lines | sha256 |
|---|---|---|---|
| src/master_finhub/runtime/repeat_reminder.py | created | 64 | 074a51f279db8b42da9fa1f5cab95b200dc3b5f16a469b191bfbbfb447902445 |
| src/master_finhub/runtime/loop.py | modified (+16/-2) | 248 | cf74139b815fd8bb29964b0a57bd2ed9a4e81a7bb0a606fa5f1fd5218c4c0bdd |
| tests/test_repeat_reminder.py | created | 563 | 27c520bbc22790f810a2f4ee111f9df04892a4bff1031dd54ae3c58971404b13 |

All three digests equal those stated in the design (C8.md lines 258-260) and judge r3.

## Claims implemented
A1-A17 and N1-N18 exactly as in the patch; nothing added. Judge follow-ups (F1 2-hex digest prefix, F2 escaped bound pinned only by a command, F3 refactor-tight tests, tuple/list key collision, padding evasion, small clip_budget_tokens clipping the notice) NOT built: for the PR description.

## Gate
| command | result |
|---|---|
| `.venv/bin/python -m pytest tests/test_repeat_reminder.py -q` | 61 passed in 0.36s |
| `env -u PYTHONUNBUFFERED .venv/bin/python -m pytest -q` | 1403 passed, 10 skipped in 99.74s |
| `PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q` | 1403 passed, 10 skipped in 99.98s (flaky test_safety timing test did not fire) |
| `ruff check src tests` | All checks passed! (rc 0) |
| `black --check src tests` | 69 files would be left unchanged |
| `mypy --strict src` | Success: no issues found in 39 source files |
| `.venv/bin/python -m pytest tests -k repeat -q` | 64 passed, 1349 deselected |
| `bash scripts/check-harness-refs.sh` | 0 FAIL, packager exit 0 |
| `bash scripts/package-plugin.sh` | rc 0, lint_harness 0 errors 0 warnings, dist/finhub-harness.plugin 104285 bytes |
| `LC_ALL=C.UTF-8 grep -nP '\p{Hangul}'` over the 3 files | no output, rc 1 |
| secrets grep (`sk-`, BEGIN RSA/PRIVATE, AKIA, ghp_, password=) over the 3 files | no output, rc 1. A broader first pattern (`secret`, `token=`) matched only the identifiers `redact_secrets` / a local variable named `secret` in the test: not secrets |
| attribution in repeat_reminder.py docstring | present: "Adapted (idea only, own code) from the MIT-licensed deepseek-harness ... index.ts (:103, :189-198, :199, :200); and from autogpt classic watchdog.py:32 (MIT)" |

## Mutation run (tar copy, fresh process per mutant, adapted runner paths only)
Command: `.venv/bin/python _workspace/02_strategy-architect_C8_mutate.py /home/user/finhub-harness <scratchpad>/mut <venv python>`, 3m22s.
`TOTAL 101: killed 96, survived-equivalent 5, unexpected survivors/partial 0`. Survivors: T25, T26, S18, Z11, Z36 (the declared equivalents). Output kept in the scratchpad (mut.out), not in the repo.

## AMBER actions
None (no dependency changes).

## Deviations from design
None.

## Final `git status --short`
```
 M src/master_finhub/runtime/loop.py
?? src/master_finhub/runtime/repeat_reminder.py
?? tests/test_repeat_reminder.py
```

## Fix after QA (test-only)
QA found one false-pass survivor class: nothing asserted that the tool and the guard receive exactly the model's id, name and arguments (A11, A13, L13, A4).
- Added `test_the_tool_and_the_guard_receive_exactly_what_the_model_sent` to tests/test_repeat_reminder.py (recording tool and guard, ten identical calls with nested, key-ordered, non-ASCII arguments; asserts the tool got `[args]*10` with key order intact and the guard saw `(c1..c10, "echo", args)`). No change to src/.
- tests/test_repeat_reminder.py now 585 lines, 41 functions / 62 cases, sha256 0d8b0b773632b3f833e99308308e47856ec596f8deb9b22bb8f9cadf5f6070e9.
- src unchanged: repeat_reminder.py 074a51f2...2445, loop.py cf74139b...bdd (byte-identical to the patch).
- Gates: repeat tests x3 in both modes 62 passed each; full pytest `env -u PYTHONUNBUFFERED` 1404 passed, 10 skipped (101.80s); `PYTHONUNBUFFERED=1` 1404 passed, 10 skipped (99.74s); flaky timing test did not fire; ruff, black (69 unchanged), mypy --strict (39 files) clean; check-harness-refs 0 FAIL; package-plugin rc 0; Hangul rc 1; secrets rc 1.
- Mutants on a tar copy (src tests skills .claude .gitignore pyproject scripts; baseline 67 passed on test_repeat_reminder + test_loop), fresh `python -B` per mutant, each diff verified 1 changed line: A11 (tool run on dict(args,_x=1) in _execute) killed; L13 (same in _run_tool) killed; A13 (guard sees id+"x") killed; A4a (guard sees name+"x"), A4b (guard sees extra arg), A4c (guard sees reversed key order) all killed. Each: 1 failed, 66 passed. Architect runner re-run: TOTAL 101: killed 96, survived-equivalent 5, unexpected 0.
- Still not built, for the PR description: F1, F2, F3, tuple/list key collision, padding evasion, small clip_budget_tokens, 0.3 s / 300 MB transient on a 100 MB argument.
