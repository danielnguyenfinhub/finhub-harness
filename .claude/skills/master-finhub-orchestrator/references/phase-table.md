# Phase table — inputs, outputs, re-run hand-off

Use this when Phase 0 picks a partial re-run: find the agent, pass the "Prior output" paths, then run only the "Invalidates" phases.

| Phase | Agent | Mode | model / subagent_type | Reads | Writes | Prior output passed on re-run | Invalidates downstream |
|---|---|---|---|---|---|---|---|
| 0 | orchestrator | none | — | `_workspace/` presence, user request | `_workspace/00_input/request.md` | — | — |
| 1 | reference-miner ×8 | sub, bg, parallel | sonnet / Explore | `references/<submodule>/**`, `00_input/` (scope line) | (returned) → orchestrator saves `01_reference-miner_{submodule}_portmap.md` | `01_reference-miner_{submodule}_portmap.md` | Phase 1b (scout re-ranks), Phase 2 (architect re-reads that map) |
| 1b | capability-scout | sub, bg | opus / capability-scout | all eight `01_*_portmap.md`, `references/LICENSES.md`, repo inventory, `00_input/` | `01b_capability-scout_backlog.md` | prior backlog (ids stable) | Daniel's pick; Phase 2 for the picked item |
| 2 | strategy-architect | named agent | opus / strategy-architect | all eight `01_*_portmap.md` (or the picked backlog row), `00_input/`, latest verdict | `02_strategy-architect_slices.md` or `02_strategy-architect_<item>.md` | the design file + its latest verdict | judge audit; slices or items whose claims changed |
| 2 | adversarial-risk-judge | fresh agent per round | opus / adversarial-risk-judge | the design file (`02_strategy-architect_slices.md` or `02_strategy-architect_<item>.md`), cited `references/` lines | `02_adversarial-risk-judge_verdict.md` (slices) or `02_adversarial-risk-judge_<item>_r<k>.md` (one per round) | previous verdict(s) | builder for slices or items with changed verdicts |
| 3 | runtime-builder | sub | sonnet / general-purpose | the design file + its clean verdict; on retry the matching `03_*` reports | `src/master_finhub/**`, `tests/**` (slice) or `skills/**`, `.claude/**`, `docs/**` (adoption); `03_runtime-builder_slice{N}.md` or `03_runtime-builder_<item>.md` | the two `03_*` reports for that slice or item | QA for that slice or item |
| 3 | boundary-qa | sub | sonnet / general-purpose | the design file, the builder report, the targeted files | `03_boundary-qa_slice{N}.md` or `03_boundary-qa_<item>.md` | previous QA report for that slice or item | commit + PR on PASS; Phase 4 |
| 4 | boundary-qa | sub | sonnet / general-purpose | all 02 + 03 files, code | `04_boundary-qa_report.md` | previous report | — |

Phase 4 timing: runtime goal, after the last slice of the run; adoption goal, after each item's QA PASS when Daniel asks for a "final report", otherwise the per-item QA report stands and Phase 4 runs once at the end of the session's picks.

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
| "re-rank" / "re-run the scout" / "what should we adopt next" | capability-scout with prior backlog | stop for Daniel's pick |
| "build C3" / "adopt C3" / "build the next backlog item" | Phase 2 for that item (architect + fresh judge), then Phase 3 for it | QA, commit + PR on PASS, back to the backlog |
| "design the adoption of C3" | Phase 2 only | — |

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
