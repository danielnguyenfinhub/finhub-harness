"""Proof for skills/finhub-harness/scripts/lint_harness.py (C2)."""

import subprocess
import sys
import time
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


DELEG = FIX / "harness_delegation"


def test_lazy_delegation_is_flagged_in_spawning_files_only() -> None:
    code, out = lint(DELEG)
    assert code == 0 and "Traceback" not in out, out  # a WARN, never an ERROR
    lazy = "skills/lazy-orchestrator/SKILL.md"
    hits = [
        (lazy, 7, "Based on your findings"),
        (lazy, 8, "AS WE DISCUSSED"),
        (lazy, 9, "based on the research"),  # wrapped over lines 9-10
        (lazy, 11, "as discussed"),
        (lazy, 12, "based on the findings"),  # tab and no-break space between the words
        (lazy, 13, "based on the research"),
        (lazy, 13, "as discussed"),  # two hits on one line
        (lazy, 14, "based on your research"),
        (lazy, 15, "as we discussed"),  # tab, then a line break, between the words
        ("agents/delegator.md", 7, "based on your findings"),
        ("skills/lazy-orchestrator/references/deep/SKILL.md", 2, "based on your findings"),
        ("skills/wf-orchestrator/SKILL.md", 6, "Based on your findings"),  # agent( only
        ("skills/task-orchestrator/SKILL.md", 6, "As discussed"),  # Task( only
        ("skills/named-orchestrator/SKILL.md", 6, "based on the research"),  # Agent( only
        ("skills/msg-orchestrator/SKILL.md", 6, "based on your findings"),  # SendMessage only
    ]
    warns = [line for line in out.splitlines() if line.startswith("WARN")]
    for where, n, phrase in hits:
        want = f"{where}: lazy-delegation line {n}: {phrase!r}"
        assert any(want in line for line in warns), (want, out)
    assert len(warns) == len(hits), out  # clean-orchestrator, no-spawn and worker.md stay silent
    assert out.strip().endswith("0 error(s), 15 warning(s)"), out


def test_lazy_delegation_regex_is_linear(tmp_path: Path) -> None:
    skill = tmp_path / "skills/stress/SKILL.md"
    skill.parent.mkdir(parents=True)
    head = (
        '---\nname: stress\ndescription: "Stress. Use to re-run."\n---\n'
        'subagent_type: "worker"\n'
    )
    parts = [
        "based on" + " " * 300_000 + "x\n",
        "as" + "\n" * 300_000 + "x\n",
        "as\u00a0we" + "\u00a0" * 300_000 + "x\n",
        "based on the " * 50_000 + "x\n",
        "as we " * 50_000 + "x\n",
        "based on your findin " * 50_000 + "\n",
    ]
    skill.write_text(head + "".join(parts), encoding="utf-8")
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "worker.md").write_text(
        '---\nname: worker\ndescription: "W. Not for planning."\nmodel: sonnet  # cheap\n---\n',
        encoding="utf-8",
    )
    t0 = time.monotonic()
    code, out = lint(tmp_path)
    assert code == 0 and "lazy-delegation" not in out, out[-300:]
    assert time.monotonic() - t0 < 20


def test_lazy_delegation_line_numbers_are_linear(tmp_path: Path) -> None:
    skill = tmp_path / "skills/big/SKILL.md"
    skill.parent.mkdir(parents=True)
    head = '---\nname: big\ndescription: "Big. Use to re-run."\n---\n' 'subagent_type: "x"\n'
    skill.write_text(head + "based on the research\n" * 100_000, encoding="utf-8")
    t0 = time.monotonic()
    code, out = lint(tmp_path)
    assert code == 1 and time.monotonic() - t0 < 20, out  # error: no agent file for 'x'
    assert "line 100005: 'based on the research'" in out, out[-300:]


def test_this_repo_has_no_lazy_delegation() -> None:
    for target in (REPO / ".claude", REPO):
        assert "lazy-delegation" not in lint(target)[1]


def test_lazy_delegation_in_a_dot_claude_project_with_a_late_gate_and_odd_whitespace(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".claude"  # the real target is project/.claude
    (root / "skills/big").mkdir(parents=True)
    (root / "agents").mkdir()
    (root / "agents/w.md").write_text(
        '---\nname: w\ndescription: "W. Not for planning."\nmodel: sonnet  # cheap\n---\n',
        encoding="utf-8",
    )
    body = (
        '---\nname: big\ndescription: "Big. Use to re-run."\n---\n'
        + "filler line\n" * 400  # the first spawn token sits past character 2,000
        + 'subagent_type: "w"\n'
        + "based on the\r\nresearch\n"
        + "as\u2003discussed\n"
        + "as\x0bwe discussed\n"
    )
    (root / "skills/big/SKILL.md").write_bytes(body.encode("utf-8"))  # keeps the CR LF
    code, out = lint(root)
    assert code == 0, out
    for n, phrase in [
        (406, "based on the research"),
        (408, "as discussed"),
        (409, "as we discussed"),
    ]:
        assert f"big/SKILL.md: lazy-delegation line {n}: {phrase!r}" in out, out
    assert out.count("lazy-delegation") == 3, out


WORKER = '---\nname: w\ndescription: "W. Not for planning."\nmodel: sonnet  # cheap\n---\n'


def _orch(root: Path, name: str, tail: str) -> None:
    (root / "agents").mkdir(exist_ok=True)
    (root / "agents/w.md").write_text(WORKER, encoding="utf-8")
    d = root / "skills" / name
    d.mkdir(parents=True)
    head = f'---\nname: {name}\ndescription: "{name}. Use to re-run."\n---\nsubagent_type: "w"\n'
    (d / "SKILL.md").write_text(head + tail, encoding="utf-8")


def test_lazy_delegation_found_in_the_twelfth_spawning_file(tmp_path: Path) -> None:
    for i in range(12):
        _orch(tmp_path, f"s{i:02d}", "based on your findings\n" if i == 11 else "")
    out = lint(tmp_path)[1]
    assert "s11/SKILL.md: lazy-delegation line 6" in out, out


def test_lazy_delegation_found_at_the_end_of_a_six_megabyte_file(tmp_path: Path) -> None:
    _orch(tmp_path, "big", "x" * 6_000_000 + " based on the research\n")
    out = lint(tmp_path)[1]
    assert "big/SKILL.md: lazy-delegation" in out, out


def test_lazy_delegation_matches_mixed_case(tmp_path: Path) -> None:
    _orch(tmp_path, "mix", "go as Discussed\nbased on the Research\n")
    out = lint(tmp_path)[1]
    assert out.count("lazy-delegation") == 2, out
