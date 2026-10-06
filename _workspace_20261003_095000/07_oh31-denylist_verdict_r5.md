UPHELD 41 / REJECTED 0 / UNVERIFIED 0 — round 5 (second extra round Daniel authorised, scoped to A40-A42; clean)

# Adversarial verdict: OH31 sensitive-path denylist (revision 5)

- **Audited file:** `_workspace/07_oh31-denylist_design.md` (revision 5). Authority List A1-A42. A30 is withdrawn and not counted, so 41 claims.
- **Prior verdicts read:** r1-r4. In r4, A40 was rejected for two reasons: symlink targets were not charged, and `scan=` broke T41. I did not trust the claimed fixes, and I re-judged A40, A41 and A42 from scratch. Audited 2026-10-02 with fresh context. Reference pin: `references/openharness` HEAD = 9b2efd795c6a (MIT).
- **Probe method (read-only).** I built my own simulation from the design text alone, in `scratchpad/r5/`, not from the architect's `sim5.py`:
  - `sp5.py` follows the Interfaces/Behaviour text:
    - `Scan`, plus a `_SCAN` ContextVar and `call_scope` (only the opener resets);
    - `realpath_bounded` with one directory fd, `os.stat`/`os.open`/`os.readlink` with `dir_fd`, `O_RDONLY|O_DIRECTORY|O_NOFOLLOW`, a deque, a charge of 1 per popped component (root, cwd prefix and symlink-target components included), `MAX_SYMLINKS = 40`, and lexical appending after a missing component;
    - `sensitive_rule`, which matches lexical forms first.
  - `patch5.py` re-executes `safety.py` with the rev-5 edits in the real module's namespace:
    - `_sp` alias;
    - `sensitive` threaded through;
    - `call_scope` in `_check(depth=0)` and around `_guard`'s body;
    - the path-key branch;
    - `_check_value` → `check_command(value, policy)` left unchanged.
  - Mutants are selected with `MUT=`: `pathresolve` (rev 4), `nocap`, `lstatwalk`, `globalscan`, `noreset`, `nestedreset`, `opath`.
  - Runtime: Python 3.11.15 (`.venv`), `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`. Fixtures live under `scratchpad/r5/fx`.
  - Repo writes: `find -newer <stamp>` over the repo is empty apart from this file.
- **Spot-checked unchanged rows (5+):**
  - A1, A2, A9, A11, A12, A13: `checker.py:14-33`, `:84-98` and `query.py:1026-1032` were re-read and match.
  - Re-run in the simulation:
    - A15: all 5 nested and POSIX-only cases → `sensitive-path`.
    - A21: all 8 pinned allowlist cases → `sensitive-path` via `check_command`, `make_guard` and `_both`.
    - A34: the stripping cases are denied; `notes.txt.` → `None`.
    - A38: the 3 cases are denied; `env -C /workspace` → `None`.
    - A39: the 2 cases are denied; the 3 must-pass cases → `None`.

## Claims

