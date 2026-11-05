# Port map — openrig

- Submodule: references/openrig
- Pinned SHA: 475ccab (confirmed with `git rev-parse --short HEAD`)
- Licence: Apache-2.0 (`references/openrig/LICENSE` is the standard Apache text; holder "Copyright 2026 Mike Schwarz" per licence-rules.md row `openrig`, not re-read here). Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: PARTIAL, a sample. Opened: most of `docs/reference/` that concerns SDLC, planning, state and refocus; `scripts/gate-lane*.mjs`, `mirror-skills.mjs`, `check-docs-guard.mjs`; the orchestration, review and oversight pod skills, `watchdog` and `verification-before-completion`; about ten files under `packages/daemon/src/domain/`. The rest is listed in Gaps.
- Language: docs and skills are Markdown (adapt means prose or a rule in `skills/`); daemon and scripts are TypeScript and Node (adapt means a Python rewrite under `src/master_finhub/` or `skills/finhub-harness/scripts/`).
- Id prefix: `OR`.
- Scope: harness-factory patterns first, runtime patterns second.
- Earlier OpenRig port maps (discipline, state, shortlist) named in licence-rules.md were not on disk in this checkout; the adopted list below comes from CLAUDE.md only.

## Already adopted (do not re-propose)

| candidate | what | where it lives now |
|---|---|---|
| OR-D1 | verdict-to-candidate binding | `skills/finhub-harness/scripts/candidate_id.py` (CLAUDE.md row 2026-10-08) |
| OR-D2 | mutant catches judged at the intended assertion | `scripts/mutant_gate.py` (CLAUDE.md row 2026-10-08) |
| OR-D4 | cause-of-miss tags and drift row | `scripts/finding_tags.py`, quality-gates 3-8 (CLAUDE.md row 2026-10-11) |
| OR-D6 | cost statement for a new refusal, prompt or step | quality-gates 3-11 (CLAUDE.md row 2026-10-15) |
| OR-S5 | ship scan of packed files | `scripts/ship_scan.py` (CLAUDE.md row 2026-10-12) |
| OR-S6 | waiver ledger | `WAIVERS.md`, `scripts/waiver_ledger.py` (CLAUDE.md row 2026-10-14) |
| OR-S7 | skill provenance and freshness warnings | `lint_harness.py` verified-* rules (CLAUDE.md row 2026-10-14) |
| OR-S8 | rigor assigned by the owner (Part A default, Part B only when assigned) | Rigor table, `scripts/rigor_check.py` (CLAUDE.md row 2026-10-14) |

Also covered without an OR id, by grep of `skills/` and CLAUDE.md only: a smoke run is never a PASS (quality-gates C8, so the smoke flag in `references/openrig/scripts/gate-lane-run.mjs:89` adds little); the Quick lane matches the elastic middle of `references/openrig/docs/reference/sdlc-conventions.md:203`; absolute and `..` path refusal matches `references/openrig/packages/daemon/src/domain/path-safety.ts:7`; credential patterns match `references/openrig/packages/daemon/src/domain/transcript-redaction.ts:12` (our `secret_scan`).

## Findings

