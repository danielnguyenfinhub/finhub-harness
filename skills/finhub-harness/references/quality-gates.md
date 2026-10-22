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

### 1-4. Check every cite mechanically before the audit

A cite to a file that is not there, or to a line past its end, is a wrong citation that a script can find in seconds, before a judge spends a round on it. `scripts/cite_check.py` in the finhub-harness skill directory reads one or more documents and checks every `references/<sub>/<path>:<line>` and `references/<sub>/<path>:<start>-<end>` cite, and any `, :<n>`, `; :<n>` or ` and :<n>` straight after one, against the commit the project pins for that submodule. Run it from the project root: `python3 <finhub-harness skill dir>/scripts/cite_check.py <design or port map> [...]`.

| Id | Rule |
|----|------|
| CC1 | The architect runs it on the design before saying the design is ready and fixes every `BAD` line. The judge runs it on the same file before the first claim and copies its `SUMMARY:` line into the verdict body. The architect's and the judge's agent files, or the skills they are told to read, say so. |
| CC2 | A row whose cite the script prints as `BAD` is REJECTED with the printed reason and `cause: judgment-gap` (section 3-8: the design names the file). A judge who opens the cited line and finds the script wrong rules the row UNVERIFIED and quotes the script's line instead, so a false `BAD` never fails a correct row. A cite the script passes is still opened at ±5 lines, because a line in range is not a line that supports the claim. |
| CC3 | Exit 0: every cite exists at the pin and is in range. Exit 4: at least one `BAD` line (a missing file, a line below 1, a line number of more than 9 digits, an inverted range, a line past the end, a directory, a symlink, a nested submodule, a binary file, an unknown submodule, or a path that climbs out of the submodule or is not normalised). Exit 3: no `BAD` line, but something could not be read (no `.gitmodules`, no index, no `git`, no gitlink, a submodule not checked out, its pin missing from a shallow clone, or a cited blob missing from a partial clone); those cites count as `unavailable`, never as checked, and their rows are UNVERIFIED unless the judge can open them. Exit 2: a bad call or an unreadable document. Any other exit is a crash and is not a pass. |
| CC4 | The cited file is read from the pinned commit through git, not from the working tree and never from the network: every git call runs with `protocol.allow=never`, and with `protocol.<name>.allow=never` for file, git, ssh, http, https and ext, given on git's command line, which outranks a user's config such as `protocol.file.allow=always`; it also sets `GIT_NO_LAZY_FETCH=1`, which not every git honours. So a partial clone that lacks a blob gives exit 3 instead of a fetch. When the checkout has moved off the pin the script prints a `NOTICE` and still checks the pin. The path text of a document is only looked up in the pin's file list; it never reaches git's arguments or a shell. Nothing is hashed: after a re-pin, a cite whose line still exists but now holds other text passes, and only the judge's reading of the line catches it. |
| CC5 | After a cite, `, :<n>`, `; :<n>`, ` and :<n>` and a line list such as `:3-5, 8-10` (a comma, then a number or a range) are read as more lines of the same file. Every token that starts with `references/` and holds a colon followed by a digit is checked, `BAD` or `SKIPPED` with a reason; none is dropped silently. A file the project itself tracks under `references/` (such as `references/LICENSES.md`) is checked against its index entry. `SKIPPED` is printed as `SKIPPED` and counted, never passed: a placeholder such as `:<line>`, a path holding a character the grammar does not read before the colon (`*`, a backtick, a quote, `|`, `<`, `>`, `,` or `;`), and a one-part `references/<file>` the project does not track (a skill-relative path; write it from the project root). Not seen at all: a path with a space, a line given in prose (`at :20`), a file named without the `references/` prefix and any other file of the project (`skills/...:12`). |

Where the script is: with the finhub-harness plugin installed, the plugin's copy in this skill's `scripts/` directory, run by its path from the project root; a harness that must work without the plugin copies `cite_check.py` into its own `scripts/` and runs that copy. Where no shell runs (chat without code execution, Cowork without a terminal) the script cannot run, and whether it works there is unverified: the architect says `cite_check not run (no shell)`, the judge writes `SUMMARY: cite_check not run (no shell)` and opens every line by hand as before; with neither copy present, both write `(no script)` instead of `(no shell)`. (Reading the cited bytes at a recorded commit through git, and the three range bounds, adapted from references/repository_harness/.agents/skills/onboard-repository/scripts/emit_evidence_bundle.py:63-86 (MIT); the cite grammar, the pin lookup, the exit codes and rules CC1-CC5 are new here.)

---

## 2. Fresh-context adversarial audit

The judge is a separate agent that shares nothing with the architect except the design file and the cited lines. This is adversarial verification: a scripted audit of the list catches mis-citations that a persona reviewer, reading the same reasoning as the author, would wave through.

### 2-1. Isolation rules

- The judge reads only the design file (the Authority List, plus slice text where a claim needs its context) and opens every cited line itself, at ±5 lines, wider when a claim names a whole function.
- The judge ignores rationale prose and chat messages that argue a position.
- The judge never edits the architect's file. Its only artefact is the verdict.
- The judge changes a verdict only for new evidence, meaning a line it can open. A louder argument is not evidence.
- The judge defaults to doubt: a citation off by more than a few lines, in a different function, or needing inference to support the claim is not UPHELD.
- Doubt decides each claim of an audit that was assigned; it never decides whether an audit runs, how many rounds it gets past the cap in 2-4, or which further gate (another judge or a QA agent) to add (section 3-10). A judge that thinks another gate is needed writes one sentence naming the unresolved risk in the body of its verdict and carries on. (adapted from references/openrig/packages/daemon/specs/agents/shared/skills/pods/review-team/SKILL.md:29-31 (Apache-2.0))

### 2-2. Verdict schema

The verdict file starts with a totals line so the orchestrator can gate on it without parsing tables. The second line is `CANDIDATE:`, the id of the design file the judge read (section 3-7), and the third is `CARRIED:`. Format from `.claude/skills/adversarial-audit/references/verdict-schema.md`:

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

A REJECTED row also carries one cause tag, set by rule T3 of section 3-8: `cause: judgment-gap` when the cited file is one the design lists as an input and the architect could read it, `cause: context-gap` otherwise. Doubt decides whether a claim is accepted, never the cause. (adapted from references/openrig/docs/reference/wave-sdlc.md:58-62 (Apache-2.0))

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

Domains other than trading need their own fixed rows. The pattern is the table, not the six topics: list the ways a result in your domain can be confidently wrong, and make each one a row the judge must rule on every time. The cost statement of section 3-11 is a fixed row of the same kind, one ruling per design.

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

The first line of every slice QA report starts with `RESULT: PASS` or `RESULT: FAIL`, so the orchestrator reads it without parsing. PASS requires all of: every boundary matches, all gate commands exit 0, the proof command produces the expected output, and the compliance sweep is clean. A command that cannot run is a FAIL with the missing tool named; QA never marks PASS by skipping. The next two lines are `CANDIDATE:` and `CARRIED:` (section 3-7): the PASS belongs to the tree named there and to no other. Every check behind that line is a command with its observed output, and PASS also needs at least one recorded adversarial probe (`qa-agent-guide.md` section 7). The PASS also needs the drift row of section 3-8, with `undeclared=-`, `flags=0` and the Base line's `excl=`; a missing or wrong drift row is a refusal (exit 4) like any other. The PASS also needs the `RIGOR:` line of section 3-10 on line 5, and `rigor_check.py` must exit 0 on the report.

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

A green gate only proves the tests pass. It does not prove the tests can fail. For every safety-critical behaviour, QA deliberately breaks the code and confirms that the test written for that behaviour fails, at the assertion written for it. A run that fails for any other reason proves nothing about the test. (adapted from references/openrig/packages/test-system/ci/result.mjs:33-34 (Apache-2.0))

Procedure:

1. Copy the tree into a scratch directory outside it with `tar`, so `.gitignore`, `skills/` and `.claude/` come along (tests read them, and a copy without them fails for the wrong reason). Leave `.venv`, `.git`, `dist` and `__pycache__` out of the copy (a copy that includes a virtual environment can fill the disk), and give the copy a read-only link to the pinned `references/` instead of a second copy; a mutant never targets `references/`. Take the copy from the tree whose `candidate_id.py id` equals the `Candidate:` line of your brief, make a new copy for each mutant and delete it after the row is written. Everything you write (`spec.json`, the three reports) goes into a work directory outside the tree too: a stray file inside the tree under review moves its candidate id. Never edit or delete anything in the repo under review.
2. Confirm the import path actually loads the copy. In the slice 9 record, a first attempt hit a comment line and was a silent no-op (`22 passed`); only redoing it against the real call produced a kill. Show that the diff between the copy and the original is non-empty and is the change the spec states.
3. Before the first run of a mutant, write its spec and save it: `id`, `file` (the code under test: never the module named in `test`, and never `conftest.py`, because the mutation goes into the code under test and never into the test that is meant to catch it; `classify` exits 2 for such a spec), `old`, `new`, `test` (the one test id the change is meant to break) and `sig` (the distinctive text of the assertion that should trip, such as an expected value; at least 6 characters, and not the bare word `assert` or `AssertionError`). Record `sha256sum` of the spec file in the report. Choosing the mutant after seeing which test fails is not a mutation check. For a mutant that the design's Test plan lists, copy `test` and `sig` from the design's row byte for byte, record the spec's sha256 next to that row, and show that every field equals the design's row. A mutant you add yourself is labelled "not pre-registered" in the report and never replaces a design row.
4. Apply one mutation at a time (drop a check, invert a condition, remove a cleanup).
5. Run three legs, in this order, each in a new process with the same command and the same test files (no `-x`: a stopped run reports fewer tests and is void), each writing its own report and starting from no report file: the untouched copy (`before`), the copy with the change (`mutant`), the copy after the file is put back and `cmp` against the original is empty (`after`). Then run `classify` and paste its whole output as the mutant's row.

