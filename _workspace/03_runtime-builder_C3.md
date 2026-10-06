# Runtime builder report: C3 (secret-shape redaction), status PASS

## Files
- src/master_finhub/tools/secret_scan.py: created, 103 lines (design block verbatim)
- src/master_finhub/runtime/loop.py: modified (+6: import, `_execute` wrapper, old body renamed `_run_tool`)
- src/master_finhub/tools/mcp/client.py: modified (import, `redact()` span merge with `mcp_shapes`, `call_tool` redacts every result)
- tests/test_secret_scan.py: created, 330 lines, 207 cases (design's 325/202 plus the N13 additions below)
No other file edited; references/ untouched; no commit; no dependency added (no AMBER actions).

## Claims implemented
A1-A40 (all UPHELD in 02_adversarial-risk-judge_C3_r3.md). Map: A1-A24, A28-A30, A32-A33, A35 -> secret_scan.py rules + test_each_rule_redacts_and_labels / header / negatives / non-ASCII / lengths tests; A25-A26, A37 -> loop.py + loop tests; A27, A34, A39, A40 -> client.py + merge/escape/success-result tests; A31 -> P7/P7b; A36, A38 -> timing test and jwt pins.

## Gate
- `pytest -q tests/test_secret_scan.py`: 207 passed (5.5 s). Test-first: before secret_scan.py existed, collection errored.
- `pytest -q` (whole suite, real tree): `1102 passed, 10 skipped` (895 before + 207). The design said 1097 because it counted 202 cases; the 5 extra are the N13 additions (2 ADVERSARIAL inputs, 3 pins). No existing test failed or was edited.
- `mypy --strict src`: Success: no issues found in 38 source files
- `ruff check src tests`: All checks passed!
- `black --check src tests`: 66 files would be left unchanged (a Python 3.15 target warning only)
- P5: loop.py 2 lines (import :16, call :220); client.py 3 lines (:32, :115, :116). OK
- P5b: `grep -c re.ASCII` = 11. P6 = 2. P7 = 0. P7b = `()`.
- P8: LC_ALL=C.UTF-8 grep -cP Hangul: 0 and 0, rc 1; python fallback over all 4 files: 0.
- 8-word-run check (prose of secret_scan.py vs team.py and redact-mcp-secrets.ts): 0 hits.
- `bash scripts/check-harness-refs.sh`: rc 0 (all PASS). `bash scripts/package-plugin.sh`: rc 0.
- Timing: test_adversarial_megabyte_stays_fast (27 inputs x 1 MB) passes inside the 5.5 s file run.

## N13 additions (test-only)
"eyJ_" and "eyJ0" added to ADVERSARIAL; pins `"_"+JWT` and `"0"+JWT` unchanged, and `"."+JWT` -> `".[REDACTED:jwt]"` positive.

## Mutation (tar copy in scratchpad, python -B, fresh process each, runner adapted from mutate_r2.py)
83 mutants (design's 81 plus jwt-lb-no-underscore and jwt-lb-no-digits), each asserted to differ from the original file. 80 killed, 3 survived, all the design's proven equivalents: gh-trail (X20), no-ascii-0 (the comment occurrence), no-ascii-1 (R1). Both N13 mutants killed (1 failed each). Also killed: oai-lookahead-restored (timeout), jwt-restore-b, jwt-lookbehind-word-only, no-ascii-all, mcp-sequential-values-first/shapes-first, mcp-no-escape, merge-touching, merge-skip-1char, loop-site, loop-success-only, loop-str-coerce. Not run: none of the design's list skipped. The two no-ascii survivors are mapped by index, not by the per-rule names in the design table.

## Deviations from design
Only the 5 N13 test cases (required by the judge); test count 207 not 202, suite total 1102 not 1097.

## Fix after QA (test-only; src/ untouched)
Added to tests/test_secret_scan.py (330 -> about 440 lines after black), 28 new cases, none timing-based:
D1 slack letters a/b/p/r/s (5 cases incl. existing b); D2 github letters p/o/u/s/r (5); D3 underscore in gh and github_pat_ bodies (1 + folded into D2); D4 JWT with `-` and `_` in every segment (1); D5 JWT segment 2/3 minimum, 5 redacted and 4 not (3); D6 Bearer and x-mcp-key tokens containing each of `+ / ~ - = .` (6); D7 dashed `sk-ant-api-`/`sk-ant-api03-` keys with digit-free and digit tails keep label anthropic-key (2); D8 `sk-` with each digit 0-9 redacted, digit-free not (1); D9 Bearer glued to an identifier unchanged (3); D10 `redact(AWS,[AWS]) == "[REDACTED]"` (value span names the merged span, A33) (1). Credentials are built from FAKE fragments at runtime.

Gates after the fix:
- tests/test_secret_scan.py: 235 passed. Full `pytest -q`: 1130 passed, 10 skipped (1102 + 28).
- mypy --strict src: no issues in 38 files. repo `ruff check src tests`: All checks passed. `black --check src tests`: 66 files unchanged (after `black` reformatted the new test file once).
- check-harness-refs.sh rc 0; package-plugin.sh rc 0. P7 = 0; P7b = `()`; Hangul grep 0 (rc 1).

Mutants (QA runner adapted, tar copy, 3 work dirs, python -B; 118 mutants, no NOOP): 111 killed, 7 survived.
- Q03, Q04, Q05, Q07, Q08, Q09, Q10, Q11, Q13, Q14, Q15 (plus, slash, eq, tilde, dash, dot), Q17, Q27, Q28: all KILLED (each 1 failed).
- Both N13 mutants (jwt-lb-no-underscore, jwt-lb-no-digits) KILLED. The design's 83 mutants: 80 killed, 3 equivalent survivors (gh-trail, no-ascii-0, no-ascii-1).
- Remaining survivors: Q12 (harmless, trailing \b only extends over trailing dashes), Q18 and Q24 (equivalent per QA's fuzz proof), Q23 (survives secret_scan tests only; QA showed tests/test_mcp_client.py kills it).

## Fix after QA 2 (test-only; src/ untouched)
Added 20 cases to tests/test_secret_scan.py (all synthetic, built from FAKE fragments, no timing): Defect 1 `JWT+"-"` -> `[REDACTED:jwt]-`; Defect 2 five header forms (`Bearer 'tok'`, `x-mcp-key': tok`, tab and newline after the colon, tab around `=`); Defect 3 `_LongTool` with 5,000 and 10,000 characters of padding before an AWS key, through both the normal drive and `resume(in_flight="rerun")`; Defect 4 and 5 nine unchanged negatives (AuthBearer, myx-mcp-key, my_github_pat_, x_sk-ant-, AIDA+16, AKIA+16 lowercase, JWT with `!` as either separator, lowercase eyj); Defect 6 unterminated key plus trailing newline gives `before\n[REDACTED:private-key]` (nothing survives, R1 uses `\Z`); Defect 7 known value of 3 characters untouched, of 4 redacted; Defect 8 `redact(AWS,[AWS[:8]]) == "[REDACTED]"`.

Gates: test file 255 passed on 3 consecutive runs (no flake, about 5.7 s each). Full `pytest -q`: 1150 passed, 10 skipped (1130 + 20). mypy --strict src clean (38 files); repo ruff clean; black --check 66 files unchanged; check-harness-refs rc 0; package-plugin rc 0; P7 = 0, P7b = `()`, Hangul 0 (rc 1).

Mutants (tar copy, fresh processes, runner reports NOOP when a mutation does not change the file):
- mutq.py incl. the design's 83 and both N13: 118 run, 113 killed. Survivors: gh-trail, no-ascii-0, no-ascii-1 (design equivalents), Q18 and Q24 (QA-proven equivalents). Q12 and every other Q-series mutant killed.
- mutn.py: 54 run, 52 killed; survivors N31 (proven equivalent) and N50 (a declared control no-op, reported NOOP). N04, N06, N07, N10, N11, N20b, N21, N22, N23, N27a, N33, N34, N38, N46 and N47 all killed.
- Q23 (client minimum 4 -> 1) on a full repo-tree copy with the whole suite: killed by test_mcp_client.py::test_redact_env_value_and_bearer and by the new minimum-length test; the only other failure was the tree-dependent test_lint_harness::test_bad_fixture_names_every_seeded_defect (references/ was not copied).

## Fix after QA 3 (test-only; src/ untouched)
Added 34 cases (cases, not functions; about 14 functions) to tests/test_secret_scan.py, all from FAKE fragments (P7 = 0, P7b = `()`), no timing assertions: private-key header variants (none/ENCRYPTED/RSA/EC/DSA/OPENSSH) x bodies 100/3000/10000; whitespace after `Bearer` and `x-mcp-key:` (`\r \f \v \r\n \t \n` and two spaces); long tokens (20, 60, 1000 repeats; up to about 5,000 characters) for Bearer, x-mcp-key, ghp_, github_pat_, sk-ant-, sk-, xoxb-, and each of the three JWT segments; digit-free AWS and Slack keys; a secret after 120,000 characters through redact_secrets, client.redact and client.redact(mcp_shapes=False); several known values and every occurrence of one value; a three-call loop (two calls in one turn plus one in the next) with no key in any tool message; end-to-end MCP: an inline stub (written to tmp_path, key built at runtime) answers `tools/call` with a JSON-RPC error and writes stderr, asserting the error message (R46/R47) and `stderr_tail` (R43/R44, polled to a 10 s deadline, not a timing assertion) hold neither the env value nor the AWS key; `_fail` and `stderr_tail` unit test (R43-R45).

Gates (run with repo tools): test file 289 passed x3 (6.3, 6.0, 5.9 s); full `pytest -q` 1184 passed, 10 skipped (1150 + 34); mypy --strict src clean (38 files); ruff clean; black --check 66 files unchanged; check-harness-refs rc 0; package-plugin rc 0; P7 0; P7b `()`; Hangul 0 (rc 1). git status shows only the 4 target files (no stray files).

Mutants (tar copy, fresh processes, NOOP reported):
- mutr.py (55): 48 killed; survivors R04, R16, R29, R39, R40 (QA-proven equivalents) and R14, R15 (over-redaction follow-ups). Every R-series under-redaction mutant (R02, R03, R07, R08, R10-R13, R17, R20-R24, R26-aws, R26-slack, R35-R38, R43-R47, R52) is killed.
- mutq.py (118): 113 killed; survivors gh-trail, no-ascii-0, no-ascii-1, Q18, Q24 only.
- mutn.py (54): 52 killed; survivor N31 only; N50 is the declared control NOOP.
