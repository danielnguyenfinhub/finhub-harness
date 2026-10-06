# Capability backlog — 2026-10-05, from 8 port maps (re-rank after meta_harness)

Scope: both. Maps read: autogpt (A1-A39), crewai (C1-C52), deepseek_harness (D1-D57), dify (Y1-Y37), openhands (O1-O36), openharness (OH1-OH84), revfactory_harness (R1-R18), **meta_harness (M1-M27, new)**. All eight are `Status: COMPLETE`; none missing. Prior backlog kept at `_workspace/01b_capability-scout_backlog_prev_20261005.md`.

Licence tiers (from `references/LICENSES.md` and `.claude/skills/reference-mining/references/licence-rules.md`, both opened [verified]):
- MIT `adapt`: crewai, deepseek_harness, openhands, autogpt `classic/` only; openharness (upstream org unverified, accepted as MIT by Daniel on 2026-10-03, `request.md:16`).
- Apache-2.0 `adapt` with notices: revfactory_harness; **meta_harness** (`LICENSES.md:15`, `licence-rules.md:16`; `references/meta_harness/LICENSE` header "Apache License Version 2.0" [verified]). Attribution line required, no verbatim runs of 8+ words.
- Pattern only: dify. No dify identifiers in any proof below.
- Polyform Shield sources excluded.

Verification for this re-rank: every meta_harness line cited below was opened in `references/meta_harness/` and its heading or definition matched the map (27 lines across `audit_harness.py`, `validate_skills.py`, `handoffs.md`, `runtime-capabilities.md` x2, `role-contract.md`, `portable-contract.md`, `SKILL.md`, `agent-design-patterns.md`, `orchestrator-template.md`, `skill-testing-guide.md`, `autonomous-experimentation.md`) [verified]. Every source line for open items C10-C14 was re-opened as well (A35 `:510`/`:284`, OH36 `query.py:524`, OH41-OH45, OH53-OH55, OH59 `tool_outputs.py:10-12`, OH77, D24, D32, D33, D44, D46, D47, C50, R18) and matched [verified]. Repo-side lines were opened in the current tree.

## Changes

