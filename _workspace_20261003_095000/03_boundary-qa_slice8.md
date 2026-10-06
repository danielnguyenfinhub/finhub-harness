RESULT: PASS

# Boundary QA — slice 8 (docker sandbox engine + process stream), re-run after test-strength retry

Previous FAIL (defects 1-3: M2/M3/M4 survived) re-checked: all three mutants are now killed. No src change since the last run; only tests/test_stream.py differs.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| SandboxExecTool schema <-> loop Tool/ToolSpec | docker_engine.py:144-156 `ToolSpec(name="sandbox_exec", parameters={"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}, idempotent=False)`; `run(arguments: dict[str, Any]) -> str` | runtime/loop.py:37-41 `ToolSpec(name, description, parameters, idempotent)`; :126-131 `Tool` Protocol `spec` + `run(dict)->str` | yes (mypy --strict clean) |
| tool arg key <-> loop guard | docker_engine.py:162 reads `arguments["command"]` | tools/safety.py:30 `COMMAND_ARG_KEYS` contains `command` | yes |
| SandboxExecTool.run <-> tests | docker_engine.py:167 `exit=<code>\nSTDOUT:\n..\nSTDERR:\n..` + truncated/timed-out/image hints | test_docker_engine.py:121 asserts `startswith("exit=3\nSTDOUT:\nhi\n")`; :131 asserts `docker pull <image>` | yes (timeout/truncated suffixes untested, not required) |
| DockerEngine.stream <-> check_command | docker_engine.py:123-125 `check_command` then raise `CommandBlocked`; `stream` is a plain function (no `yield`), returns `stream_process(...)` at :132 | tests:93-102 monkeypatches `subprocess.Popen` to raise, asserts `CommandBlocked` from `.stream()` and `.run()` without iteration | yes. Mutation M5 (denial=None) -> test fails |
| docker_argv <-> design order | docker_engine.py:94-107 | slice 8 argv block (02 file) | yes: same flags/order, `--user` POSIX only, `-e` sorted, `sh -c <command>` last |
| argv <-> hardening test | docker_engine.py:96 `--read-only`, `--network none`, `--cap-drop ALL`, `--rm`, `--pull never` | test_docker_engine.py:30-47 | yes. Mutation M1 (drop --read-only) -> test fails |
| stream_process <-> design Interfaces | stream.py:118-124 `(argv, *, env, timeout_s, on_timeout)`; `Chunk(seq, kind, data)`; `ExecResult` | 02 file Interfaces | yes |
| stream_process <-> DockerEngine call | docker_engine.py:132-137 keyword `env`, `timeout_s`, `on_timeout` | stream.py:118-124 | yes |
| shell usage | stream.py:131-138 `Popen(list(argv), ... start_new_session=True)` no shell | grep `shell=True`/`os.system` in `src/` and `tests/`: no hits | yes (A16) |
| dependencies | pyproject.toml `dependencies = []`, extras unchanged | slice 8 "Dependencies: None" | yes (no baseline copy to diff; content has no docker/new package) |
| skips | `test_echo_in_container` only | `pytest -rs` on the two slice files: `SKIPPED [1] tests/test_docker_engine.py:134: docker daemon or image not available` | yes. Whole-suite 9 skips: 1 slice 8 + 8 from checkpoint/workspace (win32/junction), none new |

## Gate
| command | exit | output |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 0 | `540 passed, 9 skipped in 22.47s` |
| `.venv/bin/python -m ruff check src tests` | 0 | `All checks passed!` |
| `.venv/bin/python -m black --check src tests` | 0 | `56 files would be left unchanged.` (py3.11 vs 3.15 parse warning only) |
| `.venv/bin/python -m mypy --strict src` | 0 | `Success: no issues found in 36 source files` |
| proof: `pytest tests/test_stream.py tests/test_docker_engine.py -q` | 0 | `15 passed, 1 skipped` |

## Scope
`git status`: M docker_engine.py, M stream.py, ?? tests/test_docker_engine.py, ?? tests/test_stream.py. Nothing else; pyproject.toml unchanged (`git diff --quiet` clean). Compliance grep (emails, AU mobiles, sk- keys, shell=True, os.system) over the 4 files: no hits.

## Mutation re-check (scratchpad copy `mq2`, PYTHONPATH confirmed to load the copy; repo never edited)
| # | mutation | result |
|---|---|---|
| baseline | unmutated copy | 15 passed, 1 skipped |
| M2 | drop `stop.set()` in finally | KILLED: `test_abandoned_stream_releases_readers` (tests/test_stream.py:133 AssertionError), 17.6 s |
| M3 | drop reader join loop | KILLED: `test_abandoned_stream_releases_readers` (pipe-closed assert, test_stream.py:136; stdout still open) |
| M4 | close both pipes right after `_kill_group`, before join | KILLED: `test_abandoned_stream_with_escaped_child_does_not_hang` (elapsed < 10 assert, test_stream.py:157), 62 s on the mutant |
| M1 (regression) | drop `--read-only` | KILLED: `test_docker_argv_hardening` |

## Flakiness and leftovers
- `-k abandoned` x10: 0 failures. `-k timeout` x10: 0 failures (timeout 120 s each, no hangs).
- `ps` after all runs: no pytest, no sleeping grandchild (`sleep(60)`), no reader-script processes left.

## Skips
Slice 8 has exactly one skip: `tests/test_docker_engine.py:134 test_echo_in_container` ("docker daemon or image not available"). Whole suite 9 skips = 1 slice 8 + 8 checkpoint/workspace (platform), no new ones.

## Defects
None. Residual note (not a defect): `test_echo_in_container` and the real docker path remain unexercised against a daemon (none available).
