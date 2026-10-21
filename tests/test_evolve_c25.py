"""Pins for the C25 rules in skills/finhub-harness-evolve/SKILL.md (state the change, fresh rerun, decision) and the checker behaviour they rest on."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "finhub-harness-evolve" / "SKILL.md"
CHECK = ROOT / "skills" / "finhub-harness" / "scripts" / "finding_tags.py"

LESSON = (
    "LESSON | layer: routing | cause: context-gap | evidence: _workspace/run1/dispatch.log:2 - "
    "a refund-letter request fell to the default agent | fix: .claude/skills/memo-orchestrator/SKILL.md - "
    "add a refund-letter row to the dispatch table, Why: the table had no row for it\n"
)
CHANGE = (
    "CHANGE | file: .claude/skills/memo-orchestrator/SKILL.md | job: a refund-letter request | baseline: "
    "_workspace/run1/dispatch.log:2 - dispatch fell to memo-writer | expect: dispatch names the letter row | "
    "weakened by: dispatch still logs the default agent | remove when: the team gains a letter agent\n"
)
PENDING = (
    "Decision: pending fresh rerun - next: in a new session, ask for a refund letter for client_a and read "
    "the dispatch line of _workspace/run2/dispatch.log\n"
)
REPORT_CHANGE = LESSON + CHANGE + PENDING
REPORT_KEEP = (
    "NO-OP: closed the 2026-10-04 pending change; no lesson called for an edit.\n"
    "Decision on the 2026-10-04 change: keep - _workspace/run2/dispatch.log:2\n"
)

PHRASES = [
    ("close-pending", "Close an earlier pending change"),
    (
        "decision-row",
        "`Decision on the <date> change: <keep|revise|remove> - <path>:<line>`",
    ),
    (
        "change-format",
        "`CHANGE | file: <the file in fix:> | job: <the kind of run the change is for> | baseline: <path>:<line>",
    ),
    (
        "weakened-by",
        "| weakened by: <what a rerun would show if the change does not work> |",
    ),
    ("remove-when", "| remove when: <the condition under which the change comes out again>`"),
    ("one-change", "a change that needs a second file is a second lesson"),
    ("no-made-up-baseline", "never make a baseline up"),
    ("rerun-heading", "Fresh rerun before any claim"),
    ("blind-input", "(never the lesson, the change or the `expect:` text)"),
    (
        "startup-files",
        "A same-session subagent does not count when the change is to a file the host may load only when a session starts",
    ),
    ("not-count-reread", "re-reading the edited file and reasoning that the job would now pass"),
    ("not-count-self", "doing the job yourself in this conversation"),
    ("keep", "`keep` when it shows the `expect:` result and nothing in `weakened by:`"),
    ("revise", "`revise` when it reached the changed instruction"),
    ("remove", "`remove` when it shows the `weakened by:` evidence"),
    (
        "pending-format",
        "`Decision: pending fresh rerun - next: <the task to run in a new session",
    ),
    ("pending-normal", "Pending is a normal result, not a failure"),
    (
        "history-marker",
        "with `pending fresh rerun;` and the `job:`, `expect:`, `weakened by:` and `remove when:` fields",
    ),
    ("report-claim", "Say that the harness improved only beside a `keep` line"),
    ("principle", "A change is a guess until a rerun shows it"),
    ("report-decision-form", "in the report the same decision is the line"),
    ("noop-reported", "and Phase 5 reports it like any edited file"),
    ("startup-hooks", "`.claude/settings.json` or a hook"),
    ("history-backup", "(`CLAUDE.md` takes the Phase 3 backup gate like any harness file)"),
]
# sha256 of SKILL.md lines 65 and 67 at 864ab77 (LESSON format and cause tag), without the newline.
LESSON_LINES = {
    "1bc557f2b4e84d053291711c8062039a5820d9e8636dd41ac628ccd078615dc2",
    "39d9fd4c69eea469a3ddc1851d65f24665b26b1e56a1b3204a91f91298085dc6",
}
RH = re.compile(
    r"adapted from references/repository_harness/(?:\.agents/skills/improve-harness/SKILL\.md|"
    r"docs/templates/harness-improvement\.md):\d+(?:-\d+)? \(MIT\)"
)
RH_KEYS = [
    "adapted from references/repository_harness/.agents/skills/improve-harness/SKILL.md:61-68 (MIT)",
    "adapted from references/repository_harness/.agents/skills/improve-harness/SKILL.md:75-84 (MIT)",
    "adapted from references/repository_harness/.agents/skills/improve-harness/SKILL.md:86-96 (MIT)",
]
PC_KEY = (
    "adapted from references/paperclip/.agents/skills/fix-failed-paperclip-run/SKILL.md:60-65 (MIT)"
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


def test_change_report_exits_0(tmp_path: Path) -> None:
    proc = run_check(tmp_path, REPORT_CHANGE)
    assert proc.returncode == 0, "c25 change report exit 0"
    assert "1 record(s), 0 refused" in proc.stdout, "c25 change report exit 0"


def test_keep_only_report_exits_2(tmp_path: Path) -> None:
    proc = run_check(tmp_path, REPORT_KEEP)
    assert proc.returncode == 2, "c25 keep-only report exit 2"
    assert "no record in file" in proc.stderr + proc.stdout, "c25 keep-only report exit 2"


@pytest.mark.parametrize("phrase", [p for _, p in PHRASES], ids=[i for i, _ in PHRASES])
def test_skill_carries_the_c25_rules(phrase: str) -> None:
    assert phrase in SKILL.read_text(encoding="utf-8"), f"c25 phrase missing: {phrase}"


def test_old_improvement_line_is_gone() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert (
        "The improvement expected on the next run" not in text
    ), "c25 unchecked improvement line back"


def test_lesson_lines_byte_identical() -> None:
    digests = {
        hashlib.sha256(line.encode("utf-8")).hexdigest()
        for line in SKILL.read_text(encoding="utf-8").splitlines()
    }
    assert LESSON_LINES <= digests, "c25 lesson line changed"


def test_c25_attribution_lines() -> None:
    text = SKILL.read_text(encoding="utf-8")
    found = {m.group(0) for m in RH.finditer(text)}
    assert len(found) >= 5, "c25 attribution missing"
    for key in RH_KEYS:
        assert key in found, "c25 attribution missing"
    assert PC_KEY in text, "c25 attribution missing"
