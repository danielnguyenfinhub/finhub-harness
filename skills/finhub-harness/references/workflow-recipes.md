# Workflow Recipes: Script Skeletons and Pitfalls
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

This document explains the script patterns you can put in an orchestration skill when you build a harness in Workflow orchestration (Mode A). Write scripts in plain JavaScript and pass them through the `script` parameter of the `Workflow` tool.

---

## Table of contents

1. [Basic skeleton](#1-basic-skeleton)
2. [Fan-out and adversarial verification](#2-fan-out-and-adversarial-verification)
3. [Judge panel](#3-judge-panel)
4. [Loop-until-dry](#4-loop-until-dry)
5. [Token-budget-driven loop](#5-token-budget-driven-loop)
6. [Custom type with structured output](#6-custom-type-with-structured-output)
7. [Pitfalls checklist](#7-pitfalls-checklist)

---

## 1. Basic skeleton

A complete runnable script starts with a `meta` literal. The title you use in a `phase()` call must exactly match a `title` in `meta.phases`.

```javascript
export const meta = {
  name: 'domain-task',
  description: 'One-line description (shown in the permission dialog)',
  phases: [
    { title: 'Collect', detail: 'Research in parallel for each perspective' },
    { title: 'Verify', detail: 'For each finding, look for evidence that refutes it' },
  ],
}

phase('Collect')
const raw = await pipeline(args.items, item =>
  agent(`...${item}...`, { label: `collect:${item}`, phase: 'Collect', schema: COLLECT_SCHEMA }))

phase('Verify')
// ...

return { result }   // the final return value is passed to the main agent
```

**Principles:**
- **Use `pipeline()` by default, and use `parallel()` only when a synchronization barrier is truly needed.** A synchronization barrier is needed only when the next stage must compare **all** results of the previous stage with each other. De-duplication, early exit when the overall result is 0 items, and prompts that say "compare with the other findings" are examples.
- Do not write the values of the item list directly into the script. Where possible, have the main agent pass the list it fixed during its pre-survey as `args.items`.
- If you need a timestamp, pass it as `args.now`. `Date.now()` is not available.

## 2. Fan-out and adversarial verification

Collect review results from each perspective, then verify the results one by one. Do not wait for the research of other perspectives to finish; as soon as the research for one perspective finishes, verify the results from that perspective.

```javascript
export const meta = {
  name: 'review-fanout-verify',
  description: 'Review from each perspective, then verify each finding by looking for evidence that refutes it',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
}

const FINDINGS = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'object',
    required: ['title', 'file', 'evidence'], properties: {
      title: { type: 'string' }, file: { type: 'string' }, evidence: { type: 'string' } } } } } }
const VERDICT = { type: 'object', required: ['status', 'reason'], properties: {
  status: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
  reason: { type: 'string' } } }

const results = await pipeline(
  args.dimensions,   // e.g. [{key:'security', prompt:'...'}, {key:'perf', prompt:'...'}]
  d => agent(d.prompt, { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS }),
  review => parallel((review?.findings ?? []).map(f => () =>
    agent(`Verify the following review finding. Judge it confirmed if the evidence is sufficient, refuted if it is clearly rebutted, and uncertain if it is hard to decide: ${JSON.stringify(f)}`,
      { label: `verify:${f.file}`, phase: 'Verify', schema: VERDICT })
      .then(v => ({ ...f, verdict: v }))))
)
const confirmed = results.flat().filter(Boolean)
  .filter(f => f.verdict?.status === 'confirmed')
log(`${confirmed.length} of ${results.flat().filter(Boolean).length} findings passed verification.`)
return { confirmed }
```

To make verification stricter, launch three adversarial verification agents for each finding. Pass only the findings that at least two of them judge `confirmed` (evidence sufficient). If you give each agent a different verification criterion, such as correctness, security, and reproducibility, you can find a wider variety of problems than by checking repeatedly against the same criterion.

## 3. Judge panel

This pattern is for design work with many possible solutions. Produce N independent drafts, judge them in parallel, and build the final version from the judging results.

```javascript
export const meta = {
  name: 'design-judge-panel',
  description: 'Produce N independent drafts, judge them, and write the final version based on the top-scoring draft',
  phases: [{ title: 'Drafts' }, { title: 'Judging' }, { title: 'Synthesis' }],
}

const angles = args.angles?.length
  ? args.angles
  : ['MVP-first', 'risk-management-first', 'user-experience-first']
const judgeCount = args.judgeCount ?? 3

phase('Drafts')
const drafts = (await parallel(angles.map(a => () =>
  agent(`Write a draft independently from the ${a} perspective: ${args.brief}`,
    { label: `draft:${a}`, phase: 'Drafts' }))))
  .filter(Boolean)
log(`Produced ${drafts.length} of ${angles.length} drafts.`)
if (!drafts.length) return { error: 'There are no completed drafts.', drafts: [] }

phase('Judging')   // synchronization barrier needed: all drafts must be compared with each other
const SCORE = { type: 'object', required: ['scores'], properties: {
  scores: { type: 'array', items: { type: 'object',
    required: ['index', 'score', 'strengths'], properties: {
      index: { type: 'integer' }, score: { type: 'number' }, strengths: { type: 'string' } } } } } }
const judged = (await parallel(Array.from({ length: judgeCount }, (_, j) => () =>
  agent(`Score the following ${drafts.length} drafts:\n${drafts.map((d, i) => `[${i}] ${d}`).join('\n---\n')}`,
    { label: `judge:${j}`, phase: 'Judging', schema: SCORE })))).filter(Boolean)
log(`Received results from ${judged.length} of ${judgeCount} judges.`)
if (!judged.length) return { error: 'There are no completed judging results.', drafts }

phase('Synthesis')
const ranked = drafts.map((_, i) => {
  const scores = judged.flatMap(r =>
    r.scores.filter(x => x.index === i).map(x => x.score)).filter(Number.isFinite)
  return scores.length
    ? { index: i, average: scores.reduce((sum, score) => sum + score, 0) / scores.length }
    : null
}).filter(Boolean)
if (!ranked.length) return { error: 'There are no valid per-draft scores.', drafts, judged }
const winner = ranked.reduce((best, item) =>
  item.average > best.average ? item : best).index
const finalDraft = await agent(
  `Write the final version based on the draft that received the highest score. Also reflect the strengths of the other drafts where needed.\nTop-scoring draft:\n${drafts[winner]}\nJudges' comments:\n${JSON.stringify(judged)}`,
  { phase: 'Synthesis' })
if (!finalDraft) {
  log('Could not write the final version.')
  return { error: 'Could not write the final version.', drafts, judged, winner }
}
return finalDraft
```

## 4. Loop-until-dry

Use this for work where you cannot know in advance how many items must be found. Repeat the search until no new item appears for K consecutive rounds.

The code in sections 4 to 6 is a snippet that goes into the basic skeleton of section 1. When you use it as a full script, put `meta` at the very top and define the phase titles and schemas it uses.

```javascript
const finders = args.finders ?? []
const dryLimit = args.dryRuns ?? 2
const findingKey = finding => JSON.stringify([
  finding.file ?? '', finding.title ?? '', finding.evidence ?? ''
])
const seen = new Set(), confirmed = []
if (!finders.length) return { confirmed, error: 'There are no search criteria.' }
let dry = 0
while (dry < dryLimit) {
  const found = (await parallel(finders.map(f => () =>
    agent(f.prompt, { phase: 'Explore', schema: FINDINGS })))).filter(Boolean).flatMap(r => r.findings)
  const fresh = found.filter(b => !seen.has(findingKey(b)))   // Judge duplicates by seen. Do not use confirmed as the basis.
  if (!fresh.length) { dry++; continue }
  dry = 0
  fresh.forEach(b => seen.add(findingKey(b)))
  const judged = await parallel(fresh.map(b => () =>
    agent(`Verify the following review finding. Judge it confirmed if the evidence is sufficient, refuted if it is clearly rebutted, and uncertain if it is hard to decide: ${JSON.stringify(b)}`,
      { phase: 'Verify', schema: VERDICT })
      .then(v => ({ b, ok: v?.status === 'confirmed' }))))
  confirmed.push(...judged.filter(Boolean).filter(x => x.ok).map(x => x.b))
  log(`${confirmed.length} items confirmed so far, and this round found ${fresh.length} new items.`)
}
return { confirmed }
```

If you de-duplicate against `confirmed`, items rejected in verification reappear every round, so the loop never ends. De-duplicate against `seen`, which holds every item found even once.

## 5. Token-budget-driven loop

In a session where the user specified a token budget such as "+500k", you can adjust the search scope automatically according to the remaining budget. In an unlimited session with no `budget.total`, `remaining()` returns `Infinity`, so always check in the condition that `budget.total` exists first.

```javascript
const findings = []
while (budget.total && budget.remaining() > 50_000) {
  const r = await agent('Carry out the following search task.', { schema: FINDINGS })
  if (r) findings.push(...r.findings)
  log(`Found ${findings.length} items so far, and the remaining token budget is ${Math.round(budget.remaining() / 1000)}k.`)
}
// To fix the scale of the work in advance: const FLEET = budget.total ? Math.floor(budget.total / 100_000) : 3
```

## 6. Custom type with structured output

Use the `.claude/agents/{name}.md` definitions the harness built directly in the workflow.

```javascript
const r = await agent(
  `Verify the file _workspace/02_draft.md and return the findings`,
  { agentType: 'qa-inspector',      // .claude/agents/qa-inspector.md
    schema: FINDINGS,               // a custom type also returns only results that match the given schema
    effort: 'high' })               // it is good to raise reasoning effort in the verification stage
```

- If you omit `agentType`, the default workflow sub-agent is used.
- Choose `model` by the nature of the work in each stage. Use `sonnet` for repetitive collection and conversion stages, `opus` for in-depth verification, judging, and design stages, and `fable` for overall-planning and long-running stages. See `model-selection-guide.md` for detailed criteria.
- If several agents might edit files at the same time and conflict, set `isolation: 'worktree'`. Preparing the working environment has a cost, so use it only when a conflict is actually likely.

## 7. Pitfalls checklist

Check the list below when you verify a workflow script in Step 6-2 of the harness.

| Pitfall | Problem that appears | Prevention |
|------|------|------|
| Using variables or operations in `meta` | The script cannot be parsed. | Put only literals in `meta`. |
| Using TypeScript syntax (`: string[]`, etc.) | The script cannot be parsed. | Write in plain JavaScript. |
| Using `Date.now()` / `Math.random()` / `new Date()` | An error occurs because of the resume-protection feature. | Pass timestamps and seeds through `args`, and if you need randomness, write the prompt differently by index. |
| Missing `.filter(Boolean)` | The `null` returned by a failed agent stops the next stage. | Apply `.filter(Boolean)` before using the result of `parallel()` or `pipeline()`. |
| Unnecessary synchronization barrier | Agents that finish early wait for slow agents, so the total run time grows. | If you do not need to compare all results with each other, rewrite it with `pipeline()`. |
| `phase` title mismatch | Progress is not displayed in the intended groups. | Make the `phase()` call match the `title` in `meta.phases`. |
| Calling the global `phase()` inside a parallel stage | The groups used to display progress conflict with each other. | Specify `opts.phase` explicitly inside the stage. |
| De-duplicating against `confirmed` | Rejected items reappear and the loop never ends. | De-duplicate against the `seen` set. |
| Missing `budget.total` check in a token-budget loop | In an unlimited session, `agent()` keeps running until the per-workflow call cap is reached. | Use the condition `while (budget.total && ...)`. |
| Processing only part of the scope without saying so | It processes only the top N and still reports "all done." | State the number of unprocessed items in `log()`. |
| Not checking the run record (`journal`) when diagnosing results | An empty result taken from the cache is mistaken for success. | Before diagnosing a completed workflow, check the `journal` in the run history (`transcript`) directory. |
| Writing the script to a file first | You go through a step you do not need. | Pass the script content directly in `script`. The file is preserved automatically when you call it, and when you revise repeatedly, `Edit` the preserved file and call again with `scriptPath`. |
