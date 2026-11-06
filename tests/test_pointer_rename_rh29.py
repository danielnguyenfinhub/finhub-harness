"""Proof for the renamed-orchestrator rule of the pointer step in skills/finhub-harness/SKILL.md (RH29).

The skip-when-current rule was already adopted with C33 (case 3 of the pointer step).

adapted from references/openrig/packages/daemon/src/domain/managed-blocks.ts:8 and :36 (Apache-2.0), idea only
"""

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills/finhub-harness/SKILL.md"


def paragraph() -> str:
    text = SKILL.read_text(encoding="utf-8")
    m = re.search(r"^A renamed orchestrator:.*$", text, re.MULTILINE)
    assert m, "the renamed-orchestrator paragraph is missing"
    return m.group(0)


def test_rule_names_the_trigger_case() -> None:
    p = paragraph()
    assert "valid pair whose name matches no orchestrator skill of this harness" in p


def test_old_block_is_left_alone_and_the_user_is_asked() -> None:
    p = paragraph()
    assert "Leave it exactly as it is" in p
    assert "ask the user whether to remove it" in p


def test_never_deletes_or_rewrites_unasked() -> None:
    assert "never delete or rewrite a block under another name unasked" in paragraph()


def test_says_the_lint_does_not_flag_it() -> None:
    assert "The lint does not flag it." in paragraph()


def test_rule_sits_after_the_four_cases_and_before_the_backup_paragraph() -> None:
    text = SKILL.read_text(encoding="utf-8")
    four = text.index("4. Anything else (a second begin")
    rename = text.index("A renamed orchestrator:")
    backup = text.index("Back up before the first write,")
    assert four < rename < backup


def test_skip_when_current_is_still_there() -> None:
    assert "If the result matches those lines, write nothing." in SKILL.read_text(encoding="utf-8")


def test_attribution_names_the_source_and_licence() -> None:
    p = paragraph()
    assert "references/openrig/packages/daemon/src/domain/managed-blocks.ts:8 and :36" in p
    assert "Apache-2.0" in p
