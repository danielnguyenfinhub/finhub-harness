"""Proof for run-once phases (OR-S1): the `replay` column of scripts/state_ledger.py and section 3a of
references/state-ledger.md. tests/test_state_ledger.py is not touched and must keep passing.

The rules O1-O7 each have a behaviour check below. problems() runs every check against a script, a
doc, a SKILL.md and an orchestrator-template text, so the same function proves the real files (no
problems) and kills each mutant in MUTANTS (at least one problem carrying the expected tag).
Sources: see the attribution lines in references/state-ledger.md (Apache-2.0).
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import io
import itertools
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/state_ledger.py"
DOC = REPO / "skills/finhub-harness/references/state-ledger.md"
SKILL = REPO / "skills/finhub-harness/SKILL.md"
TEMPLATE = REPO / "skills/finhub-harness/references/orchestrator-template.md"
REFS = {  # reference files whose retry and resume text carries the once exception
    n: REPO / f"skills/finhub-harness/references/{n}.md"
    for n in ("execution-modes", "team-patterns", "team-examples", "workflow-recipes")
}

HEAD6 = "| phase | producer | consumer | path | sections | replay |"
SEP6 = "|---|---|---|---|---|---|"
HEAD5 = "| phase | producer | consumer | path | sections |"
SEP5 = "|---|---|---|---|---|"
Rows = list[tuple[str, str, str]]
ROWS: Rows = [  # phase, sections, replay
    ("1", "Findings; Gaps", "-"),
    ("2", "Intent; Result", "once"),
    ("3", "Verdict", "safe"),
    ("4", "Intent; Result", "once"),
]
TWO: Rows = [("1", "A", "-"), ("2", "Intent; Result", "once")]


def plan6(rows: Rows = ROWS) -> str:
    body = "".join(
        f"| {n} | p{n} | q{n} | _workspace/0{n}_{'abcd'[int(n) - 1]}.md | {s} | {r} |\n"
        for n, s, r in rows
    )
    return f"# Orchestrator\n\n## Handoff files\n\n{HEAD6}\n{SEP6}\n{body}"


def plan5(rows: Rows = ROWS) -> str:
    body = "".join(
        f"| {n} | p{n} | q{n} | _workspace/0{n}_{'abcd'[int(n) - 1]}.md | {s} |\n"
        for n, s, _ in rows
    )
    return f"# Orchestrator\n\n## Handoff files\n\n{HEAD5}\n{SEP5}\n{body}"


FULL = {
    1: "## Findings\nx\n\n## Gaps\ny\n",
    2: "## Intent\nkey k1\n\n## Result\nsent id 1\n",
    3: "## Verdict\nv\n",
    4: "## Intent\nkey k2\n\n## Result\nwritten id 2\n",
}
INTENT = "## Intent\nkey k1\n"
OLD_KEYS = {"LEDGER", "ACTION", "PHASE", "PATH", "REASON", "DRIFT", "SUSPECT"}
HANGUL = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
COUNTER = itertools.count()
OBSERVED: set[tuple[str, int]] = set()


def load(path: Path, name: str) -> ModuleType:
    """The script as a fresh module, run from its source so a mutant text can be loaded too."""
    mod = ModuleType(name)
    mod.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), mod.__dict__)  # noqa: S102
    return mod


class World:
    """A scratch project: plan.md plus a _workspace/, driven through the script's main()."""

    def __init__(self, mod: ModuleType, root: Path, plan: str | None = None) -> None:
        self.mod, self.root = mod, root
        (root / "_workspace").mkdir()
        (root / "plan.md").write_text(plan or plan6(), encoding="utf-8")

    def path(self, phase: int) -> Path:
        return self.root / f"_workspace/0{phase}_{'abcd'[phase - 1]}.md"

    def put(self, phase: int, text: str) -> Path:
        self.path(phase).write_text(text, encoding="utf-8")
        return self.path(phase)

    @property
    def ledger(self) -> Path:
        return self.root / "_workspace/00_state.md"

    def run(self, cmd: str = "resume") -> tuple[int, dict[str, list[str]]]:
        buf = io.StringIO()
        with contextlib.chdir(self.root), contextlib.redirect_stdout(buf):
            code = self.mod.main([cmd, "plan.md"])
        out: dict[str, list[str]] = {}
        for line in buf.getvalue().splitlines():
            key, _, val = line.partition(": ")
            out.setdefault(key, []).append(val)
        if "ACTION" in out:
            OBSERVED.add((out["ACTION"][0], code))
        out["_order"] = [line.partition(": ")[0] for line in buf.getvalue().splitlines()]
        return code, out

    def state(self, phase: int) -> tuple[str, str]:
        rows, _ = self.mod.parse_ledger(self.ledger.read_text(encoding="utf-8"))
        r = {x["phase"]: x for x in rows}[str(phase)]
        return r["completion"], r["note"]


@contextlib.contextmanager
def patched(attr: str, fn: Callable[..., object]) -> Iterator[None]:
    real_fn = getattr(Path, attr)
    setattr(Path, attr, fn)
    try:
        yield
    finally:
        setattr(Path, attr, real_fn)


def fresh(mod: ModuleType, tmp: Path, name: str, plan: str | None = None) -> World:
    d = tmp / name
    d.mkdir()
    return World(mod, d, plan)


def plan_hash(mod: ModuleType, plan: str) -> str:
    return str(mod.plan_hash(mod.parse_plan(plan)))


def o1_grammar(mod: ModuleType, tmp: Path) -> None:
    """The optional sixth column: accepted values, refusals, and no change for a five-column plan."""
    assert tuple(mod.PLAN_COLS) == ("phase", "producer", "consumer", "path", "sections")
    assert tuple(mod.REPLAY) == ("safe", "once", "-")
    w5 = fresh(mod, tmp, "five", plan5())
    for n in (1, 2, 3, 4):
        w5.put(n, FULL[n])
    w5.put(2, "## Intent\n")  # with no column this is an ordinary partial phase
    code, out5 = w5.run()
    assert (code, out5["ACTION"], out5["PHASE"]) == (0, ["resume"], ["2"]), out5
    assert set(out5) - {"_order"} == OLD_KEYS, "a five-column plan prints the old lines only"
    w6 = fresh(mod, tmp, "six_dash", plan6([(n, s, "-") for n, s, _ in ROWS]))
    for n in (1, 2, 3, 4):
        w6.put(n, FULL[n])
    w6.put(2, "## Intent\n")
    code, out6 = w6.run()
    assert (code, out6["ACTION"]) == (0, ["resume"]) and "HALF-DONE" not in out6, out6
    assert w5.ledger.read_text(encoding="utf-8") == w6.ledger.read_text(encoding="utf-8")
    for i, cell in enumerate(("once", "`once`", " once ", "safe", "-", "`-`")):
        w = fresh(mod, tmp, f"ok{i}", plan6([("1", "A", "-"), ("2", "Intent; Result", cell)]))
        assert w.run()[0] == 0, cell
    digest = plan_hash(mod, plan5())
    assert digest == plan_hash(mod, plan6()), "the marker is not part of the plan hash"
    flipped = [(n, s, "safe" if r == "once" else r) for n, s, r in ROWS]
    assert plan_hash(mod, plan6(flipped)) == digest
    legacy = (
        "# State ledger\nplan: plan.md\nplan-hash: " + digest + "\nnext: 1\n\n"
        "| phase | producer | consumer | path | sections | completion | note |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    for ph, s, _ in ROWS:
        legacy += f"| {ph} | p{ph} | q{ph} | _workspace/0{ph}_{'abcd'[int(ph) - 1]}.md | {s} | pending | - |\n"
    w = fresh(mod, tmp, "legacy", plan5())
    w.ledger.write_text(legacy, encoding="utf-8")
    code, out = w.run()
    assert out["LEDGER"] == ["ok"] and out["DRIFT"] == ["-"], out
    assert tuple(mod.COLS) == tuple(mod.PLAN_COLS) + ("completion", "note")
    assert w.ledger.read_text(encoding="utf-8") == legacy, "an old ledger is not rewritten"
    wide = legacy.replace("| completion | note |", "| completion | note | replay |")
    wide = wide.replace("|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|")
    wide = re.sub(r"(\| pending \| - \|)\n", r"\1 - |\n", wide)
    w = fresh(mod, tmp, "wide_ledger", plan5())
    w.ledger.write_text(wide, encoding="utf-8")
    assert w.run()[1]["LEDGER"][0].startswith("unreadable"), "the ledger keeps its seven columns"

    def refuse(name: str, plan: str, reason: str = "") -> None:
        wx = fresh(mod, tmp, name, plan)
        code, out = wx.run()
        assert code == 2 and out["ACTION"] == ["stop-no-plan"], (name, code, out)
        assert reason in out["REASON"][0], (name, out)
        assert not wx.ledger.exists(), name

    for i, cell in enumerate(("Once", "ONCE", "run-once", "yes", "once!", "onc", "safe;once")):
        refuse(f"bad{i}", plan6([("1", "A", "-"), ("2", "Intent; Result", cell)]))
    refuse("one_section", plan6([("1", "A", "-"), ("2", "Intent", "once")]))
    refuse("dash_sections", plan6([("1", "A", "-"), ("2", "-", "once")]))
    refuse("empty_name", plan6([("1", "A", "-"), ("2", "Intent;", "once")]))
    for i, same in enumerate(("Intent; Intent", "Intent;Intent", " Intent ;  Intent ", "A;A;A")):
        refuse(f"dup{i}", plan6([("1", "A", "-"), ("2", same, "once")]))
    wc = fresh(mod, tmp, "case_distinct", plan6([("1", "A", "-"), ("2", "Intent; intent", "once")]))
    assert wc.run()[0] == 0, "headings are case-sensitive, so Intent and intent are two sections"
    wd = fresh(mod, tmp, "dup_safe", plan6([("1", "A", "-"), ("2", "Intent; Intent", "safe")]))
    assert wd.run()[0] == 0, "duplicate names are refused for a once row only"
    for i, head in enumerate(("Replay", "REPLAY", "rePlay")):
        refuse(f"header{i}", plan6().replace("| replay |", f"| {head} |"), "[replay]")
    refuse("typo_header", plan6().replace("| replay |", "| replays |"))
    refuse("seven_cols", plan6().replace("| replay |", "| replay | more |"))
    refuse("short_row", plan6().replace("| Verdict | safe |", "| Verdict |"))
    refuse("empty_cell", plan6().replace("| Verdict | safe |", "| Verdict |  |"))
    refuse("fenced", "```md\n" + plan6() + "```\n")
    first_wins = plan5([("1", "A", "-"), ("2", "B", "-")]) + "\n" + plan6()
    wf = fresh(mod, tmp, "first_wins", first_wins)
    wf.put(1, "## A\n")
    wf.put(2, "## B\n")
    assert wf.run()[1]["ACTION"] == ["stop-done"], "the first matching table is the plan"


def o2_half_done(mod: ModuleType, tmp: Path) -> None:
    """Half done is read from the phase file alone."""
    cases: list[tuple[str, str | None, str, str]] = [
        ("absent", None, "pending", "-"),
        ("empty", "", "partial", "empty file"),
        ("blank", " \n\n", "partial", "empty file"),
        ("one_section", INTENT, "partial", "missing: Result"),
        ("last_only", "## Result\nr\n", "partial", "missing: Intent"),
        ("fenced", "```md\n## Intent\n## Result\n```\n", "partial", "missing: Intent, Result"),
        ("whole", FULL[2], "complete", "-"),
        ("bom", "\ufeff" + FULL[2], "complete", "-"),
    ]
    for name, text, state, note in cases:
        w = fresh(mod, tmp, f"c_{name}", plan6(TWO))
        w.put(1, "## A\n")
        if text is not None:
            w.path(2).write_text(text, encoding="utf-8")
        w.run("rebuild")
        assert w.state(2) == (state, note), (name, w.state(2))
        code, out = w.run()
        if state == "partial":
            assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), (name, out)
        elif state == "pending":
            assert (code, out["ACTION"]) == (0, ["start"]), (name, out)
        else:
            assert (code, out["ACTION"]) == (3, ["stop-done"]), (name, out)
    w = fresh(mod, tmp, "cap", plan6(TWO))
    w.put(1, "## A\n")
    real_cap = mod.CAP
    mod.__dict__["CAP"] = 40
    try:
        w.put(2, "## Intent\n## Result\n" + "x" * 30)
        code, out = w.run()
    finally:
        mod.__dict__["CAP"] = real_cap
    assert (code, out["ACTION"]) == (3, ["stop-confirm"]) and "byte limit" in out["REASON"][0]
    w = fresh(mod, tmp, "bytes", plan6(TWO))
    w.put(1, "## A\n")
    w.path(2).write_bytes(b"## Intent\n\xff\xfe\n## Result\n")
    assert w.run()[1]["ACTION"] == ["stop-done"]
    # something is there that is not a regular file
    w = fresh(mod, tmp, "dir", plan6(TWO))
    w.put(1, "## A\n")
    w.path(2).mkdir()
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
    w = fresh(mod, tmp, "dangling", plan6(TWO))
    w.put(1, "## A\n")
    w.path(2).symlink_to("missing.md")
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
    w = fresh(mod, tmp, "loop", plan6(TWO))
    w.put(1, "## A\n")
    w.path(2).symlink_to("02_b.md")
    code, out = w.run()
    assert (code, out["ACTION"]) in ((3, ["stop-confirm"]), (2, ["stop-no-plan"])), out
    # a symlink that stays inside is followed; one that leaves the project stops the run
    w = fresh(mod, tmp, "link_in", plan6(TWO))
    w.put(1, "## A\n")
    (w.root / "_workspace/real.md").write_text(FULL[2], encoding="utf-8")
    w.path(2).symlink_to("real.md")
    assert w.run()[1]["ACTION"] == ["stop-done"]
    outside = tmp / "outside.md"
    outside.write_text(FULL[2], encoding="utf-8")
    w = fresh(mod, tmp, "link_out", plan6(TWO))
    w.put(1, "## A\n")
    w.path(2).symlink_to(outside)
    code, out = w.run()
    assert (code, out["ACTION"]) == (2, ["stop-no-plan"]) and not w.ledger.exists(), out
    # a safe phase keeps its old reading: a directory in its place is pending, not half done
    w = fresh(mod, tmp, "safe_dir", plan6([("1", "A", "safe"), ("2", "B", "-")]))
    w.put(1, "## A\n")
    w.path(2).mkdir()
    code, out = w.run()
    assert (code, out["ACTION"]) == (0, ["start"]), out
    # an unreadable file and a directory that cannot be searched are half done, never a crash
    w = fresh(mod, tmp, "noopen", plan6(TWO))
    w.put(1, "## A\n")
    w.put(2, FULL[2])
    real_open = Path.open

    def deny(self: Path, *a: object, **k: object) -> object:
        if self.name == "02_b.md":
            raise PermissionError(13, "Permission denied")
        return real_open(self, *a, **k)  # type: ignore[call-overload]

    with patched("open", deny):
        code, out = w.run()
    assert (code, out["ACTION"]) == (3, ["stop-confirm"]) and "unreadable" in out["REASON"][0]
    w = fresh(mod, tmp, "nosearch", plan6(TWO))
    w.put(1, "## A\n")
    w.put(2, FULL[2])
    real_is_file = Path.is_file

    def cannot_search(self: Path) -> bool:
        if self.name == "02_b.md":
            raise PermissionError(13, "Permission denied")
        return real_is_file(self)

    with patched("is_file", cannot_search):
        code, out = w.run()
    assert (code, out["ACTION"]) == (3, ["stop-confirm"]) and "unreadable" in out["REASON"][0]
    vanished(mod, tmp)
    other_base(mod, tmp)
    lstat_denied(mod, tmp)
    redos(str(mod.__file__))


