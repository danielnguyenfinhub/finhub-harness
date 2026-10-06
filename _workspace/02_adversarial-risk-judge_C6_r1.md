TOTALS: UPHELD 31 / REJECTED 5 / UNVERIFIED 0 — round 1/3

# Adversarial verdict — C6 delegation contract (revision 0), round 1

- Audited file: _workspace/02_strategy-architect_C6.md (revision 0), with companions `02_strategy-architect_C6.patch` and `02_strategy-architect_C6_support/`
- Fresh context; the architect's chat was not read. No extra-round authorisation exists (round 1 of 3).
- Scratch copy: tar copy of the repo (references and .venv symlinked) with `patch -p1 < 02_strategy-architect_C6.patch` applied cleanly. Nothing in the repo or in the architect's files was edited. Scratch paths: `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/{cp6,mut.py,mutwork,live6,coldproj,redos2.py,ng.py}`.
- Rows A1-A33 are the architect's. Rows S1-S3 are added by the judge for substance findings that are not Authority List rows but are blocking under the fixed QA bar (`00_input/request.md` Pick 7), so the totals line cannot read clean while they stand.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | openhands/src/api/launch-child-conversation-client-tool.ts:17; openharness/.../coordinator_mode.py:405 | :17 "it cannot see this conversation's history — everything it needs must be in the task brief"; :405 "Workers can't see your conversation. Every prompt must be self-contained" | — |
| A2 | UPHELD | launch-child-conversation-client-tool.ts:34-35 | "the goal, the relevant file paths, the constraints, the expected deliverable, and how it should report back" | — |
| A3 | UPHELD | coordinator_mode.py:424 | :424 heading "Add a purpose statement", :426 "so workers can calibrate depth and emphasis" | — |
| A4 | UPHELD | coordinator_mode.py:411 | `Never write "based on your findings" or "based on the research."` | — |
| A5 | UPHELD | coordinator_mode.py:409 | "specific file paths, line numbers" | — |
| A6 | UPHELD | launch-child-conversation-client-tool.ts:36-38 | independent scope of siblings; one call per delegated task, never twice | — |
| A7 | UPHELD | crewai/.../task.py:153-155; project/crew_base.py:106 | `expected_output: str = Field(description=...)` with no default (required); crew_base.py:106 `expected_output: str` | — |
| A8 | UPHELD | openharness/.../autopilot/service.py:2035-2038 | "Expected output: 1. What you changed. 2. What you verified. 3. Any remaining risk or human follow-up." | — |
| A9 | UPHELD | deepseek_harness/.../tool-ralph/src/index.ts:91-103 | schema with status enum [continue, complete, blocked], summary, evidence, nextSteps, blocker | plugin renames `continue` to `partial` (A12) |
| A10 | UPHELD | index.ts:112-142 | `validateReport` switch: continue needs nextSteps and empty blocker; complete needs evidence, no nextSteps, empty blocker; blocked needs normalizedText(blocker); default throws | note: the source also rejects whitespace-padded items (`value === value.trim()`, :105); the plugin table does not state that (follow-up F2) |
| A11 | UPHELD | deepseek_harness/.../goal-round-driver/src/prompt.ts:20-22 | "Before claiming completion, gather evidence that the whole objective is achieved" | — |
| A12 | UPHELD | NET-NEW (`partial` not `continue`) | reason stated; G05 re-run on patched copy: 1; `continue` count in the pasted block: 0 (`grep -c continue` on the extracted block) | verification can fail (exact status line pinned) |
| A13 | UPHELD | crewai/.../utilities/guardrail.py:68-70; task.py:1343, :1382, :1400 | :70 `error: Error message if validation failed`; :1343 `max_attempts = self.guardrail_max_retries + 1`; :1382 `if attempt >= self.guardrail_max_retries`; :1400 error fed into `validation_error` context | — |
| A14 | UPHELD | NET-NEW (cap one) | task.py:279-280 `guardrail_max_retries ... default=3` confirmed; backlog row C6 says "re-asked once" confirmed; G10, G11 re-run: 1, 1; live: always x3 = 2, 2, 2 worker calls (mine); a "re-ask up to three times" mutant gave 4 calls (killed) | reproduced independently |
| A15 | UPHELD | coordinator_mode.py:384; :440 | :384 "Continue the same worker with SendMessage — it has the full error context"; :440 "Correcting a failure ... Continue" | — |
| A16 | UPHELD | NET-NEW (one-shot relaunch) | G12: 1; principle 4 (`orchestrator-template.md:292`) says one-shot, no `name`; live `once` x2 = 2 calls, corrected report accepted (mine) | — |
| A17 | UPHELD | NET-NEW (no new text for C34/OH1) | `sed -n 249p orchestrator-template.md` prints "Wait for the completion notifications. The main agent does not repeat a search it already delegated." (run) | — |
| A18 | UPHELD | NET-NEW ("as discussed") | `grep -rniE "as we discussed\|as discussed"` over the cited reference paths: no output (run); fixture lines 8, 11, 15 expect hits and the E9 test passes | but see F4 (attribution wording) |
| A19 | REJECTED | NET-NEW (matching rules) | named check "the Step 6 grep finds 5 of 7 fixture lines against the lint's 7" is stale. Run on the patched `lazy-orchestrator/SKILL.md`: grep prints 5 lines (7, 8, 11, 13, 14); the lint reports 9 hits on 8 lines (7, 8, 9, 11, 12, 13, 14, 15). The grep misses lines 9, 12 AND 15. | The same wrong "5 of the 7" is in Decisions item 1 and P-3. Correct to "5 of 8 hit lines (9 hits)". Also the whitespace claim is not pinned for CR, form feed, vertical tab or em-space (see S3 mutant J04). |
| A20 | REJECTED | NET-NEW (scope gate) | reason "only a file that delegates has briefs" is false for the gate as built. Run on a scratch harness: `agent("Based on your findings, fix", {schema})`, `Task(prompt: "As discussed, go ahead")`, `Agent(name: "w", prompt: "based on the research above...")`, `SendMessage(... "based on your findings, continue")` in a file that names neither token: `lint_harness: 0 error(s), 0 warning(s)`. The plugin itself says a Workflow `agent()` may omit `agentType` (`workflow-recipes.md:200`), and the contract text says the brief rule covers every `SendMessage`. | Disclosed only in the design's "Does not cover". The shipped SKILL.md Step 6.1 clause says "no file which spawns workers briefs them with a lazy-delegation phrase", which claims more than the rule checks. Fix: widen `SPAWN_RE` (add `\bagent\s*\(`, `\bTask\s*\(`, `\bAgent\s*\(`, `\bSendMessage\b`) plus a fixture, or reword E4 and the template sentence to "a file that names `subagent_type` or `agentType`" and state the limit there. |
| A21 | UPHELD | NET-NEW (WARN, exit 0) | `lint_harness.py tests/fixtures/harness_delegation` → `0 error(s), 11 warning(s)`, exit 0; E9 test asserts it; WARN→ERROR mutant killed | — |
| A22 | UPHELD | NET-NEW (linear) | my sweep on the real `LAZY_RE`/`SPAWN_RE` (`redos2.py`), n = 4,096 / 200,000 / 1,000,000, 15 hostile shapes each (long whitespace runs, ten whitespace kinds incl. NBSP, em-space, ideographic space, VT, FF, CR LF, U+2028; near-matches `based on your findin`, `as we`, `based on the researc`; wrapped real hits): worst case 0.0476 s at 1 MB for a single pattern, 0.1303 s for the mixed unicode shape; doubling n doubles time. End-to-end `lint_harness.py` on a 1.58 MB file with 80,000 hits: 0.236 s. Naive per-hit `count(…, 0, …)` mutant (J20): killed by the 100k-hit test (61 s under load, bound 20 s) | timing-based kill; margin is large |
| A23 | UPHELD | NET-NEW (repo has no hit) | Step 6 grep over `skills/*/SKILL.md .claude/skills/*/SKILL.md .claude/agents/*.md` in the patched copy: no output, rc 1 (G27 = 0); `lint_harness.py .` → `0 error(s), 0 warning(s)`; `lint_harness.py .claude` → `0 error(s), 5 warning(s)` and no `lazy-delegation` line | — |
| A24 | UPHELD | NET-NEW (block has no phrase) | G19 = 0 on the extracted copy block (31 lines); the block is byte-identical to `live/block.md` | — |
| A25 | UPHELD | NET-NEW (contract is new) | before the edit (real repo): `grep -c 'STATUS:' orchestrator-template.md` = 0; `grep -rln lazy-delegation skills tests` empty; `grep -n "without omission"` → lines 290 and 292 only | — |
| A26 | UPHELD | NET-NEW (Code only) | `sed -n 63p surfaces.md`: "Sub-agent, SendMessage, native Task and Workflow tools are not exposed in chat. Observed 2026-10-03 ... self-reported"; `sed -n 134p`: Agent row, Cowork column `unverified`; `docs/surface-verification.md` P4 exists (line 20) | — |
| A27 | UPHELD | NET-NEW (re-ask behaviour) | reproduced with Claude Code 2.1.289, own layout, scanner doubles: `good` 1 Agent call; `once` 2 and 2; `always` 2, 2, 2 (all final lines "unverified"); the block deleted (`always`) 1; "re-ask up to three times" mutant 4 | see F8: the call count alone did not kill my additive mutant |
| A28 | UPHELD | NET-NEW (cold build) | one fresh `claude -p` cold build (my domain "release-notes check", two agents, Mode C) from the patched SKILL.md: built `.claude/agents/{collector,drafter}.md` and 3 skills; `lint_harness.py .claude` → `0 error(s), 0 warning(s)`; Step 6 grep prints nothing (rc 1); `grep -l 'STATUS:'` lists the orchestrator; five brief lines (38-42), Worker report, Check before use table, re-ask-once rule present | one more run, not a rate; the model condensed the block |
| A29 | UPHELD | NET-NEW (packager unchanged) | scratch copy: `bash scripts/check-harness-refs.sh` → 40 PASS, 0 FAIL; `bash scripts/package-plugin.sh` rc 0 (lint 0/0, three archives) | — |
| A30 | UPHELD | NET-NEW (no 8-word run) | my broader sweep: all of `references/` (20.4M distinct 8-grams) against every added line of the five touched text files: 2 hits, both the attribution path string `references/openharness/src/openharness/coordinator/coordinator_mode.py` (a path, not prose). Architect's `ngram.py` semantic equivalent: 0 | — |
| A31 | UPHELD | NET-NEW (<500 lines) | `wc -l skills/finhub-harness/SKILL.md` = 200 patched (198 before) | — |
| A32 | UPHELD | references/LICENSES.md:9, :11, :12, :14 | :9 openhands MIT; :11 crewai MIT; :12 deepseek_harness MIT; :14 openharness "MIT ... upstream org unverified; pinned fork" | no autogpt_platform, no dify citation anywhere in C6 |
| A33 | UPHELD | NET-NEW (attribution lines) | G15-G18 each 1 on the patched template | wording issue F4 |
| S1 | REJECTED | gate: black | `black --check` on the patched tree: `would reformat tests/test_lint_harness.py` (rc 1). `test_lazy_delegation_regex_is_linear` has `head = '---\nname: stress\ndescription: "Stress. Use to re-run."\n---\nsubagent_type: "worker"\n'` over the pyproject `line-length = 100`; black wants it wrapped in parentheses. The real repo's two files pass black today. Design P-2 says "files unchanged". | Pick 7 requires black green. ruff, mypy --strict, pytest (8 passed), check-harness-refs (40/0), packager, Hangul (rc 1) all green. One-line fix. |
| S2 | REJECTED | Step 6.2 text (E5) | E5 says the grep ... prints nothing "(the lint check is the same test and also catches a phrase wrapped over two lines)". It is not the same test. On the delegation fixtures the E5 grep prints 5 lines the lint stays silent on (`clean-orchestrator` lines 7, 8, 10: "rebased on the research", "was discussed", "has discussed"; `no-spawn` line 6; `worker.md` line 7), because it has no `\b` word boundaries and no spawn gate. A harness with a legitimate research-and-write leaf skill cannot make the grep "print nothing". Legit text blocked and not listed. | Fix: say the grep is a stricter manual fallback (substring match, every file), so each hit is judged by hand; or add `-w`-style boundaries and say it covers all files. Drop "same test". |
| S3 | REJECTED | mutation bar | Independent mutants that pass the four new tests plus the 4 old ones and let a seeded bad brief through: J04 `\s+` → `[ \t\n ]+` (a CRLF-wrapped or em-space or vertical-tab or form-feed phrase passes); J14 spawn gate searches only the first 2,000 characters (an orchestrator whose first `subagent_type` sits past char 2,000 is not scanned; the fixtures are all tiny); J19 rule skipped when the lint root's name starts with `.` (the real target is `project/.claude`; every fixture test lints a non-dot root). One new test kills all three: a `.claude` project whose SKILL.md has 400 filler lines, then `subagent_type: "w"`, then `based on the<CR><LF>research`, `as<U+2003>discussed` and `as<VT>we discussed`; the patched lint prints 3 `lazy-delegation` warnings and each mutant prints 0 (run). | See Mutants below |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C6 | N/A text lint and prose, no pricing or returns | N/A | N/A | N/A | N/A | N/A no eval, verifier or data split touched |

