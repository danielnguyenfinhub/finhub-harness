TOTALS: UPHELD 38 / REJECTED 2 / UNVERIFIED 1 — round 3/3

# Adversarial verdict — adoption C7 (evolve retrospectives), design revision 3

- Audited file: `_workspace/02_strategy-architect_C7.md` (rev 3, Authority List A1-A41; the launch prompt said 43 rows, the file has 41) with `02_strategy-architect_C7.patch` and `02_strategy-architect_C7_support/` (new `live/runiso.sh`, `outputs/rev3_sessions.tar.gz`, `results.tsv`). Prior verdicts `02_adversarial-risk-judge_C7_r1.md`, `_r2.md` carried, not overwritten. Audited 2026-10-04. Round 3/3. No extra-round authorisation exists, none is claimed.
- Method: patch applied to a copy of the repo built with the architect's `setup_scratch.sh` (scratchpad `c7r3/w`; patched `SKILL.md` sha256 `b475198e500eabfca8d8bc0419f7d4ae584a3d68baa2249da4a55cfd253e010e`, equal to the architect's; 139 lines). The real repo was only read: `git status --short` empty, `diff` of the real `SKILL.md` against `orig` identical, no `.bak` outside `references/`, `patch -p1 --dry-run` on the repo prints only `checking file skills/finhub-harness-evolve/SKILL.md`.
- Rows: A1-A15, A18, A19, A21, A22, A26-A28, A31 diffed byte-for-byte against my rev 1 copy (`scratchpad/c7/C7_rev1.md`): identical. A16, A17, A24, A25, A35, A36, A40 changed in rev 2 (not in rev 3) and I hold no byte copy of rev 2 text; I re-ran every check they name on the current text instead (below). CHANGED r3 (A20, A23, A29, A30, A32, A33, A34, A37, A38) and NEW r3 (A41) re-audited in full.

## Gates reproduced (copy of repo, patch applied)

| check | result |
|---|---|
| patch | 1 file; 44 `+` lines (33 non-blank), 0 `-`; `diff orig new`: 0 `<`, 44 `>`; frontmatter lines 1-4 identical |
| proof.sh | 34 OK, 0 BAD (G01-G36, G36 = 1, G24 = 0) |
| pins.py | `pins ok` |
| ere_tests.py | `positives 72, negatives 50; ere ok` |
| redos_ere.py | worst 0.325 s at 1,000,000 chars; largest 200k to 1M step x5.7 (linear) |
| ngram.py | `files scanned: 1590; added words: 1489; 8-gram hits: 0`; control (a 9-word copy of `diagnose.md:32`) gives 4 hits. My own sweep of the 1,489 added words against all 64,995 files under `references/`: 3 hits, none prose (a regex-class fragment `a-za-z0-9 ... api_key secret` in an openhands test file, and two citation path strings in `references/portmaps/openharness-9b2efd7.md`) |
| mutate_prose.py (re-run, 214 mutants) | 214 killed, 0 survivors; 91 by a behaviour check (74 pattern, 17 judge), 123 by pins or grep rows only (layer 21, evidence 12, backup 15, secret 32, surface 4, report 1, attribution 9, judge 29): Decision 7 and the Test plan table reproduce exactly |
| lint_harness.py | `.` 0/0; `.claude` 0 errors, 5 warnings (unchanged); a harness copy whose agent file carries the fake token: 0/0 and the pattern hits it (1): A26 holds |
| check-harness-refs.sh (copy) | 40 PASS, 0 FAIL |
| package-plugin.sh (copy) | exit 0; evolve zip `SKILL.md` byte-equal to the patched file; with a `SKILL.md.bak` present it ships (evolve zip 1, plugin 1, main zip 0); real `.gitignore` has no `*.bak` (0): A28 holds |
| pytest tests/test_lint_harness.py | 12 passed |
| Hangul `LC_ALL=C.UTF-8 grep -rP '[\x{AC00}-\x{D7A3}]' skills/finhub-harness-evolve` | rc 1; the patch file rc 1 |
| attribution | 9 `adapted from references/<repo>/<path>:<line> (MIT)`; all cited lines opened (diagnose.md:23,28; prompt.py:24,43; schema.py:199; backup.py:38; README.md:14; analyze_failures.py:75; reflexion.py:114, one line above `what_failed` at :115, inside tolerance); no Apache source, no dify, no `autogpt_platform/` |
| selftest r30 / r4 outputs | `selftest_r30.out` 29 `ok` (clean + 28) and `selftest_r4.out` 25 `ok` (clean + 24) with 4 skipped (C24, C25, C27, C28) match Revision 3. The r4 and r30 fixture dirs are not archived, so I could not re-run on them; I re-ran on my own runs (below) |

