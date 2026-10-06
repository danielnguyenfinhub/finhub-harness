# Capability backlog — 2026-10-03, from 7 port maps

Scope: both (request `_workspace/00_input/request.md`). Maps read: autogpt (A1-A39), crewai (C1-C52), deepseek_harness (D1-D57), dify (Y1-Y37), openhands (O1-O36), openharness (OH1-OH84), revfactory_harness (R1-R18). All seven are `Status: COMPLETE`; none missing.

Licence tiers used (from `references/LICENSES.md` and `licence-rules.md`, both opened [verified]):
- MIT `adapt`: crewai, deepseek_harness, openhands, autogpt `classic/` only.
- MIT `adapt`, upstream org unverified: openharness. Its `LICENSE` is present ("Copyright (c) 2025 OpenHarness Contributors"), so this backlog treats it as MIT adapt. **Flag for Daniel:** this rests on the pinned fork's LICENSE file, not on a confirmed upstream.
- Apache-2.0 `adapt` with notices: revfactory_harness.
- Pattern only: dify. No dify identifiers appear in any proof below.
- Polyform Shield sources excluded.

Inventory was opened, not taken from the miners' notes. Opened: `skills/finhub-harness/SKILL.md` and the headings of all 12 references; `skills/finhub-harness-evolve/SKILL.md`; `.claude/agents/*.md` (6) and `.claude/skills/*` (6); `scripts/package-plugin.sh`; module list and docstrings of `runtime/loop.py`, `runtime/context.py`, `tools/safety.py`, `sandbox/stream.py`, `sandbox/docker_engine.py`, `sandbox/workspace.py`, `tools/mcp/client.py`, `evals/runner.py` and `evals/verifiers.py`.

One correction to the miners: **`src/master_finhub/factory/{evolver,skill_compiler,team_generator}.py` are zero-byte files** [verified, `wc -l` = 0]. A32, A37 and C45 told the scout to diff against `skill_compiler.py` and `evolver.py`, but there is no code there to diff against. See Gaps.

## Already have

