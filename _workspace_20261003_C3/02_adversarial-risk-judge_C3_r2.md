TOTALS: UPHELD 38 / REJECTED 1 / UNVERIFIED 0 — round 2/3

# Adversarial verdict: C3 secret-shape redaction (revision 1)

- Audited file: _workspace/02_strategy-architect_C3.md (revision 1), `## Authority List` A1-A37, plus the r1 substance rows S1 and S2, the N1-N7 decisions and the X20 equivalence dispute.
- Audited: 2026-10-03
- Changed claims re-audited this round: A12, A27 (CHANGED r1), and the new rows A32-A37. A1-A11, A13-A26 and A28-A31 are carried forward as UPHELD, as the launch prompt instructs.
- Prior verdict: _workspace/02_adversarial-risk-judge_C3_r1.md (UPHELD 30 / REJECTED 3).
- Simulation: my own scratch tree at `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c3j2/full`.
  - It is a copy of the repo at 18d61a6, with `references/` symlinked and read only.
  - `secret_scan.py` (design lines 240-337) and `tests/test_secret_scan.py` (design lines 415-715) were extracted by line range from the design file. The `loop.py` and `client.py` hunks were applied as written.
  - All four files are byte-identical (`cmp`) to the architect's scratch tree.
  - Every run used `python -B` and `PYTHONDONTWRITEBYTECODE=1`. Each mutant ran in a fresh temp copy.
  - Nothing was written into the repo except this file.
