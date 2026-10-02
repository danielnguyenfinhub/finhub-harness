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
     has not changed return cached results immediately, so the run costs little.
3. If you run fresh, receive a new `runId` and record it in `_workspace/run_meta.json`.

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
| An individual `agent()` fails (returns `null`) | Exclude it with `.filter(Boolean)` and record the number of excluded items with `log()`. State the missing items in the report as well. |
| The whole workflow fails | Check the actual return values in the `journal`, fix only the failed stage, and resume with `resumeFromRunId`. |
| Failures that retrying will not fix (usage limit exhausted, expired authentication, permission denied) | Do not retry or resume until the cause is cleared, because doing so only burns the remaining limit. Open the `journal` and the partial artifacts directly to confirm how far the run actually got, record the missing content as a file in `_workspace/`, and report to the user. For a usage limit, also tell the user when it resets. Once the cause is cleared, you can continue with `resumeFromRunId`. The main agent reflects only facts it confirmed directly, and does not guess at agents' judgments (for example, which material was excluded and why). |
| The result is empty | Do not mistake it for success. Check each agent's actual return value in the `journal`. |
| Conflicting data | Do not delete it; record it together with its sources. |

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
  and tell me what to fix"). Pass the answer to {teammate-1} so it makes the revision.
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
3. Just before producing the final artifact, recompute the hashes, as with `shasum -c _workspace/freeze_{phase}.sha`, to confirm that the frozen artifacts have not changed. If a hash differs or a new version file has appeared, check what changed and decide whether to re-run the stages that read the content as it was before the change.
4. Produce the final artifact at `{output-path}/{filename}`.

### Step 6: Wrap-up
1. Leave `_workspace/` so that you can verify later and review the work process.
2. Summarize the results and report to the user.
   There is no procedure for dissolving the team. Agents end automatically when their work is done, and you can stop them with TaskStop if needed.

## Error handling

| Situation | Response |
|------|------|
| A teammate does not respond or has stopped | Check status with SendMessage and instruct it again. If that still fails, launch the same custom type under a new name and pass the needed work context in the prompt. |
| The cause of the stop is usage limit exhausted, expired authentication, or permission denied | Retrying gives the same result, so do not instruct again or launch a replacement agent. Open the partial artifacts directly to confirm how far the work actually got, record the missing content as a file in `_workspace/`, and report to the user. For a usage limit, also tell the user when it resets. The leader reflects only facts it confirmed directly, and does not guess at agents' judgments (for example, which material was excluded and why). |
| More than half of the teammates failed | Tell the user and confirm whether to continue. |
| The time limit was exceeded | Proceed with the results received so far, and state in the report the areas that were not finished. |
| The data conflicts | Do not delete it; write it side by side with its sources. |
| Task status was reflected late | Check with TaskList, then update it directly with TaskUpdate. |

## Test scenarios

### Normal flow
1. When the user provides {input}, Step 2 launches {N} agents and registers {M} tasks.
2. In Step 3, feedback is exchanged {K} times; in Step 4 the artifacts are frozen, and in Step 5 the results are integrated.
3. Expected result: `{output-path}/{filename}` is created.

### Error flow
1. In Step 3, {teammate-2} does not respond.
2. Check status with SendMessage and instruct it again. If that still fails, launch a replacement agent named "{teammate-2}b" and pass it the existing artifact paths.
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

## Work procedure

### Step 0: Check existing work
Check whether `_workspace/` exists to decide whether to run for the first time, re-run only part of it, or run fresh.

### Step 1: Preparation
Analyze the input and create `_workspace/`.

### Step 2: Parallel execution
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
- If one agent fails, retry once. If it fails again, state the missing piece and continue.
- Do not retry failures that give the same result when retried, such as usage limit exhausted, expired authentication, or permission denied. Open the partial artifacts directly to confirm how far the work actually got, record the missing content as a file in `_workspace/`, and report to the user. For a usage limit, also tell the user when it resets. The main agent reflects only facts it confirmed directly, and does not guess at agents' judgments.
- If more than half of the agents fail, tell the user and confirm whether to continue.
```

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

## Follow-up request phrasings to put in `description`

To make this skill get selected not only on the first run but also when results are fixed or re-run, include the following phrasings.

- re-run, run again, update, revise, supplement
- "only the {part} of {domain} again"
- "based on the previous results", "improve the results"
- Request phrasings the domain commonly uses (for example, for a launch-strategy harness: "launch", "promotion", "trending")

Without follow-up request phrasings, this harness may not be selected again after the first run.
