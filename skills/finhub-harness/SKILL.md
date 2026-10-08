---
name: finhub-harness
description: "Designs a harness for a project or domain: defines the specialist agents, creates the skills each agent uses, and writes a surface-aware orchestrator for Claude Code, Claude chat or Claude Cowork. Use when the user asks to 'build a harness', 'set up a harness', 'design a harness', 'harness engineering', 'create an agent team', 'build an agent team for X', 'make a finhub harness', or to rework, extend, migrate or enrich an existing harness ('add an agent', 'upgrade the harness to v2', 'borrow the judge-panel pattern from repo Y'). Also use to operate an existing harness: 'audit the harness', 'check harness status', 'sync agents and skills'. Do NOT use for running a harness that already exists (call its orchestrator skill) or for folding run feedback back in (use finhub-harness-evolve)."
---

# FinHub Harness — agent teams, their skills and a surface-aware orchestrator

> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and extended for FinHub. Original: https://github.com/revfactory/harness. FinHub additions: surface adaptation (Code / chat / Cowork), the Authority List with a fresh-context adversarial audit, mutation-tested boundary QA, and licence-tiered enrichment from other harness repos.

Design a harness that fits the project. Define each agent's role, write the skill each agent follows when it works, and write one orchestrator that says who collaborates, in what order, on which surface.

## Core principles

1. Agent definitions live in `project/.claude/agents/`, skills in `project/.claude/skills/`. An agent definition says **who** works; a skill says **how** the work is done. Keep them apart.
2. Choose the execution mode from the shape of the work. If the item list, the verification rule and the repeat condition can be written as code, orchestrate with a Workflow. If the same expert must trade feedback across turns, use persistent named agents. If you only need a result once, delegate to a sub-agent. Step 2-1 gives the rule; the full decision tree is `references/execution-modes.md` §4.
3. Choose the model per agent from the task's complexity, duration, autonomy and latency need: fable for long-horizon autonomous planning, opus for bounded deep reasoning (design, code generation, cross-checking), sonnet for routine work. The criteria are in `references/model-selection-guide.md`. Never set every agent to the top model because "it matters".
4. Record only the trigger conditions and a change history in `CLAUDE.md`, so a new session can find the orchestrator. Everything else lives in the orchestrator and the agent/skill files.
5. Feed what each run teaches back into the agents, skills and `CLAUDE.md`. The retrospective is `finhub-harness-evolve`'s job.
6. Write every generated artefact in the language the user writes in. Do not copy this skill's language or the templates' example wording; translate headings and examples. If the user extends an existing harness, follow the language of the existing files.
7. **Declare the target surface.** Every orchestrator says whether it runs on Claude Code, Claude chat, Claude Cowork or several. Modes A/B/C exist only in Claude Code; chat and Cowork need a single-context fallback. `references/surfaces.md` says exactly how each primitive degrades.
8. **Borrowed patterns carry a citation.** A design decision taken from a reference repo enters the harness through an Authority List row (`claim → references/<repo>/<path>:<line>`, licence tier noted). A decision with no source is labelled NET-NEW with a reason and a named test, never a fake citation. `references/quality-gates.md` has the schema; `references/source-enrichment.md` says what may be borrowed from where.

## Procedure

### Step 0: Check the current state

Read `project/.claude/agents/`, `project/.claude/skills/`, `project/CLAUDE.md` and, if present, `project/.claude-plugin/plugin.json`. Then pick exactly one path:

- **New build**: no agents or skills, or empty directories → run Steps 1-6 in full.
- **Extend an existing harness**: add an agent, a skill, or change the structure → run only the steps in the table below.
- **Operate / maintain**: audit, repair or sync → go to Step 7.

| Change | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 | Step 6 |
| --- | --- | --- | --- | --- | --- | --- |
| Add an agent | skip, reuse Step 0 findings | decide only which mode, team and phase it joins | required | only if it needs a dedicated skill | edit the orchestrator | required |
| Add or change a skill | skip | skip | skip | required | only if wiring changes | required |
| Change structure or execution mode | skip | required | affected agents only | affected skills only | required | required |

Then:

