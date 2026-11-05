# Port map — hive

- Submodule: references/hive
- Pinned SHA: 67502fa (confirmed with `git rev-parse --short HEAD`)
- Licence: Apache-2.0 ("Copyright 2024 Aden", `references/hive/LICENSE`; licence-rules.md row `hive`). No NOTICE file. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the two purposes in scope (runtime and harness-factory). Not exhaustive: the server, credentials, browser, UI, global_db and `tools/` trees were not opened (see Gaps).
- Language: all sources are Python, so "adapt" means a rewrite under `src/master_finhub/` or prose in `skills/` with the Apache-2.0 attribution comment. Paths in the table are written in full.
- Id prefix: `HV`.
- Scope: runtime patterns and harness-factory patterns.

## Already adopted (do not re-propose)

| candidate | what | where it lives now |
|---|---|---|
| H1 | per-row unit tracker (sqlite, done column NULL until done) from `core/framework/tools/tracker_tools.py` | `skills/finhub-harness/scripts/unit_tracker.py`, `references/unit-tracker.md` (CLAUDE.md row 2026-10-18) |
| H2 | pilot-then-fan-out from `core/framework/agents/queen/nodes/__init__.py:336` | `team-patterns.md` section 1-2a, rules P1-P6 |

Open from the proposal: H3 (retry and convergence) and H4 (claim). Rows HV10-HV14 below are the evidence for them.

## Already covered by runtime slices 1-11 (do not re-propose)

Checked by grep against `src/master_finhub/`; only module docstrings and a few names were read, not full bodies.

| slice | covered in | note |
|---|---|---|
| 1 loop | `runtime/loop.py`, `runtime/repeat_reminder.py` | exact repeated-call chain reminder at counts 3/5/8; hive's `is_tool_doom_loop` (stall_detector.py:77) is the same idea |
| 2 context | `runtime/context.py` | token estimate, head/marker/tail clip, deterministic model-free summary |
| 3 safety | `tools/safety.py`, `sandbox/workspace.py` | command denylist, workspace fence |
| 5-6 | `orchestration/dag_engine.py`, `graph*.py` | checkpoint, resume |
| 7 modes | `orchestration/modes/team.py` | halt reasons include `stalled` (team.py:82) |
| 9-11 | `tools/mcp/client.py`, `server/sse.py`, `evals/` | |

## Findings

### (a) Runtime

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| HV1 | 1 | Text stall detector: stalled only if every consecutive pair of recent replies has bigram Jaccard similarity above a threshold | references/hive/core/framework/agent_loop/internals/stall_detector.py:11 (`ngram_similarity`; `is_stalled` at :33) | adapt | Complements exact-call `repeat_reminder`; catches "still stuck" rephrasings. Pure functions. |
| HV2 | 2 | Microcompact: blank old tool results by count, but only those with a recovery path on disk; otherwise leave intact | references/hive/core/framework/agent_loop/internals/compaction.py:207 | adapt | Recoverability invariant stops re-read loops. Needs HV3 spill first. |
| HV3 | 2 | Persist every non-error tool result to disk; context gets the result unchanged if small, preview plus plain-prose file reference if large | references/hive/core/framework/agent_loop/internals/tool_result_handler.py:238 | adapt | Docstring records a model copying a bracketed "[Saved to ...]" trailer. Avoid bracket trailers. |
| HV4 | 2 | On resume, recover the next spill number by scanning existing numbered spill files | references/hive/core/framework/agent_loop/internals/tool_result_handler.py:580 | adapt | Ten lines; prevents overwriting spill files after restart. |
| HV5 | 2 | Compaction pipeline: clip oversized user messages, microcompact, prune, LLM summary, emergency deterministic summary; breaker after 3 failures | references/hive/core/framework/agent_loop/internals/compaction.py:330 (`MAX_CONSECUTIVE_FAILURES` at :124) | pattern | Only matters if an LLM summariser is added; ours is model-free. Keep the staged ordering and breaker. |
| HV6 | 1 | Schema-driven coercion of model tool arguments (string to number/bool, JSON-in-string, object list to string list); unknown shapes pass through | references/hive/core/framework/agent_loop/internals/tool_input_coercer.py:51 | adapt | Conservative by design; log each coercion. Useful for haiku-tier workers. |
| HV7 | 1 | Classify an exception as transient (retry) or permanent, and separately as context-too-large | references/hive/core/framework/agent_loop/internals/tool_result_handler.py:72 (`is_context_too_large_error` at :64) | adapt | Keyword lists are string-matching on messages; brittle, keep the two-way split only. |
| HV8 | 4 | Round-robin key pool; a rate-limited key sits out for retry-after; if all cooling, pick the soonest to recover | references/hive/core/framework/llm/key_pool.py:28 | adapt | No `KeyPool` name in `src/` by grep. Thread-safe with one lock. |
| HV9 | 5 | JSONL event log that reopens its handle once after a failed write instead of dropping all later events | references/hive/core/framework/host/event_log.py:23 | adapt | Docstring names a real incident of silent loss. Small unit. |

