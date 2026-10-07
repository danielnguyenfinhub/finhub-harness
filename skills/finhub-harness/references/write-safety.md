# Write safety: the ownership ladder and honest labels

> Adapted from references/meta_harness/docs/architecture/runtime-capabilities.md:46 (Apache-2.0) for the ladder and from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0) for the labels. Rewritten for Claude surfaces, not copied; the Writers table, its ten rules and the checker are ours.

Use this whenever a generated orchestrator can have two or more workers writing files in the same run. Being able to launch workers in one message does not make their edits safe: if two of them can write the same file, the result depends on timing. This file says how to keep writers apart and how to say truthfully how well that works.

## The ladder

Pick the highest rung the surface really provides. Lower one rung at a time, and write down why.

| Rung | Label | True only when | Same-batch overlap |
|------|-------|----------------|--------------------|
| 1 | `enforced` | Something other than the brief stops a write outside the role's paths: a path-scoped permission rule or a hook that denies the path. | forbidden |
| 2 | `workspace-enforced` | Each writer works in its own worktree or copy (`isolation: 'worktree'`, `team-patterns.md` section 4, `execution-modes.md` section 1) and the orchestrator merges the results one at a time, settling each conflict before the next. | allowed |
| 3 | `advisory` | Each brief's Scope line names disjoint paths and nothing stops a worker from writing elsewhere. | forbidden |
| 4 | `serialised` | One writer runs at a time. The next starts after the previous worker's report has been accepted. | alone |

Reading the last column: `forbidden` means two writers on this rung may not share a batch if their paths overlap. `allowed` means isolation makes the overlap safe to run, with a merge step afterwards; the checker therefore skips any pair in which one writer is `workspace-enforced`, because that writer's edits reach the shared checkout only at the merge. `alone` means the writer's batch holds no other writer.

A role is left out of the table only if nothing it can use can write. A `tools:` list without `Edit`, `Write` and `Bash` (and without any MCP tool that writes) stops the role writing through those tools (`SKILL.md` Step 3). A role that keeps `Bash`, such as a reviewer that runs a linter or the tests, can still write files, so it gets a row whose Writes names the paths its commands may touch; or the orchestrator states that its Bash use is read-only, and QA opens the command and shows it. `tools:` limits tools, not paths, so it cannot keep a writer inside its own paths and does not make a writer `enforced`.

## The Writers table

Every orchestrator section that launches writers in parallel carries one table under a heading named `Writers` (level 2 to 4). Keep each worker's Scope line in step with its row; the checker does not compare the two. A harness with a single writer needs no table and must not be checked with `--require`.

