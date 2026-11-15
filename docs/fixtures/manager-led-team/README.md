# Manager-led team fixture (made-up data)

A small team built in the manager-led shape (`skills/finhub-harness/references/team-patterns.md` §1-5a, rules MT1 to MT8) to try the shape on a real run. All data is invented. Nothing here sends, writes a record or publishes. It is not shipped by the packager.

## What is in it

| Piece | File | Role |
|---|---|---|
| Manager | `.claude/skills/refi-pack-manager/SKILL.md` | Reads the brief, plans, staffs, summarises, accepts |
| Existing team | `.claude/skills/doc-checklist/SKILL.md` + `.claude/agents/doc-checker.md` | Stands in for a team that was already in the project |
| Specialists | `.claude/agents/statement-reader.md`, `.claude/agents/payslip-reader.md` | One job each, with `Covers:` and a `tools:` list |
| Shared method | `.claude/skills/income-lines/SKILL.md` | The one skill both readers use |
| Data | `data/` | Brief, received-documents list, statement (page 3 unreadable on purpose), two payslips |

`python3 skills/finhub-harness/scripts/lint_harness.py docs/fixtures/manager-led-team/.claude` gives 0 errors and 0 warnings (`tests/test_manager_led_fixture.py`).

## Live run, 2026-11-15

Outputs are in `run-2026-11-15/_workspace/`. The lead session acted as the manager; the three workers ran as separate sub-agents on the haiku model.

| Rule | What the run showed |
|---|---|
| MT1, MT8 | The manager wrote the plan and the summary and did not accept the pack as complete |
| MT3 | The document check went to the existing `doc-checklist` team; its files were not edited |
| MT4 | Each reader did only its own document type, with the shared `income-lines` method |
| MT5 | `payslip-reader` matched net pay against `02_statement.md` on the board and reported that it did not open the bank statement |
| MT6, SW6 | `statement-reader` reported page 3 `NOT RUN` and added no row for October; `payslip-reader` marked the 15 Oct net pay "cannot be checked", not "not matched"; the manager asked the owner for the page and filled nothing in |
| SW5 | Both readers ended `STATUS: partial`; neither marked its work done |

## What this run does not show

- The workers ran as general-purpose sub-agents told to read their role file, not as registered agent types, so the `tools:` and `model:` lines of the agent files were not enforced by the host (the model was set on the call).
- The existing team was used by following its skill's steps and briefing its worker; the `doc-checklist` skill was not invoked through the Skill tool. Whether the `income-lines` skill was loaded through the Skill tool or read as a file by each worker was not recorded.
- One run, one seeded fault. The happy path and the partial re-run scenario were not run.
- MT2 (start alone, propose the team) and MT7 (shared records wait for the owner's yes) were not exercised: the team was asked for, and the fixture has no outside effect.
- Claude chat and Cowork were not tried.
