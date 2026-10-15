# harness-100: suitable skills and agents for FinHub

Read 2026-10-16. Source: github.com/danielnguyenfinhub/harness-100 at commit 8e8d35c (Apache-2.0), English tree `en/` only.

Status: a recommendation, not a decision. Nothing from harness-100 is installed, pinned or adapted yet. Daniel chooses install or mine (see Next step).

## Assumed stacks (not confirmed by Daniel)

AU mortgage broking (Mercury CRM, Google Workspace, Twilio SMS), the Python harness runtime and Claude plugin in this repo, and WordPress/cPanel/Railway. If the stacks differ, re-rank.

## What was checked

- Verified by command: 100 harnesses, 315 skills, every skill file is named `skill.md`.
- Verified by word-bounded search: zero Australian references (ASIC, ATO, APRA, NCCP, Australia) anywhere in `en/`.
- Verified by search: Korean-jurisdiction content (PIPA, Korean tax and hiring law) remains in 69, 75, 78, 83, 86, 88, 90, 81, 82, and in parts of 72 and 96.
- Sampled only, not read end to end: the skills listed under Adopt (size, Korea hits, first 40 lines of cap-rate-calculator).

## Adopt (fills a gap, jurisdiction-neutral)

| Harness | Take | Fits |
|---|---|---|
| 27-data-pipeline | skills data-quality-framework, dag-orchestration-patterns; agents data-quality-manager, pipeline-reviewer | Mercury sync, rate sweeps, book reviews |
| 38-chatbot-builder | skills intent-taxonomy-builder, conversation-flow-validator; agents dialog-tester, conversation-designer | SMS agent, client-portal flows |
| 30-open-source-launcher | skill license-compatibility-matrix | Apache-2.0 adaptation and licence-tier rules |

## Adopt with a caveat

- 96-real-estate-analyst: location-scoring and the cap-rate formulas suit investor-client scenarios. The cap-rate benchmark table is unsourced (T4 on Daniel's tiers). Never put it in client-facing output. It is not underwriting.

## Rewrite, do not copy

- 69-privacy-engineer: real gap for a broker. The GDPR/PIPA cross-reference pattern could become a Privacy Act and APP cross-reference (notifiable data breach scheme, CDR). Current content is Korean law.
- 75-tax-calculator, 78-personal-finance: Korea-heavy, no direct use.

## Skip

- Duplicates of tools Daniel already has: 66 (contract-of-sale review), 67 and 94 (ACL and compliance audit), 53 and 51 (financial-analysis), 49 (complaints, tickets), 10 and 03 (social, email), 37 (scraping), 62 (ADR), 21, 24, 28 (code review, testing, security).
- Korea-bound: 83, 90, 91, 72.

## Defects found in the source

- All 315 skills are named `skill.md`. Claude Code expects `SKILL.md`. A plain `cp -r` as its README suggests may not load them on a case-sensitive filesystem. Unverified: loading was not tested. Rename on install.
- Agents carry only name and description (no tool or model scoping). Treat as templates, not production agents.

## Verify before acting

1. Do the assumed stacks match?
2. Install into Claude, or mine as a tenth pinned reference for the capability backlog? Recommendation: mine, because attribution and licence rules already exist there.
3. Anything client-facing built from these needs AU T1-sourced content first.

## Next step

Daniel says install or mine. Then the three Adopt rows go first.
