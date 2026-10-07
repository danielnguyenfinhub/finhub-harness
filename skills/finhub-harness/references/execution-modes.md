# Execution Modes in Detail: The Three Modes of Harness v2
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

This document explains the main features, constraints, and selection criteria of the three execution modes that Harness v2 provides. It supplements Step 2-1 of `SKILL.md`.

---

## Table of contents

1. [Mode A: Workflow orchestration](#1-mode-a-workflow-orchestration)
2. [Mode B: Persistent agent collaboration](#2-mode-b-persistent-agent-collaboration)
3. [Mode C: Sub-agent delegation](#3-mode-c-sub-agent-delegation)
4. [Decision tree for choosing an execution mode](#4-decision-tree-for-choosing-an-execution-mode)
5. [Migrating from v1 to v2](#5-migrating-from-v1-to-v2)

---

## 1. Mode A: Workflow orchestration

Workflow orchestration (Mode A) runs an orchestration script through the `Workflow` tool. Control flow such as fan-out, loops, and conditional branches is decided by **code**, not by the model's judgment in the moment. The same input therefore reproduces the same structure easily, and the mode suits running many agents in parallel.

```
[Main agent] → Workflow(script)
           ├── phase('Explore'): pipeline(items, item => agent(...))
           ├── phase('Verify'): for each finding, look for evidence that refutes it (in parallel)
           └── return { confirmed }   ← structured final result
```

**Main features:**
- `agent(prompt, opts)` runs a sub-agent. If you set a JSON Schema in `opts.schema`, it returns a structured object that has already passed schema validation. You do not need to parse it separately, and it retries automatically when the output does not match the schema. For a phase marked `once`, leave `opts.schema` off: whether that retry repeats the agent's outside call is not known, and rule O7 of `state-ledger.md` section 3a forbids a retry of a `once` phase. (adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0)) If you set `opts.agentType`, you can use a custom type defined in `.claude/agents/`. `opts.effort` adjusts reasoning effort, and `opts.isolation: 'worktree'` isolates file changes.
- `pipeline(items, stage1, stage2, ...)` sends each item through several stages independently. There is no synchronization barrier between stages, so **use it by default for multi-stage work.**
- `parallel(thunks)` is a synchronization barrier that waits until every task finishes. Use it only when the next stage needs **all** results of the previous stage, for example for de-duplication or for early exit based on the total count.
- `phase(title)` / `log(msg)` group progress and tell the user what is currently running.
- `budget` links to a token budget the user specifies (for example "+500k"). Use `budget.total` and `budget.remaining()` to scale the work dynamically.
- `workflow(nameOrRef, args)` runs another workflow nested one level deep. Use it to delegate work hierarchically.

**Characteristics:**
- Code decides the control flow, so the same input follows the same execution structure.
- Structured output (`schema`) lets you pass schema-conforming data between stages.
- `resumeFromRunId` resumes an interrupted run. Unchanged `agent()` calls return cached results immediately, so a partial re-run costs little. A stage marked `once` that did not return a result is not resumed this way, because its call may have gone out: run `resume` and follow rule O6 of `state-ledger.md` section 3a. A `once` stage that already returned a result is cached only while its prompt is unchanged: pass such a stage file paths and its key, never the text of an upstream result, so editing an upstream stage cannot make it run again; if its prompt must change, treat it as a named re-run of that stage and ask under rule O6 of `state-ledger.md` section 3a.
- It runs in the background and sends a notification when the work finishes.

**Constraints:**
- **The user must ask first.** Use it only when the user directly requested a workflow or multi-agent orchestration, or when the user runs a skill that explicitly calls `Workflow`. An orchestration skill built by the harness falls under the second case. Even so, keep the default number of agents small, and use large-scale fan-out only when the user explicitly asks for it.
- Scripts must be plain JavaScript; TypeScript syntax is not allowed. `Date.now()`, `Math.random()`, and `new Date()` without arguments interfere with resuming a run, so do not use them. Pass timestamps through `args`.
- The `meta` block accepts literals only. Variables, function calls, and spread syntax are not allowed.
- Each session has an upper limit on how many agents may run concurrently. Work beyond the limit is queued automatically. The total number of agents a single workflow may call is also capped to prevent runaway execution.
- A failed or skipped `agent()` returns `null`. `parallel()` does not throw even when a call fails, so always apply `.filter(Boolean)` to the results.
- The `parallel()` barrier only aligns when tasks finish; it does not prevent edits after they finish. In mixed modes, a named agent woken by `SendMessage` after a workflow stage ends can edit that stage's artifact files, so freeze artifacts (artifact freeze) at the boundary where the mode changes (Step 4 of Template B in `orchestrator-template.md`).

**Good fit:** fan-out whose list can be fixed in advance, such as N files or M perspectives; loop-until-dry iteration and adversarial verification; large-scale migrations and audits; structured report generation

**Poor fit:** work where the target must be discovered through an ongoing conversation so the list cannot be fixed in advance; work that needs frequent consultation with the user midway

> See `workflow-recipes.md` for concrete script skeletons and pitfalls.

## 2. Mode B: Persistent agent collaboration

Persistent agent collaboration (Mode B) runs named agents and coordinates them with a shared task list and `SendMessage`. It replaces the "agent team" mode of v1.

**Biggest difference from v1:** `TeamCreate` and `TeamDelete` no longer exist. You do not create an explicit team object as in v1. Agents you launch with a name in a session belong to one collaboration group that is formed automatically.

```
[Main agent (leader)]
    ├── Agent(name: "researcher", subagent_type: "...", prompt: ...)   ← runs in parallel
    ├── Agent(name: "critic", ...)
    ├── TaskCreate(task + dependencies) → shared task list
    ├── SendMessage({to: "researcher"}, ...)  ← gives further instructions while keeping conversation context
    └── Receives completion notifications → collects results → final wrap-up
```

**Main features:**
- `Agent(name: ..., subagent_type: ..., model: ..., prompt: ...)`: if you set `name`, the agent becomes a persistent agent that you can call again with `SendMessage`. It runs in the background by default and sends a notification when it completes. If you need to wait until the work finishes, set `run_in_background: false`.
- `SendMessage({to: name})` lets a previously launched agent continue its work **with its conversation context intact**. It is needed when results go back and forth through repeated revisions.
- `TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet` share the task list. Use them to manage dependencies and progress between tasks, and when a supervisor assigns work according to progress.
- `TaskStop` stops background work that is over-running or no longer needed.

**Characteristics:**
- Agents remember earlier conversation and work history, so they can handle follow-up requests such as "fix only section 2 of the draft you made earlier in this session."
- Agents can share what they find, discuss differing opinions, and redirect the work immediately.
- The same specialist agent stays available for as long as the session lasts.

**Constraints:**
- The main agent (leader) coordinates directly, so the more agents there are, the more work piles onto the leader. Three to five agents is the right size.
- Deeply nested delegation slows responses and tends to lose conversation context. Keep delegation within two levels.
- It costs more tokens than calling a sub-agent once.
- A named agent still receives messages after it reports completion, so it may edit an artifact it already handed off while answering another agent's late question. If the next stage reads that artifact, freeze artifacts at the stage boundary. The freeze procedure is in Step 4 of Template B in `orchestrator-template.md`.

**Good fit:** work where an author and a verifier go back and forth with repeated revisions; reconciling conflicting data through discussion into one result; work where a supervisor assigns tasks according to progress; work that needs specialist agents throughout the session

**Poor fit:** one-off work where you only need the result; large-scale fan-out whose task list can be fixed in advance

## 3. Mode C: Sub-agent delegation

Sub-agent delegation (Mode C) hands work to a sub-agent with a single call to the `Agent` tool. Only the result returns to the main agent, and agents do not communicate with each other.

```
[Main agent] → Agent(sub A) ─┐
             → Agent(sub B) ─┼→ (parallel, background by default) → receive completion notifications → collect results
             → Agent(sub C) ─┘
```

**Characteristics:**
- Low overhead and fast. The main agent receives summarized results.
- Independent calls **bundled into one message** run at the same time.
- It runs in the background by default. If you need the result right away, set `run_in_background: false`.
- The main agent does not repeat a search it already delegated; it waits for the result.

**Constraints:**
- Agents cannot communicate with each other, and conversation context does not carry over once a call ends. To start fresh work, call without `name`.
- The main agent handles all coordination.

**Good fit:** one-shot research and collection; picking the specialists you need and taking only their results; a single independent verification

**Poor fit:** work where results must go back and forth through repeated revisions; large-scale fan-out whose execution flow can be fixed in advance

## 4. Decision tree for choosing an execution mode

```
Can the task list, verification criteria, and iteration conditions be expressed in code in advance?
├── Yes → Workflow orchestration (Mode A)
│         Code decides the control flow instead of the model's judgment.
│         Still honor the condition that the user must ask first, and do not raise the agent count beyond what is needed.
│
└── No → Does quality improve only if results go back and forth repeatedly and conversation context carries over?
          ├── Yes → Persistent agent collaboration (Mode B)
          │
          └── No → Are there two or more agents?
                    ├── Yes → Parallel sub-agent delegation (Mode C)
                    └── No → Single sub-agent call (Mode C)
```

**Choosing a mixed mode:** If the answer to the questions above differs by stage, mix execution modes. The following combinations are the common ones.

| Combination | Composition | Example |
|------|------|------|
| Workflow collection → persistent integration | A → B | Collect material in bulk by splitting it up, then have a team discuss and reconcile data that conflicts |
| Persistent generation → workflow verification | B → A | A team writes a draft, then adversarial verification runs in fan-out for each finding |
| Sub-agent pre-survey → workflow main work | C → A | The main agent or a sub-agent first works out the task list, then passes that list to the workflow through `args` |

**Principle of confirming the list before orchestrating:** Before starting a workflow, take a brief look at the file list, review targets, and research items, and fix the task list. Understanding the shape of the work before execution keeps the script simple and cuts unnecessary work.

## 5. Migrating from v1 to v2

When you find an orchestration skill or agent definition built by a v1 harness, propose converting it to the v2 format according to the table below.

| v1 element | Status | v2 replacement |
|---------|------|---------|
| `TeamCreate(team_name, members)` | **Removed** | Launch `Agent(name: ...)` in parallel in one message. Named agents belong to the collaboration group formed automatically in the session, so there is no need to create a team object separately. |
| `TeamDelete` / "team cleanup" step | **Removed** | Delete that step. Agents end naturally when they finish their work, and you can stop them with `TaskStop` if needed. |
| "Only one team active per session" constraint | **Form changed** | The explicit team object is gone, so the v1 constraint does not apply. Named agents work together in the collaboration group formed automatically in the session. |
| `SendMessage({to: "all"})` broadcast | Changed | Send `SendMessage` individually to only the recipients who need it. |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | **Not needed** | Remove it from both documents and scripts. |
| Forcing `model: "opus"` on every agent | Policy retired | Choose the model per agent according to the nature of its work. When the call is unclear, use `sonnet`, and keep model inheritance only when it was chosen deliberately. |
| Building large-scale fan-out as a team | Improved | Move it to a `Workflow` script. Code decides the control flow, structured output is used, and runs can be resumed. |
| "Step 0: check conversation context" in the orchestration skill | Kept | Keep the existing procedure, but add the `resumeFromRunId` option to Workflow orchestration (Mode A). |
| `_workspace/` file-writing rules | Kept | Use them as they are. |
| `CLAUDE.md` location notes and change history | Kept | Use them as they are. |

**Migration procedure:**
1. Remove references to `TeamCreate`, `TeamDelete`, broadcast, and the experimental flag from the existing orchestration skill.
2. Find the fan-out and verification-loop sections. If the execution flow can be fixed in code in advance, switch them to Workflow orchestration (Mode A).
3. Rewrite the remaining collaboration sections with the Persistent agent collaboration (Mode B) syntax (`Agent(name:)` + `SendMessage` + `TaskCreate` / `TaskUpdate`).
4. Remove the blanket `model: "opus"` setting from agent definitions, and keep only assignments that have a reason.
5. Run the Step 6 verification again (structural verification and a trial run) and record it in the `CLAUDE.md` change history.
