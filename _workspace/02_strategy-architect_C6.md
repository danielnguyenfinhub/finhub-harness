# Adoption design C6: delegation contract for generated orchestrators (revision 2)

## Revision 2

Fixes against the judge's round 1 verdict (`02_adversarial-risk-judge_C6_r1.md`; UPHELD 31, REJECTED 5). The first issue of this design was numbered revision 0; the coordinator asked for this one as revision 2. Each failure was reproduced first on the judge's patched copy; rows marked `CHANGED r2` in the Authority List; every other row is byte-identical.

- **A19 (stale check), fixed.** Measured on the patched `lazy-orchestrator/SKILL.md`: the lint reports 9 hits on 8 lines (7, 8, 9, 11, 12, 13, 14, 15); the Step 6 grep prints 5 lines (7, 8, 11, 13, 14) and misses 9 (wrapped), 12 (tab and no-break space) and 15 (tab and line break). "5 of 7" is corrected in Decisions item 1, P-3 and A19. Every named check in the Authority List was re-run against the current text (results in P-1, P-2, P-3).
- **A20 (scope gate), fixed by widening.** `SPAWN_RE` now also matches `SendMessage`, `agent(`, `Agent(` and `Task(`, with four new fixtures. Choice, cost and the shipped sentence: Decisions item 7. New rows A34, A35.
- **S1 (black red), fixed.** The long `head = '...'` lines are wrapped; black, ruff, mypy `--strict` and pytest outputs are quoted in P-2.
- **S2 (E5 false), fixed.** E5 now calls the grep a stricter manual fallback whose hits are judged by hand; "same test" and "prints nothing" are gone. The five grep hits the lint stays silent on are listed under Does not cover. New row A36.
- **S3 (mutation bar), fixed.** One new test kills the judge's J04, J14 and J19. Runner and counts in Test plan. New row A37.
- **Folded in (one sentence, no behaviour change except where noted):** (a) the Limits paragraph says the check never opens an evidence item, an invented path passes (1 of 3 live runs), the `SendMessage` and Workflow branches are untested, and a Mode A `schema` carrying STATUS is UNVERIFIED (nothing under `references/` settles it); (b) the paragraph states what the block does not pin (status case, repeated STATUS lines, literal `none`) and what the judge saw live; (c) one sentence in the block says the re-ask is the only retry for an invalid report (this one changes behaviour slightly, so the live tests were re-run: P-3); (d) the attribution sits on the self-contained-brief sentence and the text says "as discussed" is not from any reference; (e) `live/` now builds its own fixture (`build_fixture.sh`) and has a checker (`check_case.sh`) whose `always` rule also needs a final line. New rows A38, A39.
- **Follow-ups (not built):** see the section of that name before the Authority List.

Goal: capability-adoption. Scope: factory (plugin skill prose) plus one small rule in the existing lint. Item: C6. Pick recorded in `_workspace/00_input/request.md` § Pick 7. Effort S.

Byte-exact companion files (all under `_workspace/`): `02_strategy-architect_C6.patch` (unified diff of every touched file and the new fixtures; applies cleanly with `patch -p1` on the current tree, checked), and `02_strategy-architect_C6_support/` (apply script, proof greps, mutation runners, live-test recipe). The fixtures contain a tab and a no-break space, so the patch, not this page, is the byte-exact source for them.

## Decisions for Daniel

1. **Lint rule: yes, 13 added lines, WARN not ERROR.** The Step 6 grep from the backlog row misses a phrase wrapped over two lines and one with a tab or no-break space (measured on the seeded `lazy-orchestrator`: the lint reports 9 hits on 8 lines, 7, 8, 9, 11, 12, 13, 14, 15; the grep prints 5 of them, 7, 8, 11, 13, 14, and misses 9, 12 and 15; it also has no word boundaries and no gate, so it prints 5 lines the lint stays silent on). The lint already runs at Step 6.1 and in the packager, so the rule costs one regex. WARN because natural prose has false positives (a research-and-write skill legitimately says "write the summary based on the research"); Step 6 already says "fix each WARN or say why it stays".
2. **One re-ask, not three.** The backlog row says once; the CrewAI retry loop it adapts defaults to three. We keep one. Live runs: a worker that never complies was asked exactly once more in 3 of 3 runs.
3. **Status names are `complete | partial | blocked`.** The DeepSeek loop calls the middle one `continue` because it loops; a one-shot delegation has no next round, so `partial` says what it is.
4. **The Step 6.2 grep is written in regex form on purpose** (`based on (your|the) (findings|research)`). Spelled out as the plain phrase it would make the finhub-harness SKILL.md trip its own new lint rule.
5. **Live result worth knowing:** the re-ask works, but a model worker told "your evidence is empty" can invent evidence (1 of 3 live runs). Evidence present is not evidence true. See Does not cover.
6. **Housekeeping disclosure:** early in this task I ran `bash scripts/check-harness-refs.sh` in the real repo once to get a baseline. It calls `scripts/package-plugin.sh`, which rewrites `dist/*`. No source file changed; `dist/` was regenerated from the same sources. Everything else I ran in a scratch copy.
7. **Gate widened (A20).** First issue: the lint only looked at files naming `subagent_type` or `agentType`, but a Workflow `agent("...")`, `Task(...)`, `Agent(name:, prompt:)` or a `SendMessage` can carry a bad brief without either token (`workflow-recipes.md:200` says `agentType` may be omitted). Chosen: widen the gate to `\b(?:subagent_type|agentType|SendMessage)\b|\b(?:agent|Agent|Task)\(` and add fixtures, rather than shrink the claim, because the contract text says the brief rule covers every `SendMessage` and `agent()`. Cost: a file that merely mentions `SendMessage` or writes `Agent(`/`Task(` in prose and also contains a banned phrase now warns. Measured on this repo: `lint_harness.py .` stays 0 errors, 0 warnings, and `.claude` has 0 `lazy-delegation` lines (the repo has no hit at all, so no spawn mention can trip). Still not scanned: `references/*.md` and any file the lint does not read. The shipped Step 6.1 clause now names the tokens instead of saying "no file which spawns workers".

Licence note carried from the backlog (`:165`): every OpenHarness-primary row rests on the pinned fork's `LICENSE` ("MIT", `references/openharness/LICENSE:1`); the upstream org is unverified. Daniel accepted MIT in the Pick.

## Source

Backlog row C6 (`_workspace/01b_capability-scout_backlog.md:53`): self-contained brief in; status, evidence and blocker report out, validated once. Score 0.82. The row's own risk: this is prompt quality, not a verifiable guarantee.

Port-map rows re-opened at the pinned commits (every line below opened by me, not taken from the maps):

| row | re-opened line | what it says | used for |
|---|---|---|---|
| OH2 | `references/openharness/src/openharness/coordinator/coordinator_mode.py:405` | workers cannot see your conversation; every prompt must be self-contained | brief must be self-contained |
| OH2 | `:409` | understand findings, then write a prompt with specific paths and line numbers | Inputs line |
| OH2 | `:411` | never write the two "based on ..." phrases; they delegate understanding to the worker | banned phrases |
| OH2 | `:424` | add a purpose statement so the worker calibrates depth | Goal line |
| OH3 | `:384`, `:440` | a failed worker is continued, it has the error context | re-ask by `SendMessage` for a named worker |
| OH79 | `references/openharness/src/openharness/autopilot/service.py:2035-2038` | expected output is three items: what changed, what was verified, remaining risk | report content maps to SUMMARY, EVIDENCE, NEXT STEPS or BLOCKER |
| D53 | `references/deepseek_harness/packages/goal/goal-round-driver/src/prompt.ts:20-22` | gather evidence before claiming completion | `complete` needs EVIDENCE |
| D54 | `references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:91-103` | report schema: status, summary, evidence, nextSteps, blocker | report fields |
| D54 | `:112-142` | `validateReport`: continue needs nextSteps and no blocker; complete needs evidence, no nextSteps, no blocker; blocked needs a concrete blocker; anything else throws | the validity table |
| O32 | `references/openhands/src/api/launch-child-conversation-client-tool.ts:17` | the child cannot see the parent history | self-contained |
| O32 | `:34-35` | the brief holds goal, paths, constraints, expected deliverable and how to report back | five brief lines |
| O32 | `:36-38` | scopes independent of siblings; one call per task, never twice for the same task | Scope line; one-task rule |
| C28/C29 | `references/crewai/lib/crewai/src/crewai/project/crew_base.py:106`, `references/crewai/lib/crewai/src/crewai/task.py:153-155` | `expected_output` is a required task field | Expected output line |
| C37/C38 | `references/crewai/lib/crewai/src/crewai/utilities/guardrail.py:68-70`, `references/crewai/lib/crewai/src/crewai/task.py:1343`, `:1382`, `:1400` | a failed check carries an error message, is retried a bounded number of times with the error fed back, then fails | re-ask once with the broken row named |

