"""ApprovalStore: the caller contract of the MCP client (persist approved_digests and approved_infos)
kept by a small JSON file, written atomically with mode 0600, failing closed when it cannot be trusted.
"""

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from master_finhub.tools.mcp.client import (
    QUARANTINE_NOTICE,
    ApprovalStore,
    McpClient,
    StdioServer,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="mode bits are POSIX")


def fake_client(listing: dict[str, Any]) -> McpClient:
    c = McpClient(StdioServer(name="srv", command=("true",)))
    c._initialized = True

    def request(method: str, params: Any = None, timeout_s: Any = None) -> dict[str, Any]:
        return {"tools": listing["tools"]}

    c.request = request  # type: ignore[method-assign]
    return c


def raw(name: str, desc: str = "d") -> dict[str, Any]:
    return {"name": name, "description": desc, "inputSchema": {"type": "object"}}


def state(tools: list[Any]) -> dict[str, bool]:
    return {t._info.name: t.quarantined for t in tools}


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "approvals.json"


def test_first_listing_is_the_baseline_and_is_saved(path: Path) -> None:
    c = fake_client({"tools": [raw("a"), raw("b")]})
    assert not path.exists()
    assert state(ApprovalStore(path).mcp_tools(c)) == {"a": False, "b": False}
    assert path.exists()


def test_round_trip_in_a_new_process_keeps_approved_tools_unquarantined(path: Path) -> None:
    c = fake_client({"tools": [raw("a"), raw("b")]})
    ApprovalStore(path).mcp_tools(c)
    again = ApprovalStore(path).mcp_tools(c)  # a new object, as after a restart
    assert state(again) == {"a": False, "b": False}


def test_a_changed_tool_stays_quarantined_over_restarts_and_shows_the_approved_text(
    path: Path,
) -> None:
    listing: dict[str, Any] = {"tools": [raw("t", "benign text")]}
    c = fake_client(listing)
    ApprovalStore(path).mcp_tools(c)
    listing["tools"] = [raw("t", "EVIL text")]
    for _ in range(3):
        (tool,) = ApprovalStore(path).mcp_tools(c)
        assert tool.quarantined
        assert "benign text" in tool.spec.description and QUARANTINE_NOTICE in tool.spec.description
        assert "EVIL" not in tool.spec.description
    assert "EVIL" not in path.read_text()


def test_a_new_tool_is_quarantined_and_stays_so(path: Path) -> None:
    listing: dict[str, Any] = {"tools": [raw("a")]}
    c = fake_client(listing)
    ApprovalStore(path).mcp_tools(c)
    listing["tools"] = [raw("a"), raw("b")]
    for _ in range(2):
        assert state(ApprovalStore(path).mcp_tools(c)) == {"a": False, "b": True}


def test_the_operator_can_approve_a_changed_tool_by_digest_and_it_is_then_stored(
    path: Path,
) -> None:
    listing: dict[str, Any] = {"tools": [raw("t", "v1")]}
    c = fake_client(listing)
    ApprovalStore(path).mcp_tools(c)
    listing["tools"] = [raw("t", "v2")]
    (tool,) = ApprovalStore(path).mcp_tools(c)
    digest = tool._info.digest
    (tool,) = ApprovalStore(path).mcp_tools(c, enabled={"t": digest})
    assert not tool.quarantined
    assert state(ApprovalStore(path).mcp_tools(c)) == {"t": False}  # approval persisted


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        "",
        "[]",
        "null",
        '{"version": 1, "digests": {"a": 1}, "infos": {}}',
        '{"version": 1, "digests": [], "infos": {}}',
        '{"version": 1, "digests": {"a": "x"}}',
        '{"version": 2, "digests": {"a": "x"}, "infos": {}}',
        '{"version": 1, "digests": {"a": "x"}, "infos": {"a": {"name": 3}}}',
        '{"version": 1, "digests": {"a": "x"}, "infos": {',
    ],
)
def test_a_corrupt_file_quarantines_everything(path: Path, content: str) -> None:
    c = fake_client({"tools": [raw("a"), raw("b")]})
    ApprovalStore(path).mcp_tools(c)
    path.write_text(content)
    path.chmod(0o600)
    tools = ApprovalStore(path).mcp_tools(c)
    assert state(tools) == {"a": True, "b": True}
    # and it stays closed: the file the failed load rewrote approves nothing either
    assert state(ApprovalStore(path).mcp_tools(c)) == {"a": True, "b": True}


def test_an_unparseable_file_loads_as_empty_not_as_a_first_listing(path: Path) -> None:
    path.write_text("{")
    path.chmod(0o600)
    previous, infos = ApprovalStore(path).load()
    assert previous == {} and infos == {}


