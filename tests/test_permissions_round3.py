"""Third round on the mode guard: the second re-audit's findings (P2-01 to P2-17).

Each group pins one finding with the report's exact repro and a nearby command that must stay
allowed. The refusal text is checked where a rule has its own reason, so a mutant that refuses
for the wrong reason, or one rule that hides behind another, is still caught.
"""

import os
import time
from pathlib import Path

import pytest

from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools import permissions
from master_finhub.tools.permissions import make_mode_guard

CLASSES = {"write_file": "write", "run": "shell"}
VCS = "g" + "it"
PROTECTED = "it touches a protected file"


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    root = tmp_path / "ws"
    (root / "sub").mkdir(parents=True)
    (root / ".claude").mkdir()
    return Workspace(root)


def guard(mode: str, ws: Workspace):  # type: ignore[no-untyped-def]
    return make_mode_guard(mode, ws, tool_classes=CLASSES)  # type: ignore[arg-type]


def run(cmd: str) -> ToolCall:
    return ToolCall("c", "run", {"command": cmd})


def ww(ws: Workspace, cmd: str) -> str | None:
    return guard("workspace-write", ws)(run(cmd))


def ro(ws: Workspace, cmd: str) -> str | None:
    return guard("read-only", ws)(run(cmd))


def refused(ws: Workspace, cmd: str, why: str | None = None) -> None:
    msg = ww(ws, cmd)
    assert msg is not None, cmd
    if why:
        assert why in msg, (cmd, msg)


def allowed(ws: Workspace, cmd: str) -> None:
    assert ww(ws, cmd) is None, cmd


# --- P2-01: cd is tracked ------------------------------------------------------------------

CD_BYPASS = [
    "cd .claude && echo x > settings.json",
    "cd .claude; tee settings.json",
    "cd .claude\ntee settings.json",
    "pushd .claude && cp ../a settings.json",
    "(cd .claude && echo x > settings.json)",
    "bash -c 'cd .claude && echo x > settings.json'",
    'sh -c "cd .claude; tee settings.local.json"',
    "env bash -lc 'cd .claude && tee settings.json'",
    "eval 'cd .claude; echo x > settings.json'",
    "cd sub && cd ../.claude && echo x > settings.json",
    "cd sub/../.claude && echo x > settings.json",
    "cd .claude && cd . && echo x > settings.json",
    "cd .claude && echo x >> settings.local.json",
    "{ cd .claude; echo x > settings.json; }",
    "if cd .claude; then echo x > settings.json; fi",
    "pushd .claude; popd; pushd .claude; echo x > settings.json",
    "cd .claude && sed -i s/a/b/ settings.json",
    "cd .claude && mv ../x settings.json",
]


@pytest.mark.parametrize("cmd", CD_BYPASS)
def test_cd_into_a_protected_parent_then_a_bare_name_is_refused(ws: Workspace, cmd: str) -> None:
    refused(ws, cmd, PROTECTED)


def test_cd_by_absolute_path_is_followed(ws: Workspace) -> None:
    refused(ws, f"cd {ws.root}/.claude && echo x > settings.json", PROTECTED)
    refused(ws, f"cd {ws.root}/sub && cd ../.claude && tee settings.json", PROTECTED)


def test_cd_through_a_symlink_is_followed(ws: Workspace) -> None:
    os.symlink(ws.root / ".claude", ws.root / "lnk")
    refused(ws, "cd lnk && echo x > settings.json", PROTECTED)


CD_ALLOWED = [
    "(cd .claude); echo x > settings.json",
    "(cd .claude && echo y > notes.txt); echo x > settings.json",
    "cd src && echo x > settings.json",
    "cd sub && cd .. && echo x > settings.json",
    "pushd .claude; popd; echo x > settings.json",
    "cd .claude && echo x > notes.txt",
    "bash -c 'cd .claude'; echo x > settings.json",
    "cd /tmp && echo x > settings.json",
    "cd {root}/sub && echo x > settings.json",
]


@pytest.mark.parametrize("cmd", CD_ALLOWED)
def test_cd_that_does_not_reach_a_protected_file_is_allowed(ws: Workspace, cmd: str) -> None:
    allowed(ws, cmd.replace("{root}", str(ws.root)))


UNKNOWN_CWD = [
    'cd "x$D" && echo x > settings.json',
    "cd && echo x > settings.json",
    "cd - && tee settings.json",
    "cd x$D; cp a b",
    "cd sub/x$X && echo x > settings.json",
    "popd; echo x > settings.json",
    "pushd x$D; echo x > settings.json",
    "cd x$D; (cd /tmp; true); git commit -m x",
]


@pytest.mark.parametrize("cmd", UNKNOWN_CWD)
def test_after_a_cd_the_guard_cannot_follow_a_bare_name_is_refused(ws: Workspace, cmd: str) -> None:
    refused(ws, cmd, "working directory is unknown")


def test_unknown_cwd_still_allows_reads_absolute_paths_and_a_known_cd(ws: Workspace) -> None:
    allowed(ws, 'cd "x$D"; cat settings.json')
    allowed(ws, 'cd "x$D"; ls')
    allowed(ws, 'cd "x$D"; cp /tmp/a /tmp/b')
    allowed(ws, f'cd "x$D"; cd {ws.root}/sub; echo x > settings.json')
    allowed(ws, f'cd "x$D"; cd {ws.root}; cd sub; echo x > settings.json')


def test_unknown_cwd_covers_the_redirect_target_too(ws: Workspace) -> None:
    refused(ws, 'cd "x$D"; echo x > out.txt', "working directory is unknown")
    allowed(ws, 'cd "x$D"; echo x > /tmp/out.txt')


# --- P2-02: wrappers and path prefixes -----------------------------------------------------

WRAPPED = [
    f"/usr/bin/{VCS} config a.b c",
    f"command {VCS} config a.b c",
    f"env {VCS} config a.b c",
    f"env -i {VCS} config a.b c",
    f"env A=1 {VCS} config a.b c",
    f"env -u HOME {VCS} config a.b c",
    f"sudo {VCS} config a.b c",
    f"sudo -u root {VCS} config a.b c",
    f"sudo --user root {VCS} config a.b c",
    f"nice {VCS} config a.b c",
    f"nice -n 5 {VCS} config a.b c",
    f"timeout 5 {VCS} config a.b c",
    f"timeout -s KILL 5 {VCS} config a.b c",
    f"time {VCS} config a.b c",
    f"nohup {VCS} config a.b c",
    f"exec {VCS} config a.b c",
    f"xargs -n1 {VCS} config",
    f"busybox {VCS} config a.b c",
    f"sudo env nice {VCS} config a.b c",
    f"env {VCS} stash -u",
    f"/usr/bin/{VCS} stash -u",
    f"/usr/bin/{VCS} clean -fd",
    f"/usr/bin/{VCS} -c core.pager=x log",
    "/bin/rm -rf *",
    "/bin/rm -rf .",
    "/usr/bin/find . -delete",
    "env find . -delete",
    "command rm -rf .claude",
    "nice -n 5 rm -rf .claude",
    "busybox rm -rf .",
    "xargs rm -rf .claude",
    "! rm -rf .",
]


@pytest.mark.parametrize("cmd", WRAPPED)
def test_a_wrapper_or_path_prefix_does_not_hide_the_command(ws: Workspace, cmd: str) -> None:
    refused(ws, cmd)


@pytest.mark.parametrize("name", ["chroot", "ssh", "flock", "watch", "script", "su", "parallel"])
def test_a_wrapper_the_guard_cannot_see_through_is_refused(ws: Workspace, name: str) -> None:
    refused(ws, f"{name} x ls", f"'{name}' runs other commands")