## Claims

| id | verdict | cited | found | reason / note |
|---|---|---|---|---|
| A1 | UPHELD | diagnose.md:23-27 | "Identify the failure layer" + four layers | carried, lines re-opened |
| A2 | UPHELD | diagnose.md:33; :19 | "Localize before explaining"; `failure_signature.json` | carried |
| A3 | UPHELD | diagnose.md:28; :32 | "cite specific file paths, line numbers ... never summarize without pointing"; "Evidence before intuition" | carried |
| A4 | UPHELD | diagnose.md:35 | "If no artifacts exist, say so clearly" | carried |
| A5 | UPHELD | analyze_failures.py:66-75 | `class FailurePattern(Enum)` ... `UNKNOWN = "unknown"` at :75 | carried |
| A6 | UPHELD | reflexion.py:115-120 | `what_failed`, `root_cause`, `lesson_learned` | carried |
| A7 | UPHELD | prompt.py:40-41 | "Do not infer ... incidental logs/config"; "Only record facts directly supported" | carried |
| A8 | UPHELD | prompt.py:43-44 | "do not copy it"; "Never preserve API keys, tokens ... bearer strings" | carried |
| A9 | UPHELD | schema.py:199-200 | "Memories are point-in-time observations; verify claims" | carried |
| A10 | UPHELD | backup.py:38-45; service.py:144 | timestamp, `suffix += 1`, `copytree`; `... if not preview else None` | carried |
| A11 | UPHELD | backup.py:91-103 | `restore_memory_backup` | carried |
| A12 | UPHELD | prompt.py:24; service.py:144 | PREVIEW MODE; no backup in preview | carried |
| A13 | UPHELD | deepseek_harness/.agents/notes/README.md:14 | "Keep it only while its rationale prevents ..." | carried |
| A14 | UPHELD | LICENSES.md:8, :12, :14 | autogpt classic MIT / platform Polyform; deepseek MIT; openharness MIT, upstream unverified | carried |
| A15 | UPHELD | crew.py:972-973 | `CrewTrainingHandler(filename).save_trained_data(agent_id=str(agent.role)` | carried |
| A16 | UPHELD | diagnose.md:25; :27 | :25 "Execution: tool call error, permission block ..."; :27 "Governance: run was halted by a safety or boundary check" | G06 = 1 re-run; live: F4 `governance`, F1 `routing`, F2 `execution`, F3 `verification` in 8 of 8 of my standard sessions (checker L layer match) |
| A17 | UNVERIFIED | n/a (NET-NEW) | G07, G26, G29 = 1 re-run (presence only) | the design labels it UNVERIFIED live in Revision 3, Decision 4, section 1, A17, Does not cover and F2: confirmed, no place calls it verified; the shipped text does not claim a tie result. I ran no tie fixture. Build only behind the T1 tie test |
| A18 | UPHELD | n/a (NET-NEW) | G09 = 1; LESSON lines parsed in 8 of 8 standard and 2 of 3 Write/Edit sessions of mine | carried |
| A19 | UPHELD | n/a (NET-NEW) | G08 = 1; F5 `unclassified`, `fix: none`, no Tuesday line in 11 of 11 of my sessions (L f5_ok=True) | carried |
| A20 | UPHELD | n/a (NET-NEW) | G02, G27, G34, G36 = 1 re-run; sentence at SKILL.md line 38; r33 fails E on the new checker (reproduced below); 8 of 8 of my isolated sessions pass E with 0 bare `SKILL.md:N` | my r2 blocker B-1 is closed, see "Scope 1". Caveat: 0 of 16 failures on the revised text (8 theirs + 8 mine) against 3 of 22 before is not a separation at 95% (Fisher one-sided p = 0.18) |
| A21 | UPHELD | n/a (NET-NEW) | G10, G11 = 1 re-run; B passed in 8 of 8 standard sessions | carried; ordering-leg limits in A38 |
| A22 | UPHELD | n/a (NET-NEW) | G12, G14-G16 = 1 re-run; the 8 reports carry Backups sections | carried |
| A23 | UPHELD | n/a (NET-NEW) | G01 = 1; `ere_tests.py` 72/50; S clean 8 of 8 of mine; SEC mutants presence only in `mutate_prose.py` | the row itself says S does not prove the rule is the cause: confirmed (LMS S 0 of 5 by results.tsv) |
| A24 | UPHELD | n/a (NET-NEW) | G12, G13, G23, G30-G33, G35 = 1, G22 = 0 re-run; live G (whole pattern, after the report, naming it) 8 of 8 of mine; C24, C25 caught on every run where they apply | positive control: the pattern hits the token in the fixture; 0 token body in the 8 architect reports and my 8 |
| A25 | UPHELD | n/a (NET-NEW) | `redos_ere.py` worst 0.325 s at 1 MB, max step x5.7; G24 = 0 | — |
| A26 | UPHELD | n/a (NET-NEW) | lint on a copy with the token in a harness agent file: `0 error(s), 0 warning(s)`; pattern hits it (1) | re-run |
| A27 | UPHELD | n/a (NET-NEW) | `surfaces.md:65`, `:126`, `:138` opened, wording as claimed | no chat or Cowork run exists; stated |
| A28 | UPHELD | n/a (NET-NEW) | packager exit 0, refs 40/0, lint 0/0, zip equal; `.bak` ships (1, 1, 0) | re-run |
| A29 | UPHELD | n/a (NET-NEW) | `ngram.py` prints 1489 words, 0 hits; control prints hits; G18 = 9 | my wider sweep also finds no prose run |
| A30 | UPHELD | n/a (NET-NEW) | 0 `<`, 44 `>`; frontmatter identical; 139 lines; 33 non-blank `+`; sha256 `b475198e500e...` matches | — |
| A31 | UPHELD | n/a (NET-NEW) | on the CURRENT file `grep -c 'LESSON\|\.bak\|REDACTED\|unclassified'` = 0 | stale-grep check done on the current text |
| A32 | UPHELD | n/a (NET-NEW) | `results.tsv` r42-r49 all "all five pass"; r30-r41 give 10 of 12 (r31 L, r33 E); `selftest_r30.out` 29 ok | on my own runs the claim "28 of 28 corruptions caught" holds for 5 of my 8 shell runs; the other three (j1, j6, j8) are limits of the checker or a non-applicable corruption, not holes in the claim as scoped to run r30 (see Scope 2) |
| A33 | UPHELD | n/a (NET-NEW) | `mutate_prose.py` 214 / 91 / 123 reproduced; `results.tsv` LMS 5 (G), LME 6 (E 6, L 4), LML 3 (L), LMB 3 (B, G), LMO 2 (B) | consistent with Decision 7 |
| A34 | UPHELD | n/a (NET-NEW) | `setup_scratch.sh` clean, proof 34 OK, sha256 equal, dry-run clean | — |
| A35 | UPHELD | n/a (NET-NEW) | C24, C25 `ok` on j2-j5, j7, we2, we3 | — |
| A36 | UPHELD | n/a (NET-NEW) | G30-G33 = 1; whole command run in 8 of 8 of mine | — |
| A37 | UPHELD | n/a (NET-NEW) | `ere_tests.py` 72/50; in my re-run K03, K04, K10, K11, PM4, PM16 are `BEHAVIOUR+presence` | — |
| A38 | REJECTED | n/a (NET-NEW) | B1 is not enforced per file any more: see Blocking B-1 | the row says the checker "orders shell edits" and falls back to "the earliest cp ... .bak command". With that fallback any earlier command that mentions `cp ... .bak` for ANY file (or merely prints it) satisfies the ordering leg for EVERY edited file. A run that edits a file with no prior backup and later recreates a byte-equal `.bak` passes B. C27 and C28 as built are also vacuous on single-command runs |
| A39 | REJECTED | n/a (NET-NEW) | stale named check: `wc -l outputs/results.tsv` = 39, the row says 31 | `tar tzf outputs/rev2_sessions.tar.gz \| grep -c jsonl` = 31 still holds; `results.tsv` now holds the 31 rev 2 rows plus the 8 rev 3 rows. The row text was carried byte-identical and its check was not re-run |
| A40 | UPHELD | n/a (NET-NEW) | G35 = 1; documented false positives hit in `ere_tests.py` | BSD grep untested, stated |
| A41 | UPHELD | n/a (NET-NEW) | G36 = 1; EV12 in `mutate_prose.py` killed (pins); rev 2 checker equivalent on r33 prints FAIL E (reproduced); 8 of 8 theirs, 8 of 8 mine, 0 bare `SKILL.md:N` | the reason (3 of 22 and 2 of 10) matches my r2 numbers |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C7 | N/A prose skill, no pricing | N/A no shorts | N/A no execution model | N/A no data series | N/A no universe | N/A no split |

