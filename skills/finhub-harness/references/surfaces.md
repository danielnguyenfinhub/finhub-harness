# Running a harness on each Claude surface

A harness is a team of roles, a workflow that connects them, and handoff artefacts. How much of that a surface can run natively differs. This file says, per surface, what the packaging is, which orchestration primitives exist, how the three execution modes degrade, and how the generated orchestrator must adapt.

Terms:

- **Mode A: Workflow orchestration.** A scripted run (pipeline, parallel fan-out, phases, schema-checked outputs) driven by the Workflow tool.
- **Mode B: Persistent agent collaboration.** Named, long-lived agents that exchange messages and share a task list.
- **Mode C: Sub-agent delegation.** The orchestrator spawns one-shot sub-agents, each with a task and a file hand-off.

Claims marked "unverified — confirm in that surface before relying on it" are things the author could not establish. Do not build on them without checking.

## 1. Claude Code

### Packaging

A Claude Code plugin is a directory:

```
<plugin>/
  .claude-plugin/plugin.json    # manifest (name, version, description)
  skills/<skill-name>/SKILL.md  # skills, each with optional references/
  agents/<agent-name>.md        # custom agent types
```

Project-local harnesses live in the repo instead: `.claude/skills/`, `.claude/agents/`, and `CLAUDE.md` for the pointer and change history.

### Orchestration primitives

| Primitive | What it does |
|-----------|--------------|
| `Agent` | Spawns a sub-agent. `name:` makes it addressable (persistent). `run_in_background` runs it without blocking. `subagent_type` selects a custom type defined in `.claude/agents/`. |
| `SendMessage` | Sends a message to a named agent. |
| `TaskCreate` / `TaskUpdate` / `TaskList` | Shared task list for coordination. |
| `Workflow` | Scripted runs: `pipeline`, `parallel`, `agent`, `phase`, `schema`, `resumeFromRunId`. The user must opt in before a workflow runs. |
| `Skill` | Loads a skill's instructions into the turn. |
| Files (`_workspace/`) | Handoff artefacts between roles. |

The v1 team-creation and team-deletion tools do not exist, and the experimental agent-teams environment flag is not needed. An orchestrator that still uses them (or a v1 team-name parameter) is a v1 artefact and must be migrated, not copied. `scripts/package-plugin.sh` greps for these and fails the build.

### Modes on Claude Code

| Mode | Status | How |
|------|--------|-----|
| A: Workflow | Native, opt-in | Use `Workflow`. Ask the user to opt in; if they decline, fall back to Mode C. |
| B: Persistent agents | Native | `Agent` with `name:` plus `SendMessage` plus the task tools. |
| C: Sub-agents | Native | `Agent` with `subagent_type`, hand off via files. |

### Orchestrator rule

Write all three modes. State which is the default, when to pick each, and what the fallback is (A to C when the user does not opt in; B to C when messaging is not needed). Handoffs go through `_workspace/` files so any mode can resume from them.

## 2. Claude chat (claude.ai)

### Packaging

A skill is uploaded as a zip of the skill folder (`SKILL.md` plus `references/`) in the Anthropic skills format. The frontmatter is the same `name` and `description`. The zip contains the skill folder only, not a plugin manifest and not agent definitions.

`dist/finhub-harness-skill.zip` and `dist/finhub-harness-evolve-skill.zip` (from `scripts/package-plugin.sh`) are this format.

### Orchestration primitives

Sub-agent, `SendMessage`, Task and Workflow tools are believed unavailable — unverified — confirm in that surface before relying on it. Until confirmed, do not tell a chat-surface orchestrator to call them. A "team" runs as ONE context that plays each role in turn.

Whether chat can write files or create artefacts depends on the account's tool settings: unverified — confirm in that surface before relying on it. Whether connectors or MCP tools are attached in a given chat also varies: unverified — confirm in that surface before relying on it.

### Modes on Claude chat

| Mode | Status | How |
|------|--------|-----|
| A: Workflow | Degraded | Each workflow phase becomes a labelled section, run in order in one context. |
| B: Persistent agents | Degraded | Roles become labelled turns of the same context. Agent-to-agent messaging believed unavailable (unverified). |
| C: Sub-agents | Degraded | Each sub-agent becomes a labelled role pass. Context isolation believed unavailable (unverified). |

### The degradation rule

1. **One section per phase.** Every phase of the workflow becomes a clearly labelled section, such as `## Phase 2: Strategy (role: strategy-architect)`. The model states the role it is playing at the top of the section and stays inside it.
2. **Handoffs are written inline.** The orchestrator writes each handoff artefact as a labelled block in the conversation. If the surface lets it create files or artefacts, it writes them there as well. Later phases quote the block, not memory.
3. **Adversarial verification is a separate labelled pass.** The judge or QA role runs as its own section with a fresh-eyes instruction: "Re-read only the artefact above, not the reasoning that produced it. Assume it is wrong and try to show where." A same-context pass is weaker than a separate agent; the report must say so.
4. **Parallel fan-out becomes sequential.** Items are processed one after another. The orchestrator states an item cap (for example, "at most 6 items per run; list the rest as not processed") so one context is not overrun.
5. **Say what was lost.** The final report notes which isolation or parallelism guarantees were not available.

## 3. Claude Cowork

### Packaging

