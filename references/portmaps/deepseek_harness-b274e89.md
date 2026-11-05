# Port map — deepseek_harness

- Submodule: references/deepseek_harness
- Pinned SHA: b274e89 (confirmed with `git rev-parse --short HEAD`)
- Licence: MIT ("Copyright (c) 2026 DeepSeek", `references/deepseek_harness/LICENSE`; licence-rules.md row `deepseek_harness`). Attribution line required when adapting; the repo is TypeScript, so every `adapt` is a Python or prose rewrite.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: PARTIAL for the two purposes in scope (runtime and harness-factory). About 25 of roughly 150 packages were opened (guard, spill, compaction, token-meter, llm-retry, sandbox, interaction, hooks, goal, plan, todo, workflow/ralph, context, subagent child-agent, plus AGENTS.md and four docs). Not opened: the `llm-deepseek`/`llm-pi-ai` adapters beyond slice 1-4 sources, `apps/`, `website/`, `native/`, `python/`, `vendor/`, `packages/web`, `acp`, `terminal`, `lsp`, `schedule`, `jobs-local`, `session-persistence-*`, `docs/postmortem/*` (see Gaps).
- Id prefix: `D`.
- Scope: runtime patterns and harness-factory patterns.

## Already covered by runtime slices 1-4 and later (do not re-propose)

Checked by reading the module docstrings of `src/master_finhub/` (grep for `deepseek`), not full bodies.

| slice | covered in | deepseek source it came from |
|---|---|---|
| 1 loop, repeat reminder | `runtime/loop.py`, `runtime/repeat_reminder.py` | `packages/core/agent-loop/src/agent.ts`, `packages/guard/repeat-tool-reminder/src/index.ts` (advisory thresholds 3/5/8) |
| 1 router | `runtime/router.py` | `packages/llm/llm/src/types.ts:343` |
| 1 provider adapter | `runtime/anthropic_llm.py` | `packages/llm/llm-pi-ai/src/{context,stream}.ts`; retry-after clamp is its own design |
| 2 context | `runtime/context.py` | token-meter `estimate.ts` (chars/4 plus overheads), pruner head/marker/tail clip, compaction-basic thresholds and tail-anchored range, `tool-pairing.ts` back-off, summary frame tags |
| 3 fence | `sandbox/workspace.py`, `tools/safety.py` | fs-sandbox containment, check-at-write (reads fenced too, a deliberate departure) |
| 4 process I/O | `sandbox/stream.py`, `sandbox/docker_engine.py` | subprocess env scrub, bounded tail, process-group kill |
| 5 checkpoint | `orchestration/dag_engine.py` | storage-json atomic write, no-clobber publish, `session-checkpoint-policy/src/index.ts:52-58` (checkpoint before tool body, fail closed) |
| 7 subagent | `orchestration/modes/subagent.py` | depth cap and "child guard = parent AND config" already exist; `subagent/subagent/src/child-agent.ts:48` is the same idea |
| 9 MCP | `tools/mcp/client.py` | python sdk client, mcp-client pagination and isError mapping |

## Findings

### (a) Runtime

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D1 | new | Oversized plain-text tool result is saved whole to a session artifact; the model sees a head/tail preview plus a locator and retrieval hint | references/deepseek_harness/packages/spill/spill-policy/src/index.ts:190 | adapt | `context.py` only clips and drops the rest; this keeps the full text retrievable. Needs a spill dir. |
| D2 | new | Reserve the notice's byte cost inside the cap so the replacement never exceeds the cap; if the notice alone is too big, keep the original | references/deepseek_harness/packages/spill/spill-policy/src/index.ts:171 | adapt | Cap invariant is the testable part. Orphan spill file accepted at :181. |
| D3 | new | Spill is best-effort: a storage failure or missing backend keeps the inline result and never turns a success into an error | references/deepseek_harness/packages/spill/spill-policy/src/index.ts:154 | adapt | Also skip the `read` tool (:195) to avoid read, spill, read-again loops. |
| D4 | new | Config validated at load, not per call: a negative or fractional cap fails the deployment, not the tool | references/deepseek_harness/packages/spill/spill-policy/src/index.ts:117 | pattern | Same rule as AGENTS.md:114 (D24). Applies to every new Python config. |
| D5 | new | A tool declares `timeoutMs`; a wrapper arms a deadline, then replaces the result with a structured TOOL_TIMEOUT only if its own timer fired | references/deepseek_harness/packages/guard/timeout-policy/src/index.ts:56 | adapt | Scoping by code stops a nested outer deadline being misread (:19-24). Result shape at :41. |
| D6 | 2 | Context-overflow recovery: on a window-exceeded error, compact once and retry, bounded by a per-policy retry count | references/deepseek_harness/packages/compaction/compaction-basic/src/index.ts:179 | adapt | `context.py` compacts before the call only. Default 1 retry at config.ts:93; counter reset at :171-177. |
| D7 | 2 | Compaction brackets the whole operation with start, summary and end events, so a crash mid-way leaves an open lock | references/deepseek_harness/docs/subsystems/compaction.md:19 | pattern | Fits dag_engine checkpoints; record only if compaction ever uses a model. |
| D8 | 2 | Log the estimated tokens a compaction replaced, so meters never double count shadowed content | references/deepseek_harness/packages/llm/token-meter/src/surface-projection.ts:31 | pattern | Only needed once usage is metered across compactions. |
| D9 | 1 | Retry delay: capped exponential with a jitter ratio, and the retry is logged durably before the cancellable wait | references/deepseek_harness/packages/llm/llm-retry/src/index.ts:58 | pattern | `anthropic_llm.py` relies on SDK retries plus a retry-after cap; this adds own-jitter formula only. Low value. |
| D10 | 1 | A Stop hook that denies pushes a steering message so the loop runs another step | references/deepseek_harness/packages/hooks/hooks-claude-code/src/index.ts:270 | adapt | Upstream has a TODO at :269 for a cap on forced continuations; ours must ship the cap. |
| D11 | 1 | Hook outcomes merged by strictness: deny beats ask beats allow; first halt is sticky; reasons of the winning rank joined | references/deepseek_harness/packages/hooks/hook-protocol/src/merge.ts:62 | adapt | Rank table at :35. Pure function, easy to mutant-test. |

