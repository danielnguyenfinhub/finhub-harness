# Port map — openharness

- Submodule: references/openharness
- Pinned SHA: 9b2efd7 (`git -C references/openharness rev-parse --short HEAD`)
- Licence: MIT ("Copyright (c) 2025 OpenHarness Contributors", `references/openharness/LICENSE`; licence-rules.md row `openharness`). Upstream org unverified per that row; pin is a fork under danielnguyenfinhub.
- Mined: 2026-10-03 (re-run; prior map `references/portmaps/openharness-9b2efd7.md`, 40 rows)
- Status: COMPLETE for scope `both`. Rows OH1-OH40 kept and re-checked. OH41-OH64 added from the previously unopened packages.
- Language: all sources are Python, so "adapt" means a rewrite under `src/master_finhub/` or a prose rule in the plugin, with the MIT comment `# adapted from references/openharness/<path>:<line> (MIT)`.
- Id prefix: `OH`. Source paths below are shortened to `src/openharness/...` relative to `references/openharness/`. Prefix each with `references/openharness/` when citing.
- Re-verification: I re-read the cited line of every OH1-OH40 source (def, class and heading lines). All still match on disk at 9b2efd7. One correction: for OH12, `tasks/types.py:11` is the `TaskStatus` literal, and the `TaskRecord` dataclass sits below it. No other row changed.

## Already-present in this repo (do not re-propose)

| ids | where it lives | note |
|---|---|---|
| OH23, OH24, OH25, OH26, OH27 | QA verification rules, adopted in the prior run | Already-present |
| OH31 | sensitive-path denylist, adopted in the prior run | Already-present |
| slices 1-11 | `src/master_finhub/runtime/loop.py`, `runtime/context.py`, `tools/safety.py`, `sandbox/*`, `orchestration/*`, `tools/mcp/client.py`, `server/*`, `evals/*` | Overlap map from the prior run stands. `runtime/loop.py` defines `CheckpointHook` only. There is no pre/post tool-hook layer (see OH41). `sandbox/stream.py` already strips secret-looking env names (`SENSITIVE_ENV` at :22). No content-level secret scan exists (see OH51). |

## Findings

### (a) Orchestration and execution modes

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH1 | meta | Coordinator prompt rules: parallelise research, serialise writes per file set, never fabricate worker results, never thank notifications | src/openharness/coordinator/coordinator_mode.py:252 (`get_coordinator_system_prompt`; Concurrency at :363) | adapt | Prose only. Feeds orchestrator templates and the chat fallback. |
| OH2 | meta | "Always synthesize": restate findings as a self-contained spec with paths and lines; never write "based on your findings" | src/openharness/coordinator/coordinator_mode.py:407 | adapt | Strong rule for delegation prompts in Mode C and the Authority List. |
| OH3 | meta | Continue-vs-spawn heuristic by context overlap; a failed worker is continued with its error context | src/openharness/coordinator/coordinator_mode.py:432 (failures at :381) | adapt | Maps to the existing Mode B vs C decision. Adds the overlap criterion. |
| OH4 | 7 | Worker results delivered as an XML task-notification envelope: task-id, status, summary, result, usage | src/openharness/coordinator/coordinator_mode.py:109 (`format_task_notification`; dataclass :80) | adapt | Result-envelope format only. The slice 7 bus already exists. |
| OH5 | meta | Workers get a shared scratchpad directory with no permission prompts, for durable cross-worker notes | src/openharness/coordinator/coordinator_mode.py:221 (`get_coordinator_user_context`) | adapt | Already used in Claude Code here. Document as a `_workspace` standard. |
| OH6 | 7 | Agent definition fields: `disallowed_tools`, `permission_mode`, `max_turns`, `background`, `isolation`, `critical_system_reminder`, memory scope | src/openharness/coordinator/agent_definitions.py:60 (`AgentDefinition`; `ISOLATION_MODES` :51) | adapt | Field set for agent-file frontmatter. Slice 7 `Persona` is thinner. |
| OH7 | meta | Built-in definitions: Explore and Plan read-only via `disallowed_tools`; `worker`; `verification` background-only | src/openharness/coordinator/agent_definitions.py:556 (Explore), :575 (Plan), :590 (worker), :602 (verification) | adapt | Template for the read-only reviewer default in SKILL Step 3. |
| OH8 | meta | Agent markdown loader accepts camelCase and snake_case frontmatter, validates `maxTurns`, filters agents by required MCP servers | src/openharness/coordinator/agent_definitions.py:695 (`load_agents_dir`; `has_required_mcp_servers` :956) | adapt | The MCP-requirement filter fits Cowork, where connectors vary. |
| OH9 | 7 | Per-teammate abort controller with cooperative cancel and force flag; mailbox drained at turn boundaries | src/openharness/swarm/in_process.py:52 (`TeammateAbortController`; `_drain_mailbox` :295) | reference | Slice 7 already has limits and a bus. Compare cancel semantics only. |
| OH10 | 7 | Leader-approves-worker permission flow: pending and resolved request files, polling for response | src/openharness/swarm/permission_sync.py:102 (`SwarmPermissionRequest`; `handle_permission_request` :1082) | reference | Now opened: see OH45-OH47 for the usable units. |
| OH11 | 8 | Git-worktree isolation per agent: slug validation (64 chars, no `.` or `..`), create-or-resume, stale cleanup | src/openharness/swarm/worktree.py:21 (`validate_worktree_slug`; `WorktreeManager` :135; `create_worktree` :150) | adapt | The slug validator is a small, safe unit. |
| OH12 | 7 | Background task record: types local_bash / local_agent / in_process_teammate; status pending to killed; output file; listeners | src/openharness/tasks/types.py:11 (`TaskStatus`; record below it; manager at tasks/manager.py:49) | reference | Task board (slice 7) overlaps. Line :11 corrected to the status literal. |
| OH13 | meta | Autopilot repo-task-card loop: queued cards, bounded attempts, worktree per card, journal, active-context file | src/openharness/autopilot/service.py:644 (`run_card`; store :226; `rebuild_active_context` :405) | reference | Now opened: see OH58-OH62. Still GitHub-coupled. |

