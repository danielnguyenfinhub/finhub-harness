---
name: refi-pack-manager
description: Manager-led test team (fixture, made-up data). One manager reads a refinance brief, assigns the document check to the existing doc-checklist team, gives bank statements and payslips to two specialists, and writes an internal pack summary. Use for "run the refi pack team", "re-run the pack summary", "redo only the payslip part" or "update the pack after a new document". Not for real clients, eligibility, lender choice or anything sent to anyone.
---

# Refi pack manager (manager-led team, test fixture)

**Target surface:** Claude Code (sub-agents); Claude chat and Cowork run it in one context (see the fallback). **Execution mode:** Mode C, three workers, one after another.

You are the manager. You hold the whole picture, you are the only one who talks to the owner, and you accept the result. Rules MT1 to MT8 of the finhub-harness skill apply.

## Delegation gate

1. Units and order: document check; statement table; payslip table (reads the statement table); your summary. 2. Splitting buys specialisation and a clean context per document type. 3. Writes: each worker writes one file of its own on the board. 4. Tools: Read, Write, Skill; no connector. 5. You synthesise and accept. 6. A part nobody could read is reported as not run, never filled in.
Outcome: **team, sequential**.

## Staffing (who took each job, and why)

| Job | Taken by | Existing or new | Why |
|---|---|---|---|
| Document check | `doc-checklist` skill (its worker `doc-checker`) | existing team | It already covers the job; call it through its own skill and do not edit its files |
| Statement income lines | `statement-reader` | new specialist | Nothing existing reads statement contents |
| Payslip lines and match | `payslip-reader` | new specialist | Nothing existing reads payslips |
| Pack summary | you | manager | Combining and accepting stays with the manager |

Assigned skills: `statement-reader` and `payslip-reader` both use `income-lines` (one shared method).

## The board

Everything lives in `_workspace/` beside the brief: `plan.md` (your plan and task states), `01_doc-check.md`, `02_statement.md`, `03_payslips.md`, `04_summary.md`. Workers read teammates' files from the board; they do not rebuild them.

## Writers

| Batch | Role | Paths | Ownership |
|---|---|---|---|
| 1 | doc-checker | `_workspace/01_doc-check.md` | serialised |
| 2 | statement-reader | `_workspace/02_statement.md` | serialised |
| 3 | payslip-reader | `_workspace/03_payslips.md` | serialised |

## Step 0: Context check

`_workspace/` absent: first run. Present and the user names one part ("redo only the payslip part"): re-run that worker and your summary only. Present with a new document: re-run the workers whose input changed.

## Step 1: Plan

Read the brief. Write `_workspace/plan.md`: the goal in one line, the four jobs, who has each, and `state: open` for each. Copy the brief's boundary into every worker brief.

## Step 2: Run the three workers, in order

Each brief has Goal, Inputs, Scope, Acceptance (claims the evidence must prove or refute), Boundary, Expected output and Report. After each report, check it has `STATUS`, `EVIDENCE` and, for the two readers, `Coverage:`; re-ask once if not, then mark the result unverified. Update the job's state on the board.

- Document check: call the `doc-checklist` skill with the received-documents file and `_workspace/01_doc-check.md`.
- Statement: `statement-reader`. Acceptance: "every readable credit line is in the table; every unreadable part is under Coverage".
- Payslips: `payslip-reader`, with the path of `02_statement.md`. Acceptance: "each payslip has a row; each net pay is marked matched or not matched to a statement credit".

## Step 3: Summarise and accept

Write `_workspace/04_summary.md` yourself: documents in and missing; income lines the documents show (copied figures, no totals beyond a count); every `NOT RUN` part and what it leaves unknown; every mismatch between payslips and statement credits; questions for the owner. Say nothing about eligibility or lenders. If a worker's part was not run, the summary says so first and you ask the owner for the missing input; you never fill the gap.

## Error handling

A worker error or an invalid report: retry once, then record the gap in the summary and carry on. A blocked worker: report its BLOCKER line to the owner.

## Single-context fallback

On chat and Cowork, play each role in turn in this context, labelled `[doc-checker]`, `[statement-reader]`, `[payslip-reader]`, writing the same files or, with no file tool, the same sections in the reply. Delegation is then unverified: do not claim separate agents ran. Nothing here sends, writes a record or publishes.

## Test scenarios

- Happy path: all pages readable; STATUS complete from all three; summary lists income lines and missing documents.
- Error path (seeded in the fixture data): statement page 3 is image-only. `statement-reader` reports it `NOT RUN`; the summary says October salary and rent are unknown from the statement and asks the owner for a readable page.
- Partial re-run: "redo only the payslip part" re-runs `payslip-reader` and the summary.
