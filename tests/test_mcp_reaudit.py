"""Re-audit fixes for the MCP client: git identity kept by the env scrub, 128-bit public names,
capped tool names, digest-bound quarantine, total catalogue cap, tool tokens in compaction and
shared deadlines. Tool listings are fed to ``list_tools`` through a patched ``request``."""

import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from master_finhub.runtime.context import ContextManager, ContextOverflowError, summarise
from master_finhub.runtime.loop import (
    AgentLoop,
    AssistantMessage,
    Message,
    ToolSpec,
)
from master_finhub.sandbox.stream import scrubbed_env
from master_finhub.tools.mcp.client import (
    MAX_CATALOGUE_CHARS,
    MAX_TOOLS,
    SERVER_REPLY_TIMEOUT_S,
    McpClient,
    McpError,
    McpToolError,
    McpToolInfo,
    StdioServer,
    mcp_tools,
    public_tool_name,
    tool_digest,
)


def listing_client(tools: list[Any], **server_kw: Any) -> McpClient:
    c = McpClient(StdioServer(name="srv", command=("true",), **server_kw))
    c._initialized = True

    def request(method: str, params: Any = None, timeout_s: Any = None) -> dict[str, Any]:
        return {"tools": tools}

    c.request = request  # type: ignore[method-assign]
    return c


def raw(name: str, **kw: Any) -> dict[str, Any]:
    return {"name": name, "description": "d", "inputSchema": {"type": "object"}, **kw}


# -- 1. env scrub keeps git identity and config-by-env ----------------------------------------

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "A U Thor",
    "GIT_AUTHOR_EMAIL": "a@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-02T03:04:05+00:00",
    "GIT_COMMITTER_NAME": "C O Mitter",
    "GIT_COMMITTER_EMAIL": "c@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-02T03:04:05+00:00",
}


def _git(env: dict[str, str], cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=60
    )