- Totals: 37 Authority rows plus S1 and S2 (both now closed) make 39 rows. The R10 ReDoS is counted once, under A36. It does not have its own S row.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1-A11, A13-A26, A28-A31 | UPHELD (carried) | as r1 | as r1 | Byte-identical to revision 0, per the launch prompt |
| A12 | UPHELD | NET-NEW | — | The look-ahead is gone. R8 is `\bsk-[A-Za-z0-9_-]{20,}\b` with a Python digit test (`_DIGIT.search(text, start, m.end())`). My timings at 1 MB: `"sk-"` repeats 0.068 s, `"sk-ant-"` 0.058 s, `"sk-abc-"` 0.067 s, `"sk-ant-"` followed by 25 dashes 0.075 s, and 41,666 adjacent digit-bearing `sk-` tokens 0.130 s. At 4 MB every `sk` input took under 0.43 s. The mutant oai-lookahead-restored was killed by a 120 s timeout. My J10 (digit searched after the token) and J11 (`[1-9]`) were both killed |
| A27 | UPHELD | NET-NEW | — | The `redact()` hunk applies exactly. The only changed call site is `call_tool` (scratch `client.py:363`). `stderr_tail` (:147), `_fail` (:183) and JSON-RPC errors (:308) keep the default `mcp_shapes=True`. Both S2 cases now give `id=[REDACTED:aws-access-key]` and `k=[REDACTED:anthropic-key]`, and `redact(GHP, ["ghp_FAKE"])` gives `[REDACTED]`. `tests/test_mcp_client.py` passes unmodified. mcp-sequential-values-first and mcp-sequential-shapes-first were both killed. My J15 (`mcp_shapes` default False) was killed by `test_redact_env_value_and_bearer` |
| A32 | UPHELD | NET-NEW | — | I tested 11 positives, each with 14 non-ASCII neighbours on the left, right and both sides: é, ß, CJK, Arabic-Indic digit, fullwidth 0, NBSP, U+3000, ZWSP, combining acute, `。`, ², Ⅰ, a math-bold letter and ʰ. That is 462 inputs with **0 leaks**. All negatives (base64 PNG, `QUJDAKIA…`, SHA/UUID/ULID, PUBLIC KEY and CERTIFICATE headers) still pass. No rule uses `\d`, and every key class is already ASCII, so a fullwidth digit was never a token character. Case folding changes only exotic folds (K/ſ), which no real header uses. **One loss of coverage:** `\s` in R2 and R3 no longer matches any non-ASCII space (U+00A0, U+2002-2009, U+202F, U+3000, U+2028, U+1680, U+0085, and also ASCII `\x1c`-`\x1f`). Revision 0 caught all of these. Does-not-cover #5 states this, so it is not counted. See N11. no-ascii-all and no-ascii-jwt were both killed |
| A33 | UPHELD | NET-NEW | — | **Merge oracle:** I fuzzed 100,000 random mixtures of the 12 secret forms, noise and glue (5 seeds) and compared `apply_spans(merge_spans(...))` with an independent union. Result: **0 mismatches, 0 idempotence failures, 0 labels outside the rule ids**. **Hand cases:** <br>• value inside shape → shape label <br>• shape inside value → `[REDACTED]` <br>• identical spans → value wins <br>• tie at the same start: input order (`merge_spans([(3,9,'b'),(3,4,'a')])` gives `(3,9,'b')`) <br>• a value bridging two keys (`"0000 ghp_"`) gives one span <br>• an empty or 1-3 character value is ignored <br>• duplicate values are handled <br>• a value equal to `[REDACTED]` or to `REDACTED:bearer-token` gives no re-entry <br>• a value made of regex metacharacters is escaped <br>• the client output is idempotent and passes the loop rescan with `()`. <br>**Complexity:** sort-based, not quadratic. 1M shuffled disjoint spans merge in 0.74 s, 1M chained overlaps in 0.67 s, 1M nested in 0.22 s. `client.redact` on 3.8 MB of AWS keys with 5 values took 1.34 s. Killed: no-merge, labels-from-raw, tie-later-wins, keep-not-excluded, and my J03 (end not `max`), J04 (later tag wins), J05 (tie by tag text), J09 (`pos = start`), J12 (labels in merge order) and J18 (unsorted). Survived and harmless (no leak): J01 merges touching spans; J02 merges only overlaps of 2 or more characters, because `apply_spans` slices `text[pos:start]` to `''`. See N12 |
| A34 | UPHELD | NET-NEW | — | The `if is_error:` gate is gone, and the call is `redact(text, self._secrets(), mcp_shapes=is_error)`. `McpTool.run` (scratch :428-432) raises `McpToolError(result.text)` on an error, using already-redacted text. Killed: mcp-success-no-values, mcp-shapes-always, and my J06 (values passed only when `is_error`). **Not pinned:** "and the C3 table on successful results". My J16 (table spans added only when `mcp_shapes`) survives the full `test_secret_scan.py` plus `test_mcp_client.py`. In practice the loop rescans every `McpTool` result, so this gap matters only to direct `call_tool` callers. See N9 |
| A35 | UPHELD | NET-NEW | — | `Bearer "…"` gives `Bearer "[REDACTED:bearer-token]"`. Re-scanning that output gives `()`. bearer-noquote was killed |
| A36 | **REJECTED** | NET-NEW | — | **The claim is false for R10 (jwt). The scan is quadratic on dash-joined `eyJ` runs, and the 13-input timing test cannot see it.** `\beyJ[A-Za-z0-9_-]{10,}\.…` starts at every `-eyJ`, because `-` is a non-word character, so `\b` holds. `-` is also in the segment class, so every start scans to the end of the run looking for `.` and fails. Measured for R10 alone: `"eyJ-"` repeats take 0.033 s at 10 KB, **3.2 s at 100 KB** and **29.6 s at 300 KB**, and the scan did not finish within 300 s at 1 MB (extrapolated about 330 s at 1 MB and about 1.5 h at 4 MB = `MAX_LINE_CHARS`). `"eyJaaaaaaaaaaaa-"` repeats take 0.78 s at 100 KB and timed out at 60 s at 1 MB. Adding `"eyJ-"` to `ADVERSARIAL` makes the **unmutated** design time out at 120 s (my J21). Does-not-cover #12 ("at most 0.12 s per MB … every rule's prefix") is therefore also false. This is the same failure class as r1 A12: a fetched page or a file read can stall `_execute`. My r1 timing set used dotted JWT chains only and missed this. **Fix (verified):** change R10's leading `\b` to `(?<![A-Za-z0-9_-])`, so there is at most one start per run. Measured: 0.29 s at 4 MB on both inputs, and all 188 design tests pass unchanged. Add `"eyJ-"` (and `"eyJaaaaaaaaaaaa-"`) to `ADVERSARIAL`, and correct #12. The only coverage given up is a JWT glued after `-`, which belongs with the glued cases in #5. Every other rule stays linear: 38 inputs at 1 MB took ≤0.13 s each, and 22 inputs at 4 MB took ≤0.52 s (scan) or ≤0.83 s (`client.redact`, values only) |
| A37 | UPHELD | NET-NEW | — | On the run path a tool returning `bytes` raises `TypeError('cannot use a string pattern on a bytes-like object')`, and an `int` raises `TypeError("expected string or bytes-like object, got 'int'")`. **Neither message carries the payload.** The resume path (`rerun`, idempotent tool) behaves the same: the claim snapshot is saved, no tool message is stored, there is no leak, and `pending_calls` is intact, so the checkpoint is not corrupted. A later resume raises the same error deterministically. Nothing swallows it silently: `server/app.py:147` streams only the class name, and `evals/runner.py:160` records the error as `TypeError: …` and fails the case. loop-str-coerce was killed |
| S1 (r1) | UPHELD (closed) | — | — | Resolved by A32 |
| S2 (r1) | UPHELD (closed) | — | — | Resolved by A27 and A33. Both cases, plus `GHP`/`ghp_FAKE`, are tests |

