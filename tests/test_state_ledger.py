"""Proof for the state ledger (C11): scripts/state_ledger.py and references/state-ledger.md.

The rules R1-R9 in the doc each have a behaviour check below; problems() runs every check against a
script, a doc and a SKILL.md text, so the same function proves the real files (no problems) and
kills each mutant in MUTANTS (at least one problem, carrying the expected tag).
Sources: see the attribution lines in references/state-ledger.md (Apache-2.0 and MIT).
"""

from __future__ import annotations

import contextlib
import functools
import importlib.util
import io
import itertools
import os
import re
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

COLS = ("phase", "producer", "consumer", "path", "sections", "completion", "note")
HEAD = "| " + " | ".join(COLS) + " |"
PLAN_HEAD = "| " + " | ".join(COLS[:5]) + " |"
SEP = "|---|---|---|---|---|---|---|"
PLAN_SEP = "|---|---|---|---|---|"
ACTIONS = {
    "start": 0,
    "resume": 0,
    "stop-done": 3,
    "stop-blocked": 3,
    "stop-unreadable": 3,
    "stop-no-plan": 2,
}
HL = "plan-hash: 0123456789ab\n"
RULES = {  # one phrase per rule that must stay in the doc's rule table
    "R1": "exactly seven cells",
    "R2": "at least two rows",
    "R3": "outside code fences",
    "R4": "Files win",
    "R5": "clears when the file is complete",
    "R6": "first row that is not complete",
    "R7": "writes only",
    "R8": "listed as suspect",
    "R9": "the decision is `stop-unreadable`",
    "R10": "LEDGER: unwritable",
}
PINS = {  # prose that tells the orchestrator what to do; nothing but the phrase can bind it
    "same `plan-hash`": 1,
    "retry nothing": 1,
    "retries nothing": 1,
    "takes priority over R6": 1,
    "a complete phase is not run again": 1,
    "**after every phase**": 1,
    "start from phase 1 and say so": 1,
    "complete means the headings are present, not that the content is right or current": 2,
    "if the session that resumes does not have the plugin installed, copy `state_ledger.py` into the generated harness": 1,
    "asks the user, and on a yes runs `resume` again": 1,
    "so ask the user, then run `resume` again, which reads the rebuilt ledger": 1,
    "the ledger cannot be rewritten (a read-only `_workspace`): tell the user and stop": 1,
    "a plan edit clears every blocker, so tell the user which phases were blocked": 1,
    "in a session that continues, run `resume` before any `rebuild`": 1,
}
PLAN = f"""# Orchestrator

## Handoff files

{PLAN_HEAD}
{PLAN_SEP}
| 1 | a | b | _workspace/01_a.md | Findings; Gaps |
| 2 | b | c | _workspace/02_b.md | Design |
| 3 | c | d | _workspace/03_c.md | Verdict; Reasons |
| 4 | d | e | _workspace/04_d.md | - |
"""
FULL = {
    1: "## Findings\nx\n\n## Gaps\ny\n",
    2: "## Design\nz\n",
    3: "## Verdict\nv\n\n## Reasons\nr\n",
    4: "free text\n",
}
OBSERVED: set[tuple[str, int]] = set()
COUNTER = itertools.count()


def load(path: Path, name: str) -> ModuleType:
    """Import the script as module `name` without leaving bytecode, so a mutant is never stale."""
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


class World:
    """A scratch project: plan.md plus a _workspace/, driven through the script's main()."""

    def __init__(self, mod: ModuleType, root: Path, plan: str = PLAN) -> None:
        self.mod, self.root = mod, root
        (root / "_workspace").mkdir()
        (root / "plan.md").write_text(plan, encoding="utf-8")

    def put(self, phase: int, text: str) -> Path:
        path = self.root / f"_workspace/0{phase}_{'abcd'[phase - 1]}.md"
        path.write_text(text, encoding="utf-8")
        return path

    @property
    def ledger(self) -> Path:
        return self.root / "_workspace/00_state.md"

    def run(self, cmd: str = "resume", plan: str = "plan.md") -> tuple[int, dict[str, list[str]]]:
        buf = io.StringIO()
        with contextlib.chdir(self.root), contextlib.redirect_stdout(buf):
            code = self.mod.main([cmd, plan])
        out: dict[str, list[str]] = {}
        for line in buf.getvalue().splitlines():
            key, _, val = line.partition(": ")
            out.setdefault(key, []).append(val)
        if "ACTION" in out:
            OBSERVED.add((out["ACTION"][0], code))
        return code, out

    def rows(self) -> dict[str, dict[str, str]]:
        parsed, _ = self.mod.parse_ledger(self.ledger.read_text(encoding="utf-8"))
        return {r["phase"]: r for r in parsed}

    def state(self, phase: int) -> tuple[str, str]:
        r = self.rows()[str(phase)]
        return r["completion"], r["note"]


@contextlib.contextmanager
def patched(attr: str, fn: Callable[..., object]) -> Iterator[None]:
    """Replace a pathlib.Path method for the block; the suite runs as root, so chmod cannot fail."""
    real_fn = getattr(Path, attr)
    setattr(Path, attr, fn)
    try:
        yield
    finally:
        setattr(Path, attr, real_fn)


def edit_ledger(w: World, phase: int, completion: str, note: str) -> None:
    out = []
    for line in w.ledger.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip("|").split("|")]
        if c[0] == str(phase) and len(c) == 7:
            c[5], c[6] = completion, note
            line = "| " + " | ".join(c) + " |"
        out.append(line)
    w.ledger.write_text("\n".join(out) + "\n", encoding="utf-8")