### (b) Delegation, retry and claim (open candidates H3, H4)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| HV10 | 7 | Convergence loop: each round re-queries undone rows, dispatches one worker each, stops at max rounds or a failure-fraction breaker, then records leftover rows once | references/hive/core/framework/host/playbook/runner.py:305 | adapt | H3 core. Pairs with `unit_tracker.py pending`. Stateless, so re-run equals resume. |
| HV11 | 7 | Worker retries only lifecycle failures with optional exponential or linear backoff capped at 30 s; never retries on receipt shape | references/hive/core/framework/host/playbook/runner.py:190 (`_backoff_sleep` at :296) | adapt | H3. The "no shape retry" reason is duplicate non-idempotent sends. |
| HV12 | 7 | Dead-letter store for rows still unresolved at stop; recorded once, not once per round | references/hive/core/framework/host/playbook/runner.py:57 | adapt | H3. Ten lines. Maps to a `failed` state in the tracker plus a report line. |
| HV13 | 7 | Start-rate gate: reserve the next slot under a lock, sleep outside it, so parallel workers pace without serialising | references/hive/core/framework/host/playbook/runner.py:77 | adapt | Uses the loop's monotonic clock. Only needed when workers hit a rate-limited API. |
| HV14 | 7 | Atomic claim: one UPDATE with status guard and claim token; zero rows returned means someone else has it; never select then update | references/hive/core/framework/skills/_default_skills/colony-progress-tracker/SKILL.md:16 (generic next-pending form at :32) | adapt | H4. Writes carry a worker-id guard so a revoked claim cannot write. |
| HV15 | 7 | Claim outcomes as typed results: not found, already completed, owned by other, blocked by unfinished tasks, ok | references/hive/core/framework/tasks/store.py:806 | pattern | Typed outcomes are the useful part; its JSON-document store is not needed. |
| HV16 | 7 | Sweep marks long-idle in_progress tasks abandoned (30 min), distinct from completed; resumable | references/hive/core/framework/tasks/store.py:603 (threshold at tasks/models.py:45) | adapt | The skill text promises a stale-claim reclaimer; this is the only sweep found (see Gaps). |
| HV17 | 7 | Rule: the tracker row is truth, the worker receipt is only its claim; disagreement means re-dispatch; side effects must self-check "already done" | references/hive/core/framework/skills/_default_skills/worker-delegation/SKILL.md:139 | adapt | Prose rule for team-patterns; extends P1-P6. Also: do not fan out below about 3 units (:35). |
| HV18 | 5 | Restore returns conversation, outputs, iteration and the stall detector state together | references/hive/core/framework/agent_loop/internals/cursor_persistence.py:49 | reference | Idea: persist detector counters with the checkpoint. dag_engine already resumes. |