def vanished(mod: ModuleType, tmp: Path) -> None:
    """A run-once file that was there and is gone is half done; the same for a safe row is not."""
    w = fresh(mod, tmp, "gone")
    for n in (1, 2, 3, 4):
        w.put(n, FULL[n])
    assert w.run()[1]["ACTION"] == ["stop-done"]
    w.path(2).unlink()
    for run in range(3):  # the answer does not drift while the file stays gone
        code, out = w.run()
        assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
        had = "complete" if run == 0 else "partial"  # the first run rewrites the ledger as partial
        assert f"(file gone; the ledger had it {had})" in out["REASON"][0], out
        assert out["HALF-DONE"] == ["2"] and w.state(2)[0] == "partial"
    assert w.run("rebuild")[0] == 0 and not w.path(2).exists(), "a rebuild never recreates it"
    w.put(2, FULL[2])  # the user restores both sections
    assert w.run()[1]["ACTION"] == ["stop-done"]
    w = fresh(mod, tmp, "gone_partial")
    w.put(1, FULL[1])
    w.put(2, INTENT)
    assert w.run()[1]["ACTION"] == ["stop-confirm"]
    w.path(2).unlink()
    code, out = w.run()
    assert (code, out["ACTION"]) == (3, ["stop-confirm"]), out
    assert "(file gone; the ledger had it partial)" in out["REASON"][0], out
    # a safe row whose file vanished is simply pending again, as before
    w = fresh(mod, tmp, "gone_safe")
    for n in (1, 2, 3, 4):
        w.put(n, FULL[n])
    w.run()
    w.path(3).unlink()
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["3"]), out
    assert out["DRIFT"] == ["3: ledger complete, files pending"], out
    # a once row that was never started stays pending: there is nothing to have vanished
    w = fresh(mod, tmp, "never")
    w.put(1, FULL[1])
    w.run()
    assert w.run()[1]["ACTION"] == ["start"]
    # a blocked once row whose file vanished stays blocked, with the reminder
    w = fresh(mod, tmp, "gone_blocked")
    w.put(1, FULL[1])
    w.run("rebuild")
    edit_ledger(
        w,
        "| 2 | p2 | q2 | _workspace/02_b.md | Intent; Result | pending | - |",
        "| 2 | p2 | q2 | _workspace/02_b.md | Intent; Result | blocked | no sms credit |",
    )
    w.put(2, INTENT)
    w.path(2).unlink()
    code, out = w.run()
    assert out["ACTION"] == ["stop-blocked"] and out["REASON"][0].startswith("no sms credit"), out

    # limits (doc section 8): no evidence after a plan change, nor from an unreadable ledger, and
    # editing a row's path or marker defeats the protection
    def gone_world(name: str) -> World:
        wx = fresh(mod, tmp, name)
        for n in (1, 2, 3, 4):
            wx.put(n, FULL[n])
        wx.run()
        wx.path(2).unlink()
        return wx

    w = gone_world("limit_plan")
    (w.root / "plan.md").write_text(plan6().replace("| p2 |", "| px |"), encoding="utf-8")
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["2"]), out
    assert out["DRIFT"][0] == "plan changed, so no blocker is carried", out
    w = gone_world("limit_marker")
    flipped = [(n, s, "safe" if r == "once" else r) for n, s, r in ROWS]
    (w.root / "plan.md").write_text(plan6(flipped), encoding="utf-8")
    code, out = w.run()
    assert (code, out["ACTION"], out["DRIFT"][0][:2]) == (0, ["start"], "2:"), out
    w = gone_world("limit_corrupt")
    w.ledger.write_text("garbage", encoding="utf-8")
    code, out = w.run()
    assert out["ACTION"] == ["stop-unreadable"] and out["LEDGER"][0].startswith("unreadable"), out
    assert w.state(2) == ("pending", "-"), "an unreadable ledger is no evidence either"


def other_base(mod: ModuleType, tmp: Path) -> None:
    """The run-once reads join the --base directory, not the working directory."""
    here = tmp / "elsewhere"
    here.mkdir()

    def run_from_elsewhere(w: World) -> tuple[int, str, str]:
        buf = io.StringIO()
        argv = ["resume", str(w.root / "plan.md"), "--base", str(w.root)]
        with contextlib.chdir(here), contextlib.redirect_stdout(buf):
            code = mod.main(argv)
        out = buf.getvalue()
        return code, "".join(x for x in out.splitlines(True) if x.startswith("ACTION")), out

    w = fresh(mod, tmp, "base_dir", plan6(TWO))
    w.put(1, "## A\n")
    w.path(2).mkdir()  # something is there that is not a regular file
    code, action, out = run_from_elsewhere(w)
    assert (code, action) == (3, "ACTION: stop-confirm\n"), out
    assert "not a regular file" in out, out
    w.path(2).rmdir()
    w.put(2, FULL[2])
    assert run_from_elsewhere(w)[1] == "ACTION: stop-done\n"
    w.path(2).unlink()  # vanished: the ledger written from here says complete
    code, action, out = run_from_elsewhere(w)
    assert (code, action) == (3, "ACTION: stop-confirm\n"), out
    assert "file gone; the ledger had it complete" in out, out


def lstat_denied(mod: ModuleType, tmp: Path) -> None:
    """The error must not depend on Path.is_file raising: Python 3.14 swallows OSError there. Here
    is_file says False and only os.lstat raises, once the containment check has run."""
    w = fresh(mod, tmp, "lstat", plan6(TWO))
    w.put(1, "## A\n")
    w.put(2, FULL[2])
    real_lstat, real_contain, armed = os.lstat, mod.contain, []

    def contain_then_arm(*a: object, **k: object) -> None:
        real_contain(*a, **k)
        armed.append(1)

    def deny(path: object, *a: object, **k: object) -> object:
        if armed and Path(str(path)).name == "02_b.md":
            raise PermissionError(13, "Permission denied")
        return real_lstat(path, *a, **k)  # type: ignore[arg-type]

    real_is_file = Path.is_file

    def swallow(self: Path) -> bool:
        return False if self.name == "02_b.md" else real_is_file(self)

    mod.__dict__["contain"] = contain_then_arm
    os.lstat = deny  # type: ignore[assignment]
    try:
        with patched("is_file", swallow):
            code, out = w.run()
    finally:
        os.lstat = real_lstat
        mod.__dict__["contain"] = real_contain
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
    assert "unreadable" in out["REASON"][0], out
    # the same for a path whose parent is a plain file: nothing to have started, so pending
    w = fresh(mod, tmp, "notdir", plan6([("1", "A", "-"), ("2", "Intent; Result", "once")]))
    w.put(1, "## A\n")
    w.path(2).with_name("sub").write_text("x", encoding="utf-8")
    (w.root / "plan.md").write_text(
        plan6(TWO).replace("_workspace/02_b.md", "_workspace/sub/02_b.md"), encoding="utf-8"
    )
    assert w.run()[1]["ACTION"] == ["start"]


