RESULT: PASS

# Boundary QA: C2 lint script (r4 design + fixture fix for Q20; uncommitted tree)

Re-verification after the builder's fixture-only fix (writer.md gains `## Required connectors` / `- crmb` + `## Working principles`; good demo-orchestrator gains `| writer | crmb |`). Script untouched: md5 fd989f2ba3fa77de0a83a7f4391d1d60, 150 lines. All mutants ran on a tar copy in the scratchpad (v7/repo); the tree was not modified.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| lint CLI output <-> test 1 | lint_harness.py:140 prints `<LEVEL> <path>: <rule> <msg>` + summary | tests/test_lint_harness.py asserts 24 ERROR / 4 WARN by path + rule text | yes |
| good fixture agents <-> good preflight table <-> test 2 | researcher.md and writer.md both declare a connector; table rows `researcher\|crm`, `writer\|crmb` | test 2 expects 0/0 | yes (Q20, S1-S3 now fail test 2) |
| packager <-> script | package-plugin.sh calls lint_harness.py, rc -> err() | exit 1 on error | yes (nested probe exit 1) |
| SKILL.md Step 6.1 <-> script rules | lists the rule set | script rule ids match | yes |

## Gate
| command | exit | output observed |
|---|---|---|
| `md5sum skills/finhub-harness/scripts/lint_harness.py; wc -l` | 0 | `fd989f2ba3fa77de0a83a7f4391d1d60`, `150` (identical to the previously verified md5) |
| `lint_harness.py tests/fixtures/harness_bad` (stderr to file) | 1 | stderr 0 bytes; `lint_harness: 24 error(s), 4 warning(s)` |
| `... tests/fixtures/harness_good` | 0 | `lint_harness: 0 error(s), 0 warning(s)` |
| `... .claude` | 0 | `lint_harness: 0 error(s), 6 warning(s)` |
| `... .` (repo root) | 0 | `lint_harness: 0 error(s), 0 warning(s)` |
| `pytest -q` | 0 | `895 passed, 10 skipped in 81.24s` |
| `ruff check src tests <script>` | 0 | `All checks passed!` |
| `black --check src tests <script>` | 0 | `65 files would be left unchanged.` |
| `mypy --strict src` | 0 | `Success: no issues found in 37 source files` |
| `mypy --strict <script> tests/test_lint_harness.py` | 0 | `Success: no issues found in 2 source files` |
| `bash scripts/check-harness-refs.sh` | 0 | 0 FAIL lines; last `PASS packager exit 0` |
| `bash scripts/package-plugin.sh` (tar copy v7) | 0 | `lint_harness: 0 error(s), 0 warning(s)`; 3 dist lines; skill zip contains `scripts/lint_harness.py` once, evolve zip 0 |
| greps `lint_harness.py` / `TeamCreate` / `# 3. package` in package-plugin.sh | - | 1 / 0 / 1 |
| nested `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(` (tar copy) | 1 | `lint_harness: 1 error(s), 0 warning(s)` / `FAIL: lint_harness.py found errors` / `Validation failed; nothing packaged.` |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}'` script, test, SKILL.md, package-plugin.sh, both fixture dirs, skills/ | 1 | no match; the two edited good fixtures alone also rc 1 |
| `git status --short` | - | ` M scripts/package-plugin.sh`, ` M skills/finhub-harness/SKILL.md`, `?? skills/finhub-harness/scripts/`, `?? tests/fixtures/harness_bad/`, `?? tests/fixtures/harness_good/`, `?? tests/test_lint_harness.py`; `git submodule status` 0 lines with +/- |
| baseline on tar copy: `diff -r tests/fixtures <tree>` and `pytest tests/test_lint_harness.py` | 0 | `FIXTURES_IDENTICAL`, `4 passed` (needed before any kill counts; an earlier copy that dropped a fixture dir failed baseline and was discarded) |

## Probes
| probe | exit | observed |
|---|---|---|
| good copy with `\| writer \| crmb \|` row deleted (the second connector agent) | 1 | `preflight agent 'writer' needs 'crmb': no preflight row` |
| good copy with `- crmb` deleted from writer.md | 1 | `preflight row writer \| crmb has no agent connector line` |

## Q20 and siblings (script file diff shown by the driver; each had `old != new`, old-count 1, file changed, md5 restored)
| id | diff at lint_harness.py:129 | result |
|---|---|---|
| Q20 | `-declared \|= {(name, s) for s in connectors(path, text)}` / `+declared \|= {...} if not declared else set()` | KILLED: test_clean_fixture_passes_without_warnings fails |
| S1 collect from last declaring agent only | `+declared = {...} or declared` | KILLED: test_clean_fixture_passes_without_warnings |
| S2 skip first-sorted agent | `+declared \|= {...} if path != agents[0] else set()` | KILLED: bad-fixture test and clean-fixture test |
| S3 `=` instead of `\|=` | `+declared = {...}` | KILLED: bad-fixture test and clean-fixture test |

## Design mutants M1-M42 (design driver c2/mutate.py adapted to tar copy v7, plus per-mutant `old != new`, count-1 and changed-file checks)
42 KILLED / 0 SURVIVED / 0 no-op (each mutant produced a 1-3 line diff; script md5 restored fd989f2b... after the run).

## QA mutants (Q-series, 24)
My earlier driver was not kept, so the 24 were re-created from the previous report's descriptions (same changes where described; Q11, Q14-Q19, Q22, Q24 are best-effort equivalents). Result: 20 KILLED / 4 SURVIVED. Survivors are exactly the four earlier observations: Q2 (drop optional quote after key; judge-listed non-blocking JSON-key form), Q13 (blank-line continuation in frontmatter), Q21 (connector section ends at `## ` only), Q23 (agents bypass read(), G16 contrived). Q20 moved from SURVIVED to KILLED; nothing else changed.

## Defects
None blocking. Observations (unchanged, no action): Q2, Q13, Q21, Q23.

## Not run
- Q-series is a reconstruction, not my original driver (see above); the Q20 and S1-S3 results do not depend on it.
- Packager run on a tar copy (not the real tree, which would rewrite the ignored dist/); the copy excluded .git, references, .venv, dist.
- `references/` per-file licence check and 8-gram scan were not repeated: the script and the other new files are byte-identical to the previous run, and the only changed files are two good fixtures (checked for Hangul only).
- Unreadable-file and FIFO cases not re-probed.
