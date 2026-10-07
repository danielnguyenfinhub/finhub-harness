"""Proof for the write-safety ladder, the Writers table and its checker (C18).

Prose checks bind each rule in references/write-safety.md to the checker's behaviour; the checker
(skills/finhub-harness/scripts/check_writers.py) is exercised on fixture orchestrators.
"""

import contextlib
import importlib
import io
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills/finhub-harness"
REFS = SKILL / "references"
DOC = REFS / "write-safety.md"
SCRIPT = SKILL / "scripts/check_writers.py"
SURFACES = REFS / "surfaces.md"
TEMPLATE = REFS / "orchestrator-template.md"
PATTERNS = REFS / "team-patterns.md"
GATES = REFS / "quality-gates.md"
SKILL_MD = SKILL / "SKILL.md"
META = REPO / "references/meta_harness"
BANNED = "autogpt" + "_platform"  # the Polyform Shield tree; never cited
TOUCHED = (DOC, SCRIPT, SURFACES, TEMPLATE, PATTERNS, GATES, SKILL_MD)


def load() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        return importlib.import_module("check_writers")
    finally:
        sys.path.remove(str(SCRIPT.parent))


cw = load()
HEAD = (
    "## Writers\n\n| Batch | Role | Writes | Label | Wanted | Mechanism or reason |\n"
    "|---|---|---|---|---|---|\n"
)


def row(batch: str, role: str, writes: str, label: str, wanted: str = "", note: str = "") -> str:
    return f"| {batch} | {role} | {writes} | {label} | {wanted or label} | {note} |\n"