REDOS = """
import pathlib, sys, tempfile, time, types
m = types.ModuleType("m")
exec(compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec"), m.__dict__)
d, worst = pathlib.Path(tempfile.mkdtemp()), 0.0
for n in (20000, 80000):
    shapes = ["# a" + " " * n + "b", "# " + "#" * n + "x", "|" + " |" * n, "|" + " " * n + "x"]
    shapes += ["| phase |" * (n // 10), "| replay " * (n // 8) + "|", "`" * n + "x"]
    for s in shapes:
        f = d / "f.md"
        f.write_text("## Intent\\n" + s + "\\n## Result\\n")
        for call in (
            lambda: m.judge(f, "Intent; Result"),
            lambda: m.table(s + "\\n", m.PLAN_COLS, "replay"),
        ):
            t = time.perf_counter()
            try:
                call()
            except ValueError:
                pass
            worst = max(worst, time.perf_counter() - t)
print(worst)
"""


def redos(script: str) -> None:
    """The new header path takes the same adversarial lines as the old one, in linear time."""
    run = subprocess.run(
        [sys.executable, "-c", REDOS, script],
        capture_output=True,
        text=True,
        timeout=6,
        check=False,
    )
    assert run.returncode == 0, run.stderr[-300:]
    assert float(run.stdout.strip()) < 1.0, run.stdout


def edit_ledger(w: World, old: str, new: str) -> None:
    text = w.ledger.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    w.ledger.write_text(text.replace(old, new), encoding="utf-8")


def o3_decision(mod: ModuleType, tmp: Path) -> None:
    w = fresh(mod, tmp, "stop")
    w.put(1, FULL[1])
    w.put(2, INTENT)
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
    assert out["PATH"] == ["_workspace/02_b.md"] and out["REASON"][0].startswith("run-once phase")
    assert "missing: Result" in out["REASON"][0] and "ask the user" in out["REASON"][0]
    assert w.state(2) == ("partial", "missing: Result")
    assert "next: 2" in w.ledger.read_text(encoding="utf-8").splitlines()
    files = [w.path(1), w.path(2), w.root / "plan.md"]
    for f in files:
        os.utime(f, ns=(10**9, 10**9))
    before = {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in files}
    os.utime(w.ledger, ns=(10**9, 10**9))
    for _ in range(2):  # it stays put: same answer, nothing created, nothing rewritten
        code, out2 = w.run()
        assert (code, out2["ACTION"], out2["PHASE"]) == (3, ["stop-confirm"], ["2"])
        assert {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in files} == before
        assert w.ledger.stat().st_mtime_ns == 10**9
        assert sorted(p.name for p in (w.root / "_workspace").iterdir()) == [
            "00_state.md",
            "01_a.md",
            "02_b.md",
        ]
    code, out2 = w.run("rebuild")
    assert code == 0 and out2["NEXT"] == ["2"], "rebuild never stops"
    # the user's answer 'it happened' is a complete file; the run then goes on
    w.path(2).write_text(INTENT + "\n## Result\nconfirmed by the user; not checked\n", "utf-8")
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["3"]), out
    assert w.state(2) == ("complete", "-")
    # a complete run-once phase is not asked about again, and is not started again
    w.put(3, FULL[3])
    w.put(4, FULL[4])
    code, out = w.run()
    assert (code, out["ACTION"]) == (3, ["stop-done"]), out
    # a pending run-once phase starts; a safe partial phase still resumes
    w = fresh(mod, tmp, "pending")
    w.put(1, FULL[1])
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"], out["REASON"]) == (0, ["start"], ["2"], ["-"]), out
    w.put(2, FULL[2])
    w.put(3, "")
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["resume"], ["3"]), out
    # a half-done run-once phase that is not the first unfinished one does not stop, but is listed
    w = fresh(mod, tmp, "later")
    w.put(2, INTENT)
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["1"]), out
    assert out["HALF-DONE"] == ["2"], out
    # a blocker on a run-once row keeps its stop and says the effect may have happened
    w = fresh(mod, tmp, "blocked")
    w.put(1, FULL[1])
    w.run("rebuild")
    edit_ledger(
        w,
        "| 2 | p2 | q2 | _workspace/02_b.md | Intent; Result | pending | - |",
        "| 2 | p2 | q2 | _workspace/02_b.md | Intent; Result | blocked | no sms credit |",
    )
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-blocked"], ["2"]), out
    assert out["REASON"] == ["no sms credit; run-once phase, its effect may have happened"], out
    assert out["HALF-DONE"] == ["2"], out
    w = fresh(
        mod,
        tmp,
        "blocked_safe",
        plan6([("1", "A", "-"), ("2", "B", "safe"), ("3", "C; D", "once")]),
    )
    w.put(1, "## A\n")
    w.run("rebuild")
    edit_ledger(
        w,
        "| 2 | p2 | q2 | _workspace/02_b.md | B | pending | - |",
        "| 2 | p2 | q2 | _workspace/02_b.md | B | blocked | auth expired |",
    )
    code, out = w.run()
    assert out["REASON"] == ["auth expired"] and out["HALF-DONE"] == ["-"], out
    # an unreadable ledger does not hide a half-done run-once phase; its drift line still prints
    w = fresh(mod, tmp, "corrupt")
    w.put(1, FULL[1])
    w.put(2, INTENT)
    w.ledger.write_text("garbage", encoding="utf-8")
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
    assert out["LEDGER"][0].startswith("unreadable") and "unknown" in out["DRIFT"][0], out
    w.put(2, FULL[2])
    w.put(3, FULL[3])
    w.put(4, FULL[4])
    w.ledger.write_text("garbage", encoding="utf-8")
    assert w.run()[1]["ACTION"] == ["stop-done"], "done still wins over an unreadable ledger"
    # the ledger is still written whole, through one replace, and not again when unchanged
    w = fresh(mod, tmp, "atomic")
    w.put(1, FULL[1])
    w.put(2, INTENT)
    moved: list[object] = []
    real = os.replace

    def spy(src: object, dst: object) -> None:
        moved.append(dst)
        real(src, dst)  # type: ignore[arg-type]

    os.replace = spy  # type: ignore[assignment]
    try:
        w.run()
        w.run()
    finally:
        os.replace = real
    assert [Path(str(m)).name for m in moved] == ["00_state.md"], moved
    assert [p.name for p in (w.root / "_workspace").iterdir() if p.name.endswith(".tmp")] == []
    # a ledger that cannot be written still gives the stop
    w = fresh(mod, tmp, "unwritable")
    w.put(1, FULL[1])
    w.put(2, INTENT)
    w.ledger.mkdir()
    code, out = w.run()
    assert (code, out["ACTION"]) == (3, ["stop-confirm"]), out
    assert out["LEDGER"][0].startswith("unwritable"), out


def o4_half_done_line(mod: ModuleType, tmp: Path) -> None:
    w = fresh(mod, tmp, "none", plan6([(n, s, "-") for n, s, _ in ROWS]))
    w.put(1, FULL[1])
    _, out = w.run()
    assert "HALF-DONE" not in out and set(out) - {"_order"} == OLD_KEYS, out
    w = fresh(mod, tmp, "dash")
    w.put(1, FULL[1])
    _, out = w.run()
    assert out["HALF-DONE"] == ["-"] and out["_order"][-1] == "SUSPECT", out
    assert out["_order"].index("HALF-DONE") == out["_order"].index("SUSPECT") - 1
    w.put(2, INTENT)
    w.put(4, INTENT)
    _, out = w.run()
    assert out["HALF-DONE"] == ["2, 4"] and out["_order"][-1] == "SUSPECT", out
    w.put(2, FULL[2])  # complete once rows are not listed, but are suspect after the resume row
    w.put(3, "")
    _, out = w.run()
    assert out["HALF-DONE"] == ["4"] and out["ACTION"] == ["resume"], out
    w.put(4, FULL[4])
    _, out = w.run()
    assert out["HALF-DONE"] == ["-"] and out["SUSPECT"] == ["4"], out
    w = fresh(mod, tmp, "all_done")
    for n in (1, 2, 3, 4):
        w.put(n, FULL[n])
    code, out = w.run()
    assert (code, out["ACTION"], out["HALF-DONE"]) == (3, ["stop-done"], ["-"]), out


def o5_worker_order(mod: ModuleType, tmp: Path) -> None:
    """The file order a once worker follows: the first section alone is half done, the last
    section completes it, so a crash between the outside call and the last section is visible."""
    w = fresh(mod, tmp, "order", plan6([("1", "A", "-"), ("2", "Intent; Result; Receipt", "once")]))
    w.put(1, "## A\n")
    steps = [
        ("", ("partial", "empty file")),
        ("## Intent\nkey k1\n", ("partial", "missing: Result, Receipt")),
        ("## Intent\nkey k1\n\n## Result\nr\n", ("partial", "missing: Receipt")),
        ("## Intent\nkey k1\n\n## Result\nr\n\n## Receipt\nid\n", ("complete", "-")),
    ]
    for text, want in steps:
        w.path(2).write_text(text, encoding="utf-8")
        w.run("rebuild")
        assert w.state(2) == want, (text, w.state(2))


def o6_resolution(mod: ModuleType, tmp: Path) -> None:
    """Both answers leave the ledger consistent: 'it happened' completes the file; 'run it again'
    reuses the file, and a second crash stops again."""
    w = fresh(mod, tmp, "again")
    w.put(1, FULL[1])
    w.put(2, INTENT)
    assert w.run()[1]["ACTION"] == ["stop-confirm"]
    key = w.path(2).read_text(encoding="utf-8")
    assert "key k1" in key  # the brief of the re-run quotes this, the same key
    w.path(2).write_text(key + "\n## Result\nsent again with key k1\n", "utf-8")
    assert w.run()[1]["ACTION"] == ["start"]
    w.put(3, FULL[3])
    w.put(4, INTENT)
    assert w.run()[1]["ACTION"] == ["stop-confirm"], "the next run-once phase asks on its own"


def o7_no_auto_retry(mod: ModuleType, tmp: Path) -> None:
    """Why O7 exists: after a failed once worker the files say half done, `resume` stops, and
    `rebuild`, which a loop may run after every phase, prints a NEXT line that is not a stop."""
    w = fresh(mod, tmp, "rb")
    w.put(1, FULL[1])
    w.put(2, INTENT)  # the worker saved its intent, called out, and its report came back invalid
    code, out = w.run("rebuild")
    assert code == 0 and out["NEXT"] == ["2"], out
    assert "HALF-DONE" not in out and "ACTION" not in out, "rebuild prints LEDGER and NEXT only"
    code, out = w.run("resume")
    assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-confirm"], ["2"]), out
    w.path(2).write_text(INTENT + "\n## Result\npartial: outcome unknown\n", encoding="utf-8")
    assert w.run()[1]["ACTION"] == ["start"], "a complete file is the user's O6 decision, not O7"


