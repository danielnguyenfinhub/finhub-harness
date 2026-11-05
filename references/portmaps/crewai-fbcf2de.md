# Port map — crewai

- Submodule: references/crewai
- Pinned SHA: fbcf2de (confirmed with `git rev-parse --short HEAD`)
- Licence: MIT (`references/crewai/LICENSE`; licence-rules.md row `crewai`, port as `adapt`). No NOTICE file. Attribution line required when adapting.
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: PARTIAL for the two purposes in scope (runtime and harness-factory). About 25 files opened, not exhaustive: the CLI, a2a, rag, knowledge, llms/providers, crewai-tools, crewai-files, events listeners, telemetry and docs were not opened (see Gaps).
- Language: all sources are Python under `references/crewai/lib/crewai/src/crewai/`; "adapt" means a rewrite under `src/master_finhub/` or prose in `skills/`. Every path below is written in full.
- Id prefix: `C`.
- Scope: harness-factory patterns (crew, agent and task definitions, delegation prompts, guardrails, flows, memory, evaluation, training) and runtime patterns (delegation tools, task context passing, LLM routing).

## Already covered or adopted (do not re-propose)

Checked by grep over `src/master_finhub/` and `CLAUDE.md`; only names, docstrings and the cited headers were read.

| what | where it lives now |
|---|---|
| Baseline buckets for eval runs (regressed, removed, fixed, still_failing, unchanged, new), adapted from crewai `experimental/evaluation/experiment/result.py:99` | `src/master_finhub/evals/runner.py:7` and `:36`. Row C25 below covers only what that module did not take. |
| Exact repeated tool call is blocked (crewai `tools/tool_usage.py:779`, message `en.json:49`) | `runtime/repeat_reminder.py` (reminder at counts 3/5/8); same idea, do not re-propose |
| Subagent fan-out where a child guard is the parent guard AND the config guard | `orchestration/modes/subagent.py` (delegation only gets stricter); crewai's `allow_delegation` flag has no such rule |
| Structured summary on context overflow | `runtime/context.py` is model-free; C12 below is only relevant if a model summariser is added |
| Provider retry and rate-limit waits | `runtime/anthropic_llm.py` docstring (SDK retry budget); crewai `utilities/rpm_controller.py:38` adds nothing a single-provider runtime needs |
| Do-nothing default and distilled lessons for the evolve skill | CW2 and C25 in CLAUDE.md; row C20 below adds only the "approval is not a lesson" rule |

## Findings

