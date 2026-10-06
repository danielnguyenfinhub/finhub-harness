TOTALS: UPHELD 23 / REJECTED 0 / UNVERIFIED 0 — round 5 (authorised)

# Adversarial verdict: C2 lint script (revision 4)

- Audited file: _workspace/02_strategy-architect_C2.md (revision 4)
- Audited: 2026-10-03
- Extra round authorised by Daniel: 2026-10-03
- Re-audited this round: S1, S3, A8 (count 24), A20 (encoding rule), mutants M36 (re-anchored) and M40-M42, the stale-number fixes ("146" -> 150), and the new Does not cover entries.
- Carried forward unchanged as UPHELD: A1-A7, A9-A19, S2.
- Simulation: my own scratch copy at `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/j5/`.
  - `repo/` is a fresh tar copy of the real repo. F1, F2 and all 28 fixture files (22 bad, 6 good) were extracted from the design by `j5/extract.py`, with the 0xE9 bytes written raw. Byte checks: `notes-style` contains `EF BF BD`; `bad-bytes` and `deep/more` each contain exactly one 0xE9.
  - E1, E2 and E3 were applied to `repo/` from the design's own blocks, with anchors asserted at lines 142, 169, 24, 45 and 49.
  - `mrepo/` is an isolated copy for mutants (`j5/mut5.py`, 79 mutants). `fz/` holds the fuzz runs. `probe5.py` is the three-place encoding probe.
  - I did not use the architect's numbers or scripts. Nothing was written into the repo except this file.
- Row count: 20 Authority List rows (A1-A20) plus 3 substance rows (S1-S3).

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A7, A9-A19 | UPHELD | (r1/r2 rows, unchanged) | carried forward | Not re-audited, per the launch prompt |
| A8 | UPHELD | NET-NEW; backlog :92; deepseek index.ts:993-995 | carried from r1 | The count now reads "not among the 24 errors" (:906). My run gives `lint_harness: 24 error(s), 4 warning(s)`, and `owner` appears only as a `WARN ... unknown-key` line. 24 also matches test 1's 24 tuples (:376-399) and the 24 items listed in P1 (:774) |
| A20 | UPHELD | NET-NEW (added r3; CHANGED r4): judge's r3 note (a); no reference lints file encodings | — | A reason is stated, and no port map contradicts it. Every named verification can fail, as shown under S1/S3: the r1 and r2 scripts fail test 1 (`'Traceback' is contained here`), the r3 script fails test 2, and M36, M37, M40, M41 and M42 are all killed. "the other 22" (:918) = 24 - 2 encoding errors, which is correct |

## Substance

| id | verdict | finding | evidence | fix |
|---|---|---|---|---|
| S1 | UPHELD | **Fixed.** The nested read site is now pinned by the 0xE9 line in `references/deep/more/SKILL.md` and its test-1 tuple (:398). My r4 mutants are both killed: F1/M40 (nested read decodes but never reports) and F13/M41 (nested strict `read_text`) | `mut5.py`: `F1 nested files bypass read()`: killed (test 1). `F13 nested read strict`: killed (test 1). The probe (`probe5.py`, a nested `skills/ok/references/n/SKILL.md` next to a `wrong-dir` sentinel) gives `enc=1`, `skills/ok/references/n/SKILL.md: encoding not valid UTF-8 ...`, sentinel still printed, exit 1, no Traceback | — |
| S2 | UPHELD | carried from r3 | — | — |
| S3 | UPHELD | **Fixed.** `read()` (:224-228) now reports only when `text.encode() != raw`. A valid file containing U+FFFD passes; a real bad byte gives exactly one `encoding` ERROR, and the scan continues | `probe5.py` on the r4 script, with each case next to a `wrong-dir` sentinel. **U+FFFD (EF BF BD)** in a skill, an agent and a nested `SKILL.md`: `enc=0` in all three; only the sentinel error remains (`1 error(s)`). **0xE9** in each of the three: `enc=1` for exactly that file (`skills/s1/SKILL.md`, `agents/ag.md`, `skills/ok/references/n/SKILL.md`), sentinel still printed, `2 error(s)`, exit 1, `Traceback` absent from stderr. The r3 script (`j4/r3.py`) on the same probe gives a false `enc=1` in all three U+FFFD cases. Against the r4 tests, the r3 script FAILS `test_clean_fixture_passes_without_warnings` (`1 failed, 3 passed`). So the new good seed can fail, and M42 is killed | — |

## Mutation run (`j5/mut5.py`: 79 mutants on r4, 65 killed)

Mutants rerun: X1-X30 (including X3-X10, X14, X17, X17b, X18, X19, X24); N1-N14 (including N4, N7, N11, N12, N14); F1-F13; M36 (r4 anchor `if text.encode() != raw:`), M37 and M42. There are 16 fresh mutants, G1-G16. Killed: X1-X6, X7-X30, X17b, N1-N3, N5-N11, N13, N14, M36, M37, M42, F1, F2, F4, F9 (re-anchored), F11, F12, F13, and G1-G4, G7-G12, G15.