def run(tmp_path: Path, text: str, *flags: str) -> tuple[int, str]:
    f = tmp_path / "orchestrator.md"
    f.write_text(text, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cw.main(["check_writers.py", *flags, str(f)])
    return code, buf.getvalue()


def codes(out: str) -> set[str]:
    return set(re.findall(r": (W\d+) ", out))


def verdict(tmp_path: Path, *rows: str, flags: tuple[str, ...] = ()) -> tuple[int, set[str]]:
    code, out = run(tmp_path, HEAD + "".join(rows), *flags)
    return code, codes(out)


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def table_rows(block: str) -> list[list[str]]:
    lines = [ln for ln in block.splitlines() if ln.lstrip().startswith("|")]
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    return [r for r in rows[1:] if not set("".join(r)) <= set("-: ")]


def fenced_after(text: str, caption: str) -> str:
    rest = text[text.index(caption) :]
    start = rest.index("```markdown\n") + len("```markdown\n")
    return rest[start : rest.index("\n```", start)] + "\n"


DOC_TEXT = DOC.read_text(encoding="utf-8")


# ---- the prose is tied to the checker -------------------------------------------------------


def test_rule_ids_in_doc_equal_checker_rules() -> None:
    block = section(DOC_TEXT, "## Rules the checker enforces", "Example that passes:")
    ids = {r[0] for r in table_rows(block)}
    assert ids == set(cw.RULES) == {f"W{i}" for i in range(1, 11)}
    assert {r[0]: r[1] for r in table_rows(block)} == cw.RULES
    window = re.search(r"within the (\w+) words", cw.RULES["W6"])
    assert window and {"six": 6}[window.group(1)] == cw.NEGATION_WINDOW


def test_ladder_order_is_the_checker_order() -> None:
    rows = table_rows(section(DOC_TEXT, "## The ladder", "Reading the last column"))
    assert [r[0] for r in rows] == ["1", "2", "3", "4"]
    assert [r[1].strip("`") for r in rows] == list(cw.LABELS)
    assert cw.LABELS == ("enforced", "workspace-enforced", "advisory", "serialised")


def test_ladder_says_what_makes_each_rung_true() -> None:
    rows = table_rows(section(DOC_TEXT, "## The ladder", "Reading the last column"))
    must = (
        ("path-scoped permission rule", "hook that denies the path"),
        ("own worktree", "merges the results one at a time"),
        ("disjoint paths", "nothing stops"),
        ("One writer runs at a time", "report has been accepted"),
    )
    for r, words_ in zip(rows, must, strict=True):
        assert all(w in r[2] for w in words_), (r[1], words_)
    assert "allowlist" not in rows[0][2]
    limits = DOC_TEXT[DOC_TEXT.index("## Limits") :]
    assert "allowlist" not in limits
    assert "shows only that the role cannot write through those tools" in limits
    assert "with `Bash` it shows nothing about writes" in limits
    read_only = section(DOC_TEXT, "A role is left out of the table", "## The Writers table")
    assert (
        "limits tools, not paths" in read_only and "does not make a writer `enforced`" in read_only
    )
    assert "without `Edit`, `Write` and `Bash`" in read_only and "keeps `Bash`" in read_only
    assert "can still write files, so it gets a row" in read_only
    assert "QA opens the command and shows it" in read_only
    assert "guarantee" not in read_only and "writes nothing" not in read_only


@pytest.mark.parametrize("rung", range(4))
def test_overlap_column_matches_checker_behaviour(tmp_path: Path, rung: int) -> None:
    r = table_rows(section(DOC_TEXT, "## The ladder", "Reading the last column"))[rung]
    label, permits = r[1].strip("`"), r[3]
    note = "named mechanism"
    pair = (
        row("1", "w1", "`src/**`", label, note=note),
        row("1", "w2", "`src/x.py`", label, note=note),
    )
    code, found = verdict(tmp_path, *pair)
    if permits == "forbidden":
        assert (code, found) == (1, {"W2"})
    elif permits == "allowed":
        assert (code, found) == (0, set())
    else:
        assert permits == "alone" and (code, found) == (1, {"W3"})
        assert verdict(tmp_path, row("1", "w1", "`src/**`", label)) == (0, set())
    assert (permits == "forbidden") == (label in ("enforced", "advisory"))


def test_doc_examples_behave_as_captioned(tmp_path: Path) -> None:
    good = fenced_after(DOC_TEXT, "Example that passes:")
    caption = re.search(r"Example that fails with (W\d) and (W\d):", DOC_TEXT)
    assert caption is not None
    assert run(tmp_path, good, "--require") == (
        0,
        "check_writers: 0 violation(s), 1 Writers table(s)\n",
    )
    code, out = run(tmp_path, fenced_after(DOC_TEXT, caption.group(0)), "--require")
    assert code == 1 and codes(out) == set(caption.groups())


def test_table_layout_example_passes(tmp_path: Path) -> None:
    example = fenced_after(DOC_TEXT, "## The Writers table")
    assert run(tmp_path, example, "--require") == (
        0,
        "check_writers: 0 violation(s), 1 Writers table(s)\n",
    )
    assert run(tmp_path, example.replace("`_workspace/b/**`", "`_workspace/a/x.md`"))[0] == 1


def test_each_choice_step_and_honest_bullet_names_its_rule() -> None:
    steps = section(DOC_TEXT, "## How to choose", "## What an honest label is")
    bullets = section(DOC_TEXT, "## What an honest label is", "## Rules the checker enforces")
    lines = [ln for ln in (steps + bullets).splitlines() if re.match(r"(\d\.|-) ", ln)]
    assert len(lines) == 9
    tags = [re.search(r"\[([^\]]+)\]$", ln) for ln in lines]
    assert all(tags)
    named = {w for t in tags if t for w in t.group(1).split() if t.group(1) != "not checked"}
    assert named <= set(cw.RULES) and named == {f"W{i}" for i in (1, 2, 3, 4, 5, 6, 9)}
    assert sum(t.group(1) == "not checked" for t in tags if t) == 2


# ---- checker behaviour ----------------------------------------------------------------------


def test_disjoint_advisory_writers_pass(tmp_path: Path) -> None:
    rows = (
        row("1", "a", "`_workspace/a/**`", "advisory"),
        row("1", "b", "`_workspace/b/**`", "advisory"),
    )
    assert verdict(tmp_path, *rows) == (0, set())


@pytest.mark.parametrize(
    ("a", "b", "clash"),
    [
        ("`out/a.md`", "`out/a.md`", True),
        ("`out/**`", "`out/a.md`", True),
        ("`out`", "`out/a/b.md`", True),
        ("`out/*.md`", "`out/a.md`", True),
        ("`out/*.md`", "`out/sub/a.md`", False),
        ("`src/ab`", "`src/a`", False),
        ("`src/a/**`", "`src/ab/**`", False),
        ("`./out/a`", "`out/a`", True),
        ("`**/a.md`", "`x/y.md`", True),
        ("`*`", "`anything/here`", True),
        ("`.`", "`out/a.md`", True),
        ("", "`out/a.md`", True),
        ("`out/a.md`, `out/b.md`", "`out/b.md`", True),
        ("`out/a.md`, `out/b.md`", "`out/c.md`", False),
        ("`a/1`, `b/2`, `c/3`", "`c/3`", True),
        ("`a/1`, `b/2`, `c/3`", "`d/4`", False),
        ("`src/*_a.py`", "`src/a_*.py`", True),
        ("`docs/*-draft.md`", "`docs/report-*.md`", True),
        ("`a/*_x/b`", "`a/y_*/c`", False),
        ("`SRC/A.py`", "`src/a.py`", True),
        ("`/abs/src/a.py`", "`src/a.py`", True),
        ("`~/x`", "`y`", True),
        ("`C:/x`", "`y`", True),
        ("`src/../docs/x`", "`docs/x`", True),
        ("`../x`", "`x`", True),
        ("`src/{a,b}.py`", "`src/a.py`", True),
        ("`src\\a.py`", "`src/a.py`", True),
        ("`src\\a.py`", "`src/b.py`", False),
        ("`src/\u00df.py`", "`src/ss.py`", True),
        ("`src/{a,b}.py`", "`other/z.py`", True),
        ("`src/\u00e9.py`", "`src/e\u0301.py`", True),
        ("`src/a?.py`", "`src/ab.py`", True),
        ("`src/a?.py`", "`src/abc.py`", False),
        ("`[ab]/x`", "`c/x`", False),
        ("`[ab]/x`", "`a/x`", True),
        ("`src/a.py (new)`", "`src/a.py`", True),
        ("`src/a.py (new)`", "`zzz/o.py`", True),
        ("`my docs/a.md`", "`zzz/o.py`", True),
        ("`src/a.py;src/b.py`", "`zzz/o.py`", True),
        ("`src/a.py<br>src/b.py`", "`zzz/o.py`", True),
        ("`src/a.py`src/b.py`", "`zzz/o.py`", True),
        ('"src/a.py"', "`zzz/o.py`", True),
        ("'src/a.py'", "`zzz/o.py`", True),
        ("`src/a(.py`", "`zzz/o.py`", True),
        ("`src/a).py`", "`zzz/o.py`", True),
        ("`src/a.py:12`", "`zzz/o.py`", True),
        ("`src/a.py#L1`", "`zzz/o.py`", True),
        ("`<item>/a.py`", "`zzz/o.py`", False),
        ("`src/a.py`", "`zzz/o.py`", False),
    ],
)
def test_path_overlap(tmp_path: Path, a: str, b: str, clash: bool) -> None:
    rows = (row("1", "a", a, "advisory"), row("1", "b", b, "advisory"))
    assert verdict(tmp_path, *rows) == ((1, {"W2"}) if clash else (0, set()))


def test_different_batches_may_share_paths(tmp_path: Path) -> None:
    rows = (row("1", "a", "`x/**`", "advisory"), row("2", "b", "`x/**`", "advisory"))
    assert verdict(tmp_path, *rows) == (0, set())


@pytest.mark.parametrize(
    ("first", "second", "clash"),
    [
        ("enforced", "enforced", True),
        ("enforced", "advisory", True),
        ("advisory", "workspace-enforced", False),
        ("workspace-enforced", "enforced", False),
        ("workspace-enforced", "workspace-enforced", False),
    ],
)
def test_overlap_depends_on_both_labels(
    tmp_path: Path, first: str, second: str, clash: bool
) -> None:
    rows = (
        row("1", "a", "`x/**`", first, note="mech"),
        row("1", "b", "`x/y`", second, note="mech"),
    )
    assert verdict(tmp_path, *rows) == ((1, {"W2"}) if clash else (0, set()))


def test_serialised_must_be_alone(tmp_path: Path) -> None:
    assert verdict(tmp_path, row("1", "a", "`x`", "serialised")) == (0, set())
    rows = (
        row("1", "a", "`x`", "serialised"),
        row("1", "b", "`y`", "workspace-enforced", note="wt"),
    )
    assert verdict(tmp_path, *rows) == (1, {"W3"})
    rows = (row("1", "a", "`x`", "serialised"), row("2", "b", "`x`", "serialised"))
    assert verdict(tmp_path, *rows) == (0, set())


@pytest.mark.parametrize(
    ("label", "note", "ok"),
    [
        ("enforced", "", False),
        ("workspace-enforced", "", False),
        ("enforced", "a hook denies writes outside Writes", True),
        ("advisory", "", True),
        ("serialised", "", True),
    ],
)
def test_mechanism_required_for_top_two_rungs(
    tmp_path: Path, label: str, note: str, ok: bool
) -> None:
    assert verdict(tmp_path, row("1", "a", "`x`", label, note=note)) == (
        (0, set()) if ok else (1, {"W4"})
    )


@pytest.mark.parametrize(
    ("label", "wanted", "note", "ok"),
    [
        ("advisory", "enforced", "", False),
        ("serialised", "advisory", "", False),
        ("serialised", "workspace-enforced", "", False),
        ("advisory", "enforced", "no hook is set up", True),
        ("advisory", "advisory", "", True),
        ("enforced", "advisory", "path rule", True),
        ("workspace-enforced", "serialised", "own worktree", True),
        ("advisory", "serialised", "", True),
        ("advisory", "workspace-enforced", "", False),
        ("serialised", "enforced", "", False),
        ("workspace-enforced", "advisory", "own worktree", True),
    ],
)
def test_lowering_needs_a_reason(
    tmp_path: Path, label: str, wanted: str, note: str, ok: bool
) -> None:
    code, found = verdict(tmp_path, row("1", "a", "`x`", label, wanted, note))
    assert (code, found) == ((0, set()) if ok else (1, {"W5"}))


@pytest.mark.parametrize(
    ("label", "wanted"),
    [("exclusive", "advisory"), ("advisory", "locked"), ("", "advisory"), ("none", "none")],
)
def test_unknown_label_is_rejected(tmp_path: Path, label: str, wanted: str) -> None:
    code, found = verdict(tmp_path, row("1", "a", "`x`", label, wanted))
    assert code == 1 and "W1" in found


def test_label_case_and_backticks_are_forgiven(tmp_path: Path) -> None:
    assert verdict(tmp_path, row("1", "a", "`x`", "`Advisory`", "ADVISORY")) == (0, set())


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("advisory: exclusive access to src", True),
        ("advisory, so the path is locked", True),
        ("advisory but guaranteed by the brief", True),
        ("advisory, exclusively theirs", True),
        ("advisory ownership is not exclusive", False),
        ("never call advisory ownership exclusive", False),
        ("advisory, not guaranteed", False),
        ("advisory, so the path is not locked", False),
        ("must not touch x; advisory ownership of src, exclusive to a", True),
        ("Advisory: Exclusive access", True),
        ("advisory ownership isn't exclusive", False),
        ("advisory, shared checkout", False),
        ("advisory block", False),
    ],
)
def test_advisory_is_never_called_exclusive(tmp_path: Path, text: str, flagged: bool) -> None:
    assert verdict(tmp_path, row("1", "a", "`x`", "advisory", note=text)) == (
        (1, {"W6"}) if flagged else (0, set())
    )
    prose = f"{HEAD}{row('1', 'a', '`x`', 'serialised')}\nNote: {text}\n"
    assert (run(tmp_path, prose)[0] == 1) == flagged


