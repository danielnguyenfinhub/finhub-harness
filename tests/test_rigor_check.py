# adapted from references/openrig/docs/reference/sdlc-conventions.md:23-24 (Apache-2.0)
"""Proof for OR-S8: skills/finhub-harness/scripts/rigor_check.py and the prose of quality-gates.md section
3-10, SKILL.md, the agents and CLAUDE.md. The clock is injected as an argument; no option sets it. Each
refusal test asserts the checker's own message before the exit code, so a rule that stops firing fails at
that message."""

from __future__ import annotations

import contextlib
import importlib.machinery
import io
import re
import subprocess
import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/rigor_check.py"
FINDING_TAGS = REPO / "skills/finhub-harness/scripts/finding_tags.py"
QUALITY_GATES = REPO / "skills/finhub-harness/references/quality-gates.md"
SKILL = REPO / "skills/finhub-harness/SKILL.md"
TEMPLATE = REPO / "skills/finhub-harness/references/orchestrator-template.md"
TEAM_PATTERNS = REPO / "skills/finhub-harness/references/team-patterns.md"
QA_GUIDE = REPO / "skills/finhub-harness/references/qa-agent-guide.md"
BOUNDARY_QA = REPO / ".claude/agents/boundary-qa.md"
JUDGE = REPO / ".claude/agents/adversarial-risk-judge.md"
VERDICT_SCHEMA = REPO / ".claude/skills/adversarial-audit/references/verdict-schema.md"
ORCHESTRATOR = REPO / ".claude/skills/master-finhub-orchestrator/SKILL.md"
CLAUDE_MD = REPO / "CLAUDE.md"
TODAY = date(2026, 10, 14)
UNIT = "client-email/c1"
LEDGER_HEAD = (
    "# Waivers\n\n| id | scope | gap | owner | receipt | granted | expires |\n"
    "|---|---|---|---|---|---|---|\n"
)
CAND = "git:1a2b3c4d5e6f+0f1e2d3c4b5a6978"
ROWS = (
    "| client-email | audited-decision | gated | default | 2026-10-14 |\n"
    "| tool-build | other | gated | owner:daniel | 2026-10-14 |\n"
    "| note-draft | other | light | owner:daniel | 2026-10-14 |\n"
)
LOWERED = ROWS.replace(
    "| client-email | audited-decision | gated | default |",
    "| client-email | other | light | owner:daniel |",
)


def load() -> Any:
    loader = importlib.machinery.SourceFileLoader("rigor_check_under_test", str(SCRIPT))
    mod = types.ModuleType(loader.name)
    mod.__file__ = str(SCRIPT)
    loader.exec_module(mod)
    return mod


MOD = load()


def orch(rows: str | None = None, extra: str = "") -> str:
    rows = rows if rows is not None else ROWS
    return (
        "# Orchestrator\n\n## Rigor\n\n| scope | class | level | assigned-by | on |\n"
        f"|---|---|---|---|---|\n{rows}{extra}\n## Next\n\ntext\n"
    )


def dg(
    unit: str = UNIT,
    granted: str = "2026-10-14",
    expires: str = "2026-10-14",
    owner: str = "daniel",
    receipt: str | None = None,
    rid: str = "RIGOR-CE-001",
) -> str:
    receipt = receipt if receipt is not None else f'words: "skip the review for this one" {granted}'
    return (
        f"| {rid} | rigor:{unit} | judge and QA not run for {unit} | {owner} | {receipt} "
        f"| {granted} | {expires} |\n"
    )


def report(
    unit: str = UNIT,
    by: str = "default",
    on: str = "2026-10-14",
    level: str = "gated",
    first: str = "RESULT: PASS",
) -> str:
    return (
        f"{first}\nCANDIDATE: {CAND} n=1 excludes=_workspace/\nCARRIED: -\n"
        f"BASE: git:1a2b3c4d5e6f excl=none\nRIGOR: {level} unit={unit} by={by} on={on}\n\n## Gate\n"
    )


def run(
    tmp_path: Path,
    table: str | None = None,
    ledger: str | None = LEDGER_HEAD,
    unit: str = UNIT,
    prev: str | None = None,
    changed: tuple[str, ...] = (),
    reports: tuple[str, ...] = (),
    today: date = TODAY,
) -> tuple[int, str]:
    (tmp_path / "orch.md").write_text(table if table is not None else orch(), encoding="utf-8")
    args = ["rigor_check.py", "check", "orch.md"]
    if ledger is None:
        args.append("-")
    else:
        (tmp_path / "WAIVERS.md").write_text(ledger, encoding="utf-8")
        args.append("WAIVERS.md")
    args.append(unit)
    if prev is None:
        args.append("-")
    else:
        (tmp_path / "prev.md").write_text(prev, encoding="utf-8")
        args.append("prev.md")
    (tmp_path / "changed.txt").write_text(
        "\n".join(changed) + ("\n" if changed else ""), encoding="utf-8"
    )
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
        code = MOD.main(args, today=today)
    return code, buf.getvalue() + err.getvalue()


# ---------------------------------------------------------------- the two classes


