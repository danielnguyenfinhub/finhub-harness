RESULT: FAIL

# boundary-qa: C9 (verification gates as data, argv only, no shell)

One real-process bypass of QA-bar item (a): a policy-accepted non-shell gate runs a shell, reproduced through the real CLI with strace proof. Everything else in the bar is green. Four survivors in the fresh mutant batch (none a bypass; Q26 and Q42 are test gaps in the same /proc and metacharacter rules, see Defects).

Scope audited: src byte-identical to the audited design (see Gate 1). Nothing in `src/` or `tests/` was edited, nothing committed. `git status --short` at the end: ` M src/master_finhub/sandbox/stream.py`, `?? src/master_finhub/evals/gates.py`, `?? tests/test_gates.py` (dist/ is gitignored).

## Defects

### D1 (FAIL, QA bar (a)): `..` after a symlink to /proc/self/cwd bypasses the shell refusal
File: `src/master_finhub/evals/gates.py`, `_link_into_opaque` (lines 245-258) and `_opaque` (line 241) take `os.path.normpath(path)` BEFORE walking components, and `_checked_real` (line 263) then calls `os.path.realpath(path)` on the UNNORMALISED path.

Expected (design N37/N41/N43, QA check (ii) "every runner-versus-child resolution mismatch ... a symlink in the gate folder into /proc or /dev ... with the runner cwd != the gate cwd ... `..` forms"): policy error, exit 2, nothing spawned.
Actual: the gate is accepted, `/bin/sh` runs the gate's `-c` text, status `pass`, rc 0.

Mechanism: gate folder `G` holds `lnk -> /proc/self/cwd`; the parent of `G` holds `mysh -> /bin/sh`; argv[0] is `lnk/../mysh`; the runner's cwd `R` is not `G`.
- Runner side: `normpath("G/lnk/../mysh")` collapses `lnk/..` lexically, so the link component is never examined (no link seen, no /proc prefix); then `realpath` expands `lnk -> /proc/self/cwd` to the RUNNER's cwd `R`, `..` goes to parent(R), and `parent(R)/mysh` does not exist (or is harmless). The basename is `mysh`, not a shell name. Accepted.
- Child side: Popen does chdir(G) first, so `lnk` is the child's cwd = `G`, `..` is parent(G), and `parent(G)/mysh -> /bin/sh` is exec'd. A shell runs.
This is the same class as the judge's ATK5 (runner `/proc/self` != the child's), reached through a path the 17 + prefix tests do not cover.

Repro (real CLI, scratch dir under the scratchpad; script `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/q9x/p3b.py`, driver `drv.py` in the same folder). Layout: `D/sub/lnk -> /proc/self/cwd`, `D/mysh -> /bin/sh`, `D/a/b/` empty; runner cwd `D/a/b`, `--root D`, gate `{"id":"g","argv":["lnk/../mysh","-c","touch D/MARK"],"cwd":"sub"}`, no `--allow-shell`.

```
BAD A_relative_dotdot: rc=0 exec=3 marker=True [('g', 'pass', '')]
    execs: ['"lnk/../mysh", ["lnk/../mysh", "-c", "touch /tmp/claude-0/-home-user/c"...], ...', '"/usr/bin/touch", ["touch", "/tmp/claude-0/-home-user/cc98ae1"...], ...']
BAD B_abs_dotdot (@D@/sub/lnk/../mysh): rc=0 exec=3 marker=True [('g', 'pass', '')]
BAD C_dot_dotdot (./lnk/../mysh): rc=0 exec=3 marker=True [('g', 'pass', '')]
BAD D_string_form ("lnk/../mysh -c x"): rc=1 exec=2 marker=False [('g', 'fail', 'exit code 127')]   <- the shell ran ("x: not found")
BAD E_PATH_entry_lnk/.. (PATH=lnk/..:/usr/bin:/bin, argv0 "mysh"): rc=0 exec=3 marker=True [('g', 'pass', '')]
BAD F_thread-self (lnk -> /proc/thread-self/cwd): rc=0 exec=3 marker=True [('g', 'pass', '')]
BAD G_(lnk -> /proc/self/cwd/.): rc=1 exec=2 marker=False [('g', 'fail', 'exit code 2')]            <- shell ran, my touch text was mangled by the dir name
```
(`exec=N` = successful execve calls under `strace -f`; a refused gate shows `exec=1`, the runner's own python. "BAD" is my driver's label for "not refused".) The second execve is the dash that was reached through the link, the third is the `touch` it ran; MARK was created in A, B, C, E, F.

