"""Proof for MCP tool hints and quarantine of a new write tool (O16, PC34).

adapted from references/paperclip/doc/MCP-ACCESS-GOVERNANCE.md:221 (MIT) and
references/openhands/src/api/canvas-ui-client-tool.ts:9 (MIT), idea only
"""

from typing import Any

import pytest

from master_finhub.tools.mcp.client import (
    McpResult,
    McpToolError,
    McpToolInfo,
    StdioServer,
    mcp_tools,
)


class FakeClient:
    """Duck-typed stand-in for McpClient: one listing per call, records every tools/call."""

    def __init__(self, listing: list[McpToolInfo]) -> None:
        self._server = StdioServer(name="crm", command=("true",))
        self.listing = listing
        self.calls: list[str] = []

    def list_tools(self) -> list[McpToolInfo]:
        return self.listing

    def call_tool(self, name: str, arguments: dict[str, Any]) -> McpResult:
        self.calls.append(name)
        return McpResult(f"ran {name}", False)


def info(name: str, *, read_only: bool) -> McpToolInfo:
    return McpToolInfo(
        name=name,
        public_name=f"mcp__crm__{name}",
        description="",
        input_schema={"type": "object"},
        read_only=read_only,
    )


BASE = [info("get_record", read_only=True), info("update_record", read_only=False)]


def names(tools: list[Any]) -> list[str]:
    return [t.spec.name for t in tools]


def test_first_listing_is_the_baseline_nothing_is_quarantined() -> None:
    client = FakeClient(BASE)
    tools = mcp_tools(client)
    assert names(tools) == ["mcp__crm__get_record", "mcp__crm__update_record"]
    assert tools[1].run({}) == "ran update_record"


def test_new_write_tool_is_refused_with_a_named_reason() -> None:
    client = FakeClient([*BASE, info("delete_record", read_only=False)])
    tools = {
        t.spec.name: t for t in mcp_tools(client, previous={"get_record": "", "update_record": ""})
    }
    with pytest.raises(McpToolError) as err:
        tools["mcp__crm__delete_record"].run({})
    assert "delete_record" in str(err.value) and "quarantined" in str(err.value)
    assert client.calls == []  # the server never saw the call


def test_existing_tools_stay_callable_after_a_refresh() -> None:
    client = FakeClient([*BASE, info("delete_record", read_only=False)])
    tools = {
        t.spec.name: t for t in mcp_tools(client, previous={"get_record": "", "update_record": ""})
    }
    assert tools["mcp__crm__update_record"].run({}) == "ran update_record"


def test_new_operator_trusted_tool_is_not_quarantined() -> None:
    client = FakeClient([*BASE, info("list_records", read_only=True)])
    tools = {
        t.spec.name: t
        for t in mcp_tools(
            client,
            previous={"get_record": "", "update_record": ""},
            trusted_read_only={"list_records"},
        )
    }
    assert tools["mcp__crm__list_records"].run({}) == "ran list_records"


def test_enabling_a_quarantined_tool_by_name_lets_it_run() -> None:
    client = FakeClient([*BASE, info("delete_record", read_only=False)])
    tools = {
        t.spec.name: t
        for t in mcp_tools(
            client, previous={"get_record": "", "update_record": ""}, enabled={"delete_record"}
        )
    }
    assert tools["mcp__crm__delete_record"].run({}) == "ran delete_record"


def test_tool_without_a_hint_counts_as_write() -> None:
    raw = McpToolInfo("x", "mcp__crm__x", "", {"type": "object"})
    assert raw.read_only is False


def test_list_tools_reads_the_read_only_hint() -> None:
    from master_finhub.tools.mcp import client as mod

    class Wire(mod.McpClient):
        def __init__(self) -> None:
            super().__init__(StdioServer(name="crm", command=("true",)))
            self._initialized = True

        def request(self, method: str, params: Any = None, **kw: Any) -> dict[str, Any]:
            return {
                "tools": [
                    {"name": "a", "annotations": {"readOnlyHint": True}},
                    {"name": "b", "annotations": {"readOnlyHint": False}},
                    {"name": "c"},
                ]
            }

    got = {t.name: t.read_only for t in Wire().list_tools()}
    assert got == {"a": True, "b": False, "c": False}
