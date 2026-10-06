# Port map — deepseek_harness (scope: both; runtime rows D1-D21 kept, factory rows D22-D56 added)

- Submodule: references/deepseek_harness
- Pinned SHA: b274e89 (`git -C references/deepseek_harness rev-parse --short HEAD`)
- Licence: MIT, Copyright (c) 2026 DeepSeek (LICENSE opened in the prior run). `references/LICENSES.md` was not opened, so drift against it is UNVERIFIED.
- Mined: 2026-10-03 AEST
- Status: COMPLETE for reachable patterns (the repo is TypeScript, so every row is an idea port to Python, not syntax). Specific unread areas are listed in Gaps.
- Re-verification of prior rows: D1-D21 were each checked against disk. The cited line is the first line of the cited unit, or the first line of the cited code, in every case, so all 21 rows are kept unchanged. This includes D21 at client.py:363, which is the subscriber fan-out block.
- Scope warnings:
  - I did not open `src/master_finhub/` this run. Compaction and sandbox rows may partly overlap adopted slices 2-3. Each affected row says "check overlap" or "delta only".
  - Hook, permission-prompt, skill, goal and ledger rows target the plugin (`skills/`, `.claude/`) and the runtime event ledger. They are not the same things as slices 1-11.
  - OH23-27 and OH31 are not touched.

## Findings

### Runtime rows (unchanged from the prior run, slices 8-11)

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

### Harness-factory rows (new)

Compaction strategies and state ledgers (slice column = area name)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D22 | compaction | Compaction ledger: log-only `compaction/start`, `/summary` (inputs, shadowed seqs, model, usage), `/end` sharing one compactionId; an unmatched start marks a crash | references/deepseek_harness/packages/compaction/compaction/src/types.ts:23 | adapt | Events at :23 (start), :33 (summary), :71 (end). Check overlap with the slice-2 compaction record. |
| D23 | compaction | Shadow-price event: model-free prune logs the shadowed range and token count immediately before its replacement message | references/deepseek_harness/packages/compaction/compaction/src/types.ts:81 | pattern | Pairing is contractual: the replacement is appended synchronously right after. Delta idea only. |
| D24 | compaction | Eight-section checkpoint template (intent, concepts, files, errors, pending, current work, next step, critical context); "(none)" for empty; merge any prior checkpoint | references/deepseek_harness/packages/compaction/compaction-basic/src/summarizer.ts:31 | adapt | Strongest factory find. Reusable as a skill handoff or `/compact` prompt. Rules at :60-65. |
| D25 | compaction | Checkpoint framing: preamble telling the model to treat it as established background, wrapped in `<compacted-summary>` tags | references/deepseek_harness/packages/compaction/compaction-basic/src/summarizer.ts:69 | adapt | `frameSummary` at :189. The tags at :21-22 also let the next compaction recognise a prior checkpoint. |
| D26 | compaction | Summariser fails closed: max-tokens, error and abort finishes raise; blank or image-bearing summaries rejected; directive sent LAST so the prefix cache is reused | references/deepseek_harness/packages/compaction/compaction-basic/src/summarizer.ts:121 | adapt | `finishError` at :198; empty check at :170; cache rationale at :24-30. |
| D27 | compaction | Tool-pair-balanced cuts: a cut is safe only when no tool call is unanswered; corrupt surface (result without call) throws | references/deepseek_harness/packages/compaction/compaction/src/tool-pairing.ts:117 | adapt | Incremental cache is at :15-98; one counter pass is enough for Python. `balancedAfter` at :129. |
| D28 | compaction | Range selection: walk back from the tail until the retain-token budget is met, then step back to a balanced cut; never compact the whole surface | references/deepseek_harness/packages/compaction/compaction-basic/src/region.ts:98 | adapt | Returns None when nothing is compactable. Check overlap with the slice-2 selector (delta only). |
| D29 | compaction | Compaction transaction: durable start event acts as the lock; every failure makes exactly one end attempt; failed close leaves the start detectable | references/deepseek_harness/packages/compaction/compaction-basic/src/region.ts:152 | adapt | Resume check `inspectCompactionEntryState` at :517 finds an unmatched start and the open turn. |
| D30 | compaction | Trigger policy: threshold = window*ratio, retain < threshold, prune first then re-measure, bounded retry loop; overflow bypasses threshold and retain | references/deepseek_harness/packages/compaction/compaction-basic/src/index.ts:258 | adapt | Config rules in `config.ts:133` (retainTokens < thresholdTokens) and `:67`; ratio and tokens are mutually exclusive (:240). |
| D31 | compaction | Deterministic tool-result prune: keep head and tail chars, replace the middle with a fixed marker; config rejects head+marker+tail > threshold | references/deepseek_harness/packages/compaction/compaction-tool-result-pruner/src/config.ts:36 | adapt | Defaults 8192/4096/1024 at :10. Marker at :7. `pruneContent` at index.ts:83; non-text blocks kept. |
| D32 | memory | Spill oversized plain-text tool results to a session artifact, leave a head/tail preview plus retrieval hint; spill failure never turns success into error | references/deepseek_harness/packages/spill/spill-policy/src/index.ts:111 | adapt | Rules in module doc :1-60. Skip `read` to avoid a read-spill-read loop. No `maxInlineBytes` means no-op. |
| D33 | memory | Goal ledger: durable snapshots with compare-and-set (id, revision); strict fold validates transitions; phases active, paused, blocked, complete | references/deepseek_harness/packages/goal/goal/src/fold.ts:271 | adapt | `foldGoal` at :339; types at types.ts:21. Resume is by replay with no catch-up code. A Python dataclass plus event list is enough. |
| D34 | memory | Plan mode as logged state: the last `plan/mode` event wins, and a prefix fold can answer "was it on at event N" | references/deepseek_harness/packages/plan/plan-mode/src/index.ts:129 | pattern | Same "log is the state" idea as D38. Controller at :202 not read in depth. |
| D35 | memory | Write-behind batching with a fixed deadline and an explicit flush barrier; checkpoint is awaited before a model call and before a tool body, fail-closed | references/deepseek_harness/packages/session/session-checkpoint-policy/src/index.ts:29 | adapt | `afterCheckpoint` at :29. Batching class at `session-persistence/src/write-behind.ts:22`. Python: JSONL append plus fsync before a tool side effect. |

