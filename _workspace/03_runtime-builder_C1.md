# runtime-builder report: adoption C1 (connector preflight)

Status: PARTIAL. E1-E9 built; P-1, P-4 gates green. P-2 (live fixture) and P-3 (cold generation) NOT RUN.

## Files
- modified: skills/finhub-harness/SKILL.md (E1, E2, E3), skills/finhub-harness/references/orchestrator-template.md (E4, E5 x2), skills/finhub-harness/references/surfaces.md (E6), docs/surface-verification.md (E7), README.md (E9)
- deleted (git rm, staged): src/master_finhub/factory/{__init__,evolver,skill_compiler,team_generator}.py; directory gone (E8)
- Not committed. tests/ and references/ untouched.

## Claims implemented
A1, A2, A4, A5, A6, A7, A8, A10, A11, A12 -> E1/E4 prose (greps below). A3 -> E1 (body section; P-3 not run). A9 -> E4 "deferred listings included" (P-2 not run). A13 -> attribution line in SKILL.md:1 and orchestrator-template.md:1. A14/A15 -> E8, pytest unchanged. A16 -> E9, grep 0.

## Gate: P-1 (all match expected)
E1 1; E2 1; E3 1; attribution SKILL.md:1 / orchestrator-template.md:1; E4 `^4. Connector preflight` 1 (line 52, after item 3 at 51, before `### Step 1` at 63); Do not stop without asking 1; phase as skipped 1; Present means listed, not working 1; Missing connector {server} for agent {agent} 1; E5 2; E6 1; E7 2; E8 `gone`, grep of src tests scripts pyproject.toml README.md empty; E9 0; SKILL.md `wc -l` 197.

## Gate: P-4
- 8-word run script vs agent_definitions.py: 0 hits in all four files.
- Hangul `grep -cP '[\x{AC00}-\x{D7A3}]'`: 0 in all five files; `LC_ALL=C.UTF-8 grep -rnP '\p{Hangul}' skills/` rc=1 (no output).
- `bash scripts/package-plugin.sh` exit 0 (dist/finhub-harness.plugin 94462 bytes).
- `bash scripts/check-harness-refs.sh` exit 0; 40 PASS, 0 FAIL.
- `.venv/bin/python -m pytest -q`: 891 passed, 10 skipped.
- `git diff --stat -- tests/`: empty.

## Could not run
- P-2 live fixture (absent and present, A9 scoring with `ping` requirement): the fixture creation plus `claude -p ... --permission-mode bypassPermissions` command was blocked by the auto-mode classifier ("Create Unsafe Agents"). I did not retry or work around it. Nothing was executed and A9 is UNTESTED here. Fixture recipe and a9 script (with the extra `ping` check) are in the design; needs your approval or a run by someone with permission.
- P-3 cold generation: this agent has no sub-agent tool, so not run. A3 verification (P-3 grep) is outstanding.
- P7 stays empty by design (manual, chat/Cowork).

## AMBER actions
None (no dependency changes). Deletion of the four 0-byte stubs is within the design's file list.

## Deviations from design
- E4 inserted with no blank line between item 3 and item 4 (design: "between line 51 and the blank line before Step 1"). No other deviation.
