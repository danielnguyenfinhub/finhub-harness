# Safe update: plan against a stored baseline, stage conflicts, edit nothing

> The decision order, the per-path cases and the conflict reasons are adapted from references/repository_harness/crates/harness/src/application/service.rs:516 and :238 and references/repository_harness/crates/harness/src/domain/model.rs:155; staging apart from live files from references/repository_harness/docs/decisions/0025-latest-release-self-update-and-human-directed-conflicts.md:49; the marker lines from references/repository_harness/crates/harness/src/application/service.rs:560 (MIT, Hoang Nguyen). Ideas only; fresh text and code.

Use this when a harness's files were installed from a source (a plugin, a template) and the source has a new version, while someone may have edited the installed copies. `scripts/safe_update.py` answers, per file, what is safe to do, and stages the files that are not. It does not apply anything.

## 1. What you need

Three folders: `BASE`, the copy installed last time (keep it when you install; without it nothing here works); `LOCAL`, the files on disk now; `UPSTREAM`, the new version. A harness that never stored its installed copy has no baseline: say so and ask the user instead of guessing which side changed.

## 2. Commands

Run from the project root.

| Command | What it does |
|---------|--------------|
| `plan --baseline B --local L --upstream U` | Prints `PLAN <action> <path> (<reason>)` for every path that needs a decision, then `SUMMARY`. Exit 0 with no conflict, 4 with one. |
| `stage --baseline B --local L --upstream U --out DIR` | Prints the same plan and copies `BASE`, `LOCAL` and `UPSTREAM` of each conflicting path under `DIR/<path>/`. Refuses an `--out` inside the local tree. |
| `markers FILE [FILE ...]` | Exit 4 and `MARKER file:line` for each line that starts a conflict marker. Run it on a file an agent merged by hand. |

Actions: `update` (take upstream), `keep-local`, `keep`, `create`, `delete`, `preserve`, `conflict`.

## 3. Rules

| Id | Rule |
|----|------|
| R1 | Decide from three comparisons before any merge tool: LOCAL equals BASE takes UPSTREAM; UPSTREAM equals BASE keeps LOCAL; LOCAL equals UPSTREAM keeps LOCAL. Only when all three differ is it a conflict (`overlapping-changes`). |
| R2 | Each path has exactly one case: 14 combinations of present or absent and equal or different (the tests list them). A file edited locally and removed upstream is `modified-but-removed`, never a delete. A file removed locally that upstream changed is `missing-managed-file`. A file on disk that was never installed and differs from upstream is `existing-unmanaged-path`. |
| R3 | A conflict is exit 4 and has a named reason; the report gives the reason, not only the word conflict. |
| R4 | A conflict changes no live file. `stage` copies the three versions apart, and nothing is written into the local tree. |
| R5 | A symlink in any of the three trees is a conflict (`unsafe-path`); it is never followed or copied. |
| R6 | A hand-resolved file is not accepted while a line starts `<<<<<<< `, `||||||| `, `=======` or `>>>>>>> `. |

## 4. Using it

1. Run `plan`. Show the user the plan. For `update`, `delete` and `create`, edit each file after the backup gate of `finhub-harness-evolve` Phase 3 and a yes for that file (its item 8).
2. For a conflict, run `stage`, show the three versions, and ask the user to choose. Do not write partial merge markers into a live instruction file.
3. After a resolution, run `markers` on the resolved file before it replaces the live one.
4. Store the new `UPSTREAM` as the next `BASE` only after every path is applied or consciously kept.

## Does not cover

- Merging text: nothing here calls `git merge-file`, so an `overlapping-changes` path is resolved by a person or by an agent the user directs.
- Applying the plan: no file is written, so there is no journal or recovery; the backup gate covers one file at a time.
- Resuming after a conflict, a version-order guard, and a lock against edits between planning and applying: not adopted.
- Chat and Cowork have no shell: the three-way table can be done by hand there, and the script is unverified on those surfaces.
