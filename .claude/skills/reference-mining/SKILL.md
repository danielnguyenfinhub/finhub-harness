---
name: reference-mining
description: "Extracts a licence-checked port map from one pinned reference submodule under references/ (autogpt, openhands, dify, crewai, deepseek_harness, revfactory_harness): which path:line holds an agent loop, compaction, token meter, path containment, sandbox policy, DAG/checkpoint, delegation, SSE streaming, MCP client or eval runner pattern, and whether it may be ported. Use for: mine references, build a port map, re-mine dify, where does deepseek do compaction, what can we port from crewai, update the port map. Not for reading arbitrary third-party repos outside references/ or for general library docs questions."
---

# Reference Mining

Produce one port map per submodule so the architect can cite exact lines and the judge can re-open them. The port map is the only bridge between six large repos and a small design — a wrong line number here becomes a REJECTED claim two phases later, so precision beats coverage.

## Steps

1. **Confirm the submodule is present.** List `references/<submodule>/`. If empty or only `.gitkeep`, stop and return a port map with an empty Findings table and a Gaps line naming the path. Do not guess contents from memory of the upstream project.
2. **Read the licence rules** in `references/licence-rules.md` and note the constraint row for this submodule before you look at code. Licence decides what the "Port as" column may say.
3. **Locate targets.** Search for the patterns the slice order needs (see table below). Use Grep/Glob to find candidates, then open the specific region. Read the actual lines; record the first line of the function/class.
4. **Record findings** in the schema from `references/port-map-schema.md`. One row per pattern unit (a function or class), not per file.
5. **Record exclusions and gaps.** Anything licence-blocked goes under **Do not port**. Any target pattern that this submodule does not contain goes under **Gaps** with what you searched for.
6. **Return the map** as your final message (you run as Explore — read-only; the orchestrator saves it).

## Target patterns by slice

| Slice | Pattern | Likely source |
|---|---|---|
| 1 | agent loop: preStep → turn → step; stop when no tool calls | `deepseek_harness/packages/core/agent-loop/` |
| 2 | token estimate (len//4), threshold compaction, tool-result pruning | `deepseek_harness/packages/llm/token-meter/`, `packages/compaction/compaction-basic/` |
| 3 | path containment (`isPathUnder`), sandbox policy modes, upload path checks | `deepseek_harness/packages/fs/fs-sandbox/`, `packages/sandbox/sandbox-policy/`, `openhands/src/api/workspace-upload-path.ts` |
| 4 | provider/model routing by profile | `deepseek_harness/packages/llm/`, `crewai` `llm.py` |
| 5–6 | checkpoint per step, limits/observability layers around an executor | `dify/api/core/workflow/` (pattern only) |
| 7 | delegation / ask-question tools, task context passing | `crewai` `tools/agent_tools/` |
| 8 | container ingress/entrypoint pattern | `openhands/docker/` |
| 9 | MCP client shape | `dify/api/core/mcp/mcp_client.py` (pattern only) |
| 10 | SSE ping/idle streaming | `dify/api/core/app/apps/streaming_utils.py` (pattern only) |
| 11 | benchmark harness/runner/evaluator | `autogpt/classic/direct_benchmark/` (MIT only) |
| meta | harness/skill/agent conventions | `revfactory_harness/` |

Paths above are starting points from the plan's exploration, not facts — verify each one exists before citing it.

## Rules that prevent downstream rejections

- Cite `references/<submodule>/<path>:<line>` exactly as it exists on disk, forward slashes, line = first line of the unit.
- Never list `references/autogpt/autogpt_platform/**` as a source. It is Polyform Shield.
- For `dify`, the "Port as" value is always `pattern` — modified Apache-2.0 forbids treating its files as copy sources for a SaaS-capable runtime.
- Describe what the code does in your own words in ≤20 words; do not paste code blocks longer than 5 lines.
- Mark language: the runtime is Python; TypeScript sources are ports of the idea, not the syntax.

## On re-run

If the orchestrator passes a prior port map, read it first, re-verify only the rows or gaps it flags, and return the full map with only those parts changed. Re-verifying everything wastes the budget and can introduce churn the architect then has to chase.
