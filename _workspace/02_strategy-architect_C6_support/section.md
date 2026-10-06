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
