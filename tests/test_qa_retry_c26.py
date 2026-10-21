"""Pins for the C26 rules (an earlier QA FAIL is kept as _r<k> after a passing retry) and the checker behaviour they rest on."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "skills" / "finhub-harness" / "scripts" / "finding_tags.py"
FILES = {
    "qg": "skills/finhub-harness/references/quality-gates.md",
    "qag": "skills/finhub-harness/references/qa-agent-guide.md",
    "otpl": "skills/finhub-harness/references/orchestrator-template.md",
    "bqa": ".claude/agents/boundary-qa.md",
    "orch": ".claude/skills/master-finhub-orchestrator/SKILL.md",
    "wsl": ".claude/skills/master-finhub-orchestrator/references/workspace-layout.md",
}
ATTR = "adapted from references/paperclip/.agents/skills/verify-paperclip/SKILL.md:192 (MIT)"
PINS = [
    ("qg-keeps", "qg", "every earlier attempt keeps its own file"),
    ("qg-format", "qg", "`Earlier attempts: <path> | failed:"),
    (
        "qg-unknown",
        "qg",
        "never says flaky, environment or infrastructure without that command and output",
    ),
    ("qg-never-passed", "qg", "kept reports are never passed to them"),
    ("qag-never-over", "qag", "Never write to a kept `_r<k>` report"),
    ("otpl-earlier-input", "otpl", "`Earlier: <each kept report of the unit, comma-separated>`"),
    ("otpl-never-passed", "otpl", "kept reports are never passed to `candidate_id.py check`"),
    ("bqa-never-over", "bqa", "Never write to a kept `_r<k>` report"),
    (
        "orch-earlier-input",
        "orch",
        "    Earlier: {each kept _workspace/03_boundary-qa_{unit}_r<k>.md",
    ),
    ("orch-move", "orch", "then move the QA report to `_workspace/03_boundary-qa_{unit}_r<k>.md`"),
    ("wsl-except", "wsl", "except a QA report: before a QA retry"),
    ("wsl-resume", "wsl", "a QA retry was due and has not written its report"),
    (
        "qg-gate-use",
        "qg",
        "a kept `_r<k>` report was checked while it was current and is not passed again",
    ),
]

CAND = "git:1a2b3c4d5e6f+0f1e2d3c4b5a6978"
BASE_SHA = "1a2b3c4d5e6f"
EXCL = "5e6f7a8b9c0d"
EARLIER = (
    "Earlier attempts: _workspace/03_boundary-qa_unit_a_r1.md | failed: a.py:1 expected 2, got 1 "
    "| changed: builder fixed a.py (_workspace/03_runtime-builder_unit_a.md) | reason: unknown"
)


def _report(verdict: str, after_head: str, defects: str) -> str:
    head = f"CANDIDATE: {CAND} n=214 excludes=_workspace/\nCARRIED: -\nBASE: git:{BASE_SHA} excl={EXCL}\n"
    drift = (
        f"| drift: declared=3 changed=3 undeclared=- flags=0 excl={EXCL} on={CAND} "
        f'| git -C "$REPO" diff -z --no-renames --name-only {BASE_SHA} | 0 | 3 paths |\n'
    )
    return f"RESULT: {verdict}\n{head}{after_head}\n## Gate\n{drift}\n## Defects\n{defects}"


def _check(path: Path) -> int:
    return subprocess.run(
        [sys.executable, "-I", str(CHECK), "check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    ).returncode


def _text(fid: str) -> str:
    return (ROOT / FILES[fid]).read_text(encoding="utf-8")


def test_overwrite_sentence_gone() -> None:
    assert "overwrites the slice report" not in _text("qg"), "overwrite sentence still present"


@pytest.mark.parametrize(("pid", "fid", "phrase"), PINS, ids=[p[0] for p in PINS])
def test_rule_phrases(pid: str, fid: str, phrase: str) -> None:
    assert phrase in _text(fid), f"c26 phrase missing: {pid}"


@pytest.mark.parametrize("fid", ["qg", "qag", "otpl", "bqa", "orch"])
def test_c26_attribution(fid: str) -> None:
    assert ATTR in _text(fid), f"c26 attribution missing: {fid}"


def test_kept_fail_and_pass_pass_finding_tags(tmp_path: Path) -> None:
    fail = tmp_path / "fail.md"
    fail.write_text(
        _report("FAIL", "", "- defect: a.py:1 expected 2, got 1 cause: judgment-gap\n"),
        encoding="utf-8",
    )
    assert _check(fail) == 0, "kept fail report refused"
    ok = tmp_path / "pass.md"
    ok.write_text(_report("PASS", f"\n{EARLIER}\n", "none\n"), encoding="utf-8")
    assert _check(ok) == 0, "earlier attempts line refused"
