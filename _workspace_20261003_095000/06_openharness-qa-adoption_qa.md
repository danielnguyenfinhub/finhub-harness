RESULT: PASS

QA of the uncommitted OH23-OH27 prose adoption (design rev 3, verdict UPHELD 23/0/0). Six files modified, no code touched. Four observations below, none a defect.

## Boundary table

| boundary | side A | side B | match |
|---|---|---|---|
| Slice-report first line | agent file :10 reminder and :35 Format, `RESULT: PASS` or `RESULT: FAIL`, timeout `RESULT: FAIL — incomplete` at :40 | SKILL.md :23 and template :28; orchestrator :98, :102-104; quality-gates §3-1 :165 ("starts with"), §5 :283; qa-agent-guide §7-2 | yes. All five name the same two values. The ` — incomplete` form is covered by "starts with". The regex `^RESULT: (PASS\|FAIL)( — incomplete)?$` accepts PASS and FAIL — incomplete, rejects PARTIAL and "PASS and nothing else" |
| PARTIAL | agent file :36 "does not use ... PARTIAL" (only hit, count 1) | guide §7-2 "there is no PARTIAL"; orchestrator Phase 3 routes PASS/FAIL only; quality-gates :165 "cannot run = FAIL". The other PARTIAL hits in `.claude` are the port-map status and the builder's own timeout status (`runtime-builder.md:34`), not QA | yes |
| Phase 4 final report | agent file :10 "follows quality-gates §4-1 instead" | orchestrator Phase 4 reminder omits the `RESULT:` clause; quality-gates §4-5 first line Done / Partly done / Blocked | yes. See observation 1 |
| Gate row content | agent file :35-36 "output observed", success summary line, 60 lines on failure | SKILL.md :39-46 (success rows carry text, probe row added); quality-gates :165 and §5 :294-295; guide §7-2 block | yes. See observation 2 |
| Probe before PASS | agent file :29 | SKILL.md :23; quality-gates :165 and §5 :294; guide §7-3, §7-4 | yes |
| Before-FAIL guard | agent file :30 | guide §7-5 (same three checks, same non-waivable list, `observation:`) | yes. Wording differs only by the judge-advised phrase (see D-note) |
| Standing reminder | agent file :10 (1 hit) | orchestrator :97 and :116 (2 hits); guide §7-6 says per spawn, not per turn, matching the source's :127 comment | yes |
| Cited lines vs source | every `:<line>` in the five files | `agent_definitions.py` opened with `sed -n` | yes. See cite check |

## Gate

| command | exit | output observed |
|---|---|---|
| N1a `grep -c 'first line starts with' .claude/agents/boundary-qa.md` | 0 | `1` (expect 1) |
| N1b `grep -c 'and nothing else' …boundary-qa.md` | 1 | `0` (expect 0; grep exits 1 on a zero count) |
| N1c `grep -c 'Phase 4 final report follows' …boundary-qa.md` | 0 | `1` (expect 1) |
| N1d regex `^RESULT: (PASS\|FAIL)( — incomplete)?$` on four sample lines (`.venv/bin/python`) | 0 | `RESULT: PASS True` / `RESULT: FAIL — incomplete True` / `RESULT: PARTIAL False` / `RESULT: PASS and nothing else False`. Applied to sample strings only, not a spawned QA's real report |
| N2 `grep -c PARTIAL …boundary-qa.md` | 0 | `1` (expect 1) |
| N3a `grep -c 'listed only in the builder' …boundary-qa.md` | 0 | `1` (expect 1) |
| N3b `grep -c "builder report's deviation list" …boundary-qa.md` | 1 | `0` (expect 0) |
| N4a `grep -c 'compliance-sweep hit' …boundary-qa.md` | 0 | `1` (expect 1) |
| N4b `grep -c 'observation:' …boundary-qa.md` | 0 | `1` (expect >=1) |
| N5 `grep -cF 'quality-gates.md` §3-4' …boundary-qa.md` | 0 | `1` (expect >=1) |
| N6a `grep -c 'output on failure\|on failure, ≤60' …boundary-qa.md` | 1 | `0` (expect 0) |
| N6b same pattern on `.claude/skills/boundary-qa/SKILL.md` | 1 | `0` (expect 0) |
| N6c `grep -c probe .claude/skills/boundary-qa/SKILL.md` | 0 | `2` (expect >=2) |
| N6d `grep -c 'adversarial probe' …quality-gates.md` | 0 | `2` (expect >=2) |
| N6e `grep -nE '^\| [^\|]+ \| [0-9]+ \| *\|$' SKILL.md _workspace/03_boundary-qa_slice*.md \| wc -l` | 0 | `0` (expect 0; empty output cells) |
| N7a `grep -c 'Standing reminder' …master-finhub-orchestrator/SKILL.md` | 0 | `2` (expect 2) |
| N7b `grep -c 'Standing reminder' …boundary-qa.md` | 0 | `1` (expect 1) |
| N8a `grep -c 'one smallest step either side' …qa-agent-guide.md` | 0 | `1` (expect 1) |
| N8b `grep -c '80.00%' …qa-agent-guide.md` | 1 | `0` (expect 0) |
| N9 `grep -c 'CRM or system-of-record write' …qa-agent-guide.md` | 0 | `1` (expect >=1) |
| N10 `grep -c 'G1-G6' …qa-agent-guide.md` | 0 | `1` (expect >=1) |
| N11 `grep -ci 'simulator\|emulator' …qa-agent-guide.md` | 1 | `0` (expect 0) |
| attribution count `grep -c 'adapted from references/openharness'` per file | 0 | agent file 6 (1.1 reminder + four 1.2 bullets + 1.3b), guide 7 (§7-1 to §7-7, plus the capital-A "Adapted from" header), SKILL.md 0, quality-gates 0, orchestrator 0. Matches the design: those three carry coherence edits only |
| verbatim check (script in scratchpad, 8-word normalised n-gram match of each edited file against `agent_definitions.py`) | 0 | all five files `0` hits |
| `bash scripts/package-plugin.sh` | 0 (artifacts written; the `tail` pipe masked its exit status) | `dist/finhub-harness.plugin  91331 bytes`, `dist/finhub-harness-skill.zip  80133 bytes`, `dist/finhub-harness-evolve-skill.zip  3516 bytes` |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' skills/` | 1 | no output, 0 hits |
| `.venv/bin/python -m pytest -q` | 0 | `677 passed, 9 skipped in 61.84s (0:01:01)` |
| `.venv/bin/ruff check src tests` | 0 | `All checks passed!` |
| `git status --short` | 0 | exactly 6 lines: `M .claude/agents/boundary-qa.md`, `M .claude/skills/boundary-qa/SKILL.md`, `M .claude/skills/master-finhub-orchestrator/SKILL.md`, `M CLAUDE.md`, `M skills/finhub-harness/references/qa-agent-guide.md`, `M skills/finhub-harness/references/quality-gates.md`. Nothing under src/, tests/, references/ |
| mutant: M1 scratch copy of agent file with the `- Before writing \`RESULT: FAIL\`` bullet deleted | 0 | N4a `1 -> 0`, N3a `1 -> 0`, N4b `1 -> 0`. The greps bite |
| mutant: M2 same scratch copy with the `- Before writing \`RESULT: PASS\`` bullet also deleted | 0 | `Before writing .RESULT: PASS` `1 -> 0`, N5 `1 -> 0` (the §3-4 mention lived in that bullet). The greps bite |
| mutant: M3 scratch copy of boundary-qa SKILL.md with the `at least one adversarial probe ... with its output, and` clause removed from step 5 | 0 | N6c `2 -> 1`, below the >=2 threshold. The grep bites |
| probe: cite check of every `:<line>` in the five files against `agent_definitions.py`, opened with `sed -n` | 0 | :79 `critical_system_reminder → criticalSystemReminder_EXPERIMENTAL`; :127 `short message re-injected at every user turn`; :251-253 verification-specialist prompt with both failure patterns; :268 `=== VERIFICATION STRATEGY ===`; :271-281 per-change-type rows; :290 `Match rigor to stakes`; :294-301 rationalisation list; :312-313 BEFORE ISSUING PASS; :315-319 BEFORE ISSUING FAIL; :322-323 OUTPUT FORMAT; :341 `Reading code is not verification`; :343 `End with exactly this line`; :351 PARTIAL rule; :357-360 critical reminder. All real and on the claimed topic |

