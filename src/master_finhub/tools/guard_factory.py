"""One place that builds the tool guard for an entry point (CLI, server) from a permission mode.

The base command guard always runs first, then the mode guard. Without a workspace folder the
mode guard cannot judge a write, so only tools classed as read pass (and full-access keeps just
the base guard).
"""

from __future__ import annotations

from collections.abc import Mapping

from master_finhub.runtime.loop import ToolCall, ToolGuard
from master_finhub.sandbox.workspace import WORKSPACE_ENV_VAR, Workspace
from master_finhub.tools.permissions import Mode, ToolClass, effective_guard
from master_finhub.tools.safety import guard_tool_call

MODES: tuple[Mode, ...] = ("read-only", "workspace-write", "full-access")

# One entry per tool an entry point registers; a tool that is not listed is "unknown".
DEFAULT_TOOL_CLASSES: dict[str, ToolClass] = {"echo": "read"}


def build_guard(mode: Mode, tool_classes: Mapping[str, ToolClass] | None = None) -> ToolGuard:
    classes = dict(DEFAULT_TOOL_CLASSES if tool_classes is None else tool_classes)
    try:
        workspace = Workspace()
    except (FileNotFoundError, NotADirectoryError):
        workspace = None
    if workspace is not None:
        return effective_guard(mode, workspace, tool_classes=classes)
    if mode == "full-access":
        return guard_tool_call

    def guard(call: ToolCall) -> str | None:
        denial = guard_tool_call(call)
        if denial is not None or classes.get(call.name) == "read":
            return denial
        return (
            f"{mode} mode: {call.name} needs a workspace folder. "
            f"Set {WORKSPACE_ENV_VAR} to an existing folder."
        )

    return guard
