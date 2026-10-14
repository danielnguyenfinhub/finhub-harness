"""Proof for the verified-* rules of skills/finhub-harness/scripts/lint_harness.py (OR-S7).

adapted from references/openrig/packages/daemon/test/skill-audit.test.ts:54-70 (Apache-2.0)
"""

import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
SKILL_MD = REPO / "skills/finhub-harness/SKILL.md"
GUIDE = REPO / "skills/finhub-harness/references/skill-writing-guide.md"
CHANGED = [LINT, Path(__file__), SKILL_MD, GUIDE]
RULES = [
    "verified-date",
    "verified-future",
    "verified-bare",
    "verified-window",
    "verified-stale",
    "verified-orphan",
]
SRC = 'verified_source: "ASIC Regulatory Guide 209 (Dec 2019), read 2026-10-01"'


def ago(n: int) -> str:
    return str(datetime.now().astimezone().date() - timedelta(days=n))


def run_lint(root: Path, skills: dict[str, list[str]]) -> tuple[int, str]:
    """Write root/skills/<name>/SKILL.md per entry and run the lint; returns (rc, out), never raises on a
    non-zero exit (a crashed lint must reach the caller's assertions, not abort the test)."""
    for name, lines in skills.items():
        d = root / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        head = f'---\nname: {name}\ndescription: "D. Use when X."\n'
        (d / "SKILL.md").write_text(
            head + "\n".join(lines) + ("\n" if lines else "") + "---\nBody\n", encoding="utf-8"
        )
    run = subprocess.run(
        [sys.executable, str(LINT), str(root)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run.returncode, run.stdout + run.stderr


def rules(out: str, name: str) -> list[str]:
    pat = re.compile(rf"skills/{re.escape(name)}/SKILL\.md: (verified-[a-z]+)")
    return [m.group(1) for m in map(pat.search, out.splitlines()) if m]


def fresh(n: int = 10, window: str = "30", src: str = SRC) -> list[str]:
    lines = [f'last_verified: "{ago(n)}"', src]
    return lines + ([f"review_days: {window}"] if window else [])


def test_skill_without_the_fields_is_silent(tmp_path: Path) -> None:
    code, out = run_lint(tmp_path, {"c0": []})
    assert code == 0 and "verified-" not in out, (
        "a skill without the fields must stay silent: " + out
    )
    assert out.strip().endswith("0 error(s), 0 warning(s)"), out


def test_fresh_sourced_skill_is_silent(tmp_path: Path) -> None:
    code, out = run_lint(tmp_path, {"c0": fresh()})
    assert code == 0 and out.strip().endswith("0 error(s), 0 warning(s)"), (
        "a fresh sourced skill must produce no warning: " + out
    )


def test_stale_skill_warns(tmp_path: Path) -> None:
    _, out = run_lint(tmp_path, {"c0": fresh(400, "30")})
    assert rules(out, "c0") == ["verified-stale"], (
        "a skill past its window must warn verified-stale: " + out
    )


def test_window_boundary_is_strict(tmp_path: Path) -> None:
    _, out = run_lint(tmp_path, {"c0": fresh(30, "30"), "c1": fresh(31, "30")})
    assert "verified-stale" not in rules(out, "c0"), (
        "age equal to the window is still fresh: " + out
    )
    assert "verified-stale" in rules(out, "c1"), (
        "age past the window must warn verified-stale: " + out
    )


def test_future_dated_skill_warns(tmp_path: Path) -> None:
    _, out = run_lint(tmp_path, {"c0": fresh(-30, "30")})
    assert rules(out, "c0") == ["verified-future"], (
        "a future last_verified must warn verified-future: " + out
    )


def test_last_verified_today_is_fresh(tmp_path: Path) -> None:
    _, out = run_lint(tmp_path, {"c0": fresh(0, "30")})
    assert rules(out, "c0") == [], "a last_verified of today must not be future: " + out


def test_malformed_dates_warn(tmp_path: Path) -> None:
    bad = [
        "2026-13-40",
        "2026-02-30",
        "10/01/2026",
        "2026-1-5",
        "20261001",
        "soon",
        "２０２６-10-01",
    ]
    _, out = run_lint(
        tmp_path,
        {f"c{i}": [f'last_verified: "{v}"', SRC, "review_days: 30"] for i, v in enumerate(bad)},
    )
    for i, v in enumerate(bad):
        assert rules(out, f"c{i}") == [
            "verified-date"
        ], f"malformed last_verified date must warn verified-date: {v!r}"
    assert "Traceback" not in out, out


def test_self_referential_source_is_bare(tmp_path: Path) -> None:
    srcs = ["skills/rules-2026/SKILL.md", "./SKILL.md 2026"]
    _, out = run_lint(
        tmp_path, {f"c{i}": fresh(src=f'verified_source: "{s}"') for i, s in enumerate(srcs)}
    )
    for i, s in enumerate(srcs):
        assert "verified-bare" in rules(
            out, f"c{i}"
        ), f"a source naming the skill's own SKILL.md must warn verified-bare: {s!r}"


def test_source_without_locator_is_bare(tmp_path: Path) -> None:
    srcs = [None, "the lender portal", "APRA APS 220"]
    cases = {f"c{i}": fresh(src=f'verified_source: "{s}"' if s else "") for i, s in enumerate(srcs)}
    _, out = run_lint(tmp_path, {k: [x for x in v if x] for k, v in cases.items()})
    for i, s in enumerate(srcs):
        assert "verified-bare" in rules(
            out, f"c{i}"
        ), f"a source with no URL or year must warn verified-bare: {s!r}"


def test_real_sources_are_accepted(tmp_path: Path) -> None:
    srcs = [
        "https://example.org/policy/guide",
        "ATO TR 2023/1 (example)",
        "T1 lender policy guide v14, 2026-09-30",
    ]
    _, out = run_lint(
        tmp_path, {f"c{i}": fresh(src=f'verified_source: "{s}"') for i, s in enumerate(srcs)}
    )
    for i, s in enumerate(srcs):
        assert "verified-bare" not in rules(
            out, f"c{i}"
        ), f"a dated or linked source must not warn verified-bare: {s!r}"


def test_missing_or_invalid_window_warns(tmp_path: Path) -> None:
    vals = ["", "0", "-5", "abc", "30.5", "99999", "²", "٣"]
    _, out = run_lint(tmp_path, {f"c{i}": fresh(window=v) for i, v in enumerate(vals)})
    for i, v in enumerate(vals):
        got = rules(out, f"c{i}")
        assert got == [
            "verified-window"
        ], f"missing or invalid review_days must warn verified-window: {v!r} {got}"


def test_window_upper_bound(tmp_path: Path) -> None:
    _, out = run_lint(tmp_path, {"c0": fresh(5, "3650"), "c1": fresh(5, "3651")})
    assert rules(out, "c0") == [], "review_days 3650 must be accepted: " + out
    assert rules(out, "c1") == ["verified-window"], (
        "review_days above 3650 must warn verified-window: " + out
    )


def test_no_global_default_window(tmp_path: Path) -> None:
    _, out = run_lint(tmp_path, {"c0": ['last_verified: "2001-01-01"', SRC]})
    assert "verified-stale" not in rules(out, "c0"), (
        "without review_days staleness must not be judged against a default: " + out
    )
    assert "verified-window" in rules(out, "c0"), out


def test_fields_without_a_date_warn_as_orphan(tmp_path: Path) -> None:
    cases = {"c0": [SRC], "c1": ["review_days: 30"], "c2": ["last_verified:", SRC]}
    _, out = run_lint(tmp_path, cases)
    for name in cases:
        assert rules(out, name) == [
            "verified-orphan"
        ], f"fields without last_verified must warn verified-orphan: {name}"


def test_every_warning_names_a_fix(tmp_path: Path) -> None:
    skills = {
        "c0": [SRC],
        "c1": ['last_verified: "soon"'],
        "c2": fresh(-30, "30"),
        "c3": ['last_verified: "' + ago(5) + '"', "review_days: 30"],
        "c4": fresh(5, ""),
        "c5": fresh(400, "30"),
    }
    _, out = run_lint(tmp_path, skills)
    lines = [ln for ln in out.splitlines() if "verified-" in ln]
    assert {r for n in skills for r in rules(out, n)} == set(RULES), out
    for ln in lines:
        assert "; fix: " in ln, "every provenance warning must name a fix: " + ln


def test_provenance_findings_stay_warnings(tmp_path: Path) -> None:
    code, out = run_lint(tmp_path, {"c0": fresh(-30, ""), "c1": fresh(400, "30")})
    assert code == 0, "provenance findings must stay WARN: " + out
    assert "ERROR" not in out, "provenance findings must stay WARN: " + out
    assert all(ln.startswith("WARN") for ln in out.splitlines() if "verified-" in ln), out


def test_only_top_level_skills_are_checked(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents/a.md").write_text(
        '---\nname: a\ndescription: "A."\nmodel: sonnet  # cheap\nlast_verified: soon\n---\n'
    )
    nested = tmp_path / "skills/x/references/deep"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text('---\nname: x\ndescription: "X."\nlast_verified: soon\n---\n')
    _, out = run_lint(tmp_path, {"x": []})
    assert "verified-" not in out, "agents must not get provenance checks: " + out


def test_docs_name_every_provenance_rule() -> None:
    for f in (SKILL_MD, GUIDE):
        text = f.read_text(encoding="utf-8")
        for r in RULES:
            assert (
                r in text
            ), f"the lint rule list in SKILL.md must name every provenance rule: {f.name} {r}"


def test_docs_state_the_tier_and_upload_limits() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "does not read tiers" in guide, "the guide must say the lint does not read tiers"
    assert (
        "does not date each figure" in guide
    ), "the guide must say the lint does not date each figure"
    assert "UNVERIFIED" in guide and "UNVERIFIED" in SKILL_MD.read_text(
        encoding="utf-8"
    ), "the chat and Cowork upload caveat must appear in the guide and in Step 4"


def test_changed_files_carry_attribution() -> None:
    for f in CHANGED:
        text = f.read_text(encoding="utf-8")
        assert "adapted from references/openrig/" in text and "(Apache-2.0)" in text, (
            "every changed file must carry the OpenRig attribution line: " + f.name
        )


def test_changed_files_hold_no_hangul() -> None:
    for f in CHANGED:
        bad = [
            c
            for c in f.read_text(encoding="utf-8")
            if 0xAC00 <= ord(c) <= 0xD7A3 or 0x1100 <= ord(c) <= 0x11FF
        ]
        assert not bad, "changed files must hold no Hangul: " + f.name
