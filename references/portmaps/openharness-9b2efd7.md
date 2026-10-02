# Port map — openharness

- Submodule: references/openharness
- Pinned SHA: 9b2efd7 (confirmed with `git log -1`)
- Licence: MIT ("Copyright (c) 2025 OpenHarness Contributors", `references/openharness/LICENSE`; licence-rules.md row `openharness`). Upstream org unverified per that row.
- Mined: 2026-10-02 (reference-miner, Explore type, read-only)
- Status: COMPLETE for purposes (a)-(e). Not exhaustive: unopened packages are listed under Gaps.
- Language: all sources are Python, so "adapt" means a rewrite under `src/master_finhub/` with the one-line MIT attribution comment. All paths below are under `references/openharness/src/openharness/` and are written out in full in the table.
- Id prefix: `OH` (the schema's `O` is taken by openhands).
- Purpose: Authority List rows for `skills/finhub-harness/SKILL.md`. Rows are grouped by purpose (a)-(e).
- Kept in-repo (not only `_workspace/`) so the map survives a lost session.

## Already covered by runtime slices 1-11 (do not re-propose)

Checked against the module docstrings and defs under `src/master_finhub/`. Docstrings were read, not full bodies.

| slice | covered in | note |
|---|---|---|
| 1 loop | `runtime/loop.py` | ReAct loop from deepseek |
| 2 context | `runtime/context.py` | token estimate, tool-output clip, threshold compaction, orphan tool-result check at line 93 |
| 3 safety | `tools/safety.py`, `sandbox/workspace.py` | command denylist with lexer, wrappers, git rules and interpreters; workspace fence |
| 4 routing | `runtime/router.py`, `runtime/anthropic_llm.py` | |
| 5 checkpoint | `orchestration/dag_engine.py` | immutable JSON per save, resume |
| 6 graph | `orchestration/graph.py`, `graph_store.py` | deterministic graph, owner lock, fence, atomic publish |
| 7 modes | `orchestration/modes/{subagent,team,task_board,team_tools,workflow}.py`, `message_bus.py` | delegate with depth cap and budget, team with personas and limits, task board, bounded mailboxes |
| 8 container | `sandbox/docker_engine.py`, `sandbox/stream.py` | network-less, read-only, one container per command |
| 9 MCP | `tools/mcp/client.py` | stdio JSON-RPC |
| 10 SSE | `server/app.py`, `server/sse.py` | |
| 11 evals | `evals/runner.py`, `evals/verifiers.py` | deterministic string-match verifier, isolated workspace per case |

`factory/{evolver,skill_compiler,team_generator}.py` are empty stubs (slice 12 superseded by the finhub-harness skill).

**Consequence for this mine.** OpenHarness's own loop, compaction, mailbox, Docker sandbox, task board and MCP are mostly redundant with the above. The rows below are limited to what the slices lack: prompt-level and definition-level patterns, a few small mechanisms, and the "verification" and "permission" ideas.

## Findings

### (a) Orchestration and execution modes

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH1 | meta | Coordinator prompt rules: parallelise research, serialise writes per file set, never fabricate worker results, never thank notifications | references/openharness/src/openharness/coordinator/coordinator_mode.py:252 (`get_coordinator_system_prompt`; "Concurrency" subsection at :363) | adapt | Prose only. Feeds orchestrator templates and the chat fallback. |
| OH2 | meta | "Always synthesize": coordinator must restate findings as a self-contained spec with paths and lines, and never write "based on your findings" | references/openharness/src/openharness/coordinator/coordinator_mode.py:407 | adapt | Strong rule for delegation prompts in Mode C and the Authority List. |
| OH3 | meta | Continue-vs-spawn heuristic by context overlap; a failed worker is continued with its error context | references/openharness/src/openharness/coordinator/coordinator_mode.py:432 (failures at :381) | adapt | Maps to the existing Mode B vs C decision. Adds the overlap criterion. |
| OH4 | 7 | Worker results delivered as an XML task-notification envelope: task-id, status (completed/failed/killed), summary, result, usage | references/openharness/src/openharness/coordinator/coordinator_mode.py:109 (`format_task_notification`; dataclass at :80) | adapt | Result-envelope format only. Slice 7's message bus already exists. |
| OH5 | meta | Workers get a shared scratchpad directory with no permission prompts, for durable cross-worker notes | references/openharness/src/openharness/coordinator/coordinator_mode.py:221 (`get_coordinator_user_context`) | adapt | Already used in Claude Code here (scratchpad dir). Document as a standard in `_workspace`. |
| OH6 | 7 | Agent definition fields: `disallowed_tools`, `permission_mode`, `max_turns`, `background`, `isolation` (worktree or remote), `critical_system_reminder`, `memory scope` | references/openharness/src/openharness/coordinator/agent_definitions.py:60 (`AgentDefinition`; `ISOLATION_MODES` at :51) | adapt | Field set for agent-file frontmatter. Slice 7 `Persona` is much thinner. |
| OH7 | meta | Built-in definitions: Explore and Plan are read-only via `disallowed_tools`; `worker`; `verification` is background-only | references/openharness/src/openharness/coordinator/agent_definitions.py:556 (Explore), :575 (Plan), :590 (worker), :602 (verification) | adapt | Template for the read-only reviewer default in SKILL Step 3. |
| OH8 | meta | Agent markdown loader accepts camelCase and snake_case frontmatter, validates positive `maxTurns`, and filters agents by required MCP servers | references/openharness/src/openharness/coordinator/agent_definitions.py:695 (`load_agents_dir`; `has_required_mcp_servers` at :956) | adapt | The MCP-requirement filter is useful for Cowork, where connectors vary. |
| OH9 | 7 | Per-teammate abort controller with cooperative cancel and force flag; mailbox drained at turn boundaries for shutdown and user messages | references/openharness/src/openharness/swarm/in_process.py:52 (`TeammateAbortController`; `_drain_mailbox` at :295) | reference | Slice 7 team mode already has limits and a bus. Compare cancel semantics only. |
| OH10 | 7 | Leader-approves-worker permission flow: pending and resolved request files, polling for response, sandbox-permission variant | references/openharness/src/openharness/swarm/permission_sync.py:102 (`SwarmPermissionRequest`; `handle_permission_request` at :1082) | reference | Pattern for "worker asks the human via the lead". 1168 lines. Not needed until a human-gate slice. |
| OH11 | 8 | Git-worktree isolation per agent: slug validation (64 chars, no `.` or `..`), create-or-resume, stale cleanup | references/openharness/src/openharness/swarm/worktree.py:21 (`validate_worktree_slug`; `WorktreeManager` at :135; `create_worktree` at :150) | adapt | The slug validator is a small, safe unit and matches workspace-fence thinking. |
| OH12 | 7 | Background task record: types local_bash / local_agent / in_process_teammate; status pending/running/completed/failed/killed; output file; completion listeners | references/openharness/src/openharness/tasks/types.py:11 (`TaskRecord`; manager at tasks/manager.py:49 `BackgroundTaskManager`) | reference | Task board (slice 7) overlaps. Take only the output-file-plus-listener idea if wanted. |
| OH13 | meta | Autopilot "repo task card" loop: queue of cards, bounded attempts, worktree per card, journal, active-context file rebuilt each run | references/openharness/src/openharness/autopilot/service.py:644 (`run_card`; store at :226, `rebuild_active_context` at :405) | reference | 2239 lines and GitHub-coupled. Read for the shape of an unattended loop only. |

### (b) Skill and plugin structure

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH14 | meta | SKILL.md frontmatter via `yaml.safe_load` (handles `>` and `\|` scalars); fallback to `# heading` and first paragraph; fallback description template | references/openharness/src/openharness/skills/_frontmatter.py:34 (`parse_skill_metadata`) | adapt | Good fallback chain for a skill linter. A bad description yields a degraded match. |
| OH15 | meta | Project skill discovery walks from cwd up to the git root, least-specific first so later entries override; user dir as a second source | references/openharness/src/openharness/skills/loader.py:83 (`discover_project_skill_dirs`) | adapt | Override precedence rule for a future skill compiler. |
| OH16 | meta | Skill registry: name-keyed register/get/list with later registration overriding | references/openharness/src/openharness/skills/registry.py:8 (`SkillRegistry`) | pattern | 29 lines. Trivial. |
| OH17 | meta | Plugin manifest: name, version, `skills_dir`, `hooks_file`, `mcp_file`, `commands`, `agents`, `enabled_by_default`; also reads `.claude-plugin/plugin.json` | references/openharness/src/openharness/plugins/schemas.py:8 (`PluginManifest`; loader at plugins/loader.py:126 `load_plugin`) | adapt | Field list to check against `.claude-plugin/plugin.json` in the existing Step 0. |
| OH18 | meta | Plugin loader bundles skills, commands, agents, hooks and MCP from one directory; commands are namespaced by plugin name | references/openharness/src/openharness/plugins/loader.py:234 (`_command_name_from_file`; `_load_plugin_agents` at :479) | reference | Namespacing convention only. |
| OH19 | meta | Bundled skill set: commit, debug, diagnose, plan, review, simplify, skill-creator, test | references/openharness/src/openharness/skills/bundled/content/skill-creator.md:1 | reference | Compare with finhub skill-writing-guide. `skill-creator.md` is OpenHarness-specific on paths. |
| OH20 | meta | `diagnose` skill: failure localised by layer (routing, execution, verification, governance) from run artefacts (manifest, execution_trace.jsonl, failure_signature.json) | references/openharness/src/openharness/skills/bundled/content/diagnose.md:1 | adapt | Fits `finhub-harness-evolve` retrospectives. Needs run artefacts that slice 5 checkpoints partly provide. |
| OH21 | meta | Hook event set: session_start/end, pre/post_compact, pre/post_tool_use, user_prompt_submit, notification, stop, subagent_stop; hook types command/prompt/http/agent | references/openharness/src/openharness/hooks/events.py:8 (`HookEvent`; schemas at hooks/schemas.py:10) | reference | Same shape as Claude Code hooks. Useful only as a checklist. |
| OH22 | meta | Hook policy: per-hook `timeout_seconds` (1-600), `block_on_failure` (default False for command, True for prompt), `priority` ordering | references/openharness/src/openharness/hooks/schemas.py:22 (`PromptHookDefinition`; command variant at :10) | pattern | Default-block-for-prompt hooks is a design idea, not code. |

### (c) Verification, QA and eval

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH23 | meta | Verification-specialist prompt: try to break, not confirm. Names two failure modes (verification avoidance, seduced by first 80%). Caller may re-run commands, and a PASS without command output is rejected | references/openharness/src/openharness/coordinator/agent_definitions.py:251 (`_VERIFICATION_SYSTEM_PROMPT`) | adapt | Closest match to qa-agent-guide + `RESULT:` first line. Differs: VERDICT is the last line, so keep our first-line rule. |
| OH24 | meta | Mandatory per-check block (Command run / Output observed / Result). A check with no command is "a skip". At least one adversarial probe is required before PASS | references/openharness/src/openharness/coordinator/agent_definitions.py:251 (OUTPUT FORMAT and BEFORE ISSUING PASS sections) | adapt | Directly usable in chat fallback QA. Also supports the mutation spot-check gate. |
| OH25 | meta | Rationalisation list ("reading is not verification", "implementer's tests already pass") and a "before FAIL" check: already handled, intentional, not actionable | references/openharness/src/openharness/coordinator/agent_definitions.py:251 (RECOGNIZE YOUR OWN RATIONALIZATIONS / BEFORE ISSUING FAIL) | adapt | Reduces false FAILs. Pairs with PARTIAL verdict. |
| OH26 | meta | `critical_system_reminder` re-injected every turn for the verification agent: read-only on the project, tmp allowed, must end with VERDICT | references/openharness/src/openharness/coordinator/agent_definitions.py:357 (`_VERIFICATION_CRITICAL_REMINDER`) | adapt | Cheap guard against role drift in long runs. |
| OH27 | meta | Verification strategy table by change type (frontend, API, CLI, infra, library, bug fix, migration, refactor, data pipeline) | references/openharness/src/openharness/coordinator/agent_definitions.py:251 (VERIFICATION STRATEGY section) | adapt | Reference table for QA agents. Domain-specific rows need FinHub equivalents (e.g. lender-calculation checks). |
| OH28 | 11 | Verification policy as data: commands as argv (no shell) by default; shell metacharacters are an error unless `shell: true` opt-in; policy errors become a failing step | references/openharness/src/openharness/autopilot/service.py:155 (`_parse_verification_entry`; run at :2094 `_run_verification_steps`) | adapt | Fail-loud policy parsing. Slice 11 runner has no command-gate layer. |
| OH29 | 11 | Repair loop: attempts bounded (3), failure stage and prior summary fed into the next prompt, "smallest patch", re-run verification | references/openharness/src/openharness/autopilot/service.py:1595 (`_prepare_repair_prompt`; defaults near :70-90) | adapt | Matches "one builder retry" in quality-gates. Prompt wording is the useful part. |
| OH30 | meta | Human gate defaults on; auto-merge only with an explicit label; merge and release require a human; auto-revert off | references/openharness/src/openharness/autopilot/service.py:60 (`default_human_gate`; release policy defaults nearby) | pattern | Policy defaults, not mechanism. |

### (d) Sandboxing and tool safety

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH31 | 3 | Built-in sensitive-path denylist (ssh, aws, gcloud, azure, gnupg, docker, kube creds) checked first and not overridable by mode or allow-list | references/openharness/src/openharness/permissions/checker.py:75 (`PermissionChecker.evaluate`; patterns defined at the top of the same file) | adapt | Net-new vs `tools/safety.py` and workspace fence. Credential paths outside the workspace are not named there. Verify before porting; safety.py bodies were not read. |
| OH32 | 3 | Evaluation order: sensitive path, denied tools, allowed tools, path rules, command deny, mode (full_auto / read-only / plan / default-confirm) | references/openharness/src/openharness/permissions/checker.py:75 (`evaluate`; modes at permissions/modes.py:8) | adapt | Plan mode (block all mutating tools) is a ready-made "dry run" switch for the chat fallback. |
| OH33 | 3 | `validate_sandbox_path`: resolve then `relative_to` cwd, with extra allowed roots | references/openharness/src/openharness/sandbox/path_validator.py:8 | reference | Same as the existing workspace fence. Nothing to add. |
| OH34 | 8 | Docker run argv: `--network none` always; fail closed if domain allow/deny is configured but unenforceable; cpu/memory limits; project bind mount | references/openharness/src/openharness/sandbox/docker_backend.py:82 (`_build_run_argv`) | reference | Slice 8 engine already does network-less read-only. "Fail closed on unenforceable policy" is the one idea worth a test. |
| OH35 | 8 | `fail_if_unavailable`: if sandbox is enabled but the runtime is missing, raise instead of running unsandboxed | references/openharness/src/openharness/sandbox/adapter.py:105 (`wrap_command_for_sandbox`; `SandboxUnavailableError` at :17) | adapt | Check slice 8 has an explicit refuse-if-unavailable test. |
| OH36 | 2 | Large tool output offloaded to a file; inline gets a preview plus size and path | references/openharness/src/openharness/engine/query.py:524 (`_offload_tool_output_if_needed`) | adapt | Slice 2 clips; it does not save the full output. The path name is sanitised and capped at 80 chars. |

### (e) Lessons for the single-context chat / Cowork fallback

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OH37 | 2 | Microcompact: replace old tool results with a cleared marker, keep the most recent N (min 1), no LLM call | references/openharness/src/openharness/services/compact/__init__.py:808 (`microcompact_messages`) | adapt | Cheap first pass before summary compaction. In chat, the analogue is "drop raw tool dumps, keep the last few". |
| OH38 | 2 | Compaction split never cuts through a tool_use / tool_result pair; trailing orphan tool_use removed | references/openharness/src/openharness/services/compact/__init__.py:483 (`_split_preserving_tool_pairs`; `_boundary_crosses_tool_pair` at :471) | adapt | `runtime/context.py` checks orphan results. Confirm it also preserves pairs on the compaction cut. |
| OH39 | 2 | Post-compaction attachments: re-inject task focus, recent files, plan, invoked skills and verified work after a summary | references/openharness/src/openharness/services/compact/__init__.py:566 (`create_task_focus_attachment_if_needed`; `create_recent_verified_work_attachment_if_needed` at :619) | pattern | Best source for a chat "state ledger" carried across context resets. Idea only. |
| OH40 | meta | In a single context, the same patterns degrade to prose: OH1/OH2 become a "restate the findings as a spec" step, OH23-OH26 become a role switch with command-and-output blocks, OH37 becomes a rolling "cleared" summary | coordinator/coordinator_mode.py:407, coordinator/agent_definitions.py:251, services/compact/__init__.py:808 (same files as above) | adapt | Synthesis row, not a new source. Cite the three underlying rows in the fallback section. |

## Do not port

| source | reason |
|---|---|
| references/openharness/src/openharness/ui/**, frontend/**, autopilot-dashboard/**, themes/**, vim/**, keybindings/**, voice/**, output_styles/** | UI, terminal and voice front ends. Out of scope. |
| references/openharness/src/openharness/channels/** (13 impl files) and ohmo/** | Chat-platform bridges and the personal-agent product. No runtime need. |
| references/openharness/src/openharness/auth/**, api/** | Provider auth and API clients. Slice 4 has its own router and adapter. |
| references/openharness/src/openharness/swarm/{subprocess_backend,spawn_utils}.py and tmux pane handling in swarm/team_lifecycle.py | Terminal-pane spawning. Slice 7 runs agents on threads. |
| references/openharness/src/openharness/swarm/mailbox.py (file-based inboxes with an exclusive lock) | Overlaps slice 7 `message_bus.py`. In-process bounded queues were chosen deliberately. |
| references/openharness/src/openharness/engine/query.py (whole loop) and engine/cost_tracker.py | Overlaps slices 1-2. Not a better loop. Only OH36 is taken from it. |
| references/openharness/src/openharness/memory/**, personalization/**, services/autodream/** | Memory and personalisation stores. FinHub memory is external (Zep, Supermemory). |
| references/openharness/src/openharness/mcp/** | Overlaps slice 9. Not opened beyond the directory listing. |
| Bilingual (zh/en) issue-comment text in autopilot/service.py | Product-specific and not relevant to FinHub. |
| `README.zh-CN.md`, release notes | Documentation. |

## Gaps

- **Unverified licence provenance.** `licence-rules.md` says the upstream org is unverified. The pin is a fork under `danielnguyenfinhub`. MIT is confirmed at `LICENSE` only.
- **No eval or benchmark runner.** Searched: `tests/`, `scripts/` listings and `autopilot/`. The only verification machinery is OH28/OH29 (command gates) and the prompt-level verifier OH23-OH27. There is no case-based benchmark, no LLM-judge panel and no mutation testing. Slice 11 and the quality-gates mutation check stay net-new or autogpt-sourced.
- **No judge panel or adversarial-majority audit.** Searched for "panel", "judge", "refute" in the files opened. Not found. The Authority List audit remains FinHub's own.
- **No deterministic graph or workflow DSL.** Coordination is LLM-driven (coordinator prompt plus tools), so there is nothing for Mode A (Workflow) or slice 6. Slices 5-6 are already ahead of this repo.
- **No budget or token-limit enforcement across agents.** `cost_tracker.py` only sums usage (24 lines). Slice 7 has `_AgentBudget`.
- **No plugin or skill trigger testing.** Skill loading is tested (`tests/test_skills`, listed but not opened). There is no description-quality or near-miss trigger check. SKILL.md Step 6 is net-new.
- **Not opened.** `plugins/loader.py` internals beyond the def list, `permission_sync.py` bodies (only def names), `hooks/executor.py` bodies, `memory/`, `bridge/`, `tests/`, `docs/autopilot`, `ohmo/`. Rows OH10, OH12, OH13, OH18, OH21 rest on def and class listings and docstrings, hence `reference`.
- **Sensitive-path list.** OH31 cites `evaluate()`. The pattern constant begins above line 20 of `permissions/checker.py`. The architect should open the top of that file for the exact line before citing it.
- **Line-number method.** Line numbers come from `grep -n` def lines or `sed` ranges opened this session. Prompt-section rows (OH23-OH27, OH1) point at the string constant or function start. Individual section lines inside the f-string or triple-quoted prompt were read but not individually numbered, except the `coordinator_mode.py` headings (:363, :372, :381, :407, :432) from grep.
- **Python, not TypeScript.** Unlike deepseek, these sources are Python already. "adapt" still means rewriting, with the MIT comment `# adapted from references/openharness/<path>:<line> (MIT)`.
