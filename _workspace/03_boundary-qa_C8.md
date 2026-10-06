RESULT: FAIL

C8 (advisory repeat-call reminder). Source is byte-identical to the audited design, all gates are green, every probe behaves as designed. The FAIL is one bar-(a) survivor from the fresh mutant batch: a mutation on a C8-owned line that adds an extra argument to what the tool receives survives the whole 1403-test suite. Real code is correct (probe 4 below); the test suite does not pin "the tool receives exactly the model's arguments". Kill test and one-line fix are under Defects.

## Boundary table

| boundary | side A shape | side B shape | match |
|---|---|---|---|
| `loop._execute` -> `RepeatReminder.observe` | `observe(call.name: str, call.arguments: dict)` (loop.py:233) | `observe(name: str, arguments: object) -> str`, returns text or "" (repeat_reminder.py:48) | yes |
| `observe` result -> tool message | `redact_secrets(self._run_tool(call))[0] + note` (loop.py:234), same Message("tool"), same tool_call_id | `_drive`/`_uncertain` append one `Message("tool", ...)` per call; `_analyse` accepts every checkpoint snapshot (probe 5) | yes |
| `run()`/`resume()` -> `reset()` | reset at loop.py:171 and :178, both before `_save` | `LoopSnapshot` has only step+messages (loop.py:84-85), no counter persisted | yes |
| `_uncertain` -> `_execute` | UNCERTAIN_RESULT paths return before `_execute` (loop.py:219-223) | only the idempotent/rerun branch (loop.py:220) reaches `observe` | yes |
| 5 `AgentLoop(` call sites | cli.py:132, server/app.py:138, subagent.py:315, team.py:356, evals/runner.py:153 | one `RepeatReminder()` per instance (loop.py:168) | yes |
| eval runner -> loop | `parts = [loop.run(bench.task)]` (runner.py:161) | reminder text is not in the final answer; `grep -c observe` over evals = 0 | yes |
| design Authority List N1-N18 <-> current files | see Gate rows G15-G19 | all re-run, all match | yes |
| test fixtures <-> design | `_Tool.run` ignores `arguments` (tests/test_repeat_reminder.py:56); only the guard sees the call (:245-265) | design N10 says the call is never altered | NO, see Defect 1 |

## Gate

