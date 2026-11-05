# Port map — openhands

- Submodule: references/openhands
- Pinned SHA: a8c0558 (confirmed with `git rev-parse --short HEAD`)
- Licence: MIT ("Copyright © 2025 OpenHands contributors", `references/openhands/LICENSE:1-3`; licence-rules.md row `openhands`). One LICENSE only; no `enterprise/` directory, no NOTICE file. Attribution line required when adapting: holder "OpenHands contributors".
- Mined: 2026-11-05 (reference-miner, read-only)
- Status: COMPLETE for the scope given, but the scope is thin. This submodule is the OpenHands Agent Canvas React/TypeScript frontend (`references/openhands/AGENTS.md:3-4`), not the agent runtime. The agent loop, condenser, sandbox and event model live in other OpenHands repositories that are not pinned (see Gaps). Rows below are the frontend's contributor-governance files (`.agents/skills/`, `AGENTS.md`, `.github/`) and the few client-side tool and delegation modules. Not exhaustive: `src/components/`, `src/hooks/`, `src/routes/`, `tests/e2e/`, `electron/`, `helm/` and `docker/` were not opened.
- Language: sources are TypeScript, Python (`.github/scripts/`) and Markdown. "adapt" means a Python rewrite under `src/master_finhub/` or prose in `skills/`, with the MIT attribution comment.
- Id prefix: `O` (schema value for openhands).
- Scope: harness-factory patterns first (rows O1-O13), runtime patterns second (O14-O25).

## Already covered / adopted (do not re-propose)

Checked by grep over `src/master_finhub/`, `skills/` and `.claude/`, and by the CLAUDE.md change history.

| topic | where it lives now | note |
|---|---|---|
| Lean SKILL.md plus loaded-on-demand reference files | `skills/finhub-harness/references/skill-writing-guide.md:135-137` (progressive disclosure) | OpenHands' `references/guide.md` layout (`.agents/skills/e2e-testing/SKILL.md:10-20`) is the same idea |
| A test must fail when the behaviour regresses | `skills/finhub-harness/scripts/mutant_gate.py`, quality-gates 3-4 (OR-D2) | `custom-codereview-guide.md:238` says it in one sentence |
| Verdict bound to the exact candidate commit | `skills/finhub-harness/scripts/candidate_id.py` (OR-D1) | `pr-design-doc/SKILL.md:56-66` (head SHA must match) is the same rule |
| Cited lines checked against the pinned commit | `skills/finhub-harness/scripts/cite_check.py` (C27) | |
| Rigor assigned by the owner, not by an agent | `rigor_check.py`, `WAIVERS.md` (OR-S8) | O11 below adds only the label-actor analogy |
| Exact-repeat tool-call reminder, compaction, command guard, MCP client, SSE | `runtime/loop.py`, `runtime/context.py`, `tools/safety.py`, `tools/mcp/client.py`, `server/sse.py` | nothing comparable in this repo to port |
| Retry with exponential backoff (`references/openhands/src/api/with-retry.ts:4-26`) | open as hive HV11 (candidate H3) | 22 lines, no jitter, no error classification; HV11 is the better source |
| Secret redaction of messages | `tools/secret_scan.py`, `runtime/loop.py` | O23 is only about the MCP probe error path |

## Findings

