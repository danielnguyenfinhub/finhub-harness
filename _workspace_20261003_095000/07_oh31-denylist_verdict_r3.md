UPHELD 34 / REJECTED 4 / UNVERIFIED 0 — round 3/3 (final, so this escalates to Daniel)

# Adversarial verdict: OH31 sensitive-path denylist (revision 3)

- Audited file: `_workspace/07_oh31-denylist_design.md` (revision 3). Authority List A1-A39. A30 is withdrawn and not counted, so 38 claims.
- Prior verdicts read: `07_oh31-denylist_verdict.md` (r1) and `07_oh31-denylist_verdict_r2.md` (r2: UPHELD 32 / REJECTED 3, which were A33, A35 and D5). I re-judged every changed and new row from scratch. I did not trust the claimed fixes.
- Audited 2026-10-02, fresh context, round 3/3.
- Reference pin: `references/openharness` HEAD = 9b2efd795c6a (MIT).
- **Probe method (read-only).** I wrote a scratchpad module outside the repo (`scratchpad/r3/sim.py`). It monkeypatches `safety._State`, `segment_rule`, `_inline_rule`, `_check_tokens`, `_check`, `check_rule`, `check_command` and `_guard`, and the `check_command` names bound in `mcp/client.py` (`sensitive_paths=False`) and `docker_engine.py`.
  - It implements the rev-3 rule exactly as Behaviour specifies: caps, expand, drive split, segment stripping, `normpath`, resolve only when pathish and the expansion is ≤ 4,096, casefold, `/`-prefix, trailing-slash forms, one combined regex, a memo per top-level call, and the rule as the first statement of `segment_rule`.
  - Mutants are switched by an environment variable.
  - Runtime: `.venv` Python 3.11.15, 4 cores, host `PATH` = 223 chars. I ran with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` (the existing `.pytest_cache` dates from 11:22 and is not mine). Nothing in the repo was written. I checked this with `find -newer`.
- **Existing suites under the simulation.** I ran `test_safety`, `test_modes_sub`, `test_mcp_client`, `test_docker_engine`, `test_workspace` and `test_modes`: **294 passed, 5 skipped** on all three runs. This matches the architect's numbers.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD (spot-checked) | checker.py:14 ; :18 | :14 "always denied regardless of permission mode or user config"; :18 `SENSITIVE_PATH_PATTERNS` | — |
| A2 | UPHELD (spot-checked) | checker.py:20 | `"*/.ssh/*"` | — |
| A3 | UPHELD (carried) | checker.py:22 ; :23 | `.aws/credentials`, `.aws/config` | — |
| A4-A8 | UPHELD (carried; lines re-seen) | checker.py:25-33 | gcloud :25, azure :27, gnupg :29, docker :31, kube :33 | — |
| A9 | UPHELD (spot-checked) | checker.py:84 ; :105 | :84 starts the sensitive check, which returns a denial at :92; :101 deny list; :105 allow list | — |
| A10 | UPHELD (spot-checked) | checker.py:169 | `return (normalized, normalized + "/")` | — |
| A11 | UPHELD (spot-checked) | query.py:1029 ; :1032 | `Path(value).expanduser()`; `return str(path.resolve())` | — |
| A12 | UPHELD (carried) | query.py:1026 | `for key in ("file_path", "path", "root"):` | — |
| A13 | UPHELD (spot-checked) | checker.py:91 | `fnmatch.fnmatch(candidate_path, pattern)` | — |
| A14 | UPHELD (carried) | NET-NEW | — | — |
| A15 | UPHELD (re-run) | NET-NEW | safety.py:285, :299 | All six nested-payload cases and three POSIX-only cases return `sensitive-path` in the simulation |
| A16 | UPHELD (carried) | NET-NEW | — | — |
| A17 | UPHELD (changed: cross-reference) | NET-NEW | — | Under mutant 9 (no casefold), `~/.SSH/ID_RSA`, `cat ~/.SSH/ID_RSA` and `cat ~/.Aws/Credentials` all pass, so the mutant is killed. The cross-reference is now correct |
| A18 | UPHELD (carried) | NET-NEW | — | — |
| A19 | UPHELD (changed) | NET-NEW | — | Under the resolved-only mutant, both named killing tests pass, so both kill it: `{"path": "C:\\Users\\client_a\\.aws\\credentials"}` and `type C:\Users\client_a\.ssh\id_rsa` (the resolved form ends in `\id_rsa`, not `/id_rsa`). The `_netrc` carve-out is now correct |
| A20 | UPHELD, **one-line fix required** | NET-NEW | safety.py:11 "Any internal error fails closed"; :491-494 | The claim holds. The verification names a function the design no longer routes through. Nothing on the guard path calls `is_sensitive_path`: `_guard` and the segment rule both call `sensitive_rule`. A test that patches only `is_sensitive_path` to raise therefore gets `None` from `check_command("ls ./x")` and fails red. Test-plan line 398 ("and the same for `is_sensitive_path`") has the same problem. Fix: in A20, say "patched `sensitive_rule` raising", and drop the `is_sensitive_path` parenthetical. Why this is not a rejection: the bad test shows up red at build time, not as a silent pass, and the fix is one word with no design choice. Compare A31 |
| A21 | UPHELD (re-run) | NET-NEW | safety.py:519, :523, :528-535 | All nine pinned allowlist cases return `sensitive-path` through `check_command`, `make_guard` and `_both` |
| A22 | UPHELD (re-run) | NET-NEW | — | The `cat ~/.aws/credentials_acct_001` denial contains none of the forbidden substrings |
| A23-A29 | UPHELD (carried) | NET-NEW | — | — |
| A30 | WITHDRAWN | — | — | not counted |
| A31 | **REJECTED** | NET-NEW | client.py:70-72, :149 (match) | The opt-out itself is sound: `check_command(shlex.join(("kube-mcp","--kubeconfig","~/.kube/config")), sensitive_paths=False)` returns `None` in the simulation. **The AST scan in the verification cannot pass as written.** Assertion (c) bans the names `_check`, `_check_tokens`, `_inline_rule`, `segment_rule` and `_State` as `ast.Name` or `ast.Attribute` in every module outside safety.py. Today's tree already breaks it: `sandbox/workspace.py:120/146/149` (`Workspace._check` / `self._check`) and `orchestration/message_bus.py:322/373` (`self._check`). I ran the spec'd scan over `src/` and it flags both files. It also under-catches. Assertion (a) only looks at calls whose callee is spelled `check_command`/`check_rule`/..., so it misses `from ...safety import check_command as cc; cc(c, sensitive_paths=False)`, `functools.partial(check_command, sensitive_paths=False)` and `getattr(safety, "check_rule")(c, sensitive_paths=False)` (all probed: not caught). It does catch `=0`, `**{...}`, `_check(...)` and `safety._check(...)`. **Fix:** (a) flag the keywords `sensitive_paths`/`sensitive`/`memo` on **every** `ast.Call` outside safety.py (client.py allowed exactly once, value `False` checked with `is False`), and flag any string constant `"sensitive_paths"` outside those two files. (c) only counts names imported from `master_finhub.tools.safety`, or attributes on a name bound to that module |
| A32 | UPHELD (carried) | NET-NEW | docker_engine.py:104, :123; tests/test_docker_engine.py:93-97 | — |
| A33 | UPHELD (changed), note | NET-NEW | safety.py:26 `MAX_COMMAND_CHARS: Final = 10_000` | Closed, re-measured. All of these return `path-too-long`: `"cat "+"$PATH"*1990` in 0.009 s; the same behind `bash -c ` ×3 in 0.009 s; quoted `bash -c 'cat $PATH*1980'` in 0.007 s; `eval` ×3 in 0.008 s; `{"path": "$PATH"*819}` in 0.0004 s; `{"paths": ["$PATH"*819]*10}` in 0.0004 s; `{"command": "cat "+"$PATH"*1990}` in 0.009 s. The test-plan `$CLIENT_A_PAD` cases (path ×300, list of 10, command ×700) also return `path-too-long`, and `"/workspace/"+"a"*4000` passes. **Note (not counted):** the per-value caps do not bound the total. `{"paths": [<2,000 elements of "./"+"$PATH/"*18+str(i)>]}` (about 220 KB) takes **5.7 s** (base 0.001 s), because each element stays just under 4,096 and is resolved. The path branch has no memo, so identical elements are recomputed too. Per input byte (about 2.6e-5 s) this is within the existing guard's envelope: base `_guard` also has no total cap, and many nested worst-case commands cost the same per byte. So this is not the r2 stall. Cheap hardening: share the call memo with the path-arg branch per `_guard` call |
| A34 | UPHELD (changed) | NET-NEW | — | Under the no-strip mutant, `_netrc.`, `_netrc::$DATA`, `.git-credentials.`, `.kube\config ` and both `.ssh.\config` cases (command and path) pass, so the mutant is killed. `type ...\notes.txt.` and `/workspace/report.v1.` pass. The text fixes from r2 are applied |
| A35 | **REJECTED** | NET-NEW | tests/test_safety.py:220-232 | **The claim "the new rule adds ≤ 0.07 s to the worst nested-unquoted vectors" is false for a vector the design does not test: many distinct path-like words, each expanding to just under 4,096.** Example: `"cat " + " ".join("$PATH/"*18 + str(i) for i in range(2000))` cut to 10,000 chars (about 90 words). The memo cannot help because every word is distinct, and each word pays one `resolve` on a path of about 4 k characters with about 800 components. Measured, best/worst of 5: **single level 0.243 / 0.370 s, against 0.010 / 0.012 s today.** That is a 25-35× regression, and it exceeds the module's own 0.25 s worst-vector budget with no help from today's code. The same idea as `echo ./$PATH/...` gives 0.202 / 0.260 s (base 0.007). Behind `bash -c ` ×3 it gives **0.362 / 0.428 s against 0.137 / 0.169 s**, which **passes the new 0.5 s limit while costing 2.6× today's code**. A host env var with denser `/` makes it worse: a synthetic 4,080-char `"y/"*2040` variable gives 7.2 s, but the model cannot set env vars, so `PATH` density is the realistic case. **Also, the test-plan vector table contradicts the spec:** row `"bash -c "*3 + "cat " + "$CLIENT_A_PAD "*600` is listed as `path-too-long`, but each word expands to only 240 chars. The spec gives `None` (simulated: `None` in 0.13 s), so that test fails red against a correct build. **Fix:** (1) bound the total `resolve` work per top-level call. For example, deny `path-too-long` once the sum of expanded lengths of resolved words in one call passes a fixed budget (say 32 k), or resolve command words only when the expansion is ≤ 1,024. Fail closed, never skip silently. (2) Add the distinct-word vectors, single-level under the existing 0.25 s and nested under 0.5 s, plus the increment check described in the ruling below. (3) Correct the `$CLIENT_A_PAD "*600` expectation to `None`, or remove the spaces so it is one word that expands to 144,000 chars and gives `path-too-long` |
| A36 | **REJECTED** | NET-NEW | — | **No planned test pins "never kept across calls", and a leaking memo is a security hole.** Mutant: one module-level memo (equivalently, `functools.lru_cache` on `sensitive_rule`, which is a natural "optimisation"). It passes the memo-count test (count 1), every timing vector, all 294 existing tests, and every test-plan case. The planned symlink tests are path arguments, which are not memoised. The attack, simulated with synthetic files under a temp HOME: call 1 `cat ./notes.txt` (a regular file) returns `None`. The file is then replaced by a symlink to `$HOME/.aws/credentials`. Call 2 `cat ./notes.txt` returns `sensitive-path` under rev 3 but **`None` under the mutant**. The real rev-3 design does not leak: the memo is a local dict created in `_check(depth=0)`. Two threads running different commands 200× each got the correct, isolated results. Within one call, the key `(word, resolve)` is deterministic, because cwd and HOME are fixed for the call and `resolve` is a function of the word. So there is no in-call poisoning beyond the TOCTOU already listed. The per-`_check` memo mutant (counted 15×) is killed by the count test. **Fix:** add a two-call symlink-flip test using a command word (above), and add the mutation target "memo kept across calls / `lru_cache` on `sensitive_rule`" |
| A37 | **REJECTED** | NET-NEW | checker.py:91 (fnmatch, matches) | **The stated evidence is false under rev 3.** "The per-pattern loop fails the existing `first19 < 1.0` limit (judge: 1.45-1.62 s)" was my r2 measurement **without a memo**. With the A36 memo, a per-pattern `fnmatchcase` loop gives the following: existing linear test worst 0.08 s and first-19 0.52-0.58 s (pass); all seven new vectors < 0.5 s (worst 0.25 s); full suites 294 passed, twice. Proof calls A37 "load-bearing", and mutation 10's per-pattern half is the kill. Neither holds: that half of mutation 10 survives everything. The combined regex is a fine implementation choice, but it is not pinned by anything. **Fix:** remove "load-bearing" and the per-pattern branch from mutation 10. Restate A37 as an implementation choice, verified by an equivalence test: on every test-plan string, the regex matches exactly when `any(fnmatchcase(f, p) for p in patterns)` does |
| A38 | UPHELD (new) | NET-NEW | safety.py:216-235 `strip_wrappers` (matches) | `K=~/.aws; cat $K/credentials`, `xargs -a ~/.ssh/id_rsa echo` and `env -C ~/.aws cat credentials` return `sensitive-path`. Under mutant 8 (rule after `strip_wrappers` / `if not core`), **exactly these three** change to `None`. Every other test-plan case stays denied, including `K=~/.ssh; cat $K/id_rsa` and `sudo -u ... cat ~/.aws/credentials`, so without these three the mutant would survive. Confirmed. `env -C /workspace cat notes.txt` passes. D5 is closed |
| A39 | UPHELD (new) | NET-NEW | — | `type C:.aws\credentials`, `type C:.ssh\config` and `{"path": "C:.aws\\credentials"}` return `sensitive-path`. Under the no-split mutant exactly these three pass, so it is killed. `cat c:/x`, `cat a:b/.ssh-x` and `scp report.csv host:/tmp/` return `None`. Bypass search via the split found nothing. The split only applies to segment 0 shaped `<letter>:<text>` and only adds a boundary, never removes text. Stream stripping of `rest` happens after the split. The resolved form is computed from the unsplit expansion, so the split cannot hide a real POSIX path. Cases tried: `C:..\.aws\credentials`, `\\?\C:\...\.aws\...`, `h:~/.ssh/id_rsa`, `host:~/.ssh/id_rsa`, `a:/.ssh/id_rsa`. All denied as intended or harmless |

