# Real-World Team Composition Examples
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

Each example shows the criteria for choosing the execution mode that fits the work, along with the basic form of Harness v2 syntax. Mode definitions are in `execution-modes.md`, and how to write workflow scripts is in `workflow-recipes.md`.

---

## Example 1: Comprehensive research team (Workflow orchestration, Mode A)

**Composition:** Fan-out/fan-in + adversarial verification

**Why this choice:** The perspectives to research can be listed in advance, and the procedure of verifying each claim can be fixed in code.

```
[Main] Pre-survey: fix the research perspectives (official sources, press, community, background)
     → Workflow(script, args: {axes, topic, ws})
         phase 'Research': pipeline(axes, axis => agent(..., {schema: FINDINGS}))
         phase 'Verify': launch adversarial verification agents per claim → only claims that a majority judge confirmed pass
         phase 'Synthesis': launch one omission reviewer → if a perspective is missing, run additional research
     → The main agent writes the comprehensive report from the returned structured result
```

Define the research principles and the structured output format in `.claude/agents/researcher.md`, and the verification principle that puts refutation first in `.claude/agents/fact-checker.md`. In the workflow, specify the two agents through `agentType`.

Do not arbitrarily discard one side of conflicting information. Carry it in the return schema together with its sources.

## Example 2: Sci-fi novel writing team (mixed mode centered on persistent agents)

**Composition:** Pipeline + producer-reviewer

**Why this choice:** The worldbuilding, characters, and plot must be coordinated in real time so they do not contradict one another, so each specialist must remember earlier conversation context. The reviewers, on the other hand, only need to deliver results from independent perspectives, so sub-agents are enough.

```
Stage 1 (persistent agents): launch Agent(name: "worldbuilder") + Agent(name: "character-designer")
               + Agent(name: "plot-architect") in parallel
               → TaskCreate(worldbuilding, characters, plot, with their mutual dependencies stated)
               → The leader relays: worldbuilder fixes the social structure
                 → pass it to character-designer with SendMessage
                 → if a character's occupation group conflicts with the worldbuilding, ask
                   worldbuilder to adjust with SendMessage
                 Because the earlier context remains, you can instruct a partial fix such as
                 "in the class structure we set earlier, change only the merchant class."
Stage 2 (sub-agent): call prose-stylist once → read the three artifacts saved in _workspace/ and write the draft
Stage 3 (sub-agents in parallel): science-consultant + continuity-manager each review
Stage 4 (persistent agent): you cannot send SendMessage to a prose-stylist that was called only once.
                 If you launched it with a name in Stage 2, you can instruct it to reflect the review results.
                 If revisions are likely to repeat, give it a name from the start.
```

Give a `name` from the first launch to any agent that may receive revision requests again. An agent called only once cannot continue using the earlier conversation context.

## Example 3: Comprehensive code review (Workflow orchestration, Mode A)

**Composition:** Fan-out/fan-in + adversarial verification

**Why this choice:** The review perspectives, such as security, performance, structure, and testing, can be set in advance, and the procedure of verifying each item found again can be expressed in code.

```javascript
// Review per perspective → adversarial verification for each item found
// Do not wait for the whole review. When the security review finishes, even if the performance review is still running,
// verify the problems found in the security area right away.
const FINDINGS = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'object',
    required: ['title', 'file', 'evidence'], properties: {
      title: { type: 'string' }, file: { type: 'string' }, evidence: { type: 'string' } } } } } }
const VERDICT = { type: 'object', required: ['status', 'reason'], properties: {
  status: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
  reason: { type: 'string' } } }
const results = await pipeline(
  [
    { key: 'security', prompt: 'Review from the security perspective.' },
    { key: 'perf', prompt: 'Review from the performance perspective.' },
    { key: 'arch', prompt: 'Review from the structure perspective.' },
    { key: 'test', prompt: 'Review from the testing perspective.' },
  ],
  d => agent(d.prompt, { phase: 'Review', schema: FINDINGS }),
  r => parallel((r?.findings ?? []).map(f => () =>
    agent(`Verify the following finding. Judge it confirmed if the evidence is sufficient, refuted if it is clearly rebutted, and uncertain if it is hard to decide: ${JSON.stringify(f)}`,
      { phase: 'Verify', schema: VERDICT })
      .then(verdict => ({ ...f, verdict }))))
)
const confirmed = results.flat().filter(Boolean)
  .filter(f => f.verdict?.status === 'confirmed')
```

