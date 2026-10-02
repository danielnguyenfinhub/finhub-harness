# Licence rules for reference submodules

Source of truth: `references/LICENSES.md` at the repo root. This file restates it for the miner and adds the "port as" mapping. If the two ever disagree, `references/LICENSES.md` wins — flag the drift in Gaps.

Reference repos are pinned read-only submodules used for pattern mining. Port patterns and ideas; do not copy files verbatim unless the licence row permits it.

| submodule | upstream | licence | constraint | allowed `port as` |
|---|---|---|---|---|
| `autogpt` | Significant-Gravitas/AutoGPT | `classic/` MIT; `autogpt_platform/` Polyform Shield 1.0 | **Never copy from `autogpt_platform/`.** Only `classic/` (direct_benchmark, forge) may be ported. | `classic/**`: adapt · `autogpt_platform/**`: none — list under Do not port |
| `openhands` | OpenHands/agent-canvas | MIT | UI-only fork; no agent runtime present. | adapt |
| `dify` | langgenius/dify | Apache-2.0 **modified** | No multi-tenant SaaS without written authorisation; logo/copyright must stay. Port patterns (SSE, MCP client shape), not files. DAG engine is the external `graphon` package, not in-repo. | pattern only |
| `crewai` | crewAIInc/crewAI | MIT | — | adapt |
| `deepseek_harness` | deepseek-ai/deepseek-harness | MIT | — | adapt |
| `revfactory_harness` | revfactory/harness | Apache-2.0 | Meta-skill source; installed copy lives at `~/.claude/skills/harness`. | adapt / reference |
| `openharness` | OpenHarness (upstream org unverified; pinned fork at danielnguyenfinhub/OpenHarness) | MIT (`LICENSE`, "Copyright (c) 2025 OpenHarness Contributors") | Pinned 2026-10-02 at 9b2efd7. Port map: `references/portmaps/openharness-9b2efd7.md` (40 rows). | adapt |

All pins point at forks under `github.com/danielnguyenfinhub`.

## What each `port as` means in practice

- **adapt** — rewrite the idea in Python under `src/master_finhub/`; a one-line source comment (`# adapted from references/<submodule>/<path>:<line> (MIT)`) is enough attribution for MIT. Apache-2.0 adaptations keep the same comment and must not remove upstream notices if any text is reused.
- **pattern** — the design idea only (e.g. "send a PING every N seconds while idle"). Write it fresh; the resulting code must not mirror the source's structure, names or comments. Always the case for dify.
- **reference** — read to understand; nothing ported.

## Hard stops

1. Any path under `references/autogpt/autogpt_platform/` → Do not port, regardless of how useful.
2. Any dify file → never `adapt`, never verbatim.
3. A submodule with no licence file at its root → report in Gaps and treat as `reference` until Daniel confirms.
