RESULT: PASS

# Boundary QA - slice 10 (HTTP server + SSE) - 2026-10-02

## Scope
`git status --short`: ` M src/master_finhub/server/app.py`, ` M src/master_finhub/server/sse.py` (tracked 0-byte stubs), `?? tests/test_server.py`, `?? tests/test_sse.py`. Nothing else. `git diff -- pyproject.toml references` empty; submodule SHAs unchanged; `dependencies = []` still. No leftover mutation: app.py/sse.py read in full against the design, every required item present (PING first sse.py:48; default host 127.0.0.1 and non-loopback ValueError app.py make_server; Host check + hmac.compare_digest in `_allowed`; `_both(guard_tool_call, extra)` imported from subagent.py:111; idle timeout + reset; `release` in stream `finally`; 413 branch with bounded drain).

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| SSE frame <-> test client parser | sse.py `encode`: `id: N\nevent: X\ndata: Y\n\n`, one `data:` per line | tests/test_sse.py `parse_frame` and test_server.py `parse_stream` partition on ": ", blank-line terminator | yes (exact bytes asserted in test_encode_frame) |
| hook payload <-> design / snapshot.messages[-1] | app.py `_work.hook`: `{"role","content","tool_calls":[names]}` from `snapshot.messages[-1]`; loop.py `_save` once per append (:165,170,178,185,196) | design A49; test asserts first event == `{"role":"user","content":"echo hi","tool_calls":[]}`, roles `[user,assistant,tool,assistant]` under a shrinking ContextManager | yes (tool_calls names themselves not asserted, see M12) |
| terminal events <-> client | `DONE` data `json.dumps(final_text)`, `ERROR` data `json.dumps(class name)` | tests assert `("done",'"hi"')`, `("error",'"RuntimeError"')`, no "secret" in raw | yes |
| request body <-> handler | `{"prompt": non-empty str}`; handler catches ValueError/KeyError/TypeError, rejects non-str/empty | tests: not-json 400, prompt=3 400 | yes |
| status codes <-> design table | 202/400/401/404/409/413/421/429 as in design; /health 200 no auth | each asserted in test_server.py | yes |
| guard composition <-> loop | `AgentLoop(guard=_both(guard_tool_call, extra))` | `ToolGuard` = `(ToolCall)->str|None`; test_extra_guard_cannot_weaken (tool never runs) | yes |
| make_server interface <-> design | signature as design plus keyword-only `context_factory`, `idle_timeout_s`, `ping_interval_s`, `poll_s` (declared deviation 1, defaults match) | tests use them | yes (additive) |

## Gate (re-run by QA, `.venv/bin/python -m ...`)
| command | exit | output |
|---|---|---|
| pytest -q | 0 | 588 passed, 9 skipped in 41.32s |
| ruff check src tests | 0 | All checks passed! |
| black --check src tests | 0 | 61 files would be left unchanged (py3.15 target-version warning only) |
| mypy --strict src | 0 | Success: no issues found in 37 source files |
| proof: tests/test_sse.py tests/test_server.py | 0 | included in full run |

## Safety / compliance
- Sweep (email, AU mobile, key patterns, UUIDs) over server/, test_server.py, test_sse.py: no hits. No `shell=True`, no `dify` / `autogpt_platform` strings, no new dependency.
- Key never echoed (probe: key not in 401/421 bodies). Non-ASCII key header -> 401. `log_message` suppressed. Key printed once to stderr by `main()` as the design specifies.
- Path traversal: `GET /runs/../../etc/passwd/events` -> 404 (run id is a dict lookup only).
- Header limits: 70 KB header -> 431, 70 KB request line -> 414, negative Content-Length -> 400, duplicate Host with first evil -> 421. Body read bounded to 64 KB; 413 drain bounded to 128 KB.
- Host probes (all via raw socket, valid key): accepted `localhost`, `LOCALHOST`, `LocalHost:80`, `127.0.0.1`, `[::1]`, `[::1]:80`, `localhost:abc`. Refused 421: `localhost.`, `localhost.:80`, `127.0.0.1.`, `[::ffff:127.0.0.1]`, `127.1`, `0.0.0.0`, `localhost@evil.com`, `evil.com#@localhost`, `localhost:80@evil.com`, `localhost.evil.com`, `evil.com/localhost`, `localhost,evil.com`, empty, missing.

