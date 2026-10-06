RESULT: PASS

Adoption C1 (design revision 4, judge r5 UPHELD 20 / REJECTED 0 / UNVERIFIED 0). No repo file was modified; scratch in `<scratchpad>/qa5/`. All `claude -p` runs used default permission mode (no bypassPermissions); only the P-2 present case used `--allowedTools mcp__fixture__echo`.

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| agent `## Required connectors` <-> orchestrator table (P-3) | `contact-finder.md`: `## Required connectors` / `crm` | `contact-lookup-orchestrator/SKILL.md:28` `\| contact-finder \| crm \|` | yes |
| design stop line <-> live output | `Missing connector {server} for agent {agent}. ... Nothing was started.` | control run 1 and 2 printed `Missing connector fixture for agent pinger. Attach or authorise it, then run again. Nothing was started.` | yes |
| present rule <-> live stream | deferred_from_start, agent_calls>=1, no stop line, `ping` | true / 1 / 0 / `ping` | yes |
| fixture item 4 <-> `orchestrator-template.md:52` | same text (only the table row differs) | diff showed only `{agent}`/`{server}` row | yes |
| E-claims <-> files | P-1 counts | see Gate | yes |

## Gate
| command | exit | output observed |
|---|---|---|
| control (unmutated fixture), absent case x2: `ENABLE_TOOL_SEARCH=true claude -p "run the fixture harness" --strict-mcp-config --mcp-config absent.json --output-format stream-json --verbose` | 0, 0 | run1 tools `Skill ToolSearch`, agent_calls=0, stop-line grep count 1; run2 tools `Skill ToolSearch`, agent_calls=0, stop-line count 1 |
| M1 pre-check: `grep -c '^ *- Claude Code:'` before / `sed -i '/^ *- Claude Code:/d'` / after / `diff -q` | 0 | before 1, after 0, `Files ctl/.../SKILL.md and m1/.../SKILL.md differ` (mutation applied) |
| M1 absent x2, same command | 0, 0 | run1: tools `Skill ToolSearch`, agent_calls=0, stop-line count 0 ("I haven't run the `pinger` agent..."); run2: same, count 0. KILLED 2/2 |
| M1c pre-check: `grep -c 'Connector preflight'` before / delete item 4 (python slice from `4. Connector preflight` to `### Step 2`) / after / `diff -q` | 0 | before 1, after 0, files differ (mutation applied) |
| M1c absent x2 | 0, 0 | run1: tools `Skill Agent ToolSearch ToolSearch ToolSearch`, agent_calls=1, stop-line 0; run2: same tools, agent_calls=1, stop-line 0. KILLED 2/2 |
| mutant M2 (live): fixture `begins with \`mcp__{server}__\`` -> `contains {server}`; `lookalike.json` (server `fixture2`) | 0 | first attempt used a wrong sed pattern and was a no-op (diff -q silent), run voided. Redo: pattern count before 1, after 0, `diff -q` differs; tools `Skill Agent ToolSearch`, stop 0, agent spawned. KILLED |
| control for M2: unmutated fixture + `lookalike.json` | 0 | tools `Skill`, agent_calls=0, `Missing connector fixture for agent pinger. ... Nothing was started.` (exact-prefix rule holds, A5) |
| mutant M3 (tar copy `M3/`): chat/Cowork sentences -> `stop.` ; `grep -c 'Do not stop without asking' orchestrator-template.md` | 0 | 1 -> 0. KILLED |
| mutant M4 (tar copy `M4/`): remove last E5 sentence in Template C; `grep -c 'Then run the connector preflight from Template A Step 0, item 4'` | 0 | 2 -> 1. KILLED |
| mutant M5 (tar copy `M5/`): `: > src/master_finhub/factory/__init__.py`; `test ! -e src/master_finhub/factory` | 1 | test fails ("E8 test ! -e FAILS"). KILLED |
| mutant M6 (tar copy `M6/`): drop attribution suffix from E4; `grep -c 'agent_definitions.py:956 (MIT)' orchestrator-template.md` | 0 | 1 -> 0. KILLED |
| P-2 present: `ENABLE_TOOL_SEARCH=true claude -p "run the fixture harness" --strict-mcp-config --mcp-config present.json --output-format stream-json --verbose --allowedTools mcp__fixture__echo` ; `bash a9_verdict.sh present.jsonl` | 0 / 0 | `deferred_from_start=true agent_calls=1 missing_lines=0 fixture_was_deferred=1` / `A9 PASS`; tool order `Skill Agent ToolSearch mcp__fixture__echo`; tool_result text `ping` (count 1); result: "...the reply was `ping`." |
| P-1 E1 `grep -c '^- Connectors: an agent that cannot do its job' SKILL.md` | 0 | 1 |
| P-1 E2 `grep -c '^- \*\*Connector preflight\*\*' SKILL.md` | 0 | 1 |
| P-1 E3 `grep -c 'has a row in the orchestrator.s connector preflight table' SKILL.md` | 0 | 1 |
| P-1 attribution `grep -c '...agent_definitions.py:956 (MIT)' SKILL.md orchestrator-template.md` | 0 | `SKILL.md:1`, `orchestrator-template.md:1` |
| P-1 E4 `grep -c '^4. Connector preflight'` / order | 0 | 1; line of `3. If you run fresh` 51 < item 4 52 < `### Step 1: Fix the task list` 63 |
| P-1 E4 chat / skipped / health / stop line | 0 | 1 / 1 / 1 / 1 |
| P-1 E5 | 0 | 2 |
| P-1 E6 `grep -c '^| 7 | Connector preflight |' surfaces.md` | 0 | 1 |
| P-1 E7 `grep -c '^| P7 |' docs/surface-verification.md` | 0 | 2 |
| P-1 E8 `test ! -e src/master_finhub/factory`; `grep -rn 'master_finhub.factory\|master_finhub/factory' src tests scripts pyproject.toml README.md` | 0 | `gone`; no output |
| P-1 E9 `grep -c 'factory/. package' README.md` | 1 (count 0) | 0 |
| P-1 SKILL size `wc -l < SKILL.md` | 0 | 197 |
| 8-word-run script vs `references/openharness/.../agent_definitions.py` | 0 | SKILL.md 0, orchestrator-template.md 0, surfaces.md 0, surface-verification.md 0 |
| Hangul: `LC_ALL=C.UTF-8 grep -cP '[\x{AC00}-\x{D7A3}]'` on the five files; `grep -rnP '\p{Hangul}' skills/` | rc 1 each | all counts 0; skills/ rc=1 (none) |
| `bash scripts/package-plugin.sh` | 0 | `dist/finhub-harness-skill.zip 81759 bytes`, `dist/finhub-harness-evolve-skill.zip 3516 bytes` |
| `bash scripts/check-harness-refs.sh` | 0 | 40 PASS, 0 FAIL |
| `.venv/bin/python -m pytest -q` | 0 | `891 passed, 10 skipped in 82.73s` |
| `ruff check src tests` | 0 | `All checks passed!` |
| `black --check src tests` | 0 | `63 files would be left unchanged.` |
| `mypy --strict src` | 0 | `Success: no issues found in 37 source files` |
| `git diff --stat -- tests/` and `--cached` | 0 | empty |
| `git status --short` | 0 | M README.md, docs/surface-verification.md, skills/finhub-harness/SKILL.md, references/orchestrator-template.md, references/surfaces.md; D (staged) four `src/master_finhub/factory/*.py`. Nothing else (packager output under `dist/` is not listed) |
| P-3 re-confirm on `p3_out`: `grep -c '^## Required connectors' .claude/agents/*.md`; `grep -rn 'contact-finder.*crm'`; `grep -rn 'Connector preflight'`; `grep -rc 'Missing connector'` | 0 | `contact-finder.md:1` with next line `crm`; `SKILL.md:28 \| contact-finder \| crm \|`; `SKILL.md:24 4. Connector preflight.`; Missing connector count 1 |
| compliance sweep: touched files contain no client data/secrets | n/a | fixture uses only `fixture`/`pinger`/`crm` placeholders; `tests/` diff empty; 8-word and Hangul clean |

Mutation score: M1, M1c, M2, M3, M4, M5, M6 all killed; 0 survived. Adversarial probes: lookalike server `fixture2` (control stops, M2 spawns), M1 and M1c live in default mode, two-run repeats.

## Defects
None blocking.
1. observation: M1's kill depends on the model's wording (it stops via the first line of item 4 and the table, but prints a free-form refusal instead of the exact stop line). Killed 2/2 as the design's r4 simulation stated; run-to-run variance is possible with a live model.
2. observation: my first M2 sed was a no-op (pattern had `{server}`, not `fixture`); caught by `diff -q` silence and a count of 0, run voided and redone. The design's M2 text says `begins with \`mcp__{server}__\`` and it should be applied to that literal.
3. observation: carried over, `orchestrator-template.md:52` "skip if the table says none" is handled by the model (earlier run); not re-run now. `README.md:45` ("five agents") is out of scope.

## Not run
- Test-plan cases 4 (none row) and 5 (two rows, one present) were not re-run this round; they passed in the prior report (files unchanged since).
- P7 manual chat/Cowork probe stays empty by design (not a PASS condition).