Same layout, runner cwd == gate cwd, is refused (the resolution agrees), and `lnk/mysh` (no `..`) is refused by the component walk, so the hole is exactly "a `..` that follows a symlink component", in argv[0], an absolute argv[0] and a PATH entry.

Suggested kill test (for the builder/architect, not applied): the layout above through `plan_gate` with `monkeypatch.chdir(D/a/b)`, `argv=("lnk/../mysh","-c","x")`, gate cwd `sub`, must return a policy-error string; plus the PATH variant `PATH="lnk/..:/usr/bin"`, `argv=("mysh",)`. Suggested direction: walk the components WITHOUT `normpath`, resolving `..` physically after each link (or refuse any `..` that comes after a symlink component, or refuse any argv[0]/PATH entry that contains a `..` component once a link on the way points into /proc or /dev).

### D2 (follow-up, survivor Q42): the metacharacter scan can skip the first character
Mutant `for ch in text` -> `for ch in text[1:]` survives. A string command that STARTS with a metacharacter (`;true`, `|x`, `$HOME/x`) is accepted instead of refused. It is inert (no shell: the tokens become an argv whose first word does not exist), so not a bypass. Kill test: `plan_gate(Gate(command=";true"...))` and one per metacharacter at index 0 must be policy errors.

### D3 (follow-up, survivor Q26): `//proc` and `//dev` lexical forms
Mutant `p = "/" + os.path.normpath(path).lstrip("/")` -> `p = os.path.normpath(path)` survives (POSIX normpath keeps exactly two leading slashes). I ran the mutated tree through the real CLI with `//proc/self/cwd/mysh`, `//dev/stdin`, `//proc/self/exe`: still refused (rc 2, exec=1), because the symlink walk catches `/proc/self`, `/proc/thread-self`, `/dev/fd`, `/dev/stdin` anyway. What the mutant changes: `//dev/null` and `//proc/<other pid>/...` are no longer refused (outcome would be an `error` status, no mismatch). So no bypass, a test gap. Kill test: `plan_gate(argv=("//dev/null",))` must be a policy error.

### D4 (follow-up, survivor Q25): over-refusal
`p.startswith(root + "/")` -> `p.startswith(root)` survives; it would refuse `/development/bin/tool`, `/devices/x`. Kill test: `plan_gate(argv=("/developer/tool",))` must NOT be the /proc-or-/dev refusal.

### D5 (equivalent, survivor Q90): `raw.strip()` in the shell argv. `sh -c` sees the same command modulo outer whitespace. Equivalent.

### Observations (set aside, each with the evidence line)
- `sudo -s touch X` under a non-shell gate ran (`sudo` -> `/bin/bash -c`, exec=3): in the KNOWN list (`sudo -s`), not a FAIL. Note `sudo` is in WRAPPERS but `-s` is not a shell name.
- Time-out with a `setsid` grandchild: gate status `timeout`, rc 1, but `sleep` in its own session survived the group kill (pid seen after the run; I killed it). Never a pass; consistent with process-group kill; not on the KNOWN list explicitly, worth a Does-not-cover line. The run took 6.0 s for a 1 s timeout (the 5 s pipe-join of `stream.py`).
- SIGINT with `trap '' INT` is ignored by the runner (inherited SIG_IGN, Python does not install a handler): the gate keeps running; SIGTERM and SIGHUP are still handled under every trap (rc 143, 129, no orphan). Matches the design (INT is not in HANDLED_SIGNALS).
- `scrubbed_env` is by name only (`KEY|PASSWORD|SECRET|TOKEN`): a secret in a variable named `PLAINNAME` reaches the child; the report tail redaction replaced a `sk-...` shape. This is the shared C1-era `stream.py` rule, unchanged.
- black prints "Python 3.11 cannot parse code formatted for Python 3.15" (pre-existing target-version warning), rc 0.

