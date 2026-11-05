# Capability shortlist — 2026-11-05

Source: the fourteen port maps in `references/portmaps/` (all present, none `EMPTY`), `.claude/skills/capability-triage/` (SKILL.md and scoring rubric), the `CLAUDE.md` change history and spot greps of the tree. Scores rank; they do not decide. Daniel picks.

Candidate ids are the primary port-map row id, not a new `C` number: the crewai map uses `C1`-`C33`, which collides with the adoption ids `C25`-`C28` and `C33` in `CLAUDE.md`.

Score = 0.35 value + 0.20 licence + 0.20 effort (inverse) + 0.15 risk (inverse) + 0.10 novelty, per `scoring-rubric.md`. Tags: `[v]` verified (map row or repo file opened), `[a]` assumed.

Excluded by gate: Polyform Shield sources (`autogpt_platform/**`) are excluded. No dify row made the list (all dify rows are pattern-only; Y2-Y5, Y15, Y22 were weaker than the rows below).

## Shortlist

| rank | id | pattern (<=20 words) | target | licence / port as | evidence (rows; corroboration) | test that would prove it | size | score (V/L/E/R/N) |
|---|---|---|---|---|---|---|---|---|
| 1 | RH28 | A generated skill that sends, publishes or pays is explicit-only: lint requires `disable-model-invocation: true` | script (`lint_harness.py`) | MIT / adapt | RH28 `[v]`; ties to adopted C28 ask-first; spirit in PC34, OR9 (3 repos) | Lint WARN `send-implicit` on a fixture skill carrying the Ask-first block without the key; clean with the key; both repo lint runs unchanged; one mutant per branch | S | 0.94 (1/1/1/0.6/1) |
| 2 | C11 | Reviewer verdict fails closed: unparseable or errored reply is not a pass; a retry always carries feedback | plugin skill (`team-patterns.md`, `team-examples.md`) | MIT / adapt | C11, C9, C10 `[v]`; HV19, HV20 corroborate; HV21 is the fail-open counter-example; OH29 (3 repos) | Cold run of a generated harness whose stub reviewer returns garbage: orchestrator does not advance; pytest pins the wording | S | 0.92 (1/1/1/1/0.2) |
| 3 | O8 | QA evidence honesty: mocked run is not live evidence; pin absence of the false claim; state checked scope | plugin skill (`qa-agent-guide.md`) | MIT / adapt (O8, D26); OR14 Apache adapt; OR15, PC8 pattern | O8, O10 `[v]`; D26, D27; OR14, OR15; PC8, PC9 (4 repos) | Seeded fixture: builder report claims a live run backed only by a mock, and a test that asserts only the true claim; a cold QA run must FAIL both; pytest pins phrases | S | 0.89 (1/1/1/0.6/0.5) |
| 4 | RH20 | Audit classifies each rule: enforced, partial, unenforced, check without authority, unknown; plus evidence class | plugin skill (`finhub-harness` audit path, `quality-gates.md`) | MIT / adapt | RH20, RH13, RH22, RH24 `[v]`; O3 (gate is source of truth); D30 (2 more repos) | Cold audit of a fixture harness with one prose-only rule and one orphan gate: report names both with the right class; pytest pins the five class words | M | 0.87 (1/1/0.6/1/0.5) |
| 5 | O16 | Tools carry read-only and destructive hints; a new write tool after MCP catalog refresh is quarantined | runtime module (`tools/mcp/client.py`, `tools/safety.py`) | MIT / adapt (O16, CW04); PC33, PC34 idea-only | O16, CW04, CW05 `[v]`; PC33, PC34 (3 repos) | Fake MCP server whose second listing adds `delete_record`: call refused with a named reason until enabled; existing tools still callable; mutants on the diff | M | 0.86 (1/1/0.6/0.6/1) |
| 6 | D5 | Tool deadline wrapper reports TOOL_TIMEOUT only when its own timer fired, never a nested one | runtime module (`runtime/loop.py`) | MIT / adapt | D5 `[v]`; Y11 (pattern), A8 (3 repos) | Inner tool raising its own `TimeoutError` is not reported as TOOL_TIMEOUT; a tool past its declared deadline is; loop continues | S | 0.81 (0.6/1/1/1/0.5) |
| 7 | C16 | Tool reports failure as typed object (reason, code, retryable); policy ignore, warn or raise | runtime module (`tools/`) | MIT / adapt | C16 `[v]`; Y14, D15 closed outcomes (3 repos); MCP isError already mapped `[v]` | A tool answering "HTTP 200, ok false" is logged as a failure, not success; policy `raise` stops the run | S | 0.81 (0.6/1/1/1/0.5) |
| 8 | HV1 | Stall detector: reply similarity across recent turns plus a silence clock; pure functions, `now` passed in | runtime module (`runtime/`, `orchestration/modes/team.py`) | Apache / adapt (HV1); PC30 idea-only | HV1 `[v]`; PC30, A9, Y15, OR23 (5 repos); `repeat_reminder.py` covers exact repeats only | Rephrased replies above threshold flag `stalled`; one dissimilar pair does not; silence levels at fixed `now` values | S | 0.78 (0.6/0.6/1/1/1) |
| 9 | D6 | On a context-window error, compact once and retry, bounded by a per-policy count | runtime module (`runtime/context.py`, `loop.py`) | MIT / adapt | D6 `[v]`; Y1, HV5 (3 repos); `anthropic_llm.py:224` maps the stop `[v]`, retry path `[a]` absent | Fake LLM overflows once then succeeds: one compaction, one retry; overflows twice: `ContextOverflowError` | S | 0.75 (0.6/1/1/0.6/0.5) |
| 10 | D1 | Oversized tool result saved whole to a spill file; context gets preview plus locator; failure keeps inline | runtime module (`runtime/context.py`) | MIT / adapt | D1, D2, D3 `[v]`; HV3, HV4, OH36, Y10 (4 repos) | Inline replacement never exceeds the cap including its notice (D2); storage failure keeps inline (D3); restart resumes spill numbering (HV4) | M | 0.72 (0.6/1/0.6/0.6/1) |
| 11 | CW01 | Named session permission modes, read-only shell allowlist, protected files, subagent inherits mode (CW1) | runtime module (`tools/safety.py`, `orchestration/modes/subagent.py`) | MIT / adapt | CW01-CW08 `[v]`; D12, D13, D18; A14, A15, A17; OH32; OR28; PC37 (7 repos, most corroborated) | Mode x tool-class matrix; read-only refuses unknown command and file redirect; child cannot widen parent; protected file refused through a symlink; mutants on precedence | L | 0.72 (1/1/0.2/0.2/1) |
| 12 | MH1 | Experiment profile: name mutable and read-only eval surfaces, baseline, keep/discard rule before first candidate | plugin skill (new reference, `skill-testing-guide.md`) | Apache / adapt | MH1-MH10 `[v]`; R9 (sample size on claims) (2 repos) | Cold build of an "optimise prompt X" harness names all seven contract items before its first candidate; topology A/B keeps fixture, model, budget fixed; pytest pins phrases | M | 0.70 (0.6/0.6/0.6/1/1) |

