TOTALS: UPHELD 30 / REJECTED 3 / UNVERIFIED 0 — round 1/3

# Adversarial verdict: C3 secret-shape redaction (revision 0)

- Audited file: _workspace/02_strategy-architect_C3.md (revision 0), `## Authority List` A1-A31. The launch prompt also asked for substance checks (a)-(i).
- Audited: 2026-10-03
- References opened: `references/openharness/src/openharness/memory/team.py:1-90`, `references/openhands/src/utils/redact-mcp-secrets.ts:1-130`, `references/deepseek_harness/scripts/railway-mercury-mcp.cordis.yml:1-19`, `references/LICENSES.md:9,12,14`. Nothing is cited from `references/autogpt/autogpt_platform/`.
- Simulation: scratch copy at `/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c3j/full`. `references/` was symlinked and read only. `secret_scan.py` and the test file were extracted byte-for-byte from design lines 188-236 and 295-495. The loop.py and client.py edits were applied as given. My diff equals the design's hunks. Every run used `python -B` with `PYTHONDONTWRITEBYTECODE=1`. Nothing was written into the repo except this file.
- Totals: 31 Authority List rows plus 2 substance rows (S1, S2). Both substance rows count toward REJECTED. The REJECTED rows are A12, S1 and S2.

## Claims