## Decisions on r1 notes and the X20 dispute

| item | ruling | evidence |
|---|---|---|
| N1 | accepted | Spot-checked bearer-15 (X08), mcp-colon-only (X12) and jwt-lead (X22): all killed. The minimum-length and context cases are in the test file |
| **X20** | **accepted as equivalent** | For R5 and R6 the class `[A-Za-z0-9_]` is exactly ASCII `\w`, so a greedy run always ends next to an ASCII non-word character or the end of the text, and `\b` holds on the first try. I compared finditer spans with and without the trailing `\b` on 300,000 random strings per rule (alphabet: word characters, `-`, `.`, é, CJK, a combining mark, space, newline and the prefixes). Result: **0 differences under `re.ASCII`**, and about 17,500 differences per rule in Unicode mode. So the equivalence depends on `re.ASCII`, and the no-ascii-github-token mutant guards that. gh-trail survived in my run, as expected |
| N2 | accepted | P8 gives 0/0 with `LC_ALL=C.UTF-8`, and the Python fallback gives 0 |
| N3 | accepted | The extended P7 gives 0. Planted `xoxb-`, `sk-ant-` and `AKIA` literals each give 1. A planted `sk-proj-…` gives 0 under P7 but is caught by P7b (`('openai-key',)`). P7b on the real test file gives `()` |
| N4 | accepted | See A35 |
| N5 | accepted | See A34. The table-on-success half is unpinned (N9) |
| N6 | accepted | Pinned, and listed in #11 |
| N7 | accepted | See A37 |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C3 | N/A: no pricing, returns or backtest | N/A | N/A | N/A | N/A | N/A: touches no eval scoring, verifier or data split (design :107) |

## Re-run of the design's proof

| check | design expects | I got |
|---|---|---|
| P1 | 188 passed | `188 passed in 1.20s` |
| P2 | before 895/10; after 1083/10 | real tree (unmodified): `895 passed, 10 skipped`. Scratch tree with C3: `1083 passed, 10 skipped`, using the repo `.venv`. My first run gave 1 failure because my tar excluded the nested `tests/fixtures/…/references` fixture. After restoring it, the run was clean |
| P3 | mypy --strict, 38 files | `Success: no issues found in 38 source files` |
| P4 | ruff and black clean | `All checks passed!`; `66 files would be left unchanged.` |
| P5 | loop 2 lines, client 3 lines | loop :16, :220; client :32, :115, :116 |
| P5b | 11 | 11 |
| P6 | 2 | 2 |
| P7 / P7b | 0 / `()` | 0 / `()`. Both can fail on a planted literal (see N3) |
| P8 | 0 | 0, 0, and 0 from the fallback |
| P12 | slowest 0.13 s at 1 MB; 0.43 s at 4 MB; `client.redact` 0.86 s | 13 design inputs: ≤0.13 s at 1 MB. Other rules: ≤0.52 s at 4 MB (`x-mcp-key: ` repeats), and `client.redact` ≤0.83 s. **R10 is not linear: see A36** |
| Stale numbers | — | The design no longer says "35 mutants", "113" or "1008". "49" appears only as the r0→r1 line-count history (:14). The mutation table has 75 rows, 72 killed plus 3 equivalent, which matches :735. There are 20 NEGATIVES, which matches A30 |