## Boundary table
| boundary | side A shape | side B shape | match |
|---|---|---|---|
| gate file JSON -> `load_gate_file` -> `Gate` | keys `schema_version,gates`; gate keys `id,command,argv,shell,timeout_s,cwd` (design N2) | `ROOT_KEYS`, `GATE_KEYS`, `_parse_gate` (gates.py:171-205); 46 loader probes all exit 2 / 1 accepted | match |
| `Gate` -> `plan_gate` -> `Plan` | policy errors never spawn (N13) | `run_gates` plans all first (gates.py:437-451); mixed file with refused gate FIRST/MIDDLE/LAST: exec=1, `not-run` for the rest | match |
| argv[0] as the runner resolves it -> argv[0] as the child execs it | design N41/N43: resolved from the GATE's cwd, /proc and /dev refused | `_resolve`/`_checked_real` normalise lexically then realpath in the RUNNER's namespace (gates.py:241-300) | MISMATCH (D1) |
| `plan_gate` -> `stream_process(argv, env, cwd, timeout)` | N14 spawn arguments | gates.py:413 passes `env=scrubbed_env(), timeout_s, cwd=str(plan.cwd)`; stream.py:137 `cwd=cwd` (+4 lines) | match |
| `stream_process` other callers | `docker_engine.py:132` passes no cwd | default `None` = old behaviour; test_stream/test_docker_engine/test_mcp_client 37 passed, 1 skipped | match |
| `GateResult` -> JSON report -> `exit_code` | N20 keys, N4 exit codes 0/1/2 | key order observed `id,status,exit_code,duration_s,stdout_tail,stderr_tail,truncated,message`; no command/cwd/env in output | match |
| C4 runner contract | N1: `runner.py` byte-identical | sha256 c34f998b... before and after; exit codes 0/1/2/3 and `--baseline` output identical (durations stripped) | match |

## Gate
All commands run from `/home/user/finhub-harness` with `.venv/bin/python` (3.11.15) unless stated. Scratch under `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/q9x/`.

