# Port map — autogpt (slices 8-11 focus)

- Submodule: references/autogpt
- Pinned SHA: d58d41b (git rev-parse --short HEAD)
- Licence: root `references/autogpt/LICENSE` says everything outside `autogpt_platform/` is MIT, and `autogpt_platform/` is Polyform Shield. This matches the `autogpt` row in licence-rules.md. The miner did not open `references/LICENSES.md`, so it did not check it for drift (UNVERIFIED).
- Mined: 2026-10-02
- Status: COMPLETE for the paths opened. Slices 9 and 10 have no source in `classic/` (see Gaps).

Existing-code skim, to avoid re-proposing slices 1-7: `src/master_finhub/sandbox/docker_engine.py`, `sandbox/stream.py`, `server/app.py`, `server/sse.py` and `tools/mcp/__init__.py` all exist but are 0-line stubs. There is no `evals/` or `verifiers/` package yet. `sandbox/workspace.py` (166 lines, slice 3), the runtime loop and the orchestration code are already built, so do not re-propose those.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| A1 | 8 | Availability probe: `docker.from_env().info()["OSType"] == "linux"`, any exception returns False. Use it to skip when there is no Docker. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:39 | adapt | Use `subprocess` with `docker info --format {{.OSType}}`. The `docker` SDK would be a new dependency. |
| A2 | 8 | Detect "already inside a container" via `os.path.exists("/.dockerenv")`, then run directly instead of nesting. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:30 | adapt | One line. Probably not needed for the tests. |
| A3 | 8 | Run a script in a container: pull the image if missing, mount the workspace at `/workspace` rw, then `exec_run` `python -B <relpath> args` and raise on a non-zero exit. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:422 | adapt | Rewrite as `docker run --rm -v ws:/workspace -w /workspace`. Output goes through stream.py. |
| A4 | 8 | Per-agent container name gets a random 8-letter suffix, so agents do not share a container. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:85 | adapt | Use `--name mf_<uuid8>`. Prefer `--rm` over the reuse/restart logic at :446-505. |
| A5 | 8 | Timeout is clamped 1-600 (default 120) and a timeout raises a dedicated `CodeTimeoutError`. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:120 | adapt | Use `subprocess.run(timeout=)` or `asyncio.wait_for`, then `docker kill`. This source only times out in the non-docker path (:258-274). The docker `exec_run` at :512 passes no timeout, so the cap is not enforced there. |
| A6 | 8 | Image pull streamed line by line, logging status/progress. This is the only streamed output in the source. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:468 | pattern | For stream.py, yield stdout/stderr lines from `Popen`. |
| A7 | 3/8 | Shell allowlist/denylist: `validate_command` takes the first token from `shlex.split`. Allowlist mode never permits a shell. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:283 | adapt | Slice 3 already has `safety.py`. Reuse that. This is only a cross-check. |
| A8 | 8 | Shell `subprocess.run` with `cwd` inside the workspace, timeout, and output formatted as `STDOUT:\n..\nSTDERR:\n..`. | references/autogpt/classic/forge/forge/components/code_executor/code_executor.py:332 | adapt | Output format for the stream.py `final` chunk. |
| A9 | 11 | Data models: `Challenge(name, task, category, difficulty, cutoff, ground_truth, artifacts_dir, source_path)`. | references/autogpt/classic/direct_benchmark/direct_benchmark/models.py:259 | adapt | Use a stdlib `dataclass`, not pydantic. Check whether pydantic is already a dependency. |
| A10 | 11 | `StepResult` and `ChallengeResult(success, score, steps, n_steps, run_time, cost, timed_out, error_message, output_files)`. | references/autogpt/classic/direct_benchmark/direct_benchmark/models.py:274 | adapt | `ChallengeResult` starts at models.py:285. Map `steps` onto the loop's tool-call records. |
| A11 | 11 | Challenge `data.json` schema: name, task, cutoff, category, and `ground` containing `files`, `should_contain`, `should_not_contain` and `eval.type`. | references/autogpt/classic/direct_benchmark/challenges/verticals/code/0_execute_python/data.json:1 | adapt | Use as the benchmark fixture shape. One challenge is enough for the "one benchmark pass/fail" proof. |
| A12 | 11 | Loader: `rglob("data.json")`, skip "deprecated", skip malformed with a warning, filter by category and name. | references/autogpt/classic/direct_benchmark/direct_benchmark/challenge_loader.py:59 | adapt | `_load_challenge` is at :127 (defaults cutoff=60). Port only the glob + name filter. |
| A13 | 11 | Per-run isolated temp workspace. Copy `artifacts_in` into it, run the agent, then collect every file as `{relpath: text}`. | references/autogpt/classic/direct_benchmark/direct_benchmark/runner.py:45 | adapt | `_setup_workspace` is at :132, `_collect_output_files` at :341. Use `tempfile.mkdtemp`, then `Workspace` from slice 3. |
| A14 | 11 | Agent loop under `asyncio.wait_for(timeout)`: `max_steps` cap, a `finish` tool ends the run, and a step callback is called. | references/autogpt/classic/direct_benchmark/direct_benchmark/runner.py:235 | adapt | Slice 1 `loop.py` already stops when there are no tool calls, so wrap it rather than copy this. |
| A15 | 11 | Timeout and exception handling: build a failed `ChallengeResult` (`timed_out=True` or `error_message` with traceback) and never raise. | references/autogpt/classic/direct_benchmark/direct_benchmark/runner.py:88 | adapt | The caller always receives a result. |
| A16 | 11 | `Evaluator.evaluate`: dispatch on `ground.eval.type`. Pass threshold is `score >= 0.9`, and a timed-out run can never pass but still gets a score. | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:15 | adapt | This is the core of the `verifiers/` dispatch. |
| A17 | 11 | String-match verifier: every `should_contain` present, no `should_not_contain`, optional case-insensitivity; score is 0.0 or 1.0. | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:94 | adapt | Simplest deterministic verifier. Start here. |
| A18 | 11 | File selection: pattern ".ext" matches by suffix, otherwise exact name or `endswith("/"+name)`, then contents joined. | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:71 | adapt | `_matches_pattern` is at :86. |
| A19 | 11 | Python and pytest verifiers: write the outputs to a tmpdir, run `sys.executable` (30s) or `-m pytest` (60s), and pass on exit code 0. | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:117 | adapt | `_eval_pytest` is at :158. The `"error" in stderr` heuristic at :153 is brittle, so skip it. Agent-written code runs on the host, so run it in the slice 8 container instead. |
| A20 | 11 | The "llm" eval type is declared but falls back to string match (a stub). | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:50 | reference | Do not build an LLM judge; YAGNI. |
| A21 | 11 | Resume state: `.benchmark_state.json` keyed `config:challenge:attempt`, saved immediately after each completed run. | references/autogpt/classic/direct_benchmark/direct_benchmark/state.py:40 | adapt | Optional. Reuse the slice 5 checkpoint helper (`orchestration/_fsio.py`) instead of porting the class. |
| A22 | 11 | Concurrency: `asyncio.Semaphore(max_parallel)` plus `as_completed` over a matrix of config x challenge x attempt. | references/autogpt/classic/direct_benchmark/direct_benchmark/parallel.py:41 | adapt | The semaphore is at :88. Optional; the slice 11 proof needs one run. |
| A23 | 11 | Adapter ABC with `setup`, `load_challenges` and `evaluate`, plus a registry decorator. | references/autogpt/classic/direct_benchmark/direct_benchmark/adapters/base.py:10 | reference | Over-engineered for one benchmark, so skip it. `adapters/__init__.py:9` is the registry. |
| A24 | 11 | Report: per-config `report.json` plus a comparison report. | references/autogpt/classic/direct_benchmark/direct_benchmark/report.py:17 | pattern | One JSON dump is enough. |
| A25 | 10 | Agent Protocol REST shape: `POST /agent/tasks`, `POST /agent/tasks/{id}/steps` (the step route is the one that does work) and `GET /heartbeat`. | references/autogpt/classic/forge/forge/agent_protocol/api_router.py:50 | pattern | Route naming only. The steps route is at :252 and heartbeat at :42. No SSE here. |
| A26 | 10 | The only streaming in `classic` is a plain `StreamingResponse` for artifact download, with `media_type=application/octet-stream`. | references/autogpt/classic/original_autogpt/autogpt/app/agent_protocol_server.py:427 | reference | Not SSE. No ping or idle handling. |

