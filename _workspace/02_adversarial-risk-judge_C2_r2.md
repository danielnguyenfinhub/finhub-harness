TOTALS: UPHELD 19 / REJECTED 2 / UNVERIFIED 0 — round 2/3

# Adversarial verdict: C2 lint script (revision 1)

- Audited file: _workspace/02_strategy-architect_C2.md (revision 1)
- Audited: 2026-10-03
- Changed claims re-audited this round: A10, A13, A19 (with E3), S1. Also re-audited: everything in F1, F2, F3 and F4 that these claims touch. New substance row: S2.
- Carried forward unchanged from r1 (UPHELD): A1-A9, A11, A12, A14-A18
- Simulation: my own scratch copy at /tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/j2/repo. I extracted F1, F2 and the 21 fixture files from the design. Fixture bodies were taken up to the closing fence, minus the fence's own newline, so the 64-char good skill ends in `---` with no newline. E3 was applied to scratch `old.sh` → `new.sh`. Nothing was written into the repo except this verdict.
- Totals: 19 Authority List rows plus 2 substance rows (S1, S2). Both substance rows count toward REJECTED.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A9, A11, A12, A14-A18 | UPHELD | (r1 rows, unchanged) | carried forward | Non-blocking: A8 still says "not among the 9 errors". P1 now has 16 errors. The verification still holds (`owner` is a WARN) |
| A10 | UPHELD | NET-NEW; crewai crew.py:725 | :724-725 is `@model_validator` / `def check_manager_llm` (manager composition, as the claim says) | Recounted with F1's `REF_RE` over `.claude/**/*.md`: 6 agents × 1 + orchestrator SKILL 7 = **13**. P3 `.claude` gives 0 errors, so all 13 resolve |
| A13 | UPHELD | NET-NEW; repo SKILL.md:180; repo orchestrator-template.md:52-56 | :180 is the both-ways checklist line. :52 reads "Skip this item if the table says "none"". :54-56 is the table indented 3 spaces with the `{agent} \| {server, as in mcp__{server}__*}` placeholder | **Own simulation** (orchestrator = template lines 52-56 verbatim plus rows; agent `crm-agent` with `- crm`). match → 0/0, exit 0. Match plus `\| none \| none \|` plus `\| {agent} \| {server} \|` → 0/0, exit 0. Only a `none` row, agent with no connectors → 0/0, exit 0. Missing row → `preflight agent 'crm-agent' needs 'crm': no preflight row`, exit 1. Orphan `ghost \| erp` → `row ghost \| erp has no agent connector line`, exit 1. Wrong server → both errors, exit 1. Both directions still fire |
| A19 | UPHELD | NET-NEW; backlog :89 | as r1 | **Own simulation** (old.sh vs new.sh, fresh copy per case; table below). The nested `skills/finhub-harness/references/x/SKILL.md` with `TeamCreate(a)` now gives new exit **1**, like the old one. No old-exit-1 case drops to 0 except the documented EOF relaxation. Hidden-dir (`.h/SKILL.md`), depth-0 (`skills/SKILL.md`) and depth-3 nested files also exit 1 in both. The corrected E3 sentence (design :605-610) is true: the old frontmatter loop read only `skills/*/SKILL.md` (package-plugin.sh:28), and `V1_RE` matches the old grep pattern (:43) exactly. The behaviour-change note is accurate: deepseek index.ts:927 `const lineEnd = nextNewline < 0 ? raw.length : nextNewline` and :929-930 accept a closing `---` at EOF; the old regex `---\n(.*?)\n---\n` (:33) does not |

### Old vs new packager (E3), my run

| seeded defect | old | new |
|---|---|---|
| none (clean) | 0 | 0 (prints `lint_harness: 0 error(s), 0 warning(s)`; skill zip holds lint_harness.py ×1) |
| frontmatter removed | 1 | 1 |
| `name:` line removed | 1 | 1 (**by traceback, see S2**) |
| `name:` empty | 0 | 1 (**by traceback, see S2**) |
| `description:` empty | 1 | 1 (**by traceback, see S2**) |
| `description` key renamed | 1 | 1 (**by traceback, see S2**) |
| opening `---` removed | 1 | 1 |
| closing `---` removed | 1 | 1 |
| `TeamCreate(` / `TeamDelete(` / `team_name:` / experimental flag | 1 | 1 (all four) |
| third skill without frontmatter | 1 | 1 |
| nested `SKILL.md` with `TeamCreate(` | 1 | **1** (r1: 0, now fixed) |
| nested depth 3 `TeamDelete(`; nested `team_name:` + flag; hidden `.h/`; `skills/SKILL.md` | 1 | 1 |
| CRLF | 0 | 0 |
| frontmatter-only, closing `---` at EOF with no newline | 1 | 0 (intended relaxation, documented) |
| garbage top-level frontmatter line | 0 | 1 |

### P12 / E3 renumbering (item 4 of the launch prompt)

