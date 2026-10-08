# Orchestrator Skill Templates (v2)
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

The orchestrator coordinates the whole team. This document provides three templates, one per execution mode, and also explains how to combine execution modes stage by stage.

- **Template A: Workflow orchestration (Mode A)**: large-scale fan-out or iterative verification whose control flow is fixed in advance
- **Template B: Persistent agent collaboration (Mode B)**: repeated feedback, negotiation, or long-running collaboration where agents must keep earlier conversation
- **Template C: Sub-agent delegation (Mode C)**: hand off independent tasks once each, in parallel, and collect only the results
- **Mixed mode**: combine the suitable execution mode for each stage

Every template checks for existing work in Step 0. Always include the `_workspace/` file layout rules, the error-handling methods, and the test scenarios.

---

## Template A: Workflow orchestration (Mode A)

```markdown
---
name: {domain}-orchestrator
description: "Orchestrates the {domain} workflow. Use it when the user asks with any of {initial run keywords}, and also for follow-up work such as revising {domain} results, partial re-runs, updates, supplements, re-running, and improving previous results."
---

# {Domain} Orchestrator

## Execution mode: Workflow orchestration (Mode A)

This skill uses the Workflow tool to orchestrate work whose control flow is fixed in advance. When the user
invokes this skill, treat it as consent to use Workflow. Limit the default number of agents to {N}. Raise the
number of agents only when the user asks for "thorough", "exhaustive", or "all".

## Agent composition

| Role | `agentType` | Skill | Artifact (`schema` summary) |
|------|-----------|------|--------------------|
| {collector} | {custom or built-in} | {skill} | {findings: [...]} |
| {verifier}  | {custom or built-in} | {skill} | {status, reason} |

In `{custom or built-in}`, write the name of a custom type or a built-in type.

## Work procedure

### Step 0: Check existing work (handle follow-up requests)

1. Check whether `_workspace/` exists.
   - If it does not → run from the start
   - If it does and the request is to fix only part of it → re-run only that part
   - If it does and new input was received → move the existing `_workspace/` to `_workspace_{ts}/` and run fresh
2. If you re-run only part of it and the previous run's `runId` is in `_workspace/run_meta.json`, handle it as follows.
   - Modify only that stage in the script, then resume with `resumeFromRunId`. `agent()` calls whose content
     has not changed return cached results immediately, so the run costs little. A stage marked `once` that failed or was interrupted is not resumed this way: run `resume` and follow rule O6 of `state-ledger.md` section 3a.
3. If you run fresh, receive a new `runId` and record it in `_workspace/run_meta.json`.
4. Connector preflight. Skip this item if the table says "none". Run it before any agent, Workflow, message or task call.

   | Agent | Required connector |
   |-------|--------------------|
   | {agent} | {server, as in `mcp__{server}__*`} |

   A connector counts as present when your tool list, deferred listings included, has at least one tool whose name begins with `mcp__{server}__`.
   - Claude Code: if any row is absent, make no further calls. Reply with one line per absent row: `Missing connector {server} for agent {agent}. Attach or authorise it, then run again. Nothing was started.`
   - Claude chat or Cowork: an attached connector can stay hidden until its schema is loaded, so absence is not proof. Search for the server name with the tool-search step if there is one. If it is still absent, name it in the same form and ask whether to attach it and continue, continue without it (report that agent's phase as skipped), or stop. Do not stop without asking.
   - Present means listed, not working. An auth or connection error on the first real call is handled by the error table below; do not retry it. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:956 (MIT))

### Step 1: Fix the task list (the main agent does this directly)

Before starting the workflow, take a brief look at {file list / research axes / review targets} and organize them into an array.
Pass the organized list to the script through `args`.

### Step 2: Run the workflow

Pass the following script to the Workflow tool. For detailed examples, see `workflow-recipes.md` of the finhub-harness skill.

- `meta`: `name` is '{domain}-run', and `phases` is [{Collect}, {Verify}, {Synthesize}]
- Collect: pipeline(args.items, item => agent(..., {schema: COLLECT}))
- Verify: adversarial verification for each item found → .filter(Boolean) → pass only items that survive verification to the next stage
- Synthesize: return the structured result

After calling it, wait for the completion notification. Do not presume the result before receiving the notification.

### Step 3: Organize and report the results

1. Receive the value the workflow returned.
2. If any items were excluded or are missing, state this in the report without fail.
3. Produce the final artifact at `{output-path}/{filename}`.
4. Leave the intermediate artifacts and `run_meta.json` in `_workspace/`.

## Error handling

| Situation | Response |
|------|------|
| An individual `agent()` fails (returns `null`) | For a phase marked `once`, do not run it again: run `resume` and follow rule O6 of `state-ledger.md` section 3a. Otherwise exclude it with `.filter(Boolean)` and record the number of excluded items with `log()`. State the missing items in the report as well. |
| The whole workflow fails | Check the actual return values in the `journal`, fix only the failed stage, and resume with `resumeFromRunId`. A stage marked `once` is never fixed and resumed this way: run `resume` and follow rule O6 of `state-ledger.md` section 3a. |
| Failures that retrying will not fix (usage limit exhausted, expired authentication, permission denied) | Do not retry or resume until the cause is cleared, because doing so only burns the remaining limit. Open the `journal` and the partial artifacts directly to confirm how far the run actually got, record the missing content as a file in `_workspace/`, and report to the user. For a usage limit, also tell the user when it resets. Once the cause is cleared, you can continue with `resumeFromRunId`, except a stage marked `once`: run `resume` and follow rule O6 of `state-ledger.md` section 3a. The main agent reflects only facts it confirmed directly, and does not guess at agents' judgments (for example, which material was excluded and why). |
| The result is empty | Do not mistake it for success. Check each agent's actual return value in the `journal`. |
| Conflicting data | Do not delete it; record it together with its sources. |
| A verdict whose `check` exits 3 (only where a worker judges a candidate) | The verdict belongs to another tree: treat it as not given, commit and start nothing from it, tell the user, and run the judging phase on the current tree when they agree. |

## Test scenarios

### Normal flow
1. When the user provides {input}, the pre-check fixes {M} items.
2. The workflow collects the {M} items, and when {K} of them pass verification, the results are organized.
3. Expected result: `{output-path}/{filename}` is created, and the run information is recorded in `run_meta.json`.

### Error flow
1. Two items return `null` in the collection stage.
2. Exclude those items with `.filter(Boolean)` and announce "2 items excluded" with `log()`.
3. Write "{item name}: 2 items failed to collect" in the final report.
```