The architect states this N/A with the reason in "Test plan / Quant guardrails". Accepted: the rule is a text check on harness files and nothing in C6 computes a return, a score or a split.

## Reproduced gates (patched scratch copy)

| gate | result |
|---|---|
| `pytest -q tests/test_lint_harness.py` | 8 passed |
| `ruff check` (script + test) | All checks passed |
| `black --check` (script + test) | **FAIL**: would reformat tests/test_lint_harness.py (S1) |
| `mypy --strict` (script + test) | Success: no issues found in 2 source files |
| `lint_harness.py .` / `.claude` / harness_good / harness_bad / harness_delegation | 0/0; 0 err 5 warn (no lazy line); 0/0; 24 err 4 warn; 0 err 11 warn |
| `scripts/check-harness-refs.sh` (in the copy) | 40 PASS, 0 FAIL |
| `scripts/package-plugin.sh` (in the copy) | rc 0, three archives |
| Hangul, `LC_ALL=C.UTF-8 grep -rP '[\x{AC00}-\x{D7A3}]'` over the 5 touched files + fixture dir | no output, rc 1 (required) |
| `proof.sh` G01-G33 on the patched copy | every row equals its expected value |
| size | SKILL.md 198 → 200; lint_harness.py 150 → 163; patch is 153 added non-fixture lines + 6 fixture files; effort S is honest for the script and SKILL.md, the template and tests carry most of the bulk |
| (h) real repo | `git status --short` = 0 lines, `git diff --stat` empty; `dist/` is gitignored and `git ls-files dist` = 0. The architect's disclosed `check-harness-refs.sh` run left no tracked change. |

