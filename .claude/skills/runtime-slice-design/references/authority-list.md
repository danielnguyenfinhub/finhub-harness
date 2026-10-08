# Authority List contract

The Authority List is the last section of `_workspace/02_strategy-architect_slices.md`. It is the only part the adversarial-risk-judge audits, so it must stand alone: a reader with no chat history opens each cited line and decides whether it supports the claim.

## Format

```markdown
## Authority List

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | The loop ends a run when a model turn contains no tool calls | references/deepseek_harness/packages/core/agent-loop/src/agent.ts:88 | 1 |
| A2 | Token count is estimated as character length // 4 | references/deepseek_harness/packages/llm/token-meter/src/estimate.ts:3 | 2 |
| A3 | Containment is checked on the resolved absolute path, not the raw input | references/deepseek_harness/packages/fs/fs-sandbox/src/containment.ts:10 | 3 |
| A4 | SSE stream emits a PING event while idle | references/dify/api/core/app/apps/streaming_utils.py:30 | 10 |
| A5 | Regex command denylist (`rm -rf /`, fork bomb, `mkfs`) | NET-NEW — spec requirement; no reference implements a denylist (see D-gap in deepseek_harness port map) | 3 |
```

Line numbers above are illustrative; real rows must cite lines opened during this design.

## Rules

1. **Short form:** `claim → references/<submodule>/<path>:<line>`. One claim, one primary line. A second line may be added after `;` only if the claim genuinely spans two places.
2. **Evidence must be inside `references/`.** No URLs, no package docs, no "commonly known". Anything else is `NET-NEW — <reason>`.
3. **Claims are falsifiable.** "Uses a loop" is not a claim; "ends the run when a turn has no tool calls" is.
4. **One claim per behaviour the builder will rely on.** If the builder would write a test for it, it needs a row.
5. **Licence-clean.** No `references/autogpt/autogpt_platform/**`. dify rows describe a pattern, not code to copy.
6. **Stable ids.** Never renumber across revisions; append new ids, mark withdrawn ones `WITHDRAWN` in the claim column.
7. **Quant claims** (fees, slippage, borrow cost, look-ahead, survivorship, train/test split) appear as rows too, even when `NET-NEW`, so the judge can match them to the guardrail table.

## How the judge reads it

The judge opens each `evidence` path at the line (±5 lines) and rules:

| verdict | when |
|---|---|
| UPHELD | the cited lines plainly do what the claim says |
| REJECTED | the lines do something else, the path/line is wrong, evidence is outside `references/`, or licence-blocked |
| UNVERIFIED | file missing / submodule not checked out / ambiguous without reading beyond ±5 lines |

A verdict is about the design file as it was read. The verdict's `CANDIDATE:` line names that file by content, and an edit made afterwards makes every row of the verdict stale, UPHELD rows included; the orchestrator runs `candidate_id.py check` on the verdict before a builder starts, and a stale verdict sends the design back for a new round. Rows carried forward unchanged are named on the verdict's `CARRIED:` line. (adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0))

`NET-NEW` rows are not rejected for lacking a citation; the judge checks only that the reason is stated and that no reference actually contradicts it.
