TOTALS: UPHELD 33 / REJECTED 4 / UNVERIFIED 0 — round 2/3

# Adversarial verdict — C5 hook kit, design revision 2

- Audited file: _workspace/02_strategy-architect_C5.md (revision 2, 788 lines), Authority List A1-A37
- Prior verdict: _workspace/02_adversarial-risk-judge_C5_r1.md (UPHELD rows carried forward)
- Judge context: fresh. Cited lines were not re-opened for A1-A23, A26, A28-A30 because their row text is unchanged (see "Byte-identity check").
- Scratch work only (scratchpad `c5r2/`, nothing written to the repo or the design): script, tests, hooks.md and edits.py extracted verbatim from the design; the design's `edits.py` applied to copies of SKILL.md and surfaces.md; probes `probe.py`, `fail.py`, `perf.py`, `mut.py`.
- Baseline reproduced: 108 passed on Python 3.11; edits apply (SKILL.md 198 -> 203; added lines 5; surfaces.md 1 removed / 3 added); `lint_harness.py .` 0 errors 0 warnings; no Hangul in the five new or edited files; the three Step 6.7 script probes give exit 2 with reason, 0, 1 and empty stdout. The architect's own runner, 14 mutants spot-checked (A24/A25/A27/A31 families): all killed.
- Round-2 outcome: 4 REJECTED (A24, A25, A27, A31), 5 blocking findings (B1-B5; three of them are false passes of a deny). Revise, then relaunch for round 3/3. No extra round is authorised, so a round-3 REJECTED row escalates to Daniel.
- Python versions run: 3.10.20, 3.11.15, 3.12.3, 3.13.14 (3.14 not installed).

## Byte-identity check