## Lint rule attack (c, d)

- ReDoS: none. Actual regex, 4 KB / 200 KB / 1 MB, ten whitespace kinds, near-matches, 45,000 real hits: linear, worst 0.13 s at 1.66 MB. End to end 1.58 MB with 80,000 hits: 0.236 s. The line counter fix holds (J20 killed, the 100k-hit test pins `line 100005`).
- False positives (WARN, disclosed): any spawning file's own prose "write the report based on the research", "as discussed in section 3", a quoted prohibition, an inline code span: all warn (run: lines 13, 14, 17, 18 of my probe). Acceptable at WARN because Step 6.1 says "fix each WARN or say why it stays".
- False negatives: paraphrase ("based upon your findings", "based on what you found", "using the findings from earlier", "as previously discussed", "per our discussion"), markup in the phrase (`based on **your** findings`), "based on your earlier findings", singular "based on the finding", non-breaking hyphen: all silent. The design lists paraphrase and markup; "earlier", singular and "based upon" are the same class.
- Gate bypass: A20 (Workflow `agent()` without `agentType`, `Task(`, `Agent(name:, prompt:)` without `subagent_type`, `SendMessage`-only). Only `.claude/agents/*.md`, `skills/*/SKILL.md` and nested `skills/**/SKILL.md` are read: a brief kept in `skills/x/references/*.md` is never scanned (stated only as an aside in Does not cover).
- Severity: WARN exits 0; Step 6.1 says fix or explain, so a WARN is acted on in the build flow (and in the packager it only prints).
- (d) Step 6.2 regex form: `lint_harness.py .` is 0/0 on the patched repo, so SKILL.md does not trip its own rule; the pasted copy block carries no phrase (G19). The E5 grep itself is S2.