---

## Template B: Persistent agent collaboration (Mode B)

```markdown
---
name: {domain}-orchestrator
description: "Orchestrates the collaboration of {domain} agents. Use it when the user asks with any of {initial run keywords}, and also for follow-up work such as revisions, partial re-runs, updates, supplements, re-running, and improving previous results."
---

# {Domain} Orchestrator

## Execution mode: Persistent agent collaboration (Mode B)

Do not create an explicit team object as in v1. Agents you launch with a name in a session belong to one
collaboration group that is formed automatically. TeamCreate and TeamDelete are tools that existed only in v1.

## Agent composition

| Name | `subagent_type` | Role | Skill | Artifact |
|------|--------------|------|------|------|
| {teammate-1} | {custom or built-in} | {role} | {skill} | {output-file} |
| {teammate-2} | {custom or built-in} | {role} | {skill} | {output-file} |

In `{custom or built-in}`, write the name of a custom type or a built-in type.

## Work procedure

### Step 0: Check existing work
As in Template A, check whether `_workspace/` exists to decide whether to run for the first time, re-run only part of it,
or run fresh. If you re-run only part of it, put the previous artifact paths in the agent prompt so
the agent reads and reflects the existing results.
Then run the connector preflight from Template A Step 0, item 4, before launching any agent.

### Step 1: Preparation
1. Analyze the user input to confirm {what needs to be understood}.
2. Create `_workspace/` and save the input in `_workspace/00_input/`.

### Step 2: Launch agents and register tasks

1. Launch the agents in parallel in one message. `name` is required and is used to address the target in SendMessage.
   - Agent(name: "{teammate-1}", subagent_type: "{type}", prompt: "{role + work instructions + output path}")
   - Agent(name: "{teammate-2}", subagent_type: "{type}", prompt: "...")
2. Register the shared task list.
   - TaskCreate({title: "{task 1}", assignee: "{teammate-1}"})
   - TaskCreate({title: "{task 3}", depends_on: [task 1]})
   > Three to six tasks per teammate is appropriate. State dependencies between tasks explicitly with `depends_on`.

### Step 3: Coordinate the collaboration

- Proceed while receiving teammates' completion and idle notifications. Check overall progress with TaskList.
- Request a review with SendMessage({to: "{teammate-2}"}, "Review the draft at {teammate-1}'s _workspace/01_...
  and tell me what to fix"). Pass the answer to {teammate-1} so it makes the revision. Do not send a revision request to a teammate whose phase is marked `once` after its effect has gone out: rule O6 of `state-ledger.md` section 3a.
  The agent keeps the earlier conversation, so you can narrow the scope in your instruction, as in "only section 2 of that draft from earlier."
- If teammates must discuss what they found, the leader relays the messages. Always leave artifacts as files.

**Where artifacts are saved:**

| Teammate | Output path |
|------|----------|
| {teammate-1} | `_workspace/{phase}_{teammate-1}_{artifact}.md` |
| {teammate-2} | `_workspace/{phase}_{teammate-2}_{artifact}.md` |

### Step 4: Artifact freeze

A named agent still receives messages after it reports completion. If it edits an artifact it already handed off while answering another teammate's late question, the next stage will read and work from the content as it was before the change. Do not block the messages teammates send each other to cross-check, because they can catch errors. Instead, freeze the artifacts (artifact freeze) each time you pass a stage boundary, so the files the next stage will read do not change midway.

1. Use TaskList and the completion notifications to confirm that every teammate responsible for the previous stage has reported completion.
2. Tell those teammates about the freeze with SendMessage. For example: "The {stage} artifacts are frozen. If something needs fixing afterward, do not edit the existing file; write it as a new version file such as `{phase}_{teammate}_{artifact}_v2.md` and tell the leader."
3. Record the artifact hashes. For example: `shasum _workspace/{phase}_* > _workspace/freeze_{phase}.sha` (`md5sum` also works)
4. In the prompt of the agent responsible for the next stage, pass the artifact paths together with the hash file path.

If the collaboration has several stages, follow the same procedure at each stage boundary.

### Step 5: Integration
1. Use TaskList to confirm that all tasks are finished.
2. Read each artifact with Read and apply the {integration/verification logic}.
3. Just before producing the final artifact, recompute the hashes, as with `shasum -c _workspace/freeze_{phase}.sha`, to confirm that the frozen artifacts have not changed. If a hash differs or a new version file has appeared, check what changed and decide whether to re-run the stages that read the content as it was before the change, except a stage marked `once`, which is never re-run to refresh it: tell the user its effect used the earlier content (rule O6 of `state-ledger.md` section 3a).
4. Produce the final artifact at `{output-path}/{filename}`.

### Step 6: Wrap-up
1. Leave `_workspace/` so that you can verify later and review the work process.
2. Summarize the results and report to the user.
   There is no procedure for dissolving the team. Agents end automatically when their work is done, and you can stop them with TaskStop if needed.

## Error handling

| Situation | Response |
|------|------|
| A teammate does not respond or has stopped | For a phase marked `once`, do not instruct it again or launch a replacement: run `resume` and follow rule O6 of `state-ledger.md` section 3a. Otherwise check status with SendMessage and instruct it again. If that still fails, launch the same custom type under a new name and pass the needed work context in the prompt. |
| The cause of the stop is usage limit exhausted, expired authentication, or permission denied | Retrying gives the same result, so do not instruct again or launch a replacement agent. Open the partial artifacts directly to confirm how far the work actually got, record the missing content as a file in `_workspace/`, and report to the user. For a usage limit, also tell the user when it resets. The leader reflects only facts it confirmed directly, and does not guess at agents' judgments (for example, which material was excluded and why). |
| More than half of the teammates failed | Tell the user and confirm whether to continue. |
| The time limit was exceeded | Proceed with the results received so far, and state in the report the areas that were not finished. |
| The data conflicts | Do not delete it; write it side by side with its sources. |
| Task status was reflected late | Check with TaskList, then update it directly with TaskUpdate. |
| A verdict whose `check` exits 3 (only where a worker judges a candidate) | The verdict belongs to another tree: treat it as not given, commit and start nothing from it, tell the user, and run the judging phase on the current tree when they agree. |

## Test scenarios

### Normal flow
1. When the user provides {input}, Step 2 launches {N} agents and registers {M} tasks.
2. In Step 3, feedback is exchanged {K} times; in Step 4 the artifacts are frozen, and in Step 5 the results are integrated.
3. Expected result: `{output-path}/{filename}` is created.

### Error flow
1. In Step 3, {teammate-2} does not respond.
2. Check status with SendMessage and instruct it again. If that still fails, launch a replacement agent named "{teammate-2}b" and pass it the existing artifact paths. (For a teammate whose phase is marked `once`, do neither: run `resume` and follow rule O6 of `state-ledger.md` section 3a.)
3. Write "{teammate-2} area: partially reworked" in the final report.
```

