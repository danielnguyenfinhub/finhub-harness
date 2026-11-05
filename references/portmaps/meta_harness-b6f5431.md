# Port map — meta_harness

- Submodule: references/meta_harness
- Pinned SHA: b6f5431 (confirmed with `git rev-parse --short HEAD`, v0.8.4 plus unreleased installer scripts)
- Licence: Apache-2.0 (`references/meta_harness/LICENSE`, licence-rules.md row `meta_harness`). The LICENSE file is the unmodified Apache text with no copyright-holder line, and there is no NOTICE file. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the two purposes in scope (harness-factory and runtime). Not exhaustive: the TUI, the Pi, Cursor and Antigravity adapters, the docs site layout, `install.sh`/`install.ps1` and `scripts/validate_pages.py` were not opened (see Gaps).
- Id prefix: `MH`.
- What this repo is: a port of revfactory/harness to a runtime-neutral `.agents/skills/` layout plus a Python installer. It is NOT a harness search or optimisation system: no proposer/evaluator split, no run logging code (see Gaps). Its value is the autonomous-experiment profile, a topology A/B method with hard gates, a capability-status vocabulary, and an idempotent, rollback-safe installer.
- Language: Python (stdlib only) and Markdown. "adapt" means a rewrite in `skills/finhub-harness/` prose or scripts with the Apache-2.0 attribution comment.

## Already covered or adopted (do not re-propose)

Checked by grep against `skills/finhub-harness/`, `.claude/` and `CLAUDE.md`; only the names below were opened.

| area | covered by | note |
|---|---|---|
| revfactory base: six phases, six patterns, QA boundary guide, with-skill vs baseline runs, blind comparator, trigger near-miss sets | `skills/finhub-harness/references/skill-testing-guide.md:61-161`, `qa-agent-guide.md`, `team-patterns.md` | meta_harness `qa-agent-guide.md` and `skill-testing-guide.md` sections 1-9 are the same material; mine nothing there |
| delegation decision gate with six answers | `skills/finhub-harness/SKILL.md:64-74` | same six questions as meta_harness `agent-design-patterns.md:221-232` |
| writer ownership ladder: enforced, workspace-enforced, advisory, serialised; "advisory is never exclusive" | `skills/finhub-harness/references/write-safety.md:13-18,58` | equivalent to meta_harness ownership lowering (MH10); only the 4-status vocabulary is new |
| handoff classes (ephemeral / durable record / artifact) | `skills/finhub-harness/references/state-ledger.md:13` | already adopted from OpenRig |
| lint: dir name equals `name`, broken links, missing `references/` files, 1024-char description | `skills/finhub-harness/scripts/lint_harness.py:112-119,160,183` | covers meta_harness `validate_skills.py:140-148,72-89`; do not re-propose |
| short pointer file, kept small, details by pointer | `CLAUDE.md` pointer block, C33 row | covers meta_harness `agents-md-guide.md`; the pointer rule is built |
| per-row tracker, waiver ledger, candidate binding, mutant gate | `unit_tracker.py`, `waiver_ledger.py`, `candidate_id.py`, `mutant_gate.py` | meta_harness has none of these; its ledger is a plain TSV (MH1) |
| runtime slices 1-11 (loop, context, safety, DAG, modes, MCP, SSE, evals) | `src/master_finhub/` | meta_harness has no runtime code; nothing there overlaps |

## Findings