### (b) Sandbox, permission and approval

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D12 | new | Policy precedence per call: approved explicit mode, then last session override, then deployment default; default is read-only | references/deepseek_harness/packages/sandbox/sandbox-policy/src/index.ts:135 | adapt | Basis for CW1 (named session permission modes). Fail-safe default noted at :62. |
| D13 | new | A session's mode override is the last mode event in the log; resume needs no catch-up state | references/deepseek_harness/packages/sandbox/sandbox-policy/src/session-mode.ts:52 | adapt | Needs an event log per session; `dag_engine` checkpoints could carry it. |
| D14 | new | Approval policy per session: `ask` delegates to answerers, `never` rejects every ask without prompting (headless stance) | references/deepseek_harness/packages/interaction/user-approval/src/index.ts:85 | adapt | Maps to our scheduled or unattended run that never sends (C28 D2). |
| D15 | new | Approval outcomes are a closed set; a missing or throwing answerer becomes `unavailable` and callers deny; a grant covers only the asked action | references/deepseek_harness/packages/interaction/user-approval/src/index.ts:1 | adapt | Outcome type in types.ts; audit pair asked/decided at :36-55 (one decided per asked). |
| D16 | new | Escalation ladder is strictly wider only; the schema lists targets, execution checks the per-call truth | references/deepseek_harness/packages/sandbox/sandbox/src/escalation.ts:28 | adapt | Table at :28, closed target list :41. |
| D17 | new | An escalation request must carry a non-empty justification, and both arguments travel together | references/deepseek_harness/packages/sandbox/sandbox/src/escalation.ts:51 | adapt | `approveEscalation` at :157 runs the ask before anything executes. |
| D18 | new | One user-facing preset bundles sandbox mode and approval policy; unmatched knob values show as `custom`, never as a switch target | references/deepseek_harness/packages/interaction/permission-presets/src/index.ts:70 | adapt | CW1 shape: named modes over two independent knobs. Last-preset fold at :81. |
| D19 | new | Missing or unusable confinement fails closed; the runner never returns the original argv unconfined | references/deepseek_harness/packages/sandbox/sandbox-local/src/index.ts:1 | pattern | Landlock, bwrap, Seatbelt chain is OS specific and not portable. Principle only; `docker_engine.py` is our runner. |

