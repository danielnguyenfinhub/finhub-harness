"""Re-audit of the mode guard: the report's exact bypass inputs, and the over-refusals.

Every bypass worked because the guard read text that the shell expands later. These tests pin the
structural fixes: unevaluable words are refused in read-only, options come from a per-command
allowlist, protected paths are compared after folding `..`, and values inside key=value words,
globs and expansions are looked at in workspace-write.
"""

import os
from pathlib import Path

import pytest

from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools import permissions
from master_finhub.tools.permissions import make_mode_guard

CLASSES = {"write_file": "write", "run": "shell"}
VCS = ".g" + "it"


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def g(mode: str, ws: Workspace):  # type: ignore[no-untyped-def]
    return make_mode_guard(mode, ws, tool_classes=CLASSES)  # type: ignore[arg-type]


def run(cmd: str) -> ToolCall:
    return ToolCall("c", "run", {"command": cmd})


# --- read-only: words the guard cannot evaluate --------------------------------------------

RO_BYPASS = [
    "sort --{output=o9,reverse} in",
    "sort --o{utput,}=x in",
    "sort --{output,zz}=out in",
    "sort --compress-{program,x}=sh in",
    "date --{set,x}=now",
    "file --{compile,x}",
    "git diff --{output,zz}=x",
    "git diff --out{put,}=x",
    "find . -{delete,print}",
    "find . -{fprint,zz} x",
    "find . -{exec,zz} x",
    "sort $'-o' o10 in",
    "sort $'\\x2do' x a",
    "date $'-s' now",
    "find . $'-delete'",
    'sort $"-o" x in',
    "sort $'--output=x' in",
    "sort ${EMPTY}-o x in",
    "sort $(true)-o x in",
    "sort -$()o x in",
    "sort -\\o x in",
    "sort -o\\\nx in",
    "cat ~root/x",
    "cat *",
    "cat ?",
    "cat [a]*",
    "cat a`true`",
    "sort {-o,out} in",
    "cat a\\ b",
]


@pytest.mark.parametrize("cmd", RO_BYPASS)
def test_read_only_refuses_unevaluable_words(ws: Workspace, cmd: str) -> None:
    assert g("read-only", ws)(run(cmd)) is not None, cmd


RO_EXEC = [
    "rg --hostname-bin=sh x",
    "rg --hostname-bin sh x",
    "rg --hostname-b sh x",
    "rg -z x",
    "rg --search-zip x",
    "rg --pre=sh x",
    "git diff --ext-diff",
    "git log --textconv",
    "git diff --textconv",
    "git show --ext-diff",
    "git log --ext-d",
    "git diff --output=x",
    "git config user.name x",
    "git -c core.pager=sh log",
    "sort -T. in",
    "sort --temporary-directory=. in",
    "sort -T /tmp in",
    "sort --compress-program=sh in",
    "sort --comp=sh in",
    "sort -o out in",
    "find . -delete",
    "find . -execdir x {} +",
    "find . -fprintf x y",
    "date 010112002026",
    "date --set=now",
]


@pytest.mark.parametrize("cmd", RO_EXEC)
def test_read_only_allowlist_refuses_options_that_run_or_write(ws: Workspace, cmd: str) -> None:
    assert g("read-only", ws)(run(cmd)) is not None, cmd


RO_ALLOWED = [
    "date -Iseconds",
    "date -I",
    "date -u",
    "date --utc",
    "date -R",
    "date -d '-2 hours'",
    "date --date='-2 hours'",
    "date --date=@0 +%s",
    "date -r a.txt",
    "date +%s",
    "date -u +%Y-%m-%dT%H:%M:%SZ",
    "rg --pretty foo",
    "rg --files",
    "rg -n -i foo src",
    "rg -g '*.py' foo",
    "rg --glob '*.py' foo",
    "sort -to -k2 file",
    "sort -k1,1 in",
    "sort -u -r -n in",
    "sort -t, -k2 in",
    "sort -c in",
    "sort -rn in",
    "cat README.md",
    "ls -la",
    "ls -lah src",
    "head -5 f",
    "head -n 5 f",
    "tail -f log",
    "tail -n5 f",
    "wc -l f",
    "git log --oneline -n 5",
    "git log -5 --oneline",
    "git status -sb",
    "git diff --stat",
    "git diff HEAD~1",
    "git diff --name-only 'HEAD~1'",
    "git show --stat HEAD",
    "grep -rn --include='*.py' foo src",
    "grep -rn foo src",
    "grep -E 'a|b' f",
    "grep -A3 -B1 x f",
    "find . -name '*.py'",
    "find . -type f -name x -maxdepth 2",
    "find src -path 'a/*' -print",
    "file -bi a",
    "stat a",
    "diff -u a b",
    "echo -n hi",
    "echo -----",
    "cat ~/notes.txt",
    "echo 'a$b {x} *'",
    'echo "plain text"',
    "cat a | head -3",
]


@pytest.mark.parametrize("cmd", RO_ALLOWED)
def test_read_only_still_allows_benign_reads(ws: Workspace, cmd: str) -> None:
    assert g("read-only", ws)(run(cmd)) is None, cmd


# --- workspace-write: protected files ------------------------------------------------------