Opened and **not adopted**, with the reason:

- **C34** (`crew.py:1531`, a manager has no tools): Template C already says the orchestrator does not repeat delegated work (`orchestrator-template.md:249`, quoted in A16). No new text.
- **C39** (`task.py:412`, one retry counter per guardrail): the contract has one check, so one counter. No new text.
- **OH1** (`coordinator_mode.py:292`, never fabricate agent results): Template A already says not to presume a result before its notification, and the error tables say the orchestrator reflects only facts it confirmed. No new text.
- **D54 handoff size cap** (`maxHandoffChars`, `index.ts:145`): out of scope for S; listed under Does not cover.

Licences: crewai, deepseek_harness, openhands, openharness are MIT (`references/LICENSES.md:9-14`). Nothing from `autogpt_platform/`. No dify.

## Target

| # | file | change |
|---|---|---|
| E1 | `skills/finhub-harness/references/orchestrator-template.md` | writing principles: new item 10 after line 297 |
| E2 | same | new section `## Delegation contract` before the `## Follow-up request phrasings` heading (line 299); holds the copy block |
| E3 | `skills/finhub-harness/SKILL.md` | Step 5 "Every orchestrator contains": new bullet after the Data hand-off bullet (line 115) |
| E4 | same | Step 6.1 (line 142): one clause added to the lint's check list, in place |
| E5 | same | Step 6.2 (line 143): one sentence appended, in place |
| E6 | same | Deliverable checklist: one item after line 181 |
| E7 | `skills/finhub-harness/references/surfaces.md` | section 6 table: row 8 after line 161 |
| E8 | `skills/finhub-harness/scripts/lint_harness.py` | two regexes and one 8-line loop |
| E9 | `tests/fixtures/harness_delegation/` (new, 6 files) | seeded fixtures; the existing `harness_good` and `harness_bad` are not touched |
| E10 | `tests/test_lint_harness.py` | one import line and five test functions appended; the four existing test functions are byte-identical |

Not touched: Templates A, B and C step text, `workflow-recipes.md`, `scripts/package-plugin.sh`, `scripts/check-harness-refs.sh`, `.claude/`, `CLAUDE.md` (the orchestrator adds the change-history row at Phase 4), `README.md`, `docs/`.

Size after the edit (simulated on a scratch copy): `SKILL.md` 198 to 200 lines (limit 500), `orchestrator-template.md` 308 to 353, `surfaces.md` 161 to 162, `lint_harness.py` 150 to 163.

## Design

### The contract, in one place

**1. What a brief must contain.** The `prompt` of every `Agent` call, `SendMessage` and Workflow `agent()` carries five lines, in this order: `Goal` (one sentence plus what the result is for), `Inputs` (exact paths, line numbers where the point is one place, and the facts the orchestrator already holds, stated, not referred to), `Scope` (what may be written or changed and what must not be touched; parallel workers get disjoint scopes), `Expected output` (file under `_workspace/` and the shape of its content), `Report` (end with the worker report below). One task per call; never send the same task twice (A1-A7).

**2. Banned lazy-delegation phrases and the rule for matching them.** A brief that points at an earlier result instead of stating it is the failure. The marks the lint knows are exactly the regex `\b(?:based\s+on\s+(?:your|the)\s+(?:findings|research)|as\s+(?:we\s+)?discussed)\b`, case-insensitive: "based on your findings", "based on the findings", "based on your research", "based on the research", "as discussed", "as we discussed". Matching rules:

- Any run of whitespace between the words counts as one gap: a space, a tab, a line break, a no-break space. A phrase wrapped over two lines is a hit.
- Case does not matter.
- Word boundaries at both ends: "rebased on the research notes", "was discussed in the ticket" and "based on the researchers' notes" are not hits.
- **Scope gate:** the rule only looks at a file that contains, as a whole word anywhere in it, `subagent_type`, `agentType` or `SendMessage`, or the call forms `agent(`, `Agent(` or `Task(`. A file with none of these has no brief to check and is skipped. It reads `agents/*.md`, `skills/*/SKILL.md` and nested `skills/**/SKILL.md` (like the v1 rule); a brief kept in a `references/*.md` file is not scanned.
- Each hit is one `WARN <path>: lazy-delegation line N: '<phrase, whitespace normalised>'`; N is the line where the phrase starts.

False-positive limits (stated in Does not cover): an orchestrator's own non-brief prose ("write the final report based on the research"), and a spawning file that quotes the phrase as a prohibition, both warn. The fix is to name the file or to say in the report why the warning stays. The first two phrases come from OpenHarness (A4); "as discussed" is from the backlog row and is net-new (A18).

**3. The worker report.** Five labelled lines at the end of the worker's reply: `STATUS: complete | partial | blocked`, `SUMMARY`, `EVIDENCE` (one item per line the orchestrator can open or re-run), `NEXT STEPS` (partial only), `BLOCKER` (blocked only). Validity:

| STATUS | valid only when |
|---|---|
| complete | EVIDENCE has at least one item, and there is no BLOCKER or NEXT STEPS |
| partial | NEXT STEPS has at least one item, and there is no BLOCKER |
| blocked | BLOCKER names something concrete |

A missing STATUS line, a status outside the table, or a report failing its row is invalid (A9-A12).

**4. Who validates, and when.** The orchestrator, as ordinary prose in the step that integrates results, before it uses anything from the report. No script, no runtime. A `complete` report with no evidence is rejected and the worker is **re-asked once**: one sentence naming the broken row, and a request for the corrected report. A named worker gets `SendMessage` (continue, it has the context: A15). A one-shot worker (Mode C, launched without `name`, so not addressable) is launched once more with the same brief plus that sentence (net-new, A15). In a Workflow script the same check is a plain `if` after `agent()` and one second `agent()` call. If the second report is invalid too, the orchestrator does not ask a third time: it records the result as unverified in `_workspace/`, says so in the final report and takes nothing from it as fact. A `blocked` report with a concrete BLOCKER is valid and goes to the existing error table; auth, permission and usage-limit failures are still not retried (A13, A14).

**5. Surfaces.** The contract applies wherever an orchestrator spawns or messages a worker: agent teams on Claude Code, Modes A, B and C. It is never pasted into a `## Single-context fallback`: a role pass has no separate worker, and `surfaces.md` section 5 forbids naming `Agent` or `SendMessage` there. Chat exposes no sub-agent tool (observed 2026-10-03, self-reported, `surfaces.md:63`). Cowork sub-delegation is UNVERIFIED and stays so; no probe is added (A26).

### Is a lint rule warranted? Yes

Reasons: (a) the backlog grep fails on three realistic forms (wrapped, tab, no-break space); (b) the lint already runs at Step 6.1 and in `scripts/package-plugin.sh`, so a rule there is one more check on an existing path, not new machinery; (c) the cost is thirteen lines (two regexes, an eight-line loop) and one fixture directory. Why only this one rule and nothing for the report: a report exists at run time, not in the harness files, so a static lint cannot see it. That half of the contract is prose plus the live test below.

- **Rule id:** `lazy-delegation`. **Severity:** WARN (A21). Exit code stays 0 on a WARN-only harness, so the packager does not fail on this rule.
- **Complexity and ReDoS (ran the actual regex, not a stand-in):** the regex is two alternation arms joined by `\s+` between fixed words, no nested quantifier. Timings on `LAZY_RE.finditer` plus the gate, seconds, at n = 25k / 50k / 100k / 200k: `"based on" + " "*n` 0.0011 / 0.0018 / 0.0038 / 0.0076; `"as" + "\n"*n` 0.0011 / 0.0023 / 0.0042 / 0.0087; `"based on "*n` 0.0074 / 0.0145 / 0.0305 / 0.0575; `"based on the "*n` 0.0107 / 0.0218 / 0.0429 / 0.0869; `"as we "*n` 0.0063 / 0.0123 / 0.0252 / 0.0500; `"based on your findin "*n` 0.0151 / 0.0300 / 0.0594 / 0.1262; no-break-space run 0.0008 / 0.0015 / 0.0030 / 0.0058; mixed 0.0180 / 0.0356 / 0.0711 / 0.1600. Doubling n doubles the time: linear. Script: `_workspace/02_strategy-architect_C6_support/redos.py`.
- **A first draft was quadratic, in the line counter, not the regex.** Computing each hit's line number with `text.count("\n", 0, m.start())` took 4.357 s for 30,000 hits. The shipped loop counts newlines only between consecutive hits (`last`), which is linear: 100,000 hits lint in 0.36 s. A test pins it (mutant L21, killed after 50 s).