1. **Detect v1 artefacts.** If an orchestrator or agent mentions `TeamCreate`, `TeamDelete`, `team_name`, `SendMessage({to: "all"})` or `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, it was built for v1 and will silently degrade to a single agent on the current runtime. Propose the v2 migration in `references/execution-modes.md` §5 before anything else.
2. **Detect the surface mismatch.** If the orchestrator assumes `Agent`/`Workflow` tools but the user wants to run it in Claude chat or Cowork, add the single-context fallback (`references/surfaces.md`) before extending it.
3. Compare the real agent and skill list with the `CLAUDE.md` change history and list every mismatch.
4. Report the findings and the plan to the user and get confirmation.

### Step 1: Analyse the domain and the work

1. Extract the domain and the goal from the request.
2. Split the work by kind: generate, verify, edit, analyse.
3. Characterise the flow so Step 2 can pick a mode:
   - Can the item list be enumerated up front (N files, M viewpoints)?
   - Is there a verify-then-fix loop?
   - Does the result improve when agents argue with each other?
   - Must the same expert stay in conversation within one session?
4. Find overlaps or conflicts with the agents and skills found in Step 0.
5. Skim the codebase: stack, data model, main modules, existing tests and gates (`pytest`, `ruff`, `mypy` or their equivalents) — the orchestrator's QA must run the real gates, not invent new ones.
6. Match the explanation level to the user. Do not use "assertion" or "JSON Schema" without a gloss for a non-coder.
7. **Which surface(s)?** Ask if it is not obvious. A harness for a mortgage-broking operator who works in Cowork with CRM connectors is a different artefact from one for a developer in Claude Code, even for the same domain.

### Step 2: Choose the execution mode and the team pattern

#### 2-0. Delegation gate (first; the default is one agent)

Before choosing a mode or a pattern, answer six questions in one line each: (1) which units of work are independent, or in what order they hand off, (2) what splitting buys: specialisation, parallel speed or a separate context, (3) which paths or resources each worker writes, (4) whether every worker's tools and permissions cover its task on the target surface, (5) who synthesises and accepts the result, (6) how a partial, blocked or conflicting result is reported. `references/team-patterns.md` §6-1 says when an answer counts as unclear.

- If any answer is missing or unclear, the outcome is **single agent**: the main context does the work, there is at most one agent file, and no Mode A or B and no parallel workers are used. Having an `Agent` or `Workflow` tool is not a reason to delegate. For an extension, "at most one agent file" counts the new role only: the new role then becomes a step of the main context or of an existing agent, not a new file.
- Only when all six answers are concrete is the outcome **delegate**; then 2-1 to 2-3 and the Step 5 scale rule size the team. When extending a harness, run the gate again for the new role alone.
- A dependent chain (pipeline, producer-reviewer, Mode B, a fresh-context judge, design then judge then build then QA) is concrete when each hand-off artefact is named; it delegates in sequence, and independence only decides whether calls run in parallel.
- When the user explicitly asks for a team or names the roles, build what was asked: write each unclear answer under `## Delegation gate` as a stated risk and tell the user. The single-agent default applies when the user has not chosen.
- A coordinator layer between the root and its workers needs one sentence in the orchestrator that names why the root cannot hold that work; without it, workers report to the root. The two-level cap in 2-2 stays.
- Write the answers and the outcome in the orchestrator under `## Delegation gate` (Step 5).

(adapted from references/meta_harness/.agents/skills/harness/references/agent-design-patterns.md:221 (Apache-2.0); adapted from references/meta_harness/.agents/skills/harness/SKILL.md:166 (Apache-2.0))

#### 2-1. Execution mode (Claude Code)

| Mode | Primitives | Fits |
| --- | --- | --- |
| **A. Workflow orchestration** | `Workflow` script: `agent()`, `pipeline()`, `parallel()`, `phase()`, `schema` | item list, verification rule and repeat count expressible as code; schema-validated results; dozens of agent calls |
| **B. Persistent agent collaboration** | `Agent(name:)`, `SendMessage`, `TaskCreate`/`TaskUpdate` | named experts that keep context across feedback, negotiation and joint editing |
| **C. Sub-agent delegation** | one `Agent` call per task, background by default; independent calls parallel in one message, dependent calls one after another with the prior artefact path in the prompt | no agent-to-agent talk needed; a result once |

