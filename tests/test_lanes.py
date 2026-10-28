"""The building team's Quick and Full lanes: the table row, the effective level, and the pinned lane text."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / ".claude/skills/master-finhub-orchestrator/SKILL.md"
PHASE = ROOT / ".claude/skills/master-finhub-orchestrator/references/phase-table.md"
SCRIPT = ROOT / "skills/finhub-harness/scripts/rigor_check.py"
TODAY = date(2026, 10, 28)

sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("rigor_check_lanes", SCRIPT)
assert spec is not None and spec.loader is not None
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)

LIGHT_ROW = "| master-finhub-unit | other | light | owner:daniel | 2026-10-28 |"
GATED_ROW = "| master-finhub-unit | other | gated | owner:daniel | 2026-10-14 |"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def run(prev: str | None) -> str:
    _, out = MOD.check_text("o", read(ORCH), "-", None, "master-finhub-unit/x", prev, [], [], TODAY)
    return "\n".join(out)


def test_table_row_is_light_so_quick_is_the_default() -> None:
    assert LIGHT_ROW in read(ORCH), "light row"
    assert GATED_ROW not in read(ORCH), "old gated row still present"
    assert "EFFECTIVE: master-finhub-unit/x light" in run(None)


def test_lowering_the_row_needs_a_receipt() -> None:
    prev = read(ORCH).replace(LIGHT_ROW, GATED_ROW)
    assert prev != read(ORCH), "swapped the row back"
    assert "table" in run(prev), "a lowering against the previous gated table is flagged"


def test_lanes_section_pins_the_quick_steps_and_the_stop_list() -> None:
    t = read(ORCH)
    lanes = t[t.index("## Lanes") : t.index("## 워크플로우")]
    for needle in (
        "**Quick (default).**",
        "No architect, judge or QA agent.",
        "src/master_finhub/tools/safety.py",
        "A change to `WAIVERS.md` or to the Rigor table is always a unit of its own, run `gated`.",
        "**Full (only when Daniel says full).**",
        "carry the rows whose text is unchanged by id under rule C4",
    ):
        assert needle in lanes, needle


def test_full_lane_marks_and_the_raise_line_are_present() -> None:
    t = read(ORCH)
    assert "### Phase 2: Strategy + risk debate\n(Full lane only.)" in t
    assert "### Phase 3: Build\n(Full lane only." in t
    assert "on=<the date Daniel said full>" in t
    assert "on=2026-10-14" not in t, "old fixed date left in a brief line"
    assert "A new scope cannot be lowered this way" in t


def test_routing_has_both_lanes() -> None:
    p = read(PHASE)
    assert '"build C3 full"' in p and "Quick lane" in p