### (a) Harness-factory patterns

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| O1 | meta | A review ends in exactly one verdict, approve or comment; the reviewer never issues a blocking verdict, a human owns blocking | references/openhands/.agents/skills/custom-codereview-guide.md:44-50 | adapt | Fits a generated reviewer or judge agent whose output must not gate by itself. |
| O2 | meta | First review step: confirm the change belongs in this repo against an ownership table; if not, say so and ask a maintainer | references/openhands/.agents/skills/custom-codereview-guide.md:65-76 (table also at references/openhands/AGENTS.md:26-37) | adapt | A scope check before inspection; our architect brief has no "wrong place" step. |
| O3 | meta | The executable guard test is the source of truth for a rule; prose points to it and never copies its allowlist; changing the allowlist counts as an architecture change | references/openhands/.agents/skills/custom-codereview-guide.md:85-90 (guard at references/openhands/src/api/no-direct-agent-server-calls.test.ts:7-11, :78) | adapt | Stops prose and gate drifting apart. Matches how `cite_check.py` is cited. |
| O4 | meta | An index table in the root instruction file maps work areas to skills with "invoke every applicable skill", and says not to copy rules back into the index | references/openhands/AGENTS.md:51-66 | adapt | Our pointer block (C33) lists no skill routing. Prose for the CLAUDE.md pointer rules. |
| O5 | meta | A human-only section of the PR description: agents must not add, edit, move or remove it; on a validator failure the agent stops and asks the human, or reports the exact error | references/openhands/AGENTS.md:47-49 | adapt | Same shape as our rule that owner words are quoted, never written by an agent. |
| O6 | meta | Machine check of that section: marker lines found only outside fenced code, so quoting the template cannot stand in for filling it; note must reach 20 characters | references/openhands/.github/scripts/check_pr_description.py:149-166 (length rule at :398-400; fence masking at references/openhands/.github/scripts/markdown_sections.py:59) | adapt | The fence-masking idea also bears on `finding_tags.py` and `waiver_ledger.py` parsing. Offsets are preserved. |
| O7 | meta | PR validator: a "Bug fix" type requires reproduction evidence; the checked type is cross-checked against the linked issue's labels so mislabelling cannot dodge the rule | references/openhands/.github/scripts/check_pr_description.py:235-253 (label cross-check described at :16-19, check at :317) | pattern | Idea is the cross-check. Our PR text is prose; no script proposed. |
| O8 | meta | Evidence rules: a mock-LLM or mocked-backend run is regression coverage, not live evidence; the artifact must name the backend and model; bug fixes need the same setup before and after | references/openhands/.agents/skills/custom-codereview-guide.md:207-221 | adapt | Directly useful for the Quick-lane PR line and for any "live proof" claim. |
| O9 | meta | Match evidence to behaviour: a still image proves a static state, not duration, ordering or refresh; those need a recording showing trigger, transition and final state | references/openhands/.agents/skills/custom-codereview-guide.md:224-228 | pattern | For harnesses that report UI or timing claims. One sentence in QA rules. |
| O10 | meta | Lifecycle fixes must also verify the resulting process or resource state (parent exit code, remaining child services, listening ports) | references/openhands/.agents/skills/custom-codereview-guide.md:236-238 (shutdown rule in references/openhands/.agents/skills/local-stack-runtime/references/guide.md:105) | adapt | Fits `boundary-qa` command/output blocks. Guide:105 says signal the process tree, not only the child. |
| O11 | meta | Only a repo writer may add the ready-for-dev label; a label from anyone else is removed by a workflow; one event per issue at a time | references/openhands/.github/workflows/issue-readiness-check.yml:4-5, :11-14, :36-41 | pattern | Analogy for "approval counts only from the owner". Not a script we need. |
| O12 | meta | Final-context discipline: before submitting, compare the summary and every finding with the current head, changed-file list, linked issues and open threads; re-read if a finding is outside them | references/openhands/.agents/skills/custom-codereview-guide.md:253-258 | adapt | One paragraph for judge/QA prompts. Complements candidate binding (mechanical) with a stated check. |
| O13 | meta | Before changing a shared helper, list affected consumers along named dimensions and test each distinct path, not the full product of dimensions | references/openhands/.agents/skills/custom-codereview-guide.md:116-131 (checklist at references/openhands/AGENTS.md:39-45) | adapt | Maps to Claude Code / chat / Cowork surface checks in a generated harness. |

### (b) Runtime patterns

| id | slice | pattern | source | port as | notes |
|---|---|---|---|---|---|
| O14 | 3 | A required minimum server version is raised when the client starts relying on new server behaviour; adding a client method does not make an old server support it | references/openhands/.agents/skills/custom-codereview-guide.md:104-114 (floor stored at references/openhands/config/defaults.json:8) | pattern | For MCP or plugin version assumptions. We pin no server version today. |
| O15 | 3 | Version compare returns null when either side cannot be parsed, treats the string "unknown" as unparseable, and ranks a prerelease below its release | references/openhands/src/api/agent-server-compatibility.ts:205-216 (compare at :253-282) | adapt | About 30 lines of Python. Unknown must not read as "old" or "new". |
| O16 | 1 | Tool descriptions double as prompts: say when to call, in what order, and not to repeat in the same turn; tool carries read-only, destructive, idempotent and open-world hints | references/openhands/src/api/canvas-ui-client-tool.ts:9-20, :22-58, :85-90 | adapt | No hint fields in `src/master_finhub/tools/` by grep. Hints could feed the guard. |
| O17 | 7 | Delegation tool text: the child cannot see the parent, so the brief carries goal, paths, constraints and deliverable; keep siblings' scope disjoint; one call per task | references/openhands/src/api/launch-child-conversation-client-tool.ts:14-59 | adapt | Our delegate tool prompt can copy the three rules. |
| O18 | 7 | Delegation is acknowledged at once; the real outcome returns later as a follow-up message with a fixed prefix carrying id, URL, target and status, or an error with guidance | references/openhands/src/api/launch-child-conversation-client-tool.ts:54-59 (result sent at references/openhands/src/services/child-conversation-launch.ts:486-516) | pattern | Async handoff shape. Our subagent mode is synchronous; relevant only if async is added. |
| O19 | 1 | Validate what the schema cannot (enum values dropped by the server, cross-parameter rules); each failure says "nothing was launched" and names the corrective call | references/openhands/src/services/child-conversation-launch.ts:99-132 | adapt | Pairs with hive HV6 (argument coercion). Failure text is written for the model. |
| O20 | 7 | A non-repeatable tool call is claimed by its call id in a persisted ledger before any network work, so a replayed event cannot launch twice; a corrupt ledger starts fresh; a full store proceeds | references/openhands/src/services/child-conversation-launch.ts:199-230 (use at :533) | adapt | Browser localStorage in source; we would use a file or the unit tracker. Accepts replay risk over never launching. |
| O21 | 7 | Isolation default is a git worktree per child; when the parent has no commit or worktree creation fails, fall back to a shared directory and tell the agent the consequence | references/openhands/src/services/child-conversation-launch.ts:266-272, :304-323 | adapt | The note field is the useful part: a fallback is reported, never silent. |
| O22 | 7 | When the server is too old to persist a parent link, the launch still succeeds and the result states the link was not saved | references/openhands/src/services/child-conversation-launch.ts:236-250 | pattern | Degrade-and-report instead of fail. Same idea as the surface degradation rules. |
| O23 | 4 | Workspace hooks loaded from a fixed file under the project directory with a 5 s timeout because the call is on the start path; any failure degrades to "no hooks" with a warning | references/openhands/src/api/hooks-service.ts:7-9, :17-19, :36-45 | adapt | Timeout-bounded optional config load. We have no hook loader in `src/`. |
| O24 | 4 | Secrets are redacted from a probe's error message before it is stored; a regex flags 401/403/unauthorized text as a credentials problem rather than a connection problem | references/openhands/src/api/mcp-health/probe-mcp-server-health.ts:16-36 | adapt | Could improve error classes in `tools/mcp/client.py`. Regex is conservative. |
| O25 | meta | Live-credential CI rules: key only in the one trusted step, never job-level env; skip fork PRs before checkout; no trace capture because traces record request bodies; failure text never prints credential-bearing responses | references/openhands/.agents/skills/e2e-testing/references/guide.md:13-15 | adapt | Prose for any harness that runs a live paid session (C28 live proofs). |

