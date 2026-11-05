# Port map — paperclip

- Submodule: references/paperclip
- Pinned SHA: 2a5a323 (confirmed with `git rev-parse --short HEAD`, full 2a5a323e)
- Licence: MIT (`references/paperclip/LICENSE:1-3`, "Copyright (c) 2025 Paperclip AI"; licence-rules.md row `paperclip`). No NOTICE file at the root. The holder is disputed, see Gaps. Every row below says `pattern` or `reference` (idea only, fresh text), so no holder text is copied.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the scope given (agent skills, task checkout, approvals, MCP governance, run verification, failed-run repair, heartbeat and budget controls). Not exhaustive: `server/src/services/heartbeat.ts`, `ui/`, `packages/` adapters and chat channels were not opened.
- Language: sources are TypeScript and Markdown. The runtime is Python, so a runtime row is an idea rewritten from scratch.
- Id prefix: `PC`.
- Scope: harness-factory patterns first, runtime patterns second.

## Already adopted (do not re-propose)

| candidate | what | where it lives now |
|---|---|---|
| C26 | keep an earlier QA FAIL after a passing retry, from `references/paperclip/.agents/skills/verify-paperclip/SKILL.md:192` | QA retry rules in `skills/finhub-harness/references/` and `.claude/agents/boundary-qa.md` (CLAUDE.md row 2026-10-21) |
| C28 | ask first before an outside effect, from `references/paperclip/skills/paperclip/SKILL.md:470` and `references/paperclip/doc/MCP-ACCESS-GOVERNANCE.md:328` | Ask-first block in `orchestrator-template.md` (CLAUDE.md row 2026-10-22) |
| C25 (part) | first failing step as the baseline, from `references/paperclip/.agents/skills/fix-failed-paperclip-run/SKILL.md:53` | `finhub-harness-evolve/SKILL.md` Phase 3 item 7 |

Rejected by C25 and not re-listed: red-first reproduction as a rule for the evolve skill (here PC21 only offers it for runtime bug fixes).

## Findings

