Outcome: PARTLY DONE. Slices 8, 9, 10 and 11 are built, merged and pass the gate. Slice 12 (factory) is deferred, and the docker execution path in slice 8 has never been run against a real daemon.

# Master FinHub runtime - final report, resumed build (slices 8-11)

Read and run 2026-10-02 (AEST), branch `claude/tender-brown-8us2kt` at commit 967ec1b, `.venv/bin/python` = Python 3.11.15. Slices 1-7 were built in an earlier session and are out of scope here.

## Built
| slice | what it gives you | files |
|---|---|---|
| 8 | Docker sandbox engine (hardened `docker run`, kill on timeout) and a bounded process-output stream | src/master_finhub/sandbox/stream.py, sandbox/docker_engine.py, tests/test_stream.py, tests/test_docker_engine.py |
| 9 | Stdio MCP client with bounded reader, page cap, server-request reply and safe teardown | src/master_finhub/tools/mcp/client.py, tests/mcp_stub_server.py, tests/test_mcp_client.py |
| 10 | Loopback HTTP server streaming agent runs over SSE | src/master_finhub/server/sse.py, server/app.py, tests/test_sse.py, tests/test_server.py |
| 11 | Deterministic eval runner and string-match verifier, one shipped passing benchmark, one must-fail fixture | src/master_finhub/evals/__init__.py, evals/verifiers.py, evals/runner.py, evals/benchmarks/echo_pass.json, tests/fixtures/evals/echo_fail.json, tests/test_evals.py |

Source: `_workspace/03_runtime-builder_slice{8,9,10,11}.md` Files sections, read 2026-10-02.

## Passed
Whole-tree gate, re-run by me on 2026-10-02 at commit 967ec1b (`.venv/bin/python -m ...`):

| command | exit | output |
|---|---|---|
| pytest -q | 0 | `624 passed, 9 skipped in 40.86s` |
| ruff check src tests | 0 | `All checks passed!` |
| black --check src tests | 0 | `65 files would be left unchanged.` (plus a warning that Python 3.11 cannot parse code formatted for 3.15; target-version inference, not a failure) |
| mypy --strict src | 0 | `Success: no issues found in 40 source files` |
| proof: `python -m master_finhub.evals.runner src/master_finhub/evals/benchmarks/echo_pass.json` | 0 | suite `passed 1, failed 0, total 1`; expectations 2 passed, 0 failed |
| proof: `python -m master_finhub.evals.runner tests/fixtures/evals/echo_fail.json` | 1 | suite `passed 0, failed 1, total 1, pass_rate 0.0`; case `error: null`, `timed_out: false`; expectation `output contains "42"` failed with evidence `"41"` (a graded failure, not a crash) |

The 9 skips (`pytest -rs`, this session): 4 checkpoint tests (win32 only), 1 docker test (daemon or image not available), 4 workspace tests (Windows paths or junctions only). Exactly one of them belongs to slices 8-11 (see Gaps).

Per-slice RESULT history (from `_workspace/03_boundary-qa_slice{N}.md` first lines and their notes, read 2026-10-02; the first-pass FAIL reports were overwritten, so the first-pass details come from the retry reports):

| slice | history | current RESULT |
|---|---|---|
| 8 | FAIL once on test strength (mutants M2, M3, M4 survived), fixed on retry; all three now killed | PASS |
| 9 | FAIL once on test strength (mutants M7a, M7b survived; env scrubbing unasserted), fixed on retry (tests and stub only, client.py unchanged) | PASS |
| 10 | PASS first time | PASS |
| 11 | FAIL once on loader defects and test strength (D1 empty phrase accepted, D2 non-string `eval.type` crashed, S1 empty ground could pass, S2 workspace cleanup only on success), fixed on retry; all four closed | PASS |

Gate counts in the per-slice reports at the time: slice 8 `540 passed, 9 skipped`; slice 9 `562 passed, 9 skipped`; slice 11 `624 passed, 9 skipped`. Slice 10's count is not restated here.

## Adversarial audit outcome
Source: `_workspace/02_adversarial-risk-judge_verdict.md`, read 2026-10-02.
- Authority List: 78 claims (A1-A78).
- Round 1: REJECTED 3 (A3, F1, F2; UPHELD 71, UNVERIFIED 0).
  - A3: the cited line separates agents, not runs.
  - F1: the MCP line cap, page cap and `-32601` reply had no row, and the reader was unbounded.
  - F2: the bounded queue had no row, and an abandoned full queue leaked blocked readers.
