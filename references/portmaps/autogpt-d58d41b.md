# Port map — autogpt

- Submodule: references/autogpt
- Pinned SHA: d58d41b (confirmed with `git rev-parse --short HEAD` in references/autogpt)
- Licence: `LICENSE` at the root says everything outside `autogpt_platform/` is MIT and everything inside is Polyform Shield (licence-rules.md row `autogpt`). `classic/` has no LICENSE file of its own; the root one governs. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: PARTIAL for the two purposes in scope. `classic/forge` permissions, watchdog, action history, component pipeline; `classic/direct_benchmark` evaluator, state, parallel, runner; two prompt strategies and two root `.claude/skills` were opened. Not opened: llm providers, file_storage, agent_protocol, other prompt strategies (lats, rewoo, tree_of_thoughts, plan_execute), the adapters other than base, `challenges/` data, `original_autogpt/app`. See Gaps.
- Language: Python. "adapt" means a rewrite under `src/master_finhub/` or prose in `skills/` with the MIT attribution comment.
- Id prefix: `A`.
- Scope: runtime patterns and harness-factory patterns. No `autogpt_platform/**` file was opened or cited.

## Already adopted / covered (do not re-propose)

Checked by grep against `src/master_finhub/`, `skills/` and the CLAUDE.md change history; module names and a few symbols only, not full bodies.

| area | covered in | note |
|---|---|---|
| benchmark runner, cutoff, baseline compare, string-contains grading | `src/master_finhub/evals/runner.py`, `evals/verifiers.py`, `evals/gates.py` | slice 11 was built from this tree's direct_benchmark idea; A1 to A4 below are only the leftover details |
| resume at the row | `skills/finhub-harness/scripts/unit_tracker.py` (H1) | A8 is the same idea at the benchmark level; keep as reference |
| exact repeated-call reminder | `runtime/repeat_reminder.py` | A11 (watchdog) is the same trigger; only its escalation differs |
| command deny list, workspace fence | `tools/safety.py`, `tools/sensitive_paths.py`, `sandbox/workspace.py` | deny is checked before allow already |
| DAG checkpoint and resume | `orchestration/dag_engine.py`, `graph_store.py` | |
| permission modes (CW1) | not started | A5 to A7 are the evidence for it, not a new proposal |

## Findings

### (a) Runtime

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| A1 | evals | Timed-out run still gets scored but is forced to fail, so a report can say "would have passed" | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:15 (rule at :62) | adapt | Check `evals/runner.py` already keeps score on cutoff before porting. |
| A2 | evals | Challenge passes only at score at least 0.9; no ground truth gives score 0 with a named error | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:23 (threshold at :67) | adapt | Threshold is a magic number; make it a parameter. |
| A3 | evals | Ground truth matched by extension or trailing path; case-insensitive option; contains and not-contains lists | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:86 (`_eval_string_match` at :94) | reference | `verifiers.contains` has the contains half; the not-contains half may be missing. |
| A4 | evals | Output files copied to a temp dir, the test file run with a hard timeout; timeout means score 0 | references/autogpt/classic/direct_benchmark/direct_benchmark/evaluator.py:158 | adapt | Run through our sandbox, not the host interpreter. Stderr-contains-"error" check at :153 is crude. |
| A5 | evals | Run key `config:challenge:attempt`; state saved after every finished run; corrupt state file falls back to a fresh session with a warning | references/autogpt/classic/direct_benchmark/direct_benchmark/state.py:40 (`run_key` :60, `load` :64, `mark_completed` :114) | pattern | Fresh-on-corrupt silently discards history; we should refuse instead. |
| A6 | evals | Retry-failures option deletes only the failed rows of saved state, returns how many it reset | references/autogpt/classic/direct_benchmark/direct_benchmark/state.py:253 | adapt | Small; fits a suite resume flag. |
| A7 | evals | Executor builds all config x challenge x attempt tasks, skips those a predicate calls done, runs under a semaphore, yields results as they finish | references/autogpt/classic/direct_benchmark/direct_benchmark/parallel.py:41 (semaphore at :88; skip predicate wired at harness.py:249) | pattern | Skipped count is stored on the executor for the report. |
| A8 | 1 | Step loop with a max-steps bound and an overall `wait_for` timeout; a finish tool ends it; cost read from the provider after each step | references/autogpt/classic/direct_benchmark/direct_benchmark/runner.py:235 (timeout at :318, `timed_out` at :337) | reference | `runtime/loop.py` covers the loop; only the per-step cost row is new. |
| A9 | 1 | Watchdog: when the same tool and arguments repeat, rewind history one step and re-ask with the stronger model | references/autogpt/classic/forge/forge/components/watchdog/watchdog.py:32 | pattern | Escalate-the-model-on-loop is net-new; our reminder only nudges. Name is wrong in source: it sets `big_brain` on the wrong object (:60). |
| A10 | 2 | Last N steps kept whole; older steps shown as one-line summaries until a token budget is full | references/autogpt/classic/forge/forge/components/action_history/action_history.py:56 | pattern | `runtime/context.py` has head/tail clip; per-step summaries with a budget differ. |
| A11 | 2 | Compression is lazy: summaries are made only when the prompt is built, and skipped for phases that build no prompt | references/autogpt/classic/forge/forge/components/action_history/action_history.py:124 | pattern | Saves model calls; our summary is model-free already, so low value. |
| A12 | 1 | Pending user feedback is shown as its own prominent message on the next turn, whether the user approved or denied | references/autogpt/classic/forge/forge/components/action_history/action_history.py:105 | pattern | Pairs with a deny that returns feedback (A14). |
| A13 | 7 | Pipeline runs a protocol method over components in dependency order; retries one component 3 times on an endpoint error, restarts the whole pipeline on a pipeline error | references/autogpt/classic/forge/forge/agent/base.py:177 (topological sort at :296) | pattern | Three error tiers is the useful part. Args are copied so a restart starts clean. |

