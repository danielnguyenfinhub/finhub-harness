# Slice 8 report: docker sandbox engine + process stream. Status: PASS

## Files
- src/master_finhub/sandbox/stream.py (created, was 0-byte stub)
- src/master_finhub/sandbox/docker_engine.py (created, was 0-byte stub)
- tests/test_stream.py (created)
- tests/test_docker_engine.py (created)

## Tests
test_stream.py: test_scrubbed_env_drops_secret_names, test_tail_buffer_keeps_tail, test_stream_process_orders_and_exits, test_stream_process_timeout_kills_group, test_abandoned_stream_releases_readers, test_abandoned_stream_with_escaped_child_does_not_hang (setsid grandchild holds the pipe).
test_docker_engine.py: test_docker_argv_hardening, test_docker_argv_rejects_comma_root, test_docker_argv_rejects_bad_image_and_env, test_config_timeout_bounds, test_docker_argv_unique_names, test_engine_blocks_denied_command, test_docker_available_false_without_daemon, test_tool_formats_result, test_tool_missing_image_hint, test_echo_in_container.
Skipped: test_echo_in_container (no docker daemon / image: "docker daemon or image not available"). All others run without docker.

## Claims implemented
A1-A17 and A73-A74 (A3 per-instance name; A73 fresh mf_<uuid8> + --rm each run). Judge fixes: N7 (stop -> kill group + on_timeout -> proc.wait -> shared 5 s join -> close only pipes of dead readers; reader threads daemon), N1 (DockerEngine.stream is a plain function; check_command before the generator is returned), N2 (touch /etc/x is smoke only), scrubbed_env in sandbox/stream.py.

## Gate
- pytest -q: exit 0 (540 passed, 9 skipped)
- ruff check src tests: exit 0 (All checks passed)
- black --check src tests: exit 0 (56 files unchanged)
- mypy --strict src: exit 0 (no issues, 36 files)

## AMBER actions
None. No dependency added.

## Deviations from design
- SandboxConfig default is `config: SandboxConfig | None = None` in DockerEngine (built inside) rather than a shared default instance: avoids a mutable-looking default; same behaviour.
- Tool output on exit_code None prints `exit=timeout`; image-missing hint appended when exit==125 or stderr says "Unable to find image".
- SandboxExecTool reads engine._config for the timeout/image text (same module).
- Timeout also calls on_timeout exactly once; abandoned stream calls it once (guarded by flag).
- Not exercised against a real daemon (none available).

## Retry (boundary-qa FAIL, test strength only; no src change)
- tests/test_stream.py: abandoned-stream test now writes 600 x 64 KiB (> QUEUE_MAX 256) so the queue truly fills, comment corrected, and asserts both pipes closed via a Popen spy. Escaped-grandchild test: grandchild sleeps 60 s, asserts close() < 10 s, kills the grandchild in a finally.
- Mutations on a scratchpad copy (repo untouched): M2 drop stop.set() KILLED (releases_readers fails); M3 drop reader join loop KILLED (pipe-closed assertion fails); M4 close pipes before join KILLED (escaped_child test fails after ~61 s on the mutant).
- Gates after retry: pytest -q 0 (540 passed, 9 skipped), ruff 0, black --check 0, mypy --strict 0.
- Flakiness: the two abandoned tests run 10x, 0/10 failures.
