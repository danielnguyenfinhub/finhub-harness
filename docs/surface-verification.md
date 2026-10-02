# Surface verification: Claude chat and Claude Cowork

`skills/finhub-harness/references/surfaces.md` marks most chat and Cowork behaviour "unverified". This checklist closes those claims in about ten minutes per surface. Nothing here has been run yet; every result cell is empty on purpose.

## Setup

1. `bash scripts/package-plugin.sh` (writes `dist/`, which is git-ignored).
2. Chat: upload `dist/finhub-harness-skill.zip` and `dist/finhub-harness-evolve-skill.zip` as skills. Cowork: add `dist/finhub-harness.plugin`.
3. Use a fresh conversation per surface. Do not paste anything from `surfaces.md` into it.

## Probes

Run in order. Record exactly what happens, including error text. Do not retry a failure before recording it.

| # | Prompt (verbatim) | Pass looks like | Why it matters (`surfaces.md` claim) |
|---|---|---|---|
| P1 | `build a harness for a team that checks a loan document pack` | The `finhub-harness` skill is named as loaded and it starts Step 0 (context check / questions) | Skill trigger works at all |
| P2 | `Without calling anything, state yes or no for each tool you can call right now: Agent (sub-agents), SendMessage, Workflow, TaskCreate, file write, MCP connectors, hooks.` | An honest yes/no per tool | Lines 134-140: every "unverified (believed ✗)" cell |
| P3 | `Write a file called probe.md containing the word ping, then tell me where it is.` | Either a file you can open, or a clear statement it cannot | Lines 65, 125, 138: file writing, `_workspace/` handoff |
| P4 | `Spawn one sub-agent that replies with the word pong, and show me its reply.` | `pong` from a separate agent, or a clear refusal or error | Lines 63, 93, 101: sub-agent availability and isolation |
| P5 | Re-run P1 to completion, then read the orchestrator it wrote | Role-labelled sections in ONE context; no unconditional `Agent`, `SendMessage` or `Workflow` calls; "unverified — confirm in that surface" next to any step that depends on a feature P2-P4 did not confirm | The single-context fallback is what the factory promises |
| P6 | `harness retrospective: the document checker missed a missing signature page` | The `finhub-harness-evolve` skill loads | Companion skill trigger |

## Result sheet (fill in, then paste back)

| Probe | Chat result | Cowork result |
|---|---|---|
| P1 | | |
| P2 | 2026-10-03, Claude mobile app, file creation and connectors enabled. Self-reported, no calls made: Agent no, SendMessage no, Workflow no, TaskCreate no (native; connector task tools only), file write yes (outputs folder), MCP connectors yes but deferred (schema must be loaded first), hooks no. | |
| P3 | | |
| P4 | 2026-10-03, same chat. Declined: no sub-agent tool exposed, would not simulate a reply. Consistent with P2. | |
| P5 | | |
| P6 | | |

Also note: product and plan (for example Claude Pro or a Cowork build), the date, and whether any connector was attached.

## What happens next

Paste the sheet back. Each confirmed cell replaces "unverified" in `surfaces.md` with the observed behaviour and the date. Each cell that contradicts a "believed" claim is a defect in the factory's fallback and gets fixed through the normal design, judge and QA path. Cells you skip stay "unverified". The README Gaps section then shrinks to match.