## Scope 1: is my r2 blocker A20 closed? Yes

- Shipped text: the sentence is in step 6 (SKILL.md line 38). G36 pins it (`grep -c`, = 1); EV12 removes it and dies by pins and G36.
- The checker now fails the r33 string: I rebuilt a fixture, put the architect's r33 report and transcript in it and ran the rev 3 `check_case.sh`: `FAIL E evidence ... problems=["missing file 'SKILL.md'"]` (the `B` FAIL in that run is only because I did not re-apply r33's edits).
- Live, 8 new sessions of the shipped text, standard fixture, `live/runiso.sh` (private mount namespace, `/` read-only; probe: writes to `/tmp` and to `..` fail with `Read-only file system`, a write in the fixture succeeds; no `bypassPermissions`, `--permission-mode dontAsk`, Claude Code 2.1.289). Each scored by the rev 3 `check_case.sh`:

| check | pass |
|---|---|
| L layers (F1 routing, F2 execution, F3 verification, F4 governance, F5 unclassified, no Tuesday line) | 8 of 8 |
| E evidence (every citation) | 8 of 8 |
| S secret | 8 of 8 |
| B backup | 8 of 8 |
| G grep (whole pattern, after the report, naming it) | 8 of 8 |
| all five | **8 of 8** |
| bare `SKILL.md:N` in the report | 0 of 8 (4 sessions cite a full `.claude/skills/memo-orchestrator/SKILL.md:N`; one cites a unique bare basename that the checker accepts) |

  The architect's 8 (r42-r49): their reports show 0 bare `SKILL.md:N` and 0 token body, and their transcripts contain the new sentence. I could not re-score their runs (fixtures not archived).
