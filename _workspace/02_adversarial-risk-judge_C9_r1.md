TOTALS: UPHELD 62 / REJECTED 3 / UNVERIFIED 0 — round 1/3

# Adversarial verdict — C9 (verification gates as data: argv only, no shell), revision 1

- Audited file: _workspace/02_strategy-architect_C9.md (rev 1) with 02_strategy-architect_C9.patch (sha256 6c3d0d94e7752a059d692b3c476fc0c1e5c2fd46037a825283bac3d60e918249, matches); the code blocks A and C in the design are byte-identical to the patch result.
- Judged tree: tar copy of the working tree at HEAD 588dd9b (with .gitignore, skills/, .claude/, scripts/; references/ symlinked read-only) plus `git apply` of the patch. Scratch: scratchpad/j9/pat. No file in the repo or the architect's files was edited.
- Extra round authorised by Daniel: none.
- Rows REJECTED here are three attack rows added by the judge (ATK1-ATK3). No A row and no architect N row is REJECTED on its own text; ATK1 falsifies Decision 3 and the QA bar (a), ATK2 and ATK3 are environment-dependent tests.

## Claims (A rows: opened the cited line, +-5)

| id | verdict | cited | found at cited line | note |
|---|---|---|---|---|
| A1 | UPHELD | O/service.py:167 | `else:` then error "entry must be a string or a mapping with a 'command' key" (:167-173) | |
| A2 | UPHELD | :143 | docstring :140-147 "shell is false -> argv executed with shell=False; true -> raw handed to the shell; error must not be executed" | |
| A3 | UPHELD | :136 | `_SHELL_METACHARS = frozenset(";&\|`$<>\n\r")` | |
| A4 | UPHELD | :175; test :214 | scan over `raw` before `shlex.split`; test :214-220 says intended | |
| A5 | UPHELD | :180; test :46 | message names the mapping form with `shell: true`; test asserts "shell: true" in error | |
| A6 | UPHELD | :185; test :88 | `shlex.split` in try, `ValueError` -> "could not tokenize command"; test :88-91 | |
| A7 | UPHELD | :158, :194 | `if not raw` (mapping) :158; `if not argv` :194-195; the blank STRING case is :165-166, 7 lines from :158 | follow-up: cite :165 too |
| A8 | UPHELD | :160; test :70 | `bool(entry.get("shell", False))` -> shell path, else "fall through" :162; test :70-73 | |
| A9 | UPHELD | :160 | `bool(...)` so the string "false" is truthy | |
| A10 | UPHELD | :2097; test :111 | `if cmd.error is not None:` -> error step returncode -1 -> `continue`; test :111-130 spy raises on run | |
| A11 | UPHELD | :2106 | `continue` | |
| A12 | UPHELD | :2107; test :133 | `target = cmd.raw if cmd.shell else list(cmd.argv)`; `shell=cmd.shell` :2112; test :133-160 | |
| A13 | UPHELD | :2109 | `subprocess.run(... cwd, shell, text, capture_output, check, timeout=1800)`: no env, stdin, session or bound | |
| A14 | UPHELD | :2127; test :195 | `except FileNotFoundError` -> status "error"; test :195-211 | |
| A15 | UPHELD | :2136 | `TimeoutExpired` -> status "error", stderr "Timed out after" :2141-2143 | |
| A16 | UPHELD | :2123 | `[-4000:]` on stdout and stderr | |
| A17 | UPHELD | :2122 | `"success" if returncode == 0 else "failed"` | |
| A18 | UPHELD | :199, :2090 | `_looks_available` :199-210; use :2090-2091 | |
| A19 | UPHELD | :2169 | "No verification commands were applicable." under `if not steps` | |
| A20 | UPHELD | :2002 | `_read_yaml` returns `dict(default)` for missing/exception/non-dict :2003-2010 | |
| A21 | UPHELD | :492 | `load_policies` returns autopilot, verification, release | |
| A22 | UPHELD | :90; test :94 | `_DEFAULT_VERIFICATION_POLICY` commands: two strings and one mapping with `"shell": True` :99-106; test :94-100 | |
| A23 | UPHELD | :70, :1208 | `"max_attempts": 3` :70; `_max_attempts` :1208-1213 | follow-up: 3 is the DEFAULT of a policy-configurable value, not a fixed bound; reword "defaults to three" |
| A24 | UPHELD | test :223 | `f"{sys.executable} --version"`, status success, returncode 0 :223-234 | |
| A25 | UPHELD | deepseek spawn.ts:260, :358 | `killGroup` `process.kill(-pid, sig)` swallowing errors :260-266; `detached: platform !== 'win32'` with the group comment :358-360 (MIT, references/LICENSES.md:12) | |
| A26 | UPHELD | openharness/LICENSE:1 | "MIT License", "Copyright (c) 2025 OpenHarness Contributors" | |