In v1 you used a persistent team in which reviewers shared findings with each other through `SendMessage`. If a single finding can be verified on its own, as in the example above, put enough of that finding's evidence in the prompt and verify it right away. If it must be compared with findings from other perspectives, collect the whole review result and verify it behind a synchronization barrier. Use persistent agents only when real-time conversation is essential, such as debating a design direction.

## Example 4: Large-scale code migration (persistent supervisor collaboration or Workflow orchestration)

**Composition:** Fan-out/fan-in if it can be split in advance, supervisor if it must be re-split during the run

**Selection criterion:** Choose the execution mode by whether the work batches can be split in advance.

If the work batches can be fixed in advance, use a workflow.

```javascript
const MIGRATION_RESULT = { type: 'object', required: ['worktreePath', 'changedFiles'], properties: {
  worktreePath: { type: 'string', minLength: 1 },
  changedFiles: { type: 'array', minItems: 1, uniqueItems: true,
    items: { type: 'string', minLength: 1 } } } }
const MIGRATION_VERDICT = { type: 'object', required: ['status', 'reason'], properties: {
  status: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
  reason: { type: 'string' } } }
const migrated = await pipeline(args.batches,   // estimate complexity in a pre-survey, then fix the work batches
  b => agent(`Migrate the following work batch, and return the absolute path of the isolated worktree and the list of files actually changed: ${b.files.join(', ')}`,
    { agentType: 'migrator', isolation: 'worktree', schema: MIGRATION_RESULT }),
  (r, b) => r && agent(
    `In the isolated worktree ${r.worktreePath}, compare the migration targets against the files actually changed, and verify omissions and errors. Original targets: ${b.files.join(', ')}. Actual changes: ${r.changedFiles.join(', ')}`,
    { agentType: 'qa-inspector', schema: MIGRATION_VERDICT })
    .then(verdict => ({ ...r, verdict })))
const confirmed = migrated.filter(Boolean)
  .filter(r => r.verdict?.status === 'confirmed')
return { confirmed }
```

Always pass the adversarial verification agent the path of the isolated worktree that holds the migration result. When the workflow ends, the main agent checks the `worktreePath` of each `confirmed` result one by one, and either merges the change into the base branch or cherry-picks only the commits it needs. If a conflict arises, resolve it before merging the next worktree, and apply the next change only after the integration tests pass. Do not merge `refuted` or `uncertain` results; report the reason they are missing.

If the work must be re-split according to progress, use persistent agents.

```
The leader registers work batches with TaskCreate (including depends_on)
→ Launch Agent(name: "migrator-1"), Agent(name: "migrator-2"), Agent(name: "migrator-3") in parallel
→ Check the result each time a completion notification arrives
→ For a failed task, confirm the cause with SendMessage, then reassign it with TaskUpdate
→ When all are done, run the integration tests
```

## Example 5: Webtoon production (persistent producer and one-shot reviewer)

**Composition:** Producer-reviewer

**Why this choice:** Only one producer and one reviewer are needed. Sending the review result back to the producer at most twice is enough, so a light mixed mode suffices.

```
Stage 1: Agent(name: "artist") → generate panels → _workspace/panels/
Stage 2: call Agent(subagent_type: "webtoon-reviewer", prompt: "Review the panels") once → PASS/FIX/REDO verdict
       → _workspace/review_report.md
Stage 3: instruct regeneration with SendMessage({to: "artist"}) only for panels that received a REDO verdict
       Repeat at most twice. Because the artist remembers the earlier context,
       you can narrow the scope, as in "fix only the composition of panel 3."
Retry policy: if a panel still does not pass after two fixes, tell the user the unresolved state and the cause.
             If 50% or more of all panels are REDO, suggest that the user revise the prompt.
```

---

## How to save artifacts

- **Agent definitions:** Create them at `project/.claude/agents/{name}.md`. Always include the core roles, working principles, input and output rules, how to call again, error handling, and collaboration method. Add communication rules for persistent agents, and the structured output format for agents used in workflows.
- **Skills:** Create them at `project/.claude/skills/{name}/SKILL.md`, and add `references/` and `scripts/` if needed.
- **Orchestrator:** Always state the execution mode. Use the templates in `orchestrator-template.md`.
- **Intermediate artifacts:** Save them in the form `_workspace/{phase}_{agent}_{artifact}.{ext}` and keep them even after verification is done.