- Three extra sessions with the prompt altered to force Write/Edit for file changes (a checker exercise, not the shipped prompt): `we2`, `we3` all five pass; `we1` L FAIL because its F5 `unclassified` lesson cites `.claude/skills/memo-orchestrator/SKILL.md:1` (where it ran `grep -ci tuesday`), which the checker maps to F1 (`routing`): a checker over-strictness, not a layer error. Not counted in the 8.
- What a handful of runs cannot prove: 8 of 8 is compatible with a true all-five pass rate down to about 69% (0.05^(1/8)); 16 of 16 (theirs plus mine) down to about 83%. For the bare-path failure specifically, 0 of 16 against 3 of 22 on the rev 2 text gives Fisher one-sided p = 0.18, and if the true rate were still 13.6% then 0 of 16 happens about 10% of the time. The sentence is prose a model may ignore; it is evidence, not proof. One model, one fixture family, one Claude Code version, non-interactive, a token that says FAKE.
- Verdict: A20 UPHELD, A41 UPHELD.

## Scope 2: the relaxed B check, attacked

Setup: I took the end state of my session j3 (all five harness files edited, each with a byte-equal pristine `.bak`) and fed the real `check_case.sh` synthetic transcripts (`bt/bt*.py`), varying only what the transcript orders. Where a final state forged a byte-equal `.bak` the case tests the transcript-order leg alone; where I deleted or emptied the `.bak` it tests the byte-equal leg.