def r1_shape(mod: ModuleType, tmp: Path) -> None:
    assert tuple(mod.COLS) == COLS and tuple(mod.PLAN_COLS) == COLS[:5]
    w = World(mod, tmp)
    w.put(1, FULL[1])
    w.run("rebuild")
    text = w.ledger.read_text(encoding="utf-8")
    assert HEAD in text.splitlines() and SEP in text.splitlines()
    assert re.search(r"^plan-hash: [0-9a-f]{12}$", text, re.MULTILINE)
    good, digest = mod.parse_ledger(text)
    assert mod.parse_ledger("".join(f"{x}  \n" for x in text.splitlines())) == (good, digest)
    assert len(good) == 4 and all(list(r) == list(COLS) for r in good)
    row = "| 1 | a | b | p | s | complete | - |"
    blocked = "| 1 | a | b | p | s | blocked | stuck |"
    top = f"{HL}{HEAD}\n{SEP}\n"
    for bad in (
        f"{top}| 1 | a | b | p | s | done | - |\n",  # state outside the four
        f"{top}| 1 | a | b | p | s | blocked | - |\n",  # blocked without a reason
        f"{top}{row}\n{row}\n",  # duplicate phase id
        f"{top}| 1 | a | b | p | s | complete |\n",  # six cells
        f"{top}{row} x |\n",  # eight cells
        f"{top}| 1 | a | b | p | s | complete |  |\n",  # empty cell
        HL + "| " + " | ".join(COLS[:6]) + f" |\n{SEP}\n{row}\n",  # a column missing
        f"{HL}{HEAD}\n{row}\n",  # no separator row
        f"{HEAD}\n{SEP}\n{row}\n",  # no plan-hash line
        "nothing here\n",
    ):
        try:
            mod.parse_ledger(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted a ledger that breaks R1: {bad!r}")
    assert mod.parse_ledger(f"{top}{blocked}\n")[0][0]["note"] == "stuck"


def r2_plan(mod: ModuleType, tmp: Path) -> None:
    def refuse(name: str, plan: str) -> None:
        d = tmp / name
        d.mkdir()
        w = World(mod, d, plan)
        code, out = w.run()
        assert code == 2 and out["ACTION"] == ["stop-no-plan"], (name, code, out)
        assert not w.ledger.exists(), name

    ok_rows = PLAN.split("\n| 1 | ")[1]
    head = PLAN.split("| 1 | ")[0]
    one = f"{head}| 1 | {ok_rows.splitlines()[0]}\n"
    refuse("none", "# no table here\n")
    refuse("one", one)
    refuse("dup", f"{one}| 1 | x | y | _workspace/z.md | - |\n")
    paths = ["/etc/passwd", "//srv/share/x", "../x.md", "a/../b.md", "a\\b.md"]
    paths += ["C:/Windows/win.ini", "c:x.md", "\\\\srv\\share\\x"]
    for n, path in enumerate(paths):
        refuse(f"path{n}", f"{one}| 2 | x | y | {path} | - |\n")
    for n, sections in enumerate((";", "a;;b", "a;", " ; b")):
        refuse(f"sect{n}", f"{one}| 2 | x | y | _workspace/z.md | {sections} |\n")
    refuse("empty", f"{one}| 2 | x |  | _workspace/z.md | - |\n")
    refuse("short", f"{one}| 2 | x | y | _workspace/z.md |\n")
    refuse("fenced", "```md\n" + PLAN + "```\n")
    refuse("nosep", PLAN.replace(PLAN_SEP + "\n", ""))
    refuse("extra", PLAN.replace("| sections |", "| sections | more |"))
    padded = "".join(f"{x}  \n" for x in PLAN.splitlines())
    aligned = PLAN.replace(PLAN_SEP, "| :--- | :---: | ---: | --- | --- |")
    ticks = PLAN.replace("| _workspace/01_a.md |", "| `_workspace/01_a.md` |")
    two = f"{one}| 2 | x | y | _workspace/02_b.md | - |\n"  # the smallest plan that is allowed
    for name, plan in (
        ("two", two),
        ("good", PLAN),
        ("padded", padded),
        ("aligned", aligned),
        ("ticks", ticks),
    ):
        d = tmp / name
        d.mkdir()
        code, out = World(mod, d, plan).run()
        assert code == 0 and out["ACTION"] == ["start"], name
        assert out["PATH"] == ["_workspace/01_a.md"], name
    contained(mod, tmp)
    extra_r2(mod, tmp)


def extra_r2(mod: ModuleType, tmp: Path) -> None:
    """A path that cannot be resolved stops the run; a project behind a symlinked parent works."""
    d = tmp / "loop"
    d.mkdir()
    w = World(mod, d)
    real_resolve = Path.resolve

    def resolve(self: Path, *a: object, **k: object) -> Path:
        if self.name == "01_a.md":
            raise RuntimeError("Symlink loop")
        return real_resolve(self, *a, **k)  # type: ignore[arg-type]

    with patched("resolve", resolve):
        code, out = w.run()
    assert code == 2 and out["ACTION"] == ["stop-no-plan"], out
    assert "outside the project" in out["REASON"][0] and not w.ledger.exists()
    (d / "_workspace/01_a.md").symlink_to("01_a.md")  # a real loop: refused, or just not a file
    code, out = w.run()
    assert (code, out["ACTION"]) in ((2, ["stop-no-plan"]), (0, ["start"])), out
    d = tmp / "viaparent"
    (d / "real").mkdir(parents=True)
    (d / "link").symlink_to(d / "real")
    w = World(mod, d / "real")
    argv = ["resume", str(w.root / "plan.md"), "--base", str(d / "link")]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mod.main(argv)
    assert code == 0 and "ACTION: start" in buf.getvalue(), buf.getvalue()


def contained(mod: ModuleType, tmp: Path) -> None:
    outside = tmp / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(FULL[1], encoding="utf-8")
    for name in ("link_out", "link_in", "ledger_out", "ledger_in"):
        (tmp / name).mkdir()
    w = World(mod, tmp / "link_out")  # a phase file that is a symlink out of the project
    (w.root / "_workspace/01_a.md").symlink_to(outside / "secret.md")
    code, out = w.run()
    assert code == 2 and out["ACTION"] == ["stop-no-plan"], out
    assert "outside the project" in out["REASON"][0] and not w.ledger.exists()
    w = World(mod, tmp / "link_in")  # one that stays inside is followed
    (w.root / "_workspace/real.md").write_text(FULL[1], encoding="utf-8")
    (w.root / "_workspace/01_a.md").symlink_to("real.md")
    assert w.run()[0] == 0 and w.state(1) == ("complete", "-")
    w = World(mod, tmp / "ledger_out")  # a dangling ledger symlink must not create its target
    w.ledger.symlink_to(outside / "target.md")
    code, out = w.run()
    assert code == 2 and not (outside / "target.md").exists(), out
    w = World(mod, tmp / "ledger_in")  # an inside one is replaced, not written through
    keep = w.root / "_workspace/keep.md"
    keep.write_text("keep", encoding="utf-8")
    w.ledger.symlink_to("keep.md")
    w.run()
    assert not w.ledger.is_symlink() and keep.read_text(encoding="utf-8") == "keep"


def r3_completion(mod: ModuleType, tmp: Path) -> None:
    cases: list[tuple[int, str | None, str, str]] = [
        (1, None, "pending", "-"),
        (1, "", "partial", "empty file"),
        (1, "  \n\n", "partial", "empty file"),
        (1, "## Findings\nx\n", "partial", "missing: Gaps"),
        (1, "## Gaps\n", "partial", "missing: Findings"),
        (1, FULL[1], "complete", "-"),
        (1, "# Findings\n###### Gaps ##\n", "complete", "-"),
        (1, "```md\n## Findings\n## Gaps\n```\n", "partial", "missing: Findings, Gaps"),
        (
            1,
            "````md\n```x\n## Findings\n```\n## Gaps\n````\n",
            "partial",
            "missing: Findings, Gaps",
        ),
        (1, "~~~\n## Findings\n~~~\n## Gaps\n", "partial", "missing: Findings"),
        (1, "```md\n## Findings\n```  \n## Gaps\n", "partial", "missing: Findings"),
        (1, "## Findings extra\n## Gaps\n", "partial", "missing: Findings"),
        (1, "```\n## Findings\n~~~\n## Gaps\n", "partial", "missing: Findings, Gaps"),
        (1, "```md\n## Findings\n```x\n## Gaps\n", "partial", "missing: Findings, Gaps"),
        (1, "\ufeff## Findings\n## Gaps\n", "complete", "-"),
        (1, "Findings\nGaps\n", "partial", "missing: Findings, Gaps"),
        (4, None, "pending", "-"),
        (4, "", "partial", "empty file"),
        (4, "anything\n", "complete", "-"),
    ]
    for i, (phase, text, state, note) in enumerate(cases):
        d = tmp / f"c{i}"
        d.mkdir()
        w = World(mod, d)
        if text is not None:
            w.put(phase, text)
        w.run("rebuild")
        assert w.state(phase) == (state, note), (i, text, w.state(phase))
    d = tmp / "dir"
    d.mkdir()
    w = World(mod, d)
    (d / "_workspace/01_a.md").mkdir()
    w.run("rebuild")
    assert w.state(1) == ("pending", "-")
    d = tmp / "bytes"
    d.mkdir()
    w = World(mod, d)
    (d / "_workspace/01_a.md").write_bytes(b"## Findings\n\xff\xfe\n## Gaps\n")
    w.run("rebuild")
    assert w.state(1) == ("complete", "-")
    d = tmp / "cap"
    d.mkdir()
    w = World(mod, d)
    mod.__dict__["CAP"] = 40
    w.put(1, "## Findings\n## Gaps\n")
    w.run("rebuild")
    assert w.state(1) == ("complete", "-")
    w.put(1, "## Findings\n## Gaps\n" + "x" * 30)
    w.run("rebuild")
    assert w.state(1)[0] == "partial" and w.state(1)[1].startswith("over the 40 byte"), w.state(1)
    redos(str(mod.__file__))
    extra_r3(mod, tmp)


def extra_r3(mod: ModuleType, tmp: Path) -> None:
    """Heading level 7 is no heading, a tab before closing hashes is cut, an unopenable file is partial."""
    for n, (text, want) in enumerate(
        (
            ("####### Findings\n## Gaps\n", ("partial", "missing: Findings")),
            ("## Findings\t##\n## Gaps\t\n", ("complete", "-")),
            ("#Findings\n#Gaps\n", ("partial", "missing: Findings, Gaps")),
        )
    ):
        d = tmp / f"h{n}"
        d.mkdir()
        w = World(mod, d)
        w.put(1, text)
        w.run("rebuild")
        assert w.state(1) == want, (text, w.state(1))
    d = tmp / "noopen"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    real_open = Path.open

    def deny(self: Path, *a: object, **k: object) -> object:
        if self.name == "01_a.md":
            raise PermissionError(13, "Permission denied")
        return real_open(self, *a, **k)  # type: ignore[call-overload]

    with patched("open", deny):  # an uncaught OSError here would be a traceback and exit 1
        code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["resume"], ["1"]), out
    state, note = w.state(1)
    assert state == "partial" and note.startswith("unreadable: ") and "Permission" in note


