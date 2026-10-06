# C2 adoption design: lint script for generated harnesses (revision 4)

## Changes in revision 4

Extra round authorised by Daniel: 2026-10-03.

Changed: A8 (count only), A20 (encoding test), S1 and S3, all marked `CHANGED r4`. All other Authority List rows are byte-identical to r3. I reproduced both fixes independently in my own scratchpad (`.../scratchpad/c2`); I did not copy the judge's `j4/fx2`.

- **S1, the nested read path.** Confirmed: no nested fixture held a bad byte, so a nested read that never reports, or that decodes strictly, passed all 4 tests.
  - Fix: `harness_bad/skills/bad-orchestrator/references/deep/more/SKILL.md` gains the line `Caf<0xE9> notes.`, a raw 0xE9 byte written with `write_bytes`.
  - Test 1 now expects `("references/deep/more/SKILL.md", "encoding not valid UTF-8")`.
  - The judge's F1 and F13 mutants are added as M40 (nested read decodes with replacement but never reports) and M41 (nested read is strict). Both are killed.
- **S3, a false error on a valid file.** Confirmed: the r3 `read()` reported any decoded U+FFFD. Run against the new good fixture, r3 gave `ERROR ... notes-style/SKILL.md: encoding not valid UTF-8` and exit 1.
  - Fix, with the same line count: `text = (raw := path.read_bytes()).decode("utf-8", errors="replace")`, then `if text.encode() != raw:`. Valid UTF-8 round-trips byte for byte, a BOM and CRLF included, so only undecodable bytes trigger the report.
  - The good `notes-style` gains the line `A lost character prints as �; flag it to the client.` (bytes `EF BF BD`).
  - The r3 test is mutant M42, killed by test 2. M36 is re-anchored to the new condition.
- **Totals.** Bad fixture **24 errors, 4 warnings**. Updated in the F3 row, P1, test 1, A8 and A20. Mutation simulation **42/42 killed**. The script stays at **150 lines**. The stale "146" in the F1 row and in P4 now read 150.
- **Does not cover** gains the judge's file-type limits: a directory, a dangling symlink, an unreadable file, a FIFO, and a UTF-8 BOM. No behaviour was added for them, because the script is at the line cap.

What I ran, all in the scratchpad:
- F1 on the bad fixture (`24/4`, exit 1), the good fixture (`0/0`, exit 0), `.claude` (`0/6`) and the repo root (`0/0`);
- the r3 script on the new good fixture (1 false `encoding` ERROR, confirming S3);
- `mutate.py`, all 42 mutants;
- `pytest` (4 passed), `mypy --strict`, `ruff` and `black` on F1 and F2;
- `package-plugin.sh` (exit 0) and `check-harness-refs.sh` (0 FAIL) on `pkg/`.

## Changes in revision 3

Extra round authorised by Daniel: 2026-10-03.

Changed claims: A8 (count only) and S1, marked `CHANGED r3`. Added: A20 (new id, appended). Rows A1-A7 and A9-A19 are byte-identical to r2.

