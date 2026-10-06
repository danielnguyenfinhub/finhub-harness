# Port map — crewai (runtime slices 8-11 + harness factory)

- Submodule: references/crewai
- Pinned SHA: fbcf2de (`git -C references/crewai rev-parse --short HEAD`, unchanged since the prior map)
- Licence: MIT (matches `references/LICENSES.md` row `crewai`, no drift)
- Mined: 2026-10-03 AEST
- Status: COMPLETE
- Scope: both. Prior rows C1-C27 re-checked on disk; C28-C47 are new factory rows.
- Path prefix: `L` = `references/crewai/lib/crewai/src/crewai`. The Source column always carries the full path.
- Re-verification: I sed-read the cited line of every prior row. 26 of 27 still match the unit they describe.
  - C14 had drifted. The cited line :15 is blank. The class is at :17, so the row below is corrected.
  - For C1-C27 the line is only the unit's first line (class/def/constant); I did not re-open bodies, so row descriptions are carried over from the prior run.
  - C2 (:54) is the first of the timeout constants.
  - C4 (:435) is `_list_tools_impl`, which does the normalising. The public `list_tools` is :403, which C16 cites.
  - C5 (:612) is `_call_tool_impl`. C20 (:59) is `_run_test_case`. C21 (:130) is `_assert_scores`. C22 (:26) is the `ExperimentRunner` class.
  - C24 (:99) is `_compare_with_run`.
- Not re-proposed (already adopted): runtime slices 1-11, including slice 7 delegation/task context. OH23-27 and OH31 are not touched.