Ties: rank 10 and 11 tie at 0.72; lower effort first (rubric tie-break). CW01 is the best-corroborated idea in the corpus but scores low on effort and risk (new security surface needs its own design round); upstream default is full-access (`CW` map Gaps), so ours must choose the default deliberately.

### Deferred (scored, ranked 13th or lower)

| id | pattern | score |
|---|---|---|
| OR11 | Two blind reviewers answer each other AGREE / DISAGREE / PARTIAL (also A20, HH22); heavy, against the 2026-10-28 "too heavy" direction | 0.70 |
| RH29 | Pointer block skip-if-current, and recognise an old marker name on rename (OR29); closes a named C33 gap | 0.67 |
| PC1 | Evolve edits a skill only after a confirmation that showed the diff, one target per consent (PC2, PC3; idea-only) | 0.67 |
| HV14 | Atomic claim for the unit tracker (H4; PC21-PC25, HV15, HV16, O20) | 0.64 |
| RH1 | Safe updater: stored baseline, three-way merge, staged conflicts (RH1-RH12; MH21-MH25) | 0.64 |
| HV10 | Convergence loop with dead-letter rows (H3; HV11, HV12, PC27, OR26, A6) | 0.59 |

## Top 5 cite spot-check

`python3 skills/finhub-harness/scripts/cite_check.py references/portmaps/<map>.md`, run 2026-11-05 on every map a top-5 row cites:

| map | result |
|---|---|
| repository_harness-485fd40 | exit 0, checked 42, bad 0 |
| crewai-fbcf2de | exit 0, checked 46, bad 0 |
| hive-67502fa | exit 0, checked 30, bad 0 |
| openhands-a8c0558 | exit 0, checked 43, bad 0 |
| deepseek_harness-b274e89 | exit 0, checked 32, bad 0 |
| openrig-475ccab | exit 0, checked 37, bad 0 |
| paperclip-2a5a323 | exit 0, checked 49, bad 0 |
| cowagent-987a61c | exit 0, checked 29, bad 0 |

cite_check verifies that a line exists at the pin, not that it still says what the row claims (C27 D-HASH).

## Duplicates and overlaps