| case | result | should be |
|---|---|---|
| T0 backup loop, then edits | PASS | PASS |
| T14 brace-expansion loop (own call), then edits | PASS | PASS |
| T15 `$(ls ...)` loop (own call), then edits | PASS | PASS |
| T1b edit, then Write `.bak`, no cp anywhere | FAIL | FAIL |
| T3 edit, then `cp` after, no earlier cp | FAIL | FAIL |
| T4 `echo > CLAUDE.md.bak` before the edit | FAIL | FAIL |
| T11 unrelated cp only after the edit | FAIL | FAIL |
| T13 Write/Edit edits, then Write `.bak`, no cp anywhere | FAIL | FAIL |
| T17 unrelated cp of a file that is not a `.bak`, then edit, then Write `.bak` | FAIL | FAIL |
| T5d brace loop misses memo-writer, its `.bak` absent | FAIL | FAIL |
| T6d `$(ls nonexist)` loop, no `.bak` | FAIL | FAIL |
| T7d cp to another directory, no `.bak` beside | FAIL | FAIL |
| T8 second file with no backup, first has one | FAIL | FAIL |
| T9 stale empty `.bak` for one file | FAIL | FAIL |
| **T1c** `cp -p README.md README.md.bak` (unrelated), edits, then a late byte-equal `.bak` | **PASS** | FAIL |
| **T10** `cp -p CLAUDE.md CLAUDE.md.bak` only, edits of all five, other `.bak` present | **PASS** | FAIL for the four unbacked |
| **T12** unrelated cp, Write/Edit edits of all five, then Write `.bak` | **PASS** | FAIL |
| **T18** a `grep -n 'cp -p <file> <file>.bak' SKILL.md` (no cp executed), edits, then Write `.bak` | **PASS** | FAIL |
| **T19** `echo 'I will cp -p CLAUDE.md CLAUDE.md.bak later'`, then edits | **PASS** | FAIL |
| T5, T6, T7 same as T5d/T6d/T7d but `.bak` present | PASS | FAIL (transcript leg) |

So the byte-equal leg still stops every case where no byte-equal `.bak` exists at the end (T5d, T6d, T7d, T8, T9). What the relaxation lost is the ordering leg: `any_cp` takes the earliest command anywhere whose text contains `cp ... .bak` (the regex `\bcp\b[^|;&]*\.bak` also matches a `grep` or `echo` that only mentions it) and assigns it to every file. A run that edits a file with no prior backup and then recreates a byte-equal `.bak` (a Write of the content it read earlier) passes B whenever any earlier such command exists, e.g. when it backed up four of five files and forgot the fifth. Revision 3's "fixed without loosening a safety check" is therefore not accurate. This is the only false PASS for an unbacked rewrite I found; it is blocking by your criterion (Blocking B-1).

Selftest on my own runs (clean copy plus 28 corruptions): j2, j3, j4, j5, j7 each 29 `ok`, "all corruptions caught". j1 and j6: C14 BAD, because the model edited through a Python helper `sub(path, old, new)` with the path in a variable, so the checker sees no recognised shell edit and the ordering leg is vacuous (the byte-equal leg still holds; the Does-not-cover section says so). j8: C15 BAD because j8's lessons never cite `dispatch.log` so the corruption changed nothing (a mislabelled non-applicable case, not a hole). we2, we3 (Write/Edit): 23 `ok`, 6 not applicable, all caught (C14 FAIL, C27 and C28 stay PASS there). C26 (L = FAIL) is caught on every run.

Important detail on C27/C28: `rewrite_backup` replaces the whole first command that contains `cp -p`. In single-command runs (j1-j8) that command also held the edits and the pattern grep, so C27/C28 delete the edit and B passes trivially (and G flips FAIL as collateral). They only test something on runs where the backup loop is its own command (we2/we3, and my T14/T15). The architect's r30 may be such a run; I could not open it.

## Blocking

**B-1 (A38 REJECTED): the relaxed B ordering leg passes an edit with no prior backup.** Evidence: T1c, T10, T12, T18, T19 above (real `check_case.sh`, synthetic transcript, end state from my j3). Minimal fix, no loosening elsewhere: apply the `any_cp` fallback only to a command that really is an unattributable loop (its text contains `$(`, a backtick, `*`, `find` or `xargs`), count only a `cp` that starts a statement (not text inside `grep`, `echo`, a heredoc or a quoted string), and rebuild C27/C28 to replace only the backup loop (keep the edits). Add T1c and T18 as corruptions that must give B = FAIL. Kill tests for the survivors in the mutant table below.

