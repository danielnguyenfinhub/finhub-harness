# adapted from references/openrig/docs/reference/wave-sdlc.md:54-62 (Apache-2.0)
"""Proof for OR-D4 round 4: skills/finhub-harness/scripts/finding_tags.py, the prose of quality-gates.md
section 3-8 and qa-agent-guide.md section 7-10, and the drift commands run in a temporary git repository.
Each refusal test asserts the checker's own message before the exit code, so the rule that stops firing
fails at that message."""

from __future__ import annotations

import hashlib
import importlib.machinery
import os
import re
import subprocess
import sys
import types
import unicodedata
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/finding_tags.py"
QA_GUIDE = "skills/finhub-harness/references/qa-agent-guide.md"
SRC = REPO / "references/openrig/docs/reference/wave-sdlc.md"
CAND = "git:1a2b3c4d5e6f+0f1e2d3c4b5a6978"
OTHER = "git:9f8e7d6c5b4a+0f1e2d3c4b5a6978"
BASE_SHA = "1a2b3c4d5e6f"
EXCL = "5e6f7a8b9c0d"
HEAD = (
    f"CANDIDATE: {CAND} n=214 excludes=_workspace/\nBASE: git:{BASE_SHA} excl={EXCL}\nCARRIED: -\n"
)


def drift(
    on: str = CAND,
    undeclared: str = "-",
    declared: int = 3,
    changed: int = 3,
    flags: int = 0,
    excl: str = EXCL,
) -> str:
    return (
        f"| drift: declared={declared} changed={changed} undeclared={undeclared} flags={flags} excl={excl} "
        f'on={on} | git -C "$REPO" diff -z --no-renames --name-only {BASE_SHA} | 0 | 3 paths |\n'
    )


def qa(verdict: str = "PASS", body: str = "", rows: str | None = None, head: str = HEAD) -> str:
    rows = drift() if rows is None else rows
    return f"RESULT: {verdict}\n{head}\n## Gate\n{rows}\n## Defects\n{body}"


def run(tmp_path: Path, text: str, name: str = "report.md") -> tuple[int, str]:
    """Runs the checker with no option: the one path there is (every refusal exits 4)."""
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "check", str(f)],
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode, p.stdout + p.stderr


def load_checker() -> Any:
    loader = importlib.machinery.SourceFileLoader("finding_tags_under_test", str(SCRIPT))
    mod = types.ModuleType(loader.name)
    loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- positive controls


def test_qa_pass_with_one_drift_row_is_accepted(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa())
    assert code == 0, out


def test_lesson_with_one_context_gap_is_accepted(tmp_path: Path) -> None:
    text = "LESSON | layer: routing | cause: context-gap | evidence: a.md:1 - x | fix: b.md - y\n"
    code, out = run(tmp_path, text)
    assert code == 0, out


@pytest.mark.parametrize(
    "reason",
    [
        "candidate moved during QA",
        "candidate differs from the brief",
        "missing tool: pytest",
        "no git",
    ],
)
def test_process_fail_with_controlled_reason_needs_no_defect_or_drift(
    tmp_path: Path, reason: str
) -> None:
    code, out = run(tmp_path, f"RESULT: FAIL — {reason}\n{HEAD}\n## Gate\n")
    assert code == 0, out


def test_process_fail_with_reason_that_only_starts_like_a_listed_one_is_refused(
    tmp_path: Path,
) -> None:
    code, out = run(tmp_path, f"RESULT: FAIL — no gitignore rule\n{HEAD}\n## Gate\n")
    assert "FAIL reason is not a process reason" in out, out
    assert code == 4, out


def test_fenced_lesson_without_cause_is_not_a_record(tmp_path: Path) -> None:
    text = (
        "```\nLESSON | layer: routing | evidence: a.md:1 - x | fix: b.md - y\n```\n"
        "LESSON | layer: routing | cause: judgment-gap | evidence: a.md:1 - x | fix: b.md - y\n"
    )
    code, out = run(tmp_path, text)
    assert "LESSON without exactly one cause" not in out, out
    assert code == 0, out


def test_judge_verdict_with_tagged_rejected_row_is_accepted(tmp_path: Path) -> None:
    text = (
        "TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
        "| A4 | REJECTED | references/dify/x.py:30 | import block | PING is at :61 cause: judgment-gap |\n"
    )
    code, out = run(tmp_path, text)
    assert code == 0, out


def test_numbered_defects_with_cause_and_location_are_accepted(tmp_path: Path) -> None:
    body = "1. runtime/loop.py:54 — passes `message`, schema declares `text`. cause: judgment-gap\n"
    code, out = run(tmp_path, qa("FAIL", body))
    assert code == 0, out


def test_fenced_drift_row_does_not_satisfy_d1(tmp_path: Path) -> None:
    text = f"RESULT: PASS\n{HEAD}\n## Gate\n```\n{drift()}```\n## Defects\n"
    code, out = run(tmp_path, text)
    assert "drift row missing or repeated (0 found)" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- T1-T3: cause tags and defect locations


def test_lesson_without_cause_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, "LESSON | layer: routing | evidence: a.md:1 - x | fix: b.md - y\n")
    assert "LESSON without exactly one cause tag" in out
    assert code == 4, out


def test_lesson_with_two_causes_is_refused(tmp_path: Path) -> None:
    text = "LESSON | layer: routing | cause: context-gap | cause: judgment-gap | evidence: a.md:1 - x | fix: b.md - y\n"
    code, out = run(tmp_path, text)
    assert "LESSON without exactly one cause tag" in out
    assert code == 4, out


def test_unknown_cause_value_is_refused(tmp_path: Path) -> None:
    code, out = run(
        tmp_path,
        "LESSON | layer: routing | cause: context | evidence: a.md:1 - x | fix: b.md - y\n",
    )
    assert "LESSON without exactly one cause tag" in out
    assert code == 4, out


def test_defect_row_without_cause_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("FAIL", "- defect: src/x.py:4 expected 1 actual 2\n"))
    assert "defect row without exactly one cause tag" in out
    assert code == 4, out


def test_defect_row_without_location_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("FAIL", "- defect: none cause: context-gap\n"))
    assert "defect row without a file:line location" in out
    assert code == 4, out


def test_pass_with_defect_row_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", "- defect: src/x.py:4 cause: judgment-gap\n"))
    assert "PASS with defect rows (1)" in out
    assert code == 4, out


def test_numbered_defect_without_cause_is_refused(tmp_path: Path) -> None:
    body = "- defect: src/a.py:1 cause: judgment-gap\n2. src/b.py:2 — untagged item\n"
    code, out = run(tmp_path, qa("FAIL", body))
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


def test_rejected_row_without_cause_is_refused(tmp_path: Path) -> None:
    text = (
        "TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 0 — round 2/3\n"
        "CANDIDATE: files:0f1e2d3c4b5a6978 n=1 excludes=- paths=_workspace/x.md\n"
        "CARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
        "| A4 | REJECTED | references/dify/x.py:30 | import block | PING is at :61 |\n"
    )
    code, out = run(tmp_path, text)
    assert "REJECTED row without exactly one cause tag" in out
    assert code == 4, out


def test_formatted_rejected_cells_need_a_cause(tmp_path: Path) -> None:
    text = (
        "TOTALS: UPHELD 6 / REJECTED 3 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
        "| A4 | **REJECTED** | x.py:1 | a | b |\n"
        "| A5 | `REJECTED` | x.py:2 | a | b |\n"
        "| A6 | rejected | x.py:3 | a | b |\n"
    )
    code, out = run(tmp_path, text)
    assert out.count("REJECTED row without exactly one cause tag") == 3, out
    assert code == 4, out


@pytest.mark.parametrize("cell", ["REJECTED.", "REJECTED:", "Rejected,"])
def test_punctuated_rejected_cells_need_a_cause(tmp_path: Path, cell: str) -> None:
    text = (
        "TOTALS: UPHELD 0 / REJECTED 1 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
        f"| A4 | {cell} | x.py:1 | a | b |\n"
    )
    code, out = run(tmp_path, text)
    assert "REJECTED row without exactly one cause tag" in out, out
    assert code == 4, out


@pytest.mark.parametrize("cell", ["REJECTED.", "REJECTED:", "Rejected,"])
def test_punctuated_rejected_cells_reconcile_with_totals(tmp_path: Path, cell: str) -> None:
    text = (
        "TOTALS: UPHELD 0 / REJECTED 0 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
        f"| A4 | {cell} | x.py:1 | a | b |\n"
    )
    code, out = run(tmp_path, text)
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out


def test_rejected_word_anywhere_in_a_cell_is_a_verdict(tmp_path: Path) -> None:
    # Judge r4 Q3(a), amended: the word counts wherever it sits in a cell, so a reason that says "rejected" needs a tag.
    head = (
        "TOTALS: UPHELD 1 / REJECTED 1 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
    )
    code, out = run(tmp_path, head + "| A2 | UPHELD | x.py:1 | a | not rejected by the gate |\n")
    assert "REJECTED row without exactly one cause tag" in out, out
    assert code == 4, out
    code, out = run(
        tmp_path,
        head + "| A2 | UPHELD | x.py:1 | a | not rejected by the gate cause: judgment-gap |\n",
        name="tagged.md",
    )
    assert code == 0, out


# Judge r3 REJECTED: the five fail-open forms (P-3 j3-j6, j11). Each row is refused untagged, and TOTALS 0
# is refused as a mismatch; tagged with TOTALS 1 the same row is accepted.
FAIL_OPEN = {
    "symbol": "| A4 | ✗ REJECTED | x.py:1 | a{tag} | b |",
    "label": "| A4 | **Verdict:** REJECTED | x.py:1 | a{tag} | b |",
    "strike": "| A4 | ~~REJECTED~~ | x.py:1 | a{tag} | b |",
    "no-pipe": "A4 | REJECTED | x.py:1 | a{tag} | b",
    "either": "| A4 | UNVERIFIED / REJECTED | x.py:1 | a{tag} | b |",
}


@pytest.mark.parametrize("form", list(FAIL_OPEN), ids=list(FAIL_OPEN))
def test_fail_open_rejected_forms_are_counted(tmp_path: Path, form: str) -> None:
    def report(total: int, tag: str) -> str:
        return (
            "TOTALS: UPHELD 0 / REJECTED " + str(total) + " / UNVERIFIED 0 — round 1/3\n"
            f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
            "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
            + FAIL_OPEN[form].format(tag=tag)
            + "\n"
        )

    code, out = run(tmp_path, report(0, ""))
    assert "REJECTED row without exactly one cause tag" in out, out
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out
    code, out = run(tmp_path, report(1, " cause: judgment-gap"), name="tagged.md")
    assert code == 0, out


def test_totals_mismatch_is_refused(tmp_path: Path) -> None:
    text = f"TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 0 — round 1/3\nCANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n"
    code, out = run(tmp_path, text)
    assert "TOTALS says REJECTED 1 but the tables hold 0 REJECTED cell(s)" in out, out
    assert code == 4, out


def test_totals_line_is_not_counted_as_a_row(tmp_path: Path) -> None:
    # The TOTALS line is not a table row, even when it holds a pipe: its word "rejected" is not a verdict cell.
    text = (
        "TOTALS: UPHELD 1 | the word rejected sits here / REJECTED 0 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n"
    )
    code, out = run(tmp_path, text)
    assert code == 0, out


def test_guardrail_rejected_cell_needs_a_cause(tmp_path: Path) -> None:
    text = (
        "TOTALS: UPHELD 0 / REJECTED 1 / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| slice | G1 fees | G2 borrow |\n|---|---|---|\n"
        "| 11 | PASS 5 bps default | REJECTED shorts free |\n"
    )
    code, out = run(tmp_path, text)
    assert "REJECTED row without exactly one cause tag" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- T4 and BC7: bare FAIL and process reasons


def test_bare_fail_without_defect_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("FAIL", ""))
    assert "bare FAIL with no defect row" in out
    assert code == 4, out


def test_process_fail_with_uncontrolled_reason_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, f"RESULT: FAIL — builder fault in y.py\n{HEAD}\n## Gate\n")
    assert "FAIL reason is not a process reason" in out
    assert code == 4, out


def test_pass_with_reason_suffix_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS").replace("RESULT: PASS", "RESULT: PASS — looks fine", 1))
    assert "PASS line carries a reason" in out
    assert code == 4, out


# ---------------------------------------------------------------- D1-D5 and BC5: drift row


def test_pass_without_drift_row_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=""))
    assert "drift row missing or repeated" in out
    assert code == 4, out


def test_repeated_drift_row_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift() + drift()))
    assert "drift row missing or repeated (2 found)" in out
    assert code == 4, out


def test_drift_row_from_another_candidate_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(on=OTHER)))
    assert "drift row names another candidate" in out
    assert code == 4, out


def test_pass_with_undeclared_path_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(undeclared="src/extra.py")))
    assert "PASS with undeclared paths" in out
    assert code == 4, out


def test_fail_with_undeclared_path_is_accepted_when_defect_is_caused(tmp_path: Path) -> None:
    body = "- defect: src/extra.py:1 not in Declared cause: judgment-gap\n"
    code, out = run(tmp_path, qa("FAIL", body, rows=drift(undeclared="src/extra.py")))
    assert code == 0, out


def test_qa_report_without_candidate_line_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, f"RESULT: PASS\nCARRIED: -\n## Gate\n{drift()}")
    assert "no CANDIDATE line naming a git: or files: tree" in out
    assert code == 4, out


def test_files_candidate_cannot_pass(tmp_path: Path) -> None:
    head = "CANDIDATE: files:0f1e2d3c4b5a6978 n=1 excludes=-\nBASE: git:1a2b3c4d5e6f excl=5e6f7a8b9c0d\nCARRIED: -\n"
    code, out = run(tmp_path, qa("PASS", rows=drift(on="files:0f1e2d3c4b5a6978"), head=head))
    assert "PASS needs a git: candidate" in out
    assert code == 4, out


def test_files_token_on_drift_row_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(on="files:0f1e2d3c4b5a6978")))
    assert "drift row on= is not a git: token" in out
    assert code == 4, out


def test_unborn_token_on_drift_row_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(on="git:unborn+0f1e2d3c4b5a6978")))
    assert "drift row on= is not a git: token" in out
    assert code == 4, out


