# Slice 10 report - HTTP server + SSE (status: PASS)

## Files
- src/master_finhub/server/sse.py (created, was 0-byte)
- src/master_finhub/server/app.py (created, was 0-byte)
- tests/test_sse.py (created)
- tests/test_server.py (created)

## Claims implemented
A40-A44 (ping-first, idle/ping timers, terminal set, defaults, event-stream + no-cache), A45/A46 (loopback default, LAN refused, loopback socket test), A47 (session header, hmac.compare_digest), A48 (routes, run lifecycle, retention, daemon threads), A49 (hook emits snapshot.messages[-1]; guard_tool_call first via imported _both; ERROR = class name only), A50 (Host check).

## Tests
test_sse.py: test_encode_frame, test_ping_first_then_event_then_stop, test_error_is_terminal, test_idle_pings_then_timeout, test_real_event_resets_idle_timer.
test_server.py: test_health_needs_no_key, test_run_streams_ping_then_events (also frame shape vs reference client parser), test_missing_or_wrong_key_401, test_key_compare_is_constant_time, test_bad_host_header_421, test_loopback_host_names_accepted, test_unknown_run_404_and_unknown_route_404, test_bad_bodies_400_and_413, test_second_subscriber_409, test_refuses_lan_bind, test_allow_remote_permits_non_loopback_host, test_default_bind_is_loopback, test_loopback_only, test_extra_guard_cannot_weaken, test_extra_guard_can_add_denial, test_agent_error_event_has_class_name_only, test_compaction_does_not_drop_or_repeat_events, test_too_many_running_429, test_disconnect_releases_thread_and_subscriber, test_idle_stream_times_out_and_releases, test_shutdown_does_not_hang_with_open_stream.

Self mutation check (each made the named test fail, source restored after): drop PING-first, default host 0.0.0.0, drop Host check, drop key check, extra_guard replaces default guard, drop disconnect cleanup (release), drop idle timeout, drop idle-timer reset.

## Gate
- pytest -q: exit 0 (588 passed, 9 skipped)
- ruff check src tests: exit 0 (All checks passed!)
- black --check src tests: exit 0 (61 files would be left unchanged)
- mypy --strict src: exit 0 (no issues found in 37 source files)

## AMBER actions
None. No dependency added, pyproject.toml untouched.

## Deviations from design
1. make_server gained keyword-only `context_factory` (default ContextManager) and `idle_timeout_s`/`ping_interval_s`/`poll_s` pass-throughs: test seams so compaction and idle/disconnect tests are deterministic and fast. Defaults match the design.
2. Stream removal on disconnect: the run entry is dropped from `server.runs` in the stream handler's `finally` (any end: terminal event, idle timeout, disconnect, shutdown). The run thread keeps going and finishes harmlessly; its queue is garbage collected. RunServer.shutdown sets a `closing` event so open streams end at their next frame (daemon_threads=True too).
3. 413 path drains at most 2*MAX_BODY_BYTES of the declared body before replying, so the client reliably receives the 413 instead of a connection reset. Body is never echoed.
4. Host check runs before the key check; /health is exempt from both (per route table).
5. Initial user prompt is emitted as the first MESSAGE event (the loop's first checkpoint save), consistent with "one event per hook call".
6. Run entries for finished-but-never-streamed runs are evicted oldest-first only when over MAX_RETAINED.
