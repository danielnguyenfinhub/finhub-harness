"""Fourth round on the mode guard: the residuals the third round left open.

Each bypass here was first run in real bash in a throwaway workspace with a dummy HOME (the
``lab`` fixture): unguarded, the command really changes a protected file, so the case is a
real bypass and not a guess; guarded, ``workspace-write`` must refuse it. Benign neighbours
must stay allowed. A differential test replays the third round's command lists and generated
commands against the guard as it stood before this round and loses none.

Open on purpose: read-only ``grep -r . .`` at the workspace root still reads ``.env`` and
``.git`` (protected files are readable in read-only mode by design, and an existing test needs
``grep -rn foo .`` to stay allowed); ``tar``, ``unzip`` or ``patch`` run at the workspace root
whose archive or patch names a protected file (the content is not readable by a text guard).
"""

import importlib.util
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.permissions import make_mode_guard

CLASSES = {"write_file": "write", "run": "shell"}
BASE_SHA = "23030b9"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}
WATCHED = (".env", ".claude/settings.json", ".git/config")

PATCH = "--- settings.json\n+++ settings.json\n@@ -1 +1 @@\n-LOCAL\n+PWNED\n"
GIT_PATCH = (
    "diff --git a/.claude/settings.json b/.claude/settings.json\n"
    "--- a/.claude/settings.json\n+++ b/.claude/settings.json\n@@ -1 +1 @@\n-LOCAL\n+PWNED\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **GIT_ENV}, check=True, capture_output=True
    )