---

## Template C: Sub-agent delegation (Mode C)

```markdown
---
name: {domain}-orchestrator
description: "Delegates independent {domain} tasks to sub-agents. Use it when the user asks with any of {initial run keywords}, and also for follow-up work such as revising results, partial re-runs, updates, supplements, re-running, and improving previous results."
---

## Execution mode: Sub-agent delegation (Mode C)

## Delegation gate
Answer before Step 1, one line each. Any unclear answer means a single agent: skip the step that spawns workers, do the work in this context, and replace the `## Execution mode` heading above with `## Execution mode: Single agent` and the description's "Delegates ... to sub-agents" wording with a description of the work itself. If the user explicitly asked for a team, build it anyway and fill the Risks line.
- Independent units, or the order they hand off (name each hand-off artefact):
- What splitting buys (specialisation, parallel speed or a separate context):
- Write ownership (paths or resources per worker):
- Tools and permissions per worker, on each target surface:
- Synthesis owner and acceptance check:
- Partial, blocked and conflicting results are reported as:
- Outcome: single agent | delegate
- Risks (only when the user explicitly asked for a team): each unclear answer, stated

## Worker delegation notes (optional; keep only when the outcome is delegate)
- Eligible tasks:
- Forbidden overlaps (paths, resources, topics):
- Synthesis owner and what they accept:
- Conflicting-result rule:

