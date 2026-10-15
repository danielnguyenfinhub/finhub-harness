"""A reader that hangs up early (`script | head -1`) ends a script quietly, with exit code 141.

The pipe is made and its read end closed before the script starts, so the first write fails every
time and no timing decides the result. Each script runs once with unbuffered output (the failing
write is a print in main) and once buffered (the failing write is the flush at the end)."""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="pipes and descriptor 1 as on Linux and macOS; CI is ubuntu"
)

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/finhub-harness/scripts"
HANGUP = 141  # 128 + SIGPIPE: the status a shell reports for a writer whose pipe closed


def _cases(tmp: Path) -> dict[str, list[str]]:
    record = tmp / "report.md"
    record.write_text("RESULT: PASS\n", encoding="utf-8")
    pack = tmp / "pack.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("skills/x/SKILL.md", "plain text\n")
    changed = tmp / "changed.txt"
    changed.write_text("src/x.py\n", encoding="utf-8")
    orch = ".claude/skills/master-finhub-orchestrator/SKILL.md"
    sc = str(SCRIPTS)
    return {
        "candidate_id-id": [f"{sc}/candidate_id.py", "id"],
        "candidate_id-check": [f"{sc}/candidate_id.py", "check", "WAIVERS.md"],
        "waiver_ledger": [f"{sc}/waiver_ledger.py", "check", "WAIVERS.md"],
        "finding_tags": [f"{sc}/finding_tags.py", "check", str(record)],
        "rigor_check": [
            f"{sc}/rigor_check.py",
            "check",
            orch,
            "WAIVERS.md",
            "u/x",
            "-",
            str(changed),
        ],
        "mutant_gate": [
            f"{sc}/mutant_gate.py",
            "classify",
            "s",
            "--before",
            "a",
            "--mutant",
            "a",
            "--after",
            "a",
        ],
        "lint_harness": [f"{sc}/lint_harness.py", "."],
        "state_ledger": [f"{sc}/state_ledger.py", "resume", "absent-plan.md"],
        "check_writers": [f"{sc}/check_writers.py"],
        "ship_scan": [str(REPO / "scripts/ship_scan.py"), str(pack)],
    }


NAMES = (
    "candidate_id-id",
    "candidate_id-check",
    "waiver_ledger",
    "finding_tags",
    "rigor_check",
    "mutant_gate",
    "lint_harness",
    "state_ledger",
    "check_writers",
    "ship_scan",
)


@pytest.mark.parametrize("unbuffered", [True, False])
@pytest.mark.parametrize("name", NAMES)
def test_closed_reader_ends_quietly(name: str, unbuffered: bool, tmp_path: Path) -> None:
    argv = _cases(tmp_path)[name]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    if unbuffered:
        env["PYTHONUNBUFFERED"] = "1"
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        run = subprocess.run(
            [sys.executable, "-B", *argv],
            stdout=write_end,
            stderr=subprocess.PIPE,
            text=True,
            cwd=REPO,
            env=env,
            timeout=120,
            check=False,
        )
    finally:
        os.close(write_end)
    assert run.stderr == "", f"traceback on closed pipe: {name}: {run.stderr[-200:]}"
    assert run.returncode == HANGUP, f"exit code on closed pipe: {name}: {run.returncode}"


@pytest.mark.parametrize("name", NAMES)
def test_closed_stdout_keeps_exit_code(name: str, tmp_path: Path) -> None:
    argv = [sys.executable, "-B", *_cases(tmp_path)[name]]
    normal = subprocess.run(argv, capture_output=True, text=True, cwd=REPO, check=False)
    closed = subprocess.run(
        argv,
        stdout=None,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO,
        preexec_fn=lambda: os.close(1),
        check=False,
    )
    assert closed.stderr == "", f"stderr with stdout closed: {name}: {closed.stderr[-200:]}"
    assert (
        closed.returncode == normal.returncode
    ), f"exit code with stdout closed: {name}: {closed.returncode} != {normal.returncode}"
