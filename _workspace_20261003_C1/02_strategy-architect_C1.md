# Adoption design C1: connector preflight for generated agents (revision 4)

Goal: capability-adoption. Scope: factory. Item: C1 (OH8). Pick recorded in `_workspace/00_input/request.md` § Pick: OpenHarness accepted as MIT; the empty `src/master_finhub/factory/` stubs are deleted in this same adoption (separate claims A14-A16).

## Changes in revision 4

Extra round authorised by Daniel: 2026-10-03 (round 5).

Changed: A8 (row marked `CHANGED r4`), the mutation rows M1 and M1c (M1b withdrawn), and this note together with the revision 3 note below. No other claim was touched.

The r3 premise was false. QA's bullet-level mutant was a no-op: `grep -v '^- Claude Code:'` does not match the indented bullet, so the mutated file was byte-identical to the original. The bullet was never removed, so QA's "survived" result says nothing about it. r3 classified the mutant as equivalent on that basis, and that classification is withdrawn.

Simulated r4 on 2026-10-03 in scratch, on a fresh copy of the P-2 fixture at `<scratchpad>/c1-m1b/`:

- `grep -c '^ *- Claude Code:' .claude/skills/fixture-orchestrator/SKILL.md` gave **1** before the edit.
- I ran `sed -i '/^ *- Claude Code:/d'` on that file.
- The same grep then gave **0**.
- I ran the absent case twice with the P-2 recipe command. Both runs: `agent_calls=0`, `missing_lines=0`. The model said the preflight failed and did not spawn `pinger`, but it never printed the `Missing connector … Nothing was started.` line.

So the bullet-level M1 is **killed** by case 1, whose PASS condition requires that stop line. This matches what the judge saw.

## Changes in revision 3

Extra round authorised by Daniel: 2026-10-03 ("accept and add the stronger mutant and authorise round 4").

r3 added the whole-item-4 deletion as a mutant, now named **M1c**, and changed A8 to cite it. The r3 text that called the bullet-level deletion an equivalent mutant rested on a no-op QA mutation. It is withdrawn in revision 4 (see above).

