UPHELD 27 / REJECTED 7 / UNVERIFIED 0 — round 1/3

# Adversarial verdict — OH31 sensitive-path denylist (revision 1)

- Audited file: _workspace/07_oh31-denylist_design.md (revision 1), Authority List A1-A30 plus design defects D1-D4 found by probing the code
- Audited: 2026-10-02, fresh context, round 1/3
- Reference pin checked: `references/openharness` HEAD = 9b2efd795c6a (matches 9b2efd7); licence MIT per `references/LICENSES.md:14`, so `adapt` is allowed
- Probes: read-only `python3 -c` / heredoc against `src/` (Python 3.11.15), no files written. The proposed matcher was simulated exactly as the Behaviour section specifies, to test bypasses.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | checker.py:14 ; :18 | :14 comment "always denied regardless of permission mode or user config"; :18 `SENSITIVE_PATH_PATTERNS` tuple | — |
| A2 | UPHELD | checker.py:20 | `"*/.ssh/*"` | — |
| A3 | UPHELD | checker.py:22 ; :23 | `"*/.aws/credentials"`, `"*/.aws/config"` | — |
| A4 | UPHELD | checker.py:25 | `"*/.config/gcloud/*"` | — |
| A5 | UPHELD | checker.py:27 | `"*/.azure/*"` | — |
| A6 | UPHELD | checker.py:29 | `"*/.gnupg/*"` | — |
| A7 | UPHELD | checker.py:31 | `"*/.docker/config.json"` | — |
| A8 | UPHELD | checker.py:33 | `"*/.kube/config"` | — |
| A9 | UPHELD | checker.py:84 ; :105 | :84-98 sensitive check returns deny first; :101 denied_tools, :105 allowed_tools, :129 mode come after | — |
| A10 | UPHELD | checker.py:169 | `return (normalized, normalized + "/")` in `_policy_match_paths` | — |
| A11 | UPHELD | query.py:1029 ; :1032 | `Path(value).expanduser()`; `return str(path.resolve())` | the source resolves relative paths against the `cwd` parameter; the design uses the process cwd (disclosed) |
| A12 | UPHELD | query.py:1026 | `for key in ("file_path", "path", "root"):` | — |
| A13 | UPHELD | checker.py:91 | `fnmatch.fnmatch(candidate_path, pattern)` | the design uses `fnmatchcase` on casefolded input, which is equivalent and platform-independent |
| A14 | UPHELD | NET-NEW | — | reason stated; the test `"openharness" not in ...` can fail |
| A15 | REJECTED | NET-NEW | — | The design says a `bash -c` payload "arrives as one word that still contains `/.ssh/`". That is false once the payload has its own quoting, because the scan does not re-lex inline payloads the way `_inline_rule` (safety.py:285-296) does. In the simulated matcher these all PASS: `bash -c 'cat ~/.a"w"s/credentials'`, `bash -c "cat ~/.a\ws/credentials"`, `sh -c 'cat ~/.n\etrc'`, `eval 'cat ~/.a"w"s/credentials'`. The named test covers only an unquoted payload. Fix: recurse into `-c`/`/c`/`-Command`/`eval` payloads (re-lex at depth+1, reusing `_inline_kind`), or drop the claim and list nested-shell quoting under "Does not cover". Also add brace expansion (`~/.a{w,}s/credentials`) and ANSI-C quoting (`~/$'\x2e'aws/...`) to "Does not cover"; both pass. |
| A16 | UPHELD | NET-NEW | — | reason stated; the tests can fail (`cp -r ~/.kube x` fails without the `*/.kube` root) |
| A17 | UPHELD | NET-NEW | — | reason stated; `~/.SSH/ID_RSA` does not match any pattern without casefold on Linux, so the test can fail |
| A18 | UPHELD | NET-NEW | — | reason stated; the tests can fail. The incomplete Windows forms are logged as D3 |
| A19 | REJECTED | NET-NEW | — | The named verification cannot fail if the lexical form is removed. With the resolved form alone, `{"path": "a/../../.ssh/id_rsa"}` is still denied (`<cwd parent>/.ssh/id_rsa`), `~/.ssh/../notes.txt` still passes, and the symlink case proves the resolved form, not the lexical one. The stated reason ("the resolved form alone can miss" relative words) does not hold either: a relative `.ssh/x` resolves under cwd and still matches. The real lexical-only catches are Windows forms (`{"path": "C:\\Users\\client_a\\.aws\\credentials"}` resolves to `<cwd>/C:\Users...`, which does not match). Name that as A19's killing test, restate the reason, and add mutant "resolved form only" to the mutation targets. |
| A20 | UPHELD | NET-NEW | — | the NUL path raises ValueError in `resolve()`; the simulation denied it only through the exception path. Fail-closed convention confirmed at safety.py:11, :493, :564 |
| A21 | UPHELD | NET-NEW | — | ordering verified, see substance (b) |
| A22 | UPHELD | NET-NEW | — | `_denial` (safety.py:510-514) interpolates only the rule name and reason; the test can fail |
| A23 | UPHELD | NET-NEW | — | reason stated (`McpTool` forwards argument names verbatim); the tests can fail. The missing length cap on path values is logged as D2 |
| A24 | UPHELD | NET-NEW | — | reason stated; the tests can fail; `/workspace/.netrc.example` passes (simulated) |
| A25 | UPHELD | NET-NEW | — | reason stated; the test can fail |
| A26 | UPHELD | NET-NEW | — | reason stated; the test can fail |
| A27 | UPHELD | NET-NEW | — | reason stated; the test can fail |
| A28 | UPHELD | NET-NEW | — | reason stated; `/workspace/id_rsa.pub` and `known_id_rsa_fingerprint.txt` pass (simulated) |
| A29 | UPHELD | NET-NEW | — | all five sites confirmed: cli.py:133, server/app.py:339 (`_both(guard_tool_call, extra)`), subagent.py:233 and team.py:567 (default `guard=guard_tool_call`), evals/runner.py:151. No other `AgentLoop(` construction exists. The design does not list `run_team(guard=<custom>)` as an override hole (only root `SubagentConfig`); add it to "Callers that bypass". The two unlisted `check_command` callers are logged as D1 |
| A30 | REJECTED | NET-NEW | — | "verification: none needed": the row cannot fail, so it is not a claim. Delete it (the "Does not cover" table already states the scope) or turn it into a check that can fail |

