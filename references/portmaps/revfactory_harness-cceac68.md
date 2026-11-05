# Port map — revfactory_harness

- Submodule: references/revfactory_harness
- Pinned SHA: cceac68 (full `cceac68ea1d0ad198ef4b7b906cd238375836387`, confirmed with `git rev-parse HEAD`; last commit 2026-06-10, "Merge pull request #25")
- Licence: Apache-2.0 (`references/revfactory_harness/LICENSE`; licence-rules.md row `revfactory_harness`). No NOTICE file in the pin. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the harness-factory scope (every file of `skills/harness/`, `docs/`, `CONTRIBUTING.md`, the PR template, the release audit and the README evaluation section was opened). Runtime scope not mined: upstream has no runtime. README_KO, README_JA, `index.html`, `privacy.html` and `_workspace/0[1-4]_*` were not opened (see Gaps).
- Language: upstream is Korean Markdown (the skill text is Korean, `docs/` is English). "adapt" means English prose or a small script in `skills/finhub-harness/`.
- Id prefix: `R`.
- Scope: harness-factory patterns only; diffed against `skills/finhub-harness/`, `skills/finhub-harness-evolve/` and `skills/finhub-harness-light/`.
- Headline: the pin is upstream **v1.2.0** plus an Unreleased block (`references/revfactory_harness/.claude-plugin/plugin.json:4`, `CHANGELOG.md:5`), while `skills/finhub-harness/SKILL.md:8` says it was ported from **v2.1.0**. The local skill is therefore far ahead of this pin, and nearly everything here is already covered. Net-new material is in section (a) and is small.

## Already covered/adopted (do not re-propose)

Checked by grep and by opening the local lines named. Section (c) below holds the paired citations.

| upstream idea | where it lives now |
|---|---|
| Phase 0 audit and three-way branch, Phase selection matrix | `skills/finhub-harness/SKILL.md:27` (Step 0) and the table at :35-39 |
| Boundary cross-comparison QA, state-transition trace, incremental QA | `skills/finhub-harness/references/qa-agent-guide.md:31`, :65, :87 |
| Agent and skill reuse review, split criteria | `skills/finhub-harness/references/team-patterns.md:267`, :304; `skill-writing-guide.md:240` |
| Grader, blind comparator, analyzer; non-discriminating assertions; 60/40 description tuning | `skills/finhub-harness/references/skill-testing-guide.md:175`, :185, :243 |
| Retry cap and 50 percent REDO escalation | `skills/finhub-harness/references/team-examples.md:141` |
| Evolution triggers, feedback-to-target table | `skills/finhub-harness/SKILL.md:195`; `skills/finhub-harness-evolve/SKILL.md:72` |
| Pointer-only CLAUDE.md (extended with begin/end markers and a size budget) | `skills/finhub-harness/SKILL.md:163` (CLAUDE.md rows 2026-10-27, C33) |
| Follow-up trigger words in descriptions | `skills/finhub-harness/SKILL.md:172` |
| Progressive disclosure, 500-line limit, ToC on long references | `skills/finhub-harness/SKILL.md:120`; `skill-writing-guide.md:160` |
| Script bundling signals | `skills/finhub-harness/references/skill-writing-guide.md:166` |
| v1 team tools (`TeamCreate`, flag) detected and migrated to v2 | `skills/finhub-harness/SKILL.md:43`; `execution-modes.md:153` |

## Findings

