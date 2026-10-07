# State ledger: resuming a run after a context reset

> Handoff classes, adapted from references/meta_harness/docs/architecture/handoffs.md:13 (Apache-2.0). Field names, adapted from references/meta_harness/.agents/skills/harness/SKILL.md:158 (Apache-2.0). A small state file rebuilt on every change, adapted from references/openharness/src/openharness/autopilot/service.py:405 (MIT). A next step and a verified state per item that survive a reset, adapted from references/openharness/src/openharness/services/compact/__init__.py:566 (MIT). A halting state that outlives a reset, adapted from references/openharness/src/openharness/services/compact/__init__.py:635 (MIT). A blocked state that carries its reason, adapted from references/deepseek_harness/packages/goal/goal/src/types.ts:64 (MIT). A write through a temporary file that is then moved over the target, adapted from references/openharness/src/openharness/utils/fs.py:39 (MIT). A step with an outside effect that is declared and, when half done, stopped on resume, adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0). A retry that carries the identity of the first attempt, adapted from references/openrig/docs/as-built/architecture/coordination-primitive.md:46 (Apache-2.0). A failed resume that stops and asks instead of starting over, adapted from references/openrig/docs/as-built/architecture/architecture-rules-and-event-system.md:74 (Apache-2.0). The layout, the rebuild rule, the half-done test and the resume procedure are FinHub's own.

A context reset (a compaction, a new session, a closed chat) takes away what the orchestrator held in mind: which phases are done, what a blocked worker said. The files in `_workspace/` survive. The ledger is one small file, `_workspace/00_state.md`, that records for every phase who produced which file for whom, and whether that file is whole. It is a cache of the files, never a second source of truth. Delete it and `scripts/state_ledger.py rebuild` regenerates it.

## 1. When to keep one

Handoffs come in three classes. Persist one only when it earns its place: when someone will audit it, resume from it, debug with it or read it from another agent. (adapted from references/meta_harness/docs/architecture/handoffs.md:9 (Apache-2.0))

| Class | Examples | In the ledger |
|-------|----------|---------------|
| Ephemeral coordination | a status line, a short question, a bounded message to a peer | never |
| Durable coordination record | a blocker, an acceptance, the point where the run resumes | the ledger itself |
| Durable artefact | a plan, review evidence, a report | one row per file; the file stays the artefact |

Keep a ledger when the run has two or more phases and a later phase reads a file an earlier one wrote. Skip it for a single-phase harness and for one whose results all come back as return messages: it would cost a rebuild per phase and add a file that can disagree with the others.

## 2. The two tables

**Handoff files** is a section of the orchestrator (`## Handoff files`) that lists every durable artefact in run order. It is the plan the rebuild reads.

```md plan
## Handoff files

| phase | producer | consumer | path | sections |
|---|---|---|---|---|
| 1 | analyst | architect | _workspace/01_analyst_findings.md | Findings; Gaps |
| 2 | architect | reviewer | _workspace/02_architect_design.md | Design; Authority List |
| 3 | reviewer | builder | _workspace/03_reviewer_verdict.md | Verdict; Reasons |
| 4 | builder | qa | _workspace/04_builder_report.md | - |
```

`sections` names the headings the file must contain, separated by `;`. It is the same shape the worker brief promises under "Expected output" (`orchestrator-template.md`). Write `-` when the file has no headings. Every cell is filled, and `-` stands for none.

A sixth column, `replay`, is optional. It marks the phases whose worker acts outside `_workspace/`; section 3a has the grammar. A plan without the column is valid, and then every phase may run again. Leave the column out of a plan that has no `once` phase.

**The ledger** repeats those five columns and adds two:

| Field | Meaning |
|-------|---------|
| phase, producer, consumer, path, sections | copied from the plan, never edited by hand |
| completion | one state from the table below |
| note | `-`, or the missing sections of a partial row, or the blocker text of a blocked row |

The file starts with `plan:` (the file holding the Handoff files table), `plan-hash:` (the first 12 hex digits of the SHA-256 of the plan rows, so a blocker is never carried to a different plan) and `next:` (the first phase that is not complete, or `done`), then the table.

| State | Meaning |
|-------|---------|
| pending | the file does not exist |
| partial | the file is empty or lacks a listed section |
| complete | the file exists and has every listed section |
| blocked | a worker reported it cannot proceed; `note` says why |