No citation is outside references/, none touches references/autogpt/autogpt_platform/ (A rows cite openharness and deepseek_harness only), dify is not cited.

## Claims (N rows: every named check run by me on the patched copy)

| id | verdict | check run and result |
|---|---|---|
| N1 | UPHELD | runner.py sha256 c34f998b...06166e6 before and after (identical to the base copy); `grep -c gates runner.py` = 0; `git apply --stat` lists 3 files, no runner.py; tests/test_evals_baseline.py and tests/test_stream.py byte-identical to HEAD; M14, M20 killed in the runner |
| N2 | UPHELD | 63 documents + 15 raw files collected and pass; my own 22-case file probe (BOM, NaN, 1.0, true, duplicate keys at root/gate, `Shell`, string "true", 1, surrogate id, NUL id, 5,000-digit int, 262,144 `[`, 300 KB blank, empty, non-ASCII id) is identical on 3.11, 3.12, 3.13 and every case is a GateFileError (a lone-surrogate argv loads and is refused at plan time); L24, Z04 survive and are equivalent (see Mutation) |
| N3 | UPHELD | tests pass; L18, L19, F01 killed; my I25 (empty list accepted at load) killed |
| N4 | UPHELD | 12-case status table passes; F23-F30, M07, M08, M10 killed; real CLI exit 0/1/2 observed (bigbin/failing matrix rc=1, refused rc=2); no 3 anywhere |
| N5 | UPHELD | `grep -n _stdout_lost gates.py` = 4 lines; M11, M15-M19 killed; /dev/full test ran (not skipped) |
| N6 | UPHELD | counts 9 / 16 / 16 / 15 match; A01-A10, X01-X21 killed; my I01-I06 (no strip, `>=` cap, first-char scan, quotes-stripped scan, `comments=True`, `posix=False`) all killed |
| N7 | UPHELD as written (the list form is verbatim); see ATK1 for what that permits | Q12, Q14 killed |
| N8 | UPHELD | R08-R13 killed; my I07, I08 killed |
| N9 | UPHELD | R01-R07 killed; my I09, I10, I11 (checks only on argv[0]) killed |
| N10 | UPHELD as written (the `shell` key needs all five conditions) | Q01-Q11, F02, F03, F34, M01, M02 killed; my I20, I35, I36 killed; spy run: `shell:true` without `--allow-shell` spawns 0 processes. The claim does NOT cover the `sh -c` path in ATK1 |
| N11 | UPHELD | counts 12 and 5 match; `grep -n "guard_tool_call(" gates.py` = 1 line; Q24c equivalent not re-judged beyond the runner (it did not appear as a survivor: the runner lists Z01-Z05, L24, M22 only, see Mutation); my I13, I14, I35, I37 killed |
| N12 | UPHELD | my probe of 25 cwd values (`..`, symlink out, symlink in, a file, missing, `~`, `$HOME`, empty, NUL, `//etc`, 2,000 chars, trailing slash, `a/../sub`) gives the documented answers; S01, S06, S14, S15, E06, E07 killed; my I12, I17, I18, I19 killed |
| N13 | UPHELD | my own spy on `subprocess.Popen` over 6 mixed files (ok + metachar, ok + shell without flag, ok + force-push, ok + cwd `..`, ok + empty executable, refused FIRST): exit 2 and 0 spawns in all six |
| N14 | UPHELD | `grep -c "shell=True" gates.py` = 0; `grep -nE "import subprocess\|os\.system\|os\.popen"` rc 1; `grep -n "stream_process("` = 1 call; my fd/thread probe (22 gates incl. fail, ENOENT, timeout) leaves fds 4 -> 4 and 1 thread |
| N15 | UPHELD | the three timeout tests pass; S03, S04, E03-E05, E13, E14, E21, E22 killed (S04 and E-series by serial re-run); my I33, I46 killed |
| N16 | UPHELD | my real-process matrix: no-shebang script -> error (ENOEXEC as OSError), `kill -9 $$` -> fail "killed by signal 9", directory as argv[0] -> error, mode 644 -> error, bad shebang interpreter -> error, missing command -> error, silent gate -> pass, binary + `\xff\xfe` 514 KB output -> pass with truncated true; E08-E22, E38-E40 killed; my I32 killed |
| N17 | UPHELD | tests pass; K13, K14, E23-E33 killed; my I29, I30, I31, I44 killed |
| N18 | UPHELD | tests pass; K12, F09-F17 killed; my I26, I27 killed |
| N19 | UPHELD | tests pass; F17-F22 killed, F22 under PYTHONHASHSEED 0-39 by the runner; L26-L28 killed; my I15, I38 killed |
| N20 | UPHELD | tests pass; M12-M14, M23, E35-E37 killed; my I49, I50 killed |
| N21 | UPHELD | same-file-same-report passes; ordering mutants killed under seeds 0-39 |
| N22 | UPHELD | tests pass; Q31-Q35, E12, M09 killed; observed texts: "could not start (OSError)", "the root argument does not exist...", no path echoed |
| N23 | UPHELD for what it claims | `grep -n "O_PATH" sensitive_paths.py` = 3 lines (:5, :7, :61); shell refusal test passes; Q07, Q08 killed; Windows and macOS stay UNVERIFIED, as the row says (no claim made) |
| N24 | UPHELD for interpreter versions | new tests 366 passed on 3.11.15, 3.12.3, 3.13.14, each also under `-W error`; full suite `env -u PYTHONUNBUFFERED` 3.11: 1770 passed 10 skipped (118 s); `PYTHONUNBUFFERED=1` 3.11: 1770/10 (120 s); 3.12: 1770/10 (117 s); 3.13: 1770/10 (119 s); test_adversarial_inputs_are_linear did not fire. My plan/cwd/loader probes are byte-identical across the three versions. Limits of this row: it does not cover signal disposition or PATH permissions (ATK2, ATK3) |
| N25-N27 | UPHELD (N/A) | `grep -ciE "slippage\|borrow\|survivorship\|pnl\|fee" gates.py` = 0 |
| N28-N30 | UPHELD (N/A with the stated limit) | no series read; limit stated in Design 15 and Does not cover ("exit code is the whole verdict") |
| N31 | UPHELD | no `import re` in gates.py (rc 1); I re-ran 02_strategy-architect_C9_redos.py on 3.11 and 3.13: 346 rows, "overall OK", slowest 0.153 s |
| N32 | UPHELD | the diff is +4 lines; `grep -n "cwd=cwd" stream.py` = 1; every caller of `stream_process` (docker_engine.py:132 uses keywords only; mcp/client.py imports only `scrubbed_env`) is unaffected; S01, S06, S14, S15 killed |
| N33 | UPHELD | docstring carries "adapted (MIT, own code) from references/openharness/.../service.py:155"; my 8-word check (words only) of gates.py, test_gates.py, stream.py against service.py and test_verification.py: only `from pathlib import Path` / `from typing import Any`. With punctuation split there are extra hits that are code syntax (the 9-symbol metacharacter set, dataclass and typing boilerplate), no prose |
| N34 | UPHELD | the three files contain no credential shape (my grep for sk-, ghp_, AKIA, xox, PEM, AIza, JWT = rc 1); Hangul rc 1 on all three files |
| N35 | UPHELD | `test_the_documented_bounds` passes; K01-K16 killed |
| N36 | UPHELD for SIGTERM and for SIGINT when SIGINT is not inherited as ignored | real-process test passes; 8 manual SIGTERM runs against a gate that floods stdout: rc 143, gate gone each time; G01-G12 killed. See ATK2 for the test's environment dependence and the SIGHUP follow-up |