### Mutants

- **Architect's mutants spot-checked: 18, all behaving as stated.** 17 were killed:
  - oai-lookahead-restored (120 s timeout)
  - no-ascii-all
  - mcp-sequential-values-first
  - loop-site
  - bearer-15
  - mcp-success-no-values
  - mcp-shapes-always
  - loop-str-coerce
  - tie-later-wins
  - no-merge
  - labels-from-raw
  - keep-not-excluded
  - mcp-sequential-shapes-first
  - bearer-noquote
  - no-ascii-jwt
  - mcp-colon-only
  - jwt-lead

  gh-trail (X20) survived, as the design says it should (equivalent).
- **My own mutants: 19.** I ran them against `test_secret_scan.py` plus `test_mcp_client.py`.
  - **Killed (12):**
    - J03 merge end not `max`
    - J04 later tag wins on overlap
    - J05 tie broken by tag text
    - J06 values only on error results
    - J07 redaction moved into `_drive` only (killed by the resume test)
    - J08 the resume path calls `_run_tool` (killed by the resume test)
    - J09 `apply_spans` sets `pos = start`
    - J10 digit searched after the token
    - J11 `[1-9]`
    - J12 labels in merge order
    - J15 `mcp_shapes` defaults to False
    - J18 spans not sorted
  - **Survived (6):**
    - J01 touching spans merged (harmless)
    - J02 1-character overlap not merged (harmless: no leak)
    - J13 value minimum 5 instead of 4 (the 4 predates C3)
    - **J14 `re.escape` removed**: security-relevant, see N9
    - J16 table spans on successful client results (see A34)
    - J17 R1 `\Z` → `$` (it only leaves a trailing newline)
  - **Equivalent (1):** J19.
  - The design bar ("drop a rule or the call site must be killed") is still met, so the survivors are not counted.

## Notes (not counted; fix in the same revision if cheap)

- **N8 Header rules swallow a following header.** R2's and R3's token class contains letters plus `. = / - ~ +`. A header glued by one of those characters to the next header lets the first match consume the second header's name, and the second token leaks:
  - `x-mcp-key: V1/x-mcp-key: V2` → `x-mcp-key: [REDACTED:mercury-mcp-key]: V2…`
  - `Bearer securities=Bearer <16+ token>` → the real token is visible.

  This was already the behaviour in revision 0, and it needs contrived glue. Either list it in Does-not-cover, or stop the class before a header with `(?:(?!Bearer\s|x-mcp-key)[A-Za-z0-9._~+/=-]){16,}`; time that change before adopting it.
- **N9 Test gaps in new client code.**
  - J14: dropping `re.escape` survives. A real value such as `ab+cd/ef==` would then fail to match itself and leak. Add one value with metacharacters to `test_mcp_values_and_shapes_are_merged_on_the_original_text`.
  - J16: add an `AWS` echo to the successful stub test so the table-on-success half of A34 is pinned.
- **N10 Pre-existing quadratic `SECRET_SHAPES` JWT.** The alternation `eyJ[A-Za-z0-9_-]{5,}\.…` has no anchor at all. On `"eyJ"*N` it takes 4.2 s at 100 KB, and `"eyJ-"` takes 6.5 s at 100 KB. It runs on `_fail` messages and on JSON-RPC error messages of up to 4 MB.
  - This is not C3's regression. C3 correctly keeps it off successful results.
  - It is the same one-token fix as A36, and C3 already rewrites `redact()`. Raise it with Daniel, or fold it in.
- **N11 Non-ASCII whitespace after `Bearer` / `x-mcp-key`.** `(?u:\s)+` inside the `re.ASCII` pattern restores revision 0's whitespace coverage and keeps the ASCII `\b`. Verified on Python 3.11: NBSP, U+3000 and tab are caught, and `éBearer X` still matches. #5 discloses the gap, so this is optional.
- **N12 Edge pins for `merge_spans`.** Add one touching-span case (`AWS + "-post"` with value `-post` → `[REDACTED:aws-access-key][REDACTED]`) and one 1-character-overlap case, so J01 and J02 are killed and the "union of overlaps" wording is exact.
