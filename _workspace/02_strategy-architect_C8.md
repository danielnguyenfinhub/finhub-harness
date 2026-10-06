# C8 design: advisory repeat-call reminder in the agent loop (revision 3)

Item: C8 (Pick 9). Shape: runtime module, effort S. Code is delivered as `_workspace/02_strategy-architect_C8.patch` (sha256 `e958910679608d6d0f8e990b68b73f26e3776f3a4f05e6d8e09c796aa78ca5ef`, 697 lines, applies with `git apply` on origin/main = HEAD `0474fc5`; three files: `loop.py` +16/-2, new `runtime/repeat_reminder.py` 64 lines, new `tests/test_repeat_reminder.py` 563 lines). Mutation runner: `_workspace/02_strategy-architect_C8_mutate.py`, its output `_workspace/02_strategy-architect_C8_mutate.out`. Everything below was run on a tar copy in the scratchpad, never in the repo.

## Revision 3

Round 2 of the judge: UPHELD 40, REJECTED 1 (B6, prose). Changed in this file only (patch, tests, runner and code untouched, patch sha256 `e958910679608d6d0f8e990b68b73f26e3776f3a4f05e6d8e09c796aa78ca5ef` re-verified): B6, Design 9 now states the rev-2 order (`observe` runs before the tool, fails open, returns only text, cannot change the call) in place of "the call has already run" and "`observe` runs after the tool"; N1 line range `:21-31` corrected to `:21-30` and N12 `:21` corrected to `:19` (both `CHANGED r3`). Follow-ups (not built): F1 a 2-hex-digit digest prefix is not killed by the 500-key test (only a 1-char cut is); F2 the escaped-length bound is pinned only by a command (`_call_key("echo", {"x": "é" * 16000}) is not None` and `* 17000) is None`), not by a test; F3 some tests are tight to the current refactor; tuple/list key collision and padding evasion (as in revision 2).

## Revision 2

Round 1 of the judge (`_workspace/02_adversarial-risk-judge_C8_r1.md`): UPHELD 32 (every A and N row), REJECTED 5 (B1-B5, all surviving non-equivalent mutants of the Pick 9 bar, none a citation). Each failure was reproduced on revision 1 first: the 14 non-equivalent Z mutants all survived the 50 revision-1 tests (`C8_REV=1 C8_ONLY=Z` run of the runner), and the new mutating-tool test fails on the revision-1 `_execute`. Then fixed:

| id | bar | what changed in rev 2 | killed by |
|---|---|---|---|
| B1 | (f) | `test_other_exceptions_fail_open`: `MemoryError` and `OverflowError` raised from a mapping's `items()` give `""` and leave the call unharmed (also through the full loop) | Z4, Z5 |
| B2 | (d) | `test_names_are_exact`, `test_values_are_exact` (5 pairs: case, inner space, null vs empty, the text "null" vs empty, leading space), `test_digest_is_full_and_distinct` (500 keys, all 64 hex chars) | Z6, Z7, Z8, Z9, Z35, Z1 (and K14 stops being a survivor) |
| B3 | (c) | `test_unicode_arguments_are_tracked` (Vietnamese text), `test_empty_result_gets_the_reminder`, `test_huge_result_gets_the_reminder` (200,000-character result) | Z2, Z14, Z15 |
| B4 | (e) | `test_resume_with_a_new_user_message_resets` (the `team.py:371` path: history plus a new user message, no pending call), `test_chain_crosses_turns_into_a_batch` ([K] then [K, K]) | Z17, Z21 |
| B5 | (d) | S17 is NOT equivalent (accepted): the notice is now computed BEFORE `_run_tool` in `_execute` (two lines), so a tool that edits its own arguments in place cannot change the key. New `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls` (A, B, A where the tool pops a key from its arguments: no run; three real repeats still draw the reminder). S17 is redefined as "count after the run (the rev 1 order)" and dies. Real equivalents now: T25, T26, S18, Z11 (stored count capped at 9) and Z36 (name and arguments swapped in the key). K14 (`hash()` key) is no longer a survivor | S17 |
| w1 | wording | A9 re-worded (see CHANGED r2 row): D49 counts before it delegates to later listeners, but still after the tool ran | none (prose) |
| w2 | one-line test | `test_nan_arguments_are_tracked` (judge F1/Z3: `allow_nan=False` would make NaN arguments untracked) | Z3 |
| w3 | one line | the 100,000-character bound counts ASCII-escaped JSON characters (a non-ASCII character costs up to 6); stated in Design 10, in the `MAX_KEY_CHARS` comment and in Does not cover | none (prose) |
| w4 | one line | a small `clip_budget_tokens` can clip the notice off the tail of a result: Does not cover | none (prose) |