### Inserted text (exact)

**E1.** After line 297 (`9. **Do not include items that existed only in v1.** ...`):

```markdown
10. **Give every worker a self-contained brief and require a report you can check.** Paste the Delegation block below into the orchestrator once, at the step that launches or messages workers, and fill one brief per worker role.
```

**E2.** Before the `## Follow-up request phrasings` heading. The block below is shown inside a five-backtick fence; inside it, the four-backtick fence is the copy unit, and the text outside that inner fence is explanation and attribution and is not pasted:

`````markdown
## Delegation contract (every template that spawns or messages a worker)

A worker starts with an empty context: it sees its brief and the files the brief names, nothing else. A brief that points back at an earlier result hands your understanding to a reader who never had it, and a report that says "done" with nothing to open cannot be told from a guess. The block below fixes both ends. Paste it at the step that launches workers (Template A: before the `agent()` calls; B: team setup; C: Step 2) and fill the brief once per worker role. Never paste it into a `## Single-context fallback`: a role pass has no separate worker, and the fallback may not name `Agent` or `SendMessage` (`surfaces.md` section 5). (adapted from references/openharness/src/openharness/coordinator/coordinator_mode.py:407 (MIT); adapted from references/openhands/src/api/launch-child-conversation-client-tool.ts:32 (MIT))

Three phrases mark a brief that delegates understanding instead of stating it: "based on your findings", "based on the research" (also "the findings", "your research") and "as discussed" (also "as we discussed"). The first two come from the OpenHarness coordinator rules cited above; "as discussed" is not from any reference. `scripts/lint_harness.py` flags them as `lazy-delegation` in an agent file or a skill file that names `subagent_type`, `agentType`, `SendMessage`, `agent(`, `Agent(` or `Task(`; it reads only `agents/*.md` and `skills/**/SKILL.md`, so a brief kept in a `references/` file is not scanned. Keep the phrases out of the pasted block and out of every brief.

The three report states and the rule that a `complete` report needs evidence come from a fresh-agent loop that validates each round's report. (adapted from references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:112 (MIT)) The single bounded re-ask, with the error fed back, comes from a task guardrail retry loop; the cap of one is ours. (adapted from references/crewai/lib/crewai/src/crewai/task.py:1327 (MIT))

````markdown
### Delegating work

**Worker brief.** The `prompt` of every `Agent` call, `SendMessage` and `agent()` carries these five lines, filled in:

- Goal: one sentence, and what the result is for (the purpose tells the worker how deep to go).
- Inputs: the exact paths to read, with line numbers when the point is one place in a file. State the facts you already hold; never point at an earlier result in place of stating it.
- Scope: what the worker may write or change, and what it must not touch. Workers running in parallel get disjoint scopes.
- Expected output: the file under `_workspace/` and the shape of its content.
- Report: end the reply with the Worker report below.

One task per call; never send the same task twice.

**Worker report.** Every worker ends its reply with:

```text
STATUS: complete | partial | blocked
SUMMARY: one or two sentences
EVIDENCE: one item per line that you can open or re-run (path:line, a command with its output, an artefact path)
NEXT STEPS: what remains (partial only)
BLOCKER: what is missing and what would unblock it (blocked only)
```

**Check before use.** In the step that integrates results, read each report before using anything from it:

| STATUS | Valid only when |
|--------|-----------------|
| complete | EVIDENCE has at least one item, and there is no BLOCKER or NEXT STEPS |
| partial | NEXT STEPS has at least one item, and there is no BLOCKER |
| blocked | BLOCKER names something concrete |

A missing STATUS line, a status outside the table, or a report that fails its row is invalid. Re-ask once: tell the worker which row it broke, in one sentence, and ask for the corrected report. Use `SendMessage` for a named worker; for a one-shot worker launch it once more with the same brief plus that sentence; in a Workflow script make one second `agent()` call the same way. If the second report is invalid too, do not ask again: record the result as unverified in `_workspace/`, say so in the final report, and take nothing from it as fact. This re-ask is the only retry for an invalid report; the general retry-once rule does not add a second. A `blocked` report with a concrete BLOCKER is valid; handle it with the error table, and do not retry authentication, permission or usage-limit failures.
````

Limits. The check confirms that an evidence item is present and never opens it, so an invented path passes (seen in 1 of 3 live runs); the orchestrator keeps reflecting only facts it confirmed itself. The check is prose the orchestrator follows, not code that runs; the `SendMessage` and Workflow branches are untested, and how a Mode A `schema` result carries STATUS is UNVERIFIED. The block does not pin the case of a status word, repeated STATUS lines or the literal `none` under NEXT STEPS or BLOCKER: live, `STATUS: Complete` and `none` lines were accepted and two STATUS lines were rejected, by the model's judgement. The lint knows a short phrase list; a paraphrase passes it.
`````

**E3.** After the `- **Data hand-off**:` bullet in Step 5:

```markdown
- **Delegation contract** (only when the orchestrator spawns or messages a worker, so never in a single-context fallback): paste the Delegation block from `references/orchestrator-template.md` at the step that launches workers and fill one five-line brief per worker role. The block fixes what a brief must contain, the STATUS / EVIDENCE / BLOCKER report a worker ends with, and the check the orchestrator runs before it uses a report (re-ask once, then mark the result unverified). It is prompt quality plus a check, not a guarantee.
```

**E4.** In Step 6.1, replace this clause:

```markdown
that `## Required connectors` lines and the preflight table agree, and v1 artefacts;
```

with:

```markdown
that `## Required connectors` lines and the preflight table agree, that no agent or skill file which calls `Agent(`, `agent(`, `Task(` or `SendMessage`, or names `subagent_type` or `agentType`, contains a lazy-delegation phrase (WARN `lazy-delegation`), and v1 artefacts;
```

**E5.** In Step 6.2, after `Chat/Cowork targets — the single-context fallback covers every phase.` append:

```markdown
 Delegation, wherever workers are spawned or messaged — `grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` lists the orchestrator. Where the lint cannot run, `grep -nEi 'based on (your|the) (findings|research)|as (we )?discussed' project/.claude/skills/*/SKILL.md project/.claude/agents/*.md` is a stricter manual fallback (no word boundaries, every file, blind to a phrase wrapped over two lines): judge each hit by hand, because a research-and-write skill may legitimately keep one.
```

**E6.** In the Deliverable checklist, after the item that starts `- [ ] Every ` followed by the `## Required connectors` line wording (line 181):

```markdown
- [ ] Every worker brief has Goal, Inputs, Scope, Expected output and Report; every worker report ends in STATUS / EVIDENCE / BLOCKER form; the orchestrator re-asks once and then marks the result unverified.
```

**E7.** After row 7 of the `surfaces.md` section 6 table:

```markdown
| 8 | Delegation contract | The Delegation block (`orchestrator-template.md`) is in every section that spawns or messages a worker, and in no Single-context fallback. Code only: chat exposes no sub-agent tool (section 2), Cowork is unverified |
```

**E8.** `skills/finhub-harness/scripts/lint_harness.py` (unified diff against the current file):

