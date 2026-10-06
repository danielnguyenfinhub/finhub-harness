# Slice 9 — MCP client (stdio): builder report

Status: PASS (all four gate commands exit 0). Not committed, not pushed.

## Files
| path | state |
|---|---|
| src/master_finhub/tools/mcp/client.py | created |
| tests/mcp_stub_server.py | created (stub server, 9 modes after retry: normal, --paged, --die-on-call, --never-answer, --version, --huge-line, --endless-pages, --ask-client N, --ignore-eof [--ignore-term]) |
| tests/test_mcp_client.py | created (22 tests after the QA retry) |

No other file touched (slices 1-8, pyproject.toml, references/ unchanged). Black was run over src and tests; it reported 59 files unchanged at the end.

## Claims implemented
A18-A37 (spawn, reader/stderr threads, id->queue routing, write lock, deadline, fail-all-waiters, handshake, version check, pagination, public names, isError, content join, filter, redaction, close sequence, not-initialized guard), A38 (check_command on launch), A39 (stub, eight modes), A75 (bounded readline), A76 (page cap), A77 (-32601 reply) plus N8/N9.

## Tests (named, with the behaviour each one pins)
- test_handshake_and_list (initialize -> notifications/initialized -> tools/list order, via stub log)
- test_call_echo_round_trip
- test_is_error_maps_to_tool_error_and_redacts_env_secret (A31, A30, A35)
- test_pagination
- test_server_death_fails_waiter (A22, under 5 s)
- test_timeout (A21)
- test_unsupported_version_rejected
- test_oversize_line_closes_session (A75; monkeypatches MAX_LINE_CHARS=1000; second call also McpClosed)
- test_endless_pages_capped (A76; stub log shows exactly 20 tools/list)
- test_server_request_gets_method_not_found (A77; stub log has -32601 reply with same id "s0", call still returns "hi")
- test_server_request_flood_closes_session (N9 cap; 104 requests -> McpClosed, under 5 s including close())
- test_public_name_rules, test_filter_block_wins, test_redact_env_value_and_bearer
- test_denied_launch_command_never_spawns (rm -rf / denied, `_proc is None`; the stub launch itself is allowed by every other test)
- test_missing_binary_is_mcp_error
- test_not_initialized_and_close_idempotent_kills_child
- test_close_kills_child_that_ignores_stdin_eof
- test_loop_calls_mcp_tool (AgentLoop with guard_tool_call and mcp__stub__echo)

Mutation spot-checks I ran myself (each made the named test fail, then restored): removed server-request cap, page cap 20 -> 3, -32601 -> -1, removed oversize check, `readline(MAX_LINE_CHARS + 1)` -> `readline()` (test_oversize_line_closes_session fails by timeout).

## Gate
Run from /home/user/finhub-harness with .venv.
- `pytest -q` exit 0: `559 passed, 9 skipped in 23.48s`
- `ruff check src tests` exit 0: `All checks passed!`
- `black --check src tests` exit 0: `All done! 59 files would be left unchanged.` (the "Python 3.11 cannot parse code formatted for Python 3.15" line is a pre-existing Black warning about target-version inference; no config was changed)
- `mypy --strict src` exit 0: `Success: no issues found in 37 source files`

## AMBER actions
None. No dependency added (stdlib only), no shell=True.

## Accepted risks (N6)
MCP tool names, descriptions and input schemas come from the server and are passed to the model via `ToolSpec`. A malicious or compromised server can therefore inject instructions through them (prompt-injection surface). No code mitigation in this slice, per the design. Mitigations that do exist: launch-command check, scrubbed env, per-tool allow/block list, loop guard on every call. Also: `call_tool` text results are not redacted unless `isError` is true.

## Deviations from design
1. `MAX_LINE_BYTES` renamed `MAX_LINE_CHARS` (judge N8: the text-mode limit counts characters). The test monkeypatches `MAX_LINE_CHARS`.
2. Added `MAX_SERVER_REQUESTS = 64` (judge N9). Past the cap the session closes with `McpClosed("too many server requests")` and the child is killed.
3. After an oversize line the reader kills the child directly (in addition to failing waiters), because the server may be blocked writing the rest of the line.
4. `close()` closes stdin in a short-lived daemon thread and joins it with a 2 s limit, then waits 2 s, terminates, waits 5 s, kills. Reason: a plain `stdin.close()` can block on a full pipe (N9); the design only said "close stdin".
5. `CLIENT_VERSION = "0.1.0"` is a constant matching pyproject.toml rather than a runtime lookup (the package defines no `__version__`).
6. `StdioServer.__post_init__` raises ValueError for a name outside `[a-z0-9_-]{1,32}` (design only commented the pattern).
7. Stub mode `--ask-client` takes a count (`--ask-client N`) so the same mode drives both the -32601 test (N=1) and the flood-cap test, keeping the stub at eight modes. The stub's `fail` tool echoes `MCP_STUB_SECRET` so the redaction test goes through a real round trip.
8. Stderr lines are read with `readline(4096)` so a newline-less stderr flood is bounded too (not in the design).
9. `mcp_tools` reads the server config via `client._server` (module-internal access).

## Retry (boundary-qa FAIL on close() mutants M7a/M7b)
Fix is tests and stub only; no src change.
- Stub: ninth mode `--ignore-eof` (stays alive after stdin EOF), with optional `--ignore-term` (also ignores SIGTERM). A39 mapping kept: the new mode is proved by the three close tests below. The stub's initialize result now also reports `serverInfo.envKeys` (sorted child environment keys).
- New tests replacing test_close_kills_child_that_ignores_stdin_eof:
  - test_close_terminates_child_that_ignores_stdin_eof (terminate branch; returncode == -SIGTERM, close() under 10 s)
  - test_close_kills_child_that_ignores_eof_and_sigterm (kill branch; returncode == -SIGKILL, under 12 s, `os.kill(pid, 0)` raises ProcessLookupError)
  - test_close_final_kill_runs_even_if_wait_raises (the `finally` kill; `proc.wait` patched to raise)
  - test_child_env_is_scrubbed (parent FAKE_API_KEY absent from the child env; plain var and explicit MCP_STUB_SECRET present)
- test_oversize_line_closes_session now patches MAX_LINE_CHARS to 100_000 (the initialize reply now carries the env keys and exceeded 1000 characters); the 5 MB line is still far over it.
- Deviation: ninth stub mode (the A39 list grows from eight to nine).

### Mutation results (scratchpad copies only; repo untouched)
| mutant | result | failing tests |
|---|---|---|
| M7a every terminate()/kill() in close() -> pass | KILLED | test_close_terminates_..., test_close_kills_..., test_close_final_kill_..., test_oversize_line_closes_session |
| M7b drop only the `finally` kill | KILLED | test_close_final_kill_runs_even_if_wait_raises |
| M7c drop only terminate() (kill kept) | KILLED | test_close_terminates_child_that_ignores_stdin_eof |
| M9 scrubbed_env(...) -> os.environ | KILLED | test_child_env_is_scrubbed (plus 4 others) |

### Gate after retry (.venv/bin/python)
- pytest -q: exit 0, 562 passed, 9 skipped
- ruff check src tests: exit 0
- black --check src tests: exit 0, 59 files unchanged
- mypy --strict src: exit 0, 37 files
- close and env tests run 10x under `timeout 120`: 10 of 10 runs `7 passed` (about 9.3 s each).
- ps: no stray `mcp_stub_server` from the repo tree. Eight orphans from the deliberately kill-less mutant copies were found and killed; ps then showed 0.