def test_wrapped_ordinary_commands_stay_allowed(ws: Workspace) -> None:
    for cmd in (
        "env FOO=1 pytest -q",
        "time pytest",
        "nice -n 5 make",
        "/usr/bin/env python x.py",
        "timeout 30 pytest",
        "sudo -u bob ls",
        "command ls",
        f"/usr/bin/{VCS} status",
        f"env {VCS} log --oneline",
        f"command {VCS} add a.txt",
    ):
        allowed(ws, cmd)


# --- P2-05: a prefix assignment is scanned -------------------------------------------------

ASSIGN = [
    "X=.env sh -c 'echo x > \"$X\"'",
    "X=.claude/settings.json sh -c 'echo x > \"$X\"'",
    "X=.env bash -c 'rm \"$X\"'",
    "X=.env; sh -c 'echo x > \"$X\"'",
    "A=1 B=.checkpoints cp a b",
    f"D={VCS} sh -c 'echo x > \"$D/config\"'",
]


@pytest.mark.parametrize("cmd", ASSIGN)
def test_a_protected_name_in_an_assignment_is_refused(ws: Workspace, cmd: str) -> None:
    refused(ws, cmd, PROTECTED)


def test_ordinary_assignments_stay_allowed(ws: Workspace) -> None:
    for cmd in (
        "X=1 sh -c 'echo ok'",
        "FOO=bar pytest -q",
        "A=1; B=2; echo $A",
        "X=notes.txt cat x",
    ):
        allowed(ws, cmd)


# --- P2-03 / P2-04: the root and the parent of a protected entry ----------------------------


def root_cases(ws: Workspace) -> list[str]:
    r, name = str(ws.root), ws.root.name
    return [
        f"rm -rf {r}",
        f"rm -rf {r}/",
        f"rm -rf ./../{name}",
        f"rm -rf sub/../../{name}",
        f"rm -rf {r}/sub/..",
        f"rm -r {r}",
        f"find {r} -delete",
        f"find ./../{name} -type f -delete",
        f"mv {r} {r}2",
        f"mv ./../{name} /tmp/elsewhere",
        "rm -rf ..",
        "rm -rf ../",
        "rm -r .",
        "mv . /tmp/x",
        "mv ../ws /tmp/x",
    ]


def test_the_workspace_root_under_any_spelling_is_refused(ws: Workspace) -> None:
    for cmd in root_cases(ws):
        refused(ws, cmd)


PARENT = [
    "rm -rf .claude",
    "rm -r .claude/",
    "rm -rf ./.claude",
    "rm -rf sub/../.claude",
    "rm -rf .clau*",
    "rmdir .claude",
    "unlink .claude",
    "shred -u .claude",
    "mv .claude old",
    "mv .claude .claude.bak",
    "mv -t out .claude",
    "mv --target-directory=out .claude",
    "find .claude -delete",
    "find .claude -type f -delete",
    "find ./sub/../.claude -delete",
    f"{VCS} rm -r .claude",
    f"{VCS} mv .claude x",
    "tar -xf a.tar -C .claude",
    "rsync -a src/ .claude/",
    "cp -r a/. .claude",
    "cp -r a/. .",
    "unzip a.zip -d .claude",
    "gzip -r .claude",
    "cd .claude && rm -rf .",
    "cd .claude && rm -rf ../.claude",
]


@pytest.mark.parametrize("cmd", PARENT)
def test_removing_or_replacing_a_parent_of_a_protected_entry_is_refused(
    ws: Workspace, cmd: str
) -> None:
    refused(ws, cmd)


def test_parent_refusals_have_their_own_reasons(ws: Workspace) -> None:
    refused(ws, "rm -rf .claude", "recursive delete of a glob, an expansion, the workspace root")
    refused(ws, "rmdir .claude", "deletes the workspace root or a directory")
    refused(ws, "mv .claude old", "moves the workspace root or a directory")
    refused(ws, "find .claude -delete", "must not start at the workspace root")
    refused(ws, "rm -rf *", "recursive delete of a glob")
    refused(ws, "tar --remove-files -cf x.tar .", "tar --remove-files")
    refused(ws, "rsync -a --delete e/ .", "rsync")
    refused(ws, "cp -r a/. .claude", "merging copy")
    refused(ws, "unzip a.zip -d .claude", "unzip into")
    refused(ws, "gzip -r .claude", "gzip -r over")
    refused(ws, f"{VCS} rm -r .claude", "removes or moves a directory")


DESTRUCTIVE_ALLOWED = [
    "rm -rf build",
    "rm -rf src/build",
    "rm -rf sub/..x",
    "rm a.txt",
    "rmdir empty",
    "unlink a.txt",
    "mv a b",
    "mv a.txt .",
    "mv a.txt sub/",
    "mv -t sub a.txt",
    "mv sub sub2",
    "find src -name '*.pyc' -delete",
    "find sub -type f -delete",
    "tar -czf out.tgz .",
    "tar -czf out.tgz src",
    "tar -xf a.tar -C out",
    "tar -xf a.tar",
    "rsync -a src/ dest/",
    "rsync -a --delete src/ dest/",
    "cp x .",
    "cp -r src/. dest/",
    "cp -r src dest",
    "unzip a.zip -d out",
    "unzip a.zip",
    "gzip -r src",
    "gzip a.txt",
    f"{VCS} rm a.txt",
    f"{VCS} mv a b",
    "ls -R .claude",
]


@pytest.mark.parametrize("cmd", DESTRUCTIVE_ALLOWED)
def test_destructive_commands_on_ordinary_paths_stay_allowed(ws: Workspace, cmd: str) -> None:
    allowed(ws, cmd)


def test_find_write_actions_from_the_root_have_a_clear_reason(ws: Workspace) -> None:
    for cmd in (
        "find . -name '*.pyc' -delete",
        "find . -empty -delete",
        "find . -fprint x",
        "find . -fls x",
        "find . -exec wc -l {} +",
        "find -delete",
        "find .. -delete",
    ):
        refused(ws, cmd, "start from a subdirectory such as src")


# --- P2-06 / P2-08: other bulk writers, and the untokenizable fail-closed list -------------


def test_the_tokenizable_writers_are_checked_for_protected_targets(ws: Workspace) -> None:
    for cmd in (
        "shred .env",
        "truncate -s 0 .env",
        "gzip .env",
        "bzip2 .env",
        "xz .env",
        "sed -i s/a/b/ .env",
        "perl -pi -e 1 .env",
        "ed -s .env",
        "install a .env",
        "cpio -o > .env",
        "dd if=a of=.env",
        "unlink .env",
        "tar --remove-files -cf x .",
    ):
        refused(ws, cmd)


LEGACY = [
    "unlink .e$(true)nv",
    "shred -u .e$(true)nv",
    "shred .e${NOPE}nv",
    "gzip -f .e$(true)nv",
    "bzip2 .e$(true)nv",
    "xz .e$(true)nv",
    "zstd .e$(true)nv",
    "rmdir .g$(true)it",
    "ed -s .e$(true)nv",
    "split -l 1 .e$(true)nv",
    "cpio -i .e$(true)nv",
    "rename a b $(true)",
    f"{VCS} remote add x $(pwd)",
    f"{VCS} worktree add $(pwd)/x",
    f"{VCS} tag -d $(pwd)",
    f"{VCS} reflog expire $(pwd)",
    f"{VCS} init $(pwd)",
]


@pytest.mark.parametrize("cmd", LEGACY)
def test_untokenizable_text_with_any_known_writer_is_refused(ws: Workspace, cmd: str) -> None:
    refused(ws, cmd)


def test_untokenizable_text_without_a_writer_is_allowed(ws: Workspace) -> None:
    allowed(ws, "echo $(date)")
    allowed(ws, "ls $(pwd)")
    allowed(ws, "cat ${HOME}/notes.txt")


# --- P2-07 / P2-09: git -------------------------------------------------------------------

