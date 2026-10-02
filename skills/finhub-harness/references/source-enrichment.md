# Enriching a harness from other harness repos

A new harness gets better when it borrows proven patterns instead of inventing them. Borrowing has two risks: copying something the licence forbids, and citing a pattern that is not actually in the source. This file is the procedure that avoids both. It restates the reference-mining skill (`.claude/skills/reference-mining/SKILL.md`) and its `references/licence-rules.md` and `references/port-map-schema.md`. If this file and `licence-rules.md` ever disagree, `licence-rules.md` wins, and `references/LICENSES.md` at the repo root wins over both.

## 1. The six pinned references

Pinned as read-only submodules under `references/` (see `.gitmodules`; every upstream is a fork under `github.com/danielnguyenfinhub`). Tiers below are taken from `licence-rules.md`.

| submodule | upstream | licence | constraint (verbatim) | allowed `port as` |
|---|---|---|---|---|
| `autogpt` | Significant-Gravitas/AutoGPT | `classic/` MIT; `autogpt_platform/` Polyform Shield 1.0 | **Never copy from `autogpt_platform/`.** Only `classic/` (direct_benchmark, forge) may be ported. | `classic/**`: adapt · `autogpt_platform/**`: none — list under Do not port |
| `openhands` | OpenHands/agent-canvas | MIT | UI-only fork; no agent runtime present. | adapt |
| `dify` | langgenius/dify | Apache-2.0 **modified** | No multi-tenant SaaS without written authorisation; logo/copyright must stay. Port patterns (SSE, MCP client shape), not files. DAG engine is the external `graphon` package, not in-repo. | pattern only |
| `crewai` | crewAIInc/crewAI | MIT | — | adapt |
| `deepseek_harness` | deepseek-ai/deepseek-harness | MIT | — | adapt |
| `revfactory_harness` | revfactory/harness | Apache-2.0 | Meta-skill source; installed copy lives at `~/.claude/skills/harness`. | adapt / reference |
| `openharness` | OpenHarness (upstream org unverified; pinned fork at danielnguyenfinhub/OpenHarness) | MIT (`LICENSE`, "Copyright (c) 2025 OpenHarness Contributors") | Pinned 2026-10-02 at 9b2efd7. Port map: `references/portmaps/openharness-9b2efd7.md` (40 rows; strongest: verification-specialist prompt rules OH23-OH27, sensitive-path denylist OH31, compaction state-ledger OH37-OH40). | adapt |

### The two hard cases

`licence-rules.md`, "Hard stops":

> 1. Any path under `references/autogpt/autogpt_platform/` → Do not port, regardless of how useful.
> 2. Any dify file → never `adapt`, never verbatim.
> 3. A submodule with no licence file at its root → report in Gaps and treat as `reference` until Daniel confirms.

- **dify is Modified Apache-2.0: pattern only.** Write the idea fresh. The resulting code must not mirror the source's structure, names or comments (no mirrored names).
- **autogpt_platform is Polyform Shield 1.0: never a source.** Only `autogpt/classic/` (MIT) may be used.

What each `port as` value means (from `licence-rules.md`):

| value | meaning |
|---|---|
| adapt | Rewrite the idea in the target language. For MIT, a one-line source comment such as `# adapted from references/<submodule>/<path>:<line> (MIT)` is enough. Apache-2.0 adaptations keep the same comment and must not remove upstream notices if any text is reused. |
| pattern | The design idea only (for example "send a PING every N seconds while idle"). Written fresh, no structural copy. Always the case for dify. |
| reference | Read to understand; nothing ported. |

## 2. The port-map procedure

Use this to borrow patterns from any harness repo, pinned or new.

1. **One miner per submodule.** Each miner reads exactly one `references/<submodule>/`. Run them in parallel when the surface supports it (see `surfaces.md`); sequentially otherwise.
2. **Read-only.** The miner cannot write. It returns the port map as its final message and the orchestrator saves it, for example to `_workspace/01_reference-miner_{submodule}_portmap.md`.
3. **Check the submodule exists.** If `references/<submodule>/` is empty or only `.gitkeep`, return an empty Findings table and a Gaps line naming the path. Never fill the table from memory of the upstream project.
4. **Licence first.** Read the constraint row for this submodule before opening code. It decides what the "port as" column may say.
5. **Locate, open, record.** Search for candidate patterns, open the exact region, and record one row per pattern unit (a function or class, not a file).
6. **Cite `file:line`.** Format `references/<submodule>/<path>:<line>`, forward slashes, line = first line of the unit, opened in this session. A wrong line number becomes a rejected claim at audit time.
7. **Describe in your own words.** Pattern column at most 20 words; notes at most 15; no code blocks longer than 5 lines.
8. **Fill the "Do not port" table.** Anything licence-blocked or out of scope, with a reason.
9. **Fill the Gaps section.** A pattern the repo does not contain is a valid finding. Record what you searched for.
10. **On re-run,** pass the prior map, re-verify only the flagged rows, and return the whole map with only those parts changed.

