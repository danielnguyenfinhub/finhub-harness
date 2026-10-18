# Adopting the concept of aden-hive/hive into finhub-harness

Read 2026-10-18. Source: github.com/aden-hive/hive at commit 67502fa (Apache-2.0, verified from its `LICENSE`; no NOTICE file seen). Read only: README, `host/playbook/runner.py`, the queen delegation prompt and a directory survey. Hive was not run. Its benchmark figures (LongMemEval) are self-reported and unverified here.

Status: a proposal, not a decision. Hive is not pinned, mined or adapted yet.

## The concept in one paragraph

A persistent "queen" agent takes an outcome, does the FIRST unit of the work herself (the pilot), writes the method down as a reusable skill, then fans out parallel workers, one per row. Workers write results to a shared SQLite tracker. "What is left" is always a fresh query of that table, so re-running resumes by construction. A playbook runner adds retries with backoff, rate-limited lanes, a failure-fraction circuit breaker and a dead-letter list for rows that never finish. The queen checks every row before she answers and clears the ones that fail.

## Why not "implement hive"

Hive is a runtime and product (queens, dashboard, browser bridge, personas, cloud sync). finhub-harness is a harness factory plus a small Python runtime. Rebuilding hive here would duplicate it. The useful part is a handful of mechanisms the repo lacks.

## What finhub-harness already has, and the gaps

| Hive mechanism | finhub-harness today | Gap |
|---|---|---|
| Shared tracker, row = unit, "what's left" is a query | `state_ledger.py` resumes at phase level; fan-out is a static pattern | no unit-level (row) state or resume |
| Pilot one unit, then write the skill, then fan out | nothing | orchestrator template has no pilot rule |
| Converge loop: retry, backoff, circuit breaker, dead-letter | `orchestration/dag_engine.py` has no retry or dead-letter (searched) | failures are not retried or recorded as unresolved |
| Queen verifies each row, clears bad ones | boundary-qa verifies built code | no row-level verification gate for bulk work |
| Sentinel (stall and escalation) | `runtime/repeat_reminder.py` partial | low priority |

## Candidates, in suggested order

| ID | Candidate | Lands in | Hive anchor (67502fa) | Proof |
|---|---|---|---|---|
| H1 | Unit tracker script: init table, list pending rows, upsert a row, show status. Stdlib sqlite3. Resume = re-run | `skills/finhub-harness/scripts/` + reference + SKILL.md step | `core/framework/host/playbook/runner.py:1-20`, `agents/queen/nodes/__init__.py:350-364` | pytest with mutants: a re-run never repeats a done row |
| H2 | Pilot-then-fan-out rule for "do N similar things" harnesses | `references/orchestrator-template.md`, `team-patterns.md` | `agents/queen/nodes/__init__.py:336-380` | lint rule: a bulk fan-out section must name its pilot |
| H3 | Converge loop in the runtime: rounds, retry with backoff, circuit breaker, dead-letter, no silent drops | `src/master_finhub/orchestration/` | `host/playbook/runner.py:199-303` (retry, backoff), `:305-366` (converge) | pytest, mypy strict, mutants |
| H4 | Row-verification gate: each row carries a source, suspect rows are cleared, "not found" is never reported as zero | `references/quality-gates.md` | README "What you just watched" step 6; no code anchor read | design audit only |
| H5 | Stall and escalation watcher | runtime | `core/framework/sentinel/classifier.py:98,218` | deferred |

Skip: queen personas, dashboard, browser bridge, memory benchmark, credential sync, Hive-hosted LLM and cloud features.

## Where this fits FinHub work

Bulk jobs such as a book-wide rate sweep, a lender policy re-check or a batch of client reviews are exactly "N similar units". H1 and H2 would let a generated harness resume at the row, and H3 would stop a failed unit vanishing.

## What is unverified

- The upstream URL (aden-hive/hive) is not a danielnguyenfinhub fork and its provenance is not checked.
- Anchors above come from a partial read; the judge must open every line before a design relies on it.
- H4 has no code anchor.
- Nothing here has been tested against Mercury, Twilio or Google Workspace.

## Decisions needed from Daniel

1. Pin hive as the eleventh reference (`references/hive`), as was done for the others? Pinning changes `.gitmodules`, `scripts/check-harness-refs.sh` and CLAUDE.md.
2. Which candidates: H1 and H2 first (plugin side, cheap), then H3 (runtime)? Recommended.
3. Rigor: the repo rule is the full gated team (design, fresh judge, build, QA). Lowering it needs Daniel's own words in `WAIVERS.md`.
