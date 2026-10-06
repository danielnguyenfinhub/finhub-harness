TOTALS: UPHELD 46 / REJECTED 2 / UNVERIFIED 0 — round 4 (authorised)

# Adversarial verdict — C5 hook kit, design revision 4

- Audited file: _workspace/02_strategy-architect_C5.md (revision 4, 1205 lines), Authority List A1-A48
- Prior verdicts: _workspace/02_adversarial-risk-judge_C5_r1.md, _r2.md, _r3.md (UPHELD rows carried forward)
- Extra round authorised by Daniel: 2026-10-04
- Scope (Daniel's narrow scope for this round): (1) the three r3 REJECTED rows A27, A37, A38/A43, the new rows A45-A48 and every row marked CHANGED r4 (A21, A22, A26, A27, A32, A37, A38, A43); (2) re-run the r3 reproductions against the rev-4 script; (3) attack only what rev 4 newly introduced (`expand_vars()`, the size bounds, the budget wording, the new hooks.md row and lists); (4) run the architect's runner and tests on a scratch copy; (5) at most 12 independent mutants on `expand_vars`, the size bounds and the budget arithmetic; (6) ReDoS and timing of the new `expand_vars`; (7) attribution, 8-word runs, Hangul, guardrails, gates. Nothing else was re-opened.
- Judge context: fresh. Scratch work only (scratchpad `c5r4/`): script, tests, hooks.md and edits.py extracted verbatim from the design; `edits.py` applied to copies of SKILL.md and surfaces.md; nothing written to the repo or the design.
- Python versions run: 3.10.20, 3.11.15, 3.12.3, 3.13.14 (3.14 not installed). Repo `.venv` is 3.11; 3.10 needed `exceptiongroup` and `tomli` installed to a scratch dir.
- Round-4 outcome: 2 REJECTED (A27, A45), one new blocking finding (B9). It is a quadratic regex in the new `expand_vars`, reachable by the model alone, that runs the hook to or past its 10 s timeout, which hooks.md says is fail-open. The fix is one regex and a three-line guard (below). This is the last authorised round, so the orchestrator stops and escalates to Daniel (see Escalation).
- r3 blockers: B6 (environment-value amplification) is closed as reproduced, but the replacement code opens B9. B7 (brace limit) is closed. B8 (budget wording) is closed.

## Byte-identity check

The rev-3 design file was not retained, so I compared rev-4 row text with the r2 rows I kept (`c5r2/new_rows.txt`) and with the r3 verdict's quotations. Identical to r2 and unchanged in r3: A1-A20, A23, A28-A30, A34-A36 (27 rows). Marked CHANGED r4 and different from r2: A21, A22, A26, A32, A27, A37 (r4 text) and A38, A43 (r3 rows rewritten). A24, A25, A31, A33 differ from r2 (they were CHANGED r3) and are not marked r4; their r3 content is what the r3 verdict quoted, and I could not byte-compare them against r3 itself. A39-A42 and A44 were new in r3 and are not marked r4. A45-A48 are new. For every carried row whose named check greps a changed file I re-ran the grep against the CURRENT files (scratch tree with `edits.py` applied):

| row | check | result |
|---|---|---|
| A30 | `grep -c "hooks.md"` surfaces.md; Hooks-row chat/Cowork cells | 1; surfaces.md gains 3 lines against the repo file (the Hooks-row chat and Cowork cells not re-diffed this round; carried from r3) |
| A35 | `c5-probe`, `does not show that Bash words` | SKILL.md 1 / hooks.md 1 each |
| A36 | `run no hook`, `no hook runs` in skills | 0 |
| A37 | `grep -rn x ~`, `project-local`, `brace expansion that splits a name`, ``a `root` argument``, `the minimum` | hooks.md 1 each (r3's A37 grep for "brace expansion" was stale; the r4 row names the new phrase and it is 1) |
| A43 | `A relative word after a \`cd\``, ``a bare word `.ssh` ``, `more than 40 symlinks`, `a command of more than about 16,384 divided by (depth of the working directory + 2) distinct words` | hooks.md 1 each |
| A44 | ``that `cwd` and `command` reach the hook`` | SKILL.md 1 / hooks.md 1 |
| A47 | `echo $KUBECONFIG`, `curl https://h/x/.npmrc` | hooks.md 1 each |

Every mutant id named in a row exists in the runner (script over the 213 ids; wildcard families counted: `split-class-drops-*` 16, `expand-*` 11, `mark-dropped-*` 12, `resolve-*` 10, `budget-*` 10, `key-dropped-*` 3, `links-*` 5 plus the keyword one = 6 for A39).

## Claims

| id | verdict | cited | found | reason / correct location |
|---|---|---|---|---|
| A1-A17 | UPHELD (carried) | deepseek codec.ts, runner.ts, matcher.ts, index.ts, config.ts; openharness schemas.py, loader.py, checker.py, query.py | row text identical to r2; re-opened this round: codec.ts:3, 4, 11, 38, 59, 66, 72; checker.py:20, 22, 25, 27, 29, 31, 33, 91, 169 | unchanged |
| A18-A20, A23, A28-A30, A34-A36 | UPHELD (carried) | NET-NEW | greps above; tests pass (168 on 3.10-3.13) | unchanged |
| A21 | UPHELD (CHANGED r4) | NET-NEW | the named mutants `no-backslash-replace-in-expand`, `backslash-replace-before-split-dropped`, `X15-backslash-becomes-space-in-command` exist and are killed; `cat ~\.kube\config`, `C:\Users\u\.docker\config.json`, `C:\Users\u\.ssh\id_rsa` deny; a value `C:\Users\u\.ssh\id_rsa` in `$X` denies | stale ids fixed |
| A22 | UPHELD (CHANGED r4) | NET-NEW | `no-normpath`, `no-resolve`, `J-N19`, `X24-pass1-not-casefolded` exist and are killed | stale ids fixed |
| A24 | UPHELD (carried) | NET-NEW | 168 tests pass; named mutants exist and are killed | the row says nothing about expansion linearity |
| A25 | UPHELD (carried) | NET-NEW | tests pass on 3.10-3.13; `R22-parse_int-dropped`, `X17-parse_int-float` killed | — |
| A26 | UPHELD (CHANGED r4) | NET-NEW | `failclosed-2->0`, `failclosed-2->1`, `except-Exception->OSError` exist and are killed; NUL path exit 2 | — |
| A27 | REJECTED (CHANGED r4) | NET-NEW (bounded `expand_vars()`; "the command cap is checked first, so the work is one linear pass") | B6 closed: `cat /h/.netrc ` + `$BIG ` x 33,313 with BIG 1,111 / 5,883 / 11,877 / 94,000 / 120,000 B (credential first, credential last, and benign): exit 2 `check failed (ValueError)` in 0.02-0.03 s on 3.10, 3.11, 3.12, 3.13; `echo $BIG $BIG` (94 KB) 0; three refs exit 2; `$PATH` of 2,009 B allowed. **But the work is not linear.** The new `VAR` pattern is `\$(\w+\|\{[^}]*\})` and has no `\|$` alternative, so every unterminated `${` scans to the end of the string and backtracks: quadratic in the number of `${`. `cat /h/.netrc ` + `${` x 99,000 (198,014 chars, under the 200,000 cap, no environment needed): **killed by a 10 s timeout** on 3.10, 3.11 and 3.12 and 9.28 s on 3.13; 25,000 `${` 0.71 s, 50,000 2.76 s, 75,000 6.41 s, 90,000 9.39 s (x4 per doubling). Shapes `${` x 100,000: 9.6-10.9 s, `{$` x 100,000: 9.6-10.8 s, `${a` x 66,000: 6.2-7.1 s, `${ ` x 66,000: 6.1-7.2 s. Control, same command with `ab` x 99,000: 0.04 s. The stdlib expansion is linear on the same input (0.14 s in r3's sweep, which is why r3 did not see it): current CPython patch releases (3.10.20, 3.11.15, 3.12, 3.13 here) use `\$(\w+\|\{[^}]*(\}\|$))`, so the code comment "the pattern os.path.expandvars uses" is false on every version I ran | hooks.md says a timeout is fail-open. The text pass runs after `candidates()`, so the credential word never gets checked. This is worse than r3's B6: the model alone controls the input, no large environment value is needed, and the row's own sentence ("one linear pass") is false. Fix (tested, 0.04 s on all four shapes, 168 tests still pass): `VAR = re.compile(r"\$(\w+\|\{[^}]*(?:\}\|$))", re.ASCII)` and at the top of `value()` `if name[0] == "{" and not name.endswith("}"): return m.group(0)`. Add a test: `"cat /h/.netrc " + "${" * 99_000` exits 2 in under 5 s. Rest of the row verified: 33 deny / 16 allow / 16 separators; `test_variable_expansion_cannot_outlast_the_hook`, `test_command_expansion_bound_is_200000` pass. See B9 |
| A28 | UPHELD (carried) | NET-NEW | tests pass | — |
| A29 | UPHELD (carried, re-run) | NET-NEW | `lint_harness.py .` 0/0; `package-plugin.sh` exit 0 on the scratch copy, plugin and skill zips list `deny_sensitive` and `hooks.md` (2 entries), evolve zip 0 | — |
| A30 | UPHELD (carried, re-run) | NET-NEW | see greps | — |
| A31 | UPHELD (carried) | NET-NEW | the three protocol tests pass; mutants `mark-dropped-*` (12), `flat-claim-readded`, `cowork-flat-claim`, four `B4-*` killed | listed limits unchanged (r3 F2) |
| A32 | UPHELD (CHANGED r4) | NET-NEW | `empty-word-filter-dropped` and `dedupe-dropped` both killed in the runner; the "equivalent survivor" phrase is gone | — |
| A33 | UPHELD (carried) | NET-NEW | 198,000-character benign word allowed, long `/.ssh/` words denied; mutants killed | Stale in the safe direction (F4): the stated residual (`KEYS=/h/.ssh`, `cat $KEYS/<4100 a>`) no longer exists; the command-level expansion makes it exit 2 `sensitive-path` (run) |
| A34 | UPHELD (carried) | NET-NEW | NUL and lone surrogate exit 2 | 3.14 untested |
| A37 | UPHELD (CHANGED r4) | NET-NEW (named limits incl. "brace expansion that splits a name") | all five named greps return 1 on the CURRENT hooks.md; `cat ~/.kube/{config,x}`, `cat ~/.{net,npm}rc`, `cat ~/.n{e,}trc` exit 0 as documented; `test_name_splitting_brace_expansion_is_a_documented_pass` and `test_the_brace_limit_stays_documented` pass; `brace-limit-sentence-dropped`, `brace-example-dropped` killed | r3 rejection closed |
| A38 | UPHELD (CHANGED r4) | NET-NEW (budget 16,384 // (depth + 2) distinct words) | bisection through the script with distinct plain words `x0..xN`: depth 1: 5,461 allowed, next word `path-budget` exit 2; depth 3: 3,276; depth 6: 2,048; depth 8: 1,638; depth 15: 963; each equals `16,384 // (depth + 2)`. `test_budget_is_16384_over_depth_plus_two_distinct_words` (depths 1, 8, 15) passes; ten `budget-*` mutants killed | The numbers are exact for single-component words. "Every distinct word of any kind costs depth + 2" is not literally true for path-shaped words (F3): at depth 6, relative `src/mod/fN.py` allows 1,638, absolute `/x/y/z/fN` 3,276. The stated number is an upper bound for relative paths, the false positive class is listed, and hooks.md says "about"; not blocking |
| A39 | UPHELD (carried) | NET-NEW | 40-link path 0, 41-link path 2 (run); six named mutants killed | — |
| A40 | UPHELD (carried) | NET-NEW | chain test passes; four named mutants killed | wording "no filesystem call" (F1 of r3) unchanged |
| A41 | UPHELD (carried) | NET-NEW | ten `resolve-*` mutants killed | — |
| A42 | UPHELD (carried) | NET-NEW | `R22-parse_int-dropped` killed | — |
| A43 | UPHELD (CHANGED r4) | NET-NEW | the four greps return 1 on the CURRENT hooks.md; the number in the sentence matches A38 | r3 rejection closed |
| A44 | UPHELD (carried, re-run) | NET-NEW | grep 1 in SKILL.md and 1 in hooks.md | — |
| A45 | REJECTED | NET-NEW (bounded expansion; "the bound is checked as the result grows, so the work is linear in the 200,000-character input") | Bound arithmetic verified: command `$A$B` at 100,000 + 100,000 allowed, 100,001 refused; path value 2,048 + 2,048 allowed, 2,049 refused; 800 refs of a 94 KB value in a `path` exit 2 in 0.02 s; 49,000 refs of a 3-byte value 0.07 s; `cat /h/.netrc $BIG` (94 KB) `sensitive-path` 0.03 s; two refs allowed, three refused. **The linearity sentence is false** (A27): `${` x 99,000 runs 10 s. The verification list has no case with an unterminated `${`; none of the 11 `expand-*` mutants touches the pattern. Stdlib parity claims (ASCII names, unset `${NOPE:-~/.netrc}`) hold; the only difference from the stdlib is unterminated `${`, where the script expands MORE than the stdlib (differential fuzz below) | same fix and test as A27. After the fix the row text can say "linear" |
| A46 | UPHELD | NET-NEW | the depth test passes at 5,461, 1,638, 963 and refuses one word later; `budget-step-2`, `budget-never-charged` killed; independently re-measured at depths 3 and 6 as well | same wording note as A38 (F3) |
| A47 | UPHELD | NET-NEW | both greps 1; the listed false positives run as listed (see spot check) | — |
| A48 | UPHELD | NET-NEW | `X06-dirroot-probe-not-casefolded`, `X07-path-value-stripped`, `X13-command-cap-counts-bytes`, `X15-backslash-becomes-space-in-command`, `X17-parse_int-float`, `X24-pass1-not-casefolded` all exist and are killed in my run | — |

All NET-NEW rows carry a reason and a named check; no citation outside `references/`; none under `references/autogpt/autogpt_platform/`. Both cited sources are MIT.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C5 hook kit | N/A no returns, pricing, backtest, eval or verifier | N/A same | N/A same | N/A same | N/A same | N/A no data split |

## Blocking findings

| # | what | evidence (re-runnable in scratch) | fix the judge expects |
|---|---|---|---|
| B9 (A27, A45; hooks.md "Length of a Bash word" and "Variable expansion" rows, which say the text work is linear) | The new `VAR` pattern is quadratic on unterminated `${`. The model alone can send a command under the 200,000 cap that runs the hook to its 10 s timeout, which hooks.md says to treat as fail-open, before any word is text-checked | `cat /h/.netrc ` + `${` x 99,000: TIMEOUT at 10 s on 3.10, 3.11, 3.12; 9.28 s on 3.13. 25k 0.71 s, 50k 2.76 s, 75k 6.41 s, 90k 9.39 s. Controls: same length without `${` 0.04 s; stdlib `os.path.expandvars` on the same string linear (current CPython has `(\}\|$)`) | change `VAR` to `\$(\w+\|\{[^}]*(?:\}\|$))` and leave an unterminated `${...` unchanged in `value()`; correct the comment "the pattern os.path.expandvars uses"; add `test_unterminated_brace_cannot_outlast_the_hook` (`"cat /h/.netrc " + "${" * 99_000` exits 2, under 5 s) and a mutant that restores the old pattern; I confirmed 168/168 tests still pass with the fix |

## Follow-up (not blocking)

- F1 Message only: when an expansion passes the bound, `candidates()` raises before any word is text-checked, so `cat /h/.netrc $BIG $BIG $BIG` reports `check failed (ValueError)` rather than `sensitive-path`. Exit is 2 either way, no deny is lost. The A27 row does not promise the reason.
- F2 hooks.md says a 6 KB environment value referenced 33,000 times kept the hook "past its 10-second timeout". Measured on r3: 5,883 B 8.3 s (past 10 s only from about 11,877 B, or on a slower host); the row's own A27 text says "3-8 s". Say "toward and past".
- F3 A38/A43/A46 and hooks.md: the formula is exact for single-component words; a relative path word costs depth + 1 + its components, an absolute one costs its components + 1 (depth 6: `src/mod/fN.py` 1,638 words, `/x/y/z/fN` 3,276, plain 2,048). Add "a word with slashes costs more".
- F4 A33's stated residual (`KEYS=/h/.ssh`, `cat $KEYS/<4100 a>`) is stale: the command-level expansion denies it. Drop the sentence or say it is closed by A27.
- F5 Gate wording: the design's Proof (line 1066) says ruff is clean. With the repo `.venv` ruff 0.16.10 and the repo `pyproject.toml`, `ruff check` on the design's tests reports 2 FURB167 errors (`re.S` at test line 368, `re.I` at line 526; the repo's own code spells `re.IGNORECASE`). Auto-fixable with `--fix`. black (100) and `mypy --strict` are clean; `lint_harness.py .` 0/0; packager exit 0. The builder's gate will catch it; the written claim is wrong.
- F6 Test gaps from my independent mutants (below): Y03, Y07, Y08 with kill inputs. Y07 is the only one that lets a denied path through, and only in a mutated build.
- F7 Carried from r3, unchanged by design: `~user` costs one `getpwnam` per word (F1 r3), protocol test limits (F2), bare hash output (F3), F8-F10 of r3.

## Independent mutants (Y01-Y12: none in the architect's runner or my r1-r3 sets)

Each applied to a fresh copy of the rev-4 script by exact single-occurrence substitution (count asserted 1, result asserted different); `tests/test_deny_sensitive.py` (168) run once per mutant with the repo `.venv` pytest. 12 mutants: 6 killed, 6 survived (3 equivalent or over-denial-only, 3 test gaps).

| id | mutation | result | kill test / reason |
|---|---|---|---|
| Y01 | `size = len(s) + 1` | killed | `test_command_expansion_bound_is_200000` |
| Y02 | ref length counted from `m.group(1)` not `m.group(0)` | killed | same |
| Y04 | `resolve` starts from `path.lstrip("/")` (budget charge one lower per word) | killed | `test_component_budget` |
| Y05 | path-value limit `MAX_CHARS + 1` | killed | `test_path_value_expansion_bound_is_4096` |
| Y06 | command limit `MAX_COMMAND + 1` | killed | `test_command_expansion_bound_is_200000` |
| Y09 | budget starts at `MAX_COMPONENTS - 1` | killed | `test_component_budget` |
| Y03 | an empty-valued variable stays literal (`if not found`) | SURVIVED | `cat /h/.ssh$E` with `E=""`: original 2, mutant 0 (run). Gap |
| Y07 | `VAR.sub(value, s, count=1000)` | SURVIVED | `"echo " + "$U " * 1100 + "a" * 4100 + "$X"` with `X=/.netrc`: original 2, mutant 0 (run; the first 1,100 refs are harmless, and a short ref is rescued by the per-word `expand`, a word over 4096 characters is not). Gap |
| Y08 | size only grows, never shrinks | SURVIVED | `"$E" * 4000 + "x" * 190000 + "$A"` with `E=""`, `A="y" * 7000` (198,002 chars): original 0, mutant 2. The mutant blocks a call the original allows; contrived, gap |
| Y10 | `${}` special-cased by name length | SURVIVED, equivalent | an environment cannot hold an empty name |
| Y11 | limit checked before the add as well | SURVIVED, near-equivalent | differs only when the starting string already exceeds the limit (a path value after `~` expansion with a 4,000-character home) |
| Y12 | skip variables whose value contains `$` | SURVIVED, over-denial only | the original re-expands such a value in the per-word pass; a shell would not (it reads the literal text), so no real input is lost |

Architect's runner on the scratch copy (`mutate.py`, deny tests only per mutant, 4 jobs, Python 3.11): 213 mutants, 203 killed, the 10 `EQUIV` survive (`J-N10`, `R04`, `R01`, `J-N07`, `J-N22`, `R07`, `R03`, `J-N12`, `R02`, `X20`), 0 problems. The unmodified tests: 168 passed on 3.10, 3.11, 3.12 and 3.13. The count 168 / 213 / 10 reproduces.

## Attack tables

`expand_vars` against `os.path.expandvars` (differential, 300,000 random strings of `$ { } A a 1 _ é : - x / \ . ~`, tokens `${A}`, `${A:-x}`, `$1`, `$$`, `${}`, `$É`; env with an empty value, a value containing `$B`, `{A}`, spaces, a non-ASCII name; run on 3.10-3.13): every difference involves an unterminated `${`, where the stdlib swallows the rest of the string unexpanded and the script expands later references. The script never expands less. So no credential path passes because of the swap, and a legitimate call is blocked only if an unterminated `${` is followed by a variable holding a credential path. Behaviour confirmed by run: undefined variables stay literal; `$$`, `$1`, `$` at the end stay literal; `${HOME:-x}/.netrc` and `${NOPE:-~/.netrc}` deny; non-ASCII names do not match (`$É/.netrc` denies on the literal suffix); names are case-sensitive (`$home/.netrc` denies on the suffix, unset); a value containing `$B` is re-expanded once by the per-word pass, not recursively; values with separators or `C:\..\.ssh\id_rsa` or `~/.netrc` deny; a value of 5,007 or 6,007 characters ending in or containing a credential path denies (text-only long word); a 2,009-byte `$PATH` allowed. Boundaries exact at 200,000 and 4,096 (both sides, run). A command and a path-value refusal both exit 2; the pass-1 order only changes the stderr reason (F1).

Spot check of hooks.md lists (run on the scratch tree), all as stated. Known false positives, each exit 2: `curl https://h/x/.npmrc`; `echo $KUBECONFIG` with the variable set to `/h/.kube/config`; `grep .ssh f`; `git show HEAD:.netrc`; `ls /w/.SSH`; `git commit -m 'document ~/.ssh/config usage'`; `cat .npmrc`; a heredoc mentioning `~/.aws/config`; `file_path /w/.kube/config`; `/w/tests/id_rsa`; `/w/x/.ssh/a`; a 200,001-character command; 1,100-level nesting; three refs of a 94 KB variable; a 41-link path; 2,100 distinct words at depth 6 (2,048 allowed). Known passes, each exit 0: `cat ~/.ne*rc`; the three brace forms; `~/.ss""h/config`; `~/.net\rc`; `cd ~/.kube && cat config`; `grep -rn x ~`; `tar czf /tmp/b.tgz ~`; `find ~ -name x`; a `Glob` `pattern`, a list-valued `paths`, a `root`, a `filepath` argument; a write `content`; `.env`, `.pgpass`, `k.pem`.

Fail directions across the four texts (unchanged from r3 except the rows below)

| condition | script | hooks.md | SKILL.md 6.7 / surfaces.md | Authority List |
|---|---|---|---|---|
| expansion past 200,000 / 4,096 | exit 2 `check failed (ValueError)` | yes (Variable expansion row) | — | A27, A45 |
| unterminated `${` x 99,000 | runs to the 10 s timeout (fail-open) | "linear" (wrong) | — | A27, A45 (wrong) |
| budget or 41 links | exit 2 `path-budget` | yes, formula correct for single-component words | — | A24, A38, A39, A46 |
| everything else | as r3 | as r3 | as r3 | as r3 |

ReDoS and size (independent sweep of the rev-4 script, end to end)

| input | result |
|---|---|
| `${` x 100,000; `{$` x 100,000; `${a` x 66,000; `${ ` x 66,000; `unterminated + $A` (140,000) | 9.6-10.9 s; 9.6-10.8 s; 6.2-7.1 s; 6.1-7.2 s; 4.1-5.0 s: **B9** |
| `$` x 200,000; `${x` + 199,990 x; `${}` x 66,666; `$a ` x 66,666; `$a` x 100,000; `$_` x 100,000; `~` x 200,000; `=` x 200,000; `a/` x 100,000; `../` x 66,000 | 0.03-0.15 s |
| 4,096-character `path` / `file_path` values of `${`, `$`, `${a`, `$a`, `${x...` | 0.02-0.03 s |
| 1 MB JSON with a 1,000,000-character `content` field; 1 MB command (refused at the cap) | 0.03 s each |
| hostile environment values (`${` x 50,000, `${` x 60,000 and `${a` x 20,000 in two variables, each referenced once to three times) | 0.02-0.03 s (the value is not re-scanned by the command-level pass, and the per-word pass sees words cut at `{`) |
| the r3 DoS (`$BIG ` x 33,313; 1,111, 5,883, 11,877, 94,000, 120,000 bytes; 3.10-3.13) | exit 2 in 0.02-0.03 s, deny or refuse as stated |

Attribution and verbatim

8-word runs (case-folded alphanumerics) of the script, the test file, hooks.md and the added lines of SKILL.md (5) and surfaces.md (3) against 61 files (37,287 distinct 8-grams) under deepseek `packages/hooks`, openharness `permissions/`, `hooks/`, `plugins/loader.py`, `engine/query.py`: 0 shared runs in all five. Attribution lines present: script docstring (codec.ts:59, checker.py:20), hooks.md last line, E1 bullet. Hangul: 0 characters in the five new or edited files. Gates on the scratch copy with the repo `.venv`: black (100) clean, `mypy --strict` clean, `lint_harness.py .` 0 errors 0 warnings, `package-plugin.sh` exit 0 with `deny_sensitive.py` and `hooks.md` in the plugin and skill zips, none in the evolve zip; ruff reports 2 FURB167 (F5).

## Escalation

Round 4 (authorised) with REJECTED > 0: stop and escalate to Daniel with these rows side by side.

| id | judge position | architect position |
|---|---|---|
| A27, A45 | `VAR` is quadratic on unterminated `${`: `cat /h/.netrc ` + `${` x 99,000 hits the 10 s hook timeout (fail-open per hooks.md) on 3.10-3.12 and 9.3 s on 3.13, with no environment condition; the stdlib pattern it claims to copy is linear. One regex and a three-line guard fix it (tested: 0.04 s, 168/168 pass) | `expand_vars` is a "linear `re.sub`"; the cap is checked first so the work is "one linear pass" and measured 0.02 s on the judge's own large-value cases (true for those cases; the unterminated-brace shape was not tested) |

Everything else in scope is closed: A37 and A38/A43 are UPHELD, the env-amplification DoS is closed, the brace limit and the budget wording are correct, and the test/mutant counts reproduce. If Daniel accepts the fix as a follow-up built together with `test_unterminated_brace_cannot_outlast_the_hook`, A27 and A45 become UPHELD on a re-audit of those two rows plus the one regex.