### (a) Harness factory

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| MH1 | meta | Experiment loop contract: name mutable surface, read-only evaluation surface, baseline, comparison rule, ledger, keep/discard rule, failure rule before the first candidate | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:23-33 | adapt | Net-new: finhub-harness has no experiment profile. Seven items become a checklist. |
| MH2 | meta | Evaluation surface stays read-only for a run; changing it forces a new run with a new baseline | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:33 | adapt | Pairs with mutant_gate idea: a moved yardstick voids earlier scores. |
| MH3 | meta | Ledger row per candidate: id, metric, runtime, status keep/discard/crash/timeout, summary; baseline is row one | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:51-66 | adapt | Could be one `unit_tracker.py` table instead of a TSV. |
| MH4 | meta | Loop of seven steps: snapshot request, baseline, one bounded candidate, run under budget, log at once, decide, summarise | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:68-76 | adapt | "Log immediately after the run" is the resumability rule. |
| MH5 | meta | Failure policy: retry only mechanical failures, one or two attempts, timeouts and crashes stay in the ledger | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:78-83 | adapt | Compare `state-ledger.md` once-phase rules; this is for non-effectful runs. |
| MH6 | meta | When-not-to-use list: moving evaluation surface, unbounded mutable surface, no metric, production side effects, unauditable host | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:13-19 | adapt | Doubles as the refusal rule a generator needs before offering the profile. |
| MH7 | meta | Experiment loop is a profile layered on Pipeline, Supervisor or Producer-Reviewer, not a seventh pattern | references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:85-91 | adapt | Keeps `team-patterns.md` at six patterns; add a pairing note only. |
| MH8 | meta | Topology-change A/B: same fixture, model, permissions, budget and rubric; four paired scenarios; rerun only ties or anomalies | references/meta_harness/.agents/skills/harness/references/skill-testing-guide.md:184-202 | adapt | Net-new: our guide compares skill vs none, not old vs new topology. |
| MH9 | meta | Hard gates checked before any score: canonical skill untouched, no overlapping writes, owner named, gaps disclosed, no invented evidence | references/meta_harness/.agents/skills/harness/references/skill-testing-guide.md:206-212 | adapt | Gate-then-score order matters; a high score cannot buy back a failed gate. |
| MH10 | meta | High confidence only if every gate passes, correctness holds, the target improves in more than one case, near-miss does not regress | references/meta_harness/.agents/skills/harness/references/skill-testing-guide.md:214 | adapt | Otherwise "document and defer". A concrete adopt/defer rule for evolve. |
| MH11 | meta | Worked review record: scope file, per-scenario score TSV with gate columns and verdict, report with Implemented and Deferred/Rejected lists | references/meta_harness/_workspace/reviews/harness-modernization/04_results.tsv:1-5 | pattern | Real example of MH8-MH10 output; scores are simulation, not measured. |
| MH12 | meta | Review report states its limit: paired decision simulations, no statistical significance claimed; defers a repeated benchmark | references/meta_harness/_workspace/reviews/harness-modernization/final-report.md:39 | pattern | Honest-limit sentence for our own evolve reports; also see :20 for the win rule. |
| MH13 | meta | Rippability rule: native profiles are removable and regenerable, and deleting them leaves the portable skill, roles and workspace usable | references/meta_harness/.agents/skills/harness/SKILL.md:361-369 | adapt | Net-new as a stated rule: prescribes a precedence order and "promote edits back". |
| MH14 | meta | Removable section in the orchestrator template for model-specific retries, with a stated deletion trigger | references/meta_harness/.agents/skills/harness/references/orchestrator-template.md:67-70 | adapt | One template section; lint could warn when a retry rule sits outside it. |
| MH15 | meta | Four capability statuses (supported, supported_with_extension, advisory, unsupported); a status describes a guarantee, not a similarly named command | references/meta_harness/.agents/skills/harness/references/runtime-capabilities.md:7-14 | adapt | Maps onto our per-surface table in `surfaces.md`; unverified chat/Cowork cells become `advisory`. |
| MH16 | meta | Role contract fields as a table: ownership with enforcement kind, workspace, escalation, deny-by-default permissions, blocked and partial states | references/meta_harness/.agents/skills/harness/SKILL.md:87-97 | pattern | Partly covered by write-safety; the "explicit blocked/partial completion" field is new. |
| MH17 | meta | Semantic model policy (inherit, fast, economy, balanced, strong); concrete model ids only in a removable override | references/meta_harness/.agents/skills/harness/SKILL.md:139-143 | pattern | We name haiku/sonnet/opus directly; a policy word would survive model renames. Low priority. |
| MH18 | meta | Phase 0 inventory and drift audit with a closed set of operation classes; unresolved conflict means stop, not overwrite | references/meta_harness/.agents/skills/harness/SKILL.md:175-204 | pattern | Our Step 1 detects mode by prose; a read-only audit script could back it (see MH19). |

