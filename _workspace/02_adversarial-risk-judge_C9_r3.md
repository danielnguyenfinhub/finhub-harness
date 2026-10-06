TOTALS: UPHELD 69 / REJECTED 5 / UNVERIFIED 0 — round 3/3

# Adversarial verdict — C9 (verification gates as data: argv only), revision 3

- Audited file: _workspace/02_strategy-architect_C9.md (rev 3, 3,652 lines) with 02_strategy-architect_C9.patch (sha256 3ef03715de5787d6967440b2361ea7506968764cae5a95aab763e292368f638f, matches; `git apply --stat`: gates.py +489, stream.py +4, test_gates.py +1,976; no runner.py).
- runner.py sha256 c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6 before and after (matches).
- Judged tree: tar copy of the working tree at HEAD 588dd9b (everything except .venv, .git, _workspace, caches; references/, .gitignore, skills/, .claude/ included) plus `git apply` of the patch. Scratch: scratchpad/j9r3/pat. Interpreters: repo .venv 3.11.15, v312 3.12.3, v313 3.13.14. Nothing in the repo or the architect's files was edited.
- Extra round authorised by Daniel: none (no authorisation line in the launch prompt; none written).
- Changed claims re-audited this round: N37, N24, N40, N41, N42 (all rows touching changed text re-run, below); A1-A26 re-opened line by line (all cite the same lines as r2, all hold); every other N row re-run on the shipped tree.
- Rows REJECTED: two defects.
  1. ATK5 (code, blocking): a shell runs without `shell: true` through an absolute path that is resolved by the RUNNER but opened by the CHILD: `/proc/self/cwd/mysh` with `mysh -> /bin/sh`. Falsifies N37 ("symlinks of any name ... reached by an absolute path") and N41 ("never from the runner's"). Same family as ATK4, one path the rev-3 fix does not reach. Rows N37, N41, ATK5.
  2. ATK6 (proof gap, blocking by the false-pass-mutant rule): my mutant K08 (the PATH search takes the LAST hit instead of the first) survives all 505 tests, and it is a real false pass: with the shell link EARLIER on PATH than a harmless file of the same name the mutated plan accepts and the child runs the shell. N42's "first executable regular file" is stated and not pinned. Rows N42, ATK6.

## Scope 1: ATK4 closed, both r2 reproductions, real CLI

Run with PYTHONPATH on the patched src and a Popen spy over the whole CLI run (scratchpad/j9r3/spy.py).

| case | result |
|---|---|
| `ln -s /bin/sh sub/mysh`; gate `{"argv":["./mysh","-c","echo A; echo B > out.txt && echo $0"],"cwd":"sub"}`, runner in the parent | exit 2, status `policy-error`, message "the executable is a shell; declare shell: true and pass --allow-shell", spawns=0, no `sub/out.txt` |
| same link, runner in `other/`, `--root ../sub`, gate `{"argv":["./mysh","-c","echo B > out2.txt"]}` (default cwd) | exit 2, `policy-error`, spawns=0, no `out2.txt` |
| declared `{"command":"echo A; echo B > out3.txt","shell":true}` without `--allow-shell` | exit 2, `policy-error` "shell gate refused: pass --allow-shell", spawns=0 |
| same with `--allow-shell` | exit 0, spawn `['/bin/sh','-c',...]`, `out3.txt` created |

ATK4 as reproduced in r2: CLOSED (UPHELD).

## Claims (A rows: opened the cited line, +-5)

| id | verdict | found at cited line |
|---|---|---|
| A1-A26 | UPHELD | Re-opened every cited line: service.py :167 `else:`, :143 "When ``shell`` is false, ``argv`` is executed with ``shell=False``", :136 `_SHELL_METACHARS = frozenset(";&\|`$<>\n\r")`, :175 `if any(ch in _SHELL_METACHARS for ch in raw):`, :180 error text, :185 `try:`, :158/:165/:194 the three empty checks, :160 `if bool(entry.get("shell", False)):`, :2097 `if cmd.error is not None:`, :2106 `continue`, :2107 `target: ... = cmd.raw if cmd.shell else list(cmd.argv)`, :2109 `subprocess.run(`, :2127 `except FileNotFoundError`, :2136 `except subprocess.TimeoutExpired`, :2123 `[-4000:]`, :2122 success/failed, :199 and :2090 `_looks_available`, :2169 "No verification commands were applicable.", :2002 `_read_yaml`, :492 `load_policies`, :90 `_DEFAULT_VERIFICATION_POLICY`, :70 `"max_attempts": 3,`, :1208 `_max_attempts`; test_verification.py :214 :46 :88 :70 :111 :133 :195 :94 :223 all name the claimed tests; deepseek spawn.ts :260 `export function killGroup`, :358 the `detached` comment; openharness/LICENSE:1 "MIT License". No citation is outside references/; none touches references/autogpt/autogpt_platform/. |