REDOS = """
import importlib.util, pathlib, sys, tempfile, time
spec = importlib.util.spec_from_file_location("m", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
d, worst = pathlib.Path(tempfile.mkdtemp()), 0.0
for n in (20000, 80000):
    shapes = ["# a" + " " * n + "b", "# " + "#" * n + "x", "`" * n + "x", " " * n + "`", "~" * n]
    shapes += ["#" * n, "# " + " " * n, "|" + " |" * n, "|" + " " * n + "x"]
    for s in shapes:
        f = d / "f.md"
        f.write_text("## Findings\\n" + s + "\\n## Gaps\\n")
        for call in (lambda: m.judge(f, "Findings; Gaps"), lambda: m.table(s + "\\n", m.PLAN_COLS)):
            t = time.perf_counter()
            call()
            worst = max(worst, time.perf_counter() - t)
print(worst)
"""


def redos(script: str) -> None:
    """Adversarial 20k and 80k character lines must be linear; a hang is cut at 6 s."""
    run = subprocess.run(
        [sys.executable, "-c", REDOS, script],
        capture_output=True,
        text=True,
        timeout=6,
        check=False,
    )
    assert run.returncode == 0, run.stderr[-300:]
    assert float(run.stdout.strip()) < 1.0, run.stdout


def r4_files_win(mod: ModuleType, tmp: Path) -> None:
    w = World(mod, tmp)
    w.put(1, FULL[1])
    w.put(2, FULL[2])
    w.run("rebuild")
    assert w.state(2) == ("complete", "-")
    w.root.joinpath("_workspace/02_b.md").unlink()
    edit_ledger(w, 3, "complete", "-")  # the ledger claims a file that is not there
    _, out = w.run()
    assert out["ACTION"] == ["start"] and out["PHASE"] == ["2"], out
    assert out["DRIFT"] == [
        "2: ledger complete, files pending",
        "3: ledger complete, files pending",
    ]
    assert w.state(2) == ("pending", "-") and w.state(3) == ("pending", "-")
    _, out = w.run()  # a second run finds nothing to report
    assert out["DRIFT"] == ["-"] and out["LEDGER"] == ["ok"]
    text = w.ledger.read_text(
        encoding="utf-8"
    )  # the plan changed since: hash differs, phase 9 left
    text = re.sub(r"plan-hash: \w+", "plan-hash: 000000000000", text)
    w.ledger.write_text(
        text + "| 9 | a | b | _workspace/09.md | - | complete | - |\n", encoding="utf-8"
    )
    _, out = w.run()
    assert out["DRIFT"] == [
        "plan changed, so no blocker is carried",
        "9: in the ledger, not in the plan",
    ], out
    assert "9" not in w.rows()
    text = w.ledger.read_text(encoding="utf-8")  # same plan, extra row: not a ledger of this plan
    w.ledger.write_text(
        text + "| 9 | a | b | _workspace/09.md | - | complete | - |\n", encoding="utf-8"
    )
    assert w.run()[1]["LEDGER"][0].startswith("unreadable")


def r5_blocked(mod: ModuleType, tmp: Path) -> None:
    w = World(mod, tmp)
    w.put(1, FULL[1])
    w.run("rebuild")
    edit_ledger(w, 2, "blocked", "auth expired")
    code, out = w.run()
    assert code == 3 and out["ACTION"] == ["stop-blocked"], out
    assert out["PHASE"] == ["2"] and out["REASON"] == ["auth expired"]
    assert "next: 2" in w.ledger.read_text(encoding="utf-8").splitlines()  # blocked is not done
    w.run("rebuild")  # the blocker survives another rebuild
    assert w.state(2) == ("blocked", "auth expired")
    w.put(2, "")  # a partial file does not clear it
    assert w.run()[1]["ACTION"] == ["stop-blocked"] and w.state(2)[0] == "blocked"
    w.put(2, FULL[2])  # a complete file does
    code, out = w.run()
    assert code == 0 and out["ACTION"] == ["start"] and out["PHASE"] == ["3"], out
    assert out["DRIFT"] == ["2: ledger blocked, files complete"], out  # the clearing is visible
    assert w.state(2) == ("complete", "-")
    edit_ledger(w, 3, "blocked", "needs approval")
    w.ledger.unlink()  # no old ledger: the blocker cannot be known
    code, out = w.run()
    assert out["ACTION"] == ["start"] and out["LEDGER"] == ["absent"], out
    assert w.state(3) == ("pending", "-")
    d = tmp / "partial_row"  # only a blocked row is carried: an old partial row is judged afresh
    d.mkdir()
    w3 = World(mod, d)
    w3.put(1, FULL[1])
    w3.put(2, "")
    w3.run("rebuild")
    assert w3.state(2)[0] == "partial"
    code, out = w3.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["resume"], ["2"]), out
    # a blocker never crosses to another plan
    d = tmp / "other"
    d.mkdir()
    w2 = World(mod, d)
    w2.put(1, FULL[1])
    w2.run("rebuild")
    edit_ledger(w2, 2, "blocked", "old task: auth expired")
    (d / "other.md").write_text(PLAN.replace("| Design |", "| Design; Notes |"), encoding="utf-8")
    code, out = w2.run(plan="other.md")
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["2"]), out
    assert out["DRIFT"][0] == "plan changed, so no blocker is carried", out
    assert w2.state(2) == ("pending", "-")


def r6_target(mod: ModuleType, tmp: Path) -> None:
    def at(name: str, files: dict[int, str]) -> tuple[int, dict[str, list[str]], World]:
        d = tmp / name
        d.mkdir()
        w = World(mod, d)
        for phase, text in files.items():
            w.put(phase, text)
        code, out = w.run()
        return code, out, w

    code, out, w = at("none", {})
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["1"])
    assert "next: 1" in w.ledger.read_text(encoding="utf-8").splitlines()
    code, out, w = at("two", {1: FULL[1], 2: FULL[2]})
    assert (code, out["ACTION"], out["PHASE"], out["REASON"]) == (0, ["start"], ["3"], ["-"])
    assert out["PATH"] == ["_workspace/03_c.md"]
    code, out, w = at("part", {1: FULL[1], 2: FULL[2], 3: "## Verdict\nv\n"})
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["resume"], ["3"])
    assert out["PATH"] == ["_workspace/03_c.md"] and out["REASON"] == ["missing: Reasons"]
    code, out, w = at("first", {1: "## Findings\n", 2: FULL[2], 3: FULL[3], 4: FULL[4]})
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["resume"], ["1"])
    code, out, w = at("all", FULL)
    assert (code, out["ACTION"], out["PHASE"], out["PATH"]) == (3, ["stop-done"], ["-"], ["-"])
    assert "next: done" in w.ledger.read_text(encoding="utf-8").splitlines()
    code, out = w.run("rebuild")
    assert code == 0 and out["NEXT"] == ["done"] and out["LEDGER"] == ["ok"]


def r7_readonly(mod: ModuleType, tmp: Path) -> None:
    w = World(mod, tmp)
    w.put(1, FULL[1])
    w.put(2, "## Design\n")
    w.put(4, FULL[4])
    files = [w.root / "plan.md"] + [
        w.root / f"_workspace/0{n}_{'abcd'[n - 1]}.md" for n in (1, 2, 4)
    ]
    for f in files:
        os.utime(f, ns=(10**9, 10**9))
    before = {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in files}
    for n, cmd in enumerate(("rebuild", "resume", "resume")):
        w.run(cmd)
        if n:
            assert w.ledger.stat().st_mtime_ns == 10**9, "unchanged text was written again"
        assert {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in files} == before, cmd
        assert not (w.root / "_workspace/03_c.md").exists()
        assert sorted(p.name for p in (w.root / "_workspace").iterdir()) == sorted(
            ["00_state.md", "01_a.md", "02_b.md", "04_d.md"]
        )
        os.utime(w.ledger, ns=(10**9, 10**9))  # a run that changes nothing leaves it alone
    w.put(3, FULL[3])
    w.run()
    assert w.ledger.stat().st_mtime_ns != 10**9  # a changed text is written
    elsewhere = tmp / "elsewhere"
    elsewhere.mkdir()
    buf = io.StringIO()
    argv = ["resume", str(w.root / "plan.md"), "--base", str(w.root), "--ledger", "x/y/s.md"]
    with contextlib.chdir(elsewhere), contextlib.redirect_stdout(buf):
        assert mod.main(argv) == 3  # every phase is complete by now
    assert (w.root / "x/y/s.md").is_file() and list(elsewhere.iterdir()) == []
    assert "ACTION: stop-done" in buf.getvalue()
    d = tmp / "atomic"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
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
    assert [Path(str(m)).name for m in moved] == [
        "00_state.md"
    ], moved  # one move for the first write, none when unchanged
    assert [p.name for p in (d / "_workspace").iterdir() if p.name.endswith(".tmp")] == []
    extra_r7(mod, tmp)