def test_audited_decision_starts_gated_and_a_matching_qa_report_is_clean(tmp_path: Path) -> None:
    code, out = run(tmp_path, reports=(report(),))
    assert f"EFFECTIVE: {UNIT} gated" in out, out
    assert code == 0, out


def test_other_unit_is_light_and_needs_no_report(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="note-draft/n1")
    assert "EFFECTIVE: note-draft/n1 light" in out, out
    assert "DOWNGRADE:" not in out, out
    assert code == 0, out


def test_owner_assigned_gated_other_unit_needs_a_qa_report(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="tool-build/t1")
    assert "gated unit has no QA report" in out, out
    assert code == 4, out


def test_agent_cannot_assign_rigor(tmp_path: Path) -> None:
    for by in ("agent:builder", "qa", "plan", "role:reviewer", "owner:mallory", "light", "owner:"):
        rows = f"| tool-build | other | gated | {by} | 2026-10-14 |\n"
        code, out = run(tmp_path, table=orch(rows), unit="tool-build/t1")
        assert "assigned-by must be default or owner:<name>" in out, f"{by!r}: {out}"
        assert code == 4, out


def test_audited_decision_cannot_be_light_in_the_table(tmp_path: Path) -> None:
    rows = "| client-email | audited-decision | light | owner:daniel | 2026-10-14 |\n"
    code, out = run(tmp_path, table=orch(rows), reports=(report(by="owner:daniel"),))
    assert "audited-decision output cannot be assigned light in the table" in out, out
    assert code == 4, out


def test_class_other_cannot_be_assigned_by_default(tmp_path: Path) -> None:
    rows = "| note-draft | other | light | default | 2026-10-14 |\n"
    code, out = run(tmp_path, table=orch(rows), unit="note-draft/n1")
    assert "class other must be assigned by owner:<name>, not default" in out, out
    assert code == 4, out


def test_class_and_level_values_are_checked(tmp_path: Path) -> None:
    cases = {
        "| client-email | software | gated | default | 2026-10-14 |\n": "class must be one of",
        "| client-email | other | heavy | owner:daniel | 2026-10-14 |\n": "level must be light or gated",
    }
    for rows, msg in cases.items():
        code, out = run(tmp_path, table=orch(rows))
        assert msg in out, f"{msg}: {out}"
        assert code == 4, out


# ---------------------------------------------------------------- the item downgrade is a ledger row


def test_active_downgrade_for_the_named_item_makes_it_light(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg())
    assert f"EFFECTIVE: {UNIT} light" in out, out
    assert (
        "DOWNGRADE: client-email/c1 runs light (no judge, no QA agent) by daniel, waiver RIGOR-CE-001"
        in out
    ), out
    assert code == 0, out


def test_downgrade_covers_only_the_named_item(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(), unit="client-email/c2")
    assert "EFFECTIVE: client-email/c2 gated" in out, out
    assert "gated unit has no QA report" in out, out
    assert code == 4, out


def test_downgrade_is_active_on_its_expiry_day(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(granted="2026-10-13", expires="2026-10-14"))
    assert "the unit runs gated" not in out, out
    assert code == 0, out


def test_expired_downgrade_reverts_to_gated(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(granted="2026-10-12", expires="2026-10-13"))
    assert "expired on 2026-10-13; the unit runs gated" in out, out
    assert "gated unit has no QA report" in out, out
    assert code == 4, out


def test_downgrade_dated_tomorrow_is_not_active(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(granted="2026-10-15", expires="2026-10-15"))
    assert "not active until 2026-10-15; the unit runs gated" in out, out
    assert "EFFECTIVE: client-email/c1 gated" in out, out
    assert code == 4, out


def test_downgrade_must_name_a_table_scope_and_an_item(tmp_path: Path) -> None:
    for scope in ("ghost/x", "client-email", "client-email/", "Client-Email/c1"):
        code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(unit=scope), reports=(report(),))
        assert (
            "downgrade waiver names no scope and item of the Rigor table" in out
        ), f"{scope!r}: {out}"
        assert code == 4, out


def test_downgrade_row_follows_the_ledger_rules(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(owner="builder"), reports=(report(),))
    assert "owner must be one of: daniel" in out, out
    assert code == 4, out
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(receipt="ok fine"), reports=(report(),))
    assert "receipt must be" in out, out
    assert code == 4, out
    wide = dg(granted="2026-08-01", expires="2026-12-01")
    code, out = run(tmp_path, ledger=LEDGER_HEAD + wide, reports=(report(),))
    assert "exceeds ceiling" in out, out
    assert code == 4, out


def test_forged_receipt_passes_the_script_and_is_a_known_limit(tmp_path: Path) -> None:
    # quoted words the owner never said look like any other quote; the owner reading the DOWNGRADE
    # line, and QA comparing the quote in a downgrade unit of its own (quality-gates 3-9 W6, 3-10 RG5),
    # are the controls. A whole forged QA report is not told from a real one either.
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(receipt='words: "he said yes" 2026-10-14'))
    assert code == 0, out
    assert "DOWNGRADE:" in out, out


def test_no_ledger_means_no_downgrade(tmp_path: Path) -> None:
    code, out = run(tmp_path, ledger=None, reports=(report(),))
    assert f"EFFECTIVE: {UNIT} gated" in out, out
    assert code == 0, out
    code, out = run(tmp_path, ledger=None)
    assert "gated unit has no QA report" in out, out
    assert code == 4, out