## 3. Rules

Each rule is enforced by `scripts/state_ledger.py` and by a test in `tests/test_state_ledger.py`; the test fails when a rule is dropped from this table or from the script.

| Id | Rule |
|----|------|
| R1 | A ledger row has exactly seven cells in the order phase, producer, consumer, path, sections, completion, note. No cell is empty; write `-`. `completion` is one of pending, partial, complete, blocked. A blocked row has a reason in `note`. |
| R2 | The rows come from the `## Handoff files` table: five columns, or those five plus the optional `replay` column (section 3a), at least two rows, unique phase ids, no empty section name, every path relative to the project root with no `..`, no drive letter and no UNC share. Every phase file and the ledger must also resolve inside the project with symlinks followed; one that does not stops the run (R9). |
| R3 | Completion comes from the file. Absent path: pending. Empty file, or a listed section missing as a heading outside code fences: partial, with `missing: <names>` in `note`. Every listed section present: complete. A heading matches only when its whole text equals the section name. A byte order mark is ignored, and a file over 8 MiB is partial with a note. Complete means the headings are present, not that the content is right or current. |
| R4 | Files win. Every rebuild rewrites the ledger from the files. Where the old ledger disagreed, `resume` prints a `DRIFT` line and decides from the files. |
| R5 | A blocker survives a rebuild only through the old ledger of the same plan (same `plan-hash`); a changed plan carries none and prints a `DRIFT` line. A blocked row stays blocked while its file is absent or partial and clears when the file is complete. With no readable old ledger a blocker cannot be known, and the row shows pending or partial. A plan edit clears every blocker, so tell the user which phases were blocked before the edit if you know. |
| R6 | The resume target is the first row that is not complete, in table order. None: stop, done. Blocked: stop and report the note; retry nothing. Partial: resume that phase and give its worker the path and the note; a half-done `once` row is the exception and stops (O3). Pending: start that phase. |
| R7 | A rebuild or a resume writes only `_workspace/00_state.md`, through a temporary file in the same directory that replaces it, and not even that when its text would not change. No phase file is created, changed or deleted, and a complete phase is not run again unless the user names it (O2 covers a run-once file that vanished). |
| R8 | A complete row after the resume row is listed as suspect: it may rest on an input that is about to change. Tell the user, and check it before using its file as an input. |
| R9 | A ledger that breaks R1, or whose phases do not match its own plan, is rebuilt from the files and reported as unreadable, and the decision is `stop-unreadable` (exit 3, unless every phase is complete, or O3 applies: a half-done run-once resume row stops as `stop-confirm` first, and the question then also says the ledger was unreadable): a blocker may have been lost, so ask the user, then run `resume` again, which reads the rebuilt ledger; if `resume` still says `stop-unreadable` after the user said yes, the ledger cannot be rewritten (a read-only `_workspace`): tell the user and stop. A plan that breaks R2, or is missing, stops with `stop-no-plan` and exit 2; ask the user. |
| R10 | A ledger that cannot be written (a directory in its place, a read-only workspace) is reported as `LEDGER: unwritable: <reason>`; the decision still comes from the files and the exit codes stay 0, 2 and 3. |

## 3a. Run-once phases

A client SMS that goes out twice, a CRM record written twice or a page published twice cannot be undone by running the phase again, so the ledger treats a phase with an outside effect differently from one that only writes files in `_workspace/`. The author declares such a phase in the `replay` column. The ledger cannot see an effect and does not try; it reads the phase files and, in one case (a file that has vanished, O2), its own previous ledger.

```text
| phase | producer | consumer | path | sections | replay |
|---|---|---|---|---|---|
| 1 | analyst | sender | _workspace/01_analyst_draft.md | Draft | - |
| 2 | sender | logger | _workspace/02_sender_send.md | Intent; Result | once |
```

Mark a phase `once` when its worker sends a message (SMS, email, chat), creates or changes a record in a CRM or another system of record, publishes a page or a post, uploads a file where others can see it, or moves money. A phase that only drafts into `_workspace/` for a person to send is `safe`: the person is the one who acts. A write that a stable key makes harmless to repeat may also be `safe`, but only when the brief names that key; nothing checks it.