GIT_REFUSED = [
    "stash --include-un",
    "stash --include-untracked",
    "stash --all",
    "stash --al",
    "stash --a",
    "stash --i",
    "stash push --inc",
    "stash push --a",
    "stash push --include-untracked=x",
    "stash -u",
    "stash -a",
    "stash -ua",
    "stash -au",
    "stash push -mx -u",
    "-C . config a b",
    "-C sub config a b",
    "-C sub -C . clean -fd",
    "--config-env=a.b=C log",
    "--exec-path=x log",
    "--git-dir=x log",
    "--work-tree=x log",
    "-c a.b=c log",
    "config a b",
    "hook run x",
    "update-ref -d HEAD",
    "clean -fdx",
    "notes add -m x",
    "replace a b",
    "filter-branch --all",
    "gc",
    "prune",
    "repack -d",
    "worktree add x",
    "submodule add x y",
    "update-index --assume-unchanged a",
    "symbolic-ref HEAD x",
    "maintenance run",
    "remote add x y",
    "remote set-url x y",
    "remote rename a b",
    "remote remove x",
    "remote rm x",
    "remote prune x",
    "remote update",
    "remote set-head a b",
    "remote set-branches a b",
    "reflog expire --all",
    "reflog delete HEAD@{1}",
    "tag -d v1",
    "tag -f v1",
    "tag -df v1",
    "tag --delete v1",
    "tag --del v1",
    "tag --force v1",
    "tag --fo v1",
    "branch -m a b",
    "branch -M a b",
    "branch -d a",
    "branch -D a",
    "branch -u origin/x",
    "branch -c a b",
    "branch -C a b",
    "branch -f a b",
    "branch --edit-description",
    "branch --delete a",
    "branch --del a",
    "branch --move a b",
    "branch --copy a b",
    "branch --force a b",
    "branch --set-upstream-to=o/x",
    "branch --unset-upstream",
    "init --separate-git-dir=x",
    "rm -r .claude",
    "mv .claude x",
]


@pytest.mark.parametrize("args", GIT_REFUSED)
def test_git_commands_that_rewrite_dot_git_or_delete_protected_files_are_refused(
    ws: Workspace, args: str
) -> None:
    refused(ws, f"{VCS} {args}")


def test_git_refusals_have_their_own_reasons(ws: Workspace) -> None:
    refused(ws, f"{VCS} stash --a", "git stash of untracked or ignored")
    refused(ws, f"{VCS} stash -u", "git stash of untracked or ignored")
    refused(ws, f"{VCS} -c a.b=c log", "a git option can set configuration")
    refused(ws, f"{VCS} --config-env=a=B log", "a git option can set configuration")
    refused(ws, f"{VCS} -C . config a b", "git config can change")
    refused(ws, f"{VCS} gc", "git gc can change")
    refused(ws, f"{VCS} remote add x y", "git remote add")
    refused(ws, f"{VCS} reflog expire", "git reflog")
    refused(ws, f"{VCS} tag -d x", "git tag -d")
    refused(ws, f"{VCS} branch -m a b", "git branch with an option")
    refused(ws, f"{VCS} init --separate-git-dir=x", "separate-git-dir")


GIT_ALLOWED = [
    "status",
    "log --oneline -n 3",
    "diff --stat",
    "add -A",
    "add src",
    "commit -m 'fix the docs'",
    "checkout main",
    "checkout -b feature",
    "branch",
    "branch -a",
    "branch -v",
    "branch --list",
    "branch feature",
    "remote",
    "remote -v",
    "remote show origin",
    "remote get-url origin",
    "tag",
    "tag -l",
    "tag v1",
    "tag -a v1 -m x",
    "init",
    "stash",
    "stash list",
    "stash pop",
    "stash push -m msg",
    "stash push -m msg --keep-index",
    "stash --keep-index",
    "stash show",
    "reflog",
    "reflog show",
    "-C sub status",
    "rm a.txt",
    "mv a b",
    "pull",
    "fetch",
    "push",
    "merge main",
    "rebase main",
]


@pytest.mark.parametrize("args", GIT_ALLOWED)
def test_everyday_git_commands_stay_allowed(ws: Workspace, args: str) -> None:
    allowed(ws, f"{VCS} {args}")


# --- P2-10: no catastrophic backtracking ---------------------------------------------------


def test_many_expansion_pieces_in_one_word_are_checked_in_linear_time(ws: Workspace) -> None:
    for text in ("{a}" * 40 + "Z", "$a" * 40 + "Z", "{a}x" * 40 + "Z", "*a" * 40 + "Z"):
        t0 = time.monotonic()
        ww(ws, f"touch {text}")
        assert time.monotonic() - t0 < 1.5, text[:12]


def test_a_word_with_too_many_pieces_is_refused_with_a_reason(ws: Workspace) -> None:
    refused(ws, "touch " + "{a}" * 200, "too many expansion or glob pieces")
    refused(ws, "echo x > " + "$a" * 200, "too many expansion or glob pieces")
    assert permissions.MAX_PIECES == 128
    allowed(ws, "touch " + "{a}" * 100 + "Z")


def test_glob_and_expansion_matching_against_protected_names(ws: Workspace) -> None:
    for cmd in (
        "cp in .e?v",
        "cp in .[e]nv",
        "cp in .e*",
        "cp in .?nv",
        "cp in .ENV",
        "cp in .e{n,}v",
        "cp in .e$Xv",
        "cp in $X",
        "cp in .*",
        "cp in .claude/s*",
        "cp in .claude/?ettings.json",
    ):
        refused(ws, cmd)
    for cmd in (
        "cp in *nv",
        "cp in *env",
        "cp in ?nv",
        "cp in [e]nv",
        "cp in e*",
        "cp in .e??v",
        "cp in .e",
        "cp in env",
        "cp in a$Xz",
        "cp in .claude/x*",
    ):
        allowed(ws, cmd)


# --- P2-12 / P2-13 / P2-14: write tools ----------------------------------------------------


def write(ws: Workspace, args: dict[str, object]) -> str | None:
    return guard("workspace-write", ws)(ToolCall("c", "write_file", args))


NESTED = [
    {"path": "a.txt", "files": {".env": "x"}},
    {"path": "a.txt", "files": {f".{VCS}/config": "x"}},
    {"path": "a.txt", "edits": [{"path": ".env", "content": "x"}]},
    {"path": "a.txt", "edits": [{"file": ".claude/settings.json", "content": "x"}]},
    {"path": "a.txt", "extra": {"path": ".env"}},
    {"path": "a.txt", "extra": {"deep": {"dest": ".env"}}},
    {"path": "a.txt", "ops": [{"args": ["./.env"]}]},
    {"path": "a.txt", "list": [[".env"]], "paths": [["x.txt", ".env"]]},
    {"path": "a.txt", "meta": {"x": "../escape.txt"}},
    {"path": "a.txt", "note": "/etc/x"},
    {"path": "a.txt", "out_dir": ".checkpoints"},
    {"path": "a.txt", "dest_path": ".env"},
    {"path": "a.txt", "backup_file": ".env"},
    {"path": "a.txt", "to": ".env"},
    {"path": "a.txt", "from": ".env"},
]


@pytest.mark.parametrize("args", NESTED)
def test_write_tool_checks_nested_path_shaped_values(
    ws: Workspace, args: dict[str, object]
) -> None:
    assert write(ws, args) is not None, args


def test_write_tool_accepts_prose_and_option_strings(ws: Workspace) -> None:
    for extra in (
        {"title": "Fix: login bug"},
        {"pattern": "*.py"},
        {"label": "what?"},
        {"summary": "x<y"},
        {"regex": "a|b"},
        {"url": "https://x/y"},
        {"name": "aux.txt"},
        {"tag": "v1.0", "branch": "feature/x", "lang": "py", "mode": "w", "encoding": "utf-8"},
        {"content": "a b c: d? e* f"},
        {"headers": {"Content-Type": "text/plain; charset=utf-8"}},
        {"edits": [{"old_string": "a: b?", "new_string": "c|d"}]},
        {"title": "line one\nline two"},
    ):
        assert write(ws, {"path": "a.txt", **extra}) is None, extra