| id | verdict | cited | found (±5) | reason |
|---|---|---|---|---|
| A1-A19, A21-A29, A31-A39 | UPHELD (carried; spot-checked as above) | checker.py / query.py / NET-NEW | as in r4 | Byte-identical to rev 4 |
| A20 | UPHELD (carried), **test-plan fix required** | NET-NEW | — | The claim holds: with `os.stat` patched to raise, `{"path": "/workspace/ok.txt"}` → `sensitive-path`. **But two of its verifications are stale under rev 5** (see Contradiction 1). They fail loudly against a correct build, so they are not silent passes. The fix is mechanical, as with r4's row 439 |
| A30 | WITHDRAWN | — | — | not counted |
| A40 | **UPHELD (changed)** | NET-NEW | — | Every attack is now bounded (table below): worst 0.071 s, against 17-18 s in rev 4. The budget charges the cwd prefix (`nx/a` with a 9-component cwd charges 12), the root (`/nx/a/b` → 4) and symlink-target components (a link with a 51-component target → 62). Patched budget 10: `/a/b /c/d /e/f` → `None`; adding `/g/h` → `path-budget`. Shared budget: 2,500 paths plus a 500-word command → `path-budget`, and each alone → `None`. Lexical forms are matched before any walk: at budget 0, `cat ~/.ssh/id_rsa` and `{"path": "/root/.aws/x"}` → `sensitive-path`, while `cat ./ok` → `path-budget`. A credential word after budget exhaustion is still denied (`path-budget`), and placed first it gives `sensitive-path`. TOCTOU is listed (line 428). A36 two-call swap: `(None, None, None)` → `(sensitive-path ×3)` for `check_rule`, the guard command and the guard path |
| A41 | **UPHELD (new)** | NET-NEW; tests/test_modes.py:555-556 | stub `lambda value, policy=None: ""` | Six suites, 3 runs: **294 passed, 5 skipped** each time (15.78-15.81 s), T41 included. Whole `tests/`: **677 passed, 9 skipped**, identical to the unpatched baseline (677/9). Attacks: see the A41 table below. All isolation mutants are killed |
| A42 | **UPHELD (new)**, notes | NET-NEW | — | **Equivalence:** `realpath_bounded == os.path.realpath` on 80,000 paths (two seeds × 20,000 × relative and absolute), **0 differences**, 0 budget denials. The fixture has relative, absolute and dangling links, `a/up → ..`, `x → y/..`, symlink→symlink→dir (`s2s2 → s2s/z`), absolute-to-relative chains (`link3`), `..` through a symlink (`a/b/c/home/../z`), a link through a file (`viafile → file/x`) and `root → /`. On 9 named cases where a naive normpath walk differs from realpath, the bounded walk agrees with realpath on all 9. **O(1) per component:** a 1,000-level tree takes 0.057-0.071 s for 30 or 2,000 path arguments, against 0.49-0.63 s for the whole-prefix `lstat` mutant and 0.42-4.93 s for `Path.resolve`. **Opens only directories:** a spy on `os.open` saw 180 opens over the FIFO, device and `/proc` cases. All 180 carried `O_DIRECTORY` and none was writable. `open(fifo, O_RDONLY\|O_DIRECTORY\|O_NOFOLLOW)` fails with `ENOTDIR` in 10 µs, so a swap between stat and open cannot block. No fd leaks over 1,000 walks. Notes (not counted) are in Contradictions 4 and 5 |

## Bounded-walk attacks (judge fixtures; best/worst of 3; rev 5 vs mutants)

| attack | rev 5 | `pathresolve` (rev 4) | `nocap` | `lstatwalk` |
|---|---|---|---|---|
| 500-link chain, `cat ./c0` | 0.030/0.032 `path-budget` | 0.81/0.93 `None` | 0.030 `path-budget` | 0.019 `path-budget` |
| chain, 20 spellings (483 chars) | 0.029/0.031 `path-budget` | **18.39 `None`** | 0.035 `path-budget` | 0.020 `path-budget` |
| chain, 20 path args | 0.031 `path-budget` | **17.41 `None`** | 0.032 `path-budget` | 0.028 `path-budget` |
| flat 1,300 links: 1 word / 11 path args | 0.031 / 0.037-0.041 `path-budget` | 1.32 / 13.16 `None` | 0.031 / 0.030 `path-budget` | 0.022 / 0.019 `path-budget` |
| 1,000-level tree: 4 spellings / 30 args / 2,000 via `L` | 0.021 `None` / 0.057-0.071 / 0.057-0.070 `path-budget` | 0.11 / 0.42-0.48 / **4.93** | ≈ rev 5 | 0.13 / **0.49-0.64 / 0.57-0.63** |
| `x/up → ..`: 50 links / 39 links | `path-budget` / `None` (0.5 ms) | `None` / `None` | **`None`** / `None` | `path-budget` / `None` |
| loop `a → b → a` (path / command) | `path-budget` (0.2 ms) | `sensitive-path` (RuntimeError, fail closed) | `path-budget` (0.035-0.040 s, via budget) | `path-budget` |
| `s → .`, `s/`×41 | `path-budget` | `None` | **`None`** | `path-budget` |
| 4,095-char relative target `./`×2047: 1 link / 9 spellings | `None` / `path-budget` (3 ms) | `None` / `None` | same | same |
| 40-link / 41-link chain | `None` / `path-budget` | `None` / `None` | `None` / **`None`** | `None` / `path-budget` |
| 100,000-entry directory, 200 lookups | 0.009 `None` | — | — | — |
| FIFO as a path arg and command word (`./p`, `./p/x`, `./pd/..`), `/dev/zero`, `/dev/tty`, `/dev/sda`, `/proc/self/fd/0`, `/proc/kmsg` | < 0.5 ms, `None`, never blocked (alarm 10 s not hit) | — | — | — |
| stale or slow mount | **not simulated**: no FUSE or NFS here. `fstatat` on a hung mount blocks exactly as `lstat` in `Path.resolve` did, so this is not a regression. The design makes no hang-free claim | | | |

