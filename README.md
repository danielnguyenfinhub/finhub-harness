# finhub-harness

A Claude plugin that builds agent teams, plus the Python runtime and build team that grew alongside it. One repo, two capabilities.

| | Capability | What you get | Status |
| --- | --- | --- | --- |
| 1 (primary) | **Harness factory** — `finhub-harness` and `finhub-harness-evolve` skills | Describe a domain; get a team of specialist agents, the skills each one follows, and an orchestrator written for the Claude surface you use | Built, cold-tested once on Claude Code. Chat and Cowork behaviour is **unverified** (see Gaps) |
| 2 (secondary) | **Master FinHub runtime** — `src/master_finhub/` plus a five-agent build team in `.claude/` | A stdlib-only Python agent runtime (slices 1-11) and the team that built and QA'd it | Built; 677 tests pass, 9 skipped |

## 1. The harness factory

`finhub-harness` is an English port of [revfactory/harness](https://github.com/revfactory/harness) v2.1.0 (Apache-2.0). Ask for "a harness for X" and it designs the agents, writes one `SKILL.md` per agent job, and writes an orchestrator that says who works in what order. It supports three execution modes on Claude Code:

- **A. Workflow orchestration** — scripted phases and parallel agents.
- **B. Persistent named agents** — long-lived teammates that message each other.
- **C. Sub-agent delegation** — isolated one-shot agents.

What FinHub adds on top of the original:

- **Surface adaptation.** The orchestrator is written for where it will run. Claude Code gets the modes above; Claude chat and Claude Cowork get a single-context fallback where one context plays each role in turn (`skills/finhub-harness/references/surfaces.md`).
- **Authority List with a fresh-context judge.** Every borrowed design decision cites `references/<repo>/<path>:<line>` and its licence tier. A judge that sees only the design rules each claim UPHELD, REJECTED or UNVERIFIED; up to three rounds, then it escalates to you with both positions (`references/quality-gates.md`).
- **Mutation-tested boundary QA.** QA re-runs the real gates, probes the code adversarially before it will write PASS, and mutates a scratch copy; a green gate with a surviving mutant is a FAIL.
- **Licence-tiered enrichment.** A procedure for borrowing patterns from other harness repos through pinned submodules and port maps, with hard licence stops (`references/source-enrichment.md`).

`finhub-harness-evolve` is the companion: it folds run feedback back into agents, skills and the change history.

### Install

| Surface | Steps | Verified? |
| --- | --- | --- |
| **Claude Code** | `/plugin marketplace add danielnguyenfinhub/finhub-harness`, then `/plugin install finhub-harness@finhub-harness-marketplace` | Marketplace manifest present; install flow not run end to end in this session |
| **Claude Cowork** | Run `bash scripts/package-plugin.sh`, then add `dist/finhub-harness.plugin` in Cowork's plugin settings | Package builds (script exits 0); loading in Cowork **not tested** |
| **Claude chat (claude.ai)** | Run `bash scripts/package-plugin.sh`, then upload `dist/finhub-harness-skill.zip` and `dist/finhub-harness-evolve-skill.zip` as skills | Zips build; upload and behaviour **not tested** |

`dist/` is git-ignored, so Cowork and chat users build the files themselves from a clone (needs `bash` and `python3`). The packager validates `plugin.json`, skill frontmatter and a few known-bad patterns before it writes anything.

### Use

In any project, say: `build a harness for <domain>`. Other triggers: "design an agent team", "audit this harness", "migrate this harness", "borrow pattern X from repo Y", and for the companion, "harness retrospective" or "fold this feedback in".

## 2. The Master FinHub runtime

`src/master_finhub/` is a Python 3.11+ agent runtime with no runtime dependencies (the Anthropic SDK is an optional extra). It contains the agent loop, context compaction, command guard and workspace fence, model router, checkpoint and resume, graph executor, message bus and execution modes, a docker sandbox, a stdio MCP client, a loopback SSE server and deterministic evals, plus a `factory/` package that generates teams and skills in code.

The team that built it lives in `.claude/`: reference-miner, strategy-architect, adversarial-risk-judge, runtime-builder and boundary-qa, driven by the `master-finhub-orchestrator` skill. Ask it to "rebuild slice N" or "re-run only the judge".

```
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Run the CLI with `master-finhub` (entry point `master_finhub.cli:main`).

## Reference repos and licences

Seven reference harnesses are pinned as read-only submodules under `references/` (`git submodule update --init --depth 1` to fetch them). Port patterns, do not copy files, unless the row allows it. `references/LICENSES.md` is the source of truth.

| Submodule | Licence | Rule |
| --- | --- | --- |
| `autogpt` | `classic/` MIT; `autogpt_platform/` Polyform Shield | Never use `autogpt_platform/`. Only `classic/` |
| `dify` | Apache-2.0 modified | Pattern only; no mirrored names or structure |
| `crewai`, `deepseek_harness`, `openhands`, `openharness` | MIT | Adapt, with a one-line source comment |
| `revfactory_harness` | Apache-2.0 | Adapt or reference; keep upstream notices |

Notes: `openhands` is a UI-only fork with no agent runtime. The `openharness` upstream organisation is unverified; the pin is a fork at 9b2efd7.

## Gaps (stated plainly)

- **Claude chat and Cowork:** whether sub-agents, messaging or file writing work there is unverified. The factory plans single-context execution on both until you confirm. The six-probe test script and result sheet are in [`docs/surface-verification.md`](docs/surface-verification.md).
- **Docker sandbox:** its real-container test is skipped where no docker daemon exists, and was skipped in the build environment.
- **Plugin install flow:** the commands above follow the plugin layout but were not run against a live Claude Code install.
- **Migrated build orchestrator:** its Phase 2 was converted to the v2 tools and has not been re-run end to end.

## Licence

Apache-2.0 (`LICENSE`, `NOTICE`). The factory skill is derived from revfactory/harness v2.1.0, also Apache-2.0.