## Ruling on the disputed 0.5 s budget

Measured on this box, best/worst of 5. "Today" is the unmodified code (`SIM_OFF=1`); "rev 3" is the simulation.

| vector | today | rev 3 |
|---|---|---|
| `"bash -c "*3 + "./a "*2490` | 0.134 / 0.143 | 0.145 / 0.233 |
| `"bash -c "*3 + "~ "*4980` | 0.162 / 0.178 | 0.179 / 0.250 |
| `"eval "*3 + "./a "*2490` | 0.128 / 0.148 | 0.145 / 0.183 |
| `"bash -c "*3 + "a "*4980` | **0.193 / 0.252** | 0.239 / 0.291 |
| `"cat "+"$PATH"*1990` | 0.007 / 0.008 | 0.009 / 0.013 (`path-too-long`) |
| `"bash -c "*3 + "cat " + "$PATH "*1600` | 0.120 / 0.179 | 0.130 / 0.152 |
| 1,500 distinct `./N` | 0.008 / 0.009 | 0.041 / 0.043 |
| existing ADVERSARIAL, worst / first-19 (3 runs) | 0.060-0.082 / 0.36-0.47 | 0.078-0.093 / 0.50-0.60 |
| **distinct `$PATH/`×18 words, single level** (not in the design) | 0.010 / 0.012 | **0.243 / 0.370** |
| **same behind `bash -c ` ×3** (not in the design) | 0.137 / 0.169 | **0.362 / 0.428** |