| # | command | rc | output observed |
|---|---|---|---|
| 1a | `git status --short` | 0 | ` M src/master_finhub/sandbox/stream.py` / `?? src/master_finhub/evals/gates.py` / `?? tests/test_gates.py` |
| 1b | `sha256sum` + `wc -l` of the 4 files | 0 | gates.py `c46273479692459b86f8dede4a9188308266dbf64482fe9e33599f82d20283bf` 542 lines; stream.py `180e44ed671760fc402b50d741f98a8f92582954f893025cdf229e72b5200d93`; tests/test_gates.py `7e6c63a2b4a76d27ab5fe6064d9c8a040c42c59c936daa2ccd4a3ad139685aca` 2190 lines; runner.py `c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6` |
| 1c | `sha256sum _workspace/02_strategy-architect_C9.patch` | 0 | `a383cc8a28a00fd4ac806e27ebed290534262e5789c3aec829c2b55960a156d4` |
| 1d | `git archive 588dd9b \| tar -x -C q9x/repro` (includes .gitignore, skills/, .claude/), `git apply --check` + `git apply` of the patch, `cmp` each of the 3 files with the repo | 0 | `applied`, `same src/master_finhub/evals/gates.py`, `same src/master_finhub/sandbox/stream.py`, `same tests/test_gates.py`; `diff -rq` repro vs repo (excluding .git .venv dist caches references _workspace*) lists only untracked/ignored local files (`.claude/proven-config*`, `.claude-flow`, `_workspace_*`) |
| 1e | `git diff --numstat src/master_finhub/sandbox/stream.py` | 0 | `4	0	src/master_finhub/sandbox/stream.py` |
| 2a | `pytest -q tests/test_gates.py`, 3.11 / 3.12 / 3.13 | 0 | `543 passed in 13.95s` / `543 passed in 14.37s` / `543 passed in 14.60s` |
| 2b | same with `python -W error`, 3.11 / 3.12 / 3.13 | 0 | `543 passed in 14.38s` / `14.39s` / `14.55s` |
| 2c | `bash -c "trap '' INT; ..."` | 0 | `543 passed in 13.91s` |
| 2d | `bash -c "trap '' INT HUP; ..."` | 0 | `543 passed in 14.44s` |
| 2e | `setsid --wait nohup ... </dev/null` | 0 | `543 passed in 13.94s` |
| 2f | stdin closed (`<&-`) | 0 | `543 passed in 14.06s` |
| 2g | `env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/root` | 0 | `543 passed in 13.55s` |
| 2h | as user nobody: tree copied to `/tmp/c9qa_nobody` (chmod a+rX), `setpriv --reuid=nobody --regid=nogroup --clear-groups env HOME=... TMPDIR=... PYTHONPATH=/tmp/c9qa_nobody/src`, `id -u` printed 65534, module imported from the copy | 0 | `543 passed in 14.31s` (copy removed afterwards) |
| 2i | as root (uid 0): every run above | 0 | see 2a-2g |
| 2j | `env -u PYTHONUNBUFFERED pytest -q`, 3.11, foreground | 0 | `1947 passed, 10 skipped in 116.74s (0:01:56)` |
| 2k | `PYTHONUNBUFFERED=1 pytest -q`, 3.11, foreground, after 2j | 0 | `1947 passed, 10 skipped in 116.36s (0:01:56)` |
| 2l | `pytest -q`, 3.12, then 3.13 (extra) | 0 | `1947 passed, 10 skipped in 115.85s (0:01:55)`; 3.13: `1947 passed, 10 skipped in 122.68s (0:02:02)`. test_adversarial_inputs_are_linear did not fire |
| 2m | `ruff check src tests` | 0 | `All checks passed!` |
| 2n | `black --check src tests` | 0 | `71 files would be left unchanged.` (plus the pre-existing py3.15 target warning) |
| 2o | `mypy --strict src` | 0 | `Success: no issues found in 40 source files` |
| 2p | `bash scripts/check-harness-refs.sh` | 0 | last lines `PASS six agent files`, `PASS CLAUDE.md says six-agent`, `PASS no Hangul in agents+triage`, `PASS packager exit 0` |
| 2q | `bash scripts/package-plugin.sh` | 0 | `lint_harness: 0 error(s), 0 warning(s)`; `dist/finhub-harness.plugin  104285 bytes` (dist/ gitignored) |
| 2r | `LC_ALL=C.UTF-8 grep -nP '\p{Hangul}'` over the 3 files | 1 | no output |
| 2s | secrets grep (AKIA, sk-, ghp_, PRIVATE KEY, xox, password=) over the 3 files | 1 | no output |
| 2t | `sed -n 4p gates.py`; open service.py lines 136, 155, 2094 | 0 | `Policy adapted (MIT, own code) from references/openharness/src/openharness/autopilot/service.py:155`; :136 `_SHELL_METACHARS = frozenset(";&|\`$<>\n\r")`, :155 `def _parse_verification_entry`, :2094 `def _run_verification_steps` |
| 2u | 8-word verbatim scan (words only, vs service.py) of gates.py, test_gates.py, stream.py | 0 | gates.py 1 hit, test_gates.py 1 hit, stream.py 0; the hit is `from pathlib import Path from typing import Any` (the allowed import line) |
| 3 | Authority List greps (below) | 0 | all as stated |
| 4 | real-CLI probes | see Probes | one failure class, D1 |
| 5 | mutant batch | see Mutants | 90 mutants, 86 killed, 4 survived (D2-D5) |
| 6 | `git status --short` at the end | 0 | same three lines as 1a |

### Authority List re-run (check 3)
| row | command | result |
|---|---|---|
| N1 | `grep -c gates src/master_finhub/evals/runner.py`; `git diff --stat` | `0`; only stream.py, `4 ++++` |
| N5 | `grep -n _stdout_lost gates.py \| wc -l` | 4 |
| N11 | `grep -n "guard_tool_call(" gates.py \| wc -l` | 1 |
| N14 | `grep -c "shell=True" gates.py`; `grep -nE "import subprocess\|os\.system\|os\.popen"`; `grep -n "stream_process("` | `0`; rc 1; 1 call (line 413) |
| N23 | `grep -n O_PATH src/master_finhub/tools/sensitive_paths.py \| wc -l` | 3 |
| N25 | `grep -ciE "slippage\|borrow\|survivorship\|pnl\|fees?" gates.py` | 0 |
| N31 | `grep -nE "^import re\|^from re " gates.py` | rc 1 |
| N32 | `git diff --numstat` stream.py; `grep -n "cwd=cwd" stream.py`; `tests/test_stream.py` diff | `4 0`; line 137; unmodified; `tests/test_stream.py tests/test_evals_baseline.py`: 118 passed |
| N33 | `grep -n "references/openharness" gates.py \| wc -l` | 1 |
| N39 | `grep -c "NOT detected"`; `grep -c "not a sandbox"`; quoted-false-claim grep in the design | 1; 2; 2 lines |
| N40 | `grep -n "default_int_handler" tests/test_gates.py \| wc -l` | 1 |
| N20 (count) | `pytest --collect-only -q tests/test_gates.py \| tail -1` | `543 tests collected` |
| tests named in the list | each `test_...` name from the Authority List grepped as `def name` in tests/ | none missing except name prefixes and file names (`test_argv_item_`, `test_cwd_`, `test_shell_gate_`, `test_total_budget_`, `test_cli_root_flag_`, which are prefixes) |