| # | command | exit | output observed |
|---|---|---|---|
| G1 | `git status --short` | 0 | ` M src/master_finhub/runtime/loop.py` / `?? src/master_finhub/runtime/repeat_reminder.py` / `?? tests/test_repeat_reminder.py` |
| G2 | `sha256sum` + `wc -l` of the 3 files | 0 | repeat_reminder.py `074a51f279db8b42da9fa1f5cab95b200dc3b5f16a469b191bfbbfb447902445` (64); loop.py `cf74139b815fd8bb29964b0a57bd2ed9a4e81a7bb0a606fa5f1fd5218c4c0bdd` (248); test_repeat_reminder.py `27c520bbc22790f810a2f4ee111f9df04892a4bff1031dd54ae3c58971404b13` (563). All three equal the QA bar. |
| G3 | `sha256sum _workspace/02_strategy-architect_C8.patch`; `git archive HEAD \| tar -x` into a scratch dir; `git apply --check` then `git apply`; `cmp` each file with the repo | 0 | `e958910679608d6d0f8e990b68b73f26e3776f3a4f05e6d8e09c796aa78ca5ef` (matches); `apply rc=0`; `SAME src/master_finhub/runtime/repeat_reminder.py`, `SAME .../loop.py`, `SAME tests/test_repeat_reminder.py` |
| G4 | `env -u PYTHONUNBUFFERED .venv/bin/python -B -m pytest -q -p no:cacheprovider` (foreground) | 0 | `1403 passed, 10 skipped in 100.70s (0:01:40)` |
| G5 | `PYTHONUNBUFFERED=1 ... pytest -q` (foreground, after G4) | 0 | `1403 passed, 10 skipped in 99.35s (0:01:39)` |
| G6 | `pytest -q tests/test_repeat_reminder.py`, both buffering modes | 0 | `61 passed in 0.25s` / `61 passed in 0.26s` |
| G7 | `pytest -q tests -k repeat`, both modes | 0 | `64 passed, 1349 deselected in 2.04s` / `... in 2.64s` |
| G8 | `.venv/bin/ruff check src tests`, both modes | 0 | `All checks passed!` |
| G9 | `.venv/bin/black --check src tests`, both modes | 0 | `69 files would be left unchanged.` |
| G10 | `.venv/bin/python -m mypy --strict src`, both modes | 0 | `Success: no issues found in 39 source files` |
| G11 | `bash scripts/check-harness-refs.sh` ; `... \| grep -c FAIL` | 0 / grep rc 1 | tail: `PASS six agent files` / `PASS CLAUDE.md says six-agent` / `PASS no Hangul in agents+triage` / `PASS packager exit 0`; FAIL count `0` |
| G12 | `bash scripts/package-plugin.sh` | 0 | `pkg rc=0`, `dist/finhub-harness-skill.zip  88048 bytes`, `dist/finhub-harness-evolve-skill.zip  7021 bytes`; `git status --short` afterwards unchanged (dist/ is gitignored) |
| G13 | `LC_ALL=C.UTF-8 grep -nP '\p{Hangul}'` over the 3 files | 1 | no output, `hangul rc=1` |
| G14 | secrets grep (sk-, AKIA, BEGIN ... PRIVATE, password=, api_key=, ghp_, xox) over repeat_reminder.py and the test | 1 | no output, `secrets rc=1` (the test builds its fake AWS key at runtime: `AWS = "AKIA" + "FAKE" * 3 + "0000"`) |
| G14b | attribution: `grep -nE "index.ts:\|watchdog.py" repeat_reminder.py`; loop.py hunk | 0 | repeat_reminder.py:7 `references/autogpt/classic/forge/forge/components/watchdog/watchdog.py:32` (MIT); index.ts `:103`, `:189-198`, `:199`, `:200` cited at lines 4-6; loop.py docstring cites `.../repeat-tool-reminder/src/index.ts:189`. Both cited reference files exist. |
| G14c | 8-word verbatim scan (scratch script, lower-cased word 8-grams) of the 3 files vs `index.ts` and `watchdog.py` | 0 | all six pairs `0 []` |
| G15 | N3: `grep -n "_execute(" loop.py`; `grep -n "_repeat\." loop.py` | 0 | `:193`, `:220`, `:225`; `:171`, `:178`, `:233` (exact) |
| G16 | N8: `grep -rn "AgentLoop(" src --include=*.py \| grep -v runtime/loop.py` | 0 | 5 lines (cli.py:132, server/app.py:138, subagent.py:315, team.py:356, evals/runner.py:153) |
| G17 | N10: `git diff -U0 loop.py \| grep -c '^@@'` ; N15: `git diff --stat` | 0 | `6`; `loop.py \| 18 ++++++++++++++++--` (1 file, 16 insertions, 2 deletions) |
| G18 | N11: `grep -nE "\bhash\(\|random\|time\.\|datetime" repeat_reminder.py` ; N14: `grep -c observe src/master_finhub/evals/*.py` | 1 / 0 | no output; `__init__.py:0 runner.py:0 verifiers.py:0` |
| G19 | N16 `grep -n "note = self._repeat.observe" loop.py` + next line; N7 `_call_key("echo",{"x":"é"*16000}) is not None`, `*17000) is None`; N4/N5/N9/N18 line contents | 0 | `233:` then `return redact_secrets(self._run_tool(call))[0] + note`; `True True`; `LoopSnapshot` fields `step`, `messages` only; UNCERTAIN returns precede `_execute`; `balanced_cuts` and `clip` tail as cited; team.py:371 `loop.resume(LoopSnapshot(prior.step, (*prior.messages, Message("user", prompt))))` |
| G20 | eval before/after: `echo_pass.json` via `python -m master_finhub.evals.runner` with `PYTHONPATH` set to a clean HEAD tar and to the patched tar (module path printed to confirm) | 0 / 0 | both `echo_pass passed true, score 1.0, steps 2, grading 2/2`; `diff` of the two reports differs only in `duration_s` (0.00106 vs 0.00099) |
| G21 | `runner echo_pass.json --baseline <before report>` on the patched tree | 0 | `"regressed": [], "removed": [], "fixed": [], "still_failing": [], "unchanged": ["896d46e952d98230"], "new": []` |
| G22 | `git status --short` at the end | 0 | same three lines as G1; no scratch files in the repo |

The known flaky `test_safety.py::test_adversarial_inputs_are_linear` did not fire in G4 or G5.