def test_w6_looks_back_at_most_200_characters(tmp_path: Path) -> None:
    """The negation window is cut at 200 characters so a huge line cannot slow the scan; the cost
    is a false positive when the six words before the overclaim are longer than that."""
    near = "advisory, never exclusive"
    far = "advisory, never " + " ".join("w" * 60 for _ in range(5)) + " exclusive"
    assert len(far) > 200
    assert verdict(tmp_path, row("1", "a", "`x`", "advisory", note=near)) == (0, set())
    assert verdict(tmp_path, row("1", "a", "`x`", "advisory", note=far)) == (1, {"W6"})


def test_w6_ignores_lines_without_advisory(tmp_path: Path) -> None:
    assert run(tmp_path, "The worktree is exclusive to one writer and locked.\n")[0] == 0
    rows = row("1", "a", "`x`", "workspace-enforced", note="own worktree, exclusive to a")
    assert verdict(tmp_path, rows) == (0, set())


@pytest.mark.parametrize(
    "text",
    [
        "## Writers\n\n| Batch | Role | Writes | Label | Wanted |\n|---|---|---|---|---|\n| 1 | a | `x` | advisory | advisory |\n",
        HEAD,
        HEAD + row("", "a", "`x`", "advisory"),
        HEAD + row("1", "", "`x`", "advisory"),
    ],
)
def test_malformed_table_is_w7(tmp_path: Path, text: str) -> None:
    code, out = run(tmp_path, text)
    assert code == 1 and codes(out) == {"W7"}