def _tampered(path: Path, edit: Any) -> None:
    c = fake_client({"tools": [raw("a")]})
    ApprovalStore(path).mcp_tools(c)
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    assert state(ApprovalStore(path).mcp_tools(c)) == {"a": True}


def test_an_unknown_version_of_an_otherwise_good_file_is_not_trusted(path: Path) -> None:
    _tampered(path, lambda d: d.update(version=2))


def test_one_bad_entry_anywhere_distrusts_the_whole_file(path: Path) -> None:
    _tampered(path, lambda d: d["digests"].update(zzz=5))


def test_a_stored_definition_of_the_wrong_shape_distrusts_the_whole_file(path: Path) -> None:
    _tampered(path, lambda d: d["infos"]["a"].update(read_only="yes"))


def test_a_file_that_cannot_be_examined_is_not_trusted(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = fake_client({"tools": [raw("a")]})
    ApprovalStore(path).mcp_tools(c)

    def denied(p: Any) -> Any:
        raise PermissionError("no")

    monkeypatch.setattr(os, "lstat", denied)
    assert ApprovalStore(path).load() == ({}, {})


def test_a_device_or_pipe_is_not_read(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ApprovalStore(path).mcp_tools(fake_client({"tools": [raw("a")]}))
    real = os.lstat(path)
    fake = os.stat_result((stat.S_IFIFO | 0o600, *tuple(real)[1:]))
    monkeypatch.setattr(os, "lstat", lambda p: fake)
    assert ApprovalStore(path).load() == ({}, {})


def test_save_accepts_a_one_shot_iterable(path: Path) -> None:
    tools = ApprovalStore(path).mcp_tools(fake_client({"tools": [raw("a"), raw("b")]}))
    ApprovalStore(path).save(t for t in tools)
    data = json.loads(path.read_text())
    assert set(data["digests"]) == {"a", "b"} and set(data["infos"]) == {"a", "b"}


def test_a_missing_file_is_a_first_listing_not_a_corrupt_one(path: Path) -> None:
    assert ApprovalStore(path).load() == (None, {})


@posix_only
def test_the_file_is_written_with_mode_0600_whatever_the_umask(path: Path) -> None:
    old = os.umask(0)
    try:
        ApprovalStore(path).mcp_tools(fake_client({"tools": [raw("a")]}))
    finally:
        os.umask(old)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@posix_only
def test_a_loose_existing_file_is_tightened_by_the_next_save(path: Path) -> None:
    c = fake_client({"tools": [raw("a")]})
    ApprovalStore(path).mcp_tools(c)
    path.chmod(0o600)
    ApprovalStore(path).mcp_tools(c)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@posix_only
@pytest.mark.parametrize("mode", [0o620, 0o602, 0o666, 0o660])
def test_a_file_others_can_write_is_not_trusted(path: Path, mode: int) -> None:
    c = fake_client({"tools": [raw("a")]})
    ApprovalStore(path).mcp_tools(c)
    path.chmod(mode)
    assert state(ApprovalStore(path).mcp_tools(c)) == {"a": True}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600  # and the save that followed tightened it


@posix_only
def test_a_file_that_is_not_a_regular_file_is_not_trusted(tmp_path: Path, path: Path) -> None:
    target = tmp_path / "elsewhere.json"
    c = fake_client({"tools": [raw("a")]})
    ApprovalStore(path).mcp_tools(c)
    path.rename(target)
    path.symlink_to(target)
    assert state(ApprovalStore(path).mcp_tools(c)) == {"a": True}


def test_a_failed_write_leaves_the_old_file_and_no_temp_file(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    listing: dict[str, Any] = {"tools": [raw("a")]}
    c = fake_client(listing)
    ApprovalStore(path).mcp_tools(c)
    before = path.read_bytes()
    listing["tools"] = [raw("a"), raw("b")]

    def boom(*a: Any, **k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        ApprovalStore(path).mcp_tools(c, trusted_read_only=["b"])
    assert path.read_bytes() == before
    assert [p.name for p in path.parent.iterdir()] == [path.name]


def test_the_file_holds_only_approved_digests_as_json(path: Path) -> None:
    ApprovalStore(path).mcp_tools(fake_client({"tools": [raw("a")]}))
    data = json.loads(path.read_text())
    assert data["version"] == 1 and set(data["digests"]) == {"a"} and set(data["infos"]) == {"a"}


def test_save_without_a_listing_to_trust_does_not_invent_approvals(path: Path) -> None:
    ApprovalStore(path).save([])
    assert json.loads(path.read_text())["digests"] == {}


def test_nothing_imports_the_store_outside_its_module() -> None:
    """Not wired into any entrypoint."""
    import subprocess

    src = Path(__file__).resolve().parent.parent / "src"
    out = subprocess.run(
        ["grep", "-rl", "ApprovalStore", str(src), "--include=*.py"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    assert [Path(p).name for p in out] == ["client.py"]