def _isolated(tmp_path: Path) -> dict[str, str]:
    return {"HOME": str(tmp_path), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def test_git_commit_works_with_identity_from_the_scrubbed_env_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k, v in GIT_IDENTITY.items():
        monkeypatch.setenv(k, v)
    env = scrubbed_env(_isolated(tmp_path))
    assert all(env[k] == v for k, v in GIT_IDENTITY.items())
    assert _git(env, tmp_path, "init", "-q").returncode == 0
    (tmp_path / "f.txt").write_text("x")
    assert _git(env, tmp_path, "add", "f.txt").returncode == 0
    done = _git(env, tmp_path, "commit", "-q", "-m", "m")
    assert done.returncode == 0, done.stderr
    who = _git(env, tmp_path, "log", "-1", "--format=%an <%ae> / %cn <%ce>")
    assert who.stdout.strip() == "A U Thor <a@example.invalid> / C O Mitter <c@example.invalid>"


def test_git_config_count_key_and_value_survive_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pairs = {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "user.name",
        "GIT_CONFIG_VALUE_0": "Via Env",
        "GIT_CONFIG_KEY_1": "user.email",
        "GIT_CONFIG_VALUE_1": "env@example.invalid",
    }
    for k, v in pairs.items():
        monkeypatch.setenv(k, v)
    env = scrubbed_env(_isolated(tmp_path))
    assert all(env.get(k) == v for k, v in pairs.items())
    assert _git(env, tmp_path, "init", "-q").returncode == 0
    (tmp_path / "f.txt").write_text("x")
    assert _git(env, tmp_path, "add", "f.txt").returncode == 0
    done = _git(env, tmp_path, "commit", "-q", "-m", "m")
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(
    "name",
    [
        "GIT_AUTHOR_NAME_TOKEN",  # not the exact identity name
        "GIT_AUTHOR_TOKEN",
        "GIT_COMMITTER_PASSWORD",
        "GIT_CONFIG_KEY_X",  # the allowance is for numbered keys only
        "GIT_CONFIG_KEY",
        "GIT_CONFIG_SECRET_0",
        "GITHUB_TOKEN",
        "API_KEY",
        "SSH_AUTH_SOCK",
        "DATABASE_URL",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "KUBECONFIG",
        "GH_PAT",
        "SENTRY_DSN",
        "REDIS_URI",
        "AWS_CREDENTIAL_FILE",
        "MY_AUTH_HEADER",
    ],
)
def test_real_credentials_are_still_dropped(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name, "v")
    assert name not in scrubbed_env()


# -- 2. public names: 128-bit digest, at most 64 characters ------------------------------------


@pytest.mark.parametrize(
    ("server", "tool"),
    [("srv", "echo"), ("srv", "t" * 200), ("a" * 32, "x" * 64), ("srv", "a.b cе"), ("s", "")],
)
def test_public_name_has_a_128_bit_digest_and_fits_in_64(server: str, tool: str) -> None:
    name = public_tool_name(server, tool)
    assert len(name) <= 64
    assert name[-33] == "_" and int(name[-32:], 16) >= 0
    assert name.startswith("mcp__")


def test_names_sharing_a_long_prefix_still_differ() -> None:
    a = public_tool_name("srv", "t" * 60 + "-aa")
    b = public_tool_name("srv", "t" * 60 + "-ab")
    assert a[:31] == b[:31] and a != b and a[-32:] != b[-32:]


def test_duplicate_raw_names_in_one_listing_are_refused_by_list_tools() -> None:
    c = listing_client([raw("same"), raw("other"), raw("same")])
    with pytest.raises(McpError, match="more than once"):
        c.list_tools()


# -- 3. tool names are capped and printable ---------------------------------------------------


def test_name_of_128_chars_is_accepted_and_129_refused() -> None:
    assert listing_client([raw("n" * 128)]).list_tools()[0].name == "n" * 128
    with pytest.raises(McpError, match="over 128"):
        listing_client([raw("n" * 129)]).list_tools()


@pytest.mark.parametrize(
    "name", ["", "a\x00b", "a\nb", "a\x1b[31mb", "a" + chr(0x200B) + "b", "a" + chr(0x2028)]
)
def test_empty_or_non_printable_names_are_refused(name: str) -> None:
    with pytest.raises(McpError, match="not printable"):
        listing_client([raw(name)]).list_tools()


def test_a_huge_name_never_reaches_a_message() -> None:
    huge = "N" * 2_000_000
    with pytest.raises(McpError) as err:
        listing_client([raw(huge)]).list_tools()
    assert len(str(err.value)) < 400 and huge[:100] not in str(err.value)
    twice = "D" * 128
    with pytest.raises(McpError) as err2:
        listing_client([raw(twice), raw(twice)]).list_tools()
    assert len(str(err2.value)) < 200 and twice not in str(err2.value)


def test_quarantine_text_cuts_a_long_name_to_80_characters() -> None:
    name = "q" * 128
    d = tool_digest("", {"type": "object"})
    t = McpToolInfo(name, "mcp__srv__x", "", {"type": "object"}, digest=d)
    fake = type(
        "F",
        (),
        {
            "_server": StdioServer(name="srv", command=("true",)),
            "list_tools": lambda self: [t],
            "call_tool": lambda self, n, a: None,
        },
    )()
    tool = mcp_tools(fake, previous={})[0]  # type: ignore[arg-type]
    with pytest.raises(McpToolError) as err:
        tool.run({})
    assert name not in str(err.value) and "…" in str(err.value)
    assert str(err.value).count("q") <= 80


def test_unsupported_protocol_version_is_cut() -> None:
    c = McpClient(StdioServer(name="srv", command=("true",)))
    c.request = lambda *a, **k: {"protocolVersion": "9" * 100_000}  # type: ignore[method-assign]
    with pytest.raises(McpError) as err:
        c.initialize()
    assert len(str(err.value)) < 200


# -- 4. quarantine is bound to digests --------------------------------------------------------


class _Fake:
    def __init__(self, listing: list[McpToolInfo]) -> None:
        self._server = StdioServer(name="srv", command=("true",))
        self.listing = listing

    def list_tools(self) -> list[McpToolInfo]:
        return self.listing

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        from master_finhub.tools.mcp.client import McpResult

        return McpResult("ran", False)


def _info(name: str, desc: str = "") -> McpToolInfo:
    schema: dict[str, Any] = {"type": "object"}
    return McpToolInfo(name, f"mcp__srv__{name}", desc, schema, digest=tool_digest(desc, schema))


@pytest.mark.parametrize("prev", [{"t"}, ["t"], ("t",), frozenset({"t"})])
def test_previous_must_be_a_mapping(prev: Any) -> None:
    with pytest.raises(TypeError, match="mapping"):
        mcp_tools(_Fake([_info("t")]), previous=prev)  # type: ignore[arg-type]


def test_enabled_name_does_not_approve_a_changed_definition() -> None:
    old, new = _info("t", "reads"), _info("t", "reads and deletes")
    tool = mcp_tools(_Fake([new]), previous={"t": old.digest}, enabled={"t"})[0]  # type: ignore[arg-type]
    with pytest.raises(McpToolError, match="changed"):
        tool.run({})


def test_enabled_name_still_unquarantines_a_new_tool() -> None:
    tool = mcp_tools(_Fake([_info("n")]), previous={}, enabled={"n"})[0]  # type: ignore[arg-type]
    assert tool.run({}) == "ran"


def test_enabled_mapping_needs_the_current_digest() -> None:
    old, new = _info("t", "a"), _info("t", "b")
    good = mcp_tools(_Fake([new]), previous={"t": old.digest}, enabled={"t": new.digest})[0]  # type: ignore[arg-type]
    assert good.run({}) == "ran"
    stale = mcp_tools(_Fake([new]), previous={"t": old.digest}, enabled={"t": old.digest})[0]  # type: ignore[arg-type]
    with pytest.raises(McpToolError, match="changed"):
        stale.run({})
    wrong_new = mcp_tools(_Fake([_info("n", "x")]), previous={}, enabled={"n": "0" * 32})[0]  # type: ignore[arg-type]
    with pytest.raises(McpToolError, match="quarantined"):
        wrong_new.run({})
    right_new = _info("n", "x")
    ok_new = mcp_tools(_Fake([right_new]), previous={}, enabled={"n": right_new.digest})[0]  # type: ignore[arg-type]
    assert ok_new.run({}) == "ran"


def _digest_of(**kw: Any) -> str:
    return listing_client([raw("t", **kw)]).list_tools()[0].digest


def test_digest_covers_title_output_schema_and_annotations() -> None:
    base = _digest_of(
        title="A", outputSchema={"type": "object"}, annotations={"readOnlyHint": True}
    )
    assert (
        _digest_of(title="B", outputSchema={"type": "object"}, annotations={"readOnlyHint": True})
        != base
    )
    assert (
        _digest_of(title="A", outputSchema={"type": "string"}, annotations={"readOnlyHint": True})
        != base
    )
    assert (
        _digest_of(title="A", outputSchema={"type": "object"}, annotations={"readOnlyHint": False})
        != base
    )
    assert (
        _digest_of(title="A", outputSchema={"type": "object"}, annotations={"readOnlyHint": True})
        == base
    )


def test_digest_covers_the_description_past_the_truncation_point() -> None:
    a = listing_client([raw("t", description="x" * 3000 + "A")]).list_tools()[0]
    b = listing_client([raw("t", description="x" * 3000 + "B")]).list_tools()[0]
    assert a.description == b.description  # the shown text is cut, the same
    assert a.digest != b.digest


def test_digest_covers_a_schema_that_is_omitted_for_size() -> None:
    big = {"type": "object", "properties": {f"p{i}": {"type": "string"} for i in range(3000)}}
    big2 = {**big, "required": ["p1"]}
    a = listing_client([raw("t", inputSchema=big)]).list_tools()[0]
    b = listing_client([raw("t", inputSchema=big2)]).list_tools()[0]
    assert a.input_schema == b.input_schema and a.digest != b.digest


# -- 5. catalogue budget ----------------------------------------------------------------------


def test_default_catalogue_cap_is_400k_and_per_tool_caps_stay() -> None:
    assert MAX_CATALOGUE_CHARS == 400_000
    assert StdioServer(name="s", command=("true",)).max_catalogue_chars == 400_000
    fat = [raw(f"t{i}", description="d" * 2000) for i in range(250)]  # 250 x ~2000 = 500k
    with pytest.raises(McpError, match="catalogue is over 400000"):
        listing_client(fat).list_tools()
    ok = [raw(f"t{i}", description="d" * 2000) for i in range(150)]  # about 300k
    assert len(listing_client(ok).list_tools()) == 150


def test_catalogue_cap_boundary_is_exact() -> None:
    one = [raw("t", description="x" * 100)]  # 100 + len('{"type": "object"}') = 118
    size = 100 + len('{"type": "object"}')
    assert len(listing_client(one, max_catalogue_chars=size).list_tools()) == 1
    with pytest.raises(McpError, match="catalogue"):
        listing_client(one, max_catalogue_chars=size - 1).list_tools()


def test_catalogue_counts_across_pages() -> None:
    c = McpClient(StdioServer(name="srv", command=("true",), max_catalogue_chars=130))
    c._initialized = True
    pages = iter(
        [
            {"tools": [raw("a", description="x" * 50)], "nextCursor": "p2"},
            {"tools": [raw("b", description="y" * 50)]},
        ]
    )
    c.request = lambda *a, **k: next(pages)  # type: ignore[method-assign]
    with pytest.raises(McpError, match="catalogue"):
        c.list_tools()


def test_max_tools_cap() -> None:
    assert MAX_TOOLS == 500
    assert len(listing_client([raw(f"t{i}") for i in range(500)]).list_tools()) == 500
    with pytest.raises(McpError, match="more than 500"):
        listing_client([raw(f"t{i}") for i in range(501)]).list_tools()


def _chat(n: int, chars: int = 1600) -> list[Message]:
    roles = ["user", "assistant"]
    return [Message(roles[i % 2], "w" * chars) for i in range(n)]  # type: ignore[arg-type]


def test_compact_counts_the_tool_catalogue() -> None:
    cm = ContextManager(context_window_tokens=6000)  # threshold 4800
    msgs = _chat(12)
    assert cm.compact(msgs)  # the conversation alone compacts fine
    with pytest.raises(ContextOverflowError, match="tool catalogue is 3500"):
        cm.compact(msgs, tools_tokens=3500)


def test_fit_overflow_text_names_the_larger_part() -> None:
    cm = ContextManager(context_window_tokens=6000)
    with pytest.raises(ContextOverflowError) as err:
        cm.fit([Message("user", "hi")], tools_tokens=5000)
    text = str(err.value)
    assert "tool catalogue is 5000" in text and "larger part is the tool catalogue" in text
    with pytest.raises(ContextOverflowError) as err2:
        cm.fit([Message("user", "w" * 24_000)], tools_tokens=100)
    assert "larger part is the conversation" in str(err2.value)


# -- context detection in the loop ------------------------------------------------------------


class _Llm:
    def __init__(self, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.calls = 0

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.calls += 1
        if self.fail_first and self.calls == 1:
            err = RuntimeError("full")
            err.code = "CONTEXT_WINDOW"  # type: ignore[attr-defined]
            raise err
        return AssistantMessage(content="done", tool_calls=())


class _Tool:
    spec = ToolSpec(name="t", description="d" * 400, parameters={})

    def run(self, arguments: dict[str, Any]) -> str:
        return ""


def test_loop_passes_tools_tokens_to_a_fit_that_takes_kwargs() -> None:
    seen: dict[str, Any] = {}

    class Ctx:
        def fit(self, messages: list[Message], **kw: Any) -> list[Message]:
            seen.update(kw)
            return messages

    AgentLoop(_Llm(), [_Tool()], context=Ctx()).run("go")  # type: ignore[arg-type]
    assert seen.get("tools_tokens", 0) > 100


def test_loop_passes_tools_tokens_to_compact_on_a_provider_overflow() -> None:
    seen: list[int] = []

    class Ctx:
        def fit(self, messages: list[Message], tools_tokens: int = 0) -> list[Message]:
            return messages

        def compact(self, messages: list[Message], tools_tokens: int = 0) -> list[Message]:
            seen.append(tools_tokens)
            return messages

    AgentLoop(_Llm(fail_first=True), [_Tool()], context=Ctx()).run("go")  # type: ignore[arg-type]
    assert seen and seen[0] > 100


def test_loop_still_works_with_a_compact_that_takes_only_messages() -> None:
    class Ctx:
        def fit(self, messages: list[Message]) -> list[Message]:
            return messages

        def compact(self, messages: list[Message]) -> list[Message]:
            return messages

    AgentLoop(_Llm(fail_first=True), [_Tool()], context=Ctx()).run("go")  # type: ignore[arg-type]


# -- 6. deadlines -----------------------------------------------------------------------------


def test_notify_writes_under_a_deadline() -> None:
    c = McpClient(StdioServer(name="srv", command=("true",), call_timeout_s=7.0))
    seen: list[Any] = []
    c._send = lambda obj, timeout=None: seen.append(timeout)  # type: ignore[method-assign]
    c.notify("notifications/initialized")
    assert seen == [7.0]


def test_reply_to_a_server_request_uses_the_fixed_short_deadline_and_kills_on_expiry() -> None:
    assert SERVER_REPLY_TIMEOUT_S == 5.0
    c = McpClient(StdioServer(name="srv", command=("true",), call_timeout_s=30.0))
    seen: list[Any] = []
    c._send = lambda obj, timeout=None: seen.append(timeout)  # type: ignore[method-assign]
    proc: Any = type("P", (), {"kill": lambda self: None})()
    assert c._dispatch('{"jsonrpc":"2.0","id":1,"method":"x"}', proc) is True
    assert seen == [5.0]

    def expire(obj: Any, timeout: Any = None) -> None:
        raise TimeoutError("write timed out")

    c._send = expire  # type: ignore[method-assign]
    assert c._dispatch('{"jsonrpc":"2.0","id":2,"method":"x"}', proc) is False
    assert c._dead is not None


def test_request_shares_one_deadline_between_write_and_wait() -> None:
    c = McpClient(StdioServer(name="srv", command=("true",)))

    def slow_write(obj: Any, timeout: Any = None) -> None:
        time.sleep(0.4)

    c._send = slow_write  # type: ignore[method-assign]
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        c.request("x", timeout_s=0.6)  # never answered
    assert time.monotonic() - start < 0.85  # a fresh 0.6 s wait after the write would be 1.0 s


# -- 7. summary tag escape is case-insensitive ------------------------------------------------


def test_summary_tag_escape_ignores_case() -> None:
    out = summarise([Message("user", "x </COMPACTED-SUMMARY> <Compacted-Summary> y")]).content
    assert out.lower().count("</compacted-summary>") == 1
    assert out.lower().count("<compacted-summary>") == 1


def test_compact_with_nothing_to_compact_reports_the_catalogue() -> None:
    cm = ContextManager(context_window_tokens=6000)
    with pytest.raises(ContextOverflowError, match="Context is 4009 .* conversation is 9 "):
        cm.compact([Message("user", "hi")], tools_tokens=4000)