### (a) Runtime

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| C1 | 7 | Delegation tool takes coworker, task and context; its description tells the caller the coworker knows nothing, so share everything | references/crewai/lib/crewai/src/crewai/translations/en.json:58 (schema at references/crewai/lib/crewai/src/crewai/tools/agent_tools/delegate_work_tool.py:8) | adapt | Prompt wording only; own text. Fits subagent dispatch briefs and generated orchestrators. |
| C2 | 7 | Coworker lookup normalises whitespace, case and quotes; a miss returns the list of valid names instead of failing | references/crewai/lib/crewai/src/crewai/tools/agent_tools/base_agent_tools.py:20 (miss path at :99) | adapt | Comment at :66 says small models emit truncated JSON; the error doubles as a repair hint. |
| C3 | 7 | Delegated request becomes a fresh task whose expected output asks for the best answer to the asking coworker | references/crewai/lib/crewai/src/crewai/tools/agent_tools/base_agent_tools.py:112 (text at references/crewai/lib/crewai/src/crewai/translations/en.json:28) | pattern | Each delegation is a new unit with its own contract, not a continuation of the caller's context. |
| C4 | 7 | Delegation tools are injected only when delegation is allowed and more than one agent exists; the caller is removed from its own targets | references/crewai/lib/crewai/src/crewai/crew.py:1833 (injection helper at :1753) | pattern | Self-delegation exclusion is a one-line rule for generated orchestrators. |
| C5 | 7 | Hierarchical mode refuses a crew with no manager and refuses a manager that is also in the worker list | references/crewai/lib/crewai/src/crewai/crew.py:725 | adapt | Two checks; map to a lint rule in a generated team (coordinator must not be a worker). |
| C6 | 6 | Crew validators: first task not conditional, at least one unconditional task, a task's context may not name a later task | references/crewai/lib/crewai/src/crewai/crew.py:819 (also :803 and :868) | adapt | Cheap static DAG checks; compare against `dag_engine` validation before building. |
| C7 | 6 | Context passing: an explicit task list is joined as raw outputs; "not specified" means all earlier outputs; none means empty | references/crewai/lib/crewai/src/crewai/crew.py:1879 (join at references/crewai/lib/crewai/src/crewai/utilities/formatter.py:29) | adapt | Three-valued context (explicit, all, none) is the useful part. Header text at `en.json:21`. |
| C8 | 6 | Conditional step: a predicate over the previous output decides run or skip; a skip yields an empty output so later steps still run | references/crewai/lib/crewai/src/crewai/crews/utils.py:180 (predicate at references/crewai/lib/crewai/src/crewai/tasks/conditional_task.py:41) | adapt | The predicate sees only the previous output; skip is recorded, not silent. `graph.py` has node_skipped already. |
| C9 | 1 | Guardrail retry loop: on failure the error and the previous result are fed back as context; after N retries it raises with the last error | references/crewai/lib/crewai/src/crewai/task.py:1327 (give-up at :1382, feedback at :1400; text at references/crewai/lib/crewai/src/crewai/translations/en.json:55) | adapt | Bounded retry with feedback is the core of a QA-then-redo loop. Counts per guardrail index (:1343). |
| C10 | 1 | Guardrail contract is a pair (ok, data-or-error); success must not carry an error and failure must not carry a result | references/crewai/lib/crewai/src/crewai/utilities/guardrail.py:106 (exclusivity check at :81) | adapt | A guardrail returning None as a success result is rejected (task.py:1360). |
| C11 | 1 | LLM guardrail asks a judge for valid plus feedback only, explicitly no corrections; any judge error becomes a failure, not a pass | references/crewai/lib/crewai/src/crewai/tasks/llm_guardrail.py:49 (prompt rule at :89, fail-closed at :125) | adapt | Fail-closed is the opposite of hive HV21's fail-open parser. Prefer this behaviour. |
| C12 | 2 | At the iteration cap, ask once more for a final answer, using a trailing user turn because an assistant prefill is rejected | references/crewai/lib/crewai/src/crewai/utilities/agent_utils.py:366 (text at references/crewai/lib/crewai/src/crewai/translations/en.json:47) | adapt | The comment records the real 400 error. Cheap guard for our loop's last turn. |
| C13 | 2 | On context overflow either summarise or stop with a clear message, chosen by one explicit flag; summary has five named sections | references/crewai/lib/crewai/src/crewai/utilities/agent_utils.py:793 (section list at references/crewai/lib/crewai/src/crewai/translations/en.json:26) | pattern | Sections: task, state, discoveries, next steps, values to keep. Only if a model summariser is added. |
| C14 | 2 | Summary chunking retries with a smaller chars-per-token assumption (4, 3, then 2.5) before giving up | references/crewai/lib/crewai/src/crewai/utilities/agent_utils.py:878 (give-up at :958) | pattern | Our estimate is chars // 4; a fallback ladder is the idea. Low value without a summariser. |
| C15 | 1 | Per-tool usage cap: a spent tool returns a plain refusal text naming the limit | references/crewai/lib/crewai/src/crewai/tools/tool_usage.py:803 | adapt | Small. Useful for paid or send-type tools in a generated harness. |
| C16 | 1 | A tool reports its own failure in a typed object (reason, code, retryable); policy ignore, warn or raise; nothing guesses from text | references/crewai/lib/crewai/src/crewai/tools/tool_failure.py:71 (policy at :57, reasons at :35) | adapt | Docstring: Slack answers HTTP 200 with ok false, so the run was logged as success. Fits MCP isError. |
| C17 | 1 | Tool-input repair: try a JSON repair pass, and if the result is unusable or wrapped in a list, keep the original | references/crewai/lib/crewai/src/crewai/agents/parser.py:161 | pattern | Needs a repair library; overlaps hive HV6. Pick one coercion layer, not both. |
| C18 | 7 | Step planner: each step has number, tool_to_use, dependencies and status; a step that names a tool must call it or fail | references/crewai/lib/crewai/src/crewai/utilities/planning_types.py:27 (check at references/crewai/lib/crewai/src/crewai/agents/step_executor.py:521) | adapt | The "expected tool was not called" check is a one-function verification rule. |
| C19 | 1 | Each plan step runs on a fresh two-message list (system plus step prompt), not on the whole history | references/crewai/lib/crewai/src/crewai/agents/step_executor.py:245 | pattern | Token saver for haiku workers; the cost is losing earlier tool results unless passed in. |
| C20 | 1 | Observation after each step is an LLM call only at medium or high effort; at low it is a fixed heuristic with no call | references/crewai/lib/crewai/src/crewai/agents/planner_observer.py:88 (levels in references/crewai/lib/crewai/src/crewai/agent/planning_config.py:21) | pattern | Effort dial that removes a call. Matches the light-mode goal; heuristic always says plan still valid. |

