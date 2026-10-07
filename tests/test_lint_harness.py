"""Proof for skills/finhub-harness/scripts/lint_harness.py (C2, C6, C17)."""

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


# --- C17: local links, bundled references/ files, duplicate names -----------------------------
OK_LINKS = FIX / "harness_links_ok"
BAD_LINKS = FIX / "harness_links_bad"


def test_links_ok_fixture_has_no_false_errors() -> None:
    code, out = lint(OK_LINKS)  # anchors, URLs, fences, inline code, ancestors, placeholders
    assert code == 0, out
    assert out.strip().endswith("0 error(s), 0 warning(s)"), out


def test_links_bad_fixture_names_every_seeded_defect() -> None:
    code, out = lint(BAD_LINKS)
    assert code == 1 and "Traceback" not in out, out
    broken = "skills/broken/SKILL.md: "
    expected = [
        "duplicate-name skill 'dup-one' in skills/dup-one/SKILL.md, skills/dup-two/SKILL.md",
        "duplicate-name agent 'twin' in agents/twin-a.md, agents/twin-b.md",
        broken + "broken-link line 8: 'missing.md' does not exist",
        broken + "broken-link line 8: 'assets/none.png' does not exist",
        broken + "broken-link line 9: 'gone/page.md#top' does not exist",
        broken + "broken-link line 12: 'gone-def.md' does not exist",
        broken + "broken-link line 19: 'after-fence.md' does not exist",
        broken + "broken-link line 20: '<missing angle.md>' does not exist",
        broken + "broken-link line 21: 'gone(1' does not exist",  # r2 form: cut at the first ')'
        broken + "broken-link line 22: 'gone((2' does not exist",  # D2: depth 2 is cut, not skipped
        broken + "broken-link line 23: 'gone-t1.md' does not exist",
        broken + "broken-link line 23: 'gone-t2.md' does not exist",
        broken + "broken-link line 23: 'gone-t3.md' does not exist",
        broken + "broken-link line 24: 'gone-p1.md' does not exist",
        broken + "broken-link line 24: 'gone-p2.md' does not exist",
        broken + "broken-link line 25: 'gone-t300.md' does not exist",  # 300-char link text
        broken + "broken-link line 26: 'gone-d3.md' does not exist",  # definition, 3-space indent
        broken + "broken-link line 27: 'gone-d4.md' does not exist",  # definition with a title
        broken + "broken-link line 28: 'gone-d300.md' does not exist",  # 300-char definition label
        broken + "broken-link line 29: '`gone-bt.md`' does not exist",  # definition keeps its span
        broken + "bundled-ref line 30: references/a-b.md does not exist",
        broken + "broken-link line 31: 'gone-nospace.md' does not exist",  # no space after ]:
        broken + "broken-link line 33: 'gone-dbl.md' does not exist",  # (line 32 stays silent)
        broken + "broken-link line 37: 'gone-tab.md' does not exist",  # fence closed by a tab
        broken + "bundled-ref line 38: references/ghost3.mp3 does not exist",
        "skills/broken/nested/SKILL.md: broken-link line 3: 'gone-nested.md' does not exist",
        "agents/twin-b.md: broken-link line 7: 'gone-agent.md' does not exist",
        broken + "bundled-ref line 14: references/ghost.md does not exist",
        broken + "bundled-ref line 14: references/ghost2.md does not exist",
        "skills/dup-two/SKILL.md: dir-name",
    ]
    errors = [line for line in out.splitlines() if line.startswith("ERROR")]
    for want in expected:
        assert any(want in line for line in errors), (want, out)
    assert len(errors) == len(expected), out
    assert "hidden" not in out, out  # the fenced lines stay silent


