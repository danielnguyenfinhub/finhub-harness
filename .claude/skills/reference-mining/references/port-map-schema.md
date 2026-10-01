# Port map schema

One file per submodule: `_workspace/01_reference-miner_{submodule}_portmap.md`. Exact structure below. Values in the example are illustrative placeholders — the miner must replace every one with a line it actually opened.

```markdown
# Port map — deepseek_harness

- Submodule: references/deepseek_harness
- Pinned SHA: b274e89591
- Licence: MIT (see licence-rules.md row `deepseek_harness`)
- Mined: 2026-10-01 19:40 AEST
- Status: COMPLETE            # COMPLETE | PARTIAL — stopped at <path> | EMPTY

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| D1 | 1 | ReAct loop: preStep, model turn, tool step; ends when turn has no tool calls | references/deepseek_harness/packages/core/agent-loop/src/agent.ts:42 | adapt | TS → Python; keep stop condition |
| D2 | 2 | Token estimate = chars // 4 | references/deepseek_harness/packages/llm/token-meter/src/estimate.ts:3 | adapt | one-liner; no tokenizer dep |
| D3 | 3 | Path containment check after resolve | references/deepseek_harness/packages/fs/fs-sandbox/src/containment.ts:10 | adapt | must resolve symlinks first |

## Do not port

| source | reason |
|---|---|
| references/deepseek_harness/packages/ui/** | UI, out of scope |

## Gaps

- No regex command denylist in sandbox-policy (searched: `deny`, `rm -rf`, `blocked`). Slice 3 denylist is net-new.
```

## Column rules

| column | allowed values / rule |
|---|---|
| `id` | submodule initial + number: `A` autogpt, `O` openhands, `Y` dify, `C` crewai, `D` deepseek_harness, `R` revfactory_harness |
| `slice` | 1–12, or `meta` |
| `pattern` | ≤20 words, own words |
| `source` | `references/<submodule>/<path>:<line>`, forward slashes, opened this session |
| `port as` | `adapt` (MIT/Apache, rewrite in Python) · `pattern` (idea only, no structural copy — always for dify) · `reference` (read for understanding, nothing ported) |
| `notes` | gotchas the architect must know; ≤15 words |

## JSON form (optional, for tooling)

```json
{
  "submodule": "crewai",
  "sha": "fbcf2de39",
  "status": "COMPLETE",
  "findings": [
    {"id": "C1", "slice": 7, "pattern": "Delegate-work tool passes task + context to a named coworker",
     "source": "references/crewai/src/crewai/tools/agent_tools/delegate_work_tool.py:15",
     "port_as": "adapt", "notes": "fallback when message bus absent"}
  ],
  "do_not_port": [],
  "gaps": ["No message bus; delegation is tool-call based"]
}
```