```bash
REPO=/path/to/the/tree/named/on/your/Candidate/line     # the tree under review; nothing is written into it
W=$(mktemp -d)                                           # outside "$REPO": spec.json and the three reports
COPY=$(mktemp -d)                                        # outside "$REPO": a new one for each mutant
tar -C "$REPO" --exclude=./.venv --exclude=./.git --exclude=./dist --exclude=./references \
    --exclude=__pycache__ -cf - . | tar -C "$COPY" -xf -
ln -s "$REPO/references" "$COPY/references"              # read-only use; no mutant targets it
# write "$W/spec.json" now, then:
rm -f "$W"/before.xml "$W"/mutant.xml "$W"/after.xml; sha256sum "$W/spec.json"
(cd "$COPY" && python -B -m pytest -p no:cacheprovider --junitxml="$W/before.xml" tests/test_guard.py)
# apply the change in "$COPY"; show the diff against "$REPO"
(cd "$COPY" && timeout 300 python -B -m pytest -p no:cacheprovider --junitxml="$W/mutant.xml" tests/test_guard.py)
# put the file back; cmp it against "$REPO"
(cd "$COPY" && python -B -m pytest -p no:cacheprovider --junitxml="$W/after.xml" tests/test_guard.py)
python3 "$REPO/skills/finhub-harness/scripts/mutant_gate.py" classify "$W/spec.json" \
    --before "$W/before.xml" --mutant "$W/mutant.xml" --after "$W/after.xml"
rm -rf "$COPY"                                           # after the row is written
```

Run `classify` from the unmutated script in `$REPO`, never from the copy. Use the same Python that runs the repo's own gates (the virtual environment is not copied).

6. Compare the repo file to the original afterwards (`cmp`) to prove the repo was untouched.

The script prints one `STATE:` per mutant and exits 0 only for CAUGHT. The rules, with the state each one produces (the healthy-faulted-healthy sandwich and its refusal of a startup error, timeout or unrelated failure are adapted from references/openrig/docs/as-built/test-layers.md:214-226 and :324-326 (Apache-2.0)):

| Id | Rule |
|----|------|
| M1 | The spec is written and hashed before the first leg. `classify` prints the spec's sha256 and returns `ORDER` when the spec file is newer than the `before` run. It exits 2 for a spec whose `file` is the module named in `test` or is `conftest.py`: the mutation goes into the code under test, never into the test that is meant to catch it. |
| M2 | One mutant is three legs: before, mutant, after. A leg whose report is missing or unreadable (a timeout, a kill, a crash) is not a result: a missing `mutant` report is `INVALID`, a missing baseline report is `BASELINE-RED`. All three legs must run exactly the tests of the `before` leg: the same set of test ids, not only the same number (a different selection of equal size is `INVALID` for the `mutant` leg and `BASELINE-RED` for the `after` leg). |
| M3 | CAUGHT needs all of: the `test` of the spec ran and failed in the `mutant` leg; its first error line is an assertion (`assert ...`, `AssertionError` or `Failed: DID NOT RAISE`) and the error lines contain `sig`; the report holds no error element. Other tests may fail as well. Anything else is `INVALID`: a collection, import or syntax error, a crash or a timeout, the intended test passing while another fails, a different exception in the intended test, a missing signature. (adapted from references/openrig/packages/test-system/ci/result.mjs:50-65 (Apache-2.0)) |
| M4 | `before` and `after` must each show the intended test passing with no failure and no error, or the state is `BASELINE-RED`. A red `before` voids the mutant run; a red `after` means the file was not put back or a test depends on run order. |
| M5 | The reports must be in time order: spec file, `before`, `mutant`, `after`, and a leg must end (its start plus the suite time pytest wrote) no later than the next leg starts. Otherwise `ORDER`. For a mutant the design's Test plan lists, the file time is the only mechanical guard on your own `sig`; the design's row is the other (step 3). |
| M6 | `SURVIVED` (every test passed with the change in place, and the sandwich holds) is a FAIL when the mutant is not equivalent, as before; the equivalence argument stays in the report. |
| M7 | `INVALID`, `BASELINE-RED` and `ORDER` are void: neither a kill nor a survivor. Keep the row and its output, fix the mutant or the environment, write a new spec and run again. A behaviour whose mutants are all void is unproven, and the report is FAIL. Only a `mutant:` row that ends in `CAUGHT` or `SURVIVED` counts as the adversarial probe of section 3-1. |
| M8 | A mutant result belongs to the candidate it ran on (rule C4). After a builder fix, run every mutant again on the new candidate; a state taken from an earlier candidate goes on the `CARRIED:` line and never licenses a PASS. |

Does not cover:

- Anything that is not pytest. `classify` reads pytest JUnit files. Supported: pytest 6.2.5 to 9.1.1 on Python 3.11 (measured); nothing is claimed below pytest 6.2 (5.4.3 gave error elements in the baseline). The script itself needs Python 3.9 or later. For a shell script, a grep gate or another runner, the same sandwich is done by hand, and the failing run must show the pinned text of the check it was written to break; a startup error or timeout is still not a catch.
- Prose mutants without a pin. Where a test pins a sentence (a test that asserts the sentence is in the file), the pin test is the intended assertion: its id is `test` and the pinned phrase is in `sig`. Prose that no test pins has no assertion to catch the change, so its proof is the design's greps, not this rule.
- Equivalent mutants. They still need a written argument (rule M6); `classify` reports them as `SURVIVED`.
- Flaky tests. A flaky test can turn a leg red or make a catch intermittent. M4 catches some of it. Section 3-5 still applies.
- A test that asserts the wrong thing. `CAUGHT` shows that the test noticed this change at a place the QA agent named; it does not show that the assertion is a good one, or that `sig` was well chosen.
- A QA agent that picks `sig` after reading the failure. For a mutant that the design pre-registered, copying `test` and `sig` from the design's row (step 3) is the answer; for a mutant the QA agent adds, only the spec file's time guards against it (rule M1), and a file time can be set by hand. The script is there to catch accidents, not to detect fraud.
- Failure shapes that are never a catch: `--tb=native` (the failure text has no `E` lines, so the run is `INVALID`), a failing `pytest.warns` (`Failed: DID NOT WARN` is not in the allow-list, so `INVALID`), and `pytest.fail`. A test id whose parameter ids contain `::` cannot be matched to the report (the run ends `BASELINE-RED`, which fails closed). A `\` in the `test` path is read as `/`; other Windows path forms are not normalised.
- Naive timestamps. pytest 6 and 7 write the suite start without a time zone; `classify` reads it in its own time zone, so a different `TZ` between the runs and `classify` can give `ORDER` or let the file-time check pass wrongly. Run the legs and `classify` in one environment.
- The mutation tables that builders keep inside their own tests (for example `tests/test_candidate_id.py`) judge a kill by a named check failing; this rule does not change them.

Real mutants that survived on the first pass of this build. Each was a green gate with a weak test; the builder fixed the tests and QA re-ran the mutants until all were killed (source: first-pass defects as restated in `_workspace/03_boundary-qa_slice8.md`, `..._slice9.md`, `..._slice11.md` and `_workspace/04_boundary-qa_report.md`):

| slice | surviving mutant(s) | what was untested |
|---|---|---|
| 8 | M2: drop `stop.set()` in `finally`. M3: drop the reader join loop. M4: close both pipes before join. | Test strength: nothing proved an abandoned stream releases its reader threads or pipes, or that teardown cannot hang. Killed afterwards by `test_abandoned_stream_releases_readers` and `test_abandoned_stream_with_escaped_child_does_not_hang`. |
| 9 | M7a: replace every `terminate()`/`kill()` in `close()` with `pass`. M7b: drop the `finally` kill. | The kill path was never reached: the stub server exited on stdin EOF, so no test forced `close()` past EOF. Fixed by adding `--ignore-eof` and `--ignore-term` stub modes, so the terminate and kill branches are provably reached. The same pass found environment scrubbing unasserted (M9 killed afterwards). |
| 11 | D1: empty phrase accepted. D2: non-string `eval.type` crashed with `TypeError`. S1: empty ground could pass. S2: workspace cleanup only on success. | D1 and D2 were loader defects, and S1 and S2 were test gaps. After the retry all four were killed by `test_empty_phrase_rejected`, `test_non_string_eval_type_is_valueerror`, `test_empty_ground_cannot_pass` and `test_workspace_cleaned_after_crash`. |

The kills in this table were recorded under the earlier wording (a named test fails) and were not re-run under rule M3.

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
2. Before QA runs again, the orchestrator moves the FAIL report to the same name with `_r<k>` added before `.md`, where `k` is one more than the highest `n` of the unit's existing `_r<n>` reports (1 when it has none; only names with digits after `_r` count, so a `_rerun` file does not), and stops if that name is taken. QA re-checks every previously listed defect plus a full gate run and writes its new report under the usual name, so the name the commit step checks holds the latest attempt and every earlier attempt keeps its own file.
3. If the second run is still FAIL, stop building later slices. Record the failed slice, the verbatim failing output, the path of every kept report and the open question in the final report's Gaps section. Do not mark it PASS and do not start the next slice on top of it.

A report written after a FAIL names each kept report on a line of its own, after its fifth line and before its first heading, never as a numbered item: `Earlier attempts: <path> | failed: <the PASS condition or defect row it failed on> | changed: <what the builder changed, and the path of its retry report> | reason: <the cause a command showed, or unknown>`. The later PASS shows that the work passes now; it does not explain the earlier failure. So `reason:` names the command and output that showed the cause, or reads `unknown`, and never says flaky, environment or infrastructure without that command and output. A kept report is history and not evidence for the new candidate: its own `CANDIDATE:` line goes stale when the builder changes the tree, a check reused from it goes on `CARRIED:` (rule C4), so a PASS that licenses a commit still re-runs every check and every mutant (rule M8), and every attempt carries the unit's one `BASE:` line (section 3-8). The step that checks reports passes only the report under the usual name to `candidate_id.py check`, `finding_tags.py check` and `rigor_check.py`; kept reports are never passed to them, because `rigor_check.py` refuses any report that is not `RESULT: PASS`. Where no shell runs, the orchestrator writes the earlier report's text into the `_r<k>` file with its file tool before the retry; whether that file survives into a new conversation is unverified (`state-ledger.md` section 6). (adapted from references/paperclip/.agents/skills/verify-paperclip/SKILL.md:192 (MIT))

In this build slices 8, 9 and 11 failed once on test strength or loader defects and passed after the single retry; slice 10 passed first time. The first-pass FAIL reports were overwritten by the retry reports, so the first-pass detail above comes from the retry reports' notes.

### 3-7. The verdict names the candidate it judged

A PASS is a statement about one tree. If the tree is not named, an edit made after the verdict leaves the PASS standing over files nobody checked, and the commit that follows rests on it. A QA report and a judge verdict therefore carry a `CANDIDATE:` line directly under their first line (`RESULT:` for QA, `TOTALS:` for the judge), then a `CARRIED:` line, and whoever is about to act on the verdict compares that line with the tree in front of them first.

```text
RESULT: PASS
CANDIDATE: git:1a2b3c4d5e6f+0f1e2d3c4b5a6978 n=214 excludes=_workspace/
CARRIED: -
```

`scripts/candidate_id.py` computes the id and makes the comparison (standard library only, no network, exit 0 / 2 / 3 with the meaning they have in `state_ledger.py`). Its `id` command prints the line to paste, and its `check` command takes a verdict file and prints `STATE: current` or `STATE: STALE` with the reason. If the session that runs the harness does not have the plugin, copy the script into the harness the way `state-ledger.md` section 4 copies `state_ledger.py`.

| Id | Rule |
|----|------|
| C1 | The line comes from `candidate_id.py id`, never from memory or by hand. `git:<head12>+<tree16>` names a git worktree: the commit, plus the content of every tracked file and of every untracked file that `.gitignore` does not hide. `files:<tree16>` with a `paths=` field names the listed files or directories (a patch file, a design document) and is the kind to use outside git. `unverified (<reason>)` is written where no shell runs or `id` exits 3. |
| C2 | `excludes=` lists what the id leaves out. The default is `_workspace/`, so the reports and verdicts a team writes there do not change the id they carry. Add an exclude only for output that the reviewed work itself produces. `check` takes the list from the record and prints it as its `EXCLUDES:` line; the orchestrator compares that line with `_workspace/` (or the list the harness declares) and refuses a verdict whose list differs, because a wider list hides files from the id. Compare entry by entry and ignore a trailing slash: the script prints the default as `_workspace/` and every entry you add without one (`--exclude .claude-flow/` is printed `.claude-flow`). The default belongs to the `git:` kind only; a `files:` id lists exactly the paths it is given, so a design file under `_workspace/` is covered. |
| C3 | The reviewer computes the id when it starts and again just before it writes. A start id that differs from the one in its brief makes the first line `RESULT: FAIL — candidate differs from the brief`; an id that moved during the run makes it `RESULT: FAIL — candidate moved during QA`. A judge does the same with `TOTALS:` and the design file. |
| C4 | One verdict covers one candidate. A check that was not run on this candidate is named on `CARRIED:` with the candidate it was run on, and the line reads `-` when there is none. A QA verdict with anything but `-` there never licenses a commit. A judge verdict may carry Authority List rows whose text is unchanged from the earlier round, and says which. |
| C5 | Before anyone acts on a verdict (commits, pushes, opens a pull request, ships, starts the phase that consumes it, resumes a run), run `check` on the verdict file. Exit 0: go on. Exit 3: the verdict is stale, unbound or unverified, and its first line is void for this tree. Exit 2: the call was wrong; fix the call. A generated orchestrator with an error table gives the exit 3 its own row (a verdict whose `check` exits 3 is treated as not given), besides the step that checks reports. |
| C6 | A stale verdict is replaced by a new verdict on the new candidate, not argued away. A narrower check made after a small change is a new report with its own `CANDIDATE:` and a `CARRIED:` naming what it did not run; it may guide the builder, and under C4 it does not license a commit. |
| C7 | The commit that holds the judged tree changes the commit part of the id. `check --tree-only` ignores that part and passes while the files are unchanged; with an empty `git status --short` after the commit, a push or a pull request can show which verdict it rests on. The plain `check` fails after the commit, so one verdict licenses one commit. |
| C8 | A run that only shows the gate commands start (a smoke or dry run) is a FAIL under 3-1 whatever id it carries, never a PASS. |

In a harness with a state ledger (`state-ledger.md`), a verdict file is one handoff row, and `complete` there means its headings exist, not that it is current. The orchestrator runs `check` on the file before it starts the phase that consumes it. Exit 3 means that verdict phase has to be earned on the current tree; rule R7 of the ledger still applies, so the orchestrator tells the user the verdict is stale and runs the phase when they agree.

Does not cover:

- The id shows what was on disk when the line was computed. It does not show that the reviewer opened every file in it: a verdict over 214 files may rest on ten.
- The tree can change between the check and the action that follows it. The check shortens that gap and does not close it.
- Ignored files, the contents of a submodule (only its pinned commit), what a symlink points at, file times and the git configuration in force are outside the id. A tracked file replaced by a directory, an unreadable file, an untracked directory the user cannot read, a file over the size limit or a symlinked directory on a path makes the id partial, and `id` and `check` then exit 3 instead of guessing.
- The id is byte exact. A change of line endings or a byte order mark changes it, and the same commit checked out under a different `core.autocrlf` setting gives a different id.
- Sixteen hex digits notice an accidental change. A verdict file is plain text that anyone can edit, so the line is not tamper evidence.
- A gate can refuse a dirty tree outright. This id accepts one and binds the verdict to its content, because the team reviews work before it is committed: untracked files count, ignored ones do not, and `--tree-only` passing proves nothing about a file the commit left out unless `git status --short` is also empty.
- Chat and Cowork have no git and no shell. `unverified` cannot be compared, so the consumer treats any edit made after the verdict as voiding it and says so to the user.
- `check` reads the `CANDIDATE:` line and nothing else in the file: a stale FAIL is as void as a stale PASS, and a downstream phase that already read a stale file is not marked out of date.
- A `CANDIDATE:` line copied from the brief without running `id` matches like a computed one, so `check` shows that the tree is unchanged since the brief, not that the reviewer looked at it; a `RESULT: FAIL` report checks `current` too.
- Of a submodule only the staged pin is read, not the commit checked out inside it: a different checked-out commit under the same pin does not move the id.
- A file hidden by an untracked `.gitignore`, including one that hides itself, is invisible to the id, although a test or lint run still reads it.
- `_workspace/` is outside the default id, so the design file QA judged against and the report itself can change without moving a git id.

(Binding a verdict to the exact commit and refusing a mismatch, adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0). A run that fails when the commit moves under it, adapted from references/openrig/scripts/gate-lane.mjs:151-154 (Apache-2.0). An id that states what it covers, adapted from references/openrig/docs/reference/sdlc-conventions.md:157-173 (Apache-2.0). A verdict that is used once, adapted from references/openrig/scripts/gate-lane-consume.mjs:29-31 (Apache-2.0). Evidence taken from an earlier candidate says so, adapted from references/openrig/CHANGELOG.md:591 (Apache-2.0).)

---

### 3-8. Cause tags and the drift row

Two additions to what QA and the judge record, adapted from a reviewer brief that asks whether built work still matches what was asked, and why each miss happened (adapted from references/openrig/docs/reference/wave-sdlc.md:54-62 (Apache-2.0)). Both are plain text, checked by `scripts/finding_tags.py check FILE`. The tag names a cause and the drift row names paths; neither changes what counts as a defect.

**Cause.** Each finding recorded as a miss carries exactly one tag, `cause: context-gap` or `cause: judgment-gap`. `context-gap`: the fact the failing step needed was not in anything it was handed (the brief, the design, the routed files); the fix goes into the brief, the design or the route that should have carried it. `judgment-gap`: the fact was in what the step was handed and the call was still wrong; the fix is a check that would have caught the call.

The cause is set by a rule on the record's evidence, never by doubt:

- a judge REJECTED row (T3): `judgment-gap` when the cited file is one the design lists as an input and the architect could read it; `context-gap` when the needed file was not routed or is not in `references/`;
- a QA defect row (T2): `judgment-gap` when the design or the brief states the requirement the defect breaks and the row cites its line; `context-gap` when no such line can be cited;
- a LESSON line (T1): `judgment-gap` when its `evidence:` cites a line of something the failing step was handed; `context-gap` otherwise.

Doubt decides whether a claim is accepted or a defect is raised. It never decides the cause.

| Id | Rule |
|----|------|
| T1 | Each `LESSON` line of an evolve report has exactly one cause tag, after the `layer:` field (`skills/finhub-harness-evolve/SKILL.md`, Phase 2). |
| T2 | Each defect row of a QA report has exactly one cause tag on its own line and starts with a plain `file:line` location (a location in bold or backticks, and a tag on the continuation line of a wrapped row, are refused). The Defects route is an allow-list and fails closed. **First-word rule:** outside a code fence, a line whose first word is `defect` or `defects`, case ignored, with quote markers, heading marks, list marks, markup, HTML tags, spaces and tabs before it skipped (a longer or hyphenated word such as `defect-row` is another word), is exactly one of three canonical forms or the record is refused (exit 4, the message names the line and `non-canonical Defects line`): the heading `## Defects` or `### Defects` at column 0; a defect row `- defect: file:line ...` at column 0 with one space after the colon; the none line `Defects: none`. Every other spelling is refused, whatever its verdict: ` ## Defects`, `##Defects`, `# Defects`, `## Defects (round 2)`, `## Defects found`, `## Defect`, `**Defects**`, `*Defects*`, a plain `Defects` or `Defects:` line, a quoted, tab-indented, HTML-wrapped, setext, link-wrapped or code-wrapped heading, `* defect:`, `| defect:`, `-defect:`, `1. defect:`. The text is read after entities, tags, format and combining characters, compatibility forms and the `FOLD_MAP` look-alikes are folded (T3), so an entity-encoded `## Defe&#99;ts` is the canonical heading. **Section rule:** a Defects section opens at a canonical heading, or at an ATX heading, a whole-line bold title, an HTML heading or bold, or a setext title whose text names defects after its first word (`## Known defects`, `**Known defects**`), and ends at the next heading of the same or a higher level; a heading inside a code fence is not read. Inside it every non-blank line is one of: a defect row (`- defect: file:line ...`, or a numbered item `1. file:line ...` or `1) file:line ...` at column 0; `1. observation:` is a defect row too, fail closed); a continuation of a row, observation or none line (indented at least two spaces or a tab, not starting with a list mark, `|`, `>`, `#` or `:`); an observation `- observation: ...`; a none line (`Defects: none`, or `none`, `none found`, `no defects found` or `n/a` with an optional leading bullet, parentheses around `none`, a trailing period, any case); a code fence. Any other non-blank line is refused (message `non-canonical line in a Defects section`): a bare bullet, an indented or deeper-level item, a table row, a definition list, a block-quote item, a `---` rule, a deeper sub-heading, a bold title, prose. A PASS holds no defect row. A FAIL's section holds at least one defect row or none line, and a bare FAIL holds a defect row. A defect row inside a code fence is counted like any other, and a fenced `- defect:` line is refused. A numbered row `N. file:line ...` or `N) file:line ...` at column 0 outside a code fence is a defect row wherever it sits, under a heading that never names defects included: it needs the cause tag, and a PASS holds none (a numbered item with no `file:line` is an ordinary list item, and a numbered `file:line` line inside a fence outside a Defects section is command output and is not counted); a `- defect:` row is a defect row wherever it sits too. For that rule the location is read after bold and backtick markup is stripped, a leading bracket, parenthesis or quote is skipped (so a link `[src/x.py:4](x)` is read), and it needs a path-like token (a slash or a dot and a letter) followed by `:` and digits (a range such as `:4-9` counts) and then by a space, colon, comma, dot, dash, close parenthesis, close bracket, closing quote or the end of the line, with a space or a tab after the item number; `1. 12:30 start`, `1. localhost:8080 up`, `1. 3:1 ratio` and `1. exit:0` are ordinary list items. In a PASS a numbered row outside a Defects section is refused with the message `the row sits outside a Defects section` (tag it, or move it to bullets, a table or a code fence). To list changed files in a PASS, use bullets, a table or the `declared=` count of the drift row, never a column-0 numbered list whose items start with `file:line`: the checker reads each such item as a defect row wherever it sits, and refuses the PASS. For the word Defects and its row mark the text is also read after the look-alikes of `DEFECT_FOLD` (Cyrillic, Greek and Latin small-capital, hooked and stroked forms of the letters d, e, f, c, t and s) are folded and the control characters (NUL included, the tab excepted) are dropped; a first word that holds any other non-ASCII letter and whose ASCII letters alone are within one edit of `defect` or `defects` is refused as `non-canonical Defects line` (fail closed), and a title word of that shape opens a section; a look-alike word two or more edits from those is not caught. A code fence that is never closed by a matching closer (a closer of another mark or a shorter closer, or an inline triple-backtick span at the start of a line) refuses the record (message `code fence opened here is never closed`), because it would hide every later line. |
| T3 | Each judge table row (a line with a `\|`, with or without a leading pipe; a full-width bar counts as a pipe) in which a cell holds the word REJECTED, case ignored, after `*`, `_`, backticks and `~` are read as spaces (guardrail cells included), has exactly one cause tag, whether or not the line is inside a code fence. Before the word is read, HTML entities are resolved until nothing changes (a line still changing after 100 passes refuses the record: a nesting 100 deep is read, one 101 deep is refused), tags are resolved and format and combining characters are dropped; the thirteen Cyrillic and Greek capitals and small letters of `FOLD_MAP` that look like E, C, T, J or D (the Greek lunate sigmas U+03F9 and U+03F2 included) are read as their Latin letters; and a markup character inside the word is read as nothing. A fenced line of a judge or QA record that is a table row (a leading and a trailing pipe), or that holds REJECTED in a row, is refused. A fenced line that holds REJECTED in a row is refused even without an edge pipe. The `REJECTED n` on the `TOTALS:` line equals the number of such cells. |
| T4 | A bare `RESULT: FAIL` has at least one defect row. `RESULT: FAIL — <reason>` is a process failure, and its reason must begin with one of: `candidate differs from the brief` or `candidate moved during QA` (C3, section 3-7), `missing tool` (section 3-1), `no git` (section 7-10). A process FAIL needs no defect row; any other reason is refused. |

