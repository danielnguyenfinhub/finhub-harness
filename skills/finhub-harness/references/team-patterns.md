# Team Composition Patterns: Six Basic Patterns, Quality Verification, Agent Definitions
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

This document supplements Step 2-2 and Step 3 of `SKILL.md`. It explains the execution mode that v2 recommends for each pattern. Details are in `execution-modes.md`.

---

## Table of contents

1. [Six basic patterns](#1-six-basic-patterns)
2. [Quality verification patterns (added in v2)](#2-quality-verification-patterns-added-in-v2)
3. [Composite patterns](#3-composite-patterns)
4. [Choosing an agent type](#4-choosing-an-agent-type)
5. [Agent definition structure](#5-agent-definition-structure)
6. [Criteria for splitting agents](#6-criteria-for-splitting-agents)
7. [Designing agents for reuse](#7-designing-agents-for-reuse)
8. [Skills versus agents](#8-skills-versus-agents)

---

## 1. Six basic patterns

### 1-1. Pipeline

Work proceeds in a fixed order. The output of the previous agent becomes the input of the next agent.

```
[Analyze] → [Design] → [Implement] → [Verify]
```

**Fits when:** each stage depends heavily on the artifact of the previous stage

**Example:** Writing a novel: worldbuilding → characters → plot → drafting → editing

**Caution:** If one stage slows down, the whole job slows down. Design each stage to be as independent as possible.

**Execution mode v2 recommends:** If the stages and items can be listed in advance, Workflow orchestration (Mode A) is recommended, using `pipeline()`. Each item moves to the next stage as soon as the previous stage finishes it, with no need to wait for every item in a stage to finish, so total run time is shorter too. If a person must review the artifact between stages, call sub-agents in sequence (Sub-agent delegation, Mode C).

### 1-2. Fan-out/fan-in

Independent tasks are processed at the same time, and the results are merged into one.

```
         ┌→ [Specialist A] ─┐
[Split] → ├→ [Specialist B] ─┼→ [Merge]
         └→ [Specialist C] ─┘
```

**Fits when:** the same input must be analyzed separately from several perspectives or domains

**Example:** Comprehensive research: investigate official sources, press, community, and background at the same time, then compile them into one report

**Caution:** How you merge the results decides overall quality.

**Execution mode v2 recommends:** Consider Workflow orchestration (Mode A) first. Define the list of perspectives as an array, send it through `pipeline()`, receive results that match the `schema`, and merge them in code. Use `parallel()` only when you must collect all results and then de-duplicate them. In that case, every parallel call finishes before the next stage begins. For research with two to four investigators who need to share what they find in real time, Persistent agent collaboration (Mode B) also fits.

### 1-3. Expert pool

Only the specialist that fits the input and situation is called.

```
[Classifier] → { Specialist A | Specialist B | Specialist C }
```

**Fits when:** each input type needs a different way of handling

**Example:** Code review: of the security, performance, and architecture specialists, call only the one for the relevant area

**Caution:** If the classifier agent misclassifies the input, the right specialist cannot be selected.

**Execution mode v2 recommends:** Use Sub-agent delegation (Mode C) to call only the needed specialist once. If you must carry on a follow-up conversation with the same specialist, give it a `name` and switch to Persistent agent collaboration (Mode B).

### 1-4. Producer-reviewer

A producing agent and a verifying agent work as a pair.

```
[Produce] → [Verify] → (if a problem is found) → [Produce] re-run
```

**Fits when:** the quality of the artifact must be verified and an objective pass criterion can be set

**Caution:** Set a maximum retry count of two to three so that verification and revision do not repeat endlessly.

**Execution mode v2 recommends:** If the verification criteria can be expressed in code, use Workflow orchestration (Mode A). Run parallel verification for each item found by the adversarial verification pattern below. If subjective judgments must be reconciled, launch the producer and verifier as a **persistent agent pair** with names and exchange feedback through SendMessage. The producer keeps the earlier conversation, so it can correct exactly the parts that were flagged.

### 1-5. Supervisor

A central agent manages work state and divides the work according to progress.

```
         ┌→ [Worker A]
[Supervisor] ─┼→ [Worker B]    ← distributed according to progress
         └→ [Worker C]
```

**Fits when:** the workload keeps changing, or you must decide how to divide the work while it runs

**Difference from fan-out:** Fan-out decides the distribution before the work starts. A supervisor watches progress and redistributes the work.

**Caution:** If you split the work too finely, the supervisor must redistribute often and becomes a bottleneck.

**Execution mode v2 recommends:** Use Persistent agent collaboration (Mode B). The main agent as leader registers work with `TaskCreate`, receives workers' completion notifications, and redistributes the work with `SendMessage` and `TaskUpdate`. If the task list can be fixed in advance and the distribution procedure can be written as code, switch to Workflow orchestration (Mode A). In that case the supervisor has no judgments left to make.

### 1-6. Hierarchical delegation

A delegated agent in turn hands work to lower-level agents. This is the approach for breaking a complex problem into several levels.

```
[Overseer] → [Lead A] → [Practitioner A1, A2]
           → [Lead B] → [Practitioner B1]
```

**Fits when:** the problem divides naturally into higher-level and lower-level work

**Caution:** Beyond three levels, execution slows and earlier work may not be passed along properly. **Two levels or fewer is recommended.**

**Execution mode v2 recommends:** Nest workflows. The parent workflow calls child workflows with `workflow(nameOrRef, args)`. Nested calls are supported only one level deep, which keeps the hierarchy from growing too deep. Alternatively, remove the hierarchy and recompose it as `phase()` stages of a single workflow.

## 2. Quality verification patterns (added in v2)

These are workflow verification patterns to add to a harness whose artifacts must be accurate. Their purpose is to filter out results that look right at first glance but are actually wrong.

| Pattern | Structure | Use when |
|------|------|------|
| **Adversarial verification** | For each item found, launch N independent adversarial verification agents. Only items that more than half of the N agents judge `confirmed` (evidence sufficient) pass. | The findings or claims must be trustworthy (review, audit, research) |
| **Perspective-split verification** | Do not give the N adversarial verification agents the same prompt. Assign each a different perspective such as correctness, security, or reproducibility. | Errors can come in several types. Splitting the verification criteria finds errors that repeating the same verification would miss. |
| **Judge panel** | Judge in parallel N drafts made with different approaches. Take the highest-rated draft as the base and write the final version, reflecting the strengths of the other drafts where needed. | Design or planning with many possible solutions. Comparing several drafts beats revising one draft repeatedly. |
| **Loop-until-dry** | Repeat the search until the number of new items found is 0 for K consecutive rounds. Record rejected items in `seen` too, so the same item is not proposed again and again. | Searches where you cannot know how many problems exist (bugs, issues, edge cases). Fixing the number of rounds in advance can miss problems that would have been found later. |
| **Multi-criteria search** | Run in parallel agents that search by different criteria, such as container, content, entity, and time. | When a single search criterion cannot find everything |
| **Omission review** | Place one agent at the end whose only job is to check "Which search criteria were not used, which claims were not verified, and which material was not read?" (the omission reviewer) | Just before merging results. Add newly found omissions to the next search task. |
| **Disclose excluded counts** | If you limit the scope of checking with `top-N` or sampling, always record the number of excluded items with `log()`. | Every fan-out. If you do not disclose the excluded count, the user wrongly understands that everything was checked. |

**Scaling principle:** Set the scale to match the research scope the user requested. For "see if there are bugs," use a few searchers and one adversarial verification agent. For "audit it thoroughly," increase the searchers, assign three to five adversarial verification agents to each item found, and then go through a synthesis stage. If it is hard to judge the requested scope, be thorough for research, review, and audit, and keep quick checks small.

> Implementation examples are in `workflow-recipes.md`.

## 3. Composite patterns

Real work combines several patterns.

| Composite pattern | Composition | Example |
|----------|------|------|
| **Fan-out/fan-in + producer-reviewer** | Produce several drafts at the same time, then verify each | Multilingual translation: translate into four languages in parallel, then a native-speaker reviewer for each language inspects it |
| **Pipeline + fan-out/fan-in** | Process some of the sequential stages in parallel | Analysis (sequential) → implementation (parallel) → integration test (sequential) |
| **Supervisor + expert pool** | The supervisor calls the specialist that fits the situation | Handling customer inquiries: the supervisor classifies the inquiry, then assigns it to the right specialist |
| **Search + adversarial verification + synthesis** | Search by several criteria → verify each item found → omission review → write the report | Comprehensive code audit, in-depth research |

In a composite pattern, choose the suitable execution mode for each stage. This kind of composition is called a mixed mode. The selection criterion is whether the control flow of that stage can be fixed in code in advance.

## 4. Choosing an agent type

When you call an agent, specify the type with the `subagent_type` parameter of the Agent tool or the `agentType` parameter of Workflow.

### Built-in types

| Type | Available tools | Suited use |
|------|----------|-----------|
| `general-purpose` | All (including WebSearch, WebFetch) | Web research, general work, file edits |
| `Explore` | Read-only (no Edit, Write) | Finding where code lives in a codebase. Do not use it for review or audit. |
| `Plan` | Read-only (no Edit, Write) | Architecture design, writing implementation plans |

### Custom types

Define a type in `.claude/agents/{name}.md`. When calling, specify `subagent_type: "{name}"` or `agentType: "{name}"`. The tools and model to use are set in the YAML frontmatter.

### Selection criteria

| Situation | Recommended | Reason |
|------|------|------|
| The role is complex and reused across several sessions | **Custom type** | The specialist role and working principles are managed consistently in a file. |
| Simple one-off research or collection where a detailed prompt alone is enough | `general-purpose` + detailed prompt | Use the built-in type directly without a separate definition file. |
| Only locating code | `Explore` | It has no file-editing tools, so there is no risk of editing by mistake. |
| Only writing a design or plan | `Plan` | It focuses on analysis without changing code. |
| Simple one-off file edit | `general-purpose` + detailed prompt | Handle it right away with the built-in type. |
| Implementation that is reused or needs specialist rules | **Custom type** | Allow every tool needed and apply specialist guidelines. |
| Editing several files in parallel | Custom type + `isolation: 'worktree'` | It prevents file-edit conflicts between agents. Creating a worktree has a cost, so use it only for parallel edits. |

**Principle:** Create a specialist role that will be reused across several sessions as a custom type in `.claude/agents/{name}.md`. Do not create a separate definition file for one-off work that uses a built-in type as it is.

**Model policy:** Choose the model tier by the complexity of the work, the expected duration, the scope of judgment the agent must exercise on its own, and the response speed required. Use **fable** for the highest-difficulty work that must be planned and run autonomously over a long period, and for agent orchestration. Use **opus** for design and architecture, code generation, complex analysis, cross-verification, and creative writing. Use **sonnet** for structured work that needs little judgment, such as log analysis, format conversion, static file checks, running deploy scripts, and simple collection. If it is hard to decide, choose sonnet. Do not assign the same model to every agent without a reason, and leave the reason for your choice as a comment. Detailed criteria are in `model-selection-guide.md`.

## 5. Agent definition structure

```markdown
---
name: agent-name
description: "Describe the role in one or two sentences and list the phrasings that serve as trigger conditions."
# tools: Read, Grep, Glob, Bash        ← optional: set when restricting the tools to use (read-only reviewers, etc.)
#                                         for an agent that edits artifacts, include Edit along with Write
# model: sonnet                         ← choose to fit the nature of the work (model-selection-guide.md), and record the reason as a comment
---

# Agent Name — one-line role summary

You are a [role] specialist in [domain].

## Core roles
1. Role 1
2. Role 2

## Working principles
- Principle 1 (state the reason as well, so the agent judges by the same standard in exceptional situations.)
- Principle 2

## Input and output rules
- Input: [what it receives from where — file path, args, previous-stage artifact]
- Output: [what it writes where — a _workspace/ path or a structured return value]
- Format: [file format, structure, schema]

## Communication rules (persistent agent collaboration)
- First report: tell the leader the list of tools actually available (to check whether any tool listed in `tools` is missing)
- Receiving messages: [which messages it receives from whom]
- Sending messages: [which messages it sends to whom]
- Shared tasks: [what kinds of tasks it registers or requests]

## When called again
- If a previous artifact exists, read it and reflect the improvements.
- If it receives user feedback, revise only the relevant part.

## Error handling
- [what to do on failure]
- [what to do when input is missing or ambiguous]

## Collaboration
- Relationship with other agents
```

**Workflow-only agents:** Put a "Structured output" section in place of "Communication rules". State the JSON structure to return, and write that the final text is **return data**, not a message to the user.

**Cautions when restricting `tools`:**

- Give an agent that edits artifacts Edit as well as Write. With Write alone, even a one-line fix requires rewriting the whole file. When the artifact is large, the agent gives up on editing and works around it by writing to a separate file, so the original artifact is left unfixed.
- Deferred-loading tools such as `TaskCreate` and `TaskUpdate` have been observed not to be provided at run time even when listed in `tools` (observed in Claude Code 2.1.226; this may differ by environment). `SendMessage`, also a deferred-loading tool, was provided, so the boundary of which tools go missing is unclear. Have persistent agents report the list of tools actually available in their first report. If a tool is missing, the orchestrator handles that work in its place (for example, the leader updates task status with `TaskUpdate`) or you lift the `tools` restriction in the definition file.

## 6. Criteria for splitting agents

| Criterion | Split | Merge |
|------|------|------|
| Expertise | Split if the areas of responsibility differ | Merge if the areas of responsibility overlap |
| Parallelism | Split if they can run independently | Consider merging if they must be processed in order |
| Information needed | Split if one agent would have to handle a lot of information | Merge if little information is needed and the work is short |
| Reusability | Split if other teams can reuse it | Consider merging if only this team uses it |

## 7. Designing agents for reuse

Before creating a new agent, compare its role with the existing agents in `.claude/agents/`. If you build or extend a harness several times, agents with the same role can pile up under different names.

| Relationship to existing agents | Action |
|------|------|
| An existing agent fully covers the new role | Do not create a new one; call the existing agent. |
| They overlap in part, and generalizing the existing agent lets it take on the new role | Generalize and extend the existing agent. |
| They overlap in part, but the domain was deliberately specialized | Create a separate new agent. |
| The role scope is entirely different | Create a new one. |

**Principle:** The more an agent concentrates on one role, the easier it is to reuse and the less duplication there is. If the extension leaves an agent with two or more roles, first consider whether it can be split.

**When extending an existing agent:** The behavior of the orchestrators that call that agent may change too. Before extending, check which orchestrators call this agent, and reflect the widened role in its `description`. After extending, run a dry run (Step 6-5 of `SKILL.md`) to confirm the existing flow still works as before.

## 8. Skills versus agents

| Aspect | Skill | Agent |
|------|-------------|-----------------|
| Definition | A collection of work procedures and tools | A specialist role and behavioral principles |
| Location | `.claude/skills/` | `.claude/agents/` |
| Run condition | When the user request matches the trigger conditions written in `description` | When called directly through the Agent or Workflow tool |
| Purpose | "How it is done" | "Who does it" |

### Ways to connect skills and agents

| Method | Implementation | Suited when |
|------|------|-----------|
| **Call through the Skill tool** | State in the agent prompt: `Call /skill-name with the Skill tool` | The skill is an independent workflow that the user can also call directly |
| **Include directly in the prompt** | Write the skill content directly in the agent definition | The skill is short, at most 50 lines, and only that agent uses it |
| **Load a reference file** | Read the skill's `references/` file with `Read` only when needed | The skill content is large and needed only under certain conditions |

Call a skill shared by several agents through the Skill tool. Put a short skill that only a particular agent uses directly in its prompt, and if the content is large, load only the reference file that is needed.
