"""Proof for the pointer-* rules of skills/finhub-harness/scripts/lint_harness.py and the pointer step
of skills/finhub-harness/SKILL.md (C33).

adapted from references/repository_harness/scripts/install-harness.sh:330-344 and
references/repository_harness/tests/installer/assert-agent-authority-contract.sh:35 (MIT, Hoang Nguyen)
"""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
SKILL_MD = REPO / "skills/finhub-harness/SKILL.md"
NAME = "demo-orchestrator"
BEGIN = f"<!-- finhub-harness:begin {NAME} -->\n"
END = f"<!-- finhub-harness:end {NAME} -->\n"
USER_TOP = "# Project rules\n\nUser text above the block.\n\n"
HISTORY = "\n**Change history:**\n| Date | Change | Target | Reason |\n| --- | --- | --- | --- |\n"


def block(
    body: str = "## Harness: demo\n\n**Goal:** g\n\n**Trigger:** t\n", name: str = NAME
) -> str:
    return f"<!-- finhub-harness:begin {name} -->\n{body}<!-- finhub-harness:end {name} -->\n"


def run(tmp_path: Path, claude_md: str | bytes, target: str = ".claude") -> tuple[int, str]:
    """Write a one-skill harness under tmp_path/.claude and CLAUDE.md at tmp_path; lint target."""
    skill = tmp_path / ".claude" / "skills" / "demo"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text('---\nname: demo\ndescription: "D. Use when X."\n---\nBody\n')
    data = claude_md if isinstance(claude_md, bytes) else claude_md.encode()
    (tmp_path / "CLAUDE.md").write_bytes(data)
    done = subprocess.run(
        [sys.executable, str(LINT), str(tmp_path / target)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def pointer(out: str) -> list[str]:
    return [line for line in out.splitlines() if ": pointer-" in line]


def test_no_markers_not_checked(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + "## Harness: demo\n\n**Goal:** g\n" + HISTORY + "x" * 5000)
    assert code == 0 and pointer(out) == [], f"C33 no marker not checked: {out}"


def test_good_block_passes(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + block() + HISTORY)
    assert code == 0 and pointer(out) == [], f"C33 good block passes: {out}"


def test_two_begin_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + BEGIN + block() + HISTORY)
    assert code == 1, f"C33 two begin refused: {out}"
    assert (
        "pointer-marker 'demo-orchestrator': 2 begin and 1 end" in out
    ), f"C33 two begin refused: {out}"


def test_end_before_begin_refused(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + END + "## Harness: demo\n" + BEGIN + HISTORY)
    assert code == 1, f"C33 end before begin refused: {out}"
    assert (
        "end marker at line 5 is above begin marker at line 7" in out
    ), f"C33 end before begin refused: {out}"


@pytest.mark.parametrize(
    ("text", "counts"),
    [(BEGIN + "## Harness: demo\n", "1 begin and 0 end"), ("x\n" + END, "0 begin and 1 end")],
    ids=["begin-only", "end-only"],
)
def test_unpaired_refused(tmp_path: Path, text: str, counts: str) -> None:
    code, out = run(tmp_path, USER_TOP + text + HISTORY)
    assert code == 1 and f"'demo-orchestrator': {counts}" in out, f"C33 unpaired refused: {out}"


def test_nested_refused(tmp_path: Path) -> None:
    inner = block(name="other-orchestrator")
    code, out = run(tmp_path, USER_TOP + block(body="## Harness: demo\n" + inner) + HISTORY)
    assert code == 1, f"C33 nested refused: {out}"
    assert (
        "holds a marker of 'other-orchestrator' inside this block" in out
    ), f"C33 nested refused: {out}"


def test_two_harnesses_pass(tmp_path: Path) -> None:
    text = USER_TOP + block() + HISTORY + "\n" + block(name="other-orchestrator") + HISTORY
    code, out = run(tmp_path, text)
    assert code == 0 and pointer(out) == [], f"C33 two harnesses pass: {out}"


def sized(n: int) -> str:
    """A block of exactly n bytes, both marker lines and the end line's newline included."""
    filler = n - len(BEGIN) - len(END) - 1
    return BEGIN + "x" * filler + "\n" + END


def test_budget_counts_block_only(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + sized(1600) + HISTORY + "| r |\n" * 20000)
    assert code == 0 and pointer(out) == [], f"C33 budget at 1600 is fresh: {out}"
    code, out = run(tmp_path, USER_TOP + sized(1601) + HISTORY)
    assert code == 0, f"C33 budget is a WARN: {out}"
    want = (
        f"WARN {tmp_path / 'CLAUDE.md'}: pointer-budget 'demo-orchestrator': block is 1601 bytes, "
        "over 1600; fix: keep Goal and Trigger short and leave the change history below the block"
    )
    assert pointer(out) == [want], f"C33 budget over 1600 warns: {out}"


def test_budget_in_bytes_not_characters(tmp_path: Path) -> None:
    body = chr(0xAC00) * 520 + "\n"  # 520 characters, 1560 bytes in UTF-8
    code, out = run(tmp_path, USER_TOP + BEGIN + body + END)
    assert code == 0 and "pointer-budget" in out, f"C33 budget counts bytes: {out}"


def test_last_line_without_newline(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + sized(1601)[:-1])  # 1600 bytes: no newline at end of file
    assert code == 0 and pointer(out) == [], f"C33 no phantom newline byte: {out}"


def test_marker_must_be_whole_line(tmp_path: Path) -> None:
    mention = f"| 2026-10-27 | markers `{BEGIN.strip()}` and `{END.strip()}` | x | y |\n"
    text = USER_TOP + mention + "  " + BEGIN + "> " + BEGIN + HISTORY
    code, out = run(tmp_path, text)
    assert code == 0 and pointer(out) == [], f"C33 a marker is a whole line: {out}"
    crlf = USER_TOP + BEGIN.replace("\n", " \r\n") + "x\r\n" + END.replace("\n", "\t\r\n")
    code, out = run(tmp_path, crlf + BEGIN.replace("\n", "\r\n"))
    assert (
        code == 1 and "2 begin and 1 end" in out
    ), f"C33 trailing blanks and CR still a marker: {out}"


def test_claude_md_location(tmp_path: Path) -> None:
    bad = USER_TOP + BEGIN + BEGIN + END
    for target in (".claude", "."):
        code, out = run(tmp_path, bad, target)
        assert (
            code == 1 and "pointer-marker" in out
        ), f"C33 CLAUDE.md beside DIR read: {target} {out}"
    (tmp_path / ".claude" / "CLAUDE.md").write_text(bad)
    (tmp_path / "CLAUDE.md").write_text("plain\n")
    done = subprocess.run(
        [sys.executable, str(LINT), str(tmp_path / ".claude")],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert (
        done.returncode == 0 and "pointer-" not in done.stdout
    ), f"C33 CLAUDE.md beside DIR read: inside .claude {done.stdout}"


def test_claude_md_from_inside_dot_claude(tmp_path: Path) -> None:
    run(tmp_path, "plain\n")
    (tmp_path / ".claude" / "CLAUDE.md").write_text("plain\n")
    (tmp_path / "CLAUDE.md").write_text(USER_TOP + BEGIN + BEGIN + END)
    done = subprocess.run(
        [sys.executable, str(LINT), "."],
        cwd=tmp_path / ".claude",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert (
        done.returncode == 1 and "2 begin and 1 end" in done.stdout
    ), f"C33 DIR . inside .claude reads the project file: {done.stdout}"


def test_claude_md_symlinked_dot_claude(tmp_path: Path) -> None:
    run(tmp_path / "store", "plain\n")  # the real harness lives elsewhere, its own CLAUDE.md clean
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".claude").symlink_to(tmp_path / "store" / ".claude")
    (proj / "CLAUDE.md").write_text(USER_TOP + BEGIN + BEGIN + END)
    done = subprocess.run(
        [sys.executable, str(LINT), str(proj / ".claude")],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert (
        done.returncode == 1 and "2 begin and 1 end" in done.stdout
    ), f"C33 a linked .claude reads the project file: {done.stdout}"


def test_byte_order_mark_on_first_line(tmp_path: Path) -> None:
    code, out = run(tmp_path, b"\xef\xbb\xbf" + (block() + HISTORY).encode())
    assert code == 0 and pointer(out) == [], f"C33 a BOM before the begin line is ignored: {out}"
    code, out = run(tmp_path, b"\xef\xbb\xbf" + (BEGIN + block() + HISTORY).encode())
    assert (
        code == 1 and "2 begin and 1 end" in out
    ), f"C33 a BOM before the begin line is ignored: {out}"


def test_unreadable_claude_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("lint_c33", LINT)
    assert spec and spec.loader, "C33 lint importable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    target = tmp_path / "CLAUDE.md"
    target.write_text(BEGIN + BEGIN + END)
    real = Path.read_bytes

    def deny(self: Path) -> bytes:
        if self == target:
            raise PermissionError(13, "Permission denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", deny)
    try:
        mod.check_pointer(target)
        crashed = ""
    except OSError as e:
        crashed = repr(e)
    assert (
        crashed == "" and len(mod.out) == 1
    ), f"C33 unreadable file is one WARN line: {crashed} {mod.out}"
    assert (
        mod.out[0].startswith("WARN ") and "pointer-unread" in mod.out[0]
    ), f"C33 unreadable file is one WARN line: {mod.out}"


def lint_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_c33_stat", LINT)
    assert spec and spec.loader, "C33 lint importable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stat_failure_is_one_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLAUDE.md that cannot even be stat-ed (a link into a mode-000 directory, a dead mount)."""
    mod = lint_module()
    target = tmp_path / "CLAUDE.md"
    target.write_text(BEGIN + BEGIN + END)
    real_stat = os.stat

    def deny(p: object, *a: object, **k: object) -> os.stat_result:
        if str(p) == str(target):
            raise PermissionError(13, "Permission denied")
        return real_stat(p, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "stat", deny)
    try:
        mod.check_pointer(target)
        crashed = ""
    except OSError as e:
        crashed = repr(e)
    monkeypatch.undo()
    assert crashed == "" and [x.split(": ", 1)[1] for x in mod.out] == [
        "pointer-unread not checked: Permission denied; fix: make it readable"
    ], f"C33 stat failure is one WARN line: {crashed} {mod.out}"


def test_not_a_file_is_silent(tmp_path: Path) -> None:
    mod = lint_module()
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "CLAUDE.md").mkdir()
    mod.check_pointer(tmp_path / "d" / "CLAUDE.md")
    assert mod.out == [], f"C33 a directory named CLAUDE.md is not checked: {mod.out}"
    (tmp_path / "l").mkdir()
    (tmp_path / "l" / "CLAUDE.md").symlink_to(tmp_path / "nowhere")
    mod.check_pointer(tmp_path / "l" / "CLAUDE.md")
    assert mod.out == [], f"C33 a broken link is no file: {mod.out}"
    (tmp_path / "f").mkdir()
    os.mkfifo(tmp_path / "f" / "CLAUDE.md")
    mod.check_pointer(tmp_path / "f" / "CLAUDE.md")  # must return without opening it
    assert mod.out == [], f"C33 a FIFO is not read: {mod.out}"


def test_non_utf8_claude_md(tmp_path: Path) -> None:
    code, out = run(tmp_path, b"\xff\xfe user bytes\n" + block().encode() + b"\xff\n")
    assert (
        code == 0 and "encoding" not in out and pointer(out) == []
    ), f"C33 bytes not decoded: {out}"


def template() -> str:
    text = SKILL_MD.read_text(encoding="utf-8")
    m = re.search(r"````markdown\n(<!-- finhub-harness:begin .*?)````", text, re.DOTALL)
    assert m, "C33 template in SKILL.md"
    return m.group(1).replace("{orchestrator-skill-name}", NAME)


def test_template_from_skill_passes(tmp_path: Path) -> None:
    code, out = run(tmp_path, USER_TOP + template() + "| 2026-10-27 | x | y | z |\n" * 3000)
    assert code == 0 and pointer(out) == [], f"C33 template passes the lint: {out}"


def test_this_repo_out_of_scope() -> None:
    text = (REPO / "CLAUDE.md").read_bytes()
    assert not re.search(
        rb"(?m)^<!-- finhub-harness:(?:begin|end) ", text
    ), "C33 repo has no marker"
    for target in (REPO, REPO / ".claude"):
        done = subprocess.run(
            [sys.executable, str(LINT), str(target)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert (
            done.returncode == 0 and "pointer-" not in done.stdout
        ), f"C33 repo lint clean: {target}"


PINS = {
    "sk-marker": "<!-- finhub-harness:begin {orchestrator-skill-name} -->",
    "sk-history-below": "with the change history after the end marker",
    "sk-legacy": "say in the report that the pointer has no markers",
    "sk-grep": "list the marker lines from the file itself, with `grep -n 'finhub-harness:' CLAUDE.md`",
    "sk-bom": "a byte-order mark at the very start of the file does not count as text",
    "sk-keep": "start the new block from the lines now between the markers and change only what this run changes",
    "sk-unread": "or a `CLAUDE.md` you cannot read): write nothing",
    "sk-context": "never from the copy of `CLAUDE.md` loaded at session start",
    "sk-same": "If the result matches those lines, write nothing.",
    "sk-outside": "Every byte above the begin line and below the end line stays as it was.",
    "sk-refuse": "write nothing to `CLAUDE.md`. Show the user the marker lines with their line numbers",
    "sk-noguess": "Never guess which pair is meant.",
    "sk-backup": "`cp -p CLAUDE.md CLAUDE.md.bak && cmp CLAUDE.md CLAUDE.md.bak`",
    "sk-budget": "to 1600 bytes or fewer",
    "sk-history-never": "never counted, never trimmed and never moved into it",
    "sk-surface": "whether `CLAUDE.md` can be read or edited in place and whether the lint can run",
    "sk-lint": "(`pointer-marker`, ERROR) and a block of at most 1600 bytes (`pointer-budget`, WARN",
    "sk-checklist": "inside its one pair of finhub-harness marker lines (1600 bytes or fewer)",
    "sk-attr": "references/repository_harness/scripts/install-harness.sh:330-344 and :369 (MIT, Hoang",
    "sk-attr-budget": "repository_harness/tests/installer/assert-agent-authority-contract.sh:35 (MIT",
}


@pytest.mark.parametrize("pin", sorted(PINS))
def test_prose_pins(pin: str) -> None:
    text = " ".join(SKILL_MD.read_text(encoding="utf-8").split())
    assert " ".join(PINS[pin].split()) in text, f"C33 prose pin {pin}"


def test_old_pointer_line_removed() -> None:
    old = "- **`CLAUDE.md` pointer**: record only the block below. Agent lists"
    assert old not in SKILL_MD.read_text(encoding="utf-8"), "C33 old pointer line removed"


def test_lint_attribution() -> None:
    text = " ".join(LINT.read_text(encoding="utf-8").split())
    for cite in (
        "references/repository_harness/scripts/install-harness.sh:330-344",
        "references/repository_harness/tests/installer/assert-agent-authority-contract.sh:35",
        "(MIT, Hoang Nguyen)",
    ):
        assert cite in text, f"C33 lint attribution {cite}"


def test_script_links_reads_only_this_skills_scripts() -> None:
    """tests/test_state_ledger.py script_links must skip a pinned repo's file and still catch a typo."""
    spec = importlib.util.spec_from_file_location(
        "ledger_tests", REPO / "tests/test_state_ledger.py"
    )
    assert spec and spec.loader, "C33 state ledger tests importable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = "script `scripts/state_ledger.py`"
    cite = "(adapted from references/repository_harness/scripts/install-harness.sh:330-344 (MIT))"
    try:
        mod.script_links(doc, cite)
        passed = True
    except AssertionError:
        passed = False
    assert passed, "C33 a pinned repo's script cite is not read as ours"
    try:
        mod.script_links(doc, cite + " run `scripts/state_ledgr.py`")
        caught = False
    except AssertionError:
        caught = True
    assert caught, "C33 a typo in this skill's script name is still caught"
    try:
        mod.script_links(doc, "run `tools-references/x/scripts/state_ledgr.py`")
        anchored = False
    except AssertionError:
        anchored = True
    assert anchored, "C33 the strip starts only at a path that begins with references/"