## Probes (check 4; real CLI `python -m master_finhub.evals.gates`, strace -f -e trace=execve to count spawns, a marker file to detect side effects)
Driver `drv.py`; each case in a fresh scratch dir, expected for every refusal: rc 2, `exec=1` (only the runner's own python), no marker. Outputs are in the run logs I printed; summary by group (full per-case lines were shown during the run, quoted here where they matter):

(i) shell forms, 49 cases: `sh/bash/dash/zsh/ksh/SH/Bash.exe` in list and string form, `/bin/sh`, `/usr/bin/bash`, `/bin/dash`, `/bin//sh`, `/bin/./sh`, `/usr/../bin/sh`, `/bin/../bin/bash`, symlink named `anyname`, `true`, `python3`, `q` (chain of two) to sh/bash by absolute, `./` and PATH, chains of 2 and 20 links, a 50-link chain (refused as >40 hops) and a loop and a self loop (refused), `env sh`, `env -i sh`, `env A=b sh`, `env /bin/sh`, `busybox sh` (no busybox installed, refused by the wrapper rule), `xargs sh -c`, `find -exec sh`/`/bin/bash`, `su -c`, `su root -c`, `watch`, `exec -a sh`, `nohup sh`, `timeout 5 sh`, `sh` with `--allow-shell` still refused. All rc 2, exec=1, no marker, EXCEPT `sudo -s touch X` (rc 1, exec=3: the KNOWN limit). Not tested because not installed: zsh, ksh, busybox binaries (the name rule was exercised; no real binary behind them).

(ii) /proc and /dev family, with runner cwd != gate cwd (gate cwd `sub`): `/proc/self/cwd/mysh`, `/proc/thread-self/cwd/mysh`, `/proc/self/cwd/./mysh`, `/proc/self/cwd//mysh`, `/proc/self/cwd/../sub/mysh`, `/proc/self/root/bin/sh`, `/proc/self/root/<D>/sub/mysh`, `/proc/self/exe`, `/proc/self/fd/0..3`, `/dev/fd/0`, `/dev/fd/3`, `/dev/stdin`, `/dev/stdout`, `/dev/null`, `/dev/shm/x`, `/dev`, `/proc`, `/proc//self/...`, `//proc/self/...`, `/./proc/...`, `/proc/./self/...`, `/proc/self/../self/...`, trailing slash, `/proc/1/cwd`, `/proc/1/root/bin/sh`, `/dev/./fd/0`, `/dev//fd/0`, string forms, runner inside `sub` with `--root` the parent, gate-folder links to `/proc/self/cwd/mysh`, `/dev/stdin`, `/proc/self/exe`, a link whose target climbs 20 `../` to `/proc/self/exe` and `/dev/stdin`, a dir link `pdir -> /proc/self/cwd`, `dd -> /dev` then `dd/fd/0`, PATH entries `/proc/self/cwd`, `/proc/thread-self/cwd`, `/dev`, `/proc/self/root/bin`, `/proc/self/cwd/.`, `/proc//self/cwd`, relative entry `bin`, empty entry, `.` entry, trailing empty entry, `..` entry, symlinked gate cwd, `sub/../sub//.` cwd, `--root` elsewhere, the runner's own pid (`/proc/<runner pid>/cwd/mysh` via a launcher that execs the runner, pid printed in the gate file), `/proc/self/fd/N`, `/dev/fd/N`, `/proc/<pid>/fd/N` with a real inherited fd to `/bin/sh`: all rc 2 with the /proc-or-/dev message (or the shell message for the plain relative-link and PATH cases), exec=1, no marker. NOT refused as policy (rc 1 `error`, ENOENT, nothing runs): `/PROC/self/cwd/mysh`, `/Proc/...`, a zero-width-space `/proc​/self/...`, `sh\n`, `ѕh` (Cyrillic), fullwidth `sh`, ` sh`, `sh.` (they do not name anything on Linux). NUL in argv[0]: rc 2. The only miss: D1 above (`..` after a link to /proc).

(iii) shell:true, 17 cases: refused without `--allow-shell` (rc 2, exec=1); with it `/bin/sh -c` ran (exec=3; the `touch` target path had spaces in my scratch dir name so rc/marker are not meaningful, the execve trace shows `/bin/sh -c ...` then the command); `"true"`, `1`, `"True"`, `"yes"`, `[]`, `null`, `"false"`, `0` all `shell must be true or false` rc 2; shell with argv rc 2; duplicate `shell` key rc 2; `Shell`/`SHELL` unknown key rc 2; env `ALLOW_SHELL`, `FINHUB_ALLOW_SHELL`, `MASTER_FINHUB_ALLOW_SHELL=1` did not enable it; `--allow-shell` does not rescue a metacharacter string in a non-shell gate.

(iv) metacharacters, 21 + 9 + 12 cases: `; & | < > backtick $( $ \n \r`, `$(id)`, `x && y`, `x > f`, `${IFS}`, `cat <<<hi`, here-string: all refused (rc 2, exec=1). Unbalanced quotes, trailing backslash: refused. `A=b true`: refused. `~/x`: inert (ENOENT). `echo *`, `echo ?`: inert (echo printed `*`, `?`). NUL: refused. Same bytes in `argv`: inert (`echo ;`, `&&`, `|`, `>`, backtick, `$(id)`, `*`, `~`, `${IFS}`, `a b`, newline all pass as plain arguments). `A=b` / `-x` / empty / `[]` as argv[0]: refused.

(v) spawn, 40 cases: cwd `..` outside, `/`, `/etc`, symlink escape, a file, missing, empty string, `/proc/self`, `.ssh` (sensitive path): all policy errors rc 2, exec=1. cwd really `sub`. Env: `MY_API_KEY`, `DB_PASSWORD`, `GH_TOKEN`, `X_SECRET`, `myTokenLower` never reached the child (child saw `[]` for any value containing SECRET), `OKVAR` did; a secret-shaped value in a plain-named variable and printed by the child came back `[REDACTED:openai-key]` / `[REDACTED:github-token]`; neither value nor command nor cwd appears in the report (keys listed above). stdin: child read `''`. Status: exit 3 -> `fail` rc 1; `kill -9` self -> `fail`, exit_code -9, `killed by signal 9`; SIGSEGV -> `killed by signal 11`; ENOENT -> `error`; non-executable file -> `error` `not executable or not permitted`; no-shebang script -> `error` `could not start (OSError)`; directory as argv[0] (`./sub`, `/tmp`) -> `error`; PermissionError on the gate cwd as user nobody (`chmod 000` folder) -> `error` `not executable or not permitted`, the second gate still ran (`pass`), rc 1; prints nothing -> `pass`; prints `FAILED 3 tests` and exits 0 -> `pass` (stated limit); `os._exit(256)` -> exit 0 -> `pass` (kernel wraps to 0). Output: 5 MB -> `pass`, tail 80..4000 chars with `truncated: true`; binary 12,800 bytes ok; non-UTF-8 bytes decoded with replacement; a secret placed past the 64 KB window: `truncated: true` (fragment limit is the KNOWN one).
Timeouts (no strace, process listing after): plain sleep 1 s -> `timeout` in 1.002 s; grandchild in the group -> `timeout`, no orphan; double fork in the group -> no orphan; SIGTERM-ignoring gate -> `timeout` 1.1 s; daemonised grandchild holding the pipe with the parent already exited 0 -> `timeout` 2.002 s, no orphan; `setsid` grandchild -> `timeout` (6.003 s), the escaped `sleep` survived (see Observations). Bounds: `timeout_s` 0, -1, 1801, true, NaN, Infinity, 1e999, "5" rc 2; 1800 accepted; 50 gates run (exec=51), 51 gates rc 2; no fail-fast (`false,true,false` ran all three, rc 1).

(vi) pre-validation: file `[touch MARK, true, sh -c x]` (refused LAST): rc 2, exec=1, statuses `not-run, not-run, policy-error`, no MARK; refused FIRST, middle (cwd `/etc`), and `shell:true` without the flag LAST: same.

(vii) loader, 46 cases, rc 2 each: empty list, unknown root/gate key, duplicate ids, NaN, BOM, duplicate JSON keys, schema_version 2 / 1.0 / true / missing, root list/str, gates not list, gate not object, id `../x` / empty / `é` / 65 chars, command+argv, neither, argv with an int, argv a string, command a list, cwd int, lone surrogate, 5,000-digit int, 100,000-deep list, 50,000-deep object, deep value inside a gate, empty file, whitespace, truncated, trailing garbage, 300 KB, 262,145 bytes, non-UTF-8, UTF-16, FIFO, directory, missing, `/dev/null`, `/dev/zero`, `/proc/self/environ`, bad CLI args (rc 2 each), `--root` missing/is a file. Accepted correctly: duplicate ids differing only by case, a file of exactly 262,144 bytes. Deep nesting and the huge int also through the CLI under 3.12 and 3.13: rc 2 each (`not UTF-8 JSON (duplicate keys and very deep nesting are refused)` or `larger than 262144 bytes`).

(viii) signals (a gate that spawns a grandchild `sleep`, signal sent after 2 s, normal and trap'd dispositions via `bash -c "trap ... ; exec python -m ..."`):
```
SIGTERM  pre=''               rc=143 report=no gate-sleep before=1 after=0
SIGTERM  pre="trap '' INT;"   rc=143 report=no gate-sleep before=1 after=0
SIGTERM  pre="trap '' INT HUP;" rc=143 report=no gate-sleep before=1 after=0
SIGTERM  pre="trap '' TERM;"  rc=143 report=no gate-sleep before=1 after=0
SIGINT   pre=''               rc=-2 report=no gate-sleep before=1 after=0
SIGINT   pre="trap '' INT;"   rc=-9 report=no gate-sleep before=1 after=1   (runner did not exit within 20 s; I killed it; SIGINT ignored by inheritance)
SIGINT   pre="trap '' INT HUP;" rc=-9 report=no gate-sleep before=1 after=1  (same)
SIGINT   pre="trap '' TERM;"  rc=-2 report=no gate-sleep before=1 after=0
SIGHUP   pre=''               rc=129 report=no gate-sleep before=1 after=0
SIGHUP   pre="trap '' INT;"   rc=129 ...  after=0
SIGHUP   pre="trap '' INT HUP;" rc=129 ... after=0
SIGHUP   pre="trap '' TERM;"  rc=129 ... after=0
```
(ix) stream.py: callers are `docker_engine.py:132` (no cwd), `tools/mcp/client.py` (imports only `scrubbed_env`), `gates.py:413`; `pytest tests/test_stream.py tests/test_docker_engine.py tests/test_mcp_client.py` -> `37 passed, 1 skipped in 18.45s`; full suite green (2j-2l).

(x) C4 contract: `runner.py` sha256 c34f998b... in the repo and in a clean `git archive 588dd9b` copy. Before (clean src) vs after (patched src): `echo_pass.json` rc 0 / 0, `echo_fail.json` rc 1 / 1, both rc 1 / 1, missing file rc 2 / 2, `--baseline` of a prior echo_pass report rc 0 / 0, regression via `--baseline` with echo_fail rc 3 / 3 (I did not reach exit 3 with the plain runner on its own; exit 3 is the baseline regression). JSON outputs identical once duration fields are filtered (`diff` printed `plain: identical`, `baseline: identical`).

## Mutants (check 5: one fresh batch)
Runner `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/q9x/mut/qamut.py` (own list Q01-Q90, own code): fresh process per mutant, tar copy of the patched tree including `.gitignore`, `skills/`, `.claude/`, `scripts/`, `python -B -m pytest -x tests/test_gates.py`, module path checked to be the copy, every edit applied with an exact occurrence count and a non-empty unified diff verified (0 errors); 4 parallel workers, then Q48, Q53, Q63 re-run serially alone (timing-sensitive killers): killed again. Q84 (gates passed through a `set`, order depends on the hash seed) run under PYTHONHASHSEED 0-39: killed under every seed. Control (unmutated tree) 543 passed.

```
TOTAL 90 killed 86 survived ['Q25', 'Q26', 'Q42', 'Q90'] errors [] 207
```
Classes covered: shell-name list and basename/.exe/lower rule (Q01-Q09), su/watch (Q10, Q11), PATH lookup / first hit / X_OK / isfile / relative base / runner-vs-gate cwd (Q12-Q16), realpath and the final opaque check (Q17-Q19), link walk, loop, hop limit, last-component, target join, recursion (Q20-Q24), /proc and /dev prefix, normalisation, roots (Q25-Q28), opaque exception swallowed and PATH entry check (Q29, Q30), wrapper list and later-argument rule (Q31-Q36), two-key shell rule (Q37-Q39), metacharacter set, scan, shlex (Q40-Q45), spawn env/cwd/timeout (Q46-Q48), status mapping (Q49-Q51, Q87), pre-validation (Q52), total budget (Q53), file schema checks (Q54-Q65, Q71-Q74), exit codes (Q66, Q86, Q88), signal handlers (Q67-Q69), stream.py cwd keyword (Q70), cwd fence and guard (Q75-Q79), tail redaction/cut/truncated (Q80-Q82), shell refusal resolved from runner cwd (Q83), ordering (Q84, Q85), shell path (Q89, Q90).

Survivors, each classified:
- Q25 `startswith(root + "/")` -> `startswith(root)`: follow-up (over-refusal), kill test in D4.
- Q26 `//proc` lexical form: follow-up (test gap, not a bypass: I ran the mutant through the real CLI, still refused for `//proc/self/...` via the link walk), kill test in D3.
- Q42 first character of a command string skipped by the metacharacter scan: follow-up (inert), kill test in D2.
- Q90 `raw.strip()` in the shell argv: equivalent.
No survivor is a false pass or a bypass. The real bypass (D1) is in the unmutated code and no mutant of mine models it, which means the 543 tests and 90 mutants all miss the lexical-`..`-over-a-link case.

Overlap with the architect's and judge's runners: I compared each mutant's old and new text against `_C9_mutate.py` and the three judge runners (substring match on both texts): 52 of the 90 matched nothing; 38 (Q01, Q12, Q14, Q16, Q17, Q19, Q22, Q23, Q24, Q27, Q28, Q33, Q34, Q36, Q43, Q44, Q46, Q48, Q52-Q58, Q60, Q62, Q63, Q65-Q69, Q79, Q80, Q82, Q83, Q89) match on a short string and may repeat an existing mutant in spirit. The four survivors Q25, Q26, Q42, Q90 are among the 52 that matched nothing. So the fresh count is at least 52 (above the bar's 40).

## Deviations and surprises
- Several of my probe cases were labelled BAD by my own driver for reasons unrelated to the code: scratch directory names containing spaces broke the `touch` target in four positive shell-gate cases, and `expect_rc=None` cases print BAD by construction (`/PROC/...`, `sh\n`, Cyrillic `sh`, fullwidth `sh`, ` sh`, `sh.`, `//` trailing slash, `str ~/x`, `echo *`). I re-ran or read each; none is a defect. The first run of the `setsid` timeout under `strace -f` hung because strace waits for the escaped process; I killed it and re-ran those cases without strace.
- One `pkill -f` I used matched my own shell command and killed my shell; no repo effect.
- Not installed on this host: zsh, ksh, busybox; those names were tested by the name rule only.
- I created and removed `/tmp/c9qa_nobody` and `/tmp/c9qa_names.txt`. Scratch under the scratchpad (`q9x/`) is left in place. The repo `git status` is unchanged apart from the three C9 files.

## Next step
Return C9 to the architect/builder: fix `_link_into_opaque`/`_checked_real` so a `..` that follows a symlink component cannot hide the link (and the same for PATH entries), add the D1 repro and the D2-D4 kill tests, then re-run QA. The bar allows no shell-running bypass, so C9 cannot merge as it stands.
