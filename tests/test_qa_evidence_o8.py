"""Proof for the evidence-honesty rules E1-E5 in qa-agent-guide.md section 7-4a (O8).

adapted from references/openhands/.agents/skills/custom-codereview-guide.md:207 (MIT)
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GUIDE = REPO / "skills/finhub-harness/references/qa-agent-guide.md"


def text() -> str:
    return GUIDE.read_text(encoding="utf-8")


def section() -> str:
    m = re.search(r"^### 7-4a\. .*?(?=^### )", text(), re.DOTALL | re.MULTILINE)
    assert m, "section 7-4a is missing"
    return m.group(0)


def test_section_sits_between_7_4_and_7_5() -> None:
    t = text()
    assert t.index("### 7-4. ") < t.index("### 7-4a. ") < t.index("### 7-5. ")


def test_mock_is_not_live_evidence() -> None:
    s = section().lower()
    assert "a mocked or stubbed run is regression coverage, not live evidence" in s


def test_live_claim_names_backend_and_model() -> None:
    assert "names the backend and the model" in section().lower()


def test_same_setup_before_and_after() -> None:
    assert "same setup before and after" in section().lower()


def test_absence_of_the_false_claim_is_pinned() -> None:
    s = section().lower()
    assert "asserts the absence of the false claim" in s


def test_checked_scope_is_stated() -> None:
    assert "what was checked and what was not" in section().lower()


def test_rerun_yourself_and_point_at_drift_row() -> None:
    s = section().lower()
    assert "re-run the command yourself" in s
    assert "drift row" in s


def test_excuses_table_has_the_live_claim_row() -> None:
    assert "The builder says it ran live" in text()


def test_attribution_lines() -> None:
    s = section()
    assert "references/openhands/.agents/skills/custom-codereview-guide.md:207-221" in s
    assert "references/deepseek_harness/docs/testing.md:27" in s
    assert "(MIT)" in s