## Work procedure

### Step 0: Check existing work
Check whether `_workspace/` exists to decide whether to run for the first time, re-run only part of it, or run fresh.
Then run the connector preflight from Template A Step 0, item 4, before spawning any sub-agent.

### Step 1: Preparation
Analyze the input and create `_workspace/`.

### Step 2: Parallel execution
Run this step only when the gate's outcome is delegate; dependent hand-offs are called one after another, each with the prior artefact path. For a single agent, the main agent does the work in this context (an agent file, if there is one, is its role brief) and Steps 3 and 4 apply to its own output.

Call the Agent tool N times at the same time in one message. They run in the background by default.

| Agent | `subagent_type` | Input | Artifact |
|---------|--------------|------|------|
| {agent-1} | {type} | {source} | `_workspace/{phase}_{agent}_{artifact}.md` |
| {agent-2} | {type} | {source} | `_workspace/{phase}_{agent}_{artifact}.md` |

In `{type}`, write the name of a custom type or a built-in type.

Wait for the completion notifications. The main agent does not repeat a search it already delegated.

### Step 3: Integration
1. Collect the return values and file artifacts, integrate them, and produce the final artifact.

### Step 4: Wrap-up
Leave `_workspace/` and summarize the results for the user.

## Error handling
- If one agent fails, retry once, except a phase marked `once` (never retried: run `resume` and follow rule O6 of `state-ledger.md` section 3a). If it fails again, state the missing piece and continue.
- Do not retry failures that give the same result when retried, such as usage limit exhausted, expired authentication, or permission denied. Open the partial artifacts directly to confirm how far the work actually got, record the missing content as a file in `_workspace/`, and report to the user. For a usage limit, also tell the user when it resets. The main agent reflects only facts it confirmed directly, and does not guess at agents' judgments.
- If more than half of the agents fail, tell the user and confirm whether to continue.
- A worker whose valid report is `partial` or `blocked`: keep what it returned, name the missing part in the final artifact and mark the result incomplete. Do not cover the missing part with a guess.
- A synthesis input that never arrives (a worker failed twice, or a branch has no report): mark each missing branch as missing in the final artifact and in the report. Do not write text that implies coverage the run lacks.

