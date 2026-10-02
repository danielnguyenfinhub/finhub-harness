---
name: master-finhub-orchestrator
description: "Master FinHub harness orchestrator (하이브리드). Runs the five-agent team that mines the pinned reference repos, designs runtime slices with an adversarially audited Authority List, then builds and verifies the Python runtime under src/master_finhub/ one slice at a time. ALWAYS use when Daniel says: build the master finhub runtime, run the finhub harness, build slice N, port compaction/loop/sandbox from deepseek/dify/crewai, re-run, update, partial re-run, improve the previous build, re-run only the judge, re-run only the builder, re-run slice N, continue to the next slice, update the harness after I changed the spec. NOT for Mercury CRM, loan documents, video or marketing tasks, and not for creating new skills or MCP servers."
---

# Master FinHub Orchestrator

Coordinates reference-miner, strategy-architect, adversarial-risk-judge, runtime-builder and boundary-qa. Why hybrid: mining and building are independent and verifiable by commands (sub-agents are cheaper and isolated), while design-vs-audit needs a real back-and-forth (a named architect resumed with SendMessage, audited by a fresh judge each round).

## 실행 모드: 하이브리드

| Phase | 모드 | 이유 |
|-------|------|------|
| Phase 0 (context check) | 없음 | Decide initial / partial re-run / new run before spending tokens |
| Phase 1 (reference mining) | 서브 에이전트 | Six independent read-only sweeps, no inter-agent talk needed |
| Phase 2 (strategy + risk debate) | 에이전트 팀 | Architect and judge iterate via SendMessage until 0 REJECTED |
| Phase 3 (build slices) | 서브 에이전트 | One builder then one QA per slice; each is self-contained |
| Phase 4 (verification report) | 서브 에이전트 | Single QA agent, objective commands, no judgement debate |

Full per-phase inputs/outputs: `references/phase-table.md`. Workspace file naming: `references/workspace-layout.md`.

## 에이전트 구성

| 팀원 | 에이전트 타입 | 역할 | 스킬 | 출력 |
|------|-------------|------|------|------|
| reference-miner ×6 | Explore (sonnet) | Port map for one submodule | reference-mining | `_workspace/01_reference-miner_{submodule}_portmap.md` |
| strategy-architect | strategy-architect (opus) | Slice design + Authority List | runtime-slice-design | `_workspace/02_strategy-architect_slices.md` |
| adversarial-risk-judge | adversarial-risk-judge (opus) | Fresh-context audit of Authority List | adversarial-audit | `_workspace/02_adversarial-risk-judge_verdict.md` |
| runtime-builder | general-purpose (sonnet) | Build one slice test-first | runtime-slice-design (+ finhub-build-discipline, superpowers:test-driven-development) | `src/`, `tests/`, `_workspace/03_runtime-builder_slice{N}.md` |
| boundary-qa | general-purpose (sonnet) | Cross-boundary QA + final report | boundary-qa | `_workspace/03_boundary-qa_slice{N}.md`, `_workspace/04_boundary-qa_report.md` |

Models are tiered (sonnet for ingestion/build/QA, opus for design/judgement) per Daniel's global CLAUDE.md §8 — recorded in the repo CLAUDE.md 변경 이력.

## 워크플로우

### Phase 0: Context check
**실행 모드:** 없음 (컨텍스트 확인)

Check whether `_workspace/` exists at the repo root, then pick exactly one path:

1. **`_workspace/` absent → initial run.** Create `_workspace/00_input/`, copy the user's request and any spec text into `00_input/request.md`, run Phases 1–4.
2. **`_workspace/` present + partial request** ("re-run only the judge", "rebuild slice 3", "improve the previous build", "re-run QA") → re-run only the affected agent. Pass it the prior output paths from `references/phase-table.md` and the instruction "prior output exists: read it and improve only the flagged part". Then run only the phases downstream of that agent that the change invalidates (judge re-run → builder slices whose claims changed → QA).
3. **`_workspace/` present + new input** (new spec, "after I changed the spec", a different goal) → move `_workspace/` to `_workspace_{YYYYMMDD_HHMMSS}/` (AEST timestamp), then start an initial run. Never delete old workspaces.

State which path you chose and why in one line before continuing.

### Phase 1: Reference mining
**실행 모드:** 서브 에이전트

In ONE message, issue six `Agent` calls in parallel, one per submodule (`autogpt`, `openhands`, `dify`, `crewai`, `deepseek_harness`, `revfactory_harness`):

```
Agent(
  description: "Mine dify port map",
  subagent_type: "Explore",
  model: "sonnet",
  run_in_background: true,
  prompt: "You are reference-miner. Read .claude/agents/reference-miner.md and
    .claude/skills/reference-mining/SKILL.md first. Submodule: dify.
    Spec: _workspace/00_input/request.md. Return the port map as your final message."
)
```

Explore agents are read-only, so when each completes, write its returned port map verbatim to `_workspace/01_reference-miner_{submodule}_portmap.md`. Do not edit the content.

### Phase 2: Strategy + risk debate
**실행 모드:** 지속형 에이전트 협업 (v2: persistent named agents; no team object)

There is no team-create/team-delete tool in v2. Named agents launched in this session form the collaboration group automatically, and `SendMessage` resumes an agent with its context intact. The judge must audit in a **fresh context**, so it is launched anew for each round rather than resumed.

