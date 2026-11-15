"""Specialist workers (ideas from OpenWorker): rules SW1 to SW10 and their pointers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills" / "finhub-harness"
PATTERNS = (ROOT / "references" / "team-patterns.md").read_text()
SKILL = (ROOT / "SKILL.md").read_text()
SECTION = PATTERNS.split("### 1-3a.")[1].split("### 1-4.")[0]


def test_all_ten_rules_are_present() -> None:
    for n in range(1, 11):
        assert f"| SW{n} |" in SECTION, n


def test_generalist_first() -> None:
    assert "Start with one general agent" in SECTION
    assert '"more thorough" is not one' in SECTION


def test_undeclared_means_absent() -> None:
    assert "does not declare is one the specialist does not have" in SECTION


def test_worker_never_asks_the_user_or_accepts_its_own_work() -> None:
    assert "it never asks the user anything" in SECTION
    assert "never accepts its own work" in SECTION


def test_no_silent_skip_and_fix_rechecked() -> None:
    assert "reported `NOT RUN` with the reason" in SECTION
    assert "reruns the check that found the problem" in SECTION


def test_recommendation_is_not_permission() -> None:
    assert "never counts as the owner's yes" in SECTION


def test_borrowed_specialist_is_read_first() -> None:
    assert "read before it joins a team" in SECTION


def test_attribution_names_source_licence_and_holder() -> None:
    assert "references/openworker/README.md:63" in SECTION
    assert "(MIT), holder Andrew Ng" in SECTION
    assert "ideas only, fresh text" in SECTION


def test_skill_points_to_the_rules() -> None:
    assert "§1-3a, rules SW1 to SW10" in SKILL
    assert "- Specialists: a specialist's file holds" in SKILL
    assert "no worker marks its own item done" in SKILL
