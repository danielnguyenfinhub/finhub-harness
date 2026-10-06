TOTALS: UPHELD 15 / REJECTED 1 / UNVERIFIED 0 — round 2/3

# Adversarial verdict: adoption C1 (connector preflight), revision 1

- Audited file: _workspace/02_strategy-architect_C1.md (revision 1): `## Authority List` plus `## Changes in revision 1`
- Audited: 2026-10-03
- Prior verdict: _workspace/02_adversarial-risk-judge_C1_r1.md (UPHELD 14 / REJECTED 0 / UNVERIFIED 2)
- Re-audited this round: A7, A9 (both CHANGED r1) and the SKILL.md length dispute. All other rows carried forward unchanged.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | agent_definitions.py:110; :962 | carried from r1 | — |
| A2 | UPHELD | agent_definitions.py:110 | carried from r1 | — |
| A3 | UPHELD | NET-NEW | carried from r1 | The r1 note still applies and is unchanged: "chat/Cowork do not ship agent files" overstates §3b:124. The first reason alone carries the claim. |
| A4 | UPHELD | agent_definitions.py:964 | carried from r1 | — |
| A5 | UPHELD | NET-NEW (departs from :965) | carried from r1 | — |
| A6 | UPHELD | NET-NEW (departs from :970-975) | carried from r1 | — |
| A7 | UPHELD | NET-NEW, backed by `skills/finhub-harness/references/surfaces.md` §3b | :124 `agents/*.md custom types \| used \| believed not applicable (unverified) \| uncommon; unverified` | Reworded to "may not ship agent files", quoting the row's own hedges. Design § Behaviour item 2 (:62) matches. P-3 table-row grep and E3 can fail. Resolves the r1 UNVERIFIED. |
| A8 | UPHELD | NET-NEW | carried from r1 | r1 QA note on M1 still applies |
| A9 | REJECTED | NET-NEW, verification P-2 present case | see below | The verification cannot fail in the scenario it exists to catch, so it is vacuous on the A9 assumption. |
| A10 | UPHELD | NET-NEW, surfaces.md:139 | carried from r1 | — |
| A11 | UPHELD | NET-NEW, surfaces.md:81 | carried from r1 | — |
| A12 | UPHELD | NET-NEW, orchestrator-template.md:82/:188/:247 | carried from r1 | — |
| A13 | UPHELD | references/openharness/LICENSE:1 | carried from r1 | — |
| A14 | UPHELD | NET-NEW (repo fact) | carried from r1 | — |
| A15 | UPHELD | NET-NEW (repo fact) | carried from r1 | — |
| A16 | UPHELD | NET-NEW (repo fact) | carried from r1 | — |

### A9 detail

The architect's rule (Authority List A9 and P-2 table rows 2 and 3) says:

- FAIL if `agent_calls=0` or a "Missing connector" line appears **while `fixture_was_deferred>=1`**.
- If `fixture_was_deferred=0`, the result is untested and never PASS.

`fixture_was_deferred` counts ToolSearch results that returned a `mcp__fixture__*` match. That number is at least 1 only if some agent actually called ToolSearch for a fixture tool. In the failure A9 targets, the preflight does not count deferred names, so the Code branch stops in Step 0 ("make no further calls"). Nobody searches, `fixture_was_deferred=0`, and the rule files the run as **untested**, not FAIL. The FAIL branch is reachable only if something searches for the fixture before stopping, and the Code branch never tells anyone to.

Evidence:

1. **Synthetic streams** (`<scratchpad>/c1r2/{fail,pass}.jsonl`, jq 1.7, run with the design's exact commands):
   - Preflight-stops stream: `agent_calls=0`, `toolsearch_in_init=true`, `fixture_was_deferred=0`, and the result says `Missing connector fixture for agent pinger … Nothing was started.` Under the A9 rule this is untested.
   - Pass stream: `1 / true / 1`.
   - The jq expressions themselves are syntactically correct. That includes a string-valued `tool_use_result`, which `.matches?` skips.
2. **The architect's own simulation** (`<scratchpad>/c1sim/run_true.jsonl`, `ENABLE_TOOL_SEARCH=true`):
   - Init lists `ToolSearch`, `mcp__fixture__echo` and `mcp__fixture__fail`, so the fixture tools were deferred.
   - No ToolSearch call was made, so `fixture_was_deferred=0`.
   - `call_true.jsonl` gives 1 only because the model was told to call echo.
   - So the counter measures "a fixture schema was loaded later", not "the fixture was deferred at start". On the failure path it is always 0.
3. **The P-2 table contradicts itself.** Take a run with `agent_calls=0`, a Missing-connector line and `fixture_was_deferred=0`. Row 2's FAIL column (no gate) calls it FAIL. Row 3 and the Authority List call it untested. The Authority List wording is the one the builder and QA will follow.

What would make the check able to fail (for the architect; not a judge citation):

- Take the deferral proof from the run's starting condition, not from a later load. That means `toolsearch_in_init=true` together with the fixture names in init, under `ENABLE_TOOL_SEARCH=true`. The architect's own `run_true` against `run_false` shows that pair separates the deferred mode from the eager one.
- Then FAIL whenever `toolsearch_in_init=true` and (`agent_calls=0` or a Missing-connector line), whatever `fixture_was_deferred` reads.
- Keep `fixture_was_deferred>=1` only as a corroborating condition for PASS.
- Record untested only when `toolsearch_in_init=false`.

## SKILL.md length dispute

| check | result |
|---|---|
| Baseline `wc -l < skills/finhub-harness/SKILL.md` | 194 (file ends in a newline) |
| Anchors | :91 `- Body: role, working principles…`, :112 `- **Step 0 context check**: …`, :177 `- [ ] Orchestrator Step 0 distinguishes…`, all exact |
| E1/E2/E3 blocks pulled from the design's fenced ```markdown blocks | 1 / 1 / 1 lines |
| Inserted bottom-up after :177, :112, :91 into `<scratchpad>/c1r2/SKILL.md` | `wc -l` = **197**; new lines land at :92, :114, :180 |
| Proof row (design :197) | `197 (194 + 3 …)`, consistent with the simulation |

The architect is right. 197 is correct. The r1 verdict also recorded "194 → 197 OK", and no 198 appears in r1, so nothing in r1 needs undoing.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C1 | N/A: prose-only plugin change plus deletion of empty stubs; no pricing, returns, backtest, eval or verifier logic | N/A | N/A | N/A | N/A | N/A |

## Scratch work (outside the repo)

- `<scratchpad>/c1r2/SKILL.md`: the E1-E3 insertion simulation.
- `<scratchpad>/c1r2/fail.jsonl` and `pass.jsonl`: synthetic stream-json runs through the design's P-2 jq commands.
- Read only, not modified: the architect's `<scratchpad>/c1sim/{run_true,run_false,call_true}.jsonl`.
