---
name: finhub-harness-evolve
description: "Harness evolution skill. Collects and generalises feedback on the run results of a harness in use, applies it to the agents, skills and orchestrator, captures the delta against the initial setup, and updates the change history. Always use this skill when the user asks to improve an existing harness from its run experience: 'harness retrospective', 'evolve the harness', 'evolve the finhub harness', 'apply feedback to the harness', 'improve the harness', 'the result was disappointing, fix the harness', 'fold this feedback into the harness', 'fold feedback into the harness', 'summarise harness lessons'. New harness builds, structural redesign and adding agents belong to the finhub-harness skill."
---

# Harness Evolve — the evolution mechanism for harnesses
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

A harness is not a fixed artefact; it is a system that evolves. This skill captures the delta of "what worked and what did not" and feeds it back into the harness, so the next run is measurably better.

```
Initial harness ──▶ Use on a real project ──▶ Current harness
                                                   │
                                                   ▼ (capture the delta with evolve)
                                   Generalise feedback → apply to agents, skills, orchestrator
                                                   │
                                                   ▼
                                   Update change history → the next run starts from a better draft
```

## Workflow

### Phase 1: Collect the delta

1. Read `.claude/agents/`, `.claude/skills/` and `CLAUDE.md` (the change-history table).
2. If this is a git repository, inspect the history of the harness files (`git log --oneline -- .claude/ CLAUDE.md`) to see what changed since the initial setup, when, and why.
3. If `_workspace/` exists, skim the intermediate artefacts of the most recent run for evidence of what actually executed:
   - Do the artefacts exist at the paths the orchestrator defines? (If not, the workflow was bypassed or is dead code.)
   - Does artefact quality follow the format and criteria the skills specify?
4. Ask the user for feedback (skip if they already gave it):
   - "Is there anything in the results you would improve?"
   - "Is there anything about the agent composition or workflow you would change?"
   - Do not press if there is no feedback. But if any observation signal below is present, proactively propose improvements.

**Observation-based evolution signals (propose even without feedback):**
- Traces of the same kind of correction request two or more times.
- A pattern of an agent repeatedly failing or retrying.
- Traces of the user bypassing the orchestrator and working by hand (suspect an orchestrator trigger failure; candidate fix: expand the description).
- v1 artefacts left in the orchestrator (the removed v1 team-creation and team-deletion calls, or the experimental agent-teams flag) — point to the migration procedure in the finhub-harness skill.

### Phase 2: Classify the feedback type and map it to a target

| Feedback type | Target to modify | Example |
|---------------|------------------|---------|
| Output quality | The skill of the responsible agent | "The analysis is too shallow" → add depth criteria to the skill |
| Agent role | Agent definition `.md` | "Security review is needed too" → point to the finhub-harness skill to add an agent |
| Workflow order | Orchestrator skill | "Verification should come first" → change the Phase order |
| Team composition | Orchestrator + agents | "These two could be merged" → merge the agents |
| Missed trigger | Skill description | "It did not fire on this phrasing" → expand the description |
| Execution mode mismatch | Orchestrator | "It is the same fan-out every time and it is slow" → switch to workflow mode |
| Scale/cost | Orchestrator | "It uses too many tokens" → shrink the default scale, add budget linkage |

**Scope judgement:** if the change needs a new agent, a deleted agent or an architectural redesign, do not do it in this skill; point to the finhub-harness skill (the extend-an-existing-configuration procedure in its Phase 0). Evolve focuses on **adjusting the existing configuration**.

### Phase 3: Generalise and apply

1. **Generalise the feedback.** A narrow fix that only fits one case is overfitting. "The introduction was long in this report" should not become "keep the introduction under 10% of the whole". Find why it ran long (the skill had no length-allocation criterion) and fix it at the level of principle.
2. **Record the Why with the change.** Put the reason next to the amended instruction. Knowing the reason lets the agent judge edge cases correctly.
3. Apply changes one at a time, and run Phase 4 right after each change.
4. **Regression guard:** if a fix would reverse an earlier fix in the change history, tell the user about the conflict and get confirmation. (If it was shortened before for "too long" and now the complaint is "too short", the right answer is a criterion that satisfies both.)
5. **Keep the language of the existing file.** Sentences you add to agents, skills, orchestrators and `CLAUDE.md` are written in the language already used in the file being modified. Do not mix this skill's language into a harness written in a different language.

### Phase 4: Update the change history and verify

1. Record the change in the **change history** table of CLAUDE.md:

```markdown
**Change history:**
| Date | Change | Target | Reason |
|------|--------|--------|--------|
| 2026-07-19 | Added tone guide | skills/content-creator | "Too stiff" feedback |
```

2. Verify the structure of the modified files (frontmatter, reference consistency).
3. If you changed a description, run trigger verification (at least 3 should-trigger and 3 near-miss queries).
4. Do a final check that CLAUDE.md matches the actual files.

### Phase 5: Evolution report

Report to the user:
- A summary of the captured delta (initial configuration → current).
- The changes applied this time and the generalisation behind each.
- Feedback you decided not to apply, and why (if any).
- The improvement expected on the next run.

## Principles

- **The delta is an asset.** The more change history accumulates, the more a later harness build in the same domain starts from a draft closer to release state. Never delete the history.
- **No application without generalisation.** Adding one rule per case, 1:1, turns a skill into a pile of rules. Compress to principles.
- **One at a time.** If you apply several changes together you cannot tell which one helped.

## FinHub additions

1. **Failure recurrence is an evolve signal.** When a run's QA report (`RESULT: FAIL`) or a judge verdict (`REJECTED > 0`) recurs for the same reason twice, treat that as an evolve signal even without user feedback.
2. **Where the lesson is written.** Write the generalised lesson to the project's change history, AND, if the operator uses Super Memory, as a `remember` call with `kind:"learning"` tagged with the harness name. Never write client data into either.
