TOTALS: UPHELD 42 / REJECTED 0 / UNVERIFIED 0 — round 3/3

# Adversarial verdict: C3 secret-shape redaction (revision 2)

- Audited file: _workspace/02_strategy-architect_C3.md (revision 2), `## Authority List` A1-A40, plus the decisions on N8, N10 and N11.
- Audited: 2026-10-03
- Changed claims re-audited this round: A36 (CHANGED r2) and the new rows A38, A39 and A40.
- Carried forward as UPHELD: A1-A35 and A37, plus S1 and S2 (closed in r2).
  - I diffed the Authority List against the architect's saved revision 1 (`scratchpad/c3/design_r1.md`). The only differences are the A36 row and the added rows A38-A40, as the architect states.
  - `secret_scan.py` differs from revision 1 only in R10's anchor and the 3-line comment above it.
- Prior verdicts: `_r1.md` (UPHELD 30 / REJECTED 3) and `_r2.md` (UPHELD 38 / REJECTED 1: A36).
- Simulation: my own tree at `scratchpad/c3j3/full`.
  - It is a tar copy of the repo at 18d61a6, including `.git` and the nested `tests/fixtures/.../references` fixture, with the top-level `references/` symlinked and read only.
  - I extracted `secret_scan.py` (design lines 305-407) and the test file (design lines 486-810) by line range and applied the `loop.py` and `client.py` hunks. All four files are byte-identical (`cmp`) to the architect's `scratchpad/c3/repo`.
  - Every run used `python -B` with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.
  - I wrote nothing into the repo except this file. `git status --porcelain` returns 0 lines.
- Totals: 40 Authority rows plus S1 and S2 make 42 rows.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A35, A37 | UPHELD (carried) | as r1/r2 | as r1/r2 | Byte-identical to revision 1 (diff above) |
| S1, S2 (r1) | UPHELD (closed) | — | — | As in r2 |
| A36 | UPHELD | NET-NEW | — | **My own sweep found no super-linear growth on any C3 path** (details in "ReDoS sweep" below). Worst result for each C3 path, in seconds at 1 MB and then 4 MB: <br>• `redact_secrets`: 0.13 and 0.49 <br>• successful-result `client.redact` with no values: 0.13 and 0.49 <br>• the same path with values: 0.23 and 1.01 (`"Bearer  "+16a+":"` with value `aaaa`). The design reports 0.937 s here, so my input is 8% slower; the 2 s bound at 1 MB holds with about 9× margin. <br>**The timing test is sound.** On the design the slowest parameter takes 0.31 s for both calls together, against a bound of 2 s for each call, so it will not flake. On my restored-`\b` mutant the timing test kills it on its own: `[eyJ-]` took 324 s and `[eyJaaaaaaaaaaaa-]` 81 s, and both failed the assert. The test times `redact_secrets` and `redact(…, mcp_shapes=False)` separately. The repo has no pytest-timeout, so a regression costs about 7 minutes before it fails. **Test gap (N13, required):** the look-behind class is pinned only for `-` and letters. See N13 |
| A38 | UPHELD | NET-NEW | — | **Linear.** R10 alone on `eyJ_`, `eyJ0` and `eyJ-` takes 0.002 s at 100 KB, and the per-rule sweep's worst for R10 is 0.019 s at 1 MB and 0.077 s at 4 MB. <br>**Only `-` changed.** I compared old `\beyJ` and new look-behind spans on 200,000 random strings. There were 11 differences, and all 11 were matches that start right after `-`. Under `re.ASCII` the look-behind equals `\b` plus "not `-`". <br>**Still redacted:** the JWT alone, inside JSON, after `=`, `:`, `'`, `"`, space, newline, `(`, `[`, `/` and `.`, in `?token=`, `#id_token=`, `Cookie: jwt=`, `<t>…</t>` and `x-auth-token: `, at the start and at the end of the text, and after `Bearer ` (labelled bearer-token). The same is true for `redact_secrets` and both client paths. <br>**Now missed (new false negatives):** `-eyJ…`, `--eyJ…`, `Bearer-eyJ…`, `token-eyJ…`, `X-Token-eyJ…`, `Authorization: Bearer-eyJ…`. MCP error text still catches all of them through the unanchored `SECRET_SHAPES`. <br>**I accept the stated trade-off.** `Bearer-<token>` is not valid Authorization syntax, because RFC 6750 requires whitespace, and real `Bearer <jwt>` is still caught by R2. A JWT glued to a key name by `-` is the same kind of miss as the `_`-glued and letter-glued cases that were accepted in r1. It is disclosed in #5 and pinned (`"-"+JWT`). `Bearer%20eyJ…` was already missed by revision 1 (`0` is a word character) and falls under #4 (encoded forms). <br>**Mutants:** jwt-restore-b and jwt-lookbehind-word-only were both killed by the pin. |
| A39 | UPHELD | NET-NEW | — | I tested 13 values containing `+ ( ) [ ] \ . * ? ^ $ \| { }` (one combines all of them). Each was redacted literally, twice in the same text, through both the success path and the error path, with 0 failures. Decoys such as `v1x2y3` for value `v1.2.3`, `aaab` for `a*b*` and `5z` for `\d\w` were left unchanged. mcp-no-escape is killed by the `ab+cd/ef==(x)` assert |
| A40 | UPHELD | NET-NEW | — | <br>• `AWS+"-post"` with value `-post` (touching) gives `[REDACTED:aws-access-key][REDACTED]`. <br>• With value `0-po` (1-character overlap) it gives `[REDACTED:aws-access-key]st`. <br>• With value `00-p` it gives `…ost`. <br>• `merge_spans` keeps `(0,5),(5,9)` as two spans and merges `(0,5),(4,9)` into `(0,9,'a')`. <br>merge-touching and merge-skip-1char are both killed by `test_touching_spans_stay_separate_and_overlaps_merge` |

