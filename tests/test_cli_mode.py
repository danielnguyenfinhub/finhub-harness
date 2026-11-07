"""The CLI runs the loop under a permission mode (read-only, workspace-write, full-access)."""

from pathlib import Path

import pytest

from master_finhub import cli
from master_finhub.orchestration.dag_engine import CheckpointStore
from master_finhub.runtime.loop import ToolCall
from master_finhub.sandbox.workspace import WORKSPACE_ENV_VAR, Workspace
from master_finhub.tools import guard_factory, permissions

MODES = ["read-only", "workspace-write", "full-access"]


@pytest.fixture()
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("mode", MODES)
def test_echo_runs_in_every_mode(mode: str, ws: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--mode", mode, "echo hi"]) == 0
    assert capsys.readouterr().out.strip() == "hi"


def test_unknown_mode_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(["--mode", "root", "echo hi"])
    assert stop.value.code == 2
    assert "read-only" in capsys.readouterr().err


def test_default_mode_is_workspace_write_and_guard_is_the_mode_guard(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, dict[str, str]]] = []
    real = permissions.effective_guard

    def spy(mode, workspace, *, tool_classes=None, protected=permissions.DEFAULT_PROTECTED):  # type: ignore[no-untyped-def]
        seen.append((mode, dict(tool_classes or {})))
        return real(mode, workspace, tool_classes=tool_classes, protected=protected)

    monkeypatch.setattr(guard_factory, "effective_guard", spy)
    assert cli.main(["echo hi"]) == 0
    assert seen == [("workspace-write", {"echo": "read"})]


@pytest.mark.parametrize("mode", ["read-only", "workspace-write"])
def test_without_a_workspace_folder_echo_still_runs(
    mode: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "/nonexistent-folder-for-test")
    assert cli.main(["--mode", mode, "echo hi"]) == 0
    assert capsys.readouterr().out.strip() == "hi"


@pytest.mark.parametrize("mode", ["read-only", "workspace-write"])
def test_without_a_workspace_folder_only_read_tools_pass(
    mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "/nonexistent-folder-for-test")
    guard = cli.build_guard(mode)  # type: ignore[arg-type]
    assert guard(ToolCall("1", "echo", {"text": "hi"})) is None
    for name in ("write_file", "bash"):
        why = guard(ToolCall("2", name, {"path": "x", "command": "ls"}))
        assert why is not None and "workspace" in why


def test_full_access_without_a_workspace_folder_keeps_the_base_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "/nonexistent-folder-for-test")
    guard = cli.build_guard("full-access")
    assert guard(ToolCall("1", "echo", {"text": "hi"})) is None
    assert guard(ToolCall("2", "bash", {"command": "cat ~/.ssh/id_rsa"})) is not None


def test_base_command_guard_still_runs_first(ws: Path) -> None:
    guard = cli.build_guard("full-access")
    assert guard(ToolCall("1", "bash", {"command": "cat ~/.ssh/id_rsa"})) is not None


def test_run_saves_the_mode_and_resume_cannot_widen_it(
    ws: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--run-id", "r1", "--mode", "read-only", "echo hi"]) == 0
    checkpoint, writer = CheckpointStore(Workspace()).resume_run("r1")
    writer.close()
    assert checkpoint.meta["mode"] == "read-only"
    capsys.readouterr()
    assert cli.main(["--resume", "r1", "--mode", "full-access"]) == 2
    assert "read-only" in capsys.readouterr().err


def test_resume_without_mode_uses_the_saved_one(
    ws: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--run-id", "r2", "--mode", "read-only", "echo hi"]) == 0
    seen: list[str] = []
    real = cli.build_guard

    def spy(mode):  # type: ignore[no-untyped-def]
        seen.append(mode)
        return real(mode)

    monkeypatch.setattr(cli, "build_guard", spy)
    capsys.readouterr()
    cli.main(["--resume", "r2"])
    assert seen == ["read-only"]


def test_a_run_saved_before_modes_resumes_as_the_default(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_create = CheckpointStore.create_run

    def create_without_mode(self, run_id, meta=None, **kw):  # type: ignore[no-untyped-def]
        return real_create(
            self, run_id, meta={k: v for k, v in (meta or {}).items() if k != "mode"}, **kw
        )

    monkeypatch.setattr(CheckpointStore, "create_run", create_without_mode)
    assert cli.main(["--run-id", "old", "--mode", "read-only", "echo hi"]) == 0
    seen: list[str] = []
    real = cli.build_guard

    def spy(mode):  # type: ignore[no-untyped-def]
        seen.append(mode)
        return real(mode)

    monkeypatch.setattr(cli, "build_guard", spy)
    cli.main(["--resume", "old"])
    assert seen == ["workspace-write"]