| Id | Rule |
|----|------|
| O1 | `replay` is optional and takes `safe`, `once` or `-`; `-` and an absent column both mean safe. Any other value, and a `once` row that lists fewer than two distinct section names, make the plan invalid: `stop-no-plan`, exit 2. The ledger keeps its seven columns, and `plan-hash` covers the five plan columns only, so an old ledger stays valid and changing a marker does not drop a blocker. |
| O2 | A `once` row is half done when its file exists and is not complete: empty, missing a listed section, over the size cap, unreadable, or present but not a regular file. An absent file is not half done, unless the previous ledger recorded that phase as partial or complete: then the file has vanished, the row is half done (`file gone; the ledger had it <state>`) and a delete of the file alone cannot make the phase start again. The previous ledger is no evidence when the plan changed (R5 drops the old rows) or when it is unreadable. Apart from that ledger, only the phase files are read, never the outside system. |
| O3 | When the resume row (the first unfinished one) is a half-done `once` row, the decision is `stop-confirm`, exit 3, and nothing runs. This comes before `stop-unreadable`, whose `DRIFT` line still prints. A `once` row that is pending starts, a complete one is not run again while its file is there (O2 covers a vanished file), and a blocked one stops as `stop-blocked` with a reminder that its effect may have happened. |
| O4 | While the plan has a `once` row, `resume` prints a `HALF-DONE` line naming every `once` row that is partial or blocked, or `-`. The orchestrator never starts, resumes or repeats a listed phase without the user's yes, even when it is not the first unfinished one. |
| O5 | A `once` worker saves its file with the first section before its first outside call, and adds the last section only after the call is confirmed. The first section says what will be done, to whom and under which key; the key comes from the phase inputs, not from the attempt or the clock, and goes with the call when the connector takes one. A worker that cannot tell whether the call went through reports `STATUS: partial` and leaves the last section out. |
| O6 | On `stop-confirm` the orchestrator quotes the first section and the note and asks whether the effect happened. If it did, the orchestrator adds the missing sections to the phase file, says who confirmed it and that the harness did not check, and runs `rebuild`. If it did not, or the user wants it sent again, the orchestrator runs the phase with the file path and the same key in the brief and an order to skip any call the file records as done, and to add to the file rather than rewrite it. Anything else: stop. A user who names a complete `once` phase for a re-run is asked once more, because the re-run repeats the effect. A `once` phase listed in `SUSPECT` is never re-run to refresh it; tell the user its effect used the earlier input. |
| O7 | A `once` phase is never retried automatically and never re-asked: it is outside the orchestrator's retry-once rule and outside the single re-ask for an invalid report. After a worker error, a timeout, an invalid report or `STATUS: partial`, do not launch or ask that worker again; run `resume` and follow O6. Write this exception into the orchestrator's error table and into the step that checks reports. |

The script and `tests/test_state_ledger_runonce.py` enforce O1-O3 and the `HALF-DONE` line of O4. The rest of O4 and O5-O7 are instructions to the worker and the orchestrator: a test pins their wording, and nothing checks that they are followed.

## 4. Procedure on Claude Code

Run the commands from the project root. `<skill dir>` is the directory of the finhub-harness skill and `<orchestrator>` is the file with the Handoff files table. The script lives in the plugin: if the session that resumes does not have the plugin installed, copy `state_ledger.py` into the generated harness (for example `.claude/skills/<orchestrator>/scripts/`) and write that path into the orchestrator's Step 0.

1. **At the start of a run** and **after every phase**: `python3 <skill dir>/scripts/state_ledger.py rebuild <orchestrator>`. A reset before the first phase ends still leaves a ledger. In a session that continues, run `resume` before any `rebuild`: `rebuild` overwrites an unreadable ledger and so skips the stop. `rebuild` prints `LEDGER` and `NEXT` only, so there is no `HALF-DONE` line and no `ACTION`: its `NEXT` line never starts a `once` phase (O7); run `resume` first.
2. **Step 0, when `_workspace/` exists and the request is to continue**: `python3 <skill dir>/scripts/state_ledger.py resume <orchestrator>`. It rebuilds the ledger and prints `LEDGER`, `ACTION`, `PHASE`, `PATH`, `REASON`, one `DRIFT` line per disagreement (or `DRIFT: -`), a `HALF-DONE` line when the plan has a `once` phase, and `SUSPECT`.
3. Act on `ACTION`:

| ACTION | Exit | The orchestrator |
|--------|------|------------------|
| start | 0 | runs `PHASE` from its first step, then continues in table order, rebuilding after each phase |
| resume | 0 | re-runs `PHASE` with `PATH` and `REASON` in the worker brief, and does not start the next phase before it is complete |
| stop-done | 3 | reports that every phase is complete and starts nothing |
| stop-blocked | 3 | reports `REASON`, retries nothing, and asks the user |
| stop-confirm | 3 | quotes the first section of the half-done run-once file and `REASON`, asks whether the effect happened, and follows O6; runs nothing before the answer, and says so when `LEDGER` is unreadable, because a blocker elsewhere may have been lost |
| stop-unreadable | 3 | says the ledger was unreadable and a blocker may have been lost, asks the user, and on a yes runs `resume` again |
| stop-no-plan | 2 | says the Handoff files table is missing or invalid, or a path leaves the project, and asks the user |

`resume` never names a half-done `once` phase; that case is `stop-confirm`.

4. **A blocked worker.** When a worker ends with `STATUS: blocked` (the Delegation block in `orchestrator-template.md`), set that row's `completion` to `blocked` and its `note` to the blocker on one line without a `|`, then run `rebuild`. This is the only hand edit of the ledger.
5. Give the user one line before acting: the `next:` phase and the reason, quoting `PHASE` and `REASON`. If `SUSPECT` or `DRIFT` is not `-`, add them to that line. Say that complete means the headings are present, not that the content is right or current.

Where no shell runs, apply R3 and R6 by hand to the plan rows in order: look at each path, judge it, and say which phase is first not complete.

## 5. Worked example

The plan is the table in section 2. After phase 2 finished and the session ended, the ledger reads:

```md ledger-a
# State ledger
plan: .claude/skills/doc-orchestrator/SKILL.md
plan-hash: 3bf66f6ee89e
next: 3

| phase | producer | consumer | path | sections | completion | note |
|---|---|---|---|---|---|---|
| 1 | analyst | architect | _workspace/01_analyst_findings.md | Findings; Gaps | complete | - |
| 2 | architect | reviewer | _workspace/02_architect_design.md | Design; Authority List | complete | - |
| 3 | reviewer | builder | _workspace/03_reviewer_verdict.md | Verdict; Reasons | pending | - |
| 4 | builder | qa | _workspace/04_builder_report.md | - | pending | - |
```

`resume` prints `ACTION: start` and `PHASE: 3`; phases 1 and 2 are neither read nor rewritten. Had the session ended while phase 3 was writing its file, and a file for phase 4 had been left by an earlier run, the ledger would read:

```md ledger-b
# State ledger
plan: .claude/skills/doc-orchestrator/SKILL.md
plan-hash: 3bf66f6ee89e
next: 3

| phase | producer | consumer | path | sections | completion | note |
|---|---|---|---|---|---|---|
| 1 | analyst | architect | _workspace/01_analyst_findings.md | Findings; Gaps | complete | - |
| 2 | architect | reviewer | _workspace/02_architect_design.md | Design; Authority List | complete | - |
| 3 | reviewer | builder | _workspace/03_reviewer_verdict.md | Verdict; Reasons | partial | missing: Reasons |
| 4 | builder | qa | _workspace/04_builder_report.md | - | complete | - |
```

Now `ACTION` is `resume`, `PHASE` is 3 and `SUSPECT` is 4: the leftover report may describe a verdict that is about to change.

## 6. Claude chat and Claude Cowork

There is no shell to run the script, and whether a file survives into a new conversation is unverified — confirm in that surface before relying on it. The single-context fallback therefore does this: at the end of every phase section it writes the ledger table as an inline block labelled `STATE LEDGER`, with each phase's block counting as its file (`surfaces.md` section 2, rule 2). On "continue" in the same conversation it reads the latest block. In a new conversation the user pastes the last ledger block and the handoff blocks; the orchestrator applies R3 and R6 by hand and says which blocks it could not find. With no block at all there is nothing to resume: start from phase 1 and say so, and before a run-once phase ask the user whether it already ran, because no record of an earlier run can exist here. For a run-once phase the intent block is written before the outside call and the result block after it; an intent block with no result block is a half-done phase, so stop and ask as in O6. The fallback does not name a sub-agent, messaging or task primitive.

