"""Proof for OR-D1: scripts/candidate_id.py and the verdict-binding rules C1-C8 (quality-gates.md 3-7).

Each check below is a behaviour of the script or a phrase of the prose; checks run against the real
files (no problems) and against every mutant in MUTANTS and PROSE_MUTANTS (the named check must fail).
Binding a verdict to one exact commit and refusing a mismatch is adapted from
references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0); a run that fails when the commit
moves under it, from references/openrig/scripts/gate-lane.mjs:151-154 (Apache-2.0).
"""

# adapted from references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0)
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/candidate_id.py"
PROSE = {
    "qg": "skills/finhub-harness/references/quality-gates.md",
    "qag": "skills/finhub-harness/references/qa-agent-guide.md",
    "tmpl": "skills/finhub-harness/references/orchestrator-template.md",
    "skill": "skills/finhub-harness/SKILL.md",
    "bqa": ".claude/agents/boundary-qa.md",
    "judge": ".claude/agents/adversarial-risk-judge.md",
    "vs": ".claude/skills/adversarial-audit/references/verdict-schema.md",
    "aa": ".claude/skills/adversarial-audit/SKILL.md",
    "al": ".claude/skills/runtime-slice-design/references/authority-list.md",
    "orch": ".claude/skills/master-finhub-orchestrator/SKILL.md",
}
BLOCK_SHA = (
    "067918a36acc80c749037332240a990930cde75392a5a2281bd410437514d221"  # pasted Delegating block
)
HANGUL = ((0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F))
SHAPE = re.compile(r"^(?:git:(?:[0-9a-f]{12}|unborn)\+[0-9a-f]{16}|files:[0-9a-f]{16})$")


def load(path: Path = SCRIPT) -> ModuleType:
    """Import the script without leaving bytecode, so a mutant is never stale."""
    name = f"cid_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # a dataclass looks its own module up by name
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