**Drift.** The QA brief gives two lines, `Base:` and `Declared:` (`orchestrator-template.md`). `Base: git:<12 hex> excl=<12 hex or none>` is the head and the `.git/info/exclude` digest, recorded once per unit before the first builder spawn (the Base step of `qa-agent-guide.md` section 7-10). A builder re-run for the same unit carries the same line, so a commit made in an earlier round stays in the listing. The orchestrator writes the line to `_workspace/base_{unit}.txt` in the same step. A resumed run reads it from that file and never records a new Base for a unit once a builder for it has run, because a Base recorded after a builder commit hides that commit. If the file is missing on a resume, the unit stops and the user is asked. `Declared:` is the paths the design lists. QA copies the Base line into its report as the `BASE:` line, and writes one drift row in `## Gate`:

`| drift: declared=<n> changed=<m> undeclared=<LIST or -> flags=<n> excl=<12 hex or none> on=<git token> | <command> | <exit> | <output> |`

`LIST` is comma-separated with no space in it. Each path is percent-encoded as `qa-agent-guide.md` section 7-10 shows, so a space is `%20`, a newline is `%0A` and a non-ASCII byte is `%XX`. `flags=` counts the index flags (`git ls-files -v` lines that do not start with `H`); `excl=` is the digest of `.git/info/exclude` as it stands. `on=` is the `git:` token of the report's `CANDIDATE:` line.

| Id | Rule |
|----|------|
| D1 | A PASS and a bare FAIL hold exactly one drift row; a process FAIL holds none or one well-formed row. A row inside a code fence does not count. |
| D2 | `on=` equals the `git:` token of the report's own `CANDIDATE:` line, so a row copied from an earlier tree is refused. A `files:` or `unborn` token is refused on a drift row, and a PASS needs a `git:` candidate. |
| D3 | A PASS has `undeclared=-`. A changed path the design does not declare is a defect with its cause (T2): the builder removes it, or the design is revised and audited first. |
| D4 | A PASS has `flags=0`. An index flag other than `H` (`assume-unchanged`, `skip-worktree`) hides a tracked file's change from the listing, so a flagged PASS is refused. |
| D5 | `excl=` equals the `excl=` of the `BASE:` line on a PASS and a bare FAIL, which both need that line. A changed `.git/info/exclude` can hide an undeclared new file from the listing; the digest pins the file as it was at Base. |

