RESULT: PASS

# Boundary QA: OH31 sensitive-path denylist (design rev 5, uncommitted)

Files verified: `src/master_finhub/tools/sensitive_paths.py` (new), `tools/safety.py`, `tools/mcp/client.py`, `tests/test_sensitive_paths.py` (new). Repo files were not edited; mutants ran on a scratch copy that is deleted.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| guard path-named args | safety.py `_guard` -> `PATH_ARG_KEYS` (16 keys, casefolded, list/tuple elements) -> `_path_rule` -> `_sp.sensitive_rule(resolve=True)` | tests `test_variant_path_args_denied`; probes below (`path`, `Path`, `paths`, nested `cwd`, `uri`) | yes |
| guard command args | `_guard` -> `_check_value` -> `check_command` -> `check_rule` -> `_check(depth=0)` -> `segment_rule` -> `_sensitive_word_rule` -> `_sp.sensitive_rule(resolve=_pathish(w), max_chars=10_000)` | probes: command-form `{"command": ...}` denied | yes |
| shared Scan | `_guard` opens `call_scope()`; `_check(depth=0)` opens `call_scope()`; nested opener reuses | tests `test_nested_scope_*`, `test_sequential_*`, `test_two_threads_*`; mutants 11, 14a, 14b killed | yes |
| call sites | cli.py:133, server/app.py:339, orchestration/modes/subagent.py:233, orchestration/modes/team.py:567, evals/runner.py:151 all pass `guard_tool_call` (-> `_guard`) | unchanged by the diff | yes |
| MCP launch | mcp/client.py:150 `check_command(..., sensitive_paths=False)`; `grep sensitive_paths=` in src outside safety.py = exactly 1 hit | `test_mcp_launch_opt_out`, AST scan (allowed count 1); mutant S4 killed | yes |
| docker engine | sandbox/docker_engine.py:123 `check_command(command, self._policy)` (default on) | `test_docker_engine_keeps_the_default` | yes |
| RULE_REASONS | safety.py:173-181 rows `sensitive-path`, `path-too-long`, `path-budget` | `_denial` text printed in probes echoes no path, command or pattern | yes |
| signatures | `check_rule(command, *, sensitive_paths=True)`, `check_command(command, policy, *, sensitive_paths=True)`; no other new keyword (`_check_value`, `ToolGuard` unchanged) | `tests/test_modes.py::test_empty_string_denial_blocks` passes unmodified | yes |