def test_bundled_reference_resolves_in_the_skill_dir_or_an_ancestor_up_to_the_root_parent(
    tmp_path: Path,
) -> None:
    (tmp_path / "references").mkdir()
    (tmp_path / "references/shared.md").write_text("x", encoding="utf-8")
    skill = tmp_path / "proj/skills/s/SKILL.md"
    skill.parent.mkdir(parents=True)
    head = '---\nname: s\ndescription: "S. Use to re-run."\n---\n'
    skill.write_text(head + "see references/shared.md and references/nope.md\n", encoding="utf-8")
    out = lint(tmp_path / "proj")[1]  # root.parent is tmp_path, where shared.md lives
    assert "references/nope.md does not exist" in out and "shared.md" not in out, out
    (tmp_path / "proj/skills/s/references").mkdir()
    (tmp_path / "proj/skills/s/references/nope.md").write_text("x", encoding="utf-8")
    assert lint(tmp_path / "proj")[0] == 0  # now found in the skill's own references/


def test_unclosed_angle_starts_are_linear(tmp_path: Path) -> None:
    """D3: 60,000 chars of `[a](<` took seconds when each start scanned on for a closing `>`."""
    skill = tmp_path / "skills/s/SKILL.md"
    skill.parent.mkdir(parents=True)
    head = '---\nname: s\ndescription: "S. Use to re-run."\n---\n'
    skill.write_text(head + "[a](<" * 12000 + "\n", encoding="utf-8")
    start = time.monotonic()
    code, out = lint(tmp_path)
    assert code in (0, 1) and "Traceback" not in out, out[-300:]
    assert time.monotonic() - start < 1.0


def test_bundled_walk_stops_at_the_root_parent(tmp_path: Path) -> None:
    """A references/ file two levels above the lint root is not found (the walk ends at root.parent)."""
    (tmp_path / "references").mkdir()
    (tmp_path / "references/far.md").write_text("x", encoding="utf-8")
    skill = tmp_path / "up/root/skills/s/SKILL.md"
    skill.parent.mkdir(parents=True)
    head = '---\nname: s\ndescription: "S. Use to re-run."\n---\n'
    skill.write_text(head + "see references/far.md\n", encoding="utf-8")
    assert "bundled-ref" in lint(tmp_path / "up/root")[1]
    old = "stop = root.resolve().parent"
    assert "bundled-ref" not in _run_mutant(tmp_path, old, old + ".parent", tmp_path / "up/root")


def _symlinked_skill(tmp_path: Path, real: str, body: str) -> Path:
    """proj/skills/s is a symlink to a dir outside the lint root; returns the lint root."""
    target = tmp_path / real
    target.mkdir(parents=True)
    head = '---\nname: s\ndescription: "S. Use to re-run."\n---\n'
    (target / "SKILL.md").write_text(head + body, encoding="utf-8")
    root = tmp_path / "a/b/proj"
    (root / "skills").mkdir(parents=True)
    (root / "skills/s").symlink_to(target, target_is_directory=True)
    return root