### (b) Harness factory

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| C21 | meta | Human feedback is distilled to reusable rules only; approval or one-off corrections return an empty list; stored lessons are replayed before the next review | references/crewai/lib/crewai/src/crewai/flow/human_feedback.py:337 (replay at :279; prompt text at references/crewai/lib/crewai/src/crewai/translations/en.json:42) | adapt | Extends the evolve skill: a "looks good" reply is not a LESSON. Good-lesson examples are in the prompt. |
| C22 | meta | Feedback collapses to one routing label: exact match first, else the longest label found inside the reply | references/crewai/lib/crewai/src/crewai/flow/human_feedback.py:87 | adapt | Deterministic fallback for an LLM classifier reply. No match returns None; caller must decide. |
| C23 | memory | Memory consolidation prompt: per old record keep, update or delete; separately insert_new; "prefer keep when unsure" | references/crewai/lib/crewai/src/crewai/translations/en.json:75 (four-way routing by missing fields and similarity in references/crewai/lib/crewai/src/crewai/memory/encoding_flow.py:224) | pattern | Same intent as hive HV28 update-before-create. New: the conservative default sentence. |
| C24 | memory | Conflicting consolidation actions from several new items are merged first: one delete or one update per old record | references/crewai/lib/crewai/src/crewai/memory/encoding_flow.py:375 | pattern | Prevents two items rewriting the same record. Only if a memory store with batch writes is built. |
| C25 | eval | Regression gate: fail on any case that passed in the latest baseline; warn, not fail, when baseline cases are missing; first run only writes the baseline | references/crewai/lib/crewai/src/crewai/experimental/evaluation/testing.py:40 (baseline file handling at references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:48) | reference | Buckets are already adopted in `evals/runner.py`; check there that missing-case handling matches. |
| C26 | eval | Evaluator prompt scopes one metric with explicit "do not evaluate" lines and returns null score when the metric cannot apply | references/crewai/lib/crewai/src/crewai/experimental/evaluation/metrics/tools_metrics.py:22 (exclusions at :78, null score at :47) | pattern | Template for single-criterion judges in a generated QA agent; avoids blended scores. |
| C27 | eval | Declarative flow definition: static serialisable model with checks on method names, trigger namespace and expressions | references/crewai/lib/crewai/src/crewai/flow/flow_definition.py:714 (validators at :772, :778, :791) | pattern | Idea: a harness spec as data that is linted. Sample at `flow/templates/flow_definition_example.yaml`. |
| C28 | meta | Skill name rule: lowercase words joined by hyphens, at most 64 characters, directory name equals declared name, description at most 1024 | references/crewai/lib/crewai/src/crewai/skills/validation.py:15 (dir check at :43; description cap at references/crewai/lib/crewai/src/crewai/skills/models.py:21) | pattern | Compare to `lint_harness.py` rule list; add only the missing ones. Same family as hive HV27. |
| C29 | token | Three disclosure levels for a skill (name and description, then body, then resource list); output wrapped in a named tag | references/crewai/lib/crewai/src/crewai/skills/loader.py:293 | pattern | Confirms the light-skill design (description always, body on use). No new work. |
| C30 | meta | Task output path validator: rejects parent-directory parts and shell expansion or special characters before any write | references/crewai/lib/crewai/src/crewai/task.py:502 | adapt | A string pre-check only; the sandbox fence stays the real control. Useful in generated harness lint. |
| C31 | meta | Template fill replaces only `{identifier}` placeholders, leaves JSON braces alone, and raises on a missing key | references/crewai/lib/crewai/src/crewai/utilities/string_utils.py:79 | adapt | Small and testable; avoids `str.format` crashing on JSON in prompts. |
| C32 | meta | Trained suggestions are stored per agent role and appended to the task prompt as instructions that must be followed | references/crewai/lib/crewai/src/crewai/agent/core.py:1430 | pattern | Idea only: per-role rules file applied at run time. Storage is pickle (see Do not port). |
| C33 | runtime | LLM routing order: forced custom endpoint, then explicit provider, then provider prefix in the model name, then inference, then a generic fallback | references/crewai/lib/crewai/src/crewai/llm.py:283 (route resolution at :453) | pattern | We have one provider; reuse only the "explicit beats inferred" ordering if a second is added. |