### (a) Not in `skills/finhub-harness/` today (net-new candidates)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| R1 | release | Version audit: treat plugin.json as the authority, then sync README badges, marketplace.json and CHANGELOG to it | references/revfactory_harness/_workspace/release/audit-2026-04-18.md:42 | adapt | Ours: both manifests read 0.1.0; grep found no check across them. |
| R2 | release | Release audit opens with a Before table: each version source, its value and file:line, then names the mismatch | references/revfactory_harness/_workspace/release/audit-2026-04-18.md:10 | pattern | Report shape for R1; a script could print the same table. |
| R3 | release | Retroactive tags planned as annotated tags only, with the exact commands written down and held for explicit approval | references/revfactory_harness/_workspace/release/audit-2026-04-18.md:95 | reference | Matches our ask-first rule; nothing to build now. |
| R4 | docs | Regulated users run the factory at design time only, commit the plain Markdown output, and need no flag in production | references/revfactory_harness/docs/experimental-dependency.md:133 | adapt | FinHub is regulated; surfaces.md has no design-time wording (grep). |
| R5 | docs | Plan per plausible change of a platform dependency: detection trigger, time-boxed actions, user-visible artefact | references/revfactory_harness/docs/experimental-dependency.md:59 | pattern | Ours covers only v1 flag removal (execution-modes.md:153). |
| R6 | docs | Observable monitoring commitment: event, response time, how it is measured | references/revfactory_harness/docs/experimental-dependency.md:115 | reference | The hour counts are upstream's own promises; do not copy numbers. |
| R7 | docs | Quickstart failure FAQ: each entry names the step, the cause, then the fix | references/revfactory_harness/docs/quickstart.md:39 | pattern | `docs/QUICKSTART.md` has no failure section (grep for fail, cause). |
| R8 | release | PR template with CHANGELOG-updated and SemVer-impact checkboxes tied to commit types | references/revfactory_harness/.github/PULL_REQUEST_TEMPLATE.md:47 | pattern | `.github/` here holds only `workflows`; mapping table is CONTRIBUTING.md:161. |
| R9 | evaluation | Each effect-size claim carries sample size and "author-measured"; readers are told to run their own pilot | references/revfactory_harness/README.md:259 | pattern | No equivalent wording in our skills or docs (grep). Upstream's +60 percent is unverified. |
| R10 | team size | Team size by workload: 2-3 members for small, 3-5 medium, 5-7 large, with tasks per member | references/revfactory_harness/skills/harness/SKILL.md:248 | adapt | Ours has "three to five agents" (execution-modes.md:84) and 3-6 tasks (orchestrator-template.md:159). Partial. |

### (b) Same as ours, but with a different emphasis

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| R11 | skills | Cost warning in the quickstart: one complex task can cost 50K-200K tokens; run one task per invocation | references/revfactory_harness/docs/quickstart.md:97 | reference | Its `--max-turns` hint is hedged; our CLAUDE.md row 2026-11-05 leaves that flag unclaimed. |
| R12 | skills | Description rules: Claude under-triggers on simple tasks, so describe the job and the trigger situations and draw the boundary | references/revfactory_harness/skills/harness/references/skill-writing-guide.md:24 | reference | Local `skill-writing-guide.md:31` and :37 already say the same. |

### (c) Already covered (upstream citation, local citation in notes)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| R13 | coordinator | Phase 0 audit routes to new build, extend or maintain; Phase selection matrix says which phases an extension runs | references/revfactory_harness/skills/harness/SKILL.md:18 (matrix at :28) | reference | Covered: local SKILL.md:27, :35-39. |
| R14 | verification | QA reads both sides of a boundary, traces state transitions, and runs after each module | references/revfactory_harness/skills/harness/references/qa-agent-guide.md:40 (incremental at :131) | reference | Covered: local qa-agent-guide.md:65, :87, and far extended (mutants). |
| R15 | coordinator | Reuse review before adding an agent: reuse, generalise, keep separate or create, by overlap | references/revfactory_harness/skills/harness/references/agent-design-patterns.md:262 | reference | Covered: local team-patterns.md:304; skills at skill-writing-guide.md:240. |
| R16 | evaluation | Grader, blind comparator and analyzer roles; drop assertions that every run passes | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:166 | reference | Covered: local skill-testing-guide.md:175, :185. |
| R17 | evaluation | Tune a description on 20 queries, 60/40 split, choose by the test half, at most five rounds | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:264 | reference | Covered: local skill-testing-guide.md:243. |
| R18 | verification | Reviewer verdict PASS, FIX or REDO; two redo rounds, then stop; at half REDO ask for a prompt change | references/revfactory_harness/skills/harness/references/team-examples.md:238 | reference | Covered: local team-examples.md:141. Upstream forces PASS after two loops; we report instead. |
| R19 | retrospective | Evolve on repeated feedback, repeated failure or user bypass of the orchestrator; map feedback type to the file to change | references/revfactory_harness/skills/harness/SKILL.md:373 (triggers at :400) | reference | Covered: local SKILL.md:195; evolve SKILL.md:72, far extended. |
| R20 | coordinator | Maintenance workflow: audit, one change at a time, sync change history, verify | references/revfactory_harness/skills/harness/SKILL.md:407 | reference | Covered: local SKILL.md:186-190 (Step 7). |
| R21 | memory | CLAUDE.md holds only a trigger pointer and a change-history table, not agent or skill lists | references/revfactory_harness/skills/harness/SKILL.md:258 | reference | Covered and extended: local SKILL.md:163 (markers, 1600-byte budget). |
| R22 | coordinator | Orchestrator step 0 picks first, partial or new run from `_workspace/`; description carries follow-up words | references/revfactory_harness/skills/harness/references/orchestrator-template.md:37 (keywords at :277) | reference | Covered: local SKILL.md:172 and orchestrator-template. |
| R23 | skills | Bundle a script when three of three runs write the same helper; also known-error notes | references/revfactory_harness/skills/harness/references/skill-writing-guide.md:188 | reference | Covered: local skill-writing-guide.md:166. |