def test_column_order_is_free(tmp_path: Path) -> None:
    text = (
        "### Writers\n\n| Label | Role | Mechanism | Wanted | Batch | Writes |\n|--|--|--|--|--|--|\n"
        "| advisory | a | | advisory | 1 | `x` |\n| advisory | b | | advisory | 1 | `x/y` |\n"
    )
    assert run(tmp_path, text)[0] == 1
    assert run(tmp_path, text.replace("`x/y`", "`z`"))[0] == 0


def test_require_and_fences(tmp_path: Path) -> None:
    assert run(tmp_path, "# Plan\nno table\n")[0] == 0
    code, out = run(tmp_path, "# Plan\nno table\n", "--require")
    assert (code, codes(out)) == (1, {"W8"})
    bad = HEAD + row("1", "a", "`x`", "advisory") + row("1", "b", "`x`", "advisory")
    for fence in ("```", "~~~", "````"):
        text = f"{fence}markdown\n{bad}{fence}\n"
        assert run(tmp_path, text)[0] == 0
        assert codes(run(tmp_path, text, "--require")[1]) == {"W8"}
    nested = f"````markdown\n```text\nx\n```\n{bad}````\n"
    assert run(tmp_path, nested)[0] == 0
    short_inside = f"````markdown\n```\n{bad}````\n"
    assert run(tmp_path, short_inside)[0] == 0
    other_char = f"```markdown\n~~~\n{bad}```\n"
    assert run(tmp_path, other_char)[0] == 0
    after = f"```text\nx\n```\n{bad}"
    assert run(tmp_path, after)[0] == 1


def test_heading_level_and_name(tmp_path: Path) -> None:
    rows = row("1", "a", "`x`", "advisory") + row("1", "b", "`x`", "advisory")
    for heading in ("## Writers", "### Writers", "#### Writers"):
        assert run(tmp_path, HEAD.replace("## Writers", heading) + rows)[0] == 1
    for heading in ("# Writers", "##### Writers", "## Writers and roles", "## Workers"):
        assert run(tmp_path, HEAD.replace("## Writers", heading) + rows)[0] == 0


def test_batches_are_per_table_and_table_ends_at_prose(tmp_path: Path) -> None:
    one = HEAD + row("1", "a", "`x`", "advisory")
    two = HEAD + row("1", "b", "`x`", "advisory")
    assert run(tmp_path, one + "\ntext\n\n" + two)[0] == 0
    stray = one + "\ntext\n\n" + row("1", "b", "`x`", "advisory")
    assert run(tmp_path, stray)[0] == 0


def test_cli_exit_codes(tmp_path: Path) -> None:
    f = tmp_path / "o.md"
    f.write_text(HEAD + row("1", "a", "`x`", "advisory"), encoding="utf-8")
    cmd = [sys.executable, "-I", str(SCRIPT)]
    assert subprocess.run([*cmd, str(f)], capture_output=True, check=False).returncode == 0
    assert subprocess.run(cmd, capture_output=True, check=False).returncode == 2
    assert (
        subprocess.run([*cmd, "--nope", str(f)], capture_output=True, check=False).returncode == 2
    )
    assert (
        subprocess.run(
            [*cmd, str(tmp_path / "missing.md")], capture_output=True, check=False
        ).returncode
        == 2
    )
    f.write_text(HEAD + row("1", "a", "`x`", "enforced"), encoding="utf-8")
    bad = subprocess.run([*cmd, str(f)], capture_output=True, text=True, check=False)
    assert bad.returncode == 1 and f"{f.as_posix()}:5: W4 a:" in bad.stdout