## Defects

None. Every N1-N11 grep matches the expected value.

observation: 1. `skills/finhub-harness/references/quality-gates.md:165` says "The first line of every QA report starts with `RESULT:`", while §4-5 (`:268`) says the Phase 4 final report's first line is Done / Partly done / Blocked. The §3-1 heading is "The verdict line" for slice QA, and the agent file's :10 reminder resolves it explicitly. The sentence is original text, left unchanged in meaning, and the design scopes it with N1. A fresh reader of quality-gates alone could still hesitate. Optional wording: "every slice QA report".

observation: 2. `quality-gates.md:181` and `:287` still read "verbatim output (up to 60 lines on failure)". That is a cap, not an "output on failure only" rule, and the new §5 bullet at `:295` says success rows carry the summary line. Opened both lines. Not a contradiction, but the phrase could be misread by a QA that stops at :287.

observation: 3. Wording deviation from the design text: agent file :30 and guide §7-5 say "only fixable by violating an interface that the design says an outside party owns" instead of design 1.2's "unfixable without breaking an external contract the design names". The judge's round advisory (verdict lines 61-63) asked for a reword of that phrase. The deviation is audited, not builder-only, and the meaning is unchanged. Similarly the §7-7 lending row adds the "(e.g. 0.01 percentage points for a ratio, one cent for an amount)" example, which the judge advised (verdict line 34). Build record lists both.

observation: 4. Under-specified in the agent file for a fresh QA: `mutant: <id>` does not say which id (use the mutant label from `quality-gates.md` §3-4 or a short name). The "probe whose observed behaviour differs from the design" clause gives no rule for a probe the design never specified. The agent also cannot see the rule "an error-path probe that exits non-zero as designed is not a failure" resolve a case where the design is silent. Neither blocks execution.

## Cold-test simulation (read as a fresh QA, no sub-agents spawned)

- Instructions executable as written: re-read the reminder before each verdict, four gate commands each as a row with summary line, at least one `probe:` or `mutant:` row before PASS, before-FAIL checks for findings outside §3-1 conditions, `observation:` rows under `## Defects`, timeout form, Phase 4 format via §4-1.
- This run followed them: the file I wrote begins with `RESULT:` on line 1, carries M1-M3 and a cite-check probe as rows, and ran the scratch mutations on copies.
- Ambiguities: only those in observation 4. Not tested: the design's cold tests N3, N4, N7-N10 (they need a spawned QA with a seeded defect; the builder also did not run them). This is a gap in verification of behaviour, not of text.

## Notes

- N1 regex was checked on sample lines, not on a real slice report from a spawned QA.
- Scratch copies lived only under the scratchpad `mut/` directory and are removed afterwards. No repo file was edited or committed. `dist/` output of the package script is untracked or ignored (git status shows only the six files).
