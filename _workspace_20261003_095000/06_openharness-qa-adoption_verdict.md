TOTALS: UPHELD 23 / REJECTED 0 / UNVERIFIED 0 — round 3/3

# Adversarial verdict — OpenHarness QA adoption (OH23-OH27), revision 3

- Audited file: _workspace/06_openharness-qa-adoption_design.md (revision 3, 304 lines)
- Audited: 2026-10-02 AEST
- Changed claims re-audited this round: N1, N3, N8 (round-2 rejections), N4 (advisory), Edit 3.0 (quality-gates.md:165, covered by N1). Also re-ran the greps of N2, N5, N6, N7, N9-N11 against built scratch copies.
- Method: copied `.claude/agents/boundary-qa.md` to the scratchpad and applied insertions 1.1, 1.2, 1.3a, 1.3b exactly as written (the anchors at :8, :23, :28 matched byte-for-byte). Appended insertion 2.2 to a scratch copy of `qa-agent-guide.md` (212 lines; anchors :15 and :212 matched). Ran every named grep on the scratch copy and on the real current file. Vacuity test: for each grep, I either compared the current file with the scratch copy or removed the rule's sentence from the scratch copy, then confirmed the count changes.
- Source reopened: references/openharness/src/openharness/coordinator/agent_definitions.py (AD) :79, :127, :251, :268, :290, :294, :312, :315, :322, :341, :343, :351, :357; references/portmaps/openharness-9b2efd7.md:120; references/openharness/LICENSE:1 "MIT License".

## Claims

