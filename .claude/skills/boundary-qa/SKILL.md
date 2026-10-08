---
name: boundary-qa
description: "Verifies a built Master FinHub runtime slice by comparing shapes across every boundary it touches (tool schema <-> loop call site <-> test fixture/assertion <-> CLI invocation and output), re-running pytest -q, ruff check, black --check and mypy --strict, and writing PASS/FAIL with exact failing output; also writes the final run report (built, passed, gaps, next step). Use for: QA slice N, verify the build, re-run QA, check the slice boundaries, final report, did slice N pass. Not for auditing design citations (use adversarial-audit) or reviewing code in other FinHub repos."
---

# Boundary QA

Most integration bugs live between two files that each look correct alone: the tool declares `path`, the loop sends `file`; the CLI prints `result`, the test asserts on `output`. Read both sides of each boundary together, then let the commands decide.

## Per-slice steps

1. **Load the contract.** Read slice N in `_workspace/02_strategy-architect_slices.md` — its Interfaces and Proof sections are what "correct" means. Read `_workspace/03_runtime-builder_slice{N}.md` for the files touched, but do not trust its gate results.
2. **Walk the boundaries** in `references/boundary-checklist.md` that apply to this slice. For each, open side A and side B and record both shapes in the boundary table. Mismatch = defect with file:line.
3. **Run the gate** from the repo root, each command separately, capturing exit code and output:
   ```
   pytest -q
   ruff check src tests
   black --check src tests
   mypy --strict src
   ```
   Then run the slice's proof command if it has one (e.g. `python -m master_finhub.cli "echo hi"`).
4. **Compliance sweep** of files touched: no real names, emails, phone numbers, account numbers, Mercury ids, API keys or tokens in `src/` or `tests/`.
5. **Write** `_workspace/03_boundary-qa_slice{N}.md`. First line `RESULT: PASS` only if every boundary matches, all four commands exit 0, the proof command produces the expected output, at least one adversarial probe is recorded as a `probe:` or `mutant:` row with its output (a `mutant:` row ends in `STATE: CAUGHT` or `STATE: SURVIVED` from `mutant_gate.py classify`; adapted from references/openrig/packages/test-system/ci/result.mjs:33-34 (Apache-2.0)), and the sweep is clean. Otherwise `RESULT: FAIL`.

## Report format (slice)

```markdown
RESULT: FAIL

# Boundary QA — slice 1

## Boundary table
| boundary | side A | side B | match |
|---|---|---|---|
| echo schema ↔ loop call | tools/builtins/echo.py:8 `params={"text": str}` | runtime/loop.py:54 passes `{"message": ...}` | NO |
| CLI output ↔ test | cli.py:20 prints `result.text` | tests/test_loop.py:31 asserts stdout == "hi\n" | yes |

## Gate
| command | exit | output observed (summary line on success; ≤60 lines on failure) |
|---|---|---|
| pytest -q | 1 | `FAILED tests/test_loop.py::test_echo_round_trip - KeyError: 'text'` |
| ruff check src tests | 0 | `All checks passed!` |
| black --check src tests | 0 | `3 files would be left unchanged.` |
| mypy --strict src | 0 | `Success: no issues found in 3 source files` |
| proof: python -m master_finhub.cli "echo hi" | 1 | `KeyError: 'text'` |
| probe: python -m master_finhub.cli (no argument) | 2 | `error: the following arguments are required: ...` |

## Defects
1. runtime/loop.py:54 — passes `message`, schema declares `text` (expected `text`).
```

## Final report (Phase 4)

Write `_workspace/04_boundary-qa_report.md` for Daniel, who will not read code. Re-run the gate once across the whole tree first.

```markdown
# Master FinHub runtime — run report (2026-10-01 AEST)

## Built
| slice | what it gives you | files |
|---|---|---|
| 1 | Agent loop runs a tool and stops | runtime/loop.py, tools/builtins/echo.py, cli.py |

## Passed
| slice | pytest | ruff | black | mypy | proof |
|---|---|---|---|---|---|
| 1 | pass | pass | pass | pass | `echo hi` → `hi` |

## Gaps
- Slice 3 FAIL after one retry — mypy: `sandbox/workspace.py:22 Returning Any` (verbatim output in 03_boundary-qa_slice3.md).
- Claims still UNVERIFIED in code: A7 (guarded by tests/test_router.py::test_profile_fallback).
- Slices 4–11 not started.

## Next step
Re-run slice 3 after fixing the return type in sandbox/workspace.py.
```

## Rules

- Read-only on code. Report; do not fix.
- Never mark PASS by skipping a command. A missing tool is a FAIL with the install hint (`uv pip install -e .[dev]`).
- Paste real output; never paraphrase an error.
- On re-run, re-check every previously listed defect plus a full gate run.
