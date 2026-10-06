# Slice 11 report (runtime-builder) - status PASS

## Files
- src/master_finhub/evals/__init__.py (created)
- src/master_finhub/evals/verifiers.py (created) - Expectation, Grading, contains, VERIFIERS = {"contains"}
- src/master_finhub/evals/runner.py (created) - Benchmark, CaseResult, SuiteReport, load_benchmark, run_case, run_suite, main
- src/master_finhub/evals/benchmarks/echo_pass.json (created, shipped, passes)
- tests/fixtures/evals/echo_fail.json (created, must fail)
- tests/test_evals.py (created, 25 tests incl. parametrized)
Root-level evals/ stubs untouched. No existing file modified.

## Claims implemented
A51-A64, A71, A78 (A65-A70 are N/A rulings, see below).

## Tests (test-first; collection error confirmed before src existed)
test_contains_all_present, test_contains_forbidden_present, test_contains_case_insensitive,
test_contains_empty_ground_scores_zero, test_evidence_is_bounded, test_pass_benchmark_passes,
test_fail_benchmark_fails, test_crash_becomes_failed_result, test_step_limit_is_failure,
test_cutoff_marks_timed_out, test_unknown_eval_type_rejected, test_missing_field_rejected[5],
test_file_entry_outside_workspace_fails, test_tools_get_case_workspace, test_agent_never_sees_ground,
test_case_id_stable_and_explicit, test_suite_continues_after_crash, test_main_exit_codes.

## Gate
- pytest -q: exit 0 (610 passed, 9 skipped; skips are docker/pre-existing)
- ruff check src tests: exit 0 (All checks passed!)
- black --check src tests: exit 0 (65 files would be left unchanged)
- mypy --strict src: exit 0 (no issues in 40 source files)
Proof commands: echo_pass.json -> pass_rate 1.0, exit 0; echo_fail.json -> pass_rate 0.0, exit 1.

## AMBER actions
None. No dependency added.

## Deviations from design
- passed additionally requires grading.total > 0 (an empty ground cannot pass vacuously). Reason: pass_rate is 0.0 for total==0 per design, so passing it would be inconsistent.
- score is forced to 0.0 on timeout (design says score = grading.pass_rate; on timeout grading is None anyway, so identical).
- Benchmark.ground typed dict[str, Any] rather than Mapping (frozen dataclass, JSON-loaded); no behaviour change.
- main accepts multiple benchmark paths and prints the full SuiteReport JSON (pass_rate at top level plus per-case results incl. duration_s and steps; no token metering, fake LLM has none).
- Expectation text for forbidden phrases is `output lacks "<phrase>"`; required is `output contains "<phrase>"` (matches the test spec).

## Quant guardrails as ruled
G1 fees, G2 borrow, G3 slippage, G4 look-ahead, G5 survivorship, G6 train/test leakage: all N/A (A65-A70). Slice computes no prices, returns, fills, series or splits; the schema has no such fields. Forward rule enforced by A64: unknown eval.type is rejected at load (test_unknown_eval_type_rejected also asserts set(VERIFIERS) == {"contains"}).

## Retry (boundary-qa FAIL: D1, D2, S1, S2) - status PASS
Test-first: 9 new tests failed before the fix. Changes in src/master_finhub/evals/runner.py only:
- D1: empty/whitespace phrases in should_contain/should_not_contain rejected at load (ValueError naming the field).
- D2: `isinstance(etype, str) and etype in VERIFIERS`; list/dict/int/None types are ValueError naming ground.eval.type; main exits 2.
- Extras: `case_sensitive` must be bool (ValueError); mkdtemp moved inside the try (failure becomes a failed result); spy test now also covers tool parameters and repr of every message (tool_call args).
- New tests: test_empty_phrase_rejected[x4], test_non_string_eval_type_is_valueerror[x4], test_main_exit_2_on_bad_eval_type, test_case_sensitive_must_be_bool, test_empty_ground_cannot_pass, test_workspace_cleaned_after_crash, test_workspace_cleaned_after_timeout, test_mkdtemp_failure_is_failed_result.
- Gate: pytest -q exit 0 (624 passed, 9 skipped); ruff exit 0; black --check exit 0; mypy --strict exit 0.
- Proof: echo_pass exit 0 pass_rate 1.0; echo_fail exit 1 pass_rate 0.0.
- Mutants (scratchpad copy): D1 killed (test_empty_phrase_rejected x4); D2 killed (test_non_string_eval_type_is_valueerror[list,dict], test_main_exit_2_on_bad_eval_type); S1 killed (test_empty_ground_cannot_pass); S2 killed (test_workspace_cleaned_after_crash, _after_timeout).
