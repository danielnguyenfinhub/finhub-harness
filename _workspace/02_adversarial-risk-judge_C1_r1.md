TOTALS: UPHELD 14 / REJECTED 0 / UNVERIFIED 2 — round 1/3

# Adversarial verdict — adoption C1 (connector preflight), revision 0

- Audited file: _workspace/02_strategy-architect_C1.md (revision 0), `## Authority List` A1-A16
- Audited: 2026-10-03
- Changed claims re-audited this round: all (first round)
- Reference pin checked: `references/openharness` HEAD = 9b2efd7 (matches the design)

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | references/openharness/src/openharness/coordinator/agent_definitions.py:110; :962 | :110 `required_mcp_servers: list[str] \| None = None  # server name patterns that must be present` on `AgentDefinition`; :962-963 `if not agent.required_mcp_servers: return True` | — |
| A2 | UPHELD | agent_definitions.py:110 | same field, comment says "server name patterns" | Server granularity is plain at :110. The `mcp__fixture__ping` → `fixture` mapping is this design's own naming rule, checked by P-2/P-3, not taken from the reference |
| A3 | UPHELD | NET-NEW | — | Reason stated; `skills/finhub-harness/SKILL.md:91` does say "there is no `skills:` frontmatter field". P-3 grep `^## Required connectors` ≥ 1 can fail. Note: the second half of the reason ("chat/Cowork do not ship agent files") overstates `surfaces.md` §3b, which says "believed not applicable (unverified)" for chat and "uncommon; unverified" for Cowork. The first reason is enough on its own, so the claim stands; see A7 |
| A4 | UPHELD | agent_definitions.py:964 | :964-967 `return all(any(pattern.lower() in server.lower() for server in available_servers) for pattern in agent.required_mcp_servers)` | All-of is plain. Simulated in scratch: missing one of two rows → only that row is reported |
| A5 | UPHELD | NET-NEW (departs from :965) | :965 `pattern.lower() in server.lower()`, case-insensitive substring, as the claim says | Reason stated and correct. Scratch simulation: OpenHarness rule accepts `fixture`⊂`fixture2` and `git`⊂`github`; exact `mcp__<server>__` prefix rejects both. Test case 3 / M2 really fail under a substring rule. Segment rule also checked on real tool names with hyphens and `_` (`plugin_browser-use_browser-use`, `FINHUB-WHATSAPP-_0430111188`): they match their own prefix |
| A6 | UPHELD | NET-NEW (departs from :970-975) | :970-975 `filter_agents_by_mcp_requirements` returns `[a for a in agents if has_required_mcp_servers(...)]`, with no logging or message | Silent drop confirmed. "No caller" also confirmed: `grep -rn 'filter_agents_by_mcp_requirements\|has_required_mcp_servers' references/openharness` finds only the def lines :956, :970 and the internal call :975. `plugins/loader.py:583-612` parses the field but never filters on it. P-2 absent case (result must name `fixture` and `pinger`) can fail |
| A7 | UNVERIFIED | NET-NEW, backed by `skills/finhub-harness/references/surfaces.md` §3b `agents/*.md` row | §3b row: Chat "believed not applicable (unverified)", Cowork "uncommon; unverified" | The design choice (orchestrator owns a copied table) is sound, and P-3 can fail. But the claim gives as fact ("because chat/Cowork do not ship agent files") what the cited row says is a belief or uncommon and unverified. Reword to "may not ship agent files (§3b: unverified)". The builder may implement it; P-3 already makes a test that fails if the table is not emitted |
| A8 | UPHELD | NET-NEW | — | Reason stated (upstream filter has no spawn path, confirmed under A6). P-2 absent `agent_calls=0` can fail. Note for QA: the M1 "caught by" column is imprecise. With the Code bullet deleted, the chat bullet ("ask … do not stop without asking") under `claude -p` may also yield 0 Agent calls. M1 is still killed by the P-2 text criterion (`Missing connector … Nothing was started` disappears with the bullet), not by an Agent call appearing |
| A9 | UNVERIFIED | NET-NEW | — | Reason stated, but the named check does not test the claim. The P-2 present case uses one stub server with two tools (`echo`, `fail`), and Claude Code normally loads that few MCP tools eagerly, not as deferred names. If the fixture tools are not deferred, `agent_calls>=1` passes whether or not a deferred name counts as present. The check can fail, but not on the A9 assumption. To make it discriminating, QA must show that the fixture tools were deferred in the present run (from the stream-json init/system event, or by forcing tool search for that run), or record A9 as untested |
| A10 | UPHELD | NET-NEW, backed by `surfaces.md:139` (own file) | :139 Connectors / MCP row: chat "✓ but deferred: schema must be loaded first; failures only visible after a call (observed 2026-10-03, account-dependent)"; Cowork "unverified (believed ✓)" | Line supports the chat premise. Grep `Do not stop without asking` = 1 can fail (M3). The design itself states that P7 is manual and empty |
| A11 | UPHELD | NET-NEW, backed by `surfaces.md` §2 degradation rule 5 | :81 `5. **Say what was lost.** The final report notes which isolation or parallelism guarantees were not available.` | Grep `report that agent's phase as skipped` = 1 can fail |
| A12 | UPHELD | NET-NEW, reuses `orchestrator-template.md:82`, `:188`, `:247` | :82 Template A error table, "expired authentication … Do not retry"; :188 Template B, same; :247 Template C bullet, same | All three lines match. Grep `Present means listed, not working` = 1 can fail |
| A13 | UPHELD | references/openharness/LICENSE:1 | `MIT License` (:3 `Copyright (c) 2025 OpenHarness Contributors`) | Attribution suffix cites `:956`, which is the `has_required_mcp_servers` def. Upstream org unverified, accepted in the Pick (`_workspace/00_input/request.md:16`) |
| A14 | UPHELD | NET-NEW (repo fact) | — | `wc -c` = 0 for all four files, all git-tracked. The design's grep over `src tests scripts pyproject.toml` returns nothing (rc=1). Wider `\bfactory\b` grep over src/tests/scripts: only `*_factory` parameter names. `rglob("*.py")` tests (`test_sensitive_paths.py:798`, `test_router.py:101`) read file contents and gain nothing from empty files. Simulated: scratch copy of the repo with `src/master_finhub/factory/` removed, `PYTHONPATH=<scratch>/src` (import resolved to the scratch copy) → `891 passed, 10 skipped`, the stated baseline |
| A15 | UPHELD | NET-NEW (repo fact) | `pyproject.toml:19-20` `[tool.hatch.build.targets.wheel] packages = ["src/master_finhub"]`; `:16-17` only entry point is `master_finhub.cli:main` | `grep -c factory pyproject.toml` = 0 confirmed. Weak but not vacuous: it checks the premise, not a build |
| A16 | UPHELD | NET-NEW (repo fact) | `README.md:43` ends "…plus a \`factory/\` package that generates teams and skills in code." | The architect's grep pattern `factory/` also matches every `revfactory/` line, so it is noisy. A `\bfactory\b` grep (excluding references, _workspace*, caches) finds no other prose that claims a package. `.claude/agents/strategy-architect.md:11` and `runtime-builder.md:11` name slice 12 "factory" (superseded/deferred) as a slice, not a package. Note: `runtime-builder.md:11` says "deferred" where CLAUDE.md says "superseded"; that is outside C1 |