def test_the_item_name_table_is_reserved(tmp_path: Path) -> None:
    code, out = run(
        tmp_path, unit="client-email/table", reports=(report(unit="client-email/table"),)
    )
    assert "reserved for table receipts" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- lowering the table against the previous commit


def test_reclassifying_audited_decision_to_other_light_is_refused_without_a_receipt(
    tmp_path: Path,
) -> None:
    # the exact edit `audited-decision -> other, light, default`, then the same with a typed owner name
    for by in ("default", "owner:daniel"):
        now = ROWS.replace(
            "| client-email | audited-decision | gated | default |",
            f"| client-email | other | light | {by} |",
        )
        code, out = run(tmp_path, table=orch(now), prev=orch(), reports=(report(by=by),))
        assert (
            "audited-decision -> other, light lowers rigor and needs an active receipt row "
            "rigor:client-email/table" in out
        ), f"{by}: {out}"
        assert code == 4, out


def test_lowering_is_allowed_with_an_active_receipt_row(tmp_path: Path) -> None:
    ledger = LEDGER_HEAD + dg(unit="client-email/table")
    code, out = run(tmp_path, table=orch(LOWERED), prev=orch(), ledger=ledger)
    assert "LOWERED: client-email audited-decision -> other, light by daniel" in out, out
    assert code == 0, out


def test_a_receipt_for_a_lowering_must_be_active(tmp_path: Path) -> None:
    for granted, expires in (("2026-10-12", "2026-10-13"), ("2026-10-15", "2026-10-15")):
        ledger = LEDGER_HEAD + dg(unit="client-email/table", granted=granted, expires=expires)
        code, out = run(tmp_path, table=orch(LOWERED), prev=orch(), ledger=ledger)
        assert "lowers rigor and needs an active receipt row" in out, f"{granted}: {out}"
        assert code == 4, out


def test_lowering_gated_to_light_is_refused_without_a_receipt(tmp_path: Path) -> None:
    now = ROWS.replace(
        "| tool-build | other | gated | owner:daniel |",
        "| tool-build | other | light | owner:daniel |",
    )
    code, out = run(tmp_path, table=orch(now), prev=orch(), unit="tool-build/t1")
    assert "other, gated -> other, light lowers rigor" in out, out
    assert code == 4, out


def test_removing_a_scope_is_refused_without_a_receipt(tmp_path: Path) -> None:
    now = ROWS.replace("| note-draft | other | light | owner:daniel | 2026-10-14 |\n", "")
    code, out = run(tmp_path, table=orch(now), prev=orch(), reports=(report(),))
    assert "note-draft: scope removed from the Rigor table lowers rigor" in out, out
    assert code == 4, out


def test_removing_a_scope_is_allowed_with_an_active_receipt_row(tmp_path: Path) -> None:
    # BC1: the receipt for a removed scope is read against the scopes of the previous table too
    now = ROWS.replace("| note-draft | other | light | owner:daniel | 2026-10-14 |\n", "")
    ledger = LEDGER_HEAD + dg(unit="note-draft/table")
    code, out = run(tmp_path, table=orch(now), prev=orch(), ledger=ledger, reports=(report(),))
    assert "downgrade waiver names no scope and item of the Rigor table" not in out, out
    assert "LOWERED:" in out and "note-draft" in out, out
    assert code == 0, out


def test_a_new_scope_classed_other_is_a_lowering(tmp_path: Path) -> None:
    now = ROWS + "| new-kind | other | light | owner:daniel | 2026-10-14 |\n"
    code, out = run(tmp_path, table=orch(now), prev=orch(), unit="new-kind/x")
    assert "new-kind: audited-decision -> other, light lowers rigor" in out, out
    assert code == 4, out


def test_a_new_scope_classed_audited_decision_needs_no_receipt(tmp_path: Path) -> None:
    now = ROWS + "| new-kind | audited-decision | gated | default | 2026-10-14 |\n"
    code, out = run(
        tmp_path,
        table=orch(now),
        prev=orch(),
        unit="new-kind/x",
        reports=(report(unit="new-kind/x"),),
    )
    assert "lowers rigor" not in out, out
    assert code == 0, out


def test_raising_and_leaving_the_table_alone_need_no_receipt(tmp_path: Path) -> None:
    code, out = run(tmp_path, prev=orch(), reports=(report(),))
    assert "lowers rigor" not in out, out
    assert code == 0, out
    raised = ROWS.replace(
        "| tool-build | other | gated |", "| tool-build | audited-decision | gated |"
    )
    code, out = run(
        tmp_path,
        table=orch(raised),
        prev=orch(),
        unit="tool-build/t1",
        reports=(report(unit="tool-build/t1", by="owner:daniel"),),
    )
    assert "lowers rigor" not in out, out
    assert code == 0, out


def test_a_previous_file_with_no_table_is_the_first_commit(tmp_path: Path) -> None:
    code, out = run(tmp_path, prev="# no table yet\n", reports=(report(),))
    assert "lowers rigor" not in out, out
    assert code == 0, out