### (b) Skill and plugin structure

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH14 | meta | SKILL.md frontmatter via `yaml.safe_load`; fallback to `# heading` and first paragraph; fallback description | src/openharness/skills/_frontmatter.py:34 (`parse_skill_metadata`) | adapt | Fallback chain for a skill linter. |
| OH15 | meta | Project skill discovery walks cwd up to git root, least-specific first so later entries override | src/openharness/skills/loader.py:83 (`discover_project_skill_dirs`) | adapt | Override precedence rule. |
| OH16 | meta | Skill registry: name-keyed register/get/list, later registration overrides | src/openharness/skills/registry.py:8 (`SkillRegistry`) | pattern | 29 lines. Trivial. |
| OH17 | meta | Plugin manifest: name, version, `skills_dir`, `hooks_file`, `mcp_file`, `commands`, `agents`, `enabled_by_default`; also reads `.claude-plugin/plugin.json` | src/openharness/plugins/schemas.py:8 (`PluginManifest`; loader plugins/loader.py:126) | adapt | Field list to check against `.claude-plugin/plugin.json`. See OH42 for `tools_dir`. |
| OH18 | meta | Plugin loader bundles skills, commands, agents, hooks and MCP; commands namespaced by plugin name | src/openharness/plugins/loader.py:234 (`_command_name_from_file`; `_load_plugin_agents` :479) | reference | Now opened: see OH42-OH44. |
| OH19 | meta | Bundled skill set: commit, debug, diagnose, plan, review, simplify, skill-creator, test | src/openharness/skills/bundled/content/skill-creator.md:1 | reference | `skill-creator.md` is OpenHarness-specific on paths. |
| OH20 | meta | `diagnose` skill: failure localised by layer (routing, execution, verification, governance) from run artefacts | src/openharness/skills/bundled/content/diagnose.md:1 | adapt | Fits `finhub-harness-evolve` retrospectives. |
| OH21 | meta | Hook event set: session_start/end, pre/post_compact, pre/post_tool_use, user_prompt_submit, notification, stop, subagent_stop | src/openharness/hooks/events.py:8 (`HookEvent`; schemas hooks/schemas.py:10) | reference | Superseded by OH41 (executor now opened). |
| OH22 | meta | Hook policy: per-hook timeout 1-600, `block_on_failure` (False for command, True for prompt), `priority` | src/openharness/hooks/schemas.py:22 (`PromptHookDefinition`; command variant :10) | pattern | Now confirmed from the schema bodies. See OH41. |

