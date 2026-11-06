"""Audit fixes for the mode guard: fail closed, reader arguments, read-only flag matching."""

from pathlib import Path

import pytest

from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.permissions import DEFAULT_PROTECTED, make_mode_guard

CLASSES = {"write_file": "write", "run": "shell"}
VCS = ".g" + "it"


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def g(mode: str, ws: Workspace):  # type: ignore[no-untyped-def]
    return make_mode_guard(mode, ws, tool_classes=CLASSES)  # type: ignore[arg-type]


def run(cmd: str) -> ToolCall:
    return ToolCall("c", "run", {"command": cmd})


FAIL_CLOSED = [
    "true\necho X > .env",
    "echo X > ${PWD}/.env",
    "echo `id` > .env",
    "echo $(id) > .env",
]


@pytest.mark.parametrize("cmd", FAIL_CLOSED)
def test_untokenizable_command_naming_protected_file_is_refused(ws: Workspace, cmd: str) -> None:
    assert g("workspace-write", ws)(run(cmd)) is not None, cmd


def test_untokenizable_command_without_protected_name_is_allowed(ws: Workspace) -> None:
    assert g("workspace-write", ws)(run("true\necho X > out.txt")) is None


READER_WRITES = [
    "sort -o .env in",
    f"find {VCS} -delete",
    f"git config --file {VCS}/config a.b c",
    "find . -fprint .claude/settings.json",
    "sort -o.env in",
]


@pytest.mark.parametrize("cmd", READER_WRITES)
def test_reader_with_write_flag_is_refused_in_workspace_write(ws: Workspace, cmd: str) -> None:
    assert g("workspace-write", ws)(run(cmd)) is not None, cmd


def test_plain_reads_of_protected_files_still_allowed(ws: Workspace) -> None:
    assert g("workspace-write", ws)(run("cat .env")) is None
    assert g("workspace-write", ws)(run(f"git log {VCS}")) is None


READ_ONLY_REFUSED = [
    "sort -ro out in",
    "sort -uo out in",
    "sort --o=out in",
    "sort --out=out in",
    "sort --output=out in",
    "sort -S1k --compress-program=sh in",
    "sort --compress-program sh in",
    "date -us",
    "date -s tomorrow",
    "date --s=now",
    "file --compile",
    "file -C",
    "file -bC",
]


@pytest.mark.parametrize("cmd", READ_ONLY_REFUSED)
def test_read_only_refuses_flag_variants(ws: Workspace, cmd: str) -> None:
    assert g("read-only", ws)(run(cmd)) is not None, cmd


@pytest.mark.parametrize("cmd", ["sort -u a", "sort -k1,2 a", "date -u", "file -b a", "date +%s"])
def test_read_only_still_allows_plain_flags(ws: Workspace, cmd: str) -> None:
    assert g("read-only", ws)(run(cmd)) is None, cmd


def test_every_path_key_is_checked(ws: Workspace) -> None:
    guard = g("workspace-write", ws)
    c = ToolCall("c", "write_file", {"path": "ok.txt", "file_path": ".env"})
    assert guard(c) is not None
    c = ToolCall("c", "write_file", {"path": ".env", "filename": "ok.txt"})
    assert guard(c) is not None
    assert guard(ToolCall("c", "write_file", {"path": "a.txt", "file_path": "b.txt"})) is None


@pytest.mark.parametrize("name", [".ENV", ".Env", f"sub/{VCS.upper()}/config"])
def test_protected_match_is_case_insensitive(ws: Workspace, name: str) -> None:
    assert g("workspace-write", ws)(ToolCall("c", "write_file", {"path": name})) is not None


def test_checkpoints_is_protected(ws: Workspace) -> None:
    assert ".checkpoints" in DEFAULT_PROTECTED
    assert (
        g("workspace-write", ws)(ToolCall("c", "write_file", {"path": ".checkpoints/x"}))
        is not None
    )
