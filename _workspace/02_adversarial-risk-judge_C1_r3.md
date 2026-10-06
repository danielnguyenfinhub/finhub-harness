TOTALS: UPHELD 16 / REJECTED 0 / UNVERIFIED 0 — round 3/3

# Adversarial verdict: adoption C1 (connector preflight), revision 2

- Audited file: _workspace/02_strategy-architect_C1.md (revision 2): `## Authority List` plus `## Changes in revision 2`
- Audited: 2026-10-03
- Prior verdicts: _workspace/02_adversarial-risk-judge_C1_r1.md (UPHELD 14 / REJECTED 0 / UNVERIFIED 2); _workspace/02_adversarial-risk-judge_C1_r2.md (UPHELD 15 / REJECTED 1 (A9) / UNVERIFIED 0)
- Re-audited this round: A3 and A9 (both CHANGED r2). All other rows carried forward unchanged from r2.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | agent_definitions.py:110; :962 | carried from r2 | — |
| A2 | UPHELD | agent_definitions.py:110 | carried from r2 | — |
| A3 | UPHELD | NET-NEW; `SKILL.md:91`, `surfaces.md` §3b | `skills/finhub-harness/SKILL.md:91` ends "there is no `skills:` frontmatter field"; `surfaces.md:124` `agents/*.md custom types \| used \| believed not applicable (unverified) \| uncommon; unverified` | The r1/r2 note is resolved: the claim now says "may not ship agent files (§3b: unverified)", which matches the row's hedges. Reason stated; P-3 grep `^## Required connectors` >= 1 can fail. |
| A4 | UPHELD | agent_definitions.py:964 | carried from r2 | — |
| A5 | UPHELD | NET-NEW (departs from :965) | carried from r2 | — |
| A6 | UPHELD | NET-NEW (departs from :970-975) | carried from r2 | — |
| A7 | UPHELD | NET-NEW, surfaces.md §3b | carried from r2 | — |
| A8 | UPHELD | NET-NEW | carried from r2 | r1 QA note on M1 still applies |
| A9 | UPHELD | NET-NEW, verification P-2 present case scored by the design's rule (design :271-279) | see A9 detail | The verification can now fail in the scenario it exists to catch. All three required behaviours were reproduced on judge-built synthetic streams. |
| A10 | UPHELD | NET-NEW, surfaces.md:139 | carried from r2 | — |
| A11 | UPHELD | NET-NEW, surfaces.md:81 | carried from r2 | — |
| A12 | UPHELD | NET-NEW, orchestrator-template.md:82/:188/:247 | carried from r2 | — |
| A13 | UPHELD | references/openharness/LICENSE:1 | carried from r2 | — |
| A14 | UPHELD | NET-NEW (repo fact) | carried from r2 | — |
| A15 | UPHELD | NET-NEW (repo fact) | carried from r2 | — |
| A16 | UPHELD | NET-NEW (repo fact) | carried from r2 | — |

### A9 detail

**Rule under test.** I took the rule from the design's P-2 fenced block (design :271-279), not from the architect's script. `diff` against `<scratchpad>/a9_verdict.sh` minus its two header lines: identical. The deferral init line in my streams is the real init event from the live `c1-fixture/present.jsonl`. That event lists `ToolSearch`, `mcp__fixture__echo` and `mcp__fixture__fail` among 199 tools. Everything after the init line is synthetic and was written by me (`<scratchpad>/c1r3/t*.jsonl`).

| # | stream (judge-built) | deferred_from_start / agent_calls / missing / fixture_was_deferred | verdict | exit | required |
|---|---|---|---|---|---|
| 1 | deferred init, then the `Missing connector …` text and result; no ToolSearch, no Agent | true / 0 / 1 / 0 | FAIL | 1 | FAIL: met |
| 1b | as 1, but a ToolSearch call returns a fixture `tool_reference` before the stop | true / 0 / 1 / 1 | FAIL | 1 | FAIL: met (independent of `fixture_was_deferred`) |
| 1c | deferred init, stop paraphrased with no "Missing connector" text, 0 Agent | true / 0 / 0 / 0 | FAIL | 1 | FAIL: met (`agent_calls=0` catches it alone) |
| 2 | deferred init, 1 Agent call, fixture `tool_reference`, no Missing line | true / 1 / 0 / 1 | PASS | 0 | PASS: met |
| 2b | as 2 with no `tool_reference` | true / 1 / 0 / 0 | PASS | 0 | PASS: met (`fixture_was_deferred` is extra evidence only, as stated) |
| 2c | deferred init, 1 Agent call, Missing line in the result | true / 1 / 1 / 0 | FAIL | 1 | correct |
| 3 | init with `ToolSearch` removed (eager), 1 Agent call | false / 1 / 0 / 0 | UNTESTED | 2 | UNTESTED, never PASS: met |
| 3b | init with ToolSearch but no `mcp__fixture__*` names | false / 1 / 0 / 0 | UNTESTED | 2 | met |
| 3c | no init event at all | empty / 1 / 0 / 0 | UNTESTED | 2 | met |
| 3d | two init events | `true true` / 1 / 0 / 0 | UNTESTED | 2 | fails safe (not PASS) |
| 3e | not JSON | empty / 0 / 0 / 0 | UNTESTED | 2 | fails safe |

