RESULT: FAIL
Survivors (pass 2, 33 mutants): 0 non-equivalent UNDER-redaction src survivors (M10 M12 M14 M16 M21 M25 M26 M27 M28 all KILLED); 3 over-redaction survivors M11 M13 M15 (follow-ups, out of scope; M29 is now killed); 1 test-only weakening T4 still SURVIVES under my runner (sole blocker, see Defects 1); 0 equivalents claimed.

# Boundary QA pass 2: C3 follow-ups F1 + F2 (2026-10-03)

Tree /home/user/finhub-harness (uncommitted, not modified by me). Repo python `.venv/bin/python -B`. Scratch: /tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/p3 (`after3/` = tar of the working tree, `mut3/<id>/` = one mutant tree each, `mut3.py` = my pass-1 runner `mut.py` with only the paths repointed; `mut3.log` = raw output).

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| F1 src change | client.py:52 JWT branch gains `(?<![A-Za-z0-9_-])` | `git diff src`: exactly one `-`/`+` pair, that token | yes |
| client.redact error path vs call site | client.py:363 `mcp_shapes=is_error` | new test drives `McpClient.call_tool` against the stub: success text verbatim, isError text `boom denied: [REDACTED]` with `_secrets` patched to [] | yes (M21, M22, M18 killed by it) |
| SECRET_SHAPES quantifier minima vs tests | `{20,}`, `{20,}`, `{10,}`, JWT `{5,}`x3 | new tests at the exact minimum (xghp_/xghs_ +20, xgithub_pat_ +20, xxoxb- +10, eyJabcde.fghij.klmno) | yes (M10 M12 M14 M16 M25-M28 killed) |
| F2 pin vs R2 | `redact_secrets("Bearer "+BEARER+sep+"rest")` | secret_scan.py `_TOKEN` | yes (B5, M23 killed) |
| glued forms vs pins | see section 5 | `test_mcp_jwt_glued_...[-,_,0,a,Z]`, table cases `"-"+JWT`, `"_"+JWT`, `"0"+JWT`, `"x"+JWT` | yes, by character class |

## 1. Scope
| command | exit | output observed |
|---|---|---|
| `git status --short` | 0 | ` M src/master_finhub/tools/mcp/client.py` / ` M tests/test_secret_scan.py` |
| `git diff --stat` | 0 | `client.py 2 +-`, `test_secret_scan.py 80 ++++-`, `2 files changed, 80 insertions(+), 2 deletions(-)` (vs base: 1 src line pair; 1 test line pair is the import) |
| `git diff src | grep '^[-+]'` | 0 | only `-    r"|eyJ[A-Za-z0-9_-]{5,}\.…"` / `+    r"|(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.…"`: one token |
| `git diff --quiet -- src/master_finhub/tools/secret_scan.py references && echo untouched` | 0 | `untouched` |
| `diff after2/tests/test_secret_scan.py tests/test_secret_scan.py` (my pass-1 copy vs now) | 1 | one `<` line (the single-line import `from master_finhub.tools.mcp.client import McpClient, McpError, StdioServer, redact`) replaced by a 7-line parenthesised import adding `SECRET_SHAPES`; every other line is `>` (5 new tests). Not pure additions: the one removed line is that import, re-emitted by the same names plus SECRET_SHAPES. Black-driven reformat, no test edited or deleted. |

## 2. Gates on the real tree
| command | exit | output observed |
|---|---|---|
| new tests x3: `pytest -q -p no:cacheprovider tests/test_secret_scan.py -k "jwt_at_segment_minimum or glued_github_prefix or glued_pat_and_slack or fragmenting_known or is_error_result_gets or jwt or comma or linear"` | 0 x3 | `55 passed, 272 deselected in 8.24s` / `7.83s` / `8.02s` |
| MCP stub test x10 (`-k is_error_result_gets`) | 0 x10 | ten runs, all `1 passed, 326 deselected` in 0.15-0.20 s |
| under CPU load (8 busy loops on 4 cores): stub + timing tests | 0 | `17 passed, 310 deselected in 18.60s` (timing test bound 3.0 s held); stub test x5 under load `1 passed` in 0.24-0.48 s |
| `pytest -q -p no:cacheprovider` (full) | 0 | `1222 passed, 10 skipped in 97.95s (0:01:37)` (= 1184 + 38 as the builder said) |
| `mypy --strict src` | 0 | `Success: no issues found in 38 source files` |
| `.venv/bin/ruff check --no-cache src tests` | 0 | `All checks passed!` |
| `.venv/bin/python -B -m black --check src tests` | 0 | `66 files would be left unchanged.` |
| `bash scripts/check-harness-refs.sh` | 0 | `PASS no Hangul in agents+triage` / `PASS packager exit 0` |
| `bash scripts/package-plugin.sh` | 0 | `dist/finhub-harness-skill.zip  85199 bytes` / `dist/finhub-harness-evolve-skill.zip  3516 bytes` (writes gitignored `dist/` in the repo root; not deleted by me) |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' skills/` | 1 | no output |
| P7b `redact_secrets(open(tests/test_secret_scan.py).read())[1]` | 0 | `()` |
| P7 broad grep (`ghp_…{20,}|xox…{10,}|AKIA…|sk-ant-|github_pat_…{20,}|eyJ…{10,}\.`) on the test file | 0 | 11 hits, all prefixes or fragment concatenations (e.g. `ANT = "sk-ant-" + "FAKE0" * 5`, `"sk-ant-",`, `"eyJaaaaaaaaaaa."`); no complete literal credential; the authoritative check is P7b `()` |
| probe: planted `x = "xoxb-0000-FAKEFAKE"` appended to a scratch copy | | P7b on the copy `('slack-token',)`, literal grep count `1`: both fail on the planted literal; real file `()` / table above |