## Anchor lines the edits depend on (not Authority List rows; checked on request)

| edit | stated anchor | found | status |
|---|---|---|---|
| E1 | SKILL.md:91 starts `- Body: role, working principles…` | :91 exact | OK |
| E2 | SKILL.md:112 starts `- **Step 0 context check**:` | :112 exact | OK |
| E3 | SKILL.md:177 `- [ ] Orchestrator Step 0 distinguishes first run…` | :177 exact | OK |
| SKILL size | 194 → 197 | `wc -l` = 194 | OK |
| E4 | orchestrator-template.md:51 `3. If you run fresh…` inside the fence, before `### Step 1: Fix the task list` | :51 exact; Template A fence :17-:97; Step 1 header at :53 | OK |
| E5 B | :128-130, last line `the agent reads and reflects the existing results.` | :127 header, :128-130 body, :130 matches | OK |
| E5 C | :222 `Check whether \`_workspace/\` exists…` | :222 exact, inside fence :211-:249 | OK |
| E6 | surfaces.md:160 `\| 6 \| Packaging matches surface \|` | :160 exact; it is the last line of the file (160 lines) | OK |
| E7 | docs/surface-verification.md:22 `\| P6 \|` probe; :33 `\| P6 \| \| \|` | :22 and :33 exact | OK |
| E9 | README.md:43 | :43 exact | OK |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C1 | N/A: prose-only plugin change plus deletion of empty stubs; no pricing, returns, backtest, eval or verifier logic | N/A | N/A | N/A | N/A | N/A |

## Scratch work (outside the repo)

- `<scratchpad>/c1_rule.py`: OpenHarness rule against the C1 exact-prefix rule, with assertions for lookalike, all-of, empty and case-sensitivity cases, plus segment extraction from real tool names. All pass.
- `<scratchpad>/c1sim/`: repo copy without `references/`, `.git` or `.venv`, with the factory directory removed. Full pytest run: 891 passed, 10 skipped.
