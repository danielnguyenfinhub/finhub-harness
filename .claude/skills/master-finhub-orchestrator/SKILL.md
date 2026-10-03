---
name: master-finhub-orchestrator
description: "Master FinHub harness orchestrator (하이브리드). Runs the six-agent team that mines the seven pinned reference repos, ranks their capabilities into a backlog, designs runtime slices or the adoption of one backlog item with an adversarially audited Authority List, then builds and verifies it (Python runtime under src/master_finhub/, or the finhub-harness plugin under skills/ and .claude/) one design at a time. ALWAYS use when Daniel says: build the master finhub runtime, run the finhub harness, improve finhub harness from the reference repos, pick the best capabilities from the other repos, capability backlog, what should we adopt next, adopt X from Y, build C3, build the next backlog item, build slice N, port compaction/loop/sandbox from deepseek/dify/crewai/openharness, re-run, update, partial re-run, improve the previous build, re-run only the judge, re-run only the builder, re-run the scout, re-run slice N, continue to the next slice, update the harness after I changed the spec. NOT for Mercury CRM, loan documents, video or marketing tasks, not for building a harness for another domain or borrowing a pattern into one (use the finhub-harness skill), not for run-feedback retrospectives (finhub-harness-evolve), and not for creating MCP servers."
---

# Master FinHub Orchestrator

Coordinates reference-miner, capability-scout, strategy-architect, adversarial-risk-judge, runtime-builder and boundary-qa. Target surface: Claude Code only (the team uses `Agent`, named agents and `SendMessage`; there is no chat or Cowork fallback for this orchestrator). Why hybrid: mining, ranking and building are independent and verifiable by commands (sub-agents are cheaper and isolated), while design-vs-audit needs a real back-and-forth (a named architect resumed with SendMessage, audited by a fresh judge each round).