## Contract text and protocol attack (a, b, e)

Live boundary runs, Claude Code 2.1.289, my own scanner doubles, one run each, Mode C one-shot, orchestrator = the architect's fixture with the byte-identical block:

| double | worker calls | outcome |
|---|---|---|
| `EVIDENCE: none` / `N/A` / `done` / whitespace only | 2 each | re-asked once, unverified (the model read "one item you can open or re-run", not "at least one item") |
| complete + valid evidence + `NEXT STEPS: none`, `BLOCKER: none` | 1 | accepted (the `none` lines were not treated as a BLOCKER) |
| complete + evidence + real BLOCKER | 2 | re-asked, unverified |
| `STATUS: completed` | 2 | re-asked |
| `STATUS: Complete` (capital) | 1 | accepted (case unspecified in the text) |
| two STATUS lines (blocked, complete) | 2 | unverified |
| partial with empty NEXT STEPS | 2 | re-asked |
| blocked, `BLOCKER: something went wrong` | 2 | re-asked, then accepted a later blocked report |
| no STATUS line | 2 | unverified |
| complete, evidence path that does not exist | 1 | unverified at once, no re-ask: the orchestrator opened the path on its own; the contract text does not tell it to |

Reading: the fallback "recorded as unverified, nothing used as fact" is reachable and unambiguous in Mode C (the only branch exercised). The mechanical rule is weaker than the behaviour: the table says "at least one item", a literal reader accepts `EVIDENCE: done`; the model rejected it by judgement. A made-up path with the right shape passes unless the orchestrator happens to open it. The shipped Limits paragraph says only "Evidence that is present can still be wrong"; it does not say the check never opens an item or that an invented path passes (observed 1 of 3 by the architect). The design file states it plainly, the plugin text does not (F1). No sentence in the plugin text claims verification; E3 "prompt quality plus a check, not a guarantee" is accurate.