def test_a_row_is_one_worker_and_per_item_rows_say_so(tmp_path: Path) -> None:
    ok = row("1", "extractor (per item)", "`_workspace/<item>/r.md`", "advisory")
    assert verdict(tmp_path, ok) == (0, set())
    assert verdict(
        tmp_path, row("1", "extractor (per item)", "`_workspace/results.md`", "advisory")
    ) == (1, {"W9"})
    assert verdict(
        tmp_path, row("1", "extractor (per item)", "`_workspace/r/*.md`", "advisory")
    ) == (0, set())
    for role in (
        "workers, one per item",
        "each item writer",
        "Per-File editor",
        "N instances",
        "per file",
    ):
        assert verdict(tmp_path, row("1", role, "`out/x.md`", "advisory")) == (1, {"W9"}), role
    assert verdict(tmp_path, row("1", "merger", "`out/x.md`", "advisory")) == (0, set())
    two = (
        row("1", "a (per item)", "`out/<item>/x`", "advisory"),
        row("1", "b", "`out/<item>/x`", "advisory"),
    )
    assert verdict(tmp_path, *two) == (1, {"W2"})


def test_w9_wants_every_writes_path_to_be_per_item(tmp_path: Path) -> None:
    role = "worker per item"
    mixed = "`_workspace/<item>.md`, `_workspace/glossary.md`"
    assert verdict(tmp_path, row("1", role, mixed, "advisory")) == (1, {"W9"})
    both = "`_workspace/<item>.md`, `_workspace/<item>.log`"
    assert verdict(tmp_path, row("1", role, both, "advisory")) == (0, set())
    globs = "`_workspace/<item>.md`, `_workspace/log/*.txt`"
    assert verdict(tmp_path, row("1", role, globs, "advisory")) == (0, set())
    assert verdict(tmp_path, row("1", role, "", "advisory")) == (1, {"W9"})


@pytest.mark.parametrize(
    "role",
    [
        "single-instance merger",
        "merger (one instance)",
        "Instances manager",
        "extractor",
        "instance",
    ],
)
def test_w9_does_not_read_instance_as_per_item(tmp_path: Path, role: str) -> None:
    assert verdict(tmp_path, row("1", role, "`out/x.md`", "advisory")) == (0, set())


@pytest.mark.parametrize(
    "role",
    [
        "writer per instance",
        "each instance",
        "3 instances",
        "N instances",
        "many instances",
        "several instances",
        "multiple instances",
        "parallel instances",
        "per-item writer",
        "each file",
    ],
)
def test_w9_reads_these_per_item_phrasings(tmp_path: Path, role: str) -> None:
    assert verdict(tmp_path, row("1", role, "`out/x.md`", "advisory")) == (1, {"W9"})


@pytest.mark.parametrize(
    "heading",
    [
        "## Writers:",
        "## **Writers**",
        "## **Writers:**",
        "## 3. Writers",
        "## 3) Writers",
        "## Writers (batch 1)",
        "## Writers table",
        "### writers",
        "## WRITERS Table (a)",
        "## Writers  ",
    ],
)
def test_heading_variants_are_the_writers_heading(tmp_path: Path, heading: str) -> None:
    clash = row("1", "a", "`x`", "advisory") + row("1", "b", "`x`", "advisory")
    text = HEAD.replace("## Writers", heading, 1) + clash
    code, out = run(tmp_path, text, "--require")
    assert (code, codes(out)) == (1, {"W2"}), heading


@pytest.mark.parametrize(
    "heading",
    ["# Writers", "##### Writers", "## Writers and roles", "## The Writers table", "## Writers 2"],
)
def test_other_headings_are_not_the_writers_heading(tmp_path: Path, heading: str) -> None:
    clash = row("1", "a", "`x`", "advisory") + row("1", "b", "`x`", "advisory")
    code, out = run(tmp_path, HEAD.replace("## Writers", heading, 1) + clash, "--require")
    assert (code, codes(out)) == (1, {"W8"}), heading


def test_a_sentence_may_precede_the_table_but_the_next_heading_ends_the_search(
    tmp_path: Path,
) -> None:
    clash = row("1", "a", "`x`", "advisory") + row("1", "b", "`x`", "advisory")
    intro = HEAD.replace("## Writers\n\n", "## Writers\n\nWho writes where, in one table.\n\n")
    code, out = run(tmp_path, intro + clash, "--require")
    assert (code, codes(out)) == (1, {"W2"}) and "1 Writers table(s)" in out
    table = HEAD.split("\n\n", 1)[1] + clash
    for later in ("## Other", "#### Deeper", "# Top"):
        text = f"## Writers\n\nNo parallel writers here.\n\n{later}\n\n{table}"
        code, out = run(tmp_path, text)
        assert (code, codes(out)) == (1, {"W7"}) and "no table under it" in out, later


