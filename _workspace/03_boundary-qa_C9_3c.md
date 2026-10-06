RESULT: PASS

# boundary-qa: C9 rev 3c (verification gates as data, argv only, no shell)

Prior FAIL D1 (`lnk/../mysh` with `lnk -> /proc/self/cwd`) is closed: reproduced verbatim through the real CLI in three runner placements, plus 14 further `..` forms, all refused (rc 2, policy-error, `strace -f -e trace=execve` shows 1 successful execve = the runner's own python). No new shell-execution bypass of a non-shell gate found by my own 70-row matrix x 3 placements, 4,700+ routes of my own kernel-truth differential fuzz, and a 76-mutant batch (73 killed, 3 survivors, all equivalent). Nothing in `src/` or `tests/` edited, nothing committed; scratch left in the scratchpad qa3c folder (the delete was blocked by a hook, no repo file touched).

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| argv[0] as the runner resolves it vs as the child execs it (D1 class) | child: Popen chdir(gate cwd) then exec; `..` after a link = parent of the link target; `/proc/self` = child's | gates.py `_no_dotdot` (raw `..` refused) + `_walk` (one physical walk, no normpath/realpath, /proc and /dev refused, >40 links refused); `grep -c "normpath\|realpath" gates.py` = 0 | yes |
| PATH search (runner `os.get_exec_path()`) vs Popen search of scrubbed env | `scrubbed_env()` keeps PATH; empty/relative entry = child cwd | `_resolve` joins each entry onto the gate cwd, walks it, hit = isfile and X_OK | yes (probes below) |
| `plan_gate` -> `stream_process(argv, env, cwd, timeout)` | `cwd=str(plan.cwd)`, resolved by `ws.check_read` | gates.py `_run_one`; positive control `pwd` in a symlinked gate cwd printed the real folder | yes |
| `run_gates` plan-all-first | one refused gate = nothing spawned | gates.py `run_gates` (len(ready) != len(plans)); M57/M84 killed | yes |
| exit codes / report | 0 pass, 1 fail, 2 policy | `exit_code`; M59/M60 killed | yes |
| runner.py (C4) | byte-identical | sha256 c34f998b... | yes |

## Gate
| command | exit | output observed |
|---|---|---|
| `sha256sum` gates.py / tests/test_gates.py / tests/gate_matrix.py / evals/runner.py | 0 | `a993f67f...2a56`, `d39174c0...a2`, `ec3de49a...4188`, `c34f998b...66e6`: all four equal the expected values |
| `git status --short` (before and after) | 0 | ` M src/master_finhub/evals/gates.py` / ` M tests/test_gates.py` / `?? tests/gate_matrix.py` |
| `env -u PYTHONUNBUFFERED .venv/bin/python -m pytest -q` (3.11, foreground) | 0 | `2081 passed, 10 skipped in 129.60s (0:02:09)` |
| `PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q` (3.11, after the one above) | 0 | `2081 passed, 10 skipped in 129.24s (0:02:09)` |
| `scratchpad/v312/bin/python -m pytest -q` (3.12.3) | 0 | `2081 passed, 10 skipped in 129.42s (0:02:09)` |
| `scratchpad/v313/bin/python -m pytest -q tests/test_gates.py` (3.13.14) | 0 | `677 passed in 26.41s` |
| `PYTHONHASHSEED=0..39 pytest -q tests/test_gates.py` (3.11, 40 fresh processes, run twice) | 0 | every seed `677 passed`; second sweep: 0 lines not `677 passed` |
| `ruff check src tests` | 0 | `All checks passed!` |
| `black --check src tests` | 0 | `All done! 72 files would be left unchanged.` (the pre-existing py3.15 target warning) |
| `mypy --strict src` | 0 | `Success: no issues found in 40 source files` |
| `LC_ALL=C.UTF-8 grep -nP '\p{Hangul}'` over the 3 files | 1 | no output (0 lines) |
| `sed -n 4p gates.py`; open `references/openharness/.../autopilot/service.py` | 0 | line 4 `Policy adapted (MIT, own code) from references/openharness/src/openharness/autopilot/service.py:155`; service.py:155 is `def _parse_verification_entry`, :136 `_SHELL_METACHARS = frozenset(";&\|`$<>\n\r")` |
| own 8-word scan (word tokens) of the added lines of gates.py and test_gates.py plus all of gate_matrix.py vs every file under `references/` | 0 | 10 distinct 8-grams, all import lines or kwargs: `__future__ import annotations import json import os import`, `import os shutil subprocess tempfile from pathlib import`, `capture_output true text true timeout 120 check false`. No prose or logic run: confirms the builder |
| compliance sweep (emails, AU mobiles, sk-/ghp_/Bearer, UUIDs) over the 3 files | 0 | no hits |
| `grep -c "normpath\|realpath" gates.py` | 0 | `0` |

## Probes (real CLI: `python -m master_finhub.evals.gates GATE --root D`, no `--allow-shell`)
Layout: gate cwd `D/sub`, runner cwd `D/a/b` ("elsewhere"), `D/sub` ("same"), `D/other` with `--root D` ("rootelsewhere"); the gate is `argv [WORD,"-c","touch D/MARK"]`; success = MARK created. 0 MARKs in 3 placements x 70 words, except the documented limits below.

| probe | result (all 3 placements unless stated) |
|---|---|
| `probe: lnk/../mysh` (`lnk -> /proc/self/cwd`, `mysh -> /bin/sh` in the parent; the prior D1 repro) | rc 2, `policy-error: the executable path has a '..' component...`, strace execve count 1, no MARK |
| `probe:` `./lnk/../mysh`, absolute `D/sub/lnk/../mysh`, `lt/../mysh` (`/proc/thread-self/cwd`), `ld/../mysh` (`-> /dev`), string form `lnk/../mysh -c x`, PATH `lnk/..:/usr/bin`, PATH `pc/..`, PATH `inner/..` | rc 2 each, policy-error, no exec |
| `probe:` `inner/../lsh` (a `..` after a plain folder), `../lsh_parent` | rc 2 refused (the stated cost of the raw `..` rule) |
| `probe:` symlink to a shell first (`./lsh`), middle (`dlink/lsh`, `dlink/dlink/dlink/lsh`, `dreal/tool`), last (`./rel`, relative target `../../bin/sh`; mixed chain `./chain1`->`inner/chain2`->`../chain3`->`lsh`->`/bin/sh`), 30-link chain | rc 2 `executable is a shell` each |
| `probe:` links into /proc and /dev: `lp/mysh`, `lproc/self/cwd/mysh`, `lps/cwd/mysh`, `lroot/bin/sh`, `./lexe`, `/proc/self/exe`, `/proc/self/root/bin/sh`, `/proc/self/cwd/lsh`, `/proc/thread-self/cwd/lsh`, `//proc/self/cwd/lsh`, `/./proc/self/cwd/lsh`, `//dev/null`, `/dev/null`, `/dev/fd/0`, `/proc/self/fd/0`, `lfd/0`, `devfd/0`, `./stdin` (`-> /dev/stdin`), `./nul` | rc 2 `under /proc or /dev` each |
| `probe:` `//bin//sh`, `/bin/./sh`, `/bin/sh/`, `lsh/`, `lsh/.`, `/bin/SH`, `SH`, `sh.exe`, `'s'h -c x` | rc 2 `executable is a shell` |
| `probe:` link loops: 50-link ring `./loop0`, self loop `./self`, 45-link chain to sh `./c0` | rc 2 `link loop or more than 40 links` |
| `probe:` PATH forms with a link to a shell in the gate folder: `binlink:/usr/bin`, relative `bin:`, empty first `:/usr/bin`, empty last `/usr/bin:`, `.`, PATH set to the empty string, PATH unset with `./zz` | rc 2 `executable is a shell` (PATH unset with a bare `zz`: rc 1 `not found`, defpath has no cwd entry, nothing ran) |
| `probe:` PATH entries `pc` (link to /proc/self/cwd), `/proc/self/cwd`, `//proc/self/cwd`, `/dev/shm`; a PATH hit `hit -> /proc/self/exe` | rc 2 `under /proc or /dev` |
| `probe:` sibling roots `/developer/tool`, `/devices/x`, `/procfs/x` | rc 1 `executable or folder not found` (not refused as opaque: the sibling rule holds) |
| `probe:` symlinked gate cwd (`subl -> sub`) with `./lsh` and `lp/../mysh`; gate cwd `subl2 -> /proc/self/cwd` with `./mysh`; `--root` as a symlink with relative and absolute `lsh`; `--root /` with cwd `/proc/self/cwd` | refused each (`..` or shell), or `cwd refused` in the same placement |
| control `pwd` in `sub`, in the symlinked `subl`, in `subl2` | rc 0 `pass`, prints the real folder (child cwd = the folder the runner checked) |
| `probe: strace -f -e trace=execve` on 12 refused words incl. the D1 repro | rc 2, 1 successful execve (the runner), no MARK; control `pwd`: 2 execves |
| own differential fuzz (not the architect's): random links (to /proc, /dev, `..`, absolute, relative, mixed) and words in 9 PATH values; truth = this process chdir'd to the gate folder, first executable file that is `samefile` as the shell; plan = `plan_gate` with the process cwd elsewhere; seeds 101-103 x 400 and 201-206 x 700 layouts | 0 bypasses over 2,101 routes to the shell (180+177+193+307+305+287+336+318+308) |
| documented limits CONFIRMED as limits (each ran the marker, rc 0 `pass`): a copy of dash, a hard link of dash, `env ./lsh` (wrapper handed a link), `python3 -c os.system`, `perl -e system`, `flock FILE -c`, a shell copy named `ksh93` (outside the 14 names) | limits, not defects: all listed in the module docstring "NOT detected" and design row r56/l01-l05 |

## Mutants (one batch, 76 mutants of gates.py; fresh `python -B -m pytest -x tests/test_gates.py` process per mutant, PYTHONHASHSEED=0, four tar copies that include `.gitignore`, `skills/`, `.claude/`, with `references/` symlinked, PYTHONPATH pointing at the copy; every mutant verified a real non-empty diff against the original, 0 no-ops)
73 KILLED. The three that survived (SURVIVED, `677 passed`):
- M09 `if links > 40` -> `> 400`; M10 -> `> 39`. Equivalent: I built chains to /bin/sh of 30, 38, 39, 40, 41, 45 links and `Popen` of each: 30 ran (rc 7), 38 and above `OSError 40 ELOOP`. The kernel's own limit is below the plan's 40, so no chain the kernel can run is accepted or refused differently.
- M26 `base = _walk(os.path.join(cwd, entry))` -> unwalked join. Equivalent: the next line walks `os.path.join(base, word)` over the same components, so the PATH entry is walked anyway.
Killed set covers: both `..` checks, every walk step (`.`, `..`, islink, opaque, budget direction, absolute/relative target, reversal), `_opaque` equality/prefix/each root, runner-cwd vs gate-cwd joins (word and entry), isfile/X_OK/walked candidate/defpath, name set/resolved name/runners/wrappers (all, skip-first, base)/lower/.exe/split, shell-gate inversion, allow-shell, metachar `|` and first-char, `=`, `-`, NUL, argv length, empty argv0, cwd isdir/fence/passing, guard, fail-open, plan-all-first, exit code, env scrub, tail/redaction, timeouts, SIGHUP, schema checks. No ordering mutant exists in the batch (no set iteration decides an outcome); the 40-seed PYTHONHASHSEED sweep of the unmutated tree passed 40/40.

## Defects
None. Observations (each set aside with the line opened):
- observation: design row 12 says a gate whose cwd is under `/dev` (such as `/dev/shm/x`) is refused for a bare name. Real CLI: `--root /`, cwd `/dev/shm`, argv `["ls"]` is accepted (rc 0, pass). Cause: gates.py `_resolve` joins an ABSOLUTE PATH entry onto cwd with `os.path.join(cwd, entry)`, which drops cwd, so the cwd is only examined for relative or empty PATH entries. This is the safe direction (exec of an absolute entry does not depend on cwd, as the matrix `pwd` control confirms) but the design sentence overstates the false positive; the docstring does not repeat it. Not a bypass.
- observation: `env ./lnk-to-shell`, copies, hard links, `python -c`, `flock -c` run the marker. Declared limits, see the confirmation row.
- observation: black's "Python 3.11 cannot parse code formatted for Python 3.15" warning is pre-existing.

## Next step
Orchestrator may proceed with C9 rev 3c (commit and PR). Still a speed bump, not a sandbox: it covers the 70-row matrix, the fuzz and the 76 mutants here, not the absence of a further mismatch.