## Do not port

| source | reason |
|---|---|
| references/openhands/src/components/**, src/routes/**, src/hooks/**, src/ui/**, src/themes/**, src/i18n/** | React UI, out of scope |
| references/openhands/electron/**, references/openhands/helm/**, references/openhands/docker/**, references/openhands/vercel.json | packaging and deployment of the UI |
| references/openhands/src/stores/** (for example `goal-store.ts:19-33`) | Zustand UI state; no loop or ledger logic |
| references/openhands/src/api/cloud/**, src/api/backend-registry/**, src/api/automation-service/** | OpenHands Cloud and backend-selection integration, product specific |
| references/openhands/specs/canvas-extensions.md (design as a whole) | UI extension runtime; only its install-disabled, enable-separately rule (`:30-34`) is a pattern, not proposed here |
| references/openhands/docs/DefenseClaw.md | third-party Cisco tool integration guide; only its observe-before-block idea (`:139-142`) is noted, not proposed |
| references/openhands/tools/canvas_ui_tool.py | legacy no-op tool kept for old persisted conversations (`:1-20`); the client-tool form is O16 |
| references/openhands/.github/workflows/{docker,desktop-*,npm-publish,release,bump-chart,update-debian-snapshot}.yml and release-please configs | release pipeline of a different product |
| references/openhands/stryker.config.mjs | JS mutation config; our mutation gate is `mutant_gate.py` |

## Gaps

- No agent loop, condenser or context compaction in this repository. Searched `src/` file names (`ls src/api src/services src/stores src/lib`) and found only UI state stores and API adapters. The pin is the Agent Canvas frontend; `AGENTS.md:26-37` says the agent server, SDK, agents, tools and events live in `OpenHands/software-agent-sdk`. Runtime slices 1-2 get nothing from this pin.
- No sandbox or runtime implementation. `docs/architecture.md:14-19` states Agent Canvas does not execute agent actions or provide workspace isolation. Slice 3 gets nothing.
- No DAG or checkpoint engine, no message bus and no eval runner of the agent. The only mutation or eval config is JS (`stryker.config.mjs`); E2E suites under `tests/e2e/` were not opened. Slices 5, 6, 8 and 10 gain nothing.
- The event stream is consumed here (`src/api/event-service/`, three files) but its wire model is defined upstream (`custom-codereview-guide.md:133-149`). Event files were listed, not read.
- No coordinator or orchestrator prompt, no judge panel and no memory ledger. The only reviewer prompt is `custom-codereview-guide.md`, which targets one repo's PRs. The retrospective loop is absent.
- The licence-rules row says "UI-only fork; no agent runtime present". That is confirmed. The row names `OpenHands/agent-canvas`; `AGENTS.md:26-30` names `OpenHands/OpenHands`. Not resolved; no impact on MIT.
- Not opened: `.agents/skills/telemetry-analytics/`, `.agents/skills/desktop-electron/`, `src/extensions/`, `src/manifests/`, `examples/acp-docker/`, `docs/ACP_AGENTS.md` beyond its first 40 lines, `docs/SELF_HOSTING.md`.
- Cites to `.github/scripts/check_pr_description.py:317` and `:398-400` point at the function and the length rule; the label cross-check body between them was read only through its docstring.