## Judge attack rows

| id | verdict | evidence |
|---|---|---|
| ATK1 | REJECTED (blocking; QA bar (a) "run a shell when not declared"; Decision 3 rationale) | The two-key rule claims "editing the file alone cannot switch a shell on" (Decision 3). It can. Real CLI run (3.11, patched tree), no `shell: true`, no `--allow-shell`: gates `{"id":"sh1","argv":["sh","-c","echo A; echo B > out.txt && echo $0"]}` and `{"id":"sh2","command":"bash -c ls"}` both ran: status pass, exit 0, out.txt created with "B", `;` `>` `&&` `$0` all interpreted by a shell. `plan_gate` also accepts (no refusal): `["bash","-c","echo $HOME > f"]`, `["/bin/sh","-c","id && id"]`, `["dash","-c","a;b"]`, `["zsh","-c","a;b"]`, `["env","sh","-c","a;b"]`, `["busybox","sh","-c","a;b"]`, `["xargs","-I{}","sh","-c","{}"]`, `["su","-c","a;b"]`, `["find",".","-exec","sh","-c","a;b","{}",";"]`, `["bash","--noprofile","-c","a;b"]`, and the string form `sh -c id`, `env sh`, `/bin/sh -c id`. The guard only denies the dangerous payloads it recognises (`sh -c 'rm -rf ~'`, `curl x \| sh`, force-push, `~/.ssh`). No test pins either answer (`grep -n '"sh"\|bash\|sh -c' tests/test_gates.py` hits only a refused `\| bash` payload and the `shell:true` fence test). The design never states that `sh`/`bash`/... as argv[0] (or behind `env`, `busybox`, `xargs`) is a shell run without declaration; Design 6(d) and Does not cover only mention `python -c`, `make` and scripts. The title claim "no shell" and Decision 3 are overstated. Required before build: either refuse a shell (basename in sh bash dash ksh zsh fish, applied to NON-shell gates only; my naive version that also hit the `/bin/sh -c` argv of declared shell gates broke 11 tests, so place it before the shell branch) with a policy error pointing at `shell: true`, plus tests and mutants for it, or delete the Decision-3 sentence and the "no shell" wording and state plainly that argv[0] may itself be a shell, that wrappers (`env`, `busybox`, `xargs`, `find -exec`, `su -c`) and interpreters (`python -c`, `perl -e`, `awk system()`) are not detected, and that `shell: true` plus `--allow-shell` is a declaration convention for the string form, not a control. Wrapper chains cannot be closed by a tripwire, so the second option must be written in any case. |
| ATK2 | REJECTED (blocking; signal-behaviour dependent test, the C8 and test_ctrl_c_interrupts_wait class) | `test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass[SIGINT]` Popens the runner without resetting SIGINT. When the suite is started with SIGINT ignored (a background job, `nohup`), the child Python keeps SIGINT ignored and never raises KeyboardInterrupt. Reproduced: `bash -c "trap '' INT; pytest tests/test_gates.py -k a_signal_to_the_runner"` gives `1 failed, 1 passed in 31.5s`, `subprocess.TimeoutExpired ... timed out after 30 seconds` at `proc.communicate(timeout=30)`. Fix: `preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL)` (or set it in the test around Popen). Foreground, 3.11/3.12/3.13, all pass. |
| ATK3 | REJECTED (blocking, one-line fix; environment/platform dependent test) | `test_missing_executable_is_an_error_not_a_pass` asserts the message "executable or folder not found". Run as user `nobody` (not root) in this container: 365 passed, 1 failed, message was "not executable or not permitted", because PATH contains root-only directories (/root/.local/bin, /root/.cargo/bin, /root/.bun/bin: mode 700 home) and execvp reports the saved EACCES in preference to ENOENT. With a PATH of accessible directories the same user passes 366/366. The code is right (both are status `error`, never pass); the test depends on every PATH entry being searchable. Fix: set `PATH` in the test, or accept both messages. |

