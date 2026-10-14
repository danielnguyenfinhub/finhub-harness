# adapted from references/openrig/scripts/gate-lane-ledger.mjs:60-85 (Apache-2.0)
"""Proof for OR-S6: skills/finhub-harness/scripts/waiver_ledger.py, the WAIVERS.md at the repo root, and the
prose of quality-gates.md section 3-9, .claude/agents/boundary-qa.md and the orchestrator step.
The clock is injected as a function argument; the command line has no way to set it, so the one test that
uses the real clock builds its dates from today. Each refusal test asserts the checker's own message
before the exit code, so a rule that stops firing fails at that message."""

from __future__ import annotations

import importlib.machinery
import re
import shutil
import subprocess
import sys
import types
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/waiver_ledger.py"
FINDING_TAGS = REPO / "skills/finhub-harness/scripts/finding_tags.py"
CANDIDATE_ID = REPO / "skills/finhub-harness/scripts/candidate_id.py"
QUALITY_GATES = REPO / "skills/finhub-harness/references/quality-gates.md"
BOUNDARY_QA = REPO / ".claude/agents/boundary-qa.md"
ORCHESTRATOR = REPO / ".claude/skills/master-finhub-orchestrator/SKILL.md"
LEDGER = REPO / "WAIVERS.md"
CLAUDE_MD = REPO / "CLAUDE.md"
TODAY = date(2026, 10, 14)
# The seed as built on 2026-10-14. Every test of the seed reads this copy, never the live file, so a
# renewal or a closure that edits WAIVERS.md leaves the suite green. The build-time comparison of the
# live file with this copy is a QA command (quality-gates 3-9), not a test.
SEED = """<!-- adapted from references/openrig/scripts/gate-lane-ledger.mjs:14-112 (Apache-2.0): see skills/finhub-harness/references/quality-gates.md section 3-9 for the rules. -->
# Waivers

Accepted gaps, one row each. Check with `python3 skills/finhub-harness/scripts/waiver_ledger.py check WAIVERS.md`.

| id | scope | gap | owner | receipt | granted | expires |
|---|---|---|---|---|---|---|
| OR-D4-R01 | quality-gates.md 3-8 residual 1 | REJECTED written as a symbol only or as the word REJECT is not counted | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R02 | quality-gates.md 3-8 residual 2 | A verdict written as prose on a line with no pipe is not counted | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R03 | quality-gates.md 3-8 residual 3 | REJECTED split across a line break inside a cell is not counted | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R04 | quality-gates.md 3-8 residual 4 | An HTML comment with angle brackets inside the word hides it | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R05 | quality-gates.md 3-8 residual 5 | Invisible characters that are neither Cf nor Mn inside the word are not dropped | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R06 | quality-gates.md 3-8 residual 6 | Dotted or hyphenated letters (R.E.J.E.C.T.E.D) are not counted | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R07 | quality-gates.md 3-8 residual 7 | Look-alike letters outside the fold map are not read as Latin letters | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R08 | quality-gates.md 3-8 residual 8 | The UNVERIFIED count on the TOTALS line is not reconciled with the table | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R09 | quality-gates.md 3-8 residual 9 | The resume route (the Base file) is a prose-only control | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R10 | quality-gates.md 3-8 residual 10 | The candidate id does not read .git/info/exclude | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R11 | quality-gates.md 3-8 residual 11 | A fenced line with a pipe, no edge pipe and no REJECTED is not refused | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R12 | quality-gates.md 3-8 residual 12 | Four historic judge records are refused and left unedited | daniel | words: "Accept the residuals in writing" (reply to: accept the residuals in writing and build with them named, or authorise a sixth round) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R13 | quality-gates.md 3-8 residual 13 | Symbol look-alikes and invisible symbols inside the word Defects are not folded | daniel | words: "proceed" (answered a two-option question; the acceptance record says Claude interpreted it as the recommended option and that residual 13 must be withdrawn if that reading is wrong; Daniel has not confirmed) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R14 | quality-gates.md 3-8 residual 14 | False refusals in a PASS for numbered items whose first token looks like a path | daniel | words: "2" (option 2: accept the false refusals and the observation spellings as residuals 14 and 15; date of reply not in the record, between 2026-10-11 and 2026-10-12) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R15 | quality-gates.md 3-8 residual 15 | Numbered-row spellings that pass because the rule needs a path-like first token | daniel | words: "2" (option 2: accept the false refusals and the observation spellings as residuals 14 and 15; date of reply not in the record, between 2026-10-11 and 2026-10-12) 2026-10-11 | 2026-10-11 | 2027-01-09 |
| OR-D4-R16 | quality-gates.md 3-8 residual 16 | Fail-open terminators after the line number let an untagged numbered row pass a PASS | daniel | words: "2" (option 2: ship now with the three open items as named residuals) 2026-10-12 | 2026-10-12 | 2027-01-10 |
| OR-D4-R17 | quality-gates.md 3-8 residual 17 | The generated QA agent text in SKILL.md Step 3 lacks the changed-files sentence | daniel | words: "2" (option 2: ship now with the three open items as named residuals) 2026-10-12 | 2026-10-12 | 2027-01-10 |
| OR-D4-R18 | quality-gates.md 3-8 residual 18 | Mutants Z6, Z8 and Z17 of finding_tags.py survive the test suite | daniel | words: "2" (option 2: ship now with the three open items as named residuals) 2026-10-12 | 2026-10-12 | 2027-01-10 |
"""
HEADER = (
    "| id | scope | gap | owner | receipt | granted | expires |\n|---|---|---|---|---|---|---|\n"
)


