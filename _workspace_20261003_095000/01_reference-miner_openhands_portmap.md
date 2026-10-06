# Port map — openhands (slices 8-11 focus)

- Submodule: references/openhands (fork of OpenHands/agent-canvas)
- Pinned SHA: not read (no git access used)
- Licence: MIT (references/openhands/LICENSE:1, "Copyright 2025 OpenHands contributors"); matches references/LICENSES.md. No enterprise/ directory exists in this submodule (ls enterprise: absent), and the only LICENSE file under it is the root one. No licence drift.
- Mined: 2026-10-02 AEST
- Status: COMPLETE for slices 8-11. The miner read src/master_finhub/ only at directory level, plus a size check. sandbox/docker_engine.py, stream.py, server/app.py, sse.py and tools/mcp/ are empty stubs (0 lines), so slices 8-10 are unbuilt, and evals/ exists at repo root. Slices 1-7 already own safety.py (573 lines), workspace.py (166), router, context, checkpoint, graph, bus and modes. The miner did not re-propose them.
- Important: this is a UI-only fork (TypeScript/React). There is NO sandbox runtime, MCP client, SSE server or eval runner. The agent-server is an external pip/docker image. Rows below are TS ports of the idea, not syntax. Most value is in operational patterns.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| O1 | 8 | Child-PID list plus `trap cleanup EXIT SIGINT SIGTERM` that kills children then waits then exits | references/openhands/docker/entrypoint.sh:286 | adapt | Maps to docker_engine teardown: kill container on exit and signal. |
| O2 | 8 | Readiness gate: poll TCP port every 1s up to max_wait, warn and return 1 on timeout | references/openhands/docker/entrypoint.sh:359 | adapt | Use for container-ready wait; Python socket.create_connection with deadline. |
| O3 | 8 | Supervisor loop: `kill -0` the ingress PID every 10s; container exits nonzero when it dies | references/openhands/docker/entrypoint.sh:493 | adapt | Backend crash tolerated, ingress death fatal. Watchdog idea for engine. |
| O4 | 8 | Validate path-prefix env input: normalise slashes, reject `.`/`..`, charset whitelist, reject collision with reserved routes | references/openhands/docker/entrypoint.sh:105 | adapt | Input-validation pattern; reserved list at line 149. Reuse for mount and path args. |
| O5 | 8 | Port env must be numeric before it is interpolated into a proxy target URL | references/openhands/docker/entrypoint.sh:158 | adapt | Cheap fail-fast; validate container port args. |
| O6 | 8 | Secure-by-default exposure: session key embedded only if explicit opt-in flag, with warning to publish on loopback only | references/openhands/docker/entrypoint.sh:163 | reference | Policy shape for engine config: network and secrets opt-in, default deny. |
| O7 | 8 | Multi-stage image; config values generated to a sourceable defaults.env at build to avoid runtime parsers | references/openhands/docker/Dockerfile:50 | reference | Image is Node/agent-server specific; only the no-runtime-parser idea transfers. |
| O8 | 8 | Test config uses `--network host` on Linux; host.docker.internal override for Docker Desktop | references/openhands/playwright.mock-llm-docker.config.ts:19 | reference | Informs docker_engine network flag and the skip-without-docker test. |
| O9 | 8 (stream) | Paginate command output events by `page_id`/`next_page_id` with a hard page cap (20) and concatenate stdout/stderr in timestamp order | references/openhands/src/api/bash-service/bash-service.api.ts:49 | adapt | Output-stream model: ordered chunks, bounded loop. Cap constant at line 18. |
| O10 | 8 (stream) | Event type guard: filter a mixed stream to BashOutput kind | references/openhands/src/api/bash-service/bash-service.api.ts:20 | reference | Tagged-event discriminator for stream.py chunk kinds (stdout/stderr/exit). |
| O11 | 9 | Redact secrets from MCP error text: collect config values (url userinfo, secret-like query params, auth values), strip them from message | references/openhands/src/utils/redact-mcp-secrets.ts:110 | adapt | Directly useful for MCP client errors. Min length 4 (line 9) avoids mangling. |
| O12 | 9 | Generic secret regexes: GitHub PAT, Slack, Linear, JWT shapes, plus Bearer token keeping prefix | references/openhands/src/utils/redact-mcp-secrets.ts:18 | adapt | Port as compiled `re` list; Bearer pattern at line 31. |
| O13 | 9 | Map probe response to health: failed(kind) or healthy(verified vs connectivity-only); 401/403 text reclassified as credentials | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:46 | adapt | `verified` requires probe tool advertised AND call succeeded; never silently upgrade. |
| O14 | 9 | Auth-failure sniff regex on error text | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:22 | adapt | Conservative; keep as error-kind classifier. |
| O15 | 9 | Non-mutating probe wrapper: begin check, call server test, catch to failed, resolve | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:75 | adapt | Shape for a `health_check()` on the MCP client. |
| O16 | 9 | In-flight check ids: a result commits only if the entry is still the same `checking` id, so stale probes cannot overwrite newer ones | references/openhands/src/api/mcp-health/mcp-health-store.ts:50 | adapt | Small, testable concurrency guard. Store is deliberately non-persisted (line 7). |
| O17 | 10 | Reconnect backoff: base 1s doubling, cap 30s, plus up to 30% random jitter, optional maxAttempts | references/openhands/src/hooks/use-websocket.ts:25 | adapt | Client-side reconnect; delay math at line 133. Useful in the server test client. |
| O18 | 10 | Reconnect only for sockets still marked allowed; disable flag set before close on unmount | references/openhands/src/hooks/use-websocket.ts:118 | reference | Avoids reconnect-after-close race; lifecycle lesson for SSE client tests. |
| O19 | 10 | Ingress route table: prefix to backend map (/api, /sockets, /health, /ready, /docs ...) | references/openhands/docker/entrypoint.sh:407 | reference | Only informs route naming: health and ready endpoints. No SSE here. |
| O20 | 10 | Default bind is loopback; non-loopback bind with embedded session key refused unless explicit flag | references/openhands/scripts/static-server.mjs:244 | adapt | server/app.py should default 127.0.0.1 and refuse LAN plus key without opt-in. Flags at line 159-165, mutual exclusion at 197. |
| O21 | 10 | Test that the server binds loopback only: connect via LAN IPv4 fails, loopback succeeds | references/openhands/tests/e2e/bind-policy/loopback-bind.spec.ts:30 | adapt | `canConnect` helper at line 37; port to a pytest socket test. |
| O22 | 10 | Session auth header `X-Session-API-Key` between client and runtime | references/openhands/src/api/bash-service/bash-service.api.ts:33 | reference | Header name only (doc comment). Use constant-time compare in Python. |
| O23 | 10 | Paged event search with `next_page_id` and graceful fallback to empty page when server lacks filters (avoids infinite retry) | references/openhands/src/api/event-service/event-service.api.ts:75 | reference | Fallback comment at line 126; pagination cursor idea for event replay endpoint. |
| O24 | 11 | Test report renderer: summary visible, per-test table (status, duration, retries, error) in collapsible details | references/openhands/tests/e2e/mock-llm/scripts/render-mock-llm-report.mjs:150 | reference | Result-record fields only (tests[].status, durationMs, retryCount, error). |
| O25 | 11 | Mock-LLM e2e: deterministic fake LLM server so agent runs are reproducible | references/openhands/playwright.mock-llm-docker.config.ts:3 | reference | Same idea as the existing fake_llm.py; confirms an eval-with-fake-LLM design. |

