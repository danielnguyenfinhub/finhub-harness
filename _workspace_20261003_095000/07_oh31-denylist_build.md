# OH31 sensitive-path denylist: build report (design revision 5)

Status: **PASS**. All four gate commands exit 0. Nothing committed or pushed.

## Files
| path | status |
|---|---|
| src/master_finhub/tools/sensitive_paths.py | created (238 lines, over the design's 120-line target: docstrings, adapted-from comments and the 17 patterns) |
| src/master_finhub/tools/safety.py | modified: `_sp` import, `PATH_ARG_KEYS`, 3 `RULE_REASONS` rows, `_State.sensitive`, `_sensitive_word_rule` (first statement of `segment_rule`), `sensitive` threaded through `_check` / `_check_tokens` / `_inline_rule`, `call_scope` in `_check(depth=0)` and `_guard`, `_path_rule`, `sensitive_paths` keyword on `check_rule` / `check_command` |
| src/master_finhub/tools/mcp/client.py | modified: `sensitive_paths=False` at the launch check (one line plus a comment) |
| tests/test_sensitive_paths.py | created (214 passed, 1 skipped) |

No other file under `src/` or `tests/` changed. Existing tests are unmodified.

## Claims implemented
A1-A29, A31-A42 (A30 withdrawn). Coverage map (test names in `tests/test_sensitive_paths.py`):

| id | test(s) |
|---|---|
| A1, A9, A21 | `test_allowlist_cannot_pre_empt[*]` (8 pinned names, via `check_command`, `make_guard`, `_both`), `test_cd_branch_does_not_pre_empt`, `test_constants_not_configurable` |
| A2-A8, A10, A13, A16, A24-A28 | `test_pattern_denied_as_path_arg[*]`, `test_pattern_denied_as_cat_command[*]` (19 paths), `test_variant_commands_denied` (dir roots, trailing slash), `test_variant_path_args_denied`, `test_must_pass_paths`, `test_must_pass_commands` |
| A11 | `test_symlinks_resolved_form`, `test_symlink_into_credentials_denied`, `test_two_calls_do_not_share_a_memo` |
| A12, A23 | `test_variant_path_args_denied` (`Path`, `FILE_PATH`, `paths`, nested `source`, `cwd`, `destination`, `uri`, `root`), `test_free_text_key_not_scanned` |
| A14 | `test_openharness_stores_not_ported`; `test_adapted_patterns_carry_source_comments` (comment lines 18, 20, 22, 23, 25, 27, 29, 31, 33, 91, 169 and query.py:1032) |
| A15 | `test_nested_payloads_denied` (7), `test_posix_stream_only_spellings` |
| A17 | `test_variant_commands_denied` (`~/.SSH/ID_RSA`, `~/.Aws/Credentials`), `test_variant_path_args_denied` |
| A18, A19 | `test_windows_forms_need_the_lexical_form` (realpath_bounded patched to return `/nowhere`, so only the lexical form can deny), Windows entries in the variant tests |
| A20 | `test_nul_under_an_existing_directory_is_denied`, `test_stat_failure_is_denied` (patches `os.stat`), `test_walk_failure_is_denied` (patches `realpath_bounded`), `test_permission_denied_is_deny_not_missing`, `test_matcher_crash_is_check_failed` |
| A22 | `test_denials_never_echo` |
| A29 | `test_agent_loop_spy_tool_never_runs` |
| A31 | `test_mcp_launch_opt_out`, `test_mcp_launch_live_stub_does_not_raise`, `test_mcp_launch_destructive_still_denied`, `test_ast_scan_tree_is_clean` (0 violations, allowed count exactly 1), `test_ast_scan_flags_negative_spellings` (11), `test_ast_scan_positives` (3) |
| A32 | `test_docker_engine_keeps_the_default` |
| A33 | `test_cap_raw_lengths`, `test_cap_applies_after_expansion`, `test_command_scan_cost[pad-one-word, bash-pad-one]` |
| A34, A39 | Windows suffix and drive-relative entries in the variant tests, `test_drive_split_cases`, must-pass commands |
| A35 | `test_command_scan_cost[*]` (12 vectors; check (i) < 0.5 s, (ii) 7 interleaved runs each, fastest of each, limit 0.1 s, (iii) single level < 0.25 s) |
| A36 | `test_memo_counts_one_match_per_word`, `test_two_calls_do_not_share_a_memo` (`check_rule`, guard command form, guard path form) |
| A37 | `test_regex_equals_per_pattern_fnmatch`, `test_regex_dropping_a_pattern_would_be_caught` |
| A38 | `test_rule_runs_before_strip_wrappers` |
| A40 | `test_budget_*` (distinct paths, legit paths, shared budget, boundary at 10, lexical-before-walk at budget 0), `test_symlink_chain_is_bounded`, `test_flat_symlink_amplification_is_bounded`, `test_symlink_cap[39/40/41]`, `test_symlink_loop_is_denied`, `test_symlinked_workspace_passes` |
| A41 | `test_sequential_guard_calls_do_not_share_budget`, `test_sequential_check_rule_calls_do_not_share_budget`, `test_two_threads_do_not_share_budget`, `test_nested_scope_is_shared_and_reset_only_by_opener`, `test_scope_reset_after_exception`; T41 `tests/test_modes.py::test_empty_string_denial_blocks` passes unmodified |
| A42 | `test_walk_equals_realpath` (2,000 seeded paths, relative and absolute, 0 differences), `test_deep_existing_tree_is_cheap`, `test_search_only_directory` (skips as root) |

## Mutation targets 1-14
Each mutant was applied to a scratch copy of `src/` (outside the repo, `-o pythonpath=`), and `tests/test_sensitive_paths.py` was run. Every mutant turned at least one test red.

| # | mutant | killed by (first failures) |
|---|---|---|
| 1 | rule moved below the `cd` branch | `test_variant_commands_denied[cd ...]`, `test_cd_branch_does_not_pre_empt`, `test_rule_runs_before_strip_wrappers[K=...]` |
| 2 | fail open | `test_nul_under_an_existing_directory_is_denied`, `test_stat_failure_is_denied`, `test_walk_failure_is_denied`, `test_permission_denied_is_deny_not_missing` |
| 3 | lexical form dropped / resolved form dropped | 22 variant tests incl. the A19 Windows cases / `test_symlinks_resolved_form`, `test_symlink_into_credentials_denied` |
| 4 | POSIX stream skipped | `test_posix_stream_only_spellings`, `test_nested_payloads_denied` |
| 5 | first argument only | 28 tests, incl. `cp`, `git`, `grep` variants and the pinned table |
| 6 | no recursion into payloads | `test_nested_payloads_denied` |
| 7 | raw-only cap | `test_cap_applies_after_expansion`, `test_command_scan_cost[pad-one-word, bash-pad-one]`, `test_denials_never_echo` |
| 8 | rule after `strip_wrappers` | `test_rule_runs_before_strip_wrappers` (3) |
| 9 | no casefold | `~/.SSH/ID_RSA`, `~/.Aws/Credentials` variant tests |
| 10 | `Scan` per segment instead of per call | `test_memo_counts_one_match_per_word`, `test_command_scan_cost[distinct-dot]`, `test_budget_boundary` |
| 11 | memo kept across calls (module-level `Scan`) | `test_command_scan_cost[cat-dirs18 ...]`, `test_budget_many_distinct_paths_denied_fast` (12 failures) |
| 12 | no budget charge | `test_command_scan_cost[cat-dirs18, bash-cat-dirs18, echo-dirs17]`, `test_budget_many_distinct_paths_denied_fast` |
| 13 | `Path.resolve` plus string charge | `test_symlink_chain_is_bounded`, `test_flat_symlink_amplification_is_bounded`, `test_deep_existing_tree_is_cheap`, `test_symlink_cap[41]` |
| 13 | symlink cap removed | `test_symlink_cap[41-path-budget]` (the 41-link test, not the loop test: the loop still gives `path-budget` through the component budget) |
| 13 | whole-prefix `lstat` walk | `test_deep_existing_tree_is_cheap` (2 runs) |
| 14 | `call_scope` never resets / resets in a nested scope | 34 tests incl. the sequential and thread tests / `test_budget_is_shared_between_path_and_command_branches`, `test_nested_scope_is_shared_and_reset_only_by_opener` |
| spare | path-key branch deleted, stream stripping dropped, drive split dropped, MCP keyword flipped to on, regex missing a pattern | 68, 10, 4, 2 (`test_mcp_launch_live_stub_does_not_raise`, AST scan), 24 failures |

## Gate
Run in `/home/user/finhub-harness` with `.venv/bin/...`, after the last edit.

- `.venv/bin/python -m pytest -q`: **exit 0, 891 passed, 10 skipped** (82 s). Previous 677 + 214 new = 891. Skipped is 10, not 9: the new `test_search_only_directory` skips because this box runs as root, as the fix-up requires.
- `.venv/bin/ruff check src tests`: exit 0, `All checks passed!`
- `.venv/bin/black --check src tests`: exit 0, `67 files would be left unchanged.` (Black also prints a "Python 3.11 cannot parse code formatted for Python 3.15" warning from the environment's config; it is not an error.)
- `.venv/bin/mypy --strict src`: exit 0, `Success: no issues found in 41 source files`
- Six existing suites (`test_safety`, `test_modes_sub`, `test_mcp_client`, `test_docker_engine`, `test_workspace`, `test_modes`), 3 runs: **294 passed, 5 skipped** each (16.1, 16.5, 16.9 s). No failures, including T41.
- `tests/test_sensitive_paths.py` alone, 3 runs: 214 passed, 1 skipped each (about 20-21 s).
- Proof one-liner (`bash -c 'cat ~/.a"w"s/credentials'`) prints `rule sensitive-path` and no `credentials`.

## AMBER actions
None. No dependency added, no `pyproject.toml` change.

## Deviations from design
1. **ENAMETOOLONG treated as missing in the walk.** A single name over 255 characters makes `os.stat` raise `ENAMETOOLONG`. `os.path.realpath` treats it as missing, and the design's must-pass `{"path": "/workspace/" + "a" * 4000}` needs a non-error result. Every other `OSError` (EACCES, EIO, NUL `ValueError`) still denies. Only `FileNotFoundError`, `NotADirectoryError` and `ENAMETOOLONG` mean missing. The name cannot exist, so nothing is hidden.
2. **O_PATH (fix-up 2).** Directory lookups use `O_PATH|O_DIRECTORY|O_NOFOLLOW` (falls back to `O_RDONLY` if `os.O_PATH` is absent). I could not run the search-only test here: the box is root, so it skips. It is written to the judge's spec (`d` mode 0111, `d/k -> $HOME/.ssh`, `d/notes` allowed, `d/k/id_rsa` denied). The `O_PATH` behaviour on search-only directories is therefore **unverified on this box**. A non-root run is needed. A separate test pins that `EACCES` from `stat` is a denial.
3. **Windows import behaviour** is stated in the module docstring: `os.O_DIRECTORY` is referenced at import, so the module fails loudly there.
4. **Cost-vector rows 4,104-char / 17 reps** use `"./$CLIENT_A_DIRS/" * n` for the `echo` rows and `"./" + "$CLIENT_A_DIRS/" * 18` for the `cat` rows, matching the design's two forms. Results match the design table (`path-budget`, `path-budget`, `path-budget`, `None`).
5. **Root-ness.** The 0.5 s / 0.25 s / 0.1 s timing limits are unchanged. They passed in all 6 runs here (the box is noisy; see the design's margins). If a slower CI host breaks one, boundary-qa should name it; I did not loosen anything.
6. The cost-vector test (ii) uses "fastest of 7 interleaved runs each", the rev-5 wording. Mutation 13's "symlink cap removed" is named to the 41-link test.

## Could not satisfy
Nothing in the design was unsatisfiable. Open item: the search-only-directory test has not executed (see Deviation 2).
