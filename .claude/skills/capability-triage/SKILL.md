---
name: capability-triage
description: "Turns the nine reference port maps into one ranked adoption backlog for the finhub-harness plugin and runtime, with a licence gate, a weighted score per candidate (value, licence, effort, risk, novelty) and a proof test each. Used by the capability-scout agent inside master-finhub-orchestrator; invoke directly only for: rank the port maps, re-rank after re-mining, compare two candidates, explain a backlog score. A request to run the whole adoption flow ('capability backlog', 'what should we adopt next', 'improve finhub harness from the reference repos') goes to master-finhub-orchestrator. Not for mining a repo (reference-mining), designing an adoption (runtime-slice-design) or auditing a design (adversarial-audit)."
---

# Capability Triage

Nine port maps hold more ideas than the repo can absorb at once. This skill ranks them so one design round at a time goes to the idea most worth it, and so the ranking can be argued with: every score is shown, every rejection has a reason, every candidate has a test.

## Steps

1. **Inventory what exists.** List `skills/*/SKILL.md` sections, `.claude/agents/*.md`, `.claude/skills/*/`, `src/master_finhub/**/*.py` module names and the `CLAUDE.md` change history. A candidate already present in the tree goes to **Already have** with the file that holds it. Partial presence is a candidate with novelty 0.5.
2. **Extract candidates.** Read every Findings table. One candidate per idea; when several maps carry the same idea, list all source rows and prefer the one with the cleanest licence tier as primary.
3. **Gate on licence** before scoring, from `references/LICENSES.md` and `licence-rules.md`: blocked sources (`autogpt_platform/**`) never enter the table; dify is pattern-only; no licence row means `reference` until Daniel confirms.
4. **Score** each survivor with `references/scoring-rubric.md`. Record each criterion's score and the one-line reason, then the weighted total to two decimals. Tag the evidence `[verified]`, `[assumed]` or `[missing]`; a `[missing]` criterion takes the rubric's lower bound.
5. **Name the proof.** For every candidate, the command, test or probe that would show the adoption works, and what failure would look like. No proof, no backlog row.
6. **Write the backlog** in the layout below. Rank by total, break ties by lower effort, then by cleaner licence. The `## Backlog` table holds at most 12 rows; every scored candidate ranked 13th or lower goes under `## Deferred` as id, capability and total only, keeping its id so it can be promoted on a re-rank without renumbering.

## Output layout

`_workspace/01b_capability-scout_backlog.md`:

```markdown
# Capability backlog — {date}, from the available port maps

## Already have
| capability | where it lives | source rows that match |

## Backlog
| id | capability | source rows | target | licence | value | licence | effort | risk | novelty | total | proof |

## Top 3 in detail
### C1 — {capability}
What it is · why it ranks here · adoption shape (which file(s), roughly how big) · proof test · risks and the "does not cover" line · effort S/M/L.

## Deferred
| id | capability | total |   (scored, ranked 13th or lower; ids stable)

## Rejected
| candidate | reason (licence / no proof / duplicate / low value) |

## Gaps
Patterns the request wanted that no map offers, with the search terms the miners recorded.
```

## Rules and why

- **Show the criterion scores.** A total alone cannot be challenged; Daniel and the judge need to see which weight carried a row.
- **Ranking is advice.** The orchestrator stops after this file and waits for Daniel's pick; the backlog never auto-selects.
- **Targets are concrete.** `plugin skill` (a section or reference under `skills/`), `agent` (`.claude/agents/*.md`), `runtime module` (`src/master_finhub/**`) or `docs`. A candidate that needs two targets is two rows.
- **Keep the ids stable** across re-runs so verdicts and reports can refer to `C3` months later.
- **Synthetic examples only.** No client names, Mercury records or secrets in any example.

## On re-run

Read the prior backlog first. Re-score only rows whose source map changed or that Daniel flagged; carry the rest unchanged; list the changed ids under `## Changes` at the top.