1. `Agent(name: "strategy-architect", subagent_type: "strategy-architect", model: "opus", run_in_background: false)` — read all six `01_*_portmap.md` and the built code, write `02_strategy-architect_slices.md` ending with the Authority List.
2. `Agent(subagent_type: "adversarial-risk-judge", model: "opus")` with **no name** and a prompt that limits it to `02_strategy-architect_slices.md` plus the cited `references/` lines — write `02_adversarial-risk-judge_verdict.md`, totals line first.
3. If the totals show `REJECTED > 0`: `SendMessage({to: "strategy-architect"})` with the rejected claim ids and the judge's exact fixes; the architect revises in place. Then launch a **new** judge (fresh context, prior verdict path passed as "prior output exists") for the next round. Max 3 rounds; if round 3 still has REJECTED > 0, stop and escalate to Daniel with the rejected claims side by side.
4. Confirm both 02 files are saved in `_workspace/`.
5. Nothing to tear down. The architect stays addressable for later "redesign slice N" requests; sub-agent calls for Phase 3 follow directly.

### Phase 3: Build slices
**실행 모드:** 서브 에이전트

For each slice N in Part B order (default target this session: slices 1–3; continue on request):

```
Agent(
  description: "Build slice N",
  subagent_type: "general-purpose",
  model: "sonnet",
  prompt: "You are runtime-builder. Read .claude/agents/runtime-builder.md first.
    Build slice N only from _workspace/02_strategy-architect_slices.md and
    _workspace/02_adversarial-risk-judge_verdict.md."
)
Agent(
  description: "QA slice N",
  subagent_type: "general-purpose",
  model: "sonnet",
  prompt: "You are boundary-qa. Read .claude/agents/boundary-qa.md first.
    Verify slice N; write _workspace/03_boundary-qa_slice{N}.md.
    Standing reminder: do not edit src/, tests/ or any repo file; scratch work only in a temp
    directory, deleted afterwards; the report's first line starts with RESULT: PASS or RESULT: FAIL."
)
```

Run builder and QA sequentially (QA depends on builder). Read the first line of `03_boundary-qa_slice{N}.md`:
- `RESULT: PASS` → next slice.
- `RESULT: FAIL` → re-run runtime-builder once with "prior output exists" and both slice{N} report paths, then QA again. Still FAIL → stop the slice loop; go to Phase 4 with the gap recorded.

### Phase 4: Verification report
**실행 모드:** 서브 에이전트

```
Agent(
  description: "Final QA report",
  subagent_type: "general-purpose",
  model: "sonnet",
  prompt: "You are boundary-qa. Read .claude/agents/boundary-qa.md first.
    Write _workspace/04_boundary-qa_report.md from all _workspace/02_* and 03_* files,
    re-running pytest -q, ruff check src tests, black --check src tests, mypy --strict src.
    Standing reminder: do not edit src/, tests/ or any repo file; scratch work only in a temp
    directory, deleted afterwards."
)
```

Relay to Daniel: built / passed / gaps / one NEXT step, in plain English. Do not paste code.

## 데이터 흐름

```
_workspace/00_input/request.md
   └─► Phase 1 (×6, parallel) ─► 01_reference-miner_{submodule}_portmap.md ×6
         └─► Phase 2 agents ─► 02_strategy-architect_slices.md ◄─SendMessage─► 02_adversarial-risk-judge_verdict.md
               └─► Phase 3 per slice ─► src/master_finhub/**, tests/**
                     ├─► 03_runtime-builder_slice{N}.md
                     └─► 03_boundary-qa_slice{N}.md
                           └─► Phase 4 ─► 04_boundary-qa_report.md
```

Judge reads only `02_strategy-architect_slices.md` + cited `references/` lines. Builder reads both 02 files. QA reads 02 slices + 03 builder report + code.

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| One miner fails or times out | Retry once; if still failing, proceed and record the gap in the architect's input (`portmap <submodule> missing`) |
| ≥3 miners fail | Stop; tell Daniel which submodules failed and the errors; ask whether to proceed |
| Architect/judge still disagree after 3 rounds | Stop the loop; keep both positions side by side in the verdict; escalate to Daniel — never delete either view |
| Named agent stops mid-task | SendMessage to check status; restart once; if still down, record and escalate |
| Builder gate red | One retry with QA's defect list; still red → stop slices, report in Phase 4 |
| QA tool missing (pytest/ruff/black/mypy) | Report FAIL with the missing tool; tell Daniel to run `uv pip install -e .[dev]`; never mark PASS |
| `_workspace/` collision on new input | Move to `_workspace_{YYYYMMDD_HHMMSS}/`, never overwrite or delete |

## 테스트 시나리오

### 정상 흐름
1. Daniel: "build the master finhub runtime". No `_workspace/` → initial run.
2. Phase 1: six Explore agents return; six `01_*_portmap.md` files written.
3. Phase 2: named architect writes slices + Authority List; a fresh unnamed judge rejects 2 claims in round 1; `SendMessage` to the architect, it revises; a new judge's round 2 totals `REJECTED 0`; no teardown.
4. Phase 3: slice 1 build → QA PASS (`python -m master_finhub.cli "echo hi"` prints `hi`); slices 2 and 3 likewise.
5. Phase 4: `04_boundary-qa_report.md` lists 3 slices built, all four commands exit 0, gaps = slices 4–11 pending.

### 에러 흐름
1. Daniel: "re-run slice 3". `_workspace/` present + partial request → only runtime-builder (slice 3) then boundary-qa.
2. QA reports `RESULT: FAIL` — tool schema declares `path: str` but the loop passes `{"file": ...}`.
3. Builder re-run once with both slice3 reports; fixes the call site; QA re-runs.
4. Still FAIL (mypy error) → slice loop stops; Phase 4 report lists slice 3 under Gaps with the verbatim mypy output and one NEXT step for Daniel.