Port-map shape (full schema in `port-map-schema.md`):

| part | content |
|---|---|
| Header | submodule, pinned SHA, licence, mined time, status (COMPLETE, PARTIAL, EMPTY) |
| Findings | table: id, slice, pattern, source, port as, notes. Ids use the submodule initial and a number |
| Do not port | table: source, reason |
| Gaps | bullet list of absent patterns and what was searched |

## 3. The Authority List gate

A borrowed pattern enters a generated harness only through an Authority List row (see `quality-gates.md`). The path is:

port-map row (with `file:line` and licence verdict) leads to an Authority List row that cites it, and the adversarial judge re-opens that line before the row is accepted.

Consequences:

- No Authority List row, no borrowed pattern. A pattern mentioned in a design note but absent from the list is not authorised.
- A row citing a `pattern`-only source (dify) must not describe or name things after the source.
- A row citing `autogpt_platform/**` is rejected outright.
- A row whose line the judge cannot reproduce is rejected; send the miner back to re-verify that row only.

## 4. Adding a new reference repo

Do these in order; mining comes last.

1. **Add the licence row first.** Add the repo to `references/LICENSES.md` (the source of truth) and mirror it in `licence-rules.md`: upstream, licence, constraint, allowed `port as`. If the repo has no licence file, the row says `reference` until Daniel confirms (Hard stop 3).
2. **Add the submodule.**

   ```
   git submodule add --depth 1 <fork-url> references/<name>
   ```

   Existing entries are shallow forks under `github.com/danielnguyenfinhub`. Follow that convention and record it in `.gitmodules`.
3. **Pin it.** Commit the submodule so the pinned SHA is recorded. Put that SHA in the port-map header.
4. **Register the id letter.** Pick a unique initial for the Findings `id` column (existing: A, O, Y, C, D, R). Add the repo to the reference-mining skill description and target-patterns table.
5. **Then mine.** Spawn one miner for the new submodule.

## 5. What to borrow from where

Starting points only. The reference-mining skill states that its paths are not facts until the miner has verified each one exists.

| need | source | tier | note |
|---|---|---|---|
| Harness, skill and agent conventions; workflow and judge-panel patterns | `revfactory_harness` | Apache-2.0, adapt / reference | meta-skill source |
| Verifier, benchmark and eval-runner patterns | `autogpt/classic/` (for example `direct_benchmark/`) | MIT, adapt | `classic/` only, never `autogpt_platform/` |
| Sandbox policy, path containment, MCP and agent-loop patterns | `deepseek_harness` | MIT, adapt | |
| Delegation and ask-question tools, task context passing | `crewai` | MIT, adapt | |
| SSE streaming shape, MCP client shape | `dify` | Modified Apache-2.0, pattern only | no mirrored names; DAG engine is not in the repo |
| Container ingress and entrypoint | `openhands` | MIT, adapt | UI-only fork; confirm what exists |

## 6. Worked example: borrowing a verifier pattern

1. The architect needs an eval-runner shape for a new harness. The reference-mining table points at `autogpt/classic/direct_benchmark/` (MIT only).
2. The miner opens the submodule, confirms the directory exists, and records one row per runner/evaluator class with `file:line` and `port as: adapt`. Anything it saw under `autogpt_platform/` goes to Do not port.
3. The architect writes an Authority List row citing that port-map row and states what is adapted and what is net-new.
4. The judge re-opens the cited line. If the line moved or the unit differs, the row is REJECTED and the miner re-verifies only that row.
5. The builder adds the one-line `# adapted from references/...:<line> (MIT)` comment in the generated artefact.

## 7. Quick rules

- Open the line before you cite it.
- Read the licence row before you read the code.
- dify: idea only, written fresh.
- autogpt_platform: never a source.
- No Authority List row, no borrowed pattern.

## 8. When a reference has nothing to give

- Record the absence under Gaps with the search terms used (for example, openhands has no agent runtime, per `licence-rules.md`).
- Do not substitute a pattern from memory of the upstream project. If the harness still needs it, mark it net-new in the Authority List and let the judge test it as an original claim.
- Re-mine only when the pinned SHA changes or the architect flags a row.
