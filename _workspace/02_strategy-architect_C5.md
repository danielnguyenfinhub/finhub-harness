# C5 adoption design: Claude Code hook kit for generated harnesses (revision 4)

Target shape: plugin skill only. One new reference file, one new stdlib script, one new test file, edits in `SKILL.md` Steps 3, 5 and 6 plus its checklist and reference list, and three edits in `surfaces.md`. No lint rule, no packager change, no change to any existing test. Effort S/M (script 162 lines; the backlog row scored effort 0.6 and called it M, and the script grew from 88 to 162 lines over the audit, so S/M is the honest label).

## Revision 4 (judge round 3: UPHELD 41, REJECTED 3 (A27, A37, A38), blocking findings B6-B8; extra round authorised by Daniel 2026-10-04, narrow scope)

Changed claims: A21, A22, A26, A27, A32, A37, A38, A43 (marked `CHANGED r4`; A21, A22, A26 and A32 only for stale mutant ids, targets or wording). New NET-NEW rows A45-A48 are appended. All other rows are byte-identical to revision 3. The Revision 3 and Revision 2 sections below are kept. I reproduced each failure on revision 3 before changing anything: `cat /h/.netrc ` followed by `$BIG ` x 33,313 took 3.3 s with a 5,883-byte value and 8.1 s with 11,877 bytes, and a 94,000-byte value was still running at 40 s; a path value of `$BIG` x 800 (5,883 bytes) was allowed after a 0.9-second expansion.

| Fix | Answers | What changed |
|---|---|---|
| Variable expansion is bounded. `expand_vars()` replaces `os.path.expandvars`: one linear `re.sub` over the same pattern (`\$(\w+|\{[^}]*\})`, ASCII), which adds up the final size as it goes and raises before building a result longer than 200,000 characters (command) or 4096 (path value). The command-length cap is checked first, so the work is at most one pass over 200,000 characters plus one dictionary lookup per reference. The refusal is exit 2 through the fail-closed path (`check failed (ValueError)`). | B6, A27 | `expand_vars`, `candidates`, `expand` in D1. Measured: the judge's case with 1,111, 5,883, 11,877 and 94,000-byte values: 0.02 s each, exit 2. `cat /h/.netrc $BIG` with a 94 KB value: exit 2 `sensitive-path` in 0.02 s; `echo $BIG $BIG` (188,000 characters) is allowed; `$BIG` three times (282,000) is refused. Path value `$BIG` x 800 with 94,000 bytes: exit 2 in 0.02 s. 49,000 references of a 3-byte value 0.07 s. Tests `test_variable_expansion_cannot_outlast_the_hook`, `test_command_expansion_bound_is_200000`, `test_path_value_expansion_bound_is_4096`, `test_variable_names_follow_the_stdlib_pattern`; 11 new mutants. hooks.md: the "linear and small" sentence is replaced and a "Variable expansion" row is added. |
| Brace expansion that splits a name is a named limit again, with the judge's examples, and a test pins both the behaviour and the sentence. | B7, A37 | hooks.md "Does not cover"; `test_name_splitting_brace_expansion_is_a_documented_pass`, `test_the_brace_limit_stays_documented`. Every named grep in the Authority List was re-run against the current files: table in Proof 11. |
| The budget wording is corrected: every distinct word of any kind costs the depth of the working directory plus 2 components, so the budget runs out after 16,384 // (depth + 2) distinct words. I measured it by bisection through the script: depth 1: 5,461; depth 3: 3,276; depth 6: 2,048; depth 8: 1,638; depth 15: 963; each equals the formula. | B8, A38, A43 | hooks.md (Symlinks row, false-positive list), Deny-rules table, A38, A43 and its grep; `test_budget_is_16384_over_depth_plus_two_distinct_words` at depths 1, 8 and 15, each a pass at the threshold and a refusal one word later. |
| Six test gaps closed: `/h/.SSH` (X06), a blank path under a credential `cwd` (X07), `"\u00e9 " * 99,999` (X13), `cat ~\.kube\config` and `C:\Users\u\.docker\config.json` (X15), `{"file_path": 5}` under a credential `cwd` (X17), a `.SSH` link to an innocent directory (X24). | X-series | D2; the six judge mutants plus five more of his are in the runner. |
| One-line doc fixes: A32 no longer calls `dedupe-dropped` an equivalent survivor (the runner kills it); A21, A22, A26 use the runner's current mutant ids and targets; the false-positive list adds URLs and words ending in a credential file name and variables that hold a credential path (`echo $KUBECONFIG`); the effort label is S/M. | Follow-ups F4, F6, F7 | hooks.md, Authority List, header. |

Decisions Daniel should know about:
1. `os.path.expandvars` is replaced by a 15-line bounded version of the same pattern, for command words and path values alike. A command or path value whose expansion passes 200,000 or 4096 characters now exits 2. The path-value half is a new false positive but a path longer than `PATH_MAX` cannot be opened anyway.
2. The budget false positive is larger than r3 said: any command with more than about 16,384 / (depth + 2) distinct words, so a long inline script or SQL statement written through Bash can be refused in a deep project (about 2,000 words at depth 6). Use the Write tool for long content. I did not raise the budget; it is the runtime guard's number.
3. Still not fixed, by instruction: `~user` words cost one `getpwnam` each (F1), the protocol test is a drift lint with listed limits (F2), and the hash test prints bare hashes (F3).

## Revision 3 (judge round 2: UPHELD 33, REJECTED 4, blocking findings B1-B5; last round)

Changed claims: A24, A25, A27, A31, A33 (marked `CHANGED r3`). New NET-NEW rows A38-A44 are appended. Rows A1-A23, A26, A28-A30, A32 and A34-A37 are byte-identical to revision 2. The Revision 2 section below is kept as it was. I reproduced each failure on revision 2 in the scratchpad before changing anything: a 4301-digit integer next to a `.ssh` path exited 1; 12,000 distinct words after a 300-link symlink chain with the credential word last ran 13.4 s (the hook timeout is 10 s, and a timeout is fail-open); `docker run -v ~/.ssh:/root/.ssh:ro img` and `cat ${X:-~/.netrc}` exited 0; appending "Claude Code blocks any call whose PreToolUse hook exits 2, and Cowork ignores hooks." to hooks.md left the protocol test green.