- Round 2: REJECTED 0, UPHELD 78, UNVERIFIED 0. All three rejections were confirmed fixed.
- NET-NEW rows: 25. I counted them in `02_strategy-architect_slices.md` (78 Authority List rows, 25 containing "NET-NEW"). The judge states each NET-NEW decision carries a named test. I did not individually re-verify all 25 named tests this session.
- The judge's round-2 non-blocking notes N7-N9 were applied by the builders (the slice 9 QA report confirms the request cap and the char limit). N6 (document the MCP prompt-injection surface) is recorded in the slice 9 builder report as an accepted risk, but no code mitigates it.

## Gaps and accepted risks
Stated as found, not softened.

Slice 8
- The real docker path has never run against a daemon. `tests/test_docker_engine.py::test_echo_in_container` (line 134) is skipped with "docker daemon or image not available". Argv construction, hardening flags and denial are tested with mocks only.

Slice 9
- Accepted risk, no mitigation: MCP tool names, descriptions and input schemas come from the server and reach the model, so a malicious or compromised server can inject instructions. Only the launch-command check, scrubbed env and allow/block lists exist.
- Non-error `call_tool` results are not redacted. Only error results go through redaction (the slice 9 QA report records this as "as designed").
- Residual (slice 9 QA): the direct `proc.kill()` after an oversize line or request flood is covered only by `close()` and not separately pinned by a test.

Slice 10 (QA advisories, none blocking)
1. LOW: `app.py` `_hostname` uses `urlsplit`, so a Host header with userinfo (`evil.com@localhost`) parses to `localhost` and is accepted. Browsers cannot send that header and a real attacker Host is still refused, but the parser differential exists.
2. LOW: no per-connection socket timeout. A client sending a partial body parks a handler thread until it disconnects. Memory is bounded; thread count is not. Loopback default limits exposure.
3. LOW: `_send`/`_fail` do not catch `BrokenPipeError`. A client that drops before the 401/413 reply makes socketserver print a traceback to stderr.
4. INFO: `main()` (including the `--profile` branch) has no test.
5. INFO: a `BaseException` (not `Exception`) in the run thread queues no terminal event.
6. INFO: if the ERROR event were ever dropped from the terminal set, only the 240 s test timeout would catch it.

Slice 11 (QA notes, none blocking)
- Duplicate explicit case ids are not rejected; two results can share a `case_id`.
- `cutoff_s` of NaN is accepted, so the cutoff never fires. Negative values do time out.
- Leftover `/tmp/mf_eval_*` directories from earlier QA mutant runs exist; QA did not delete them, and the real code leaks none.

Deferred and untouched
- Slice 12 (factory) is deferred (Authority List A72, YAGNI). `src/master_finhub/factory/__init__.py`, `evolver.py`, `skill_compiler.py` and `team_generator.py` are all 0 bytes (checked 2026-10-02).
- The root-level `evals/` stubs are untouched: `evals/runner.py` is 0 bytes, `evals/benchmarks/` and `evals/verifiers/` hold only `.gitkeep`, and git history for `evals/` shows only the scaffold commit 05b22c3. The real evals live in `src/master_finhub/evals/`, so the root-level stubs are now dead duplicates.

Toolchain
- Python is 3.11.15 in this toolchain, not 3.12. The docker tool text and image names in slice 8 reference python:3.12-alpine, which was not exercised.
- Black prints a 3.11-versus-3.15 target-version warning on every run.

## PR history
Source: `gh api repos/danielnguyenfinhub/finhub-harness/pulls`, read 2026-10-02.
- #5 slice 8: merged 2026-10-02T02:31Z.
- #6 slice 9: merged 2026-10-02T03:03Z.
- #7 slice 10: merged 2026-10-02T03:37Z.
- #8 slice 11: **merged** 2026-10-02T04:03Z. This contradicts the brief, which said the slice 11 PR is open; GitHub reports it merged. The local branch has not been fetched since, so local `git log` still ends at commit 967ec1b.
- Earlier: #1 to #4 (slices 1-7) merged 2026-10-01.
- Titles of #5 to #7 read "slices 8-11 ... (slice N so far)" and were not retitled to match what each merged. They are history only.

## Next step
Run `docker pull python:3.12-alpine` on a machine with a docker daemon, then run `pytest tests/test_docker_engine.py -rs` and confirm `test_echo_in_container` passes rather than skips. That is the only piece of slice 8 that has never been exercised.
