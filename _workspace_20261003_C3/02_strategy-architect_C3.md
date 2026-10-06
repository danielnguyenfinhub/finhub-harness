# C3 adoption design: secret-shape redaction of tool results and MCP text (revision 2)

Scope: runtime. Target module: `src/master_finhub/tools/secret_scan.py`. Author: strategy-architect, 2026-10-03.
Every design choice below was simulated on a scratch copy of `src/` and `tests/` (scratchpad only, nothing outside `_workspace` edited, `python -B`, no bypassPermissions). The simulated results are quoted as **[simulated]**.

## Changes in revision 2

This responds to `02_adversarial-risk-judge_C3_r2.md` (UPHELD 38 / REJECTED 1), round 3 of 3. I accept the A36 rejection and reproduced it before changing anything. The old R10 alone on `"eyJ-"` repeated took 0.031 s at 10 KB and 3.08 s at 100 KB (100 times as long for 10 times the input).

**Behaviour change (one): R10's leading `\b` becomes `(?<![A-Za-z0-9_-])`.** This is the judge's fix.
- Measured after the fix **[simulated]**: `eyJ-` and `eyJaaaaaaaaaaaa-` repeated take 0.007 s at 100 KB, 0.07 s at 1 MB and 0.29 s at 4 MB.
- The fix has one side effect, which is now pinned and disclosed: a JWT glued directly after `-` is no longer redacted (Does-not-cover #5).
- Both dash-joined inputs are added to `ADVERSARIAL`, and #12 is corrected.

**Independent sweep (P13)**, run as requested, because the round-1 timing review missed a shape.
- For each rule I generated 1,591 inputs in total. Each input is one of the rule's prefixes glued to itself:
  - with each separator `'' - _ . 0 a A space / + = ~ : " ' \n é`;
  - with each separator after one character short of the minimum length;
  - with each separator after exactly the minimum length;
  - with each separator after a partial-segment JWT;
  - for private keys, with header fragments.
- Every input was run against every rule's pattern, `redact_secrets`, and `client.redact(…, mcp_shapes=False)` (the merged-span path for successful results). I ran a separate process per family, with a 900 s timeout.
- **Sanity check:** the same sweep on revision 1 at 100 KB flags R10 at 3.21 s. Every other rule is ≤0.03 s there.

Revision 2, worst case per rule **[simulated]** (seconds):

| rule | own pattern 1 MB | own pattern 4 MB | worst unit (4 MB) | `redact_secrets` 4 MB | `client.redact` 4 MB |
|---|---|---|---|---|---|
| R1 private-key | 0.023 | 0.086 | `-----BEGIN PRIVATE KEY-----+` | 0.364 | 0.362 |
| R2 bearer-token | 0.043 | 0.110 | `Bearer\t\n` | 0.440 | 0.844 |
| R3 mercury-mcp-key | 0.032 | 0.100 | `x-mcp-key=aaaaaaaa'` | 0.466 | 0.754 |
| R4 aws-access-key | 0.016 | 0.053 | `AKIA"` | 0.304 | 0.759 |
| R5 github-token | 0.017 | 0.053 | `gho_` + 20a + `=` | 0.436 | 0.937 |
| R6 github-pat | 0.016 | 0.045 | `github_pat_` + 20a + `'` | 0.413 | 0.718 |
| R7 anthropic-key | 0.014 | 0.053 | `sk-ant-` + 20a + `+` | 0.440 | 0.838 |
| R8 openai-key | 0.019 | 0.052 | `sk-proj-` + 19×`0` + `/` | 0.392 | 0.858 |
| R9 slack-token | 0.028 | 0.076 | `xoxp-` + 10a + `:` | 0.444 | 0.722 |
| R10 jwt | 0.028 | 0.069 | `eyJ` + 10a + `.000000000"` | 0.310 | 0.768 |

Notes on the table:
- The last two columns are measured on the worst unit of that rule's input family, so they reflect all ten rules, not just that row's rule.
- The `redact_secrets` worst case at 1 MB is 0.203 s, and the client worst case at 1 MB is 0.248 s. All ten per-rule winners are added to `ADVERSARIAL`, which now has 25 inputs.
- The timing test now also times the successful-result `client.redact` path, which is test-only.

**Test-only additions (no behaviour change):**
- **N9:**
  - A known value with metacharacters (`ab+cd/ef==(x)`) must be redacted. This kills the judge's J14, dropping `re.escape`.
  - A successful stub echo of an AWS key must come back as `[REDACTED:aws-access-key]`. This kills J16, the table being applied to error text only.
- **N12:** one touching-spans case and one case with a 1-character overlap. These kill J01 and J02.

**Decisions on notes N8, N10 and N11, recorded under Does-not-cover. None is fixed in C3:**
- **N8 (a header glued to a second header swallows its name):** Does-not-cover #5. Contrived glue; it was also present in revision 0.
- **N10 (the pre-existing `SECRET_SHAPES` JWT branch is quadratic on MCP error text):**
  - It is a follow-up. C3 does not touch it beyond keeping it off successful results.
  - The one-token fix is `|(?<![A-Za-z0-9_-])eyJ…` in `client.py:51`. Measured with that fix: 4.23 s → 0.010 s at 100 KB, and 0.40 s at 4 MB. See #12.
- **N11 (`Bearer` + U+00A0):** a follow-up with `(?u:\s)+`. See #5.

**Mutants:** 81 run, 78 killed. The 3 survivors are the same proven equivalents as before (X20, `re.ASCII` on R1, and the `re.ASCII` comment). The new mutants are jwt-restore-b, jwt-lookbehind-word-only, mcp-no-escape, mcp-table-error-only, merge-touching and merge-skip-1char.

**Counts:**
- `secret_scan.py`: 98 → 103 lines. The only change is R10's anchor plus its 3-line comment.
- `tests/test_secret_scan.py`: 301 → 325 lines, 188 → 202 cases.
- Whole suite: 1092 passed **[simulated]**, which is 890 + 202 with 5 tree-dependent tests deselected. The expected count on the real tree is 1097 passed, 10 skipped.
- `mypy --strict src`, `ruff` and `black` are clean. P7 returns 0 and P7b returns `()`.

**Authority List:**
- **A36 CHANGED r2.**
- **New rows:** A38 (R10 look-behind), A39 (`re.escape` pinned), A40 (touch versus overlap pinned).
- **Unchanged:** every other row is byte-identical to revision 1. I checked this with a diff. A12 and A27 keep their `CHANGED r1` text.

## Changes in revision 1

Response to `02_adversarial-risk-judge_C3_r1.md` (UPHELD 30 / REJECTED 3). I accept all three rejections; each one reproduced in my scratchpad before I changed anything.

| judge id | reproduced | change | Authority rows |
|---|---|---|---|
| A12 (R8 quadratic) | yes: the old R8 on `"sk-"*333_333` (1 MB) did not finish within a 90 s timeout | The look-ahead is removed. R8 is now `\bsk-[A-Za-z0-9_-]{20,}\b`, and the digit test runs in Python on the matched token (`need_digit` flag, `_DIGIT.search(text, start, end)`). Every rule was timed on 16 adversarial inputs: the worst is 0.12 s at 1 MB and 0.43 s at 4 MB (`x-mcp-key: ` repeats). `client.redact` on 4 MB of `AKIA` with two short values takes 0.86 s. A timing test (13 inputs, 1 MB each, under 2 s each) is added. Does-not-cover #12 no longer says "linear passes"; it states the measurements. | A12 CHANGED r1; A36 new |
| S1 (Unicode `\b`) | yes: `redact_secrets("clé"+AWS)` returned the key | `re.ASCII` on every rule (11 occurrences in the file, including one in a comment). There are tests for a non-ASCII neighbour on each side for every positive, plus CJK before `Bearer` and before `x-mcp-key`. One per-rule mutant drops `re.ASCII`. Two of these mutants are equivalent: R1 (no `\b`, `\w`, `\s`, `\d` or case folding) and the comment. Does-not-cover #5 is rewritten. | A32 new |
| S2 (value-first partial leak) | yes: `redact("id="+AWS, ["0000"])` left 16 of 20 key characters | **Merged spans** (option a), not documentation only. `secret_spans()` finds every rule match on the original text. `merge_spans()` takes the union of overlapping spans; the earliest start names a merged span, and on a tie input order decides. `apply_spans()` replaces each merged span once. `redact_secrets` and `client.redact` both use these functions. `client.redact` puts known-value spans first, then `SECRET_SHAPES` spans, then table spans, so a tie at the same start keeps today's `[REDACTED]`. Both judge cases and `GHP` with value `ghp_FAKE` are tests. Both sequential orderings are mutants, and both are killed. Cost: `secret_scan.py` grows from 49 to 98 lines, and `redact` from 4 to 9 lines. I chose this over documentation-only because it also fixes the `pw-` direction and costs about 30 lines. | A27 CHANGED r1; A33 new |

Notes folded in, with no other scope change:

- **N1:**
  - Each minimum length is pinned with a positive at the minimum and a negative one below it: Bearer 15/16, x-mcp-key 7/8, `github_pat_`, `sk-ant-` and `sk-` 19/20, `xoxb-` 9/10, JWT first segment 9/10.
  - Context forms are pinned: `x-mcp-key=…`, `X-MCP-KEY: …`, and `Bearer` followed by a tab or a newline.
  - Glued-prefix negatives are added for GitHub, Slack and JWT.
  - The judge's own surviving mutants X03-X14, X22 and X23 are in the mutation table, and all are killed **[simulated]**.
  - **X20 (drop the trailing `\b` on R5) is an equivalent mutant**, so it cannot be killed. R5's class `[A-Za-z0-9_]` is exactly the ASCII word class, so the greedy run always ends next to an ASCII non-word character or the end of the text, and `\b` always holds there under `re.ASCII`. The same is true of R6's trailing `\b`.
- **N2:** P8 now uses `LC_ALL=C.UTF-8`, plus a `python3 -c` fallback that needs no locale.
- **N3:** P7 is extended. It now covers `github_pat_`, `sk-ant-`, `xox[abprs]-`, the three-segment JWT, `Bearer` plus 16 characters, and `x-mcp-key`. A new P7b runs the scanner itself over the test file and expects `()`. A planted `xoxb-` literal is found by the extended P7 **[simulated]**.
- **N4 (quoted Bearer): fixed.** One character class changes: `keep` is now `\bBearer\s+["']?`. There is a test and the mutant `bearer-noquote`. → A35.
- **N5 (successful MCP results get no known-value pass): fixed.** `call_tool` runs `redact(text, self._secrets(), mcp_shapes=is_error)` on every result.
  - The value pass and the C3 table run always.
  - `SECRET_SHAPES` still runs on error text only. Its any-length Bearer would otherwise turn successful prose such as "Bearer securities are negotiable" into `[REDACTED] are negotiable`.
  - The stub echo test covers both halves. The mutants `mcp-success-no-values` and `mcp-shapes-always` are killed. → A34.
- **N6 (a bare BEGIN header in docs wipes the rest): documented and pinned.** Redacting to end-of-text is the deliberate fail-safe for a truncated key; any heuristic end would leak a key body that ends without END. A test pins the behaviour, and the case is listed under Does-not-cover #11.
- **N7 (non-str result raises out of the loop): documented and pinned.** This fails closed, and the `Tool` protocol already requires `str` (`loop.py:129`). A test asserts `TypeError`, and the mutant `loop-str-coerce` (which would wrap the result in `str(...)`) is killed. → A37.

UPHELD rows A1-A11, A13-A26 and A28-A31 are byte-identical to revision 0.

## Source

Backlog row C3 (`_workspace/01b_capability-scout_backlog.md:50`, `### C3` at :95) asks for:
- a regex table of anchored credential shapes;
- the table applied to every tool result in `AgentLoop._execute` and to MCP error and stderr text;
- labels returned, never the match.

Port-map rows, re-opened for this design:

| row | port map | cited line, re-opened | what is there |
|---|---|---|---|
| OH65 | `01_reference-miner_openharness_portmap.md:125` | `references/openharness/src/openharness/memory/team.py:24-31` | `SECRET_RULES`: a tuple of `(rule_id, label, compiled pattern)` covering private-key header, AWS `AKIA`, GitHub `gh[pousr]_`, OpenAI `sk-`, Anthropic `sk-ant-` and a generic `secret/token/api key/password` assignment. |
| OH65 | same | `team.py:70-77`, `:80-90` | `scan_for_secrets` walks the rules in order and appends one `SecretMatch(rule_id, label)` per rule that matches. No matched text is kept. `check_team_memory_secrets` joins the labels into a refusal message. OH65 blocks the write. It does not replace text. |
| O12 | `01_reference-miner_openhands_portmap.md:38` | `references/openhands/src/utils/redact-mcp-secrets.ts:18-28` | `GENERIC_SECRET_PATTERNS` covers GitHub classic and `github_pat_`, Slack `xox?-`, Linear and JWT `eyJ…`. |
| O12 | same | `redact-mcp-secrets.ts:30-31` | A `Bearer` pattern, case-insensitive, with 8 or more token characters. The prefix is kept so the message stays readable. |
| O11 (context) | `01_reference-miner_openhands_portmap.md:37` | `redact-mcp-secrets.ts:110-129` | Known config values are replaced first (:116-121), then the Bearer pattern (:122-125), then the generic patterns (:126-128). |
| (Mercury) | none; found while grounding the FinHub shapes | `references/deepseek_harness/scripts/railway-mercury-mcp.cordis.yml:8-9`, `:19` | The Mercury CRM MCP server accepts its static secret as `Authorization: Bearer` or `x-mcp-key`. The harness sends `Bearer ${MERCURY_MCP_TOKEN}`. |

Licences, from `references/LICENSES.md`:
- openharness: MIT (`:14`). The upstream organisation is unverified, and every OH row inherits that flag (backlog `:165`).
- openhands: MIT (`:9`).
- deepseek_harness: MIT (`:12`). Only a fact is used from it; no code is copied.
- Nothing is cited from `references/autogpt/autogpt_platform/`.

### What the runtime already does (verified in `src/`)

- `tools/mcp/client.py:107-110`, `redact()`:
  - replaces known values, longest first, when they are 4 or more characters long;
  - then applies `SECRET_SHAPES` (`:47-52`): Bearer of any length with no prefix kept, `gh[pousr]_`, `github_pat_`, `xox[abprs]-` and JWT, each replaced by `[REDACTED]`.
  - The backlog's "only value-based redaction" understates this. A shape list already exists, but it covers MCP text only.
- MCP text paths that call `redact()`:
  - `stderr_tail` (`:141`);
  - `_fail` (`:177`), whose messages become the text of `McpClosed`;
  - JSON-RPC error messages (`:302`);
  - `isError` tool text (`:358`).
  - A **successful** MCP tool result is not redacted.
- `sandbox/stream.py:22`, `SENSITIVE_ENV`, removes secret-looking env *names* from child environments. It never sees output.
- `runtime/loop.py:216-228`, `AgentLoop._execute`, returns tool output, guard denials, the unknown-tool text and exception text **unredacted**. Both `_drive` (`:184`) and the resume path `_uncertain` (`:211`) call `_execute`.
- Every agent run goes through `AgentLoop`:
  - CLI (`cli.py:132`);
  - server SSE (`server/app.py:138`, whose hook streams each message's `content`);
  - subagent (`modes/subagent.py:315`);
  - team (`modes/team.py:356`);
  - evals (`evals/runner.py:146`).
  - One choke point in `_execute` therefore covers the transcript, checkpoints (`_save`), SSE events and `_workspace` files written from snapshots.
- Order of events in a step:
  1. `_execute`;
  2. append the result to `messages`;
  3. `_save(...)`, which runs the checkpoint and SSE hook;
  4. later, `context.fit` (`loop.py:191`), which clips long tool results (`context.py:63`).
  - Redaction inside `_execute` therefore runs **before** storage and **before** the context clip. The clip can never split a key that the scan would have caught.


## Target

Runtime module, four files:

| file | change |
|---|---|
| `src/master_finhub/tools/secret_scan.py` | NEW, 103 lines: `RULES` table, `secret_spans()`, `merge_spans()`, `apply_spans()`, `redact_secrets()` |
| `src/master_finhub/runtime/loop.py` | +6 lines: import; `_execute` becomes the redacting wrapper; the old body is renamed `_run_tool` |
| `src/master_finhub/tools/mcp/client.py` | +1 import; `redact()` rewritten as a span merge with a new keyword `mcp_shapes` (9 lines); `call_tool` runs `redact` on every result (2 lines become 1) |
| `tests/test_secret_scan.py` | NEW, 325 lines, 202 test cases |

No other file changes:
- no existing test is modified;
- nothing under `skills/` or `.claude/`;
- no new dependency (stdlib `re` only).

The orchestrator, not this design, decides whether `CLAUDE.md` gets a change-history row.

Quant guardrails: not applicable. C3 touches no backtest, eval scoring or verifier logic.

## Design

### Decision 1: the rule table (anchored token shapes only)

The table is matched on the original text. Each merged match span is replaced by `[REDACTED:<rule>]`. Two header rules keep their header: the `keep` group is excluded from the span. **Every rule is compiled with `re.ASCII`** (A32), so `\b` treats é, CJK and other non-ASCII letters as non-word characters.

| # | rule id | pattern (Python `re`, plus `re.ASCII`) | digit required | source | notes |
|---|---|---|---|---|---|
| R1 | `private-key` | `-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*?(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----\|\Z)` with `re.DOTALL` | no | header from OH65 `team.py:25`; block span is NET-NEW | OH65 only detects the header because it refuses the whole write. A replacing scanner must take the body too, or the base64 key leaks. With no END line (a truncated output), it redacts to the end of the text. Non-greedy, so text between two keys survives. ` BLOCK` covers PGP. |
| R2 | `bearer-token` | `(?P<keep>\bBearer\s+["']?)[A-Za-z0-9._~+/=-]{16,}` with `re.IGNORECASE` | no | O12 `:30-31` (prefix kept, case-insensitive, token charset) | The minimum is 16 rather than O12's 8 (NET-NEW). "bearer securities" (10 characters) and "Bearer instruments" are ordinary finance prose. The optional quote is N4 (A35). Also covers the Mercury MCP `Authorization: Bearer` header (deepseek `cordis.yml:9`, `:19`). |
| R3 | `mercury-mcp-key` | `(?P<keep>\bx-mcp-key["']?\s*[:=]\s*["']?)[A-Za-z0-9._~+/=-]{8,}` with `re.IGNORECASE` | no | header name from deepseek `cordis.yml:9`; regex NET-NEW | FinHub-specific and **grounded**, not synthetic. The token class excludes `[`, so an existing label is never redacted again (idempotence). |
| R4 | `aws-access-key` | `\b(?:AKIA\|ASIA)[0-9A-Z]{16}\b` | no | `AKIA` from OH65 `team.py:26`; `ASIA` is NET-NEW | `ASIA` is the STS temporary-key prefix. The exact length of 16 and the word boundaries are kept. |
| R5 | `github-token` | `\bgh[pousr]_[A-Za-z0-9_]{20,}\b` | no | OH65 `team.py:27` (same shape as O12 `:20`, which requires 16 or more) | The trailing `\b` is redundant (see X20 in Changes) but kept as in the source. |
| R6 | `github-pat` | `\bgithub_pat_[A-Za-z0-9_]{20,}\b` | no | O12 `:21` | |
| R7 | `anthropic-key` | `\bsk-ant-[A-Za-z0-9_-]{20,}\b` | no | OH65 `team.py:29` | It comes before R8, so it names the merged span when both start at the same place (A13). |
| R8 | `openai-key` | `\bsk-[A-Za-z0-9_-]{20,}\b` | **yes**, checked in Python | OH65 `team.py:28`; digit requirement is NET-NEW (A12) | The digit test stops kebab-case identifiers such as `sk-component-header-wrapper` being redacted. It runs **after** the match, on the token only, because a look-ahead inside the pattern made the scan quadratic. A rejected match is still consumed by `finditer`, so the scan stays linear. |
| R9 | `slack-token` | `\bxox[abprs]-[A-Za-z0-9-]{10,}` | no | O12 `:23` (prefix `xox` + letter + `-`) | Narrowed to `[abprs]` and 10 or more characters (NET-NEW). O12's `xox[a-z](?:-…)+` would redact `xoxo-hugs`. |
| R10 | `jwt` | `(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b` | no | O12 `:27` (shape); leading look-behind is NET-NEW (A38) | Three segments are required. The leading anchor is a look-behind on the segment class, not `\b`. With `\b`, every `-eyJ` inside one dash-joined run was a start, and each start scanned to the end of the run: quadratic (judge r2). Now there is at most one start per run. |

**Rules dropped, and why:**

- **OH65 `generic-secret`** (`team.py:30`, `\b(secret|token|api[_-]?key|password)\s*[:=]…`) is not adopted.
  - It is an assignment rule, not an anchored token shape, so it breaks the backlog's own mitigation (`:50`).
  - Its leading `\b` cannot match inside `AUTH_TOKEN=` or `DB_PASSWORD=`, because `_` is a word character. So it misses the usual `.env` names.
  - It would redact code such as `password = get_password_from_vault()`.
- **Twilio** has no dedicated rule.
  - No file under `references/` defines a Twilio token shape. `grep -rIil twilio references` finds only `autogpt/.secrets.baseline`, which holds a detector name and no pattern.
  - The Twilio auth token has no vendor prefix [assumed, not grounded]. Any rule for it would be a generic-hex rule, which the brief forbids.
  - Account SIDs are identifiers, not secrets.
  - Dropped; listed under "Does not cover".
- **Xero** has no dedicated rule.
  - `references/` has no Xero token shape (the only hits are cassettes and a `.d.ts` file).
  - Xero OAuth access tokens are expected to be JWTs and so fall under R10, or under R2 when they are sent as Bearer. This is [assumed]: it is not grounded in `references/` and no Authority row relies on it.
  - The Xero client secret has no prefix, so it is not covered.
- **Mercury** is grounded through its transport. Its secret appears as `Authorization: Bearer` (R2) or `x-mcp-key` (R3). A bare Mercury secret with no header is not covered.
- **Linear `lin_api_`** (O12 `:25`) is dropped because FinHub has no Linear consumer. It can be added later as one row plus its tests.

### Decision 2: where redaction runs, and its order relative to truncation and storage

- **In the loop.** `_execute` becomes:

  ```python
  def _execute(self, call: ToolCall) -> str:
      """Every tool result, denial and error text passes the secret scan before it is stored."""
      return redact_secrets(self._run_tool(call))[0]

  def _run_tool(self, call: ToolCall) -> str:
      ...  # the current _execute body, unchanged (loop.py:217-228)
  ```

  One choke point covers four kinds of text:
  1. the success result;
  2. the guard denial (`Error: {denial}`);
  3. the unknown-tool message;
  4. the exception text, including `McpToolError(result.text)` raised by `McpTool.run` for an `isError` MCP result.

  Both callers use it: `_drive` and the resume path through `_uncertain`.
  - `redact_secrets` runs outside `_run_tool`'s `try`. A tool that breaks the `Tool` protocol (`loop.py:129`) by returning a non-`str` therefore raises `TypeError` out of the loop instead of being stored. This **fails closed**, which is deliberate, and a test pins it (N7, A37).
- **Order relative to truncation and storage.** Redaction runs after the tool returns and before:
  - the message is appended;
  - `_save` (checkpoint file, SSE event);
  - `ContextManager.fit` clips it.
- **Truncation inside a tool still happens first.** Docker output passes through `TailBuffer` (`stream.py:44`), and MCP stderr lines are capped at 4096 characters (`client.py:41`). That truncation happens before `_execute` can see the text. See "Does not cover".
- **In the MCP client: merged spans on the original text (S2).** `redact()` becomes:

  ```python
  def redact(text: str, secrets: Iterable[str], *, mcp_shapes: bool = True) -> str:
      """Known values, SECRET_SHAPES and the secret_scan table, all matched on the original text."""
      spans: list[Span] = []
      for secret in sorted({s for s in secrets if len(s) >= 4}, key=len, reverse=True):
          spans += ((m.start(), m.end(), "[REDACTED]") for m in re.finditer(re.escape(secret), text))
      if mcp_shapes:
          spans += ((m.start(), m.end(), "[REDACTED]") for m in SECRET_SHAPES.finditer(text))
      spans += ((s, e, f"[REDACTED:{rule}]") for s, e, rule in secret_spans(text))
      return apply_spans(text, merge_spans(spans))
  ```

  - **No sequential replacement.** All three sources are matched on the **original** text, and overlapping spans are joined into one. This removes both partial-leak directions:
    - Value first used to split a token: `id=` + AWS key with the value `0000` left 16 key characters. It now gives `id=[REDACTED:aws-access-key]`.
    - Shapes first would have left a value prefix: `pw-` + AWS key. It still gives `conn=[REDACTED]`.
  - **Tie-break.** When two spans start at the same index, the earlier one in the list names the merged span. Values come first, then `SECRET_SHAPES`, then the table. So `redact(GHP, ["ghp_FAKE"])` and the existing `test_redact_env_value_and_bearer` both still produce plain `[REDACTED]`.
  - **A side benefit.** A short value can no longer match inside a `[REDACTED]` that was inserted earlier, because nothing is inserted until all spans are known.
- **`call_tool` (N5).** `redact` now runs on every result: `text = redact(text, self._secrets(), mcp_shapes=is_error)`.
  - Successful results get the known-value pass and the C3 table.
  - `SECRET_SHAPES` stays error-only. Its any-length Bearer, with no prefix kept, would hit successful prose (A34).
- **Why the client pass is needed even though the loop also scans:**
  - `McpClosed` and `McpError` messages and `stderr_tail` reach callers outside the loop, for example an `McpClient.__enter__` failure raised to the CLI or server.
  - Only the client knows the configured values.

### Decision 3: interaction with the existing redaction (idempotence and ordering)

- **Labels never match a rule.** `[REDACTED:<rule>]` and `[REDACTED]` contain `[`, `]` and `:`.
  - None of these is in a token class that follows a prefix: R2 and R3 use `[A-Za-z0-9._~+/=-]`, and R2 accepts only a quote after `Bearer`.
  - No rule starts with `[`.
  - So `redact_secrets(redact_secrets(x)[0]) == (redact_secrets(x)[0], ())`. This is pinned by `test_redaction_is_idempotent`.
- **MCP text is scanned twice:** once in `redact()`, then again by the loop. Idempotence makes this safe.
- **Overlaps between rules are merged** (A33). Examples:
  - `Bearer ` + JWT: both spans start at the token, so R2 names the span by table order.
  - `sk-ant-…`: R7 and R8 have the same span, so R7 names it.
  - A key inside a private-key block: R1 starts first.
  - A partial overlap between two rules: the union is replaced, so no fragment is left.
- **Env-name scrub** (`stream.py:22`) is orthogonal. It controls which variables a child process receives. C3 controls what the child's output may carry back.

### Decision 4: labels, never the match

- `redact_secrets(text) -> tuple[str, tuple[str, ...]]` returns the redacted text and the names of the merged spans, in table order, each once. This follows OH65 `team.py:74-76`, which appends one entry per matching rule and keeps no matched text.
- The replacement token carries only the rule id.
- No log, exception or return value carries the matched substring.
- The loop uses only `[0]`. The labels exist for the proof test and for a future C12 post-hook or audit record.

### Interface (the contract boundary-qa checks)

```python
# src/master_finhub/tools/secret_scan.py
Span = tuple[int, int, str]                                   # start, end, rule id or replacement text
RULES: Final[tuple[tuple[str, re.Pattern[str], bool], ...]]   # (rule id, pattern, needs a digit), table order
def secret_spans(text: str) -> list[Span]: ...                # every rule match on text; keep-prefix excluded
def merge_spans(spans: Iterable[Span]) -> list[Span]: ...     # union of overlaps; earliest start names it, ties keep input order
def apply_spans(text: str, merged: Iterable[Span]) -> str: ...
def redact_secrets(text: str) -> tuple[str, tuple[str, ...]]: ...
# src/master_finhub/runtime/loop.py
AgentLoop._execute(self, call: ToolCall) -> str   # == redact_secrets(self._run_tool(call))[0]; non-str raises TypeError
AgentLoop._run_tool(self, call: ToolCall) -> str  # former _execute body, byte-identical
# src/master_finhub/tools/mcp/client.py
redact(text: str, secrets: Iterable[str], *, mcp_shapes: bool = True) -> str  # value, SECRET_SHAPES and table spans merged
McpClient.call_tool(...)                          # redact(text, secrets, mcp_shapes=is_error) on every result
```

### Reference implementation of `secret_scan.py` [simulated: mypy --strict, ruff and black clean]

```python
"""Secret-shape redaction for tool results and MCP text: returns rule labels, never the match.

Rule table adapted from references/openharness/src/openharness/memory/team.py:24 (MIT) and
references/openhands/src/utils/redact-mcp-secrets.ts:18 (MIT); Bearer keeps its prefix (:31).
Anchored token shapes only: no generic hex, entropy or ``password=`` assignment rule.
Spans are found on the original text and merged, so overlapping matches never leave a fragment.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

_TOKEN: Final = r"[A-Za-z0-9._~+/=-]"
Span = tuple[int, int, str]  # start, end, rule id or replacement text

# re.ASCII on every rule: with Unicode ``\b`` a key glued to é or CJK text was missed.
# Table order breaks ties: when two matches start together the earlier rule names the span.
# (rule id, pattern, token must contain an ASCII digit); the digit test is done in Python
# because a look-ahead inside the pattern made the scan quadratic. R10 starts after a
# look-behind, not \b: ``-`` is both a boundary and a segment character, so ``\b`` let
# every ``-eyJ`` in one run start a scan to the end of that run.
RULES: Final[tuple[tuple[str, re.Pattern[str], bool], ...]] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*?"
            r"(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|\Z)",
            re.DOTALL | re.ASCII,
        ),
        False,
    ),
    (
        "bearer-token",
        re.compile(rf"(?P<keep>\bBearer\s+[\"']?){_TOKEN}{{16,}}", re.IGNORECASE | re.ASCII),
        False,
    ),
    (
        "mercury-mcp-key",
        re.compile(
            rf"(?P<keep>\bx-mcp-key[\"']?\s*[:=]\s*[\"']?){_TOKEN}{{8,}}", re.IGNORECASE | re.ASCII
        ),
        False,
    ),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", re.ASCII), False),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", re.ASCII), False),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.ASCII), False),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", re.ASCII), False),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b", re.ASCII), True),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}", re.ASCII), False),
    (
        "jwt",
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b",
            re.ASCII,
        ),
        False,
    ),
)
_DIGIT: Final = re.compile(r"[0-9]")


def secret_spans(text: str) -> list[Span]:
    """(start, end, rule id) of every rule match in ``text``, in table order; prefixes excluded."""
    found: list[Span] = []
    for rule, pattern, need_digit in RULES:
        for m in pattern.finditer(text):
            start = m.end("keep") if "keep" in pattern.groupindex else m.start()
            if not need_digit or _DIGIT.search(text, start, m.end()):
                found.append((start, m.end(), rule))
    return found


def merge_spans(spans: Iterable[Span]) -> list[Span]:
    """Union overlapping spans; a merged span keeps the earliest start's tag (ties: input order)."""
    merged: list[Span] = []
    for start, end, tag in sorted(spans, key=lambda span: span[0]):
        if merged and start < merged[-1][1]:
            first, last, kept = merged[-1]
            merged[-1] = (first, max(last, end), kept)
        else:
            merged.append((start, end, tag))
    return merged


def apply_spans(text: str, merged: Iterable[Span]) -> str:
    """Replace each merged span with its tag."""
    out: list[str] = []
    pos = 0
    for start, end, tag in merged:
        out += (text[pos:start], tag)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def redact_secrets(text: str) -> tuple[str, tuple[str, ...]]:
    """Replace every rule match with ``[REDACTED:<rule>]``; return (text, rules that fired)."""
    merged = merge_spans(secret_spans(text))
    fired = {rule for _, _, rule in merged}
    out = apply_spans(text, ((s, e, f"[REDACTED:{rule}]") for s, e, rule in merged))
    return out, tuple(rule for rule, _, _ in RULES if rule in fired)
```

Implementation notes:
- Ruff in this repo rejects the short flag aliases `re.I` and `re.S`. Use `re.IGNORECASE`, `re.DOTALL` and `re.ASCII`.
- The only lambda is the sort key, which mypy infers without help.
- The attribution follows the house form already used in `tools/sensitive_paths.py:25`: `adapted from references/<repo>/<path>:<line> (MIT)`.

### Exact edits to existing files [simulated diff]

```diff
--- src/master_finhub/runtime/loop.py
@@ -13,6 +13,8 @@
 from typing import Any, Final, Literal, Protocol
 
+from master_finhub.tools.secret_scan import redact_secrets
+
 DEFAULT_MAX_STEPS = 20
@@ -214,6 +216,10 @@
     def _execute(self, call: ToolCall) -> str:
+        """Every tool result, denial and error text passes the secret scan before it is stored."""
+        return redact_secrets(self._run_tool(call))[0]
+
+    def _run_tool(self, call: ToolCall) -> str:
         tool = self._tools.get(call.name)
--- src/master_finhub/tools/mcp/client.py
@@ -29,6 +29,7 @@
 from master_finhub.tools.safety import check_command
+from master_finhub.tools.secret_scan import Span, apply_spans, merge_spans, secret_spans
@@ -104,10 +105,15 @@
-def redact(text: str, secrets: Iterable[str]) -> str:
+def redact(text: str, secrets: Iterable[str], *, mcp_shapes: bool = True) -> str:
+    """Known values, SECRET_SHAPES and the secret_scan table, all matched on the original text."""
+    spans: list[Span] = []
     for secret in sorted({s for s in secrets if len(s) >= 4}, key=len, reverse=True):
-        text = text.replace(secret, "[REDACTED]")
-    return SECRET_SHAPES.sub("[REDACTED]", text)
+        spans += ((m.start(), m.end(), "[REDACTED]") for m in re.finditer(re.escape(secret), text))
+    if mcp_shapes:
+        spans += ((m.start(), m.end(), "[REDACTED]") for m in SECRET_SHAPES.finditer(text))
+    spans += ((s, e, f"[REDACTED:{rule}]") for s, e, rule in secret_spans(text))
+    return apply_spans(text, merge_spans(spans))
@@ -354,8 +360,7 @@
         is_error = result.get("isError") is True
-        if is_error:
-            text = redact(text, self._secrets())
+        text = redact(text, self._secrets(), mcp_shapes=is_error)  # values on every result
         return McpResult(text, is_error)
```

Import cycle check: `secret_scan` imports only `re`, `typing` and `collections.abc`, so there is no cycle **[simulated: whole suite imports]**.

## Proof

| # | command | expected |
|---|---|---|
| P1 | `pytest -q tests/test_secret_scan.py` | `202 passed` (about 5 s; the timing test is most of it) |
| P2 | `pytest -q` (whole suite) | before: `895 passed, 10 skipped` (measured 2026-10-03 on the current tree); after: `1097 passed, 10 skipped`, with 0 failed and no existing test edited. **[Simulated]** on the scratch copy with the 5 tree-dependent tests deselected: `1092 passed, 10 skipped`, which equals 890 + 202. |
| P3 | `mypy --strict src` | `Success: no issues found in 38 source files` |
| P4 | `ruff check src tests` and `black --check src tests` | clean (the CI gates in `.github/workflows`) |
| P5 | `grep -nE "redact_secrets\|secret_spans\|merge_spans\|apply_spans" src/master_finhub/runtime/loop.py src/master_finhub/tools/mcp/client.py` | loop: 2 lines (import, call); client: 3 lines (the import line, the `secret_spans(text)` line, the `apply_spans(text, merge_spans(spans))` line) |
| P5b | `grep -c "re.ASCII" src/master_finhub/tools/secret_scan.py` | `11` (10 rules + 1 comment) |
| P6 | `grep -cE "adapted from references/openharness/src/openharness/memory/team.py:24 \(MIT\)\|references/openhands/src/utils/redact-mcp-secrets.ts:18 \(MIT\)" src/master_finhub/tools/secret_scan.py` | `2` (docstring lines 3 and 4, one per source) |
| P7 | `grep -cE 'AKIA[0-9A-Z]{16}\|gh[pousr]_[A-Za-z0-9_]{20,}\|github_pat_[A-Za-z0-9_]{20,}\|sk-ant-[A-Za-z0-9_-]{20,}\|xox[abprs]-[A-Za-z0-9-]{10,}\|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\|Bearer\s+["'"'"']?[A-Za-z0-9._~+/=-]{16,}\|x-mcp-key["'"'"']?\s*[:=]\s*["'"'"']?[A-Za-z0-9._~+/=-]{8,}\|BEGIN [A-Z ]*PRIVATE KEY' tests/test_secret_scan.py`. In this table `\|` stands for a plain `\|` alternation; `'"'"'` is bash quoting for a single quote. | `0`. Every fake credential is assembled at runtime. A planted `"xoxb-0000-FAKEFAKE"` literal gives `1` **[simulated]**. |
| P7b | `PYTHONPATH=src python -B -c "from master_finhub.tools.secret_scan import redact_secrets; print(redact_secrets(open('tests/test_secret_scan.py').read())[1])"` | `()`. This uses the scanner's own rules, including R8's digit test, which the grep cannot express. |
| P8 | `LC_ALL=C.UTF-8 grep -cP '[\x{AC00}-\x{D7A3}]' src/master_finhub/tools/secret_scan.py tests/test_secret_scan.py`. Locale-free fallback: `python3 -c "import sys;print(sum(1 for f in sys.argv[1:] for ch in open(f,encoding='utf-8').read() if '가'<=ch<='힣'))" src/master_finhub/tools/secret_scan.py tests/test_secret_scan.py` | `0` for each file, and `0` from the fallback (no Hangul). The non-ASCII test inputs are written as `\u` escapes. |
| P9 | `git diff --cached --stat` before commit | exactly the 4 files in `## Target`, staged by explicit path |
| P10 | `bash scripts/check-harness-refs.sh; echo $?` and `bash scripts/package-plugin.sh` | exit 0 for each, as before (measured `refs=0` today). No file the scripts read is touched. |
| P11 | 8-word verbatim check: every 8-word window of the prose in `secret_scan.py` (docstrings and comments) is absent from `team.py` and `redact-mcp-secrets.ts` | 0 hits. Regex literals copied from MIT sources are code under attribution, not prose. |
| P12 | timing: `test_adversarial_megabyte_stays_fast` (25 inputs × 1 MB; `redact_secrets` and the successful-result `client.redact` path each under 2 s) | **[simulated]**: slowest 0.32 s for both calls together. The restored R8 look-ahead and R10 `\b` mutants both fail it, and both are also killed by faster pins. |
| P13 | independent sweep (`scratchpad/c3/sweep.py`): 1,591 self-glued inputs × every rule, `redact_secrets` and `client.redact(mcp_shapes=False)`, at 1 MB, then the per-rule winners at 4 MB | See the sweep table in Changes in revision 2. Worst per rule at 4 MB is 0.110 s; `redact_secrets` 0.466 s; client path 0.937 s. The same sweep on revision 1 at 100 KB flags R10 (3.21 s), so the sweep can detect what it is looking for. |

## Test plan

All data is synthetic and obviously fake: `FAKE` runs, `FAKE0` runs, and a "MADEUP-NOT-A-KEY" base64 body. Non-ASCII inputs use `\u` escapes. **Builders must keep the runtime concatenation** (P7, P7b).

Full reference test file, 325 lines **[simulated: 202 passed]**:

```python
"""C3 proof: secret-shape redaction of tool results and MCP text (synthetic, obviously fake data).

Every fake credential is assembled at runtime so no complete token shape is committed.
"""

import sys
import time
from pathlib import Path
from typing import Any

import pytest

from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import (
    AgentLoop,
    AssistantMessage,
    LoopSnapshot,
    Message,
    ToolCall,
    ToolSpec,
)
from master_finhub.tools.mcp.client import McpClient, StdioServer, redact
from master_finhub.tools.secret_scan import RULES, redact_secrets

FAKE = "FAKE"
AWS = "AKIA" + FAKE * 3 + "0000"
AWS_TEMP = "ASIA" + FAKE * 3 + "0000"
GHP = "ghp_" + FAKE * 9
PAT = "github_pat_" + FAKE * 6
ANT = "sk-ant-" + "FAKE0" * 5
OAI = "sk-proj-" + "FAKE0" * 5
SLACK = "xoxb-" + "0000-FAKEFAKE"
JWT = "eyJ" + FAKE * 3 + "." + FAKE * 2 + "." + FAKE * 2
KEY_BODY = "TUFERVVQLU5PVC1BLUtFWQ"  # base64 of "MADEUP-NOT-A-KEY"
PEM = "-----BEGIN " + "PRIVATE KEY-----\n" + KEY_BODY + "\n-----END PRIVATE KEY-----"
SSH = (
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----\n" + KEY_BODY + "\n-----END OPENSSH PRIVATE KEY-----"
)
PGP = (
    "-----BEGIN "
    + "PGP PRIVATE KEY BLOCK-----\n"
    + KEY_BODY
    + "\n-----END PGP PRIVATE KEY BLOCK-----"
)
BEARER = "FAKE0" * 4
MCPKEY = "FAKE0" * 2

POSITIVES = [
    ("private-key", PEM, KEY_BODY),
    ("private-key", SSH, KEY_BODY),
    ("private-key", PGP, KEY_BODY),
    ("aws-access-key", AWS, AWS),
    ("aws-access-key", AWS_TEMP, AWS_TEMP),
    ("github-token", GHP, GHP),
    ("github-pat", PAT, PAT),
    ("anthropic-key", ANT, ANT),
    ("openai-key", OAI, OAI),
    ("slack-token", SLACK, SLACK),
    ("jwt", JWT, JWT),
]
WRAPS = ["{}", '"{}"', "'{}'", "KEY={}", "key: {}\n", '{{"k": "{}"}}', "start {} end"]


@pytest.mark.parametrize("wrap", WRAPS)
@pytest.mark.parametrize(("rule", "secret", "leak"), POSITIVES)
def test_each_rule_redacts_and_labels(rule: str, secret: str, leak: str, wrap: str) -> None:
    out, labels = redact_secrets(wrap.format(secret))
    assert leak not in out and f"[REDACTED:{rule}]" in out
    assert labels == (rule,)
    assert leak not in "".join(labels)


@pytest.mark.parametrize(
    ("text", "expected", "rule"),
    [
        (
            "Authorization: Bearer " + BEARER,
            "Authorization: Bearer [REDACTED:bearer-token]",
            "bearer-token",
        ),
        (
            "authorization: bearer " + BEARER,
            "authorization: bearer [REDACTED:bearer-token]",
            "bearer-token",
        ),
        ("Bearer " + JWT, "Bearer [REDACTED:bearer-token]", "bearer-token"),
        ("x-mcp-key: " + MCPKEY, "x-mcp-key: [REDACTED:mercury-mcp-key]", "mercury-mcp-key"),
        (
            '"x-mcp-key": "' + MCPKEY + '"',
            '"x-mcp-key": "[REDACTED:mercury-mcp-key]"',
            "mercury-mcp-key",
        ),
    ],
)
def test_header_rules_keep_their_prefix(text: str, expected: str, rule: str) -> None:
    assert redact_secrets(text) == (expected, (rule,))


def test_anthropic_wins_over_openai() -> None:
    assert redact_secrets(ANT)[1] == ("anthropic-key",)


def test_truncated_private_key_is_redacted_to_end() -> None:
    out, labels = redact_secrets("before\n" + PEM.split("\n-----END")[0])
    assert out == "before\n[REDACTED:private-key]" and labels == ("private-key",)


def test_two_private_keys_keep_the_text_between() -> None:
    out, _ = redact_secrets(PEM + "\nmiddle text\n" + PEM)
    assert out == "[REDACTED:private-key]\nmiddle text\n[REDACTED:private-key]"


def test_labels_are_deduplicated_in_table_order() -> None:
    out, labels = redact_secrets(f"{GHP} {AWS} {AWS}")
    assert out.count("[REDACTED:aws-access-key]") == 2
    assert labels == ("aws-access-key", "github-token")


NEGATIVES = [
    "a1b2c3d4e5" * 4,  # 40-hex git SHA
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # sha256
    "123e4567-e89b-12d3-a456-426614174000",  # UUID
    "01ARZ3NDEKTSV4RRFFQ69G5FAV",  # ULID
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
    "data:image/png;base64,QUJDAKIA" + FAKE * 3 + "0000==",  # key shape inside base64
    "-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----",
    "-----BEGIN CERTIFICATE-----",
    "task-runner-configuration-2024",
    "sk-component-header-wrapper",
    "xoxo-hugs-and-kisses-forever",
    "Bearer securities are negotiable",
    "bearer instruments",
    "AKIA" + FAKE * 3 + "000",
    "AKIA" + FAKE * 3 + "00000",
    "ghp_" + "A" * 19,
    "eyJhbGciOiJIUzI1NiJ9.payload",
    "x-mcp-key: short",
    "BSB 062-000 account 12345678",
    "[REDACTED]",
]


@pytest.mark.parametrize("text", NEGATIVES)
def test_false_positive_corpus_passes_unchanged(text: str) -> None:
    assert redact_secrets(text) == (text, ())


def test_redaction_is_idempotent() -> None:
    corpus = "\n".join([s for _, s, _ in POSITIVES] + ["Bearer " + BEARER, "x-mcp-key: " + MCPKEY])
    once, labels = redact_secrets(corpus)
    assert len(labels) == len(RULES)
    assert redact_secrets(once) == (once, ())


def test_mcp_redact_chains_to_shape_scan() -> None:
    out = redact(f"value=abcd1234 {AWS} {ANT}", ["abcd1234"])
    assert out == "value=[REDACTED] [REDACTED:aws-access-key] [REDACTED:anthropic-key]"


class _LeakyTool:
    spec = ToolSpec(name="echo", description="returns a fake .env", parameters={}, idempotent=True)

    def __init__(self, mode: str = "ok") -> None:
        self.mode = mode

    def run(self, arguments: dict[str, Any]) -> str:
        if self.mode == "raise":
            raise ValueError(f"cannot parse {AWS}")
        return f"AWS_ACCESS_KEY_ID={AWS}\nGITHUB_TOKEN={GHP}\n"


def _all_text(snaps: list[LoopSnapshot]) -> str:
    return "\n".join(m.content for s in snaps for m in s.messages)


@pytest.mark.parametrize("mode", ["ok", "raise", "guard"])
def test_loop_transcript_never_holds_the_fake_key(mode: str) -> None:
    snaps: list[LoopSnapshot] = []
    guard = (lambda call: f"denied, saw Bearer {BEARER}") if mode == "guard" else None
    loop = AgentLoop(ScriptedLLM(), [_LeakyTool(mode)], guard=guard, checkpoint=snaps.append)
    answer = loop.run("echo show the env file")
    text = _all_text(snaps) + answer
    for leak in (AWS, GHP, BEARER):
        assert leak not in text
    assert "[REDACTED:" in snaps[-1].messages[-2].content


def test_resume_rerun_path_is_redacted() -> None:
    call = ToolCall("call-1", "echo", {"text": "x"})
    snap = LoopSnapshot(1, (Message("user", "echo x"), Message("assistant", "", (call,))))
    snaps: list[LoopSnapshot] = []
    llm_reply = AssistantMessage(content="done")

    class _Done:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            return llm_reply

    AgentLoop(_Done(), [_LeakyTool()], checkpoint=snaps.append).resume(snap, in_flight="rerun")
    assert AWS not in _all_text(snaps) and "[REDACTED:aws-access-key]" in _all_text(snaps)


def test_mcp_known_values_are_replaced_before_shapes() -> None:
    value = "pw-" + AWS  # a configured secret that contains a token shape
    assert redact(f"conn={value}", [value]) == "conn=[REDACTED]"


@pytest.mark.parametrize("glue", ["cl\u00e9{}", "{}\u00e9", "\u5bc6\u94a5{}\u3002"])
@pytest.mark.parametrize(("rule", "secret", "leak"), POSITIVES)
def test_non_ascii_neighbours_do_not_hide_a_key(
    rule: str, secret: str, leak: str, glue: str
) -> None:
    out, labels = redact_secrets(glue.format(secret))
    assert leak not in out and labels == (rule,)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\u8ba4\u8bc1Bearer " + BEARER, "\u8ba4\u8bc1Bearer [REDACTED:bearer-token]"),
        ("\u5bc6\u94a5x-mcp-key: " + MCPKEY, "\u5bc6\u94a5x-mcp-key: [REDACTED:mercury-mcp-key]"),
        ("Bearer\t" + BEARER, "Bearer\t[REDACTED:bearer-token]"),
        ("Bearer\n" + BEARER, "Bearer\n[REDACTED:bearer-token]"),
        ('Bearer "' + BEARER + '"', 'Bearer "[REDACTED:bearer-token]"'),
        ("Bearer " + "F" * 16, "Bearer [REDACTED:bearer-token]"),
        ("Bearer " + "F" * 15, "Bearer " + "F" * 15),
        ("x-mcp-key=" + MCPKEY, "x-mcp-key=[REDACTED:mercury-mcp-key]"),
        ("X-MCP-KEY: " + MCPKEY, "X-MCP-KEY: [REDACTED:mercury-mcp-key]"),
        ("x-mcp-key: " + "F" * 8, "x-mcp-key: [REDACTED:mercury-mcp-key]"),
        ("x-mcp-key: " + "F" * 7, "x-mcp-key: " + "F" * 7),
        ("ghp_" + "F" * 20, "[REDACTED:github-token]"),
        ("github_pat_" + "F" * 20, "[REDACTED:github-pat]"),
        ("github_pat_" + "F" * 19, "github_pat_" + "F" * 19),
        ("sk-ant-" + "F" * 20, "[REDACTED:anthropic-key]"),
        ("sk-ant-" + "F" * 19, "sk-ant-" + "F" * 19),
        ("sk-" + "F0" * 10, "[REDACTED:openai-key]"),
        ("sk-" + "F0" * 9 + "F", "sk-" + "F0" * 9 + "F"),
        ("xoxb-" + "0000-FAKEF", "[REDACTED:slack-token]"),
        ("xoxb-" + "0000-FAKE", "xoxb-" + "0000-FAKE"),
        ("eyJ" + "F" * 10 + ".FAKEF.FAKEF", "[REDACTED:jwt]"),
        ("eyJ" + "F" * 9 + ".FAKEF.FAKEF", "eyJ" + "F" * 9 + ".FAKEF.FAKEF"),
        ("abc" + GHP, "abc" + GHP),  # glued to an ASCII word: not anchored (Does not cover #5)
        ("x" + SLACK, "x" + SLACK),
        ("x" + JWT, "x" + JWT),
        ("-" + JWT, "-" + JWT),  # R10 look-behind: a dash-glued JWT is not anchored (#5)
        # a bare header in prose wipes the rest (Does not cover #11): pinned, deliberate
        ("see -----BEGIN " + "PRIVATE KEY----- here\nmore", "see [REDACTED:private-key]"),
    ],
)
def test_lengths_contexts_and_anchors_are_pinned(text: str, expected: str) -> None:
    assert redact_secrets(text)[0] == expected


ADVERSARIAL = [
    "sk-",
    "sk-ant-",
    "sk-abc-",
    "Bearer ",
    "x-mcp-key: ",
    "AKIA",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "eyJ",
    "eyJaaaaaaaaaaa.",
    "eyJ-",
    "eyJaaaaaaaaaaaa-",
    # winners of the self-glued sweep (worst unit per rule at 1 MB)
    "-----BEGIN " + "PRIVATE KEY-----+",
    "Bearer\t" + "a" * 16 + "\n",
    'x-mcp-key="',
    'AKIA"',
    "ghp_" + "a" * 20 + "\n",
    "github_pat_" + "a" * 20 + "'",
    "sk-ant-" + "a" * 20 + "+",
    "sk-proj-" + "0" * 19 + "/",
    "xoxp-" + "a" * 10 + ":",
    "eyJ" + "a" * 10 + '.000000000"',
    "-----BEGIN ",
    "-----BEGIN " + "PRIVATE KEY-----",
]


@pytest.mark.parametrize("unit", ADVERSARIAL)
def test_adversarial_megabyte_stays_fast(unit: str) -> None:
    text = unit * (1_000_000 // len(unit))
    started = time.perf_counter()
    redact_secrets(text)
    assert time.perf_counter() - started < 2.0  # linear: well under 0.3 s; quadratic: minutes
    started = time.perf_counter()
    redact(text, ["aaaa", "0000"], mcp_shapes=False)  # the merged-span path of a successful result
    assert time.perf_counter() - started < 2.0


def test_mcp_values_and_shapes_are_merged_on_the_original_text() -> None:
    assert redact("id=" + AWS, ["0000"]) == "id=[REDACTED:aws-access-key]"
    assert redact("k=sk-ant-" + "abcde8080fghij" * 3, ["8080"]) == "k=[REDACTED:anthropic-key]"
    assert redact(GHP, ["ghp_FAKE"]) == "[REDACTED]"
    assert redact("v=ab+cd/ef==(x) end", ["ab+cd/ef==(x)"]) == "v=[REDACTED] end"  # re.escape


def test_touching_spans_stay_separate_and_overlaps_merge() -> None:
    assert redact(AWS + "-post", ["-post"]) == "[REDACTED:aws-access-key][REDACTED]"
    assert redact(AWS + "-post", ["0-po"]) == "[REDACTED:aws-access-key]st"


def test_successful_mcp_result_gets_the_known_value_pass() -> None:
    stub = str(Path(__file__).with_name("mcp_stub_server.py"))
    value = "stub-secret-value-1"
    cfg = StdioServer(name="stub", command=(sys.executable, stub), env={"MCP_STUB_SECRET": value})
    with McpClient(cfg) as c:
        assert c.call_tool("echo", {"text": f"token={value}"}).text == "token=[REDACTED]"
        assert c.call_tool("echo", {"text": AWS}).text == "[REDACTED:aws-access-key]"
        prose = "Bearer securities are negotiable"
        assert c.call_tool("echo", {"text": prose}).text == prose


def test_non_text_tool_result_fails_closed() -> None:
    class _IntTool:
        spec = ToolSpec(name="echo", description="returns an int", parameters={})

        def run(self, arguments: dict[str, Any]) -> str:
            return 7  # type: ignore[return-value]

    with pytest.raises(TypeError):
        AgentLoop(ScriptedLLM(), [_IntTool()]).run("echo x")
```

### Why the end-to-end test does not use `EchoTool`

`ScriptedLLM` (`fake_llm.py:17-20`) copies the prompt text into the echo call. With "echo <fake key>", the key would sit in the user message and in the tool-call arguments, which C3 does not scan by design (see "Does not cover"). So the test registers `_LeakyTool` under the name `echo`. It returns a fake `.env` that is not in the prompt. The check is then meaningful:
- every snapshot passed to the checkpoint hook (the same stream that `server/app.py:128` turns into SSE and that a `CheckpointStore` writes to `_workspace`), plus the final answer, holds no fake key.

### Must still pass, unmodified

- `tests/test_mcp_client.py`, in particular:
  - `test_redact_env_value_and_bearer` (`:162-168`). Its `Bearer tok.en-123` span from `SECRET_SHAPES` and its `ghp_` span both still become `[REDACTED]`; the value `abcd1234` becomes `[REDACTED]`; `short=ab` is untouched.
  - `test_is_error_maps_to_tool_error_and_redacts_env_secret` (`:73-78`).
  - `test_call_echo_round_trip` (`:68-70`). The text `hi` has no value of 4 or more characters and no shape.
- `tests/test_loop.py`, `tests/test_checkpoint.py`, `tests/test_server.py`, `tests/test_modes*.py` and `tests/test_evals.py`.
  - The only shape-like literal in the suite is `DUMMY_KEY = "sk-ant-test-DUMMY"` (`test_anthropic_llm.py:38`). It is 10 characters after `sk-ant-` and is never a tool result.
- **[Simulated]** whole suite with the change: no existing test failed. Five tests were deselected only because they read repo-root files that the scratch copy lacks: `test_lint_harness.py` ×4 and `test_checkpoint.py::test_checkpoints_folder_ignores_itself`.

### Mutation targets: one or more per rule, per call site and per ordering decision

All of these were applied one at a time on a scratch copy (`python -B`, a fresh process per mutant, 60 s timeout), against `pytest -x tests/test_secret_scan.py`. **Revision 2: 78 of 81 were killed. The three survivors are the same proven equivalents as before** **[simulated]**. Ids starting `X` are the judge's round-1 survivors.

| id | mutant | killed by |
|---|---|---|
| drop-<rule> ×10 | delete one row from `RULES` (each of R1-R10) | `test_each_rule_redacts_and_labels` for R1, R4-R10; `test_header_rules_keep_their_prefix` for R2 and R3 |
| pk-no-eot / pk-greedy / pk-no-block | drop `\|\Z` / `.*?` → `.*` / drop `(?: BLOCK)?` | truncated-key test / two-keys test / PGP positive |
| bearer-case | drop `re.IGNORECASE` from R2 | lowercase `authorization: bearer` |
| bearer-15 (X08) / bearer-17 (X09) | `{16,}` → `{15,}` / `{17,}` | `Bearer` + 15 negative / + 16 positive |
| bearer-nokeep | drop the `keep` group | exact-output header test |
| bearer-space (X14) | `\s+` → a single space | `Bearer\t…`, `Bearer\n…` |
| bearer-noquote (N4) | drop `["']?` after `\s+` | `Bearer "…"` |
| mcp-nokeep / mcp-noquote / mcp-class | as in revision 0 | header exact output / JSON form / idempotence |
| mcp-colon-only (X12) | `[:=]` → `:` | `x-mcp-key=…` |
| mcp-case (X13) | drop `re.IGNORECASE` from R3 | `X-MCP-KEY: …` |
| mcp-7 (X10) / mcp-9 (X11) | `{8,}` → `{7,}` / `{9,}` | 7-character negative / 8-character positive |
| aws-lead / aws-trail / aws-noasia | as in revision 0 | base64 `QUJDAKIA…` / `AKIA`+17 / `AWS_TEMP` |
| gh-min / gh-21 / gh-lead | `{20,}` → `{1,}` / `{21,}` / drop leading `\b` | `ghp_`+19 / `ghp_`+20 / `abc`+`ghp_…` |
| pat-min (X03) / pat-21 | `{1,}` / `{21,}` | `github_pat_`+19 / +20 |
| ant-min (X04) / ant-21 | `{1,}` / `{21,}` | `sk-ant-`+19 / +20 |
| oai-min (X05) / oai-21 / oai-lead | `{1,}` / `{21,}` / drop leading `\b` | `sk-`+19 with a digit / +20 / `task-runner-configuration-2024` |
| oai-nodigit | `need_digit` True → False | `sk-component-header-wrapper` |
| **oai-lookahead-restored** | revision 0's look-ahead pattern, `need_digit` False | `test_adversarial_megabyte_stays_fast[sk-]` (90 s timeout) |
| slack-broad / slack-min (X06) / slack-11 / slack-lead (X23) | `xox[a-z]` / `{1,}` / `{11,}` / drop leading `\b` | `xoxo-…` / `xoxb-`+9 / +10 / `x`+`xoxb-…` |
| jwt-twoseg / jwt-min (X07) / jwt-11 / jwt-lead (X22) | two segments / `{1,}` / `{11,}` / drop the leading look-behind | `eyJ….payload` / 9-character first segment / 10 / `x`+JWT |
| jwt-restore-b (r2) | look-behind → `\b` (revision 1) | `-`+JWT pin; `test_adversarial_megabyte_stays_fast[eyJ-]` |
| jwt-lookbehind-word-only (r2) | look-behind class without `-` | `-`+JWT pin |
| no-ascii-<rule> ×9 (R2-R10) and no-ascii-all | replace `re.ASCII` with `0` | `test_non_ascii_neighbours_do_not_hide_a_key`; CJK before `Bearer` and before `x-mcp-key` |
| no-merge | `merge_spans` never merges | `Bearer `+JWT exact output |
| labels-from-raw | labels from unmerged spans | `Bearer `+JWT labels `== ("bearer-token",)` |
| tie-later-wins | reverse the sort, so later spans win ties | anthropic/openai and Bearer/JWT label tests |
| keep-not-excluded | span starts at `m.start()` (header swallowed) | header exact-output tests |
| mcp-sequential-values-first | revision 0 `redact()` (replace values, then shapes) | `test_mcp_values_and_shapes_are_merged_on_the_original_text` |
| mcp-sequential-shapes-first | shapes then values | `test_mcp_known_values_are_replaced_before_shapes` |
| mcp-chain-removed / mcp-values-removed | drop table spans / drop value spans | chain test / ordering tests |
| mcp-success-no-values (N5) | restore `if is_error:` | `test_successful_mcp_result_gets_the_known_value_pass` |
| mcp-shapes-always (N5) | `mcp_shapes=True` on success | same test (Bearer prose) |
| loop-site / loop-success-only | as in revision 0 | end-to-end `[ok]` / `[raise]`, `[guard]` |
| loop-str-coerce (N7) | `redact_secrets(str(self._run_tool(call)))` | `test_non_text_tool_result_fails_closed` |
| mcp-no-escape (r2, N9, judge J14) | `re.finditer(secret, …)` without `re.escape` | `ab+cd/ef==(x)` value assert |
| mcp-table-error-only (r2, N9, judge J16) | table spans only when `mcp_shapes` | AWS echo on a successful stub result |
| merge-touching (r2, N12, judge J01) | `start <= end` merges touching spans | `AWS+"-post"` with value `-post` |
| merge-skip-1char (r2, N12, judge J02) | a 1-character overlap is not merged | `AWS+"-post"` with value `0-po` |
| **equivalent:** gh-trail (X20) | drop R5's trailing `\b` | cannot be killed: `[A-Za-z0-9_]` is the whole ASCII word class, so a greedy run always ends at a boundary |
| **equivalent:** no-ascii on R1 | drop `re.ASCII` from R1 | cannot be killed: R1 uses no `\b`, `\w`, `\s`, `\d` or case folding |
| **equivalent:** no-ascii in the comment | edit the comment text | not code |

QA should rerun at least oai-lookahead-restored (use a timeout), no-ascii-all, mcp-sequential-values-first, loop-site and bearer-15. Use `python -B` or a fresh module name per mutant: same-size, same-second rewrites can be served from a stale `.pyc`.

## Does not cover

Honest limits and known false positives/negatives:

1. **Opaque secrets with no vendor prefix are not covered.** Examples:
   - an AWS *secret* access key;
   - a Twilio auth token;
   - a Xero client secret;
   - a Mercury `MCP_AUTH_SECRET` outside an `Authorization: Bearer` or `x-mcp-key` header, **except** in MCP results from a server whose env holds that value (the N5 known-value pass);
   - database passwords, and `.env` values in general unless they have a listed shape.

   The OH65 assignment rule was deliberately not adopted (Decision 1).
2. **Short tokens are not covered.**
   - A Bearer token under 16 characters is not caught by R2. In MCP **error** text the existing `SECRET_SHAPES` still catches Bearer at any length.
   - An `x-mcp-key` value under 8 characters is not caught.
3. **Split secrets are not covered:**
   - secrets split across two tool results or stream chunks;
   - secrets cut by a tool's own truncation before the loop sees the text. `TailBuffer` keeps the last 64 KB, and MCP stderr lines are capped at 4096 characters. A fragment such as `KIA…` of an AWS key matches no anchored rule and is left visible.
   - The context clip cannot split a key, because redaction runs before `fit`.
4. **Encoded forms are not covered:** base64, URL-encoded (`%2D`), hex, JSON `\uXXXX` escapes, zero-width characters and rot13.
5. **A prefix glued to an ASCII word character is not covered:** `my_AKIA…`, `abcghp_…`, `xxoxb-…`, `xeyJ…`, and for R10 also a dash (`-eyJ…`, because of the look-behind, A38). These are pinned as negatives. The leading `\b` is what keeps base64 blobs safe, so this miss is the price of that.
   - With `re.ASCII` (A32), a non-ASCII neighbour on either side (é, CJK, `。`) **is** a boundary, so those keys are redacted.
   - **N11 (decision: follow-up, not C3).** Under `re.ASCII`, `\s` in R2 and R3 no longer matches non-ASCII spaces. `Bearer` followed by U+00A0 (no-break space) or U+3000 and then a token is not caught. The judge-verified follow-up is `(?u:\s)+` in R2 and R3.
   - **N8 (decision: Does-not-cover, not C3).** R2's and R3's token class contains `. = / - ~ +`. If two headers are glued together by one of those characters, the first match consumes the second header's name and the second token is left visible. Examples: `x-mcp-key: V1/x-mcp-key: V2`; `Bearer securities=Bearer <token>`. This needs contrived glue and was already true in revision 0. A follow-up could stop the class before a header name, with timing.
6. **Non-text content is not scanned.** MCP image and resource items never reach the loop; they become `[<type> content omitted]` (`client.py:354`). Binary is not scanned.
7. **These parts of the transcript are not scanned:**
   - the user's own prompt;
   - the model's assistant text;
   - the model's tool-call **arguments**. If the model copies a secret from the prompt into a call, that call is stored as typed.
   - Checkpoints written before C3 are not re-scanned on resume.
8. **Files the agent writes are not scanned.** The workspace fence governs where they go, not what is in them.
9. **Exceptions are covered only through `_execute` or `client.redact`.** An exception raised outside both, for example the CLI printing a non-MCP error, is not scanned.
   - A tool that returns a non-`str` makes the loop raise `TypeError` rather than store anything. This fails closed and is pinned (N7).
10. **Vendor formats not in the table are not covered:**
    - Stripe `sk_live_`;
    - Google `AIza`;
    - Slack `xapp-` and `xoxe`;
    - Linear `lin_api_` (dropped, Decision 1);
    - any future format.
11. **Known false positives:**
    - a 20+ character `sk-` kebab identifier that contains a digit, for example `sk-widget-v2-header-wrapper`;
    - `Bearer` (optionally quoted) followed by 16 or more token characters in prose;
    - a 16-character `AKIA[0-9A-Z]` code standing alone;
    - an `x-mcp-key:` placeholder of 8 or more characters in documentation;
    - **a bare `-----BEGIN … PRIVATE KEY-----` line quoted in prose or docs with no END line: everything after it is replaced** (N6, pinned). This is the cost of the truncated-key fail-safe.
    - In MCP text, any value of 4 or more characters configured in the server's env, such as `PORT=8080` or `prod`, is replaced wherever it occurs, now in successful results too (N5). This was already true for error text.
12. **This is not a DLP system.**
    - Cost: ten regex passes plus a sort of the match spans.
    - Measured **[simulated]** by the P13 sweep (1,591 self-glued inputs; winners re-run at 4 MB = `MAX_LINE_CHARS`):
      - every single rule at most 0.043 s at 1 MB and 0.110 s at 4 MB;
      - `redact_secrets` at most 0.203 s at 1 MB and 0.466 s at 4 MB;
      - `client.redact` on a successful result at most 0.248 s at 1 MB and 0.937 s at 4 MB.
    - The R8 look-ahead (A12) and the R10 `\b` start (A38) that made scans quadratic are gone. The 25-input timing test fails a regression of either.
    - **N10 (decision: follow-up, not C3).** The pre-existing `SECRET_SHAPES` JWT branch in `mcp/client.py:51` has no anchor and is quadratic on MCP **error** text. Measured **[simulated]**: `"eyJ"*N` takes 4.23 s and `"eyJ-"*N` 3.20 s at 100 KB. It predates C3, and C3 keeps it off successful results (`mcp_shapes=is_error`).
      - The one-token fix is to prefix that branch with `(?<![A-Za-z0-9_-])`, giving `|(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.…`.
      - Measured with that fix: 0.010 s at 100 KB and 0.40 s at 4 MB.
      - It is queued as a follow-up for Daniel.
    - Memory grows with the number of matches, one tuple per match.


## Authority List

| id | claim | evidence | slice |
|---|---|---|---|
| A1 | Secret rules are a fixed, ordered tuple of `(rule id, label, compiled regex)` | references/openharness/src/openharness/memory/team.py:24 | C3 |
| A2 | The scan reports which rules matched and never returns the matched text | references/openharness/src/openharness/memory/team.py:71; references/openharness/src/openharness/memory/team.py:76 | C3 |
| A3 | Labels are produced once per matching rule, in table order (no per-match duplicates) | references/openharness/src/openharness/memory/team.py:74 | C3 |
| A4 | Private-key header shape `-----BEGIN [A-Z ]*PRIVATE KEY-----` | references/openharness/src/openharness/memory/team.py:25 | C3 |
| A5 | R1 redacts the whole block up to the matching END line, or to end-of-text when END is missing, non-greedily, and also accepts the PGP ` BLOCK` suffix | NET-NEW. OH65 only detects the header because it refuses the write (team.py:88). A replacing scanner that stopped at the header would leak the body. Check: `test_truncated_private_key_is_redacted_to_end`, `test_two_private_keys_keep_the_text_between`, and the PGP positive fail under M-pk-no-eot, M-pk-greedy and M-pk-no-block. | C3 |
| A6 | AWS access key is `AKIA` + exactly 16 `[0-9A-Z]` between word boundaries | references/openharness/src/openharness/memory/team.py:26 | C3 |
| A7 | R4 also accepts the `ASIA` (temporary credential) prefix | NET-NEW. No reference lists it. Check: the `AWS_TEMP` positive fails under M-aws-noasia. | C3 |
| A8 | GitHub token shape `gh[pousr]_` + 20 or more `[A-Za-z0-9_]` | references/openharness/src/openharness/memory/team.py:27 | C3 |
| A9 | Fine-grained GitHub PAT shape `github_pat_` + 20 or more `[A-Za-z0-9_]` | references/openhands/src/utils/redact-mcp-secrets.ts:21 | C3 |
| A10 | Anthropic key shape `sk-ant-` + 20 or more `[A-Za-z0-9_-]` | references/openharness/src/openharness/memory/team.py:29 | C3 |
| A11 | OpenAI key shape `sk-` + 20 or more `[A-Za-z0-9_-]` | references/openharness/src/openharness/memory/team.py:28 | C3 |
| A12 | R8 requires at least one ASCII digit in the matched token. The check runs in Python after the match (no look-ahead), so kebab-case identifiers are not redacted and the scan stays linear. CHANGED r1 | NET-NEW, a false-positive control. Check: negative `sk-component-header-wrapper` fails under M-oai-nodigit; `test_adversarial_megabyte_stays_fast[sk-]` times out under M-oai-lookahead-restored. | C3 |
| A13 | Because rules replace text, `sk-ant-` must be tried before the broader `sk-` rule so the label is `anthropic-key` | NET-NEW. OH65 only labels, so its order (openai before anthropic at team.py:28-29) has no replacement effect. Check: `test_anthropic_wins_over_openai` fails under M-order-ant-oai. | C3 |
| A14 | Slack tokens start with `xox` + a letter + `-` | references/openhands/src/utils/redact-mcp-secrets.ts:23 | C3 |
| A15 | R9 narrows the letter to `[abprs]` and requires 10 or more trailing characters | NET-NEW. O12's `xox[a-z](?:-…)+` matches `xoxo-hugs`. Check: negative `xoxo-hugs-and-kisses-forever` fails under M-slack-broad. | C3 |
| A16 | JWT shape: three base64url segments, the first starting `eyJ` | references/openhands/src/utils/redact-mcp-secrets.ts:27 | C3 |
| A17 | A Bearer token is redacted with the `Bearer ` prefix kept, case-insensitively, over the charset `[A-Za-z0-9._~+/=-]` | references/openhands/src/utils/redact-mcp-secrets.ts:31 | C3 |
| A18 | The Bearer rule runs before the generic token shapes | references/openhands/src/utils/redact-mcp-secrets.ts:122; references/openhands/src/utils/redact-mcp-secrets.ts:126 | C3 |
| A19 | R2 requires 16 or more token characters (O12 uses 8) so finance prose ("bearer securities", "Bearer instruments") is untouched | NET-NEW, a false-positive control. Check: negatives `Bearer securities are negotiable` and `bearer instruments` fail under M-bearer-min8. | C3 |
| A20 | Known config values are replaced before any token-shape pattern | references/openhands/src/utils/redact-mcp-secrets.ts:118 | C3 |
| A21 | The Mercury CRM MCP secret is sent as `Authorization: Bearer` or as an `x-mcp-key` header | references/deepseek_harness/scripts/railway-mercury-mcp.cordis.yml:9 | C3 |
| A22 | R3 redacts the `x-mcp-key` value (8 or more token characters), keeps the header name and optional JSON quotes, and its token class excludes `[` so labels are never re-matched | NET-NEW (regex). Check: header exact-output cases fail under M-mcp-nokeep and M-mcp-noquote; `test_redaction_is_idempotent` fails under M-mcp-class. | C3 |
| A23 | OH65's generic assignment rule needs a word boundary before `secret`, `token`, `api key` or `password`, so it cannot match `AUTH_TOKEN=`; it is not adopted | references/openharness/src/openharness/memory/team.py:30 | C3 |
| A24 | No Twilio or Xero token shape exists under `references/`, so no dedicated Twilio or Xero rule is added | NET-NEW (absence). Check: `grep -rIn -i twilio references --include=*.py --include=*.ts` returns 0 lines, and `grep -rIn -i xero references --include=*.py --include=*.ts` returns only `references/openhands/global.d.ts` (the word "Prefixer", not a token). Either grep finding a pattern would refute this row. | C3 |
| A25 | `AgentLoop._execute` is the single point every tool result, guard denial, unknown-tool text and exception text passes through, for both the normal and the resume-rerun path; C3 redacts there | NET-NEW (runtime code: `src/master_finhub/runtime/loop.py:184`, `:211`, `:216-228`). Check: `test_loop_transcript_never_holds_the_fake_key[ok,raise,guard]` and `test_resume_rerun_path_is_redacted` fail under M-loop-site and M-loop-success-only. | C3 |
| A26 | Redaction happens before the message is appended, checkpointed, streamed or clipped, so no snapshot, SSE event or `_workspace` file ever holds the match | NET-NEW. Check: the end-to-end test collects every snapshot from the checkpoint hook and asserts the fake keys are absent; it fails under M-loop-site. | C3 |
| A27 | `mcp/client.py:redact` matches known values, `SECRET_SHAPES` (error text only) and the `secret_scan` table on the original text, then merges overlapping spans and replaces each merged span once. On a tie the value span names it. CHANGED r1 | NET-NEW. Check: `test_mcp_values_and_shapes_are_merged_on_the_original_text` fails under mcp-sequential-values-first; `test_mcp_known_values_are_replaced_before_shapes` fails under mcp-sequential-shapes-first; `test_mcp_redact_chains_to_shape_scan` fails under mcp-chain-removed; `tests/test_mcp_client.py` passes unmodified. | C3 |
| A28 | Redaction is idempotent: no `[REDACTED…]` label matches any rule | NET-NEW. Check: `test_redaction_is_idempotent` fails under M-mcp-class. | C3 |
| A29 | Each match is replaced by `[REDACTED:<rule id>]`, never by anything derived from the match | NET-NEW. OH65 refuses instead of replacing; O12 uses one fixed placeholder (redact-mcp-secrets.ts:127). Check: `test_each_rule_redacts_and_labels` asserts `leak not in out` and `f"[REDACTED:{rule}]" in out`. | C3 |
| A30 | Every rule keeps a false-positive guard: 40-hex SHA, sha256, UUID, ULID, base64 PNG prefix (including an embedded key shape), public key and certificate headers, kebab `sk-`, `xoxo`, finance "bearer" prose and length-boundary near-misses all pass unchanged | NET-NEW. Check: `test_false_positive_corpus_passes_unchanged` (20 cases) fails under M-aws-lead, M-aws-trail, M-gh-min, M-oai-nodigit, M-oai-lead, M-slack-broad, M-jwt-twoseg and M-bearer-min8. | C3 |
| A31 | Test credentials are synthetic and assembled at runtime, so no complete token shape is committed | NET-NEW (repo policy, `runtime-builder.md` synthetic-data rule). Check: the P7 grep returns 0 lines. | C3 |
| A32 | Every rule is compiled with `re.ASCII`, so a key next to a non-ASCII letter (é, CJK, `。`) still meets its `\b` anchors (judge S1) | NET-NEW. Check: `test_non_ascii_neighbours_do_not_hide_a_key` and the CJK-before-`Bearer` and CJK-before-`x-mcp-key` cases fail under no-ascii for each of R2-R10 and under no-ascii-all. R1 is an equivalent mutant (no `\b`, `\w`, `\s`, `\d` or case folding). | C3 |
| A33 | `redact_secrets` collects every rule's spans on the original text and replaces the union of overlapping spans once. The earliest start names a merged span, and on a tie table order decides. Labels are the names of the merged spans (judge S2) | NET-NEW. Check: the `Bearer `+JWT exact-output and label tests fail under no-merge and labels-from-raw; the anthropic/openai and Bearer/JWT label tests fail under tie-later-wins. | C3 |
| A34 | `call_tool` runs the known-value pass and the C3 table on successful MCP results too; `SECRET_SHAPES` stays error-only so its any-length Bearer does not alter successful prose (judge N5) | NET-NEW. Check: `test_successful_mcp_result_gets_the_known_value_pass` fails under mcp-success-no-values and under mcp-shapes-always. | C3 |
| A35 | R2 accepts one optional quote between `Bearer ` and the token and keeps it (judge N4) | NET-NEW. Check: the `Bearer "…"` exact-output case fails under bearer-noquote. | C3 |
| A36 | Every rule, `redact_secrets` and the successful-result `client.redact` path finish each of 25 adversarial 1 MB inputs in under 2 s. Measured over 1,591 self-glued inputs: worst rule 0.110 s, `redact_secrets` 0.466 s, client 0.937 s, all at 4 MB. CHANGED r2 | NET-NEW (performance bound). Check: `test_adversarial_megabyte_stays_fast` (25 inputs, both calls) fails or times out under oai-lookahead-restored and jwt-restore-b. | C3 |
| A37 | A tool result that is not a `str` makes `_execute` raise `TypeError` out of the loop instead of being stored, which fails closed (judge N7) | NET-NEW. Check: `test_non_text_tool_result_fails_closed` fails under loop-str-coerce. | C3 |
| A38 | R10 starts with the look-behind `(?<![A-Za-z0-9_-])` instead of `\b`, so a dash-joined run gives at most one JWT start (linear). A JWT glued after `-` is therefore no longer redacted | NET-NEW. Check: the `-`+JWT negative pin fails under jwt-lookbehind-word-only and jwt-restore-b; `test_adversarial_megabyte_stays_fast[eyJ-]` times out under jwt-restore-b. | C3 |
| A39 | Known MCP values are matched literally (`re.escape`), so a value containing regex metacharacters is redacted | NET-NEW. Check: the `ab+cd/ef==(x)` assert fails under mcp-no-escape. | C3 |
| A40 | `merge_spans` joins spans that overlap by even one character and keeps spans that only touch as separate tags | NET-NEW. Check: `test_touching_spans_stay_separate_and_overlaps_merge` fails under merge-touching and merge-skip-1char. | C3 |
