RESULT: FAIL

# Boundary QA: C6 delegation contract (design rev 2, Authority List A1-A40, judge r2 UPHELD 43 / REJECTED 0)

One-line cause: the built tree is byte-identical to the audited design and every gate, grep, cold build and live run passes, but my one fresh mutant batch found 3 non-equivalent survivors that let a seeded bad brief through the lint's test suite (Q10, Q23, Q24). Under Daniel's fixed bar ("ZERO non-equivalent mutants that let a seeded bad brief ... pass") that is a FAIL. The product code is correct on all three inputs (probed below); the gap is three missing test cases. Per the bar, no second batch is run.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| design patch <-> built tree | `_workspace/02_strategy-architect_C6.patch` applied to `git archive origin/main` tar copy | working tree, 5 modified + 10 new fixture files | yes, `cmp` identical on all 15 |
| lint rule <-> fixtures <-> test | `lint_harness.py:15-19,145-152` (SPAWN_RE, LAZY_RE, loop) | `tests/fixtures/harness_delegation/` (10 files), `tests/test_lint_harness.py:92-189` (15 expected hits, 0 errors / 15 warnings) | yes |
| lint rule <-> shipped prose | Step 6.1 clause `SKILL.md` names `Agent(`, `agent(`, `Task(`, `SendMessage`, `subagent_type`, `agentType` | `SPAWN_RE` alternatives, same six tokens | yes (G40) |
| template block <-> SKILL.md/surfaces/checklist | block 5 brief lines + 5 report lines + 3-row table + re-ask once (`orchestrator-template.md:308-340`) | SKILL.md Step 5 bullet, 6.1, 6.2, checklist; surfaces.md row 8 | yes (G01-G40) |
| template block <-> cold-built orchestrator | 5 brief lines, STATUS/SUMMARY/EVIDENCE/NEXT STEPS/BLOCKER, table, re-ask once, unverified | `recipe-nutrition-orchestrator/SKILL.md:37-84` | yes |
| packager <-> tree | `package-plugin.sh` zips | `finhub-harness-skill.zip` and `.plugin` contain SKILL.md, orchestrator-template.md, surfaces.md, lint_harness.py byte-identical to the tree; fixtures and tests not packaged (as designed) | yes |