**Ruling: the 0.5 s figure is a legitimate blow-up tripwire. It is not dishonest, but it is not an honest measure of the claim it is used to support.**

- **The architect's factual point is correct.** Today's code already reaches 0.19-0.25 s on `bash -c ×3 + "a "*4980`, and one of my five runs of today's code exceeded 0.25 s. A 0.25 s limit on these new vectors would be flaky for reasons unrelated to OH31.
- **It is not a loosened existing limit.** `test_adversarial_inputs_are_linear` keeps 0.25 / 1.0 unchanged, and passes under rev 3.
- **It catches the blow-ups it was built for.**
  - The no-memo mutant gives 0.58-11.5 s on the vectors. Killed.
  - The per-`_check` memo mutant is killed by the count test, not by timing.
- **Its weakness is that it is absolute and about 2× today's cost.** So it lets the new rule roughly double the scan cost without failing, and the distinct-word vector shows exactly that: 0.14 s → 0.43 s nested passes 0.5 s. It therefore does not pin A35's "adds ≤ 0.07 s".
- **What would make it honest:**
  - Keep 0.5 s as the absolute tripwire.
  - Add an increment check on the same host: for each vector, best-of-3 `check_rule(v)` minus best-of-3 `check_rule(v, sensitive_paths=False)` must be < 0.1 s. The keyword already exists, so this is host-independent and isolates exactly the new rule's cost.
  - Run single-level vectors, where today's cost is about 0, under the existing 0.25 s.

