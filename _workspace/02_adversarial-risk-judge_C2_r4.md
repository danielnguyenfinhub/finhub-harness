TOTALS: UPHELD 21 / REJECTED 2 / UNVERIFIED 0 — round 4 (authorised)

# Adversarial verdict: C2 lint script (revision 3)

- Audited file: _workspace/02_strategy-architect_C2.md (revision 3)
- Audited: 2026-10-03
- Extra round authorised by Daniel: 2026-10-03
- Re-audited this round: S1, A8 (count 23), A20 (new, NET-NEW), and the revision-3 changes for notes (a) non-UTF-8, (b) test 1 stderr capture, (c) parser details (trailing ` # comment` cut, folded `>` marker), plus mutants M35-M39. I also added one new substance row, S3, for a defect in the new `read()` helper.
- Carried forward unchanged as UPHELD: A1-A7, A9-A19, S2.
- Simulation: my own scratch copy at `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/j4/`.
  - `repo/` is a fresh copy of the real repo. I extracted F1, F2 and all 28 fixture files (22 bad, 6 good) with `j4/extract.py`, writing byte 0xE9 for `<0xE9>`.
  - `mrepo/` is an isolated copy used for mutants (`j4/mut4.py`, 61 mutants).
  - `fz/` holds the fuzz runs (`j4/fuzz4.py`); `dv/` holds the r2-vs-r3 diff; `fx2/` holds the verified fix.
  - I did not use the architect's numbers or scripts. Nothing was written into the repo except this file.
- Row count: 20 Authority List rows (A1-A20) plus 3 substance rows (S1-S3).

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A7, A9-A19 | UPHELD | (r1/r2 rows, unchanged) | carried forward | Not re-audited, per the launch prompt |
| A8 | UPHELD | NET-NEW; backlog :92; deepseek index.ts:993-995 | carried from r1 | The count now reads "not among the 23 errors" (:871). My run gives `23 error(s), 4 warning(s)`, and `owner` appears only as a WARN line. The figure 23 also matches test 1's 23 expected tuples (:351-375) and P1 (:747) |
| A20 | UPHELD | NET-NEW (added r3): judge's r3 note (a); no reference lints file encodings | — | A reason is stated, and no port map contradicts it. The named check can fail, as I showed: the r3 test 1 FAILS against the r1 and r2 scripts (`'Traceback' is contained here: Traceback (most recent call last):`, UnicodeDecodeError on `bad-bytes`). M36 and M37 are killed. On my fuzz set, a non-UTF-8 byte gives `ERROR <file>: encoding not valid UTF-8 ...`. The run then continues: the sentinel `dir-name` finding is still printed, exit is 1, and there is no Traceback. Two defects in how the rule is implemented and tested are counted separately under S1 and S3 |

## Substance

| id | verdict | finding | evidence | fix |
|---|---|---|---|---|
| S1 | **REJECTED** | **N14 is fixed.** With `typer.md` now `agentType: 'ghost-two'` and `caller.md` still `"ghost"`, N14/M35 is killed, and so is the reverse narrowing to `[']` (F2). All earlier mutants are killed again: X1-X5b, X6, X7-X30, X14, X17, X17b, X18, X19, X24, N1-N3, N5-N11, N13 and N14. **New gap, in a stated rule condition:** the `encoding` row's scope is "all files read" (:161), and the r3 notes say "Both read sites use it: the top-level files and the nested `SKILL.md` scan" (:15). The nested read site (:300) is not pinned: no nested fixture is non-UTF-8. Two mutants of that one line pass all 4 tests: (F1) the nested site decodes with replacement but never reports, so a nested non-UTF-8 file passes silently; (F13) the nested site uses strict `read_text(encoding="utf-8")`. F13 is M37 applied to one of the two sites, and it brings back the r2 crash: `UnicodeDecodeError` and no findings. This is the same class as r3's N14 and r2's X18/X19 (nested-scope conditions), so it is held to the same bar | Probe `pn/` (a valid `skills/ok/SKILL.md` plus `references/n/SKILL.md` containing `caf\xe9`). Original: `ERROR pn/skills/ok/references/n/SKILL.md: encoding not valid UTF-8 ...`, exit 1. F1 mutant: `0 error(s), 0 warning(s)`, exit **0**, `pytest`: **4 passed**. F13 mutant: `UnicodeDecodeError ... 0xe9`, `pytest`: **4 passed** | Append one raw 0xE9 line to `harness_bad/skills/bad-orchestrator/references/deep/more/SKILL.md` and add `("references/deep/more/SKILL.md", "encoding not valid UTF-8")` to test 1. The total goes to **24 errors, 4 warnings**. Verified in `fx2/`: F1 and F13 are both killed, and the script stays at 150 lines |
| S2 | UPHELD | carried from r3 | — | — |
| S3 | **REJECTED** | **False `encoding` ERROR on a valid UTF-8 file.** `read()` (:200-204) reports whenever the decoded text contains U+FFFD. A file that is valid UTF-8 and contains a literal U+FFFD (bytes EF BF BD) is therefore reported `not valid UTF-8`, and the run exits 1. The packager (E3) would then refuse to package a valid plugin. The Rules row says the rule fires only when "the file is not valid UTF-8" (:161), so the code contradicts its own stated condition. No fixture pins the valid case | Fuzz case `literal-fffd-valid` (`description: "replacement char � shown"`, encoded UTF-8): `ERROR ...: encoding not valid UTF-8 (undecodable bytes replaced)`, exit 1. Today no `.md` under `.claude`, `skills` or `references` contains U+FFFD, so P3 is unaffected | Same line count: `text = (raw := path.read_bytes()).decode("utf-8", errors="replace")`, then `if text.encode() != raw:`. Valid UTF-8 round-trips exactly, and invalid bytes do not. Pin it with a line containing a literal U+FFFD in good `notes-style`. Verified in `fx2/` with S1's fix: the script is **150** lines; bad fixture `24 error(s), 4 warning(s)`; good fixture `0/0`; `pytest`: 4 passed; mypy --strict, ruff and black are clean. The current r3 `read()` FAILS test 2 against the new seed (`1 failed, 3 passed`), so the seed can fail |

