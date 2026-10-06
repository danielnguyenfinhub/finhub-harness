# 03 runtime-builder C2 (status PASS)

## Files
created: skills/finhub-harness/scripts/lint_harness.py (150 lines), tests/test_lint_harness.py, tests/fixtures/harness_bad/ (22 files), tests/fixtures/harness_good/ (6 files)
modified: skills/finhub-harness/SKILL.md (Step 6.1 line 142, checklist line after 169; 198 lines), scripts/package-plugin.sh (old lines 24-45 -> one lint call; "# 3. package")
Files were generated from the design's code blocks by a scratchpad script; 0xE9 written as raw bytes (bad-bytes, nested deep/more); good notes-style holds U+FFFD (EF BF BD).

## Claims implemented
A1-A20 all in F1 (rule table in design); A19 also E3. Map: A1 dir-name/wrong-dir; A2,A3 name; A4,A5 description; A6 frontmatter; A7 no-name/bare-name/no-desc; A8 unknown-key owner; A10 subagent-ref; A11 v1-artefact; A12 connector; A13 preflight; A14 test 4; A15 long-desc/.claude; A16-A18 parser, keys, model; A19 P6/P12; A20 encoding.

## Gate
- P1 bad fixture: 24 error(s), 4 warning(s), exit 1, every seeded defect named, no Traceback.
- P2 good fixture: 0/0 exit 0. P3 .claude: 0 errors, 6 warnings exit 0; repo root 0/0 exit 0.
- P4 mypy --strict (script + test): Success, 2 files. ruff check skills/finhub-harness/scripts tests: All checks passed. black --check: 28 files unchanged. wc -l: 150.
- CI cmds: ruff check src tests pass; black --check src tests pass; mypy --strict src Success 37 files.
- P5 pytest -q: 895 passed, 10 skipped.
- P6 package-plugin.sh: first line "lint_harness: 0 error(s), 0 warning(s)", exit 0; zip contains lint_harness.py once (count 1).
- P7 check-harness-refs.sh: exit 0, no FAIL.
- P8 2; P9 1; P10 0; P11 198; P12 1 / 0 / 1; P13 1 / 1.
- Nested TeamCreate( in skills/finhub-harness/references/x/SKILL.md on a tar copy (scratchpad): packager exit 1, "Validation failed; nothing packaged."
- 8-gram overlap (whitespace tokens) between script, test, SKILL.md, fixtures and the 7 cited reference files: 0.
- Hangul: grep -rlP on design file list rc 1 (no output); grep -rnP '\p{Hangul}' skills/ gives 0 lines.

## AMBER actions
none (no dependency added).

## Deviations from design
none. Agents and skills share one read() statement, so no extra 0xE9 agent seed (total stays 24).

## Not run
Mutation suite M1-M42 (design's scratchpad mutate.py is not in the repo); left for boundary-qa. Nothing committed.

## Fix after QA (Q20)
Deviation from the audited fixture table (no claim change, no script change): tests/fixtures/harness_good/agents/writer.md gains `## Required connectors` / `- crmb` (then `## Working principles` heading before its body line, so the section ends), and the good demo-orchestrator preflight table gains the indented row `| writer | crmb |`.
- Lint: good 0/0 exit 0; bad 24/4 exit 1; .claude 0/6; repo root 0/0.
- tests/test_lint_harness.py: 4 passed. pytest -q: 895 passed, 10 skipped. mypy --strict, ruff, black on script+test pass. check-harness-refs.sh: 0 FAIL.
- Q20 mutant on a copy in the scratchpad (line 129): diff `declared |= {...}` -> `declared |= {...} if not declared else set()`. Result: test 2 FAILS (also test 3), 2 failed 2 passed. Killed.
