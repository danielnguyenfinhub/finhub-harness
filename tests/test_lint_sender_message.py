"""The connector-tools-unscoped WARN names the worker file and says exactly how to fix it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
RULE = "connector-tools-unscoped"

ORCH = """---
name: orch
description: Runs the team and sends only after a yes. Use for the outreach job.
---

## Ask before an outside effect

Show every call, send only after a yes.
"""
WORKER = """---
name: drafter
description: Drafts the message text. Use when a draft is needed.
---

Draft the text.
"""


def lint(tmp_path: Path) -> list[str]:
    (tmp_path / "skills/orch").mkdir(parents=True)
    (tmp_path / "skills/orch/SKILL.md").write_text(ORCH)
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents/drafter.md").write_text(WORKER)
    p = subprocess.run(
        [sys.executable, "-B", str(LINT), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return [ln for ln in p.stdout.splitlines() if RULE in ln]


def test_the_warn_names_the_worker_file_and_worker(tmp_path: Path) -> None:
    (line,) = lint(tmp_path)
    assert (
        line.startswith("WARN ") and "agents/drafter.md: " + RULE in line
    )  # the file leads the line
    assert "worker drafter " in line


def test_the_fix_for_a_non_sender_is_a_tools_allowlist(tmp_path: Path) -> None:
    (line,) = lint(tmp_path)
    assert "; fix: if it must not send, add a tools: allowlist without mcp__" in line


def test_the_fix_for_the_sender_gives_the_exact_marker_line(tmp_path: Path) -> None:
    (line,) = lint(tmp_path)
    assert 'if it IS the sending worker, add one body line that starts "Sending worker"' in line
    assert 'and says "approved list"' in line
    assert "Sending worker: sends only the calls on the approved list" in line


def test_the_example_marker_in_the_message_really_clears_the_warning(tmp_path: Path) -> None:
    (line,) = lint(tmp_path)
    example = line.split("for example: ")[1].strip()
    (tmp_path / "agents/drafter.md").write_text(WORKER + "\n" + example + "\n")
    p = subprocess.run(
        [sys.executable, "-B", str(LINT), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert RULE not in p.stdout