Not exercised live by anyone: the `SendMessage` branch (Mode B), the Workflow `agent()` branch (Mode A). Template A agents return `schema` objects (`orchestrator-template.md:33`, `:73`), but the contract's report is five text lines and the block never says how STATUS maps onto a schema or where the `if` goes; that branch is under-specified, not only untested (F1). Chat has no sub-agent tool (self-reported) and Cowork is unverified: both stated in `surfaces.md` row 8 and in the design. The 1-cold-build limit is stated in the design only; my second cold build agrees with theirs.

## Mutants (f): 18 independent, each verified a real single-occurrence substitution (`mut.py` asserts count == 1 and a changed file; fresh tar copy and fresh pytest process each; kill test = `tests/test_lint_harness.py`)

Killed (10): J05 `last = m.end()`; J06 line count to `m.end()`; J09 gate `search` → `match`; J10 hit text lower-cased; J11 added `as agreed` arm; J12 only the first 100,000 characters scanned; J13 agent files skipped; J15 one warning per distinct phrase per file; J16 cap 50 warnings per file; J18 gate boundary `(?<![A-Za-z])`. Also J20 naive per-hit count (61 s, timing kill).

Survived (non-equivalent), exact kill test:

| id | mutation | effect | kill test |
|---|---|---|---|
| J04 | `\s+` → `[ \t\n ]+` in all three gaps | **bad brief passes** when wrapped with CRLF, or separated by em-space, VT or FF | fixture line `based on the<CR><LF>research` and `as<U+2003>discussed`, expect hits (S3) |
| J14 | gate reads only `text[:2000]` | **bad brief passes** in an orchestrator whose first spawn token is past char 2,000 | fixture with 400 filler lines before `subagent_type` (S3) |
| J19 | rule skipped when `root.name` starts with `.` | **bad brief passes** on the real `…/.claude` target | lint a copy of the delegation fixture under a directory named `.claude` (S3) |
| J01 | `on\s+` → `on\s*` | false positive `based onthe research` | clean fixture line `based onthe research`, expect silent (follow-up) |
| J02 | `(?:your\|the)` + `our` | false positive `based on our findings` | same pattern (follow-up) |
| J03 | `findings` → `findings?` | false positive `based on the finding` | same pattern (follow-up) |
| J07 | `ln, last = 0, 1` | line off by one when a file starts with a newline | nested fixture starting with a blank line (follow-up, message only) |
| J08 | gate compiled IGNORECASE | false positive on `AGENTTYPE` prose | fixture `no-spawn` line `AgentType` (follow-up) |
| P-A1 | (prose, additive) a new sentence in the block "If EVIDENCE is empty, accept the report anyway." | passes every G grep and the whole-line pins, because they catch edits not additions; live: 1 Agent + 1 SendMessage, run did not conclude, the model ignored the sentence | not killable by text pins; the live pass rule must also check the final line, see F8 |

