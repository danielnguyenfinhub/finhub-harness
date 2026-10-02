"""Docker sandbox engine: one throwaway, network-less, read-only container per command.

Patterns adapted from autogpt classic code_executor.py (MIT; availability probe, workspace mount,
per-run name, timeout bound). Hardening flags, re-check and argv validation are net-new. The
agent's command string is only ever interpreted by ``sh -c`` inside the container; the host side
never uses a shell.
"""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from master_finhub.runtime.loop import ToolSpec
from master_finhub.sandbox.stream import (
    DEFAULT_MAX_OUTPUT_BYTES,
    Chunk,
    ExecResult,
    collect,
    scrubbed_env,
    stream_process,
)
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.safety import DEFAULT_POLICY, CommandPolicy, check_command

DEFAULT_IMAGE: Final = "python:3.12-alpine"
CONTAINER_WORKDIR: Final = "/workspace"
IMAGE_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,127}")
ENV_NAME_RE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
BAD_ROOT_CHARS: Final = (",", "=", "\n", "\x00")


def _run_quiet(argv: list[str], timeout_s: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=scrubbed_env(),
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except Exception:  # noqa: BLE001 - missing binary, timeout, anything: not available
        return None


def docker_available(timeout_s: float = 10.0) -> bool:
    r = _run_quiet(["docker", "info", "--format", "{{.OSType}}"], timeout_s)
    return r is not None and r.returncode == 0 and r.stdout.strip() == "linux"


def image_present(image: str, timeout_s: float = 10.0) -> bool:
    if not IMAGE_RE.fullmatch(image):
        return False
    r = _run_quiet(["docker", "image", "inspect", image], timeout_s)
    return r is not None and r.returncode == 0


@dataclass(frozen=True)
class SandboxConfig:
    image: str = DEFAULT_IMAGE
    timeout_s: int = 120
    memory: str = "512m"
    cpus: str = "1"
    pids_limit: int = 128
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES
    env: Mapping[str, str] = field(default_factory=dict)  # the ONLY env the container sees

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_s <= 600:
            raise ValueError("timeout_s must be between 1 and 600")


class CommandBlocked(PermissionError):
    """check_command denied the command; the message is the denial text, never the command."""


def docker_argv(config: SandboxConfig, workspace_root: Path, command: str, name: str) -> list[str]:
    root = str(workspace_root)
    if any(c in root for c in BAD_ROOT_CHARS):
        raise ValueError("workspace root contains a character not allowed in a mount")
    if not IMAGE_RE.fullmatch(config.image):
        raise ValueError("invalid image reference")
    for key in config.env:
        if not ENV_NAME_RE.fullmatch(key):
            raise ValueError("invalid environment variable name")
    argv = [
        "docker", "run", "--rm", "--pull", "never", "--name", name,
        "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
        "--pids-limit", str(config.pids_limit),
        "--memory", config.memory, "--cpus", config.cpus,
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
    ]  # fmt: skip
    if hasattr(os, "getuid"):
        argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
    argv += ["--mount", f"type=bind,src={root},dst={CONTAINER_WORKDIR}", "-w", CONTAINER_WORKDIR]
    for key in sorted(config.env):
        argv += ["-e", f"{key}={config.env[key]}"]
    return [*argv, config.image, "sh", "-c", command]


class DockerEngine:
    def __init__(
        self,
        workspace: Workspace,
        config: SandboxConfig | None = None,
        policy: CommandPolicy = DEFAULT_POLICY,
    ) -> None:
        self._workspace = workspace
        self._config = config or SandboxConfig()
        self._policy = policy

    def stream(self, command: str) -> Iterator[Chunk]:
        # Plain function (not a generator): a denied command raises here, before anything spawns.
        denial = check_command(command, self._policy)
        if denial is not None:
            raise CommandBlocked(denial)
        name = f"mf_{uuid.uuid4().hex[:8]}"
        argv = docker_argv(self._config, self._workspace.root, command, name)

        def kill_container() -> None:
            _run_quiet(["docker", "kill", name], 10.0)

        return stream_process(
            argv,
            env=scrubbed_env(),
            timeout_s=self._config.timeout_s,
            on_timeout=kill_container,
        )

    def run(self, command: str) -> ExecResult:
        return collect(self.stream(command), self._config.max_output_bytes)


class SandboxExecTool:
    spec = ToolSpec(
        name="sandbox_exec",
        description=(
            "Run a shell command inside an isolated, network-less container "
            "whose only writable folder is the workspace."
        ),
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        idempotent=False,
    )

    def __init__(self, engine: DockerEngine) -> None:
        self._engine = engine

    def run(self, arguments: dict[str, Any]) -> str:
        command = arguments.get("command")
        if not isinstance(command, str):
            raise TypeError("'command' must be a string")
        res = self._engine.run(command)
        code = "timeout" if res.exit_code is None else str(res.exit_code)
        text = f"exit={code}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        if res.truncated:
            text += "\n[output truncated]"
        if res.timed_out:
            text += f"\n[timed out after {self._engine._config.timeout_s}s]"
        if res.exit_code == 125 or "Unable to find image" in res.stderr:
            text += f"\n[image missing? run: docker pull {self._engine._config.image}]"
        return text