def load() -> Any:
    loader = importlib.machinery.SourceFileLoader("waiver_ledger_under_test", str(SCRIPT))
    mod = types.ModuleType(loader.name)
    loader.exec_module(mod)
    return mod


M = load()


def row(
    id: str = "W-001",
    owner: str = "daniel",
    receipt: str | None = None,
    granted: str = "2026-10-01",
    expires: str = "2026-12-01",
    scope: str = "s",
) -> str:
    receipt = f'words: "ok" {granted}' if receipt is None else receipt
    return f"| {id} | {scope} | a gap | {owner} | {receipt} | {granted} | {expires} |\n"


def check(*rows: str, today: date = TODAY, head: str = HEADER) -> tuple[int, str]:
    code, lines = M.check_text("L.md", head + "".join(rows), today)
    return code, "\n".join(lines)


def run_cli(*args: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode, p.stdout + p.stderr


# ---------------------------------------------------------------- positive controls


def test_clean_ledger_names_every_waiver() -> None:
    code, out = check(row("W-001"), row("W-002", scope="second scope"))
    assert code == 0, f"a valid ledger must be clean: {out}"
    assert "WAIVERS: 2 active, 0 expired, 0 other problem(s) (each is named)" in out, out
    assert "W-001 owner daniel expires 2026-12-01 (s)" in out, out
    assert "W-002 owner daniel expires 2026-12-01 (second scope)" in out, out
    assert out.endswith("STATE: CLEAN"), out


def test_empty_ledger_is_clean_and_says_so() -> None:
    code, out = check()
    assert code == 0, f"a ledger with no rows must be clean: {out}"
    assert "WAIVERS: 0 active, 0 expired, 0 other problem(s) (no exclusions)" in out, out


def test_lifetime_of_exactly_the_ceiling_is_accepted() -> None:
    code, out = check(row(granted="2026-10-01", expires="2026-12-30"))
    assert code == 0, f"a lifetime of exactly 90 days is allowed: {out}"


def test_a_waiver_that_expires_the_day_it_is_granted_is_allowed() -> None:
    code, out = check(row(granted="2026-10-14", expires="2026-10-14"))
    assert code == 0, f"an expiry equal to the grant date is allowed: {out}"


def test_expiry_day_itself_is_still_active() -> None:
    code, out = check(row(granted="2026-08-01", expires="2026-10-14"))
    assert code == 0, f"the expiry day itself is still active: {out}"


@pytest.mark.parametrize(
    "receipt",
    [
        'words: "Accept the residuals in writing" 2026-10-01',
        'words: "2" (option 2: ship now with the open items named) 2026-10-01',
        "pr: #12 2026-10-01",
        "pr: https://example.test/pull/12 2026-10-01",
    ],
)
def test_a_dated_quote_or_a_dated_pr_reference_is_a_receipt(receipt: str) -> None:
    code, out = check(row(receipt=receipt))
    assert code == 0, f"a dated quote or a dated pr reference is a receipt: {out}"


# ---------------------------------------------------------------- expiry is red


def test_expired_waiver_is_red() -> None:
    code, out = check(row(granted="2026-08-01", expires="2026-10-13"))
    assert code == 4, f"an expired waiver must be red: {out}"
    assert "EXPIRED: W-001 expired on 2026-10-13 (1 day(s) ago)" in out, out
    assert out.endswith("STATE: RED"), out
    assert "W-001 owner daniel" not in out, "an expired waiver is not listed as active"
    assert "WAIVERS: 0 active, 1 expired" in out, out


def test_lifetime_over_the_ceiling_is_refused() -> None:
    code, out = check(row(granted="2026-10-01", expires="2027-01-01"))
    assert code == 4, f"a lifetime over the ceiling must be refused: {out}"
    assert "lifetime 92 days exceeds ceiling 90" in out, out


def test_granted_today_or_tomorrow_is_accepted() -> None:
    for granted, expires in (("2026-10-14", "2026-12-01"), ("2026-10-15", "2026-12-01")):
        code, out = check(row(granted=granted, expires=expires))
        assert code == 0, f"a grant dated {granted} is accepted (one day of clock slack): {out}"


def test_granted_two_days_ahead_is_refused() -> None:
    code, out = check(row(granted="2026-10-16", expires="2026-11-16"))
    assert code == 4, f"a grant dated two days ahead must be refused: {out}"
    assert "granted 2026-10-16 is more than 1 day after today" in out, out


def test_a_refused_row_is_not_listed_as_active() -> None:
    code, out = check(row(owner="x"))
    assert (
        "  W-001 owner" not in out
    ), f"a refused row must not be listed as an active waiver: {out}"
    assert "WAIVERS: 0 active, 0 expired, 1 other problem(s)" in out, out
    assert code == 4, out


def test_expiry_before_the_grant_is_named() -> None:
    code, out = check(row(granted="2026-10-10", expires="2026-10-05"))
    assert "expires is before granted" in out, f"an expiry before the grant must be named: {out}"
    assert code == 4, out


def test_february_30_is_not_a_calendar_date() -> None:
    code, out = check(row(granted="2026-08-01", expires="2026-02-30"))
    assert "expires must be a calendar date YYYY-MM-DD" in out, f"February 30 is not a date: {out}"
    assert code == 4, out


@pytest.mark.parametrize("bad", ["2026-1-5", "2026-10-14T00:00", "20261014", "2026-13-01", "soon"])
def test_other_non_dates_are_refused(bad: str) -> None:
    code, out = check(row(granted="2026-08-01", expires=bad))
    assert "expires must be a calendar date YYYY-MM-DD" in out, f"{bad!r} is not a date: {out}"
    assert code == 4, out


def test_notice_comes_14_days_before_expiry_and_is_not_red() -> None:
    code, out = check(row(granted="2026-08-01", expires="2026-10-28"))
    assert "NOTICE: W-001 expires in 14 day(s)" in out, f"14 days out gets a notice: {out}"
    assert code == 0, out
    code, out = check(row(granted="2026-08-01", expires="2026-10-29"))
    assert "NOTICE" not in out, f"15 days out gets no notice: {out}"
    assert code == 0, out


# ---------------------------------------------------------------- the schema


def test_every_blank_cell_is_named() -> None:
    for col in M.COLUMNS:
        cells = {
            "id": "W-001",
            "scope": "s",
            "gap": "a gap",
            "owner": "daniel",
            "receipt": 'words: "ok" 2026-10-01',
            "granted": "2026-10-01",
            "expires": "2026-12-01",
        }
        cells[col] = ""
        line = "| " + " | ".join(cells[c] for c in M.COLUMNS) + " |\n"
        code, out = check(line)
        assert f"missing {col}" in out, f"a blank {col} cell must be named missing: {out}"
        assert code == 4, out


@pytest.mark.parametrize("owner", ["boundary-qa", "runtime-builder", "Daniel", "daniel, claude"])
def test_an_agent_name_is_not_an_owner(owner: str) -> None:
    code, out = check(row(owner=owner))
    assert "owner must be one of: daniel" in out, f"{owner!r} is not an owner: {out}"
    assert code == 4, out


def test_invalid_row_exits_4() -> None:
    code, _ = check(row(owner="x"))
    assert code == 4, "an invalid row must exit 4, not 0"


@pytest.mark.parametrize(
    "receipt",
    [
        "daniel agreed",
        'words: "" 2026-10-01',
        "words: 2026-10-01",
        'words: "x"',
        "pr: 2026-10-01",
        'words: "x" 2026-10-01 later',
    ],
)
def test_a_receipt_that_is_not_a_quote_or_a_pr_reference_is_refused(
    receipt: str,
) -> None:
    code, out = check(row(receipt=receipt))
    assert "receipt must be words" in out, f"{receipt!r} is no receipt: {out}"
    assert code == 4, out


def test_receipt_date_must_equal_granted() -> None:
    code, out = check(row(receipt='words: "ok" 2026-09-01', granted="2026-10-01"))
    assert (
        "receipt date 2026-09-01 differs from granted 2026-10-01" in out
    ), f"a bumped granted date with an old receipt must be refused: {out}"
    assert code == 4, out


def test_duplicate_id_is_refused() -> None:
    code, out = check(row("W-001"), row("W-001"))
    assert "duplicate id W-001" in out, f"a repeated id must be refused: {out}"
    assert code == 4, out


@pytest.mark.parametrize("bad_id", ["w-1", "X", "HAS SPACE", "a" * 40])
def test_malformed_id_is_refused(bad_id: str) -> None:
    code, out = check(row(bad_id))
    assert "id must match [A-Z][A-Z0-9-]{2,31}" in out, f"{bad_id!r} is no id: {out}"
    assert code == 4, out


def test_wrong_cell_count_is_refused() -> None:
    eight = (
        "| W-001 | s | g | daniel | "
        + 'words: "ok" 2026-10-01'
        + " | 2026-10-01 | 2026-12-01 | extra |\n"
    )
    six = "| W-001 | s | g | daniel | " + 'words: "ok" 2026-10-01' + " | 2026-10-01 |\n"
    no_end = (
        "| W-001 | s | g | daniel | " + 'words: "ok" 2026-10-01' + " | 2026-10-01 | 2026-12-01\n"
    )
    for line, got in ((eight, 8), (six, 6), (no_end, 0)):
        code, out = check(line)
        assert (
            f"expected 7 cells between pipes, got {got}" in out
        ), f"a row with {got} cells must be refused: {out}"
        assert code == 4, out


# ---------------------------------------------------------------- the file and the command line


def test_a_file_with_no_table_or_a_wrong_header_is_a_usage_error() -> None:
    for text in ("no table here\n", "| id | scope |\n|---|---|\n", "# Waivers\n"):
        with pytest.raises(M.Usage):
            M.check_text("L.md", text, TODAY)


def test_cli_exit_codes_use_the_real_clock(tmp_path: Path) -> None:
    t = date.today()
    ok = tmp_path / "ok.md"
    g = (t - timedelta(days=10)).isoformat()
    ok.write_text(HEADER + row(granted=g, expires=(t + timedelta(days=30)).isoformat()))
    code, out = run_cli("check", str(ok))
    assert code == 0 and "STATE: CLEAN" in out, f"a live waiver is clean on the real clock: {out}"
    old = tmp_path / "old.md"
    g = (t - timedelta(days=40)).isoformat()
    old.write_text(HEADER + row(granted=g, expires=(t - timedelta(days=1)).isoformat()))
    code, out = run_cli("check", str(old))
    assert "EXPIRED: W-001" in out, f"a waiver past its expiry is red on the real clock: {out}"
    assert code == 4, out


def test_cli_bad_calls_exit_2_and_there_is_no_clock_option(tmp_path: Path) -> None:
    f = tmp_path / "w.md"
    f.write_text(HEADER + row(granted="2020-01-01", expires="2020-02-01"))
    for args in (
        ("check", str(f), "--today", "2020-01-15"),
        ("check", "--today", "2020-01-15", str(f)),
        ("check",),
        ("check", str(tmp_path / "missing.md")),
        ("verify", str(f)),
    ):
        code, out = run_cli(*args)
        assert code == 2, f"{args} must be a bad call, never a clean run: {out}"
    nothing = tmp_path / "n.md"
    nothing.write_text("# no table\n")
    code, out = run_cli("check", str(nothing))
    assert code == 2 and "no ledger table" in out, out


def test_the_process_time_zone_is_the_one_clock_input(tmp_path: Path) -> None:
    f = tmp_path / "w.md"
    f.write_text(HEADER + row(granted="2020-01-01", expires="2020-02-01"))
    if not Path("/usr/share/zoneinfo/Pacific/Kiritimati").exists():
        pytest.skip("no zoneinfo database")
    seen = set()
    for tz in ("Pacific/Kiritimati", "Etc/GMT+12"):
        p = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "check", str(f)],
            capture_output=True,
            text=True,
            check=False,
            env={"TZ": tz, "PATH": "/usr/bin:/bin"},
        )
        seen.add(p.stdout.splitlines()[0])
    assert len(seen) == 2, f"TZ must move the TODAY line (the only clock input): {seen}"


