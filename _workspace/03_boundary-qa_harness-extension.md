RESULT: PASS

# Boundary QA — harness extension, round 5 (D12 re-verification)

Scope: D12 fix, new scripts/check-harness-refs.sh, standing gates, regression of earlier fixes. No repo file edited; mutation copies lived only in the scratchpad and were deleted (`ls` -> No such file or directory). `git status --short` = 16 lines (13 M + 3 untracked: capability-scout.md, capability-triage/, scripts/check-harness-refs.sh; the 16th is the new script).

## 1. D12 end to end
| statement | file:line | text observed |
|---|---|---|
| verdict header field | .claude/skills/adversarial-audit/references/verdict-schema.md:13 | `- Extra round authorised by Daniel: 2026-10-01 (only on round 4 and later; copied from the launch prompt, omitted otherwise)` |
| round wording | verdict-schema.md:3 | `The round field reads round k/3, or round 4 (authorised) and later when the launch prompt records Daniel's authorisation.` |
| audit skill step 6 | .claude/skills/adversarial-audit/SKILL.md:21 | `max 3 rounds unless the launch prompt records Daniel's authorisation for an extra round (copy it into the verdict header as Extra round authorised by Daniel: <date>). After round 3 with rejections and no such line, stop and hand to the orchestrator for escalation` |
| judge Core Role 4 | .claude/agents/adversarial-risk-judge.md:14 | `max 3 unless the launch prompt records Daniel's authorisation for an extra round; copy it into the verdict header, then escalate` |
| judge after-round-3 rule | adversarial-risk-judge.md:39 | `After round 3 with REJECTED > 0 and no authorisation line in the launch prompt: stop the loop ... escalate to Daniel` |
| orchestrator Phase 2 step 3 | .claude/skills/master-finhub-orchestrator/SKILL.md:103 | `Max 3 rounds; if round 3 still has REJECTED > 0, stop and escalate to Daniel ... Daniel may authorise further rounds one at a time; put Extra round authorised by Daniel: <date> in that round's launch prompt so the judge copies it into the verdict header.` |

Agreement: all four say the cap is 3 by default, an extra round exists only when the launch prompt carries Daniel's authorisation, the judge copies it into the header, and no line means stop and escalate. Orchestrator error-handling table line 185 (`still disagree after 3 rounds -> escalate to Daniel`) and strategy-architect.md:41 (`max 3 rounds`) state the default cap and the escalation, which the authorised-round clause extends only with Daniel's explicit say-so (consistent with CLAUDE.md:27 precedent). No contradiction. D12 FIXED.
Observation O7 (not counted): judge.md uses the word "authorisation" but not the literal `Extra round authorised by Daniel` string; the literal is in the schema, SKILL.md and orchestrator, which the judge reads, so the header text is still reproducible.

## 2. scripts/check-harness-refs.sh
| command | exit | output observed |
|---|---|---|
| `bash scripts/check-harness-refs.sh \| grep -c FAIL` | 0 (count) | `0`; script exit `rc=0`, 40 PASS lines |
| read for checks that cannot fail | - | each `chk` runs a real grep/test; weak ones: `Deferred pick rule` (bare word `Deferred` in orchestrator), `judge agent authorisation` (bare word). Both do fail when the word is removed (M2 below). Model check allows an absent `model:` line, only capability-scout has one (see M6) |
| mutants on a scratchpad tar copy (top-level references/, .git, .venv, dist excluded) | | |
| mutant: M1 verdict-schema literal -> `Extra round OK` | 0 | `FAIL authorisation line` CAUGHT |
| mutant: M1b same change in orchestrator | 0 | `FAIL authorisation line` CAUGHT |
| mutant: M2 judge `authorisation` -> `auth` | 0 | `FAIL judge agent authorisation` CAUGHT |
| mutant: M3 boundary-qa `Not for` -> `Never for` | 0 | `FAIL Not-for clause boundary-qa` CAUGHT |
| mutant: M4 runtime-builder `name: x` | 0 | `FAIL frontmatter runtime-builder` CAUGHT |
| mutant: M5 Hangul in runtime-builder description | 0 | `FAIL no Hangul in agents+triage` CAUGHT |
| mutant: M6 runtime-builder `model: haiku` | 0 | no FAIL: equivalent, runtime-builder has no `model:` line (the check only validates a line that exists); same mutation on capability-scout `model: haiku` -> `FAIL frontmatter capability-scout` CAUGHT |
| mutant: M7 triage `## Deferred` -> `## Zed` | 0 | `FAIL Deferred section` CAUGHT |
| mutant: M8 orchestrator `openharness` -> `oh` | 0 | `FAIL miner openharness in orchestrator` CAUGHT |
| mutant: M9 audit SKILL `_r<k>` -> `_rk` | 0 | `FAIL verdict path _r<k>` CAUGHT |
| mutant: M10 CLAUDE.md `six-agent` -> `five-agent` | 0 | `FAIL CLAUDE.md says six-agent` CAUGHT |
| mutant: M11 boundary-qa `name: boundary-q` | 0 | `FAIL frontmatter boundary-qa` CAUGHT |
| mutant: M12 boundary-qa.md removed | 0 | `FAIL agent file boundary-qa` + `FAIL six agent files` CAUGHT |
| mutant: M13 package-plugin.sh replaced by `exit 1` | 0 | `FAIL packager exit 0` CAUGHT |
| restore + rerun on the copy | 0 | no FAIL, `rc=0` |
| cleanup | 0 | qa5, qa6 deleted; repo tree untouched |
(First attempt excluded every `references` dir, which stripped .claude/**/references and produced spurious FAILs; discarded and redone with `--exclude=./references`.)

