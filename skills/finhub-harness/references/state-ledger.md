# State ledger: resuming a run after a context reset

> Handoff classes, adapted from references/meta_harness/docs/architecture/handoffs.md:13 (Apache-2.0). Field names, adapted from references/meta_harness/.agents/skills/harness/SKILL.md:158 (Apache-2.0). A small state file rebuilt on every change, adapted from references/openharness/src/openharness/autopilot/service.py:405 (MIT). A next step and a verified state per item that survive a reset, adapted from references/openharness/src/openharness/services/compact/__init__.py:566 (MIT). A halting state that outlives a reset, adapted from references/openharness/src/openharness/services/compact/__init__.py:635 (MIT). A blocked state that carries its reason, adapted from references/deepseek_harness/packages/goal/goal/src/types.ts:64 (MIT). A write through a temporary file that is then moved over the target, adapted from references/openharness/src/openharness/utils/fs.py:39 (MIT). The layout, the rebuild rule and the resume procedure are FinHub's own.

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
| R2 | The rows come from the `## Handoff files` table: five columns, at least two rows, unique phase ids, no empty section name, every path relative to the project root with no `..`, no drive letter and no UNC share. Every phase file and the ledger must also resolve inside the project with symlinks followed; one that does not stops the run (R9). |
| R3 | Completion comes from the file. Absent path: pending. Empty file, or a listed section missing as a heading outside code fences: partial, with `missing: <names>` in `note`. Every listed section present: complete. A heading matches only when its whole text equals the section name. A byte order mark is ignored, and a file over 8 MiB is partial with a note. Complete means the headings are present, not that the content is right or current. |
| R4 | Files win. Every rebuild rewrites the ledger from the files. Where the old ledger disagreed, `resume` prints a `DRIFT` line and decides from the files. |
| R5 | A blocker survives a rebuild only through the old ledger of the same plan (same `plan-hash`); a changed plan carries none and prints a `DRIFT` line. A blocked row stays blocked while its file is absent or partial and clears when the file is complete. With no readable old ledger a blocker cannot be known, and the row shows pending or partial. A plan edit clears every blocker, so tell the user which phases were blocked before the edit if you know. |
| R6 | The resume target is the first row that is not complete, in table order. None: stop, done. Blocked: stop and report the note; retry nothing. Partial: resume that phase and give its worker the path and the note. Pending: start that phase. |
| R7 | A rebuild or a resume writes only `_workspace/00_state.md`, through a temporary file in the same directory that replaces it, and not even that when its text would not change. No phase file is created, changed or deleted, and a complete phase is not run again unless the user names it. |
| R8 | A complete row after the resume row is listed as suspect: it may rest on an input that is about to change. Tell the user, and check it before using its file as an input. |
| R9 | A ledger that breaks R1, or whose phases do not match its own plan, is rebuilt from the files and reported as unreadable, and the decision is `stop-unreadable` (exit 3, unless every phase is complete): a blocker may have been lost, so ask the user, then run `resume` again, which reads the rebuilt ledger; if `resume` still says `stop-unreadable` after the user said yes, the ledger cannot be rewritten (a read-only `_workspace`): tell the user and stop. A plan that breaks R2, or is missing, stops with `stop-no-plan` and exit 2; ask the user. |
| R10 | A ledger that cannot be written (a directory in its place, a read-only workspace) is reported as `LEDGER: unwritable: <reason>`; the decision still comes from the files and the exit codes stay 0, 2 and 3. |

## 4. Procedure on Claude Code

Run the commands from the project root. `<skill dir>` is the directory of the finhub-harness skill and `<orchestrator>` is the file with the Handoff files table. The script lives in the plugin: if the session that resumes does not have the plugin installed, copy `state_ledger.py` into the generated harness (for example `.claude/skills/<orchestrator>/scripts/`) and write that path into the orchestrator's Step 0.

1. **At the start of a run** and **after every phase**: `python3 <skill dir>/scripts/state_ledger.py rebuild <orchestrator>`. A reset before the first phase ends still leaves a ledger. In a session that continues, run `resume` before any `rebuild`: `rebuild` overwrites an unreadable ledger and so skips the stop.
2. **Step 0, when `_workspace/` exists and the request is to continue**: `python3 <skill dir>/scripts/state_ledger.py resume <orchestrator>`. It rebuilds the ledger and prints `LEDGER`, `ACTION`, `PHASE`, `PATH`, `REASON`, one `DRIFT` line per disagreement (or `DRIFT: -`) and `SUSPECT`.
3. Act on `ACTION`:

| ACTION | Exit | The orchestrator |
|--------|------|------------------|
| start | 0 | runs `PHASE` from its first step, then continues in table order, rebuilding after each phase |
| resume | 0 | re-runs `PHASE` with `PATH` and `REASON` in the worker brief, and does not start the next phase before it is complete |
| stop-done | 3 | reports that every phase is complete and starts nothing |
| stop-blocked | 3 | reports `REASON`, retries nothing, and asks the user |
| stop-unreadable | 3 | says the ledger was unreadable and a blocker may have been lost, asks the user, and on a yes runs `resume` again |
| stop-no-plan | 2 | says the Handoff files table is missing or invalid, or a path leaves the project, and asks the user |

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

There is no shell to run the script, and whether a file survives into a new conversation is unverified — confirm in that surface before relying on it. The single-context fallback therefore does this: at the end of every phase section it writes the ledger table as an inline block labelled `STATE LEDGER`, with each phase's block counting as its file (`surfaces.md` section 2, rule 2). On "continue" in the same conversation it reads the latest block. In a new conversation the user pastes the last ledger block and the handoff blocks; the orchestrator applies R3 and R6 by hand and says which blocks it could not find. With no block at all there is nothing to resume: start from phase 1 and say so. The fallback does not name a sub-agent, messaging or task primitive.

## 7. How it fits the existing Step 0 and workspace rules

- The three Step 0 branches stay as they are. The ledger is consulted only in the branch where `_workspace/` exists and the user asks to continue; a new input still moves the whole directory to `_workspace_{timestamp}/`, ledger included, and a moved workspace is not resumed.
- A partial re-run of a phase the user names takes priority over R6. The ledger is rebuilt afterwards, but it does not track that phases downstream of the one re-run are now out of date (see section 8).
- A Workflow run keeps `run_meta.json` and `resumeFromRunId` for resuming inside one run. The ledger decides which phase a new session starts with; the two do not replace each other.
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
