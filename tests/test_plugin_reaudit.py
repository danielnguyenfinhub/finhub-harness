"""Re-audit of the plugin content: prose pins for the light skill, Step 3, README and unit-tracker.md."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIGHT = (REPO / "skills/finhub-harness-light/SKILL.md").read_text(encoding="utf-8")
STEP = (REPO / "skills/finhub-harness/SKILL.md").read_text(encoding="utf-8")
DOC = (REPO / "skills/finhub-harness/references/unit-tracker.md").read_text(encoding="utf-8")
README = (REPO / "README.md").read_text(encoding="utf-8")


def test_light_skill_outside_effects_is_unambiguous() -> None:
    assert "ask the owner once: use the full skill `finhub-harness`, or build it here?" in LIGHT
    assert "If the owner says build here, write this rule" in LIGHT
    assert "or build it only with this rule" not in LIGHT


def test_light_skill_tells_the_sender_to_say_approved_list() -> None:
    assert "its file says it works from the approved list" in LIGHT
    assert "with no `tools:` line it inherits them" in LIGHT


def test_light_skill_stays_self_contained_and_within_cap() -> None:
    assert len(LIGHT.encode("utf-8")) <= 8000
    assert "references/" not in LIGHT


def test_step3_qa_line_agrees_with_the_scoping_rule() -> None:
    assert "QA agents get a type with all tools (" not in STEP
    assert "all tools except `mcp__` connector tools unless the agent is the sender" in STEP


def test_readme_says_which_guards_are_wired() -> None:
    assert "register only `EchoTool`" in README
    assert "The command guard, workspace fence and checkpoints are wired" in README
    assert "`--mode read-only|workspace-write|full-access`" in README
    assert "Docker engine and MCP client are libraries that no shipped" in README


def test_unit_tracker_doc_says_a_dead_unit_is_not_claimable_or_writable() -> None:
    claim = next(r for r in DOC.splitlines() if r.startswith("| `claim DB"))
    dead = next(r for r in DOC.splitlines() if r.startswith("| `deadletter DB"))
    assert "never claimable" in claim and "CLAIM: dead-lettered" in claim
    assert "not claimable and not writable" in dead and "UPSERT: dead-lettered" in dead
    u10 = next(r for r in DOC.splitlines() if r.startswith("| U10"))
    assert "not writable either" in u10 and "the only way back is a new key" in u10
    c5 = next(r for r in DOC.splitlines() if r.startswith("| C5"))
    assert "a new key is the only way back" in c5