### (c) Verification, QA and eval

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH23 | meta | Verification-specialist prompt: try to break, not confirm; PASS without command output rejected | src/openharness/coordinator/agent_definitions.py:251 (`_VERIFICATION_SYSTEM_PROMPT`) | Already-present | Adopted in the prior run. |
| OH24 | meta | Mandatory per-check block (Command / Output / Result); at least one adversarial probe before PASS | src/openharness/coordinator/agent_definitions.py:251 | Already-present | Adopted. |
| OH25 | meta | Rationalisation list and "before FAIL" check | src/openharness/coordinator/agent_definitions.py:251 | Already-present | Adopted. |
| OH26 | meta | `critical_system_reminder` re-injected every turn for the verifier | src/openharness/coordinator/agent_definitions.py:357 (`_VERIFICATION_CRITICAL_REMINDER`) | Already-present | Adopted. |
| OH27 | meta | Verification strategy table by change type | src/openharness/coordinator/agent_definitions.py:251 | Already-present | Adopted. |
| OH28 | 11 | Verification policy as data: argv with no shell by default; metacharacters are an error unless `shell: true`; policy errors fail the step | src/openharness/autopilot/service.py:155 (`_parse_verification_entry`; run :2094) | adapt | Tests at tests/test_autopilot/test_verification.py:19-82 pin the behaviour. Slice 11 has no command-gate layer. |
| OH29 | 11 | Repair loop: attempts bounded (3), failure stage and prior summary fed into the next prompt, "smallest patch" | src/openharness/autopilot/service.py:1595 (`_prepare_repair_prompt`; defaults :53) | adapt | Matches "one builder retry" in quality-gates. |
| OH30 | meta | Human gate defaults on; auto-merge only with explicit label; merge and release need a human; auto-revert off | src/openharness/autopilot/service.py:60 (`default_human_gate`; release defaults :110) | pattern | Policy defaults, not mechanism. See OH60. |

### (d) Sandboxing and tool safety

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH31 | 3 | Built-in sensitive-path denylist checked first, not overridable by mode or allow-list | src/openharness/permissions/checker.py:75 (`PermissionChecker.evaluate`) | Already-present | Adopted in the prior run. |
| OH32 | 3 | Evaluation order: sensitive path, denied tools, allowed tools, path rules, command deny, mode | src/openharness/permissions/checker.py:75 (modes at permissions/modes.py:8) | adapt | Plan mode (block all mutating tools) is a ready-made dry-run switch. |
| OH33 | 3 | `validate_sandbox_path`: resolve then `relative_to` cwd with extra roots | src/openharness/sandbox/path_validator.py:8 | reference | Same as the existing workspace fence. |
| OH34 | 8 | Docker run argv: `--network none`; fail closed if domain policy is unenforceable | src/openharness/sandbox/docker_backend.py:82 (`_build_run_argv`) | reference | One idea worth a test. |
| OH35 | 8 | `fail_if_unavailable`: raise instead of running unsandboxed when the runtime is missing | src/openharness/sandbox/adapter.py:105 (`wrap_command_for_sandbox`; `SandboxUnavailableError` :17) | adapt | Check slice 8 has an explicit refuse-if-unavailable test. |
| OH36 | 2 | Large tool output offloaded to a file; inline gets a preview plus size and path | src/openharness/engine/query.py:524 (`_offload_tool_output_if_needed`) | adapt | Slice 2 clips and does not save the full output. Thresholds are in OH55. |