| capability | where it lives | source rows that match |
|---|---|---|
| Throwaway Docker container with no network, a read-only root and a PID cap; a Docker availability probe | `src/master_finhub/sandbox/docker_engine.py:96-98` (`--network none`, `--read-only`, `--pids-limit`), `:54` `docker_available` [verified] | D7, OH34, A1, A3, A4, A5. OH35 is only partly covered: there is a probe but no named refuse-if-unavailable error [verified]. |
| Child env scrubbed by secret-looking *names* | `sandbox/stream.py:22` `SENSITIVE_ENV`, `:30` `scrubbed_env` [verified] | D1, C10, C11 |
| Output tail buffer, thread+queue+sentinel stream, process-group kill | `sandbox/stream.py` docstring [verified] | D2, D3, D5, D6, C17, C19, A6, A8, OH83 (idea) |
| Stdio MCP client: id routing, deadlines, fail-all-waiters on EOF, public names, `isError` mapping | `tools/mcp/client.py` docstring [verified] | D9-D19, C1-C8, C14, Y8-Y14 |
| MCP error and stderr text redacted by known config *values* | `tools/mcp/client.py:107` `redact`, used at :141, :177, :302, :358 [verified] | O11 |
| SSE with PING and idle handling | `server/sse.py`, `server/app.py` (slice 10) [assumed from CLAUDE.md and the module list] | Y1-Y7, D20, D21, C18 |
| Benchmark runner (isolated workspace, never raises, stable id, cutoff) and deterministic string verifier with the grading schema | `evals/runner.py` docstring, `evals/verifiers.py:20-31` [verified] | A9-A18, A15, C20-C23, C25, R1-R5, R9 |
| Compaction: head/marker/tail clip, tool-pair-balanced cut, tail-anchored range, threshold/retain ratios, `<compacted-summary>` frame, model-free summariser | `runtime/context.py:63, :83, :98, :121, :169`, tags at `:43-44` [verified] | D25, D27, D28, D30, D31, OH38, A28. OH37 and OH56 are mostly present (see Rejected). |
| Sensitive-path denylist checked before any allow | `tools/sensitive_paths.py`, wired in `tools/safety.py` [verified] | OH31, A29, A30 |
| Command tripwire, deny before allow, fails closed | `tools/safety.py:1-13`, `make_guard` `:650` [verified] | A7, OH32 (eval order; plan mode not present) |
| Single pre-tool guard seam (one callable that returns a denial string) | `runtime/loop.py:112` `ToolGuard`, `:192` [verified] | Weaker form of OH41-OH45, D44, C50. See C12. |
| Checkpoint and resume, with a fail-closed checkpoint hook | `runtime/loop.py:97-98` `CheckpointHook`, `orchestration/_fsio.py` [verified] | A21, D35 (partial), Y25 |
| Delegation depth cap that a nested config can only lower | `orchestration/modes/subagent.py:94-95` [verified] | D55, Y19, Y20 |
| Workspace fence: lexical reject, then resolve, then containment | `sandbox/workspace.py:1-10` [verified] | O26, O27, A34, OH33. OH66's symlink check on the deepest existing parent is not compared here [assumed covered by the resolve step]. |
| QA verifier stance: command and output per check, probe before PASS, rationalisation list, before-FAIL guard, standing reminder | `skills/finhub-harness/references/qa-agent-guide.md` §7, `.claude/agents/boundary-qa.md` [verified headings] | OH23-OH27 |
| Judge-panel recipe: N drafts, parallel judges, schema-validated scores, mean ranking | `skills/finhub-harness/references/workflow-recipes.md:84-138` [verified] | A35 (partial; see C10) |
| A/B runs, trigger evals with near-misses, train/test split, `grading.json`/`timing.json` schema | `skill-testing-guide.md` §3, §4, §8, §9; `skill-writing-guide.md` §7 [verified headings] | R6-R11 |
| Retry once, then record the gap; no retry on auth or limit failures | `orchestrator-template.md:82, :246-247`, `quality-gates.md` §3-6 [verified] | R14, OH29 (partial) |
| `_workspace/` intermediates kept and archived per run | orchestrator and `workspace-layout.md` [verified grep] | R15, OH5 |
| Plugin manifest check (valid JSON, kebab-case name), skill frontmatter has name and description, v1 artefact gate | `scripts/package-plugin.sh:11-43` [verified] | OH17, OH47 (partial). Covers **this repo's own** skills only; see C2. |
| v2.1.0 harness port (team patterns, orchestrator templates, agent reuse, duplicate review) | `skills/finhub-harness/**` [verified] | R12, R13, revfactory "Do not port" rows |

## Backlog

Weights: value 0.35, licence 0.20, effort (inverse) 0.20, risk (inverse) 0.15, novelty 0.10. Each cell gives the score, a reason and an evidence tag. Ties are broken as the rubric says: lower effort, then cleaner licence, then a single-command proof.