No revision-1 file is kept under `_workspace/`. I compared the Authority List rows of revision 2 against `scratchpad/c5/doc_r1.md` (the architect's own copy of revision 1; its cited columns also match my r1 verdict). Result by exact row text: A1-A23, A26, A28, A29, A30 identical (27 rows); A24, A25, A27, A31 differ (marked CHANGED); A32-A37 new. The claim "byte-identical" holds, with the caveat that the baseline file is the architect's copy.

## Claims

| id | verdict | cited | found | reason / correct location |
|---|---|---|---|---|
| A1-A17 | UPHELD (carried) | deepseek codec.ts, runner.ts, matcher.ts, index.ts, config.ts; openharness schemas.py, loader.py, checker.py, query.py | per r1 | row text unchanged |
| A18-A23 | UPHELD (carried) | NET-NEW | per r1 | row text unchanged; the tests they name still pass (108) |
| A24 | REJECTED | NET-NEW (length rules, command cap 200,000) | Reason says the cap "keeps the measured worst case at 0.32 s, far below the 10 s timeout". That holds only on a filesystem with no symlink chains. Reproduced: 300 symlinks `c0 -> c1 -> ... -> c299 -> end` (one `ln -s` loop) and a command of 12,000 words `c0/N` followed by `cat /h/.netrc`: the hook is still running at 10 s (killed by my timeout; Python 3.11 and 3.13 both take 28-35 s for 30,000 words; 3.1 s for 2,000 words). The credential word is the last word, so it is never reached. With the credential word first the same command exits 2. | hooks.md says "treat a timeout as fail-open", so this is a false pass of a deny, reachable in two ordinary calls (create links, then a long command). The runtime guard already bounds this walk: `src/master_finhub/tools/sensitive_paths.py:56-57` has `RESOLVE_COMPONENT_BUDGET = 16_384` and `MAX_SYMLINKS = 40`. See B2. The other parts of the row (4096 on path values only, words over 4096 text-only, 200,000 refusal; BASH_ALLOW cases; 4095/4096 pair) are correct and tested: my mutants of them were killed |
| A25 | REJECTED | NET-NEW (malformed input exits 1; unparseable-depth exits 2) | Reason: "well-formed host input the parser cannot hold must not fail open". Counter-example, run on 3.10.20, 3.11.15, 3.12.3, 3.13.14: `{"tool_input":{"path":"/h/.ssh/id_rsa","x":<4301 digits>}}` is valid JSON; `json.loads` raises `ValueError` (int digit limit); `main()` catches `ValueError` as "unreadable" and exits 1 (not blocking). 4300 digits -> exit 2, 4301 and 100,000 digits -> exit 1, `-` followed by 4301 digits -> exit 1. | Same class as r1 B2: content the model controls (any numeric argument of an MCP tool) turns a deny into a pass. Fix, tested here: `json.loads(data, parse_int=str)` parses 100,000 digits without error. See B1. Everything else in the row holds: depth 990, 1100, 100,000, 5,000,000 and a nested-dict case exit 2 on all four versions; raw UTF-8 under `PYTHONIOENCODING=ascii`/`cp1252` and `LANG=C PYTHONUTF8=0` denies correctly; BOM, UTF-16, CRLF, NaN, huge floats and exponents parse and deny |
| A26 | UPHELD (carried) | NET-NEW | unchanged text; re-run: NUL path -> exit 2 `check failed (ValueError)` on 3.10, 3.11, 3.12, 3.13 | — |
| A27 | REJECTED | NET-NEW (Bash command cut by one linear `re.split` ... each distinct word checked) | The class `[\s;&|()<>`"'=]` omits `:`, `,`, `{`, `}`. Ordinary un-obfuscated commands that name a credential pass (exit 0): `docker run -v ~/.ssh:/root/.ssh:ro img`, `docker run -v ~/.ssh:/k img`, `docker run -v $HOME/.aws:/root/.aws:ro img`, `docker run -v /h/.netrc:/k img`, `docker run --mount source=/h/.kube/config,target=/k img`, `export KUBECONFIG=/h/.kube/config:/h/.kube/other`, `cat /h/.netrc:x`, `cat ${X:-~/.netrc}`. Only the case where the second path happens to end the word (`-v ~/.ssh:/root/.ssh`) is denied. | This is r1 B1 (punctuation glued to a word defeats the end-anchored patterns and the directory-root probe) with different characters; the 12-separator test cannot show completeness. Fix, run here: class `[\s;&\|()<>`"'=:,{}]` -> all 108 tests still pass, all eight commands above exit 2, and `curl https://example.com:8080/a,b`, `git log --format=%h:%s`, `ls /w/a:b` still exit 0. Also `grep -rn .ssh docs/`, `jq '.ssh' f`, `echo .aws`, `git log -- .ssh` exit 2 and no false-positive entry names a bare `.ssh`/`.aws`/`.azure`/`.gnupg` word (B5). 22 deny / 10 allow / 12 separators counts verified |
| A28 | UPHELD (carried) | NET-NEW | unchanged | — |
| A29 | UPHELD (carried) | NET-NEW | lint on the edited copy 0 errors 0 warnings (re-run); packager not run (it deletes `dist/`) | — |
| A30 | UPHELD (carried) | NET-NEW | surfaces.md diff: 1 removed (old Hooks row) and 3 added; chat and Cowork cells of the Hooks row byte-identical; row 8 = 1, `hooks.md` = 1, `deny_sensitive` = 1 | — |
| A31 | REJECTED | NET-NEW (every protocol sentence resting on the bridge or plugin-dev text is an Unverified row) | The row says "every". hooks.md still holds flat host claims outside the table: line 73 "A tool value that is not a string is ignored: the host's own schema rejects it." and the status cell of the nested-JSON row "the host never sends such input". `test_host_protocol_rows_stay_marked_unverified` cannot see them. Reworded slip demonstrated: appending "Claude Code blocks any call whose PreToolUse hook exits 2, and Cowork ignores hooks." after line 73 leaves `-k "host_protocol or wiring"` green (2 passed). | The non-string claim is load-bearing: ignoring non-string values is only safe if the host rejects them. See B4. The ten named rows are correctly marked and the test does fail when a mark or one of three banned phrases changes (mutants killed) |
| A32 | UPHELD | NET-NEW (dedupe, empty words skipped) | `call({"command": ";"}, cwd=<credential dir>)` is allowed; mutant with the empty-word filter removed: 1 failed, 40 passed (killed). Dedupe is decision-equivalent (rule is a pure function of word and cwd): my timing 25,000 repeats of one word 0.03 s vs 0.32 s without dedupe | The check can fail |
| A33 | UPHELD | NET-NEW (long Bash word text-only) | long words with `/.ssh/` and `\.ssh\` denied; 198,000-character benign word 0.07 s; mutants `always-None` and `always-denied` killed (run) | The "performance only" label on `EQUIV-PERF-long-word-does-full-check` is not literally true: with `KEYS=/h/.ssh` in the hook environment, `cat $KEYS/<4100 x a>` exits 0 and the full-check mutant exits 2. No path the kernel can open is that long (PATH_MAX), so I accept it as security-neutral; reword to "no decision on any openable path" (F5) |
| A34 | UPHELD | NET-NEW (lone surrogate second trigger) | `ok\x00.txt` -> `ValueError`, `ok\ud800.txt` -> `UnicodeEncodeError`, both exit 2 `check failed` on 3.10, 3.11, 3.12, 3.13; same for words in a Bash command; the test fails if either stops raising | 3.14 untested here |
| A35 | UPHELD | NET-NEW (live blocked-read probe and its limits) | `grep -c c5-probe` = 1 in SKILL.md and 1 in hooks.md; `grep -c "does not show that Bash words"` = 1 in each; deleting the sentence drops both to 0 | Check can fail. The live probe itself cannot be run here; see item (4) |
| A36 | UPHELD | NET-NEW (chat reported none, Cowork unknown) | `grep -rn "run no hook\|no hook runs"` over SKILL.md, references, scripts: 0; E1, E4, E6 wording read | The hooks.md claim "line 1" is the first paragraph (line 3), cosmetic |
| A37 | UPHELD | NET-NEW (limits named) | `grep -c "grep -rn x ~"` 1, `"project-local"` 1, `"brace expansion"` 1, the `root` argument sentence present (hooks.md:86), "minimum" present | The check can fail. New limits found this round are not in it (F1, F2) |

All NET-NEW rows carry a reason and a named check; no citation outside `references/`; none under `references/autogpt/autogpt_platform/`. Both cited sources are MIT.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C5 hook kit | N/A no returns, pricing, backtest, eval or verifier | N/A same | N/A same | N/A same | N/A same | N/A no data split |

## Blocking findings (revise before build)

| # | what | evidence (re-runnable in scratch) | fix the judge expects |
|---|---|---|---|
| B1 (A25) | Valid JSON the parser cannot hold fails open: a decimal integer of more than 4300 digits anywhere in `tool_input` | `{"tool_input":{"path":"/h/.ssh/id_rsa","x":<4301 x "1">}}` -> exit 1 on 3.10.20, 3.11.15, 3.12.3, 3.13.14 | `json.loads(data, parse_int=str)` (verified) or catch the digit-limit `ValueError` separately and exit 2; add the 4301-digit case plus a `.ssh` path to `test_unparseable_json_depth_fails_closed`; add mutant "parse_int dropped"; add the case to the hooks.md row for unparseable JSON |
| B2 (A24) | Hook timeout can be forced; the guard fails open (hooks.md's own rule) because `os.path.realpath` is unbounded per word | 300-link chain in the project; command of 12,000 distinct `c0/N` words then `cat /h/.netrc`: still running at 10 s. 3.11: 3.1 s for 2,000 words, 34.6 s for 30,000; 3.13: 28.5 s | (a) first pass: text-only check of every word, deny on a hit before any filesystem call; (b) second pass: bound the walk as the runtime guard does (`sensitive_paths.py:56-57`: component budget and 40-link limit), and exit 2 when the budget is spent; (c) test: a 300-link chain with many words and the credential word last -> exit 2 within the test's time guard; (d) correct the A24 reason and the hooks.md "Length of a Bash word" row (the 10 s margin is not a measured constant). Also note that on 3.11 a chain over about 1,000 links gives `RecursionError` in realpath, exit 2 `check failed` (false positive; list it) |
| B3 (A27) | Glued `:` `,` `{` `}` defeat the end-anchored patterns and the directory-root probe | the eight commands in the A27 row; `docker run -v ~/.ssh:/root/.ssh:ro` is the canonical way to hand a key to a container | class `[\s;&\|()<>`"'=:,{}]` (verified: 108 pass, eight passes closed, no new benign deny in my set); add the eight commands to `BASH_DENY`, add `:` `,` `{` `}` to the separator test's list and one mutant per character; update the hooks.md sentence that lists the cut characters and the Authority List row. Brace expansion `~/{.netrc,.npmrc}` then exits 2; update the "Does not cover" example that says it passes |
| B4 (A31) | Flat host claims remain in hooks.md and the pytest cannot catch new ones | hooks.md:73 "the host's own schema rejects it", the nested-JSON row "the host never sends such input"; slip demo above | move both into the Unverified table (rows "Non-string values" and "Nested JSON"), reword to "assumed, not checked"; extend the test: assert that every sentence outside the table that contains `host` or `Claude Code` or `Cowork` is on an allow-list of known sentences, or ban the three words outside the table and the intro; add a mutant that re-adds a flat sentence in the Deny-rules section |
| B5 (A27 / hooks.md) | A legitimate call is blocked and not listed | `grep -rn .ssh docs/`, `jq '.ssh' f.json`, `echo .aws`, `git log -- .ssh` all exit 2. The false-positive bullet says "a bare word that equals a credential file name or contains /.ssh/"; `.ssh` is neither a file name nor contains `/.ssh/` | add "a bare word `.ssh`, `.aws`, `.azure` or `.gnupg` (a grep pattern, a jq filter, a git pathspec)" and "a tool input nested more than about 1,000 levels" and "a project that holds a symlink chain over about 1,000 links" to the false-positive list |

## Follow-up (not blocking)

- F1 `cd` then a relative word passes: `cd ~/.kube && cat config`, `cd ~/.docker; cat config.json`, `cd ~/.config && cat gcloud/application_default_credentials.json` (the relative words resolve against the payload `cwd`, not the new directory). Same class as the parent-directory limit; name it in "Does not cover".
- F2 Quote or backslash splits inside the path pass: `cat ~/.ss""h/config`, `cat ~/.net\rc`. Designed limit (obfuscation); the bullet says "obfuscated shell" without these two common forms. `cat ~/.ss""h/id_rsa` is still denied because the second piece ends in `id_rsa`.
- F3 If stderr is closed by the reader or full (`/dev/full`, closed pipe) the hook exits 120 after a failed write, which is non-blocking. Host-side fault; add a line to "Infrastructure faults make the call proceed", or write the reason inside `try` and still return 2.
- F4 hooks.md does not say invalid UTF-8 stdin exits 1 (A25 and the design table do). The depth threshold is version dependent; "about 1000" is acceptable.
- F5 Reword `EQUIV-PERF-long-word-does-full-check` as "no decision on any openable path" (see A33).
- F6 `~user` words: each distinct word costs one `getpwnam`; 30,000 distinct `~uNNNN` words took 0.64 s here. On a host with a networked name service this could approach the timeout; B2's pass structure also bounds it.
- F7 hooks.md Windows row says `\` becomes `/` "before anything else"; for path values it happens after `expanduser`/`expandvars` and the join. Result is the same; wording only.
- F8 Step 6.7 and hooks.md Install 4: add "or that `cwd` and `command` reach the hook" to the list of what a pass does not show (the probe path is absolute and `~`-based, so it uses neither).
- F9 Mutant test gaps from my independent set (below).

## Item (1): tokeniser attack table

| vector | result |
|---|---|
| glued `; & \| ( ) < > backtick " ' =`, `$(...)`, `<(cat ~/.netrc)`, `2>~/.ssh/x`, `<<<~/.ssh/id_rsa`, `FOO=~/.ssh/id_rsa cmd`, `$'/h/.ssh/id_rsa'` | denied |
| `$HOME`, `${HOME}`, `~`, `~root`, `"$HOME"/.netrc`, backslash-escaped `\` before newline | denied |
| `:` `,` `{` `}` glued | passed: B3 |
| brace expansion `~/{.netrc,.npmrc}`, `~/.n[e]trc`, `~/.ne*rc`, `$KEYS/config` with an unset variable | pass; documented as obfuscation (brace becomes denied once B3 is applied) |
| path split across a quote `~/.ss""h/config`, backslash `~/.net\rc` | pass; designed limit, stated only generically (F2). `~/.ss""h/id_rsa` is denied by the `id_rsa` piece |
| quoted path with spaces `'~/.my dir/.ssh/id_rsa'`, `"/h/my keys/.ssh/id_rsa"` | denied (last piece carries the suffix) |
| NBSP, U+2028, VT as separators, `\ſ` long-s case-fold | extra denies only (false positives, harmless) |
| `cd X && cat rel` | pass: F1 |
| legitimate: `https://host/path`, `curl -d '{"a":"b"}' https://h/x`, `a=b c=d`, long commit message, `git log --format=%h:%s` | allowed; `git commit -m 'fix .npmrc handling'` denied (listed class) |

## Item (2): fail directions

| condition | result | stated in hooks.md / SKILL.md 6.7 / Authority List |
|---|---|---|
| nested JSON, any depth 990 to 5,000,000, list or dict | exit 2 on 3.10-3.13 (no crash, no signal) | hooks.md yes; A25 yes; tested |
| 4301+ digit integer | exit 1, fail-open | not stated anywhere: B1 |
| invalid UTF-8, empty, non-JSON, wrong shape | exit 1 | hooks.md says empty or non-JSON only (F4); A25 yes; tested |
| non-ASCII under ascii / cp1252 / `LANG=C` | parses, denies, reason ASCII-escaped | A25 yes, tested; not in hooks.md (harmless) |
| command over 200,000 chars | exit 2 `check failed (ValueError)` | hooks.md yes (deny-rules row and false-positive list); A24 yes; tested at 200,001 |
| word over 4096 | text patterns only | yes, tested |
| path value over 4096 | exit 2 `too-long` | yes, tested |
| NUL, lone surrogate | exit 2 on all four versions | A26, A34; tested |
| timeout | fail-open (stated), reachable: B2 | hooks.md "Treat a timeout as fail-open"; A24 reason wrongly says it cannot be reached |
| stderr unwritable | exit 120, not blocking | not stated: F3 |

## Item (3) and (4)

- (3) A flat protocol claim still slips in: shown above (B4). The pytest checks ten row marks and three phrases and reads only hooks.md; SKILL.md and surfaces.md are not read by any test.
- (4) Step 6.7 live probe: Code-only, conditional on Step 3 shipping the guard, names the exact stderr line to look for, names `/hooks`, and states what a pass does not show (Bash words, MCP tools, subagents, timeout, chat, Cowork). A returned refusal can only be the guard's own line, because a missing hook gives a "file not found" result for a non-existent path. Remaining unstated limits: F8. The live probe cannot be run here, so it stays UNVERIFIED by design, which the text says.

## Item (5): cwd, case, dedupe

Join order (`join(cwd, X)`), credential-named link as cwd, a `.SSH` real directory, `..` in cwd and in the word, empty or non-string cwd, Windows-style cwd: all behave as designed (tests plus my probes). Case-folding false positive on a case-sensitive filesystem is documented. Dedupe is decision-equivalent. The long-word mutant is performance-equivalent for openable paths only (A33).

## Item (6): ReDoS and size

`text_hit` on 16 literals x 9 hostile shapes at 4,096, 200,000 and 1,000,000 characters: worst 1 ms, 72 ms, 324 ms (linear). `WORD_SPLIT` on 200,000 characters: 9 ms. Eight hostile 200 KB commands (`${` x 2040 words, `$`, `~`, `/.`, `/..`, quote soup, unterminated quote, many distinct 3-character words): 0.03-0.08 s. 1 MB stdin with a 1 MB `content` field: 0.03 s; 600,000-word command: refused in 0.04 s. No regex hazard; the only unbounded cost is filesystem work (B2).

## Item (7): attribution and verbatim

8-word runs (case-folded alphanumeric tokens) of hooks.md, the script, the test file and the lines added to SKILL.md and surfaces.md against 61 files (35,321 distinct 8-grams) under deepseek `packages/hooks`, openharness `permissions/`, `hooks/`, `plugins/loader.py`, `engine/query.py`: 0 shared runs in all five. Attribution lines present: script docstring (codec.ts:59, checker.py:20; both lines re-opened and still land in `parseHookOutput` and the `SENSITIVE_PATH_PATTERNS` tuple), hooks.md last line, E1 bullet. Guardrails: N/A with a correct reason.

## Mutants (independent set: 25 entries R01-R25; none in the architect's runner, none from my r1 set N01-N23)

Each applied to a fresh copy by exact single-occurrence substitution (count asserted == 1, result asserted different), whole `tests/test_deny_sensitive.py` run once per mutant. R22 is the proposed B1 fix, not a mutant. Of the 24 true mutants: 6 killed, 18 survived; 6 of the survivors are equivalent or message-only, 12 are test gaps.

| id | mutation | result | kill test |
|---|---|---|---|
| R14 | `realpath(s)` -> `realpath(s, strict=True)` | killed | — |
| R16 | pre-split backslash replace with count 1 | killed | — |
| R18 | azure pattern `*/.azure/*` -> `*/.azure/x` | killed | — |
| R19 | gnupg pattern widened to `*/gnupg/*` | killed | — |
| R21 | `cwd.rstrip('/') or '/'` in the join | killed | — |
| R24 | deny prefix text changed | killed | — |
| R01 | `expandvars(expanduser())` order swapped | SURVIVED, near-equivalent | none (only differs for a hook-environment variable holding a literal `~`) |
| R02 | split class without `+` | SURVIVED, equivalent (empty words are filtered) | none |
| R03 | `sorted(set(words))` instead of `dict.fromkeys` | SURVIVED, equivalent | none |
| R04 | reason shows the last 200 characters | SURVIVED, message-only | none (design pins only the prefix) |
| R07 | `RE.fullmatch` for `RE.match` | SURVIVED, equivalent (every pattern ends in `\Z`) | none |
| R25 | `~user` expansion only for `~/` | SURVIVED, near-equivalent (`~root/.ssh` is also caught by text) | none |
| R05 | stdin read capped at 1,000,000 bytes | SURVIVED | payload with a `.ssh` path and a 2,000,000-character `content` field -> 2 |
| R06 | only the first 1,000 distinct words checked | SURVIVED | 1,500 distinct words then `/h/.netrc` -> 2 |
| R08 | `*/id_ed25519` widened to `*/id_ed25519*` | SURVIVED | ALLOW `/h/id_ed25519.pub` |
| R09 | `*/.pypirc` widened to `*/.pypirc*` | SURVIVED | ALLOW `/h/.pypirc.bak` |
| R10 | `*/.git-credentials` widened to `*/.git-credentials*` | SURVIVED | ALLOW `/h/.git-credentials.bak` |
| R11 | `*/.netrc` -> `*.netrc` | SURVIVED | ALLOW `/w/my.netrc` |
| R12 | `*/_netrc` -> `*_netrc` | SURVIVED | ALLOW `/w/my_netrc` |
| R13 | `*/id_rsa` -> `*id_rsa` | SURVIVED | ALLOW `/w/not_id_rsa` |
| R15 | length cap counts UTF-8 bytes, not characters | SURVIVED | ALLOW a 3,000-character path of `é` -> 0 |
| R17 | stdin decoded with `errors="ignore"` | SURVIVED | valid JSON object with a stray byte `\xff` inside a string and a `.ssh` path -> 1 (documented fail direction) |
| R20 | case-fold replaced by `replace("SSH","ssh").replace("AWS","aws")` | SURVIVED | DENY `/h/.AZURE/t`, `/h/.GNUPG/x`, `/H/.NETRC`, `/h/.KUBE/CONFIG` |
| R23 | dedupe by lower-cased word | SURVIVED | case-sensitive filesystem: link `Lnk` -> `.ssh`, command `cat lnk/x Lnk/x` -> 2 |
| R22 | proposed B1 fix (`parse_int=str`) applied | survives all 108 tests, which shows nothing tests big integers | the B1 test |

## Escalation

Not applicable (round 2/3). If round 3 still has a REJECTED row and the launch prompt records no authorisation, stop and escalate to Daniel with the rejected rows beside the architect's position.