### (a) Harness factory: planning, briefs, orchestration

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OR1 | planning | Planning rigor is a per-piece dial: P0 pointers, P1 spec, P2 research round, P3 adversarial pass, P4 blind design diff | references/openrig/docs/reference/planning-dial.md:8 | adapt | Our Rigor table prices verification only; the owner would assign the rung. |
| OR2 | planning | A piece earns a research or adversarial round only if a wrong plan is costly, hard to undo and invisible to its author | references/openrig/docs/reference/planning-dial.md:35 | adapt | Importance alone never earns it. Context gate at :27: only context-holders write prompts. |
| OR3 | planning | Dispatch brief carries goal, acceptance criteria, exact context routes and territory; default scope is the whole spec, smaller chunks need a stated reason | references/openrig/docs/reference/wave-sdlc.md:22 | adapt | Fits the Quick-lane brief. Territory overlap means serialize; mid-build conflict means stop and rule. |
| OR4 | planning | A spec is ready when a cold reader, given only it and its routed reads, reproduces the intent; reread it as that reader | references/openrig/docs/reference/product-management-pass.md:16 | adapt | Cold-reader test for generated skills and agent briefs; reread step at :58. |
| OR5 | planning | Senders put problem, grounding and options on the table and leave steering to the receiver, upward and downward | references/openrig/docs/reference/product-management-pass.md:79 | pattern | Weak models (haiku tier) may need steps; check against the light skill first. |
| OR6 | planning | Right-layer check: before a fix, name the layer one below, state what each fixes and leaves broken, then choose | references/openrig/docs/reference/product-management-pass.md:120 | adapt | Tell: the lower fix is often smaller because it deletes. Small prompt line for architect and builder. |
| OR7 | orchestration | Scope each status read to the question; capture a transcript only for one stale owner; huge output is a protocol miss | references/openrig/packages/daemon/specs/agents/shared/skills/pods/orchestration-team/SKILL.md:44 | adapt | Token-efficiency rule for orchestrator prompts. An event triggers a check, never elapsed time. |
| OR8 | orchestration | On a missed handoff, name the miss and the rule instead of silently doing the work; bridge only after repeated failure | references/openrig/packages/daemon/specs/agents/shared/skills/pods/orchestration-team/SKILL.md:54 | adapt | A permanently busy orchestrator signals a broken teaching loop. Applies to lead versus worker. |
| OR9 | orchestration | An unblock keeps the operation's scope and never grants publish, destructive or lifecycle powers; decide from the real prompt | references/openrig/packages/daemon/specs/agents/shared/skills/pods/orchestration-team/SKILL.md:216 | adapt | Pairs with C28 ask-first; for unattended runs. Idle-seat rule at :159, plain-Go rule at :206. |

### (b) Harness factory: review, verification, verdicts

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OR10 | verification | Anti-slop review question: will an agent in three months find two ways to do the same thing? | references/openrig/packages/daemon/specs/agents/shared/skills/pods/review-team/SKILL.md:62 | adapt | Checklist: duplication, pattern divergence, parallel implementations, naming. Small QA addition. |
| OR11 | judge | Two reviewers work blind, then answer each other's findings AGREE, DISAGREE or PARTIAL; synthesis marks CONFIRMED, DISPUTED, WITHDRAWN | references/openrig/packages/daemon/specs/agents/shared/skills/pods/review-team/SKILL.md:129 | adapt | A panel pattern hive lacked. Hindsight review for spec-less work at :121. Costs a second reviewer. |
| OR12 | judge | Proof drop header has five required fields; verdict and artifact type are closed sets; agent records that it looked at the evidence | references/openrig/docs/reference/sdlc-conventions.md:325 | adapt | Compare `verdict-schema.md` first. Hand-placed files without a drop are the anti-pattern. |
| OR13 | verification | When intent rests on a missing capability: revise ambition down, mark PARTIAL, name the gap as its own work, never widen scope | references/openrig/docs/reference/sdlc-conventions.md:175 | adapt | Five parts: asked, shipped, not shipped with proof, coverage limits, follow-ons. |
| OR14 | verification | Tests must pin the absence of the false claim in every encoding, not only the presence of the true one | references/openrig/docs/reference/wave-sdlc.md:99 | adapt | Not written in `qa-agent-guide.md` by grep. Evidence theater, wrong-reason failures, at :95. |
| OR15 | verification | Six ways a green check lies: count not content, label not value, one tested axis, parse-only, hang, truncated inventory | references/openrig/packages/daemon/specs/agents/shared/skills/process/verification-before-completion/SKILL.md:113 | pattern | File is vendored from Obra Superpowers; take the idea, write fresh QA probes. |
| OR16 | verification | A shortcut that makes a worktree import another tree's code gives false greens; check resolved paths and plant a deliberate error | references/openrig/docs/reference/worktree-builds.md:1 | adapt | Python analog: editable install from another checkout. QA probe prints package `__file__`. Check at :42. |
| OR17 | verification | A new gate run deletes any earlier verdict, binds to a clean HEAD, and fails if HEAD moved before the verdict is written | references/openrig/scripts/gate-lane.mjs:111 | adapt | Overlaps C7 and `candidate_id.py`; check first. Single-use consume at references/openrig/scripts/gate-lane-consume.mjs:12. |

