# Port map — deepseek_harness (slices 8-11 only)

- Submodule: references/deepseek_harness
- Pinned SHA: b274e89 (git log -1 --format=%h)
- Licence: MIT, Copyright (c) 2026 DeepSeek (references/deepseek_harness/LICENSE opened). Matches the `deepseek_harness` row in licence-rules.md. `references/LICENSES.md` was not opened, so drift against it was not checked (UNVERIFIED).
- Mined: 2026-10-02 AEST
- Status: COMPLETE for the reachable patterns. The deepseek repo is TypeScript and has no Docker engine, no server-side SSE and no eval runner, so slices 8, 10 and 11 are mostly Gaps (see below).

State of src/master_finhub, so slices 1-7 are not re-proposed:
- Slices 1-7 are built. `tools/safety.py` (573 lines) already holds the command guard: `check_command` at :517, `make_guard` at :572, `CommandPolicy` at :153. `sandbox/workspace.py` (166 lines) holds `Workspace` at :93, `SandboxDenied` at :35 and `lexical_reject` at :48. Do not re-mine path containment or the command denylist.
- Slices 8-11 files exist as 0-byte stubs: `sandbox/docker_engine.py`, `sandbox/stream.py`, `tools/mcp/__init__.py`, `server/app.py`, `server/sse.py`, `server/__init__.py`. `evals/runner.py` is also empty, with empty `evals/benchmarks/` and `evals/verifiers/` directories.
- The builder starts from nothing on 8-11. It must import `check_command` and `Workspace` rather than reimplement them.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D1 | 8 | Scrubbed child env: copy parent env, drop keys matching `KEY\|PASSWORD\|SECRET\|TOKEN` and `DSH_*` (case-insensitive) | references/deepseek_harness/packages/subprocess/subprocess/src/index.ts:60 (regex at :44) | adapt | Reuse for `docker run -e` and the MCP stdio child. Explicit env merges after the scrub. |
| D2 | 8 | Collect-mode output spec: bounded in-memory cap that keeps the TAIL, plus an optional whole-stream spill file with its own cap | references/deepseek_harness/packages/subprocess/subprocess/src/types.ts:44 | adapt | The `CollectedOutput` shape (text, truncated, spillPath) is at :22. It maps directly to `stream.py`. |
| D3 | 8 | Tail-retaining byte buffer: push chunks, drop from the head while over the cap | references/deepseek_harness/packages/e2b/subprocess-e2b/src/output.ts:97 (class at :65) | adapt | Loop at :103. In Python, use `collections.deque[bytes]` plus a retained-bytes counter. |
| D4 | 8 | Offset-based non-consuming read: returns text, nextOffset and a `lossy` flag when the caller's offset fell off the tail | references/deepseek_harness/packages/e2b/subprocess-e2b/src/output.ts:117 | adapt | Lets multiple consumers share one stream. Optional for the first cut. |
| D5 | 8 | Process-tree kill: signal the negative process group, fall back to the direct child on failure, keep teardown idempotent | references/deepseek_harness/packages/subprocess/subprocess-local/src/spawn.ts:290 | adapt | In Python use `start_new_session=True` plus `os.killpg`. For Docker, `docker kill` or `docker rm -f` replaces it. |
| D6 | 8 | SIGTERM-then-SIGKILL escalation with a validated, bounded `graceMs` | references/deepseek_harness/packages/subprocess/subprocess-local/src/spawn.ts:326 | adapt | Only the grace-period validation is visible at :326-329. The escalation timer body was not read (UNVERIFIED). |
| D7 | 8 | Sandbox profile by mode: read-only root bind plus writable `workspaceRoot` and `/tmp` only in `workspace-write`; PID unshare; die with parent | references/deepseek_harness/packages/sandbox/sandbox-local/src/profiles.ts:16 | adapt | Docker analogue: `--read-only`, `-v ws:ws:rw`, `--tmpfs /tmp`, `--pids-limit`. Add `--network none` (net-new). |
| D8 | 8 | Sandbox escalation: modes ordered by width, escalation targets limited to `workspace-write` and `danger-full-access`, justification validated | references/deepseek_harness/packages/sandbox/sandbox/src/escalation.ts:28 | reference | Slice 3 already covers policy modes. Only relevant if the Docker engine needs an "allow once" path. |
| D9 | 9 | Transport factory by config discriminator (stdio vs streamable-http); stdio child gets the scrubbed env plus the explicit env | references/deepseek_harness/packages/mcp/mcp-client/src/transport.ts:31 | adapt | Env helper at :21. Stdio only for slice 9 (stdlib, no `mcp` SDK dependency). |
| D10 | 9 | Config union: stdio {command, args, env, cwd} or streamable-http {url, headers}, plus `serverName`, `toolCallTimeoutMs`, `failOnStartupError` | references/deepseek_harness/packages/mcp/mcp-client/src/index.ts:50 | adapt | Use a Python frozen dataclass for the stdio variant only. |
| D11 | 9 | Public tool name `mcp__<server>__<tool>`; invalid chars replaced with `_`; truncated names get a 12-hex SHA-256 suffix | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:111 | adapt | `hashlib` only. The model-facing name limit is 64 chars. Check the existing tool registry's limit first. |
| D12 | 9 | `tools/call` request carrying a cancel signal and a per-call timeout | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:80 | adapt | Timeout is `opts.toolCallTimeoutMs` at :92. |
| D13 | 9 | Executor maps MCP `isError: true` to a thrown error so the runtime emits an error result; content is flattened to text | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:303 | adapt | The `isError` branch is at :344. Skip the image projection at :354-457 (YAGNI). |
| D14 | 9 | Two-phase tool sync: fetch the full list first, then swap; a failed fetch leaves the previous tool generation intact | references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:143 | adapt | The one-shot sync that slice 9 needs is small. The paginated `tools/list` helper is at :72. |
| D15 | 9 | Reconnect supervisor: backoff = min(maxDelay, initial*2^(n-1)), attempt budget resets after an uptime of maxDelay | references/deepseek_harness/packages/mcp/mcp-client/src/connection.ts:192 | pattern | Optional for the "stub stdio round-trip" proof. Defaults at :40: 500 ms, 30 s, 10 attempts. Policy validation at :65. Defer unless the architect wants it. |
| D16 | 9 | Python stdio JSON-RPC client: `Popen` with pipes and line buffering; daemon reader thread parses one JSON object per line; stderr drained on a separate thread | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:37 | adapt | Launch is at :73, reader loop at :318, stderr loop at :336. This is the closest runnable Python precedent for slice 9. |
| D17 | 9 | Response routing: pending id -> one-slot `queue.Queue`; dispatches on message shape (request, response, notification); an error object raises `JsonRpcError` | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:343 | adapt | Waiter registration is at :238. The deadline loop that raises `TimeoutError` is at :258-276. |
| D18 | 9 | On EOF or reader crash, fail every pending waiter so no caller hangs; request writes serialised by a write lock | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:331 | adapt | Lock at :44. Needed for a no-hang stub-server test. |
| D19 | 9 | Graceful close: send `shutdown`, then close stdin and reap the child | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:87 | adapt | Add `terminate()` then `kill()` after a timeout, which this file does not show. MCP uses `notifications/initialized`. |
| D20 | 10 | SSE line framing as the consumer side: payload `[DONE]` is terminal, and EOF before it is an error (`STREAM_CLOSED`) | references/deepseek_harness/packages/llm/llm-deepseek/src/sse.ts:28 | reference | Client-side parser, not a server. Use it only as the test-side client for "receives PING then event". |
| D21 | 10 | In-process notification fan-out: per-subscriber queue with an optional predicate filter; a failing predicate drops that subscriber | references/deepseek_harness/python/sdk/src/deepseek_harness/client.py:363 | pattern | Shape for per-run event subscribers feeding SSE. `NotificationSubscription.next/drain/close` is at :507. |