def test_table_and_ledger_in_one_commit_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, prev=orch(), changed=("orch.md", "WAIVERS.md"), reports=(report(),))
    assert "the Rigor table and the ledger change in one commit" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- a light unit changes no ledger


def test_a_light_unit_must_not_change_the_ledger(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="note-draft/n1", changed=("src/a.py", "WAIVERS.md"))
    assert "a light unit must not change the ledger" in out, out
    assert code == 4, out
    code, out = run(tmp_path, ledger=LEDGER_HEAD + dg(), changed=("WAIVERS.md",))
    assert "a light unit must not change the ledger" in out, out
    assert code == 4, out


def test_a_gated_unit_may_change_the_ledger(tmp_path: Path) -> None:
    code, out = run(tmp_path, changed=("WAIVERS.md",), reports=(report(),))
    assert "must not change the ledger" not in out, out
    assert code == 0, out


def test_changed_paths_are_compared_after_normalising(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="note-draft/n1", changed=("./WAIVERS.md",))
    assert "a light unit must not change the ledger" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- reports


def test_gated_unit_without_report_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="tool-build/t1")
    assert "gated unit has no QA report" in out, out
    assert code == 4, out


def test_gated_unit_with_only_a_verdict_is_refused(tmp_path: Path) -> None:
    verdict = report(first="TOTALS: UPHELD 1 / REJECTED 0 / UNVERIFIED 0 - round 1/3")
    code, out = run(tmp_path, reports=(verdict,))
    assert "gated unit has no QA report" in out, out
    assert code == 4, out


def test_a_failing_qa_report_does_not_license_a_commit(tmp_path: Path) -> None:
    code, out = run(tmp_path, reports=(report(first="RESULT: FAIL"),))
    assert "QA report is not RESULT: PASS" in out, out
    assert code == 4, out


def test_report_without_rigor_line_is_refused(tmp_path: Path) -> None:
    text = report().replace(f"RIGOR: gated unit={UNIT} by=default on=2026-10-14\n", "")
    code, out = run(tmp_path, reports=(text,))
    assert "report has no RIGOR line" in out, out
    assert code == 4, out


def test_rigor_line_on_line_9_is_refused(tmp_path: Path) -> None:
    line = f"RIGOR: gated unit={UNIT} by=default on=2026-10-14\n"
    text = report().replace(line, "") + "\n".join(f"filler {i}" for i in range(2)) + "\n" + line
    assert text.splitlines().index(line.strip()) == 8  # line 9
    code, out = run(tmp_path, reports=(text,))
    assert "report has no RIGOR line" in out, out
    assert code == 4, out


def test_report_rigor_line_must_match_the_table(tmp_path: Path) -> None:
    kws = (
        {"by": "owner:daniel"},
        {"on": "2026-10-13"},
        {"unit": "client-email/c9"},
        {"level": "light"},
    )
    for kw in kws:
        code, out = run(tmp_path, reports=(report(**kw),))
        assert "RIGOR line does not match the table row" in out, f"{kw}: {out}"
        assert code == 4, out


def test_rigor_line_inside_a_code_fence_does_not_count(tmp_path: Path) -> None:
    line = f"RIGOR: gated unit={UNIT} by=default on=2026-10-14\n"
    text = report().replace(line, f"```\n{line}```\n")
    code, out = run(tmp_path, reports=(text,))
    assert "report has no RIGOR line" in out, out
    assert code == 4, out


def test_two_rigor_lines_are_refused(tmp_path: Path) -> None:
    line = f"RIGOR: gated unit={UNIT} by=default on=2026-10-14\n"
    text = report().replace("\n\n## Gate", f"\n{line}\n## Gate")
    code, out = run(tmp_path, reports=(text,))
    assert "report has more than one RIGOR line" in out, out
    assert code == 4, out


def test_report_must_start_with_a_verdict_line(tmp_path: Path) -> None:
    code, out = run(tmp_path, reports=(report(first="hello"),))
    assert "report first line is not RESULT: or TOTALS:" in out, out
    assert code == 4, out


def test_unknown_unit_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="ghost/x", reports=(report(),))
    assert "unit is not a scope in the Rigor table" in out, out
    assert code == 4, out
    code, out = run(tmp_path, unit="client-email", reports=(report(),))
    assert "unit must be <scope>/<item>" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- the table


def test_table_shape_rules(tmp_path: Path) -> None:
    row = "| client-email | audited-decision | gated | default | 2026-10-14 |\n"
    cases = {
        row + row: "repeated scope",
        "| client-email | audited-decision | gated | default |  |\n": "blank cell",
        row.replace("client-email", "Client Email"): "scope must match",
        "| client-email | audited-decision | gated | default |\n": "expected 5 cells",
    }
    for rows, msg in cases.items():
        code, out = run(tmp_path, table=orch(rows), reports=(report(),))
        assert msg in out, f"{msg}: {out}"
        assert code == 4, out