## Probes (real `AgentLoop`, ScriptedLLM-style `_Seq`, a scratch script outside the repo; all rows exit 0)

| # | probe | observed |
|---|---|---|
| P1 | 10 identical calls; tail per call | `['-','-','G','-','F5','-','-','F8','-','-']`, tool ran 10 times |
| P2 | `{"b":1,"a":2}`, `{"a":2,"b":1}`, `{"b":1,"a":2}` | reminder on the 3rd call (same key) |
| P3 | A, A, B, A, A | no reminder anywhere (different call resets) |
| P4 | tool receives exact args over 6 calls (no mutation) | `t.seen == args` True |
| P5 | raising tool x3; guard denial x3 (tool run count 0); real `guard_tool_call` on `cat ~/.ssh/id_rsa` x3; unknown tool name x3; real `EchoTool` x5 | `Error: tool 'echo' failed...` kept and notice on 3rd; `Error: denied` + notice on 3rd, `runs == 0`; `Error: Blocked by safety policy (rule sensitive-path)` + notice on 3rd; `Error: Unknown tool 'nope'` + notice on 3rd; echo `['-','-','G','-','F5']` |
| P6 | run crashed by the checkpoint hook after 2 results, then `resume(snapshot)` on a fresh loop | tails `['-','-','-','-','G','-']`: counter restarted at resume |
| P7 | `run()` twice on one instance after a crashed run | second run `['-','-','G']` (reset) |
| P8 | two loop instances sharing one tool | no cross-talk, all `-` |
| P9 | 200,000-char result x3; empty result x3 | 3rd message ends with `GENTLE`, length > 200,000, 3 tool messages; empty result becomes exactly `"\n\n" + GENTLE` |
| P10 | non-ASCII args (Vietnamese, CJK, emoji) x3 | tracked, notice on 3rd |
| P11 | unserialisable args (`set`, `bytes`, `object()`) x4 | no exception, tool ran 4 times, results unchanged, no reminder |
| P12 | 100,000-deep nested dict x3 | `RecursionError` swallowed, tool ran 3 times, results unchanged |
| P13 | `{"a": "x"*100001}` x4 / `{"a": "x"*99900}` x3 | untracked, results intact / tracked, notice on 3rd |
| P14 | `_call_key` patched to raise `MemoryError` | fail open, tool ran 4 times, results `R` |
| P15 | `_call_key` patched to raise `KeyboardInterrupt` | propagates; the tool was not run |
| P16 | tool that increments its own `x` argument in place, x3 | notice on 3rd (count taken before the run) |
| P17 | name `sneakyname`, arg value `TOPSECRETVALUE`, key `secretarg`, output `OUTPUTMARK`, 8 calls; reminder text searched for each | none appears in any reminder |
| P18 | every checkpoint snapshot passed to `_analyse` (via the loop's own `LoopSnapshot` constructor) | all accepted, no split or orphan pair; snapshots JSON-serialisable |
| P19 | `max_steps=3`, 3 identical calls | `AgentLoopError` raised, 3rd saved result ends with `GENTLE` |
| P20 | `ContextManager()`, 9 identical calls; 5-call batch in one turn | `['-','-','G','-','F5','-','-','F8','-']`; batch `['-','-','G','-','F5']` |

Two of my first probe rows read BAD (guard denial, name leak); both were bugs in my script (it named every call `echo` while the tool had another name). Fixed and re-run, then all rows OK, the unknown-tool row re-run separately as shown.

## Timing and memory sweep of `_call_key` / `observe` (scratch script)

| input | observe time | peak RSS after | key |
|---|---|---|---|
| small dict | 0.0 ms | 14 MB | set |
| 99,000-char string | 0.4 ms | 14 MB | set |
| 100,001-char string | 0.4 ms | 14 MB | none |
| 1 MB | 2.9 ms | 17 MB | none |
| 10 MB | 30.6 ms | 42 MB | none |
| 100 MB | 330 ms | 300 MB | none |
| 50 M `é` (ensure_ascii x6, 300 MB text) | 590 ms | 634 MB | none |
| 200k keys / 1M keys | 69 ms / 405 ms | 634 MB | none |
| list of 5 M ints | 369 ms | 634 MB | none |
| nest depth 1e6 (dict, list) | 0.6 ms / 0.2 ms | 634 MB | none |
| NaN/inf, cyclic dict, hostile `__repr__` object, `__str__`-raising str subclass, `{1:"a","1":"b"}`, `{1:..,None:..}` | 0.0 ms each | | no exception |
| 200,000 distinct small calls | 0.74 s total | | state O(1) |

Linear in argument size (about 3.3 ms per MB, transient memory about 3x the text), no super-linear case, no exception. `observe` builds the whole JSON text before it checks the 100,000-char cap, so a hostile 100 MB argument costs about 0.3 s and 300 MB once per call. Observation only: design Design 10 quotes the same linear cost; no regex logic exists.

## Mutant batch (one fresh batch: tar copy of the patched tree per mutant, fresh process, `python -B`, each mutation verified REAL: pattern must occur exactly once and the unified diff must be non-empty)

Test set per mutant: `tests/test_repeat_reminder.py tests/test_loop.py tests/test_context.py tests/test_checkpoint.py` (baseline in the same tar: `175 passed, 4 skipped`). Ordering mutant Q17 (sort_keys off) run under hash seeds 0-39, killed at seed 0.

Harness defect found and fixed before the result below counts: my first run (63 mutants) reported everything KILLED with `1 failed, 118 passed`. The baseline in my tar copy failed `tests/test_checkpoint.py::test_checkpoints_folder_ignores_itself` because I had not copied `.gitignore`; every first-run kill was a false kill and was discarded (a no-op/false-kill trap of the same kind as the one in the QA bar). I added `.gitignore`, confirmed the unmutated tar is green (`175 passed, 4 skipped`), and re-ran the identical list. Only that second run is reported. This is one batch of 63 mutants run twice because of my harness error, not two batches.

Result: 63 mutants, 55 killed, 8 survived (Q10, Q33, Q41, L08, L16, L18, L19, A9 below are all equivalent).

Killed, with the first failing test (all 63 diffs verified non-empty):

| id | mutation | class | killed by |
|---|---|---|---|
| Q01-Q08 | REMIND_AT (2,5,8), (4,5,8), (3,4,8), (3,6,8), (3,5,7), (3,5,9), (3,5,8,9), (3,5,8,13) | c | test_third_identical_call_ends_with_the_reminder / test_reminder_pattern_over_twenty_identical_calls |
| Q09 | `count not in REMIND_AT` -> `count < REMIND_AT[0]` (fires at 4,6,7,9...) | c | test_reminder_pattern_over_twenty_identical_calls |
| Q11 | gentle/firm selection moved to count 5 | c | test_third_identical_call_ends_with_the_reminder |
| Q12-Q14 | count +2; initial 0; initial 2 | c | test_third_identical_call_ends_with_the_reminder |
| Q15 | `==` -> `!=` on the key compare | d | test_third_identical_call_ends_with_the_reminder |
| Q16 | drop the key compare (total rather than consecutive) | d | test_different_calls_are_never_merged |
| Q17 | sort_keys False (seeds 0-39) | d | test_key_order_does_not_matter (seed 0) |
| Q18 | separators with spaces | d | test_size_cap_boundary |
| Q19 / Q20 | name dropped / args dropped from the key | d | test_different_calls_are_never_merged |
| Q21 | name concatenated with args JSON (name/args boundary) | d | test_size_cap_boundary |
| Q22 / Q23 | digest cut to 8 / 1 hex chars | d | test_digest_is_full_and_distinct / test_names_are_exact |
| Q24-Q26 | cap `>=`; cap `> MAX+1`; MAX 99,999 | d | test_size_cap_boundary |
| Q27 | cap check disabled (`if False`) | f | test_unkeyable_arguments_fail_open_..._[7] |
| Q28 / Q29 | chain not cleared on over-cap key / on exception | e | test_an_unkeyable_call_resets_the_chain |
| Q30 | `except BaseException` | f | test_a_keyboard_interrupt_is_not_swallowed |
| Q31 | `except (ValueError, TypeError)` | f | test_unkeyable_arguments_fail_open_..._[5] |
| Q32 | `ensure_ascii=False` | f | test_unicode_arguments_are_tracked |
| Q34 | `default=str` (unserialisable args become keyable) | f | test_unkeyable_arguments_fail_open_..._[0] |
| Q35 | `reset()` becomes `pass` | e | test_a_new_prompt_resets_the_count |
| Q36 / Q38 / Q39 | FIRM left unformatted; `\n` instead of `\n\n`; count+1 in the text | m | pinned-text tests |
| Q37 / Q42 / Q43 | name / `repr(arguments)` appended to the notice | g | test_third_identical_call_ends_with_the_reminder / test_reminder_pattern_over_twenty_identical_calls |
| Q40 | stored count always 1 | c | test_third_identical_call_ends_with_the_reminder |
| L01 / L02 | reset removed from `run()` / `resume()` | e | test_a_new_prompt_resets_the_count / test_resume_restarts_the_count_and_the_rerun_path_counts |
| L03 | count after the tool run | c | test_a_tool_that_edits_its_own_arguments_cannot_merge_calls |
| L04 | notice appended before `redact_secrets` | g | test_the_reminder_survives_redaction_and_is_not_altered_by_it |
| L05 | notice dropped | c | test_third_identical_call_ends_with_the_reminder |
| L06 | error/denial/unknown results not counted | c | test_a_guard_denial_is_counted_and_gets_the_reminder |
| L07 | UNCERTAIN path counted | c | test_uncertain_results_from_a_missing_tool_or_a_guard_are_not_counted |
| L09 / L10 | key uses `call.id` / `{}` instead of the arguments | d | test_third_identical_call_ends_with_the_reminder / test_different_calls_are_never_merged |
| L11 | one shared module-level reminder | e | test_two_loop_instances_share_no_state |
| L12 | reset at every `_drive` iteration | e | test_third_identical_call_ends_with_the_reminder |
| L14 | `raise AgentLoopError` when a notice would be sent (veto) | a | test_third_identical_call_ends_with_the_reminder |
| L15 | skip the tool and return the notice at count 5 | a | test_reminder_pattern_over_twenty_identical_calls |
| L17 | notice `.strip()` | m | test_third_identical_call_ends_with_the_reminder |
| L20 | observe a copy of the arguments | eq intended, but killed | test_unkeyable_arguments_fail_open_..._[6] (the 8-shape test passes a non-dict; `dict()` of it raises). Not equivalent for non-dict input, so it is a legitimate kill. |
| A1 | `_execute` runs the tool with `{}` | a | test_loop.py::test_executes_tool_call_then_finishes |
| A2 / A8 / A10 | observe or `_execute` adds a key / clears the arguments / sets `advisory` | a | test_third_identical_call_ends_with_the_reminder (shared `K` dict) / test_reminder_never_quotes_... |
| A3 | tool name upper-cased on the run | a | test_third_identical_call_ends_with_the_reminder |
| A5 | the tool is run twice when a notice is due | a | test_third_identical_call_ends_with_the_reminder |
| A6 | notice replaces the result (lose the result) | b | test_third_identical_call_ends_with_the_reminder |
| A7 | `reversed(pending)` (reorder) | a | test_uncertain_results_are_neither_counted_nor_given_a_reminder |
| A12 / A14 | `_execute` drops the `text` argument / sets `text` to `z` | a | test_unkeyable_..._[6] / test_loop.py::test_executes_tool_call_then_finishes |
| A4* | guard sees a call with `{}` | a | killed only by the full suite (16 failed vs 11 baseline); not by the 4-file set |

(* A4, L13, A11 and A13 were additionally run against the full suite, 100 s each, foreground. The tar copy has 11 baseline failures in `tests/test_lint_harness.py` because it lacks `skills/` and `.claude/`; the unmutated tar full run is `11 failed, 1392 passed, 10 skipped`. A4: `16 failed, 1387 passed` = killed. L13 and A11: `11 failed, 1392 passed` = identical to baseline = SURVIVED the full suite.)

Survivors:

| id | mutation | class | verdict |
|---|---|---|---|
| Q10 | `count == REMIND_AT[0]` -> `count <= REMIND_AT[0]` | c | EQUIVALENT: counts 1 and 2 return earlier, so the branch is only reached with count >= 3 |
| Q33 | `.encode("ascii")` -> `.encode("utf-8")` | d | EQUIVALENT: `json.dumps` default `ensure_ascii=True` makes the text pure ASCII |
| Q41 | store `min(count, 8)` | c | EQUIVALENT: a count >= 9 is only compared with REMIND_AT, and the stored 8 yields 9 again, silent either way (differs only in int size) |
| L08 | `reset()` at the top of `_uncertain` | e | EQUIVALENT: `_uncertain` is called once, from `resume()` (loop.py:185), right after the reset at :178 |
| L16 | `call.arguments.clear() if False else None` | eq | EQUIVALENT by construction (dead code); control showing the runner reports survivors |
| L18 / L19 | the reset moved after `messages = [...]` / after `_save` | e | EQUIVALENT: the checkpoint hook never reads the counter |
| A9 | `_run_tool` receives a copy of the call | eq | EQUIVALENT for the tools and guards in the tree (a copy of a frozen dataclass with a copied dict) |
| **A11** | `_execute` runs the tool on `ToolCall(call.id, call.name, dict(call.arguments, _x=1))` (a C8-owned line) | **a** | **FALSE-PASS: survives the 4-file set and the full suite (`11 failed, 1392 passed`, identical to baseline)** |
| **L13** | `_run_tool` calls `tool.run(dict(call.arguments, _x=1))` (existing line, outside the C8 hunks) | **a** | **same gap, in unchanged code; survives the full suite** |
| A13 | `_execute` runs the tool on a call whose `id` is changed (`'x' + call.id`) | a | same gap for the id the guard sees; survives the 4-file set (not run on the full suite) |

Why A11 is a FAIL and not an observation. Before writing FAIL I checked the guards from the QA brief. Guarded elsewhere on the call path: no, no test or code compares the `arguments` the tool receives with the model's `arguments` (`tests/test_repeat_reminder.py:56` `_Tool.run` ignores them; `tests/test_loop.py` uses `EchoTool`, which reads only `arguments["text"]`, so an injected extra key is invisible). Declared deliberate in the design: no, N10 says the reminder never changes control flow and "the tool runs every time", and the fixed bar names "alter a tool call" as class (a). Fixable only by violating an outside interface: no. It is not on the KNOWN list (F1, F2, F3, tuple/list collision, padding, small clip budget, flaky timing test). So the PASS condition "zero surviving non-equivalent class (a) mutants" fails.

## Defects

1. tests/test_repeat_reminder.py (whole file, class (a) pin missing); loop.py:233-234 is the C8 line that a mutant can alter without any test noticing. Expected (design N10 / bar (a)): the tool and the guard receive exactly the model's name, id and arguments, for the counted calls and for the call that carries a notice. Actual: no test asserts it, so mutant A11 (`dict(call.arguments, _x=1)` on the C8 line) survives all 1403 tests. Exact kill test (follow-up for the builder, not applied by QA): in `test_it_never_vetoes_skips_or_changes_a_call`, replace the plain `_Tool` with a recording tool that stores `dict(arguments)` per run and a guard that already stores `call`, then assert `recorded == [K] * 10` and `[(c.id, c.name, c.arguments) for c in seen] == [("c1", "echo", K), ... ("c10", "echo", K)]` (a fresh `{"x": 1, "y": [2]}` per call so a shared-dict mutation cannot hide). That kills A11, A13, L13 and A4 in the first 61 tests. A mutation-only pin: run `tests/test_repeat_reminder.py` against mutant A11 and expect a failure.
2. observation: loop.py:213/225 area is untouched by C8, but L13 (`tool.run(dict(call.arguments, _x=1))`) shows the same pin is missing for the pre-existing `_run_tool` too. Pre-existing gap, same test closes it.
3. observation (not a defect of C8): `observe` builds the full JSON text before checking the 100,000-char cap, so a hostile 100 MB argument costs about 0.3 s and 300 MB of transient memory per call (linear, no exception). Same cost the design quotes in Design 10; a bounded encoder would be a separate change.
4. observation: my first mutant run was invalid (missing `.gitignore` in the scratch tar made the baseline itself fail, so every mutant looked KILLED); reported above, discarded, re-run on the identical list. Any reviewer reproducing the batch must confirm the unmutated tar copy is green first (`175 passed, 4 skipped` for the 4-file set).

## Deviations and surprises

- The mutation set grew to 63 (43 on repeat_reminder.py, 20 on loop.py) plus 14 class-(a) follow-ups (A1-A14). The 14 were run only because L13 looked like a false-pass; they are not a second general batch.
- A1, A3, A5-A8, A10, A12, A14 (alter/skip/reorder/lose result) all die; the live probes confirm the real code never alters the call. The single failing point is the missing exact-argument pin, a test-strength gap, not a behaviour defect.
- Scratch files and the three tar copies were created only in the scratchpad and removed afterwards; the real repo `git status` is unchanged (G22).
