# Port map — harness_100

- Submodule: references/harness_100
- Pinned SHA: 8e8d35c (confirmed with `git rev-parse --short HEAD`)
- Licence: Apache-2.0 ("Copyright 2026 Robin", `references/harness_100/LICENSE`; licence-rules.md row `harness_100`). No NOTICE file. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the harness-factory scope (pattern extraction), by sampling. Read in full: the `01-youtube-production` harness (orchestrator, reviewer, scriptwriter, strategist, SEO agent, one extension skill) and the orchestrator or agent files named in the table for 04, 22, 27, 30, 38, 52, 60, 66, 69, 28 and 94. Corpus shape checked by command over all of `ko/`. Not read: the other ~85 harnesses, `en/`, any domain skill body beyond its head. No runtime scope was requested.
- Source tree: `ko/` only (authoritative). Cited paths are written in full; two rows cite `README_ko.md` at the submodule root.
- Id prefix: `HH`.
- Language: sources are Korean prose and Markdown. "adapt" means rewrite the idea in English prose or a lint rule under `skills/` with the Apache-2.0 attribution line. No code is ported.

## What the corpus is (verified by command, not by reading every file)

- 100 harness folders under `ko/`, each `NN-name/.claude/{CLAUDE.md, agents/, skills/}`.
- 489 agent files (4 or 5 per harness: 11 harnesses have 4, 89 have 5) and 315 skill files, every skill named `skill.md`.
- Frontmatter has `name` and `description` only: 0 of 489 agent files carry `model:` or `tools:`.
- All 100 orchestrator skills share the same 8 `##` headings (grep counts of 100 each): execution mode, agent roster, workflow, scale modes, data protocol, error handling, extension skills, test scenarios.
- 87 orchestrators say "5 agents talk by SendMessage"; 429 of 489 agent files never name `SendMessage` (the protocol lives only in prose).
- 82 skill files contain a "max 2" rework cap; 243 contain an explicit out-of-scope sentence.

## Already covered in this repo (do not re-propose)

Checked by grep of `skills/finhub-harness/SKILL.md` and `skills/finhub-harness/references/*.md` for each term; only presence was checked, not wording quality.

| idea | present in finhub-harness? |
|---|---|
| `_workspace/00_input` intake, existing-file reuse, should-trigger / NOT-trigger, test scenarios | yes (e.g. `orchestrator-template.md:149`) |
| severity labels, rework cap | present in at least one reference file; HH7 and HH8 only add detail |

harness-100 and revfactory/harness share this skeleton, so most rows below are confirmations; the new value is in HH12, HH16, HH17, HH18, HH20 and HH21.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| HH1 | meta | Fixed folder skeleton per harness: CLAUDE.md, agents/, one orchestrator skill plus extension skills | references/harness_100/README_ko.md:27 | reference | Same as revfactory layout; confirms it. |
| HH2 | meta | Every orchestrator uses the same eight sections in the same order | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:10 | pattern | Lint candidate: required-section list. Count 100/100 by grep. |
| HH3 | meta | Roster table: agent, file path, role, agent type | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:16 | pattern | Type is always general-purpose; no tool or model column. |
| HH4 | meta | Phase 1 done by the orchestrator itself: extract inputs, make workspace, save input, copy user files, pick mode | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:26 | pattern | Marks required vs optional input fields in bold labels. |
| HH5 | meta | Task table with order id, owner, dependencies and one output file each; 2a/2b marks parallel work | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:42 | adapt | Parallel only when both depend on the same single predecessor (line 50). |
| HH6 | meta | Hand-off lines state exactly what each finished agent passes to which named teammate | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:52 | adapt | Content-level contract, not just "send results". Good lint target. |
| HH7 | meta | Last agent cross-checks all outputs pairwise, labels findings red/yellow/amber-green, asks the owner agent to fix | references/harness_100/ko/01-youtube-production/.claude/agents/production-reviewer.md:18 | adapt | Checklist pairs at :25-46; no commands run, judgment only. |
| HH8 | meta | Rework loop for a must-fix finding: request fix, redo, re-verify, at most 2 times | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:103 | adapt | Same cap in 82 skills. Does not say what happens after round 2. |
| HH9 | meta | Scale modes table maps request wording to a mode and the exact agent subset | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:76 | adapt | Includes a reviewer-alone mode; matches our light/full idea. |
| HH10 | meta | User-supplied artefact is copied into its numbered slot and that stage's agent is skipped | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:84 | adapt | Numbered filenames make the skip rule mechanical. |
| HH11 | meta | Three hand-off channels named with purpose: files, messages, task list; filename rule number_agent_artefact | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:88 | adapt | Convention at :94. |
| HH12 | meta | Error table: one retry, then continue without the artefact and list the omission in the review report | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:102 | adapt | Missing output must be named, never silent. Check our template says so. |
| HH13 | meta | Extension skill ties to one agent; its description names that agent and says what stays with the orchestrator | references/harness_100/ko/01-youtube-production/.claude/skills/hook-writing/skill.md:3 | adapt | Also :8 restates the target agent. 50 skills have a target-agent heading. |
| HH14 | meta | Orchestrator description lists trigger phrases, covers the existing-file case, then ends with an explicit out-of-scope sentence | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:3 | adapt | Lint: description must carry a not-for sentence. |
| HH15 | meta | Three test scenarios per orchestrator: normal, existing-file, error, each with expected results | references/harness_100/ko/01-youtube-production/.claude/skills/youtube-production/skill.md:114 | adapt | Expected results are checkable bullets (counts, files). |
| HH16 | meta | Agent file anatomy: role intro, core roles, work principles, deliverable format, team protocol, error handling | references/harness_100/ko/01-youtube-production/.claude/agents/content-strategist.md:62 | adapt | Protocol lists one line per recipient; error section at :69. |
| HH17 | meta | Agent names its output file path and gives a fenced template for that file | references/harness_100/ko/01-youtube-production/.claude/agents/scriptwriter.md:26 | adapt | Output path matches the orchestrator task table. Lint: path agreement. |
| HH18 | meta | Per-harness CLAUDE.md: one-line purpose, structure tree, trigger sentence, list of workspace artefacts | references/harness_100/ko/01-youtube-production/.claude/CLAUDE.md:5 | reference | Pointer is a full tree, unbounded; our marked-block budget is tighter. |
| HH19 | meta | Quality bar of eight criteria stated once for the whole collection | references/harness_100/README_ko.md:46 | pattern | Usable as a checklist for harness lint; criteria listed at README_ko.md lines 47-57. |
| HH20 | meta | Pure sequential chain with a tester-to-engineer fix loop and no parallel stage | references/harness_100/ko/22-legacy-modernizer/.claude/skills/legacy-modernizer/skill.md:40 | pattern | Feedback edge at :52 sits outside the final review loop. 10+ harnesses lack parallel stages. |
| HH21 | meta | One source fans out to three converters in parallel, then one quality reviewer | references/harness_100/ko/04-content-repurposer/.claude/skills/content-repurposer/skill.md:41 | pattern | Siblings also pass hints sideways (:53-54). |
| HH22 | meta | Adversarial pair: pro and con built in parallel, orchestrator relays cross-examination, judge scores, rapporteur writes | references/harness_100/ko/60-debate-simulator/.claude/skills/debate-simulator/skill.md:40 | pattern | Orchestrator-mediated exchange at :57-64; independent first drafts then cross. |
| HH23 | meta | Coordinator-style QA: final agent is a coordinator that verifies consistency instead of a named reviewer | references/harness_100/ko/66-contract-analyzer/.claude/skills/contract-analyzer/skill.md:18 | reference | 51 of 100 last agents are called reviewer; others vary (:57 shows the rework rule). |
| HH24 | meta | Regulated-domain output carries a not-legal-advice notice at the top of every analysis | references/harness_100/ko/66-contract-analyzer/.claude/agents/clause-analyst.md:23 | adapt | Notice is in the agent rules and the output template (:31). Fits our client-facing rule. |
| HH25 | meta | Domain skill rule tiers: P0 failures stop the pipeline, P1 warn and continue | references/harness_100/ko/27-data-pipeline/.claude/skills/data-quality-framework/skill.md:23 | pattern | P1 at :49; six quality dimensions with thresholds at :10. |
| HH26 | meta | Extension skill ends with a fill-in report template for the agent that uses it | references/harness_100/ko/38-chatbot-builder/.claude/skills/conversation-flow-validator/skill.md:131 | reference | Target agents named at :10. Template, not procedure. |