As written, it is acceptable as a tripwire but insufficient as evidence. That is part of the A35 rejection.

## Memo attack summary (requested)

| attack | result |
|---|---|
| Same word, symlink target changed between two calls (rev 3 as specified) | Denied on the second call. The memo is per call. |
| Same, with the memo kept across calls (module-level dict or `lru_cache`) | **Allowed: stale-allow hole.** No planned test catches it (A36). |
| Same word, different cwd or HOME between calls | Not reachable as specified: the memo dies with the call. Within one call, cwd and HOME are fixed. |
| Concurrent calls (2 threads × 200) | Isolated and correct. No shared state. |
| Key choice `(word, resolve)` | Sound. `resolve = _pathish(word)` is derived from the word, and `max_chars` and `sensitive` are constant per call. |
| In-call poisoning | Nothing beyond the TOCTOU already listed under "Does not cover". |

## Contradictions between sections

1. Test plan, A35 vector table: `"bash -c "*3 + "cat " + "$CLIENT_A_PAD "*600` expects `path-too-long`, but the Behaviour spec gives `None`. Counted under A35.
2. Test plan line 398 and the A20 row: patching `is_sensitive_path` has no effect on the guard path. One-line fix under A20.
3. Proof ("A37 is load-bearing"), Behaviour step 5 ("a per-pattern loop is not acceptable … failing first-19") and mutation 10 (per-pattern half) all rest on a memo-less measurement. Counted under A37.
4. Test-plan AST (c) contradicts the current tree (`Workspace._check`, `MessageBus._check`). Counted under A31.
5. Not counted:
   - The memo-count test and the fail-closed test patch `sensitive_paths.sensitive_rule` as a module attribute. They only work if `safety.py` calls it as `sensitive_paths.sensitive_rule(...)`, not via `from ... import sensitive_rule`. State the import style.
   - `PATH_MAX_CHARS` (sensitive_paths) and `MAX_PATH_ARG_CHARS` (safety) are two names for 4,096. Keep one.

