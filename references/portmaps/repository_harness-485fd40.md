# Port map — repository_harness

- Submodule: references/repository_harness
- Pinned SHA: 485fd40 (confirmed: `git rev-parse HEAD` gives 485fd4062be1c71b27c1c9e5585ac4cd2faa7e06)
- Licence: MIT ("Copyright (c) 2025 Hoang Nguyen", `references/repository_harness/LICENSE:3`; licence-rules.md row `repository_harness`). No NOTICE file. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the harness-factory scope (skills, evidence capsule, updater, installer contracts, templates). Not exhaustive: release scripts, workflows, the PowerShell installer and the CLI layer were not opened (see Gaps).
- Language: skills and docs are Markdown, the evidence tools are Python, the updater is Rust. "adapt" means a Python rewrite under `skills/finhub-harness/scripts/` or prose in `skills/`, with the MIT attribution comment.
- Id prefix: `RH`. Numbering is fresh for this map and does not match older `RH` ids quoted in CLAUDE.md (see Gaps).
- Scope: harness-factory patterns. The repo has no agent runtime, so there are no runtime rows.

## Already adopted (do not re-propose)

| candidate | what | source | where it lives now |
|---|---|---|---|
| C25 | change is a guess until a fresh rerun; one hypothesis line per change; keep, revise, remove, or pending | references/repository_harness/.agents/skills/improve-harness/SKILL.md:59 (hypothesis block; rerun at :75, decision at :86) and references/repository_harness/docs/templates/harness-improvement.md:44 | `skills/finhub-harness-evolve/SKILL.md` (CLAUDE.md row 2026-10-21) |
| C27 | citation checker: cited line exists at the pin | references/repository_harness/.agents/skills/audit-onboarding-proposal/scripts/validate_evidence_capsule.py:141 (`git_blob`) and references/repository_harness/.agents/skills/onboard-repository/scripts/emit_evidence_bundle.py:63 (`git_blob_reader`) | `skills/finhub-harness/scripts/cite_check.py` (nothing hashed, by design D-HASH) |
| C33 | one marked pointer block with a size budget; exactly one ordered marker pair or refuse | references/repository_harness/scripts/install-harness.sh:330 (`validate_harness_markers`) and references/repository_harness/tests/installer/assert-agent-authority-contract.sh:35 | `lint_harness.py` `check_pointer()`, SKILL.md Step 5 |

## Findings

### (a) Safe updater with three-way merge (the first candidate named at pin time)

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| RH1 | updater | Three-way decision order: unedited local takes upstream; unchanged upstream or identical edit keeps local; only then a real merge | references/repository_harness/crates/harness/src/application/service.rs:516 | adapt | Three comparisons before any tool call. Pure function; easy to test. |
| RH2 | updater | Wrap `git merge-file -p --diff3` with labels LOCAL, BASE, UPSTREAM; exit 0 clean, 1 conflict, else error | references/repository_harness/crates/harness/src/infrastructure/git_merge.rs:19 | adapt | Python `subprocess` plus three temp files. Needs git on PATH; chat and Cowork have no shell. |
| RH3 | updater | Per-path plan over the union of installed and upstream paths: create, preserve, update, delete, or a typed conflict | references/repository_harness/crates/harness/src/application/service.rs:238 | adapt | Seven (baseline, upstream, local) presence cases; a modified file upstream removed is a conflict, not a delete. |
| RH4 | updater | Typed conflict reasons: overlapping changes, missing managed file, existing unmanaged path, modified-but-removed, unsafe path | references/repository_harness/crates/harness/src/domain/model.rs:155 | adapt | Five reasons; a report names the reason, not just "conflict". |
| RH5 | updater | Installed baseline kept as a versioned state: schema version, core version, per-file content and hash | references/repository_harness/crates/harness/src/domain/model.rs:93 | adapt | This stored BASE is what makes a three-way merge possible. We store none today. |
| RH6 | updater | A conflict changes no live file; BASE, LOCAL, UPSTREAM and RESOLVED are staged apart, and the workspace is frozen | references/repository_harness/docs/decisions/0025-latest-release-self-update-and-human-directed-conflicts.md:49 (rejected alternative at :83) | pattern | Partial markers in a live instruction file would corrupt agent authority at once. |
| RH7 | updater | Resume after conflict: refuse if versions, path set, a frozen file, or the staged BASE and UPSTREAM differ from now | references/repository_harness/crates/harness/src/application/service.rs:136 | adapt | Drift check before apply; abort just deletes the staged session. |
| RH8 | updater | Refuse a resolved file that still has marker lines: line-start `<<<<<<< `, `||||||| `, `=======`, `>>>>>>> ` | references/repository_harness/crates/harness/src/application/service.rs:560 | adapt | Eight lines of Python. Reusable by any "agent merged this file" check. |
| RH9 | updater | Under a lock, re-read every frozen file and compare; a symlink or non-file also refuses | references/repository_harness/crates/harness/src/infrastructure/filesystem_state.rs:404 | adapt | Closes the gap between planning and applying. |
| RH10 | updater | Apply as a transaction: back up touched files and state, write a journal, mutate, commit; recovery restores from the journal | references/repository_harness/crates/harness/src/infrastructure/filesystem_state.rs:430 (recovery at :521) | pattern | Journal phases Applying and Committed. Our `.bak` gate covers one file; this covers a set. |
| RH11 | updater | Forward-only version guard: parse both as semver, refuse a candidate older than installed | references/repository_harness/crates/harness/src/application/service.rs:546 | pattern | Needs a plugin version stored in the baseline (RH5). |
| RH12 | updater | Managed path must be relative: no leading or trailing slash, backslash, NUL, colon, empty, `.` or `..` component | references/repository_harness/crates/harness/src/domain/model.rs:8 | adapt | Same rule family as PR #49 path refusal; check ours is not weaker. |

