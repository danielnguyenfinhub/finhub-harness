# Port map — revfactory_harness (scope: both)

- Submodule: references/revfactory_harness
- Pinned SHA: cceac68 (`git -C references/revfactory_harness rev-parse --short HEAD`; unchanged from the prior run)
- Licence: Apache-2.0 (references/revfactory_harness/LICENSE; matches licence-rules.md and references/LICENSES.md, no drift)
- Mined: 2026-10-03 AEST
- Status: COMPLETE
- Re-run basis: prior map `_workspace_20261003_095000/01_reference-miner_revfactory_harness_portmap.md`. I re-opened every cited line. Rows R2, R3 and R7 had stale line numbers and are corrected below. All other rows still match on disk.

Key factory-scope result: **almost nothing in this submodule is absent from our port.** The pin is harness v1.2.x plus Unreleased (plugin.json says 1.2.0, and SKILL.md still uses TeamCreate/SendMessage v1 prose). `skills/finhub-harness/` is a port of v2.1.0, so it is newer than the pin. The submodule has no scripts, hooks, eval harness, runnable examples or CI. It contains only 7 Markdown skill files, 2 plugin manifests, docs, and launch artefacts. The only gaps are in repo-hygiene and docs, listed as R16-R18.

Path abbreviations: `RH/` = `references/revfactory_harness/skills/harness/references/`, `RS/` = `references/revfactory_harness/skills/harness/`.

## Findings

Rows R1-R15 are kept from the prior run (slice 8-11 runtime scope), with line fixes. Rows R16-R18 are new factory-scope rows.

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| R1 | 11 | Eval case record: id, descriptive name, prompt, list of objective assertions | references/revfactory_harness/skills/harness/references/skill-writing-guide.md:207 | adapt | dataclass `EvalCase`; ids descriptive, not numeric (see R7) |
| R2 | 11 | Grading result: expectations list with text/passed/evidence plus summary passed/failed/total/pass_rate | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:139 | adapt | Line corrected from 140 (heading is 139). Exact field names fix the verifier return shape |
| R3 | 11 | Same grading schema restated, with a warning against field-name variants | references/revfactory_harness/skills/harness/references/skill-writing-guide.md:223 | adapt | Line corrected from 222; the "no name/met/details variants" warning is at :245 |
| R4 | 11 | Good assertion = objectively true/false, descriptive, tests core value; bad = subjective or always true | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:118 | adapt | Verifiers must be deterministic code, not LLM judgement |
| R5 | 11 | Programmatically checkable assertions should be scripts, reusable across iterations | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:131 | adapt | Supports `verifiers/` as plain Python callables |
| R6 | 11 | Non-discriminating assertions (pass in both configs) carry no signal; remove or harden | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:135 | adapt | Needs a baseline run; include one pass AND one fail benchmark (slice 11 proof) |
| R7 | 11 | Per-iteration directory layout: eval-<name>/{with_skill,without_skill}/{outputs,timing.json,grading.json}, benchmark.json | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:278 | adapt | Line corrected from 280 (section heading is 278). Never overwrite earlier iterations; use a tmp dir in tests |
| R8 | 11 | Run each prompt twice (with vs baseline); baseline is no-skill or snapshot of old version | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:75 | adapt | Runner with and without a feature or profile; YAGNI-trim to single-config first |
| R9 | 11 | Capture total_tokens and duration_ms at completion time because they cannot be recovered later | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:104 | adapt | Runner records tokens and wall time per case; reuses slice 2 token meter |
| R10 | 11 | Trigger-eval queries: should-trigger vs near-miss should-not-trigger, 20 total | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:235 | reference | Already in our skill-testing-guide §8 and finhub-harness SKILL.md step 4 (line 143) |
| R11 | 11 | Train 60% / Test 40% split to avoid overfitting when optimising | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:266 | reference | Already in our skill-testing-guide.md:245; do not build in slice 11 |
| R12 | 3, 8-11 | QA runs incrementally after each module, not once at the end | references/revfactory_harness/skills/harness/references/qa-agent-guide.md:131 | reference | Already the phase-table Part B convention; cite as justification only |
| R13 | 10 | Boundary check: compare response shape against client consumer; watch paginated or 202 shape mismatch | references/revfactory_harness/skills/harness/references/qa-agent-guide.md:44 | reference | Slice 10 test principle: assert SSE frame shape matches the client parser |
| R14 | 8-11 | Error policy: one retry then proceed and name the gap; partial results on timeout | references/revfactory_harness/skills/harness/references/orchestrator-template.md:211 | reference | Process convention only; matches miner Error Handling |
| R15 | meta | Preserve _workspace/ intermediates for audit; move old run to _workspace_<timestamp> on new input | references/revfactory_harness/skills/harness/references/orchestrator-template.md:41 | reference | Already followed by the orchestrator |
| R16 | retrospective | Time-boxed upstream-change playbook: three scenarios (flag removed, managed-agents GA, API break), each with T+24/48/72h actions and artefacts | references/revfactory_harness/docs/experimental-dependency.md:59 | reference | Absent from ours. Template for a host-API compat watch note; not needed until we depend on a flag |
| R17 | retrospective | Observable monitoring SLA table: event, response deadline, measurement; nightly-CI compat check (stated as planned, not present in this repo) | references/revfactory_harness/docs/experimental-dependency.md:113 | reference | No CI exists upstream to copy (:99 says "tracked as roadmap P-13"); idea only |
| R18 | meta | Zero-to-first-harness quickstart: strict time budget, numbered steps, per-step "Failure FAQ" with cause and fix | references/revfactory_harness/docs/quickstart.md:3 | adapt | We have no quickstart. A `docs/quickstart.md` for our plugin would reuse the structure; replace the v1 experimental-flag steps (:28, :93) |