### (c) Harness factory: knowledge, evolve, config

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OR18 | memory | Items carry a stage field from birth: wip, provisional, established, canonical, superseded (must name successor), retired | references/openrig/docs/reference/knowledge-maturity.md:88 | adapt | Extends OR-S7 keys. Lint idea: superseded without successor. Warrant rule at :55. |
| OR19 | retrospective | Promote a learned practice only if it holds on a stranger's machine in another project; record the incident in one line | references/openrig/docs/reference/chain-file-convention.md:111 | adapt | For evolve LESSON promotion. Editing a file is not delivery to a running seat (:123). |
| OR20 | coordinator | Choose intervention by evidence: no-op for an active owner, wake for liveness, refocus for drift, checkpoint at a phase boundary | references/openrig/packages/daemon/specs/agents/shared/skills/core/watchdog/SKILL.md:46 | adapt | Heavy nudge when a light one was due is a common stall (refocus-channel.md:103). |
| OR21 | permissions | Profile restore policy may only narrow; an ambiguous unqualified reference is refused; same skill id with different content fails launch | references/openrig/docs/reference/agent-spec.md:266 | adapt | Lint candidates for generated harnesses. Precedence at :177, skill conflict at :288. |

### (d) Runtime and hooks

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| OR22 | hooks | Hook fires on transcript growth, not turns or time; compaction keeps due state; failures degrade loudly, three failures raise one item | references/openrig/docs/reference/refocus-channel.md:19 | adapt | Evidence for deferred CW3. A hook must never break a turn; 5 s limit at :34. |
| OR23 | 5 | Session, activity and resumability stay separate axes; unknown is a valid answer; parked, held and stuck are derived at read time | references/openrig/docs/reference/agent-state-taxonomy.md:14 | adapt | Parked is accident, held is on purpose (:44). Stuck anchors: workflow-deadline.ts:1. Check `team.py` names. |
| OR24 | meta | A new detector enters on trial, measured but not consulted, and is promoted after agreeing observations; partial coverage gets identity-only trust | references/openrig/docs/reference/agent-state-taxonomy.md:72 | adapt | Model for new lint rules: WARN-trial before blocking. A fixture pass alone never promotes. |
| OR25 | 7 | Marking work done requires a reason from a closed set; handoff, blocked and escalation also require a target | references/openrig/packages/daemon/src/domain/hot-potato-enforcer.ts:59 | adapt | Enforced in one layer. Fits `unit_tracker` done semantics and worker reports. |
| OR26 | 7 | Obligation lives once on the row; the wake is at-least-once, so retries re-send a pointer, never the content | references/openrig/packages/daemon/src/domain/queue-wake-ladder.ts:6 | adapt | Ladder state derived from log markers, survives restart. Unconfirmed outcomes escalate, never retry. Pairs HV11. |
| OR27 | 2 | Before compacting, ask the agent to write a restore map; send compact only after that artifact is published within a deadline | references/openrig/packages/daemon/src/domain/claude-compaction-enforcer.ts:9 | adapt | Opt-in, default off; re-arm below threshold; uncertain delivery never replays. Feeds the state ledger. |
| OR28 | 3 | Five named permission postures with an allow, ask, deny split and a named destructive class; config policies are recorded, not applied | references/openrig/docs/reference/rig-spec.md:251 | pattern | Comparison data for CW1 (not started). Reusable part: say recorded versus enforced. |
| OR29 | meta | Id-keyed BEGIN/END markers in CLAUDE.md; the old marker form is still recognised so rename or uninstall is clean | references/openrig/packages/daemon/src/domain/managed-blocks.ts:8 | adapt | Closes the C33 gap where a renamed orchestrator leaves the old block. Merge at :36. |
| OR30 | 3 | Test launches strip the inherited state-path variable and name an explicit scratch path; inheriting it is a defect whatever happens | references/openrig/docs/reference/sdlc-conventions.md:368 | adapt | QA rule: clear inherited env before runtime tests. An explicit setting still wins. |