### (b) Evidence and audit discipline

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| RH13 | audit | Five-way evidence class (Authoritative, Observed, Derived, Decision required, Unknown); never promote silently | references/repository_harness/.agents/skills/onboard-repository/SKILL.md:86 | adapt | Fits the Authority List for regulated domains: a code default is not policy. |
| RH14 | audit | Patch worksheet: every cell mandatory, then a separate counterexample pass; an omitted cell forces NO APPLY | references/repository_harness/.agents/skills/audit-onboarding-proposal/SKILL.md:225 (counterexample pass at :264) | adapt | Judge rule: a missing cell is a rejection, not reviewer confidence. |
| RH15 | audit | Narrow audit modes that state what they did not recompute (`Producer gates: not recomputed`) | references/repository_harness/.agents/skills/audit-onboarding-proposal/SKILL.md:50 (reissue mode at :82) | adapt | Matches Full-lane round 2 auditing only changed rows; adds the explicit "not recomputed" line. |
| RH16 | audit | Independence contract: fresh session, read-only, verify the artifact digest first or return INVALID | references/repository_harness/.agents/skills/audit-onboarding-proposal/SKILL.md:12 | adapt | Overlaps CANDIDATE binding (OR-D1); the new part is no tool writes during audit. |
| RH17 | audit | Temporal words and sentinels are causal claims: "before", "successful" need the signal; one probe is not "the schema" | references/repository_harness/.agents/skills/onboard-repository/SKILL.md:297 (sentinel rule at :303) | adapt | Eight-item checklist for a judge reading a client-facing claim. |
| RH18 | audit | Model supplies an unhashed JSON spec; the tool reads pinned blobs and computes every hash and patch | references/repository_harness/.agents/skills/onboard-repository/scripts/emit_evidence_bundle.py:126 | pattern | Never let a model type a digest. Extends C27 only if D-HASH is reopened. |
| RH19 | audit | Boundary row result is derived: Pass needs equal non-null hashes, Fail needs different ones, otherwise Unknown | references/repository_harness/.agents/skills/onboard-repository/scripts/emit_evidence_bundle.py:89 | adapt | Unknown can never be upgraded to Pass; gate is conjunctive. Compare our QA drift row (OR-D4). |
| RH20 | audit | Inventory rule against check: Enforced, Partially enforced, Unenforced rule, Check lacking authority, Unknown | references/repository_harness/.agents/skills/onboard-repository/SKILL.md:131 | adapt | Strong fit for the harness audit mode: prose rule with no gate, or a gate with no source. |
| RH21 | audit | Proposal must carry six fields: failure prevented, evidence, destination, content, unknowns, replay proof; none is a valid result | references/repository_harness/.agents/skills/onboard-repository/SKILL.md:233 | pattern | Shape for capability-triage candidates. "Return no proposals" matches the CW2 no-op. |