def test_doc_says_a_row_is_one_worker_and_pipeline_shares_a_batch() -> None:
    table = section(DOC_TEXT, "## The Writers table", "## How to choose")
    assert (
        "**A row is one worker.**" in table and "two instances that share a path overlap" in table
    )
    assert "`<item>`" in table and "or write one row per instance" in table
    assert "Under `pipeline()`" in table and "stages of different items run together" in table
    assert "put every stage that writes in one batch" in table
    assert (
        "writers with the same batch number run at the same time; batch 2 starts after" not in table
    )
    step2 = next(ln for ln in DOC_TEXT.splitlines() if ln.startswith("2. Put writers"))
    assert "under `pipeline()`, every stage that writes shares one batch" in step2
    assert (
        "A harness with a single writer needs no table and must not be checked with `--require`"
        in table
    )
    limits = DOC_TEXT[DOC_TEXT.index("## Limits") :]
    assert "Do not run the checker on this file" in limits
    assert "It compares rows, and a row is one worker." in limits
    assert "`single-instance merger` or `Instances manager` is not read as per item" in limits
    assert "Only commas split a Writes cell." in limits
    assert "never a silent pass" in limits and "`src/a.py (new)`, `a;b`, `<br>`, a space" in limits
    assert "the next heading of any level ends the search" in limits
    assert "a Role that says none of these is not caught" in table
    writes = next(ln for ln in table.splitlines() if ln.startswith("- **Writes**"))
    for item in ("a `..` segment", "a `{`", "a space", "a quote", "a backtick", "`;`", "`:`"):
        assert item in writes, item
    for item in ("`#`", "`(`", "`<br`", "`/` or `~`", "`**`", "every path of its Writes cell"):
        assert item in (writes + table), item
    example = next(ln for ln in table.splitlines() if "<item>" in ln and ln.startswith("- **A row"))
    assert "_workspace/<item>/draft.md" in example


def test_batch_numbers_are_normalised_or_rejected(tmp_path: Path) -> None:
    for a, b in (("1", "01"), ("1", "Batch 1"), ("batch 2", "2"), ("3", " 03 ")):
        rows = (row(a, "a", "`x`", "advisory"), row(b, "b", "`x`", "advisory"))
        assert verdict(tmp_path, *rows) == (1, {"W2"}), (a, b)
    for bad in ("one", "1a", "1.5", "-1", "Batch"):
        code, found = verdict(tmp_path, row(bad, "a", "`x`", "advisory"))
        assert (code, found) == (1, {"W7"}), bad


def test_blank_line_inside_a_table_does_not_drop_rows(tmp_path: Path) -> None:
    text = HEAD + row("1", "a", "`x`", "advisory") + "\n" + row("1", "b", "`x`", "advisory")
    code, out = run(tmp_path, text)
    assert code == 1 and codes(out) == {"W7", "W2"} and "blank line inside" in out
    assert "1 Writers table(s)" in out


def test_second_table_under_one_heading_is_checked(tmp_path: Path) -> None:
    one = HEAD + row("1", "a", "`x`", "advisory")
    two = (
        HEAD.split("\n\n", 1)[1]
        + row("1", "b", "`y`", "advisory")
        + row("1", "c", "`y`", "advisory")
    )
    code, out = run(tmp_path, one + "\n" + two)
    assert code == 1 and codes(out) == {"W2"} and "2 Writers table(s)" in out


def test_bom_before_the_heading_is_ignored(tmp_path: Path) -> None:
    f = tmp_path / "o.md"
    f.write_bytes(b"\xef\xbb\xbf" + (HEAD + row("1", "a", "`x`", "enforced")).encode())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cw.main(["c", "--require", str(f)])
    assert code == 1 and codes(buf.getvalue()) == {"W4"}


def test_size_caps_report_w10_and_stay_fast(tmp_path: Path) -> None:
    many = "".join(row("1", f"w{i}", f"`d{i}/x`", "advisory") for i in range(51))
    assert verdict(tmp_path, many) == (1, {"W10"})
    assert verdict(
        tmp_path, "".join(row("1", f"w{i}", f"`d{i}/x`", "advisory") for i in range(50))
    ) == (0, set())
    assert verdict(tmp_path, row("1", "a", "`" + "a" * 501 + "`", "advisory")) == (1, {"W10"})
    paths = ", ".join(f"`p{i}`" for i in range(11))
    assert verdict(tmp_path, row("1", "a", paths, "advisory")) == (1, {"W10"})
    ten = ", ".join(f"`p{i}`" for i in range(10))
    assert verdict(tmp_path, row("1", "a", ten, "advisory")) == (0, set())
    slow = {
        "20k cell": row("1", "a", ", ".join(f"`p{i}`" for i in range(3300)), "advisory")
        + row("1", "b", ", ".join(f"`q{i}`" for i in range(3300)), "advisory"),
        "5000 rows": "".join(row("1", f"w{i}", f"`d{i}/x`", "advisory") for i in range(5000)),
        "w6 line": "advisory " + "not locked " * 30000,
    }
    for name, text in slow.items():
        start = time.perf_counter()
        code, _ = run(tmp_path, text if name == "w6 line" else HEAD + text)
        assert time.perf_counter() - start < 1.0, name
        assert code == (0 if name == "w6 line" else 1), name


# ---- composition with the existing gates ----------------------------------------------------


def test_surfaces_table_claims_only_what_the_surface_can_do() -> None:
    text = SURFACES.read_text(encoding="utf-8")
    block = section(text, "## 3c. Parallel writers by surface", "## 4. Primitive by surface")
    assert text.index("## 3b.") < text.index("## 3c.") < text.index("## 4. Primitive")
    by = {r[0]: set(re.findall(r"`([a-z-]+)`", r[1])) & set(cw.LABELS) for r in table_rows(block)}
    assert by["Claude chat"] == {"serialised"}
    assert by["Claude Cowork"] == {"serialised"}
    assert by["Claude Code"] == {"enforced", "workspace-enforced", "advisory", "serialised"}
    code_row = next(r for r in table_rows(block) if r[0] == "Claude Code")
    assert "`enforced` only if" in code_row[1]
    cowork = next(r for r in table_rows(block) if r[0] == "Claude Cowork")
    assert "Unverified" in cowork[1]
    assert "Single-context fallback carries no Writers table" in block


