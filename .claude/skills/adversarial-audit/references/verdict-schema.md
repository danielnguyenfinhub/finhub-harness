# Verdict schema

File: `_workspace/02_adversarial-risk-judge_verdict.md` for runtime slices (overwritten each round), or `_workspace/02_adversarial-risk-judge_<item-id>_r<k>.md` for one adoption (one file per round, never overwritten). First line is always the totals so the orchestrator can gate on it without parsing. The round field reads `round k/3`, or `round 4 (authorised)` and later when the launch prompt records Daniel's authorisation.

```markdown
TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 1 — round 2/3

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

## Escalation

(only when round 3/3 and REJECTED > 0)

| id | judge position | architect position |
|---|---|---|
| A4 | cited line is imports | "file-level citation should suffice" |
```

## Verdict values

| value | meaning | builder may implement? |
|---|---|---|
| UPHELD | cited lines plainly support the claim | yes |
| REJECTED | wrong line/function, out-of-bounds, licence-blocked, or guardrail fail | no |
| UNVERIFIED | cannot confirm (missing file, ambiguous) | only behind a test that fails if the assumption is wrong |

Guardrail cell values: `PASS <how>`, `REJECTED <why>`, `N/A <why>`. A REJECTED guardrail counts toward the REJECTED total.

## Message to architect (SendMessage body)

```
TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 1 — round 2/3
REJECTED A4: cites imports; PING emission is at streaming_utils.py:61
UNVERIFIED A7: llm.py:210 is a 200-line function; cite the routing line
GUARDRAIL slice 11 G2: shorts have no borrow cost
```

When REJECTED = 0, send `clean` with the totals line.