## Do not port

| source | reason |
|---|---|
| references/harness_100/en/** | partly machine-garbled; `ko/` is authoritative and was used |
| references/harness_100/ko/*/.claude/skills/*/skill.md (domain bodies) | per-domain content; only the section layout is mined |
| references/harness_100/ko/66-contract-analyzer/** (clause and statute tables) | Korean law and Korean contract practice, not AU |
| references/harness_100/ko/69-privacy-engineer/**, ko/75-*, ko/78-*, ko/83-*, ko/90-* | Korea-specific legal content (see docs/harness-100-recommendations.md) |
| references/harness_100/ko/01-youtube-production/.claude/agents/thumbnail-designer.md (image-generation section) | provider-specific image tooling, out of scope |
| the file name `skill.md` | Claude Code expects `SKILL.md`; copying the name would break loading on a case-sensitive filesystem (unverified, per the recommendations doc) |
| references/harness_100/ko/27-data-pipeline/.claude/skills/dag-orchestration-patterns/skill.md (Airflow code) | domain code, not a harness pattern |

## Gaps

- No per-agent `model:` or `tools:` scoping in any of 489 agents (searched `model:` and `^tools:` across `ko/*/.claude/agents`). Our light/full model tiering has no counterpart here.
- QA is a judgment checklist. No command-run checks, no probe-before-PASS rule, no mutation testing, no candidate or verdict binding (searched for `mutant`, `probe`, `candidate`-like wording only through the headings counted above; not an exhaustive text search).
- No fresh-context judge panel, no Authority List, no permission or denylist, no hooks, no memory or compaction ledger, no retrospective or evolve loop, no state ledger or resume rule beyond reusing `_workspace/` files.
- No surface adaptation (Claude chat or Cowork); every harness assumes Claude Code agent-team tools (`SendMessage`, `TaskCreate`).
- Rework cap of 2 has no stated outcome after the cap (HH8); our quality-gates already define one, so treat harness_100 as weaker.
- The orchestrator says agents use `SendMessage`, but 429 of 489 agent files never mention it; the claim is carried by the orchestrator text only.
- Sampling limit: about 12 of 100 harnesses read; the 4-skill harnesses (02, 03, 05-11, 28, 31, 51-53, 81) were counted, not read for what the fourth skill adds.
- Candidate downstream use already noted elsewhere: three Adopt skills in `docs/harness-100-recommendations.md` (data-quality-framework, dag-orchestration-patterns, license-compatibility-matrix, plus the 38 chatbot pair). That doc was read from `en/`; the `ko/` heads of those skills were opened here and look intact, but their bodies were not compared to `en/`.
