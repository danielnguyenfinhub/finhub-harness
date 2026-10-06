RESULT: PASS

# Boundary QA - slice 11 (evals runner + verifiers), re-verification after retry

Previous defects D1, D2, S1, S2 re-checked independently against the real code: all closed. No new defects.

## Scope
- `git status --short`: only `?? src/master_finhub/evals/`, `?? tests/fixtures/`, `?? tests/test_evals.py`. `git diff HEAD --stat` empty: no tracked file modified, no pyproject/dependency change.
- Compliance sweep (emails, AU mobiles, key patterns) of evals/, tests/test_evals.py, tests/fixtures: no hits.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| benchmark JSON -> loader | echo_pass.json / echo_fail.json: name, task, max_steps, cutoff_s, ground{files, should_contain, should_not_contain, case_sensitive, eval.type} | runner.py:72-103 validates each, `eval.type` must be str in VERIFIERS, phrases non-blank, case_sensitive bool | yes |
| loader -> verifier | Benchmark.ground dict | verifiers.py `contains` reads should_contain / should_not_contain / case_sensitive | yes |
| load error shape | design B6: ValueError naming field -> exit 2 | all bad inputs below raise ValueError; main prints, returns 2, no traceback | yes (D2 closed) |
| verifier not trivially satisfiable | A59 | empty/blank phrases rejected at load; empty ground fails (`total > 0`) | yes (D1, S1 closed) |
| tools_factory(ws) | Callable[[Workspace], list[Tool]] | runner.py:127 passes the case Workspace | yes |
| runner -> AgentLoop / CheckpointHook | loop.py signature, LoopSnapshot.step | runner.py:125-132 | yes |
| SuiteReport/CaseResult/Grading -> CLI JSON | dataclass fields | `asdict(report)` printed; test_main_exit_codes asserts pass_rate | yes |

## Gate (.venv/bin/python)
| command | exit | output |
|---|---|---|
| pytest -q | 0 | `624 passed, 9 skipped in 41.68s` |
| ruff check src tests | 0 | `All checks passed!` |
| black --check src tests | 0 | `65 files would be left unchanged.` (py3.15 target warning only) |
| mypy --strict src | 0 | `Success: no issues found in 40 source files` |
| proof echo_pass.json | 0 | suite `pass_rate: 1.0` |
| proof tests/fixtures/evals/echo_fail.json | 1 | suite `pass_rate: 0.0`, `error: null`, failing expectation `output contains "42"` evidence `"41"` (clean grading failure, not a crash) |

## Raw-input probes (real code, load_benchmark/run_case plus `main` subprocess)
| input | result |
|---|---|
| should_contain `[""]`, `[" "]`; should_not_contain `[""]` | ValueError at load; main exit 2, no traceback |
| eval.type list / dict / int / None / "llm"; eval a string; eval missing; ground `{}` | ValueError; main exit 2, no traceback |
| case_sensitive "false" / 1 | ValueError; main exit 2 |
| ground with eval only (no lists) | runs, passed False (total 0); main exit 1 |
| files `["../x"]`, `["/etc/passwd"]` | failed case, `SandboxDenied ... [path outside workspace]`; main exit 1 |
| files `[1]`, id 5, max_steps True | ValueError; main exit 2 |
| bad JSON, missing file, directory path | exit 2, no traceback |
| duplicate explicit ids (`same`, `same`) | both run, report has two results with the same case_id (see N1) |

## Mutation testing (scratchpad copy only; repo untouched, no rm -rf)
| mutation | result | named test |
|---|---|---|
| D1 drop empty-phrase check | KILLED | test_empty_phrase_rejected |
| whitespace-only allowed (strip dropped) | KILLED | test_empty_phrase_rejected |
| D2 drop isinstance(etype, str) | KILLED | test_non_string_eval_type_is_valueerror, test_main_exit_2_on_bad_eval_type |
| S1 drop `grading.total > 0` | KILLED | test_empty_ground_cannot_pass |
| S2 cleanup only on success | KILLED | test_workspace_cleaned_after_crash, test_workspace_cleaned_after_timeout |
| accept unknown eval type | KILLED | test_unknown_eval_type_rejected |
| leak ground to agent task | KILLED | test_agent_never_sees_ground (+4 more) |
| exception escapes run_case | KILLED | test_crash_becomes_failed_result (+4) |
| any() instead of all() | KILLED | test_fail_benchmark_fails, test_main_exit_codes, test_suite_continues_after_crash |
| drop should_not_contain | KILLED | test_contains_forbidden_present |
| skip case workspace to tools_factory | KILLED | test_tools_get_case_workspace (+2) |
| allow ../ entries | KILLED | test_file_entry_outside_workspace_fails |
| drop cutoff CheckpointHook | KILLED | test_cutoff_marks_timed_out |
| sha256 id -> constant | KILLED | test_case_id_stable_and_explicit |
| case_sensitive bool check dropped | KILLED | test_case_sensitive_must_be_bool |
| mkdtemp outside try | KILLED | test_mkdtemp_failure_is_failed_result |
| casefold ignored | KILLED | test_contains_case_insensitive |
| timeout passes (`ok = True`) | SURVIVED - equivalent: the next line still requires `grading is not None`, and a timed-out case has grading None |
| score kept on timeout | SURVIVED - equivalent: grading is None on timeout, so score is 0.0 either way |

## Determinism and leaks
- CLI pass+fail suite x10 with `duration_s` lines removed: 1 distinct md5. `pytest tests/test_evals.py` x10: 36 passed each time.
- `/tmp/mf_eval_*` count: 22 before gate and proofs, 22 after (real code leaks nothing). 28 later only because the S2 / mkdtemp mutants deliberately leak; count stayed 28 across the 20 determinism runs. Dirs predate this run (earlier mutant runs) and are not from the real code.

## Defects
None.

## Notes (non-blocking)
- N1: duplicate explicit `id` values across a suite are not rejected; two results share a case_id. Outside the slice's declared interface.
- N2: `cutoff_s` NaN is accepted (`float("nan")` -> cutoff never fires, case passed). Negative values time out. Consider rejecting non-finite values.
- N3: leftover `/tmp/mf_eval_*` dirs from earlier mutant runs can be cleaned by Daniel at will; I did not delete them.
