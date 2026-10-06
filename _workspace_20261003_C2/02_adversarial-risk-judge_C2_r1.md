TOTALS: UPHELD 17 / REJECTED 3 / UNVERIFIED 0 — round 1/3

# Adversarial verdict: C2 lint script (revision 0)

- Audited file: _workspace/02_strategy-architect_C2.md (revision 0), `## Authority List` A1-A19, plus substance checks the launch prompt asked for
- Audited: 2026-10-03
- Pinned submodules opened: crewai fbcf2de, deepseek_harness b274e89, autogpt d58d41b (classic/ only), openharness 9b2efd7, revfactory_harness cceac68
- Simulation: scratch copy at /tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c2/repo. F1, F2 and the fixtures were extracted verbatim from the design, and E1, E2 and E3 were applied there. Nothing was written into the repo.
- Totals: 19 Authority List rows plus 1 substance row (S1), which counts toward REJECTED.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | crewai .../skills/validation.py:54 | `if dir_name != skill_name:` raises ValueError (:53-56) | — |
| A2 | UPHELD | deepseek .../skill/src/index.ts:20; crewai validation.py:15 | `const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/`; `SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` | Citation is correct, but no fixture seeds a grammar violation. See S1 |
| A3 | UPHELD | crewai validation.py:13; autogpt classic/.../skill_model.py:27 | `MAX_SKILL_NAME_LENGTH: Final[int] = 64`; `max_length=64` | classic/ path, not autogpt_platform/ |
| A4 | UPHELD | crewai .../skills/models.py:63 | `description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LENGTH)` | — |
| A5 | UPHELD | crewai models.py:21; autogpt skill_model.py:32 | `MAX_DESCRIPTION_LENGTH: Final[int] = 1024`; `max_length=1024` | — |
| A6 | UPHELD | deepseek .../skill-filesystem/src/index.ts:913; openharness _frontmatter.py:53 | `if (firstLine !== '---') return undefined` (closing check at :915-916); `if content.startswith("---\n"):` (closing `\n---\n` at :54) | The closing-`---` half has no seeded defect. See S1 |
| A7 | UPHELD | deepseek skill-filesystem index.ts:812, :984 | `if (name === undefined \|\| description === undefined)` → ignored; `stringField` returns undefined when `value.length > 0` fails | — |
| A8 | UPHELD | NET-NEW; backlog :92 | backlog :92 reads "Over-strict rules could block a valid harness, so unknown keys are warnings" | The verification can fail: P1 `owner` is a WARN, and M11 was killed in my run |
| A9 | UPHELD | autogpt skill_model.py:43; deepseek skill-filesystem index.ts:993 | `author` :43, `allowed-tools` alias :40, `version` :47 (all within ±5); `rejectLegacyInvocationKey(..., 'disable-model-invocation')`, `'user-invocable'` :993-995 | The NET-NEW extension keys only warn, so no harm |
| A10 | UPHELD | NET-NEW; crewai crew.py:725 | :725 is `def check_manager_llm`, which validates manager composition, not name resolution | The verification can fail: `ghost` gives an ERROR, and M4/M12 were killed. **Correct a count:** `.claude/` has **13** quoted `subagent_type`/`agentType` references, not 14 (6 in agents, 7 in the orchestrator SKILL). Fix the numbers in A10 and Test plan item 3 |
| A11 | UPHELD | revfactory .../references/team-examples.md:39 | `- TeamCreate(team_name: "research-team", members: [` | Pattern only. Only the `TeamCreate(` form is seeded. See S1 |
| A12 | UPHELD | NET-NEW; repo skills/finhub-harness/SKILL.md:92 | :92 reads "one server per line, written as the segment between `mcp__` and the next `__`" | The verification can fail: `mcp__erp__search` gives an ERROR, and M7 was killed |
| A13 | **REJECTED** | NET-NEW; repo SKILL.md:180 | :180 is the both-ways checklist line (supports the intent) | **Substance: the rule as designed false-fails a harness built verbatim from the plugin's own template.** `skills/finhub-harness/references/orchestrator-template.md:54-56` puts the preflight table **indented 3 spaces** inside list item `4.`. F1's `TABLE_RE = r"^\|\s*Agent..."` and its row capture `(?:\|.*\n?)*` anchor `\|` at column 0, so the table is never found. Simulated: agent `researcher` with `- crm`, and an orchestrator holding the template's indented table with row `researcher \| crm`, gave `ERROR ...: preflight agent 'researcher' needs 'crm': no preflight row` with exit 1. A second false positive: the same template line :52 says "Skip this item if the table says "none"", and a table row `\| none \| none \|` gives `ERROR preflight row none \| none has no agent connector line`. Fix: allow leading whitespace (`^[ \t]*\|`) in TABLE_RE and in the row capture, treat a `none` row as empty, and make the F4 good orchestrator use the template's indented table, so test 2 guards both cases |
| A14 | UPHELD | NET-NEW | — | The verification can fail: test 4 gives exit 1 for an empty dir and exit 2 for a missing one, and M10 was killed |
| A15 | UPHELD | NET-NEW | — | P3 reproduced exactly: `.claude` gives `0 error(s), 6 warning(s)`, exit 0, and the 1259-char orchestrator description is one of the six. F2 does not assert this WARN. See S1 |
| A16 | UPHELD | NET-NEW; openharness _frontmatter.py:57 | `metadata = yaml.safe_load(content[4:end_index])` | "14 real files" is 12 in `.claude` plus 2 in `skills/`, which is correct. The unparseable-line branch is unseeded. See S1 |
| A17 | UPHELD | NET-NEW; repo SKILL.md:90 | :90 names `name`, `description`, `tools`, `model` | P2 and P3 show no agent `unknown-key` warning; `color` only matters as a warning |
| A18 | UPHELD | NET-NEW; repo SKILL.md:90 | :90 reads "`model` with the reason as a comment" | 5 of 6 agents lack `model:` (only capability-scout has it), as the design says. M14 and M15 were killed |
| A19 | **REJECTED** | NET-NEW; backlog :89 | :89 reads "`package-plugin.sh` calls the same script on this repo's `skills/` so there is one rule set" | **Substance: E3 loses a check that the old gate made.** The old v1 grep is `grep -rnE --include=SKILL.md ... skills/` and recurses to any depth. F1 reads only `skills/*/SKILL.md`. I seeded `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(a)`: the old packager exited **1**, the new one exited **0** and packaged it. The design's sentence "Everything the removed block checked is still checked by F1" is false; the next paragraph admits the gap but treats it as acceptable because "no nested skills today". That is no reason to drop a regression gate. Fix: F1 scans `skills/**/SKILL.md` (rglob) at least for `v1-artefact`, or E3 keeps the one-line grep. Then strike the "everything is still checked" sentence or make it true |

