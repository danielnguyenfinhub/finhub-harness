"""Manager-led team (ideas from hive): rules MT1 to MT8 and their pointers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills" / "finhub-harness"
PATTERNS = (ROOT / "references" / "team-patterns.md").read_text()
SKILL = (ROOT / "SKILL.md").read_text()
SECTION = PATTERNS.split("### 1-5a.")[1].split("### 1-6.")[0]


def test_all_eight_rules_are_present() -> None:
    for n in range(1, 9):
        assert f"| MT{n} |" in SECTION, n


def test_one_manager_talks_to_the_owner() -> None:
    assert "It is the only one who talks to the owner" in SECTION


def test_manager_starts_alone_and_proposes_the_team() -> None:
    assert "it proposes the team to the owner, with the reason, before staffing it" in SECTION


def test_existing_team_is_used_before_a_new_one() -> None:
    assert "assigned to that team through its own orchestrator skill" in SECTION
    assert "does not edit that team's files" in SECTION
    assert "built only for a job nothing covers" in SECTION


def test_one_shared_board_and_claim_before_start() -> None:
    assert "it does not rebuild it" in SECTION
    assert "claims a task before it starts" in SECTION


def test_workers_report_up_and_manager_never_guesses() -> None:
    assert "never fills a gap with a guess" in SECTION


def test_shared_records_wait_for_the_owner() -> None:
    assert "after the Ask-first yes" in SECTION


def test_attribution_names_source_licence_and_holder() -> None:
    assert "references/hive/core/framework/agents/queen/nodes/__init__.py:35-49" in SECTION
    assert "(Apache-2.0), holder Aden" in SECTION
    assert "MT3's use of an existing team is this skill's own rule" in SECTION


def test_skill_points_to_the_pattern() -> None:
    assert "§1-5a, rules MT1 to MT8" in SKILL
    assert "A team harness names one manager" in SKILL