def test_delegation_block_keeps_its_shape_and_passes_w6(tmp_path: Path) -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    block = section(text, "````markdown\n### Delegating work", "\n````\n").split("\n", 1)[1]
    for lead in ("Goal", "Inputs", "Scope", "Expected output", "Report"):
        assert len(re.findall(rf"^- {lead}:", block, re.MULTILINE)) == 1, lead
    brief = section(block, "**Worker brief.**", "One task per call")
    assert len([ln for ln in brief.splitlines() if ln.startswith("- ")]) == 5
    scope = next(ln for ln in block.splitlines() if ln.startswith("- Scope:"))
    assert "Workers running in parallel get disjoint scopes." in scope
    assert "`## Writers` table" in scope and "never call advisory ownership exclusive" in scope
    assert all(f"`{label}`" in scope for label in cw.LABELS)
    assert run(tmp_path, block)[0] == 0
    assert run(tmp_path, block.replace("never call", "call"))[0] == 1
    lead = section(text, "Keep the phrases out of the pasted block", "````markdown")
    assert "`write-safety.md`" in lead and "`## Writers`" in lead


def test_pointers_land_once_in_the_right_place() -> None:
    patterns = PATTERNS.read_text(encoding="utf-8")
    fan = section(patterns, "### 1-2. Fan-out/fan-in", "### 1-3.")
    assert fan.count("**Write safety:**") == 1 and "`write-safety.md`" in fan
    assert patterns.count("**Write safety:**") == 1
    gates = GATES.read_text(encoding="utf-8")
    checklist = section(gates, "## 5. Checklist to paste", "## 6.")
    assert checklist.count("`## Writers` table") == 1 and "A label you cannot show" in checklist
    assert checklist.index("Sweep touched files") < checklist.index("`## Writers` table")
    assert checklist.index("`## Writers` table") < checklist.index("Report; do not fix")
    skill = SKILL_MD.read_text(encoding="utf-8")
    assert skill.count("references/write-safety.md") == 2
    assert skill.count("scripts/check_writers.py --require") == 1
    assert "- [ ] Every section that launches writers in parallel" in skill
    assert "- Parallel writers, the ownership ladder and honest labels:" in skill
    assert (SKILL / "references/write-safety.md").is_file()
    assert (SKILL / "scripts/check_writers.py").is_file()


ATTRIBUTION = {
    DOC: (
        "references/meta_harness/docs/architecture/runtime-capabilities.md:46 (Apache-2.0)",
        "references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0)",
    ),
    SCRIPT: (
        "references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0)",
        "references/meta_harness/docs/architecture/runtime-capabilities.md:46 (Apache-2.0)",
    ),
    SURFACES: (
        "adapted from references/meta_harness/docs/architecture/runtime-capabilities.md:46 (Apache-2.0)",
    ),
    PATTERNS: (
        "adapted from references/meta_harness/docs/architecture/runtime-capabilities.md:61 (Apache-2.0)",
    ),
    TEMPLATE: (
        "adapted from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0)",
    ),
    GATES: (
        "adapted from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0)",
    ),
    SKILL_MD: (
        "adapted from references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0)",
    ),
}
ANCHORS = {
    "docs/architecture/runtime-capabilities.md:46": "mechanical ownership",
    "docs/architecture/runtime-capabilities.md:61": "Never run conflicting",
    ".agents/skills/harness/SKILL.md:133": "Ownership requirements are not guarantees",
}