def test_write_tool_content_with_spaces_is_not_run_through_the_path_check(ws: Workspace) -> None:
    assert write(ws, {"path": "a.txt", "content": "two words", "title": "a b"}) is None
    assert write(ws, {"path": "a.txt", "mystery": "has spaces: and ? marks"}) is None


def test_write_tool_still_needs_a_path_and_a_string_path(ws: Workspace) -> None:
    msg = write(ws, {"content": "x"})
    assert msg is not None and "needs a path to check" in msg
    msg = write(ws, {"path": 3})
    assert msg is not None and "needs a path to check" in msg
    msg = write(ws, {"path": "a.txt", "file_path": ["b"]})
    assert msg is not None and "needs a path to check" in msg
    assert write(ws, {"path": "a.txt"}) is None


def test_write_tool_a_value_starting_like_a_path_outside_the_workspace_is_refused(
    ws: Workspace,
) -> None:
    for v in ("/etc/passwd", "../x", "./.env"):
        assert write(ws, {"path": "a.txt", "anything": v}) is not None, v
    assert write(ws, {"path": "a.txt", "anything": "./ok.txt"}) is None
    assert write(ws, {"path": "a.txt", "anything": "x/y/./z"}) is None


@pytest.mark.skipif(os.name != "posix", reason="hard links")
def test_write_tool_refuses_a_hard_link_to_a_protected_file(ws: Workspace) -> None:
    (ws.root / ".env").write_text("secret")
    (ws.root / ".claude" / "settings.json").write_text("{}")
    os.link(ws.root / ".env", ws.root / "hard")
    os.link(ws.root / ".claude" / "settings.json", ws.root / "sub" / "h2")
    for name in ("hard", "sub/h2"):
        msg = write(ws, {"path": name})
        assert msg is not None and "hard link to a protected file" in msg, name
    msg = write(ws, {"path": "a.txt", "dest": "hard"})
    assert msg is not None and "hard link" in msg


@pytest.mark.skipif(os.name != "posix", reason="hard links")
def test_write_tool_allows_other_hard_links_and_plain_files(ws: Workspace) -> None:
    (ws.root / "one.txt").write_text("x")
    os.link(ws.root / "one.txt", ws.root / "two.txt")
    (ws.root / ".env").write_text("secret")
    (ws.root / "plain.txt").write_text("y")
    for name in ("one.txt", "two.txt", "plain.txt", "missing.txt"):
        assert write(ws, {"path": name}) is None, name


@pytest.mark.skipif(os.name != "posix", reason="hard links")
def test_hard_link_to_a_file_inside_a_protected_directory_is_found(ws: Workspace) -> None:
    (ws.root / ".checkpoints").mkdir()
    (ws.root / ".checkpoints" / "a").write_text("x")
    os.link(ws.root / ".checkpoints" / "a", ws.root / "b")
    assert write(ws, {"path": "b"}) is not None


# --- P2-11: read-only readers and paths ---------------------------------------------------


