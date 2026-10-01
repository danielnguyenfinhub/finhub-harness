# Boundary checklist

For each slice, check every row whose "applies from" slice ≤ N. Record side A and side B shapes in the report's boundary table. A row is a match only if names, types, optionality and error shape all agree.

## Core boundaries (every slice from 1)

| # | boundary | side A — open | side B — open | what must agree |
|---|---|---|---|---|
| B1 | Tool schema ↔ loop call site | `ToolSpec.params` in the tool module | where `loop.py` builds `ToolCall.args` / validates | arg names, types, required vs optional |
| B2 | Loop ↔ LLM protocol | `LLM` Protocol signature | `FakeLLM` in tests and any real provider | method name, param order, return type (`Turn`) |
| B3 | Tool result ↔ message history | what a tool returns | how the loop appends it (role, call id pairing) | every tool call has exactly one result with the same id |
| B4 | CLI ↔ test | `cli.py` argv parsing and printed output | test invoking CLI (subprocess or `main([...])`) | argv form, stdout text incl. trailing newline, exit code |
| B5 | Design interface ↔ code | Interfaces block in `02_strategy-architect_slices.md` | actual signatures in `src/` | names, params, return types (deviations must be listed in builder report) |
| B6 | Error shape | how the slice reports errors (exception type or error result) | tests asserting them; CLI printing them | same type/message contract; CLI shows a human message, not a traceback |

## Slice-specific boundaries

| applies from | boundary | side A | side B | what must agree |
|---|---|---|---|---|
| 2 | Token estimate ↔ compaction threshold | `estimate()` units | threshold constant / config | both in tokens (len//4), not chars |
| 2 | Pruned tool result ↔ history pairing | pruner output | loop history | call/result pairs remain balanced after clipping |
| 3 | Safety check ↔ tool executor | `safety.check(cmd \| path)` return | call site before execution | check runs before every exec/file op; block = no side effect |
| 3 | Workspace root ↔ path resolution | `Workspace.root` | containment check | resolved absolute paths, symlinks resolved, case on Windows |
| 4 | Router profile ↔ model id | profile→provider/model map | callers requesting a profile | profile names identical; unknown profile → explicit error |
| 5 | Checkpoint writer ↔ reader | serialised dataclass fields | resume loader | same field set; version field present |
| 6 | DAG node spec ↔ executor | node declaration | `TopologicalSorter` input | node ids, deps; cycle → explicit error |
| 7 | Message envelope ↔ queue consumers | message dataclass | each agent's handler | sender/recipient/body fields |
| 8 | Sandbox policy ↔ docker args | policy mode enum | `docker run` arg builder | `read-only` → `:ro` mount; no `--privileged` |
| 9 | MCP tool list ↔ loop ToolSpec | MCP `list_tools` mapping | `ToolSpec` | JSON schema → params mapping lossless for required fields |
| 10 | SSE event ↔ client | event name/data format | test client parsing | `event:` / `data:` lines; PING while idle |
| 11 | Verifier result ↔ runner report | verifier return | report aggregation | pass/fail + reason; quant guardrail checks present (see adversarial-audit quant-guardrails.md) |

## Compliance sweep (every slice)

Grep `src/` and `tests/` for patterns that must not appear in fixtures or code:

| pattern | example regex |
|---|---|
| email addresses | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` (allow `example.com`/`example.org`) |
| AU mobile numbers | `\b04\d{2}\s?\d{3}\s?\d{3}\b` |
| API keys / tokens | `sk-[A-Za-z0-9]{20,}`, `ghp_[A-Za-z0-9]{20,}`, `Bearer [A-Za-z0-9._-]{20,}` |
| UUID-like ids in fixtures | `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` (flag for manual check) |

Any hit outside obvious synthetic placeholders → defect.
