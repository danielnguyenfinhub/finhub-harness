TOTALS: UPHELD 41 / REJECTED 3 / UNVERIFIED 0 — round 3/3

# Adversarial verdict — C5 hook kit, design revision 3

- Audited file: _workspace/02_strategy-architect_C5.md (revision 3, 1063 lines), Authority List A1-A44
- Prior verdicts: _workspace/02_adversarial-risk-judge_C5_r1.md, _r2.md (UPHELD rows carried forward)
- Judge context: fresh. Scratch work only (scratchpad `c5r3/`): script, tests, hooks.md and edits.py extracted verbatim from the design; the design's `edits.py` applied to copies of SKILL.md and surfaces.md; nothing written to the repo or the design.
- Python versions run: 3.10.20, 3.11.15, 3.12.3, 3.13.14 (3.14 not installed; the design says so too). 153 passed on each (3.10 and 3.12 through borrowed site-packages). Gates on the scratch copy with the repo `.venv`: ruff, black (100), `mypy --strict` clean; `lint_harness.py .` 0/0; `package-plugin.sh` exit 0, plugin and skill zips 2 entries each, evolve zip 0; no Hangul in the five new or edited files; Step 6.7 probes: exit 2 with reason, 0, 1; `${CLAUDE_PROJECT_DIR}` wiring command run as written: exit 2.
- Round-3 outcome: 3 REJECTED (A27, A37, A38), 3 blocking findings (B6-B8 below), all three have a one- or two-line fix. No extra round is authorised, so the orchestrator stops and escalates to Daniel (see Escalation).
- Round-2 blockers B1-B5: B1 and B2 are closed, B3 is closed for the eight commands but its sibling (brace splitting) is open and unlisted (B7), B4 is closed for the reworded sentence (limits in F2), B5 is closed except for one wrong entry (B8).

## Byte-identity check

Authority List rows of revision 3 compared by exact row text against my own extraction of the revision-2 rows (`c5r2/new_rows.txt`, taken from the r2 file when I audited it): A1-A23, A26, A28-A30, A32, A34-A37 identical (32 rows); A24, A25, A27, A31, A33 differ (CHANGED r3); A38-A44 new. The architect's "byte-identical" claim holds. Identical text does not make a carried row safe: A37 names a grep over hooks.md, and hooks.md changed. I re-ran the named checks of every carried row that points at hooks.md, SKILL.md or surfaces.md (A29, A30, A35, A36, A37). A37 fails (below); the others pass.

## Claims

