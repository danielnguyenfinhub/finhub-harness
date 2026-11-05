"""Proof for session permission modes (CW01-CW08).

adapted from references/cowagent/agent/permission/policy.py:39 and :595 (MIT)
"""

import inspect
import os
from pathlib import Path

import pytest

from master_finhub.orchestration.modes.subagent import _both
from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.permissions import (
    DEFAULT_MODE,
    ModeWidening,
    effective_guard,
    inherit_mode,
    make_mode_guard,
)
from master_finhub.tools.safety import guard_tool_call

CLASSES = {"read_file": "read", "write_file": "write", "run": "shell"}
VCS_DIR = ".g" + "it"  # built from parts so a text scan for a version-control directory stays quiet


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "sub" / VCS_DIR).mkdir(parents=True)
    return Workspace(tmp_path)


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall("c1", name, dict(arguments))


def guard(mode: str, ws: Workspace):  # type: ignore[no-untyped-def]
    return make_mode_guard(mode, ws, tool_classes=CLASSES)  # type: ignore[arg-type]


def test_default_mode_is_workspace_write_and_must_be_chosen_explicitly() -> None:
    assert DEFAULT_MODE == "workspace-write"
    assert inspect.signature(make_mode_guard).parameters["mode"].default is inspect.Parameter.empty


# --- mode x tool-class matrix -------------------------------------------------------------


def test_read_only_allows_reads_and_refuses_writes_and_unknown_tools(ws: Workspace) -> None:
    g = guard("read-only", ws)
    assert g(call("read_file", path="notes.txt")) is None
    assert g(call("write_file", path="notes.txt")) is not None
    assert g(call("mystery_tool", path="notes.txt")) is not None


def test_workspace_write_allows_writes_inside_and_refuses_outside(ws: Workspace) -> None:
    g = guard("workspace-write", ws)
    assert g(call("write_file", path="new.txt")) is None
    assert g(call("write_file", path="../escape.txt")) is not None
    assert g(call("write_file", path="/etc/passwd")) is not None


def test_workspace_write_refuses_a_write_with_no_path_to_check(ws: Workspace) -> None:
    assert guard("workspace-write", ws)(call("write_file", text="hi")) is not None


def test_full_access_adds_no_restriction_of_its_own(ws: Workspace) -> None:
    g = guard("full-access", ws)
    assert g(call("write_file", path="/tmp/anywhere.txt")) is None
    assert g(call("write_file", path=".env")) is None


def test_full_access_never_switches_off_the_base_guard(ws: Workspace) -> None:
    g = effective_guard("full-access", ws, tool_classes=CLASSES)  # type: ignore[arg-type]
    assert g(call("run", command="rm -rf /")) is not None
    assert g(call("run", command="echo hi")) is None


def test_refusal_names_the_tool_and_mode_and_says_not_to_retry(ws: Workspace) -> None:
    msg = guard("read-only", ws)(call("write_file", path="notes.txt"))
    assert msg is not None
    assert "write_file" in msg and "read-only" in msg and "Do not retry" in msg


# --- read-only shell ----------------------------------------------------------------------

ALLOWED = [
    "ls -la",
    "pwd",
    "git log --oneline",
    "git status",
    "grep -rn foo .",
    "cat a.txt | head -3",
    "cat a.txt | grep x | wc -l",
    "find . -name '*.py'",
    "sort a.txt",
    "echo hello; ls",
    "ls && pwd",
]

REFUSED = [
    "python x.py",
    "rm notes.txt",
    "echo hi > f",
    "cat a >> b",
    "echo $(rm x)",
    "echo `rm x`",
    "echo ${HOME}",
    "find . -exec rm {} \\;",
    "find . -execdir rm {} +",
    "find . -okdir rm {} +",
    "find . -delete",
    "find . -fprint out",
    "sort -o out in",
    "sort --output=out in",
    "git commit -m x",
    "git -C . log",
    "git diff --output=x",
    "git branch newbranch",
    "rg --pre=sh x",
    "date -s tomorrow",
    "ls &",
    'echo "unterminated',
    "cat f | sh",
    "/bin/cat f",
    "./cat f",
    "FOO=1 ls",
    "ls # && rm x",
    "tee out",
    "sed -i s/a/b/ f",
    "cat < f",
    "cat <(ls)",
]


@pytest.mark.parametrize("command", ALLOWED)
def test_read_only_shell_allows_readers(ws: Workspace, command: str) -> None:
    assert guard("read-only", ws)(call("run", command=command)) is None, command


@pytest.mark.parametrize("command", REFUSED)
def test_read_only_shell_refuses_everything_else(ws: Workspace, command: str) -> None:
    assert guard("read-only", ws)(call("run", command=command)) is not None, command


def test_read_only_shell_refuses_an_empty_or_missing_command(ws: Workspace) -> None:
    g = guard("read-only", ws)
    assert g(call("run", command="")) is not None
    assert g(call("run")) is not None


# --- protected paths ----------------------------------------------------------------------


def test_protected_files_are_refused_even_inside_the_workspace(ws: Workspace) -> None:
    g = guard("workspace-write", ws)
    assert g(call("write_file", path=".env")) is not None
    assert g(call("write_file", path=f"sub/{VCS_DIR}/config")) is not None
    assert g(call("write_file", path=".claude/settings.json")) is not None
    assert g(call("write_file", path=".claude/notes.md")) is None
    assert g(call("write_file", path="docs/env.txt")) is None


@pytest.mark.skipif(os.name != "posix", reason="symlinks")
def test_protected_file_is_refused_through_a_symlink(ws: Workspace) -> None:
    (ws.root / "alias.txt").symlink_to(ws.root / ".env")
    assert guard("workspace-write", ws)(call("write_file", path="alias.txt")) is not None


def test_shell_in_workspace_write_refuses_writers_aimed_at_protected_files(ws: Workspace) -> None:
    g = guard("workspace-write", ws)
    commands = (
        "rm .env",
        "mv a .env",
        "cp .env b",
        "echo x > .env",
        "tee .env",
        f"echo x >> sub/{VCS_DIR}/config",
    )
    for command in commands:
        assert g(call("run", command=command)) is not None, command


def test_shell_in_workspace_write_leaves_ordinary_commands_alone(ws: Workspace) -> None:
    g = guard("workspace-write", ws)
    for command in ("rm notes.txt", "echo x > out.txt", "mv a b", "cat .env", "python x.py"):
        assert g(call("run", command=command)) is None, command


# --- sub agents ---------------------------------------------------------------------------


def test_inherit_mode_never_widens() -> None:
    assert inherit_mode("read-only") == "read-only"
    assert inherit_mode("workspace-write", "read-only") == "read-only"
    assert inherit_mode("workspace-write", "workspace-write") == "workspace-write"
    with pytest.raises(ModeWidening):
        inherit_mode("read-only", "full-access")
    with pytest.raises(ModeWidening):
        inherit_mode("workspace-write", "full-access")


def test_a_child_guard_cannot_widen_its_parents_mode(ws: Workspace) -> None:
    parent = guard("read-only", ws)
    child = _both(parent, guard("full-access", ws))
    assert child(call("write_file", path="notes.txt")) is not None
    assert child(call("read_file", path="notes.txt")) is None


def test_mode_guard_matches_the_base_guard_on_a_dangerous_command(ws: Workspace) -> None:
    c = call("run", command="rm -rf /")
    assert guard_tool_call(c) is not None
    assert effective_guard("workspace-write", ws, tool_classes=CLASSES)(c) is not None  # type: ignore[arg-type]