## Design defects found on substance (count toward REJECTED)

| id | verdict | evidence (opened / run) | reason / fix |
|---|---|---|---|
| D1 | REJECTED | `tools/mcp/client.py:149` `check_command(shlex.join(self._server.command))`; `sandbox/docker_engine.py:123` `check_command(command, self._policy)` | Finding 3 says extending `check_command` "changes no wiring", but two callers are missing from it. (1) MCP server launch argv is operator-configured, not model-supplied, and would now be refused if it names a credential path, e.g. `docker run -v ~/.kube/config:/root/.kube/config ...` or `aws-mcp --config ~/.aws/config`. That changes behaviour silently and no test covers it. (2) Every in-container command goes through the new check (probably wanted, but unstated). Fix: list both callers, decide the launch-path behaviour (deny on purpose, or use `check_rule` + allowlist there), and add one test for each. |
| D2 | REJECTED | simulated `is_sensitive_path("a/"*(n//2)+"x")`: n=10k 0.023 s, 100k 0.39 s, 400k 4.5 s | Path-arg matching grows quadratically (`Path.resolve` walks every component) and path values have no length cap. Command words are capped by `MAX_COMMAND_CHARS` (:26, :472), path values are not. This breaks the module's "linear, capped" invariant (docstring :10-11), and a model-supplied argument can stall the guard. Fix: deny any path value longer than `MAX_COMMAND_CHARS` (or 4096) before expanding or resolving (fail closed), with a test. |
| D3 | REJECTED | simulated: `type C:\Users\a\_netrc.` PASS, `type C:\Users\a\_netrc::$DATA` PASS, `type C:\Users\a\.git-credentials.` PASS, `type C:\Users\a\AWS~1\credentials` PASS | Inside the claimed Windows coverage (A18, A24, A27, A28): Win32 strips trailing dots and spaces and accepts `::$DATA` stream suffixes, so end-anchored patterns (`*/_netrc`, `*/.git-credentials`, `*/.npmrc`, `*/id_*`, `*/.kube/config`, `*/.docker/config.json`) miss. Fix: strip trailing `.`/space and any `:<stream>` suffix from each segment of the lexical form, and add tests. List 8.3 short names (`AWS~1`, `SSH~1`) under "Does not cover". |
| D4 | REJECTED | test plan vs simulated mutants | Planned tests let these mutants survive. (i) **Scan only the non-POSIX stream**: every planned command case is also caught by the non-POSIX stream. Add POSIX-only catches: `cat ~/.a"w"s/credentials`, `cat ~/.a\ws/credentials`. (ii) **Check only the first argument**: the not-overridable loop for `cat cp scp rsync tar base64 git grep` names no strings. Pin them, with at least one case where the sensitive path is last after a benign argument (`grep -r KEY ~/.aws`, `tar czf /workspace/k.tgz ~/.ssh`), plus a write-direction case, which nothing tests today (`cp /workspace/k ~/.ssh/authorized_keys`, `echo x >> ~/.ssh/authorized_keys`). (iii) **Resolved form only**: not in the mutation targets (see A19). The "only the text form" mutant (path-key branch deleted) is killed by the per-pattern path-arg tests, as the spare target says. |