### Old vs new packager simulation (E3), the base for A19

Each defect was seeded into a fresh scratch copy, and both the old and the new `package-plugin.sh` were run on it.

| seeded defect | old exit | new exit | note |
|---|---|---|---|
| none (real repo) | 0 | 0 | the new one prints `lint_harness: 0 error(s), 0 warning(s)`, 3 dist files, and the skill zip contains lint_harness.py (count 1) |
| frontmatter removed | 1 | 1 | |
| `name:` line removed | 1 | 1 | |
| `name:` empty | 0 | 1 | the new one is stricter |
| `description:` empty | 1 | 1 | |
| `description` key renamed | 1 | 1 | |
| opening `---` removed | 1 | 1 | |
| closing `---` removed | 1 | 1 | |
| `TeamCreate(` / `TeamDelete(` / `team_name:` / `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=` | 1 | 1 | all four |
| third skill without frontmatter | 1 | 1 | |
| **nested `SKILL.md` with `TeamCreate(`** | **1** | **0** | **lost check (A19)** |
| CRLF line endings | 0 | 0 | |
| frontmatter-only file, closing `---` at EOF with no newline | 1 | 0 | an old false positive: deepseek `findClosingFrontmatter` (index.ts:923-934) accepts `---` at EOF. Not a loss |
| garbage top-level frontmatter line | 0 | 1 | the new one is stricter |