## Do not port

| source | reason |
|---|---|
| references/deepseek_harness/packages/sandbox/sandbox-windows-acl/** | Windows ACL/FFI sandbox; target is Linux and Docker. |
| references/deepseek_harness/packages/e2b/** (except the output buffer, D3/D4) | E2B cloud sandbox with a base64 transport; third-party service, no Docker. |
| references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:363-559 | MCP image-to-attachment projection; YAGNI for slice 9. |
| references/deepseek_harness/packages/client/**, apps/web/** | UI; out of scope. |
| references/autogpt/autogpt_platform/** | Not mined here. Polyform Shield, so any slice 11 evidence must come from `autogpt/classic/direct_benchmark/` only. |

## Gaps

- **Slice 8, Docker:** no Docker engine exists in deepseek. Searched case-insensitively for `docker` and `container` across packages, apps, scripts and docs; the only hits are e2b/sandbox READMEs and unrelated files. `docker run` flag design is net-new. The miner did not open `references/openhands/docker/`.
- **Slice 8, output stream:** D2-D4 are the only analogues. There is no line-by-line "stream container stdout to a consumer" abstraction in deepseek. D2 is a collect/tail buffer, not an event stream.
- **Slice 10, server and SSE:** deepseek has no server-side SSE emitter. Searched `text/event-stream`, `EventSource`, `createServer`, `WebSocket`, `Hono` and `express` across packages and apps. The only SSE code is the client parser (D20). `packages/api/gateway` has no heartbeat, keepalive or ping code (searched `heartbeat`, `keepalive`, `ping`, `idle`; the matches were e2e UI tests only). The PING/idle pattern comes from dify `api/core/app/apps/streaming_utils.py` (pattern only), which this miner did not open because the assignment was deepseek only.
- **Slice 11, evals and verifiers:** no benchmark runner exists in deepseek. `BENCHMARK.md` is two lines pointing at the Python SDK `jsonrpc-agent` example. Nothing there is portable. The only source is `autogpt/classic/direct_benchmark/` (MIT). Do not use anything under `autogpt_platform/`.
- **D6:** only the `graceMs` guard at spawn.ts:326-329 was read. The SIGTERM-then-SIGKILL timer body was not opened, so the architect should treat the escalation sequence as unverified.
- **TypeScript to Python:** D16-D19 are the only Python sources. They are synchronous and thread-based, which fits the stdlib-only constraint. D9-D15 are TypeScript built on the `@modelcontextprotocol/sdk` package. Port the idea only, using JSON-RPC 2.0 over stdio via `subprocess` and `json`. A new MCP SDK dependency would need a licence check.