## 3. Standing gates
| command | exit | output observed |
|---|---|---|
| `bash scripts/package-plugin.sh` | 0 | `dist/finhub-harness.plugin 93356 bytes`, `finhub-harness-skill.zip 80651`, `finhub-harness-evolve-skill.zip 3516` |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' .claude/agents .claude/skills/capability-triage \| wc -l` | 0 | `0`; separate `grep -rqP` rc=1 (no match, not rc=2) |
| `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' skills/ \| wc -l` | 0 | `0` |
| `.venv/bin/python -m pytest -q` | 0 | `891 passed, 10 skipped in 83.49s (0:01:23)` |
| `.venv/bin/ruff check src tests` | 0 | `All checks passed!` |
| `.venv/bin/black --check src tests` | 0 | `67 files would be left unchanged.` |
| `.venv/bin/mypy --strict src` | 0 | `Success: no issues found in 41 source files` |

## 4. Regression of D1-D11
The previous report was overwritten earlier in the loop and only D10-D12 are written down in it; D1-D9 text is not recoverable. I re-checked what is identifiable plus every structural family the script and earlier rounds covered.
| check | command | observed |
|---|---|---|
| D10 Deferred promotion in orchestrator | `grep -c "promote \`Cn\` into a full Backlog row" orchestrator SKILL.md` | `1` |
| D11 Deferred in scout and triage layouts | `grep -c "## Deferred"` scout / triage | `2` / `2` |
| frontmatter delimiters on all 12 agent/skill files | loop `grep -c '^---$' >= 2` | `fm-ok`, no BAD |
| no v1 team tools in .claude | `grep -rnE 'TeamCreate\|TeamDelete\|team_name\|CLAUDE_CODE_EXPERIMENTAL' .claude CLAUDE.md \| wc -l` | `1` (CLAUDE.md history row only, same as prior rounds) |
| `.claude/commands` absent | `ls .claude/commands` | `No such file or directory` (good) |
| SKILL.md length | `wc -l .claude/skills/*/SKILL.md` | max 214 |
| stale counts | `grep -rnE '\bfive-agent\|x6\|×6' .claude CLAUDE.md \| wc -l` | `0` |
| agents/miners/verdict paths/six files/CLAUDE six-agent | `check-harness-refs.sh` | 40 PASS, 0 FAIL |

## Probe (adversarial)
probe: mutate the authorisation literal in either file the judge reads (M1, M1b) and drop the judge's wording (M2): each is caught by a distinct FAIL line, so D12 cannot silently regress. probe: round-4 wording `round 4 (authorised)` present together with the `k/3` default, so a fresh judge launched for round 4 has a defined header (the P3 case from the prior round).

## Defects
None counted. Observations: O7 (judge.md lacks the literal string); script weak spot, `model:` check is vacuous for agents with no model line (only capability-scout has one); D1-D9 individual wording unavailable, covered by script and gates above.
