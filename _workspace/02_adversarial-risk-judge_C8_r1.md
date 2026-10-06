TOTALS: UPHELD 32 / REJECTED 5 / UNVERIFIED 0 - round 1/3

# Adversarial verdict - C8 advisory repeat-call reminder, revision 1

- Audited file: _workspace/02_strategy-architect_C8.md (Authority List A1-A17, N1-N15) with patch sha256 d46fe6e9...ecae11e (matches the design), mutation runner and output
- Audited against: repo HEAD 0474fc5, tar copy in the judge scratchpad, patch applied with `patch -p1` (and `git apply --check` clean on the repo HEAD); repo itself untouched (git status clean)
- Extra round authorised by Daniel: none exists
- The 32 UPHELD rows are the 17 A rows and 15 N rows. The 5 REJECTED rows B1-B5 are mutation-bar rows added by the judge: each is a surviving non-equivalent mutant of a class the fixed QA bar of Pick 9 forbids ((c), (d), (e), (f)) or a false equivalence declaration. No Authority List citation is wrong.

## Claims

| id | verdict | cited | found at cited line (+-5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | deepseek_harness/.../repeat-tool-reminder/src/index.ts:197 | `const count = chain !== undefined && chain.key === key ? chain.count + 1 : 1` | - |
| A2 | UPHELD | index.ts:195 | `const key = JSON.stringify([exec.name, canonical])` | - |
| A3 | UPHELD | index.ts:103 ; :89 | `canonicalize` = `JSON.stringify(sortJsonValue(...))`; `sortJsonValue` recurses arrays and objects, sorts keys | - |
| A4 | UPHELD | index.ts:46 | `thresholds: z.array(z.number()).default([3, 5, 8])` | - |
| A5 | UPHELD | index.ts:199 ; README.md:90 | `if (!thresholdSet.has(count)) return undefined`; README: "Past the highest threshold a chain goes silent - reminders fire only at exact configured counts" | - |
| A6 | UPHELD | index.ts:200 | `count === thresholds[0] ? GENTLE_REMINDER : detailedReminder(...)` | - |
| A7 | UPHELD | index.ts:70 | `detailedReminder(toolName, count, canonicalArguments)` emits tool and arguments lines (:72,:74) | - |
| A8 | UPHELD | index.ts:184 ; README.md:28 | comment "denied calls also flow through this waterfall ... a model hammering a denied call is exactly the loop worth breaking"; README "Denied calls count" | - |
| A9 | UPHELD | index.ts:213 | `observe(exec)` at :214, `await next()` at :215, reminder prepended to whatever decision came back at :216-223 (block and non-block) | Note only: D49 counts BEFORE it delegates (:209-210 "count first ... DELEGATE"); the claim's "delegates first" is true only relative to attaching. Not blocking. |
| A10 | UPHELD | index.ts:230 | `if (messages.some(message => message.source.kind === 'user')) chains.delete(agent)` | - |
| A11 | UPHELD | README.md:31 | "In-memory only. A session resumed from persistence starts with a fresh chain" | - |
| A12 | UPHELD | index.ts:173 | `const chains = new WeakMap<Agent, Chain>()` | - |
| A13 | UPHELD | index.ts:114 | doc comment :113-117 "Bounds only the model-visible text - the chain key always uses the full canonical string" | - |
| A14 | UPHELD | index.ts:176 | `tracked()` with include/exclude patterns; config fields :47-48 | - |
| A15 | UPHELD | autogpt/classic/forge/forge/components/watchdog/watchdog.py:51 | `result.use_tool.name == previous_command and result.use_tool.arguments == previous_command_args` (:51-54); classic tree, not autogpt_platform | - |
| A16 | UPHELD | watchdog.py:57 | `if rethink_reason:` ... `self.event_history.rewind()` :59, `big_brain = True` :60, `raise ComponentSystemError` :63 | - |
| A17 | UPHELD | deepseek_harness/LICENSE:1 ; autogpt/LICENSE:4 | "MIT License", "Copyright (c) 2026 DeepSeek"; "Everything outside the autogpt_platform folder is under the MIT License" | - |
| N1 | UPHELD | own code repeat_reminder.py:21-30 | GENTLE/FIRM at :21-30; texts are constants plus `{count}` only. Re-run: runner S13, S14, S15, T21-T24 all KILLED | Verified `redact_secrets` leaves all three texts unchanged. |
| N2 | UPHELD | loop.py:225-233; secret_scan.py:28-29 | `_execute` at :225-233; private-key rule `.*?(?:...END...|\Z)` at :28-29 runs to end of text. Runner S6 KILLED | - |
| N3 | UPHELD | grep checks | `grep -n "_execute(" loop.py` -> :193, :220, :225; `grep -n "_repeat\." loop.py` -> :171, :178, :233 (re-run, exact). S1, S7, S8 KILLED. Also no other `_execute`/`_run_tool`/`_drive` use outside loop.py (team.py `_execute` is an unrelated function) | - |
| N4 | UPHELD | own code | `LoopSnapshot` fields step, messages only (origin :84-85). S2, S3, S4, C12 KILLED | Coverage of the resume reset is incomplete: see B4. |
| N5 | UPHELD | loop.py:214-223 | both `UNCERTAIN_RESULT` returns neither observe nor reset; S9, S9b KILLED | - |
| N6 | UPHELD | repeat_reminder.py:50-64 | `except Exception`; MemoryError, RecursionError, OverflowError, TypeError, ValueError all caught (verified directly); KeyboardInterrupt propagates. F1-F9 KILLED | Coverage of non-listed exception classes is incomplete: see B1. |
| N7 | UPHELD | repeat_reminder.py:19-20, :33-39 | cap exact: 99,999 and 100,000 chars keyed, 100,001 unkeyed (re-measured); state is (str, int). 20 MB string 0.065 s (claimed 0.067 s). K6-K13 KILLED | - |
| N8 | UPHELD | grep | `grep -rn "AgentLoop(" src --include=*.py \| grep -v runtime/loop.py` -> 5 lines (cli.py:132, server/app.py:138, subagent.py:315, team.py:356, evals/runner.py:153), each builds its own instance; team.py:356 reuses one loop per agent across turns via `resume()` (resets). S10 KILLED | - |
| N9 | UPHELD | context.py:74-77, :83-95 | `clip_text` keeps the tail (1/5 of the budget), `balanced_cuts` unchanged. S5 KILLED | Reminder survives only while the tail slice (budget/5) is longer than the notice: follow-up F3. |
| N10 | UPHELD | own code | `git diff` shows 6 hunks, none in `_drive`, `_uncertain`, `_run_tool` or the raise. +15/-2 and 64 lines confirmed. S11, S12 KILLED | - |
| N11 | UPHELD | grep | `grep -nE "\bhash\(|random|time\.|datetime" repeat_reminder.py` -> no output, rc 1. K1, K2, K3 KILLED under hash seeds 0-39 each (re-run: x40 seeds); new test passes under seeds 0,1,7,99,31337 | - |
| N12 | UPHELD | repeat_reminder.py:19 | constants (3, 5, 8); T1-T24 KILLED, T25/T26 equivalent (see Equivalence rulings) | - |
| N13 | UPHELD | own code | probes: name, values, keys, 1 vs 1.0 vs True, list order, nested key order all distinguished/ignored as claimed; JSON array keeps name/args boundary unambiguous. K4, K5, K15-K18, C6 KILLED | Named check leaves many merge mutants alive: see B2. |
| N14 | UPHELD | evals/runner.py:161-162; grep | lines are `parts = [loop.run(bench.task)]` and the files read; `grep -c observe src/master_finhub/evals/*.py` -> 0,0,0. The only shipped benchmark (echo_pass.json) gives an identical CaseResult before and after (passed, 2 steps, same expectations) | - |
| N15 | UPHELD | suite | collect before: 1352 = 1342 passed + 10 skipped; after 1387 passed, 10 skipped under both `env -u PYTHONUNBUFFERED` (97.9 s) and PYTHONUNBUFFERED=1 (98.9 s), run one after the other in the foreground; only loop.py + 2 new files change; `test_adversarial_inputs_are_linear` did not fire | - |
| B1 | REJECTED | bar (f): exception escape | mutant Z4 `except (TypeError, ValueError, RuntimeError)` and Z5 (adds RecursionError, OverflowError, KeyError) SURVIVE all 50 tests plus test_loop/test_modes | No test uses an exception that is not TypeError/ValueError/RuntimeError. `MemoryError` and `OverflowError` from a mapping's `items()` would escape `observe` and fail a successful tool call. Kill test: `test_other_exceptions_fail_open` below (passes on the patch, kills Z4, Z5). |
| B2 | REJECTED | bar (d): merge different calls | mutants SURVIVE: Z6 name lower-cased (`Echo` == `echo`), Z7 name stripped, Z8 key text lower-cased (`"A"` == `"a"`), Z9 spaces removed (`"a b"` == `"ab"`), Z35 `null` merged with `""`, Z1 digest cut to 1 hex char | `DIFFERENT` has 10 pairs, all name/number/type/list-order; no string-value, case, whitespace, null-vs-empty or digest-length pair. Kill tests: `test_names_are_exact`, `test_values_are_exact`, `test_digest_is_full_and_distinct` below. |
| B3 | REJECTED | bar (c): missed reminder at 3/5/8 | mutants SURVIVE: Z2 `ensure_ascii=False` (every call with non-ASCII arguments, e.g. Vietnamese text, becomes untracked: no reminder ever), Z14 empty tool result gets no reminder, Z15 result over 60,000 chars gets none | Tests only use ASCII args, a non-empty `PLAIN` result and at most a 50,000-char result. Kill tests: `test_unicode_args_are_tracked`, `test_empty_result_gets_the_reminder`, `test_huge_result_gets_the_reminder`. |
| B4 | REJECTED | bar (e): reset / chain rules | mutants SURVIVE: Z17 `resume()` resets only when calls are pending, Z21 chain cleared at the start of any multi-call turn | Z17 is exactly the team path (team.py:356-371 resumes with a new user message: status `awaiting_model`, no pending call): tests only resume a `tools_in_flight` snapshot. Z21: no test carries a chain from one turn into a batched turn ([K] then [K,K]). Kill tests: `test_resume_with_a_new_user_message_resets`, `test_chain_crosses_turns_into_a_batch`. |
| B5 | REJECTED | bar (d) + false equivalence | runner mutant S17 (count before the run) is declared equivalent, but is not | `observe` runs AFTER `tool.run`, so a tool that edits its arguments in place changes the key: calls A={"x":1,"t":0}, B={"x":1} against a tool that does `arguments.pop("t")` give [no, no, reminder] for A,B,A (A and B merged; reproduced). No shipped tool mutates arguments (grepped src), so severity is low, but the equivalence note is false. Fix: compute the notice before `_run_tool` (S17 shape: `note = observe(...)`, run, `return result + note`) and add a mutating-tool test, or declare the limit and test it. |

## Equivalence rulings (architect's 5 survivors)

| mutant | ruling |
|---|---|
| T25, T26 | equivalent: at that branch `count` is already in {3,5,8}, so `< 5` and `<= 3` select the same element. Agreed. |
| K14 | equivalent in function (equality of `hash(text)` inside one process equals text equality up to a 2^-64 collision). Agreed; it is not the same as B2/Z1, which a test can kill. |
| S18 | equivalent: a completed snapshot runs no call and the next `run()`/`resume()` resets first. Agreed. |
| S17 | NOT equivalent: see B5. |
| (judge) Z11 counter capped at 8 | equivalent: counts above 8 are silent either way. |

## Reproduction (judge scratchpad, tar copy of HEAD 0474fc5 + patch)

- New tests: 45 passed. Full pytest `env -u PYTHONUNBUFFERED`: 1387 passed, 10 skipped (97.87 s); PYTHONUNBUFFERED=1: 1387 passed, 10 skipped (98.89 s), foreground, one after the other.
- ruff: All checks passed. black --check: 69 files unchanged. mypy --strict src: no issues in 39 files. check-harness-refs.sh (via bash; the file mode is 644 in the repo): all PASS, rc 0. package-plugin.sh: three artefacts written, rc 0.
- Hangul (`LC_ALL=C.UTF-8 grep -P`): rc 1 on the three files; no non-ASCII byte at all in the two new files. 8-word verbatim runs: 4,810 distinct 8-grams of the D49 package and the watchdog directory against the patch's added lines: 0 hits. Attribution line present in the module docstring (index.ts path with lines) and in loop.py.
- Sha256 of the three patched files equal the design's hashes (loop b708ba02..., repeat_reminder 5f9e2827..., test d7442a08...).
- Architect's runner re-run: 85 mutants, 80 killed, 5 survived (T25, T26, K14, S17, S18), 0 unexpected; K1-K3 and K14 under seeds 0-39.
- Judge's own 35 mutants Z1-Z35 (fresh process, tar copy, `python -B`, each mutation asserted single-occurrence and changed, module path asserted to be the copy; ordering mutant Z28 under seeds 0-39): 20 killed by the architect's tests, 15 survived (Z1-Z9, Z11, Z14, Z15, Z17, Z21, Z35; Z3 NaN and Z11 are not in B1-B5: Z11 equivalent, Z3 follow-up). With the kill tests below added, 13 of those 15 die; Z3 and Z11 remain.

## Probes (all run against the patched copy)

- Key: `1` vs `1.0` vs `True`, `0` vs `-0.0`, `"1"` vs `1`, NFC vs NFD, `1e20` vs `10**20`, `{}` vs `[]`: never merged. NaN vs NaN merged (identical call). Name/args boundary (`a`,`["b"]` vs `a",["b`,`[]`): not merged. Non-dict args (list, str, None, int): keyed.
- Merged but unreachable from model JSON: tuple vs list, `{1:"a"}` vs `{"1":"a"}`, `{True:..}` vs `{"true":..}`. bytes, sets, `{1:"a","b":2}` raise TypeError and are caught. Follow-up F2.
- Cost before the bound check: json.dumps runs to the end first: 20 MB string 0.065 s, 200 MB 0.69 s, 5M-int list 0.48 s, 2M-key dict 0.99 s; deep nesting (5,000 / 50,000 / 100,000) raises RecursionError in under 1 ms (caught). Cost is linear in the argument size already held in memory. Acceptable.
- Bound exactness: 99,999 and 100,000 JSON chars keyed, 100,001 not keyed. The bound counts ASCII-escaped characters, so a non-ASCII character costs up to 6.
- Evasion: oversized arguments clear the chain, so padding arguments past 100,000 chars (or changing any argument) avoids the reminder. Same class as D49's own exact-match limit (README:85); advisory only; acceptable. Stated, not blocking.
- Counting paths: `_execute` is the only counting site; guard denial, tool error, unknown tool and the resume rerun path count; the two `UNCERTAIN_RESULT` returns do not; a BaseException from a tool ends the run before counting and the next run/resume resets. Batched calls in one assistant turn are executed in order and count consecutively (third result in the batch gets the notice).
- Consumers: cli, server, subagent, evals runner build one loop per run; team.py reuses one loop per agent and always resumes (reset). No consumer shares one loop across conversations. No code parses tool-message content (only clip, summarise, balanced_cuts, anthropic_llm pass-through), so the appended text breaks no parser; `redact_secrets` is applied only inside `_execute`, never again, so the notice is never re-scanned.
- Tokens: notice is 190-218 characters, at most three times per chain.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C8 | N/A no returns or pricing computed | N/A | N/A | N/A no data indexing; loop text only | N/A | N/A no split |

The slice does not touch backtest, pricing, verifier or eval-runner code. The runner calls `AgentLoop` and grades only the final answer and files; the one shipped benchmark gives an identical result before and after.

## Findings classification

Blocking (REJECTED): B1 (f), B2 (d), B3 (c), B4 (e), B5 (d, false equivalence). All are test or declaration gaps; the code under test behaves correctly on every probe except B5's argument-mutating tool.
Follow-up (not counted): F1 Z3 `allow_nan=False` survives (NaN arguments would become untracked); add `observe("e", {"x": float("nan")})` three times -> third non-empty. F2 tuple/list and int/str key collisions are unreachable from JSON arguments. F3 a small `clip_budget_tokens` (tail = budget/5 characters x4) can cut the notice off a clipped result; the test uses the default budget only. F4 non-ASCII text counts up to 6 characters toward the 100,000 cap. F5 A9 wording ("delegates first").

## Kill tests that passed on the patch and killed the survivors (judge scratchpad; for the architect to adopt or adapt)

```python
from typing import Any
import pytest
from master_finhub.runtime.loop import AgentLoop, LoopSnapshot, Message, ToolCall
from master_finhub.runtime.repeat_reminder import GENTLE, RepeatReminder, _call_key
from tests.test_repeat_reminder import _Tool, _Seq, _calls, _run, _tool_texts, PLAIN

K: dict[str, Any] = {"x": 1}

def test_unicode_args_are_tracked():
    u = {"x": "éạ việt"}
    assert _run([*_calls(u, u, u), "done"])[2].endswith(GENTLE)

class _Mem(dict):
    def items(self):
        raise MemoryError
class _Ovf(dict):
    def items(self):
        raise OverflowError

@pytest.mark.parametrize("cls", [_Mem, _Ovf])
def test_other_exceptions_fail_open(cls):
    assert RepeatReminder().observe("e", cls(x=1)) == ""

def test_names_are_exact():
    r = RepeatReminder()
    assert [r.observe(n, K) for n in ("echo", "Echo", "echo", "echo ", "echo")] == [""] * 5

@pytest.mark.parametrize("a,b", [({"x": "A"}, {"x": "a"}), ({"x": "a b"}, {"x": "ab"}), ({"x": None}, {"x": ""}), ({"x": "null"}, {"x": ""})])
def test_values_are_exact(a, b):
    r = RepeatReminder()
    assert [r.observe("e", v) for v in (a, b, a)] == [""] * 3

def test_digest_is_full_and_distinct():
    keys = {_call_key("e", {"x": i}) for i in range(500)}
    assert len(keys) == 500 and all(len(k) == 64 for k in keys)

def test_empty_result_gets_the_reminder():
    assert _run([*_calls(K, K, K), "done"], [_Tool(out="")])[2] == "\n\n" + GENTLE

def test_huge_result_gets_the_reminder():
    assert _run([*_calls(K, K, K), "done"], [_Tool(out="q" * 200_000)])[2].endswith(GENTLE)

def test_chain_crosses_turns_into_a_batch():
    c = lambda i: ToolCall(f"c{i}", "echo", K)
    out = _run([[c(1)], [c(2), c(3)], "done"])
    assert out[2].endswith(GENTLE) and out[:2] == [PLAIN] * 2

def test_resume_with_a_new_user_message_resets():
    snaps = []
    loop = AgentLoop(_Seq([*_calls(K, K), "done", *_calls(K), "done"]), [_Tool()], 99, checkpoint=snaps.append)
    loop.run("first")
    prior = snaps[-1]
    snaps.clear()
    loop.resume(LoopSnapshot(prior.step, (*prior.messages, Message("user", "again"))))
    assert _tool_texts(snaps) == [PLAIN] * 3  # history keeps the 2 earlier results; the new one has no reminder
```