## Findings

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| C1 | 9 | Result carrier pairing tool text with the MCP `isError` flag, so errors are not lost | references/crewai/lib/crewai/src/crewai/mcp/client.py:45 | adapt | NamedTuple/dataclass; maps to the loop's tool-result error flag |
| C2 | 9 | Client constants: 30s connect/exec/discovery timeouts, 3 retries | references/crewai/lib/crewai/src/crewai/mcp/client.py:54 | adapt | Plain module constants; make them injectable for tests |
| C3 | 9 | Client with `connect` / `disconnect`, async context manager, auto-connect on first use | references/crewai/lib/crewai/src/crewai/mcp/client.py:67 | adapt | Keep the small surface: connect, list_tools, call_tool, disconnect |
| C4 | 9 | `_list_tools_impl` normalises each tool to name / original_name / description / inputSchema | references/crewai/lib/crewai/src/crewai/mcp/client.py:435 | adapt | Keep the original name for the wire call; sanitised name for the LLM |
| C5 | 9 | `_call_tool_impl` runs under `asyncio.wait_for`, takes the first content item's text, reads `isError` | references/crewai/lib/crewai/src/crewai/mcp/client.py:612 | adapt | Join all text items instead of only the first (crewai drops the rest) |
| C6 | 9 | Retry wrapper: per-attempt timeout, 2**attempt backoff, auth and not-found errors fail fast | references/crewai/lib/crewai/src/crewai/mcp/client.py:706 | adapt | Its string matching on "unauthorized" is crude; retry only transient errors |
| C7 | 9 | Strips None values from tool arguments, recursing into dicts and lists | references/crewai/lib/crewai/src/crewai/mcp/client.py:563 | adapt | Drop the hard-coded `sources` special case at :578 |
| C8 | 9 | Tool-name sanitiser: NFKD to ASCII, split camelCase, lowercase, `[a-z0-9_]`, 64 chars with sha256 suffix | references/crewai/lib/crewai/src/crewai/utilities/string_utils.py:26 | adapt | Stdlib only; avoids provider name-rule rejections |
| C9 | 9 | Transport ABC: connect/disconnect, `_set_streams` / `_clear_streams`, `connected` flag | references/crewai/lib/crewai/src/crewai/mcp/transports/base.py:25 | adapt | Only needed with more than one transport; stdio-only needs no ABC |
| C10 | 9 | Stdio transport connect: merges env over the SDK default env, then applies an optional env-filter hook | references/crewai/lib/crewai/src/crewai/mcp/transports/stdio.py:69 | adapt | Spawn with a scrubbed env, not the parent env |
| C11 | 9 | Module-level `_env_filter_hook` for stripping credentials from child env | references/crewai/lib/crewai/src/crewai/mcp/transports/stdio.py:13 | adapt | Idea becomes an allowlisted env builder; matters for secrets here |
| C12 | 9 | Stdio disconnect: terminate, wait up to 5s, then kill; cleanup best-effort and logged | references/crewai/lib/crewai/src/crewai/mcp/transports/stdio.py:124 | adapt | `self._process` is never assigned in connect(); terminate branch is dead code, do not copy |
| C13 | 9 | `StaticToolFilter`: allow list and block list on tool name, block wins | references/crewai/lib/crewai/src/crewai/mcp/filters.py:38 | adapt | Tiny; per-server tool allowlist, a safety win |
| C14 | 9 | `MCPNativeTool`: fresh client per invocation via `client_factory`, name prefixed `{server}_{tool}` | references/crewai/lib/crewai/src/crewai/tools/mcp_native_tool.py:17 | adapt | Line corrected from :15. Per-call client avoids shared state; costs a spawn per call |
| C15 | 9 | Exception hierarchy: `MCPConnectionError` subclasses `ConnectionError` and carries `status_code` | references/crewai/lib/crewai/src/crewai/mcp/exceptions.py:49 | adapt | Only the base class is worth keeping for a stdio-only client |
| C16 | 9 | Public `list_tools` with tool-list cache keyed per server, 300s TTL | references/crewai/lib/crewai/src/crewai/mcp/client.py:403 | pattern | Cache dict is module-global at :58; skip it or keep it per instance |
| C17 | 8 | Stream session: ordered frames through a queue, run in a worker thread, end/error by sentinel/exception | references/crewai/lib/crewai/src/crewai/utilities/streaming.py:254 | adapt | `queue.Queue`, sentinel None, re-raise errors; same shape as sandbox output stream |
| C18 | 8 / 10 | `StreamFrame` model: monotonic `seq`, `type`, `channel`, `data`, `timestamp` | references/crewai/lib/crewai/src/crewai/types/streaming.py:31 | adapt | Frozen dataclass; reuse for stdout chunks and SSE events |
| C19 | 8 / 10 | Queue sentinel helpers `_signal_frame_end` / `_signal_frame_error` (put None or the exception) | references/crewai/lib/crewai/src/crewai/utilities/streaming.py:229 | adapt | Consumer raises on Exception items and stops on None |
| C20 | 11 | `_run_test_case`: run the system, score it, compare to `expected_score`; any exception becomes a failed result with score 0.0 | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:59 | adapt | Per-case try/except so one crash does not kill the run |
| C21 | 11 | `_assert_scores` pass rule: actual >= expected for scalars; for dicts each matching key >= expected | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:130 | adapt | Scalar path is enough for slice 11 |
| C22 | 11 | `ExperimentRunner`: dataset-driven loop with a stable per-case id (explicit `identifier` or md5) | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/runner.py:26 | adapt | Use sha256, not md5; the id keys baseline comparison |
| C23 | 11 | `ExperimentResult` record: identifier, inputs, score, expected_score, passed | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:9 | adapt | Frozen dataclass is enough; no pydantic |
| C24 | 11 | `_compare_with_run` buckets each case into improved / regressed / unchanged / new by prior `passed` | references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result.py:99 | adapt | Optional; one benchmark pass/fail needs no baseline |
| C25 | 11 | `assert_experiment_successfully` raises `AssertionError` listing each failed case, expected vs actual | references/crewai/lib/crewai/src/crewai/experimental/evaluation/testing.py:13 | adapt | Readable pytest-facing failure message |
| C26 | 11 | `EvaluationScore`: 0-10 score, feedback text, raw response | references/crewai/lib/crewai/src/crewai/experimental/evaluation/base_evaluator.py:32 | pattern | LLM-judge scoring; slice 11 verifiers should be deterministic |
| C27 | 11 | `BaseEvaluator` ABC with `evaluate()` and a metric category | references/crewai/lib/crewai/src/crewai/experimental/evaluation/base_evaluator.py:52 | pattern | A plain `Callable[[output], bool]` is simpler |
| C28 | crew-task-agent definitions | Task config schema: description, expected_output, agent, context (list of task names), async_execution, human_input, guardrail, guardrail_max_retries | references/crewai/lib/crewai/src/crewai/project/crew_base.py:97 | adapt | Maps to an agent/task field checklist for harness-factory output; keep expected_output mandatory |
| C29 | crew-task-agent definitions | Task model: required `description` plus `expected_output`, optional `context` list and `output_file` | references/crewai/lib/crewai/src/crewai/task.py:120 | adapt | "Every task states its expected output" is the transferable rule |
| C30 | crew-task-agent definitions | Agent config TypedDict (YAML-sourced): role/goal/backstory style fields, all optional | references/crewai/lib/crewai/src/crewai/project/crew_base.py:42 | reference | Role/goal/backstory trio is the convention; finhub agents already use description+principles |
| C31 | crew-task-agent definitions | YAML configs resolved by name: agent and task string references mapped to instances after load | references/crewai/lib/crewai/src/crewai/project/crew_base.py:621 | pattern | Idea only: names in config, instances resolved later; fail early on unknown name |
| C32 | delegation | Delegation base: case-insensitive, whitespace-normalised coworker matching; unknown name returns an error string listing coworkers | references/crewai/lib/crewai/src/crewai/tools/agent_tools/base_agent_tools.py:20 | reference | Slice 7 already adopted delegation; read only to compare. Not re-proposed |
| C33 | hierarchical manager | `Process` enum: sequential and hierarchical only (consensual is a TODO) | references/crewai/lib/crewai/src/crewai/process.py:6 | adapt | Two modes are enough; maps to a coordinator vs fixed-order team switch |
| C34 | hierarchical manager | Manager creation: a custom manager gets `allow_delegation=True` and must have NO tools; default manager gets only the delegation tools | references/crewai/lib/crewai/src/crewai/crew.py:1531 | adapt | Rule worth keeping: coordinator delegates, never does work itself |
| C35 | hierarchical manager | Config validation: hierarchical process requires `manager_llm` or `manager_agent`, and the manager must not also be in `agents` | references/crewai/lib/crewai/src/crewai/crew.py:725 | adapt | Cheap team-definition lint; port as a QA check on team manifests |
| C36 | hierarchical manager | Per-task manager tool injection: if the task has an agent, delegate only to it; otherwise delegate to all agents | references/crewai/lib/crewai/src/crewai/crew.py:1866 | pattern | Scoped delegation list per task; slice 7 covers the tool itself |
| C37 | guardrails | `GuardrailResult` (success, result, error) built from a `(bool, data)` tuple; result and error mutually exclusive | references/crewai/lib/crewai/src/crewai/utilities/guardrail.py:60 | adapt | Frozen dataclass; the (ok, payload-or-error) tuple contract is the useful part |
| C38 | guardrails | `_invoke_guardrail_function`: run guardrail, on failure feed the error back and retry up to `guardrail_max_retries` (default 3), then raise | references/crewai/lib/crewai/src/crewai/task.py:1327 | adapt | Bounded retry loop with error fed back; strongest candidate for task-output validation |
| C39 | guardrails | `guardrails` is an ordered list of callables or strings, each with its own retry counter | references/crewai/lib/crewai/src/crewai/task.py:412 | adapt | Chain several deterministic checks; per-guardrail counters avoid one check starving another |
| C40 | guardrails | `LLMGuardrail`: a natural-language description is turned into an LLM validator returning `(bool, feedback)` | references/crewai/lib/crewai/src/crewai/tasks/llm_guardrail.py:49 | pattern | LLM-judged, non-deterministic; use only for criteria code cannot check |
| C41 | guardrails | `HallucinationGuardrail` class: output vs reference context check | references/crewai/lib/crewai/src/crewai/tasks/hallucination_guardrail.py:20 | reference | Body is a stub or enterprise-gated as far as opened; I read only the class header and `__call__` signature |
| C42 | memory | Unified `Memory`: remember / recall / forget / update on hierarchical scopes, with `scope()` and `slice()` views | references/crewai/lib/crewai/src/crewai/memory/unified_memory.py:76 | pattern | Single store with scope paths replaced the old short/long/entity split |
| C43 | memory | Recall scoring: composite of semantic similarity, recency decay (half-life in days) and explicit importance, each weighted | references/crewai/lib/crewai/src/crewai/memory/types.py:135 | adapt | Weighted-score formula is a few lines; fits a ledger/lessons ranker without embeddings if similarity is keyword-based |
| C44 | memory | `MemoryRecord` with importance float, plus `ConsolidationPlan` actions for merging near-duplicate memories at write time | references/crewai/lib/crewai/src/crewai/memory/analyze.py:124 | pattern | Dedupe-on-write idea for lessons files; the LLM analysis step is heavy |
| C45 | training/evaluation | `Crew.train`: run n iterations with human feedback, save per-agent trained suggestions to a file keyed by agent role | references/crewai/lib/crewai/src/crewai/crew.py:943 | pattern | Feedback becomes per-agent suggestions reloaded into prompts; maps to the evolve loop |
| C46 | training/evaluation | `Crew.test`: n iterations scored by an evaluator LLM; `CrewEvaluator` aggregates per-task scores | references/crewai/lib/crewai/src/crewai/crew.py:2299 | pattern | Repeated-run scoring for a team; pair with C20/C21 deterministic runner instead of an LLM scorer |
| C47 | planning | `TodoList` with step dependencies: `get_ready_todos`, `mark_running/completed/failed`, `can_parallelize`, `replace_pending_todos` | references/crewai/lib/crewai/src/crewai/utilities/planning_types.py:45 | adapt | Small stateful plan with dependency readiness; stdlib dataclasses |
| C48 | planning | `CrewPlanner`: a planning agent writes a per-task step plan (`PlanPerTask`) that is appended to each task description | references/crewai/lib/crewai/src/crewai/utilities/planning_handler.py:37 | pattern | Plan-before-execute step; the prompt text is the transferable part |
| C49 | planning | `PlannerObserver`: after each step, observe the result and refine remaining steps (`StepObservation`, `apply_refinements`), with a heuristic fallback | references/crewai/lib/crewai/src/crewai/agents/planner_observer.py:39 | pattern | Replan-on-observation loop; the heuristic path (:88) avoids an LLM call |
| C50 | hooks | Before/after tool-call hook registry: before-hook returning False blocks the call; after-hook can rewrite the result | references/crewai/lib/crewai/src/crewai/hooks/tool_hooks.py:142 | adapt | Block-on-False reducer is the same shape as a denylist hook; check against OH31 before proposing |
| C51 | skills | `SkillFrontmatter` / `Skill` model: SKILL.md-style frontmatter, allowed-tools parsing, scripts/references/assets dirs, disclosure levels | references/crewai/lib/crewai/src/crewai/skills/models.py:43 | reference | Same Agent Skills layout the plugin already uses; read for comparison only |
| C52 | skills | `validate_directory_name`: skill directory name must match the frontmatter `name` | references/crewai/lib/crewai/src/crewai/skills/validation.py:43 | adapt | One-line lint for plugin skills; confirm the plugin does not already check it |

