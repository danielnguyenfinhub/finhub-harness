"""package_harness.py: a generated harness packed for Claude Code, Cowork and chat."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/finhub-harness/scripts/package_harness.py"
SKILL = (ROOT / "skills/finhub-harness/SKILL.md").read_text()


def harness(tmp: Path) -> Path:
    c = tmp / "proj/.claude"
    (c / "skills/doc-check/references").mkdir(parents=True)
    (c / "skills/doc-check/SKILL.md").write_text("---\nname: doc-check\ndescription: d\n---\nbody\n")
    (c / "skills/doc-check/references/r.md").write_text("ref\n")
    (c / "skills/doc-check/SKILL.md.bak").write_text("old\n")
    (c / "skills/doc-check/_workspace").mkdir()
    (c / "skills/doc-check/_workspace/x.md").write_text("scratch\n")
    (c / "agents").mkdir()
    (c / "agents/checker.md").write_text("---\nname: checker\ndescription: d\n---\n")
    outside = tmp / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("do not pack\n")
    (c / "skills/doc-check/link.md").symlink_to(outside / "secret.txt")
    (c / "skills/doc-check/linkdir").symlink_to(outside)
    return c


def run(*args: object, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        check=False,
    )


def test_builds_the_plugin_and_one_zip_per_skill(tmp_path: Path) -> None:
    out = tmp_path / "dist"
    r = run(harness(tmp_path), "--name", "doc-harness", "--out", out, home=tmp_path)
    assert r.returncode == 0, r.stderr
    with zipfile.ZipFile(out / "doc-harness.plugin") as z:
        assert sorted(z.namelist()) == [
            ".claude-plugin/plugin.json",
            "agents/checker.md",
            "skills/doc-check/SKILL.md",
            "skills/doc-check/references/r.md",
        ]
        assert json.loads(z.read(".claude-plugin/plugin.json"))["name"] == "doc-harness"
    with zipfile.ZipFile(out / "doc-check-skill.zip") as z:
        assert sorted(z.namelist()) == ["doc-check/SKILL.md", "doc-check/references/r.md"]
    assert sorted(p.name for p in out.iterdir()) == ["doc-check-skill.zip", "doc-harness.plugin"]
    assert "doc-harness:<agent>" in r.stdout
    assert not (tmp_path / ".claude").exists()  # no install unless asked


def test_a_bad_name_or_an_empty_harness_is_refused(tmp_path: Path) -> None:
    c = harness(tmp_path)
    d = tmp_path / "d"
    assert run(c, "--name", "Doc_Harness", "--out", d, home=tmp_path).returncode == 2
    assert run(tmp_path, "--name", "doc-harness", "--out", d, home=tmp_path).returncode == 2
    assert run(c, "--name", "x", "--description", "d" * 501, "--out", d, home=tmp_path).returncode == 2
    assert not d.exists()


def test_install_user_copies_once_and_never_overwrites(tmp_path: Path) -> None:
    c, home, out = harness(tmp_path), tmp_path / "home", tmp_path / "dist"
    assert run(c, "--name", "doc-harness", "--out", out, "--install-user", home=home).returncode == 0
    skill = home / ".claude/skills/doc-check"
    assert (skill / "references/r.md").read_text() == "ref\n"
    assert (home / ".claude/agents/checker.md").is_file()
    assert sorted(p.name for p in skill.iterdir()) == ["SKILL.md", "references"]
    (skill / "SKILL.md").write_text("my edit\n")
    (home / ".claude/agents/checker.md").unlink()
    r = run(c, "--name", "doc-harness", "--out", out, "--install-user", home=home)
    assert r.returncode == 4
    assert "nothing copied" in r.stderr
    assert (skill / "SKILL.md").read_text() == "my edit\n"
    assert not (home / ".claude/agents/checker.md").exists()  # all or nothing


def test_the_skill_offers_the_install_option() -> None:
    for phrase in (
        "**Install option**",
        "scripts/package_harness.py",
        "--install-user",
        "ask the owner once",
        "never overwrites",
        "Loading in Cowork and chat is unverified",
    ):
        assert phrase in SKILL, phrase
