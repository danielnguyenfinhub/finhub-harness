# Port map — openhands

- Submodule: references/openhands (fork of OpenHands/agent-canvas)
- Pinned SHA: a8c0558
- Licence: MIT (references/openhands/LICENSE; matches references/LICENSES.md row `openhands`, "UI-only fork"). No licence drift. No enterprise/ directory.
- Mined: 2026-10-03 AEST (re-run; prior map `_workspace_20261003_095000/01_reference-miner_openhands_portmap.md`, scope runtime slices 8-11)
- Scope: both. Runtime rows O1-O25 are kept from the prior map. Re-verified this session: 10 rows had stale or wrong line cites and are corrected below (O6, O8, O18, O19, O21, O22, O25, plus the O1/O4 line notes). O26-O36 are new harness-factory rows.
- Status: COMPLETE
- Language: the fork is TypeScript/React. Rows are ports of the idea, not syntax.

## Re-verification summary (prior rows)

- Still match on disk, unchanged: O1 (286), O2 (359), O3 (493), O4 (105/149), O5 (158), O7 (50), O9 (49), O10 (20), O11 (110), O12 (18/31), O13 (46), O14 (22), O15 (75), O16 (50), O17 (25/133), O20 (help text line 244), O23 (75/126), O24 (150).
- Corrected:
  - O6: line 163 is `esac`, so the opt-in warning is at docker/entrypoint.sh:403.
  - O8: the `--network host` note is at playwright.mock-llm-docker.config.ts:16, not 19.
  - O18: the cite is now use-websocket.ts:93 (the `canReconnect` check). Line 118 is only a comment.
  - O19: line 407 is only the `node static-server.mjs` invocation. The reserved route list is at entrypoint.sh:149, and that is the real source for route naming.
  - O21: the original description was wrong. The spec at tests/e2e/bind-policy/loopback-bind.spec.ts:58 asserts that a LAN bind strips the session key from `GET /`. `canConnect` is at line 37. The row now says this.
  - O22: the header reference is at bash-service.api.ts:36, not 33.
  - O25: the mock-LLM description is at playwright.mock-llm-docker.config.ts:2, not 3.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| O1 | 8 | Child-PID list plus `trap cleanup EXIT SIGINT SIGTERM`: kill children, wait, exit | references/openhands/docker/entrypoint.sh:286 | adapt | Maps to docker_engine teardown. The trap line itself is 294. |
