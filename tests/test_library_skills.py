"""The harness builders tell the builder to assign existing library skills to each agent."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills"
FULL = (ROOT / "finhub-harness" / "SKILL.md").read_text()
LIGHT = (ROOT / "finhub-harness-light" / "SKILL.md").read_text()


def test_full_skill_assigns_library_skills_per_agent():
    for phrase in (
        "Library skills:",
        "at most three",
        "`Skill` to its `tools:`",
        "never one from memory",
        "`none found`",
        "not the sending worker",
    ):
        assert phrase in FULL, phrase


def test_full_checklist_checks_the_assignment_table():
    assert "agent | skill | why table" in FULL


def test_light_skill_reuses_before_writing():
    assert "**Reuse.** Assign a listed skill" in LIGHT and "`Skill` to its `tools:`" in LIGHT
    assert LIGHT.index("**Reuse.** Assign a listed skill") > LIGHT.index("**Choose the shape.**")
