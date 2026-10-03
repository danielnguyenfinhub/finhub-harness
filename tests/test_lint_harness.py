"""Proof for skills/finhub-harness/scripts/lint_harness.py (C2)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
FIX = REPO / "tests/fixtures"
N65 = "-".join(["abcdefghij"] * 6)  # 65 chars


def lint(target: Path) -> tuple[int, str]:
    run = subprocess.run(
        [sys.executable, str(LINT), str(target)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run.returncode, run.stdout + run.stderr


def test_bad_fixture_names_every_seeded_defect() -> None:
    code, out = lint(FIX / "harness_bad")
    assert code == 1 and "Traceback" not in out
    expected = [
        ("skills/wrong-dir/SKILL.md", "dir-name"),
        (f"skills/{N65}/SKILL.md", "name"),
        ("skills/empty-desc/SKILL.md", "description"),
        ("agents/caller.md", "subagent-ref"),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact"),
        ("skills/no-frontmatter/SKILL.md", "frontmatter"),
        ("agents/badconn.md", "connector"),
        ("harness_bad", "preflight agent 'fetcher' needs 'crm'"),
        ("harness_bad", "preflight row fetcher-two | erp"),
        ("skills/Bad_Name/SKILL.md", "name 'Bad_Name'"),
        ("skills/no-close/SKILL.md", "frontmatter missing"),
        ("skills/bad-line/SKILL.md", "frontmatter unparseable line"),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact line 12: team_name:"),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact line 13: TeamDelete("),
        ("skills/bad-orchestrator/SKILL.md", "v1-artefact line 14: CLAUDE_CODE_EXPERIMENTAL"),
        ("references/nested/SKILL.md", "v1-artefact line 2: TeamCreate("),
        ("skills/no-name/SKILL.md", "name frontmatter name is missing"),
        ("skills/bare-name/SKILL.md", "name frontmatter name is missing"),
        ("skills/no-desc/SKILL.md", "description frontmatter description is missing"),
        ("skills/heading-first/SKILL.md", "frontmatter missing"),
        ("agents/typer.md", "subagent-ref line 7: no agent file for 'ghost-two'"),
        ("skills/bad-bytes/SKILL.md", "encoding not valid UTF-8"),
        ("references/deep/more/SKILL.md", "encoding not valid UTF-8"),
        ("references/deep/more/SKILL.md", "v1-artefact line 2: TeamDelete("),
    ]
    errors = [line for line in out.splitlines() if line.startswith("ERROR")]
    for where, rule in expected:
        assert any(where + ": " + rule in line for line in errors), (where, rule, out)
    assert len(errors) == len(expected), out
    warnings = [line for line in out.splitlines() if line.startswith("WARN")]
    for where, rule in [
        ("skills/bad-orchestrator/SKILL.md", "unknown-key frontmatter key 'owner'"),
        ("agents/nomodel.md", "model no model: field"),
        ("agents/nocomment.md", "model model: has no '# reason' comment"),
        ("skills/long-desc/SKILL.md", "description 1025 chars"),
    ]:
        assert any(where + ": " + rule in line for line in warnings), (where, rule, out)
    assert len(warnings) == 4, out


def test_clean_fixture_passes_without_warnings() -> None:
    code, out = lint(FIX / "harness_good")
    assert code == 0, out
    assert out.strip().endswith("0 error(s), 0 warning(s)"), out


def test_this_repo_team_and_plugin_pass() -> None:
    for target in (REPO / ".claude", REPO):
        code, out = lint(target)
        assert code == 0, out


def test_nothing_to_lint_is_an_error(tmp_path: Path) -> None:
    assert lint(tmp_path)[0] == 1
    assert lint(tmp_path / "missing")[0] == 2