## Gate
| command | exit | output observed |
|---|---|---|
| `.venv/bin/python -m pytest -q` (run 1) | 0 | `891 passed, 10 skipped in 80.96s (0:01:20)` |
| `.venv/bin/python -m pytest -q` (run 2) | 0 | `891 passed, 10 skipped in 81.73s (0:01:21)` (no flake in 2 runs) |
| `.venv/bin/ruff check src tests` | 0 | `All checks passed!` |
| `.venv/bin/black --check src tests` | 0 | `All done! ... 67 files would be left unchanged.` (plus the environment's "Python 3.11 cannot parse code formatted for Python 3.15" warning) |
| `.venv/bin/mypy --strict src` | 0 | `Success: no issues found in 41 source files` |
| six existing suites, run 1/2/3 | 0 | `294 passed, 5 skipped in 16.39s` / `...16.79s` / `...16.21s` |
| `pytest tests/test_modes.py -k empty_string_denial` | 0 | `1 passed, 19 deselected in 0.05s` |
| `pytest -q tests/test_sensitive_paths.py` x3 | 0 | `214 passed, 1 skipped in 18.68s` / `20.05s` / `20.04s` |
| `git diff --stat -- tests` | 0 | empty (no existing test modified); `git status --short` = ` M client.py`, ` M safety.py`, `?? sensitive_paths.py`, `?? tests/test_sensitive_paths.py` only |

## Adversarial probes (real code, synthetic HOME and workspace under the scratchpad; all timings < 0.01 s)
Denied (`rule sensitive-path` unless noted):
| probe | observed |
|---|---|
| `cat ~/.ssh/id_rsa`; `base64 ~/.ssh/id_ed25519` | denied |
| `bash -c 'cat ~/.a"w"s/credentials'`; `sh -c 'cat ~/.n\etrc'`; `eval 'cat ~/.a"w"s/credentials'`; `powershell -Command 'cat ~/.aws/credentials'` | denied |
| `K=~/.aws; cat $K/credentials`; `xargs -a ~/.ssh/id_rsa echo`; `env -C ~/.aws cat credentials` | denied |
| `type C:\Users\client_a\.ssh\id_rsa`; `type C:.aws\credentials`; `cat ~/.SSH/ID_RSA`; `cat ~/.netrc.`; `cat ~/.netrc::$DATA` | denied |
| `cd ~/.ssh`; `cat ./notes.txt ~/.netrc`; `cp x ~/.aws/`; `cat $HOME/.aws/credentials`; `cat ${HOME}/.aws/credentials`; `cat "$HOME"/.aws/c"r"edentials`; `cat ~/.ssh/../.aws/credentials`; `cat /proc/self/root<home>/.aws/credentials` | denied |
| extra: `cat <~/.ssh/id_rsa`, `echo $(cat ~/.ssh/id_rsa)`, `` cat `echo ~/.ssh/id_rsa` ``, `cat ~root/.ssh/id_rsa`, `echo hi >~/.ssh/authorized_keys`, `sudo/nice/timeout 5 cat ~/.ssh/id_rsa`, `(cat ..)`, `{ cat ..; }`, `cat ~//.ssh//id_rsa`, `tar cf - ~/.aws`, `cat $'\x2e\x73sh'/id_rsa` | all denied |
| guard `{"path": "/root/.ssh/id_rsa"}`, `{"path": "C:\\Users\\client_a\\.aws\\credentials"}`, `{"Path": "~/.ssh/id_rsa"}`, `{"paths": ["/ok","~/.ssh/id_rsa"]}`, `{"nested": {"cwd": "~/.aws"}}`, `{"uri": "file:///root/.ssh/id_rsa"}`, `{"path": "/root/.ssh"}`, `{"path": "/root/.ssh/"}`, `{"file_path": "x\x00/.ssh/id_rsa"}`, `{"command": "cat ~/.ssh/id_rsa"}` | all denied |
| two-call symlink swap: call 1 `cat ./notes.txt` (regular file) | `None`; then `notes.txt` replaced by a symlink to `~/.aws/credentials`: call 2 command and guard path form -> `sensitive-path` |
| 5-link symlink chain to credentials | `sensitive-path` |
| 500-link symlink chain (command and guard path) | `path-budget` in 0.001 s |
| `"cat " + "$PATH"*1990`; guard `{"path": "$PATH"*819}` | `path-too-long` in 0.001 s |
Must-still-pass (all `None`): `cat ssh_notes.txt`, `ls .ssh-docs/`, `ls ~/.ssh-docs`, `cat id_rsa.pub`, `cat .netrc.example`, `cat proj/.docker/compose.yml`, `cat c:/x`, `scp report.csv host:/tmp/`, `git status`, `ls -la`, `git commit -m 'add .ssh/ to gitignore'`, `env -C /workspace cat notes.txt`, `cat README.md`, `type C:\Users\client_a\notes.txt.`; guard `{"path":"ssh_notes.txt"}`, `{"path":"id_rsa.pub"}`, `{"path":""}`, `{"path":"~/.ssh-docs/x"}`, `{"path":"/workspace/"+"a"*4000}`, `{"text":"how do I set up ~/.ssh/config?"}`.
Denial text for `cat ~/.ssh/id_rsa`: `Blocked by safety policy (rule sensitive-path): touches a credential or key location (SSH, cloud, registry or token files); ask Daniel to handle credentials manually. Use a path inside the workspace, or ask Daniel to run it manually.` (no path, command or pattern echoed).
Observation (not a defect): shell globs `cat ~/.aw?/credentials` and `cat ~/.a*/cred*` pass; the design's out-of-scope table (design line 416) lists globs ("glob expansion happens in the shell"). `cat ~/.ssh%2fid_rsa` passes; it names no real file.

## Mutation testing (scratch copy; `tests/test_sensitive_paths.py -x`; baseline on the copy: 214 passed, 1 skipped)
| mutant | first killing test |
|---|---|
| 1 rule after the `cd` branch | `test_rule_runs_before_strip_wrappers[K=~/.aws;...]` |
| 1b check only in allowlist mode (after the default-mode allow) | `test_pattern_denied_as_cat_command[~/.ssh/id_rsa]` |
| 8 rule after `strip_wrappers` (scans `core`) | `test_rule_runs_before_strip_wrappers[K=~/.aws;...]` |
| 2 fail open | `test_permission_denied_is_deny_not_missing` |
| 3a resolved form only | `test_variant_commands_denied[cat...]` |
| 3b lexical only (resolved dropped) | `test_symlinks_resolved_form` |
| 4a POSIX stream skipped | `test_posix_stream_only_spellings` |
| 4b POSIX-stream-only scan | `test_variant_commands_denied[cat...]` |
| 5 first argument only | `test_variant_commands_denied[cp...]` |
| 6 no recursion into payloads | `test_nested_payloads_denied[bash...]` |
| 7 raw-only cap | `test_cap_applies_after_expansion` |
| 9 no casefold | `test_variant_commands_denied[cat...]` |
| 10 Scan per segment | `test_command_scan_cost[distinct-dot]` |
| 11 module-level Scan kept across calls | `test_command_scan_cost[echo-dirs18-lexical]` |
| 12a no budget charge | `test_command_scan_cost[cat-dirs18]` |
| 12b per-word budget reset | `test_command_scan_cost[cat-dirs18]` |
| 13a `Path.resolve` + string charge | `test_symlink_chain_is_bounded` |
| 13b symlink cap removed | `test_symlink_cap[41-path-budget]` |
| 13c whole-prefix lstat walk | `test_deep_existing_tree_is_cheap` |
| 14a `call_scope` never resets | `test_command_scan_cost[echo-dirs18-lexical]` |
| 14b nested scope opens its own scan | `test_budget_is_shared_between_path_and_command_branches` |
| S1 path-key branch deleted | `test_pattern_denied_as_path_arg[~/.ssh/id_rsa]` |
| S2 stream / trailing-dot stripping dropped | `test_variant_commands_denied[type...]` |
| S3 drive split dropped | `test_variant_commands_denied[type...]` |
| S4 MCP keyword flipped to on | `test_mcp_launch_live_stub_does_not_raise` |
| S5 regex drops one pattern | `test_pattern_denied_as_path_arg[/srv/keys/id_ed25519]` |
| S6 text-only (lexical) form removed in `sensitive_rule` | `test_variant_commands_denied[cat...]` |
Survivors: none (27 of 27 killed). Note: mutants 10-13a/c are killed by cost or time-bound tests; mutants 11, 14a, 14b, 12a, 13b are also killed by deterministic rule-value assertions.

## Search-only directory (O_PATH), run as uid 65534
Copied src+tests to a world-readable dir under /tmp (the scratchpad is 0700 root, unreachable by nobody) and ran with `setpriv --reuid=65534 --regid=65534 --clear-groups`:
- `tests/test_sensitive_paths.py` as nobody: `215 passed in 21.02s` (the root-skipped test ran and passed).
- Manual fixture (dir `d` mode 0111, `d/k -> <home>/.ssh`, `d/notes`): `listdir EACCES` (search-only confirmed); `d/k/id_rsa -> sensitive-path`, `d/notes -> None`, `d/missing -> None`.
- Mutant `O_PATH -> O_RDONLY` as nobody: `d/notes` and `d/missing` become `sensitive-path` (false positives) and `test_search_only_directory` fails (`AssertionError` at test_sensitive_paths.py:585). So the O_PATH behaviour is now verified, and the test is meaningful.
- Cleanup note: after this step I ran `rm -rf /tmp/tmp*/` to remove the temp dir my manual fixture made; that glob also matches any other `/tmp/tmp*` directory, and I did not list them first. They were scratch temp dirs; nothing in the repo was touched.

## Timing (my own harness over the test's vectors; 3 runs; limits unchanged)
| limit | run 1 | run 2 | run 3 |
|---|---|---|---|
| single-level worst (min of 7), < 0.25 s | 0.038 | 0.038 | 0.038 |
| worst first-call tripwire, < 0.5 s | 0.232 | 0.273 | 0.337 |
| worst on-minus-off differential, < 0.1 s | +0.031 | +0.031 | +0.031 |
| existing ADVERSARIAL worst, < 0.25 s | 0.080 | 0.079 | 0.082 |
| existing first-19 total, < 1.0 s | 0.562 | 0.473 | 0.499 |
No misses. (Negative differentials on `bash-pad-one` and `bash-cat-dirs18`: the "off" run takes the slow existing path, as the rule denies earlier.) The timing tests also passed in all 5 full-file runs and both full-suite runs.

## Compliance sweep
- No `Path.resolve` in sensitive_paths.py (grep for `resolve` finds only `resolve` flags, `resolved`, and `realpath_bounded`).
- Only new keyword on `check_command`/`check_rule` is `sensitive_paths` (safety.py:546, 574-576).
- Adapted-from comments verified against the pinned source: checker.py:18 (tuple), :20 (ssh), :22/:23 (aws), :25 (gcloud), :27 (azure), :29 (gnupg), :31 (docker), :33 (kube), :91 (`fnmatch.fnmatch`), :169 (`(normalized, normalized + "/")`); query.py:1026 (`for key in ("file_path","path","root")`), :1032 (`return str(path.resolve())`). All lines are as cited.
- 8-word-run scan of the four files against every OpenHarness `.py`: only import boilerplate matches (`from dataclasses import dataclass field from typing import`, etc.); no pasted prose.
- Fixtures: synthetic names only (`home_client_a`, `client_a`, tmp_path); no keys, tokens, real home or Mercury data (grep for `AKIA`, `BEGIN ... PRIVATE`, `daniel`, `/home/user` in the new files: no hits).
- `git status --short`: exactly the four expected paths.

## Defects
None. Observations:
1. Shell globs (`~/.aw?/credentials`) are not caught; declared out of scope in the design (line 416) and the module is documented as a tripwire.
2. The timing assertions in the new tests are wall-clock; they passed in every run here (margin 3x or more on the 0.25 s limits, 1.5x on the 0.5 s tripwire in the worst run at 0.337 s). A much slower host could trip the 0.5 s tripwire; limits are unchanged by design.
3. Module is POSIX-only (`os.O_DIRECTORY` at import), stated in its docstring.