## 3. Mutants (mut3.py, fresh process per mutant, `timeout 150`, `tests/test_secret_scan.py tests/test_mcp_client.py`; each run prints `srcfiles_differ=1` (one src file differs from after3) and the exact replaced strings; BAD-COUNT guard requires exactly one occurrence)
| id | change | result |
|---|---|---|
| B1 | restore old JWT branch | KILLED rc 124 (hang in timing test, 59 dots then stall) |
| B2 | look-behind without `-` | KILLED rc 124 |
| B3 | look-behind without `_` | KILLED rc 124 |
| B4 | look-behind `\b` | KILLED rc 124 |
| B5 | `,` added to R2 `_TOKEN` | KILLED rc 1 `test_bearer_token_stops_at_comma_and_semicolon[,]` |
| M06 | look-behind direction `(?<=` | KILLED rc 124 |
| M07 | look-behind drops `A-Z` | KILLED rc 124 |
| M08 | look-behind drops `0-9` | KILLED rc 124 |
| M09 | look-behind drops `a-z` | KILLED rc 1 `test_mcp_jwt_glued_...[a]` |
| M10 | seg 1 `{6,}` | KILLED rc 1 `test_jwt_at_segment_minimum_is_redacted_by_shapes_alone` |
| M11 | seg 1 `{4,}` | SURVIVED (over-redaction, follow-up): `349 passed` |
| M12 | seg 2 `{6,}` | KILLED rc 1 `…segment_minimum…` |
| M13 | seg 2 `{4,}` | SURVIVED (over-redaction, follow-up) |
| M14 | seg 3 `{6,}` | KILLED rc 1 `…segment_minimum…` |
| M15 | seg 3 `{4,}` | SURVIVED (over-redaction, follow-up) |
| M16 | lead `eyJ`->`eyj` | KILLED rc 1 `…segment_minimum…` |
| M17 | known-value pass dropped | KILLED `test_mcp_redact_chains_to_shape_scan` |
| M18 | `if mcp_shapes:`->`if True:` | KILLED `test_is_error_result_gets_the_shape_pass_through_the_call_path` |
| M19 | `if not mcp_shapes:` | KILLED `…segment_minimum…` |
| M20 | `if False:` | KILLED `…segment_minimum…` |
| M21 | call site `mcp_shapes=False` | KILLED `test_is_error_result_gets_the_shape_pass_through_the_call_path` |
| M22 | call site `mcp_shapes=True` | KILLED same test |
| M23 | `;` in `_TOKEN` | KILLED `test_bearer_token_stops_at_comma_and_semicolon[;]` |
| M24 | R2 label renamed | KILLED `test_header_rules_keep_their_prefix[…]` |
| M25 | `gh[pousr]_{21,}` | KILLED `test_glued_github_prefix_is_matched_by_shapes_only[xghp_…]` |
| M26 | `github_pat_{21,}` | KILLED `test_glued_pat_and_slack_prefix_are_matched_by_shapes_only` |
| M27 | `xox…{11,}` | KILLED same test |
| M28 | class `gh[pour]_` | KILLED `…glued_github_prefix…[xghs_…]` |
| M29 | JWT `\.`->`.` | KILLED (was a survivor in pass 1) `test_fragmenting_known_value_is_applied_with_shapes` |
| T1 | old branch + 100 KB | KILLED `test_mcp_error_path_is_linear_…[eyJ-no-known]` |
| T2 | old branch + 40 KB | KILLED by the glue pin `…glued…[-]` (as pass 1) |
| T3 | old branch + 100 KB + bound 300 s | KILLED by the glue pin `…glued…[-]` |
| T4 | test only: `[[], ["aaaa"]]`->`[[], []]` in the timing test's parametrize (no src change, `testfile_differs=True`) | **SURVIVED**: `349 passed in 22.97s`, rc 0 |

F1 mutants (restore old branch B1, drop `-` B2, drop `_` B3, remove look-behind B1/B4, `,` in `_TOKEN` B5): all killed (hang rc 124 or rc 1).
Over-redaction survivors: M11 M13 M15 exactly (M29 moved to killed). Equivalent mutants: none claimed.