Decide in this order: (1) if the list, rule and loop can be coded, use A — code-defined control flow is reproducible; (2) else if agents must converse or remember, use B; (3) else C — a short pipeline of one-shot agents is still Mode C, run sequentially; (4) mix modes per phase and write `**Execution mode:**` above each phase. Write only the mode(s) you chose; an orchestrator is not required to carry all three.

`Workflow` needs the user's explicit opt-in. Invoking an orchestrator skill that declares a Workflow counts as opt-in. Keep the default agent count small; scale up only on "thorough", "exhaustive" or a stated token budget (`+500k`).

> Details, concurrency caps, schemas, budgets and resume: `references/execution-modes.md`. Chat and Cowork fallbacks: `references/surfaces.md`.

#### 2-2. Team pattern

Split the work by expertise, then pick from `references/team-patterns.md`: **pipeline**, **fan-out/fan-in**, **expert pool**, **producer-reviewer**, **supervisor**, **hierarchical delegation** (two levels at most; one level of Workflow nesting).

When correctness matters, add verification patterns: **adversarial verification** (N adversarial checkers per finding; only majority-`confirmed` passes; `refuted`/`uncertain` never count as passes), **judge panel**, **loop-until-dry**, **multi-axis search**, **omission reviewer**. For harnesses that *design before they build*, add the FinHub pattern: an **Authority List** audited by a **fresh-context judge** (`references/quality-gates.md` §1-2), which is adversarial verification applied to the design itself.

#### 2-3. Splitting agents

Split on expertise, parallelism, context load and reuse (`references/team-patterns.md` §6). Before creating any agent, check `.claude/agents/` for one that already covers the role and extend it instead (§7).

### Step 3: Write the agent definitions

Reusable experts are custom types in `project/.claude/agents/{name}.md`, invoked with `subagent_type: "{name}"` (Agent) or `agentType: "{name}"` (Workflow). One-off tasks that fit `general-purpose`, `Explore` or `Plan` get no file.

- Frontmatter: `name` and `description` required; `tools` to restrict (drop Edit and Write for read-only reviewers; give Edit *and* Write to anything that fixes artefacts); `model` with the reason as a comment.
- Body: role, working principles with their reasons, input/output rules, error handling, collaboration. Persistent agents (Mode B) add `## Communication rules`; Workflow-only agents (Mode A) add `## Structured output`; one-shot agents (Mode C) need neither — their `## Input and output rules` name the artefact paths they read and write. Skills are wired in the body ("call `/skill-name` with the Skill tool"); there is no `skills:` frontmatter field.
- Connectors: an agent that cannot do its job without an MCP server or connector gets a `## Required connectors` section in its body, one server per line, written as the segment between `mcp__` and the next `__` in its tool names (`mcp__crm__search` → `crm`). Leave the section out when the agent needs none. Step 5 copies these lines into the orchestrator's preflight table, so a missing connector stops the run before anyone is spawned instead of failing on the agent's first call. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:956 (MIT))
- QA agents get a type with all tools (`Explore` cannot run scripts), compare shapes across boundaries rather than check existence, and run after every module, not once at the end (`references/qa-agent-guide.md`). Add the mutation spot-check from `references/quality-gates.md` §3 whenever the QA agent judges tests, and have it write a `CANDIDATE:` line under `RESULT:` so the verdict names the tree it judged (§3-7).
- Model per agent from `references/model-selection-guide.md`: fable only for the layer that plans and runs long; opus for design, generation, judging; sonnet by default.

### Step 4: Write the skills

Each agent's method goes in `project/.claude/skills/{name}/SKILL.md` (`references/skill-writing-guide.md`).

1. Check `.claude/skills/` for an existing skill that covers it; link or extend rather than duplicate (§9).
2. Layout: `SKILL.md` (required, under 500 lines) + optional `scripts/`, `references/`, `assets/`.
3. `description` states what the skill does and the concrete situations that must trigger it. Follow-up phrasings ("re-run", "update", "redo only the X part") are required on the orchestrator and on any skill users will invoke directly; a leaf skill only ever called by an agent needs none. Name near-miss cases it must not take.
4. Body: explain the reason behind each rule, generalise to principles, imperative register, move detail to `references/` and say when to read each file.
5. Wire skills to agents: Skill-tool call for shared workflows, inline for short agent-private procedures, `Read` of a reference file for long conditional material.

### Step 5: Integrate and order the run

