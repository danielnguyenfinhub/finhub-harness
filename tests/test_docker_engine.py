"""Slice 8 proof tests: docker argv, engine gate, tool (no docker needed except one skipped test)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from master_finhub.sandbox import docker_engine as de
from master_finhub.sandbox.docker_engine import (
    DEFAULT_IMAGE,
    CommandBlocked,
    DockerEngine,
    SandboxConfig,
    SandboxExecTool,
    docker_argv,
    docker_available,
    image_present,
)
from master_finhub.sandbox.stream import Chunk
from master_finhub.sandbox.workspace import Workspace


def test_docker_argv_hardening(tmp_path: Path) -> None:
    argv = docker_argv(SandboxConfig(env={"B": "2", "A": "1"}), tmp_path, "echo hi", "mf_deadbeef")
    joined = " ".join(argv)
    for flag in (
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--rm",
        "--pull never",
        "--security-opt no-new-privileges",
        "--pids-limit 128",
        "dst=/workspace",
        "--name mf_deadbeef",
    ):
        assert flag in joined
    for bad in ("--privileged", "docker.sock", "host"):
        assert bad not in joined
    assert argv[:2] == ["docker", "run"]
    assert argv[-3:] == ["sh", "-c", "echo hi"]
    assert argv.index("-e") < argv.index(DEFAULT_IMAGE)
    assert argv[argv.index("-e") + 1] == "A=1"


def test_docker_argv_rejects_comma_root(tmp_path: Path) -> None:
    bad = tmp_path / "a,b"
    bad.mkdir()
    with pytest.raises(ValueError):
        docker_argv(SandboxConfig(), bad, "true", "mf_00000000")


def test_docker_argv_rejects_bad_image_and_env(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        docker_argv(SandboxConfig(image="-v /:/x"), tmp_path, "true", "mf_00000000")
    with pytest.raises(ValueError):
        docker_argv(SandboxConfig(env={"A B": "1"}), tmp_path, "true", "mf_00000000")


def test_config_timeout_bounds() -> None:
    for bad in (0, 601):
        with pytest.raises(ValueError):
            SandboxConfig(timeout_s=bad)
    assert SandboxConfig(timeout_s=1).timeout_s == 1
    assert SandboxConfig(timeout_s=600).timeout_s == 600


def _engine(tmp_path: Path) -> DockerEngine:
    return DockerEngine(Workspace(root=tmp_path))


def test_docker_argv_unique_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake(argv: Any, **_: Any) -> Any:
        seen.append(list(argv))
        yield Chunk(0, "exit", "0")

    monkeypatch.setattr(de, "stream_process", fake)
    eng = _engine(tmp_path)
    eng.run("echo a")
    eng.run("echo b")
    names = [a[a.index("--name") + 1] for a in seen]
    assert len(set(names)) == 2
    assert all(re.fullmatch(r"mf_[0-9a-f]{8}", n) for n in names)
    assert all("--rm" in a for a in seen)


def test_engine_blocks_denied_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise AssertionError("must not spawn")

    monkeypatch.setattr(subprocess, "Popen", boom)
    eng = _engine(tmp_path)
    with pytest.raises(CommandBlocked):
        eng.stream("rm -rf /")  # raised before any iteration: stream is a plain function
    with pytest.raises(CommandBlocked):
        eng.run("rm -rf /")


def test_docker_available_false_without_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    def nope(*_: Any, **__: Any) -> Any:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", nope)
    assert docker_available() is False
    assert image_present(DEFAULT_IMAGE) is False


def test_tool_formats_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(argv: Any, **_: Any) -> Any:
        yield Chunk(0, "stdout", "hi\n")
        yield Chunk(1, "exit", "3")

    monkeypatch.setattr(de, "stream_process", fake)
    out = SandboxExecTool(_engine(tmp_path)).run({"command": "echo hi"})
    assert out.startswith("exit=3\nSTDOUT:\nhi\n")


def test_tool_missing_image_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(argv: Any, **_: Any) -> Any:
        yield Chunk(0, "stderr", "Unable to find image locally\n")
        yield Chunk(1, "exit", "125")

    monkeypatch.setattr(de, "stream_process", fake)
    out = SandboxExecTool(_engine(tmp_path)).run({"command": "echo hi"})
    assert f"docker pull {DEFAULT_IMAGE}" in out


@pytest.mark.skipif(
    not (docker_available() and image_present(DEFAULT_IMAGE)),
    reason="docker daemon or image not available",
)
def test_echo_in_container(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    assert eng.run("echo hi").stdout == "hi\n"
    # smoke only: non-root --user would also block this; --read-only is proven by the argv test
    assert eng.run("touch /etc/x").exit_code != 0
    assert eng.run("wget -T 2 http://example.com").exit_code != 0
