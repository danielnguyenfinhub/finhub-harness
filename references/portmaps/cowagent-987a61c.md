# Port map — cowagent

- Submodule: references/cowagent
- Pinned SHA: 987a61c (confirmed with `git rev-parse --short HEAD`)
- Licence: MIT ("Copyright (c) 2022 zhayujie", `references/cowagent/LICENSE`; licence-rules.md row `cowagent`). No NOTICE file. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: PARTIAL for the stated scope. Opened: `agent/permission/policy.py` (parts), `agent/evolution/` (trigger, config, backup, executor parts), `agent/protocol/steer.py` and `cancel.py` (heads), `agent/subagent/` (parts), `agent/workspace/session_prefs.py` (head), `agent/memory/summarizer.py` (parts), `agent/skills/archive.py` (head). Not opened: see Gaps.
- Language: all sources are Python, so "adapt" means a rewrite under `src/master_finhub/` or prose in `skills/` with the MIT attribution comment (holder zhayujie).
- Id prefix: `CW`. Row ids are sequential (CW01...). Candidate names used in CLAUDE.md are given in the notes: candidate CW1 = rows CW01-CW08, candidate CW3 = rows CW10-CW11.
- Scope: harness-factory patterns and runtime patterns.

## Already adopted (do not re-propose)

| candidate | what | where it lives now |
|---|---|---|
| CW2 | do-nothing default, change-only reporting, fix-the-source, do-not-capture list, from `agent/evolution/prompts.py` and `record.py` | `skills/finhub-harness-evolve/SKILL.md`, `tests/test_evolve_cw2.py` (CLAUDE.md row 2026-10-19) |
| (backup) | backup before editing a skill, per CLAUDE.md row 2026-10-19 "already in `finhub-harness-evolve`" | `skills/finhub-harness-evolve/SKILL.md`; rows CW15-CW16 add only the restore-side checks |

## Findings

### (a) Runtime

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| CW01 | 3 | Three session modes (read-only, workspace-write, full-access); one pure function decides each tool call | references/cowagent/agent/permission/policy.py:39 (modes), :595 (`check_tool_call`) | adapt | Candidate CW1. Default full-access there; ours should pick deliberately. |
| CW02 | 3 | Mode pinned per session, otherwise follows the global setting; absent field means follow global | references/cowagent/agent/workspace/session_prefs.py:13 (store shape), :45 (`_FIELDS`) | adapt | JSON file; atomic write helper not opened. |
| CW03 | 3 | Read-only shell: command allowlist, unknown name refused, unparseable command refused, redirects to files refused | references/cowagent/agent/permission/policy.py:729 (`_check_bash_read_only`), :149 (allowlist) | adapt | Fails closed. Compare with our denylist guard in `tools/safety.py`. |
| CW04 | 9 | Unknown MCP tool judged by verb in its name (create, delete, send...) in read-only mode | references/cowagent/agent/permission/policy.py:134 (`_MUTATING_NAME_RE`), :657 | adapt | Heuristic; known tools listed at :125 to avoid false hits. |
| CW05 | 3 | Per-tool action table: only some sub-actions mutate (browser click, scheduler create) | references/cowagent/agent/permission/policy.py:115 (`_ACTION_TOOLS`), :643 | adapt | Needs our tool names mapped. |
| CW06 | 3 | Protected-file list refused even inside writable roots; resolved by realpath; destination-aware for mv/cp | references/cowagent/agent/permission/policy.py:516 (`_normalize_protected`), :530 (`_protected_operand`), :677 | adapt | Candidate CW1. Overlaps our credential denylist; ours is read-side. |
| CW07 | 3 | Refusal text written for the model: what was blocked, which mode, do not retry, route that works | references/cowagent/agent/permission/policy.py:570 (`_switch_hint`), :587 (`_deny`) | adapt | Drop the UI-location sentence; ours has no console. |
| CW08 | 7 | Sub agent inherits the parent's permission mode; a fixed blocked-tool set; nesting depth in a ContextVar | references/cowagent/agent/subagent/runner.py:131 (inherit), :22 (depth); references/cowagent/agent/subagent/templates.py:28 (`BLOCKED_TOOLS`) | adapt | Delegation must not bypass the mode. Settings at runner.py:33-37. |
| CW09 | 7 | Child gets half the parent step budget and private shallow copies of tools | references/cowagent/agent/subagent/runner.py:86 (`_private_tools`), :115 | pattern | Copy fixes shared cancel_event on tool instances. |
| CW10 | 1 | Idle trigger: fire when idle long enough AND (turns since last pass >= N OR context past 0.8 of budget) | references/cowagent/agent/evolution/trigger.py:118 (`_scan_once`), :34 (`_CONTEXT_RATIO`), :137 | adapt | Candidate CW3. Needs a daemon; chat/Cowork have none. Defaults: config.py:15-17. |
| CW11 | 1 | Run-active flag so the idle scan skips a session mid-turn | references/cowagent/agent/evolution/trigger.py:78 (`mark_run_active`), :132 | adapt | Candidate CW3. Small; prevents a review racing the live turn. |
| CW12 | 7 | Cap on concurrent background passes plus one lock per workspace so rollback cannot overwrite a commit | references/cowagent/agent/evolution/executor.py:44 (`_MAX_CONCURRENT`), :50-64 | adapt | Only matters if CW10 is built. |
| CW13 | 5 | Write transaction: snapshot bytes before first write, rollback restores, removes created files and empty parents | references/cowagent/agent/evolution/executor.py:131 (`_EvolutionWriteTransaction`), :178 (`rollback`) | adapt | Atomic multi-file edit for unattended passes; `has_changes` at :164. |
| CW14 | 3 | Evolution write guard: resolve first, deny outside workspace, bookkeeping files, built-in skills; casefolded | references/cowagent/agent/evolution/executor.py:200 (`_denied_evolution_path`), :224 | adapt | Hard guard, not prompt-based (:227). Source of CW6-style protected list. |
| CW15 | meta | Restore validates the whole manifest before writing any file; manifest paths treated as untrusted | references/cowagent/agent/evolution/backup.py:103 (`restore_backup`), :115-134 | adapt | Our evolve skill backs up but has no restore check. |
| CW16 | meta | Backup id has a retry loop on directory collision; incomplete snapshot is discarded | references/cowagent/agent/evolution/backup.py:59-75, :95-100 | adapt | Minor. Pruning (:145) rejected, see Do not port. |
| CW17 | 1 | Bounded steering inbox for a running turn; atomic close-if-empty closes the final-drain race | references/cowagent/agent/protocol/steer.py:35 (`SteerInbox`), :67 (`close_if_empty`), :111 | adapt | Statuses: accepted, inactive, ambiguous, full, closing. |
| CW18 | 1 | Cancel event polled at safe checkpoints; cancel injects an interrupted note keeping tool_use/tool_result pairs intact | references/cowagent/agent/protocol/cancel.py:18 (`AgentCancelledError`), :35 | pattern | Compare with our loop's cancel handling before porting. |
| CW19 | 2 | Memory flush dedupes by content hash; in-flight hashes claimed; recorded as flushed only after the summary lands | references/cowagent/agent/memory/summarizer.py:277-280, :299-311 | adapt | Retry-safe. md5 there; use sha256. |
| CW20 | 2 | Scheduler-injected message pairs stripped before promoting to long-term memory | references/cowagent/agent/memory/summarizer.py:289-298 | pattern | Idea: do not summarise automated noise. |