## Notes (a), (b), (c): my checks

- **(a) non-UTF-8.** Fuzz results on r3; each case sits next to a sentinel `wrong-dir` skill:
  - These cases each give an `encoding` ERROR, exit 1, no Traceback, and the sentinel `dir-name` still printed: invalid byte in the frontmatter value; latin-1 name; mixed UTF-8 + latin-1; UTF-16; truncated multibyte sequence; encoded surrogate bytes; a 1 MB file with a bad byte at the end; a non-UTF-8 agent file.
  - These cases give no encoding error and no crash: BOM (a `frontmatter` ERROR, because line 1 is not `---`), CRLF (accepted), CR-only, NUL, an empty file, a 1 MB clean file, and U+2028.
  - Remaining crash paths are not covered by any claim; see the notes below.
- **(b) stderr capture.** `lint()` now returns `run.stdout + run.stderr` (:345).
  - The r3 test 1 run against the **r1** script FAILS at `assert code == 1 and "Traceback" not in out`, with `'Traceback' is contained here`. Against the r2 script it fails in the same way. Against r3 it passes.
  - With the old stdout-only `lint()`, the same r1 run gets past that assertion and fails later, on the missing `wrong-dir` finding. So the r3 change is what makes the Traceback clause able to fail.
- **(c) parser details.** N7/M38 (comment cut dropped) is killed by `notes-style`. N11/M39 (block marker strip dropped) is killed by the folded 1024-char description, which measures 1026.

## Mutation run (`j4/mut4.py`, 61 mutants on r3, 52 killed)

| survivor | stated rule condition? | note |
|---|---|---|
| F1, F13 (nested read site) | **yes**: `encoding` "all files read" (:161), plus the r3 note at :15 | counted as S1 |
| X6b | no | equivalent mutant, as in r3: the `"---" not in lines[1:]` guard stays |
| N4 (unterminated quote treated as quoted) | no: A16 parser detail | no fixture difference, as in r3 |
| N12 (parsing continues after an unparseable line) | no | the extra findings coincide with the existing ones, as in r3 |
| F3 (JSON-quoted key `"subagent_type": "x"` form dropped) | no: the Rules row names `subagent_type: "x"` / `agentType: 'x'` only | no real file uses the JSON-key form (I grepped `.claude` and `skills`) |
| F6 (comment cut at any `#`), F8 (cut requires two spaces) | no: parser paragraph (:165), not a Rules row | `notes-style` pins only `name: x  # c` with two spaces. A single-space `name: x # c` or `C# notes` is not pinned |
| F7 (`\|` block marker not stripped), F10 (chomping `>-` / `\|+` not stripped) | no: parser paragraph (:165) | only a bare `>` is pinned |

Killed among the fresh mutants: F2 (`[']` only), F4 (encoding as WARN), F5 (`errors="ignore"`), F9 (report only on more than one replacement character), F11 (skip the file after an encoding error), F12 (message changed). M35-M39 correspond to N14, M36, M37, N7 and N11, and all are killed.

## Re-run of the design's proof (all pass; not findings)