def _build(tmp: Path, state: str) -> Path:
    root = tmp / "ws"
    for d in ("sub", "src", ".claude"):
        (root / d).mkdir(parents=True)
    (root / ".env").write_text("ORIG\n")
    (root / ".claude" / "settings.json").write_text("ORIG\n")
    (root / "src" / "a.py").write_text("ORIG\n")
    (root / "sub" / "x").write_text("ORIG\n")
    (root / "sub" / "settings.json").write_text("PWNED\n")
    (root / "sub" / "config").write_text("PWNED\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "i")
    # untracked helpers, made after the commit
    (root / "a.diff").write_text(PATCH)
    (root / "g.diff").write_text(GIT_PATCH)
    subprocess.run(["tar", "-cf", "a.tar", "-C", "sub", "settings.json"], cwd=root, check=True)
    subprocess.run(["tar", "-cf", "g.tar", "-C", "sub", "config"], cwd=root, check=True)
    subprocess.run(["zip", "-q", "a.zip", "settings.json"], cwd=root / "sub", check=True)
    shutil.move(str(root / "sub" / "a.zip"), root / "a.zip")
    subprocess.run(["zip", "-q", "g.zip", "config"], cwd=root / "sub", check=True)
    shutil.move(str(root / "sub" / "g.zip"), root / "g.zip")
    gz = root / ".claude" / "settings.json.gz"
    gz.write_bytes(
        subprocess.run(["gzip", "-c"], input=b"PWNED\n", capture_output=True, check=False).stdout
    )
    os.link(root / ".env", root / "h")
    os.link(root / ".claude" / "settings.json", root / ".claude" / "hl")
    os.link(root / "sub" / "x", root / "sub" / "x2")
    if state == "dirty":  # tracked protected files edited and not committed
        (root / ".env").write_text("LOCAL\n")
        (root / ".claude" / "settings.json").write_text("LOCAL\n")
    elif state == "stashed":  # the edits sit in a stash, the tree is clean
        (root / ".env").write_text("LOCAL\n")
        (root / ".claude" / "settings.json").write_text("LOCAL\n")
        _git(root, "stash")
    return root


@pytest.fixture
def lab(tmp_path: Path) -> Path:
    return _build(tmp_path, "dirty")


@pytest.fixture
def lab_stashed(tmp_path: Path) -> Path:
    return _build(tmp_path, "stashed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {p: (root / p).read_bytes() for p in WATCHED}


def unguarded(root: Path, cmd: str) -> bool:
    """Run the command in real bash, no guard, dummy HOME; did a watched file change?"""
    home = root.parent / "home"
    home.mkdir(exist_ok=True)
    env = {"PATH": os.environ["PATH"], "HOME": str(home), **GIT_ENV}
    before = snapshot(root)
    subprocess.run(
        ["bash", "-c", cmd],
        cwd=root,
        env=env,
        timeout=30,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return snapshot(root) != before


def guard(root: Path, mode: str = "workspace-write"):  # type: ignore[no-untyped-def]
    return make_mode_guard(mode, Workspace(root), tool_classes=CLASSES)  # type: ignore[arg-type]


def verdict(root: Path, cmd: str) -> str | None:
    return guard(root)(ToolCall("c", "run", {"command": cmd}))


def check_bypass(root: Path, cmd: str, why: str | None = None) -> None:
    """The guard refuses it, and unguarded in real bash it really changes a protected file."""
    msg = verdict(root, cmd)
    assert msg is not None, f"allowed: {cmd}"
    if why:
        assert why in msg, (cmd, msg)
    assert unguarded(root, cmd), f"not a real bypass in bash: {cmd}"


# --- (1) writers that act on the working directory without naming it ------------------------

CWD_WRITERS = [
    "cd .claude && tar -xf ../a.tar",
    "cd .claude && tar xf ../a.tar",
    "cd .claude && tar -x -f ../a.tar",
    "cd .claude && tar --extract -f ../a.tar",
    "cd .claude && tar --get -f ../a.tar",
    "cd .claude && tar -xvf ../a.tar",
    "cd .claude; tar xvf ../a.tar",
    "(cd .claude && tar -xf ../a.tar)",
    "bash -c 'cd .claude && tar -xf ../a.tar'",
    "pushd .claude >/dev/null && tar -xf ../a.tar",
    "cd .claude && unzip -o ../a.zip",
    "cd .claude && unzip -oq ../a.zip",
    "cd .claude && patch -p0 < ../a.diff",
    "cd .claude && git apply ../g.diff",
    "cd .claude && gunzip -f settings.json.gz",
    "cd .claude && gzip -d -f settings.json.gz",
    "cd .claude && gzip --decompress -f settings.json.gz",
    "cd .claude && gzip -dkf settings.json.gz",
    "cd .git && tar -xf ../g.tar",
    "cd .git && unzip -o ../g.zip",
    "cd sub && cd ../.claude && tar -xf ../a.tar",
]


@pytest.mark.parametrize("cmd", CWD_WRITERS)
def test_writer_into_a_protected_cwd_is_refused_and_is_a_real_bypass(lab: Path, cmd: str) -> None:
    check_bypass(lab, cmd, None if ".git" in cmd else "current directory")


CWD_WRITERS_NO_PROOF = [  # cpio is not installed here, so only the guard is checked
    "cd .claude && cpio -i < ../a.cpio",
    "cd .claude && cpio --extract < ../a.cpio",
    "cd .claude && cpio -idm < ../a.cpio",
    "cd .claude && cpio -p ../sub",
    "cd .claude && cpio --pass-through ../sub",
]


@pytest.mark.parametrize("cmd", CWD_WRITERS_NO_PROOF)
def test_cpio_into_a_protected_cwd_is_refused(lab: Path, cmd: str) -> None:
    msg = verdict(lab, cmd)
    assert msg is not None and "current directory" in msg, cmd


DIR_DESTINATIONS = [  # the file name comes from the source, the destination is a directory
    "cp sub/settings.json .claude/",
    "cp sub/settings.json .claude",
    "cp -f sub/settings.json .claude/.",
    "cd .claude && cp ../sub/settings.json .",
    "cd .claude && cp -f ../sub/settings.json ./",
    "cp -t .claude sub/settings.json",
    "cp --target-directory=.claude sub/settings.json",
    "cp -t .claude -- sub/settings.json",
    "mv sub/settings.json .claude/",
    "install -m 644 sub/settings.json .claude/",
    "ln -sf ../sub/settings.json .claude/",
    "cp -a sub/config .git/",
    "cd .git && cp ../sub/config .",
    "cd .claude && ln -sf ../sub/settings.json",
]


@pytest.mark.parametrize("cmd", DIR_DESTINATIONS)
def test_copy_into_a_protected_directory_is_refused_and_is_a_real_bypass(
    lab: Path, cmd: str
) -> None:
    check_bypass(lab, cmd)


BENIGN_CWD = [
    "tar -xf a.tar",  # at the workspace root: the archive content is unreadable (open item)
    "cd src && tar -xf ../a.tar",
    "cd sub && unzip -o ../a.zip",
    "cd sub && patch -p0 < ../a.diff",
    "cd .claude && tar -tf ../a.tar",
    "cd .claude && tar tvf ../a.tar",
    "cd .claude && tar -cf ../out.tar settings.json.gz",
    "cd .claude && unzip -l ../a.zip",
    "cd .claude && unzip -p ../a.zip",
    "cd .claude && unzip -t ../a.zip",
    "cd .claude && unzip -d ../sub ../a.zip",
    "cd .claude && git apply --check ../g.diff",
    "cd .claude && git apply --stat ../g.diff",
    "cd .claude && patch --dry-run -p0 < ../a.diff",
    "cd .claude && gunzip -c settings.json.gz",
    "cd .claude && gzip -t settings.json.gz",
    "cd .claude && gzip -dc settings.json.gz",
    "cd .claude && ls",
    "cd .claude && cat settings.json",
    "cp sub/x src/",
    "cp sub/settings.json src/",
    "cp sub/x .claude/",
    "mv sub/x .claude/",
    "cd .claude && cp ../sub/x .",
    "cp -r src sub",
]


@pytest.mark.parametrize("cmd", BENIGN_CWD)
def test_benign_neighbours_of_the_cwd_rule_stay_allowed(lab: Path, cmd: str) -> None:
    assert verdict(lab, cmd) is None, cmd


# --- (2) git commands that overwrite or delete tracked protected files ----------------------

GIT_OVERWRITE = [
    "git checkout .",
    "git checkout -- .",
    "git checkout -- .claude",
    "git checkout HEAD -- .claude",
    "git checkout HEAD .",
    "git checkout -- '*'",
    "git checkout -f",
    "git checkout -f main",
    "git checkout --force main",
    "git restore .",
    "git restore --worktree .",
    "git restore -W .claude",
    "git restore --staged --worktree .",
    "git restore -SW .",
    "git restore --source=HEAD .",
    "git restore -s HEAD .",
    "git restore --source HEAD .",
    "git restore ':/'",
    "git restore -- .claude",
    "git reset --hard",
    "git reset --hard HEAD",
    "git reset -q --hard",
    "git reset --ha",
    "git switch -f main",
    "git switch --discard-changes main",
    "git -C .claude checkout settings.json",
    "git -C .claude restore settings.json",
    "git -C .claude checkout .",
    "git -C .claude restore .",
    "git -C sub -C ../.claude checkout .",
    "git checkout-index -a -f",
]


@pytest.mark.parametrize("cmd", GIT_OVERWRITE)
def test_git_overwrite_of_tracked_protected_files_is_refused_and_is_real(
    lab: Path, cmd: str
) -> None:
    check_bypass(lab, cmd, "git")


GIT_RESTORE_FROM_STASH = [
    "git stash pop",
    "git stash apply",
    "git stash pop --index",
    "git stash apply --quiet",
    "git stash branch newb",
]


@pytest.mark.parametrize("cmd", GIT_RESTORE_FROM_STASH)
def test_git_stash_restore_is_refused_and_is_real(lab_stashed: Path, cmd: str) -> None:
    check_bypass(lab_stashed, cmd, "git stash")


GIT_BENIGN = [
    "git checkout -- src/a.py",
    "git checkout src/a.py",
    "git checkout main",
    "git checkout -b feature",
    "git checkout -b feature main",
    "git checkout HEAD~1 -- src",
    "git restore src/a.py",
    "git restore --source=HEAD src",
    "git restore --staged .",
    "git restore -S src",
    "git reset",
    "git reset HEAD src/a.py",
    "git reset --soft HEAD~1",
    "git reset --mixed",
    "git stash",
    "git stash list",
    "git stash show",
    "git stash drop",
    "git switch main",
    "git switch -c other",
    "git -C sub checkout main",
    "git -C src restore a.py",
    "git status",
    "git diff",
    "git add src",
    "git commit -m wip",
]


@pytest.mark.parametrize("cmd", GIT_BENIGN)
def test_benign_git_neighbours_stay_allowed(lab: Path, cmd: str) -> None:
    assert verdict(lab, cmd) is None, cmd


# --- (3) a hard link made earlier to a protected file ---------------------------------------

HARD_LINK_WRITES = [
    "echo y > h",
    "echo y >> h",
    "printf y | tee h",
    "echo y | tee -a h",
    "truncate -s 0 h",
    "dd if=sub/x of=h",
    "cat sub/x > ./h",
    "cd sub && echo y > ../h",
    "echo y > .claude/hl",
    "cp sub/x h",
    "cp sub/x .claude/hl",
]


@pytest.mark.parametrize("cmd", HARD_LINK_WRITES)
def test_write_through_a_hard_link_to_a_protected_file_is_refused_and_is_real(
    lab: Path, cmd: str
) -> None:
    check_bypass(lab, cmd, "protected")


HARD_LINK_REPLACE = [  # replaces the name (new inode), so bash changes no protected file
    "sed -i s/ORIG/Y/ h",
    "mv sub/x h",
    "cp h sub/copy",  # a hard link to a protected file is named like it: not a plain read
]


@pytest.mark.parametrize("cmd", HARD_LINK_REPLACE)
def test_replacing_a_hard_link_name_is_refused_too(lab: Path, cmd: str) -> None:
    assert verdict(lab, cmd) is not None, cmd


HARD_LINK_BENIGN = [
    "cat h",
    "ls -l h",
    "grep ORIG h",
    "head -n 1 .claude/hl",
    "echo y > h2",
    "echo y > sub/x2",  # a hard link, but not to a protected file
    "tee sub/x2 < /dev/null",
]


@pytest.mark.parametrize("cmd", HARD_LINK_BENIGN)
def test_reading_a_hard_link_and_other_hard_links_stay_allowed(lab: Path, cmd: str) -> None:
    assert verdict(lab, cmd) is None, cmd


def test_a_hard_link_check_follows_the_tracked_directory(lab: Path) -> None:
    assert verdict(lab, "cd .claude && echo y > hl") is not None
    assert verdict(lab, "cd sub && echo y > hl") is None  # sub/hl is not the linked file


def test_a_hard_link_check_survives_a_missing_file_and_a_directory(lab: Path) -> None:
    assert verdict(lab, "echo y > nothing-here") is None
    assert verdict(lab, "echo y > sub/new-file") is None
    assert verdict(lab, "touch sub") is None


# --- (4) a symlink made in the same command and written through -----------------------------

SAME_COMMAND_LINKS = [
    "ln -s .claude c && echo y > c/settings.json",
    "ln -s .claude c; echo y > c/settings.json",
    "ln -sf .claude c; cd c; echo y > settings.json",
    "ln -s .claude c && cd c && echo y > settings.json",
    "ln --symbolic .claude c && printf y | tee c/settings.json",
    "ln -s .claude c && cp sub/x c/settings.json",
    "ln -s ../.claude sub/c && echo y > sub/c/settings.json",
    "cd sub && ln -s ../.claude c && echo y > c/settings.json",
    "ln -s .claude c && sed -i s/LOCAL/Y/ c/settings.json",
    "ln -s -f .claude c && tar -xf a.tar -C c",
    "ln -s .claude c && cp sub/settings.json c",
]


@pytest.mark.parametrize("cmd", SAME_COMMAND_LINKS)
def test_writing_through_a_symlink_made_in_the_same_command_is_refused_and_is_real(
    lab: Path, cmd: str
) -> None:
    check_bypass(lab, cmd)


LINK_BENIGN = [
    "ln -s src c && echo y > c/a.py",
    "ln -s .claude c && ls c",
    "ln -s .claude c && cat c/settings.json",
    "ln -s sub/x y",
    "ln -s .claude c",  # alone it writes nothing through the link
    "ln -s src c; cd c; echo y > a.py",
]


@pytest.mark.parametrize("cmd", LINK_BENIGN)
def test_symlinks_to_ordinary_directories_and_plain_reads_stay_allowed(lab: Path, cmd: str) -> None:
    assert verdict(lab, cmd) is None, cmd


def test_a_link_to_a_protected_directory_is_followed_in_a_later_command(lab: Path) -> None:
    (lab / "c").symlink_to(".claude")
    assert verdict(lab, "echo y > c/settings.json") is not None


# --- (5) shell functions that cd ------------------------------------------------------------

FUNCTION_CD = [  # the definition moves the guard's tracked directory, the call moves bash's
    "cd sub; f() if cd ../.claude; then :; fi; cd ../sub; f; echo x > settings.json",
    "cd sub; f() while cd ../.claude; do break; done; cd ../sub; f; echo x > settings.json",
    (
        "pushd sub >/dev/null; f() if pushd ../.claude >/dev/null; then :; fi; "
        "pushd ../sub >/dev/null; f; echo x > settings.json"
    ),
    "cd sub; function f if cd ../.claude; then :; fi; cd ../sub; f; echo x > settings.json",
    "cd sub; f () if cd ../.claude; then :; fi; cd ../sub; f; tar -xf ../a.tar",
]


@pytest.mark.parametrize("cmd", FUNCTION_CD)
def test_defining_a_function_that_changes_directory_is_refused_and_is_real(
    lab: Path, cmd: str
) -> None:
    check_bypass(lab, cmd, "function")


def test_a_function_with_cd_in_a_nested_shell_body_is_refused(lab: Path) -> None:
    msg = verdict(
        lab,
        "bash -c 'cd sub; f() if cd ../.claude; then :; fi; cd ../sub; f; echo x > settings.json'",
    )
    assert msg is not None


FUNCTION_BENIGN = [
    "f() ( echo hi ); f",
    "f() if true; then echo hi; fi; f",
    "cd sub; ls",
    "cd sub && echo y > x",
    "echo 'f()'; ls",
]


@pytest.mark.parametrize("cmd", FUNCTION_BENIGN)
def test_functions_without_cd_and_cd_without_functions_stay_allowed(lab: Path, cmd: str) -> None:
    assert verdict(lab, cmd) is None, cmd


# --- read-only: documented, not changed -----------------------------------------------------


def test_read_only_recursive_grep_at_the_root_is_still_allowed_by_design(lab: Path) -> None:
    g = guard(lab, "read-only")
    assert g(ToolCall("c", "run", {"command": "grep -rn foo ."})) is None


# --- differential: nothing the guard refused before this round is allowed now ---------------


def _baseline():  # type: ignore[no-untyped-def]
    here = Path(__file__).resolve().parents[1]
    done = subprocess.run(
        ["git", "show", f"{BASE_SHA}:src/master_finhub/tools/permissions.py"],
        cwd=here,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        pytest.skip(f"base commit {BASE_SHA} is not in this clone")
    spec = importlib.util.spec_from_loader("permissions_base", loader=None)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["permissions_base"] = mod
    exec(compile(done.stdout, "permissions_base.py", "exec"), mod.__dict__)  # noqa: S102
    return mod


def _round3_commands() -> list[str]:
    path = Path(__file__).with_name("test_permissions_round3.py")
    spec = importlib.util.spec_from_file_location("round3_cmds", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out: list[str] = []
    for name, value in vars(mod).items():
        if name.isupper() and isinstance(value, (list, tuple)):
            out += [v for v in value if isinstance(v, str) and len(v) > 3]
    return sorted(set(out))


def _generated(n: int) -> list[str]:
    rnd = random.Random(4)
    heads = [
        "cd", "tar -xf", "tar -tf", "unzip", "patch", "git checkout", "git restore", "git reset",
        "git stash", "cp", "mv", "ln -s", "tee", "touch", "cat", "ls", "rm", "echo y >", "sed -i s/a/b/",
        "gunzip", "git apply", "install", "dd of=", "truncate -s 0",
    ]  # fmt: skip
    words = [
        ".claude", ".env", ".git", "sub", "src", "a.tar", "settings.json", ".", "..", "*", "x", "h",
        "--", "-f", "--hard", "pop", "../.claude", ".claude/settings.json", "c", "sub/x", "-C",
    ]  # fmt: skip
    joins = [" && ", "; ", " | ", "\n"]
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(1, 3)):
            parts.append(
                rnd.choice(heads) + " " + " ".join(rnd.choices(words, k=rnd.randint(0, 3)))
            )
        out.append(rnd.choice(joins).join(parts))
    return out


def test_nothing_the_guard_refused_before_this_round_is_allowed_now(lab: Path) -> None:
    base = _baseline()
    old = base.make_mode_guard("workspace-write", Workspace(lab), tool_classes=CLASSES)
    new = guard(lab)
    old_ro = base.make_mode_guard("read-only", Workspace(lab), tool_classes=CLASSES)
    new_ro = guard(lab, "read-only")
    cmds = _round3_commands() + _generated(1500)
    assert len(cmds) > 1500
    lost = []
    for cmd in cmds:
        call = ToolCall("c", "run", {"command": cmd})
        if old(call) is not None and new(call) is None:
            lost.append(("workspace-write", cmd))
        if old_ro(call) is not None and new_ro(call) is None:
            lost.append(("read-only", cmd))
    assert lost == []
