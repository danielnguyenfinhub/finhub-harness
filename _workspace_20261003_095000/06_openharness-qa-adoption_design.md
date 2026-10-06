# OpenHarness QA adoption (OH23-OH27) — prose design

Revision 3 (round-2 fixes: N1, N3, N8; advisories N4 and quality-gates.md:165 folded in). Revision 2 (after round-1 verdict `_workspace/06_openharness-qa-adoption_verdict.md`). Changed: Q1, Q5, Q6, Q9, Q12, N1, N3, N4, N6, N7, N8, N10; added fourth target (orchestrator) and edits to `.claude/skills/boundary-qa/SKILL.md` and `quality-gates.md` §5. Unchanged: Q2-Q4, Q7, Q8, Q10, Q11, N2, N5, N9, N11.

Scope: prose targets only, no Python. Source: `references/openharness/src/openharness/coordinator/agent_definitions.py` (MIT, `references/openharness/LICENSE` line 1 "MIT License"). Port mode for every cited row: **adapt** (rewritten in FinHub words, one-line attribution, no pasted prose). Port-map rows: `references/portmaps/openharness-9b2efd7.md:73-77`.

The port map cites `:251` for OH23-OH25 and OH27 (start of `_VERIFICATION_SYSTEM_PROMPT`). Each adopted section was opened with `sed -n` and is cited at its own line below: VERIFICATION STRATEGY `:268`, RECOGNIZE YOUR OWN RATIONALIZATIONS `:294`, BEFORE ISSUING PASS `:312`, BEFORE ISSUING FAIL `:315`, OUTPUT FORMAT `:322`, `_VERIFICATION_CRITICAL_REMINDER` `:357`.

## Already in FinHub — not added again

| OpenHarness rule | where FinHub already has it | action |
|---|---|---|
| "The implementer's tests already pass" is not evidence (`:297`); test results are context (`:292`) | `.claude/agents/boundary-qa.md:12` "never trust the builder's report"; `quality-gates.md` §3-3 | not repeated; the new excuses bullet points back to it |
| Do not modify the project (`:255-259`) | `.claude/agents/boundary-qa.md:22` "Read-only on code"; `.claude/skills/boundary-qa/SKILL.md:79` | only the per-spawn reminder (OH26) is new |
| Run build, suite, linters, type-checker (`:283-288`) | the four gates, `boundary-qa.md:21`, `SKILL.md:14-20` | not repeated |
| PARTIAL for environment limits (`:351`) | FinHub rule is stricter: a command that cannot run is FAIL with the tool named (`boundary-qa.md:31`, `quality-gates.md` §3-1) | **not adopted** (NET-NEW-retained N2) |
| Verdict line last (`:343`) | FinHub puts `RESULT:` first (`boundary-qa.md:28`, `SKILL.md:23`, `quality-gates.md` §3-1); timeout form `RESULT: FAIL — incomplete` (`boundary-qa.md:32`) | **not adopted** (NET-NEW-retained N1) |
| Mutation testing | OpenHarness has none (port map line 120); FinHub has it in `quality-gates.md` §3-4 | kept; mapped as one valid kind of before-PASS probe (N5) |
| Flakiness x10, honest reporting | `quality-gates.md` §3-5, §4 | untouched |

---

## (a) Insertions and edits

### Target 1 — `.claude/agents/boundary-qa.md`

**Insertion 1.1** — after line 8, anchor:

> `You are the boundary QA for the Master FinHub harness.`

Insert (blank line before and after):

```markdown
> Standing reminder — re-read before writing every `RESULT:` line: you do not edit `src/`, `tests/` or any other repo file; scratch copies and throwaway scripts live only in the scratchpad or a temp directory and are deleted afterwards; a slice report's first line starts with `RESULT: PASS` or `RESULT: FAIL` (on timeout, `RESULT: FAIL — incomplete`); the Phase 4 final report follows `skills/finhub-harness/references/quality-gates.md` §4-1 instead.
> (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:357 (MIT))
```

**Insertion 1.2** — after line 23, anchor:

> `- Check compliance surfaces too: no client data, secrets or real Mercury records in \`tests/\` fixtures or \`src/\`.`

Insert four bullets:

