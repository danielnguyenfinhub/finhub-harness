TOTALS: UPHELD 28 / REJECTED 3 / UNVERIFIED 0 — round 1/3

# Adversarial verdict — C5 hook kit, design revision 1

- Audited file: _workspace/02_strategy-architect_C5.md (revision 1), Authority List A1-A31
- Judge context: fresh; read only the design file, the cited references/ lines (±5) and the repo files the design edits (SKILL.md, surfaces.md, sensitive_paths.py for A19). No extra round authorised or needed.
- Scratch work (nothing written to the repo): script, tests and hooks.md extracted verbatim from the design into `<scratchpad>/repo`; the design's own `edits.py` applied to a copy of SKILL.md/surfaces.md in `<scratchpad>/ed2`; probes `probe.py`, `p2.py`, `redos.py`, `mut.py` in the scratchpad.
- Reproduced the architect's baseline: 71 passed on Python 3.11 and on 3.13; edits apply cleanly (SKILL.md 198 -> 203 lines; grep counts 2 / 4 / 1 / 1; surfaces.md 1 / 1 / 1; lint 0 errors 0 warnings; no Hangul in any new or edited file).
- Round-1 outcome: 3 REJECTED rows, 5 further blocking findings (B4-B8). Revise, then relaunch.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | deepseek hook-protocol/src/codec.ts:11, :66 | :11 `BLOCKING_EXIT_CODE = 2` ("stderr -> model"); :66 `if (exitCode === BLOCKING_EXIT_CODE)` sets decision block, reason = stderr | Evidence is the deepseek decoder, not the official Claude Code page (see Protocol audit) |
| A2 | UPHELD | codec.ts:3, :4 | header comment: "exit 2 blocks with stderr as the reason; every other exit is a non-blocking error" | same scope note |
| A3 | UPHELD | hook-protocol/src/runner.ts:89, :96 | :89-91 signal death maps to `undefined`, "non-blocking error"; :96-98 catch: "A hook that cannot run is a non-blocking error" | same scope note |
| A4 | UPHELD | codec.ts:72 | :71-72 "Structured stdout is valid only for a clean exit" / `if (exitCode === 0)` | — |
| A5 | UPHELD | codec.ts:38 | :34-36 comment says `{"decision":"deny"}` is invalid and ignored; :38-39 `topLevelDecisionOf` accepts only approve/block | — |
| A6 | UPHELD | hooks-claude-code/src/index.ts:324, :340 | :324-329 `session_id`, `transcript_path`, `cwd`, `hook_event_name`; :339-340 `tool_name`, `tool_input`, `tool_use_id` | Holds for the deepseek bridge only; hooks.md scopes it correctly, the claim text does not |
| A7 | UPHELD | index.ts:145 | :145-147 "Run the hook in the agent's session workspace"; `workdir = ...session.header.cwd` (and :328 puts the same value in `cwd`) | bridge-scoped, as the claim says |
| A8 | UPHELD | runner.ts:74, :20 | :74 `timeoutMs = hook.timeoutSec * 1000` else default; :20 `DEFAULT_HOOK_TIMEOUT_MS = 600_000` | — |
| A9 | UPHELD | hooks-claude-code/src/config.ts:52, :60 | :51-62 `substituteCommand` replaces `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PROJECT_DIR}` | bridge behaviour; hooks.md presents it unmarked, see B7 |
| A10 | UPHELD | hook-protocol/src/matcher.ts:14, :62 | :14-15 `isMatchAll`: undefined, '' or '*'; :61-62 literal `[A-Za-z0-9_|]+` is `split('\|').includes(query)` | bridge behaviour; hooks.md presents it unmarked, see B7 |
| A11 | UPHELD | index.ts:114 | :113-115 catch: "could not load hook config ... no hooks registered", `return` | — |
| A12 | UPHELD | config.ts:98; openharness hooks/schemas.py:61 | config.ts:97-100 non-`command` types pushed to `skipped`; schemas.py:61 `HookDefinition = CommandHookDefinition \| PromptHookDefinition \| HttpHookDefinition ...` (command kind at :10-13) | — |
| A13 | UPHELD | openharness plugins/loader.py:657 | `hooks_data = raw.get("hooks", raw)` | Plugin loader of OpenHarness; the claim is correctly limited to "a hooks file" |
| A14 | UPHELD | openharness permissions/checker.py:20, :22, :25, :27, :29, :31, :33 | :20 `*/.ssh/*`; :22-23 `*/.aws/credentials`, `*/.aws/config`; :25 gcloud; :27 azure; :29 gnupg; :31 docker config.json; :33 kube config | exact |
| A15 | UPHELD | checker.py:91 | `if fnmatch.fnmatch(candidate_path, pattern):` | the script uses `fnmatch.translate` + `re.match` (same semantics) |
| A16 | UPHELD | checker.py:169 | :160-169 `_policy_match_paths` returns `(normalized, normalized + "/")`, docstring names the directory-root case | — |
| A17 | UPHELD | openharness engine/query.py:1029, :1032 | :1029 `Path(value).expanduser()`; :1032 `str(path.resolve())` | the reference also reads a `root` key (:1026), which the kit does not (F9) |
| A18 | UPHELD | NET-NEW (`.aws` whole directory) | reason stated; DENY `/h/.aws/sso/cache/t.json` fails if the pattern is narrowed to two files; checker.py:22-23 lists only two files, no contradiction | — |
| A19 | UPHELD | NET-NEW (nine key/credential names) | reason stated; all nine are at src/master_finhub/tools/sensitive_paths.py:45-53; one DENY case per name; dropping a pattern fails its case | note: the runtime list also has `*/.docker` and `*/.kube` roots, the kit does not (stated in the design) |
| A20 | UPHELD | NET-NEW (case-insensitive) | DENY `/h/.SSH/ID_RSA` fails without `casefold` | `casefold`->`lower` survives; equivalent for these ASCII patterns |
| A21 | UPHELD | NET-NEW (backslash to slash) | DENY `C:\Users\u\.ssh\id_rsa`, `..\..\.ssh\k`, Windows cwd; my mutant `.replace(..., 1)` is killed | holds for path keys only; the Bash-word gap is filed under A27/B4 |
| A22 | UPHELD | NET-NEW (normalised + realpath) | `test_symlinks_tilde_and_cwd` fails when realpath's cwd handling is changed (my N05 killed) | gaps: N04 and N19 survive, see Mutants (F3) |
| A23 | UPHELD | NET-NEW (`$VAR`) | `$HOME/lnk/x` case needs `expandvars` | — |
| A24 | REJECTED | NET-NEW ("a path over 4096 characters is refused") | `rule()` applies the cap to every Bash word and every `=` remainder, not only to paths. Reproduced: `git commit -m "<2100 x 'x '>"` -> exit 2 `too-long`; `echo aaaa...(4100)` -> exit 2 | The stated reason ("mirrors PATH_MAX") does not apply to a commit message, PR body, inline script or base64 word. A legitimate call is blocked and the false-positive list in hooks.md does not mention it. See B3 |
| A25 | REJECTED | NET-NEW (unreadable stdin exits 1, never blocks) | Reproduced two fail-open paths reachable by content: (1) `{"tool_input":{"path":"/h/.ssh/id_rsa","x":[[...]]}}` nested 990 deep -> exit 2, nested 1100 deep -> exit 1 `unreadable ... not blocking`; (2) raw UTF-8 JSON with one non-ASCII char (`# \u00c1`) under `PYTHONIOENCODING=cp1252` or `ascii` -> exit 1 | Valid host JSON is treated as "malformed" and allowed. The reason ("a hook defect must not brick every tool call") covers a broken host, not well-formed input the parser cannot cope with. See B2 |
| A26 | UPHELD | NET-NEW (parsed-call error exits 2) | NUL path -> exit 2 `check failed (ValueError)` on Python 3.10, 3.11, 3.12 and 3.13 (all run here); the test can fail (it needs `except Exception` to catch `ValueError`; narrowing to `OSError` alone is killed, narrowing to `(OSError, ValueError)` survives, see N10) | The trigger is version-dependent (3.14 untested). `ok\ud800.txt` gives `UnicodeEncodeError` -> exit 2 on all four versions; use it as a second trigger (F5). NUL is not a security dependency: a NUL path cannot reach a real file |
| A27 | REJECTED | NET-NEW (Bash `command` scanned word by word) | Reproduced exit 0 (guard allows) on ordinary, un-obfuscated commands: `cat ~/.netrc;ls`, `echo $(cat ~/.npmrc)`, `cat ~/.git-credentials>/tmp/x`, `cat ~/.netrc\|base64`, `cat ~/.netrc&&echo`, `(cat ~/.kube/config)`, `` cat `echo ~/.pypirc` ``, `cat keys/id_rsa;`, `cat ~/.docker/config.json)`. Also `cat C:\Users\u\.ssh\id_rsa` (unquoted; shlex eats the backslashes before the separator step) -> exit 0 | The 11 end-anchored patterns (docker config.json, kube config, netrc, _netrc, npmrc, pypirc, git-credentials, id_*) only match when the word ends exactly at the file name; `;`, `\|`, `&`, `)`, `` ` ``, `>`, `<` glued to the word defeat them. The 5 directory patterns survive only because they end in `/*`. hooks.md "Does not cover" lists different cases (and two of its examples, `<~/.ssh/id_rsa` and `$(echo ~)/.ssh/id_rsa`, are actually denied). See B1, B4 |
| A28 | UPHELD | NET-NEW (only path keys and Bash words read) | `test_only_path_keys_and_command_are_read` fails if `content`/`pattern` were read; key-dropped mutants killed by `test_each_path_key` | — |
| A29 | UPHELD | NET-NEW (no lint rule, no packager change) | `lint_harness.py .` on the edited copy: 0 errors 0 warnings (run). The packager was not run (it does `rm -rf dist` in the repo); `scripts/package-plugin.sh` line `inc=".claude-plugin skills ..."` does include `skills/`, so both files ship | — |
| A30 | UPHELD | NET-NEW (Code only; chat not exposed, Cowork unverified) | surfaces.md:65 and :140 carry the chat observation; after the design's edits `grep -c hooks.md` = 1, `deny_sensitive` = 1, row 8 = 1, and only the Code cell of the `Hooks` row changed | the body text overstates Cowork, see B7 |
| A31 | UPHELD | NET-NEW (second-hand protocol points marked UNVERIFIED) | `grep -c "Unverified" hooks.md` = 6 on my extraction: exactly at the threshold of 6 (case-sensitive; the Input row says lowercase "unverified"). Removing one mark makes it fail, so the check can fail | covers only the points listed in A31; the matcher, `${CLAUDE_PROJECT_DIR}`, stdout and "enforced by the host" are not covered, see B7 |

All cited paths are under `references/`; none under `references/autogpt/autogpt_platform/`. Both sources are MIT per references/LICENSES.md (deepseek_harness row 12, openharness row 14).

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C5 hook kit | N/A no returns, pricing, backtest, eval or verifier is touched | N/A same | N/A same | N/A same | N/A same | N/A no data split |

The N/A reason is correct: the change is a stdlib path guard, a reference page and prose edits. Step 6.7 is a smoke probe of the guard, not a quant verifier.

## Blocking findings (revise before build)

| # | what | evidence (re-runnable in scratch) | fix the judge expects |
|---|---|---|---|
| B1 (A27) | False pass on ordinary Bash forms: shell punctuation glued to a word defeats the 11 end-anchored patterns | exit 0 for `cat ~/.netrc;ls`, `echo $(cat ~/.npmrc)`, `cat ~/.netrc\|base64`, `(cat ~/.kube/config)`, `` `cat ~/.pypirc` ``, `cat keys/id_rsa;` | tokenise with `shlex.shlex(cmd, posix=True, punctuation_chars=True)` or split each word on `[;&\|()<>`$"']`, then test every piece; add the cases above (and quoted `cat "/h/.npmrc"`) to `test_bash_denies`; correct the two wrong "passes" examples in hooks.md |
| B2 (A25) | Fail-open on parse-stage conditions reachable by content | nested JSON depth >= about 1000 in any `tool_input` field with a sensitive `path` -> exit 1; non-UTF-8 stdin decode (Windows code page, `PYTHONIOENCODING`) with one non-ASCII character -> exit 1 | read bytes: `json.loads(sys.stdin.buffer.read())`; treat `RecursionError` as exit 2 (host JSON the parser cannot hold is not "unreadable"); keep exit 1 only for empty or not-JSON input; add tests: depth 1100 plus sensitive path -> 2, and `PYTHONIOENCODING=ascii` plus `\u00c1` in the command plus sensitive path -> 2 |
| B3 (A24) | Legitimate Bash call blocked by the 4096 cap applied to non-path words | `git commit -m "<4200 chars>"` -> exit 2 `too-long`; same for `gh pr create --body`, `python3 -c "<long>"`, base64 words | apply the cap to `PATH_KEYS` values only (for Bash words skip, or run the pattern check on the first 4096 characters), or state it as a known false positive and add a test; the 4095/4096 boundary test must then name which inputs it covers |
| B4 (A27/A21) | Windows backslashes inside Bash words are consumed by POSIX `shlex` before the `\`->`/` step | `cat C:\Users\u\.ssh\id_rsa` -> exit 0 while `'C:\Users\u\.ssh\id_rsa'` -> exit 2; the hooks.md row says `\` becomes `/` "before anything else" | also test `cmd.replace("\\", "/")` split on whitespace, or narrow the hooks.md row to path keys and add Windows Bash words to "Does not cover"; add a test either way |
| B5 (test bar) | The suite never sends an absolute credential path together with a payload `cwd`, yet every real payload carries `cwd` | mutant N03 (`posixpath.join(X, cwd)` instead of `join(cwd, X)`) lets `{"file_path":"/h/.ssh/id_rsa","cwd":"/w"}` through with exit 0, and all 71 tests pass; the architect's "82 killed, 0 survivors" does not hold against this mutant | add `call({"file_path": "/h/.ssh/k"}, cwd="/w")` -> 2 (and the Bash form) to DENY; make `read()` always send a cwd |
| B6 (c) | Protocol rows rely on a reimplementation and are not all marked UNVERIFIED in hooks.md | see Protocol audit: the intro sentence "enforced by the host before the tool runs", the matcher `*` paragraph, `${CLAUDE_PROJECT_DIR}` in the wiring, and the Stdout row are stated flat; A31's grep does not cover them | add a row each to the "What the host and the script agree on" table with status "Unverified: deepseek bridge only" or reword; extend the A31 check to name them |
| B7 (c) | hooks.md line 1 and checklist E4 say "chat and Cowork run no hook"; surfaces.md and A30 say Cowork is unverified | hooks.md first paragraph, E4 checklist line, E6 | write "chat reported hooks as not exposed; Cowork unknown; treat both as having no guard" |
| B8 (c)(d) | Step 6.7 passes on `/hooks` listing alone; nothing in the build observes that exit 2 actually blocks or that `cwd`/`tool_input` arrive | E3 text; Does-not-cover says the closing check is "`/hooks` plus a real blocked call" but 6.7 does not require the second half | add to 6.7: in a live Code session ask the agent to read a non-existent `~/.ssh/c5-probe` and record whether the guard's stderr line came back; E4 checklist item to require that line |

B7 and B8 are text/proof-bar defects rather than code defects; they are blocking only because the verdict criteria count a protocol claim stated as verified and a proof that cannot fail on the unverified point.

## Follow-up (not blocking)

- F1 Parent-directory recursion is not in "Does not cover" and the "Directory roots" rationale suggests recursive search is covered: `grep -rn BEGIN ~`, `tar czf /tmp/b.tgz ~`, a `Grep` with `path=/h`, `find ~ -name x` all exit 0 (`find ~ -name id_rsa` is denied only because of the word `id_rsa`). Name this limit.
- F2 Undocumented false positives (all exit 2): project-local `.npmrc`, `.pypirc`, `.kube/config`, `.docker/config.json`, a fixture `tests/fixtures/id_rsa`, `docs/.ssh/readme.md`, `git commit -m 'document ~/.ssh/config usage'`, a heredoc that mentions `~/.aws/config`. Add them to the false-positive list.
- F3 Test gaps found by my mutants (below): quoted end-anchored word, absolute path plus cwd, credential-named link as cwd, 4000-character relative path with a long cwd, attached short option `-i/h/.ssh/k`, `file://` URL, over-broad patterns (`*/gcloud/*`, `*/config`), real path through a `.SSH` directory.
- F4 Performance: `shlex.split` is quadratic on an unterminated quote (pure-Python `self.token +=`): command of 400 KB takes 3.1 s, 600 KB 5.9 s, 800 KB 11.6 s, which exceeds the wiring's 10 s timeout, and hooks.md treats a timeout as fail-open. Many small words cost about 3 s per 800 KB (one `realpath` each). Not reachable in one model turn, but cap `len(command)` (deny above a stated limit) or run a raw-string pre-scan before `shlex`.
- F5 Add the `\ud800` trigger beside the NUL one in `test_check_failure_after_parse_blocks` so the test does not depend on interpreter behaviour (NUL raises on 3.10-3.13, checked; 3.14 not available here).
- F6 The wiring test pins the doc against itself; mutation `python3`->`python` in the command survives. It cannot prove host acceptance, which is what Step 6.7 is for.
- F7 hooks.md "Does not cover" claims `<~/.ssh/id_rsa` and `$(echo ~)/.ssh/id_rsa` pass; they are denied (the words contain `/.ssh/`). Fix the wording; the real passes are in B1 and F1.
- F8 Scope: no `.pgpass`, `.config/gh/hosts.yml`, `.terraform.d/credentials*`, `*.pem`, `.env`, `/etc/shadow`. A stated constant list is acceptable; say that it is the minimum.
- F9 The reference reads `root` as a path key (query.py:1026); add it to `PATH_KEYS` or state why not.
- F10 A31's check sits exactly at its threshold (6); make it name the rows instead of counting.
- F11 Message text after `deny_sensitive:` is unpinned (design says so): follow-up by the design's own rule.

## Protocol audit (item c)

| Claim relied on | Where it is relied on | Marked UNVERIFIED? |
|---|---|---|
| Exit 2 blocks, stderr is the reason | hooks.md Block row; D1 docstring; Step 6.7 expectation | Yes (table). The intro sentence "enforced by the host before the tool runs" is not hedged (B6) |
| Other exits non-blocking; signal/cannot-run non-blocking | hooks.md row; Does-not-cover | Yes |
| Payload fields `tool_input`, `cwd` | hooks.md Input row | Yes (lowercase "unverified") |
| Stdout ignored on exit 2 | hooks.md Stdout row | No: status says only "deepseek decoder" (B6) |
| Matcher `*` selects every tool | hooks.md paragraph under the JSON block | No (B6) |
| `${CLAUDE_PROJECT_DIR}` available in the command | wiring JSON | No (B6) |
| Timeout effect, parallel hooks, reload, settings.json shape | hooks.md rows | Yes |
| Hook runs in the session directory | hooks.md "Relative paths" | Yes ("unverified" inline) |
| No hook on Cowork | hooks.md line 1, E4 | Stated as fact; surfaces.md says unverified (B7) |

The design does not treat any of these as verified in its Does-not-cover or Proof sections; the gaps are the unflagged rows and sentences above, plus Step 6.7 (B8).

## Item (d): wiring and the Step 6.7 proof

`test_wiring_block_in_hooks_md` can fail: I mutated hooks.md (timeout 10->30, matcher `*`->`Bash`, `hooks`->`Hooks`, `PreToolUse`->`PostToolUse`, dropping `${CLAUDE_PROJECT_DIR}`): 5 of 5 killed; `python3`->`python` survives. It only compares the doc with itself, so it cannot show that Claude Code accepts the shape. The three script probes in Step 6.7 behave as written (run from the repo root: exit 2 with reason, exit 0, exit 1; stdout empty). Whether `/hooks` lists the entry is outside what I can run (live session); see B8 for the missing blocked-call probe.

## Item (e): NUL and `os.path.realpath`

NUL raises `ValueError` from `realpath` on Python 3.10, 3.11, 3.12 and 3.13 (run). Both forms are built in one tuple before any match, so the raise happens before matching: the fallback (exit 2, `check failed`) is reached, and the test would fail loudly if a newer interpreter stopped raising. Sufficient for security (a NUL path cannot name a real file) but fragile as a test; add the lone-surrogate trigger (F5).

## Item (f): ReDoS and size sweep

`RE.match` on 130 hostile strings (each pattern literal repeated, minus its last character, `/`, `/.`, `/a`, newlines, with and without trailing `/`) at 4096, 65,536 and 1,000,000 characters: worst case 0.5 ms, 8.5 ms and 128 ms, linear. `os.path.expandvars` on `${`*2048 and `$`*4096: 1 ms. No regex hazard. The unbounded quantities are command length and word count (F4), not the regex.

## Item (a) summary: attacks tried

| Vector | Result |
|---|---|
| `=` suffix, quotes, `$HOME`, `${HOME}`, `~`, `~user`, `..`, `.`/`//` collapse, symlink to dir or file, case, `cd ~/.ssh`, `cd ~ && cat .ssh/id_rsa`, `--`, newline-separated words, unbalanced quote fallback | denied |
| `notebook_path`, `path`, `file_path` | denied; other keys (`root`, `paths`, `filepath`, `glob`, `url`) not read (documented in part; F9) |
| Trailing metacharacter on end-anchored names; unquoted Windows backslash word | allowed: B1, B4 |
| Deep JSON nesting; non-UTF-8 stdin decode | allowed (exit 1): B2 |
| 4095 vs 4096 boundary | correct for paths; wrongly applied to every word: B3 |
| NUL, lone surrogate | exit 2 |
| Empty, huge, non-object, missing `tool_input` | exit 1 as designed (empty/garbage fail-open is the stated protocol choice) |
| Payload without `cwd`; `cwd` empty or non-string | handled as designed |
| Parent-directory recursion, scripts written then run, globs, `$(echo ~)` assembly | allowed; documented only in part (F1) |

## Mutants (23 of my own; none taken from the architect's families)

Each mutation was applied to a scratch copy by exact single-occurrence substitution (count asserted == 1, resulting file asserted different), then the full 71-test file run once per mutant.

| id | mutation | result | test that should kill it |
|---|---|---|---|
| N01 | `shlex.split(cmd)` -> `shlex.split(cmd, posix=False)` | SURVIVED | `cat "/h/.npmrc"` -> 2 (quoted end-anchored word) |
| N02 | `.replace("\\","/")` -> `.replace("\\","/",1)` | killed | — |
| N03 | `join(cwd, X)` -> `join(X, cwd)` | SURVIVED (guard off on every real payload) | `{"file_path":"/h/.ssh/k","cwd":"/w"}` -> 2 (B5) |
| N04 | lexical form ignores cwd (`normpath(raw)`) | SURVIVED | cwd = link named `.ssh` to an innocent dir, `file_path: "k"` -> 2 |
| N05 | realpath form ignores cwd | killed | — |
| N06 | length check on joined path instead of `raw` | SURVIVED | 4000-character relative path with a 200-character cwd -> 0 |
| N07 | `casefold` -> `lower` | SURVIVED, equivalent for these ASCII patterns | none needed |
| N08 | absent cwd resolves to `/` | killed | — |
| N09 | reason not truncated (`raw[:200]` -> `raw[:20000]`) | killed | — |
| N10 | `except Exception` -> `except (OSError, ValueError)` | SURVIVED | no black-box trigger outside `ValueError`/`OSError` found; keep, or note as unkillable |
| N11 | skip words that start with `-` | SURVIVED | `ssh -i/h/.ssh/id_rsa host` -> 2 |
| N12 | skip words containing `://` | SURVIVED | `curl file:///h/.ssh/id_rsa` -> 2 |
| N13 | gcloud pattern widened to `*/gcloud/*` | SURVIVED | ALLOW `/w/src/gcloud/x.py` |
| N14 | azure pattern changed to `*/azure/*` (narrowing) | killed | — |
| N15 | kube pattern widened to `*/config` | SURVIVED | ALLOW `/w/.git/config` and `/w/config` |
| N16 | `shlex.split` replaced by whitespace split | SURVIVED | same as N01 |
| N17 | gnupg pattern loses `/*` | killed | — |
| N18 | backslash replaced by `//` | SURVIVED, equivalent (normpath collapses) | none needed |
| N19 | casefold applied to lexical form only | SURVIVED | symlink to a real directory named `.SSH` -> 2 |
| N20 | payload cwd ignored unless absolute | killed | — |
| N21 | `=` remainder loses its leading `~` | killed | — |
| N22 | directory-root probe `f + "//"` | SURVIVED, equivalent (still matches `/.ssh//`) | none needed |
| N23 | reason text `sensitive-path ` (trailing space) | killed | — |

23 mutants: 9 killed, 14 survived; 4 of the survivors are equivalent or unkillable (N07, N10, N18, N22), 10 are real test gaps (N01/N16 count once as a gap: N01, N03, N04, N06, N11, N12, N13, N15, N16, N19). N03 is the serious one (B5).

## Verbatim and attribution (item g)

8-word runs (case-folded, punctuation-light tokenisation) computed for the script, the test file, hooks.md and the lines added to SKILL.md/surfaces.md against all 65 files under the deepseek hooks packages, openharness `permissions/`, `hooks/`, `plugins/loader.py` and `engine/query.py`: 0 shared runs (also 0 shared 6-word runs). Attribution lines present as required: script docstring (two lines, codec.ts:59 and checker.py:20, both MIT), hooks.md last line, the E1 bullet. The docstring's `codec.ts:59` lands in the `parseHookOutput` doc comment, which is the exit-code contract; acceptable.

## Escalation

Not applicable (round 1/3).