- **P1:** 23 ERROR + 4 WARN, matching the list exactly. Last line `lint_harness: 23 error(s), 4 warning(s)`, exit 1, stderr empty.
- **P2:** `0 error(s), 0 warning(s)`, exit 0.
- **P3:** `.claude` gives `0 error(s), 6 warning(s)` (five agents with no `model:`, plus the orchestrator description at 1259 chars), exit 0. `.` gives `0/0`, exit 0. Both hold on the scratch copy and on the real tree.
- **P4:** `wc -l` = **150**, at the cap and within it. `mypy --strict` on F1+F2: `Success: no issues found in 2 source files`. `ruff`: `All checks passed!`. `black --check`: `2 files would be left unchanged`.
- **Fold check.** `diff` of the r2 and r3 scripts shows exactly three changes: `read()` added and used at both read sites; the `name, desc` line folded; and `if not m: return set()` folded into `... if m else []`. Both folds are semantically equivalent. The r2 and r3 outputs (stdout, stderr, exit) are **identical on 14/14 targets**: the r3 bad fixture minus `bad-bytes` (22/4), the r3 good fixture, the r2 bad and good fixtures, `.claude` and the root on both the scratch copy and the real repo, and 6 valid-UTF-8 fuzz dirs (bare keys, CRLF, NUL, BOM, empty file, connectors). The only behaviour change is the encoding handling.
- **P5:** the full suite in the scratch copy gives **895 passed, 10 skipped**. That is the design's total: the 891 baseline plus 4 new tests. `tests/test_lint_harness.py` gives 4 passed.
- **P6/P12 (E3 applied in scratch).**
  - Greps: **1 / 0 / 1**.
  - Packager prints `lint_harness: 0 error(s), 0 warning(s)` plus the three dist lines, exit **0**, and the skill zip holds the script **once**.
  - `check-harness-refs.sh` exits 0 with 0 FAIL lines.
  - With a nested `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(team="x")`, the run prints `ERROR ... v1-artefact line 1: TeamCreate(` and `Validation failed; nothing packaged.`, exit **1**. With the probe removed, exit is 0 again.

## Stale numbers in the design (fix with S1/S3; not counted)

- :120 (Target, F1 row): "**new**, 146 lines". The script is 150.
- :750 (P4 expected): "**≤150** (simulated 146)". The simulated figure is 150.
- Every other 9/16/22/28/34 figure is in the revision 1/2 history (:46-:78) and is correct as history. A20's "the other 22" (:883) is correct (23 - 1). Mutant ranges (M1-M39, 39/39 at :23, :89, :795) are consistent. After the S1 fix, 23 becomes 24 in test 1, P1, A8, A20 ("the other 23"), F3 and the r4 notes.

## Non-blocking notes (not counted)

1. **Crash paths outside encoding (OSError).** Each of these ends with a Traceback, exit 1, and **all findings lost**, including the sentinel:
   - `skills/x/SKILL.md` that is a directory: `IsADirectoryError`. The same happens for `agents/x.md` as a directory and for a nested `SKILL.md` directory.
   - A dangling symlink `agents/dangle.md`: `FileNotFoundError`.
   - An unreadable file, tested as root with `CAP_DAC_OVERRIDE` dropped: `PermissionError`.
   - A FIFO named `SKILL.md`: the run **hangs** (killed at 20 s).

   All except the FIFO fail closed, and no claim covers them. Suggested: in `read()`, catch `OSError` and report `ERROR <file>: encoding unreadable (<errno>)`, returning `""`, or skip non-regular files (`path.is_file()`). Otherwise, list them under Does not cover. Mind the 150-line cap.
2. **Unpinned parser details** (F3, F6, F7, F8, F10, N4, N12 above). Optional seeds: `name: x # c` with a single space, `description: |` and `description: >-` in good skills.
3. **BOM.** A UTF-8 file with a BOM is valid UTF-8, but it gets `frontmatter missing ---`. This is acceptable fail-closed behaviour, but the message does not say why. Consider listing it under Does not cover.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C2 | N/A static lint of Markdown frontmatter; no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no model training or splits |

## Escalation

Round 4 (authorised) ends with REJECTED = 2. The launch prompt authorises no further round, so the loop stops here and the orchestrator escalates to Daniel. Both fixes are small and were verified together in `j4/fx2/`: the script stays at 150 lines; bad fixture 24/4; good fixture 0/0; 4 passed; mypy, ruff and black clean.

| id | judge position | architect position (from the design) |
|---|---|---|
| S1 | The nested read site of the `encoding` rule has no seed. F1 (no report) and F13 (strict decode, the r2 crash) both pass all tests. Fix: one 0xE9 byte in `references/deep/more/SKILL.md` plus one test tuple | "Both read sites use it" (:15); M37 is killed (:835), but M37 mutates the shared `errors=` argument, which affects both sites at once |
| S3 | `read()` flags a valid UTF-8 file containing U+FFFD as "not valid UTF-8", contradicting the Rules row (:161). Fix: `if text.encode() != raw:` (same line count) plus a U+FFFD line in a good fixture | not addressed: the design treats U+FFFD in the decoded text as proof of bad bytes |