Real streams, read only:

| stream | values | verdict |
|---|---|---|
| `c1-fixture/present.jsonl` | true / 1 / 0 / 1 | PASS |
| `c1-fixture/absent.jsonl` | false / 0 / 1 / 0 | UNTESTED under the A9 rule, which is correct |
| `c1sim/run_true.jsonl` | true / 0 / 0 / 0 | FAIL |
| `c1sim/run_false.jsonl` | false / 0 / 0 / 0 | UNTESTED |

Notes on the real streams:

- **present.jsonl:** one main-thread `Agent` call, then inside the sub-agent (parent `toolu_01ThY…`) `ToolSearch` followed by `mcp__fixture__echo`. The result reports the reply `ping`.
- **absent.jsonl:** the init has no fixture names, so `deferred_from_start=false`. The absent case is scored by its own check, not by `a9_verdict.sh`. Its result line is exactly the stop text.

**Check (4): do the three statements of the rule agree?** I compared the `## Changes in revision 2` table (:12-16), the A9 row (:380) and the P-2 pass table, present row (:291).

- FAIL: the same condition in all three.
- UNTESTED: the same condition in all three. P-2 and A9 also add "or the CLI fallback was used".
- PASS: the same core condition in all three. P-2 alone adds "the result contains the echo reply `ping`".

No input gets opposite verdicts in two places. The one gap is a stream with deferred start, at least 1 Agent call, no Missing line and no `ping`. The A9 row and the script call it PASS, while the P-2 table classifies it nowhere. For A9's claim, that deferred names count as present, the Agent call is the deciding signal, so this does not undermine A9. It is a note for QA (see below), not a rejection. The r2 self-contradiction is gone: FAIL no longer depends on `fixture_was_deferred` anywhere.

**The `run_true.jsonl` dispute.** The architect's position is sound. `run_true.jsonl` is the r1 init probe. It contains no `Agent`/`Task` tool_use, so under any rule that needs at least 1 Agent call for PASS it cannot pass, and FAIL is the rule working as written. The r2 verdict did not actually ask for `run_true` to PASS. It cited the `run_true`/`run_false` pair only as proof that init contents separate the deferred mode from the eager one. The pair does that here: `true` against `false`. The PASS evidence is the live `present.jsonl`, and it scores PASS.

**Residual notes for builder and QA (not rejections):**

1. The script prints `A9 PASS` without checking for `ping`. QA must also apply the P-2 table's `ping` condition to the present case, and must report a missing `ping` as a present-case failure, not as A9 PASS.
2. The script does not read `ENABLE_TOOL_SEARCH`. It cannot, because the stream does not record the environment. It infers the deferred mode from `ToolSearch` in init. QA must run the exact P-2 command line, which sets the variable, and quote it in the report.
3. If a stream ever carries more than one init event, `deferred_from_start` reads `true true` and the run scores UNTESTED. That fails safe. If it happens, QA should report it rather than edit the stream.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C1 | N/A: prose-only plugin change plus deletion of empty stubs; no pricing, returns, backtest, eval or verifier logic | N/A | N/A | N/A | N/A | N/A |

## Scratch work (outside the repo)

- `<scratchpad>/c1r3/rule.sh`: the P-2 block extracted from the design, :271-279.
- `<scratchpad>/c1r3/t*.jsonl`: the judge-built synthetic streams listed above.
- Read only, not modified: `<scratchpad>/a9_verdict.sh`, `<scratchpad>/c1-fixture/{present,absent}.jsonl`, `<scratchpad>/c1sim/{run_true,run_false,call_true}.jsonl`.
