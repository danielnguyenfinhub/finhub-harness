# Port map — revfactory_harness (slices 8-11 focus)

- Submodule: references/revfactory_harness
- Pinned SHA: cceac68
- Licence: Apache-2.0 (references/revfactory_harness/LICENSE; licence-rules.md row `revfactory_harness`; matches references/LICENSES.md, no drift)
- Mined: 2026-10-02 AEST
- Status: COMPLETE (scope: slices 8-11; every line below was opened this session)

Current repo state, checked in src/master_finhub/. Slices 1-7 are present and not re-proposed. These slice 8-11 targets are 0-line stubs: sandbox/docker_engine.py, sandbox/stream.py, server/app.py, server/sse.py, tools/mcp/__init__.py. evals/ and verifiers/ do not exist yet. factory/*.py is also empty (slice 12, deferred). The only non-empty sandbox file is sandbox/workspace.py (166 lines, slice 3).

Note on the submodule: revfactory_harness is a Claude-Code meta-skill (prose Markdown, Korean). It has no Python, Docker, MCP, or SSE code. Its relevance to slices 8-11 is limited to the evals/verifiers methodology (slice 11) and QA/process conventions. Base paths below: `references/revfactory_harness/skills/harness/references/` is abbreviated as `RH/`, and `references/revfactory_harness/skills/harness/` as `RS/`.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| R1 | 11 | Eval case record: id, descriptive name, prompt, list of objective assertions | references/revfactory_harness/skills/harness/references/skill-writing-guide.md:207 | adapt | dataclass `EvalCase`; ids descriptive, not numeric (see R7) |
| R2 | 11 | Grading result: expectations list with text/passed/evidence plus summary passed/failed/total/pass_rate | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:140 | adapt | Use exact field names; fixes the verifier return shape |
| R3 | 11 | Same grading schema restated, with a warning against field-name variants | references/revfactory_harness/skills/harness/references/skill-writing-guide.md:222 | adapt | Pin names `text`, `passed`, `evidence` in a typed dict or dataclass |
| R4 | 11 | Good assertion = objectively true/false, descriptive, tests core value; bad = subjective or always true | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:118 | adapt | Verifiers must be deterministic code, not LLM judgement |
| R5 | 11 | Programmatically checkable assertions should be scripts, reusable across iterations | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:131 | adapt | Supports `verifiers/` as plain Python callables |
| R6 | 11 | Non-discriminating assertions (pass in both configs) carry no signal; remove or harden | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:135 | adapt | Needs a baseline run; include one pass AND one fail benchmark (slice 11 proof) |
| R7 | 11 | Per-iteration directory layout: eval-<name>/{with_skill,without_skill}/{outputs,timing.json,grading.json}, benchmark.json | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:280 | adapt | Never overwrite earlier iterations; write results to a tmp dir in tests |
| R8 | 11 | Run each prompt twice (with vs baseline); baseline is no-skill or snapshot of old version | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:75 | adapt | Maps to runner with and without a feature or profile; YAGNI-trim to single-config first |
| R9 | 11 | Capture total_tokens and duration_ms at completion time because they cannot be recovered later | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:104 | adapt | Runner records tokens and wall time per case; reuses slice 2 token meter |
| R10 | 11 | Trigger-eval queries: should-trigger vs near-miss should-not-trigger, 20 total | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:235 | reference | Only relevant to the deferred factory (slice 12); skip for slice 11 |
| R11 | 11 | Train 60% / Test 40% split to avoid overfitting when optimising | references/revfactory_harness/skills/harness/references/skill-testing-guide.md:266 | reference | Optional and token-costly; do not build in slice 11 |
| R12 | 3, 8-11 | QA runs incrementally after each module, not once at the end | references/revfactory_harness/skills/harness/references/qa-agent-guide.md:131 | reference | Already the phase-table Part B convention; cite as justification only |
| R13 | 10 | Boundary check: compare response shape against client consumer; watch paginated or 202 shape mismatch | references/revfactory_harness/skills/harness/references/qa-agent-guide.md:44 | reference | Principle for slice 10 test: assert SSE frame shape matches the client parser |
| R14 | 8-11 | Error policy: one retry then proceed and name the gap; partial results on timeout | references/revfactory_harness/skills/harness/references/orchestrator-template.md:211 | reference | Process convention only; matches existing miner Error Handling |
| R15 | meta | Preserve _workspace/ intermediates for audit; move old run to _workspace_<timestamp> on new input | references/revfactory_harness/skills/harness/references/orchestrator-template.md:41 | reference | Already followed by the orchestrator |

## Do not port

| source | reason |
|---|---|
| references/revfactory_harness/skills/harness/SKILL.md (Phases 0-7) | Claude-Code TeamCreate/agent orchestration prose, not runtime code; slice 12 factory is deferred |
| references/revfactory_harness/_workspace/** and docs/, index.html, privacy.html, README_*.md | Launch and marketing artefacts, no relevant pattern |
| (not a licence block) Korean-language text | If any wording is reused, translate it and keep Apache-2.0 notices per licence-rules.md |

## Gaps

- Docker sandbox and output stream (slice 8): absent. The repo has no container, subprocess, or stream code. Searched for docker, subprocess, stdout, stream across skills/ and docs/. Slice 8 sources must come from openhands/docker (MIT) and deepseek_harness, per the SKILL.md table.
- MCP client (slice 9): absent. The repo has no stdio/JSON-RPC code. Use dify mcp_client.py as a pattern only, and the stub stdio server proof from the phase table.
- Server/SSE (slice 10): absent. Only the QA boundary principle (R13) applies. Use dify streaming_utils.py as a pattern only.
- Eval runner and verifiers (slice 11): no code, only methodology (R1-R9). The runnable benchmark shape must come from autogpt/classic/direct_benchmark (MIT only, never autogpt_platform).
- With-skill vs baseline comparison (R8) needs an LLM-driven agent run. For slice 11 use the existing fake_llm.py, so runs are deterministic and offline.
- Suggested minimal slice-11 shape for the architect, from R1-R6: stdlib dataclasses `EvalCase` and `Grading` with R3's field names, verifier callables returning `(passed, evidence)`, and a runner that emits a `pass_rate` summary. No new dependency is needed.
- Pin-drift check: references/LICENSES.md and licence-rules.md agree for this submodule.