## Claims (N rows: every named check run by me on the shipped patched copy)

| id | verdict | check run and result |
|---|---|---|
| N1 | UPHELD | runner.py sha unchanged, `grep -c gates runner.py` = 0, patch lists no runner.py; M14, M20 killed by the architect's runner |
| N2 | UPHELD | file tests pass; L01-L28, P01-P36, X30-X32 killed; L24, Z04 equivalent |
| N3 | UPHELD | L18, L19, F01 killed |
| N4 | UPHELD | F23-F30, M07, M08, M10 killed; no exit 3 |
| N5 | UPHELD | `grep -n _stdout_lost gates.py` = 4 lines; M11, M15-M19 killed |
| N6 | UPHELD | A01-A10, X01-X21 killed |
| N7 | UPHELD | Q12, Q14 killed (Q12 by serial re-run) |
| N8 | UPHELD | R08-R13 killed |
| N9 | UPHELD | R01-R07 killed |
| N10 | UPHELD | shell:true refused without the flag, runs with it (Scope 1 table); Q01-Q11, F02, F03, F34, M01, M02 killed |
| N11 | UPHELD | `grep -n "guard_tool_call(" gates.py` = 1 line (:331); Q11, Q15, Q23-Q25b, Q28-Q30 killed (Q24c equivalent) |
| N12 | UPHELD | S01, S06, S14, S15, E06, E07, Q17-Q22b, Q26 killed |
| N13 | UPHELD | F04-F08, Q28-Q30 killed; Scope 1 spies show 0 spawns for every refusal |
| N14 | UPHELD | `grep -c "shell=True" gates.py` = 0; `grep -nE "import subprocess\|os\.system\|os\.popen"` rc 1; `grep -n "stream_process(" gates.py` = 1 (:360); E01-E07, S02, S05, S07-S13 killed |
| N15 | UPHELD | S03, S04, E03-E05, E13, E14, E21, E22 killed; the 14 timing kills re-run serially by the runner: Q12 E03 E04 E05 E13 E21 E22 E34 F11 F13 F14 F15 F25 S04, all KILLED(rerun) |
| N16 | UPHELD | E08-E22, E38-E40 killed |
| N17 | UPHELD | K13, K14, E23-E33 killed (architect's K ids) |
| N18 | UPHELD | K12, F09-F17 killed |
| N19 | UPHELD | F17-F22, L26-L28 killed |
| N20 | UPHELD | M12-M14, M23, E35-E37 killed |
| N21 | UPHELD | determinism test passes; ordering mutants killed |
| N22 | UPHELD | Q31-Q35, E12, M09 killed |
| N23 | UPHELD | `grep -n O_PATH sensitive_paths.py` = 3; Q07, Q08 killed; Windows/macOS UNVERIFIED as stated |
| N24 | UPHELD | 505 passed on 3.11.15, 3.12.3, 3.13.14, each plain and under `-W error` (13.9-14.6 s); full suite 1,909 passed / 10 skipped on 3.11 PYTHONUNBUFFERED unset (119.6 s) and =1 (121.0 s), 3.12 unset (119.9 s) and =1 (120.4 s), foreground one after the other; `test_safety.py::test_adversarial_inputs_are_linear` did not fire in any of the four |
| N25-N27 | UPHELD (N/A) | `grep -ciwE "slippage\|borrow\|survivorship\|pnl\|fees?" gates.py` = 0 |
| N28-N30 | UPHELD (N/A with the stated limit) | no series read |
| N31 | UPHELD | `test_the_module_has_no_regex` passes; `grep -nE "^import re\|^from re " gates.py` rc 1; the architect's redos script on 3.11 prints "rules in the table: 10; limit 5.0s; overall OK" |
| N32 | UPHELD | `grep -n "cwd=cwd" stream.py` = 1 (:137); diff +4; S01, S06, S14, S15 killed |
| N33 | UPHELD | docstring has the adapted-from line (`grep -c "references/openharness" gates.py` = 1); my 8-word check (words lower-cased, punctuation split) of gates.py, test_gates.py, stream.py against service.py, test_verification.py, spawn.ts: only `from pathlib import Path / from typing import Any` in gates.py and test_gates.py, 0 in stream.py |
| N34 | UPHELD | secrets grep rc 1 on the three files; Hangul (U+AC00-D7AF, 1100-11FF, 3130-318F, LC_ALL=C.UTF-8) rc 1 on gates.py, test_gates.py, stream.py, the design .md and the .patch |
| N35 | UPHELD | `test_the_documented_bounds` passes; K01-K16 (architect's ids) killed |
| N36 | UPHELD | the signal tests pass in every matrix cell below; G01-G14 killed; `grep -n "_signals_raise" gates.py` = 2 lines (:447, :475); the Decision 9 limits are the ones I reproduced in r2 and are now stated |
| N37 | REJECTED | The claim: a shell is refused "symlinks of any name, reached by an absolute path, a relative path or a bare name" with the child's resolution "FROM THE GATE'S cwd". An absolute path whose resolution depends on WHICH PROCESS opens it is resolved by the runner and opened by the child. See ATK5: `/proc/self/cwd/mysh` (`mysh -> /bin/sh` in the gate folder) runs a shell, status pass, `out.txt` created. All other parts of N37 reproduce: the 41 and 14 refusal cases pass; H01-H10, H18-H23, H3-*, T01-T12 killed; `grep -n "_shell_refusal" gates.py` = 2 lines (:277 def, :327 call, after the cwd fence); real CLI exit 2 with no file (Scope 1); declared shell gate unaffected |
| N38 | UPHELD | 29/2 tests pass, lists pinned verbatim; H11-H17, H4-*, H5-*, H6-* killed |
| N39 | UPHELD | `grep -c "NOT detected" gates.py` = 1; `grep -c "not a sandbox" gates.py` = 2; `grep -n "editing the file alone cannot switch a shell on"` on the design = lines 31 and 3650 only (the rev-2 table row quoting it, and N39); CLI `--help` prints "a declaration convention for the string form, not a sandbox"; Decision 3 states the `python -c` caveat. The ATK5 case is a defect of N37, not a wording gap |
| N40 | UPHELD | all 505 pass on 3.11, 3.12, 3.13 under `trap '' INT`, `trap '' INT HUP`, `setsid -w nohup ... < /dev/null`, `env -i PATH=/usr/bin:/bin`, stdin closed (15 runs); as user nobody (copy at /tmp/j9nb3 because /tmp/claude-0 is mode 700, `setpriv`): repo PATH (root-only dirs), `/usr/local/bin:/usr/bin:/bin`, `env -i` (3 runs, 3.11); as root (this session) plain and `env -i`; LC_ALL=C + 150-char TMPDIR + PYTHONHASHSEED=0: 505 passed; `grep -n default_int_handler tests/test_gates.py` = 1 |
| N41 | REJECTED | The claim: "resolves `argv[0]` from the GATE's cwd, never from the runner's". Both of the judge's named repros pass (Scope 1; `test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd` and its sibling, 2 real-CLI cases, `test_the_relative_path_entry_is_not_taken_from_the_runner_cwd`; `grep -c "_resolve" gates.py` = 2; T01, T07, T08, T10, T12 killed; my K01-K04, K10, K13, K14 killed) but "never" is false for `/proc/self/cwd/...` (ATK5): `os.path.realpath` runs in the runner's `/proc/self`, the child's exec in its own |
| N42 | REJECTED | The claim: a bare name is searched along PATH "as Popen's exec does: first executable regular file". The tests named (5 PATH values, the non-executable skip, the directory skip, the residual-limits pin, the 3 false positives) pass; T02-T06, T09, T11 killed. But "first" is not pinned: my mutant K08 (`for entry in reversed(os.get_exec_path())`, last hit instead of first) survives all 505 tests, and it is not equivalent: with PATH `d1:d2`, `d1/zz -> /bin/sh` and `d2/zz -> /bin/true`, the mutated plan ACCEPTS and the child runs the shell (oracle case "sh earlier": plan ACCEPT, child prints SHELLRAN). A false-pass mutant is blocking |

## Judge attack rows

| id | verdict | evidence |
|---|---|---|
| ATK1 (r1) | UPHELD (closed) | `sh -c`, `bash -c`, `env sh`, `busybox sh`, the wrapper forms: refused, 0 spawns (Scope 1 spies; 41-case test) |
| ATK2 (r1) | UPHELD (closed) | signal tests pass under trap/nohup/setsid/env -i on 3.11/3.12/3.13 |
| ATK3 (r1) | UPHELD (closed) | as nobody, three PATH/env shapes, 505 passed |
| ATK4 (r2) | UPHELD (closed) | both repros exit 2, 0 spawns, no file (Scope 1); the declared shell gate still runs only with the flag |
| ATK5 (new) | REJECTED (blocking: a shell runs without `shell: true` in a case rev 3 claims to refuse; N37 and N41 falsified) | Real CLI, patched tree, 3.11. `ln -s /bin/sh sub/mysh`. Variant A: runner in the parent folder, gate `{"argv":["/proc/self/cwd/mysh","-c","echo A; echo B > out.txt && echo $0"],"cwd":"sub"}` -> `"status": "pass"`, `"stdout_tail": "A\n/proc/self/cwd/mysh\n"`, exit 0, `sub/out.txt` contains `B`, one spawn `['/proc/self/cwd/mysh', ...]`. Variant B: runner in `other/`, `--root ../sub`, argv `["/proc/self/cwd/mysh","-c","echo RAN > out.txt"]` -> pass, `out.txt` created; the same with `/proc/thread-self/cwd/mysh` and `/proc/self/cwd/./mysh`. Control: with the runner's cwd equal to the gate cwd (`cd sub`, `--root .`) the same gate is refused, exit 2, 0 spawns, which is why the tests do not see it. Cause: `_resolve` does `os.path.realpath(os.path.join(cwd, word))`; for `/proc/self/cwd/mysh` that is a path whose `/proc/self` is the RUNNER's, so it resolves to `<runner cwd>/mysh` (a name that is not a shell, accepted), while the child (`chdir(gate cwd)` then `execve`) opens its own `/proc/self/cwd`. The same applies to a PATH entry `/proc/self/cwd`. Fix options (either closes it): (a) in `_resolve`, refuse (policy error) any word or PATH hit whose normalised path starts with `/proc/` or `/dev/fd/`, and add tests with runner cwd != gate cwd for `/proc/self/cwd/mysh`, `/proc/thread-self/cwd/mysh` and PATH `/proc/self/cwd`, plus a mutant that removes the guard; or (b) narrow N37, N41, Design 4b R2 and the docstring to say that a path through `/proc/self` is judged by its own name, pin it with a test, and say so in Does not cover |
| ATK6 (new) | REJECTED (blocking by the false-pass-mutant rule; N42) | K08 above. Kill test to add: PATH `d1:d2`, `d1/mytool -> sh`, `d2/mytool` a harmless executable (a copy of `true`), `plan(argv=("mytool","-c","a"))` must be refused. Nothing else in the PATH search is unpinned: K01-K07, K09-K15 were killed |

## Attack results on what rev 3 introduced (scope 2)

Method: an oracle (scratchpad/j9r3/oracle.py) builds a tree per case, runs the REAL `plan_gate` and then the REAL `Popen(argv, cwd=gate cwd, env=scrubbed_env())` of `echo SHELLRAN` and compares what the plan said with what the child did. Result for 28 cases:

- Plan and child agree (refused, child runs the shell): `./mysh`; `../up`; `../sub/mysh`; `//bin//sh`; `/bin/../bin/sh`; a 3-hop chain `l1 -> l2 -> l3 -> /bin/sh`; a chain across folders; bare name on PATH `bin:/usr/bin` (relative entry), `:/usr/bin` (empty entry), `.`, `""` (PATH empty); a non-executable file earlier on PATH; a directory of the same name earlier; a broken symlink earlier; the shell link earlier; `MYSH` (upper case); a bare name on an absolute PATH entry; PATH `../sub` with the gate cwd `other`; gate cwd given as a symlink (`lnk -> sub`) and gate cwd `other/../sub`; `./sh` (a file named sh, refused by name); trailing slash `/bin/sh/` (refused, the child would fail ENOTDIR).
- Accepted as stated: `/proc/self/exe` (python, not a shell: child printed 1), copy and hard link of a shell (child ran the shell: stated and pinned), symlink to a wrapper (stated and pinned).
- MISMATCH, blocking: `/proc/self/cwd/...` (ATK5).
- MISMATCH, stated, follow-up: an EXECUTABLE regular file earlier on PATH that exec skips for another reason (no shebang: ENOEXEC; shebang naming a missing interpreter: ENOENT) followed by a shell link of the same name later on PATH. Plan ACCEPT, child runs the shell (both cases reproduced). The Revision 3 paragraph states this ("the check may look at a file `exec` skips"). It is stated ONLY there: not in Does not cover, Design 4b R2, N37/N42 (which say "what the child's exec finds" and "as Popen's exec does"), or the module docstring, and the paragraph's heading "stated and pinned" is wrong for it (no test pins it; the residual-limits test covers the copy, hard link, wrapper and earlier-gate cases). Not counted as a rejection because the limit is disclosed in the design; add it to Does not cover and the docstring and pin it.
- Checked, no defect: PATH inherited through `scrubbed_env` (PATH is not scrubbed, so `os.get_exec_path()` and Popen's `get_exec_path(env)` read the same value; with PATH unset both use `os.defpath`); the gate has no `env` key (GATE_KEYS refuses it); Popen's search for a name with a slash (it execs the path as given, as `_resolve` assumes) and without one (PATH entries joined, empty entry = cwd after the child's chdir); `os.access(X_OK)` for root (needs one x bit, same as exec) and noexec mounts; case-insensitive file systems are handled by lower-casing the basename (macOS untested); NUL and surrogate words never reach `_resolve` (`_argv_refusal` first); trailing slash, `./sh`, `../sh`, `sub/../sh`, `//bin//sh`, `/bin/../bin/sh` above.
- TOCTOU: the design states that it is not caught: Does not cover (a link made by an EARLIER gate; "TOCTOU on cwd between the plan and the spawn"), Revision 3 residual paragraph, and the `_resolve` docstring ("Not looked at: a file created or swapped after this check"). Confirmed stated where it matters, with one gap: the executable swapped by a concurrent process is covered only by the docstring and the Revision 3 paragraph, not by Does not cover.
- Fence order: the cwd fence now runs BEFORE the shell check, so a gate with both a bad cwd and a shell executable reports "cwd refused (...)" instead of "the executable is a shell". Both are `policy-error`, exit 2, 0 spawns; no earlier test pinned the old order (all 505 pass; no earlier-pinned exit code or message changed).
- Platform note (follow-up): `_shell_link` and the new tests link to `shutil.which("sh")`. On a host where `sh` resolves to busybox the link's realpath is `busybox`, which is not a shell name, so those tests would fail (and in practice such a link, invoked under another name, is not an applet either). Debian/Ubuntu/Nix (this host) and macOS are fine; Alpine is UNVERIFIED. Not blocking.
- Shell list gap (follow-up, stated as "not exhaustive"): `ksh93`, `elvish`, `nu`, `xonsh` and versioned names (`zsh-5.9`, `bash5`) are not in the 14 names.

## Scope 3: the 16 new cases and environment dependence

- The 16 new cases (505 - 489): relative-symlink tests (2), real-CLI relative link (2), PATH entries (5), runner-cwd PATH entry (1), non-executable skip (1), directory skip (1), residual limits (1), false positives (3). No timing threshold, signal, tty, `/proc` or hash-seed dependence; only `shutil.which("sh")`, `shutil.which("env")`, symlink and hard-link support.
- Matrix, all 505 passed: 3.11/3.12/3.13 plain and `-W error`; 3.11/3.12/3.13 under `trap '' INT`, `trap '' INT HUP`, `setsid -w nohup < /dev/null`, `env -i`, stdin closed (15 runs); nobody x 3 (3.11); root plain and `env -i`; LC_ALL=C + 150-char TMPDIR + PYTHONHASHSEED=0. The hard-link test links the test's own copy (protected_hardlinks safe, verified as nobody).
- Same-class check (protected_hardlinks and friends) elsewhere in the file: the only `os.link` is the one the architect fixed; `/usr/bin/dash` is never linked.

## Scope 4: full suite and gates

- 1,909 passed / 10 skipped, four runs one after the other in the foreground: 3.11 unset 119.64 s, 3.11 =1 120.99 s, 3.12 unset 119.94 s, 3.12 =1 120.38 s. The known flaky timing test did not fire.
- `ruff check src tests`: all checks passed. `black --check src tests`: 71 files unchanged. `mypy --strict src`: no issues in 40 files. `scripts/check-harness-refs.sh`: rc 0, 0 FAIL lines. `scripts/package-plugin.sh`: rc 0 (finhub-harness-skill.zip 88,048 bytes, finhub-harness-evolve-skill.zip 7,021 bytes). Hangul rc 1 on all five files. Verbatim 8-word runs: only the import pair.

## Scope 5: mutation on the SHIPPED patch tree

- Architect's WHOLE runner (`C9_JOBS=4`): TOTAL 395, killed 388, survived-equivalent 7, unexpected survivors/partial 0. Survivors L24, M22, Z01-Z05 (all equivalent, same seven as r2). The 14 timing kills re-run serially, all KILLED(rerun) (list in N15). T01-T12 all KILLED.
- Adapted I01-I50: 48 killed, 2 survived (I45, I48; equivalent as in r1/r2), 0 bad.
- Adapted J01-J48: 46 killed, 2 survived (J14, J23; equivalent as in r2), 0 bad.
- Counts match the architect's: 395 / 388 / 7 / 0; I45, I48, J14, J23 equivalent.
- My 15 NEW mutants K01-K15 (only `_resolve`, the PATH search, the cwd-first ordering; each edit verified to occur exactly once; fresh copy and fresh `python -B -m pytest -x` per mutant): 14 killed, 1 survived.
  - Survivor K08 (last PATH hit instead of the first): NOT equivalent (above). Exact kill test: PATH `d1:d2`, `d1/mytool` a symlink to `sh`, `d2/mytool` a copy of `true`; `plan(argv=("mytool","-c","a"))` must be a refusal containing `--allow-shell`.
  - Killed: K01 realpath(word); K02 join(os.getcwd(), word); K03 PATH entry not anchored on the gate cwd; K04 anchored on the runner cwd; K05 no X_OK test; K06 exists instead of isfile; K07 relative PATH entries ignored; K09 PATH hit not realpath-ed; K10 abspath instead of realpath; K11 default PATH; K12 resolved name never added; K13 shell check on Path.cwd(); K14 shell check only for the root cwd; K15 empty PATH entry skipped.
- No mutant (the architect's or mine) resolves a `/proc/self/...` word, and no test has a `/proc/self` word at all: that is why ATK5 is invisible to the suite.

## Scope 6: doc-only items (a)-(f)

| item | verdict | where |
|---|---|---|
| (a) programs that run a shell without naming one: `flock -c`, `script -qec`, `runuser -c`, `parallel`, `sudo -s`, `env -S` | present and accurate | module docstring lines 14-17 (`script -c`), Decision 3(c), Does not cover bullet 2 (`flock` and `script` "ran for real in the judge's probe", true in r2) |
| (b) copies, hard links, symlink to a wrapper, links by earlier gates | present and accurate; pinned for these four | docstring, Decision 3(c), Does not cover, `test_the_stated_residual_limits_of_the_shell_refusal_are_pinned` (passes). NOT included and not pinned: the exec-skip mismatch above |
| (c) three new false positives | present | Design 4b "Known false positives" (`timeout 5 pytest tests/shell/sh`, `find . -path "*/bash"`, `time pytest -k sh`), `test_the_documented_wrapper_false_positives_are_refused` (3 cases) passes |
| (d) signal race (SystemExit between Popen and the `try`) | present, accurate (reproduced in r2) | Decision 9, Does not cover |
| (e) SIGHUP under nohup | present, accurate (rc 129, no report; reproduced in r2) | Decision 9, Does not cover, Follow-ups |
| (f) 444 -> 489; PYTHONPATH once; env-scrub reason | present | `grep -n "444"` hits only the two changelog rows that describe the fix; PYTHONPATH appears once in Does not cover; the `LD_PRELOAD`/`BASH_ENV`/`ENV`/`PYTHONSTARTUP`/`PYTHONHOME` reason is restated |

Overstatement sweep (design, docstring, CLI help): no remaining sentence says "no shell", "cannot switch a shell on" or "symlinks of any name" without the qualification, EXCEPT that "symlinks of any name, reached by an absolute path" (N37) and Design 4b R2 "however it is reached" are themselves false for `/proc/self/cwd` (ATK5); the module docstring says "a link to one found from the gate's folder", which is also not true for that path. The two remaining "no shell" strings (Design 8, N14, stream.py docstring) describe the Popen call, which is true.

## Guardrails (quant-guardrails.md)

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C9 | N/A no trades modelled; gates read an exit code | N/A no positions | N/A no fills | N/A reads no series; stated limit (Design 15) | N/A no universe | N/A no split or scaler |

## Follow-ups (non-blocking)

1. The exec-skip mismatch (no-shebang or bad-shebang executable earlier on PATH): add to Does not cover and the docstring, correct "stated and pinned", pin with a test (the oracle cases above are ready-made).
2. Executable swapped by a concurrent process: one more clause in Does not cover.
3. busybox-`sh` hosts (Alpine): tests UNVERIFIED there.
4. Shell names not in the 14 (`ksh93`, `elvish`, `nu`, `xonsh`, versioned names).
5. The r2 follow-ups stay follow-ups: SHELL_RUNNERS extensions (`runuser`, `flock -c`, `script -c`, `parallel`, `sudo -s`, `env -S`), skip a signal whose disposition is SIG_IGN, a post-run recheck for links made by earlier gates, copies and hard links.

## Escalation (round 3/3, REJECTED > 0; no extra round authorised)

| id | judge position | architect position (rev 3 text) |
|---|---|---|
| N37 / N41 / ATK5 | Rejected. `_resolve` resolves an absolute path in the RUNNER's process; `/proc/self/cwd` (and `/proc/thread-self/cwd`, or a PATH entry of that name) names a different folder in the child. Reproduced with the real CLI: `ln -s /bin/sh sub/mysh`; gate `{"argv":["/proc/self/cwd/mysh","-c","echo A; echo B > out.txt && echo $0"],"cwd":"sub"}`, runner in the parent: status pass, stdout `A\n/proc/self/cwd/mysh\n`, `sub/out.txt` created, no `shell: true`, no `--allow-shell`. Control: runner cwd == gate cwd is refused. N37 says "symlinks of any name ... reached by an absolute path"; N41 says "never from the runner's". Both are false for this path | Rev 3 text: "a word with a `/` is `realpath(join(cwd, word))`"; the ATK4 repros are closed; "the shell check may look at a file `exec` skips" is the only residual limit stated for the resolution; `/proc` is not mentioned anywhere in the design, the tests or the code. Likely position: a `/proc/self` path is the same class as `/proc/self/exe`, a tripwire limit, to be disclosed rather than closed |
| N42 / ATK6 | Rejected. "First executable regular file" has no test: mutant K08 (last PATH hit) survives 505 tests and is a real false pass (shell link earlier on PATH than a harmless file: plan ACCEPT, child runs the shell). One test closes it | N42 lists the PATH tests, T02-T06, T09, T11 killed; T11 ("only the first PATH entry searched") is the nearest mutant. Likely position: the 395-mutant table already covers the PATH search |

Both defects are small: ATK5 is a few lines (refuse a resolved path under `/proc/` or `/dev/fd/`, plus 3 tests and a mutant) or a wording change plus a pinning test; ATK6 is one test. The orchestrator should stop and take the escalation to Daniel with the table above.