## Decisions on N8, N10, N11

| item | ruling | evidence |
|---|---|---|
| N8 | accepted (Does-not-cover #5) | The behaviour is unchanged from revision 0. It needs contrived glue, and it is now disclosed with both examples |
| N10 | **accepted, with one correction to the wording** | **Is the stall on a path C3 introduced? No.** It is in `SECRET_SHAPES.finditer` inside `redact()` (scratch `client.py:114`). That line runs only when `mcp_shapes=True`, which means the four pre-existing error call sites: `stderr_tail` :147, `_fail` :183, JSON-RPC error :308, and `call_tool` :363 when `isError`. Before C3 the same regex ran on the same four sites as `SECRET_SHAPES.sub`. The new successful-result path (`mcp_shapes=False`) is linear: 0.007 s at 100 KB on `eyJ`. <br>**Worst case is unchanged.** At 100 KB, before and after C3: `"eyJ"*N` 4.36 / 4.36 s and `"eyJ-"*N` 3.25 / 3.25 s. From 10 KB to 30 KB to 100 KB, `eyJ` goes 0.042, 0.38, 4.36 s, which is quadratic. Extrapolated to a 4 MB error message, that is about 2 hours. I did not run it. <br>**Correction:** "not worsened" is true for the worst case only. Because C3 matches on the original text, it removes protection that the old sequential replace gave by accident. Example: `"eyJaaaaa"*N` with configured value `aaaa`, error path, 100 KB: **0.002 s before C3, 1.59 s after**. The old `replace` split the run with `[REDACTED]`, so the scan stayed short. The attacker's best input (`eyJ` alone) was already this slow, so the risk level does not change. The one-token follow-up the design names (`(?<![A-Za-z0-9_-])` on that branch) should be done soon, not left on the backlog |
| N11 | accepted (follow-up) | Disclosed in #5. The fix was verified in r2 |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C3 | N/A: no pricing, returns or backtest | N/A | N/A | N/A | N/A | N/A: touches no eval scoring, verifier or data split |

## ReDoS sweep (independent; I did not use the architect's `sweep.py`)

Scripts: `scratchpad/c3j3/jsweep.py`, `jstage2.py` and `n10.py`.

**Stage 1: 53,336 units.**
- 47,336 grammar units built from each rule's own literal pieces:
  - R1: BEGIN/END fragments and PGP;
  - R2: `Bearer` with spaces, tabs, newlines and quotes, in several cases;
  - R3: `x-mcp-key` with `:`, `=`, quotes and spaces;
  - R4: `AKIA`, `ASIA` and `AKI`;
  - R5 and R6: `gh?_` and `github_pat_` runs;
  - R7 and R8: `sk-ant-` and `sk-`;
  - R9: `xox[abprs]-` and `xoxo-`;
  - R10: `eyJ`, `eyJ.`, `eyJ-`, `eyJ_`, partial segments, `eyJxxxxxxxxxx.xxxxxxxxxx.` and `eyJ.eyJ.`.
- Each piece was combined with 21 separators (`'' space \t \n - _ . : = " ' / + ~ [ , é U+3000 NUL a 0`):
  - piece then separator, and separator then piece;
  - the piece doubled;
  - a flood of 8 separators;
  - a fill of 11 class characters at the minimum length minus 1, at the minimum, and at the minimum plus 3.
- 6,000 random grammar units biased toward the literal pieces and `[REDACTED…]`.
- Each unit was tiled to 10 KB and 100 KB and run through `redact_secrets`, the successful-result client path with no values, the same path with values (`aaaa`, `0000`, `ab+cd/ef==(x)`, `eyJ-`, `Bearer`), and the client error path (`mcp_shapes=True`, at 10 KB and 30 KB).

**Stage 2: 450 suspects.** These were the top 120 per target by absolute time plus the top 120 by growth ratio. I re-timed them on a quiet machine, best of 2, at 100 KB and 1 MB, then took the top 10 to 4 MB.

**Extra checks:**
- 30 random non-periodic strings of 1 MB;
- 19 hand-built backtracking maximisers of 1 MB each:
  - a PEM with no END followed by near-miss END lines;
  - `[A-Z ]*` floods;
  - whitespace floods after `Bearer` and `x-mcp-key`;
  - quote and `=` floods;
  - JWT inputs with no first dot, a missing third segment, dash-only third segments, dot chains and dash-dot runs;
  - `sk-` dash floods, `sk-ant-` runs, `ghp_` underscore runs, `xoxb-` dash runs, and `AKIA` plus 15 characters.

| target | worst 1 MB (s) | worst 4 MB (s) | worst 1 MB / 100 KB ratio | verdict |
|---|---|---|---|---|
| R1 private-key (own pattern) | 0.025 | 0.095 | 5.5 | linear |
| R2 bearer-token | 0.042 | 0.176 | 7.8 | linear |
| R3 mercury-mcp-key | 0.021 | 0.085 | 4.9 | linear |
| R4 aws-access-key | 0.013 | 0.096 | 7.3 | linear |
| R5 github-token | 0.010 | 0.054 | 1.7 | linear |
| R6 github-pat | 0.010 | 0.035 | 1.2 | linear |
| R7 anthropic-key | 0.015 | 0.036 | 7.0 | linear |
| R8 openai-key | 0.014 | 0.054 | 1.3 | linear |
| R9 slack-token | 0.011 | 0.039 | 1.9 | linear |
| R10 jwt | 0.019 | 0.077 | 4.9 | linear |
| `redact_secrets` | 0.129 | 0.494 | 15.4 | linear (see note) |
| `client.redact` ok, no values | 0.130 | 0.485 | 15.5 | linear (see note) |
| `client.redact` ok, values | 0.231 | 1.011 | 13.1 | linear |
| `client.redact` error (`mcp_shapes=True`) | — | — | quadratic on the `eyJ` family only | pre-existing `SECRET_SHAPES` (N10) |
| random 1 MB ×30 / hand maximisers ×19 | ≤0.153 / ≤0.201 | — | — | linear |

Notes on the table:
- **The two ratios just above 15 are timer noise.** At 100 KB the time is about 7 ms, so a few milliseconds of noise moves the ratio a lot. I re-timed both units at 250 KB, 1 MB and 4 MB (best of 3):
  - `BEGIN PRIVATE KEY-----   :`: 0.018, 0.071, 0.281 s;
  - `ghs_`+19A+`_`: 0.016, 0.066, 0.243 s.

  Each step is 4× the input and 4× the time, which is linear.
- No unit took more than 0.232 s at 100 KB on any C3 path in Stage 1.

## Re-run of the design's proof

| check | design expects | I got |
|---|---|---|
| P1 | 202 passed | `202 passed in 5.36s` |
| P2 | before 895/10; after 1097/10 | Real tree, unmodified: `895 passed, 10 skipped`. Scratch tree with C3, `.git` copied and nothing deselected: `1097 passed, 10 skipped` |
| P3 | 38 files clean | `Success: no issues found in 38 source files` |
| P4 | clean | `All checks passed!`; `66 files would be left unchanged.` |
| P5 / P5b / P6 | 2+3 lines / 11 / 2 | loop :16, :220; client :32, :115, :116 / 11 / 2 |
| P7 / P7b / P8 | 0 / `()` / 0 | 0 / `()` / 0. **The test file holds no complete credential.** The scanner and an extra loose grep find only `sk-runner-…` (from `task-runner`), the kebab and `xoxo` negatives, the `eyJhbGciOiJIUzI1NiJ9` header-only negative and the timing units. `SECRET_SHAPES` finds only "Bearer securities" |
| Stale numbers | — | "98", "301" and "188" appear only as the from-values in the r2 count lines (:61-62). "113", "1008", "1083", "35" and "75" do not appear. The r1 history row (:77) keeps "13 inputs / 0.12 s / 0.43 s" as history. Counts match the file: 202 cases, 25 `ADVERSARIAL` entries, 103 and 325 lines |

### Mutants

- **Architect's mutants spot-checked: 13, all killed as stated.**
  - jwt-restore-b
  - jwt-lookbehind-word-only
  - jwt-lead
  - mcp-no-escape
  - mcp-table-error-only
  - merge-touching
  - merge-skip-1char
  - oai-lookahead-restored (180 s timeout)
  - no-ascii-all
  - mcp-sequential-values-first
  - loop-site
  - bearer-15
  - mcp-shapes-always

  jwt-restore-b is also killed by the timing test on its own (see A36).
- **My own mutants: 19.** I ran them against `test_secret_scan.py` plus `test_mcp_client.py`.
  - **Killed (12):**
    - K04 look-behind of `-` only
    - K07 first segment `{9,}`
    - K08 `apply_spans` drops the tail
    - K09 no `\s*` after `[:=]` in R3
    - K10 `mcp_shapes=not is_error`
    - K11 value span one character short
    - K12 R7 moved after R8
    - K14 R9 class without `-`
    - K15 merge end not `max`
    - K17 redaction only on the `_drive` path
    - K18 `mcp_shapes` defaults to False
    - K19 values only on error results
  - **Survived (7):**
    - **K01 look-behind without `_`**
    - **K02 look-behind without digits**

      Both reopen the exact r2 quadratic: R10 alone takes **3.23 s** on `eyJ_` and **3.19 s** on `eyJ0` at 100 KB. See N13.
    - K03 look-behind with `.` added. This loses `.eyJ…` coverage, and no positive pins it.
    - K05 look-behind plus `\b`. Equivalent.
    - K06 R10 trailing `\b` dropped. Harmless: it only extends the span over trailing dashes.
    - K13 labels in alphabetical order. Harmless: the order test uses aws/github, where table order and alphabetical order agree.
    - K16 `sorted(spans)` (ties by end, then tag). Harmless: it changes only which tag names a tie, and nothing leaks.

## Notes (not counted)

- **N13 Look-behind completeness is not pinned (fix before build; test-only).** In `ADVERSARIAL` and the pins, `-` is the only non-letter character of R10's look-behind class that is pinned.
  - Removing `_` or the digits from `(?<![A-Za-z0-9_-])` brings back the quadratic scan.
  - Those mutants pass all 224 tests.
  - This is the same class of escape as rounds 1 and 2, now for a future edit.
  - Add `"eyJ_"` and `"eyJ0"` to `ADVERSARIAL`, or add `"_"+JWT` and `"0"+JWT` to the negative pins (or both).
  - Optionally add a `"."+JWT` positive, which kills K03.
  - The runtime-builder should treat this as a build condition. It changes no behaviour.
- **N10 follow-up is time-sensitive.** On MCP error text the quadratic is about 2 hours at the 4 MB line cap. It predates C3, but it is the same one-token fix, and C3 removes one accidental mitigation (see the N10 row).
- **N14 cosmetic.** The design says (:42) that all ten per-rule winners were added to `ADVERSARIAL`. That is not literally true:
  - the winners in the 4 MB table (:30, :31, :33) are not the `ADVERSARIAL` entries for R2, R3 and R5;
  - the list comment says "worst unit per rule at 1 MB".

  Align the wording. No behaviour is affected.
