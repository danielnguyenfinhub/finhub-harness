TOTALS: UPHELD 78 / REJECTED 0 / UNVERIFIED 0 — round 2/3

# Adversarial verdict — slices revision 2 (slices 8-11, slice 12 deferred)

- Audited file: _workspace/02_strategy-architect_slices.md (revision 2, 743 lines)
- Audited: 2026-10-02 AEST
- Scope: Authority List A1-A78 (78 rows). Round-1 F1/F2 are now rowed as A74-A77 and are no longer counted separately.
- Changed claims re-audited this round: A3, A39, A49 (changed); A73-A78 (added). I re-audited these independently and did not rely on the architect's "Changes in revision 2" summary.
- Unchanged rows carried forward as UPHELD. I spot-checked 29 cited lines from them, and all still match (listed below).
- Method: I opened every cited `references/` line at ±5 lines, wider where a claim names a function. I read `src/master_finhub/runtime/loop.py` and `orchestration/modes/subagent.py` for the A49 interface claims. I ran Python 3.11.15 probes for the `readline(limit)` bound, the close-while-read behaviour and `check_command`.

## Claims

### Changed and added rows (full re-audit)

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A3 | UPHELD | code_executor.py:94 | `random_suffix = "".join(random.choices(string.ascii_lowercase, k=8))`, applied only when the name is the default. Comment at :86 says "from using the same container". | The reworded claim (per executor instance, agents never share) is exactly what the line shows. Round-1 fix A3a has been applied. |
| A39 | UPHELD | NET-NEW | — | All eight modes listed in the row have a proof test that uses them: paged, die-on-call, never-answer, version, huge-line, endless-pages, ask-client, plus normal (slice text lines 316-328). No reference ships a stdio MCP server. |
| A49 | UPHELD | NET-NEW (`subagent.py:111`) | `def _both(first, extra)` at :111. It returns `first`'s denial unless that is `None`, then calls `extra`. | The interface claim is verified. `snapshot.messages[-1]` is exact: `_save` runs once per append (loop.py:165, 178, 185, 196), and `context.fit` at :192 runs before the append at :195, so the last message is always the newly appended one. Round-1 note N3 has been applied. The named test exists. |
| A73 | UPHELD | code_executor.py:451; :457 | `client.containers.get(container_name)` at :449-451. Comment "Remove existing container - it may have stale mounts from a previous run" at :452. `container.remove(force=True)` at :457, then `raise NotFound("Container removed, recreating")`. | This is inside `_run_python_code_in_docker` (def at :422), so it runs on every execution. Claim supported. Round-1 fix A3b has been applied. The design adaptation (`mf_<uuid8>` plus `--rm`) is proven by `test_docker_argv_unique_names`. |
| A74 | UPHELD | NET-NEW (reason cites crewai streaming.py:213) | `sync_queue: ... = queue.Queue()` at :213 is unbounded. | The reason is true. The mechanism is in the slice text (line 147): bounded `maxsize=256`, `put(timeout=0.1)` retries until `stop` is set (sentinel included), and `finally` does stop, group kill, close, join(5 s). The named test is `test_abandoned_stream_releases_readers`. Memory ceiling is 256 x 64 KB = 16 MB per stream before `collect`. Builder note N7 applies (finally ordering). |
| A75 | UPHELD | NET-NEW (reason cites deepseek client.py:323) | `for line in proc.stdout:` at :323 has no bound. | The reason is true. Slice text line 287 uses `readline(MAX_LINE_BYTES + 1)` and closes on "limit reached without newline". I probed this on 3.11.15: text-mode `readline(1001)` on a 5 MB newline-less stream returned 1001 chars with no `\n`, so the bound holds. Named test: `test_oversize_line_closes_session`. Builder note N8 applies (chars vs bytes). |
| A76 | UPHELD | NET-NEW (reason cites tools.ts:173-174) | `cursor = response.nextCursor` / `} while (cursor)` has no cap. | The reason is true. Named test: `test_endless_pages_capped` (exactly 20 requests). |
| A77 | UPHELD | NET-NEW (reason cites deepseek client.py:348-351) | :348 `if isinstance(msg_id,(str,int)) and isinstance(method,str)`. :350 `self._requests.put(IncomingRequest(...))` hands the request to an application queue. | The reason is true. The design advertises no capabilities, so `-32601` is the correct reply. Named test: `test_server_request_gets_method_not_found`. Builder note N9 applies (the reader thread now writes to the pipe). |
| A78 | UPHELD | NET-NEW (reason cites direct_benchmark/runner.py:58, :66) | `tempfile.mkdtemp(` at :58. `_setup_workspace(challenge)` at :66; `_create_agent(challenge)` at :69. | Within tolerance. The reason (the reference's agent wiring is not portable) is fair. `run_case` signature `tools_factory: Callable[[Workspace], list[Tool]]` (line 575) and `tools_factory(workspace)` (line 584) are consistent. Named tests: `test_tools_get_case_workspace` and `test_file_entry_outside_workspace_fails`. Round-1 note N4 has been applied. Slice 10's `tools_factory: Callable[[], list[Tool]]` is a separate API and stays consistent with its own test. |

### Unchanged rows — carried forward UPHELD (round 1 verdicts unchanged)

A1, A2, A4-A38, A40-A48, A50-A72: UPHELD (see round 1 evidence; unchanged text and citations).

Spot-check this round. Each line was re-opened and still matches its claim:

| id | line re-opened | content |
|---|---|---|
| A1 | code_executor.py:48; :49 | `return docker_info["OSType"] == "linux"`; `except Exception:` |
| A2 | code_executor.py:489; :493 | `"bind": "/workspace"`; `working_dir="/workspace"` |
| A4 | code_executor.py:132 | `"Timeout in seconds (1-600, default: 120)"` |
| A5 | subprocess/src/index.ts:44 | `SENSITIVE_ENV_PATTERN = /KEY\|PASSWORD\|SECRET\|TOKEN/i` |
| A6 | output.ts:103 | `while (this.retainedBytes > this.maxBytes)` |
| A8 | spawn.ts:304 | `process.kill(-pid, sig)` |
| A10 | crewai streaming.py:279; :281 | `if item is None:`; `if isinstance(item, Exception):` |
| A18 | deepseek client.py:73; :323 | `subprocess.Popen(`; `for line in proc.stdout:` |
| A20 | client.py:239; :357 | `queue.Queue(maxsize=1)`; `isinstance(message.get("error"), dict)` |
| A21 | client.py:269 | `if remaining <= 0:` |
| A23 | client.py:304 | `with self._write_lock:` |
| A28 | tools.ts:112 | `` `mcp__${serverName}__${rawName}` `` |
| A30 | tools.ts:344 | `if (result.isError === true) {` |
| A33 | filters.py:82 | blocked check |
| A35 | redact-mcp-secrets.ts:119; :35 | split/join redaction; `value.length < MIN_SECRET_LENGTH` |
| A40 | dify streaming_utils.py:25 | `yield StreamEvent.PING.value` |
| A43 | dify message_generator.py:27 | `idle_timeout=300` |
| A45 | static-server.mjs:244 | `Hostname to bind (default: 127.0.0.1 loopback)` |
| A53 | direct_benchmark/runner.py:88 | `except asyncio.TimeoutError:` |
| A55 | evaluator.py:64 | `if result.timed_out:` |
| A56 | evaluator.py:103 | `for phrase in should_contain:` |
| A60 | skill-testing-guide.md:137 | an assertion passing 100% in both configurations is non-discriminating; remove or replace it |
| A62 | crewai experiment/runner.py:69 | `or md5(str(test_case).encode(), ...)` |

Slice text that changed around unchanged rows was re-checked:
- **N1 (A14).** `DockerEngine.stream` is "plain function, not a generator", runs `check_command` and then returns the `stream_process` generator (lines 114-116). Because `Popen` lives inside the generator body, an un-iterated generator spawns nothing.
- **N2.** `touch /etc/x` is labelled a smoke test only. `--read-only` is proven by `test_docker_argv_hardening` (lines 176, 180).
- **N5.** "a timed-out case never passes (A55)" (line 588).
- **A55.** The row text "never passes even though its score is still recorded" is unchanged and still matches evaluator.py:64.

## Round-1 rejections: fix confirmation

| round-1 id | status | evidence in revision 2 |
|---|---|---|
| A3 | FIXED | A3 is reworded to per-instance only. A73 cites the per-run recreate (:451; :457). `test_docker_argv_unique_names` (line 174) asserts distinct `--name mf_<8 hex>` and `--rm` in both argvs. |
| F1 | FIXED | Slice text line 287 says the reader uses `proc.stdout.readline(MAX_LINE_BYTES + 1)` "instead of `for line in proc.stdout`", and a limit-length line without a newline gives `McpClosed`. The other two parts are in line 292 (`MAX_TOOL_PAGES` → `McpError`) and line 311 (`-32601` with the same id). Rows A75, A76 and A77 each carry an honest NET-NEW reason I verified against the cited reference lines. Named tests are at lines 323-325, and the A39 mode list is updated. |
| F2 | FIXED | Slice text line 147 (option b): bounded queue; every `put` including the sentinel uses `timeout=0.1` in a loop that exits on `stop`; `finally` sets `stop`, kills the group, closes the pipes and joins readers (5 s). Row A74 has an honest reason. `test_abandoned_stream_releases_readers` (line 175) checks reader threads dead, process group gone and pipes closed. |

## New-defect search (revision 2)

None of these is blocking. The builder must apply N7-N9; they do not change any verdict.

- **N7 (slice 8, A74) — finally ordering can hang.** I verified on 3.11.15 that `BufferedReader.close()` blocks while another thread is inside `read1()` on the same pipe, and returns only after the pipe reaches EOF.
  - The design order is stop → kill group → close → join(5 s). If a descendant escaped the process group (`setsid`) and still holds the write end, `close()` hangs forever and the 5 s join never runs.
  - **Fix:** use the order stop → kill group (and `on_timeout`) → `join(timeout=5)` → close the pipes only for readers that are dead. Make the reader threads `daemon=True`, so a stuck reader cannot block interpreter exit.
  - No new test is needed; the existing abandoned-stream test still covers the normal path.
- **N8 (slice 9, A75) — the limit counts characters, not bytes.** The stream is text-mode UTF-8, so `readline(MAX_LINE_BYTES + 1)` bounds characters, up to about 16 MB of raw bytes plus one decoder chunk.
  - **Fix:** rename the constant to `MAX_LINE_CHARS`, or state the ceiling in a comment. The limit stays bounded either way.
  - The check must be `len(line) > MAX_LINE_BYTES and not line.endswith("\n")`. A line of exactly `MAX_LINE_BYTES` chars plus `\n` is valid, and `""` means EOF (break).
- **N9 (slice 9, A77) — the reader thread now writes.** Writing the `-32601` reply from the reader under the write lock (A23) means a hostile server can deadlock the client. Such a server floods requests and never reads stdin; once its stdin pipe is full, the reader blocks in `write`. From then on stdout is not drained, the write lock is held forever, and `close()` would block on `stdin.close()`.
  - The client-write variant of this hang already exists in the reference and in the UPHELD A23 design. A77 widens it to the reader thread.
  - **Fix:** cap server-initiated requests per session (e.g. `MAX_SERVER_REQUESTS = 64`). Beyond the cap, close the session with `McpClosed("server sent too many requests")` instead of replying.
  - Add a stub-mode case to `test_server_request_gets_method_not_found`, or a new test `test_request_flood_closes_session`.
- **N6 (carried from round 1, not applied).** Slice 9 has no "Accepted risks" section. Add one stating that MCP tool names, descriptions and schemas come from the server and reach the model (prompt-injection surface).
- No other defect found. Specific checks:
  - Thread leak: readers exit on `stop`; MCP reader and stderr threads are daemon threads per A18/A19.
  - Unbounded memory: stream queue bounded; SSE per-run queue bounded by `max_steps`; MCP stderr `deque(maxlen=200)`.
  - Deadlock in the normal stream path: sentinels are received before `finally`.
  - Claim without a row: none. Every NET-NEW decision in slices 8-11 maps to a row (A12-A17, A38, A39, A48-A50, A64-A78).

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| 8 | N/A runs commands; no prices/returns | N/A no positions | N/A no fills | N/A no time series | N/A no universe | N/A no split |
| 9 | N/A protocol plumbing | N/A | N/A | N/A | N/A | N/A |
| 10 | N/A transport only | N/A | N/A | N/A | N/A | N/A |
| 11 | N/A genuine: string expectations on agent text; schema has no price/trade fields | N/A genuine: no positions or leverage | N/A genuine: no fills | N/A genuine: independent prompts; only `task` reaches the agent, `ground` never does | N/A genuine: no universe | N/A genuine: nothing fitted or tuned; no split |
| 11 forward rule | A64 gate is unchanged: an unknown `eval.type` is rejected at load, so a returns/backtest verifier needs code plus a new slice that states G1-G6 PASS mechanisms | | | | | |

A78 changes only which `Workspace` the tools receive. It adds no numeric logic, so every guardrail ruling is unchanged.

## Safety invariants (re-confirmed)

| invariant | result | evidence |
|---|---|---|
| Children never get a weaker guard than the parent | PASS | `_both` (subagent.py:111-118) is unchanged and returns `first`'s denial unless that is `None`. Slice 10 composes `guard_tool_call` first. Slice 11 uses `guard=guard_tool_call`. New tools are plain `Tool`s. |
| Loopback default bind | PASS | `host="127.0.0.1"`; `ValueError` unless `allow_remote`; 421 Host check; `hmac.compare_digest` |
| No host exec of agent code | PASS | Verifiers are string checks only (A57, A64). A78 tools write through `Workspace` (fenced) and execute nothing. |
| No `shell=True` | PASS | Only mentioned as forbidden (lines 150, 681). argv lists everywhere; MCP `command: tuple[str, ...]`. |
| No new dependency | PASS | `pyproject.toml:10 dependencies = []`; the revision adds only stdlib (`threading.Event`). |
| `check_command` re-check | PASS | Engine (A14), checked before the generator is created (N1), and MCP launch (A38). Probe: `check_command(shlex.join([sys.executable, "tests/mcp_stub_server.py"]))` → `None`; `rm -rf /` (string and joined argv) → denial. |

## Python 3.11 compatibility

No problems found. The host runs Python 3.11.15. The revision adds `threading.Event`, `queue.Queue.put(timeout=)`, `TextIOWrapper.readline(size)` (probed and working) and `Callable[[Workspace], list[Tool]]`, all of which are available in 3.11. It uses no PEP 695 syntax and no 3.12-only stdlib.

## Licence check

- No citation outside `references/`. None into `references/autogpt/autogpt_platform/`.
- New autogpt rows (A73; A78 reason) are under `classic/` (MIT).
- New dify usage: none.

## Round 1 history

- Round 1 totals: UPHELD 71 / REJECTED 3 / UNVERIFIED 0 (A1-A72 plus F1, F2).
- Rejected in round 1:
  - **A3:** `:94` separates agents, not runs.
  - **F1:** unrowed MCP line cap, page cap and `-32601` reply; the `for line in proc.stdout` reader was unbounded.
  - **F2:** unrowed bounded queue; abandoned full queue leaked blocked readers.
- Round 1 non-blocking notes N1-N6:
  - N1-N5 are applied in revision 2.
  - N6 is not applied and is carried forward above.
- Round 2 outcome: all three rejections fixed; 0 REJECTED, so the audit is clean.
