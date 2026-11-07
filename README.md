# finhub-harness

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![CI](https://github.com/danielnguyenfinhub/finhub-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/danielnguyenfinhub/finhub-harness/actions)

A Claude plugin that builds agent teams, plus the Python runtime and build team that grew alongside it. One repo, two capabilities.

| | Capability | What you get | Status |
| --- | --- | --- | --- |
| 1 (primary) | **Harness factory** — `finhub-harness`, `finhub-harness-light` (low-token build) and `finhub-harness-evolve` skills | Describe a domain; get a team of specialist agents, the skills each one follows, and an orchestrator written for the Claude surface you use | Built, cold-tested once on Claude Code. Chat and Cowork behaviour is **unverified** (see Gaps) |
| 2 (secondary) | **Master FinHub runtime** — `src/master_finhub/` plus a six-agent build team in `.claude/` | A stdlib-only Python agent runtime (slices 1-11) and the team that built and QA'd it | Built; 4252 tests pass, 10 skipped (CI on PR #66, 2026-10-22) |

## Contents

- [1. The harness factory](#1-the-harness-factory)
- [2. The Master FinHub runtime](#2-the-master-finhub-runtime)
- [Reference repos and licences](#reference-repos-and-licences)
- [Gaps](#gaps-stated-plainly)
- [Quick start](#quick-start)
- [Contributing](#contributing)
- [Licence](#licence)

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
| **Claude Code** | `/plugin marketplace add danielnguyenfinhub/finhub-harness`, then `/plugin install finhub-harness@finhub-harness-marketplace`. Skills appear as `finhub-harness:finhub-harness`, `finhub-harness:finhub-harness-light`, `finhub-harness:finhub-harness-evolve`. The install copies the whole repository (about 1.4 GB with the `references/` submodules). | Verified 2026-11-05 with Claude Code 2.1.318 using the non-interactive `claude plugin marketplace add` / `claude plugin install` / `claude plugin list` (exit 0 each; version 0.1.0 enabled) and a headless run in which the skill loaded and began its Step 0 context check. It installs what is pushed to `main`, not unpushed local work; a second install after the Phase 2 to 5 merge (exit 0, enabled) contained the merged files. The interactive `/plugin` commands were not run. |
| **Claude Cowork** | Run `bash scripts/package-plugin.sh`, then add `dist/finhub-harness.plugin` in Cowork's plugin settings | Package builds (script exits 0); loading in Cowork **not tested** |
| **Claude chat (claude.ai)** | Run `bash scripts/package-plugin.sh`, then upload `dist/finhub-harness-skill.zip`, `dist/finhub-harness-light-skill.zip` and `dist/finhub-harness-evolve-skill.zip` as skills (the light one alone is enough for a small job) | Zips build; upload and behaviour **not tested** |

`dist/` is git-ignored, so Cowork and chat users build the files themselves from a clone (needs `bash` and `python3`). The packager validates `plugin.json`, skill frontmatter and a few known-bad patterns before it writes anything.

Fallback if the marketplace route fails (direct skill copy, verified to be discovered by Claude Code 2.1.318; invoking it was not run): `cp -r skills/finhub-harness skills/finhub-harness-light skills/finhub-harness-evolve ~/.claude/skills/`. The skills then appear under their bare names (`finhub-harness`, not `finhub-harness:finhub-harness`). Copy all three together: the full skill's scripts are referenced relative to its own folder.

### Use

In any project, say: `build a harness for <domain>`. Other triggers: "design an agent team", "audit this harness", "migrate this harness", "borrow pattern X from repo Y", and for the companion, "harness retrospective" or "fold this feedback in".

## 2. The Master FinHub runtime

`src/master_finhub/` is a Python 3.11+ agent runtime with no runtime dependencies (the Anthropic SDK is an optional extra). It contains the agent loop, context compaction, command guard and workspace fence, model router, checkpoint and resume, graph executor, message bus and execution modes, a docker sandbox, a stdio MCP client, a loopback SSE server and deterministic evals. Teams and skills are generated by the `finhub-harness` skill, not by Python code.

The team that built it lives in `.claude/`: reference-miner, strategy-architect, adversarial-risk-judge, runtime-builder and boundary-qa, driven by the `master-finhub-orchestrator` skill. Ask it to "rebuild slice N" or "re-run only the judge".

```
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Run the CLI with `master-finhub` (entry point `master_finhub.cli:main`). The shipped CLI and server register only `EchoTool`, so the command guard, workspace fence, Docker engine, MCP client and permission modes are libraries that no shipped entrypoint wires yet. A caller of the MCP client must persist `approved_digests(tools)` and pass it as `previous` on the next listing, not the raw latest listing, or a changed tool stops being quarantined.

## Reference repos and licences

Fourteen reference harnesses are pinned as read-only submodules under `references/` (`git submodule update --init --depth 1` to fetch them). Port patterns, do not copy files, unless the row allows it. `references/LICENSES.md` is the source of truth.

| Submodule | Licence | Rule |
| --- | --- | --- |
| `autogpt` | `classic/` MIT; `autogpt_platform/` Polyform Shield | Never use `autogpt_platform/`. Only `classic/` |
| `dify` | Apache-2.0 modified | Pattern only; no mirrored names or structure |
| `crewai`, `deepseek_harness`, `openhands`, `openharness` | MIT | Adapt, with a one-line source comment |
| `revfactory_harness` | Apache-2.0 | Adapt or reference; keep upstream notices |

Notes: `openhands` is a UI-only fork with no agent runtime. The `openharness` upstream organisation is unverified; the pin is a fork at 9b2efd7.

## Gaps (stated plainly)

- **Claude chat and Cowork:** whether sub-agents, messaging or file writing work there is unverified. The factory plans single-context execution on both until you confirm. The six-probe test script and result sheet are in [`docs/surface-verification.md`](docs/surface-verification.md).
- **Docker sandbox:** verified 2026-11-05 against a real daemon (Docker 29.9.2, started with `dockerd` as root inside the build sandbox, image `python:3.12-alpine` pulled): `tests/test_docker_engine.py` passes 10 of 10 with `test_echo_in_container` running, not skipped. That test checks echo, a refused write to `/etc` and a refused network call, so it is a smoke test; the hardening flags are proven by the argv tests only. The test still skips where no daemon or image exists, so CI without Docker does not run it.
- **Plugin install flow:** run twice on 2026-11-05 with the non-interactive `claude plugin` commands (see Install): first against the earlier `main`, then again after the Phase 2 to 5 merge, where the installed tree held all 14 port maps and the `standard` rigor text. Not run: the interactive `/plugin` commands, a headless skill-trigger run on the merged `main`, and anything on Cowork or chat. The install is about 1.4 GB because `references/` is copied.
- **Migrated build orchestrator:** run end to end on 2026-11-05 in the full lane for the `standard` rigor unit: a named strategy-architect, fresh-context judge per round (2 rounds), `SendMessage` revision, a builder, then QA (one FAIL, kept as `_r1`, then PASS) and the commit gates. The unit ran through the v2 tools; the mining and capability-ranking phases (1 and 1b) were also run as fourteen parallel miners plus the scout. Not re-run: the runtime-slice path (`slice N`), which this run did not touch.

## Quick start

See [docs/QUICKSTART.md](docs/QUICKSTART.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## Licence

Apache-2.0 (`LICENSE`, `NOTICE`). The factory skill is derived from revfactory/harness v2.1.0, also Apache-2.0.
