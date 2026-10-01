## 하네스: master-finhub

**목표:** Five-agent team (reference-miner, strategy-architect, adversarial-risk-judge, runtime-builder, boundary-qa) that mines the pinned `references/` submodules, designs runtime slices with an adversarially audited Authority List, and builds and verifies the Python runtime in `src/master_finhub/` one slice at a time.

**트리거:** Any request to build, re-run, update or improve the Master FinHub harness or runtime (including partial re-runs such as "re-run only the judge" or "rebuild slice N") → use the `master-finhub-orchestrator` skill.

**변경 이력:**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-10-01 | Initial build: 5 agents, 5 skills, hybrid orchestrator | `.claude/agents/`, `.claude/skills/` | Approved plan Part A |
| 2026-10-01 | Tiered models (sonnet: miner/builder/QA; opus: architect/judge) instead of all-opus | all agents, orchestrator | Daniel's global CLAUDE.md §8 and the Master FinHub spec both tier models |
| 2026-10-01 | English body headings in agent/skill files; frontmatter and orchestrator Korean markers unchanged | all agents and skills | Daniel reads English; the harness skill parses frontmatter only |