Decision on B5 and the consequence on every path (the order D49 uses is "observe, then delegate": `index.ts:214-215`; but D49's post-execute listener runs after the tool, so counting before the tool is net-new here). Guard denial: the call is counted before the guard is asked, the denial text still carries the notice (same results, test unchanged). Unknown tool and tool error: same. `UNCERTAIN_RESULT` returns: untouched (they never reach `_execute`). Resume rerun path: through `_execute`, same. A `BaseException` or a guard that raises: the chain has advanced, the run ends, and the next `run()`/`resume()` resets first, so no leak. A tool result's text never feeds the key (it is not computed yet), which also makes the old "key ignores output" mutants cheaper to kill. Whole suite and whole mutation set re-run on a scratch tar copy of HEAD 0474fc5: results below.

Follow-ups (not built): F2 tuple/list and `{1: "a"}`/`{"1": "a"}` merge (unreachable from model JSON); evasion by padding arguments past the bound or changing any argument (same class as D49's exact-match limit); the judge's other 20 killed Z mutants need nothing.

## Source

Backlog row C8 (`_workspace/01b_capability-scout_backlog.md:55`): "Advisory repeat-call reminder in the agent loop (3/5/8 identical calls); never vetoes", sources D49 and A27, target `runtime/loop.py`, MIT adapt, score 0.80. Re-opened:

- **D49** (`01_reference-miner_deepseek_harness_portmap.md:90`) -> `references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts`. Opened lines: key `:194-195`, chain `:196-198`, threshold test `:199`, tier `:200-202`, gentle text `:63-67`, detailed text `:70-79` (quotes tool name and arguments), canonicalisation `:89-105`, denied calls counted `:184-188`, post-execute enrich-never-veto `:213-224`, user-message reset `:229-231`, per-agent `WeakMap` `:173`, include/exclude `:176-179`, preview cap `:113-121`. README `:25-31` (chain semantics, "In-memory only. A session resumed from persistence starts with a fresh chain") and `:90` ("Past the highest threshold a chain goes silent").
- **A27** (`01_reference-miner_autogpt_portmap.md:47`) -> `references/autogpt/classic/forge/forge/components/watchdog/watchdog.py`. Opened `:32-63`: a call is a repeat when its name and arguments equal the previous call's (`:51-54`); the reaction is a rewind and a retry on the stronger model (`:57-63`). Only the detection idea is used; the reaction is not adopted (it vetoes). Path is the classic tree, never `autogpt_platform` (`references/autogpt/LICENSE:4`: everything outside `autogpt_platform` is MIT).
- Own code re-read: `src/master_finhub/runtime/loop.py` (all 234 lines of origin/main), `runtime/context.py` (`balanced_cuts` `:83-95`, `fit` `:169-189`, `estimate_message` `:55-60`), `tools/secret_scan.py` (rule table `:24-60`, `redact_secrets` `:98-103`), `tests/test_loop.py`, `tests/test_secret_scan.py:170-215`, `runtime/fake_llm.py`, `orchestration/modes/team.py:350-376`, `evals/runner.py:150-165`.

Facts about the current runtime that the design rests on (all re-run, see the Proof section):

- origin/main `loop.py:218-220`: `_execute(call)` is `redact_secrets(self._run_tool(call))[0]`. It is reached from exactly two places: the `_drive` pending loop (`:186`) and the resume rerun branch of `_uncertain` (`:213`). Unknown-tool text, guard denial text (`:229-230`) and tool-error text (`:233-234`) are all produced inside `_run_tool`, so every tool message the loop stores goes through `_execute`. `UNCERTAIN_RESULT` (`:211`, `:215`) does not: those two returns never run the call.
- `max_steps` raises at origin/main `:188-192`, after the pending calls of the last turn have run and been saved (`:185-187`).
- `LoopSnapshot` holds only `step` and `messages` (`:84-85`); `CheckpointHook` receives it (`:100`). Nothing in it can carry a counter.
- `ScriptedLLM` (`runtime/fake_llm.py:10-22`) issues one `echo{"text": X}` call and then answers; it cannot issue the same call three times. The tests therefore use a test-local scripted LLM in the style of `QueueLLM` (`tests/test_loop.py:16-25`) and a test-local tool named `echo`.

## Target

- NEW `src/master_finhub/runtime/repeat_reminder.py` (64 lines): `RepeatReminder`, `REMIND_AT`, `GENTLE`, `FIRM`, `MAX_KEY_CHARS`, `_call_key`. A separate module because the logic is unit-testable without a loop and `loop.py` stays at the audited shape; `secret_scan.py` is the precedent.
- EDIT `src/master_finhub/runtime/loop.py`: one import, one attribute, two `reset()` calls, a rewritten `_execute`, three docstring lines (the attribution). Six hunks, none touching `_drive`, `_uncertain`, `_run_tool`, the guard call or the `max_steps` raise.
- NEW `tests/test_repeat_reminder.py` (40 test functions, 61 collected cases). `tests/test_loop.py` is unchanged (the backlog proof `pytest tests/test_loop.py -k repeat` becomes `pytest tests -k repeat`; the file name carries the keyword). No existing test is modified.
- No new dependency (stdlib `json`, `hashlib`). No prose, skill or agent file is touched.

## Design

### Decisions, each with its evidence

**1. Canonical call key.** `sha256` of `json.dumps([name, arguments], sort_keys=True, separators=(",", ":"))`, as ASCII text. `sort_keys=True` sorts every nested dict, so `{"b":1,"a":2}` and `{"a":2,"b":1}` give the same key, and so do nested dicts inside lists; list order is data and stays significant. The name is part of the key, so the same arguments on two tools are two calls. Evidence: D49 builds `[exec.name, canonical]` and canonicalises by a deep key sort then stringify (`index.ts:194-195`, `:89-105`; README `:25`). Differences from D49, all deliberate: the key is a digest, not the string (memory bound, decision 10); Python's JSON keeps `1`, `1.0` and `true` apart where JavaScript's `JSON.stringify(1.0)` is `1` (fewer merges, so fewer reminders, never a false one); tool output and call id are not in the key (tests `test_the_key_ignores_the_tool_output`, mutants K15, K16). Non-JSON-serialisable arguments (`object()`, sets, bytes, mixed-type keys, circular references, nesting deep enough to hit `RecursionError`, a mapping whose `items()` raises) make `json.dumps` raise; the arguments are then not trackable (decision 9). Over-size arguments (decision 10) give no key either.

**2. Counting window.** Consecutive identical calls in one `AgentLoop` instance: a call equal to the previous counted call increments the run, any different call restarts the run at 1. A,B,A,B never counts. A call that has no key (decision 9) counts as a different call, so it restarts the chain. Evidence: D49 `index.ts:196-198` (`chain.key === key ? chain.count + 1 : 1`); A27 compares only with the previous call (`watchdog.py:51-54`). Not the total in a run: K,K,L,K is not a third K (test `test_only_consecutive_calls_count_and_a_different_call_resets`, mutants C3, C4, C11). Known limit, stated in Does not cover: a model alternating two calls is never flagged (D49 has the same limit).

**3. Reset rules.**
- `run()` resets (a new user prompt starts a new chain). Evidence: D49 resets when the context holds a user message (`index.ts:229-231`, spec `tests/repeat-tool-reminder.spec.ts:233-250`). `AgentLoop` has exactly two entry points that can take a new user prompt, `run()` and `resume()`; `team.py:371` feeds a new user message through `resume()`, so `resume()` resets too.
- `resume()` resets. The counter is in memory only and the snapshot has no field for it (`loop.py:84-85`). Evidence: README `:31`, "A session resumed from persistence starts with a fresh chain". Cost, accepted: after a crash at most two extra repeats before the first reminder. Alternative rejected: deriving the chain from `snapshot.messages` would work on uncompacted history only, and adding a snapshot field changes the persisted checkpoint format that `tests/test_checkpoint.py` pins.
- Compaction does not reset. The chain lives on the loop object, not in the messages, and `ContextManager.fit` (`context.py:169-189`) only rewrites the message list. The synthetic summary message is `role="user"` (`context.py:132`), which D49 would not count as a user turn either (it checks `source.kind === 'user'`, `:230`). Test `test_compaction_neither_resets_the_count_nor_splits_a_pair` forces a summary before the 8th call; mutant S5.
- A raised run does not leak: `run()` resets at its start, not its end (test `test_a_run_that_raised_does_not_leak_its_count_into_the_next_run`, mutant S4).
- The two `UNCERTAIN_RESULT` returns in `_uncertain` neither count nor reset (the call did not run; the chain is already empty there because `resume()` just reset it). Tests `test_uncertain_results_*`, mutants S9, S9b. The rerun branch of `_uncertain` goes through `_execute` and counts (test `test_resume_restarts_the_count_and_the_rerun_path_counts`, mutant S8).
- `max_steps`: untouched. The counter is neither read nor changed by the raise; the third result is still saved before the raise (test `test_max_steps_still_raises_and_the_last_result_is_saved_with_its_reminder`).

**4. Thresholds 3, 5, 8 and 9+.** `REMIND_AT = (3, 5, 8)`, tested as exact membership (`count not in REMIND_AT` returns no text). Calls 1, 2, 4, 6, 7 and every call from the 9th on get no text; the 20-call test pins each position. Evidence: D49 default `[3, 5, 8]` (`index.ts:29`, `:46`), reminder only when the count is in the set (`:199`), "Past the highest threshold a chain goes silent" (README `:90`). Fixed constants, no config: D49 validates configurable thresholds (`:128-141`); nothing here needs them (YAGNI). Tier: the text for `REMIND_AT[0]` is the short one, later counts get the firmer one (`index.ts:200-202`). Boundary tests and mutants: every member +-1 (T1-T6), an extra 9 and 12 (T7, T8), a dropped member (T9, T10), inverted and `<`/`<=`/`>` forms (T11-T15).

**5. Reminder text.** Two fixed texts, written fresh (no 8-word run in common with D49, checked: 0 hits over all 4,740 distinct 8-word runs in the D49 package and the watchdog directory). The 3rd call gets `GENTLE`; the 5th and 8th get `FIRM` with the integer count substituted. The text is a pure function of the count: it never contains the tool name, the arguments or any tool output. D49's detailed tier does quote the tool name and up to 500 characters of the canonical arguments (`index.ts:70-79`, `:118-121`); that is not adopted, because arguments can carry paths, ids and credentials that the loop's own `redact_secrets` would then have to catch in a second place, and because the name of an unknown tool is model-controlled text. Tests: `test_reminder_texts_are_pinned` (literal full text), `test_reminder_never_quotes_arguments_output_or_tool_name` (sentinels), mutants S13-S15, T21-T24.
The text also survives the C3 scan unchanged: `redact_secrets(text) == (text, ())` for 3, 5 and 8 (test `test_the_reminder_survives_redaction_and_is_not_altered_by_it`).

**6. Where it is appended.** At the end of the same tool message's content, in `_execute`, AFTER `redact_secrets`, with the count taken BEFORE the tool runs: `note = self._repeat.observe(call.name, call.arguments); return redact_secrets(self._run_tool(call))[0] + note`, with the separator `"\n\n"` inside `observe`. One call site covers every path that stores a tool message: success, unknown tool, guard denial, tool error and the resume rerun. Order matters: the `private-key` rule runs to the end of the text when there is no END marker (`secret_scan.py:28-29`, `\Z`), so a notice added before the scan would be swallowed whenever a tool output ends inside a key block (test case "unclosed", mutant S6). The notice is fixed text with no secret shape, so scanning it adds nothing. Counting before the run keeps the key independent of anything the tool does to its own arguments (B5, test `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls`, mutant S17). The docstring of `_execute` ("Every tool result, denial and error text passes the secret scan before it is stored") stays true: every untrusted character is scanned; the appended constant is not untrusted.
- *Pair never split.* No message is added; the reminder is part of `Message("tool", ..., tool_call_id=call.id)`. `LoopSnapshot.__post_init__` re-validates pairing on every save (`loop.py:87-88`), and the test records every snapshot through the checkpoint hook. A turn with three calls keeps `c1, c2, c3` in order with the reminder on `c3` (test `test_the_call_and_result_pair_is_never_split_or_lost`; mutant S16 appends a separate user message and dies).
- *Guard denial.* Counted, and the denial text carries the reminder. The guard is asked exactly once per call (the reminder code never calls it). Evidence: D49 counts denied calls ("a model hammering a denied call is exactly the loop worth breaking", `index.ts:184-188`; README `:28`). Test `test_a_guard_denial_is_counted_and_gets_the_reminder`, mutant S7.
- *Error path.* A tool exception becomes `Error: tool '<name>' failed: ...` (`_run_tool`), counted, same suffix. An unknown tool name is counted too (test `test_tool_errors_and_unknown_tools_are_counted_too`).
- *Compaction.* `ContextManager.fit` clips a long tool result to head 4/5, marker, tail 1/5 (`context.py:74-77`); the suffix is a few hundred characters at the very end, so it lands in the tail (test `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`). Old turns replaced by the deterministic summary lose their suffix; that is acceptable for advice about the latest calls. `balanced_cuts` (`context.py:83-95`) counts roles and tool calls only, so a longer tool content cannot unbalance it.
- *Transcript recording.* The suffix is stored in the checkpoint like any tool text (`_save`, `loop.py:210-212` in the patched file). After a resume the transcript still shows an old reminder while the counter restarts; harmless, advisory.
- *MCP tools.* MCP tools are ordinary `Tool` objects in `self._tools`; their text has already been redacted by the client, and the loop scan runs again. Nothing special. D49 does not special-case them either (its `exclude: [mcp_*]` example is an option, not a default; no include/exclude is adopted, `index.ts:176-179`).

**7. Memory bound.** One attribute per loop: `(digest: 64-char str, count: int)`. A 90,000-character argument and 2,000 distinct calls leave `len(repr(vars(r))) < 200` (test `test_state_is_one_digest_and_one_count_whatever_the_arguments`; mutant K13 stores the text and dies). `count` is an int that grows with the run; it is never stored per key.

**8. Concurrency.** `_drive` runs the calls of a turn one after another (`loop.py:192-194` patched), so a loop executes one tool at a time. Each `AgentLoop(` call site in `src` builds its own instance (cli `:132`, server `app.py:138`, subagent `:315`, team `:356`, evals `runner.py:153`); the state is an instance attribute, never module level. The one shared-instance case is team mode, where one loop per member is driven by one worker thread (`team.py:356-373`). The pair `(digest, count)` is replaced by a single tuple assignment, so interleaved use of one instance by two threads could only mix counts, never raise or corrupt. No lock (comment in the class docstring). Tests: a nested run of a second loop inside a tool call of the first (`test_two_loop_instances_share_no_state`) and eight threads each with their own loop (`test_threads_with_their_own_loops_each_see_their_own_pattern`); mutant S10 (module-level state) dies on both.

**9. Fail open.** The whole of `observe` is inside `try ... except Exception`, and the handler clears the chain and returns `""`. So: no exception from odd arguments escapes (`TypeError`, `ValueError`, `RecursionError`, `OverflowError`, `MemoryError`, a custom exception from a mapping's `items()`; test `test_other_exceptions_fail_open`); the call has not run yet when `observe` runs (it is the first line of `_execute`, `loop.py:233`), and nothing `observe` does can alter the call or its result, so the tool then runs and its result is stored unchanged; the chain restarts. `KeyboardInterrupt` and `SystemExit` are not caught (test `test_a_keyboard_interrupt_is_not_swallowed`, mutant F2). Nothing here can veto: `observe` runs before the tool, fails open on every `Exception` (it then returns `""`), only returns a string, and `_run_tool(call)` is called with the same `call` whatever it returned, so it cannot skip, replace or change the call. Tests: eight unkeyable argument shapes through the full loop (`test_unkeyable_arguments_fail_open_...`), chain reset after an unkeyable call for both an exception and an over-cap case (`test_an_unkeyable_call_resets_the_chain`; mutants F4, F7).

**10. Huge arguments.** `json.dumps` of the call is built once per call and measured: if the text is longer than `MAX_KEY_CHARS = 100_000` ASCII-escaped JSON characters (a non-ASCII character costs up to 6, so Vietnamese text reaches the bound sooner than the source length suggests) there is no key (fail open, no reminder, chain restart); otherwise only its digest is kept. The work is linear in the argument size, the same order as `estimate_message`'s own `json.dumps(call.arguments, sort_keys=True)` (`context.py:58`) that runs on every turn when a context policy is set. Measured here (CPython 3.11): 100 KB string 0.3 ms, 1 MB 2.9 ms, 20 MB 67 ms, 5 million-element list 0.32 s, 5,000-deep nesting 0.2 ms (the C encoder raises `RecursionError`). A repeated call with over-cap arguments therefore draws no reminder; D49 keys on the full string (`index.ts:113-117`), here the cap is a bounded-cost choice. Boundary tests: exactly at the cap is keyed, one over is not (`test_size_cap_boundary`, mutants K6-K11).

**11. Determinism.** The key is `sha256` of ASCII JSON; there is no `hash()`, clock, randomness or iteration over a set (`grep -nE "\bhash\(|random|time\.|datetime"` on the module returns nothing). Same call sequence, same output text, whatever `PYTHONHASHSEED`: a child process under seeds 0, 1 and 4242 prints the same list (`test_output_does_not_depend_on_the_hash_seed`), and the ordering mutants run under seeds 0-39.

### What is adapted and what is new

Adapted from D49 (MIT, idea only, no code copied): consecutive-chain counting, key-sorted canonical arguments, thresholds 3/5/8 with silence elsewhere, first-tier text distinct from later tiers, count denied calls, reset on a user prompt, fresh chain on resume. Adapted from A27 (MIT): repeat means same name and same arguments as the previous call; the rewind and stronger-model retry are not adopted. Attribution lines are in the docstring of `repeat_reminder.py` and `loop.py`. Net-new: appending inside the tool message after redaction, a fixed content-free text, the digest key and its size cap, `Exception`-only fail-open, per-instance state, the Python key semantics. Not adopted from D49: configurable thresholds, include/exclude patterns, the argument preview, the separate plugin-labelled message (`index.ts:57`, `:203-206`).

### Quant guardrails

No backtest, pricing or verifier code is touched. The eval runner uses `AgentLoop` (`evals/runner.py:153`) and grades only the final answer and workspace files (`:161-162`), so the reminder cannot change a verifier. It is content-free (no task text, label, ground truth or output), so it cannot leak a held-out answer; it is appended identically in every arm. Fees, borrow cost, slippage, look-ahead, survivorship and train/test leakage: not applicable. One real effect is stated in Does not cover: an eval case whose agent repeats one call three or more times sees different tool text than before, so a baseline recorded before this change can differ for that case.

### Inserted code in full

The code below is the file content of the patch; the patch is authoritative (sha256 above).

#### `src/master_finhub/runtime/repeat_reminder.py` (new)

```python
"""Advisory repeat-call reminder: text for the 3rd, 5th and 8th identical call in a row.

Adapted (idea only, own code) from the MIT-licensed deepseek-harness
``references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts``: key-sorted
canonical arguments (:103), a chain of consecutive identical calls (:189-198), reminders at
counts 3/5/8 (:199) and a gentle first tier (:200); and from autogpt classic
``references/autogpt/classic/forge/forge/components/watchdog/watchdog.py:32`` (MIT), which
compares each call with the previous one. Net-new: a fixed text that never quotes the tool
name, arguments or output, a digest key with a size cap, and fail-open error handling.
It never vetoes, skips or reorders a call: the caller appends the returned text to the result.
"""

from __future__ import annotations

import hashlib
import json
from typing import Final

REMIND_AT: Final = (3, 5, 8)  # a count outside this tuple, 9 and above included, stays silent
MAX_KEY_CHARS: Final = 100_000  # ASCII-escaped JSON chars; a longer call is not tracked
GENTLE: Final = (
    "[advisory] The same tool call, with the same arguments, has now been issued 3 times in a "
    "row. Read the earlier results again; if the task is unfinished, change the arguments or "
    "the approach."
)
FIRM: Final = (
    "[advisory] This exact call (same tool, same arguments) has now been issued {count} times "
    "in a row. More repeats are unlikely to help: use a different tool or different arguments, "
    "or give your final answer with what you have."
)


def _call_key(name: str, arguments: object) -> str | None:
    """Digest of the key-sorted JSON form of (name, arguments); None when over the size cap."""
    text = json.dumps([name, arguments], sort_keys=True, separators=(",", ":"))
    if len(text) > MAX_KEY_CHARS:
        return None
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class RepeatReminder:
    """One chain per instance: (digest, run length) of the latest call. Not locked: advisory."""

    def __init__(self) -> None:
        self._last: tuple[str, int] | None = None

    def reset(self) -> None:
        self._last = None

    def observe(self, name: str, arguments: object) -> str:
        """Count one call; return the text to append to its result, or "". No Exception escapes."""
        try:
            key = _call_key(name, arguments)
            if key is None:
                self._last = None
                return ""
            count = self._last[1] + 1 if self._last is not None and self._last[0] == key else 1
            self._last = (key, count)
            if count not in REMIND_AT:
                return ""
            return "\n\n" + (GENTLE if count == REMIND_AT[0] else FIRM.format(count=count))
        except Exception:  # noqa: BLE001 - advisory only: odd arguments must not fail a call
            self._last = None
            return ""
```

#### `src/master_finhub/runtime/loop.py` (diff against origin/main)

```diff
diff --git a/src/master_finhub/runtime/loop.py b/src/master_finhub/runtime/loop.py
index f828de5..5f9e472 100644
--- a/src/master_finhub/runtime/loop.py
+++ b/src/master_finhub/runtime/loop.py
@@ -5,6 +5,9 @@ Control flow ported (idea only, not code) from the MIT-licensed deepseek-harness
 (``ReactLoopAgent.step``, lines ~332-420): call the model; if the assistant message has no
 tool calls the run is completed, otherwise execute the tool calls, append their results and
 loop. Streaming, sessions, hooks and abort handling are intentionally out of scope for slice 1.
+The advisory repeat-call reminder (``repeat_reminder.py``) is adapted from the MIT-licensed
+deepseek-harness
+``references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:189``.
 """
 
 from __future__ import annotations
@@ -13,6 +16,7 @@ from collections.abc import Callable
 from dataclasses import dataclass, field
 from typing import Any, Final, Literal, Protocol
 
+from master_finhub.runtime.repeat_reminder import RepeatReminder
 from master_finhub.tools.secret_scan import redact_secrets
 
 DEFAULT_MAX_STEPS = 20
@@ -161,14 +165,17 @@ class AgentLoop:
         self._tools = {t.spec.name: t for t in tools}
         self._specs = [t.spec for t in tools]
         self._max_steps = max_steps
+        self._repeat = RepeatReminder()
 
     def run(self, prompt: str) -> str:
+        self._repeat.reset()  # a new user prompt starts a new chain
         messages = [Message(role="user", content=prompt)]
         self._save(0, messages)
         return self._drive(messages, 0, [])
 
     def resume(self, snapshot: LoopSnapshot, *, in_flight: InFlightPolicy = "stop") -> str:
         """Continue from a saved snapshot. The first save is a claim: see CheckpointStore."""
+        self._repeat.reset()  # the chain is not in the snapshot, so it restarts here
         self._save(snapshot.step, list(snapshot.messages))
         if snapshot.status == "completed":
             return snapshot.messages[-1].content
@@ -216,8 +223,15 @@ class AgentLoop:
         raise ResumeBlocked(call.name, call.id, step)
 
     def _execute(self, call: ToolCall) -> str:
-        """Every tool result, denial and error text passes the secret scan before it is stored."""
-        return redact_secrets(self._run_tool(call))[0]
+        """Every tool result, denial and error text passes the secret scan before it is stored.
+
+        The repeat notice is fixed text appended after the scan, inside the same tool message: a
+        private-key match runs to the end of the text and would swallow it, and the pair stays
+        whole. It is counted before the call runs, so a tool that edits its own arguments in place
+        cannot change the key.
+        """
+        note = self._repeat.observe(call.name, call.arguments)
+        return redact_secrets(self._run_tool(call))[0] + note
 
     def _run_tool(self, call: ToolCall) -> str:
         tool = self._tools.get(call.name)
```

## Proof

Run on a tar copy (`src tests pyproject.toml` of origin/main plus the patch) in the scratchpad, `python -B`, repo `.venv` (CPython 3.11.15), in this order, each in the foreground:

| check | command | result |
|---|---|---|
| baseline before the patch | `env -u PYTHONUNBUFFERED pytest -q -p no:cacheprovider` (revision 1 on HEAD 0474fc5, from the judge's run) | 1387 passed, 10 skipped |
| new tests alone | `env -u PYTHONUNBUFFERED pytest -q tests/test_repeat_reminder.py` | 61 passed in 0.32 s |
| full suite, unbuffered off | `env -u PYTHONUNBUFFERED pytest -q -p no:cacheprovider` | 1403 passed, 10 skipped in 99.24 s |
| full suite, unbuffered on | `env PYTHONUNBUFFERED=1 pytest -q -p no:cacheprovider` | 1403 passed, 10 skipped in 98.99 s |
| lint | `ruff check src tests` | `All checks passed!` |
| format | `black --check src tests` | `69 files would be left unchanged.` |
| types | `mypy --strict src` | `Success: no issues found in 39 source files` |
| harness refs | `bash scripts/check-harness-refs.sh` | 40 PASS, 0 FAIL (the patch touches no `.claude/` or `skills/` file) |
| packager | `bash scripts/package-plugin.sh` | exit 0, three artefacts written (in the scratch tree) |
| Hangul | `LC_ALL=C.UTF-8 grep -P '[\x{AC00}-\x{D7A3}]'` on the three files | rc 1 |
| secrets | `grep -nE 'AKIA[0-9A-Z]{16}\|gh[pousr]_[A-Za-z0-9_]{20}\|sk-[A-Za-z0-9_-]{20}\|BEGIN [A-Z ]*PRIVATE'` on the three files, and `redact_secrets(file) == file` for each | rc 1; all three True |
| 8-word runs | tokenised 8-grams of the new files and the added `loop.py` lines against every file of the D49 package and the watchdog directory (4,740 distinct 8-grams) | 0 hits |
| patch | `git apply --check` then `git apply` on a fresh `git archive 0474fc5` (= origin/main); `sha256sum` of the three files equals the scratch tree | clean; equal |
| the backlog proof | `pytest tests -k repeat` (the ScriptedLLM-style test issues `echo{"x":1}` three times) | `test_third_identical_call_ends_with_the_reminder`: third result is `plain-result` + `\n\n` + the gentle text, the tool ran 3 times |

`test_adversarial_inputs_are_linear` (known flaky timing test) did not fire in either full run. File hashes of the audited code (the QA recomputation target):

```
cf74139b815fd8bb29964b0a57bd2ed9a4e81a7bb0a606fa5f1fd5218c4c0bdd  src/master_finhub/runtime/loop.py
074a51f279db8b42da9fa1f5cab95b200dc3b5f16a469b191bfbbfb447902445  src/master_finhub/runtime/repeat_reminder.py
27c520bbc22790f810a2f4ee111f9df04892a4bff1031dd54ae3c58971404b13  tests/test_repeat_reminder.py
```

Greps that must return these results on the current files of the patched tree:

| grep | expected |
|---|---|
| `grep -n "_execute(" src/master_finhub/runtime/loop.py` | 3 lines: `:193` (`_drive`), `:220` (`_uncertain` rerun), `:225` (the definition) |
| `grep -n "_repeat\." src/master_finhub/runtime/loop.py` | 3 lines: `:171` reset in `run`, `:178` reset in `resume`, `:233` observe in `_execute` |
| `grep -nE "\bhash\(\|random\|time\.\|datetime" src/master_finhub/runtime/repeat_reminder.py` | no output, rc 1 |
| `grep -c "repeat-tool-reminder/src/index.ts" src/master_finhub/runtime/repeat_reminder.py src/master_finhub/runtime/loop.py` | 1 and 1 (the attribution lines) |
| `git diff -U0 src/master_finhub/runtime/loop.py \| grep -c '^@@'` | 6 hunks; none at `_drive`, `_uncertain`, `_run_tool` or the `max_steps` raise |
| `grep -rn "AgentLoop(" src --include=*.py \| grep -v runtime/loop.py` | 5 lines, all inside function scope (cli, server app, subagent, team, evals runner) |

## Test plan

Every test is in the patch and reproduced below in full. Must-still-pass: the whole existing suite, unmodified (1387 passed before revision 2 and 1403 after; 1342 before the patch at all). The cases map to the QA bar of Pick 9 as follows:

| QA bar | tests |
|---|---|
| (a) never vetoes, skips, reorders or alters a call | `test_it_never_vetoes_skips_or_changes_a_call` (10 identical calls: tool ran 10 times, guard asked 10 times, every result starts with the plain result), `test_max_steps_still_raises_...` |
| (b) pair never split, result never lost | `test_the_call_and_result_pair_is_never_split_or_lost`, `test_compaction_neither_resets_...`, every test goes through `LoopSnapshot` validation via the checkpoint hook |
| (c) exactly 3, 5, 8, both directions | `test_third_identical_call_ends_with_the_reminder`, `test_reminder_pattern_over_twenty_identical_calls` (positions 1-20), `test_reminder_texts_are_pinned` |
| (d) key order and merging | `test_key_order_does_not_matter` (flat and nested), `test_different_calls_are_never_merged` (10 pairs), `test_only_consecutive_calls_count_...` |
| (e) resets | `test_a_new_prompt_resets_the_count`, `test_a_run_that_raised_...`, `test_resume_restarts_the_count_and_the_rerun_path_counts`, `test_uncertain_results_*` (2), `test_an_unkeyable_call_resets_the_chain`, compaction test |
| (f) no exception, no behaviour change on odd arguments | `test_unkeyable_arguments_fail_open_...` (8 shapes: `object()`, set, bytes, unsortable keys, circular, 5,000-deep, raising `items()`, over the cap), `test_size_cap_boundary`, `test_a_keyboard_interrupt_is_not_swallowed` |
| (c, d, e, f additions in rev 2) | `test_other_exceptions_fail_open` (MemoryError, OverflowError), `test_names_are_exact`, `test_values_are_exact` (5 pairs), `test_digest_is_full_and_distinct`, `test_unicode_arguments_are_tracked`, `test_nan_arguments_are_tracked`, `test_empty_result_gets_the_reminder`, `test_huge_result_gets_the_reminder`, `test_chain_crosses_turns_into_a_batch`, `test_resume_with_a_new_user_message_resets`, `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls` |
| (g) no arguments or output in the text | `test_reminder_never_quotes_arguments_output_or_tool_name`, `test_reminder_texts_are_pinned`, `test_the_reminder_survives_redaction_and_is_not_altered_by_it` |
| memory, concurrency, determinism | `test_state_is_one_digest_...`, `test_two_loop_instances_share_no_state`, `test_threads_with_their_own_loops_...`, `test_output_does_not_depend_on_the_hash_seed` |

### `tests/test_repeat_reminder.py` (new, in full)

```python
"""C8 proof: advisory repeat-call reminder (synthetic data only, no network).

Every fake credential is assembled at runtime so no complete token shape is committed.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from master_finhub.runtime.context import CLIP_MARKER, ContextManager, balanced_cuts
from master_finhub.runtime.loop import (
    UNCERTAIN_RESULT,
    AgentLoop,
    AgentLoopError,
    AssistantMessage,
    LoopSnapshot,
    Message,
    ToolCall,
    ToolSpec,
)
from master_finhub.runtime.repeat_reminder import (
    FIRM,
    GENTLE,
    MAX_KEY_CHARS,
    REMIND_AT,
    RepeatReminder,
    _call_key,
)
from master_finhub.tools.secret_scan import redact_secrets

PLAIN = "plain-result"
SUMMARY = "<compacted-summary>"
AWS = "AKIA" + "FAKE" * 3 + "0000"
K: dict[str, Any] = {"x": 1}


def _notice(count: int) -> str:
    """What the design says the result of the count-th identical call must end with."""
    if count == 3:
        return "\n\n" + GENTLE
    return "\n\n" + FIRM.format(count=count) if count in (5, 8) else ""


class _Tool:
    def __init__(self, name: str = "echo", out: str = PLAIN, boom: bool = False) -> None:
        self.spec = ToolSpec(name=name, description="test tool", parameters={})
        self.out, self.boom, self.runs = out, boom, 0

    def run(self, arguments: dict[str, Any]) -> str:
        self.runs += 1
        time.sleep(0)  # let another thread run, for the sharing tests
        if self.boom:
            raise ValueError("boom")
        return self.out


class _Seq:
    """One assistant turn per entry: a list of ToolCall, or a str for a final answer."""

    def __init__(self, turns: list[list[ToolCall] | str]) -> None:
        self.turns = list(turns)
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.seen.append(list(messages))
        turn = self.turns.pop(0) if self.turns else "done"
        return AssistantMessage(turn) if isinstance(turn, str) else AssistantMessage("", turn)


def _calls(*args_list: dict[str, Any], name: str = "echo") -> list[list[ToolCall]]:
    return [[ToolCall(f"c{i}", name, a)] for i, a in enumerate(args_list, start=1)]


def _tool_texts(snaps: list[LoopSnapshot]) -> list[str]:
    return [m.content for m in snaps[-1].messages if m.role == "tool"]


def _run(turns: list[list[ToolCall] | str], tools: list[Any] | None = None, **kw: Any) -> list[str]:
    """Run to the end; return every tool message in order."""
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_Seq(turns), tools or [_Tool()], 99, checkpoint=snaps.append, **kw)
    assert loop.run("go") == "done"
    return _tool_texts(snaps)


def test_third_identical_call_ends_with_the_reminder() -> None:
    tool = _Tool()
    out = _run([*_calls(K, K, K), "done"], [tool])
    assert out == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]
    assert tool.runs == 3  # the calls still ran


def test_reminder_pattern_over_twenty_identical_calls() -> None:
    out = _run([*_calls(*[K] * 20), "done"])
    assert out == [PLAIN + _notice(n) for n in range(1, 21)]
    assert REMIND_AT == (3, 5, 8)  # 4, 6, 7 and 9 and above stay silent


def test_reminder_texts_are_pinned() -> None:
    out = _run([*_calls(*[K] * 8), "done"])
    assert out[2] == PLAIN + (
        "\n\n[advisory] The same tool call, with the same arguments, has now been issued 3 times "
        "in a row. Read the earlier results again; if the task is unfinished, change the "
        "arguments or the approach."
    )
    for n in (5, 8):
        assert out[n - 1] == PLAIN + (
            "\n\n[advisory] This exact call (same tool, same arguments) has now been issued "
            f"{n} times in a row. More repeats are unlikely to help: use a different tool or "
            "different arguments, or give your final answer with what you have."
        )


def test_reminder_never_quotes_arguments_output_or_tool_name() -> None:
    args = {"x": "SENTINEL-ARG-77", "tail": {"k": "SENTINEL-NEST-66"}}
    out = _run(
        [*_calls(*[args] * 8, name="sentinel_tool"), "done"],
        [_Tool("sentinel_tool", out="SENTINEL-OUT-88")],
    )
    for n, text in enumerate(out, start=1):
        notice = text[len("SENTINEL-OUT-88") :]
        assert text.startswith("SENTINEL-OUT-88") and notice == _notice(n)
        for secret in ("SENTINEL", "sentinel_tool"):
            assert secret not in notice


def test_key_order_does_not_matter() -> None:
    ab, ba = {"b": 1, "a": 2}, {"a": 2, "b": 1}
    assert _run([*_calls(ba, ab, ba), "done"])[2].endswith(GENTLE)
    nested1 = {"o": {"d": 1, "c": [{"z": 1, "y": 2}]}, "l": [3, 4]}
    nested2 = {"l": [3, 4], "o": {"c": [{"y": 2, "z": 1}], "d": 1}}
    assert _run([*_calls(nested1, nested2, nested1), "done"])[2].endswith(GENTLE)


DIFFERENT: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = [
    ("echo", {"x": 1}, "other", {"x": 1}),  # the tool name is part of the key
    ("echo", {"x": 1}, "echo", {"x": 2}),
    ("echo", {"x": 1}, "echo", {"y": 1}),
    ("echo", {"x": 1}, "echo", {"x": "1"}),
    ("echo", {"x": 1}, "echo", {"x": True}),
    ("echo", {"x": 1}, "echo", {"x": 1.0}),
    ("echo", {"x": [1, 2]}, "echo", {"x": [2, 1]}),  # list order is data
    ("echo", {}, "echo", {"x": None}),
    ("echo", {"x": {"a": 1}}, "echo", {"x": {"a": 2}}),
    ("echo", {"x": 1}, "echo", {"x": 1, "y": 1}),
]


@pytest.mark.parametrize(("n1", "a1", "n2", "a2"), DIFFERENT)
def test_different_calls_are_never_merged(
    n1: str, a1: dict[str, Any], n2: str, a2: dict[str, Any]
) -> None:
    turns: list[list[ToolCall] | str] = [
        [ToolCall("c1", n1, a1)],
        [ToolCall("c2", n2, a2)],
        [ToolCall("c3", n2, a2)],
        "done",
    ]
    assert _run(turns, [_Tool("echo"), _Tool("other")]) == [PLAIN] * 3  # B, B is only two in a row


def test_only_consecutive_calls_count_and_a_different_call_resets() -> None:
    other = {"x": 2}
    assert _run([*_calls(K, K, other, K, K, K), "done"]) == [PLAIN] * 5 + [PLAIN + "\n\n" + GENTLE]
    assert _run([*_calls(K, K, other, K), "done"]) == [PLAIN] * 4  # not a total of three
    assert _run([*_calls(K, other, K, other, K, other), "done"]) == [PLAIN] * 6  # ping-pong


def test_a_new_prompt_resets_the_count() -> None:
    llm = _Seq([*_calls(K, K), "done", *_calls(K), "done"])
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    assert _tool_texts(snaps) == [PLAIN, PLAIN]
    loop.run("second")  # same instance: a 3rd identical call overall, but a new chain
    assert _tool_texts(snaps) == [PLAIN]


def test_a_run_that_raised_does_not_leak_its_count_into_the_next_run() -> None:
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_Seq([*_calls(K, K, K), "done"]), [_Tool()], 2, checkpoint=snaps.append)
    with pytest.raises(AgentLoopError, match="max_steps"):
        loop.run("first")  # two identical calls, then the step limit
    loop.run("second")  # one more identical call: a new chain, so no reminder
    assert _tool_texts(snaps) == [PLAIN]


def test_the_key_ignores_the_tool_output() -> None:
    class _Counting(_Tool):
        def run(self, arguments: dict[str, Any]) -> str:
            super().run(arguments)
            return f"call number {self.runs}"

    out = _run([*_calls(K, K, K), "done"], [_Counting()])
    assert out == ["call number 1", "call number 2", "call number 3\n\n" + GENTLE]


def _pending_snapshot(*calls: ToolCall) -> LoopSnapshot:
    return LoopSnapshot(1, (Message("user", "go"), Message("assistant", "", calls)))


def test_resume_restarts_the_count_and_the_rerun_path_counts() -> None:
    a, b, c = (ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3))
    snaps: list[LoopSnapshot] = []
    # run() leaves a chain of two on this instance; resume() must not continue it.
    loop = AgentLoop(_Seq([*_calls(K, K), "done", "done"]), [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    loop.resume(_pending_snapshot(a), in_flight="rerun")
    assert _tool_texts(snaps) == [PLAIN]
    # rerun (via _uncertain) counts as call 1, the next pending call as 2, the model's as 3.
    snaps.clear()
    fresh = AgentLoop(_Seq([[c], "done"]), [_Tool()], 99, checkpoint=snaps.append)
    fresh.resume(_pending_snapshot(a, b), in_flight="rerun")
    assert _tool_texts(snaps) == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_uncertain_results_are_neither_counted_nor_given_a_reminder() -> None:
    a, b, c = (ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3))
    snaps: list[LoopSnapshot] = []
    llm = _Seq(["done"])
    AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append).resume(
        _pending_snapshot(a, b, c), in_flight="report_unknown"
    )
    assert _tool_texts(snaps) == [UNCERTAIN_RESULT, PLAIN, PLAIN]  # c1 not counted: c3 is no 3rd


def test_uncertain_results_from_a_missing_tool_or_a_guard_are_not_counted() -> None:
    a, b, c = (ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3))
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(
        _Seq(["done"]), [_Tool()], 99, guard=lambda call: "nope", checkpoint=snaps.append
    )
    loop.resume(_pending_snapshot(a, b, c), in_flight="rerun")
    assert _tool_texts(snaps) == [UNCERTAIN_RESULT, "Error: nope", "Error: nope"]


def test_it_never_vetoes_skips_or_changes_a_call() -> None:
    tool, seen = _Tool(), []

    def guard(call: ToolCall) -> str | None:
        seen.append(call)
        return None

    out = _run([*_calls(*[K] * 10), "done"], [tool], guard=guard)
    assert tool.runs == 10 and len(seen) == 10 and len(out) == 10
    assert all(t.startswith(PLAIN) for t in out)


def test_a_guard_denial_is_counted_and_gets_the_reminder() -> None:
    tool, seen = _Tool(), []

    def guard(call: ToolCall) -> str | None:
        seen.append(call)
        return "nope"

    out = _run([*_calls(K, K, K), "done"], [tool], guard=guard)
    assert out == ["Error: nope", "Error: nope", "Error: nope\n\n" + GENTLE]
    assert tool.runs == 0 and len(seen) == 3  # still denied, guard asked once per call


def test_tool_errors_and_unknown_tools_are_counted_too() -> None:
    boom = "Error: tool 'echo' failed: ValueError: boom"
    out = _run([*_calls(K, K, K), "done"], [_Tool(boom=True)])
    assert out == [boom, boom, boom + "\n\n" + GENTLE]
    miss = "Error: Unknown tool 'nope'. Available tools: echo."
    out = _run([*_calls(K, K, K, name="nope"), "done"])
    assert out == [miss, miss, miss + "\n\n" + GENTLE]


def test_the_reminder_survives_redaction_and_is_not_altered_by_it() -> None:
    for n in (3, 5, 8):
        text = (GENTLE if n == 3 else FIRM.format(count=n)).strip()
        assert redact_secrets(text) == (text, ())
    out = _run([*_calls(K, K, K), "done"], [_Tool(out=f"key {AWS}")])
    assert out == ["key [REDACTED:aws-access-key]"] * 2 + [
        "key [REDACTED:aws-access-key]\n\n" + GENTLE
    ]
    # an unterminated private-key block is redacted to the end of the text: the notice is outside
    unclosed = "-----BEGIN " + "PRIVATE KEY-----\nTUFERVVQ"
    out = _run([*_calls(K, K, K), "done"], [_Tool(out=unclosed)])
    assert out[2] == "[REDACTED:private-key]\n\n" + GENTLE


def test_max_steps_still_raises_and_the_last_result_is_saved_with_its_reminder() -> None:
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_Seq(_calls(K, K, K, K)), [_Tool()], 3, checkpoint=snaps.append)
    with pytest.raises(AgentLoopError, match=r"max_steps \(3\) exceeded"):
        loop.run("go")
    assert _tool_texts(snaps) == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_the_call_and_result_pair_is_never_split_or_lost() -> None:
    snaps: list[LoopSnapshot] = []  # LoopSnapshot validates pairing on every save
    three = [ToolCall(f"c{i}", "echo", K) for i in (1, 2, 3)]
    llm = _Seq([three, "done"])
    AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append).run("go")
    roles = [m.role for m in snaps[-1].messages]
    assert roles == ["user", "assistant", "tool", "tool", "tool", "assistant"]
    tools = [m for m in snaps[-1].messages if m.role == "tool"]
    assert [m.tool_call_id for m in tools] == ["c1", "c2", "c3"]
    assert [m.content for m in tools] == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_compaction_neither_resets_the_count_nor_splits_a_pair() -> None:
    big = "y" * 1700  # ~425 estimated tokens each: a summary replaces old turns, no clip
    llm = _Seq([*_calls(*[K] * 9), "done"])
    ctx = ContextManager(context_window_tokens=3000, clip_budget_tokens=500)
    assert _run_with(llm, _Tool(out=big), ctx) == "done"
    summarised = [i for i, s in enumerate(llm.seen) if any(SUMMARY in m.content for m in s)]
    assert summarised and summarised[0] < 8  # compaction ran before the 8th call's reminder
    for seen in llm.seen:
        assert balanced_cuts(seen)[-1]  # no orphan result, no call left without its result
    latest = [s[-1].content for s in llm.seen[1:10]]  # the result each model turn just received
    assert latest == [big + _notice(n) for n in range(1, 10)]


def _run_with(llm: _Seq, tool: _Tool, ctx: ContextManager) -> str:
    return AgentLoop(llm, [tool], 99, context=ctx).run("go")


def test_a_clipped_long_result_keeps_its_reminder_in_the_tail() -> None:
    llm = _Seq([*_calls(K, K, K), "done"])
    _run_with(llm, _Tool(out="z" * 50_000), ContextManager())
    last = llm.seen[3][-1].content  # what the model saw after the third call
    assert CLIP_MARKER in last and last.endswith("\n\n" + GENTLE)


class _Boom(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise RuntimeError("boom")


def _circular() -> dict[str, Any]:
    d: dict[str, Any] = {}
    d["self"] = d
    return d


def _deep() -> dict[str, Any]:
    leaf: Any = 0
    for _ in range(5000):
        leaf = [leaf]
    return {"x": leaf}


UNKEYABLE: list[dict[Any, Any]] = [
    {"x": object()},
    {"x": {1, 2}},
    {"x": b"bytes"},
    {1: "a", "b": 2},  # keys that cannot be sorted together
    _circular(),
    _deep(),
    _Boom(x=1),
    {"x": "a" * (MAX_KEY_CHARS + 1)},  # over the size cap
]


@pytest.mark.parametrize("args", UNKEYABLE, ids=range(len(UNKEYABLE)))
def test_unkeyable_arguments_fail_open_with_no_reminder_and_no_exception(
    args: dict[Any, Any],
) -> None:
    tool = _Tool()
    out = _run([*_calls(*[args] * 5), "done"], [tool])
    assert out == [PLAIN] * 5 and tool.runs == 5


def test_an_unkeyable_call_resets_the_chain() -> None:
    over = {"x": "a" * (MAX_KEY_CHARS + 1)}  # no exception, but no key either
    for bad in ({"x": object()}, over):
        assert _run([*_calls(K, K, bad, K), "done"]) == [PLAIN] * 4
        assert _run([*_calls(K, K, bad, K, K, K), "done"])[5].endswith(GENTLE)


def test_size_cap_boundary() -> None:
    assert MAX_KEY_CHARS == 100_000
    base = len(json.dumps(["echo", {"x": ""}], separators=(",", ":")))
    at_cap = {"x": "a" * (MAX_KEY_CHARS - base)}
    over = {"x": "a" * (MAX_KEY_CHARS - base + 1)}
    assert _call_key("echo", at_cap) is not None
    assert _call_key("echo", over) is None
    assert _run([*_calls(*[at_cap] * 3), "done"])[2].endswith(GENTLE)
    assert _run([*_calls(*[over] * 3), "done"])[2] == PLAIN


def test_state_is_one_digest_and_one_count_whatever_the_arguments() -> None:
    r = RepeatReminder()
    for i in range(2000):
        r.observe("echo", {"x": f"{i}" * 40})
    assert len(repr(vars(r))) < 200
    r.observe("echo", {"x": "q" * 90_000})
    assert len(repr(vars(r))) < 200


def test_two_loop_instances_share_no_state() -> None:
    inner_tool = _Tool()
    inner_snaps: list[LoopSnapshot] = []
    inner = AgentLoop(_Seq([*_calls(K), "done"]), [inner_tool], 99, checkpoint=inner_snaps.append)

    class _Nest(_Tool):
        def run(self, arguments: dict[str, Any]) -> str:
            if self.runs == 1:  # during the outer loop's 2nd call another loop runs to the end
                inner.run("inner")
            return super().run(arguments)

    out = _run([*_calls(K, K, K), "done"], [_Nest()])
    assert out == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]
    assert _tool_texts(inner_snaps) == [PLAIN]


def test_threads_with_their_own_loops_each_see_their_own_pattern() -> None:
    results: list[list[str]] = []

    def work() -> None:
        results.append(_run([*_calls(*[K] * 12), "done"]))

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 8
    assert all(r == [PLAIN + _notice(n) for n in range(1, 13)] for r in results)


CHILD = """
import json
from master_finhub.runtime.repeat_reminder import RepeatReminder
r = RepeatReminder()
a = {"b": 1, "a": [{"d": 1, "c": 2}]}
b = {"a": [{"c": 2, "d": 1}], "b": 1}
print(json.dumps([r.observe("echo", a if i % 2 else b) for i in range(12)]))
"""


def test_output_does_not_depend_on_the_hash_seed() -> None:
    root = Path(__file__).resolve().parent.parent
    outs = set()
    for seed in ("0", "1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(root / "src")}
        done = subprocess.run(
            [sys.executable, "-B", "-c", CHILD],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        outs.add(done.stdout)
    assert len(outs) == 1
    assert json.loads(outs.pop()) == [_notice(n) for n in range(1, 13)]


class _Interrupt(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise KeyboardInterrupt


def test_a_keyboard_interrupt_is_not_swallowed() -> None:
    with pytest.raises(KeyboardInterrupt):
        RepeatReminder().observe("echo", _Interrupt(x=1))


# --- revision 2: classes the round-1 audit found unpinned (B1-B5) and two one-line follow-ups ---


class _Mem(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise MemoryError


class _Ovf(dict[str, Any]):
    def items(self) -> Any:  # type: ignore[override]
        raise OverflowError


@pytest.mark.parametrize("cls", [_Mem, _Ovf])
def test_other_exceptions_fail_open(cls: type[dict[str, Any]]) -> None:
    r = RepeatReminder()
    assert r.observe("echo", cls(x=1)) == ""
    assert _run([*_calls(*[cls(x=1)] * 3), "done"]) == [PLAIN] * 3  # the call itself is unharmed


def test_names_are_exact() -> None:
    r = RepeatReminder()
    assert [r.observe(n, K) for n in ("echo", "Echo", "echo", "echo ", "echo")] == [""] * 5


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ({"x": "A"}, {"x": "a"}),
        ({"x": "a b"}, {"x": "ab"}),
        ({"x": None}, {"x": ""}),
        ({"x": "null"}, {"x": ""}),
        ({"x": " a"}, {"x": "a"}),
    ],
)
def test_values_are_exact(a: dict[str, Any], b: dict[str, Any]) -> None:
    r = RepeatReminder()
    assert [r.observe("echo", v) for v in (a, b, a)] == [""] * 3  # a, b, a is never a run


def test_digest_is_full_and_distinct() -> None:
    keys = {_call_key("echo", {"x": i}) for i in range(500)}
    assert len(keys) == 500 and all(k is not None and len(k) == 64 for k in keys)


def test_unicode_arguments_are_tracked() -> None:
    u = {"x": "xin chào, tiếng Việt éạ"}
    assert _run([*_calls(u, u, u), "done"])[2].endswith(GENTLE)


def test_nan_arguments_are_tracked() -> None:
    n = {"x": float("nan")}
    assert _run([*_calls(n, n, n), "done"])[2].endswith(GENTLE)


def test_empty_result_gets_the_reminder() -> None:
    assert _run([*_calls(K, K, K), "done"], [_Tool(out="")])[2] == "\n\n" + GENTLE


def test_huge_result_gets_the_reminder() -> None:
    out = _run([*_calls(K, K, K), "done"], [_Tool(out="q" * 200_000)])
    assert out[2].endswith(GENTLE) and len(out[2]) > 200_000


def test_chain_crosses_turns_into_a_batch() -> None:
    def c(i: int) -> ToolCall:
        return ToolCall(f"c{i}", "echo", K)

    out = _run([[c(1)], [c(2), c(3)], "done"])
    assert out == [PLAIN, PLAIN, PLAIN + "\n\n" + GENTLE]


def test_resume_with_a_new_user_message_resets() -> None:
    snaps: list[LoopSnapshot] = []
    llm = _Seq([*_calls(K, K), "done", *_calls(K), "done"])
    loop = AgentLoop(llm, [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    prior = snaps[-1]
    snaps.clear()
    # the team.py path: history plus a new user message, no call pending
    loop.resume(LoopSnapshot(prior.step, (*prior.messages, Message("user", "again"))))
    assert _tool_texts(snaps) == [PLAIN] * 3  # two earlier results; the new call is a first


def test_a_tool_that_edits_its_own_arguments_cannot_merge_calls() -> None:
    class _Pop(_Tool):
        def run(self, arguments: dict[str, Any]) -> str:
            arguments.pop("t", None)
            return super().run(arguments)

    a1, b, a2 = {"x": 1, "t": 0}, {"x": 1}, {"x": 1, "t": 0}  # A, B, A: no two alike in a row
    assert _run([*_calls(a1, b, a2), "done"], [_Pop()]) == [PLAIN] * 3
    c1, c2, c3 = {"x": 1, "t": 0}, {"x": 1, "t": 0}, {"x": 1, "t": 0}  # three real repeats
    assert _run([*_calls(c1, c2, c3), "done"], [_Pop()])[2].endswith(GENTLE)
```

## Mutation plan and results

Runner: `_workspace/02_strategy-architect_C8_mutate.py <tree> <scratch> <python>` (`C8_REV=1` selects the revision-1 source shape, `C8_ONLY=Z` runs one id prefix). For each mutant it takes a fresh tar copy of `src tests pyproject.toml` from the audited tree, applies the exact-string edit(s) (the old text must occur exactly once and the file must change, else the runner aborts: a no-op mutation cannot pass), checks that `import master_finhub` resolves inside the copy, and runs a FRESH `python -B -m pytest` process over `tests/test_repeat_reminder.py` and `tests/test_loop.py`. Killed means a non-zero exit. Ordering mutants (K1, K2, K3, K14) run once per `PYTHONHASHSEED` 0..39 and must die under every seed. An unmutated control copy runs first. Expected-equivalent mutants are declared in the table with their reason; a survivor that is not declared makes the runner exit 1.

Result (`_workspace/02_strategy-architect_C8_mutate.out`, revision 2, run on a scratch tar copy of HEAD 0474fc5 plus the patch): control 66 passed; **101 mutants: 96 killed, 5 survived (all declared equivalent: T25, T26, S18, Z11, Z36), 0 unexpected survivors**; K1, K2, K3 and K14 died under every one of their 40 hash seeds. Revision 1 had 85 mutants (80 killed, 5 survivors including S17, which the judge showed is not equivalent); the Z series (16 mutants, the judge's classes plus mine) was added in revision 2, ran first against the revision-1 tests (0 killed of 14 non-equivalent: the reproduction) and then against revision 2 (all 14 killed).

Each mutant is one rule, comparison direction, boundary, call site, reset point or error path:

| id | mutation | seeds | verdict | killed by (alphabetical first two failing tests) |
|---|---|---|---|---|
| T1 | 3 -> 2 (off by one down) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T2 | 3 -> 4 (off by one up) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T3 | 5 -> 4 | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T4 | 5 -> 6 | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T5 | 8 -> 7 | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T6 | 8 -> 9 | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T7 | 9 added (9+ must stay silent) | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T8 | 12 added | 1 | KILLED | `test_output_does_not_depend_on_the_hash_seed`, `test_reminder_pattern_over_twenty_identical_calls` (+more) |
| T9 | 3 dropped | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T10 | 8 dropped | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T11 | membership inverted | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T12 | fires at every count >= 3 (< first) | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T13 | fires from 4 (<= first) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T14 | silent above 8 inverted (> last) | 1 | KILLED | `test_a_guard_denial_is_counted_and_gets_the_reminder`, `test_a_new_prompt_resets_the_count` (+more) |
| T15 | fires at every count >= 1 | 1 | KILLED | `test_a_guard_denial_is_counted_and_gets_the_reminder`, `test_a_new_prompt_resets_the_count` (+more) |
| T16 | tier: gentle only at 3 -> not-equal | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T17 | tier: gentle at the second threshold | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T18 | tier: gentle at 3 and 5 (<= second) | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T19 | tier: always firm | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T20 | tier: always gentle | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T21 | firm text shows count + 1 | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T22 | firm text shows a fixed 5 | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| T23 | separator \n\n -> \n | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T24 | no separator | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| T25 | tier equivalent: gentle at < second | 1 | SURVIVED | none: count is already in {3,5,8}, so < 5 is the same set as == 3 |
| T26 | tier equivalent: gentle at <= first | 1 | SURVIVED | none: count is already in {3,5,8}, so <= 3 is the same set as == 3 |
| C1 | increment by 2 | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C2 | never increments | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C3 | restart value 0 after a different call | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C4 | restart value 2 after a different call | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C5 | key equality inverted | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C6 | every call merged into one chain | 1 | KILLED | `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls`, `test_different_calls_are_never_merged` (+more) |
| C7 | identity compare instead of equality | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C8 | None check dropped (first call raises, fail-open) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C9 | chain never stored | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C10 | chain stored with count 1 | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| C11 | total count per call key (never reset by a different call) | 1 | KILLED | `test_a_new_prompt_resets_the_count`, `test_a_run_that_raised_does_not_leak_its_count_into_the_next_run` (+more) |
| C12 | reset() does nothing | 1 | KILLED | `test_a_new_prompt_resets_the_count`, `test_a_run_that_raised_does_not_leak_its_count_into_the_next_run` (+more) |
| K1 | key order matters (sort_keys False) | 40 | KILLED | `test_key_order_does_not_matter`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| K2 | only the top level is key-sorted | 40 | KILLED | `test_key_order_does_not_matter`, `test_output_does_not_depend_on_the_hash_seed` |
| K3 | set-based key (order free, nested values unhashable) | 40 | KILLED | `test_key_order_does_not_matter`, `test_output_does_not_depend_on_the_hash_seed` (+more) |
| K4 | name dropped from the key | 1 | KILLED | `test_different_calls_are_never_merged`, `test_names_are_exact` (+more) |
| K5 | arguments dropped from the key | 1 | KILLED | `test_a_keyboard_interrupt_is_not_swallowed`, `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls` (+more) |
| K6 | default separators (cap counted on a longer text) | 1 | KILLED | `test_size_cap_boundary` |
| K7 | cap: > becomes >= | 1 | KILLED | `test_size_cap_boundary` |
| K8 | cap: > MAX + 1 | 1 | KILLED | `test_size_cap_boundary` |
| K9 | cap inverted | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| K10 | cap removed | 1 | KILLED | `test_size_cap_boundary`, `test_unkeyable_arguments_fail_open_with_no_reminder_and_no_exception` |
| K11 | cap constant changed | 1 | KILLED | `test_size_cap_boundary` |
| K12 | unserialisable values stringified | 1 | KILLED | `test_unkeyable_arguments_fail_open_with_no_reminder_and_no_exception` |
| K13 | key is the text, not a digest (memory) | 1 | KILLED | `test_digest_is_full_and_distinct`, `test_state_is_one_digest_and_one_count_whatever_the_arguments` |
| K14 | key is hash(text) (same equality per process; the 64-char digest is pinned) | 40 | KILLED | `test_digest_is_full_and_distinct` |
| K15 | tool output goes into the key | 1 | KILLED | `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls`, `test_huge_result_gets_the_reminder` (+more) |
| K16 | call id goes into the key | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| K17 | name dropped at the call site | 1 | KILLED | `test_different_calls_are_never_merged`, `test_size_cap_boundary` |
| K18 | arguments dropped at the call site | 1 | KILLED | `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls`, `test_an_unkeyable_call_resets_the_chain` (+more) |
| F1 | except narrowed to TypeError/ValueError | 1 | KILLED | `test_other_exceptions_fail_open`, `test_unkeyable_arguments_fail_open_with_no_reminder_and_no_exception` |
| F2 | except widened to BaseException | 1 | KILLED | `test_a_keyboard_interrupt_is_not_swallowed` |
| F3 | except re-raises | 1 | KILLED | `test_an_unkeyable_call_resets_the_chain`, `test_other_exceptions_fail_open` (+more) |
| F4 | except does not reset the chain | 1 | KILLED | `test_an_unkeyable_call_resets_the_chain` |
| F5 | except returns None | 1 | KILLED | `test_an_unkeyable_call_resets_the_chain`, `test_other_exceptions_fail_open` (+more) |
| F6 | except removed (try body only) | 1 | KILLED | `test_an_unkeyable_call_resets_the_chain`, `test_other_exceptions_fail_open` (+more) |
| F7 | no key: chain not reset | 1 | KILLED | `test_an_unkeyable_call_resets_the_chain` |
| F8 | no key branch removed (None keys chain up) | 1 | KILLED | `test_size_cap_boundary`, `test_unkeyable_arguments_fail_open_with_no_reminder_and_no_exception` |
| F9 | no key: returns a reminder | 1 | KILLED | `test_an_unkeyable_call_resets_the_chain`, `test_size_cap_boundary` (+more) |
| S1 | no reminder appended | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| S2 | reset missing in run() | 1 | KILLED | `test_a_new_prompt_resets_the_count`, `test_a_run_that_raised_does_not_leak_its_count_into_the_next_run` |
| S3 | reset missing in resume() | 1 | KILLED | `test_resume_restarts_the_count_and_the_rerun_path_counts`, `test_resume_with_a_new_user_message_resets` |
| S4 | reset at the END of run() (a raised run leaks its count) | 1 | KILLED | `test_a_run_that_raised_does_not_leak_its_count_into_the_next_run` |
| S5 | reset on every context fit (compaction) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_compaction_neither_resets_the_count_nor_splits_a_pair` |
| S6 | notice appended BEFORE the secret scan | 1 | KILLED | `test_the_reminder_survives_redaction_and_is_not_altered_by_it` |
| S7 | denials and errors not counted | 1 | KILLED | `test_a_guard_denial_is_counted_and_gets_the_reminder`, `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls` (+more) |
| S8 | counted in _drive only (rerun path uncounted) | 1 | KILLED | `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls`, `test_resume_restarts_the_count_and_the_rerun_path_counts` |
| S9b | uncertain result (report_unknown branch) counted too | 1 | KILLED | `test_uncertain_results_are_neither_counted_nor_given_a_reminder` |
| S9 | uncertain result (missing tool / guard branch) counted too | 1 | KILLED | `test_uncertain_results_from_a_missing_tool_or_a_guard_are_not_counted` |
| S10 | state shared across loops (module level) | 1 | KILLED | `test_threads_with_their_own_loops_each_see_their_own_pattern`, `test_two_loop_instances_share_no_state` |
| S11 | the call is skipped from count 7 (a veto) | 1 | KILLED | `test_compaction_neither_resets_the_count_nor_splits_a_pair`, `test_it_never_vetoes_skips_or_changes_a_call` (+more) |
| S12 | result replaced by the notice (call result lost) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| S13 | tool output copied into the reminder | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| S14 | arguments copied into the reminder | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| S15 | tool name copied into the reminder | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| S16 | reminder as its own user message (pair split) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| S17 | count AFTER the run (the rev 1 order; a tool that edits its arguments merges calls) | 1 | KILLED | `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls` |
| S18 | resume() of a completed snapshot does not reset (equivalent) | 1 | SURVIVED | none: a completed snapshot runs no call, and the next run() or resume() resets first |
| S19 | observer built per call (never counts) | 1 | KILLED | `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`, `test_a_guard_denial_is_counted_and_gets_the_reminder` (+more) |
| Z1 | digest cut to one hex char | 1 | KILLED | `test_digest_is_full_and_distinct`, `test_names_are_exact` |
| Z2 | ensure_ascii=False (non-ASCII arguments become untracked) | 1 | KILLED | `test_unicode_arguments_are_tracked` |
| Z3 | allow_nan=False (NaN arguments untracked) | 1 | KILLED | `test_nan_arguments_are_tracked` |
| Z4 | except narrowed to TypeError/ValueError/RuntimeError | 1 | KILLED | `test_other_exceptions_fail_open` |
| Z5 | except narrowed to six named classes (no MemoryError) | 1 | KILLED | `test_other_exceptions_fail_open` |
| Z6 | name lower-cased | 1 | KILLED | `test_names_are_exact` |
| Z7 | name stripped | 1 | KILLED | `test_names_are_exact` |
| Z8 | key text lower-cased | 1 | KILLED | `test_names_are_exact`, `test_values_are_exact` |
| Z9 | spaces removed from the key text | 1 | KILLED | `test_names_are_exact`, `test_values_are_exact` |
| Z11 | run length stored capped at 9 (equivalent: 9 and above are silent anyway) | 1 | SURVIVED | none: a stored count of 9 still gives 9, 10... and none of them is in (3, 5, 8) |
| Z14 | an empty tool result gets no reminder | 1 | KILLED | `test_empty_result_gets_the_reminder` |
| Z15 | a result over 60,000 characters gets no reminder | 1 | KILLED | `test_huge_result_gets_the_reminder` |
| Z17 | resume() resets only when calls are pending (the team.py path) | 1 | KILLED | `test_resume_with_a_new_user_message_resets` |
| Z21 | chain cleared at the start of every multi-call turn | 1 | KILLED | `test_chain_crosses_turns_into_a_batch` |
| Z35 | null merged with the empty string | 1 | KILLED | `test_values_are_exact` |
| Z36 | name and arguments swapped in the key (equivalent: same equality) | 1 | SURVIVED | none: the pair is still unique per call; only the digest changes |

The five survivors are equivalent by construction (T25 and T26 select the same set as `== 3` because the count is already a member of `{3, 5, 8}`; S18 skips the reset on a completed snapshot, which runs no call; Z11 stores a count capped at 9, and 9 and above are silent anyway; Z36 swaps name and arguments in the key, which keeps the same equality). K14 (`hash()` as the key) is killed by the digest-length test; S17 (count after the run) is killed by the mutating-tool test. Not mutated, with the reason: the `"\n\n"` text of GENTLE/FIRM beyond what the literal pins catch (message-only per the QA bar), `MAX_KEY_CHARS` as a number (pinned by `assert MAX_KEY_CHARS == 100_000` plus K11), a re-ordering of `name` and `arguments` in the key (same equality, equivalent), the time between counting and the tool (no clock is used).

Mutation coverage against the Pick 9 clauses: (a) veto/skip/reorder/alter: S1, S11, S12, S16, S19; (b) split or lose the pair: S12, S16; (c) wrong count or call: T1-T26, C1-C4, C10, Z2, Z14, Z15; (d) key order and merging: K1-K5, K15-K18, C5-C8, S17, Z1, Z6-Z9, Z35; (e) resets: S2-S5, S9, S9b, C12, F4, F7, Z17, Z21; (f) exceptions and unserialisable arguments: F1-F9, K7-K12, Z3-Z5; (g) arguments or output in the text: S13-S15, T21-T24, K15; call sites: S1, S8, S9, S9b; error paths: S7, F1-F9.

## Does not cover

- **Alternation.** A,B,A,B is not a run; a model ping-ponging between two calls is never flagged (same as D49 and A27, which compare consecutive calls only).
- **Over-cap and unkeyable arguments** never draw a reminder (more than 100,000 characters of JSON, or arguments `json.dumps` rejects). Fail-open by design.
- **Python key semantics.** `1` and `1.0` are different calls, `1` and `true` differ, a list is ordered. Integer and string dict keys that print the same (`{1: "a"}` and `{"1": "a"}`) merge, because `json.dumps` writes both as `"1"`; a model cannot produce non-string keys, only a Python caller can.
- **Silent from the 9th identical call.** A model that repeats the call 20 times gets exactly three reminders. Follows D49 (README `:90`); a repeating tail ("every 3 after 8") is a one-line change if wanted.
- **Persistence.** A resumed run restarts the count; at most two extra repeats before the first reminder.
- **No effect measured on a live model.** Whether the text actually reduces wasted steps before `max_steps` is the backlog's own assumption (`[assumed]`), not verified here; no model call is made in any test. The text is plain tool-result content, so no provider message-shape rule is touched, but a provider's reaction to it was not exercised.
- **Evals baselines.** `evals/runner.py:153` runs `AgentLoop`; any benchmark case whose agent repeats one call three or more times now sees different tool text, so a baseline recorded earlier can move for that case. The built-in `ScriptedLLM` benchmarks make single calls. Not measured over the benchmark set.
- **Shared instance across threads.** One `AgentLoop` driven by two threads at once is not supported before this change (they would interleave one message list) and gets no lock now; separate instances are tested.
- **Tool name is not in the text,** so the model is not told which tool; it has the preceding assistant message for that. D49's detailed tier names the tool and quotes arguments; not adopted (decision 5).
- **Platform.** Run only on Linux CPython 3.11. The 5,000-deep nesting case relies on the C JSON encoder raising `RecursionError`; other interpreters were not run.
- **Clipped notice.** `clip_text` keeps a tail of one fifth of the clip budget; with a very small `clip_budget_tokens` the tail can be shorter than the notice and the notice is cut off a clipped result. The test uses the default budget only.
- **Bound units.** The 100,000 bound counts ASCII-escaped JSON characters (non-ASCII text costs up to 6 each), so non-English arguments reach it sooner than their source length suggests.
- **Compaction summaries** drop old reminders (they excerpt 200 characters per message); the reminders for the latest calls are intact.

## Authority List

Rows A1-A17 cite `references/`. N-rows are net-new own-code claims, each with a check that can fail: a test or mutant named below, or a grep that must return the stated result on the current files.

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | The detector counts consecutive identical calls: a call with the same key as the stored one increments the run, otherwise the run restarts at 1 | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:197 | C8 |
| A2 | The key is the tool name plus the canonical arguments, serialised together as a JSON array | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:195 | C8 |
| A3 | Canonical arguments are a deep key-sort followed by JSON stringify, so property order does not matter at any depth | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:103 ; references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:89 | C8 |
| A4 | The default thresholds are 3, 5 and 8 | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:46 | C8 |
| A5 | A reminder is produced only when the run length is exactly one of the thresholds; every other count, including counts past the highest, produces none | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:199 ; references/deepseek_harness/packages/guard/repeat-tool-reminder/README.md:90 | C8 |
| A6 | The text at the first threshold is a short one and later thresholds get a longer one | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:200 | C8 |
| A7 | The detailed text names the tool and quotes the canonical arguments (this design deliberately does not) | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:70 | C8 |
| A8 | Denied calls are counted too, because a model hammering a denied call is the loop worth breaking | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:184 ; references/deepseek_harness/packages/guard/repeat-tool-reminder/README.md:28 | C8 |
| A9 | CHANGED r2: The guard only observes and enriches: it counts first (`observe` at :214, still after the tool ran, since this is the post-execute hook), then delegates to later listeners (`next()` at :215) and attaches the reminder to whatever decision came back, never replacing the call | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:213 ; references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:209 | C8 |
| A10 | A user message in the context deletes the chain | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:230 | C8 |
| A11 | A session resumed from persistence starts with a fresh chain (the chain is in memory only) | references/deepseek_harness/packages/guard/repeat-tool-reminder/README.md:31 | C8 |
| A12 | The chain state is held per agent object, not globally | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:173 | C8 |
| A13 | The detail cap bounds only the quoted text; D49's chain key always compares the full canonical string (this design caps the key instead and drops the quote) | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:114 | C8 |
| A14 | Configurable include and exclude patterns exist in D49 and are not adopted here | references/deepseek_harness/packages/guard/repeat-tool-reminder/src/index.ts:176 | C8 |
| A15 | The AutoGPT watchdog treats a call as a repeat when its tool name and arguments equal the previous call's | references/autogpt/classic/forge/forge/components/watchdog/watchdog.py:51 | C8 |
| A16 | The watchdog's reaction to a repeat is a history rewind and a retry on the stronger model, i.e. it vetoes; not adopted | references/autogpt/classic/forge/forge/components/watchdog/watchdog.py:57 | C8 |
| A17 | Licences: the deepseek harness is MIT; everything in AutoGPT outside `autogpt_platform` is MIT (the classic tree is used) | references/deepseek_harness/LICENSE:1 ; references/autogpt/LICENSE:4 | C8 |
| N1 | CHANGED r3 (line range): NET-NEW: the reminder text is a pure function of the count and never contains the tool name, the arguments or any output. Check: `test_reminder_never_quotes_arguments_output_or_tool_name` and `test_reminder_texts_are_pinned`; mutants S13, S14, S15, T21-T24 each die | own code `repeat_reminder.py:21-30` | C8 |
| N2 | CHANGED r2 (lines): NET-NEW: the notice is appended after `redact_secrets` because the private-key rule runs to the end of the text. Check: test case "unclosed" in `test_the_reminder_survives_redaction_and_is_not_altered_by_it`; mutant S6 dies | own code `loop.py:225-234`, `tools/secret_scan.py:28-29` | C8 |
| N3 | CHANGED r2 (grep text): NET-NEW: `_execute` is the only counting site and covers success, unknown tool, guard denial, tool error and the resume rerun. Check: `grep -n "_execute(" loop.py` returns `:193`, `:220`, `:225`; `grep -n "_repeat\." loop.py` returns `:171`, `:178`, `:233` (re-run on rev 2: exact); mutants S1, S7, S8 die | own code | C8 |
| N4 | NET-NEW: the counter is not persisted; `resume()` resets it and `run()` resets it at its start. Check: `LoopSnapshot` has the two fields `step` and `messages` (`loop.py:84-85` origin, still unchanged in the patch); tests `test_resume_restarts_...`, `test_a_new_prompt_resets_the_count`, `test_a_run_that_raised_...`; mutants S2, S3, S4, C12 die | own code | C8 |
| N5 | NET-NEW: `UNCERTAIN_RESULT` returns neither count nor reset. Check: `test_uncertain_results_are_neither_counted_nor_given_a_reminder` and `test_uncertain_results_from_a_missing_tool_or_a_guard_are_not_counted`; mutants S9, S9b die | own code `loop.py:214-223` | C8 |
| N6 | CHANGED r2: NET-NEW: `observe` fails open on `Exception` only: the chain is cleared, the result is unchanged, `KeyboardInterrupt` propagates; `MemoryError` and `OverflowError` are caught like the rest. Check: the eight-shape test, `test_other_exceptions_fail_open` (MemoryError, OverflowError, through the full loop too), `test_an_unkeyable_call_resets_the_chain`, `test_a_keyboard_interrupt_is_not_swallowed`; mutants F1-F9, Z4, Z5 die | own code `repeat_reminder.py:50-64` | C8 |
| N7 | CHANGED r2: NET-NEW: the key is the sha256 digest (64 hex characters) of the ASCII JSON text, with no key when the text exceeds 100,000 ASCII-escaped characters; the state is one 64-character string and one int. Check: `test_size_cap_boundary`, `test_state_is_one_digest_...`, `test_digest_is_full_and_distinct`; mutants K6-K14, Z1 die; timing quoted in Design 10; escaped-length check: `_call_key("echo", {"x": "é" * 16000})` is keyed (96,017 characters) and `* 17000` is not (re-run: True, True) | own code `repeat_reminder.py:19-20`, `:33-39` | C8 |
| N8 | NET-NEW: state is per instance and every `AgentLoop(` call site builds its own instance. Check: `grep -rn "AgentLoop(" src --include=*.py \| grep -v runtime/loop.py` returns 5 lines; `test_two_loop_instances_share_no_state`, `test_threads_with_their_own_loops_...`; mutant S10 dies | own code | C8 |
| N9 | NET-NEW: compaction neither resets the chain nor unbalances a pair, and a clipped result keeps its suffix. Check: `test_compaction_neither_resets_...` (summary present from the 6th model turn), `test_a_clipped_long_result_keeps_its_reminder_in_the_tail`; mutant S5 dies | own code `runtime/context.py:74-77`, `:83-95` | C8 |
| N10 | CHANGED r2: NET-NEW: the reminder never changes control flow: `max_steps` still raises with the third result saved, the tool runs every time, the guard is asked once per call. Check: `test_max_steps_still_raises_...`, `test_it_never_vetoes_skips_or_changes_a_call`; `git diff -U0 loop.py` shows 6 hunks and none at `_drive`, `_uncertain`, `_run_tool` or the raise (re-run: 6); mutants S11, S12 die | own code | C8 |
| N11 | NET-NEW: output is deterministic and independent of `PYTHONHASHSEED`. Check: `grep -nE "\bhash\(\|random\|time\.\|datetime" repeat_reminder.py` returns nothing; `test_output_does_not_depend_on_the_hash_seed` (seeds 0, 1, 4242); mutants K1, K2, K3 die under seeds 0-39 each | own code | C8 |
| N12 | CHANGED r3 (line): NET-NEW: thresholds are fixed constants (3, 5, 8) with exact membership, no configuration. Check: `test_reminder_pattern_over_twenty_identical_calls` pins positions 1-20; mutants T1-T15 die | own code `repeat_reminder.py:19` | C8 |
| N13 | CHANGED r2: NET-NEW: the key distinguishes tool name (case, trailing space), argument values (case, inner space, null vs empty, number vs string), keys, JSON type and list order, and ignores tool output and call id. Check: `test_different_calls_are_never_merged` (10 pairs), `test_names_are_exact`, `test_values_are_exact` (5 pairs), `test_the_key_ignores_the_tool_output`; mutants K4, K5, K15-K18, C6, Z6-Z9, Z35 die | own code | C8 |
| N14 | NET-NEW (quant guardrails): no backtest, pricing or verifier code changes; the eval runner grades only the final answer and files, and the reminder holds no task or label text. Check: `evals/runner.py:161-162` (`parts = [loop.run(bench.task)]`, then workspace files) and `grep -c "observe" src/master_finhub/evals/*.py` returns 0 for every file | own code | C8 |
| N15 | CHANGED r2: NET-NEW: no existing test changes and the suite stays green in both buffering modes. Check: `git diff --stat` lists `loop.py`, `repeat_reminder.py`, `test_repeat_reminder.py` only; 1403 passed, 10 skipped under `env -u PYTHONUNBUFFERED` and `PYTHONUNBUFFERED=1`, run one after the other in the foreground (1387 + the 16 new cases) | own code | C8 |
| N16 | NEW r2: NET-NEW: the notice is computed BEFORE `_run_tool`, so a tool that edits its own arguments in place cannot change the key (D49 observes before delegating to later listeners, `index.ts:214-215`, but after its tool; the before-the-tool order is net-new). Check: `grep -n "note = self._repeat.observe" loop.py` returns `:233` and the next line is the return; `test_a_tool_that_edits_its_own_arguments_cannot_merge_calls` fails on the revision-1 `_execute` (reproduced) and passes now; mutant S17 (count after the run) dies | own code `loop.py:233-234` | C8 |
| N17 | NEW r2: NET-NEW: tracking is independent of the text of the arguments and the result: non-ASCII arguments and NaN are keyed, an empty result and a 200,000-character result still carry the notice. Check: `test_unicode_arguments_are_tracked`, `test_nan_arguments_are_tracked`, `test_empty_result_gets_the_reminder`, `test_huge_result_gets_the_reminder`; mutants Z2, Z3, Z14, Z15 die | own code | C8 |
| N18 | NEW r2: NET-NEW: the chain survives a turn boundary into a batched turn, and `resume()` with a new user message and no pending call resets it (the `team.py:371` path). Check: `test_chain_crosses_turns_into_a_batch`, `test_resume_with_a_new_user_message_resets`; mutants Z17, Z21 die | own code `loop.py:178`, `orchestration/modes/team.py:371` | C8 |