| id | capability | source rows | target | licence | value | licence | effort | risk | novelty | total | proof |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Generated agents declare the connectors/MCP servers they need; orchestrator preflights them before spawning | **OH8** (`coordinator/agent_definitions.py:956` `has_required_mcp_servers`) | plugin skill | MIT adapt (OH upstream unverified) | 1.0: a missing connector stops the run at Step 0 instead of failing silently mid-run; chat failures are "only visible after a call" [verified surfaces.md:139] | 1.0: MIT [verified LICENSES.md] | 1.0: S, about 30 lines of prose across SKILL Step 3 and the orchestrator-template Step 0 [assumed] | 0.6: deferred tool listings could hide a connector that is present and cause a false stop; mitigation is to warn and ask on chat/Cowork, and hard-stop only on Code [assumed] | 1.0: no preflight anywhere [verified grep "connector" in skills/] | **0.94** | Build the fixture harness from the cold-trigger test with one agent that declares `mcp__fixture__ping`, then run it on Code with that server absent. PASS: the orchestrator reports "missing connector `fixture` for agent X" before any Agent call, and the transcript has 0 Agent calls. FAIL: an agent is spawned and fails on its first tool call. |
| C2 | Lint script for generated harnesses: names, frontmatter, cross-references, model field, v1 artefacts | **C52** (`skills/validation.py:43`), A32 (`skill_model.py:19`), D50 (`skill-filesystem/src/index.ts:909`, name regex `skill/src/index.ts:20`), OH14 (`skills/_frontmatter.py:34`), C35 (`crew.py:725`) | plugin skill (`skills/finhub-harness/scripts/` + Step 6.1) | MIT adapt | 1.0: a misnamed skill or a dangling `subagent_type` silently never triggers; the third party gets files that load [assumed] | 1.0: all sources MIT [verified] | 1.0: S, ≤150 lines of stdlib Python [assumed] | 0.6: strict rules could reject valid files; unknown frontmatter keys are warnings, not errors [assumed] | 0.6: `package-plugin.sh:24-43` checks this repo's own skills for name/description and v1 only; SKILL Step 6.1 is a manual list [verified] | **0.90** | `python skills/finhub-harness/scripts/lint_harness.py tests/fixtures/harness_bad/` exits 1 and names each seeded defect (dir≠name, 65-char name, empty description, `subagent_type: ghost` with no agent file, `TeamCreate(`). The same command on a clean fixture and on this repo's `.claude/` exits 0. |
| C3 | Secret-shape redaction of tool results and MCP text, returning labels only | **OH65** (`memory/team.py:24` `SECRET_RULES`, `:80`), O12 (`redact-mcp-secrets.ts:18`, Bearer `:31`) | runtime module (`tools/secret_scan.py`, called from `loop.py:_execute` and `mcp/client.py:redact`) | MIT adapt | 1.0: a credential echoed by a tool (cat of a `.env` inside the workspace, an MCP error) no longer reaches the transcript or `_workspace` [assumed] | 1.0: MIT [verified] | 1.0: S, a regex table plus two call sites [assumed] | 0.6: false positives could corrupt legitimate output; mitigation is anchored token shapes only, no generic-hex rule, and a negative test on 40-hex git SHAs [assumed] | 0.6: only value-based redaction (`mcp/client.py:107`) and env-name scrub (`stream.py:22`) exist [verified] | **0.90** | `pytest tests/test_secret_scan.py`: synthetic `AKIA`+16, `ghp_`+36, `sk-ant-` and `-----BEGIN PRIVATE KEY-----` strings are replaced and their labels returned, and the match never appears in the output. A 40-hex SHA and a UUID pass through unchanged. A loop run whose echo tool returns a fake key yields a transcript without it. Mutants that drop a rule or the call site must be killed. |
| C4 | Eval regression buckets: compare with a prior report and fail on any pass→fail case | **A36** (`challenge_loader.py:49`, filter `:66`), C24 (`experiment/result.py:99`), R6 (`skill-testing-guide.md:135`, Apache) | runtime module (`evals/runner.py`) | MIT adapt | 0.6: QA can see regressions, not just today's pass rate; this is the runtime evals, so third parties do not see it directly [assumed] | 1.0: primary MIT [verified] | 1.0: S, one compare function plus a `--baseline` flag [assumed] | 1.0: reads one JSON file; no new surface [assumed] | 1.0: no baseline or regress logic in `evals/` [verified grep] | **0.86** | `python -m master_finhub.evals.runner --baseline prev.json cases/` where one case flips pass→fail. PASS: the report lists it under `regressed` and the exit code is non-zero. With no flips the exit is 0, and a new case is listed under `new`. |
| C5 | Claude Code hook kit for generated harnesses: a PreToolUse deny hook using the exit-2 protocol | **D42** (`hook-protocol/src/codec.ts:59`), D43 (`:97`), D44 (`merge.ts:62`), D45 (`matcher.ts:57`), D46 (`runner.ts:67`), D48 (`hooks-claude-code/src/index.ts:96`), OH41 (`hooks/schemas.py:10`), OH51 (`plugins/loader.py:649`) | plugin skill (new `references/hooks.md`, a sample script, Step 3/5 edits) | MIT adapt | 1.0: a generated harness ships an enforced guard, not just prose, so the third party gets a safer tool guard [assumed] | 1.0: MIT [verified] | 0.6: M, a new reference file, a sample hook script and edits in two SKILL steps [assumed] | 0.6: a bad matcher can block legitimate tools; mitigation is that only exit 2 blocks, other errors do not, and a load-time matcher check (D45) runs [assumed] | 1.0: no hook guidance in `skills/` [verified grep "hook": only frontend-hook hits] | **0.86** | `echo '{"tool_name":"Read","tool_input":{"file_path":"/home/u/.ssh/id_rsa"}}' \| skills/finhub-harness/scripts/hooks/deny_sensitive.py; echo $?` prints 2 and a reason on stderr. A workspace path gives 0. Malformed JSON gives a non-blocking non-zero code. A cold-built harness from the skill text includes `hooks/hooks.json` wired to it. Code only; chat and Cowork hooks are unverified. |
| C6 | Delegation contract: self-contained brief in; status, evidence and blocker report out, validated once | **OH2** (`coordinator/coordinator_mode.py:407`), OH1 (`:252`), OH3 (`:432`), OH79 (`autopilot/service.py:2013`), D53 (`goal-round-driver/src/prompt.ts:12`), D54 (`tool-ralph/src/index.ts:90`, `:112`), O32 (`launch-child-conversation-client-tool.ts:14`), C28 (`crew_base.py:97`), C29 (`task.py:120`), C34 (`crew.py:1531`), C37-C39 (`utilities/guardrail.py:60`, `task.py:1327`, `:412`) | plugin skill (`orchestrator-template.md` principles + Step 6 check) | MIT adapt | 0.6: worker briefs and "done" claims get better, but this is prompt quality, not a verifiable guarantee [assumed] | 1.0: MIT [verified] | 1.0: S, one principles section plus one Step 6 line [assumed] | 1.0: prose; no runtime surface [verified] | 0.6: Mode C already asks for "Agent parameters without omission" (`orchestrator-template.md:275-285`); no banned-phrase rule and no report schema [verified] | **0.82** | Step 6 grep `grep -nEi "based on (your\|the) (findings\|research)\|as (we )?discussed" <harness>/.claude/skills/*/SKILL.md` returns nothing on a cold-built harness. A fixture orchestrator containing the phrase is flagged (the same check can live in C2's lint). A report marked `complete` with no `evidence` field is rejected and re-asked once. |
| C7 | Evolve retrospectives: diagnose by layer, cite evidence per lesson, back up before rewrite, never copy secrets | **OH20** (`skills/bundled/content/diagnose.md:1`), OH68 (`services/autodream/prompt.py:12`), OH63 (`memory/schema.py:192`), OH69 (`autodream/backup.py:27`), A37 (`analyze_failures.py:270`, enum `:66`), A38 (`reflexion.py:109`), D57 (`.agents/notes/README.md:1`), C45 (`crew.py:943`) | plugin skill (`finhub-harness-evolve` Phase 1-2) | MIT adapt | 0.6: makes Daniel's evolve loop sharper; third parties do not see it [assumed] | 1.0: MIT [verified] | 1.0: S, one section [assumed] | 1.0: prose [verified] | 0.6: Phase 2 already classifies feedback by type [verified headings] | **0.82** | Run `finhub-harness-evolve` on a synthetic feedback fixture with 4 seeded failures (one per layer: routing, execution, verification, governance) and one seeded fake token. PASS: each failure is assigned the right layer, each lesson cites a file path, the token is absent from the output, and a `.bak` exists before any edited file changes. |
| C8 | Advisory repeat-call reminder in the agent loop (3/5/8 identical calls); never vetoes | **D49** (`guard/repeat-tool-reminder/src/index.ts:162`, observe `:189`, text `:63`/`:70`), A27 (`watchdog.py:32`) | runtime module (`runtime/loop.py`) | MIT adapt | 0.6: fewer wasted steps before `max_steps`; invisible to third parties [assumed] | 1.0: MIT [verified] | 1.0: S, a counter keyed on canonical args, about 40 lines [assumed] | 0.6: the injected text changes the transcript; mitigation is to append it to the tool result so the tool pair is never split [assumed] | 1.0: the loop only raises at `max_steps` (`loop.py:186-190`) [verified] | **0.80** | `pytest tests/test_loop.py -k repeat`: a ScriptedLLM issues the same `echo{"x":1}` 3 times. The third tool result ends with the reminder, the calls still run (no veto), the counter resets on a user message, and key order `{"b":1,"a":2}` vs `{"a":2,"b":1}` counts as the same call. Listed above C9 on a tie because it touches one file. |
| C9 | Verification gates as data: argv only, no shell; shell metacharacters are an error unless `shell: true` | **OH28** (`autopilot/service.py:155`, run `:2094`, tests `tests/test_autopilot/test_verification.py:19-82`), OH81 (`:492`), OH29 (`:1595`) | runtime module (`evals/gates.py` + CLI) | MIT adapt | 0.6: QA re-runs a declared gate list that cannot be quietly skipped; this is the runtime QA path [assumed] | 1.0: MIT [verified] | 1.0: S, a parser plus `subprocess.run` [assumed] | 0.6: it runs commands; bounded by argv-only, a timeout, and cwd held inside the repo [assumed] | 1.0: no command-gate layer in `evals/` [verified] | **0.80** | `pytest tests/test_gates.py`: `"pytest -q"` runs as argv. `"pytest; rm x"` is a policy error that fails the step without spawning anything (assert via a spawn spy). `shell: true` is honoured only when declared. A gate that times out reports FAIL, not PASS. |
| C10 | Judge-panel recipe reports judge spread and flags low consensus instead of a silent pick | **A35** (`multi_agent_debate.py:510`, `_get_proposal_score` `:284`), OH44 (`hooks/executor.py:169`, `_parse_hook_json` `:232`) | plugin skill (`workflow-recipes.md` §3) | MIT adapt | 0.6: a third party sees when judges disagreed, but it is a recipe change, not a guard [assumed] | 1.0: MIT [verified] | 1.0: S, a few lines in one recipe [assumed] | 1.0: prose and a script [verified] | 0.2: the recipe already ranks by schema-validated mean (`workflow-recipes.md:119-133`) [verified] | **0.78** | Recipe dry run with stubbed judges scoring draft 0 as 9, 2 and 9 (spread 7 > threshold): the result carries `lowConsensus: true` and the spread. A judge reply that is not schema-valid is excluded, never defaulted. A35 defaults missing critiques to 0.5; that must not be copied, and the proof asserts it. |
| C11 | Cross-reset state ledger for generated orchestrators (`_workspace/00_state.md` rebuilt at each phase) | **OH77** (`autopilot/service.py:340, :381, :405`), OH53 (`services/compact/__init__.py:566`), OH54 (`:635`), OH55 (`:964`), D24 (`compaction-basic/src/summarizer.ts:31`), D33 (`goal/src/fold.ts:271`), OH40 | plugin skill (`orchestrator-template.md` A/B/C + `surfaces.md` fallback) | MIT adapt | 0.6: long runs resume after compaction or a lost session; benefit is real but indirect [assumed] | 1.0: MIT [verified] | 0.6: M, three templates plus the chat fallback [assumed] | 1.0: prose [verified] | 0.6: Step 0 "check existing work" exists, but there is no ledger layout or checkpoint template [verified] | **0.74** | Cold-build a Mode C fixture harness, stop it after phase 2, then start a fresh session with "continue". PASS: phase-1 outputs keep their mtimes, the orchestrator cites `00_state.md` "next step", and phase 3 starts. A Step 6 grep confirms that each template writes `00_state.md` at every phase boundary. |
| C12 | Ordered pre/post tool hook chain in the runtime (deny wins, per-hook failure policy, audit record) | **OH42** (`hooks/executor.py:64`, `types.py:21`), OH41 (`schemas.py:10`), OH45 (`engine/query.py:895`, `:1009`), D44 (`merge.ts:62`), D46 (`runner.ts:67`), D47 (`events.ts:92`), C50 (`hooks/tool_hooks.py:142`), Y31 (dify, pattern only; idea of paired input/output checks) | runtime module (`runtime/hooks.py`, `loop.py:_execute`) | MIT adapt (Y31 pattern only) | 0.6: a seam, not a guard; it lets C3 and future guards compose [assumed] | 1.0: primary MIT [verified] | 0.6: M, a new module plus loop and resume-path changes (`loop.py:179` re-checks the guard on resume) [verified] | 0.6: in-process callables only; command and HTTP hooks (OH43) excluded so a hook cannot stall the run [assumed] | 0.6: a single `ToolGuard` exists (`loop.py:112`) [verified] | **0.68** | `pytest tests/test_hooks.py`: deny from hook 2 of 3 blocks the call and returns hook 2's reason as the tool result. A post-hook sees and may replace the result. A raising hook with `block_on_failure=True` blocks and with `False` passes. The existing `tests/test_safety.py` still passes with `guard_tool_call` registered as hook 0. |

## Top 3 in detail

### C1 — Connector preflight for generated agents

- **What it is.** Each generated agent definition names the connectors or MCP servers it cannot work without. The orchestrator's Step 0 checks that those tool prefixes (`mcp__<server>__`) are present before it spawns anyone. Source: OH8, where OpenHarness filters agents whose required MCP servers are missing (`references/openharness/src/openharness/coordinator/agent_definitions.py:956`, loader `:695`).
- **Why it ranks here.** It is the only candidate that is cheap, prose-only and directly changes what a third party receives on Cowork and chat. Those are the surfaces where `surfaces.md:139` records that connector failures appear only after a call. Nothing in `skills/` does this today [verified].
- **Adoption shape.**
  - SKILL Step 3 gains one bullet: "list required connectors in the body under `## Requires`".
  - `orchestrator-template.md` Step 0 in each template gets a 5-line preflight.
  - `surfaces.md` §6 checklist gets one row.
  - About 30 lines in total. No code.
- **Proof test.** Fixture harness with an agent requiring `mcp__fixture__ping`, run on Code with the server absent. Zero Agent calls must occur, and the stop message names the agent and the connector. Re-run with the stub server (`tests/mcp_stub_server.py` exists) present: the run proceeds.
- **Risks and "does not cover".** Deferred tool lists may not show a connector until its schema is loaded, so a hard stop could be a false positive on chat/Cowork. The rule there is warn and ask. The preflight does not check credentials or whether the connector works; it checks presence only. It does not cover connector-free agents.
- **Effort.** S.

### C2 — Lint script for generated harnesses

- **What it is.** A stdlib script shipped in the plugin. It checks a generated harness's `.claude/agents/*.md`, `.claude/skills/*/SKILL.md` and orchestrator:
  - directory name equals the frontmatter `name` (C52);
  - names match the kebab grammar, ≤64 chars, and descriptions are non-empty and ≤1024 chars (A32, D50);
  - frontmatter parses, with a fallback chain for diagnostics (OH14);
  - every `subagent_type`/`agentType` referenced resolves to an agent file, and a coordinator agent has no work tools (C35, C34);
  - every agent has `model` with a reason comment;
  - no v1 artefacts.
- **Why it ranks here.** SKILL Step 6.1 asks for exactly these checks, but by hand. `package-plugin.sh` automates part of them, and only for this repo's own skills. A silent mis-wire (a skill that never triggers, a missing agent type) is the most common way a generated harness fails a third party without anyone noticing.
- **Adoption shape.**
  - `skills/finhub-harness/scripts/lint_harness.py` (≤150 lines).
  - Step 6.1 changes to "run the lint; fix every error".
  - `package-plugin.sh` calls the same script on this repo's `skills/` so there is one rule set.
  - Two bad/good fixtures under `tests/fixtures/`.
- **Proof test.** The bad fixture exits 1 and lists each seeded defect by file. The good fixture and this repo's `.claude/` exit 0. Mutation spot-check: deleting any single rule lets its seeded defect through.
- **Risks and "does not cover".** Over-strict rules could block a valid harness, so unknown keys are warnings. On chat the script cannot run unless code execution is enabled, so the manual Step 6.1 list stays as the fallback. It does not judge description *quality*; trigger evals (§8) still do that.
- **Effort.** S.

### C3 — Secret-shape redaction of tool results and MCP text

- **What it is.** A regex table of anchored credential shapes: private-key blocks, AWS access keys, GitHub tokens, OpenAI/Anthropic keys, and Bearer headers that keep their prefix. FinHub-relevant shapes for Twilio, Xero and Mercury are added as synthetic patterns. The table is applied to every tool result in `AgentLoop._execute` and to MCP error and stderr text. It returns the redacted text and labels, never the match. Sources: OH65 (`references/openharness/src/openharness/memory/team.py:24`, `:80`) and O12 (`references/openhands/src/utils/redact-mcp-secrets.ts:18`, `:31`).
- **Why it ranks here.**
  - The runtime today redacts only *known config values* (`mcp/client.py:107`) and env *names* (`stream.py:22`).
  - A token read from a workspace file, or echoed by a server, reaches the transcript unchanged.
  - For a finance business this is the leak that matters most.
  - It ties C2 on score. It is listed after C2 only because the plugin is the primary capability (CLAUDE.md); the rubric's tie-breaks do not separate them.
- **Adoption shape.** New `tools/secret_scan.py` (about 80 lines). One call in `loop.py:_execute` after the tool runs. `mcp/client.py:redact` chains to it. Tests in `tests/test_secret_scan.py`. It needs no hook layer; if C12 is built later it can move to a post-hook.
- **Proof test.**
  - Synthetic positives are each redacted and labelled.
  - 40-hex SHAs, UUIDs and base64 image prefixes pass unchanged.
  - An end-to-end loop with a ScriptedLLM shows the fake key absent from `LoopSnapshot.messages`.
  - Mutants that drop the call site or any one rule must be killed.
- **Risks and "does not cover".**
  - False positives can corrupt legitimate output, so anchored shapes only and no generic entropy rule.
  - It does not catch split, encoded or novel-format secrets.
  - It does not scan files the agent *writes*; the workspace fence governs where those go, not what is in them.
  - It is not a DLP system.
- **Effort.** S.

## Suggested first pick

C1. It is the highest-scoring row, prose-only, and the cheapest one to judge. It also turns a known silent failure on chat and Cowork (`surfaces.md:139`) into an upfront stop for every harness the plugin generates. If Daniel would rather start in the runtime, C3 is the strongest code-level pick. Daniel decides.

## Deferred

| id | capability | total |
|---|---|---|
| C13 | Tool-output offload to a workspace file with a head/tail preview (OH36, OH59, D32) | 0.68 |
| C14 | Quickstart doc for the plugin, rewritten for the no-flag v2 install (R18) | 0.64 |

## Rejected

| candidate | reason (licence / no proof / duplicate / low value) |
|---|---|
| Compaction ledger, crash detection and circuit breaker (D22, D23, D29, OH57, OH58) | Low value. The summariser is model-free (`context.py:121`), so there is no LLM call to crash, retry or circuit-break. An audit record of the dropped range would be polish (value 0.2). |
| Microcompact and deterministic tiering (OH37, OH56) | Duplicate in substance: `context.py` already clips every oversized tool result and summarises without a model. |
| Human approval flow and permission presets (D39, D40, D41, OH70-OH73, A31) | Low value. The runtime is non-interactive, with no answerer, and building one is speculative. Revisit if the server (slice 10) gains an approve endpoint. |
| File-based memory store: schema, dedup, index cap, relevance, per-agent dirs (OH60-OH64, OH66, OH67, C42-C44) | Low value. FinHub memory is external by design (Zep, Supermemory; OH map Gaps). The staleness and evidence ideas go into C7. |
| Planning todo list, planner and observer (C47, C48, C49) | Low value. Orchestrators already own task order. No harness gap is named. |
| Plugin loader trust and installer guard (OH47-OH50, OH52, OH18) | Low value / no consumer. Neither the runtime nor the plugin loads third-party plugins. OH47's dual manifest location is a lint rule that can join C2. |
| MCP health probe (O13-O16) | Low value, and a risk: "verified" health requires a successful tool call, which may mutate. No runtime consumer of a health status yet. |
| Prompt-injection safety fixtures (A39, `data_draft.json`) | No proof. Under `fake_llm.py` ScriptedLLM, an injection case tests the script, not resistance. It needs a live-model eval design first. |
| Keyless replay from real session JSONL (D56) | Risk. Harvesting real sessions conflicts with the synthetic-data-only rule (`runtime-builder.md:23`) unless a sanitising step is designed. That is its own design round. |
| Reviewer may only APPROVE or COMMENT (O35) | Conflicts with the adopted adversarial-audit design, where the judge can reject. |
| `@spec` ID tags (O36) | Mostly a duplicate. The Authority List already ties claims to cited lines and tests. |
| Status vocabulary and autopilot card lifecycle, scoring, tick and cron (O29-O31, OH74-OH76, OH78, OH80, OH82) | Low value / duplicate. capability-triage already records per-criterion reasons (the OH75 idea). One-at-a-time is already the orchestrator rule. OH77 is merged into C11. |
| Skill catalog digest, skill precedence, discovery and registry (D51, D52, OH15, OH16, OH19) | No consumer. The host (Claude Code, chat, Cowork) owns skill loading. |
| Plan-mode dry-run switch (OH32 mode, OH54, D34) | Low value [assumed]. No caller needs a dry-run mode today. Revisit with C12. |
| Sandbox escalation, policy precedence and prompt rendering (D8, D36, D37, D38) | Duplicate or delta-only against slice 3 policy modes. The miner's own note says "delta only". |
| Git worktree isolation (OH11), bridge runner and ingress secret (OH83, OH84) | No consumer (agents run on threads). OH84 is flagged unsafe by its miner. |
| dify observability, persistence, pause and suspend layers (Y22-Y27), RBAC and recipient scenes (Y29, Y30), variable namespaces (Y32, Y33), strategy base (Y34), last-iteration tool strip (Y35), annotations and feedback export (Y36, Y37), variable size cap (Y21) | Low value / no consumer, and pattern-only. Y21 is also unverified at line level per its miner. Y31 is kept only as a pattern note inside C12. |
| Upstream-change playbook and monitoring SLA (R16, R17) | Low value. No host flag is depended on today. |
| crewai config-by-name, agent trio, delegation scoping, LLM guardrail, hallucination guardrail (C30, C31, C32, C36, C40, C41) | Duplicate (slice 7) or unverified (C41 is a stub as far as opened). C40 is LLM-judged and only fits where code cannot check. |
| Train-and-test via repeated LLM scoring (C26, C27, C46) | Low value. Verifiers are deliberately deterministic (`verifiers.py:1`). |
| Polyform Shield sources excluded. | — |

## Gaps

- **Zero-byte factory modules.** `src/master_finhub/factory/evolver.py`, `skill_compiler.py` and `team_generator.py` are empty [verified]. CLAUDE.md says slice 12 is superseded by the `finhub-harness` skill. These look like the dead stubs QA removed from root `evals/` on 2026-10-02. Daniel may want them deleted; nothing in this backlog targets them.
- **No judge-panel or adversarial-majority audit in any map** beyond A35's in-agent debate. The Authority List audit remains FinHub's own. Search terms recorded by the miners: `panel`, `judge`, `refute`, `reviewer`, `consensus`, `critique` (OH, A, D, Y, O Gaps).
- **No skill trigger-quality testing** (near-miss description checks) in any repo. FinHub's §8 is already ahead. OH: `tests/test_skills` was not opened.
- **No cross-agent budget enforcement.** `cost_tracker.py` only sums usage (OH Gaps).
- **Hooks on chat and Cowork:** no map covers non-Code surfaces. C5 is Code-only until a surface check confirms otherwise.
- **Unopened areas the miners listed** (UNVERIFIED, so absence is not assumed):
  - deepseek: `packages/guard/timeout-policy`, `credentials/authorization`, `self-modification`, `.agents/skills/*`, `docs/`.
  - dify: `dify-agent/src/dify_agent/layers/` (the most relevant to hook conventions).
  - autogpt: repo-root `.claude`, `.agents`, `skills/`, `AGENTS.md`, `MULTI_EXPERT_TEAMS_PLAN.md`. These are MIT by root LICENSE but outside `classic/`; ask Daniel before mining.
  - openharness: `plugins/loader.py:320-620`, `channels/`, `ohmo/`.
- **Licence provenance:** openharness upstream org is still unverified. Every OH-primary row (C1, C3, C6, C7, C9, C11, C12) inherits that flag.
- **Scope note:** the OH map's header points at "OH51" for the content secret scan; the actual row is OH65 (OH51 is the hooks-file fallback). C3 cites OH65.
