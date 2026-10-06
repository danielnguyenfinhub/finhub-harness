RESULT: PASS

Scoped re-run of C8 after the builder's test-only fix. src is unchanged, the new test is in and effective, and the defect from `_workspace/03_boundary-qa_C8.md` (the missing exact-arguments pin) is closed. No new false-pass survivor appeared.

## Gate

| # | command | exit | output observed |
|---|---|---|---|
| R1 | `git status --short` | 0 | ` M src/master_finhub/runtime/loop.py` / `?? src/master_finhub/runtime/repeat_reminder.py` / `?? tests/test_repeat_reminder.py` |
| R2 | `sha256sum` of the 3 files, `wc -l`, `grep -c "^def test_"` | 0 | repeat_reminder.py `074a51f2...902445` (unchanged); loop.py `cf74139b...c0bdd` (unchanged); test file `0d8b0b773632b3f833e99308308e47856ec596f8deb9b22bb8f9cadf5f6070e9`, 585 lines, 41 functions; 62 cases per the pytest count in R5 |
| R3 | clean `git archive HEAD` + patch in a scratch dir, `diff` of its test file (sha `27c520bbc22790f8...`, 563 lines) against the repo test file | 1 (diff) | only `255a256,277` added: `test_the_tool_and_the_guard_receive_exactly_what_the_model_sent` (22 lines, 563 + 22 = 585); nothing removed or altered |
| R4 | `env -u PYTHONUNBUFFERED .venv/bin/python -B -m pytest -q -p no:cacheprovider` (foreground) | 0 | `1404 passed, 10 skipped in 101.02s (0:01:41)` |
| R4b | `PYTHONUNBUFFERED=1 ...` (foreground, after R4) | 0 | `1404 passed, 10 skipped in 100.32s (0:01:40)` |
| R5 | `pytest -q tests/test_repeat_reminder.py`, then `tests -k repeat`, both modes | 0 | `62 passed` and `65 passed, 1349 deselected` in both modes |
| R6 | `ruff check src tests`; `black --check src tests`; `python -m mypy --strict src`, both modes | 0 | `All checks passed!`; `69 files would be left unchanged.`; `Success: no issues found in 39 source files` |
| R7 | `bash scripts/check-harness-refs.sh \| grep -c FAIL`; `bash scripts/package-plugin.sh` | 0 / 0 | `0`; `pkg rc=0` |
| R8 | Hangul `LC_ALL=C.UTF-8 grep -nP '\p{Hangul}'` over the 3 files; secrets grep over repeat_reminder.py and the test | 1 / 1 | `hangul rc=1`, `secrets rc=1`, no output |
| R9 | `git status --short` at the end | 0 | same three lines as R1 (dist/ is gitignored); no scratch files in the repo |

The flaky `test_safety.py::test_adversarial_inputs_are_linear` did not fire in R4 or R4b.

## The new test (read in full, tests/test_repeat_reminder.py:256-277)

- It builds `args = {"b": 2, "a": [1, {"z": 1, "y": "é"}]}`: key order `b, a` (not sorted), a nested dict with order `z, y`, and a non-ASCII value.
- It runs ten identical calls through `_run(...)`, which builds a real `AgentLoop`; only the tool's `run` is replaced by a recorder that stores the received `arguments`, and the guard only records `(call.id, call.name, call.arguments)`. The loop, `_execute`, `_run_tool` and the reminder are real, so the thing under test is not mocked.
- Assertions: `got == [args] * 10` and `[list(g) for g in got] == [["b", "a"]] * 10`, `[list(g["a"][1]) ...] == [["z", "y"]] * 10`; `seen == [(f"c{i}", "echo", args) for i in range(1, 11)]` and the guard-seen key order `[["b", "a"]] * 10`. This is the exact shape I specified.

## Mutants (scratch tar copy of src, tests, skills, .claude, .gitignore, pyproject.toml, scripts; fresh `python -B` process per mutant; every mutation verified real by a non-empty diff; test set `tests/test_repeat_reminder.py test_loop.py test_context.py test_checkpoint.py test_lint_harness.py`)

Unmutated baseline first: `BASELINE SURVIVED 188 passed, 4 skipped` (green, no failures).

Previously false-pass survivors, now killed, each by exactly the new test and no other:

| id | mutation | result |
|---|---|---|
| A11 | `_execute` runs the tool on `dict(call.arguments, _x=1)` | KILLED, `1 failed, 187 passed`: `test_the_tool_and_the_guard_receive_exactly_what_the_model_sent` only |
| A13 | `_execute` runs a call whose id is `'x' + call.id` | KILLED, same single test |
| L13 | `_run_tool` calls `tool.run(dict(call.arguments, _x=1))` | KILLED, same single test |
| A4 | guard sees a call with `{}` | KILLED, same single test |
| A4a | guard sees `name + 'x'` | KILLED, same single test |
| A4b | guard sees an extra `_x` argument | KILLED, same single test |
| A4c | guard sees the arguments in reversed key order | KILLED, same single test |

Earlier survivors, classification unchanged (all remain SURVIVED, all equivalent, reasons as in the first report): Q10 (count `<=`, branch only reached at count >= 3), Q33 (`utf-8` vs `ascii`, text is pure ASCII), Q41 (`min(count, 8)`, counts above 8 are silent either way), L08 (reset in `_uncertain`, called once from `resume()` after the reset), L16 (dead code), L18 and L19 (reset moved after `messages=` / `_save`, the hook never reads the counter), A9 (call copy, equal value).

Earlier killed mutants, still killed: A1 (5 failed), A2 (8), A3 (57), A5 (5), A6 (20), A7 (4), A8 (15), A10 (2; one of them is the new test), A12 (7), A14 (6; one of them is the new test).

No second general batch was run. No new false-pass survivor was found.

## Defects
None. Observations carried over unchanged: `observe` builds the full JSON text before the cap check (about 0.3 s and 300 MB transient for a 100 MB argument); judge follow-ups F1, F2, F3, tuple/list collision and padding evasion remain not built.
