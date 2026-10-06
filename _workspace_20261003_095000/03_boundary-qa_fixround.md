RESULT: PASS

# Boundary QA - fix round (slice 10 and 11 advisories) - 2026-10-02

Independent re-verification; builder report not trusted. Read-only on code; mutations only in scratchpad copies (one fresh dir per mutant, nothing deleted).

## Scope
- `git status --short`: exactly M runner.py, M app.py, M tests/test_evals.py, M tests/test_server.py, M tests/test_sse.py. `git diff HEAD -- pyproject.toml references` empty; submodule SHAs unchanged (no +/- prefix); `dependencies` untouched; no `shell=True`; src diff is only app.py (+40/-12) and runner.py (+21/-4). Compliance sweep of the diff: only synthetic Host attack strings (`localhost@evil.com`), no real data.
- Tests: `git diff HEAD` shows no deleted assertion. Only two existing tests edited: test_sse.py::test_error_is_terminal (same assertion, `idle_timeout_s=0.3` added so a mutant fails in 0.3 s not 300 s; justified, not loosened) and test_server.py::test_agent_error_event_has_class_name_only (same assertions, `idle_timeout_s=1.0, **FAST` added; same justification). 12 new server tests, 24/24 named earlier tests spot-checked present.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| Host header <-> `_hostname`/`_allowed` | app.py:157-170 strict `host[:port]` / `[v6][:port]`; `headers.get_all("Host")`, exactly one value else None | test_server.py raw-socket parametrized 421 cases + keep-loopback cases + duplicate/missing | yes |
| make_server `read_timeout_s` <-> RunServer <-> `_Handler.setup` | keyword-only, default READ_TIMEOUT_S 30.0 | tests inject 0.2 s; real default probed (below) | yes |
| `_Handler.handle` catch <-> socketserver | only `(BrokenPipeError, ConnectionResetError)`; `finish()`/`shutdown_request` still close socket | test_client_drop_before_reply_is_quiet asserts handle_error never called | yes |
| worker `_work` <-> SSE client | any BaseException -> `ERROR` data = `json.dumps(type(exc).__name__)`; finally decrements `_running`, `finished=True` | stream `finally: release(run_id)`; tests assert no secret, `_running` back to 0 | yes |
| benchmark JSON `cutoff_s` <-> loader | finite non-bool number >= 0 | tests nan/inf/-inf/-1/True/"5"/None rejected, 0 allowed; `main` exit 2 | yes |
| `run_suite` ids <-> report/CLI | duplicate (explicit or sha256-derived) -> ValueError naming id before any run | main prints it, exit 2 | yes |

## Gate (`.venv/bin/python -m ...`)
| command | exit | output |
|---|---|---|
| pytest -q | 0 | `676 passed, 9 skipped in 61.09s` |
| ruff check src tests | 0 | `All checks passed!` |
| black --check src tests | 0 | `65 files would be left unchanged.` (py3.15 target-version warning only) |
| mypy --strict src | 0 | `Success: no issues found in 40 source files` |
| proof `evals.runner src/master_finhub/evals/benchmarks/echo_pass.json` | 0 | `pass_rate: 1.0` (the design puts echo_pass under src/.../benchmarks, not tests/fixtures; the tests/fixtures path does not exist, by design) |
| proof `evals.runner tests/fixtures/evals/echo_fail.json` | 1 | `pass_rate: 0.0`, `error: null` (clean grading failure) |

## (2) Regression
Slice 10: PING first, 127.0.0.1 default, non-loopback refusal, Host check, `hmac.compare_digest`, guard order (`_both`), idle timeout and reset, disconnect cleanup, 413 bound all still present in code and exercised by the full 676-test run. Slice 11: ground never reaches agent, timed-out never passes, no exception escapes run_case, non-string/unknown eval.type rejected, empty phrases rejected, traversal rejected, tools_factory gets workspace: all unchanged in code; re-killed by mutation (below).

## (3) Strict Host probe (raw sockets, valid key, real server)
- Accepted (reached 404 route): `localhost`, `LOCALHOST`, `localhost:PORT`, `127.0.0.1`, `127.0.0.1:PORT`, `[::1]`, `[::1]:PORT`.
- Refused 421 (all 30): `evil.com@localhost`, `evil.com\@localhost`, `localhost@evil.com`, `localhost.`, `127.1`, `0.0.0.0`, `[::ffff:127.0.0.1]`, `localhost.evil.com`, `localhost:99999`, `localhost:abc`, `localhost:80:80`, `[::1]x`, empty, single space, `\x01`, `\x7f`, tab, embedded space, non-ASCII byte, `localhost:`, `:80`, `[]`, `[::1`, bare `::1`, `localhost:+80`, `localhost:-1`, `localhost:65536`, duplicate Host in both orders (`localhost`+`evil.com`, `evil.com`+`localhost`) and identical duplicate, plus missing Host (HTTP/1.0).
- `/health`: 200 with good Host, evil Host and no Host (unchanged: it is before `_allowed`, as before).
- Nit (not a defect): `[localhost]:80` is accepted (bracketed non-IP loopback name); `localhost:00080` accepted. Both resolve to loopback names only.

