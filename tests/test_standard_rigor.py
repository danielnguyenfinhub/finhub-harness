# adapted from references/openrig/docs/reference/planning-dial.md:3-6 and :53 (Apache-2.0)
"""Proof for P3-standard-rigor: `standard` as a third level of the Rigor table (rigor_check.py), rules RS1-RS6 in
quality-gates.md 3-10, and the pointers in the template, SKILL.md and the light skill. Each refusal test asserts
the checker's message before the exit code."""

from __future__ import annotations

import contextlib
import importlib.machinery
import io
import re
import types
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/rigor_check.py"
QG_PATH = REPO / "skills/finhub-harness/references/quality-gates.md"
TEMPLATE = REPO / "skills/finhub-harness/references/orchestrator-template.md"
SKILL = REPO / "skills/finhub-harness/SKILL.md"
LIGHT = REPO / "skills/finhub-harness-light/SKILL.md"
TODAY = date(2026, 10, 14)
LEDGER_HEAD = (
    "# Waivers\n\n| id | scope | gap | owner | receipt | granted | expires |\n"
    "|---|---|---|---|---|---|---|\n"
)
CAND = "git:1a2b3c4d5e6f+0f1e2d3c4b5a6978"
STD = "| tool-std | other | standard | owner:daniel | 2026-10-14 |\n"
GATED = "| tool-std | other | gated | owner:daniel | 2026-10-14 |\n"
LIGHT_ROW = "| tool-std | other | light | owner:daniel | 2026-10-14 |\n"


def load() -> Any:
    loader = importlib.machinery.SourceFileLoader("rigor_check_std", str(SCRIPT))
    mod = types.ModuleType(loader.name)
    mod.__file__ = str(SCRIPT)
    loader.exec_module(mod)
    return mod


MOD = load()


def orch(rows: str) -> str:
    return (
        "# Orchestrator\n\n## Rigor\n\n| scope | class | level | assigned-by | on |\n"
        f"|---|---|---|---|---|\n{rows}\n## Next\n\ntext\n"
    )


def report(unit: str = "tool-std/s1", level: str = "standard") -> str:
    return (
        f"RESULT: PASS\nCANDIDATE: {CAND} n=1 excludes=_workspace/\nCARRIED: -\n"
        f"BASE: git:1a2b3c4d5e6f excl=none\nRIGOR: {level} unit={unit} by=owner:daniel on=2026-10-14\n\n## Gate\n"
    )


def run(
    tmp_path: Path,
    rows: str,
    unit: str = "tool-std/s1",
    prev: str | None = None,
    ledger: str = LEDGER_HEAD,
    reports: tuple[str, ...] = (),
) -> tuple[int, str]:
    (tmp_path / "orch.md").write_text(orch(rows), encoding="utf-8")
    (tmp_path / "WAIVERS.md").write_text(ledger, encoding="utf-8")
    args = ["rigor_check.py", "check", "orch.md", "WAIVERS.md", unit]
    if prev is None:
        args.append("-")
    else:
        (tmp_path / "prev.md").write_text(orch(prev), encoding="utf-8")
        args.append("prev.md")
    (tmp_path / "changed.txt").write_text("", encoding="utf-8")
    args.append("changed.txt")
    for i, text in enumerate(reports):
        (tmp_path / f"report{i}.md").write_text(text, encoding="utf-8")
        args.append(f"report{i}.md")
    buf, err = io.StringIO(), io.StringIO()
    with (
        contextlib.chdir(tmp_path),
        contextlib.redirect_stdout(buf),
        contextlib.redirect_stderr(err),
    ):
        code = MOD.main(args, today=TODAY)
    return code, buf.getvalue() + err.getvalue()


def test_standard_is_a_table_level(tmp_path: Path) -> None:
    code, out = run(tmp_path, STD, reports=(report(),))
    assert "EFFECTIVE: tool-std/s1 standard" in out, out
    assert code == 0, out


def test_standard_unit_needs_a_qa_report(tmp_path: Path) -> None:
    code, out = run(tmp_path, STD)
    assert "standard unit has no QA report" in out, out
    assert code == 4, out


def test_standard_report_line_must_say_standard(tmp_path: Path) -> None:
    code, out = run(tmp_path, STD, reports=(report(level="gated"),))
    assert "expected `RIGOR: standard unit=tool-std/s1" in out, out
    assert code == 4, out


def test_audited_decision_cannot_be_standard(tmp_path: Path) -> None:
    rows = "| ce | audited-decision | standard | owner:daniel | 2026-10-14 |\n"
    code, out = run(tmp_path, rows, unit="ce/c1")
    assert "audited-decision output cannot be assigned standard in the table" in out, out
    assert code == 4, out


