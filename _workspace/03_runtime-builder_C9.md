# runtime-builder report: C9 (verification gates as data, argv only)

Status: PASS. Deviations: none. Nothing committed or pushed.

## Files
| path | change | sha256 | lines |
|---|---|---|---|
| src/master_finhub/evals/gates.py | created | c46273479692459b86f8dede4a9188308266dbf64482fe9e33599f82d20283bf | 542 |
| src/master_finhub/sandbox/stream.py | modified (+4, cwd keyword) | 180e44ed671760fc402b50d741f98a8f92582954f893025cdf229e72b5200d93 | 227 |
| tests/test_gates.py | created | 7e6c63a2b4a76d27ab5fe6064d9c8a040c42c59c936daa2ccd4a3ad139685aca | 2190 |

Digests match the design (c46273479692459b, 180e44ed671760fc, 7e6c63a2b4a76d27). src/master_finhub/evals/runner.py unchanged, sha256 c34f998b07ad197a9dcfdc090e383e10d0576de243ed83ccc959e1d8e06166e6.
Patch sha256 a383cc8a28a00fd4ac806e27ebed290534262e5789c3aec829c2b55960a156d4 verified; `git apply --check` then `git apply` ok; stat: 3 files, 2736 insertions. HEAD = origin/main = 588dd9b, tree clean before, branch claude/tender-brown-8us2kt.
Final `git status --short`: ` M stream.py`, `?? gates.py`, `?? tests/test_gates.py` (dist/ is gitignored).

## Claims implemented
All of the design's Authority List (incl. N37-N45) via the byte-exact patch; nothing added. Follow-ups NOT built (for the PR description): SHELL_RUNNERS list extensions, SIG_IGN skip for SIGHUP, post-run recheck for links made by earlier gates, copies/hard links, widening the shell-name list, busybox host test issue.

## Gate
- tests/test_gates.py: 543 passed under 3.11.15, 3.12.3, 3.13.14 (~14 s each), and 543 passed again with `-W error` under all three.
- Same file, 3.11 .venv, 543 passed under: `bash -c "trap '' INT; ..."`; `trap '' INT HUP`; `setsid --wait nohup ... </dev/null` (plain `setsid` returned before the run, so --wait was used); stdin `</dev/null`; `env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/root`.
- As user nobody: tree copied (no .venv/.git/references) to /tmp/c9b_nobody (chmod a+rX), run with `setpriv --reuid=nobody --regid=nogroup --clear-groups env HOME=/tmp/c9b_nobody/.scratch TMPDIR=... PYTHONPATH=/tmp/c9b_nobody/src .venv/bin/python -m pytest tests/test_gates.py`; uid 65534, module imported from the copy; 543 passed.
- Full `pytest -q`, run one after the other in the foreground: 3.11 `env -u PYTHONUNBUFFERED` 1947 passed, 10 skipped in 115.58 s; 3.11 PYTHONUNBUFFERED=1 1947 passed, 10 skipped in 115.21 s; 3.12 1947 passed, 10 skipped in 117.59 s. No flaky timing test fired.
- `ruff check src tests`: All checks passed (rc 0). `black --check src tests`: 71 files unchanged (rc 0). `mypy --strict src`: no issues in 40 source files (rc 0).
- scripts/check-harness-refs.sh: 0 FAIL, rc 0 (it ends with "PASS packager exit 0"). scripts/package-plugin.sh: rc 0, lint_harness 0 errors 0 warnings.
- Hangul (LC_ALL=C.UTF-8 grep -P '\p{Hangul}') over the 3 files: rc 1. Secrets grep: rc 1.
- Attribution: gates.py line 4 "Policy adapted (MIT, own code) from references/openharness/src/openharness/autopilot/service.py:155".
- Mutation runner (_C9_mutate.py, fresh process per mutant, on a tar copy including .gitignore, skills/, .claude/, scripts/): CONTROL 543 passed; `TOTAL 413: killed 406, survived-equivalent 7, unexpected survivors/partial 0`; 14 KILLED(rerun) (timing-only mutants re-killed serially). Judge mutants (_C9_judge_mutants.py): TOTAL 50 killed 48, survived I45 and I48, bad [] (the design's known equivalents; not rejudged here).
- Scratch: /tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c9b (tree, mscr, jscr, mutate.out, judge.out). /tmp/c9b_nobody created by me, left in place.
