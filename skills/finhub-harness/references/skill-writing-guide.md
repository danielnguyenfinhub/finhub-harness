# Skill Writing Guide
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

This guide explains in detail how to raise the quality of skills built with the harness. It supplements Step 4 of `SKILL.md`.

---

## Table of Contents

1. [Writing the `description`](#1-description-pattern)
2. [Writing the body](#2-body-style)
3. [Defining the output format](#3-output-format-pattern)
4. [Writing examples](#4-example-pattern)
5. [Loading only the information that is needed, step by step](#5-progressive-disclosure-pattern)
6. [Deciding whether to bundle scripts](#6-script-bundling-criteria)
7. [Data schema standard](#7-data-schema-standard)
8. [What to leave out of a skill](#8-what-not-to-include-in-a-skill)
9. [Designing skills for reuse](#9-designing-skills-for-reuse)

---

<a id="1-description-pattern"></a>

## 1. Writing the `description`

The skill fields exposed to Claude are `name` and `description`, and the specific trigger conditions go in the `description`. Claude reads these two fields to decide which skill to use.

### How skills get triggered

Claude tends not to trigger a skill for simple tasks it can handle easily with its basic tools. For example, a simple request such as "read this PDF" may not trigger a skill even when the `description` is well written. The more complex the task (multiple steps, or specialist judgement), the more likely the skill is to trigger.

### Writing principles

1. State both **what the skill does** and **the specific situations in which to trigger it**.
2. If there are cases that look similar but must not trigger the skill, state the scope and the exclusions clearly.
3. Claude judges conservatively whether to trigger a skill, so word the situations that should trigger it somewhat assertively.
4. For a skill that orchestrates several tasks, always include **words that signal follow-up work** (re-run, update, revise, improve a previous result).

### Good example

```yaml
description: "Reads PDF files and extracts text and tables, and performs merging,
  splitting, rotation, watermarking, encryption and decryption, and OCR. Always use
  this skill when the user mentions a .pdf file or asks for a PDF deliverable. It is
  especially useful for tasks that need conversion, editing or analysis, rather than
  a plain request to 'read' a PDF."
```

### Bad examples

- `"A skill that processes data"` — too vague to tell which files or tasks it covers.
- `"PDF-related tasks"` — does not say what it can do or when to trigger it.

<a id="2-body-style"></a>

## 2. Writing the body

### Explain the reason first

A large language model (LLM) that understands why a rule exists can judge correctly in exceptional situations. Rather than listing dos and don'ts as bare commands, explain why the rule should be followed.

**Bad example:**

```markdown
Always use pdfplumber for table extraction. Never use PyPDF2 for tables.
```

**Good example:**

```markdown
Use pdfplumber when extracting tables. PyPDF2 is meant for text extraction, so it
does not preserve the row and column structure of a table. pdfplumber recognises
cell boundaries and returns structured data.
```

### Fix with a principle that applies to many cases

When feedback or testing exposes a problem, do not append an instruction that fits only that one example. Fix it with a principle that applies to other cases as well.

**Overfitted fix:** `If there is a "Q4 revenue" column, convert that column to numbers.`

**Generalised fix:** `If a column name contains a word that denotes a numeric value, such as "revenue", "amount" or "quantity", convert that column to a numeric type. Leave values that cannot be converted as they are.`

### Write in the imperative

Write "Do X" and "Use Y", not "You should do X" or "You can use Y". A skill is an instruction sheet that an AI agent must follow.

### Reduce the amount of information to consult at one time

The amount of information a model can consult at one time (the context window) is limited. That limit covers not only the skill instructions but also the other information the task needs. Judge whether each sentence is worth the tokens it takes, using these criteria.

- "Does Claude already know this?" → Delete it.
- "Does Claude make mistakes without this explanation?" → Keep it.
- "Would one concrete example be clearer than a long explanation?" → Replace it with an example.

<a id="3-output-format-pattern"></a>

## 3. Defining the output format

For a skill whose output format matters, state the structure to follow.

```markdown
## Report structure
Follow this template exactly.

# [Title]
## Summary
## Key findings
## Recommendations
```

Keep the format description short and include a real example; that works better.

**Output that the next step of a workflow will read:** If the next step reads and processes the output in code, specify a **JSON structure** instead of a Markdown template. Also state that the final text is return data to hand to the next step, not a message to show the user. The `agent()` call in `Workflow` enforces the return format through `schema`, so the structure defined in the skill and the one in the script must match.

<a id="4-example-pattern"></a>

## 4. Writing examples

A concrete example conveys a rule more clearly than a long explanation.

```markdown
## Commit message format

**Example 1:**
Input: Add user authentication using JWT tokens
Output: feat(auth): implement JWT authentication

**Example 2:**
Input: Fix the bug where the show-password button on the login page does not work
Output: fix(login): repair password visibility toggle button
```

<a id="5-progressive-disclosure-pattern"></a>

## 5. Loading only the information that is needed, step by step (Progressive Disclosure)

### Approach 1: Split files by business domain

```
bigquery-skill/
├── SKILL.md (overview + guidance for choosing a business domain)
└── references/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    └── product.md (API usage, features)
```

When the user asks about revenue, load only `finance.md`.

### Approach 2: Read detailed instructions only when needed

```markdown
## Editing documents
For simple edits, modify the XML directly.
**If tracked changes are needed**, see [REDLINING.md](references/redlining.md).
```

### Approach 3: Add a table of contents to large reference files

Add a table of contents at the top of any reference file longer than 300 lines.

<a id="6-script-bundling-criteria"></a>

## 6. Deciding whether to bundle scripts

Read the work logs of the agents that ran the tests. If any of the following recurs, include the script or procedure in the skill.

| Recurring behaviour | Action |
|------------|------|
| The agent writes the same helper script in all three tests. | Put the script in `scripts/`. |
| The agent runs the same `pip install` or `npm install` command every time. | Write a dependency installation step into the skill. |
| The agent follows the same multi-step procedure every time. | Write the standard procedure into the skill body. |
| The agent hits a similar error and works around it the same way every time. | Write the known issue and its fix into the skill. |

Always run and verify any script you include in a skill.

<a id="7-data-schema-standard"></a>

## 7. Data schema standard

Use the standard schemas below so that data passes between skills consistently. The same schemas can also be used when testing and evaluating skills built with the harness.

### `eval_metadata.json`

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": [
    "The output contains X",
    "A file was created in format Y"
  ]
}
```

### `grading.json`

```json
{
  "expectations": [
    {
      "text": "The output contains 'Seoul'",
      "passed": true,
      "evidence": "Confirmed 'extract Seoul region data' in the third step"
    }
  ],
  "summary": { "passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0 }
}
```

**Field names matter:** Use `text`, `passed` and `evidence` exactly. Do not rename them to variants such as `name`/`met`/`details`.

### `timing.json`

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

When a sub-agent's completion notification arrives, save `total_tokens` and `duration_ms` immediately. Both values are available only at the moment the notification arrives and cannot be recovered later.

<a id="8-what-not-to-include-in-a-skill"></a>

## 8. What to leave out of a skill

- Supplementary documents such as `README.md`, `CHANGELOG.md` and `INSTALLATION_GUIDE.md`
- Information needed only while building the skill (test results, iteration history)
- Explanations written for users (a skill is an instruction sheet that an AI agent follows)
- General knowledge that Claude already has
- Items that were used only in v1 (`TeamCreate`/`TeamDelete`, experimental flags, a blanket `model` setting applied to every agent)

<a id="9-designing-skills-for-reuse"></a>

## 9. Designing skills for reuse

Before creating a new skill, compare its capabilities with the existing skills in `.claude/skills/`. When a harness is built or extended several times, skills with the same capability can pile up under different names.

| Relationship to existing skills | Action |
|------|------|
| An existing skill already covers all of the new capability. | Do not create a new one; connect the existing skill to the agent. |
| Only part overlaps, and generalising the existing skill would let it cover the new capability too. | Generalise and extend the existing skill. |
| Part overlaps, but the domain specialisation is intentional. | Create a separate new skill. |
| The capability scope is entirely different. | Create a new skill. |

**Principle:** The more a skill focuses on a single role, the easier it is to reuse and the less duplication it causes. If a skill has two or more roles, first consider whether it can be split.

### How far to generalise

Generalisation can go on without end, so stop at the scope of responsibility the skill has taken on. Keep the intended domain specialisation and strip out only the incidental dependencies.

For example, generalising a "fintech risk assessment PDF" skill goes as follows.

| Dependency stripped | Result |
|------|------|
| Fintech | "Assessment result PDF". If the scope of responsibility is the assessment report, stop here. |
| Assessment | "PDF form completion". If a skill with the same capability already exists, do not create a new one; use that skill. |

If the scope of responsibility was defined from the start as "fintech risk assessment", do not generalise it; keep it as a separate skill.

Extending an existing skill can also change the behaviour of the agents that use it. Before extending, check which agents use the skill, and reflect the wider scope of use in the `description`.
