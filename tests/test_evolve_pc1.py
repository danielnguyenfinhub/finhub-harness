"""Proof for Phase 3 item 8 of skills/finhub-harness-evolve/SKILL.md: a diff and one yes per target (PC1-PC3).

adapted from references/paperclip/server/src/services/change-consent-gate.ts:14, :48 and :117 (MIT, Paperclip AI), idea only
"""

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills/finhub-harness-evolve/SKILL.md"


def item() -> str:
    text = SKILL.read_text(encoding="utf-8")
    m = re.search(
        r"^8\. \*\*Show the diff and get a yes for each target\.\*\*.*$", text, re.MULTILINE
    )
    assert m, "Phase 3 item 8 is missing"
    return m.group(0)


def test_the_change_is_shown_as_a_diff() -> None:
    assert "as a fenced diff or as lines starting with `+` and `-`" in item()


def test_one_named_file_per_yes() -> None:
    p = item()
    assert "name the one file it changes" in p
    assert "One yes covers one file" in p


def test_a_yes_before_the_diff_does_not_count() -> None:
    assert "A yes that came before the diff was shown does not count." in item()


def test_an_earlier_yes_for_another_file_is_not_reused() -> None:
    assert "a yes given earlier in the conversation for another file is not reused" in item()


def test_no_answer_or_no_edits_nothing() -> None:
    p = item()
    assert "With no answer, or a no, edit nothing" in p
    assert "say that nothing was applied" in p


def test_backup_runs_after_the_yes() -> None:
    assert "backup gate runs after the yes and before the edit" in item()


def test_item_sits_in_phase_3_after_item_7() -> None:
    text = SKILL.read_text(encoding="utf-8")
    seven = text.index("7. **Say what the change should do.**")
    eight = text.index("8. **Show the diff and get a yes for each target.**")
    phase4 = text.index("### Phase 4: Update the change history and verify")
    assert seven < eight < phase4


def test_attribution_names_the_source_and_licence() -> None:
    p = item()
    assert "references/paperclip/server/src/services/change-consent-gate.ts:14, :48 and :117" in p
    assert "MIT, Paperclip AI" in p