# ---------------------------------------------------------------- the live ledger and the seed


def refused(text: str, today: date) -> list[str]:
    """Problem lines other than EXPIRED: the live-file rule. An expired row is the gate's business."""
    _, lines = M.check_text("WAIVERS.md", text, today)
    return [x for x in lines if re.match(r"WAIVERS\.md:\d+: ", x) and "EXPIRED: " not in x]


def test_the_shipped_ledger_parses_with_no_refused_row() -> None:
    bad = refused(LEDGER.read_text(encoding="utf-8"), date.today())
    assert not bad, f"the shipped WAIVERS.md must have no refused row: {bad}"


def test_a_ledger_with_a_row_deleted_passes_the_live_rule() -> None:
    kept = "".join(x for x in SEED.splitlines(keepends=True) if "| OR-D4-R13 |" not in x)
    assert kept != SEED, "the fixture must hold R13"
    code, lines = M.check_text("WAIVERS.md", kept, TODAY)
    assert code == 0, f"closing a gap (a row deleted) must leave a clean ledger: {lines[:2]}"
    assert not refused(kept, date(2027, 1, 12)), "a deleted row leaves no refused row"


def test_a_ledger_with_renewed_dates_passes_the_live_rule() -> None:
    renewed = re.sub(
        r"\| OR-D4-R(0[1-9]|1[0-5]) \|(.*)\| 2026-10-11 \| 2027-01-09 \|",
        lambda m: f"| OR-D4-R{m.group(1)} |"
        + m.group(2).replace("2026-10-11", "2027-01-09")
        + "| 2027-01-09 | 2027-04-09 |",
        SEED,
    )
    assert renewed != SEED, "the renewal must change the fixture"
    code, lines = M.check_text("WAIVERS.md", renewed, date(2027, 1, 10))
    out = "\n".join(lines)
    assert code == 0, f"a renewed ledger must be clean the day after the old expiry: {out}"
    assert not refused(renewed, date(2027, 1, 10)), f"a renewal must leave no refused row: {out}"


