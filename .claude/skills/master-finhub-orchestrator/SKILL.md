---
name: master-finhub-orchestrator
description: "Master FinHub harness orchestrator (하이브리드). Runs the six-agent team that mines the fourteen pinned reference repos, ranks their capabilities into a backlog, designs runtime slices or one backlog adoption with an adversarially audited Authority List, then builds and verifies it (runtime under src/master_finhub/, or the finhub-harness plugin) one design at a time. ALWAYS use when Daniel says: build the master finhub runtime, run the finhub harness, capability backlog, pick the best capabilities, what should we adopt next, adopt X from Y, build C3, build slice N, port compaction/loop/sandbox from deepseek/dify/crewai/openharness, re-run the judge/builder/scout/slice N, partial re-run, improve the previous build, update after I changed the spec. NOT for Mercury CRM, loan documents, video or marketing, not for building a harness for another domain (finhub-harness skill), not for retrospectives (finhub-harness-evolve), not for creating MCP servers."
---

# Master FinHub Orchestrator

Coordinates reference-miner, capability-scout, strategy-architect, adversarial-risk-judge, runtime-builder and boundary-qa. Target surface: Claude Code only (the team uses `Agent`, named agents and `SendMessage`; there is no chat or Cowork fallback for this orchestrator). Why hybrid: mining, ranking and building are independent and verifiable by commands (sub-agents are cheaper and isolated), while design-vs-audit needs a real back-and-forth (a named architect resumed with SendMessage, audited by a fresh judge each round).

