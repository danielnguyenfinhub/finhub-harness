## Harness: finhub-harness (primary capability — the harness factory)

**Goal:** A Claude plugin (`.claude-plugin/plugin.json`, skills in `skills/`) that builds agent teams and their skills for any domain, on Claude Code, Claude chat or Claude Cowork. Ported from revfactory/harness v2.1.0 (Apache-2.0) and extended with surface adaptation, an adversarially audited Authority List, mutation-tested QA and licence-tiered enrichment from the pinned reference harnesses.

**Trigger:** "build / design / extend / audit / migrate a harness", "create an agent team", "borrow pattern X from repo Y" → use the `finhub-harness` skill. "Harness retrospective", "evolve the harness", "fold this feedback in" → use the `finhub-harness-evolve` skill. Package for Cowork or chat with `scripts/package-plugin.sh`.

## Harness: master-finhub (secondary capability — the runtime build team)

**Goal:** Five-agent team (reference-miner, strategy-architect, adversarial-risk-judge, runtime-builder, boundary-qa) that mines the pinned `references/` submodules, designs runtime slices with an adversarially audited Authority List, and builds and verifies the Python runtime in `src/master_finhub/` one slice at a time. Slices 1-11 are built; slice 12 (factory) is superseded by the `finhub-harness` skill above.

**Trigger:** Any request to build, re-run, update or improve the Master FinHub runtime (including partial re-runs such as "re-run only the judge" or "rebuild slice N") → use the `master-finhub-orchestrator` skill.

**Change history:**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-10-01 | Initial build: 5 agents, 5 skills, hybrid orchestrator | `.claude/agents/`, `.claude/skills/` | Approved plan Part A |
| 2026-10-01 | Tiered models (sonnet: miner/builder/QA; opus: architect/judge) instead of all-opus | all agents, orchestrator | Daniel's global CLAUDE.md §8 and the Master FinHub spec both tier models |
| 2026-10-01 | English body headings in agent/skill files; frontmatter and orchestrator Korean markers unchanged | all agents and skills | Daniel reads English; the harness skill parses frontmatter only |
| 2026-10-02 | Runtime slices 8-11 built, QA'd and merged (PRs #5-#9); fix round on slices 10-11 | `src/master_finhub/`, `tests/` | Resumed build after the local session was lost |
| 2026-10-02 | Repo becomes the `finhub-harness` Claude plugin: `finhub-harness` + `finhub-harness-evolve` skills under `skills/`, English port of revfactory/harness v2.1.0 plus `surfaces.md`, `quality-gates.md`, `source-enrichment.md`; `scripts/package-plugin.sh` for Cowork/chat | `.claude-plugin/`, `skills/`, `scripts/` | Daniel: the most important capability is building harness agent teams like revfactory/harness, for Code, chat and Cowork |
| 2026-10-02 | `master-finhub-orchestrator` Phase 2 migrated from v1 `TeamCreate`/`TeamDelete` to v2 named agent + fresh-context judge per round | `.claude/skills/master-finhub-orchestrator/` | v1 team tools no longer exist; Phase 2 had already been run this way by hand |