```markdown
## Writers

| Batch | Role | Writes | Label | Wanted | Mechanism or reason |
|-------|------|--------|-------|--------|---------------------|
| 1 | extractor-a | `_workspace/a/**` | advisory | enforced | no path hook is set up here |
| 1 | extractor-b | `_workspace/b/**` | advisory | enforced | no path hook is set up here |
| 2 | merger | `_workspace/merged.md` | serialised | serialised | |
```

- **Batch**: a whole number (`1`, `01` and `Batch 1` are the same batch); writers with the same number may be running at the same time. After a plain run of `Agent` calls, batch 2 starts when every batch 1 report is accepted. Under `pipeline()`, which `team-patterns.md` section 1-1 recommends for staged work, each item moves to the next stage without waiting, so stages of different items run together: put every stage that writes in one batch.
- **Writes**: the paths or globs the role may write, comma separated, one plain path each. An empty cell, `**`, a path starting with `/` or `~`, a `..` segment, a `{`, or a part with a space, a quote, a backtick, `;`, `:`, `#`, `(` or `<br` (an annotated path such as `src/a.py (new)`) means "unknown", which counts as overlapping everything. Write paths relative to one root.
- **A row is one worker.** A role launched once per item (a `pipeline()` stage, a per-item fan-out) is many workers, and two instances that share a path overlap with no second row to show it. Give such a row a per-item part in Writes, written `<item>` (for example `_workspace/<item>/draft.md`), or write one row per instance. A Role that says per item, per file, per instance, each item, each file, each instance or N instances needs that part (or a glob) in every path of its Writes cell, or it is W9; a Role that says none of these is not caught.
- **Label**: the guarantee the run actually has (rung words above). **Wanted**: the rung the design asked for.
- **Mechanism or reason**: the thing that makes rung 1 or 2 true, and the reason whenever Label sits lower than Wanted.

## How to choose

Each step ends with the checker rules that catch a breach, or `[not checked]` where the table cannot show it.

1. List each writer's Writes. If a writer's paths cannot be named in advance, leave Writes empty; it then overlaps everyone. A role run once per item gets a per-item part. [W2 W9]
2. Put writers that may run together in one batch. After plain `Agent` calls, batch 2 starts only when every batch 1 report is accepted; under `pipeline()`, every stage that writes shares one batch. [not checked]
3. If writers in a batch have overlapping Writes, give each its own worktree (rung 2) or move them into separate batches (rung 4). Never label overlapping writers `advisory` or `enforced`. [W2 W3]
4. If the Writes are disjoint, use rung 1 when a mechanism exists, otherwise rung 3. [not checked]
5. Wanted is the rung you started from, Label is what you got. If a correctness requirement needs rung 1 or 2 and neither exists, use rung 4 or stop; do not accept an instruction in a brief in its place. [W5]

## What an honest label is

A label states how strong the guarantee is, not how firmly the brief is worded. It is honest when all of these hold:

- It is one of the four words, in the Label and Wanted columns alike. [W1]
- Rung 1 and rung 2 rows name the mechanism, so a reader can open it and see it. [W4]
- No line that says `advisory` describes the ownership as exclusive, locked or guaranteed. "Only extractor-a writes here" in a brief is advisory unless something blocks the others. [W6]
- A row whose Label is lower than Wanted says why. [W5]

## Rules the checker enforces

`python3 scripts/check_writers.py [--require] FILE.md ...` (path relative to this skill's directory) reads every Writers table outside code fences (several under one heading are each checked; a blank line inside a table is reported). Tables are capped at 50 rows and a Writes cell at 500 characters and 10 paths; above that it reports W10 and skips the table rather than slow down. It prints `file:line: W<n> ...` for each violation and exits 1; `--require` also fails a file that has no Writers table, so use it on the orchestrator.

| id | rule |
|----|------|
| W1 | Label and Wanted are each one of the four labels. |
| W2 | `enforced` or `advisory` writers in one batch have disjoint Writes. |
| W3 | A `serialised` writer is alone in its batch. |
| W4 | `enforced` and `workspace-enforced` writers name their mechanism. |
| W5 | A Label on a lower rung than Wanted says why. |
| W6 | No line that says `advisory` calls ownership exclusive, locked or guaranteed, unless "not" or "never" comes within the six words before that word. |
| W7 | The table has the six columns, at least one row, no blank line inside it, a whole-number Batch and a Role on every row. |
| W8 | With `--require`, the file has a Writers table. |
| W9 | A Role that says per or each item, file or instance, or N instances, has a `<item>` part or a glob in every Writes path. |
| W10 | A table has at most 50 rows, and a Writes cell at most 500 characters and 10 paths. |

Example that passes:

```markdown
## Writers

| Batch | Role | Writes | Label | Wanted | Mechanism or reason |
|-------|------|--------|-------|--------|---------------------|
| 1 | migrator-a | `src/a/**` | workspace-enforced | workspace-enforced | own worktree per writer |
| 1 | migrator-b | `src/a/util.py` | workspace-enforced | workspace-enforced | own worktree per writer |
| 2 | docs-writer | `docs/**` | advisory | advisory | |
```

Example that fails with W2 and W6:

```markdown
## Writers

| Batch | Role | Writes | Label | Wanted | Mechanism or reason |
|-------|------|--------|-------|--------|---------------------|
| 1 | migrator-a | `src/**` | advisory | advisory | exclusive access to src |
| 1 | migrator-b | `src/util.py` | advisory | advisory | |
```

## On each surface

`surfaces.md` section 3c says which labels each surface can truthfully claim. The short version: on chat and Cowork a single context plays each role in turn, so writers are `serialised` by construction and the report says so.

## Limits

- Do not run the checker on this file or any other that only describes the rules: it reports the rule text as W6 lines. Run it on the orchestrator.
- The checker reads the table, not the run. It cannot tell that a worker wrote outside its Writes, and it accepts any text in the mechanism cell. A reviewer opens the named mechanism (the permission rule or hook, the worktree setting) before trusting `enforced` or `workspace-enforced`; a `tools:` line without `Edit`, `Write` and `Bash` shows only that the role cannot write through those tools, and with `Bash` it shows nothing about writes.
- It compares rows, and a row is one worker. W9 reads the Role wording, so a role launched per item that does not say so passes with one shared path, and a Role such as `single-instance merger` or `Instances manager` is not read as per item.
- W6 looks at words on one line. A paraphrase such as "sole owner" passes, and "not" within six words before "exclusive" passes even if the sentence is misleading.
- Path overlap, exactly: paths are compared case-insensitively after Unicode NFC, segment by segment. A glob is matched against a literal segment exactly (`*` does not cross `/`); two globs in the same segment are assumed to overlap; a shorter path overlaps a longer one it is a directory prefix of. `**` anywhere, an empty cell, a leading `/` or `~`, a `..` segment, a `{`, or a space, quote, backtick, `;`, `:`, `#`, `(` or `<br` (so a drive letter too) makes the path unknown, so it overlaps everything. Symlinks, hard links and environment variables are not resolved, and every path is read as relative to one root.
- Only commas split a Writes cell. A part that carries an annotation or a quote (`src/a.py (new)`, `a;b`, `<br>`, a space) is read as unknown, so it overlaps everything: a false W2 against another writer in its batch, never a silent pass. That holds for the characters listed in the Writes rule; other separators (`+`, `&`, `=>`, a fullwidth comma) are not split, so a cell joined with them is read as one path and can pass silently.
- Parsing: a fence indented by any amount is treated as a fence; the heading must be the word Writers, alone or with a colon, bold, a number, `table` or a bracket note (`## Writers:`, `## 3. Writers (batch 1)`), and `## Writers and roles` is not found; sentences may sit between the heading and the table, but the next heading of any level ends the search and is reported as W7 (no table under it); a table inside an HTML comment is still read; a pipe inside a cell shifts the columns and is reported as W1 or W7.
- Which surfaces offer isolation for a given primitive is partly unverified; see `surfaces.md` section 3c.