Discarded as equivalent: J17 (tautology `if ln or True`).

## Blocking vs follow-up

Blocking (round 2 must fix): A19 (stale 5-of-7), A20 (scope claim and E4 overclaim), S1 (black red), S2 (E5 "same test" and over-broad grep), S3 (J04, J14, J19 survivors).

Follow-up (do not block):
- F1 Limits paragraph (`orchestrator-template.md`): add that the check confirms an item is present, never opens it, an invented path passes (observed 1 in 3), and that the `SendMessage` and Workflow branches are untested; say how a Mode A `schema` result carries STATUS.
- F2 Report grammar: case of the status word, two STATUS lines, whitespace-padded items, literal `none` in NEXT STEPS or BLOCKER are not specified (the live model chose sensibly; the DeepSeek source rejects padded items, :105).
- F3 Interaction with the existing "retry once" error policy (SKILL.md Error policy; Template C error table): a failed one-shot worker can now be launched three times; say whether the re-ask counts as that retry.
- F4 Attribution: the sentence listing three phrases carries `adapted from` OpenHarness and OpenHands, but "as discussed" is net-new (A18).
- F5 `02_strategy-architect_C6_support/live/` omits `.claude/agents/`, `.claude/skills/fixture-orchestrator/` and `_workspace/note.txt`; `runcase.sh` fails as shipped, the layout had to be inferred.
- F6 Line numbers count `\n` only; the older loop uses `splitlines()`; form feed, VT, U+2028 skew the two.
- F7 `grep -l 'STATUS:'` proves the token, not the contract; briefs in `references/*.md` are not scanned.
- F8 The live pass rule counts `Agent`+`SendMessage` calls; my additive mutant gave 2 total and was not killed by that. Add "final line is unverified, or accepted with non-empty second EVIDENCE" as the architect's own rule already says.
- F9 `surfaces.md` row 8 is a statement, not a runnable check.

## Message to orchestrator

TOTALS: UPHELD 31 / REJECTED 5 / UNVERIFIED 0 — round 1/3. Relay to strategy-architect: A19, A20, S1, S2, S3 (details above). Residual follow-ups F1-F9.