## Do not port

| source | reason |
|---|---|
| references/revfactory_harness/skills/harness/SKILL.md:93 (every agent runs on `opus`) | Local model-selection-guide.md tiers models by job; the CLAUDE.md 2026-11-05 row adds a light mode. |
| references/revfactory_harness/skills/harness/SKILL.md:189, references/revfactory_harness/skills/harness/references/orchestrator-template.md:11 and :260, references/revfactory_harness/skills/harness/references/agent-design-patterns.md:7 | `TeamCreate`, `TaskCreate`, `TeamDelete` and the experimental flag are v1; local SKILL.md:43 treats them as legacy to migrate. |
| references/revfactory_harness/skills/harness/SKILL.md:95 (rebuild the team between phases) | Depends on the same v1 team tools. |
| references/revfactory_harness/CONTRIBUTING.md:56 and :192 (maintainer contact emails, maintainer list) | Personal contact details and an upstream's governance; not ours to copy. |
| references/revfactory_harness/CONTRIBUTING.md:13 (72-hour and 48-hour response times, biweekly release) | Upstream's own commitments; nothing in them for a plugin with one owner. |
| references/revfactory_harness/README.md:253 (+60 percent, 15 of 15 wins) | Author-measured, n=15, replications pending by its own line :259; not evidence for our harness. |
| references/revfactory_harness/README.md:229 (neighbour repo positioning), `index.html`, `privacy.html`, `*.png` | Marketing and site assets; no pattern. |
| references/revfactory_harness/docs/quickstart.md:99 (`--max-turns`) | Hedged upstream ("if your version supports it"); unverified, and our rules say not to claim it. |

## Gaps

- **Version gap.** The pin is v1.2.0 (plugin.json:4) with an Unreleased block (CHANGELOG.md:5). Local SKILL.md:8 says the port came from v2.1.0, so v2 material is absent from this pin: the Workflow execution mode, the A/B-as-workflow testing, the surface rules. Local skill-testing-guide.md:85 ("Running A/B tests as a workflow (v2)") has no upstream counterpart here. To mine v2.x, the submodule would need a newer pin; the pin is the fork `danielnguyenfinhub/harness` (`.gitmodules`), not the upstream URL, and its freshness against upstream was not checked.
- licence-rules.md says an installed copy lives at `~/.claude/skills/harness`; it was not opened here, and may be a newer version than the pin.
- No coordinator prompts with standing reminders, no permission or denylist rules, no hooks, no memory ledger, no judge panel and no mutation or eval runner exist in this repo (searched file names and the five reference files). Those areas for the factory come from other pins (openharness, openrig, hive).
- No `scripts/` directory: CONTRIBUTING.md:105 mentions `scripts/validate_skills.py` "if present", and the tree has none. There is no lint to port.
- Not opened: README_KO.md, README_JA.md (translations of README.md), `index.html`, `privacy.html`, `_workspace/01_auditor_repo_audit.md`, `_workspace/02_content_launch_contents.md`, `_workspace/03_scout_outreach_map.md`, `_workspace/04_strategist_launch_plan.md`, `_workspace/release/post-m0-audit-2026-04-18.md` and the issue templates. The `_workspace/` files look like launch-marketing working papers; treat as unmined.
- Local-side checks were by grep and by opening the lines cited, not a full read of every local file. R8's claim that no PR template exists rests on `ls .github` showing only `workflows`.
