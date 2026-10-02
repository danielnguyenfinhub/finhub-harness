# finhub-harness

Two capabilities in one repo.

## 1. The harness factory (primary) — a Claude plugin

`finhub-harness` turns a domain description into an agent team, the skills each agent uses and an orchestrator that knows which Claude surface it runs on. It is an English port of [revfactory/harness](https://github.com/revfactory/harness) v2.1.0 (Apache-2.0), extended with:

- **Surface adaptation** — Claude Code gets the three execution modes (Workflow, persistent agents, sub-agents); Claude chat and Claude Cowork get a single-context fallback written into the orchestrator (`skills/finhub-harness/references/surfaces.md`).
- **Authority List + fresh-context adversarial audit** — every borrowed design decision cites `references/<repo>/<path>:<line>` with its licence tier; a judge that reads only the design rules each claim UPHELD / REJECTED / UNVERIFIED, max three rounds (`references/quality-gates.md`).
- **Mutation-tested boundary QA** — QA re-runs the repo's real gates after every slice and mutates the code on a scratch copy; a green gate with a surviving mutant is a FAIL.
- **Licence-tiered enrichment** — how to borrow patterns from other harness repos through pinned submodules and port maps (`references/source-enrichment.md`).

Companion skill: `finhub-harness-evolve` folds run feedback back into agents, skills and the change history.

### Install

| Surface | How |
| --- | --- |
| Claude Code | `/plugin marketplace add danielnguyenfinhub/finhub-harness` then `/plugin install finhub-harness@finhub-harness-marketplace` |
| Claude Cowork | `scripts/package-plugin.sh` → add `dist/finhub-harness.plugin` |
| Claude chat (claude.ai) | `scripts/package-plugin.sh` → upload `dist/finhub-harness-skill.zip` (and `dist/finhub-harness-evolve-skill.zip`) as skills |

Then, in any project: `"build a harness for <domain>"`.

## 2. The Master FinHub runtime (secondary)

`src/master_finhub/` is a Python 3.11+ stdlib-only agent runtime built by this repo's own harness team (`.claude/agents/`, `.claude/skills/master-finhub-orchestrator`): agent loop, context compaction, command guard and workspace fence, model router, checkpoint/resume, graph executor, message bus and execution modes, docker sandbox, stdio MCP client, loopback SSE server, deterministic evals. Slices 1-11 are built and QA'd; slice 12 (factory) is superseded by the plugin above.

```
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Pinned reference harnesses live under `references/` as submodules (`git submodule update --init --depth 1`); their licence tiers are in `.claude/skills/reference-mining/references/licence-rules.md`.