## Guardrails (quant-guardrails.md)

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C9 | N/A no trades modelled; gates read an exit code | N/A no positions | N/A no fills | N/A reads no series; stated limit in Design 15: a gate cannot see look-ahead inside the command it runs | N/A no universe | N/A no split or scaler |

## Mutation (judge)

- Architect's runner (02_strategy-architect_C9_mutate.py, copied to scratch, run on my patched tree on 3.11, prefix groups serially, 4 workers inside a group, each group with an unmutated CONTROL run first: 366 passed): 297 mutants (A10 X24 L28 P36 Q40 R14 E40 F34 K16 M23 G12 S15 Z5): killed 290, survived 7, unexpected survivors 0. The 14 timing-only kills were re-run serially by the runner and killed again (E03 E04 E05 E13 E21 E22 E34, F11 F13 F14 F15 F25, Q12, S04). F22 and the other ordering mutants run under PYTHONHASHSEED 0-39 inside the runner and were killed.
- Equivalence of the 7 survivors, judged: Z01, Z02 `zip(strict=True)` to False: both lists have one entry per gate on those branches, UPHELD equivalent. Z03 `isinstance(p, str)` to `not isinstance(p, Plan)`: `plan_gate` returns exactly Plan or str, equivalent. Z04 `entry.get` for the timeout default: an explicit JSON null gives None and the same refusal, equivalent. Z05 `SandboxDenied` to `OSError`: SandboxDenied is a PermissionError; any other OSError would fall into the outer `except Exception` and still refuse, equivalent in outcome (message differs). L24 `!=` to `<` on `len(set) vs len(list)`: a set is never larger, equivalent. M22 load/Workspace order: both failures are exit 2 before any gate runs, equivalent.
- Independent mutants (scratchpad/j9/indep.py, fresh tar copy per mutant, python -B, `-x`, each mutation verified single-occurrence and file changed): 50 new mutants I01-I50 covering the string rules, argv checks on argv[0] only, guard input and cwd key, cwd resolution and fence mode, report counting (not-run counted as pass, ok without non-empty check), SHELL_PATH by PATH lookup, BOM, RecursionError at load, schema_version bool, empty list, duplicate keys, unknown keys, id charset, timeout bool/zero, tail head vs tail, redaction on one stream, capture truncation flag, signal death as pass, timeout ordering, SIGTERM restore, finally without killpg, env scrub TOKEN dropped, stdout cap. 48 killed, 2 survived: I45 (stream.py: exit chunk emitted even when `proc.poll()` is None) outcome is `int("None")` ValueError in `collect`, which `_run_one` maps to status error, never pass, so equivalent for the bar and not in the patch; I48 (`parsed or ()` rewritten as `tuple(parsed) if parsed else ()`) equivalent by construction. No false-pass survivor. Exact kill tests are in the run output, e.g. I13 `test_plain_strings_refused[-empty command]`, I17 `test_cwd_default_is_the_root_and_child_runs_there`, I28 `test_the_sigterm_handler_unwinds_with_143_and_is_restored`.
- The mutation suite cannot kill a mutant of ATK1 because no test asserts anything about a shell as argv[0]: adding "refuse shells in non-shell gates" and removing it is invisible to the 366 tests.

