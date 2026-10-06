TOTALS: UPHELD 20 / REJECTED 0 / UNVERIFIED 0 — round 5 (authorised)

# Adversarial verdict: adoption C1 (connector preflight), revision 4

- Audited file: _workspace/02_strategy-architect_C1.md (revision 4): A8 (:412), mutation rows M1 (:381) and M1c (:382), withdrawn M1b, `## Changes in revision 4` (:5-20), `## Changes in revision 3` (:22-35)
- Audited: 2026-10-03
- Extra round authorised by Daniel: 2026-10-03 (round 5)
- Prior verdict: _workspace/02_adversarial-risk-judge_C1_r4.md (UPHELD 17 / REJECTED 2 / UNVERIFIED 0)
- Re-audited this round: A8, M1, M1c, M1b (withdrawal), R3-changes, R4-changes. A1-A7 and A9-A16 are carried forward as UPHELD.
- Count: 16 claims + M1 + M1c + R3-changes + R4-changes = 20. M1b is withdrawn and not counted.

## Claims

| id | verdict | cited | found (own check) | reason / correct location |
|---|---|---|---|---|
| A1-A7 | UPHELD (7) | as r4 | carried from r4 | — |
| A8 | UPHELD | NET-NEW; P-2 absent `agent_calls=0`, M1c, M1 (:412) | The citations are only the P-2 absent case, M1c (`agent_calls>=1`, no `Missing connector`, killed 2/2 r3) and M1 (stop line removed, killed 2/2 r4). The row has no "equivalent" clause. Own runs below: base gives 0 Agent calls and the stop line; M1c gives 1 Agent call | Both mutants can fail and are distinct. The verification is not vacuous. |
| A9-A16 | UPHELD (8) | as r4 | carried from r4 | — |
| M1 | UPHELD | :381 `sed -i '/^ *- Claude Code:/d'`, count 1 -> 0 (void if still 1); expects the stop line missing from case 1 | Own scratch copy: `grep -c '^ *- Claude Code:'` gave 1 before and 0 after. The diff removes exactly the indented bullet (line 18). Two runs in default mode (init `permissionMode=default`, no bypass): `agent_calls=0`, `missing_lines=0` in both; tools `Skill ToolSearch`. The results say "didn't run / preflight failed" (r1) and "How do you want to proceed? 1. Attach…" (r2). Neither has the stop line. Architect's `c1-m1b/absent_{1,2}.jsonl` (bypass mode): ac=0, miss=0 | Killed by the absent-case PASS rule at :315, which requires `Missing connector fixture for agent pinger` and `Nothing was started`. The before/after guard makes a no-op mutation like QA's detectable. |
| M1c | UPHELD | :382 delete all of item 4; `grep -c 'Connector preflight'` 1 -> 0; expects `agent_calls>=1` and no `Missing connector` | Own scratch copy: item 4 (fixture lines 11-21) deleted. `Connector preflight` count went 1 -> 0, and `Missing connector` count in the orchestrator is 0. One default-mode run: `agent_calls=1`, `missing_lines=0`, tools `Skill Agent ToolSearch×3`; `pinger` was spawned and reported no echo | Distinct from M1: M1 keeps 0 spawns and loses only the stop line, while M1c spawns. Its kill signature (an Agent call) differs from M1's (no stop line). |
| M1b | WITHDRAWN | — | `grep -n 'M1b'` finds only :9 "(M1b withdrawn)". No mutation row is left | The r4 rejection is resolved by withdrawal. Not counted. |
| R3-changes | UPHELD | :22-35 | :26 says that the r3 equivalent-mutant text "rested on a no-op QA mutation" and "is withdrawn in revision 4". The rest describes M1c's r3 simulation, consistent with the r4 check of `c1-m1/` | The false premise is no longer asserted; it is only recorded as withdrawn. |
| R4-changes | UPHELD | :5-20 | :11 correctly states that QA's `grep -v '^- Claude Code:'` missed the indented bullet, so the file was byte-identical (matches r4 finding on `qa_c1b/fxm1b`). :13-20 counts 1 -> 0 and 2 runs `agent_calls=0`, `missing_lines=0`, reproduced by me in default mode | The section matches the evidence. |

### Check (4): grep for 'M1' and 'equivalent'

- `equivalent`: :11 and :26 only. Both are withdrawal notes.
- `M1`: :9, :11 (via "bullet-level"), :20, :26, :28, :35, :381, :382, :412. None calls M1 or M1b equivalent.
- `surviv|no-op|QA saw|behaviour is the same`: only :11 ("survived" … "says nothing about it") and :26 ("no-op QA mutation"). Both are withdrawals.
- No sentence still relies on QA's no-op mutation.

### Control (unmutated fixture, default permission mode)

`judge_c1r5/base/b1.jsonl` and `b2.jsonl`: `agent_calls=0`, `missing_lines=1`, tools `Skill`. The result was exactly `Missing connector fixture for agent pinger. Attach or authorise it, then run again. Nothing was started.`

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C1 | N/A: prose-only plugin change plus deletion of empty stubs; no pricing, returns, backtest, eval or verifier logic | N/A | N/A | N/A | N/A | N/A |

## Note for the orchestrator

`_workspace/03_boundary-qa_C1.md` still records QA's no-op M1 result (r4 note). Any QA re-run should use the :381 command and quote the 1 -> 0 count.

## Scratch work (outside the repo)

`<scratchpad>/judge_c1r5/{base,m1,m1c}/`: fresh copies of `c1-fixture/.claude` and `absent.json`. Command: `ENABLE_TOOL_SEARCH=true claude -p "run the fixture harness" --strict-mcp-config --mcp-config absent.json --output-format stream-json --verbose` (default permission mode). Runs: `base/b{1,2}.jsonl`, `m1/r{1,2}.jsonl`, `m1c/c1.jsonl`; all exit 0 with empty stderr.
