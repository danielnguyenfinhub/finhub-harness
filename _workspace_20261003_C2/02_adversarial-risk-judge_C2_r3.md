TOTALS: UPHELD 20 / REJECTED 1 / UNVERIFIED 0 — round 3/3

# Adversarial verdict: C2 lint script (revision 2)

- Audited file: _workspace/02_strategy-architect_C2.md (revision 2)
- Audited: 2026-10-03
- Changed claims re-audited this round: A8 (count), S1, S2 (all marked CHANGED r2), and the P12 renumber under A19/E3.
- Carried forward unchanged from r2 (UPHELD): A1-A7, A9-A19.
- Simulation: my own fresh scratch copy at /tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/j3/repo. I extracted F1, F2 and all 27 fixture files (21 bad, 6 good) from the design with my r2 extractor (`j3/extract.py`). E3 and the renumber were applied to scratch `scripts/package-plugin.sh`. Mutants: `j3/mut3.py` (47 mutants) plus single probes. I did not use the architect's numbers or scripts. Nothing was written into the repo except this verdict.
- Totals: 19 Authority List rows plus 2 substance rows (S1, S2). The REJECTED row is S1.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A7, A9-A19 | UPHELD | (r1/r2 rows, unchanged) | carried forward | Byte-identical to r2. A19's P12 is re-verified below and holds |
| A8 | UPHELD | NET-NEW; backlog :92; deepseek index.ts:993-995 | carried from r1 | The count now reads "not among the 22 errors" (design :819). That matches P1 (:701), test 1 (:729), F3 (:93) and my run (`22 error(s), 4 warning(s)`, with `owner` among the WARN lines). The only remaining "16" is in the revision 1 history (:49), which is correct as history |

## P12 / E3 (my run)

On a scratch copy, I replaced lines 24-45 with E3's 6-line block and changed `# 4. package` to `# 3. package`.
- Greps: `lint_harness.py` **1**, `TeamCreate` **0**, `^# 3. package` **1**. Section headers read `# 1.` (:11), `# 2.` (:24), `# 3. package` (:33).
- Real tree: the packager prints `lint_harness: 0 error(s), 0 warning(s)`, then the three dist lines, and exits **0**. The skill zip holds `finhub-harness/scripts/lint_harness.py` once. `check-harness-refs.sh` exits 0 with 0 FAIL lines.
- With `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(team="x")`, the run prints `ERROR ... v1-artefact line 2: TeamCreate(` and `Validation failed; nothing packaged.`, and exits **1**. With the probe removed, it exits 0 again.

## Substance

| id | verdict | finding | evidence | fix |
|---|---|---|---|---|
| S1 | **REJECTED** | Proof bar (launch prompt): "for EVERY lint rule and condition, deleting or weakening it lets its seeded defect through". **All three r2 survivors are now killed:** X7 (opening `---`) by `heading-first`; X14 (`agentType` alternation) by `typer.md`; X24 (empty-name report) by `no-name`/`bare-name`. So are all my other r1/r2 mutants: X1, X3, X4, X5, X5b, X6/X6c, X8-X13, X15-X23, X25-X29, plus X17 (case-sensitive `none`), X17b (`none` skip dropped), X18/X19 (nested excluded or one level only), and X30 (r1 crash guard restored). X6b alone is an equivalent mutant: it leaves the `"---" not in lines[1:]` guard in place. Combined with dropping that guard (X6c), it is killed. **One new weakening of a stated rule condition survives: N14.** The Rules table's `subagent-ref` row (:130) names the single-quoted form explicitly (`` `agentType: 'x'` ``). Narrowing REF_RE's quote class from `["']` to `["]` passes all 4 tests (`4 passed`). Every seeded dangling ref is double-quoted (`caller.md` `"ghost"`, `typer.md` `"ghost-two"`). The only single-quoted ref in the fixtures is the good `'general-purpose'`, a built-in, which passes whether it is matched or skipped. The single-quoted form is also the common real one: the plugin's own recipes write `{ agentType: 'qa-inspector', ... }` (`skills/finhub-harness/references/qa-agent-guide.md:125`, `workflow-recipes.md:195`, `team-examples.md:106,109`). Note: the r2 fix text asked for `agentType: 'ghost2'` in single quotes; the seed uses double quotes | Probe dir: agent `a.md` with ``Use `subagent_type: 'ghost'` and `agentType: 'ghost2'`.``. Original F1: `ERROR ... subagent-ref line 6: no agent file for 'ghost'` and the same for `'ghost2'`, 2 errors, exit 1. N14 mutant: `lint_harness: 0 error(s), 0 warning(s)`, exit **0**; `pytest tests/test_lint_harness.py`: **4 passed** | One-character seed change: in `harness_bad/agents/typer.md`, write `` `agentType: 'ghost-two'` `` with single quotes. P1's count stays 22, and test 1's expected string (`no agent file for 'ghost-two'`) is unchanged, because the message reprs the value. This kills M31 and N14 together. Add N14 to the mutation table |
| S2 | UPHELD | Crash fixed. `scalar` (:193) now tests `raw[:1] in ('"', "'")`, so `raw == ""` no longer reaches `raw[0]` | Own fuzz (`j3/fuzz.py`): each case is a skill dir next to a sentinel `wrong-dir` skill. **Missing `name:`**, **bare `name:`**, **missing `description:`**, bare `description:`, `name: ` (trailing space), lone `"`, lone `'`, unterminated `"abc`, value `#`, value `# c`, `>-`/`\|` alone, empty file, `---` alone, `---\n---`, leading indented line, BOM, CRLF, tab-indented key, bare `:`, NUL byte, duplicate key, `"a"b`, and agent `model: #` / bare `model:` / no name: **all exit 1, no Traceback, sentinel `dir-name` ERROR still printed**. Each odd value gives a `name`/`description`/`frontmatter` ERROR, or is accepted as written (CRLF). The bad fixture's `no-name`, `bare-name` and `no-desc` each print their ERROR line (P1). The X30 mutant (r1 guard restored) is killed | — (see the non-blocking notes for the one non-`scalar` crash path) |