Two goals share this team. **Runtime build**: design and build the Python runtime slices (Phase 1 → 2 → 3 → 4). **Capability adoption**: learn from the seven reference repos, rank what is worth adopting, and build the picked items into the plugin or the runtime (Phase 1 → 1b → stop for Daniel's pick → 2 → 3 per item → 4). Phase 0 decides which goal the request is.

## 실행 모드: 하이브리드

| Phase | 모드 | 이유 |
|-------|------|------|
| Phase 0 (context check) | 없음 | Decide goal and initial / partial re-run / new run before spending tokens |
| Phase 1 (reference mining) | 서브 에이전트 | Seven independent read-only sweeps, no inter-agent talk needed |
| Phase 1b (capability ranking) | 서브 에이전트 | One scout reads all maps once and writes the backlog; Daniel picks |
| Phase 2 (strategy + risk debate) | 에이전트 팀 | Architect and judge iterate via SendMessage until 0 REJECTED |
| Phase 3 (build) | 서브 에이전트 | One builder then one QA per slice or item; each is self-contained |
| Phase 4 (verification report) | 서브 에이전트 | Single QA agent, objective commands, no judgement debate |

Full per-phase inputs/outputs: `references/phase-table.md`. Workspace file naming: `references/workspace-layout.md`.

## 에이전트 구성

| 팀원 | 에이전트 타입 | 역할 | 스킬 | 출력 |
|------|-------------|------|------|------|
| reference-miner ×7 | Explore (sonnet) | Port map for one submodule | reference-mining | `_workspace/01_reference-miner_{submodule}_portmap.md` |
| capability-scout | capability-scout (opus) | Ranked adoption backlog from all seven maps | capability-triage | `_workspace/01b_capability-scout_backlog.md` |
| strategy-architect | strategy-architect (opus) | Slice design or one adoption design + Authority List | runtime-slice-design | `_workspace/02_strategy-architect_slices.md` or `_02_strategy-architect_<item>.md` |
| adversarial-risk-judge | adversarial-risk-judge (opus) | Fresh-context audit of Authority List | adversarial-audit | `_workspace/02_adversarial-risk-judge_verdict.md` or `..._<item>_r<k>.md` |
| runtime-builder | general-purpose (sonnet) | Build one slice or one adoption, gates per target | runtime-slice-design (+ finhub-build-discipline, superpowers:test-driven-development) | `src/`, `tests/` or `skills/`, `.claude/`; `_workspace/03_runtime-builder_{slice{N}\|<item>}.md` |
| boundary-qa | general-purpose (sonnet) | Cross-boundary QA + final report | boundary-qa | `_workspace/03_boundary-qa_{slice{N}\|<item>}.md`, `_workspace/04_boundary-qa_report.md` |

Models are tiered (sonnet for ingestion/build/QA, opus for design/judgement) per Daniel's global CLAUDE.md §8 — recorded in the repo CLAUDE.md 변경 이력.

## 워크플로우

### Phase 0: Context check
**실행 모드:** 없음 (컨텍스트 확인)

First name the goal: **runtime build** (slice numbers, "build the runtime", "continue to the next slice") or **capability adoption** ("improve from the reference repos", "pick the best", "backlog", "adopt X from Y", "build C3"). Then check whether `_workspace/` exists at the repo root and pick exactly one path:

1. **`_workspace/` absent → initial run.** Create `_workspace/00_input/`, copy the user's request and any spec text into `00_input/request.md` together with a `scope:` line (`runtime`, `factory` or `both`; adoption defaults to `both`), then run Phases 1–4 (adoption: 1 → 1b → pick → 2 → 3 → 4).
2. **`_workspace/` present + partial request** ("re-run only the judge", "rebuild slice 3", "improve the previous build", "re-run QA") → re-run only the affected agent. Pass it the prior output paths from `references/phase-table.md` and the instruction "prior output exists: read it and improve only the flagged part". Then run only the phases downstream of that agent that the change invalidates (judge re-run → builder slices whose claims changed → QA).
3. **`_workspace/` present + new input** (new spec, "after I changed the spec", a different goal) → move `_workspace/` to `_workspace_{YYYYMMDD_HHMMSS}/` (AEST timestamp), then start an initial run. Never delete old workspaces.

State which path you chose and why in one line before continuing.

### Phase 1: Reference mining
**실행 모드:** 서브 에이전트

Before spawning, decide per submodule whether to reuse: a prior `01_*_portmap.md` is reused only when its header SHA equals `git submodule status` for that path **and** its scope covers this run's `scope:` line (a map mined for runtime slices 8-11 does not cover a `both` run). Otherwise mine again, passing the prior map as "prior output exists" so unchanged rows are kept.

In ONE message, issue up to seven `Agent` calls in parallel, one per submodule to mine (`autogpt`, `openhands`, `dify`, `crewai`, `deepseek_harness`, `revfactory_harness`, `openharness`), each prompt carrying the `scope:` line:

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

### Phase 1b: Capability ranking (adoption goal only)
**실행 모드:** 서브 에이전트

```
Agent(
  description: "Rank capabilities into backlog",
  subagent_type: "capability-scout",
  model: "opus",
  run_in_background: true,
  prompt: "You are capability-scout. Read .claude/agents/capability-scout.md first.
    Rank all seven _workspace/01_*_portmap.md into _workspace/01b_capability-scout_backlog.md
    per the capability-triage skill. Request: _workspace/00_input/request.md."
)
```

When the backlog exists, **stop**. Relay to Daniel the ranked table (id, capability, target, licence, total, effort) and the top three in two lines each, then wait for his pick. Scores rank; Daniel decides. If his standing instruction for this run is "you decide", take the top row and say so. Never start Phase 2 for an item he has not named or delegated. On "re-rank" or after re-mining, re-run the scout with "prior output exists" and keep ids stable.

Pick rules, applied before Phase 2 starts:
- **"build Cn" with no `01b_capability-scout_backlog.md`** → run Phase 1 (reusing maps whose SHA and scope match) and Phase 1b first, then show the backlog and ask Daniel to confirm `Cn` is still his pick; never design from an id that has no row.
- **`Cn` is not in the backlog or Deferred tables** → say so, list the ids that exist, stop.
- **`Cn` is only in the Deferred table** (id, capability and total, no target, licence tier or proof) → re-run capability-scout with "prior output exists" and the instruction to promote `Cn` into a full Backlog row (displacing the lowest row if the table is full), show Daniel the promoted row, and continue only after he confirms it; the licence and dify rules below then apply to that row.
- **The picked row's licence tier is `reference`** (no confirmed licence row) → stop before Phase 2 and ask Daniel to confirm the licence row in `references/LICENSES.md`; nothing is designed from an unconfirmed source.
- **The picked row is pattern-only (dify)** → proceed, and the architect's prompt says every claim is `pattern`: fresh text, no mirrored names.

### Phase 2: Strategy + risk debate
**실행 모드:** 지속형 에이전트 협업 (v2: persistent named agents; no team object)

There is no team-create/team-delete tool in v2. Named agents launched in this session form the collaboration group automatically, and `SendMessage` resumes an agent with its context intact. The judge must audit in a **fresh context**, so it is launched anew for each round rather than resumed.

1. `Agent(name: "strategy-architect", subagent_type: "strategy-architect", model: "opus", run_in_background: false)` — runtime goal: read all seven `01_*_portmap.md` and the built code, write `02_strategy-architect_slices.md`; adoption goal: read the picked row of `01b_capability-scout_backlog.md`, re-open its port-map rows and the real code it touches, write `02_strategy-architect_<item>.md` per `runtime-slice-design` § Adoption design. Both end with the Authority List.
2. `Agent(subagent_type: "adversarial-risk-judge", model: "opus")` with **no name** and a prompt that names the design file and limits it to that file plus the cited `references/` lines and read-only simulation outside the repo — write the verdict (`02_adversarial-risk-judge_verdict.md`, or `..._<item>_r<k>.md` per round), totals line first.
3. If the totals show `REJECTED > 0`: `SendMessage({to: "strategy-architect"})` with the rejected claim ids and the judge's exact fixes, telling it to re-verify each by simulation and dispute with evidence if it disagrees; the architect revises in place. Then launch a **new** judge (fresh context, prior verdict paths passed as "prior output exists") for the next round. Max 3 rounds; if round 3 still has REJECTED > 0, stop and escalate to Daniel with the rejected claims side by side and both positions. Daniel may authorise further rounds one at a time; put `Extra round authorised by Daniel: <date>` in that round's launch prompt so the judge copies it into the verdict header.
4. Confirm both 02 files are saved in `_workspace/`.
5. Nothing to tear down. The architect stays addressable for later "redesign slice N" requests; sub-agent calls for Phase 3 follow directly.

### Phase 3: Build
**실행 모드:** 서브 에이전트

For each slice N in Part B order, or for the one picked backlog item. Set the placeholders first and use them in both prompts:

| placeholder | runtime slice N | adoption item `Cn` |
|---|---|---|
| `{unit}` | `slice{N}` | `Cn` |
| `{design}` | `_workspace/02_strategy-architect_slices.md` | `_workspace/02_strategy-architect_Cn.md` |
| `{verdict}` | `_workspace/02_adversarial-risk-judge_verdict.md` | the `_workspace/02_adversarial-risk-judge_Cn_r<k>.md` with the highest `k` (must show `REJECTED 0`) |

```
Agent(
  description: "Build {unit}",
  subagent_type: "general-purpose",
  model: "sonnet",
  prompt: "You are runtime-builder. Read .claude/agents/runtime-builder.md first.
    Build {unit} only from {design} and {verdict}; write _workspace/03_runtime-builder_{unit}.md."
)
Agent(
  description: "QA {unit}",
  subagent_type: "general-purpose",
  model: "sonnet",
  prompt: "You are boundary-qa. Read .claude/agents/boundary-qa.md first.
    Verify {unit} against {design} and _workspace/03_runtime-builder_{unit}.md;
    write _workspace/03_boundary-qa_{unit}.md.
    Standing reminder: do not edit src/, tests/ or any repo file; scratch work only in a temp
    directory, deleted afterwards; the report's first line starts with RESULT: PASS or RESULT: FAIL."
)
```

Run builder and QA sequentially (QA depends on builder). Read the first line of the QA report:
- `RESULT: PASS` → next slice; for an adoption, commit and push on the session's designated development branch (the branch the session instructions name, never `main`; if none is named, ask Daniel), open a draft PR, subscribe to it, then return to Phase 1b's backlog for Daniel's next pick (re-run the scout only if a pin or a map changed). Phase 4 for the adoption goal runs when Daniel asks for a "final report" or after his last pick of the session.
- `RESULT: FAIL` → re-run runtime-builder once with "prior output exists" and both report paths, then QA again. Still FAIL → stop; go to Phase 4 with the gap recorded.

Nothing is committed before `RESULT: PASS`; a stop hook asking for a commit mid-build is answered with that rule, not with a commit.

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
_workspace/00_input/request.md (+ scope: line)
   └─► Phase 1 (×7, parallel) ─► 01_reference-miner_{submodule}_portmap.md ×7
         ├─► [adoption] Phase 1b ─► 01b_capability-scout_backlog.md ─► STOP: Daniel picks <item>
         └─► Phase 2 agents ─► 02_strategy-architect_{slices|<item>}.md ◄─SendMessage─► 02_adversarial-risk-judge_{verdict|<item>_r<k>}.md
               └─► Phase 3 per slice or item ─► src/**, tests/**  or  skills/**, .claude/**, docs/**
                     ├─► 03_runtime-builder_{slice{N}|<item>}.md
                     └─► 03_boundary-qa_{slice{N}|<item>}.md ─► PASS ─► commit, PR, next pick
                           └─► Phase 4 ─► 04_boundary-qa_report.md
```

Scout reads all seven maps and the repo inventory, never the reference code. Judge reads only the design file + cited `references/` lines. Builder reads the design and its clean verdict. QA reads the design + builder report + the targeted files.

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| One miner fails or times out | Retry once; if still failing, proceed and record the gap in the architect's input (`portmap <submodule> missing`) |
| ≥3 miners fail | Stop; tell Daniel which submodules failed and the errors; ask whether to proceed |
| Scout's top row is licence-blocked or has no proof | The scout must already have moved it to Rejected; if it reached the table, re-run the scout with the rubric gates quoted and treat the backlog as invalid until then |
| Daniel picks an item outside the backlog | Design it anyway, but the architect marks every claim NET-NEW or cites a map row it adds; the scout is re-run afterwards so the backlog records the pick |
| Architect/judge still disagree after 3 rounds | Stop the loop; keep both positions side by side in the verdict; escalate to Daniel — never delete either view |
| Named agent stops mid-task | SendMessage to check status; restart once; if still down, record and escalate |
| Builder gate red | One retry with QA's defect list; still red → stop slices, report in Phase 4 |
| QA tool missing (pytest/ruff/black/mypy) | Report FAIL with the missing tool; tell Daniel to run `uv pip install -e .[dev]`; never mark PASS |
| `_workspace/` collision on new input | Move to `_workspace_{YYYYMMDD_HHMMSS}/`, never overwrite or delete |

## 테스트 시나리오

### 정상 흐름
1. Daniel: "build the master finhub runtime". No `_workspace/` → initial run.
2. Phase 1: seven Explore agents return; seven `01_*_portmap.md` files written.
3. Phase 2: named architect writes slices + Authority List; a fresh unnamed judge rejects 2 claims in round 1; `SendMessage` to the architect, it revises; a new judge's round 2 totals `REJECTED 0`; no teardown.
4. Phase 3: slice 1 build → QA PASS (`python -m master_finhub.cli "echo hi"` prints `hi`); slices 2 and 3 likewise.
5. Phase 4: `04_boundary-qa_report.md` lists 3 slices built, all four commands exit 0, gaps = slices 4–11 pending.

### 정상 흐름 (capability adoption)
1. Daniel: "improve finhub harness from the reference repos". `_workspace/` holds a runtime run → moved to `_workspace_{timestamp}/`; `00_input/request.md` gets `scope: both`.
2. Phase 1: seven maps; two reused (SHA and scope match), five re-mined with prior maps passed.
3. Phase 1b: scout writes a 9-row backlog; orchestrator relays the table and stops. Daniel: "C2".
4. Phase 2: architect writes `02_strategy-architect_C2.md` targeting `skills/finhub-harness/references/qa-agent-guide.md`; judge round 1 rejects one NET-NEW row for a vacuous verification; `SendMessage`; round 2 clean.
5. Phase 3: builder applies the insertions, greps match, packager exits 0, pytest unchanged; QA PASS; commit, draft PR, subscribe; back to the backlog for the next pick.

### 에러 흐름 (capability adoption)
1. Daniel: "build C5". Backlog row C5 has `licence: reference` (no LICENSES.md row). Orchestrator stops before Phase 2 and asks Daniel to confirm the licence row first; nothing is designed from an unconfirmed source.

### 에러 흐름
1. Daniel: "re-run slice 3". `_workspace/` present + partial request → only runtime-builder (slice 3) then boundary-qa.
2. QA reports `RESULT: FAIL` — tool schema declares `path: str` but the loop passes `{"file": ...}`.
3. Builder re-run once with both slice3 reports; fixes the call site; QA re-runs.
4. Still FAIL (mypy error) → slice loop stops; Phase 4 report lists slice 3 under Gaps with the verbatim mypy output and one NEXT step for Daniel.
