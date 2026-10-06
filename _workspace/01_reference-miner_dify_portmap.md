# Port map — dify (scope: both; runtime slices 8-11 plus harness factory)

- Submodule: references/dify
- Pinned SHA: 431c1857 (`git -C references/dify rev-parse --short HEAD`, same as the prior run)
- Licence: Apache-2.0 MODIFIED (references/LICENSES.md and licence-rules.md agree; no drift). **Every row is `pattern` only. Nothing is adapted or copied.**
  - Multi-tenant use is barred without Dify's written authorisation.
  - The LOGO/copyright clause applies to `web/` only.
  - Write each unit fresh in Python with no mirrored names, structure or comments.
  - The DAG engine is the external `graphon` package, so `ExecutionLimitsLayer` and the `GraphEngineLayer` base are not in this repo. Only the wiring is visible.
- Mined: 2026-10-03 AEST (rows Y1-Y17 carried over from the 2026-10-03 09:50 run and re-checked; Y18-Y37 are new)
- Status: COMPLETE for slices 8-11 and the factory areas below. Some subsystems were not opened; see Gaps.
- Re-verification of prior rows:
  - Y1-Y4 are still correct at streaming_utils.py:13/35/40/53.
  - Y6, Y7, Y8, Y9, Y10, Y11, Y12, Y13, Y14, Y15, Y16, Y17 are unchanged on disk.
  - **Y5 was corrected.** The old cite `message_generator.py:20` is now `return topic`. The defaults `idle_timeout=300` and `ping_interval=10.0` are at `message_generator.py:27-28`.
  - Y10's `invoke_tool` is at mcp_client.py:120; `list_tools` stays at :113.
