RESULT: FAIL

Read-only QA, round 2, 2026-10-02. Both round-1 blockers fixed in substance. One small residual under the strict "every chat/Cowork claim carries unverified" rule (R1), plus 2 non-blocking leftovers (R2, R3). Everything else passes.

## Round 1 history
Round 1 (FAIL): D1 surfaces.md asserted unverified chat/Cowork facts; D2 Phase 2 custom types inconsistent; D3 licence rows not verbatim; D4 judge/architect "team" wording; D5 stale "team" wording; D6 no LICENSE/NOTICE.

## Round-1 items re-verified
- D1 (surfaces.md): line 63 now "believed unavailable — unverified — confirm in that surface"; lines 65, 87, 89, 93 carry "unverified"; table lines 134-140 read "unverified (believed ✗)" / "unverified". Mostly FIXED; residual R1 below.
- D2 (custom types): SKILL.md:27-28 table = `strategy-architect (opus)` / `adversarial-risk-judge (opus)`; SKILL.md:71-72 `subagent_type: "strategy-architect"` / `"adversarial-risk-judge"`; phase-table.md:9-10 `opus / strategy-architect`, `opus / adversarial-risk-judge`; both agent files line 15 "Invoked as the custom type of the same name". All five agree. FIXED.
- D3 (licence rows): `diff` of the six rows (autogpt, openhands, dify, crewai, deepseek_harness, revfactory_harness) between source-enrichment.md and licence-rules.md -> IDENTICAL. FIXED.
- D4 (judge/architect wording): judge line 14 now "Write the verdict; the orchestrator relaunches you fresh each round (max 3, then escalate)"; "Peer: strategy-architect (named agent)". Mostly FIXED; leftovers R2.
- D5 (stale "team"): phase-table.md now "named agent" / "fresh agent per round"; SKILL.md:125 "Phase 2 agents", :141 "Named agent stops mid-task". FIXED except R2.
- D6 (LICENSE/NOTICE): LICENSE (169 non-empty lines, Apache 2.0) and NOTICE (credits revfactory/harness v2.1.0, line 4) exist; `unzip -l dist/finhub-harness.plugin` lists LICENSE (11358 B) and NOTICE (353 B). FIXED.

## Original checklist
| Check | Result |
|---|---|
| `claude plugin validate .claude-plugin/plugin.json` | exit 0, passed (1 harmless warning: root CLAUDE.md not loaded as context) |
| `bash scripts/package-plugin.sh` | exit 0; dist/finhub-harness.plugin 87330, finhub-harness-skill.zip 76132, finhub-harness-evolve-skill.zip 3516 |
| skills/*/SKILL.md name+description | both OK (2 lines each) |
| Hangul in skills/ | 0 |
| `TeamCreate(` / `TeamDelete(` in orchestrator | 0 |
| Phase 2 / table / phase-table / agent files agree | yes (custom types) |
| licence rows byte-identical | yes |
| `.venv/bin/python -m pytest -q` | 677 passed, 9 skipped |
| `git status --short src tests` | empty |
| `dist` ignored | `git check-ignore dist` -> dist |

git diff --stat (tracked, 7 files, +70/-25): .claude/agents/adversarial-risk-judge.md, .claude/agents/strategy-architect.md, orchestrator SKILL.md, phase-table.md, .gitignore, CLAUDE.md, README.md.
Untracked: .claude-plugin/, LICENSE, NOTICE, scripts/, skills/. dist/ ignored. Matches expectation.

## Defects (remaining)
- R1 (strict-rule, small) skills/finhub-harness/references/surfaces.md:72-73 assert chat limits as fact: "No real messaging." / "No isolation." (status "Degraded" at 71-73 likewise). Also :124-126 chat column "not applicable" / "inline blocks instead" / "not available; keep it in the skill..." carry no "unverified" (Cowork column does). Fix: append "(unverified)" to those chat cells/sentences, or rephrase as "assumed, unverified".
- R2 (non-blocking) Leftover v1 team wording: .claude/agents/strategy-architect.md:3 and adversarial-risk-judge.md:3 "Phase 2 team member"; both files :30 heading "Team Communication Protocol" and body (shared task list, judge "Sends: to strategy-architect") still describes SendMessage/task-list dialogue, whereas orchestrator has the judge fresh and unnamed, with the orchestrator relaying via SendMessage to the architect. Orchestrator SKILL.md:8 "(a team with SendMessage)". Fix: "Phase 2 agent"; heading "Communication"; judge "Sends" -> writes the verdict file, orchestrator relays.
- R3 (note) SKILL.md:16 Korean marker "에이전트 팀" intentionally kept per CLAUDE.md change history.