WW_BYPASS = [
    "echo x > .e$(true)nv",
    "echo x > .e$()nv",
    "echo x > .${NOPE}env",
    "echo x > .${HOME:0:0}env",
    "echo x > .e${A}nv",
    "echo x > .e$Anv",
    "echo x > .g$()it/config",
    "echo x > .clau$()de/settings.json",
    "echo x > .check$()points/a",
    "echo x > .c\\\nlaude/settings.json",
    "echo x > .g\\\nit/config",
    "echo x > .check\\\npoints/a",
    "echo x > .claude/x/../settings.json",
    "echo x > .claude/sub/../settings.local.json",
    "echo x > ././/.env",
    "echo x > a/../.env",
    "dd of=.env",
    "dd if=in of=.env",
    "echo x | dd of=.env",
    f"dd of={VCS}/config",
    "dd of=.claude/settings.json",
    f"cp --target-directory={VCS} in",
    "env -S 'tee .env'",
    "env --split-string='tee .env'",
    "script -c 'tee .env' /dev/null",
    "sed 's/a/b/w .env' in",
    "echo x > .{e,f}nv",
    "echo x > .e{n,}v",
    "echo x > $'.env'",
    "cp in .gi?/config",
    "cp in .claude/settings.*",
    "cp in .claude/s*",
    "cp in .claude/*/settings.json",
    "cp in .c*/settings.json",
    "cp in .ch*",
    "cp in .[e]nv",
    "cp in .claude/x/../settings.*",
    "dd of=.e$Anv",
    "cp --target-directory=.g?t in",
    "myrunner 'tee .env'",
    "rm -rf *",
    "rm -rf .*",
    "rm -r $D",
    "find . -type f -delete",
    "find . -delete",
    "git config x y",
    "git config --local core.hooksPath h",
    "git hook run x",
    "git update-ref -d HEAD",
    "git -c core.fsmonitor=sh status",
    "git clean -fdx",
    "git stash -u",
    "git stash --include-untracked",
    f"git checkout {VCS}/config",
    "git restore .claude/settings.json",
    "git commit -m x && echo y > .e$()nv",
]


@pytest.mark.parametrize("cmd", WW_BYPASS)
def test_workspace_write_refuses_protected_targets_reached_by_expansion(
    ws: Workspace, cmd: str
) -> None:
    assert g("workspace-write", ws)(run(cmd)) is not None, cmd


WW_ALLOWED = [
    "echo hi > out.txt",
    "cp a b",
    "mv a b",
    "rm a.txt",
    "rm -rf build",
    "rm -rf src/build",
    "git add -A",
    "git add src",
    "git checkout main",
    "git status",
    "git log --oneline -n 3",
    "echo x > .gitignore",
    "ls .github",
    "pytest -q",
    "tee out.txt",
    "sort -o out.txt in",
    "echo see .env docs",
    'printf "%s" ".env notes"',
    "cat .env",
    "dd if=in of=out.bin",
    "cp --target-directory=outdir in",
    "find src -name '*.pyc' -delete",
    "true\necho X > out.txt",
    "python x.py",
    "cp in docs/env.txt",
]


@pytest.mark.parametrize("cmd", WW_ALLOWED)
def test_workspace_write_leaves_ordinary_commands_alone(ws: Workspace, cmd: str) -> None:
    assert g("workspace-write", ws)(run(cmd)) is None, cmd


@pytest.mark.skipif(os.name != "posix", reason="symlinks")
def test_shell_write_through_a_symlink_to_a_protected_file_is_refused(ws: Workspace) -> None:
    (ws.root / ".env").write_text("x")
    (ws.root / "lnk").symlink_to(ws.root / ".env")
    for cmd in ("echo x > lnk", "tee lnk", "cp in lnk"):
        assert g("workspace-write", ws)(run(cmd)) is not None, cmd


def test_text_with_substitution_and_a_writer_or_redirect_is_refused(ws: Workspace) -> None:
    guard = g("workspace-write", ws)
    assert guard(run("echo $(date) > out.txt")) is not None
    assert guard(run("cp $(pwd)/a b")) is not None
    assert guard(run("echo $(date)")) is None  # no redirect and no writer


# --- write tool: every string argument -----------------------------------------------------

WRITE_KEYS: list[dict[str, object]] = [
    {"path": "ok.txt", "dest": ".env"},
    {"path": "dest", "to": ".env"},
    {"path": "ok", "destination": f"{VCS}/config"},
    {"path": "a", "new_path": ".env"},
    {"path": "a", "output": ".env"},
    {"path": "a", "target": "../escape.txt"},
    {"path": "ok.txt", "paths": ["fine.txt", ".env"]},
    {"path": "ok.txt", "dest": ".claude/x/../settings.json"},
]


@pytest.mark.parametrize("args", WRITE_KEYS)
def test_write_tool_checks_every_string_argument(ws: Workspace, args: dict[str, object]) -> None:
    assert g("workspace-write", ws)(ToolCall("c", "write_file", args)) is not None, args


def test_write_tool_does_not_treat_content_as_a_path(ws: Workspace) -> None:
    c = ToolCall("c", "write_file", {"path": "a.txt", "content": "/etc/passwd\n.env\n../x"})
    assert g("workspace-write", ws)(c) is None
    c = ToolCall("c", "write_file", {"path": "a.txt", "dest": "b.txt", "mode": "w"})
    assert g("workspace-write", ws)(c) is None


# --- advisory sentence ---------------------------------------------------------------------


def test_workspace_write_refusal_says_the_protection_is_advisory(ws: Workspace) -> None:
    msg = g("workspace-write", ws)(run("dd of=.env"))
    assert msg is not None
    assert "advisory" in msg and "only a real sandbox is a boundary" in msg
    assert "advisory" in (permissions.__doc__ or "")
    ro = g("read-only", ws)(run("rm x"))
    assert ro is not None and "advisory" not in ro