| id | change | why |
|---|---|---|
| C1-C4, C6-C9 | moved out of the ranking to `## Built` | merged (C1-C4 in #16-#22, C6 #24, C7 #25, C8 #26, C9 #27/#28; `request.md` Picks 6-10, `git log` top 8 [verified]) |
| C5 | marked **stopped**, not ranked | Daniel stopped it after judge round 4 (`request.md` "C5 decision"); design and verdicts kept in `_workspace/02_*C5*`; restart is Daniel's call |
| C11 | source rows extended with M5, M6, M7 as **input fields** (producer, consumer, path, completion state; "persist only when it earns it"); score unchanged 0.74 | meta_harness gives vocabulary only, no ledger layout or resume rule (map "Overlap with C10-C14") |
| C13 | promoted from Deferred to Backlog with full criterion scores; total unchanged 0.68 | table space freed by built items; prior file showed only its total |
| C14 | re-scored 0.64 → **0.56** (novelty 0.2, value 0.2) and moved to Deferred | `README.md` §Install / §Use (lines 27-41) now gives per-surface install steps with a "Verified?" column [verified]; only the failure-FAQ shape of R18 is left |
| C10, C12 | carried unchanged | no meta_harness source (map searched `judge`, `consensus`, `spread`, `pre_tool`, `PreToolUse`, `hook`) |
| C15-C24 | new, from meta_harness | see Backlog / Deferred |

## Built (not ranked)

| id | capability | status |
|---|---|---|
| C1 | connector preflight | merged #16/#17 |
| C2 | `lint_harness.py` | merged #18 (`skills/finhub-harness/scripts/lint_harness.py`, 163 lines [verified]) |
| C3 | secret-shape redaction | merged #19 (+ JWT follow-up #20; `src/master_finhub/tools/secret_scan.py` [verified]) |
| C4 | eval regression buckets | merged (#16-#22 range) |
| C5 | Claude Code hook kit | **stopped** by Daniel 2026-10-04 after judge r4 (UPHELD 46 / REJECTED 2, quadratic `${` in `expand_vars`); nothing built; prior score 0.86 |
| C6 | delegation contract | merged #24 (`orchestrator-template.md:306` [verified]) |
| C7 | evolve retrospectives | merged #25 |
| C8 | repeat-call reminder | merged #26 (`src/master_finhub/runtime/repeat_reminder.py` [verified]) |
| C9 | verification gates as data | merged #27/#28 (`src/master_finhub/evals/gates.py` [verified]) |

## Already have

| capability | where it lives | source rows that match |
|---|---|---|
| Throwaway Docker container with no network, a read-only root and a PID cap; a Docker availability probe | `src/master_finhub/sandbox/docker_engine.py:96-98` (`--network none`, `--read-only`, `--pids-limit`), `:54` `docker_available` [verified] | D7, OH34, A1, A3, A4, A5. OH35 is only partly covered: there is a probe but no named refuse-if-unavailable error [verified]. |
| Child env scrubbed by secret-looking *names* | `sandbox/stream.py:22` `SENSITIVE_ENV`, `:30` `scrubbed_env` [verified] | D1, C10, C11 |
| Output tail buffer, thread+queue+sentinel stream, process-group kill | `sandbox/stream.py` docstring [verified] | D2, D3, D5, D6, C17, C19, A6, A8, OH83 (idea) |
| Stdio MCP client: id routing, deadlines, fail-all-waiters on EOF, public names, `isError` mapping | `tools/mcp/client.py` docstring [verified] | D9-D19, C1-C8, C14, Y8-Y14 |
| MCP error and stderr text redacted by known config *values* | `tools/mcp/client.py:107` `redact`, used at :141, :177, :302, :358 [verified] | O11 |
| SSE with PING and idle handling | `server/sse.py`, `server/app.py` (slice 10) [assumed from CLAUDE.md and the module list] | Y1-Y7, D20, D21, C18 |
| Benchmark runner (isolated workspace, never raises, stable id, cutoff) and deterministic string verifier with the grading schema | `evals/runner.py` docstring, `evals/verifiers.py:20-31` [verified] | A9-A18, A15, C20-C23, C25, R1-R5, R9 |
| Compaction: head/marker/tail clip, tool-pair-balanced cut, tail-anchored range, threshold/retain ratios, `<compacted-summary>` frame, model-free summariser | `runtime/context.py:63, :83, :98, :121, :169`, tags at `:43-44` [verified] | D25, D27, D28, D30, D31, OH38, A28. OH37 and OH56 are mostly present (see Rejected). |
| Sensitive-path denylist checked before any allow | `tools/sensitive_paths.py`, wired in `tools/safety.py` [verified] | OH31, A29, A30 |
| Command tripwire, deny before allow, fails closed | `tools/safety.py:1-13`, `make_guard` `:650` [verified] | A7, OH32 (eval order; plan mode not present) |
| Single pre-tool guard seam (one callable that returns a denial string) | `runtime/loop.py:112` `ToolGuard`, `:192` [verified] | Weaker form of OH41-OH45, D44, C50. See C12. |
| Checkpoint and resume, with a fail-closed checkpoint hook | `runtime/loop.py:97-98` `CheckpointHook`, `orchestration/_fsio.py` [verified] | A21, D35 (partial), Y25 |
| Delegation depth cap that a nested config can only lower | `orchestration/modes/subagent.py:94-95` [verified] | D55, Y19, Y20 |
| Workspace fence: lexical reject, then resolve, then containment | `sandbox/workspace.py:1-10` [verified] | O26, O27, A34, OH33. OH66's symlink check on the deepest existing parent is not compared here [assumed covered by the resolve step]. |
| QA verifier stance: command and output per check, probe before PASS, rationalisation list, before-FAIL guard, standing reminder | `skills/finhub-harness/references/qa-agent-guide.md` §7, `.claude/agents/boundary-qa.md` [verified headings] | OH23-OH27 |
| Judge-panel recipe: N drafts, parallel judges, schema-validated scores, mean ranking | `skills/finhub-harness/references/workflow-recipes.md:84-138` [verified] | A35 (partial; see C10) |
| A/B runs, trigger evals with near-misses, train/test split, `grading.json`/`timing.json` schema | `skill-testing-guide.md` §3, §4, §8, §9; `skill-writing-guide.md` §7 [verified headings] | R6-R11 |
| Retry once, then record the gap; no retry on auth or limit failures | `orchestrator-template.md:82, :246-247`, `quality-gates.md` §3-6 [verified] | R14, OH29 (partial) |
| `_workspace/` intermediates kept and archived per run | orchestrator and `workspace-layout.md` [verified grep] | R15, OH5 |
| Plugin manifest check (valid JSON, kebab-case name), skill frontmatter has name and description, v1 artefact gate | `scripts/package-plugin.sh:11-43` [verified] | OH17, OH47 (partial). Covers **this repo's own** skills only; see C2. |
| v2.1.0 harness port (team patterns, orchestrator templates, agent reuse, duplicate review) | `skills/finhub-harness/**` [verified] | R12, R13, revfactory "Do not port" rows |
| Hierarchy kept shallow (two levels at most) | `skills/finhub-harness/SKILL.md:78` "two levels at most"; `references/team-patterns.md:116` "Two levels or fewer is recommended" [verified] | **M15** (miner's "no match" grep was wrong). The "coordinator only with a justification" clause rides inside C15. |
| Four-value capability legend incl. "unverified" | `skills/finhub-harness/references/surfaces.md:130` [verified] | M10 |
| Near-miss trigger queries (should / should-not) | `skills/finhub-harness-evolve/SKILL.md:103`; `skill-testing-guide.md` §8 (`:221`) [verified] | M19 |
| Frontmatter name = directory name; description ≤1024 chars | `lint_harness.py:76-83` [verified] | M23 |
| v1 artefact detection | `SKILL.md:41` (prose), `lint_harness.py:14`, `:143` (error) [verified] | M2 (the "migrate" class only) |
| Short project-instructions pointer, no agent lists or trees | `SKILL.md:120` [verified] | M27 |
| Worker report states with evidence for `complete` | `orchestrator-template.md:306` (C6, merged) [verified] | M11 (completion states). M11's ownership labels go to C18. |
| Per-agent model choice with a reason comment | `team-patterns.md:191`, lint `lint_harness.py:130-133` [verified] | M13 partly (see C23) |

## Backlog

Weights: value 0.35, licence 0.20, effort (inverse) 0.20, risk (inverse) 0.15, novelty 0.10. Each cell: score, reason, evidence tag. Ties: lower effort, then cleaner licence, then single-command proof; a tie the rubric cannot break is stated.

| rank | id | capability | source rows | target | licence | value | licence | effort | risk | novelty | total | proof |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **C17** | Lint: local Markdown links, `references/` paths exist; duplicate agent or skill names | **M21** (`scripts/validate_skills.py:72` `_check_links`, `:85` `_check_references`), M3 (`scripts/audit_harness.py:117` `_duplicate_names`) | plugin skill (`skills/finhub-harness/scripts/lint_harness.py` + fixtures) | Apache-2.0 adapt, attribution line | 1.0: a generated skill that points at a missing reference file fails silently when the model reads it; the third party gets files whose pointers resolve [assumed; no broken link exists in this repo today, probe below] | 0.6: Apache-2.0 [verified LICENSES.md:15] | 1.0: S, two regex rules + one dict count, ≈40 lines in an existing 163-line script, no dependency [verified lint_harness.py] | 0.6: false positives on template paths (`references/{x}.md`), repo-root-relative paths and URLs; mitigation: skip `{`, `://`, `#`-only, resolve from the file's dir then the lint root, WARN not ERROR for root-relative [assumed] | 0.6: lint has no link or path check and `names` (`:118`, `:129`) never flags a duplicate [verified] | **0.82** | `python3 skills/finhub-harness/scripts/lint_harness.py tests/fixtures/harness_bad/` exits 1 and names each seeded defect: `[x](references/missing.md)`, a backticked `references/ghost.md`, two agent files with `name: writer`. The same command on `.claude` and `bash scripts/package-plugin.sh` exit 0 (so `boundary-qa` as both agent and skill is not a duplicate, and `{`-templated paths pass). One mutant per rule (drop the rule, invert the exists test, compare across kinds) must be killed. |
| 2 | **C10** | Judge-panel recipe reports judge spread; flags low consensus instead of a silent pick | **A35** (`multi_agent_debate.py:510`, `:284`), OH44 (`hooks/executor.py:169`, `:232`) | plugin skill (`workflow-recipes.md` §3) | MIT adapt | 0.6: a third party sees when judges disagreed; recipe, not a guard [assumed] | 1.0: MIT [verified] | 1.0: S [assumed] | 1.0: prose and a script [verified] | 0.2: recipe already ranks by schema-validated mean; no `consensus`/`spread` text in `workflow-recipes.md` [verified grep] | **0.78** | Unchanged: stubbed judges score draft 0 as 9, 2, 9 → result carries `lowConsensus: true` and the spread; a schema-invalid reply is excluded, never defaulted (A35's 0.5 default must not be copied). |
| 3 | **C15** | Delegation decision gate before choosing a team; default single-agent; worker delegation notes | **M14** (`.agents/skills/harness/references/agent-design-patterns.md:221`; `.agents/skills/harness/SKILL.md:166`), M17 (`references/orchestrator-template.md:78`), M8 missing-synthesis / partial-worker rows (`docs/architecture/handoffs.md:32`; `SKILL.md:345`), M15 clause (`docs/architecture/role-contract.md:49`) | plugin skill (`SKILL.md` §2-2, `team-patterns.md` §6, `orchestrator-template.md` Template C) | Apache-2.0 adapt | 0.6: fewer over-delegated harnesses and a named synthesis owner; prose guidance, consistent with C6's 0.6 [assumed] | 0.6: Apache-2.0 [verified] | 1.0: S, ≈20 lines over three files [assumed] | 1.0: prose [verified] | 0.6: `team-patterns.md:236-243` has split/merge criteria; no "stay single-agent if unclear" gate, no synthesis-owner question [verified grep `single-agent`, `decision gate`: no hits in `skills/`] | **0.74** | Cold-build two fixtures from the skill text alone. (a) Near-miss "fix the headings in one Markdown file": the harness records the six gate answers and builds a single agent (at most one agent file). (b) "Review six independent documents, then synthesise": fan-out with a named synthesis owner and a partial-worker row in the error table. FAIL: (a) yields 2+ agents, or either orchestrator lacks the gate answers. Clears the queued follow-up "Template C single-agent guidance" (`_workspace/00_input/request.md:22`, repeated `:27`) [verified]. |
| 4 | **C18** | Write-safety ladder and honest ownership labels for parallel writers | **M9** (`docs/architecture/runtime-capabilities.md:41`, `:61`; `.agents/skills/harness/references/runtime-capabilities.md:85`), **M12** (`.agents/skills/harness/SKILL.md:133`), M11 ownership field (`docs/architecture/role-contract.md:12`) | plugin skill (`surfaces.md` degradation rule `:75`, `team-patterns.md` fan-out §1-2, `quality-gates.md` check) | Apache-2.0 adapt | 0.6: generated Mode C teams stop running overlapping writers concurrently; prose, not enforcement [assumed] | 0.6: Apache-2.0 [verified] | 1.0: S, one ladder + one label list [assumed] | 1.0: prose [verified] | 0.6: `surfaces.md:75-83` degrades parallelism by surface but has no write-ownership ladder; no "advisory/enforced" vocabulary in `skills/` [verified grep `ownership`, `advisory`: no hits] | **0.74** | Cold-build a fixture where two workers must edit the same file. PASS: the orchestrator either serialises them or gives disjoint paths, and each writer carries one label from {enforced, workspace-enforced, advisory, serialised}; none says "exclusive" with advisory enforcement. FAIL: two Agent calls in one message with overlapping write paths. A `grep -c` for the label list in the built orchestrator is the cheap first check. Tie with C15 not broken by the rubric (same effort, licence, proof shape); C15 listed first by judgement because it clears a queued follow-up. |
| 5 | **C11** | Cross-reset state ledger (`_workspace/00_state.md` rebuilt at each phase) | **OH77** (`autopilot/service.py:340`, `:381`, `:405`), OH53 (`compact/__init__.py:566`), OH54 (`:635`), OH55 (`:964`), D24 (`summarizer.ts:31`), D33 (`fold.ts:271`), OH40; **input fields** from M5 (`scripts/audit_harness.py:61`), M6 (`docs/architecture/handoffs.md:13`, `:20`), M7 (`.agents/skills/harness/SKILL.md:158`) | plugin skill (`orchestrator-template.md` A/B/C + `surfaces.md` fallback) | MIT adapt (M5-M7 Apache, fields only) | 0.6 [assumed] | 1.0: primary MIT [verified] | 0.6: M, three templates + chat fallback [assumed] | 1.0: prose [verified] | 0.6: no `00_state` in `skills/` [verified grep] | **0.74** | Unchanged, plus: the ledger row names producer, consumer, path and completion state (M7). Cold-build Mode C fixture, stop after phase 2, fresh session "continue": phase-1 mtimes unchanged, orchestrator cites `00_state.md` next step, phase 3 starts. |
| 6 | **C20** | Experiment-loop recipe: mutable vs immutable eval surface, baseline first, keep/discard ledger | **M20** (`.agents/skills/harness/references/autonomous-experimentation.md:21`, `:51`, `:59`, `:68`) | plugin skill (`workflow-recipes.md` new recipe) | Apache-2.0 adapt | 0.6: generated tuning harnesses cannot quietly edit their own grader; shows to third parties only for that harness type [assumed] | 0.6 [verified] | 1.0: S, one recipe [assumed] | 0.6: an autonomous loop can run long; mitigation is bounded retries and a `timeout` status [assumed] | 0.6: mutation spot-checks (`quality-gates.md:191-199`) have the same shape; no general recipe; no `results.tsv`/`experiment` in `skills/` [verified grep] | **0.68** | Cold-build "tune a prompt against a fixed eval set". PASS: the recipe names mutable and immutable files, writes a baseline row first, and every iteration has one status in {keep, discard, crash, timeout}; in a seeded run where the worker edits the eval file, the eval file's sha256 is unchanged at the end or the iteration is marked discard. FAIL: no baseline row, or the eval file changed and was kept. |
| 7 | **C12** | Ordered pre/post tool hook chain in the runtime | **OH42** (`hooks/executor.py:64`, `types.py:21`), OH41 (`schemas.py:10`), OH45 (`engine/query.py:895`, `:1009`), D44 (`merge.ts:62`), D46 (`runner.ts:67`), D47 (`events.ts:92`), C50 (`hooks/tool_hooks.py:142`), Y31 (pattern only) | runtime module | MIT adapt | 0.6 [assumed] | 1.0 [verified] | 0.6: M [verified `loop.py:147`, `:158` single `ToolGuard`] | 0.6 [assumed] | 0.6 [verified] | **0.68** | Unchanged (`pytest tests/test_hooks.py`: deny from hook 2 of 3 blocks with its reason; post-hook may replace result; `block_on_failure` both ways; `tests/test_safety.py` still green). |
| 8 | **C13** | Tool-output offload to a workspace file with head/tail preview | **OH36** (`engine/query.py:524`), OH59 (`services/tool_outputs.py:10-12`), D32 (`spill-policy/src/index.ts:111`) | runtime module (`runtime/context.py` or `loop.py:_execute`) | MIT adapt | 0.6: a long tool result is retrievable instead of clipped; invisible to third parties [assumed] | 1.0: MIT [verified] | 0.6: M, file write, retrieval hint, fence check, tests [assumed] | 0.6: new file writes; bounded by the workspace fence; a spill failure must never turn success into error (D32) [assumed] | 0.6: `context.py` clips, does not save; no `offload` in `src/` [verified grep] | **0.68** | `pytest tests/test_offload.py`: a 50 KB tool result yields an inline head/tail preview with byte size and a path inside the workspace; the file holds the full text; a failing write leaves the result a success with the plain clip; a `read` of the offload file is never re-offloaded. A mutant that drops the fence check must be killed. |
| 9 | **C16** | Read-only Step 0 audit script: inventory, duplicate names, operation class | **M1** (`scripts/audit_harness.py:177` `audit_target`), M2 (`:153` `_classify`, rule chain only), M3 (`:117`), M4 (`:297` `main`, "mutation: none") | plugin skill (`skills/finhub-harness/scripts/audit_harness.py` + `SKILL.md` Step 0) | Apache-2.0 adapt | 0.6: makes "audit / migrate / extend" deterministic for Daniel; third parties see it only through better routing [assumed] | 0.6 [verified] | 0.6: M, source is 313 lines [verified `wc -l`]; ours ≈150 + fixtures + Step 0 edit [assumed] | 1.0: read-only, advisory output [assumed; must be proven by the tree hash] | 0.6: lint covers v1 and frontmatter (`lint_harness.py:14`, `:72`); `check-harness-refs.sh` is master-finhub-only greps (`:13-53`); neither inventories or classifies [verified] | **0.66** | `python3 skills/finhub-harness/scripts/audit_harness.py <fixture>` on four fixtures prints the expected class (empty → build; a `TeamCreate(` orchestrator → migrate; an existing harness → extend/audit; two agents named `writer` → listed as duplicates) and `mutation: none`; `find <fixture> -type f -exec sha256sum {} +` is identical before and after. FAIL: wrong class or any byte changed. Keeps our Step 0 classes (`SKILL.md:35` table), not meta_harness's. Would make the queued "thin Step 0" (`request.md:22`) a one-command step. |
| 10 | **C19** | Topology A/B protocol in the evolve skill: paired scenarios, hard gates before scores | **M18** (`.agents/skills/harness/references/skill-testing-guide.md:184`) | plugin skill (`skill-testing-guide.md` §4 + `finhub-harness-evolve`) | Apache-2.0 adapt | 0.6: Daniel's evolve loop stops adopting a worse team shape on a score alone [assumed] | 0.6 [verified] | 0.6: M, a section plus a fixture with four scenarios and two topologies [assumed] | 1.0: prose [verified] | 0.6: A/B runs exist (`skill-testing-guide.md` §3-4, `:63`, `:85`); nothing topology-specific [verified headings] | **0.66** | Evolve run on a fixture proposing three parallel writers on one file: the A/B record shows the write-overlap hard gate failing before any score comparison and keeps the baseline; the near-miss scenario stays direct. FAIL: scores compared with a failed hard gate, or the worse topology adopted. |
| 11 | **C21** | "Removable model-specific logic" template section with a deletion trigger per workaround | **M16** (`.agents/skills/harness/references/orchestrator-template.md:67`; `agent-design-patterns.md:25`) | plugin skill (`orchestrator-template.md` + evolve) | Apache-2.0 adapt | 0.2: polish for the evolve loop [assumed] | 0.6 [verified] | 1.0: S [assumed] | 1.0: prose [verified] | 1.0: no `removab`/`deletion trigger` in `skills/` [verified grep] | **0.64** | Cold-built orchestrator: every retry or workaround block sits under the section with a `Delete when:` line (`grep -c`); an evolve fixture whose trigger is met removes the block and leaves a `.bak`. FAIL: a workaround with no trigger, or removal without backup. |
| 12 | **C22** | Source-of-truth order: packaged copies are generated, never edited; canonical files survive deleting them | **M25** (`docs/architecture/portable-contract.md:13`, `:34`) | docs (`SKILL.md` Step 7 or `surfaces.md` §3 packaging) | Apache-2.0 adapt | 0.2: guards against editing `dist/` copies; `dist/` is git-ignored (`README.md` §Install) [verified] | 0.6 [verified] | 1.0: S, one paragraph [assumed] | 1.0: prose [verified] | 1.0: no `rippab` in `skills/` [verified grep] | **0.64** | `rm -rf dist && bash scripts/package-plugin.sh && python3 skills/finhub-harness/scripts/lint_harness.py .` both exit 0, and a grep finds the "never edit packaged copies" sentence in the packaging section. Weak: proves the rule is stated and the canonical tree stands alone, not that people follow it. |

## Top 3 in detail

### C17 — Lint: links, reference paths, duplicate names

- **What it is.** Two rules borrowed from meta_harness's skill validator (`references/meta_harness/scripts/validate_skills.py:72` link check, `:85` bundled-reference check) and one from its audit (`scripts/audit_harness.py:117` duplicates), rewritten for our lint.
  - Every relative Markdown link and every backticked `references/…`/`scripts/…` path in an agent or SKILL file resolves.
  - No two agent files share a frontmatter `name`; no two skills share one. Agent vs skill with the same name is allowed (this repo has `boundary-qa` as both [verified `ls`]).
- **Why it ranks here.** Highest total, smallest effort, and a single-command proof. It closes the one gap the merged C2 left: `SKILL.md` Step 6 asks that paths be real, and nothing checks it.
- **Adoption shape.** ≈40 lines in `lint_harness.py`, two fixture defects in `tests/fixtures/harness_bad/`, one attribution comment (Apache-2.0, meta_harness). `package-plugin.sh:29` already runs the lint on this repo, so the rule covers the plugin too.
- **Proof test.** See row. One mutant per rule, as the C2 process lesson requires (`request.md:27`).
- **Risks and "does not cover".** Path resolution base is the hard part: skill-relative vs repo-root vs template placeholders. It does not check anchors, URLs or that a referenced file says what the pointer claims. Cross-directory duplicates (`.claude/skills` vs `skills/`) are out of reach while the lint takes one DIR.
- **Effort.** S.

### C10 — Judge spread and low-consensus flag

- **What it is.** The judge-panel recipe keeps its mean ranking but also reports spread and sets a low-consensus flag above a threshold; schema-invalid judge replies are excluded. Source A35 (`references/autogpt/classic/original_autogpt/autogpt/agents/prompt_strategies/multi_agent_debate.py:510`, scoring `:284`), parse rule OH44 (`references/openharness/src/openharness/hooks/executor.py:232`).
- **Why it ranks here.** Clean MIT, prose, and it makes a panel verdict honest about disagreement. It ranks below C17 because a weaker form (mean ranking) already exists.
- **Adoption shape.** A few lines in `workflow-recipes.md` §3.
- **Proof test.** Stubbed judges 9 / 2 / 9 → `lowConsensus: true` with the spread; an invalid reply is excluded, not defaulted to 0.5.
- **Risks and "does not cover".** The threshold is a guess until real panels are run. It does not make judges agree or pick a winner; it only reports.
- **Effort.** S.

### C15 — Delegation decision gate

- **What it is.** Before Step 2-2 picks a pattern, the skill asks six questions (independent units, where value comes from, write ownership, tool sufficiency, who synthesises, how partial failure is reported). If any answer is unclear, stay single-agent; a coordinator layer needs a stated reason. Template C gets an optional delegation-notes block (eligible tasks, forbidden overlaps, synthesis owner, conflicting-result rule) and two error rows (missing synthesis, partial worker). Sources: `references/meta_harness/.agents/skills/harness/references/agent-design-patterns.md:221`, `.agents/skills/harness/SKILL.md:166`, `references/orchestrator-template.md:78`, `docs/architecture/handoffs.md:32`.
- **Why it ranks here.** Small, prose-only, and it is the queued follow-up "Template C single-agent guidance" (`_workspace/00_input/request.md:22`). Its value score is held at 0.6 to match C6: it shapes what is generated but enforces nothing.
- **Adoption shape.** ≈20 lines over `SKILL.md` §2-2, `team-patterns.md` §6 and Template C. No code.
- **Proof test.** Two cold builds (near-miss → single agent; real fan-out → named synthesis owner), see row.
- **Risks and "does not cover".** A model may answer the gate questions perfunctorily; the proof checks the outcome, not the quality of the answers. It does not size teams (Step 5 scale rule `SKILL.md:118` stays).
- **Effort.** S.

## Deferred

| id | capability | total |
|---|---|---|
| C23 | Semantic model tier table (inherit / fast / balanced / strong → Claude Code alias; chat ignores) (M13: `.agents/skills/harness/references/runtime-capabilities.md:73`; scores v0.2 l0.6 e1.0 r1.0 n0.6) | 0.60 |
| C14 | Quickstart failure FAQ for the plugin (R18: `references/revfactory_harness/docs/quickstart.md:3`; re-scored v0.2 l0.6 e1.0 r1.0 n0.2, README §Install covers the rest) | 0.56 |
| C24 | Lint warning: runtime-specific call (`SendMessage`, `Agent(`) in a chat/Cowork-targeted harness without `## Single-context fallback` (M22: `scripts/validate_skills.py:92`, pattern; v0.2 l0.6 e1.0 r0.6 n0.6) | 0.54 |

## Rejected

| candidate | reason (licence / no proof / duplicate / low value) |
|---|---|
| Required-term presence check over adapter docs (M24, `scripts/validate_adapters.py:20`) | No proof worth auditing: a substring-presence check, which meta_harness's own QA guide advises against (`.agents/skills/harness/references/qa-agent-guide.md:52` "Prefer Cross-Checks Over Presence Checks") [verified]. |
| Install preflight, snapshot and rollback (M26, `scripts/installer_core.py:908`, `:509`) | No consumer: finhub-harness has no installer; out of the mining scope Daniel set (`request.md` "Reference decision": ignore installer). |
| meta_harness operation classes (M2's own list: drift repair, adapter update, skill-only update) | Duplicate in purpose of our Step 0 table (`SKILL.md:35`); adapter classes have no Claude surface. Only the ordered rule chain is used, inside C16. |
| Adapters for Pi, Codex, Antigravity, Cursor; Codex/Pages validators | Out of scope by Daniel's decision (`request.md` "Reference decision"); not Daniel's surfaces. |
| Compaction ledger, crash detection and circuit breaker (D22, D23, D29, OH57, OH58) | Low value. The summariser is model-free (`context.py:121`), so there is no LLM call to crash, retry or circuit-break. An audit record of the dropped range would be polish (value 0.2). |
| Microcompact and deterministic tiering (OH37, OH56) | Duplicate in substance: `context.py` already clips every oversized tool result and summarises without a model. |
| Human approval flow and permission presets (D39, D40, D41, OH70-OH73, A31) | Low value. The runtime is non-interactive, with no answerer, and building one is speculative. Revisit if the server (slice 10) gains an approve endpoint. |
| File-based memory store: schema, dedup, index cap, relevance, per-agent dirs (OH60-OH64, OH66, OH67, C42-C44) | Low value. FinHub memory is external by design (Zep, Supermemory; OH map Gaps). The staleness and evidence ideas go into C7. |
| Planning todo list, planner and observer (C47, C48, C49) | Low value. Orchestrators already own task order. No harness gap is named. |
| Plugin loader trust and installer guard (OH47-OH50, OH52, OH18) | Low value / no consumer. Neither the runtime nor the plugin loads third-party plugins. OH47's dual manifest location is a lint rule that can join C2. |
| MCP health probe (O13-O16) | Low value, and a risk: "verified" health requires a successful tool call, which may mutate. No runtime consumer of a health status yet. |
| Prompt-injection safety fixtures (A39, `data_draft.json`) | No proof. Under `fake_llm.py` ScriptedLLM, an injection case tests the script, not resistance. It needs a live-model eval design first. |
| Keyless replay from real session JSONL (D56) | Risk. Harvesting real sessions conflicts with the synthetic-data-only rule (`runtime-builder.md:23`) unless a sanitising step is designed. That is its own design round. |
| Reviewer may only APPROVE or COMMENT (O35) | Conflicts with the adopted adversarial-audit design, where the judge can reject. |
| `@spec` ID tags (O36) | Mostly a duplicate. The Authority List already ties claims to cited lines and tests. |
| Status vocabulary and autopilot card lifecycle, scoring, tick and cron (O29-O31, OH74-OH76, OH78, OH80, OH82) | Low value / duplicate. capability-triage already records per-criterion reasons (the OH75 idea). One-at-a-time is already the orchestrator rule. OH77 is merged into C11. |
| Skill catalog digest, skill precedence, discovery and registry (D51, D52, OH15, OH16, OH19) | No consumer. The host (Claude Code, chat, Cowork) owns skill loading. |
| Plan-mode dry-run switch (OH32 mode, OH54, D34) | Low value [assumed]. No caller needs a dry-run mode today. Revisit with C12. |
| Sandbox escalation, policy precedence and prompt rendering (D8, D36, D37, D38) | Duplicate or delta-only against slice 3 policy modes. The miner's own note says "delta only". |
| Git worktree isolation (OH11), bridge runner and ingress secret (OH83, OH84) | No consumer (agents run on threads). OH84 is flagged unsafe by its miner. |
| dify observability, persistence, pause and suspend layers (Y22-Y27), RBAC and recipient scenes (Y29, Y30), variable namespaces (Y32, Y33), strategy base (Y34), last-iteration tool strip (Y35), annotations and feedback export (Y36, Y37), variable size cap (Y21) | Low value / no consumer, and pattern-only. Y21 is also unverified at line level per its miner. Y31 is kept only as a pattern note inside C12. |
| Upstream-change playbook and monitoring SLA (R16, R17) | Low value. No host flag is depended on today. |
| crewai config-by-name, agent trio, delegation scoping, LLM guardrail, hallucination guardrail (C30, C31, C32, C36, C40, C41) | Duplicate (slice 7) or unverified (C41 is a stub as far as opened). C40 is LLM-judged and only fits where code cannot check. |
| Train-and-test via repeated LLM scoring (C26, C27, C46) | Low value. Verifiers are deliberately deterministic (`verifiers.py:1`). |
| Polyform Shield sources excluded. | — |

## Gaps

- **meta_harness has no runtime patterns** (no loop, compaction, hooks, offload, judge panel or quickstart; map Gaps). C10, C12, C13 and C14 get no new source; C11 gets field names only.
- **Corrections to the meta_harness map** [verified in this tree]:
  - M15: the map's grep "finds no match"; `SKILL.md:78` and `team-patterns.md:116` already cap hierarchy at two levels → moved to Already have.
  - M4: cites a "do not silently overwrite" rule at our `SKILL.md:203`; `SKILL.md` has 200 lines and no "overwrite" anywhere. The read-only contract in C16 is net-new, not a mirror.
  - M3: "duplicate skill names across `.claude/skills` and `skills/` are real here"; there are none today (6 vs 2 names, disjoint). The rule is preventive.
  - M14: the "Template C single-agent guidance" follow-up is queued in `_workspace/00_input/request.md:22` (repeated `:27`), not in `CLAUDE.md`.
- **No broken links today.** A probe over the eight `SKILL.md` files found 0 unresolved `references/*.md` or relative Markdown links. C17's value rests on generated harnesses, not this repo.
- **Stale docs (not a capability, a docs fix):** `references/LICENSES.md:15` and `licence-rules.md:16` still say meta_harness "Port map: not yet mined"; `README.md:57` says "Eight reference harnesses" but its licence table (`:59-64`) has no `meta_harness` row.
- **Resolved since the prior backlog:** `src/master_finhub/factory/` no longer exists (deleted with C1, `request.md:16`) [verified `ls`].
- **Carried:** hooks on chat and Cowork unverified (C5 was Code-only); no cross-agent budget enforcement in any map; openharness upstream org unverified (accepted by Daniel); unopened areas listed in the prior backlog (deepseek `guard/timeout-policy`, dify `layers/`, autogpt root `.claude`, openharness `plugins/loader.py:320-620`) stay UNVERIFIED.
- **meta_harness unopened:** `docs/guides/*.md`, `docs/sample-prompts.md`, `tests/`, `plans/upgrade_plan_20260906.md` (map "Could not verify").

## Ranked top 5

| rank | id | name | tier | target | score | effort |
|---|---|---|---|---|---|---|
| 1 | C17 | Lint: links, reference paths, duplicate names | Apache-2.0 adapt | plugin skill (`lint_harness.py`) | 0.82 | S |
| 2 | C10 | Judge spread / low-consensus flag | MIT adapt | plugin skill (`workflow-recipes.md`) | 0.78 | S |
| 3 | C15 | Delegation decision gate, single-agent default | Apache-2.0 adapt | plugin skill (SKILL §2-2, team-patterns, Template C) | 0.74 | S |
| 4 | C18 | Write-safety ladder, honest ownership labels | Apache-2.0 adapt | plugin skill (`surfaces.md`, `team-patterns.md`, `quality-gates.md`) | 0.74 | S |
| 5 | C11 | Cross-reset state ledger (+ M5-M7 fields) | MIT adapt | plugin skill (`orchestrator-template.md`, `surfaces.md`) | 0.74 | M |

## Recommended next pick

**C17.** Highest total, effort S, it extends code that is already merged and audited (C2), and its proof is one command with a mutant per rule, the cheapest shape for the judge and QA.

**Weakest link:** the value score of 1.0 is `[assumed]`. Today this repo has no broken link, so the rule's benefit is preventive and depends on generated harnesses actually shipping bad pointers. The second-weakest point is path resolution: if the design cannot state one resolution base (skill dir, then lint root) that passes this repo and `package-plugin.sh` with zero false errors, the rule must ship as WARN, and value drops to 0.6 (total 0.68, tied with C20 at rank 6-7).

If Daniel prefers prose that clears a queued follow-up, C15 is the alternative. Daniel picks.