def extra_r7(mod: ModuleType, tmp: Path) -> None:
    """The temporary file sits next to the ledger and the ledger is world-readable."""
    d = tmp / "same_dir"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    pairs: list[tuple[Path, Path]] = []  # (directory of the temp file, directory of the target)
    real = os.replace

    def spy(src: object, dst: object) -> None:
        pairs.append((Path(str(src)).absolute().parent, Path(str(dst)).absolute().parent))
        real(src, dst)  # type: ignore[arg-type]

    os.replace = spy  # type: ignore[assignment]
    try:
        w.run()
    finally:
        os.replace = real
    assert pairs == [(w.ledger.parent, w.ledger.parent)], pairs
    d = tmp / "synced"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    calls: list[str] = []
    real_sync, real_replace = os.fsync, os.replace

    def sync_spy(fd: int) -> None:
        calls.append("fsync")
        real_sync(fd)

    def replace_spy(src: object, dst: object) -> None:
        calls.append("replace")
        real_replace(src, dst)  # type: ignore[arg-type]

    os.fsync, os.replace = sync_spy, replace_spy  # type: ignore[assignment]
    try:
        w.run()
    finally:
        os.fsync, os.replace = real_sync, real_replace
    assert calls == ["fsync", "replace"], calls  # the data is on disk before the ledger is swapped
    assert w.ledger.stat().st_mode & 0o777 == 0o644


def r8_suspect(mod: ModuleType, tmp: Path) -> None:
    def suspects(name: str, files: dict[int, str]) -> list[str]:
        d = tmp / name
        d.mkdir()
        w = World(mod, d)
        for phase, text in files.items():
            w.put(phase, text)
        return w.run()[1]["SUSPECT"]

    assert suspects("a", {1: FULL[1], 2: FULL[2], 3: "## Verdict\n", 4: FULL[4]}) == ["4"]
    assert suspects("b", {1: "## Findings\n", 2: FULL[2], 4: FULL[4]}) == ["2, 4"]
    assert suspects("c", {1: FULL[1], 2: FULL[2]}) == ["-"]
    assert suspects("d", {1: FULL[1], 2: "", 3: "## Verdict\n"}) == ["-"]
    assert suspects("e", FULL) == ["-"]


def r9_unreadable(mod: ModuleType, tmp: Path) -> None:
    w = World(mod, tmp)
    w.put(1, FULL[1])
    bad_state = f"{HL}{HEAD}\n{SEP}\n| 1 | a | b | p | s | done | - |\n"
    for n, junk in enumerate(("hello\n", "", bad_state)):
        w.ledger.write_text(junk, encoding="utf-8")
        code, out = w.run()
        assert out["LEDGER"][0].startswith("unreadable"), (n, out)
        assert (code, out["ACTION"], out["PHASE"]) == (3, ["stop-unreadable"], ["2"]), out
        assert "unknown" in out["DRIFT"][0] and w.state(1) == ("complete", "-")  # rebuilt
        code, out = w.run()  # the rebuilt ledger is readable, so the second resume goes on
        assert (code, out["ACTION"], out["LEDGER"]) == (0, ["start"], ["ok"]), out
    w.ledger.write_bytes(b"\xff\xfe\x00")
    code, out = w.run()
    assert out["LEDGER"][0].startswith("unreadable") and w.state(1) == ("complete", "-")
    for name in ("cut_mid_row", "cut_at_row", "cut_hash"):  # a truncated blocked ledger
        d = tmp / name
        d.mkdir()
        w = World(mod, d)
        w.put(1, FULL[1])
        w.run("rebuild")
        edit_ledger(w, 2, "blocked", "auth expired")
        text = w.ledger.read_text(encoding="utf-8")
        cut = {
            "cut_mid_row": text[: text.index("| 3 |") + 9],
            "cut_at_row": text[: text.index("| 3 |")],
            "cut_hash": text.replace("plan-hash: ", "plan-hush: "),
        }[name]
        w.ledger.write_text(cut, encoding="utf-8")
        code, out = w.run()
        assert (code, out["ACTION"]) == (3, ["stop-unreadable"]), (name, out)
        assert out["LEDGER"][0].startswith("unreadable"), (name, out)
    d = tmp / "alldone"
    d.mkdir()
    w = World(mod, d)
    for n, text in FULL.items():
        w.put(n, text)
    w.ledger.write_text("garbage", encoding="utf-8")
    assert w.run()[1]["ACTION"] == ["stop-done"]  # nothing left that a blocker could hold back
    code, out = w.run("resume", plan="missing.md")
    assert code == 2 and out["ACTION"] == ["stop-no-plan"] and "REASON" in out
    extra_r9(mod, tmp)


def extra_r9(mod: ModuleType, tmp: Path) -> None:
    """Reason text, the double fault, an unreadable ledger file, and rebuild on a corrupt ledger."""
    d = tmp / "reason"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    w.ledger.write_text("garbage", encoding="utf-8")
    real = os.replace

    def boom(src: object, dst: object) -> None:
        raise OSError("read-only")

    os.replace = boom  # type: ignore[assignment]
    try:
        code, out = w.run()  # unreadable and unwritable at once: it stops, and says both
        again = w.run()
    finally:
        os.replace = real
    assert code == 3 and out["ACTION"] == ["stop-unreadable"], out
    assert "unreadable" in out["LEDGER"][0] and "unwritable" in out["LEDGER"][0], out
    assert "blocker" in out["REASON"][0] and "ask the user" in out["REASON"][0], out
    assert again[0] == 3 and again[1]["ACTION"] == ["stop-unreadable"]
    d = tmp / "noread"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    w.run()
    real_read = Path.read_text

    def deny(self: Path, *a: object, **k: object) -> str:
        if self.name == "00_state.md":
            raise PermissionError(13, "Permission denied")
        return real_read(self, *a, **k)  # type: ignore[arg-type]

    with patched("read_text", deny):  # a ledger that cannot be read is unreadable, not a crash
        code, out = w.run()
    assert (code, out["ACTION"]) == (3, ["stop-unreadable"]), out
    assert "Permission" in out["LEDGER"][0]
    d = tmp / "nosearch"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    real_is_file = Path.is_file

    def cannot_search(self: Path) -> bool:
        if self.name == "00_state.md":
            raise PermissionError(13, "Permission denied")
        return real_is_file(self)

    with patched("is_file", cannot_search):  # a _workspace that cannot be searched: no traceback
        code, out = w.run()
    assert code in (0, 2, 3) and "ACTION" in out, (code, out)
    d = tmp / "rebuild_corrupt"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    w.ledger.write_text("garbage", encoding="utf-8")
    code, out = w.run("rebuild")
    assert code == 0 and out["LEDGER"][0].startswith("unreadable"), (code, out)


