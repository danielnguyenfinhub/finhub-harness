# Port map — dify (slices 8-11 only)

- Submodule: references/dify
- Pinned SHA: 431c1857 (git rev-parse --short HEAD)
- Licence: Apache-2.0 MODIFIED (references/dify/LICENSE; matches references/LICENSES.md and licence-rules.md, no drift). Every row below is **pattern only**.
- Exact additional conditions, from LICENSE:
  1. Multi-tenant: "Unless explicitly authorized by Dify in writing, you may not use the Dify source code to operate a multi-tenant environment." One tenant = one workspace.
  2. LOGO/copyright: you may not remove or modify the LOGO or copyright information in the Dify console or applications. This applies to the frontend only, meaning everything under `web/` or the "web" Docker image. It is inapplicable to uses that do not involve the frontend.
  3. Contributor terms: the producer can adjust the licence, and contributed code may be used commercially.
  4. All other rights and restrictions follow Apache-2.0. The interactive design is protected by an appearance patent. © 2025 LangGenius, Inc.
- Consequence for us: nothing is copied. Write each unit fresh in Python 3.12 stdlib, with no mirrored names, structure or comments. Nothing from `web/` is touched.
- Mined: 2026-10-02 AEST
- Status: COMPLETE for slices 8-11. Slices 1-7 were not re-mined.

## Existing code state

