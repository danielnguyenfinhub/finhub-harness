RESULT: PASS

# Boundary QA — slice 9 (MCP stdio client), re-check after retry

Previous FAIL (M7a/M7b survived, env scrubbing unasserted) is resolved. Builder retry was tests + stub only; client.py is unchanged.

## Scope
- `git status --short`: only `?? src/master_finhub/tools/mcp/client.py`, `?? tests/mcp_stub_server.py`, `?? tests/test_mcp_client.py`. `git diff --stat` empty (pyproject, references/, slices 1-8 untouched).
- client.py still has: `MAX_TOOL_PAGES = 20` (:38), `"code": -32601` (:222), `MAX_SERVER_REQUESTS = 64` (:40, check :218), `proc.stdout.readline(MAX_LINE_CHARS + 1)` (:193) with the oversize check (:198), `check_command(shlex.join(...))` before spawn (:149), `scrubbed_env` imported from `master_finhub.sandbox.stream` (:30, used :161). close() sequence intact (:366-397).

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| McpTool <-> loop Tool protocol | loop.py `Tool: spec, run(arguments) -> str` | client.py:411-425 | yes (unchanged) |
| close() branches <-> tests | client.py:377 terminate, :381 kill, :386-387 finally kill | test_close_terminates_child_that_ignores_stdin_eof, test_close_kills_child_that_ignores_eof_and_sigterm, test_close_final_kill_runs_even_if_wait_raises | yes (each mutant killed, below) |
| child env <-> test | client.py:161 `env=scrubbed_env(self._server.env)` | stub initialize `serverInfo.envKeys`; test_child_env_is_scrubbed | yes |
| stub modes <-> tests (A39, nine modes) | stub: normal, --paged, --die-on-call, --never-answer, --version, --huge-line, --endless-pages, --ask-client N, --ignore-eof [--ignore-term] | test_mcp_client.py uses all nine (lines 86, 92, 98, 103, 110, 121, 130/140, 196/213/225; normal everywhere else) | yes |
| test name <-> behaviour | old misnamed test removed | new tests really reach terminate and kill (below) | yes |
| other boundaries (public name rule, isError text, ToolSpec, launch safety, redaction) | unchanged from first pass | | yes |

## Gate (.venv/bin/python)
| command | exit | output |
|---|---|---|
| pytest -q | 0 | `562 passed, 9 skipped in 32.46s` |
| ruff check src tests | 0 | `All checks passed!` |
| black --check src tests | 0 | `59 files would be left unchanged.` (pre-existing py3.11/3.15 target warning) |
| mypy --strict src | 0 | `Success: no issues found in 37 source files` |

## Stub --ignore-eof / --ignore-term (verified directly with Popen)
- `--ignore-eof`: alive 1.5 s after stdin EOF = True; after terminate() dead, rc -15 (terminate branch reachable and sufficient).
- `--ignore-eof --ignore-term`: alive after EOF = True; still alive after SIGTERM = True; only kill() ends it, rc -9 (kill branch forced).
- Normal mode exits on EOF (so the other tests are unaffected).

## Mutation tests (scratchpad copy m9qa; PYTHONPATH confirmed to import the copy; repo client.py `cmp`-identical to original afterwards)
| mutant | result | failing test(s) |
|---|---|---|
| M7a every terminate()/kill() in close() -> pass | KILLED | test_close_terminates_child_that_ignores_stdin_eof, test_close_kills_child_that_ignores_eof_and_sigterm, test_close_final_kill_runs_even_if_wait_raises, test_oversize_line_closes_session |
| M7b drop only the `finally` kill | KILLED | test_close_final_kill_runs_even_if_wait_raises |
| M7c drop only terminate() (kill kept) | KILLED | test_close_terminates_child_that_ignores_stdin_eof |
| M9 scrubbed_env -> os.environ | KILLED | test_child_env_is_scrubbed |
| M1 remove server-request cap | KILLED | test_server_request_flood_closes_session |
| M5 `proc.stdout.readline(MAX+1)` -> `readline()` | KILLED | test_oversize_line_closes_session (TimeoutError) |
| M6 drop fail-all-waiters on EOF | KILLED | test_server_death_fails_waiter (TimeoutError) |

Harness note (QA side, not a defect): my first M5 attempt hit the comment on line 39 and was a no-op (22 passed); redone against the real call at :193 it is killed. Orphaned stub processes from the kill-less mutants were killed; ps shows none.

## Flakiness
`timeout 120 pytest -q tests/test_mcp_client.py` x10: every run `22 passed in ~10.2 s`, exit 0. `ps` afterwards: no stub_server or pytest processes.

## Defects
None blocking. Residual non-blocking (carried over, not required by the design): B1/B2 (direct `proc.kill()` after oversize line / request flood) are rescued by close() and not independently pinned; non-error `call_tool` text is not redacted (as designed, noted in builder report); N6 prompt-injection surface accepted risk.