### (c) Agent behaviour, memory and loops

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D20 | harness | Goal round prompt: treat the workspace as authoritative, gather evidence that the whole objective holds before marking complete | references/deepseek_harness/packages/goal/goal-round-driver/src/prompt.ts:18 | adapt | Prose for generated loop agents; pairs with H2 pilot rule. Own wording needed. |
| D21 | harness | Goal lifecycle: active, paused, blocked, complete; blocked carries a stable code plus a message; every change bumps a revision (compare-and-set) | references/deepseek_harness/docs/subsystems/goal.md:25 | pattern | Blocked reason at :32. Useful for a run ledger; the event-sourced service is not needed. |
| D22 | harness | Ralph loop: one fresh child per round, carrying only the objective and the previous bounded handoff; statuses continue, complete, blocked, budget-limited | references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:1 | adapt | Round cap default 256 at :37; handoff size cap in Config. Fits `modes/` as a fourth mode. |
| D23 | harness | Todo tool replaces the whole list each call; last write wins; config says whether several items may be in progress | references/deepseek_harness/packages/todo/tool-todo/src/index.ts:1 | pattern | Flag at :37. Tiny; prefer unit_tracker for bulk work. |
| D24 | harness | Plan mode keeps the exit tool registered while inactive, so toggling changes only a prompt section, not the tool catalogue | references/deepseek_harness/packages/plan/plan-mode/src/index.ts:16 | pattern | Cache-stable request prefix idea; sandbox and approval stay independent (:5-7). |
| D25 | harness | Instruction files load before the first request; later nested, changed or removed files arrive through the inbox after fs tool touches | references/deepseek_harness/packages/context/agent-instructions/src/index.ts:1 | pattern | For generated harnesses with nested CLAUDE.md; not needed for the runtime. |

### (d) Verification and process rules

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D26 | harness | Verify the world, not the self-report: re-run the command or re-read the file, assert untouched files are byte-identical | references/deepseek_harness/docs/testing.md:27 | adapt | Check `qa-agent-guide.md` for overlap before porting; only surfaces.md matched a loose grep. |
| D27 | harness | A guard only guards if the regression actually fails it; smoke tests must pin the exports a loader needs | references/deepseek_harness/docs/testing.md:34 | pattern | Same intent as mutant_gate; one sentence for the QA guide. |
| D28 | harness | Runtime invariants assert owned relationships from authoritative event streams, not service presence or fixed examples | references/deepseek_harness/AGENTS.md:104 | pattern | Per-package invariant companions (e.g. guard/timeout-policy/src/invariant.ts:21 is an empty one by design). |
| D29 | harness | Anything that reaches the model must be reconstructable from the session log | references/deepseek_harness/AGENTS.md:108 | adapt | Rule for `state-ledger.md`: new model-visible input needs a logged event. |
| D30 | harness | Misconfiguration fails loud at load, never silently skips a missing referent | references/deepseek_harness/AGENTS.md:114 | pattern | Check against lint_harness rules before adding. |
| D31 | harness | Defensive rules: report orthogonal outcomes separately, dispose to quiescence, contain callback exceptions | references/deepseek_harness/docs/defensive-patterns.md:7 | pattern | Items at :19 and :23. Runtime review checklist, not code. |
| D32 | harness | Every non-trivial change ships a short design note in the same PR | references/deepseek_harness/AGENTS.md:123 | reference | Our `_workspace` verdicts and CLAUDE.md rows already do this; nothing to port. |

## Do not port

| source | reason |
|---|---|
| references/deepseek_harness/packages/sandbox/sandbox-windows-acl/** | Windows ACL FFI runner; OS specific, out of scope for the Python runtime. |
| references/deepseek_harness/native/** | Landlock launcher binary; native code, we use docker. |
| references/deepseek_harness/packages/web/**, apps/**, website/**, packages/terminal/** | UI and hosting, out of scope. |
| references/deepseek_harness/packages/hooks/hooks-codex/**, subagent-codex/**, subagent-claude-code/**, subagent-acp/** | Bridges to other vendors' agents; not our design. |
| references/deepseek_harness/packages/llm/llm-deepseek/** | DeepSeek provider adapter; we use Anthropic. |
| references/deepseek_harness/vendor/** | Vendored third-party source with its own licences; not mined and not a source (see THIRD_PARTY_NOTICES.md). |

## Gaps

- No tokenizer: the token meter is chars/4 only (`estimate.ts:13`), so slice 4 real counts are net-new. Searched `packages/llm/token-meter/src`.
- No regex command denylist, no sensitive-path list: sandbox confinement is by OS runner (bwrap, Landlock, Seatbelt), not text matching. Our `safety.py` guard is net-new relative to this repo.
- No pilot-then-fan-out or per-row tracker: `docs/subsystems/agent-team.md` has a mailbox and task list for teammates; opened only its first 30 lines, so its claim rules are not mapped.
- No mutation-testing or judge panel found; `docs/testing.md` has only per-file coverage and snapshot rules.
- Not opened, so no finding either way: `packages/subagent/subagent/src/continuation.ts` beyond its header (cold resume, FIFO turns), `jobs-local`, `schedule`, `session-persistence-*`, `session-query`, `skill-filesystem` internals, `docs/postmortem/*`, `docs/cookbook/*`, `python/sdk*`. Re-mine these for a later round.
- The hooks bridge is declared by the repo as honoring only some Claude Code fields (`updatedInput` is logged, not honored, `hooks-claude-code/src/index.ts:6`); do not assume parity.