CHECKS: dict[str, Callable[[ModuleType, Path], None]] = {
    "O1": o1_grammar,
    "O2": o2_half_done,
    "O3": o3_decision,
    "O4": o4_half_done_line,
    "O5": o5_worker_order,
    "O6": o6_resolution,
    "O7": o7_no_auto_retry,
}
RULES = {  # one phrase per rule that must stay in the doc's run-once table
    "O1": "`-` and an absent column both mean safe",
    "O2": "An absent file is not half done",
    "O3": "the decision is `stop-confirm`, exit 3, and nothing runs",
    "O4": "never starts, resumes or repeats a listed phase without the user's yes",
    "O5": "adds the last section only after the call is confirmed",
    "O6": "is asked once more, because the re-run repeats the effect",
    "O7": "never retried automatically and never re-asked",
}
PINS = {  # prose that tells the orchestrator what to do, with the count it must keep
    "the harness did not check": 1,
    "the same key in the brief": 1,
    "an order to skip any call the file records as done": 1,
    "is never re-run to refresh it": 1,
    "this comes before `stop-unreadable`": 1,
    "a phase that only drafts into `_workspace/` for a person to send is `safe`": 1,
    "ask the user whether it already ran": 1,
    "an intent block with no result block is a half-done phase": 1,
    "the key comes from the phase inputs, not from the attempt": 1,
    "the ledger asks and never checks": 1,
    "an idempotency key accepted by the connector is the real fix": 1,
    "the `once` marker is the author's declaration": 1,
    "a run-once phase whose file is absent reads as not started": 1,
    "o6 asks again before it repeats an effect": 1,
    "leave the column out of a plan that has no `once` phase": 1,
    "run `resume` and follow o6": 1,
    "its `next` line never starts a `once` phase (o7); run `resume` first": 1,
    "the script and `tests/test_state_ledger_runonce.py` enforce o1-o3": 1,
    "nothing checks that they are followed": 1,
    "unless the previous ledger recorded that phase as partial or complete": 1,
    "the previous ledger is no evidence when the plan changed": 1,
    "the vanished-file stop reads the previous ledger, so it needs one": 1,
    "changing a `once` row's path or marker between runs defeats the protection": 1,
    "distinct section names": 1,
    "o2 covers a vanished file": 1,
    "o2 covers a run-once file that vanished": 1,
    "a half-done run-once resume row stops as `stop-confirm` first": 1,
    "`plan-hash` covers the five plan columns only": 1,
    "a `half-done` line when the plan has a `once` phase": 1,
    "or moves money": 1,
    "uploads a file where others can see it": 1,
    "may also be `safe`, but only when the brief names that key; nothing checks it": 1,
    "the ledger cannot see an effect and does not try": 1,
    "or when the ledger was deleted or unreadable, there is no evidence": 1,
    "after a worker error, a timeout, an invalid report or `status: partial`, do not launch or ask that worker again; run `resume` and follow o6": 1,
    "write this exception into the orchestrator's error table and into the step that checks reports": 1,
    "a `once` stage that did not return a result is not resumed with `resumefromrunid`: its call may have gone out, so `resume` and o6 decide (rule o7)": 1,
    "and a delete of the file alone cannot make the phase start again": 1,
    "a half-done `once` row is the exception and stops (o3)": 1,
    "a test or dry run of a harness whose agent calls a live sending connector (sms, email, chat post, page publish, crm write) sends for real, and a fresh test run starts with no ledger. test such a harness against a stub or sandbox connector with synthetic recipients; the ledger does not see test runs.": 1,
    "| resume | 0 | re-runs `phase` with `path` and `reason` in the worker brief, and does not start the next phase before it is complete |": 1,
    "`resume` never names a half-done `once` phase; that case is `stop-confirm`.": 1,
}


def doc_block(doc: str) -> str | None:
    m = re.search(r"^```text\n(\| phase .*?)^```$", doc, re.DOTALL | re.MULTILINE)
    return m[1] if m else None


def doc_once(mod: ModuleType, doc: str) -> None:
    found = {m[1]: m[2] for m in re.finditer(r"^\| (O\d+) \| (.*) \|$", doc, re.MULTILINE)}
    assert set(found) == set(RULES) == set(CHECKS), (sorted(found), sorted(CHECKS))
    for rid, phrase in RULES.items():
        assert phrase in found[rid], (rid, phrase)
    (row,) = re.findall(r"^\| stop-confirm \| 3 \| (.*) \|$", doc, re.MULTILINE)
    assert "follows O6; runs nothing before the answer" in row, row  # it asks, it does not resend
    assert "when `LEDGER` is unreadable, because a blocker elsewhere may have been lost" in row
    head = doc.splitlines()[2]
    assert "declared and, when half done, stopped on resume" in head and "never replayed" not in doc
    assert (
        "Each rule is enforced by `scripts/state_ledger.py` and by a test in `tests/test_state_ledger_runonce.py`"
        not in doc
    )
    assert OBSERVED >= {("stop-confirm", 3), ("start", 0), ("resume", 0), ("stop-done", 3)}
    block = doc_block(doc)
    assert block is not None
    rows = mod.parse_plan(block)  # the grammar example is a valid plan
    assert [(r["phase"], r["replay"]) for r in rows] == [("1", "-"), ("2", "once")]
    assert not any(lo <= ord(c) <= hi for c in doc for lo, hi in HANGUL), "Hangul"
    start = doc.index("## 6. Claude chat and Claude Cowork")
    chat = doc[start : doc.index("## 7.")]
    assert "ask the user whether it already ran" in chat
    assert not re.search(r"SendMessage|Agent\(|TaskCreate|Workflow|subagent_type", chat)
    low = doc.lower()
    cover = low[low.index("## 8. does not cover") :]
    for phrase in (
        "the `once` marker is the author's declaration",
        "an idempotency key accepted by the connector is the real fix",
        "a run-once phase whose file is absent reads as not started",
        "also reads as half done, so that crash costs the user one question",
        "fails closed, and the fix is to copy the current script",
    ):
        assert phrase in cover, phrase
    for phrase, count in PINS.items():
        assert low.count(phrase) >= count, phrase
    sec3a = doc[doc.index("## 3a.") : doc.index("## 4.")]
    assert "tests/test_state_ledger_runonce.py" in sec3a
    assert "a complete one is not run again while its file is there" in sec3a
    assert "NEXT" in doc[doc.index("## 4.") : doc.index("## 5.")]  # rebuild prints no HALF-DONE


def doc_attrib(doc: str, skill: str, template: str, script: str) -> None:
    rig = "references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0)"
    cp = "references/openrig/docs/as-built/architecture/coordination-primitive.md:46 (Apache-2.0)"
    ar = "openrig/docs/as-built/architecture/architecture-rules-and-event-system.md:74"
    assert f"adapted from {rig}" in doc and f"adapted from {cp}" in doc
    assert f"adapted from references/{ar} (Apache-2.0)" in doc
    assert f"adapted from {rig}" in skill and f"adapted from {cp}" in template
    assert "# adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0)" in script
    assert f"# adapted from references/{ar} (Apache-2.0)" in script
    assert not re.search(r"# adapted from openrig/", script), "the repo form has references/"
    for text in (doc, skill, template, script):
        assert "autogpt" + "_platform" not in text  # split so a licence grep stays clean
    for text in (skill, template, script):
        assert not any(lo <= ord(c) <= hi for c in text for lo, hi in HANGUL), "Hangul"


def skill_once(skill: str) -> None:
    (step0,) = [x for x in skill.splitlines() if x.startswith("- **Step 0 context check**")]
    assert "`once`" in step0 and "`replay`" in step0 and "section 3a" in step0
    assert "stops and asks about a half-done one instead of running it again" in step0
    assert "sends, publishes, uploads or writes a record outside the workspace" in step0
    assert "a named partial re-run still wins" in step0  # the C11 sentence is intact
    assert (
        "`resumeFromRunId` when `run_meta.json` has one, except for a `once` stage that did not"
        " return a result (`references/state-ledger.md` section 3a, rule O7)."
    ) in step0
    old = "- State ledger, rebuild and resume across context resets: `references/state-ledger.md`"
    lines = skill.splitlines()
    assert old in lines, "the C11 References bullet is unchanged"
    new = (
        "- Run-once phases: a resume stops and asks about a half-done send, publish or record write"
    )
    (bullet,) = [x for x in lines if x.startswith(new)]
    assert (
        "section 3a" in bullet
        and "idempotency key accepted by the connector is the real fix" in bullet
    )
    assert "never repeats" not in skill, "the ledger reads files; it does not promise no repeat"
    (policy,) = [x for x in lines if x.startswith("- **Error policy**")]
    assert "a `once` phase is never retried automatically: it stops and asks" in policy
    assert "rule O7" in policy
    (deleg,) = [x for x in lines if x.startswith("- **Delegation contract**")]
    assert "a `once` phase is never re-asked" in deleg
    assert (
        "the orchestrator re-asks once and then marks the result unverified"
        " (a `once` phase is never re-asked)."
    ) in skill, "the checklist line carries the exception"
    rerun_scan("SKILL.md", lines)


O6 = "rule O6 of `state-ledger.md` section 3a"
ATT = " (adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0))"
RERUN = (  # the template phrases that re-execute a failed or stopped worker or stage
    r"instruct it again|fix only the failed stage|retry once|re-ask once|resumeFromRunId"
    r"|launch a replacement agent named|launch the same custom type|re-run the stages"
    r"|launch a replacement agent|once more|try again|reassign|redistribut|relaunch|call it again|retry the"
    r"|(?:send|ask|tell) (?:it|them|that worker|the worker) again"
    r"|(?:hand|pass|give) (?:the|this|that) (?:task|phase|work|stage)\b[^.]{0,40}(?:another|a different|a fresh) (?:teammate|worker|agent)"
)
BLOCK_SHA = (
    "067918a36acc80c749037332240a990930cde75392a5a2281bd410437514d221"  # pasted Delegating block
)
TEMPLATE_CLAUSES = (
    f"A stage marked `once` is never fixed and resumed this way: run `resume` and follow {O6}.",
    f"you can continue with `resumeFromRunId`, except a stage marked `once`: run `resume` and follow {O6}.",
    f"(For a teammate whose phase is marked `once`, do neither: run `resume` and follow {O6}.)",
    f"A stage marked `once` that failed or was interrupted is not resumed this way: run `resume` and follow {O6}.",
    f"except a stage marked `once`, which is never re-run to refresh it: tell the user its effect used the earlier content ({O6}).",
    f"Do not send a revision request to a teammate whose phase is marked `once` after its effect has gone out: {O6}.",
)
REFS_CLAUSES = {
    "execution-modes": (
        f"For a phase marked `once`, leave `opts.schema` off: whether that retry repeats the agent's outside call is not known, and rule O7 of `state-ledger.md` section 3a forbids a retry of a `once` phase.{ATT}",
        f"A stage marked `once` that did not return a result is not resumed this way, because its call may have gone out: run `resume` and follow {O6}. A `once` stage that already returned a result is cached only while its prompt is unchanged: pass such a stage file paths and its key, never the text of an upstream result, so editing an upstream stage cannot make it run again; if its prompt must change, treat it as a named re-run of that stage and ask under {O6}.",
    ),
    "team-patterns": (
        f"A phase marked `once` is not part of this loop: verify before it runs, and after a failure run `resume` and follow {O6}.{ATT}",
        f"A phase marked `once` is never redistributed after a failure: run `resume` and follow {O6}.",
    ),
    "team-examples": (
        f"A task of a phase marked `once` is not reassigned: run `resume` and follow {O6}.{ATT}",
    ),
    "workflow-recipes": (
        f"so a script with a stage marked `once` is not called again after that stage started: run `resume` and follow {O6}.{ATT}",
    ),
}