E3 is fully specified: replace lines 24-45 with the 6-line block, and "Also change line 49 `# 4. package` to `# 3. package`" (design :605, also :72). Applying both to a scratch copy gives P12 = **1 / 0 / 1**, with section headers `# 1.`, `# 2.`, `# 3. package`. The third grep can fail (it gives 0 if the rename is skipped), so it is not vacuous. P12 is internally consistent. Note: the architect's own `scratchpad/c2/pkg/scripts/package-plugin.sh:33` still reads `# 4. package`, so the architect never ran P12's third grep. My run is what verifies it.

## Substance

| id | verdict | finding | evidence | fix |
|---|---|---|---|---|
| S1 | **REJECTED** | Proof bar (backlog :91, "deleting any single rule lets its seeded defect through"). **All 8 r1 survivors are now killed** by my own mutants: X1 grammar, X3 unparseable report, X4 drop WARN, X5 loosen, X6 closing check (crash and no-crash variants), X8 `team_name:`, X9 `TeamDelete(`, X10 flag. So are the design's M13 (re-anchored), M18, M24-M28 and 17 other mutants of mine. **Three rule conditions in the Rules table still have no seeded defect, and deleting them passes all 4 tests:** **X24**, `name` "missing or empty" (`if not name: report(...)` → `pass`); **X7**, `frontmatter` "line 1 is not `---`" (drop `lines[0] != "---" or`); **X14**, `subagent-ref` on `agentType` (REF_RE `(?:subagent_type\|agentType)` → `(?:subagent_type)`) | X7 probe: `# Title\nname: t\ndescription: "d"\n---` gives ERROR from the original and `0 error(s)` (exit 0) from the mutant. X14 probe: an agent with `agentType: "ghost"` gives ERROR from the original and exit 0 from the mutant. X24 only survives because no fixture has a missing or bare `name:`, and seeding one exposes S2. `no-frontmatter` has no `---` at all, so the closing check catches it and the opening check is never isolated | Seed into `harness_bad`: a skill with no `name:` key, or a bare `name:` (after S2 is fixed); a skill whose line 1 is a heading, followed by valid keys and a `---`; an agent line `agentType: 'ghost2'`. Update the ERROR count in test 1 and P1, and add X7, X14 and X24 to the mutation table |
| S2 | **REJECTED** | **F1 crashes on any missing or bare-empty `name`/`description`.** `scalar` (design :168) tests `raw[:1] in "\"'"`. For `raw == ""` that is `"" in "\"'"`, which is **True**, so `raw[0]` raises `IndexError`. `check_meta` calls `scalar(data.get("name", ""))`, so a missing key, or `name:` / `description:` with no value, kills the run with a traceback. No `ERROR ... name`/`description` line is printed, and every other finding collected in `out` is lost. The rules table's "missing or empty" (A7) works only for the quoted `""` form, which is the one form the fixture seeds | Run: skill dirs `a` (no `name:`), `b` (`name:` bare) and `c` (no `description:`) each print `IndexError: string index out of range` from `scalar`, exit 1. The packager still fails (non-zero exit), but by accident, and E1 tells the user to "fix every `ERROR` line", which then does not exist | Guard the empty string, e.g. `if raw[:1] in ("\"", "'") and ...`. Add the S1 missing-name seed so test 1 pins it |

## Re-run of the design's proof (all pass; not findings)

- P1: 16 ERROR + 4 WARN, exactly as listed (v1 lines 11/12/13/14, nested line 2). Last line `lint_harness: 16 error(s), 4 warning(s)`, exit 1.
- P2: `0 error(s), 0 warning(s)`, exit 0, with the 64-char skill having no newline after `---`. Description lengths measured at 1025 (bad) and 1024 (good).
- P3: `.claude` gives `0 error(s), 6 warning(s)` (5 no-`model:` and 1259 chars), exit 0. `.` gives `0 error(s), 0 warning(s)`, exit 0.
- P4: `wc -l` = **146**. `mypy --strict` on both files reports `Success: no issues found in 2 source files`. ruff reports `All checks passed!`. black leaves 28 files unchanged.
- P5: full suite in the scratch copy gives **895 passed, 10 skipped**. The new file gives 4 passed. (A first run gave 1 failure because my copy lacked `.gitignore`, which `test_checkpoint.py:386` reads. That was a scratch artefact, fixed by copying the file.)
- P6/P7: new packager exit 0 with zip count 1; `check-harness-refs.sh` exit 0, 0 FAIL lines.
- Minor, non-blocking: X17 (`none` skip made case-sensitive) and X19 (nested glob narrowed to exactly `skills/*/*/*/SKILL.md`) also survive. The "(any case)" and "any depth" claims are true in F1 but not pinned by a test. Consider an uppercase `None` row in `none-orchestrator` and a nested fixture one level shallower. The "no newline after `---`" pin depends on the builder honouring the prose at :344, because a Markdown fence cannot show it.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C2 | N/A static lint of Markdown frontmatter; no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no model training or splits |
