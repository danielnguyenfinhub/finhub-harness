"""Proof for the fail-closed reviewer verdict rules V1-V5 (C11).

adapted from references/crewai/lib/crewai/src/crewai/tasks/llm_guardrail.py:49 (MIT)
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REFS = REPO / "skills/finhub-harness/references"
PATTERNS = REFS / "team-patterns.md"
EXAMPLES = REFS / "team-examples.md"


def section() -> str:
    text = PATTERNS.read_text(encoding="utf-8")
    m = re.search(r"^### 1-4a\. .*?(?=^### |^## )", text, re.DOTALL | re.MULTILINE)
    assert m, "section 1-4a is missing"
    return m.group(0)


def test_section_sits_between_1_4_and_1_5() -> None:
    text = PATTERNS.read_text(encoding="utf-8")
    assert text.index("### 1-4. ") < text.index("### 1-4a. ") < text.index("### 1-5. ")


def test_unreadable_reply_is_not_a_pass() -> None:
    s = section().lower()
    assert "empty, cut off, not parseable" in s
    assert "names neither pass nor fail" in s
    assert "never a pass" in s


def test_error_or_timeout_is_not_a_pass() -> None:
    s = section().lower()
    assert "an error, a timeout or a refusal" in s
    assert "not verified" in s


def test_reviewer_gives_a_verdict_and_feedback_only() -> None:
    assert "does not rewrite the artifact" in section()


def test_retry_always_carries_feedback() -> None:
    s = section().lower()
    assert "a retry without feedback is not allowed" in s
    assert "the previous result" in s


def test_verdict_pair_is_exclusive() -> None:
    s = section().lower()
    assert "a pass carries no error" in s
    assert "a fail carries no result" in s


def test_cap_stops_with_the_last_feedback() -> None:
    assert "shows the user the last feedback" in section()


def test_example_stub_reviewer_garbage_does_not_advance() -> None:
    text = EXAMPLES.read_text(encoding="utf-8")
    m = re.search(r"^## Example 6: .*?(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    assert m, "Example 6 is missing"
    assert "does not advance to stage 3" in m.group(0).lower()
    assert "garbage" in m.group(0)


def test_attribution_lines() -> None:
    text = section() + EXAMPLES.read_text(encoding="utf-8")
    for cite in (
        "references/crewai/lib/crewai/src/crewai/tasks/llm_guardrail.py:49",
        "llm_guardrail.py:49, :89 and :125",
        "references/crewai/lib/crewai/src/crewai/utilities/guardrail.py:81 and :106",
    ):
        assert cite in text
    assert "(MIT)" in section()
