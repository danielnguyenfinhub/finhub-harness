"""Proof for C27: skills/finhub-harness/scripts/cite_check.py checks `references/<sub>/<path>:<line>` cites.

Every test builds its own superproject and submodule with git in tmp_path, so nothing here reads the
pinned references/ of this repo (CI does not check them out). Each assertion message is the
signature a pre-registered mutant trips (quality-gates.md 3-4). The three bounds and the git read
at a recorded commit are adapted from
references/repository_harness/.agents/skills/onboard-repository/scripts/emit_evidence_bundle.py:81-86
(MIT)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/finhub-harness/scripts/cite_check.py"
TEN = "".join(f"line {i}\n" for i in range(1, 11))


def git(cwd: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
        GIT_CONFIG_NOSYSTEM="1",
        HOME=str(cwd),
    )
    p = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env, check=False
    )
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def link(root: Path, name: str, sha: str) -> None:
    git(
        root,
        "config",
        "-f",
        ".gitmodules",
        f"submodule.references/{name}.path",
        f"references/{name}",
    )
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{sha},references/{name}")


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """A superproject pinning references/demo at its first commit."""
    return make_root(tmp_path / "super")


def make_root(top: Path) -> Path:
    sub = top / "references" / "demo"
    (sub / "dir").mkdir(parents=True)
    git(sub, "init", "-q")
    (sub / "ten.txt").write_text(TEN)
    (sub / "noeol.txt").write_text("a\nb")
    (sub / "crlf.txt").write_bytes(b"a\r\nb\r\nc\r\n")
    (sub / "lonecr.txt").write_bytes(b"a\rb\n")
    (sub / "bin.dat").write_bytes(b"a\0b\n")
    (sub / "dir" / "inner.md").write_text("x\n")
    os.symlink("ten.txt", sub / "link")
    os.symlink("dir", sub / "linkdir")
    (sub / "app" / "(grp)").mkdir(parents=True)
    (sub / "app" / "(grp)" / "page.tsx").write_text("x\n")
    git(sub, "add", "-A")
    git(sub, "update-index", "--add", "--cacheinfo", f"160000,{'3' * 40},nested")
    git(sub, "commit", "-qm", "pin")
    git(top, "init", "-q")
    (top / "secret.txt").write_text("s\n")
    (top / "references" / "portmaps").mkdir()
    (top / "references" / "portmaps" / "map.md").write_text(TEN)
    (top / "references" / "NOTES.md").write_text("n\n")
    git(top, "add", "references/portmaps/map.md", "references/NOTES.md")
    link(top, "demo", git(sub, "rev-parse", "HEAD"))
    return top


def run(root: Path, text: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    doc = root.parent / "doc.md"
    doc.write_text(text)
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(doc)],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return p.returncode, p.stdout


def test_valid_cites_pass(root: Path) -> None:
    code, out = run(
        root,
        "A1 | references/demo/ten.txt:1 |\n"
        "see `references/demo/ten.txt:3-5`, `:7` and :8-10; :2.\n"
        "references/demo/noeol.txt:2 and references/demo/dir/inner.md:1).\n",
    )
    assert code == 0, f"C27 valid cites refused: {out}"
    assert "SUMMARY: checked 7, bad 0, skipped 0, unavailable 0" in out, f"C27 continuation: {out}"


def test_line_zero_refused(root: Path) -> None:
    code, out = run(root, "references/demo/ten.txt:0\n")
    assert code == 4 and "line 0 or less" in out, f"C27 line zero refused: {out}"


def test_inverted_range_refused(root: Path) -> None:
    code, out = run(root, "references/demo/ten.txt:5-3\n")
    assert code == 4 and "range inverted (5-3)" in out, f"C27 inverted range refused: {out}"


def test_past_end_refused(root: Path) -> None:
    code, out = run(root, "references/demo/ten.txt:11\nreferences/demo/noeol.txt:3\n")
    assert code == 4, f"C27 past end exit: {out}"
    assert "line 11 past the end (file has 10 lines)" in out, f"C27 past end ten: {out}"
    assert "line 3 past the end (file has 2 lines)" in out, f"C27 past end noeol: {out}"
    code, out = run(root, "references/demo/ten.txt:10\nreferences/demo/ten.txt:9-10\n")
    assert code == 0, f"C27 last line accepted: {out}"


def test_lines_are_counted_by_newline(root: Path) -> None:
    code, out = run(root, "references/demo/crlf.txt:3\nreferences/demo/lonecr.txt:1\n")
    assert code == 0, f"C27 newline count: {out}"
    code, out = run(root, "references/demo/lonecr.txt:2\n")
    assert code == 4 and "file has 1 lines" in out, f"C27 lone CR is not a line end: {out}"


def test_missing_file_refused(root: Path) -> None:
    (root / "references/demo/new.txt").write_text(TEN)  # on disk, not at the pin
    code, out = run(root, "references/demo/new.txt:1\nreferences/demo/nope.txt:1\n")
    assert code == 4 and out.count("missing file at the pin") == 2, f"C27 missing file: {out}"


def test_reads_the_pin_not_the_checkout(root: Path) -> None:
    sub = root / "references/demo"
    (sub / "ten.txt").write_text("one\ntwo\nthree\n")
    git(sub, "commit", "-qam", "later")
    code, out = run(root, "references/demo/ten.txt:10\n")
    assert code == 0, f"C27 checked at the pin: {out}"
    assert "differs from the pin" in out, f"C27 notice on a moved checkout: {out}"


def test_traversal_refused(root: Path) -> None:
    code, out = run(
        root,
        "references/demo/../../secret.txt:1\nreferences/demo/./ten.txt:1\n"
        "references/demo//ten.txt:1\nreferences/../demo/ten.txt:1\n",
    )
    assert code == 4, f"C27 traversal exit: {out}"
    assert out.count("path escapes the submodule") == 4, f"C27 traversal refused: {out}"


def test_symlink_refused(root: Path) -> None:
    code, out = run(root, "references/demo/link:1\nreferences/demo/linkdir/inner.md:1\n")
    assert code == 4, f"C27 symlink exit: {out}"
    assert "a symlink (cite the file it points to)" in out, f"C27 symlink refused: {out}"
    assert "linkdir/inner.md:1: missing file" in out, f"C27 symlinked directory not followed: {out}"


def test_binary_refused(root: Path) -> None:
    code, out = run(root, "references/demo/bin.dat:1\n")
    assert code == 4 and "binary file" in out, f"C27 binary refused: {out}"


def test_directory_refused(root: Path) -> None:
    code, out = run(root, "references/demo/dir:1\n")
    assert code == 4 and "a directory, not a file" in out, f"C27 directory refused: {out}"


def test_unknown_submodule_refused(root: Path) -> None:
    code, out = run(root, "references/nosuch/ten.txt:1\n")
    assert code == 4 and "unknown submodule" in out, f"C27 unknown submodule refused: {out}"


def test_unreadable_submodules_exit_3(root: Path) -> None:
    (root / "references/ghost").mkdir()
    link(root, "ghost", "1" * 40)
    stale = root / "references/stale"
    stale.mkdir()
    git(stale, "init", "-q")
    link(root, "stale", "2" * 40)
    code, out = run(root, "references/ghost/a.md:1\nreferences/stale/b.md:1\n")
    assert code == 3, f"C27 incomplete is exit 3: {out}"
    assert "not checked out" in out, f"C27 ghost not checked out: {out}"
    assert "is not in its local object store" in out, f"C27 stale pin: {out}"
    assert "checked 0, bad 0, skipped 0, unavailable 2" in out, f"C27 unread not checked: {out}"
    code, out = run(root, "references/ghost/a.md:1\nreferences/demo/ten.txt:99\n")
    assert code == 4, f"C27 a BAD line beats an unreadable submodule: {out}"


def test_no_gitmodules_exit_3(tmp_path: Path) -> None:
    code, out = run(tmp_path, "references/demo/ten.txt:1\n")
    assert code == 3 and "no .gitmodules" in out, f"C27 no gitmodules: {out}"


def test_usage_exit_2(root: Path) -> None:
    for argv, err in (
        ([], "usage: cite_check.py"),
        (["--all"], "usage: cite_check.py"),
        ([str(root / "absent.md")], "cannot read"),
    ):
        p = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *argv],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert p.returncode == 2 and err in p.stderr, f"C27 usage exit 2 for {argv}"


def test_placeholders_skipped_and_prose_ignored(root: Path) -> None:
    code, out = run(
        root,
        "references/demo/ten.txt:<line> and references/<sub>/<path>:<line>\n"
        "round 2/3 at 10:30, host:8080, step 3: go, quality-gates.md:346,\n"
        "skills/x/references/demo/ten.txt:99 and https://h/references/demo/ten.txt:99\n",
    )
    assert code == 0, f"C27 prose exit: {out}"
    assert "checked 0, bad 0, skipped 1, unavailable 0" in out, f"C27 prose not a cite: {out}"


def test_document_text_never_reaches_git(root: Path, tmp_path: Path) -> None:
    real = shutil.which("git")
    assert real
    shim = tmp_path / "bin"
    shim.mkdir()
    log = tmp_path / "argv.log"
    (shim / "git").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{log}"\nexec "{real}" "$@"\n')
    (shim / "git").chmod(0o755)
    env = dict(os.environ, PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
    code, out = run(root, "references/demo/zz$HOME&&touch_pwned.txt:1\n", env=env)
    assert code == 4 and "missing file at the pin" in out, f"C27 hostile path: {out}"
    assert "ls-tree" in log.read_text(), "C27 shim saw no git call"
    assert "zz" not in log.read_text(), "C27 document text reached git argv"
    assert not list(root.rglob("*pwned*")), "C27 hostile path ran"
    src = SCRIPT.read_text()
    assert "shell=True" not in src and "os.system" not in src, "C27 no shell in the script"


def test_every_git_call_forbids_fetch(root: Path, tmp_path: Path) -> None:
    real = shutil.which("git")
    assert real
    shim = tmp_path / "bin"
    shim.mkdir()
    log = tmp_path / "calls.log"
    body = f'#!/bin/sh\nprintf "CALL %s %s\\n" "$GIT_NO_LAZY_FETCH" "$*" >> "{log}"\nexec "{real}" "$@"\n'
    (shim / "git").write_text(body)
    (shim / "git").chmod(0o755)
    env = dict(os.environ, PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
    code, out = run(root, "references/demo/ten.txt:1\nreferences/portmaps/map.md:2\n", env=env)
    calls = log.read_text().splitlines()
    assert code == 0 and len(calls) >= 5, f"C27 shim calls: {out} {calls}"
    assert all(
        "-c protocol.allow=never" in c for c in calls
    ), "C27 no-fetch option on every git call"
    assert all(c.startswith("CALL 1 ") for c in calls), "C27 lazy fetch disabled in env"
    per = [f"-c protocol.{p}.allow=never" for p in ("file", "git", "ssh", "http", "https", "ext")]
    assert all(all(x in c for x in per) for c in calls), "C27 per-protocol no-fetch on every call"


def test_git_environment_ignored(root: Path) -> None:
    env = dict(os.environ, GIT_DIR="/nonexistent", GIT_INDEX_FILE="/nonexistent")
    code, out = run(root, "references/demo/ten.txt:1\n", env=env)
    assert code == 0, f"C27 GIT_ environment ignored: {out}"


def test_adjacent_cites_each_read(root: Path) -> None:
    code, out = run(
        root,
        "references/demo/ten.txt:3,references/demo/ten.txt:99\n"
        "(references/demo/ten.txt:1)(references/demo/ten.txt:77)\n"
        "|references/demo/ten.txt:2|references/demo/ten.txt:55|\n",
    )
    assert out.count("past the end") == 3, f"C27 adjacent cite swallowed: {out}"
    assert code == 4, f"C27 adjacent exit: {out}"
    assert "checked 6, bad 3, skipped 0" in out, f"C27 adjacent counts: {out}"


def test_paths_with_brackets_read(root: Path) -> None:
    code, out = run(root, "references/demo/app/(grp)/page.tsx:1 and :99\n")
    assert code == 4 and "line 99 past the end" in out, f"C27 bracket path read: {out}"


def test_unread_tokens_are_skipped(root: Path) -> None:
    code, out = run(root, "references/demo/a*b.md:3 and references/demo/ten.txt:1\n")
    assert code == 0, f"C27 unread token exit: {out}"
    assert "not read as a cite" in out, f"C27 unread token skipped: {out}"
    assert "checked 1, bad 0, skipped 1" in out, f"C27 unread token counts: {out}"


def test_tracked_project_file_under_references(root: Path) -> None:
    code, out = run(root, "references/portmaps/map.md:10 and references/NOTES.md:1\n")
    assert code == 0, f"C27 tracked project file checked: {out}"
    assert "checked 2, bad 0" in out, f"C27 project file counts: {out}"
    code, out = run(root, "references/portmaps/map.md:11\nreferences/skill-local.md:4\n")
    assert code == 4 and "line 11 past the end" in out, f"C27 project file range: {out}"
    assert "not a tracked file under references/" in out, f"C27 skill-relative skipped: {out}"


def test_nested_submodule_refused(root: Path) -> None:
    code, out = run(root, "references/demo/nested:1\n")
    assert code == 4 and "a nested submodule" in out, f"C27 nested submodule refused: {out}"


def test_line_number_too_large(root: Path) -> None:
    code, out = run(
        root,
        "references/demo/ten.txt:" + "9" * 5000 + "\nreferences/demo/ten.txt:1-" + "9" * 10 + "\n",
    )
    assert code == 4, f"C27 huge line number exit: {out}"
    assert out.count("line number too large") == 2, f"C27 huge line number refused: {out}"


def test_partial_clone_never_fetches(root: Path, tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q")
    (src / "f.txt").write_text("a\nb\n")
    git(src, "add", "f.txt")
    git(src, "commit", "-qm", "x")
    git(src, "config", "uploadpack.allowFilter", "true")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    part = root / "references" / "part"
    git(root, "clone", "-q", "--no-checkout", "--filter=blob:none", f"file://{src}", str(part))
    link(root, "part", git(src, "rev-parse", "HEAD"))
    code, out = run(root, "references/part/f.txt:2\n")
    missing = git(
        part, "-c", "protocol.allow=never", "rev-list", "--objects", "--missing=print", "--all"
    )
    assert "?" in missing, "C27 nothing fetched"
    assert code == 3, f"C27 missing blob is exit 3: {out}"
    assert (
        "nothing was fetched" in out and "unavailable 1" in out
    ), f"C27 missing blob reason: {out}"


def test_not_a_work_tree_exit_3(tmp_path: Path) -> None:
    (tmp_path / ".gitmodules").write_text('[submodule "x"]\n\tpath = references/demo\n')
    code, out = run(tmp_path, "references/demo/ten.txt:1\n")
    assert code == 3 and "cannot read the index" in out, f"C27 no index exit 3: {out}"


def test_no_git_binary_exit_3(root: Path, tmp_path: Path) -> None:
    empty = tmp_path / "nobin"
    empty.mkdir()
    code, out = run(root, "references/demo/ten.txt:1\n", env=dict(os.environ, PATH=str(empty)))
    assert code == 3 and "UNAVAILABLE" in out, f"C27 no git exit 3: {out}"


HOSTILE = [
    "references/demo/ten.txt:" + "0" * 20,
    "references/demo/ten.txt:١٢",
    "references/demo/ten.txt:3-٣",
    "references/demo/\x00:1",
    "references/" * 2000 + ":1",
    "`references/demo/ten.txt:1`:2:3-4,:5;:6 and :7-",
    "references/demo/ten.txt:" + "1-" * 3000,
    "references/.:1 references/..:1 references/demo/.:1 references/demo/./:1",
    "x" * 200000 + "references/demo/ten.txt:1",
]


@pytest.mark.parametrize("n", range(len(HOSTILE)))
def test_no_traceback_on_hostile_input(root: Path, n: int) -> None:
    doc = root.parent / "doc.md"
    doc.write_text(HOSTILE[n] + "\n")
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(doc)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode in (0, 3, 4) and "Traceback" not in p.stderr, f"C27 crash on hostile {n}"


def run3(root: Path, text: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    doc = root.parent / "doc.md"
    doc.write_text(text)
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(doc)],
        cwd=root,
        capture_output=True,
        env=env,
        check=False,
    )
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def test_line_list_without_colon_read(root: Path) -> None:
    code, out = run(
        root,
        "references/demo/ten.txt:3,99\nreferences/demo/ten.txt:3, 99\n"
        "references/demo/ten.txt:3-5, 99-120\nreferences/demo/ten.txt:3-5, 8-10\n",
    )
    assert out.count("past the end") == 3, f"C27 line list read: {out}"
    assert code == 4 and "checked 8, bad 3, skipped 0" in out, f"C27 line list counts: {out}"


def test_submodule_name_with_space(root: Path) -> None:
    git(
        root,
        "config",
        "-f",
        ".gitmodules",
        "--rename-section",
        "submodule.references/demo",
        "submodule.demo repo",
    )
    code, out = run(root, "references/demo/ten.txt:1\n")
    assert code == 0 and "checked 1, bad 0" in out, f"C27 submodule name with a space: {out}"


def test_non_utf8_gitmodules_path(root: Path) -> None:
    with open(root / ".gitmodules", "ab") as f:
        f.write(b'[submodule "z"]\n\tpath = references/\xff\xfe\n')
    code, _out, err = run3(root, "references/demo/ten.txt:1\n")
    assert "Traceback" not in err and code == 0, f"C27 non-UTF-8 gitmodules path: {err}"


def test_non_utf8_project_directory(tmp_path: Path) -> None:
    top = make_root(tmp_path / os.fsdecode(b"proj\xe9") / "super")
    env = dict(os.environ, PYTHONIOENCODING="utf-8:strict")  # a locale that does not escape
    code, out, err = run3(top, "references/demo/ten.txt:1\nreferences/demo/ten.txt:99\n", env=env)
    assert "Traceback" not in err, f"C27 non-UTF-8 project directory: {err}"
    assert code == 4 and "checked 2, bad 1" in out, f"C27 non-UTF-8 directory counts: {out}"


def partial(root: Path, tmp_path: Path) -> Path:
    src = tmp_path / "src2"
    src.mkdir()
    git(src, "init", "-q")
    (src / "f.txt").write_text("a\nb\n")
    git(src, "add", "f.txt")
    git(src, "commit", "-qm", "x")
    git(src, "config", "uploadpack.allowFilter", "true")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    part = root / "references" / "part2"
    git(root, "clone", "-q", "--no-checkout", "--filter=blob:none", f"file://{src}", str(part))
    link(root, "part2", git(src, "rev-parse", "HEAD"))
    return part


def test_no_fetch_on_a_git_without_the_variable(root: Path, tmp_path: Path) -> None:
    """A git that ignores GIT_NO_LAZY_FETCH, with protocol.file.allow=always in the user's config."""
    part = partial(root, tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text('[protocol "file"]\n\tallow = always\n')
    real = shutil.which("git")
    assert real
    shim = tmp_path / "oldgit"
    shim.mkdir()
    (shim / "git").write_text(f'#!/bin/sh\nunset GIT_NO_LAZY_FETCH\nexec "{real}" "$@"\n')
    (shim / "git").chmod(0o755)
    env = dict(os.environ, HOME=str(home), PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
    code, out = run(root, "references/part2/f.txt:2\n", env=env)
    missing = git(
        part, "-c", "protocol.file.allow=never", "rev-list", "--objects", "--missing=print", "--all"
    )
    assert "?" in missing, "C27 per-protocol option blocks the fetch"
    assert code == 3, f"C27 older git exit 3: {out}"


def test_many_cites_on_one_line(root: Path) -> None:
    import time

    line = "references/demo/ten.txt:1," * 40000
    t = time.monotonic()
    code, out = run(root, line + "\n")
    took = time.monotonic() - t
    assert code == 0 and "checked 40000," in out, f"C27 many cites counts: {out[-200:]}"
    assert took < 5, f"C27 one long line is linear: {took:.1f}s"


QG = "skills/finhub-harness/references/quality-gates.md"
AA = ".claude/skills/adversarial-audit/SKILL.md"
RS = ".claude/skills/runtime-slice-design/SKILL.md"
SK = "skills/finhub-harness/SKILL.md"
SC = "skills/finhub-harness/scripts/cite_check.py"
PINS = {
    "qg-heading": (QG, "### 1-4. Check every cite mechanically before the audit"),
    "qg-cc1": (QG, "The architect runs it on the design before saying the design is ready"),
    "qg-cc2": (QG, "because a line in range is not a line that supports the claim"),
    "qg-cc3": (QG, "cites count as `unavailable`, never as checked"),
    "qg-cc4": (QG, "it never reaches git's arguments or a shell"),
    "qg-cc5": (QG, "is printed as `SKIPPED` and counted, never passed"),
    "qg-noshell": (QG, "the judge writes `SUMMARY: cite_check not run (no shell)`"),
    "qg-attr": (QG, "onboard-repository/scripts/emit_evidence_bundle.py:63-86 (MIT)"),
    "aa-run": (AA, "and copy its `SUMMARY:` line into the verdict body"),
    "aa-bad": (AA, "printed a `BAD` line for the row's cite → REJECTED with the printed reason"),
    "rs-run": (RS, "and fix every `BAD` line before step 5"),
    "aa-escape": (
        AA,
        "a judge who opens the cited line and finds the script wrong rules UNVERIFIED",
    ),
    "sk-root": (SK, "run from the project root as"),
    "qg-list": (QG, "a line list such as `:3-5, 8-10`"),
    "rs-adopt": (RS, "Before saying an adoption design is ready, run the cite check of step 4"),
    "qg-nohash": (QG, "Nothing is hashed: after a re-pin, a cite whose line still exists"),
    "qg-escape": (QG, "so a false `BAD` never fails a correct row"),
    "qg-where": (QG, "copies `cite_check.py` into its own `scripts/` and runs that copy"),
    "qg-nofetch": (QG, "every git call runs with `protocol.allow=never`"),
    "qg-silent": (QG, "none is dropped silently"),
    "sk-step6": (SK, "cite exists at the pinned commit and is in range, not that it supports"),
    "sk-ref": (SK, "`references/quality-gates.md` §1-4 and `scripts/cite_check.py`"),
    "sk-attr": (
        SK,
        "(adapted from references/repository_harness (MIT); the source lines are named in §1-4)",
    ),
    "sc-attr": (SC, "audit-onboarding-proposal/scripts/validate_evidence_capsule.py:141-158"),
}


@pytest.mark.parametrize("pin", sorted(PINS))
def test_prose_pins(pin: str) -> None:
    rel, phrase = PINS[pin]
    text = " ".join((REPO / rel).read_text(encoding="utf-8").split())
    assert text.count(phrase) == 1, f"C27 prose pin {pin}"
