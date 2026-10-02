# Reference submodule licences

Reference repos are pinned read-only submodules used for pattern mining. Port
patterns and ideas; do not copy files verbatim unless the licence row permits it.

| submodule | upstream | licence | constraint |
|---|---|---|---|
| `autogpt` | Significant-Gravitas/AutoGPT | `classic/` MIT; `autogpt_platform/` Polyform Shield 1.0 | **Never copy from `autogpt_platform/`.** Only `classic/` (direct_benchmark, forge) may be ported. |
| `openhands` | OpenHands/agent-canvas | MIT | UI-only fork; no agent runtime present. |
| `dify` | langgenius/dify | Apache-2.0 **modified** | No multi-tenant SaaS without written authorisation; logo/copyright must stay. Port patterns (SSE, MCP client shape), not files. DAG engine is the external `graphon` package, not in-repo. |
| `crewai` | crewAIInc/crewAI | MIT | — |
| `deepseek_harness` | deepseek-ai/deepseek-harness | MIT | — |
| `revfactory_harness` | revfactory/harness | Apache-2.0 | Meta-skill source; installed copy lives at `~/.claude/skills/harness`. |
| `openharness` | OpenHarness (upstream org unverified; pinned fork at danielnguyenfinhub/OpenHarness) | MIT (`LICENSE`, "Copyright (c) 2025 OpenHarness Contributors") | Pinned 2026-10-02 at 9b2efd7. Port map: `references/portmaps/openharness-9b2efd7.md`. |

All pins point at forks under `github.com/danielnguyenfinhub`. Update a pin by
`git -C references/<name> checkout <sha>` then committing the gitlink.