## Do not port

| source | reason |
|---|---|
| references/crewai/lib/crewai/src/crewai/utilities/training_handler.py | Training data kept with pickle (`PickleHandler`); loading pickle is unsafe. Idea kept in C32 only. |
| references/crewai/lib/crewai/src/crewai/tasks/hallucination_guardrail.py | Its docstring says it is a no-op placeholder in the open-source repo; nothing to learn. |
| references/crewai/lib/crewai/src/crewai/a2a/**, references/crewai/lib/crewai/src/crewai/cli/**, references/crewai/lib/cli/**, references/crewai/lib/devtools/** | Agent-to-agent protocol, platform login and project scaffolding; out of scope. |
| references/crewai/lib/crewai/src/crewai/llms/**, references/crewai/lib/crewai/src/crewai/llm.py (litellm path) | Provider SDK wrappers; we call one provider directly. Routing idea only (C33). |
| references/crewai/lib/crewai/src/crewai/memory/storage/**, references/crewai/lib/crewai/src/crewai/rag/**, references/crewai/lib/crewai/src/crewai/knowledge/** | Vector store and embedder backends; no vector store in this runtime. |
| references/crewai/lib/crewai/src/crewai/telemetry/**, references/crewai/lib/crewai/src/crewai/plus_api.py | Usage telemetry and a vendor platform API; not wanted. |
| references/crewai/lib/crewai-tools/** | Third-party tool integrations; not opened, no pattern needed. |
| references/crewai/docs/** | Documentation snapshots; per its AGENTS.md the frozen versions are not edited; not mined. |

## Gaps

- No message bus or inter-agent channel. Delegation is a tool call that runs the target agent synchronously (`base_agent_tools.py:120`); nothing resembles a mailbox, so slice 7 messaging cannot borrow from it.
- No permission-mode or command-denylist layer. The nearest items are the hook veto points in `hooks/tool_hooks.py:173` (a hook returning False blocks a tool call) and C30; neither judges commands. Searched `hooks/` and `security/`; `security/fingerprint.py` is agent identity only.
- No adversarial reviewer panel. Reviewing is one guardrail agent (C11) or one evaluator per metric (C26); no consensus or multi-round audit.
- No mutation or test-sabotage pattern. The `crew.test()` method (`crew.py:2299`) scores crew runs with an LLM judge over N iterations; it was read only to its signature.
- Not opened: `lib/crewai/src/crewai/a2a/`, `cli/`, `rag/`, `knowledge/`, `llms/`, `events/listeners/`, `telemetry/`, `mcp/`, `lite_agent.py`, `crew.py` outside the lines cited (2,559 lines), `agent/core.py` outside the lines cited, `flow/flow.py`, `flow/runtime/`, `state/provider/`, `experimental/skills/`, `lib/crewai-files/`, `lib/crewai-tools/` and the tests tree. The checkpoint prune rule (`state/checkpoint_config.py:184`, keep the newest N) was seen but not turned into a row; `dag_engine` checkpoint already resumes.
- Line numbers cite the first line of the `def` or `class` unless the notes say "at :N". Rows C1 and C7 cite `en.json` or `formatter.py` for the text and the helper that carries it.
- `en.json` prompt text is a long JSON file; the cited line holds the whole prompt, so a port must be in own words (the pattern column is already own words).