## (4) Socket read timeout, REAL defaults (read 30 s, ping 10 s, idle 300 s)
Probe: default `make_server`, LLM blocking 40 s. At t=33 s: idle pre-auth connection closed by server, half-sent-body connection closed by server, handler threads released. The SSE stream, quiet for 40 s of real events, delivered 4 pings, then `message`/`done` with "slow-done" (t=40.0 s). Reason: the stream handler only writes after the GET is parsed; no read happens, so the read timeout cannot fire; writes use the same timeout but only matter if a client stops draining for 30 s (raises OSError, caught by the stream's `except OSError`; the stream finally still releases). `/health` 200 afterwards; thread delta 0 after the run. Injected-value test test_read_timeout_does_not_cut_an_idle_sse_stream agrees.
- Advisory A1 (low): a stalled write on the non-stream path (`_send`) raises TimeoutError, which is not in the `handle` catch and goes to `handle_error` (stderr traceback, no secrets). Previously it would hang forever, so this is an improvement, not a regression.

## (5) BrokenPipe/ConnectionReset catch (app.py `_Handler.handle`)
Catch is narrow (two exception types, around `super().handle()` only). Handler runs no agent code (agent runs in its own thread), so nothing unrelated can be hidden. Nothing logged (`log_message` suppressed; the `pass` logs nothing). Socket closed by socketserver `finish`/`shutdown_request`. The stream path keeps its own `except OSError` and `finally: release`.

## (6) Run-thread BaseException
Terminal ERROR event carries class name only (no message, no traceback); not re-raised, so threading's excepthook cannot print exception text to stderr. KeyboardInterrupt cannot arrive in a non-main thread by signal; SystemExit in a worker would only end the thread silently by default, so converting it to an ERROR event is acceptable. `finally` decrements `_running` and sets `finished`; the stream's `finally: release` pops the run entry. Verified by test_run_thread_always_queues_a_terminal_event_on_baseexception.
- Residual (pre-existing, unchanged): a run with no subscriber ever attached stays in `runs` until MAX_RETAINED eviction.

## (7) cutoff_s and duplicate ids (direct probe)
Rejected with ValueError naming cutoff_s: nan, inf, -inf, -1, -0.5, True, "5", None. Accepted: 0, 0.0, 30. Duplicate explicit ids and two files with identical content (same sha256-derived id) both rejected; `main` exit 2 with the id in the message; two distinct ids exit 0. Running the same benchmark file twice (exit 2) is not a legitimate use: grep of tests/, src/, docs and the design finds no invocation with a repeated path (`run_suite([PASS, FAIL])` is the only multi-file use).

## (8) Mutation test (scratchpad copy, files: test_server.py, test_sse.py, test_evals.py)
| mutant | result | killed by |
|---|---|---|
| `_hostname` lenient urlsplit | KILLED | test_strict_host_parse_refuses_421[evil.com@localhost] |
| socket timeout removed | KILLED | test_slow_body_handler_is_released_by_read_timeout |
| BrokenPipe/Reset catch dropped | KILLED | test_client_drop_before_reply_is_quiet |
| run thread `except Exception` | KILLED | test_run_thread_always_queues_a_terminal_event_on_baseexception |
| run thread terminal event removed | KILLED | test_agent_error_event_has_class_name_only |
| ERROR not in TERMINAL | KILLED | test_agent_error_event_has_class_name_only (test_dropping_error_from_terminal_set_is_caught_fast is the sse-level guard) |
| duplicate ids accepted | KILLED | test_duplicate_explicit_ids_rejected |
| NaN cutoff accepted | KILLED | test_cutoff_s_must_be_finite_non_negative_number[nan] |
| negative cutoff accepted | KILLED | ...[-1] |
| duplicate Host header accepted | KILLED | test_duplicate_or_missing_or_empty_host_421 |
| port > 65535 unchecked (extra) | KILLED | test_strict_host_parse_refuses_421[localhost:99999] |
| drop PING-first (regression) | KILLED | test_run_streams_ping_then_events |
| drop API-key check (regression) | KILLED | test_missing_or_wrong_key_401 |
| drop `grading.total > 0` (regression) | KILLED | test_empty_ground_cannot_pass |
| bracket-suffix check `rest.startswith(":")` removed (extra) | SURVIVED | not equivalent: `[::1]x80` would parse as host ::1 port 80 and be accepted by the mutant; real code refuses (probed: None). Test gap only; add `b"[::1]x80"` to the refuse list (test_server.py:431). Not exploitable (result is still a loopback name). |

## Flakiness
58 timing/main/host/duplicate/cutoff tests x10: 10/10 passed (about 20 s each). `pgrep` for pytest/master_finhub afterwards: nothing. Real-default probe thread delta 0.

## Defects
None blocking. Advisories: A1 above; survivor `[::1]x80` test gap; unchanged `runs` retention for never-attached runs.