| Fix | Answers | What changed |
|---|---|---|
| `json.loads(..., parse_int=str)`: integers stay text, so no digit count can make valid JSON "unreadable". Floats and exponents were checked in the same pass: `0.` plus 100,000 digits, `1e999999999`, `1E+400`, `-1e-999999` and a 5,000-digit integer part with a fraction all parse (no limit applies to them). Nested JSON still exits 2. | B1, A25, R22 | `main()`; `test_numbers_cannot_hide_a_sensitive_path` (6 numbers, deny and allow); hooks.md row "Nested JSON, or an integer of more than 4300 digits". |
| Two passes. Pass 1 runs the text check on every word and path, with no filesystem call, and denies on a hit. Pass 2 follows symlinks with `resolve()`, a bounded stand-in for `os.path.realpath`: a budget of 16,384 path components per call and 40 links per path (the runtime guard's own numbers, `sensitive_paths.py:56-57`). Exceeding either exits 2, rule `path-budget`. | B2, A24 | `check()`, `resolve()`, `BudgetError` in D1. Measured on the judge's scenario (300-link chain, credential word last): 12,000 words 13.4 s on r2 against 0.10 s on r3; 20,000 words (168,905 characters) 0.15 s; the same 20,000 words with no credential word 0.16 s and `path-budget`. 30,000 words exceed the 200,000-character command cap and are refused in 0.03 s. |
| Separator class gains `:` `,` `{` `}`, and `$VAR` and `${VAR}` are expanded over the whole command before the cut (so `${HOME}/lnk/x` keeps working now that braces split words). | B3, A27 | `WORD_SPLIT`, `candidates()`; eight new `BASH_DENY` commands plus `cat ~/{.netrc,.npmrc}`; `${HOME}` test; four more separators in the separator test. |
| Flat host claims moved into Unverified rows ("Non-string values", "Nested JSON, ..."). The protocol test now also fails on any new sentence in hooks.md that mentions Claude Code, Cowork, the host or chat unless it is on a reviewed list, and on any changed or added hook line in `SKILL.md` or `surfaces.md` (sha256 of each line). | B4, A31 | `test_no_new_flat_host_claim_in_hooks_md`, `test_hook_lines_in_skill_and_surfaces_are_the_reviewed_ones`. |
| False-positive list gains bare `.ssh`/`.aws`/`.azure`/`.gnupg` words, tool input nested over about 1,000 levels, a path through more than 40 links, a command naming more than about 3,000 distinct paths, and words that become a bare credential name after the new cuts. The two performance-only labels are withdrawn: with the budget in place both mutants are now killed (dedupe dropped spends the budget on repeats; a long word given the full walk exceeds it). The judge's `KEYS=/h/.ssh` then `cat $KEYS/<4100 a>` case is a path over `PATH_MAX`, which no kernel can open; it is stated in A33, not hidden behind an equivalence label. | B5, A33 | hooks.md "Does not cover"; Test plan; A33. |
| The judge's 12 test gaps (R05, R06, R08-R13, R15, R17, R20, R23) each have a test; the 25 R-series entries, the r1 J-series and the new mutants are all in the runner. | R-series | Test plan: counts below. |
| One-sentence doc follow-ups folded in: `cd` then a relative word, quote or backslash inside a name, invalid UTF-8 exits 1, and "or that `cwd` and `command` reach the hook" in Step 6.7 and Install step 4. | F1, F2, F4, F8 | hooks.md, E3. Everything else the judge listed is under Follow-ups (not built). |

Decisions Daniel should know about:
1. The script now carries its own bounded symlink resolver (about 35 lines) instead of `os.path.realpath`. It is tested against the same symlink, `..`, `.`, relative-target and absolute-target cases and pinned by 26 mutants, but it is code that must be kept in step with `sensitive_paths.py` if that guard's numbers change.
2. Budget exhaustion denies (exit 2). The false positives are a command naming more than about 3,000 distinct paths and a path through more than 40 links (the kernel refuses those too). I chose deny because a timeout is fail-open and the judge reproduced that attack.
3. The tests now freeze the reviewed wording of every hook line in `SKILL.md` and `surfaces.md` and every host-related sentence in hooks.md. A later legitimate edit to one of those lines has to update the test on purpose. What this cannot catch: a flat claim phrased without those five words, a flat body behind an "Unverified" prefix, another file, or a wrong claim that was reviewed.
4. `shlex` stays gone; `$VAR` expansion now covers the whole command, so an environment variable that holds spaces changes how words are cut. That affects only which words are checked, never which are skipped.
5. Because integers are now kept as text, a JSON integer given as a path value (`{"file_path": 5}`) is checked as the path `5`; the non-string tests use a float and a list instead. Behaviour on real tool input is unchanged, since the host sends paths as strings.
6. Python 3.14 is still untested (the judge ran 3.10 to 3.13 on r2); I ran 3.11.

## Revision 2 (judge round 1: UPHELD 28, REJECTED 3, blocking findings B1-B8)

Changed claims: A24, A25, A27, A31 (marked `CHANGED r2`). New NET-NEW rows A32-A37 are appended. Rows A1-A23, A26, A28-A30 are byte-identical to revision 1. I reproduced each rejection on revision 1 before changing anything: `cat ~/.netrc;ls`, `(cat ~/.kube/config)`, `cat C:\Users\u\.ssh\id_rsa` and the other punctuation cases exited 0; a command with a 4200-character commit message exited 2; a 1100-level nested payload and a non-ASCII payload under `PYTHONIOENCODING=ascii` exited 1; `join(X, cwd)` passed all 71 tests.

| Fix | Answers | What changed |
|---|---|---|
| Bash words are cut with one linear `re.split` at whitespace, `;` `&` `\|` `(` `)` `<` `>`, a backtick, both quotes and `=`; backslashes become `/` before the cut. `shlex` is gone. | A27, B1, B4, F4 | `candidates()` in D1; 11 separator cases and 22 deny commands in D2. The two hooks.md "passes" the judge found wrong (`<~/.ssh/id_rsa`, `$(echo ~)/.ssh/id_rsa`) are removed; the real passes are listed. |
| stdin is read as bytes; a nested-JSON `RecursionError` now exits 2; empty or non-JSON input still exits 1; the deny reason is written with `!a` so a non-ASCII path cannot break stderr. | A25, B2 | `main()` in D1; `test_unparseable_json_depth_fails_closed`, `test_non_ascii_survives_a_narrow_stdio_encoding`. |
| The 4096 cap applies to path-key values only. A Bash word over 4096 characters gets the text patterns only (no expansion, no filesystem); a command over 200,000 characters is refused. | A24, B3, F4 | `rule(..., is_path=)` and `MAX_COMMAND` in D1; `git commit -m "<4200 chars>"`, a 4100-character word and a 198,000-character word all pass. |
| Every test payload carries `cwd` (default `/w`); absolute-path-plus-cwd, credential-named-link cwd, `.SSH` real directory and 4000-character-path-with-long-cwd cases added. | B5, F3 | `call()` in D2; the join-argument-swap mutant now dies. |
| Every host-protocol sentence that rests only on the deepseek bridge or the plugin-dev text is a table row whose status starts "Unverified" (Input, Block, Other exit codes, Stdout, Matcher, Command variable, Timeout, Several hooks, Config reload, `settings.json` shape); "enforced by the host" is gone. A pytest pins the rows and bans the old flat sentences. | B6, F10, A31 | hooks.md D3; `test_host_protocol_rows_stay_marked_unverified`. |
| Chat is "reported no hooks (observed 2026-10-03, self-reported)", Cowork is "unknown", in hooks.md line 1, E1 and E4. | B7 | D3, edits.py. |
| Step 6.7 now closes with a live blocked call and says what it cannot prove. | B8 | E3 and E4 in edits.py; hooks.md Install step 4. |
| The judge's mutants and the new ones are in the runner; `108 tests`. | all 10 gaps | `_workspace/02_strategy-architect_C5_mutate.py`; counts in Test plan. |
| One-line prose follow-ups: parent-directory recursion, the false-positive list, `ok\ud800.txt` beside the NUL trigger, the input-size guard (fail direction: refuse). F7's wrong examples fixed. | F1, F2, F4, F5, F7 | hooks.md "Does not cover", `test_check_failure_after_parse_blocks`. |

Decisions Daniel should know about:
1. Nested JSON the parser cannot hold now **blocks** (exit 2), so even the string `[` repeated 200,000 times blocks. Reason: the host never sends such input, and the judge showed a sensitive path hidden behind deep nesting would otherwise fail open.
2. A Bash command over 200,000 characters is refused. A heredoc that writes a file of more than 200 KB through Bash is a false positive; use the Write tool. Fail direction is closed because the scan must stay far below the 10-second timeout, which hooks.md treats as fail-open.
3. `shlex` is dropped. Quote-aware splitting is lost, but a quoted path with spaces still matches because its last piece carries the credential suffix.
4. Two mutants (`EQUIV-PERF-*`) change only running time (0.05 s becomes 0.8 s and 1.6 s on a 200 KB command), so no test pins them. I classify them equivalent, not killed; a timing assertion tight enough to kill them would flake on a loaded CI machine.
5. Judge finding N10 (`except (OSError, ValueError)` instead of `except Exception`) is also equivalent on every input I can build: the only exceptions reachable in that block are `ValueError` (NUL byte, lone surrogate, over-long command) and `OSError`.

## Source

Backlog row C5 (`_workspace/01b_capability-scout_backlog.md:52`): "a generated harness ships an enforced guard, not just prose". Scope, surface rule and the fixed QA bar are in `_workspace/00_input/request.md`, "Pick 6". Port-map rows re-opened against the real files:

| Row | What I opened | Line | Used for |
|---|---|---|---|
| D42 | `references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts` | :11, :59, :66, :72 | exit 2 blocks and stderr is the reason; structured stdout read on exit 0 only |
| D43 | same file | :38, :107 | a top-level `deny` is not honoured, so exit 2 is the only deny path this kit uses |
| D45 | `.../hook-protocol/src/matcher.ts` | :14, :18, :58, :62 | `*` matches all; a words-and-pipe matcher is an exact-name list |
| D46 | `.../hook-protocol/src/runner.ts` | :20, :74, :89-91, :96-98 | per-hook timeout in seconds; signal death and a hook that cannot run are non-blocking |
| D48 | `.../hooks-claude-code/src/index.ts`, `config.ts` | index :104, :114, :145-147, :324-329, :340; config :52-60, :98-99 | stdin payload fields; load failure registers nothing; `${CLAUDE_PROJECT_DIR}` substitution; non-command types skipped |
| OH41 | `references/openharness/src/openharness/hooks/schemas.py` | :10-17, :61 (the port map says :60; the union opens at :61) | four hook kinds; this kit ships the command kind only (deterministic, no model call) |
| OH51 | `references/openharness/src/openharness/plugins/loader.py` | :649, :657, :670 | a hooks file is accepted both with and without a top-level `hooks` key |
| (patterns) | `references/openharness/src/openharness/permissions/checker.py` | :18-33, :91, :169 | credential patterns, fnmatch, directory-root form |
| (expand) | `references/openharness/src/openharness/engine/query.py` | :1029, :1032 | `~` expansion then resolve before matching |

Local denylist idea reused by pattern, not by import: `src/master_finhub/tools/sensitive_paths.py` (the plugin ships without the runtime). D44 (merge of many hook outputs) and D47 (audit events) are not used: one hook, no merge, no audit log (deferred, see Does not cover).

## Target

New files:
- `skills/finhub-harness/references/hooks.md` (full text in Design D3)
- `skills/finhub-harness/scripts/deny_sensitive.py` (D1). Flat in `scripts/` beside `lint_harness.py`; the backlog proof line said `scripts/hooks/deny_sensitive.py`, the flat path is the one `request.md` Pick 6 names.
- `tests/test_deny_sensitive.py` (D2)

Edited files (insertions only, except one existing table row in `surfaces.md` that gains words):
- `skills/finhub-harness/SKILL.md` (198 lines now, 203 after): Step 3 (+1 bullet), Step 5 (+1 bullet), Step 6 (+1 item, "7."), Deliverable checklist (+1), References (+1)
- `skills/finhub-harness/references/surfaces.md`: §3b (+1 row), §4 (existing `Hooks` row edited), §6 (+1 row, "8")

Not touched, with the reason: `lint_harness.py` and `tests/test_lint_harness.py` (see Design D5), `scripts/package-plugin.sh` (already zips all of `skills/`), `scripts/check-harness-refs.sh` (checks this repo's team prose), `orchestrator-template.md` (the one-line orchestrator note lives in Step 5, so the template stays generic), `finhub-harness-evolve`, everything under `src/`.

## Design

### D1. The hook script (`skills/finhub-harness/scripts/deny_sensitive.py`, 162 lines, simulated and run)

The builder may restyle, but must keep every pattern, rule, limit, exit code and call site; each is pinned by a mutant below.

```python
"""PreToolUse guard: exit 2 (reason on stderr) when a tool call names a credential path.

A tripwire, not a sandbox: it reads path-like arguments and the words of a Bash command, it
does not run a shell. Exit 0 allows. Empty or non-JSON stdin exits 1 (non-blocking); anything
that parsed, or that the parser could not hold, and then fails exits 2. The patterns and the
limits are constants; no input can extend or remove them.
Exit protocol adapted from references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:59 (MIT);
patterns adapted from references/openharness/src/openharness/permissions/checker.py:20 (MIT).
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import sys
from collections import deque

PATTERNS = (
    "*/.ssh/*", "*/.aws/*", "*/.config/gcloud/*", "*/.azure/*", "*/.gnupg/*",
    "*/.docker/config.json", "*/.kube/config", "*/.netrc", "*/_netrc", "*/.npmrc",
    "*/.pypirc", "*/.git-credentials", "*/id_rsa", "*/id_dsa", "*/id_ecdsa", "*/id_ed25519",
)  # fmt: skip
PATH_KEYS = ("file_path", "notebook_path", "path")
MAX_CHARS = 4096  # longest path value; longer Bash words get a text-only check
MAX_COMMAND = 200_000  # longest Bash command we will scan
MAX_COMPONENTS = 16_384  # path components resolved per call (the runtime guard's budget)
MAX_LINKS = 40  # symlinks followed per path (Linux MAXSYMLINKS: the kernel refuses more)
RE = re.compile("|".join(fnmatch.translate(p) for p in PATTERNS))
VAR = re.compile(r"\$(\w+|\{[^}]*\})", re.ASCII)  # the pattern os.path.expandvars uses
# whitespace, shell punctuation, quotes, and = : , { }
WORD_SPLIT = re.compile(r"[\s;&|()<>`\"'=:,{}]+")


class BudgetError(Exception):
    """Resolving symlinks needed more components or links than the limits allow."""


def text_hit(s: str) -> bool:
    f = s.casefold()
    return bool(RE.match(f) or RE.match(f + "/"))


def expand_vars(s: str, limit: int) -> str:
    """os.path.expandvars(s), but an expansion longer than `limit` raises before it is built."""
    size = len(s)

    def value(m: re.Match[str]) -> str:
        nonlocal size
        name = m.group(1)
        found = os.environ.get(name[1:-1] if name[0] == "{" else name)
        if found is None:
            return m.group(0)
        size += len(found) - len(m.group(0))
        if size > limit:
            raise ValueError("variable expansion too long")
        return found

    return VAR.sub(value, s)


def expand(raw: str, cwd: str) -> str:
    return posixpath.join(cwd, expand_vars(os.path.expanduser(raw), MAX_CHARS)).replace("\\", "/")


def resolve(path: str, budget: list[int]) -> str:
    """os.path.realpath(path), but every component and link is counted and the counts are capped."""
    if not path.startswith("/"):
        path = os.getcwd() + "/" + path
    pending = deque(path.split("/"))
    done: list[str] = []
    links = 0
    while pending:
        budget[0] -= 1
        if budget[0] < 0:
            raise BudgetError
        name = pending.popleft()
        if name in ("", "."):
            continue
        if name == "..":
            if done:
                done.pop()
            continue
        try:
            target = os.readlink("/" + "/".join([*done, name]))
        except OSError:  # not a link, or missing: a plain component
            done.append(name)
            continue
        links += 1
        if links > MAX_LINKS:
            raise BudgetError
        if target.startswith("/"):
            done.clear()
        pending.extendleft(reversed(target.split("/")))
    return "/" + "/".join(done)


def candidates(tool_input: dict[str, object]) -> list[tuple[str, bool]]:
    """(value, is_path) pairs: the path arguments, then the distinct words of a command."""
    out = [(v, True) for k in PATH_KEYS if isinstance(v := tool_input.get(k), str) and v]
    cmd = tool_input.get("command")
    if isinstance(cmd, str):
        if len(cmd) > MAX_COMMAND:
            raise ValueError("command too long")
        words = WORD_SPLIT.split(expand_vars(cmd.replace("\\", "/"), MAX_COMMAND))
        out += [(w, False) for w in dict.fromkeys(words) if w]
    return out


def check(tool_input: dict[str, object], cwd: str) -> tuple[str, str] | None:
    """(rule, value) for the first denied value, else None. Text first, then symlinks."""
    todo = []
    for raw, is_path in candidates(tool_input):  # pass 1: text only, no filesystem
        if len(raw) > MAX_CHARS:
            if is_path:
                return "too-long", raw
            if text_hit(raw):
                return "sensitive-path", raw
            continue
        s = expand(raw, cwd)
        if text_hit(posixpath.normpath(s)):
            return "sensitive-path", raw
        todo.append((raw, s))
    budget = [MAX_COMPONENTS]
    for raw, s in todo:  # pass 2: follow symlinks within the budget
        try:
            real = resolve(s, budget)
        except BudgetError:
            return "path-budget", raw
        if text_hit(real):
            return "sensitive-path", raw
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read(), parse_int=str)  # str: no digit limit
        tool_input = payload["tool_input"]
        if not isinstance(tool_input, dict):
            raise TypeError
    except RecursionError:  # JSON the parser cannot hold is not "unreadable": fail closed
        print("deny_sensitive: input nested too deeply; blocking", file=sys.stderr)
        return 2
    except (ValueError, KeyError, TypeError):  # ValueError covers empty and non-JSON input
        print("deny_sensitive: unreadable hook input; not blocking", file=sys.stderr)
        return 1
    try:
        cwd = payload.get("cwd")
        base = cwd if isinstance(cwd, str) else ""  # "" resolves against the process cwd
        if hit := check(tool_input, base):
            print(f"deny_sensitive: {hit[0]}: {hit[1][:200]!a}", file=sys.stderr)
            return 2
    except Exception as exc:  # noqa: BLE001 - fail closed once the call is parsed
        print(f"deny_sensitive: check failed ({type(exc).__name__}); blocking", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### D2. Tests (`tests/test_deny_sensitive.py`, 591 lines, 168 cases; stdlib plus pytest, every case runs the script in a fresh subprocess)

```python
"""Proof for skills/finhub-harness/scripts/deny_sensitive.py (C5)."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/deny_sensitive.py"
HOOKS_MD = REPO / "skills/finhub-harness/references/hooks.md"
HOME = "/h"


def run(
    stdin: str | bytes,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    data = stdin.encode() if isinstance(stdin, str) else stdin
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=data,
        capture_output=True,
        timeout=30,
        check=False,
        cwd=cwd,
        env={"PATH": os.environ["PATH"], "HOME": HOME, **(env or {})},
    )
    assert proc.stdout == b""  # JSON on stdout is never used (A5)
    return proc.returncode, proc.stderr.decode()


def call(tool_input: dict[str, object], cwd: object = "/w") -> str:
    """A payload as the host sends it, with a cwd; cwd=None leaves the field out."""
    payload: dict[str, object] = {"tool_name": "T", "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = cwd
    return json.dumps(payload)


def bash(
    cmd: str, *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> tuple[int, str]:
    return run(call({"command": cmd}), cwd=cwd, env=env)


def read(path: str, *, cwd: Path | None = None) -> tuple[int, str]:
    return run(call({"file_path": path}), cwd=cwd)


DENY = [
    "/h/.ssh/config",
    "/h/.aws/credentials",
    "/h/.aws/config",
    "/h/.aws/sso/cache/t.json",  # wider than the two files the reference lists
    "/h/.config/gcloud/creds.db",
    "/h/.azure/token",
    "/h/.gnupg/secring",
    "/h/.docker/config.json",
    "/h/.kube/config",
    "/h/.netrc",
    "/h/_netrc",
    "/h/.npmrc",
    "/h/.pypirc",
    "/h/.git-credentials",
    "/h/id_rsa",
    "/h/id_dsa",
    "/h/id_ecdsa",
    "/h/id_ed25519",
    "/h/.ssh",  # directory root (trailing-slash form)
    "/h/.ssh/",
    "/w/x/../../h/.aws/config",  # traversal
    "/h/.SSH/ID_RSA",  # case
    "/h/.AZURE/t",
    "/h/.SSH",  # directory root, upper case
    "/h/.GNUPG/x",
    "/H/.NETRC",
    "/h/.KUBE/CONFIG",
    "C:\\Users\\u\\.ssh\\id_rsa",  # Windows separators and drive
    "C:/Users/u/.gnupg/pubring.kbx",
    "..\\..\\.ssh\\k",
]
ALLOW = [
    "/w/a.txt",
    "/h/id_rsa.pub",
    "/h/id_ed25519.pub",
    "/h/.pypirc.bak",
    "/h/.git-credentials.bak",
    "/w/my.netrc",
    "/w/my_netrc",
    "/w/not_id_rsa",
    "/w/" + "\u00e9" * 3000,  # long in bytes, short in characters
    "/h/.sshx/k",
    "/h/.ssh_notes/k",
    "/h/.docker/daemon.json",
    "/h/.kube/cache/x",
    "/h/.config/other/x",
    "/h/.npmrc.bak",
    "/h/.aws-sam/x",
    "/w/.ssh/../a.txt",  # traversal out of a credential-named dir
    "/w/.ssh//../a.txt",  # empty component before ..
    "/w/.ssh/./../a.txt",  # . before ..
    "relative/a.txt",
]


@pytest.mark.parametrize("path", DENY)
def test_denies(path: str) -> None:
    code, err = read(path)
    assert code == 2 and err.startswith("deny_sensitive: sensitive-path: "), (code, err)


@pytest.mark.parametrize("path", ALLOW)
def test_allows(path: str) -> None:
    assert read(path) == (0, "")


@pytest.mark.parametrize("key", ["file_path", "notebook_path", "path"])
def test_each_path_key(key: str) -> None:
    assert run(call({key: "/h/.ssh/k"}))[0] == 2


def test_only_path_keys_and_command_are_read() -> None:
    assert run(call({"content": "see /h/.ssh/id_rsa", "pattern": "/h/.ssh/*"}))[0] == 0


def test_symlinks_tilde_and_cwd(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    (home / "dotfiles/ssh").mkdir(parents=True)
    (home / "lnk").symlink_to(home / ".ssh")  # innocent name, credential target
    work = tmp_path / "work"
    work.mkdir()
    (work / "key").symlink_to(home / ".ssh/id_rsa")
    env = {"HOME": str(home)}
    # realpath form: the link target is a credential dir or file
    assert run(call({"file_path": str(work / "key")}), env=env)[0] == 2
    assert run(call({"file_path": str(home / "lnk/x")}), env=env)[0] == 2
    # ~ and $HOME are expanded before the walk
    assert run(call({"file_path": "~/lnk/x"}), env=env)[0] == 2
    assert run(call({"file_path": "$HOME/lnk/x"}), env=env)[0] == 2
    # lexical form: a credential-named link to a harmless-named target still matches
    (home / ".kube").symlink_to(home / "dotfiles/ssh")
    assert run(call({"file_path": str(home / ".kube/config")}), env=env)[0] == 2
    # relative path resolves against payload cwd, not the process cwd
    cred = home / ".ssh"
    assert run(call({"file_path": "k"}, cwd=str(cred)), cwd=work)[0] == 2
    assert run(call({"file_path": "k"}, cwd=str(work)), cwd=cred)[0] == 0
    # no payload cwd: the process cwd is used
    assert run(call({"file_path": "k"}, cwd=None), cwd=cred)[0] == 2
    assert run(call({"file_path": "k"}, cwd=""), cwd=cred)[0] == 2
    assert run(call({"file_path": "k"}, cwd=5), cwd=cred)[0] == 2  # not a string: ignored
    assert run(call({"file_path": "k"}, cwd=5), cwd=work) == (0, "")
    # a Windows-style cwd is normalised
    assert run(call({"file_path": "k"}, cwd="C:\\Users\\u\\.ssh"), cwd=work)[0] == 2
    # an empty path value is ignored even when cwd is a credential dir
    assert run(call({"file_path": ""}, cwd=str(cred)), cwd=work) == (0, "")
    assert run(call({"command": ";"}, cwd=str(cred)), cwd=work) == (0, "")  # empty words
    # lexical form keeps cwd: a cwd that is a credential-named link to an innocent directory
    (work / "innocent").mkdir()
    (work / ".ssh").symlink_to(work / "innocent")
    assert run(call({"file_path": "k"}, cwd=str(work / ".ssh")), cwd=work)[0] == 2
    # real form is case-folded: a link to a real directory named .SSH
    (home / ".SSH").mkdir()
    (home / "plain").symlink_to(home / ".SSH")
    assert run(call({"file_path": str(home / "plain/k")}), env=env)[0] == 2
    # `..` after a link follows the link target, not the link's own directory
    (home / ".ssh/sub").mkdir()
    (work / "jump").symlink_to(home / ".ssh/sub")
    assert run(call({"file_path": str(work / "jump/../k")}), env=env)[0] == 2
    assert run(call({"file_path": str(work / "innocent/../k")}), env=env) == (0, "")
    # `.` before `..` does not change which directory `..` leaves
    (home / "x/.ssh").mkdir(parents=True)
    (work / "jump2").symlink_to(home / "x/.ssh")
    assert run(call({"file_path": str(work / "jump2/./../k")}), env=env) == (0, "")
    # an absolute link target replaces the path walked so far
    (tmp_path / "plain2").mkdir()
    (home / ".ssh/outlink").symlink_to(tmp_path / "plain2")
    (work / "jumpssh").symlink_to(home / ".ssh")
    assert run(call({"file_path": str(work / "jumpssh/outlink/k")}), env=env) == (0, "")
    # a relative link target is resolved from the directory that holds the link
    (work / "rel").symlink_to("../home/.ssh")
    assert run(call({"file_path": str(work / "rel/x")}), env=env)[0] == 2
    # dedupe is by exact word: on a case-sensitive filesystem Zk and zk differ
    (home / "Zk").symlink_to(home / ".ssh")
    assert bash(f"cat {home}/zk/x {home}/Zk/x", env=env)[0] == 2
    # ${HOME} is expanded before the command is cut at braces
    assert bash("cat ${HOME}/lnk/x", env=env)[0] == 2
    # a blank value is a path under cwd; an integer value is the path of that text
    assert run(call({"file_path": " "}, cwd=str(cred)), cwd=work)[0] == 2
    assert run(call({"file_path": 5}, cwd=str(cred)), cwd=work)[0] == 2
    # the resolved path is compared case-folded too: the lexical form (.SSH link) gives it away
    (work / ".SSH").symlink_to(work / "innocent")
    assert run(call({"file_path": str(work / ".SSH/k")}), env=env)[0] == 2
    # the length cap counts the value, not the value joined to cwd
    long_cwd = str(work / ("b" * 200))
    assert run(call({"file_path": "a" * 4000}, cwd=long_cwd)) == (0, "")


BASH_DENY = [
    "cat ~/.ssh/id_rsa",
    "cat /h/.aws/credentials | head",
    "scp --identity=/h/.ssh/k host:",
    "cp /w/a /h/.npmrc",
    'cat "/h/.ssh/id_rsa',  # unbalanced quote
    'cat "/h/.npmrc"',
    "cat C:\\Users\\u\\.ssh\\id_rsa",  # unquoted Windows path
    "ssh -i/h/.ssh/id_rsa host",  # attached short option
    "curl file:///h/.ssh/id_rsa",
    "cat ~/.netrc;ls",
    "echo $(cat /h/.npmrc)",
    "cat /h/.git-credentials>/w/x",
    "cat /h/.netrc|base64",
    "cat /h/.netrc&&echo",
    "(cat /h/.kube/config)",
    "cat `echo /h/.pypirc`",
    "cat keys/id_rsa;",
    "cat /h/.docker/config.json)",
    "cat <" + "/h/.ssh/id_rsa",
    "x=/h/.npmrc cat $x",
    "docker run -v ~/.ssh:/root/.ssh:ro img",  # glued ':' ',' '{' '}'
    "docker run -v ~/.ssh:/k img",
    "docker run -v $HOME/.aws:/root/.aws:ro img",
    "docker run -v /h/.netrc:/k img",
    "docker run --mount source=/h/.kube/config,target=/k img",
    "export KUBECONFIG=/h/.kube/config:/h/.kube/other",
    "cat /h/.netrc:x",
    "cat ${X:-~/.netrc}",
    "cat ~\\.kube\\config",  # Windows separators on the other end-anchored names
    "cat C:\\Users\\u\\.docker\\config.json",
    "cat ~/{.netrc,.npmrc}",
    "a" * 5000 + "/.ssh/k",  # long word: text-only check
    "a" * 5000 + "\\.ssh\\k",  # long word with Windows separators
]


@pytest.mark.parametrize("cmd", BASH_DENY)
def test_bash_denies(cmd: str) -> None:
    code, err = bash(cmd)
    assert code == 2 and err.startswith("deny_sensitive: sensitive-path: "), (code, err)


BASH_ALLOW = [
    "ls src/",
    "git status",
    "echo \"it's",
    "pytest -q tests/",
    'git commit -m "' + "word " * 840 + '"',  # long message, short words
    "echo " + "a" * 4100,  # one long word with no path in it
    "echo " + "a" * 4097,
    "a " * 100_000,  # 200000 characters, at the command cap
    "a/" * 99_000,  # one 198000-character word: no filesystem walk
    "cat /w/gcloud/x.py /w/.git/config /w/config",
    "curl https://example.com:8080/a,b",
    "git log --format=%h:%s",
    "ls /w/a:b",
    'curl -d \'{"a":"b"}\' https://h/x',
    "echo a:b c,d {e}",
    "\u00e9 " * 99_999,  # 199,998 characters, twice that in bytes
]


@pytest.mark.parametrize("cmd", BASH_ALLOW)
def test_bash_allows(cmd: str) -> None:
    start = time.monotonic()
    assert bash(cmd) == (0, "")
    assert time.monotonic() - start < 5  # repeated words are checked once


@pytest.mark.parametrize(
    "sep", [";", "&", "|", "(", ")", "<", ">", "`", '"', "'", " ", "=", ":", ",", "{", "}"]
)
def test_each_separator_splits_a_word(sep: str, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    (home / "lnk").symlink_to(home / ".ssh")
    env = {"HOME": str(home)}
    assert bash(f"cat /h/.npmrc{sep}", env=env)[0] == 2  # end-anchored name, glued after
    assert bash(f"cat x{sep}~/lnk/k", env=env)[0] == 2  # `~` glued after a separator


def test_command_over_the_cap_is_refused() -> None:
    code, err = bash("a " * 100_000 + "b")
    assert code == 2 and "check failed" in err


MALFORMED = [
    "",
    "garbage",
    "[]",
    '"tool_input"',
    "42",
    "{}",
    '{"tool_name": "T"}',
    '{"tool_input": "/h/.ssh/k"}',
    '{"tool_input": null}',
    b"\xff\xfe{",
]


@pytest.mark.parametrize("stdin", MALFORMED)
def test_malformed_input_is_non_blocking(stdin: str | bytes) -> None:
    code, err = run(stdin)
    assert code == 1 and "Traceback" not in err and err.startswith("deny_sensitive: unreadable")


def test_unparseable_json_depth_fails_closed() -> None:
    nested = "[" * 1100 + "]" * 1100
    deep = '{"tool_input":{"path":"/h/.ssh/id_rsa","x":' + nested + "}}"
    assert run(deep)[0] == 2
    assert run("[" * 200_000)[0] == 2


def raw_utf8(cmd: str) -> str:
    """Payload with the command as raw UTF-8 text, not \\u escapes."""
    return json.dumps({"tool_input": {"command": cmd}, "cwd": "/w"}, ensure_ascii=False)


def test_non_ascii_survives_a_narrow_stdio_encoding() -> None:
    for enc in ("ascii", "cp1252"):
        env = {"PYTHONIOENCODING": enc}
        for cmd in ("# \u00c1\u00e9 cat /h/.ssh/id_rsa", "cat /h/.ssh/\u00c1k"):
            code, err = run(raw_utf8(cmd), env=env)
            assert code == 2 and err.startswith("deny_sensitive: sensitive-path: "), (enc, err)
        assert run(raw_utf8("# \u00c1 ls"), env=env) == (0, "")


def test_non_string_values_are_ignored() -> None:
    assert run(
        call({"file_path": 5.5, "path": ["/h/.ssh/k"], "command": ["cat", "/h/.ssh/k"]})
    ) == (0, "")


def test_check_failure_after_parse_blocks() -> None:
    for bad in (
        "ok\x00.txt",
        "ok\ud800.txt",
    ):  # NUL: realpath raises; lone surrogate: encode raises
        code, err = read(bad)
        assert code == 2 and "check failed" in err


def test_length_cap_boundary() -> None:
    assert read("/" + "a" * 4095) == (0, "")
    code, err = read("/" + "a" * 4096)
    assert code == 2 and "too-long" in err


def test_deny_reason_is_truncated() -> None:
    assert len(read("/h/.ssh/" + "a" * 300)[1]) < 260


@pytest.mark.parametrize("path", ["/" * 4096, "/a" * 2048, "/.ssh" * 800, "a/" * 2000 + "x"])
def test_matching_is_fast_on_hostile_paths(path: str) -> None:
    start = time.monotonic()
    assert read(path)[0] in (0, 2)
    assert time.monotonic() - start < 2


def test_wiring_block_in_hooks_md() -> None:
    block = re.search(r"```json\n(.*?)\n```", HOOKS_MD.read_text(encoding="utf-8"), re.S)
    assert block
    group = json.loads(block.group(1))["hooks"]["PreToolUse"]
    assert len(group) == 1 and group[0]["matcher"] == "*"
    (hook,) = group[0]["hooks"]
    assert hook["type"] == "command" and hook["timeout"] == 10
    assert hook["command"].startswith('python3 "')
    assert hook["command"].endswith('.claude/hooks/deny_sensitive.py"')
    assert "${CLAUDE_PROJECT_DIR}" in hook["command"]


def make_chain(base: Path, links: int) -> None:
    """c0 -> c1 -> ... -> c<links-1> -> end, `links` symlinks in all."""
    (base / "end").mkdir()
    for i in range(links):
        (base / f"c{i}").symlink_to(f"c{i + 1}" if i < links - 1 else "end")


def test_symlink_chain_cannot_delay_a_deny(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    make_chain(base, 300)
    cmd = " ".join(f"c0/{i}" for i in range(12_000)) + " ; cat /h/.netrc"
    start = time.monotonic()
    code, err = run(call({"command": cmd}, cwd=str(base)))
    assert code == 2 and err.startswith("deny_sensitive: sensitive-path: ")  # text pass, first
    assert time.monotonic() - start < 5  # the hook's own timeout is 10 s, and fail-open


def test_link_limit_is_40(tmp_path: Path) -> None:
    for links, expected in ((40, (0, "")), (41, None)):
        base = (tmp_path / f"n{links}").resolve()
        base.mkdir()
        make_chain(base, links)
        got = run(call({"command": "ls c0/x"}, cwd=str(base)))
        if expected is None:
            assert got[0] == 2 and got[1].startswith("deny_sensitive: path-budget: "), got
        else:
            assert got == expected, got


def slash_words(n: int, prefix: str) -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_component_budget() -> None:
    assert bash(slash_words(1_000, "/w/p/q/r")) == (0, "")
    code, err = bash(slash_words(5_000, "/w/p/q/r"))
    assert code == 2 and err.startswith("deny_sensitive: path-budget: ")
    # `/pN` costs two components: 8,192 words spend the 16,384 budget exactly
    assert bash(slash_words(8_192, "/p")) == (0, "")
    assert bash(slash_words(8_193, "/p"))[0] == 2
    # one more word spends 16,384 exactly (`/a`: two) or 16,385 (`/a/b`: three)
    assert bash(slash_words(8_191, "/p") + " /a") == (0, "")
    assert bash(slash_words(8_191, "/p") + " /a/b")[0] == 2


def test_every_word_is_checked_not_just_the_first_ones() -> None:
    cmd = " ".join(f"w{i}" for i in range(1_500)) + " /h/.netrc"
    assert bash(cmd)[0] == 2


def test_a_big_payload_is_read_in_full() -> None:
    big = json.dumps({"tool_input": {"path": "/h/.ssh/k", "content": "x" * 2_000_000}})
    assert run(big)[0] == 2


def test_stray_invalid_utf8_inside_valid_json_is_unreadable() -> None:
    assert run(b'{"tool_input":{"path":"/h/.ssh/k","x":"\xff"}}')[0] == 1


@pytest.mark.parametrize(
    "number",
    ["1" * 4301, "-" + "1" * 4301, "1" * 100_000, "0." + "1" * 100_000, "1e999999999", "1E+400"],
)
def test_numbers_cannot_hide_a_sensitive_path(number: str) -> None:
    payload = '{"tool_input":{"path":"/h/.ssh/id_rsa","x":' + number + '},"cwd":"/w"}'
    code, err = run(payload)
    assert code == 2 and err.startswith("deny_sensitive: sensitive-path: "), (code, err)
    assert run('{"tool_input":{"path":"/w/a","x":' + number + "}}") == (0, "")


BRACE_PASSES = ["cat ~/.kube/{config,x}", "cat ~/.{net,npm}rc", "cat ~/.n{e,}trc"]


@pytest.mark.parametrize("cmd", BRACE_PASSES)
def test_name_splitting_brace_expansion_is_a_documented_pass(cmd: str) -> None:
    # a known limit (hooks.md "Does not cover"); if this starts failing, update the doc on purpose
    assert bash(cmd) == (0, "")


def test_the_brace_limit_stays_documented() -> None:
    text = HOOKS_MD.read_text(encoding="utf-8")
    assert "brace expansion that splits a name" in text
    assert all(cmd.removeprefix("cat ") in text for cmd in BRACE_PASSES)


@pytest.mark.parametrize(("depth", "words"), [(1, 5_461), (8, 1_638), (15, 963)])
def test_budget_is_16384_over_depth_plus_two_distinct_words(depth: int, words: int) -> None:
    cwd = "/" + "/".join(f"d{i}" for i in range(depth))

    def words_cmd(n: int) -> str:
        return " ".join(f"w{i}" for i in range(n))

    assert run(call({"command": words_cmd(words)}, cwd=cwd)) == (0, "")
    code, err = run(call({"command": words_cmd(words + 1)}, cwd=cwd))
    assert code == 2 and err.startswith("deny_sensitive: path-budget: "), (code, err)


def test_variable_expansion_cannot_outlast_the_hook() -> None:
    for size in (5_883, 94_000):
        env = {"BIG": "x" * size}
        start = time.monotonic()
        code, err = bash("cat /h/.netrc " + "$BIG " * 33_313, env=env)
        assert code == 2 and "check failed" in err, (size, code, err)
        assert time.monotonic() - start < 5
    assert bash("echo $BIG $BIG", env={"BIG": "x" * 94_000}) == (0, "")
    assert bash("echo $BIG $BIG $BIG", env={"BIG": "x" * 94_000})[0] == 2


def test_command_expansion_bound_is_200000() -> None:
    a = "x" * 100_000
    assert bash("$A$B", env={"A": a, "B": "y" * 100_000}) == (0, "")
    assert bash("$A$B", env={"A": a, "B": "y" * 100_001})[0] == 2


def test_path_value_expansion_bound_is_4096() -> None:
    def path(b: str) -> tuple[int, str]:
        return run(call({"path": "$A$B"}), env={"A": "a" * 2_048, "B": b})

    assert path("b" * 2_048) == (0, "")
    assert path("b" * 2_049)[0] == 2
    assert run(call({"path": "$BIG" * 800}), env={"BIG": "x" * 94_000})[0] == 2


def test_variable_names_follow_the_stdlib_pattern() -> None:
    assert bash("cat $CAF\u00c9", env={"CAF\u00c9": "/h/.netrc"}) == (0, "")  # ASCII names only
    assert bash("cat ${CAFE}", env={"CAFE": "/h/.netrc"})[0] == 2
    assert bash("cat $CAFE", env={"CAFE": "/h/.netrc"})[0] == 2
    assert bash("cat ${NOPE:-~/.netrc}")[0] == 2  # an unset variable stays as written
    assert bash("cat $nope", env={"NOPE": "/h/.netrc"}) == (0, "")  # names are case-sensitive


UNVERIFIED_ROWS = {
    "Input",
    "Block",
    "Other exit codes",
    "Stdout",
    "Matcher",
    "Command variable",
    "Timeout",
    "Several hooks on one event",
    "Config reload",
    "`settings.json` shape",
    "Nested JSON, or an integer of more than 4300 digits",
    "Non-string values",
}
# Every sentence outside the table that mentions the host, Claude Code, Cowork or chat. A new
# one fails the test until a person reads it and adds it here: flat claims cannot slip in.
HOST_WORDS = re.compile(r"\b(claude code|cowork|hosts?|chat)\b", re.I)
ALLOWED_SENTENCES = {
    "A `PreToolUse` command hook is meant to run before the tool does and refuse the call; whether and how Claude Code honours that is stated in the table below, with its status.",
    "It targets Claude Code only.",
    "On chat, hooks were reported as not exposed (observed 2026-10-03, self-reported); on Cowork they are unknown.",
    'Every row whose status starts with "Unverified" rests on the deepseek bridge or the plugin-dev skill text, not on Claude Code\'s official hooks page, which was not opened.',
    "Its last probe is a live blocked call in a Claude Code session: ask the agent to read the non-existent file `~/.ssh/c5-probe`; the guard's stderr line, `deny_sensitive: sensitive-path: ...`, must come back as the refusal.",
    "A returned refusal shows this host ran the hook and honoured exit 2 for a read.",
    "It does not show that Bash words, MCP tools or subagents are covered, that `cwd` and `command` reach the hook, what a timeout does, or that the hook runs on chat or Cowork; none of that is checked.",
    "- A Windows host, and any claim about hooks on chat or Cowork: unverified.",
}
# sha256 prefixes of every line of SKILL.md and surfaces.md that mentions a hook. A reworded or
# added line fails the test until a person reads it and updates the set.
HOOK_LINES = {
    "aa7a11619263",
    "be16f7223b92",
    "599b882d7455",
    "5309b6e7a7bd",
    "f24da61ff8dd",
    "4639c097e714",
    "655fef7ba544",
    "31418ad84e77",
    "65c3bb0254c5",
    "cf2de34a33be",
}


def host_sentences(text: str) -> list[str]:
    found, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.strip() and not line.startswith(("|", "#")):
            sentences = re.split(r"(?<=[.!?])\s+", line.strip())
            found += [t for t in sentences if HOST_WORDS.search(t)]
    return found


def test_host_protocol_rows_stay_marked_unverified() -> None:
    text = HOOKS_MD.read_text(encoding="utf-8")
    table = text.split("## What the host and the script agree on")[1].split("## Deny rules")[0]
    rows = {}
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 3:
            rows[cells[0]] = cells[2]
    assert UNVERIFIED_ROWS <= rows.keys()
    for name in UNVERIFIED_ROWS:
        assert rows[name].startswith("Unverified"), name
    assert "enforced by the host" not in text
    assert "no hook runs" not in text and "run no hook" not in text  # Cowork is unknown


def test_no_new_flat_host_claim_in_hooks_md() -> None:
    text = HOOKS_MD.read_text(encoding="utf-8")
    table = text.split("## What the host and the script agree on")[1].split("## Deny rules")[0]
    unknown = [t for t in host_sentences(text.replace(table, "")) if t not in ALLOWED_SENTENCES]
    assert not unknown, unknown


def test_hook_lines_in_skill_and_surfaces_are_the_reviewed_ones() -> None:
    lines = []
    for rel in ("skills/finhub-harness/SKILL.md", "skills/finhub-harness/references/surfaces.md"):
        text = (REPO / rel).read_text(encoding="utf-8")
        lines += [ln for ln in text.splitlines() if "hook" in ln.lower()]
    assert {hashlib.sha256(ln.encode()).hexdigest()[:12] for ln in lines} == HOOK_LINES
```

How the tests live: they sit in `tests/` beside `test_lint_harness.py`, import only the standard library and pytest, locate the script and the docs by `Path(__file__).resolve().parents[1]`, and write only under pytest's `tmp_path`. They need ruff, black (line length 100) and `mypy --strict` clean, which I ran on both files with the repo's `.venv` mypy. Five cases assert elapsed time under 5 seconds as a hang guard (all measured under 0.5 s); no mutant relies on timing.

### D3. `skills/finhub-harness/references/hooks.md` (95 lines, new text, no source prose pasted)

`````markdown
# Guard hook kit for Claude Code harnesses

A prose rule such as "never read credential files" is advice the model can talk itself out of. A `PreToolUse` command hook is meant to run before the tool does and refuse the call; whether and how Claude Code honours that is stated in the table below, with its status. This kit gives a generated harness one small, stdlib-only hook that refuses tool calls naming a credential path. It targets Claude Code only. On chat, hooks were reported as not exposed (observed 2026-10-03, self-reported); on Cowork they are unknown. Treat both as having no guard: the harness's prose rules are the only guard there, and the build report says so.

Read this file at Step 3 when an agent can write files or run shell commands and the harness handles client or credential data. Skip it otherwise: a hook that blocks a legitimate call costs more than it saves in a harness that never touches such data.

## Files the harness ships

| File | Source |
|------|--------|
| `project/.claude/hooks/deny_sensitive.py` | copy of this skill's `scripts/deny_sensitive.py`, unchanged |
| `hooks` entry in `project/.claude/settings.json` | the block below |

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/deny_sensitive.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

When `settings.json` already exists, merge the `PreToolUse` entry; never overwrite the user's own hooks.

## What the host and the script agree on

Every row whose status starts with "Unverified" rests on the deepseek bridge or the plugin-dev skill text, not on Claude Code's official hooks page, which was not opened. Do not turn such a row into a flat statement elsewhere.

| Point | Behaviour | Status |
|-------|-----------|--------|
| Input | One JSON object on stdin. The script reads `tool_input` (an object, required) and `cwd` (a string, optional) and ignores every other field. | Unverified: the deepseek bridge builds `tool_name`, `tool_input`, `cwd`, `session_id` and `hook_event_name` for `PreToolUse`, and the plugin-dev text lists the same fields. |
| Block | Exit 2; stderr is the reason handed back to the model. | Unverified: same two sources. |
| Other exit codes | Non-blocking. A hook that cannot run, or dies by signal, never stops the call. | Unverified: same two sources. |
| Stdout | Never written. Structured JSON is read only on exit 0, so this script has nothing to get wrong there. | Unverified: the deepseek decoder only; what Claude Code does with stdout on exit 2 was not checked. |
| Matcher | `*` selects every tool, MCP tools included. A matcher made only of words and pipes is an exact-name list, so a narrower matcher would leave MCP tools unchecked. | Unverified: seen only in the deepseek bridge; Claude Code's own matcher rules were not checked. |
| Command variable | `${CLAUDE_PROJECT_DIR}` in the command is replaced by the project root. | Unverified: the deepseek bridge and the plugin-dev text only. |
| Timeout | The wiring sets 10 seconds. The default differs between sources (60 s in the plugin-dev text, 600 s in the deepseek bridge) and what a timeout does is not stated. Treat a timeout as fail-open. | Unverified. |
| Several hooks on one event | The plugin-dev text says they run in parallel and cannot see each other. Whether a sibling "allow" can override this deny is not known. | Unverified. |
| Config reload | The plugin-dev text says hooks load at session start, so a new entry needs a restart. | Unverified. |
| `settings.json` shape | The block above uses a top-level `hooks` key. The plugin-dev text shows that shape for a plugin's `hooks.json` and events at the top level for settings. | Unverified until a live check passes (Install step 4); if the entry is not listed, try the other shape. |
| Empty or non-JSON stdin, or invalid UTF-8 | Exit 1 with one stderr line: not blocking. | Net-new choice: a hook bug must not brick every tool call. |
| Nested JSON, or an integer of more than 4300 digits | Exit 2: blocking. Integers are kept as text, so no digit count makes valid JSON unreadable; nesting beyond about 1000 levels cannot be parsed and is refused. | Unverified: assumed, not checked, that the host never sends input this deep; refusing is safe either way. A net-new choice. |
| Non-string values | A tool value that is not a string is ignored. | Unverified: assumed, not checked, that the host's own schema rejects non-strings, so ignoring them is safe. |
| Failure while checking a parsed call | Exit 2: blocking. | Net-new choice: once the call is understood, an error is not a licence to allow it. |

## Deny rules

The patterns are constants in the script. No tool input, setting or environment variable can add or remove one. They are the credential locations the runtime's own guard uses (ssh, aws, gcloud, azure, gnupg, docker config, kube config, netrc, npmrc, pypirc, git credentials, private-key file names). This list is the minimum, not a complete inventory of secrets: `.env` files, `.pgpass`, `*.pem` and cloud-CLI token caches outside it are not covered.

A call is checked when any of these values matches: `file_path`, `notebook_path`, `path`, or a word of a Bash `command`. A command has `$VAR` and `${VAR}` expanded (an expansion that would pass 200,000 characters is refused), then is cut into words at whitespace, at `;` `&` `|` `(` `)` `<` `>`, at a backtick, at either quote and at `=` `:` `,` `{` `}`, so `cat ~/.netrc;ls`, `tool --out=~/.npmrc`, `docker run -v ~/.ssh:/k img` and `cat ${X:-~/.netrc}` are checked on the credential path itself. Text in other fields, such as the `content` of a write, is never read, so a document may mention `~/.ssh` freely.

| Question | Decision | Why |
|----------|----------|-----|
| Traversal | The path is joined to `cwd`, then checked in normalised form (`..` and `.` resolved). | `/w/../h/.aws/config` must match; `/w/.ssh/../a.txt` must not. |
| Symlinks | Checked twice: the normalised path and its fully resolved real path. The text check of every word runs first, so a deny never waits on the filesystem; the symlink walk then has a budget of 16,384 path components per call and 40 links per path, and exceeding either exits 2 with rule `path-budget`. Every distinct word of any kind costs the depth of the working directory plus 2 components, so the budget runs out after about 16,384 divided by (depth + 2) distinct words: 5,461 at depth 1, 3,276 at depth 3, 2,048 at depth 6, 963 at depth 15. | The real path catches a harmless-looking link to a credential directory. The normalised path catches a credential-named link that points somewhere harmless, such as `~/.ssh` kept in a dotfiles repo. The limits are the runtime guard's; the kernel refuses more than 40 links anyway. Without a bound, a chain of links and thousands of words kept the hook running past its 10-second timeout, which is fail-open. |
| `~` and `$VAR` | Expanded before either check. | Without it, `~/link/x` would not follow a link in the home directory. |
| Case | Compared case-insensitively. | macOS and Windows filesystems ignore case. Known false positive on Linux: `.SSH` is blocked. |
| Windows separators | In path values and in a Bash command, `\` becomes `/` before anything else. A drive prefix needs no handling because every pattern matches a path suffix. | Verified on a POSIX host only. NTFS stream names, trailing dots and 8.3 short names are not handled. |
| Directory roots | `/h/.ssh` matches as well as `/h/.ssh/x`. | Reading or listing the credential directory itself must be refused. A search that starts in a parent directory is a different case, see Does not cover. |
| Length of a path value | Over 4096 characters: refused. | Bounds the work and fits `PATH_MAX`. |
| Length of a Bash word | Over 4096 characters: no expansion and no filesystem lookup, only the text patterns. A command over 200,000 characters is refused. | A commit message, an inline script or a base64 blob is not a path and must pass; the command cap and the expansion bound keep the text work linear in at most 200,000 characters (one word of 200,000 slashes takes about 0.07 s). Known false positive: a heredoc that writes a file of more than 200 KB through Bash. |
| Variable expansion | `$VAR` and `${VAR}` are expanded without building a result longer than 200,000 characters for a command or 4096 for a path value; a longer expansion exits 2 (`check failed`). | Without the bound, a 6 KB environment value referenced 33,000 times kept the hook running past its 10-second timeout, which is fail-open; the stdlib expansion does quadratic work. New false positive: a command or path value whose expansion passes the bound. |
| Relative paths | Resolved against the payload `cwd`; if absent, the hook's own working directory. | The hook runs in the session directory (unverified). |


## Install

1. Copy `scripts/deny_sensitive.py` to `project/.claude/hooks/deny_sensitive.py`.
2. Merge the JSON block above into `project/.claude/settings.json`.
3. Add one line to the orchestrator's error policy: a refusal from the guard is final for that call; rephrasing the same path is not a retry.
4. Run the probes in SKILL.md Step 6.7. Its last probe is a live blocked call in a Claude Code session: ask the agent to read the non-existent file `~/.ssh/c5-probe`; the guard's stderr line, `deny_sensitive: sensitive-path: ...`, must come back as the refusal. A returned refusal shows this host ran the hook and honoured exit 2 for a read. It does not show that Bash words, MCP tools or subagents are covered, that `cwd` and `command` reach the hook, what a timeout does, or that the hook runs on chat or Cowork; none of that is checked.

## Does not cover

- Obfuscated shell. The script cuts a command into words; it does not run a shell. `cat ~/.ne*rc`, brace expansion that splits a name (`cat ~/.kube/{config,x}`, `cat ~/.{net,npm}rc`, `cat ~/.n{e,}trc`), a name assembled from variables, a quote or backslash inside the name (`~/.ss""h/config`, `~/.net\rc`), and encoded paths pass. This is a tripwire, not a sandbox.
- A relative word after a `cd`: `cd ~/.kube && cat config` resolves `config` against the payload `cwd`, not the new directory.
- A search or archive that starts in a parent directory: `grep -rn x ~`, `tar czf /tmp/b.tgz ~`, `find ~ -name x`, or a `Grep` with `path` set to `/home`. The credential directory is reached by the tool, not named in the call.
- Other argument names. A `Glob` `pattern` holding an absolute credential path, a list-valued `paths` argument, a `root` argument and an MCP argument named `filepath` are not read.
- Known false positives, all refused: a project-local `.npmrc`, `.pypirc`, `.kube/config` or `.docker/config.json`; a test fixture named `id_rsa`; a directory named `.ssh` anywhere in the project; a bare word that equals a credential file name or contains `/.ssh/` in any Bash command, for example `git commit -m 'document ~/.ssh/config usage'` or a heredoc that mentions `~/.aws/config`; `.SSH` on Linux; a bare word `.ssh`, `.aws`, `.azure` or `.gnupg` (a grep pattern, a jq filter, a git pathspec); a word that becomes a bare credential name once cut at `:` `,` `{` `}` (a git `rev:path`, a JSON key); a tool input nested more than about 1,000 levels; a path through more than 40 symlinks; a command of more than about 16,384 divided by (depth of the working directory + 2) distinct words, any word and not only paths (about 2,000 at depth 6; the budget); a URL or word that ends in a credential file name (`curl https://h/x/.npmrc`); a variable whose value is a credential path (`echo $KUBECONFIG`); an expansion past the bound above; a Bash command over 200,000 characters.
- Copies, hard links and files opened by a process the hook never sees.
- A symlink made and followed inside one Bash command: the hook runs before that command does.
- A Windows host, and any claim about hooks on chat or Cowork: unverified.
- A user who deletes the hook entry. The guard protects against the model, not against the operator.

Adapted from references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:59 (MIT) for the exit-code contract and from references/openharness/src/openharness/permissions/checker.py:20 (MIT) for the credential patterns.
`````

### D4. Prose edits (exact anchors; `edits.py` below applies all of them (revisions 3 and 4 changed only the E3 item, by one phrase) and asserts each anchor occurs exactly once)

Anchor lines, quoted from the files as they stand:
- E1, `SKILL.md:94`: `- Model per agent from \`references/model-selection-guide.md\`: fable only for the layer that plans and runs long; opus for design, generation, judging; sonnet by default.` Insert one bullet after it: "Guard hook (Claude Code only)...", ending with the attribution `(adapted from references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:59 (MIT))`.
- E2, `SKILL.md:114`: the `- **Connector preflight** (only when an agent has ...` bullet. Insert after it the "Guard hook note" bullet.
- E3, `SKILL.md:147`: `6. **Record** one happy-path and at least one error-path scenario under \`## Test scenarios\` in the orchestrator.` Insert item "7. **Guard hook proof**" after it.
- E4, `SKILL.md:183`: the last checklist line, `- [ ] If the harness builds software: ...`. Insert one checklist line after it.
- E5, `SKILL.md:198`: `- Borrowing from other harness repos under licence rules: \`references/source-enrichment.md\``. Insert the reference line after it.
- E6, `surfaces.md:124`: the `agents/*.md` custom types row of §3b. Insert one row after it; chat cell says hooks were reported as not exposed (observed 2026-10-03, already recorded at `surfaces.md:65`), Cowork cell `unverified`.
- E7, `surfaces.md:140`: the §4 `Hooks` row: the Code cell gains "(command hooks; kit in `references/hooks.md`)". The chat and Cowork cells are byte-identical to today.
- E8, `surfaces.md:161`: §6 row 7. Insert row 8 after it.

```python
def edit(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, (path, old[:40], s.count(old))
    open(path, "w").write(s.replace(old, old + "\n" + new))
S = "skills/finhub-harness/SKILL.md"; F = "skills/finhub-harness/references/surfaces.md"
edit(S, "- Model per agent from `references/model-selection-guide.md`: fable only for the layer that plans and runs long; opus for design, generation, judging; sonnet by default.",
"- Guard hook (Claude Code only): when an agent can write files or run shell commands and the harness handles client or credential data, ship the credential-path guard in `references/hooks.md`: the script `scripts/deny_sensitive.py` plus one `PreToolUse` entry. Chat reported no hooks and Cowork is unknown, so there the prose rules in the agent body stay the only guard. (adapted from references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:59 (MIT))")
edit(S, "- **Connector preflight** (only when an agent has `## Required connectors`): Step 0 ends with the preflight item from Template A Step 0 in `references/orchestrator-template.md`, holding one agent → connector row per declared line. On Claude Code a missing connector stops the run before any spawn; on chat and Cowork the orchestrator warns and asks instead, because connector listings there are deferred and an absent name is not proof (`references/surfaces.md` §4).",
"- **Guard hook note** (only when Step 3 shipped the guard): one line in the error policy saying a refusal from the guard is final for that call and that rephrasing the same path is not a retry, so agents do not loop on a block (`references/hooks.md` Install step 3).")
edit(S, "6. **Record** one happy-path and at least one error-path scenario under `## Test scenarios` in the orchestrator.",
"7. **Guard hook proof** (only when Step 3 shipped the guard): from the project root, pipe `{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"/home/u/.ssh/id_rsa\"},\"cwd\":\"/work\"}` into `python3 .claude/hooks/deny_sensitive.py` and check that it prints a reason and exits 2; the same call with `/work/a.txt` exits 0; the text `garbage` exits 1. Then run the closing check, Claude Code only: in a live session ask the agent to read the non-existent file `~/.ssh/c5-probe` and confirm that the guard's line `deny_sensitive: sensitive-path: ...` came back as the refusal, and that `/hooks` lists the entry. A returned refusal shows this host ran the hook and honoured exit 2 for a read; it does not show that Bash words, MCP tools or subagents are covered, that `cwd` and `command` reach the hook, what a timeout does, or that anything runs on chat or Cowork. The `settings.json` shape stays unverified until this passes (`references/hooks.md`).")
edit(S, "- [ ] If the harness builds software: QA runs the repo's real gates after every slice and reports `RESULT:` first.",
"- [ ] If the harness ships the guard hook: the Step 6.7 script probes exit 2, 0 and 1, the live probe returned the guard's refusal line, `/hooks` lists the entry, and the report says chat reported no hooks and Cowork is unknown, so neither is guarded.")
edit(S, "- Borrowing from other harness repos under licence rules: `references/source-enrichment.md`",
"- Guard hook kit for Claude Code harnesses: `references/hooks.md`")
edit(F, "| `agents/*.md` custom types | used | believed not applicable (unverified) | uncommon; unverified |",
"| `.claude/hooks/deny_sensitive.py` and its `hooks` entry in `settings.json` | used | not applicable (hooks reported as not exposed, observed 2026-10-03) | unverified |")
edit(F, "| 7 | Connector preflight | Every agent's `## Required connectors` line has a row in the orchestrator's Step 0 preflight table; the Code branch stops before any spawn; the chat/Cowork branch warns and asks and never stops on its own |",
"| 8 | Guard hook | If shipped, it is declared Code-only; the single-context fallback does not rely on it and says its prose rules are the only guard there |")
s = open(F).read(); old = "| Hooks | ✓ | ✗ (observed 2026-10-03, self-reported) | unverified (rare) |"; assert s.count(old) == 1
open(F, "w").write(s.replace(old, "| Hooks | ✓ (command hooks; kit in `references/hooks.md`) | ✗ (observed 2026-10-03, self-reported) | unverified (rare) |"))
```

The `7.` item reads each probe literally so a builder cannot reinterpret it: exit 2 with a reason for the `.ssh` call (the payload carries `cwd`), exit 0 for `/work/a.txt`, exit 1 for `garbage`, then the closing live check. Its stated limits, now including that `cwd` and `command` are not shown to reach the hook, are in the item itself.

### D5. Lint and packager treatment

- `lint_harness.py` is not changed. It checks agent and skill definitions; the hook script and `hooks.md` are neither. A lint rule for the hook wiring would only restate the matcher check (D45), and the shipped matcher is the constant `*`, valid by construction. The wiring is pinned instead by `test_wiring_block_in_hooks_md` and, in a generated harness, by the Step 6.7 live `/hooks` check. Reconsider a lint rule only if a harness ships a custom matcher.
- `lint_harness.py .` on the edited tree: 0 errors, 0 warnings (run in a scratch copy). `hooks.md` carries no v1 artefact string and the lint does not scan `references/` files other than nested `SKILL.md`.
- `package-plugin.sh` is not changed. It zips all of `skills/`, so the script and `hooks.md` ship in `dist/finhub-harness.plugin` and `dist/finhub-harness-skill.zip` (2 matching entries each) and not in the evolve zip (0). Run in the scratch copy: exit 0. The zip may drop the script's execute bit; the wiring runs it as `python3 <path>`, so none is needed.

### Hook protocol, as the generated harness depends on it

Stated once in `hooks.md` (table "What the host and the script agree on"). Every row marked "Unverified" there is pinned by a test, and the table is the only place a statement about what the host does may sit; the allow-list test enforces that.

| Point | Behaviour | Checked against |
|---|---|---|
| stdin | one JSON object read as bytes, integers kept as text; uses `tool_input` (object, required) and `cwd` (string, optional) | deepseek `index.ts:324-340` (payload built); plugin-dev skill text lists the same fields. Official docs page: UNVERIFIED (not opened) |
| deny | exit 2, reason on stderr (ASCII-escaped), nothing on stdout | `codec.ts:66-68`; plugin-dev text agrees; official page UNVERIFIED |
| other non-zero, signal, cannot run | non-blocking | `codec.ts:3-4`, `runner.ts:89-91`, `:96-98`; official page UNVERIFIED |
| empty or non-JSON stdin, invalid UTF-8, missing or non-object `tool_input` | exit 1 (non-blocking), no traceback | NET-NEW choice (A25); reference decoders only cover malformed hook *output* |
| nested JSON beyond the parser's limit | exit 2 (blocking); an integer of any length parses (`parse_int=str`) | NET-NEW choice (A25), revised in r2 and r3 |
| failure after a successful parse; a command over 200,000 characters; a variable expansion over its bound; a walk over budget | exit 2 (blocking) | NET-NEW choice, mirrors the runtime guard's "any error denies" (A24, A26, A38, A39) |
| non-string tool values | ignored | UNVERIFIED assumption that the host rejects them; now a row in hooks.md (B4) |
| timeout | wiring sets 10 s; effect of a timeout UNVERIFIED, treated as fail-open, which is why the walk is bounded (A38) | `runner.ts:74` (override), `:20` (600 s default here), plugin-dev text says 60 s: sources disagree |
| hooks in parallel, sibling allow overriding deny | UNVERIFIED for Claude Code; deepseek merges deny above allow (`merge.ts:62`) | plugin-dev text says parallel and mutually blind |
| matcher `*`, `${CLAUDE_PROJECT_DIR}`, stdout on exit 2 | UNVERIFIED for Claude Code (rows in hooks.md) | `matcher.ts:14`, `config.ts:52-60`, `codec.ts:72` (deepseek bridge only) |
| wiring shape in `settings.json` | UNVERIFIED until the live check passes | `loader.py:657` accepts both shapes in a plugin hooks file; plugin-dev text is inconsistent between wrapper and top-level |
| broken wiring file | in the deepseek bridge a load failure registers nothing, so the guard silently turns off | `index.ts:114`; hence the live check, not just the file test |

### Deny rules and path semantics (decisions)

Every decision below is implemented in `check()`, `resolve()`, `candidates()` and `main()` and has test cases and mutants.

| Question | Decision | Justification |
|---|---|---|
| What is matched | `file_path`, `notebook_path`, `path`, plus each distinct word of a Bash command | Covers the Read/Write/Edit/NotebookEdit/Glob/Grep path arguments and the shell example in the backlog proof. Other fields (a write's `content`) are never read, so a document may mention `~/.ssh` |
| Word boundaries | `$VAR` and `${VAR}` expanded over the command (bounded, see Variable expansion), backslashes to `/`, then one `re.split` at whitespace, `; & \| ( ) < > `, backtick, both quotes and `= : , { }` | The end-anchored patterns (`*/.npmrc`, `*/id_rsa`, ...) only match when the word ends at the file name; punctuation glued to the name defeated `shlex` (r1) and then the shorter class (r2: `docker run -v ~/.ssh:/k`, `${X:-~/.netrc}`). Expanding variables first keeps `${HOME}/lnk/x` working after braces became separators. One character class is linear |
| Order of work | pass 1 checks the text of every word and path with no filesystem call; pass 2 follows symlinks | A deny must not wait for the filesystem: a 300-link chain and 12,000 words kept r2 running past its timeout while the credential word sat last |
| Symlink walk | `resolve()` counts every component popped (budget 16,384 per call) and every link followed (40 per path); over either: exit 2, rule `path-budget`. Every distinct word of any kind costs depth(cwd) + 2 components, so the limit is 16,384 // (depth + 2) distinct words: 5,461 at depth 1, 3,276 at depth 3, 2,048 at depth 6, 1,638 at depth 8, 963 at depth 15 (measured by bisection) | The numbers are the runtime guard's (`RESOLVE_COMPONENT_BUDGET`, `MAX_SYMLINKS`); the kernel refuses more than 40 links, so a refusal loses nothing openable. Measured worst case 0.16 s. False positives: a command with more than 16,384 // (depth + 2) distinct words, whatever the words are; a path through more than 40 links |
| Traversal | join with `cwd`, then `posixpath.normpath` (pass 1); `..` handled during the walk (pass 2) | `/w/x/../../h/.aws/config` denied; `/w/.ssh/../a.txt`, `/w/.ssh//../a.txt` and `/w/.ssh/./../a.txt` allowed; `link/../k` follows the link first |
| Symlink forms | the normalised path and the resolved path are both matched | Resolved: a link named `lnk` into `~/.ssh`. Normalised: `~/.kube` kept as a link into a dotfiles directory |
| `~`, `$VAR` | `expanduser` then a bounded `expand_vars` per value, and `expand_vars` over the whole command | Without it `~/link/x` is not followed through a link in the home directory; tested with a temp HOME, also glued to a separator |
| Case | `casefold` the path, both forms | macOS and Windows ignore case; false positive on Linux accepted and documented |
| Windows separators | `\` to `/` in path values (after the join) and in a Bash command (before the cut) | `cat C:\Users\u\.ssh\id_rsa` unquoted was a bypass in r1. A drive prefix needs no handling: every pattern matches a path suffix. POSIX host only |
| Directory root | the form with a trailing `/` is matched too | Reading or listing the credential directory itself must be refused |
| Length of a path value | over 4096 characters: exit 2, rule `too-long` | bounds work, mirrors `PATH_MAX` |
| Length of a Bash word | over 4096 characters: text patterns only, no expansion and no filesystem lookup | a commit message or base64 blob is not a path; a 198,000-character word costs 0.06 s instead of 1.6 s |
| Length of a command | over 200,000 characters: exit 2 | keeps the text work linear (one 200,000-slash word 0.07 s) |
| Variable expansion | `expand_vars()` raises before building a result longer than 200,000 characters (command) or 4096 (path value); exit 2 (`check failed`) | the stdlib `os.path.expandvars` does quadratic work: a 6 KB environment value referenced 33,000 times took 8 s and a 94 KB value over 40 s, past the 10-second hook timeout, which is fail-open. Linear now: 0.02 s for the same inputs. New false positive: an expansion past the bound |
| Integers | kept as text (`parse_int=str`) | no digit count can make valid JSON "unreadable" and fail open; floats and exponents have no such limit |
| NUL byte, lone surrogate, or any other exception after parse | exit 2, `check failed` | fail closed once the call is parsed; NUL raises in `readlink` and a lone surrogate on encode, on Python 3.10-3.13 |
| Patterns | 16, constant | 7 adapted from `checker.py:20-33` (`.aws` widened from two files to the directory), the rest net-new, the same list as the runtime guard minus the `*/.docker` and `*/.kube` roots; stated as the minimum, not an inventory (hooks.md) |
| Empty or non-string values | ignored | assumed, not checked, that the host's schema rejects non-strings (an Unverified row); an empty value would otherwise test the `cwd` itself |

ReDoS and size: the 16 patterns compile to one alternation of `fnmatch.translate` outputs and the word splitter is one character class with `+`. The judge swept `RE.match` at 4,096, 200,000 and 1,000,000 characters (worst 324 ms, linear) and `WORD_SPLIT` on 200,000 characters (9 ms). After the r3 changes I re-timed the whole script: 200 KB of distinct short words 0.23 s, distinct deep paths 0.32 s, one word of 200,000 slashes 0.07 s, 200,000 quotes 0.02 s, and the 300-link chain scenarios above (0.10 s and 0.15 s). In r4 I re-timed the expansion attacks: the judge's repro with values of 1,111, 5,883, 11,877 and 94,000 bytes 0.02 s each; 49,000 references of a 3-byte value 0.07 s; 99,000 references of a 1-byte value 0.10 s. QA does its own independent sweep per the process lessons.

### Wiring the generated harness ships

The JSON block in `hooks.md` (copied to `project/.claude/settings.json`'s `hooks` key; script at `project/.claude/hooks/deny_sensitive.py`): event `PreToolUse`, matcher `*`, type `command`, command `python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/deny_sensitive.py"`, timeout 10. Matcher, variable and shape are each a row marked Unverified. For a plugin-packaged harness the same entry works in `hooks/hooks.json` with `${CLAUDE_PLUGIN_ROOT}` in place of the project variable (`loader.py:670`, `config.ts:52`); I do not add that variant to `hooks.md` because a generated harness is project-local (`surfaces.md` §1) and the plugin variant is unverified.

## Proof

Run from the repo root after the build. Counts are what I got on the scratch copy.

1. `python3 -m pytest -q tests/test_deny_sensitive.py` : 168 passed. Whole scratch tree (new file + `test_lint_harness.py`): 172 passed.
2. `ruff check`, `black --check` (line length 100), `mypy --strict` on `skills/finhub-harness/scripts/deny_sensitive.py` and `tests/test_deny_sensitive.py`: all clean.
3. Script probes: `echo '{"tool_name":"Read","tool_input":{"file_path":"/home/u/.ssh/id_rsa"},"cwd":"/work"}' | python3 skills/finhub-harness/scripts/deny_sensitive.py; echo $?` prints `deny_sensitive: sensitive-path: '/home/u/.ssh/id_rsa'` on stderr and `2`. With `/work/a.txt`: `0`. With `garbage`: one stderr line and `1`. Stdout is empty in all three.
4. SKILL.md: `wc -l` = 203; `grep -c "deny_sensitive" SKILL.md` = 2; `grep -c "references/hooks.md" SKILL.md` = 4; `grep -c "^7\. \*\*Guard hook proof" SKILL.md` = 1; `grep -c "Step 6.7" SKILL.md` = 1; `grep -c "c5-probe" SKILL.md` = 1; `grep -c "that \`cwd\` and \`command\` reach the hook" SKILL.md` = 1; `diff` against the old file shows 5 added lines and 0 removed.
5. surfaces.md: `grep -c "^| 8 | Guard hook"` = 1; `grep -c "deny_sensitive"` = 1; `grep -c "hooks.md"` = 1; `diff` shows 1 removed and 3 added lines (the removed line is the old `Hooks` row, replaced by its edited form).
6. `python3 skills/finhub-harness/scripts/lint_harness.py .` : 0 errors, 0 warnings. `bash scripts/check-harness-refs.sh | grep -c FAIL` = 0. `bash scripts/package-plugin.sh` exits 0, and `unzip -l` of the plugin and skill zips each list 2 entries matching `deny_sensitive.py` or `references/hooks.md`, the evolve zip 0.
7. Hangul check on the new or edited files: no match (`grep -P '[\x{AC00}-\x{D7A3}]'` exit 1).
8. Verbatim check: every 8-word run in `hooks.md`, the script, the test file and the lines added to `SKILL.md` and `surfaces.md`, against the 47 files under the cited deepseek hooks packages and the cited openharness files: 0 shared runs. Attribution lines: script docstring (2 lines), `hooks.md` last line, E1 bullet.
9. `grep -rn "run no hook\|no hook runs" skills` = 0 (Cowork is unknown, not "no hook").
10. Live check, by the person running a generated harness, not by CI: the Step 6.7 closing probe (a real blocked read of `~/.ssh/c5-probe`) and `/hooks`. UNVERIFIED until run on Claude Code. What it cannot prove is written in the step and in hooks.md Install step 4.


11. Named greps in the Authority List, re-run against the CURRENT `hooks.md`, `SKILL.md` and `surfaces.md` (scratch tree with `edits.py` applied). Result per row:

| row | check | result |
|---|---|---|
| A30 | `grep -c "hooks.md"` / `"deny_sensitive"` in surfaces.md | 1 / 1 (expected 1 / 1) |
| A30 | `grep -c "^\| 8 \| Guard hook"` in surfaces.md | 1 (expected 1) |
| A35 | `c5-probe` in SKILL.md / hooks.md | 1 / 1 (expected 1 / 1) |
| A35 | `does not show that Bash words` in SKILL.md / hooks.md | 1 / 1 (expected 1 / 1) |
| A36 | `run no hook` or `no hook runs` in SKILL.md, surfaces.md, hooks.md | 0 (expected 0) |
| A37 (r4) | `grep -rn x ~` in hooks.md | 1 (expected 1) |
| A37 (r4) | `project-local` in hooks.md | 1 (expected 1) |
| A37 (r4) | `brace expansion that splits a name` in hooks.md | 1 (expected 1) |
| A37 (r4) | `a `root` argument` in hooks.md | 1 (expected 1) |
| A37 (r4) | `the minimum` in hooks.md | 1 (expected 1) |
| A43 (r4) | `A relative word after a `cd`` in hooks.md | 1 (expected 1) |
| A43 (r4) | `a bare word `.ssh`` in hooks.md | 1 (expected 1) |
| A43 (r4) | `more than 40 symlinks` in hooks.md | 1 (expected 1) |
| A43 (r4) | `a command of more than about 16,384 divided by (depth of the working directory + 2) distinct words` in hooks.md | 1 (expected 1) |
| A44 | `that `cwd` and `command` reach the hook` in SKILL.md / hooks.md | 1 / 1 (expected 1 / 1) |
| A45 (new) | `| Variable expansion |` row in hooks.md | 1 (expected 1) |
| A47 (new) | `echo $KUBECONFIG` and `curl https://h/x/.npmrc` in hooks.md | 1 / 1 (expected 1 / 1) |
| A29 | `lint_harness.py .`, `package-plugin.sh`, zip contents | run on the scratch tree below: lint 0 errors 0 warnings, packager exit 0, plugin and skill zips 2 matching entries each, evolve zip 0 | see Proof 6 |

## Test plan

Unit cases (all in D2, 168 in total): 30 deny paths (each of the 16 patterns, directory roots including `/h/.SSH`, traversal, case including `.AZURE`, `.GNUPG`, `/H/.NETRC`, `.KUBE/CONFIG`, Windows separators), all sent with a payload `cwd`; 20 allow paths; each of the 3 path keys; ignored fields; symlinks through `~`, `$HOME`, a real link, a credential-named link, a link to a `.SSH` directory, a `.SSH` link to an innocent directory, `..` after a link, `.` before `..`, an absolute link target that leaves a credential directory, a relative link target, a case-sensitive pair of links (`Zk`, `zk`), `${HOME}`, a blank path and an integer path under a credential `cwd`; `cwd` cases; 33 Bash deny commands (adds `cat ~\\.kube\\config` and the Windows docker path); 16 Bash allow commands (adds 199,998 characters of two-byte words); 16 separators each glued after a credential word and before a `~` word; the budget (1,000 and 5,000 words, the 8,192/8,193 pair for 16,384 components, `/a` or `/a/b` after 8,191 words) and, new, the depth-1, depth-8 and depth-15 thresholds (5,461, 1,638, 963 distinct words, each allowed and refused one word later); the 40/41-link boundary; the 300-link chain with 12,000 words; the three brace-expansion passes and the sentence that documents them; variable expansion: 5,883- and 94,000-byte values referenced 33,313 times, two 94 KB references allowed and three refused, the 200,000-character boundary through two 100,000-byte variables, the 4096 path-value boundary through two 2,048-byte variables, 800 references of a 94 KB value in a path, ASCII variable names and an unset `${NOPE:-~/.netrc}`; 1,500 words with the credential word last; a 2,000,000-character payload; stray invalid UTF-8; six numbers beside a sensitive path and beside a harmless one; 10 malformed inputs; deep nesting and bare `[` x 200,000; raw UTF-8 under `ascii` and `cp1252`; NUL and lone-surrogate fail-closed; the 4095/4096 path boundary; four hostile-regex timings; the wiring block; twelve protocol rows still marked Unverified; the allow-list of host sentences; the hashes of the ten hook lines in `SKILL.md` and `surfaces.md`.

Must still pass, unmodified: `tests/test_lint_harness.py` (4), the rest of `tests/`, `check-harness-refs.sh`, `package-plugin.sh`.

Mutation targets. I applied each to a scratch copy by exact single-occurrence substitution (count asserted == 1, result asserted different), one fresh pytest process per mutant (four at a time). **213 mutants run: 203 killed, 10 survive by classification, 0 other survivors, 0 bad anchors.** All 10 survivors are equivalent on every input: `J-N07` (`casefold` to `lower`), `J-N22` (doubled-slash directory probe), `J-N10` (`except (OSError, ValueError)`: no other class is reachable there), `J-N12` (skipping words that contain `://`: `:` is a separator, so no word can), `R01` (swapping `expanduser` and the bounded expansion), `R02` (no `+` on the splitter), `R03` (`sorted(set())` for `dict.fromkeys`), `R04` (last 200 characters in the message), `R07` (`fullmatch` for `match`: every pattern ends in `\\Z`), `X20` (first line of the reason only: message-only). `dedupe-dropped` and `A33-long-word-gets-full-check` are killed (the budget), as in r3. 13 mutants are the judge's round-1 set, 20 the round-2 R-series and 11 the round-3 X-series (the six gaps X06, X07, X13, X15, X17, X24 and five more), adapted to the revision-4 code. Runner: `_workspace/02_strategy-architect_C5_mutate.py` (`C5_REPO=<scratch tree laid out like the repo>`; QA should re-verify each mutation is real in its own fresh process, as the process lessons require). Families (r3 families unchanged except where noted):
- exit codes and call sites: deny 2 to 1, 0 and 3; recursion 2 to 1 and 0, clause dropped; malformed 1 to 0 and 2; fail-closed 2 to 0 and 1; allow 0 to 1; `sys.exit(main())` dropped; `parse_int=str` dropped, `float` (X17); stdin capped, decoded with `ignore`, read as text; deny text on stdout; reason `!r`, untruncated, first line only;
- parse boundary: each of three caught exception types removed; `Exception` narrowed; the `tool_input` dict check dropped and inverted; `tool_input` defaulted (X21);
- `cwd` and joins: ignored, non-string accepted, join dropped, arguments swapped (N03), backslash replace dropped, lexical form and resolved form ignoring `cwd` (N04, N05), `cwd` not passed on; path value stripped (X07);
- path semantics: `expanduser`, the bounded `expand_vars`, command-wide expansion each removed; `normpath` removed; walk removed; pass 1 deny removed; pass 2 list never filled or cut to the first path (X02); `casefold` removed, only for `ssh` and `aws` (R20), resolved form not folded (N19), pass 1 not folded (X24), directory probe not folded (X06); trailing-slash and file forms removed; `or` to `and`; `match` to `search`;
- lengths: `>` to `>=`, 4097, 4095, cap on the joined value (N06), cap counting bytes (R15), long-word threshold plus one (X16), cap applied to words and not to paths, `too-long` returning None, long-word check dropped and always-deny; command cap `>=`, 199,999, 200,001, silent skip, counting bytes (X13);
- variable expansion (new): the bound removed; `>` to `>=`; command limit and path limit made huge; size never grown, started at 0, or not net of the reference length; braces not stripped; an unset variable vanishing; `re.ASCII` dropped; names upper-cased;
- budget, link limit and walk semantics: as r3 (26 mutants);
- keys and Bash: each of the 3 path keys dropped; wrong command key; non-string command accepted; Bash scan skipped; empty-word filter and dedupe dropped; dedupe by lower case (R23); first 1,000 words only (R06); backslash replace before the cut dropped, or made a space (X15); words starting `-` skipped (N11); words containing `://` skipped (N12); each of the 16 splitting characters removed; `maxsplit=1000` (X11);
- patterns: each of the 16 dropped; the widened and narrowed variants of r3;
- wiring, marks and docs: as r3 plus two new: the brace-limit sentence shortened, and its first example removed.

Message-only text (the wording after `deny_sensitive:` beyond the rule name and the `unreadable`, `nested` and `check failed` prefixes) is not pinned; changing the rest is a follow-up, not a defect.

Prose edits have no mutants beyond the hash test; QA applies these to a scratch copy and each must make a named check fail: (a) delete the E1 bullet: `grep -c "references/hooks.md" SKILL.md` drops from 4 to 3 and the hash test fails; (b) change `exit 2` to `exit 1` in the 7. item: Proof 3 and the item disagree and the hash test fails; (c) delete `surfaces.md` row 8: `grep -c "^| 8 | Guard hook"` drops to 0; (d) add a Hangul character to `hooks.md`: check 7 exits 0 instead of 1; (e) delete the live-probe sentence from the 7. item: `grep -c "c5-probe" SKILL.md` drops from 1 to 0.

## Does not cover

- Chat and Cowork. `surfaces.md:65` records that the chat reported hooks as not exposed (observed 2026-10-03, self-reported, one account); Cowork hooks are UNVERIFIED (not "no hook"). Nothing here was run on either surface. The kit is Code only and `hooks.md` says the prose rules are the only guard elsewhere.
- Claude Code's official hooks page was not opened. Protocol rows marked Unverified rest on the deepseek bridge and the plugin-dev skill text, both reimplementations or second-hand. The one check that closes this is Step 6.7's live blocked call plus `/hooks`; even a pass proves only that this host ran the hook and honoured exit 2 for a read.
- What the protocol test cannot catch: a flat claim written without the words Claude Code, Cowork, the host, host or chat; a flat body behind an "Unverified" prefix; a flat claim in another file; a claim that was reviewed and is wrong.
- Timeout behaviour, parallel hooks and whether a sibling hook can override this deny, config reload without restart, and the `settings.json` wrapper shape: UNVERIFIED, stated as such in `hooks.md`.
- Obfuscated shell, globs, `~/.ne*rc`, brace expansion that splits a name (`cat ~/.kube/{config,x}`, `cat ~/.{net,npm}rc`, `cat ~/.n{e,}trc`: all pass, pinned by a test), names built from variables, a quote or backslash inside a name, copies and hard links, races, Windows hosts and NTFS naming tricks. A relative word after `cd`. Parent-directory recursion (`grep -rn x ~`, `tar czf x ~`, `find ~`, a `Grep` with `path=/home`). Argument names not read: a `Glob` `pattern` holding an absolute credential path, list-valued `paths`, `root` (the reference reads it, `query.py:1026`), `filepath`.
- Known false positives, all refused: a project-local `.npmrc`, `.pypirc`, `.kube/config` or `.docker/config.json`; a fixture named `id_rsa`; any directory named `.ssh`; a bare word `.ssh`, `.aws`, `.azure` or `.gnupg` (`grep -rn .ssh docs/`, `jq '.ssh' f`, `echo .aws`, `git log -- .ssh`); any Bash word equal to a credential file name or containing `/.ssh/`; a word that becomes a bare credential name once cut at `:` `,` `{` `}`; `.SSH` on Linux; a tool input nested more than about 1,000 levels; a path through more than 40 symlinks; a command with more than 16,384 // (depth of the working directory + 2) distinct words, whatever the words are (about 2,000 at depth 6: a long inline script or SQL statement can hit it; use the Write tool); a URL or word that ends in a credential file name (`curl https://h/x/.npmrc`); a variable whose value is a credential path (`echo $KUBECONFIG`, `$GOOGLE_APPLICATION_CREDENTIALS`); a variable expansion past 200,000 characters in a command or 4096 in a path value; a Bash command over 200,000 characters.
- Infrastructure faults make the call proceed: a timeout, a crash of the interpreter before `main`, a missing `python3` or script file. If stderr cannot be written the hook exits 120, also non-blocking (follow-up).
- No audit log (D47) and no hook-output merge (D44): one hook, one decision.
- No lint rule for hook wiring; see D5.
- The tests and the walk were run on Python 3.11 here; the judge ran 3.10, 3.12 and 3.13 on r2. 3.14 is untested.
- Quant guardrails (fees, borrow, slippage, look-ahead, survivorship, train/test leakage): not applicable, no backtest, eval or verifier is touched.

## Follow-ups (not built)

From the judge's lists; none changes a verdict.
- F8 (r1) scope: no `.pgpass`, `.config/gh/hosts.yml`, `.terraform.d/credentials*`, `*.pem`, `.env`, `/etc/shadow`. hooks.md says the list is the minimum.
- F9 (r1) `root` as a path key (the reference reads it): add to `PATH_KEYS` with a test and a mutant when a harness uses a tool with that argument.
- F11 (r1) pin the wording after `deny_sensitive:`.
- Decide whether `Grep`/`Glob` with a parent-directory `path` should be refused when the tool is recursive; needs `tool_name`, which the script does not read.
- A real `settings.json` shape check and a subagent probe once someone can run them on Claude Code.
- (r2 F3) stderr closed or full: the hook exits 120, non-blocking. Write the reason inside `try` and still return 2.
- (r2 F6) `~user` words cost one name-service lookup per distinct word; bounded by the 200,000-character cap, not by the walk budget.
- (r2 F7) hooks.md Windows row says `\` is replaced "before anything else"; for path values it happens after `expanduser`, `expandvars` and the join. Wording only.
- (r3 F1) pass 1 is not literally filesystem-free: each distinct `~name` word makes one `pwd.getpwnam` call (25,000 such words took 0.64 s here); on a host with a networked name service that is the same fail-open class. Say "no symlink walk" or skip `~user` in pass 1.
- (r3 F2) the protocol test is a drift lint. These stay green: a new row in the protocol table with status "Verified"; a Deny-rules row that says the host blocks the call; headings and fenced blocks; "Claude  Code" with two spaces or a line wrap inside the name; a reviewed sentence deleted outright; a flat claim on a SKILL.md or surfaces.md line without the word "hook".
- (r3 F3) `test_hook_lines_in_skill_and_surfaces_are_the_reviewed_ones` prints two bare hash prefixes; print the file and line and say "update HOOK_LINES after review". The hash list lives in the same file, so it forces a change to be visible in review but cannot judge whether the new wording is true.
- (r3 F8, F9, F10) stderr closed or full exits 1 here (r2 said 120): non-blocking either way; hooks.md Input row does not state the fail direction for trailing data, a top-level array or a non-object `tool_input` (all exit 1); duplicate JSON keys: the last wins, as in a JavaScript host.
- (r3 F11) the `$KEYS` expansion makes the A33 residual (`KEYS=/h/.ssh`, `cat $KEYS/<4100 a>`) denied; the sentence in A33 is stricter than needed.
- (r2 F1, F2) a `cd` then a relative word, and quote or backslash splits inside a name, are named in hooks.md only generically; add worked examples when a harness hits them.

## Authority List

| id | claim | evidence | target |
|---|---|---|---|
| A1 | Exit code 2 is the blocking code and stderr becomes the reason | references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:11; references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:66 | D1 `main`, hooks.md |
| A2 | Every other exit code is a non-blocking error | references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:3; references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:4 | D1 `main`, hooks.md |
| A3 | A signal death or a hook that cannot run is non-blocking, so an infrastructure fault never stops the call | references/deepseek_harness/packages/hooks/hook-protocol/src/runner.ts:89; references/deepseek_harness/packages/hooks/hook-protocol/src/runner.ts:96 | hooks.md, Does not cover |
| A4 | Structured JSON on stdout is read only on a clean exit, so a script that prints nothing and exits 2 has no stdout to get wrong | references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:72 | D1, test stdout assertion |
| A5 | A top-level `deny` decision is not honoured; only `approve` or `block` are accepted there, so the kit uses exit 2 and not a JSON deny | references/deepseek_harness/packages/hooks/hook-protocol/src/codec.ts:38 | D1 |
| A6 | The `PreToolUse` payload carries `session_id`, `cwd`, `hook_event_name`, `tool_name` and `tool_input` | references/deepseek_harness/packages/hooks/hooks-claude-code/src/index.ts:324; references/deepseek_harness/packages/hooks/hooks-claude-code/src/index.ts:340 | D1 stdin, hooks.md |
| A7 | In the deepseek bridge the hook runs in the session workspace, which is why a relative path is resolved against the payload `cwd` | references/deepseek_harness/packages/hooks/hooks-claude-code/src/index.ts:145 | D1 `rule`, hooks.md "Relative paths" |
| A8 | A hook `timeout` is in seconds and overrides a default; the default in that bridge is 600 s | references/deepseek_harness/packages/hooks/hook-protocol/src/runner.ts:74; references/deepseek_harness/packages/hooks/hook-protocol/src/runner.ts:20 | wiring `timeout` |
| A9 | `${CLAUDE_PROJECT_DIR}` in a hook command is substituted from config, and `${CLAUDE_PLUGIN_ROOT}` likewise | references/deepseek_harness/packages/hooks/hooks-claude-code/src/config.ts:52; references/deepseek_harness/packages/hooks/hooks-claude-code/src/config.ts:60 | wiring command |
| A10 | Matcher `*`, empty or absent selects every tool; a words-and-pipe matcher is an exact-name list | references/deepseek_harness/packages/hooks/hook-protocol/src/matcher.ts:14; references/deepseek_harness/packages/hooks/hook-protocol/src/matcher.ts:62 | wiring matcher `*` |
| A11 | In that bridge a hook config that cannot be read or parsed registers no hooks and only logs a warning, so a broken wiring file silently disables the guard | references/deepseek_harness/packages/hooks/hooks-claude-code/src/index.ts:114 | Step 6.7 live `/hooks` check |
| A12 | Only command hooks run in that bridge; other types are skipped, so the kit ships the command kind | references/deepseek_harness/packages/hooks/hooks-claude-code/src/config.ts:98; references/openharness/src/openharness/hooks/schemas.py:61 | wiring `type` |
| A13 | A hooks file is accepted with or without a top-level `hooks` key | references/openharness/src/openharness/plugins/loader.py:657 | hooks.md "settings.json shape" row (the status stays UNVERIFIED for `settings.json` itself) |
| A14 | The credential patterns for ssh, gcloud, azure, gnupg, the docker config and the kube config, and two aws files, come from the reference list | references/openharness/src/openharness/permissions/checker.py:20; references/openharness/src/openharness/permissions/checker.py:22; references/openharness/src/openharness/permissions/checker.py:25; references/openharness/src/openharness/permissions/checker.py:27; references/openharness/src/openharness/permissions/checker.py:29; references/openharness/src/openharness/permissions/checker.py:31; references/openharness/src/openharness/permissions/checker.py:33 | D1 `PATTERNS` |
| A15 | Patterns are matched with fnmatch against the path | references/openharness/src/openharness/permissions/checker.py:91 | D1 `RE` |
| A16 | A directory root is matched by also testing the path with a trailing slash | references/openharness/src/openharness/permissions/checker.py:169 | D1 `rule` |
| A17 | A leading `~` is expanded and the path resolved before matching | references/openharness/src/openharness/engine/query.py:1029; references/openharness/src/openharness/engine/query.py:1032 | D1 `rule` |
| A18 | NET-NEW: `.aws` is denied as a whole directory, not just `credentials` and `config`. Reason: sso and cli caches hold tokens. Verification that can fail: DENY case `/h/.aws/sso/cache/t.json`; mutants `aws-two-files` and `aws-one-file` | NET-NEW | D1 `PATTERNS` |
| A19 | NET-NEW: private-key and credential-store names outside the reference list (`.netrc`, `_netrc`, `.npmrc`, `.pypirc`, `.git-credentials`, `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`). Reason: same list as the runtime guard in `src/master_finhub/tools/sensitive_paths.py`. Verification: one DENY case per name; 9 pattern-dropped mutants | NET-NEW | D1 `PATTERNS` |
| A20 | NET-NEW: case-insensitive match. Reason: macOS and Windows filesystems ignore case. Verification: DENY `/h/.SSH/ID_RSA`; mutant `no-casefold` | NET-NEW | D1 `rule` |
| A21 | CHANGED r4. NET-NEW: backslashes become `/`, with no separate drive handling because patterns are suffix patterns. Verification: DENY `C:\Users\u\.ssh\id_rsa`, `..\..\.ssh\k`, Windows-style `cwd`, `cat ~\.kube\config` and `cat C:\Users\u\.docker\config.json` (r4); mutants `no-backslash-replace-in-expand`, `backslash-replace-before-split-dropped`, `X15-backslash-becomes-space-in-command` | NET-NEW | D1 `expand`, `candidates` |
| A22 | CHANGED r4. NET-NEW: both the normalised and the symlink-resolved path are matched. Reason: a link into a credential directory and a credential-named link to a harmless target are both real. Verification: `test_symlinks_tilde_and_cwd` (link cases incl. `.SSH` links); mutants `no-normpath`, `no-resolve`, `J-N19`, `X24-pass1-not-casefolded` | NET-NEW | D1 `check`, `resolve` |
| A23 | NET-NEW: `$VAR` expansion before matching. Verification: `$HOME/lnk/x` case; mutant `no-expandvars` | NET-NEW | D1 `rule` |
| A24 | CHANGED r3. NET-NEW: a path-key value over 4096 characters is refused (`too-long`); a Bash word over 4096 characters gets the text patterns only; a command over 200,000 characters is refused; the text check of every word runs before any filesystem work, and the symlink walk is capped at 16,384 path components per call and 40 links per path, exceeding either exiting 2 (`path-budget`). Reason: 4096 mirrors `PATH_KEYS` values to `PATH_MAX`; 16,384 and 40 are the numbers the runtime guard uses (`RESOLVE_COMPONENT_BUDGET`, `MAX_SYMLINKS` in `src/master_finhub/tools/sensitive_paths.py`) and the kernel refuses more than 40 links, so a refusal loses nothing openable; the direction is deny because a hook timeout is fail-open and the unbounded walk let 12,000 words after a 300-link chain run 13.4 s against a 10 s timeout (judge round 2; reproduced here, 0.10 s after the fix). The r2 reason ("worst case 0.32 s") was false on a filesystem with links and is withdrawn. Verification that can fail: the 4095/4096 path pair; BASH_ALLOW cases (4200-character message, 4097- and 4100-character words, 198,000-character word, 200,000-character command); 200,001 refused; the chain test asserts rule `sensitive-path` and under 5 s; mutants `cap->=`, `cap-4097`, `cap-4095`, `J-N06`, `R15`, `cap-applies-to-words-too`, `cap-skips-paths-too`, `command-cap-*`, `pass1-deny-dropped` | NET-NEW | D1 `check`, `resolve`, `candidates` |
| A25 | CHANGED r3. NET-NEW: empty or non-JSON stdin, invalid UTF-8, or a missing or non-object `tool_input` exits 1 and never blocks; JSON nested beyond the parser's recursion limit exits 2; integers are parsed as text (`parse_int=str`), so a 4301-digit or 100,000-digit number beside a sensitive path exits 2. stdin is read as bytes, so a non-ASCII payload under a narrow stdio encoding parses, and the deny reason is written ASCII-escaped. Reason: a hook defect must not brick every tool call, but well-formed host input the parser cannot hold must not fail open (judge round 1: 1100-level nesting and `PYTHONIOENCODING=ascii`; round 2: a 4301-digit integer, exit 1 on Python 3.10-3.13); reference decoders cover only malformed hook output. Floats and exponents checked in the same pass parse without a limit. Verification that can fail: 10 malformed inputs assert exit 1 and no traceback; depth 1100 plus a `.ssh` path and bare `[` x 200,000 assert exit 2; six numbers beside a `.ssh` path assert exit 2 and beside a harmless path exit 0; raw UTF-8 under `ascii` and `cp1252`; a stray invalid byte inside valid JSON gives exit 1; a 2,000,000-character payload is read in full; mutants `malformed-1->0`, `malformed-1->2`, `recursion-2->1`, `recursion-2->0`, `recursion-clause-dropped`, `stdin-text-not-bytes`, `R22-parse_int-dropped`, `R05`, `R17`, `reason-repr-not-ascii`, three `parse-except-no-*` | NET-NEW | D1 `main` |
| A26 | CHANGED r4. NET-NEW: once the call parsed, any error exits 2. Reason: an error is not a licence to allow. Verification: NUL-byte path gives exit 2 and `check failed`; mutants `failclosed-2->0`, `failclosed-2->1`, `except-Exception->OSError` | NET-NEW | D1 `main` |
| A27 | CHANGED r4. NET-NEW: a Bash `command` has `$VAR` and `${VAR}` expanded by a bounded `expand_vars()` (refused, exit 2, if the result would pass 200,000 characters; the command cap is checked first, so the work is one linear pass), backslashes turned into `/`, is cut by one linear `re.split` at whitespace, `;` `&` `|` `(` `)` `<` `>`, a backtick, both quotes and `=` `:` `,` `{` `}`, and each distinct word is checked as a path. Reason: the backlog's own proof example is a shell read of a key; the end-anchored patterns match only when the word ends at the file name, and neither `shlex` (r1) nor the shorter class (r2) split every glued character. Expansion runs first so `${HOME}/lnk/x` is still followed. r3's unbounded `os.path.expandvars` let a 6-12 KB environment value referenced 33,000 times run 3-8 s and a 94 KB value past 40 s, a fail-open timeout (judge round 3; reproduced); r4 measures 0.02 s on the same inputs. New false positives checked: URLs with a port, `git log --format=%h:%s`, `ls /w/a:b`, a JSON argument still pass. Verification that can fail: 33 deny commands, 16 allow commands, 16 separators tested glued after a credential word and before a `~` word, a `${HOME}` link case, `test_variable_expansion_cannot_outlast_the_hook`, `test_command_expansion_bound_is_200000`; mutants `split-class-drops-*` (16), `command-expandvars-dropped`, `backslash-replace-before-split-dropped`, `expand-*` (11), `J-N11`, `J-N12`, `command-key-wrong`, `command-nonstr-accepted`, `bash-skipped` | NET-NEW | D1 `expand_vars`, `candidates` |
| A28 | NET-NEW: only `file_path`, `notebook_path`, `path` and Bash words are read; other fields such as a write's `content` are not. Reason: documents may legitimately mention credential paths. Verification: `test_only_path_keys_and_command_are_read`; the three `key-dropped-*` mutants | NET-NEW | D1 `candidates` |
| A29 | NET-NEW: no lint rule and no packager change. Reason: the script and `hooks.md` are not harness definitions and the packager already zips `skills/`. Verification: `lint_harness.py .` 0 errors 0 warnings, packager exit 0, two zips list 2 entries each, evolve zip 0 | NET-NEW | D5 |
| A30 | NET-NEW: Claude Code only; chat reported hooks as not exposed (observed 2026-10-03, self-reported) and Cowork is unverified. Verification: `grep -c "hooks.md" surfaces.md` = 1 and the `Hooks` row's chat and Cowork cells are byte-identical to the current file | NET-NEW | E6, E7, hooks.md |
| A31 | CHANGED r3. NET-NEW: every statement in `hooks.md` about what the host does sits in a row of the host-protocol table whose status starts "Unverified" (Input, Block, Other exit codes, Stdout, Matcher, Command variable, Timeout, Several hooks on one event, Config reload, `settings.json` shape, Nested JSON, Non-string values), the flat phrases "enforced by the host" and "run no hook" are absent, any new sentence outside the table that mentions Claude Code, Cowork, the host or chat must be added to a reviewed list, and any changed or added hook line in `SKILL.md` or `surfaces.md` fails a hash comparison. Reason: judge round 2 appended a flat claim that left the r2 test green. Verification that can fail: `test_host_protocol_rows_stay_marked_unverified`, `test_no_new_flat_host_claim_in_hooks_md`, `test_hook_lines_in_skill_and_surfaces_are_the_reviewed_ones`; mutants `mark-dropped-*` (12), `flat-claim-readded`, `cowork-flat-claim`, `B4-slip-appended-to-hooks-md`, `B4-slip-in-deny-rules-section`, `B4-skill-line-reworded`, `B4-surfaces-row-reworded`. What it cannot catch is listed under Does not cover | NET-NEW | hooks.md, SKILL.md, surfaces.md |
| A32 | CHANGED r4. NET-NEW: a command's words are deduplicated and empty words skipped, so work is bounded by distinct words. Reason: 100,000 repeats of one word cost 0.79 s undeduplicated against 0.05 s, and with the budget in place the undeduplicated command is refused. Verification: `;` with a credential-directory `cwd` is allowed (an empty word would test the `cwd`); mutants `empty-word-filter-dropped` and `dedupe-dropped` are both killed (the second through the component budget; it is not an equivalent survivor) | NET-NEW | D1 `candidates` |
| A33 | CHANGED r3. NET-NEW: a Bash word over 4096 characters is matched on its text only, not expanded or looked up on disk. Reason: a 198,000-character word costs 0.06 s this way and 1.56 s with the full walk. Verification that can fail: long words containing `/.ssh/` and `\\.ssh\\` are denied; a 198,000-character benign word is allowed; mutants `long-word-text-check-dropped`, `long-word-always-denied`. `A33-long-word-gets-full-check` and `dedupe-dropped` are killed (the full walk on a 198,000-character word, and 100,000 repeated words, both exceed the component budget). One difference remains and is stated, not hidden: a word over 4096 characters built from an environment variable (`KEYS=/h/.ssh` then `cat $KEYS/<4100 a>`) is not expanded; no kernel can open a path that long | NET-NEW | D1 `check` |
| A34 | NET-NEW: a lone surrogate in a path is a second fail-closed trigger beside NUL. Reason: the NUL trigger depends on how the interpreter's `realpath` treats it; the surrogate fails on encode. Verification: `test_check_failure_after_parse_blocks` runs both and asserts exit 2 and `check failed` | NET-NEW | D2 |
| A35 | NET-NEW: Step 6.7 closes with a live blocked read of the non-existent `~/.ssh/c5-probe` in Claude Code, and states that a pass does not cover Bash words, MCP tools, subagents, timeouts, chat or Cowork. Reason: the script probes cannot show that the host runs the hook or honours exit 2. Verification: `grep -c "c5-probe"` is 1 in SKILL.md and 1 in hooks.md; `grep -c "does not show that Bash words"` is 1 in each; deleting the sentence drops the count to 0 | NET-NEW | E3, E4, hooks.md Install |
| A36 | NET-NEW: hooks.md line 1, E1 and E4 say chat reported no hooks (observed 2026-10-03, self-reported) and Cowork is unknown; neither is guarded. Reason: consistency with `surfaces.md:65` and A30. Verification: `grep -rn "run no hook\|no hook runs" skills` returns 0 lines; mutant `cowork-flat-claim` | NET-NEW | hooks.md, E1, E4 |
| A37 | CHANGED r4. NET-NEW: hooks.md names the limits the judge found: parent-directory recursion, brace expansion that splits a name (with `~/.kube/{config,x}`, `~/.{net,npm}rc` and `~/.n{e,}trc`, all of which pass), a `root` argument, the project-local false positives, and states the pattern list is a minimum. The r3 text of this row carried a grep for the words "brace expansion" that returned 0 on the delivered hooks.md; the sentence had been deleted. Verification that can fail: `grep -c "grep -rn x ~"`, `"project-local"`, `"brace expansion that splits a name"`, `"a \`root\` argument"` and `"the minimum"` are each 1 in the CURRENT hooks.md (Proof 11 shows the run); `test_name_splitting_brace_expansion_is_a_documented_pass` fails if a brace form stops passing, `test_the_brace_limit_stays_documented` fails if the sentence or an example is removed; mutants `brace-limit-sentence-dropped`, `brace-example-dropped` | NET-NEW | hooks.md |
| A38 | CHANGED r4. NET-NEW: the symlink walk is bounded to 16,384 path components per call; exhaustion exits 2 with rule `path-budget`. Every distinct word of any kind (a flag, a heredoc token, not only a path) is joined to `cwd` first and costs depth(cwd) + 2 components, so the limit is 16,384 // (depth + 2) distinct words: measured by bisection through the script, 5,461 at depth 1, 3,276 at depth 3, 2,048 at depth 6, 1,638 at depth 8, 963 at depth 15. Reason: the unbounded `os.path.realpath` let a symlink chain plus thousands of words outlast the 10 s hook timeout, which is fail-open; the number is the runtime guard's. False positive: a command with more than that many distinct words, for example a long inline script or SQL statement in a deep project (r3 wrongly said "about 3,000 distinct paths"). Verification: 1,000 words allowed and 5,000 refused; the 8,192/8,193-word pair that spends exactly 16,384 components; `/a` and `/a/b` after 8,191 words; `test_budget_is_16384_over_depth_plus_two_distinct_words` at depths 1, 8, 15 (allowed at the threshold, refused one word later); mutants `budget-16385`, `budget-16383`, `budget-huge`, `budget-tiny`, `budget-test-<=0`, `budget-step-2`, `budget-never-charged`, `budget-per-word`, `budget-exhausted-allows`, `budget-exhausted-reason` | NET-NEW | D1 `resolve`, `check` |
| A39 | NET-NEW: at most 40 symlinks are followed per path; the 41st exits 2 with rule `path-budget`. Reason: Linux refuses more than 40 itself, so no openable path is lost. Verification: a 40-link chain allowed and a 41-link chain refused; mutants `links-41`, `links-39`, `links-huge`, `links->=`, `links-not-counted`, `keyword-resolve-link-follow-dropped` | NET-NEW | D1 `resolve` |
| A40 | NET-NEW: the text check of every word and path runs before any filesystem call (pass 1), and the walk follows (pass 2). Reason: a deny must not depend on how long the filesystem takes. Verification: the 300-link chain with 12,000 distinct words and the credential word last exits 2 with rule `sensitive-path` (not `path-budget`) in under 5 s; measured 0.10 s against 13.4 s on r2; mutants `pass1-deny-dropped`, `pass2-todo-dropped`, `no-resolve`, `hit-always-None-pass2` | NET-NEW | D1 `check` |
| A41 | NET-NEW: `resolve()` follows `..`, `.`, absolute and relative link targets like `os.path.realpath`, counting as it goes. Reason: the bound needs its own walk. Verification: `..` after a link follows the link target; `.` and an empty component before `..` do not change the parent; an absolute and a relative target; NUL and a lone surrogate still reach exit 2 (`check failed`); mutants `resolve-*` (10) | NET-NEW | D1 `resolve` |
| A42 | NET-NEW: integers are kept as text (`json.loads(..., parse_int=str)`). Reason: Python 3.10.7 and later raise `ValueError` for an integer of more than 4300 digits, which r2 treated as unreadable input (exit 1, fail-open). Verification: 4301-digit, negative 4301-digit and 100,000-digit integers beside a `.ssh` path exit 2; fraction and exponent forms exit 2 as well; mutant `R22-parse_int-dropped` | NET-NEW | D1 `main` |
| A43 | CHANGED r4. NET-NEW: `hooks.md` names the limits found in round 2 and 3: `cd` then a relative word, quote or backslash inside a name, bare `.ssh`/`.aws`/`.azure`/`.gnupg` words, nesting over about 1,000 levels, a path through more than 40 links, a command of more than about 16,384 divided by (depth of the working directory + 2) distinct words of any kind, words that become a bare credential name after the cuts. Verification: `grep -c "A relative word after a \`cd\`"`, `"a bare word \`.ssh\`"`, `"more than 40 symlinks"` and `"a command of more than about 16,384 divided by (depth of the working directory + 2) distinct words"` are each 1 in the CURRENT hooks.md (Proof 11); deleting one drops its count to 0 | NET-NEW | hooks.md |
| A44 | NET-NEW: Step 6.7 and hooks.md Install step 4 add that a passing live probe does not show that `cwd` and `command` reach the hook. Reason: the probe path is absolute and tilde-based, so it uses neither. Verification: `grep -c "that \`cwd\` and \`command\` reach the hook"` is 1 in SKILL.md and 1 in hooks.md; the hash test fails if the SKILL.md line changes without review | NET-NEW | E3, hooks.md |
| A45 | NET-NEW: `$VAR` and `${VAR}` expansion never builds a result longer than 200,000 characters (command) or 4096 (path value); a longer one exits 2 (`check failed`). Reason: the stdlib expansion does quadratic work and a large environment value pushed the hook past its 10 s timeout, which is fail-open; the bound is checked as the result grows, so the work is linear in the 200,000-character input. Verification: a 5,883-byte and a 94,000-byte value referenced 33,313 times exit 2 in under 5 s; two 94 KB references allowed and three refused; the boundary pair at 100,000 + 100,000 against 100,001 bytes (command) and 2,048 + 2,048 against 2,049 (path value); 800 references of a 94 KB value in a path exit 2; ASCII-only names and an unset `${NOPE:-~/.netrc}` match `os.path.expandvars`; mutants `expand-bound-dropped`, `expand-bound->=`, `expand-command-limit-huge`, `expand-path-limit-huge`, `expand-size-not-grown`, `expand-size-start-0`, `expand-ref-length-ignored`, `expand-braces-not-stripped`, `expand-unset-vanishes`, `expand-not-ascii`, `expand-environ-key-upper` | NET-NEW | D1 `expand_vars` |
| A46 | NET-NEW: a deep working directory lowers the number of distinct words a command may have: 16,384 // (depth + 2). Reason: each word is joined to `cwd` and every component counts. Verification: `test_budget_is_16384_over_depth_plus_two_distinct_words` at depths 1, 8 and 15 passes at 5,461, 1,638 and 963 words and refuses at one more; a mutant that charges per word instead of per component (`budget-step-2`, `budget-never-charged`) is killed | NET-NEW | D2, hooks.md |
| A47 | NET-NEW: hooks.md lists, as known false positives, a URL or word ending in a credential file name (`curl https://h/x/.npmrc`), a variable whose value is a credential path (`echo $KUBECONFIG`), and an expansion past the bound. Reason: end-anchored suffix patterns and whole-command expansion refuse these. Verification: `grep -c "echo \$KUBECONFIG"` and `"curl https://h/x/.npmrc"` are each 1 in the CURRENT hooks.md | NET-NEW | hooks.md |
| A48 | NET-NEW: the six test gaps from judge round 3 each have a test that fails on the named mutant: `/h/.SSH` (X06), a blank path under a credential `cwd` (X07), 199,998 characters of two-byte words (X13), `cat ~\.kube\config` (X15), `{"file_path": 5}` under a credential `cwd` (X17), a `.SSH` link to an innocent directory (X24). Verification: mutants `X06-dirroot-probe-not-casefolded`, `X07-path-value-stripped`, `X13-command-cap-counts-bytes`, `X15-backslash-becomes-space-in-command`, `X17-parse_int-float`, `X24-pass1-not-casefolded` are killed | NET-NEW | D2 |