### (c) Harness factory

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| HV19 | judge | Three-level judge: short-circuits, custom judge with full authority, then implicit output-key check plus optional quality gate; no-feedback verdict is not logged | references/hive/core/framework/agent_loop/internals/judge_pipeline.py:42 | adapt | Layering for a generated QA agent. A RETRY must always carry feedback. |
| HV20 | judge | Subagent judge escalates wording as iterations run out: plain, WARNING, then URGENT naming the missing output keys | references/hive/core/framework/agent_loop/internals/judge_pipeline.py:15 | adapt | Cheap budget-aware retry text for workers. |
| HV21 | judge | Quality gate reads the last 10 messages and answers ACTION, CONFIDENCE, FEEDBACK lines; the judge gets about 20 percent of the main budget | references/hive/core/framework/orchestrator/conversation_judge.py:33 (parser at :181) | pattern | Parser defaults to ACCEPT on a malformed reply: fail-open. A gate here must default to RETRY. |
| HV22 | coordinator | Supervisor classifier for a parked agent: continue, needs_human or done; hard blockers decided in code first; on error default continue and flag `errored` | references/hive/core/framework/sentinel/classifier.py:218 (prompt at :117) | adapt | Rules worth keeping: user stop request overrides, blocked remainder is never "continue". |
| HV23 | coordinator | Reminder hub: advisory text injected at named points (session start, post tool, pre and post compact, stop); post-compact re-announces dropped context | references/hive/core/framework/agent_loop/reminders.py:356 (`ReminderSource` at :279; point list in docstring :1) | pattern | Maps to Claude Code hooks (PostCompact style). Do not port the async ticker. |
| HV24 | coordinator | Nudge budgets per park variant: questionless park nudged once, broken park gets full budget; counts reset on a user message | references/hive/core/framework/agent_loop/idle_nudge.py:131 (`_cap_for` at :180) | adapt | Rule for any unattended-run prompt: cap nudges per user cycle, never unbounded. |
| HV25 | verification | Default skill: classify failure transient or structural; retry once, fix input, skip and record, or escalate; never silently drop an item | references/hive/core/framework/skills/_default_skills/error-recovery/SKILL.md:10 | adapt | Own wording; fits generated worker skills. Hive's `{{max_retries_per_tool}}` is a template slot. |
| HV26 | memory | Default skill: save needed values to notes right after a tool call, because old tool results will be pruned | references/hive/core/framework/skills/_default_skills/context-preservation/SKILL.md:10 | adapt | Short; pairs with HV2 and the compaction ledger. |
| HV27 | evaluation | Strict SKILL.md validator for CI (explicit name, name equals directory, no YAML fixup, non-empty body) separate from the lenient runtime parser | references/hive/core/framework/skills/validator.py:27 | pattern | `lint_harness.py` already lints skills; compare rule list only. |
| HV28 | memory | Reflection agent rules: one storage decision per learning, update before create, skip task-specific facts, do nothing if nothing durable; periodic merge pass with size caps | references/hive/core/framework/agents/queen/reflection_agent.py:495 (housekeeping prompt at :554) | adapt | do-nothing default already adopted from cowagent (CW2). New: dedupe-across-scopes and file caps. |
| HV29 | memory | Recall selector: LLM picks up to 5 memory files from a manifest; profile-type memories back-fill free slots; any error returns empty | references/hive/core/framework/agents/queen/recall_selector.py:59 | pattern | Best-effort recall that never blocks the turn. Only if a memory store is built. |
| HV30 | token-efficiency | Eager versus searchable tool tiers: small always-loaded set, rest as one-line manifest loaded on demand; stable list object keeps the prompt cache warm | references/hive/core/framework/tools/tool_tiers.py:1 (module docstring) | pattern | Fits the light-skill token goal. Empty eager list means fail-open (all tools eager). |

## Do not port

| source | reason |
|---|---|
| references/hive/core/framework/credentials/** | Credential vault and OAuth providers; secrets handling out of scope and risky to copy. |
| references/hive/core/framework/skills/trust.py | Git-remote trust prompt (:153) is interactive CLI UX for a local app; Claude Code has its own trust model. |
| references/hive/core/framework/server/**, references/hive/core/framework/host/webhook_server.py | aiohttp web UI backend; our SSE slice exists. |
| references/hive/core/framework/tools/browser_tools.py, `.claude/skills/browser-edge-cases/**` | Browser automation; out of scope. |
| references/hive/core/framework/agents/queen/nodes/__init__.py (CRM passages from :202, :344) | Team CRM claim and promote flow tied to Hive's own CRM CLI; H2 text was already taken from :336. |
| references/hive/core/framework/host/playbook/runner.py `_namespace` (:384 area) | Runs queen-authored scripts via in-process exec with full builtins; its own comment says it is not a security boundary. |
| references/hive/tools/**, `examples/`, `templates/` | Third-party integrations and sample agents; not opened, no runtime or factory pattern needed. |

## Gaps

- No stale-claim reclaimer in code. The colony-progress-tracker skill (SKILL.md:111) says one revokes claims after 15 minutes; `grep -rn -i reclaim` over `core/framework` found only unrelated MCP thread comments. The only sweep found is HV16 (30 minutes, task store, not the sqlite tracker). If H4 is built, the reclaimer is net-new.
- No adversarial multi-reviewer panel or consensus judge. Hive's judges are single-verdict (HV19, HV21); a panel is not in this repo.
- No permission-mode or command-denylist layer comparable to `tools/safety.py`. The nearest items are skill trust (not ported) and tool gating; both are about prompts, not commands.
- No scripted mutation or eval-runner pattern; `core/framework/testing/` (llm_judge, approval_cli) was listed but not opened. Treat as unmined.
- Not opened: `core/framework/server/`, `credentials/`, `global_db/`, `loader/` (including `mcp_client.py` at about 1,000 lines, which may hold a call-result ceiling worth a later look), `observability/`, `pipeline/`, `maintenance/`, `tracker/`, `trackerdb/`, `skills/installer.py`, `skills/overrides.py`, `docs/`, `scripts/`, `tools/` and `examples/`.
- Line numbers cite the first line of the class or function (the `def`/`class` line, not its decorator). The `ReminderSource` and `ReminderHub` rows cite class lines; the list of reminder points is in the module docstring.