- Already adopted in this repo and not re-proposed: runtime slices 1-11 (SSE and MCP client shapes included), OH23-27 QA rules, OH31 denylist.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| Y1 | 10 | Generator yields an immediate PING first so the connection is not left pending | references/dify/api/core/app/apps/streaming_utils.py:13 | pattern | Already ported as a pattern; kept for the record |
| Y2 | 10 | Poll loop with 1s receive timeout; track last-message and last-ping times | references/dify/api/core/app/apps/streaming_utils.py:35 | pattern | Already ported; `queue.get(timeout)` in stdlib |
| Y3 | 10 | Idle timeout ends the stream; ping interval fires only while idle; any message resets both timers | references/dify/api/core/app/apps/streaming_utils.py:40 | pattern | Already ported; clocks injectable |
| Y4 | 10 | Stream ends after an event whose type is in a terminal set; non-dict events skipped | references/dify/api/core/app/apps/streaming_utils.py:53 | pattern | Already ported; terminal set also at :61 |
| Y5 | 10 | Defaults idle_timeout=300 and ping_interval=10.0 passed through to the stream generator | references/dify/api/core/app/apps/message_generator.py:27 | pattern | Line corrected from :20; defaults only |
| Y6 | 10 | Event-name StrEnum with PING="ping", ERROR, MESSAGE, MESSAGE_END | references/dify/api/core/app/entities/task_entities.py:62 | pattern | Own StrEnum |
| Y7 | 10 | Response wraps the generator with mimetype text/event-stream plus no-cache and keep-alive headers | references/dify/api/controllers/service_api/app/workflow_events.py:172 | pattern | Stdlib http.server equivalent |
| Y8 | 9 | MCPClient is a context manager that connects, initialises and cleans up via ExitStack | references/dify/api/core/mcp/mcp_client.py:20 | pattern | Already ported as a shape |
| Y9 | 9 | Transport chosen from URL path with SSE to streamable-HTTP fallback; partial connection closed first | references/dify/api/core/mcp/mcp_client.py:58 | pattern | Already ported; dify has no stdio |
| Y10 | 9 | list_tools and invoke_tool each raise if the session is uninitialised | references/dify/api/core/mcp/mcp_client.py:113 | pattern | Already ported |
| Y11 | 9 | cleanup closes the exit stack, then always resets session state in finally | references/dify/api/core/mcp/mcp_client.py:126 | pattern | Already ported |
| Y12 | 9 | MCP handshake: initialize with version and capabilities, validate the reply, then notifications/initialized | references/dify/api/core/mcp/session/client_session.py:112 | pattern | JSON-RPC method names are protocol, not Dify IP |
| Y13 | 9 | send_request waits on a per-request-id queue with a read timeout and raises on a JSON-RPC error | references/dify/api/core/mcp/session/base_session.py:199 | pattern | Already ported |
| Y14 | 9 | Background receive loop dispatches responses, requests and notifications; a None sentinel ends it | references/dify/api/core/mcp/session/base_session.py:309 | pattern | Already ported; wake waiters on EOF |
| Y15 | 9 | SSE transport: endpoint event, then message events; writer thread POSTs queued messages | references/dify/api/core/mcp/client/sse_client.py:167 | pattern | Understanding only; HTTP transport out of scope. Prior run said `reference`; normalised to `pattern` under the dify rule |
| Y16 | 8 | Code-execution-as-a-service: POST to a sandbox endpoint with split timeouts; non-200 and 503 mapped to typed errors | references/dify/api/core/helper/code_executor/code_executor.py:69 | pattern | Only the error mapping and timeout split carry over |
| Y17 | 8 | Sandbox reply has data.stdout and data.error; a parse failure raises a typed error | references/dify/api/core/helper/code_executor/code_executor.py:127 | pattern | Maps to our result type |
| Y18 | workflow-limits | Execution-limits layer attached to the graph engine with max_steps and max_time taken from config | references/dify/api/core/workflow/workflow_entry.py:178 | pattern | Layer class lives in external graphon; only wiring is visible |
| Y19 | workflow-limits | Nested-workflow depth guard: raise when call_depth exceeds a configured max | references/dify/api/core/workflow/workflow_entry.py:139 | pattern | Maps to sub-agent or nested-orchestrator depth cap |
| Y20 | workflow-limits | Limits are three named config fields: steps 500, seconds 3600, call depth 5 | references/dify/api/configs/feature/__init__.py:921 | pattern | Defaults at :921, :931, :936. Own constants; the numbers are not copied advice |
| Y21 | workflow-limits | Per-variable size cap (200 KB default) on workflow variables | references/dify/api/configs/feature/__init__.py:942 | pattern | Cite is the line after the depth field; reopen before use |
| Y22 | observability | Observability layer: one span per node on start, closed on end with status, context set so inner calls attach | references/dify/api/core/app/workflow/layers/observability.py:43 | pattern | Hooks on_node_run_start :92 and on_node_run_end :125 |
| Y23 | observability | Per-node-type parser registry with a default parser selects which span attributes to record | references/dify/api/core/app/workflow/layers/observability.py:75 | pattern | Layer is added only when OTel is enabled (workflow_entry.py:184) |
| Y24 | observability | Persistence layer maps every engine event (run start, succeed, fail, abort, pause; node start, retry, fail) to a stored execution record | references/dify/api/core/app/workflow/layers/persistence.py:83 | pattern | Event-to-record dispatch at :118; retry history at :370 |
| Y25 | observability | Pause-state layer serialises the full runtime state plus pause reasons on a pause event so a run can resume later | references/dify/api/core/app/layers/pause_state_persist_layer.py:77 | pattern | Resumption context at :39; on_event at :117. Fits checkpoint/resume |
| Y26 | observability | Suspend layer tracks whether the graph paused, exposing an is_paused flag | references/dify/api/core/app/layers/suspend_layer.py:7 | pattern | Small unit; flag at :31 |
| Y27 | observability | Layer lifecycle: on_graph_start, on_event for all events, on_graph_end(error) as an observer interface | references/dify/api/core/app/layers/pause_state_persist_layer.py:107 | pattern | Layers observe only; they never alter engine control flow |
| Y28 | tool-permissions | Tool-engine error mapping: each exception class becomes a short LLM-readable string fed back to the model | references/dify/api/core/tools/tool_engine.py:129 | pattern | Branches at :129-152; every error fires an error callback and logs |
| Y29 | tool-permissions | Surface-to-allowed-recipient allowlist: API surfaces get a narrower set than the console; unknown yields deny | references/dify/api/core/workflow/human_input_policy.py:27 | pattern | Deny-by-default check at :42; comment at :25 gives the intent |
| Y30 | tool-permissions | Permission points are named scenes in a StrEnum, each forwarded to an access-check endpoint | references/dify/api/core/rbac/entities.py:25 | pattern | Only the named-scene idea; RBAC backend is tenant-coupled |
| Y31 | tool-permissions | Moderation hook with input and output checks and an action enum (direct output or overridden) | references/dify/api/core/moderation/base.py:30 | pattern | Action enum at :10; maps to a pre/post gate, not an OH31 duplicate |
| Y32 | variable-scoping | Reserved selector namespaces ("sys", "env", "conversation", "rag") separate system, environment and conversation variables | references/dify/api/core/workflow/variable_prefixes.py:1 | pattern | Scoping by namespaced selector, not by flat dict |
| Y33 | variable-scoping | Closed enum of system variable keys, with typed getters that read from the pool by key | references/dify/api/core/workflow/system_variables.py:22 | pattern | Getters at :140-157; the keys are Dify-specific and not copied |
| Y34 | agent-strategy | Agent strategy base: public invoke delegates to abstract _invoke; get_parameters declares the strategy's inputs | references/dify/api/core/agent/strategy/base.py:10 | pattern | Template-method shape; strategies are swappable by parameter schema |
| Y35 | agent-strategy | Function-calling loop caps iterations at min(configured, 99), strips tools on the final iteration, raises if the model still wants tools | references/dify/api/core/agent/fc_agent_runner.py:122 | pattern | Strip at :150, raise at :310. Companion default max_iteration=10 at entities.py:86 |
| Y36 | evaluation-annotation | Annotation reply: look up a human-curated answer by similarity with a score threshold; a hit is recorded in a hit history | references/dify/api/core/app/features/annotation_reply/annotation_reply.py:45 | pattern | Threshold default at :45; hit record at annotation_service.py:614 |
| Y37 | evaluation-annotation | Feedback export: collect user feedback on messages and export as CSV or JSON for review | references/dify/api/services/feedback_service.py:16 | pattern | Offline review loop; export formats at :126 and :168 |

