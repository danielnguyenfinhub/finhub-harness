# runtime-builder F1+F2 (own-code fix, no reference claims)
Status: PASS. Files: src/master_finhub/tools/mcp/client.py (modified, one token), tests/test_secret_scan.py (modified, +32 tests). Not committed.

## F1 change
SECRET_SHAPES JWT branch gets leading `(?<![A-Za-z0-9_-])`. Nothing else in src.
Repro (scratchpad/repro.py, client.redact mcp_shapes=True):
- before: "eyJ" 10KB 0.042s, 100KB 4.28s; "eyJ-" 10KB 0.033s, 100KB 3.2s (quadratic). C3 regression "eyJaaaaaaaaaaaa-" 100KB known aaaa: 0.847s.
- after (100KB / 1MB / 4MB): eyJ .009/.10/.39; eyJ- .010/.10/.41; eyJ_ .009/.10/.41; eyJ0 .009/.10/.39; eyJaaaaaaaaaaaa- .010/.10/.38; eyJ.eyJ.eyJ. .010/.16/.47; eyJaaaaa. .011/.11/.41. C3 regression case: 0.0177s.

## Tests (tests/test_secret_scan.py)
- test_mcp_error_path_is_linear_on_jwt_shaped_runs: 8 units x {no known, known "aaaa"} at 4 MB, bound 3 s (measured max ~0.96 s).
- test_mcp_error_text_jwt_is_still_redacted (9 contexts), test_mcp_jwt_glued_after_a_segment_character_is_not_matched (5): glued after - _ 0 a Z returns text unchanged end to end.
- test_bearer_token_stops_at_comma_and_semicolon (F2, 2).
Behaviour change to note: before F1 a JWT glued after [A-Za-z0-9_-] WAS redacted by SECRET_SHAPES ("-eyJ..." -> "-[REDACTED]"); after, it is left unredacted (secret_scan R10 has the same boundary). Pinned as spec'd. A JWT glued BEFORE a trailing char stays redacted (third segment absorbs it), so no suffix pin.

## Gate
- new tests x3: 44 passed (selector includes pre-existing matches) each run, ~7.7 s.
- pytest -q: baseline 1184 passed/10 skipped confirmed; after 1216 passed/10 skipped (+32).
- mypy --strict src: no issues (38 files). ruff check src tests: all passed. black --check: 66 unchanged.
- check-harness-refs.sh rc 0; package-plugin.sh rc 0.
- P7 (extended grep) on tests/test_secret_scan.py: 0; P7b: (); Hangul grep over skills/: 0 lines (rc 1). P7/P7b only run on test_secret_scan.py (only test file touched).
- Not run: P7/P7b elsewhere (not needed); no CI.

## Mutation (tar copy in scratchpad/m2, each diff shown, PYTHONPATH import path verified)
1. old branch restored: timing test hangs, killed by timeout 60 (rc 124).
2. drop `-` from look-behind: killed by "eyJ-" timing test (rc 124); first attempt survived only because my -k selector hit the eyJ_ test, re-run with the right id.
   drop `_`: killed by "eyJ_" test (rc 124).
3. no look-behind: killed by "eyJ0" timing test (rc 124).
4. add `,` to _TOKEN in secret_scan.py: comma pin FAILED (rc 1).
Caveat: timing tests have no internal kill; against a quadratic regex they hang (minutes-hours) rather than fail fast.

## Fix after QA (test-only, no further src change)
Added 6 tests (pytest count 1216 -> 1222 passed, 10 skipped): test_jwt_at_segment_minimum_is_redacted_by_shapes_alone (client.redact and SECRET_SHAPES.sub on `eyJabcde.fghij.klmno`, kills M10 M12 M14 M16); test_glued_github_prefix_is_matched_by_shapes_only (xghp_, xghs_ + 20 a; M25 M28); test_glued_pat_and_slack_prefix_... (xgithub_pat_, xxoxb-1111111111; M26 M27); test_fragmenting_known_value_is_applied_with_shapes (pins the exact fragmented output, T4); test_is_error_result_gets_the_shape_pass_through_the_call_path (stub server, `_secrets` patched to [] so only SECRET_SHAPES acts; "boom denied: [REDACTED]"; M21). Over-redaction pins M11 M13 M15 M29 deliberately NOT added (follow-ups).
Gates after: new tests x3 26 passed each; pytest 1222 passed/10 skipped; mypy strict, ruff, black clean; check-harness-refs rc 0; package rc 0; P7 0, P7b (), Hangul 0.
Mutation (fresh tar copy per mutant, diff shown, scratchpad/m3): M10 M12 M14 M16 M21 M25 M26 M27 M28 T4 all killed (pytest rc 1, named failing test). F1 mutants (old branch, drop '-', drop '_', no look-behind) killed by timeout (rc 124); add ',' to R2 _TOKEN killed (rc 1). M12/M14 mutated the segment quantifier and also turned `\.` into `.`; still a real mutant and killed.