def test_the_seed_is_valid_on_the_build_date() -> None:
    code, lines = M.check_text("WAIVERS.md", SEED, TODAY)
    out = "\n".join(lines)
    assert code == 0, f"the seed must be clean on the build date: {out}"
    assert "WAIVERS: 18 active, 0 expired" in out, out


def test_the_seed_rows_match_the_residuals_in_quality_gates() -> None:
    text = QUALITY_GATES.read_text(encoding="utf-8")
    start = text.index("- Accepted residuals (Daniel")
    nxt = re.search(r"^- ", text[start + 1 :], re.MULTILINE)
    assert nxt is not None, "the residuals bullet must be followed by another bullet"
    listed = {
        int(n)
        for n in re.findall(r"^  (\d+)\. ", text[start : start + 1 + nxt.start()], re.MULTILINE)
    }
    seed = {int(n) for n in re.findall(r"^\| OR-D4-R(\d\d) \|", SEED, re.MULTILINE)}
    assert (
        listed == seed
    ), f"the seed rows and the numbered residuals of 3-8 must match: {listed ^ seed}"
    assert len(listed) == 18, listed


def test_the_cliff_is_red_for_fifteen_rows_then_all_eighteen() -> None:
    code, lines = M.check_text("WAIVERS.md", SEED, date(2027, 1, 9))
    assert code == 0, f"the last seed day is still clean: {lines[:3]}"
    code, lines = M.check_text("WAIVERS.md", SEED, date(2027, 1, 10))
    out = "\n".join(lines)
    assert code == 4 and out.count("EXPIRED: ") == 15, f"15 rows expire on 2027-01-10: {out}"
    code, lines = M.check_text("WAIVERS.md", SEED, date(2027, 1, 11))
    assert "\n".join(lines).count("EXPIRED: ") == 18, "all 18 rows are expired on 2027-01-11"
    code, lines = M.check_text("WAIVERS.md", SEED, date(2026, 12, 26))
    assert "\n".join(lines).count("NOTICE: ") == 15, "15 notices 14 days before the first expiry"