## Do not port

| source | reason |
|---|---|
| references/revfactory_harness/skills/harness/SKILL.md (Phases 0-7) | v1.2 prose. Ours is the v2.1.0 port, which is newer, so nothing is missing. It also uses TeamCreate and SendMessage with the experimental flag, which our finhub-harness SKILL.md step 1 flags as a v1 artefact to migrate away from |
| references/revfactory_harness/skills/harness/references/agent-design-patterns.md | Covered by our team-patterns.md (six patterns, quality verification, composite, agent types, definition structure, §6 split criteria, §7 agent reuse, §8 skills vs agents). The upstream "agent reuse" table at :262 is already ported as §7 |
| references/revfactory_harness/skills/harness/references/{orchestrator-template,qa-agent-guide,skill-testing-guide,skill-writing-guide,team-examples}.md | Each has an English, v2-updated counterpart in skills/finhub-harness/references/ (ours is longer in 4 of 5, shorter only in team-examples: 152 vs 328 lines) |
| .claude-plugin/plugin.json, .claude-plugin/marketplace.json | We already ship our own manifests. The extra upstream keywords (pipeline, fan-out-fan-in, etc.) are marketing only |
| CONTRIBUTING.md (SLA table :9, branch and commit conventions) | Maintainer-process text for a public project, not a harness capability |
| _workspace/**, docs/index.html, privacy.html, README_KO/JA.md, harness_*.png, .github/ISSUE_TEMPLATE | Launch and marketing artefacts |
| Korean-language text | Not a licence block. If any wording is reused, translate it and keep the Apache-2.0 notices (NOTICE already exists at the repo root) |

## Gaps

- Missing from the reference repo: no scripts/, hooks/, evals/, runnable examples or CI workflows. The tree has 7 skill Markdown files, 2 manifests and docs. The Phase 6.3 "bundle repeated helper code into scripts/" item (SKILL.md:~335) is prose only. I searched `git ls-files` and found none. A harness-eval runner or hook pattern must come from openharness, autogpt classic or deepseek, not this submodule.
- Diff against skills/finhub-harness/references/*.md and finhub-harness-evolve/SKILL.md found these upstream items **already ported**, so they are not listed above.
  - Phase 0 audit and the extend-existing matrix: finhub-harness SKILL.md:27-35.
  - Duplicate review before creating an agent or skill (3-0 and 4-0, the Unreleased CHANGELOG items): SKILL.md:84 and :99, and team-patterns §7.
  - Hybrid mode and the CLAUDE.md pointer: SKILL.md:117.
  - Follow-up keywords in descriptions: SKILL.md:101.
  - Trigger verification, dry run and test scenarios: SKILL.md:143-144 and orchestrator-template.
  - A/B and blind grading, `benchmark.json` layout and the train/test description optimiser: skill-testing-guide §4, §8 and §9.
  - Team size guidance (upstream :248): present in ours and not re-verified line by line.
  - Phase 7 evolution loop and change history: finhub-harness-evolve.
- Where ours is **ahead**: v1 artefact migration, surface adaptation (Code / chat / Cowork), quality-gates.md, source-enrichment.md, model-selection-guide.md, workflow-recipes.md, execution-modes.md, surfaces.md.
- Not verified: the upstream Phase 6.3 text (a re-read of that phase section) was only skimmed, not compared word for word, against our skill-testing-guide §3-§4.
- The upstream `model: "opus"` for all agents rule (SKILL.md Phase 3) conflicts with our model-selection-guide. Ours wins and nothing is ported.
- The runtime slice 8-11 gaps from the prior run still stand. This repo has no Docker, MCP, SSE or eval-runner code. Use openhands/docker, dify mcp_client and streaming_utils (pattern only), and autogpt classic direct_benchmark (MIT only). The slice 11 shape suggested earlier (stdlib `EvalCase` and `Grading` dataclasses, verifiers returning `(passed, evidence)`, a runner emitting `pass_rate`) is still valid, based on R1-R6.
- Backlog advice for the scout: R16-R18 are low value. Only R18 (quickstart) is a concrete, cheap addition, and it needs rewriting for our no-flag v2 install. Rank revfactory below the openharness, deepseek and crewai rows.
