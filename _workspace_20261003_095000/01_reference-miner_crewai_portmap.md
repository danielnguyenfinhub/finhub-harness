# Port map — crewai (slices 8-11 focus)

- Submodule: references/crewai
- Pinned SHA: fbcf2de (git rev-parse --short HEAD)
- Licence: MIT (`LICENSE` at the submodule root, "Copyright (c) 2025 crewAI, Inc."; matches `references/LICENSES.md` row `crewai`, no drift)
- Mined: 2026-10-02 AEST
- Status: COMPLETE
- Path prefix used below: `L` = `references/crewai/lib/crewai/src/crewai`. Every row is a full path in the Source column.
- Existing code check: slices 1-7 are built. `src/master_finhub/sandbox/workspace.py` (166 lines) already exists. These files are 0-byte stubs: `sandbox/docker_engine.py`, `sandbox/stream.py`, `server/app.py`, `server/sse.py`, `tools/mcp/__init__.py`. There is no `src/master_finhub/evals/` or `verifiers/` directory yet. So slices 8-11 are all net-new.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| C1 | 9 | Result carrier pairing tool text with the MCP `isError` flag, so errors are not lost | references/crewai/lib/crewai/src/crewai/mcp/client.py:45 | adapt | NamedTuple/dataclass; maps to the loop's tool-result error flag |
| C2 | 9 | Client constants: 30s connect/exec/discovery timeouts, 3 retries | references/crewai/lib/crewai/src/crewai/mcp/client.py:54 | adapt | Plain module constants; make them injectable for tests |
| C3 | 9 | Client with `connect` / `disconnect`, async context manager, auto-connect on first use | references/crewai/lib/crewai/src/crewai/mcp/client.py:67 | adapt | Keep the small surface: connect, list_tools, call_tool, disconnect |
| C4 | 9 | `list_tools` normalises each tool to name / original_name / description / inputSchema | references/crewai/lib/crewai/src/crewai/mcp/client.py:435 | adapt | Keep the original name for the wire call; use the sanitised name for the LLM |
| C5 | 9 | `call_tool` runs under `asyncio.wait_for`, takes the first content item's text, reads `isError` | references/crewai/lib/crewai/src/crewai/mcp/client.py:612 | adapt | Join all text items instead of only the first (crewai drops the rest) |
| C6 | 9 | Retry wrapper: per-attempt timeout, 2**attempt backoff, auth and not-found errors fail fast | references/crewai/lib/crewai/src/crewai/mcp/client.py:706 | adapt | Its string matching on "unauthorized" is crude; retry only transient errors |
| C7 | 9 | Strips None values from tool arguments, recursing into dicts and lists | references/crewai/lib/crewai/src/crewai/mcp/client.py:563 | adapt | Drop the hard-coded `sources` special case at :578 |
| C8 | 9 | Tool-name sanitiser: NFKD to ASCII, split camelCase, lowercase, `[a-z0-9_]`, 64 chars with sha256 suffix | references/crewai/lib/crewai/src/crewai/utilities/string_utils.py:26 | adapt | Stdlib only; avoids provider name-rule rejections |
| C9 | 9 | Transport ABC: connect/disconnect, `_set_streams` / `_clear_streams`, `connected` flag | references/crewai/lib/crewai/src/crewai/mcp/transports/base.py:25 | adapt | Only needed if there is more than one transport; stdio-only needs no ABC |
| C10 | 9 | Stdio transport: merges env over the SDK default env, then applies an optional env-filter hook | references/crewai/lib/crewai/src/crewai/mcp/transports/stdio.py:69 | adapt | Spawn with a scrubbed env, not the parent env |
| C11 | 9 | Module-level `_env_filter_hook` for stripping credentials from child env | references/crewai/lib/crewai/src/crewai/mcp/transports/stdio.py:13 | adapt | The idea becomes an allowlisted env builder; matters for secrets in this repo |
| C12 | 9 | Stdio disconnect: terminate, wait up to 5s, then kill; cleanup is best-effort and logged | references/crewai/lib/crewai/src/crewai/mcp/transports/stdio.py:124 | adapt | `self._process` is never assigned in connect(), so the terminate branch is dead code; do not copy that |
| C13 | 9 | `StaticToolFilter`: allow list and block list on tool name, block wins | references/crewai/lib/crewai/src/crewai/mcp/filters.py:38 | adapt | Tiny; gives a per-server tool allowlist, a safety win |
| C14 | 9 | `MCPNativeTool`: fresh client per invocation via `client_factory`, name prefixed `{server}_{tool}` | references/crewai/lib/crewai/src/crewai/tools/mcp_native_tool.py:15 | adapt | Per-call client avoids shared connection state; costs a spawn per call |
| C15 | 9 | Exception hierarchy: `MCPConnectionError` subclasses `ConnectionError` and carries `status_code` | references/crewai/lib/crewai/src/crewai/mcp/exceptions.py:49 | adapt | Only the base class is worth keeping for a stdio-only client |
| C16 | 9 | Tool-list cache keyed per server with a 300s TTL | references/crewai/lib/crewai/src/crewai/mcp/client.py:403 | pattern | Module-global dict at :58; skip it, or keep the cache on the instance |
| C17 | 8 | Stream session: ordered frames (id, seq, type, channel, data) delivered through a queue; the run happens in a worker thread; end and error signalled by sentinel/exception | references/crewai/lib/crewai/src/crewai/utilities/streaming.py:254 | adapt | Same shape as the sandbox output stream and the SSE feed; use `queue.Queue`, sentinel None, re-raise errors |
| C18 | 8 / 10 | `StreamFrame` model: monotonic `seq`, `type`, `channel`, `data`, `timestamp`; `content` property returns chunk text | references/crewai/lib/crewai/src/crewai/types/streaming.py:31 | adapt | A frozen dataclass; reuse the same frame for stdout chunks and SSE events |
| C19 | 8 / 10 | Queue sentinel helpers `_signal_frame_end` / `_signal_frame_error` (put None or the exception) | references/crewai/lib/crewai/src/crewai/utilities/streaming.py:229 | adapt | The consumer loop raises on Exception items and stops on None |
| C20 | 11 | Experiment runner: for each dataset case, run the system, score it, compare against `expected_score`, build a result; any exception becomes a failed result with score 0.0 | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:59 | adapt | Per-case try/except so one crash does not kill the run |
| C21 | 11 | Pass rule: actual >= expected for scalars; for dicts, matching keys must each be >= expected | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:130 | adapt | Simple verifier logic; scalar path is enough for slice 11 |
| C22 | 11 | Dataset-driven loop with a stable per-case id (explicit `identifier` or md5 of the case) | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:26 | adapt | Use sha256, not md5; the id keys baseline comparison |
| C23 | 11 | Result record: identifier, inputs, score, expected_score, passed | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:9 | adapt | A frozen dataclass is enough; no pydantic needed |
| C24 | 11 | Baseline comparison buckets each case into improved / regressed / unchanged / new by prior `passed` | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:99 | adapt | Optional; one benchmark pass/fail needs no baseline |
| C25 | 11 | `assert_experiment_successfully` raises `AssertionError` listing each failed case with expected and actual | references/crewai/lib/crewai/src/crewai/experimental/evaluation/testing.py:13 | adapt | Readable pytest-facing failure message |
| C26 | 11 | `EvaluationScore`: 0-10 score, feedback text, raw response | references/crewai/lib/crewai/src/crewai/experimental/evaluation/base_evaluator.py:32 | pattern | LLM-judge scoring; slice 11 verifiers should be deterministic, so treat as optional |
| C27 | 11 | `BaseEvaluator` ABC with `evaluate()` and a metric category | references/crewai/lib/crewai/src/crewai/experimental/evaluation/base_evaluator.py:52 | pattern | Verifier interface idea; a plain `Callable[[output], bool]` is simpler |