M1c was simulated on 2026-10-03 in scratch (`<scratchpad>/c1-m1/`, a fresh copy of the P-2 fixture's `.claude/` and `absent.json`). Item 4 was removed from the copy's orchestrator: a grep for `Connector preflight|Missing connector|pinger | fixture` there returned 0. The agent's `## Required connectors` was kept. The absent case ran with the P-2 recipe (`ENABLE_TOOL_SEARCH=true claude -p "run the fixture harness" --strict-mcp-config --mcp-config absent.json --output-format stream-json --verbose --permission-mode bypassPermissions`) and once more without the bypass flag.

| run | agent_calls | missing_lines |
|---|---|---|
| with the bypass flag | 1 | 0 |
| without the bypass flag | 1 | 0 |

M1c is killed on both runs. The unmutated fixture under the same command (r2) gave `agent_calls=0` and the exact stop line.

## Changes in revision 2

Changed claims: A3 and A9 (rows marked `CHANGED r2`). Everything else, including the r1 text below, is unchanged.

- **A3:** "do not ship agent files" now reads "may not ship agent files (§3b: unverified)".
- **A9:** P-2 now establishes deferral from the start of the run, using the init event. It no longer relies on a ToolSearch call made later. The FAIL rule is independent of `fixture_was_deferred`. P-2's pass table and the A9 row now give the same rule:

  | `deferred_from_start` | `agent_calls = 0` or a `Missing connector` line | verdict |
  |---|---|---|
  | true | yes | **FAIL** |
  | true | no | **PASS** (`fixture_was_deferred >= 1` is extra evidence only) |
  | false (or the CLI fallback was used) | any | **UNTESTED** |

  `deferred_from_start` is true when `ENABLE_TOOL_SEARCH=true` and the init `tools` holds both `ToolSearch` and at least one `mcp__fixture__*` name.

How r2 was checked, on 2026-10-03, in scratch only (`<scratchpad>/c1-fixture`, `<scratchpad>/a9_verdict.sh`):

- **Live fixture runs.** I built the P-2 fixture in scratch: agent `pinger` with `## Required connectors` set to `fixture`, and an orchestrator whose Step 0 is the E4 item 4 block from this file, with the row `| pinger | fixture |`. I ran it with the real `claude -p` and `ENABLE_TOOL_SEARCH=true`.
  - **present.json:** the main thread made one `Agent` call. Inside the sub-agent: `ToolSearch` with `select:mcp__fixture__echo`, then `mcp__fixture__echo`, which returned `ping`. The result reports that the harness passed.
  - **absent.json:** 0 Agent calls. The result was exactly `Missing connector fixture for agent pinger. Attach or authorise it, then run again. Nothing was started.`
- **The P-2 verdict script, run on four streams:**

  | stream | verdict | exit | values |
  |---|---|---|---|
  | synthetic stop-in-Step-0 (the real deferred-mode init line from `present.jsonl`, then only a `Missing connector` text and result; no ToolSearch, no Agent) | FAIL | 1 | `deferred_from_start=true agent_calls=0 missing_lines=1 fixture_was_deferred=0` |
  | live `present.jsonl` | PASS | 0 | `deferred_from_start=true agent_calls=1 missing_lines=0 fixture_was_deferred=1` |
  | `c1sim/run_false.jsonl` (`ENABLE_TOOL_SEARCH=false`) | UNTESTED | 2 | |
  | `c1sim/run_true.jsonl` | FAIL | 1 | |

- **On `run_true.jsonl`.** The judge asked for it to show PASS. It cannot. It is the r1 init probe ("Reply with only the word ok"), not a fixture-harness run, so it has 0 Agent calls by construction. Scoring it FAIL is correct. The PASS evidence is the live `present.jsonl` above, a real fixture-harness run in deferred mode.
- **Bug found and fixed while re-checking.** r1's `fixture_was_deferred` jq read `tool_use_result.matches`, and that field is absent on sub-agent tool results: it returned 0 on the live run even though the sub-agent did load the tool through ToolSearch. r2 counts `tool_reference` items in tool results instead, and that returns 1. It is extra evidence only, so the bug could not have affected a verdict under the r2 rule.

## Changes in revision 1

Changed claims: A7, A9 (rows marked `CHANGED r1`). Disputed, not changed: the judge asked for SKILL.md's expected length to be 198. A simulation on a scratch copy says otherwise. It inserted the three E1-E3 blocks extracted from this file at lines 91, 112 and 177 into `skills/finhub-harness/SKILL.md` (194 lines), and `wc -l` gave **197**. Each block is a single line. My r0 handback note ("E1-E3 add 4 lines") was the error and the judge followed it. The Proof row stays 197, with the simulation noted. Text changed only where it supports those items: Design § Behaviour item 2 (A7); P-2 commands, checks and pass table (A9); the Does-not-cover bullet on deferred listings (A9). All other claims are byte-identical to r0.

I simulated A9 on 2026-10-03 in scratch (`<scratchpad>/c1sim`, nothing committed). `claude` 2.1.288 is authenticated in this container.

- With `ENABLE_TOOL_SEARCH=true` and the stub registered as `fixture`, the init event's `tools` held `ToolSearch`, `mcp__fixture__echo` and `mcp__fixture__fail`.
- Asked to call `mcp__fixture__echo`, the model first called `ToolSearch` with `select:mcp__fixture__echo`. That tool result carried `tool_use_result.matches == ["mcp__fixture__echo"]` and `total_deferred_tools: 184`. Only then did it call `mcp__fixture__echo`, which returned `ping`.
- With `ENABLE_TOOL_SEARCH=false`, `ToolSearch` was absent from init `tools`.

So the init `tools` list alone cannot prove deferral, because it names the fixture tools in both modes. The deferral proof is the ToolSearch result that lists `mcp__fixture__echo` among the deferred matches. Side finding: `--strict-mcp-config` did not stop plugin-provided MCP servers from loading. None of them has the `fixture` prefix, so the absent case is unaffected.

Baseline measured 2026-10-03 before any edit: `.venv/bin/python -m pytest -q` → `891 passed, 10 skipped`; `bash scripts/package-plugin.sh` exit 0; `bash scripts/check-harness-refs.sh` exit 0 (40 PASS lines); Hangul count 0 in every target file.

## Source

Backlog row (`_workspace/01b_capability-scout_backlog.md:48`, detail `:63-73`): generated agents declare the connectors/MCP servers they need; the orchestrator preflights them before spawning. Score 0.94. Risk named there: deferred tool listings could hide a present connector, so chat/Cowork warn and ask while Code hard-stops.

Port-map row OH8 (`_workspace/01_reference-miner_openharness_portmap.md:33`): loader at `coordinator/agent_definitions.py:695`, filter `has_required_mcp_servers` at `:956`. Re-opened at pinned commit `9b2efd7`:

| line | what it does |
|---|---|
| `agent_definitions.py:110` | `AgentDefinition.required_mcp_servers: list[str] \| None`, commented "server name patterns that must be present". The requirement is per agent and at server granularity, not per tool. |
| `:724` | loader docstring lists `requiredMcpServers` / `required_mcp_servers` as a frontmatter field. |
| `:848-851` | loader reads that frontmatter key (camelCase first, snake_case fallback). |
| `:962-963` | an agent with no requirement passes. |
| `:964-967` | every declared pattern must match some available server (`all(any(...))`). |
| `:965` | matching is case-insensitive **substring** (`pattern.lower() in server.lower()`). |
| `:970-975` | `filter_agents_by_mcp_requirements` returns only agents whose servers are available. Unavailable agents are **dropped without a message**. |

Observation from re-opening, for the judge: `grep -rn 'filter_agents_by_mcp_requirements\|has_required_mcp_servers' references/openharness --include=*.py` finds no call site outside the definitions themselves. OpenHarness defines the filter but does not wire it in. We adopt the data shape and the all-of rule, not a wired behaviour.

Licence: `references/openharness/LICENSE:1` reads `MIT License`. The upstream org is unverified (backlog `:165`); Daniel accepted MIT in the Pick.

## Target

Plugin skill prose (factory). No Python is added. One deletion in the runtime tree.

| # | file | change |
|---|---|---|
| E1 | `skills/finhub-harness/SKILL.md` | Step 3: one new bullet after line 91 |
| E2 | `skills/finhub-harness/SKILL.md` | Step 5: one new bullet after line 112 |
| E3 | `skills/finhub-harness/SKILL.md` | Deliverable checklist: one new item after line 177 |
| E4 | `skills/finhub-harness/references/orchestrator-template.md` | Template A Step 0: new item 4 after line 51 (inside the fenced template) |
| E5 | `skills/finhub-harness/references/orchestrator-template.md` | Template B Step 0 (line 128-130) and Template C Step 0 (line 222): one sentence each |
| E6 | `skills/finhub-harness/references/surfaces.md` | §6 checklist: row 7 after line 160 |
| E7 | `docs/surface-verification.md` | probe P7 after line 22; result row after line 33 |
| E8 | `src/master_finhub/factory/{__init__,evolver,skill_compiler,team_generator}.py` and the directory | delete |
| E9 | `README.md` | line 43: drop the clause that claims a `factory/` package |

Not touched: `tests/` (including `tests/mcp_stub_server.py`), `scripts/`, `.claude/`, `CLAUDE.md` (the orchestrator adds the change-history row at Phase 4), `qa-agent-guide.md`.

## Design

### Behaviour, in one place

1. **Declaration.** An agent that cannot work without an MCP server/connector carries a body section `## Required connectors`, one server per line. The server is written as the segment between `mcp__` and the next `__` in its tool names (`mcp__crm__search` → `crm`; a plugin server is written as Claude Code shows it, e.g. `plugin_foo_bar`). Body, not frontmatter (A3). Server granularity, not tool (A2): the backlog's `mcp__fixture__ping` becomes connector `fixture`.
2. **Copy into the orchestrator.** Step 5 copies every declared line into one agent → connector table in the orchestrator's Step 0. The orchestrator owns the check because chat and Cowork may not ship agent files (`surfaces.md` §3b row `agents/*.md`: chat "believed not applicable (unverified)", Cowork "uncommon; unverified"). The table therefore lives in the skill that runs on every surface (A7).
3. **Presence test.** A connector is present when at least one tool whose name begins with exactly `mcp__<server>__` appears in the tool list, deferred listings included (A5, A9). Exact prefix, not OpenHarness's substring (A5).
4. **All-of.** Every row must be present; an agent with no rows is not checked (A1, A4).
5. **Claude Code: hard stop.** If any row is absent, the orchestrator makes no Agent, Workflow, SendMessage or TaskCreate call. It replies with one line per missing row naming connector and agent, and says nothing was started (A6, A8).
6. **Chat / Cowork: warn and ask.** First try the surface's tool-search step for the server name, if the surface has one. If it is still absent, name it in the same form and ask: attach and continue, continue without it (that agent's phase is reported as skipped), or stop. It never stops on its own (A10, A11).
7. **Presence is not health.** The check does not cover auth or a lapsed connection. Those fail on the first real call and follow each template's existing no-retry rule for expired authentication (A12).