## Do not port

| source | reason |
|---|---|
| references/crewai/lib/crewai/src/crewai/experimental/evaluation/experiment/result_display.py | Rich console UI, out of scope |
| references/crewai/lib/crewai/src/crewai/experimental/evaluation/metrics/** | LLM-judged metrics tied to crewai Agent/Crew internals |
| references/crewai/lib/crewai/src/crewai/experimental/evaluation/agent_evaluator.py | Coupled to the crewai event bus |
| references/crewai/lib/crewai/src/crewai/mcp/tool_resolver.py | AMP slugs, platform fetch, pydantic schema generation; crewai-specific |
| references/crewai/lib/crewai/src/crewai/mcp/transports/http.py and sse.py | HTTP/SSE MCP transports; slice 9 proof is stdio only |
| references/crewai/lib/crewai/src/crewai/a2a/** | Agent-to-agent protocol, out of scope |
| references/crewai/lib/crewai/src/crewai/tools/agent_tools/** | Delegation and ask-question tools are already adopted in slice 7 |
| references/crewai/lib/crewai/src/crewai/utilities/training_handler.py | Pickle persistence of training data; unsafe format, do not copy |
| references/crewai/lib/crewai/src/crewai/crew.py (whole file) | Event-bus, telemetry and pydantic coupled; take only the cited units (C34, C35, C45, C46) |
| references/crewai/lib/crewai/src/crewai/memory/storage/** | LanceDB/Qdrant vector backends; new dependencies, not needed for a file ledger |

## Gaps

- **Delegation and ask-question tools:** present (`tools/agent_tools/`), but already adopted in slice 7. C32 and C36 are reference-only.
- **Short/long/entity memory:** these classes are not in this pin. `grep -rn "ShortTerm\|LongTerm\|EntityMemory" --include=*.py` over `L` returned nothing. They are replaced by the unified scoped `Memory` (C42-C44), which needs an embedder and LLM. The factory can only take the scoring formula and consolidation idea, not a ready store.
- **Slice 8 Docker sandbox:** crewai has none. `agent/core.py:1469` `_validate_docker_installation` is a deprecated no-op pointing at E2B/Modal. There is no container lifecycle or stdout pump. Take ingress from openhands and policy from deepseek.
- **Slice 10 SSE server:** crewai has no HTTP server, `text/event-stream` producer or PING/idle logic. Use dify (pattern only) for ping/idle. C17-C19 supply only the queue feeder.
- **Slice 11 benchmark:** crewai evaluation is LLM-scored on crewai Agents. Only the runner/threshold/baseline structure (C20-C25) is worth taking. The executable-verifier harness belongs to autogpt `classic/direct_benchmark` (MIT).
- **Slice 9 dependency risk:** the client wraps the third-party `mcp` SDK, imported lazily at `mcp/transports/stdio.py:83`, so it is not stdlib. Its licence was not checked. The architect should pick a stdlib JSON-RPC stdio client or have the SDK licence checked first. Stdlib newline-delimited framing is an inference, not a cited finding.
- **Guardrail C41:** only the class header and `__call__` signature were opened (`tasks/hallucination_guardrail.py:20,84`), so the notes on its behaviour are limited to that.
- **Not opened:** `memory/recall_flow.py` bodies, `memory/encoding_flow.py`, `utilities/evaluators/*` bodies, `skills/loader.py` bodies, `agent/planning_config.py` fields, `mcp/config.py`, `mcp/transports/http.py`, `tools/mcp_tool_wrapper.py` bodies, and `flow/` and `llm.py` streaming. No row cites their internals.
- **Existing harness state not checked:** I did not read `src/master_finhub/` or the plugin to confirm C50 and C52 are not already covered. The scout should check C50 against OH31 and C52 against the plugin's skill lint.
- **Licence file drift:** none found.
