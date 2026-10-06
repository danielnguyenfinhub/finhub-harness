# Build record — OpenHarness QA adoption (design rev 3, verdict UPHELD 23 / REJECTED 0)

Applied: 1.1, 1.2, 1.3a, 1.3b, 1b.1-1b.4 (N6), 2.1, 2.2, 3.0, 3.1, 3.2, 4.1, 4.2, plus CLAUDE.md change-history row. Anchors matched byte-for-byte. Advisories folded: (a) "(e.g. 0.01 percentage points for a ratio, one cent for an amount)" in §7-7 lending row; (b) "public API as a consumer would" -> "exported API the way a downstream user would"; "unfixable without breaking an external contract" -> "only fixable by violating an interface that the design says an outside party owns" (agent file 1.2 bullet 4, §7-5); (c) no double blank line before `## Core Role`.

| id | grep / check | expected | actual |
|---|---|---|---|
| N1 | `grep -c 'first line starts with' boundary-qa.md` | 1 | 1 |
| N1 | `grep -c 'and nothing else' boundary-qa.md` | 0 | 0 |
| N1 | `grep -c 'Phase 4 final report follows' boundary-qa.md` | 1 | 1 |
| N1 | regex `^RESULT: (PASS\|FAIL)( — incomplete)?$` on PASS / FAIL-incomplete / PARTIAL lines | 2 of 3 match | 2 of 3 |
| N2 | `grep -c PARTIAL boundary-qa.md` | 1 | 1 |
| N3 | `grep -c 'listed only in the builder'` | 1 | 1 |
| N3 | `grep -c "builder report's deviation list"` | 0 | 0 |
| N4 | `grep -c 'compliance-sweep hit'` | 1 | 1 |
| N4 | `grep -c 'observation:'` | >=1 | 1 |
| N5 | `grep -c 'quality-gates.md\` §3-4' boundary-qa.md` | >=1 | 1 |
| N6 | `grep -c 'output on failure\|on failure, ≤60'` agent file / SKILL.md | 0 / 0 | 0 / 0 |
| N6 | `grep -c probe` boundary-qa SKILL.md | >=2 | 2 |
| N6 | `grep -c 'adversarial probe' quality-gates.md` | >=2 | 2 |
| N6 | empty-output Gate-row regex on SKILL.md + existing slice reports | 0 | 0 |
| N7 | `grep -c 'Standing reminder'` orchestrator / agent file | 2 / 1 | 2 / 1 |
| N8 | `grep -c 'one smallest step either side' qa-agent-guide.md` | 1 | 1 |
| N8 | `grep -c '80.00%' qa-agent-guide.md` | 0 | 0 |
| N9 | `grep -c 'CRM or system-of-record write'` | >=1 | 1 |
| N10 | `grep -c 'G1-G6' qa-agent-guide.md` | >=1 | 1 |
| N11 | `grep -ci 'simulator\|emulator' qa-agent-guide.md` | 0 | 0 |

Other checks: `bash scripts/package-plugin.sh` exit 0; `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' skills/` 0 hits; pytest 677 passed, 9 skipped; `git status --short`: only the five targets + CLAUDE.md modified (this _workspace file is gitignored); nothing under src/, tests/, pyproject, references/.

Not run: N3/N4/N7-N10 cold tests (they need a spawned QA agent); N1 regex was checked on sample lines, not a real slice report.