## Do not port

| source | reason |
|---|---|
| references/dify/web/** | Frontend; the LOGO/copyright condition applies and it is irrelevant here. |
| Any dify file as a copy source | Modified Apache-2.0 makes everything `pattern` only (licence-rules hard stop 2). |
| references/dify/api/core/mcp/auth/**, auth_client.py | OAuth and tenant-workspace coupling. |
| references/dify/api/core/mcp/mcp_client.py:33 (Flask header placeholder substitution) | Flask and tenant-request coupling. |
| references/dify/api/core/app/layers/timeslice_layer.py:16 (CFS plan scheduler) | Multi-tenant fair-share scheduling, the exact use the licence restricts. |
| references/dify/api/core/rbac/**, services/annotation_service.py (DB, tenant, embedding coupling) | Tenant/account model; only the ideas in Y30 and Y36 transfer. |
| references/autogpt/autogpt_platform/** | Not mined here; Polyform Shield, never a source. |

## Gaps

- **No stdio MCP transport** in dify (searched `stdio` in api/core/mcp). Already built in this repo, so no action.
- **No Docker engine or container lifecycle** in dify. The sandbox is a remote HTTP service (Y16).
- **No eval or benchmark runner and no LLM-judge panel.**
  - There is no `api/core/evaluation` directory.
  - Only the human annotation and feedback loops (Y36, Y37) exist, and both are DB-backed.
  - Judge and benchmark patterns belong to autogpt `classic/direct_benchmark` and crewai.
- **No file-level permission or command denylist** like OH31.
  - Dify's permission code is tenant RBAC (Y29, Y30) and a moderation hook (Y31).
  - Tool execution applies no per-tool allow or deny policy beyond error mapping (Y28).
- **Y21 is unverified at line level.** I read the config block around :921-:942, not the MAX_VARIABLE_SIZE field itself. Reopen it before citing.
- **Not opened this run**, so no rows:
  - `references/dify/dify-agent/src/dify_agent/layers/` (ask_human, shell, knowledge, output, user_prompt, execution_context)
  - `references/dify/dify-agent/src/shellctl/`
  - `references/dify/api/core/ops/unified_trace/` (hierarchy.py:45 `WorkflowHierarchy` seen by name only)
  - `references/dify/api/core/memory/token_buffer_memory.py`
  - `references/dify/api/core/callback_handler/`
  - `references/dify/skills/difyctl/`
  - The dify-agent layers look the most relevant to agent-strategy and hook conventions. They are worth a second pass if Daniel wants more factory rows.
- **Server framework mismatch** (Flask versus stdlib) is a design choice, already resolved by slice 10.
- The LICENSE copyright line was not checked against upstream for drift.
