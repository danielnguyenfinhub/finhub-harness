---
name: doc-checklist
description: Existing one-worker team that checks a list of received documents against a required list and reports what is in and what is missing. Use for "check the document list", "what documents are missing", "re-run the checklist" or "redo the document check". Not for reading the contents of a document.
---

# Document checklist (an existing team in this project)

**Target surface:** Claude Code, Claude chat, Claude Cowork. **Execution mode:** Mode C, one worker; on chat and Cowork run it in one context.

## Delegation gate

1. Units: one. 2. Splitting buys a clean context for the comparison. 3. Writes: one file, named by the caller. 4. The worker needs Read and Write. 5. This skill accepts the result. 6. An item that cannot be matched is reported as `unclear`, never guessed.
Outcome: **one worker**.

## Step 1: Run the worker

Input: the path of a received-documents file that also states the required list, and the path to write to. Call `doc-checker` with both paths. On chat and Cowork, play the role in this context, labelled `[doc-checker]`.

## Step 2: Report

Return the worker's table path and its STATUS line. Nothing here sends, writes a record or publishes.

## Test scenarios

- Happy path: every required item matched; STATUS complete.
- Error path: the file does not state a required list; STATUS blocked, nothing written.
