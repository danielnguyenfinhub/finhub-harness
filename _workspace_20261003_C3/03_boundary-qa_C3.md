RESULT: PASS (Daniel's bounded bar: zero non-equivalent under-redaction survivors across Q, N and R batches; everything else held)
Survivor split: under-redaction non-equivalent 0; equivalent 11 (gh-trail, no-ascii-0, no-ascii-1, Q18, Q24, N31, R04, R16, R29, R39, R40); over-redaction follow-ups 2 (R14, R15); label/whitespace 0

# Boundary QA, pass 4: C3 secret-shape redaction

Date 2026-10-03. Repo tree untouched (scratch runs in `.../scratchpad/qa/`, `.venv/bin/python -B`). No new mutants written (orchestrator instruction).

## Boundary table

| boundary | side A | side B | match |
|---|---|---|---|
| secret_scan.py, loop.py, client.py vs previous-pass copy (`qa/repo3`) | previous | now | `cmp` rc 0, 0, 0 (src unchanged) |
| secret_scan.py vs design block (`02_strategy-architect_C3.md` from line 304) | design | built | `diff` rc 0 |
| tests/test_secret_scan.py vs previous copy | 494 lines | 617 lines | `diff` = `22c22` (import gains `McpError`, nothing else) + pure append `494a495,617`; no existing test edited or weakened |
| git status | design 4 files | ` M loop.py`, ` M client.py`, `?? secret_scan.py`, `?? test_secret_scan.py` | match; repo root has no stray files; `git status --short references` 0 lines; `git submodule status \| grep -c '^[+-]'` 0 |
| call sites (loop `_execute`/`_run_tool`, client `redact`/`call_tool`/`_fail`/`stderr_tail`/JSON-RPC error) | design | unchanged | match (e2e and stub below) |

## Gate (command | rc | output)

| command | rc | output |
|---|---|---|
| `pytest -q -p no:cacheprovider tests/test_secret_scan.py` x5 | 0 | `289 passed in 5.89s`, `6.35s`, `5.68s`, `5.98s`, `6.23s` |
| probe: two new MCP stub tests (`-k "mcp_error_message or mcp_fail_message"`) x10 in isolation | 0 | 10 x `2 passed, 287 deselected in 0.13-0.17s` |
| probe: same two tests x5 plus the whole file under CPU load (12 busy processes on 4 cpus, load 6.26) | 0 | 5 x `2 passed ... in 0.48-0.51s`; whole file `289 passed in 20.09s` |
| probe: stub hygiene | | stub written to `tmp_path / "stub.py"` (pytest-owned); the only subprocess is `sys.executable` over stdio; `grep -nE "socket\|http\|urlopen\|requests" tests/test_secret_scan.py` no match; `ps` for `stub.py` after the runs: 0 children left |
| `pytest -q -p no:cacheprovider` (full) | 0 | `1184 passed, 10 skipped in 89.50s` |
| `mypy --strict src` | 0 | `Success: no issues found in 38 source files` |
| `.venv/bin/ruff check src tests` | 0 | `All checks passed!` |
| `.venv/bin/black --check src tests` | 0 | `66 files would be left unchanged.` |
| `bash scripts/check-harness-refs.sh` | 0 | `grep -c FAIL` 0; last lines `PASS CLAUDE.md says six-agent`, `PASS no Hangul in agents+triage`, `PASS packager exit 0` |
| `bash scripts/package-plugin.sh` on a scratch copy | 0 | `lint_harness: 0 error(s), 0 warning(s)`; three dist files written |
| P7 credential grep on tests/test_secret_scan.py | 1 (no match) | `0` |
| P7b `redact_secrets(open('tests/test_secret_scan.py').read())[1]` | 0 | `()` |
| probe: P7 and P7b on a copy with `x = "xoxb-0000-FAKEFAKE"` appended | | P7 `1`, P7b `('slack-token',)`: both fail on the planted literal |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' skills/` | 1 | no output |
| `mutq.py` (118 = design 83 + Q 35; each change real, 0 NOOP) | 0 | `TOTAL 118 killed 113 survived ['gh-trail','no-ascii-1','no-ascii-0','Q18-digit-from-m.start','Q24-client-no-value-sort']`; design 83: 80 killed, 3 survivors (gh-trail, no-ascii-0, no-ascii-1) all equivalent |
| `mutn.py` (54) | 0 | `TOTAL 54 killed 52 survived ['N31-client-no-reverse'] noop ['N50-...']` (N50 is the declared no-op control) |
| `mutr.py` (55, `test_secret_scan.py` + `test_mcp_client.py`, each change asserted real) | 0 | `TOTAL 55 killed 48 survived ['R04','R14','R15','R16','R29','R39','R40'] noop []` |
| Q23 (client minimum length 1) on a FULL tree copy (references/, .claude/ present), `pytest -q -x` | 1 (killed) | `FAILED tests/test_mcp_client.py::test_redact_env_value_and_bearer`, `1 failed, 299 passed, 5 skipped`; also killed inside mutq (`1 failed, 251 passed`) |

All 26 previous under-redaction survivors (R02 R03 R07 R08 R10-R13 R17 R20-R24 R26-aws R26-slack R35-R38 R43-R47 R52) are now KILLED.

## End-to-end, MCP stub path and timing

| check | result |
|---|---|
| `qa/e2e.py` normal loop: success, raised exception, guard denial | 3 x `leaks=[] labels=16 PORT-kept=True` |
| unknown tool | `Error: Unknown tool 'echo'. Available tools: none.` (no secret) |
| resume (rerun, report_unknown, stop) x (success, raise, guard) and non-idempotent rerun | 10 combinations `leaks=[]`; final line `E2E OK` |
| MCP stub, successful results (github token, cfg value, .env text, x-mcp-key, Bearer) | all `leak: False` |
| independent stub `qa/mcp4.py` (own stub, env value + AWS key everywhere) | success `k=[REDACTED] [REDACTED:aws-access-key]`; `isError` result redacted, `is_error=True`; JSON-RPC error `EXC rpc [REDACTED] [REDACTED:aws-access-key]`; `stderr_tail` 3 lines all redacted; every row `leak: False`; no child left after exit |
| 4 MB timing (`qa/t4.py`, 17 maximiser units) | `redact_secrets` worst 0.447 s (`x-mcp-key: `); successful-result `client.redact` worst 0.965 s (`eyJ-`); all others at or under 0.877 s |

## Follow-up table (over-redaction survivors; do not fail the bar; for the PR description)

| mutant | change | effect | one-line pin |
|---|---|---|---|
| R14 | header token class gains `,` | `Bearer <token>,rest` loses `,rest` (real keeps it) | `assert redact_secrets("Bearer " + BEARER + ",rest")[0] == "Bearer [REDACTED:bearer-token],rest"` |
| R15 | header token class gains `;` | `Bearer <token>;rest` loses `;rest` | `assert redact_secrets("Bearer " + BEARER + ";rest")[0] == "Bearer [REDACTED:bearer-token];rest"` |

N04, N06 and the other earlier label/whitespace survivors are now killed (mutn survivor list is N31 only). No label-only or whitespace-only survivors remain.

## Equivalents (11), with the proof class

Design: gh-trail, no-ascii-0, no-ascii-1. Earlier passes (300,000-pair fuzz): Q18, Q24, N31. Fuzz proofs from pass 3 (`qa/fz3.py`; src unchanged so they still hold): R04 (`\Z` matches only at len(text), where the END header cannot), R16 (rule has IGNORECASE so `[a-z]` already matches `A-Z`), R29 (`text[start]` is the `s` of `sk-`), R39 (duplicate spans merge), R40 (same union argument as Q24).

## Adversarial probes recorded

probe: 10x isolated and 5x CPU-loaded runs of the new MCP stub tests (flake); probe: whole file under load; probe: stub leaves no child, writes only to tmp_path, no network; probe: planted literal against P7 and P7b; probe: Q23 on a full tree copy; probe: re-run of the three mutant batches (227 mutants, fresh process each); probe: normal and resume loop across success, exception, guard denial; probe: independent MCP stub (success, isError, JSON-RPC error, stderr); probe: 4 MB maximisers.

## Defects

None blocking. Observations:
1. The stub in the new test carries the fake AWS key in the tmp_path script only (key is built at runtime from fragments; P7 and P7b on the test file are clean).
2. N35 is still killed only by the 1 MB timing test (about 180 s in mutq); unchanged from pass 3.
3. `check-harness-refs.sh` runs the packager inside the real tree (rc 0, `git status` still the four design files); `package-plugin.sh` itself was run on a scratch copy.

## Not run

- No further fresh mutant batch (orchestrator instruction).
- No network or real-credential checks; nothing staged or committed.

## Next step

Put the R14/R15 follow-up pins in the PR description (or add them as two assertions later) and merge.