## Do not port

| source | reason |
|---|---|
| references/autogpt/autogpt_platform/backend/backend/api/features/mcp/routes.py | Polyform Shield. MCP discover-tools and OAuth routes (`discover_tools` at :120). Do not use as a source for slice 9. |
| references/autogpt/autogpt_platform/backend/backend/api/features/mcp/oauth_registration.py | Polyform Shield. MCP OAuth. |
| references/autogpt/autogpt_platform/backend/backend/api/features/chat/routes.py | Polyform Shield. Contains `StreamingResponse`/SSE chat, which is tempting for slice 10 but off-limits. |
| references/autogpt/autogpt_platform/** (all of it) | Polyform Shield 1.0. Never a source. |
| references/autogpt/classic/direct_benchmark/direct_benchmark/adapters/swe_bench.py | MIT, but it is the `swebench` package plus Modal and HuggingFace datasets, so it would add heavy dependencies. Only the idea is useful (`_check_docker` at :113, `_evaluate_with_docker` at :305). |
| references/autogpt/classic/direct_benchmark/direct_benchmark/ui.py | Rich terminal UI. Out of scope, and `rich` would be a new dependency. |

## Gaps

- **Slice 9 (MCP client): none in `classic/`.** The miner grepped `classic/` for `mcp`, `stdio_client`, `jsonrpc` and `modelcontext` and found nothing. The only MCP code is under `autogpt_platform/`, which is blocked. Use the Dify rows (`dify/api/core/mcp/mcp_client.py`, pattern only) or write it fresh from the MCP spec. A stdio JSON-RPC 2.0 client over `asyncio.subprocess` is stdlib-only.
- **Slice 10 (server/SSE): no SSE, PING or idle handling in `classic/`.** The miner grepped for `text/event-stream`, `EventSource` and `sse_starlette` and found nothing. Only A25/A26 (REST naming, a binary StreamingResponse) exist. Use the Dify `streaming_utils.py` pattern (pattern only) or hand-write it with `http.server`/`asyncio` streams. Note that `classic/` uses FastAPI and uvicorn, which are not stdlib and would need a licence and dependency check.
- **Slice 8: no stream-to-client output in the docker path.** `code_executor.py` returns the whole output at the end (:527). The only streaming is the image-pull loop (A6). The stream.py design (line-by-line chunks from `Popen` stdout/stderr) is net-new. The source also ignores `timeout` in `exec_run`, so the docker kill-on-timeout behaviour is net-new too (the non-docker path does enforce it, :258-274).
- **Dependency flags for the architect.** `code_executor.py` imports the `docker` SDK (:10) and the benchmark uses pydantic and click. The spec says no new dependency without a licence check. The stdlib alternatives are the `docker` CLI via `subprocess`, `dataclasses`, `argparse` and `json`.
- **Slice 11 verifier gap.** Autogpt has no verifier that runs inside a sandbox. A19 runs on the host and A16's `"llm"` type is a stub. Running verifiers in the slice 8 container is net-new.
- The miner did not read any file in `forge/forge/components/watchdog/` or `permissions.py` beyond the listing, so it makes no claims about them. Slice 3 is already built anyway.
