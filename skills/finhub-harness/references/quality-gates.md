# Quality Gates: Authority List, Adversarial Audit, Boundary QA, Honest Reporting

Four gates that keep a generated harness from shipping confident but wrong work. They were developed and exercised in the Master FinHub build (slices 8-11) and are written here as a pattern any harness built by `finhub-harness` can adopt. Every number below comes from a run record in `_workspace/` of that build; the source file is named next to it.

## Table of Contents

1. [The Authority List](#1-the-authority-list)
2. [Fresh-context adversarial audit](#2-fresh-context-adversarial-audit)
3. [Boundary QA after every slice](#3-boundary-qa-after-every-slice)
4. [Honest reporting](#4-honest-reporting)
5. [Checklist to paste into a QA agent definition](#5-checklist-to-paste-into-a-qa-agent-definition)
6. [What this reference could not verify](#6-what-this-reference-could-not-verify)

How the gates fit together: the architect writes a design that ends in an Authority List; a judge with no shared context audits that list; the builder implements only what survived; QA checks each built slice against the design's declared interfaces; the last report tells the truth about what was and was not proven.

---

## 1. The Authority List

The Authority List is the closing section of the design document. It is the only part the judge audits, so it must stand alone: a reader with no chat history opens each cited line and decides whether it supports the claim.

### 1-1. Row format

```markdown
## Authority List

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | The loop ends a run when a model turn contains no tool calls | references/<repo>/<path>:<line> | 1 |
| A5 | Regex command denylist (`rm -rf /`, fork bomb, `mkfs`) | NET-NEW: spec requirement; no reference implements a denylist | 3 |
```

Rules, taken from `.claude/skills/runtime-slice-design/references/authority-list.md`:

1. One claim, one primary citation in the form `references/<repo>/<path>:<line>`. A second line is allowed only when the claim genuinely spans two places.
2. Evidence must live inside `references/`. A URL, package documentation or "commonly known" is not evidence.
3. A claim is falsifiable. "Uses a loop" is not a claim; "ends the run when a turn has no tool calls" is.
4. Add one row for every behaviour the builder will rely on. If the builder would write a test for it, it needs a row.
5. Keep ids stable. Never renumber across revisions; append new ids and mark withdrawn ones `WITHDRAWN`.
6. Add rows for quantitative claims (fees, slippage, borrow cost, look-ahead, survivorship, train/test split) even when they are NET-NEW, so the judge can match them to the guardrail table.

### 1-2. NET-NEW instead of a fake citation

When no reference implements a decision, label the row `NET-NEW` and state a reason. Never stretch a nearby citation to cover it. A fabricated citation passes a skim and fails the audit; an honest NET-NEW row passes the audit and moves the risk onto a named test.

A NET-NEW row needs three things:

| part | example from the Master FinHub build |
|---|---|
| The label | `NET-NEW` in the evidence column |
| A reason | "the reference reader is unbounded: `for line in proc.stdout:` at deepseek `client.py:323` has no cap" (A75) |
| A named test | `test_oversize_line_closes_session` |

The judge does not reject a NET-NEW row for lacking a citation. It checks that the reason is stated, that no reference contradicts it, and that the cited reason is true. In the build's round-2 verdict, rows A74-A77 were NET-NEW rows whose reasons each cited a reference line the judge opened and confirmed (for example A74: `sync_queue: ... = queue.Queue()` at crewai `streaming.py:213` is unbounded). Source: `_workspace/02_adversarial-risk-judge_verdict.md`.

In the final run report, 25 of the 78 rows were NET-NEW (counted by the QA agent in `_workspace/02_strategy-architect_slices.md`, source `_workspace/04_boundary-qa_report.md`).

### 1-3. Licence tiers per cited repo

Record the licence tier of every repo you cite, before citing it. The tier decides what the builder may do with the line. The Master FinHub build used a table in `.claude/skills/reference-mining/references/licence-rules.md`; the tiers collapse to three:

| tier | meaning | example in this build |
|---|---|---|
| copy (adapt) | Permissive licence. Rewrite the idea in the target language and keep a one-line attribution comment such as `# adapted from references/<repo>/<path>:<line> (MIT)`. | crewai (MIT), deepseek_harness (MIT), openhands (MIT), `autogpt/classic/` (MIT), revfactory_harness (Apache-2.0) |
| pattern-only | Restrictive or modified licence. Take the design idea only; the resulting code must not mirror the source's structure, names or comments. | dify (Apache-2.0 modified: no multi-tenant SaaS without written authorisation) |
| never | The licence forbids reuse. Any row sourced here is rejected on licence grounds, however useful the code. | `autogpt/autogpt_platform/` (Polyform Shield 1.0) |

Hard stops the judge enforces mechanically: a citation under a "never" path is REJECTED; a dify file is never `adapt`; a submodule with no licence file is treated as reference-only until the owner confirms. The licence file at the repo root is the source of truth; when a restated table drifts from it, the root file wins and the drift is reported as a gap.

---

## 2. Fresh-context adversarial audit

The judge is a separate agent that shares nothing with the architect except the design file and the cited lines. This is adversarial verification: a scripted audit of the list catches mis-citations that a persona reviewer, reading the same reasoning as the author, would wave through.

### 2-1. Isolation rules

- The judge reads only the design file (the Authority List, plus slice text where a claim needs its context) and opens every cited line itself, at ±5 lines, wider when a claim names a whole function.
- The judge ignores rationale prose and chat messages that argue a position.
- The judge never edits the architect's file. Its only artefact is the verdict.
- The judge changes a verdict only for new evidence, meaning a line it can open. A louder argument is not evidence.
- The judge defaults to doubt: a citation off by more than a few lines, in a different function, or needing inference to support the claim is not UPHELD.

### 2-2. Verdict schema

The verdict file starts with a totals line so the orchestrator can gate on it without parsing tables. Format from `.claude/skills/adversarial-audit/references/verdict-schema.md`:

```markdown
TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 1 — round 2/3

## Claims
| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A4 | REJECTED | references/dify/api/core/app/apps/streaming_utils.py:30 | import block | PING emission is at :61 in the same file |
| A7 | UNVERIFIED | references/crewai/src/crewai/llm.py:210 | function spans 200 lines | ambiguous without reading beyond ±5 |
| A9 | UPHELD | NET-NEW: spec requirement | none | reason stated; no contradicting reference |
```

| verdict | when | may the builder implement it? |
|---|---|---|
| UPHELD | The cited lines plainly do what the claim says | Yes |
| REJECTED | Wrong line or function, citation outside `references/`, licence-blocked, or a failed guardrail row | No |
| UNVERIFIED | File missing, submodule not checked out, or ambiguous | Only behind a test that fails if the assumption is wrong |

UNVERIFIED is honest, not lenient. It still constrains the builder. Giving the architect the correct location with each REJECTED row shortens the loop.

### 2-3. Fixed guardrail rows that cannot be skipped

Alongside the claims table, the verdict carries a guardrail table with one row per slice and one column per guardrail. The columns are fixed so a design cannot quietly skip one. Cell values are `PASS <how>`, `REJECTED <why>` or `N/A <why>`; a REJECTED guardrail counts toward the REJECTED total.

The six quantitative rows from `.claude/skills/adversarial-audit/references/quant-guardrails.md` are the worked example. They apply to any slice that computes returns, P&L, scores, benchmarks or data splits:

| # | guardrail | PASS requires the design to state | REJECTED when |
|---|---|---|---|
| G1 | Transaction fees | Fee model per trade (bps or fixed), applied on entry and exit, configurable, default > 0 | Returns computed gross; fee defaults to 0; fee applied on one side only |
| G2 | Borrow costs | Short positions accrue borrow (annualised rate × days held); financing on leverage | Shorts are free; leverage without financing cost |
| G3 | Slippage | Fill price differs from signal price (fixed bps, spread-based, or volume-based) | Fills at the same bar's close that generated the signal; zero slippage default |
| G4 | Look-ahead / future-index leakage | Signals use data up to `t-1` (or `t` close with fill at `t+1`); trailing windows only; no `shift(-k)` on features | Any feature uses data timestamped after the decision time; centred rolling windows; `.iloc[i+1]` in feature code |
| G5 | Survivorship bias | Universe is point-in-time (includes delisted names) or the limitation is stated in the output | Uses today's constituent list for historical periods without disclosure |
| G6 | Train/test leakage | Time-ordered split (walk-forward or fixed cutoff); scaler fit on train only; no shuffle across time | Random shuffle split on time series; normaliser fit on the full dataset; hyper-parameters tuned on test |

How to apply them:

- Rows are per slice. A slice with no numeric finance logic gets all six as `N/A <reason>`, for example "slice 3 safety: no prices or splits". The reason is required; a bare N/A is a skipped row.
- NET-NEW is acceptable for these rows, because most references do not implement them. The design must still describe the mechanism.
- Defaults count. A configurable fee that defaults to 0 is REJECTED, because the default is what actually runs.
- A PASS needs a test that fails when the guardrail is removed, such as a synthetic series on which a look-ahead feature would score perfectly.
- A rule that is `N/A` today needs a forward rule. In the build, slice 11 had every guardrail `N/A genuine` (string-match verifiers, no prices, nothing fitted), and the judge added a forward rule: an unknown verifier `eval.type` is rejected at load, so a future returns or backtest verifier needs code plus a new slice that states G1-G6 PASS mechanisms.

Domains other than trading need their own fixed rows. The pattern is the table, not the six topics: list the ways a result in your domain can be confidently wrong, and make each one a row the judge must rule on every time.

### 2-4. Round limit and escalation

- Loop between architect and judge until REJECTED = 0.
- Stop after 3 rounds. If REJECTED is still above zero, the judge writes the verdict and the orchestrator escalates to the human owner, with both positions side by side:

```markdown
## Escalation
| id | judge position | architect position |
|---|---|---|
| A4 | cited line is imports | "file-level citation should suffice" |
```

- On re-runs, carry UPHELD rows forward unchanged and re-audit only changed claims and prior UNVERIFIED rows. Churn on settled rows wastes rounds. Spot-check a sample of carried rows anyway: in round 2 the judge re-opened 29 carried lines and all still matched.

### 2-5. What each round found in the Master FinHub build

Source: `_workspace/02_adversarial-risk-judge_verdict.md` (round 2 file, which also holds the round-1 history), read 2026-10-02.

| round | totals | what it found |
|---|---|---|
| 1 | UPHELD 71 / REJECTED 3 / UNVERIFIED 0 (74 rows: A1-A72 plus F1 and F2) | A3: the cited line `:94` separates agents, not runs. F1: the MCP line cap, page cap and `-32601` reply had no row, and the reader was unbounded. F2: the bounded queue had no row, and an abandoned full queue leaked blocked readers. |
| 2 | UPHELD 78 / REJECTED 0 / UNVERIFIED 0 (78 of 78) | All three rejections confirmed fixed. F1 and F2 were turned into NET-NEW rows A74-A77 with named tests. Three non-blocking defects (N7 hang in `finally` ordering, N8 characters versus bytes, N9 reader thread now writes) were found and applied by the builders. |

Two things worth copying. First, round 1 caught defects that were not mis-citations at all: F1 and F2 were designs that relied on behaviour with no row, which is the gate working as intended, because "no row" means "no named test". Second, round 2 did not trust the architect's "changes in revision 2" summary; the judge re-audited changed rows independently and probed behaviour directly (a `readline(limit)` bound, a close-while-read hang) instead of reading only.

---

## 3. Boundary QA after every slice

Run QA after each slice, not once at the end. Defects found late are expensive and early contract mismatches spread to later slices (see `qa-agent-guide.md`, section 3-4). The build ran QA after every one of slices 8, 9, 10 and 11.

### 3-1. The verdict line

The first line of every QA report is exactly `RESULT: PASS` or `RESULT: FAIL`, so the orchestrator reads it without parsing. PASS requires all of: every boundary matches, all gate commands exit 0, the proof command produces the expected output, and the compliance sweep is clean. A command that cannot run is a FAIL with the missing tool named; QA never marks PASS by skipping.

### 3-2. Shape comparison across boundaries

Most integration bugs live between two files that each look correct alone: the tool declares `path` and the loop sends `file`; the CLI prints `result` and the test asserts on `output`. Open both sides of each boundary together and record both shapes in a table:

| boundary | side A | side B | match |
|---|---|---|---|
| tool schema ↔ loop call site | `docker_engine.py:144-156` `ToolSpec(... "required": ["command"])` | `runtime/loop.py:37-41` `ToolSpec(name, description, parameters, idempotent)` | yes |
| tool arg key ↔ loop guard | `docker_engine.py:162` reads `arguments["command"]` | `tools/safety.py:30` `COMMAND_ARG_KEYS` contains `command` | yes |
| CLI output ↔ test | CLI printed output | test's stdout assertion, including trailing newline and exit code | yes |

The standard set is tool schema ↔ call site ↔ test ↔ CLI, plus the design's declared interfaces ↔ the code, plus the error shape. Judge against the interfaces the design declared, not against what the code happens to do. A mismatch is a defect recorded with `file:line`, expected versus actual.

### 3-3. Re-run the gates yourself

QA never trusts the builder's report. It runs each gate command separately from the repo root and records exit code and verbatim output (up to 60 lines on failure). The four gates in this build were `pytest -q`, `ruff check src tests`, `black --check src tests` and `mypy --strict src`, plus the slice's proof command. Slice 11's record shows the shape:

| command | exit | output |
|---|---|---|
| pytest -q | 0 | `624 passed, 9 skipped in 41.68s` |
| mypy --strict src | 0 | `Success: no issues found in 40 source files` |
| proof: must-fail fixture | 1 | `pass_rate: 0.0`, `error: null`, failing expectation with evidence `"41"` |

Also record what is skipped. The slice 8 record names the one skip that belongs to the slice (`tests/test_docker_engine.py:134`, "docker daemon or image not available") and accounts for the other eight by cause.

### 3-4. Mutation spot-checks on a scratch copy

A green gate only proves the tests pass. It does not prove the tests can fail. For every safety-critical behaviour, QA deliberately breaks the code and confirms a test notices.

Procedure:

1. Copy the package into a scratch directory. Never edit the repo under review, and never delete anything there.
2. Confirm the import path actually loads the copy. In the slice 9 record, a first attempt hit a comment line and was a silent no-op (`22 passed`); only redoing it against the real call produced a kill. Run the unmutated baseline in the copy first, and confirm each mutation changes behaviour before trusting a "killed" result.
3. Apply one mutation at a time (drop a check, invert a condition, remove a cleanup) and run the relevant tests.
4. A mutant is KILLED if a named test fails. It SURVIVED if the suite stays green.
5. Compare the repo file to the original afterwards (`cmp`) to prove the repo was untouched.

Real mutants that survived on the first pass of this build. Each was a green gate with a weak test; the builder fixed the tests and QA re-ran the mutants until all were killed (source: first-pass defects as restated in `_workspace/03_boundary-qa_slice8.md`, `..._slice9.md`, `..._slice11.md` and `_workspace/04_boundary-qa_report.md`):

| slice | surviving mutant(s) | what was untested |
|---|---|---|
| 8 | M2: drop `stop.set()` in `finally`. M3: drop the reader join loop. M4: close both pipes before join. | Test strength: nothing proved an abandoned stream releases its reader threads or pipes, or that teardown cannot hang. Killed afterwards by `test_abandoned_stream_releases_readers` and `test_abandoned_stream_with_escaped_child_does_not_hang`. |
| 9 | M7a: replace every `terminate()`/`kill()` in `close()` with `pass`. M7b: drop the `finally` kill. | The kill path was never reached: the stub server exited on stdin EOF, so no test forced `close()` past EOF. Fixed by adding `--ignore-eof` and `--ignore-term` stub modes, so the terminate and kill branches are provably reached. The same pass found environment scrubbing unasserted (M9 killed afterwards). |
| 11 | D1: empty phrase accepted. D2: non-string `eval.type` crashed with `TypeError`. S1: empty ground could pass. S2: workspace cleanup only on success. | D1 and D2 were loader defects, and S1 and S2 were test gaps. After the retry all four were killed by `test_empty_phrase_rejected`, `test_non_string_eval_type_is_valueerror`, `test_empty_ground_cannot_pass` and `test_workspace_cleaned_after_crash`. |

**The rule: a surviving mutant is a FAIL even when the gate is green.** A green gate with a survivor means the test suite cannot detect that class of defect. The builder gets the mutant list as its defect list, and QA re-runs the same mutants after the fix.

One exception, and it must be argued: a mutant may stand when QA proves it is *equivalent*, meaning no observable behaviour changes. Slice 11 recorded two survivors this way, with the reason beside each: "timeout passes (`ok = True`)" survived because the next line still requires `grading is not None` and a timed-out case has grading `None`; "score kept on timeout" survived because the score is 0.0 either way. Write the equivalence argument in the report; without it the survivor is a FAIL.

Honest note on this build: in the fix round (`_workspace/03_boundary-qa_fixround.md`), one non-equivalent mutant survived (removing the `rest.startswith(":")` bracket-suffix check, so `[::1]x80` would be accepted by the mutant). QA recorded it as an advisory test gap, not exploitable because the result is still a loopback name, and the report's RESULT was PASS. That departs from the rule above. A harness author applying the rule strictly should treat that survivor as a FAIL and send the one-line test fix back to the builder.

### 3-5. Flakiness runs and stray processes

- Re-run timing-sensitive and concurrency tests 10 times, for example `pytest -k abandoned` x10 and the whole MCP test file x10. Record the pass count. A single green run is not evidence for a threaded or timing-dependent test.
- Where output should be deterministic, hash it across runs: slice 11's suite output, with `duration_s` lines removed, gave 1 distinct md5 over 10 runs.
- After every run, check for strays with `ps`/`pgrep`: leftover pytest processes, sleeping grandchildren, stub servers, scratch directories (`/tmp/mf_eval_*` was counted before and after). Mutant runs that remove kill logic deliberately leak processes; kill those and say so.

### 3-6. One retry, then stop and record the gap

When QA returns FAIL:

1. The orchestrator sends the builder QA's defect list for one retry (`master-finhub-orchestrator/SKILL.md`: "One retry with QA's defect list; still red → stop slices, report in Phase 4").
2. QA re-checks every previously listed defect plus a full gate run, and overwrites the slice report.
3. If the second run is still FAIL, stop building later slices. Record the failed slice, the verbatim failing output and the open question in the final report's Gaps section. Do not mark it PASS and do not start the next slice on top of it.

In this build slices 8, 9 and 11 failed once on test strength or loader defects and passed after the single retry; slice 10 passed first time. The first-pass FAIL reports were overwritten by the retry reports, so the first-pass detail above comes from the retry reports' notes.

---

## 4. Honest reporting

The final report is written for a reader who will not read the code and will act on it. Its job is to be true, not reassuring.

### 4-1. First line is the outcome

Start with exactly one of three words: **Done**, **Partly done** or **Blocked**, followed by one sentence naming what is and is not true. The build's final report opened:

> Outcome: PARTLY DONE. Slices 8, 9, 10 and 11 are built, merged and pass the gate. Slice 12 (factory) is deferred, and the docker execution path in slice 8 has never been run against a real daemon.

### 4-2. Never soften a gap

- State each gap as found, with the file and line, the verbatim error, and the severity. The build's Gaps section listed accepted risks with no mitigation (MCP tool names and schemas reach the model, a prompt-injection surface) in those words.
- Report deferred work as deferred, with the evidence: slice 12's files were 0 bytes, checked on the report date.
- Report contradictions between the brief and reality, for example a pull request the brief called open that GitHub reported as merged.
- Do not describe a failure as "mostly working". A failed gate stays failed until it passes.

### 4-3. List what was not verified

A passing report that hides an unexercised path is a false report. Add a "not verified" item for every path no test or run exercised, and say why. The build's example:

> The real docker path has never run against a daemon. `tests/test_docker_engine.py::test_echo_in_container` (line 134) is skipped with "docker daemon or image not available". Argv construction, hardening flags and denial are tested with mocks only.

The report then names the single action that closes it (`docker pull python:3.12-alpine`, then confirm the test passes rather than skips). Other examples in the same report: Python was 3.11.15 in the toolchain while the slice 8 text referenced a 3.12 image, so that image was not exercised; the QA agent counted the 25 NET-NEW rows but did not individually re-verify each row's named test.

### 4-4. Source and read date on every figure

Every number gets its source and the date it was read. Write "`624 passed, 9 skipped`, re-run 2026-10-02 at commit 967ec1b, `.venv/bin/python` = Python 3.11.15", not "all tests pass". When a figure came from a file another agent wrote, name the file. When it was not re-measured this session, say so. A figure with no source and no date cannot be checked and should not appear.

### 4-5. Structure that worked

| section | content |
|---|---|
| Outcome (first line) | Done / Partly done / Blocked, one sentence |
| Built | what each slice gives the reader, and its files |
| Passed | gate results per slice with exit codes and verbatim output, plus the skip list |
| Audit outcome | totals per round, what each round found |
| Gaps and accepted risks | every failure, deferral and unverified path, unsoftened |
| Next step | one action |

---

## 5. Checklist to paste into a QA agent definition

```markdown
## Quality gates (non-negotiable)

- [ ] Open the design's declared interfaces first. Judge the code against them, not against itself.
- [ ] Write `RESULT: PASS` or `RESULT: FAIL` as the first line of the report.
- [ ] For each boundary the slice touches, open side A and side B together and record both shapes
      (tool schema, call site, test fixture and assertion, CLI invocation and output, error shape).
- [ ] Re-run every gate command yourself, separately, from the repo root. Record exit code and
      verbatim output (up to 60 lines on failure). Never copy the builder's results.
- [ ] A command that cannot run is a FAIL with the missing tool named. Never PASS by skipping.
- [ ] List every skipped test with its reason. Account for each skip.
- [ ] Mutation-check every safety-critical behaviour on a scratch COPY. Confirm the copy is what
      gets imported, run an unmutated baseline first, and prove the repo is unchanged afterwards.
- [ ] A surviving non-equivalent mutant is a FAIL even when every gate is green. An equivalent
      mutant needs a written argument.
- [ ] Re-run timing and concurrency tests 10 times. Check for stray processes and scratch files.
- [ ] Sweep touched files for real client data, secrets and personal identifiers.
- [ ] Report; do not fix. Give each defect as file:line, expected versus actual.
- [ ] On a re-run, re-check every previously listed defect plus a full gate run.
- [ ] After one builder retry, if still FAIL: stop, and record the gap with verbatim output.
- [ ] Final report: first line Done / Partly done / Blocked; gaps unsoftened; a "not verified"
      list; source and read date on every figure; one next step.
```

---

## 6. What this reference could not verify

- The first-pass FAIL reports for slices 8, 9 and 11 were overwritten by their retry reports. The surviving-mutant and defect lists above are taken from the retry reports' statements about the previous run and from the final report, not from the original files.
- Slice 10's first-pass result is recorded as PASS in the final report. Its slice report was not used for the mutant list.
- The 25 NET-NEW count and the "named test exists for every NET-NEW row" claim are taken from the final report and the judge's verdict. They were not re-counted here.
- The licence tier names "copy / pattern-only / never" are a simplification. The build's own labels are `adapt`, `pattern`, `reference` and "do not port".
- Whether the mutation, flakiness and escalation procedures have been exercised end to end by a harness other than Master FinHub is not known. No round of the build reached escalation (round 3).