## Do not port

| source | reason |
|---|---|
| references/openrig/packages/ui/**, references/openrig/packages/tui/** | Web and terminal UI for the rig product; out of scope. |
| references/openrig/packages/cli/** and the `rig` command surface (tmux, cmux, herdr, seat launch, handover) | Process and terminal orchestration of local agent sessions; we use Claude Code subagents. |
| references/openrig/packages/daemon/specs/agents/shared/skills/process/systematic-debugging/SKILL.md, `test-driven-development`, `verification-before-completion` | Vendored from Obra Superpowers (frontmatter `vendored_from`); upstream licence differs. Idea only, as in OR15. |
| references/openrig/packages/daemon/specs/agents/shared/skills/process/dogfood/SKILL.md, `agent-browser`, `frontend-design` | Vendored from Vercel agent-browser or an unknown vendor ("quarterly license review"); do not copy. |
| references/openrig/docs/reference/non-interruptive-mode.md | Launch flags that accept Claude Code and Codex bypass-permission warnings; unsafe to imitate. |
| references/openrig/scripts/gate-lane-lock.mjs | Machine-wide localhost-port mutex for one desk running its own gate; our QA runs singly. |
| references/openrig/scripts/bootstrap-product-factory-vps.sh, `vm-bootstrap/`, `docker/`, `demo/`, `assets/` | Provisioning and demo material for the OpenRig product. |
| references/openrig/docs/reference/slack-app-setup.md | Slack integration for the product. |

## Gaps

- No scripted mutation testing, eval runner or benchmark scorer beyond what OR-D2 already took from `packages/test-system/ci/result.mjs`; not searched again here.
- Continuity policy (`sync_triggers`, restore quiz) is validated but unused: `references/openrig/docs/reference/rig-spec.md:670` says nothing acts on it. Row OR27 is the working mechanism instead.
- No multi-reviewer panel beyond the pair in OR11; no judge panel with a tie-break rule was found in the files opened.
- Not opened, so unmined: `docs/reference/health-diagnosis.md`, `lore-routing.md`, `stream-classifier-worker.md`, `release-boundary.md`, `rosters.md`, `edge-types.md`, `product-journey-sdlc.md`, `mission-install.md`; skills `pm/requirements-writer`, `pm/office-hours`, `core/human-in-the-loop`, `core/messaging-the-human`, `pods/development-team`; daemon `queue-stuck-sweep.ts`, `watchdog-policy-engine.ts`, `workflow-*`; `ARCHITECTURE.md`, `CHANGELOG.md`, `ROADMAP.md`.
- Mirror and digest scripts (`references/openrig/scripts/mirror-skills.mjs:19`, `regen-edge-digests.mjs:1`) were read but not listed: checksum-based drift check plus "regen refreshes only the reality side" is a packaging idea of low value now.
- `check-docs-guard.mjs:3` (exact-path exceptions, never directory holes) was read and left out as low value.
- Overlap with `skills/` was checked by grep for a few words only (hindsight, context proof, anti-slop, absence, untested axis, editable). A design must re-check before building.
- Line numbers cite the heading, comment block or `export`/`function` line that starts the unit.