| id | verdict | cited | found | reason / correct location |
|---|---|---|---|---|
| A1-A17 | UPHELD (carried) | deepseek codec.ts, runner.ts, matcher.ts, index.ts, config.ts; openharness schemas.py, loader.py, checker.py, query.py | per r1/r2 | row text unchanged; attribution lines codec.ts:59 (`parseHookOutput`) and checker.py:18-33 (`SENSITIVE_PATH_PATTERNS`) re-opened, still correct |
| A18-A23 | UPHELD (carried) | NET-NEW | per r2 | tests they name pass (153). Cosmetic: mutant ids `no-realpath` (A22), `no-backslash-replace` (A21) no longer exist in the runner (now `no-resolve`, `no-backslash-replace-in-expand`); the equivalent mutants exist and are killed (F4) |
| A24 | UPHELD | NET-NEW (lengths, text-first, budget 16,384 / 40) | `sensitive_paths.py:56-57` opened: `RESOLVE_COMPONENT_BUDGET = 16_384`, `MAX_SYMLINKS = 40`. B2 reproduced and closed: 300-link chain, 12,000 words, credential word last: exit 2 `sensitive-path` in 0.19-0.33 s on 3.10-3.13 (r2: still running at 10 s); 30,000 words (258,905 chars) refused 0.03 s; credential first 0.04 s. Spy over `os.readlink/lstat/stat/getcwd/listdir/scandir/open`: pass 1 makes none of them (a `~user` word makes one `pwd.getpwnam`, see F1). Boundaries: 16,384 allowed / 16,385 denied (`/p` x 8,192 / 8,193; `/a/b` after 8,191), 40-link chain opens in the kernel and in the script, 41 gives `ELOOP` and `path-budget` | Every named test passes; every named mutant exists in the runner and is killed. The rule is deny-on-exhaustion, which the row states. The row says nothing about the false-positive size; that statement is A38's (B8) |
| A25 | UPHELD | NET-NEW (malformed exits 1; unparseable exits 2; parse_int=str) | B1 reproduced and closed: `{"tool_input":{"path":"/h/.ssh/id_rsa","x":<N digits>}}` exit 2 for N = 4300, 4301, 100,000 and a negative 4301, on 3.10, 3.11, 3.12, 3.13; harmless path exit 0. Also exit 2: `NaN`, `-Infinity`, `1e999999999999`, 50,000-digit float, BOM, UTF-16 with BOM; depth 990, 1100, 100,000, 3,000,000 as list and as dict on all four versions. Exit 1 (malformed, as designed): trailing garbage, a second JSON value, top-level array, `tool_input` string, null or list. Duplicate keys: last wins (same as a JS host, F11) | A string integer path (`{"file_path": 5}`) is now checked as the path `5` (disclosed, decision 5). Mutants `R22`, `R05`, `R17` etc. killed. No other parse path fails open that I could build |
| A26 | UPHELD (carried) | NET-NEW | NUL path: exit 2 `check failed (ValueError)` on all four versions | — |
| A27 | REJECTED | NET-NEW (whole-command `$VAR` expansion, then one `re.split` at `: , { }` etc.) | B3 closed: all eight r2 commands exit 2, plus `cat ~/{.netrc,.npmrc}`; `curl https://example.com:8080/a,b`, `git log --format=%h:%s`, `ls /w/a:b`, `echo a:b c,d {e}`, a JSON argument, `ssh host:path`, `scp -r a user@h:/srv/x`, `docker run -v /w/data:/data:ro`, `docker run -v $PWD:/app`, `awk '{print $1}'`, `date +%H:%M`, 50 common commands: allowed. 31 deny / 15 allow / 16 separator counts verified. **But the expansion has no size bound.** `os.path.expandvars` runs over the whole command, which was capped before expansion, so the work is about `len(cmd)/5 x len(largest env var)`. Reproduced (credential word FIRST, 33,313 refs of `$BIG`, cmd 199,900 chars): env var of 1,111 B 1.07 s; 2,139 B 2.1 s; 4,389 B 3.8 s; 8,889 B 7.8 s; 11,877 B 10.4 s; a `$PATH` of 5,883 B: 8.3 s; 24 KB: 38 s; 94 KB: still running at 60 s | hooks.md says a timeout is fail-open, so a command of 33,000 `$PATH` references followed by `cat ~/.netrc` is passed on a host whose environment holds a 12 KB value (10.4 s) or, on a loaded machine, about 6 KB. Not attacker-controlled (the model cannot grow the hook's environment), but the 200,000 cap no longer bounds the work, hooks.md says it does ("keeps the text work linear and small"), and the design's timings (0.23 s, 0.32 s) assume small environments. This host's largest variable is 759 B (0.5 s). Fix: after `expandvars`, if `len(expanded) > MAX_COMMAND` raise (exit 2), and add a test with a 5 KB variable repeated; or expand per word again. Rest of the row verified. See B6 |
| A28 | UPHELD (carried) | NET-NEW | unchanged | tests pass |
| A29 | UPHELD (carried, re-run) | NET-NEW | lint 0/0; packager exit 0 on a scratch copy of repo root; zips list 2/2/0 | — |
| A30 | UPHELD (carried, re-run) | NET-NEW | surfaces.md diff: 1 removed (old Hooks row), 3 added; chat and Cowork cells of the Hooks row byte-identical; row 8 = 1, `hooks.md` = 1, `deny_sensitive` = 1 | — |
| A31 | UPHELD | NET-NEW (host claims confined to Unverified rows; reviewed sentence list; line hashes) | B4 closed for the demanded form: r2's slip appended to hooks.md (after any sentence, or as its own paragraph) -> 1 failed; a bullet in Does not cover with "Claude Code blocks" -> 1 failed; `flat-claim-readded`, `cowork-flat-claim`, the four `B4-*` mutants killed; 12 `mark-dropped-*` killed. The three tests can fail | The test is a drift lint, not a gate, and its limits are wider than the design lists. All of these stay GREEN: a new row in the protocol table with status "Verified on the official hooks page"; a row of the Deny rules table "Claude Code blocks the call"; a heading; a fenced block; "Claude  Code" (two spaces, or a line wrap inside the name); a reviewed sentence deleted outright; a flat claim in SKILL.md/surfaces.md on a line without the word "hook"; plus the four limits the design names. The row's "any new sentence" is literally true (sentences), so UPHELD; the over-broad comment "flat claims cannot slip in" and the Does-not-cover list should name these (F2). Hash test: failure output is two bare hash strings with no file or line and no instruction (F3) |
| A32 | UPHELD | NET-NEW (dedupe, empty words skipped) | empty-word filter and dedupe both killed | The text of the row is stale: it still calls `EQUIV-PERF-dedupe-dropped` "an equivalent survivor", but r3's runner has `dedupe-dropped` as killed (budget exhaustion) and A33 says so; drop the phrase (F4) |
| A33 | UPHELD | NET-NEW (long Bash word text-only) | long words with `/.ssh/` and `\.ssh\` denied; 198,000-char benign word allowed; `A33-long-word-gets-full-check` and `dedupe-dropped` killed (runner reproduced: 189 run, 180 killed, the 9 EQUIV survive, 0 problems) | The stated residual (`KEYS=/h/.ssh`, `cat $KEYS/<4100 a>`) is true and no longer hidden behind an equivalence label. NB: with the whole-command expansion of A27 the `$KEYS` word is now expanded before the cut, so that case is denied; the sentence is stricter than needed, not wrong |
| A34 | UPHELD (carried) | NET-NEW | NUL and lone surrogate exit 2 on 3.10-3.13 | 3.14 untested |
| A35 | UPHELD (carried, re-run) | NET-NEW | `c5-probe` 1/1; "does not show that Bash words" 1/1 | the live probe itself cannot be run here; the text says so |
| A36 | UPHELD (carried, re-run) | NET-NEW | `run no hook`/`no hook runs`: 0 hits in skills | — |
| A37 | REJECTED | NET-NEW (hooks.md names the limits: parent-directory recursion, brace expansion, the `root` argument, project-local false positives, "minimum") | The named check `grep -c "brace expansion"` on the rev-3 hooks.md returns **0** (case-insensitive `brace`: 0). Revision 3 deleted the sentence when braces became separators; the claim text was carried unchanged. The other four checks return 1 | The claim is false in the delivered text and the check fails. It also hides a live limit: brace expansion that splits a NAME still passes (exit 0): `cat ~/.kube/{config,x}`, `cat ~/.{net,npm}rc`, `cat ~/.n{e,}trc`, `cat ~/.{ssh,x}/k`, `cat /h/.{aws,x}/credentials`, `cat ~/.docker/{config.json,x}`; only forms that keep a whole name in one alternative are caught. Fix: restore "brace expansion (`~/.kube/{config,x}`, `~/.{net,npm}rc`)" to the obfuscated-shell bullet in hooks.md and add the commands to a test that documents the pass. See B7 |
| A38 | REJECTED | NET-NEW (symlink walk budget 16,384 components, exit 2 `path-budget`; false positive "more than about 3,000 distinct paths") | Mechanism verified: 1,000 words allowed, 5,000 refused, 8,192/8,193 pair, ten named mutants killed. The stated false positive is wrong. The budget is charged per DISTINCT WORD of any kind (a flag, a heredoc token), not per path, and every word costs `depth(cwd) + 2` components because each is joined to `cwd` first. Measured threshold of distinct plain words: `16,384 // (depth + 2)` exactly: depth 1: 5,461; depth 3 (`/home/user/finhub-harness`): 3,276; depth 4: 2,730; depth 6: 2,048; depth 10: 1,365; depth 15: 963; depth 30: 512. A heredoc with 3,000 distinct identifiers is allowed at depth 3 and denied (`path-budget`) at depth 6 | A legitimate long inline script, SQL or prose written through Bash is blocked at about 500-3,300 distinct words depending on the project depth, and the list says "paths" and "3,000". Both the noun and the number are wrong. The tests only use `cwd=/w`, so "about 3,000" is never exercised. `git status` is unaffected at any depth (2 words; checked at depth 60). Fix text only: "a command with more than about 16,384 / (depth of the working directory + 2) distinct words (any word, not only paths; about 2,000 at depth 6); use the Write tool for long content". Same wording lives in hooks.md (Does not cover), D5/Deny table, A24-adjacent text, A43 (its grep `about 3,000 distinct paths` must change with it). See B8 |
| A39 | UPHELD | NET-NEW (40 links per path) | 40-link chain allowed, 41 refused; the kernel agrees (`os.stat` opens 39 and 40, errno 40 at 41); six named mutants killed | — |
| A40 | UPHELD | NET-NEW (text pass before the walk) | chain test: exit 2 with rule `sensitive-path` (not `path-budget`) in 0.2 s; the spy shows no filesystem call in pass 1; four named mutants killed | wording "no filesystem call" is a little strong for `~user` (F1) |
| A41 | UPHELD | NET-NEW (`resolve()` equals `os.path.realpath`) | differential fuzz, 60,000 paths over two random trees (absolute, relative, `..`, `.`, empty components, links to links, dangling, loops, a link named `.ssh`, `config`, `.aws`) on 3.10, 3.11, 3.12, 3.13: 0 differences wherever the walk did not exhaust; every exhausted path was a loop or a >40-link chain (strict `realpath` fails or the path exceeds 40 links; no case where strict `realpath` succeeds and the script exhausts). Permission-denied component (run as uid 65534 on a 000 directory): same result as `realpath` (path left unresolved, exit 0). Link loop, dangling link, cwd that is a link, credential-named link as cwd: as designed (tests + fuzz) | Ten `resolve-*` mutants killed |
| A42 | UPHELD | NET-NEW (`parse_int=str`) | see A25; mutant `R22` killed | — |
| A43 | UPHELD | NET-NEW (hooks.md names the round-2 limits) | the four greps return 1 each | Its list repeats A38's wrong number; the A38 edit must change this row's grep text too |
| A44 | UPHELD | NET-NEW (a pass does not show `cwd` and `command` reach the hook) | `grep -c` 1 in SKILL.md and 1 in hooks.md; the hash test fails if the SKILL.md line changes | — |

All NET-NEW rows carry a reason and a named check; no citation outside `references/`; none under `references/autogpt/autogpt_platform/`. Both cited sources are MIT.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C5 hook kit | N/A no returns, pricing, backtest, eval or verifier | N/A same | N/A same | N/A same | N/A same | N/A no data split |

## Blocking findings (B1-B5 are the closed r2 ones; B6-B8 are new)

| # | what | evidence (re-runnable in scratch) | fix the judge expects |
|---|---|---|---|
| B6 (A27; hooks.md "Length of a Bash word") | Whole-command `expandvars` has no output bound; the hook can be driven past its 10 s timeout, which hooks.md says is fail-open. Needs a large environment value on the host (not model-controlled) | `cat /h/.netrc ` + `$BIG ` x 33,313 with BIG 11,877 B: exit 2 in 10.44 s (at the limit); PATH 5,883 B: 8.3 s; 94 KB: >60 s. Posted numbers in the A27 row | after `expandvars`, refuse when `len(expanded) > MAX_COMMAND` (exit 2); test with a 5 KB variable referenced 30,000 times asserting exit 2 and a time guard; correct the "linear and small" sentence |
| B7 (A37; hooks.md Does not cover) | A named limit was deleted while still true: name-splitting brace expansion passes | `cat ~/.kube/{config,x}`, `cat ~/.{net,npm}rc` exit 0; `grep -c "brace expansion"` hooks.md = 0 | restore the limit with these examples; add them to a documented-pass test or a "Does not cover" test |
| B8 (A38 + A43, hooks.md) | The budget false positive is described as "about 3,000 distinct paths"; it is "any distinct word, `16,384 // (depth + 2)`" | threshold table in A38 above; heredoc at depth 6 denied | reword in hooks.md, A38, A43 (and its grep), the Deny-rules table; add a test at a deep `cwd` (e.g. depth 8, 1,700 words allowed, 1,900 refused) so the stated number is checked |

## Follow-up (not blocking)

- F1 Pass 1 is not literally filesystem-free: every distinct `~name` word calls `pwd.getpwnam` (spy: only that call). 25,000 such words took 0.64 s here; on a host with a networked name service this is the same fail-open class. Say "no symlink walk" instead of "no filesystem call", or skip `~user` in pass 1.
- F2 Name the limits of the protocol test (A31 section above). Suggested: new rows in any table, headings, fenced blocks, wrapped or double-spaced "Claude Code", deletions, lines without the word "hook" in SKILL.md/surfaces.md. Reword the test comment "flat claims cannot slip in".
- F3 `test_hook_lines_in_skill_and_surfaces_are_the_reviewed_ones` freezes 10 lines (it also freezes the two pre-existing surfaces.md lines 65 and 87 that merely contain "hook"). Any later legitimate edit to those lines, or a new line containing "webhook" or "hooks", fails with two bare sha256 prefixes and no hint. Print the offending file and line; say "update HOOK_LINES after review". Bypass: the hash list lives in the same file and any author can recompute it (`sha256(line)[:12]`); it only forces the change to be visible in review, it cannot judge whether a new wording is true. State that limit.
- F4 Stale text: A32 ("EQUIV-PERF-dedupe-dropped ... equivalent survivor"); mutant ids `no-realpath` (A22), `no-backslash-replace` (A21), `except-Exception->narrow` (A26) differ from the runner's names.
- F5 Test gaps from my independent mutants (below): X06, X07, X13, X15, X17, X24, each with a kill test. The fixed QA bar (no non-equivalent survivor for a rule that lets a denied path through or blocks a legitimate one) applies to them.
- F6 Add to the false-positive list: a URL or word ending in a credential file name (`curl https://h/x/.npmrc`, `ssh-keygen -f ./id_ed25519`); a command that references an environment variable whose value is a credential path (`echo $KUBECONFIG`, `$GOOGLE_APPLICATION_CREDENTIALS`, `$AWS_SHARED_CREDENTIALS_FILE`), now expanded because of A27; the hooks.md wording "equals a credential file name" is narrower than the behaviour (end-anchored suffix).
- F7 "Effort S (script 143 lines)": the backlog row (`_workspace/01b_capability-scout_backlog.md:52`) scores effort 0.6 and calls it M; the script grew 88 -> 143 lines (+63%), the tests are 520 lines, hooks.md 94, and a bounded resolver now duplicates `sensitive_paths.py` (decision 1). Change the header to M. Not a verdict row.
- F8 stderr closed or full: the hook does not exit 2 (I saw exit 1 for `/dev/full`, the design says 120); either way non-blocking. hooks.md is silent; the design's Does-not-cover has it.
- F9 hooks.md Input row does not state the fail direction for a missing or non-object `tool_input`, trailing data or a top-level array (all exit 1, tested for the first, probed for the others).
- F10 Duplicate keys: last wins, identical to a JS host; not stated.

## Independent mutants (X01-X24: none in the architect's runner, my r1 N-set or my r2 R-set)

Each applied to a fresh copy of the rev-3 script by exact single-occurrence substitution (count asserted == 1, result asserted different); `tests/test_deny_sensitive.py` (153) run once per mutant. 24 mutants: 14 killed, 10 survived (5 equivalent or message-only, 5 test gaps; X17 is both).

| id | mutation | result | kill test / reason |
|---|---|---|---|
| X01 | `..` clears the whole walked prefix instead of popping one | killed | — |
| X02 | pass 2 checks only the first path | killed | — |
| X03 | empty and `.` components not charged to the budget | killed | — |
| X04 | link counter reset every step | killed | — |
| X05 | rule renamed `path_budget` | killed | — |
| X08 | `normpath` before `resolve` (lexical `..` before following links) | killed | — |
| X09 | absolute link target detected only for `//` | killed | — |
| X10 | backslash replace in `expand` limited to the first one | killed | — |
| X11 | `re.split(..., maxsplit=1000)` | killed | — |
| X14 | `readlink` of the parent only | killed | — |
| X16 | long-word threshold `MAX_CHARS + 1` | killed | — |
| X18 | links counted only when the target is absolute | killed | — |
| X21 | `payload.get("tool_input", {})` instead of `payload["tool_input"]` | killed | — |
| X23 | `todo.clear()` after the first resolved path | killed | — |
| X06 | directory-root probe uses the un-casefolded string | SURVIVED | `read("/h/.SSH")` -> orig 2, mutant 0 (run) |
| X07 | path value `v` -> `v.strip()` | SURVIVED | `{"file_path":" "}` with `cwd=/h/.ssh` -> orig 2, mutant 0 (run) |
| X13 | command cap counts bytes | SURVIVED | `"é " * 99999` (199,998 chars) -> orig 0, mutant 2 (run); mutant blocks a legitimate call |
| X15 | backslash becomes a space in a command | SURVIVED | `cat ~\.kube\config` and `cat C:\Users\u\.docker\config.json` -> orig 2, mutant 0 (run); the Windows tests use only `.ssh` |
| X17 | `parse_int=float` instead of `str` | SURVIVED (equivalent except one input) | `{"file_path": 5}` with `cwd=/h/.ssh` -> orig 2, mutant 0 (run); all big numbers still parse |
| X24 | pass-1 text check not case-folded | SURVIVED | a link named `.SSH` to an innocent directory, `file_path = <dir>/.SSH/k` -> orig 2, mutant 0 (run); needs the case-folded lexical form |
| X12 | distinct-word cap 40,000 | SURVIVED, equivalent | 49,000 distinct 3-char words + `/h/.netrc` -> both exit 2 (budget); any cap above 8,192 words is decision-equivalent |
| X19 | `~user` expanded only for `~` and `~/` | SURVIVED, near-equivalent | differs only for another account's home that contains a link; not portable to test |
| X20 | reason limited to the first line | SURVIVED, message-only | — |
| X22 | budget charged after the pop | SURVIVED, equivalent | same count |

Also: the architect's own runner reproduced on the scratch copy (deny tests only, my first attempt was invalid because the scratch lacked the lint fixtures): 189 run, 180 killed, the 9 `EQUIV` survive, 0 problems.

## Attack tables

Tokeniser and expansion

| vector | result |
|---|---|
| the eight r2 commands (`docker -v ~/.ssh:/root/.ssh:ro`, `--mount source=...,target=`, `export KUBECONFIG=a:b`, `cat x:y`, `${X:-~/.netrc}`) | denied |
| 14 other glued characters after `~/.netrc` (`# ? * [ ! @x + % ^ ~ $ . -]`) | pass; they are other file names or shell globs (`~/.netrc*` is the glob case listed as obfuscation) |
| whitespace-like (NBSP, VT, FS, NEL, U+2028, U+3000), tab, CR, NUL | denied |
| `$VAR` expansion: unset names stay literal; values with separators only add words; no case found where expansion hides a word that was caught before | amplification: B6 |
| `~user` per word | yes, one `getpwnam` per distinct word (F1) |
| false positives | `git show HEAD~1:.npmrc`, `scp user@h:~/.ssh/x .`, `cat .npmrc`, `ssh-keygen -f ./id_ed25519` denied (listed or F6); 46 other common commands allowed |

Fail directions across the four texts

| condition | script | hooks.md | SKILL.md 6.7 / surfaces.md | Authority List |
|---|---|---|---|---|
| empty, non-JSON, invalid UTF-8 | exit 1 | yes | `garbage` -> 1 (run) | A25 yes |
| missing or non-object `tool_input`, trailing data, array | exit 1 | not stated (F9) | — | A25 (missing/non-object) |
| nesting over about 1,000, any integer length | exit 2 | yes | — | A25, A42 |
| failure after parse, NUL, surrogate, command over 200,000 | exit 2 | yes | — | A24, A26, A34 |
| walk budget or 41 links | exit 2 `path-budget` | yes (false-positive size wrong: B8) | — | A24, A38, A39 |
| timeout | fail-open | yes | "what a timeout does" unproven | A24 |
| timeout caused by a huge env value | fail-open | "linear and small" is wrong | — | B6 |
| stderr unwritable | not 2 | not stated | — | design only (F8) |

ReDoS and size (independent sweep)

`text_hit` plus `normpath` on 13 hostile shapes at 4,096, 200,000 and 1,000,000 characters: worst 2 ms, 122 ms, 381 ms (linear). `expandvars` on `${` x 100,000, `$` x 200,000, `${a` x 66,000 and four more shapes: worst 0.14 s on 3.10-3.13. End to end: eight shapes as 48 words of 4,090 characters, 2,000 words of 100, one word of 199,000: 0.02-0.34 s (many exit 2 by the budget, as designed). 1 MB `content` field: 0.03 s. The only unbounded cost is B6.

Attribution and verbatim

8-word runs (case-folded alphanumerics) of the script, the test file, hooks.md and the 5+3 lines added to SKILL.md and surfaces.md against 65 files (37,369 distinct 8-grams) under deepseek `packages/hooks`, openharness `permissions/`, `hooks/`, `plugins/loader.py`, `engine/query.py`: 0 shared runs in all four. Attribution lines: script docstring, hooks.md last line, E1 bullet. Guardrails: N/A with a correct reason.

## Escalation

Round 3/3 with REJECTED > 0 and no authorisation line in the launch prompt: stop and escalate to Daniel with these rows side by side.

| id | judge position | architect position |
|---|---|---|
| A27 | expanding `$VAR` over the whole command lets an environment value of about 6-12 KB push the hook to its 10 s timeout (fail-open) with the credential word first; a two-line cap on the expanded length closes it | the 200,000-character cap keeps text work "linear and small"; measured 0.23-0.32 s on small environments |
| A37 | hooks.md has no "brace expansion" (check returns 0) and `cat ~/.kube/{config,x}` still passes | carried unchanged from r2: hooks.md names brace expansion |
| A38 | the false positive is any distinct word, threshold `16,384 // (depth+2)` (2,048 at depth 6), not "about 3,000 distinct paths" | budget is the runtime guard's number; false positive is "a command naming more than about 3,000 distinct paths" |

All three are one-line text or two-line code fixes with no design change. If Daniel accepts them as follow-ups, the rows A27/A37/A38 would be UPHELD after the edits with a re-audit of those three rows only; if he wants them built as they stand, runtime-builder must not implement the A27 expansion without the length cap, must restore the brace limit in hooks.md, and must use the corrected A38 wording.