Sandbox policy modes

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D36 | sandbox | Fail-safe default `read-only`; policy rendered into the per-request context text, telling the model to try the tool and follow the denial guidance | references/deepseek_harness/packages/sandbox/sandbox-policy/src/index.ts:38 | adapt | Default at :94. Delta only: slice 3 has the modes already. The prompt wording is the new part. |
| D37 | sandbox | Precedence: approved explicit mode, then last session-log mode, then deployment default; workspace root from the session cwd | references/deepseek_harness/packages/sandbox/sandbox-policy/src/index.ts:135 | adapt | Check overlap with the slice-3 policy before proposing. |
| D38 | sandbox | Mode override is just the last `sandbox/mode` log event; `effective = fold(events) ?? default`; delegation seeds a child with source `delegation` | references/deepseek_harness/packages/sandbox/sandbox-policy/src/session-mode.ts:52 | adapt | Writer `setSandboxMode` at :69. Resume needs no catch-up. Delta only. |

Permission prompts

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D39 | permissions | Approval policy `ask` or `never`; `never` rejects deterministically before any dispatch; no answerer available means `unavailable` (fail closed) | references/deepseek_harness/packages/interaction/user-approval/src/index.ts:94 | adapt | Never-check at :312. Outcomes `allowed-once, rejected, cancelled, unavailable` at types.ts:29. Model told not to request escalation (:100). |
| D40 | permissions | Every ask writes an `approval/asked` then `approval/decided` audit pair; asking outside an open turn throws | references/deepseek_harness/packages/interaction/user-approval/src/index.ts:257 | adapt | Pair rule at :261-274. Gives an audit trail for prompt decisions. |
| D41 | permissions | Permission preset = named bundle of (sandbox mode, approval policy); current value derived by folding knob events, `custom` when no preset matches | references/deepseek_harness/packages/interaction/permission-presets/src/index.ts:55 | adapt | Fold at :143, `custom` at :70. Switching writes both knob events (:396). |