### (e) Chat / Cowork fallback

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH37 | 2 | Microcompact: replace old tool results with a cleared marker, keep the most recent N, no LLM call | src/openharness/services/compact/__init__.py:808 (`microcompact_messages`; marker :52) | adapt | Cheap first pass before summary compaction. |
| OH38 | 2 | Compaction split never cuts a tool_use / tool_result pair | src/openharness/services/compact/__init__.py:483 (`_split_preserving_tool_pairs`; `_boundary_crosses_tool_pair` :471) | adapt | Confirm `runtime/context.py` preserves pairs on the cut. |
| OH39 | 2 | Post-compaction attachments: task focus, recent files, plan, skills, verified work | src/openharness/services/compact/__init__.py:566 (`create_task_focus_attachment_if_needed`; verified work :619) | pattern | Fully read this run. See OH53, OH54 for the ledger fields. |
| OH40 | meta | Single-context fallback: OH1/OH2 become a restate-as-spec step, OH23-OH26 a role switch, OH37 a rolling "cleared" summary | coordinator/coordinator_mode.py:407, coordinator/agent_definitions.py:251, services/compact/__init__.py:808 | adapt | Synthesis row. Cite the three underlying rows. |

### (f) NEW: hooks (opened this run)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH41 | hooks | Four hook kinds (command, prompt, http, agent) as a pydantic union; shared fields `timeout_seconds` (1-600), `matcher` (fnmatch), `block_on_failure`, `priority` (higher first, ties keep registration order) | src/openharness/hooks/schemas.py:10 (union at :60; Command :10, Prompt :22, Http :36, Agent :50) | adapt | Defaults differ by kind: command and http do not block, prompt and agent do. Agent timeout is 60. |
| OH42 | hooks | `HookExecutor.execute`: run matching hooks in order, aggregate; `AggregatedHookResult.blocked` is true if any hook blocked, and `reason` is the first blocking reason | src/openharness/hooks/executor.py:64 (`execute`); src/openharness/hooks/types.py:21 (`AggregatedHookResult`) | adapt | Fail-closed hook layer for `runtime/loop.py`, which has only a checkpoint hook. |
| OH43 | hooks | Command hook: payload passed via env var and `$ARGUMENTS` shell-quoted; timeout kills the process; a missing sandbox counts as failure and blocks if `block_on_failure` | src/openharness/hooks/executor.py:80 (`_run_command_hook`; `_inject_arguments` :223) | adapt | Quoting plus kill-on-timeout are the safe parts. |
| OH44 | hooks | Prompt and agent hooks: a model returns strict `{"ok": bool, "reason"}`; the parser falls back to a plain "ok/true/yes" and treats anything else as a rejection | src/openharness/hooks/executor.py:169 (`_run_prompt_like_hook`; `_parse_hook_json` :232) | adapt | Fail-closed parse of a judge reply. Reusable for review panels. |
| OH45 | hooks | Pre-tool hook can block a tool call with a reason that is returned as the tool result; a post-tool hook receives the result | src/openharness/engine/query.py:895 (pre, block at :901); :1009 (post) | adapt | Call-site shape for a slice-1 hook seam. |
| OH46 | hooks | Settings and plugin hooks are merged into one registry; unknown events are skipped, disabled plugins skipped; a settings-file mtime check hot-reloads | src/openharness/hooks/loader.py:48 (`load_hook_registry`); src/openharness/hooks/hot_reload.py:11 (`HookReloader`) | pattern | Hot reload is best-effort mtime polling. Low value for a one-shot run. |

### (g) NEW: plugin loading

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH47 | plugins | Manifest lookup in `plugin.json` or `.claude-plugin/plugin.json`; discovery from user dir, project dir and extra roots, de-duplicated and sorted | src/openharness/plugins/loader.py:50 (`_find_manifest`; `discover_plugin_paths` :61) | adapt | Same dual-location rule as Step 0 manifest checks. |
| OH48 | plugins | Project-local plugins are off by default (`allow_project_plugins`); a warning names the directory when one is found and ignored | src/openharness/plugins/loader.py:81 (`discover_plugin_paths_for_settings`; warning in `load_plugins` :107) | adapt | Trust-boundary default. Opt-in per workspace. |
| OH49 | plugins | `load_plugin` order: manifest validate, `enabled_plugins` override or `enabled_by_default`, then skills, commands, agents, hooks, MCP; tools loaded only when enabled; a bad manifest returns None | src/openharness/plugins/loader.py:126 (`load_plugin`) | adapt | Python tools only load for enabled plugins. Check order for a plugin linter. |
| OH50 | plugins | Skill loading accepts a single `SKILL.md` or one subdirectory per skill; `command_name` is the directory name and display name is shown only if different | src/openharness/plugins/loader.py:251 (`_load_plugin_skills`) | adapt | Matches the Claude Code layout. |
| OH51 | plugins | Hooks file fallback: flat `hooks.json`, else `hooks/hooks.json` in the structured `{matcher, hooks[]}` form, with `${CLAUDE_PLUGIN_ROOT}` substituted | src/openharness/plugins/loader.py:649 (`_load_plugin_hooks_structured`; flat form :621) | adapt | Accepts Claude Code hook JSON as is. |
| OH52 | plugins | Install and uninstall guard: a plugin name must equal its own basename, and the resolved path must be a direct child of the plugins dir | src/openharness/plugins/installer.py:10 (`_resolve_user_plugin_dir`) | adapt | Small, safe traversal check. Note `install_plugin_from_path` at :20 deletes any existing destination first. |

