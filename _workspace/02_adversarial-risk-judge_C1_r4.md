TOTALS: UPHELD 17 / REJECTED 2 / UNVERIFIED 0 — round 4 (authorised)

# Adversarial verdict: adoption C1 (connector preflight), revision 3

- Audited file: _workspace/02_strategy-architect_C1.md (revision 3): A8, mutation rows M1 and M1b (:374-375), `## Changes in revision 3` (:5-28)
- Audited: 2026-10-03
- Extra round authorised by Daniel: 2026-10-03
- Prior verdict: _workspace/02_adversarial-risk-judge_C1_r3.md (UPHELD 16 / REJECTED 0 / UNVERIFIED 0)
- Re-audited this round: A8 (CHANGED r3), M1, M1b, Changes in revision 3. A1-A7 and A9-A16 carried forward from r3 unchanged.

## Claims

| id | verdict | cited | found (own check) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | agent_definitions.py:110; :962 | carried from r3 | — |
| A2 | UPHELD | agent_definitions.py:110 | carried from r3 | — |
| A3 | UPHELD | NET-NEW | carried from r3 | — |
| A4 | UPHELD | agent_definitions.py:964 | carried from r3 | — |
| A5 | UPHELD | NET-NEW | carried from r3 | — |
| A6 | UPHELD | NET-NEW | carried from r3 | — |
| A7 | UPHELD | NET-NEW | carried from r3 | — |
| A8 | UPHELD | NET-NEW; P-2 absent case + M1 | unmutated `c1-fixture/absent.jsonl`: agent_calls=0, result = exact stop line. M1 `c1-m1/absent_recipe.jsonl`: agent_calls=1 (main thread), Missing connector count 0 in result and in whole stream, tools `Skill Agent ToolSearch`. `c1-m1/absent_nobypass.jsonl`: agent_calls=1, Missing 0, tools `Skill Agent ToolSearch ToolSearch` | Verification can fail and the two outcomes are distinct and observable. Mutant copy diffed against `c1-fixture`: only item 4 (11 lines, table row `pinger \| fixture`) removed; `pinger.md` and `absent.json` byte-identical. The row's closing clause "M1b is an equivalent mutant" is false (see M1b) and must be corrected with M1b, but A8 does not rest on it. |
| A9 | UPHELD | NET-NEW | carried from r3 | — |
| A10-A16 | UPHELD (7) | as r3 | carried from r3 | — |
| M1 | UPHELD | design :374 | as A8 above, 2/2 killed | Killed by the absent-case table at :315 (any Agent call; no stop line). |
| M1b | REJECTED | design :375 "QA saw it survive 2/2"; "item 4's first line, the table and the presence rule already make the model stop" | (a) QA's M1b was never applied. `qa_c1b/fxm1b/.claude/skills/fixture-orchestrator/SKILL.md` is byte-identical to `qa_c1b/fx/...` (`diff` empty). The bullet is indented (`   - Claude Code:`), so QA's `grep -v '^- Claude Code:'` matched 0 lines; `grep -c 'Claude Code:'` on the "mutant" = 1, and the bullet text is in the skill content loaded in `m1r1.jsonl`. QA's "survived 2/2" is two runs of the unmutated fixture, which is why the exact bullet wording was printed. (b) Judge ran the mutant correctly applied (`sed '/^ *- Claude Code:/d'`, bullet count 1 -> 0, `Missing connector` count in orchestrator 0), same P-2 absent command with `ENABLE_TOOL_SEARCH=true … --permission-mode bypassPermissions`, 2 runs: agent_calls=0 both; `Missing connector` in result 0 both; both results fall through to the chat/Cowork branch and ask "attach / continue without / stop". | Not an equivalent mutant. On Code, deleting the bullet turns the hard stop into warn-and-ask, the behaviour Design item 5 vs 6 and A6 forbid on Code. It is KILLED by the absent-case PASS rule at :315 (result must contain `Missing connector fixture for agent pinger` and `Nothing was started`). Fix: make M1b an ordinary killed mutant "caught by case 1 (absent): no `Missing connector … Nothing was started` line; result asks instead", record the correct deletion command (`sed '/^ *- Claude Code:/d'`), drop "QA saw it survive 2/2" and "behaviour is the same", and drop the A8 clause calling M1b equivalent. |
| R3-changes | REJECTED | design :9 "conflicted with QA's finding that the stop line still appears without the bullet"; :12 same M1b reasoning | as M1b | The premise is wrong: QA never ran without the bullet. The coordinator's interim M1 expectation (bullet deletion -> stop line missing) was correct and is killed 2/2 in the judge's runs. The new M1 (whole item 4) can stay as an extra mutant; the section must stop citing QA's survival as evidence. |

### Check (3): grep for 'M1'

Hits at :9, :11, :12, :28, :374, :375, :405. None restates the old bullet-only expectation as a current expectation; :9 mentions it historically. Under the fix above, :9, :12, :375 and the last sentence of :405 change. :370 ("each must turn a PASS into a FAIL") becomes consistent again once M1b is a killed mutant.

### Note for the orchestrator on QA's report

`_workspace/03_boundary-qa_C1.md` gate row "mutant M1 (new expectation)" says "count of that bullet 1 -> 0". The pattern `^- Claude Code:` counts 0 before and after; the bullet is indented. QA's Defect 1 ("M1 survives") was therefore produced by a no-op mutation. QA should re-run M1b with an indentation-tolerant deletion and quote the before/after count with the same pattern.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C1 | N/A: prose-only plugin change plus deletion of empty stubs; no pricing, returns, backtest, eval or verifier logic | N/A | N/A | N/A | N/A | N/A |

## Escalation

Round 4 is the authorised extra round and REJECTED > 0. No authorisation for round 5 is recorded; escalate to Daniel.

| id | judge position | architect position |
|---|---|---|
| M1b | Correctly applied, the bullet deletion is killed 2/2 (no stop line; model asks attach/continue/stop on Code). QA's 2/2 survival came from a mutant that changed nothing. | "Equivalent mutant; item 4's first line, table and presence rule already make the model stop; QA saw it survive 2/2." |
| R3-changes | Same: the r3 rationale rests on QA's no-op run. | Same as M1b. |

Neither rejection affects the built prose or A8's 0-spawn property (0 Agent calls in all four judge/architect mutant-free and M1b runs). The fix is text-only in the design's mutation table and Changes section.

## Scratch work (outside the repo)

- `<scratchpad>/judge_c1r4/m1b/`: copy of `c1-fixture/.claude` and `absent.json`, bullet deleted with `sed '/^ *- Claude Code:/d'`; runs `r1.jsonl`, `r2.jsonl` (exit 0, stderr empty).
- Read only: `<scratchpad>/c1-m1/{absent_recipe,absent_nobypass}.jsonl` and its `.claude/`; `<scratchpad>/c1-fixture/`; `<scratchpad>/qa_c1b/{fx,fxm1b}/`.