### (a) Harness factory

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| PC1 | factory/consent | An agent may edit its own instructions or skills only with an accepted confirmation that showed a diff, from an earlier run, spent once | references/paperclip/server/src/services/change-consent-gate.ts:117 | pattern | Strong fit for evolve: gate before any skill rewrite. Prose rule, not code. |
| PC2 | factory/consent | A confirmation counts only if its text shows a diff (fenced diff or +/- lines) | references/paperclip/server/src/services/change-consent-gate.ts:48 | pattern | Cheap check for "change approved without seeing it". |
| PC3 | factory/consent | Target key per thing changed (agent instructions, skill, skill import) so consent cannot be reused for another target | references/paperclip/server/src/services/change-consent-gate.ts:14 | pattern | Pairs with PC1; one approval, one named target. |
| PC4 | factory/verification | Second-order safety table: for each changed boundary, list the strongest plausible side effect and a test for it | references/paperclip/.agents/skills/fix-failed-paperclip-run/SKILL.md:112 | pattern | Not in our architect brief; could feed judge cost-statement rows. |
| PC5 | factory/verification | Regression must be run red on unfixed code at the owning boundary; a mock's own return value is not a red | references/paperclip/.agents/skills/fix-failed-paperclip-run/SKILL.md:86 | pattern | C25 rejected for evolve; usable for runtime bug units only. |
| PC6 | factory/verification | A successful retry proves a later attempt passed; never infer an infra fault from a passing retry alone | references/paperclip/.agents/skills/verify-paperclip/SKILL.md:192 | reference | Source of C26, already adopted; wording check only. |
| PC7 | factory/verification | Classify a failed eval as product, model, grading or infrastructure from evidence; a completed wrong answer is not infra | references/paperclip/.agents/skills/paperclip-evals/SKILL.md:48 | pattern | Could extend cause tags (context-gap, judgment-gap) to a mutation or eval run. |
| PC8 | factory/verification | Verification report names source scope, live scope and remaining gaps separately; outcome clean, changed or blocked | references/paperclip/.agents/skills/maintain-verification-skill/SKILL.md:22 | pattern | Fits QA report header; a targeted pass must not read as a full pass. |
| PC9 | factory/verification | Evidence separation: endpoint exists, tool declared, and admitted agent path are three different proofs | references/paperclip/.agents/skills/maintain-verification-skill/SKILL.md:16 | pattern | Useful for gate rows that claim "covered". |
| PC10 | factory/skills | Generated verification skill must be run once end to end (launch, doctor, drive, evidence, cleanup) before handoff | references/paperclip/.agents/skills/create-verification-skill/SKILL.md:54 | pattern | Origin is a third-party fork (see Gaps); take the idea only. Matches our cold trigger test. |
| PC11 | factory/skills | Skill sections a cold-reading agent needs: Launch, Doctor (read-only health check), Drive, Evidence, Cleanup that keeps proof | references/paperclip/.agents/skills/create-verification-skill/SKILL.md:27 | pattern | Doctor-first idea could go into generated QA agents. |
| PC12 | factory/loop | Bounded loop: three invariants (next owner, only real blockers stop, no infinite loop) plus an iteration budget and a board gate | references/paperclip/.agents/skills/terminal-bench-loop/SKILL.md:35 | pattern | Maps to our judge-round cap; the explicit "never silently start N+1" is at :159. |
| PC13 | factory/watchdog | Reviewer of stopped work treats each stop as a claim to verify, not a fact; leaves legitimate stops alone | references/paperclip/doc/TASK-WATCHDOG.md:102 | pattern | Good model for a "stalled orchestrator" check agent. |
| PC14 | factory/watchdog | Watcher mandate has limits that custom instructions cannot widen (stay in subtree, no self-wake, no faked approvals) | references/paperclip/doc/TASK-WATCHDOG.md:107 | pattern | Rule for generated agents: instructions may narrow, never grant authority. |
| PC15 | factory/watchdog | Stop fingerprint hash of stopped leaves plus config; same fingerprint suppresses a repeat review, changed one wakes again | references/paperclip/doc/TASK-WATCHDOG.md:89 | pattern | Directly reusable idea for "do not re-run QA on an unchanged candidate". |
| PC16 | factory/rules | If the system knows the next step and may do it under existing authority, it does it; no user checklists for infra facts | references/paperclip/rules/product-harness-responsibility.mdc:6 | pattern | Matches our light-mode aim; short enough to quote as a principle in own words. |
| PC17 | factory/protocol | State claims must match real state: never say a watcher exists unless a persisted monitor was scheduled and read back | references/paperclip/skills/paperclip/SKILL.md:607 | pattern | Anti-narration rule for orchestrators that promise follow-ups. |
| PC18 | factory/protocol | Blocked-task dedup: skip and do not re-comment when your last note was a blocked update and nobody replied | references/paperclip/skills/paperclip/SKILL.md:117 | pattern | Cuts token use on idle re-runs; fits the state ledger. |
| PC19 | factory/protocol | Scoped-wake fast path: when the wake names a specific task, skip inbox discovery and go straight to checkout | references/paperclip/skills/paperclip/SKILL.md:94 | pattern | Token saver for resume runs; pairs with the unit tracker. |
| PC20 | factory/protocol | Every mutating call carries the run id header so each change is traceable to one run | references/paperclip/skills/paperclip/SKILL.md:30 | pattern | Audit-line idea for generated harness ledgers. |