- Slices 1-7 are built: runtime/{loop,context,router,anthropic_llm,fake_llm}, tools/safety.py, sandbox/workspace.py, and orchestration/{dag_engine,graph,graph_store,message_bus,modes/*}.
- 0-byte stubs exist for these slice 8-11 targets:
  - sandbox/docker_engine.py, sandbox/stream.py
  - server/app.py, server/sse.py
  - tools/mcp/__init__.py exists, but there is no client.py.
  - There are no evals/ or verifiers/ directories.
- factory/* is empty and deferred (slice 12).

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| Y1 | 10 | Generator yields an immediate PING first so the connection is not left pending | references/dify/api/core/app/apps/streaming_utils.py:13 | pattern | Satisfies "client receives PING then event"; yield before any subscribe/wait |
| Y2 | 10 | Poll loop with 1s receive timeout; track last-message and last-ping times | references/dify/api/core/app/apps/streaming_utils.py:35 | pattern | Use queue.get(timeout) in stdlib; no Redis |
| Y3 | 10 | Idle timeout ends the stream; ping interval emits keepalive only while idle; any message resets both timers | references/dify/api/core/app/apps/streaming_utils.py:40 | pattern | Make clocks injectable so the test is deterministic |
| Y4 | 10 | Stream stops after an event whose type is in a terminal set; non-dict events skipped | references/dify/api/core/app/apps/streaming_utils.py:53 | pattern | Our terminal set: run finished / error |
| Y5 | 10 | Defaults: idle_timeout=300, ping_interval=10.0, passed through to the stream generator | references/dify/api/core/app/apps/message_generator.py:20 | pattern | Defaults only; expose as constants |
| Y6 | 10 | Event-name enum with PING="ping", ERROR, MESSAGE, MESSAGE_END | references/dify/api/core/app/entities/task_entities.py:62 | pattern | Our own StrEnum; keep wire names simple |
| Y7 | 10 | HTTP response wraps the generator with mimetype text/event-stream | references/dify/api/controllers/service_api/app/workflow_events.py:172 | pattern | Stdlib http.server equivalent; set no-cache headers ourselves |
| Y8 | 9 | MCPClient is a context manager that connects, initializes, and cleans up via ExitStack | references/dify/api/core/mcp/mcp_client.py:20 | pattern | Shape: `__enter__` connects and handshakes, `__exit__` closes |
| Y9 | 9 | Transport chosen from URL last path segment, with fallback sse to streamable http, closing the partial connection first | references/dify/api/core/mcp/mcp_client.py:58 | pattern | We need stdio instead (see Gaps); close the half-open transport on failure |
| Y10 | 9 | Public API: list_tools and invoke_tool(name, args), each raising if the session is not initialized | references/dify/api/core/mcp/mcp_client.py:113 | pattern | Mirror as list_tools/call_tool; guard against use before handshake |
| Y11 | 9 | cleanup closes the exit stack, then always resets session state in finally | references/dify/api/core/mcp/mcp_client.py:126 | pattern | Terminate the subprocess in finally; do not leak it |
| Y12 | 9 | MCP handshake: send initialize with protocol version and capabilities, validate server version, then send notifications/initialized | references/dify/api/core/mcp/session/client_session.py:112 | pattern | Needed for the stub-server round-trip; the JSON-RPC method names are protocol, not Dify IP |
| Y13 | 9 | Request/response correlation: send_request waits on a per-request-id queue with a read timeout and raises on a JSON-RPC error | references/dify/api/core/mcp/session/base_session.py:199 | pattern | Our version: a reader thread plus dict[id, Queue] |
| Y14 | 9 | Background receive loop dispatches responses, requests and notifications; a None sentinel ends it | references/dify/api/core/mcp/session/base_session.py:309 | pattern | On subprocess EOF, wake all waiters with an error so none hang |
| Y15 | 9 | SSE transport: endpoint event, then message events; writer thread POSTs queued messages | references/dify/api/core/mcp/client/sse_client.py:167 | reference | Understanding only; HTTP transport is out of scope for the slice-9 proof |
| Y16 | 8 | Code-execution-as-a-service: POST language/code to a sandbox endpoint with split connect/read/write timeouts; non-200 and 503 mapped to a typed error | references/dify/api/core/helper/code_executor/code_executor.py:69 | pattern | Only the error-mapping and timeout split carry over; we run docker directly via subprocess |
| Y17 | 8 | Sandbox reply carries a code/message plus data.stdout/data.error; error raises, else stdout is returned | references/dify/api/core/helper/code_executor/code_executor.py:127 | pattern | Maps to our result type: stdout, error, exit status |

## Do not port

| source | reason |
|---|---|
| references/dify/web/** | Frontend. The LOGO/copyright condition applies, and it is irrelevant to our runtime. |
| Any dify file as copy source | Modified Apache-2.0. The multi-tenant restriction makes it pattern only (licence-rules hard stop 2). |
| references/dify/api/core/mcp/auth/**, auth_client.py | OAuth and tenant-workspace coupling; out of scope for the slice-9 stub round-trip. |
| references/dify/api/core/mcp/mcp_client.py:33 (request-header placeholder substitution via Flask) | Flask and tenant-request coupling. |
| references/autogpt/autogpt_platform/** | Not mined here; the standing rule is Polyform Shield, never a source. |

## Gaps

- **No stdio MCP transport in dify.**
  - Searched: case-insensitive `stdio` in api/core/mcp returned no files.
  - The client only supports streamable-HTTP and SSE (mcp_client.py:62).
  - Slice 9's proof ("stub stdio server round-trip") is net-new.
  - Best sources are the MCP spec and the existing `mcp` PyPI package. That is a new dependency and needs a licence check, so the miner recommends hand-rolling newline-delimited JSON-RPC over subprocess pipes.
  - Dify's MCP types (core/mcp/types.py) are large pydantic models. Do not mirror them; use plain dicts and TypedDict.
- **No Docker engine / container-lifecycle code in dify.**
  - Searched: `docker` across api/core/*.py found nothing relevant.
  - Sandbox execution is delegated over HTTP to an external service (code_executor.py:69).
  - api/core/sandbox and api/core/virtual_environment do not exist.
  - Slice 8's source of container ingress and entrypoint patterns is openhands/docker (per the phase table), which is another miner's scope.
- **No stdout/stderr output-stream pattern for slice 8's stream.py.**
  - Dify's streaming is event-topic pub/sub, not process output.
  - The nearest transferable idea is the generator-with-idle-timeout shape (Y2, Y3).
- **No eval/benchmark/verifier runner in dify.**
  - Searched: `evaluat` in core returned only rag/entities/metadata_entities.py and mcp/types.py, which are unrelated.
  - api/core/evaluation does not exist.
  - Slice 11's source is autogpt/classic/direct_benchmark (MIT only), outside this submodule.
- **Server framework mismatch.**
  - Dify serves SSE through Flask `Response(generator, mimetype="text/event-stream")` (Y7).
  - We have no Flask dependency, so the server will need stdlib `http.server`/`socketserver` or asyncio. That is a design choice for the architect, not something dify answers.
- **Transport-agnostic MCP core.** Dify's MCP code imports Flask and httpx (mcp_client.py:9, sse_client.py), so even the shape in Y8-Y11 needs de-coupling before it is useful.
- The LICENSE copyright line reads "© 2025 LangGenius"; no check against upstream for drift was made.