### (h) NEW: memory and compaction ledgers

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH53 | memory | Compaction attachments carry state across a reset: task focus (goal, recent goals, artifacts, verified state, next step), recent verified work, invoked skills, async agent state, plan-mode flag; capped counts per kind | src/openharness/services/compact/__init__.py:566 (focus), :619 (verified work), :635 (plan), :654 (skills), :670 (async agents), :686 (work log) | pattern | Gives the field list for a `_workspace` state ledger. Caps are 3 to 8 entries per kind. |
| OH54 | memory | Plan-mode attachment re-injects "do not execute mutating tools until the user exits plan mode" after a compaction | src/openharness/services/compact/__init__.py:635 (`create_plan_attachment_if_needed`) | adapt | Pairs with OH32. A mode flag must survive a reset. |
| OH55 | memory | Compaction prompt: a no-tools preamble and trailer, an `<analysis>` scratchpad, then a nine-section `<summary>`; `format_compact_summary` strips the analysis | src/openharness/services/compact/__init__.py:964 (`NO_TOOLS_PREAMBLE`; `BASE_COMPACT_PROMPT` :974; `format_compact_summary` :1010) | adapt | The section list is a ready checklist for a hand-written chat summary. Includes "All User Messages" and "Pending Tasks". |
| OH56 | memory | Deterministic session-memory compaction before the LLM one: summarise old messages without a model call and return None if the result is not smaller | src/openharness/services/compact/__init__.py:915 (`try_session_memory_compaction`) | adapt | Tiering: microcompact, then deterministic, then LLM. |
| OH57 | memory | Autocompact circuit breaker: after 3 consecutive failures, stop trying; threshold is window minus a 13k buffer | src/openharness/services/compact/__init__.py:1052 (`AutoCompactState`); :1095 (`should_autocompact`; constants :55-57) | adapt | Slice 2 should have a failure cap too. Check `runtime/context.py`. |
| OH58 | memory | Compaction checkpoints appended to a metadata list (checkpoint name, trigger, message and token counts), sanitised before persisting | src/openharness/services/compact/__init__.py:187 (`_record_compact_checkpoint`) | pattern | Audit trail of what each compaction dropped. |
| OH59 | memory | Tool-output budget constants: inline limit 16,000 chars, preview 3,000, microcompact threshold 4,000; MCP results are always eligible for clearing | src/openharness/services/tool_outputs.py:9 (constants); :46 (`is_microcompactable_tool_result`) | adapt | Numbers for OH36 and OH37. Env-overridable with a floor. |
| OH60 | memory | Memory entry schema v1: frontmatter with id, type (user/feedback/project/reference), scope, importance, signature, ttl_days, disabled, supersedes, tags | src/openharness/memory/schema.py:35 (`FRONTMATTER_FIELDS`; types :20) | pattern | Field set for a file-based ledger. FinHub memory itself stays external (Zep, Supermemory). |
| OH61 | memory | Dedup by content signature (SHA-256 of normalised text plus type and category); a duplicate refreshes the existing file instead of adding one | src/openharness/memory/schema.py:94 (`normalize_memory_content`; `compute_memory_signature` :103); src/openharness/memory/manager.py:37 (`add_memory_entry`) | adapt | Write is under a file lock plus atomic replace. |
| OH62 | memory | `MEMORY.md` index is bounded to 200 lines and 25,000 bytes; truncation appends a warning to keep index entries to one line | src/openharness/memory/schema.py:137 (`truncate_entrypoint_content`; limits :31-33); src/openharness/memory/memdir.py:15 | adapt | Good rule for any index file loaded into context. |
| OH63 | memory | Staleness: memories older than 1 day get a "verify against current state" warning; a TTL hides expired entries; unused low-importance entries older than 60 days are prune candidates | src/openharness/memory/schema.py:192 (`memory_freshness_text`); :283 (`is_memory_expired`); src/openharness/memory/usage.py:107 (`find_stale_memory_candidates`) | adapt | Fits the `evolve` retrospective. A recalled fact is treated as a point-in-time claim. |
| OH64 | memory | Relevance pick: token overlap, metadata matches weighted 2x, plus importance, a use-count cap and a recency boost; an optional model reranker is applied to the shortlist | src/openharness/memory/search.py:15 (`find_relevant_memories`); src/openharness/memory/relevance.py:37 (`select_relevant_memories`) | pattern | Heuristic only; can be done without embeddings. |
| OH65 | memory | Secret scan before a shared write: regex rules (private key, AWS, GitHub, OpenAI, Anthropic, generic assignment) return labels only, never the match | src/openharness/memory/team.py:24 (`SECRET_RULES`; `check_team_memory_secrets` :80) | adapt | Net-new for FinHub: the repo only strips env names (`sandbox/stream.py:22`). Add Mercury, Twilio and Xero token shapes. |
| OH66 | memory | Team vault write-path check: resolve, require under the vault, then check the deepest existing parent for a symlink escape | src/openharness/memory/team.py:51 (`validate_team_memory_write_path`) | adapt | Covers symlink escape of a not-yet-existing file. Check against the workspace fence. |
| OH67 | memory | Per-agent memory directory with a sanitised agent type and a snapshot seed that never overwrites an existing file unless `replace` | src/openharness/memory/agent.py:19 (`sanitize_agent_type`); :59 (`initialize_agent_memory_from_snapshot`) | pattern | Maps to per-agent notes in `_workspace`. |
| OH68 | memory | "Dream" consolidation prompt: evidence discipline, classify every fact (preference, project, recent snapshot, sensitive, reminder), snapshots dated with `Last observed`, at most 2 new files, never copy secrets | src/openharness/services/autodream/prompt.py:12 (`build_consolidation_prompt`) | adapt | Retrospective prompt for `finhub-harness-evolve`. Preview mode only proposes a patch. |
| OH69 | memory | Dream safety: one-holder lock with a stale timeout and pid liveness check, timestamped backup before a run, and diff plus restore | src/openharness/services/autodream/lock.py:52 (`try_acquire_consolidation_lock`); src/openharness/services/autodream/backup.py:27 (`create_memory_backup`; `restore_memory_backup` :91) | pattern | Backup-before-rewrite rule for anything that edits memory files unattended. |

