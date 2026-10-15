# Verdict schema

File: `_workspace/02_adversarial-risk-judge_verdict.md` for runtime slices (overwritten each round), or `_workspace/02_adversarial-risk-judge_<item-id>_r<k>.md` for one adoption (one file per round, never overwritten). First line is always the totals so the orchestrator can gate on it without parsing. The second line is `CANDIDATE:` (from `candidate_id.py id --paths <design file> [<patch file>]`, both files when the design carries a patch, computed before the first claim and again before writing) and the third is `CARRIED:`, naming the rows reused unchanged from an earlier round and the candidate they were audited on (`-` when none); see `skills/finhub-harness/references/quality-gates.md` section 3-7. (adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0)) The round field reads `round k/3`, or `round 4 (authorised)` and later when the launch prompt records Daniel's authorisation. The lines of a verdict run TOTALS, CANDIDATE, CARRIED, RIGOR (the RIGOR line is line 4): `RIGOR:` is copied from the `Rigor:` line of the launch prompt (`quality-gates.md` section 3-10). (adapted from references/openrig/docs/reference/sdlc-conventions.md:23-24 (Apache-2.0))

```markdown
TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 1 — round 2/3
CANDIDATE: files:0f1e2d3c4b5a6978 n=1 excludes=- paths=_workspace/02_strategy-architect_slices.md
CARRIED: A1-A3 (text unchanged from round 1, audited on files:7a8b9c0d1e2f3a4b)
RIGOR: gated unit=master-finhub-unit/OR-S8 by=owner:daniel on=2026-10-14

# Adversarial verdict — slices revision 2

- Audited file: _workspace/02_strategy-architect_slices.md (revision 2)
- Audited: 2026-10-01 20:15 AEST
- Changed claims re-audited this round: A4, A7
- Extra round authorised by Daniel: 2026-10-01 (only on round 4 and later; copied from the launch prompt, omitted otherwise)

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | references/deepseek_harness/packages/core/agent-loop/src/agent.ts:88 | returns when `toolCalls.length === 0` | — |
| A4 | REJECTED | references/dify/api/core/app/apps/streaming_utils.py:30 | import block | PING emission is at :61 in the same file |
| A7 | UNVERIFIED | references/crewai/src/crewai/llm.py:210 | file present, function spans 200 lines | ambiguous without reading beyond ±5 |
| A9 | UPHELD | NET-NEW — spec requirement | — | reason stated; no contradicting reference |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 1 | N/A no pricing | N/A | N/A | N/A | N/A | N/A |
| 11 | PASS 5 bps default | REJECTED shorts free | PASS 2 bps | PASS t-1 features | PASS disclosed | PASS walk-forward |

## Cost statement

| row | verdict | additions found | reason |
|---|---|---|---|
| cost statement | UPHELD | 1 (slice 3 path denylist) | scenario, cause and cost to others each name a case |

## Escalation

(only when round 3/3 and REJECTED > 0)

| id | judge position | architect position |
|---|---|---|
| A4 | cited line is imports | "file-level citation should suffice" |
```

Each REJECTED row, in the claims table or in a guardrail cell, carries one cause tag in the same row, set by rule (`skills/finhub-harness/references/quality-gates.md` section 3-8, rule T3): `cause: judgment-gap` when the cited file is one the design lists as an input and the architect could read it; `cause: context-gap` when the needed file was not routed or is not in `references/`. Doubt decides whether a claim is rejected, never the cause. The `REJECTED n` on the `TOTALS:` line counts the table cells in which the word REJECTED appears, case ignored, after `*`, `_`, backticks and `~` are read as spaces or as nothing, after HTML entities and tags are resolved, and after format and combining characters are dropped (quality-gates 3-8, T3). A row needs no leading pipe to be counted, and `✗ REJECTED`, `**Verdict:** REJECTED`, `UNVERIFIED / REJECTED` and `&#82;EJECTED` all count. A verdict table is not written inside a code fence: a fenced table row is refused. A cell that says "rejected" in another sense also counts, so it is reworded. `finding_tags.py check` refuses a row without exactly one tag or a count that differs. (adapted from references/openrig/docs/reference/wave-sdlc.md:58-62 (Apache-2.0))

## Verdict values

| value | meaning | builder may implement? |
|---|---|---|
| UPHELD | cited lines plainly support the claim | yes |
| REJECTED | wrong line/function, out-of-bounds, licence-blocked, or guardrail fail | no |
| UNVERIFIED | cannot confirm (missing file, ambiguous) | only behind a test that fails if the assumption is wrong |

Guardrail cell values: `PASS <how>`, `REJECTED <why>`, `N/A <why>`. A REJECTED guardrail counts toward the REJECTED total.

The `cost statement` row is ruled once per design, in its own table: `UPHELD`, `REJECTED <why>` or `N/A <what was read>` (`skills/finhub-harness/references/quality-gates.md` section 3-11). A REJECTED cell counts toward the REJECTED total and carries one cause tag in its row, like any other REJECTED cell. The reason cell avoids the word "rejected" when it means something else, because the count reads every cell. (adapted from references/openrig/CONTRIBUTING.md:29-31 (Apache-2.0))

## Message to architect (SendMessage body)

```
TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 1 — round 2/3
REJECTED A4: cites imports; PING emission is at streaming_utils.py:61
UNVERIFIED A7: llm.py:210 is a 200-line function; cite the routing line
GUARDRAIL slice 11 G2: shorts have no borrow cost
COST STATEMENT: slice 3 path denylist has no cost-to-others cell
```

When REJECTED = 0, send `clean` with the totals line.
