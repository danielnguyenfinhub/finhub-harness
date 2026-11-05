"""Proof for the send-implicit rule of skills/finhub-harness/scripts/lint_harness.py (RH28).

adapted from references/repository_harness/tests/installer/assert-agent-authority-contract.sh:90 (MIT), holder Hoang Nguyen
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
ASK = "## Ask before an outside effect"


def lint(root: Path, extra_key: str, body: list[str]) -> tuple[int, str]:
    d = root / "skills" / "sender"
    d.mkdir(parents=True)
    head = f'---\nname: sender\ndescription: "D. Use when X."\n{extra_key}---\n'
    (d / "SKILL.md").write_text(head + "\n".join(body) + "\n", encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(LINT), str(root)], capture_output=True, text=True, check=False
    )
    return run.returncode, run.stdout


def test_sender_without_key_warns(tmp_path: Path) -> None:
    rc, out = lint(tmp_path, "", [ASK, "Show the calls first."])
    assert "WARN" in out and "send-implicit" in out
    assert "disable-model-invocation: true" in out  # the fix is named
    assert rc == 0  # a WARN never fails the lint


def test_sender_with_key_is_clean(tmp_path: Path) -> None:
    rc, out = lint(tmp_path, "disable-model-invocation: true\n", [ASK])
    assert "send-implicit" not in out
    assert rc == 0


def test_key_set_false_still_warns(tmp_path: Path) -> None:
    _, out = lint(tmp_path, "disable-model-invocation: false\n", [ASK])
    assert "send-implicit" in out


def test_block_one_level_deeper_still_warns(tmp_path: Path) -> None:
    _, out = lint(tmp_path, "", ["### Ask before an outside effect"])
    assert "send-implicit" in out


def test_plain_sentence_is_not_the_block(tmp_path: Path) -> None:
    _, out = lint(tmp_path, "", ["Ask before an outside effect, always."])
    assert "send-implicit" not in out


def test_skill_without_the_block_is_clean(tmp_path: Path) -> None:
    _, out = lint(tmp_path, "", ["Plain skill, nothing leaves the machine."])
    assert "send-implicit" not in out


def test_heading_inside_a_fence_is_not_the_block(tmp_path: Path) -> None:
    _, out = lint(tmp_path, "", ["```markdown", ASK, "```"])
    assert "send-implicit" not in out


def test_repo_lint_runs_unchanged() -> None:
    for root in (REPO / ".claude", REPO / "skills"):
        run = subprocess.run(
            [sys.executable, str(LINT), str(root)], capture_output=True, text=True, check=False
        )
        assert "send-implicit" not in run.stdout
