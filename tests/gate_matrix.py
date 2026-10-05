"""The C9 resolution-mismatch matrix: every way the RUNNER and the CHILD could resolve the executable
word of a non-shell gate differently, as data plus a real-CLI runner. Used by tests/test_gates.py and by
the probe script (_workspace/02_strategy-architect_C9_probe_matrix.py), so the table exists once.

A row builds a fresh folder B holding a test-made "shell" (an executable file called bash that creates
MARK in its cwd with a shell builtin), the row's links and one gate, then runs the REAL CLI in a mode:
M1 runner cwd B/a/b (not the gate's), --root B; M2 runner cwd = the gate's cwd; M3 runner cwd B/a/b,
--root B/sub, default gate cwd. A refused row must give exit 2, status policy-error and no MARK.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

STRACE = shutil.which("strace") or "strace"  # absolute: a row may set a PATH without it
FAKE = '#!/bin/sh\n: > "$PWD/MARK"\n'  # a builtin only: PATH may not hold touch
# (id, description, files, gate, PATH, extra); files: (relpath, kind, arg), kinds fake | link | file | copy |
# hard | dir; gate: ("argv", [words]) | ("command", text); {B} base, {S} B/sub, {Brel} B without the slash;
# extra: cwd, rootarg, skip3, limit (a documented limit: MARK is expected), core (also run in M2 and M3)
D1 = [("sub/lnk", "link", "/proc/self/cwd"), ("mysh", "link", "bin/bash")]
M = "mysh"
ROWS: list[tuple] = [
    (
        "r01",
        "file named like a shell",
        [("sub/bash", "fake", "")],
        ("argv", ["./bash", "-c", "x"]),
        None,
        {},
    ),
    (
        "r02",
        "link last, relative target",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh", "-c", "x"]),
        None,
        {"core": True},
    ),
    (
        "r03",
        "link last, absolute target",
        [("sub/mysh", "link", "{B}/bin/bash")],
        ("argv", ["./mysh", "-c", "x"]),
        None,
        {},
    ),
    (
        "r04",
        "chain mixing absolute and relative targets",
        [("sub/l1", "link", "l2"), ("sub/l2", "link", "{S}/l3"), ("sub/l3", "link", "../bin/bash")],
        ("argv", ["./l1"]),
        None,
        {"core": True},
    ),
    (
        "r05",
        "dir link in the middle",
        [("sub/d", "link", "../bin"), ("bin/mysh", "link", "bash")],
        ("argv", ["d/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r06",
        "dir link first, absolute word",
        [("sub/d", "link", "../bin"), ("bin/mysh", "link", "bash")],
        ("argv", ["{S}/d/mysh"]),
        None,
        {},
    ),
    (
        "r07",
        "target climbing to the root",
        [("sub/mysh", "link", "../" * 12 + "{Brel}/bin/bash")],
        ("argv", ["./mysh"]),
        None,
        {},
    ),
    (
        "r08",
        "D1: .. after a link to /proc/self/cwd",
        D1,
        ("argv", ["lnk/../mysh", "-c", "x"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r09",
        "D1 absolute word",
        D1,
        ("argv", ["{S}/lnk/../mysh", "-c", "x"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r10",
        "D1 with ./",
        D1,
        ("argv", ["./lnk/../mysh", "-c", "x"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r11",
        "D1 link to /proc/thread-self/cwd",
        [("sub/lnk", "link", "/proc/thread-self/cwd"), ("mysh", "link", "bin/bash")],
        ("argv", ["lnk/../mysh"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r12",
        "D1 as a PATH entry lnk/..",
        D1,
        ("argv", ["mysh", "-c", "x"]),
        "lnk/..:{B}/none",
        {"skip3": True, "core": True},
    ),
    (
        "r13",
        "D1 string form",
        D1,
        ("command", "lnk/../mysh -c x"),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r14",
        ".. after a plain directory link",
        [("sub/d", "link", "../bin"), ("mysh2", "link", "bin/bash")],
        ("argv", ["d/../mysh2"]),
        None,
        {"skip3": True, "core": True},
    ),
    (
        "r15",
        ".. with no link at all (cost: refused)",
        [("mysh", "link", "bin/bash")],
        ("argv", ["../mysh"]),
        None,
        {"skip3": True},
    ),
    (
        "r16",
        "/proc/self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/self/cwd/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r17",
        "/proc/thread-self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/thread-self/cwd/mysh"]),
        None,
        {},
    ),
    (
        "r18",
        "/proc/self/cwd/./<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/self/cwd/./mysh"]),
        None,
        {},
    ),
    (
        "r19",
        "/proc//self/cwd//<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc//self/cwd//mysh"]),
        None,
        {},
    ),
    (
        "r20",
        "//proc/self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["//proc/self/cwd/mysh"]),
        None,
        {},
    ),
    (
        "r21",
        "/./proc/self/cwd/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/./proc/self/cwd/mysh"]),
        None,
        {},
    ),
    (
        "r22",
        "/proc/self/root/<B>/sub/<link>",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["/proc/self/root{S}/mysh"]),
        None,
        {},
    ),
    ("r23", "/proc/self/exe", [], ("argv", ["/proc/self/exe"]), None, {}),
    ("r24", "/proc/self/fd/0", [], ("argv", ["/proc/self/fd/0"]), None, {}),
    ("r25", "/dev/fd/0", [], ("argv", ["/dev/fd/0"]), None, {}),
    ("r26", "/dev/stdin", [], ("argv", ["/dev/stdin"]), None, {}),
    ("r27", "/dev/null", [], ("argv", ["/dev/null"]), None, {}),
    ("r28", "/dev/shm/x (cost: refused)", [], ("argv", ["/dev/shm/x"]), None, {}),
    ("r29", "/proc/1/root/bin/sh", [], ("argv", ["/proc/1/root/bin/sh"]), None, {}),
    ("r30", "/dev//fd/0 and /dev/./fd/0", [], ("argv", ["/dev/./fd/0"]), None, {}),
    (
        "r31",
        "link to /proc/self/cwd/<link>",
        [("sub/lnk", "link", "/proc/self/cwd/mysh"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./lnk"]),
        None,
        {"core": True},
    ),
    (
        "r32",
        "dir link to /proc/self/cwd",
        [("sub/pdir", "link", "/proc/self/cwd"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["pdir/mysh"]),
        None,
        {},
    ),
    (
        "r33",
        "dir link to /dev then fd/0",
        [("sub/dd", "link", "/dev")],
        ("argv", ["dd/fd/0"]),
        None,
        {},
    ),
    (
        "r34",
        "chain ending in /dev/stdin",
        [("sub/l1", "link", "l2"), ("sub/l2", "link", "/dev/stdin")],
        ("argv", ["./l1"]),
        None,
        {},
    ),
    (
        "r35",
        "link to /proc/self/exe",
        [("sub/l1", "link", "/proc/self/exe")],
        ("argv", ["./l1"]),
        None,
        {},
    ),
    (
        "r36",
        "link target climbs with .. to the root, then /proc/self/cwd/<link>",
        [
            ("sub/lnk", "link", "../" * 30 + "proc/self/cwd/mysh"),
            ("sub/mysh", "link", "../bin/bash"),
        ],
        ("argv", ["./lnk"]),
        None,
        {"core": True},
    ),
    (
        "r37",
        "dir link up to / (all ..), then proc/self/cwd/<link>",
        [("sub/up", "link", "../" * 30), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["up/proc/self/cwd/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r38",
        "D1 inside a link TARGET: lnk/../mysh with lnk -> /proc/self/cwd",
        [
            ("sub/lnk", "link", "/proc/self/cwd"),
            ("sub/m2", "link", "lnk/../mysh"),
            ("mysh", "link", "bin/bash"),
        ],
        ("argv", ["./m2"]),
        None,
        {"core": True},
    ),
    (
        "r39",
        "link target climbs with .. to /dev/fd",
        [("sub/dd", "link", "../" * 30 + "dev/fd")],
        ("argv", ["dd/0"]),
        None,
        {"core": True},
    ),
    (
        "r40",
        "relative PATH entry",
        [("sub/bin/mysh", "link", "{B}/bin/bash")],
        ("argv", ["mysh"]),
        "bin",
        {"core": True},
    ),
    (
        "r41",
        "empty PATH entry",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["mysh"]),
        ":{B}/none",
        {},
    ),
    ("r42", "PATH entry .", [("sub/mysh", "link", "../bin/bash")], ("argv", ["mysh"]), ".", {}),
    (
        "r43",
        "PATH entry /proc/self/cwd",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["mysh"]),
        "/proc/self/cwd",
        {"core": True},
    ),
    (
        "r44",
        "directory link in PATH",
        [("sub/pd", "link", "../bin"), ("bin/mysh", "link", "bash")],
        ("argv", ["mysh"]),
        "pd",
        {"core": True},
    ),
    (
        "r45",
        "PATH entry that is a link to /proc/self/cwd",
        [("sub/pc", "link", "/proc/self/cwd"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["mysh"]),
        "pc",
        {},
    ),
    (
        "r46",
        "PATH entry with ..",
        [("bin/mysh", "link", "bash")],
        ("argv", ["mysh"]),
        "../bin",
        {"skip3": True},
    ),
    (
        "r47",
        "first PATH hit is the shell link",
        [("d1/mysh", "link", "{B}/bin/bash"), ("d2/mysh", "file", "#!/bin/sh\nexit 0\n")],
        ("argv", ["mysh"]),
        "{B}/d1:{B}/d2",
        {},
    ),
    (
        "r48",
        "PATH hit is a link into /proc/self/cwd (relative entry; the runner's cwd lacks the target)",
        [("sub/bin2/tool", "link", "/proc/self/cwd/mysh"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["tool"]),
        "bin2",
        {"core": True},
    ),
    (
        "r49",
        "PATH hit is a link into /proc/self/cwd (absolute entry)",
        [("d1/tool", "link", "/proc/self/cwd/mysh"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["tool"]),
        "{B}/d1",
        {"core": True},
    ),
    (
        "r50",
        ".//mysh and ./././mysh",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./././mysh"]),
        None,
        {},
    ),
    (
        "r51",
        "trailing slash",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh/"]),
        None,
        {},
    ),
    ("r52", "case: MYSH", [("sub/MYSH", "link", "../bin/bash")], ("argv", ["./MYSH"]), None, {}),
    (
        "r53",
        "symlinked gate cwd",
        [("lnkdir", "link", "sub"), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh"]),
        None,
        {"cwd": "lnkdir", "skip3": True},
    ),
    (
        "r54",
        "symlinked --root",
        [("rootlink", "link", "."), ("sub/mysh", "link", "../bin/bash")],
        ("argv", ["./mysh"]),
        None,
        {"rootarg": "{B}/rootlink"},
    ),
    (
        "r55",
        "link in a subfolder of the gate cwd",
        [("sub/x/mysh", "link", "../../bin/bash")],
        ("argv", ["./x/mysh"]),
        None,
        {},
    ),
    ("r58", "//dev/null (QA Q26: the double-slash form)", [], ("argv", ["//dev/null"]), None, {}),
    (
        "r59",
        "//proc/1/cwd/x (another pid, double slash)",
        [],
        ("argv", ["//proc/1/cwd/x"]),
        None,
        {},
    ),
    (
        "r57",
        "links first, middle and last in one word (a1/a2/mysh)",
        [
            ("sub/a1", "link", "x"),
            ("sub/x/a2", "link", "../../bin"),
            ("bin/mysh", "link", "bash"),
        ],
        ("argv", ["a1/a2/mysh"]),
        None,
        {"core": True},
    ),
    (
        "r56",
        "LIMIT: env handed a link to a shell",
        [("sub/mysh", "link", "../bin/bash")],
        ("argv", ["env", "./mysh"]),
        None,
        {
            "limit": "the wrapper rule compares argument names, not what a link points at: not detected"
        },
    ),
    (
        "l01",
        "LIMIT: a copy of a shell",
        [("sub/tool", "copy", "")],
        ("argv", ["./tool"]),
        None,
        {"limit": "a copy has its own name and content: not detected"},
    ),
    (
        "l02",
        "LIMIT: a hard link of a shell",
        [("sub/tool", "hard", "")],
        ("argv", ["./tool"]),
        None,
        {"limit": "a hard link is a second name for the same inode: not detected"},
    ),
    (
        "l03",
        "LIMIT: a symlink to a wrapper",
        [("sub/w", "link", "/usr/bin/env"), ("bin/mysh", "link", "bash")],
        ("argv", ["./w", "{B}/bin/mysh"]),
        None,
        {"limit": "a link to a wrapper is not a wrapper name: not detected"},
    ),
    (
        "l04",
        "LIMIT: earlier PATH file exec skips (no shebang)",
        [("d1/mysh", "file", "plain data\n"), ("d2/mysh", "link", "{B}/bin/bash")],
        ("argv", ["mysh"]),
        "{B}/d1:{B}/d2",
        {"limit": "exec skips d1/mysh (ENOEXEC) and runs d2/mysh; the plan stops at d1"},
    ),
    (
        "l05",
        "LIMIT: a shell not in the 14 names",
        [("sub/ksh93", "fake", "")],
        ("argv", ["./ksh93"]),
        None,
        {"limit": "the list has 14 names; ksh93 is not one"},
    ),
]


def build(base: Path, files: list) -> Path:
    rel = str(base).lstrip("/")
    (base / "bin").mkdir()
    (base / "sub").mkdir()
    (base / "a" / "b").mkdir(parents=True)
    (base / "bin" / "bash").write_text(FAKE)
    (base / "bin" / "bash").chmod(0o755)

    def subst(text: str) -> str:
        return (
            text.replace("{B}", str(base)).replace("{S}", str(base / "sub")).replace("{Brel}", rel)
        )

    for relpath, kind, arg in files:
        p = base / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        if kind == "fake":
            p.write_text(FAKE)
            p.chmod(0o755)
        elif kind == "file":
            p.write_text(subst(arg))
            p.chmod(0o755)
        elif kind == "link":
            p.symlink_to(subst(arg))
        elif kind == "copy":
            shutil.copy(base / "bin" / "bash", p)
        elif kind == "hard":
            os.link(base / "bin" / "bash", p)
        elif kind == "dir":
            p.mkdir()
    return base


def run_row(
    row: tuple, mode: str, src: Path, py: str, scratch: Path | None = None, strace: bool = False
) -> tuple[str, str]:
    """Returns (verdict, note): n/a, MARK (the child ran the shell), refused, or other."""
    _rid, _desc, files, gate, path, extra = row
    if mode == "M3" and extra.get("skip3"):
        return "n/a", ""
    base = Path(tempfile.mkdtemp(prefix="gm_", dir=scratch)).resolve()
    try:
        build(base, files)

        def subst(text: str) -> str:
            return text.replace("{B}", str(base)).replace("{S}", str(base / "sub"))

        entry: dict = {"id": "g"}
        if gate[0] == "argv":
            entry["argv"] = [subst(w) for w in gate[1]]
        else:
            entry["command"] = subst(gate[1])
        entry["cwd"] = "." if mode == "M3" else extra.get("cwd", "sub")
        gf = base / "gates.json"
        gf.write_text(json.dumps({"schema_version": 1, "gates": [entry]}))
        root = str(base / "sub") if mode == "M3" else subst(extra.get("rootarg", str(base)))
        runner = base / "sub" if mode == "M2" else base / "a" / "b"
        env = {**os.environ, "PYTHONPATH": str(src)}
        if path is not None:
            env["PATH"] = subst(path)
        cmd = [py, "-B", "-m", "master_finhub.evals.gates", str(gf), "--root", root]
        if strace:
            cmd = [
                STRACE,
                "-f",
                "-qq",
                "-e",
                "trace=execve",
                "-o",
                str(base / "strace.log"),
            ] + cmd
        done = subprocess.run(
            cmd, cwd=runner, env=env, capture_output=True, text=True, timeout=120, check=False
        )
        try:
            status = json.loads(done.stdout)["gates"][0]["status"]
        except (ValueError, KeyError, IndexError):
            status = "?"
        note = f"exit={done.returncode} status={status}"
        if strace:
            lines = (base / "strace.log").read_text().splitlines()
            ran = [
                ln
                for ln in lines
                if "execve(" in ln
                and any(n in ln for n in ("bash", "mysh", "tool", "ksh93", '/w"', "lnk", "/m2"))
            ]
            note += f" gate-execs={len(ran)}"
        if list(base.rglob("MARK")):
            return "MARK", note
        if done.returncode == 2 and status == "policy-error":
            return "refused", note
        return "other", note + " " + done.stderr.strip()[-80:]
    finally:
        shutil.rmtree(base, ignore_errors=True)
