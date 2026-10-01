# Workspace layout

All intermediate artefacts live in `_workspace/` at the repo root. Naming is `{phase}_{agent}_{artefact}.md` so a directory listing reads as the run's history.

```
_workspace/
├── 00_input/
│   └── request.md                                  # Daniel's request + spec excerpt (orchestrator)
├── 01_reference-miner_autogpt_portmap.md
├── 01_reference-miner_openhands_portmap.md
├── 01_reference-miner_dify_portmap.md
├── 01_reference-miner_crewai_portmap.md
├── 01_reference-miner_deepseek_harness_portmap.md
├── 01_reference-miner_revfactory_harness_portmap.md
├── 02_strategy-architect_slices.md                 # slice design + ## Authority List
├── 02_adversarial-risk-judge_verdict.md            # overwritten each round; header shows round k/3
├── 03_runtime-builder_slice1.md
├── 03_boundary-qa_slice1.md                        # first line: RESULT: PASS | RESULT: FAIL
├── 03_runtime-builder_slice2.md
├── 03_boundary-qa_slice2.md
├── ...
└── 04_boundary-qa_report.md                        # final: Built / Passed / Gaps / Next step
```

## Rules

- **Never delete a workspace.** New input on an existing workspace → `mv _workspace _workspace_{YYYYMMDD_HHMMSS}` (AEST), e.g. `_workspace_20261001_193000/`.
- **Overwrite in place on re-run** of the same agent; the previous version is recoverable from the archived workspace only if a new-input move happened, so agents must read the prior file before overwriting it.
- **No client data** anywhere under `_workspace/` — synthetic examples only. No secrets, no Mercury records.
- `_workspace*/` should be git-ignored (scratch, not product). If `.gitignore` lacks it, note that in the Phase 4 report rather than editing it silently.
- Code output is not in `_workspace/`: it goes to `src/master_finhub/**` and `tests/**`.

## Status at a glance

| Signal | Meaning |
|---|---|
| six `01_*` files exist | Phase 1 complete |
| verdict totals `REJECTED 0` | Phase 2 complete |
| `03_boundary-qa_slice{N}.md` starts `RESULT: PASS` | slice N done |
| `04_boundary-qa_report.md` exists and is newer than every `03_*` | run complete |