@pytest.mark.parametrize("path", list(ATTRIBUTION), ids=lambda p: p.name)
def test_attribution_lines(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for line in ATTRIBUTION[path]:
        assert line in text, line


@pytest.mark.skipif(
    not (META / "docs").is_dir(), reason="references/meta_harness submodule not checked out"
)
def test_cited_lines_say_what_we_claim() -> None:
    for where, token in ANCHORS.items():
        path, num = where.rsplit(":", 1)
        lines = (META / path).read_text(encoding="utf-8").splitlines()
        assert token in lines[int(num) - 1], where


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def added_text(path: Path) -> str:
    """The text this change added: whole new files, section 3c, or the lines naming the feature."""
    text = path.read_text(encoding="utf-8")
    if path in (DOC, SCRIPT):
        return text
    if path == SURFACES:
        return section(text, "## 3c. Parallel writers by surface", "## 4. Primitive")
    keys = ("write-safety", "Writers", "ownership")
    return "\n".join(ln for ln in text.splitlines() if any(k in ln for k in keys))


@pytest.mark.skipif(not (META / "docs").is_dir(), reason="references/meta_harness not checked out")
def test_no_eight_word_run_copied_from_the_source() -> None:
    seen: set[tuple[str, ...]] = set()
    for src in META.rglob("*.md"):
        w = words(src.read_text(encoding="utf-8"))
        seen.update(tuple(w[i : i + 8]) for i in range(len(w) - 7))
    for path in TOUCHED:
        w = words(added_text(path))
        runs = [" ".join(w[i : i + 8]) for i in range(len(w) - 7) if tuple(w[i : i + 8]) in seen]
        assert not runs, (path.name, runs[:3])
        assert len(w) > 20, path.name


def test_no_hangul() -> None:
    ranges = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
    for path in (*TOUCHED, Path(__file__)):
        text = path.read_text(encoding="utf-8")
        assert not any(lo <= ord(c) <= hi for c in text for lo, hi in ranges), path.name


def test_no_banned_tree_citation() -> None:
    for path in TOUCHED:
        assert f"references/autogpt/{BANNED}" not in path.read_text(encoding="utf-8")


def test_prose_decision_rules_are_pinned() -> None:
    patterns = PATTERNS.read_text(encoding="utf-8")
    assert "never run in the same batch unless at least one works in its own worktree" in patterns
    gates = GATES.read_text(encoding="utf-8")
    assert "no two `enforced` or `advisory` rows in one batch share a path" in gates
    assert "every `enforced` or `workspace-enforced` row names a mechanism" in gates
    template = TEMPLATE.read_text(encoding="utf-8")
    assert (
        "ownership counts as advisory unless something other than this brief blocks the write"
        in template
    )
    label = next(ln for ln in DOC_TEXT.splitlines() if ln.startswith("- **Label**"))
    assert "**Label**: the guarantee the run actually has" in label
    assert "**Wanted**: the rung the design asked for" in label
    assert "use rung 4 or stop" in DOC_TEXT and "does not make a writer `enforced`" in DOC_TEXT
    assert (
        "- No line that says `advisory` describes the ownership as exclusive, locked or guaranteed."
        in DOC_TEXT
    )
    ladder = section(DOC_TEXT, "Reading the last column", "A role is left out of the table")
    assert (
        "`allowed` means isolation makes the overlap safe to run, with a merge step afterwards"
        in ladder
    )
    assert "one ownership label per writer" in SKILL_MD.read_text(encoding="utf-8")
    surfaces = SURFACES.read_text(encoding="utf-8")
    block = section(surfaces, "## 3c. Parallel writers by surface", "## 4. Primitive")
    assert "unverified for a plain `Agent` call" in block
    assert "no sub-agent tool was exposed on the observed setup" in block
    assert "no sub-agent tool exists" not in block
    assert "a path-scoped permission rule or a hook that denies the path" in block
    chat = next(r for r in table_rows(block) if r[0] == "Claude chat")
    assert "observed 2026-10-03" in chat[2]
    assert "one account and client" in chat[1]
    scope = next(ln for ln in template.splitlines() if ln.startswith("- Scope:"))
    assert "has a per-item part such as `<item>` in its paths" in scope
    assert "one writer needs no table and is not run with `--require`" in SKILL_MD.read_text(
        encoding="utf-8"
    )
    limits = DOC_TEXT[DOC_TEXT.index("## Limits") :]
    assert "Path overlap, exactly:" in limits and "case-insensitively after Unicode NFC" in limits
    caps = re.search(
        r"capped at (\d+) rows and a Writes cell at (\d+) characters and (\d+) paths", DOC_TEXT
    )
    assert caps and tuple(map(int, caps.groups())) == (cw.MAX_ROWS, cw.MAX_CELL, cw.MAX_PATHS)


def test_judge_pins_prose_and_w9_edges(tmp_path: Path) -> None:
    para = next(ln for ln in DOC_TEXT.splitlines() if ln.startswith("A role is left out"))
    assert "(and without any MCP tool that writes)" in para  # M36
    assert "only if nothing it can use can write" in para  # M51
    limits = DOC_TEXT[DOC_TEXT.index("## Limits") :]
    assert "a `tools:` line without `Edit`, `Write` and `Bash` shows only" in limits  # M50
    assert (
        "`+`, `&`, `=>`, a fullwidth comma) are not split" in limits
        and "can pass silently" in limits
    )
    bullet = next(ln for ln in DOC_TEXT.splitlines() if ln.startswith("- **A row is one worker.**"))
    assert "each instance or N instances needs that part" in bullet  # M47
    one = "`out/x.md`"
    assert verdict(tmp_path, row("1", "wrapper file", one, "advisory")) == (0, set())  # M5
    assert verdict(
        tmp_path, row("1", "extractor", one, "advisory", note="writes each file once")
    ) == (
        0,
        set(),
    )  # M44
    for half in ("`out/<item.md`", "`out/item>.md`"):  # M27
        assert verdict(tmp_path, row("1", "worker per item", half, "advisory")) == (1, {"W9"})
    assert "stops the role writing through those tools" in para  # M30, both readings
    assert "no `advisory` row is called exclusive, " in GATES.read_text(encoding="utf-8")  # F24
    assert "and the orchestrator merges afterwards" in PATTERNS.read_text(encoding="utf-8")  # F26
    clash = row("1", "a", "`x`", "advisory") + row("1", "b", "`x`", "advisory")
    for heading in ("## _Writers_", "## Writers (a) (b)"):  # F9, F10
        code, out = run(tmp_path, HEAD.replace("## Writers", heading, 1) + clash)
        assert (code, codes(out)) == (1, {"W2"}), heading
    indented = "".join("  " + ln for ln in clash.splitlines(keepends=True))
    code, out = run(tmp_path, HEAD + indented)  # F11
    assert (code, codes(out)) == (1, {"W2"})
    assert verdict(tmp_path, row("1", "a", "x" * 500, "advisory")) == (0, set())  # F13
    assert verdict(tmp_path, row("1", "a", "x" * 501, "advisory")) == (1, {"W10"})