def refs_once(refs: dict[str, str]) -> None:
    for name, clauses in REFS_CLAUSES.items():
        for clause in clauses:
            assert clause in refs[name], (name, clause[:80])
    assert sum(x.count(O6) for x in refs.values()) == 6, "six sites in the reference files"
    for name, text in refs.items():  # one attribution line per changed file (licence gate)
        assert text.count(ATT.strip()) == 1, name
    assert not any(lo <= ord(c) <= hi for x in refs.values() for c in x for lo, hi in HANGUL)
    assert "A new call without `resumeFromRunId` runs every stage again" in refs["workflow-recipes"]
    for name, text in refs.items():
        rerun_scan(name, text.splitlines())


RERUN_OK = {  # class G or N lines: a named partial re-run, or pattern text whose exception follows
    "SKILL.md": (
        "(re-ask once, then mark the result unverified; a `once` phase is never re-asked)",
        "(and `resumeFromRunId` for Workflow mode)",
    ),
    "template": ("so do not instruct again or launch a replacement agent.",),
    "execution-modes": ("add the `resumeFromRunId` option to Workflow orchestration (Mode A).",),
    "team-patterns": (
        "A supervisor watches progress and redistributes the work.",
        "and redistributes the work with `SendMessage` and `TaskUpdate`",
    ),
}


def rerun_scan(name: str, lines: list[str]) -> None:
    """Any line that re-runs a failed or stopped worker carries the exception on it or on its wrapped line."""
    for i, line in enumerate(lines):
        wrapped = lines[i + 1] if i + 1 < len(lines) and lines[i + 1][:1] == " " else ""
        near = f"{line} {wrapped}"  # an indented next line is the same item wrapped
        scan = line
        for ok in RERUN_OK.get(name, ()):
            scan = scan.replace(ok, "")  # only the named text is exempt, not the rest of its line
        if re.search(RERUN, scan, re.IGNORECASE):
            assert "`once`" in near and re.search(r"O[67]", near), (name, line[:120])


def template_once(template: str) -> None:
    (para,) = [x for x in template.splitlines() if x.startswith("A phase marked `once`")]
    assert "adds the last section only after the call is confirmed" in para
    assert "A re-run that the user approves after a stop carries the same key" in para
    assert "state-ledger.md` section 3a" in para
    assert template.index(para) < template.index("### Delegating work")  # outside the pasted block
    assert "passes the key to the connector when the connector takes one" in para
    assert "never from the time of the attempt" in para
    assert "(what it will do, to whom, and a key" in para
    assert "outside the retry-once rule of the Error handling section" in para
    assert "outside the single re-ask of the Delegating block" in para
    assert "run `state_ledger.py resume` and follow rule O6" in para and "rule O7" in para
    assert (
        "after a worker error, a timeout, an invalid report or `STATUS: partial`, do not launch"
        " or ask that worker again; run `state_ledger.py resume`"
    ) in para
    assert "never start a `once` phase from the `NEXT` line of `rebuild`" in para
    assert "Write that exception into the orchestrator's error table" in para
    block = template[
        template.index("### Delegating work") : template.index(
            "\n````\n", template.index("### Delegating work")
        )
    ]
    assert "`once`" not in block and "O7" not in block, "the pasted block is left as it was"
    assert "If one agent fails, retry once, except a phase marked `once` (never retried" in template
    assert template.count("rule O6 of `state-ledger.md` section 3a") == 10, "para + nine sites"
    for clause in TEMPLATE_CLAUSES:
        assert clause in template, clause
    pasted = template.index("### Delegating work")
    end = template.index("\n````\n", pasted)
    rerun_scan("template", (template[:pasted] + template[end:]).splitlines())
    pasted_block = re.search(r"````markdown\n(.*?)\n````\n", template, re.DOTALL)
    assert pasted_block is not None
    assert hashlib.sha256(pasted_block[1].encode()).hexdigest() == BLOCK_SHA, "pasted block changed"
    assert "For a phase marked `once`, do not run it again" in template
    assert "For a phase marked `once`, do not instruct it again" in template


def real_refs() -> dict[str, str]:
    return {n: p.read_text(encoding="utf-8") for n, p in REFS.items()}