## Substance checks that held

- (a) Reproduced with a read-only one-liner on the current tree. `check_command` returns None in default mode and with the allowlist {cat, cp, scp, rsync, tar, base64, git, grep} for all eight finding-1 commands, including `cat ~/.ssh/id_rsa`, `cat $HOME/.aws/credentials` and `base64 ~/.ssh/id_ed25519`. `guard_tool_call(ToolCall("1","mcp_read",{"path":"/root/.ssh/id_rsa"}))` and `make_guard(allowlist)(...)` both return None. Cause confirmed: `_guard` (:546-565) only checks `COMMAND_ARG_KEYS` (:30).
- (b) Ordering is sound. `check_command` allows only at :523 and :535. The allowlist loop (:528-534) can only deny. `_check_value` either goes through `check_command` or denies (:543). `_guard` allows only at :563, after the loop where the path-key check sits. `make_guard` and `guard_tool_call` route to `_guard`. `_both` (subagent.py:114-118) evaluates the parent first. `AgentLoop._uncertain` (loop.py:208) and `_execute` (:222) call the same guard. No path returns allow before the new check.
- (c) All five call sites confirmed (see A29).
- (d) Simulated matcher denies: `"~/.ssh/id_rsa"` (tilde in quotes), `${HOME}`, `"$HOME"/...`, `~root/...`, `.//.aws//credentials`, `ls ~/.ssh/`, `ssh -i~/.ssh/id_rsa`, `curl --netrc-file=~/.netrc`, `/root/.SSH/x`, NUL path. Must-still-pass cases pass, including `git commit -m "add .ssh/ to gitignore"`, `ls ~/.ssh-docs`, `~/.sshrc` and `~/.ssh/../notes.txt`. `fnmatch` patterns compile to a single anchored `.*` regex and run in linear time. Worst-case command scan (10k chars, 460 words, both streams, `resolve` per word) took 0.027 s. Lower-casing only adds false denials for case variants of listed names, which the design discloses. Bypasses are listed in A15 and D3.
- (e) No import cycle. `tools/__init__.py` is empty, `safety.py` imports only `runtime.loop`, and `sensitive_paths.py` (stdlib only) imports nothing from `master_finhub`. The design's reason for keeping `sensitive_in_command` in `safety.py` is correct.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 3 (OH31 add-on) | N/A no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no data split |