def test_gated_to_standard_is_a_lowering(tmp_path: Path) -> None:
    code, out = run(tmp_path, STD, prev=GATED, reports=(report(),))
    assert "other, gated -> other, standard lowers rigor" in out, out
    assert code == 4, out


def test_light_to_standard_is_a_raise(tmp_path: Path) -> None:
    code, out = run(tmp_path, STD, prev=LIGHT_ROW, reports=(report(),))
    assert "lowers rigor" not in out, out
    assert code == 0, out


def test_standard_to_light_is_a_lowering(tmp_path: Path) -> None:
    code, out = run(tmp_path, LIGHT_ROW, prev=STD)
    assert "other, standard -> other, light lowers rigor" in out, out
    assert code == 4, out


def test_new_scope_standard_is_a_lowering(tmp_path: Path) -> None:
    prev = "| other-scope | other | light | owner:daniel | 2026-10-14 |\n"
    code, out = run(tmp_path, STD + prev, prev=prev, reports=(report(),))
    assert "audited-decision -> other, standard lowers rigor" in out, out
    assert code == 4, out


def test_item_downgrade_of_standard_unit_runs_light(tmp_path: Path) -> None:
    ledger = LEDGER_HEAD + (
        "| RIGOR-TS-001 | rigor:tool-std/s1 | judge and QA not run for tool-std/s1 | daniel "
        '| words: "skip the review for this one" 2026-10-14 | 2026-10-14 | 2026-10-14 |\n'
    )
    code, out = run(tmp_path, STD, ledger=ledger)
    assert "DOWNGRADE: tool-std/s1 runs light" in out, out
    assert code == 0, out


def test_unknown_level_is_still_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, "| tool-std | other | heavy | owner:daniel | 2026-10-14 |\n")
    assert "level must be light, standard or gated" in out, out
    assert code == 4, out


def test_new_scope_other_gated_still_needs_a_receipt(tmp_path: Path) -> None:
    prev = "| other-scope | other | light | owner:daniel | 2026-10-14 |\n"
    rows = "| tool-g | other | gated | owner:daniel | 2026-10-14 |\n" + prev
    rep = report(unit="tool-g/g1", level="gated")
    code, out = run(tmp_path, rows, unit="tool-g/g1", prev=prev, reports=(rep,))
    assert "audited-decision -> other, gated lowers rigor" in out, out
    assert code == 4, out


def test_quality_gates_defines_three_levels() -> None:
    text = QG_PATH.read_text(encoding="utf-8")
    assert "Three levels, no fourth." in text, "Three levels, no fourth."
    assert "Two levels, no third" not in text, "Two levels, no third"
    assert len(re.findall(r"^\| RS[1-6] \|", text, re.MULTILINE)) == 6, "RS1-RS6 rows"


def test_standard_cuts_are_stated() -> None:
    text = QG_PATH.read_text(encoding="utf-8")
    for phrase in (
        "_<item>_fixes.md",
        "unaudited fix",
        "never a residual row",
        "not run (standard)",
        "One QA run per unit",
        "One judge round.",
        "An audited decision is never `standard`",
    ):
        assert phrase in text, phrase


def test_skill_offers_standard_and_keeps_light_default() -> None:
    text = SKILL.read_text(encoding="utf-8")
    phrase = "offer `standard` for a normal expert build"
    assert phrase in text, phrase
    phrase = "`other` units are `light` unless the owner assigns them `standard` or `gated`"
    assert phrase in text, phrase


def test_run_mode_floor_in_template() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    for phrase in (
        "The Rigor table is the floor",
        "- **standard**:",
        "keeps its gates in light mode",
    ):
        assert phrase in text, phrase


def test_light_skill_names_three_levels_and_stays_small() -> None:
    text = LIGHT.read_text(encoding="utf-8")
    assert "## Three levels" in text, "## Three levels"
    assert "you never pick or change it" in text, "you never pick or change it"
    assert "references/" not in text, "references/"
    assert len(text.encode("utf-8")) <= 8000, len(text.encode("utf-8"))


def test_changed_files_carry_attribution_and_no_hangul() -> None:
    attribution = "adapted from references/openrig/docs/reference/planning-dial.md:3-6"
    for path in (QG_PATH, SCRIPT):
        assert attribution in path.read_text(encoding="utf-8"), f"{path.name}: {attribution}"
    for path in (QG_PATH, SCRIPT, TEMPLATE, SKILL, LIGHT, Path(__file__)):
        bad = [c for c in path.read_text(encoding="utf-8") if 0xAC00 <= ord(c) <= 0xD7A3]
        assert not bad, f"{path.name}: Hangul"