A verdict whose `check` exits 3 (only where a worker judges a candidate) is one more error-handling row of its own: treat it as not given, commit and start nothing from it, tell the user, and run the judging phase on the current tree when they agree.
```

Sources for the gate block, the notes block and the two error rows above: (adapted from references/meta_harness/.agents/skills/harness/references/orchestrator-template.md:78 (Apache-2.0); adapted from references/meta_harness/docs/architecture/handoffs.md:34 (Apache-2.0)).

---

## Combining execution modes stage by stage (mixed mode)

Use the suitable execution mode for each stage. Write `**Execution mode:**` at the top of each stage.

```markdown
## Execution mode: Mixed

| Stage | Execution mode | Reason for choice |
|------|----------|-----------|
| Step 1 (pre-check) | The main agent does it directly or delegates to a sub-agent | The task list must be fixed. |
| Step 2 (bulk collection and verification) | Workflow orchestration (Mode A) | A pre-fixed list must be processed in fan-out and adversarial verification must be run. |
| Step 3 (consensus and integration) | Persistent agent collaboration (Mode B) | Conflicting data must be discussed and reconciled. |
| Step 4 (independent verification) | Sub-agent delegation (Mode C) | One quality-verification agent verifying independently is enough. |
```

**Execution mode transition rules:**
- Workflow orchestration (Mode A) → Persistent agent collaboration (Mode B): Save the structured data the workflow returned in `_workspace/`, and write the file paths in the persistent agents' prompts.
- Persistent agent collaboration (Mode B) → Workflow orchestration (Mode A): After freezing the team artifacts (Step 4 of Template B), put the list of file paths into the script through `args`.
- At every point where the execution mode changes, write down the data-handoff path so the result of the previous stage is never left unfound.

---

## Writing principles that apply to every template

1. **State the execution mode at the very top of the document.** If it is a mixed mode, organize the execution mode of each stage in a table.
2. **In Workflow orchestration (Mode A), describe the script structure in detail.** State `phases`, the `schema` summary, and the items to put in `args` without omission.
3. **In Persistent agent collaboration (Mode B), describe in detail how to use `name`, SendMessage, and TaskCreate.** Include the list of agents to launch, the communication rules, the dependencies between tasks, and the artifact freeze procedure at stage boundaries.
4. **In Sub-agent delegation (Mode C), state the Agent parameters without omission.** Say whether it is a one-shot run with no `name` specified, and state `subagent_type`, `prompt`, and the output path.
5. **State file paths clearly.** Write paths relative to `_workspace/`, and name files by the `{phase}_{agent}_{artifact}.{ext}` convention.
6. **State the dependencies between stages.** At points where the execution mode changes, describe in particular detail how the data is handed over.
7. **Prepare for errors that can actually happen.** Do not assume every task succeeds; decide the handling for each situation.
8. **Always include test scenarios.** Write one normal scenario and at least one error scenario.
9. **Do not include items that existed only in v1.** If you referenced TeamCreate, TeamDelete, `team_name`, broadcast, or the experimental flag, it was written wrongly.
10. **Give every worker a self-contained brief and require a report you can check.** Paste the Delegation block below into the orchestrator once, at the step that launches or messages workers, and fill one brief per worker role.

## Delegation contract (every template that spawns or messages a worker)

A worker starts with an empty context: it sees its brief and the files the brief names, nothing else. A brief that points back at an earlier result hands your understanding to a reader who never had it, and a report that says "done" with nothing to open cannot be told from a guess. The block below fixes both ends. Paste it at the step that launches workers (Template A: before the `agent()` calls; B: team setup; C: Step 2) and fill the brief once per worker role. Never paste it into a `## Single-context fallback`: a role pass has no separate worker, and the fallback may not name `Agent` or `SendMessage` (`surfaces.md` section 5). (adapted from references/openharness/src/openharness/coordinator/coordinator_mode.py:407 (MIT); adapted from references/openhands/src/api/launch-child-conversation-client-tool.ts:32 (MIT))

