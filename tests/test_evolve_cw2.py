"""Pins for the CW2 rules in skills/finhub-harness-evolve/SKILL.md and the exit codes they rest on."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "finhub-harness-evolve" / "SKILL.md"
CHECK = ROOT / "skills" / "finhub-harness" / "scripts" / "finding_tags.py"

NOOP_A = (
    "NO-OP: read one trace and one QA report; nothing named a harness file as the cause.\n"
    "NOT CAPTURED: environment - packager said zip not found on the user's machine\n"
    "NOT CAPTURED: retry - one timeout that cleared on the second attempt\n"
)
NOOP_B = NOOP_A + (
    "LESSON | layer: unclassified | cause: context-gap | evidence: _workspace/feedback.md:1 - "
    "the complaint names no artefact | fix: none - the artefact that would settle it is the run log\n"
)

PHRASES = [
    ("do-nothing", "Do nothing unless the evidence calls for a change"),
    (
        "exit2-note",
        "On a no-op run with no lesson lines that is the expected answer and not a refusal",
    ),
    ("not-captured-format", "NOT CAPTURED: <environment|negative-claim|one-off|retry>"),
    ("fix-source", "Fix the source, not the symptom"),
    ("report-changed", "Report only what changed"),
    ("doing-nothing", "Doing nothing is a result"),
    ("one-entry", "one `remember` call of one short bullet"),
]
ATTRIBUTION = re.compile(
    r"adapted from references/cowagent/agent/evolution/(?:prompts|record)\.py:\d+(?:-\d+)? \(MIT\)"
)


def run_check(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    report = tmp_path / "evolve-report.md"
    report.write_text(body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-I", str(CHECK), "check", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_noop_report_without_lesson_exits_2(tmp_path: Path) -> None:
    proc = run_check(tmp_path, NOOP_A)
    assert proc.returncode == 2, "no-op report exit 2"
    assert "no record in file" in proc.stderr + proc.stdout


def test_noop_report_with_unclassified_lesson_exits_0(tmp_path: Path) -> None:
    proc = run_check(tmp_path, NOOP_B)
    assert proc.returncode == 0, "no-op report with unclassified lesson exit 0"


@pytest.mark.parametrize("phrase", [p for _, p in PHRASES], ids=[i for i, _ in PHRASES])
def test_skill_carries_the_cw2_rules(phrase: str) -> None:
    assert phrase in SKILL.read_text(encoding="utf-8"), f"cw2 phrase missing: {phrase}"


def test_environment_exception_clause_present() -> None:
    text = SKILL.read_text(encoding="utf-8")
    exception = (
        "It is a lesson only when the harness file that should have declared or checked "
        "that prerequisite does not"
    )
    assert exception in text, "cw2 environment exception missing"
    assert (
        "shown by a search that finds nothing (Phase 1 step 6)" in text
    ), "cw2 environment exception missing"


def test_cw2_attribution_lines() -> None:
    found = {m.group(0) for m in ATTRIBUTION.finditer(SKILL.read_text(encoding="utf-8"))}
    assert len(found) >= 7, "cw2 attribution missing"
    key = "adapted from references/cowagent/agent/evolution/prompts.py:61-66 (MIT)"
    assert key in found, "cw2 attribution missing"