```markdown
- Your job is to break the slice, not to confirm it. Watch for two habits in yourself: closing a check by reading the code and describing what you would run instead of running it, and passing a slice because the gate is green and the happy path works while its edges were never tried. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:251-253 (MIT))
- If you notice yourself thinking "the code reads correctly", "it is probably fine" or "this would take too long", the next thing you write is a `## Gate` row with a command and its output, not a sentence. A judgement about code you only read does not go in the report as a result. (The builder's own green tests are already covered by Core Role 2.) (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:294 (MIT))
- Before writing `RESULT: PASS`, record at least one adversarial probe and what happened, even when the code handled it. A mutation spot-check on a scratch copy (`skills/finhub-harness/references/quality-gates.md` §3-4) counts; so does driving a boundary input (empty, oversize, unknown id, the same call twice) through the slice's proof command. A report whose every row is "exit 0" has tested only the happy path and is not a PASS. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:312 (MIT))
- Before writing `RESULT: FAIL` for a finding outside the PASS conditions, check it is real: is it already guarded elsewhere on the same call path (open that line); is it declared deliberate in `02_strategy-architect_slices.md` or a judge-audited revision of it (a deviation listed only in the builder's report does not count and is itself recorded as a defect for the orchestrator to accept or reject); or is it unfixable without breaking an external contract the design names. A finding set aside by any of these checks is still listed under `## Defects` as `observation:` with the line you opened as evidence. None of these checks waives any PASS condition in `skills/finhub-harness/references/quality-gates.md` §3-1: a failed or skipped gate or proof command, a skipped probe, a probe whose observed behaviour differs from the design (an error-path probe that exits non-zero as designed is not a failure), a proof command with the wrong output, any boundary mismatch (including B3, B4 and B6 in the checklist), a compliance-sweep hit, or a surviving non-equivalent mutant. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:315 (MIT))
```

**Edit 1.3a** — line 28, in the Format bullet, replace the phrase

> `` `## Gate` (command | exit code | output on failure) ``

with

> `` `## Gate` (command | exit code | output observed) ``

**Insertion 1.3b** — after line 28, anchor (the Format bullet, as it reads after edit 1.3a):

> `- Format: slice report — first line \`RESULT: PASS\` or \`RESULT: FAIL\`, then \`## Boundary table\` (boundary | side A shape | side B shape | match), \`## Gate\` (command | exit code | output observed), \`## Defects\` (file:line, expected vs actual). Final report — \`## Built\` (slices with files), \`## Passed\` (gate results per slice), \`## Gaps\` (failed/deferred slices, UNVERIFIED claims still in code, open questions for Daniel), \`## Next step\` (one action).`

Insert:

```markdown
- Every check is one row of `## Gate`: the exact command, its exit code, and the literal output it printed rather than a summary of it (on success at least the final summary line, e.g. `624 passed, 9 skipped`; on failure up to 60 lines). Probes and mutants get rows too (`probe: <what>`, `mutant: <id> <change>`). A row with no command is a skip, not a pass, and a skipped gate, proof or probe row makes the result FAIL. `RESULT:` stays the first line; FinHub does not use a last-line verdict or a PARTIAL result. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:322 (MIT))
```

Apart from edit 1.3a, lines 10-37 (Core Role, existing principles, Error Handling including the line-32 timeout rule, Collaboration) stay byte-for-byte.

### Target 1b — `.claude/skills/boundary-qa/SKILL.md` (coherence edits, N6)

**Edit 1b.1** — line 23, replace

> `` First line `RESULT: PASS` only if every boundary matches, all four commands exit 0, the proof command produces the expected output, and the sweep is clean. ``

with

> `` First line `RESULT: PASS` only if every boundary matches, all four commands exit 0, the proof command produces the expected output, at least one adversarial probe is recorded as a `probe:` or `mutant:` row with its output, and the sweep is clean. ``

**Edit 1b.2** — line 39, replace the header

> `| command | exit | output (on failure, ≤60 lines) |`

with

> `| command | exit | output observed (summary line on success; ≤60 lines on failure) |`

**Edit 1b.3** — lines 42-44, replace the three empty-output rows with

```markdown
| ruff check src tests | 0 | `All checks passed!` |
| black --check src tests | 0 | `3 files would be left unchanged.` |
| mypy --strict src | 0 | `Success: no issues found in 3 source files` |
```

**Insertion 1b.4** — after line 45, anchor:

> `| proof: python -m master_finhub.cli "echo hi" | 1 | \`KeyError: 'text'\` |`

Insert:

```markdown
| probe: python -m master_finhub.cli (no argument) | 2 | `error: the following arguments are required: ...` |
```

(Example values are illustrative, matching the template's existing fictional slice-1 failure.)

### Target 2 — `skills/finhub-harness/references/qa-agent-guide.md`

**Insertion 2.1** — Table of Contents, after line 15, anchor:

> `6. [QA agent definition template](#6-qa-agent-definition-template)`

Insert:

```markdown
7. [Verifier stance, evidence and strategy by change type](#7-verifier-stance-evidence-and-strategy-by-change-type)
```

**Insertion 2.2** — end of file, after line 212, anchor (last row of "Real cases"):

> `| A 404 occurs when opening the detail page after completion | File path → \`href\` | The route prefixes do not match. |`

Insert:

````markdown

---

## 7. Verifier stance, evidence and strategy by change type

> Adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:251 (MIT), sections cited at their own lines below. Rewritten for FinHub; the verdict rules in 7-2 deliberately differ from the source.

### 7-1. Stance

A QA agent exists to break the work, not to approve it. It fails in two predictable ways: it reads the code and writes up what it would have run instead of running it, and it passes work whose first, visible part is good (green suite, page renders) without trying the edges. Assume the orchestrator may re-run any command in your report; a passing row with no output, or output that a re-run does not reproduce, discredits the whole report. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:251-253 (MIT))

### 7-2. Evidence per check

Each check is recorded as a command plus what it printed, never as a description of code:

```markdown
| check | command | exit | output observed |
|---|---|---|---|
| CLI rejects empty input | `python -m app.cli ""` | 2 | `error: input must not be empty` |
```

A check with no command is a skip. A skipped required check makes the report FAIL. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:322 (MIT))