A Cowork plugin is believed to be the same directory as a Claude Code plugin, zipped and named `<name>.plugin` (for this repo, `dist/finhub-harness.plugin`); skills under `skills/*/SKILL.md` the primary unit, agents uncommon, hooks rare. Unverified — confirm in that surface before relying on it.

Users are believed to attach connectors (CRM, Google Workspace and similar) rather than repo tools. Unverified — confirm in that surface before relying on it. A Cowork orchestrator should name the capability it needs ("read the CRM contact") and not assume a specific repo tool exists.

### Orchestration primitives

Skills and connectors are the reliable surface. Multi-agent orchestration (sub-agents, named agents, messaging, workflows) on Cowork: unverified — confirm in that surface before relying on it. Plan on single-context execution unless it is confirmed.

### Modes on Claude Cowork

| Mode | Status | How |
|------|--------|-----|
| A: Workflow | unverified | Do not assume a Workflow tool. Use phased sections. |
| B: Persistent agents | unverified | Do not assume named agents or messaging. Use role-labelled turns. |
| C: Sub-agents | unverified | If sub-agents are confirmed, delegate. Otherwise role passes. |

### Orchestrator rule

Treat Cowork like chat until a surface check says otherwise: write a `## Single-context fallback` section, apply the degradation rule from section 2, and use connectors for external data. Any step that writes to a connector (send, update, delete) needs an explicit confirmation point in the workflow, since a single context has no separate approver.

## 3a. Choosing a mode per surface

| Situation | Claude Code | Claude chat | Claude Cowork |
|-----------|-------------|-------------|---------------|
| Same fan-out every run, many items | Mode A | Sequential phases with an item cap | Sequential phases with an item cap (unverified whether more is possible) |
| Roles must debate or hand work back and forth | Mode B | Role-labelled turns | Role-labelled turns |
| Independent one-shot tasks, file hand-off | Mode C | Role passes | Role passes unless sub-agents are confirmed |
| Needs an independent verifier | Separate agent (B or C) | Separate labelled pass, weaker | Separate labelled pass, weaker |

Rule of thumb: pick the strongest mode the surface supports, write the weaker one as the declared fallback, and never let the fallback silently skip the verification step.

## 3b. What survives the move between surfaces

| Artefact | Code | Chat | Cowork |
|----------|------|------|--------|
| `SKILL.md` frontmatter (`name`, `description`) | used | used | used |
| `references/*.md` loaded on demand | used | used (inside the zip) | used |
| `agents/*.md` custom types | used | believed not applicable (unverified) | uncommon; unverified |
| `_workspace/` handoff files | used | inline blocks instead (file writing unverified) | unverified |
| Change history in `CLAUDE.md` | used | believed unavailable (unverified); keep it in the skill or ask the user to store it | unverified |

## 4. Primitive by surface

Legend: ✓ available, degraded (works with reduced guarantees), ✗ not available, unverified (confirm in that surface before relying on it).

| Primitive | Claude Code | Claude chat | Claude Cowork |
|-----------|-------------|-------------|---------------|
| `Agent` (sub-agents) | ✓ | unverified (believed ✗) | unverified |
| Named agents + `SendMessage` | ✓ | unverified (believed ✗) | unverified |
| `Workflow` | ✓ (user opt-in) | unverified (believed ✗) | unverified |
| Tasks (`TaskCreate`/`TaskUpdate`/`TaskList`) | ✓ | unverified (believed ✗) | unverified |
| Files / `_workspace/` | ✓ | degraded (inline blocks; files only if the account provides them, unverified) | unverified |
| Connectors / MCP | ✓ (MCP servers configured in the session) | unverified | unverified (believed ✓) |
| Hooks | ✓ | unverified (believed ✗) | unverified (rare) |

## 5. How the factory must write the orchestrator

1. **Declare the target surface(s).** The orchestrator's frontmatter or description names where it runs: `Claude Code`, `Claude chat`, `Claude Cowork`, or a combination. If the user did not say, ask once; default to Claude Code only.
2. **Write Mode A, B and C for Claude Code.** Each mode has its own section with the exact primitives from section 1, a default choice, and a fallback.
3. **Add `## Single-context fallback` whenever chat or Cowork is a target.** The section applies the degradation rule from section 2: labelled phases, inline handoffs, a labelled fresh-eyes verification pass, and sequential fan-out with a stated item cap.
4. **Never name a primitive the target surface lacks.** In the single-context section, do not mention `Agent`, `SendMessage`, `Workflow` or Tasks as things to call.
5. **Never emit v1 artefacts.** No v1 team-creation or team-deletion calls, no v1 team-name parameter, no experimental agent-teams flag, on any surface.
6. **Mark uncertainty.** Where the orchestrator depends on a surface feature that is not verified, write "unverified — confirm in that surface before relying on it" next to the step.

## 6. Checklist before shipping a generated harness

| # | Check | Pass when |
|---|-------|-----------|
| 1 | Target surface declared | Orchestrator frontmatter or description names every target surface |
| 2 | Code modes complete | Mode A, B and C sections exist, each with a default and a fallback |
| 3 | Single-context fallback present | `## Single-context fallback` exists if chat or Cowork is a target |
| 4 | No foreign primitives | The fallback section names no sub-agent, `SendMessage`, Task or Workflow call |
| 5 | No v1 artefacts | `scripts/package-plugin.sh` v1-artefact grep passes |
| 6 | Packaging matches surface | Code: plugin dir. Cowork: `<name>.plugin` zip. Chat: skill-folder zip with `SKILL.md` at its root |