def test_on_date_rules(tmp_path: Path) -> None:
    for on, msg in (
        ("2026-02-30", "on must be a calendar date"),
        ("2026-10-16", "on is more than 1 day after today"),
    ):
        rows = f"| client-email | audited-decision | gated | default | {on} |\n"
        code, out = run(tmp_path, table=orch(rows), reports=(report(on=on),))
        assert msg in out, f"{on}: {out}"
        assert code == 4, out
    rows = "| client-email | audited-decision | gated | default | 2026-10-15 |\n"
    code, out = run(tmp_path, table=orch(rows), reports=(report(on="2026-10-15"),))
    assert "on is more than" not in out, out
    assert code == 0, out


def test_a_fenced_table_is_not_read(tmp_path: Path) -> None:
    only_fenced = (
        "# O\n\n## Rigor\n\n```\n| scope | class | level | assigned-by | on |\n|---|---|---|---|---|\n"
        "| client-email | audited-decision | gated | default | 2026-10-14 |\n```\n"
    )
    code, out = run(tmp_path, table=only_fenced)
    assert "no Rigor table" in out, out
    assert code == 2, out
    decoy = orch(extra="\n```\n| ghost | other | light | agent:x | 2026-10-14 |\n```\n")
    code, out = run(tmp_path, table=decoy, reports=(report(),))
    assert "agent:x" not in out, out
    assert code == 0, out


def test_a_second_table_or_section_is_refused(tmp_path: Path) -> None:
    twice = orch() + "\n## Rigor\n\n" + orch().split("## Rigor\n\n", 1)[1].split("\n## Next")[0]
    code, out = run(tmp_path, table=twice, reports=(report(),))
    assert "more than one ## Rigor section" in out, out
    assert code == 4, out
    second = orch(
        extra="\n| scope | class | level | assigned-by | on |\n|---|---|---|---|---|\n"
        "| client-email | other | light | owner:daniel | 2026-10-14 |\n"
    )
    code, out = run(tmp_path, table=second, reports=(report(),))
    assert "second table in the Rigor section" in out, out
    assert code == 4, out


def test_usage_errors_exit_2(tmp_path: Path) -> None:
    code, out = run(tmp_path, table="# no table here\n")
    assert "no Rigor table" in out, out
    assert code == 2, out
    code, out = run(tmp_path, table=orch("| a | b | c | d | e |\n").replace("class", "kind"))
    assert "the first table line must be the header" in out, out
    assert code == 2, out
    code, out = run(tmp_path, ledger="# no ledger table\n")
    assert "no ledger table" in out, out
    assert code == 2, out
    assert MOD.main(["rigor_check.py", "check", "--x", "-", UNIT, "-", "-"]) == 2
    assert MOD.main(["rigor_check.py", "check", str(tmp_path / "m.md"), "-", UNIT, "-", "-"]) == 2
    assert MOD.main(["rigor_check.py", "check", str(tmp_path / "m.md"), "-", UNIT, "-"]) == 2


# ---------------------------------------------------------------- the report line next to the existing checkers


def qa_text(rigor_early: bool) -> str:
    base = "BASE: git:1a2b3c4d5e6f excl=5e6f7a8b9c0d"
    rigor = f"RIGOR: gated unit={UNIT} by=default on=2026-10-14"
    head = [f"CANDIDATE: {CAND} n=214 excludes=_workspace/", "CARRIED: -", base]
    head = [rigor, *head] if rigor_early else [*head, rigor]
    row = (
        f"| drift: declared=3 changed=3 undeclared=- flags=0 excl=5e6f7a8b9c0d on={CAND} | "
        "git diff --name-only 1a2b3c4d5e6f | 0 | 3 paths |"
    )
    return "RESULT: PASS\n" + "\n".join(head) + f"\n\n## Gate\n{row}\n\n## Defects\n"


def run_finding_tags(tmp_path: Path, text: str) -> tuple[int, str]:
    f = tmp_path / "qa.md"
    f.write_text(text, encoding="utf-8")
    cmd = [sys.executable, "-B", str(FINDING_TAGS), "check", str(f)]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return p.returncode, p.stdout + p.stderr


def test_rigor_line_on_line_5_of_a_qa_report_passes_finding_tags(tmp_path: Path) -> None:
    code, out = run_finding_tags(tmp_path, qa_text(rigor_early=False))
    assert code == 0, out


def test_rigor_line_before_base_pushes_it_out_of_the_window_and_is_refused(tmp_path: Path) -> None:
    code, out = run_finding_tags(tmp_path, qa_text(rigor_early=True))
    assert "no BASE line" in out, out
    assert code == 4, out


def test_rigor_line_on_line_4_of_a_judge_verdict_passes_finding_tags(tmp_path: Path) -> None:
    text = (
        "TOTALS: UPHELD 1 / REJECTED 0 / UNVERIFIED 0 — round 1/3\n"
        "CANDIDATE: files:0f1e2d3c4b5a6978 n=1 excludes=- paths=d.md\nCARRIED: -\n"
        f"RIGOR: gated unit={UNIT} by=default on=2026-10-14\n\n## Claims\n"
    )
    code, out = run_finding_tags(tmp_path, text)
    assert code == 0, out


# ---------------------------------------------------------------- prose pins


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_quality_gates_states_who_selects() -> None:
    assert "No agent selects, raises or lowers a level" in read(
        QUALITY_GATES
    ), "RG1 sentence missing"