- **meta_harness MH21-MH25 vs repository_harness RH1-RH12 (safe updater).** Same job. RH has the stored baseline (RH5) and true three-way merge (RH1, RH2); MH has only keep/update/conflict plus a sha256 managed-copy marker (MH22). Use RH as primary and MH22 as the "already current" check; do not design both. (The MH map's Gaps say the same.)
- **deepseek D26 vs `qa-agent-guide.md`.** Checked by grep: partial overlap. Already present: a probe before PASS (`qa-agent-guide.md:246`), `cmp` that the repo is untouched in mutant legs (`quality-gates.md:218`, `:241`) and the drift row's `undeclared=-` (OR-D4), which covers "untouched files unchanged" for a git tree. Absent: "re-read the file the builder says it wrote" as a general rule, and the O8/OR14 evidence rules. Hence row 3 has novelty 0.5 and leads with O8, not D26.
- **Permission modes:** CW01-CW08, D12-D18, A14-A17, OH32, OR28 (data only), PC37 are one candidate (CW1). A16 and OH33 (path resolution) are already in `tools/safety.py` and `sandbox/workspace.py`.
- **Spill and microcompact:** D1-D3, HV3, HV4, OH36, Y10 are one candidate; HV2, OH37, Y1 (microcompact) depend on it and are not listed separately.
- **Retry (H3):** HV10-HV12, PC27, OR26, A6, Y28, D9. **Claim (H4):** HV14-HV16, PC21-PC25, O20. Both were already open from the hive proposal.
- **Argument coercion:** HV6 and C17 overlap; the C17 note says pick one layer. Not listed.
- **Fail-open vs fail-closed judge:** HV21 (defaults to ACCEPT) conflicts with C11 (error is a failure). Row 2 takes C11.
- **Pointer block:** OR29 and RH29 refine adopted C33; HH18 and R21 are covered.
- **Lint rules:** C28 (crewai), HV27, MH lint rows, HH14 mostly covered by `lint_harness.py`; compare rule lists only.
- **Already adopted, still listed as findings:** the openharness map dates from 2026-10-02 and lists OH23-OH27 and OH31, adopted since. OR17 overlaps `candidate_id.py`; RH16 overlaps OR-D1; RH15 overlaps the Full-lane carry rule C4 (its "not recomputed" line is the only new part).
- **revfactory R10-R23:** covered locally; the pin is older than the port source (see licence questions).

## Fresh-numbering note

The fourteen maps were re-mined on 2026-11-05 with fresh row ids. Older ids quoted in `CLAUDE.md` refer to lost maps and do not match:

- repository_harness: the C25 row cites RH11, RH15, RH16 as rejected ideas (six-way gap taxonomy, record file per experiment, no diagnosis from one run), and the C27 row cites RH26 and RH29 as bad cites it found. In the new map RH11 is the forward-only version guard, RH15 narrow audit modes, RH16 the independence contract, RH26 the entry-doc word cap and RH29 the idempotent re-run. The map's own Gaps line says so.
- cowagent: candidate names CW1, CW2, CW3 in `CLAUDE.md` map to rows CW01-CW08, the adopted prompts.py rows, and CW10-CW11.
- hive: candidates H1-H4 are proposal ids; rows are HV1-HV30. HV1 (stall detector) is not H1 (unit tracker).
- crewai `C25`-`C28`, `C33` are port-map rows (regression gate, evaluator prompt, flow definition, skill-name rule, LLM routing), not the adoptions of the same name.

Rule: cross-refer by `path:line`, never by old row id. This shortlist uses only the 2026-11-05 ids.

## Open licence questions

1. **paperclip holder.** `references/paperclip/LICENSE:3` says Paperclip AI; `README.md:582` says Paperclip Labs, Inc. Unresolved; every PC row stays idea-only, attribution uses LICENSE:3. Affects rows 5, 8 (corroboration only) and deferred PC1, HV14.
2. **paperclip third-party code.** `.agents/skills/create-verification-skill/` comes from a pstack fork (NOTICE.md:1); its licence was not opened. PC10, PC11 idea-only.
3. **openrig vendored skills.** `verification-before-completion` and other process skills are vendored from Obra Superpowers and Vercel; upstream licences differ. OR15 (row 3) is idea-only, fresh text.
4. **openharness upstream unverified.** Pinned fork; MIT confirmed at `LICENSE` only.
5. **harness_100 upstream unverified.** Fork pin, holder "Robin"; cite `ko/` only.
6. **meta_harness LICENSE has no holder line** and no NOTICE. Row 12 needs a decision on what the attribution line names.
7. **openhands repo identity.** The licence row names OpenHands/agent-canvas; `AGENTS.md:26-30` names OpenHands/OpenHands. No MIT impact; fix the row text.
8. **revfactory version.** The pin is v1.2.0 (`plugin.json:4`) on a fork, while `skills/finhub-harness/SKILL.md:8` says the port came from v2.1.0. v2 material has no pinned source; re-pin before citing v2 text.
9. **autogpt root skills.** `.claude/skills/orchestrate` and `pr-polish` sit outside `autogpt_platform/` (MIT by the root LICENSE) but serve the platform workflow; A21-A24 kept pattern-only. Confirm.
10. **dify modified Apache-2.0.** Pattern-only stands; nothing from dify is on the list.

## Gaps (no map offers it)

- A real tokenizer (all token meters are chars/4; D map Gaps).
- A judge panel with a tie-break rule (only the OR11 pair and A20 debate).
- A stale-claim reclaimer in code (HV map Gaps; PC23 is a transaction idea only).
- Harness search or optimisation code (MH map Gaps; MH1-MH10 are prose).
- OpenHands agent runtime (the pin is the UI frontend; O map Status).