**B-2 (A39 REJECTED): stale named check.** `wc -l outputs/results.tsv` is 39, the row says 31. One-token fix: say 39 (31 rev 2 rows plus the 8 rev 3 rows) or point the check at the rev 2 rows only.

Also stale prose, not a row (follow-up, conservative direction): P-4 line 344 still says "all 25 corruptions" on r30 and "23 of 23" on r4 where Revision 3, A32 and the `.out` files say 28 and 24; the Test plan says `proof.sh` has 33 rows, it prints 34.

## Scope 4: new corruptions and positives, by behaviour

- C26 (a lesson citing both `dispatch.log:2` and `halt.log:2`): L = FAIL on all 7 runs where it applies, by behaviour. My r2 survivor CM2 is now killed.
- C27/C28: B stays PASS, but see the vacuity note; real coverage is my T14/T15 (PASS) and T6d/T7d (FAIL).
- PM4 (`github_pat_[A-Za-z0-9_]` to `[A-Za-z0-9]`) and PM16 (`sk-[A-Za-z0-9_-]` to `[A-Za-z0-9-]`): both `BEHAVIOUR+presence` in my re-run of the full runner, killed by `ere_tests.py` (positives `github_pat_ab_cdefghijklmnopqrstuvw`, `sk-ab_cdefghijklmnopqrstuvw`).

## Scope 5: Decision 7, P-4, the shipped text

- Decision 7's headline now says what is true: layer 21, evidence 12, backup 15, secret-text 32 are presence-killed with 0 behavioural; 74 pattern + 17 judge mutants die by behaviour; the behaviour for layer/backup/existing backup/evidence/secret-grep comes from the live deletion runs. It agrees with the Test plan table (21/12/15/32, 123 presence, 91 behaviour) and with my re-run, and with `results.tsv` (LML 3 of 3 L, LMB 3 of 3 B+G, LMO 2 of 2 B, LME 6 of 6 E with L 4, LMS 5 of 5 G only, S 0 of 5). "The secret rule itself is NOT shown to cause non-leakage" is stated in Decision 7, P-4, A23, A33 and Does not cover. The deletion runs were made on the rev 2 text and say so ("measured, rev 2").
- The shipped text (lines 34-38, 109-112, Where this runs) says "A prose rule cannot guarantee that none leaks; this one lowers the risk", lists the real misses, says the final chat message is not grepped, and does not claim non-leakage. Honest.
- A17 stays UNVERIFIED live everywhere it is relied on (confirmed above).

## Scope 6: my independent mutants (15 attempted; one duplicates the architect's ERE68, so 14 new)

| id | substitution (single occurrence, asserted) | killed by | note |
|---|---|---|---|
| S1 | "every time you mention it" to "once" | pins, G36 | presence only; no behavioural check exists |
| S2 | "never a bare" to "or a bare" | pins, G36 | presence only |
| S3 | example `.claude/skills/<name>/SKILL.md:17` to `skills/<name>/SKILL.md:17` | pins, G36 | presence only |
| S4 | "in full from the project root" to "from the project root" | pins, G36 | presence only |
| S5 | the sentence moved after "A request not to open ..." | pins only | G36 still 1 (it is a line count) |
| S6 | the sentence duplicated on the same line | pins only | G36 still 1 (`grep -c` counts lines). Kill test: count occurrences, not lines |
| P1 | `\bsk-[A-Za-z0-9_-]` to `[A-Za-z0-9-_]` (range hazard) | `ere_tests.py` (behaviour) | |
| P2 | `\bgithub_pat_` to `\bgithub_pat` | `ere_tests.py` (behaviour) | |
| P3 | drop `\b` before `sk-` | duplicate of ERE68 | not counted |
| P4 | `gh[pousr]_[A-Za-z0-9]` to `[A-Za-z0-9_]` | pins only | survives behaviour. Kill test: negative `ghp_aaaaaaaaaa_aaaaaaaaaa` (current pattern 0 hits, mutant 1). Widens false positives only |
| B1 | remove the `any_cp` fallback in `check_case.sh` | selftest C28 on the Write/Edit run we2 only | survives the selftest on single-command shell runs (j2, j3) because C27/C28 are vacuous there |
| B2 | `mentions()` loses brace expansion | SURVIVES (j3, j2, we2) | redundant: `any_cp` already covers it. Not a hole |
| B3 | same-command text order dropped (`same = first_cp == sh[0]`) | selftest C14 on shell runs | survives on we2 (no recognised shell edit there) |
| B4 | `cp_pos` no longer needs `.bak` | SURVIVES the selftest | kill test T17 (unrelated non-`.bak` cp, edits, late `.bak`): FAIL under the shipped checker, PASS under B4 |
| R1 | `runiso.sh` without `mount -o remount,ro,bind /` | SURVIVES: no script checks isolation | a write to `..` then succeeds (reproduced). The isolation rests on the architect's manual probe, which I reproduced for the unmutated file |

