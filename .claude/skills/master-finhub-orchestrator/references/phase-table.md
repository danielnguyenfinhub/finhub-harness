# Phase table — inputs, outputs, re-run hand-off

Use this when Phase 0 picks a partial re-run: find the agent, pass the "Prior output" paths, then run only the "Invalidates" phases.

| Phase | Agent | Mode | model / subagent_type | Reads | Writes | Prior output passed on re-run | Invalidates downstream |
|---|---|---|---|---|---|---|---|
| 0 | orchestrator | none | — | `_workspace/` presence, user request | `_workspace/00_input/request.md` | — | — |
| 1 | reference-miner ×6 | sub, bg, parallel | sonnet / Explore | `references/<submodule>/**`, `00_input/` | (returned) → orchestrator saves `01_reference-miner_{submodule}_portmap.md` | `01_reference-miner_{submodule}_portmap.md` | Phase 2 (architect re-reads that map) |
| 2 | strategy-architect | named agent | opus / strategy-architect | all six `01_*_portmap.md`, `00_input/`, latest verdict | `02_strategy-architect_slices.md` | `02_strategy-architect_slices.md`, `02_adversarial-risk-judge_verdict.md` | judge audit; slices whose claims changed |
| 2 | adversarial-risk-judge | fresh agent per round | opus / adversarial-risk-judge | `02_strategy-architect_slices.md`, cited `references/` lines | `02_adversarial-risk-judge_verdict.md` | previous verdict | builder for slices with changed verdicts |
| 3 | runtime-builder | sub | sonnet / general-purpose | both 02 files; on retry `03_*_slice{N}.md` | `src/master_finhub/**`, `tests/**`, `03_runtime-builder_slice{N}.md` | `03_runtime-builder_slice{N}.md`, `03_boundary-qa_slice{N}.md` | QA slice N |
| 3 | boundary-qa | sub | sonnet / general-purpose | 02 slices, `03_runtime-builder_slice{N}.md`, code | `03_boundary-qa_slice{N}.md` | previous `03_boundary-qa_slice{N}.md` | Phase 4 |
| 4 | boundary-qa | sub | sonnet / general-purpose | all 02 + 03 files, code | `04_boundary-qa_report.md` | previous report | — |

## Partial-request routing

| Daniel says | Re-run | Then |
|---|---|---|
| "re-mine dify" / "re-run the miners" | reference-miner (named submodules) | Phase 2 → affected slices |
| "re-run only the judge" | adversarial-risk-judge as a fresh unnamed sub-agent; `SendMessage` the named architect only if REJECTED > 0 | builder for changed verdicts |
| "redesign slice N" / "after I changed the spec" (same goal) | Phase 2 agents | builder from slice N |
| "rebuild slice N" / "re-run the builder" | runtime-builder slice N | boundary-qa slice N |
| "re-run QA" / "verify the build" | boundary-qa (slice N or all) | Phase 4 |
| "continue to the next slice" | runtime-builder for first slice without `RESULT: PASS` | boundary-qa, Phase 4 |
| "final report" | Phase 4 only | — |

## Slice order (Part B)

| # | Slice | Proof |
|---|---|---|
| 1 | `runtime/loop.py` + `tools/builtins/echo.py` + `cli.py` | `python -m master_finhub.cli "echo hi"` → `hi`; `tests/test_loop.py` |
| 2 | `runtime/context.py` | 3000-token result clipped; call/result pairs balanced |
| 3 | `tools/safety.py` + `sandbox/workspace.py` | path traversal rejected; `rm -rf /` blocked |
| 4 | `runtime/router.py` | profile `judge`→opus, `miner`→sonnet |
| 5 | `orchestration/dag_engine.py` checkpoint | kill after step 2, resume at 3 |
| 6 | `dag_engine.py` executor (`graphlib.TopologicalSorter`) | diamond order; step limit halts |
| 7 | `orchestration/modes/*`, `message_bus.py` | two fake agents exchange a message |
| 8 | `sandbox/docker_engine.py`, `stream.py` | skip without docker; else echo in container |
| 9 | `tools/mcp/client.py` | stub stdio server round-trip |
| 10 | `server/app.py`, `sse.py` | client receives PING then event |
| 11 | `src/master_finhub/evals/runner.py`, `evals/verifiers.py` | one benchmark pass/fail |
| 12 | `factory/*` | deferred (YAGNI) |