The orchestrator is itself a skill. Use the matching template in `references/orchestrator-template.md` (A, B, C or mixed) and the scripts in `references/workflow-recipes.md`. When extending, edit the existing orchestrator; never create a second one for the same domain.

Every orchestrator contains:

- **Execution mode and target surface** at the top (per phase if mixed). If chat or Cowork is a target, a `## Single-context fallback` section (`references/surfaces.md`).
- **Step 0 context check**: no `_workspace/` → fresh run; `_workspace/` + partial request → re-run only that agent/phase (pass prior output paths); `_workspace/` + new input → move it to `_workspace_{timestamp}/` and start fresh; Workflow mode → `resumeFromRunId` when `run_meta.json` has one, except for a `once` stage that did not return a result (`references/state-ledger.md` section 3a, rule O7). A run of two or more phases that pass files to each other also keeps a state ledger, so a request to continue after a context reset or in a new session starts at the first unfinished phase, not the first one; a named partial re-run still wins, and the script is copied into the harness when the plugin is not installed there (`references/state-ledger.md`, script `scripts/state_ledger.py`). A phase that sends, publishes, uploads or writes a record outside the workspace is marked `once` in the optional `replay` column of that table, so a resume stops and asks about a half-done one instead of running it again (`references/state-ledger.md` section 3a). (adapted from references/openharness/src/openharness/autopilot/service.py:405 (MIT); adapted from references/meta_harness/.agents/skills/harness/SKILL.md:158 (Apache-2.0); adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0))
- **Connector preflight** (only when an agent has `## Required connectors`): Step 0 ends with the preflight item from Template A Step 0 in `references/orchestrator-template.md`, holding one agent → connector row per declared line. On Claude Code a missing connector stops the run before any spawn; on chat and Cowork the orchestrator warns and asks instead, because connector listings there are deferred and an absent name is not proof (`references/surfaces.md` §4).
- **Data hand-off**: structured return (`schema`) in A; return message in C; `SendMessage` and shared tasks in B; files for anything large or auditable, as `_workspace/{phase}_{agent}_{artifact}.{ext}`. Freeze artefacts at phase boundaries in B (template B Step 4).
- **Delegation contract** (only when the orchestrator spawns or messages a worker, so never in a single-context fallback): paste the Delegation block from `references/orchestrator-template.md` at the step that launches workers and fill one five-line brief per worker role. The block fixes what a brief must contain, the STATUS / EVIDENCE / BLOCKER report a worker ends with, and the check the orchestrator runs before it uses a report (re-ask once, then mark the result unverified; a `once` phase is never re-asked). It is prompt quality plus a check, not a guarantee.
- **Delegation gate** (every orchestrator): a `## Delegation gate` section with the six answers and the outcome from Step 2-0, written before anything is spawned; a single-agent outcome spawns nothing. Template C in `references/orchestrator-template.md` carries the block and an optional notes block for workers; an A or B orchestrator copies the same block.
- **Error policy**: one retry then proceed and record the gap, except that a `once` phase is never retried automatically: it stops and asks (`references/state-ledger.md` section 3a, rule O7); a verdict whose `candidate_id.py check` exits 3 gets its own row in the error table (treated as not given, the judging phase re-run on the current tree when the user agrees); never retry quota, auth or permission failures — open the partial artefacts, record what is missing, report; the orchestrator fills a gap only with facts it verified itself, never with a guessed judgement; in Mode A, `.filter(Boolean)` after every `parallel()`/`pipeline()` and `log()` the dropped count.
- **Scale**: 2-3 persistent agents for small jobs, 3-5 for medium, supervisor + 3-5 for large; Workflow calls from a handful to hundreds, capped by `budget.remaining()` when a budget is set.
- **Quality gates** when the harness builds software or produces audited decisions — outputs a third party will rely on (a lender, a client, a regulator, an auditor): credit or compliance assessments, client-facing advice, legal or financial figures. A gap email that only lists missing documents is not one; a servicing verdict is. Then: Authority List → fresh-context judge (max 3 rounds, then escalate with both positions) → build one slice → boundary QA with `RESULT: PASS|FAIL` first line, the repo's real gates re-run, mutation spot-checks on a scratch copy, one builder retry → final report whose first line is Done / partly done / blocked (`references/quality-gates.md`). Each QA report and judge verdict names the candidate it judged, and the orchestrator checks that line before it commits or ships (`scripts/candidate_id.py`, §3-7; `unverified` where no shell runs).
- **`CLAUDE.md` pointer**: record only the block below. Agent lists, directory trees and run rules stay out of it.