@contextlib.contextmanager
def iso(tmp: Path) -> Iterator[None]:
    """A home of its own and no GIT_* variables, so the machine's git config never leaks in."""
    saved = dict(os.environ)
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    for k in [k for k in os.environ if k.startswith("GIT_")]:
        del os.environ[k]
    os.environ.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1")
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def g(cwd: Path, *a: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1")
    r = subprocess.run(
        [
            "git",
            "-c",
            "user.name=qa",
            "-c",
            "user.email=qa@example.test",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(cwd),
            *a,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return r.stdout


def repo(tmp: Path, name: str, files: dict[str, bytes], commit: bool = True) -> Path:
    r = tmp / name
    r.mkdir(parents=True)
    g(r, "init", "-q", "-b", "main")
    for rel, data in files.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_bytes(data)
    if commit:
        g(r, "add", "-A")
        g(r, "commit", "-q", "-m", "c")
    return r


def run(mod: ModuleType, *args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main(list(args))
    return rc, buf.getvalue()


def tok(out: str) -> str:
    m = re.search(r"^CANDIDATE: (\S+)", out, re.MULTILINE)
    assert m, out
    return m.group(1)


def line(out: str) -> str:
    m = re.search(r"^CANDIDATE: (.*)$", out, re.MULTILINE)
    assert m, out
    return m.group(0)


def verdict(tmp: Path, name: str, id_out: str, first: str = "RESULT: PASS", nl: str = "\n") -> Path:
    p = tmp / name
    p.write_bytes(nl.join([first, line(id_out), "CARRIED: -", "", "body"]).encode())
    return p


def cid(mod: ModuleType, root: Path, *extra: str) -> str:
    rc, out = run(mod, "id", "--root", str(root), *extra)
    assert rc == 0, out
    return tok(out)


def chk(mod: ModuleType, rec: Path | str, root: Path, *extra: str) -> tuple[int, str]:
    return run(mod, "check", str(rec), "--root", str(root), *extra)


# ---------------------------------------------------------------- checks on the script


def c_stable(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    rc, out = run(mod, "id", "--root", str(r))
    assert rc == 0 and SHAPE.match(tok(out)), out
    assert cid(mod, r) == tok(out), "same tree, same id"
    v = verdict(tmp, "v.md", out)
    rc, o = chk(mod, v, r)
    assert rc == 0 and "STATE: current" in o, o
    g(tmp, "clone", "-q", str(r), str(tmp / "r2"))
    assert cid(mod, tmp / "r2") == tok(out), "a clone of the same commit has the same id"


def c_change(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    rc, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    (r / "a").write_bytes(b"1 changed\n")
    rc, o = chk(mod, v, r)
    assert rc == 3 and "STATE: STALE" in o and "the files differ" in o, o
    assert "the commit moved" not in o, o


def c_untracked(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    rc, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    (r / "new.py").write_bytes(b"x = 1\n")
    rc, o = chk(mod, v, r)
    assert rc == 3, o


def c_ignored(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", ".gitignore": b"*.log\n"})
    rc, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    (r / "x.log").write_bytes(b"noise\n")
    rc, o = chk(mod, v, r)
    assert rc == 0, "an ignored file is outside the id: " + o
    (r / "x.log").write_bytes(b"other noise\n")
    assert chk(mod, v, r)[0] == 0


def c_globalignore(mod: ModuleType, tmp: Path) -> None:
    home = Path(os.environ["HOME"])
    (home / ".gi").write_text("*.txt\n")
    (home / ".gitconfig").write_text(f"[core]\n\texcludesFile = {home}/.gi\n")
    r = repo(tmp, "r", {"a": b"1\n"})
    rc, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    (r / "new.txt").write_bytes(b"hidden only on this machine\n")
    rc, o = chk(mod, v, r)
    assert rc == 3, "the user's own ignore file must not hide a file from the id: " + o


def c_deleted(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    base = cid(mod, r)
    (r / "a").unlink()
    gone = cid(mod, r)
    (r / "a").write_bytes(b"")
    empty = cid(mod, r)
    assert len({base, gone, empty}) == 3, (base, gone, empty)


def c_exec(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"run.sh": b"echo\n"})
    base = cid(mod, r)
    (r / "run.sh").chmod(0o755)
    assert cid(mod, r) != base, "the executable bit is part of the tree"


def c_swap(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"AAA\n", "b": b"BBB\n"})
    base = cid(mod, r)
    (r / "a").write_bytes(b"BBB\n")
    (r / "b").write_bytes(b"AAA\n")
    swapped = cid(mod, r)
    (r / "a").write_bytes(b"AAA\n")
    (r / "b").write_bytes(b"BBB\n")
    (r / "a").rename(r / "c")
    renamed = cid(mod, r)
    assert len({base, swapped, renamed}) == 3, (base, swapped, renamed)


def c_collision(mod: ModuleType, tmp: Path) -> None:
    shapes: list[tuple[dict[str, bytes], dict[str, str]]] = [
        ({"a": b"xb"}, {}),
        ({"ax": b"b"}, {}),
        ({"a": b"1", "b": b"2"}, {}),
        ({"a": b"12"}, {}),
        ({}, {"a": "lb"}),  # path a, kind l, text lb ...
        ({}, {"al": "b"}),  # ... is the same run of characters as path al, kind l, text b
        ({}, {"a\nb": "c"}),
        ({}, {"a": "b\nc"}),
    ]
    seen = set()
    for i, (files, links) in enumerate(shapes):
        d = tmp / f"d{i}"
        d.mkdir()
        for rel, data in files.items():
            (d / rel).write_bytes(data)
        for rel, target in links.items():
            os.symlink(target, d / rel)
        seen.add(cid(mod, d, "--paths", "."))
    assert len(seen) == len(shapes), "two different trees collided in the encoding"


def c_symlink(mod: ModuleType, tmp: Path) -> None:
    out_dir = tmp / "outside"
    out_dir.mkdir()
    (out_dir / "t.txt").write_bytes(b"outside one\n")
    (out_dir / "f").write_bytes(b"outside f\n")
    r = repo(tmp, "r", {"a": b"1\n", "d/f": b"inside\n"})
    os.symlink("t1", r / "ln")
    base1 = cid(mod, r)
    (r / "ln").unlink()
    os.symlink("t2", r / "ln")
    assert cid(mod, r) != base1, "symlink text is part of the id"
    (r / "ln").unlink()
    os.symlink(out_dir / "t.txt", r / "ln")
    a = cid(mod, r)
    (out_dir / "t.txt").write_bytes(b"outside two, changed\n")
    assert cid(mod, r) == a, "the target of a symlink is never read"
    shutil.rmtree(r / "d")
    os.symlink(out_dir, r / "d")
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "symlink" in o, o
    first = tok(o)
    (out_dir / "f").write_bytes(b"outside f, changed\n")
    rc, o = run(mod, "id", "--root", str(r))
    assert tok(o) == first and rc == 3, "a file behind a symlinked directory was read"


def c_submodule(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    sha1, sha2 = "1" * 40, "2" * 40
    g(r, "update-index", "--add", "--cacheinfo", f"160000,{sha1},sub")
    (r / "sub").mkdir()
    rc, out = run(mod, "id", "--root", str(r))
    assert rc == 0, out
    t1 = tok(out)
    (r / "sub" / "inside.txt").write_bytes(b"not covered\n")
    assert cid(mod, r) == t1, "the files of a submodule are outside the id"
    g(r, "update-index", "--add", "--cacheinfo", f"160000,{sha2},sub")
    assert cid(mod, r) != t1, "the pinned commit of a submodule is part of the id"


def c_unreadable(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    rc, good = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", good)
    real = mod.os.open

    def deny(path: str, *a: object, **k: object) -> int:
        if str(path).endswith("/b"):
            raise PermissionError(13, "Permission denied")
        return real(path, *a, **k)  # type: ignore[no-any-return]

    with mock.patch.object(mod.os, "open", side_effect=deny):
        rc, o = run(mod, "id", "--root", str(r))
        assert rc == 3 and "partial=1" in o and "SKIPPED: b" in o, o
        rc, o2 = chk(mod, v, r)
        assert rc == 3 and "uncovered" in o2, o2
    bad = tmp / "bad.md"
    bad.write_text(line(o) + "\n")
    assert chk(mod, bad, r)[0] == 3, "a verdict recorded with an uncovered file never licenses"


def c_huge(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    (r / "big.bin").write_bytes(b"x" * 5000)
    rc, o = run(mod, "id", "--root", str(r), "--max-bytes", "1000")
    assert rc == 3 and "SKIPPED: big.bin" in o and "limit" in o, o
    sparse = r / "sparse.bin"
    with open(sparse, "wb") as f:
        f.truncate(300 * 1024 * 1024)
    (r / "big.bin").unlink()
    t0 = time.time()
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "SKIPPED: sparse.bin" in o, o
    assert time.time() - t0 < 20, "an over-limit file must not be read"
    assert "grew while hashing" not in o, "the size is checked before the file is opened"


def c_crlf(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"one\ntwo\n"})
    lf = cid(mod, r)
    (r / "a").write_bytes(b"one\r\ntwo\r\n")
    crlf = cid(mod, r)
    (r / "a").write_bytes(b"\xef\xbb\xbfone\ntwo\n")
    bom = cid(mod, r)
    assert len({lf, crlf, bom}) == 3, "the id is byte exact"
    (r / "a").write_bytes(b"one\ntwo\n")
    rc, out = run(mod, "id", "--root", str(r))
    v = tmp / "v.md"
    body = line(out) + "\r\nCARRIED: -\r\n"
    v.write_bytes(b"\xef\xbb\xbf" + body.encode())
    rc, o = chk(mod, v, r)
    assert rc == 0, "a verdict saved with a BOM and CRLF must still parse: " + o


def c_empty(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "emptydir"
    d.mkdir()
    rc, o = run(mod, "id", "--root", str(d), "--paths", ".")
    assert rc == 3 and "empty candidate" in o, o
    rc, o2 = chk(mod, line(o), d)
    assert rc == 3 and "cannot be shown to match" in o2, (
        "a verdict over nothing proves nothing: " + o2
    )
    r = repo(tmp, "r0", {}, commit=False)
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "empty candidate" in o, o
    (r / "a").write_bytes(b"1\n")
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 0 and tok(o).startswith("git:unborn+"), o
    # the id of an empty diff: a clean tree is a candidate like any other
    c = repo(tmp, "clean", {"a": b"1\n"})
    rc, o = run(mod, "id", "--root", str(c))
    assert rc == 0 and g(c, "status", "--porcelain") == ""


def c_detached(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    (r / "a").write_bytes(b"2\n")
    g(r, "commit", "-aq", "-m", "two")
    on_branch = cid(mod, r)
    g(r, "checkout", "-q", "--detach", "HEAD")
    assert cid(mod, r) == on_branch, "the branch name is not part of the id"
    g(r, "checkout", "-q", "--detach", "HEAD~1")
    old = cid(mod, r)
    assert old.split("+")[0] != on_branch.split("+")[0] and old != on_branch


def c_nongit(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "plain"
    d.mkdir()
    (d / "f.md").write_bytes(b"text\n")
    rc, o = run(mod, "id", "--root", str(d))
    assert rc == 2, o
    rc, o = run(mod, "id", "--root", str(d), "--paths", "f.md")
    assert rc == 0 and tok(o).startswith("files:"), o
    v = verdict(tmp, "v.md", o, first="TOTALS: UPHELD 1 / REJECTED 0 / UNVERIFIED 0 — round 1/3")
    assert chk(mod, v, d)[0] == 0
    (d / "f.md").write_bytes(b"text edited\n")
    assert chk(mod, v, d)[0] == 3
    gitrec = tmp / "g.md"
    gitrec.write_text("RESULT: PASS\nCANDIDATE: git:1a2b3c4d5e6f+0f1e2d3c4b5a6978 n=3 excludes=-\n")
    assert chk(mod, gitrec, d)[0] == 2, "a git id cannot be checked where there is no git"


def c_midrun(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    real = mod._sha_file
    calls = {"n": 0}

    def appear(*a: object, **k: object) -> tuple[str, str]:
        calls["n"] += 1
        if calls["n"] == 1:
            (r / "late.txt").write_bytes(b"appeared while hashing\n")
        return real(*a, **k)  # type: ignore[no-any-return]

    with mock.patch.object(mod, "_sha_file", side_effect=appear):
        rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "changed while" in o, o
    (r / "late.txt").unlink()
    heads = iter(["a" * 12, "b" * 12, "b" * 12, "b" * 12])
    with mock.patch.object(mod, "_head", side_effect=lambda *_: next(heads)):
        rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "changed while" in o, "a commit that moved while hashing: " + o
    real_fstat, seen = mod.os.fstat, {"n": 0}

    def drift(fd: int) -> object:
        st = real_fstat(fd)
        seen["n"] += 1
        if seen["n"] % 2 == 0:
            return SimpleNamespace(
                st_mode=st.st_mode,
                st_ino=st.st_ino,
                st_size=st.st_size,
                st_mtime_ns=st.st_mtime_ns + 1,
            )
        return st

    with mock.patch.object(mod.os, "fstat", side_effect=drift):
        rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "changed while" in o, "a file that changed while it was read: " + o


def c_emptydiff(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    base = cid(mod, r)
    for f in ("a", "b"):
        os.utime(r / f, (1, 1))
    assert cid(mod, r) == base, "file times are not part of the id"
    (r / "a").write_bytes(b"changed\n")
    assert cid(mod, r) != base
    (r / "a").write_bytes(b"1\n")
    assert cid(mod, r) == base, "a change that is undone leaves the id as it was"


def c_headmoved(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    (r / "a").write_bytes(b"2\n")
    rc, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    assert chk(mod, v, r)[0] == 0
    g(r, "commit", "-aq", "-m", "the judged tree")
    rc, o = chk(mod, v, r)
    assert rc == 3 and "the commit moved" in o and "the files differ" not in o, o
    rc, o = chk(mod, v, r, "--tree-only")
    assert rc == 0, "the commit holds the judged tree: " + o
    (r / "a").write_bytes(b"3\n")
    assert chk(mod, v, r, "--tree-only")[0] == 3, "tree-only still sees a content change"
    g(r, "commit", "-aq", "--allow-empty", "-m", "x")
    (r / "a").write_bytes(b"2\n")
    assert chk(mod, v, r, "--tree-only")[0] == 0
    assert chk(mod, v, r)[0] == 3


def c_record(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    rc, out = run(mod, "id", "--root", str(r))
    ln = line(out)
    f = tmp / "f.md"
    f.write_text("RESULT: PASS\n" + ln + "\n")
    assert chk(mod, f, r)[0] == 0
    assert chk(mod, ln, r)[0] == 0, "a CANDIDATE line can be passed directly"
    f.write_text("\n".join(["x"] * 8 + [ln]) + "\n")
    rc, o = chk(mod, f, r)
    assert rc == 3 and "unbound" in o, "a line below the header is not a binding: " + o
    f.write_text("RESULT: PASS\nbody only\n")
    assert chk(mod, f, r)[0] == 3
    assert chk(mod, tmp / "missing.md", r)[0] == 2
    f.write_text("RESULT: PASS\nCANDIDATE: unverified (no shell)\n")
    rc, o = chk(mod, f, r)
    assert rc == 3 and "recorded as unverified" in o, o
    f.write_text("RESULT: PASS\nCANDIDATE: git:zzzz+123\n")
    rc, o = chk(mod, f, r)
    assert rc == 3 and "malformed id" in o, o
    f.write_text("RESULT: PASS\nCANDIDATE: files:0f1e2d3c4b5a6978 n=1 excludes=-\n")
    rc, o = chk(mod, f, r)
    assert rc == 3 and "paths" in o, o


def c_excludes(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    _, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    assert "excludes=_workspace/" in out
    (r / "_workspace").mkdir()
    (r / "_workspace" / "03_boundary-qa_x.md").write_bytes(b"RESULT: PASS\n")
    assert chk(mod, v, r)[0] == 0, "the team's own reports must not move the id they carry"
    (r / "_workspace2").mkdir()
    (r / "_workspace2" / "x").write_bytes(b"x\n")
    assert chk(mod, v, r)[0] == 3, "a sibling that shares a prefix is not excluded"
    (r / "_workspace2" / "x").unlink()
    (r / "_workspace2").rmdir()
    plain = cid(mod, r)
    assert cid(mod, r, "--exclude", "docs") != plain, "the exclude list is bound into the id"


def c_usage(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "sub/b": b"2\n"})
    cases = [
        ("bogus",),
        ("id", "--root", str(r), "--paths", "../x"),
        ("id", "--root", str(r), "--paths", ".."),
        ("id", "--root", str(r), "--paths", "/etc/passwd"),
        ("id", "--root", str(r), "--paths", "nothere"),
        ("id", "--root", str(r / "sub")),
        ("id", "--root", str(tmp / "absent")),
        ("id", "--root", str(r), "--max-bytes", "many"),
        ("check",),
        ("check", str(tmp / "nofile.md"), "--root", str(r)),
    ]
    for argv in cases:
        rc, o = run(mod, *argv)
        assert rc == 2, (argv, rc, o)
    # every exit is 0, 2 or 3: the meaning state_ledger.py gives them
    assert {run(mod, "id", "--root", str(r))[0], chk(mod, "RESULT: PASS", r)[0]} <= {0, 2, 3}


def c_files(mod: ModuleType, tmp: Path) -> None:
    a, b = tmp / "a", tmp / "b"
    for d in (a, b):
        (d / "docs").mkdir(parents=True)
        (d / "docs" / "p.patch").write_bytes(b"--- a\n+++ b\n")
        (d / "skip").mkdir()
        (d / "skip" / "x").write_bytes(b"x")
    t_a = cid(mod, a, "--paths", "docs", "--exclude", "skip")
    assert cid(mod, b, "--paths", "docs", "--exclude", "skip") == t_a, "same bytes, other root"
    (b / "docs" / "p.patch").write_bytes(b"--- a\n+++ c\n")
    assert cid(mod, b, "--paths", "docs") != t_a
    os.symlink("/etc", a / "docs" / "etc")
    rc, o = run(mod, "id", "--root", str(a), "--paths", "docs")
    assert rc == 0 and "n=2" in o, "a symlinked directory is one entry and is not walked: " + o
    rc, o = run(mod, "id", "--root", str(a), "--paths", "docs/p.patch", "docs/p.patch")
    assert rc == 0 and "n=1" in o, "a path named twice counts once"


def c_linear(mod: ModuleType, tmp: Path) -> None:
    counts = []
    for n in (5, 200):
        r = repo(tmp, f"r{n}", {f"f{i}": f"{i}\n".encode() for i in range(n)})
        real = mod._git_raw
        calls: list[tuple[str, ...]] = []

        def counted(*a: str, calls: list[tuple[str, ...]] = calls, real: Any = real) -> Any:
            calls.append(a)
            return real(*a)

        with mock.patch.object(mod, "_git_raw", side_effect=counted):
            assert run(mod, "id", "--root", str(r))[0] == 0
        counts.append(len(calls))
    assert counts[0] == counts[1] <= 8, f"git is called a fixed number of times, got {counts}"


def c_nonet(mod: ModuleType, tmp: Path) -> None:
    src = Path(str(mod.__file__)).read_text()
    imports = set(re.findall(r"^(?:from|import) ([\w.]+)", src, re.MULTILINE))
    assert not imports & {
        "socket",
        "urllib.request",
        "http",
        "http.client",
        "ssl",
        "requests",
        "ftplib",
    }, imports
    assert "subprocess" in imports and "git" in src


def c_env(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    base = cid(mod, r)
    with mock.patch.dict(
        os.environ,
        {"GIT_DIR": str(tmp / "nowhere"), "GIT_INDEX_FILE": str(tmp / "idx"), "GIT_WORK_TREE": "/"},
    ):
        assert cid(mod, r) == base, "GIT_* variables must not redirect the listing"


def c_output(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    _, o = run(mod, "id", "--root", str(r))
    assert re.search(
        r"^CANDIDATE: git:[0-9a-f]{12}\+[0-9a-f]{16} n=1 excludes=_workspace/$", o, re.MULTILINE
    ), o
    assert (
        "COVERS:" in o
        and "NOT-COVERED:" in o
        and "ignored files" in o
        and "submodule contents" in o
    )
    assert "not tamper evidence" in o


def c_unmerged(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"base\n"})
    g(r, "checkout", "-q", "-b", "side")
    (r / "a").write_bytes(b"side\n")
    g(r, "commit", "-aq", "-m", "side")
    g(r, "checkout", "-q", "main")
    (r / "a").write_bytes(b"main\n")
    g(r, "commit", "-aq", "-m", "main")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=qa",
            "-c",
            "user.email=qa@example.test",
            "-C",
            str(r),
            "merge",
            "side",
        ],
        check=False,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
    )
    assert "UU" in g(r, "status", "--porcelain")
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 0 and " n=1 " in o, (
        "an unmerged path is listed once and read from the worktree: " + o
    )


def c_nested(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    inner = r / "inner"
    inner.mkdir()
    g(inner, "init", "-q")
    (inner / "z").write_bytes(b"z\n")
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "SKIPPED: inner/" in o, o


def c_fifo(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    d.mkdir()
    (d / "ok").write_bytes(b"ok\n")
    os.mkfifo(d / "pipe")
    box: list[tuple[int, str]] = []
    t = threading.Thread(
        target=lambda: box.append(run(mod, "id", "--root", str(d), "--paths", ".")), daemon=True
    )
    t.start()
    t.join(10)
    if not box:  # release a reader that a mutant left blocked in open()
        with contextlib.suppress(OSError):
            os.close(os.open(d / "pipe", os.O_WRONLY | os.O_NONBLOCK))
    assert box, "a FIFO must never be opened for reading"
    assert box[0][0] == 3 and "SKIPPED: pipe" in box[0][1], box[0]


def c_perm_dir(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "f").write_bytes(b"x\n")
    (d / "ok").write_bytes(b"ok\n")
    real = os.scandir

    def deny(p: Any = ".") -> Any:
        if str(p).endswith("/sub"):
            raise PermissionError(13, "Permission denied", str(p))
        return real(p)

    with mock.patch.object(mod.os, "scandir", side_effect=deny):
        rc, o = run(mod, "id", "--root", str(d), "--paths", ".")
    assert rc == 3 and "unreadable directory" in o, o


def c_dirswap(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    (r / "a").unlink()
    (r / "a").mkdir()
    (r / "a" / "x").write_bytes(b"x\n")
    rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "SKIPPED: a (a directory" in o, (
        "a tracked file replaced by a directory: " + o
    )


def c_exclfile(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "b": b"2\n"})
    base = cid(mod, r, "--exclude", "a")
    (r / "a").write_bytes(b"changed\n")
    assert cid(mod, r, "--exclude", "a") == base, "a single file can be excluded by name"
    (r / "b").write_bytes(b"changed\n")
    assert cid(mod, r, "--exclude", "a") != base


def c_exclists(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    d.mkdir()
    (d / "f.md").write_bytes(b"text\n")
    two = cid(mod, d, "--paths", "f.md", "--exclude", "a", "--exclude", "b")
    one = cid(mod, d, "--paths", "f.md", "--exclude", "axb")
    assert two != one, "the exclude list a,b is not the exclude list axb"
    assert (
        cid(mod, d, "--paths", "f.md", "--exclude", "b", "--exclude", "a") == two
    ), "order is free"


def c_gone(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    d.mkdir()
    (d / "design.md").write_bytes(b"text\n")
    rc, o = run(mod, "id", "--root", str(d), "--paths", "design.md")
    v = verdict(tmp, "v.md", o)
    (d / "design.md").unlink()
    rc, o = chk(mod, v, d)
    assert rc == 3 and "STALE" in o, "a judged file that vanished is stale, not a usage error: " + o


def c_addstable(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n", "c": b"3\n"})
    (r / "b").write_bytes(b"2\n")
    before = cid(mod, r)
    g(r, "add", "b")
    assert cid(mod, r) == before, "staging a file does not change the id"


def c_multipath(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    d.mkdir()
    (d / "a b.md").write_bytes(b"design\n")
    (d / "p,q.patch").write_bytes(b"patch\n")
    rc, o = run(mod, "id", "--root", str(d), "--paths", "a b.md", "p,q.patch")
    assert rc == 0 and "n=2" in o, o
    v = verdict(tmp, "v.md", o)
    rc, o2 = chk(mod, v, d)
    assert rc == 0 and "STATE: current" in o2, "a two-path id round-trips through check: " + o2
    (d / "p,q.patch").write_bytes(b"patch edited\n")
    assert chk(mod, v, d)[0] == 3, "an edit of the second path alone is seen"


def c_forged(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    d.mkdir()
    (d / "a").write_bytes(b"x\n")
    forged = "CANDIDATE: files:0123456789abcdef n=1 excludes=- paths=a%00b"
    rc, o = chk(mod, forged, d)
    assert rc == 2 and "relative" in o, "a NUL in a recorded path is a usage error: " + o


def c_capedge(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    (r / "five").write_bytes(b"12345")
    assert (
        run(mod, "id", "--root", str(r), "--max-bytes", "5")[0] == 0
    ), "a file of exactly the limit"
    rc, o = run(mod, "id", "--root", str(r), "--max-bytes", "4")
    assert rc == 3 and "SKIPPED: five" in o, o


def c_late(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"first\n", "b": b"2\n", "c": b"3\n"})
    real = mod._sha_file
    calls = {"n": 0}

    def edit_hashed(*a: object, **k: object) -> tuple[str, str]:
        calls["n"] += 1
        if calls["n"] == 3:  # a and b are hashed already; the third file is being read
            (r / "a").write_bytes(b"edited after it was hashed\n")
        return real(*a, **k)  # type: ignore[no-any-return]

    with mock.patch.object(mod, "_sha_file", side_effect=edit_hashed):
        rc, o = run(mod, "id", "--root", str(r))
    assert rc == 3 and "changed while" in o, "a file edited after it was hashed: " + o


def c_exclline(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    rc, out = run(mod, "id", "--root", str(r))
    v = verdict(tmp, "v.md", out)
    rc, o = chk(mod, v, r)
    assert rc == 0 and "EXCLUDES: _workspace/\n" in o, o
    rc, out2 = run(mod, "id", "--root", str(r), "--exclude", "src")
    v2 = verdict(tmp, "v2.md", out2)
    rc, o = chk(mod, v2, r)
    assert rc == 0 and "EXCLUDES: _workspace/,src\n" in o, "the list check used is shown: " + o
    (r / "a").write_bytes(b"2\n")
    rc, o = chk(mod, v, r)
    assert rc == 3 and "EXCLUDES: _workspace/\n" in o, "a stale answer shows it too: " + o
    rc, o = chk(mod, v, r, "--max-bytes", "1")
    assert rc == 3 and "cannot be shown" in o and "EXCLUDES: _workspace/\n" in o, (
        "the refusal that names uncovered files shows it too: " + o
    )
    rc, out3 = run(mod, "id", "--root", str(r), "--exclude", ".claude-flow/")
    assert "excludes=_workspace/,.claude-flow\n" in out3, (
        "a trailing slash is normalised away: " + out3
    )
    rc, o = chk(mod, line(out3), r)
    assert rc == 0 and "EXCLUDES: _workspace/,.claude-flow\n" in o, (
        "a custom entry is printed without a slash, the default with one: " + o
    )


def _late(mod: ModuleType, tmp: Path, edit: Callable[[Path], None], moves: bool) -> None:
    """Run `id` and apply `edit` to the already hashed file `a` while the third file is read."""
    r = repo(tmp, "r", {"a": b"first\n", "b": b"2\n", "c": b"3\n"})
    real = mod._sha_file
    calls = {"n": 0}

    def hook(*a: object, **k: object) -> tuple[str, str]:
        calls["n"] += 1
        if calls["n"] == 3:
            edit(r / "a")
        return real(*a, **k)  # type: ignore[no-any-return]

    with mock.patch.object(mod, "_sha_file", side_effect=hook):
        rc, o = run(mod, "id", "--root", str(r))
    if moves:
        assert rc == 3 and "changed while" in o, "an edit of exactly this field is seen: " + o
    else:
        assert rc == 0, "control: an edit that changes nothing in the signature is fine: " + o


def _set_mtime(p: Path) -> None:
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 7_000_000_000))


def _set_size(p: Path) -> None:
    st = p.stat()
    p.write_bytes(b"first\nplus more bytes\n")
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))


def _set_inode(p: Path) -> None:
    st = p.stat()
    tmpf = p.with_name("a.swap")
    tmpf.write_bytes(p.read_bytes())
    tmpf.chmod(stat.S_IMODE(st.st_mode))
    os.utime(tmpf, ns=(st.st_atime_ns, st.st_mtime_ns))
    os.replace(tmpf, p)
    assert p.stat().st_ino != st.st_ino, "this file system reused the inode number"


def _set_mode(p: Path) -> None:
    p.chmod(stat.S_IMODE(p.stat().st_mode) ^ 0o020)


def c_sig_control(mod: ModuleType, tmp: Path) -> None:
    _late(mod, tmp, lambda p: None, moves=False)


def c_sig_mtime(mod: ModuleType, tmp: Path) -> None:
    _late(mod, tmp, _set_mtime, moves=True)


def c_sig_size(mod: ModuleType, tmp: Path) -> None:
    _late(mod, tmp, _set_size, moves=True)


def c_sig_inode(mod: ModuleType, tmp: Path) -> None:
    _late(mod, tmp, _set_inode, moves=True)


def c_sig_mode(mod: ModuleType, tmp: Path) -> None:
    _late(mod, tmp, _set_mode, moves=True)


def c_wsfiles(mod: ModuleType, tmp: Path) -> None:
    d = tmp / "d"
    (d / "_workspace").mkdir(parents=True)
    (d / "_workspace" / "d.md").write_bytes(b"design\n")
    rc, o = run(mod, "id", "--root", str(d), "--paths", "_workspace/d.md")
    assert rc == 0 and "n=1" in o, "a files id covers a design file under _workspace/: " + o
    v = verdict(tmp, "v.md", o)
    assert chk(mod, v, d)[0] == 0
    (d / "_workspace" / "d.md").write_bytes(b"edited\n")
    assert chk(mod, v, d)[0] == 3, "an edit of that design file is seen"


def c_execany(mod: ModuleType, tmp: Path) -> None:
    r = repo(tmp, "r", {"a": b"1\n"})
    before = cid(mod, r)
    (r / "a").chmod(0o654)  # group-only executable bit: counted, although git would not record it
    assert cid(mod, r) != before


SHIM = """\
import os, sys
if "-o" in sys.argv:
    msg = ""
    for n in os.environ["SHIM_NAME"].split("|"):
        if os.environ.get("LC_ALL") == "C":
            msg += "warning: could not open directory '" + n + "/': Permission denied\\n"
        else:
            msg += "warnung: Verzeichnis '" + n + "/' konnte nicht geoeffnet werden\\n"
    sys.stderr.write(msg)
    sys.exit(0)
os.execv(REAL, [REAL] + sys.argv[1:])
"""


def _fake_git(tmp: Path, name: str) -> Path:
    """A `git` that behaves as the real one, except that `ls-files -o` reports a directory it could
    not open, in English under LC_ALL=C and in German otherwise (no permissions are needed)."""
    real = shutil.which("git")
    assert real
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    shim = bindir / "git"
    shim.write_text(
        f"#!{sys.executable}\n" + SHIM.replace("REAL", repr(real)),
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bindir


def _with_fake_git(
    mod: ModuleType, tmp: Path, name: str, make: bool, setup: Callable[[Path], None] | None = None
) -> tuple[int, str]:
    r = repo(tmp, "r", {"a": b"1\n"})
    if make:
        for n in name.split("|"):
            (r / n).mkdir()
    if setup:
        setup(r)
    bindir = _fake_git(tmp, name)
    os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"
    os.environ["SHIM_NAME"] = name
    os.environ["LC_ALL"] = (
        "de_DE.UTF-8"  # what a user's shell may carry; the script must override it
    )
    return run(mod, "id", "--root", str(r))


def c_gitshim(mod: ModuleType, tmp: Path) -> None:
    for i, name in enumerate(["secret", "it's", "nl\ndir", "caf\u00e9 dir"]):
        sub = tmp / f"s{i}"
        sub.mkdir()
        rc, o = _with_fake_git(mod, sub, name, make=True)
        assert rc == 3 and f"SKIPPED: {name} (" in o, (
            f"a directory git could not open must be reported, whatever its name ({name!r}): " + o
        )
    sub = tmp / "s9"
    sub.mkdir()
    rc, o = _with_fake_git(mod, sub, "z': b\nc", make=True)  # ambiguous: still not silent
    assert rc == 3, "a name the parser cannot place exactly must still fail closed: " + o


def c_gitshim_unplaced(mod: ModuleType, tmp: Path) -> None:
    rc, o = _with_fake_git(mod, tmp, "ghost\nname", make=False)
    assert rc == 3 and "could not open a directory" in o, (
        "a warning that names no directory of the tree must still fail closed: " + o
    )


def _nobody_python() -> str | None:
    """A Python that uid 65534 can run, or None when privileges cannot be dropped."""
    for cand in (sys.executable, "/usr/bin/python3"):
        try:
            r = subprocess.run(
                [cand, "-c", "print(7)"], user=65534, capture_output=True, text=True, check=False
            )
        except (OSError, PermissionError):
            continue
        if r.returncode == 0 and r.stdout.strip() == "7":
            return cand
    return None


def c_unreadable_untracked_dir(mod: ModuleType, tmp: Path) -> None:
    py = _nobody_python()
    if py is None:
        pytest.skip(
            "cannot run a child as uid 65534 here, so a directory cannot be made unreadable"
        )
    r = repo(tmp, "r", {"a": b"1\n"})
    for hidden in ("secret", "nl\ndir"):  # a newline in the name defeats any line-based parsing
        (r / hidden).mkdir()
        (r / hidden / "x").write_bytes(b"hidden\n")
        (r / hidden).chmod(0o000)
    home = tmp / "home"
    (home / ".gitconfig").write_text("[safe]\n\tdirectory = *\n")
    for p in (tmp, home):
        p.chmod(0o755)
    copy = tmp / "cid.py"
    copy.write_text(Path(str(mod.__file__)).read_text(encoding="utf-8"), encoding="utf-8")
    copy.chmod(0o644)
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    try:
        res = subprocess.run(
            [py, "-B", str(copy), "id", "--root", str(r)],
            user=65534,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp),
            timeout=60,
            check=False,
        )
    finally:
        for hidden in ("secret", "nl\ndir"):
            (r / hidden).chmod(0o755)
    assert res.returncode == 3 and "SKIPPED: secret" in res.stdout, (
        "an untracked directory the user cannot read must not be skipped silently: "
        + res.stdout
        + res.stderr
    )
    assert "SKIPPED: nl\ndir (" in res.stdout, "the same for a name with a newline: " + res.stdout


def _mk_dir_a(r: Path) -> None:
    (r / "a").unlink()
    (r / "a").mkdir()
    (r / "a" / "f").write_bytes(b"in a\n")


def _mk_untracked_a(r: Path) -> None:
    g(r, "rm", "-q", "--cached", "a")  # the sibling file `a` stays on disk, untracked


def _mk_symlink_a(r: Path) -> None:
    (r / "a").unlink()
    (r / "d").mkdir()
    (r / "a").symlink_to("d")  # git lists a symlink as a file; isdir() would follow it


SIBLINGS: list[tuple[str, str, Callable[[Path], None] | None]] = [
    ("tracked file a", "a': b", None),
    ("untracked file a", "a': b", _mk_untracked_a),
    ("directory a", "a': b", _mk_dir_a),
    ("a symlink a to a directory", "a': b", _mk_symlink_a),
    ("no sibling", "a': b", lambda r: (r / "a").unlink()),
    ("both x and x': y", "x|x': y", None),
]


def c_gitshim_prefix(mod: ModuleType, tmp: Path) -> None:
    for i, (what, name, setup) in enumerate(SIBLINGS):
        sub = tmp / f"p{i}"
        sub.mkdir()
        rc, o = _with_fake_git(mod, sub, name, make=True, setup=setup)
        assert rc == 3 and "SKIPPED:" in o, (
            f"a directory named `a': b` next to {what} must not vanish from the id: " + o
        )


def c_unreadable_prefix(mod: ModuleType, tmp: Path) -> None:
    py = _nobody_python()
    if py is None:
        pytest.skip(
            "cannot run a child as uid 65534 here, so a directory cannot be made unreadable"
        )
    home = tmp / "home"
    (home / ".gitconfig").write_text("[safe]\n\tdirectory = *\n")
    copy = tmp / "cid.py"
    copy.write_text(Path(str(mod.__file__)).read_text(encoding="utf-8"), encoding="utf-8")
    copy.chmod(0o644)
    for p in (tmp, home):
        p.chmod(0o755)
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    for i, (what, name, setup) in enumerate(SIBLINGS):
        sub = tmp / f"u{i}"
        sub.mkdir()
        sub.chmod(0o755)
        r = repo(sub, "r", {"a": b"1\n"})
        if setup:
            setup(r)
        hidden = [r / n for n in name.split("|")]
        for h in hidden:
            h.mkdir()
            (h / "x").write_bytes(b"hidden\n")
            h.chmod(0o000)
        try:
            res = subprocess.run(
                [py, "-B", str(copy), "id", "--root", str(r)],
                user=65534,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(sub),
                timeout=60,
                check=False,
            )
        finally:
            for h in hidden:
                h.chmod(0o755)
        assert res.returncode == 3 and "SKIPPED:" in res.stdout, (
            f"an unreadable directory `{name}` next to {what} must fail closed: "
            + res.stdout
            + res.stderr
        )


def c_sig_symlink(mod: ModuleType, tmp: Path) -> None:
    def swap(p: Path) -> None:
        keep = p.parent / "_workspace" / "a.keep"  # default-excluded: no new entry in the listing
        keep.parent.mkdir()
        os.link(p, keep)  # same inode, size, mtime and mode as `a`, as seen through a link
        p.unlink()
        p.symlink_to("_workspace/a.keep")

    _late(mod, tmp, swap, moves=True)


CHECKS: dict[str, Callable[[ModuleType, Path], None]] = {
    "stable": c_stable,
    "change": c_change,
    "untracked": c_untracked,
    "ignored": c_ignored,
    "globalignore": c_globalignore,
    "deleted": c_deleted,
    "exec": c_exec,
    "swap": c_swap,
    "collision": c_collision,
    "symlink": c_symlink,
    "submodule": c_submodule,
    "unreadable": c_unreadable,
    "huge": c_huge,
    "crlf": c_crlf,
    "empty": c_empty,
    "detached": c_detached,
    "nongit": c_nongit,
    "midrun": c_midrun,
    "emptydiff": c_emptydiff,
    "headmoved": c_headmoved,
    "record": c_record,
    "excludes": c_excludes,
    "usage": c_usage,
    "files": c_files,
    "linear": c_linear,
    "nonet": c_nonet,
    "env": c_env,
    "output": c_output,
    "unmerged": c_unmerged,
    "nested": c_nested,
    "fifo": c_fifo,
    "permdir": c_perm_dir,
    "dirswap": c_dirswap,
    "exclfile": c_exclfile,
    "exclists": c_exclists,
    "gone": c_gone,
    "addstable": c_addstable,
    "multipath": c_multipath,
    "forged": c_forged,
    "capedge": c_capedge,
    "late": c_late,
    "excline": c_exclline,
    "unreaduntracked": c_unreadable_untracked_dir,
    "sigcontrol": c_sig_control,
    "sigmtime": c_sig_mtime,
    "sigsize": c_sig_size,
    "siginode": c_sig_inode,
    "sigmode": c_sig_mode,
    "wsfiles": c_wsfiles,
    "execany": c_execany,
    "gitshim": c_gitshim,
    "gitshim2": c_gitshim_unplaced,
    "gitprefix": c_gitshim_prefix,
    "unreadprefix": c_unreadable_prefix,
    "sigsymlink": c_sig_symlink,
}


def run_check(tag: str, mod: ModuleType) -> str:
    """'' when the check holds, else the message of the failure."""
    tmp = Path(tempfile.mkdtemp(prefix="cid_"))
    try:
        with iso(tmp):
            CHECKS[tag](mod, tmp)
        return ""
    except pytest.skip.Exception:
        raise
    except BaseException as e:  # noqa: BLE001 - a crash in a mutant counts as a failed check
        return f"{type(e).__name__}: {e}"[:300] or "failed"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize("tag", sorted(CHECKS))
def test_script_check(tag: str) -> None:
    assert run_check(tag, load()) == ""


# ---------------------------------------------------------------- mutants of the script


def rep(old: str, new: str, nth: int = 0) -> Callable[[str], str]:
    """Replace the nth occurrence of old; the test fails if old is not there."""

    def edit(src: str) -> str:
        parts = src.split(old)
        assert len(parts) > nth + 1, f"mutation target not found: {old[:50]!r} #{nth}"
        return old.join(parts[: nth + 1]) + new + old.join(parts[nth + 1 :])

    return edit


NOCMP = 'NOW: {now}\\nEXCLUDES: {_enc(excl)}")\n    return 3'
MUTANTS: list[tuple[str, str, Callable[[str], str]]] = [
    (
        "M01 no length prefix in the digest",
        "collision",
        rep(
            'b"%d:%s%s%d:%s" % (len(path), path, k.encode(), len(payload), payload)',
            'b"%s%s%s%s" % (path, k.encode(), payload, b"")',
        ),
    ),
    ("M02 executable bit ignored", "exec", rep('"x" if st.st_mode & 0o111 else "f"', '"f"')),
    (
        "M03 untracked files left out",
        "untracked",
        rep("out += [(p, None) for p in sorted(names)]", "pass"),
    ),
    (
        "M04 ignored files counted",
        "ignored",
        rep('"ls-files", "-o", "--exclude-standard", "-z"', '"ls-files", "-o", "-z"'),
    ),
    (
        "M05 the user's global ignore file honoured",
        "globalignore",
        rep('"-c", "core.excludesFile=/dev/null", ', ""),
    ),
    (
        "M06 a deleted file equals an empty file",
        "deleted",
        rep(
            'return (pb, "m", b""), ""',
            'return (pb, "f", hashlib.sha256(b"").hexdigest().encode()), ""',
        ),
    ),
    ("M07 a symlink is followed", "symlink", rep("st = os.lstat(full)", "st = os.stat(full)")),
    (
        "M08 a symlinked directory on the path is read through",
        "symlink",
        rep('return (pb, "u", b""), "a directory on the path is a symlink"', "pass"),
    ),
    ("M09 no size limit", "huge", rep("if st.st_size > cap:", "if False:")),
    (
        "M10 an unreadable file hashes as empty",
        "unreadable",
        rep(
            '        return "", f"unreadable: {e.strerror or e.errno}"\n    h, got',
            '        return hashlib.sha256(b"").hexdigest(), ""\n    h, got',
        ),
    ),
    (
        "M11 id exits 0 with uncovered files",
        "unreadable",
        rep("if r.unstable or r.skipped or r.n == 0:", "if r.unstable or r.n == 0:", 1),
    ),
    ("M13 an empty candidate is accepted", "empty", rep(" or r.n == 0", "", 1)),
    (
        "M14 an empty candidate is accepted by check",
        "empty",
        rep("if r.unstable or r.skipped or r.n == 0:", "if r.unstable or r.skipped:", 0),
    ),
    (
        "M15 tree-only compares the commit too",
        "headmoved",
        rep(
            'same = token.split("+")[-1] == now.split("+")[-1] if tree_only else token == now',
            "same = token == now",
        ),
    ),
    (
        "M16 the plain check ignores the commit",
        "headmoved",
        rep("else token == now", 'else token.split("+")[-1] == now.split("+")[-1]'),
    ),
    ("M17 a stale verdict exits 1", "change", rep(NOCMP, NOCMP.replace("return 3", "return 1"))),
    (
        "M18 a usage error exits 1",
        "usage",
        rep(
            'print(f"candidate_id: {e}")\n        return 2',
            'print(f"candidate_id: {e}")\n        return 1',
        ),
    ),
    (
        "M19 a bad option exits 1",
        "usage",
        rep("except SystemExit:\n        return 2", "except SystemExit:\n        return 1"),
    ),
    (
        "M20 a file with no CANDIDATE line is current",
        "record",
        rep(
            'REASON: unbound, the file has no CANDIDATE line in its first 8 lines")\n        return 3',
            'REASON: unbound, the file has no CANDIDATE line in its first 8 lines")\n        return 0',
        ),
    ),
    (
        "M21 the whole file is searched for the line",
        "record",
        rep("splitlines()[:8]", "splitlines()[:80]"),
    ),
    (
        "M22 the byte order mark is not stripped",
        "crlf",
        rep('decode("utf-8-sig", "replace")', 'decode("utf-8", "replace")'),
    ),
    ("M23 unverified is accepted", "record", rep(' or token == "unverified"', "")),
    ("M24 any token shape is accepted", "record", rep("if not TOKEN.match(token)", "if False")),
    (
        "M25 the commit part is 7 digits",
        "output",
        rep("HEAD_LEN, DIGEST_LEN = 12, 16", "HEAD_LEN, DIGEST_LEN = 7, 16"),
    ),
    (
        "M26 the tree part is 8 digits",
        "output",
        rep("HEAD_LEN, DIGEST_LEN = 12, 16", "HEAD_LEN, DIGEST_LEN = 12, 8"),
    ),
    (
        "M27 a tree that moved while hashing is accepted",
        "midrun",
        rep("if moved or again != pairs or", "if moved or False and again != pairs or"),
    ),
    (
        "M28 a commit that moved while hashing is accepted",
        "midrun",
        rep('or (kind == "git" and _head(real_root) != head)', ""),
    ),
    (
        "M30 _workspace is not excluded by default",
        "excludes",
        rep('DEFAULT_EXCLUDES = ("_workspace/",)', "DEFAULT_EXCLUDES = ()"),
    ),
    (
        "M31 an exclude matches any prefix",
        "excludes",
        rep('rel.startswith(e.rstrip("/") + "/")', 'rel.startswith(e.rstrip("/"))'),
    ),
    (
        "M32 check ignores the recorded excludes",
        "excludes",
        rep(
            'excl, kind = _dec(f.get("excludes", "-")), token.split(":")[0]',
            'excl, kind = [], token.split(":")[0]',
        ),
    ),
    (
        "M33 an exclude list is not bound into the id",
        "excludes",
        rep("    for e in sorted(excl):\n        h.update(", "    for e in []:\n        h.update("),
    ),
    ("M34 .. is allowed in a path", "usage", rep(' or q == ".." or q.startswith("../")', "")),
    ("M35 an absolute path is allowed", "usage", rep("or os.path.isabs(p) ", "")),
    (
        "M36 a subdirectory of a repository is accepted as root",
        "usage",
        rep("if os.path.realpath(top) != real_root:", "if False:"),
    ),
    ("M37 GIT_* variables reach git", "env", rep('if not k.startswith("GIT_")', "if True")),
    (
        "M38 a submodule pin is ignored",
        "submodule",
        rep('return (pb, "g", idx[1].encode()), ""', 'return (pb, "g", b""), ""'),
    ),
    (
        "M39 a submodule directory is not recognised",
        "submodule",
        rep('if idx and idx[0] == "160000":', "if False:"),
    ),
    (
        "M40 a nested repository is treated as a file",
        "nested",
        rep(
            'return (pb, "u", b""), "a directory (a nested repository or a replaced file)"',
            'return (pb, "f", b""), ""',
        ),
    ),
    (
        "M41 a FIFO is opened",
        "fifo",
        lambda s: rep("if not stat.S_ISREG(st.st_mode):", "if False:")(
            rep("os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK", "os.O_RDONLY | os.O_NOFOLLOW")(s)
        ),
    ),
    (
        "M42 file times enter the id",
        "emptydiff",
        rep('digest.encode()), ""', 'digest.encode() + str(st.st_mtime_ns).encode()), ""'),
    ),
    (
        "M43 the coverage statement is dropped",
        "output",
        rep('"NOT-COVERED: ignored files', '"NOTE: ignored files'),
    ),
    (
        "M44 the file count is dropped from the line",
        "output",
        rep(
            'out = f"{self.token} n={self.n} excludes={_enc(self.excludes)}"',
            'out = f"{self.token} excludes={_enc(self.excludes)}"',
        ),
    ),
    (
        "M45 partial is not written to the line",
        "unreadable",
        rep('+ (f" partial={len(self.skipped)}" if self.skipped else "")', '+ ""'),
    ),
    (
        "M46 a files id without paths is computed anyway",
        "record",
        rep('if kind == "files" and not paths:', "if False:"),
    ),
    ("M47 an unborn HEAD has no name", "empty", rep('return "unborn"', 'return ""')),
    (
        "M48 git is called once per file",
        "linear",
        rep(
            "        e, why = _entry(real_root, real_root, rel, idx, cap)\n",
            "        e, why = _entry(real_root, real_root, rel, idx, cap)\n        _git(real_root, 'rev-parse', 'HEAD')\n",
        ),
    ),
    (
        "M49 a network module is imported",
        "nonet",
        rep("import subprocess\n", "import subprocess\nimport socket\n"),
    ),
    (
        "M50 a directory the walk cannot read is ignored",
        "permdir",
        rep(
            'onerror=lambda e: skipped.append(\n                (str(e.filename), f"unreadable directory: {e.strerror}")\n            ),',
            "onerror=None,",
        ),
    ),
    (
        "M51 a symlinked directory in a walk is followed",
        "files",
        rep("followlinks=False", "followlinks=True"),
    ),
    (
        "M53 a file edited after it was hashed is not seen",
        "late",
        rep("    moved = any(", "    moved = False and any("),
    ),
    (
        "M54 an unreadable untracked directory is dropped",
        "unreaduntracked",
        rep("            names.add(name)  # listed", "            pass  # listed"),
    ),
    (
        "M55 check does not show the exclude list",
        "excline",
        rep(
            'NOW: {now}\\nEXCLUDES: {_enc(excl)}")\n        return 0',
            'NOW: {now}")\n        return 0',
        ),
    ),
    (
        "J22 any indexed directory is a submodule",
        "dirswap",
        rep('if idx and idx[0] == "160000":', "if idx:"),
    ),
    (
        "J26 a single-file exclude is dropped",
        "exclfile",
        rep('any(rel == e.rstrip("/") or rel.startswith', "any(rel.startswith"),
    ),
    (
        "J30 check refuses a vanished judged file",
        "gone",
        rep("cap, missing_ok=True)", "cap, missing_ok=False)"),
    ),
    (
        "J44 entries are not sorted",
        "addstable",
        rep("for path, k, payload in sorted(entries):", "for path, k, payload in entries:"),
    ),
    (
        "J47 paths= is not decoded",
        "multipath",
        rep('paths = _dec(f.get("paths", "-"))', 'paths = [f.get("paths", "-")]'),
    ),
    (
        "J20 a NUL is allowed in a path",
        "forged",
        rep(' or "\\x00" in p', ""),
    ),
    (
        "J41 a file of exactly the limit is refused",
        "capedge",
        rep("if st.st_size > cap:", "if st.st_size >= cap:"),
    ),
    (
        "J01 exclude records carry no length",
        "exclists",
        rep('h.update(b"x%d:%s" % (len(e.encode()), e.encode()))', 'h.update(b"x%s" % e.encode())'),
    ),
    (
        "J45 the exclude list is not sorted",
        "exclists",
        rep("for e in sorted(excl):", "for e in excl:"),
    ),
    (
        "M56 the exclude list is not shown when the tree cannot be shown to match",
        "excline",
        rep('            f"\\nEXCLUDES: {_enc(excl)}"\n', ""),
    ),
    (
        "M57 git may answer in the user's language",
        "gitshim",
        rep('    env["LC_ALL"] = "C"\n', ""),
    ),
    (
        "M58 the language is pinned for the first call only (LC_ALL read from the user)",
        "gitshim",
        rep('env["LC_ALL"] = "C"', 'env.setdefault("LC_ALL", "C")'),
    ),
    (
        "M59 a warning that names a missing path is ignored",
        "gitshim2",
        rep("    if text.count(OPEN_MARK) != placed:", "    if False:"),
    ),
    (
        "M60 only the first line of a name is matched",
        "gitshim",
        rep("\" '(.*?)': [^\\n]*(?:\\n|$)\", re.DOTALL)", "\" '(.*?)': [^\\n]*(?:\\n|$)\")"),
    ),
    (
        "M61 a path that does not exist is accepted as the named directory",
        "gitshim2",
        rep("if name and os.path.isdir(full) and not os.path.islink(full):", "if name:"),
    ),
    (
        "N12 any existing path counts as the placed directory (a sibling file `a`)",
        "gitprefix",
        rep("os.path.isdir(full) and not os.path.islink(full)", "os.path.lexists(full)"),
    ),
    (
        "N12r the same, with a real directory the user cannot read",
        "unreadprefix",
        rep("os.path.isdir(full) and not os.path.islink(full)", "os.path.lexists(full)"),
    ),
    (
        "N12c a symlink to a directory counts as the placed directory",
        "gitprefix",
        rep("os.path.isdir(full) and not os.path.islink(full)", "os.path.isdir(full)"),
    ),
    (
        "N13 the signature follows a symlink (stat, not lstat)",
        "sigsymlink",
        rep(
            "st = os.lstat(path)\n    except OSError:\n        return None",
            "st = os.stat(path)\n    except OSError:\n        return None",
        ),
    ),
    (
        "S1 mtime is not in the signature",
        "sigmtime",
        rep(
            "return st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino",
            "return st.st_mode, st.st_size, 0, st.st_ino",
        ),
    ),
    (
        "S2 size is not in the signature",
        "sigsize",
        rep(
            "return st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino",
            "return st.st_mode, 0, st.st_mtime_ns, st.st_ino",
        ),
    ),
    (
        "S3 inode is not in the signature",
        "siginode",
        rep(
            "return st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino",
            "return st.st_mode, st.st_size, st.st_mtime_ns, 0",
        ),
    ),
    (
        "S4 mode is not in the signature",
        "sigmode",
        rep(
            "return st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino",
            "return 0, st.st_size, st.st_mtime_ns, st.st_ino",
        ),
    ),
    (
        "S5 the signature check afterwards is only for the last file",
        "sigsize",
        rep(
            "moved = any(_sig(os.path.join(real_root, rel)) != sg for (rel, _), sg in zip(pairs, sigs))",
            "moved = bool(pairs) and _sig(os.path.join(real_root, pairs[-1][0])) != sigs[-1]",
        ),
    ),
    (
        "F26 a files id applies the default exclude",
        "wsfiles",
        rep(
            "excl = ([] if a.paths else list(DEFAULT_EXCLUDES)) + [",
            "excl = list(DEFAULT_EXCLUDES) + [",
        ),
    ),
    (
        "J04 only the owner executable bit counts",
        "execany",
        rep('"x" if st.st_mode & 0o111 else "f"', '"x" if st.st_mode & 0o100 else "f"'),
    ),
    (
        "S6 a custom exclude keeps its trailing slash",
        "excline",
        rep('q = os.path.normpath(p).replace(os.sep, "/")', 'q = p.replace(os.sep, "/")'),
    ),
    (
        "M52 a swapped pair of files gives the same id",
        "swap",
        rep(
            "for path, k, payload in sorted(entries):",
            "for (path, k, _), (_, _, payload) in zip(sorted(entries), sorted(entries, key=lambda e: e[2])):",
        ),
    ),
]


@pytest.mark.parametrize("name,tag,edit", MUTANTS, ids=[m[0].split()[0] for m in MUTANTS])
def test_script_mutant_is_killed(
    name: str, tag: str, edit: Callable[[str], str], tmp_path: Path
) -> None:
    src = SCRIPT.read_text(encoding="utf-8")
    mutated = edit(src)
    assert mutated != src, f"{name}: the edit changed nothing"
    mutant = tmp_path / "candidate_id_mutant.py"
    mutant.write_text(mutated, encoding="utf-8")
    try:
        mod = load(mutant)
    except (
        SyntaxError
    ) as e:  # pragma: no cover - a mutant that does not even import is a bad mutant
        pytest.fail(f"{name}: mutant does not import: {e}")
    assert run_check(tag, mod) != "", f"{name}: survived check {tag}"


# ---------------------------------------------------------------- the prose


def texts() -> dict[str, str]:
    return {k: (REPO / v).read_text(encoding="utf-8") for k, v in PROSE.items()}


def section37(t: str) -> str:
    return t[
        t.index("### 3-7. The verdict names the candidate it judged") : t.index(
            "## 4. Honest reporting"
        )
    ]


# Sentences a reviewer relies on: (tag, file key, exact words). Each is checked in the real text and
# its removal is a mutant in test_pinned_sentence_is_killed.
PINS: list[tuple[str, str, str]] = [
    ("K01-c1-no-hand", "qg", "never from memory or by hand"),
    (
        "K02-c2-why",
        "qg",
        "so the reports and verdicts a team writes there do not change the id they carry",
    ),
    ("K22-c2-add", "qg", "Add an exclude only for output that the reviewed work itself produces."),
    ("BC5-c2-line", "qg", "prints it as its `EXCLUDES:` line"),
    ("BC5-c2-refuse", "qg", "refuses a verdict whose list differs"),
    ("K03-c4", "qg", "A QA verdict with anything but `-` there never licenses a commit."),
    ("K04-c5", "qg", "Exit 2: the call was wrong; fix the call."),
    ("K05-c6", "qg", "under C4 it does not license a commit"),
    ("K19-treeonly", "qg", "`--tree-only` passing proves nothing about a file the commit left out"),
    ("BC4-dir", "qg", "an untracked directory the user cannot read"),
    ("BC6-pasted", "qg", "matches like a computed one"),
    ("BC6-fail", "qg", "a `RESULT: FAIL` report checks `current` too"),
    ("BC6-submodule", "qg", "only the staged pin is read, not the commit checked out inside it"),
    ("BC6-gitignore", "qg", "including one that hides itself"),
    ("BC6-workspace", "qg", "`_workspace/` is outside the default id"),
    ("K11-mutcopy", "qag", "Mutation copies belong outside the tree."),
    ("K24-tmpl", "tmpl", "the orchestrator treats it as not given"),
    ("K16-judge-moved", "judge", "write `CANDIDATE: unverified (design moved during the audit)`"),
    ("K27-judge-order", "judge", "Under `TOTALS:` write the `CANDIDATE:` line, then `CARRIED:`"),
    ("BC7-judge", "judge", "id --paths <design file> [<patch file>]"),
    ("BC7-judge-both", "judge", "put both paths on the line"),
    ("BC7-vs", "vs", "id --paths <design file> [<patch file>]"),
    ("BC7-orch", "orch", "id --paths <design file> [<patch file>]"),
    ("BC8-row", "orch", "change-history row belongs inside the unit"),
    ("BC8-exclude", "orch", "must list `.claude-flow/`"),
    ("BC8-orch", "orch", "nobody edits it between `check` and the commit"),
    ("BC7-vs-both", "vs", "both files when the design carries a patch"),
    ("F2-slash", "qg", "ignore a trailing slash"),
    ("F2-printed", "qg", "(`--exclude .claude-flow/` is printed `.claude-flow`)"),
    ("F2-tmpl", "tmpl", "Compare the `EXCLUDES:` line that `check` prints entry by entry"),
    ("F26-files", "qg", "a `files:` id lists exactly the paths it is given"),
    ("A2-c5-row", "qg", "gives the exit 3 its own row"),
    ("A2-tmpl-row", "tmpl", "as a row of its own"),
    ("A2-skill-row", "skill", "gets its own row in the error table"),
    ("P08-c2-covered", "qg", "so a design file under `_workspace/` is covered"),
    ("P05-three-sections", "tmpl", "the three Error handling sections above carry the row"),
    (
        "A2-tmpl-response",
        "tmpl",
        (
            "(response: treat the verdict as not given, tell the user, run the judging phase on "
            "the current tree when they agree)"
        ),
    ),
    ("A2-c5-response", "qg", "(a verdict whose `check` exits 3 is treated as not given)"),
    (
        "A2-skill-response",
        "skill",
        "(treated as not given, the judging phase re-run on the current tree when the user agrees)",
    ),
]


def prose_problems(t: dict[str, str]) -> list[str]:
    out: list[str] = []

    def need(tag: str, ok: bool) -> None:
        if not ok:
            out.append(tag)

    try:
        s = section37(t["qg"])
    except ValueError:
        s = ""
    need("qg-section", bool(s))
    for i in range(1, 9):
        need(f"qg-C{i}", f"| C{i} |" in s)
    for ph in (
        "`check --tree-only`",
        "exit 0 / 2 / 3",
        "Does not cover:",
        "`candidate_id.py id`",
        "`unverified (<reason>)`",
        "`_workspace/`",
        "R7",
        "so one verdict licenses one commit",
        "RESULT: FAIL — candidate moved during QA",
        "RESULT: FAIL — candidate differs from the brief",
        "not tamper evidence",
    ):
        need(f"qg-phrase {ph}", ph in s)
    need("qg-attribution", s.count("adapted from references/openrig/") >= 4)
    need("qg-31", "The next two lines are `CANDIDATE:` and `CARRIED:`" in t["qg"])
    need("qg-22", "The second line is `CANDIDATE:`, the id of the design file" in t["qg"])
    need("qg-checklist", "- [ ] Second line `CANDIDATE:` from `candidate_id.py id`" in t["qg"])
    need(
        "qag",
        "### 7-8. Name the candidate" in t["qag"]
        and "candidate moved during QA" in t["qag"]
        and "CARRIED:" in t["qag"],
    )
    need(
        "qag-template",
        "Open the report with the verdict line, then a `CANDIDATE:` line" in t["qag"],
    )
    paras = [
        x
        for x in t["tmpl"].splitlines()
        if x.startswith("A worker whose job is to judge a candidate")
    ]
    need("tmpl-para", len(paras) == 1)
    if paras:
        p = paras[0]
        need("tmpl-order", t["tmpl"].index(p) < t["tmpl"].index("### Delegating work"))
        need("tmpl-report", "the Report line of the block below stays as it is" in p)
        need(
            "tmpl-check",
            "`candidate_id.py check`" in p
            and "Exit 3" in p
            and "rule R7 of `state-ledger.md`" in p,
        )
        need("tmpl-unverified", "reads `unverified`" in p and "is not a ship verdict" in p)
    blk = re.search(r"````markdown\n(.*?)\n````\n", t["tmpl"], re.DOTALL)
    need(
        "tmpl-block-sha",
        blk is not None and hashlib.sha256(blk[1].encode()).hexdigest() == BLOCK_SHA,
    )
    need("tmpl-o6", t["tmpl"].count("rule O6 of `state-ledger.md` section 3a") == 10)
    need(
        "tmpl-once-para",
        len([x for x in t["tmpl"].splitlines() if x.startswith("A phase marked `once`")]) == 1,
    )
    need("skill-qa", "`CANDIDATE:` line under `RESULT:`" in t["skill"])
    need("skill-gates", "`scripts/candidate_id.py`, §3-7" in t["skill"])
    need(
        "skill-checklist",
        "the orchestrator runs `candidate_id.py check` on that report before it commits"
        in t["skill"],
    )
    need("skill-ref", "refusing a stale verdict" in t["skill"])
    need(
        "bqa-run",
        "candidate_id.py id" in t["bqa"]
        and "candidate differs from the brief" in t["bqa"]
        and "candidate moved during QA" in t["bqa"],
    )
    need(
        "bqa-format",
        "second line `CANDIDATE: <line from candidate_id.py id>`, third line `CARRIED: -`"
        in t["bqa"],
    )
    need("bqa-timeout", "keeping the `CANDIDATE:` line" in t["bqa"])
    need(
        "judge",
        "candidate_id.py id --paths <design file>" in t["judge"] and "`CARRIED:`" in t["judge"],
    )
    need("vs-example", "CANDIDATE: files:" in t["vs"] and "CARRIED: A1-A3" in t["vs"])
    need("vs-text", "The second line is `CANDIDATE:`" in t["vs"])
    need("al", "makes every row of the verdict stale, UPHELD rows included" in t["al"])
    need("aa", "`CARRIED:` line" in t["aa"] and "never copied" in t["aa"])
    need("orch-judge", "then its `CANDIDATE:` and `CARRIED:` lines" in t["orch"])
    need(
        "orch-design",
        "candidate_id.py check {verdict}" in t["orch"] and "launch a new judge" in t["orch"],
    )
    need(
        "orch-qa",
        "Candidate: {CANDIDATE line}" in t["orch"]
        and "candidate_id.py check _workspace/03_boundary-qa_{unit}.md" in t["orch"],
    )
    need(
        "orch-pass",
        "`RESULT: PASS` with `check` exit 0 and `CARRIED: -`" in t["orch"]
        and "check --tree-only" in t["orch"],
    )
    need("orch-gate", "Nothing is committed before `RESULT: PASS` on this tree;" in t["orch"])
    need("orch-error", "`check` exits 3 on a QA PASS or a clean verdict" in t["orch"])
    for k, v in t.items():
        if k == "tmpl":
            need(
                f"attrib-{k}",
                "references/openrig/scripts/gate-lane-consume.mjs:23-25 (Apache-2.0)" in v,
            )
        elif k in ("qg", "qag", "skill", "bqa", "judge", "vs", "aa", "al", "orch"):
            need(
                f"attrib-{k}",
                bool(
                    re.search(
                        r"adapted from references/openrig/[\w./-]+:\d+(?:-\d+)? \(Apache-2\.0\)", v
                    )
                ),
            )
        need(
            f"hangul-{k}",
            not any(lo <= ord(c) <= hi for c in v for lo, hi in HANGUL) or k == "orch",
        )
    need(
        "tmpl-error-rows",
        t["tmpl"].count("A verdict whose `check` exits 3 (only where a worker judges a candidate)")
        == 3,
    )
    rows = [
        ln
        for ln in t["tmpl"].splitlines()
        if ln.lstrip("| ").startswith("A verdict whose `check` exits 3")
    ]
    need(
        "tmpl-row-response",
        len(rows) == 3
        and all(
            r in ln
            for ln in rows
            for r in (
                "treat it as not given",
                "commit and start nothing from it",
                "tell the user",
                "run the judging phase on the current tree when they agree",
            )
        ),
    )
    need("autogpt", "autogpt" + "_platform" not in s + SCRIPT.read_text())
    need("vs-link", "quality-gates.md` section 3-7" in t["vs"])
    for tag, key, phrase in PINS:
        need(f"pin-{tag}", phrase in t[key])
    return out


def test_prose_holds() -> None:
    assert prose_problems(texts()) == []


def _nth_row(old: str, new: str, nth: int) -> Callable[[str], str]:
    """Edit `old` inside the nth stale-verdict row/line (0 = Template A, 1 = B, 2 = C)."""

    def edit(src: str) -> str:
        lines = src.splitlines(keepends=True)
        hits = [
            i
            for i, ln in enumerate(lines)
            if ln.lstrip("| ").startswith("A verdict whose `check` exits 3")
        ]
        lines[hits[nth]] = lines[hits[nth]].replace(old, new)
        return "".join(lines)

    return edit


PROSE_MUTANTS: list[tuple[str, str, str, Callable[[str], str]]] = [
    ("P01 rule C5 removed", "qg", "qg-C5", lambda s: re.sub(r"\| C5 \|.*\n", "", s)),
    (
        "P02 the tree-only rule removed",
        "qg",
        "qg-phrase `check --tree-only`",
        lambda s: s.replace("`check --tree-only`", "`check`"),
    ),
    (
        "P03 section 3-1 loses its pointer",
        "qg",
        "qg-31",
        lambda s: s.replace(
            "The next two lines are `CANDIDATE:` and `CARRIED:` (section 3-7): ", ""
        ),
    ),
    (
        "P04 the does-not-cover list removed",
        "qg",
        "qg-phrase Does not cover:",
        lambda s: s.replace("Does not cover:", "Notes:"),
    ),
    (
        "P05 the checklist bullet removed",
        "qg",
        "qg-checklist",
        lambda s: s.replace(
            "- [ ] Second line `CANDIDATE:` from `candidate_id.py id`", "- [ ] Second line"
        ),
    ),
    (
        "P06 the ledger rule R7 dropped",
        "qg",
        "qg-phrase R7",
        lambda s: s.replace("rule R7 of the ledger still applies", "the ledger is silent"),
    ),
    (
        "P07 the qa guide section removed",
        "qag",
        "qag",
        lambda s: s.replace("### 7-8. Name the candidate", "### 7-8. Naming"),
    ),
    (
        "P08 the template paragraph loses its Report sentence",
        "tmpl",
        "tmpl-report",
        lambda s: s.replace(
            "the Report line of the block below stays as it is", "the block changes"
        ),
    ),
    (
        "P09 the pasted Delegating block is edited",
        "tmpl",
        "tmpl-block-sha",
        lambda s: s.replace(
            "### Delegating work\n\n**Worker brief.**", "### Delegating work\n\n**Worker brief!**"
        ),
    ),
    (
        "P10 the template paragraph duplicated",
        "tmpl",
        "tmpl-para",
        lambda s: s + "\nA worker whose job is to judge a candidate again.\n",
    ),
    (
        "P11 the boundary-qa start check removed",
        "bqa",
        "bqa-run",
        lambda s: s.replace("candidate differs from the brief", "candidate is odd"),
    ),
    (
        "P12 the judge loses its candidate line",
        "judge",
        "judge",
        lambda s: s.replace("candidate_id.py id --paths <design file>", "a hash"),
    ),
    (
        "P13 the orchestrator skips the QA check",
        "orch",
        "orch-qa",
        lambda s: s.replace("candidate_id.py check _workspace/03_boundary-qa_{unit}.md", "ls"),
    ),
    (
        "P14 the orchestrator commits on a carried PASS",
        "orch",
        "orch-pass",
        lambda s: s.replace(" and `CARRIED: -`", ""),
    ),
    ("P15 Hangul in a changed file", "bqa", "hangul-bqa", lambda s: s + "\n" + chr(0xAC00) + "\n"),
    (
        "P16 the attribution line removed from the template",
        "tmpl",
        "attrib-tmpl",
        lambda s: s.replace("gate-lane-consume.mjs:23-25", "gate-lane-consume.mjs"),
    ),
    (
        "P17 the verdict example loses its carried line",
        "vs",
        "vs-example",
        lambda s: s.replace("CARRIED: A1-A3", "CARRIED: none"),
    ),
    (
        "P19 one template loses its stale-verdict row",
        "tmpl",
        "tmpl-error-rows",
        lambda s: s.replace(
            "| A verdict whose `check` exits 3 (only where a worker judges a candidate) |",
            "| x |",
            1,
        ),
    ),
    (
        "N19 template A row: the verdict is used anyway",
        "tmpl",
        "tmpl-row-response",
        _nth_row("treat it as not given", "use it anyway", 0),
    ),
    (
        "N20 template B row: the commit goes ahead",
        "tmpl",
        "tmpl-row-response",
        _nth_row("commit and start nothing from it", "commit it", 1),
    ),
    (
        "P11 template C line: no re-run of the judging phase",
        "tmpl",
        "tmpl-row-response",
        _nth_row("run the judging phase on the current tree when they agree", "carry on", 2),
    ),
    (
        "P08 the C2 sentence says a design file is not covered",
        "qg",
        "pin-P08-c2-covered",
        lambda s: s.replace(
            "so a design file under `_workspace/` is covered",
            "so a design file under `_workspace/` is not covered",
        ),
    ),
    (
        "P05 the template says one Error handling section carries the row",
        "tmpl",
        "pin-P05-three-sections",
        lambda s: s.replace(
            "the three Error handling sections above carry",
            "one Error handling section above carries",
        ),
    ),
    (
        "P18 the design-check step removed",
        "orch",
        "orch-design",
        lambda s: s.replace("candidate_id.py check {verdict}", "ls {verdict}"),
    ),
]


@pytest.mark.parametrize(
    "name,key,tag,edit", PROSE_MUTANTS, ids=[m[0].split()[0] for m in PROSE_MUTANTS]
)
def test_prose_mutant_is_killed(name: str, key: str, tag: str, edit: Callable[[str], str]) -> None:
    t = texts()
    changed = edit(t[key])
    assert changed != t[key], f"{name}: the edit changed nothing"
    t[key] = changed
    assert tag in prose_problems(t), f"{name}: survived (wanted {tag})"


@pytest.mark.parametrize("tag,key,phrase", PINS, ids=[p[0] for p in PINS])
def test_pinned_sentence_is_killed(tag: str, key: str, phrase: str) -> None:
    t = texts()
    assert phrase in t[key], f"{tag}: the sentence is not in {PROSE[key]}"
    t[key] = t[key].replace(phrase, "")
    assert f"pin-{tag}" in prose_problems(t), f"{tag}: survived"


# ---------------------------------------------------------------- the cited lines and the no-copy rule


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def cited() -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    blob = "\n".join(texts().values()) + SCRIPT.read_text() + Path(__file__).read_text()
    for m in re.finditer(r"references/openrig/([\w./-]+?):(\d+)(?:-(\d+))?", blob):
        out.add((m[1], int(m[2])))
        if m[3]:
            out.add((m[1], int(m[3])))
    return out


def test_cited_openrig_lines_exist() -> None:
    root = REPO / "references/openrig"
    if not (root / "LICENSE").exists():
        pytest.skip("references/openrig is not checked out")
    for path, ln in sorted(cited()):
        f = root / path
        assert f.is_file(), path
        assert 1 <= ln <= len(f.read_text(encoding="utf-8").splitlines()), (path, ln)


def test_no_eight_word_run_from_openrig() -> None:
    root = REPO / "references/openrig"
    if not (root / "LICENSE").exists():
        pytest.skip("references/openrig is not checked out")
    grams: set[tuple[str, ...]] = set()
    for path in {p for p, _ in cited()}:
        w = words((root / path).read_text(encoding="utf-8"))
        grams.update(tuple(w[i : i + 8]) for i in range(len(w) - 7))
    ours = [section37(texts()["qg"])] + [
        texts()[k] for k in ("qag", "tmpl", "bqa", "judge", "al", "aa")
    ]
    ours += [SCRIPT.read_text()]
    for blob in ours:
        w = words(blob)
        for i in range(len(w) - 7):
            assert tuple(w[i : i + 8]) not in grams, " ".join(w[i : i + 8])


def test_script_is_executable_python_without_bytecode_residue() -> None:
    assert stat.S_ISREG(SCRIPT.stat().st_mode)
    assert SCRIPT.read_text().startswith('"""Name the exact tree')