### (b) Harness-factory

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| CW21 | meta | Untrusted skill archive: refuse traversal, absolute paths, links, devices; cap entries and declared size | references/cowagent/agent/skills/archive.py:1-15, :39 (`_check_within`) | adapt | Fits any evolve or install path that unpacks a zip. |

## Do not port

| source | reason |
|---|---|
| references/cowagent/channel/**, references/cowagent/desktop/**, references/cowagent/voice/**, references/cowagent/translate/** | chat-app channels, desktop shell, voice: out of scope |
| references/cowagent/models/**, references/cowagent/bridge/** | model vendor adapters and channel bridge: not opened, out of scope |
| references/cowagent/skills/image-generation, references/cowagent/skills/knowledge-wiki | image generation and wiki product skills |
| references/cowagent/agent/evolution/executor.py:5 (`[SILENT]` sentinel) | rejected in CW2 (CLAUDE.md 2026-10-19) |
| references/cowagent/agent/evolution/backup.py:145 (`_prune_old_backups`, keep 10) | pruning rejected in CW2; deleting history is a decision for the owner |
| references/cowagent/agent/evolution/executor.py:642 (`_notify_user`), :614 (`_inject_evolution_record`) | pushes to a chat channel; no channel here |
| references/cowagent/agent/memory/summarizer.py:511 (`deep_dream`), vector and embedding backends | persona and memory tiers rejected in CW2; embedding store out of scope |

## Gaps

- Not opened: `agent/permission/policy.py` lines 195-515 and 835-982 (git read forms, path-mutating command tables, `describe_mode`); only the entry points above were read.
- Not opened: `agent/memory/conversation_store.py`, `manager.py`, `chunker.py`, `reranker.py`; `agent/workspace/project_store.py`, `service.py`; `agent/team.py`, `routing.py`, `multiagent/`; `agent/tools/`, `agent/prompt/`, `agent/knowledge/`; `agent/skills/loader.py`, `manager.py`; `tests/`.
- No token metering, SSE stream or DAG/checkpoint pattern was looked for beyond the files above; do not read this map as proof they are absent.
- CW10 and CW11 need a long-lived process. The harness factory targets chat and Cowork, which have no daemon, so CW3 fits the Python runtime only; the evolve skill would need a different cue.
- CW01 default is full-access (policy.py:47) so an unchanged install is ungated; no evidence of how strict mode is tested (tests not opened).