### (i) NEW: permission sync

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH70 | permissions | Worker permission request record: id, worker, tool, tool_use_id, description, input, suggestions, status pending/approved/rejected, resolved_by, feedback, optional `updated_input` | src/openharness/swarm/permission_sync.py:102 (`SwarmPermissionRequest`) | pattern | Field list for a human-gate request. `updated_input` lets the approver edit the call. |
| OH71 | permissions | Resolution is atomic: lock, read pending, write resolved to a tmp file, `os.replace`, delete pending; returns False if already gone | src/openharness/swarm/permission_sync.py:493 (`_sync_resolve_permission`) | adapt | Double-resolve safe. File-based so it survives a restart. |
| OH72 | permissions | Leader handler: read-only tools auto-approve without the checker; every other tool goes through `PermissionChecker.evaluate` with path and command; the denial reason becomes feedback | src/openharness/swarm/permission_sync.py:1082 (`handle_permission_request`; `_READ_ONLY_TOOLS` :76) | adapt | Read-only allowlist plus checker is the whole policy. Reuses OH32. |
| OH73 | permissions | Worker side polls the resolved file and converts it to a simple approved/denied response; responses are deleted after reading and old ones cleaned up | src/openharness/swarm/permission_sync.py:653 (`poll_for_response`; `cleanup_old_resolutions` :597) | reference | Polling design. Slice 7 uses in-process queues, so this is not needed there. |

