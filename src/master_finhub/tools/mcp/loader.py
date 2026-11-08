"""Open the MCP servers named in a config file and hand their tools to an entry point.

The operator owns the config file: it names each server's launch command, which tools are trusted
read-only, and which new tools are enabled. The first listing of a server is its baseline; after
that a tool that is new or changed is quarantined until the operator enables it (``ApprovalStore``
keeps the approved digests, one 0600 file per server in a 0700 directory). A tool is classed
``read`` for the mode guard only when the operator listed it in ``trusted_read_only`` (the server's
own readOnlyHint is not trusted); the operator may class others ``write`` or ``shell`` in
``tool_classes``, and a tool in neither list is unknown to the mode guard (refused in read-only
mode; in workspace-write only the base command guard judges it).

Config shape (unknown keys are refused, so a typo cannot silently drop a restriction)::

    {"servers": [{"name": "files", "command": ["python", "server.py"],
                  "env": {"KEY": "value"}, "cwd": null, "call_timeout_s": 30,
                  "allowed_tools": ["a"], "blocked_tools": ["b"],
                  "trusted_read_only": ["a"], "tool_classes": {"put": "write"},
                  "enabled": ["c"]}]}

``enabled`` is a list of names or a mapping of name to the digest the operator approved.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from master_finhub.tools.mcp.client import (
    ApprovalStore,
    McpClient,
    McpTool,
    StdioServer,
)
from master_finhub.tools.permissions import ToolClass

_KEYS: Final = {
    "name",
    "command",
    "env",
    "cwd",
    "call_timeout_s",
    "allowed_tools",
    "blocked_tools",
    "trusted_read_only",
    "tool_classes",
    "enabled",
}
_CLASSES: Final = ("read", "write", "shell")


class McpConfigError(ValueError):
    """The MCP config file is missing, unreadable or not the expected shape."""


@dataclass(frozen=True)
class McpEntry:
    server: StdioServer
    trusted_read_only: frozenset[str]
    enabled: frozenset[str] | Mapping[str, str]
    tool_classes: Mapping[str, ToolClass] = field(default_factory=dict)


@dataclass(frozen=True)
class McpBundle:
    tools: list[McpTool]
    tool_classes: dict[str, ToolClass]
    quarantined: list[str]  # public names of tools the model cannot call yet


def _strings(raw: Any, what: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise McpConfigError(f"{what} must be a list of strings")
    return raw


def _entry(raw: Any, position: int) -> McpEntry:
    where = f"server {position}"
    if not isinstance(raw, dict):
        raise McpConfigError(f"{where} must be an object")
    unknown = sorted(set(raw) - _KEYS)
    if unknown:
        raise McpConfigError(f"{where} has unknown keys: {', '.join(map(str, unknown))}")
    name = raw.get("name")
    if not isinstance(name, str):
        raise McpConfigError(f"{where} needs a name")
    where = f'server "{name}"'
    command = _strings(raw.get("command"), f"{where} command")
    if not command:
        raise McpConfigError(f"{where} command is empty")
    env = raw.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        raise McpConfigError(f"{where} env must map names to strings")
    cwd = raw.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        raise McpConfigError(f"{where} cwd must be a string or null")
    extra: dict[str, Any] = {}
    if "call_timeout_s" in raw:
        timeout = raw["call_timeout_s"]
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise McpConfigError(f"{where} call_timeout_s must be a number above 0")
        extra["call_timeout_s"] = float(timeout)
    if "allowed_tools" in raw:
        extra["allowed_tools"] = frozenset(_strings(raw["allowed_tools"], f"{where} allowed_tools"))
    if "blocked_tools" in raw:
        extra["blocked_tools"] = frozenset(_strings(raw["blocked_tools"], f"{where} blocked_tools"))
    enabled: frozenset[str] | Mapping[str, str]
    raw_enabled = raw.get("enabled", [])
    if isinstance(raw_enabled, dict):
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in raw_enabled.items()):
            raise McpConfigError(f"{where} enabled must map names to digests")
        enabled = dict(raw_enabled)
    else:
        enabled = frozenset(_strings(raw_enabled, f"{where} enabled"))
    try:
        server = StdioServer(name=name, command=tuple(command), env=env, cwd=cwd, **extra)
    except ValueError as exc:
        raise McpConfigError(f"{where}: {exc}") from None
    trusted = frozenset(_strings(raw.get("trusted_read_only", []), f"{where} trusted_read_only"))
    classes = raw.get("tool_classes", {})
    if not isinstance(classes, dict) or not all(
        isinstance(k, str) and v in _CLASSES for k, v in classes.items()
    ):
        raise McpConfigError(f"{where} tool_classes must map names to read, write or shell")
    clash = sorted(trusted & set(classes))
    if clash:
        raise McpConfigError(
            f"{where} lists {', '.join(clash)} in both trusted_read_only and tool_classes"
        )
    return McpEntry(server, trusted, enabled, dict(classes))


def read_config(path: str | os.PathLike[str]) -> list[McpEntry]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
        raise McpConfigError(f"cannot read MCP config {os.fspath(path)}: {exc}") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"servers"}
        or not isinstance(data["servers"], list)
    ):
        raise McpConfigError('MCP config must be {"servers": [...]}')
    entries = [_entry(raw, i) for i, raw in enumerate(data["servers"], 1)]
    names = [e.server.name for e in entries]
    if len(set(names)) != len(names):
        raise McpConfigError("two MCP servers share a name")
    return entries


@contextmanager
def open_mcp(
    config_path: str | os.PathLike[str], approvals_dir: str | os.PathLike[str] | None = None
) -> Iterator[McpBundle]:
    """Start every configured server, list its tools under the saved approvals, and close them all
    on exit. Raises ``McpConfigError`` for a bad config and ``McpError`` if a server will not start.
    """
    entries = read_config(config_path)
    root = Path(approvals_dir) if approvals_dir else Path(f"{os.fspath(config_path)}.approvals")
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise McpConfigError(f"cannot create the approvals directory {root}: {exc}") from None
    with ExitStack() as stack:
        tools: list[McpTool] = []
        classes: dict[str, ToolClass] = {}
        for entry in entries:
            client = stack.enter_context(McpClient(entry.server))
            listed = ApprovalStore(root / f"{entry.server.name}.json").mcp_tools(
                client, enabled=entry.enabled, trusted_read_only=entry.trusted_read_only
            )
            for tool in listed:
                kind: ToolClass | None = (
                    "read"
                    if tool.tool_name in entry.trusted_read_only
                    else entry.tool_classes.get(tool.tool_name)
                )
                if kind is not None:
                    classes[tool.spec.name] = kind
            tools.extend(listed)
        yield McpBundle(tools, classes, [t.spec.name for t in tools if t.quarantined])
