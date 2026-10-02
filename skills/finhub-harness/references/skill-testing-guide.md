# Skill Testing and Iterative Improvement Guide
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

This guide explains how to verify the quality of skills built with the harness and improve them over several iterations. It supplements Step 6 of `SKILL.md`.

---

## Table of Contents

1. [Testing approach overview](#1-testing-framework-overview)
2. [Writing test prompts](#2-writing-test-prompts)
3. [Comparing with-skill runs and baseline runs](#3-running-tests-with-skill-vs-baseline)
4. [Running A/B tests as a workflow (v2)](#4-workflow-based-ab-v2)
5. [Quantitative evaluation with assertions](#5-quantitative-evaluation-assertion-based-grading)
6. [Using specialist agents](#6-using-specialist-agents)
7. [Iterative improvement procedure](#7-iterative-improvement-loop)
8. [Verifying `description` trigger conditions](#8-description-trigger-verification)
9. [Test working directory structure](#9-workspace-structure)

---

<a id="1-testing-framework-overview"></a>

## 1. Testing approach overview

Verify skill quality using **qualitative evaluation, in which a person judges the output** together with **quantitative evaluation, in which assertions grade the output**.

| Evaluation type | Method | Suitable skills |
|----------|------|-----------|
| **Qualitative evaluation** | The user reviews the output directly. | Skills where judging quality needs human assessment, such as writing style, design and creative work |
| **Quantitative evaluation** | Grade automatically against assertions. | Skills whose results can be checked objectively, such as file creation, data extraction and code generation |

Proceed in this order: **write → run tests → evaluate → improve → test again**.

## 2. Writing test prompts

### Writing principles

Write test prompts as **concrete, natural sentences that a real user would plausibly type**. Abstract or deliberately contrived prompts make it hard to tell whether the skill works well in real use.

**Bad examples:** `"Process the PDF"`, `"Extract the data"`

**Good example:**

```
"In 'Q4_sales_final_v2.xlsx' in my Downloads folder, use column C (revenue) and
column D (cost) to add a profit margin (%) column. Then sort in descending order
by profit margin."
```

### How to vary the prompts

- Mix formal and casual wording.
- Mix requests that state the intent directly with requests where the intent must be inferred from context. For example, include both cases where the file format is stated outright and cases where it must be inferred from context.
- Mix simple and complex tasks, and put abbreviations, typos and everyday expressions into some prompts.

### Scope of use cases to include

Start with two or three prompts. Always include one core use case and one edge case, and add one case that asks for several tasks at once if needed.

<a id="3-running-tests-with-skill-vs-baseline"></a>

## 3. Comparing with-skill runs and baseline runs

### 3-1. How to compare the two runs

For each test prompt, launch two sub-agents **at the same time** in a single message.

- **With-skill run**: Read the skill, do the task, and save the result to `_workspace/iteration-N/eval-{id}/with_skill/outputs/`.
- **Baseline run**: Handle the same prompt without the skill and save the result to `_workspace/iteration-N/eval-{id}/without_skill/outputs/`.

### 3-2. How to choose the baseline run

| Situation | Baseline run |
|------|----------|
| Creating a new skill | Run the same prompt without the skill. |
| Improving an existing skill | Preserve the pre-change skill as a separate copy and use it. |

### 3-3. Recording run time and token usage

When a sub-agent's completion notification arrives, save `total_tokens` and `duration_ms` **immediately**. Both values are available only at the moment the completion notification arrives and cannot be recovered later.

<a id="4-workflow-based-ab-v2"></a>

## 4. Running A/B tests as a workflow (v2)

If there are three or more test cases, or the verification must be repeated several times, build the A/B test itself as a workflow script. Use it only when the user has agreed to run the tests.

```javascript
export const meta = {
  name: 'skill-ab-test',
  description: 'Run the with-skill and baseline runs, then grade them anonymously',
  phases: [{ title: 'Run' }, { title: 'Grade' }],
}
const RUN_RESULT = { type: 'object', required: ['saved', 'files'], properties: {
  saved: { type: 'boolean' },
  files: { type: 'array', minItems: 2, items: { type: 'string', minLength: 1 } } } }
const SLOT_GRADE = { type: 'object', required: ['expectations', 'summary'], properties: {
  expectations: { type: 'array', items: { type: 'object',
    required: ['text', 'passed', 'evidence'], properties: {
      text: { type: 'string' }, passed: { type: 'boolean' }, evidence: { type: 'string' } } } },
  summary: { type: 'object', required: ['passed', 'failed', 'total', 'pass_rate'], properties: {
    passed: { type: 'integer' }, failed: { type: 'integer' }, total: { type: 'integer' },
    pass_rate: { type: 'number' } } } } }
const GRADE = { type: 'object', required: ['A', 'B', 'comparison'], properties: {
  A: SLOT_GRADE,
  B: SLOT_GRADE,
  comparison: { type: 'object', required: ['preferred', 'reason'], properties: {
    preferred: { type: 'string', enum: ['A', 'B', 'tie'] },
    reason: { type: 'string' } } } } }

const results = await pipeline(
  args.evals,   // [{id, prompt, assertions, skillPath, withSkillSlot: 'A' | 'B'}]
  e => {
    const withSkillSlot = e.withSkillSlot === 'B' ? 'B' : 'A'
    const baselineSlot = withSkillSlot === 'A' ? 'B' : 'A'
    return parallel([
      () => agent(
        `${e.prompt}\n\nFirst read and follow ${e.skillPath}. Save the output to ${args.ws}/${e.id}/with_skill/outputs/, and save the same files to ${args.ws}/${e.id}/blind/${withSkillSlot}/outputs/ as well. Return every saved file path.`,
        { label: `with-skill:${e.id}`, phase: 'Run', schema: RUN_RESULT }),
      () => agent(
        `${e.prompt}\n\nSave the output to ${args.ws}/${e.id}/without_skill/outputs/, and save the same files to ${args.ws}/${e.id}/blind/${baselineSlot}/outputs/ as well. Return every saved file path.`,
        { label: `baseline:${e.id}`, phase: 'Run', schema: RUN_RESULT }),
    ])
  },
  (runs, e) => {
    const completed = (runs ?? []).filter(Boolean)
    if (completed.length !== 2 || completed.some(r => !r.saved || r.files.length < 2)) {
      log(`${e.id}: the outputs of the with-skill run and the baseline run are not both ready, so grading is skipped.`)
      return null
    }
    return agent(
      `First confirm that outputs exist in both ${args.ws}/${e.id}/blind/A/outputs/ and ${args.ws}/${e.id}/blind/B/outputs/. If either path is empty, do not grade; report the reason for the failure. If both outputs exist, grade A and B separately and judge which is better as one of A, B or tie. To preserve anonymity, do not open eval_metadata.json, with_skill/ or without_skill/. Assertions: ${JSON.stringify(e.assertions)}`,
      { label: `grade:${e.id}`, phase: 'Grade', schema: GRADE })
      .then(grade => {
        if (!grade) log(`${e.id}: no anonymous grading result was received, so this case is skipped.`)
        return grade
      })
  }
)
const mapped = results.map((grade, index) => {
  if (!grade) return null
  const e = args.evals[index]
  const withSkillSlot = e.withSkillSlot === 'B' ? 'B' : 'A'
  const baselineSlot = withSkillSlot === 'A' ? 'B' : 'A'
  return {
    evalId: e.id,
    withSkill: grade[withSkillSlot],
    baseline: grade[baselineSlot],
    comparison: {
      preferred: grade.comparison.preferred === 'tie'
        ? 'tie'
        : grade.comparison.preferred === withSkillSlot ? 'with_skill' : 'baseline',
      reason: grade.comparison.reason,
    },
  }
}).filter(Boolean)
return { results: mapped }
```

The main agent alternates `withSkillSlot` between A and B for each test case. The grader reads only the neutral `blind/A/` and `blind/B/` paths, so it cannot tell which side had the skill applied. Only cases whose two outputs are both ready are graded, and when grading finishes, the main agent maps the A/B results back to the with-skill run and the baseline run. Save the mapped results to `grading.json` in each run directory. Grading starts the moment a single test case finishes, so there is no need to wait until all cases are done. After you modify the skill and re-run with `resumeFromRunId`, unchanged cases use cached results and are skipped.

<a id="5-quantitative-evaluation-assertion-based-grading"></a>

## 5. Quantitative evaluation with assertions

### 5-1. Writing assertions

A **good assertion** can be judged true or false objectively, tells you what it checks from its wording alone, and measures a result that should improve when the skill is applied. A bad assertion is one that always passes even without the skill (for example, "the output exists") or one that needs a person's subjective judgement (for example, "it is well written").

### 5-2. Assertions that code can check

Write assertions that code can verify as scripts. A script is faster than checking by eye and its results are more reliable, and the same script can be reused when the iteration changes.

### 5-3. Beware of assertions with no discriminating power

An assertion that both the with-skill run and the baseline run pass 100% of the time does not measure the difference the skill makes. When you find one, delete it or replace it with a condition strict enough to expose the difference between the two runs.

### 5-4. Grading result schema

Follow the `grading.json` format defined in `skill-writing-guide.md` (`text`/`passed`/`evidence` and `summary`).

<a id="6-using-specialist-agents"></a>

## 6. Using specialist agents

| Role | What it does | When to use |
|------|--------|------------|
| **Grader** | Records whether each assertion passed and the evidence for it, cross-checks the factual claims in the output, and also reviews the quality of the assertions themselves. | Every iteration |
| **Blind comparator** | Hides which output had the skill applied, shuffles the A/B order, and compares the quality of the two outputs. | When you need to confirm rigorously that the new version is really better |
| **Analyzer** | Analyses statistical patterns such as assertions with no discriminating power, evaluation cases with high variance in results, and the trade-off between time and token usage. | After three or more iterations of results have accumulated |

<a id="7-iterative-improvement-loop"></a>

## 7. Iterative improvement procedure

### 7-1. Improvement principles

1. **Generalise the feedback.** Fixing the skill to fit a single test case causes overfitting. Fix it with a principle that applies to other cases as well.
2. **Delete instructions that do not help.** Read the agents' work logs, and if the skill is making them do unnecessary work, remove that instruction.
3. **Explain the reason.** Even for short feedback, work out why it matters, then edit the skill so that reason shows.
4. **Add the tools that repeated work needs up front.** If every test creates the same helper script from scratch, put that script in `scripts/`.

### 7-2. Iteration order

```
1. Modify the skill.
2. Re-run all test cases in a new `iteration-{N+1}/` directory.
3. Present the results compared with the previous iteration to the user.
4. Take the feedback, revise again, and repeat the same order.
```

**Stop conditions:** Stop when the user is satisfied, when there is no feedback left to apply, or when no further meaningful improvement is possible.

### 7-3. Re-read the draft with fresh eyes

When you revise a skill, first write a draft. Then read the draft again from the start as a reviewer seeing it for the first time, and fix it. Do not try to write it perfectly from the start.

<a id="8-description-trigger-verification"></a>

## 8. Verifying `description` trigger conditions

### 8-1. Writing requests to evaluate triggering

Create 20 evaluation requests: 10 `should-trigger` requests, for which the skill must run, and 10 `should-NOT-trigger` requests, for which it must not.

**Criteria for writing evaluation requests:**

- Write concrete, natural sentences that a real user would plausibly type.
- Include concrete details such as file paths, the user's situation, column names and company names.
- Concentrate on **borderline cases** where it is hard to judge whether the skill applies, rather than cases with an obvious answer.

**`should-trigger`:** Include requests that express the same intent in several ways, requests that do not state the file type but clearly need this skill, uncommon use cases, and requests that overlap with other skills but should choose this one.

**`should-NOT-trigger`:** **Near misses, which look similar in wording but are not what the skill is for, matter most.** Include requests that use similar words but are better served by another tool or skill. Clearly unrelated requests are not worth testing.

### 8-2. Checking for conflicts with existing skills

1. Collect the `description` of every existing skill.
2. Check that the new skill's `should-trigger` requests do not wrongly trigger an existing skill.
3. If a conflict arises, state the scope and the exclusions in the `description` more clearly.

### 8-3. Automatic optimisation (optional, advanced)

1. Split the 20 evaluation requests into 60% training (Train) and 40% test (Test).
2. Measure the trigger accuracy of the current `description`.
3. Analyse the failed cases and improve the `description`.
4. Pick the best-performing `description` by the results on the **test set (Test set)**. Picking by the results on the training set causes overfitting.
5. Repeat this process up to five times.

> Check with a script that automates headless execution (`claude -p`). It uses many tokens, so run it as the last step, after the skill has become stable enough.

<a id="9-workspace-structure"></a>

## 9. Test working directory structure

```
_workspace/
├── iteration-1/
│   ├── eval-descriptive-name/
│   │   ├── eval_metadata.json
│   │   ├── with_skill/    (outputs/ + timing.json + grading.json)
│   │   ├── without_skill/ (outputs/ + timing.json + grading.json)
│   │   └── blind/         (A/outputs/ + B/outputs/)
│   └── benchmark.json
├── iteration-2/
└── evals/evals.json
```

**Retention rules:**

- Give `eval` directories names that describe their content instead of numbers (for example, `eval-multi-page-table-extraction`).
- Create a separate directory for each iteration, and do not overwrite earlier `iteration` directories.
- Do not delete `_workspace/`, because post-hoc verification and change-history tracking need it.