### (j) NEW: autopilot

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH74 | autopilot | Task card lifecycle: queued, accepted, preparing, running, verifying, pr_open, waiting_ci, repairing, completed, merged, failed, rejected, superseded | src/openharness/autopilot/types.py:9 (`RepoTaskStatus`; `RepoTaskCard` :34) | pattern | Status vocabulary for a backlog item. FinHub uses pick, design, judge, build, QA. |
| OH75 | autopilot | De-dupe by source ref or content fingerprint (sha1, first 16 hex); additive scoring with recorded reasons (bug label, urgent, draft penalty, freshness) | src/openharness/autopilot/service.py:1923 (`_build_fingerprint`; `_score_card` :1935; base scores :43) | pattern | Reasons list makes a score auditable. Complements the capability-triage score. |
| OH76 | autopilot | `pick_next_card`: queued only, sorted by score, then recency, then title | src/openharness/autopilot/service.py:334 | pattern | Deterministic tie-break. |
| OH77 | autopilot | Every status change appends to a journal and rebuilds an active-context file: focus, in progress, next up, recently completed, recent failures, last 8 journal lines, policy paths | src/openharness/autopilot/service.py:340 (`update_status`); :381 (`append_journal`); :405 (`rebuild_active_context`) | adapt | Concrete layout for a `_workspace` state ledger that survives a reset. Pairs with OH53. |
| OH78 | autopilot | `tick` guard: scan, skip if any card is active, idle if nothing queued, otherwise run exactly one card | src/openharness/autopilot/service.py:1152 (`tick`) | pattern | One-at-a-time rule matches "one item at a time". |
| OH79 | autopilot | Execution prompt: smallest coherent change, run verification before stopping, no merge or release, summarise what changed, what was verified and remaining risk | src/openharness/autopilot/service.py:2013 (`_build_execution_prompt`) | adapt | Three-part output contract is a good builder hand-back format. |
| OH80 | autopilot | Auto-merge gate: draft is never eligible; modes `pr_only`, `label_gated` (default), `fully_auto`; defaults require a human for merge and release and keep auto-revert off | src/openharness/autopilot/service.py:1574 (`_automerge_eligible`); defaults :53, :110 | pattern | Policy shape only. Extends OH30. |
| OH81 | autopilot | Policy files in three YAML parts (autopilot, verification, release) with defaults; a failing policy read falls back to defaults | src/openharness/autopilot/service.py:492 (`load_policies`; `_read_yaml` :2002) | pattern | Policy-as-data, same idea as OH28. |
| OH82 | autopilot | Default cron install: scan every 30 minutes, tick every 2 hours | src/openharness/autopilot/service.py:1174 (`install_default_cron`) | reference | Scheduling is handled by Claude Code routines here. |

### (k) NEW: bridge

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH83 | bridge | Child session runner: spawn a shell command, copy its stdout to a log file, report status running/completed/failed from the return code, read only the last 12,000 bytes, terminate then kill after 3 seconds | src/openharness/bridge/manager.py:30 (`BridgeSessionManager`; `read_output` :71); src/openharness/bridge/session_runner.py:16 (`SessionHandle.kill`) | reference | Overlaps `sandbox/stream.py` and the task board. The terminate-then-kill and tail-read are the only ideas. |
| OH84 | bridge | Work secret: base64url JSON with a version check, required ingress token and base URL; `build_sdk_url` picks ws/wss by whether the host is local | src/openharness/bridge/work_secret.py:17 (`decode_work_secret`; `build_sdk_url` :31) | reference | Remote-session ingress. The local test is a substring match on the URL, so a lookalike host could pass. Not for adoption. |

## Do not port