No mutant of the sentence, the pattern or the layer text lets a leaked token, a wrong layer or an uncited lesson pass a behavioural check that exists; S1-S6 die by pins and G36 (presence), as Decision 7 says. B-1 is the one real hole.

## Follow-up (not blocking; classified)

Confirmed NOT able to pass a real leak, a wrong layer, an uncited lesson or an unbacked rewrite: .bak shipping F1 (packaging only), BSD grep (an unusable `\b` makes the grep miss, the fixture token is still caught by S), a Write/Edit transcript of the revised text (my we2/we3 give one), the P4 and S5/S6 survivors, the stale prose counts, runiso scripting.

Cannot be confirmed as harmless, so stated plainly:
- **F10 pattern misses** (`rk_live_`, `Token <x>`, `pwd=`, `key=`, `auth=`, plus the named misses): a real secret in those shapes passes the shipped grep. Disclosed in Does not cover and generally in the shipped text ("The pattern flags only what it matches"); it cannot pass the fixture's own S check. Follow-up, with the disclosure.
- **F9 checker E hardening** (symlink inside the project, a file the run itself created and filled with the user's words, a `.bak` or the evolve skill as evidence; r2 H1, H2, H5, H6): the E check is unchanged in rev 3; these can pass E for a lesson whose evidence is not independent. Follow-up, disclosed; the shipped rule text forbids them and the live runs did not do it.
- **F2 tie fixture (A17)**: the tie rule may be ignored by a model; UNVERIFIED, not a pass of a wrong layer on the four clean failures.
- **The B-1 hole above** is the one item I cannot call a follow-up.
- Extra checker over-strictness seen: an `unclassified` lesson that cites the orchestrator file is mapped to F1 (we1 L false FAIL).

## Escalation (round 3/3, REJECTED > 0): judge position against architect position

| id | judge position (evidence) | architect position (Revision 3) |
|---|---|---|
| A38 | The relaxed B check passes an edit with no prior backup: T1c, T10, T12, T18, T19 (real checker, synthetic transcripts over my j3 end state) all give B = PASS where the ordering rule says FAIL; `any_cp` accepts any earlier command whose text contains `cp ... .bak`, even a `grep` or `echo`, for every file. The byte-equal leg stays (T5d, T6d, T7d, T8, T9 FAIL). C27/C28 are vacuous on single-command runs. | "Fixed without loosening a safety check ... an unattributable earliest `cp ... .bak` counts, the byte-equal `.bak` having been verified separately; the transcript-order check still fails when no `cp` precedes the edit (C14)." True only for the case where no cp of any file exists at all. |
| A39 | `wc -l outputs/results.tsv` = 39, not 31; the named check as written fails. | Row carried byte-identical from rev 2 (31 rows then). |

Daniel decides. My view: B-1 is a narrow checker (support-only) loosening with a one-paragraph fix; the shipped skill text, its pattern and its live results are unaffected, A20 and A41 stand, and A39 is a count. If Daniel accepts B-1 as a disclosed checker limit, the verdict becomes UPHELD 40 / UNVERIFIED 1 once the A38 row's "orders shell edits" wording and the A39 count are corrected; if he does not, the builder must not implement the checker's ordering leg as designed.