## A41 ContextVar attacks

| attack | result |
|---|---|
| Sequential `guard_tool_call` × 2, 180 distinct 51-component paths each | `None`, `None`. `globalscan` → `path-budget` ×2. `noreset` → `path-budget` ×2 |
| Sequential `check_rule` at budget 6,000: 96 distinct 51-component words, 9,881 chars | `None`, `None`. `noreset` → `path-budget` |
| 2 threads × 20 calls, released by a `Barrier` | all `None`, and `current_scan()` is `None` after. `globalscan` → all `path-budget`. `noreset` → mixed `None` and `path-budget` |
| asyncio, 2 tasks × 10 calls interleaved with `await` | all `None` (the guard is synchronous, so no interleaving inside a call) |
| Nested guard from a callback (stubbed `check_command` calls `guard_tool_call` inside `_guard`) | The inner call reuses the outer `Scan` (same object) and does not reset it. `current_scan()` is `None` after the outer call. Effect: more sharing, so more denials only |
| Exception mid-call (`segment_rule` raises; `sensitive_rule` raises) | `check-failed` for the guard command, the guard path and `check_rule`. `current_scan()` is `None` after each |
| `nestedreset` mutant | The shared case (2,500 paths + 500 words) → `None`, so it is **killed** |
| Generator holding `call_scope()` across `yield` | Its `Scan` is visible to the caller while it is suspended (standard ContextVar semantics), and is reset on `close()`. Not reachable: `_guard` and `_check` are plain functions. Not counted |
| T41 `test_empty_string_denial_blocks`, unmodified | passes 3/3 (4/4 counting a targeted run) |

## Mutation targets 13 and 14 (would the named tests kill them?)

- **Unbounded walk** (`Path.resolve` plus a string charge): **killed**. The chain, flat and deep tests return `None` in 0.8-18 s, or exceed 0.25 s. The 41-link test → `None`. The loop → `sensitive-path`, not `path-budget`.
- **Symlink cap removed:** **killed** by the 41-link test (`None`), plus `up`×50 and `s→.`×41. **The design's text is half wrong here** (Contradiction 2): the loop case still gives `path-budget` under this mutant, via the component budget, in 0.035 s.
- **Whole-prefix `lstat` walk:** **killed** by the deep-tree cases (0.49-0.64 s against the 0.25 s limit, a 2× margin). The chain and flat cases do not kill it.
- **Budget leaks between calls** (module-global `Scan`, no reset, reset in a nested scope): **killed** by the sequential, command-form and thread tests, and the nested reset by the shared-budget case.

## Timing (interleaved on/off, 7 each, min; two full runs)

- **Worst increment:** +0.041 s (`DIRS*18 cat`). Next: 1,500 `./N` at +0.034/+0.039, then `echo DIRS*17/18` at +0.021/+0.023. All other vectors are ≤ +0.013. Limit 0.1 s.
- **Single-level worst:** 0.053 s (limit 0.25). **Absolute worst:** 0.296 s (limit 0.5).
- **Rows 529/530/531/532:** `path-budget` / `path-budget` / `path-budget` / `None`, as stated.
- **Existing linear test,** 6 runs: worst 0.074-0.109 s (limit 0.25); first-19 0.466-0.693 s (limit 1.0).

## Contradictions between sections