## 4. End to end and timing (e2e.py, stub_e2e.py, t4mb.py in scratchpad; real tree)
| path | result |
|---|---|
| AgentLoop.run (ScriptedLLM, leaky tool) | `snaps 4 has REDACTED: True leaks: []` |
| AgentLoop.resume(in_flight="rerun") | `snaps 3 has REDACTED: True leaks: []` |
| MCP stub success / isError / JSON-RPC error | each `leaks: [] | redacted: True` |
| stderr_tail | `leaks: []` |
| 4 MB x 13 units, SECRET_SHAPES.sub, worst | 0.13 s (`ghp_`) |
| 4 MB x 13 units, redact_secrets, worst | 0.42 s (`Bearer\n`) |
| 4 MB x 13 units, client.redact(known `aaaa`, mcp_shapes=True), worst | 0.94 s (`eyJ`+12 a+`-`); e2e.py five units worst 0.88 s |
All linear, no unit near the 3.0 s test bound. Branch coverage of the 13 units: B1 Bearer (2), B2 ghp_ (2), B3 github_pat (1), B4 xox (2), B5 JWT (6).

## 5. Pinned behaviour: CI hang and the six glued forms
CI-hang rating: FOLLOW-UP, not blocking. `grep -n timeout .github/workflows/ci.yml pyproject.toml` returns nothing (rc 1): no job `timeout-minutes`, no pytest-timeout. A regression to the old JWT branch stalls CI up to the GitHub 360-minute default (B1: 59 dots then hang, rc 124 at 150 s here); it corrupts nothing and leaks nothing, and the glue pins fail fast when the file is run without timing tests (T2/T3). One line `timeout-minutes: 15` under `jobs.check` is the recommended fix; not done (QA does not edit).

Six forms, unredacted by design after F1 (re-run of forms.py on the real tree: `token-eyJ…`, `Bearer-eyJ…`, `jwt_eyJ…`, `jwt-eyJ…`, `x-eyJ…`, `1eyJ…` all `client.redact LEAK | table-only LEAK`; the other 15 forms in the table redact):
| form | pinned as NOT redacted by | pin kind |
|---|---|---|
| token-eyJ, Bearer-eyJ, jwt-eyJ, x-eyJ | `test_mcp_jwt_glued_after_a_segment_character_is_not_matched[-]` (client.redact) and table case `("-"+JWT, "-"+JWT)` (secret_scan) | by the preceding character `-` |
| jwt_eyJ | `…glued…[_]` and table `("_"+JWT, …)` | by `_` |
| 1eyJ | `…glued…[0]` and table `("0"+JWT, …)` | by digit `0` |
Pinned: all six, at character-class level (the tests glue one char to a fixture JWT; none uses the literal words `token`, `Bearer`, `jwt`, `x`). A later fix that redacts any of them fails these tests, so it would be a conscious change. Unpinned: the literal-word spellings; the pins would not distinguish `Bearer-eyJ` from `x-eyJ`, which is acceptable because the rule depends only on the preceding character. Daniel's acceptance of the trade is still recorded as open.

## Defects
1. tests/test_secret_scan.py:308 mutant T4 survives. `@pytest.mark.parametrize("known", [[], ["aaaa"]], ids=["no-known","fragmenting-known"])` can drop `["aaaa"]` with all 349 tests still passing (mut3 T4: rc 0, `349 passed in 22.97s`). The builder's new `test_fragmenting_known_value_is_applied_with_shapes` pins the functional output (and kills M29), but it is a separate test, so removing the fragmenting-known case from the timing test is not detected. Test-only, no src change, no leak; by the standing PASS bar a surviving non-equivalent mutant is a FAIL, and Daniel's instruction was that T4 be killed. The builder reported T4 killed, which does not reproduce in my runner (the builder's T4 definition was not shown to me; my T4 is the same mutation as pass 1). Orchestrator may accept this as test-hygiene residue (the property it guarded is now pinned functionally); it is not a PASS under the stated bar.
2. observation: client.py:52 / secret_scan.py:62: the six glued forms leak end to end (section 5); declared trade (C3 Does-not-cover #5, A38), pinned by character class. Needs Daniel's explicit acceptance.
3. observation: the single removed test line (import reformat) breaks "additions only" literally; content-equivalent.
4. observation: ci.yml / pyproject.toml have no timeout; follow-up per section 5.
5. observation: M11 M13 M15 over-redaction survivors remain follow-ups (witnesses: `eyJabcd.fghij.klmno`, `eyJabcde.fghi.klmno`, `eyJabcde.fghij.klmn` expected unchanged by the design minimum of 5).

## Not run
No new mutants and no new fresh batch (Daniel's bound). Global ruff (old version in /root/.local/bin) not re-run (pass-1 note stands). No CI run.
