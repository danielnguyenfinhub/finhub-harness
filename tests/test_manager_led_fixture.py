"""The manager-led fixture team stays lint-clean and keeps the pieces the pattern needs."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "docs" / "fixtures" / "manager-led-team"
LINT = REPO / "skills" / "finhub-harness" / "scripts" / "lint_harness.py"
MANAGER = (FIX / ".claude" / "skills" / "refi-pack-manager" / "SKILL.md").read_text()


def test_fixture_lints_clean() -> None:
    run = subprocess.run(
        [sys.executable, str(LINT), str(FIX / ".claude")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout
    assert "0 error(s), 0 warning(s)" in run.stdout


def test_manager_names_staffing_and_board() -> None:
    assert "## Staffing (who took each job, and why)" in MANAGER
    assert "| existing team |" in MANAGER and "| new specialist |" in MANAGER
    assert "## The board" in MANAGER
    assert "you never fill the gap" in MANAGER


def test_specialists_declare_job_cover_and_lead() -> None:
    for name in ("statement-reader", "payslip-reader"):
        text = (FIX / ".claude" / "agents" / f"{name}.md").read_text()
        assert "Job: " in text and "Covers: " in text and "tools: Read, Write, Skill" in text
        assert "You answer to the lead" in text
        assert "You never mark your own work done" in text