1. **Stale fail-closed tests (A20, mutation 2), fix required.** Rev 5 no longer calls `Path.resolve`, but these places still assume it:
   - test plan line 649 ("patch `Path.resolve` → `/workspace/ok.txt` denied");
   - line 648 / Behaviour 354-355 ("NUL → ValueError in `resolve`");
   - the A20 evidence;
   - mutation 2's kill list;
   - Dependencies (`pathlib`).

   Simulated rev 5 gives: patched `Path.resolve` → **`None`**, and `{"path": "/workspace/a\x00b"}` → **`None`**. `/workspace` does not exist here or on CI, so the walk turns lexical before the NUL and makes no syscall. That agrees with `os.path.realpath`, so it is correct per A42. Both tests fail against a correct build, and the plan then has **no test that kills mutation 2 (fail open)**. The NUL bypass is harmless: a NUL after a missing or non-directory component cannot reach an existing credential. **Fix:**
   - put the NUL under an existing directory (`str(tmp_path) + "/a\x00b"`, giving `ValueError` from `os.stat` → `sensitive-path`);
   - patch `os.stat` (or `_sp.realpath_bounded`) to raise `OSError` instead of `Path.resolve`. Simulated: → `sensitive-path`.

   **Builder warning:** never reintroduce `Path.resolve` to make the old test pass. Mutation 13 would catch it.
2. Mutation 13's sentence "remove the `MAX_SYMLINKS` check → … the 41-link and loop cases no longer give `path-budget`" is wrong for the loop: it still gives `path-budget` via the budget. The mutant is still killed by the 41-link case. Wording only.
3. The A35 authority row (carried from rev 4) still says "(ii) best-of-3" and "suites 294 passed in 6 of 7 runs". The rev-5 test plan says interleaved 7 each, and 3/3 clean. The test plan governs. Not counted.
4. **A42 equivalence is wider than what is proven (unlisted false positive).** The walk enters directories with `O_RDONLY`, which needs read permission, while the kernel and `realpath` need only search (`x`) permission. With DAC override dropped (`capsh --drop=cap_dac_override,cap_dac_read_search`) and a mode-0111 directory `d`:
   - `realpath_bounded("d/k/id_rsa")` raises `PermissionError`, so the call fails closed. `{"path": "d/notes"}` (harmless) → **`sensitive-path`**, while `realpath` resolves fine.
   - The `opath` mutant (`O_PATH|O_DIRECTORY`) matches realpath and gives `d/notes` → `None`, while still denying `d/k/id_rsa` (`d/k → ~/.ssh`).

   On this box (root) and in a root container this is invisible. On a non-root host, paths through someone else's search-only directory are denied. **Not a bypass under the literal spec** ("any other exception → `sensitive-path`"). It **would become one** if a builder mapped `EACCES` to "missing → lexical" to copy `islink` (simulated reasoning: `chmod 111 d` hides `d/k → ~/.ssh` from the walk, while `cat` can still traverse). Recommend:
   - `O_PATH` on Linux, or listing it under Known false positives;
   - a test (skipped as root): x-only `d` with `d/k → $HOME/.ssh`, and `d/k/id_rsa` must be denied.
5. **Platform honesty.** Line 427 states that the walk relies on POSIX `*at` calls and that hosts are Linux-only. That is honest, but it does not say what Windows does.
   - If `os.O_DIRECTORY` is referenced at import, `sensitive_paths` (and so `safety`) fails to import on Windows: a loud fail-closed.
   - If it is referenced lazily, `dir_fd` raises `NotImplementedError`, and every pathish word is denied through the fail-closed path.

   Either way it fails closed. One sentence saying so would close it. On macOS, `dir_fd` works but `MAXSYMLINKS` is 32, so the guard allows 33-40-link paths that the kernel rejects anyway, which is harmless. Not counted.
6. **The `_sp` alias is consistent:** Files, Interfaces lines 263-264, Behaviour and the test plan all say `_sp.<name>`. Tests that `monkeypatch.setattr(sensitive_paths, …)` hit the same module object (simulated: the `RESOLVE_COMPONENT_BUDGET` patch and the `sensitive_rule` patch both take effect). The r4 line-218 contradiction is resolved: `check_rule` creates nothing.
7. Known false positives are honestly listed for `path-budget`, the 40-link limit, loops and the 16,384-component limit. The search-only directory case (note 4) is the one unlisted false positive.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 3 (OH31 add-on) | N/A no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no data split |