| id | verdict | cited | found at cited line (±5) | reason / exact fix |
|---|---|---|---|---|
| Q1 | UPHELD (carried, spot-checked) | AD:251-253 | :251 "Your job is not to confirm the implementation works — it's to try to break it." | — |
| Q2 | UPHELD (carried) | AD:253 | two failure patterns | — |
| Q3 | UPHELD (carried) | AD:253 | re-execution rejects PASS steps with no output | — |
| Q4 | UPHELD (carried, spot-checked) | AD:268 | `=== VERIFICATION STRATEGY ===` | — |
| Q5 | UPHELD (carried, spot-checked) | AD:290 | "Match rigor to stakes: a one-off script ... production payments" | — |
| Q6 | UPHELD (carried, spot-checked) | AD:294 | `=== RECOGNIZE YOUR OWN RATIONALIZATIONS ===` | — |
| Q7 | UPHELD (carried, spot-checked) | AD:312-313 | `=== BEFORE ISSUING PASS ===`; "at least one adversarial probe you ran" | — |
| Q8 | UPHELD (carried, spot-checked) | AD:315-319 | `=== BEFORE ISSUING FAIL ===`; :319 not actionable is an observation | — |
| Q9 | UPHELD (carried, spot-checked) | AD:322 | `=== OUTPUT FORMAT (REQUIRED) ===` | — |
| Q10 | UPHELD (carried, spot-checked) | AD:341 | "(No command run. Reading code is not verification.)" | — |
| Q11 | UPHELD (carried, spot-checked) | AD:357 | `_VERIFICATION_CRITICAL_REMINDER = (` | — |
| Q12 | UPHELD (carried, spot-checked) | AD:127; AD:79 | :127 `critical_system_reminder ... # short message re-injected at every user turn`; :79 maps to `criticalSystemReminder_EXPERIMENTAL` | — |
| N1 | UPHELD | NET-NEW-retained (AD:343; boundary-qa.md:28, :32; quality-gates.md §3-1, §4-1) | AD:343 "End with exactly this line"; boundary-qa.md:32 timeout form; quality-gates.md:239-241 §4-1 Done / Partly done / Blocked | Round-2 fix applied. 1.1 now says "a slice report's first line starts with ..." and adds "the Phase 4 final report follows ... §4-1 instead". Grep results, current file → scratch copy: `first line starts with` 0 → 1; `Phase 4 final report follows` 0 → 1; `and nothing else` 0 → 0 (guard against regression). Vacuity: with "a slice report's first line starts with" removed, the count is 0; with the §4-1 clause cut, the count is 0. Regex `^RESULT: (PASS\|FAIL)( — incomplete)?$` on six sample lines matches only `RESULT: PASS`, `RESULT: FAIL`, `RESULT: FAIL — incomplete` (3/6); it rejects `RESULT: PARTIAL`, `RESULT: PASS (probably)` and `Done`. |
| N2 | UPHELD (carried, re-grepped) | NET-NEW-retained (AD:351; boundary-qa.md:31) | AD:351 PARTIAL "for environmental limitations only" | `PARTIAL` 0 → 1. |
| N3 | UPHELD | NET-NEW (tightens AD:318) | AD:315-319 before-FAIL checks | Round-2 fix applied. The self-failing `deviation list` grep has been replaced with `builder report's deviation list`. Grep results, current → scratch: `listed only in the builder` 0 → 1 (discriminating; it falls to 0 when the 1.2 parenthesis is cut); `builder report's deviation list` 0 → 0. A test line containing the revision-1 phrase scores 1, so the negative grep catches a regression and is not vacuous. The bare `deviation list` still scores 1 on the scratch copy, which confirms that dropping it was correct. |
| N4 | UPHELD | NET-NEW (keeps quality-gates.md:165, §3-4/§4-2/§4-3) | — | Advisory adopted: "a failed ... probe command" is now "a probe whose observed behaviour differs from the design (an error-path probe that exits non-zero as designed is not a failure)". 1.2 and §7-5 agree. This is consistent with the 1b.4 example probe (exit 2 on missing argument). `compliance-sweep hit` 0 → 1 and falls to 0 when its clause is cut; `observation:` 0 → 1. |
| N5 | UPHELD (carried, spot-checked) | NET-NEW (port map :120) | :120 "no case-based benchmark, no LLM-judge panel and no mutation testing" | ``quality-gates.md` §3-4`` 0 → 1 in scratch. |
| N6 | UPHELD (carried, re-grepped) | NET-NEW (coherence) | SKILL.md:23, :39, :42-45 and quality-gates.md:293 unchanged from round 2 (re-read) | `output on failure\|on failure, ≤60` in boundary-qa.md: 1 → 0. SKILL.md `probe` = 0 today. quality-gates.md `adversarial probe` = 0 today. |
| N7 | UPHELD (carried, anchors re-verified) | NET-NEW (orchestrator SKILL.md:95-96, :112-114) | :95 `prompt: "You are boundary-qa. Read .claude/agents/boundary-qa.md first.`; :96 `    Verify slice N; write _workspace/03_boundary-qa_slice{N}.md."`; :112 same as :95; :114 `    re-running pytest -q, ruff check src tests, black --check src tests, mypy --strict src."` | Byte-for-byte match with the anchors in 4.1 and 4.2. `Standing reminder` = 0 today in the orchestrator SKILL.md and in boundary-qa.md; it is 1 in the scratch boundary-qa.md. The 4.1 reminder says "the report's first line" only inside the Phase 3 slice prompt, and 4.2 omits it, so the scope is correct. |
| N8 | UPHELD | NET-NEW (no reference covers lending maths) | — | Round-2 fix applied. The row now reads "the design's threshold T and one smallest step either side (T − ε, T + ε) in the threshold's own unit". The cold test asserts probes at 999.99, 1,000.00 and 1,000.01 plus monthly-vs-annual income, so row and test now agree. "percentage points" is gone from the design. `one smallest step either side` 0 → 1; `80.00%` 0 → 0. Advisory: the row does not give my suggested example "(e.g. 0.01 percentage points for a ratio, one cent for an amount)". For an amount in synthetic "units", an agent could read the smallest step as 1 unit rather than 0.01 and probe 999 and 1,001. Adding the example would close that gap. I did not reject on this: the cold test states the cent, and the error would produce a coarser probe, not a false PASS on a threshold mismatch. |
| N9 | UPHELD (carried, re-grepped) | NET-NEW (boundary-qa.md:23) | :23 no client data / Mercury records | `CRM or system-of-record write` 0 → 1. |
| N10 | UPHELD (carried, re-grepped) | NET-NEW (quality-gates.md §2-3) | — | `G1-G6` 0 → 1. |
| N11 | UPHELD (carried, re-grepped) | NET-NEW (YAGNI) | — | `simulator\|emulator` 0 → 0. This is an absence check by nature; the source row AD:277 is not carried. |

