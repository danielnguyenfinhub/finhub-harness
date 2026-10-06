# Runtime builder - fix round for QA advisories (slices 10 and 11)  STATUS: PASS

## Files (all modified, none created)
- src/master_finhub/server/app.py, src/master_finhub/evals/runner.py
- tests/test_server.py, tests/test_sse.py, tests/test_evals.py
No pyproject/dependency change (no AMBER). No commit.

## Items, tests (each written first and seen red)
1. Host userinfo: `_hostname` is now a strict `host[:port]` / `[v6][:port]` parse (rejects @, backslash, whitespace, control, non-printable, empty host, empty/non-numeric/over-65535 port, extra colons, bad brackets). Tests: test_strict_host_parse_refuses_421 (25 raw-socket cases), test_strict_host_parse_keeps_loopback_names (6), test_duplicate_or_missing_or_empty_host_421.
2. Read timeout: `READ_TIMEOUT_S = 30.0`, `make_server(read_timeout_s=)`, applied in `_Handler.setup`. Tests: test_slow_body_handler_is_released_by_read_timeout, test_idle_preauth_connection_is_released_by_read_timeout (thread count back to baseline), test_read_timeout_does_not_cut_an_idle_sse_stream (stream silent 0.6 s with 0.2 s read timeout still delivers done).
3. Client drop: test_client_drop_before_reply_is_quiet (RST before 401 and before 413; `handle_error` never called).
4. BaseException in run thread: always queues ERROR (class name only). Test: test_run_thread_always_queues_a_terminal_event_on_baseexception (secret absent, _running back to 0, 1 s idle so failure is fast).
5. main(): test_main_default_uses_scripted_llm_and_prints_key_once, test_main_profile_branch_builds_llm_through_router, test_main_ctrl_c_exits_zero_and_closes, test_main_bad_arguments_exit_2 (serve_forever patched; no real server).
6. test_sse.py::test_dropping_error_from_terminal_set_is_caught_fast (0.3 s), plus test_error_is_terminal and server test_agent_error_event_has_class_name_only now use short idle timeouts so the mutant fails in ~0.3-2 s, not 300 s.
7. Duplicate ids: `run_suite` loads all cases then rejects any repeated case_id (explicit or derived) with a ValueError naming it, before running anything. Tests: test_duplicate_explicit_ids_rejected, test_main_exit_2_on_duplicate_ids.
8. cutoff_s: must be a finite non-bool number >= 0, else ValueError naming cutoff_s. Tests: test_cutoff_s_must_be_finite_non_negative_number (nan, inf, -inf, -1, True, "5", None), test_main_exit_2_on_nan_cutoff (literal NaN in JSON).

## Mutation results (scratchpad copy, repo untouched; script and copy under the session scratchpad)
| mutant | result | killed by |
|---|---|---|
| _hostname loosened to urlsplit | KILLED | test_strict_host_parse_refuses_421[evil.com@localhost] |
| socket timeout removed | KILLED | test_slow_body_handler_is_released_by_read_timeout (idle test also covers) |
| BrokenPipe/Reset catch dropped | KILLED | test_client_drop_before_reply_is_quiet |
| run thread `except Exception` (no BaseException terminal) | KILLED | test_run_thread_always_queues_a_terminal_event_on_baseexception |
| ERROR dropped from TERMINAL | KILLED | test_dropping_error_from_terminal_set_is_caught_fast (0.33 s), test_agent_error_event_has_class_name_only (1.6 s) |
| duplicate ids accepted | KILLED | test_duplicate_explicit_ids_rejected |
| NaN cutoff accepted | KILLED | test_cutoff_s_must_be_finite_non_negative_number[nan] |
| negative cutoff accepted (extra) | KILLED | ...[-1] |
| duplicate Host header accepted (extra) | KILLED | test_duplicate_or_missing_or_empty_host_421 |
(The first ERROR-mutant run showed SURVIVED only because my selector included the old 300 s test and my harness timed out; re-run individually, both new tests fail fast. The old test was shortened.)

## Flakiness / strays
Timing tests (timeout, slow body, idle, drop, baseexception, terminal/error, main) x10: 10/10 `16 passed` in 5.1 s each. `pgrep` after: no stray pytest or master_finhub processes. /tmp/mf_eval_* count 28, unchanged (pre-existing mutant leftovers noted by QA, not touched).

## Gate (.venv/bin/python, repo root)
- pytest -q: exit 0, `676 passed, 9 skipped`
- ruff check src tests: exit 0, `All checks passed!`
- black --check src tests: exit 0, `65 files would be left unchanged.` (py3.15 target warning only)
- mypy --strict src: exit 0, `Success: no issues found in 40 source files`
- proof echo_pass.json: exit 0, suite pass_rate 1.0
- proof tests/fixtures/evals/echo_fail.json: exit 1, pass_rate 0.0 (clean grading failure)

## Deviations (with reason)
- Item 3: the catch is in `_Handler.handle()` rather than only `_send`/`_fail`. A client reset can also surface in the body read (`rfile.read`) on the 413 path; one catch at `handle` covers every path with no per-call duplication.
- Item 4: the BaseException is NOT re-raised. A worker thread has no caller; re-raising only makes threading's excepthook print the exception text (possible secret) to stderr. The error event carries the class name only.
- Item 1 extra: duplicate Host headers are now refused whatever their order (QA table said "duplicate refused" but only first-evil was; first-good/second-evil was accepted).
- Item 7: duplicate check is in `run_suite` (a single file cannot duplicate itself), covers derived ids too, as asked ("reject any duplicate id within one suite"). Passing the same file twice is therefore exit 2.
- Item 8: cutoff_s 0 stays valid (existing timeout test relies on it); only negative is rejected.
- Not done: no connection-level cap on handler threads beyond the read timeout; Host header values with leading/trailing spaces are stripped by the HTTP parser before `_hostname` sees them (standard, harmless).
