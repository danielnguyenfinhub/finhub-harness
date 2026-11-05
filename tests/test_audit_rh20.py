"""Proof for the rule-versus-check audit guide (RH20, RH13, RH22).

adapted from references/repository_harness/.agents/skills/onboard-repository/SKILL.md:131 (MIT)
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GUIDE = REPO / "skills/finhub-harness/references/audit-guide.md"
SKILL = REPO / "skills/finhub-harness/SKILL.md"


def guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


def test_five_finding_classes() -> None:
    g = guide()
    for word in (
        "Enforced",
        "Partially enforced",
        "Unenforced rule",
        "Check lacking authority",
        "Unknown",
    ):
        assert f"**{word}**" in g, word


def test_five_evidence_classes_never_promoted() -> None:
    g = guide()
    for word in ("Authoritative", "Observed", "Derived", "Decision required"):
        assert f"**{word}**" in g, word
    assert "never promote" in g.lower()


def test_four_enforcement_levels_are_kept_apart() -> None:
    g = guide().lower()
    for level in ("local command", "optional hook", "ci invocation", "branch protection"):
        assert level in g, level
    assert "do not infer one from another" in g


def test_audit_is_read_only() -> None:
    g = guide().lower()
    assert "reads and reports" in g
    assert "does not edit" in g


def test_failure_message_names_four_things() -> None:
    g = guide().lower()
    assert "the violating item" in g and "the authority source" in g
    assert "a compliant next action" in g


def test_skill_step_7_points_at_the_guide() -> None:
    s = SKILL.read_text(encoding="utf-8")
    step7 = s[s.index("### Step 7") :]
    assert "references/audit-guide.md" in step7


def test_no_shell_surfaces_say_by_hand() -> None:
    g = guide().lower()
    assert "claude chat and cowork" in g and "by hand" in g and "unverified" in g


def test_attribution_lines() -> None:
    g = guide()
    assert "references/repository_harness/.agents/skills/onboard-repository/SKILL.md:131" in g
    assert "references/repository_harness/docs/patterns/encoding-invariants.md:75" in g
    assert "(MIT)" in g