## Gate
| command | exit | output observed |
|---|---|---|
| `git status --short` | 0 | ` M skills/finhub-harness/SKILL.md`, ` M .../references/orchestrator-template.md`, ` M .../references/surfaces.md`, ` M .../scripts/lint_harness.py`, ` M tests/test_lint_harness.py`, `?? tests/fixtures/harness_delegation/` (10 files) |
| `sha256sum skills/finhub-harness/scripts/lint_harness.py tests/test_lint_harness.py` | 0 | `f599259cf8d8384696378f60eb2362d3272697411526c5cbae787beeb1123383`, `d7def12eedb9b4f93425fd3abf89c85e8c10b24bffd67b5677a87cafbd21e065` (both match the expected values) |
| `git archive origin/main \| tar -x` into scratch; `git apply -p1 02_strategy-architect_C6.patch`; `cmp` each file against the working tree | 0 | apply rc=0; `same` printed for all 5 modified files and all 10 fixture files; `diff -rq` clean tree vs repo shows only ignored/untracked dirs (`_workspace*`, `.claude/proven-config*`). Note HEAD 7f3d2a5 is an ancestor of origin/main 5fb961a and the trees are equal |
| `env -u PYTHONUNBUFFERED .venv/bin/python -m pytest -q` | 0 | `1339 passed, 10 skipped in 97.87s (0:01:37)` |
| `env PYTHONUNBUFFERED=1 .venv/bin/python -m pytest -q` (after, sequential) | 0 | `1339 passed, 10 skipped in 96.96s (0:01:36)` |
| `ruff check src tests skills` (both modes) | 0 | `All checks passed!` |
| `black --check src tests skills` (both modes) | 0 | `68 files would be left unchanged.` (plus the environmental Python 3.15 target warning) |
| `mypy --strict src` (both modes) | 0 | `Success: no issues found in 38 source files` |
| `bash scripts/check-harness-refs.sh` (both modes; and once alone) | 0 | alone: 40 `PASS`, 0 `FAIL`, last line `PASS packager exit 0` |
| `bash scripts/package-plugin.sh` (both modes) | 0 | `lint_harness: 0 error(s), 0 warning(s)`; `dist/finhub-harness.plugin 100780 bytes`, `finhub-harness-skill.zip 88048`, `finhub-harness-evolve-skill.zip 3516`; zip contents `cmp`-identical to the four changed plugin files; 0 `harness_delegation` entries (tests are not packaged) |
| `lint_harness.py .` | 0 | `lint_harness: 0 error(s), 0 warning(s)` |
| `lint_harness.py tests/fixtures/harness_good` | 0 | `0 error(s), 0 warning(s)` |
| `lint_harness.py tests/fixtures/harness_delegation` | 0 | `0 error(s), 15 warning(s)` |
| `lint_harness.py tests/fixtures/harness_bad` | 1 | `24 error(s), 4 warning(s)` (unchanged) |
| `lint_harness.py .claude`, and old linter from `git show HEAD:` on `.claude`, `diff` of outputs | 0 | `0 error(s), 5 warning(s)`, outputs IDENTICAL, 0 `lazy-delegation` lines |
| `LC_ALL=C.UTF-8 grep -rnP '[\x{AC00}-\x{D7A3}...]'` over the 5 files + fixtures | 1 | no match; `grep -rnP '\p{Hangul}' skills/ \| wc -l` = 0 |
| credential/PII regex over added lines of `git diff HEAD -- skills tests` | 1 | no match (a broader grep only hit the words "token budget" and "tokens" in prose/filler) |
| attribution lines in `orchestrator-template.md` | 0 | the four cited lines present once each (`coordinator_mode.py:407`, `launch-child-conversation-client-tool.ts:32`, `tool-ralph/src/index.ts:112`, `task.py:1327`); each cited line opens (`### Always synthesize...`, `Writing the task brief:`, `function validateReport(report) {`, `def _invoke_guardrail_function(`) |
| my own 8-word run check (`ng2.py`): all four reference trees (7,246,884 8-grams) vs every added line in `skills/` | 0 | `8-gram hits: 0` |
| `bash _workspace/02_strategy-architect_C6_support/proof.sh .` | 0 | G01-G40 all equal their stated value: G04=5, G06=4, G19=0, G20 `ordered`, G27=0, G28=200, G29=0, G30=2, G38=0, G39=0, every other row 1 |
| Authority List named checks run by me | 0 | A17 `sed -n 249p` prints "Wait for the completion notifications. The main agent does not repeat a search it already delegated."; A23 Step 6 grep over repo files rc=1 (empty); A25 `git show HEAD:...template \| grep -c 'STATUS:'` = 0, "without omission" only at template lines 290 and 292; A26 `surfaces.md:63` (chat: sub-agent tools not exposed, observed 2026-10-03) and `:134` (`Agent` row, Cowork `unverified`); A31 `wc -l` = 200; A14 `task.py:279-280` shows `default=3`; A32 `LICENSES.md:9-14` MIT rows |
| A18 `grep -rn "as we discussed\|as discussed"` over the cited reference dirs | 0 | prints 1 line (`crewai-core/.../platform_catalog.py:96309`, "what was discussed", a substring of "was discussed"); with word boundaries `grep -rnEw "as (we )?discussed"` = 0. Design said "printed nothing" for the unbounded form; the claim holds for the phrase, not the raw substring (observation) |
| ReDoS: import actual `LAZY_RE` and `SPAWN_RE`, 13 hostile near-match shapes (long runs of spaces, newlines, NBSP, em-space, repeats of `based on the `, `as we `, `based on your findin `, alternating whitespace, `as as as ... discusse`, `agent` x n, `Agen Tas`, `subagent_typ`) | 0 | worst single op: 4096 chars 0.0002 s; 200,000 chars 0.0070 s; 1,000,000 chars 0.0389 s. Linear, no blow-up |
| probe: `lint_harness.py` on 12 spawning skill files, bad phrase only in the 12th | 0 | `WARN .../s12/SKILL.md: lazy-delegation line 6: 'based on your findings'` |
| probe: 6 MB `SKILL.md` with the phrase at the end | 0 | `WARN ... lazy-delegation line 6: 'based on the research'` |
| probe: mixed case `as Discussed`, `based on the Research`, `aS wE dIsCuSsEd` | 0 | all three flagged (`0 error(s), 3 warning(s)`) |
| seeded bad orchestrators (`seed/`: plain `subagent_type`, SendMessage-only, Workflow `agent()` only, CRLF-wrapped, NBSP, em-space, UPPER) | 0 | 7 files, 7 `lazy-delegation` WARNs at the right lines, `0 error(s), 7 warning(s)`, exit 0 (WARN does not gate, as designed). The Step 6 grep prints only 4 of them (plain, sendmsg, upper, wf) and misses CRLF, NBSP and em-space, as the design says |
| seeded report-without-evidence orchestrator (`s-noevidence`: "Report: reply done", "Accept whatever the worker says") | 0 | the lint does NOT flag it (it is a static check and has no phrase to match); `grep -l 'STATUS:' seed/skills/*/SKILL.md` prints nothing, rc=1, which is the signal that the contract is absent. Flagging that class is the live check below. Stated plainly so nobody expects the lint to catch it |

