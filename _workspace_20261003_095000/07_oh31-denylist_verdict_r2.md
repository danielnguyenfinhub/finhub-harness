UPHELD 32 / REJECTED 3 / UNVERIFIED 0 — round 2/3

# Adversarial verdict — OH31 sensitive-path denylist (revision 2)

- Audited file: _workspace/07_oh31-denylist_design.md (revision 2): Authority List A1-A35 (A30 withdrawn, not counted, so 34 claims) plus one new design defect (D5) found by probing
- Prior verdict read: _workspace/07_oh31-denylist_verdict.md (round 1: UPHELD 27 / REJECTED 7). Each round-1 finding was re-judged from scratch against the code.
- Audited: 2026-10-02, fresh context, round 2/3
- Reference pin: `references/openharness` HEAD = 9b2efd795c6a (matches 9b2efd7), MIT
- Probes: read-only. The proposed rule was simulated exactly as the Behaviour section specifies, in a scratchpad module (outside the repo) that monkeypatches `safety.segment_rule`. The existing suites were run against it with `pytest -p no:cacheprovider` and `PYTHONDONTWRITEBYTECODE=1`, so nothing in the repo was written. Python 3.11.15 (`.venv`), 4 cores. Timings are best of 3 where noted. Two matcher variants were timed: **literal**, a per-pattern `fnmatchcase` loop as written in Behaviour step 5, and **combined**, one compiled alternation regex.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD (spot-checked) | checker.py:14 ; :18 | :14 "always denied regardless of permission mode or user config"; :18 `SENSITIVE_PATH_PATTERNS` | — |
| A2 | UPHELD (carried) | checker.py:20 | `"*/.ssh/*"` | — |
| A3 | UPHELD (spot-checked) | checker.py:22 ; :23 | `"*/.aws/credentials"`, `"*/.aws/config"` | — |
| A4 | UPHELD (carried) | checker.py:25 | `"*/.config/gcloud/*"` | — |
| A5 | UPHELD (carried) | checker.py:27 | `"*/.azure/*"` | — |
| A6 | UPHELD (carried) | checker.py:29 | `"*/.gnupg/*"` | — |
| A7 | UPHELD (carried) | checker.py:31 | `"*/.docker/config.json"` | — |
| A8 | UPHELD (carried) | checker.py:33 | `"*/.kube/config"` | — |
| A9 | UPHELD (spot-checked) | checker.py:84 ; :105 | :84-98 sensitive check returns deny first; :101 deny list, :105 allow list follow | — |
| A10 | UPHELD (carried) | checker.py:169 | `return (normalized, normalized + "/")` | — |
| A11 | UPHELD (spot-checked) | query.py:1029 ; :1032 | `Path(value).expanduser()`; `return str(path.resolve())` | — |
| A12 | UPHELD (spot-checked) | query.py:1026 | `for key in ("file_path", "path", "root"):` | — |
| A13 | UPHELD (spot-checked) | checker.py:91 | `fnmatch.fnmatch(candidate_path, pattern)` | — |
| A14 | UPHELD (carried) | NET-NEW | — | — |
| A15 | UPHELD | NET-NEW | safety.py:285 `_inline_rule`, :299 `segment_rule`, :482-485 both streams | Closed. Simulated with the rule as the first statement of `segment_rule`: `bash -c 'cat ~/.a"w"s/credentials'`, `bash -c "cat ~/.a\ws/credentials"`, `sh -c 'cat ~/.n\etrc'`, `eval 'cat ~/.a"w"s/credentials'`, `cmd /c type C:\Users\client_a\_netrc`, `pwsh -Comm "Get-Content ~/.ssh/id_rsa"`, `eval eval eval cat ~/.a"w"s/credentials` all return `sensitive-path`. Mutation 6 (no `sensitive` on re-entry) is killed by the first case. Interface gap (not counted): `_State` is constructed in `_check_tokens` (`_State(depth=depth)`), which is not in the Files/Interfaces list of functions the keyword is threaded through. The A31 test would catch the omission, so this is not a defect, but name it. Cost: see A35 |
| A16 | UPHELD (carried) | NET-NEW | — | — |
| A17 | UPHELD (carried) | NET-NEW | — | The cross-reference "(mutation 3)" is stale. Mutation 3 is now resolved-form/lexical-form only. The case tests still kill a casefold mutant |
| A18 | UPHELD (carried) | NET-NEW | — | — |
| A19 | UPHELD | NET-NEW | — | Closed. Under a "resolved form only" mutant, `{"path": "C:\\Users\\client_a\\.aws\\credentials"}` is no longer denied, so the mutant is killed. Correction needed: "both fail under mutation 3" is false. `{"file_path": "c:/users/client_a/_netrc"}` resolves to `<cwd>/c:/users/client_a/_netrc`, which still matches `*/_netrc` (simulated: resolved_only=True). Drop "both" |
| A20 | UPHELD (carried) | NET-NEW | safety.py:491-494 fail-closed | — |
| A21 | UPHELD | NET-NEW | safety.py:519 `rule = check_rule(command)`; :523 `return None`; :528-534 allowlist loop only denies; :535 `return None` | Ordering holds: the rule lives inside `check_rule`, which runs before both allow exits. The pinned table kills mutant 5 "first argument only" (simulated: killed) |
| A22-A29 | UPHELD (carried) | NET-NEW | — | — |
| A30 | WITHDRAWN | — | — | not counted |
| A31 | UPHELD | NET-NEW | client.py:149 `check_command(shlex.join(self._server.command))`; :70-72 `StdioServer` | No model-controlled input reaches the call site. `grep` finds no `StdioServer(`/`McpClient(` construction anywhere in `src/` (tests only), and no config loader. The live-stub case is sound: `start()` only spawns, and the stub reads `sys.argv[1:]` as mode flags. Weakness (not counted): the "exactly one file under `src/` contains `sensitive_paths=False`" test is a spelling check. It misses `sensitive_paths=0`, `**{"sensitive_paths": False}`, `check_rule(..., sensitive_paths=False)`, or a direct `_check(..., sensitive=False)`. A stronger tripwire: an AST or regex scan for any `sensitive_paths`/`sensitive=` keyword outside `safety.py` (allowing one occurrence, in `client.py`), plus the live launch test |
| A32 | UPHELD | NET-NEW | docker_engine.py:123 `denial = check_command(command, self._policy)`; :104 workspace bind; tests/test_docker_engine.py:93-97 Popen patched to raise | Default stays on. The proposed test mirrors the existing `test_engine_blocks_denied_command` |
| A33 | REJECTED | NET-NEW | — | **The cap is applied to the raw value, before `expandvars`, so a short `$VAR` expands past it unchecked.** `{"path": "$PATH"*819}` is 4,095 raw characters and passes the cap. It expands to 182,637 characters, and `is_sensitive_path` takes **0.40 s** with this box's 223-character `PATH` (cost grows quadratically with the host's `PATH` length). A list value multiplies it: `{"paths": ["$PATH"*819]*10}` (41 KB of JSON) takes **4.5 s**. That is the same stall D2 rejected, still reachable. Commands have no expanded-length cap at all (see A35). Fix: cap the **expanded** string inside `is_sensitive_path` (deny `path-too-long`, or skip `resolve` when the expanded string is longer than 4,096), so command words get the cap too. Add a `$VAR`-expansion case and a list-of-N case to the A33 tests. The 4,096 figure itself is fine: Linux `PATH_MAX`, disclosed |
| A34 | UPHELD | NET-NEW | — | Closed D3. Simulated: `_netrc.`, `_netrc::$DATA`, `.git-credentials.`, `.kube\config ` (trailing space) and `.ssh.\id_rsa` are denied. `notes.txt.`, `/workspace/report.v1.` and POSIX `cat c:/x` pass. A POSIX `notes.` gives no false denial, and the drive rule leaves `c:/x` intact. Two text fixes (not counted): (a) the "known false positive" example `a:b/.ssh-x` is wrong: it strips to `a/.ssh-x` and passes (simulated `None`). A real example is `.ssh:notes/x` → `.ssh/x`. (b) `.ssh.\id_rsa` does not exercise stripping, because `*/id_rsa` matches it either way. Also see note N1 |
| A35 | REJECTED | NET-NEW | tests/test_safety.py:220-232 | **The claim "keeps the module's linear-time budget" is false. Resolving only path-like words does not bound cost, because the attacker picks path-like words and nesting re-scans them.** `_inline_rule` re-checks `" ".join(args[i+1:])`, so an **unquoted** chain `bash -c bash -c bash -c W...` scans the word list 2+4+8+16 = 30 times. Measured (literal / combined matcher; today's code in brackets): `"bash -c "*3 + "./a "*2490` = **3.3 s / 2.0 s** [0.13 s]; `"bash -c "*3 + "~ "*4980` = **4.8 s / 2.8 s** [0.16 s]; `"eval "*3 + "./a "*2490` = **3.4 s / 2.0 s**; non-path words `"bash -c "*3 + "a "*4980` = **1.7 s / 0.6 s** [0.21 s]. Combined with the A33 expansion hole: `"cat " + "$PATH"*1990` = **4.8 s**; the same behind `bash -c ` ×3 = **67 s**. The budget is 0.25 s. The design's own budget case `bash -c './a ...'*1600` takes 0.233 s literal, a 7% margin. **The literal spec (per-pattern `fnmatchcase`) also breaks the existing test**: run against the real `tests/test_safety.py`, `test_adversarial_inputs_are_linear` fails `first19 < 1.0` (1.45 s and 1.62 s in two runs). The combined regex passes (0.66 s). The Proof line "unchanged and still pass" therefore does not hold as specified. Bare-name symlinks *are* honestly listed under "Does not cover". Words outside the path-like set reach credentials only by cwd-relative bare names (e.g. `cat credentials` with the host cwd in `~/.aws`). The row's generic sentence covers those. Fix (simulated): memoise `is_sensitive_path` per top-level `check_rule` call (a dict keyed by `(word, resolve)`), and specify one compiled regex. Measured with both: unquoted nest3 `./a` 0.11-0.15 s, `~` 0.14-0.18 s, 1,500 distinct `./N` words 0.20-0.21 s. Add the expanded-length cap from A33, and add the nested-unquoted and `$PATH` vectors to the timing test |

## Design defects found this round (count toward REJECTED)

| id | verdict | evidence (opened / run) | reason / fix |
|---|---|---|---|
| D5 | REJECTED | simulated mutant: rule moved after `core = strip_wrappers(words)` / `if not core: return None`, scanning `core` | The design requires the rule to run **before `strip_wrappers`** so that assignment words and wrapper arguments are seen (Behaviour, "Command strings"). No named test pins this. **All** command cases in the test plan stay red under the mutant, including `K=~/.ssh; cat $K/id_rsa`, which `$K/id_rsa` still catches via `*/id_rsa`. Cases the mutant lets through (design denies, mutant `None`): `K=~/.aws; cat $K/credentials`, `xargs -a ~/.ssh/id_rsa echo`, `env -C ~/.aws cat credentials`. Fix: add those three to the test plan, and add mutation target "rule after `strip_wrappers` / early `return None`" |

## Round-1 findings — closure check (not counted again)

| r1 id | status | how verified |
|---|---|---|
| A15 | closed | see A15 row; nested payloads with their own quoting are re-lexed and denied |
| A19 | closed | Windows path-argument case kills "resolved form only"; "both" wording to fix |
| A30 | closed | withdrawn |
| D1 | closed | both direct callers named and decided (A31 opt-out, A32 default on), each with a test |
| D2 | **open** | moved to A33, which caps only the raw value; expansion bypasses it (A33 REJECTED) |
| D3 | closed | segment stripping denies `_netrc.`, `::$DATA`, `.git-credentials.`; 8.3 names listed |
| D4 | closed | mutants simulated against the plan's command list: non-POSIX-only killed (`cat ~/.a"w"s/credentials`, `cat ~/.a\ws/credentials`, `cat ~/.n'e'trc`); POSIX-only killed (`type C:\Users\client_a\.ssh\id_rsa`, `%USERPROFILE%\.ssh\id_rsa`, `_netrc.`, `::$DATA`); first-argument-only killed; resolved-only killed; check placed after `check_command`'s denylist-mode `return None` killed (`check_command("cat ~/.kube/config")` default-mode case). A new survivor appeared, logged as D5 |

## Notes (not counted; the architect should address them in the same revision)

- **N1 — Windows drive-relative paths.** `type C:.aws\credentials` and `type C:.ssh\config` pass (simulated `None`). The stripping rule treats `C:.aws` as stream `C` + `:.aws`, so `.aws` is dropped; `*/id_rsa` happens to catch `C:.ssh\id_rsa` only. Relative `.aws\credentials` is denied, so this is inconsistent. No Windows host is declared (CI is ubuntu-only), so the impact is low. Either split a segment-0 `x:rest` into `x:` + `rest`, or add a "Does not cover" row.
- **N2 — `resolve` on a Windows host.** With A35, any command word containing `\` is resolved. On a Windows host, `Path(r"\\host\share\x").resolve()` opens a UNC path, so the guard itself would make an outbound SMB connection (credential-hash leak). Not reachable on the current Linux-only hosts. If Windows hosts are ever supported, skip `resolve` for UNC (`\\` / `//` prefixed) words.
- **N3 — scope of the timing claim.** Even today, unquoted `"bash -c "*3 + "a "*4980` takes 0.21 s, near the 0.25 s limit. Memoising, as in the A35 fix, would also help the existing rules.
- Spot-checked unchanged rows: A1, A3, A9, A11, A12 (plus A13): all at the cited lines. All safety.py line citations in the design (:285, :299, :307, :409-411, :470, :482-485, :491-494, :519, :523, :528-535) and subagent.py `_both` :111-118, loop.py :208/:221 match.
- The existing suites (`test_safety`, `test_modes_sub`, `test_modes`, `test_mcp_client`, `test_docker_engine`, `test_workspace`) pass under the simulated rule with the combined matcher (294 passed, 5 skipped). The only failure, with the literal matcher, is the timing test (A35). Every `ALLOWED` command still passes.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 3 (OH31 add-on) | N/A no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no data split |