def problems(
    script: Path, doc: str, skill: str, template: str, refs: dict[str, str] | None = None
) -> list[str]:
    found: list[str] = []
    OBSERVED.clear()

    def attempt(tag: str, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - a crash in a mutant counts as a failed check
            found.append(f"{tag}: {type(e).__name__}: {str(e)[:200]}")

    try:
        mod = load(script, f"state_ledger_once_{next(COUNTER)}")
    except Exception as e:  # noqa: BLE001
        return [f"O1: script does not load: {e}"]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for rid, check in CHECKS.items():
            d = tmp / rid
            d.mkdir()
            attempt(rid, functools.partial(check, mod, d))
    attempt("doc-once", lambda: doc_once(mod, doc))
    text = script.read_text(encoding="utf-8")
    attempt("doc-attrib", lambda: doc_attrib(doc, skill, template, text))
    attempt("skill-once", lambda: skill_once(skill))
    attempt("template-once", lambda: template_once(template))
    attempt("refs-once", lambda: refs_once(real_refs() if refs is None else refs))
    return found


def sub(old: str, new: str, count: int = 1) -> Callable[[str], str]:
    def fn(text: str) -> str:
        assert text.count(old) == count, (old, text.count(old))
        return text.replace(old, new)

    return fn


def drop_line(pattern: str) -> Callable[[str], str]:
    def fn(text: str) -> str:
        out, n = re.subn(pattern, "", text, count=1, flags=re.MULTILINE)
        assert n == 1, pattern
        return out

    return fn


HALF = 'first["phase"] in once and first["completion"] == "partial"'
STOP = (
    f"    elif {HALF}:\n"
    '        act, why = "stop-confirm", f"run-once phase, half done ({first[\'note\']}); ask the user"\n'
)
CORRUPT = (
    "    elif corrupt:\n"
    "        act, why = (\n"
    '            "stop-unreadable",\n'
    '            "a blocker may have been lost; ask the user, then resume again",\n'
    "        )\n"
)
LEDGER_OF_SKILL = "- State ledger, rebuild and resume across context resets:"
STEP0_ONCE = (
    " A phase that sends, publishes, uploads or writes a record outside the workspace is marked"
    " `once` in the optional `replay` column of that table, so a resume stops and asks about a"
    " half-done one instead of running it again (`references/state-ledger.md` section 3a)."
)

# (name, target, expected check, edit). Each is a plausible regression; none is behaviour-neutral.
MUTANTS: list[tuple[str, str, str, Callable[[str], str]]] = [
    ("M01 sixth column never read", "script", "O1", sub('PLAN_COLS, "replay")', "PLAN_COLS)")),
    (
        "M02 unknown replay value is safe",
        "script",
        "O1",
        sub('if r["replay"] not in REPLAY:', "if False:"),
    ),
    (
        "M03 replay compared without case",
        "script",
        "O1",
        sub('r.setdefault("replay", "-")', 'r["replay"] = r.get("replay", "-").lower()'),
    ),
    (
        "M04 a run-once row may list one section",
        "script",
        "O1",
        sub('len({x.strip() for x in r["sections"].split(";")}) < 2', 'r["sections"] == "-"'),
    ),
    (
        "M05 run-once row needs no sections at all",
        "script",
        "O1",
        sub(
            'if r["replay"] == "once" and len({x.strip() for x in r["sections"].split(";")}) < 2:',
            "if False:",
        ),
    ),
    (
        "M06 a dash in replay is refused",
        "script",
        "O1",
        sub('REPLAY = ("safe", "once", "-")', 'REPLAY = ("safe", "once")'),
    ),
    (
        "M07 plan hash covers the marker",
        "script",
        "O1",
        sub('"|".join(p[c] for c in PLAN_COLS)', '"|".join(p[c] for c in (*PLAN_COLS, "replay"))'),
    ),
    (
        "M08 ledger gains the replay column",
        "script",
        "O1",
        sub(
            'COLS = PLAN_COLS + ("completion", "note")',
            'COLS = PLAN_COLS + ("replay", "completion", "note")',
        ),
    ),
    (
        "M09 only the six-column header is a plan",
        "script",
        "O1",
        sub("if got not in heads:", "if got != heads[-1]:"),
    ),
    (
        "M10 matched header not adopted",
        "script",
        "O1",
        sub(
            "        cols = tuple(got)  # the header that matched, with or without the optional column\n",
            "",
        ),
    ),
    (
        "M11 absent replay is not defaulted",
        "script",
        "O1",
        sub('        r.setdefault("replay", "-")\n', ""),
    ),
    (
        "M12 absent replay means once",
        "script",
        "O1",
        sub('r.setdefault("replay", "-")', 'r.setdefault("replay", "once")'),
    ),
    (
        "M14 an absent run-once file is half done",
        "script",
        "O2",
        sub("except (FileNotFoundError, NotADirectoryError):", "except ZeroDivisionError:"),
    ),
    (
        "M15 a directory in place of a run-once file is pending",
        "script",
        "O2",
        sub(
            '            else:\n                state, note = "partial", "something is there that is not a regular file"\n',
            "            else:\n                pass\n",
        ),
    ),
    (
        "M16 a dangling symlink reads as absent",
        "script",
        "O2",
        sub("os.lstat(base", "os.stat(base"),
    ),
    (
        "M17 the not-a-file rule applies to every phase",
        "script",
        "O2",
        sub('if state == "pending" and p["replay"] == "once":', 'if state == "pending":'),
    ),
    (
        "M18 a run-once decision needs the empty-file note",
        "script",
        "O3",
        sub(HALF, 'first["phase"] in once and first["note"] == "empty file"'),
    ),
    ("M19 a half-done run-once phase resumes", "script", "O3", sub(STOP, "")),
    (
        "M20 stop-confirm exits 0",
        "script",
        "O3",
        sub(
            'return 3 if act.startswith("stop") else 0',
            'return 3 if act.startswith("stop") and act != "stop-confirm" else 0',
        ),
    ),
    ("M21 every partial phase asks", "script", "O3", sub(HALF, 'first["completion"] == "partial"')),
    (
        "M22 a pending run-once phase asks",
        "script",
        "O3",
        sub(HALF, 'first["phase"] in once and first["completion"] != "complete"'),
    ),
    (
        "M23 the safe phases are the run-once ones",
        "script",
        "O3",
        sub('if p["replay"] == "once"}', 'if p["replay"] != "once"}'),
    ),
    (
        "M24 unreadable ledger beats the half-done stop",
        "script",
        "O3",
        lambda t: sub(STOP + CORRUPT, CORRUPT + STOP)(t),
    ),
    (
        "M25 the reason loses the note",
        "script",
        "O3",
        sub("half done ({first['note']}); ask the user", "half done; ask the user"),
    ),
    (
        "M26 the reason does not ask the user",
        "script",
        "O3",
        sub('); ask the user"', ')"'),
    ),
    (
        "M27 blocked run-once row has no reminder",
        "script",
        "O3",
        sub(
            '    if act == "stop-blocked" and first and first["phase"] in once:\n'
            '        why += "; run-once phase, its effect may have happened"\n',
            "",
        ),
    ),
    (
        "M28 every blocked row gets the reminder",
        "script",
        "O3",
        sub(
            'if act == "stop-blocked" and first and first["phase"] in once:',
            'if act == "stop-blocked" and first:',
        ),
    ),
    (
        "M29 HALF-DONE printed for every plan",
        "script",
        "O4",
        sub("    if once:\n        half", "    if True:\n        half"),
    ),
    (
        "M30 HALF-DONE never printed",
        "script",
        "O4",
        sub("    if once:\n        half", "    if False:\n        half"),
    ),
    (
        "M31 HALF-DONE leaves out blocked rows",
        "script",
        "O3",
        sub('in ("partial", "blocked")', 'in ("partial",)'),
    ),
    (
        "M32 HALF-DONE lists complete run-once rows",
        "script",
        "O4",
        sub('in ("partial", "blocked")', 'in ("partial", "blocked", "complete")'),
    ),
    (
        "M33 HALF-DONE lists safe rows too",
        "script",
        "O4",
        sub('if r["phase"] in once and r["completion"] in', 'if r["completion"] in'),
    ),
    (
        "M34 HALF-DONE comes after SUSPECT",
        "script",
        "O4",
        lambda t: sub(
            '        print("HALF-DONE: " + (", ".join(half) or "-"))\n'
            "    print(\n"
            '        "SUSPECT: " + (", ".join(r["phase"] for r in after if r["completion"] == "complete") or "-")\n'
            "    )\n",
            "    print(\n"
            '        "SUSPECT: " + (", ".join(r["phase"] for r in after if r["completion"] == "complete") or "-")\n'
            "    )\n"
            '    if once:\n        print("HALF-DONE: " + (", ".join(half) or "-"))\n',
        )(t),
    ),
    (
        "M35 ledger written in place, not replaced",
        "script",
        "O3",
        sub(
            "        os.replace(tmp, path)\n",
            '        path.write_text(Path(tmp).read_text(encoding="utf-8"), encoding="utf-8")\n'
            "        os.unlink(tmp)\n",
        ),
    ),
    (
        "M36 ledger rewritten on every run",
        "script",
        "O3",
        sub("        if current != text:\n", "        if True:\n"),
    ),
    (
        "M37 containment check dropped",
        "script",
        "O2",
        sub("        if not inside:\n", "        if False:\n"),
    ),
    (
        "M38 unopenable file crashes",
        "script",
        "O2",
        sub(
            '    except OSError as e:\n        return "partial", f"unreadable: {e}"\n',
            '    except KeyError as e:\n        return "partial", f"unreadable: {e}"\n',
        ),
    ),
    (
        "M39 a directory that cannot be searched is absent",
        "script",
        "O2",
        sub(
            '    try:\n        if not path.is_file():\n            return "pending", "-"\n',
            '    if not path.is_file():\n        return "pending", "-"\n    try:\n',
        ),
    ),
    ("M40 size cap ignored", "script", "O2", sub("if len(raw) > CAP:", "if False:")),
    ("M41 byte order mark kept", "script", "O2", sub('"utf-8-sig"', '"utf-8"')),
    (
        "M42 fences never open",
        "script",
        "O2",
        sub(
            "        elif m:\n            fence = m[1]\n",
            "        elif False:\n            fence = m[1]\n",
        ),
    ),
    (
        "M43 quadratic heading regex back",
        "script",
        "O2",
        sub(
            'HEAD = re.compile(r"#{1,6}\\s+(\\S.*)")',
            'HEAD = re.compile(r"#{1,6}\\s+(.+?)\\s*#*\\s*$")',
        ),
    ),
    (
        "D01 priority over the unreadable ledger reversed",
        "doc",
        "doc-once",
        sub("This comes before `stop-unreadable`", "This comes after `stop-unreadable`"),
    ),
    (
        "D02 listed phases may start without a yes",
        "doc",
        "doc-once",
        sub(
            "never starts, resumes or repeats a listed phase without the user's yes",
            "may start a listed phase",
        ),
    ),
    (
        "D03 the second question is dropped",
        "doc",
        "doc-once",
        sub("is asked once more, because the re-run repeats the effect", "is not asked"),
    ),
    (
        "D04 the not-checked admission is dropped",
        "doc",
        "doc-once",
        sub("and that the harness did not check", "and that it is checked"),
    ),
    ("D05 stop-confirm row removed", "doc", "doc-once", drop_line(r"^\| stop-confirm \| 3 \|.*\n")),
    (
        "D06 stop-confirm exit changed",
        "doc",
        "doc-once",
        sub("| stop-confirm | 3 |", "| stop-confirm | 0 |"),
    ),
    (
        "D07 the grammar example uses a capital",
        "doc",
        "doc-once",
        sub("| Intent; Result | once |\n```", "| Intent; Result | Once |\n```"),
    ),
    (
        "D08 an absent file is half done",
        "doc",
        "doc-once",
        sub("An absent file is not half done", "An absent file is half done"),
    ),
    (
        "D09 chat question dropped",
        "doc",
        "doc-once",
        sub(
            ", and before a run-once phase ask the user whether it already ran, because no record"
            " of an earlier run can exist here",
            "",
        ),
    ),
    (
        "D10 idempotency key limit dropped",
        "doc",
        "doc-once",
        drop_line(r"^- An idempotency key accepted by the connector.*\n"),
    ),
    (
        "D11 drafting phases count as run-once",
        "doc",
        "doc-once",
        sub(
            "A phase that only drafts into `_workspace/` for a person to send is `safe`",
            "A phase that drafts is `once`",
        ),
    ),
    (
        "D12 the key comes from the attempt",
        "doc",
        "doc-once",
        sub(
            "the key comes from the phase inputs, not from the attempt",
            "the key is new for each attempt",
        ),
    ),
    (
        "D13 a suspect run-once phase is re-run",
        "doc",
        "doc-once",
        sub("is never re-run to refresh it", "is re-run to refresh it"),
    ),
    (
        "D14 attribution removed",
        "doc",
        "doc-attrib",
        sub(
            "adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0)",
            "based on an idea",
        ),
    ),
    (
        "D17 the column is wanted in every plan",
        "doc",
        "doc-once",
        sub(" Leave the column out of a plan that has no `once` phase.", ""),
    ),
    (
        "D18 the false-positive limit is dropped",
        "doc",
        "doc-once",
        drop_line(r"^- A worker that stopped after saving its first section.*\n"),
    ),
    (
        "D19 the old-script limit is dropped",
        "doc",
        "doc-once",
        drop_line(r"^- A copy of `state_ledger.py` made before section 3a.*\n"),
    ),
    ("D15 Hangul added", "doc", "doc-once", lambda t: t + "\n\uac00\n"),
    (
        "D16 chat section names a messaging tool",
        "doc",
        "doc-once",
        sub("## 7. How it fits", "SendMessage\n\n## 7. How it fits"),
    ),
    ("K01 Step 0 sentence removed", "skill", "skill-once", sub(STEP0_ONCE, "")),
    (
        "K02 new References bullet removed",
        "skill",
        "skill-once",
        drop_line(r"^- Run-once phases: a resume stops.*\n"),
    ),
    (
        "K03 old References bullet reworded",
        "skill",
        "skill-once",
        sub(LEDGER_OF_SKILL, "- State ledger and run-once phases:"),
    ),
    (
        "K04 skill attribution removed",
        "skill",
        "doc-attrib",
        sub("; adapted from references/openrig/docs/reference/rig-spec.md:519 (Apache-2.0)", ""),
    ),
    (
        "T01 template paragraph removed",
        "template",
        "template-once",
        drop_line(r"^A phase marked `once`.*\n\n"),
    ),
    (
        "T02 template retry carries a new key",
        "template",
        "template-once",
        sub(
            "A re-run that the user approves after a stop carries the same key.",
            "A re-run that the user approves after a stop carries a new key.",
        ),
    ),
    (
        "T03 template result written before the call",
        "template",
        "template-once",
        sub(
            "adds the last section only after the call is confirmed",
            "adds the last section before the call",
        ),
    ),
    (
        "M44 an lstat error other than absent is ignored",
        "script",
        "O2",
        sub(
            '            except OSError as e:\n                state, note = "partial", f"unreadable: {e}"\n            else:',
            "            except OSError:\n                pass\n            else:",
        ),
    ),
    (
        "M45 a vanished run-once file is not noticed",
        "script",
        "O2",
        sub('if seen.get(p["phase"], "pending") != "pending":', "if False:"),
    ),
    (
        "M46 only a complete phase counts as vanished",
        "script",
        "O2",
        sub(
            'if seen.get(p["phase"], "pending") != "pending":',
            'if seen.get(p["phase"]) == "complete":',
        ),
    ),
    (
        "M47 vanished evidence is also kept after a plan change",
        "script",
        "O2",
        sub("rebuild(plan, base, None if changed else old)", "rebuild(plan, base, old)"),
    ),
    (
        "M49 duplicate section names count as two",
        "script",
        "O1",
        sub(
            'len({x.strip() for x in r["sections"].split(";")}) < 2',
            'len([x.strip() for x in r["sections"].split(";")]) < 2',
        ),
    ),
    (
        "M50 the replay header is read without case",
        "script",
        "O1",
        sub("if got not in heads:", "if [g.lower() for g in got] not in heads:"),
    ),
    (
        "M51 the blocked reminder loses its words",
        "script",
        "O3",
        sub('why += "; run-once phase, its effect may have happened"', 'why += "; run-once phase"'),
    ),
    (
        "S01 script comment drops references/",
        "script",
        "doc-attrib",
        sub(
            "# adapted from references/openrig/docs/reference/rig-spec.md:519",
            "# adapted from openrig/docs/reference/rig-spec.md:519",
        ),
    ),
    (
        "D20 stop-confirm row re-runs with the same key",
        "doc",
        "doc-once",
        sub(
            "follows O6; runs nothing before the answer",
            "follows O6; re-runs the phase with the same key",
        ),
    ),
    (
        "D21 O1 says the hash covers every column",
        "doc",
        "doc-once",
        sub(
            "`plan-hash` covers the five plan columns only",
            "`plan-hash` covers all the plan columns",
        ),
    ),
    ("D22 O7 row removed", "doc", "doc-once", drop_line(r"^\| O7 \|.*\n")),
    (
        "D23 O7 allows the retry",
        "doc",
        "doc-once",
        sub("never retried automatically and never re-asked", "retried once and re-asked once"),
    ),
    (
        "D24 rebuild note dropped from section 4",
        "doc",
        "doc-once",
        sub(
            " `rebuild` prints `LEDGER` and `NEXT` only, so there is no `HALF-DONE` line and no `ACTION`:"
            " its `NEXT` line never starts a `once` phase (O7); run `resume` first.",
            "",
        ),
    ),
    (
        "D25 the closing line claims every rule is checked",
        "doc",
        "doc-once",
        sub("nothing checks that they are followed", "each is checked"),
    ),
    (
        "D26 header says never replayed",
        "doc",
        "doc-once",
        sub(
            "declared and, when half done, stopped on resume",
            "declared and never replayed on resume",
        ),
    ),
    (
        "D27 O2 loses the vanished exception",
        "doc",
        "doc-once",
        sub(
            ", unless the previous ledger recorded that phase as partial or complete: then",
            ". If the previous ledger recorded that phase as partial or complete:",
        ),
    ),
    (
        "D28 R7 loses the vanished cross-reference",
        "doc",
        "doc-once",
        sub(" (O2 covers a run-once file that vanished)", ""),
    ),
    (
        "D29 R9 loses the O3 cross-reference",
        "doc",
        "doc-once",
        sub(
            ", or O3 applies: a half-done run-once resume row stops as `stop-confirm` first, and the question then also says the ledger was unreadable",
            "",
        ),
    ),
    (
        "D30 stop-confirm row loses the unreadable-ledger question",
        "doc",
        "doc-once",
        sub(
            ", and says so when `LEDGER` is unreadable, because a blocker elsewhere may have been lost",
            "",
        ),
    ),
    (
        "D31 no-evidence limit dropped",
        "doc",
        "doc-once",
        drop_line(r"^- The vanished-file stop reads the previous ledger.*\n"),
    ),
    (
        "D32 edited-row limit dropped",
        "doc",
        "doc-once",
        drop_line(r"^- Changing a `once` row's path or marker.*\n"),
    ),
    (
        "D33 O3 again says a complete phase is not run again",
        "doc",
        "doc-once",
        sub(" while its file is there (O2 covers a vanished file)", ""),
    ),
    (
        "K05 Error policy exception removed",
        "skill",
        "skill-once",
        sub(
            ", except that a `once` phase is never retried automatically: it stops and asks (`references/state-ledger.md` section 3a, rule O7)",
            "",
        ),
    ),
    (
        "K06 Delegation contract exception removed",
        "skill",
        "skill-once",
        sub("; a `once` phase is never re-asked", ""),
    ),
    (
        "K07 References bullet promises no repeat",
        "skill",
        "skill-once",
        sub(
            "- Run-once phases: a resume stops and asks about a half-done send, publish or record write (the ledger reads files only; an idempotency key accepted by the connector is the real fix)",
            "- Run-once phases, so a resume never repeats a send, a publish or a record write",
        ),
    ),
    (
        "T04 template drops the connector key clause",
        "template",
        "template-once",
        sub("passes the key to the connector when the connector takes one, ", ""),
    ),
    (
        "T05 template drops the not-the-clock clause",
        "template",
        "template-once",
        sub(", never from the time of the attempt", ""),
    ),
    (
        "T06 template drops the intent content",
        "template",
        "template-once",
        sub("(what it will do, to whom, and a key", "(a key"),
    ),
    (
        "T07 Error handling bullet loses the exception",
        "template",
        "template-once",
        sub(
            ", except a phase marked `once` (never retried: run `resume` and follow rule O6 of `state-ledger.md` section 3a)",
            "",
        ),
    ),
    (
        "T08 Workflow error row loses the exception",
        "template",
        "template-once",
        sub(
            "For a phase marked `once`, do not run it again: run `resume` and follow rule O6 of `state-ledger.md` section 3a. Otherwise exclude it",
            "Exclude it",
        ),
    ),
    (
        "T09 team error row loses the exception",
        "template",
        "template-once",
        sub(
            "For a phase marked `once`, do not instruct it again or launch a replacement: run `resume` and follow rule O6 of `state-ledger.md` section 3a. Otherwise check status",
            "Check status",
        ),
    ),
    (
        "T10 template drops the retry-once exclusion",
        "template",
        "template-once",
        sub(
            "A `once` phase is also outside the retry-once rule of the Error handling section and outside the single re-ask of the Delegating block below: ",
            "",
        ),
    ),
    (
        "T11 the exclusion is written into the pasted block",
        "template",
        "template-once",
        sub(
            "Re-ask once: tell the worker which row it broke",
            "Re-ask once (a `once` phase too): tell the worker which row it broke",
        ),
    ),
    (
        "M52 the ledger parser also accepts a replay column",
        "script",
        "O1",
        sub("rows = table(text, COLS)", 'rows = table(text, COLS, "replay")'),
    ),
    (
        "D34 the resume output list loses HALF-DONE",
        "doc",
        "doc-once",
        sub(", a `HALF-DONE` line when the plan has a `once` phase,", ","),
    ),
    (
        "D35 the mark-once list drops moving money",
        "doc",
        "doc-once",
        sub(", or moves money.", "."),
    ),
    (
        "D36 the mark-once list drops visible uploads",
        "doc",
        "doc-once",
        sub("uploads a file where others can see it, or moves money", "or moves money"),
    ),
    (
        "D37 the stable-key sentence is dropped",
        "doc",
        "doc-once",
        sub(
            " A write that a stable key makes harmless to repeat may also be `safe`, but only when the brief names that key; nothing checks it.",
            "",
        ),
    ),
    (
        "D38 the cannot-see-an-effect sentence is dropped",
        "doc",
        "doc-once",
        sub(" The ledger cannot see an effect and does not try;", ""),
    ),
    (
        "R16 Step 0 resumes a once stage with resumeFromRunId",
        "skill",
        "skill-once",
        sub(
            ", except for a `once` stage that did not return a result (`references/state-ledger.md` section 3a, rule O7)",
            "",
        ),
    ),
    (
        "K08 Step 0 marker list drops publishes",
        "skill",
        "skill-once",
        sub(
            "A phase that sends, publishes, uploads or writes",
            "A phase that sends, uploads or writes",
        ),
    ),
    (
        "R01 Mode A table loses the once exception for a failed workflow",
        "template",
        "template-once",
        sub(
            f" A stage marked `once` is never fixed and resumed this way: run `resume` and follow {O6}.",
            "",
        ),
    ),
    (
        "R02 the cause-cleared row lets a once stage resume",
        "template",
        "template-once",
        sub(f", except a stage marked `once`: run `resume` and follow {O6}", ""),
    ),
    (
        "R03 the error-flow scenario instructs a once teammate again",
        "template",
        "template-once",
        sub(
            f" (For a teammate whose phase is marked `once`, do neither: run `resume` and follow {O6}.)",
            "",
        ),
    ),
    (
        "R04 Step 0 resumes an interrupted once stage",
        "template",
        "template-once",
        sub(
            f" A stage marked `once` that failed or was interrupted is not resumed this way: run `resume` and follow {O6}.",
            "",
        ),
    ),
    (
        "R05 the freeze check re-runs a once stage to refresh it",
        "template",
        "template-once",
        sub(
            f", except a stage marked `once`, which is never re-run to refresh it: tell the user its effect used the earlier content ({O6})",
            "",
        ),
    ),
    (
        "R06 a new error row instructs a worker again with no exception",
        "template",
        "template-once",
        sub(
            "| The data conflicts |",
            "| A teammate returns nothing | Instruct it again. |\n| The data conflicts |",
        ),
    ),
    (
        "R07 the Workflow row says a once stage may be fixed and resumed",
        "template",
        "template-once",
        sub(
            "A stage marked `once` is never fixed and resumed this way",
            "A stage marked `once` may be fixed and resumed this way",
        ),
    ),
    (
        "R08 doc says a once stage is resumed with resumeFromRunId",
        "doc",
        "doc-once",
        sub(
            " A `once` stage that did not return a result is not resumed with `resumeFromRunId`: its call may have gone out, so `resume` and O6 decide (rule O7).",
            "",
        ),
    ),
    (
        "R09 SKILL.md checklist re-asks every phase",
        "skill",
        "skill-once",
        sub(" (a `once` phase is never re-asked)", ""),
    ),
    (
        "R10 execution modes keep the schema retry for a once phase",
        "refs:execution-modes",
        "refs-once",
        sub(
            f" For a phase marked `once`, leave `opts.schema` off: whether that retry repeats the agent's outside call is not known, and rule O7 of `state-ledger.md` section 3a forbids a retry of a `once` phase.{ATT}",
            "",
        ),
    ),
    (
        "R11 execution modes resume a once stage with resumeFromRunId",
        "refs:execution-modes",
        "refs-once",
        sub(
            f" A stage marked `once` that did not return a result is not resumed this way, because its call may have gone out: run `resume` and follow {O6}.",
            "",
        ),
    ),
    (
        "R12 the produce-verify loop re-runs a once producer",
        "refs:team-patterns",
        "refs-once",
        sub(
            f" A phase marked `once` is not part of this loop: verify before it runs, and after a failure run `resume` and follow {O6}.{ATT}",
            "",
        ),
    ),
    (
        "R13 the supervisor redistributes a failed once task",
        "refs:team-patterns",
        "refs-once",
        sub(
            f" A phase marked `once` is never redistributed after a failure: run `resume` and follow {O6}.",
            "",
        ),
    ),
    (
        "R14 the Workflow recipes call a script with a once stage again",
        "refs:workflow-recipes",
        "refs-once",
        sub(
            f" A new call without `resumeFromRunId` runs every stage again, so a script with a stage marked `once` is not called again after that stage started: run `resume` and follow {O6}.{ATT}",
            "",
        ),
    ),
    (
        "J30 doc O7 tells the orchestrator to launch the worker once more",
        "doc",
        "doc-once",
        sub(
            "do not launch or ask that worker again; run `resume` and follow O6",
            "launch that worker once more; run `resume` and follow O6",
        ),
    ),
    (
        "J37 doc O7 no longer reaches the step that checks reports",
        "doc",
        "doc-once",
        sub(" and into the step that checks reports", ""),
    ),
    (
        "J40 template paragraph asks the worker once more",
        "template",
        "template-once",
        sub(
            "do not launch or ask that worker again; run `state_ledger.py resume`",
            "ask that worker once more; run `state_ledger.py resume`",
        ),
    ),
    (
        "J34 doc section 8 drops the deleted-ledger limit",
        "doc",
        "doc-once",
        sub(
            "or when the ledger was deleted or unreadable, there is no evidence",
            "there is no evidence",
        ),
    ),
    (
        "J04 the vanished note always says complete",
        "script",
        "O2",
        sub("the ledger had it {seen[p['phase']]}", "the ledger had it complete"),
    ),
    (
        "J09 the not-a-file read joins the working directory",
        "script",
        "O2",
        sub('os.lstat(base / p["path"])', 'os.lstat(Path(p["path"]))'),
    ),
    (
        "J12 the distinct section set ignores case",
        "script",
        "O1",
        sub(
            'len({x.strip() for x in r["sections"].split(";")}) < 2',
            'len({x.strip().lower() for x in r["sections"].split(";")}) < 2',
        ),
    ),
    (
        "J12b the no-table reason does not name replay",
        "script",
        "O1",
        sub('" | ".join((*PLAN_COLS, "[replay]"))', '" | ".join(PLAN_COLS)'),
    ),
    (
        "R17 execution modes lose their attribution line",
        "refs:execution-modes",
        "refs-once",
        sub(ATT, ""),
    ),
    (
        "R18 team patterns lose their attribution line",
        "refs:team-patterns",
        "refs-once",
        sub(ATT, ""),
    ),
    (
        "R19 workflow recipes lose their attribution line",
        "refs:workflow-recipes",
        "refs-once",
        sub(ATT, ""),
    ),
    (
        "R20 R6 resumes a half-done once row",
        "doc",
        "doc-once",
        sub("; a half-done `once` row is the exception and stops (O3)", ""),
    ),
    (
        "R15 O2 says a delete alone can restart the phase",
        "doc",
        "doc-once",
        sub(
            "a delete of the file alone cannot make the phase start again",
            "a delete makes the phase start again",
        ),
    ),
    (
        "B01 section 8 drops the live-connector test warning",
        "doc",
        "doc-once",
        sub(
            "- A test or dry run of a harness whose agent calls a live sending connector (SMS, email, chat post, page publish, CRM write) sends for real, and a fresh test run starts with no ledger. Test such a harness against a stub or sandbox connector with synthetic recipients; the ledger does not see test runs.\n",
            "",
        ),
    ),
    (
        "B02 team examples reassign a once task",
        "refs:team-examples",
        "refs-once",
        sub(
            f" A task of a phase marked `once` is not reassigned: run `resume` and follow {O6}.", ""
        ),
    ),
    (
        "B03 Mode B step 3 sends revisions to a once teammate",
        "template",
        "template-once",
        sub(
            f" Do not send a revision request to a teammate whose phase is marked `once` after its effect has gone out: {O6}.",
            "",
        ),
    ),
    (
        "B04 Workflow cache clause dropped",
        "refs:execution-modes",
        "refs-once",
        sub(
            " A `once` stage that already returned a result is cached only while its prompt is unchanged",
            " A stage is cached",
        ),
    ),
    (
        "B05 resume row re-runs a once phase",
        "doc",
        "doc-once",
        sub("re-runs `PHASE` with `PATH`", "re-runs `PHASE`, even a `once` phase, with `PATH`"),
    ),
    (
        "B06 resume note dropped",
        "doc",
        "doc-once",
        sub("`resume` never names a half-done `once` phase; that case is `stop-confirm`.", ""),
    ),
    (
        "B07 template row launches once more",
        "template",
        "template-once",
        sub(
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |",
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |"
            + "\n| Slow | Launch it once more with the same brief. |",
        ),
    ),
    (
        "B08 template row reassigns the task",
        "template",
        "template-once",
        sub(
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |",
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |"
            + "\n| Slow | Reassign the task to another teammate with TaskUpdate. |",
        ),
    ),
    (
        "B09 template row says try again",
        "template",
        "template-once",
        sub(
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |",
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |"
            + "\n| Slow | Try again. |",
        ),
    ),
    (
        "B10 template row retries the call",
        "template",
        "template-once",
        sub(
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |",
            "| More than half of the teammates failed | Tell the user and confirm whether to continue. |"
            + "\n| Slow | Retry the call once. |",
        ),
    ),
    (
        "B11 unprotected row directly before a protected row",
        "template",
        "template-once",
        sub(
            "| A teammate does not respond or has stopped |",
            "| Slow | Instruct it again. |\n| A teammate does not respond or has stopped |",
        ),
    ),
    (
        "B12 execution modes: failed call is called again",
        "refs:execution-modes",
        "refs-once",
        sub(
            "- It runs in the background and sends",
            "- If a call fails, call it again.\n- It runs in the background and sends",
        ),
    ),
    (
        "B13 team patterns: failed worker is relaunched",
        "refs:team-patterns",
        "refs-once",
        sub(
            "**Caution:** If you split",
            "A failed worker is relaunched under a new name.\n\n**Caution:** If you split",
        ),
    ),
    (
        "B14 pasted Delegating block edited",
        "template",
        "template-once",
        sub("Re-ask once", "Re-ask twice"),
    ),
    (
        "B15 SKILL.md gains an unprotected retry sentence",
        "skill",
        "skill-once",
        sub("- **Error policy**", "- **Retry**: try again after any failure.\n- **Error policy**"),
    ),
    (
        "B16 execution modes cites O6 for the schema retry again",
        "refs:execution-modes",
        "refs-once",
        sub(
            "and rule O7 of `state-ledger.md` section 3a forbids a retry of a `once` phase.",
            "and rule O6 of `state-ledger.md` section 3a forbids a retry of a `once` phase (rule O7).",
        ),
    ),
]


def real() -> tuple[str, str, str]:
    return (
        DOC.read_text(encoding="utf-8"),
        SKILL.read_text(encoding="utf-8"),
        TEMPLATE.read_text(encoding="utf-8"),
    )


def test_real_files_pass_every_check() -> None:
    doc, skill, template = real()
    assert problems(SCRIPT, doc, skill, template) == []


def test_mutation_table_is_big_enough() -> None:
    assert len(MUTANTS) >= 40 and len({m[0].split()[0] for m in MUTANTS}) == len(MUTANTS)


@pytest.mark.parametrize("name,target,tag,edit", MUTANTS, ids=[m[0].split()[0] for m in MUTANTS])
def test_mutant_is_killed(
    tmp_path: Path, name: str, target: str, tag: str, edit: Callable[[str], str]
) -> None:
    doc, skill, template = real()
    refs = real_refs()
    script = SCRIPT.read_text(encoding="utf-8")
    if target == "script":
        script = edit(script)
    elif target == "doc":
        doc = edit(doc)
    elif target == "skill":
        skill = edit(skill)
    elif target.startswith("refs:"):
        refs = {n: edit(x) if n == target[5:] else x for n, x in refs.items()}
    else:
        template = edit(template)
    mutant = tmp_path / "state_ledger_mutant.py"
    mutant.write_text(script, encoding="utf-8")
    found = problems(mutant, doc, skill, template, refs)
    assert any(p.startswith(tag + ":") for p in found), (name, found)


def test_cli_exit_codes_and_output(tmp_path: Path) -> None:
    (tmp_path / "_workspace").mkdir()
    (tmp_path / "plan.md").write_text(plan6(), encoding="utf-8")

    def cli(cmd: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), cmd, "plan.md"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    (tmp_path / "_workspace/01_a.md").write_text(FULL[1], encoding="utf-8")
    (tmp_path / "_workspace/02_b.md").write_text(INTENT, encoding="utf-8")
    run = cli("resume")
    assert run.returncode == 3 and "ACTION: stop-confirm\nPHASE: 2\n" in run.stdout, run.stdout
    assert "HALF-DONE: 2\nSUSPECT: -\n" in run.stdout and "Traceback" not in run.stderr
    assert cli("rebuild").returncode == 0
    (tmp_path / "plan.md").write_text(plan6().replace("| once |", "| Once |", 1), encoding="utf-8")
    run = cli("resume")
    assert run.returncode == 2 and "ACTION: stop-no-plan" in run.stdout and "replay" in run.stdout


def test_openrig_prose_is_not_copied() -> None:
    """No run of eight words in the changed prose appears in the files it was adapted from."""
    src = REPO / "references/openrig"
    if not (src / "docs").is_dir():
        pytest.skip("references/openrig is not checked out")
    words = re.compile(r"[a-z0-9']+")

    def runs(text: str) -> set[tuple[str, ...]]:
        w = words.findall(text.lower())
        return {tuple(w[i : i + 8]) for i in range(len(w) - 7)}

    theirs: set[tuple[str, ...]] = set()
    for p in itertools.chain((src / "docs").rglob("*.md"), (src / "packages").rglob("SKILL.md")):
        theirs |= runs(p.read_text(encoding="utf-8", errors="replace"))
    doc, skill, template = real()
    new_doc = doc[doc.index("## 3a.") : doc.index("## 5.")] + doc[doc.index("## 8.") :]
    para = next(x for x in template.splitlines() if x.startswith("A phase marked `once`"))
    step0 = next(x for x in skill.splitlines() if x.startswith("- **Step 0 context check**"))
    step0 += " ".join(
        x for x in skill.splitlines() if x.startswith(("- **Error policy**", "- Run-once phases"))
    )
    for name, text in (
        ("3a", new_doc),
        ("template", para),
        ("step0", step0),
        (
            "clauses",
            " ".join((*TEMPLATE_CLAUSES, *(c for cs in REFS_CLAUSES.values() for c in cs))),
        ),
        ("script", SCRIPT.read_text(encoding="utf-8")),
    ):
        # attribution paths contain the source's own words; the check is on prose
        text = re.sub(r"references/openrig/\S+|openrig/\S+", "", text)
        assert not (runs(text) & theirs), name


def test_unsearchable_directory_without_mocks(tmp_path: Path) -> None:
    """A real permission error, no mock: a run-once file in a directory that cannot be searched.
    Python 3.14 swallows the error in Path.is_file(), so the script must not rely on it. Root is run
    through setpriv without dac_override; the test is skipped where the error cannot be produced."""
    cmd: list[str] = []
    if os.geteuid() == 0:
        setpriv = shutil.which("setpriv")
        if setpriv is None:
            pytest.skip("root and no setpriv to drop dac_override")
        cmd = [setpriv, "--bounding-set=-dac_override,-dac_read_search"]
    (tmp_path / "_workspace/priv").mkdir(parents=True)
    (tmp_path / "_workspace/01_a.md").write_text("## A\n", encoding="utf-8")
    target = tmp_path / "_workspace/priv/02_b.md"
    target.write_text(FULL[2], encoding="utf-8")
    plan = plan6(TWO).replace("_workspace/02_b.md", "_workspace/priv/02_b.md")
    (tmp_path / "plan.md").write_text(plan, encoding="utf-8")
    probe = "import os, sys; os.stat(sys.argv[1])"
    locked = tmp_path / "_workspace/priv"
    try:
        locked.chmod(0o000)
        seen = subprocess.run(
            [*cmd, sys.executable, "-c", probe, str(target)], capture_output=True, check=False
        )
        if seen.returncode == 0:
            pytest.skip("this process can still search a mode 000 directory")
        run = subprocess.run(
            [*cmd, sys.executable, str(SCRIPT), "resume", "plan.md"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        locked.chmod(0o755)
    assert run.returncode == 3 and "ACTION: stop-confirm" in run.stdout, (run.stdout, run.stderr)
    assert "unreadable" in run.stdout and "Traceback" not in run.stderr, run.stdout