Hooks

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D42 | hooks | Exit-code protocol: exit 2 blocks with stderr as reason, other non-zero is non-blocking, JSON parsed only on exit 0, decoder never throws | references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:59 | adapt | Constant at :11. Matches the Claude Code hook contract that finhub plugin hooks already use. |
| D43 | hooks | Legacy top-level `decision` accepts only approve or block; allow/deny/ask only via `hookSpecificOutput.permissionDecision`; mismatched `hookEventName` discards event fields | references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:97 | adapt | Top-level filter at :38. Guards against a hook accidentally issuing a deny. |
| D44 | hooks | Merge many hook outputs: deny > ask > allow, first stop is sticky, reasons of the winning rank joined, contexts accumulate in order | references/deepseek_harness/packages/hooks/hook-protocol/src/merge.ts:62 | adapt | Rank function at :35. About 30 lines of Python. |
| D45 | hooks | Matcher: pipe-separated words are literal alternatives, anything else an unanchored regex; empty or `*` matches all; invalid regex is a non-match at runtime but rejected at config load | references/deepseek_harness/packages/hooks/hook-protocol/src/matcher.ts:57 | adapt | `matcherDiagnostic` at :37 for load-time validation. |
| D46 | hooks | Hook runner: JSON payload on stdin, per-hook timeout override, infrastructure failure becomes a non-blocking outcome so a hook can never crash the turn | references/deepseek_harness/packages/hooks/hook-protocol/src/runner.ts:67 | adapt | Default 10 min at :20. Catch block at :96. |
| D47 | hooks | Durable `hook/invoked` plus `hook/result` pair per run, decision and exit code recorded, stderr trimmed to 500 chars | references/deepseek_harness/packages/hooks/hook-protocol/src/events.ts:92 | adapt | `summarizeStderr` at :64. Invoked-side helper at :75. Useful for run-feedback retrospectives. |
| D48 | hooks | Hook config loader: parse Claude Code settings JSON once at load, skip unsupported hook types with a warning, on read failure register nothing | references/deepseek_harness/packages/hooks/hooks-claude-code/src/index.ts:96 | adapt | Hook points: PreToolUse :237, Stop :271, SubagentStop :294. Parser at `config.ts:78`. |
| D49 | hooks | Advisory repeat-call detector: canonical (key-sorted) args chain, reminder at counts 3, 5, 8 (gentle then detailed), reset on a user message, never vetoes | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:162 | adapt | Observe at :189, reminder text at :63 and :70, threshold validation at :128. Counts denied calls too. |

Skill and prompt conventions, coordinator prompts

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D50 | skills | Skill file = `---` YAML frontmatter plus body; kebab-case name grammar; `disable-model-invocation` and `user-invocable` flags; legacy key spellings rejected | references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:909 | adapt | Policy parser at :992. Name regex at `skill/skill/src/index.ts:20`. Reject unknown keys loudly. |
| D51 | skills | Skill source precedence by numeric rank (project 100, project-agents 200, custom 300, user 400/500, bundled 600); lower rank wins on a name clash | references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:36 | pattern | Bundled rank at `skill/skill/src/index.ts:27`. Useful if plugin skills and project skills can collide. |
| D52 | skills | Catalog sent as a `<system-reminder>` of names and descriptions only; model must load a skill before acting; changed catalog republished as a full replacement keyed by a content digest | references/deepseek_harness/packages/skill/tool-skill/src/index.ts:254 | adapt | Update variant :279, digest :328 (JSON-quoted entries, sha256). Description cap 500 at :27. |
| D53 | coordinator | Goal-round prompt: workspace and tool results are authoritative, gather evidence before marking complete, leave goal active if work remains | references/deepseek_harness/packages/goal/goal-round-driver/src/prompt.ts:12 | adapt | Pair with the wrap-up grounding rule in `goal/tool-goal/src/wrapup.ts:17` ("report only what the session establishes"). |
| D54 | coordinator | Fresh-agent loop: each round gets only an immutable objective and a bounded structured handoff; report status continue needs nextSteps, complete needs evidence, blocked needs a blocker | references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:90 | adapt | `validateReport` at :112 (script string). Handoff size cap and round cap are enforced. Overlaps OH23-27 style rules only loosely. |
| D55 | coordinator | Delegation depth is monotone: the persisted header value can only be deepened, never lowered by runtime options; cap must be a non-negative integer | references/deepseek_harness/packages/subagent/subagent/src/depth.ts:28 | adapt | Validator at :42. Stops a resumed child from restarting at depth zero. |