## Substance

| id | verdict | finding | evidence | fix |
|---|---|---|---|---|
| S1 | **REJECTED** | The backlog's proof bar (`01b_capability-scout_backlog.md:91`: "deleting any single rule lets its seeded defect through") is not met. Several rules in the Rules table have no seeded defect, so removing them is invisible to F2. The design's "15/15 killed" covers only the 15 mutants it chose | My extra mutants against F2 + fixtures. **Survived:** X1 drop the name grammar (`len(name) > 64 or not NAME_RE.match(name)` → `len(name) > 64`); X3 drop the `unparseable line` error; X4 drop the >1024 WARN; X5 raise the limit to 100000; X6 drop the closing-`---` check (`or "---" not in lines[1:]`); X8 drop `team_name:` from V1_RE; X9 drop `TeamDelete\(`; X10 drop the experimental flag. Killed: X7 (empty BUILTIN), X11 (bare `TeamCreate` matched) | Seed into `harness_bad`: a skill with `name: Bad_Name` (or `a--b`); a skill with no closing `---`; a skill with an unparseable top-level frontmatter line; one file each with `TeamDelete(`, `team_name:` and `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=` (or one file with all three on separate lines, asserting each `line N`); a skill with a 1025-char description, asserting the `description` WARN. Update the exact ERROR/WARN counts in test 1 and P1, and add X1-X10 to the mutation table |

## Re-run of the design's own proof (passes; not a finding)

- P1: 9 ERROR + 3 WARN exactly as listed, last line `lint_harness: 9 error(s), 3 warning(s)`, exit 1.
- P2: `0 error(s), 0 warning(s)`, exit 0.
- P3: `.claude` gives `0 error(s), 6 warning(s)` with exit 0; `.` gives `0 error(s), 0 warning(s)` with exit 0.
- P4: `wc -l` = 148. mypy `--strict` reports `Success: no issues found in 2 source files`. ruff reports `All checks passed!`. black leaves 28 files unchanged.
- P5: the full suite in the scratch copy gives **895 passed, 10 skipped**, and the new file gives 4 passed.
- P6/P7/P12: the packager exits 0 with zip count 1; check-harness-refs exits 0 (re-run with references/ linked); the counts are 1 / 0 / 1.
- P8-P11, P13: E1 and E2 anchors match the real file byte-for-byte (line 142 and line 169). After the edit, `wc -l` = 198, and the grep counts are 2 / 1 / 0 / 1 / 1.
- Mutants M1-M15: all 15 killed in my run. The ones I traced: M7 (connector `__`), M8 and M9 (preflight both directions), M10, M12, M13 (the placeholder row) and M15 (killed by test 1, and by test 3 through a KeyError crash).
- CI reach: `.github/workflows/ci.yml` runs `ruff check src tests`, `black --check src tests` and `mypy --strict src`, so `skills/` is not reached and F2 is covered by ruff/black only, as stated.
- 8-word verbatim: 8-grams of F1, F2, F3/F4, E1, E2 and E3 against validation.py, models.py, skill_model.py, both deepseek index.ts, _frontmatter.py, crew.py, agent_definitions.py and team-examples.md. Word tokens give 2 hits, both inside the adopted regex literal in F1 against validation.py:15 (attributed, MIT). Whitespace tokens give 0 hits. No prose overlap.
- Hangul gate: no output.

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C2 | N/A static lint of Markdown frontmatter; no pricing | N/A no positions | N/A no execution | N/A no time series | N/A no universe | N/A no model training or splits |