Three phrases mark a brief that delegates understanding instead of stating it: "based on your findings", "based on the research" (also "the findings", "your research") and "as discussed" (also "as we discussed"). The first two come from the OpenHarness coordinator rules cited above; "as discussed" is not from any reference. `scripts/lint_harness.py` flags them as `lazy-delegation` in an agent file or a skill file that names `subagent_type`, `agentType`, `SendMessage`, `agent(`, `Agent(` or `Task(`; it reads only `agents/*.md` and `skills/**/SKILL.md`, so a brief kept in a `references/` file is not scanned. Keep the phrases out of the pasted block and out of every brief.

The Scope line points a worker that writes to its row in the `## Writers` table, which holds its ownership label. Fill that table and choose the labels with `write-safety.md` before you paste the block. (adapted from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0))

A phase marked `once` in the `## Handoff files` table (`state-ledger.md` section 3a) changes the Expected output line of its brief: the worker saves the file with its first section (what it will do, to whom, and a key built from the phase inputs, never from the time of the attempt) before its first outside call, passes the key to the connector when the connector takes one, and adds the last section only after the call is confirmed. A re-run that the user approves after a stop carries the same key. A `once` phase is also outside the retry-once rule of the Error handling section and outside the single re-ask of the Delegating block below: after a worker error, a timeout, an invalid report or `STATUS: partial`, do not launch or ask that worker again; run `state_ledger.py resume` and follow rule O6 of `state-ledger.md` section 3a (rule O7). Write that exception into the orchestrator's error table and into the step that checks reports, and never start a `once` phase from the `NEXT` line of `rebuild`, which prints no `HALF-DONE` line. (adapted from references/openrig/docs/as-built/architecture/coordination-primitive.md:46 (Apache-2.0))

A worker whose job is to judge a candidate (a QA agent, a reviewer, a judge) adds one line to the Expected output of its brief: its report opens with its verdict line, then a `CANDIDATE:` line copied from `candidate_id.py id`, then a `CARRIED:` line (`quality-gates.md` section 3-7). The orchestrator runs `id` before it spawns that worker and puts the line in the Inputs of the brief; the Report line of the block below stays as it is. Before the orchestrator commits, hands the verdict to the phase that consumes it, or resumes a run, it runs `candidate_id.py check` on the verdict file, in the step that checks reports. Exit 3 means the verdict was earned on another tree: the orchestrator treats it as not given, tells the user, and runs the judging phase on the current tree when they agree (rule R7 of `state-ledger.md` keeps a complete phase from starting unasked). Write that outcome into the orchestrator's error table as a row of its own, "a verdict whose `check` exits 3" (response: treat the verdict as not given, tell the user, run the judging phase on the current tree when they agree), and not only into the step that checks reports; the three Error handling sections above carry the row for a harness that has a worker judging a candidate. Compare the `EXCLUDES:` line that `check` prints entry by entry and ignore a trailing slash (`quality-gates.md` section 3-7, rule C2). A report with no `CANDIDATE:` line is valid under the block below and is not a ship verdict. Where no shell runs (chat, Cowork) the line reads `unverified` and any later edit voids the verdict. (adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0))