def test_the_weak_seed_receipts_say_so() -> None:
    rows = {
        m.group(1): m.group(0) for m in re.finditer(r"^\| (OR-D4-R\d\d) \|.*$", SEED, re.MULTILINE)
    }
    assert "Daniel has not confirmed" in rows["OR-D4-R13"], "R13 must say Daniel has not confirmed"
    assert "answered a two-option question" in rows["OR-D4-R13"], "R13 must say what it answered"
    for rid in ("OR-D4-R14", "OR-D4-R15"):
        assert (
            "date of reply not in the record" in rows[rid]
        ), f"{rid} must say its date is not in the record"


# ---------------------------------------------------------------- meeting the other checks

CAND = "git:1a2b3c4d5e6f+0f1e2d3c4b5a6978"
EXCL = "5e6f7a8b9c0d"
QA_HEAD = f"CANDIDATE: {CAND} n=214 excludes=_workspace/\nBASE: git:1a2b3c4d5e6f excl={EXCL}\nCARRIED: -\n"
QA_GATE = (
    f"| drift: declared=3 changed=3 undeclared=- flags=0 excl={EXCL} on={CAND} | git diff | 0 | 3 paths |\n"
    "| python3 skills/finhub-harness/scripts/waiver_ledger.py check WAIVERS.md | 0 | STATE: CLEAN |\n"
)


