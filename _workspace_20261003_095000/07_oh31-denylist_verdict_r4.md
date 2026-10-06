UPHELD 38 / REJECTED 1 / UNVERIFIED 0 — round 4 (the extra round Daniel authorised; REJECTED > 0, so this goes to Daniel)

# Adversarial verdict: OH31 sensitive-path denylist (revision 4)

- Audited file: `_workspace/07_oh31-denylist_design.md` (revision 4). Authority List A1-A40. A30 is withdrawn and not counted, so 39 claims.
- Prior verdicts read: r1, r2, and r3 (`_verdict_r3.md`: UPHELD 34 / REJECTED 4, which were A31, A35, A36 and A37). I did not trust the claimed fixes. I re-judged every changed or new row (A20, A31, A35, A36, A37, A40) from scratch.
- Audited 2026-10-02, fresh context. Reference pin: `references/openharness` HEAD = 9b2efd795c6a (MIT).
- **Probe method (read-only).**
  - I used my own simulation, `scratchpad/r4/sim.py`. It is derived from my r3 module, not from the architect's `scratchpad/sim/sim4.py`.
  - It implements rev 4 as specified:
    - a `Scan` holding `cmd` and `path` memos, plus `components_left`, read from the module constant at construction;
    - a budget charged as `s.count("/")+1` before each resolve, returning `path-budget` when exceeded;
    - one `Scan` per `_guard` call, threaded into the command branch as `_check_value` → `check_command(value, policy, scan=scan)`, looked up as a module global as in the real code;
    - otherwise, a `Scan` created by `_check` at depth 0.
  - Mutants are switched by environment variables.
  - Runtime: `.venv` Python 3.11.15, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`.
  - Repo writes: none. `find -newer <stamp>` over the repo is empty apart from this file.
- **Spot-checked unchanged rows (5 of 33):**
  - A1, A2, A3, A10, A11, A12 and A13: the cited checker.py and query.py lines were re-read and match.
  - Re-run in the simulation:
    - A15: all 5 nested and POSIX-only cases give `sensitive-path`.
    - A21: all 8 pinned allowlist cases give `sensitive-path` via `check_command`, `make_guard` and `_both`.
    - A34: the stripping cases are denied; `notes.txt.` is allowed.
    - A38: the 3 wrapper cases are denied; `env -C /workspace` is allowed.
    - A39: the 2 drive-relative cases are denied; the 3 must-pass cases are allowed.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A19, A21-A29, A32-A34, A38, A39 | UPHELD (carried; 5 spot-checked, see above) | checker.py / query.py / NET-NEW | as in r3 | Byte-identical to rev 3 |
| A20 | UPHELD (changed) | NET-NEW | safety.py:11, :491-494 | NUL path → `sensitive-path`. Patched `Path.resolve` raising → `sensitive-path`. Patched `sensitive_paths.sensitive_rule` raising → `check-failed`, both for `check_command("ls ./x")` and for `{"path": "ok.txt"}`. The r3 one-word fix is applied |
| A30 | WITHDRAWN | — | — | not counted |
| A31 | UPHELD (changed), notes | NET-NEW | client.py:149 `check_command(shlex.join(self._server.command))` | The opt-out works: kube launch line with `sensitive_paths=False` → `None`; `rm -rf /` with the opt-out is still denied; `cat ~/.kube/config` with the default is denied. I built the AST scan from the spec text alone (`scratchpad/r4/ast4.py`). On today's tree plus the planned client.py line: **0 violations, allowed 1**. All 11 negatives are flagged, by (a) kw, (b) str, (c) attr or import. All 3 positives are clean. **Notes (not counted):** my own evasions get through: `importlib.import_module("master_finhub.tools.safety")._check(...)`; rebinding `t = safety; t._check(...)`; `kw["sensitive_"+"paths"]=False; check_command(c, **kw)`; `from master_finhub import tools; tools.safety._check(...)`; star import then `segment_rule(...)`. All of these are deliberate obfuscation. The scan is a tripwire against accidental opt-outs, and the claim lists 11 named spellings, not completeness. A second `sensitive_paths=False` in client.py passes the per-file scan but is caught by the tree assertion (allowed count must be exactly 1). `src/` has no relative imports today |
| A35 | UPHELD (changed), **one-line test-plan fix required** | NET-NEW | — | Every listed vector is within its limits (table below): the worst same-host increment is +0.073 s, below the 0.1 limit; single-level worst is 0.080 s; the absolute worst is 0.341 s. Existing linear test: worst 0.078-0.120 s, first-19 0.545-0.557 s. **But test-plan row 439 is wrong.** It reads `"echo " + " ".join("./$CLIENT_A_DIRS/"*18 + str(i) …)` and expects `path-budget`, but it gives **`None`**. With `CLIENT_A_DIRS = "/usr/lib:"*25` (225 chars), each word expands to 228 × 18 = 4,104 chars, which is over `PATH_MAX_CHARS`. Such words are never resolved and never charged. The architect's sim used host `$PATH` (223 chars → 4,068), which hid this. Fix: `*17` (simulated: `path-budget`). Not a rejection, for the same reason as r3 A20: the test fails at build time rather than passing silently, and the fix is mechanical. The suite figure in the evidence ("294 passed in 6 of 7") is wrong; see A40 |
| A36 | UPHELD (changed) | NET-NEW | — | Two-call symlink flip on rev 4: `(None, sensitive-path)` for `check_rule`, for the `guard_tool_call` command form and for the path form. Mutant 11 (a module-level `Scan`/memo) gives `(None, None)` on all three, so it is **killed**. `lru_cache` on `sensitive_rule` raises `TypeError` (`Scan` is an unhashable dataclass), so every call fails closed, which is killed by every must-pass case. Memo count for `"bash -c "*3 + "./a "*100`: rev 4 = 1, mutant 10 (per-`_check`) = 15, so it is **killed**. A `Scan` is created per call, and the call after a `path-budget` denial gets a fresh budget. The threading mechanism it shares with A40 is rejected below; the per-call and never-across-calls claim itself holds |
| A37 | UPHELD (changed) | NET-NEW | checker.py:91 `fnmatch.fnmatch(candidate_path, pattern)` | Equivalence over the full 18-pattern list: every backticked string in the design through `match_forms(resolve=False)`, plus each pattern made concrete with and without a trailing `/`, plus a hand set (`[`, `]`, `*`, `\n`, `ß`, `İ`, upper case, trailing `/`), plus 200k random strings. 142,380 distinct forms, **0 divergences** between `_PATTERN_RE.match` and `any(fnmatchcase)`. The patterns contain no `[]`. Both sides are case-sensitive on the same casefolded input, and `translate` uses `(?s:…)\Z` per alternative, so the result is equivalent by construction |
| A40 | **REJECTED** | NET-NEW | tests/test_modes.py:555-556 | **(1) The budget does not bound `resolve` work once symlinks exist.** It charges the components of the *string*, but `Path.resolve` (Python 3.11 `posixpath._joinrealpath`) walks every symlink target as well, with no limit on symlinks followed. A model can plant the symlinks in an earlier allowed call (`ln -s`). Simulated with synthetic files under a temp dir: 500 chained symlinks, each target `"x/../"*700 + "c{i+1}"`. Results: `cat ./c0` takes **0.87 s**, charged **2**. A **483-char** command of 20 spellings (`./c0`, `././c0`, …) takes **17.75 s**, charged 230, rule `None`. The same 20 as path arguments take **17.36 s**. A flat variant (1,300 symlinks to `x/..`×800, 11 path arguments) takes **12.3 s**, charged 7,491 of 16,384. A 10,000-char command scales this to minutes. The guard is synchronous in `AgentLoop._execute` (loop.py:221) and has no timeout. The evidence "a component budget bounds the new rule's work at about 0.04 s per call" is false. **(2) The specified threading breaks an existing test, deterministically.** `_guard` → `_check_value` → `check_command(value, policy, scan=scan)`. `tests/test_modes.py::test_empty_string_denial_blocks` (T41) monkeypatches `safety.check_command` with `lambda value, policy=None: ""` and asserts that `guard_tool_call(... {"command": "ls"}) == ""`. With `scan=` passed, the stub raises `TypeError`, `_guard` fails closed, and the result is `check-failed` text. Failed 3/3 runs (below). With `_check_value` calling `check_command(value, policy)` without `scan=`, it passes. So the Proof claim "unchanged and still pass" and the "294 passed" evidence do not hold for the design as written. **Fix:** (1) Replace `Path.resolve` with a bounded walk that charges every component it visits, including symlink-target components, to `components_left`. Cap symlinks per resolve at 40 (Linux `MAXSYMLINKS`) and fail closed with `path-budget`. Add the chained-symlink vector as a test (< 0.25 s, `path-budget`). (2) Share the `Scan` with the command branch without changing the `check_command(value, policy)` call shape. For example, set a `contextvars.ContextVar` in `_guard` that `_check(depth=0)` reads. Keep T41 green unmodified. (3) A35 row 439: `*17` |

## Budget attacks (requested)

| attack | result |
|---|---|
| Exhaust the budget so that a legitimate call is refused | The budget is per call, and the model writes the whole call, so it can only deny its own call. `_both` runs separate `_guard` calls, so parent and child do not share a budget. The next call starts fresh (simulated: `None`). This is fail-closed and honestly listed under "Known false positives" (`path-budget`, about 2,700 six-segment paths). Acceptable |
| A credential word checked only after the budget runs out | The call is still denied. Budget then `~/.ssh/id_rsa` → `path-budget`. Budget then a bare `id_rsa` → `path-budget`. `~/.ssh/id_rsa` first → `sensitive-path`. `segment_rule` returns the first non-None result, so nothing after exhaustion is allowed. No skip |
| Words counted after resolve, or expanded length miscounted | The charge uses the expanded `s`, before resolve. Correct for symlink-free strings. Words over 4,096 expanded are not resolved, not charged, and get the lexical form only (see row 439) |
| Symlink-expanded paths | **Not counted, and this is unbounded.** See A40 (1) |
| Per top-level call, reset between calls | Yes. `default_factory` runs per `Scan`, and one `Scan` exists per `_guard`, `check_rule` or `check_command` call. Patched budget 10: `cat ./a/b ./c/d ./e/f` → `None`; adding `./g/h` → `path-budget` |
| Shared budget across path and command keys | 2,500 paths plus a 500-word command → `path-budget`, in either key order. Each alone → `None`. Under the split-`Scan` mutant → `None`, so it is killed |
| Mutant 12 (no budget / reset per word) | The 437/438 vectors, the 2,000-element path list and the shared case all lose `path-budget`. Killed |

## Rev-4 timings (judge, this box, best/worst of 5; inc = best(on) − best(off))

| vector | on | off | inc | rule |
|---|---|---|---|---|
| `"bash -c "*3 + "./a "*2490` | 0.141 / 0.151 | 0.136 / 0.155 | +0.004 | None |
| `"bash -c "*3 + "~ "*4980` | 0.181 / 0.260 | 0.172 / 0.248 | +0.008 | None |
| `"eval "*3 + "./a "*2490` | 0.140 / 0.226 | 0.155 / 0.207 | −0.015 | None |
| `"bash -c "*3 + "a "*4980` | 0.285 / 0.341 | 0.218 / 0.321 | +0.067 | None |
| `"cat " + "$CLIENT_A_PAD"*700` | 0.009 / 0.011 | 0.008 / 0.011 | +0.001 | path-too-long |
| `"bash -c "*3 + "cat " + "$CLIENT_A_PAD "*600` | 0.108 / 0.121 | 0.105 / 0.129 | +0.003 | None |
| 1,500 distinct `./N` | 0.043 / 0.049 | 0.008 / 0.010 | +0.035 | None |
| row 437 `cat` + `$CLIENT_A_DIRS/`×18 words | 0.060 / 0.066 | 0.008 / 0.009 | +0.052 | path-budget |
| row 438 same, `bash -c` ×3 | 0.072 / 0.097 | 0.179 / 0.183 | −0.107 | path-budget |
| **row 439 `echo ./$CLIENT_A_DIRS/`×18** | 0.027 / 0.047 | 0.007 / 0.007 | +0.020 | **None (plan says path-budget)** |
| judge r3 `$PATH/`×18 single / `bash -c`×3 | 0.080 / 0.101 ; 0.060 / 0.060 | 0.007 ; 0.100 | +0.073 ; −0.041 | path-budget |
| path list 2,000 × `$CLIENT_A_DIRS` near-limit | 0.056 / 0.081 | — | — | path-budget |
| path list 2,000 legit 6-segment paths | 0.108 / 0.110 | — | — | None |
| existing ADVERSARIAL worst / first-19 (3 runs) | 0.078-0.120 / 0.545-0.557 | — | — | — |

The `bash -c ×3 "a "` increment of +0.067 s is real: about 150k memo lookups. It sits within 0.033 s of the 0.1 s limit on a noisy box. Expect occasional flakes in check (ii).

## Existing suites under the simulation (open risk 5)

`test_safety`, `test_modes_sub`, `test_mcp_client`, `test_docker_engine`, `test_workspace`, `test_modes`, three runs:

- Run 1: **1 failed, 293 passed, 5 skipped** (15.75 s). `FAILED tests/test_modes.py::test_empty_string_denial_blocks`.
- Run 2: same (15.72 s).
- Run 3: same (15.74 s).
- Base code without the simulation: 294 passed, 5 skipped.

The failure is deterministic, not load-related. The design's handling ("not captured; if it recurs, boundary-qa names the test") is **not adequate**. Its 6-of-7 clean runs mean its simulation did not route `_guard`'s command branch through the module-level `check_command` with `scan=`, which is what the spec requires. I cannot tell whether the architect's unnamed loaded-box failure was this test.

## Contradictions between sections

1. Test plan row 439 expects `path-budget`, but Behaviour gives `None` (4,104 > 4,096, so the word is not resolved). Fix: `*17`. Counted under A35 as a fix note.
2. Proof ("existing suites unchanged and still pass") and the A35/A40 evidence ("294 passed") conflict with the Interfaces and Behaviour threading `check_command(value, policy, scan=scan)`. T41 fails 3/3. Counted under A40.
3. A40 evidence ("bounds the new rule's work at about 0.04 s per call") conflicts with "Does not cover", which lists no symlink-cost limit. Counted under A40.
4. Not counted: Interfaces line 218 says "check_rule creates a fresh Scan", but line 219 says `_check(depth=0)` creates it. Inside `check_rule` and `check_command`, the parameter `sensitive_paths: bool` shadows the module `sensitive_paths`. Building per line 218 (`sensitive_paths.Scan()` in `check_rule`'s body) would raise `AttributeError` on a bool, and every command would become `check-failed`. Follow line 219, or rename the import (`from master_finhub.tools import sensitive_paths as _sp`).

## Escalation (extra round, REJECTED > 0)

| id | judge position | architect position |
|---|---|---|
| A40 | The component budget charges string components, not `resolve`'s walk. Planted symlink chains make a 483-char, 230-component call take 17.75 s with result `None`, and it scales to minutes. Separately, threading `scan=` into `check_command` breaks the existing T41 test deterministically, 3 of 3 runs. | The budget bounds work at about 0.04 s per call because resolve cost is linear in components (0.8-2.5 µs each). The suites pass in 6 of 7 runs; one unnamed failure happened on a loaded box. |

The fix is local: a bounded realpath walk that charges symlink-target components and caps symlinks at 40, a ContextVar (or equivalent) instead of a new `check_command` keyword, and `*17` on row 439. The pattern list, the hook point, the ordering, the memo semantics and the AST tripwire are all UPHELD.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 3 (OH31 add-on) | N/A no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no data split |
