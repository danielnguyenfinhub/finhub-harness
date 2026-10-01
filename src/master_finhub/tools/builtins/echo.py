"""Built-in echo tool: returns its ``text`` argument."""

from __future__ import annotations

from typing import Any

from master_finhub.runtime.loop import ToolSpec


class EchoTool:
    spec = ToolSpec(
        name="echo",
        description="Return the given text unchanged. Use to test the tool loop.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        idempotent=True,
    )

    def run(self, arguments: dict[str, Any]) -> str:
        return str(arguments["text"])