def test_uppercase_hex_on_drift_row_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(on="git:1A2B3C4D5E6F+0f1e2d3c4b5a6978")))
    assert "drift row on= is not a git: token" in out
    assert code == 4, out


def test_raw_space_in_undeclared_is_malformed(tmp_path: Path) -> None:
    code, out = run(
        tmp_path,
        qa("FAIL", "- defect: a.py:1 cause: judgment-gap\n", rows=drift(undeclared="a.py b.py")),
    )
    assert "drift row malformed" in out, out
    assert code == 4, out


def test_raw_non_ascii_path_is_malformed(tmp_path: Path) -> None:
    code, out = run(
        tmp_path,
        qa("FAIL", "- defect: a.py:1 cause: judgment-gap\n", rows=drift(undeclared="café.py")),
    )
    assert "drift row malformed" in out, out
    assert code == 4, out


def test_percent_encoded_paths_are_accepted(tmp_path: Path) -> None:
    code, out = run(
        tmp_path,
        qa(
            "FAIL",
            "- defect: a.py:1 cause: judgment-gap\n",
            rows=drift(undeclared="caf%C3%A9.py,new%20file.py"),
        ),
    )
    assert code == 0, out


def test_undeclared_list_longer_than_changed_is_refused(tmp_path: Path) -> None:
    code, out = run(
        tmp_path,
        qa(
            "FAIL",
            "- defect: a.py:1 cause: judgment-gap\n",
            rows=drift(undeclared="a.py,b.py", changed=1),
        ),
    )
    assert "undeclared list longer than changed=1" in out, out
    assert code == 4, out


def test_pass_with_index_flags_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(flags=1)))
    assert "PASS with index flags set (1 path(s)" in out, out
    assert code == 4, out


def test_excl_digest_that_differs_from_base_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift(excl="0123456789ab")))
    assert "differs from the Base line" in out, out
    assert code == 4, out


def test_pass_without_base_line_is_refused(tmp_path: Path) -> None:
    head = f"CANDIDATE: {CAND} n=214 excludes=_workspace/\nCARRIED: -\n"
    code, out = run(tmp_path, qa("PASS", head=head))
    assert "no BASE line" in out, out
    assert code == 4, out


def test_base_line_without_exclude_digest_is_refused(tmp_path: Path) -> None:
    head = f"CANDIDATE: {CAND} n=214 excludes=_workspace/\nBASE: git:{BASE_SHA}\nCARRIED: -\n"
    code, out = run(tmp_path, qa("PASS", head=head))
    assert "no BASE line" in out, out
    assert code == 4, out


def test_encoder_command_in_guide_encodes_space_and_non_ascii() -> None:
    text = (REPO / QA_GUIDE).read_text(encoding="utf-8")
    cmd = re.search(
        r"python3 -c '(import sys, urllib\.parse; print\(urllib\.parse\.quote\(sys\.argv\[1\], "
        r"safe=\"/\._-~\"\)\))' PATH",
        text,
    )
    assert cmd, "encoder command missing from qa-agent-guide 7-10"
    for name, want in (("café.py", "caf%C3%A9.py"), ("new file.py", "new%20file.py")):
        p = subprocess.run(
            [sys.executable, "-c", cmd.group(1), name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        assert p.stdout.strip() == want, p.stdout


# ---------------------------------------------------------------- one path: every refusal exits 4 (Daniel ruled enforce)


def test_default_path_refuses_a_drift_row(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=""))
    assert "drift row missing or repeated (0 found)" in out, out
    assert "ADVISORY" not in out, out
    assert code == 4, out


def test_default_path_still_refuses_cause_tags(tmp_path: Path) -> None:
    code, out = run(tmp_path, "LESSON | layer: routing | evidence: a.md:1 - x | fix: b.md - y\n")
    assert "LESSON without exactly one cause tag" in out, out
    assert code == 4, out


def test_no_option_turns_a_drift_refusal_into_a_pass(tmp_path: Path) -> None:
    # The advisory switch and its option are gone: any option is a usage error, so no run can exit 0 on a drift refusal.
    f = tmp_path / "report.md"
    f.write_text(qa("PASS", rows=""), encoding="utf-8")
    for flag in ("--drift-gate=advisory", "--drift-gate=enforce"):
        p = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "check", flag, str(f)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert p.returncode == 2, p.stdout + p.stderr
        assert "usage: finding_tags.py check FILE" in p.stderr, p.stderr
    assert "DRIFT_GATE" not in SCRIPT.read_text(encoding="utf-8")  # no switch constant is shipped


# ---------------------------------------------------------------- exit codes


def test_file_with_no_record_exits_2(tmp_path: Path) -> None:
    code, out = run(tmp_path, "just prose, no record here\n")
    assert "no record in file" in out
    assert code == 2, out


def test_no_arguments_exits_2() -> None:
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert p.returncode == 2, p.stderr


def test_missing_file_exits_2(tmp_path: Path) -> None:
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "check", str(tmp_path / "absent.md")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "cannot read" in p.stderr, p.stderr
    assert p.returncode == 2, p.stderr


def test_refusal_exits_4_not_3(tmp_path: Path) -> None:
    code, out = run(tmp_path, "LESSON | layer: routing | evidence: a.md:1 - x | fix: b.md - y\n")
    assert "LESSON without exactly one cause tag" in out
    assert code == 4, out


# ---------------------------------------------------------------- no digest exemption (judge N12, S-x)


def test_no_digest_exemption_is_shipped() -> None:
    # The legacy digest list is gone and the checker has no exemption: a record is checked whatever its age.
    assert not (REPO / "skills/finhub-harness/scripts/finding_tags_legacy.sha256").exists()
    assert "hashlib" not in SCRIPT.read_text(encoding="utf-8")


def test_pre_patch_shaped_record_is_refused_without_any_list(tmp_path: Path) -> None:
    # A pre-patch QA report: no drift row, no BASE line. It is refused by the default path, not exempt.
    old = (
        "RESULT: PASS\nCANDIDATE: "
        + CAND
        + " n=1 excludes=_workspace/\nCARRIED: -\n## Gate\n## Defects\n"
    )
    code, out = run(tmp_path, old)
    assert "drift row missing or repeated (0 found)" in out, out
    assert code == 4, out


def test_pre_patch_judge_record_is_refused_by_its_cause_rule_by_default(tmp_path: Path) -> None:
    # Decision 5: an old judge record is refused by the REJECTED cause rule (not by a drift rule).
    old = (
        "TOTALS: UPHELD 9 / REJECTED 1 / UNVERIFIED 0 — round 2/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n"
        "| A4 | REJECTED | x.py:1 | a | b |\n"
    )
    code, out = run(tmp_path, old)
    assert "REJECTED row without exactly one cause tag" in out, out
    assert "drift row" not in out, out
    assert code == 4, out


def test_pre_patch_lesson_record_is_refused_by_its_cause_rule_by_default(tmp_path: Path) -> None:
    # Decision 5: an old LESSON line is refused by the cause rule T1 on the default path.
    code, out = run(tmp_path, "LESSON | layer: routing | evidence: a.md:1 - x | fix: b.md - y\n")
    assert "LESSON without exactly one cause tag" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- BC19, BC22, BC24, BC25: drift commands in a temp repo


def drift_block() -> str:
    sec = (
        (REPO / QA_GUIDE).read_text(encoding="utf-8").split("### 7-10. Drift from the brief", 1)[1]
    )
    return str(next(b for b in re.findall(r"```bash\n(.*?)```", sec, re.DOTALL) if "diff -z" in b))


def git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    ).stdout


def run_block(repo: Path, base: str) -> set[str]:
    script = re.sub(r"^BASE=.*$", f"BASE={base}", drift_block(), flags=re.MULTILINE)
    p = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, "REPO": str(repo)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert p.returncode == 0, p.stderr
    return set(p.stdout.splitlines())


def exclude_digest(repo: Path) -> str:
    return hashlib.sha256((repo / ".git" / "info" / "exclude").read_bytes()).hexdigest()[:12]