def qa_report(accepted: str) -> str:
    return (
        f"RESULT: PASS\n{QA_HEAD}\n## Gate\n{QA_GATE}\n## Defects\nDefects: none\n\n"
        f"## Accepted gaps\n{accepted}"
    )


def finding_tags(tmp_path: Path, text: str) -> tuple[int, str]:
    f = tmp_path / "report.md"
    f.write_text(text, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-B", str(FINDING_TAGS), "check", str(f)],
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode, p.stdout + p.stderr


def test_an_accepted_gaps_section_does_not_trip_the_cause_checker(
    tmp_path: Path,
) -> None:
    code, out = finding_tags(
        tmp_path, qa_report("- waiver: OR-D4-R05 residual 5 of quality-gates 3-8\n")
    )
    assert code == 0, f"a PASS that cites waivers must pass the cause checker: {out}"


def test_a_defect_row_moved_into_accepted_gaps_is_still_refused(tmp_path: Path) -> None:
    for moved in ("- defect: src/x.py:4 broken\n", "1. src/x.py:4 broken\n"):
        code, out = finding_tags(tmp_path, qa_report(moved))
        assert (
            code == 4
        ), f"a defect row under Accepted gaps must still be refused ({moved!r}): {out}"


def test_editing_a_row_moves_the_candidate_id(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    ledger = tmp_path / "WAIVERS.md"
    ledger.write_text(HEADER + row())
    subprocess.run(["git", "-C", str(tmp_path), "add", "WAIVERS.md"], check=True)

    def cid() -> str:
        p = subprocess.run(
            [sys.executable, "-B", str(CANDIDATE_ID), "id", "--root", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return p.stdout.splitlines()[0] if p.returncode == 0 else p.stdout + p.stderr

    before = cid()
    assert before.startswith("CANDIDATE: git:"), before
    ledger.write_text(HEADER + row(expires="2026-12-02"))
    assert cid() != before, "a ledger edit must move the candidate id"


# ---------------------------------------------------------------- the prose is pinned


def test_quality_gates_pins_the_waiver_rules() -> None:
    text = QUALITY_GATES.read_text(encoding="utf-8")
    assert "The waiver ledger (opt-in)" in text, "quality-gates must hold the waiver ledger section"
    for rule in ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"):
        assert f"| {rule} |" in text, f"quality-gates must hold rule {rule}"
    for phrase, why in (
        ("An agent name is refused", "W2 must refuse an agent as owner"),
        (
            "the day after it the row is `EXPIRED` and the ledger is red",
            "W4 must say an expired row is red",
        ),
        (
            "A waiver does not change a verdict.",
            "W7 must say a waiver does not change a verdict",
        ),
        ("never invents or re-dates one", "W6 must say a builder never invents or re-dates a row"),
        ("The orchestrator, not QA, relays `NOTICE` lines.", "W8 must name who relays the notices"),
        ("it never commits past a RED", "W8 must say never commit past a RED"),
        (
            "A renewal or closure unit declares `WAIVERS.md` and no test file",
            "W4 must say a renewal declares WAIVERS.md and no test file",
        ),
        (
            "adapted from references/openrig/scripts/gate-lane-ledger.mjs:1-12",
            "3-9 must carry its attribution",
        ),
    ):
        assert phrase in text, why


def test_the_qa_agent_and_the_orchestrator_run_the_ledger_check() -> None:
    qa = BOUNDARY_QA.read_text(encoding="utf-8")
    cmd = "waiver_ledger.py check WAIVERS.md"
    assert cmd in qa, "boundary-qa must run the ledger check as a gate command"
    assert (
        "A waiver never turns a FAIL into a PASS." in qa
    ), "boundary-qa must say a waiver never turns a FAIL into a PASS"
    assert "(a missing `WAIVERS.md` is a FAIL)" in qa, "boundary-qa must fail a missing ledger"
    assert (
        "Any non-zero exit, 2 included, is a FAIL" in qa
    ), "boundary-qa must fail any non-zero exit"
    assert "Copy every `NOTICE` line" in qa, "boundary-qa must hand the notices to the orchestrator"
    assert (
        "compare every quote, date and gap text with the record the brief names, and find `WAIVERS.md` on `Declared:`"
        in qa
    ), "boundary-qa must have QA compare the quotes with the named record and check Declared"
    orch = ORCHESTRATOR.read_text(encoding="utf-8")
    assert cmd in orch, "the orchestrator must run the ledger check before a commit"
    assert (
        "is never edited to make it pass" in orch
    ), "the orchestrator must not edit the ledger to pass"
    assert "any non-zero exit" in orch, "the orchestrator must stop on any non-zero exit"
    assert "You are the one who relays" in orch, "the orchestrator must relay the notices to Daniel"
    assert (
        "put the full text of the `CLAUDE.md` row in the builder's brief" in orch
    ), "the orchestrator must put the whole CLAUDE.md row in the builder brief"
    assert (
        "it declares `WAIVERS.md` and nothing else" in orch
    ), "the orchestrator must say a renewal declares WAIVERS.md and nothing else"


def test_the_claude_md_row_is_present_and_has_no_unfilled_token() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "waiver_ledger.py check" in text, "CLAUDE.md must hold the OR-S6 row"
    assert "{{FINAL-VERDICT}}" not in text, "the CLAUDE.md row must have no unfilled token"
    assert "turn red together on 2027-01-10" in text, "the CLAUDE.md row must give the red date"