## Concurrency
- Disconnect / idle / shutdown / compaction tests run 10x: 10/10 `6 passed` (about 2.07 s each). `pgrep` after: no stray pytest/master_finhub processes.
- Shutdown probe with an open stream (ping interval 5 s): `shutdown()+server_close()` 0.50 s, stream closed immediately.
- Handler thread released on client close (test_disconnect...), run entry popped, daemon_threads=True.

## Mutation test (scratchpad copy only: .../scratchpad/mut10/w; repo untouched, git status re-checked after)
Required set - all killed by a named test:
| mutation | killed by |
|---|---|
| drop PING-first | test_ping_first_then_event_then_stop, test_run_streams_ping_then_events (+3) |
| default host 0.0.0.0 (alone / with allow_remote default True) | test_default_bind_is_loopback, test_loopback_only (+ ValueError breaks every server test) / test_refuses_lan_bind |
| drop Host check | test_bad_host_header_421 |
| drop API-key check | test_missing_or_wrong_key_401, test_key_compare_is_constant_time |
| compare_digest -> == | test_key_compare_is_constant_time |
| extra guard replaces default | test_extra_guard_cannot_weaken |
| drop disconnect cleanup | test_disconnect_releases_thread_and_subscriber |
| drop idle timeout | test_idle_stream_times_out_and_releases, test_idle_pings_then_timeout |
| drop idle-timer reset | test_real_event_resets_idle_timer |
| history length-diff instead of messages[-1] | test_compaction_does_not_drop_or_repeat_events |
| drop 413 body bound | test_bad_bodies_400_and_413 |

Extra mutations: killed - drop 429 (test_too_many_running_429), drop 409, drop Cache-Control, error event leaks str(exc), hook emits messages[0], LOOPBACK includes 0.0.0.0 (test_refuses_lan_bind), release does not pop run, closing check + daemon threads removed together (test_shutdown_does_not_hang_with_open_stream).

SURVIVORS (all outside the required list; none a stated-contract break):
1. `"tool_calls": []` always - assistant tool-call names never asserted (add an assertion on the 2nd message event).
2. `_both(extra, guard_tool_call)` order swapped - not observable by the current tests (extra returning None); a test with extra denying a command guard_tool_call also denies would pin the order.
3. Drop `closing` check alone, or `daemon_threads=False` alone - each masked by the other (test only fails when both are removed). Redundant defences, not a gap.
4. Unbounded 413 drain (`rfile.read(length)`) - bounded drain untested.
5. Ping timer not reset by a real event - untested (only idle-timer reset is).
6. Drop MAX_RETAINED eviction - untested.
7. Terminal set without ERROR - no failing assertion: test hangs until the 300 s idle timeout (detected only as a 240 s timeout, no named test).

## Defects
None blocking. Advisories (for Daniel / next builder pass, none fail a design claim):
1. LOW app.py `_hostname` (urlsplit): a Host with userinfo, e.g. `evil.com@localhost` or `evil.com\@localhost`, parses to hostname `localhost` and is accepted. Browsers cannot send such a Host header, so DNS rebinding (Host = attacker domain) is still refused; a strict `host[:port]` parse would close the parser differential.
2. LOW No per-connection socket timeout (`_Handler.timeout` unset): a client that sends `Content-Length: 100` and 3 bytes, or `Content-Length: 99999999999` and 1 KB, parks its handler thread until it closes. Pre-auth idle connections likewise. Memory per connection is bounded; thread count is not. Loopback default limits exposure.
3. LOW `_send`/`_fail` do not catch BrokenPipeError; a client that drops before the 401/413 reply makes socketserver print a traceback to stderr (client address only, no key or prompt).
4. INFO `main()` (CLI, `--profile` branch) has no test; claims A47 printout is UNVERIFIED by tests.
5. INFO Hook queue is unbounded per run (as designed, bounded by max_steps); a BaseException (not Exception) in a run thread queues no terminal event.