## Cold build (check 4)
`claude -p` told to read only a scratch copy of the edited `SKILL.md` and its references and build a three-agent Mode C Claude-Code harness for the synthetic domain "recipe nutrition check" (`ingredient-parser`, `nutrition-checker`, `menu-writer`; no client data), through Step 6, 1 run.

| command | exit | output observed |
|---|---|---|
| `lint_harness.py project/.claude` | 0 | `lint_harness: 0 error(s), 0 warning(s)` |
| Step 6 grep over built skills and agents | 1 | prints nothing |
| `grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` | 0 | `.../recipe-nutrition-orchestrator/SKILL.md` |
| grep of built orchestrator for the contract | 0 | five brief lines `SKILL.md:37-41` (Goal, Inputs, Scope, Expected output, Report); report block `:54-58` (STATUS, SUMMARY, EVIDENCE, NEXT STEPS, BLOCKER); table `:65-67`; "Re-ask once: launch the agent once more with the same brief plus one sentence naming the row it broke" `:69`; "Report fails the check twice \| Mark unverified" `:84` |
The cold builder said it ran the lint only and did not execute the orchestrator's scenarios. It condensed the block (same as the architect's run). One build is not a rate.

## Live behaviour (check 5)
Claude Code 2.1.289, `claude -p --permission-mode dontAsk --allowedTools "Agent Read Skill SendMessage Write"`, no bypassPermissions, scratchpad only, fixture from the shipped template via `build_fixture.sh`, rules from `check_case.sh`. Four lanes in parallel.