## 7. How it fits the existing Step 0 and workspace rules

- The three Step 0 branches stay as they are. The ledger is consulted only in the branch where `_workspace/` exists and the user asks to continue; a new input still moves the whole directory to `_workspace_{timestamp}/`, ledger included, and a moved workspace is not resumed.
- A partial re-run of a phase the user names takes priority over R6. The ledger is rebuilt afterwards, but it does not track that phases downstream of the one re-run are now out of date (see section 8). A run-once phase is the exception: O6 asks again before it repeats an effect.
- A Workflow run keeps `run_meta.json` and `resumeFromRunId` for resuming inside one run. The ledger decides which phase a new session starts with; the two do not replace each other. A `once` stage that did not return a result is not resumed with `resumeFromRunId`: its call may have gone out, so `resume` and O6 decide (rule O7).
- The freeze hashes of Mode B (`freeze_{phase}.sha`) are artefacts, not handoff rows, and stay as they are.
- This repo's own team keeps the same derivation by hand in the "Status at a glance" table of its workspace layout; nothing there changes.
- The ledger is not an Authority List. It needs no citation, and a harness that cites a source for its handoff layout does so in its own Authority List.

## 8. Does not cover

- A worker that wrote every heading and then stopped reads as complete. The check is on headings, not content.
- Nothing is hashed and no timestamp is read, so a file edited after a later phase used it still reads as complete, and a downstream phase is not marked out of date. R8 catches only a complete row that sits after an unfinished one.
- Table order is the resume order. Two independent phases are not run in parallel by the script.
- Two writers of `00_state.md` at once are not handled; only the orchestrator writes it.
- Past blockers are not kept. A ledger rebuilt without the old file loses them (R5), which is why an unreadable ledger stops one resume to ask (R9).
- A phase file over 8 MiB reads as partial, and a symlink that leaves the project stops the run; a symlink that stays inside is followed.
- The live proof is a model-session fixture, not a test that runs here: stop a Mode C harness after phase 2, start a fresh session with "continue", and check that the phase 1 and 2 files keep their modification times, that the reply quotes `PHASE: 3` and that phase 3 starts. A pass shows one model following the pointer on one date; it does not guarantee it.
- On chat and Cowork the inline block is a convention a model follows, not a check that runs.
- A run-once phase whose file is absent reads as not started, unless the previous ledger had it partial or complete (O2). A worker that made its outside call and stopped before saving its first section leaves nothing to find, and O5 closes that gap only when the worker follows it.
- The vanished-file stop reads the previous ledger, so it needs one. After a plan change (R5), or when the ledger was deleted or unreadable, there is no evidence, and an absent run-once file reads as not started.
- Changing a `once` row's path or marker between runs defeats the protection: a new path has no history, and a `safe` row is read as before. A path edit changes the plan hash and prints `DRIFT: plan changed`; a marker edit alone prints nothing. Nothing stops either.
- The `once` marker is the author's declaration. An effect left unmarked, or marked `safe`, is replayed on resume, and nothing detects it.
- Half done is read from headings. A worker that writes its last section before the call, or writes every heading and then fails, reads as complete.
- Whether the effect happened is the user's knowledge or the outside system's log. The ledger asks and never checks, and `HALF-DONE` shows only what the files show.
- An idempotency key accepted by the connector is the real fix, because it lets the outside system refuse the second call. The ledger only records the key. Whether a given connector accepts one is not known from this repository.
- A test or dry run of a harness whose agent calls a live sending connector (SMS, email, chat post, page publish, CRM write) sends for real, and a fresh test run starts with no ledger. Test such a harness against a stub or sandbox connector with synthetic recipients; the ledger does not see test runs.
- A worker that stopped after saving its first section but before its outside call also reads as half done, so that crash costs the user one question. The ledger prefers that question to a second message.
- A copy of `state_ledger.py` made before section 3a does not know the sixth column and stops a plan that has it with `stop-no-plan`: it fails closed, and the fix is to copy the current script.
- A phase downstream of a re-run is still not marked out of date (the limit above); a run-once phase that already went out is not re-run to catch up.