### E1: `SKILL.md` Step 3. Insert after line 91

Anchor (line 91, starts with): `- Body: role, working principles with their reasons, input/output rules, error handling, collaboration.`

Insert as a new bullet directly below it:

```markdown
- Connectors: an agent that cannot do its job without an MCP server or connector gets a `## Required connectors` section in its body, one server per line, written as the segment between `mcp__` and the next `__` in its tool names (`mcp__crm__search` → `crm`). Leave the section out when the agent needs none. Step 5 copies these lines into the orchestrator's preflight table, so a missing connector stops the run before anyone is spawned instead of failing on the agent's first call. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:956 (MIT))
```

### E2: `SKILL.md` Step 5. Insert after line 112

Anchor (line 112, starts with): `- **Step 0 context check**: no \`_workspace/\` → fresh run;`

Insert directly below it:

```markdown
- **Connector preflight** (only when an agent has `## Required connectors`): Step 0 ends with the preflight item from Template A Step 0 in `references/orchestrator-template.md`, holding one agent → connector row per declared line. On Claude Code a missing connector stops the run before any spawn; on chat and Cowork the orchestrator warns and asks instead, because connector listings there are deferred and an absent name is not proof (`references/surfaces.md` §4).
```

### E3: `SKILL.md` Deliverable checklist. Insert after line 177

Anchor (line 177): `- [ ] Orchestrator Step 0 distinguishes first run, follow-up and partial re-run (and \`resumeFromRunId\` for Workflow mode).`

Insert:

```markdown
- [ ] Every `## Required connectors` line in an agent file has a row in the orchestrator's connector preflight table, and every row has a matching agent line.
```

### E4: `orchestrator-template.md` Template A Step 0. Insert after line 51

Anchor (line 51): `3. If you run fresh, receive a new \`runId\` and record it in \`_workspace/run_meta.json\`.`

Insert between line 51 and the blank line before `### Step 1: Fix the task list` (still inside the fenced template):

```markdown
4. Connector preflight. Skip this item if the table says "none". Run it before any agent, Workflow, message or task call.

   | Agent | Required connector |
   |-------|--------------------|
   | {agent} | {server, as in `mcp__{server}__*`} |

   A connector counts as present when your tool list, deferred listings included, has at least one tool whose name begins with `mcp__{server}__`.
   - Claude Code: if any row is absent, make no further calls. Reply with one line per absent row: `Missing connector {server} for agent {agent}. Attach or authorise it, then run again. Nothing was started.`
   - Claude chat or Cowork: an attached connector can stay hidden until its schema is loaded, so absence is not proof. Search for the server name with the tool-search step if there is one. If it is still absent, name it in the same form and ask whether to attach it and continue, continue without it (report that agent's phase as skipped), or stop. Do not stop without asking.
   - Present means listed, not working. An auth or connection error on the first real call is handled by the error table below; do not retry it. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:956 (MIT))
```

### E5: Templates B and C Step 0

Template B anchor (lines 128-130, last line): `the agent reads and reflects the existing results.` Append on the next line:

```markdown
Then run the connector preflight from Template A Step 0, item 4, before launching any agent.
```

Template C anchor (line 222): `Check whether \`_workspace/\` exists to decide whether to run for the first time, re-run only part of it, or run fresh.` Append on the next line:

```markdown
Then run the connector preflight from Template A Step 0, item 4, before spawning any sub-agent.
```

The mixed-mode section has no Step 0 of its own; it inherits from whichever template runs first. No edit there.

### E6: `surfaces.md` §6. Append row 7 after line 160

Anchor (line 160, starts with): `| 6 | Packaging matches surface |`

```markdown
| 7 | Connector preflight | Every agent's `## Required connectors` line has a row in the orchestrator's Step 0 preflight table; the Code branch stops before any spawn; the chat/Cowork branch warns and asks and never stops on its own |
```

### E7: `docs/surface-verification.md`. Probe P7

Anchor (line 22, starts with): `| P6 | \`harness retrospective:`. Insert below it:

```markdown
| P7 | Upload a one-agent fixture harness whose agent lists `fixture` under `## Required connectors`, attach no such connector, then send `run the fixture harness` | The orchestrator names `fixture` and the agent, then asks whether to attach, continue without, or stop; it does not stop by itself | `surfaces.md` §4 Connectors row and §6 check 7: on chat and Cowork the preflight warns and asks |
```

Anchor (line 33): `| P6 | | |`. Insert below it: `| P7 | | |`

This is the only way to observe the chat/Cowork branch. It stays empty until Daniel runs it; the design does not claim that branch was tested.

### E8: delete the factory stubs (separate claims A14-A16)

Facts checked before designing:

- `wc -c src/master_finhub/factory/*.py` → all four files are 0 bytes; no `__pycache__` inside.
- `grep -rn 'master_finhub.factory\|from .factory\|import factory\|team_generator\|skill_compiler\|evolver' src tests scripts pyproject.toml` → no matches. Nothing imports them.
- `pyproject.toml` packages `src/master_finhub` as a whole (`[tool.hatch.build.targets.wheel] packages = ["src/master_finhub"]`); no entry point or package list names `factory`.
- The only prose that names the package is `README.md:43`. `CLAUDE.md` says "slice 12 (factory) is superseded", which stays true.

Action: `git rm src/master_finhub/factory/__init__.py src/master_finhub/factory/evolver.py src/master_finhub/factory/skill_compiler.py src/master_finhub/factory/team_generator.py`, then confirm the directory is gone (`rmdir` if git left it).

### E9: `README.md:43`

Anchor (line 43, ends with): `a loopback SSE server and deterministic evals, plus a \`factory/\` package that generates teams and skills in code.`

Replace the clause `, plus a \`factory/\` package that generates teams and skills in code.` with `. Teams and skills are generated by the \`finhub-harness\` skill, not by Python code.`

No test changes are needed. No existing test is modified.

## Proof

All commands run from `/home/user/finhub-harness`.

### P-1 Insertions landed (greps, exact expected counts)

| check | command | expected |
|---|---|---|
| E1 | `grep -c '^- Connectors: an agent that cannot do its job' skills/finhub-harness/SKILL.md` | 1 |
| E2 | `grep -c '^- \*\*Connector preflight\*\*' skills/finhub-harness/SKILL.md` | 1 |
| E3 | `grep -c 'has a row in the orchestrator.s connector preflight table' skills/finhub-harness/SKILL.md` | 1 |
| E1+E4 attribution | `grep -c 'adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:956 (MIT)' skills/finhub-harness/SKILL.md skills/finhub-harness/references/orchestrator-template.md` | `SKILL.md:1`, `orchestrator-template.md:1` |
| E4 | `grep -c '^4. Connector preflight' skills/finhub-harness/references/orchestrator-template.md` | 1 |
| E4 order | `awk '/^## Template A/{a=1} a&&/^4. Connector preflight/{print NR; exit}' …` returns a line number below `grep -n '^3. If you run fresh' …` and above `grep -n '^### Step 1: Fix the task list' …` | ordered |
| E4 chat branch | `grep -c 'Do not stop without asking' skills/finhub-harness/references/orchestrator-template.md` | 1 |
| E4 skipped | `grep -c "report that agent's phase as skipped" skills/finhub-harness/references/orchestrator-template.md` | 1 |
| E4 health | `grep -c 'Present means listed, not working' skills/finhub-harness/references/orchestrator-template.md` | 1 |
| E4 stop line | `grep -c 'Missing connector {server} for agent {agent}' skills/finhub-harness/references/orchestrator-template.md` | 1 |
| E5 | `grep -c 'Then run the connector preflight from Template A Step 0, item 4' skills/finhub-harness/references/orchestrator-template.md` | 2 |
| E6 | `grep -c '^| 7 | Connector preflight |' skills/finhub-harness/references/surfaces.md` | 1 |
| E7 | `grep -c '^| P7 |' docs/surface-verification.md` | 2 |
| E8 | `test ! -e src/master_finhub/factory && echo gone` | `gone` |
| E8 | `grep -rn 'master_finhub.factory\|master_finhub/factory' src tests scripts pyproject.toml README.md` | no output |
| E9 | `grep -c 'factory/. package' README.md` | 0 |
| SKILL size | `wc -l < skills/finhub-harness/SKILL.md` | 197 (194 + 3: E1, E2 and E3 are one line each; simulated r1 on a scratch copy), still under 500 |

### P-2 Behaviour on Claude Code (fixture harness, live)

Fixture lives in the scratchpad only; nothing is committed. `$F` = `<scratchpad>/c1-fixture`.

- `$F/.claude/agents/pinger.md`: frontmatter `name: pinger`, `description: Calls the fixture echo tool once and reports the reply.`, and a body that includes:
  ```
  ## Required connectors
  fixture
  ```
  The task: call `mcp__fixture__echo` with `{"text":"ping"}` and return the reply. The backlog's `mcp__fixture__ping` maps to connector `fixture` (server granularity, A2). The existing stub `tests/mcp_stub_server.py` exposes `echo` and `fail`, so it is reused unchanged and no `ping` tool is added.
- `$F/.claude/skills/fixture-orchestrator/SKILL.md`: Template C instantiated from the edited `orchestrator-template.md`. Step 0 includes item 4 copied verbatim, with the table row `| pinger | fixture |`. Step 2 spawns `pinger` with the Agent tool.
- `$F/absent.json`: `{"mcpServers":{}}`
- `$F/present.json`: `{"mcpServers":{"fixture":{"command":"/home/user/finhub-harness/.venv/bin/python","args":["/home/user/finhub-harness/tests/mcp_stub_server.py"]}}}`

Run each case from inside `$F`:

```bash
cd "$F" && ENABLE_TOOL_SEARCH=true claude -p "run the fixture harness" --strict-mcp-config --mcp-config present.json \
  --output-format stream-json --verbose --permission-mode bypassPermissions > present.jsonl
```

`ENABLE_TOOL_SEARCH=true` forces MCP tools to be deferred: listed by name, with the schema loaded only through `ToolSearch`. This is the condition A9 is about. Without it, the fixture's two tools may load eagerly, and a PASS would say nothing about deferred names.

Run the absent case the same way, so that both cases see the same deferred listing:

```bash
cd "$F" && ENABLE_TOOL_SEARCH=true claude -p "run the fixture harness" --strict-mcp-config --mcp-config absent.json \
  --output-format stream-json --verbose --permission-mode bypassPermissions > absent.jsonl
```

Absent-case check:

```bash
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name' "$F/absent.jsonl" | grep -cE '^(Agent|Task)$'   # expect 0
jq -r 'select(.type=="result") | .result' "$F/absent.jsonl"
```

Present-case check, the A9 verdict script (`a9_verdict.sh <present.jsonl>`; exit 0 PASS, 1 FAIL, 2 UNTESTED):

```bash
f=$1
ts=$(jq -r 'select(.type=="system" and .subtype=="init") | ((.tools|index("ToolSearch"))!=null) and ((.tools|map(select(startswith("mcp__fixture__")))|length)>0)' "$f")
ac=$(jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name' "$f" | grep -cE '^(Agent|Task)$')
miss=$(jq -r 'select(.type=="result") | .result' "$f" | grep -c 'Missing connector')
dfr=$(jq -r 'select(.type=="user") | .message.content[]? | select(.type=="tool_result") | .content | arrays | .[] | select(.type=="tool_reference") | .tool_name' "$f" | grep -c '^mcp__fixture__')
echo "deferred_from_start=$ts agent_calls=$ac missing_lines=$miss fixture_was_deferred=$dfr"
if [ "$ts" != "true" ]; then echo "A9 UNTESTED"; exit 2; fi
if [ "$ac" -eq 0 ] || [ "$miss" -gt 0 ]; then echo "A9 FAIL"; exit 1; fi
echo "A9 PASS"
```

What each value means:

- `deferred_from_start=true`: under `ENABLE_TOOL_SEARCH=true`, the init event lists `ToolSearch` and the fixture tool names. The fixture tools are therefore deferred names from turn one: their schemas must be loaded through `ToolSearch`, as the r1 probe showed.
- Under that condition, a preflight that treats deferred names as absent stops in Step 0. That gives `agent_calls=0` and a `Missing connector` line, so the result is **FAIL**, whatever `fixture_was_deferred` says.
- `fixture_was_deferred` counts `tool_reference` results for `mcp__fixture__*`, from the main thread or a sub-agent. It is extra evidence for a PASS only, and it never decides the verdict.

| case | PASS when | FAIL when | UNTESTED when |
|---|---|---|---|
| absent | `agent_calls=0`, and the result contains `Missing connector fixture for agent pinger` and `Nothing was started` | any Agent/Task tool_use, or a result that does not name both `fixture` and `pinger` | never; this case does not depend on deferral |
| present (A9) | `deferred_from_start=true`, `agent_calls>=1`, no `Missing connector` line, and the result contains the echo reply `ping` (`fixture_was_deferred>=1` recorded as extra evidence) | `deferred_from_start=true` and (`agent_calls=0` or any `Missing connector` line) | `deferred_from_start=false`, or the CLI fallback below was used |

If `claude -p` cannot authenticate in the container, QA records the CLI error verbatim. It then runs the absent case as a cold sub-agent instead: the prompt is the fixture orchestrator's text plus "run the fixture harness", and this session has no `mcp__fixture__` tools. QA counts that sub-agent's Agent calls and labels the result **weaker: same-session, absent case only**. The present case is then reported as not run, and A9 is recorded **untested**. Neither is reported PASS.

### P-3 The factory emits it (cold generation)

A cold sub-agent gets only `skills/finhub-harness/` and the prompt `build a Mode C harness on Claude Code with one agent that looks up a contact through the crm connector`. It writes into a scratch directory. PASS when, in that output:

- `grep -c '^## Required connectors' .claude/agents/*.md` totals ≥ 1, with a line reading `crm`;
- the orchestrator `SKILL.md` contains `Connector preflight` and a table row containing both the agent name and `crm`;
- the orchestrator contains `Missing connector`.

FAIL when any of these is absent.

### P-4 Prose gates

| gate | command | expected |
|---|---|---|
| attribution | P-1 attribution row | 1 per file, MIT, cites `:956` |
| no 8-word verbatim run | script below | `0` for every file |
| Hangul | `LC_ALL=C.UTF-8 grep -cP '[\x{AC00}-\x{D7A3}]' skills/finhub-harness/SKILL.md skills/finhub-harness/references/orchestrator-template.md skills/finhub-harness/references/surfaces.md docs/surface-verification.md README.md` | every count `0` |
| packager | `bash scripts/package-plugin.sh; echo $?` | `0` |
| refs | `bash scripts/check-harness-refs.sh; echo $?` | `0`, still 40 PASS lines, 0 FAIL |
| pytest | `.venv/bin/python -m pytest -q \| tail -1` | `891 passed, 10 skipped` (unchanged; the deleted stubs had no tests) |
| no test edits | `git diff --stat -- tests/` | empty |

8-word run check (source = the whole pinned OpenHarness file):

```bash
python3 - <<'EOF'
import re
w = lambda s: re.findall(r"[a-z0-9_]+", s.lower())
src = w(open("references/openharness/src/openharness/coordinator/agent_definitions.py").read())
grams = {tuple(src[i:i+8]) for i in range(len(src) - 7)}
for f in ["skills/finhub-harness/SKILL.md", "skills/finhub-harness/references/orchestrator-template.md",
          "skills/finhub-harness/references/surfaces.md", "docs/surface-verification.md"]:
    t = w(open(f).read())
    hits = [" ".join(t[i:i+8]) for i in range(len(t) - 7) if tuple(t[i:i+8]) in grams]
    print(f, len(hits), hits[:3])
EOF
```

## Test plan

**Unit-level cases (P-2 fixture variants; QA runs at least the first three):**

1. Absent server on Code → 0 Agent calls, stop line names `fixture` and `pinger`.
2. Present server on Code → ≥1 Agent call, echo reply returned.
3. Lookalike server: `present.json` with the server renamed `fixture2` → still a stop. This proves the match is the exact prefix `mcp__fixture__`, not a substring (A5). OpenHarness's substring rule at `:965` would accept it.
4. No requirement: the table says "none" → preflight skipped, the agent is spawned with `absent.json`.
5. Two rows, one present: the stop message names only the missing row, and there are 0 Agent calls (all-of, A4).

**Must still pass:** full `pytest` (891 passed, 10 skipped); `scripts/package-plugin.sh` exit 0; `scripts/check-harness-refs.sh` exit 0; the v1-artefact grep inside the packager.

**Mutation targets** (applied by QA on a scratch copy of the fixture orchestrator or the plugin; each must turn a PASS into a FAIL):

| # | mutation | caught by |
|---|---|---|
| M1 | delete only the Claude Code bullet of item 4: `sed -i '/^ *- Claude Code:/d' <fixture orchestrator SKILL.md>`. Check first: `grep -c '^ *- Claude Code:'` is 1 before the edit and 0 after (a count still at 1 means the mutation did not apply, and the run is void) | case 1 (absent): the stop line `Missing connector fixture for agent pinger … Nothing was started.` is missing from the result. Killed in r4 simulation, 2/2 runs (`agent_calls=0`, `missing_lines=0`) |
| M1c | delete ALL of item 4 (first line, table, presence rule and all three bullets) in the fixture orchestrator. Check first: `grep -c 'Connector preflight'` is 1 before the edit and 0 after | case 1 (absent): an Agent call appears (`agent_calls>=1`) and the `Missing connector` line is absent. Killed in r3 simulation, 2/2 runs |
| M2 | change `begins with \`mcp__{server}__\`` to `contains {server}` | case 3: `fixture2` passes and is spawned |
| M3 | in the chat/Cowork bullet, replace the ask-and-do-not-stop sentences with "stop" | P-1 `E4 chat branch` grep 1 → 0 |
| M4 | remove the E5 sentence from Template C | P-1 E5 count 2 → 1 |
| M5 | restore an empty `src/master_finhub/factory/__init__.py` | P-1 E8 `test ! -e` fails |
| M6 | drop the attribution suffix from E4 | P-1 attribution count for `orchestrator-template.md` 1 → 0 |

## Does not cover

- **Health, auth and quota.** Presence only. A listed connector with expired auth passes the preflight and fails on the first call (A12). That is the existing error policy's job.
- **Chat/Cowork behaviour is unverified.** The warn-and-ask branch is prose that cannot be run from this container. P7 in `docs/surface-verification.md` is the check, and it stays empty until Daniel runs it.
- **Deferred listings on Code.** This session shows MCP tools as a deferred-name list. The design counts a deferred name as present (A9). A server that "failed to connect" or "requires authentication" is absent from that list, so on Code it stops. That stop is correct (the run would fail anyway), but the message says "attach or authorise" rather than diagnosing which.
- **False negative by naming.** If the factory writes a server segment that differs from the session's real prefix (e.g. `google_drive` vs `Google_Drive`), Code stops falsely. Matching is exact and case-sensitive by design (A5); the fix is to copy the segment from a real tool name. A case-insensitive match would be cheap to add if this bites.
- **Existing generated harnesses** are not back-filled. The preflight applies to harnesses built or extended after this change.
- **Connector-free agents** are untouched.
- **Tool-level requirements.** Only the server is checked, not that a specific tool (e.g. `ping`) exists on it.
- **`README.md:45`** still says the team has five agents (it has six). That is outside C1 and left for a docs pass.
- **OpenHarness wiring.** The upstream filter has no caller (see Source), so there is no upstream runtime behaviour to match beyond the data shape and the all-of rule.

## Authority List

| id | claim | evidence | target |
|---|---|---|---|
| A1 | Connector requirements are declared per agent as a list, and an agent with no list is not checked | references/openharness/src/openharness/coordinator/agent_definitions.py:110; references/openharness/src/openharness/coordinator/agent_definitions.py:962 | E1, E4 |
| A2 | Requirements are at server granularity (server names), not individual tools; `mcp__fixture__ping` is declared as `fixture` | references/openharness/src/openharness/coordinator/agent_definitions.py:110 | E1, P-2 |
| A3 | CHANGED r2 — Requirements go in an agent body section `## Required connectors`, not in frontmatter as OpenHarness does (`:848-851`) | NET-NEW — the repo's agent files carry only Claude Code frontmatter (`SKILL.md:91` already rules out a `skills:` field), and chat/Cowork may not ship agent files (`surfaces.md` §3b: unverified), so an unknown frontmatter key may never be read there. Verification that can fail: P-3 grep `^## Required connectors` ≥ 1 in a cold-generated agent | E1 |
| A4 | Every declared server must be present (all-of); one missing row blocks the run | references/openharness/src/openharness/coordinator/agent_definitions.py:964 | E4 |
| A5 | Presence is an exact `mcp__<server>__` prefix match on tool names, case-sensitive, not OpenHarness's case-insensitive substring (`:965`) | NET-NEW — a substring rule lets server `fixture2` or `github` satisfy `fixture` or `git`, a false pass. Verification that can fail: test case 3 / mutation M2 | E4 |
| A6 | A missing connector stops the run with a message naming connector and agent, instead of silently dropping the agent as `filter_agents_by_mcp_requirements` does (`:970-975`) | NET-NEW — silent loss is the failure C1 targets (backlog `:48`); the upstream filter also has no caller in the pinned repo. Verification that can fail: P-2 absent case, the result must name `fixture` and `pinger` | E4 |
| A7 | CHANGED r1 — The check runs in the orchestrator from a table copied out of the agent files, because chat/Cowork may not ship agent files (`surfaces.md` §3b: chat "believed not applicable (unverified)", Cowork "uncommon; unverified"); the orchestrator is the one artefact present on every surface | NET-NEW — design choice backed by this repo's own `skills/finhub-harness/references/surfaces.md` §3b (`agents/*.md` row), which marks the point unverified; not a reference. Verification that can fail: P-3 grep for the agent+`crm` table row in the generated orchestrator; SKILL checklist E3 | E2, E3, E4 |
| A8 | CHANGED r4 — On Claude Code the preflight runs in Step 0 before any Agent, Workflow, SendMessage or TaskCreate call, so a stop means 0 spawns | NET-NEW — the upstream filter is not wired to any spawn path, so there is no reference for its timing. Verification that can fail: P-2 absent case `agent_calls=0`; mutation M1c (delete all of item 4), which must make case 1 show `agent_calls>=1` and no `Missing connector` line (killed 2/2, r3); and mutation M1 (delete the Claude Code bullet), which must remove the stop line from case 1 (killed 2/2, r4) | E4, E5 |
| A9 | CHANGED r2 — A deferred tool-name listing counts as present | NET-NEW — on Claude Code, MCP tools can appear as names before their schemas load. Simulated: with `ENABLE_TOOL_SEARCH=true`, `mcp__fixture__echo` had to be loaded through `ToolSearch`. Treating deferred names as absent would false-stop. Verification that can fail: P-2 present case with `ENABLE_TOOL_SEARCH=true`, scored by `a9_verdict.sh`. FAIL when `deferred_from_start=true` and (`agent_calls=0` or a `Missing connector` line), whatever `fixture_was_deferred` says. PASS when `deferred_from_start=true`, `agent_calls>=1` and there is no such line. UNTESTED only when `deferred_from_start=false` or the CLI fallback was used. Checked r2: a synthetic Step-0 stop scores FAIL; the live fixture run scores PASS | E4 |
| A10 | On chat and Cowork the preflight searches with the surface's tool-search step, then warns and asks (attach / continue without / stop) and never stops on its own | NET-NEW — this repo observed connectors on chat listed but deferred, with failures visible only after a call (`skills/finhub-harness/references/surfaces.md:139`, our file, not a reference). Verification that can fail: P7 in `docs/surface-verification.md` (manual) and the P-1 grep `Do not stop without asking` = 1 | E4, E7 |
| A11 | "Continue without it" reports that agent's phase as skipped, never silently passed | NET-NEW — this follows the existing rule that the final report says what was lost (`surfaces.md` §2 degradation rule 5). Verification that can fail: P-1 grep `report that agent's phase as skipped` = 1 | E4 |
| A12 | Presence is not health: auth or connection errors on the first call go to each template's existing no-retry error rule | NET-NEW — reuses `orchestrator-template.md:82`, `:188` and `:247` (expired authentication → do not retry). Verification that can fail: P-1 grep `Present means listed, not working` = 1 | E4 |
| A13 | The adaptation is MIT and carries a one-line attribution in each prose file that adapts it | references/openharness/LICENSE:1 | E1, E4 |
| A14 | The four `src/master_finhub/factory/*.py` files are zero bytes and nothing in `src`, `tests`, `scripts` or `pyproject.toml` imports them, so deleting them changes no behaviour | NET-NEW — repository fact, not a reference pattern; measured with `wc -c` and the E8 grep. Verification that can fail: pytest stays `891 passed, 10 skipped`; E8 grep empty | E8 |
| A15 | The wheel config packages `src/master_finhub` as a whole and names no `factory` subpackage, so the build is unaffected | NET-NEW — repository fact (`pyproject.toml` `[tool.hatch.build.targets.wheel]`). Verification that can fail: `grep -c factory pyproject.toml` = 0 | E8 |
| A16 | `README.md:43` is the only prose claiming a `factory/` package and is corrected in the same change | NET-NEW — repository fact from `grep -rn 'factory/' --exclude-dir=references --exclude-dir=_workspace*`. Verification that can fail: P-1 E9 grep = 0 | E9 |
