"""Structural proof for packs/finhub-ops-pack: the manifest is installable, every skill and agent
is well formed, attribution is present and no Hangul or dropped-word artefact remains."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PACK = Path(__file__).resolve().parents[1] / "packs/finhub-ops-pack"
SKILLS = sorted(p for p in (PACK / "skills").iterdir() if p.is_dir())
AGENTS = sorted((PACK / "agents").glob("*.md"))
HANGUL = re.compile("[가-힯ᄀ-ᇿ㄰-㆏]")
DROPPED_WORD = re.compile(r"[a-z]  [a-z]")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"frontmatter missing: {path.name}"
    head = text.split("\n---\n", 1)[0].splitlines()[1:]
    return {k: v.strip() for k, _, v in (line.partition(":") for line in head)}


def test_manifest_installable() -> None:
    m = json.loads((PACK / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert m["name"] == "finhub-ops-pack", "manifest name"
    assert 1 <= len(m["description"]) <= 500, "manifest description over the 500 char limit"
    assert m["license"] == "Apache-2.0", "manifest licence"


def test_expected_inventory() -> None:
    assert len(SKILLS) == 5, f"skills: {[p.name for p in SKILLS]}"
    assert len(AGENTS) == 4, f"agents: {[p.name for p in AGENTS]}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_well_formed(skill: Path) -> None:
    names = [p.name for p in skill.iterdir()]
    assert names == ["SKILL.md"], f"{skill.name}: expected only SKILL.md, got {names}"
    fm = _frontmatter(skill / "SKILL.md")
    assert fm["name"] == skill.name, f"{skill.name}: frontmatter name {fm['name']}"
    assert len(fm["description"]) > 40, f"{skill.name}: description too short"


@pytest.mark.parametrize("agent", AGENTS, ids=lambda p: p.stem)
def test_agent_scoped(agent: Path) -> None:
    fm = _frontmatter(agent)
    assert fm["name"] == agent.stem, f"{agent.stem}: frontmatter name {fm['name']}"
    assert fm["model"] == "sonnet", f"{agent.stem}: model not set"
    assert fm["tools"] == "Read, Write, Grep, Glob", f"{agent.stem}: tools not least-privilege"


def test_attribution_present() -> None:
    notice = (PACK / "NOTICE").read_text(encoding="utf-8")
    assert "Apache License, Version 2.0" in notice, "NOTICE lacks the licence"
    assert "8e8d35c" in notice, "NOTICE lacks the source commit"


def test_chatbot_agents_draft_only() -> None:
    for name in ("conversation-designer", "dialog-tester"):
        text = (PACK / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert "approv" in text.lower(), f"{name}: client-facing approval rule missing"


@pytest.mark.parametrize("path", [*AGENTS, *(s / "SKILL.md" for s in SKILLS)], ids=lambda p: p.stem)
def test_text_clean(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert not HANGUL.search(text), f"{path.name}: Hangul present"
    bad = [ln for ln in text.splitlines() if DROPPED_WORD.search(ln)]
    assert not bad, f"{path.name}: dropped-word artefact in {len(bad)} line(s), e.g. {bad[0][:60]}"