Evaluation and retrospective

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D56 | evaluation | Keyless replay: harvest a real session JSONL, derive the per-call model chunk script from it, patch single calls via a sidecar, fill `{{fromRequest:regex}}` placeholders from the live request | references/deepseek_harness/packages/test-support/llm-replay/src/index.ts:239 | adapt | Patches at :304, placeholder resolver :348, multi-session binding by first-call order at :549. Fails loud on mismatch. |
| D57 | retrospective | Agent Notes convention: design notes filed by lifecycle (proposed, implemented, rejected) and class; implemented notes kept current; no central index; archive rule for low-value notes | references/deepseek_harness/.agents/notes/README.md:1 | pattern | Process convention only. Fits the retrospective loop in `finhub-harness-evolve`. The archive skill is at `.agents/skills/dsh-archive-agent-notes`. |

## Do not port

| source | reason |
|---|---|
| references/deepseek_harness/packages/sandbox/sandbox-windows-acl/** | Windows ACL/FFI sandbox; target is Linux and Docker. |
| references/deepseek_harness/packages/e2b/** (except the output buffer, D3/D4) | E2B cloud sandbox with a base64 transport; third-party service, no Docker. |
| references/deepseek_harness/packages/mcp/mcp-client/src/tools.ts:363-559 | MCP image-to-attachment projection; YAGNI. |
| references/deepseek_harness/packages/client/**, apps/web/**, website/** | UI and docs site; out of scope. |
| references/deepseek_harness/packages/hooks/hooks-codex/** | Codex hook dialect; finhub targets the Claude Code dialect only (D42-D48). |
| references/deepseek_harness/packages/session/session-persistence-sqlite/**, session-persistence-jsonl/src/zstd*.ts | Storage backends and compression; the runtime ledger only needs plain JSONL. |
| references/deepseek_harness/vendor/** | Vendored third-party Cordis source; licence not checked. |
| references/autogpt/autogpt_platform/** | Not mined here. Polyform Shield; any evaluation-scoring evidence must come from `autogpt/classic/direct_benchmark/` only. |

## Gaps

- **Slice 8 (Docker):** deepseek has no Docker engine (searched `docker` and `container` in the prior run). `docker run` flag design is net-new. `references/openhands/docker/` was not opened.
- **Slice 8 (output stream):** D2-D4 are only a tail buffer, not a line-by-line stream abstraction.
- **Slice 10 (server SSE):** no server-side SSE emitter and no heartbeat code in deepseek. The PING/idle pattern lives in dify `api/core/app/apps/streaming_utils.py` (pattern only), not opened.
- **Slice 11 (eval runner):** deepseek has no benchmark runner; `BENCHMARK.md` is two lines pointing at a Python SDK example. D56 is replay for snapshot tests, not scoring.
- **D6:** only the `graceMs` guard at spawn.ts:326-329 was read; the SIGTERM-to-SIGKILL timer body is UNVERIFIED.
- **Judge panels and multi-reviewer consensus:** none found in the areas opened. Searched package names and READMEs for `guard`, `plan`, `goal`, `workflow`, `subagent`. D53/D54 are the nearest, and neither is a panel.
- **Not opened (UNVERIFIED, listed so the scout does not assume absence):**
  - `packages/test-support/llm-mock-server` and `agent-loop-testkit`.
  - `packages/guard/timeout-policy` (only exports listed).
  - `packages/credentials/authorization`.
  - `packages/self-modification`.
  - `.agents/skills/*` (only the directory list was read).
  - `docs/` (the architecture and postmortem content).
  - `session-title*` and `session-stats`.
- **Overlap with adopted work:** `src/master_finhub/` was not read in this run, so D22, D23, D27, D28, D30, D36-D38 may duplicate slices 2-3. D24, D25, D26, D29, D32, D33, D35, D39-D57 target things the prior notes do not list as adopted, but that is also unchecked on disk.
- **TypeScript to Python:** the repo uses a cordis plugin and event-bus framework. Rows describe the idea; Python needs only an append-only event list, pure fold functions and plain dataclasses.