FinHub differences from the source, kept on purpose: the verdict is the **first** line (`RESULT: PASS` or `RESULT: FAIL`, see `quality-gates.md` §3-1), and there is no PARTIAL — a check that cannot run because a tool or service is missing is a FAIL that names what is missing.

### 7-3. Before PASS

Record at least one adversarial probe and its outcome, even if the code handled it: a boundary value, an unknown id, the same mutating call twice, two concurrent calls, or a mutation spot-check on a scratch copy (`quality-gates.md` §3-4). If every row says "exit 0" or "suite passes", only the happy path has been seen. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:312 (MIT))

### 7-4. Excuses to catch yourself making

| the thought | what goes in the report instead |
|---|---|
| "The code looks right" | A gate row: the command that exercises that code path, its exit code and its output. |
| "The builder's tests pass" | Your own `pytest -q` row, then at least one `probe:` row the builder's tests do not cover. |
| "Probably fine" | A `probe:` row aimed at the case you were unsure about. |
| "No browser / no server available" | A row showing how you looked (`which <tool>`, the session's tool list). If it is truly absent: FAIL, naming it. |
| "Too slow to check" | Start it with a time limit; if it does not finish, FAIL with the limit and the command named. |

(adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:294 (MIT))

### 7-5. Before FAIL

These checks apply only to findings outside the PASS conditions in `quality-gates.md` §3-1. For such a finding, confirm it is real before reporting FAIL:

- **Guarded elsewhere?** Open the upstream validation or downstream recovery line that would stop it.
- **Declared deliberate?** Only the design document, or a revision of it the judge has audited, counts. A deviation the builder lists in its own report does not; record that deviation as a defect for the orchestrator to accept or reject. A code comment saying "intentional" does not count either.
- **Unfixable without breaking an external contract** the design names?

A finding set aside by any of these is still listed in the report as `observation:` with the line you opened as evidence, so it cannot disappear. None of these checks waives any PASS condition in `quality-gates.md` §3-1: a failed or skipped gate or proof command, a skipped probe, a probe whose observed behaviour differs from the design (an error-path probe that exits non-zero as designed is not a failure), a proof command with the wrong output, any boundary mismatch, a compliance-sweep hit, or a surviving non-equivalent mutant. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:315 (MIT))

### 7-6. Standing reminder

Give the QA agent a two-line reminder covering three things: read-only on the project, scratch work only in a temp directory, and the verdict format. Put it at the top of the agent file, and have the orchestrator include the same text in every QA spawn prompt so it is re-sent each time QA is started. The source declares such a reminder as a per-agent field documented as re-injected every user turn and passes it through to the host's agent field; the pinned source contains no injector of its own, and a prompt-only harness can re-send it per spawn, not per turn. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:127 and :79 (MIT))