```diff
@@ -12,6 +12,11 @@
 KEY_RE = re.compile(r"^([A-Za-z][\w-]*):\s?(.*)$")
 REF_RE = re.compile(r"""(?:subagent_type|agentType)["']?\s*:\s*["']([A-Za-z0-9_-]+)["']""")
 V1_RE = re.compile(r"TeamCreate\(|TeamDelete\(|team_name:|CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=")
+SPAWN_RE = re.compile(r"\b(?:subagent_type|agentType|SendMessage)\b|\b(?:agent|Agent|Task)\(")
+LAZY_RE = re.compile(
+    r"\b(?:based\s+on\s+(?:your|the)\s+(?:findings|research)|as\s+(?:we\s+)?discussed)\b",
+    re.IGNORECASE,
+)
 CONN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
 SECTION_RE = re.compile(r"^## Required connectors[ \t]*\n(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL)
 TABLE_RE = re.compile(r"^ *\| *Agent *\| *Required connector *\| *\n((?: *\|.*\n?)*)", re.MULTILINE)
@@ -137,6 +142,14 @@
                     report("ERROR", path, "subagent-ref", f"line {n}: no agent file for {ref!r}")
             if v1 := V1_RE.search(line):
                 report("ERROR", path, "v1-artefact", f"line {n}: {v1.group(0)}")
+    for path, text in texts.items():  # a brief that points back at earlier results (C6)
+        if not SPAWN_RE.search(text):
+            continue
+        ln = last = 0
+        for m in LAZY_RE.finditer(text):
+            ln, last = ln + text.count("\n", last, m.start()), m.start()
+            hit = " ".join(m.group(0).split())
+            report("WARN", path, "lazy-delegation", f"line {ln + 1}: {hit!r}")
     for agent, server in sorted(declared - table):
         report("ERROR", root, "preflight", f"agent {agent!r} needs {server!r}: no preflight row")
     for agent, server in sorted(table - declared):
```

The loop sits after the per-line v1 loop and before the preflight reports, so existing report order is unchanged. It uses `ln`, not `line`, so it does not rebind the `str` loop variable `line` that `mypy --strict` types as `str` elsewhere in `main`.

**E9.** Fixtures, `tests/fixtures/harness_delegation/` (byte-exact in the patch; `<TAB>` and `<NBSP>` mark the two non-space characters):

| file | content that matters | expected |
|---|---|---|
| `agents/worker.md` | frontmatter with `model: sonnet  # ...`; body "Write the summary based on the research you are given." No spawn token | silent (scope gate) |
| `agents/delegator.md` | body: launch `subagent_type: "worker"` and "based on your findings, fix the bug." | WARN line 7 (agent files are scanned when they delegate) |
| `skills/lazy-orchestrator/SKILL.md` | line 7 "Based on your findings"; line 8 "AS WE DISCUSSED"; lines 9-10 "based on the" + newline + "research"; line 11 "as discussed"; line 12 `based<TAB>on<NBSP>the<TAB>findings`; line 13 "based on the research, as discussed" (two hits, one line); line 14 "based on your research"; lines 15-16 `as<TAB>we` + newline + `discussed` | 9 hits, lines 7, 8, 9, 11, 12, 13, 13, 14, 15 |
| `skills/lazy-orchestrator/references/deep/SKILL.md` | `agentType: 'worker'` then "based on your findings", no frontmatter | WARN line 2 (nested file) |
| `skills/clean-orchestrator/SKILL.md` | has `subagent_type`; near misses: "rebased on the research notes", "was discussed in the ticket", "based on the researchers' notes", "findingsX", "Based on your input", "based on the result", "as we agreed", "has discussed", "discussed above" | silent (word boundaries, wrong words) |
| `skills/wf-orchestrator/SKILL.md` | line 6: `agent("Based on your findings, fix the bug", {schema})`, no `agentType` | WARN line 6 (`agent(` alone opens the gate) |
| `skills/task-orchestrator/SKILL.md` | line 6: `Task(prompt: "As discussed, go ahead")` | WARN line 6 (`Task(`) |
| `skills/named-orchestrator/SKILL.md` | line 6: `Agent(name: "w", prompt: "based on the research above")`, no `subagent_type` | WARN line 6 (`Agent(`) |
| `skills/msg-orchestrator/SKILL.md` | line 6: `SendMessage(to: "w", message: "based on your findings, continue")` | WARN line 6 (`SendMessage`) |
| `skills/no-spawn/SKILL.md` | "based on the research ..., as discussed with the client"; names `my_agentType`, `old_subagent_type`, `subagent_types`; look-alikes `SendMessages`, `magent(x)`, `subTask(x)`, `Tasks(x)`, `task(x)`, `agents(x)` (none a whole-word gate token) | silent (scope gate, every boundary and the call-form paren) |

Result, run on the simulated tree: `0 error(s), 15 warning(s)`, exit 0 (hits at lines 7, 8, 9, 11, 12, 13, 13, 14, 15 of the lazy orchestrator, line 2 of the nested file, line 7 of `delegator.md`, line 6 of each of the four call-form orchestrators).

**E10.** Tests appended to `tests/test_lint_harness.py` (the full block is in the patch):