### (c) Encoding rules, advice and entry-point contracts

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| RH22 | gates | Report four enforcement levels apart: local command, optional hook, CI invocation, branch protection | references/repository_harness/docs/patterns/encoding-invariants.md:75 (skill step at references/repository_harness/.agents/skills/encode-invariant/SKILL.md:46) | adapt | Wording for quality-gates reports: a workflow file is not a required check. |
| RH23 | gates | Invariant spec table: authority, scope, allowed, forbidden, exceptions, diagnostic; then positive and negative proof | references/repository_harness/docs/patterns/encoding-invariants.md:25 (proof at :62) | adapt | Our mutation gate already gives negative proof; the table is the missing front half. |
| RH24 | gates | Failure message names the violating item, the rule, the authority source, and a compliant next action | references/repository_harness/docs/patterns/encoding-invariants.md:52 | pattern | Check lint messages after OR-S7 already end in `; fix:`; add the authority pointer. |
| RH25 | advisory | Advice shape: Observation, Heuristic, Trade-off, Proposed enforcement (or None), Verification; advice is never policy | references/repository_harness/.agents/skills/engineering-wisdom/SKILL.md:28 (response shape at :64) | adapt | Template for a generated advisor worker so its output cannot read as a lender or compliance rule. |
| RH26 | entry-doc | Entry-doc budget as a test: word cap over entry files, plus required phrases that must remain | references/repository_harness/tests/installer/assert-agent-authority-contract.sh:35 (word cap :36-37) | adapt | C33 took only the byte cap; the word cap across several entry files is new. |
| RH27 | entry-doc | Negative-presence test: removed routing rules must not return to the entry docs | references/repository_harness/tests/workflow/test-onboarding-evidence.py:284 | adapt | Pins a deletion. Our tests pin added wording only. |
| RH28 | skills | Explicit-only skills: metadata sets implicit invocation false and the description must open "Use only when the user explicitly invokes" | references/repository_harness/tests/installer/assert-agent-authority-contract.sh:90 (policy check at references/repository_harness/tests/workflow/test-onboarding-evidence.py:247) | adapt | Lint rule for a generated skill that sends or writes. Key is `disable-model-invocation` in our lint. |
| RH29 | installer | Re-run is idempotent: a block already equal to the canonical one is skipped, with no backup | references/repository_harness/scripts/install-harness.sh:394 (skip-if-current at :424; backup-once at :239) | adapt | Our Step 5 rewrites between markers each run; a compare-first step avoids a needless backup. |

## Do not port

| source | reason |
|---|---|
| references/repository_harness/crates/harness/src/interface/** and references/repository_harness/crates/harness/src/main.rs | Rust CLI front end for a binary we do not build. |
| references/repository_harness/docs/decisions/0025-latest-release-self-update-and-human-directed-conflicts.md:30 (checksum-verified download and executable replacement) | Binary self-update; a plugin has no executable to replace. |
| references/repository_harness/.agents/skills/improve-harness/SKILL.md:41 (six-way earliest-gap taxonomy) | Rejected in the C25 design; kept out. |
| references/repository_harness/docs/templates/harness-improvement.md:1 (one record file per experiment) | Rejected in C25; state stays in the change-history row. |
| references/repository_harness/.agents/skills/engineering-wisdom/references/heuristics.md:1 | General engineering advice catalog, not harness mechanics. |
| references/repository_harness/CHANGELOG.md | Release notes for the binary. |

## Gaps

- No agent loop, compaction, token meter, sandbox, DAG or SSE code exists here (searched file list for `loop`, `compaction`, `sandbox`; the repo is a Rust installer plus Markdown skills). No runtime rows were possible.
- No judge panel, multi-reviewer consensus or hook system was found. The single audit skill is one reviewer.
- Not opened: `scripts/build-harness-release.sh`, `verify-harness-release-*.sh`, `promote-harness-release-tag.sh`, `.github/workflows/*`, `scripts/install-harness.ps1`, `crates/harness/src/application/self_update.rs` body, `filesystem_state.rs` load and write_state, `render_patch.py` internals and `validate_evidence_capsule.py` beyond lines 244-363. They are release engineering for the binary; any later claim about them needs a fresh read.
- CLAUDE.md quotes older ids (RH11, RH15, RH16, RH26, RH29) from an earlier port map that is not on disk. This map does not reproduce them, so do not cross-refer by number.
- Sources.md of engineering-wisdom and the evidence-capsule v1 reference were not read.
- RH2 and RH12 depend on git and a shell. Chat and Cowork have no shell, so a script adoption is unverified there.