## Escalation (round 3/3, REJECTED > 0)

| id | judge position | architect position |
|---|---|---|
| A31 | The specified AST scan (c) is red on today's tree (`Workspace._check`, `MessageBus._check`), and (a) misses aliased and `partial` calls. The builder would have to redesign the tripwire without an audit. | The AST scan replaces the r2 spelling test and closes `=0`, `**kwargs` and direct `_check`. |
| A35 | The claim of ≤ 0.07 s added and a linear budget is falsified. Distinct path-like words expanding to about 4 k take 0.24-0.37 s single-level (today 0.01 s), which is over the 0.25 s module budget, and 0.36-0.43 s nested (today 0.14-0.17), which passes the 0.5 s limit. One vector expectation is wrong. | The new rule adds ≤ 0.07 s on the seven measured vectors. 0.5 s is 2× the patched worst because today's code already takes about 0.2 s. |
| A36 | "Never kept across calls" has no test. A global memo or `lru_cache` mutant survives everything and gives a stale allow after a symlink flip. | One dict per top-level call, never shared, which keeps filesystem changes visible. Verified by the count test and the timing test. |
| A37 | "Load-bearing" is false once the memo exists: the per-pattern loop passes first-19 (0.52-0.58 s) and all suites, so mutation 10's per-pattern half survives. | The per-pattern loop fails first-19 (citing the judge's r2 measurement of 1.45-1.62 s). |

All four fixes are small and local (test additions or wording, plus one total resolve budget for A35). None changes the pattern list, the hook point or the ordering, all of which are UPHELD.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 3 (OH31 add-on) | N/A no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no data split |