- `test_lazy_delegation_is_flagged_in_spawning_files_only`: exit 0, `Traceback` absent, each of the 15 expected `<path>: lazy-delegation line N: '<phrase>'` strings present, WARN count exactly 15, last line `0 error(s), 15 warning(s)`. Pins: every phrase and alternative, case, whitespace kinds, wrap, two hits on a line, line numbers, WARN not ERROR, scope gate, nested file, agent file, word boundaries.
- `test_lazy_delegation_regex_is_linear`: runs the real script on a file with six adversarial 300k-character or 50k-repeat segments; exit 0, no `lazy-delegation` line, under 20 s.
- `test_lazy_delegation_line_numbers_are_linear`: 100,000 hits; the last is reported as line 100005; under 20 s (the subprocess helper times out at 60 s).
- `test_lazy_delegation_in_a_dot_claude_project_with_a_late_gate_and_odd_whitespace` (new in r2, the judge's S3 test): a project rooted at a directory named `.claude` (the real target is `project/.claude`), a `SKILL.md` with 400 filler lines, then `subagent_type: "w"`, then `based on the<CR><LF>research`, `as<U+2003>discussed` and `as<VT>we discussed`. Exactly 3 `lazy-delegation` warnings at lines 406, 408 and 409, exit 0. Kills J04, J14 and J19.
- `test_this_repo_has_no_lazy_delegation`: `.claude` and the repo root print no `lazy-delegation` line.

An existing test is **not** changed. `test_bad_fixture_names_every_seeded_defect` counts 24 errors and 4 warnings exactly, so the seeded cases live in a new fixture directory instead of `harness_bad`. The import block gains `import time`. The two over-long `head = '...'` string lines are wrapped in parentheses so `black --check` passes (S1).

## Proof

All commands from the repo root of the built tree. Results are from the simulated tree (scratch copy with the patch applied), 2026-10-04.

### P-1 Insertions landed (`_workspace/02_strategy-architect_C6_support/proof.sh`)

T = `skills/finhub-harness/references/orchestrator-template.md`, S = `skills/finhub-harness/SKILL.md`, U = `skills/finhub-harness/references/surfaces.md`.

| id | command | expected | result |
|---|---|---|---|
| G01 | `grep -c '^10\. \*\*Give every worker a self-contained brief' T` | 1 | 1 |
| G02 | `grep -c '^## Delegation contract (every template that spawns or messages a worker)' T` | 1 | 1 |
| G03 | `grep -c '^\*\*Worker brief\.\*\* The .prompt. of every' T` | 1 | 1 |
| G04 | `grep -c '^- \(Goal\|Inputs\|Scope\|Expected output\|Report\): ' T` | 5 | 5 |
| G05 | `grep -c '^STATUS: complete | partial | blocked$' T` | 1 | 1 |
| G06 | `grep -c '^\(SUMMARY\|EVIDENCE\|NEXT STEPS\|BLOCKER\): ' T` | 4 | 4 |
| G07-G09 | the three table rows `^| complete | EVIDENCE has at least one item, and there is no BLOCKER or NEXT STEPS |$`, `^| partial | NEXT STEPS has at least one item, and there is no BLOCKER |$`, `^| blocked | BLOCKER names something concrete |$` | 1 each | 1, 1, 1 |
| G10 | `grep -c 'Re-ask once: tell the worker which row it broke' T` | 1 | 1 |
| G11 | `grep -c 'do not ask again: record the result as unverified' T` | 1 | 1 |
| G12 | `grep -c 'for a one-shot worker launch it once more with the same brief' T` | 1 | 1 |
| G13 | `grep -c 'make one second .agent[(][)]. call the same way' T` | 1 | 1 |
| G14 | `grep -c 'A .blocked. report with a concrete BLOCKER is valid' T` | 1 | 1 |
| G15-G18 | `grep -c 'adapted from references/<path>:<line> (MIT)' T` for `openharness/src/openharness/coordinator/coordinator_mode.py:407`, `openhands/src/api/launch-child-conversation-client-tool.ts:32`, `deepseek_harness/packages/workflow/tool-ralph/src/index.ts:112`, `crewai/lib/crewai/src/crewai/task.py:1327` | 1 each | 1, 1, 1, 1 |
| G19 | the lines between the outer four-backtick fence, piped to `grep -ciE 'based on (your\|the) (findings\|research)\|as (we )?discussed'` | 0 | 0 |
| G20 | awk: principle 9 line < principle 10 line < section heading < follow-up heading | ordered | ordered |
| G21 | `grep -c '^- \*\*Delegation contract\*\* (only when the orchestrator spawns or messages a worker' S` | 1 | 1 |
| G22 | `grep -c 'WARN .lazy-delegation.)' S` | 1 | 1 |
| G23 | `grep -c "grep -l 'STATUS:' project/.claude/skills/\*/SKILL.md" S` | 1 | 1 |
| G24 | `grep -c "as (we )?discussed' project/.claude/skills/\*/SKILL.md project/.claude/agents/\*.md" S` | 1 | 1 |
| G25 | `grep -c '^- \[ \] Every worker brief has Goal, Inputs, Scope, Expected output and Report' S` | 1 | 1 |
| G26 | `grep -c '^| 8 | Delegation contract |' U` | 1 | 1 |
| G27 | the Step 6 grep over `skills/*/SKILL.md .claude/skills/*/SKILL.md .claude/agents/*.md`, `\| wc -l` | 0 | 0 |
| G28 | `wc -l < S` | 200 | 200 |
| G29 | `LC_ALL=C.UTF-8 grep -rcP '[\x{AC00}-\x{D7A3}]'` over the five touched files and the fixture dir, summed | 0 | 0 (the standalone `grep -P` run returns rc 1, as the QA bar requires) |
| G30 | `grep -c '^````' T` (outer copy fence) | 2 | 2 |
| G31-G33 | `Never paste it into a .## Single-context fallback.`, `^One task per call; never send the same task twice\.$`, `Workers running in parallel get disjoint scopes` in T | 1 each | 1, 1, 1 |
| G34 | `grep -c 'stricter manual fallback' S` | 1 | 1 |
| G35 | `grep -c 'This re-ask is the only retry for an invalid report' T` | 1 | 1 |
| G36 | `grep -c 'never opens it, so an invented path passes' T` | 1 | 1 |
| G37 | `grep -c '"as discussed" is not from any reference' T` | 1 | 1 |
| G38 | `grep -c 'prints nothing' S` | 0 | 0 |
| G39 | `grep -c 'which spawns workers briefs them' S` | 0 | 0 |
| G40 | `grep -c 'agent or skill file which calls' S` | 1 | 1 |

Whole-line check, stronger than the counts: every inserted line of E1-E3, E6, E7 is found exactly once as a whole line (`grep -cxF`), and the two in-place clauses E4, E5 are found exactly once as substrings. 31 whole lines and 2 substrings (`mutate_prose.py` does this check; baseline clean).

The Step 6 grep from the backlog row, on the CURRENT tree (before any edit): `grep -nEi 'based on (your|the) (findings|research)|as (we )?discussed' skills/*/SKILL.md .claude/skills/*/SKILL.md .claude/agents/*.md` prints nothing, rc 1. Before-state of the contract: `grep -c 'STATUS:' skills/finhub-harness/references/orchestrator-template.md` = 0, and no file under `skills/` or `tests/` contains `lazy-delegation`. So the contract is new, not a rewording (A25).

### P-2 Gates (simulated tree)

| gate | command | result |
|---|---|---|
| unit | `.venv/bin/python -m pytest -q tests/test_lint_harness.py` | `9 passed` (4 existing, unmodified, plus 5 new) |
| style | `black --check tests/test_lint_harness.py skills/finhub-harness/scripts/lint_harness.py`; `ruff check` on the same two; `mypy --strict` on the same two | black: `All done! ✨ 🍰 ✨` / `2 files would be left unchanged.`; ruff: `All checks passed!`; mypy: `Success: no issues found in 2 source files` (S1: the first issue failed black on the two over-long `head = '...'` lines; fixed) |
| lint, this repo | `lint_harness.py .` | `0 error(s), 0 warning(s)` |
| lint, `.claude` | `lint_harness.py .claude` | `0 error(s), 5 warning(s)`, identical to before; zero `lazy-delegation` lines |
| lint, good fixture | `lint_harness.py tests/fixtures/harness_good` | `0 error(s), 0 warning(s)` |
| lint, bad fixture | `lint_harness.py tests/fixtures/harness_bad` | `24 error(s), 4 warning(s)` (unchanged) |
| lint, delegation fixture | `lint_harness.py tests/fixtures/harness_delegation` | `0 error(s), 15 warning(s)`, exit 0 |
| packager | `bash scripts/package-plugin.sh` | exit 0; the three archives rebuild |
| refs | `bash scripts/check-harness-refs.sh` | 40 PASS, 0 FAIL, rc 0 (40 before as well) |
| 8-word runs | `_workspace/02_strategy-architect_C6_support/ngram.py` against the cited reference files | `8-gram hits: 0` |
| full suite | every `tests/test_*.py` run on its own in the patched scratch copy | all 24 files pass (for example `test_lint_harness.py` 9 passed, `test_sensitive_paths.py` 214 passed 1 skipped, `test_server.py` 63 passed). A single-process `pytest -q` of the whole tree stalled at about 32% with one `F` in my sandbox (not diagnosed, and not re-run on the unpatched tree; no file I touched is involved), so QA runs the full suite itself |

How the packager and `check-harness-refs.sh` treat the new text: no new file under `skills/`, so `package-plugin.sh` zips the edited files like any other and runs its existing `lint_harness.py .` step, which stays at exit 0 because the rule is a WARN and the repo has no hit. `check-harness-refs.sh` checks `.claude/` prose and calls the packager; it never reads the new text directly, and its own Hangul check covers only `.claude/agents` and the triage skill, so the Hangul check for the new plugin text is G29 and the standalone `grep -P`. `tests/` is not packaged.

### P-3 Seeded bad orchestrator is flagged, report without evidence is rejected

**Banned phrase.** `lint_harness.py tests/fixtures/harness_delegation` prints 15 WARN lines (above). On `lazy-orchestrator/SKILL.md` the lint reports 9 hits on 8 lines (7, 8, 9, 11, 12, 13, 14, 15); the Step 6 grep prints 5 lines (7, 8, 11, 13, 14) and misses 9 (wrapped), 12 (tab and no-break space) and 15 (tab and line break), so Step 6.1 names the lint first (A19). Over the whole fixture tree the grep (`skills/*/SKILL.md agents/*.md`) prints 15 lines, 5 of which the lint is silent on (`clean-orchestrator` 7, 8, 10; `no-spawn` 6; `agents/worker.md` 7); that is why E5 calls it a stricter manual fallback to be judged by hand (A35).

**Report without evidence (live, Claude Code 2.1.289, 2026-10-04, re-run for revision 2 on the revision 2 block).** Everything needed is in `_workspace/02_strategy-architect_C6_support/live/` and runs as shipped (fixed: the first issue omitted the agent and skill files). `build_fixture.sh <template.md> <good|once|always> <outdir> [noblock]` writes `.claude/agents/scanner.md` (a scripted test double), `.claude/skills/fixture-orchestrator/SKILL.md` (the Delegation block extracted from the template by `awk`, so the test uses the shipped text), `_workspace/note.txt` and `run.sh`. `run.sh <tag>` runs `claude -p` with `--permission-mode dontAsk` and `--allowedTools "Agent Read Skill SendMessage Write"`, no `bypassPermissions`. `check_case.sh <case> <tag>.jsonl` prints PASS or FAIL. The double must have no tool that could produce evidence (`tools: Glob`) and the brief says `Inputs: none`; my first doubles had `Read` and a brief that named a file, and produced evidence unprompted, which proved nothing.

Checker rules: `good` = 1 worker call and a final line that says accepted; `once` = 2 calls and accepted; `always` = exactly 2 calls AND a final line AND (the final line says unverified OR the second reply's `EVIDENCE:` line is non-empty); `noblock-always` (the control) must NOT be 2 calls. A run that ends without a final line fails `always`. The call count is the discriminator; the same model marked a no-evidence report "unverified" on its own even without the contract.

| case | double | worker calls | final line | checker |
|---|---|---|---|---|
| block present | `good` (evidence on the first report) | 1 | accepted | PASS |
| bad first, good on re-ask | `once` | 2 and 2 (two runs) | accepted, "re-asked once" | PASS, PASS |
| never complies | `always` | 2, 2, 2 (three runs) | unverified, unverified, "both scanner reports failed the evidence check" (the second reply's EVIDENCE was `No initialization errors`, not an item that can be opened, and the orchestrator rejected it) | PASS x3 |
| block deleted (control) | `always` | 1 and 1 (two runs) | unverified, by the model's own judgement | PASS (not 2 calls, so the contract is what causes the re-ask) |
| additive mutant: block plus "If EVIDENCE is empty, accept the report anyway." (the judge's P-A1) | `always` | 1 | accepted, EVIDENCE empty | **FAIL: killed** (the judge's run gave 2 calls and no final line; the final-line rule kills that outcome too) |

Earlier (revision 0 block, before sentence (c) was added) two more live mutants were killed by the call count alone: "re-ask until valid, at most five times" gave 6 calls, and a `complete` row reading "EVIDENCE may be empty" gave 1 call and accepted. Both are also killed by the whole-line check, so they were not re-run. In the first issue's `always` runs one of three accepted after the re-asked double invented a path; that run would pass the checker too (the second `EVIDENCE:` was non-empty): the limit stated in Does not cover.

Not live-tested: the `SendMessage` branch for a named worker and the Workflow `agent()` branch (UNVERIFIED, prose only).

### P-4 Cold build from the skill text

One run, 2026-10-04: a fresh `claude -p` session told to read the edited `SKILL.md` and its references and build a two-agent Mode C harness ("TODO audit": `scanner`, `reporter`) for Claude Code, through Step 6 (`live/cold_build_run.sh`). Result in the built harness: `lint_harness.py project/.claude` `0 error(s), 0 warning(s)`; the Step 6 grep prints nothing (rc 1); `grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` lists the orchestrator; it has the five brief lines (5 matches), `**Worker report.**`, `**Check before use.**` and a re-ask-once rule. It condensed the block to the Agent-call wording and kept every piece. One run, not a rate. QA repeats this once with its own fixture domain.

## Test plan

**Unit cases:** the five new tests above and the fixture table in E9.

**Must still pass (unchanged):** `test_bad_fixture_names_every_seeded_defect` (24 errors, 4 warnings), `test_clean_fixture_passes_without_warnings`, `test_this_repo_team_and_plugin_pass`, `test_nothing_to_lint_is_an_error`; `scripts/package-plugin.sh`; `scripts/check-harness-refs.sh`; the full `pytest -q`.

**Quant guardrails:** not applicable. This item touches no backtest, eval, verifier or pricing code; the lint is a text check on harness files. Stated so the judge need not look for fee, borrow, slippage, look-ahead, survivorship or train/test rows.

**QA bar (fixed up front, from Pick 7):** gates green; every design grep returns the stated result on the current files; a cold build contains the contract and passes the Step 6 check; a seeded bad orchestrator and a no-evidence report are flagged or re-asked; ZERO non-equivalent mutants that let a seeded bad brief or a `complete` report without evidence through; message-only survivors are follow-ups; one fresh QA batch only.

**Mutants, run by me on scratch copies, a fresh process each, every mutation asserted real (`mutate_lint.py` asserts the old text exists and the file changed):**

*Lint (`02_strategy-architect_C6_support/mutate_lint.py`), 36 mutants, 36 killed, 0 survivors (29 in the first issue, 7 more for the widened gate; the three gate rows below are replaced):*

| id | mutation | killed by |
|---|---|---|
| L01-L04 | drop `findings`, `research`, `your`, `the` from the alternation | the per-phrase hits in the E9 test |
| L05, L06, L07 | drop the optional `we`; drop the whole "as discussed" arm; drop the whole "based on" arm | line 8, 11, 15 hits |
| L08 | remove `re.IGNORECASE` | "Based", "AS WE DISCUSSED" hits |
| L09, L10, L10b | `\s+` to a single space (as-arm); to ` +` (based-arm); to `[ \t]` (no line wrap) | wrap, tab, NBSP, line 15 |
| L11, L12 | drop the leading or trailing `\b` of `LAZY_RE` | "rebased on", "was discussed", "researchers'" in the clean fixture |
| L13 | severity WARN to ERROR | exit-code assertion `code == 0` |
| L14 | remove the scope gate | `worker.md` and `no-spawn` stay silent |
| L15, L16, L17 | gate loses `agentType`, `subagent_type` or `SendMessage` | nested `agentType` file; `subagent_type` orchestrators; `msg-orchestrator` |
| L17a, L17c, L17d | gate loses `agent(`, `Agent(` or `Task(` | `wf-`, `named-` and `task-orchestrator` fixtures |
| L17e-L17i | gate group 1 loses its leading or trailing `\b`; group 2 loses its leading `\b`, its `(`, or gains lowercase `task(` | `my_agentType`, `old_subagent_type`, `subagent_types`, `magent(x)`, `subTask(x)`, `Tasks(x)`, `agents(x)`, `task(x)` in `no-spawn` |
| L18, L19 | reported line number off by one, low or high | exact `line N` strings |
| L20 | first hit per file only | the line-13 double hit and the later lines |
| L21 | naive per-hit `text.count("\n", 0, ...)` | the 100,000-hit test, timing (50 s against a 20 s bound) |
| L22 | skip nested `SKILL.md` | nested fixture |
| L23 | gate applied per line, not per file | phrase lines that do not carry the token |
| L24 | skip agent files | `delegator.md` |
| L25 | rule body deleted | every hit |
| L26, L27 | rule id renamed; hit text left un-normalised | exact message strings (message-only; killed anyway) |

L21 depends on wall-clock time (a 2.5x margin on this machine); it is the one timing-based kill.

*Prose (`mutate_prose.py`), 45 semantic mutants plus an automatic delete-each-inserted-line sweep of 31 lines, 76 killed, 0 survivors* by the whole-line and substring check: brief lines (Goal, Inputs, Scope disjointness, Expected output optional, Report), status enum (drop `partial`, drop `blocked`), each table row and its threshold (evidence at least one to zero; complete may carry a blocker; partial threshold; blocked needs no concrete blocker), re-ask cap (once to twice; to unbounded), second-failure rule (accepted instead of unverified; missing), the three re-ask branches (named, one-shot, Workflow), the blocked-is-valid sentence, the single-context fallback exclusion, the phrase list narrowed, a lazy phrase seeded inside the copy block, each of the four attribution lines, principle 10, the `SKILL.md` Step 5 bullet, the Step 6.1 clause, each part of the Step 6.2 grep (STATUS check, each alternation arm, the agents directory), the checklist item, the surfaces row and its chat claim, the Limits paragraph. These are presence and wording kills; behaviour is covered by the live rows in P-3.

*Live behaviour:* the no-block control (1 call, not 2), the judge's additive mutant "If EVIDENCE is empty, accept the report anyway" (1 call, accepted: FAIL) and, from the first issue, "at most five asks" (6 calls) and "EVIDENCE may be empty" (1 call, accepted) are all killed.

*The judge's mutant set (`mutate_judge.py`, the judge's own `mut.py` ported to this tree), 20 mutants:* 15 killed, 4 survive, 1 equivalent. J04, J14 and J19 (the three that let a bad brief through) are now killed by the S3 test (`1 failed, 8 passed` each). Also killed: J05, J06, J08-J13, J15, J16, J18, and P-A1 by the live rule above. Survivors, all false positives or message-only, none lets a bad brief through: J01 (`on\s*`: `based onthe research` flagged), J02 (`our` accepted), J03 (`findings?`), J07 (line off by one only when a file starts with a newline). Equivalent: J17 (`if ln or True`, a tautology). The four survivors are listed under Follow-ups (not built).

*For QA to repeat on the built tree:* run `mutate_lint.py`, `mutate_judge.py` and `mutate_prose.py` (copy them into a scratch copy of the built repo; they use a scratch layout with a `.venv` link), plus one fresh batch of its own. Equivalent mutants identified: none. Message-only mutants (L26, L27) are already killed, so there are no follow-ups from my side.

## Does not cover

- **Not a guarantee.** The contract is prompt quality plus a check the orchestrator performs by reading. A worker can still invent evidence: observed in 1 of 3 live runs, the re-asked double supplied a made-up path and the report passed. Evidence present is not evidence true. The orchestrator keeps the existing rule that it reflects only facts it confirmed itself (Template A/C error tables); the contract does not add an "open one evidence item" step.
- **The validation is prose, not code.** No validator script, no JSON-schema enforcement in Workflow mode beyond the orchestrator's own `if`; no handoff size cap (the DeepSeek `maxHandoffChars` is not adopted).
- **Lint false negatives.** Only six phrase forms. A paraphrase ("go with what you found", "use the earlier analysis") passes. Markup inside the phrase (`based on **your** findings`), a hyphen, a zero-width character or another language passes. The scope gate now covers `subagent_type`, `agentType`, `SendMessage`, `agent(`, `Agent(` and `Task(`; a file that delegates in some other way (a different tool name) or keeps its briefs in `references/*.md` is not scanned. Also silent: "based upon your findings", "based on your earlier findings", the singular "based on the finding", "as previously discussed", "per our discussion".
- **Lint false positives.** A delegating file's own non-brief prose ("write the final report based on the research"), or a spawning file that quotes the phrase as a prohibition, warns. The copy block itself carries no phrase (G19), and the explanation that lists the phrases is in the template, which the lint does not scan (the lint reads `SKILL.md` files and agent files, not `references/*.md`). A builder who pastes the explanation as well as the block will see WARN lines; the section says to paste the block only.
- **WARN does not gate.** A harness with `lazy-delegation` warnings still exits 0 and packages. Step 6 says fix or explain.
- **The Step 6 grep is not the lint.** It is a stricter manual fallback for chat without code execution: it has no word boundaries and no gate, so on the delegation fixtures it prints 5 lines the lint is silent on (`clean-orchestrator` 7, 8, 10, "rebased on the research", "based on the researchers'", "was discussed", "has discussed"; `no-spawn` 6; `agents/worker.md` 7), and it is blind to a phrase wrapped over two lines or separated by a tab or no-break space. A harness with a legitimate research-and-write leaf skill cannot make it print nothing; each hit is judged by hand. The packager and Step 6.1 use the lint, not the grep.
- **Live evidence is one model, one fixture, Mode C, one-shot relaunch only.** The `SendMessage` branch (named worker, Mode B) and the Workflow `agent()` branch are UNVERIFIED live. One re-ask costs a full repeat of the work for a one-shot worker, since it starts without the earlier context.
- **Surfaces.** Applies to agent teams on Claude Code. Chat has no sub-agent tool (observed, self-reported); there the block is never used. Cowork sub-delegation behaviour is UNVERIFIED, and no repo doc in `references/` verifies it; no probe was added (S).
- **Single cold build, one run**, not a rate. The cold-built harness condensed the block; the conditions in the Step 6 greps held.
- **OpenHarness licence provenance** still rests on the pinned fork's LICENSE.

## Follow-ups (not built)

From the judge's round 1 list; none can let a seeded bad brief or a no-evidence report pass, so none blocks.

- **F2 report grammar (rest):** whitespace-padded items (the DeepSeek source rejects them, `index.ts:105`) are not specified; the case of the status word, repeated STATUS lines and a literal `none` are described but not pinned (Limits paragraph).
- **F6 line numbers:** the new loop counts `\n` only, the older per-line loop uses `splitlines()`; form feed, vertical tab and U+2028 skew the two. Message-only.
- **F7 `grep -l 'STATUS:'` proves the token, not the contract;** briefs in `references/*.md` are not scanned.
- **F9 `surfaces.md` row 8 is a statement, not a runnable check.**
- **J01-J03, J07** (the four surviving false-positive mutants): add `based onthe research`, `based on our findings`, `based on the finding` and a leading-newline file to the clean fixtures if a stricter matcher is wanted.
- **Mode A:** how a Workflow `schema` result carries STATUS and where the `if` goes is under-specified; UNVERIFIED, nothing in `references/` settles it.
- **Live:** the `SendMessage` (Mode B) and Workflow branches have no live run.

## Authority List

Evidence is cited inside `references/` only. A claim whose evidence is in the plugin, in a run or in my own measurement is `NET-NEW` with a reason and a named verification that can fail.

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | A worker cannot see the orchestrator's conversation, so a brief must be self-contained | references/openhands/src/api/launch-child-conversation-client-tool.ts:17; references/openharness/src/openharness/coordinator/coordinator_mode.py:405 | C6 |
| A2 | A brief carries the goal, the relevant paths, the constraints, the expected deliverable and how to report back | references/openhands/src/api/launch-child-conversation-client-tool.ts:34-35 | C6 |
| A3 | A brief states what the result is for, so the worker calibrates depth (the Goal line) | references/openharness/src/openharness/coordinator/coordinator_mode.py:424 | C6 |
| A4 | A brief must not point at earlier findings with "based on your findings" or "based on the research"; the orchestrator states the understanding itself | references/openharness/src/openharness/coordinator/coordinator_mode.py:411 | C6 |
| A5 | Stating the understanding means specific file paths and line numbers (the Inputs line) | references/openharness/src/openharness/coordinator/coordinator_mode.py:409 | C6 |
| A6 | Parallel workers get independent scopes, and one task goes in one call, never sent twice | references/openhands/src/api/launch-child-conversation-client-tool.ts:36-38 | C6 |
| A7 | The brief names its expected output, and a task without an expected output is invalid | references/crewai/lib/crewai/src/crewai/task.py:153-155; references/crewai/lib/crewai/src/crewai/project/crew_base.py:106 | C6 |
| A8 | The report says what was done, what was verified and what risk remains (mapped to SUMMARY, EVIDENCE, NEXT STEPS or BLOCKER) | references/openharness/src/openharness/autopilot/service.py:2035-2038 | C6 |
| A9 | Report fields are status, summary, evidence, next steps and blocker, with three statuses | references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:91-103 | C6 |
| A10 | Validity rows: a continuing report needs next steps and no blocker, a complete report needs evidence and no next steps or blocker, a blocked report needs a concrete blocker, anything else is invalid | references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:112-142 | C6 |
| A11 | Completion must be backed by evidence gathered first | references/deepseek_harness/packages/goal/goal-round-driver/src/prompt.ts:20-22 | C6 |
| A12 | NET-NEW: the middle status is named `partial`, not `continue`. Reason: a one-shot delegation has no next round. Verification that can fail: G05 (the status line found once; `continue` absent) and mutant P06/P07 | n/a | C6 |
| A13 | A failed check yields an error message that is fed back to a bounded retry, then fails | references/crewai/lib/crewai/src/crewai/utilities/guardrail.py:68-70; references/crewai/lib/crewai/src/crewai/task.py:1343; references/crewai/lib/crewai/src/crewai/task.py:1382; references/crewai/lib/crewai/src/crewai/task.py:1400 | C6 |
| A14 | NET-NEW: the cap is one re-ask, then `unverified`. Reason: the backlog row's proof says once; the source default is three (`task.py:279-280`). Verification that can fail: G10, G11; mutants P12, P13; live `always` runs, 3 of 3 with exactly 2 worker calls; mutant "at most five asks" gave 6 calls | n/a | C6 |
| A15 | A failed worker with context is continued, not respawned (named worker: `SendMessage`) | references/openharness/src/openharness/coordinator/coordinator_mode.py:384; references/openharness/src/openharness/coordinator/coordinator_mode.py:440 | C6 |
| A16 | NET-NEW: an unnamed one-shot worker is relaunched once with the same brief plus the one sentence. Reason: it is not addressable (Mode C is launched without `name`, `orchestrator-template.md` principle 4), so there is nothing to continue. Verification that can fail: G12; live runs `once` B1 and B2, both 2 worker calls and a corrected report | n/a | C6 |
| A17 | NET-NEW: no new text for "the coordinator delegates and does not do the work" (C34) or "never fabricate agent results" (OH1); Template C already says the main agent does not repeat a search it already delegated. Reason: S. Verification that can fail: `sed -n 249p skills/finhub-harness/references/orchestrator-template.md` prints "Wait for the completion notifications. The main agent does not repeat a search it already delegated." (run: it does) | n/a | C6 |
| A18 | NET-NEW: "as discussed" and "as we discussed" are in the banned list. Reason: they come from the backlog row's proof text, not from a reference (`grep -rn "as we discussed\|as discussed"` over the cited reference directories printed nothing). Verification that can fail: fixture lines 8, 11, 15 expect hits; mutants L05, L06, L09 | n/a | C6 |
| A19 | CHANGED r2. NET-NEW: matching is case-insensitive, whitespace-tolerant (space, tab, line break, CR LF, no-break space, em-space, vertical tab), bounded by word boundaries, reported at the phrase's start line. Reason: generated prose wraps and varies. Verification that can fail: `test_lazy_delegation_is_flagged_in_spawning_files_only` and the S3 test; mutants L08-L12, L18, L19, J04; measured on `lazy-orchestrator/SKILL.md`: the Step 6 grep prints 5 lines (7, 8, 11, 13, 14), the lint reports 9 hits on 8 lines (7, 8, 9, 11, 12, 13, 14, 15) | n/a | C6 |
| A20 | CHANGED r2. NET-NEW: the rule scans a file only when it contains, as whole words, `subagent_type`, `agentType` or `SendMessage`, or the call forms `agent(`, `Agent(` or `Task(`; it also scans agent files and nested `SKILL.md`. Reason: a Workflow `agent()`, `Task(`, `Agent(name:, prompt:)` or `SendMessage` can carry a bad brief without `subagent_type` (`workflow-recipes.md:200` lets `agentType` be omitted), and a file with none of these has no brief. Verification that can fail: fixtures `wf-`, `task-`, `named-` and `msg-orchestrator` each give a WARN at line 6 (before the fix the judge's repro file linted 0/0), `worker.md` and `no-spawn` stay silent; mutants L14-L17i, L22-L24, J09, J13, J14, J18 | n/a | C6 |
| A21 | CHANGED r2. NET-NEW: severity is WARN, exit 0. Reason: the false positives in Does not cover; the packager must not fail on a heuristic. Verification that can fail: the E9 test asserts exit 0 and `0 error(s), 15 warning(s)`; mutant L13 | n/a | C6 |
| A22 | NET-NEW: the rule is linear in input size, including line numbering. Reason: lint runs on every packaging. Verification that can fail: the sweep numbers in § Design (doubling n doubles time; 200k-character runs under 0.17 s), `test_lazy_delegation_regex_is_linear`, `test_lazy_delegation_line_numbers_are_linear`; mutant L21 (naive count 4.357 s for 30,000 hits, 50 s for 100,000) | n/a | C6 |
| A23 | NET-NEW: the repo's current text has no hit, so adding the rule does not break the repo. Reason: `test_this_repo_team_and_plugin_pass` and the packager lint run on it. Verification that can fail: the Step 6 grep over this repo's `skills/*/SKILL.md`, `.claude/skills/*/SKILL.md` and `.claude/agents/*.md` prints nothing (run, rc 1); `lint_harness.py .` 0 errors 0 warnings; `.claude` 0 `lazy-delegation` lines | n/a | C6 |
| A24 | NET-NEW: the copy block contains none of the banned phrases, so a pasted block does not trip the lint. Verification that can fail: G19 returns 0; mutant P21 seeds a phrase into the block and the whole-line check fails | n/a | C6 |
| A25 | NET-NEW: the contract is new text, not a rewording; Mode C only says to state Agent parameters without omission. Verification that can fail: before the edit `grep -c 'STATUS:' skills/finhub-harness/references/orchestrator-template.md` = 0 and `grep -rln lazy-delegation skills tests` finds nothing; `grep -n "without omission" skills/finhub-harness/references/orchestrator-template.md` shows lines 290 and 292 only (run) | n/a | C6 |
| A26 | NET-NEW: the contract is Claude Code only; chat has no sub-agent tool and Cowork is UNVERIFIED. Reason: the evidence is the plugin's own surface notes, outside `references/`. Verification that can fail: `sed -n 63p skills/finhub-harness/references/surfaces.md` says sub-agent tools are not exposed in chat (observed 2026-10-03, self-reported) and `sed -n 134p` shows Cowork `unverified`; the Cowork probe P4 in `docs/surface-verification.md` is the check that would settle it | n/a | C6 |
| A27 | NET-NEW: an orchestrator that carries the block re-asks a no-evidence report exactly once and not otherwise. Reason: this is a behaviour of a model following prose. Verification that can fail: P-3 table, `claude` 2.1.289: `good` 1 call, `once` 2 and 2, `always` 2, 2, 2; the control without the block 1 and 1; mutants "at most five" 6 calls, "EVIDENCE may be empty" 1 call | n/a | C6 |
| A28 | NET-NEW: a cold build from the skill text pastes the contract and passes Step 6. Verification that can fail: P-4: lint `0 error(s), 0 warning(s)`, Step 6 grep prints nothing, `grep -l 'STATUS:'` lists the orchestrator, five brief lines present. One run | n/a | C6 |
| A29 | NET-NEW: the packager and `check-harness-refs.sh` need no change. Verification that can fail: `bash scripts/package-plugin.sh` exit 0 and `bash scripts/check-harness-refs.sh` 40 PASS 0 FAIL on the simulated tree | n/a | C6 |
| A30 | NET-NEW: no 8-word run is copied from a reference. Verification that can fail: `ngram.py` prints `8-gram hits: 0` over the cited files and their sibling files | n/a | C6 |
| A31 | NET-NEW: `SKILL.md` stays under 500 lines. Verification that can fail: `wc -l < skills/finhub-harness/SKILL.md` = 200 | n/a | C6 |
| A32 | The sources are MIT and may be adapted with an attribution line; OpenHarness upstream org is unverified | references/LICENSES.md:9; references/LICENSES.md:11; references/LICENSES.md:12; references/LICENSES.md:14 | C6 |
| A33 | NET-NEW: each insertion carries one attribution line in the form `adapted from references/<repo>/<path>:<line> (MIT)`. Verification that can fail: G15-G18 each count 1; mutants P22-P25 | n/a | C6 |
| A34 | NEW r2. NET-NEW: widening the gate does not make this repo warn, and its cost is bounded. Reason: the false-positive cost is a file that mentions `SendMessage`, `agent(`, `Agent(` or `Task(` and also holds a banned phrase. Verification that can fail: `lint_harness.py .` prints `0 error(s), 0 warning(s)`; `lint_harness.py .claude` has 0 `lazy-delegation` lines (run, rev 2); the repo's Step 6 grep prints nothing (G27 = 0); `no-spawn` look-alikes (`SendMessages`, `magent(x)`, `subTask(x)`, `Tasks(x)`, `task(x)`, `agents(x)`) stay silent; mutants L17a-L17i | n/a | C6 |
| A35 | NEW r2. NET-NEW: the Step 6.2 grep is a stricter manual fallback, not the lint. Reason: no word boundaries and no gate. Verification that can fail: on `harness_delegation` the grep prints 15 lines and 5 are silent in the lint (`clean-orchestrator` 7, 8, 10; `no-spawn` 6; `agents/worker.md` 7) (run); G34 `stricter manual fallback` = 1; G38 `prints nothing` = 0 in `SKILL.md`; mutants P32b, P32c | n/a | C6 |
| A36 | NEW r2. NET-NEW: the shipped Step 6.1 clause claims exactly what the gate checks. Verification that can fail: G40 (`agent or skill file which calls`) = 1 and G39 (`which spawns workers briefs them`) = 0; mutants P28, P28b, P42; the token list in the clause equals the `SPAWN_RE` alternatives (`subagent_type`, `agentType`, `SendMessage`, `agent(`, `Agent(`, `Task(`) | n/a | C6 |
| A37 | NEW r2. NET-NEW: one test catches a wrapped CR LF phrase, an em-space or vertical-tab gap, a gate token past character 2,000, and a lint root named `.claude`. Verification that can fail: `test_lazy_delegation_in_a_dot_claude_project_with_a_late_gate_and_odd_whitespace` gives 3 hits at lines 406, 408, 409; judge mutants J04, J14, J19 each `1 failed, 8 passed` (run, `mutate_judge.py`) | n/a | C6 |
| A38 | NEW r2. NET-NEW: the re-ask is the only retry for an invalid report, so a one-shot worker is not launched a third time. Reason: the existing error policy says retry once. Verification that can fail: G35 = 1; mutant P37; live rerun on the revision 2 block: `once` 2 and 2 worker calls, `always` 2, 2, 2 (never 3) | n/a | C6 |
| A39 | NEW r2. NET-NEW: the plugin text states what the check does not do and attributes only what is adapted. Verification that can fail: G36 (`never opens it, so an invented path passes`) = 1; G37 (`"as discussed" is not from any reference`) = 1; G15 and G16 still 1 on the first paragraph; mutants P38-P41 | n/a | C6 |
| A40 | NEW r2. NET-NEW: the live support runs as shipped and its pass rule also needs a final line. Verification that can fail: `build_fixture.sh` then `run.sh` then `check_case.sh` from a clean directory gave `good` PASS, `once` PASS x2, `always` PASS x3, control PASS x2 and the additive mutant FAIL; the checker's `always` rule fails a run with no final line (the judge's P-A1 outcome) | n/a | C6 |