### (b) Harness-factory

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| A14 | permissions | Layered check, first match wins: agent deny, workspace deny, agent allow, workspace allow, session denials, then ask | references/autogpt/classic/forge/forge/permissions.py:100 (class at :56) | adapt | Deny before allow already matches us; the agent/workspace layering is the new part (CW1). |
| A15 | permissions | Approval scopes once, agent, workspace, deny; the choice writes a generalised pattern to the matching settings file | references/autogpt/classic/forge/forge/permissions.py:13 (`_generalize_pattern` at :277) | adapt | Session-only deny set stops re-asking the same denied call. |
| A16 | permissions | File arguments are resolved to an absolute real path before matching, so a symlink or `..` cannot dodge a path rule | references/autogpt/classic/forge/forge/permissions.py:172 (resolve at :183-195) | reference | Our guard resolves already; use as a test idea only. |
| A17 | permissions | Glob to regex: escape first, then restore `**` as any and `*` as non-slash; `{workspace}` placeholder expanded; bad pattern matches nothing | references/autogpt/classic/forge/forge/permissions.py:237 | adapt | A malformed deny pattern fails open here (returns False); ours must fail closed. |
| A18 | permissions | Feedback instead of approval is raised as an exception so the loop can hand it to the agent as a refusal reason | references/autogpt/classic/forge/forge/permissions.py:22 | pattern | Small; fits a harness whose QA denies with a reason. |
| A19 | verification | Heuristic result check: error words versus success words, whichever appears first wins; score 0.2 or 0.8 | references/autogpt/classic/original_autogpt/autogpt/agents/prompt_strategies/reflexion.py:467 | reference | Too crude for a verdict; shows why QA needs real commands. |
| A20 | judge panel | Debate phases proposal, critique, revision, consensus, execution; critiques carry strengths, weaknesses, suggestions and a score | references/autogpt/classic/original_autogpt/autogpt/agents/prompt_strategies/multi_agent_debate.py:45 (models at :55, :67, :78) | pattern | Our judge is one fresh-context agent; a second critic is optional. Cost per round is high. |
| A21 | coordinator | Supervisor model: the orchestrating session watches panes and decides; a script does only the mechanical work (restart, press enter, recycle) | references/autogpt/.claude/skills/orchestrate/SKILL.md:35 | pattern | Outside `autogpt_platform/`, so MIT by the root LICENSE; tmux-specific, so idea only. |
| A22 | verification | Agents print `CHECKPOINT:<step>`; a window is not recycled until every required step was seen | references/autogpt/.claude/skills/orchestrate/SKILL.md:48 | pattern | Maps to our per-row tracker; the marker idea suits a chat surface with no shell. |
| A23 | verification | Done check runs in a fixed order: checkpoints, CI finished, CI passing, new CI run after spawn, unresolved threads, change requests | references/autogpt/.claude/skills/orchestrate/scripts/verify-complete.sh:4 | pattern | Order is the point: bots comment after checks, so threads are read last. |
| A24 | retrospective | Review/address loop with no fixed round count: stop only on zero new findings, all threads resolved, CI green, two quiet polls 60 s apart; hard cap of 10 rounds | references/autogpt/.claude/skills/pr-polish/SKILL.md:13 (cap at :23, loop at :52) | pattern | Our judge caps at 3 rounds; "two quiet polls" is a cheap anti-late-comment rule. |

## Do not port

| source | reason |
|---|---|
| references/autogpt/autogpt_platform/** | Polyform Shield 1.0. Not opened, not cited. Note: the root `AGENTS.md` and `.claude/skills/{pr-test,write-frontend-tests,open-pr,setup-repo}` are written for that platform's workflow; only the two skills cited above were read. |
| references/autogpt/classic/original_autogpt/autogpt/app/** | CLI and interactive approval UI, out of scope. |
| references/autogpt/classic/forge/forge/components/{image_gen,web,speech,clipboard,platform_blocks} | Feature components unrelated to the runtime or factory. |
| references/autogpt/classic/CLAUDE.md, forge/CLAUDE.md, original_autogpt/CLAUDE.md | Read as documentation only. They state the classic project is unsupported with known vulnerabilities; do not treat its security defaults as vetted. |

## Gaps

- No sandbox or container runtime in `classic/` that I opened; code execution is a Docker component (`forge/forge/components/code_executor`, listed only, not opened).
- No message bus or delegation tool: components pass data through one agent's pipeline, not between agents. Searched: `ls forge/forge/components`, `agents/`.
- Not opened: the llm providers (model routing, token counts), `file_storage/`, `agent_protocol/`, `components/skills/`, `components/todo/`, `adapters/{gaia,swe_bench,agent_bench}.py`, `models.py`, `report.py`, the other prompt strategies, `challenges/` data and `challenges_already_beaten.json` (regression-set idea in the `--maintain` flag, harness.py:187, not read in full).
- `.claude/skills/pr-review` and `pr-address` were listed but not read beyond headings.
- No MCP client and no SSE streaming found in `classic/` by listing; `agent_protocol/api_router.py` is a REST router, not opened.
- Line counts above come from files opened this session; ranges inside a unit (for example :183-195) were read in full.