### (b) Runtime-adjacent (installer and audit tooling, Python)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| MH19 | meta | Read-only audit classifies a target as new, migration, drift repair, adapter update, skill-only or extension from file evidence | references/meta_harness/scripts/audit_harness.py:153-174 | adapt | Pure function over path sets; testable without a repo. Needs our layout markers, not `.agents/`. |
| MH20 | meta | Stale generated files found by a header marker in the first 512 bytes, only when the canonical source is missing | references/meta_harness/scripts/audit_harness.py:102-114 | adapt | Rule: never delete unknown files; only marked, orphaned ones are reported. |
| MH21 | meta | Install plan as data: operation enum CREATE, UPDATE, KEEP, SKIP, REMOVE, CONFLICT; any conflict blocks apply before the first write | references/meta_harness/scripts/installer_core.py:34-41 | adapt | Plan-then-apply split fits packager and any future updater; see repository_harness overlap. |
| MH22 | meta | Managed-copy marker holds a sha256 over sorted relative path plus bytes; equal digest means KEEP, else UPDATE | references/meta_harness/scripts/installer_core.py:488-495 | adapt | Makes re-install idempotent. Our packager has no "already current" check. |
| MH23 | meta | Ownership test: a destination not marked as ours is CONFLICT and force cannot overwrite it; symlinked parents also conflict | references/meta_harness/scripts/installer_core.py:528-554 | adapt | Cost-statement case for the judge: a refusal that blocks a user-owned path. |
| MH24 | meta | Apply with transaction: snapshot each updated path, on any exception remove touched paths and restore snapshots in reverse | references/meta_harness/scripts/installer_core.py:908-985 | adapt | Best-effort only, as its own comment says; clean temp backups in finally. |
| MH25 | meta | Generated native profile carries a header; update only if the existing file has that header, else conflict | references/meta_harness/scripts/installer_core.py:663-691 | adapt | Same marker idea as MH20 applied to agent files a generator writes. |
| MH26 | meta | Dependency-free role-brief parser reads a small scalar and inline-list YAML subset, falls back to heading and filename | references/meta_harness/scripts/installer_core.py:328-390 | reference | Our lint already parses frontmatter by hand; nothing to port beyond the fallback idea. |
| MH27 | meta | Portable-boundary lint: a line that requires a runtime-specific path fails unless nearby text says removable, optional or deleted | references/meta_harness/scripts/validate_skills.py:92-103 | adapt | Needs a surface-path list for us (`.claude/`); a context window of three lines. Heuristic. |
| MH28 | meta | Adapter validator: every adapter doc must contain required terms and a status word; fixtures must not duplicate the skill | references/meta_harness/scripts/validate_adapters.py:20-29 | pattern | Term-presence check is weak, as our own notes say of keyword checks; use for `surfaces.md` only if wanted. |

## Do not port

| source | reason |
|---|---|
| references/meta_harness/scripts/installer_tui.py | Terminal UI for choosing runtimes; out of scope |
| references/meta_harness/.agents/skills/harness/references/pi-agent-adapter.md, cursor-agent-adapter.md, antigravity-agent-adapter.md, codex-agent-adapter.md | Adapters for runtimes we do not target; Claude surfaces live in `surfaces.md` |
| references/meta_harness/.agents/skills/harness/templates/codex-agent.toml | Codex profile template; no Claude use |
| references/meta_harness/scripts/installer_core.py (legacy mirror and ForgeCode, Droid, OpenHands, Aider handling) | Deprecated, unverified targets in the source itself (CHANGELOG.md:51) |
| references/meta_harness/install.sh, install.ps1, meta-harness launchers | Bootstrap installers for a CLI we do not ship |
| references/meta_harness/docs/_layouts, docs/_config.yml, .github/workflows/pages.yml, scripts/validate_pages.py | Jekyll documentation site and its checks |
| references/meta_harness/plans/upgrade_plan_20260906.md | A 2154-line plan; headings were read, bodies not mined, and it restates the shipped reference docs |
| references/meta_harness/.agents/skills/harness/references/qa-agent-guide.md, skill-testing-guide.md sections 1-9 | Same material as revfactory, already ported |

## Gaps

- No proposer/evaluator split, no search or optimisation loop code, no run logging or trace format. The only loop is prose in `autonomous-experimentation.md`; the only ledger is a TSV shape. Searched: `proposer`, `evaluator`, `candidate`, `search`, `optimi` across `scripts/` and `.agents/`; the only hits are the prose profile and test names. Any harness-search capability for finhub-harness is net-new design, not a port.
- No retrospective or feedback-into-prompts loop. `CHANGELOG.md` is a checkpoint history, not a lesson format. `finhub-harness-evolve` is ahead of this repo.
- No runtime patterns for an agent loop, compaction, token metering or SSE; the repo has no runtime. Runtime-adjacent rows MH19-MH28 are file-installer patterns only.
- The measured evidence is thin: `04_results.tsv` rows are decision simulations with self-assigned scores (final-report.md:39 says so). Treat MH8-MH12 as a method, not as proof it works.
- The Phase 0 audit and installer assume a `.agents/skills/` layout; every path constant would change for `.claude/` and `skills/`.
- Not opened: `scripts/installer_tui.py`, `scripts/test_*.py` bodies (names only grepped), `docs/compatibility/*`, `docs/installation/*`, `docs/index.md`, `docs/sample-prompts.md`, `skill-writing-guide.md`, `team-examples.md`, and the Pi, Cursor and Antigravity adapter bodies.
- Overlap to watch: MH21-MH24 duplicate the "safe updater with three-way merge" candidate noted for `repository_harness` (CLAUDE.md row 2026-10-21); decide between them before any design. meta_harness has no three-way merge, only keep/update/conflict.