### (b) Runtime

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| PC21 | runtime/checkout | Atomic task claim: one conditional UPDATE sets owner, run id and status only if unowned or owned by the same run | references/paperclip/server/src/services/issues.ts:11725 | pattern | Core of the checkout idea; sqlite `UPDATE ... WHERE` rowcount equals 1 does it. |
| PC22 | runtime/checkout | Re-claim by the same agent and run returns the row instead of conflicting (no self-409) | references/paperclip/server/src/services/issues.ts:2085 | pattern | Makes claim idempotent; needed for safe retries of a step. |
| PC23 | runtime/checkout | Adopt a stale lock only inside a transaction that locks both runs and confirms the old run is terminal | references/paperclip/server/src/services/issues.ts:7549 | pattern | Crash recovery, not retry; never adopt a lock held by a live run. |
| PC24 | runtime/checkout | Lock lifecycle: finalization compare-and-clears only locks still pointing at the finishing run; never a successor's | references/paperclip/doc/execution-semantics.md:208 | pattern | Spec text for PC21-PC23; use as the test oracle list. |
| PC25 | runtime/checkout | A claim conflict means a real owner or gate; the worker stops and picks other work, never retries | references/paperclip/doc/execution-semantics.md:215 | pattern | Same rule is in the agent skill at SKILL.md:597. |
| PC26 | runtime/queue | Pure admission rule for a new wake while a run holds the lock: coalesce, defer or proceed | references/paperclip/server/src/modules/wake-queue/domain/policy.ts:44 | pattern | Facts in, decision out, no DB or clock; fits our DAG engine tests. |
| PC27 | runtime/retry | Separate retry counters: resource waits, repairs and continuations do not spend the failure-retry budget | references/paperclip/server/src/services/execution-recovery-attempt.ts:43 | pattern | Feeds open hive H3 (retry); keeps waits from exhausting retries. |
| PC28 | runtime/recovery | Recovery is bounded by a durable fingerprint; five same-state attempts then one human-owned escalation, no substitute agent | references/paperclip/doc/execution-semantics.md:925 | pattern | Comments or prose do not reset the count; only state changes do. |
| PC29 | runtime/liveness | Valid next-move primitives list: live run, queued wake, typed participant, pending interaction, timed monitor, human owner, blocker, recovery action | references/paperclip/doc/execution-semantics.md:421 | pattern | Checklist for "stalled" detection in `orchestration/`. |
| PC30 | runtime/liveness | Silence clock starts at last output, else process start, else run start, else creation; levels ok, suspicious, critical | references/paperclip/server/src/modules/active-run-watchdog/domain/policy.ts:24 | pattern | Complements hive HV1 text stall; small pure functions with `now` passed in. |
| PC31 | runtime/budget | Reserve a hold before dispatching paid work, under the same lock as charges; the hold outlives restarts until accounting closes | references/paperclip/server/src/services/budget-reservations.ts:11 | pattern | Estimates gate admission, they cannot cap the provider bill. |
| PC32 | runtime/budget | Budget status ladder: ok, warning at a percent, hard stop at the limit, evaluated from observed spend | references/paperclip/server/src/services/budgets.ts:77 | pattern | Compare with our token meter; the warn percent default is 80 (:682). |
| PC33 | runtime/mcp | Profile says can the agent see the tool; policy says is this exact call allowed now; deny beats allow | references/paperclip/doc/MCP-ACCESS-GOVERNANCE.md:62 | pattern | Two-stage check for `tools/mcp/client.py`; order at :301. |
| PC34 | runtime/mcp | A new write or destructive tool appearing after a catalog refresh is quarantined until an operator re-enables it | references/paperclip/doc/MCP-ACCESS-GOVERNANCE.md:221 | pattern | Defends against upstream servers adding verbs; slice 9 has no catalog diff. |
| PC35 | runtime/mcp | Approval stores a hash of canonical arguments; replaying the same call reuses the pending request instead of stacking | references/paperclip/server/src/services/tool-gateway.ts:8351 | pattern | Unsigned rows older than a grace time are expired, not replayed (:8405). |
| PC36 | runtime/mcp | Approval can be promoted to a trust rule limited to one argument shape, actor scope, count or expiry | references/paperclip/doc/MCP-ACCESS-GOVERNANCE.md:339 | pattern | Ask-first fatigue remedy; extends adopted C28. |
| PC37 | runtime/trust | Low-trust preset: narrower policy wins, unknown scope or foreign company fails closed | references/paperclip/doc/LOW-TRUST-PRESETS.md:24 | pattern | Matches our guard stance; adds the "intersect sources" rule. |
| PC38 | runtime/trust | Output from low-trust work is replaced by a fixed placeholder in higher-trust context until a reviewer promotes it | references/paperclip/server/src/services/source-trust.ts:12 | pattern | Prompt-injection containment between agents in a team. |
| PC39 | runtime/tasks | Child task creation is idempotent per source task plus caller key; blocked children wait, only ready ones wake | references/paperclip/doc/execution-semantics.md:349 | pattern | Fits unit tracker upsert key; stops duplicate fan-out on re-run. |
| PC40 | runtime/tasks | Exact-once decomposition: one accepted plan revision may produce at most one child tree | references/paperclip/doc/execution-semantics.md:353 | pattern | Fingerprint is (source id, accepted revision id). |
| PC41 | runtime/layout | Feature module split into pure domain, ports-based application and adapters; domain may not read the clock or database | references/paperclip/server/src/modules/README.md:1 | pattern | Layering rule for `src/master_finhub/`; enforced by a check script upstream. |