### 7-7. Strategy by change type

Pick the row for what changed. Scale the checking to what a defect would cost: a throwaway script needs a smoke run; anything that moves money or writes a system of record gets every probe. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:268 and :290 (MIT))

| change type | exercise it | try to break it |
|---|---|---|
| CLI or script | Run with typical arguments; check stdout, stderr and exit code; check `--help` matches behaviour | Empty, malformed and boundary arguments |
| API or server | Start it; call each changed endpoint; compare body fields with the declared contract, not only the status code | Error paths, unknown ids, the same mutating call twice |
| Library | Build, full suite, then import from a fresh interpreter and call the public API as a consumer would | Exported names versus the documented ones |
| Bug fix | Reproduce the bug first, then confirm the fix and run regressions | Neighbouring behaviour for side effects |
| Refactor | Existing suite passes unchanged; public surface diff is empty | Same inputs give same outputs on a sample |
| Data pipeline | Run a sample; check schema and types | Empty input, one row, nulls; row count in versus out |
| Migration | Up, check schema, down | Run against populated data, not an empty database |
| Infrastructure or config | Validate syntax; dry-run | Every defined env var or secret is actually read |
| Frontend | Use the browser tools you have; fetch a sample of referenced assets (a page can return 200 while its assets fail) | Console errors, broken links (section 2-2) |
| **Lending, serviceability or duty calculation** (FinHub) | Recompute the expected figure by hand for a synthetic applicant from the rule the design cites | The design's threshold T and one smallest step either side (T − ε, T + ε) in the threshold's own unit, rounding direction, units (monthly vs annual, % vs bps, gross vs net income). Any mismatch is FAIL unless the design states a tolerance |
| **CRM or system-of-record write** (FinHub) | Run against a stub or sandbox only, with synthetic fixtures; read the record back after writing | The same write twice (no duplicate), a write to an unknown id (explicit error), no real client data in fixtures |
| **Returns, backtest or eval scoring** (FinHub) | Apply guardrails G1-G6 in `quality-gates.md` §2-3 | A synthetic series on which a look-ahead feature would score perfectly must not |
| Anything else | Find a way to run it directly, compare with the expectation | Inputs the builder did not test |

Mobile rows from the source are not carried; no FinHub harness ships a mobile app.
````

### Target 3 — `skills/finhub-harness/references/quality-gates.md`

**Edit 3.0** — line 165, replace `is exactly \`RESULT: PASS\` or \`RESULT: FAIL\`` with `starts with \`RESULT: PASS\` or \`RESULT: FAIL\``, so it agrees with the timeout form `RESULT: FAIL — incomplete` at `boundary-qa.md:32` (observation from round 2; no new claim id, covered by N1).

**Insertion 3.1** — appended as a new sentence at the end of line 165 (same paragraph, §3-1; anchor quoted as it reads before edit 3.0):

> `The first line of every QA report is exactly \`RESULT: PASS\` or \`RESULT: FAIL\`, so the orchestrator reads it without parsing. PASS requires all of: every boundary matches, all gate commands exit 0, the proof command produces the expected output, and the compliance sweep is clean. A command that cannot run is a FAIL with the missing tool named; QA never marks PASS by skipping.`

Append:

```markdown
 Every check behind that line is a command with its observed output, and PASS also needs at least one recorded adversarial probe (`qa-agent-guide.md` section 7).
```

**Insertion 3.2** — §5 checklist, after line 293, anchor:

> `      mutant needs a written argument.`

Insert:

```markdown
- [ ] Before PASS, record at least one adversarial probe (`probe:` or `mutant:` row) with its output.
      Every gate row carries its observed output, the summary line on success included.
```

### Target 4 — `.claude/skills/master-finhub-orchestrator/SKILL.md` (per-spawn reminder, N7)

**Edit 4.1** — Phase 3 QA spawn prompt, line 96. Anchor (lines 95-96):

> `  prompt: "You are boundary-qa. Read .claude/agents/boundary-qa.md first.`
> `    Verify slice N; write _workspace/03_boundary-qa_slice{N}.md."`

Replace line 96 with:

```
    Verify slice N; write _workspace/03_boundary-qa_slice{N}.md.
    Standing reminder: do not edit src/, tests/ or any repo file; scratch work only in a temp
    directory, deleted afterwards; the report's first line starts with RESULT: PASS or RESULT: FAIL."
```

**Edit 4.2** — Phase 4 QA spawn prompt, line 114. Anchor (lines 112-114):

> `  prompt: "You are boundary-qa. Read .claude/agents/boundary-qa.md first.`
> `    Write _workspace/04_boundary-qa_report.md from all _workspace/02_* and 03_* files,`
> `    re-running pytest -q, ruff check src tests, black --check src tests, mypy --strict src."`

Replace line 114 with:

```
    re-running pytest -q, ruff check src tests, black --check src tests, mypy --strict src.
    Standing reminder: do not edit src/, tests/ or any repo file; scratch work only in a temp
    directory, deleted afterwards."
```

(The final report's first line is governed by `quality-gates.md` §4-1, so the Phase 4 reminder omits the `RESULT:` clause.) The builder spawn prompt and all other orchestrator lines are unchanged. Per the orchestrator's change-log rule, the implementer adds a row to the `CLAUDE.md` 변경 이력 table for this edit.

---

## (b) Authority List

All cited paths: `references/openharness/src/openharness/coordinator/agent_definitions.py` (abbreviated `AD`), licence MIT, port-as **adapt**.

| id | claim | evidence | licence | port-as | target |
|---|---|---|---|---|---|
| Q1 | The verifier's job is to try to break the work, not confirm it | AD:251-253 | MIT | adapt | 1.2, 2.2 §7-1 |
| Q2 | Two named failure modes: verification avoidance (reading and narrating instead of running) and being seduced by the first 80% | AD:253 | MIT | adapt | 1.2, 2.2 §7-1 |
| Q3 | The caller may re-run commands; a PASS step without command output, or with output that re-execution does not reproduce, is rejected | AD:253 | MIT | adapt | 2.2 §7-1 |
| Q4 | Strategy is chosen by change type (frontend, API, CLI, infra, library, bug fix, data pipeline, migration, refactor, other) | AD:268; rows AD:271-281 | MIT | adapt | 2.2 §7-7 |
| Q5 | The depth of checking scales with what a defect would cost (one-off script vs payments code); reworded, no source phrase reused | AD:290 | MIT | adapt | 2.2 §7-7 |
| Q6 | Named rationalisations ("reading is not verification", "implementer's tests pass", "probably fine", "no browser", "too long") are cues to act; FinHub's response is a `## Gate` row, written in FinHub terms (§7-4 right column, 1.2 bullet 2) | AD:294; items AD:296-301 | MIT | adapt | 1.2, 2.2 §7-4 |
| Q7 | Before PASS the report includes at least one adversarial probe and its result; only "200"/"suite passes" means happy path only | AD:312; text AD:313 | MIT | adapt | 1.2, 2.2 §7-3, 3.1 |
| Q8 | Before FAIL, check already handled / intentional / not actionable; not-actionable is an observation, not a FAIL | AD:315; items AD:317-319 | MIT | adapt | 1.2, 2.2 §7-5 |
| Q9 | Every check has a command-run block with observed output; a check without a command is a skip, not a PASS (1.3b wording: "the literal output it printed rather than a summary of it") | AD:322; text AD:323 | MIT | adapt | 1.3b, 2.2 §7-2, 3.1 |
| Q10 | Reading code is not verification (rejected example) | AD:341 | MIT | adapt | 2.2 §7-2 |
| Q11 | A short reminder states read-only on the project, temp files allowed, and the verdict format | AD:357; text AD:358-360 | MIT | adapt | 1.1, 2.2 §7-6, 4.1, 4.2 |
| Q12 | The source declares a per-agent reminder field documented as "re-injected at every user turn" and maps it to the host field `criticalSystemReminder_EXPERIMENTAL`; the pinned repo itself contains no injector (no claim that its runtime re-sends it) | AD:127; AD:79 | MIT | adapt | 2.2 §7-6 |
| N1 | A slice report's first line starts with `RESULT: PASS` or `RESULT: FAIL` (on timeout, `RESULT: FAIL — incomplete`, `boundary-qa.md:32`); the Phase 4 final report follows `quality-gates.md` §4-1 (Done / Partly done / Blocked) instead | NET-NEW-retained — source puts the verdict last (AD:343); FinHub's orchestrator reads line 1 (`boundary-qa.md:28`, `quality-gates.md` §3-1). Verify: `grep -c 'first line starts with' .claude/agents/boundary-qa.md` = 1 and `grep -c 'and nothing else' .claude/agents/boundary-qa.md` = 0; `grep -c 'Phase 4 final report follows' .claude/agents/boundary-qa.md` = 1; cold test "write the slice 1 QA report `_workspace/03_boundary-qa_slice1.md`" → line 1 of that slice report must match `^RESULT: (PASS\|FAIL)( — incomplete)?$` (the regex is not applied to `04_boundary-qa_report.md`) | — | — | 1.1, 1.3b, 2.2 §7-2 |
| N2 | No PARTIAL; a missing tool or service is FAIL naming it | NET-NEW-retained — source allows PARTIAL for environment limits (AD:351); FinHub rule `boundary-qa.md:31`. Verify: `grep -c PARTIAL .claude/agents/boundary-qa.md` = 1 (the "does not use … PARTIAL" sentence only); cold test with ruff uninstalled → report must say FAIL and name ruff | — | — | 1.3b, 2.2 §7-2 |
| N3 | "Deliberate" counts only when `02_strategy-architect_slices.md` or a judge-audited revision of it says so; a deviation listed only by the builder is recorded as a defect for the orchestrator, never a reason not to FAIL; code comments and commit messages do not count | NET-NEW — tightens AD:318, which accepts CLAUDE.md/comments/commit messages; the builder is the party under test (`boundary-qa.md:12`, `SKILL.md:12`). Verify: `grep -c 'listed only in the builder' .claude/agents/boundary-qa.md` = 1 and `grep -c "builder report's deviation list" .claude/agents/boundary-qa.md` = 0 (the revision-1 wording; insertion 1.2 now says "a deviation listed only in the builder's report", which this grep does not match); cold tests: (a) defect with a `# intentional` comment and no design entry → FAIL; (b) defect listed only in the builder report's deviation list, absent from the design → FAIL, with the deviation under `## Defects` | — | — | 1.2, 2.2 §7-5 |
| N4 | Before-FAIL checks apply only outside the §3-1 PASS conditions and never waive any of them (failed or skipped gate/proof, skipped probe, probe behaviour differing from the design, wrong proof output, any boundary mismatch incl. B3/B4/B6, compliance-sweep hit, surviving non-equivalent mutant); every finding set aside is still listed as `observation:` with evidence | NET-NEW — keeps `quality-gates.md:165` PASS conditions and §3-4 / §4-2 / §4-3 intact against AD:317-319. Verify: `grep -c 'compliance-sweep hit' .claude/agents/boundary-qa.md` = 1 and `grep -c 'observation:' .claude/agents/boundary-qa.md` ≥ 1; cold tests: (a) compliance-sweep hit labelled "not actionable" → FAIL; (b) surviving mutant labelled "guarded elsewhere" → FAIL; (c) a finding dismissed as "guarded elsewhere" → appears under `## Defects` as `observation:` with a file:line | — | — | 1.2, 2.2 §7-5 |
| N5 | A mutation spot-check on a scratch copy satisfies the before-PASS probe | NET-NEW — source has no mutation testing (port map `openharness-9b2efd7.md:120`). Verify: grep `quality-gates.md\` §3-4` in boundary-qa.md insertion 1.2 | — | — | 1.2, 2.2 §7-3 |
| N6 | Probes and mutants are rows in the existing `## Gate` table; every row, success included, carries observed output; the same rule and the probe-before-PASS condition are written into `boundary-qa.md:28`, `SKILL.md:23`, `SKILL.md:39-45` and `quality-gates.md` §5 so no instruction says "output on failure" only | NET-NEW — the existing template showed empty success cells (`SKILL.md:42-44`); left unchanged it would contradict 1.3b. Verify: `grep -c 'output on failure\|on failure, ≤60' .claude/agents/boundary-qa.md .claude/skills/boundary-qa/SKILL.md` = 0 for both files; `grep -c 'probe' .claude/skills/boundary-qa/SKILL.md` ≥ 2; `grep -c 'adversarial probe' skills/finhub-harness/references/quality-gates.md` ≥ 2; on any QA report written after the edit, `grep -nE '^\| [^|]+ \| [0-9]+ \| *\|$' _workspace/03_boundary-qa_slice*.md` returns no Gate rows (an empty output cell) | — | — | 1.3a, 1.3b, 1b, 3.1, 3.2 |
| N7 | The reminder is re-sent per QA spawn (both boundary-qa spawn prompts in the orchestrator carry it) and sits at the top of the agent file; it is not re-sent per turn, because a prompt-only harness has no per-turn injection hook | NET-NEW — the orchestrator's spawn prompts (`master-finhub-orchestrator/SKILL.md:95-96`, `:112-114`) carry no reminder today; the source's per-turn re-send rests on a field comment only (Q12). Verify: `grep -c 'Standing reminder' .claude/skills/master-finhub-orchestrator/SKILL.md` = 2 (0 today); `grep -c 'Standing reminder' .claude/agents/boundary-qa.md` = 1 | — | — | 1.1, 2.2 §7-6, 4.1, 4.2 |
| N8 | Strategy row: lending, serviceability or duty calculation — hand-recomputed expected value from the design's cited rule; probes at the design's threshold T and one smallest step either side (T − ε, T + ε) in the threshold's own unit, rounding, units; zero tolerance unless declared | NET-NEW — no reference covers lending maths (port map row OH27 asks for FinHub equivalents); the row states no real threshold, rate or lender fact. Verify: `grep -c 'one smallest step either side' skills/finhub-harness/references/qa-agent-guide.md` = 1 and `grep -c '80.00%' …` = 0; cold test "QA a synthetic serviceability calculator: monthly income 10,000 units, monthly commitments 6,000 units, design threshold surplus ≥ 1,000 units" → the plan must include probes at 999.99, 1,000.00 and 1,000.01 (the threshold and one cent either side) and a units probe (monthly vs annual income) | — | — | 2.2 §7-7 |
| N9 | Strategy row: CRM/system-of-record write — stub or sandbox only, synthetic fixtures, read-back, duplicate-write and unknown-id probes | NET-NEW — FinHub compliance (no real Mercury records, `boundary-qa.md:23`). Verify: grep `CRM or system-of-record write`; cold test "QA a Mercury note writer" → must refuse a live record and run the duplicate-write probe | — | — | 2.2 §7-7 |
| N10 | Strategy row: returns/backtest/eval scoring routes to guardrails G1-G6 | NET-NEW — guardrails are FinHub's own (`quality-gates.md` §2-3). Verify: grep `G1-G6` in qa-agent-guide.md §7-7; cold test "QA a returns calculator whose fee defaults to 0" → must FAIL citing G1 | — | — | 2.2 §7-7 |
| N11 | Mobile rows from the source are dropped | NET-NEW — YAGNI; no FinHub harness ships mobile. Verify: `grep -ci 'simulator\|emulator' qa-agent-guide.md` = 0 | — | — | 2.2 §7-7 |

**Totals: 12 cited (Q1-Q12, all MIT/adapt) / 11 NET-NEW (N1-N11, of which N1-N2 retained FinHub rules).** No new ids were needed; the orchestrator edit is covered by N7 and the SKILL.md / §5 coherence edits by N6.

Licence check: every cited row is under `references/openharness/` (MIT, `LICENSE:1`); no dify, no `autogpt_platform`. The rows the judge flagged as too close to the source (Q6 right column and 1.2 bullet 2, Q5 lead sentence, Q9 "paraphrased") are rewritten; the left column of §7-4 quotes the excuse strings by design.

---

## (c) Risk note

1. The before-FAIL step (AD:315-319) could launder defects; N3 and N4 close that: only the audited design makes something deliberate, no §3-1 PASS condition can be waived, and every set-aside finding stays in the report as `observation:`.
2. PARTIAL (AD:351) and a last-line verdict (AD:343) would weaken the line-1 gate and the "cannot run = FAIL" rule, so neither is adopted (N1, N2); the timeout form `RESULT: FAIL — incomplete` is preserved.
3. OH26 is only partly delivered: the reminder is re-sent once per QA spawn (Target 4) and re-read by self-discipline before each verdict, not re-injected every turn, which this prompt-only harness cannot do; everything else only adds obligations, and no existing boundary-qa rule is removed (the only reworded existing text is the "output on failure" column, now "output observed", which is stricter).