````markdown
## Harness: {domain}

**Goal:** {one line}

**Trigger:** For {domain} work, use the `{orchestrator-skill-name}` skill. Simple questions may be answered directly.

**Change history:**
| Date | Change | Target | Reason |
| --- | --- | --- | --- |
| {YYYY-MM-DD} | Initial build with finhub-harness | all | - |
````

On an initial build the Reason column stays `-`; later rows carry the feedback or defect that caused the change.

- **Follow-up triggers** in the orchestrator `description`: "re-run", "update", "fix", "redo only {part}", "improve the previous result", plus the domain's everyday verbs.

### Step 6: Verify and test

Follow `references/skill-testing-guide.md`.

1. **Files and references**: run `python3 scripts/lint_harness.py project/.claude` (path relative to this skill's directory) and fix every `ERROR` line; fix each `WARN` line or say in the report why it stays. The lint checks frontmatter, name grammar and that a skill's directory matches its name, non-empty descriptions, that every `subagent_type`/`agentType` names an agent file or a built-in type, that `## Required connectors` lines and the preflight table agree, that no agent or skill file which calls `Agent(`, `agent(`, `Task(` or `SendMessage`, or names `subagent_type` or `agentType`, contains a lazy-delegation phrase (WARN `lazy-delegation`), and v1 artefacts, and that local markdown links, a skill's single-level `references/<file>.<ext>` mentions and agent and skill names (`broken-link`, `bundled-ref`, `duplicate-name`) are not dead or duplicated; for a mention of a file you mean to create later, write it with a path prefix (`<skill>/references/x.md`), inside a code fence or as an angle-bracket placeholder rather than waiving the ERROR; it exits 1 on any error. Where it cannot run (chat without code execution), check the same list by hand. The lint does not check that nothing was written to `.claude/commands/` or that every Authority List citation opens to a line that supports the claim; check those yourself. (adapted from references/crewai/lib/crewai/src/crewai/skills/validation.py:43 (MIT))
2. **Per mode**: A — `meta` is a pure literal, no `Date.now()`/`Math.random()`, `parallel()` only where a barrier is needed, `.filter(Boolean)` present, `phase()` titles match `meta.phases`; B — message routes, task dependencies, agent count; C — inputs chain to outputs, parallel calls batched in one message; mixed — mode written per phase and hand-offs unbroken. Chat/Cowork targets — the single-context fallback covers every phase. Delegation, wherever workers are spawned or messaged — `grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` lists the orchestrator. Where the lint cannot run, `grep -nEi 'based on (your|the) (findings|research)|as (we )?discussed' project/.claude/skills/*/SKILL.md project/.claude/agents/*.md` is a stricter manual fallback (no word boundaries, every file, blind to a phrase wrapped over two lines): judge each hit by hand, because a research-and-write skill may legitimately keep one.
3. **Skill runs**: 2-3 realistic prompts per skill, with-skill vs baseline in parallel, qualitative plus assertion-based grading; fix by principle, not per example; repeat until gains flatten; move repeated helper code into `scripts/`.
4. **Trigger check**: 10 should-trigger prompts in varied register and 10 near-miss should-not-trigger prompts; check for collisions with existing skills' descriptions.
5. **Dry run**: phase order, hand-off paths, input/output fit, error branches executable.
6. **Record** one happy-path and at least one error-path scenario under `## Test scenarios` in the orchestrator.

### Step 7: Operate, maintain and improve

A harness is not a one-off artefact. Retrospectives and feedback belong to `finhub-harness-evolve` ("harness retrospective", "evolve the harness", "fold this feedback in"). This skill handles operation:

1. **Status check**: diff `.claude/agents/`, `.claude/skills/` and the orchestrator; list mismatches and report.
2. **Incremental change**: one item at a time, verify immediately.
3. **Change history**: date, change, target, reason in `CLAUDE.md`.
4. **Verify the change**: structure always; trigger test if a description changed; run test and dry run if the change is large; final `CLAUDE.md`-vs-files check.

Suggest `finhub-harness-evolve` when the same feedback recurs, an agent fails twice for the same cause, a QA report or judge verdict rejects for the same reason twice, or the user keeps doing the orchestrator's job by hand.

### Enriching from other harness repos

When the user wants a pattern from another harness (`"borrow the judge panel from repo Y"`, `"adopt how Z sandboxes code"`), do not copy. Pin the repo as a reference submodule, run the port-map procedure, then adopt the pattern through an Authority List row with its licence tier. `references/source-enrichment.md` has the procedure, the pinned repos and their tiers.

## Deliverable checklist

- [ ] Every reusable custom type has a file in `project/.claude/agents/`; one-offs on built-in types have none.
- [ ] Every needed `SKILL.md` and reference exists under `project/.claude/skills/`.
- [ ] One orchestrator skill with data hand-off, error policy, test scenarios and a declared target surface; a single-context fallback if chat or Cowork is a target.
- [ ] Execution mode written (per phase if mixed); no v1 artefacts.
- [ ] `scripts/lint_harness.py` exits 0 on `project/.claude`, and every `WARN` line is fixed or explained.
- [ ] `model:` chosen per agent from the task, with the reason as a comment; no blanket top-model setting.
- [ ] Workflow scripts: `.filter(Boolean)` present, `meta` literal, `parallel()` only for real barriers.
- [ ] Nothing written to `.claude/commands/`.
- [ ] Existing agents and skills checked for overlap before creating new ones; no name or role collision.
- [ ] Artefacts written in the user's language (or the existing harness's language).
- [ ] Every skill `description` names its trigger situations and follow-up phrasings.
- [ ] Every `SKILL.md` under 500 lines; detail moved to `references/`.
- [ ] Run with 2-3 realistic prompts; triggers validated with should and should-not cases.
- [ ] `CLAUDE.md` holds only the trigger pointer and change history.
- [ ] Orchestrator Step 0 distinguishes first run, follow-up and partial re-run (and `resumeFromRunId` for Workflow mode).
- [ ] Every `## Required connectors` line in an agent file has a row in the orchestrator's connector preflight table, and every row has a matching agent line.
- [ ] Every worker brief has Goal, Inputs, Scope, Expected output and Report; every worker report ends in STATUS / EVIDENCE / BLOCKER form; the orchestrator re-asks once and then marks the result unverified (a `once` phase is never re-asked).
- [ ] Every section that launches writers in parallel has a `## Writers` table with one ownership label per writer (`references/write-safety.md`); `python3 scripts/check_writers.py --require` on that orchestrator exits 0 (path relative to this skill's directory); a harness with one writer needs no table and is not run with `--require`.
- [ ] Borrowed patterns cited in an Authority List with licence tier; net-new decisions labelled with reason and test.
- [ ] If the harness builds software: QA runs the repo's real gates after every slice and reports `RESULT:` first, then `CANDIDATE:`; the orchestrator runs `candidate_id.py check` on that report before it commits.

## References

- Execution modes and v1→v2 migration: `references/execution-modes.md`
- Surfaces (Code / chat / Cowork) and the single-context fallback: `references/surfaces.md`
- Model selection: `references/model-selection-guide.md`
- Team patterns and agent definitions: `references/team-patterns.md`
- Worked team examples: `references/team-examples.md`
- Workflow scripts and pitfalls: `references/workflow-recipes.md`
- Orchestrator templates: `references/orchestrator-template.md`
- State ledger, rebuild and resume across context resets: `references/state-ledger.md`
- Run-once phases: a resume stops and asks about a half-done send, publish or record write (the ledger reads files only; an idempotency key accepted by the connector is the real fix): `references/state-ledger.md` section 3a
- Skill writing: `references/skill-writing-guide.md`
- Skill testing: `references/skill-testing-guide.md`
- QA agents: `references/qa-agent-guide.md`
- Authority List, adversarial audit, mutation-tested QA, honest reporting: `references/quality-gates.md`
- Naming the tree a verdict judged, and refusing a stale verdict: `references/quality-gates.md` §3-7 and `scripts/candidate_id.py` (adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0))
- Parallel writers, the ownership ladder and honest labels: `references/write-safety.md` (adapted from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0))
- Borrowing from other harness repos under licence rules: `references/source-enrichment.md`