| survivor | stated rule condition? | note |
|---|---|---|
| X6b | no | equivalent mutant (as in r3 and r4) |
| N4, N12, F3, F6, F7, F8, F10 | no: parser details (:189) and the JSON-key `REF_RE` form | unchanged from r4; non-blocking |
| F5 (`errors="ignore"`), G5 (`errors="backslashreplace"`) | no: equivalent for detection | The round-trip compare still fires, because `ignore` drops the bad byte and `backslashreplace` expands it. Either way `text.encode() != raw`. Only the decoded text of an already-reported file differs. F5 was killed in r4 only because r3 detected via U+FFFD |
| G14 (`text.encode() not in raw`) | no: equivalent | An invalid file re-encodes to a byte string of the same length or longer that differs from `raw`, so it is never a substring of `raw`. A valid file round-trips exactly |
| G6 (`utf-8-sig` decode) | borderline; non-blocking | A UTF-8 file with a BOM gets an `encoding` ERROR instead of `frontmatter missing`. It is one ERROR either way, with exit 1, so no valid harness is blocked and no finding is lost. This contradicts the documented BOM behaviour (:889), which no fixture pins. Optional seed: a BOM'd skill in the bad fixture |
| G13 (nested files read only when they contain `Team`) | no: contrived content filter | Both nested seeds contain a v1 token. Any finite fixture admits content-sniffing mutants like this one |
| G16 (agents bypass `read()` via an added `if path in skills else ...` branch) | the scope is stated ("all files read", :185), but this is not a natural mutant of the r4 code | Agents and skills share **one** read statement (:310). Every natural mutation of that statement (G7 strict, G8 never reports) is killed by `bad-bytes`. G16 survives only because no **agent** fixture holds a bad byte. This differs from r4 S1, where the nested read was a separate statement. **QA note:** if the builder restyles F1 to read agents and skills in separate statements, put a 0xE9 byte in a bad agent (e.g. `nocomment.md`, taking the total to 25), or QA must FAIL it |

## Re-run of the design's proof (all pass)

- **P1:** `24 error(s), 4 warning(s)`, exit 1, stderr empty (0 bytes). The 24 ERROR lines match P1's list exactly, including `bad-bytes` and `references/deep/more/SKILL.md` encoding.
- **P2:** `0 error(s), 0 warning(s)`, exit 0, with the U+FFFD line present in `notes-style`.
- **P3:** `.claude` gives `0 error(s), 6 warning(s)` (5 agents with no `model:`, plus the orchestrator description at 1259 chars), exit 0. `.` gives `0/0`, exit 0.
- **P4:** `wc -l` = **150**. `mypy --strict` on F1+F2: `Success: no issues found in 2 source files`. `ruff`: `All checks passed!`. `black --check`: `28 files would be left unchanged.`
- **P5:** full suite in the scratch copy: **895 passed, 10 skipped**. That is the design's total (891 baseline plus 4 new). `tests/test_lint_harness.py` gives 4 passed.
- **Test 1 can fail:** the r1 script (`j2/F1.orig`, the `raw[:1] in "\"'"` crash) FAILS test 1 with `'Traceback' is contained here`. The r2 script fails the same way.
- **P6/P12 (E1-E3 applied in scratch):**
  - The packager prints `lint_harness: 0 error(s), 0 warning(s)` and the three dist lines, then exits **0**. The skill zip holds the script **once**.
  - Greps: **1 / 0 / 1**.
  - P8-P11: `2`, `1`, `0`, `198`.
  - `check-harness-refs.sh` exits 0 with 0 FAIL lines.
  - With a nested `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(team="x")`, the run prints `ERROR ... v1-artefact line 2: TeamCreate(` and `Validation failed; nothing packaged.`, exit **1**. With the probe removed, exit is 0 again.

## Stale numbers (grep of the design)

- `146`: appears at :70, in the revision 2 history, and at :144, inside the F1 row's own marker "(CHANGED r4: was a stale 146)". The current value, 150, is stated beside it. P4 (:777) now reads "simulated 150".
- `23` as the bad-fixture total: appears only at :35, :47 and :50, all in the revision 3 history.
- `22`: :70, :71 and :75 are revision 2 history. The other three are not error totals and are correct: :136 is the line range `package-plugin.sh:11-22`; :146 is the file count (6 + 14 + 2 = 22 files); :918 "the other 22" is 24 - 2.
- The mutant totals 34 and 39 appear only in history. The current text says 42 (:17, :23, :113, :823), and the table has 42 rows, M1-M42.
- **Result:** outside the revision history, no stale value remains.

## New Does not cover entries (:886-889): checked against the r4 script

- A directory named `SKILL.md` or `agents/x.md`, and a nested `SKILL.md` directory, each give `IsADirectoryError` with a traceback and all findings lost.
- A dangling agent symlink gives `FileNotFoundError`.
- A FIFO makes the run hang (killed at 20 s).
- A BOM file gives `frontmatter missing --- delimited frontmatter`.
- Unreadable file: this run's `setpriv` probe could not open the script itself, so it was inconclusive. r4 observed `PermissionError`, and the read path (`read_bytes`) is unchanged.
- All five entries are accurate as written. They are disclosed limits, not claims.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C2 | N/A static lint of Markdown frontmatter; no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no model training or splits |