| source | reason |
|---|---|
| src/openharness/ui/**, frontend/**, autopilot-dashboard/**, themes/**, vim/**, keybindings/**, voice/**, output_styles/**, docs/autopilot/{index.html,snapshot.json,assets} | UI, terminal and voice front ends and a static dashboard export. Out of scope. |
| src/openharness/channels/** and ohmo/** | Chat-platform bridges and the personal-agent product. Still not opened, see Gaps. |
| src/openharness/auth/**, api/** | Provider auth and API clients. Slice 4 has its own router. |
| src/openharness/swarm/{subprocess_backend,spawn_utils}.py and tmux handling in swarm/team_lifecycle.py | Terminal-pane spawning. Slice 7 runs agents on threads. |
| src/openharness/swarm/mailbox.py | Overlaps slice 7 `message_bus.py`. |
| src/openharness/engine/query.py (whole loop) and engine/cost_tracker.py | Overlaps slices 1-2. Only OH36 and OH45 are taken. |
| src/openharness/autopilot/service.py GitHub plumbing: issue and PR scan, `gh` calls, PR body builders, CI polling, bilingual comments (:502-:626, :1251-:1572, :1357-:1500) | GitHub-coupled and product-specific. Only the card, scoring and journal ideas above are kept. |
| src/openharness/bridge/work_secret.py as code | Remote ingress secret handling with a weak local-host test. See OH84. |
| src/openharness/plugins/loader.py `_load_plugin_tools` (:691) | Imports and runs arbitrary Python from a plugin's `tools/` directory with `exec_module`. Not safe to port. |
| src/openharness/memory/{migrate,scan}.py, personalization/**, services/memory_extract/**, services/session_memory/** | Not needed given external memory. Not opened beyond the listing. |
| src/openharness/mcp/** | Overlaps slice 9. |
| README.zh-CN.md, release notes | Documentation. |

## Gaps

- **Licence provenance.** The upstream org is unverified per `licence-rules.md`. MIT is confirmed at `references/openharness/LICENSE` only.
- **No eval or benchmark runner.** Searched `tests/`, `scripts/` and `autopilot/`. Only command gates (OH28, OH29) and the prompt-level verifier exist. No case-based benchmark, LLM-judge panel or mutation testing. OH44 (strict-JSON judge reply) is the closest piece.
- **No judge panel or adversarial-majority audit.** Searched "panel", "judge", "refute" in the files opened. The Authority List audit remains FinHub's own.
- **No deterministic graph or workflow DSL.** Coordination is LLM-driven, so there is nothing for slices 5-6.
- **No cross-agent budget enforcement.** `cost_tracker.py` only sums usage.
- **No skill trigger-quality testing.** `tests/test_skills` was not opened. Skill loading is tested, but no description near-miss check was found.
- **Opened this run.** `hooks/` (all five files), `plugins/{loader,schemas,installer}.py` (loader read except the commands and agents bodies at :320-:620), `memory/` (manager, schema, team, usage, search, relevance, memdir, agent), `bridge/` (manager, session_runner, work_secret), `swarm/permission_sync.py` (request, resolve, poll and handler bodies; mailbox send variants at :766-:996 only listed), `autopilot/` (types and service excerpts), `services/compact/__init__.py` (prompt, attachments, state, session-memory), `services/tool_outputs.py`, `services/autodream/` (prompt, lock, backup, service heads), `docs/autopilot`, and the test file names under `tests/test_{hooks,plugins,memory,autopilot,bridge}`.
- **Still not opened.** `ohmo/` (only listed), `channels/`, `memory/{scan,migrate}.py`, `services/{memory_extract,session_memory,cron_scheduler}`, `plugins/loader.py:320-:620` (command and agent file loaders), `compact_conversation` body (`services/compact/__init__.py:1119`), and the test bodies other than `test_autopilot/test_verification.py` and `test_hooks/test_priority.py` names. Rows OH73, OH82-OH84 are `reference` for that reason or by choice.
- **Hook seam is net-new.** Searched `src/master_finhub` for "hook": only `CheckpointHook` in `runtime/loop.py:98`, and the docstring says hooks are out of scope for slice 1. OH41-OH45 therefore need a new insertion point, not a patch to an existing layer.
- **Memory is external by design.** OH60-OH69 are for file-based ledgers inside `_workspace` or the plugin. They do not replace Zep or Supermemory.
- **Line-number method.** Numbers come from `sed -n` on the line or `grep -n` of def and constant lines in this session. Prompt-section rows point at the constant or function start. Rows OH41 and OH60 cite union and tuple definitions whose class lines I read; the inner field list is at the cited file, not at one line.
- **Python, not TypeScript.** "adapt" means rewrite with the MIT comment, not copy.