- **S1, single-quoted refs.** Confirmed: both seeded broken references were double-quoted, so narrowing `REF_RE` to `"` passed every test.
  - Fix: `harness_bad/agents/typer.md` now reads `agentType: 'ghost-two'` (single-quoted). `caller.md` keeps the double-quoted `subagent_type: "ghost"`, so both quote styles are pinned.
  - The subagent-ref seeds stay at 2 errors, out of the 23 total below.
  - New mutant M35 (judge's N14: both quote classes narrowed to `"`) is killed.
- **Note (a), non-UTF-8 file.** Confirmed: `read_text` raised `UnicodeDecodeError`, which dropped every other finding.
  - New helper `read(path)` decodes with `errors="replace"`. When a replacement character appears, it reports `ERROR <file>: encoding not valid UTF-8 (undecodable bytes replaced)` and continues.
  - Both read sites use it: the top-level files and the nested `SKILL.md` scan.
  - New seed: `harness_bad/skills/bad-bytes/SKILL.md`, with byte 0xE9 in its body.
  - New rule row `encoding` and claim A20.
  - Mutants: M36 (report dropped) and M37 (strict decode: traceback) are both killed.
- **Note (b), dead assertion.** `lint()` now returns stdout + stderr, so `"Traceback" not in out` can fail. I showed it failing by running the revision-3 test 1 against the r1 script in the scratch repo: it stopped at `assert code == 1 and "Traceback" not in out` with `'Traceback' is contained here: Traceback (most recent call last):`. The first crash r1 reaches on this fixture is the `UnicodeDecodeError` from `bad-bytes`. M37 is killed by the same assertion.
- **Note (c), parser details.** Each is now pinned by a good-fixture case:
  - Trailing ` # comment` cut: good `notes-style` has `name: notes-style  # house style for client notes`. Without the cut, the name breaks the grammar and `dir-name`. Mutant M38 is killed.
  - Lone block marker: the good 64-char skill's 1024-char description is now a folded `description: >` block. Without the marker strip it measures 1026 chars and draws a WARN. Mutant M39 is killed.
- **New totals.** Bad fixture **23 errors, 4 warnings**, in test 1, P1 and A8. Mutation simulation **39/39 killed**. The script is **150 lines**, at the cap, after folding two lines in `check_meta` and `connectors` with no behaviour change.

What I ran, all in the scratchpad (`/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c2/`):
- F1 on the bad fixture (`23/4`, exit 1), the good fixture (`0/0`, exit 0), `.claude` (`0/6`) and the repo root (`0/0`);
- `mutate.py`, all 39 mutants;
- the r1-script run against the r3 test 1;
- `pytest` (4 passed), `mypy --strict`, `ruff` and `black` on F1 and F2;
- `package-plugin.sh` (exit 0) and `check-harness-refs.sh` (0 FAIL) on `pkg/`.

## Changes in revision 2

Changed claims: A8 (stale count only) and S1/S2, marked `CHANGED r2`. Rows A1-A7, A9-A19 are byte-identical to r1. I re-checked every rejection by simulation before accepting it, and all of them hold, so there is no dispute.

- **S2 (crash).** Confirmed: on a skill with a bare `name:`, the r1 script died with `IndexError: string index out of range` and printed no findings.
  - Cause: in `scalar`, `raw[:1] in "\"'"` is True for `raw == ""`, so `raw[0]` was evaluated on an empty string.
  - Fix: `raw[:1] in ('"', "'")`. The same probe now gives two clean `ERROR` lines (name, description) and exit 1.
  - Seeds: all three forms are seeded (`no-name`: key absent; `bare-name`: `name:` with no value; `no-desc`: description key absent). Test 1 asserts their `ERROR` lines and `"Traceback" not in out`.
  - Mutant M34 restores the old test, which crashes the run, and is killed.
- **S1 (unseeded rule conditions).** Each of the three rule conditions the judge named now has a seeded defect and a mutant:
  - `no-name`/`bare-name` for the empty-name branch (M29);
  - `heading-first`, whose line 1 is `# Title`, for the line-1 `---` check (M30);
  - agent `typer.md` with `agentType: "ghost-two"` for `agentType` resolution (M31).
- **S1, minor survivors.** The good `none-orchestrator` gains a `| NONE | none |` row (case-insensitive skip, M32). A deeper nested file `skills/bad-orchestrator/references/deep/more/SKILL.md` contains `TeamDelete(` (any-depth scan, M33).
- **New totals.** Bad fixture **22 errors, 4 warnings**, updated in test 1 and P1. Mutation simulation: **34/34 killed**. The script stays at 146 lines.
- **A8.** The stale "among the 9 errors" now reads 22.
- **P12.** The `# 4. package` → `# 3. package` renumber is now applied in the simulated `pkg/` copy. The three greps give **1 / 0 / 1**, the packager exits 0, and the skill zip contains the script once.

What I ran, all in the scratchpad (`/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c2/`):
- F1 on both fixtures, `.claude` and the repo root (`22/4` exit 1; `0/0` exit 0; `0/6` exit 0; `0/0` exit 0);
- the crash probe, against the r1 script (traceback) and against r2 (2 ERRORs);
- `mutate.py`, all 34 mutants;
- `pytest` (4 passed), `mypy --strict`, `ruff` and `black` on F1 and F2;
- `package-plugin.sh` (exit 0) and `check-harness-refs.sh` (0 FAIL) on `pkg/`.

## Changes in revision 1

Changed claims: A13, A19 and A10 (count only), rows marked `CHANGED r1`, plus S1 (fixtures, test counts, mutation table). All other claims are byte-identical to r0. Each rejection was re-checked by simulation in the scratchpad before I accepted it. All three hold, so there is no dispute.

- **A13.** Template A Step 0 item 4 (`orchestrator-template.md:54-56`) indents the table 3 spaces, and the r0 `TABLE_RE` only matched `|` in column 0. Simulated r0 result: a harness copying the template got a false `no preflight row` ERROR. Item 4 also says to skip when the table says "none", and r0 reported a `| none | none |` row as an orphan.
  - Fix: `TABLE_RE` allows leading spaces on the header and on each row. `preflight_rows` drops rows whose agent cell is `none` (any case), along with `{...}` placeholders and the separator row.
  - Fixture changes: the good fixture's `demo-orchestrator` now uses the template's indented item-4 table, with the template's own placeholder row. A new good skill `none-orchestrator` has a `| {agent} | {server} |` placeholder row and a `| none | none |` row.
  - New mutants: M26 (indent), M27 (none) and M13 (placeholder, re-anchored).
- **A19/E3.** The old packager grep searches `SKILL.md` at any depth. r0 read only `skills/*/SKILL.md`. Simulated r0: a nested `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(` passed.
  - Fix: F1 also reads every `skills/**/SKILL.md` below the first level and applies the line rules to it (`v1-artefact`, `subagent-ref`, preflight-table rows). Frontmatter rules are not applied to nested files, because nested `SKILL.md` files are not loaded as skills.
  - The false E3 sentence is corrected.
  - New seeded defect: `harness_bad/skills/bad-orchestrator/references/nested/SKILL.md`. New mutant: M28.
  - The intended behaviour change from the judge's note is recorded under E3.
- **S1.** Every rule now has a seeded defect that its removal lets through:
  - `Bad_Name` for the name grammar (M16);
  - `no-close` for the closing `---` (M17);
  - `bad-line` for the unparseable frontmatter line (M18);
  - `team_name:`, `TeamDelete(` and the experimental flag on their own lines (M19-M21);
  - `long-desc` at 1025 chars for the length WARN (M22, M23 loosened, M24 tightened), with a 1024-char good boundary;
  - a 64-char good name for the cap (M25).
  
  New totals: bad fixture **16 errors, 4 warnings**. Mutation simulation: **28/28 killed**.
- **A10 (non-blocking).** `.claude/` has **13** quoted references, not 14. Corrected in A10 and in Test plan item 3. "14 real files" in A16 is a different count (12 `.claude` files plus 2 plugin skills) and stays.

What I ran, all in the scratchpad (`/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c2/`):
- F1 on both fixtures, on `.claude` and on the repo root;
- the 28-mutant script (`mutate.py`);
- `pytest`, `mypy --strict`, `ruff` and `black` on F1 and F2, using the repo's `pyproject.toml`;
- `package-plugin.sh` and `check-harness-refs.sh` on the `pkg/` copy, clean and with the nested seeded `TeamCreate(` (which gave `Validation failed; nothing packaged.`).

Item: C2 from `_workspace/01b_capability-scout_backlog.md:49` (row) and `:76-93` (`### C2` detail). Scope: factory. Pick: `_workspace/00_input/request.md:18-21` ("Pick 2"). C1 is merged (PRs #16/#17, `_workspace_20261003_C1/`). This lint verifies C1's `## Required connectors` contract.

Everything below was simulated in the scratchpad only, with no edits to the repo. A scratch copy of `.claude/`, `skills/` and `scripts/` held the script, the fixtures, the test and both prose edits. Results (revision 4): the script is 150 lines. The new test file gives 4 passed. `mypy --strict`, `ruff check` and `black --check` pass on both new Python files (run with the repo's `pyproject.toml`). All 42 mutants M1-M42 were killed. Both `scripts/package-plugin.sh` and `scripts/check-harness-refs.sh` exit 0, and the skill zip contains the script. The baseline in the real repo before this change is `pytest -q` at **891 passed, 10 skipped**.

## Source

Backlog row C2 (score 0.90): a stdlib lint shipped in the plugin. It checks a generated harness's `.claude/agents/*.md`, `.claude/skills/*/SKILL.md` and its orchestrator. Shape: `skills/finhub-harness/scripts/lint_harness.py` (at most 150 lines); Step 6.1 becomes "run the lint; fix every error"; `package-plugin.sh` calls the same script so there is one rule set; bad and good fixtures go under `tests/fixtures/`. Risk named there: strict rules could reject valid files, so unknown keys are warnings.

I re-opened each port-map row at its pinned commit:

| row | port map | opened | what the line does | used? |
|---|---|---|---|---|
| C52 | `01_reference-miner_crewai_portmap.md:74` | `references/crewai/lib/crewai/src/crewai/skills/validation.py:43-56` (crewai fbcf2de) | `validate_directory_name`: `if dir_name != skill_name:` (`:54`) raises `ValueError` | yes: rule `dir-name` (A1) |
| (C52 file) | same file | `validation.py:13`, `:15` | `MAX_SKILL_NAME_LENGTH = 64`; `SKILL_NAME_PATTERN = ^[a-z0-9]+(?:-[a-z0-9]+)*$` | yes: rule `name` (A2, A3) |
| (C52 package) | same package | `references/crewai/lib/crewai/src/crewai/skills/models.py:21`, `:63` | `MAX_DESCRIPTION_LENGTH = 1024`; `description: str = Field(min_length=1, max_length=...)` | yes: rule `description` (A4, A5) |
| A32 | `01_reference-miner_autogpt_portmap.md:52` | `references/autogpt/classic/forge/forge/components/skills/skill_model.py:19-55` (classic/ only; nothing from `autogpt_platform/`) | `SkillMetadata`: name `max_length=64` (`:27`), description `max_length=1024` (`:32`); optional `license` `:34`, `allowed-tools` alias `:40`, `author` `:43`, `version` `:47`, `tags` `:51` | yes: limits (A3, A5) and the recognised skill keys (A9) |
| D50 | `01_reference-miner_deepseek_harness_portmap.md:96` | `references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:909-918` (b274e89) | `parseFrontmatter`: the first line must be `---` (`:913`) and a closing `---` must exist (`:916`), otherwise the result is `undefined` | yes: rule `frontmatter` (A6) |
| (D50) | same file | `:811-814`, `:982-984` | the skill is ignored when `name` or `description` is undefined; `stringField` treats `''` as undefined | yes: name and description required (A7) |
| (D50) | same file | `:993-995` | legacy camelCase keys rejected; canonical `disable-model-invocation`, `user-invocable` | partly: the canonical keys are recognised (A9). The legacy spellings are **not** rejected; they fall under the unknown-key warning (A8) |
| (D50 name) | `skill/skill/src/index.ts:20` | `references/deepseek_harness/packages/skill/skill/src/index.ts:20` | `const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/` | yes: rule `name` (A2) |
| OH14 | `01_reference-miner_openharness_portmap.md:44` | `references/openharness/src/openharness/skills/_frontmatter.py:34-82` (9b2efd7) | `parse_skill_metadata`: frontmatter only when content starts with `---\n` (`:53`); `yaml.safe_load` (`:57`); falls back to `# heading` + first paragraph, then to `"Skill: {name}"` | partly: the `---` start rule (A6, second line). **Fallback chain not adopted**: a loader may guess a description, but a linter that guesses would hide the very defect it exists to report. `yaml.safe_load` not adopted: PyYAML is not stdlib (A16) |
| C35 | `01_reference-miner_crewai_portmap.md:57` | `references/crewai/lib/crewai/src/crewai/crew.py:724-745` | `check_manager_llm`: hierarchical process requires a manager; the manager must not also be in `agents` | **not adopted.** It checks team composition when the config loads. The closest analogue here is the dangling-reference rule (A10), which is NET-NEW because no reference resolves Claude Code agent types |
| C34 | `01_reference-miner_crewai_portmap.md:56` | `crew.py:1531-1542` | a custom manager with tools logs a warning, clears the tools and raises | **not adopted.** In this plugin the coordinator is the main session running the orchestrator *skill*. Skills have no `tools:` frontmatter to lint, so the rule has no target. Listed under Does not cover |
| (v1 syntax) | `01_reference-miner_revfactory_harness_portmap.md:43` | `references/revfactory_harness/skills/harness/references/team-examples.md:39` (Apache-2.0, pattern only) | v1 prose calls `TeamCreate(team_name: "research-team", ...)` | yes: rule `v1-artefact` matches that call syntax (A11) |

Port-map rows OH17 and OH47 (plugin manifest) are out of scope. `package-plugin.sh:11-22` already checks the manifest, and that block is untouched.

## Target

Plugin skill `finhub-harness` (primary capability) and its packaging gate. Exact files:

| # | file | change |
|---|---|---|
| F1 | `skills/finhub-harness/scripts/lint_harness.py` | **new**, 150 lines (CHANGED r4: was a stale 146), stdlib only, Python ≥3.11 (uses `:=` and `X \| None`). Ships inside both the `.plugin` and the skill zip, because `package-plugin.sh` zips `skills/finhub-harness` |
| F2 | `tests/test_lint_harness.py` | **new**, 4 tests, runs the script as a subprocess (no import, so `mypy --strict src` stays untouched) |
| F3 | `tests/fixtures/harness_bad/` | **new**, 22 files (6 agents, 14 skills, 2 nested `SKILL.md`; one skill and one nested `SKILL.md` deliberately not valid UTF-8) with 24 seeded errors and 4 seeded warnings (CHANGED r4) |
| F4 | `tests/fixtures/harness_good/` | **new**, 6 Markdown files (2 agents, 4 skills): must give 0 errors and 0 warnings |
| E1 | `skills/finhub-harness/SKILL.md` | Step 6.1 line replaced in place (line 142) |
| E2 | `skills/finhub-harness/SKILL.md` | one checklist line inserted after line 169 |
| E3 | `scripts/package-plugin.sh` | lines 24-45 (frontmatter loop and v1 grep) replaced by one call to F1; `# 4. package` renumbered `# 3. package` |

Not touched: `src/`, the existing `tests/*.py`, `.claude/` (the lint *reads* it), `scripts/check-harness-refs.sh`, `skills/finhub-harness/references/`, and `CLAUDE.md`. As with C1, the orchestrator adds the change-history row at Phase 4.

Placement decisions:
- **Fixtures and the pytest file belong in this change.** The backlog's proof test *is* a fixture run, and CI (`.github/workflows/ci.yml`) already runs `pytest -q` and `ruff`/`black` over `tests`. That makes the proof a permanent regression gate at no new cost. The fixtures hold only `.md` files, so pytest collects nothing from them.
- **What runs on the script.** CI's `mypy --strict src` and `ruff check src tests` do not reach `skills/`. QA therefore runs `mypy --strict`, `ruff check` and `black --check` on F1 explicitly (see Proof P4). F2 is covered by CI's existing `ruff`/`black` over `tests`. No CI file changes.

## Design

### Interface (F1)

```
python3 lint_harness.py DIR
```

- `DIR` holds `agents/*.md` and/or `skills/*/SKILL.md`. For a generated harness it is `project/.claude`. For this plugin it is the repo root, which has `skills/` and no `agents/`.
- Output: one line per finding, `ERROR <path>: <rule> <message>` or `WARN <path>: <rule> <message>`. The last line is `lint_harness: <E> error(s), <W> warning(s)`.
- Exit 0 when E = 0 (warnings allowed); 1 when E ≥ 1; 2 on usage (wrong argument count, or DIR is not a directory).
- Functions (typed, all module-level): `report(level, path, rule, msg) -> None`, `frontmatter(path, text) -> dict[str, str] | None`, `scalar(raw) -> str`, `check_meta(path, data, known, expect) -> str`, `connectors(path, body) -> set[str]`, `preflight_rows(body) -> set[tuple[str, str]]`, `main(argv) -> int`.

### Rules

| rule id | level | applies to | fires when | evidence |
|---|---|---|---|---|
| `empty` | ERROR | DIR | no `agents/*.md` and no `skills/*/SKILL.md` under DIR. This stops a silent pass when the user gives the project root instead of `.claude` | A14 |
| `frontmatter` | ERROR | all files | line 1 is not `---`, or there is no closing `---` line, or a top-level frontmatter line is neither `key: value`, an indented or `- ` continuation, blank, nor a `#` comment | A6, A16 |
| `name` | ERROR | all files | `name` is missing or empty; or it does not match `^[a-z0-9]+(?:-[a-z0-9]+)*$`; or it is longer than 64 chars | A2, A3, A7 |
| `dir-name` | ERROR | skills | the skill directory name differs from `name` | A1 |
| `description` | ERROR | all files | `description` is missing or empty | A4, A7 |
| `description` | WARN | all files | `description` is longer than 1024 chars | A5, A15 |
| `unknown-key` | WARN | all files | a frontmatter key is outside the recognised set: skills {name, description, license, allowed-tools, metadata, version, author, tags, disable-model-invocation, user-invocable, argument-hint}; agents {name, description, tools, model, color} | A8, A9, A17 |
| `model` | WARN | agents | there is no `model:` key, or `model:` has no `# reason` comment | A18 |
| `subagent-ref` | ERROR | all files plus nested `skills/**/SKILL.md`, every line | a quoted `subagent_type: "x"` / `agentType: 'x'` names neither an agent `name` under DIR nor a built-in (`general-purpose`, `Explore`, `Plan`, `statusline-setup`, `claude-code-guide`). Placeholders such as `"{name}"` and namespaced `"plugin:agent"` do not match the token grammar and are skipped | A10 |
| `v1-artefact` | ERROR | all files plus nested `skills/**/SKILL.md` (any depth, as the old packager grep), every line | `TeamCreate(`, `TeamDelete(`, `team_name:` or `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=`. This is the same pattern as `package-plugin.sh:43`. Prose that only *names* the removed tools ("remove TeamCreate") passes | A11 |
| `encoding` | ERROR | all files read, nested `SKILL.md` included (CHANGED r4) | the file's bytes are not valid UTF-8, i.e. decoding with replacement does not round-trip to the same bytes. A valid file that merely contains U+FFFD passes. The scan continues, so no other finding is lost | A20 |
| `connector` | ERROR | agents | a non-blank line under `## Required connectors`, after stripping one `- `/`* ` bullet and backticks, is not a bare server token (`^[A-Za-z0-9][A-Za-z0-9_-]*$` with no `__`). Example: `mcp__erp__search` instead of `erp` | A12 |
| `preflight` | ERROR | DIR | an agent's declared (agent, server) pair has no row in any `\| Agent \| Required connector \|` table, **or** a table row has no matching agent line. The header and rows may be indented with spaces (Template A item 4 indents them 3 spaces). Skipped rows: rows containing `{` (template placeholders), rows whose agent cell is `none` (item 4's "skip if the table says none"), and the separator row | A13 |

Frontmatter values are read as written, with no YAML library. A quoted value is the text between the quotes. Otherwise a leading `>`/`|` block indicator is dropped, continuation lines are joined, and a trailing ` # comment` is cut. This is enough for `name`, `description` and `model`, which are the only values the rules read (A16).

### F1 source (the simulated version; the builder may restyle but must keep every rule, rule id, level and the exit codes)

```python
"""Lint a harness dir (agents/*.md, skills/*/SKILL.md). Exit 0 clean, 1 errors, 2 usage.
Adapted from references/crewai/lib/crewai/src/crewai/skills/validation.py:43 (MIT) and
references/deepseek_harness/packages/skill/skill/src/index.ts:20 (MIT)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^([A-Za-z][\w-]*):\s?(.*)$")
REF_RE = re.compile(r"""(?:subagent_type|agentType)["']?\s*:\s*["']([A-Za-z0-9_-]+)["']""")
V1_RE = re.compile(r"TeamCreate\(|TeamDelete\(|team_name:|CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=")
CONN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SECTION_RE = re.compile(r"^## Required connectors[ \t]*\n(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL)
TABLE_RE = re.compile(r"^ *\| *Agent *\| *Required connector *\| *\n((?: *\|.*\n?)*)", re.MULTILINE)
ROW_RE = re.compile(r"^\|\s*`?([^|`]+?)`?\s*\|\s*`?([^|`]+?)`?\s*\|\s*$")
BUILTIN = {"general-purpose", "Explore", "Plan", "statusline-setup", "claude-code-guide"}
SKILL_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "version"}
SKILL_KEYS |= {"author", "tags", "disable-model-invocation", "user-invocable", "argument-hint"}
AGENT_KEYS = {"name", "description", "tools", "model", "color"}

out: list[str] = []


def report(level: str, path: Path, rule: str, msg: str) -> None:
    out.append(f"{level} {path}: {rule} {msg}")


def read(path: Path) -> str:
    text = (raw := path.read_bytes()).decode("utf-8", errors="replace")
    if text.encode() != raw:
        report("ERROR", path, "encoding", "not valid UTF-8 (undecodable bytes replaced)")
    return text


def frontmatter(path: Path, text: str) -> dict[str, str] | None:
    """Parse the leading --- block into raw string values; None (and an error) if unusable."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        report("ERROR", path, "frontmatter", "missing --- delimited frontmatter")
        return None
    data: dict[str, str] = {}
    key = ""
    for line in lines[1 : lines.index("---", 1)]:
        m = KEY_RE.match(line)
        if m:
            key = m.group(1)
            data[key] = m.group(2).strip()
        elif key and (line.startswith((" ", "\t", "- ")) or not line.strip()):
            data[key] = (data[key] + " " + line.strip()).strip()
        elif not line.lstrip().startswith("#"):
            report("ERROR", path, "frontmatter", f"unparseable line: {line[:60]!r}")
            return None
    return data


def scalar(raw: str) -> str:
    """Value of a YAML scalar as written: quoted body, or unquoted text minus a # comment."""
    if raw[:1] in ('"', "'") and raw[1:].find(raw[0]) >= 0:
        return raw[1 : 1 + raw[1:].find(raw[0])]
    raw = re.sub(r"^[>|][-+]?\s*", "", raw)
    return raw.split(" #", 1)[0].strip()


def check_meta(path: Path, data: dict[str, str], known: set[str], expect: str | None) -> str:
    name, desc = scalar(data.get("name", "")), scalar(data.get("description", ""))
    if not name:
        report("ERROR", path, "name", "frontmatter name is missing or empty")
    elif len(name) > 64 or not NAME_RE.match(name):
        report("ERROR", path, "name", f"{name!r}: kebab-case, max 64 chars (got {len(name)})")
    if expect is not None and name and name != expect:
        report("ERROR", path, "dir-name", f"directory {expect!r} does not match name {name!r}")
    if not desc:
        report("ERROR", path, "description", "frontmatter description is missing or empty")
    elif len(desc) > 1024:
        report("WARN", path, "description", f"{len(desc)} chars; over the 1024-char skill limit")
    for k in sorted(set(data) - known):
        report("WARN", path, "unknown-key", f"frontmatter key {k!r} is not recognised")
    return name


def connectors(path: Path, body: str) -> set[str]:
    """Servers under '## Required connectors' (one per line, bullet and backticks optional)."""
    m = SECTION_RE.search(body)
    found: set[str] = set()
    for line in m.group(1).splitlines() if m else []:
        s = re.sub(r"^[-*]\s+", "", line.strip()).strip("`")
        if s and CONN_RE.match(s) and "__" not in s:
            found.add(s)
        elif s:
            report("ERROR", path, "connector", f"{s[:60]!r}: not a bare server name")
    return found


def preflight_rows(body: str) -> set[tuple[str, str]]:
    """(agent, server) rows of '| Agent | Required connector |' tables; skip {..}, none, separator."""
    lines = [ln.strip() for table in TABLE_RE.findall(body) for ln in table.splitlines()]
    found = [m.group(1, 2) for m in map(ROW_RE.match, lines) if m and "{" not in m.group(0)]
    return {(a.strip(), s.strip()) for a, s in found if a.strip("-: ").lower() not in ("", "none")}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not Path(argv[1]).is_dir():
        print("usage: lint_harness.py DIR  (DIR holds agents/ and/or skills/, e.g. .claude)")
        return 2
    root = Path(argv[1])
    agents = sorted(root.glob("agents/*.md"))
    skills = sorted(root.glob("skills/*/SKILL.md"))
    if not agents and not skills:
        report("ERROR", root, "empty", "no agents/*.md or skills/*/SKILL.md (pass the .claude dir)")
    names: set[str] = set()
    texts: dict[Path, str] = {}
    declared: set[tuple[str, str]] = set()
    for path in agents + skills:
        texts[path] = text = read(path)
        if (data := frontmatter(path, text)) is None:
            continue
        is_agent = path in agents
        keys, expect = (AGENT_KEYS, None) if is_agent else (SKILL_KEYS, path.parent.name)
        name = check_meta(path, data, keys, expect)
        if is_agent:
            names.add(name)
            if "model" not in data:
                report("WARN", path, "model", "no model: field (choose one per agent)")
            elif "#" not in data["model"]:
                report("WARN", path, "model", "model: has no '# reason' comment")
            declared |= {(name, s) for s in connectors(path, text)}
    for path in sorted(set(root.glob("skills/**/SKILL.md")) - set(skills)):  # nested: line rules
        texts[path] = read(path)
    table = {row for text in texts.values() for row in preflight_rows(text)}
    for path, text in texts.items():
        for n, line in enumerate(text.splitlines(), 1):
            for ref in REF_RE.findall(line):
                if ref not in names and ref not in BUILTIN:
                    report("ERROR", path, "subagent-ref", f"line {n}: no agent file for {ref!r}")
            if v1 := V1_RE.search(line):
                report("ERROR", path, "v1-artefact", f"line {n}: {v1.group(0)}")
    for agent, server in sorted(declared - table):
        report("ERROR", root, "preflight", f"agent {agent!r} needs {server!r}: no preflight row")
    for agent, server in sorted(table - declared):
        report("ERROR", root, "preflight", f"row {agent} | {server} has no agent connector line")
    errors = sum(line.startswith("ERROR") for line in out)
    print("\n".join(out + [f"lint_harness: {errors} error(s), {len(out) - errors} warning(s)"]))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

### F2 source (`tests/test_lint_harness.py`)

```python
"""Proof for skills/finhub-harness/scripts/lint_harness.py (C2)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
FIX = REPO / "tests/fixtures"
N65 = "-".join(["abcdefghij"] * 6)  # 65 chars


def lint(target: Path) -> tuple[int, str]:
    run = subprocess.run(
        [sys.executable, str(LINT), str(target)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run.returncode, run.stdout + run.stderr


def test_bad_fixture_names_every_seeded_defect() -> None:
    code, out = lint(FIX / "harness_bad")
    assert code == 1 and "Traceback" not in out
    expected = [
        ("skills/wrong-dir/SKILL.md", "dir-name"),
        (f"skills/{N65}/SKILL.md", "name"),
        ("skills/empty-desc/SKILL.md", "description"),
        ("agents/caller.md", "subagent-ref"),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact"),
        ("skills/no-frontmatter/SKILL.md", "frontmatter"),
        ("agents/badconn.md", "connector"),
        ("harness_bad", "preflight agent 'fetcher' needs 'crm'"),
        ("harness_bad", "preflight row fetcher-two | erp"),
        ("skills/Bad_Name/SKILL.md", "name 'Bad_Name'"),
        ("skills/no-close/SKILL.md", "frontmatter missing"),
        ("skills/bad-line/SKILL.md", "frontmatter unparseable line"),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact line 12: team_name:"),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact line 13: TeamDelete("),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact line 14: CLAUDE_CODE_EXPERIMENTAL"),
        ("references/nested/SKILL.md", "v1-artefact line 2: TeamCreate("),
        ("skills/no-name/SKILL.md", "name frontmatter name is missing"),
        ("skills/bare-name/SKILL.md", "name frontmatter name is missing"),
        ("skills/no-desc/SKILL.md", "description frontmatter description is missing"),
        ("skills/heading-first/SKILL.md", "frontmatter missing"),
        ("agents/typer.md", "subagent-ref line 7: no agent file for 'ghost-two'"),
        ("skills/bad-bytes/SKILL.md", "encoding not valid UTF-8"),
        ("references/deep/more/SKILL.md", "encoding not valid UTF-8"),
        ("references/deep/more/SKILL.md", "v1-artefact line 2: TeamDelete("),
    ]
    errors = [line for line in out.splitlines() if line.startswith("ERROR")]
    for where, rule in expected:
        assert any(where + ": " + rule in line for line in errors), (where, rule, out)
    assert len(errors) == len(expected), out
    warnings = [line for line in out.splitlines() if line.startswith("WARN")]
    for where, rule in [
        ("skills/bad-orchestrator/SKILL.md", "unknown-key frontmatter key 'owner'"),
        ("agents/nomodel.md", "model no model: field"),
        ("agents/nocomment.md", "model model: has no '# reason' comment"),
        ("skills/long-desc/SKILL.md", "description 1025 chars"),
    ]:
        assert any(where + ": " + rule in line for line in warnings), (where, rule, out)
    assert len(warnings) == 4, out


def test_clean_fixture_passes_without_warnings() -> None:
    code, out = lint(FIX / "harness_good")
    assert code == 0, out
    assert out.strip().endswith("0 error(s), 0 warning(s)"), out


def test_this_repo_team_and_plugin_pass() -> None:
    for target in (REPO / ".claude", REPO):
        code, out = lint(target)
        assert code == 0, out


def test_nothing_to_lint_is_an_error(tmp_path: Path) -> None:
    assert lint(tmp_path)[0] == 1
    assert lint(tmp_path / "missing")[0] == 2
```

### F3, F4: fixtures (exact content)

The 65-char bad directory and name is `abcdefghij` six times joined by `-`; the 64-char good one is the same string minus its last character. `long-desc` has a 1025-char description and the 64-char good skill a 1024-char one (boundary cases). The 64-char good `SKILL.md` deliberately has no newline after its closing `---`.

#### `tests/fixtures/harness_bad/agents/badconn.md`
```markdown
---
name: badconn
description: "Reads ledger entries."
model: sonnet  # routine reads
---

## Required connectors
- mcp__erp__search

```
#### `tests/fixtures/harness_bad/agents/caller.md`
```markdown
---
name: caller
description: "Delegates review work to a reviewer agent."
model: sonnet  # routine delegation
---

Spawn the reviewer with `subagent_type: "ghost"`.

```
#### `tests/fixtures/harness_bad/agents/fetcher.md`
```markdown
---
name: fetcher
description: "Fetches client records from the CRM."
model: sonnet  # routine lookups
---

## Required connectors
crm

```
#### `tests/fixtures/harness_bad/agents/nocomment.md`
```markdown
---
name: nocomment
description: "Agent whose model has no reason comment."
model: sonnet
---

```
#### `tests/fixtures/harness_bad/agents/nomodel.md`
```markdown
---
name: nomodel
description: "Agent with no model field."
---

```
#### `tests/fixtures/harness_bad/agents/typer.md`
```markdown
---
name: typer
description: "Starts a workflow step on another agent."
model: sonnet  # routine delegation
---

Run the step with `agentType: 'ghost-two'`.

```
#### `tests/fixtures/harness_bad/skills/Bad_Name/SKILL.md`
```markdown
---
name: Bad_Name
description: "A skill whose name breaks the kebab-case grammar."
---

```
#### `tests/fixtures/harness_bad/skills/abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghij/SKILL.md`
```markdown
---
name: abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghij
description: "A skill whose name is 65 characters long."
---

```
#### `tests/fixtures/harness_bad/skills/bad-bytes/SKILL.md` (written as bytes: `<0xE9>` below stands for the single raw byte 0xE9, which is not valid UTF-8; build it with `write_bytes`)
```markdown
---
name: bad-bytes
description: "A skill saved in the wrong encoding."
---

Caf<0xE9> notes.

```
#### `tests/fixtures/harness_bad/skills/bad-line/SKILL.md`
```markdown
---
name: bad-line
{not a key
description: "Frontmatter with an unparseable line."
---

```
#### `tests/fixtures/harness_bad/skills/bad-orchestrator/SKILL.md`
```markdown
---
name: bad-orchestrator
description: "Runs the bad fixture team."
owner: fixtures
---

| Agent | Required connector |
|-------|--------------------|
| fetcher-two | erp |

Step 1: TeamCreate(team="old")
Step 2: pass team_name: "old" to every spawn
Step 3: TeamDelete(team="old")
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

```
#### `tests/fixtures/harness_bad/skills/bad-orchestrator/references/deep/more/SKILL.md` (written as bytes: `<0xE9>` below stands for the single raw byte 0xE9, which is not valid UTF-8; build it with `write_bytes`)
```markdown
A deeper nested file:
TeamDelete(team="deep")
Caf<0xE9> notes.

```
#### `tests/fixtures/harness_bad/skills/bad-orchestrator/references/nested/SKILL.md`
```markdown
A nested file still written for v1:
TeamCreate(team="nested")

```
#### `tests/fixtures/harness_bad/skills/bare-name/SKILL.md`
```markdown
---
name:
description: "A skill whose name key has no value."
---

```
#### `tests/fixtures/harness_bad/skills/empty-desc/SKILL.md`
```markdown
---
name: empty-desc
description: ""
---

```
#### `tests/fixtures/harness_bad/skills/heading-first/SKILL.md`
```markdown
# Title
name: heading-first
description: "Line 1 is a heading, not ---."
---

```
#### `tests/fixtures/harness_bad/skills/long-desc/SKILL.md`
```markdown
---
name: long-desc
description: "Seeded over-long description. xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
---

```
#### `tests/fixtures/harness_bad/skills/no-close/SKILL.md`
```markdown
---
name: no-close
description: "Frontmatter that never closes."

Body text.

```
#### `tests/fixtures/harness_bad/skills/no-desc/SKILL.md`
```markdown
---
name: no-desc
---

```
#### `tests/fixtures/harness_bad/skills/no-frontmatter/SKILL.md`
```markdown
# No frontmatter

This skill forgot its frontmatter.

```
#### `tests/fixtures/harness_bad/skills/no-name/SKILL.md`
```markdown
---
description: "A skill with no name key."
---

```
#### `tests/fixtures/harness_bad/skills/wrong-dir/SKILL.md`
```markdown
---
name: right-name
description: "A skill whose directory does not match its name."
---

```
#### `tests/fixtures/harness_good/agents/researcher.md`
```markdown
---
name: researcher
description: "Looks up client records and summarises them."
model: sonnet  # routine lookups; no deep reasoning
tools: Read, Grep, mcp__crm__search
---

## Required connectors
- `crm`

## Working principles
Cite every record you use.

```
#### `tests/fixtures/harness_good/agents/writer.md`
```markdown
---
name: writer
description: >
  Drafts the client summary from the researcher's notes.
model: opus  # client-facing prose, judged by a reviewer
---

Write in plain English.

```
#### `tests/fixtures/harness_good/skills/abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghi/SKILL.md`
```markdown
---
name: abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghij-abcdefghi
description: >
  Description exactly at the limit. yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
---
```
#### `tests/fixtures/harness_good/skills/demo-orchestrator/SKILL.md`
```markdown
---
name: demo-orchestrator
description: "Runs the demo team. Use for 'run the demo', 're-run the demo', 'redo only the summary'."
---

4. Connector preflight. Skip this item if the table says "none". Run it before any agent call.

   | Agent | Required connector |
   |-------|--------------------|
   | {agent} | {server, as in `mcp__{server}__*`} |
   | researcher | crm |

Step 1. Spawn `subagent_type: "researcher"`, then `subagent_type: "writer"`.
Use `agentType: 'general-purpose'` for one-off checks; a template shows `subagent_type: "{name}"`.
v1 migration note: remove TeamCreate and TeamDelete calls.

```
#### `tests/fixtures/harness_good/skills/none-orchestrator/SKILL.md`
```markdown
---
name: none-orchestrator
description: "A second orchestrator whose agents need no connector."
---

| Agent | Required connector |
|-------|--------------------|
| {agent} | {server} |
| none | none |
| NONE | none |

```
#### `tests/fixtures/harness_good/skills/notes-style/SKILL.md` (valid UTF-8 that contains the character U+FFFD, bytes `EF BF BD`; it must pass)
```markdown
---
name: notes-style  # house style for client notes
description: "House style for client notes. Use when writing or editing a client note."
allowed-tools: Read
---

Short sentences. No jargon.
A lost character prints as �; flag it to the client.

```

### E1: `SKILL.md` Step 6.1, replaced in place (line 142)

Anchor (line 142, the whole line, quoted verbatim):

```markdown
1. **Files and references**: every agent file in place; every `SKILL.md` has `name` and `description`; cross-referenced names match; nothing was written to `.claude/commands/`; no v1 artefacts (`TeamCreate`, `TeamDelete`, `team_name`, experimental flags); where an Authority List exists, every citation opens to a line that supports the claim.
```

Replace it with this single line:

```markdown
1. **Files and references**: run `python3 scripts/lint_harness.py project/.claude` (path relative to this skill's directory) and fix every `ERROR` line; fix each `WARN` line or say in the report why it stays. The lint checks frontmatter, name grammar and that a skill's directory matches its name, non-empty descriptions, that every `subagent_type`/`agentType` names an agent file or a built-in type, that `## Required connectors` lines and the preflight table agree, and v1 artefacts; it exits 1 on any error. Where it cannot run (chat without code execution), check the same list by hand. The lint does not check that nothing was written to `.claude/commands/` or that every Authority List citation opens to a line that supports the claim; check those yourself. (adapted from references/crewai/lib/crewai/src/crewai/skills/validation.py:43 (MIT))
```

The two manual checks the lint cannot do (`.claude/commands/` and Authority List citations) stay as explicit instructions, so the step loses nothing. The chat fallback keeps the backlog's risk note: on chat the script runs only when code execution is enabled.

### E2: `SKILL.md` checklist. Insert after line 169

Anchor (line 169, verbatim): `- [ ] Execution mode written (per phase if mixed); no v1 artefacts.`

Insert:

```markdown
- [ ] `scripts/lint_harness.py` exits 0 on `project/.claude`, and every `WARN` line is fixed or explained.
```

### E3: `scripts/package-plugin.sh`. Replace lines 24-45

Anchor: from line 24 (`# 2. every skill has frontmatter with name and description; required skills present`) up to and including line 45 (`fi`, which closes the v1 grep). Line 46 is blank, and line 47 (`if [ "$fail" -ne 0 ]; then ...`) is unchanged. Replacement:

```bash
# 2. required skills present; every skill passes the shared harness lint
#    (frontmatter, name grammar and directory, description, subagent refs, v1 artefacts)
for s in finhub-harness finhub-harness-evolve; do
  [ -f "skills/$s/SKILL.md" ] || err "skills/$s/SKILL.md missing"
done
python3 skills/finhub-harness/scripts/lint_harness.py . || err "lint_harness.py found errors (see above)"
```

Also change line 49 `# 4. package` to `# 3. package`. CHANGED r1: the removed block's checks map to F1 on `.` as follows:
- frontmatter present (`frontmatter`, on `skills/*/SKILL.md`);
- `name` and `description` present (`name`, `description`, on `skills/*/SKILL.md`);
- the v1 regex, which is identical (`v1-artefact`). It runs on `skills/*/SKILL.md` **and** on every nested `skills/**/SKILL.md`, the same reach as the old `grep -r --include=SKILL.md`.

The old frontmatter loop (lines 28-38) also read only `skills/*/SKILL.md`, so frontmatter reach is unchanged.

F1 is stricter in four ways: name grammar, `dir-name`, `subagent-ref` and the 64-char limit. Both current plugin skills pass all four (simulated: `0 error(s), 0 warning(s)`).

**Intended behaviour change.** The old loop's regex `---\n(.*?)\n---\n` rejected a frontmatter-only `SKILL.md` with no newline after its closing `---`. F1 accepts it, as deepseek's `findClosingFrontmatter` does (`references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:923-934`, the closing line may end at end of file). The good fixture's 64-char skill pins this.

## Proof

Run from the repo root after the build. Expected values come from the scratchpad simulation.

| id | command | expected |
|---|---|---|
| P1 | `python3 skills/finhub-harness/scripts/lint_harness.py tests/fixtures/harness_bad; echo $?` | CHANGED r4. 24 `ERROR` lines, one per seeded defect: `bad-bytes` encoding; nested `references/deep/more/SKILL.md` encoding; `wrong-dir` dir-name; 65-char `name`; `Bad_Name` name grammar; `no-name` and `bare-name` name missing; `no-desc` description missing; `heading-first` frontmatter (line 1 not `---`); `typer.md` subagent-ref `'ghost-two'` (single-quoted `agentType`); deeper nested `references/deep/more/SKILL.md` v1-artefact `TeamDelete(`; `empty-desc` description; `caller.md` subagent-ref `'ghost'`; `bad-orchestrator` v1-artefact lines 11 `TeamCreate(`, 12 `team_name:`, 13 `TeamDelete(`, 14 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=`; nested `references/nested/SKILL.md` v1-artefact `TeamCreate(`; `no-frontmatter` and `no-close` frontmatter (missing); `bad-line` frontmatter (unparseable line); `badconn.md` connector; preflight `'fetcher' needs 'crm'`; preflight row `fetcher-two \| erp`. Then 4 `WARN` lines: `owner` unknown-key; `nomodel.md` model; `nocomment.md` model; `long-desc` description 1025 chars. Last line `lint_harness: 24 error(s), 4 warning(s)`; exit **1**; no `Traceback` on stdout or stderr |
| P2 | `python3 skills/finhub-harness/scripts/lint_harness.py tests/fixtures/harness_good; echo $?` | `lint_harness: 0 error(s), 0 warning(s)`; exit **0** |
| P3 | `python3 skills/finhub-harness/scripts/lint_harness.py .claude; echo $?` and the same with `.` | `.claude`: `0 error(s), 6 warning(s)` (five agents with no `model:`, plus `master-finhub-orchestrator` description at 1259 chars), exit **0**. `.`: `0 error(s), 0 warning(s)`, exit **0** |
| P4 | `.venv/bin/mypy --strict skills/finhub-harness/scripts/lint_harness.py tests/test_lint_harness.py`; `.venv/bin/ruff check skills/finhub-harness/scripts tests`; `.venv/bin/black --check skills/finhub-harness/scripts tests`; `wc -l skills/finhub-harness/scripts/lint_harness.py` | `Success: no issues found in 2 source files`; `All checks passed!`; black leaves the files unchanged; **≤150** (simulated 150, at the cap) |
| P5 | `.venv/bin/pytest -q` | **895 passed, 10 skipped** (baseline 891 + the 4 new tests); `pytest -q tests/test_lint_harness.py` gives 4 passed |
| P6 | `bash scripts/package-plugin.sh; echo $?` then `unzip -l dist/finhub-harness-skill.zip \| grep -c 'finhub-harness/scripts/lint_harness.py'` | prints `lint_harness: 0 error(s), 0 warning(s)` before the three dist lines; exit **0**; zip count **1** |
| P7 | `bash scripts/check-harness-refs.sh; echo $?` | no `FAIL` line; exit **0** |
| P8 | `grep -c 'scripts/lint_harness.py' skills/finhub-harness/SKILL.md` | **2** (E1 + E2) |
| P9 | `grep -c 'adapted from references/crewai/lib/crewai/src/crewai/skills/validation.py:43 (MIT)' skills/finhub-harness/SKILL.md` | **1** |
| P10 | `grep -c 'every agent file in place' skills/finhub-harness/SKILL.md` | **0** (old Step 6.1 line gone) |
| P11 | `wc -l < skills/finhub-harness/SKILL.md` | **198** (197 + E2; E1 is a one-for-one line swap) |
| P12 | `grep -c 'lint_harness.py' scripts/package-plugin.sh`; `grep -c 'TeamCreate' scripts/package-plugin.sh`; `grep -c '^# 3. package' scripts/package-plugin.sh` | **1**; **0**; **1** |
| P13 | `grep -c 'references/crewai/lib/crewai/src/crewai/skills/validation.py:43 (MIT)' skills/finhub-harness/scripts/lint_harness.py`; `grep -c 'references/deepseek_harness/packages/skill/skill/src/index.ts:20 (MIT)' skills/finhub-harness/scripts/lint_harness.py` | **1**; **1** |

### Prose gates (adoption)

| gate | command | expected |
|---|---|---|
| attribution | P9 and P13 | the SKILL line cites crewai `validation.py:43 (MIT)`. The script docstring cites crewai `:43` and deepseek `skill/src/index.ts:20`, both MIT |
| no 8-word verbatim runs | 8-gram overlap between {F1, F2, F3, F4, E1 text, E2 text} and the cited files (`validation.py`, `models.py`, `skill_model.py`, both deepseek `index.ts`, `_frontmatter.py`, `crew.py`, `agent_definitions.py`) | simulated: **0** in prose. The only shared 8-gram is the token run of the adopted name regex literal `^[a-z0-9]+(?:-[a-z0-9]+)*$` in F1. That is the rule itself, MIT and attributed in the docstring, not copied prose |
| Hangul 0 | `LC_ALL=C.UTF-8 grep -rlP '[\x{AC00}-\x{D7A3}]' skills/finhub-harness/SKILL.md skills/finhub-harness/scripts tests/test_lint_harness.py tests/fixtures/harness_bad tests/fixtures/harness_good` | no output (the only Korean in the repo stays the orchestrator's phase markers in `.claude/skills/master-finhub-orchestrator/`) |
| packager | P6 | exit 0 |
| check-harness-refs | P7 | exit 0 |
| pytest unchanged | P5 and `git diff --stat -- tests/*.py` | the only test change is the new `tests/test_lint_harness.py`; no existing test is modified; 891 existing tests still pass |

## Test plan

Unit cases (F2):
1. `test_bad_fixture_names_every_seeded_defect` (CHANGED r4): exit 1 with no `Traceback` in stdout + stderr (`lint()` returns both). Each of the 24 seeded errors is named with its file and rule id, and there are **exactly** 24 `ERROR` lines, which catches over-reporting. The 4 seeded warnings are named, and there are exactly 4 `WARN` lines.
2. `test_clean_fixture_passes_without_warnings`: exit 0, and the output ends `0 error(s), 0 warning(s)`. This exercises the false-positive guards:
   - a folded `>` description (`writer.md`) and a folded `>` 1024-char description, so stripping a lone block marker is pinned at the boundary (CHANGED r3);
   - an unquoted `name:` with a trailing ` # comment` (`notes-style`), so the comment cut is pinned (CHANGED r3);
   - a valid UTF-8 line containing the character U+FFFD (`notes-style`), so a valid file is never reported as `encoding` (CHANGED r4);
   - `model:` with a reason comment;
   - `tools:` on an agent;
   - `allowed-tools` on a skill;
   - backticked bullet connector line;
   - `{agent} | {server}` placeholder row, a `| none | none |` row and a `| NONE | none |` row (`none-orchestrator`);
   - Template A's 3-space-indented item-4 table with its own placeholder row (`demo-orchestrator`);
   - boundary values: a 64-char name and a 1024-char description;
   - a `SKILL.md` with no newline after its closing `---`;
   - `"{name}"` placeholder ref;
   - `'general-purpose'` built-in with single quotes;
   - prose "remove TeamCreate and TeamDelete calls" without `(`.
3. `test_this_repo_team_and_plugin_pass`: `.claude` and the repo root both exit 0. The 13 real quoted `subagent_type`/`agentType` references in `.claude/` all resolve (CHANGED r1: count corrected from 14).
4. `test_nothing_to_lint_is_an_error`: an empty dir exits 1; a missing dir exits 2.

Must still pass, all unmodified: the existing 891 tests; `ruff check src tests`; `black --check src tests`; `mypy --strict src`; `scripts/package-plugin.sh`; `scripts/check-harness-refs.sh`.

Mutation targets. QA applies each to a scratch copy of F1 and runs `pytest -q tests/test_lint_harness.py`. A mutant is killed when the run fails. All 42 were simulated (revision 4): **42/42 killed**.

| id | mutation (in F1) | killed by | simulated |
|---|---|---|---|
| M1 | `name and name != expect` → `name and False` (drop `dir-name`) | test 1 (`wrong-dir` missing) | killed |
| M2 | `len(name) > 64 or not` → `not` (drop the length cap) | test 1 (65-char name missing) | killed |
| M3 | `if not desc:` → `if False:` (drop empty-description) | test 1 | killed |
| M4 | `if ref not in names and` → `if False and` (drop `subagent-ref`) | test 1 (`ghost` missing) | killed |
| M5 | `V1_RE` pattern prefixed with `(?!)` (never matches) | test 1 (`TeamCreate(` missing) | killed |
| M6 | missing-frontmatter branch returns `{}` instead of reporting | test 1 (`no-frontmatter` missing; count off) | killed |
| M7 | `CONN_RE.match(s) and "__" not in s` → `CONN_RE.match(s)` | test 1 (`mcp__erp__search` accepted) | killed |
| M8 | `sorted(declared - table)` → empty | test 1 (`fetcher`/`crm` missing) | killed |
| M9 | `sorted(table - declared)` → empty | test 1 (`fetcher-two \| erp` missing) | killed |
| M10 | `if not agents and not skills:` → `if False:` | test 4 (empty dir exits 0) | killed |
| M11 | `sorted(set(data) - known)` → empty (drop unknown-key) | test 1 (`owner` warning missing) | killed |
| M12 | `BUILTIN` set without `general-purpose` | tests 2 and 3 (false ERROR on the built-in) | killed |
| M13 | CHANGED r1: `if m and "{" not in m.group(0)]` → `if m]` in `preflight_rows` | test 2 (the `none-orchestrator` placeholder row becomes an orphan ERROR) | killed |
| M14 | `elif "#" not in data["model"]:` → `elif False:` | test 1 (`nocomment.md` warning missing) | killed |
| M15 | `if "model" not in data:` → `if False:` | test 1 (`nomodel.md` warning missing) | killed |
| M16 | `len(name) > 64 or not NAME_RE.match(name)` → `len(name) > 64` (drop grammar) | test 1 (`Bad_Name` missing) | killed |
| M17 | drop ` or "---" not in lines[1:]` (closing check) | test 1 (`no-close` crashes the run or is missed) | killed |
| M18 | `elif not line.lstrip().startswith("#"):` → `elif False:` (drop unparseable-line error) | test 1 (`bad-line` missing) | killed |
| M19 | remove `team_name:` from `V1_RE` | test 1 (line 12 missing) | killed |
| M20 | remove `TeamDelete\(` from `V1_RE` | test 1 (line 13 missing) | killed |
| M21 | remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=` from `V1_RE` | test 1 (line 14 missing) | killed |
| M22 | `elif len(desc) > 1024:` → `elif False:` (drop length WARN) | test 1 (`long-desc` warning missing) | killed |
| M23 | `> 1024` → `> 2048` (loosened) | test 1 | killed |
| M24 | `> 1024` → `> 1023` (tightened) | test 2 (1024-char good description warns) | killed |
| M25 | `len(name) > 64` → `len(name) > 63` | test 2 (64-char good name errors) | killed |
| M26 | `TABLE_RE` `^ *\|` → `^\|` (column 0 only, the r0 defect) | test 2 (indented template table: `researcher`/`crm` no-row ERROR) | killed |
| M27 | `not in ("", "none")` → `not in ("",)` (drop none skip) | test 2 (`none \| none` orphan ERROR) | killed |
| M28 | nested glob `skills/**/SKILL.md` → `skills/*/SKILL.md` | test 1 (nested `TeamCreate(` missing) | killed |
| M29 | CHANGED r2: empty-name `report(...)` → `pass` | test 1 (`no-name`, `bare-name` missing) | killed |
| M30 | drop `lines[0] != "---" or ` (line-1 check) | test 1 (`heading-first` missing) | killed |
| M31 | `REF_RE` `(?:subagent_type\|agentType)` → `(?:subagent_type)` | test 1 (`typer.md` `ghost-two` missing) | killed |
| M32 | drop `.lower()` from the `none` skip | test 2 (`NONE \| none` orphan ERROR) | killed |
| M33 | nested glob `skills/**/SKILL.md` → `skills/*/*/*/SKILL.md` (one depth only) | test 1 (`deep/more` `TeamDelete(` missing) | killed |
| M34 | empty-scalar guard reverted to `raw[:1] in "'\""` (the r1 crash) | test 1 (`IndexError` traceback, no findings) | killed |
| M35 | CHANGED r3: `REF_RE` `\s*["']([A-Za-z0-9_-]+)["']` → `\s*["]([A-Za-z0-9_-]+)["]` (judge N14) | test 1 (single-quoted `typer.md` `ghost-two` missing) | killed |
| M36 | CHANGED r4: `if text.encode() != raw:` → `if False:` (drop the encoding report) | test 1 (`bad-bytes` and nested `deep/more` missing) | killed |
| M37 | `errors="replace"` → `errors="strict"` (the r2 crash) | test 1 (`Traceback` in stderr) | killed |
| M38 | `return raw.split(" #", 1)[0].strip()` → `return raw.strip()` | test 2 (`notes-style` name and dir-name ERRORs) | killed |
| M39 | delete the `re.sub(r"^[>\|][-+]?\s*", "", raw)` line | test 2 (folded 1024-char description measures 1026: WARN) | killed |
| M40 | CHANGED r4 (judge F1): the nested read `texts[path] = read(path)` → `path.read_bytes().decode("utf-8", errors="replace")` (decodes, never reports) | test 1 (nested `deep/more` encoding ERROR missing) | killed |
| M41 | CHANGED r4 (judge F13): the nested read → `path.read_text(encoding="utf-8")` (strict) | test 1 (`UnicodeDecodeError` traceback, no findings) | killed |
| M42 | CHANGED r4: `if text.encode() != raw:` → `if "\ufffd" in text:` (the r3 heuristic) | test 2 (false `encoding` ERROR on the valid U+FFFD line in `notes-style`) | killed |

## Does not cover

- **Scope of the scan.** All rules apply to `agents/*.md` and `skills/*/SKILL.md`. CHANGED r1: nested `skills/**/SKILL.md` files get the line rules only (`v1-artefact`, `subagent-ref`, preflight-table rows), not frontmatter rules. A skill's `references/*.md` are not scanned, so a spawn table or `subagent_type` written only in a reference file is not checked.
- **Preflight table recognition.** The header must read `| Agent | Required connector |`, indented with spaces at most (tabs not recognised). A `none` row is skipped wherever it appears, so a table mixing `none` with real rows still checks the real rows. Agent types given as bare table cells (the `| Agent | \`subagent_type\` |` spawn table in Template C) are not resolved; only quoted `subagent_type:`/`agentType:` values are.
- **Namespaced and unquoted types.** Plugin-namespaced types (`"plugin:agent"`) and unquoted values are skipped.
- **The built-in list is fixed** (`general-purpose`, `Explore`, `Plan`, `statusline-setup`, `claude-code-guide`). A new built-in type would be reported as a dangling reference until the set is updated (known false positive).
- **Not a YAML parser.** Flow mappings, anchors and multi-document frontmatter are not understood. An escaped quote inside a quoted value ends the value early, so the reported description length can be short. A valid but unusual top-level line may be flagged `frontmatter` (false positive, fix by quoting).
- **Description quality.** The lint does not judge what a description says; the trigger evals (Step 6.4) still do that.
- **Not checked at all:**
  - `model:` value validity, `tools:` validity, and connector *presence* (the run-time preflight from C1 does that);
  - `.claude/commands/` and Authority List citations (E1 keeps both as manual checks);
  - Workflow-script rules (`.filter(Boolean)`, literal `meta`);
  - C34's "coordinator has no work tools" rule: the coordinator here is an orchestrator skill with no `tools:` field;
  - C35's manager-composition rule.
- **Chat without code execution** cannot run the script. E1 keeps the manual fallback.
- **v1 migration tables.** `v1-artefact` also fires on a generated harness's own migration table if it shows v1 *call* syntax inside a `SKILL.md`. That matches today's `package-plugin.sh` behaviour, and reference files are not scanned.
- **Unusual file types (CHANGED r4, judge round 4; no behaviour added because the script is at the 150-line cap).**
  - A `SKILL.md` or agent `.md` that is a directory, a dangling symlink or an unreadable file crashes the run with a traceback (`IsADirectoryError`, `FileNotFoundError`, `PermissionError`). Test 1's `Traceback` assertion would catch this only for fixture files.
  - A FIFO named `SKILL.md` makes the run hang on read.
  - A file that starts with a UTF-8 BOM gets `frontmatter missing --- delimited frontmatter` instead of an encoding message, because line 1 is `\ufeff---`.
- **Platform.** The test's path assertions use `/`, so they are POSIX only. CI runs on ubuntu.
- **Current warnings in this repo, not fixed here (outside C2's targets):**
  - five of six agents in `.claude/agents/` have no `model:` key; their tier is stated in body prose;
  - the `master-finhub-orchestrator` description is 1259 chars, over the 1024-char skill limit in A5. It loads on Claude Code today, but a claude.ai skill upload may reject it. **Flag for Daniel.**

## Authority List

| id | claim | evidence | target |
|---|---|---|---|
| A1 | A skill whose directory name differs from its frontmatter `name` is a defect (rule `dir-name`, ERROR) | references/crewai/lib/crewai/src/crewai/skills/validation.py:54 | F1 |
| A2 | A valid name matches `^[a-z0-9]+(?:-[a-z0-9]+)*$` (kebab-case, no leading, trailing or double hyphen) | references/deepseek_harness/packages/skill/skill/src/index.ts:20; references/crewai/lib/crewai/src/crewai/skills/validation.py:15 | F1 |
| A3 | A name longer than 64 chars is invalid | references/crewai/lib/crewai/src/crewai/skills/validation.py:13; references/autogpt/classic/forge/forge/components/skills/skill_model.py:27 | F1 |
| A4 | An empty description is invalid (minimum length 1) | references/crewai/lib/crewai/src/crewai/skills/models.py:63 | F1 |
| A5 | The skill description limit is 1024 chars | references/crewai/lib/crewai/src/crewai/skills/models.py:21; references/autogpt/classic/forge/forge/components/skills/skill_model.py:32 | F1 |
| A6 | Frontmatter is usable only when line 1 is exactly `---` and a closing `---` line exists; otherwise the file has no metadata | references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:913; references/openharness/src/openharness/skills/_frontmatter.py:53 | F1 |
| A7 | `name` and `description` are both required, and an empty string counts as missing (the file is otherwise ignored) | references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:812; references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:984 | F1 |
| A8 | CHANGED r4 (count only). Unknown frontmatter keys produce a WARN, never an ERROR | NET-NEW. The backlog's risk note (`01b_capability-scout_backlog.md:92`) says over-strict rules could block a valid harness. deepseek rejects only specific *legacy* spellings (`index.ts:993-995`), not unknown keys in general, so no reference contradicts this. Verification that can fail: P1 shows `owner` as `WARN` and not among the 24 errors; M11 | F1 |
| A9 | `allowed-tools`, `author` and `version` are recognised optional skill keys, as are `disable-model-invocation` and `user-invocable`. The rest of the recognised set (`license`, `tags`, `metadata`, `argument-hint`) is a NET-NEW extension: harmless, because unknown keys only warn | references/autogpt/classic/forge/forge/components/skills/skill_model.py:43; references/deepseek_harness/packages/skill/skill-filesystem/src/index.ts:993 | F1 |
| A10 | Every quoted `subagent_type`/`agentType` value must name an agent under DIR or a built-in type; otherwise ERROR `subagent-ref`. Placeholders `{...}` and namespaced values are skipped | NET-NEW. Claude Code agent types are not modelled in any reference. crewai's closest check validates manager composition at config load (`crew.py:725`), not name resolution. Verification that can fail: P1 `ghost`; P3 shows all 13 real quoted references in `.claude/` resolve (0 errors); M4, M12. CHANGED r1 (count 14 → 13 only) | F1 |
| A11 | v1 harness prose calls `TeamCreate(` with `team_name:`, so these call/assignment forms (plus `TeamDelete(` and the experimental flag) mark a v1 artefact; bare mentions do not | references/revfactory_harness/skills/harness/references/team-examples.md:39 | F1, E3 |
| A12 | A `## Required connectors` line must be a bare server token (`^[A-Za-z0-9][A-Za-z0-9_-]*$`, no `__`), after one optional bullet and backticks | NET-NEW. This is the C1 contract in this repo's `skills/finhub-harness/SKILL.md:92` ("the segment between `mcp__` and the next `__`"), not a reference. The pattern allows the upper case and `_`/`-` seen in real server segments. Verification that can fail: P1 `mcp__erp__search`; P2 backticked bullet `crm` passes; M7 | F1 |
| A13 | CHANGED r1. Declared (agent, server) pairs and preflight-table rows must match both ways. Tables may be indented with spaces, as in Template A item 4. Placeholder `{...}`, `none` and separator rows are skipped | NET-NEW. This is the C1 checklist line in this repo's `skills/finhub-harness/SKILL.md:180`; the indented table and the "none" skip rule are this repo's `skills/finhub-harness/references/orchestrator-template.md:52-56`. Verification that can fail: P1 `fetcher`/`crm` and `fetcher-two \| erp`; P2 (indented template table and `none` row give 0 errors); M8, M9, M13, M26, M27 | F1 |
| A14 | A DIR with no agent or skill files is an ERROR (exit 1); a missing DIR is a usage error (exit 2) | NET-NEW. This stops a silent pass when the project root is given instead of `.claude`. Verification that can fail: test 4; M10 | F1 |
| A15 | A description over 1024 chars is a WARN, not an ERROR | NET-NEW. This repo's own `master-finhub-orchestrator` description is 1259 chars and loads on Claude Code. The backlog requires `.claude/` to exit 0. Verification that can fail: P3 shows `0 error(s), 6 warning(s)` and exit 0 | F1 |
| A16 | Frontmatter is read by a stdlib line parser (quoted value, block indicator, continuation lines, trailing `# comment`), not a YAML library | NET-NEW. The backlog requires stdlib only. OH14 uses `yaml.safe_load` (`_frontmatter.py:57`), which is a dependency choice, not a contradiction. Verification that can fail: P3 (all 14 real files parse) and P2 (folded `>` description parses); M6 | F1 |
| A17 | Recognised agent keys are `name`, `description`, `tools`, `model`, `color` | NET-NEW. Claude Code agent frontmatter is not modelled in any reference. `name`/`description`/`tools`/`model` come from this repo's SKILL.md Step 3 (`:90`); `color` is the Claude Code agent UI field. Unknown keys only warn (A8). Verification that can fail: P2 and P3 show no `unknown-key` warning on real or fixture agents | F1 |
| A18 | An agent with no `model:` key, or with `model:` but no `# reason` comment, gets a WARN | NET-NEW. SKILL.md Step 3 (`:90`) asks for "`model` with the reason as a comment". It is a warning because five of this repo's six agents omit `model:` and the backlog requires `.claude/` to exit 0. Verification that can fail: P1 `nomodel.md`/`nocomment.md`; M14, M15 | F1 |
| A19 | CHANGED r1. `package-plugin.sh` delegates its frontmatter and v1 checks to F1 on `.`, so there is one rule set. The v1 rule keeps the old grep's any-depth reach via F1's nested `skills/**/SKILL.md` scan. One intended relaxation: a frontmatter-only file with no newline after its closing `---` now passes | NET-NEW. Backlog adoption shape (`01b_capability-scout_backlog.md:89`). Verification that can fail: P6 (exit 0, lint summary printed) and P12. In simulation, a scratch skill with `name: Bad_Name` and `TeamCreate(`, and separately a nested `skills/finhub-harness/references/x/SKILL.md` containing `TeamCreate(`, each made the packager print `Validation failed; nothing packaged.`. P1 nested fixture; M28 | E3 |
| A20 | CHANGED r4. A file whose bytes are not valid UTF-8 (decoding with replacement does not round-trip to the same bytes) produces an `encoding` ERROR for that file, for top-level and nested files alike. The scan continues, so other findings are not lost. A valid file containing U+FFFD is not reported | NET-NEW (added r3). This is the judge's round-3 note (a); no reference lints file encodings. Verification that can fail: P1 `bad-bytes` and nested `deep/more` ERRORs alongside the other 22; test 1's `Traceback` assertion; test 2's valid U+FFFD line; M36, M37, M40, M41, M42 | F1 |