def test_doubt_decides_claims_not_rigor() -> None:
    for p in (QUALITY_GATES, JUDGE):
        assert "Doubt decides each claim of an audit that was assigned" in read(p), str(p)


def test_claude_md_labels_judge_and_qa_as_assigned_by_the_owner() -> None:
    label = "**Rigor:** the judge and QA are `gated`, assigned by the owner"
    assert label in read(CLAUDE_MD), "CLAUDE.md label missing"
    assert "`rigor:<scope>/<item>` row in `WAIVERS.md`" in read(CLAUDE_MD), "CLAUDE.md spelling"


def test_boundary_qa_copies_the_rigor_line() -> None:
    assert "RIGOR: gated unit=" in read(
        BOUNDARY_QA
    ), "boundary-qa.md does not say to copy the RIGOR line"


def test_briefs_and_agents_state_the_line_order() -> None:
    needle = "RESULT, CANDIDATE, CARRIED, BASE, RIGOR"
    for p in (TEMPLATE, BOUNDARY_QA, QA_GUIDE):
        assert needle in read(p), str(p)
    assert "TOTALS, CANDIDATE, CARRIED, RIGOR" in read(JUDGE), "judge order missing"
    assert "TOTALS, CANDIDATE, CARRIED, RIGOR" in read(
        VERDICT_SCHEMA
    ), "verdict-schema order missing"


def test_rigor_is_a_separate_axis_from_team_size() -> None:
    text = read(SKILL)
    assert "The six answers never select a level" in text, "I5 sentence missing from SKILL.md"
    assert (
        "an exception to the single-agent cap above" in text
    ), "I5 does not name the sentence it qualifies"


def test_unclear_output_is_treated_as_an_audited_decision() -> None:
    sentence = "When it is unclear whether an output is an audited decision, treat it as one"
    assert sentence in read(SKILL), "SKILL.md Step 5"
    assert sentence in read(QUALITY_GATES), "quality-gates 3-10"


def test_owner_classifies_and_lowering_needs_the_users_approval() -> None:
    for p in (SKILL, QUALITY_GATES):
        text = read(p)
        assert "an agent never classifies a unit as `other`" in text, str(p)
        assert "needs the user's approval" in text, str(p)


def test_gap_email_is_client_facing_text_in_step_5_and_in_3_10() -> None:
    skill, qg = read(SKILL), read(QUALITY_GATES)
    assert "A gap email is client-facing text and so is one" in skill, "SKILL.md Step 5"
    assert "a gap email is client-facing text, so it is one" in qg, "quality-gates 3-10"
    assert "A gap email that only lists missing documents is not one" not in skill, "old exemption"
    assert (
        "money, eligibility, compliance and client-facing text" in skill
    ), "class wording in Step 5"
    assert "money, eligibility, compliance and client-facing text" in qg, "class wording in 3-10"
    assert "third party will rely on" not in skill, "added qualifier in Step 5"
    assert "third party will rely on" not in qg[qg.index("### 3-10") :], "added qualifier in 3-10"


def test_reviewer_roles_the_user_asked_for_are_not_caught() -> None:
    assert "Roles the user asked for" in read(TEAM_PATTERNS), "I10 scope sentence missing"


def test_downgrade_lifetime_and_cost_are_stated() -> None:
    qg = read(QUALITY_GATES)
    assert (
        "never one run" in qg and "red until a closure unit deletes the row" in qg
    ), "3-10 lifetime text"


def test_final_report_names_every_light_unit() -> None:
    assert "RIGOR: no unit ran light" in read(QUALITY_GATES), "final report line"


def test_downgrade_row_is_committed_by_its_own_gated_unit() -> None:
    sentence = "committed by a unit of its own that declares `WAIVERS.md` and nothing else and runs `gated`"
    assert sentence in read(QUALITY_GATES), "RG5 sentence missing"


def test_known_limits_say_what_is_enforced_and_what_is_not() -> None:
    qg = read(QUALITY_GATES)
    assert "boundary QA runs it too" in qg, "who runs the script"
    assert (
        "a rule, and the script enforces only that a light unit changes no ledger" in qg
    ), "RG5 limit"
    assert "a whole forged QA report is not told from a real one" in qg, "forged report limit"
    assert "reads shape, not the verdict of a report beyond RESULT: PASS" in qg, "FAIL report limit"


def test_master_orchestrator_phase_2_steps_are_numbered_once_and_use_unit() -> None:
    text = read(ORCHESTRATOR)
    phase2 = text[text.index("### Phase 2") : text.index("### Phase 3")]
    numbers = [int(m.group(1)) for m in re.finditer(r"(?m)^(\d+)\. ", phase2)]
    assert numbers == sorted(set(numbers)) and numbers[-1] == len(
        numbers
    ), f"Phase 2 numbering {numbers}"
    assert "master-finhub-unit/{unit}" in text, "commit step uses the unit variable"
    assert "{id}" not in text, "undefined {id} variable"