def test_symlinked_skill_dir_outside_the_root_is_reported_and_terminates(tmp_path: Path) -> None:
    """The walk from a real dir outside root.parent must end at the filesystem root, not loop."""
    root = _symlinked_skill(tmp_path, "out/s", "see references/ghost.md\n")
    run = subprocess.run(
        [sys.executable, str(LINT), str(root)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert run.returncode == 1 and "references/ghost.md does not exist" in run.stdout, run.stdout


def test_bundled_walk_starts_from_the_resolved_skill_dir(tmp_path: Path) -> None:
    """references/ above the symlink's real dir counts; above the link's own path it would not."""
    (tmp_path / "real").mkdir()
    (tmp_path / "real/references").mkdir()
    (tmp_path / "real/references/shared.md").write_text("x", encoding="utf-8")
    root = _symlinked_skill(tmp_path, "real/s", "see references/shared.md\n")
    code, out = lint(root)
    assert code == 0 and "bundled-ref" not in out, out


def test_this_repo_links_and_bundled_refs_are_clean() -> None:
    for target in (REPO / ".claude", REPO):
        out = lint(target)[1]
        for rule in ("broken-link", "bundled-ref", "duplicate-name"):
            assert rule not in out, out


# (what the rule does, text in lint_harness.py, replacement, fixture, output text that flips)
MUTANTS: list[tuple[str, str, str, Path | str | None, str]] = [
    (
        "link existence",
        "            if missing:\n",
        "            if False:\n",
        BAD_LINKS,
        "broken-link",
    ),
    (
        "bundled existence",
        "                if found:\n                    break\n",
        "                if True:\n                    break\n",
        BAD_LINKS,
        "bundled-ref",
    ),
    (
        "duplicate names",
        "        if len(paths) > 1:\n",
        "        if len(paths) > 99:\n",
        BAD_LINKS,
        "duplicate-name",
    ),
    (
        "fence skip",
        "            fence = m.group(1)\n",
        '            fence = ""\n',
        OK_LINKS,
        "broken-link",
    ),
    (
        "non-local skip",
        "if not clean or NONLOCAL_RE.match(clean):",
        "if not clean:",
        OK_LINKS,
        "broken-link",
    ),
    (
        "inline-code strip",
        'LINK_RE.findall(CODE_RE.sub("", line))',
        "LINK_RE.findall(line)",
        OK_LINKS,
        "broken-link",
    ),
    ("multi-segment skip", r"(?![\w/-])", r"(?![\w-])", OK_LINKS, "bundled-ref"),
    ("ancestor stop", "stop = root.resolve().parent", "stop = root.resolve()", None, "bundled-ref"),
    (
        "skills-only bundled",
        "        if path in skills:\n",
        "        if True:\n",
        OK_LINKS,
        "bundled-ref",
    ),
    (
        "unquote",
        'clean = unquote(target.strip("<>").split("#", 1)[0].split("?", 1)[0])',
        'clean = target.strip("<>").split("#", 1)[0].split("?", 1)[0]',
        OK_LINKS,
        "broken-link",
    ),
    (
        "fence closer character",
        "                and m.group(1)[0] == fence[0]\n",
        "",
        OK_LINKS,
        "broken-link",
    ),
    (
        "bundled skips inline code",
        "for ref in BUNDLED_RE.findall(line):",
        'for ref in BUNDLED_RE.findall(CODE_RE.sub("", line)):',
        BAD_LINKS,
        "references/ghost.md does not exist",
    ),
    (
        "definition loose",
        r"(<[^>\n]+>|(?=\S*(?:/|\.\w))[^\s<]\S*)\s*(?:[\"'(].*)?$",
        r"(<[^>\n]+>|\S+)",
        OK_LINKS,
        "broken-link",
    ),
    ("definition footnote", r"\[(?!\^)", r"\[", OK_LINKS, "broken-link"),
    ("definition end of line", r"\s*(?:[\"'(].*)?$", "", OK_LINKS, "broken-link"),
    ("definition path guard", r"(?=\S*(?:/|\.\w))", "", OK_LINKS, "broken-link"),
    ("bundled OSError guard", "except OSError:", "except KeyError:", "long", "Traceback"),
    (
        "link OSError guard",
        "except (OSError, ValueError):",
        "except KeyError:",
        OK_LINKS,
        "Traceback",
    ),
    (
        "closer info string",
        '                and not line.strip(" \\t`~")\n',
        "",
        OK_LINKS,
        "broken-link",
    ),
    ("angle target", r"(<[^>\n]+>|[^)\s]+)", r"([^)\s]+)", BAD_LINKS, "missing angle.md"),
    ("lookbehind hyphen", r"(?<![\w./-])", r"(?<![\w./])", OK_LINKS, "bundled-ref"),
    ("lookbehind word", r"(?<![\w./-])", r"(?<![./-])", OK_LINKS, "bundled-ref"),
    ("lookbehind dot", r"(?<![\w./-])", r"(?<![\w/-])", OK_LINKS, "bundled-ref"),
    ("lookahead hyphen", r"(?![\w/-])", r"(?![\w/])", OK_LINKS, "bundled-ref"),
    (
        "name start dot",
        r"references/([A-Za-z0-9_][",
        r"references/([A-Za-z0-9_.][",
        OK_LINKS,
        "bundled-ref",
    ),
    ("name hyphen", r"[A-Za-z0-9_.-]*\.", r"[A-Za-z0-9_.]*\.", BAD_LINKS, "references/a-b.md"),
    ("definition indent", r"^ {0,3}\[(?!", r"^\s*\[(?!", OK_LINKS, "broken-link"),
    ("definition indent 3", r"^ {0,3}\[(?!", r"^ {0,2}\[(?!", BAD_LINKS, "gone-d3.md"),
    ("definition title", r"(?:[\"'(].*)?$", "$", BAD_LINKS, "gone-d4.md"),
    ("definition label", r"{1,300}", r"{1,299}", BAD_LINKS, "gone-d300.md"),
    ("link text 299", r"{0,300}\]\(", r"{0,299}\]\(", BAD_LINKS, "gone-t300.md"),
    ("link text 301", r"{0,300}\]\(", r"{0,301}\]\(", OK_LINKS, "broken-link"),
    ("link text unbounded", r"{0,300}\]\(", r"*\]\(", OK_LINKS, "broken-link"),
    (
        "definition on stripped line",
        "(m := DEF_RE.match(line))",
        '(m := DEF_RE.match(CODE_RE.sub("", line)))',
        BAD_LINKS,
        "gone-bt.md",
    ),
    (
        "links also on definition lines",
        '[m.group(1)] if (m := DEF_RE.match(line)) else LINK_RE.findall(CODE_RE.sub("", line))',
        '([m.group(1)] if (m := DEF_RE.match(line)) else []) + LINK_RE.findall(CODE_RE.sub("", line))',
        OK_LINKS,
        "broken-link",
    ),
    (
        "links in agents",
        "        check_links(path, text)\n        if path in skills:\n",
        "        if path in skills:\n            check_links(path, text)\n",
        BAD_LINKS,
        "gone-agent.md",
    ),
    (
        "links in nested skills",
        "        check_links(path, text)\n",
        "        if path in skills or path in agents:\n            check_links(path, text)\n",
        BAD_LINKS,
        "gone-nested.md",
    ),
]


def _long_tree(root: Path) -> Path:
    """A skill with a references/ dir that mentions a real file, a 256- and a 5,000-char file name."""
    skill = root / "skills/s/SKILL.md"
    (skill.parent / "references").mkdir(parents=True, exist_ok=True)
    (skill.parent / "references/real.md").write_text("x", encoding="utf-8")
    head = '---\nname: s\ndescription: "S. Use to re-run."\n---\n'
    body = f"see references/real.md, references/{'a' * 256}.md and references/{'b' * 5000}.md\n"
    skill.write_text(head + body, encoding="utf-8")
    return root


def _run_mutant(tmp_path: Path, old: str, new: str, target: Path) -> str:
    text = LINT.read_text(encoding="utf-8")
    assert text.count(old) == 1, old  # a refactor that moves the rule must update this table
    mutant = tmp_path / "lint_mutant.py"
    mutant.write_text(text.replace(old, new), encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(mutant), str(target)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run.stdout + run.stderr


def test_deleting_any_c17_rule_is_caught_by_a_fixture(tmp_path: Path) -> None:
    for what, old, new, fixture, rule in MUTANTS:
        if fixture is None:  # the ancestor search needs a tree where the file sits above the root
            (tmp_path / "references").mkdir(exist_ok=True)
            (tmp_path / "references/shared.md").write_text("x", encoding="utf-8")
            skill = tmp_path / "proj/skills/s/SKILL.md"
            skill.parent.mkdir(parents=True, exist_ok=True)
            head = '---\nname: s\ndescription: "S. Use to re-run."\n---\n'
            skill.write_text(head + "see references/shared.md\n", encoding="utf-8")
            target = tmp_path / "proj"
        elif fixture == "long":  # names no file system can hold
            target = _long_tree(tmp_path / "long")
        else:
            assert isinstance(fixture, Path)
            target = fixture
        assert (rule in lint(target)[1]) == (fixture is BAD_LINKS), what  # the real rule behaves
        got = _run_mutant(tmp_path, old, new, target)
        assert (rule in got) != (fixture is BAD_LINKS), (what, got)  # the mutant flips the verdict


def test_overlong_bundled_token_is_reported_missing_not_a_crash(tmp_path: Path) -> None:
    code, out = lint(_long_tree(tmp_path))
    assert code == 1 and "Traceback" not in out, out[-300:]
    errors = [line for line in out.splitlines() if line.startswith("ERROR")]
    assert len(errors) == 2, out  # real.md is found; the two impossible names are missing
    assert all("bundled-ref" in line and "does not exist" in line for line in errors), out