## Do not port

| source | reason |
|---|---|
| references/openhands/src/components/**, src/routes/**, src/hooks/ (React) | UI code, out of scope. |
| references/openhands/electron/** | Desktop shell, out of scope. |
| references/openhands/helm/** | K8s chart; the deferred factory and deploy are not in slices 8-11. |
| references/openhands/docker/Dockerfile and entrypoint.sh bodies | Node/agent-server/automation specific. Use only the shell patterns O1-O5, not the content. |
| references/openhands/src/api/cloud/**, automation-service/** | Cloud/automation service clients, not applicable to a local runtime. |

No enterprise/ or non-MIT paths were found. Nothing is licence-blocked here. autogpt_platform (Polyform Shield) and dify (pattern only) are not mined in this map.

## Gaps

- No container sandbox runtime. Searched: `docker run`, `docker exec`, `execFile`, `spawn(` in src, scripts, electron, tools, bin. Only scripts/docker-build.mjs and dev scripts exist, plus the entrypoint. Slice 8 `docker_engine.py` (create, exec, resource limits, timeout kill, output capture) is net-new. Source it from stdlib `subprocess` and the `docker` CLI, with no openhands reference. docker/ contains only Dockerfile and entrypoint.sh (matches the phase table's "container ingress/entrypoint pattern").
- No MCP protocol client (JSON-RPC over stdio, initialize, tools/list, tools/call). Only the UI-side health and redaction layer (O11-O16), and the real probe is a call to the external agent-server `McpService.testServer`. Slice 9 transport is net-new; take its shape from dify `mcp_client.py` as pattern only (not mined here).
- No SSE. Searched: `EventSource`, `text/event-stream`, `heartbeat`, `keepalive`, `ping` in src (only UI-text hits). openhands uses WebSockets plus REST pagination. There is no server-side PING/idle logic, so slice 10 PING-then-event is net-new; use dify `streaming_utils.py` (pattern only).
- No eval or benchmark runner and no verifiers. Only Playwright e2e specs and a mock-LLM report renderer (O24, O25). Slice 11 should come from autogpt `classic/direct_benchmark` (MIT only), not from here.
- Slice 8 `stream.py`: no streaming primitive for process stdout. O9 and O10 give only an ordered, capped, tagged-chunk model.
- The miner did not open static-server.mjs beyond flag and help lines (159-165, 197, 244, 722), so its proxy/WebSocket-upgrade internals are unverified.