## Do not port

| source | reason |
|---|---|
| references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result_display.py | Rich console UI, out of scope |
| references/crewai/lib/crewai/src/crewai/experimental/evaluation/metrics/** | LLM-judged metrics tied to crewai Agent/Crew internals |
| references/crewai/lib/crewai/src/crewai/experimental/evaluation/agent_evaluator.py | Coupled to the crewai event bus |
| references/crewai/lib/crewai/src/crewai/mcp/tool_resolver.py | AMP slugs, platform fetch, pydantic schema generation; heavy and crewai-specific |
| references/crewai/lib/crewai/src/crewai/mcp/transports/http.py and sse.py | HTTP/SSE MCP transports; slice 9's proof is stdio only (YAGNI) |
| references/crewai/lib/crewai/src/crewai/a2a/** | Agent-to-agent protocol, out of scope. Its `auth/server_schemes.py` is the only crewai file that mentions fastapi/starlette, and it is not a server pattern |

Other submodules are not covered by this map. Per the SKILL.md target table, they hold the container ingress, SSE ping/idle and benchmark runner patterns: openhands for slice 8, dify (pattern only) for slices 9 and 10, and autogpt `classic/` (MIT only, never `autogpt_platform/`) for slice 11.

## Gaps

- **Slice 8, Docker sandbox: crewai has none.** `L/agent/core.py:1469` `_validate_docker_installation` is a no-op that emits a DeprecationWarning saying "CodeInterpreterTool is no longer available. Use dedicated sandbox services like E2B or Modal." Greps for `docker` across `lib/` found only that, `crewai_core/runtime_env.py:171` (a `/.dockerenv` detection, not usable) and `a2a/config.py`. There is no `docker run` argument builder, container lifecycle, resource limits, or `subprocess` use for containers. The `subprocess` hits are `utilities/reset_memories.py` and `tracing/utils.py` (git info), which are irrelevant. Slice 8's engine is net-new. Take the container ingress from openhands/docker and the policy side from deepseek sandbox-policy.
- **Slice 8, output stream:** crewai only gives the generic frame/queue pattern (C17-C19). It has no container stdout/stderr pump and no chunk size cap.
- **Slice 10, server/SSE: crewai has none.** There is no HTTP server, no `text/event-stream`, no `EventSourceResponse` and no PING or idle logic. The only `text/event-stream` mention is the MCP SSE client transport (`mcp/transports/sse.py:50`, a client). The PING-then-event pattern must come from dify (`api/core/app/apps/streaming_utils.py`, pattern only). C17-C19 only supply the event-queue feeder.
- **Slice 11, benchmark:** crewai has no benchmark harness with an executable verifier. Its evaluation is LLM-judged scores on crewai Agents; the C20-C25 runner/threshold/baseline structure is the only part worth taking. The harness/verifier idea should come from autogpt `classic/direct_benchmark` (MIT).
- **Slice 9, dependency risk:** crewai's client wraps the third-party `mcp` Python SDK, imported lazily at `mcp/transports/stdio.py:83` (`from mcp import StdioServerParameters`, `from mcp.client.stdio import stdio_client`). It is not stdlib. Request.md says "no new dependency without licence check." The miner did not verify the `mcp` SDK's licence. The architect should either (a) choose a stdlib-only JSON-RPC 2.0 over stdio client with newline-delimited messages, which fits the "stub stdio server round-trip" proof, or (b) have the licence checked before adding `mcp`. The miner did not open the MCP wire spec here, so the stdlib framing is an inference, not a cited finding.
- **Slice 9 wire protocol:** crewai delegates initialize/handshake and JSON-RPC framing entirely to the SDK. There is no hand-written protocol code in crewai to port.
- **Licence file drift:** none found. `references/LICENSES.md` and `licence-rules.md` agree on MIT for crewai.
- **Not opened:** `mcp/config.py`, `mcp/transports/http.py`, `tools/mcp_tool_wrapper.py` bodies, `flow/` streaming, and `llm.py` streaming. Only the signatures and class lists of `mcp_tool_wrapper.py` were seen, so no row cites them.
