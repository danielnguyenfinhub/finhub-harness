"""Proof for the experiment profile reference (MH1-MH10, R9).

adapted from references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:23 (Apache-2.0)
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "skills/finhub-harness/references/experiment-profile.md"
SKILL = REPO / "skills/finhub-harness/SKILL.md"


def doc() -> str:
    return DOC.read_text(encoding="utf-8").lower()


def test_seven_contract_items_are_named() -> None:
    d = doc()
    for item in (
        "mutable surface",
        "read-only evaluation surface",
        "baseline run",
        "comparison rule",
        "experiment ledger",
        "keep/discard rule",
        "failure rule",
    ):
        assert item in d, item
    assert "before the first candidate" in d


def test_changing_the_yardstick_starts_a_new_run() -> None:
    assert "starts a new run with a new baseline" in doc()


def test_ledger_rows_and_statuses() -> None:
    d = doc()
    for word in ("keep", "discard", "crash", "timeout"):
        assert f"`{word}`" in d, word
    assert "baseline is row one" in d


def test_loop_has_seven_steps_in_order() -> None:
    d = doc()
    steps = [
        "snapshot the request",
        "measure the baseline",
        "make one bounded candidate",
        "run it under the budget",
        "log it at once",
        "decide",
        "summarise",
    ]
    pos = [d.index(s) for s in steps]
    assert pos == sorted(pos)


def test_failure_policy_retries_only_mechanical_failures() -> None:
    d = doc()
    assert "only mechanical failures" in d
    assert d.count("stays in the ledger") >= 2


def test_when_not_to_use_has_five_refusals() -> None:
    d = doc()
    for refusal in (
        "evaluation surface is still changing",
        "mutable surface is so broad",
        "no declared metric",
        "production side effects",
        "cannot audit",
    ):
        assert refusal in d, refusal


def test_it_is_a_profile_not_a_seventh_pattern() -> None:
    assert "not a seventh pattern" in doc()


def test_topology_ab_method() -> None:
    d = doc()
    assert "same task fixture" in d and "same model" in d and "same budget" in d
    assert "four paired scenarios" in d
    assert "run one pair first" in d
    assert "repeat only a tie" in d


def test_gates_come_before_the_score() -> None:
    d = doc()
    assert "gates before the score" in d
    assert "cannot buy back a failed gate" in d


def test_effect_size_claims_carry_sample_size() -> None:
    d = doc()
    assert "sample size" in d and "author-measured" in d
    assert "run their own pilot" in d


def test_attribution_lines() -> None:
    t = DOC.read_text(encoding="utf-8")
    assert "references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:23-33" in t
    assert "references/meta_harness/.agents/skills/harness/references/skill-testing-guide.md:184-202" in t
    assert "references/revfactory_harness/README.md:259" in t
    assert "(Apache-2.0)" in t


def test_skill_md_points_at_the_profile() -> None:
    assert "references/experiment-profile.md" in SKILL.read_text(encoding="utf-8")