## Do not port

| source | reason |
|---|---|
| references/paperclip/.agents/skills/create-verification-skill/** | Imports a third-party pstack fork (NOTICE.md:1-8, author Lauren Tan, Cursor plugins); its licence is not stated here. Idea only (PC10, PC11). |
| references/paperclip/.agents/skills/maintain-verification-skill/references/** and create-verification-skill/references/feature-map-example/** | Same third-party origin; examples not covered by the root licence statement. |
| references/paperclip/ui/**, references/paperclip/server/src/services/chat-*, references/paperclip/packages/** | Product UI, chat channels, adapters; out of scope. |
| references/paperclip/skills/slack/**, agentmail/**, paperclip-board/** | Product-specific integrations. |
| references/paperclip/skills/complain/**, suggestion-box/** | Submit feedback without asking; conflicts with our ask-first rule (C28). |
| references/paperclip/skills/paperclip/SKILL.md:479 (60-minute approval expiry) | C28 rejected a clock expiry (D5). |
| any verbatim text from Paperclip | Holder dispute; copy nothing, write fresh text with the attribution line. |

## Gaps

- LICENCE HOLDER: `references/paperclip/LICENSE:3` says "Copyright (c) 2025 Paperclip AI", while `references/paperclip/README.md:582` says "MIT (c) 2026 Paperclip Labs, Inc". Not resolved. Hence every row is `pattern` or `reference`; use LICENSE:3 for any attribution line.
- Third-party origin inside the repo: `.agents/skills/create-verification-skill/NOTICE.md:1` names pstack (Lauren Tan) from cursor/plugins; no licence text for it was opened. Idea only.
- No sandbox, path-containment or command denylist found in the files read (searched: policy, low-trust, tool-gateway headers). Our `tools/safety.py` stays net-new.
- No token-compaction or context-window code was opened (searched services listing for compaction: only `workspace-compaction.ts`, a disk concern, not read).
- No agent loop in the files read: `heartbeat.ts` (the lifecycle coordinator, per `rules/heartbeat-execution-boundaries.mdc`) was not opened, so no loop pattern is claimed.
- `server/src/services/issues.ts` is about 12k lines and `tool-gateway.ts` about 11.5k; only the cited regions were read. A line number points at the first line of the unit.
- Evals under `evals/promptfoo` and `.agents/skills/paperclip-evals` were read only for the failure-classification rule (PC7).
- Not verified by running anything: all rows are from reading source and docs.
