TOTALS: UPHELD 43 / REJECTED 0 / UNVERIFIED 0 — round 2/3

# Adversarial verdict — C6 delegation contract (revision 2), round 2

- Audited file: _workspace/02_strategy-architect_C6.md (revision 2) with `02_strategy-architect_C6.patch` and `02_strategy-architect_C6_support/`. Prior verdict: `02_adversarial-risk-judge_C6_r1.md` (31 / 5 / 0).
- Fresh context; the architect's chat was not read. No extra-round authorisation exists (round 2 of 3).
- Scratch: tar copies of the repo, `U` (unpatched) and `P` (patch applied cleanly, 15 files), `references/` and `.venv` symlinked, under `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/r2/`. Nothing in the repo or in the architect's files was edited; `git status --short` in the real repo is empty.
- Rows A1-A40 are the architect's. S1-S3 are my r1 rows, closed below (counted in the totals).
- Carry-forward check: I diffed the Authority List rows of the r1-audited copy of the design (kept in my r1 scratch, `cp6/_workspace/…C6.md`) against rev 2. Result: A19, A20, A21 CHANGED; A34-A40 NEW; the other 30 rows are byte-identical. Every carried row whose named check reads a changed file was re-run on the patched text (see the "re-run" column).

## Claims

| id | verdict | cited | found at cited line (±5) / re-run | reason / correct location |
|---|---|---|---|---|
| A1-A11 | UPHELD (carried, row text identical) | references/ lines as in r1 | spot re-opened: openhands `launch-child-conversation-client-tool.ts:17` ("cannot see this conversation's history — everything it needs must be in…"), coordinator_mode.py:405 (Workers can't see your conversation), :411 (Never write "based on your findings"…), crewai task.py:279-280 | references are pinned submodules; no change since r1 |
| A12 | UPHELD (carried) | NET-NEW | re-run: G05 = 1 on patched template | — |
| A13 | UPHELD (carried) | crewai guardrail.py:68-70; task.py:1343, :1382, :1400 | re-opened; 1327 (`_invoke_guardrail_function`) is the same function as the 1343-1400 loop | — |
| A14 | UPHELD (carried) | NET-NEW (cap one) | re-run: G10 = 1, G11 = 1; `task.py:279-280` `default=3` confirmed; backlog row C6 says "re-asked once" (line 53). Live on rev 2: `always` 2 and 2 worker calls (my runs), never 3 | — |
| A15 | UPHELD (carried) | coordinator_mode.py:384; :440 | unchanged references | — |
| A16 | UPHELD (carried) | NET-NEW (one-shot relaunch) | re-run: G12 = 1; live `once` 2 and 2 calls, corrected report accepted (mine) | — |
| A17 | UPHELD (carried) | NET-NEW | re-run: `sed -n 249p` on the patched template prints "Wait for the completion notifications. The main agent does not repeat a search it already delegated." | line number unchanged: the insertions sit after line 297 |
| A18 | UPHELD (carried) | NET-NEW ("as discussed") | re-run: `grep -rniE "as we discussed\|as discussed"` over the four cited reference paths: 0 lines; the E9 test (fixture lines 8, 11, 15) passes | — |
| A19 | UPHELD | NET-NEW (matching rules) | CHANGED r2, figures verified. Step 6 grep on `lazy-orchestrator/SKILL.md` prints lines 7 8 11 13 14 (5 lines); the lint reports 9 hits on 8 lines (7, 8, 9, 11, 12, 13 twice, 14, 15) and the test pins all nine; my independent J04 mutant (`\s+` to ASCII `[ \t\n]+`, all five gaps, real single-occurrence edit) is killed by BOTH `test_lazy_delegation_is_flagged_in_spawning_files_only` and the new S3 test | the stale "5 of 7" is gone from the design; the shipped text contains no count |
| A20 | UPHELD | NET-NEW (scope gate) | CHANGED r2, the r1 repro closed. In a scratch `.claude` whose files name neither `subagent_type` nor `agentType`: `agent("Based on your findings…", {schema})` WARN, `Task(prompt: "As discussed…")` WARN, `Agent(name: "w", prompt: "based on the research above…")` WARN, `SendMessage(… "based on your findings…")` WARN (4 of 4; the unpatched lint prints 0/0 on the same files). Four fixtures `wf-`, `task-`, `named-`, `msg-orchestrator` each hit at line 6; `worker.md` and `no-spawn` silent. `workflow-recipes.md:200` "If you omit `agentType`, the default workflow sub-agent is used" confirmed | see follow-up F-A (the bare words are not pinned) |
| A21 | UPHELD | NET-NEW (WARN, exit 0) | CHANGED r2 (count 11 to 15): `lint_harness.py tests/fixtures/harness_delegation` → `0 error(s), 15 warning(s)`, exit 0; my WARN→ERROR mutant killed (2 tests) | — |
| A22 | UPHELD (carried; named check re-run) | NET-NEW (linear) | re-run on the ACTUAL `LAZY_RE` and widened `SPAWN_RE` (`redos3.py`), 18 hostile shapes at n = 4,096, 200,000, 1,000,000 units (the last up to 15 MB): ws runs, ten whitespace kinds, `agent`×n, `Task`×n, `Agent`+spaces, `SendMessag `×n, `subagent_typ `×n, `x`×n+`Task(`, near-misses `as we discusse`, boundary `as`+é, 800k-char real hits; worst 0.0035 s / 0.21 s / 0.89 s; time scales linearly with size, no shape superlinear. New `test_lazy_delegation_*_linear` tests take 0.23 s and 0.31 s against a 20 s bound | see F-C (timing kill margin) |
| A23 | UPHELD (carried; re-run) | NET-NEW (repo has no hit) | Step 6 grep over `skills/*/SKILL.md .claude/skills/*/SKILL.md .claude/agents/*.md` on P: 0 lines (G27 = 0); `lint_harness.py .` 0/0; `.claude` 0 errors 5 warnings, output byte-identical to the unpatched tree (md5 equal), no lazy line | — |
| A24 | UPHELD (carried; re-run) | NET-NEW | G19 = 0 on the extracted block | — |
| A25 | UPHELD (carried; re-run on U) | NET-NEW | `grep -c 'STATUS:'` = 0 and `grep -rln lazy-delegation skills tests` empty on the unpatched tree; "without omission" at lines 290 and 292 only | — |
| A26 | UPHELD (carried; re-run) | NET-NEW (Code only) | `sed -n 63p surfaces.md` (chat: sub-agent/SendMessage/Task/Workflow not exposed, observed 2026-10-03), `sed -n 134p` (Agent row, Cowork `unverified`), `docs/surface-verification.md:20` P4. The new row 8 is appended after line 161 so these lines did not move | — |
| A27 | UPHELD (carried; re-run live) | NET-NEW (re-ask behaviour) | Claude Code 2.1.289, no bypassPermissions, architect's `build_fixture.sh` + `run.sh` + `check_case.sh` as shipped on the patched template: `good` 1 call PASS; `once` 2 and 2 PASS; `always` 2 and 2, final line "unverified", PASS; block deleted (`noblock`) 1 call | — |
| A28 | UPHELD (carried) | NET-NEW (cold build) | not re-run (one run, disclosed as one run). Re-ran its conditions on the patched text: lint 0/0, G23 grep, block present | — |
| A29 | UPHELD (carried; re-run) | NET-NEW | in P: `scripts/check-harness-refs.sh` 40 PASS, 0 FAIL; `scripts/package-plugin.sh` rc 0, lint 0/0, three archives | — |
| A30 | UPHELD (carried; re-run, broader) | NET-NEW (no 8-word run) | all added lines of the five touched files plus the six fixture files (1,743 distinct 8-grams) against every text file under `references/` (< 3 MB each): 2 hits, both the attribution path string `references openharness src openharness coordinator coordinator mode py` (in the port map `portmaps/openharness-9b2efd7.md`), a path not prose | — |
| A31 | UPHELD (carried; re-run) | NET-NEW (<500 lines) | `wc -l` = 200 | — |
| A32 | UPHELD (carried) | references/LICENSES.md:9, :11, :12, :14 | unchanged; no autogpt_platform and no dify citation | — |
| A33 | UPHELD (carried; re-run) | NET-NEW (attribution lines) | G15-G18 each 1; the cited lines open to the function/heading they attribute (coordinator_mode.py:407 "Always synthesize", launch-child…ts:32 "Writing the task brief:", index.ts:112 `validateReport`, task.py:1327 `_invoke_guardrail_function`) | — |
| A34 | UPHELD | NET-NEW (widening costs nothing in this repo) | `lint_harness.py .` 0/0; `.claude` no lazy line; G27 = 0; look-alikes silent (my mutants dropping a leading boundary and a trailing boundary are killed). Verified false positive class as disclosed: a worker file that merely says "SendMessage" and holds a banned phrase warns (my probe `agents/wk.md`) | see F-A, F-B |
| A35 | UPHELD | NET-NEW (Step 6.2 grep is a stricter fallback) | on `harness_delegation` with the shipped glob (`skills/*/SKILL.md agents/*.md`): 15 lines; the lint is silent on 5 of them (`clean-orchestrator` 7, 8, 10; `no-spawn` 6; `agents/worker.md` 7); G34 = 1, G38 = 0 | — |
| A36 | UPHELD | NET-NEW (Step 6.1 clause) | G40 = 1, G39 = 0; the six tokens in the SKILL.md clause (`Agent(`, `agent(`, `Task(`, `SendMessage`, `subagent_type`, `agentType`) equal the six `SPAWN_RE` alternatives, and equal the template paragraph and A20; the clause says "calls … or names", the gate is wider (any mention), so the shipped text claims less than the lint does | no automated test ties the clause to `SPAWN_RE` (follow-up F-D) |
| A37 | UPHELD | NET-NEW (the S3 test) | `test_lazy_delegation_in_a_dot_claude_project_with_a_late_gate_and_odd_whitespace` passes on P; my own re-creations of J04, J14 (gate `text[:2000]`) and J19 (skip dot root), single-occurrence edits, each fail it (J14, J19: `1 failed, 8 passed`; J04: `2 failed, 7 passed`) | — |
| A38 | UPHELD | NET-NEW (re-ask is the only retry) | G35 = 1; live rerun on the rev 2 block (mine): `once` 2 and 2 calls, `always` 2 and 2 (never 3); consistent with the existing text, see "Behaviour change" below | the second half of the sentence is not pinned by G35, see F-E |
| A39 | UPHELD | NET-NEW (limits and attribution text) | G36 = 1, G37 = 1, G15/G16 = 1; Limits paragraph present in the template, SendMessage branch, Workflow branch and the Mode A `schema` mapping each marked untested/UNVERIFIED | — |
| A40 | UPHELD | NET-NEW (live support runs as shipped) | `build_fixture.sh` then `run.sh` then `check_case.sh` from a clean directory, no edits: `good` PASS, `once` PASS x2, `always` PASS x2, control PASS, additive mutant FAIL x2 (1 call, accepted) | — |
| S1 | UPHELD (closed) | gate: black | `black --check` on the two touched Python files: "2 files would be left unchanged" (rc 0) | — |
| S2 | UPHELD (closed) | E5 wording | Step 6.2 now says "a stricter manual fallback (no word boundaries, every file, blind to a phrase wrapped over two lines): judge each hit by hand"; "same test" and "prints nothing" are gone (G34 = 1, G38 = 0); the five silent hits are listed (A35) | — |
| S3 | UPHELD (closed) | mutation bar | J04, J14, J19 each killed, see A37 | — |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C6 | N/A text lint and prose, no pricing or returns | N/A | N/A | N/A | N/A | N/A no eval, verifier or data split touched |

## Reproduced gates (patched scratch copy P; U = unpatched)

| gate | result |
|---|---|
| `pytest -q tests/test_lint_harness.py` | 9 passed (0.85 s) |
| `ruff check --no-cache` (script + test) | All checks passed |
| `black --check` (script + test) | 2 files would be left unchanged |
| `mypy --strict` (script + test) | Success: no issues found in 2 source files |
| `lint_harness.py` on `.` / `.claude` / `harness_good` / `harness_bad` / `harness_delegation` | 0 err 0 warn / 0 err 5 warn (identical to unpatched, no lazy line) / 0/0 / 24 err 4 warn / 0 err 15 warn |
| `scripts/check-harness-refs.sh` (in P) | 40 PASS, 0 FAIL |
| `scripts/package-plugin.sh` (in P) | rc 0, lint 0/0, three archives |
| Hangul, `LC_ALL=C.UTF-8 grep -rP '[\x{AC00}-\x{D7A3}]'` over SKILL.md, template, surfaces.md, the two Python files, the fixture dir | no output, rc 1 (required) |
| 8-word runs | see A30: only the attribution path string |
| attribution lines | G15-G18 each 1; "as discussed" is stated as not from any reference (G37 = 1) |
| `proof.sh` G01-G40 on P | every row equals its expected value (G19 0, G20 ordered, G27 0, G28 200, G29 0, G38 0, G39 0, the rest 1/5/4 as listed) |
| real repo | `git status --short` empty; nothing written |

### Full `pytest -q` (the architect's undiagnosed stall at ~32% with one F)

| tree | `env -u PYTHONUNBUFFERED` | `PYTHONUNBUFFERED=1` |
|---|---|---|
| U (unpatched) | 1334 passed, 10 skipped, 98.8 s | 1334 passed, 10 skipped, 96.6 s |
| P (patched) | 1339 passed, 10 skipped, 98.7 s | 1339 passed, 10 skipped, 98.5 s; second run alone on the machine 1339 passed, 97.8 s |

Five single-process full runs, `-p no:cacheprovider`, no `-x`, pytest started from the copy's root: no stall, no F, no timeout; four of them ran two at a time on 4 cores. The U result equals the C4 baseline (1334, 10 skipped) and P adds exactly the 5 new tests (9 vs 4 in the lint file). The stall does NOT reproduce on either tree, in either buffering mode. I cannot diagnose the architect's run from outside: it is not caused by the patch on any evidence I have (the unpatched tree and the patched tree are equally green, and the new tests take 0.6 s in total), and it is not reproduced as a flake either. Treat it as an unreproduced environment event; if it recurs, capture `pytest -v -p no:cacheprovider` output to a file and the F's node id.

## Reproduction of the r1 blockers

| r1 id | status | evidence |
|---|---|---|
| A19 | closed | figures verified above; the shipped text states no count |
| A20 | closed | the four r1 repro shapes now warn, see A20 |
| S1 | closed | black green |
| S2 | closed | wording fixed, see S2 |
| S3 | closed | J04, J14, J19 killed |

## Attack on what rev 2 introduced

1. Widened `SPAWN_RE`. No ReDoS (A22). No new false positive on the repo's own text: `lint_harness.py .` 0/0, `.claude` unchanged, `harness_good` 0/0. Disclosed false-positive class confirmed by probe: any spawning file's own prose that mentions `SendMessage`, `Agent(`, `Task(`, `agent(` plus a banned phrase warns (WARN, exit 0). One more instance in the same class that the design does not name: the very common plural "agent(s)" matches `agent(` (my probe `skills/prose/SKILL.md`: "Use the agent(s) listed. Write the report based on the research." warns). Not blocking: WARN, same class as Decisions item 7, Step 6.1 says fix or say why it stays. Line counter: linear, pinned at `line 100005` by a 100,000-hit test; line numbers count `\n` only (follow-up F6 from r1, unchanged). The L21 kill is wall-clock dependent in one direction only: the genuine code runs the test in 0.31 s against a 20 s bound (60x margin), so the test cannot flake on a slow machine; the naive per-hit `count(…, 0, …)` mutant took 48.5 s here under load (same 100,000-hit file), so a machine more than ~2.4x faster than this one would let that mutant pass the test (F-C).
2. Step 6.1 / Step 6.2 / surfaces.md / Limits text. No sentence found that claims more than the lint or the grep delivers. The clause says "calls … or names" while the gate is a bare mention (under-claim). Limits marks the `SendMessage`, Workflow and Mode A `schema` branches untested / UNVERIFIED. `surfaces.md` row 8 is a statement of where the block goes (follow-up F9 from r1, unchanged).
3. "The re-ask is the only retry for an invalid report". Consistent with the existing text: Template C error table "If one agent fails, retry once" (line 258) and SKILL.md Error policy "one retry then proceed" govern a worker that fails or errors; an invalid report from a worker that returned is now explicitly the re-ask and nothing more. It does not remove the retry-once for a crash, so a worker that errors and then returns an invalid report can still be launched three times in total; the sentence says "for an invalid report" and does not claim otherwise. `quality-gates.md` (one builder retry on QA FAIL) is a different loop and is not touched. Modes A (Workflow `agent()` second call), B (`SendMessage`) and C (relaunch without `name`) are each named in the one paragraph. Live: good 1; once 2 and 2; always 2 and 2 ending "unverified"; block deleted 1; additive mutant (the sentence "If EVIDENCE is empty, accept the report anyway." inserted before the validity paragraph) 1 call and accepted, checker FAIL on 2 of 2 runs, so the final-line checker catches it (it did not in r1). The checker's three rules (calls = 2, a final line, "unverified" or non-empty last EVIDENCE) were each mutated and each mutant is killed by a seeded run (see mutants).
4. Attribution. The sentence listing the phrases now says "as discussed" is not from any reference; the `adapted from` lines sit on the self-contained-brief paragraph (coordinator_mode.py:407, launch-child…ts:32), the report/validity paragraph (index.ts:112) and the re-ask paragraph (task.py:1327, "the cap of one is ours"). Fixed.

## Independent mutants (12; each a verified real single-occurrence substitution, `mut.py` asserts count == 1 and a changed file; fresh copy and fresh pytest process each; kill test is `tests/test_lint_harness.py`, full file, no `-x`)

Targets: widened `SPAWN_RE` (N1-N8), the final-line checker (C1-C3), the re-ask-only-retry sentence (M11). The four new fixtures are exercised through N1-N4 (each token removal must be killed by exactly its fixture); the new test through N8 and the r1 J mutants.

| id | mutation | result | kill / note |
|---|---|---|---|
| N1 | drop `SendMessage` from the gate | KILLED | `test_lazy_delegation_is_flagged_in_spawning_files_only` (msg-orchestrator) |
| N2 | drop `Task` from the call forms | KILLED | same test (task-orchestrator) |
| N3 | drop `Agent` | KILLED | same test (named-orchestrator) |
| N4 | drop `agent` | KILLED | same test (wf-orchestrator) |
| N5 | drop `\b` before the call forms | KILLED | same test (look-alikes in no-spawn) |
| N6 | drop the trailing `\b` after the token group | KILLED | same test |
| N7 | call forms lose the `\(` (bare words `agent`, `Agent`, `Task` open the gate) | **SURVIVED** | false-positive widening only: no fixture holds a bare "agent"/"Agent"/"Task" word next to a banned phrase while staying silent. Kill test: add the line "the agent keeps a Task list; based on the research" to `no-spawn/SKILL.md` and `agents/worker.md` and expect silence. Follow-up F-A |
| N8 | gate reads only `text[:50000]` | **SURVIVED** | false negative only for a file whose first gate token lies past 50,000 characters (the S3 test's filler is about 4,800 characters; the J14 2,000-character window IS killed). Kill test: a 60,000-character filler before `subagent_type` and a banned phrase, expect 1 hit. Follow-up F-A, not blocking: SKILL.md files are capped at 500 lines and a first spawn token that late is not a shape the contract asks for; agent files have no cap but a delegating agent file names its tools at the top |
| C1 | `check_case.sh always`: drop the `[ -n "$final" ]` condition | KILLED | seeded run S1 (the a1 run with its `result` event removed): real FAIL, mutant PASS |
| C2 | `[ "$calls" = 2 ]` to `-ge 2` in the `always` rule | KILLED | seeded run S2 (a third Agent call): real FAIL, mutant PASS |
| C3 | last EVIDENCE read by `head -1` instead of `tail -1` | KILLED | seeded run S5 (accepted after non-empty evidence on the re-ask): real PASS, mutant FAIL. The checker has no self-test of its own; these kills depend on seeded runs I built from my live runs, not on anything shipped |
| M11 | the sentence's second half inverted: "the general retry-once rule then adds a second retry." (live `always` fixture, 2 runs) | **SURVIVED** | still 2 worker calls and "unverified" on both runs: the earlier "If the second report is invalid too, do not ask again" in the same paragraph dominates; G35 greps only the first half of the sentence. Kill test: extend G35 to the whole sentence, or `grep -c 'does not add a second'` = 1. Follow-up F-E |

Also re-created from r1 and killed: J04, J14, J19 (A37), L13 WARN→ERROR (A21). That is 16 runs; the "at most 12 new" budget applies to N1-N8, C1-C3, M11 (12).

## Blocking vs follow-up

Blocking: none. No seeded bad brief passes the shipped lint (the only false-negative survivor, N8, needs a file of more than 50,000 characters before its first spawn token); no seeded invalid report passes the live protocol or the checker; no claim is stated as verified without evidence; every citation opens to the claimed line; no stale named check (each re-run on the patched text); every gate green.

Follow-up (none blocks; none can let a seeded bad brief or invalid report through in the shapes the contract names):
- F-A Lint test strength: add the bare-word silence line (N7) and a 60,000-character-prefix case (N8); note "agent(s)" in the Decisions item 7 list of false-positive spellings.
- F-B Mention the plural "agent(s)" next to `agent(` in Does not cover (it trips the gate).
- F-C The L21 kill relies on wall-clock time (naive mutant 48.5 s under load vs a 20 s bound): pin by call count instead (for example patch `str.count` through a counting subclass, or assert hits and line numbers on a file where the naive variant is observably slower by more than 10x the bound), or raise the hit count to 400,000.
- F-D No test ties the Step 6.1 clause and the template paragraph token lists to `SPAWN_RE`; today they agree (verified by hand, A36).
- F-E Extend G35 to the full sentence; the second half is not behaviour-load-bearing (M11).
- F-F Carried from r1 and unchanged: F2 (report grammar: status case, repeated STATUS, padded items, literal `none`), F6 (line numbers count `\n` only), F7, F9 (`surfaces.md` row 8 is a statement), J01-J03 and J07 (false-positive mutants of the phrase regex), Mode A schema mapping, no live run of the `SendMessage` and Workflow branches. A made-up evidence path still passes (observed again: the `always` double's second reply carried invented evidence in one of my runs and the orchestrator still ended "unverified"); the Limits paragraph says so.

## Message to orchestrator

clean. TOTALS: UPHELD 43 / REJECTED 0 / UNVERIFIED 0 — round 2/3. All five r1 blockers closed and reproduced. Full `pytest -q` is green on both trees in both buffering modes (U 1334 passed / 10 skipped, P 1339 passed / 10 skipped); the architect's stall did not reproduce and is not caused by the patch on any evidence. Survivors of my 12 new mutants (N7, N8, M11) are false-positive, far-edge false-negative and prose-pin gaps, listed as follow-ups F-A and F-E. The architect may relay.