The three report states and the rule that a `complete` report needs evidence come from a fresh-agent loop that validates each round's report. (adapted from references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:112 (MIT)) The single bounded re-ask, with the error fed back, comes from a task guardrail retry loop; the cap of one is ours. (adapted from references/crewai/lib/crewai/src/crewai/task.py:1327 (MIT))

````markdown
### Delegating work

**Worker brief.** The `prompt` of every `Agent` call, `SendMessage` and `agent()` carries these five lines, filled in:

- Goal: one sentence, and what the result is for (the purpose tells the worker how deep to go).
- Inputs: the exact paths to read, with line numbers when the point is one place in a file. State the facts you already hold; never point at an earlier result in place of stating it.
- Scope: what the worker may write or change, and what it must not touch. Workers running in parallel get disjoint scopes. A worker that writes has a row in the orchestrator's `## Writers` table (batch, role, paths, ownership label); a role launched once per item has a per-item part such as `<item>` in its paths. The label is `enforced`, `workspace-enforced`, `advisory` or `serialised`; ownership counts as advisory unless something other than this brief blocks the write, so never call advisory ownership exclusive.
- Expected output: the file under `_workspace/` and the shape of its content.
- Report: end the reply with the Worker report below.

One task per call; never send the same task twice.

**Worker report.** Every worker ends its reply with:

```text
STATUS: complete | partial | blocked
SUMMARY: one or two sentences
EVIDENCE: one item per line that you can open or re-run (path:line, a command with its output, an artefact path)
NEXT STEPS: what remains (partial only)
BLOCKER: what is missing and what would unblock it (blocked only)
```

**Check before use.** In the step that integrates results, read each report before using anything from it:

| STATUS | Valid only when |
|--------|-----------------|
| complete | EVIDENCE has at least one item, and there is no BLOCKER or NEXT STEPS |
| partial | NEXT STEPS has at least one item, and there is no BLOCKER |
| blocked | BLOCKER names something concrete |

A missing STATUS line, a status outside the table, or a report that fails its row is invalid. Re-ask once: tell the worker which row it broke, in one sentence, and ask for the corrected report. Use `SendMessage` for a named worker; for a one-shot worker launch it once more with the same brief plus that sentence; in a Workflow script make one second `agent()` call the same way. If the second report is invalid too, do not ask again: record the result as unverified in `_workspace/`, say so in the final report, and take nothing from it as fact. This re-ask is the only retry for an invalid report; the general retry-once rule does not add a second. A `blocked` report with a concrete BLOCKER is valid; handle it with the error table, and do not retry authentication, permission or usage-limit failures.
````

Limits. The check confirms that an evidence item is present and never opens it, so an invented path passes (seen in 1 of 3 live runs); the orchestrator keeps reflecting only facts it confirmed itself. The check is prose the orchestrator follows, not code that runs; the `SendMessage` and Workflow branches are untested, and how a Mode A `schema` result carries STATUS is UNVERIFIED. The block does not pin the case of a status word, repeated STATUS lines or the literal `none` under NEXT STEPS or BLOCKER: live, `STATUS: Complete` and `none` lines were accepted and two STATUS lines were rejected, by the model's judgement. The lint knows a short phrase list; a paraphrase passes it.

## Follow-up request phrasings to put in `description`

To make this skill get selected not only on the first run but also when results are fixed or re-run, include the following phrasings.

- re-run, run again, update, revise, supplement
- "only the {part} of {domain} again"
- "based on the previous results", "improve the results"
- Request phrasings the domain commonly uses (for example, for a launch-strategy harness: "launch", "promotion", "trending")

Without follow-up request phrasings, this harness may not be selected again after the first run.
