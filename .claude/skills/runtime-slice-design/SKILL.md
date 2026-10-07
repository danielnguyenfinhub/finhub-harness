---
name: runtime-slice-design
description: "Designs buildable slices of the Master FinHub Python runtime (agent loop, context compaction, safety/sandbox, router, DAG engine, message bus, docker sandbox, MCP client, SSE server, evals) or the adoption of one backlog capability into the finhub-harness plugin, agents or runtime, from the reference port maps; each design has files, typed interfaces or insertion anchors, a proof, a test plan with mutation targets, and an Authority List mapping every claim to references/<submodule>/<path>:<line>. Use for: design the slices, slice plan, redesign slice N, design the adoption of C3, revise rejected claims, update the design after I changed the spec. Also read by runtime-builder before building. Not for general Python architecture outside this repo or for designing MCP servers (Mercury, Twilio or any other)."
---

# Runtime Slice Design

Turn the nine port maps into an ordered set of small, independently provable slices, or one backlog row into one provable adoption. Each slice must be buildable in one builder call and verifiable by four commands; anything bigger hides failures.

## Steps

1. **Read every port map** (`_workspace/01_reference-miner_*_portmap.md`). Note which have `Status: PARTIAL` or empty Findings — claims depending on them must be marked, not invented.
2. **Follow the slice order** in `.claude/skills/master-finhub-orchestrator/references/phase-table.md` (Part B). Do not reorder: later slices assume earlier interfaces (the router in 4 plugs into the loop from 1; the DAG in 6 runs the checkpoint from 5).
3. **Write each slice** using `references/slice-template.md`: files, interfaces with Python type signatures, proof test, deps, ported-vs-net-new, quant guardrails if relevant.
4. **Write the Authority List** at the end per `references/authority-list.md`. Every design claim that relies on how a reference does something gets a row; net-new decisions get a `NET-NEW` row with a reason.
5. **Signal the judge** ("design ready") and wait. On a verdict with REJECTED > 0, fix only those claims and the slice text they support.

## Design rules and why

- **Python 3.12, stdlib first.** Every dependency is a supply-chain and licence question; slices 1–3, 5–7 and 11 need none. `graphlib.TopologicalSorter` over `graphon` for the DAG — dify pins an external package we would then have to audit.
- **Protocols at seams.** The LLM is a `typing.Protocol` with a `FakeLLM` for tests, so no slice before 4 needs network or keys. Tools declare a schema the loop validates against — boundary-qa compares these shapes directly.
- **Proof = one command or one test.** If you cannot state the proof in one line, the slice is too big; split it.
- **Mypy-strict friendly.** Declare return types, avoid `Any` at public boundaries, use `dataclass(frozen=True)` for messages and checkpoints (immutable data is easier to checkpoint and resume).
- **Safety slices are policy-driven and small.** Slice 3 and 8 are net-new where references lack them; keep each ≤80 lines and explain the denylist in the Authority List as `NET-NEW (spec requirement)`.
- **Quant correctness is designed in.** Any slice touching evals, verifiers, backtests or pricing states how it handles each guardrail in `.claude/skills/adversarial-audit/references/quant-guardrails.md`. The judge will check those rows regardless.
- **Licences.** Never cite `references/autogpt/autogpt_platform/`; dify claims are `pattern` only. Citations outside `references/` are invalid.
- **Synthetic data only.** Example payloads in the design use placeholder names (`client_a`, `acct_001`), never real people, accounts or Mercury records.

## Output

`_workspace/02_strategy-architect_slices.md`:

```markdown
# Master FinHub runtime — slice design (revision 1)

## Slice 1 — loop + echo tool + CLI
...(slice-template sections)...

## Slice 2 — context compaction
...

## Authority List
| id | claim | evidence | slice |
|---|---|---|---|
| A1 | ... | references/...:42 | 1 |
```

## Adoption design (one backlog item)

When the prompt names a backlog row (`C3`) instead of a slice range, write `_workspace/02_strategy-architect_<item-id>.md` with these sections, in this order: `## Source` (the backlog row and its port-map rows, re-opened), `## Target` (plugin skill / agent / runtime module / docs, and the exact files), `## Design` (for code: files and typed interfaces; for prose: each insertion as anchor line quoted verbatim + the text to insert + the one-line attribution `adapted from references/<repo>/<path>:<line> (<licence>)`), `## Proof` (the commands or greps that show every insertion or interface landed, with expected counts), `## Test plan` (unit cases, must-still-pass list, and at least three mutation targets QA can apply on a scratch copy), `## Does not cover` (honest limits and known false positives), then `## Authority List`. Keep existing tests unmodified; a design that needs an existing test changed says why in `## Design`. A prose adoption never pastes source prose: an 8-word run identical to the source is a defect.

## On revision

Read the latest verdict for your design (`02_adversarial-risk-judge_verdict.md` for runtime slices; `02_adversarial-risk-judge_<item-id>_r<k>.md` with the highest `k` for an adoption). Change only REJECTED/UNVERIFIED claims; keep UPHELD rows byte-identical so the judge can carry them forward. Bump the revision number in the title and list changed claim ids at the top under `## Changes in revision N`. If you believe a rejection is wrong, reply to the judge with the exact line as new evidence rather than resubmitting the same claim.

## For the builder

runtime-builder reads this skill to understand the slice template, then implements only UPHELD claims for its slice. Interfaces declared here are the contract boundary-qa checks against — if the builder must deviate, it records why in its report.