## Other checks reproduced

- ruff check src tests: all checks passed. black --check src tests: 71 files unchanged. mypy --strict src: no issues in 40 files. scripts/check-harness-refs.sh: 0 FAIL lines, rc 0 (packager inside it exit 0). scripts/package-plugin.sh rc 0 (the plugin zip sizes match the design). Hangul (LC_ALL=C.UTF-8) rc 1 on gates.py, test_gates.py, stream.py. Secrets grep rc 1.
- Environment matrix on the new tests (all 366 passed): LC_ALL=C with a 160-character TMPDIR and PYTHONHASHSEED 0 and 7; LC_ALL=POSIX with PYTHONIOENCODING=latin-1; `-X dev`; HOME=/, /nonexistent, /tmp, unset; `env -i PATH=/usr/bin:/bin`; six concurrent runs on 4 cores (13.4-13.9 s each, no timing failure); as root; as nobody only with a sane PATH (ATK3). Fails only in the two environments above.
- Spawn, status and cwd probes on the real CLI: ENOEXEC, EACCES, directory as argv[0], bad shebang, signal death, silent gate, 514 KB non-UTF-8 output; exit-0-after-printing-FAIL is a `pass`, stated in Design 9 and Does not cover (confirmed visible, not hidden).
- Statement checks: `SHELL` metacharacter policy, `$HOME` and `${IFS}` refused in the string form, `A=b cmd`, `-x`, NUL, unbalanced quote, `\r`, `\n` all refused; `~`, globs, `{a,b}` stay literal; `\x0b` and `\x1c` are refused by the guard as unparseable.
- Stream.py behaviour for existing consumers: unchanged (new keyword-only `cwd` defaults to None; docker_engine passes keywords).

## Follow-ups (non-blocking)

1. SIGHUP orphans a running gate: `kill -HUP` on the runner gave rc 129 and the gate kept running (killed by me). Decision 9's wording "A signal sent to the runner kills the running gate's process group" is overstated; either handle SIGHUP like SIGTERM or list it with SIGKILL under Does not cover. Never a pass, no report.
2. Effort label: the item is M, not S: 402-line module (344 code lines) + stream edit + signal handling + a 1,591-line test file (4x the module) + 297 mutants. The 36 N rows and 297 mutants are proportionate to a component that spawns commands and match the fixed QA bar; the label should change.
3. `scrubbed_env` removes names with KEY/PASSWORD/SECRET/TOKEN only. Does not cover lists PATH and PYTHONPATH; LD_PRELOAD, BASH_ENV, PYTHONSTARTUP, ENV, PYTHONHOME also pass through to a no-shell run (operator-owned environment, but name them).
4. `_sigterm_raises` restores `previous` unconditionally; `signal.signal` returns None when the old handler was installed from C, and restoring None raises TypeError. Guard with `if previous is not None`.
5. A7 should also cite service.py:165 (the blank-string branch); A23 should say "defaults to three".
6. The false-positive list heading says "accepted by design" for inputs the string form REFUSES (`echo $HOME`, `a|b`); reword to "refused although harmless".
7. N25-N27 check `grep -ciE "...|fee"` would trip on the word "feed"; harmless today (0).

## Escalation

Not applicable (round 1/3).
