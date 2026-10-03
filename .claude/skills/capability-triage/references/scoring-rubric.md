# Scoring rubric for capability triage

Total = Σ weight × score, each score in [0, 1], reported to two decimals with the per-criterion score and a one-line reason beside it. Licence is a gate first (see below) and a score second.

| Criterion | Weight | 1.0 | 0.6 | 0.2 | 0 |
|---|---|---|---|---|---|
| Value to harness users | 0.35 | changes what a third party relying on a generated harness receives: safer tool guard, honest QA verdicts, auditable decisions, fewer silent failures | makes the factory or runtime noticeably more capable for Daniel but invisible to third parties | convenience or polish | no observable change |
| Licence cleanliness | 0.20 | MIT, `adapt` | Apache-2.0, `adapt` with notices kept | pattern-only (dify): idea rewritten fresh, no mirrored names | `reference` only (no licence row confirmed) |
| Effort (inverse) | 0.20 | S: one slice, ≤150 lines of code or one skill section, no new dependency | M: two to three slices or a new reference file plus edits in two agents | L: new subsystem, new dependency, or touches more than three agents | unbounded |
| Risk (inverse) | 0.15 | no new attack surface, cannot stall the runtime, no false positives that block legitimate work | bounded new surface with a named mitigation and test | new security surface or runtime cost that needs its own design round | risk unassessed |
| Novelty vs existing | 0.10 | absent from the tree | partial: a weaker form exists (name the file) | mostly present; adoption would be a refinement | duplicate → move to **Already have**, do not score |

## Gates (applied before scoring)

1. Source under `references/autogpt/autogpt_platform/**` → never listed, not even under Rejected by name; one line "Polyform Shield sources excluded" suffices.
2. dify rows → pattern-only; the proof test must not reference dify identifiers.
3. Submodule with no row in `references/LICENSES.md` → tier `reference`; scores licence 0 and is flagged for Daniel.
4. No proof test the judge could later audit → **Rejected: no proof**.

## Evidence tags

- `[verified]`: the scorer opened the port-map row or the repo file the score rests on.
- `[assumed]`: inferred from the map's description without opening further; say what was assumed.
- `[missing]`: the fact needed is not in any map; the criterion takes the lower bound of the band it would otherwise fall in.

## Tie-breaks

Equal totals: lower effort first, then cleaner licence, then the candidate whose proof is a single command.
