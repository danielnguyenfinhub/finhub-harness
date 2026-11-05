"""The light harness skill: small, self-contained, packaged, and sharing its Run mode block with the full skill."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIGHT = ROOT / "skills/finhub-harness-light/SKILL.md"
FULL = ROOT / "skills/finhub-harness/SKILL.md"
TEMPLATE = ROOT / "skills/finhub-harness/references/orchestrator-template.md"
PACKAGER = ROOT / "scripts/package-plugin.sh"
LINT = ROOT / "skills/finhub-harness/scripts/lint_harness.py"

RUN_MODE_PHRASES = (
    "## Run mode",
    "`_workspace/mode.txt`",
    'model: "haiku"',
    "`[full-only]`",
    "keeps its gates in light mode",
)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    block = text.split("---", 2)[1]
    return {
        m.group(1): m.group(2).strip().strip('"')
        for m in re.finditer(r"(?m)^([\w-]+):\s*(.*)$", block)
    }


def test_light_skill_is_small() -> None:
    text = read(LIGHT)
    fm = frontmatter(text)
    assert fm["name"] == "finhub-harness-light" == LIGHT.parent.name
    assert len(fm["description"]) <= 800, "description sits in context every session"
    assert text.count("\n") <= 120, "SKILL.md line budget"
    assert len(text.encode()) < 0.25 * len(
        read(FULL).encode()
    ), "at most a quarter of the full skill"


def test_light_skill_is_self_contained() -> None:
    text = read(LIGHT)
    assert not re.search(r"\]\((?!https?:)[^)]+\)", text), "relative markdown link"
    assert "references/" not in text and "../" not in text, "reads no other file"
    assert not re.search("[\\uac00-\\ud7a3]", text), "Hangul"


def test_light_skill_keeps_the_owner_in_charge_of_gates() -> None:
    text = read(LIGHT)
    assert "you never decide a gate yourself; the owner does" in text.lower()
    assert "audited decision" in text and "keeps its gates in light mode" in text


def test_run_mode_block_is_shared_by_both_skills() -> None:
    for p in (LIGHT, TEMPLATE):
        t = read(p)
        for phrase in RUN_MODE_PHRASES:
            assert phrase in t, f"{p.name}: {phrase}"


def test_full_skill_points_to_light_and_has_the_run_mode_bullet() -> None:
    text = read(FULL)
    fm = frontmatter(text)
    assert "finhub-harness-light" in fm["description"], "trigger collision guard"
    assert "**Light option.**" in text
    assert "**Run mode**" in text and "`[full-only]`" in text


def test_packager_ships_the_light_skill_for_chat() -> None:
    sh = read(PACKAGER)
    assert sh.count("finhub-harness-light-skill.zip") >= 3, "built, checked and ship-scanned"
    assert "mkzip dist/finhub-harness-light-skill.zip skills finhub-harness-light" in sh


def test_lint_accepts_the_documented_cost_fields_on_agents() -> None:
    spec = importlib.util.spec_from_file_location("lint_light", LINT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert {"maxTurns", "effort", "disallowedTools"} <= mod.AGENT_KEYS
