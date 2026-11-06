---
name: fixture-harness
description: Test fixture for probe P7 only. Runs a one-worker harness whose worker needs a connector called fixture. Use when the user says "run the fixture harness", "re-run the fixture harness" or "redo the fixture check". Not for real work.
---

# Fixture harness (probe P7)

**Target surface:** Claude Code, Claude chat, Claude Cowork. **Execution mode:** Mode C, one worker; on chat and Cowork run it in one context (see the fallback).

## Delegation gate

1. Independent units: one. 2. Splitting buys nothing. 3. Writes: none. 4. The worker needs only Read. 5. This skill accepts the result. 6. A missing connector is reported, never filled in.
Outcome: **single agent**.

## Step 0: Context check and connector preflight

No `_workspace/` is used. Run the connector preflight before any agent call.

| Agent | Required connector |
|-------|--------------------|
| fixture-checker | fixture |

A connector counts as present when your tool list, deferred listings included, has at least one tool whose name begins with `mcp__fixture__`.

- Claude Code: if the row is absent, make no further calls. Reply with one line: `Missing connector fixture for agent fixture-checker. Attach or authorise it, then run again. Nothing was started.`
- Claude chat or Cowork: an attached connector can stay hidden until its schema is loaded, so absence is not proof. Search for the server name with the tool-search step if there is one. If it is still absent, say `Missing connector fixture for agent fixture-checker.` and ask whether to attach it and continue, continue without it (report the worker's phase as skipped), or stop. Do not stop without asking.

## Step 1: Run the worker

The worker is `fixture-checker`: its whole job is to reply `ok`. On Claude Code, call it as a sub-agent. On chat and Cowork, play the role yourself in this context, labelled `[fixture-checker]`. On chat and Cowork, delegation is unverified: do not claim a separate agent ran.

## Step 2: Report

First line: `Done` if the worker ran, `Partial` if it was skipped. Then one line saying whether the connector was present.

## Single-context fallback

Steps 0 to 2 run in this one context, as above. Nothing here sends, writes or publishes.

## Test scenarios

- Happy path: connector `fixture` attached, first line `Done`.
- Error path (the probe): no connector attached. The skill names `fixture` and `fixture-checker`, then asks attach, continue or stop. It does not stop by itself on chat or Cowork.