Two goals share this team. **Runtime build**: design and build the Python runtime slices (Phase 1 → 2 → 3 → 4). **Capability adoption**: learn from the fourteen reference repos, rank what is worth adopting, and build the picked items into the plugin or the runtime (Phase 1 → 1b → stop for Daniel's pick → 2 → 3 per item → 4). Phase 0 decides which goal the request is.

## 실행 모드: 하이브리드

| Phase | 모드 | 이유 |
|-------|------|------|
| Phase 0 (context check) | 없음 | Decide goal and initial / partial re-run / new run before spending tokens |
| Phase 1 (reference mining) | 서브 에이전트 | Fourteen independent read-only sweeps, no inter-agent talk needed |
| Phase 1b (capability ranking) | 서브 에이전트 | One scout reads all maps once and writes the backlog; Daniel picks |
| Phase 2 (strategy + risk debate) | 에이전트 팀 | Architect and judge iterate via SendMessage until 0 REJECTED |
| Phase 3 (build) | 서브 에이전트 | One builder then one QA per slice or item; each is self-contained |
| Phase 4 (verification report) | 서브 에이전트 | Single QA agent, objective commands, no judgement debate |

Full per-phase inputs/outputs: `references/phase-table.md`. Workspace file naming: `references/workspace-layout.md`.

## 에이전트 구성

| 팀원 | 에이전트 타입 | 역할 | 스킬 | 출력 |
|------|-------------|------|------|------|
| reference-miner ×14 | Explore (sonnet) | Port map for one submodule | reference-mining | `_workspace/01_reference-miner_{submodule}_portmap.md` |
| capability-scout | capability-scout (opus) | Ranked adoption backlog from all fourteen maps | capability-triage | `_workspace/01b_capability-scout_backlog.md` |
| strategy-architect | strategy-architect (opus) | Slice design or one adoption design + Authority List | runtime-slice-design | `_workspace/02_strategy-architect_slices.md` or `_02_strategy-architect_<item>.md` |
| adversarial-risk-judge | adversarial-risk-judge (opus) | Fresh-context audit of Authority List | adversarial-audit | `_workspace/02_adversarial-risk-judge_verdict.md` or `..._<item>_r<k>.md` |
| runtime-builder | general-purpose (sonnet) | Build one slice or one adoption, gates per target | runtime-slice-design (+ finhub-build-discipline, superpowers:test-driven-development) | `src/`, `tests/` or `skills/`, `.claude/`; `_workspace/03_runtime-builder_{slice{N}\|<item>}.md` |
| boundary-qa | general-purpose (sonnet) | Cross-boundary QA + final report | boundary-qa | `_workspace/03_boundary-qa_{slice{N}\|<item>}.md`, `_workspace/04_boundary-qa_report.md` |

Models are tiered (sonnet for ingestion/build/QA, opus for design/judgement) per Daniel's global CLAUDE.md §8 — recorded in the repo CLAUDE.md 변경 이력.

## Rigor
The unit kind below is class `other` and its table row is `light` (lowered from `gated` on 2026-10-28, on Daniel's words 'Quick unless I say full (Recommended)', after he said the team was too heavy and too slow for small tasks). A unit is `master-finhub-unit/<unit>` (`master-finhub-unit/OR-S8`). Two lanes run under that row. **Quick** is the default: no architect, judge or QA agent; the lead builds and checks with the repo's own gates (see Lanes). **Full** is an item Daniel raises by saying full ('C28 full'): the judge and QA run as described below and the item is `gated` for that run. The table cannot express a raise, so the judge verdict and QA report of a Full item carry `RIGOR: gated unit=master-finhub-unit/<item> by=owner:daniel on=<the date Daniel said full>` and the lead checks that line itself. No agent selects, raises or lowers a level or a class; an agent that thinks a unit needs the other lane says so in one sentence naming the risk to Daniel and continues in the lane he assigned. A Quick item needs no ledger row. A unit runs below its table row only through a `rigor:<scope>/<item>` row in `WAIVERS.md`, and a table row is lowered only through a `rigor:<scope>/table` row, both from Daniel's own quoted words and approval, and both committed by a gated unit of their own that declares `WAIVERS.md` only (quality-gates 3-10). A new scope cannot be lowered this way, because the receipt must name a scope that the table already lists; add no scope without asking Daniel.

| scope | class | level | assigned-by | on |
|---|---|---|---|---|
| master-finhub-unit | other | light | owner:daniel | 2026-10-28 |

(adapted from references/openrig/docs/reference/sdlc-conventions.md:20-24 (Apache-2.0))

## Lanes
**Quick (default).** When a pick or a task arrives, say the lane in one line ("C33: quick lane"), then:
1. Plan in at most ten lines in `_workspace/quick_<item>.md`: what changes, the files, the proof command, and each source cite with its licence tier. No Authority List, no design file.
2. Build it yourself, test first. One builder agent is allowed for a large mechanical edit. No architect, judge or QA agent.
3. When the change is done, run the repo's own gates once: the new and touched tests, then the full suite once; ruff, black and mypy as CI runs them; `lint_harness.py`; `check-harness-refs.sh`; the packager when a shipped file changed; `cite_check.py` over any cite you wrote; the attribution line, the 8-word scan and the Hangul check on new prose. For each new refusal or rule, break it by hand in a scratch copy and show a test fails (`mutant_gate.py classify` when you pre-registered the test and sig; a plain failing run is enough otherwise).
4. Before the commit run `waiver_ledger.py check WAIVERS.md` and `rigor_check.py check` for the unit `master-finhub-unit/<item>` with no report arguments (Phase 3 shows the call). Relay every NOTICE and EXPIRED line to Daniel.
5. Commit, push, open a draft PR, subscribe. The PR body is one page: what changed, the lane ("Quick lane: no judge, no QA agent"), the checks you ran and their results, and what was not verified.
In Quick you write one sentence naming the risk to Daniel, and continue, when the unit would change the command guard or the credential-path denylist (`src/master_finhub/tools/safety.py`, `src/master_finhub/tools/sensitive_paths.py`), send, publish or pay, or carry client-facing text. A change to `WAIVERS.md` or to the Rigor table is always a unit of its own, run `gated`. If a Quick plan grows past ten lines or eight files, say so in one sentence and offer Full.

**Full (only when Daniel says full).** Phases 1 to 4 below, with the judge and QA gated. The same process, with these cuts that keep every gate:
- The architect's brief asks for about 25 Authority List rows at most and about 15 pre-registered mutants at most, and for no live paid session unless Daniel asks for one.
- From judge round 2 the brief says: audit the rows that changed, the new rows and the fixed rows; carry the rows whose text is unchanged by id under rule C4 (quality-gates 3-7), and re-open one of them only when the change could have broken it.
- A revision batches every point of a verdict into one `SendMessage`, and the architect runs the cite check and the full matrix once, after the last fix.

## 워크플로우

### Phase 0: Context check
**실행 모드:** 없음 (컨텍스트 확인)

First name the goal: **runtime build** (slice numbers, "build the runtime", "continue to the next slice") or **capability adoption** ("improve from the reference repos", "pick the best", "backlog", "adopt X from Y", "build C3"). Then check whether `_workspace/` exists at the repo root and pick exactly one path:

1. **`_workspace/` absent → initial run.** Create `_workspace/00_input/`, copy the user's request and any spec text into `00_input/request.md` together with a `scope:` line (`runtime`, `factory` or `both`; adoption defaults to `both`), then run Phases 1–4 (adoption: 1 → 1b → pick → 2 → 3 → 4).
2. **`_workspace/` present + partial request** ("re-run only the judge", "rebuild slice 3", "improve the previous build", "re-run QA") → re-run only the affected agent. Pass it the prior output paths from `references/phase-table.md` and the instruction "prior output exists: read it and improve only the flagged part". Then run only the phases downstream of that agent that the change invalidates (judge re-run → builder slices whose claims changed → QA).
3. **`_workspace/` present + new input** (new spec, "after I changed the spec", a different goal) → move `_workspace/` to `_workspace_{YYYYMMDD_HHMMSS}/` (AEST timestamp), then start an initial run. Never delete old workspaces.

State which path you chose and why in one line before continuing, and name the lane (see Lanes): Quick unless Daniel's request says full.

### Phase 1: Reference mining
**실행 모드:** 서브 에이전트

Before spawning, decide per submodule whether to reuse: a prior `01_*_portmap.md` is reused only when its header SHA equals `git submodule status` for that path **and** its scope covers this run's `scope:` line (a map mined for runtime slices 8-11 does not cover a `both` run). Otherwise mine again, passing the prior map as "prior output exists" so unchanged rows are kept.

In ONE message, issue up to fourteen `Agent` calls in parallel, one per submodule to mine (`autogpt`, `openhands`, `dify`, `crewai`, `deepseek_harness`, `revfactory_harness`, `openharness`, `meta_harness`, `openrig`, `harness_100`, `hive`, `cowagent`, `repository_harness`, `paperclip`), each prompt carrying the `scope:` line:

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
    Rank all fourteen _workspace/01_*_portmap.md into _workspace/01b_capability-scout_backlog.md
    per the capability-triage skill. Request: _workspace/00_input/request.md."
)
```

When the backlog exists, **stop**. Relay to Daniel the ranked table (id, capability, target, licence, total, effort) and the top three in two lines each, then wait for his pick. Scores rank; Daniel decides. If his standing instruction for this run is "you decide", take the top row and say so. Never start Phase 2 for an item he has not named or delegated. On "re-rank" or after re-mining, re-run the scout with "prior output exists" and keep ids stable.

Pick rules, applied before Phase 2 starts:
- **Lane.** Quick unless Daniel says full. A Quick pick skips Phase 2 and Phase 3 and follows the Quick steps of Lanes; the rules below about the licence tier and pattern-only rows still apply to it.
- **"build Cn" with no `01b_capability-scout_backlog.md`** → run Phase 1 (reusing maps whose SHA and scope match) and Phase 1b first, then show the backlog and ask Daniel to confirm `Cn` is still his pick; never design from an id that has no row.
- **`Cn` is not in the backlog or Deferred tables** → say so, list the ids that exist, stop.
- **`Cn` is only in the Deferred table** (id, capability and total, no target, licence tier or proof) → re-run capability-scout with "prior output exists" and the instruction to promote `Cn` into a full Backlog row (displacing the lowest row if the table is full), show Daniel the promoted row, and continue only after he confirms it; the licence and dify rules below then apply to that row.
- **The picked row's licence tier is `reference`** (no confirmed licence row) → stop before Phase 2 and ask Daniel to confirm the licence row in `references/LICENSES.md`; nothing is designed from an unconfirmed source.
- **The picked row is pattern-only (dify)** → proceed, and the architect's prompt says every claim is `pattern`: fresh text, no mirrored names.

### Phase 2: Strategy + risk debate
(Full lane only.)
**실행 모드:** 지속형 에이전트 협업 (v2: persistent named agents; no team object)

There is no team-create/team-delete tool in v2. Named agents launched in this session form the collaboration group automatically, and `SendMessage` resumes an agent with its context intact. The judge must audit in a **fresh context**, so it is launched anew for each round rather than resumed.

1. `Agent(name: "strategy-architect", subagent_type: "strategy-architect", model: "opus", run_in_background: false)` — runtime goal: read all fourteen `01_*_portmap.md` and the built code, write `02_strategy-architect_slices.md`; adoption goal: read the picked row of `01b_capability-scout_backlog.md`, re-open its port-map rows and the real code it touches, write `02_strategy-architect_<item>.md` per `runtime-slice-design` § Adoption design. Both end with the Authority List.
2. `Agent(subagent_type: "adversarial-risk-judge", model: "opus")` with **no name** and a prompt that names the design file and limits it to that file plus the cited `references/` lines and read-only simulation outside the repo — write the verdict (`02_adversarial-risk-judge_verdict.md`, or `..._<item>_r<k>.md` per round), totals line first, then its `CANDIDATE:` and `CARRIED:` lines (`skills/finhub-harness/references/quality-gates.md` §3-7). The judge computes the line with `candidate_id.py id --paths <design file> [<patch file>]`; when the design carries a patch, both files go on it.
3. If the totals show `REJECTED > 0`: `SendMessage({to: "strategy-architect"})` with the rejected claim ids and the judge's exact fixes, telling it to re-verify each by simulation and dispute with evidence if it disagrees; the architect revises in place. Then launch a **new** judge (fresh context, prior verdict paths passed as "prior output exists") for the next round. Max 3 rounds; if round 3 still has REJECTED > 0, stop and escalate to Daniel with the rejected claims side by side and both positions. Daniel may authorise further rounds one at a time; put `Extra round authorised by Daniel: <date>` in that round's launch prompt so the judge copies it into the verdict header.
4. Confirm both 02 files are saved in `_workspace/`, and run `python3 skills/finhub-harness/scripts/candidate_id.py check {verdict}` on the clean verdict. Exit 0 lets Phase 3 start; exit 3 means the design changed after the verdict, so launch a new judge. (adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0))
5. Put the unit's row as a `Rigor:` line, `Rigor: gated unit=master-finhub-unit/{unit} by=owner:daniel on=<the date Daniel said full>`, in the judge's launch prompt and in every builder and QA brief. The judge's lines run TOTALS, CANDIDATE, CARRIED, RIGOR; the QA report's lines run RESULT, CANDIDATE, CARRIED, BASE, RIGOR. A verdict written before this rule existed carries no RIGOR line and is not passed to the check below.
6. Nothing to tear down. The architect stays addressable for later "redesign slice N" requests; sub-agent calls for Phase 3 follow directly.

### Phase 3: Build
(Full lane only. A Quick unit commits through the Quick steps of Lanes.)
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
    Candidate: {CANDIDATE line};
    Base: {the Base line for this unit, recorded once before its first builder spawn: git:<12 hex> excl=<12 hex or none>, or none};
    Declared: {the design's Files paths, comma-separated};
    Earlier: {each kept _workspace/03_boundary-qa_{unit}_r<k>.md of this unit, comma-separated, or none};
    write _workspace/03_boundary-qa_{unit}.md.
    Standing reminder: do not edit src/, tests/ or any repo file; scratch work only in a temp
    directory, deleted afterwards; the report's first line starts with RESULT: PASS or RESULT: FAIL."
)
```

Run builder and QA sequentially (QA depends on builder). Before you spawn the first builder for this unit, run the Base step of `skills/finhub-harness/references/qa-agent-guide.md` section 7-10 (`git rev-parse --short=12 HEAD` and the `.git/info/exclude` digest) and keep its output as the `Base:` line, `Base: git:<output> excl=<output>` (`Base: none` without git). Record it once per unit and write it to `_workspace/base_{unit}.txt` in the same step: a builder re-run for the same unit carries that same line, so a commit made in an earlier round stays in the drift listing. On a resume, read the line from that file and never record a new Base for a unit once a builder for it has run, because a Base recorded after a builder commit hides that commit; if the file is missing, stop that unit and ask the user (quality-gates 3-8; adapted from references/openrig/docs/reference/wave-sdlc.md:22-24 (Apache-2.0)). After the builder returns, run `python3 skills/finhub-harness/scripts/candidate_id.py id` yourself and add its `CANDIDATE:` line to the QA prompt as `Candidate: <line>`; a builder retry changes the tree, so the next QA prompt carries a new line. Read the first line of the QA report, then run `python3 skills/finhub-harness/scripts/candidate_id.py check _workspace/03_boundary-qa_{unit}.md`:
- `RESULT: PASS` with `check` exit 0 and `CARRIED: -` → next slice; for an adoption, commit and push on the session's designated development branch (the branch the session instructions name, never `main`; if none is named, ask Daniel), open a draft PR, subscribe to it, then return to Phase 1b's backlog for Daniel's next pick (re-run the scout only if a pin or a map changed). Phase 4 for the adoption goal runs when Daniel asks for a "final report" or after his last pick of the session.
- `RESULT: FAIL` → re-run runtime-builder once with "prior output exists" and both report paths; then move the QA report to `_workspace/03_boundary-qa_{unit}_r<k>.md` (`k` one more than the highest `n` of the unit's names matching `_r[0-9]+.md`, 1 when none; `test ! -e` the new name first and stop if it is taken) and run QA again with that path on its `Earlier:` line. Still FAIL → stop; go to Phase 4 with the gap recorded and every kept report named. The step that checks reports never passes a kept report to `candidate_id.py check`, `finding_tags.py check` or `rigor_check.py` (`skills/finhub-harness/references/quality-gates.md` §3-6). (adapted from references/paperclip/.agents/skills/verify-paperclip/SKILL.md:192 (MIT))

`check` exit 3 on a PASS means the tree moved after QA looked at it: do not commit, run QA on the tree as it is now. Run `python3 skills/finhub-harness/scripts/finding_tags.py check _workspace/03_boundary-qa_{unit}.md` after `candidate_id.py check`: exit 4 sends the report back once to boundary-qa with the lines it printed; that is a refusal of the record, not a stale verdict (quality-gates 3-8). A refusal of a drift row is a refusal like any other: it goes back once with the lines the checker printed. After the commit, `check --tree-only` passing with an empty `git status --short` shows the commit holds the tree QA judged; the plain `check` is then stale, so a PASS licenses one commit.

Before the commit, in the same step, run `python3 skills/finhub-harness/scripts/waiver_ledger.py check WAIVERS.md` on the tree as it is at that moment: any non-zero exit (4: a row refused or expired; 2: the file missing or unreadable) means do not commit, and `WAIVERS.md` is never edited to make it pass. You are the one who relays: show Daniel every `NOTICE`, `EXPIRED` and problem line in your report before any commit, and ask him to renew or drop each row with new words. A renewal or closure is a unit of its own: it declares `WAIVERS.md` and nothing else, moves the candidate id and forces a QA re-run, an accepted cost. When a unit adds or changes a row, put the owner's words (or the path of the record that holds them) in the builder and QA briefs, and put the full text of the `CLAUDE.md` row in the builder's brief, so that nothing is filled in after QA moves the id (quality-gates 3-9; adapted from references/openrig/scripts/gate-lane-ledger.mjs:60-85 (Apache-2.0)).

For a Quick unit run the `rigor_check.py` call below with no report arguments and put its `EFFECTIVE:` line in the PR body. For a Full unit skip it, because the table row is `light` and the script cannot ask for the reports of a raised item; check instead that the QA report's fifth line is `RIGOR: gated unit=master-finhub-unit/{unit} by=owner:daniel on=<the date Daniel said full>`, and keep every other check in this phase.

In the same step, after `candidate_id.py check` and `finding_tags.py check`, write the previous committed copy of the table, `git show HEAD:.claude/skills/master-finhub-orchestrator/SKILL.md > _workspace/prev_rigor_{unit}.md` (`-` only for a file with no earlier commit), and the changed paths, `{ git diff --name-only HEAD -- . ':(exclude)_workspace'; git ls-files --others --exclude-standard -- . ':(exclude)_workspace'; } > _workspace/changed_{unit}.txt`. Then run `python3 skills/finhub-harness/scripts/rigor_check.py check .claude/skills/master-finhub-orchestrator/SKILL.md WAIVERS.md master-finhub-unit/{unit} _workspace/prev_rigor_{unit}.md _workspace/changed_{unit}.txt _workspace/03_boundary-qa_{unit}.md` and add the judge verdict of the unit when it carries a RIGOR line: any non-zero exit means do not commit. Relay every `DOWNGRADE:`, `LOWERED:` and `NOTICE:` line to Daniel in your report before the commit. You never write a `rigor:` row or edit the table to make the check pass; both come only from Daniel's words and approval, and a downgrade row is committed by a gated unit of its own. The final report's second line is `RIGOR: no unit ran light` or one line per light item or lowered row (quality-gates 3-10; adapted from references/openrig/docs/reference/product-journey-sdlc.md:329-332 (Apache-2.0)).

For an adoption the `CLAUDE.md` change-history row belongs inside the unit: the builder adds it before QA so the judged tree includes it, and nobody edits it between `check` and the commit, because that moves the id and the commit is refused. A clone without the local `.git/info/exclude` entries must list `.claude-flow/` (and the other hook folders, such as `.codegraph/`) there before the first `id`, or QA fails with "candidate moved during QA".

Nothing is committed before `RESULT: PASS` on this tree; a stop hook asking for a commit mid-build is answered with that rule, not with a commit.

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
   └─► Phase 1 (×14, parallel) ─► 01_reference-miner_{submodule}_portmap.md ×14
         ├─► [adoption] Phase 1b ─► 01b_capability-scout_backlog.md ─► STOP: Daniel picks <item>
         └─► Phase 2 agents ─► 02_strategy-architect_{slices|<item>}.md ◄─SendMessage─► 02_adversarial-risk-judge_{verdict|<item>_r<k>}.md
               └─► Phase 3 per slice or item ─► src/**, tests/**  or  skills/**, .claude/**, docs/**
                     ├─► 03_runtime-builder_{slice{N}|<item>}.md
                     └─► 03_boundary-qa_{slice{N}|<item>}.md ─► PASS ─► commit, PR, next pick
                           └─► Phase 4 ─► 04_boundary-qa_report.md
```

Scout reads all fourteen maps and the repo inventory, never the reference code. Judge reads only the design file + cited `references/` lines. Builder reads the design and its clean verdict. QA reads the design + builder report + the targeted files.

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
| `check` exits 3 on a QA PASS or a clean verdict | The verdict belongs to another tree; commit nothing, start nothing, and run QA or the judge on the tree as it stands |
| QA tool missing (pytest/ruff/black/mypy) | Report FAIL with the missing tool; tell Daniel to run `uv pip install -e .[dev]`; never mark PASS |
| `_workspace/` collision on new input | Move to `_workspace_{YYYYMMDD_HHMMSS}/`, never overwrite or delete |

## 테스트 시나리오

### 정상 흐름
1. Daniel: "build the master finhub runtime". No `_workspace/` → initial run.
2. Phase 1: fourteen Explore agents return; fourteen `01_*_portmap.md` files written.
3. Phase 2: named architect writes slices + Authority List; a fresh unnamed judge rejects 2 claims in round 1; `SendMessage` to the architect, it revises; a new judge's round 2 totals `REJECTED 0`; no teardown.
4. Phase 3: slice 1 build → QA PASS (`python -m master_finhub.cli "echo hi"` prints `hi`); slices 2 and 3 likewise.
5. Phase 4: `04_boundary-qa_report.md` lists 3 slices built, all four commands exit 0, gaps = slices 4–11 pending.

### 정상 흐름 (capability adoption)
1. Daniel: "improve finhub harness from the reference repos". `_workspace/` holds a runtime run → moved to `_workspace_{timestamp}/`; `00_input/request.md` gets `scope: both`.
2. Phase 1: fourteen maps; four reused (SHA and scope match), ten re-mined with prior maps passed.
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