def test_orchestrator_table_parses_and_names_the_owner() -> None:
    # reads the live table; a renewal of WAIVERS.md cannot change it
    o = read(ORCHESTRATOR)
    assert (
        "| master-finhub-unit | other | light | owner:daniel | 2026-10-28 |" in o
    ), "repo rigor row"
    today = date(2026, 10, 28)  # the live row is dated 2026-10-28
    _, out = MOD.check_text("o", o, "-", None, "master-finhub-unit/OR-S8", None, [], [], today)
    assert "EFFECTIVE: master-finhub-unit/OR-S8 light" in "\n".join(out), out


CHANGED = [
    QUALITY_GATES, SKILL, TEMPLATE, TEAM_PATTERNS, QA_GUIDE, BOUNDARY_QA, JUDGE, VERDICT_SCHEMA, ORCHESTRATOR,
    CLAUDE_MD, SCRIPT, Path(__file__),
]  # fmt: skip


def test_changed_files_carry_the_attribution_line() -> None:
    for p in CHANGED:
        assert "adapted from references/openrig/" in read(p), str(p)


def test_changed_files_have_no_hangul() -> None:
    hangul = re.compile(f"[{chr(0xAC00)}-{chr(0xD7A3)}]")
    for p in CHANGED:
        text = read(p)
        if (
            p == ORCHESTRATOR
        ):  # the file keeps Korean phase markers by convention; only the new section is checked
            m = re.search(r"(?ms)^## Rigor\n.*?(?=^## |\Z)", text)
            assert m, "no ## Rigor section"
            text = m.group(0)
        if (
            p == CLAUDE_MD
        ):  # the file keeps Korean headings by convention; only the new lines are checked
            text = "\n".join(
                x for x in text.splitlines() if x.startswith("**Rigor:**") or "OR-S8" in x
            )
        assert not hangul.search(text), f"Hangul in {p}"


def test_rigor_table_is_shown_in_a_real_place_in_step_6() -> None:
    # BC2: the report of Step 6 item 7 exists, and SKILL.md and 3-10 point at it
    skill = read(SKILL)
    step6 = skill[skill.index("### Step 6: Verify and test") : skill.index("### Step 7")]
    assert re.search(r"(?m)^7\. \*\*Rigor table\*\*: ", step6), "Step 6 item 7 missing"
    assert "Show the table in the report of Step 6 item 7." in skill, "SKILL.md pointer"
    assert "report of `SKILL.md` Step 6 item 7" in read(QUALITY_GATES), "3-10 pointer"
    assert "Step 6 summary" not in skill + read(QUALITY_GATES), "no summary that does not exist"


def test_known_limits_name_the_three_unchecked_inputs_and_the_stale_receipt() -> None:
    # BC4 and BC1
    qg = read(QUALITY_GATES)
    assert "A wrong PREV that is not `-`" in qg, "wrong PREV limit"
    assert "The caller chooses the scope a unit is filed under" in qg, "scope choice limit"
    assert "A table receipt licenses any lowering of its scope until it expires" in qg, "receipt"
    assert "a stale receipt row costs a closure unit" in qg, "stale receipt cost"


# ---- OR-S8 follow-up: spelling of CHANGED, stale receipts, the clock, residual 13


def test_a_case_variant_of_the_ledger_path_is_the_ledger(tmp_path: Path) -> None:
    for spelling in ("waivers.md", "Waivers.MD", "./waivers.md", "docs/../WAIVERS.md"):
        code, out = run(tmp_path, unit="note-draft/n1", changed=(spelling,))
        assert "a light unit must not change the ledger" in out, f"case variant: {spelling}: {out}"
        assert code == 4, out


def test_table_and_ledger_in_one_commit_is_refused_for_any_spelling(tmp_path: Path) -> None:
    for a, b in (("ORCH.md", "waivers.md"), ("./orch.md", "./WAIVERS.md")):
        code, out = run(tmp_path, prev=orch(), changed=(a, b), reports=(report(),))
        msg = "the Rigor table and the ledger change in one commit"
        assert msg in out, f"one commit: {a} {b}: {out}"
        assert code == 4, out


def test_a_changed_path_outside_the_repository_is_refused(tmp_path: Path) -> None:
    for spelling in (
        "/work/repo/WAIVERS.md",
        "C:/work/repo/WAIVERS.md",
        "\\\\host\\share\\WAIVERS.md",
        "../WAIVERS.md",
        "..",
    ):
        code, out = run(tmp_path, changed=(spelling,), reports=(report(),))
        assert (
            "CHANGED:1:" in out and "is not a path inside the repository" in out
        ), f"outside: {spelling}: {out}"
        assert code == 4, out


def test_an_absolute_ledger_argument_matches_a_root_relative_entry() -> None:
    _, out = MOD.check_text(
        "orch.md", orch(), "/work/repo/WAIVERS.md", LEDGER_HEAD, "note-draft/n1", None,
        ["WAIVERS.md"], [], TODAY,
    )  # fmt: skip
    assert "a light unit must not change the ledger" in "\n".join(out), f"absolute argument: {out}"


def test_a_root_relative_entry_deeper_than_the_argument_matches() -> None:
    _, out = MOD.check_text(
        "orch.md", orch(), "WAIVERS.md", LEDGER_HEAD, "note-draft/n1", None,
        ["tools/WAIVERS.md"], [], TODAY,
    )  # fmt: skip
    assert "a light unit must not change the ledger" in "\n".join(out), f"deeper entry: {out}"