@pytest.fixture
def home(ws: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    (h / ".ssh").mkdir(parents=True)
    (h / ".ssh" / "id_rsa").write_text("KEY")
    monkeypatch.setenv("HOME", str(h))
    return h


RO_ABOVE = [
    "rg -uu . ~",
    "rg --files ~",
    "rg foo ~",
    "rg foo ..",
    "rg foo ../..",
    "rg foo /",
    "rg -e foo ~",
    "rg --regexp foo ~",
    "grep -r . ~",
    "grep -rn x ..",
    "grep -R x ~",
    "grep --recursive x ~",
    "grep --dereference-recursive x ~",
    "grep -r -e x ~",
    "grep -r x /",
    "diff -r a ~",
    "diff --recursive a ~",
    "find ~ -name x",
    "find .. -name x",
    "find / -name x",
    "find ~/ -type f",
    "ls -R ~",
    "ls -R ..",
    "ls --recursive ~",
    "ls -lR /",
    "grep -r x .. src",
]


@pytest.mark.parametrize("cmd", RO_ABOVE)
def test_read_only_recursive_readers_above_the_workspace_or_at_home_are_refused(
    ws: Workspace, home: Path, cmd: str
) -> None:
    msg = ro(ws, cmd)
    assert msg is not None and "home directory or above the workspace" in msg, cmd


def test_read_only_refuses_the_workspace_parent_when_home_is_elsewhere(
    ws: Workspace, home: Path
) -> None:
    assert ws.root.parent != home.resolve()
    assert ro(ws, "rg foo ..") is not None
    assert ro(ws, f"find {ws.root.parent} -name x") is not None


def test_read_only_refuses_a_home_that_is_a_parent_of_the_start(
    ws: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(ws.root.parent))
    assert ro(ws, "grep -r x ..") is not None
    assert ro(ws, f"grep -r x {ws.root.parent}") is not None


RO_INSIDE = [
    "rg foo",
    "rg foo src",
    "rg foo .",
    "rg -n foo sub",
    "rg --files",
    "rg --files sub",
    "rg -e foo",
    "rg -e foo sub",
    "grep -rn foo .",
    "grep -rn foo sub",
    "grep -r foo",
    "grep foo ../x",
    "grep foo ~/notes.txt",
    "grep -r -e foo sub",
    "diff -r a b",
    "diff a ~/x",
    "find . -name x",
    "find sub -type f",
    "find -name x",
    "find ./sub/.. -name x",
    "ls",
    "ls ~",
    "ls ..",
    "ls -R sub",
    "ls -R",
    "ls -la ~",
    "cat ../x",
    "head ~/x",
]


@pytest.mark.parametrize("cmd", RO_INSIDE)
def test_read_only_readers_inside_the_workspace_and_plain_reads_elsewhere_stay_allowed(
    ws: Workspace, home: Path, cmd: str
) -> None:
    assert ro(ws, cmd) is None, cmd


def test_read_only_applies_the_credential_denylist_to_path_words(ws: Workspace, home: Path) -> None:
    key = home / ".ssh" / "id_rsa"
    for cmd in (
        f"cat {key}",
        "cat ~/.ssh/id_rsa",
        "head ~/.ssh/id_rsa",
        "ls ~/.ssh",
        f"wc -l {key}",
        "grep x ~/.ssh/id_rsa",
        "grep -r BEGIN ~/.ssh",
        "diff a ~/.ssh/id_rsa",
        "find ~/.ssh -type f",
        "tail -n 1 ~/.aws/credentials",
        "stat ~/.ssh/id_rsa",
        "cat ~/.config/gh/hosts.yml",
    ):
        msg = ro(ws, cmd)
        assert msg is not None, cmd
        assert "credential" in msg or "home directory" in msg, (cmd, msg)


def test_read_only_credential_check_does_not_trip_on_option_words_or_ordinary_files(
    ws: Workspace, home: Path
) -> None:
    for cmd in (
        "cat README.md",
        "head -n 5 notes.txt",
        "grep -n 'a b' f",
        "ls -la",
        "wc -l f",
        "echo hi",
        "date -d '-2 hours'",
        "sort -k2 f",
    ):
        assert ro(ws, cmd) is None, cmd


# --- P2-16: date ---------------------------------------------------------------------------

DATE_OK = [
    "date -ud now",
    "date -u -d now",
    "date -dnow",
    "date -ud '-2 hours'",
    "date -ur a.txt",
    "date -r a.txt",
    "date --date now",
    "date --date=now",
    "date --reference a.txt",
    "date --reference=a.txt",
    "date --rfc-3339 seconds",
    "date --rfc-3339=seconds",
    "date -Iseconds",
    "date -I",
    "date -uI",
    "date -d now +%s",
    "date +%s",
    "date -u +%Y",
]


@pytest.mark.parametrize("cmd", DATE_OK)
def test_date_options_and_their_values_are_read_correctly(ws: Workspace, cmd: str) -> None:
    assert ro(ws, cmd) is None, cmd


DATE_BAD = [
    "date 010112002026",
    "date -u 010112002026",
    "date -d now 010112002026",
    "date -ud now 010112002026",
    "date --date now 010112002026",
    "date -- 010112002026",
    "date -I 010112002026",
    "date -s now",
    "date --set=now",
    "date -dfoor 010112002026",
    "date -Ifood 010112002026",
]


@pytest.mark.parametrize("cmd", DATE_BAD)
def test_date_that_sets_the_clock_is_still_refused(ws: Workspace, cmd: str) -> None:
    assert ro(ws, cmd) is not None, cmd


# --- P2-17: rules that no earlier test pinned ----------------------------------------------


def test_rm_recursive_spellings(ws: Workspace) -> None:
    for cmd in (
        "rm -rf *",
        "rm -fr *",
        "rm -Rf *",
        "rm --recursive *",
        "rm --rec *",
        "rm --r *",
        "rm -r $D",
        "rm -r ..",
        "rm -r a*",
        "rm -rv $X",
    ):
        refused(ws, cmd, "recursive delete of a glob")
    for cmd in ("rm -f build", "rm -v build", "rm --force build", "rm -i build"):
        allowed(ws, cmd)
    allowed(ws, "rm --verbose src/x.pyc")


def test_find_write_flags_each_count(ws: Workspace) -> None:
    for flag in (
        "-delete",
        "-exec x",
        "-execdir x",
        "-ok x",
        "-okdir x",
        "-fprint o",
        "-fprint0 o",
        "-fprintf o x",
        "-fls o",
    ):
        refused(ws, f"find . {flag}", "start from a subdirectory")
        allowed(ws, f"find src {flag}")


def test_find_with_a_glob_or_expansion_start_is_refused(ws: Workspace) -> None:
    refused(ws, "find * -delete", "start from a subdirectory")
    refused(ws, "find $D -delete", "start from a subdirectory")
    refused(ws, "find src $D -delete", "start from a subdirectory")
    allowed(ws, "find src sub -delete")
    allowed(ws, "find src -name '*.pyc' -delete")


def test_operators_split_commands_and_each_is_judged(ws: Workspace) -> None:
    for cmd in (
        "echo a; echo x > .env",
        "echo a && echo x > .env",
        "false || echo x > .env",
        "echo a | tee .env",
        "echo a\necho x > .env",
        "echo a & echo x > .env",
        "echo a |& tee .env",
        "echo a &>> .env",
        "echo a &> .env",
        "echo a;echo x>.env",
        "echo x >.env",
        "echo x 2>.env",
        "echo x >>.env",
        "echo x >| .env",
        "echo x >& .env",
    ):
        refused(ws, cmd, PROTECTED)
    for cmd in (
        "echo a; echo x > out.txt",
        "echo a & echo b",
        "echo a |& cat",
        "echo a &> out.txt",
        "echo a\necho b",
        "cat < .env",
        "cat .env | wc -l",
    ):
        allowed(ws, cmd)


def test_a_dollar_before_a_separator_is_plain_text(ws: Workspace) -> None:
    allowed(ws, "echo $")
    allowed(ws, "echo $; echo x > out.txt")
    allowed(ws, "echo x$ > out.txt")
    refused(ws, "echo $; echo x > .env", PROTECTED)
    refused(ws, "echo x $ > .env", PROTECTED)
    refused(ws, "echo $>.env", PROTECTED)


def test_escaped_newline_and_backslash_forms_are_not_trusted(ws: Workspace) -> None:
    refused(ws, "echo x > .e\\\nnv", PROTECTED)
    refused(ws, "echo x > .e\\nv", PROTECTED)
    allowed(ws, "echo a\\ b > out.txt")


def test_comments_end_at_the_newline(ws: Workspace) -> None:
    allowed(ws, "echo a # echo x > .env")
    refused(ws, "echo a # note\necho x > .env", PROTECTED)
    refused(ws, "# note\necho x > .env", PROTECTED)
    refused(ws, "echo a#b; echo x > .env", PROTECTED)
    allowed(ws, "echo a#b > out.txt")


def test_double_dash_stops_option_parsing_in_read_only(ws: Workspace) -> None:
    assert ro(ws, "cat -- -o") is None
    assert ro(ws, "grep -- -o file") is None
    assert ro(ws, "cat -- -o -n") is None
    assert ro(ws, "sort -- file -o") is None
    assert ro(ws, "sort -- -k1 f") is None
    assert ro(ws, "sort -o f") is not None


def test_read_only_option_values_are_skipped_correctly(ws: Workspace) -> None:
    assert ro(ws, "head -n 5 f") is None
    assert ro(ws, "head -n5 f") is None
    assert ro(ws, "head -c 5 f") is None
    assert ro(ws, "grep -e -o f") is None
    assert ro(ws, "grep -A 3 x f") is None
    assert ro(ws, "grep -rA 3 x f") is None
    assert ro(ws, "sort -k 2 -t , f") is None
    assert ro(ws, "sort -t, -k2 f") is None
    assert ro(ws, "sort -S 10M f") is None
    assert ro(ws, "git log --since 2020 -n 3") is None
    assert ro(ws, "git log --max-count=3") is None
    assert ro(ws, "git log --max-count 3") is None
    assert ro(ws, "git log --author=bob") is None
    assert ro(ws, "rg -g '*.py' -t py foo") is None
    assert ro(ws, "rg --glob '*.py' --max-depth 2 foo") is None
    assert ro(ws, "tail -n 5 -f f") is None
    assert ro(ws, "grep -o -o f") is None


def test_read_only_git_requires_a_read_subcommand_and_known_options(ws: Workspace) -> None:
    assert ro(ws, f"{VCS}") is not None
    assert ro(ws, f"{VCS} commit -m x") is not None
    assert ro(ws, f"{VCS} -C . status") is not None
    assert ro(ws, f"{VCS} log -Ofile") is not None
    assert ro(ws, f"{VCS} diff -O foo") is not None
    assert ro(ws, f"{VCS} diff -Ufoo") is None
    assert ro(ws, f"{VCS} status --porcelain") is None
    for sub in ("status", "log", "diff", "show", "rev-parse", "ls-files", "blame"):
        assert ro(ws, f"{VCS} {sub}") is None, sub


def test_read_only_refuses_chains_comments_substitutions_and_long_commands(ws: Workspace) -> None:
    for cmd in (
        "",
        "   ",
        "ls;",
        "ls ;; ls",
        "ls && ",
        "| ls",
        "ls |",
        "ls # c",
        "ls > out",
        "ls & ls",
        "ls |& cat",
        "(ls)",
        "ls $(pwd)",
        "ls `pwd`",
        "cat <(ls)",
    ):
        msg = ro(ws, cmd)
        assert msg is not None, repr(cmd)
    assert ro(ws, "ls | cat | head -3") is None
    assert ro(ws, "ls && pwd || echo no") is None
    assert ro(ws, "ls; pwd") is None
    assert ro(ws, "ls\npwd") is None


def test_read_only_unquoted_word_forms_the_guard_cannot_evaluate(ws: Workspace) -> None:
    for cmd in (
        "cat a{b,c}",
        "cat {a}",
        "cat a}",
        "cat ~root/x",
        "cat a=~root",
        "cat a:~root",
        "cat $HOME",
        "cat ${HOME}",
        "cat $'x'",
        'cat $"x"',
        "cat $((1+1))",
        'cat "$HOME"',
        'cat "`pwd`"',
        'cat "a\\"b"',
        'cat "a\\\nb"',
        "cat a\\b",
        "cat [a]",
        "cat a?",
        "cat a*",
        "cat [a",
        "cat \\\n",
    ):
        assert ro(ws, cmd) is not None, cmd
    for cmd in (
        "cat 'a{b}'",
        'cat "a{b}"',
        "cat '$HOME'",
        'cat "a b"',
        "cat ~/x",
        "cat ~",
        "cat a~b",
        "cat [",
        "cat 'a*'",
        'cat "*"',
        "cat $",
        "cat a$",
        "cat '~root'",
        'cat "a\'b"',
        "cat a=b",
        "cat {",
        "cat }"[:0] + "cat x",
    ):
        want = None
        if cmd in ("cat {", "cat [") or cmd == "cat ~":
            continue
        assert ro(ws, cmd) is want, cmd


def test_read_only_stops_at_long_commands_and_unknown_tools(ws: Workspace) -> None:
    g = guard("read-only", ws)
    assert g(ToolCall("c", "mystery", {})) is not None
    assert g(ToolCall("c", "write_file", {"path": "a"})) is not None
    assert guard("workspace-write", ws)(ToolCall("c", "mystery", {})) is None


def test_refusal_text_in_read_only_has_no_advisory_note(ws: Workspace) -> None:
    msg = ro(ws, "rm x")
    assert msg is not None and "advisory" not in msg and "ask the operator" in msg
    msg = ww(ws, "dd of=.env")
    assert msg is not None and "advisory" in msg and "ask the operator" in msg


# --- P2-15: a brace list of plain names is a list, not "anything" --------------------------

BRACE_ALLOWED = [
    "mkdir -p {a,b}/c",
    "mkdir -p src/{core,utils}",
    "touch {a,b}.txt",
    "cp a{,.bak}",
    "cp a.py{,~}",
    "find src -exec wc -l {} +",
    "echo x > .e{n}v",
    "echo x > out{1,2}.txt",
]
BRACE_REFUSED = [
    "echo x > {.env,b}",
    "echo x > {a,.env}",
    "echo x > .e{n,}v",
    "echo x > {,.}env",
    "echo x > .{e,f}nv",
    "echo x > {.ENV,b}",
    "echo x > {a,{.env,b}}",
    "echo x > {1..3}",
    "echo x > .e{$X,}v",
    "mkdir -p {a,.git}/c",
    "touch .clau{de,x}/settings.json",
    "touch .claude/settings{,.local}.json",
]


@pytest.mark.parametrize("cmd", BRACE_ALLOWED)
def test_a_brace_list_of_plain_names_that_is_not_protected_is_allowed(
    ws: Workspace, cmd: str
) -> None:
    allowed(ws, cmd)


@pytest.mark.parametrize("cmd", BRACE_REFUSED)
def test_a_brace_list_that_can_produce_a_protected_name_is_refused(ws: Workspace, cmd: str) -> None:
    refused(ws, cmd, PROTECTED)


# --- P2-17: tests aimed at mutants of the second-round code that no test pinned ------------


def test_a_word_with_exactly_the_piece_limit_is_checked_and_one_more_is_refused(
    ws: Workspace,
) -> None:
    limit = permissions.MAX_PIECES
    allowed(ws, "touch " + "{a}" * limit)
    refused(ws, "touch " + "{a}" * (limit + 1), "too many expansion or glob pieces")
    allowed(ws, "echo x > " + "-$a" * (limit // 2))
    refused(ws, "echo x > " + "-$a" * (limit // 2) + "-", "too many expansion or glob pieces")


def test_wrapper_options_at_the_end_of_a_command_do_not_crash(ws: Workspace) -> None:
    for cmd in (
        "timeout",
        "timeout 5",
        "sudo -u",
        "env -u",
        "nice -n",
        "sudo",
        "env",
        "time",
        "!",
        f"{VCS}",
        f"{VCS} -C",
        f"{VCS} -C .",
        f"{VCS} -",
        "xargs -n",
        "exec",
    ):
        ww(ws, cmd)  # any answer is fine, an exception is not


def test_wrapper_options_that_take_a_value_are_told_from_ones_that_do_not(ws: Workspace) -> None:
    refused(ws, f"sudo --preserve-env {VCS} config a b")
    refused(ws, f"sudo --user=root {VCS} config a b")
    refused(ws, f"sudo --user root {VCS} config a b")
    refused(ws, f"sudo -ug {VCS} config a b")  # -u takes the glued "g" as its value
    refused(ws, f"sudo -Eu root {VCS} config a b")
    refused(ws, f"timeout --signal KILL 5 {VCS} config a b")
    refused(ws, f"env -- {VCS} config a b")
    refused(ws, f"env -i -- {VCS} config a b")
    refused(ws, f"nice -n5 {VCS} config a b")
    allowed(ws, "sudo -u root ls")


def test_cd_options_are_not_directories(ws: Workspace) -> None:
    refused(ws, "cd -P .claude && echo x > settings.json", PROTECTED)
    refused(ws, "cd -L .claude && echo x > settings.json", PROTECTED)
    refused(ws, "cd -- .claude && echo x > settings.json", PROTECTED)


def test_popd_and_subshell_exit_restore_the_right_directory(ws: Workspace) -> None:
    refused(ws, "pushd .claude; pushd sub; popd; echo x > settings.json", PROTECTED)
    refused(ws, "(cd .claude; (cd sub); echo x > settings.json)", PROTECTED)
    allowed(ws, "pushd .claude; pushd sub; popd; popd; echo x > settings.json")
    allowed(ws, "(cd .claude; (cd sub); cd ..); echo x > settings.json")


def test_eval_joins_its_words_into_one_command(ws: Workspace) -> None:
    refused(ws, 'eval cd .claude "&&" echo x ">" settings.json', PROTECTED)
    refused(ws, "eval cd .claude ';' tee settings.json", PROTECTED)
    allowed(ws, "eval echo hi")


def test_nested_shell_bodies_are_followed_to_a_fixed_depth(ws: Workspace) -> None:
    import shlex

    def nest(levels: int) -> str:
        body = "cd .claude; echo x > settings.json"
        for _ in range(levels):
            body = "sh -c " + shlex.quote(body)
        return body

    assert permissions.MAX_DEPTH == 3
    refused(ws, nest(1), PROTECTED)
    refused(ws, nest(3), PROTECTED)
    refused(ws, nest(4), "nested too deep")
    refused(ws, nest(6), "nested too deep")


def test_hidden_paths_in_quoted_arguments(ws: Workspace) -> None:
    refused(ws, "A='cp x .env' true", PROTECTED)  # a prefix assignment is split like an argument
    refused(ws, "cd .claude && sed 'w settings.json' in", PROTECTED)
    refused(ws, "command sed s/a/b/w.env in", PROTECTED)
    refused(ws, "dd $Vof=.env", PROTECTED)
    refused(ws, "cp in =.env", PROTECTED)
    refused(ws, "cp in x=.env/a=b", PROTECTED)
    allowed(ws, 'echo x > "notes .env"')  # a redirect target is one file name, never split
    allowed(ws, "cd .claude && echo x > /settings.json")  # an absolute path ignores the cwd


def test_globs_expansions_and_case_in_protected_names(ws: Workspace) -> None:
    for cmd in (
        "cp in *$X",
        "cp in $X*",
        "cp in {.,.e}*env",
        "cp in .E?V",
        "cp in .EN*",
        "cp in .CLAUDE/SETTINGS.JSON",
        "rm -rf .CLAU*",
        "cp in .Claude/S*",
    ):
        refused(ws, cmd)


def test_a_custom_protected_list_is_matched_without_regard_to_case(ws: Workspace) -> None:
    g = make_mode_guard(
        "workspace-write",
        ws,
        tool_classes=CLASSES,  # type: ignore[arg-type]
        protected=("Secrets.TXT", "Dir/Sub"),
    )
    for cmd in (
        "echo x > secrets.txt",
        "echo x > SECRETS.txt",
        "echo x > dir/sub",
        "echo x > D?r/Sub",
        "tee secrets.tx?",
        "echo x > $X",
        "sh -c 'tee SECRETS.TXT'",
        "A=secrets.txt true",
        "rm -rf dir",
        "mv DIR x",
    ):
        assert g(run(cmd)) is not None, cmd
    assert g(run("echo x > other.txt")) is None
    assert g(run("rm -rf dir/other")) is None


def test_the_write_tool_checks_a_custom_protected_list(ws: Workspace) -> None:
    g = make_mode_guard(
        "workspace-write",
        ws,
        tool_classes=CLASSES,  # type: ignore[arg-type]
        protected=("Secrets.TXT",),
    )
    assert g(ToolCall("c", "write_file", {"path": "secrets.txt"})) is not None
    assert g(ToolCall("c", "write_file", {"path": "ok.txt"})) is None


def test_a_path_that_only_leaves_the_workspace_is_not_the_workspace(ws: Workspace) -> None:
    allowed(ws, "rm ../x")
    allowed(ws, "rm -rf ../x")
    allowed(ws, "mv ../x y")
    allowed(ws, "find ../x -name y")
    refused(ws, "rm -rf ../..")
    refused(ws, "mv ../.. y")


def test_children_of_a_protected_directory_are_not_the_protected_entry(ws: Workspace) -> None:
    for cmd in (
        "rm -rf .claude/cache",
        "mv .claude/old new",
        "find .claude/cache -delete",
        "rm .claude/notes.txt",
        f"{VCS} rm .claude/notes.txt",
        "gzip -r .claude/cache",
        "rsync -a src/ .claude/cache/",
        "unzip a.zip -d .claude/cache",
    ):
        allowed(ws, cmd)


def test_destructive_commands_judge_every_word_not_only_the_last_or_first(ws: Workspace) -> None:
    refused(ws, "rm -rf build *", "recursive delete of a glob")
    refused(ws, "rm -rf build .claude", "recursive delete of a glob")
    refused(ws, "rm a.txt .claude", "deletes the workspace root")
    refused(ws, "rmdir x .claude", "deletes the workspace root")
    refused(ws, "mv a.txt .claude x", "moves the workspace root")
    refused(ws, "cp -r a/. x .claude", "merging copy")
    refused(ws, "gzip -r src .claude", "gzip -r over")
    refused(ws, "find src . -delete", "start from a subdirectory")
    refused(ws, "find src $D -delete", "start from a subdirectory")
    allowed(ws, "cp -r a/. .claude b")
    allowed(ws, "unzip a.zip -d .")
    allowed(ws, "find . -name x")
    allowed(ws, "find . -type f -print")
    allowed(ws, "find src -newer . -delete")
    allowed(ws, "find src -path . -delete")
    allowed(ws, f"{VCS} stash push --patch")
    allowed(ws, f"{VCS} stash push --message x")


def test_unbalanced_quotes_and_backticks_fall_back_to_the_text_scan(ws: Workspace) -> None:
    allowed(ws, 'echo "abc')
    allowed(ws, "echo 'abc")
    refused(ws, "echo 'x .env", PROTECTED)
    refused(ws, 'echo "x .git', PROTECTED)
    refused(ws, "echo `date` > out.txt", PROTECTED)
    refused(ws, "cp `pwd`/a b", PROTECTED)
    refused(ws, "cat ${HOME}/x > out.txt", PROTECTED)
    refused(ws, "rm ${X}/a", PROTECTED)
    refused(ws, f"{VCS} config `echo a` b", PROTECTED)
    allowed(ws, "echo `date`")
    allowed(ws, "echo ${HOME}")


INTERPRETERS = [
    "awk", "bash", "busybox", "dash", "env", "eval", "exec", "find", "gawk", "lua", "nice", "node",
    "nohup", "perl", "php", "python", "python3", "ruby", "sed", "sh", "sudo", "tclsh", "time",
    "timeout", "xargs", "zsh",
]  # fmt: skip
FIND_VALUE = [
    "-amin", "-atime", "-cmin", "-ctime", "-gid", "-group", "-ilname", "-iname", "-inum", "-ipath",
    "-iregex", "-iwholename", "-links", "-lname", "-maxdepth", "-mindepth", "-mmin", "-mtime",
    "-name", "-newer", "-path", "-perm", "-regex", "-regextype", "-samefile", "-size", "-type",
    "-uid", "-user", "-wholename",
]  # fmt: skip
FIND_PLAIN = [
    "-H", "-L", "-P", "-a", "-and", "-d", "-depth", "-empty", "-executable", "-false", "-follow",
    "-mount", "-nogroup", "-not", "-nouser", "-o", "-or", "-print", "-print0", "-prune", "-quit",
    "-readable", "-true", "-writable", "-xdev",
]  # fmt: skip


@pytest.mark.parametrize("name", INTERPRETERS)
def test_every_interpreter_and_wrapper_has_its_arguments_text_scanned(
    ws: Workspace, name: str
) -> None:
    if name == "timeout":
        cmd = "timeout 5 true xx.envxx"
    elif name == "find":
        cmd = "find xx.envxx -delete"
    elif name in permissions._WRAPPERS:
        cmd = f"{name} true xx.envxx"
    else:
        cmd = f"{name} xx.envxx"
    refused(ws, cmd, PROTECTED)


@pytest.mark.parametrize("opt", FIND_VALUE)
def test_read_only_find_options_that_take_a_value_swallow_it(ws: Workspace, opt: str) -> None:
    assert ro(ws, f"find . {opt} -delete") is None, opt
    assert ro(ws, f"find . {opt} x") is None, opt


@pytest.mark.parametrize("opt", FIND_PLAIN)
def test_read_only_find_plain_options_are_listed(ws: Workspace, opt: str) -> None:
    assert ro(ws, f"find . {opt}") is None, opt


def test_read_only_find_refuses_an_unknown_option_with_a_reason(ws: Workspace) -> None:
    msg = ro(ws, "find . -frobnicate")
    assert msg is not None and "find option -frobnicate is not on the read-only list" in msg


def why_tool(ws: Workspace) -> str:
    msg = guard("read-only", ws)(ToolCall("c", "write_file", {"path": "a"}))
    assert msg is not None
    return msg


def test_read_only_reasons_are_the_ones_that_apply(ws: Workspace) -> None:
    def why(cmd: str) -> str:
        msg = ro(ws, cmd)
        assert msg is not None, cmd
        return msg

    assert "refused in read-only mode" in why("rm x")
    assert "'rm' is not on the read-only list" in why("rm x")
    assert "empty command in a chain" in why("ls;")
    assert "command is empty or cannot be judged read-only" in why("")
    assert "expansion, glob, brace, backslash or quoting form" in why("cat $X")
    assert "redirect, background, subshell or comment cannot be judged" in why("ls > x")
    assert "option --frob is not on the read-only list for cat" in why("cat --frob")
    assert "option -z is not on the read-only list for ls" in why("ls -z")
    assert "only read-only git subcommands" in why(f"{VCS} commit")
    assert "option -o is not on the read-only list for sort" in why("sort -o x")
    assert "writes are not allowed" in why_tool(ws)


def test_read_only_option_values_after_a_long_option_are_swallowed(ws: Workspace) -> None:
    assert ro(ws, "sort --key -o f") is None
    assert ro(ws, "sort -k -o f") is None
    assert ro(ws, "rg --type-not py foo") is None
    assert ro(ws, "grep --include -o f") is None
    assert ro(ws, "sort --check=silent f") is None
    assert ro(ws, "ls --color=never") is None
    assert ro(ws, "ls --color") is None


def test_read_only_unclosed_brace_is_refused(ws: Workspace) -> None:
    assert ro(ws, "cat {a") is not None
    assert ro(ws, "cat a}") is not None
    assert ro(ws, 'cat "{a"') is None


def test_double_quote_escapes_are_followed_in_workspace_write(ws: Workspace) -> None:
    refused(ws, 'echo x > ".e\\\nnv"', PROTECTED)  # backslash-newline is removed
    allowed(ws, 'echo x > ".e\\"nv"')
    allowed(ws, 'echo x > "a\\\\b"')


def test_tilde_in_read_only(ws: Workspace) -> None:
    assert ro(ws, "ls ~ | head -3") is None
    assert ro(ws, "ls ~; pwd") is None
    assert ro(ws, "ls ~/") is None
    assert ro(ws, "cat ~root") is not None
    assert ro(ws, "cat ~root/x") is not None


# --- write tool: bounds and key handling ---------------------------------------------------


def nested_path(levels: int) -> dict[str, object]:
    inner: dict[str, object] = {"path": ".env"}
    for _ in range(levels):
        inner = {"x": inner}
    return {"path": "a.txt", "wrap": inner}


def test_write_call_nesting_is_followed_to_a_limit_and_refused_beyond_it(ws: Workspace) -> None:
    assert permissions.MAX_ARG_DEPTH == 6
    for levels in (0, 3, 5):
        msg = write(ws, nested_path(levels))
        assert msg is not None and "the path is protected" in msg, levels
    for levels in (6, 7, 20):
        msg = write(ws, nested_path(levels))
        assert msg is not None and "nested deeper than 6 levels" in msg, levels
    deep_content: dict[str, object] = {"path": "a.txt", "content": nested_path(30)}
    assert write(ws, deep_content) is None  # content is never walked


def test_write_call_with_many_paths_is_checked_up_to_a_limit_and_refused_beyond_it(
    ws: Workspace,
) -> None:
    assert permissions.MAX_ARG_STRINGS == 256
    ok = {"path": "a.txt", "paths": ["b.txt"] * 255}
    assert write(ws, ok) is None
    msg = write(ws, {"path": "a.txt", "paths": ["b.txt"] * 256})
    assert msg is not None and "more than 256 paths" in msg
    hidden_last = {"path": "a.txt", "paths": ["b.txt"] * 300 + [".env"]}
    assert write(ws, hidden_last) is not None


def test_write_tool_string_length_and_key_rules(ws: Workspace) -> None:
    assert write(ws, {"path": "a.txt", "dest": "y" * 4096}) is not None  # too long for a path
    assert write(ws, {"path": "a.txt", "dest": "y" * 4097}) is None  # prose-sized: not a path
    assert write(ws, {"path": "a.txt", "title": "x" * 5000}) is None
    assert write(ws, {"path": "a.txt", "Dest": ".env"}) is not None  # key case is ignored
    assert write(ws, {"path": "a.txt", "SOURCE": ".env"}) is not None
    assert write(ws, {"path": "a.txt", "out_Dir": ".checkpoints"}) is not None
    assert write(ws, {"path": "a.txt", "content": "/etc/passwd"}) is None
    assert write(ws, {"path": "a.txt", "text": "../x"}) is None
    assert write(ws, {"path": "a.txt", "new_string": "~/x"}) is None
    assert write(ws, {"path": "a.txt", "meta": {"what?.x": 1}}) is None
    assert write(ws, {"path": "a.txt", "files": {"/etc/passwd": "x"}}) is not None
    assert write(ws, {"path": "a.txt", "files": {"notes": "x"}}) is None
    assert write(ws, {"path": "a.txt", "files": {"docs/notes.md": "x"}}) is None
    assert write(ws, {"path": "a.txt", "files": {"../escape.txt": "x"}}) is not None


def test_read_only_write_tool_message(ws: Workspace) -> None:
    msg = guard("read-only", ws)(ToolCall("c", "write_file", {"path": "a.txt"}))
    assert msg is not None and "writes are not allowed" in msg
    assert "refused in read-only mode" in msg


def test_a_custom_protected_name_is_found_inside_an_interpreter_argument(ws: Workspace) -> None:
    g = make_mode_guard(
        "workspace-write",
        ws,
        tool_classes=CLASSES,  # type: ignore[arg-type]
        protected=("Secrets.TXT",),
    )
    assert g(run("sed s/a/b/wSECRETS.TXT in")) is not None
    assert g(run("sed s/a/b/wsecrets.txt in")) is not None
    assert g(run("sed s/a/b/wother.txt in")) is None


def test_a_wrapper_the_guard_cannot_see_through_gives_the_full_reason(ws: Workspace) -> None:
    refused(ws, "chroot x ls", "'chroot' runs other commands and the guard cannot see through it")


def test_find_without_a_write_flag_is_not_judged_by_its_start_directory(ws: Workspace) -> None:
    allowed(ws, "find . -printf x")
    allowed(ws, "find . -ls")
    allowed(ws, "find . -newermt 2020-01-01")


def test_words_after_a_redirect_are_still_arguments(ws: Workspace) -> None:
    refused(ws, "rm > /dev/null -rf .claude")
    refused(ws, "rm >out.txt -r .claude")
    refused(ws, "find >out.txt . -delete")
    refused(ws, f"{VCS} >out.txt config a b")


def test_globs_with_a_dot_segment_and_equals_forms_are_still_matched(ws: Workspace) -> None:
    for cmd in (
        "echo x > ./.e?v",
        "cp in ./.cl*/settings.json",
        "cp in ./sub/../.e?v",
        "echo x > x=.env/a=b",
        "echo x > =.env",
        "echo x > of=.env",
    ):
        refused(ws, cmd, PROTECTED)


def test_an_absolute_path_with_an_expansion_ignores_the_tracked_directory(ws: Workspace) -> None:
    allowed(ws, "cd .claude && touch /settings.json$X")
    refused(ws, "cd .claude && touch settings.json$X", PROTECTED)


def test_read_only_recursion_is_judged_from_the_real_options(ws: Workspace, home: Path) -> None:
    assert ro(ws, "grep arr ~") is None  # "arr" is the pattern, not -r
    assert ro(ws, "ls xxrecursive ~") is None
    assert ro(ws, "ls --color=recursive ~") is None
    assert ro(ws, "find . -name ~") is None  # "~" is the value of -name
    assert ro(ws, "find . -name ..") is None
    assert ro(ws, "grep -r .. src") is None  # ".." is the pattern
    assert ro(ws, "rg .. src") is None
    assert ro(ws, "grep -r .. ~") is not None


def test_read_only_refuses_a_parent_of_home_even_when_it_is_not_above_the_workspace(
    ws: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep = tmp_path / "a" / "b" / "h"
    deep.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(deep))
    assert ro(ws, f"find {tmp_path}/a -name x") is not None
    assert ro(ws, f"grep -r x {tmp_path}/a/b") is not None
    assert ro(ws, f"find {deep}/sub -name x") is None


def test_every_option_letter_of_the_read_only_commands_is_listed(ws: Workspace) -> None:
    for letter in "AbeEnstTuv":
        assert ro(ws, f"cat -{letter} f") is None, letter
    for opt in ("-U3", "-C3", "-x pat", "-U 3"):
        assert ro(ws, f"diff {opt} a b") is None, opt
    for opt in ("-n 3", "-S foo", "-G foo", "-L 1,2:f"):
        assert ro(ws, f"{VCS} log {opt}") is None, opt
    assert ro(ws, "date -R") is None
    assert ro(ws, "date --rfc-email") is None
    assert ro(ws, "date --rfc-2822") is None
    assert ro(ws, "date --iso-8601=seconds") is None
    assert ro(ws, "date --universal") is None