| id | verdict | cited | found at cited line (±5) | reason / correct location |
|---|---|---|---|---|
| A1 | UPHELD | openharness team.py:24 | `SECRET_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (` | — |
| A2 | UPHELD | team.py:71; :76 | docstring "Return possible secrets in content without exposing matched values."; `matches.append(SecretMatch(rule_id=rule_id, label=label))` | — |
| A3 | UPHELD | team.py:74 | `for rule_id, label, pattern in SECRET_RULES:` with `if pattern.search(content):` at :75, so one entry per rule | — |
| A4 | UPHELD | team.py:25 | `re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")` | — |
| A5 | UPHELD | NET-NEW (team.py:88) | :87-88 build the "cannot be written to team memory" refusal | The reason is stated. All three named mutants (no-eot, greedy, no-block) were killed in my run. The unterminated case behaves as stated: `"before\n" + header + body` becomes `before\n[REDACTED:private-key]`. CRLF, JSON-escaped `\n` and ENCRYPTED/OPENSSH/PGP headers are also redacted. See note N6 on over-redaction |
| A6 | UPHELD | team.py:26 | `re.compile(r"\bAKIA[0-9A-Z]{16}\b")` | — |
| A7 | UPHELD | NET-NEW | — | M-aws-noasia was killed |
| A8 | UPHELD | team.py:27 | `re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")` | — |
| A9 | UPHELD | redact-mcp-secrets.ts:21 | `/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g` | — |
| A10 | UPHELD | team.py:29 | `re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")` | — |
| A11 | UPHELD | team.py:28 | `re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")` | — |
| A12 | **REJECTED** | NET-NEW | — | **Substance: the digit look-ahead makes R8 quadratic (ReDoS).** `(?=[A-Za-z0-9_-]*[0-9])` runs at every `\bsk-` start and scans to the end of the token run whenever the run has no digit. Measured R8 time (one process per size): `"sk-"*(N//3)` takes 0.19 s at 10 KB and **19.1 s at 100 KB** (100x for 10x the input), and it timed out at 30 s at 1 MB (extrapolated about 1900 s). `"sk-ant-"*(N//7)` takes 8.3 s at 100 KB. Two realistic digit-free inputs: `"-".join(["sk"]*60000)` (180 KB) took **62.7 s**, and `("sk-"+"abc-")*25000` (175 KB) took **25.2 s**. MCP text may be up to `MAX_LINE_CHARS` = 4 M characters (`client.py:39`), and a file the agent reads has no cap, so one tool result can stall `_execute` for hours. This also falsifies Does-not-cover #12 ("ten linear regex passes"). **Fix:** match the whole token with `\bsk-[A-Za-z0-9_-]{20,}\b` and keep the digit requirement in a named replacement function (a `def`, which avoids the mypy lambda problem in note 2). If no digit is present, the function returns `m.group(0)` and does not record the label. Measured: 0.003 s at 100 KB, 0.032 s at 1 MB, 0.127 s at 4 MB. Add a large-margin timing test, e.g. `redact_secrets("sk-"*100_000)` in under 2 s (today 19 s, fixed 0.003 s), so a regression cannot pass. Strike the "linear" sentence in #12 |
| A13 | UPHELD | NET-NEW (team.py:28-29) | :28 openai, :29 anthropic, in that order | M-order-ant-oai was killed |
| A14 | UPHELD | redact-mcp-secrets.ts:23 | `/\bxox[a-z](?:-[A-Za-z0-9]+)+/g` | — |
| A15 | UPHELD | NET-NEW | — | M-slack-broad was killed. O12's pattern does match `xoxo-hugs` |
| A16 | UPHELD | redact-mcp-secrets.ts:27 | `/\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b/g` | — |
| A17 | UPHELD | redact-mcp-secrets.ts:31 | `const BEARER_PATTERN = /\bBearer\s+[A-Za-z0-9._~+/=-]{8,}/gi;` and :30 "keeps its prefix" | — |
| A18 | UPHELD | redact-mcp-secrets.ts:122; :126 | `redacted = redacted.replace(BEARER_PATTERN, ...)`; `for (const pattern of GENERIC_SECRET_PATTERNS)` | — |
| A19 | UPHELD | NET-NEW | — | M-bearer-min8 was killed, so the check can fail. The value 16 itself is not pinned: my mutants `{15,}` and `{17,}` both survive. See N1 |
| A20 | UPHELD | redact-mcp-secrets.ts:118 | `for (const value of collectMcpSecretValues(server)) {` (replacement at :119), before :122 | The citation is right, but the order has a partial-leak side. See S2 |
| A21 | UPHELD | railway-mercury-mcp.cordis.yml:9 | "`Authorization: Bearer` or `x-mcp-key`" (:8-9); `Bearer ${process.env.MERCURY_MCP_TOKEN}` at :19 | deepseek_harness is MIT (`LICENSES.md:12`). Only a fact is used |
| A22 | UPHELD | NET-NEW | — | M-mcp-nokeep, M-mcp-noquote and M-mcp-class were all killed. The value 8 is not pinned (`{6,}` and `{9,}` survive), and neither are the `=` form nor case-insensitivity. See N1 |
| A23 | UPHELD | team.py:30 | `(?i)\b(secret\|token\|api[_-]?key\|password)\s*[:=]...` | Verified by running the regex. `AUTH_TOKEN=abcdefghijklmnop` and `DB_PASSWORD=...` give False. `token=...` and `password = get_password_from_vault()` give True |
| A24 | UPHELD | NET-NEW (absence) | — | Both greps reproduce: twilio `--include=*.py --include=*.ts` gives 0 lines; xero gives only `openhands/global.d.ts:6,16` (`PrefixerOptions`). Either grep can fail. Prose nit outside the row: design :104 says an unrestricted grep finds only `autogpt/.secrets.baseline`. It also hits two `autogpt_platform` JSON fixtures, which are not cited and hold no pattern |
| A25 | UPHELD | NET-NEW (loop.py:184, :211, :216-228) | :184 `_drive` → `self._execute(call)`; :211 `_uncertain` → `return self._execute(call)`; :216-228 `_execute` body | Traced every path. `tool.run` is called only at `loop.py:226`. The only `Message(...)` constructors outside loop.py are `context.py:132` (a summary of already-stored messages), `team.py:371` (a coworker's mail, which is model-authored) and `dag_engine.py:312` (reload of stored snapshots). All five `AgentLoop` users (cli:132, app:138, subagent:315, team:356, runner:146) go through `_drive`/`_uncertain`. Subagent output re-enters the parent through the parent's `_execute`. Server SSE errors carry the class name only (`app.py:147-150`). `_uncertain`'s unknown-tool and guard branches return the constant `UNCERTAIN_RESULT`. The only uncovered paths are already in Does-not-cover: #7 (prompt, assistant text, tool-call arguments, team mail and board results, and re-save of pre-C3 snapshots in `resume()` at :170), #8 (files written) and #9. Mutants M-loop-site, M-loop-success-only (with the wrapper removed), the resume-only `_drive` mutant and my X01 (`_uncertain` → `_run_tool`) were all killed |
| A26 | UPHELD | NET-NEW | — | Redaction runs inside `_execute`, before the append at :184, `_save` at :185 and `fit` at :191. M-loop-site was killed |
| A27 | UPHELD | NET-NEW | — | M-mcp-chain and M-mcp-order were killed, and `tests/test_mcp_client.py` passes unmodified within the 1008. The partial-leak side of the ordering is S2 |
| A28 | UPHELD | NET-NEW | — | Re-scanning a mixed corpus that already holds `[REDACTED]` and `[REDACTED:<rule>]` labels gives `(once, ())`. M-mcp-class was killed |
| A29 | UPHELD | NET-NEW (redact-mcp-secrets.ts:127) | `redacted = redacted.replace(pattern, REDACTED_MCP_SECRET_VALUE);` | My X17 (append `\g<0>` after the label) was killed. Labels never contain the match |
| A30 | UPHELD | NET-NEW | — | The 20-case corpus passes. All 8 named mutants were killed in my run |
| A31 | UPHELD | NET-NEW | — | P7 can fail: a planted `"AKIA..."` literal is found at :202. Running the scanner over the test file's own text returns `()`. P7 does not cover every shape. See N3 |

## Guardrails

| slice | G1 fees | G2 borrow | G3 slippage | G4 look-ahead | G5 survivorship | G6 train/test |
|---|---|---|---|---|---|---|
| C3 | N/A: no pricing, returns or backtest | N/A | N/A | N/A | N/A | N/A: touches no eval scoring, verifier or data split (design :76) |

## Substance

| id | verdict | finding | evidence | fix |
|---|---|---|---|---|
| S1 | **REJECTED** | **Unicode-aware `\b` leaks keys that sit next to non-ASCII letters, and the design does not disclose it.** Python `str` patterns treat `é` and CJK characters as word characters, so the leading and trailing `\b` on R4-R8 and R10 fail. Does-not-cover #5 discloses only ASCII glue (`my_AKIA`, `xghp_`) and only the leading side, and it calls the miss "the price" of keeping base64 safe | `redact_secrets("clé"+AWS)` returns `('cléAKIAFAKEFAKEFAKE0000', ())`. `AWS+"é"` gives `()`. `"密钥"+GHP+"。"` gives `()`, so the whole token leaks. CJK text with no space before a token is ordinary | Add `re.ASCII` to every rule (for R2/R3 combine it with `re.IGNORECASE`; for R1 with `re.DOTALL`). Verified: the three cases above are redacted, the base64-embedded `QUJDAKIA…` negative and `MY_AKIA…` stay unchanged, and all 113 design tests still pass. Add one Unicode-adjacent positive per side to the tests |
| S2 | **REJECTED** | **Value-first ordering in `client.redact` causes a partial leak, and the design presents the order as leak-free.** A configured value of 4 or more characters (any env value, not only secrets: `PORT=8080`, `0000`, `test`, `prod`) that occurs inside a token is replaced first. The `[REDACTED]` it leaves breaks the token class, so no shape rule matches what remains. The loop's second scan sees the same split text and cannot recover it. Decision 2 argues only the opposite case (`pw-`+AWS) | `redact("id="+AWS, ["0000"])` gives `id=AKIAFAKEFAKEFAKE[REDACTED]`, leaking 16 of 20 characters. `redact("k=sk-ant-"+"abcde8080fghij"*3, ["8080"])` gives `k=sk-ant-abcde[REDACTED]fghijabcde[REDACTED]…`, leaking nearly the whole key. `redact(GHP, ["ghp_FAKE"])` gives `[REDACTED]FAKEFAKE…`, leaking 32 characters. Before C3 those AWS and Anthropic keys leaked whole, so this is not a regression, but the design's sentence that value-first replaces "whole" is half true | Either (a) compute the spans of known values and of every shape match on the **original** text, merge overlaps, and replace each merged span once (this fixes both the `pw-` case and these cases), or (b) at minimum add the case to Does-not-cover, with a test that pins the current behaviour so a later change is deliberate |

## Re-run of the design's proof (all pass; not findings)

| check | design expects | I got |
|---|---|---|
| P1 | 113 passed | `113 passed in 0.13s` |
| P2 | before 895/10; after 1008/10 | before `895 passed, 10 skipped`; after `1008 passed, 10 skipped` (full scratch tree with `scripts/`, `.claude/`, `skills/` and `.gitignore`, using the repo `.venv` interpreter) |
| P3 | mypy --strict clean, 38 files | `Success: no issues found in 38 source files` |
| P4 | ruff and black clean | `All checks passed!`; `66 files would be left unchanged.` |
| P5 | 4 lines | loop.py:16, :220; client.py:32, :111 |
| P6 | 2 | 2 (docstring lines 3-4) |
| P7 | 0 lines | 0 lines (rc 1); it can fail on a planted `AKIA` literal |
| P8 | 0 | **rc 2 with an error** in this shell (`LANG` empty): "character code point value in \x{} or \o{} is too large". Under `LC_ALL=C.UTF-8` it gives 0 lines and finds a planted Hangul character. See N2 |
| anchors (i) | loop.py :184, :211, :216-228; client.py :47-52, :107-110, :141, :177, :302, :358 | all exact. `stream.py:44` TailBuffer is at :45, and `context.py:63` clip is at :62-63, both within tolerance |

### Mutants

- **Design mutants spot-checked: 29 of 35, all killed.** M-pk-no-eot, M-pk-greedy, M-pk-no-block, M-bearer-case, M-bearer-min8, M-bearer-nokeep, M-mcp-nokeep, M-mcp-noquote, M-mcp-class, M-aws-lead, M-aws-trail, M-aws-noasia, M-gh-min, M-oai-nodigit, M-oai-lead, M-slack-broad, M-jwt-twoseg, M-labels-dup, M-labels-all, M-order-ant-oai, M-mcp-chain, M-mcp-order, M-loop-site, M-loop-success-only, the resume-only `_drive` mutant, M-drop-jwt, M-drop-mercury-mcp-key and M-drop-github-pat.
- **My own mutants: 23. Killed 9.**
  - X01: resume call site `_uncertain` → `_run_tool`.
  - X02: AWS `{16}` → `{15,16}`.
  - X15: drop `re.DOTALL`.
  - X16: END must be a bare `PRIVATE KEY`.
  - X17: label appends the match.
  - X18: `redact()` skips the value pass.
  - X19: drop the AWS trailing `\b`.
  - X24: drop the leading `\b` on openai.
  - M-loop-success-only, run faithfully with the outer wrapper removed.
- **Survived 14:**
  - Minimum lengths: X03 github-pat `{20,}`→`{1,}`; X04 anthropic `{20,}`→`{1,}`; X05 openai `{20,}`→`{1,}`; X06 slack `{10,}`→`{1,}`; X07 jwt first segment `{10,}`→`{1,}`; X08 Bearer `{16,}`→`{15,}`; X09 Bearer `{16,}`→`{17,}`; X10 x-mcp-key `{8,}`→`{6,}`; X11 x-mcp-key `{8,}`→`{9,}`.
  - Context forms: X12 x-mcp-key `[:=]`→`:` (the `=` form is untested); X13 x-mcp-key without `IGNORECASE`; X14 Bearer `\s+`→a single space (tab and newline are untested).
  - Word boundaries: X20 github trailing `\b` dropped; X22 jwt leading `\b` dropped; X23 slack leading `\b` dropped.
  - This does not breach the backlog proof bar (`01b…backlog.md:50`: "Mutants that drop a rule or the call site must be killed"), which is met, so it is not counted. See N1.

### Regex timing (d): wall time per process, sizes 10 KB / 100 KB / 1 MB

- **Linear, every case about 0.10-0.16 s at 1 MB:**
  - an unterminated `BEGIN RSA PRIVATE KEY` followed by 1 MB of `A`;
  - repeated `BEGIN PRIVATE KEY` headers with no END;
  - `-----BEGIN ` repeats, `-----BEGIN ` plus 1 MB of spaces, and `BEGIN` followed by A-Z words with no PRIVATE;
  - 1 MB of `A` and of `Ab+/=`;
  - `Bearer ` plus 1 MB of `a` or of spaces, and `Bearer ` repeats;
  - `x-mcp-key: ` repeats, `x-mcp-key` plus spaces, and `x-mcp-key:` plus spaces;
  - repeats of `AKIA`, `ghp_`, `xoxb-` and `eyJ`;
  - `ghp_`, `eyJ` and `sk-` each followed by 1 MB of letters;
  - unfinished JWT segment chains.
- **Quadratic: R8 only** (A12).

## Notes (not counted; worth fixing in the same revision)

- **N1 Boundary and context tests.** Add a positive and a negative at each minimum length:
  - Bearer at 15 and 16 characters;
  - x-mcp-key at 7 and 8;
  - `sk-ant-`, `sk-` (with a digit) and `github_pat_` at 19 and 20;
  - `xoxb-` at 9 and 10;
  - JWT with a 9-character and a 10-character first segment.

  Also add `x-mcp-key=…`, `X-MCP-KEY: …`, `Bearer\t…`, and a glued-suffix negative for GitHub, JWT and Slack. This kills X03-X14, X20, X22 and X23, and it pins the numbers that A19 and A22 state.
- **N2 P8.** Prefix the grep with `LC_ALL=C.UTF-8`. Without it, the grep exits 2 with an error instead of reporting 0 lines.
- **N3 P7.** The regex omits `github_pat_`, `xox[abprs]-`, three-segment `eyJ` and `Bearer <16+>`. A planted `github_pat_…` or `xoxb-…` literal passes P7. These are exactly the shapes that GitHub push protection checks. Extend the alternation.
- **N4 Quoted Bearer.** `Bearer "FAKE0FAKE0FAKE0FAKE0"` is not redacted. Add it to Does-not-cover, or allow an optional quote in the `keep` group.
- **N5 Successful MCP results get no known-value pass.** `call_tool` redacts env values only `if is_error:` (`client.py:357-358`). A Mercury `MCP_AUTH_SECRET` (no prefix) echoed in a **successful** result is caught by neither layer, even though the client holds the value. Dropping that `if` is a one-line change that closes it. Today it is only covered by the general entry in Does-not-cover #1.
- **N6 Over-redaction.** Any tool output that quotes a bare `-----BEGIN PRIVATE KEY-----` line, such as a README or docs explaining PEM, loses everything after it. Add this to known false positives #11.
- **N7 Fail-closed edge.** `_execute` now calls `redact_secrets` outside `_run_tool`'s `try`. A tool that returns a non-`str` now raises `TypeError` out of the loop instead of being stored. This is acceptable (fail-closed), but say so in the interface note.