def r10_unwritable(mod: ModuleType, tmp: Path) -> None:
    w = World(mod, tmp)
    w.put(1, FULL[1])
    w.ledger.mkdir()  # a directory where the ledger belongs
    code, out = w.run()
    assert (code, out["ACTION"], out["PHASE"]) == (0, ["start"], ["2"]), out
    assert out["LEDGER"][0].startswith("unwritable: "), out
    for n, text in list(FULL.items())[1:]:
        w.put(n, text)
    assert w.run()[0] == 3  # exit codes hold when every phase is done
    code, out = w.run("rebuild")
    assert code == 0 and out["LEDGER"][0].startswith("unwritable: ")
    d = tmp / "parent_is_file"
    d.mkdir()
    w = World(mod, d)
    (d / "x").write_text("a file", encoding="utf-8")
    argv = ["resume", "plan.md", "--ledger", "x/s.md"]
    buf = io.StringIO()
    with contextlib.chdir(d), contextlib.redirect_stdout(buf):
        code = mod.main(argv)
    assert code == 0 and "LEDGER: unwritable: " in buf.getvalue(), buf.getvalue()
    d = tmp / "replace_fails"
    d.mkdir()
    w = World(mod, d)
    w.put(1, FULL[1])
    w.run()
    before = w.ledger.read_bytes()
    w.put(2, FULL[2])
    real = os.replace

    def boom(src: object, dst: object) -> None:
        raise OSError("disk full")

    os.replace = boom  # type: ignore[assignment]
    try:
        code, out = w.run()
    finally:
        os.replace = real
    assert out["LEDGER"] == ["unwritable: disk full"] and code == 0, out
    assert w.ledger.read_bytes() == before  # the old ledger is whole
    assert [p.name for p in (d / "_workspace").iterdir() if p.name.endswith(".tmp")] == []
    if os.geteuid() != 0:  # root ignores permission bits
        (d / "_workspace").chmod(0o500)
        try:
            w.put  # noqa: B018 - the directory is read-only now; only resume is run
            assert w.run()[1]["LEDGER"][0].startswith("unwritable")
        finally:
            (d / "_workspace").chmod(0o700)


def doc_blocks(doc: str) -> dict[str, str]:
    return {
        m[1]: m[2] for m in re.finditer(r"^```md (\S+)\n(.*?)^```$", doc, re.DOTALL | re.MULTILINE)
    }


def doc_example(mod: ModuleType, doc: str, tmp: Path) -> None:
    """Rebuild each worked example from the files its own rows describe; the bytes must match."""
    blocks = doc_blocks(doc)
    assert set(blocks) == {"plan", "ledger-a", "ledger-b"}
    for name in ("ledger-a", "ledger-b"):
        d = tmp / name
        d.mkdir()
        shown = blocks[name]
        plan_path = re.search(r"^plan: (\S+)$", shown, re.MULTILINE)
        assert plan_path
        target = d / plan_path[1]
        target.parent.mkdir(parents=True)
        target.write_text(blocks["plan"], encoding="utf-8")
        (d / "_workspace").mkdir()
        for r in mod.parse_ledger(shown)[0]:
            names = [] if r["sections"] == "-" else [s.strip() for s in r["sections"].split(";")]
            if r["completion"] == "pending":
                continue
            if r["completion"] == "partial":
                names = names[:-1]  # a file that stopped before its last section
            body = "".join(f"## {s}\ntext\n" for s in names) or "text\n"
            (d / r["path"]).write_text(body, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.chdir(d), contextlib.redirect_stdout(buf):
            assert mod.main(["resume", plan_path[1]]) in (0, 3)
        assert (d / "_workspace/00_state.md").read_text(encoding="utf-8") == shown, name
        lines = buf.getvalue().splitlines()
        want = {"ledger-a": ("start", "3", "-"), "ledger-b": ("resume", "3", "4")}[name]
        got = (lines[1][8:], lines[2][7:], lines[-1][9:])
        assert got == want, (name, lines)


def doc_rules(doc: str) -> None:
    found = {m[1]: m[2] for m in re.finditer(r"^\| (R\d+) \| (.*) \|$", doc, re.MULTILINE)}
    assert set(found) == set(RULES) == set(CHECKS), (sorted(found), sorted(CHECKS))
    for rid, phrase in RULES.items():
        assert phrase in found[rid], (rid, phrase)


def doc_table(mod: ModuleType, doc: str) -> None:
    assert HEAD in doc and PLAN_HEAD in doc
    assert doc.count(HEAD) >= 2 and "| " + " | ".join(mod.COLS) + " |" == HEAD
    for state in mod.STATES:
        assert f"| {state} |" in doc, state
    assert tuple(mod.STATES) == ("pending", "partial", "complete", "blocked")
    for action, code in ACTIONS.items():
        assert re.search(rf"^\| {action} \| {code} \|", doc, re.MULTILINE), action
    assert OBSERVED == set(ACTIONS.items()), sorted(OBSERVED)


def doc_surface(doc: str) -> None:
    start = doc.index("## 6. Claude chat and Claude Cowork")
    chat = doc[start : doc.index("## 7.")]
    assert "unverified — confirm in that surface before relying on it" in chat
    assert "STATE LEDGER" in chat
    assert not re.search(r"SendMessage|Agent\(|TaskCreate|Workflow|subagent_type", chat)
    ranges = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
    assert not any(lo <= ord(c) <= hi for c in doc for lo, hi in ranges), "Hangul"


def doc_attrib(doc: str, script: str) -> None:
    oh = "references/openharness/src/openharness/autopilot/service.py:405 (MIT)"
    mh = "references/meta_harness/.agents/skills/harness/SKILL.md:158 (Apache-2.0)"
    for cite in (
        "references/meta_harness/docs/architecture/handoffs.md:13 (Apache-2.0)",
        "references/meta_harness/docs/architecture/handoffs.md:9 (Apache-2.0)",
        mh,
        oh,
        "references/openharness/src/openharness/services/compact/__init__.py:635 (MIT)",
        "references/openharness/src/openharness/services/compact/__init__.py:566 (MIT)",
        "references/deepseek_harness/packages/goal/goal/src/types.ts:64 (MIT)",
    ):
        assert f"adapted from {cite}" in doc, cite
    for cite in (
        "meta_harness/.agents/skills/harness/SKILL.md:158",
        "meta_harness/scripts/audit_harness.py:61",
    ):
        assert f"references/{cite}" in script, cite
    assert "(Apache-2.0)" in script and "autopilot/service.py:405 (MIT)" in script
    assert "goal/src/fold.ts:339" in script and "types.ts:64 (MIT)" in script
    assert "scripts/state_ledger.py" in doc and "tests/test_state_ledger.py" in doc


def skill_pointer(skill: str) -> None:
    (step0,) = [x for x in skill.splitlines() if x.startswith("- **Step 0 context check**")]
    assert "`references/state-ledger.md`" in step0 and "scripts/state_ledger.py" in step0
    assert "two or more phases" in step0 and "first unfinished phase" in step0
    assert (
        ", and the script is copied into the harness when the plugin is not installed there"
        in step0
    )
    assert (
        "adapted from references/openharness/src/openharness/autopilot/service.py:405 (MIT)"
        in step0
    )
    assert (
        "adapted from references/meta_harness/.agents/skills/harness/SKILL.md:158 (Apache-2.0)"
        in step0
    )
    bullet = (
        "- State ledger, rebuild and resume across context resets: `references/state-ledger.md`"
    )
    assert bullet in skill.splitlines()
    assert DOC.is_file() and SCRIPT.is_file()


NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4}


def min_rows(mod: ModuleType, tmp: Path) -> int:
    """The fewest plan rows the script accepts, found by trying 1, 2, 3 ..."""
    head = PLAN.split("| 1 | ")[0]
    for k in range(1, 5):
        d = tmp / f"k{k}"
        d.mkdir()
        rows = "".join(f"| {i} | a | b | _workspace/0{i}_x.md | - |\n" for i in range(1, k + 1))
        if World(mod, d, head + rows).run()[0] != 2:
            return k
    raise AssertionError("no plan size is accepted")


def doc_binds(mod: ModuleType, doc: str, skill: str, tmp: Path) -> None:
    """Prose that tells the orchestrator what to do, tied to the script where it can be."""
    low = doc.lower()
    for phrase, count in PINS.items():
        assert low.count(phrase.lower()) >= count, phrase
    found = min_rows(mod, tmp)
    (step0,) = [x for x in skill.splitlines() if x.startswith("- **Step 0 context check**")]
    for where, pattern, text in (
        ("doc section 1", r"the run has (\w+) or more phases", doc),
        ("SKILL.md Step 0", r"A run of (\w+) or more phases", step0),
    ):
        m = re.search(pattern, text)
        assert m and NUMBERS[m[1]] == found, (where, m and m[1], found)
    assert "a named partial re-run still wins" in step0


def script_links(doc: str, skill: str) -> None:
    """The lint does not check scripts/ mentions, so every one must name a real file."""
    skill_dir = REPO / "skills/finhub-harness"
    for text in (doc, skill):
        refs = re.findall(r"scripts/([\w.-]+\.(?:py|sh))", text)
        assert "state_ledger.py" in refs or text is skill
        for name in refs:
            assert (skill_dir / "scripts" / name).is_file() or (
                REPO / "scripts" / name
            ).is_file(), name