| O2 | 8 | Readiness gate: poll TCP port every 1s up to max_wait, warn and return 1 on timeout | references/openhands/docker/entrypoint.sh:359 | adapt | Python `socket.create_connection` with a deadline. |
| O3 | 8 | Supervisor loop: `kill -0` the ingress PID every 10s; container exits nonzero when it dies | references/openhands/docker/entrypoint.sh:493 | adapt | Backend crash tolerated, ingress death fatal. Watchdog idea. |
| O4 | 8 | Validate path-prefix env input: normalise slashes, reject `.`/`..`, charset whitelist, reject reserved-route collision | references/openhands/docker/entrypoint.sh:105 | adapt | Reserved list at line 149. Reuse for mount and path args. |
| O5 | 8 | Port env must be numeric before it is interpolated into a proxy target URL | references/openhands/docker/entrypoint.sh:158 | adapt | Cheap fail-fast for container port args. |
| O6 | 8 | Secure-by-default exposure: session key embedded only on explicit opt-in, with a loopback-only warning | references/openhands/docker/entrypoint.sh:403 | reference | Policy shape: network and secrets opt-in, default deny. Corrected from 163. |
| O7 | 8 | Config values generated into a sourceable defaults.env at build time, so no runtime parser is needed | references/openhands/docker/Dockerfile:50 | reference | Only the no-runtime-parser idea transfers. |
| O8 | 8 | Test config uses `--network host` on Linux; `host.docker.internal` override for Docker Desktop | references/openhands/playwright.mock-llm-docker.config.ts:16 | reference | Informs the docker network flag and skip-without-docker test. Corrected from 19. |
| O9 | 8 (stream) | Paginate command output by `page_id`/`next_page_id`, hard page cap 20, ordered by timestamp | references/openhands/src/api/bash-service/bash-service.api.ts:49 | adapt | Bounded loop. Cap constant at line 18. |
| O10 | 8 (stream) | Type guard filters a mixed event stream down to bash-output events | references/openhands/src/api/bash-service/bash-service.api.ts:20 | reference | Tagged-event discriminator for stdout/stderr/exit chunks. |
| O11 | 9 | Redact secrets from MCP error text: strip config values (url userinfo, secret query params, auth values) | references/openhands/src/utils/redact-mcp-secrets.ts:110 | adapt | Min secret length 4 (line 9). Value collector at line 95. |
| O12 | 9 | Generic secret regex list (PAT, Slack, Linear, JWT shapes) plus Bearer token keeping the prefix | references/openhands/src/utils/redact-mcp-secrets.ts:18 | adapt | Compiled `re` list. Bearer pattern at line 31. |
| O13 | 9 | Map probe response to health: failed(kind), healthy verified vs connectivity-only; 401/403 text becomes credentials | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:46 | adapt | `verified` needs tool advertised AND call succeeded. |
| O14 | 9 | Auth-failure text regex used as an error-kind classifier | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:22 | adapt | Conservative classifier. |
| O15 | 9 | Non-mutating probe wrapper: begin check, call test, catch to failed, resolve | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:75 | adapt | Shape for a `health_check()` on the MCP client. |
| O16 | 9 | In-flight check ids: a result commits only if the entry is still the same `checking` id | references/openhands/src/api/mcp-health/mcp-health-store.ts:50 | adapt | Stale-probe guard. Begin at line 36. Non-persisted by design (line 10). |
| O17 | 10 | Reconnect backoff: 1s base doubling, 30s cap, up to 30% jitter, optional maxAttempts | references/openhands/src/hooks/use-websocket.ts:25 | adapt | Delay math at line 133. For the server test client. |
| O18 | 10 | Reconnect only for sockets still in the allowed set; flag cleared before close | references/openhands/src/hooks/use-websocket.ts:93 | reference | Avoids reconnect-after-close race. Corrected from 118. |
| O19 | 10 | Reserved route names (/api, /sockets, /alive, /health, /ready, /docs ...) rejected as path-prefix collisions | references/openhands/docker/entrypoint.sh:149 | reference | Informs health/ready endpoint naming only. No SSE here. |
| O20 | 10 | Default bind is loopback; non-loopback bind with embedded key refused unless an explicit LAN flag is set | references/openhands/scripts/static-server.mjs:244 | adapt | Help text. Flag at 165/257. Mutual-exclusion guard at 197. |
| O21 | 10 | Bind-policy test: on a LAN bind the session key is stripped from `GET /`; `canConnect` probes reachability | references/openhands/tests/e2e/bind-policy/loopback-bind.spec.ts:58 | adapt | `canConnect` helper at line 37. Port to a pytest socket test. |
| O22 | 10 | Session auth header `X-Session-API-Key` between client and runtime | references/openhands/src/api/bash-service/bash-service.api.ts:36 | reference | Doc comment only. Use constant-time compare in Python. |
| O23 | 10 | Paged event search with `next_page_id`; stops pagination when the server lacks timestamp filters | references/openhands/src/api/event-service/event-service.api.ts:75 | reference | Fallback comment at line 126. Cursor idea for event replay. |
| O24 | 11 | Test report renderer: summary plus per-test table (status, duration, retries) in collapsible details | references/openhands/tests/e2e/mock-llm/scripts/render-mock-llm-report.mjs:150 | reference | Result-record fields only. Collapsible `<details>` at line 220. |
| O25 | 11 | Mock-LLM e2e: deterministic fake LLM server so agent runs are reproducible | references/openhands/playwright.mock-llm-docker.config.ts:2 | reference | Matches the existing fake_llm.py design. Corrected from 3. |
| O26 | workspace-upload | Upload filename sanitiser: split on `/` and `\`, take the last segment, reject empty, `.` and `..` | references/openhands/src/api/workspace-upload-path.ts:14 | adapt | Basename-only check. Check master_finhub workspace.py (slice 3) before proposing. |
| O27 | workspace-upload | Destination built as safeName under a resolved absolute dir, with trailing slashes stripped | references/openhands/src/api/workspace-upload-path.ts:42 | adapt | Sanitise first, then resolve. Does not resolve symlinks or check containment. |
| O28 | workspace-upload | Upload size gates: 3MB per file and 3MB total including already-attached files | references/openhands/src/utils/file-validation.ts:1 | adapt | Constants at lines 1-2. `validateFiles` composes both at line 58. |
| O29 | agent-status | Closed ExecutionStatus enum: idle, running, paused, waiting_for_confirmation, finished, error, stuck | references/openhands/src/types/agent-server/core/base/common.ts:67 | adapt | `stuck` is a distinct state worth mirroring in the status vocabulary. |
| O30 | agent-status | Status predicates as frozen sets: active (idle, running, waiting, finished), paused, errored (error or stuck) | references/openhands/src/utils/status.ts:5 | adapt | Predicates at 13, 19, 25. Unknown or null status is not active. |
| O31 | agent-status | Status to indicator mapping: running, done/waiting, paused, error/stuck; null for unknown so callers omit it | references/openhands/src/utils/agent-state-emoji.ts:14 | pattern | Mapping shape only. Emoji do not belong in harness output. |
| O32 | coordinator | Child-conversation launch tool: self-contained brief, non-overlapping scopes, one call per task, corrective guidance on bad params | references/openhands/src/api/launch-child-conversation-client-tool.ts:14 | adapt | Prose is a delegation-prompt template. Child cannot see parent history. |
| O33 | coordinator | Delegation is acknowledged at once; the real outcome returns later as a prefixed follow-up message | references/openhands/src/api/launch-child-conversation-client-tool.ts:61 | pattern | Async hand-off with a result-prefix convention. The tool spec starts at line 61. |
| O34 | coordinator | AGENTS.md ownership table: which repo owns which change, with a dependency-direction rule | references/openhands/AGENTS.md:26 | adapt | Scope-before-work gate for agent teams. Also the routing table at line 51. |
| O35 | verification | Review guide: confirm scope first, then ordered checkpoints; the reviewer may only APPROVE or COMMENT, never REQUEST_CHANGES | references/openhands/.agents/skills/custom-codereview-guide.md:34 | adapt | Human owns the blocking decision. Eval-risk statement rule follows. |
| O36 | verification | `@spec ID` tags above implementation and tests, stable IDs, deprecated specs struck through | references/openhands/AGENTS.md:84 | adapt | Greppable spec-to-test traceability. Example: WUP-001 in src/api/workspace-upload-path.ts:1. |

## Do not port

| source | reason |
|---|---|
| references/openhands/src/components/**, src/routes/**, src/hooks/ (React except O17/O18 lifecycle ideas) | UI code, out of scope. |
| references/openhands/electron/** | Desktop shell. |
| references/openhands/helm/** | K8s chart. |
| references/openhands/docker/Dockerfile and entrypoint.sh bodies | Node/agent-server specific. Only the shell patterns O1-O6 transfer. |
| references/openhands/src/api/cloud/**, automation-service/** | Cloud and automation clients, not applicable. |
| references/openhands/src/utils/agent-state-emoji.ts output (emoji) | Emoji are UI chrome. Take only the status taxonomy (O29-O31). |

Nothing is licence-blocked. autogpt_platform (Polyform Shield) and dify (pattern only) are not mined in this map.

## Gaps

- Runtime gaps are unchanged from the prior map. There is no container sandbox runtime (searched: `docker run`, `docker exec`, `spawn(`), no MCP protocol client, no server-side SSE (searched: `EventSource`, `text/event-stream`, `heartbeat`), and no eval or benchmark runner. Slice 8 `stream.py`, slice 9 transport, slice 10 PING and slice 11 scoring should come from other submodules.
- Harness-factory gaps. This fork lacks all of the following, because the agent runtime lives in the external `OpenHands/software-agent-sdk`:
  - No coordinator or orchestrator prompts. The only delegation prose is the child-launch tool description (O32/O33).
  - No QA or verification rules for agents. The only reviewer rules are for human PR review (O35).
  - No permission modes or denylist engine. The only access policy is the bind and session-key policy (O6, O20).
  - No memory or compaction ledgers.
  - No hook engine. `src/api/hooks-service.ts:11` is only a client that loads `<project_dir>/.openhands/hooks.json` from the server, so it is reference-only.
  - No judge panels, multi-reviewer consensus or retrospective loop.
  - Searched: `coordinator`, `orchestrat`, `delegate`, `subagent` across src, tools, scripts, docs and specs. Hits were UI rendering of events and the child-launch tool.
- O26 to O28 overlap runtime slice 3 (`workspace-upload-path.ts` is listed there). The miner could not open `src/master_finhub/workspace.py`. The Explore tool found no such file under `/home/user/finhub-harness/src/master_finhub/` (`ls` showed `__init__.py`, `__pycache__`, `cli.py` first). The architect should diff against whatever slice 3 contains before treating them as new.
- `.agents/skills/` holds contributor skills for the Canvas frontend (telemetry, e2e, release and similar). They were not mined because they are repo-specific. `custom-codereview-guide.md` was read only to line 60.
- `scripts/static-server.mjs` proxy and WebSocket-upgrade internals remain unopened (carried over from the prior map).
- Lines were cited from `sed` and `grep` output against the pinned checkout this session.