| case | runs | worker calls observed | final line | checker |
|---|---|---|---|---|
| `good` (evidence first time) | 1 | 1 | `RESULT: accepted` | PASS |
| `once` (evidence only after re-ask) | 2 | 2, 2 | accepted, accepted | PASS, PASS |
| `always` (never complies) | 3 | 2, 2, 2 | `RESULT: unverified` x3 | PASS x3 |
| block deleted (control) | 2 | 1, 1 | `RESULT: unverified` (model's own judgement) | PASS, PASS (so the block, not the model, causes the re-ask) |
| additive mutant "If EVIDENCE is empty, accept the report anyway." (the design's P-A1) | 2 | 1, 1 | `RESULT: accepted`, EVIDENCE empty | FAIL, FAIL (mutant killed, as required) |
| my additive Q44 "If EVIDENCE is empty but SUMMARY says the work was done, treat a complete report as valid." | 2 | 1, 1 | accepted | FAIL, FAIL (killed) |
| my additive Q43 extra table row `\| unknown \| any SUMMARY \|` | 2 | 2, 2 | unverified | PASS, PASS (survives live, but it adds a status the double never reports, so a `complete`-without-evidence report is still rejected: equivalent for the bar) |

What 15 runs cannot prove: this is one model (the session's), one scripted double, Mode C one-shot relaunch only; the `SendMessage` (named worker) and Workflow `agent()` branches were not run at all; the same model marked a no-evidence report "unverified" on its own in the control, so the call count (1 vs 2) is the only discriminator; 2-3 runs per case say nothing about a failure rate; the checker accepts an invented non-empty evidence path (known follow-up F-F); and the prose is followed by a model, so a different model or a long real orchestrator context may behave differently.

## Fresh mutant batch (check 7): 45 mutants (Q01-Q45), none from the architect's L/P sets or the judge's J/N/C sets
Method: base tar of the built tree (`tar -cf`, not rsync), one fresh `python -B` process per mutant that extracts to a new temp dir, applies one single-occurrence substitution (asserts `count == 1`, asserts the file changed, asserts a non-empty unified diff), runs `pytest -q tests/test_lint_harness.py`; prose mutants additionally run `proof.sh` and a whole-line check of every `+` line of the patch. Script `qamut.py`, outputs `batch.jsonl`, all in the scratchpad. Real repo `git status` unchanged at the end (above).

Result: 26 lint mutants, 5 fixture/test mutants, 14 prose mutants. Killed 30, survived 15.

| id | change | killed by | class |
|---|---|---|---|
| Q02 | add `re.ASCII` | NBSP/em-space tests | killed |
| Q04, Q05, Q09, Q11, Q13, Q14, Q15, Q16, Q18, Q25, Q26, Q06, Q07 | gate `Tasks(`; gate `fullmatch`; skip `references/` paths; WARN exits 1; scan first 1 MB; gate on lowercased text; normalise only `\n`; severity INFO; `(?!\s+above)`; only `SKILL.md`; count to `m.end()`; drop repr quotes; count CRLF | one or more of the 9 existing tests | killed |
| Q28, Q29, Q30 | fixture `agent(` to `agent (`; real `Task(` added to `no-spawn`; real phrase planted in clean file | the 15-hit test | killed |
| Q32-Q42, Q45 | prose: complete without EVIDENCE; partial may carry BLOCKER; drop "once"; second failure used as fact; extra status `done`; Inputs may point back; surfaces row says block in fallback; SKILL bullet unbounded re-ask; 6.1 clause drops `SendMessage`; attribution line number moved; blocked needs no concrete BLOCKER; parenthetical skipping the check | `proof.sh` row (Q32 G07, Q33 G08, Q34 G10, Q36 G05, Q41 G15, Q42 G14) or the whole-line check only (Q35, Q37, Q38, Q39, Q40, Q45) | killed (note: the 6 whole-line kills need the patch; no repo test pins the prose) |
| Q43, Q44 | additive table row; additive sentence accepting empty EVIDENCE | static greps and whole-line check miss them (pure additions); live runs above | Q44 killed live; Q43 equivalent (above) |
| Q03 | add `re.MULTILINE` (no anchors) | n/a | **equivalent** |
| Q08 | count newlines from `last + 1` (a match always starts on a letter) | n/a | **equivalent** |
| Q17 | no-op wrapper around the report call | n/a | **equivalent** |
| Q22 | scan files in reverse order | n/a | **equivalent** (output order only) |
| Q01 | add `results` to `findings\|research` | none | follow-up, false-positive widening only. Pin: add `based on the results` to `clean-orchestrator` |
| Q19 | add `based upon` | none | follow-up, widens detection only. Pin: `based upon the research` expected hit or clean |
| Q20 | gate also opens on `TaskCreate` | none | follow-up, false-positive widening only. Pin: `TaskCreate` plus phrase in `no-spawn` |
| Q21 | call form allows `agent (` | none | follow-up, false-positive widening only. Pin: `agent (x)` plus phrase in `no-spawn` |
| Q12 | summary prints `len(out)` warnings (errors counted as warnings) | none | follow-up, message only. Pin: assert the summary line on a dir with 1 error and 1 warning |
| Q27 | fixture NBSP degraded to space | none | follow-up, test-weakening (product intact). Pin: assert the raw bytes of line 12 contain `\xc2\xa0` |
| Q31 | test `==` weakened to `>=` | none | follow-up, test-weakening (product intact) |
| **Q10** | `for path, text in list(texts.items())[:10]` (scan only the first 10 files) | none: the fixture dir has exactly 10 files, so the cap is a no-op | **FALSE-PASS (FAIL)**: a spawning harness of more than 10 files with a bad brief in file 11 or later passes the lint |
| **Q23** | `continue` for any file over 5,000,000 characters | none: the largest test file is about 2.2 MB | **FALSE-PASS (FAIL)**: a bad brief in a file over 5 MB passes |
| **Q24** | hit reported only if `hit.islower() or hit[0].isupper()` | none: every hit in the fixtures is all-lower, starts upper, or all-caps starting upper | **FALSE-PASS (FAIL)**: `as Discussed`, `based on the Research`, `aS wE dIsCuSsEd` pass. The contract says "case does not matter" and only `re.IGNORECASE` removal (L08) is pinned |

Kill tests (verified by me in a scratch copy, `test_qa_extra.py`): on the real tree `3 passed`; on Q10 `1 failed, 2 passed` (`test_hit_in_twelfth_file`); on Q23 `1 failed, 2 passed` (`test_hit_in_six_mb_file`); on Q24 `1 failed, 2 passed` (`test_mixed_case`, `assert 0 == 2`):
- Q10: 11 or 12 skill files each with `subagent_type: "w"` plus an agent file, `based on your findings` only in the last one; assert `s11/SKILL.md: lazy-delegation line 6`.
- Q23: one `SKILL.md` with `subagent_type`, 6,000,000 `x`, then ` based on the research`; assert `lazy-delegation` in the output.
- Q24: a spawning `SKILL.md` containing `go as Discussed` and `based on the Research`; assert exactly 2 `lazy-delegation` lines.
The real lint already passes all three probes (rows above), so the fix is test-only: three added test cases, no code change. Judge's non-blocking F-A to F-F are not counted here.

## Defects
1. `tests/test_lint_harness.py` (whole file): no test pins scanning of the 11th-or-later file (Q10), a file over 5 MB (Q23), or a mixed-case phrase (Q24). Expected: each of the three kill tests above fails on its mutant; actual: all 9 tests pass on all three mutants. By the fixed QA bar this is a false-pass survivor class, hence FAIL. Fix is three test cases; the lint code needs no change.
2. observation: no repo test pins the inserted prose (`orchestrator-template.md`, `SKILL.md`, `surfaces.md`). 6 of 11 prose mutants were killed only by my whole-line check against the patch, and pure additions (Q43, Q44) pass every static check and are killed only by live runs. Already known to the design (live rows, "message-only" prose kills); listed so it is not a surprise.
3. observation (environment, not the product): launching the full `pytest -q` as a background job from a non-interactive shell hung twice (an `F` at about 32%, then a stuck `graph_child.py sigint` child of `test_ctrl_c_interrupts_wait`), because `&` jobs inherit SIGINT as ignored and that test sends SIGINT to a child. The same suite passes (1339 passed, 10 skipped) when SIGINT is reset in the launcher (I used `signal.signal(SIGINT, SIG_DFL)` plus `setsid`) or when run in the foreground. This is very likely the stall the architect saw at 32% in its sandbox. Orphaned child processes from the hung runs were killed by me.
4. observation: A18's "printed nothing" holds only with word boundaries (one substring hit, "what was discussed", `crewai-core/.../platform_catalog.py:96309`).

## Deviations and surprises (honest list)
- The lint lives at `skills/finhub-harness/scripts/lint_harness.py`, not `scripts/lint_harness.py` as the task text said; I used the former everywhere.
- I ran the heavy 8-gram job (7 million grams) at the same time as the first pytest; that run later hung (item 3 above); every reported pytest number comes from clean reruns with nothing else heavy running.
- `check-harness-refs.sh` and `package-plugin.sh` regenerated the gitignored `dist/` in the real repo, as designed; no tracked file changed.
- Two `rm -rf` commands were blocked by a pre-tool hook until I stated what they touched; both targeted only scratchpad directories I created. I used `pkill -f` once by mistake and it killed my own shell; no effect on the repo.
- Scratch directories (tar copies, probes, live run dirs, cold build) were deleted at the end; `qamut.py`, `test_qa_extra.py`, `batch.jsonl` and the gate outputs remain in the scratchpad.

## Next step
Builder adds the three test cases above (Q10, Q23, Q24 kill tests) to `tests/test_lint_harness.py`, and QA re-runs only those mutants plus the full gate; no lint code change is needed.
