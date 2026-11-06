---
name: finhub-harness-light
description: "Low-token version of finhub-harness: builds a small agent team or a single skill in one pass, with at most two workers, cheap models, no judge or QA agents and a short orchestrator that can switch between light and full runs. Use when the user says 'light harness', 'quick harness', 'small harness', 'lean agent team', 'cheap harness', 'low-token harness' or 'light mode', when the job is one small task, and to switch a harness run to light ('run it light', 'switch to light'). Do NOT use for harnesses that decide money, eligibility, compliance or client-facing text, for software harnesses that need QA gates, or for borrowing patterns from reference repos: use finhub-harness for those."
---

# FinHub Harness Light

Build the smallest harness that does the job and spend as few tokens as possible doing it. Read only what you need, write short files, and ask nothing you can default. This skill is self-contained: it reads no other file.

## When light fits

- One small task or one repeatable job, with at most two roles.
- It is not an audited decision (money, eligibility, compliance, client-facing text) and not software that needs QA gates. If it is, write one sentence naming the risk and ask the owner whether to use the full skill `finhub-harness`. You never decide a gate yourself; the owner does.
- The user has not asked for a judge, QA agents or patterns borrowed from other repos.

## Three levels

The owner sets the level for each kind of work; you never pick or change it.
- **light**: what this skill builds. The work is checked with the real tests and lint; no judge, no QA agent. The default for small jobs.
- **standard**: one judge round, then one QA run on the real gates, no mutation tests unless the owner asks. Offer it for a normal expert build.
- **full** (`gated`): every judge round and QA check. Money, eligibility, compliance and client-facing text stay full unless the owner downgrades them through a ledger row.
For standard or full, say so and use the full skill `finhub-harness`.

## Outside effects

If the job can send, write a record, publish, share or pay, ask the owner whether to use the full skill `finhub-harness`, or build it only with this rule written into the skill under `## Ask before an outside effect`: show every call with its exact arguments first; make a call only after the owner's explicit yes to that list, each once; a no, no answer or a change sends nothing. Set `disable-model-invocation: true` in that skill's frontmatter. A worker that does not send gets a `tools:` allowlist with no `mcp__` tools; only the sender lists them.

## Procedure (one pass)

1. **Look cheaply.** List `.claude/agents` and `.claude/skills` and print only the `name:` lines (`ls`, `grep -m1 '^name:'`). Read a file only to extend it, and then only the lines you need. If something already covers the job, extend it; never add a second.
2. **Choose the shape.** The default is one skill, no agent file, and the main context does the work. Add a worker only when it needs different tools or a clean context and its job can be handed over as a file path. Never more than two. Having an `Agent` tool is not a reason to delegate: every worker spends tokens of its own.
3. **Write the files.**
   - Skill: `.claude/skills/{name}/SKILL.md`, under 120 lines. `description` says what it does and when to use it, including follow-ups such as "re-run" and "redo only X", in 600 characters or fewer, because every description sits in context all session. The body gives each rule with its reason, in the imperative.
   - Worker, only if step 2 allowed one: `.claude/agents/{name}.md` with `name`, `description`, `tools` (only what it needs; a read-only reviewer gets no Edit or Write), `model` with a `# reason` comment, `maxTurns`, and `effort: low` for look-up and format jobs.
   - Orchestrator: for a single agent the skill is the orchestrator. With workers, write one skill of about 50 lines holding the target surface, who does what in order, the hand-off files in `_workspace/`, one error rule (retry once, then record the gap and carry on) and the Run mode block below.
4. **Pick models by job.** `haiku` to extract, format or look up; `sonnet` to write or analyse; `opus` only if the user asks. On Claude Code the orchestrator passes `model` on each `Agent` call, and that value beats the agent file's `model:`, so one agent file serves both modes. Do not switch the main thread's model part-way through a session: the whole conversation is re-read uncached.
5. **Write these token habits into the skill.** Read by grep or line range, not whole files. A worker writes its detail to a file and returns at most 150 words, because a worker's result comes back into the parent's context. No fan-out unless the user asks for it.
6. **Update the `CLAUDE.md` pointer** with the block below.
7. **Check, cheaply.** `name` is kebab-case and at most 64 characters, `description` is at most 1024 characters, every file the skill mentions exists, and nothing uses `TeamCreate` or `SendMessage({to: "all"})` (v1 tools that fail silently now). Run one dry pass of the first step. If the full skill is installed, `python3 <finhub-harness dir>/scripts/lint_harness.py .claude` does the same checks; where no shell runs, tick the list by hand.
8. **Report in ten lines or fewer:** the files written, the shape (single agent or two workers), the models, what light skipped compared with the full skill, and how to switch.

## Run mode block

Paste this into an orchestrator that has workers. A single-agent skill keeps only the first two lines.

```markdown
## Run mode
The user picks per run by saying "light" or "full"; the default is {light or full}. Record the choice in `_workspace/mode.txt` so a resume keeps it.
- **light**: the main context does the work; at most two workers, one at a time; start each with `model: "haiku"` (extract, format, look up) or `"sonnet"` (write, analyse) on the `Agent` call; each returns at most 150 words and writes detail to `_workspace/`; read files by grep or line range; skip every phase marked `[full-only]` and any optional judge or QA agent, and list what was skipped in the report. A unit that the Rigor table runs `gated` or `standard` keeps its gates in light mode.
- **full**: every phase, with the models the agent files name.
```

## Surfaces

- **Claude Code:** as above.
- **Claude chat:** a sub-agent tool was not exposed in the one chat tested (2026-10-03, self-reported). Light needs none: a single-agent skill is the default, and a two-worker plan runs as two labelled passes in one context. Whether chat can write `.claude/` files depends on the account's tools; if it cannot, give the user the file text.
- **Claude Cowork:** unverified. Treat it like chat until a probe says otherwise.

## The `CLAUDE.md` pointer

Between two marker lines, each alone on its line, with the change history below the end marker:

````markdown
<!-- finhub-harness:begin {orchestrator-skill-name} -->
## Harness: {domain}

**Goal:** {one line}

**Trigger:** For {domain} work, use the `{orchestrator-skill-name}` skill. Simple questions may be answered directly.
<!-- finhub-harness:end {orchestrator-skill-name} -->

**Change history:**
| Date | Change | Target | Reason |
| --- | --- | --- | --- |
| {YYYY-MM-DD} | Initial build with finhub-harness-light | all | - |
````

Before writing, list the marker lines with `grep -n 'finhub-harness:' CLAUDE.md`. No file: create it. No marker for this name: back up with `cp -p CLAUDE.md CLAUDE.md.bak`, then append the block. One begin line above one end line: replace only the lines between them. Anything else (a second marker, a marker without its partner): write nothing and ask the user to fix the file. Keep the block to 1600 bytes or fewer; the history below it is never trimmed.

## Switching up

When the user wants a judge, QA agents, an audited design or patterns from other repos, say so and use the full skill `finhub-harness`.