def make_repo(tmp: Path) -> tuple[Path, str]:
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / ".gitignore").write_text("_workspace/\ndist/\n*.pyc\n", encoding="utf-8")
    (repo / "declared.py").write_text("a\n", encoding="utf-8")
    (repo / "old.py").write_text("o\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").strip()[:12]
    git(repo, "mv", "old.py", "renamed.py")
    (repo / "builder.py").write_text("b\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "builder commit after Base was recorded")
    (repo / "new file.py").write_text("n\n", encoding="utf-8")
    (repo / "café.py").write_text("c\n", encoding="utf-8")
    (repo / "decl.py\ndecl.py").write_text("d\n", encoding="utf-8")
    (repo / "evil\nname.py").write_text("e\n", encoding="utf-8")
    (repo / "dist").mkdir()
    (repo / "dist" / "hidden.py").write_text("h\n", encoding="utf-8")
    (repo / "c.pyc").write_text("x\n", encoding="utf-8")
    (repo / "_workspace").mkdir()
    (repo / "_workspace" / "rep.md").write_text("r\n", encoding="utf-8")
    git(repo, "add", "-f", "_workspace/rep.md")
    return repo, base


def test_drift_commands_in_temp_repo(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    got = run_block(repo, base)
    # --no-renames lists the deleted side of a rename, and the round-one builder commit is inside the diff.
    assert {"old.py", "renamed.py", "builder.py"} <= got, got
    # Names are NUL-split and percent-encoded: a space, a non-ASCII byte and a newline are each one line.
    assert {"new%20file.py", "caf%C3%A9.py", "decl.py%0Adecl.py", "evil%0Aname.py"} <= got, got
    assert not got & {"evil", "name.py", "decl.py"}, got
    # Ignored paths and the force-added _workspace file are outside the row.
    assert not got & {"dist/hidden.py", "c.pyc", "_workspace/rep.md", "declared.py"}, got
    # No index flags on a clean tree; the exclude digest is printed.
    assert not any(ln.startswith(("h ", "S ")) for ln in got), got
    assert not any(ln.startswith("H ") for ln in got), got  # clean tracked files are not flags
    assert f"excl={exclude_digest(repo)}" in got, got
    # A global excludes file is not an ignore rule: candidate_id.py lists with core.excludesFile=/dev/null,
    # so the block must list the name it matches (judge r3 N8, P-2).
    gx = tmp_path / "global_ignore"
    gx.write_text("gx_hidden.py\n", encoding="utf-8")
    git(repo, "config", "core.excludesFile", str(gx))
    (repo / "gx_hidden.py").write_text("g\n", encoding="utf-8")
    assert "gx_hidden.py" in run_block(repo, base), run_block(repo, base)


def test_nul_safe_block_has_no_tr_split() -> None:
    assert "tr '\\0'" not in drift_block(), drift_block()


def base_step_block() -> str:
    sec = (
        (REPO / QA_GUIDE).read_text(encoding="utf-8").split("### 7-10. Drift from the brief", 1)[1]
    )
    blocks = re.findall(r"```bash\n(.*?)```", sec, re.DOTALL)
    return str(next(b for b in blocks if b.startswith('echo "Base:')))


def test_drift_commands_use_hashlib_not_sha256sum() -> None:
    # judge r3 note: sha256sum is not on macOS; the digest is python3 hashlib in the Base step and the block.
    for block in (drift_block(), base_step_block()):
        assert "sha256sum" not in block, block
        assert "hashlib.sha256" in block, block


def test_base_step_prints_the_hashlib_digest_with_and_without_exclude_file(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    head = git(repo, "rev-parse", "--short=12", "HEAD").strip()
    env = {**os.environ, "REPO": str(repo)}
    p = subprocess.run(
        ["bash", "-c", base_step_block()],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == f"Base: git:{head} excl={exclude_digest(repo)}", p.stdout
    (repo / ".git" / "info" / "exclude").unlink()
    p = subprocess.run(
        ["bash", "-c", base_step_block()],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert p.stdout.strip() == f"Base: git:{head} excl=none", p.stdout


def test_carried_base_still_lists_round_one_builder_commit(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)  # round one: the builder commits builder.py after Base
    (repo / "sneaky.py").write_text("s\n", encoding="utf-8")  # round two: an undeclared commit
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "round two builder commit")
    got = run_block(repo, base)  # the carried Base, not a Base re-recorded after round one
    assert {"builder.py", "sneaky.py"} <= got, got


def test_assume_unchanged_hides_an_edit_and_is_listed_as_a_flag(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "declared.py").write_text("changed\n", encoding="utf-8")
    git(repo, "update-index", "--assume-unchanged", "declared.py")
    got = run_block(repo, base)
    assert "declared.py" not in got, got  # hidden from the diff listing
    assert "h declared.py" in got, got  # the flag line


def test_skip_worktree_hides_an_edit_and_is_listed_as_a_flag(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "declared.py").write_text("changed\n", encoding="utf-8")
    git(repo, "update-index", "--skip-worktree", "declared.py")
    got = run_block(repo, base)
    assert "declared.py" not in got, got
    assert "S declared.py" in got, got


def test_exclude_line_hides_a_new_file_and_moves_the_digest(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    before = exclude_digest(repo)  # the digest recorded at Base
    with (repo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as f:
        f.write("hidden_helper.py\n")
    (repo / "hidden_helper.py").write_text("x\n", encoding="utf-8")
    got = run_block(repo, base)
    after = exclude_digest(repo)
    assert after != before
    assert "hidden_helper.py" not in got, got  # the appended line hides the undeclared file
    assert f"excl={after}" in got, got  # but the digest moved
    head = (
        f"CANDIDATE: {CAND} n=1 excludes=_workspace/\nBASE: git:{base} excl={before}\nCARRIED: -\n"
    )
    code, out = run(tmp_path, qa("PASS", rows=drift(excl=after), head=head))
    assert "differs from the Base line" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- prose pins (named, one per claim)

CHANGED = {
    "skills/finhub-harness/SKILL.md": [
        "Its definition file also says four things, because a QA agent follows only what its own file says",
        "write `cause: context-gap` or `cause: judgment-gap` at the end of every defect row",
        "under a heading written exactly `## Defects` (rows are `- defect: file:line ...` or `1. file:line ...`",
        "no other line starts with the word Defect or Defects",
        "copy the brief's Base line into a `BASE:` line",
        "write one `drift:` row in its Gate table",
        "run `scripts/finding_tags.py check` on its report last",
    ],
    "skills/finhub-harness/references/quality-gates.md": [
        "A REJECTED row also carries one cause tag, set by rule T3 of section 3-8",
        "### 3-8. Cause tags and the drift row",
        "Doubt decides whether a claim is accepted or a defect is raised. It never decides the cause.",
        "| T2 | Each defect row of a QA report",
        "recorded once per unit before the first builder spawn",
        "| D2 | `on=` equals the `git:` token of the report's own `CANDIDATE:` line",
        "| D3 | A PASS has `undeclared=-`.",
        "| D4 | A PASS has `flags=0`.",
        "| D5 | `excl=` equals the `excl=` of the `BASE:` line",
        "**Drift refusals.** A drift row that fails D1-D5 is a refusal in every run and exits 4",
        "There is no advisory mode and no option that turns a drift refusal into a pass",
        "a missing or wrong drift row is a refusal (exit 4) like any other.",
        "in which a cell holds the word REJECTED, case ignored, after `*`, `_`, backticks and `~` are read as spaces",
        "The orchestrator writes the line to `_workspace/base_{unit}.txt` in the same step.",
        "never records a new Base for a unit once a builder for it has run",
        "A global excludes file (`core.excludesFile`) is not an ignore rule for either",
        "- Resume route:",
        "- Resume route: prose only.",
        "A defect row inside a code fence is counted like any other",
        "The Defects route is an allow-list and fails closed.",
        "**First-word rule:** outside a code fence, a line whose first word is `defect` or `defects`, case ignored",
        "a longer or hyphenated word such as `defect-row` is another word",
        "exactly one of three canonical forms or the record is refused (exit 4, the message names the line and `non-canonical Defects line`)",
        "the heading `## Defects` or `### Defects` at column 0",
        "a defect row `- defect: file:line ...` at column 0 with one space after the colon",
        "the none line `Defects: none`",
        "so an entity-encoded `## Defe&#99;ts` is the canonical heading",
        "**Section rule:** a Defects section opens at a canonical heading, or at an ATX heading",
        "whose text names defects after its first word (`## Known defects`, `**Known defects**`)",
        "ends at the next heading of the same or a higher level; a heading inside a code fence is not read",
        "a numbered item `1. file:line ...` or `1) file:line ...` at column 0; `1. observation:` is a defect row too, fail closed",
        "indented at least two spaces or a tab, not starting with a list mark, `|`, `>`, `#` or `:`",
        "a none line (`Defects: none`, or `none`, `none found`, `no defects found` or `n/a` with an optional leading bullet, parentheses around `none`, a trailing period, any case)",
        "Any other non-blank line is refused (message `non-canonical line in a Defects section`)",
        "a bare bullet, an indented or deeper-level item, a table row, a definition list, a block-quote item",
        "A PASS holds no defect row. A FAIL's section holds at least one defect row or none line, and a bare FAIL holds a defect row.",
        "a location in bold or backticks, and a tag on the continuation line of a wrapped row, are refused",
        "A numbered row `N. file:line ...` or `N) file:line ...` at column 0 outside a code fence is a defect row wherever it sits, under a heading that never names defects included",
        "a `- defect:` row is a defect row wherever it sits too",
        "a numbered `file:line` line inside a fence outside a Defects section is command output and is not counted",
        "the look-alikes of `DEFECT_FOLD` (Cyrillic, Greek and Latin small-capital, hooked and stroked forms of the letters d, e, f, c, t and s) are folded and the control characters (NUL included, the tab excepted) are dropped",
        "whose ASCII letters alone are within one edit of `defect` or `defects` is refused as `non-canonical Defects line` (fail closed)",
        "a look-alike word two or more edits from those is not caught",
        "A code fence that is never closed by a matching closer",
        "refuses the record (message `code fence opened here is never closed`)",
        "HTML entities are resolved until nothing changes",
        "the thirteen Cyrillic and Greek capitals and small letters of `FOLD_MAP` that look like E, C, T, J or D",
        "the Greek lunate sigmas U+03F9 and U+03F2 included",
        "a line still changing after 100 passes refuses the record: a nesting 100 deep is read, one 101 deep is refused",
        "A fenced line that holds REJECTED in a row is refused even without an edge pipe",
        "until nothing changes",
        "- Accepted residuals (Daniel, 2026-10-11 and 2026-10-12):",
        "1. REJECTED written as a symbol only",
        "2. A verdict written as prose on a line with no pipe",
        "3. REJECTED split across a line break",
        "4. An HTML comment that holds angle brackets",
        "5. Invisible characters that are neither format",
        "6. Dotted or hyphenated letters",
        "7. Look-alike letters outside the pinned `FOLD_MAP`",
        "8. The `UNVERIFIED n` on the TOTALS line is not reconciled",
        "9. The resume route (the Base file) is a prose-only control",
        "10. The candidate id does not read `.git/info/exclude`",
        "11. Fence narrowing:",
        "12. Four historic judge records",
        "boundary-qa is the only check on those",
        "A fenced line of a judge or QA record that is a table row",
        "U+13A1 (named CHEROKEE LETTER E)",
        "The `UNVERIFIED n` on the TOTALS line is not reconciled",
        "- REJECTED count route:",
        (
            "The step that checks reports runs `candidate_id.py check` (C5) and then `finding_tags.py check` "
            "on every QA report and judge verdict."
        ),
        "A passing `finding_tags.py check` does not show that a report is current",
        "Exit 4 is a refusal of a record, not the stale exit 3 of `candidate_id.py check`",
        "An appended or edited file is checked again in full",
        "Ignored paths are outside the drift row",
        "A forged row passes D1-D5.",
        "- Index-flag route:",
        "- Exclude-file route:",
        "- `_workspace/` design-file route:",
        "`Declared:` is copied by hand from the design",
        "A tracked file forced into `_workspace/` is hidden by the pathspec.",
        "`candidate differs from the brief` or `candidate moved during QA`",
        "A builder fault written as a process reason",
    ],
    "skills/finhub-harness/references/qa-agent-guide.md": [
        "### 7-10. Drift from the brief",
        "a `BASE:` line copied from the Base line of your brief, and a `CARRIED:` line",
        "- Write `cause: context-gap` or `cause: judgment-gap` at the end of every defect row",
        "List observations as `- observation:` bullets, never as numbered items",
        "Write the heading exactly `## Defects`, put nothing but defect rows, wrapped continuation lines",
        "never start any other line with the word Defect or Defects",
        "- Write the drift row in `## Gate` (section 7-10 of this guide), then run `finding_tags.py check <your report>` last",
        "BASE=<12 hex digits>",
        '--no-renames --name-only "$BASE"',
        "ls-files -z --others --exclude-standard",
        "-c core.excludesFile=/dev/null ls-files -z --others --exclude-standard",
        "import hashlib, sys; print(hashlib.sha256(open(sys.argv[1]",
        "and the listing reads no global excludes file",
        "ls-files -v -- . ':(exclude)_workspace' | grep -v '^H '",
        "rev-parse --absolute-git-dir)/info/exclude",
        "so a name with a newline is one line",
        "A PASS needs `undeclared=-`, `flags=0` and the Base line's `excl=`.",
    ],
    "skills/finhub-harness/references/orchestrator-template.md": [
        "`Base: git:<12 hex> excl=<12 hex or none>` is recorded once per unit",
        "a builder re-run for the same unit gets the same line",
        "`_workspace/base_{unit}.txt` in the same step",
        "never records a new Base for a unit once a builder for it has run",
        "The QA agent file that Step 3 generates must tell the agent to do four things",
        "end every defect row with a cause tag, copy the Base line into a `BASE:` line, copy the `CANDIDATE:` line, and write the drift row",
        "it is not a finding against the builder",
        "| A report that `finding_tags.py check` refuses (exit 4), from any worker |",
        "(exit 3 is a stale verdict)",
    ],
    ".claude/agents/boundary-qa.md": [
        "- Drift row and causes:",
        "an `- observation:` bullet is the one exception",
        "Write the heading exactly `## Defects`. Under it each `- defect: file:line ...` row or numbered item",
        "no other line starts with the word Defect or Defects; the checker refuses any other form",
        "finding_tags.py check <your report>",
        "its `undeclared=` is the changed paths outside `Declared:`",
        "fourth line `BASE:`",
    ],
    ".claude/skills/adversarial-audit/references/verdict-schema.md": [
        "`cause: judgment-gap` when the cited file is one the design lists as an input and the architect could read it",
        "Doubt decides whether a claim is rejected, never the cause.",
        "the word REJECTED appears, case ignored",
        "`*`, `_`, backticks and `~` are read as spaces",
        "`&#82;EJECTED` all count",
        "after HTML entities and tags are resolved",
    ],
    "skills/finhub-harness-evolve/SKILL.md": [
        "`cause: judgment-gap` when the `evidence:` line cites something the failing step was handed",
        "| cause: <context-gap|judgment-gap> | evidence:",
    ],
    ".claude/skills/master-finhub-orchestrator/SKILL.md": [
        "Before you spawn the first builder for this unit, run the Base step",
        "    Base: {the Base line for this unit, recorded once before its first builder spawn",
        "finding_tags.py check _workspace/03_boundary-qa_{unit}.md",
        "A refusal of a drift row is a refusal like any other",
        "`_workspace/base_{unit}.txt` in the same step",
        "never record a new Base for a unit once a builder for it has run",
    ],
    "CLAUDE.md": [
        "| 2026-10-11 | Cause-of-miss tags and a drift row adopted from OpenRig",
        "the gate is enforce-by-default",
        "the legacy exemption is dropped",
        "the Defects route is an allow-list that fails closed (T2)",
        "a numbered `file:line` row is a defect row under any heading; a code fence that never closes refuses the record",
        "UPHELD 64 / REJECTED 7 / UNVERIFIED 0",
        "not re-audited",
    ],
}
NEW_FILES = ["skills/finhub-harness/scripts/finding_tags.py", "tests/test_finding_tags.py"]
ATTR = re.compile(
    r"adapted from references/openrig/docs/reference/wave-sdlc\.md:\d+(?:-\d+)? \(Apache-2\.0\)"
)


@pytest.mark.parametrize("rel,phrase", [(k, p) for k, v in CHANGED.items() for p in v])
def test_prose_pin(rel: str, phrase: str) -> None:
    assert phrase in (REPO / rel).read_text(encoding="utf-8"), rel


@pytest.mark.parametrize("rel", list(CHANGED) + NEW_FILES)
def test_changed_file_carries_wave_sdlc_attribution(rel: str) -> None:
    # Specific to wave-sdlc.md: no file at 57fdf30 cites that source, so a match means this patch added one.
    assert ATTR.search((REPO / rel).read_text(encoding="utf-8")), rel


def test_no_default_cause_is_written_anywhere() -> None:
    # BC10: the cause is set by rule; "when unsure, tag context-gap" is the default that was removed.
    for rel in CHANGED:
        assert "When unsure, tag" not in (REPO / rel).read_text(encoding="utf-8"), rel


# Korean lines that already exist at 57fdf30 (CLAUDE.md header, orchestrator markers). The count must not grow.
PRE_EXISTING_HANGUL_LINES = {
    "CLAUDE.md": 1,
    ".claude/skills/master-finhub-orchestrator/SKILL.md": 27,
}


def _hangul(line: str) -> bool:
    return any(unicodedata.name(c, "").startswith("HANGUL") for c in line)


def test_no_hangul_in_changed_files() -> None:
    for rel in list(CHANGED) + NEW_FILES:
        lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
        n = sum(1 for ln in lines if _hangul(ln))
        assert n == PRE_EXISTING_HANGUL_LINES.get(rel, 0), (rel, n)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def test_no_eight_word_run_from_wave_sdlc() -> None:
    if not SRC.is_file():
        pytest.skip("references/openrig is not checked out")
    w = _words(SRC.read_text(encoding="utf-8"))
    grams = {tuple(w[i : i + 8]) for i in range(len(w) - 7)}
    hits = []
    for rel in list(CHANGED) + NEW_FILES:
        v = _words((REPO / rel).read_text(encoding="utf-8"))
        hits += [
            (rel, " ".join(v[i : i + 8])) for i in range(len(v) - 7) if tuple(v[i : i + 8]) in grams
        ]
    assert not hits, hits[:10]


def test_cited_wave_sdlc_lines_exist() -> None:
    if not SRC.is_file():
        pytest.skip("references/openrig is not checked out")
    n = len(SRC.read_text(encoding="utf-8").splitlines())
    for rel in list(CHANGED) + NEW_FILES:
        for m in re.finditer(
            r"wave-sdlc\.md:(\d+)(?:-(\d+))?", (REPO / rel).read_text(encoding="utf-8")
        ):
            assert 1 <= int(m[1]) <= n and (m[2] is None or int(m[2]) <= n), (rel, m[0])


def test_checker_imports_only_the_standard_library() -> None:
    import ast

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    # OR-D4 round 5: html (entities) and unicodedata (folding) are the two names added for the character rules.
    assert mods <= {"__future__", "re", "sys", "pathlib", "html", "unicodedata"}, mods


def test_qa_guide_has_no_short_workspace_pathspec() -> None:
    # git rejects ':!_workspace' ("Unimplemented pathspec magic '_'"); the long form is used.
    assert ":!_workspace" not in (REPO / QA_GUIDE).read_text(encoding="utf-8")


# ---------------------------------------------------------------- OR-D4 round 5 (judge N37): fences and character forms
# Judge and QA records are read on every line, fenced or not; a fence cannot hide a verdict or a defect.
# Each character form below is a REJECTED row that the folding of finding_tags.py must count.


def judge(total: int, rows: str, first: str = "TOTALS") -> str:
    return (
        f"{first}: UPHELD 0 / REJECTED {total} / UNVERIFIED 0 — round 1/3\n"
        f"CANDIDATE: {CAND} n=1 excludes=-\nCARRIED: -\n\n"
        "| id | verdict | cited | found | reason |\n|---|---|---|---|---|\n" + rows + "\n"
    )


ROWS = {
    "decimal-entity": "| A4 | &#82;EJECTED | x.py:1 | a{tag} | b |",
    "hex-entity": "| A4 | &#x52;EJECTED | x.py:1 | a{tag} | b |",
    "tag-split": "| A4 | <span>R</span>EJECTED | x.py:1 | a{tag} | b |",
    "zero-width-space": "| A4 | RE\u200bJECTED | x.py:1 | a{tag} | b |",
    "soft-hyphen": "| A4 | RE­JECTED | x.py:1 | a{tag} | b |",
    "full-width-letters": "| A4 | ＲＥＪＥＣＴＥＤ | x.py:1 | a{tag} | b |",
    "cyrillic-capital-E": "| A4 | RЕJECTED | x.py:1 | a{tag} | b |",
    "full-width-bar-row": "A4 ｜ REJECTED ｜ x.py:1 ｜ a{tag} ｜ b",
    "combining-acute": "| A4 | RÉJECTED | x.py:1 | a{tag} | b |",
    "markup-inside-word": "| A4 | RE**JECT**ED | x.py:1 | a{tag} | b |",
    "tag-named-word": "| A4 | <REJECTED> | x.py:1 | a{tag} | b |",
    "letterlike-black-letter-R": "| A4 | \u211cEJECTED | x.py:1 | a{tag} | b |",
}


@pytest.mark.parametrize("form", list(ROWS), ids=list(ROWS))
def test_character_form_of_rejected_is_counted(tmp_path: Path, form: str) -> None:
    code, out = run(tmp_path, judge(0, ROWS[form].format(tag="")))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert "REJECTED row without exactly one cause tag" in out, out
    assert code == 4, out
    code, out = run(
        tmp_path, judge(1, ROWS[form].format(tag=" cause: judgment-gap")), name="tagged.md"
    )
    assert code == 0, out


@pytest.mark.parametrize(
    "ch,latin",
    [
        ("Е", "E"),
        ("Ε", "E"),
        ("е", "E"),
        ("С", "C"),
        ("с", "C"),
        ("Т", "T"),
        ("Τ", "T"),
        ("Ј", "J"),
        ("ј", "J"),
        ("Ԁ", "D"),
        ("ԁ", "D"),
        ("\u03f9", "C"),
        ("\u03f2", "C"),
    ],
    ids=lambda v: f"U+{ord(v):04X}" if len(v) == 1 and ord(v) > 127 else v,
)
def test_every_fold_map_look_alike_in_rejected_is_counted(
    tmp_path: Path, ch: str, latin: str
) -> None:
    word = "REJECTED".replace(latin, ch, 1)
    code, out = run(tmp_path, judge(0, f"| A4 | {word} | x.py:1 | a | b |"))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out


def test_fold_map_is_the_pinned_set() -> None:
    # The pin: the map holds exactly the look-alikes named in quality-gates 3-8. A letter added or dropped fails here.
    mod = load_checker()
    assert {chr(k): v for k, v in mod.FOLD_MAP.items()} == {
        "Е": "E",
        "Ε": "E",
        "е": "e",
        "С": "C",
        "с": "c",
        "Т": "T",
        "Τ": "T",
        "Ј": "J",
        "ј": "j",
        "Ԁ": "D",
        "ԁ": "d",
        "\u03f9": "C",
        "\u03f2": "c",
    }
    assert len(mod.FOLD_MAP) == 13


def test_fenced_table_row_in_judge_is_refused(tmp_path: Path) -> None:
    code, out = run(
        tmp_path, judge(1, "```\n| A4 | REJECTED | x.py:1 | a | b cause: judgment-gap |\n```")
    )
    assert "fenced table row in a judge or QA record" in out, out
    assert code == 4, out


def test_fenced_table_row_in_qa_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", "```\n| src/x.py:4 | a | b |\n```\n"))
    assert "fenced table row in a judge or QA record" in out, out
    assert code == 4, out


def test_fenced_defect_row_in_pass_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", "```\n- defect: src/x.py:4 cause: judgment-gap\n```\n"))
    assert "fenced defect row in a judge or QA record" in out, out
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def test_entity_hidden_defect_marker_is_counted(tmp_path: Path) -> None:
    # `&#45;` is a hyphen: the row is a defect once the entity is resolved, so a PASS holding it is refused.
    code, out = run(tmp_path, qa("PASS", "&#45; defect: src/x.py:4 cause: judgment-gap\n"))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def test_entity_hidden_totals_line_is_read_as_a_judge_record(tmp_path: Path) -> None:
    code, out = run(tmp_path, judge(0, "| A4 | REJECTED | x.py:1 | a | b |", first="&#84;OTALS"))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out


def test_unclosed_fence_hides_no_row(tmp_path: Path) -> None:
    code, out = run(tmp_path, judge(0, "```\n| A4 | REJECTED | x.py:1 | a | b |"))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert "fenced table row in a judge or QA record" in out, out
    assert code == 4, out


def test_drift_row_is_read_as_written(tmp_path: Path) -> None:
    # The drift row is not folded: an entity-written drift row is not a drift row, so D1 refuses the report.
    code, out = run(tmp_path, qa("PASS", rows=drift().replace("| drift:", "| &#100;rift:", 1)))
    assert "drift row missing or repeated (0 found)" in out, out
    assert code == 4, out


def test_correct_tagged_judge_table_is_accepted(tmp_path: Path) -> None:
    # Acceptance: an ordinary table, one REJECTED row with its tag, TOTALS 1, no fence, no character form.
    rows = (
        "| A1 | UPHELD | references/dify/x.py:3 | import block | matches |\n"
        "| A2 | REJECTED | references/dify/y.py:30 | import block | PING is at :61 cause: judgment-gap |\n"
        "| A3 | UPHELD | references/dify/z.py:7 | ok | matches |"
    )
    code, out = run(tmp_path, judge(1, rows))
    assert code == 0, out


def test_fenced_numbered_defect_is_counted_and_needs_a_cause(tmp_path: Path) -> None:
    # A numbered line inside a fence under `## Defects` is a defect: it is counted, so a PASS holding it is refused.
    code, out = run(tmp_path, qa("PASS", "```\n1. src/x.py:4 untagged item\n```\n"))
    assert "PASS with defect rows (1)" in out, out
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


def test_fenced_shell_and_regex_lines_are_not_refused(tmp_path: Path) -> None:
    # Acceptance: command blocks with ordinary pipes and a regex alternation (as in a real QA report) are not table rows.
    body = (
        '```\n$ git diff --stat | tail -1\n-    r"|once more|try again|reassign|redistribut"\n'
        "$ python3 -m pytest -q | tail -3 || true\n```\n"
    )
    code, out = run(tmp_path, qa("PASS", body))
    assert code == 0, out


# ---------------------------------------------------------------- OR-D4 round 5, judge fix requirements (built on top, not re-audited)


def qa_body(heading: str, item: str, verdict: str = "PASS") -> str:
    return f"RESULT: {verdict}\n{HEAD}\n## Gate\n{drift()}\n{heading}\n{item}\n"


@pytest.mark.parametrize(
    "heading", ["### Defects", "**Defects**", "## Defects (round 2)", "#### Defects found"]
)
def test_numbered_defect_under_any_defects_heading_blocks_a_pass(
    tmp_path: Path, heading: str
) -> None:
    code, out = run(tmp_path, qa_body(heading, "1. src/x.py:4 untagged item"))
    assert "PASS with defect rows (1)" in out, out
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


def test_correct_fail_with_tagged_numbered_defects_under_a_h3_heading_passes(
    tmp_path: Path,
) -> None:
    item = "1. src/x.py:4 passes `message`, schema declares `text`. cause: judgment-gap"
    code, out = run(tmp_path, qa_body("### Defects", item, "FAIL"))
    assert code == 0, out


def test_numbered_item_under_another_heading_is_not_a_defect(tmp_path: Path) -> None:
    # Acceptance: the numbered probe list under `### Probes` is not a defect row.
    code, out = run(tmp_path, qa_body("### Probes", "1. python3 -c 'x' exits 0"))
    assert code == 0, out


def test_subheading_under_defects_does_not_end_the_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects\n### Round 1", SECTION_ONLY_ITEM))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def nested(n: int, ch: str = "82") -> str:
    """`R` as a decimal entity written n levels deep: n unescape passes are needed to reach the letter."""
    return "&" + "amp;" * (n - 1) + f"#{ch};"


@pytest.mark.parametrize("depth", [3, 40])
def test_nested_entity_reaches_a_fixed_point_and_is_counted(tmp_path: Path, depth: int) -> None:
    row = f"| A4 | {nested(depth)}EJECTED | x.py:1 | a | b |"
    code, out = run(tmp_path, judge(0, row))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out
    code, out = run(
        tmp_path, judge(1, row.replace(" b |", " b cause: judgment-gap |")), name="tagged.md"
    )
    assert code == 0, out


def test_entity_that_never_settles_refuses_the_record(tmp_path: Path) -> None:
    # Fail closed: past the safety cap the record is refused, never passed with the word unread.
    code, out = run(tmp_path, judge(0, f"| A4 | {nested(150)}EJECTED | x.py:1 | a | b |"))
    assert "entities or tags do not settle" in out, out
    assert code == 4, out


@pytest.mark.parametrize("tagged", [True, False], ids=["tagged", "untagged"])
def test_fenced_no_edge_rejected_row_is_refused(tmp_path: Path, tagged: bool) -> None:
    # Mutant M2b: the clause "holds REJECTED in a row" removed from fenced_row. A4 has no edge pipe.
    tag = " cause: judgment-gap" if tagged else ""
    code, out = run(tmp_path, judge(1, f"```\nA4 | REJECTED | x.py:1 | a | b{tag}\n```"))
    assert "fenced table row in a judge or QA record" in out, out
    assert code == 4, out


def test_fenced_no_edge_row_without_rejected_is_not_refused(tmp_path: Path) -> None:
    # The N63 narrowing, named in quality-gates 3-8: a pipe with no edge pipe and no REJECTED is not refused.
    code, out = run(tmp_path, qa("PASS", "```\nls | wc -l\n```\n"))
    assert code == 0, out


def test_real_regex_fixture_shape_is_not_refused(tmp_path: Path) -> None:
    # Fixture shape of _workspace/03_boundary-qa_OR-S1.md:25-27 (a diff block with regex pipes at 26-27).
    body = '```diff\n+r"(a|b)"\n-    r"|once more|try again|reassign|redistribut"\n```\n'
    code, out = run(tmp_path, qa("PASS", body))
    assert code == 0, out


def test_tag_nesting_beyond_the_cap_refuses_the_record(tmp_path: Path) -> None:
    # Tags are removed to a fixed point as well; a line that has not settled in the cap passes is refused.
    word = "RE" + "<" * 150 + ">" * 150 + "JECTED"
    code, out = run(tmp_path, judge(0, f"| A4 | {word} | x.py:1 | a | b |"))
    assert "entities or tags do not settle" in out, out
    assert code == 4, out


def test_nested_tags_are_removed_to_a_fixed_point_and_counted(tmp_path: Path) -> None:
    word = "RE" + "<" * 3 + ">" * 3 + "JECTED"
    code, out = run(tmp_path, judge(0, f"| A4 | {word} | x.py:1 | a | b |"))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out


# ---------------------------------------------------------------- OR-D4 fix round 1 (boundary-qa FAIL: survivors, heading forms, generated QA agent)
# adapted from references/openrig/docs/reference/wave-sdlc.md:54-62 (Apache-2.0)

UNTAGGED_ITEM = "src/x.py:4 untagged item"
SECTION_ONLY_ITEM = (
    "1. python3 -c 'x' exits 0"  # a row only inside a Defects section (no file:line)
)
TAGGED_ITEM = "src/x.py:4 passes `message`, schema declares `text`. cause: judgment-gap"


def test_item_without_a_location_is_refused(tmp_path: Path) -> None:
    code, out = run(
        tmp_path,
        qa_body("## Defects", "1. the loop passes the wrong key cause: judgment-gap", "FAIL"),
    )
    assert "defect row without a file:line location" in out, out
    assert code == 4, out


def test_table_cell_defect_row_is_a_defect(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", "| defect: src/x.py:4 untagged |\n"))
    assert "PASS with defect rows (1)" in out, out
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


def test_two_digit_numbered_item_is_counted(tmp_path: Path) -> None:
    items = "\n".join(f"{n}. src/x.py:{n} ok cause: judgment-gap" for n in range(1, 10))
    code, out = run(tmp_path, qa_body("## Defects", items + "\n10. src/x.py:10 untagged", "FAIL"))
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "item",
    [
        "- observation: src/x.py:3 guarded upstream",
        "- Observation: src/x.py:3 guarded upstream",
        "- none",
        "- (none)",
    ],
)
def test_observation_and_none_bullets_under_defects_are_not_defects(
    tmp_path: Path, item: str
) -> None:
    code, out = run(tmp_path, qa_body("## Defects", item))
    assert code == 0, out


def test_numbered_observation_under_defects_counts_as_a_defect_row(tmp_path: Path) -> None:
    # Decision (fail closed, quality-gates 3-8 T2): only a bullet can be an observation.
    code, out = run(tmp_path, qa_body("## Defects", "1. observation: src/x.py:3 guarded upstream"))
    assert "PASS with defect rows (1)" in out, out
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


def test_diff_lines_in_a_fence_under_defects_are_not_items(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects", "```diff\n- old line\n+ new line\n* x\n```"))
    assert code == 0, out


def test_sibling_heading_ends_the_defects_section(tmp_path: Path) -> None:
    body = "## Defects\nnone\n## Probes"
    code, out = run(tmp_path, qa_body(body, "1. python3 -c 'x' exits 0"))
    assert code == 0, out


def test_h1_heading_ends_an_h2_defects_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects\nnone\n# Notes", "1. python3 -c 'x' exits 0"))
    assert code == 0, out


def test_setext_heading_ends_the_defects_section(tmp_path: Path) -> None:
    body = "## Defects\nnone\nProbes\n-------"
    code, out = run(tmp_path, qa_body(body, "1. python3 -c 'x' exits 0"))
    assert code == 0, out


def test_html_heading_ends_the_defects_section(tmp_path: Path) -> None:
    code, out = run(
        tmp_path, qa_body("## Defects\nnone\n<h2>Probes</h2>", "1. python3 -c 'x' exits 0")
    )
    assert code == 0, out


def test_bold_defects_title_is_ended_by_a_following_heading(tmp_path: Path) -> None:
    code, out = run(
        tmp_path, qa_body("**Known defects**\nnone\n## Probes", "1. python3 -c 'x' exits 0")
    )
    assert code == 0, out


def test_no_space_heading_never_ends_the_defects_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects\n##Probes", SECTION_ONLY_ITEM))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def test_heading_inside_a_fence_does_not_end_the_defects_section(tmp_path: Path) -> None:
    body = "## Defects\n```\n## Notes\n```"
    code, out = run(tmp_path, qa_body(body, SECTION_ONLY_ITEM))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def test_heading_inside_a_fence_does_not_open_the_defects_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("```\n## Defects\n```", "1. python3 -c 'x' exits 0"))
    assert code == 0, out


def test_thematic_break_after_a_blank_line_is_not_a_setext_heading(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects\nnone\n\n---", SECTION_ONLY_ITEM))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


# --- survivors of the boundary-qa run: counting, grammar, caps


@pytest.mark.parametrize("cell", ["<REJ&amp;#69;CTED>", "<REJ&amp;amp;#69;CTED>"])
def test_entity_decoding_reaches_a_fixed_point_before_tags_are_read(
    tmp_path: Path, cell: str
) -> None:
    # B7: with a single decoding pass the entity is still an entity inside the tag, and the tag removal deletes the word.
    code, out = run(tmp_path, judge(0, f"| A4 | {cell} | x.py:1 | a | b |"))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out


@pytest.mark.parametrize("accent", ["É", "Ё"], ids=["U+00C9", "U+0401"])
def test_precomposed_accented_letter_inside_rejected_is_counted(
    tmp_path: Path, accent: str
) -> None:
    # A-M33 (NFKD removed) and F16 (look-alike map not applied after NFKC): the accent splits off and is dropped,
    # and the Cyrillic IE that U+0401 leaves behind is read as E.
    code, out = run(tmp_path, judge(0, f"| A4 | REJ{accent}CTED | x.py:1 | a | b |"))
    assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
    assert code == 4, out


@pytest.mark.parametrize("word", ["rejectedness", "rejectedly", "unrejected", "prejected"])
def test_rejected_inside_a_longer_word_is_not_a_verdict(tmp_path: Path, word: str) -> None:
    code, out = run(tmp_path, judge(0, f"| A4 | {word} | x.py:1 | a | b |"))
    assert code == 0, out


def test_two_rejected_cells_in_one_row_are_two_in_totals(tmp_path: Path) -> None:
    row = "| A4 | REJECTED | REJECTED | x.py:1 | b cause: judgment-gap |"
    code, out = run(tmp_path, judge(2, row))
    assert code == 0, out
    code, out = run(tmp_path, judge(1, row), "one.md")
    assert "TOTALS says REJECTED 1 but the tables hold 2 REJECTED cell(s)" in out, out
    assert code == 4, out


def test_judge_row_with_two_cause_tags_is_refused(tmp_path: Path) -> None:
    row = "| A4 | REJECTED | x.py:1 | a | b cause: judgment-gap cause: context-gap |"
    code, out = run(tmp_path, judge(1, row))
    assert "REJECTED row without exactly one cause tag" in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "base", [f"git:{BASE_SHA[:8]}", f"git:{BASE_SHA}0"], ids=["8-hex", "13-hex"]
)
def test_base_line_with_a_hash_of_the_wrong_length_is_refused(tmp_path: Path, base: str) -> None:
    head = f"CANDIDATE: {CAND} n=214 excludes=_workspace/\nBASE: {base} excl={EXCL}\nCARRIED: -\n"
    code, out = run(tmp_path, qa("PASS", head=head))
    assert "no BASE line" in out, out
    assert code == 4, out


def test_drift_row_with_empty_flags_is_malformed(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa("PASS", rows=drift().replace("flags=0", "flags=")))
    assert "drift row malformed" in out, out
    assert code == 4, out


def test_undeclared_list_may_equal_changed_but_not_exceed_it(tmp_path: Path) -> None:
    body = "- defect: src/extra.py:1 not in Declared cause: judgment-gap\n"
    code, out = run(tmp_path, qa("FAIL", body, rows=drift(undeclared="a.py", changed=1)))
    assert code == 0, out
    code, out = run(
        tmp_path, qa("FAIL", body, rows=drift(undeclared="a.py,b.py", changed=1)), "two.md"
    )
    assert "undeclared list longer than changed=1" in out, out
    assert code == 4, out


def test_bare_fail_needs_a_drift_row(tmp_path: Path) -> None:
    body = "- defect: src/x.py:1 wrong key cause: judgment-gap\n"
    code, out = run(tmp_path, qa("FAIL", body, rows=""))
    assert "drift row missing or repeated (0 found)" in out, out
    assert code == 4, out


def test_other_subcommand_names_exit_2(tmp_path: Path) -> None:
    f = tmp_path / "r.md"
    f.write_text(qa(), encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "verify", str(f)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "usage: finding_tags.py check FILE" in p.stderr, p.stderr
    assert p.returncode == 2, p.stderr


def test_nesting_of_exactly_the_cap_is_read_and_one_more_is_refused(tmp_path: Path) -> None:
    # 100 passes that change the line are allowed; the 101st change is not (quality-gates 3-8 T3). Entities, then tags.
    for build in (
        lambda n: f"{nested(n)}EJECTED",
        lambda n: "RE" + "<" * n + ">" * n + "JECTED",
    ):
        code, out = run(tmp_path, judge(0, f"| A4 | {build(100)} | x.py:1 | a | b |"))
        assert "TOTALS says REJECTED 0 but the tables hold 1 REJECTED cell(s)" in out, out
        assert "do not settle" not in out, out
        assert code == 4, out
        code, out = run(tmp_path, judge(0, f"| A4 | {build(101)} | x.py:1 | a | b |"), "over.md")
        assert "entities or tags do not settle in 100 passes; record refused" in out, out
        assert code == 4, out


def test_unsettled_line_is_refused_at_its_own_line_number(tmp_path: Path) -> None:
    text = judge(0, f"| A4 | {nested(150)}EJECTED | x.py:1 | a | b |")
    line_no = next(i for i, ln in enumerate(text.splitlines(), 1) if "amp;" in ln)
    code, out = run(tmp_path, text)
    assert f"report.md:{line_no}: entities or tags do not settle" in out, out
    assert code == 4, out


# --- the generated QA agent carries the OR-D4 rules (live-run finding)


def test_qa_agent_definition_template_carries_the_or_d4_rules() -> None:
    guide = (REPO / QA_GUIDE).read_text(encoding="utf-8")
    start = guide.index("## 6. QA agent definition template")
    template = guide[start : guide.index("## 7. Verifier stance", start)]
    for needle in (
        "`cause: context-gap` or `cause: judgment-gap`",
        "a `BASE:` line copied from the Base line of your brief",
        "`CANDIDATE:` line",
        "Write the drift row in `## Gate`",
        "finding_tags.py check <your report>",
    ):
        assert needle in template, needle


def test_harness_skill_tells_the_builder_what_a_generated_qa_agent_must_say() -> None:
    skill = (REPO / "skills/finhub-harness/SKILL.md").read_text(encoding="utf-8")
    line = next(ln for ln in skill.splitlines() if ln.startswith("- QA agents get a type"))
    for needle in (
        "`cause: context-gap` or `cause: judgment-gap`",
        "`BASE:` line",
        "`CANDIDATE:` line",
        "`drift:` row",
        "scripts/finding_tags.py check",
    ):
        assert needle in line, needle


@pytest.mark.parametrize("heading", ["# Defects", "Defects\n======="], ids=["atx-h1", "setext-h1"])
def test_deeper_heading_does_not_end_an_h1_defects_section(tmp_path: Path, heading: str) -> None:
    code, out = run(tmp_path, qa_body(f"{heading}\n## Round 1", SECTION_ONLY_ITEM))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "lines",
    [
        "| Probe | none |\n---",
        "- defect: src/x.py:4 untagged\n---",
        "1. src/x.py:4 untagged item\n---",
    ],
    ids=["table-row", "defect-line", "numbered-item"],
)
def test_underline_after_a_row_or_an_item_does_not_make_a_heading(
    tmp_path: Path, lines: str
) -> None:
    # A row, a `defect:` line or a list item over `---` is not a setext heading: the item is still counted.
    code, out = run(
        tmp_path, qa_body("## Probes" if lines.startswith("| Probe") else "## Defects", lines)
    )
    if lines.startswith("| Probe"):
        assert code == 0, out
    else:
        assert "PASS with defect rows (1)" in out, out
        assert code == 4, out


def test_table_row_over_a_dash_line_does_not_open_the_defects_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("| Probe | none |\n---", "1. python3 -c 'x' exits 0"))
    assert code == 0, out


@pytest.mark.parametrize(
    "above",
    ["---", "--", "===", "***", "___", "* * *", "- - -"],
    ids=["dashes", "two-dashes", "equals", "stars", "underscores", "spaced-stars", "spaced-dashes"],
)
def test_thematic_break_over_a_dash_line_is_not_a_heading(tmp_path: Path, above: str) -> None:
    code, out = run(tmp_path, qa_body(f"## Defects\n{above}\n---", SECTION_ONLY_ITEM))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


@pytest.mark.parametrize("mark", ["-", "*", "+", "|"])
def test_defect_line_with_any_list_mark_is_a_defect_row(tmp_path: Path, mark: str) -> None:
    # Outside a Defects section: only the `defect:` marker makes the line a defect row.
    code, out = run(tmp_path, qa_body("## Probes", f"{mark} defect: src/x.py:4 untagged"))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def test_indented_heading_ends_the_defects_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects\nnone\n  ## Probes", "1. python3 -c 'x' exits 0"))
    assert code == 0, out


# ---------------------------------------------------------------- OR-D4 fix round 2: the Defects route is an allow-list
# adapted from references/openrig/docs/reference/wave-sdlc.md:54-62 (Apache-2.0)
# Rule (quality-gates T2): a line outside a fence whose first word is defect or defects is one of four canonical
# forms or the record is refused; inside a read Defects section every non-blank line is a defect row, a continuation,
# an observation, a none line or a fence, or the record is refused.

PROCESS_FAIL = "FAIL — missing tool: x"
HIT = "src/x.py:4 hit. cause: judgment-gap"
MISS = "src/x.py:4 untagged item"
NONCANON = "non-canonical Defects line"
NONCANON_SEC = "non-canonical line in a Defects section"

REFUSED_HEADINGS = {
    "leading-1-space": " ## Defects",
    "leading-2-spaces": "  ## Defects",
    "leading-3-spaces": "   ## Defects",
    "leading-4-spaces": "    ## Defects",
    "leading-tab": "\t## Defects",
    "no-space": "##Defects",
    "h1-no-space": "#Defects",
    "h1": "# Defects",
    "h4": "#### Defects",
    "h6": "###### Defects",
    "lowercase": "## defects",
    "uppercase": "## DEFECTS",
    "singular": "## Defect",
    "colon": "## Defects:",
    "closing-hashes": "## Defects ##",
    "round-suffix": "## Defects (round 2)",
    "found-suffix": "## Defects found",
    "bold": "**Defects**",
    "bold-colon": "**Defects:**",
    "bold-underscores": "__Defects__",
    "italic-star": "*Defects*",
    "italic-underscore": "_Defects_",
    "plain": "Defects",
    "plain-colon": "Defects:",
    "plain-singular": "Defect",
    "quote": "> ## Defects",
    "quote-quote": "> > ## Defects",
    "quote-plain": "> Defects:",
    "html-h1": "<h1>Defects</h1>",
    "html-h2": "<h2>Defects</h2>",
    "html-h3": "<h3>Defects</h3>",
    "html-h4": "<h4>Defects</h4>",
    "html-h5": "<h5>Defects</h5>",
    "html-h6": "<h6>Defects</h6>",
    "html-h2-upper": "<H2>Defects</H2>",
    "html-p-b": "<p><b>Defects</b></p>",
    "html-b": "<b>Defects</b>",
    "html-strong-colon": "<strong>Defects</strong>:",
    "atx-bold": "## **Defects**",
    "atx-link": "## [Defects](#d)",
    "atx-code": "## `Defects`",
    "atx-strike": "## ~~Defects~~",
    "setext-dashes": "Defects\n-------",
    "setext-equals": "Defects\n=======",
    "setext-short": "Defects\n-",
    "markup-inside-word": "**Def**ects",
    "bulleted": "- Defects",
    "starred": "* Defects:",
    "numbered": "1. Defects",
    "number-no-space": "1.Defects",
    "table-cell": "| Defects | none |",
    "table-edge": "|Defects|",
    "fullwidth-plain": "Ｄefects",
    "none-with-period": "Defects: none.",
    "none-no-space": "Defects:none",
    "none-uppercase": "DEFECTS: NONE",
    "none-tab-indent": "\tDefects: none",
    "none-bulleted": "- Defects: none",
    "none-suffix": "Defects: none (see below)",
    "tag-wrapped-canonical": "<p>## Defects</p>",
    "trailing-comment": "## Defects <!-- note -->",
    "tag-inside-row-heading": "## <span>Defects</span>",
}
CANONICAL_HEADINGS = {
    "h2": "## Defects",
    "h3": "### Defects",
    "trailing-space": "## Defects ",
    "entity": "## Defe&#99;ts",
    "nested-entity": "## Defe&amp;#99;ts",
    "zero-width-space": "## Defe\u200bcts",
    "fullwidth-d": "## Ｄefects",
    "cyrillic-e": "## Dеfects",
}
TITLES_THAT_NAME_DEFECTS_LATER = {
    "atx-known": "## Known defects",
    "atx-open-round": "### Open Defects (round 2)",
    "bold-known": "**Known defects**",
    "html-known": "<h2>Known defects</h2>",
    "setext-known": "Known defects\n-------",
    "quote-known": "> ## Known defects",
    "loose-known": "##Known defects",
    "quote-html-known": "> <h2>Known defects</h2>",
    "underscore-known": "__Known defects__",
    "html-b-known": "<b>Known defects</b>",
    "html-strong-known": "<strong>Known defects</strong>:",
    "setext-equals-known": "Known defects\n=======",
}


def verdict_ok(tmp_path: Path, text: str, name: str = "t.md") -> tuple[int, str]:
    return run(tmp_path, text, name)


@pytest.mark.parametrize("form", list(REFUSED_HEADINGS), ids=list(REFUSED_HEADINGS))
def test_non_canonical_defects_heading_is_refused_in_pass_and_fail(
    tmp_path: Path, form: str
) -> None:
    for verdict, item in (("PASS", f"1. {MISS}"), ("FAIL", f"1. {HIT}")):
        code, out = run(tmp_path, qa_body(REFUSED_HEADINGS[form], item, verdict))
        assert NONCANON in out, out
        assert code == 4, out


@pytest.mark.parametrize("form", list(CANONICAL_HEADINGS), ids=list(CANONICAL_HEADINGS))
def test_canonical_defects_heading_is_read_in_pass_and_fail(tmp_path: Path, form: str) -> None:
    head = CANONICAL_HEADINGS[form]
    code, out = run(tmp_path, qa_body(head, "- none"))
    assert code == 0, out
    code, out = run(tmp_path, qa_body(head, f"1. {MISS}"), "miss.md")
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out
    code, out = run(tmp_path, qa_body(head, f"1. {HIT}", "FAIL"), "hit.md")
    assert code == 0, out


@pytest.mark.parametrize(
    "form", list(TITLES_THAT_NAME_DEFECTS_LATER), ids=list(TITLES_THAT_NAME_DEFECTS_LATER)
)
def test_title_that_names_defects_after_its_first_word_opens_a_section(
    tmp_path: Path, form: str
) -> None:
    head = TITLES_THAT_NAME_DEFECTS_LATER[form]
    code, out = run(tmp_path, qa_body(head, f"1. {MISS}"))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out
    code, out = run(tmp_path, qa_body(head, f"1. {HIT}", "FAIL"), "hit.md")
    assert code == 0, out
    code, out = run(tmp_path, qa_body(head, f"- bare bullet {HIT}", "FAIL"), "bare.md")
    assert NONCANON_SEC in out, out
    assert code == 4, out


CANONICAL_ITEMS = {
    "numbered": "1. {t}",
    "numbered-two-digits": "10. {t}",
    "numbered-paren": "1) {t}",
    "defect-row": "- defect: {t}",
}
REFUSED_ITEMS = {
    "numbered-indented": "   1. {t}",
    "numbered-paren-indented": "  2) {t}",
    "numbered-tab": "\t1. {t}",
    "bullet-dash": "- {t}",
    "bullet-star": "* {t}",
    "bullet-plus": "+ {t}",
    "bullet-indented": "  - {t}",
    "bullet-tab": "\t- {t}",
    "table-row": "| 1 | src/x.py:4 | {t} |",
    "definition-list": "src/x.py:4\n: {t}",
    "quote-numbered": "> 1. src/x.py:4 {t}",
    "quote-bullet": "> - src/x.py:4 {t}",
    "no-space-dash": "-defect: src/x.py:4 {t}",
    "no-space-star": "*defect: src/x.py:4 {t}",
    "no-space-plus": "+defect: src/x.py:4 {t}",
    "star-row": "* defect: src/x.py:4 {t}",
    "plus-row": "+ defect: src/x.py:4 {t}",
    "pipe-row": "| defect: src/x.py:4 {t} |",
    "numbered-defect": "1. defect: src/x.py:4 {t}",
    "indented-row": "  - defect: src/x.py:4 {t}",
    "no-space-after-colon": "- defect:src/x.py:4 {t}",
    "capital-row": "- Defect: src/x.py:4 {t}",
    "double-space-row": "- defect:  src/x.py:4 {t}",
    "prose": "The loop is wrong at src/x.py:4 {t}",
    "prose-defect-first": "Defect 1 (F01) is closed: {t}",
    "thematic": "---\n1. src/x.py:4 {t}",
    "stars": "***",
    "subheading": "### Round 1\n1. src/x.py:4 {t}",
    "bold-title": "**Notes**\n1. src/x.py:4 {t}",
    "numbered-no-space": "1.src/x.py:4 {t}",
    "numbered-over-underline": "1. src/x.py:4 {t}\n---",
    "paren-over-underline": "1) src/x.py:4 {t}\n---",
    "dash-over-underline": "- src/x.py:4 {t}\n---",
    "star-over-underline": "* src/x.py:4 {t}\n---",
    "plus-over-underline": "+ src/x.py:4 {t}\n---",
    "indented-bullet-over-underline": "  - src/x.py:4 {t}\n---",
    "table-row-over-underline": "| 1 | src/x.py:4 | {t} |\n---",
    "defect-row-over-equals": "- defect: src/x.py:4 {t}\n===",
    "thematic-over-underline": "***\n---",
}


@pytest.mark.parametrize("form", list(CANONICAL_ITEMS), ids=list(CANONICAL_ITEMS))
def test_canonical_defect_row_counts_and_is_tagged(tmp_path: Path, form: str) -> None:
    code, out = run(
        tmp_path, qa_body("## Defects", CANONICAL_ITEMS[form].format(t="src/x.py:4 untagged"))
    )
    assert "PASS with defect rows (1)" in out, out
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out
    code, out = run(
        tmp_path, qa_body("## Defects", CANONICAL_ITEMS[form].format(t=HIT), "FAIL"), "hit.md"
    )
    assert code == 0, out


@pytest.mark.parametrize("form", list(REFUSED_ITEMS), ids=list(REFUSED_ITEMS))
def test_non_canonical_item_under_defects_is_refused_in_pass_and_fail(
    tmp_path: Path, form: str
) -> None:
    for verdict, t in (("PASS", MISS), ("FAIL", HIT)):
        code, out = run(tmp_path, qa_body("## Defects", REFUSED_ITEMS[form].format(t=t), verdict))
        assert NONCANON in out or NONCANON_SEC in out, out
        assert code == 4, out


NONE_LINES_ACCEPTED = [
    "- none",
    "none",
    "None.",
    "- None found.",
    "none found",
    "NONE FOUND.",
    "- No defects found.",
    "No defects found",
    "- n/a",
    "N/A.",
    "- (none)",
    "Defects: none",
    "- observation: src/x.py:3 guarded upstream",
    "* none",
    "+ none found",
    "none ",
    "(none)",
]
NONE_LINES_REFUSED = [
    "the answer is none",
    "- None found, see below",
    "- n/a for round 1",
    "Defects: none.",
    "- Defects: none",
    "defects: none",
    "  - none",
    "None of them",
    "*none*",
]


@pytest.mark.parametrize("line", NONE_LINES_ACCEPTED)
def test_none_class_lines_are_accepted_in_pass_and_in_a_process_fail(
    tmp_path: Path, line: str
) -> None:
    code, out = run(tmp_path, qa_body("## Defects", line))
    assert code == 0, out
    code, out = run(tmp_path, qa_body("## Defects", line, PROCESS_FAIL), "fail.md")
    if line.startswith(
        "- observation"
    ):  # an observation is not a none line: a FAIL needs one of the two
        assert "Defects section holds no defect row and no none line" in out, out
        assert code == 4, out
    else:
        assert code == 0, out


@pytest.mark.parametrize("line", NONE_LINES_REFUSED)
def test_none_look_alikes_are_refused(tmp_path: Path, line: str) -> None:
    for verdict in ("PASS", PROCESS_FAIL):
        code, out = run(tmp_path, qa_body("## Defects", line, verdict))
        assert NONCANON in out or NONCANON_SEC in out, out
        assert code == 4, out


def test_continuation_line_of_a_row_is_accepted(tmp_path: Path) -> None:
    body = f"1. {HIT}\n   it wraps onto a second line\n\n\twith a tab on the third"
    code, out = run(tmp_path, qa_body("## Defects", body, "FAIL"))
    assert code == 0, out


@pytest.mark.parametrize(
    "line",
    [
        "  - src/y.py:5 hidden",
        "  * src/y.py:5 hidden",
        "  + src/y.py:5 hidden",
        "   1. src/y.py:5 hidden",
        "  | 2 | src/y.py:5 | hidden |",
        "  > src/y.py:5 hidden",
        "  : src/y.py:5 hidden",
        " one space is not an indent",
        "no indent at all",
    ],
)
def test_a_line_that_looks_like_a_new_item_is_not_a_continuation(tmp_path: Path, line: str) -> None:
    code, out = run(tmp_path, qa_body("## Defects", f"1. {HIT}\n{line}", "FAIL"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


def test_indented_line_with_no_row_before_it_is_not_a_continuation(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects", "  text with no row above it"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


def test_continuation_does_not_carry_over_a_refused_line(tmp_path: Path) -> None:
    code, out = run(
        tmp_path, qa_body("## Defects", f"1. {HIT}\n- bare\n  wrapped bare line", "FAIL")
    )
    assert out.count(NONCANON_SEC) == 2, out
    assert code == 4, out


def test_cause_tag_on_the_continuation_line_is_refused(tmp_path: Path) -> None:
    # Named in quality-gates T2: the tag is on the row line itself, not on the line a wrapped row continues on.
    code, out = run(
        tmp_path, qa_body("## Defects", "1. src/x.py:4 hit\n   cause: judgment-gap", "FAIL")
    )
    assert "defect row without exactly one cause tag" in out, out
    assert code == 4, out


@pytest.mark.parametrize("loc", ["**src/x.py:4**", "`src/x.py:4`", "[src/x.py:4](x)"])
def test_marked_up_location_is_refused(tmp_path: Path, loc: str) -> None:
    # Named in quality-gates T2: the location is plain `file:line`, first on the row.
    code, out = run(tmp_path, qa_body("## Defects", f"1. {loc} hit cause: judgment-gap", "FAIL"))
    assert "defect row without a file:line location" in out, out
    assert code == 4, out


def test_fail_section_with_only_an_observation_is_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects", "- observation: src/x.py:3 ok", PROCESS_FAIL))
    assert "Defects section holds no defect row and no none line" in out, out
    assert code == 4, out


def test_empty_section_is_accepted_in_a_pass_and_refused_in_a_fail(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects", "## Probes\n1. python3 -c 'x' exits 0"))
    assert code == 0, out
    code, out = run(
        tmp_path,
        qa_body("## Defects", "## Probes\n1. python3 -c 'x' exits 0", PROCESS_FAIL),
        "f.md",
    )
    assert "Defects section holds no defect row and no none line" in out, out
    assert code == 4, out


def test_section_at_end_of_record_is_checked_in_a_fail(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Probes\n1. ok", "## Defects", PROCESS_FAIL))
    assert "Defects section holds no defect row and no none line" in out, out
    assert code == 4, out


def test_refusal_names_the_line_of_the_section_heading(tmp_path: Path) -> None:
    text = qa_body("## Defects", "- observation: src/x.py:3 ok", PROCESS_FAIL)
    line_no = next(i for i, ln in enumerate(text.splitlines(), 1) if ln == "## Defects")
    code, out = run(tmp_path, text)
    assert f"report.md:{line_no}: Defects section holds no defect row" in out, out
    assert code == 4, out


def test_deeper_heading_in_a_defects_section_is_refused_and_a_sibling_ends_it(
    tmp_path: Path,
) -> None:
    code, out = run(tmp_path, qa_body("## Defects\n- none\n### Round 1", "- none"))
    assert NONCANON_SEC in out, out
    assert code == 4, out
    code, out = run(
        tmp_path, qa_body("### Defects\n- none\n## Probes", "1. python3 -c 'x' exits 0")
    )
    assert code == 0, out
    code, out = run(tmp_path, qa_body("## Defects\n- none\n# Notes", "1. python3 -c 'x' exits 0"))
    assert code == 0, out


@pytest.mark.parametrize("mark", ["-", "*", "+"])
@pytest.mark.parametrize("under", ["---", "==="])
def test_no_space_defect_mark_over_an_underline_is_refused(
    tmp_path: Path, mark: str, under: str
) -> None:
    # QA fix round 1 finding 1: the line is a defect row (and non-canonical), never a setext heading to skip.
    code, out = run(tmp_path, qa_body("## Defects", f"{mark}defect: src/x.py:4 untagged\n{under}"))
    assert NONCANON in out, out
    # counted as a defect row too: the guard in the setext test keeps it from being read as a heading and skipped
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


@pytest.mark.parametrize("under", ["---", "==="])
def test_canonical_defect_row_over_an_underline_is_still_counted(
    tmp_path: Path, under: str
) -> None:
    # The guard `DEFECT.match(t)` in the setext test: without it this row is read as a heading, skipped, and a PASS
    # holding a defect exits 0.
    code, out = run(
        tmp_path,
        qa_body("## Defects", f"- defect: src/x.py:3 a cause: judgment-gap\n{under}"),
    )
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


def test_defect_row_over_a_dash_line_does_not_end_the_section(tmp_path: Path) -> None:
    body = "- defect: src/x.py:3 a cause: judgment-gap\n---\n- src/y.py:5 bare"
    code, out = run(tmp_path, qa_body("## Defects", body, "FAIL"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


def test_first_word_defect_line_is_refused_anywhere_outside_a_fence(tmp_path: Path) -> None:
    for line in (
        "Defect 1 (F01) is closed: the added assertion kills it.",
        "Defects were found in round 1",
        "defects: none",
        "> Defects: none",
        "| Defects | 0 |",
        "  Defect list below",
    ):
        code, out = run(tmp_path, qa_body("## Probes", line))
        assert NONCANON in out, out
        assert code == 4, out


@pytest.mark.parametrize(
    "line",
    [
        "| defect-row grammar | DEFECT | the item pattern | no |",
        "| defective code path | a | b | c |",
        "Defective builds are out of scope.",
        "defect_table is a variable name",
        "Defects2 is another word",
    ],
)
def test_a_line_that_starts_with_another_word_is_not_a_defects_line(
    tmp_path: Path, line: str
) -> None:
    code, out = run(tmp_path, qa_body("## Probes", line))
    assert code == 0, out


def test_defects_word_inside_a_fence_is_not_read(tmp_path: Path) -> None:
    code, out = run(
        tmp_path, qa_body("## Probes", "```\nDefects\n## Defects\nDefect 1 is closed\n```")
    )
    assert code == 0, out


def test_canonical_none_line_outside_any_section_is_accepted(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Probes", "Defects: none"))
    assert code == 0, out


def test_fenced_block_inside_a_defects_section_is_accepted(tmp_path: Path) -> None:
    body = f"1. {HIT}\n```diff\n- old\n+ new\nDefects\n```"
    code, out = run(tmp_path, qa_body("## Defects", body, "FAIL"))
    assert code == 0, out


def test_refusal_names_the_line_number(tmp_path: Path) -> None:
    text = qa_body("## Defects", "- bare bullet")
    line_no = next(i for i, ln in enumerate(text.splitlines(), 1) if ln == "- bare bullet")
    _, out = run(tmp_path, text)
    assert f"report.md:{line_no}: {NONCANON_SEC}" in out, out
    text = qa_body("## Probes", "Defects")
    line_no = next(i for i, ln in enumerate(text.splitlines(), 1) if ln == "Defects")
    _, out = run(tmp_path, text, "two.md")
    assert f"two.md:{line_no}: {NONCANON}" in out, out


def test_form_table_has_at_least_sixty_forms() -> None:
    n = (
        len(REFUSED_HEADINGS)
        + len(CANONICAL_HEADINGS)
        + len(TITLES_THAT_NAME_DEFECTS_LATER)
        + len(CANONICAL_ITEMS)
        + len(REFUSED_ITEMS)
        + len(NONE_LINES_ACCEPTED)
        + len(NONE_LINES_REFUSED)
    )
    assert n >= 60, n


def test_numbered_item_in_a_fence_under_defects_is_counted(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects", "```\n1. src/x.py:4 untagged\n```"))
    assert "PASS with defect rows (1)" in out, out
    assert "fenced defect row" not in out, out
    assert code == 4, out


def test_numbered_item_in_a_fence_outside_a_defects_section_is_not_counted(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Probes", "```\n1. python3 -c 'x' exits 0\n```"))
    assert code == 0, out


@pytest.mark.parametrize("above", ["- observation: src/x.py:3 ok", "none", "Defects: none"])
def test_continuation_of_an_observation_or_none_line_is_accepted(
    tmp_path: Path, above: str
) -> None:
    code, out = run(tmp_path, qa_body("## Defects", f"{above}\n  wrapped onto a second line"))
    assert code == 0, out


def test_continuation_after_a_fence_is_not_a_continuation(tmp_path: Path) -> None:
    body = f"1. {HIT}\n```\nx\n```\n  text after the fence"
    code, out = run(tmp_path, qa_body("## Defects", body, "FAIL"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


@pytest.mark.parametrize("line", ["  #src/y.py:5 hidden", "  3.", "  4)"])
def test_more_continuation_lookalikes_are_refused(tmp_path: Path, line: str) -> None:
    code, out = run(tmp_path, qa_body("## Defects", f"1. {HIT}\n{line}", "FAIL"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


@pytest.mark.parametrize("title", ["# Known defects", "Known defects\n======="])
def test_deeper_heading_does_not_end_an_h1_known_defects_section(
    tmp_path: Path, title: str
) -> None:
    code, out = run(tmp_path, qa_body(f"{title}\n## Round 1", f"1. {MISS}"))
    assert "PASS with defect rows (1)" in out, out
    assert code == 4, out


@pytest.mark.parametrize("word", ["Defect", "Defects", "defect", "DEFECTS"])
def test_each_spelling_of_the_first_word_is_read(tmp_path: Path, word: str) -> None:
    code, out = run(tmp_path, qa_body("## Probes", f"{word}"))
    assert NONCANON in out, out
    assert code == 4, out


def test_a_second_defects_section_is_checked_on_its_own(tmp_path: Path) -> None:
    body = "- none\n## Notes\n1. python3 -c 'x' exits 0\n## Defects\n- observation: src/x.py:3 ok"
    code, out = run(tmp_path, qa_body("## Defects", body, PROCESS_FAIL))
    assert "Defects section holds no defect row and no none line" in out, out
    assert code == 4, out


def test_a_bold_title_that_does_not_name_defects_opens_no_section(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("**Probes**", "1. python3 -c 'x' exits 0"))
    assert code == 0, out
    code, out = run(tmp_path, qa_body("<b>Probes</b>", "1. python3 -c 'x' exits 0"), "html.md")
    assert code == 0, out


@pytest.mark.parametrize("title", ["## Known defects", "**Known defects**"])
def test_a_new_section_does_not_inherit_the_continuation_of_an_earlier_row(
    tmp_path: Path, title: str
) -> None:
    body = f"- defect: src/x.py:4 hit cause: judgment-gap\n{title}\n  wrapped text"
    code, out = run(tmp_path, qa_body("## Probes", body, "FAIL"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


def test_a_second_canonical_heading_does_not_inherit_the_continuation(tmp_path: Path) -> None:
    body = f"1. {HIT}\n## Defects\n  wrapped text"
    code, out = run(tmp_path, qa_body("## Defects", body, "FAIL"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


# ---------------------------------------------------------------- OR-D4 fix round 3
# Look-alikes of the word Defects, a fence that never closes, a numbered row under a heading that never names
# defects, and three mutants (F7, A23, A27) that survived the 548 tests of round 2.

R3_PASS1 = "PASS with defect rows (1)"
R3_NOTAG = "defect row without exactly one cause tag"
R3_OPEN = "code fence opened here is never closed"
R3_UNTAGGED = "1. src/x.py:4 untagged item"
# DEFECT_FOLD, written out: the letter each listed character is read as.
R3_LOOKALIKES = {
    "d": [0x1D05, 0xF0, 0x111, 0x256, 0x257],
    "D": [0xD0, 0x110],
    "e": [0x1D07, 0x25B, 0x3B5, 0x454, 0x4BD],
    "E": [0x190, 0x404],
    "f": [0x192, 0xA730, 0x3DD],
    "F": [0x191, 0x3DC],
    "c": [0x1D04, 0x188],
    "C": [0x187],
    "t": [0x1D1B, 0x1AB, 0x1AD, 0x167, 0x3C4, 0x442],
    "T": [0x166],
    "s": [0x455, 0xA731, 0x1BD, 0x282],
    "S": [0x405, 0x1A7],
}
R3_PAIRS = [(ltr, chr(cp)) for ltr, cps in R3_LOOKALIKES.items() for cp in cps]


def test_defect_fold_is_the_pinned_set() -> None:
    mod = load_checker()
    assert {chr(k): v for k, v in mod.DEFECT_FOLD.items()} == {ch: ltr for ltr, ch in R3_PAIRS}
    assert len(mod.DEFECT_FOLD) == len(R3_PAIRS) == 35
    # FOLD_MAP, and with it Daniel's residual 7, is not widened by this round
    assert len(mod.FOLD_MAP) == 13


def r3_ids(pairs: list[tuple[str, str]]) -> list[str]:
    return [f"{a}-U+{ord(b):04X}" for a, b in pairs]


R3_HEADING_PAIRS = [(a, b) for a, b in R3_PAIRS if a in "Defcts"]
R3_DASH_PAIRS = [(a, b) for a, b in R3_PAIRS if a in "defct"]


@pytest.mark.parametrize("letter,ch", R3_HEADING_PAIRS, ids=r3_ids(R3_HEADING_PAIRS))
def test_lookalike_letter_in_the_defects_heading_is_folded(
    tmp_path: Path, letter: str, ch: str
) -> None:
    # the heading reads as the canonical `## Defects`: it opens the section (the row is counted, so the PASS is refused
    # for it) and the first-word rule does not fire on it
    code, out = run(tmp_path, qa_body("## " + "Defects".replace(letter, ch, 1), R3_UNTAGGED))
    assert R3_PASS1 in out, out
    assert R3_NOTAG in out, out
    assert NONCANON not in out, out
    assert code == 4, out


@pytest.mark.parametrize("letter,ch", R3_PAIRS, ids=r3_ids(R3_PAIRS))
def test_lookalike_letter_in_a_title_word_opens_the_section(
    tmp_path: Path, letter: str, ch: str
) -> None:
    # a bare bullet is refused only inside a section, so the refusal shows that the title opened one
    base = "DEFECTS" if letter.isupper() else "defects"
    code, out = run(tmp_path, qa_body("## Known " + base.replace(letter, ch, 1), "- a bare bullet"))
    assert NONCANON_SEC in out, out
    assert code == 4, out


@pytest.mark.parametrize("letter,ch", R3_DASH_PAIRS, ids=r3_ids(R3_DASH_PAIRS))
def test_lookalike_letter_in_a_dash_defect_row_is_folded(
    tmp_path: Path, letter: str, ch: str
) -> None:
    # `- deƒect: ...` outside any section is a defect row: counted, so a PASS is refused for it
    word = "defect".replace(letter, ch, 1)
    code, out = run(tmp_path, qa_body("## Notes", f"- {word}: src/x.py:4 hit. cause: judgment-gap"))
    assert R3_PASS1 in out, out
    assert NONCANON not in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "ctl",
    ["\x00", "\x01", "\x07", "\x10", "\x1f", "\x7f", "\x80", "\x9f"],
    ids=["nul", "soh", "bel", "dle", "us", "del", "pad", "apc"],
)
def test_control_character_inside_the_word_is_dropped(tmp_path: Path, ctl: str) -> None:
    code, out = run(tmp_path, qa_body(f"## Def{ctl}ects", R3_UNTAGGED))
    assert R3_PASS1 in out, out
    assert NONCANON not in out, out
    assert code == 4, out
    code, out = run(
        tmp_path, qa_body("## Notes", f"- def{ctl}ect: src/x.py:4 hit. cause: judgment-gap"), "r.md"
    )
    assert R3_PASS1 in out, out
    assert code == 4, out


def test_tab_is_not_dropped_as_a_control_character(tmp_path: Path) -> None:
    # a tab-indented continuation is still a continuation (the drop leaves the tab alone)
    code, out = run(tmp_path, qa_body("## Defects", f"- defect: {HIT}\n\twrapped text", "FAIL"))
    assert code == 0, out


UNLISTED = [
    "ȡefects",
    "Dɘfects",
    "Дefects",
    "Defeʇts",
    "Defectʃ",
    "Dəfects",
    "defecʃ",
    "DEFECTʃ",
    "Dɘfectsʃ",
]


@pytest.mark.parametrize("word", UNLISTED)
def test_unlisted_lookalike_first_word_fails_closed(tmp_path: Path, word: str) -> None:
    # not in DEFECT_FOLD: the ASCII letters alone are within one edit of defects, so the line is refused
    for text in (
        word,
        f"## {word}",
        f"- {word}: src/x.py:4 hit. cause: judgment-gap",
        f"**{word}**",
        f"_{word}_",
        f"1. {word}",
    ):
        code, out = run(tmp_path, qa_body("## Notes", text))
        assert NONCANON in out, (text, out)
        assert code == 4, (text, out)


@pytest.mark.parametrize("word", UNLISTED)
def test_unlisted_lookalike_title_word_opens_a_section(tmp_path: Path, word: str) -> None:
    code, out = run(tmp_path, qa_body(f"## Known {word}", "- a bare bullet"))
    assert NONCANON_SEC in out, out
    assert code == 4, out
    code, out = run(tmp_path, qa_body(f"**Known {word}**", "- a bare bullet"), "b.md")
    assert NONCANON_SEC in out, out
    assert code == 4, out


@pytest.mark.parametrize("word", ["日本語", "Probesé", "Дefault", "Résumé", "Ωmega"])
def test_an_unrelated_non_ascii_word_is_not_refused(tmp_path: Path, word: str) -> None:
    code, out = run(tmp_path, qa_body(f"## {word}", "1. python3 -c 'x' exits 0"))
    assert NONCANON not in out, out
    assert R3_PASS1 not in out, out
    assert code == 0, out


def test_a_lookalike_two_edits_from_defects_is_not_caught(tmp_path: Path) -> None:
    # the stated limit of the fail-closed rule (quality-gates T2): two unlisted look-alikes put the word out of reach
    code, out = run(tmp_path, qa_body("## ȡɘfects", "- a bare bullet"))
    assert NONCANON_SEC not in out, out
    assert code == 0, out


def test_near_is_an_edit_distance_of_one() -> None:
    near = load_checker().near
    assert near("defect", "defect")
    for one in ("efect", "dfect", "defec", "defects", "xdefect", "dxfect", "defecx", "dexect"):
        assert near(one, "defect"), one
        assert near("defect", one), one
    for two in ("fect", "defe", "defectss", "xdefects", "dxfxct", "ect", ""):
        assert not near(two, "defect"), two
        assert not near("defect", two), two


def test_lookalike_needs_a_non_ascii_letter() -> None:
    mod = load_checker()
    assert not mod.lookalike("defects")
    assert mod.lookalike("ȡefects")
    assert mod.lookalike("defectʃ")
    assert mod.lookalike("ȡefect")
    assert not mod.lookalike("ȡɘfects")
    assert not mod.lookalike("ȡɘ")


# ------------------------------------------------ a fence that never closes refuses the record


def open_line(text: str, mark: str) -> int:
    return next(n for n, ln in enumerate(text.splitlines(), 1) if ln.startswith(mark))


@pytest.mark.parametrize(
    "lead",
    [
        "```\nnotes\n",
        "~~~\nnotes\n```\n",  # a tilde fence is not closed by backticks
        "```span``` and more text\n",  # an inline span at the start of a line opens a fence
        "````\nnotes\n```\n",  # a shorter closer does not close
        "```\n```x\n",  # a closer carries no text
    ],
    ids=[
        "backticks",
        "tilde-closed-by-backticks",
        "inline-span",
        "short-closer",
        "closer-with-text",
    ],
)
def test_a_fence_never_closed_before_defects_refuses_the_qa_record(
    tmp_path: Path, lead: str
) -> None:
    text = f"RESULT: PASS\n{HEAD}\n## Gate\n{drift()}\n{lead}## Defects\n{R3_UNTAGGED}\n"
    code, out = run(tmp_path, text)
    n = next(i for i, ln in enumerate(text.splitlines(), 1) if ln[:3] in ("```", "~~~"))
    assert f":{n}: {R3_OPEN}" in out, out
    assert code == 4, out


def test_a_qa_record_that_ends_inside_a_fence_is_refused(tmp_path: Path) -> None:
    text = qa_body("## Defects", "Defects: none\n```\nlate notes")
    code, out = run(tmp_path, text)
    assert f":{open_line(text, '```')}: {R3_OPEN}" in out, out
    assert code == 4, out


def test_a_judge_verdict_that_ends_inside_a_fence_is_refused(tmp_path: Path) -> None:
    text = judge(0, "| A1 | UPHELD | x.py:1 | a | b |\n```\nnotes")
    code, out = run(tmp_path, text)
    assert f":{open_line(text, '```')}: {R3_OPEN}" in out, out
    assert code == 4, out


def test_an_evolve_report_with_a_fence_never_closed_is_refused(tmp_path: Path) -> None:
    text = "```\nLESSON | layer: routing | evidence: a.md:1 - x | fix: b.md - y\n"
    code, out = run(tmp_path, text)
    assert f":1: {R3_OPEN}" in out, out
    assert code == 4, out


@pytest.mark.parametrize("closer", ["```", "````", "```  "])
def test_a_fence_closed_by_a_matching_closer_is_accepted(tmp_path: Path, closer: str) -> None:
    code, out = run(tmp_path, qa_body("## Defects", f"Defects: none\n```\nnotes\n{closer}"))
    assert R3_OPEN not in out, out
    assert code == 0, out
    code, out = run(tmp_path, qa_body("## Defects", "Defects: none\n~~~~\nnotes\n~~~~~"), "t.md")
    assert R3_OPEN not in out, out
    assert code == 0, out


# ------------------------------------------- a numbered file:line row is a defect row under any heading


@pytest.mark.parametrize(
    "heading", ["## Findings", "## Issues", "## Probes", "### Notes", "**Findings**"]
)
@pytest.mark.parametrize(
    "row",
    ["1. src/x.py:4 untagged item", "10. src/x.py:4 untagged item", "2) src/x.py:4 untagged item"],
)
def test_numbered_file_line_row_under_any_heading_is_a_defect_row(
    tmp_path: Path, heading: str, row: str
) -> None:
    code, out = run(tmp_path, qa_body(heading, row))
    assert R3_PASS1 in out, out
    assert R3_NOTAG in out, out
    assert code == 4, out


def test_numbered_file_line_row_with_no_heading_at_all_is_a_defect_row(tmp_path: Path) -> None:
    text = f"RESULT: PASS\n{HEAD}\n## Gate\n{drift()}\n1. src/x.py:4 untagged item\n"
    code, out = run(tmp_path, text)
    assert R3_PASS1 in out, out
    assert code == 4, out


def test_tagged_numbered_row_under_a_findings_heading_is_a_row_in_a_fail(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Findings", f"1. {HIT}", "FAIL"))
    assert code == 0, out
    code, out = run(tmp_path, qa_body("## Findings", "1. src/x.py:4 hit", "FAIL"), "u.md")
    assert R3_NOTAG in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "item",
    [
        "1. Run the tests",
        "1. step at 12:30 sharp",
        "3) check the build",
        "- src/x.py:4 a bullet",
        "  1. src/x.py:4 indented",
    ],
    ids=["no-location", "no-colon-token", "paren-item", "bullet", "indented"],
)
def test_other_list_items_outside_a_defects_section_are_not_rows(tmp_path: Path, item: str) -> None:
    code, out = run(tmp_path, qa_body("## Findings", item))
    assert R3_PASS1 not in out, out
    assert code == 0, out


def test_numbered_file_line_line_in_a_fence_outside_a_defects_section_is_output(
    tmp_path: Path,
) -> None:
    code, out = run(tmp_path, qa_body("## Findings", "```\n1. src/x.py:4 output line\n```"))
    assert code == 0, out


# ------------------------------------------------ survivors of the round-2 mutant run (F7, A23, A27)


@pytest.mark.parametrize("under", ["---", "==="])
def test_two_digit_numbered_row_over_an_underline_is_counted(tmp_path: Path, under: str) -> None:
    # F7: an item number of two digits is an item, so the line above `---` is not a setext heading
    code, out = run(tmp_path, qa_body("## Defects", f"10. src/x.py:4 untagged item\n{under}"))
    assert R3_PASS1 in out, out
    assert R3_NOTAG in out, out
    assert code == 4, out


def test_two_digit_numbered_row_in_a_fence_in_a_defects_section_is_counted(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Defects", "```\n10. src/x.py:4 untagged item\n```"))
    assert R3_PASS1 in out, out
    assert R3_NOTAG in out, out
    assert code == 4, out


def test_a_singular_bold_title_opens_no_section(tmp_path: Path) -> None:
    # A23: only the plural names a Defects section, so a bare bullet under `**Known defect**` is not refused
    code, out = run(tmp_path, qa_body("**Known defect**", "- a bare bullet"))
    assert NONCANON_SEC not in out, out
    assert code == 0, out
    code, out = run(tmp_path, qa_body("**Known defects**", "- a bare bullet"), "p.md")
    assert NONCANON_SEC in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "reason",
    [
        "defect found; missing tool: ruff",
        "found: no git",
        "x candidate moved during QA",
        "the candidate differs from the brief",
    ],
)
def test_a_process_reason_must_start_the_reason(tmp_path: Path, reason: str) -> None:
    # A27: `.match`, not `.search`; a reason that only mentions a listed phrase is refused
    text = qa_body("## Defects", "Defects: none", "FAIL").replace(
        "RESULT: FAIL", f"RESULT: FAIL — {reason}", 1
    )
    code, out = run(tmp_path, text)
    assert "FAIL reason is not a process reason" in out, out
    assert code == 4, out


# ------------------------------------------- fix round 4: the numbered-row location, the Q7 line, residual 13

SITS_OUTSIDE = "sits outside a Defects section"


@pytest.mark.parametrize(
    "row",
    [
        "1. `src/x.py:4` untagged item",
        "1. **src/x.py:4** untagged item",
        "1. [src/x.py:4](x) untagged item",
        "1. [**src/x.py:4**](x) untagged item",
        "1. src/x.py:4: untagged item",
        "1. src/x.py:4-9 untagged item",
        "1. src/x.py:4, untagged item",
        "1. src/x.py:4. untagged item",
        "1. (src/x.py:4) untagged item",
        "1. ./src/x.py:4 untagged item",
        "1. src/x.py:4",
        "1.\tsrc/x.py:4 untagged item",
        "1.  src/x.py:4 untagged item",
        "2) `src/x.py:4`: untagged item",
        "10. x.py:4 untagged item",
        '1. "src/x.py:4" untagged item',
        "1. 'src/x.py:4' untagged item",
        "1. [src/x.py:4] untagged item",
        "1. ** src/x.py:4** untagged item",
        "1. ( src/x.py:4 ) untagged item",
        "1. [ src/x.py:4 ] untagged item",
        '1. " src/x.py:4" untagged item',
        "1. ' src/x.py:4' untagged item",
        "1. **\tsrc/x.py:4** untagged item",
        "1. src/Makefile:4 untagged item",
    ],
)
@pytest.mark.parametrize("heading", ["## Findings", "### Notes", "**Changes**"])
def test_numbered_location_in_any_spelling_outside_defects_blocks_a_pass(
    tmp_path: Path, heading: str, row: str
) -> None:
    code, out = run(tmp_path, qa_body(heading, row))
    assert R3_PASS1 in out, out
    assert SITS_OUTSIDE in out, out
    assert code == 4, out


@pytest.mark.parametrize("row", ["1. `src/x.py:4` untagged item", "1.\tsrc/x.py:4: untagged item"])
def test_numbered_location_with_no_heading_at_all_blocks_a_pass(tmp_path: Path, row: str) -> None:
    text = f"RESULT: PASS\n{HEAD}\n## Gate\n{drift()}\n{row}\n"
    code, out = run(tmp_path, text)
    assert R3_PASS1 in out, out
    assert code == 4, out


def test_wrapped_numbered_location_needs_only_a_cause_tag_in_a_fail(tmp_path: Path) -> None:
    row = "1. `src/x.py:4` hit cause: judgment-gap"
    code, out = run(tmp_path, qa_body("## Findings", row, "FAIL"))
    assert "without a file:line location" not in out, out
    assert code == 0, out
    code, out = run(tmp_path, qa_body("## Findings", "1. `src/x.py:4` hit", "FAIL"), "w.md")
    assert R3_NOTAG in out, out
    assert code == 4, out


@pytest.mark.parametrize(
    "item",
    [
        "1. 12:30 start of run",
        "1. localhost:8080 up",
        "1. 3:1 ratio",
        "1. exit:0 for every gate",
        "1. 3.14:2 ratio",
        "1. v:1 first",
        "1. C:\\x\\y.py:12",
        "1. `exit:0`",
        "1. [12:30](x) start",
        "1. src/x.py:foo broke",
        "1. x.py:4a broke",
    ],
)
def test_numbered_items_that_are_not_a_path_are_not_rows(tmp_path: Path, item: str) -> None:
    code, out = run(tmp_path, qa_body("## Findings", item))
    assert R3_PASS1 not in out, out
    assert code == 0, out


def test_numbered_path_in_a_fence_outside_defects_stays_output(tmp_path: Path) -> None:
    code, out = run(tmp_path, qa_body("## Findings", "```\n1. `src/x.py:4` out\n```"))
    assert code == 0, out


def test_a_closed_fence_before_an_unclosed_one_names_the_unclosed_line(tmp_path: Path) -> None:
    # Q7: `opened = n` (the last opener), not `opened = opened or n` (the first one)
    text = (
        f"RESULT: PASS\n{HEAD}\n## Gate\n{drift()}\n## Defects\nDefects: none\n"
        "```\nclosed\n```\nplain\n~~~\nnever closed\n"
    )
    lines = text.splitlines()
    closed = lines.index("```") + 1
    unclosed = lines.index("~~~") + 1
    assert closed < unclosed
    code, out = run(tmp_path, text)
    assert f":{unclosed}: {R3_OPEN}" in out, out
    assert f":{closed}: {R3_OPEN}" not in out, out
    assert code == 4, out


CHANGED_R4 = {
    ".claude/agents/boundary-qa.md": [
        "To list changed files in a PASS, use bullets, a table or the `declared=` count of the drift row",
        "never a column-0 numbered list whose items start with `file:line`",
    ],
    "skills/finhub-harness/references/qa-agent-guide.md": [
        "To list changed files in a PASS, use bullets, a table or the `declared=` count of the drift row",
        "never a column-0 numbered list whose items start with `file:line`",
    ],
    "skills/finhub-harness/references/quality-gates.md": [
        "To list changed files in a PASS, use bullets, a table or the `declared=` count of the drift row",
        "never a column-0 numbered list whose items start with `file:line`",
        "For that rule the location is read after bold and backtick markup is stripped",
        "and then by a space, colon, comma, dot, dash, close parenthesis, close bracket, closing quote or the end of the line",
        "needs a path-like token (a slash or a dot and a letter)",
        "`1. 12:30 start`, `1. localhost:8080 up`, `1. 3:1 ratio` and `1. exit:0` are ordinary list items",
        "a numbered row outside a Defects section is refused with the message `the row sits outside a Defects section`",
        "  13. Single-symbol look-alikes of a letter of `defect` or `defects` that are not letters and are not folded",
        "invisible symbols inside the word (U+2800, U+1D159, U+FFFC, U+2065)",
        "two unlisted look-alike letters in one word (two U+0259; U+1F133 plus U+212E)",
        "the one-edit fallback and the fold list do not cover them, and `two or more edits away` understates it",
        "the eighteen routes below",
        "  14. False refusals in a PASS (fail closed): a numbered item whose first token holds a slash or a dot followed by a letter but is not a file path",
        "`1. example.com:443`, `1. docker.io:5000`, `1. pod/web:3`, `1. 3/4:5` and `1. am/pm:3`",
        "  15. Numbered-row spellings that pass because the rule needs a path-like first token at column 0",
        "a Windows path (accepted on purpose and pinned), a block quote, `<src/x.py:4>` and an extensionless name such as `Makefile:4`",
        "  16. Fail-open terminators (accepted by Daniel, over the builder's advice)",
        "followed by `;`, `?`, `!`, `>`, `}`, `|` or an unspaced em or en dash is not read as a defect row, so an untagged one passes a PASS",
        "This is a fail-open, not a false refusal, and it is not closed.",
        "  17. The generated QA agent text in `skills/finhub-harness/SKILL.md` Step 3 states four things and omits the changed-files sentence",
        "  18. Test gaps: three mutants of `finding_tags.py` survive the suite although the shipped code is correct.",
        'Z6 (`MARKUP.sub("", body)` changed to `MARKUP.sub(" ", body)`',
        "Z8 (`:\\d+` changed to `:\\d*` in the path-and-line pattern)",
        "Z17 (the `LOCATION` pattern left unanchored",
        "Routes 14 and 15 come from the fifth boundary-qa run, which returned RESULT: FAIL",
        "an explicit override of the rule that nothing is committed before boundary-qa returns RESULT: PASS",
    ],
    "CLAUDE.md": [
        "eighteen residual routes are named and not closed in quality-gates 3-8 Does-not-cover",
        "the fifth boundary-qa run on the final tree returned RESULT: FAIL; Daniel overrode the no-commit-before-PASS rule on 2026-10-12 and accepted residuals 14-18, a fail-open terminator rule among them",
        "a numbered `file:line` row is closed in code for a backticked, bold, link-wrapped, colon-ended, range, comma-ended or tab-separated location",
    ],
}


@pytest.mark.parametrize("rel,phrase", [(k, p) for k, v in CHANGED_R4.items() for p in v])
def test_fix_round_4_prose_pin(rel: str, phrase: str) -> None:
    assert phrase in (REPO / rel).read_text(encoding="utf-8"), rel


def test_numbered_row_outside_then_fenced_defect_without_location(tmp_path: Path) -> None:
    # the "outside" flag belongs to one line: a later fenced row is still held to the strict location rule
    body = (
        "1. `src/x.py:4` hit cause: judgment-gap\n```\n- defect: nowhere cause: judgment-gap\n```"
    )
    code, out = run(tmp_path, qa_body("## Findings", body, "FAIL"))
    assert "without a file:line location" in out, out
    assert code == 4, out