**Drift refusals.** A drift row that fails D1-D5 is a refusal in every run and exits 4, as a cause, defect, process or REJECTED refusal does. There is no advisory mode and no option that turns a drift refusal into a pass: `finding_tags.py check` takes file names only. Record the Base line after the hook folder lines are in `.git/info/exclude`, the same precondition as the candidate id (`master-finhub-orchestrator/SKILL.md`).

The drift check covers territory, which paths changed. Whether the built thing still meets the acceptance criteria the brief stated is a judgment, made by the probes of `qa-agent-guide.md` section 7-3.

**Scope.** The checker applies to the reports and verdicts the orchestrator writes after this rule is in force, and it is given only those files. No digest list exempts a record, and nothing is backfilled. An appended or edited file is checked again in full, so one changed byte re-checks every record in it.

**Gate use.** The step that checks reports runs `candidate_id.py check` (C5) and then `finding_tags.py check` on every QA report and judge verdict. A passing `finding_tags.py check` does not show that a report is current; `candidate_id.py check` does that. Exit 4 is a refusal of a record, not the stale exit 3 of `candidate_id.py check`; it sends the record back once. Under section 3-6 the QA report checked is the current one, under the usual name: a kept `_r<k>` report was checked while it was current and is not passed again.

Does not cover:

- The checker reads recorded text only. It does not confirm that `changed=`, `undeclared=`, `flags=` or `excl=` is true; the command cells are the evidence, and a re-run reproduces them. A forged row passes D1-D5.
- Territory is matched by path, with the same ignore rule as the candidate id (quality-gates 3-7). Ignored paths are outside the drift row: a file written under `dist/` or `.checkpoints/` escapes it, because `.gitignore` and `.git/info/exclude` hide it from the listing and from the candidate id. A global excludes file (`core.excludesFile`) is not an ignore rule for either: both disregard it, so a file it matches is listed. A tracked file forced into `_workspace/` is hidden by the pathspec. The candidate id has the same blind spot for `.git/info/exclude`; the drift row pins that file's digest at Base, but the candidate id is not changed here (OR-D1 is an open follow-up for Daniel). A change inside a declared file that drifts from the outcome passes D1-D5; the probes of `qa-agent-guide.md` section 7-3 are the only check for that.
- Index-flag route: `flags=` reads `assume-unchanged` and `skip-worktree` at QA time. A flag that is set and cleared between the builder's run and the QA read is not seen; the route is closed only for the state the QA reads.
- Exclude-file route: `excl=` pins `.git/info/exclude` as it stands at Base and at the QA read. An exclude line added and removed between the two reads is not seen.
- `_workspace/` design-file route: a builder that edits a file under `_workspace/`, which is where the design `Declared:` is copied from, is outside the listing (the pathspec and the candidate id both exclude it).
- Uncommitted changes that already exist when `Base:` is recorded appear as undeclared.
- The checker does not check that a defect row cites a line of the brief or the design. T2's cause is the reporter's judgment under the rule above. No agreement study was run, and no ratio of causes is computed; the source's calibration line (references/openrig/docs/reference/wave-sdlc.md:61-62) is not adopted.
- A builder fault written as a process reason (`RESULT: FAIL — missing tool: x`) escapes T2 and D1. The reason list is closed, but a listed reason can still be misused.
- `Declared:` is copied by hand from the design, and the checker does not parse the design. A wrong copy is caught only by a reader.
- A FAIL's undeclared paths are not matched to defect rows.
- Resume route: prose only. The closing rule is named here and is not enforced by code: the Base line is kept in its file and never re-recorded after a builder has run. A run that records a new Base after a builder commit hides that commit, and the checker cannot see it: it reads only the BASE line it is given.
- REJECTED count route: the count is by the word, in any line with a pipe, with or without a leading pipe (T3). Still open: a verdict written as prose on a line with no pipe is not a row and is not counted; the verdict schema requires the table. A verdict spelled only with a symbol (`✗`) or as `REJECT` does not hold the word and is not counted. A letter that looks like one in REJECTED and is not in the pinned look-alike map is not counted: the map (`FOLD_MAP` in `finding_tags.py`) covers the Cyrillic and Greek look-alikes of E, C, T, J and D only, so the Cherokee letter U+13A1 (named CHEROKEE LETTER E), which looks like R, is not read as R (residual 7 below). The `UNVERIFIED n` on the TOTALS line is not reconciled: the checker counts REJECTED only. A `|` inside a code span splits the cell and can change the count; the TOTALS check then refuses a mismatch, and each counted row still needs its tag. A cell that says 'rejected' in another sense is counted and needs a tag, so it is reworded.
- Accepted residuals (Daniel, 2026-10-11 and 2026-10-12): the eighteen routes below are named here and are not closed by the checker. Routes 1 to 12 were found by the round-5 judge, and Daniel accepted them in writing instead of authorising a sixth round. Route 13 was found by the fourth boundary-qa run and is not accepted: Claude read his reply 'proceed' as acceptance, he answered 'delete' on 2026-10-14, and its ledger row `OR-D4-R13` is removed (3-9). It stays in the list because the checker still does not close it; read 'accepted' in this bullet as covering routes 1 to 12 and 14 to 18. Routes 14 and 15 come from the fifth boundary-qa run, which returned RESULT: FAIL, and Daniel accepted them in writing. Routes 16 to 18 are the other findings of that run: on 2026-10-12 Daniel decided to ship with them open, over the advice of the builder, which is an explicit override of the rule that nothing is committed before boundary-qa returns RESULT: PASS. No later boundary-qa run has passed this tree. The round-5 design was not re-audited after the five fixes built on top of it (the Defects heading rule, the lunate sigmas, the fenced no-edge row test, the citation, the entity fixed point); boundary-qa is the only check on those.
  1. REJECTED written as a symbol only (a lone cross mark) or as the word REJECT is not counted.
  2. A verdict written as prose on a line with no pipe is not a row and is not counted.
  3. REJECTED split across a line break inside a cell is not counted.
  4. An HTML comment that holds angle brackets inside the word (`RE<!-- > -->JECTED`) is not read as markup and the word is not counted.
  5. Invisible characters that are neither format (Cf) nor combining (Mn), such as U+115F and U+2800, inside the word are not dropped.
  6. Dotted or hyphenated letters (`R.E.J.E.C.T.E.D`) are not counted.
  7. Look-alike letters outside the pinned `FOLD_MAP`: the Latin small capitals U+1D07, U+0280 and U+1D1B, the Latin letter YR U+01A6 and the Cherokee letter U+13A1 are read as the letters they are.
  8. The `UNVERIFIED n` on the TOTALS line is not reconciled with the table.
  9. The resume route (the Base file) is a prose-only control.
  10. The candidate id does not read `.git/info/exclude` (an OR-D1 follow-up for Daniel); the drift row pins that file at Base only.
  11. Fence narrowing: a fenced line with a pipe, no edge pipe and no REJECTED is not refused, so a shell or regex line in a fence is allowed.
  12. Four historic judge records (`C11_r2`, `C15_r2`, `C18_r3`, `OR-S1_r3`) stay unedited and are refused (exit 4); no procedure hands them to the checker, and the gate is given only records written after this rule.
  13. Single-symbol look-alikes of a letter of `defect` or `defects` that are not letters and are not folded (U+212E, U+249F, U+24A0, U+24A1, U+249E, U+24AF, U+2020), invisible symbols inside the word (U+2800, U+1D159, U+FFFC, U+2065), and two unlisted look-alike letters in one word (two U+0259; U+1F133 plus U+212E) are not read as the word: the one-edit fallback and the fold list do not cover them, and `two or more edits away` understates it. A heading, a section opener or a row spelled that way is not caught.
  14. False refusals in a PASS (fail closed): a numbered item whose first token holds a slash or a dot followed by a letter but is not a file path, such as `1. e.g.:2`, `1. example.com:443`, `1. docker.io:5000`, `1. pod/web:3`, `1. 3/4:5` and `1. am/pm:3`, is read as a defect row and refused for want of a cause tag. The reporter rewords the item.
  15. Numbered-row spellings that pass because the rule needs a path-like first token at column 0: a wrapped item, `file src/x.py:4`, a path with spaces, a Windows path (accepted on purpose and pinned), a block quote, `<src/x.py:4>` and an extensionless name such as `Makefile:4` are not read as defect rows, so an untagged one passes a PASS.
  16. Fail-open terminators (accepted by Daniel, over the builder's advice): a numbered `file:line` row whose line number is followed by `;`, `?`, `!`, `>`, `}`, `|` or an unspaced em or en dash is not read as a defect row, so an untagged one passes a PASS. This is a fail-open, not a false refusal, and it is not closed.
  17. The generated QA agent text in `skills/finhub-harness/SKILL.md` Step 3 states four things and omits the changed-files sentence (how a PASS lists changed files); that sentence lives in `qa-agent-guide.md`, `.claude/agents/boundary-qa.md` and T2 above, so an agent generated from the Step 3 text alone is not told it.
  18. Test gaps: three mutants of `finding_tags.py` survive the suite although the shipped code is correct. Z6 (`MARKUP.sub("", body)` changed to `MARKUP.sub(" ", body)`, after which a numbered path with an underscore or a tilde passes untagged), Z8 (`:\d+` changed to `:\d*` in the path-and-line pattern) and Z17 (the `LOCATION` pattern left unanchored, so a location later in the row is accepted). No test pins these behaviours.
- A chat or Cowork surface without git cannot produce a drift row; its report is a process FAIL with the reason `no git` (section 3-1).

### 3-9. The waiver ledger (opt-in)

A gap that a report accepts (a residual route named in Does-not-cover, a check that could not run, a finding the owner chose to ship over) stays accepted until someone looks again, and nothing makes anyone look. A harness that gates repeatedly keeps each accepted gap as one row of a checked-in `WAIVERS.md`, and `scripts/waiver_ledger.py check WAIVERS.md` turns a row past its expiry red. Standard library only; no network, no daemon, no database. Exit 0 clean, 4 red (a row refused or expired), 2 bad call (any option, an unreadable file, no table). A harness that gates once does not need it.

| Id | Rule |
|----|------|
| W1 | The ledger is one markdown table with the columns `id | scope | gap | owner | receipt | granted | expires`, in a file under version control. A row with a missing field, a wrong cell count, a repeated id or a date that is not a real calendar date is refused, and a refused row makes the ledger red. A file with no table exits 2. An invalid ledger is never read as an empty one. |
| W2 | `owner` is a human who accepted the gap: only `daniel` in this repository (the `OWNERS` line of the script, one line to change in a copy for another harness). An agent name is refused, because no agent message accepts a gap. |
| W3 | `receipt` is the owner's own words, quoted, then the date: `words: "<reply>" <optional note> YYYY-MM-DD`, or `pr: <ref> YYYY-MM-DD` for a pull request the owner approved. The date equals `granted`, so moving `granted` without writing a new receipt is refused. A test, a QA row or a log line is evidence of the gap and goes in the `gap` cell. The script checks the shape of the receipt; it cannot check that the owner said it (W6). |
| W4 | `expires` is at most 90 days after `granted` (`MAX_DAYS`), and `granted` is at most one day after today (a day of slack for a machine whose date is behind the owner's; two days ahead is refused). The last active day is `expires`; the day after it the row is `EXPIRED` and the ledger is red. To renew, write a new receipt and new dates; to close the gap, delete the row (git keeps the history). A renewal or closure unit declares `WAIVERS.md` and no test file, because no test reads the live file's seed content. |
| W5 | A clean run names every active waiver and prints a `NOTICE` for each one that expires within 14 days. A QA report pastes the first line, the `WAIVERS:` line, every `NOTICE`, `EXPIRED` and problem line, and the `STATE:` line as one `## Gate` row (the active-waiver lines may be replaced by their count). Any non-zero exit, 2 included, is a FAIL like any gate command (section 3-1), and in a repository that keeps a ledger a missing file is a FAIL. A report calls an item accepted only by citing its `id`. `package-plugin.sh` and CI do not run it. |
| W6 | A row is written or edited only from the owner's words, which the orchestrator copies into the brief (or from a written record the brief names). A builder copies the rows the audited design lists, and never invents or re-dates one. For each row the candidate adds or changes, QA finds the quoted words in the brief or compares them with the named record (every quote, date and gap text), and finds `WAIVERS.md` on `Declared:`. A missing quote, a mismatch, or a ledger edit the design did not declare is a defect with its cause (T2). Drift row D3 sees only an undeclared ledger edit; it says nothing about a declared one. |
| W7 | A waiver does not change a verdict. A surviving non-equivalent mutant is still a FAIL (section 3-4) and a command that cannot run is still a FAIL (section 3-1); the row records that the owner chose to ship over it, and when it comes back. A result that belongs to one candidate is not a waiver: a mutant argued equivalent is run again on every candidate (M8) and a skip is accounted for in every report (section 3-3). |
| W8 | When the check is RED, shows `EXPIRED` or exits non-zero, QA writes FAIL and the orchestrator stops: it shows Daniel the `NOTICE`, `EXPIRED` and problem lines in its report before any commit and asks him to renew or drop each row with new words, and it never commits past a RED or edits `WAIVERS.md` to make it pass. The orchestrator, not QA, relays `NOTICE` lines. A renewal is a unit of its own: it declares `WAIVERS.md` and nothing else, moves the candidate id and forces a QA re-run, an accepted cost. |

The eighteen residuals in 3-8 had rows `OR-D4-R01` to `OR-D4-R18`; the ledger holds seventeen, because row `OR-D4-R13` was removed on 2026-10-14 at Daniel's answer 'delete' (the checker still does not close that route, so 3-8 still lists it as not closed). Each remaining row has Daniel's reply as its receipt. The numbered list in 3-8 stays the description; the ledger holds who accepted it, on what words, and when it expires.

How it meets the other checks. The ledger is a tracked file, so an edit to a row moves the candidate id (section 3-7) and voids the verdicts written before it; the clock is not in the id, so a PASS that `candidate_id.py check` calls current can cite a waiver that expired afterwards. The orchestrator therefore runs `waiver_ledger.py check` at the moment of action, next to `candidate_id.py check` and `finding_tags.py check`. A waiver row is not a finding and has no cause cell: a defect that the owner ships over keeps its own defect row, with the cause tag `finding_tags.py` already requires (section 3-8), in the report that recorded it, and the `gap` cell names that report.

Does not cover:

- The receipt is checked for shape. A quote the owner never wrote passes the script; W6 is the only control, and the orchestrator that writes the brief could write the quote too.
- Nothing forces an accepted gap into the ledger. A gap left out is a section 4-2 matter, and no script finds it.
- The ledger check reads one file and no report: a report that cites an id that is not in the file, or an accepted item that cites no id, is not found. Only a reader catches it.
- The clock is the process's local date (`date.today()`), so the process time zone is the only clock input. A wrong clock gives a wrong answer, a machine more than a day behind the owner's date turns a fresh row red, and there is no option to set it.
- 90 days is a choice, not a measurement. Waivers granted together expire together: on 2027-01-10 fourteen of the seventeen rows are `EXPIRED` and the commit of any unit is blocked until Daniel renews or drops them (W8). The seed is not staggered, because the dates are his recorded replies and invented ones would falsify them. The 14-day notice, relayed by the orchestrator, is the only warning.
- A date and a receipt edited together to a new, invented quote pass the script (W6). So does renewing by re-dating `granted`, the receipt date and `expires` while keeping the old quote: the script cannot tell a renewal from a first grant. Only W6 (QA compares the quote with the brief or the record) catches it.

(Owned, receipted, expiring exclusions that turn the gate red by themselves, a ledger that names every exclusion in its output, and a ceiling on the expiry, adapted from references/openrig/scripts/gate-lane-ledger.mjs:1-12, :35-52, :60-85 and :90-112 (Apache-2.0). A ledger file kept in the repository next to the gate, adapted from references/openrig/scripts/gate-lane.mjs:21-23 (Apache-2.0). The ceiling counted from `granted`, the owner list and the dated receipt are new here.)

### 3-10. Rigor is assigned, not chosen

Sections 1-3 are a chain of gates. Which units of work run that chain is decided by the owner, in one table of the orchestrator and, for a downgrade, one ledger row, and by nobody else. Section 2-1's doubt is about how an assigned audit is carried out; this section is about who assigns it. The two do not overlap. (adapted from references/openrig/docs/reference/sdlc-conventions.md:20-25 (Apache-2.0))

Two levels, no third. `light`: the agent that produced the unit checks the whole outcome with the repository's real gates, and no judge or QA agent runs. `gated`: sections 1-3 in full.

Two classes. Audited decisions are money, eligibility, compliance and client-facing text; a gap email is client-facing text, so it is one. Their gate is preselected: the unit is `gated` unless the owner approves a downgrade. Everything else is class `other` and defaults to `light`; software is `other` unless the owner assigns it `gated` at build time. The owner assigns the class at build time: the build skill asks, per kind of unit, and writes the answer, and an agent never classifies a unit as `other` on its own. When it is unclear whether an output is an audited decision, treat it as one. A classification or a downgrade that lowers rigor needs the user's approval; an agent never decides it.

The table sits under `## Rigor` in the orchestrator: `| scope | class | level | assigned-by | on |`. A scope is a kind of unit (`client-email`); one piece of work is `<scope>/<item>` (`client-email/c1`). `class` is `audited-decision` or `other`. `level` is the level before any downgrade: `gated` for an audited decision (the table never holds `light` for it), `light` or `gated` for `other`. `assigned-by` is `default` (only for an audited decision whose owner gave no answer) or `owner:<name>` (required for every `other` row: it is the owner's answer).

| Id | Rule |
|----|------|
| RG1 | No agent selects, raises or lowers a level, and none classifies a unit. The owner assigns both; a plan the owner approved counts as the owner. A role name, an idle seat, a milestone, an earlier finding and a team-size decision assign no gate. |
| RG2 | An agent that thinks a unit needs another level writes one sentence naming the unresolved risk to the owner and continues at the assigned level. A judge does not add rounds or gates, and QA adds no check because an earlier check found something; it re-checks that finding once (section 3-6). Extra judge rounds still need the owner's written word (2-4). |
| RG3 | There are two ways to run below the table, and both are a ledger row of `WAIVERS.md` with the owner's quoted words, the date and an expiry (section 3-9, W2-W4). One item: scope `rigor:<scope>/<item>`, active when `granted <= today <= expires`; a row dated tomorrow is not active. Lowering the table: a class from audited-decision to other, a level from gated to light, a scope removed, or a new scope classed `other` (an unlisted scope counts as an audited decision) needs a row `rigor:<scope>/table` that is active on the day of the commit. `rigor_check.py` compares the table with the previous committed copy and refuses a lowering without it. A typed `owner:<name>` never lowers anything. After the commit the table is the record. A receipt may name a scope the new table no longer lists, because the scopes of the previous table count too. A `rigor:<scope>/table` row that is no longer needed is stale, and which check goes red depends on the lowering. A row for a scope that stays in the table (a class or level lowered): `rigor_check.py` stays clean, and `waiver_ledger.py check` is red from the day after `expires` (W4). A row for a removed scope: at the next commit the previous table no longer lists the scope, so `rigor_check.py` refuses the row as naming no scope of the table (exit 4), even before `expires`. Either way the red ends only when a closure unit deletes the row, so a stale receipt row costs a closure unit. |
| RG4 | An item downgrade covers the named item for the row's lifetime, never one run of whatever shares its scope. The lifetime is the row's `expires`, at most 90 days (W4); a closure unit that deletes the row ends it earlier. The day after `expires` the unit is `gated` again and the ledger check is red until a closure unit deletes the row (W8), so every downgrade costs one later closure unit; set `expires` as short as the work needs. |
| RG5 | The downgrade row, for an item or for the table, is committed by a unit of its own that declares `WAIVERS.md` and nothing else and runs `gated`, so QA compares the owner's quoted words with the brief (W6); the item or table change comes after that unit passes. That is a rule, and the script enforces only that a light unit changes no ledger and that the table and the ledger do not change in one commit. W7 is unchanged: the row stands for a gate that did not run, so there is no verdict to change. |
| RG6 | A gated unit's brief carries `Rigor: gated unit=<scope>/<item> by=<assigned-by> on=<date>`, copied by the orchestrator from the table. A QA report carries `RIGOR: gated unit=<scope>/<item> by=<assigned-by> on=<date>`; its lines run RESULT, CANDIDATE, CARRIED, BASE, RIGOR (line 5). A judge verdict's lines run TOTALS, CANDIDATE, CARRIED, RIGOR (line 4). The order is load-bearing: `finding_tags.py` reads BASE in lines 2-4, so a RIGOR line placed earlier pushes BASE out and the report is refused. `rigor_check.py` reads the first eight lines, outside code fences, for exactly one such line. |
| RG7 | At each commit or ship step run, after `candidate_id.py check` (the stale-report guard; this check is not) and `finding_tags.py check`: `python3 <skill dir>/scripts/rigor_check.py check <orchestrator> <WAIVERS.md or -> <scope>/<item> <PREV or -> <CHANGED> <reports...>`. PREV is the previous committed copy of the orchestrator (`git show HEAD:<path>` written to a file; `-` only when the file has no earlier commit). CHANGED is a file that lists the paths the commit changes. Reports are the item's QA report and, when it has a design, its judge verdict. Any non-zero exit blocks. The orchestrator relays every `DOWNGRADE:`, `LOWERED:` and `NOTICE:` line to the owner before the commit. The final report's second line is `RIGOR: no unit ran light` or one `RIGOR: <scope>/<item> ran light by owner downgrade (waiver <id>, expires <date>)` per light item or lowered row, in the report only. |
| RG8 | Team size and rigor are separate. The delegation gate (SKILL.md Step 2-0) never selects a level, and a level never passes the gate for the producing roles. A `gated` unit adds a judge and a QA agent to a single-agent outcome: their hand-off artefacts (the verdict and the report) are the named artefacts of question 1, and a producer does not judge its own work. Roles the user asked for, and the producer-reviewer pattern, are unaffected: this section governs only the Authority List judge and boundary QA. |
| RG9 | Failure goes toward rigor. An expired or not-yet-active downgrade, a downgrade naming no table scope, an unknown unit and a malformed table never yield `light`. A harness that never downgrades passes `-` for the ledger and keeps none, so the opt-in of section 3-9 stands; it still copies `rigor_check.py` with `waiver_ledger.py`, which it imports. |

Does not cover:

- The script checks shape and consistency. A downgrade row with words the owner never said passes it, and a whole forged QA report is not told from a real one. The controls are the user's approval, the owner reading the `DOWNGRADE:` and `LOWERED:` lines, and QA comparing the quote with the brief (W6), which is a real control only when the row sits in a unit of its own that runs gated (RG5).
- The orchestrator runs `rigor_check.py` at each commit or ship step and boundary QA runs it too, as a gate command. A skipped step is a prose failure, not a refusal. PREV and CHANGED come from the caller: a `-` for PREV where an earlier commit exists, or an incomplete CHANGED list, skips a comparison. The first table of a harness is the owner's answer at build time, shown in the report of `SKILL.md` Step 6 item 7; nothing compares it with anything.
- Path spelling of CHANGED: each entry is read with backslashes as slashes, normalised (`./`, `//`, `a/../b`) and case-folded, and it names the orchestrator or the ledger when it equals the argument or one is the tail of the other at a slash, so `waivers.md`, `./WAIVERS.md` and a ledger argument given as an absolute path all count. An entry that is absolute, has a drive letter or climbs out with `..` is refused (a `CHANGED:<n>:` line). Not closed: a symbolic or hard link to either file; a Windows short name (`WAIVER~1.MD`), a trailing dot or space, or a data-stream suffix; a path that git quotes or octal-escapes (`core.quotePath`); a rename, because `git diff --name-only` lists only the new name unless `--no-renames` is given; a Unicode composition form of a non-ASCII name; a UTF-8 byte order mark on the first line of the CHANGED file (the mark stays in the path, so `WAIVERS.md` on that line is not matched). Case folding over-matches on a case-sensitive file system, where `Waivers.md` is another file; it fails toward rigor. The tail match is wider than needed: a root file and a deeper file with the same name count as one, so a light unit that changes a deeper `WAIVERS.md` is refused, which fails toward rigor.
- The comparison is with the previous commit only. A lowering that passed once with its receipt stands in the next commit without it.
- `rigor_check.py` reads shape, not the verdict of a report beyond RESULT: PASS. A report that says FAIL does not license a commit; whether a PASS is true is for the reader.
- Whether an output is an audited decision is the owner's call. The rule treats an unclear one as yes; no script reads the work.
- A wrong PREV that is not `-` (a file that is not the previous committed copy of the orchestrator) is not detected; the script compares with whatever file the caller names.
- The caller chooses the scope a unit is filed under (`<scope>/<item>`); the script does not check that the work really belongs to that kind of unit, so an audited decision filed under an `other` scope runs at that scope's level.
- A table receipt licenses any lowering of its scope until it expires: the row `rigor:<scope>/table` is not tied to one edit, so while it is active every lowering of that scope in that window passes.
- Chat and Cowork have no shell. There the orchestrator prints the table and any downgrade in its reply and the final report line, and says the check is `unverified`.
- Waivers granted together expire together (3-9), and a downgrade lasts at most 90 days.
- The clock is the process's local calendar date (`datetime.now().astimezone().date()`), so the process time zone is the only clock input. A wrong clock gives a wrong answer, a machine more than a day behind the owner's date turns a fresh row red, and there is no option to set it. `waiver_ledger.py` reads the same local date with `date.today()` (3-9).
- The owner list is the `OWNERS` line of `waiver_ledger.py`. A harness whose user is not the owner of its output changes that line and names the owner in the Rigor section.

(Rigor assigned by the owner or the plan and never by a role or an idle seat, adapted from references/openrig/packages/daemon/specs/agents/shared/skills/pods/orchestration-team/SKILL.md:17-19 and :149-152 (Apache-2.0). The no-self-selection rule and the one-sentence ask, adapted from references/openrig/docs/reference/sdlc-conventions.md:23-24 (Apache-2.0). No raising of rigor after a finding, adapted from references/openrig/docs/reference/product-journey-sdlc.md:177-178 (Apache-2.0). An independent review not done by the author, adapted from references/openrig/packages/daemon/specs/agents/shared/skills/pods/review-team/SKILL.md:24-25 (Apache-2.0). The two classes with the owner's assignment, the ledger-row receipts, the comparison with the previous table, the effective-level computation, the two-level set and the script are new here.)

### 3-11. A new refusal, prompt or required step states its cost

Sections 1-2 check that a design's claims are true. A true claim can still add a guard that stops legitimate work, and the people it stops appear in no record. This section puts them in the record. Three questions are answered in the design, for every refusal, prompt and required step it adds, and the judge rules on the answers. (Three questions adapted from references/openrig/CONTRIBUTING.md:29-31 (Apache-2.0). The trigger being any change that adds friction, not only a security change, adapted from references/openrig/.claude/skills/developing-openrig/SKILL.md:68-69 (Apache-2.0).)

Terms. A refusal is a check, hook, lint, exit code or agent rule that stops an input, a commit, a run or a tool call (exit 4, FAIL, REJECTED, blocked). A prompt is a place where a process stops to ask the user. A required step is a step someone must now take, or a field an author must now fill, that nothing required before. A WARN that lets the work go on, a test and a documentation-only change are none of the three. A design that claims an input is never supplied for a good reason, and so skips the statement, argues it in a CS2-style cell: the claim is a statement like any other.

| Id | Rule |
|----|------|
| CS1 | A design that adds one of the three writes a `Cost statement`: a `## Cost statement` section in an adoption, a `### Cost statement` in a slice. It has one row per addition and three cells. `scenario`: the concrete case that triggers it, with the evidence that the case happens (a line, a run, an earlier incident). `caused by`: who or what produces that case and how it reaches the system. `cost to others`: what a person or agent who did nothing wrong loses or must do, how often, and their way out. A design that adds none says `Cost statement: none; this design adds no refusal, prompt or required step.` |
| CS2 | A cell names a case, not a category. "Bad input", "users" and "low" are not statements. A cost to others of "none" needs its reason in the same cell, one the judge can check (for example, the only producer of the input never emits it). |
| CS3 | The judge's fixed row `cost statement` reads UPHELD, REJECTED or N/A, in a `## Cost statement` table of the verdict. UPHELD: every addition the judge finds in the design has a row whose three cells meet CS2. REJECTED: an addition has no row, or a cell fails CS2; the row counts in `REJECTED n`, and carries exactly one cause tag (section 3-8 requires one tag on every REJECTED row but says which only for cited files, so this row sets its own cause: `judgment-gap` when the architect's brief names this section, `context-gap` when the brief did not route it). N/A: the judge read the Design, Target and Test-plan text, found no addition, and the row says what it read. The judge finds additions itself and does not take the architect's list as complete: an addition the design makes and does not list is a missing row. The row applies to designs written or revised after this section exists; a design written earlier and judged again is not failed for guards it already had. A missing statement costs one of the three judge rounds, and one found in round 3 goes to the owner (section 2-4); the judge says so in the reason cell. As a read aid, not a rule, look for refuse, reject, exit non-zero, block, deny, must, required, ask and stop. |
| CS4 | Where the cost falls on callers who did nothing wrong and the hazard is only possible, the statement says why advising and carrying on would not do. A hard refusal belongs to the genuine hazard. This is guidance for the architect; the judge rules on the three cells only. (Adapted from references/openrig/CHANGELOG.md:1822-1826 (Apache-2.0).) |
| CS5 | The row records a cost and does not veto the guard. A design with a high stated cost can be UPHELD and built; the owner and the next reviewer have the cost on the page. This departs from the source: there the maintainers may decide a fix costs more than it protects (the cost can defeat the fix). Here a judge audits citations and statements, not whether a guard is worth its price, and has no basis to weigh the two; the owner decides, and sees the cost. What is kept from the source is that the finding and the fix are separate questions, so a judge who accepts the scenario may name a cheaper fix in the body of the verdict. (Adapted, with that departure, from references/openrig/CONTRIBUTING.md:33-34 (Apache-2.0).) |
| CS6 | The row belongs to an assigned audit. It adds no round, gate or level and changes nothing in section 3-10 (RG2). A unit that runs `light` has no judge and so no row; the producing agent still writes the statement if its design adds a guard. |

Missing answers go back once, as a request, not a finding against anyone: a REJECTED row is fixed by the architect writing the statement, in the next round. (Adapted from references/openrig/CONTRIBUTING.md:34-35 (Apache-2.0).)

Worked example (a real before-case, written after the fact). The refusal added by PR #49 in `rigor_check.py`: a `CHANGED` entry that is absolute, has a drive letter or climbs out with `..` exits 4.

| addition | scenario | caused by | cost to others |
|---|---|---|---|
| refuse such a `CHANGED` entry (`rigor_check.py` lines 226-228 and 267-271) | a light unit that changed the ledger lists it as `/abs/WAIVERS.md` or `../WAIVERS.md`, which compared unequal to the ledger name, so the light-unit-changes-no-ledger rule did not fire (shown in `_workspace/02_strategy-architect_OR-S8_followup_r2.md` line 25) | a caller or script that writes an absolute path, a Windows-style path (`C:\...`, read as a drive letter after backslashes become slashes) or a `..` path into the `CHANGED` file; the orchestrator command at `master-finhub-orchestrator/SKILL.md` line 159 does not (from a sub-directory `git diff --name-only HEAD` prints root-relative names and `git ls-files --others` prints names relative to the sub-directory, so neither is refused) | a caller who wrote such a path for an innocent reason gets exit 4 and no commit until the list is rewritten root-relative; the printed line names the entry and the fix; in the standard flow the cost is zero. Not caught: a bare sub-directory-relative name from `ls-files`, which has no `..`, no leading slash and no drive letter |

Script decision. There is no script for this section. The row rides on `finding_tags.py check`, which already counts a REJECTED table cell against the `TOTALS:` line and demands one cause tag per REJECTED row (simulated: a REJECTED `cost statement` row with a tag exits 0, the same verdict with `REJECTED 0` on the totals line exits 4, the row without a tag exits 4). A keyword script that looks for refusal words in a design and requires a statement was weighed and refused under CS1. Scenario: 26 of the 36 designs in `_workspace/02_strategy-architect_*.md` contain "refus" or "exit 4", most describing refusals that already exist. Caused by: any architect who describes existing behaviour or lists a limit. Cost to others: each of those designs would be refused at a check for adding nothing, and a statement of "cost: none" would pass the keyword check anyway, so the gain is nil. A heading-only check (the section exists) misses nothing the judge does not read in the same pass, and needs wiring into the orchestrator, QA and a test for three design shapes. Revisit it if the judge misses an unlisted addition in two reports (the evolve trigger of `finhub-harness-evolve`).

Does not cover:

- The judge finds additions by reading. A refusal that sits in prose the judge skims, or comes from a library call, can be missed; no script finds them.
- Only presence and concreteness are ruled. Whether the scenario is real is the judge's existing attack on substance, not a row, and the cost is the architect's estimate: nothing counts how many callers meet the guard after it ships.
- Refusals that existed before this section have no statements and are not backfilled. The worked example above is a retroactive one.
- A WARN or an advisory that every run prints has a cost (noise); it is outside the three terms.
- QA and the builder do not compare the built guard with its statement. A guard built wider than stated is a defect only if the design's declared interfaces say otherwise.
- The threat-scope statement that OpenRig keeps in its security policy (what counts as in-scope harm, supported deployment) is not adopted.
- A harness without a judge gets only the architect's side of the rule.
- The read-aid word list is not exhaustive.

(Adapted from references/openrig/CONTRIBUTING.md:29-35, references/openrig/.claude/skills/developing-openrig/SKILL.md:68-69 and references/openrig/CHANGELOG.md:1822-1826 (Apache-2.0). The fixed judge row, the three outcomes, the cause-tag and totals interplay and the worked example are new here.)

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

The Writers bullet is adapted from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0); its labels are defined in `write-safety.md`.

```markdown
## Quality gates (non-negotiable)

- [ ] Open the design's declared interfaces first. Judge the code against them, not against itself.
- [ ] Write `RESULT: PASS` or `RESULT: FAIL` as the first line of the report.
- [ ] Second line `CANDIDATE:` from `candidate_id.py id`, computed when you start and again just before you write (a start id unlike the brief's, or one that moved, is a FAIL); third line `CARRIED:`, `-` when every check ran on this candidate (section 3-7).
- [ ] Fifth line `RIGOR:` copied from the `Rigor:` line of your brief (a judge writes it fourth, after `CARRIED:`); never choose or change a level or a class, and add no check because an earlier one found something (section 3-10).
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
- [ ] A mutant is killed only when `mutant_gate.py classify` prints `STATE: CAUGHT` for it (rules M1-M8,
      section 3-4). A mutant that broke the import, timed out or failed in another test is void: redo it.
- [ ] Before PASS, record at least one adversarial probe (`probe:` or `mutant:` row, the latter only with a
      `STATE:` of CAUGHT or SURVIVED) with its output.
      Every gate row carries its observed output, the summary line on success included.
- [ ] Re-run timing and concurrency tests 10 times. Check for stray processes and scratch files.
- [ ] Sweep touched files for real client data, secrets and personal identifiers.
- [ ] If the harness runs writers in parallel, read its `## Writers` table: no two `enforced` or `advisory` rows in one batch share a path, no `advisory` row is called exclusive, and every `enforced` or `workspace-enforced` row names a mechanism you opened and saw block the write. A label you cannot show is `advisory`.
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
- Rules M1-M8 have been run against a seeded set of broken mutants (`tests/test_mutant_gate.py`), not yet by a QA agent on a real slice.
- Whether the mutation, flakiness and escalation procedures have been exercised end to end by a harness other than Master FinHub is not known. No round of the build reached escalation (round 3).