CHECKS: dict[str, Callable[[ModuleType, Path], None]] = {
    "R1": r1_shape,
    "R2": r2_plan,
    "R3": r3_completion,
    "R4": r4_files_win,
    "R5": r5_blocked,
    "R6": r6_target,
    "R7": r7_readonly,
    "R8": r8_suspect,
    "R9": r9_unreadable,
    "R10": r10_unwritable,
}


def problems(script: Path, doc: str, skill: str) -> list[str]:
    """Every failed check as 'TAG: detail'; empty when script, doc and SKILL.md agree."""
    found: list[str] = []
    OBSERVED.clear()

    def attempt(tag: str, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - a crash in a mutant counts as a failed check
            found.append(f"{tag}: {type(e).__name__}: {str(e)[:200]}")

    try:
        mod = load(script, f"state_ledger_{next(COUNTER)}")
    except Exception as e:  # noqa: BLE001
        return [f"R1: script does not load: {e}"]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for rid, check in CHECKS.items():
            d = tmp / rid
            d.mkdir()
            attempt(rid, functools.partial(check, mod, d))
        de = tmp / "example"
        de.mkdir()
        attempt("doc-example", lambda: doc_example(mod, doc, de))
    attempt("doc-rules", lambda: doc_rules(doc))
    attempt("doc-table", lambda: doc_table(mod, doc))
    attempt("doc-surface", lambda: doc_surface(doc))
    text = script.read_text(encoding="utf-8")
    attempt("doc-attrib", lambda: doc_attrib(doc, text))
    attempt("skill-pointer", lambda: skill_pointer(skill))
    with tempfile.TemporaryDirectory() as raw:
        bd = Path(raw)
        attempt("doc-binds", lambda: doc_binds(mod, doc, skill, bd))
    attempt("script-links", lambda: script_links(doc, skill))
    return found


def sub(old: str, new: str, count: int = 1) -> Callable[[str], str]:
    def fn(text: str) -> str:
        assert text.count(old) == count, (old, text.count(old))
        return text.replace(old, new)

    return fn


def drop(pattern: str) -> Callable[[str], str]:
    def fn(text: str) -> str:
        out, n = re.subn(pattern, "", text, flags=re.MULTILINE)
        assert n == 1, (pattern, n)
        return out

    return fn


# (name, target, expected tag, edit). Each is a plausible regression; none is behaviour-neutral.
MUTANTS: list[tuple[str, str, str, Callable[[str], str]]] = [
    (
        "S01 ledger loses the note column",
        "script",
        "R1",
        sub('COLS = PLAN_COLS + ("completion", "note")', 'COLS = PLAN_COLS + ("completion",)'),
    ),
    ("S02 blocked state removed", "script", "R1", sub('"complete", "blocked")', '"complete")')),
    (
        "S03 blocked without a reason accepted",
        "script",
        "R1",
        sub('if r["completion"] == "blocked" and r["note"] == "-":', "if False:"),
    ),
    (
        "S04 plan with one phase accepted",
        "script",
        "R2",
        sub("if len(rows) < 2:", "if len(rows) < 1:"),
    ),
    (
        "S05 path escape accepted",
        "script",
        "R2",
        sub(
            'if p.is_absolute() or w.anchor or ".." in p.parts or "\\\\" in r["path"]:', "if False:"
        ),
    ),
    (
        "S06 duplicate plan ids accepted",
        "script",
        "R2",
        sub(
            "    unique(rows)\n    for r in rows:\n        p, w = PurePosixPath",
            "    for r in rows:\n        p, w = PurePosixPath",
        ),
    ),
    (
        "S07 empty cell accepted",
        "script",
        "R2",
        sub('if len(c) != len(cols) or "" in c:', "if len(c) != len(cols):"),
    ),
    (
        "S08 missing separator row accepted",
        "script",
        "R2",
        sub('if not set(next(it, "x").strip()) <= set("|-: "):', "if False:"),
    ),
    (
        "S09 empty file reads as complete",
        "script",
        "R3",
        sub('return "partial", "empty file"', 'return "complete", "-"'),
    ),
    (
        "S10 heading matched as a substring",
        "script",
        "R3",
        sub(
            "gone = [s for s in need if s not in have]",
            "gone = [s for s in need if not any(s in h for h in have)]",
        ),
    ),
    (
        "S11 a dash in sections is a section name",
        "script",
        "R3",
        sub(
            'need = [] if sections == "-" else [s.strip() for s in sections.split(";")]',
            'need = [s.strip() for s in sections.split(";")]',
        ),
    ),
    (
        "S12 fences never open",
        "script",
        "R3",
        sub("        elif m:\n            fence = m[1]", "        elif m:\n            pass"),
    ),
    (
        "S13 inner fence closes an outer one",
        "script",
        "R3",
        sub("and len(m[1]) >= len(fence)", "and True"),
    ),
    (
        "S14 a directory is read as a file",
        "script",
        "R3",
        sub("if not path.is_file():", "if not path.exists():"),
    ),
    (
        "S15 files do not win",
        "script",
        "R4",
        sub(
            'unfinished = [r for r in rows if r["completion"] != "complete"]',
            'unfinished = [r for r in (old or rows) if r["completion"] != "complete"]',
        ),
    ),
    (
        "S16 drift not reported",
        "script",
        "R4",
        sub('if r["phase"] in seen and seen[r["phase"]] != r["completion"]', "if False"),
    ),
    (
        "S17 dropped phase not reported",
        "script",
        "R4",
        sub('for i in seen if i not in {p["phase"] for p in plan}', "for i in seen if False"),
    ),
    (
        "S18 no carry-over of a blocker",
        "script",
        "R5",
        sub(
            'held = {r["phase"]: r["note"] for r in old or [] if r["completion"] == "blocked"}',
            "held = {}",
        ),
    ),
    (
        "S19 a complete file does not clear a blocker",
        "script",
        "R5",
        sub('if state != "complete" and p["phase"] in held:', 'if p["phase"] in held:'),
    ),
    (
        "S20 partial counts as done",
        "script",
        "R6",
        sub(
            'unfinished = [r for r in rows if r["completion"] != "complete"]',
            'unfinished = [r for r in rows if r["completion"] == "pending"]',
        ),
    ),
    (
        "S21 a stop-blocked exits 0",
        "script",
        "R5",
        sub('return 3 if act.startswith("stop") else 0', 'return 3 if act == "stop-done" else 0'),
    ),
    (
        "S22 next header always done",
        "script",
        "R6",
        sub(
            'for r in rows if r["completion"] != "complete"), "done")',
            'for r in rows if False), "done")',
        ),
    ),
    (
        "S23 ledger rewritten on every run",
        "script",
        "R7",
        sub(
            "if current != text:",
            "if True:",
        ),
    ),
    (
        "S24 judging rewrites the artefact",
        "script",
        "R7",
        sub(
            'text = raw.decode("utf-8-sig", errors="replace")\n',
            'text = raw.decode("utf-8-sig", errors="replace")\n    path.write_text(text, encoding="utf-8")\n',
        ),
    ),
    (
        "S25 suspect rows not listed",
        "script",
        "R8",
        sub('for r in after if r["completion"] == "complete")', "for r in after if False)"),
    ),
    (
        "S26 an unreadable ledger aborts",
        "script",
        "R9",
        sub(
            "except (OSError, ValueError) as e:\n            state",
            "except OSError as e:\n            state",
        ),
    ),
    (
        "S27 a missing plan exits 0",
        "script",
        "R9",
        sub('REASON: {e}")\n        return 2', 'REASON: {e}")\n        return 0'),
    ),
    (
        "D01 ledger header drops a field",
        "doc",
        "doc-table",
        sub(HEAD, "| " + " | ".join(COLS[:6]) + " |", 2),
    ),
    ("D02 rule R6 deleted", "doc", "doc-rules", drop(r"^\| R6 \|.*\n")),
    (
        "D03 R6 reversed",
        "doc",
        "doc-rules",
        sub("first row that is not complete", "last row that is not complete"),
    ),
    ("D04 R4 reversed", "doc", "doc-rules", sub("Files win.", "The ledger wins.")),
    ("D05 R7 reversed", "doc", "doc-rules", sub("writes only", "writes every")),
    ("D06 R8 reversed", "doc", "doc-rules", sub("listed as suspect", "listed as fresh")),
    (
        "D07 R5 reversed",
        "doc",
        "doc-rules",
        sub("clears when the file is complete", "stays until the user clears it"),
    ),
    ("D08 R3 reversed", "doc", "doc-rules", sub("outside code fences", "inside code fences")),
    ("D09 R2 weakened", "doc", "doc-rules", sub("at least two rows", "at least one row")),
    ("D10 R1 changed", "doc", "doc-rules", sub("exactly seven cells", "exactly six cells")),
    (
        "D11 R9 stop condition dropped",
        "doc",
        "doc-rules",
        sub("the decision is `stop-unreadable`", "the decision is `start`"),
    ),
    ("D12 stop-blocked row removed", "doc", "doc-table", drop(r"^\| stop-blocked \| 3 \|.*\n")),
    (
        "D13 stop-done exit changed",
        "doc",
        "doc-table",
        sub("| stop-done | 3 |", "| stop-done | 0 |"),
    ),
    (
        "D14 state removed from the table",
        "doc",
        "doc-table",
        sub("| blocked | a worker", "| halted | a worker"),
    ),
    (
        "D15 example A disagrees with the rule",
        "doc",
        "doc-example",
        sub("| Verdict; Reasons | pending | - |", "| Verdict; Reasons | complete | - |"),
    ),
    (
        "D16 example B note changed",
        "doc",
        "doc-example",
        sub("| partial | missing: Reasons |", "| partial | missing: Verdict |"),
    ),
    (
        "D17 example next changed",
        "doc",
        "doc-example",
        sub(
            "next: 3\n\n| phase | producer | consumer | path | sections | completion | note |\n|---|---|---|---|---|---|---|\n| 1 | analyst | architect | _workspace/01_analyst_findings.md | Findings; Gaps | complete | - |\n| 2 | architect | reviewer | _workspace/02_architect_design.md | Design; Authority List | complete | - |\n| 3 | reviewer | builder | _workspace/03_reviewer_verdict.md | Verdict; Reasons | partial",
            "next: 4\n\n| phase | producer | consumer | path | sections | completion | note |\n|---|---|---|---|---|---|---|\n| 1 | analyst | architect | _workspace/01_analyst_findings.md | Findings; Gaps | complete | - |\n| 2 | architect | reviewer | _workspace/02_architect_design.md | Design; Authority List | complete | - |\n| 3 | reviewer | builder | _workspace/03_reviewer_verdict.md | Verdict; Reasons | partial",
        ),
    ),
    (
        "D18 attribution removed",
        "doc",
        "doc-attrib",
        sub(
            "adapted from references/openharness/src/openharness/autopilot/service.py:405 (MIT)",
            "adapted from the OpenHarness autopilot",
        ),
    ),
    (
        "D23 next-step attribution removed",
        "doc",
        "doc-attrib",
        sub(
            "adapted from references/openharness/src/openharness/services/compact/__init__.py:566 (MIT)",
            "adapted from the OpenHarness compaction code",
        ),
    ),
    (
        "D19 chat caveat removed",
        "doc",
        "doc-surface",
        sub("unverified — confirm in that surface before relying on it", "known to work"),
    ),
    (
        "D20 chat section names a messaging tool",
        "doc",
        "doc-surface",
        sub(
            "The fallback does not name a sub-agent, messaging or task primitive.",
            "The fallback calls SendMessage to ask the user.",
        ),
    ),
    ("D21 Hangul added", "doc", "doc-surface", lambda t: t + "\n\uc0c1\ud0dc\n"),
    (
        "D22 script link removed",
        "doc",
        "doc-attrib",
        sub("tests/test_state_ledger.py", "the tests"),
    ),
    (
        "K01 Step 0 pointer removed",
        "skill",
        "skill-pointer",
        sub(" (`references/state-ledger.md`, script `scripts/state_ledger.py`)", ""),
    ),
    (
        "K02 References bullet removed",
        "skill",
        "skill-pointer",
        drop(r"^- State ledger, rebuild and resume across context resets:.*\n"),
    ),
    (
        "K03 pointer attribution removed",
        "skill",
        "skill-pointer",
        sub(
            "(adapted from references/openharness/src/openharness/autopilot/service.py:405 (MIT); ",
            "(",
        ),
    ),
]

MUTANTS += [
    (
        "S28 drive letters and UNC accepted",
        "script",
        "R2",
        sub("p.is_absolute() or w.anchor or", "p.is_absolute() or"),
    ),
    (
        "S29 empty section names accepted",
        "script",
        "R2",
        sub('if r["sections"] != "-" and "" in', 'if False and "" in'),
    ),
    (
        "S30 containment check dropped",
        "script",
        "R2",
        sub("        contain(plan, base, ledger)\n", ""),
    ),
    (
        "S31 ledger path not resolved",
        "script",
        "R2",
        sub("for p in plan] + [ledger]", "for p in plan]"),
    ),
    (
        "S32 ledger written in place, not replaced",
        "script",
        "R7",
        sub(
            "        os.replace(tmp, path)\n",
            '        path.write_text(Path(tmp).read_text(encoding="utf-8"), encoding="utf-8")\n        os.unlink(tmp)\n',
        ),
    ),
    (
        "S33 OSError on the write escapes",
        "script",
        "R10",
        sub(
            '    except OSError as e:\n        state = f"unwritable',
            '    except KeyError as e:\n        state = f"unwritable',
        ),
    ),
    (
        "S34 unwritable not reported",
        "script",
        "R10",
        sub('state = f"unwritable: {e}" if not corrupt', 'state = "ok" if not corrupt'),
    ),
    (
        "S35 temporary file left behind",
        "script",
        "R10",
        sub("            os.unlink(tmp)\n", "            pass\n"),
    ),
    ("S36 corrupt ledger resumes", "script", "R9", sub("    elif corrupt:\n", "    elif False:\n")),
    (
        "S37 a ledger missing phases is trusted",
        "script",
        "R9",
        sub("if h_old == digest and not same:", "if False:"),
    ),
    (
        "S38 blocker carried across plans",
        "script",
        "R5",
        sub(
            'old, state, changed = rows_old, "ok", h_old != digest',
            'old, state, changed = rows_old, "ok", False',
        ),
    ),
    (
        "S39 plan hash covers only phase ids",
        "script",
        "R5",
        sub('"|".join(p[c] for c in PLAN_COLS)', 'p["phase"]'),
    ),
    ("S40 byte order mark kept", "script", "R3", sub('"utf-8-sig"', '"utf-8"')),
    ("S41 size cap ignored", "script", "R3", sub("if len(raw) > CAP:", "if False:")),
    (
        "S42 quadratic heading regex back",
        "script",
        "R3",
        sub(
            'HEAD = re.compile(r"#{1,6}\\s+(\\S.*)")',
            'HEAD = re.compile(r"#{1,6}\\s+(.+?)\\s*#*\\s*$")',
        ),
    ),
    ("S43 closing hashes kept", "script", "R3", sub('m[1].rstrip(" #\\t")', "m[1].rstrip()")),
    (
        "S44 a tilde line closes a backtick fence",
        "script",
        "R3",
        sub("m[1][0] == fence[0] and ", ""),
    ),
    (
        "S45 a closing fence may carry an info string",
        "script",
        "R3",
        sub(" and not m[2].strip()", ""),
    ),
    (
        "S46 no drift line when a blocker is cleared",
        "script",
        "R5",
        sub(
            'if r["phase"] in seen and seen[r["phase"]] != r["completion"]',
            'if r["phase"] in seen and seen[r["phase"]] != r["completion"] != "complete"',
        ),
    ),
    (
        "S47 next header skips blocked rows",
        "script",
        "R5",
        sub(
            'for r in rows if r["completion"] != "complete"), "done")',
            'for r in rows if r["completion"] in ("pending", "partial")), "done")',
        ),
    ),
    (
        "S48 unreadable ledger beats done",
        "script",
        "R9",
        sub(
            "    if first is None:\n        act, why",
            "    if first is None and not corrupt:\n        act, why",
        ),
    ),
    (
        "S49 stop-unreadable exits 0",
        "script",
        "R9",
        sub(
            'return 3 if act.startswith("stop") else 0',
            'return 3 if act in ("stop-done", "stop-blocked") else 0',
        ),
    ),
    (
        "D24 R10 reversed",
        "doc",
        "doc-rules",
        sub("reported as `LEDGER: unwritable: <reason>`", "reported as `LEDGER: ok`"),
    ),
    (
        "D25 R5 plan-hash clause dropped",
        "doc",
        "doc-binds",
        sub("of the same plan (same `plan-hash`)", "of any plan"),
    ),
    (
        "D26 content caveat dropped from step 5",
        "doc",
        "doc-binds",
        sub(
            " Say that complete means the headings are present, not that the content is right or current.",
            "",
        ),
    ),
    (
        "D27 R6 blocked clause reversed",
        "doc",
        "doc-binds",
        sub("Blocked: stop and report the note; retry nothing.", "Blocked: retry that phase once."),
    ),
    (
        "D28 stop-blocked row retries",
        "doc",
        "doc-binds",
        sub(
            "reports `REASON`, retries nothing, and asks the user",
            "reports `REASON`, retries once, and asks the user",
        ),
    ),
    (
        "D29 partial re-run priority reversed",
        "doc",
        "doc-binds",
        sub("takes priority over R6", "is overridden by R6"),
    ),
    (
        "D30 R7 complete phase may be re-run",
        "doc",
        "doc-binds",
        sub(
            "a complete phase is not run again unless the user names it",
            "a complete phase is run again on every resume",
        ),
    ),
    (
        "D31 rebuild after every phase dropped",
        "doc",
        "doc-binds",
        sub("**At the start of a run** and **after every phase**", "**At the start of a run**"),
    ),
    (
        "D32 chat fallback assumes done",
        "doc",
        "doc-binds",
        sub("start from phase 1 and say so", "treat the run as done"),
    ),
    (
        "D33 doc threshold changed",
        "doc",
        "doc-binds",
        sub("the run has two or more phases", "the run has one or more phases"),
    ),
    (
        "D34 plugin-copy sentence removed",
        "doc",
        "doc-binds",
        sub("copy `state_ledger.py` into the generated harness", "ignore the script"),
    ),
    (
        "D35 script link broken in the doc",
        "doc",
        "script-links",
        sub(
            "Delete it and `scripts/state_ledger.py rebuild`",
            "Delete it and `scripts/state_ledgr.py rebuild`",
        ),
    ),
    (
        "K04 SKILL.md threshold changed",
        "skill",
        "doc-binds",
        sub("A run of two or more phases", "A run of one or more phases"),
    ),
    (
        "Z01 ledger left at mode 0600",
        "script",
        "R7",
        sub("        os.chmod(tmp, 0o644)\n", ""),
    ),
    (
        "Z05 level-7 line counts as a heading",
        "script",
        "R3",
        sub(r"#{1,6}\s+(\S.*)", r"#{1,7}\s+(\S.*)"),
    ),
    ("Z06 tab before closing hashes kept", "script", "R3", sub('rstrip(" #\\t")', 'rstrip(" #")')),
    (
        "Z07 contain fails open on an unresolvable path",
        "script",
        "R2",
        sub("            inside = False\n", "            inside = True\n"),
    ),
    (
        "Z09 double fault shows one state only",
        "script",
        "R9",
        sub(
            'state = f"unwritable: {e}" if not corrupt else f"{state}; unwritable: {e}"',
            'state = f"unwritable: {e}"',
        ),
    ),
    (
        "Z14 stop-unreadable reason replaced",
        "script",
        "R9",
        sub("a blocker may have been lost; ask the user, then resume again", "unreadable"),
    ),
    (
        "Z16 unreadable ledger file crashes",
        "script",
        "R9",
        sub(
            "except (OSError, ValueError) as e:\n            state, corrupt",
            "except ValueError as e:\n            state, corrupt",
        ),
    ),
    (
        "Z18 rebuild stops on a corrupt ledger",
        "script",
        "R9",
        sub(
            "        return 0\n    if first is None:",
            "        return 3 if corrupt else 0\n    if first is None:",
        ),
    ),
    (
        "Z20 temporary file outside the ledger directory",
        "script",
        "R7",
        sub("tempfile.mkstemp(dir=path.parent,", "tempfile.mkstemp(dir=tempfile.gettempdir(),"),
    ),
    (
        "Z22 base not resolved before the containment test",
        "script",
        "R2",
        sub("root = base.resolve()", "root = base.absolute()"),
    ),
    (
        "B1 unopenable phase file crashes",
        "script",
        "R3",
        sub(
            '    except OSError as e:\n        return "partial", f"unreadable: {e}"\n',
            '    except KeyError as e:\n        return "partial", f"unreadable: {e}"\n',
        ),
    ),
    (
        "K07 copy clause removed from SKILL.md",
        "skill",
        "skill-pointer",
        sub(
            ", and the script is copied into the harness when the plugin is not installed there", ""
        ),
    ),
    (
        "D35 doc never copies the script",
        "doc",
        "doc-binds",
        sub("installed, copy `state_ledger.py`", "installed, never copy `state_ledger.py`"),
    ),
    (
        "D36 stop-unreadable row says nothing",
        "doc",
        "doc-binds",
        sub(
            "says the ledger was unreadable and a blocker may have been lost, asks the user, and on a yes runs `resume` again",
            "goes on",
        ),
    ),
    (
        "D37 rule R9 says go on",
        "doc",
        "doc-binds",
        sub("so ask the user, then run `resume` again, which reads the rebuilt ledger", "so go on"),
    ),
    (
        "D38 read-only workspace sentence removed",
        "doc",
        "doc-binds",
        sub(
            "; if `resume` still says `stop-unreadable` after the user said yes, the ledger cannot be rewritten (a read-only `_workspace`): tell the user and stop",
            "",
        ),
    ),
    (
        "D39 plan edit sentence removed",
        "doc",
        "doc-binds",
        sub(
            " A plan edit clears every blocker, so tell the user which phases were blocked before the edit if you know.",
            "",
        ),
    ),
    (
        "D40 resume-before-rebuild sentence removed",
        "doc",
        "doc-binds",
        sub(
            " In a session that continues, run `resume` before any `rebuild`: `rebuild` overwrites an unreadable ledger and so skips the stop.",
            "",
        ),
    ),
    (
        "K05 priority clause removed from SKILL.md",
        "skill",
        "doc-binds",
        sub("a named partial re-run still wins, and ", ""),
    ),
    (
        "K06 script link broken in SKILL.md",
        "skill",
        "script-links",
        sub("script `scripts/state_ledger.py`", "script `scripts/state_ledgr.py`"),
    ),
]


def real() -> tuple[str, str]:
    return DOC.read_text(encoding="utf-8"), SKILL.read_text(encoding="utf-8")


def test_real_files_pass_every_check() -> None:
    doc, skill = real()
    assert problems(SCRIPT, doc, skill) == []


def test_every_rule_has_a_check_and_a_doc_row() -> None:
    doc, _ = real()
    doc_rules(doc)


@pytest.mark.parametrize("name,target,tag,edit", MUTANTS, ids=[m[0].split()[0] for m in MUTANTS])
def test_mutant_is_killed(
    tmp_path: Path, name: str, target: str, tag: str, edit: Callable[[str], str]
) -> None:
    doc, skill = real()
    script = SCRIPT.read_text(encoding="utf-8")
    if target == "script":
        script = edit(script)
    elif target == "doc":
        doc = edit(doc)
    else:
        skill = edit(skill)
    mutant = tmp_path / "state_ledger_mutant.py"
    mutant.write_text(script, encoding="utf-8")
    found = problems(mutant, doc, skill)
    assert any(p.startswith(tag + ":") for p in found), (name, found)


def test_cli_exit_codes_and_output(tmp_path: Path) -> None:
    (tmp_path / "_workspace").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")

    def cli(cmd: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), cmd, "plan.md"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    run = cli("resume")
    assert run.returncode == 0 and "ACTION: start\nPHASE: 1\n" in run.stdout, (
        run.stdout + run.stderr
    )
    for n, text in FULL.items():
        (tmp_path / f"_workspace/0{n}_{'abcd'[n - 1]}.md").write_text(text, encoding="utf-8")
    run = cli("resume")
    assert run.returncode == 3 and "ACTION: stop-done" in run.stdout
    (tmp_path / "plan.md").write_text("no table\n", encoding="utf-8")
    run = cli("resume")
    assert run.returncode == 2 and "ACTION: stop-no-plan" in run.stdout
    bad = subprocess.run(
        [sys.executable, str(SCRIPT), "explode", "plan.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert bad.returncode == 2 and "Traceback" not in bad.stderr