## Edit 3.0 (quality-gates.md:165) — checked, no clash

- Current :165 reads "The first line of every QA report is exactly `RESULT: PASS` or `RESULT: FAIL`, so the orchestrator reads it without parsing. ..." It is under `### 3-1. The verdict line` (:163) inside `## 3. Boundary QA after every slice` (:159). The phrase to replace is present at that line.
- No clash with §4-1 (:239 "Start with exactly one of three words: Done, Partly done or Blocked"). The §3-1 sentence is scoped by its section to per-slice QA reports, and §5 (:299) separately says "Final report: first line Done / Partly done / Blocked". The edit makes §3-1 consistent with the timeout form at boundary-qa.md:32. It does not widen the scope.
- Insertion 3.1 quotes its anchor "as it reads before edit 3.0". Whichever order the edits run in, the result is one paragraph ending in the appended sentence.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| Target 1 boundary-qa.md | N/A prose QA rules, no pricing | N/A | N/A | N/A | N/A | N/A |
| Target 1b boundary-qa SKILL.md | N/A report template | N/A | N/A | N/A | N/A | N/A |
| Target 2 qa-agent-guide.md §7 | N/A prose; returns/backtest/eval routes to quality-gates.md §2-3 G1-G6 unchanged (N10) | N/A | N/A | N/A | N/A | N/A |
| Target 3 quality-gates.md §3-1, §5 | N/A QA-rule sentences | N/A | N/A | N/A | N/A | N/A |
| Target 4 orchestrator SKILL.md | N/A spawn prompt text | N/A | N/A | N/A | N/A | N/A |

## Licence

- `references/openharness/LICENSE:1` reads "MIT License". All cited paths are under `references/openharness/`. No dify or `autogpt_platform` path is cited.
- I ran a 5-word-run scan of all insertion text (1.1, 1.2, 1.3b, 1b.3, 1b.4, 2.1, 2.2, 3.1, 3.2) against `sed -n 251,361p AD`. Shared runs:
  - "this would take too long": a quoted excuse string (AD:301), allowed.
  - "at least one adversarial probe": a technical term (AD:313).
  - "the public API as a consumer would": AD:275, 6 words, in a table cell.
  - "unfixable without breaking an external contract": AD:319, 6 words, in 1.2 bullet 4 and §7-5.
- None of these is pasted prose. Each is one short phrase inside a rewritten, attributed sentence, and MIT permits it. Advisory: reword the last two phrases if the "adapt" bar is meant to be zero shared runs. Neither phrase changed in this round.

## New defects introduced by revision 3

None blocking. One cosmetic issue: insertion 1.1 asks for a blank line before and after, but line 9 of the agent file is already blank, so the result has two blank lines before `## Core Role`. This is harmless in Markdown.

## Round 1 / Round 2 history

- Round 1: UPHELD 15 / REJECTED 7 / UNVERIFIED 1.
  - Rejected: Q6 near-verbatim; N1 timeout-line conflict; N3 builder self-declared deviations; N4 waivable PASS conditions; N6 template/skill incoherence; N7 per-spawn reminder not delivered; N8 cold test off-row.
  - Unverified: Q12, injector not in the pinned repo.
- Round 2: UPHELD 20 / REJECTED 3.
  - Rejected: N1, the first-line reminder was unscoped and clashed with §4-1; N3, the `deviation list` grep matched the design's own correct text; N8, the row probed in "percentage points" while the test used a currency threshold, below the threshold only.
  - Advisories: N4 "failed probe" wording; quality-gates.md:165 "exactly".
- Round 3: all three rejections and both advisories were resolved as asked. Clean.