## Re-run of the design's proof (all pass; not findings)

- P1: 22 ERROR + 4 WARN, exactly as listed. Last line `lint_harness: 22 error(s), 4 warning(s)`, exit 1, no Traceback.
- P2: `0 error(s), 0 warning(s)`, exit 0. The 64-char good skill ends `---` with no newline (checked with `od`).
- P3: `.claude` gives `0 error(s), 6 warning(s)`, exit 0. `.` gives `0 error(s), 0 warning(s)`, exit 0.
- P4: `wc -l` = **146** (≤150). `mypy --strict` on F1 and F2 reports `Success: no issues found in 2 source files`. ruff reports `All checks passed!`. black reports `28 files would be left unchanged`.
- P5: full suite in the scratch copy gives **895 passed, 10 skipped**. That is the design's new total: 891 baseline + 4 new.
- Mutation run (`j3/mut3.py`, 47 mutants): 41 killed. Survivors: X6b (equivalent, see S1), N14 (S1), and N4, N7, N11, N12 (notes below).

## Non-blocking notes (not counted)

1. **Remaining crash path, outside `scalar`.** A `SKILL.md` with a non-UTF-8 byte (`description: "\xff\xfe"`) makes `path.read_text(encoding="utf-8")` (:252/:266) raise `UnicodeDecodeError`. The run dies with a Traceback and exit 1, and the sentinel finding is lost: the same failure mode as r2's S2. It fails closed, and the design makes no claim about encoding, so I do not count it. Suggested: catch `UnicodeDecodeError` and `report("ERROR", path, "frontmatter", "not UTF-8")`, then `continue`. Alternatively, list it under Does not cover.
2. **Vacuous assertion.** Test 1's `"Traceback" not in out` (:316) cannot fail, because `lint()` returns only `run.stdout` (:311) and Python tracebacks go to stderr. A crash is still caught, by the missing findings and the exact count, which is why M34/X30 is killed. The assertion itself adds nothing. Suggested: return `run.stdout + run.stderr`, or assert on stderr.
3. **Unpinned parser details (A16, not Rules-table conditions):**
   - N7: dropping the ` # comment` cut survives. An unquoted `name: x  # c` would then be a false `name` ERROR.
   - N11: dropping the `>`/`|` indicator strip survives. A `description: >` with no body would then pass as non-empty.
   - N4 (unterminated quote handling) and N12 (keep parsing after an unparseable line) change no fixture output.
   - Optional seeds: `name: x  # comment` in a good skill, and `description: >` alone in a bad one.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C2 | N/A static lint of Markdown frontmatter; no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no model training or splits |

## Escalation

Round 3/3 with REJECTED = 1, and the launch prompt records no authorisation for an extra round. The loop stops here, and the orchestrator escalates to Daniel.

| id | judge position | architect position |
|---|---|---|
| S1 | Weakening `subagent-ref`'s quote condition (the explicitly listed `agentType: 'x'` form) to double quotes only passes all 4 tests (N14 survives). Every seeded dangling ref is double-quoted, and the plugin's own recipes use the single-quoted form. Fix: re-quote `typer.md`'s seed as `'ghost-two'` (no count change) | "Each of the three rule conditions the judge named now has a seeded defect and a mutant" (design :12-15); "34/34 killed" (:17, :748). True for the conditions named in r2; N14 is a new mutant this round |