def test_an_absolute_orchestrator_argument_matches_a_root_relative_entry() -> None:
    _, out = MOD.check_text(
        "/work/repo/orch.md", orch(), "WAIVERS.md", LEDGER_HEAD, UNIT, orch(),
        ["orch.md", "WAIVERS.md"], [("r.md", report())], TODAY,
    )  # fmt: skip
    msg = "the Rigor table and the ledger change in one commit"
    assert msg in "\n".join(out), f"absolute orchestrator argument: {out}"


def test_an_entry_that_is_only_the_end_of_the_argument_is_not_the_ledger(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="note-draft/n1", changed=("ers.md",))
    assert "a light unit must not change the ledger" not in out, f"argument-tail match: {out}"
    assert code == 0, out


def test_an_entry_that_only_ends_with_the_argument_is_not_the_ledger(tmp_path: Path) -> None:
    code, out = run(tmp_path, unit="note-draft/n1", changed=("mywaivers.md",))
    assert "a light unit must not change the ledger" not in out, f"path-tail match: {out}"
    assert code == 0, out


def test_a_receipt_row_for_a_removed_scope_is_refused_at_the_next_commit(tmp_path: Path) -> None:
    gone = ROWS.replace("| note-draft | other | light | owner:daniel | 2026-10-14 |\n", "")
    ledger = LEDGER_HEAD + dg(unit="note-draft/table", expires="2026-12-01")
    code, out = run(
        tmp_path, table=orch(gone), prev=orch(gone), ledger=ledger, reports=(report(),),
        today=date(2026, 10, 20),
    )  # fmt: skip
    assert (
        "downgrade waiver names no scope and item of the Rigor table" in out
    ), f"removed-scope receipt is refused: {out}"
    assert code == 4, out


def test_a_receipt_row_for_a_lowered_scope_is_clean_for_the_script_and_red_for_the_ledger(
    tmp_path: Path,
) -> None:
    ledger = LEDGER_HEAD + dg(unit="client-email/table", expires="2026-10-15")
    late = date(2026, 10, 20)
    code, out = run(
        tmp_path, table=orch(LOWERED), prev=orch(LOWERED), ledger=ledger, unit="client-email/x",
        today=late,
    )  # fmt: skip
    assert code == 0, f"lowered-scope receipt stays clean for rigor_check: {out}"
    lcode, lines = MOD.wl.check_text("WAIVERS.md", ledger, late)
    assert lcode == 4 and "EXPIRED" in "\n".join(
        lines
    ), f"lowered-scope receipt is red for the ledger: {lines}"


def test_rg3_says_which_check_goes_red_for_a_stale_receipt() -> None:
    qg = read(QUALITY_GATES)
    kept = "`rigor_check.py` stays clean, and `waiver_ledger.py check` is red from the day after `expires`"
    assert kept in qg, "RG3 names the lowered-scope case"
    gone = "refuses the row as naming no scope of the table (exit 4), even before `expires`"
    assert gone in qg, "RG3 names the removed-scope case"
    assert "stale like any other row" not in qg, "RG3 old wording gone"
    assert "a stale receipt row costs a closure unit" in qg, "RG3 cost sentence kept"


def test_3_10_states_the_local_calendar_date_clock() -> None:
    qg = read(QUALITY_GATES)
    sec = qg[qg.index("### 3-10.") : qg.index("## 4. Honest reporting")]
    assert "datetime.now().astimezone().date()" in read(SCRIPT), "script clock call"
    assert "datetime.now().astimezone().date()" in sec, "3-10 names the rigor_check clock call"
    assert "the process time zone is the only clock input" in sec, "3-10 clock limit"
    ledger = REPO / "skills/finhub-harness/scripts/waiver_ledger.py"
    assert "date.today()" in read(ledger), "ledger clock call"
    assert "(`date.today()`)" in qg[qg.index("### 3-9.") : qg.index("### 3-10.")], "3-9 clock call"


def test_the_path_spelling_limit_is_stated_in_3_10() -> None:
    qg = read(QUALITY_GATES)
    sec = qg[qg.index("### 3-10.") : qg.index("## 4. Honest reporting")]
    assert "Path spelling of CHANGED" in sec, "path spelling bullet"
    for named in (
        "a symbolic or hard link",
        "`WAIVER~1.MD`",
        "`core.quotePath`",
        "`--no-renames`",
        "byte order mark",
        "case-sensitive file system",
    ):
        assert named in sec, f"unclosed spelling named: {named}"


def test_the_residuals_bullet_does_not_call_route_13_accepted() -> None:
    qg = read(QUALITY_GATES)
    start = qg.index("- Accepted residuals (Daniel")
    bullet = qg[start : qg.index("\n", start)]
    assert (
        "Route 13 was found by the fourth boundary-qa run and is not accepted" in bullet
    ), "route 13 is not called accepted"
    assert (
        "and route 13 by the fourth boundary-qa run, and Daniel accepted them" not in bullet
    ), "old route 13 wording gone"
    assert "OR-D4-R13" in bullet, "route 13 names its removed ledger row"
